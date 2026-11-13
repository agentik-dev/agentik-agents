# Packet al6-join: the lane's four slices joined on main, the stub kept only where no wall is proved, the lists, the forward and the version

The hq's brief for row al6, in this repo's packet shape; below the table it is the brief's text.

| item | value |
|---|---|
| from | the hq's row al6 (design/21 §3.2 item 12, §3.3, §5, §9); the seams page of the lane's rows; hq entries 6, 37 and 41 |
| pin | main 23aab48, plugin 1.7.1 (al0's stub 1.6.4, ak7's plug); worktree `.claude/worktrees/al6-join`, branch `al6-join`; nothing linked |
| merges | `al1-run` adaf541, `al2-wall` aa1d299, `al3-fanout` a7755c5, `al4-report` e2143b0 (its phase 2 merged this main) |
| wall | this worktree; no push, `--amend`, rebase, install or landing; the four merges alone; no `claude`, no model, no key read, no network; `doctor` and `route --check` only under `sandbox-exec` with the network denied; no relay verb; `make` only through the gate queue |
| may touch | every file the four slices add; `plugin/lib/agentik-agents`; `plugin/lib/claude-fanout` (new); `plugin/lib/agents_install.py`; `plugin/lib/agents_plug.py`; `tests/`; `Makefile`; `plugin/.claude-plugin/plugin.json`; `NICE_TO_HAVE.md`; `design/04-api-lane.md`; `.hygiene-allow`; this packet; a charter |
| acceptance | the lines below, 1 to 13 |
| verify | `make check`, once, last, through `agentik session gate run`, then `gate wait --strict` |
| budget | a commit each: packet, the four merges, the tests seen red, each mend, the forward and install, the plug, the lists, NICE and design/04, 1.8.0 alone; stop at 90 tool calls with the act in flight committed |

Baseline at 23aab48, 2026-11-13: `plugin/bin/agentik-agents fanout x` in a temp HOME with a made-up `claude-fanout` first on PATH runs it (`ran x`, exit 0, its mark left); `ls plugin/lib/apilane` prints `No such file or directory`.

The coordinator's word: the second computer's lines are `fanout --detach ... --profile analyze` and two `wait` forms; the detached forms are row al7's. The short form already takes `--budget-usd`, `--profile` and `--add-dir`, so no flag is added; the owner's question 2 is open and R4 stands. The plug's rider: `route.state_dir`'s summary reads `The folder that holds the router's pid file and, by default, its request log.`

## The owner's words

"I need a Fable designer to recover the claude fanout to API lane agents. I want this designed and brought up to the current standards of our existing plugins. When the API lane is enabled, I'd like you to report how many agents are running within that session and what types. If the API lane is disabled we shouldn't see anything beyond what we see today." And: "Also, the work machine is invoking claude-fanout directly, so see if you can create a better mechanism." Four builders built the lane's slices on four branches; you join them and land nothing yourself: the coordinator lands your one branch.

## The ledger

The repo keeps no `DECISIONS.md` and no `CLAUDE.md`; agentik-commons' `GUIDE.md` binds. Cited from the coordinating repo's ledger, verbatim:
- Entry 6, in part: "A Python plugin, as it moves under hq design/04, runs its hooks and tools from its own `plugin/lib` through a launcher in its `plugin/bin`, on `AGENTIK_PYTHON`, else `/usr/bin/python3`, else `python3` on PATH, at a runtime floor of Python 3.9 on the standard library alone, and a runtime script in it takes a `#!/usr/bin/python3` shebang."
- Entry 41, in part: "For any other key it refuses with exit 2 and names the file and the block to edit, so no command an agent can run changes posture for later sessions."
- Entry 37: "Never commit. The tool repos are public. Commit no hostname, address, email, person's name, account detail, or private repo's name or path; examples use made-up names."

## Rulings

