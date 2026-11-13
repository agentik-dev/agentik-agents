# Sitting 2026-11-13-1: ak7-plug-agents, the plug's reads

| item | value |
|---|---|
| goal | packet `design/packets/ak7-plug-agents.md`: `describe --json`, the config read, `doctor --json`, the lane note, `status --json`'s schema |
| budget | 90 tool calls; `claude-opus-5-5`, high; one commit per act |
| pin | worktree `.claude/worktrees/ak7-plug-agents`, branch `ak7-plug-agents`, off main c0193bd (plugin 1.6.3) |
| window | builder, one sitting, spawned by a hq sitting of 2026-11-13 |
| agents | none |

## Done-ness
- [x] act 0, 252d505: the packet; this charter.
- [x] act 1, 21e96c6: tests seen red (`tests/test-plug.py` 10 of 10, the usage line, the status keys).
- [x] act 2, 1342611: `agents_plug.py`, the dispatcher's verbs, `--check --json`, the lane note, the status schema and prefix; every suite green under `/usr/bin/python3` and 3.12.7.
- [x] act 3, efc795c: NICE_TO_HAVE n7 to n9.
- [x] act 4, 52ad9a9: plugin 1.7.0, alone.
- [x] act 5: gate 20261113-084919-1503 exit 2 in 1 min on 52ad9a9, red at `doclint` only: the packet over 9 KB and out of shape, this charter out of shape.
- [ ] act 6: the packet cut to the ceiling in the repo's six sections, this charter in shape; the gate again.

## Decided (reversible, logged)
- Computed defaults are computed from agentroute's own assignments (`env` giving its default); shell defaults expand `$HOME` and nested `${...:-...}`; an empty one is null.
- `local.` takes what claude-local assigns from `${CLAUDE_LOCAL_*:-...}`; `rig.` every `${LOCALRIG_*:-...}`.
- With no `agents_plug.py` or no python3, the text `doctor` runs `--check` as at the pin.
- The packet holds the contract's shapes, not its §2 to §7 whole: doclint's 9 KB ceiling (consumer: hq).

## Handover
- `tests/test-bare-machine.py` `test_3_doctor` changed: R7 removes the `FAIL router` row it pinned.

## Next act
- The gate on the act 6 commit; then the hq record.
