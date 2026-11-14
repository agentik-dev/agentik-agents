#!/usr/bin/python3
"""The API lane's probe: the CLI once, on a made-up key, against a loopback stub, behind the wall.

`run` builds the argv and the environment a shard gets, from the same two builders, changed only
in the key (made up, new each run), the base URL (the stub's) and the prompt, and runs it under
`wrap(..., net="loopback")`: no request can leave the machine, so the probe spends nothing. The
stub asks for three reads: a file in the job dir, a canary in a walled folder, and a canary in
the system's temp folder, outside both. Five checks: `key` (each request carried the made-up key
and no bearer token), `tools` (only Read, Grep and Glob offered), `walled` (the walled canary's
read was refused and its text came back in no request), `restricted` (whether the outside
canary stayed out; recorded, never deciding `ok`) and `read` (the job file's text came back).
A CLI that refuses `--restricted` beside `--bare` is run once more without it, and `restricted`
is null. The record is `<roots.state>/probe.json`; a pass holds for one CLI version.

Where the wall gives the command a network namespace of its own (bwrap), a stub outside cannot be
reached from inside, so the stub starts inside the wall: `run` picks a port, hands the builders
the base URL on it, and wraps one launcher, `launch`, that starts the stub there, runs the CLI
with its own environment and stdin, and writes the stub's requests to a file the probe reads back.
"""

import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import types
import urllib.parse

from apilane import stubapi

SCHEMA = "agentik.api.probe/1"
CHECKS = ("key", "tools", "walled", "restricted", "read")
ALLOWED_TOOLS = ("Read", "Grep", "Glob")
CEILING_USD = 0.05
TIMEOUT = 60
PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
PROMPT = "Read each file you are asked to read, then answer in one line."
LAUNCH_PY = "/usr/bin/python3"
LIB = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
# The launcher's body, run as `<python> -I -c _LAUNCH <lib> <out> <names> <reads...> -- <argv...>`.
_LAUNCH = ("import sys; sys.path.insert(0, sys.argv[1]); from apilane import probe; "
           "sys.exit(probe.launch(sys.argv[2:]))")


class ProbeError(Exception):
    """An error a user may see: `code` and `fields`; `str()` is the code."""

    def __init__(self, code, **fields):
        super().__init__(code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


def cli_version(claude):
    """The first word of `<claude> --version`."""
    try:
        done = subprocess.run([claude, "--version"], stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=30, env={"PATH": PATH})
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ProbeError("probe.fail", check="version", detail=type(e).__name__)
    words = done.stdout.decode("utf-8", "replace").split()
    if done.returncode != 0 or not words:
        raise ProbeError("probe.fail", check="version", detail="exit %d" % done.returncode)
    return words[0]


def read(roots):
    try:
        with open(os.path.join(roots.state, "probe.json"), encoding="utf-8") as handle:
            rec = json.load(handle)
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def _passes(rec, version):
    return (isinstance(rec, dict) and rec.get("schema") == SCHEMA and rec.get("ok") is True
            and rec.get("cli_version") == version)


def passed(roots, version):
    return _passes(read(roots), version)


def ensure(*, claude, roots, build_argv=None, build_env=None, wrap=None, emit=None, inside=None):
    """The probe's record for the installed CLI: the one on disk when it passes, else a run."""
    version = cli_version(claude)
    rec = read(roots)
    if _passes(rec, version):
        return rec
    if emit is not None:
        emit("probe.start", cli_version=version)
    rec = run(claude=claude, roots=roots, build_argv=build_argv, build_env=build_env, wrap=wrap,
              inside=inside)
    if not rec["ok"]:
        bad = [c for c in rec["checks"] if c["name"] != "restricted" and c["ok"] is not True]
        raise ProbeError("probe.fail", check=bad[0]["name"], detail=bad[0]["detail"])
    return rec


def run(*, claude, roots, build_argv=None, build_env=None, wrap=None, inside=None):
    """Run the CLI once behind the wall; write and return the record. A fail is ok false.
    `inside` puts the stub inside the wall; None is `_stub_inside(wrap)`."""
    if build_argv is None:
        from apilane.argv import build as build_argv
    if build_env is None:
        from apilane.env import build as build_env
    if wrap is None:
        from apilane.wall import wrap
    if inside is None:
        inside = _stub_inside(wrap)
    version = cli_version(claude)
    _private_dir(roots.state)
    base = os.path.join(roots.state, "probe")
    shutil.rmtree(base, ignore_errors=True)
    outside = os.path.realpath(tempfile.mkdtemp(prefix="agentik-probe-"))
    try:
        base = _private_dir(base)
        job = _private_dir(os.path.join(base, "job"))
        run_dir = _private_dir(os.path.join(base, "run"))
        walled = _private_dir(os.path.join(base, "walled"))
        stub_dir = _private_dir(os.path.join(base, "stub")) if inside else None
        texts, files = {}, {}
        for name, folder, leaf in (("read", job, "notes.txt"), ("walled", walled, "canary.txt"),
                                   ("outside", outside, "canary.txt")):
            texts[name] = "probe-%s-%s" % (name, secrets.token_hex(8))
            files[name] = os.path.join(folder, leaf)
            with open(files[name], "w", encoding="utf-8") as handle:
                handle.write(texts[name] + "\n")
        step = dict(claude=claude, roots=roots, build_argv=build_argv, build_env=build_env,
                    wrap=wrap, job=job, run_dir=run_dir, stub_dir=stub_dir,
                    reads=[files["read"], files["walled"], files["outside"]])
        got = _attempt(restricted=True, **step)
        flag = True
        if (got["rc"] != 0 and not got["requests"] and "restricted" in got["output"].lower()):
            got = _attempt(restricted=False, **step)
            flag = None
        rec = _record(version, got, texts, flag)
    finally:
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)
    _write_private(os.path.join(roots.state, "probe.json"), rec)
    return rec


