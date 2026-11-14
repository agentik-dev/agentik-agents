"""A fan-out's own folder, and the verbs that read or end a run by its id (design/21 §10, packet al7).

`<state>/fanouts/<id>/`, 0700: `start.json`, written by the verb at the reservation; `fanout.json`,
the object `--json` prints plus `tag` and `ended`, written when the run returns; and a detached
run's `log.txt`. Each file is 0600 and written by one rename. `wait`, `status` and `stop` match an
ID against the job's id pattern before they join it to a path. The sweep prunes old folders and
records once at a fan-out's start. Nothing here prints: a verb returns what its caller prints, or
raises a RunError with a `code` (`run.unknown`, `run.none`, `run.two`, `run.path`, `run.starting`,
`run.record`, `job.long`, `id.used`), whose sentence is `messages.py`'s.
"""
import json
import math
import os
import shutil
import signal
import time

from apilane import job as _job

FOLDER = "fanouts"
START_SCHEMA = "agentik.fanout.start/1"
BOUND_SEC = 86400     # a detached job's latest end, a constant and no setting (A2-5)
WAIT_SEC = 540
START_SEC = 120       # the parent's wait for the child's reservation
STOP_SEC = 10
KILL_SEC = 2
WEEK = 7 * 86400
DAY = 86400


