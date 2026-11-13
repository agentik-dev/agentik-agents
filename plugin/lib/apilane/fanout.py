"""The fan-out: its plan (the dry run) and its run, in one order, always.

design/21 items 18, 20, 24 to 26. The order: the plan (the job, both
ceilings, the dirs), the probe, the key, the reservation, synced, and only
then the first shard. A fan-out that dies after its reservation has already
counted whole for its day; a stop's handler only makes the figure smaller.
Nothing here prints: it calls the `emit` it was handed, returns a value, or
raises an error with a `code` (seams section 2). Another row's function is a
keyword argument whose default, None, imports the real one inside the call.
"""
import collections
import json
import math
import os
import re
import signal
import threading
import time

from apilane import ledger
from apilane import pool as pools

LIVE_SCHEMA = "agentik.api.live/1"
BEAT_SEC = 10
STOP_GRACE_SEC = 2
SESSION_RE = re.compile(r"^[A-Za-z0-9-]{1,128}$")
STOP_SIGNALS = ("SIGINT", "SIGTERM", "SIGHUP")

FanoutResult = collections.namedtuple("FanoutResult", "id rc spent_usd budget_usd shards")
ShardResult = collections.namedtuple(
    "ShardResult", "label type state cost_usd estimated result_path reason model")


class FanoutError(Exception):
    def __init__(self, code, **fields):
        Exception.__init__(self, code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


def _quiet(*_a, **_k):
    return None


def session_name(session):
    """The session as the records name it: the id when it is at most 128
    letters, digits and dashes, else `none`."""
    if isinstance(session, str) and SESSION_RE.match(session):
        return session
    return "none"


def plan(job, *, lane, roots, models=None, check_dirs=None, now=None):
    """The dry run: refuse in R6's order, or return what would run. It starts
    nothing, opens no key, runs no probe, writes no file and makes no folder."""
    if lane.enabled is not True:
        raise FanoutError("lane.off", config=roots.config)
    # Cut on the owner's recommended answer, not yet given; one line that can leave.
    if lane.console_limit_usd is None:
        raise FanoutError("limit.unstated", config=roots.config)
    if check_dirs is None:
        from apilane import wall
        check_dirs = wall.check_dirs
    dirs = list(check_dirs(list(job.dirs), home=roots.home))
    if job.budget_usd > lane.max_fanout_usd + 1e-9:
        raise FanoutError("budget.fanout", budget_usd=job.budget_usd,
                          max_fanout_usd=lane.max_fanout_usd)
    day_sum = ledger.day(roots, now=now)["sum_usd"]
    if job.budget_usd + day_sum > lane.max_day_usd + 1e-9:
        raise FanoutError("budget.day", budget_usd=job.budget_usd,
                          day_sum_usd=day_sum, max_day_usd=lane.max_day_usd)
    if models is None:
        from apilane import types as _types
        models = {name: t.model for name, t in _types.TYPES.items()}
    worst = pools.BudgetPool(job.budget_usd)
    asked = pools.want(job.max_shard_usd, job.budget_usd, len(job.shards))
    shards = []
    for s in job.shards:
        grant = worst.reserve(asked)
        worst.settle(grant, grant)
        shards.append({"label": s.label, "type": s.type, "model": models.get(s.type),
                       "grant_usd": round(grant, 6),
                       "ceiling_usd": round(grant / pools.OVERSHOOT, 6)})
    return {"id": job.id, "budget_usd": job.budget_usd, "day_sum_usd": day_sum,
            "worst_usd": round(worst.settled, 6), "dirs": dirs, "shards": shards}


class _Slot(object):
    def __init__(self, number, shard, run, model):
        self.number = number
        self.shard = shard
        self.run = run
        self.model = model
        self.grant = 0.0
        self.state = "queued"   # queued, running, done
        self.booked = False
        self.result = None
        self.signalled = None


class _Run(object):
    def __init__(self, job, lane, roots, session, emit, now, started, pid_started):
        self.job = job
        self.lane = lane
        self.roots = roots
        self.session = session
        self.emit = emit
        self.now = now
        self.started = started
        self.pid = os.getpid()
        self.pid_started = pid_started
        self.pool = pools.BudgetPool(job.budget_usd)
        self.cond = threading.Condition()
        self.stop = threading.Event()
        self.signame = None
        self.closed = False
        self.last_write = 0.0
        folder = os.path.join(roots.state, "live", session)
        self.live = os.path.join(folder, job.id + ".json")

    # -- the live record --------------------------------------------------
    def _record(self, ended=None):
        slots = self.slots
        return {"schema": LIVE_SCHEMA, "fanout": self.job.id, "pid": self.pid,
                "pid_started": self.pid_started, "session": self.session,
                "budget_usd": self.job.budget_usd,
                "spent_usd": round(self.pool.settled, 6),
                "queued": sum(1 for s in slots if s.state == "queued"),
                "running": [{"run": s.run, "type": s.shard.type}
                            for s in slots if s.state == "running"],
                "ok": sum(1 for s in slots if s.state == "done"
                          and s.result.state == "ok"),
                "failed": sum(1 for s in slots if s.state == "done"
                              and s.result.state != "ok"),
                "beat": ledger.stamp(ledger.utcnow()), "ended": ended}

    def write_live(self, ended=None):
        """One rename; the caller holds self.cond."""
        if self.closed:
            return
        folder = os.path.dirname(self.live)
        for d in (os.path.dirname(folder), folder):
            os.makedirs(d, mode=0o700, exist_ok=True)
            os.chmod(d, 0o700)
        tmp = os.path.join(folder, "." + self.job.id + ".json.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, json.dumps(self._record(ended), sort_keys=True).encode())
        finally:
            os.close(fd)
        os.replace(tmp, self.live)
        self.last_write = time.time()

    def close_live(self):
        with self.cond:
            if self.session != "none":
                self.write_live(ended=ledger.stamp(ledger.utcnow()))
            else:
                try:
                    os.unlink(self.live)
                except FileNotFoundError:
                    pass
            self.closed = True

    # -- booking ----------------------------------------------------------
    def _book(self, slot, result):
        r = result
        try:
            ledger.book(self.roots, fanout=self.job.id, run=slot.run, type=r.type,
                        model=r.model, state=r.state, cost_usd=r.cost_usd,
                        estimated=r.estimated, now=self.now)
        except Exception:
            pass  # the reservation already counts this shard whole
        self.pool.settle(slot.grant, r.cost_usd)

    def _end(self, slot, result):
        with self.cond:
            slot.result = result
            slot.state = "done"
            self.write_live()
            self.cond.notify_all()
        self.emit("shard.end", run=slot.run, **result._asdict())

    def finish(self, slot, raw, error):
        """A shard's own end, on its worker thread."""
        with self.cond:
            if slot.booked:     # a stop booked it at its grant already
                slot.state = "done" if slot.result else slot.state
                self.cond.notify_all()
                return
            slot.booked = True
        cost = getattr(raw, "cost_usd", None)
        estimated = bool(getattr(raw, "estimated", False))
        if (not isinstance(cost, (int, float)) or isinstance(cost, bool)
                or not math.isfinite(cost) or cost < 0):
            cost, estimated = slot.grant, True
        state = getattr(raw, "state", None) or "failed"
        reason = getattr(raw, "reason", None)
        if error is not None:
            state, reason = "failed", "error:%s" % getattr(error, "code", type(error).__name__)
        result = ShardResult(slot.shard.label, slot.shard.type, state, cost, estimated,
                             getattr(raw, "result_path", None), reason,
                             getattr(raw, "model", None) or slot.model)
        self._book(slot, result)
        self._end(slot, result)

    # -- a stop -----------------------------------------------------------
    def _group(self, slot):
        try:
            with open(os.path.join(self.roots.state, "runs", slot.run, "run.json")) as f:
                rec = json.load(f)
        except (OSError, ValueError):
            return None
        pid = rec.get("pid") if isinstance(rec, dict) else None
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1:
            return None
        known = rec.get("pid_started")
        if known and self.started is not None and self.started(pid) != known:
            return None
        return pid

    @staticmethod
    def _alive(group):
        try:
            os.killpg(group, 0)
            return True
        except OSError:
            return False

    def stop_all(self):
        """TERM each running shard's group, KILL it 2 s later, book each at
        its grant, estimated. No new shard starts once this is called."""
        with self.cond:
            running = [s for s in self.slots if s.state == "running" and not s.booked]
            for s in running:
                s.booked = True
        reason = "signal:%s" % (self.signame or "stop")
        end = time.time() + STOP_GRACE_SEC
        while True:
            for s in running:
                if s.signalled is None:
                    group = self._group(s)
                    if group is not None:
                        s.signalled = group
                        try:
                            os.killpg(group, signal.SIGTERM)
                        except OSError:
                            pass
            if time.time() >= end or not any(
                    s.signalled is None or self._alive(s.signalled) for s in running):
                break
            time.sleep(0.05)
        for s in running:
            if s.signalled is not None and self._alive(s.signalled):
                try:
                    os.killpg(s.signalled, signal.SIGKILL)
                except OSError:
                    pass
        for s in running:
            result = ShardResult(s.shard.label, s.shard.type, "failed", s.grant, True,
                                 None, reason, s.model)
            self._book(s, result)
            self._end(s, result)

    # -- the loop ---------------------------------------------------------
    def wait(self, ready):
        """Wait until ready() or a stop; beat at least every BEAT_SEC."""
        while True:
            with self.cond:
                if self.stop.is_set() or ready():
                    return
                if time.time() - self.last_write >= BEAT_SEC:
                    self.write_live()
                    beat = True
                else:
                    beat = False
                self.cond.wait(min(0.2, BEAT_SEC))
            if beat:
                self.emit("beat")

    def go(self, slots, run_shard, kwargs):
        self.slots = slots
        job = self.job
        asked = pools.want(job.max_shard_usd, job.budget_usd, len(slots))
        with self.cond:
            self.write_live()
        for slot in slots:
            self.wait(lambda: sum(1 for s in slots if s.state == "running") < job.jobs)
            if self.stop.is_set():
                break
            free = self.pool.available
            grant = self.pool.reserve(asked)
            if not grant:
                result = ShardResult(slot.shard.label, slot.shard.type, "skipped", 0.0,
                                     False, None, pools.skip_reason(asked, free),
                                     slot.model)
                slot.booked = True
                self._end(slot, result)
                continue
            slot.grant = grant
            with self.cond:
                slot.state = "running"
                self.write_live()
            self.emit("shard.start", run=slot.run, type=slot.shard.type,
                      label=slot.shard.label)
            t = threading.Thread(target=self._work, args=(slot, run_shard, kwargs),
                                 name="shard-" + slot.run)
            t.daemon = True
            t.start()
        self.wait(lambda: not any(s.state == "running" for s in slots))
        if self.stop.is_set():
            self.stop_all()
            with self.cond:     # a shard whose own end raced the stop books itself
                self.cond.wait_for(lambda: all(s.result for s in slots
                                               if s.state != "queued"),
                                   timeout=STOP_GRACE_SEC)
            for slot in slots:
                if slot.state != "queued" and slot.result is None:
                    slot.result = ShardResult(slot.shard.label, slot.shard.type,
                                              "failed", slot.grant, True, None,
                                              "signal:%s" % self.signame, slot.model)
            for slot in slots:
                if slot.state == "queued":
                    slot.booked = True
                    self._end(slot, ShardResult(slot.shard.label, slot.shard.type,
                                                "skipped", 0.0, False, None,
                                                "stopped", slot.model))

    def _work(self, slot, run_shard, kwargs):
        raw = error = None
        try:
            raw = run_shard(slot.shard, grant_usd=slot.grant, fanout=self.job.id,
                            number=slot.number, **kwargs)
        except Exception as e:  # a shard that raises is a failed shard
            error = e
        self.finish(slot, raw, error)

    def on_signal(self, signum, _frame):
        try:
            self.signame = signal.Signals(signum).name
        except ValueError:
            self.signame = str(signum)
        self.stop.set()
        with self.cond:
            self.cond.notify_all()


def run(job, *, lane, roots, session, claude, run_shard=None, wrap=None, key=None,
        ensure_probe=None, started=None, emit=None, now=None, check_dirs=None,
        models=None):
    """Plan, probe, key, reserve, then the shards; settle at the end."""
    emit = emit or _quiet
    session = session_name(session)
    p = plan(job, lane=lane, roots=roots, models=models, check_dirs=check_dirs, now=now)
    emit("plan", plan=p)
    if wrap is None:
        from apilane import wall
        wrap = wall.wrap
    if ensure_probe is None:
        from apilane import probe

        def ensure_probe(c):
            return probe.ensure(claude=c, roots=roots, wrap=wrap, emit=emit)
    record = ensure_probe(claude) or {}
    restricted = record.get("restricted") is not None
    if key is None:
        from apilane import key as _key

        def key():
            return _key.load(roots)
    value = key()
    if started is None:
        from apilane import proc
        started = proc.started
    if run_shard is None:
        from apilane import run as _run
        run_shard = _run.run_shard
    pid_started = started(os.getpid())
    ledger.reserve(roots, fanout=job.id, budget_usd=job.budget_usd,
                   max_day_usd=lane.max_day_usd, session=session, pid=os.getpid(),
                   pid_started=pid_started, now=now)
    emit("reserved", fanout=job.id, budget_usd=job.budget_usd,
         day_sum_usd=ledger.day(roots, now=now)["sum_usd"])

    state = _Run(job, lane, roots, session, emit, now, started, pid_started)
    slots = [_Slot(n, s, "%s-%02d" % (job.id, n), p["shards"][n - 1]["model"])
             for n, s in enumerate(job.shards, start=1)]
    kwargs = dict(session=session, roots=roots, lane=lane, claude=claude,
                  dirs=p["dirs"], timeout_sec=job.timeout_sec, restricted=restricted,
                  wrap=wrap, key=lambda: value)
    previous = {}
    if threading.current_thread() is threading.main_thread():
        for name in STOP_SIGNALS:
            sig = getattr(signal, name)
            previous[sig] = signal.signal(sig, state.on_signal)
    try:
        state.go(slots, run_shard, kwargs)
        spent = round(state.pool.settled, 6)
        ledger.settle(roots, fanout=job.id, spent_usd=spent, now=now)
        state.close_live()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    shards = [s.result for s in slots]
    ok = sum(1 for r in shards if r.state == "ok")
    emit("done", fanout=job.id, ok=ok, failed=len(shards) - ok, spent_usd=spent,
         budget_usd=job.budget_usd)
    return FanoutResult(job.id, 0 if ok == len(shards) else 1, spent,
                        job.budget_usd, shards)