def _stub_inside(wrap):
    """The stub must start inside the wall: the real wall is handed in, and it is bwrap's."""
    try:
        from apilane import wall
    except ImportError:
        return False
    return wrap is wall.wrap and wall.backend() == "bwrap"


def _launch_python():
    """The launcher's interpreter, by its real path: the system's, else this one."""
    if os.path.isfile(LAUNCH_PY) and os.access(LAUNCH_PY, os.X_OK):
        return os.path.realpath(LAUNCH_PY)
    return os.path.realpath(sys.executable)


def _free_port():
    with socket.socket() as s:
        s.bind((stubapi.HOST, 0))
        return s.getsockname()[1]


def _attempt(*, claude, roots, build_argv, build_env, wrap, job, run_dir, stub_dir, reads,
             restricted):
    if stub_dir is not None:
        return _attempt_inside(claude=claude, roots=roots, build_argv=build_argv,
                               build_env=build_env, wrap=wrap, job=job, run_dir=run_dir,
                               stub_dir=stub_dir, reads=reads, restricted=restricted)
    key = "agentik-probe-%s" % secrets.token_hex(16)
    stub = stubapi.Stub(reads=reads)
    url = stub.start()
    try:
        shard = types.SimpleNamespace(label="probe", type="explore", prompt=PROMPT)
        argv = build_argv(shard, claude=claude, dirs=[job], ceiling_usd=CEILING_USD,
                          run_dir=run_dir, restricted=restricted)
        env = build_env(key=key, run_dir=run_dir, home=roots.home, path=PATH, base_url=url)
        cmd = wrap(argv, read=[job], write=[run_dir], net="loopback", home=roots.home)
        rc, output = _spawn(cmd, env, job, shard.prompt)
    finally:
        stub.stop()
    return {"key": key, "rc": rc, "output": output, "requests": list(stub.requests)}


def _attempt_inside(*, claude, roots, build_argv, build_env, wrap, job, run_dir, stub_dir,
                    reads, restricted):
    key = "agentik-probe-%s" % secrets.token_hex(16)
    url = "http://%s:%d" % (stubapi.HOST, _free_port())
    out = os.path.join(stub_dir, "requests.json")
    if os.path.exists(out):
        os.unlink(out)
    shard = types.SimpleNamespace(label="probe", type="explore", prompt=PROMPT)
    argv = build_argv(shard, claude=claude, dirs=[job], ceiling_usd=CEILING_USD,
                      run_dir=run_dir, restricted=restricted)
    env = build_env(key=key, run_dir=run_dir, home=roots.home, path=PATH, base_url=url)
    python = _launch_python()
    launcher = ([python, "-I", "-c", _LAUNCH, LIB, out, ",".join(sorted(env))] + list(reads)
                + ["--"] + list(argv))
    # the wall binds the launcher's own folder; the CLI's, and the launcher's code, are read
    read = [job, LIB, os.path.dirname(os.path.realpath(argv[0]))]
    if python != os.path.realpath(LAUNCH_PY):
        read.append(os.path.realpath(sys.base_prefix))
    cmd = wrap(launcher, read=read, write=[run_dir, stub_dir], net="loopback", home=roots.home)
    rc, output = _spawn(cmd, env, job, shard.prompt)
    return {"key": key, "rc": rc, "output": output, "requests": _requests(out)}


