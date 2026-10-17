#!/usr/bin/env python3
"""Tests for claude-api-agent's run dir, run.json and the stream-json fold (packet a-s5).

A fake `claude` (CLAUDE_API_AGENT_CLAUDE_BIN) prints canned stream-json: assistant
messages that repeat a message.id, tool_use blocks whose inputs carry planted secret
text, tool results, and a final result event. No key is used and no request is made.

    tests/test-apirun.py
"""
from __future__ import annotations

import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

REPO = pathlib.Path(__file__).resolve().parent.parent
WRAPPER = REPO / "bin" / "claude-api-agent"
AGENTS = REPO / "bin" / "claude-agents"

RUN_KEYS = {"id", "pid", "profile", "tags", "model", "started", "parent_session", "fanout", "state"}
END_KEYS = RUN_KEYS | {"rc", "ended"}
PROGRESS_KEYS = {"turns", "model", "last_tool", "last_tool_at", "usage", "cost_usd", "updated"}
ID_RE = re.compile(r"^\d{8}T\d{6}-\d+$")
SECRETS = ("SECRET-PROMPT-1a2b", "SECRET-INPUT-3c4d", "SECRET-THINK-5e6f", "SECRET-TEXT-7a8b",
           "SECRET-RESULT-9c0d", "SECRET-FINAL-e1f2", "SECRET-DENIED-a3b4", "SECRET-GREP-c5d6")

passed = failed = 0


def check(cond: bool, desc: str, detail: str = "") -> None:
    global passed, failed
    if cond:
        print(f"  PASS  {desc}")
        passed += 1
    else:
        print(f"  FAIL  {desc}\n     {detail}")
        failed += 1


def u(i, o, cr, cw):
    return {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr,
            "cache_creation_input_tokens": cw}


def asst(mid, model, usage, blocks, stop=None):
    return {"type": "assistant", "session_id": "sess-1", "parent_tool_use_id": None,
            "message": {"id": mid, "type": "message", "role": "assistant", "model": model,
                        "stop_reason": stop, "usage": usage, "content": blocks}}


def tres(text):
    return {"type": "user", "session_id": "sess-1", "parent_tool_use_id": None,
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": text}]}}


M = "claude-sonnet-5"
HEAD = [
    {"type": "system", "subtype": "init", "session_id": "sess-1", "model": M, "tools": ["Read"],
     "cwd": "/tmp/x"},
    asst("msg_1", M, u(10, 5, 100, 50), [{"type": "thinking", "thinking": "SECRET-THINK-5e6f"}]),
    asst("msg_1", M, u(10, 7, 100, 50), [{"type": "tool_use", "id": "toolu_1", "name": "Read",
                                          "input": {"file_path": "/x/SECRET-INPUT-3c4d"}}],
         stop="tool_use"),
    tres("SECRET-RESULT-9c0d"),
]
TAIL = [
    asst("msg_2", M, u(20, 9, 300, 0), [{"type": "tool_use", "id": "toolu_2", "name": "Grep",
                                         "input": {"pattern": "SECRET-GREP-c5d6"}}], stop="tool_use"),
    tres("SECRET-RESULT-9c0d"),
    asst("msg_3", M, u(30, 40, 400, 0), [{"type": "text", "text": "SECRET-TEXT-7a8b"}], stop="end_turn"),
]
RESULT = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 1234,
          "num_turns": 3, "result": "SECRET-FINAL-e1f2", "session_id": "sess-1",
          "total_cost_usd": 0.0123, "terminal_reason": "completed",
          "usage": u(60, 56, 800, 50),
          "modelUsage": {M: {"inputTokens": 60, "outputTokens": 56, "cacheReadInputTokens": 800,
                             "cacheCreationInputTokens": 50, "costUSD": 0.0123}},
          "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": "SECRET-DENIED-a3b4"}}]}

