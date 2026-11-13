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
| 0. the packet | done, 252d505 |
| 1. tests seen red (`tests/test-plug.py` 10 of 10, the usage line, the status keys) | done, 21e96c6 |
| 2. `agents_plug.py`, the dispatcher's verbs, `--check --json`, the lane note, the status schema and prefix | done, 1342611; test-plug, dispatch, route, status, bare-machine, rig, readme green under `/usr/bin/python3` and 3.12.7 |
| 3. NICE_TO_HAVE n7 to n9 | done |
| 4. the version, 1.7.0, alone | done |
| 5. `make check` through the gate queue | open |

## Choices inside the rulings

- Computed defaults (`route.backends_file`, `route.state_dir`, `route.log`) are computed: the script's own assignments run with `env` giving its default. Shell defaults are expanded (`$HOME`, nested `${...:-...}`); an empty one is null.
- `local.` takes the `CLAUDE_LOCAL_*` that `claude-local` assigns from `${NAME:-default}` (not `NO_PREFLIGHT`, a test of the variable); `rig.` every `${LOCALRIG_*:-...}`, `Q8_BLOB` among them.
- Where `agents_plug.py` is absent or no python3 runs, the text `doctor` runs `--check` as at the pin.
- `tests/test-bare-machine.py`'s `test_3_doctor` changed: R7 removes the `FAIL router` row it pinned.

## Handover

- Next act: the gate, `make check` through the queue.
