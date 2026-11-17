# Sitting 2026-11-16-3: agentik-agents, ag1-old-name-links, the fix of review 1

| item | value |
|---|---|
| goal | packet `design/packets/ag1-old-name-links.md`, review 1's ruling: F1 built; F2 and the leads to NICE; F3 in the packet |
| budget | about 60 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `00b3393` on the branch, main `95cfbbc`, plugin 1.9.5 (never released) |
| branch | `ag1-old-name-links`, worktree `.claude/worktrees/ag1-old-name-links` |
| level | S3 |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] F1's test, `T` test_10 (a prefix with a space, a process named by `<bin>/agentroute`, three installs), seen red at `c8522cc`: the link stays on the removed first tree; `T`'s `tree()` reads a path with a space
- [x] F1: `held_old` holds a name only where its link's target stands after the prune; `T` 1 to 8 and 10 green by hand (9 runs make: the gate's)
- [x] NICE n65 (F2) and n66 (the four leads the pin shares); the packet's sentence for F3, and F1's condition in its section 3
- [x] 1.9.6, alone in the last commit under `plugin/` (1.9.5 was never released)
- [x] `make check` through the gate on `2a24ccc`: job `20261116-185255-2217`, exit 0 (`T` 1 to 10 green in its log); hygiene `--require-private --commits main..HEAD` exit 0

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
The coordinator's read and the landing; nothing open in this sitting.

## Exit
closed: review 1's ruling built, the check green on `2a24ccc`; this file's close is the one commit after it
