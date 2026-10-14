#!/usr/bin/python3
"""Tests for claude-agents status.

Runs against a synthetic session-plugin state dir, a synthetic Claude Code
projects dir and a synthetic agentroute ledger, so it reads nothing of this
machine's real sessions, starts nothing and spends nothing.

    tests/test-status.py
"""
from __future__ import annotations

import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
TOOL = REPO / "bin" / "claude-agents"

passed = failed = 0

FIELDS = {"id", "session_id", "agent_id", "parent", "lane", "model", "started", "elapsed_s",
          "turns", "context", "window", "cost_usd", "last_tool", "last_tool_at", "state", "what"}
SECRETS = ("SECRET-PROMPT-7f3a", "SECRET-INPUT-91bc", "SECRET-RESULT-04de", "SECRET-TEXT-5e21",
           "SECRET-HELPER-PROMPT-aa10")

BUSY = "b0bb1e55-1111-4aaa-8aaa-000000000001"
IDLE = "1d1e5ea7-2222-4bbb-8bbb-000000000002"
OLD = "01d5ea70-3333-4ccc-8ccc-000000000003"
H1 = "a1aa1111beef0001"   # done via SubagentHandback, a repeated message.id
H2 = "b2bb2222beef0002"   # local per the ledger, busy, has a builders[] row
H3 = "c3cc3333beef0003"   # quiet, sonnet 5.5
H4 = "d4dd4444beef0004"   # end_turn, outside the window
LOCAL_MODEL = "qwen3.8:27b-mtp-q8_0"


def check(cond: bool, desc: str, detail: str = "") -> None:
    global passed, failed
    if cond:
        print(f"  PASS  {desc}")
        passed += 1
    else:
        print(f"  FAIL  {desc}\n     {detail}")
        failed += 1


NOW = time.time()


def iso(ago: float) -> str:
    t = dt.datetime.fromtimestamp(NOW - ago, dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def touch(path: pathlib.Path, ago: float) -> None:
    os.utime(path, (NOW - ago, NOW - ago))


def wjson(path: pathlib.Path, obj, ago: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))
    touch(path, ago)


