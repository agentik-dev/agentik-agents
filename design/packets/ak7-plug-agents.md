# Packet ak7-plug-agents: agents answers `describe`; `doctor --json` exists; no lane set up is a note

The hq's brief for row ak7, in this repo's packet shape. Its interface is the plug contract shared by five tools and read by agentik-commons' suite (`plugins/suite/lib/agentik_suite/tools.py`, `config.py`); section 3 holds what this tool prints of it, cut to the 9 KB ceiling.

| item | value |
|---|---|
| from | the hq's row ak7 (design/15 §4 P4, P5, P9, P10; §13); the plug contract §2 to §7; hq entries 6 (`/usr/bin/python3`, 3.9, stdlib) and 37 (made-up names, loopback only) |
| pin | main c0193bd, plugin 1.6.3; worktree `.claude/worktrees/ak7-plug-agents`, branch `ak7-plug-agents`; nothing linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or landing; no `claude`, no model, no key read; `doctor`, `route --check` and any probing verb only under `sandbox-exec` with the network denied; no relay verb; `make` only through the gate queue |
| may touch | `plugin/lib/agents_plug.py` (new); `plugin/lib/agentik-agents`; `plugin/lib/agentroute` (`check`, `main`); `plugin/lib/claude-agents` (the `status --json` print); `tests/test-plug.py` (new); `tests/test-dispatch.sh`; `tests/test-status.py`; `tests/test-bare-machine.py` (section 4); `Makefile` (`test`'s lists); `plugin/.claude-plugin/plugin.json`; `NICE_TO_HAVE.md`; this packet; a charter |
| acceptance | section 2's lines 1 to 13 |
| verify | `make check`, once, last, through `agentik session gate run`, then `agentik session gate wait <id> --strict --timeout 540` |
| budget | a commit each: packet, tests seen red, the code, NICE, 1.7.0 alone; stop at 90 tool calls with the act in flight committed |

## 1. What the source says

The owner: "Make plugin configuration discoverable and drill down." The suite's `agentik config agents` lists this tool's settings and `agentik config agents.route.local_max_tokens` prints one as a card. Today they are environment variables a person finds only by reading four scripts.

Baseline at c0193bd, 2026-11-13, temp HOME, sandboxed: `describe --json`, `describe config --json`, `doctor --json` exit 2 with the usage lines; `status --json` with no sessions folder exits 1 and leaves 51 files under `~/Library/Caches/com.apple.python`; the text `doctor` with no lane prints `FAIL router` and sends a HEAD to the upstream.

## 2. Rulings

- R1. Every verb but `doctor` prints and exits as at the pin, but for R8. The dispatcher stays POSIX sh, args unchanged. `route --check`'s text and exit stand.
- R2. `plugin/lib/agents_plug.py`, stdlib, run under `install_cli`'s interpreter: the three reads, the settings table, the checks. Dispatcher: `describe`, `doctor --json`, `describe` in the usage line and `table`. The freeze walks `lib/`, so it carries the file.
- R3. `describe --json`: tool `agents`, the dispatcher's version; needs `claude` (optional) and `python3`; verbs local, status, rig, route, doctor, describe, install-cli, each its `table` line, `top` false; reads `config`, `doctor`, then `sessions` (`status --json`).
- R4. Layers: `default`; `rig` (the backends file at agentroute's path, present when it exists, not travelling); `env` (present when any R5 variable is set). No `user`.
- R5. Keys: `route.` each `AGENTROUTE_*` agentroute reads by `env`/`env_num` but `BACKENDS`; `backends.<name>.url|model|fold_system|auth` as the router fills them (`AGENTROUTE_BACKENDS`, else the file, plus its `default`); `local.subagent`, `local.explore`; `rig.` each `${LOCALRIG_*:-default}`. Defaults are read from the owning script at run time, never typed here. Values cast as the script casts; `*auth`, `*_KEY` are secrets, `"(set)"` or null. Source `env`, `rig` (the file, line null) or `default`. An unparsable file or variable: `ok` true, one `unreadable` warning, the router's backends. Change: `launch` (`VAR=VALUE agentik agents local`, `... rig up <backend>`) for route, local, rig; `command` (the rig's verb) for backends; `live` false.
- R6. One summary table, a key or pattern to a sentence under 100 characters; twelve given word for word, the rest in that voice.
- R7. A lane is set up when the backends file exists, an `AGENTROUTE_*` is set, or a loopback connect to the router's address answers in 1 s: one function decides, the text `doctor` asks it. `agentroute --check --json` prints `{"ok", "rows": [{state, what, detail}]}`, same probes and exit. `doctor --json`: one check per tool on PATH (`ok`, else `note`, remedy `/agents:install-cli`), `claude` (`ok`/`warn`), `python3` (`ok`, `fail` below 3.9 or not running), then the lane: `note` when not set up, else `--check --json`'s rows (`FAIL` as `fail`); exit 0. The text `doctor` with no lane prints one line under `Local lane:` and runs no `--check`.
- R8. `status --json` opens with `"schema": "agentik.agents.sessions/1"`, `"ok": true`; with no sessions folder its stderr line and exit 1 stand. The dispatcher's `status` sets `PYTHONPYCACHEPREFIX` to `${XDG_CACHE_HOME:-$HOME/.cache}/agentik/pycache` when unset.
- R9. Settings one table, checks one list, each row data. No key opening `api`, no layer `user`, no check `api`: the API lane's design comes next.

Acceptance, `A` the worktree's `plugin/bin/agentik-agents`, each line in a temp HOME, sandboxed where it may probe:

1. `A describe --json`: exit 0, every §3 key, three reads, seven verbs, `top` false, no ESC, under 1 s; `A describe`, `A describe nosuch --json` exit 2.
2. `A describe config --json`: every §4 key, every layer `default`, `route.local_max_tokens` agentroute's integer default; no `api.` key, no `user` layer.
3. `AGENTROUTE_LOCAL_MAX_TOKENS=4096`: 4096, source env, values default then env, change `launch`, live false; `AGENTROUTE_LOCAL_AUTH`: `"(set)"`, the word nowhere.
4. A backends file: its backend, source `rig` with the path, the layer present; with `AGENTROUTE_BACKENDS` too: the variable's, source env.
5. A test holds the keys to the variables `agentroute`, `claude-local`, `localrig` read, both ways.
6. `... route.listen`: that one; `... nosuch`: `[]`, exit 0. A file not JSON: `ok` true, one `unreadable` warning, `backends.default.url` = `route.local_url`.
7. `agentroute --check --json`, nothing listening: a `router` row `FAIL`, `--check`'s exit.
8. `A doctor --json`, nothing set up: `agentik.doctor/1`, `ok` true, `failed` 0, one `lane` note, no `router`/`upstream`, exit 0, under 3 s, a recording stub sees no off-loopback connect; with a backends file the router's rows, `router` `fail`.
9. `A doctor`, nothing set up: one line under `Local lane:`, no FAIL row; with a file, the pin's rows.
10. `A status --json`, an empty sessions folder: `schema`, `ok`, then the pin's three keys; none: stderr line, exit 1. HOME unchanged outside `$XDG_CACHE_HOME/agentik/` after lines 1 to 6 and 10, no `Library`.
11. By hand: the suite's `config agents.route.local_max_tokens --json` (ok, tool, key, `launch`), `config agents`, `config` (`answers`, `0 changed`).
12. `tests/test-plug.py`, `test-dispatch.sh`, `test-route.py`, `test-bare-machine.py` pass, under `/usr/bin/python3` too.
13. The verify row, green.

## 3. Interfaces

- `agentik-agents describe --json`, `describe config --json [KEY]`, `doctor --json`: one JSON object and a newline on stdout, exit 0; a bad argv exits 2 with a line on stderr. Envelope `{"schema": "agentik.<read>/1", "ok": true, "tool": "agents", ...}`.
- A setting: `key`, `value`, `default`, `type` (string, integer, number, boolean, list, path, secret), `choices`, `summary`, `source {layer, path, line}`, `change {kind, command, path, block, note}`, `live`, `values [{layer, value}]`. A layer: `name`, `path`, `present`, `travels`. A warning: `key`, `reason`, `value`, `path`, `line`.
- A check: `name`, `status` (ok, note, warn, fail), `detail`, `remedy`; the answer's `failed` and `warned` count them.
- `agents_plug.py VERSION lane`: exit 0 a lane is set up, 1 none. `agentroute --check --json`: `{"ok", "rows"}`.

## 4. Findings that name this row

None at the pin. `tests/test-bare-machine.py`'s `test_3_doctor` pinned the bare doctor's `FAIL router` row, which R7 removes: it now holds R7's line.

## 5. Forbidden reads

A file over 8 KB whole; a relay ledger or a reference snapshot whole; anything outside the wall.

## 6. Report

The hq's record: the head, the gate's line, each acceptance line, the choices made, the summary sentences written here, for the hq to pass through its plain-English check.
