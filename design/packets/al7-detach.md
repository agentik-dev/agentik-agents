# Packet al7-detach: a detached fan-out, its wait, status and stop, a run named by its id, a tag, and a count that holds with no parent

The hq's brief for row al7, in this repo's packet shape.

| item | value |
|---|---|
| from | the hq's row al7 (design/21 §10, amendment 2, and its items 10, 18 to 21 and 24 as amended) |
| pin | main 14f146d, plugin 1.8.1 (al6-join merged); worktree `.claude/worktrees/al7-detach`, branch `al7-detach`; nothing linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or landing; no `claude`, no model, no key read, no network; no relay verb; `make` only through the gate queue |
| may touch | `plugin/lib/apilane/runs.py` (new), `cli.py`, `job.py`, `messages.py`, `report.py`, `proc.py`; `plugin/lib/agents_plug.py`; `tests/test_al7_detach.py` and its capture; `tests/test-dispatch.sh`; `Makefile`; `NICE_TO_HAVE.md`; `plugin/.claude-plugin/plugin.json`; this packet; a charter |
| untouched | `fanout.py`, `ledger.py`, `pool.py`, `run.py`, `wall.py`, `key.py`, `probe.py`, `plugin/lib/agentik-agents` |
| acceptance | section 5's lines 1 to 15 |
| verify | `make check`, once, last, through `agentik session gate run`, then `gate wait --strict` |
| budget | a commit each: packet, the tests seen red, the tag and the verbs, the count and the plug, the lists and NICE, 1.9.0 alone |

## 1. What the source says

The owner: "When the API lane is enabled, I'd like you to report how many agents are running within that session and what types." Of his own tool's forms for a run that outlasts a Bash call: it "keeps a run alive past the harness's reaper", and "exit 124 means still running". No code comes from that machine; the forms are design/21 §10's.

Baseline at 14f146d, a temp home with the lane on: `fanout --detach --budget-usd 0.5 p` exits 2 (`--detach is not a flag of the fan-out`); `fanout wait` exits 2 (`the job's job is wrong: unreadable`).

## 2. Rulings

The brief's R0 to R10, as the hq wrote them; their short form:

- R0: the seven money and wall modules and the dispatcher untouched; the foreground's stdout, stderr and exit byte-equal to the pin's but for `id.used`'s sentence.
- R1: `<state>/fanouts/<id>/`, 0700, files 0600 by one rename: `start.json` at the `reserved` event, `fanout.json` (the `--json` object plus `tag` and `ended`) after the run returns, in both forms; SIGTERM ignored from the run's return to that write. `runs.py` holds the folder, the three verbs and the sweep, prints nothing, raises a `code`.
- R2: `--detach`: the plan and the ask the parent's; the bound `ceil(shards / jobs) x timeout_sec` over 86400 s is `job.long`; the latest-end line; an exclusive `mkdir` (`id.used`); `fanout - --yes` in its own session, the job on its stdin, its output `log.txt`; the parent polls, never signals, returns the id at `start.json`, 1 with `reserved ... counts whole`, the child's own exit with no reservation, 124 after 120 s. The `child` argument of `cli.main` is the test seam.
- R3: `wait [ID] [--timeout SEC] [--json]`; R4: `status [ID | --all] [--json]` and the plug's read while the lane is on; R5: `stop [ID]`.
- R6: a record is live while its fan-out or any run of it lives; a gone fan-out drops `queued` and closes `fan-out <id> is gone: agentik agents fanout stop <id>`; `ps` under `TZ=UTC`.
- R7: the id's and the tag's pattern ends at `\Z`; `--tag` and key `tag`, `job.tag`; `--phase` refused; `id.used` names `--tag`.
- R8: `fanout.help` §10.1's block, `hook.on` A2-12's line; the three verbs answered with the lane off, before its off answer; `--detach` with the lane off the off line.
- R9: the sweep at a non-dry fan-out's start, never raising. R10: the lists, NICE rows, 1.9.0 alone, `make check` once.

## 3. Interfaces

- `cli.main(argv, *, roots=None, parts=None, stdin=None, stdout=None, stderr=None, child=None)`; `cli.default_child(env=None)` is the dispatcher's `lane_py` prefix.
- `runs.make(roots, fid)`, `runs.read(roots, fid)`, `runs.wait(...)`, `runs.status(...)`, `runs.stop(...)`, `runs.sweep(roots, ...)`; `runs.RunError(code, **fields)`.
- `Job` gains `tag`, last, default `None`. `agents_plug.describe(version, lane=None, roots=None)`.

## 4. Not built

A daemon or queue; a stop at a session's end; a cap on runs at once; a roll-up tool; a writing type; the Linux wall and the stub's removal (al2b); the band (al5).

## 5. Report

`T` is `tests/test_al7_detach.py`, run under the pin's interpreter and `/usr/bin/python3`. Lines: 1 `git diff --stat 14f146d --` R0's modules and the dispatcher prints nothing; 2 `T FormsTest`; 3 `T DetachTest`; 4 `T RefuseTest`; 5 `T ReaperTest`; 6 `T CeilingTest`; 7 `T WaitTest`; 8 `T StatusTest`; 9 `T StopTest`; 10 `T CountTest` and `tests/test_al4_report.py`; 11 `T WorkLinesTest`; 12 `T SweepTest`, `T SentenceTest`; 13 `tests/test_al4_off_golden.py`, `tests/test-dispatch.sh`; 14 1.9.0, hygiene, doclint; 15 `make check` through the queue, `test_al7_detach`'s `===` line twice.