def jl(path: pathlib.Path, rows: list, ago: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    touch(path, ago)


def user(ago, text, **kw):
    r = {"type": "user", "timestamp": iso(ago), "message": {"role": "user", "content": text}}
    r.update(kw)
    return r


def asst(ago, mid, model, usage, blocks, stop=None):
    return {"type": "assistant", "timestamp": iso(ago),
            "message": {"id": mid, "model": model, "role": "assistant", "stop_reason": stop,
                        "usage": usage, "content": blocks}}


def tool_use(name):
    return {"type": "tool_use", "id": "toolu_x", "name": name,
            "input": {"command": "echo SECRET-INPUT-91bc"}}


def tool_result(ago):
    return {"type": "user", "timestamp": iso(ago),
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_x", "content": "SECRET-RESULT-04de"}]}}


def u(i, o, cr, cw):
    return {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr,
            "cache_creation_input_tokens": cw}


def build(root: pathlib.Path) -> dict:
    """The synthetic world: three seats, four helpers, one ledger."""
    sessions = root / "state" / "agentik-session" / "sessions"
    proj = root / "projects" / "-Users-x-code-myproj"
    tpath = proj / f"{BUSY}.jsonl"
    # -- the busy seat: activity 5 s ago, newer than its turn end
    s = sessions / BUSY
    wjson(s / "meter.json", {
        "session_id": BUSY, "model": "claude-opus-5-5", "context": 80000, "window": 1000000,
        "turns": 12, "started": iso(600), "ts": iso(20),
        "transcript": {"path": str(tpath), "inode": 1, "size": 1, "offset": 1},
        "builders": [{"agent": H2, "turns": 7, "tokens": 99999, "max_context": 45000}]}, 20)
    wjson(s / "measure.json", {"at": iso(30), "context": {"tokens": 80000, "window": 1000000,
                                                           "percent": 8}, "cost": {"usd": 1.234}}, 30)
    wjson(s / "activity.json", {"event": "PreToolUse", "tool": "Bash", "at": NOW - 5}, 5)
    wjson(s / "turn-ended.json", {"at": NOW - 100}, 100)
    jl(tpath, [user(600, "SECRET-PROMPT-7f3a", cwd="/Users/x/code/myproj", sessionId=BUSY),
               asst(590, "msg_seat1", "claude-opus-5-5", u(10, 10, 0, 0),
                    [{"type": "text", "text": "SECRET-TEXT-5e21"}, tool_use("Bash")])], 5)
    sub = proj / BUSY / "subagents"
    # -- H1: done via SubagentHandback; msg_h1a spans two lines that repeat its id and usage
    m1 = u(1000, 2000, 100000, 10000)
    jl(sub / f"agent-{H1}.jsonl", [
        user(300, "SECRET-HELPER-PROMPT-aa10", cwd="/Users/x/code/myproj"),
        asst(290, "msg_h1a", "claude-opus-5-5", m1, [{"type": "text", "text": "SECRET-TEXT-5e21"}]),
        asst(289, "msg_h1a", "claude-opus-5-5", m1, [tool_use("Read")], stop="tool_use"),
        tool_result(288),
        asst(280, "msg_h1b", "claude-opus-5-5", u(10, 500, 120000, 0),
             [tool_use("SubagentHandback")], stop="tool_use"),
    ], 280)
    wjson(sub / f"agent-{H1}.meta.json", {
        "agentType": "general-purpose", "model": "opus", "toolUseId": "toolu_p1",
        "description": "Build the status verb and its tests for the a-s3 packet now"}, 280)
    # -- H2: local per the ledger, newest line 10 s ago
    jl(sub / f"agent-{H2}.jsonl", [
        user(400, "SECRET-HELPER-PROMPT-aa10"),
        asst(390, "msg_h2a", "claude-sonnet-5", u(500, 50, 0, 0), [tool_use("Grep")], stop="tool_use"),
        tool_result(10),
    ], 10)
    wjson(sub / f"agent-{H2}.meta.json", {"agentType": "Explore", "model": "sonnet",
                                          "description": "Survey the ledger"}, 10)
    # -- H3: quiet: newest line 600 s ago, file changed 60 s ago
    jl(sub / f"agent-{H3}.jsonl", [
        user(700, "SECRET-HELPER-PROMPT-aa10"),
        asst(600, "msg_h3a", "claude-sonnet-5-5", u(100, 100, 1000, 0), [tool_use("Read")],
             stop="tool_use"),
    ], 60)
    wjson(sub / f"agent-{H3}.meta.json", {"agentType": "general-purpose", "model": "sonnet",
                                          "description": "Read the meter"}, 60)
    # -- H4: done by end_turn two hours ago: outside the 30-min window
    jl(sub / f"agent-{H4}.jsonl", [
        user(7300, "SECRET-HELPER-PROMPT-aa10"),
        asst(7200, "msg_h4a", "claude-opus-5-5", u(1, 1, 0, 0),
             [{"type": "text", "text": "SECRET-TEXT-5e21"}], stop="end_turn"),
    ], 7200)
    wjson(sub / f"agent-{H4}.meta.json", {"agentType": "general-purpose", "model": "opus",
                                          "description": "An old helper"}, 7200)
    # -- the idle seat: its turn ended after its last tool; routed local as a whole;
    #    no window, a transcript path that does not exist
    s = sessions / IDLE
    wjson(s / "meter.json", {
        "session_id": IDLE, "model": "claude-sonnet-5", "context": 30000, "window": None,
        "turns": 3, "started": iso(1200), "ts": iso(200),
        "transcript": {"path": str(root / "projects" / "gone" / f"{IDLE}.jsonl")},
        "builders": []}, 200)
    wjson(s / "measure.json", {"at": iso(250), "cost": {"usd": 0.5}}, 250)
    wjson(s / "activity.json", {"event": "PostToolUse", "tool": "Edit", "at": NOW - 300}, 300)
    wjson(s / "turn-ended.json", {"at": NOW - 200}, 200)
    # -- the old seat: three hours ago, no activity.json, no measure.json
    s = sessions / OLD
    wjson(s / "meter.json", {
        "session_id": OLD, "model": "claude-opus-5-5", "context": 5000, "window": 200000,
        "turns": 1, "started": iso(11000), "ts": iso(10800),
        "transcript": {"path": str(root / "projects" / "gone" / f"{OLD}.jsonl")},
        "builders": []}, 10800)
    wjson(s / "turn-ended.json", {"at": NOW - 10800}, 10800)
    touch(s, 10800)
    # -- the ledger: H2 local; the idle seat local with no agent id; an upstream row
    #    for the busy seat (which must NOT make it local); a junk line
    ledger = root / "agentroute" / "requests.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("\n".join([
        json.dumps({"route": "upstream", "session_id": BUSY, "agent_id": None,
                    "model_out": "claude-opus-5-5", "status": 200}),
        json.dumps({"route": "local", "session_id": BUSY, "agent_id": H2, "parent_agent_id": None,
                    "model_out": LOCAL_MODEL, "status": 200, "wall_s": 3.0, "usage": u(500, 50, 0, 0)}),
        json.dumps({"route": "local", "session_id": IDLE, "agent_id": None,
                    "model_out": LOCAL_MODEL, "status": 200, "wall_s": 9.0}),
        "not json",
    ]) + "\n")
    w = {"sessions": sessions, "ledger": ledger}
    w.update(build_aux(root))
    w.update(build_bad(root))
    w.update(build_cap(root))
    w.update(build_api(root))
    # -- a ledger whose only row for H3 lies before its last 2 MB
    big = root / "big" / "requests.jsonl"
    big.parent.mkdir()
    filler = json.dumps({"route": "upstream", "session_id": "x", "pad": "p" * 200}) + "\n"
    with big.open("w") as f:
        f.write(json.dumps({"route": "local", "session_id": BUSY, "agent_id": H3,
                            "model_out": LOCAL_MODEL}) + "\n")
        f.write(filler * (2_200_000 // len(filler)))
        f.write(json.dumps({"route": "local", "session_id": BUSY, "agent_id": H2,
                            "model_out": LOCAL_MODEL}) + "\n")
    w["big"] = big
    w["empty"] = root / "empty-sessions"
    w["empty"].mkdir()
    return w


# the aux world (the fix round): liveness, busy rules, lanes, what, control characters
A_RECENT = "a0000001-0000-4000-8000-00000000000a"   # turn ended 10 s ago, activity 20 s ago
A_NOEND_B = "a0000002-0000-4000-8000-00000000000a"  # no turn-ended, activity 30 s ago
A_NOEND_Q = "a0000003-0000-4000-8000-00000000000a"  # no turn-ended, activity 600 s ago
A_HLIVE = "a0000004-0000-4000-8000-00000000000a"    # its own files 3 h old, a helper 30 s ago
A_MIXED = "a0000005-0000-4000-8000-00000000000a"    # a local and an upstream no-agent row
A_LONG = "a0000006-0000-4000-8000-00000000000a"     # a first line over 4 KB, cwd on line 2
A_NESTED = "a0000007-0000-4000-8000-00000000000a"   # a nested cwd before the top-level one
A_MIDDLE = "a0000008-0000-4000-8000-00000000000a"   # cwd only past 4 KB and before the last 64 KB
A_CTRL = "a0000009-0000-4000-8000-00000000000a"     # control characters in every text field
H5 = "e5ee5555beef0005"                              # A_HLIVE's helper
H6 = "f6ff6666beef0006"                              # A_CTRL's helper
NESTED_LEAK = "NESTED-CWD-LEAK-77"


def raw(path: pathlib.Path, text: str, ago: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    touch(path, ago)


def seat(sessions, proj, sid, ago, act=None, ended=None, tool="Read", transcript=None,
         measure=None, model="claude-opus-5-5"):
    s = sessions / sid
    tpath = proj / f"{sid}.jsonl"
    wjson(s / "meter.json", {"session_id": sid, "model": model, "context": 1000, "window": 200000,
                             "turns": 1, "started": iso(ago + 60), "ts": iso(ago),
                             "transcript": {"path": str(tpath)}, "builders": []}, ago)
    if act is not None:
        wjson(s / "activity.json", {"event": "PreToolUse", "tool": tool, "at": NOW - act}, act)
    if ended is not None:
        wjson(s / "turn-ended.json", {"at": NOW - ended}, ended)
    if measure is not None:
        wjson(s / "measure.json", {"at": iso(ago), "cost": {"usd": measure}}, ago)
    if transcript is not None:
        raw(tpath, transcript, ago)
    touch(s, ago)
    return tpath


def build_aux(root: pathlib.Path) -> dict:
    sessions = root / "aux" / "sessions"
    proj = root / "aux" / "projects" / "-p"
    top = lambda cwd, ago: json.dumps({"type": "user", "cwd": cwd, "timestamp": iso(ago),  # noqa: E731
                                       "message": {"role": "user", "content": "SECRET-PROMPT-7f3a"}}) + "\n"
    seat(sessions, proj, A_RECENT, 10, act=20, ended=10)
    seat(sessions, proj, A_NOEND_B, 30, act=30)
    seat(sessions, proj, A_NOEND_Q, 600, act=600)
    tp = seat(sessions, proj, A_HLIVE, 10800, act=10900, ended=10800)
    jl(tp.parent / A_HLIVE / "subagents" / f"agent-{H5}.jsonl", [
        user(200, "SECRET-HELPER-PROMPT-aa10"),
        asst(30, "msg_h5a", "claude-opus-5-5", u(1, 1, 0, 0), [tool_use("Grep")], stop="tool_use")], 30)
    seat(sessions, proj, A_MIXED, 100, act=100, ended=90, measure=0.75)
    snapshot_line = json.dumps({"type": "file-history-snapshot", "snapshot": {"pad": "s" * 5000}}) + "\n"
    seat(sessions, proj, A_LONG, 100, act=100, ended=90,
         transcript=snapshot_line + top("/Users/x/code/longproj", 100))
    nested = json.dumps({"type": "assistant", "timestamp": iso(100), "message": {
        "id": "m", "content": [{"type": "tool_use", "name": "Bash",
                                "input": {"cwd": f"/x/{NESTED_LEAK}"}}]}}) + "\n"
    seat(sessions, proj, A_NESTED, 100, act=100, ended=90,
         transcript=nested + top("/Users/x/code/realproj", 100))
    pad = "".join(json.dumps({"type": "progress", "pad": "q" * 700}) + "\n" for _ in range(100))
    seat(sessions, proj, A_MIDDLE, 100, act=100, ended=90,
         transcript=snapshot_line + top("/Users/x/code/midproj", 100) + pad)
    tp = seat(sessions, proj, A_CTRL, 100, act=100, ended=90, tool="Ba\nsh\x1b[2J",
              model="claude-\x1b[31mopus", transcript=top("/Users/x/code/ev\x1bil\nproj\x07", 100))
    jl(tp.parent / A_CTRL / "subagents" / f"agent-{H6}.jsonl", [
        user(100, "SECRET-HELPER-PROMPT-aa10"),
        asst(90, "msg_h6a", "claude-opus-5-5", u(1, 1, 0, 0), [tool_use("Re\nad\x1b]0;t\x07")],
             stop="tool_use")], 90)
    wjson(tp.parent / A_CTRL / "subagents" / f"agent-{H6}.meta.json",
          {"description": "Evil\x1b]0;title\x07\ndesc\u202e"}, 90)
    ledger = root / "aux" / "requests.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in [
        {"route": "local", "session_id": A_MIXED, "agent_id": None, "model_out": LOCAL_MODEL},
        {"route": "upstream", "session_id": A_MIXED, "agent_id": None, "model_out": "claude-opus-5-5"},
        {"route": "local", "session_id": A_HLIVE, "agent_id": f"agent-{H5}", "model_out": LOCAL_MODEL},
    ]) + "\n")
    return {"aux": sessions, "aux_ledger": ledger}


