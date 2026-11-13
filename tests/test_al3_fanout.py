#!/usr/bin/python3
"""Row al3's suite: the job, the pool, the day's log and the fan-out.

    python3 tests/test_al3_fanout.py [Class]

Every test hands in a temp roots, a stand-in run_shard, wrap, key,
ensure_probe, started and check_dirs, and a list that collects emit. No test
starts claude, real or fake; a signal goes only to a child this suite started.
The pool cases are ported from the old fan-out's suite (d8ca583).
"""
import collections
import io
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types as pytypes
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "plugin", "lib")
sys.path.insert(0, LIB)

from apilane import job as J  # noqa: E402
from apilane import pool as P  # noqa: E402
from apilane import ledger as L  # noqa: E402
from apilane import fanout as F  # noqa: E402

TYPES = {"review", "explore", "analyze"}
MODELS = {"review": "model-r", "explore": "model-e", "analyze": "model-a"}
FAKE_KEY = "made-up-value-not-a-key"
ShardResult = collections.namedtuple(
    "ShardResult",
    "label type state cost_usd estimated result_path reason model")


class StandInError(Exception):
    def __init__(self, code, **fields):
        Exception.__init__(self, code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


def make_roots(tmp):
    home = os.path.join(tmp, "home")
    os.makedirs(home, exist_ok=True)
    return pytypes.SimpleNamespace(
        home=home,
        config=os.path.join(home, ".config/agentik/agents/config.yaml"),
        state=os.path.join(home, ".local/state/agentik-agents/api"),
        store=os.path.join(home, ".config/agentik/agents/secrets/k.sops.yaml"))


def make_lane(**kw):
    base = dict(enabled=True, max_fanout_usd=2.0, max_day_usd=10.0,
                console_limit_usd=5.0, proxy=None, ca_file=None)
    base.update(kw)
    return pytypes.SimpleNamespace(**base)


def make_job(budget=1.0, shards=(("a", "review", "p"),), **kw):
    base = dict(id="t1", budget_usd=float(budget), dirs=(),
                shards=tuple(J.Shard(*s) for s in shards),
                max_shard_usd=None, jobs=4, timeout_sec=900)
    base.update(kw)
    return J.Job(**base)


def log_lines(roots):
    path = os.path.join(roots.state, "usage.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(x) for x in f.read().splitlines() if x.strip()]


class Harness:
    """The stand-ins, recording each call in order."""

    def __init__(self, roots, restricted=True, cost=None, sleep=0.0,
                 fail=(), probe_raises=False, key_raises=False):
        self.roots = roots
        self.calls = []
        self.events = []
        self.shard_kw = []
        self.restricted = restricted
        self.cost = cost
        self.sleep = sleep
        self.fail = set(fail)
        self.probe_raises = probe_raises
        self.key_raises = key_raises
        self.seen_log = []
        self.lock = threading.Lock()

    def check_dirs(self, dirs, home):
        self.calls.append("dirs")
        return [os.path.realpath(d) for d in dirs]

    def ensure_probe(self, claude):
        self.calls.append("probe")
        if self.probe_raises:
            raise StandInError("probe.fail", check="key", detail="x")
        return {"ok": True, "restricted": self.restricted}

    def key(self):
        self.calls.append("key")
        if self.key_raises:
            raise StandInError("key.none", store="x")
        return FAKE_KEY

    def wrap(self, argv, **kw):
        return list(argv)

    def started(self, pid):
        return "start-%d" % pid

    def emit(self, event, **fields):
        with self.lock:
            self.events.append((event, fields, self._live()))
            if event == "reserved":
                self.calls.append("reserved")

    def _live(self):
        d = os.path.join(self.roots.state, "live")
        out = []
        for root, _dirs, files in os.walk(d):
            for name in files:
                if name.endswith(".json"):
                    with open(os.path.join(root, name)) as f:
                        out.append(json.load(f))
        return out

    def run_shard(self, shard, **kw):
        with self.lock:
            self.calls.append("shard")
            self.shard_kw.append(dict(kw, label=shard.label))
            self.seen_log.append(log_lines(self.roots))
        if self.sleep:
            time.sleep(self.sleep)
        grant = kw["grant_usd"]
        cost = grant / 2 if self.cost is None else self.cost(grant)
        state = "failed" if shard.label in self.fail else "ok"
        return ShardResult(shard.label, shard.type, state, cost, False,
                           None, None, MODELS[shard.type])

    def kw(self):
        return dict(run_shard=self.run_shard, wrap=self.wrap, key=self.key,
                    ensure_probe=self.ensure_probe, started=self.started,
                    emit=self.emit, check_dirs=self.check_dirs, models=MODELS)


def run_fanout(job, roots, h, lane=None, session="sess-1", **kw):
    args = h.kw()
    args.update(kw)
    return F.run(job, lane=lane or make_lane(), roots=roots, session=session,
                 claude="/bin/false", **args)


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = self._td.name
        self.roots = make_roots(self.tmp)

    def tearDown(self):
        self._td.cleanup()

    def assertCode(self, code, fn, *a, **kw):
        with self.assertRaises(Exception) as cm:
            fn(*a, **kw)
        self.assertEqual(getattr(cm.exception, "code", None), code,
                         repr(cm.exception))
        return cm.exception


# ---------------------------------------------------------------- the job
WHOLE = {"schema": "agentik.fanout.job/1", "id": "rv-auth", "budget_usd": 1.5,
         "dirs": ["/tmp/a"],
         "shards": [{"label": "one", "type": "review", "prompt": "first"},
                    {"label": "two", "type": "explore", "prompt": "second"}],
         "max_shard_usd": 0.5, "jobs": 2, "timeout_sec": 60}


class JobTest(Base):
    def write(self, obj, name="job.json"):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as f:
            f.write(obj if isinstance(obj, str) else json.dumps(obj))
        return path

    def test_whole_job_loads(self):
        j = J.load(self.write(WHOLE), types=TYPES)
        self.assertEqual(j.id, "rv-auth")
        self.assertEqual(j.budget_usd, 1.5)
        self.assertEqual(list(j.dirs), ["/tmp/a"])
        self.assertEqual(j.shards[1], J.Shard("two", "explore", "second"))
        self.assertEqual((j.max_shard_usd, j.jobs, j.timeout_sec), (0.5, 2, 60))

    def test_defaults(self):
        j = J.load(self.write({"budget_usd": 1, "shards": [
            {"type": "review", "prompt": "x"}]}), types=TYPES)
        self.assertEqual((j.jobs, j.timeout_sec, j.max_shard_usd), (4, 900, None))
        self.assertEqual(j.shards[0].label, "s1")
        self.assertRegex(j.id, r"^f-\d{8}T\d{6}Z-[0-9a-f]{4}$")

    def test_bad_shapes(self):
        cases = [
            ({"extra": 1}, "extra"),
            ({"budget_usd": None}, "budget_usd"),
            ({"budget_usd": 0}, "budget_usd"),
            ({"budget_usd": "2"}, "budget_usd"),
            ({"budget_usd": True}, "budget_usd"),
            ({"dirs": "/tmp"}, "dirs"),
            ({"shards": []}, "shards"),
            ({"shards": "x"}, "shards"),
            ({"shards": [{"type": "review", "prompt": "p", "colour": 1}]},
             "shards[0].colour"),
            ({"shards": [{"type": "review"}]}, "shards[0].prompt"),
            ({"shards": [{"type": "review", "prompt": "p", "label": "x" * 81}]},
             "shards[0].label"),
            ({"shards": [{"type": "review", "prompt": "p", "label": "a\nb"}]},
             "shards[0].label"),
            ({"timeout_sec": 0}, "timeout_sec"),
            ({"jobs": "4"}, "jobs"),
            ({"id": 5}, "id"),
            ({"schema": "other/1"}, "schema"),
        ]
        for change, field in cases:
            obj = dict(WHOLE)
            for k, v in change.items():
                if v is None:
                    obj.pop(k)
                else:
                    obj[k] = v
            e = self.assertCode("job.shape", J.load, self.write(obj), types=TYPES)
            self.assertEqual(e.fields.get("field"), field, change)
            self.assertTrue(e.fields.get("why"))
        self.assertCode("job.shape", J.load, self.write("{not json"), types=TYPES)
        self.assertCode("job.shape", J.load, self.write("[1]"), types=TYPES)

    def test_bad_id(self):
        for bad in ("-x", "a_b", "a" * 65, "", "rv auth"):
            e = self.assertCode("job.id", J.load,
                                self.write(dict(WHOLE, id=bad)), types=TYPES)
            self.assertEqual(e.fields, {"id": bad})
        J.load(self.write(dict(WHOLE, id="a" * 64)), types=TYPES)

    def test_unknown_type(self):
        obj = dict(WHOLE, shards=[{"type": "implement", "prompt": "p"}])
        e = self.assertCode("job.type", J.load, self.write(obj), types=TYPES)
        self.assertEqual(e.fields, {"type": "implement"})

    def test_five_flags_refused(self):
        for flag in ("--model", "--out", "--claude-arg", "--phase", "--stagger-sec"):
            e = self.assertCode("job.flag", J.from_argv,
                                ["--budget-usd", "1", flag, "v", "p"], types=TYPES)
            self.assertEqual(e.fields, {"flag": flag})
        # The old suite's D5: a smuggled second ceiling never reaches a shard.
        self.assertCode("job.flag", J.from_argv,
                        ["--budget-usd", "1", "--claude-arg=--max-budget-usd 9", "p"],
                        types=TYPES)

    def test_short_form_equals_json_twin(self):
        short = J.from_argv(["--budget-usd", "1.5", "--profile", "explore",
                             "--add-dir", "/tmp/a", "-j", "2",
                             "--max-shard-usd", "0.5", "--timeout-sec", "60",
                             "--id", "rv-auth", "first", "second"], types=TYPES)
        twin = dict(WHOLE, shards=[{"type": "explore", "prompt": "first"},
                                   {"type": "explore", "prompt": "second"}])
        self.assertEqual(short, J.load(self.write(twin), types=TYPES))

    def test_short_defaults(self):
        j = J.from_argv(["--budget-usd", "1", "p"], types=TYPES)
        self.assertEqual(j.shards[0].type, "review")
        self.assertEqual(j.timeout_sec, 900)
        self.assertEqual(j.jobs, 4)

    def test_tasks_three_forms(self):
        arr = self.write([{"label": "a", "prompt": "p1"}, "p2"], "t.json")
        lines = self.write('{"label": "a", "prompt": "p1"}\n"p2"\n', "t.jsonl")
        plain = self.write("# a comment\np1\n\np2\n", "t.txt")
        want = [("a", "p1"), ("s2", "p2"), ("s3", "p3")]
        for path in (arr, lines):
            j = J.from_argv(["--budget-usd", "1", "--tasks", path, "p3"], types=TYPES)
            self.assertEqual([(s.label, s.prompt) for s in j.shards], want, path)
        j = J.from_argv(["--budget-usd", "1", "--tasks", plain], types=TYPES)
        self.assertEqual([(s.label, s.prompt) for s in j.shards],
                         [("s1", "p1"), ("s2", "p2")])

    def test_parse_picks_its_form(self):
        j = J.parse(["--budget-usd", "1", "p"], types=TYPES)
        self.assertEqual(j.shards[0].prompt, "p")
        j = J.parse(["-"], types=TYPES, stdin=io.StringIO(json.dumps(WHOLE)))
        self.assertEqual(j.id, "rv-auth")
        self.assertEqual(J.parse([self.write(WHOLE)], types=TYPES).id, "rv-auth")
        self.assertCode("job.shape", J.parse, ["a", "b"], types=TYPES)


# ---------------------------------------------------------------- the pool
class PoolTest(Base):
    def test_floor_is_measured(self):
        self.assertEqual(P.FLOOR_USD, 0.0675)
        self.assertEqual(0.05 * 1.35, P.FLOOR_USD)

    def test_floor_exact_starts_a_hair_under_does_not(self):
        self.assertEqual(P.BudgetPool(1.0).reserve(0.0675), 0.0675)
        self.assertEqual(P.BudgetPool(1.0).reserve(0.0674999), 0.0)
        self.assertEqual(P.BudgetPool(0.0675).reserve(1.0), 0.0675)

    def test_floor_judged_on_ceiling_not_reservation(self):
        # Old D3: a $0.06 pool buys a $0.044 ceiling: skipped, not launched.
        self.assertEqual(P.BudgetPool(0.06).reserve(0.06), 0.0)
        h = Harness(self.roots)
        r = run_fanout(make_job(0.06, max_shard_usd=0.06), self.roots, h)
        self.assertEqual(r.shards[0].state, "skipped")
        self.assertEqual(r.shards[0].reason, "floor")
        self.assertNotIn("shard", h.calls)

    def test_settle_books_actual_even_above_grant(self):
        p = P.BudgetPool(1.0)
        g = p.reserve(0.4)
        p.settle(g, 0.5)
        self.assertAlmostEqual(p.settled, 0.5)
        self.assertAlmostEqual(p.available, 0.5)

    def test_hard_aggregate_budget(self):
        # Old: ten shards of $0.30 under $1.00, three at once.
        h = Harness(self.roots, cost=lambda g: g)
        shards = [("n%d" % i, "review", "p") for i in range(10)]
        job = make_job(1.0, shards, max_shard_usd=0.30, jobs=3)
        r = run_fanout(job, self.roots, h)
        self.assertLessEqual(r.spent_usd, 1.0 + 1e-9)
        self.assertEqual(len(r.shards), 10)
        skipped = [s for s in r.shards if s.state == "skipped"]
        self.assertTrue(skipped)
        self.assertTrue(all(s.reason == "budget" for s in skipped))
        self.assertEqual(r.rc, 1)

    def test_ceiling_below_grant(self):
        p = F.plan(make_job(1.0, max_shard_usd=0.5), lane=make_lane(),
                   roots=self.roots, models=MODELS, check_dirs=Harness(self.roots).check_dirs)
        s = p["shards"][0]
        self.assertEqual(s["grant_usd"], 0.5)
        self.assertAlmostEqual(s["ceiling_usd"], 0.5 / 1.35, places=6)

    def test_no_cost_books_grant(self):
        # Old D1: a shard with no cost figure books its grant, estimated.
        h = Harness(self.roots, cost=lambda g: None)
        r = run_fanout(make_job(0.4), self.roots, h)
        book = [x for x in log_lines(self.roots) if x["kind"] == "shard"][0]
        self.assertEqual((book["cost_usd"], book["estimated"]), (0.4, True))
        self.assertAlmostEqual(r.spent_usd, 0.4)

    def test_nan_cost_cannot_poison_the_pool(self):
        # Old D2: a NaN cost is booked as the grant, and later shards still run.
        h = Harness(self.roots, cost=lambda g: float("nan"))
        job = make_job(1.0, [("a", "review", "p"), ("b", "review", "p")],
                       max_shard_usd=0.4, jobs=1)
        r = run_fanout(job, self.roots, h)
        self.assertTrue(math.isfinite(r.spent_usd))
        self.assertLessEqual(r.spent_usd, 1.0 + 1e-9)
        self.assertTrue(all(s.state != "skipped" for s in r.shards))

    def test_overshoot(self):
        # Old: 1.2x (measured) stays within the budget; 2.0x stays bounded.
        for factor, bound in ((1.2, 1.0), (2.0, 1.5)):
            roots = make_roots(os.path.join(self.tmp, str(factor)))
            h = Harness(roots, cost=lambda g, f=factor: g / 1.35 * f)
            shards = [("n%d" % i, "review", "p") for i in range(12)]
            r = run_fanout(make_job(1.0, shards, max_shard_usd=0.2, jobs=4),
                           roots, h)
            self.assertLessEqual(r.spent_usd, bound + 1e-9, factor)
            self.assertEqual(len(r.shards), 12)


# ---------------------------------------------------------------- the log
RESERVE_KEYS = {"schema", "kind", "fanout", "day", "at", "budget_usd", "pid",
                "pid_started", "session"}
DAY = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def reserve(roots, fanout, budget, max_day=10.0, now=DAY):
    L.reserve(roots, fanout=fanout, budget_usd=budget, max_day_usd=max_day,
              session="none", pid=os.getpid(), pid_started="x", now=now)


class LedgerTest(Base):
    def test_one_synced_line(self):
        with mock.patch("os.fsync", wraps=os.fsync) as fsync:
            reserve(self.roots, "a", 2.0)
            self.assertTrue(fsync.called)
        lines = log_lines(self.roots)
        self.assertEqual(len(lines), 1)
        self.assertEqual(set(lines[0]), RESERVE_KEYS)
        self.assertEqual((lines[0]["kind"], lines[0]["day"]), ("reserve", "2026-11-13"))
        self.assertTrue(lines[0]["at"].endswith("Z"))

    def test_settled_and_unsettled(self):
        reserve(self.roots, "a", 2.0)
        L.book(self.roots, fanout="a", run="a-01", type="review", model="m",
               state="ok", cost_usd=0.5, estimated=False, now=DAY)
        L.settle(self.roots, fanout="a", spent_usd=0.5, now=DAY)
        reserve(self.roots, "b", 3.0)
        d = L.day(self.roots, now=DAY)
        self.assertEqual(d["day"], "2026-11-13")
        self.assertAlmostEqual(d["sum_usd"], 3.5)
        self.assertAlmostEqual(d["settled_usd"], 0.5)
        self.assertAlmostEqual(d["held_usd"], 3.0)
        self.assertEqual([u["fanout"] for u in d["unsettled"]], ["b"])
        self.assertEqual(set(d["unsettled"][0]),
                         {"fanout", "budget_usd", "at", "pid", "pid_started"})

    def test_other_day_counts_nothing(self):
        reserve(self.roots, "a", 4.0, now=DAY - timedelta(days=1))
        self.assertEqual(L.day(self.roots, now=DAY)["sum_usd"], 0)

    def test_id_used(self):
        reserve(self.roots, "a", 1.0, now=DAY - timedelta(days=1))
        e = self.assertCode("id.used", reserve, self.roots, "a", 1.0)
        self.assertEqual(e.fields, {"id": "a", "day": "2026-11-12"})
        self.assertEqual(len(log_lines(self.roots)), 1)

    def test_budget_day_appends_nothing(self):
        reserve(self.roots, "a", 6.0)
        e = self.assertCode("budget.day", reserve, self.roots, "b", 6.0)
        self.assertEqual(e.fields, {"budget_usd": 6.0, "day_sum_usd": 6.0,
                                    "max_day_usd": 10.0})
        self.assertEqual(len(log_lines(self.roots)), 1)
        reserve(self.roots, "c", 4.0)

    def test_torn_line_is_a_fault(self):
        reserve(self.roots, "a", 1.0)
        path = os.path.join(self.roots.state, "usage.jsonl")
        with open(path, "a") as f:
            f.write('{"schema": "agentik.api.usage/1", "kind": "res\n')
        size = os.path.getsize(path)
        e = self.assertCode("log.fault", reserve, self.roots, "b", 1.0)
        self.assertEqual(e.fields, {"path": path, "line": 2})
        self.assertEqual(os.path.getsize(path), size)
        self.assertCode("log.fault", L.day, self.roots, now=DAY)

    def test_modes(self):
        reserve(self.roots, "a", 1.0)
        st = self.roots.state
        self.assertEqual(os.stat(st).st_mode & 0o777, 0o700)
        for name in ("usage.jsonl", "usage.lock"):
            self.assertEqual(os.stat(os.path.join(st, name)).st_mode & 0o777, 0o600)

    def test_day_writes_nothing(self):
        self.assertEqual(L.day(self.roots, now=DAY)["sum_usd"], 0)
        self.assertFalse(os.path.exists(self.roots.state))

    def test_old_lines_leave_at_a_reservation(self):
        reserve(self.roots, "old", 1.0, now=DAY - timedelta(days=8))
        reserve(self.roots, "new", 1.0)
        self.assertEqual([x["fanout"] for x in log_lines(self.roots)], ["new"])


RACE_CHILD = r"""
import os, sys, time, types
sys.path.insert(0, sys.argv[1])
from apilane import ledger
state, go, name = sys.argv[2], sys.argv[3], sys.argv[4]
roots = types.SimpleNamespace(home=os.path.dirname(state), config="", state=state, store="")
while not os.path.exists(go):
    time.sleep(0.002)
try:
    ledger.reserve(roots, fanout=name, budget_usd=6.0, max_day_usd=10.0,
                   session="none", pid=os.getpid(), pid_started="x")
    print("ok")
except Exception as e:
    print(getattr(e, "code", repr(e)))
"""


class LedgerRaceTest(Base):
    def test_one_passes_each_round(self):
        for n in range(20):
            state = os.path.join(self.tmp, "r%d" % n, "state")
            go = os.path.join(self.tmp, "go%d" % n)
            kids = [subprocess.Popen([sys.executable, "-c", RACE_CHILD, LIB, state,
                                      go, name], stdout=subprocess.PIPE, text=True)
                    for name in ("a", "b")]
            time.sleep(0.15)
            open(go, "w").close()
            outs = sorted(k.communicate(timeout=30)[0].strip() for k in kids)
            self.assertEqual(outs, ["budget.day", "ok"], "round %d" % n)


# ---------------------------------------------------------------- the plan
class PlanTest(Base):
    def test_shape_and_nothing_written(self):
        h = Harness(self.roots)
        job = make_job(1.0, [("a", "review", "p"), ("b", "explore", "p")],
                       dirs=(self.tmp,))
        p = F.plan(job, lane=make_lane(), roots=self.roots, models=MODELS,
                   check_dirs=h.check_dirs, now=DAY)
        self.assertEqual(set(p), {"id", "budget_usd", "day_sum_usd", "worst_usd",
                                  "dirs", "shards"})
        self.assertEqual(set(p["shards"][0]),
                         {"label", "type", "model", "grant_usd", "ceiling_usd"})
        self.assertEqual(p["shards"][1]["model"], "model-e")
        self.assertAlmostEqual(p["worst_usd"], 1.0)
        self.assertFalse(os.path.exists(self.roots.state))
        self.assertEqual(h.calls, ["dirs"])

    def test_refusals_in_order(self):
        def bad_dirs(dirs, home):
            raise StandInError("wall.dir", dir="/", why="root")

        def plan(job, lane, check=bad_dirs):
            return F.plan(job, lane=lane, roots=self.roots, models=MODELS,
                          check_dirs=check, now=DAY)
        big = make_job(3.0)
        off = make_lane(enabled=False, console_limit_usd=None)
        e = self.assertCode("lane.off", plan, big, off)
        self.assertEqual(e.fields, {"config": self.roots.config})
        self.assertCode("limit.unstated", plan, big, make_lane(console_limit_usd=None))
        self.assertCode("wall.dir", plan, big, make_lane())
        ok = Harness(self.roots).check_dirs
        e = self.assertCode("budget.fanout", plan, big, make_lane(), ok)
        self.assertEqual(e.fields, {"budget_usd": 3.0, "max_fanout_usd": 2.0})
        reserve(self.roots, "earlier", 9.0)
        e = self.assertCode("budget.day", plan, make_job(2.0), make_lane(), ok)
        self.assertEqual(e.fields, {"budget_usd": 2.0, "day_sum_usd": 9.0,
                                    "max_day_usd": 10.0})


# ---------------------------------------------------------------- the run
class OrderTest(Base):
    def test_one_order(self):
        h = Harness(self.roots)
        run_fanout(make_job(1.0), self.roots, h)
        self.assertEqual(h.calls[:5], ["dirs", "probe", "key", "reserved", "shard"])
        self.assertEqual(h.events[0][0], "plan")
        seen = [x for x in h.seen_log[0] if x["kind"] == "reserve"]
        self.assertEqual([x["fanout"] for x in seen], ["t1"])

    def test_probe_raises(self):
        h = Harness(self.roots, probe_raises=True)
        self.assertCode("probe.fail", run_fanout, make_job(1.0), self.roots, h)
        self.assertNotIn("key", h.calls)
        self.assertNotIn("shard", h.calls)
        self.assertEqual(log_lines(self.roots), [])

    def test_key_raises(self):
        h = Harness(self.roots, key_raises=True)
        self.assertCode("key.none", run_fanout, make_job(1.0), self.roots, h)
        self.assertNotIn("shard", h.calls)
        self.assertEqual(log_lines(self.roots), [])


class RunTest(Base):
    SHARDS = [("a", "review", "p"), ("b", "explore", "p"), ("c", "review", "p")]

    def test_three_shards(self):
        h = Harness(self.roots, sleep=0.6)
        with mock.patch.object(F, "BEAT_SEC", 0.2):
            r = run_fanout(make_job(1.5, self.SHARDS, jobs=1), self.roots, h)
        self.assertEqual(r.rc, 0)
        starts = [e for e in h.events if e[0] == "shard.start"]
        ends = [e for e in h.events if e[0] == "shard.end"]
        self.assertEqual([e[1]["run"] for e in starts], ["t1-01", "t1-02", "t1-03"])
        for i, (_ev, f, live) in enumerate(starts):
            rec = live[0]
            self.assertEqual(rec["queued"], 2 - i)
            self.assertEqual(rec["running"], [{"run": f["run"], "type": f["type"]}])
            self.assertEqual(rec["ok"], i)
        for i, (_ev, f, live) in enumerate(ends):
            self.assertEqual((live[0]["ok"], live[0]["running"]), (i + 1, []))
            self.assertEqual(f["state"], "ok")
        self.assertTrue([e for e in h.events if e[0] == "beat"])
        self.assertEqual(h.events[-1][0], "done")
        kinds = [x["kind"] for x in log_lines(self.roots)]
        self.assertEqual(kinds, ["reserve", "shard", "shard", "shard", "settle"])
        path = os.path.join(self.roots.state, "live", "sess-1", "t1.json")
        with open(path) as f:
            rec = json.load(f)
        self.assertTrue(rec["ended"])
        self.assertEqual(h.events[1][0], "reserved")
        self.assertEqual(h.events[1][2], [])   # the live record follows it
        self.assertNotEqual(rec["beat"], starts[0][2][0]["beat"])
        self.assertEqual(oct(os.stat(path).st_mode & 0o777), oct(0o600))
        kw = h.shard_kw[0]
        self.assertEqual((kw["fanout"], kw["number"], kw["session"]), ("t1", 1, "sess-1"))
        self.assertEqual(kw["key"](), FAKE_KEY)
        self.assertTrue(kw["restricted"])
        self.assertEqual(kw["timeout_sec"], 900)

    def test_one_fails(self):
        h = Harness(self.roots, fail={"b"})
        r = run_fanout(make_job(1.5, self.SHARDS, jobs=1), self.roots, h, session=None)
        self.assertEqual(r.rc, 1)
        ends = [e for e in h.events if e[0] == "shard.end"]
        self.assertEqual(ends[1][2][0]["failed"], 1)
        self.assertEqual(h.events[-1][1]["failed"], 1)
        self.assertFalse(os.path.exists(
            os.path.join(self.roots.state, "live", "none", "t1.json")))

    def test_floor_skips(self):
        h = Harness(self.roots)
        r = run_fanout(make_job(1.0, self.SHARDS, max_shard_usd=0.06), self.roots, h)
        self.assertEqual([s.state for s in r.shards], ["skipped"] * 3)
        self.assertNotIn("shard", h.calls)
        self.assertEqual(r.rc, 1)

    def test_restricted_null(self):
        h = Harness(self.roots, restricted=None)
        run_fanout(make_job(1.5, self.SHARDS), self.roots, h)
        self.assertEqual([k["restricted"] for k in h.shard_kw], [False] * 3)


CHILD = r"""
import os, signal, subprocess, sys, time, types, collections
sys.path.insert(0, sys.argv[1])
from apilane import fanout, job
state, mode, budget, fid = sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5]
roots = types.SimpleNamespace(home=os.path.dirname(state), config="c", state=state, store="")
lane = types.SimpleNamespace(enabled=True, max_fanout_usd=10.0, max_day_usd=10.0,
                             console_limit_usd=5.0, proxy=None, ca_file=None)
R = collections.namedtuple("R", "label type state cost_usd estimated result_path reason model")

def started(pid):
    out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)],
                         capture_output=True, text=True).stdout.strip()
    return out or None

def run_shard(shard, **kw):
    if mode == "kill":
        time.sleep(60)
    run = "%s-%02d" % (kw["fanout"], kw["number"])
    p = subprocess.Popen(["sleep", "60"], start_new_session=True)
    d = os.path.join(state, "runs", run)
    os.makedirs(d)
    tmp = os.path.join(d, ".run.json")
    with open(tmp, "w") as f:
        f.write('{"pid": %d, "pid_started": "%s"}' % (p.pid, started(p.pid)))
    os.rename(tmp, os.path.join(d, "run.json"))
    p.wait()
    return R(shard.label, shard.type, "failed", None, True, None, "exit:1", "m")

j = job.Job(fid, budget, (), (job.Shard("a", "review", "p"),), None, 4, 900)
fanout.run(j, lane=lane, roots=roots, session="sess-1", claude="/bin/false",
           run_shard=run_shard, wrap=lambda a, **k: a, key=lambda: "made-up",
           ensure_probe=lambda c: {"restricted": True}, started=started,
           emit=lambda e, **f: None, check_dirs=lambda d, home: [],
           models={"review": "m"})
"""


def spawn(roots, mode, budget, fid):
    return subprocess.Popen([sys.executable, "-c", CHILD, LIB, roots.state, mode,
                             str(budget), fid])


def wait_for(cond, limit):
    end = time.time() + limit
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class KillTest(Base):
    def test_kill_9_counts_whole(self):
        kid = spawn(self.roots, "kill", 2.0, "k1")
        try:
            self.assertTrue(wait_for(lambda: any(
                x["kind"] == "reserve" for x in log_lines(self.roots)), 15))
        finally:
            kid.kill()
            kid.wait()
        d = L.day(self.roots)
        self.assertAlmostEqual(d["sum_usd"], 2.0)
        self.assertEqual([u["fanout"] for u in d["unsettled"]], ["k1"])
        lane = make_lane(max_fanout_usd=10.0)
        h = Harness(self.roots)
        self.assertCode("budget.day", run_fanout, make_job(9.0, id="k2"),
                        self.roots, h, lane=lane)
        self.assertNotIn("shard", h.calls)
        self.assertNotIn("key", h.calls)
        r = run_fanout(make_job(8.0, id="k3"), self.roots, Harness(self.roots), lane=lane)
        self.assertEqual(r.rc, 0)


class SignalTest(Base):
    def stop_with(self, sig):
        kid = spawn(self.roots, "signal", 2.0, "s1")
        runj = os.path.join(self.roots.state, "runs", "s1-01", "run.json")
        try:
            self.assertTrue(wait_for(lambda: os.path.exists(runj), 15))
            with open(runj) as f:
                pid = json.load(f)["pid"]
            kid.send_signal(sig)

            def gone():
                try:
                    os.killpg(pid, 0)
                    return False
                except ProcessLookupError:
                    return True
            self.assertTrue(wait_for(gone, 5), "the shard's group outlived 5 s")
            kid.wait(timeout=15)
        finally:
            if kid.poll() is None:
                kid.kill()
                kid.wait()
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, UnboundLocalError):
                pass
        settles = [x for x in log_lines(self.roots) if x["kind"] == "settle"]
        d = L.day(self.roots)
        if settles:
            self.assertAlmostEqual(d["sum_usd"], settles[0]["spent_usd"])
            self.assertAlmostEqual(settles[0]["spent_usd"], 2.0)
        else:
            self.assertAlmostEqual(d["sum_usd"], 2.0)

    def test_sigterm(self):
        self.stop_with(signal.SIGTERM)

    def test_sighup(self):
        self.stop_with(signal.SIGHUP)


if __name__ == "__main__":
    unittest.main()
