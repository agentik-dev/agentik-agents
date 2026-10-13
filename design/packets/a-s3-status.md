# Packet a-s3: `claude-agents status`, slice one: the seats, their helpers and the local lane

| item | value |
|---|---|
| from | the owner's plugin review, 2026-10-13 (example-mac `history/observer/plugin-review-2026-10-13.md`, "The status verb, sketched"); the owner's answer at 08:54: the CLI first, the band later; the review's S3 price-table finding |
| pin | branch `a-s3-status` off main; worktree `.claude/worktrees/a-s3-status`; a hand-run builder |
| wall | this repo only. No push, merge, `--amend` or rebase. No live `claude` and no API call. Never start a router; kill only a pid your own run started, verified by `ps -o ppid,etime,args`; never `pkill -f`. Never build a relay binary or run a relay verb. Tests use synthetic dirs only; the real `~/.local/state/claude-code-session` and `~/.claude/projects` are read only by the finished tool's smoke run, and its output never goes into a commit |
| may touch | `bin/claude-agents` (new), `bin/claude-costs` (the price table and `predicted_cost` only), `tests/test-status.py` (new), `tests/test-costs.py`, `commands/agents-status.md` (new), `commands/local-status.md` (removed), `Makefile`, `README.md`, `NICE_TO_HAVE.md`, this packet; the fix round adds `agents/local-*.md` and `.claude-plugin/*.json` |
| acceptance | `make check; echo $?` ends 0; `python3 tests/test-status.py 2>&1 \| grep -c FAIL` reads 0; `make test; echo $?` ends 0; `bin/claude-agents status --json \| python3 -c 'import json,sys; json.load(sys.stdin)'; echo $?` prints 0; `bin/claude-agents frobnicate; echo $?` ends 2; `CLAUDE_AGENTS_SESSIONS_DIR=/nonexistent bin/claude-agents status; echo $?` ends 1 |
| budget | one builder sitting; one commit per act; act 1 the red tests |
| verify | the observer runs `make check && make test` once, and one live `claude-agents status` in its own session |

## 1. What the source says
- The session plugin keeps one dir per session: `${XDG_STATE_HOME:-~/.local/state}/claude-code-session/sessions/<sid>/` (claude-code-session `claude_session/resolver.py:415`); this Mac holds 713, most of them ended. `meter.json` (`meter.py:42-66`): `model`, `context`, `window`, `turns`, `started`, `ts`, `transcript.path`, and `builders[]`, one `{agent, turns, tokens, max_context}` per subagent (`meter.py:186-197`); it is written only on the main thread's PostToolUse (`hooks.py:415-441`). `measure.json` `{at, context{tokens,window,percent}, cost{usd}}` (`measure.py:80-91`) holds the only cost. `activity.json` `{event, tool, at}` (epoch float) is the main thread's last tool; `helper-activity.json` is shared by every helper and has no agent id (`hooks.py:136-143`). `turn-ended.json` `{at}`.
- A subagent's transcript is `<dirname(transcript.path)>/<sid>/subagents/agent-<id>.jsonl`, beside `agent-<id>.meta.json` (`{agentType, description, model, toolUseId, …}`; `model` is the alias, e.g. `opus`). Each line has a `timestamp`; assistant lines carry `message.model` (`claude-opus-5-5`), `message.id`, `message.usage` and `tool_use` blocks with a `name`. One assistant message can span several lines that repeat its id and usage.
- agentroute's ledger: `$AGENTROUTE_LOG`, else `${AGENTROUTE_STATE_DIR:-~/.local/state/agentroute}/requests.jsonl` (`bin/agentroute:127-129`). A row lands when its request completes, with `session_id`, `agent_id`, `parent_agent_id` (from the `x-claude-code-*` headers), `model_out`, `backend`, `status`, `wall_s` and `usage` (`:373-379`, `:249-265`, `:559-563`). Nothing records a request in flight.
- `claude-api-agent` appends to `usage.jsonl` only when a run ends (`:1517`) and runs its children `--bare` (`:1445-1448`), so they get no session dir. Nothing shows an API child in flight today; that is slice two.
- `bin/claude-costs`: `PRICES` (`:46-58`) lacks `claude-opus-5-5`, `claude-fable-5-1`, `claude-sonnet-5-5` and `claude-haiku-5-5`, which print "unpriced". `CACHE_READ_MULT = 0.10` is global (`:82`). `predicted_cost(model, {in,out,cr,cw})` (`:134-143`) is reusable; the tests load the tool with `SourceFileLoader` (`tests/test-costs.py:21-25`).
- `commands/local-status.md` runs `agentroute --check` and relays the LOCAL LANE block of `claude-costs`.