# the bad world (B F1): one bad value per seat; none may break the table
BAD = {name: f"b{i:07d}-0000-4000-8000-0000000000bb" for i, name in enumerate(
    ["builders", "turns", "act_ms", "act_nan", "started", "cost_nan", "meter_list", "garbage",
     "nul_path", "ended_str"], 1)}
H7 = "a7aa7777beef0007"                                  # the helper under BAD["builders"]


def build_bad(root: pathlib.Path) -> dict:
    sessions = root / "bad" / "sessions"
    proj = root / "bad" / "projects" / "-p"
    for name, sid in BAD.items():
        seat(sessions, proj, sid, 100, act=100, ended=90, measure=0.25)
    m = lambda sid: json.loads((sessions / sid / "meter.json").read_text())  # noqa: E731
    mb = m(BAD["builders"])
    mb["builders"] = 5
    raw(sessions / BAD["builders"] / "meter.json", json.dumps(mb), 100)
    raw(pathlib.Path(mb["transcript"]["path"]).parent / BAD["builders"] / "subagents" / f"agent-{H7}.jsonl",
        'not json\n{"type":"assistant"}\n[1,2]\n' + json.dumps(asst(
            40, "msg_h7", "claude-opus-5-5", u(10, 10, 0, 0), [tool_use("Grep")])) + "\n", 40)
    raw(sessions / BAD["turns"] / "meter.json",
        json.dumps(m(BAD["turns"])).replace('"turns": 1', '"turns": NaN')
        .replace('"context": 1000', '"context": -5').replace('"window": 200000', '"window": "big"'), 100)
    raw(sessions / BAD["act_ms"] / "activity.json", json.dumps({"tool": "Bash", "at": NOW * 1000}), 100)
    raw(sessions / BAD["act_nan"] / "activity.json", '{"tool": "Bash", "at": NaN}', 100)
    ms = m(BAD["started"])
    ms["started"] = 1e20
    raw(sessions / BAD["started"] / "meter.json", json.dumps(ms), 100)
    raw(sessions / BAD["cost_nan"] / "measure.json", '{"cost": {"usd": NaN}}', 100)
    raw(sessions / BAD["meter_list"] / "meter.json", "[]", 100)
    raw(sessions / BAD["garbage"] / "meter.json", "{not json", 100)
    mn = m(BAD["nul_path"])
    mn["transcript"]["path"] = "/tmp/a\u0000b.jsonl"
    raw(sessions / BAD["nul_path"] / "meter.json", json.dumps(mn), 100)
    raw(sessions / BAD["ended_str"] / "turn-ended.json", '{"at": "yesterday"}', 100)
    return {"bad": sessions}


def build_cap(root: pathlib.Path) -> dict:
    """55 seats, all in the window: --all lists the 50 newest."""
    sessions = root / "cap" / "sessions"
    for i in range(55):
        wjson(sessions / f"c{i:07d}-0000-4000-8000-0000000000cc" / "turn-ended.json",
              {"at": NOW - 10 - i}, 10 + i)
    return {"cap": sessions}


# the api world (packet a-s5): claude-api-agent's run dirs, lane api
R_LIVE = "20261013T100001-1001"    # running, its pid live, its parent the BUSY seat
R_DONE = "20261013T100002-1002"    # done 5 min ago, no parent, no progress.json
R_FAIL = "20261013T100003-1003"    # failed 2 min ago, a parent that is not listed
R_STALE = "20261013T100004-1004"   # running, its pid gone: failed, never rewritten
R_OLD = "20261013T100005-1005"     # done 2 h ago: only under --all
R_JUNK = "20261013T100006-1006"    # run.json is not JSON
R_ODD = "20261013T100007-1007"     # every field the wrong type
R_NAMES = "20261013T100008-1008"   # a model and a tool name outside the safe charset
API_SECRET = "SECRET-API-RESULT-55aa"


