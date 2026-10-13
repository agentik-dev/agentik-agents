# Packet a-s5: `claude-agents status`, slice two: API children in flight

| item | value |
|---|---|
| from | the owner's plugin review, 2026-10-13 ("The status verb, sketched": "To add"); packet a-s3 §3, which promised lane `api` with no field changed |
| pin | branch `a-s5-status-api` off main; worktree `.claude/worktrees/a-s5-status-api`; a hand-run builder |
| wall | this repo only. No push, merge, tag, `--amend` or rebase. No live `claude` and no API call: tests put a fake `claude` that prints canned stream-json first on PATH, via `CLAUDE_API_AGENT_CLAUDE_BIN`. Never start a router; never `pkill -f`. Never build a relay binary or run a relay verb. Never read a transcript |
| may touch | `bin/claude-api-agent`, `bin/claude-agents`, `bin/claude-fanout`, `tests/test-status.py`, `tests/test-run-path.sh`, `tests/test-apirun.py` (new), `tests/test-fanout.py`, `Makefile`, `README.md`, `NICE_TO_HAVE.md`, this packet |
| acceptance | `python3 tests/test-apirun.py 2>&1 \| tail -1` reads `N passed, 0 failed`; `python3 tests/test-status.py 2>&1 \| grep -c FAIL` reads 0; `bash tests/test-run-path.sh 2>&1 \| tail -1` ends `0 failed`; `python3 tests/test-fanout.py 2>&1 \| tail -1` ends `0 failed`; `make test; echo $?` ends 0 |
| budget | one builder sitting; one commit per act; act 1 the red tests |
| verify | the observer runs `make check` once on the branch |

## 1. What the source says
- In profile mode `claude-api-agent` runs `claude --bare <profile flags> --print …` with `--output-format json` (`:565-571`, `:1444-1448`). The prompt goes in on stdin (`:1496-1505`). The child's stdout goes to a 0600 temp file `$TMPDIR/.caa-out.XXXXXX` (`:1510-1514`). `append_usage_log` writes one `usage.jsonl` row from that envelope after the child exits (`:1517`, rows shaped at `:904-927`), and then the envelope is printed. Nothing is written at launch. Pass-through mode (`:1447`) keeps the caller's flags.
- The logging rule (`:797-801`) keeps the prompt, `result`/`structured_output` and the denials' `tool_input` out of every log.
- `--bare` loads no hooks, so an API child has no session-plugin dir. Inside a Claude Code session, `$CLAUDE_CODE_SESSION_ID` names the calling seat (claude-code-session `cli.py:366`).
- `claude-fanout` runs `claude-api-agent` shards (`:729`) and writes shard files only after each child exits (`:456-457`, `:490-491`).
- `claude-agents status` (a-s3) lists seats, helpers and local rows. Its `--json` object is the contract.

## 2. Rulings
1. **The run dir.** Each run gets one dir under the usage log's state dir: `${XDG_STATE_HOME:-~/.local/state}/claude-api-agent/runs/<id>/`, mode 0700. `CLAUDE_API_AGENT_LOG`'s dirname is used when that is set, so the tests stay hermetic. The id is `<UTC yyyymmddThhmmss>-<pid>`.
2. **`run.json` at launch.** Written before the child starts: `{id, pid, profile, tags, model, started, parent_session, fanout, state: "running"}`.
   - `parent_session` is `$CLAUDE_CODE_SESSION_ID` or null.
   - `fanout` is `$CLAUDE_FANOUT_RUN` or null.
   - At exit it is rewritten in place with `state` set to `done` (rc 0) or `failed`, plus `rc` and `ended`.
   - Every write goes to a temp file first and is renamed into place.
3. **Profile mode streams.** `--output-format json` becomes `--output-format stream-json --verbose`, and the child's stdout is piped into a stdlib fold (`claude-agents fold --run-dir <dir>`).
   - For each event the fold rewrites `progress.json`, at most once a second and on the last event: `{turns, model, last_tool, last_tool_at, usage{in,out,cr,cw}, cost_usd, updated}`.
   - Usage is counted once per `message.id`, and `cost_usd` is priced by `claude-costs`' `predicted_cost`.
   - The fold writes the `result` event, a single JSON object (the same envelope `--output-format json` gave), to the temp file that `append_usage_log` and the final print already read. Everything downstream is unchanged.
   - The child's exit code passes through (`PIPESTATUS`), as the present code keeps it.
   - With no `result` event (a crash), the temp file gets nothing, as before, and `run.json` reads `failed`.
4. **No content.** `run.json` and `progress.json` hold no prompt, result, thinking, or tool-input or tool-result text. Only names, numbers, ids and times go in, as the logging rule at `:797` requires.
5. **Pass-through mode** writes `run.json` only, with no `progress.json` and no stream.
6. **Pruning.** At launch, run dirs whose `run.json` ended more than 7 days ago are removed. A `running` dir whose pid is gone becomes `failed` with `rc: null` when `status` reads it; `status` never writes it.
7. **Fanout.** `claude-fanout` exports `CLAUDE_FANOUT_RUN=<its run id>` to each shard, so each shard's `run.json` names its fanout. Nothing else in fanout changes.
8. **Status.** `claude-agents status` lists runs that are `running` with a live pid, or that ended within `--since`.
   - The lane is `api`, the id is the run id, `parent` is `parent_session`, and `what` is the profile plus its tags.
   - A run with a parent seat that is listed nests under it as a helper does; any other run is a top-level row.
   - State is `busy` (running) or `done` or `failed`.
   - Turns, model, last tool and cost come from `progress.json`, else `-`. Context is the newest message's input plus cache tokens over `-`.
   - No `--json` field is added or renamed.

