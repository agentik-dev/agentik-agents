# Packet al4-report: the API lane's places, its one reader, the report, the hook and the verbs

| item | value |
|---|---|
| from | the coordinating repo's design/21 §3.2 to §3.4 and §3.6 (items 10 to 23), as amended after its refuter round on 2026-11-13; the seams the rows al1 to al6 share; commons `plugins/suite/lib/agentik_suite/settings.py` at `d795d4a` (the strict subset's reader) |
| pin | main at `c0193bd` (plugin 1.6.3); branch `al4-report`, worktree `.claude/worktrees/al4-report`; three rows build beside it from the same pin (one shard's run; the wall, the key and the probe; the job, the day's log and the fan-out) |
| wall | this worktree only. No push, `--amend`, rebase, install, version bump or `make` (the join runs the gate); one merge, phase 2's, on the coordinator's word. No `claude` started, no request to any API, no key read; every other row's function is a stand-in. No test reads or writes the real user file, the real state folder or the real edit-gates list. `doctor` runs only under a `sandbox-exec` profile that denies the network |
| may touch | new: `plugin/lib/apilane/{paths,config,report,hook,cli,messages}.py`, `plugin/lib/apilane/prefilter.sh`, `plugin/hooks/api-lane`, `tests/test_al4_report.py`, `tests/test_al4_off_golden.py`; edited, the named lines only: `plugin/hooks/hooks.json`, `plugin/lib/agentik-agents`, `plugin/lib/claude-agents`, `tests/test-dispatch.sh`, `.hygiene-allow`; this packet; the charter. No `apilane/__init__.py` |
| acceptance | each line run as `python3 <file> <class>` with the pin's interpreter first on PATH and as `/usr/bin/python3 <file> <class>`: `tests/test_al4_report.py` classes `PathsTest`, `SpellingTest`, `LaneKeysTest`, `PromptFilterTest`, `LineTest`, `ConsumeTest`, `RowsTest`, `HookTest`, `CliOffTest`, `CliOnTest`, `StatusVerbTest`, `KeyVerbTest`, `MessagesTest`, `StatusToolTest`, `PlantedTest`, `PlatformTest` each `OK`; `tests/test_al4_off_golden.py` `OK`; `bash tests/test-dispatch.sh` exits 0; `scripts/hygiene`, `scripts/doclint`, `sh -n plugin/lib/agentik-agents plugin/hooks/api-lane` and `sh -n plugin/lib/apilane/prefilter.sh`, and `dash -n plugin/lib/agentik-agents plugin/hooks/api-lane plugin/lib/apilane/prefilter.sh` where the dash shell is installed, exit 0. At the pin: `ls plugin/lib/apilane` prints `No such file or directory`; `plugin/bin/agentik-agents fanout x` and `api x` each exit 2 with the two usage lines |
| budget | 90 tool calls, `claude-opus-5-5`, high; six acts, one commit each |
| verify | none in this row: the join runs `make check`; the suites by hand under both interpreters |

## 1. What the source says

The owner: "When the API lane is enabled, I'd like you to report how many agents are running within that session and what types. If the API lane is disabled we shouldn't see anything beyond what we see today." And: "Also, the work machine is invoking claude-fanout directly, so see if you can create a better mechanism."

Off is byte-identical to today on every surface; one reader says on, off or refused; the places come from the account's home in the password database, never `HOME` or an `XDG_*` variable; a platform with no proved wall refuses to turn the lane on.

## 2. Rulings

1. `paths.account(env=None) -> Roots(home, config, state, store)`: `home.none` when the database's home is not absolute, `home.differs` (home, account) when `HOME` is set and its real path is another. The only reader of the database or the environment for a place; a test hands `roots` in.
2. `config.lane(roots) -> Lane(enabled, max_fanout_usd, max_day_usd, console_limit_usd, proxy, ca_file)`, defaults `False, 2.0, 10.0, None, None, None`, on the suite's five parsing functions ported whole. `true`/`True` on; `false`/`False`/no key off; anything else, an `api` that is not a mapping, an unknown key under `api`, a ceiling not above 0, a path that is not a regular file (never opened) or a file that cannot be read is `config.fault` (path, line, why).
3. `prefilter.sh`, POSIX `sh`, sourced by the hook and the dispatcher: `apilane_wants_start` (the user file under `$HOME` is regular, readable, and holds `api`), `apilane_wants_prompt TEXT` (this session's `live/` folder holds a `.json`, or any session's when the id cannot be cut; no fork), `apilane_walled` (`/usr/bin/sandbox-exec` is executable), then `walled.sh` beside it when readable. The test never decides; it is true wherever the reader says on or refused and wherever the report prints.
4. The hook, `hooks/api-lane`, `sh`, on `SessionStart` and `UserPromptSubmit` (timeout 5 s): reads stdin whole, exits 0 silent unless the test passes, then starts Python once with `-I` on `hook.py`. On: design/21 item 11's sentence, or the platform line where no wall is proved; refused: one line with the file and line; at a prompt, `report.line(..., consume=True)` whatever the switch says.
5. `report.line` and `report.rows`: the five texts of item 21 byte for byte; a run counts while its pid lives with its start time; ended and lost records are reported once, then removed with `consume`.
6. The status tool adds `report.rows` in one guarded block: no new key, no new field.
7. The dispatcher's `fanout` and `api` arms run `apilane/cli.py`; where no wall is proved `fanout` reaches the lane only to refuse a file that says on or is refused (`cli.py unwalled`), else falls to what main does. `help` gains two lines and `doctor` a block only when the file says on.
8. `cli.main(argv, *, roots, parts, ...)`: `fanout`, `api status`, `api probe`, `api key set`, `api key remove`. Off: one stderr line, exit 2, no part called. No proved wall: `wall.platform`, exit 2. Every sentence lives in `messages.py`.
9. `tests/test_al4_off_golden.py`: the launcher's and each hook's captures byte-equal with and without `plugin/lib/apilane/` in three off homes, and against the merge base with main while the branch is ahead of it.

## 3. Interfaces

The seams the four rows share: `Roots` and `Lane` as above; an error a user may see has `code` and `fields`, and `messages.say(code, **fields)` turns it into the sentence. `cli` reaches the other rows only through one `parts` object (`parse`, `plan`, `run`, `day`, `find_claude`, `build_argv`, `build_env`, `started`, `alive`, `wall_backend`, `wrap`, `check_dirs`, `key_load`, `key_store`, `key_remove`, `key_present`, `probe_run`, `probe_ensure`, `probe_read`, `probe_passed`, `cli_version`), imported inside `cli` when none is handed in.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

A file over 8 KB whole; the real user file, state folder, key store and edit-gates list; anything under a `secrets` folder.

## 6. Report

The record of each phase: each acceptance line, its exit and its last output line; the choices made inside the rulings; the branch and its head sha.
