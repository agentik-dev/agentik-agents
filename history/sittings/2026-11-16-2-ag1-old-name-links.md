# Sitting 2026-11-16-2: agentik-agents, ag1-old-name-links

| item | value |
|---|---|
| goal | packet `design/packets/ag1-old-name-links.md`: a tool started by an old name keeps its frozen tree through later installs |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `95cfbbc` on main, plugin 1.9.4 |
| branch | `ag1-old-name-links`, worktree `.claude/worktrees/ag1-old-name-links` |
| level | S3 |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet, with the finding's reproduction measured at the pin in a temp HOME
- [x] R7, the tests seen red at the pin: `tests/test_ag1_old_names.py` 1 to 5, 7 and 8 (6, a new prefix, green at the pin; 9 runs make, so it is left to the gate); bare-machine 15 rewritten to the new target
- [x] R1 to R4: an old name links to the dispatcher in the tree, which execs the tool by its real path; an old-form link a process names is held; `T` 1 to 8 green by hand, test-dispatch and al6 green; NICE n64 (claude-fanout) filed
- [x] 1.9.5, alone in the last commit under `plugin/`; hygiene `--require-private --commits main..HEAD` exit 0 by hand
- [x] the first check, job `20261116-172738-2199` on `c8425e4`, exit 2: every test green, doclint wanted this charter's window row and Next act and the packet's sections 3 and 4 by their names
- [ ] `make check` through the gate again; hygiene `--require-private --commits main..HEAD` exit 0

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
The second check through the gate, then the hand-back; the coordinator's review and the landing after.

## Exit
open
