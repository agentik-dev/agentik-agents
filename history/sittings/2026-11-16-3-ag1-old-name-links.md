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
- [ ] F1: `held_old` holds a name only where its link's target stands after the prune
- [ ] NICE n65 (F2) and n66 (the four leads the pin shares); the packet's sentence for F3
- [ ] 1.9.6, alone in the last commit under `plugin/`
- [ ] `make check` through the gate; hygiene `--require-private --commits main..HEAD` exit 0

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
F1's fix in `plugin/lib/agents_install.py`, then the NICE rows and the packet's sentence.
