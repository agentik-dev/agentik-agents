#!/usr/bin/env python3
"""Tests for claude-fanout.

Drives the real orchestrator against a stub wrapper that fabricates envelopes,
so every failure mode -- degenerate output, API error, ceiling trip, timeout,
unparseable output -- is exercised without an API key or any spend.

    tests/test-fanout.py
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
FANOUT = REPO / "bin" / "claude-fanout"

# The stub reads the -p prompt and fabricates an envelope from a keyword in it,
# so a test can request any outcome. It also honours --max-budget-usd so the
# budget-accounting tests see plausible costs.
STUB = r"""#!/usr/bin/env python3
import json, sys, time
argv = sys.argv[1:]
prompt = ""
cap = 10.0
for i, a in enumerate(argv):
    if a == "-p" and i + 1 < len(argv):
        prompt = argv[i + 1]
    if a == "--max-budget-usd" and i + 1 < len(argv):
        cap = float(argv[i + 1])

cost = 0.10
for tok in prompt.split():
    if tok.startswith("cost:"):
        cost = float(tok.split(":", 1)[1])
cost = min(cost, cap)

env = {
    "type": "result", "subtype": "success", "is_error": False,
    "terminal_reason": "completed", "session_id": "sid-" + str(abs(hash(prompt)) % 10000),
    "total_cost_usd": cost, "num_turns": 4, "permission_denials": [],
    "usage": {}, "modelUsage": {},
}

if "GOOD" in prompt:
    env["structured_output"] = {
        "summary": "A substantive summary of what the review actually found, "
                   "long enough to clear the substance threshold.",
        "findings": [{"file": "bin/claude-api-agent", "line": 10, "severity": "low",
                      "issue": "A concrete and adequately described problem statement."}],
    }
elif "DEGENERATE" in prompt:
    env["structured_output"] = {"summary": "test",
                                "findings": [{"file": "a", "severity": "low", "issue": "test"}]}
elif "CLEAN" in prompt:
    # A legitimately clean review: short summary, no findings. Must be OK --
    # the old length gate destroyed this (V1).
    env["structured_output"] = {"summary": "No actionable defects found.",
                                "findings": []}
elif "TERSEMIX" in prompt:
    # 18 substantive findings + 1 terse one. The terse finding must not poison
    # the shard (V2). All cite a real repo file so paths resolve.
    good = {"file": "bin/claude-fanout",
            "issue": "a concrete and adequately described problem statement"}
    env["structured_output"] = {
        "summary": "Nineteen findings across the fan-out orchestrator.",
        "findings": [good] * 18 + [{"file": "bin/claude-fanout", "issue": "race"}]}
elif "NOSTRUCT" in prompt:
    pass
elif "APIERROR" in prompt:
    env["is_error"] = True
    env["terminal_reason"] = "api_error"
    env["result"] = "Invalid API key"
elif "CEILING" in prompt:
    env["is_error"] = True
    env["subtype"] = "error_max_budget_usd"
    env["terminal_reason"] = "budget_exhausted"
    env["result"] = ""
elif "GARBAGE" in prompt:
    sys.stdout.write("not json at all\n")
    sys.exit(1)
elif "NANCOST" in prompt:
    # A NaN cost would, unguarded, poison the pool: NaN makes every comparison
    # in reserve() false, so every later shard launches uncapped.
    sys.stdout.write('{"total_cost_usd": NaN, "num_turns": 3, "is_error": false,'
                     ' "terminal_reason": "completed", "structured_output":'
                     ' {"summary": "x", "findings": []}}\n')
    sys.exit(0)
elif "HANG" in prompt:
    time.sleep(60)

