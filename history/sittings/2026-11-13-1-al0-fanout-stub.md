# Sitting 2026-11-13-1: al0, the fanout verb as a pass-through stub

| item | value |
|---|---|
| goal | packet `design/packets/al0-fanout-stub.md`: the dispatcher's `fanout` verb hands the call to the old fan-out tool on PATH, `--yes` dropped before `--`; plugin 1.6.4 |
| budget | 90 tool calls; `claude-opus-5-5`, high; one commit per act |
| pin | worktree `.claude/worktrees/al0-fanout-stub`, branch `al0-fanout-stub`, off main c0193bd (plugin 1.6.3) |
| window | builder, one sitting, spawned by a hq sitting of 2026-11-13 |
| agents | none |

## Done-ness
- [x] act 0: this packet and this charter (the scan reads no old name under `design/`, so no allow row).
- [ ] act 1: the failing tests (dispatch and bare machine), red at the pin.
- [ ] act 2: the verb, the head comment, plugin 1.6.4.
- [ ] act 3: `make check` once through the gate queue.

## Decided (reversible, logged)

## Handover

## Next act
act 1.

## Exit