def build_api(root: pathlib.Path) -> dict:
    base = root / "apix" / "claude-api-agent"
    runs = base / "runs"
    dead = subprocess.Popen(["/usr/bin/true"])
    dead.wait()
    plant = {
        R_LIVE: ({"pid": os.getpid(), "profile": "explore", "tags": {"id": "t1", "phase": "fix"},
                  "model": "claude-sonnet-5", "started": iso(300), "parent_session": BUSY, "fanout": None,
                  "state": "running", "result": API_SECRET},
                 {"turns": 4, "model": "claude-sonnet-5", "last_tool": "Read", "last_tool_at": iso(20),
                  "usage": {"in": 100, "out": 5, "cr": 2000, "cw": 300}, "cost_usd": 0.05,
                  "updated": iso(20), "result": API_SECRET}, 20),
        R_DONE: ({"pid": 1002, "profile": "review", "tags": None, "model": "claude-opus-5",
                  "started": iso(600), "parent_session": None, "fanout": None, "state": "done", "rc": 0,
                  "ended": iso(300)}, None, 300),
        R_FAIL: ({"pid": 1003, "profile": "analyze", "tags": None, "model": "claude-opus-5",
                  "started": iso(400), "parent_session": "ffffffff-0000-4000-8000-unlisted0000",
                  "fanout": "20261013T090000-77", "state": "failed", "rc": 2, "ended": iso(120)},
                 {"turns": 2, "model": "claude-opus-5", "last_tool": "Grep", "last_tool_at": iso(130),
                  "usage": {"in": 10, "out": 1, "cr": 0, "cw": 0}, "cost_usd": 0.01, "updated": iso(130)}, 120),
        R_STALE: ({"pid": dead.pid, "profile": "explore", "tags": None, "model": "claude-sonnet-5",
                   "started": iso(200), "parent_session": None, "fanout": None, "state": "running"}, None, 100),
        R_OLD: ({"pid": 1005, "profile": "explore", "tags": None, "model": "claude-sonnet-5",
                 "started": iso(7300), "parent_session": None, "fanout": None, "state": "done", "rc": 0,
                 "ended": iso(7200)}, None, 7200),
    }
    for rid, (rj, pj, ago) in plant.items():
        wjson(runs / rid / "run.json", dict(rj, id=rid), ago)
        if pj is not None:
            wjson(runs / rid / "progress.json", pj, ago)
    raw(runs / R_JUNK / "run.json", "not json {", 10)
    wjson(runs / R_NAMES / "run.json", {"id": R_NAMES, "pid": 1008, "profile": "explore", "tags": None,
                                        "model": "claude x", "started": iso(90), "parent_session": None,
                                        "fanout": None, "state": "done", "rc": 0, "ended": iso(50)}, 50)
    wjson(runs / R_NAMES / "progress.json", {"turns": 1, "model": "claude-x\nZQX-LEAK", "last_tool": "t" * 81,
                                             "last_tool_at": iso(55), "usage": None, "cost_usd": 0}, 50)
    wjson(runs / R_ODD / "run.json", {"id": R_ODD, "pid": "abc", "profile": ["x"], "tags": "id=1",
                                      "model": 5, "started": "yesterday", "parent_session": [BUSY],
                                      "fanout": {}, "state": "done", "rc": "0", "ended": iso(60)}, 60)
    wjson(runs / R_ODD / "progress.json", {"turns": -1, "usage": {"in": "x", "cr": None},
                                           "cost_usd": "1", "last_tool": 7}, 60)
    return {"api_log": base / "usage.jsonl", "api_xdg": root / "apix", "api_runs": runs}


def api_checks(root: pathlib.Path, w: dict) -> None:
    print("== lane api: claude-api-agent's runs (packet a-s5) ==")
    env = env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["sessions"], AGENTROUTE_LOG=w["ledger"],
                  CLAUDE_API_AGENT_LOG=w["api_log"])
    p = run(["status", "--json"], env)
    doc = load(p) or {"agents": []}
    rows = {a.get("id"): a for a in doc["agents"]}
    ids = [a.get("id") for a in doc["agents"]]
    check(p.returncode == 0 and set(doc) == {"generated", "since_min", "agents"},
          "with run dirs, status --json exits 0 with the same top-level keys", f"rc={p.returncode}")
    bad = [sorted(set(a) ^ FIELDS) for a in doc["agents"] if set(a) != FIELDS]
    check(not bad, "an api row adds no field and renames none", str(bad))
    check(all(r in rows for r in (R_LIVE, R_DONE, R_FAIL, R_STALE)) and R_OLD not in rows and R_JUNK not in rows,
          "running runs and runs ended in the window are listed; an old or unreadable one is not", str(ids))
    lv = rows.get(R_LIVE, {})
    check(lv.get("lane") == "api" and lv.get("parent") == BUSY and lv.get("session_id") is None
          and lv.get("agent_id") is None and lv.get("state") == "busy",
          "a running run: lane api, parent its seat, busy", str(lv))
    check(lv.get("turns") == 4 and lv.get("model") == "claude-sonnet-5" and lv.get("last_tool") == "Read"
          and lv.get("cost_usd") == 0.05 and lv.get("context") == 2400 and lv.get("window") is None,
          "turns, model, last tool and cost from progress.json; context in+cr+cw over no window", str(lv))
    check(lv.get("what") == "explore id=t1 phase=fix", "what is the profile plus its tags", str(lv.get("what")))
    seats = [i for i in ids if rows[i].get("lane") in ("seat", "local") and not rows[i].get("agent_id")
             and not rows[i].get("parent")]
    check(all(x in ids for x in (BUSY, IDLE, R_LIVE)) and ids.index(BUSY) < ids.index(R_LIVE) < ids.index(IDLE)
          and all(rows[i].get("parent") == BUSY for i in ids[ids.index(BUSY) + 1:ids.index(R_LIVE) + 1]),
          "a run whose parent seat is listed nests under it, after its helpers", str(ids))
    last_seat = max(ids.index(s) for s in seats) if seats else -1
    check(all(ids.index(r) > last_seat for r in (R_DONE, R_FAIL, R_STALE) if r in ids),
          "a run with no listed parent is a top-level row after the seats", str(ids))
    dn, fl = rows.get(R_DONE, {}), rows.get(R_FAIL, {})
    check(dn.get("state") == "done" and dn.get("parent") is None and dn.get("turns") is None
          and dn.get("cost_usd") is None and dn.get("last_tool") is None and dn.get("context") is None
          and dn.get("what") == "review",
          "no progress.json: turns, cost, tool and context are null", str(dn))
    check(fl.get("state") == "failed" and fl.get("parent") == "ffffffff-0000-4000-8000-unlisted0000"
          and fl.get("last_tool") == "Grep", "a failed run with an unlisted parent: failed, parent kept", str(fl))
    od = rows.get(R_ODD, {})
    check(od.get("lane") == "api" and od.get("state") == "done" and od.get("parent") is None
          and od.get("model") is None and od.get("turns") is None and od.get("context") is None
          and od.get("what") is None and ids.index(R_ODD) > ids.index(IDLE),
          "a run.json of wrong types is a top-level row of nulls", str(od))
    nm = rows.get(R_NAMES, {})
    check(nm.get("model") == "?" and nm.get("last_tool") == "?",
          "an api row's model or tool name outside the safe charset or over 80 characters is ? (A F3)", str(nm))
    st = rows.get(R_STALE, {})
    disk = json.loads((w["api_runs"] / R_STALE / "run.json").read_text())
    check(st.get("state") == "failed" and disk.get("state") == "running" and "rc" not in disk,
          "a running run whose pid is gone reads failed, and status never rewrites it", f"{st} disk={disk}")
    leaked = API_SECRET in p.stdout + p.stderr
    pt = run(["status"], env)
    leaked = leaked or API_SECRET in pt.stdout + pt.stderr
    check(not leaked, "no text beyond the named keys leaves run.json or progress.json", "leaked")
    tl = pt.stdout.splitlines()
    check(any(ln.startswith("  " + R_LIVE[-8:]) and " api " in ln for ln in tl)
          and any(ln.startswith(R_DONE[-8:]) for ln in tl),
          "text: a nested run is indented; a top-level run is not; the id shows its tail",
          "\n".join(tl)[:600])

    pa = load(run(["status", "--json", "--all"], env)) or {"agents": []}
    check(R_OLD in [a.get("id") for a in pa["agents"]], "--all lists a run that ended outside the window",
          str([a.get("id") for a in pa["agents"]])[:300])
    ps = load(run(["status", "--json", "--since", "1"], env)) or {"agents": []}
    sids = [a.get("id") for a in ps["agents"]]
    check(R_LIVE in sids and R_DONE not in sids, "--since 1: the running run stays, the one done 5 min ago goes",
          str(sids))
    ex = env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["sessions"], AGENTROUTE_LOG=w["ledger"],
                 XDG_STATE_HOME=w["api_xdg"])
    px = load(run(["status", "--json"], ex)) or {"agents": []}
    check(R_LIVE in [a.get("id") for a in px["agents"]],
          "XDG_STATE_HOME finds the runs dir when CLAUDE_API_AGENT_LOG is unset", str(px)[:200])