sys.stdout.write(json.dumps(env) + "\n")
sys.exit(1 if env["is_error"] else 0)
"""

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


passed = failed = 0


def check(cond: bool, desc: str, detail: str = "") -> None:
    global passed, failed
    if cond:
        print(f"  PASS  {desc}")
        passed += 1
    else:
        print(f"  FAIL  {desc}\n     {detail}")
        failed += 1


def run(tmp: pathlib.Path, prompts: list[str], *extra: str) -> tuple[int, dict]:
    out = tmp / f"run{len(list(tmp.iterdir()))}"
    cmd = [sys.executable, str(FANOUT), "--budget-usd", "1.00",
           "--out", str(out), "--json", *extra, *prompts]
    env = dict(os.environ, CLAUDE_FANOUT_WRAPPER=str(tmp / "stub"))
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    try:
        agg = json.loads(proc.stdout)
    except Exception:
        agg = {}
    return proc.returncode, agg


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        stub = tmp / "stub"
        stub.write_text(STUB)
        stub.chmod(0o755)

        print("== result classification ==")
        rc, agg = run(tmp, ["GOOD one", "DEGENERATE two", "APIERROR three",
                            "CEILING four", "GARBAGE five", "NOSTRUCT six"])
        st = {s["label"]: s["status"] for s in agg.get("shards", [])}
        check(st.get("task1") == "ok", "substantive result -> ok", str(st))
        check(st.get("task2") == "degenerate",
              "placeholder result -> degenerate", str(st))
        check(st.get("task3") == "error", "API error -> error", str(st))
        check(st.get("task4") == "budget_exhausted",
              "ceiling trip -> budget_exhausted", str(st))
        check(st.get("task5") == "unparseable", "non-JSON -> unparseable", str(st))
        check(st.get("task6") == "degenerate",
              "missing structured_output -> degenerate", str(st))
        check(rc != 0, "non-zero exit when any shard is unusable", f"rc={rc}")

        # The degenerate shard is the one this whole tool exists for: the
        # envelope said success and the schema validated.
        deg = next(s for s in agg["shards"] if s["label"] == "task2")
        check(bool(deg["reasons"]), "degenerate shard explains why",
              str(deg["reasons"]))

        print("== an API error is not mistaken for success ==")
        # The envelope carries subtype "success" while is_error is true; a
        # classifier keyed off subtype would call this a good run.
        err = next(s for s in agg["shards"] if s["label"] == "task3")
        check(err["status"] == "error" and "api_error" in " ".join(err["reasons"]),
              "error shard reports terminal_reason, not subtype", str(err["reasons"]))

        print("== all-good run exits zero ==")
        rc, agg = run(tmp, ["GOOD a", "GOOD b"])
        check(rc == 0, "exit 0 when every shard is usable", f"rc={rc}")
        check(agg["findings_total"] == 2, "findings are aggregated",
              str(agg.get("findings_total")))
        check(all("_shard" in f for f in agg["findings"]),
              "each finding is attributed to its shard")

        print("== hard aggregate budget ==")
        # Ten shards each reserving $0.30 against a $1.00 pool: the ceiling must
        # hold and the unfundable shards must be reported, not dropped.
        prompts = [f"GOOD cost:0.30 n{i}" for i in range(10)]
        rc, agg = run(tmp, prompts, "--jobs", "3", "--max-shard-usd", "0.30")
        spent = agg["spent_usd"]
        statuses = [s["status"] for s in agg["shards"]]
        check(spent <= 1.00 + 1e-9, "spend never exceeds the budget",
              f"spent=${spent}")
        check(len(statuses) == 10, "every task is accounted for",
              f"{len(statuses)} of 10")
        check(statuses.count("skipped_budget") > 0,
              "unfundable shards are reported as skipped",
              str({s: statuses.count(s) for s in set(statuses)}))
        skipped = next(s for s in agg["shards"] if s["status"] == "skipped_budget")
        check(bool(skipped["reasons"]), "skipped shard explains why",
              str(skipped["reasons"]))

        print("== per-shard ceiling is deflated for overshoot ==")
        rc, agg = run(tmp, ["GOOD cost:99 x"], "--max-shard-usd", "0.50")
        # The stub clamps its cost to the cap it was handed, so the observed
        # cost reveals the ceiling the orchestrator actually passed down.
        cost = agg["shards"][0]["cost_usd"]
        check(cost < 0.50, "shard ceiling is below its reservation",
              f"cost=${cost} (expected < $0.50)")

        print("== timeout ==")
        rc, agg = run(tmp, ["HANG forever"], "--timeout-sec", "2")
        s = agg["shards"][0]
        check(s["status"] == "timeout", "hung shard -> timeout", s["status"])
        check(s["cost_usd"] > 0,
              "timed-out shard books its reservation as spent",
              f"cost=${s['cost_usd']}")
        check("forfeit" in " ".join(s["reasons"]).lower(),
              "timeout explains that spend is forfeited", str(s["reasons"]))

        print("== dry run spends nothing ==")
        out = tmp / "dry"
        proc = subprocess.run(
            [sys.executable, str(FANOUT), "--budget-usd", "1.00", "--dry-run",
             "--out", str(out), "GOOD a", "GOOD b"],
            capture_output=True, text=True,
            env=dict(os.environ, CLAUDE_FANOUT_WRAPPER=str(stub)))
        plan = json.loads(proc.stdout)
        check(proc.returncode == 0 and len(plan["shards"]) == 2,
              "dry run reports the plan", proc.stdout[:200])
        check(not list(out.glob("shard-*.json")),
              "dry run launches nothing")

        print("== result validation rejects only genuine non-answers ==")
        # Runs from the repo root so cited repo files resolve under cwd.
        rc, agg = run(tmp, ["CLEAN a", "TERSEMIX b", "DEGENERATE c"])
        st = {s["label"]: s["status"] for s in agg["shards"]}
        check(st.get("task1") == "ok",
              "V1: clean 'no defects found' answer is accepted", str(st))
        check(st.get("task2") == "ok",
              "V2: one terse finding does not poison a substantive shard", str(st))
        check(st.get("task3") == "degenerate",
              "genuine placeholder output is still rejected", str(st))

        print("== a shard that ran without a cost figure books its reservation ==")
        # D1: an unparseable/garbage shard used to book $0 and free its whole
        # reservation, so the pool re-funded money that had already been spent.
        rc, agg = run(tmp, ["GARBAGE one"], "--max-shard-usd", "0.40")
        g = agg["shards"][0]
        check(g["cost_usd"] > 0 and g["cost_is_estimate"],
              "garbage shard books its reservation as an estimate, not $0",
              str((g["cost_usd"], g["cost_is_estimate"])))
        check(agg["spent_usd_is_upper_bound"] and agg["estimated_usd"] > 0,
              "aggregate flags spend as an upper bound", str(agg.get("estimated_usd")))

        print("== a NaN cost cannot poison the pool ==")
        # D2: json.loads accepts NaN; unguarded it makes every later reserve()
        # comparison false and launches subsequent shards uncapped.
        rc, agg = run(tmp, ["NANCOST a", "GOOD b"], "--budget-usd", "1.00",
                      "--max-shard-usd", "0.40", "--jobs", "1")
        spent = agg["spent_usd"]
        check(spent == spent and spent <= 1.00 + 1e-9,  # spent==spent is False for NaN
              "spend stays finite and bounded despite a NaN cost", str(spent))
        check(all(s["status"] != "skipped_budget" for s in agg["shards"]),
              "a NaN shard does not starve or over-fund later shards",
              str([s["status"] for s in agg["shards"]]))

        print("== --claude-arg cannot smuggle a second spend ceiling ==")
        # D5: a forwarded --max-budget-usd would contest the per-shard cap.
        out = tmp / "smuggle"
        proc = subprocess.run(
            [sys.executable, str(FANOUT), "--budget-usd", "1.00", "--out", str(out),
             "--claude-arg", "--max-budget-usd 9.99", "GOOD a"],
            capture_output=True, text=True,
            env=dict(os.environ, CLAUDE_FANOUT_WRAPPER=str(stub)))
        check(proc.returncode != 0 and "max-budget-usd" in proc.stderr,
              "--claude-arg with --max-budget-usd is rejected", proc.stderr[-160:])

        print("== the viability floor is judged on the ceiling, not the reservation ==")
        # D3: a reservation just above $0.05 buys a sub-$0.05 ceiling. With a
        # $0.06 pool the only shard must be skipped, not launched doomed.
        rc, agg = run(tmp, ["GOOD a"], "--budget-usd", "0.06", "--max-shard-usd", "0.06")
        check(agg["shards"][0]["status"] == "skipped_budget",
              "sub-viable-ceiling reservation is skipped", agg["shards"][0]["status"])

        print("== budget holds when shards overshoot their own ceiling ==")
        # Real shards overshoot: the ceiling is checked between requests, so the
        # request that crosses it still completes (measured 1.2x). The stub is
        # told to do the same, at 1.2x and then at a pathological 2.0x.
        for factor, must_hold in ((1.2, True), (2.0, False)):
            over = tmp / f"stub-over-{factor}"
            over.write_text(STUB.replace("cost = min(cost, cap)",
                                         f"cost = cap * {factor}"))
            over.chmod(0o755)
            out = tmp / f"over{factor}"
            proc = subprocess.run(
                [sys.executable, str(FANOUT), "--budget-usd", "1.00",
                 "--max-shard-usd", "0.20", "--jobs", "4", "--out", str(out),
                 "--json", *[f"GOOD n{i}" for i in range(12)]],
                capture_output=True, text=True,
                env=dict(os.environ, CLAUDE_FANOUT_WRAPPER=str(over)))
            agg = json.loads(proc.stdout)
            spent = agg["spent_usd"]
            if must_hold:
                check(spent <= 1.00 + 1e-9,
                      f"{factor}x overshoot (measured rate) stays within budget",
                      f"spent=${spent}")
            else:
                # Beyond the safety margin the pool cannot prevent an overrun,
                # but it must stay bounded by what is in flight rather than
                # running away across all 12 shards.
                check(spent <= 1.00 * 1.5,
                      f"{factor}x overshoot (beyond margin) stays bounded",
                      f"spent=${spent} of $1.00")
            check(len(agg["shards"]) == 12,
                  f"{factor}x overshoot still accounts for every shard",
                  str(len(agg["shards"])))

        print("== a prompt that looks like a flag cannot strip the ceiling ==")
        # End-to-end version of the wrapper's fail-open fix: the orchestrator
        # passes prompts as argv, so a prompt equal to a flag name must not be
        # read as one.
        probe = tmp / "stub-echo"
        probe.write_text(
            "#!/usr/bin/env python3\n"
            "import json,sys\n"
            "argv=sys.argv[1:]\n"
            "cap=None\n"
            "for i,a in enumerate(argv):\n"
            "    if a=='--max-budget-usd': cap=argv[i+1]\n"
            "print(json.dumps({'type':'result','subtype':'success',"
            "'is_error':False,'terminal_reason':'completed','total_cost_usd':0.01,"
            "'num_turns':1,'permission_denials':[],'structured_output':"
            "{'summary':'ceiling seen was '+str(cap)+' which is long enough to pass the check',"
            "'findings':[]}}))\n")
        probe.chmod(0o755)
        # Two ways to supply such a prompt. A tasks file is the safe path --
        # its contents never reach argv -- and `--` covers the positional form.
        taskfile = tmp / "flagtasks.json"
        taskfile.write_text(json.dumps(["--max-budget-usd"]))
        for desc, argv in (
            ("via --tasks file", ["--tasks", str(taskfile)]),
            ("via positional after --", ["--", "--max-budget-usd"]),
        ):
            out = tmp / f"flagprompt-{_slug(desc)}"
            proc = subprocess.run(
                [sys.executable, str(FANOUT), "--budget-usd", "1.00",
                 "--out", str(out), "--json", *argv],
                capture_output=True, text=True,
                env=dict(os.environ, CLAUDE_FANOUT_WRAPPER=str(probe)))
            try:
                agg = json.loads(proc.stdout)
                env_txt = pathlib.Path(agg["shards"][0]["envelope"]).read_text()
            except Exception as exc:
                check(False, f"ceiling survives flag-shaped prompt {desc}",
                      f"{exc}; stderr={proc.stderr[-200:]}")
                continue
            check("ceiling seen was None" not in env_txt,
                  f"ceiling survives flag-shaped prompt {desc}", env_txt[:200])

        # Bare positional is a usage error, not a silently mangled run.
        proc = subprocess.run(
            [sys.executable, str(FANOUT), "--budget-usd", "1.00",
             "--out", str(tmp / "flagbare"), "--max-budget-usd"],
            capture_output=True, text=True,
            env=dict(os.environ, CLAUDE_FANOUT_WRAPPER=str(probe)))
        check(proc.returncode != 0,
              "flag-shaped bare positional fails loudly rather than running",
              f"rc={proc.returncode}")

        print("== interrupt terminates in-flight delegates ==")
        # The runaway this tool exists to prevent: without an explicit kill,
        # Ctrl-C tears down the thread pool but leaves every `claude` child
        # running and billing.
        import signal
        marker = tmp / "hangstub"
        marker.write_text(STUB)
        marker.chmod(0o755)
        out = tmp / "interrupt"
        proc = subprocess.Popen(
            [sys.executable, str(FANOUT), "--budget-usd", "1.00", "--jobs", "3",
             "--out", str(out), "HANG a", "HANG b", "HANG c"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=dict(os.environ, CLAUDE_FANOUT_WRAPPER=str(marker)))
        time.sleep(4)
        # `pgrep -c` is a GNU flag: BSD/macOS pgrep rejects it with a usage error and
        # prints nothing, which read as "no delegates running" and failed this check on
        # every Mac. Count the pids ourselves so the assertion means the same everywhere.
        def alive(pattern):
            out = subprocess.run(["pgrep", "-f", str(pattern)],
                                 capture_output=True, text=True).stdout
            return len([ln for ln in out.split() if ln.strip()])

        alive_before = alive(marker)
        proc.send_signal(signal.SIGINT)
        try:
            _, err = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, err = proc.communicate()
            err = (err or "") + " [orchestrator had to be killed]"
        time.sleep(1)
        alive_after = alive(marker)
        check(alive_before > 0,
              "delegates were actually running before the interrupt",
              f"pgrep count={alive_before!r}")
        check(alive_after == 0,
              "no delegate survives the interrupt",
              f"{alive_after} still alive — these would keep billing")
        check(proc.returncode == 130,
              "interrupted fan-out exits 130", f"rc={proc.returncode}")
        check("forfeit" in (err or "").lower(),
              "interrupt reports that spend is forfeited", (err or "")[-300:])

        print("== CLAUDE_FANOUT_RUN names the fan-out in each shard (packet a-s5 ruling 7) ==")
        fanrun = tmp / "fanrun"
        fanrun.write_text("#!/usr/bin/env python3\n"
                          "import json, os\n"
                          "print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False,\n"
                          "    'total_cost_usd': 0.01, 'num_turns': 1, 'permission_denials': [],\n"
                          "    'result': 'fanout=' + str(os.environ.get('CLAUDE_FANOUT_RUN'))}))\n")
        fanrun.chmod(0o755)
        proc = subprocess.run(
            [sys.executable, str(FANOUT), "--budget-usd", "1.00", "--profile", "explore",
             "--out", str(tmp / "fanrun-out"), "--json", "one", "two"],
            capture_output=True, text=True,
            env=dict(os.environ, CLAUDE_FANOUT_WRAPPER=str(fanrun), CLAUDE_FANOUT_RUN="outer-999"))
        try:
            agg = json.loads(proc.stdout)
            seen = [json.loads(pathlib.Path(sh["envelope"]).read_text())["result"] for sh in agg["shards"]]
        except Exception as exc:                        # noqa: BLE001
            agg, seen = {}, [f"unreadable: {exc}; {proc.stderr[-200:]}"]
        rid = agg.get("id") or ""
        check(len(seen) == 2 and all(x == f"fanout={rid}" for x in seen)
              and re.match(r"^\d{8}T\d{6}-\d+$", rid),
              "every shard sees CLAUDE_FANOUT_RUN=<the fan-out's run id>, not the caller's", f"id={rid} {seen}")

        print("== run artefacts ==")
        rc, agg = run(tmp, ["GOOD a"])
        rd = pathlib.Path(agg["run_dir"])
        check((rd / "fanout.json").exists(), "aggregate JSON is written")
        check(len(list(rd.glob("shard-*.json"))) == 1, "per-shard envelope kept")
        check(len(list(rd.glob("shard-*.err"))) == 1, "per-shard stderr kept")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
