# Packet a-s17: the plugin cut to `status`, the local lane and `scribe`

| item | value |
|---|---|
| from | the owner's word of 2026-10-31, a private hq's `HANDOFF.md` item 17, build 3 of a review: "agentik-agents is cut to `status`, the local lane and `scribe`". The review's §2.5 verdict with one change, the owner's pick: the scribe stays here |
| pin | `main` at d8ca583 (plugin 1.3.2); worktree `.claude/worktrees/a-s17-cut`, branch `a-s17-cut` off it; this packet is the branch's first commit |
| wall | this worktree only; no push, merge, `--amend`, rebase, device, network, `make readme`, `make install`, `claude` but `claude plugin validate`; never write under `~/.local/state`; never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never build or run a relay binary; every other repo is read by grep and never written; past packets and design records keep their words |
| may touch | `bin/agentik-agents`, `bin/claude-agents`, `bin/claude-api-agent`, `bin/claude-fanout`, `bin/claude-costs`, `bin/queue-mvp`, `tests/test-dispatch.sh`, `tests/test-status.py`, `tests/test-apirun.py`, `tests/test-fanout.py`, `tests/test-costs.py`, `tests/test-queue.py`, `tests/test-queue-http.py`, `tests/test-arg-handling.sh`, `tests/test-run-path.sh`, `tests/test-flag-pinning.sh`, `tests/test-rig.sh` (only a line naming a deleted tool), `Makefile`, `.gitignore`, `.sops.yaml` (comments only), `.hygiene-allow`, `plugin/.claude-plugin/plugin.json`, `plugin/commands/delegate-costs.md`, `plugin/commands/delegate-review.md`, `plugin/commands/delegate-implement-brief-template.md`, `plugin/implement-brief.md`, `plugin/skills/delegated-review/SKILL.md`, `plugin/skills/local-delegation/SKILL.md`, `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`, `design/04-api-lane.md`, `design/05-local-lane-guide.md`, `design/packets/a-s17-cut.md`, `NICE_TO_HAVE.md`, `history/sittings/*.md`, `history/sessions/NEXT` |
| acceptance | `git ls-files bin \| wc -l` reads 5 (on d8ca583: 9); `git ls-files tests \| wc -l` reads 6 (on d8ca583: 14); `ls plugin/commands plugin/skills \| grep -cE 'delegate-review\|delegate-costs\|delegated-review\|implement-brief'` reads 0 (on d8ca583: 4); `wc -l < README.md` reads under 100 (on d8ca583: 1378); `cmp README.md design/readme/source.md; echo $?` reads 0 (on d8ca583: 0); `shasum -a 256 -c --status design/readme/rendered.sha256; echo $?` reads 0 (on d8ca583: 0); `grep -c '"version": "1.4.0"' plugin/.claude-plugin/plugin.json` reads 1 (on d8ca583: 0); `git grep -lE 'claude-(api-agent\|fanout\|costs)\|queue-mvp\|agents (api\|fanout\|costs\|fold)\b' -- bin plugin README.md \| wc -l` reads 0 (on d8ca583: 7; the Makefile's `RETIRED` names them on purpose, ruling 10); `bin/agentik-agents costs >/dev/null 2>&1; echo $?` reads 2 (on d8ca583: the tool's); `bin/agentik-agents fold >/dev/null 2>&1; echo $?` reads 2; `bash tests/test-dispatch.sh \| tail -1` reads 0 failed; `python3 tests/test-status.py \| tail -1` reads 0 failed; `bash tests/test-rig.sh \| tail -1` reads 0 failed; `python3 tests/test-route.py \| tail -1` reads 0 failed; `make doclint hygiene lint validate >/dev/null 2>&1; echo $?` reads 0 (on d8ca583: 0) |
| verify | `make check`, once, last, through the session gate's queue as one job: `agentik session gate run <worktree> -- make check`, then `agentik session gate wait <id>` |
| budget | acts: 0 this packet and the charter; 1 `status` loses its API rows and `fold`, keeps its prices; 2 the API tools, their verbs and their suites go; 3 the plugin; 4 README, source, sidecar, the two design notes, NICE; the proof. 90 tool calls, 180k context, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says (quoted)

