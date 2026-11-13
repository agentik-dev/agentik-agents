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
- [x] act 1: the failing tests, red at the pin: test-dispatch 50 passed, 11 failed (every fanout case); bare machine test_13 red (exit 2, the usage lines), test_14 (R8) green, as the pin holds.
- [x] act 2: the verb, the head comment, plugin 1.6.4; test-dispatch 61 passed, 0 failed; the acceptance lines by hand through `plugin/bin/agentik-agents` as the brief reads them.
- [x] act 3: gate 20261113-085844-1510 exit 0 in 1 min, on 17ca453 (test-dispatch 61/0, bare machine 14 OK, hygiene 0 hits, plugin-version-check 1.6.4).

## Decided (reversible, logged)
- The help is read before the `--yes` drop: `fanout --yes --help` hands both on (R5's "the only argument" taken as the caller's).
- R4's "inside" is any depth under `$here`, so a forward in a subfolder of lib/ is refused too.
- R6's byte compare reads c0193bd's dispatcher from git and skips where the object is absent; the retired-verb list loses `fanout`, now a verb.

## Handover
- The landing and the install are hq's; nothing waits on the owner.

## Next act
none: the landing is hq's.

## Exit
done 2026-11-13: acts 0 to 3 committed; gate 20261113-085844-1510 exit 0
