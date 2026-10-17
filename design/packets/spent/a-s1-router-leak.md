# Packet a-s1: claude-local leaks a router, and its test depends on the machine

| item | value |
|---|---|
| from | the observer, 2026-10-13: `make test` red on main 6f02c6d (tests/test-localrig.sh, 45 passed, 1 failed, reproduced twice); the agents review of the same day |
| pin | branch `a-s1-router-leak` off main 6f02c6d; worktree `.claude/worktrees/a-s1-router-leak`; a hand-run builder |
| wall | this repo only. No push, merge, `--amend` or rebase. No live `claude` and no API call: tests use a fake `claude` first on PATH. Kill only a pid your own run started, verified by `ps -o ppid,etime,args`; never `pkill -f`. Never build a relay binary or run a relay verb |
| may touch | `bin/claude-local`, `tests/test-localrig.sh`, `tests/test-agentroute.py`, `design/packets/a-s1-router-leak.md` |
| acceptance | `make test 2>&1 \| tail -1` exits 0; `bash tests/test-localrig.sh 2>&1 \| grep -c FAIL` reads 0 on two runs in a row; after `make test`, `pgrep -f 'bin/agentroute --serve'` finds no process that `make test` started |
| budget | one builder sitting; one commit per act; act 1 the red tests |
| verify | the observer runs `make check && make test` twice, with no router running before |

## 1. What the source says
- `bin/claude-local` passes every argument through (:14). With no router running (`pgrep` at :104) it starts `agentroute --serve` detached with `( nohup … & )` (:111), dropping the pid, then `exec claude …` (:168). When anything fails after the start and before the exec (the failure paths near :116 and :128), or the exec'd `claude` rejects an argument, the router is left orphaned (ppid 1). The next `claude-local` then refuses to start ("refusing to start a second router") until the orphan is killed.
- tests/test-localrig.sh:229-236 runs `claude-local --not-a-real-flag` and only afterwards asks `pgrep` whether a router runs, so the router that call itself started sends the test down the "refuse" branch, and it fails; a second run passes on the leaked router. Lines 10-11 claim the suite never starts a router.
- tests/test-agentroute.py:203-500 starts routers with no try/finally.

## 2. Rulings
1. Do not validate claude's arguments in `claude-local` (that copies claude's grammar). Keep the started router's pid (`& STARTED=$!` or equivalent) and stop it on every failure path before the exec through an EXIT trap, cleared just before the exec. After the exec, the router is meant to outlive this process; that stays.
2. The guard's meaning stays: any running `agentroute --serve` makes `claude-local` refuse to start a second. A per-port guard is out of scope.
3. The test is made hermetic: a fake `claude` first on PATH; a decoy `agentroute --serve` process the test starts and kills in its trap, so the refusal branch is always taken and always asserted (no SKIP branch); afterwards nothing listens on `$DEAD`. Cold start is tested separately with `claude-local` copied beside a stub `agentroute`, and the test asserts that the stub is stopped when the fake `claude` exits non-zero before exec, if the code path allows it. Fix the claim at lines 10-11.
4. test-agentroute.py stops every router it starts in try/finally.

## 3. Interfaces
`claude-local`: no change for a caller, except that a failure before the exec no longer leaves a router running.

## 4. Findings that name this row
The red test; the agents review's (1).

## 5. Forbidden reads
Transcripts whole; anything under `~/.local/state/agent-relay`.

## 6. Report
At most 200 words: each act's commit, the red test before and after, each acceptance line's result, the pids your runs started and that they are gone, choices made.

## 7. Charter (builder sitting 2026-10-13)
- goal: rulings 1, 3 and 4 above, the acceptance lines green.
- budget: one sitting; at most 90 tool calls; checkpoint at 80%.
- pin: branch `a-s1-router-leak`, worktree `.claude/worktrees/a-s1-router-leak`, off 82b063f.
- acts:
  1. red tests: tests/test-localrig.sh made hermetic (decoy router, stub cold start, the leak asserted). done: red, 59 passed, 2 failed (the two orphan assertions)
  2. bin/claude-local keeps the started router's pid and stops it on every pre-exec failure. done: test-localrig 63 passed, 0 failed, twice; a SIGTERM case added
  3. tests/test-agentroute.py stops every router it starts in try/finally. done: 87 passed; SIGINT mid-suite stops the router (the pre-fix file leaked one, ppid 1)
- fix round (the adversary's BLOCK, 2026-10-13; NICE_TO_HAVE.md joins `may touch`):
  4. F1: a router that answers is never its starter's to stop (launcher B may be on it). done: the race test fails on 9f977a0, passes now; h3.py: B sees 200
  5. F3: test-agentroute.py runs its finally on SIGTERM. done: h5.py, test rc 143 (was -15), its router gone; 87 passed
  6. F2 filed as S4 in a new NICE_TO_HAVE.md. done, with one more S4 (the one-poll window F1 leaves), not reproduced
- handover:
  - decide, owner: the coordinator. This repo has no `history/sittings/`, and the packet's `may touch` does not name one, so this charter lives here. Consumer: the next packet's `may touch` row.
- exit: done, round 1 (acts 1-3) and the fix round (acts 4-6) landed on 57b867f. `make check && make test` rc 0 in 28 s, run once (the verify line runs at most once); test-localrig FAIL count 0 on two runs; no `agentroute --serve` before or after. A fake claude was first on PATH throughout (flag-pinning SKIPs under it).
