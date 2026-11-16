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
- [x] R1 and R2, install-cli: an old name only where its link stands, a person's file passed over with exit 0 and one stderr line; `make uninstall` silent on an absent old name; install-cli.md and the README's sentence (the dispatcher's help footer is pinned byte for byte by test-dispatch, so it stays)
- [x] R3, the doctor: text and `--json` want `agentik-agents` and `agentik` alone; an old name whose link stands on PATH is a note
- [x] R4, R5 and R6: a missing sessions folder is an empty table, exit 0, one line (stderr under `--json`); `/agents:status` names `/agents:install-cli`; the README's "works alone" holds by R4; NICE n61, n62 leave, n63 (the pinned help footer) is filed
- [x] 1.9.4, alone in the last commit under `plugin/`; the four acceptance probes pass in temp homes; hygiene over `main..HEAD` exit 0
- [ ] `make check` once through the gate; hygiene over `main..HEAD`

## Handover
- If this sitting is cut: the first unticked line above.

## Next act
`make check` through the gate on this commit; on red, read the log and fix.