## 3. Interfaces
- `claude-api-agent`'s stdout, exit code and `usage.jsonl` rows are unchanged, and so is the envelope a caller parses.
- `claude-agents fold` is internal. The README names it once.
- The `--json` contract gains rows with lane `api` and no new field.

## 4. Findings that name this row
The owner's review, the status sketch's "To add" and "Sources" lines.

## 5. Forbidden reads
Transcripts; anything under `~/.local/state/agent-relay`; the real `~/.local/state/claude-api-agent` beyond `ls`.

## 6. Report
At most 200 words:
- each act's commit
- each test, red before and green after
- each acceptance line
- one fake run's `run.json` and `progress.json`, shown as their key lists
- the choices made

## 7. Charter (builder sitting 2026-10-13)
- goal: rulings 1-8 above, the acceptance lines green.
- budget: one sitting; at most 90 tool calls; checkpoint at 80%.
- pin: branch `a-s5-status-api`, worktree `.claude/worktrees/a-s5-status-api`, off 5d0076c.
- acts:
  1. red tests: tests/test-apirun.py (fake claude, canned stream-json, repeated message.id, planted secret, crash case), lane-api rows in tests/test-status.py, CLAUDE_FANOUT_RUN in tests/test-fanout.py; test-run-path.sh hermetic. done: red: apirun 19/20 failed, status 12 failed, fanout 1 failed
  2. the run dir and run.json in bin/claude-api-agent (rulings 1, 2, 5, 6). done: apirun 35 passed, 18 failed (act 3's); run-path 22/0, arg-handling 58/0
  3. `claude-agents fold` and the profile-mode stream switch (rulings 3, 4). done: apirun 53/0; run-path 22/0, arg-handling 58/0
  4. fanout's export (ruling 7), the status rows (ruling 8), the README. done: fanout 46/0, status 117/0, apirun 53/0, run-path 22/0
- fix round (both refuters' BLOCK on 939ecda):
  5. red tests, one per item, and the throttle (B F2) and the rename (B F3) asserted. done: apirun 61 passed 20 failed, status 1 failed; FOLD_EVERY_S=0.0 and an in-place write each fail the suite
  6. signals (A F1 = B F1): the child runs in the background (a FIFO to the fold), TERM/HUP/INT forwarded, rc 128+signal. done: apirun 71 passed, 10 failed (acts 7-8's); term.py rc 143, child gone, never completed; t3.sh prof and pass rc 143, fake gone, no orphan fold, stdout 0 bytes, run.json failed 143
  7. the fold and the files (A F2, A F3, A F4, B N1). done: apirun 79 passed, 2 failed (act 8's), status 118/0; t6.py byte-identical to main for \n, none and \r\n; t9.sh model and tool `?`, files 0600
  8. lifecycle and hermeticity (B N2, B N3); S4s A F5, B N2's pid reuse, B N4 filed, the three fixed S4s dropped. done: apirun 81/0, run-path 22/0
- choices: (one line each, as met)
  - the safe-name charset adds `_`, so an MCP tool name (`mcp__srv__x`) survives; it applies to the fold and to api rows, not seat or helper rows.
  - stream-json: assistant and result shapes confirmed against the test fixtures; assumed: `system/init` carries `model`, events carry no timestamp. Assumed too: real claude sets its own SIGINT handler (else the 2 s TERM ends it).
  - `usage` in progress.json is the newest message's {in,out,cr,cw} (so status reads context from it); `cost_usd` sums predicted_cost over each message.id once, its last-seen usage.
  - `CLAUDE_API_AGENT_NO_LOG`: no run dir, `--output-format json`.
  - stream mode, rc 0 but no result event: run.json reads `failed` (rc 0 kept).
  - pass-through run.json has `model: null` (its argv may carry free text); profile mode takes the last `--model` of the argv it built.
  - the fold takes as the result event `type: result`, or an object with no `type` and `total_cost_usd` (the usage logger's own test); non-JSON lines are dropped.
  - no run dir or no `bin/claude-agents`: the run keeps `--output-format json`.
  - fanout's export overwrites a caller's `CLAUDE_FANOUT_RUN`.
  - status: a dead `running` run's end is its newest file mtime; `--all` caps runs at 50; model falls back to run.json's; the text id is the run id's last 8 chars.
  - pruning touches only dirs named like a run id, never symlinks.
- handover:
  - decide, owner: the coordinator. Ruling 3 lists progress.json's `usage{in,out,cr,cw}` and ruling 8 reads context from "the newest message"; this sitting made `usage` the newest message's and summed cost per message.id. If `usage` was meant as the run's totals, a `context` key must be added (a field change to progress.json). Consumer: `claude-agents status` lane api.
- exit: done, acts 1-4 and the fix round (acts 5-8, eabe922). Acceptance, a fake claude first on PATH: apirun 81/0; status FAIL count 0 (118); run-path 22/0; fanout 46/0; `make test` rc 0 in 53 s, run once. No router left; nothing under the real state dir.
