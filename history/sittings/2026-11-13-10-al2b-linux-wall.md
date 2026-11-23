# Sitting 2026-11-13-10: agentik-agents, al2b-linux-wall, the first build

| item | value |
|---|---|
| goal | the brief's R1 to R5: a bubblewrap backend behind `wall.backend()` and `wall.wrap`, the probe's launcher inside the wall, `walled.sh`; the Linux classes written, the macOS tests seen red then green; the gate once |
| budget | the builder's tool calls; `claude-opus-5-5` |
| pin | worktree `.claude/worktrees/al2b-linux-wall`, branch `al2b-linux-wall`, off main 2b81b47; nothing linked |
| window | builder, one sitting, spawned by an hq sitting of 2026-11-13 |
| agents | none |

## Done-ness
- [x] act 0: the packet and this charter.
- [x] act 1: `tests/test_al2b_linux.py` (lines 1 to 6 and DoubtTest; its 8 classes skip here, one reason each) and `tests/test_al2b_argv.py` (7a to 7d), red at 2b81b47: 3 failures and 14 errors of 18 (no `_BWRAP_EMPTY_IF`, `_TRIED`, `_launch_python`, `_stub_inside`, `inside`; no `walled.sh`), the agreement test green.
- [x] act 2: R2, R3 and R5: the backend, its trial (kept per process), `walled.sh`; al2's no-backend test hides the bwrap path too. `A BwrapArgvTest TrialTest WalledShTest` 14 OK; `tests/test_al2_wall.py` OK.
- [x] act 3: R4: the probe's launcher (`probe.launch`, `inside`), the stub's `start(port)`; the launcher passes the builders' environment by its names alone, since Apple's `/usr/bin/python3` adds `SDKROOT` and others at its start. `A` 18 OK under both interpreters.
- [x] act 4: the `Makefile`'s two lists name `test_al2b_argv.py` and `test_al2b_linux.py`.
- [x] act 5: the gate once on this commit (its id in the hand-back).

## Handover
- decide, owner: the coordinator: the version is not taken in this build, so `plugin-version-check` reds the branch; consumer: the landing.
- decide, owner: the coordinator: al7's `WorkLinesTest` skips on Linux, since al6's `Lane` writes its fake's records to `DARWIN_USER_TEMP_DIR`, a folder the bwrap wall does not leave open; consumer: the Linux proof.

## Next act
The Linux proof (the hand-back's lines, on a Linux machine at this head); then review 1; then the second round: R6, the stub's removal, and R7, 1.10.0.

## Exit
R1 to R5 built and committed; the Linux classes written and not seen to run; the gate runs on this commit, the branch's tip.
