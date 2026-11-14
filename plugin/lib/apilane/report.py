"""The API lane's report (design/21 items 18 to 21): one line for a session, and the status rows.

Reads `live/<session>/<fanout>.json` and `runs/<run>/run.json` under `roots.state`. A run counts
while its pid lives with its recorded start time (`alive`, al1's `proc.alive`); a fan-out whose
pid no longer matches and that left no close is lost. Every copy of the line is drawn here.
"""
import calendar
import json
import os
import re
import time

SESSION = re.compile(r"[A-Za-z0-9-]{1,128}\Z")
DAY = 86400
# the status tool's FIELDS, in its order: a row here carries exactly these keys
FIELDS = ("id", "session_id", "agent_id", "parent", "lane", "model", "started", "elapsed_s",
          "turns", "context", "window", "cost_usd", "last_tool", "last_tool_at", "state", "what")


def _alive(alive):
    if alive is None:
        from apilane import proc
        alive = proc.alive
    return alive


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _records(folder):
    """[(path, record)] of a session's live folder, by name; a dot file is never a record."""
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith(".json") and not n.startswith("."))
    except OSError:
        return []
    found = []
    for name in names:
        rec = _read(os.path.join(folder, name))
        if rec is not None:
            found.append((os.path.join(folder, name), rec))
    return found


def _epoch(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
            try:
                return float(calendar.timegm(time.strptime(v, fmt)))
            except ValueError:
                continue
    return None


def _usd(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def _count(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def _run(roots, run):
    if not isinstance(run, str) or "/" in run or run.startswith("."):
        return None
    return _read(os.path.join(roots.state, "runs", run, "run.json"))


def _running(roots, rec, alive):
    """[(run id, type, run.json)] of the record's runs whose process lives."""
    found = []
    for item in rec.get("running") or []:
        if not isinstance(item, dict):
            continue
        run = _run(roots, item.get("run"))
        if run and alive(run.get("pid"), run.get("pid_started")):
            found.append((item.get("run"), item.get("type") or run.get("type") or "?", run))
    return found


def _types(names):
    counts = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(names) == 1:
        return order[0][0]
    return ", ".join("%d %s" % (c, n) for n, c in order)


def _money(v):
    return "$%.2f" % v


def line(session, roots, *, consume=False, alive=None, now=None):
    """The session's line, or None. A live line first; then each ended or lost record once, each
    its own line. With `consume`, each ended or lost record reported is removed, and an ended
    record older than a day is removed unreported."""
    if not isinstance(session, str) or not SESSION.match(session):
        return None
    now = time.time() if now is None else now
    live, closed = [], []
    for path, rec in _records(os.path.join(roots.state, "live", session)):
        ended = rec.get("ended")
        if ended:
            at = _epoch(ended)
            if at is not None and now - at > DAY:
                if consume:
                    _remove(path)
                continue
            closed.append((path, rec, "ended"))
            continue
        alive = _alive(alive)
        if alive(rec.get("pid"), rec.get("pid_started")):
            live.append(rec)
        else:
            closed.append((path, rec, "lost"))
    out = []
    if live:
        names = [t for rec in live for _r, t, _j in _running(roots, rec, alive)]
        n = len(names)
        text = "api lane: %d agent%s running" % (n, "" if n == 1 else "s")
        if n:
            text += " (%s)" % _types(names)
        queued = sum(_count(rec.get("queued")) for rec in live)
        if queued:
            text += ", %d queued" % queued
        text += ", %s of %s spent" % (_money(sum(_usd(r.get("spent_usd")) for r in live)),
                                      _money(sum(_usd(r.get("budget_usd")) for r in live)))
        if len(live) > 1:
            text += " in %d fan-outs" % len(live)
        out.append(text)
    head = "api lane: " if live else "api lane: 0 agents running; "
    for path, rec, kind in sorted(closed, key=lambda c: str(c[1].get("fanout"))):
        name = rec.get("fanout") or os.path.basename(path)[:-len(".json")]
        if kind == "ended":
            out.append("%sfan-out %s ended: %d ok, %d failed, %s of %s spent" % (
                head, name, _count(rec.get("ok")), _count(rec.get("failed")),
                _money(_usd(rec.get("spent_usd"))), _money(_usd(rec.get("budget_usd")))))
        else:
            out.append("%sfan-out %s stopped without a close: its whole %s counts against today"
                       % (head, name, _money(_usd(rec.get("budget_usd")))))
        if consume:
            _remove(path)
    return "\n".join(out) if out else None


def _remove(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def rows(roots, *, alive=None, now=None):
    """One dict a live shard, in the status tool's FIELDS: lane `api`, parent and session_id the
    session, id the run, what `api <type>: <label>`, state `running`, or `orphan` when its
    fan-out is gone."""
    now = time.time() if now is None else now
    base = os.path.join(roots.state, "live")
    try:
        sessions = sorted(os.listdir(base))
    except OSError:
        return []
    found = []
    for session in sessions:
        if not SESSION.match(session):
            continue
        for _path, rec in _records(os.path.join(base, session)):
            alive = _alive(alive)
            gone = not alive(rec.get("pid"), rec.get("pid_started"))
            sid = None if session == "none" else session
            for run_id, kind, run in _running(roots, rec, alive):
                started = _epoch(run.get("started"))
                r = dict.fromkeys(FIELDS)
                r.update(id=run_id, session_id=sid, parent=sid, lane="api", model=run.get("model"),
                         started=run.get("started") if started is not None else None,
                         elapsed_s=int(now - started) if started is not None else None,
                         state="orphan" if gone else "running",
                         what="api %s: %s" % (kind, run.get("label") or ""))
                found.append(r)
    return found