# FAKE_MODE: ok | crash (no result, rc 3) | crash0 (no result, rc 0) | slow (waits for $FAKE_GO
# between HEAD and TAIL) | rc7 (the whole stream, then rc 7). Under --output-format json (the
# old profile flags, or a pass-through caller) it prints the result envelope only.
FAKE = r"""#!/usr/bin/python3
import json, os, sys, time
argv = sys.argv[1:]
with open(os.environ["FAKE_ARGV"], "w") as f:
    json.dump(argv, f)
sys.stdin.read() if not sys.stdin.isatty() else None
spec = json.load(open(os.environ["FAKE_SPEC"]))
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "sleep":                 # waits to be signalled; a survivor prints late and leaves a mark
    with open(os.environ["FAKE_PIDFILE"], "w") as f:
        f.write(str(os.getpid()))
    time.sleep(8)
    open(os.environ["FAKE_PIDFILE"] + ".survived", "w").write("1")
    print("LATE OUTPUT")
    sys.exit(0)
end = os.environ.get("FAKE_END", "\n")
fmt = None
for i, a in enumerate(argv):
    if a == "--output-format" and i + 1 < len(argv):
        fmt = argv[i + 1]
    elif a.startswith("--output-format="):
        fmt = a.split("=", 1)[1]
def out(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()
if fmt == "stream-json":
    for e in spec["head"]:
        out(e)
    if mode == "slow":
        go = os.environ["FAKE_GO"]
        for _ in range(200):
            if os.path.exists(go):
                break
            time.sleep(0.05)
    for e in spec["tail"]:
        out(e)
    if mode == "crash":
        sys.exit(3)
    if mode == "crash0":
        sys.exit(0)
    sys.stdout.write(json.dumps(spec["result"]) + end)
    sys.stdout.flush()
    sys.exit(7 if mode == "rc7" else 0)
elif fmt == "json":
    if mode in ("crash", "crash0"):
        sys.exit(3 if mode == "crash" else 0)
    out(spec["result"])
    sys.exit(7 if mode == "rc7" else 0)
else:
    print("plain text answer")
"""


def load_costs():
    loader = importlib.machinery.SourceFileLoader("claude_costs", str(REPO / "bin" / "claude-costs"))
    spec = importlib.util.spec_from_loader("claude_costs", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class World:
    def __init__(self, root: pathlib.Path):
        self.root = root
        self.state = root / "state"
        self.log = self.state / "claude-api-agent" / "usage.jsonl"
        self.runs = self.state / "claude-api-agent" / "runs"
        self.fake = root / "fake-claude"
        self.fake.write_text(FAKE)
        self.fake.chmod(0o755)
        self.spec = root / "spec.json"
        self.spec.write_text(json.dumps({"head": HEAD, "tail": TAIL, "result": RESULT}))
        self.argv = root / "argv.json"
        self.pin = root / "pin.conf"
        self.pin.write_text("")

    def env(self, **kw) -> dict:
        drop = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_FANOUT_RUN", "CLAUDE_API_AGENT_NO_LOG",
                "CLAUDE_API_AGENT_TAGS", "CLAUDE_API_AGENT_BUDGET_USD", "HTTPS_PROXY", "https_proxy",
                "ALL_PROXY", "all_proxy", "CLAUDE_API_AGENT_EXPECTED_PROXY")
        e = {k: v for k, v in os.environ.items() if k not in drop}
        e.update({"HOME": str(self.root), "XDG_STATE_HOME": str(self.state),
                  "CLAUDE_API_AGENT_LOG": str(self.log), "CLAUDE_API_AGENT_CLAUDE_BIN": str(self.fake),
                  "CLAUDE_API_AGENT_PROXY_PIN_FILE": str(self.pin), "ANTHROPIC_API_KEY": "sk-an" "t-test-fake",
                  "FAKE_ARGV": str(self.argv), "FAKE_SPEC": str(self.spec), "FAKE_MODE": "ok"})
        for k, v in kw.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = str(v)
        return e

    def run(self, args, timeout=60, **kw) -> subprocess.CompletedProcess:
        try:
            return subprocess.run([str(WRAPPER), *args], capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL, env=self.env(**kw), timeout=timeout)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args, 124, "", "timed out")

    def dirs(self) -> list:
        if not self.runs.is_dir():
            return []
        return sorted(p for p in self.runs.iterdir() if p.is_dir())

    def argv_seen(self) -> list:
        try:
            return json.loads(self.argv.read_text())
        except (OSError, ValueError):
            return []

    def usage_rows(self) -> list:
        try:
            return [json.loads(ln) for ln in self.log.read_text().splitlines() if ln.strip()]
        except OSError:
            return []


