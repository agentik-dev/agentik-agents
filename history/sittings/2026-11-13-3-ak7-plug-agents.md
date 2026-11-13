# Sitting 2026-11-13-3: ak7-plug-agents, the fix of review 2

| item | value |
|---|---|
| goal | review 2's R2-F1 to R2-F4 fixed, each behind a test seen red at 0dcb9ba; its NICE notes filed; 1.7.1; the gate once, last |
| budget | 90 tool calls; `claude-opus-5-5`; one commit per finding |
| pin | worktree `.claude/worktrees/ak7-plug-agents`, branch `ak7-plug-agents` at 0dcb9ba, off main 2c18f11 |
| window | builder, one sitting, spawned by a hq sitting of 2026-11-13 |
| agents | none |
| exit | done: R2-F1 to R2-F4 fixed, n24 to n32 filed, 1.7.1; gate 20261113-111715-1559 exit 0 on 3deaa9c; record handed to the hq |

## Done-ness
- [x] act 1: R2-F1, a non-finite number at any depth of a value is its text (test_15).
- [x] act 2: R2-F2, a backend name outside `[a-z0-9_-]` is left out with one warning (test_16).
- [x] act 3: R2-F3, backends read from `AGENTROUTE_BACKENDS` print its launch line (test_17).
- [x] act 4: R2-F4, a field the router fills takes its feed's source and rows (test_18); n11 lands with it.
- [x] act 5: review 2's NICE notes as n24 to n31 (N1, N3, N4, N6 to N10); N5 landed with R2-F3 and N2 is n19, so neither is a row; n7 (R2-F2) and n11 (R2-F4) left as landed.
- [x] act 6: 1.7.1 alone at 3deaa9c, last under `plugin/` (plugin-version-check passes; README has no stamp).
- [x] act 7: gate 20261113-111715-1559 exit 0 in 2 min on 3deaa9c; n32 (the coordinator's ask, after the gate) in the closing commit.

## Decided (reversible, logged)
- R2-F1: `plain()` walks a copy of lists and mappings with a stack, not by recursion, so a value nested as deep as `json.loads` takes cannot fail the read.
- R2-F2: the review's first option. The warning is reason `unknown`, key `backends.<name>` as written, `path` the file or null for the variable; no stderr line. A slug would make a key no file holds.
- R2-F3: the review's fix. The condition is the variable set and not empty, as the router reads it, so a router-made default and an unparseable variable take the launch line too: the router reads no file in either case.
- R2-F4: the review's fix, for every field the layer leaves out: url and model take `route.local_url`/`route.local_model`'s source and `values`; auth and fold_system, filled with a constant, take source default. That also lands n11, whose row leaves in act 5. `default` stays null for a declared backend's keys: on a bare machine the backend does not exist.

## Handover
- decide, owner: the coordinator. `route.state_dir`'s new summary came after 1.7.1 and the gate, so it is not placed. The sentence is `The folder that holds the router's pid file and, by default, its request log.`; no test pins the old one. Its consumer is the landing.

## Next act
- None in this row: the coordinator reads the diff and lands.