class RunError(Exception):
    def __init__(self, code, **fields):
        Exception.__init__(self, code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


def _alive(alive):
    if alive is None:
        from apilane import proc
        alive = proc.alive
    return alive


def secs(v):
    v = float(v)
    return "%d" % v if v.is_integer() else "%g" % v


def check(word):
    """The id itself, or `run.path`: nothing is joined to a path before this holds."""
    if not isinstance(word, str) or not _job.ID_RE.match(word):
        raise RunError("run.path", word=json.dumps(word) if isinstance(word, str) else repr(word))
    return word


def folder(roots, fid):
    return os.path.join(roots.state, FOLDER, check(fid))


def bound(job):
    """(rounds, seconds): the most a job can run, ceil(shards / jobs) x timeout_sec."""
    rounds = int(math.ceil(len(job.shards) / float(job.jobs)))
    return rounds, rounds * job.timeout_sec


def check_bound(job):
    rounds, sec = bound(job)
    if sec > BOUND_SEC:
        raise RunError("job.long", id=job.id, rounds=rounds, timeout=secs(job.timeout_sec),
                       bound=secs(sec))
    return rounds, sec


def _dirs(roots):
    for d in (roots.state, os.path.join(roots.state, FOLDER)):
        os.makedirs(d, mode=0o700, exist_ok=True)
        os.chmod(d, 0o700)


def make(roots, fid):
    """The run's folder, made by an exclusive mkdir; one already there is a used id."""
    path = folder(roots, fid)
    _dirs(roots)
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        raise RunError("id.used", id=fid, day=time.strftime("%Y-%m-%d", time.gmtime()))
    os.chmod(path, 0o700)
    return path


def write(roots, fid, name, obj):
    """One file of the run's folder, 0600, by one rename; `run.record` when it cannot be."""
    path = folder(roots, fid)
    target = os.path.join(path, name)
    try:
        if not os.path.isdir(path):
            _dirs(roots)
            os.makedirs(path, mode=0o700, exist_ok=True)
        tmp = os.path.join(path, "." + name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, json.dumps(obj, sort_keys=True).encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, target)
    except OSError as e:
        raise RunError("run.record", id=fid, path=target, why=e.strerror or type(e).__name__)
    return target


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def read(roots, fid):
    """{id, folder, start, end, log} of a run, or None where it has no folder."""
    path = folder(roots, fid)
    if not os.path.isdir(path):
        return None
    log = os.path.join(path, "log.txt")
    return {"id": fid, "folder": path, "start": _read(os.path.join(path, "start.json")),
            "end": _read(os.path.join(path, "fanout.json")),
            "log": log if os.path.exists(log) else None}


def every(roots):
    base = os.path.join(roots.state, FOLDER)
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    found = []
    for name in names:
        if _job.ID_RE.match(name):
            run = read(roots, name)
            if run is not None:
                found.append(run)
    return found


def state(run, alive):
    if run["end"]:
        return "ended"
    start = run["start"]
    if not start:
        return "starting"
    return "running" if alive(start.get("pid"), start.get("pid_started")) else "lost"


def usage(roots, fid):
    """The day's log's lines for this fan-out, any day, read leniently."""
    found = []
    try:
        with open(os.path.join(roots.state, "usage.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict) and obj.get("fanout") == fid:
                    found.append(obj)
    except OSError:
        pass
    return found


def _session(run):
    return (run["start"] or {}).get("session") or (run["end"] or {}).get("session")


def _live(roots, run):
    from apilane import report
    session = _session(run)
    if not isinstance(session, str) or not report.SESSION.match(session):
        return {}
    return _read(os.path.join(roots.state, "live", session, run["id"] + ".json")) or {}


def _money(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def row(roots, run, alive):
    """A run's status row (R4)."""
    from apilane import report
    st = state(run, alive)
    start, end = run["start"] or {}, run["end"] or {}
    live = {} if st == "ended" else _live(roots, run)
    shards = report._running(roots, live, alive) if live else []
    if end:
        done = [s for s in end.get("shards") or [] if isinstance(s, dict)]
        ok = sum(1 for s in done if s.get("state") == "ok")
        failed, spent = len(done) - ok, _money(end.get("spent_usd"))
    else:
        ok, failed = report._count(live.get("ok")), report._count(live.get("failed"))
        spent = _money(live.get("spent_usd"))
    return {"id": run["id"], "state": st, "tag": start.get("tag", end.get("tag")),
            "session": _session(run), "pid": start.get("pid"), "started": start.get("at"),
            "ended": end.get("ended"), "rc": end.get("rc"),
            "budget_usd": _money(start.get("budget_usd", end.get("budget_usd"))),
            "spent_usd": spent,
            "queued": report._count(live.get("queued")) if st == "running" else 0,
            "running": [{"run": r, "type": t} for r, t, _j in shards],
            "shards_ok": ok, "shards_failed": failed}


def by_type(rows):
    counts = {}
    for r in rows:
        for item in r["running"]:
            counts[item["type"]] = counts.get(item["type"], 0) + 1
    return counts


def _newest(run):
    start, end = run["start"] or {}, run["end"] or {}
    return str(start.get("at") or end.get("ended") or "")


def resolve(roots, word, session, alive, verb):
    """The run an ID names, or with none this session's one live run, else its newest ended."""
    if word is not None:
        run = read(roots, check(word))
        if run is None:
            raise RunError("run.unknown", id=word)
        return run
    mine = [r for r in every(roots) if _session(r) == session]
    live = [r for r in mine if state(r, alive) == "running"]
    if len(live) > 1:
        raise RunError("run.two", ids=", ".join(r["id"] for r in live))
    if live:
        return live[0]
    rest = [r for r in mine if state(r, alive) in ("ended", "lost")]
    if verb == "stop" or not rest:
        raise RunError("run.none")
    return max(rest, key=_newest)


def status(roots, word, *, every_run=False, session, alive=None):
    alive = _alive(alive)
    if word is not None:
        runs = [resolve(roots, word, session, alive, "status")]
    elif every_run:
        runs = every(roots)
    else:
        runs = [r for r in every(roots) if _session(r) == session]
    return [row(roots, r, alive) for r in runs]


def wait(roots, word, *, session, timeout=WAIT_SEC, alive=None, clock=time.monotonic,
         sleep=time.sleep):
    """{kind, run, row}: kind `ended`, `lost` (no settle), `gone` (a settle, no record) or
    `running` (past the timeout). It writes, signals and removes nothing."""
    alive = _alive(alive)
    run = resolve(roots, word, session, alive, "wait")
    fid = run["id"]
    deadline = clock() + timeout
    while True:
        run = read(roots, fid) or run
        if run["end"]:
            return {"kind": "ended", "run": run, "row": row(roots, run, alive)}
        start = run["start"]
        if start and not alive(start.get("pid"), start.get("pid_started")):
            run = read(roots, fid) or run
            if run["end"]:
                return {"kind": "ended", "run": run, "row": row(roots, run, alive)}
            settles = [l for l in usage(roots, fid) if l.get("kind") == "settle"]
            out = {"kind": "gone" if settles else "lost", "run": run, "row": row(roots, run, alive)}
            if settles:
                out["spent_usd"] = _money(settles[-1].get("spent_usd"))
            return out
        if clock() >= deadline:
            return {"kind": "running", "run": run, "row": row(roots, run, alive)}
        sleep(max(0.0, min(0.2, deadline - clock())))


def end_groups(roots, fid, alive, *, killpg=os.killpg, sleep=time.sleep, clock=time.monotonic):
    """End the process group of each run of this fan-out that reads running and lives with its
    start time: SIGTERM, then SIGKILL after 2 s. Returns how many there were."""
    base = os.path.join(roots.state, "runs")
    try:
        names = sorted(os.listdir(base))
    except OSError:
        names = []
    found = []
    for name in names:
        if not name.startswith(fid + "-") or not _job.ID_RE.match(name):
            continue
        rec = _read(os.path.join(base, name, "run.json")) or {}
        if rec.get("fanout") != fid or rec.get("state") != "running":
            continue
        if isinstance(rec.get("pid"), int) and alive(rec.get("pid"), rec.get("pid_started")):
            found.append(rec)
    for rec in found:
        try:
            killpg(rec["pid"], signal.SIGTERM)
        except OSError:
            pass
    deadline = clock() + KILL_SEC
    while found and clock() < deadline and any(
            alive(r["pid"], r.get("pid_started")) for r in found):
        sleep(0.05)
    for rec in found:
        if alive(rec["pid"], rec.get("pid_started")):
            try:
                killpg(rec["pid"], signal.SIGKILL)
            except OSError:
                pass
    return len(found)


def stop(roots, word, *, session, alive=None, kill=os.kill, killpg=os.killpg, wait_sec=STOP_SEC,
         clock=time.monotonic, sleep=time.sleep):
    """{kind, run, ...}: SIGTERM then SIGCONT to a live run, then as `wait` for 10 s; `deaf` when
    it still runs then, its shards' groups ended; `orphans` when its process was gone. It
    appends nothing to the day's log."""
    alive = _alive(alive)
    run = resolve(roots, word, session, alive, "stop")
    fid = run["id"]
    if run["end"]:
        return {"kind": "ended", "run": run, "row": row(roots, run, alive), "sent": None}
    start = run["start"]
    if not start:
        raise RunError("run.starting", id=fid)
    pid, at = start.get("pid"), start.get("pid_started")
    if isinstance(pid, int) and alive(pid, at):
        for sig in (signal.SIGTERM, signal.SIGCONT):
            try:
                kill(pid, sig)
            except OSError:
                pass
        out = wait(roots, fid, session=session, timeout=wait_sec, alive=alive, clock=clock,
                   sleep=sleep)
        out["sent"] = pid
        if out["kind"] == "running":
            out["kind"] = "deaf"
            out["groups"] = end_groups(roots, fid, alive, killpg=killpg, sleep=sleep, clock=clock)
        return out
    n = end_groups(roots, fid, alive, killpg=killpg, sleep=sleep, clock=clock)
    return {"kind": "orphans", "run": run, "row": row(roots, run, alive), "sent": None,
            "groups": n}


def _age(path, now):
    newest = None
    try:
        newest = os.stat(path).st_mtime
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    t = os.stat(os.path.join(root, f)).st_mtime
                except OSError:
                    continue
                newest = t if newest is None else max(newest, t)
    except OSError:
        return 0.0
    return now - newest


def sweep(roots, *, alive=None, now=None):
    """Prune, once at a fan-out's start; it never raises (R9)."""
    try:
        _sweep(roots, _alive(alive), time.time() if now is None else now)
    except Exception:   # noqa: BLE001 -- a prune never stops a fan-out
        pass


def _sweep(roots, alive, now):
    from apilane import report
    for kind, name in ((FOLDER, "start.json"), ("runs", "run.json")):
        base = os.path.join(roots.state, kind)
        try:
            names = os.listdir(base)
        except OSError:
            continue
        for n in names:
            path = os.path.join(base, n)
            if n.startswith(".") or not os.path.isdir(path) or os.path.islink(path):
                continue
            rec = _read(os.path.join(path, name)) or {}
            if _age(path, now) > WEEK and not alive(rec.get("pid"), rec.get("pid_started")):
                shutil.rmtree(path, True)
    base = os.path.join(roots.state, "live")
    try:
        sessions = os.listdir(base)
    except OSError:
        return
    for s in sessions:
        d = os.path.join(base, s)
        if os.path.islink(d) or not os.path.isdir(d):
            continue
        for path, rec in report._records(d):
            if rec.get("ended"):
                at = report._epoch(rec.get("ended"))
                if at is not None and now - at > DAY:
                    _unlink(path)
                continue
            if alive(rec.get("pid"), rec.get("pid_started")):
                continue
            if report._running(roots, rec, alive):
                continue
            beat = report._epoch(rec.get("beat"))
            if _age(path, now) > DAY and (beat is None or now - beat > DAY):
                _unlink(path)
        try:
            os.rmdir(d)
        except OSError:
            pass


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass
