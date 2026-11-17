# Sitting 2026-11-16-2: agentik-agents, ag1-old-name-links

| item | value |
|---|---|
| goal | packet `design/packets/ag1-old-name-links.md`: a tool started by an old name keeps its frozen tree through later installs |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `95cfbbc` on main, plugin 1.9.4 |
| branch | `ag1-old-name-links`, worktree `.claude/worktrees/ag1-old-name-links` |
| level | S3 |
| agents | 0 |

## Done-ness
- [x] the packet, with the finding's reproduction measured at the pin in a temp HOME
- [ ] R7, the tests seen red at the pin (`tests/test_ag1_old_names.py`, in `make test`)
- [ ] R1 to R4: the new form, the hold over a running process, the dispatcher's old-name exec
- [ ] 1.9.5, alone in the last commit under `plugin/`
- [ ] `make check` through the gate; hygiene `--require-private --commits main..HEAD` exit 0

## Handover
- If this sitting is cut: the first unticked line above.

## Exit
open
