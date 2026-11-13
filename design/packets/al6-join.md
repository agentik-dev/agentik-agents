# Packet al6-join: the lane's four slices joined on main, the stub kept only where no wall is proved, the lists, the forward and the version

The hq's brief for row al6, in this repo's packet shape.

| item | value |
|---|---|
| from | the hq's row al6 (design/21 §3.2 item 12, §3.3, §5, §9); the seams page of the lane's rows; hq entries 6, 37 and 41 |
| pin | main 23aab48, plugin 1.7.1 (al0's stub 1.6.4, ak7's plug); worktree `.claude/worktrees/al6-join`, branch `al6-join`; nothing linked |
| merges | `al1-run` adaf541, `al2-wall` aa1d299, `al3-fanout` a7755c5, `al4-report` e2143b0 (its phase 2 merged this main) |
| wall | this worktree; no push, `--amend`, rebase, install or landing; the four merges alone; no `claude`, no model, no key read, no network; `doctor` and `route --check` only under `sandbox-exec` with the network denied; no relay verb; `make` only through the gate queue |
| may touch | every file the four slices add; `plugin/lib/agentik-agents`; `plugin/lib/claude-fanout` (new); `plugin/lib/agents_install.py`; `plugin/lib/agents_plug.py`; `tests/`; `Makefile`; `plugin/.claude-plugin/plugin.json`; `NICE_TO_HAVE.md`; `design/04-api-lane.md`; `.hygiene-allow`; this packet; a charter |
| acceptance | section 6's lines 1 to 13 |
| verify | `make check`, once, last, through `agentik session gate run`, then `gate wait --strict` |
| budget | a commit each: packet, the four merges, the tests seen red, each mend, the forward and install, the plug, the lists, NICE and design/04, 1.8.0 alone |

## 1. What the source says

The owner: "When the API lane is enabled, I'd like you to report how many agents are running within that session and what types. If the API lane is disabled we shouldn't see anything beyond what we see today." And: "the work machine is invoking claude-fanout directly, so see if you can create a better mechanism."

Baseline at 23aab48: `plugin/bin/agentik-agents fanout x` in a temp HOME with a made-up `claude-fanout` first on PATH runs it (`ran x`, exit 0, its mark left); `ls plugin/lib/apilane` prints `No such file or directory`.

The coordinator's word: the second computer runs `fanout --detach ... --profile analyze` and two `wait` forms; the detached forms are row al7's. The short form already takes `--budget-usd`, `--profile` and `--add-dir`, so no flag is added; the owner's question 2 is open and R4 stands. The plug's rider: `route.state_dir` reads `The folder that holds the router's pid file and, by default, its request log.`

## 2. Rulings

- R1, the merge: `--no-ff` of al1, al2, al3, then al4; main's lines stay, a slice's are added beside them; each mend is its own commit naming the slice.
- R2, the stub stays only where no wall is proved: al4's phase 2 made it the `fanout` arm's second way. Where a wall is proved, `fanout` with the lane off, any arguments, prints `agentik agents fanout: the API lane is off on this machine. To turn it on, add "api:" and, indented under it, "enabled: true" to <config, home as ~>; then "agentik agents api status" lists the steps left.` on stderr, exit 2. The stub's cases run on a copy whose `walled.sh` says no wall, one also with no `apilane/`; the install case stays the lane-off case.
- R3, the lists: the six lane suites in `test`'s pin list and floor list; `lint` gains `sh -n` of the hook, the prefilter and the forward, and every `apilane/*.py`; `RETIRED` loses `claude-fanout`.
- R4, the forward: `plugin/lib/claude-fanout`, POSIX sh, runs the dispatcher beside its resolved path as `fanout --yes "$@"`; one note on a terminal, none in a pipe. `install-cli` links it only while the lane is on; off, four names and main's `linked ...` line byte for byte. `api status` and the lane's doctor block name a `claude-fanout` on PATH that is not this forward.
- R5, the plug: a layer `user` (the lane's file, not travelling); the six `api.` keys, defaults from `apilane.config`, each change a hand edit of the file; the lane's five checks only while it is on.
- R6, end to end: `tests/test_al6_join.py`, every real module, `tests/fake-claude` speaking to the loopback stub, fake `sops` and `age-keygen`; skips with one reason where no wall is proved.
- R7, the old cases: one table, each case of the old suites (58, 26, 14, 46, 81 rows; the cost tool's 76 as one line) against its new test, or cut and why.
- R8, 1.8.0 alone in the last commit under `plugin/`; NICE rows; design/04's status. R9, `make check` once on that head.

## 3. Interfaces

- `agents_install.main(argv=None, out=..., err=..., lane=None)`; `lane=None` asks `apilane.config.lane(apilane.paths.account())`, any refusal is off, a refused file (`config.fault`) is one line on stderr.
- `agents_plug.config(key=None, roots=None)`; `agents_plug.doctor(lane=None, roots=None, parts=None)`; with `roots` `None`, `apilane.paths.account()`, and no account under a foreign HOME means defaults and no checks.
- `apilane.cli.old_forward(path=None)`: the PATH's `claude-fanout` when it is not this tool's, else `None`.

## 4. Findings that name this row

al4's R4 literal test (a FIFO, folder or unreadable file at the path is silent in sh, refused aloud by a verb); al2's probe PATH and cwd to match a shard's; al1's no row prunes `runs/`. Each stays as built; the join's record names them.

## 5. Forbidden reads

The real config file, state folder, gate list and any key store or `secrets` folder; a relay ledger.

## 6. Report

`J` is `tests/test_al6_join.py`, run under the pin's interpreter and `/usr/bin/python3`. Lines: 1 four merges in order (`git log --merges --first-parent`); 2 `bash tests/test-dispatch.sh` all pass, the stub's on the no-wall copy; 3 `J OffVerbTest`; 4 `J ForwardTest`; 5 `J InstallTest`; 6 `tests/test-bare-machine.py`; 7 `J PlugTest`; 8 `J EndToEndTest`; 9 `J KillTest`; 10 `G` part B run; 11 R7's table; 12 1.8.0, hygiene, doclint; 13 `make check` through the queue, each suite's `===` line for the pin and the floor.