- R1, the merge. `git merge --no-ff` of `al1-run`, `al2-wall`, `al3-fanout`, then `al4-report`, in that order; these four merges are yours to make. al1 to al3 only add files. al4 has already merged this main, so the dispatcher should merge clean; where it does not, main's lines stay and al4's are added beside them. After the merge every file of the lane is yours to mend, and each mend is its own commit that names the slice it mends.
- R2, the stub stays only where no wall is proved (design/21 items 13 and 17). A row that landed before the lane gave the dispatcher a `fanout` function that hands its arguments to an old tool found on PATH. The owner's one machine that uses that tool is Linux, where the lane has no wall and refuses to turn on. So the function is not deleted: al4's phase 2 made it the `fanout` arm's second way, reached where `apilane_walled` is false or `apilane/` is absent, and it stays that until a later row gives Linux a wall and removes it. Yours: the head comment says so in two lines; the stub's cases in `tests/test-dispatch.sh` move to where they hold, each run against a copy of `plugin/lib` whose `walled.sh` says no wall, and one of them once more against a copy with `apilane/` removed; its install case, that a link named `claude-fanout` pointing outside the tree is kept, stays as the lane-off case. What `fanout` prints with the lane off, from this row on, where a wall is proved, with any arguments, `--help` among them: `agentik agents fanout: the API lane is off on this machine. To turn it on, add "api:" and, indented under it, "enabled: true" to <the config path, the home as ~>; then "agentik agents api status" lists the steps left.`, on stderr, stdout empty, exit 2; there it hands the call to nothing. Where no wall is proved and the file does not say on, it does what main's stub does, byte for byte; where the file says on, it prints the platform's line and exits 2.
- R3, the lists. The `Makefile`'s `test` target names `tests/test_al1_run.py`, `tests/test_al2_wall.py`, `tests/test_al3_fanout.py`, `tests/test_al4_report.py`, `tests/test_al4_off_golden.py` and `tests/test_al6_join.py` in the pin's list and in the 3.9 floor's list. `lint` gains `sh -n` for `plugin/hooks/api-lane`, `plugin/lib/apilane/prefilter.sh` and `plugin/lib/claude-fanout`, and every `plugin/lib/apilane/*.py` in its Python line. `RETIRED` loses `claude-fanout`.
- R4, the forward (design/21 item 12). `plugin/lib/claude-fanout`, POSIX `sh`: it finds the dispatcher beside its own resolved path and runs `fanout --yes "$@"`, the arguments unchanged in number, order and bytes. On a terminal it prints one note on stderr, that the name is now `agentik agents fanout` and ends on 2026-12-31; in a pipe, none. `agents_install.py` links it as it links the four old names, by the same temp link and rename, and only while the lane is on: `main(argv=None, out=..., err=..., lane=None)`, where `lane` `None` asks `apilane.config.lane(apilane.paths.account())` and reads any refusal as off; a refused config file is one line on stderr. Off: four names and the `linked ...` line byte for byte as main prints it, and a path named `claude-fanout` is not touched. On: a link of that name is replaced wherever it points, a dangling one too; a path that is not a link is left and named, as for the four. `api status` and the lane's `doctor` block name any `claude-fanout` on PATH that is not this forward, with the line that removes it.
- R5, the plug's table and list. `plugin/lib/agents_plug.py` holds one table of settings and one list of checks, kept free of any `api` name for this row. Add, in the shape that file and its packet give: a layer `user`, the lane's config path, present when the file exists, not travelling; the six keys `api.enabled`, `api.max_fanout_usd`, `api.max_day_usd`, `api.console_limit_usd`, `api.proxy` and `api.ca_file`, each default read from `apilane.config` and typed nowhere else, each `change` text saying the file is edited by hand; and, only while the lane is on, the lane's checks: the key present, the probe passed for the installed CLI, the Console limit stated, the wall's wrapper present, and a note when the config path is not on the gate list. Off, `doctor --json` holds no check of the lane's.
- R6, end to end, `tests/test_al6_join.py`: every real module, `tests/fake-claude` (yours now; give it a mode that speaks to the lane's loopback stub), a fake `sops` and `age-keygen`, the real `sandbox-exec`, and `roots` under a temp home handed in process. Where `wall.backend()` is `None`, as on Linux, or a wall cannot start, the tests that need the wall skip with one printed reason and the suite ends `OK`: `make check` is green on Linux.
- R7, the old cases. One table in your packet: each case of the old tree's three shell suites and two Python suites, by name, against the new test that holds it, from al1's and al3's hand-backs: 58, 26, 14, 46 and 81 rows. A case of something that stays cut (the pass-through, the single-run verb, the open argv) is a row that says cut and why. The cost tool's 76 cases are one line. A case with no row is a block: port it.
- R8, the version and the records. `1.8.0` in `plugin/.claude-plugin/plugin.json`, alone in the last commit that touches `plugin/`. `NICE_TO_HAVE.md` gains rows for: no wall off macOS; a hard link inside a job dir; a shard's cost while it runs; the catalogue and sidecar for the lane's sentences; the README section owed. `design/04-api-lane.md` gains its status: the lane returned, what came back and what stays cut. The README and its source are not yours: rendering them is a model run.
- R9, the gate. `make check`, once, through the gate queue, on the head that holds 1.8.0.

## Acceptance

`J` is `tests/test_al6_join.py` and `G` is `tests/test_al4_off_golden.py`; each `J` line is run twice, as `python3 J <class>` with the pin's interpreter first on PATH (`pyenv which python3`) and as `/usr/bin/python3 J <class>`. Measured at your pin, on main before al4's merge: `plugin/bin/agentik-agents fanout x` in a temp HOME, with a made-up `claude-fanout` first on PATH, runs that file; `ls plugin/lib/apilane` prints `No such file or directory`.

| # | command | prints |
|---|---|---|
| 1 | `git log --merges --first-parent --format=%s <pin>..HEAD` | four lines, al1 to al4, in order |
| 2 | `bash tests/test-dispatch.sh` | every case passes, the stub's among them, each of those against a copy whose `walled.sh` says no wall: its five arguments arrive unchanged, `--yes` is dropped before `--`, no old tool on PATH is its one line and exit 2; and in that copy, with a file that says on, `fanout x` prints the platform's line, exit 2, and the made-up old tool left no mark |
| 3 | `J OffVerbTest` | `OK`, where a wall is proved (it skips with its reason elsewhere): with `roots` at a temp home and no file, `fanout a b` and `fanout --help` print R2's off line on stderr, nothing on stdout, exit 2; a made-up `claude-fanout` first on PATH that leaves a mark when run left none. Everywhere: `apilane_walled` and `wall.backend() is not None` agree |
| 4 | `J ForwardTest` | `OK`: through the forward and a stand-in dispatcher, `--budget-usd 2 'a b' '' -x` arrives as `fanout --yes` and those five, unchanged; in a pipe stderr is empty; on a pseudo-terminal it holds the one note |
| 5 | `J InstallTest` | `OK`, in process: `lane=False` gives four links and main's `linked ...` line byte for byte, and a `claude-fanout` link to a file outside the tree still points there; `lane=True` gives five, that link now points into the tree, a dangling one is replaced, and a plain file of that name is left and named |
| 6 | `python3 tests/test-bare-machine.py` | passes, with its four names |
| 7 | `J PlugTest` | `OK`: the config read lists the six `api` keys with their defaults under layer `user`; off, the doctor read holds no check of the lane's; on, in process, it holds the five |
| 8 | `J EndToEndTest` | `OK`: the probe passes on the fake, and its recorded argv has the same flags as a shard's, differing in the prompt and the ceiling alone; then `fanout JOB --yes` with three shards of two types: the fake's first start found the reservation in the log; mid-run `report.line` reads `api lane: 3 agents running (2 explore, 1 review), $0.00 of $2.00 spent` and `report.rows` has three rows under the session; at the end the log holds three `shard` lines and one `settle`, and the hook's next prompt prints the ended line once, then nothing; eight planted secrets are in no file under the temp home and in no recorded argv |
| 9 | `J KillTest` | `OK`: the fan-out, as a child process on every real module, is killed with SIGKILL after its reservation; the day's sum holds its whole budget; a second fan-out that would pass the ceiling is refused and starts no fake; the hook's next prompt prints `stopped without a close` with the budget, once |
| 10 | `python3 G` | `OK`, part B run, not skipped: off is byte-equal to the pin on every compared surface |
| 11 | the packet's table of R7 | 58, 26, 14, 46 and 81 rows and the one line; no case without a row |
| 12 | `grep -c '"version": "1.8.0"' plugin/.claude-plugin/plugin.json`; `scripts/hygiene`; `scripts/doclint` | `1`; exit 0; exit 0 |
| 13 | `make check` through the gate queue (`agentik session gate run`, then `gate wait --strict`) | exit 0, and its log holds each of the six suites' `===` lines twice, once for the pin and once for the 3.9 floor |

Write the tests of lines 3 to 9 first, after the four merges, and see each fail; say in your hand-back how each failed. A red suite of a slice is yours to mend, in a commit that names the slice.

## Not built

The session plugin's line and band (al5). A wall for Linux and the stub's removal (al2b). A writing type. A verb that turns the lane on or releases a reservation. A wall off macOS. The README and its render. The first run of the probe on the real CLI: the coordinator's, after the install. If the coordinator's word says the owner answered question 2 with a refusal or with nothing, R4 shrinks to that and line 4 and half of line 5 go; say which in your record.

No fork for the owner.

## R7's table

Owed: see the charter's handover. The old suites are the seven files a-s17's act 2 removed (034519c); each case gets a row against the new test that holds it, or `cut` and why.
