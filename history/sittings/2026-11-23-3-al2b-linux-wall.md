# Sitting 2026-11-23-3: agentik-agents, al2b-linux-wall, the stub's removal

| item | value |
|---|---|
| goal | the fourth brief: the stub `fanout()` leaves the dispatcher (R1, R2), its tests replaced (R4), the rig test's two macOS-only assumptions mended (R8), two wish-list rows (R5), the records current (R6), 1.10.0 alone last (R7) |
| budget | about 90 tool calls, `claude-opus-5-5` |
| pin | worktree `.claude/worktrees/al2b-linux-wall`, branch `al2b-linux-wall` at 6836375 (1.10.0), main 9c5aa33 (1.9.11); nothing linked |
| window | builder, one sitting, spawned by an hq sitting of 2026-11-23 |
| agents | none |

## Done-ness
- [x] act 1: R1, R2, R4: the stub gone from the dispatcher; its cases in `tests/test-dispatch.sh` replaced (11 of 13 red at 6836375, the two with a file pass there through the temp HOME's line), `test-bare-machine.py`'s test 13 and `test_al4_report.py`'s `test_launcher` mended, red at the old dispatcher; `plugin.json` at 1.9.11.
- [x] act 2: R8: `tests/test-rig.sh`'s chmod and stat cases; under a GNU-like `chmod` and `stat` first on PATH, 77 passed, 2 failed before, 79 passed after; 79 passed here plainly. No other `stat -f` pair in `tests/`, `plugin/lib/` or `scripts/`.
- [x] act 3: R5, R6: n70 and n71 from review 2's N1 and N2; the packet's "Not built" line says R6 and R7 are built; `design/04-api-lane.md`'s stub sentence and the README's lane paragraph say what `fanout` does now. doclint and recordlint at 0.
- [x] act 4: R7: 1.10.0 alone in the last commit under `plugin/`; every suite of `test` by hand under both interpreters, lint, doclint, hygiene at 0; the check queued once on this commit.

## Handover
- If cut: the first unticked line above.

## Next act
The check's result; the owner's run of the three lines on Linux at this head; the landing.

## Exit
Every ruling of brief 4 built and committed; the check queued on the head, not waited on.