def env_for(root: pathlib.Path, **kw) -> dict:
    e = {"PATH": "/usr/bin:/bin", "HOME": str(root), "XDG_STATE_HOME": str(root / "state")}
    e.update({k: str(v) for k, v in kw.items()})
    return e


def run(args, env, timeout: float = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([str(TOOL), *args], capture_output=True, text=True, env=env,
                              timeout=timeout)
    except (FileNotFoundError, PermissionError) as e:
        return subprocess.CompletedProcess([str(TOOL), *args], 127, "", str(e))
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([str(TOOL), *args], 124, "", "timed out")


def load(p) -> dict | None:
    try:
        return json.loads(p.stdout)
    except ValueError:
        return None


def strict(text: str):
    """JSON with no NaN or Infinity, else None."""
    def no(c):
        raise ValueError(c)
    try:
        return json.loads(text, parse_constant=no)
    except ValueError:
        return None


def snapshot(root: pathlib.Path) -> dict:
    """Every file and dir under the fake HOME (except where Apple's python3 caches its own
    stdlib bytecode when HOME is new), and the repo's bin/."""
    skip = root / "Library" / "Caches" / "com.apple.python"
    out = {}
    for top in (root, REPO / "bin"):
        for p in [top, *top.rglob("*")]:
            if p == skip or skip in p.parents:
                continue
            out[str(p)] = (p.stat().st_size, p.stat().st_mtime_ns)
    return out


def load_tool():
    sys.dont_write_bytecode = True      # the test's own import must not write bin/__pycache__
    loader = importlib.machinery.SourceFileLoader("claude_agents", str(TOOL))
    spec = importlib.util.spec_from_loader("claude_agents", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


CTRL = re.compile(r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def aux_checks(root: pathlib.Path, w: dict) -> None:
    env = env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["aux"], AGENTROUTE_LOG=w["aux_ledger"])
    print("== liveness: a live helper keeps its seat live (A F2) ==")
    pj = run(["status", "--json"], env)
    doc = strict(pj.stdout) or {"agents": []}
    rows = {a.get("id"): a for a in doc["agents"]}
    order = [a.get("id") for a in doc["agents"]]
    check(pj.returncode == 0, "the aux world reads, exit 0", f"rc={pj.returncode} {pj.stderr[-300:]}")
    check(A_HLIVE in rows and H5 in rows, "a seat whose files are 3 h old but whose helper wrote 30 s "
          "ago is listed, with the helper", str(order))
    check(A_HLIVE in order and A_NOEND_Q in order and order.index(A_HLIVE) < order.index(A_NOEND_Q),
          "a seat live through its helper sorts by its helper's time", str(order))
    g = lambda i, k: rows.get(i, {}).get(k)  # noqa: E731

    print("== a seat's state (the 60 s clause; no turn-ended: A F6, B F7) ==")
    check(g(A_RECENT, "state") == "busy", "turn ended 10 s ago, activity 20 s ago: busy (under 60 s)",
          str(g(A_RECENT, "state")))
    check(g(A_NOEND_B, "state") == "busy", "no turn-ended, activity 30 s ago: busy", str(g(A_NOEND_B, "state")))
    check(g(A_NOEND_Q, "state") == "quiet", "no turn-ended, activity 600 s ago: quiet, not busy",
          str(g(A_NOEND_Q, "state")))

    print("== lanes: a seat is local only when all its no-agent rows are (A F3) ==")
    check(g(A_MIXED, "lane") == "seat" and g(A_MIXED, "model") == "claude-opus-5-5",
          "a local and an upstream no-agent row: lane seat, meter's model",
          str((g(A_MIXED, "lane"), g(A_MIXED, "model"))))
    check(g(H5, "lane") == "local", "a ledger agent id with an `agent-` prefix still matches its helper",
          str(g(H5, "lane")))
    check(g(A_MIXED, "cost_usd") == 0.75, "a seat's cost is measure.json's", str(g(A_MIXED, "cost_usd")))

    print("== what: a top-level cwd, head then tail (A F1, A F4, B F5) ==")
    check(g(A_LONG, "what") == "longproj", "a first line over 4 KB: the cwd comes from the tail",
          str(g(A_LONG, "what")))
    check(g(A_NESTED, "what") == "realproj", "a nested cwd is never the what", str(g(A_NESTED, "what")))
    check(g(A_MIDDLE, "what") is None, "a cwd past the first 4 KB and before the last 64 KB is not read "
          "(the head and tail bounds hold)", str(g(A_MIDDLE, "what")))

    print("== control characters never reach the output (A F5) ==")
    vals = [v for a in doc["agents"] for v in a.values() if isinstance(v, str)]
    bad = [v for v in vals if CTRL.search(v)]
    check(A_CTRL in rows and H6 in rows and not bad, "no control or bidi character in a JSON value",
          repr(bad[:4]))
    check(isinstance(g(A_CTRL, "what"), str) and "proj" in g(A_CTRL, "what")
          and isinstance(g(H6, "what"), str) and "desc" in g(H6, "what"),
          "the cleaned labels keep their printable text", repr((g(A_CTRL, "what"), g(H6, "what"))))
    pt = run(["status"], env)
    lines = pt.stdout.splitlines()
    check(pt.returncode == 0 and len(lines) == 1 + len(doc["agents"]) and not CTRL.search(pt.stdout.replace("\n", "")),
          "the text form is one line per row with no control character", repr(pt.stdout[-300:]))
    leaked = [s for s in (*SECRETS, NESTED_LEAK) if s in pj.stdout + pt.stdout]
    check(not leaked, "no prompt or tool-input text, nested cwd included", str(leaked))


def bad_checks(root: pathlib.Path, w: dict) -> None:
    print("== one bad value never breaks the table (B F1) ==")
    env = env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["bad"], AGENTROUTE_LOG=root / "none.jsonl")
    pj = run(["status", "--json"], env)
    doc = strict(pj.stdout)
    check(pj.returncode == 0 and doc is not None, "bad values: exit 0 and strict JSON (no NaN)",
          f"rc={pj.returncode} {pj.stdout[:120]!r} {pj.stderr[-300:]}")
    doc = doc or {"agents": []}
    rows = {a.get("id"): a for a in doc["agents"]}
    g = lambda n, k: rows.get(BAD[n], {}).get(k)  # noqa: E731
    check(all(sid in rows for sid in BAD.values()), "every bad seat still has its row",
          str(sorted(set(BAD.values()) - set(rows))))
    check(H7 in rows, "builders: 5 does not hide the seat's helper", str(sorted(rows)))
    check((g("turns", "turns"), g("turns", "context"), g("turns", "window")) == (None, None, None),
          "turns NaN, context -5, window 'big': all null",
          str((g("turns", "turns"), g("turns", "context"), g("turns", "window"))))
    check(g("act_ms", "last_tool_at") is None and g("act_ms", "last_tool") == "Bash",
          "an activity time in milliseconds is out of range: null", str(g("act_ms", "last_tool_at")))
    check(g("act_nan", "last_tool_at") is None, "an activity time NaN: null", str(g("act_nan", "last_tool_at")))
    check(g("started", "started") is None and g("started", "elapsed_s") is None,
          "started 1e20: started and elapsed null", str((g("started", "started"), g("started", "elapsed_s"))))
    check(g("cost_nan", "cost_usd") is None, "cost NaN: null", str(g("cost_nan", "cost_usd")))
    check(g("nul_path", "what") is None, "a NUL in the transcript path: what null", str(g("nul_path", "what")))
    check(g("ended_str", "state") in ("busy", "quiet"), "a turn-ended time that is not a time reads as none",
          str(g("ended_str", "state")))
    pt = run(["status"], env)
    check(pt.returncode == 0 and len(pt.stdout.splitlines()) == 1 + len(doc["agents"]) and "nan" not in pt.stdout.lower(),
          "the text form survives the same values, no 'nan' printed", f"rc={pt.returncode} {pt.stderr[-300:]}")


def cap_checks(root: pathlib.Path, w: dict) -> None:
    print("== --all is capped at 50 ==")
    env = env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["cap"], AGENTROUTE_LOG=root / "none.jsonl")
    d1 = strict(run(["status", "--json"], env).stdout) or {"agents": []}
    da = strict(run(["status", "--all", "--json"], env).stdout) or {"agents": []}
    ids = [a.get("id") for a in da["agents"]]
    check(len(d1["agents"]) == 55, "the window itself is not capped", str(len(d1["agents"])))
    check(len(ids) == 50 and ids[0].startswith("c0000000") and ids[-1].startswith("c0000049"),
          "--all lists the 50 newest seats, newest first", f"{len(ids)} {ids[:1]} {ids[-1:]}")