## 2. Rulings
1. A new stdlib tool, `bin/claude-agents` (`#!/usr/bin/python3`), with one verb in this slice: `status [--json] [--watch N] [--all] [--since MIN]`. It writes nothing anywhere.
2. Rows. A seat is a session dir in which `activity.json`, `meter.json` or `turn-ended.json` changed within `--since` minutes (default 30). `--all` lists every dir, newest first, capped at 50. Each seat gives one row with lane `seat`, then one row for each of its subagent transcripts changed within the window (every one under `--all`) with lane `helper`. A row whose `(session_id, agent_id)` is in the agentroute ledger becomes lane `local` and takes the ledger's `model_out`. A seat whose session id is in the ledger with no agent id becomes `local` too.
3. Columns, in order: `id` (a seat's session id cut to 8 characters; a helper's agent id cut to 8, indented under its seat), `lane`, `model`, `elapsed`, `turns`, `context` (used/window, e.g. `80k/1M`), `cost`, `last tool` with its age, `state`, `what`.
   - **Seat:** `model`, `turns`, `context`, `window` and `started` come from `meter.json`. `cost` is `measure.json`'s `cost.usd`, the whole session's total. The last tool is from `activity.json`. `state` is `busy` when the activity is newer than `turn-ended.json` or under 60 s old, and `idle` otherwise. `what` is the `cwd` basename from the transcript's first lines.
   - **Helper:** `model` is the newest assistant line's `message.model`. `started` is the transcript's first timestamp. `turns` and `context` come from its `builders[]` row when one exists, else from counting assistant messages and reading the newest message's input plus cache tokens; the window is `-`. `cost` sums the usage of each distinct `message.id`, priced by `claude-costs`' `predicted_cost`. The last tool is the newest `tool_use` name and its line's timestamp. `state` is `done` when the newest assistant message has `stop_reason: end_turn` or its last tool is `SubagentHandback`, `busy` when the newest line is under 120 s old, and `quiet` otherwise. `what` is the meta file's `description`, at most 40 characters.
   - **Local rows:** `cost` reads `0`.
   - **Unknown values** print as `-`.
4. Never print or keep prompt, result or tool-input text. Only ids, model and tool names, numbers, timestamps and the `what` labels leave the tool; `claude-api-agent`'s logging rule (`:797-801`) holds here too.
5. `--json` prints `{"generated", "since_min", "agents": [{"id", "session_id", "agent_id", "parent", "lane", "model", "started", "elapsed_s", "turns", "context", "window", "cost_usd", "last_tool", "last_tool_at", "state", "what"}]}`, with null for an unknown value. The text form is one header line and one fixed-width line per row; an empty table prints the header and `no agents in the last N min`.
6. Exit codes (portfolio entry 25): 0 whenever the read works, an empty table included; 1 when the sessions dir cannot be read; 2 on a usage error. `--watch N` (N ≥ 1) redraws every N seconds until SIGINT, which exits 0.
7. Paths: `CLAUDE_AGENTS_SESSIONS_DIR` overrides the sessions dir. The ledger is found as agentroute finds it (`AGENTROUTE_LOG`, `AGENTROUTE_STATE_DIR`, `XDG_STATE_HOME`).
8. Bounded reads: a transcript's first 4 KB and last 64 KB. The cost scan is the only exception: it streams a helper's file once per run, and under `--watch` it resumes from the last offset. Only the ledger's last 2 MB is read.
9. Prices, from the claude-api skill's table (cached 2026-10-06, first-party list rates):
   - `PRICES` gains `claude-opus-5-5` (4.00, 20.00), `claude-fable-5-1` (10.00, 50.00), `claude-sonnet-5-5` (2.00, 10.00) and `claude-haiku-5-5` (0.10, 0.50).
   - A per-model cache-read rate in $/M overrides `CACHE_READ_MULT` in `predicted_cost` where the list names one: `claude-opus-5-5` 0.20, `claude-sonnet-5-5` 0.20, `claude-fable-5-1` 0.25.
   - `claude-sonnet-5` stays at 3/15, the billed rate the comment at `:62-68` records. `price_table_drift` stays as it is.
   - Haiku 5.5's long-prompt tier ($0.50/$2.50 above 100K) goes to `NICE_TO_HAVE.md` as S4.
   - `claude-agents` loads `claude-costs` by `SourceFileLoader`, as the tests do; no shared module in this slice.
