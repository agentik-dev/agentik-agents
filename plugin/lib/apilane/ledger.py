"""The day's log: `<state>/usage.jsonl`, appended under a flock on `usage.lock`.

design/21 items 6, 18 and 24, R1-F1. A fan-out reserves its whole budget here,
synced, before its first shard starts; its end appends a settle. The day's sum
is, for each reservation of the UTC day, its settle's `spent_usd`, else its
whole `budget_usd`. Nothing releases a reservation: a fan-out that dies has
already counted, and goes on counting whole for its day. A line that cannot be
read is `log.fault`, never an empty day.
"""
import contextlib
import fcntl
import json
import math
import os
from datetime import datetime, timedelta, timezone

SCHEMA = "agentik.api.usage/1"
LOG = "usage.jsonl"
LOCK = "usage.lock"
KEEP_DAYS = 7
# The keys each kind of line holds (seams section 8), and the money among them.
KINDS = {
    "reserve": ("fanout", "day", "at", "budget_usd", "pid", "pid_started", "session"),
    "shard": ("fanout", "run", "type", "model", "state", "cost_usd", "estimated", "at"),
    "settle": ("fanout", "day", "at", "spent_usd"),
}
MONEY = ("budget_usd", "cost_usd", "spent_usd")


class LedgerError(Exception):
    def __init__(self, code, **fields):
        Exception.__init__(self, code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


def utcnow(now=None):
    """`now` is a datetime, a function that returns one, or None."""
    if callable(now):
        now = now()
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _path(roots, name):
    return os.path.join(roots.state, name)


def _good(obj):
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        return False
    keys = KINDS.get(obj.get("kind"))
    if keys is None or any(k not in obj for k in keys):
        return False
    for k in MONEY:
        if k in obj:
            v = obj[k]
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                return False
            try:
                if not math.isfinite(v):
                    return False
            except OverflowError:   # an int too large for a float (review 1, R1-F4)
                return False
            if v < 0:   # the day's sum never falls (review 1, N3)
                return False
    for k in ("fanout", "day", "at"):
        if k in obj and not isinstance(obj[k], str):
            return False
    return True


def _read(roots):
    path = _path(roots, LOG)
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return []
    except OSError:
        raise LedgerError("log.fault", path=path, line=0)
    lines = []
    for n, text in enumerate(raw.split(b"\n"), start=1):
        if not text.strip():
            continue
        try:
            obj = json.loads(text.decode("utf-8"))
        except ValueError:
            obj = None
        if not _good(obj):
            raise LedgerError("log.fault", path=path, line=n)
        lines.append(obj)
    if raw and not raw.endswith(b"\n"):
        raise LedgerError("log.fault", path=path, line=raw.count(b"\n") + 1)
    return lines


def _sum(lines, day):
    settles = {}
    for x in lines:
        if x["kind"] == "settle":
            settles[x["fanout"]] = x["spent_usd"]
    total = settled = held = 0.0
    unsettled = []
    for x in lines:
        if x["kind"] != "reserve" or x["day"] != day:
            continue
        if x["fanout"] in settles:
            settled += settles[x["fanout"]]
        else:
            held += x["budget_usd"]
            unsettled.append({k: x[k] for k in
                              ("fanout", "budget_usd", "at", "pid", "pid_started")})
    total = settled + held
    return round(total, 6), round(settled, 6), round(held, 6), unsettled


def _mkdir(roots):
    os.makedirs(roots.state, mode=0o700, exist_ok=True)
    os.chmod(roots.state, 0o700)


@contextlib.contextmanager
def _locked(roots, create=True):
    """The log's lock, exclusive. With create false it is shared, and taken
    only where the lock file already exists, so a reader makes nothing."""
    path = _path(roots, LOCK)
    if create:
        _mkdir(roots)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(fd, 0o600)
        mode = fcntl.LOCK_EX
    else:
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            yield
            return
        mode = fcntl.LOCK_SH
    try:
        fcntl.flock(fd, mode)
        yield
    finally:
        os.close(fd)


def _append(roots, obj):
    data = (json.dumps(obj, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(_path(roots, LOG), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _prune(roots, lines, dt):
    """Drop lines older than KEEP_DAYS, by one rename. Returns what is kept."""
    cutoff = (dt - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    kept = [x for x in lines if x["at"][:10] >= cutoff]
    if len(kept) == len(lines):
        return lines
    tmp = _path(roots, LOG + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, "".join(json.dumps(x, sort_keys=True) + "\n"
                             for x in kept).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, _path(roots, LOG))
    return kept


def reserve(roots, *, fanout, budget_usd, max_day_usd, session, pid, pid_started,
            now=None):
    """Under the lock: refuse `id.used` or `budget.day`, else append the
    reservation and sync it to disk before returning."""
    dt = utcnow(now)
    day = dt.strftime("%Y-%m-%d")
    with _locked(roots):
        lines = _read(roots)
        for x in lines:
            if x["kind"] == "reserve" and x["fanout"] == fanout:
                raise LedgerError("id.used", id=fanout, day=x["day"])
        total = _sum(lines, day)[0]
        if budget_usd + total > max_day_usd + 1e-9:
            raise LedgerError("budget.day", budget_usd=budget_usd,
                              day_sum_usd=total, max_day_usd=max_day_usd)
        _prune(roots, lines, dt)
        _append(roots, {"schema": SCHEMA, "kind": "reserve", "fanout": fanout,
                        "day": day, "at": stamp(dt),
                        "budget_usd": round(float(budget_usd), 6), "pid": pid,
                        "pid_started": pid_started, "session": session})


def book(roots, *, fanout, run, type, model, state, cost_usd, estimated, now=None):
    """One shard's cost, appended under the lock."""
    dt = utcnow(now)
    with _locked(roots):
        _append(roots, {"schema": SCHEMA, "kind": "shard", "fanout": fanout,
                        "run": run, "type": type, "model": model, "state": state,
                        "cost_usd": round(float(cost_usd), 6),
                        "estimated": bool(estimated), "at": stamp(dt)})


def settle(roots, *, fanout, spent_usd, now=None):
    """A fan-out's end: what it spent, on its reservation's day."""
    dt = utcnow(now)
    day = dt.strftime("%Y-%m-%d")
    with _locked(roots):
        try:
            with open(_path(roots, LOG)) as f:
                raw = f.read().splitlines()
        except OSError:
            raw = []
        for text in raw:
            try:
                x = json.loads(text)
            except ValueError:
                continue
            if (isinstance(x, dict) and x.get("kind") == "reserve"
                    and x.get("fanout") == fanout and isinstance(x.get("day"), str)):
                day = x["day"]
        _append(roots, {"schema": SCHEMA, "kind": "settle", "fanout": fanout,
                        "day": day, "at": stamp(dt),
                        "spent_usd": round(float(spent_usd), 6)})


def day(roots, *, now=None):
    """The day's sum and its unsettled reservations. Writes nothing."""
    today = utcnow(now).strftime("%Y-%m-%d")
    with _locked(roots, create=False):
        lines = _read(roots)
    total, settled, held, unsettled = _sum(lines, today)
    return {"day": today, "sum_usd": total, "settled_usd": settled,
            "held_usd": held, "unsettled": unsettled}
