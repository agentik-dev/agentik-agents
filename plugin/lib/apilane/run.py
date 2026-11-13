"""One shard: its argv behind the wall, its environment, its process group, its record.

`run_shard` is the one function of this row that starts the CLI, and it starts only the
path it is handed. It prints nothing: it returns a `ShardResult`. The key is asked for once,
at the spawn, and goes into the child's environment alone: never an argument, a file, a
record or a return value. The record is `<state>/runs/<fanout>-<NN>/run.json`, written at
the start and rewritten by one rename at the end; the result and stderr sit beside it.
Folders are 0700 and files 0600.
"""
import collections
import datetime
import json
import math
import os
import signal
import subprocess

from . import argv as _argv
from . import classify as _classify
from . import env as _env
from . import proc as _proc
from . import types as _types

ShardResult = collections.namedtuple(
    "ShardResult", "label type state cost_usd estimated result_path reason model")

SCHEMA = "agentik.api.run/1"

# The CLI's ceiling is checked between requests, so the request that crosses it still
# completes: a $0.01 cap spent $0.0117. The grant is deflated by this factor.
OVERSHOOT_FACTOR = 1.35

# A wall's own failure, before the CLI starts, is an exit in the sysexits range with
# nothing on stdout (a profile the kernel refuses exits 65); the CLI always answers an
# `--output-format json` run with an envelope or exits outside that range.
WALL_EXITS = range(64, 79)

# Between TERM and KILL to the shard's process group.
GRACE_SEC = 5

# The child's PATH: the folder of the CLI's resolved path, then the system's own.
SYSTEM_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mkdir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)


def _write(path, data):
    """Write `data` to `path` by one rename, mode 0600."""
    tmp = "%s.tmp.%d" % (path, os.getpid())
    if os.path.lexists(tmp):
        os.unlink(tmp)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def _write_json(path, obj):
    _write(path, (json.dumps(obj, sort_keys=True) + "\n").encode())


def _envelope(text):
    start = text.find("{")
    if start < 0:
        return None
    try:
        d = json.loads(text[start:], strict=False)
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def _cost(envelope):
    """The envelope's billed cost, or None when it has no usable figure (NaN included)."""
    v = envelope.get("total_cost_usd") if envelope else None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = float(v)
    if not math.isfinite(v) or v < 0:
        return None
    return v


def _end_group(child):
    """End the shard's process group: TERM, a grace, then KILL."""
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        child.wait(GRACE_SEC)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _seconds(n):
    return "%g" % n


def run_shard(shard, *, grant_usd, fanout, number, session, roots, lane, claude, dirs,
              timeout_sec, restricted=True, wrap=None, key=None):
    """Run one shard to its end and return its ShardResult (seams §4)."""
    if wrap is None:
        from apilane import wall
        wrap = wall.wrap
    if key is None:
        from apilane import key as _key

        def key():
            return _key.load(roots)

    t = _types.TYPES.get(getattr(shard, "type", None))
    if t is None:
        raise ValueError("type: not one of %s" % ", ".join(sorted(_types.TYPES)))
    dirs = list(dirs)
    run_id = "%s-%02d" % (fanout, number)
    runs = os.path.join(roots.state, "runs")
    run_dir = os.path.join(runs, run_id)
    for d in (roots.state, runs, run_dir, os.path.join(run_dir, "tmp"),
              os.path.join(run_dir, "config")):
        _mkdir(d)
    cmd = _argv.build(shard, claude=claude, dirs=dirs, ceiling_usd=grant_usd / OVERSHOOT_FACTOR,
                      run_dir=run_dir, restricted=restricted)
    walled = wrap(cmd, read=dirs, write=[run_dir], net="all", home=roots.home)
    record = {"schema": SCHEMA, "id": run_id, "pid": None, "pid_started": None,
              "type": t.name, "model": t.model, "label": shard.label, "session": session,
              "fanout": fanout, "grant_usd": grant_usd, "started": _now(), "state": "running"}
    run_json = os.path.join(run_dir, "run.json")

    def finish(state, reason, rc, cost_usd, estimated, result_path):
        record.update(state=state, rc=rc, ended=_now(), cost_usd=cost_usd)
        _write_json(run_json, record)
        return ShardResult(shard.label, t.name, state, cost_usd, estimated, result_path,
                           reason, t.model)

    secret = key()
    child_env = _env.build(key=secret, run_dir=run_dir, home=roots.home,
                           path=os.pathsep.join((os.path.dirname(claude),) + SYSTEM_PATH),
                           proxy=getattr(lane, "proxy", None),
                           ca_file=getattr(lane, "ca_file", None))
    try:
        child = subprocess.Popen(walled, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, env=child_env, cwd=run_dir,
                                 start_new_session=True, close_fds=True)
    except OSError:
        # Nothing was executed, so no request was made: zero is a measurement here.
        return finish("wall", "wall:127", 127, 0.0, False, None)
    finally:
        child_env = None
    record["pid"] = child.pid
    record["pid_started"] = _proc.started(child.pid)
    _write_json(run_json, record)

    timed_out = False
    try:
        out, err = child.communicate(input=shard.prompt.encode(), timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        timed_out = True
        _end_group(child)
        out, err = child.communicate()
    rc = child.returncode
    text = (out or b"").decode("utf-8", "replace")
    errtext = (err or b"").decode("utf-8", "replace")
    envelope = None if timed_out else _envelope(text)
    billed = _cost(envelope)

    if _classify.holds_secret(text + "\n" + errtext, secret):
        state, reason = "leak", None
    elif timed_out:
        state, reason = "timeout", "timeout:%s" % _seconds(timeout_sec)
    elif not text.strip() and rc in WALL_EXITS:
        state, reason = "wall", "wall:%d" % rc
    else:
        state, reason = _classify.verdict(envelope, rc, dirs, t.schema is not None,
                                          raw=text, key=secret)
    secret = None

    if billed is None or timed_out:
        cost_usd, estimated = float(grant_usd), True
        if state == "ok":
            reason = "no-cost"
    else:
        cost_usd, estimated = billed, False

    result_path = None
    if state != "leak":
        _write(os.path.join(run_dir, "stderr.txt"), errtext.encode())
        if state != "ceiling" and text:
            result_path = os.path.join(run_dir, "result.json")
            _write(result_path, text.encode())
    return finish(state, reason, rc, cost_usd, estimated, result_path)
