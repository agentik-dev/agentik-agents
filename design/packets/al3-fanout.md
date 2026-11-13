# Packet al3-fanout: the job, the pool, the day's log with its reservation, and the fan-out

The brief as the coordinating hq wrote it, in this repo's packet shape. One of four rows built from one pin (al1 one shard's run, al2 the wall and the key, al4 the report and the verbs); a join merges them. The shared seams are design/21 §5 as amended 2026-11-13, in the hq.

| item | value |
|---|---|
| from | the hq's design/21 §3.2 item 10, §3.4 item 18, §3.5 items 24 to 26, §9 R1-F1; the hq's entries 6 and 37; this repo's `design/04-api-lane.md`; the old fan-out at d8ca583 (`BudgetPool`, `kill_all`, `load_tasks`, `main`) and its test |
| pin | agents main c0193bd, plugin 1.6.3; worktree `.claude/worktrees/al3-fanout`, branch `al3-fanout`, cut there; `ls plugin/lib/apilane` prints `No such file or directory` and the test file does not exist |
| wall | this worktree; no push, `--amend`, rebase, merge, install or version; no `make` (the join runs the gate and the bump); no `claude` started, real or fake; no key read, no request to any API; no test writes under the real home or reads the real `usage.jsonl`; a signal goes only to a child the test started |
| may touch | `plugin/lib/apilane/job.py`, `pool.py`, `ledger.py`, `fanout.py`; `tests/test_al3_fanout.py`; this packet; a charter under `history/sittings/` |
| acceptance | `python3 tests/test_al3_fanout.py JobTest`, then `PoolTest`, `LedgerTest`, `LedgerRaceTest`, `PlanTest`, `OrderTest`, `RunTest`, `KillTest`, `SignalTest`, each ending `OK`, under the pin's interpreter and under `/usr/bin/python3`; `scripts/hygiene` exits 0; `scripts/doclint` exits 0 |
| verify | none in this row: the join's `make check`; here the suite by hand under both interpreters |
| budget | about 90 tool calls; `claude-opus-5-5`, high; one commit per act |

## 1. What the source says

The owner: "When the API lane is enabled, I'd like you to report how many agents are running within that session and what types. If the API lane is disabled we shouldn't see anything beyond what we see today." This row is the part that holds money: a fan-out that dies has already counted.

## 2. Rulings

1. **What this row owns.** The four modules and the test, nothing else, and no `apilane/__init__.py` (the package imports as a namespace until the join). The modules print nothing: they call the `emit` they are handed, return a value, or raise an error with `code` and `fields`. No process starts but through the `run_shard` handed in.
2. **The job.** `Shard(label, type, prompt)`; `Job(id, budget_usd, dirs, shards, max_shard_usd, jobs, timeout_sec)`. `job.load(source)` reads a JSON file or `-` of schema `agentik.fanout.job/1`. `budget_usd` is required and above 0; `jobs` is 4 and `timeout_sec` 900 unless given. An unknown key, a wrong kind or empty `shards` is `job.shape` (`field`, `why`); an unknown type `job.type`; an id that is not a letter or digit then at most 63 letters, digits or dashes is `job.id`, and a missing one is `f-<UTC stamp>-<4 hex>`. A label is at most 80 printable characters, `s<n>` when left out.
3. **The short form.** `job.from_argv` takes `--budget-usd N [--profile TYPE] [--tasks FILE] [--add-dir D]... [-j N] [--max-shard-usd N] [--timeout-sec N] [--id ID] PROMPT...` and returns the job its JSON twin would. `--profile` defaults to `review`; `--tasks` reads a JSON array, JSON lines or plain lines. `--model`, `--out`, `--claude-arg`, `--phase` and `--stagger-sec` are `job.flag`. `job.parse` picks the short form when `--budget-usd` is given, else one `JOB` argument.
4. **The pool.** `BudgetPool` as it was. A grant is `min(max_shard_usd or budget/shards, free)`; under `FLOOR_USD = 0.0675` (`0.05 * 1.35` in floats) it is not started.
5. **The day's log.** `<state>/usage.jsonl` under a `flock` on `usage.lock`. The day is the UTC date. The day's sum is, for each reservation of the day, its settle's `spent_usd`, else its whole `budget_usd`; nothing releases a reservation. `reserve` refuses `id.used` and `budget.day`, else appends one line and syncs it before it returns. A line it cannot read is `log.fault`, never an empty day. Lines older than 7 days leave at a reservation, by a rename. Folder 0700, files 0600.
6. **The plan, the dry run.** Refuses, in order: `lane.off`, `limit.unstated` (one line that can leave), the wall's `check_dirs`, `budget.fanout`, `budget.day`. It starts, opens, runs, writes and makes nothing.
7. **The run, one order.** Plan; `ensure_probe(claude)` (a `restricted` of null runs every shard with `restricted=False`); `key()` once; `ledger.reserve`, then `emit("reserved")`; the live record, then the shards, at most `jobs` at once. Each shard: a grant, or `skipped` (`floor` or `budget`); else `shard.start`, `run_shard`, `ledger.book`, the pool's settle, the live record, `shard.end`. At the end the settle, the record closed, `done`. `rc` 0 when every shard is `ok`, else 1; nothing retries.
8. **The live record.** `<state>/live/<session or none>/<fanout>.json`, one rename at every change and at least every 10 s with a new `beat` and `emit("beat")`; at the end a session's record keeps `ended`, a `none` one is removed.
9. **A stop.** SIGINT, SIGTERM, SIGHUP, on the main thread only: no new shard; each running shard's process group, from its `run.json`, gets TERM and 2 s later KILL, and is booked at its grant, estimated; the settle and the closed record follow. The money never waits on this: the reservation is already the line the day's sum reads.

## 3. Interfaces

The seams' §6 and §8 (in the hq's design/21 §5): `job.load`, `job.from_argv`, `job.parse`; `ledger.reserve`, `book`, `settle`, `day`; `fanout.plan`, `fanout.run` and `FanoutResult(id, rc, spent_usd, budget_usd, shards)`; the events `plan`, `reserved`, `shard.start`, `shard.end`, `beat`, `done`; the records `usage.jsonl` (`agentik.api.usage/1`) and `live/` (`agentik.api.live/1`). Every function of another row is a keyword argument whose default, `None`, imports the real one inside the call.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

A file over 8 KB whole; a relay ledger or a reference snapshot whole; the real `usage.jsonl`; anything under a `secrets` folder or a key store.

## 6. Report

The branch and sha; each act's commit; each test class at the pin and now under both interpreters, with how each failed first; each old pool case against the test that holds it, and each left to al1's classifier.