10. `commands/agents-status.md` replaces `commands/local-status.md`. It runs `claude-agents status`, then `agentroute --check`, and relays both plainly; it starts nothing. The README's tool and command tables name it, and nothing else names `local-status`.
11. `Makefile`: `TOOLS` gains `claude-agents`, `test` runs `tests/test-status.py`, and `check` syntax-checks `bin/claude-agents`.

## 3. Interfaces
The `--json` object is the contract that a later mod (the band above the prompt) reads. Slice two adds rows with lane `api`: `claude-api-agent` writes a `run.json` at launch and a metadata-only `progress.json` from stream-json, and fanout writes its shards' state. It changes no field.

## 4. Findings that name this row
The owner's review: the agents section's status sketch, and its S3 price-table finding (`claude-costs` `:45-57`).

## 5. Forbidden reads
Transcripts whole: the builder greps or tails them, and only the tool streams them. Anything under `~/.local/state/agent-relay`.

## 6. Report
At most 200 words:
- each act's commit
- each test, red before and green after
- each acceptance line's result
- the live run's row count and its header line
- the choices made

## 7. Charter (builder sitting 2026-10-13)
- goal: rulings 1-11 above, the acceptance lines green. budget: one sitting, at most 90 tool calls. pin: branch `a-s3-status`, worktree `.claude/worktrees/a-s3-status`, off 08c0fb9.
- acts:
  1. red tests (test-status.py, the 5.x rows in test-costs.py). done: red, 58 and 14 failed
  2. the price table and `predicted_cost` (ruling 9). done: test-costs 66/0; two S4 rows filed
  3. bin/claude-agents (rulings 1-8). done: test-status 63/0 under python 3.9 and 3.14
  4. /agents-status replaces /local-status; Makefile; README. done: make check 0, make test 0
- fix round (the refuters' BLOCK on 573330d; `agents/local-*.md`, `.claude-plugin/*.json` join `may touch`):
  5. red tests: the surviving mutants and acts 6-8. done: red, 77 passed, 21 failed
  6. bad values read null, a guard per row, strict JSON, `--watch` over 86400 exits 2 (B F1, B F8). done: 86/12
  7. `what` is a top-level cwd, head then tail (A F1, A F4, B F5); control characters replaced (A F5). done: 91/7
  8. a live helper keeps its seat live (A F2); no turn-ended: busy under 120 s, else quiet (A F6, B F7); local seat only when all its no-agent rows are; seat cost is measure.json's (A F3). done: 98/0
  9. the renames; S3 out; B F3, B F4, B F6 and a routed-session note in as S4; an `agent-` prefix check. done: 99/0. Mutants M1, M2, M3, M4, M6, M6c, M7, M12, M13 caught; M14 (keep the cut tail line) survives, near-equivalent
- choices (reversible, the builder's):
  - a helper is local on a `route: local` row; a seat when all its no-agent rows route `local*`; a ledger agent id loses `agent-`.
  - a helper's context from builders[] is `max_context`; its start is the first parsed timestamp, else the file's birth time.
  - `<synthetic>` and all-zero usage are skipped; any other unpriced model makes the cost null, never partial.
  - times outside 2000-2100, counts outside 0-1e13 and costs outside 0-1e9 read null; control and bidi characters become `?`.
  - JSON `id` is the full id; a helper's `parent` is its seat; `since_min` is null under `--all`. Text drops `claude-`; under half a cent prints `<$0.01`.
  - `--watch --json` prints one object per line; text clears only on a tty; no verb exits 2.
- handover:
  - decide, owner: the coordinator. `efficiency()`, the local equivalent and `--check-prices` keep the global cache-read multiplier (S4). Consumer: a later claude-costs packet.
- exit: done, acts 1-9 on branch a-s3-status. After act 9: make check 0; test-status FAIL 0 (99 passed); make test 0 in 35 s, once, a fake claude first on PATH, no router before or after; live `--json` parses (0); `frobnicate` 2; `/nonexistent` 1. Live: 11 rows in 0.5 s; no output committed.
