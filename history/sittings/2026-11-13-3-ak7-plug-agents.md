# Sitting 2026-11-13-3: ak7-plug-agents, the fix of review 2

| item | value |
|---|---|
| goal | review 2's R2-F1 to R2-F4 fixed, each behind a test seen red at 0dcb9ba; its NICE notes filed; 1.7.1; the gate once, last |
| budget | 90 tool calls; `claude-opus-5-5`; one commit per finding |
| pin | worktree `.claude/worktrees/ak7-plug-agents`, branch `ak7-plug-agents` at 0dcb9ba, off main 2c18f11 |
| window | builder, one sitting, spawned by a hq sitting of 2026-11-13 |
| agents | none |
| exit | (open) |

## Done-ness
- [x] act 1: R2-F1, a non-finite number at any depth of a value is its text (test_15).
- [ ] act 2: R2-F2, a backend name outside `[a-z0-9_-]` is left out with one warning.
- [ ] act 3: R2-F3, backends read from `AGENTROUTE_BACKENDS` print its launch line.
- [ ] act 4: R2-F4, a field the router fills takes its feed's source and rows.
- [ ] act 5: review 2's NICE notes N1 to N10 as rows.
- [ ] act 6: 1.7.1 alone, last under `plugin/`.
- [ ] act 7: the gate, once.

## Decided (reversible, logged)
- R2-F1: `plain()` walks a copy of lists and mappings with a stack, not by recursion, so a value nested as deep as `json.loads` takes cannot fail the read.

## Handover
- None yet.

## Next act
- Act 2.
