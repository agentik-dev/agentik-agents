# Packet al1-run: one API-lane shard, from its type to its record

The coordinator's brief for row al1, in this repo's packet shape. Three rows build beside it from the same pin (al2 the wall and the key, al3 the fan-out and its day's log, al4 the report and the verbs); a join merges the four. This row writes only the files its `may touch` row names.

| item | value |
|---|---|
| from | the coordinator's brief al1-run and its seams page (design/21 §5, as amended 2026-11-13): design/21 §3.1 items 1 to 3, §3.5 items 25, 28, 29, 31, §9 R1-F5; this repo's `design/04-api-lane.md` |
| pin | agents main `c0193bd` (plugin 1.6.3); branch `al1-run`, worktree `.claude/worktrees/al1-run`, cut there |
| wall | this worktree; no push, `--amend`, rebase, merge, install or version; no `make` (the join runs the gate); no real `claude`, no model run, no request to any API: every test runs `tests/fake-claude` on a PATH built from nothing in a temp home; no key read or printed, made-up keys only; no test writes under the real home |
| may touch | new: `plugin/lib/apilane/__init__.py` (one docstring), `types.py`, `argv.py`, `env.py`, `classify.py`, `proc.py`, `run.py`; `tests/test_al1_run.py`; `tests/fake-claude`; this packet; the charter `history/sittings/2026-11-13-2-al1-run.md`. Not: the `Makefile`, `.hygiene-allow`, `plugin.json`, the dispatcher, the hooks, the README, `NICE_TO_HAVE.md`, any other file under `apilane/` |
| acceptance | `python3 tests/test_al1_run.py TypesTest`, `ArgvTest`, `FindClaudeTest`, `EnvTest`, `ClassifyTest`, `ProcTest`, `RunTest`, `SecretsTest`, `RecordTest`, `FakeIsFakeTest`, each under the pin's interpreter and `/usr/bin/python3`, each ends `OK`; `scripts/hygiene` exits 0; `scripts/doclint` exits 0; `python3 -c "import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]" plugin/lib/apilane/types.py` exits 0 (and so for each module). Baseline at `c0193bd`: `ls plugin/lib/apilane` prints `No such file or directory`; the test file does not exist |
| verify | none: the join's gate; the suite by hand under both interpreters |
| budget | One commit per ruling group by explicit path, the packet first; `claude-opus-5-5`, high; about 90 tool calls |

## 1. What the source says (quoted)

The owner's words:

"I need a Fable designer to recover the claude fanout to API lane agents. I want this designed and brought up to the current standards of our existing plugins. When the API lane is enabled, I'd like you to report how many agents are running within that session and what types. If the API lane is disabled we shouldn't see anything beyond what we see today."

## 2. Rulings

- R1, what this row owns: the files above. It prints nothing and holds no sentence a user reads: it returns a `ShardResult` or raises an error with a `code` (`claude.none`, fields `path`).
- R2, the types. `types.TYPES` maps `review`, `explore`, `analyze` to `Type(name, model, tools, schema)`; `tools` is `("Read", "Grep", "Glob")`; `review` and `explore` run `claude-sonnet-5-5`, `analyze` `claude-opus-5-5`, the newest Sonnet and Opus the status tool's `PRICES` holds at the pin. `schema` is the review's findings schema as the old wrapper had it, else `None`. Each type's system prompt and effort come back as they were. No writing type.
- R3, the argv. `argv.build(shard, *, claude, dirs, ceiling_usd, run_dir, restricted=True) -> list`: `claude` first, `--bare` second; `--tools "Read Grep Glob"`, the old deny rules, `--permission-mode dontAsk`, `--output-format json`, `--model`, `--max-budget-usd` at the ceiling, one `--add-dir` a dir; new `--permission-prompts none`, `--no-session-persistence`, and `--restricted` when `restricted`. No key, token or base URL is an argument; no pass-through.
- R4, the binary. `argv.find_claude(path=None) -> str`: the real path of the first `claude` on `path` that is an executable regular file once resolved; else `claude.none`. Under the wall the PATH name, a link inside the home, does not start; the resolved path does.
- R5, the environment. `env.build(*, key, run_dir, home, path, proxy=None, ca_file=None, base_url=None) -> dict`, an allow-list: `PATH`, `HOME`, `LANG`, `TERM`; `TMPDIR` and `CLAUDE_CONFIG_DIR` under `run_dir`; `ANTHROPIC_API_KEY`; the proxy and CA names when given; `ANTHROPIC_BASE_URL` only when `base_url` is given.
- R6, the classifier. `classify.py` holds `classify` and the four validators as they were. An empty result, a placeholder summary, a review with no finding under the job's dirs and a budget abort each read as a named state, never `ok`. New: a result holding the key's value or an age secret key's prefix reads `leak`, and its text is neither written nor returned.
- R7, the process reader. `proc.started(pid)` and `proc.alive(pid, started)`, by `ps -o lstart= -p <pid>` alone, so a recycled pid is never alive; green on Linux too.
- R8, the run. `run.run_shard(shard, *, grant_usd, fanout, number, session, roots, lane, claude, dirs, timeout_sec, restricted=True, wrap=None, key=None) -> ShardResult(label, type, state, cost_usd, estimated, result_path, reason, model)`. `key` is called once, at the spawn; `wrap(argv, read=dirs, write=[run folder], net="all", home=roots.home)`; own process group; at `timeout_sec` the group gets TERM then KILL, state `timeout`; the ceiling is `grant_usd / 1.35`; a wall that does not start is `wall`; the CLI's budget abort is `ceiling`, its result discarded and its billed cost kept; no cost figure books the grant, `estimated` true.
- R9, the record. `<state>/runs/<fanout>-<NN>/run.json`, written at the start (`pid`, `pid_started`, `grant_usd`, `state` `running`) and rewritten by one rename at the end (`rc`, `ended`, `cost_usd`, the final `state`); the result and stderr beside it; folders 0700, files 0600; no prompt, result text or key in `run.json`.
- R10, the fake. `tests/fake-claude`, first on a PATH built from nothing; it records its argv, environment and stdin to a file the test names, and by its scripted mode prints an envelope with a cost, without one, an empty result, a placeholder, a budget abort, one echoing its key, or sleeps.
- R11, the port. Every old shell case on the argv, the flag pins and the run path, and every old Python case on `classify` or a validator, ported unweakened; the pool's cases are al3's.

## 3. Interfaces

The seams page's §1 to §4 and §8, as the brief repeats them above. `ShardResult.state` is one of `ok failed ceiling empty placeholder timeout leak wall`; `reason` is `None` or a code (`exit:3`, `timeout:900`, `wall:65`, `no-cost`, `invalid:<what>`). `run.json`: `schema` `agentik.api.run/1`, `id`, `pid`, `pid_started`, `type`, `model`, `label`, `session`, `fanout`, `grant_usd`, `started`, `state`; then `rc`, `ended`, `cost_usd`. Times UTC, ISO 8601 with `Z`.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

A file over 8 KB whole; a relay ledger or a reference snapshot whole; anything under a `secrets` folder or a key store.

## 6. Report

The coordinator's record: each acceptance line, its result at the pin and now; each old case against the new test that holds it, and each left to al3; the choices made inside the rulings.
