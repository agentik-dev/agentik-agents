# Sitting 2026-11-16-1: agentik-agents, ia1-new-machine

| item | value |
|---|---|
| goal | packet `design/packets/ia1-new-machine.md`: no old name's link on a new machine, a person's own file passed over with exit 0, a status table that answers with no session plugin |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `649651c` on main, plugin 1.9.3 |
| branch | `ia1-new-machine`, worktree `.claude/worktrees/ia1-new-machine` |
| level | S3 |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet, with the baseline measured at the pin in temp homes
- [x] R7, the tests seen red at the pin: bare-machine 1, 3, 5, 6; al6 InstallTest four; plug 8, 10; status two (bare-machine 15, our four links refreshed, green at the pin)
- [ ] R1 and R2, install-cli
- [ ] R3, the doctor
- [ ] R4, R5 and R6, status, its command and the README
- [ ] 1.9.4, alone in the last commit under `plugin/`
- [ ] `make check` once through the gate; hygiene over `main..HEAD`

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
R1 and R2 in `plugin/lib/agents_install.py`, and `make uninstall` silent on an absent old name.
