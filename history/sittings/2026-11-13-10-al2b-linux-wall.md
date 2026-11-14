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
- [ ] act 4: the `Makefile`'s two lists; the gate once.

## Handover
- decide, owner: the coordinator: the version is not taken in this build, so `plugin-version-check` reds the branch; consumer: the landing.

## Next act
Act 4: the lists and the gate.

## Exit
Not yet.
