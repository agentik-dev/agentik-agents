# Sitting 2026-11-13-1: ak7-plug-agents

| item | value |
|---|---|
| goal | build packet `design/packets/ak7-plug-agents.md`: `describe --json`, the config read, `doctor --json`, the lane note, `status --json`'s schema |
| budget | 90 tool calls; Opus, high |
| pin | main c0193bd (plugin 1.6.3), branch `ak7-plug-agents` |
| exit | open |

## Done-ness

| act | state |
|---|---|
| 0. the packet | done |
| 1. tests seen red (`tests/test-plug.py`, the usage line, the status keys) | open |
| 2. `agents_plug.py`, the dispatcher's verbs, `--check --json`, the lane note, the status schema and prefix | open |
| 3. the version, 1.7.0, alone | open |
| 4. `make check` through the gate queue | open |

## Handover

- Next act: write `tests/test-plug.py` and see it red.