def guard_checks(root: pathlib.Path, w: dict) -> None:
    print("== a row that raises degrades to '-' and never changes the exit code ==")
    keep = {k: os.environ.get(k) for k in ("CLAUDE_AGENTS_SESSIONS_DIR", "AGENTROUTE_LOG",
                                           "CLAUDE_API_AGENT_LOG")}
    os.environ["CLAUDE_AGENTS_SESSIONS_DIR"] = str(w["sessions"])
    os.environ["AGENTROUTE_LOG"] = str(w["ledger"])
    os.environ["CLAUDE_API_AGENT_LOG"] = str(w["api_log"])
    try:
        mod = load_tool()

        def boom(*a, **k):
            raise RuntimeError("synthetic")
        args = mod.parse(["status", "--json"])
        for name in ("seat_row", "helper_row", "api_row"):
            real = getattr(mod, name)
            setattr(mod, name, boom)
            try:
                table = mod.collect(args, mod.CostScan(None))
                rows = {a.get("id"): a for a in table["agents"]}
                text = mod.render_text(table, args)
                if name == "seat_row":
                    r = rows.get(BUSY, {})
                    ok = r.get("session_id") == BUSY and r.get("model") is None and H1 in rows
                elif name == "helper_row":
                    r = rows.get(H1, {})
                    ok = r.get("parent") == BUSY and r.get("model") is None and rows.get(BUSY, {}).get("model")
                else:
                    r = rows.get(R_LIVE, {})
                    ok = (r.get("lane") == "api" and r.get("state") == "busy" and r.get("model") is None
                          and rows.get(H1, {}).get("model"))
                check(bool(ok) and "Traceback" not in text, f"{name} raising degrades its row only", str(r))
            except Exception as e:                       # noqa: BLE001
                check(False, f"{name} raising degrades its row only", f"{type(e).__name__}: {e}")
            finally:
                setattr(mod, name, real)
    except Exception as e:                               # noqa: BLE001
        check(False, "the tool loads as a module", f"{type(e).__name__}: {e}")
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def watch_rescan_checks() -> None:
    print("== --watch rescans: an appended message is priced once, never re-added ==")
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        w = build(root)
        env = env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["sessions"], AGENTROUTE_LOG=w["ledger"])
        h1 = next(w["sessions"].parent.parent.parent.glob(f"projects/*/{BUSY}/subagents/agent-{H1}.jsonl"))
        try:
            proc = subprocess.Popen([str(TOOL), "status", "--json", "--watch", "1"], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, env=env)
        except OSError as e:
            check(False, "--watch --json runs", str(e))
            return
        docs, deadline = [], time.time() + 20
        try:
            while len(docs) < 3 and time.time() < deadline:
                ln = proc.stdout.readline()
                if not ln:
                    break
                if not ln.strip():
                    continue
                docs.append(strict(ln) or {"agents": []})
                if len(docs) == 1:   # opus 5.5: 1000 input tokens = $0.004
                    with h1.open("a") as f:
                        f.write(json.dumps(asst(1, "msg_h1c", "claude-opus-5-5", u(1000, 0, 0, 0),
                                                [{"type": "text", "text": "x"}])) + "\n")
        finally:
            proc.send_signal(signal.SIGINT)
            try:
                proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
        cost = [next((a.get("cost_usd") for a in doc["agents"] if a.get("id") == H1), None) for doc in docs]
        want = [0.14804, 0.15204, 0.15204]
        check(len(cost) == 3 and all(isinstance(c, float) and abs(c - x) < 1e-9 for c, x in zip(cost, want)),
              "each redraw prices the appended message once (rescans, never accumulates)", str(cost))
        check(proc.returncode == 0, "SIGINT exits 0", str(proc.returncode))