def jload(p: pathlib.Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def all_text(d: pathlib.Path) -> str:
    out = []
    for p in d.rglob("*"):
        if p.is_file():
            out.append(p.read_text(errors="replace"))
    return "\n".join(out)


def expected_cost() -> float | None:
    try:
        c = load_costs()
    except Exception:                                   # noqa: BLE001
        return None
    tot = 0.0
    for i, o, cr, cw in ((10, 7, 100, 50), (20, 9, 300, 0), (30, 40, 400, 0)):
        tot += c.predicted_cost(M, {"in": i, "out": o, "cr": cr, "cw": cw})
    return tot


def profile_checks(w: World) -> None:
    print("== a profile run: stdout, usage.jsonl and the argv are what they were ==")
    p = w.run(["--tag", "id=t1", "--tag", "phase=fix", "--profile", "explore", "-p", "SECRET-PROMPT-1a2b"],
              CLAUDE_CODE_SESSION_ID="seat-abc", CLAUDE_FANOUT_RUN="20261013T000000-42")
    check(p.returncode == 0, "the run exits 0", f"rc={p.returncode} err={p.stderr[-300:]}")
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    env = None
    try:
        env = json.loads(p.stdout)
    except ValueError:
        pass
    check(len(lines) == 1 and env == RESULT, "stdout is the one result envelope, as --output-format json gave",
          p.stdout[:300])
    argv = w.argv_seen()
    fmts = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--output-format"]
    check(fmts == ["stream-json"] and "--verbose" in argv,
          "profile mode asks for --output-format stream-json --verbose", str(fmts))
    rows = w.usage_rows()
    check(len(rows) == 1 and rows[0].get("cost_usd") == 0.0123 and rows[0].get("turns") == 3
          and rows[0].get("tags") == {"id": "t1", "phase": "fix"},
          "usage.jsonl gets its one row from the result event", str(rows)[:300])

    print("== run.json (rulings 1, 2) ==")
    ds = w.dirs()
    check(len(ds) == 1 and ID_RE.match(ds[0].name or ""), "one run dir, named <UTC stamp>-<pid>",
          str([d.name for d in ds]))
    if not ds:
        return
    d = ds[0]
    check(stat.S_IMODE(d.stat().st_mode) == 0o700, "the run dir is mode 0700", oct(d.stat().st_mode))
    rj = jload(d / "run.json") or {}
    check(set(rj) == END_KEYS, "run.json carries exactly the ruled keys, plus rc and ended", str(sorted(rj)))
    check(rj.get("id") == d.name and isinstance(rj.get("pid"), int) and rj.get("profile") == "explore"
          and rj.get("tags") == {"id": "t1", "phase": "fix"} and rj.get("model") == M,
          "id, pid, profile, tags and model", str(rj))
    check(rj.get("parent_session") == "seat-abc" and rj.get("fanout") == "20261013T000000-42",
          "parent_session is $CLAUDE_CODE_SESSION_ID; fanout is $CLAUDE_FANOUT_RUN", str(rj))
    check(rj.get("state") == "done" and rj.get("rc") == 0 and isinstance(rj.get("ended"), str)
          and isinstance(rj.get("started"), str) and rj["started"] <= rj["ended"],
          "at exit: state done, rc 0, ended", str(rj))
    try:
        t = dt.datetime.strptime(d.name[:15], "%Y%m%dT%H%M%S").replace(tzinfo=dt.timezone.utc)
        skew = abs((dt.datetime.now(dt.timezone.utc) - t).total_seconds())
    except ValueError:
        skew = None
    check(skew is not None and skew < 300, "the id's stamp is UTC", f"{d.name} skew={skew}")

    print("== progress.json (rulings 3, 4) ==")
    pj = jload(d / "progress.json") or {}
    check(set(pj) == PROGRESS_KEYS, "progress.json carries exactly the ruled keys", str(sorted(pj)))
    check(pj.get("turns") == 3, "turns count distinct message ids (msg_1 twice is one)", str(pj.get("turns")))
    check(pj.get("model") == M and pj.get("last_tool") == "Grep" and isinstance(pj.get("last_tool_at"), str),
          "model and the newest tool_use's name and time", str(pj))
    check(pj.get("usage") == {"in": 30, "out": 40, "cr": 400, "cw": 0},
          "usage is the newest message's, so status reads its context from it", str(pj.get("usage")))
    want = expected_cost()
    got = pj.get("cost_usd")
    check(want is not None and isinstance(got, (int, float)) and abs(got - round(want, 6)) < 1e-9,
          "cost_usd is predicted_cost over each message.id once", f"got={got} want={want}")
    try:
        c = load_costs()
        double = want + c.predicted_cost(M, {"in": 10, "out": 5, "cr": 100, "cw": 50})
    except Exception:                                   # noqa: BLE001
        double = None
    check(double is not None and isinstance(got, (int, float)) and abs(got - double) > 1e-9,
          "a repeated message.id is not counted twice", f"got={got} double={double}")

    print("== no content in the run dir (ruling 4) ==")
    text = all_text(d)
    leaked = [s for s in SECRETS if s in text]
    check(not leaked, "no prompt, thinking, text, tool input, tool result or result text in the run dir",
          str(leaked))
    check(sorted(x.name for x in d.iterdir()) == ["progress.json", "run.json"],
          "the run dir holds run.json and progress.json only", str([x.name for x in d.iterdir()]))
    modes = {x.name: oct(stat.S_IMODE(x.stat().st_mode)) for x in d.iterdir()}
    check(set(modes.values()) == {"0o600"}, "every file in the run dir is 0600, run.json after run_end too (A F2)",
          str(modes))

    print("== the envelope keeps the result line's own bytes (A F4) ==")
    p = w.run(["--profile", "explore", "--no-stdin", "-p", "hi"], FAKE_END="")
    check(p.returncode == 0 and p.stdout == json.dumps(RESULT), "no trailing newline in, none out",
          repr(p.stdout[-20:]))


def running_checks(w: World) -> None:
    print("== run.json is written before the child starts, and progress while it runs ==")
    go = w.root / "go"
    before = set(w.dirs())
    proc = subprocess.Popen([str(WRAPPER), "--profile", "review", "--no-stdin", "-p", "SECRET-PROMPT-1a2b"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=w.env(FAKE_MODE="slow", FAKE_GO=go))
    rj = pj = None
    d = None
    live = False
    ino_mid = None
    deadline = time.time() + 15
    while time.time() < deadline:
        new = [x for x in w.dirs() if x not in before]
        if new:
            d = new[0]
            pj = jload(d / "progress.json")
            # a-s13: the message's write (turns 1) can land before its tool's; wait for both
            if pj and pj.get("turns") == 1 and pj.get("last_tool"):
                rj = jload(d / "run.json")
                live = proc.poll() is None
                ino_mid = (d / "run.json").stat().st_ino
                break
        time.sleep(0.05)
    go.write_text("")
    try:
        out, err = proc.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    rj = rj or {}
    check(rj.get("state") == "running" and "rc" not in rj and "ended" not in rj,
          "mid-run: run.json reads running, with no rc or ended", str(rj))
    check(rj.get("pid") == proc.pid and live, "mid-run: run.json's pid is the live wrapper's",
          f"pid={rj.get('pid')} wrapper={proc.pid} live={live}")
    check(bool(pj) and pj.get("turns") == 1 and pj.get("last_tool") == "Read",
          "mid-run: progress.json shows the first message and its tool while the stream pauses", str(pj))
    check(proc.returncode == 0 and json.loads(out or "null") == RESULT, "the slow run still ends with the envelope",
          f"rc={proc.returncode} {out[:200]}")
    end = jload(d / "run.json") if d else {}
    check((end or {}).get("state") == "done", "and run.json reads done after it", str(end))
    ino_after = (d / "run.json").stat().st_ino if d else None
    check(ino_mid is not None and ino_after is not None and ino_mid != ino_after,
          "run.json's exit rewrite is a new file renamed into place (B F3)", f"{ino_mid} -> {ino_after}")


def crash_checks(w: World) -> None:
    print("== a crash: no result event (ruling 3) ==")
    n0 = len(w.usage_rows())
    before = set(w.dirs())
    p = w.run(["--profile", "explore", "--no-stdin", "-p", "hi"], FAKE_MODE="crash")
    new = [x for x in w.dirs() if x not in before]
    rj = jload(new[0] / "run.json") if new else {}
    check(p.returncode == 3, "the child's exit code passes through (PIPESTATUS)", f"rc={p.returncode}")
    check(p.stdout == "", "stdout gets nothing, as before", repr(p.stdout[:200]))
    check(len(w.usage_rows()) == n0, "no usage.jsonl row", str(len(w.usage_rows())))
    check((rj or {}).get("state") == "failed" and (rj or {}).get("rc") == 3, "run.json reads failed, rc 3",
          str(rj))
    pj = jload(new[0] / "progress.json") if new else None
    check(bool(pj) and pj.get("turns") == 3, "progress.json holds what the stream got to", str(pj))

    before = set(w.dirs())
    p = w.run(["--profile", "explore", "--no-stdin", "-p", "hi"], FAKE_MODE="crash0")
    new = [x for x in w.dirs() if x not in before]
    rj = jload(new[0] / "run.json") if new else {}
    check(p.returncode == 0 and p.stdout == "" and (rj or {}).get("state") == "failed"
          and (rj or {}).get("rc") == 0,
          "rc 0 with no result event: stdout empty, run.json failed with rc 0", f"rc={p.returncode} {rj}")

    before = set(w.dirs())
    p = w.run(["--profile", "explore", "--no-stdin", "-p", "hi"], FAKE_MODE="rc7")
    new = [x for x in w.dirs() if x not in before]
    rj = jload(new[0] / "run.json") if new else {}
    check(p.returncode == 7 and json.loads(p.stdout or "null") == RESULT
          and (rj or {}).get("state") == "failed" and (rj or {}).get("rc") == 7,
          "a result then rc 7: the envelope prints, rc 7, run.json failed", f"rc={p.returncode} {rj}")


def passthrough_checks(w: World) -> None:
    print("== pass-through mode writes run.json only (ruling 5) ==")
    for desc, args, want_out in (
            ("--output-format json", ["--output-format", "json", "-p", "SECRET-PROMPT-1a2b"], RESULT),
            ("text", ["-p", "SECRET-PROMPT-1a2b"], None)):
        before = set(w.dirs())
        p = w.run(args, CLAUDE_CODE_SESSION_ID="seat-xyz")
        new = [x for x in w.dirs() if x not in before]
        rj = jload(new[0] / "run.json") if new else {}
        argv = w.argv_seen()
        if want_out is not None:
            ok_out = json.loads(p.stdout or "null") == want_out
        else:
            ok_out = p.stdout == "plain text answer\n"
        check(p.returncode == 0 and ok_out, f"pass-through {desc}: stdout unchanged", p.stdout[:200])
        check("stream-json" not in argv and "--verbose" not in argv,
              f"pass-through {desc}: the caller's flags, no stream", str(argv))
        check(len(new) == 1 and (rj or {}).get("state") == "done" and (rj or {}).get("profile") is None
              and (rj or {}).get("parent_session") == "seat-xyz" and (rj or {}).get("model") is None,
              f"pass-through {desc}: run.json done, profile and model null", str(rj))
        check(bool(new) and not (new[0] / "progress.json").exists(), f"pass-through {desc}: no progress.json",
              str([x.name for x in new[0].iterdir()]) if new else "no dir")
        leaked = [s for s in SECRETS if new and s in all_text(new[0])]
        check(not leaked, f"pass-through {desc}: no prompt in run.json", str(leaked))

    print("== CLAUDE_API_AGENT_NO_LOG writes no run dir ==")
    before = set(w.dirs())
    p = w.run(["--profile", "explore", "--no-stdin", "-p", "hi"], CLAUDE_API_AGENT_NO_LOG="1")
    argv = w.argv_seen()
    fmts = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--output-format"]
    check(p.returncode == 0 and set(w.dirs()) == before and fmts == ["json"]
          and json.loads(p.stdout or "null") == RESULT,
          "NO_LOG: no run dir, the old json flags, the envelope on stdout", f"rc={p.returncode} {fmts}")


def prune_checks(w: World) -> None:
    print("== pruning at launch (ruling 6) ==")
    now = dt.datetime.now(dt.timezone.utc)

    def iso(days):
        return (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    dead = subprocess.Popen(["/usr/bin/true"])
    dead.wait()
    plant = {
        "20260101T000000-11": {"state": "done", "rc": 0, "started": iso(9), "ended": iso(8), "pid": 11},
        "20260101T000000-12": {"state": "failed", "rc": 1, "started": iso(9), "ended": iso(8), "pid": 12},
        "20260101T000000-13": {"state": "done", "rc": 0, "started": iso(7), "ended": iso(6), "pid": 13},
        "20260101T000000-14": {"state": "running", "started": iso(9), "pid": os.getpid()},
        "20260101T000000-15": {"state": "running", "started": iso(9), "pid": dead.pid},
        "20260101T000000-16": {"state": "running", "started": iso(6), "pid": dead.pid},
        "not-a-run": {"state": "done", "rc": 0, "started": iso(30), "ended": iso(30), "pid": 1},
    }
    w.runs.mkdir(parents=True, exist_ok=True)
    for name, obj in plant.items():
        (w.runs / name).mkdir(mode=0o700, exist_ok=True)
        (w.runs / name / "run.json").write_text(json.dumps(dict(obj, id=name)))
    p = w.run(["--profile", "explore", "--no-stdin", "-p", "hi"])
    left = {x.name for x in w.dirs()}
    check(p.returncode == 0, "the pruning run exits 0", f"rc={p.returncode} {p.stderr[-200:]}")
    check("20260101T000000-11" not in left and "20260101T000000-12" not in left,
          "done and failed runs that ended over 7 days ago are removed", str(sorted(left)))
    check("20260101T000000-13" in left, "a run that ended 6 days ago is kept", str(sorted(left)))
    check("20260101T000000-14" in left, "a running dir whose pid is live is kept, however old",
          str(sorted(left)))
    check("20260101T000000-15" not in left, "a running dir whose pid is gone, started over 7 days ago, goes (B N2)",
          str(sorted(left)))
    check("20260101T000000-16" in left, "a running dir whose pid is gone, started 6 days ago, is kept",
          str(sorted(left)))
    check("not-a-run" in left, "a dir not named like a run id is never touched", str(sorted(left)))
    rj = jload(w.runs / "20260101T000000-16" / "run.json") or {}
    check(rj.get("state") == "running", "a kept running dir with a dead pid is left as written", str(rj))


def fold_checks(w: World) -> None:
    print("== claude-agents fold on its own ==")
    d = w.root / "folddir"
    d.mkdir(mode=0o700)
    feed = "".join(json.dumps(e) + "\n" for e in HEAD + TAIL)
    feed = "not json\n[1,2]\n\n" + feed + '{"type":"assistant","message":"x"}\n' + json.dumps(RESULT) + "\n"
    p = subprocess.run([str(AGENTS), "fold", "--run-dir", str(d)], input=feed, capture_output=True, text=True,
                       timeout=30)
    check(p.returncode == 0, "the fold exits 0 on garbage lines", f"rc={p.returncode} {p.stderr[-300:]}")
    check(json.loads(p.stdout or "null") == RESULT and p.stdout.count("\n") == 1,
          "its stdout is the result event, one line", p.stdout[:200])
    pj = jload(d / "progress.json") or {}
    check(pj.get("turns") == 3 and pj.get("last_tool") == "Grep",
          "the last event's progress is written", str(pj))
    check(sorted(x.name for x in d.iterdir()) == ["progress.json"], "it writes progress.json and no temp file",
          str([x.name for x in d.iterdir()]))
    big = "".join(json.dumps(asst(f"msg_{i}", M, u(1, 1, 0, 0), [])) + "\n" for i in range(3000))
    t0 = time.time()
    p = subprocess.run([str(AGENTS), "fold", "--run-dir", str(d)], input=big, capture_output=True, text=True,
                       timeout=60)
    pj = jload(d / "progress.json") or {}
    check(p.returncode == 0 and p.stdout == "" and pj.get("turns") == 3000,
          "3000 events, no result: nothing on stdout, the last event's count written",
          f"rc={p.returncode} turns={pj.get('turns')} in {time.time() - t0:.1f}s")


def fold_more_checks(w: World) -> None:
    print("== the fold keeps the result line's bytes (A F4) ==")
    line = json.dumps(RESULT).encode()
    for end in (b"\n", b"", b"\r\n"):
        d = w.root / f"fold-end-{len(end)}"
        d.mkdir(mode=0o700)
        p = subprocess.run([str(AGENTS), "fold", "--run-dir", str(d)], input=b'{"type":"system"}\n' + line + end,
                           capture_output=True, timeout=30)
        check(p.stdout == line + end, f"result line ending {end!r}: stdout is the line's own bytes", repr(p.stdout[-6:]))

    print("== names: a safe charset, at most 80 characters, else ? (A F3) ==")
    d = w.root / "fold-names"
    d.mkdir(mode=0o700)
    ev = [{"type": "system", "subtype": "init", "model": "ZQX-INIT tail"},
          asst("m1", "claude-x\nZQX-MODEL", u(1, 1, 0, 0),
               [{"type": "tool_use", "id": "t", "name": "Read\x1b]0;ZQX\x07", "input": {}}])]
    subprocess.run([str(AGENTS), "fold", "--run-dir", str(d)], input="".join(json.dumps(e) + "\n" for e in ev),
                   capture_output=True, text=True, timeout=30)
    pj = jload(d / "progress.json") or {}
    check(pj.get("model") == "?" and pj.get("last_tool") == "?", "a model or tool name outside the charset is ?",
          str(pj))
    d2 = w.root / "fold-names2"
    d2.mkdir(mode=0o700)
    ev = [asst("m1", "m" * 81, u(1, 1, 0, 0), [{"type": "tool_use", "id": "t", "name": "mcp__srv__x", "input": {}}])]
    subprocess.run([str(AGENTS), "fold", "--run-dir", str(d2)], input="".join(json.dumps(e) + "\n" for e in ev),
                   capture_output=True, text=True, timeout=30)
    pj = jload(d2 / "progress.json") or {}
    check(pj.get("model") == "?" and pj.get("last_tool") == "mcp__srv__x",
          "an 81-character model is ?; an MCP tool name stays", str(pj))

    print("== the fold writes at most once a second, each time a new file renamed into place (B F2, B F3) ==")
    d = w.root / "fold-throttle"
    d.mkdir(mode=0o700)
    proc = subprocess.Popen([str(AGENTS), "fold", "--run-dir", str(d)], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    seen, snap = set(), d / "snap.json"
    for i in range(30):
        proc.stdin.write((json.dumps(asst(f"m{i}", M, u(1, 1, 0, 0), [])) + "\n").encode())
        proc.stdin.flush()
        t_end = time.time() + 0.05
        while time.time() < t_end:
            try:
                seen.add(json.loads((d / "progress.json").read_text()).get("turns"))
                if not snap.exists():
                    os.link(d / "progress.json", snap)      # a second name for the first write's file
            except (OSError, ValueError):
                pass
            time.sleep(0.003)
    proc.stdin.close()
    proc.wait(timeout=30)
    final = (jload(d / "progress.json") or {}).get("turns")
    check(final == 30 and len(seen) <= 4, "30 events over 1.5 s: at most a write a second, and the last one",
          f"final={final} turns seen={sorted(x for x in seen if x is not None)}")
    first = (jload(snap) or {}).get("turns")
    check(first is not None and first < 30, "each write is a new file renamed into place, not a rewrite in place "
          "(a hard link to the first write still reads the first write)", f"first={first} final={final}")


def signal_checks(w: World) -> None:
    print("== a signal to the wrapper reaches the child (A F1, B F1) ==")
    cases = (("profile", ["--profile", "explore", "--no-stdin", "-p", "SECRET-PROMPT-1a2b"], signal.SIGTERM),
             ("pass-through", ["-p", "hi", "--output-format", "text"], signal.SIGTERM),
             ("pass-through", ["-p", "hi", "--output-format", "text"], signal.SIGHUP),
             ("profile", ["--profile", "explore", "--no-stdin", "-p", "hi"], signal.SIGINT))
    for desc, args, sig in cases:
        pidf = w.root / f"sleep-{desc}-{sig.name}.pid"
        before = set(w.dirs())
        proc = subprocess.Popen([str(WRAPPER), *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=w.env(FAKE_MODE="sleep", FAKE_PIDFILE=pidf))
        child = None
        for _ in range(200):
            try:
                child = int(pidf.read_text())
                break
            except (OSError, ValueError):
                time.sleep(0.02)
        proc.send_signal(sig)
        try:
            out, _err = proc.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _err = proc.communicate()
        alive = False
        if child:
            try:
                os.kill(child, 0)
                alive = True
            except OSError:
                alive = False
        new = [x for x in w.dirs() if x not in before]
        rj = jload(new[0] / "run.json") if new else {}
        want = 128 + int(sig)
        check(child is not None and not alive, f"{desc} {sig.name}: the child is gone when the wrapper exits",
              f"child={child} alive={alive}")
        check(proc.returncode == want and out == b"", f"{desc} {sig.name}: the wrapper exits {want}, stdout empty",
              f"rc={proc.returncode} out={out[:60]!r}")
        check((rj or {}).get("state") == "failed" and (rj or {}).get("rc") == want,
              f"{desc} {sig.name}: run.json reads failed, rc {want}", str(rj))
        if alive:
            os.kill(child, signal.SIGKILL)
    time.sleep(0.2)
    check(not list(w.root.glob("sleep-*.survived")), "no child ran on after its wrapper was signalled",
          str(list(w.root.glob("sleep-*.survived"))))


def foldfail_checks(w: World) -> None:
    print("== a fold that exits non-zero under a child that exits 0 (B N1) ==")
    repo = w.root / "foldfail"
    (repo / "bin").mkdir(parents=True)
    shutil.copy2(WRAPPER, repo / "bin" / "claude-api-agent")
    bad = repo / "bin" / "claude-agents"
    bad.write_text("#!/bin/sh\ncat >/dev/null\nexit 3\n")
    bad.chmod(0o755)
    before = set(w.dirs())
    p = subprocess.run([str(repo / "bin" / "claude-api-agent"), "--profile", "explore", "--no-stdin", "-p", "hi"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, env=w.env(), timeout=60)
    new = [x for x in w.dirs() if x not in before]
    rj = jload(new[0] / "run.json") if new else {}
    check(p.returncode == 1 and "fold" in p.stderr and p.stdout == "",
          "the wrapper says so on stderr and exits 1", f"rc={p.returncode} err={p.stderr[-200:]!r}")
    check((rj or {}).get("state") == "failed" and (rj or {}).get("rc") == 1, "run.json reads failed, rc 1", str(rj))


def hermetic_checks(w: World) -> None:
    print("== test-run-path.sh never writes a caller's CLAUDE_API_AGENT_LOG (B N3) ==")
    sentinel = w.root / "caller-log" / "usage.jsonl"
    env = dict(os.environ, CLAUDE_API_AGENT_LOG=str(sentinel))
    p = subprocess.run(["bash", str(REPO / "tests" / "test-run-path.sh")], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=env, timeout=300)
    check(p.returncode == 0 and not sentinel.parent.exists(),
          "a caller's exported log path is left alone", f"rc={p.returncode} exists={sentinel.parent.exists()}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        w = World(root)
        profile_checks(w)
        running_checks(w)
        crash_checks(w)
        passthrough_checks(w)
        prune_checks(w)
        fold_checks(w)
        fold_more_checks(w)
        signal_checks(w)
        foldfail_checks(w)
        hermetic_checks(w)
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
