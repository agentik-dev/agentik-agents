# Sitting 2026-11-23-5: agentik-agents, ra1-agents-ready, the records-out rehearsal

| item | value |
|---|---|
| goal | the brief's R1 to R6: a scratch clone of this branch with every record removed and `records: out` declared runs the whole `make check` with no key and with the key set to a holder's copy; a test's red is mended in tests alone; nothing under `plugin/` |
| budget | about 90 tool calls, `claude-opus-5-5` |
| pin | main 4e1b3da (1.10.0); worktree `.claude/worktrees/ra1-agents-ready`, branch `ra1-agents-ready`; nothing linked |
| window | builder, one sitting, spawned by an hq sitting of 2026-11-23 |
| agents | none |

## Done-ness
- [x] act 1: the packet and this page; doclint, recordlint and hygiene (tree and `--commits main..HEAD`) at 0.
- [x] act 2: R1 and R2: the scratch clone of 6e08f1d less its 81 records (`history/` 43, `design/packets/` 37, `NICE_TO_HAVE.md` 1; no `bugs/`, `HANDOFF.md`, `OPEN-QUESTIONS.md`, `relay/queue.yaml` or `.hygiene-live`), `records: out` declared, the holder's copy committed apart; `agentik records` prints `state: unset`; the whole check exits 0 in 302 s on the clone's head, nothing red.
- [x] act 3: R3: `agentik.records` set to the holder's copy; `agentik records` prints `state: out`, `prefix: repos/agentik-agents`; the whole check exits 0 in 303 s on the same head, nothing red.
- [x] act 4: R4: nothing turned red, so no mend and the branch holds this packet and this page alone; R6's `scribe.md` read by no check. R5: nothing under `plugin/`; this page committed, the check in this worktree queued once on its head.

## Handover
- If cut: the first unticked line above.

## Next act
The worktree check's result; the review; the landing (no version moved, so no install); then the move's own row.

## Exit
Every ruling built and committed; both rehearsals green, nothing red; the worktree check queued on the head, its result the coordinator's.