Review §2.5: "Delete the API lane from the plugin until it has a measured user; keep the design note. Move `scribe` next to `decisions:backlog`. Cut the README to a page." The owner's pick overrules the move. The review's build 3 text: "Takes: a day each, mostly deleting tests."

Confirmed on d8ca583: `README.md` is 1378 lines; `~/.local/state/agentik-agents/` does not exist, so no usage log and no run has been recorded here; 10 `.log` files are tracked.

## 2. Rulings (the builder's, reversible; the hq sitting may overrule at review)

1. The API lane is `bin/claude-api-agent`, `bin/claude-fanout`, `bin/claude-costs`, the verbs `api`, `setup-key`, `key-status`, `edit-key`, `remove-key`, `pin-proxy`, `usage`, `profiles`, `help api`, `fanout`, `costs`, `fold`, and the status tool's lane `api`.
2. `bin/queue-mvp` goes too. It runs each attempt through the API wrapper (its `AGENT_BIN`), has no verb, and no agentik repo calls it. It serves only the lane.
3. `plugin/implement-brief.md` and `plugin/commands/delegate-implement-brief-template.md` go too. The brief is written for `agentik-agents api`, and only that command reads it.
4. `status` keeps its cost column, so `PRICES`, `CACHE_READ_RATES`, `LONG_PROMPT_TIERS`, the two multipliers it uses, `canonical`, `rates` and `predicted_cost` move from `bin/claude-costs` into `bin/claude-agents`, and the suites that pin them move into `tests/test-status.py` unweakened. `INTRO_PRICING`, empty, stays behind. What a price means to `status` does not change.
5. `doctor` stays, less its API block. `status --json`'s field list does not change: the observer reads it. Lane `api` simply no longer appears.
6. The 10 `.log` files stay: they are the run records `design/01-local-agent-lane.md` and `design/02-local-rig.md` cite for the local lane, which stays. The review's question, "if they serve nothing", answers no.
7. No API-lane design note exists on d8ca583: the lane is described in the README and in passing in `design/01`. `design/04-api-lane.md` is that note, written from the README, pointing at the code by `git show d8ca583:<path>`. The live local-lane text moves from the README to `design/05-local-lane-guide.md`, words kept but for lines naming what went.
8. This repo has no `DECISIONS.md` and no `CLAUDE.md` on d8ca583, so there is no ledger entry to amend. Nothing is created here: a first ledger is its own decision, named in the charter's handover.
9. The version is 1.4.0, plugin and dispatcher. A removal of verbs is a minor at least; a major would break the `^1.2` a sibling states for `status --json`, which still holds.
10. `make install` and `make uninstall` also remove a link for the four retired tools when it still points here, so an install leaves no dangling alias. The GUIDE's alias promise until 2026-12-31 is a line for the hq.
11. NICE's lines on deleted code go, answered or not; lines on what stays are kept. The README source and render stay byte-identical by hand, the sidecar re-hashed.

## 3. Interfaces (signatures, not prose)

`agentik agents <verb>`: `local`, `status`, `rig`, `route`, `doctor`, `help`, `--version`; anything else exits 2. `claude-agents status [--json] [--watch N] [--all] [--since MIN]`, its exits and its `FIELDS` unchanged. The plugin: `/agents:status`, `/agents:delegate-local`, `agents:local-*`, `agents:scribe`, the skill `local-delegation`.

## 4. Findings that name this row

The review's §2.5; NICE's lines on `bin/claude-api-agent`, `bin/claude-fanout`, `bin/claude-costs`, `bin/queue-mvp` and the deleted suites.

## 5. Forbidden reads

Transcripts under `~/.claude/projects`; `~/.local/state` beyond an `ls`; the whole review; a file over 8 KB whole.

## 6. Report (one table, at most five bullets, under 600 words)

Callers that would break first; acts with commit shas; acceptance output; the gate's id and exit; lines removed and kept; the lines other repos need; any review claim that failed.
