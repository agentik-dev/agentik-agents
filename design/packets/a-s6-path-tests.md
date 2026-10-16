# Packet a-s6: tests for a path left at the old place after the a-s4 move

| item | value |
|---|---|
| from | NICE_TO_HAVE.md's S3 row "tests: no test catches a path left at the old place after the a-s4 move" (the a-s4 adversary, 2026-10-13) |
| pin | branch `a-s6-path-tests` off main f986500; worktree `.claude/worktrees/a-s6-path-tests`; a hand-run builder |
| wall | this repo only. No push, merge, tag, `--amend`, rebase or `git stash`. No live `claude`, no API call, no `claude plugin` verb: the tests use the suites' stubs. Never start a real router; never `pkill -f`. Never build a relay binary or run a relay verb. Never read a transcript. No `make check`, no `make install`. The plants live only in scratch copies, never in a committed file |
| may touch | `tests/test-rig.sh`, `tests/test-dispatch.sh`, `NICE_TO_HAVE.md`, this packet |
| acceptance | `bash tests/test-rig.sh 2>&1 \| tail -1` reads `N passed, 0 failed`; `bash tests/test-dispatch.sh 2>&1 \| tail -1` reads `test-dispatch: N passed, 0 failed`; in a scratch copy (`git archive HEAD \| tar -x -C $S`) with plant P1, `bash $S/tests/test-rig.sh` exits 1 and its FAIL lines name the Explore override; with P2, and again with P3, `bash $S/tests/test-dispatch.sh` exits 1 and its FAIL line names the plant; `make test; echo $?` ends 0 |
| budget | one builder sitting, 35 turns, checkpoint at 29; one commit per act |
| verify | the observer runs `make check` once on the branch |

## 1. What the source says
- a-s4 moved the plugin into `plugin/`. `bin/claude-local`'s `explore_agent_json` builds the Explore override from `$REPO/plugin/agents/local-explore.md`; when that fails, the launcher warns and leaves Explore on the session model, and no test notices (the cold-start harness runs a copy whose `$REPO` has no `plugin/`).
- agentik-r1 act 1 (e1c1c16) dropped the per-repo `.claude-plugin/marketplace.json`; the plugin ships from the agentik marketplace, and its only manifest is `plugin/.claude-plugin/plugin.json`.
- No file under `plugin/` names `CLAUDE_PLUGIN_ROOT`, a `../` path or `$REPO`; the commands reach the tools by name, through `agentik-agents <verb>`.

## 2. The plants (each in its own scratch copy)
- P1: `bin/claude-local`'s `explore_agent_json` reads `$REPO/agents/local-explore.md` again.
- P2: a root `.claude-plugin/marketplace.json` returns with its `agents` entry at `"source": "."`.
- P3: `plugin/commands/delegate-local.md` gains a fallback to `${CLAUDE_PLUGIN_ROOT}/bin/agentroute --check`.

## 3. Rulings
1. **test-rig.sh, the Explore override.** (a) `explore_agent_json`, taken from `bin/claude-local` and run with `REPO` at the tree, prints JSON whose `Explore` has `model` `local/default`, a non-empty prompt and tools. (b) The cold harness links `$COLD/plugin` to the tree's `plugin/`; the good cold start passes claude `--agents` with that model and prints no "could not build the Explore override".
2. **test-dispatch.sh, the plugin's edges.** The plugin's manifest is `plugin/.claude-plugin/plugin.json` and the root has none; a root `.claude-plugin/marketplace.json`, if one returns, sources every entry at `./plugin`; no file under `plugin/` names a `CLAUDE_PLUGIN_ROOT` path that does not resolve to a file inside `plugin/`, a `../` segment, or `$REPO`.
3. No tool, command or manifest changes.

## 4. Forbidden reads
Transcripts; anything under `~/.local/state`; any other repo, the agentik marketplace's included.

## 5. Report
At most 100 words: the tests added, red against each plant, green on the branch (`make test` tail), the head sha.

## 6. Charter (builder sitting 2026-10-16)
- goal: rulings 1-3, the acceptance lines green, each plant red.
- budget: 35 turns, checkpoint at 29; at most 90 tool calls.
- pin: branch `a-s6-path-tests`, worktree `.claude/worktrees/a-s6-path-tests`, off f986500.
- acts:
  1. this packet. done
  2. the tests (rulings 1, 2), red against P1-P3 in scratch copies, green on the branch.
  3. NICE_TO_HAVE.md: the S3 row becomes a one-line "answered by a-s6" note in place.
- handover:
  - decide, owner: the agentik marketplace's maintainer (consumer: the agents plugin's install path): the row asks for a test of "the marketplace source", but the per-repo marketplace left in agentik-r1; this repo asserts only that a returning one sources `./plugin`, and the shared marketplace's own `source` for `agents` is checked where that file lives.
- exit: open
