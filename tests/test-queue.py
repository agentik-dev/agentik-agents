#!/usr/bin/env python3
"""Tests for queue-mvp's timestamps and its backoff wait.

Stub-driven: HOME is a temp dir set before the tool loads, so its default
state dir lands there and is removed after; the job-queue service and the
clock are stubs, so nothing is served, nothing waits and nothing is spent.

    tests/test-queue.py
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import pathlib
import shutil
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone

REPO = pathlib.Path(__file__).resolve().parent.parent
TOOL = REPO / "bin" / "queue-mvp"
UTC = timezone.utc

passed = failed = 0


def check(cond: bool, desc: str, detail: str = "") -> None:
    global passed, failed
    if cond:
        print(f"  PASS  {desc}")
        passed += 1
    else:
        print(f"  FAIL  {desc}\n     {detail}")
        failed += 1


def load():
    """bin/queue-mvp as a module, in sys.modules first: its dataclasses look it up."""
    loader = importlib.machinery.SourceFileLoader("queue_mvp", str(TOOL))
    spec = importlib.util.spec_from_loader("queue_mvp", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["queue_mvp"] = mod
    loader.exec_module(mod)
    return mod


class Clock:
    """The module's utcnow and time.sleep: a sleep advances the clock, never waits."""

    def __init__(self, start: datetime) -> None:
        self.t = start
        self.slept = 0.0
        self.log: list = []

    def now(self) -> datetime:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.log.append(("sleep", seconds))
        self.slept += seconds
        self.t += timedelta(seconds=seconds)


def wait(qm, eligible_at: str):
    """wait_until_eligible on a pending job, the clock at 12:00:00.000000 UTC."""
    clock = Clock(datetime(2026, 10, 16, 12, 0, 0, tzinfo=UTC))
    job = {"id": 7, "status": "pending", "eligible_at": eligible_at}
    polls = []

    def get_job(job_id):
        polls.append(job_id)
        if len(polls) > 20:
            raise RuntimeError("stub: more than 20 polls")
        return dict(job), 200

    def event(name, **kw):
        clock.log.append(("event", name, kw))

    st = types.SimpleNamespace(api=types.SimpleNamespace(get_job=get_job),
                               journal=types.SimpleNamespace(event=event))
    saved = (qm.utcnow, qm.time)
    qm.utcnow, qm.time = clock.now, types.SimpleNamespace(sleep=clock.sleep)
    try:
        got = qm.wait_until_eligible(st, 7)
    except Exception as e:  # noqa: BLE001  (a failure is a FAIL line, not a crash)
        got = e
    finally:
        qm.utcnow, qm.time = saved
    return got, clock


def main(qm, home: pathlib.Path) -> int:
    print("== loading ==")
    check(home in qm.DEFAULT_STATE_DIR.parents, "DEFAULT_STATE_DIR is under the temp HOME",
          str(qm.DEFAULT_STATE_DIR))
    check(not any(home.iterdir()), "loading writes nothing under HOME",
          str(sorted(p.name for p in home.iterdir())))

    print("== parse_ts: the fraction ==")
    digits = "123456789"
    for n in range(10):
        s = "2026-10-16T12:34:56" + ("." + digits[:n] if n else "") + "Z"
        us = int((digits[:n] + "000000")[:6])
        want = datetime(2026, 10, 16, 12, 34, 56, us, tzinfo=UTC)
        got = qm.parse_ts(s)
        check(got == want and got.tzinfo == UTC and got.microsecond == us,
              f"{n} fraction digits: {s} -> microsecond {us}", f"{got!r}")
    got = qm.parse_ts("2026-10-16T12:34:56.5+02:00")
    want = datetime(2026, 10, 16, 10, 34, 56, 500000, tzinfo=UTC)
    check(got == want and got.tzinfo == UTC, "an offset after one digit is kept: .5+02:00 -> 10:34:56.5 UTC",
          f"{got!r}")
    got = qm.parse_ts("2026-10-16 12:34:56.1234567")
    want = datetime(2026, 10, 16, 12, 34, 56, 123456, tzinfo=UTC)
    check(got == want, "a space for the T and no offset: cut to 6 digits, read as UTC", f"{got!r}")
    check(qm.parse_ts("") is None, "an empty string is None")
    check(qm.parse_ts("not a time") is None, "a non-time is None")

    print("== wait_until_eligible: the backoff ==")
    for frac in ("1", "12", "1234", "12345"):
        at = f"2026-10-16T12:00:05.{frac}Z"
        got, clock = wait(qm, at)
        kinds = [e[0] if e[0] == "sleep" else e[1] for e in clock.log]
        ok = (isinstance(got, dict) and got.get("status") == "pending"
              and clock.slept >= 5 and "backoff_wait" in kinds
              and kinds.index("backoff_wait") < kinds.index("sleep"))
        check(ok, f"eligible_at 5 s ahead as .{frac}: sleeps at least 5 s, journals backoff_wait first",
              f"returned {got!r}, slept {clock.slept}, log {kinds}")
    got, clock = wait(qm, "2026-10-16T11:59:00.000Z")
    check(isinstance(got, dict) and got.get("status") == "pending" and not clock.log,
          "eligible_at in the past: returns with no sleep and no journal line",
          f"returned {got!r}, log {clock.log}")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="test-queue.")
    old_home = os.environ.get("HOME")
    try:
        os.environ["HOME"] = tmp
        rc = main(load(), pathlib.Path(tmp))
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(rc)