def _requests(path):
    """The requests the launcher's stub wrote, each of the stub's shape; none when unreadable."""
    try:
        with open(path, encoding="utf-8") as handle:
            got = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(got, list):
        return []
    return [r for r in got if isinstance(r, dict) and isinstance(r.get("credentials"), dict)
            and isinstance(r.get("tools"), list) and isinstance(r.get("turn"), int)
            and isinstance(r.get("body"), str)]


def launch(args):
    """The launcher, inside the wall: `<out> <names> <reads...> -- <argv...>`. The stub on the
    base URL's port, then the CLI on stdin and the environment's `<names>` (comma-joined) alone,
    so what an interpreter adds at its start never reaches it; the stub's requests to `<out>`;
    the CLI's exit (127 where it cannot start)."""
    out, names, at = args[0], args[1].split(","), args.index("--")
    reads, argv = args[2:at], args[at + 1:]
    env = {k: os.environ[k] for k in names if k in os.environ}
    stub = stubapi.Stub(reads=reads)
    rc = 127
    try:
        stub.start(port=urllib.parse.urlsplit(os.environ.get("ANTHROPIC_BASE_URL", "")).port or 0)
        try:
            rc = subprocess.call(argv, env=env)
        except OSError:
            rc = 127
    finally:
        stub.stop()
        _write_private(out, list(stub.requests))
    return rc if rc >= 0 else 128 - rc


def _spawn(cmd, env, cwd, prompt):
    """Run it with the prompt on stdin, as a shard is run: the argv carries no prompt."""
    proc = subprocess.Popen(cmd, env=env, cwd=cwd, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    try:
        out, err = proc.communicate(input=prompt.encode(), timeout=TIMEOUT)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        out, err = proc.communicate()
        rc = "timeout"
    return rc, (out + b"\n" + err).decode("utf-8", "replace")[-4000:]


def _record(version, got, texts, flag):
    reqs, key = got["requests"], got["key"]
    bodies = [r["body"] for r in reqs]
    came_back = {name: any(text in b for b in bodies) for name, text in texts.items()}
    furthest = max([r["turn"] for r in reqs] or [-1])
    checks = []

    def check(name, ok, detail):
        checks.append({"name": name, "ok": ok, "detail": detail})

    if not reqs:
        check("key", False, "no request reached the stub (exit %s)" % got["rc"])
    else:
        lacking = [i for i, r in enumerate(reqs) if key not in r["credentials"].values()]
        bearer = [i for i, r in enumerate(reqs)
                  if any(str(v).lower().startswith("bearer") for v in r["credentials"].values())]
        if lacking:
            check("key", False, "request %d lacked the made-up key" % (lacking[0] + 1))
        elif bearer:
            check("key", False, "request %d carried a bearer token" % (bearer[0] + 1))
        else:
            check("key", True, "%d requests, each on the made-up key alone" % len(reqs))
    offered = sorted({t for r in reqs for t in r["tools"]}, key=str)
    extra = [str(t) for t in offered if t not in ALLOWED_TOOLS]
    if not reqs:
        check("tools", False, "no request reached the stub")
    elif extra:
        check("tools", False, "offered beyond Read, Grep and Glob: %s" % ", ".join(extra))
    else:
        check("tools", True, "offered: %s" % ", ".join(map(str, offered)))
    if came_back["walled"]:
        check("walled", False, "the walled canary's text came back")
    elif furthest < 2:
        check("walled", False, "never answered: the CLI stopped before the walled read")
    else:
        check("walled", True, "the walled canary's read was refused")
    if flag is None:
        restricted = None
        check("restricted", None, "the CLI refused --restricted beside --bare; run without it")
    elif came_back["outside"]:
        restricted = False
        check("restricted", False, "the outside canary's text came back")
    elif furthest < 3:
        restricted = False
        check("restricted", False, "unproved: the CLI stopped before the outside read")
    else:
        restricted = True
        check("restricted", True, "the outside canary stayed out")
    if came_back["read"]:
        check("read", True, "the job file's text came back")
    else:
        check("read", False, "the job file's text never came back (exit %s)" % got["rc"])
    ok = all(c["ok"] is True for c in checks if c["name"] != "restricted")
    return {"schema": SCHEMA, "cli_version": version,
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ok": ok,
            "restricted": restricted, "checks": checks}


def _private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return os.path.realpath(path)


def _write_private(path, rec):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".probe-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(rec, handle, indent=1, sort_keys=False)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