def folder_checks() -> None:
    """agentik-r1 6.3 c1: the session plugin's folder is agentik-session, else the old
    claude-code-session while it alone exists, else agentik-session; the override wins."""
    print("== the session plugin's folder: the new one, else the old one, else the new ==")
    mod = load_tool()
    keys = ("XDG_STATE_HOME", "CLAUDE_AGENTS_SESSIONS_DIR")
    keep = {k: os.environ.get(k) for k in keys}
    try:
        with tempfile.TemporaryDirectory() as fd:
            x = pathlib.Path(fd)
            os.environ["XDG_STATE_HOME"] = fd
            os.environ.pop("CLAUDE_AGENTS_SESSIONS_DIR", None)
            new, old = x / "agentik-session" / "sessions", x / "claude-code-session" / "sessions"
            check(mod.sessions_dir() == new, "neither folder: the new one", str(mod.sessions_dir()))
            old.mkdir(parents=True)
            check(mod.sessions_dir() == old, "only the old folder: the old one", str(mod.sessions_dir()))
            new.mkdir(parents=True)
            check(mod.sessions_dir() == new, "both: the new one", str(mod.sessions_dir()))
            os.environ["CLAUDE_AGENTS_SESSIONS_DIR"] = str(x / "pinned")
            check(mod.sessions_dir() == x / "pinned", "CLAUDE_AGENTS_SESSIONS_DIR still wins")
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        w = build(root)
        env = env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["sessions"], AGENTROUTE_LOG=w["ledger"])
        run(["--help"], env)     # Apple's python3 makes HOME/Library/Caches on its first run
        before = snapshot(root)

        print("== status --json: the schema ==")
        pj = run(["status", "--json"], env)
        doc = load(pj)
        check(pj.returncode == 0 and doc is not None, "status --json exits 0 with one JSON document",
              f"rc={pj.returncode} err={pj.stderr[-300:]}")
        doc = doc or {"agents": []}
        check(set(doc) == {"generated", "since_min", "agents"}, "top-level keys are the contract",
              str(sorted(doc)))
        check(doc.get("since_min") == 30, "the default window is 30 min", str(doc.get("since_min")))
        bad = [sorted(set(a) ^ FIELDS) for a in doc["agents"] if set(a) != FIELDS]
        check(doc["agents"] and not bad, "every agent row carries exactly the contract's fields",
              str(bad))
        rows = {a.get("id"): a for a in doc["agents"]}
        order = [a.get("id") for a in doc["agents"]]

        print("== rows: seats in the window, their helpers changed in it ==")
        check(BUSY in rows and IDLE in rows, "the busy and the idle seat are listed", str(order))
        check(OLD not in rows, "a seat outside --since is not listed", str(order))
        check(H1 in rows and H2 in rows and H3 in rows, "the helpers changed in the window are listed",
              str(order))
        check(H4 not in rows, "a helper not changed in the window is not listed", str(order))
        check(order[:1] == [BUSY] and set(order[1:4]) == {H1, H2, H3} and order[4:] == [IDLE],
              "a seat's helpers follow it, seats newest first", str(order))
        g = lambda i, k: rows.get(i, {}).get(k)  # noqa: E731

        print("== lanes, models, states ==")
        check(g(BUSY, "lane") == "seat", "the busy seat is lane seat (an upstream ledger row does "
              "not make it local)", str(g(BUSY, "lane")))
        check(g(IDLE, "lane") == "local" and g(IDLE, "model") == LOCAL_MODEL,
              "a seat whose session is in the ledger with no agent id is local, with model_out",
              f"{g(IDLE, 'lane')} {g(IDLE, 'model')}")
        check(g(H1, "lane") == "helper" and g(H3, "lane") == "helper", "helpers are lane helper",
              f"{g(H1, 'lane')} {g(H3, 'lane')}")
        check(g(H2, "lane") == "local" and g(H2, "model") == LOCAL_MODEL,
              "a helper in the ledger is local and takes model_out", f"{g(H2, 'lane')} {g(H2, 'model')}")
        check(g(BUSY, "model") == "claude-opus-5-5", "a seat's model is meter.json's", str(g(BUSY, "model")))
        check(g(H1, "model") == "claude-opus-5-5" and g(H3, "model") == "claude-sonnet-5-5",
              "a helper's model is its newest assistant line's", f"{g(H1, 'model')} {g(H3, 'model')}")
        check(g(BUSY, "state") == "busy", "activity newer than turn-ended: busy", str(g(BUSY, "state")))
        check(g(IDLE, "state") == "idle", "turn ended after the last tool, 300 s ago: idle",
              str(g(IDLE, "state")))
        check(g(H1, "state") == "done", "last tool SubagentHandback: done", str(g(H1, "state")))
        check(g(H2, "state") == "busy", "newest line 10 s old: busy", str(g(H2, "state")))
        check(g(H3, "state") == "quiet", "newest line 600 s old, not done: quiet", str(g(H3, "state")))

        print("== numbers: turns, context, cost ==")
        check((g(BUSY, "turns"), g(BUSY, "context"), g(BUSY, "window")) == (12, 80000, 1000000),
              "a seat's turns, context and window are meter.json's",
              str((g(BUSY, "turns"), g(BUSY, "context"), g(BUSY, "window"))))
        check(g(BUSY, "cost_usd") == 1.234, "a seat's cost is measure.json's cost.usd", str(g(BUSY, "cost_usd")))
        check(g(H2, "cost_usd") == 0, "a local helper costs 0", str(g(H2, "cost_usd")))
        check(g(IDLE, "cost_usd") == 0.5, "a local seat's cost is still measure.json's (A F3)",
              str(g(IDLE, "cost_usd")))
        # opus 5.5 at 4/20, cache read 0.20/M, cache write 4*1.25:
        # msg_h1a once: 1000*4 + 2000*20 + 100000*0.2 + 10000*5 = 114000 -> 0.114
        # msg_h1b:      10*4 + 500*20 + 120000*0.2           =  34040 -> 0.03404
        c1 = g(H1, "cost_usd")
        check(isinstance(c1, float) and abs(c1 - 0.14804) < 1e-9,
              "a helper's cost sums each distinct message.id once (a repeated id is not billed twice)",
              str(c1))
        c3 = g(H3, "cost_usd")
        check(isinstance(c3, float) and abs(c3 - 0.0014) < 1e-9,
              "sonnet 5.5 is priced at 2/10 with cache reads at 0.20/M", str(c3))
        check(g(H1, "turns") == 2 and g(H1, "context") == 120010 and g(H1, "window") is None,
              "no builders row: turns count distinct messages, context is the newest's in+cache, "
              "window null", str((g(H1, "turns"), g(H1, "context"), g(H1, "window"))))
        check(g(H2, "turns") == 7 and g(H2, "context") == 45000,
              "a builders[] row gives a helper's turns and context",
              str((g(H2, "turns"), g(H2, "context"))))
        check(isinstance(g(BUSY, "elapsed_s"), int) and 590 <= g(BUSY, "elapsed_s") <= 700,
              "elapsed runs from meter.json's started", str(g(BUSY, "elapsed_s")))
        check(isinstance(g(H1, "elapsed_s"), int) and 290 <= g(H1, "elapsed_s") <= 400,
              "a helper's elapsed runs from its first timestamp", str(g(H1, "elapsed_s")))

        print("== last tool, what, ids ==")
        check(g(BUSY, "last_tool") == "Bash" and isinstance(g(BUSY, "last_tool_at"), str),
              "a seat's last tool is activity.json's", str((g(BUSY, "last_tool"), g(BUSY, "last_tool_at"))))
        check(g(H1, "last_tool") == "SubagentHandback" and g(H3, "last_tool") == "Read",
              "a helper's last tool is its newest tool_use", f"{g(H1, 'last_tool')} {g(H3, 'last_tool')}")
        check(g(BUSY, "what") == "myproj", "a seat's what is the cwd basename", str(g(BUSY, "what")))
        check(isinstance(g(H1, "what"), str) and 0 < len(g(H1, "what")) <= 40
              and g(H1, "what").startswith("Build the status verb"),
              "a helper's what is the meta description, at most 40 characters", repr(g(H1, "what")))
        check(g(H1, "session_id") == BUSY and g(H1, "agent_id") == H1 and g(H1, "parent") == BUSY,
              "a helper carries its seat's session id, its agent id, its seat as parent",
              str((g(H1, "session_id"), g(H1, "agent_id"), g(H1, "parent"))))
        check(g(BUSY, "agent_id") is None and g(BUSY, "parent") is None and g(BUSY, "session_id") == BUSY,
              "a seat has no agent id and no parent", str((g(BUSY, "agent_id"), g(BUSY, "parent"))))
        check(IDLE in rows and g(IDLE, "window") is None and g(IDLE, "what") is None,
              "unknowns are null in JSON (no window, no transcript)",
              str((g(IDLE, "window"), g(IDLE, "what"))))

        print("== the text form ==")
        pt = run(["status"], env)
        lines = pt.stdout.splitlines()
        check(pt.returncode == 0 and lines and lines[0].split()[:2] == ["id", "lane"],
              "the text form opens with one header line", f"rc={pt.returncode} {lines[:1]} {pt.stderr[-200:]}")
        head = lines[0] if lines else ""
        cols = ["id", "lane", "model", "elapsed", "turns", "context", "cost", "last tool", "state", "what"]
        pos = [head.find(c) for c in cols]
        check(all(p >= 0 for p in pos) and pos == sorted(pos), "the header names the columns in order", head)
        check(len(lines) == 1 + 5, "one line per row", str(len(lines)))
        body = "\n".join(lines[1:])
        check(any(ln.startswith(BUSY[:8] + " ") for ln in lines) and BUSY not in body,
              "a seat's id is cut to 8 characters", body[:300])
        check(any(ln.startswith("  " + H1[:8] + " ") for ln in lines) and H1 not in body,
              "a helper's id is cut to 8 and indented under its seat", body[:300])
        check("80k/1M" in body, "context prints used/window", body[:400])
        idle_ln = next((ln for ln in lines if ln.startswith(IDLE[:8])), "")
        check("30k/-" in idle_ln and idle_ln.rstrip().endswith("-"), "unknowns print as -", idle_ln)
        check("$0.50" in idle_ln, "a local seat prints measure.json's cost", idle_ln)
        h2_ln = next((ln for ln in lines if ln.startswith("  " + H2[:8])), "")
        check(" 0 " in h2_ln, "a local helper's cost reads 0", h2_ln)

        print("== --all ==")
        pa = run(["status", "--all", "--json"], env)
        da = load(pa) or {"agents": []}
        ids = [a.get("id") for a in da["agents"]]
        check(pa.returncode == 0 and OLD in ids and H4 in ids, "--all lists every seat and helper", str(ids))
        seats = [i for i in ids if i in (BUSY, IDLE, OLD)]
        check(seats == [BUSY, IDLE, OLD], "--all orders seats newest first", str(seats))
        old = next((a for a in da["agents"] if a.get("id") == OLD), {})
        check(old.get("cost_usd") is None and old.get("last_tool") is None and old.get("state") == "idle",
              "a seat with no measure.json or activity.json: null cost and last tool, idle", str(old))
        h4 = next((a for a in da["agents"] if a.get("id") == H4), {})
        check(h4.get("state") == "done", "stop_reason end_turn: done", str(h4.get("state")))

        print("== nothing leaks, nothing is written ==")
        outs = [p.stdout + p.stderr for p in (pj, pt, pa)]
        leaked = [s for s in SECRETS for o in outs if s in o]
        check(not leaked, "no prompt, result, text or tool-input text reaches the output", str(leaked))

        print("== paths: the ledger and sessions dir found as their owners find them ==")
        e2 = env_for(root, AGENTROUTE_STATE_DIR=w["ledger"].parent)
        d2 = load(run(["status", "--json"], e2)) or {"agents": []}
        r2 = {a.get("id"): a for a in d2["agents"]}
        check(r2.get(H2, {}).get("lane") == "local" and BUSY in r2,
              "XDG_STATE_HOME finds the sessions dir; AGENTROUTE_STATE_DIR finds the ledger",
              str(sorted(r2)))

        print("== the ledger: only its last 2 MB is read ==")
        big = w["big"]
        d3 = load(run(["status", "--json"], env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["sessions"],
                                                    AGENTROUTE_LOG=big))) or {"agents": []}
        r3 = {a.get("id"): a for a in d3["agents"]}
        check(r3.get(H2, {}).get("lane") == "local" and r3.get(H3, {}).get("lane") == "helper",
              "a ledger row older than the last 2 MB is not read",
              str((r3.get(H2, {}).get("lane"), r3.get(H3, {}).get("lane"))))

        print("== an empty window ==")
        empty = w["empty"]
        ee = env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=empty, AGENTROUTE_LOG=w["ledger"])
        pe = run(["status"], ee)
        el = pe.stdout.splitlines()
        check(pe.returncode == 0 and len(el) == 2 and el[0].startswith("id")
              and el[1].strip() == "no agents in the last 30 min",
              "an empty table prints the header and 'no agents in the last N min', exit 0",
              f"rc={pe.returncode} {el}")
        pe2 = run(["status", "--json", "--since", "5"], ee)
        de = load(pe2) or {}
        check(pe2.returncode == 0 and de.get("agents") == [] and de.get("since_min") == 5,
              "an empty --json table is agents [], exit 0", f"rc={pe2.returncode} {pe2.stdout[:200]}")

        print("== exit codes ==")
        p = run(["status"], env_for(root, CLAUDE_AGENTS_SESSIONS_DIR="/nonexistent"))
        check(p.returncode == 1, "an unreadable sessions dir exits 1", f"rc={p.returncode}")
        p = run(["status", "--json"], env_for(root, CLAUDE_AGENTS_SESSIONS_DIR=w["ledger"]))
        check(p.returncode == 1, "a sessions 'dir' that is a file exits 1", f"rc={p.returncode}")
        for args in (["frobnicate"], [], ["status", "--watch", "0"], ["status", "--since", "abc"],
                     ["status", "--since", "0"], ["status", "--bogus"], ["status", "--watch", "86401"]):
            p = run(args, env, timeout=10)
            check(p.returncode == 2, f"usage error {args} exits 2", f"rc={p.returncode}")

        aux_checks(root, w)
        bad_checks(root, w)
        cap_checks(root, w)
        guard_checks(root, w)
        api_checks(root, w)

        print("== --watch ==")
        try:
            proc = subprocess.Popen([str(TOOL), "status", "--watch", "1"], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, env=env)
        except OSError as e:
            check(False, "--watch redraws until SIGINT, which exits 0", str(e))
        else:
            time.sleep(2.5)
            proc.send_signal(signal.SIGINT)
            try:
                out, err = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
            heads = sum(1 for ln in out.splitlines() if ln.split()[:2] == ["id", "lane"])
            check(proc.returncode == 0 and heads >= 2, "--watch redraws until SIGINT, which exits 0",
                  f"rc={proc.returncode} headers={heads} err={err[-200:]}")

        print("== nothing is written (the whole fake HOME, every run above) ==")
        after = snapshot(root)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        check(not changed, "the tool writes nothing anywhere under HOME or in bin/", str(changed[:5]))

    watch_rescan_checks()
    folder_checks()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
