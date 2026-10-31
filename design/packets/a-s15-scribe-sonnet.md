# Packet a-s15: the scribe on Sonnet with a one-hour cache, and by default

| item | value |
|---|---|
| from | a private hq's design 03 (the standby agent) §7 item 1, cut 2026-10-31 by that hq's sitting 2026-10-31-1: "`agents:scribe` gains `model: sonnet` and `cacheTtl: 1h`; the hq flow (this repo's CLAUDE.md, one sentence) and GUIDE §9 say a sitting's records go through it. Acceptance: the frontmatter reads both lines; `make check` green; plugin.json bumped, the marketplace line in commons at the install."; the hq's `HANDOFF.md` item 16 |
| pin | `main` at 2edcc33 (plugin 1.3.1); worktree `.claude/worktrees/a-s15-scribe-sonnet`, branch `a-s15-scribe-sonnet` off it; this packet is on the branch |
| wall | this repo, plus the one GUIDE §9 commit named under ruling 5 on commons' own branch; no push, merge, `--amend`, rebase, device, network, `make readme`, `make install`, `claude plugin install/update/marketplace`; never write under `~/.local/state`; never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never build or run a relay binary; commons' marketplace line and the hq's CLAUDE.md stay untouched |
| may touch | `plugin/agents/scribe.md` (frontmatter only), `plugin/.claude-plugin/plugin.json` (`version` only), `README.md` and `design/readme/source.md` (the lines of ruling 3, byte-identical) with `design/readme/rendered.sha256` re-hashed (`shasum -a 256 design/readme/source.md README.md > design/readme/rendered.sha256`), `design/packets/a-s15-scribe-sonnet.md`, `NICE_TO_HAVE.md` (ruling 4's line), `history/sittings/*.md`, `history/sessions/NEXT` |
| acceptance | `grep -c '^model: sonnet$' plugin/agents/scribe.md` reads 1 (on 2edcc33: 0); `grep -c '^model: opus$' plugin/agents/scribe.md` reads 0 (on 2edcc33: 1); `grep -c '^experimental:$' plugin/agents/scribe.md` reads 1 (on 2edcc33: 0); `grep -c '^  cacheTtl: 1h$' plugin/agents/scribe.md` reads 1 (on 2edcc33: 0); `grep -c '—' plugin/agents/scribe.md` reads 0 (on 2edcc33: 0); `grep -c '"version": "1.3.2"' plugin/.claude-plugin/plugin.json` reads 1 (on 2edcc33: 0); `grep 'agents:scribe' README.md \| grep -ci opus` reads 0 (on 2edcc33: 2); `grep 'agents:scribe' README.md \| grep -ci sonnet` reads 2 (on 2edcc33: 0); `cmp README.md design/readme/source.md; echo $?` reads 0 (on 2edcc33: 0); `shasum -a 256 -c --status design/readme/rendered.sha256; echo $?` reads 0 (on 2edcc33: 0); `make doclint hygiene lint validate >/dev/null 2>&1; echo $?` reads 0 and `PYTHONDONTWRITEBYTECODE=1 python3 scripts/plugin-version-check >/dev/null 2>&1; echo $?` reads 0 (on 2edcc33: 0 and 0) |
| verify | `make check`, once, last, through the session gate's queue as one job, by the builder at the coordinator's word: `agentik session gate run <worktree> -- make check`, then `agentik session gate wait <id>` |
| budget | acts: 0 this packet and the charter; 1 the frontmatter and the version; 2 README, source, the sidecar, the NICE line; commons' one commit; the proof. 40 turns, stop at 32 (commit the act in flight), 180k, `claude-opus-5-5`; one commit per act; the charter opens with doclint's five rows |

## 1. What the source says (quoted)

The design's item is in the from row. `plugin/agents/scribe.md` on 2edcc33 reads `model: opus`, `effort: medium`, `maxTurns: 30`, `color: blue`. `README.md:195` opens its third cell "Opus;"; `README.md:424`'s comment ends "agents:scribe (model: opus)". GUIDE §9's last bullet says a hand-back's records "may be written by" the scribe. `scripts/doclint:61` requires `name`, `description`, `model`, `tools`; indented frontmatter lines are ignored there, so a nested key does not trip it.

The field, read in the Claude Code in use here (2.1.316, the shipped bundle): the agent frontmatter schema has `experimental:u({cacheTtl:...})` with the text "Prompt cache TTL for this agent's requests (\"5m\" or \"1h\") when no `subagentPromptCacheTtl` setting or env var is set. \"1h\" is ignored while a Claude subscription is in overage."; the plugin agent loader takes `yn=LYr(Y)`, and `function LYr(e){let n=e.experimental;if(typeof n!=="object"||n===null)return;...` reads only that map (the key compared case-folded, the value against the two allowed). A top-level `cacheTtl:` is read by nothing. The vendor's docs say the same: "frontmatter `experimental.cacheTtl` (`5m` or `1h`, v2.1.248 or later)", and its precedence falls below the environment variable and the setting.

## 2. Rulings (the builder's, reversible; the hq sitting may overrule at review)

1. `model: opus` becomes `model: sonnet`; `effort: medium`, `maxTurns: 30` and the body stay.
2. The design's `cacheTtl: 1h` lands as the form that is read, two lines after `model`: `experimental:` then `  cacheTtl: 1h`. A flat `cacheTtl: 1h` would pass every lint and do nothing, which is the failure this packet was asked to look for; "the frontmatter reads both lines" holds with the second line indented.
3. README and source, byte-identical: line 195's third cell opens "Sonnet;"; line 424's comment ends "agents:scribe (model: sonnet)"; line 194's "Plugin agents (`plugin/agents/`), each with" becomes "The `local-*` plugin agents (`plugin/agents/`), each with". No other line changes; the render stays a coordinator's `make readme`.
4. Line 194 is the NICE S4 of a-s14's refuter, riding this packet since it touches the area; its NICE line goes.
5. GUIDE §9's last bullet is commons' own commit on branch `a-s15-guide` in worktree `.claude/worktrees/a-s15-guide` off its main: "may be written by" becomes "go through". The hq's CLAUDE.md sentence rides another packet.
6. The version is 1.3.2: no new agent, no config key, no contract; a changed model line is a patch, the builder's reading of semver (GUIDE §7 only requires a bump). The marketplace line in commons moves at the install, by the hq sitting.

## 3. Interfaces (signatures, not prose)

The frontmatter keys read by Claude Code's plugin agent loader: `model`, `effort`, `maxTurns`, `color`, and the map `experimental` with its key `cacheTtl` in {`5m`, `1h`}. The scribe's brief, its records and its six-line hand-back do not change.

## 4. Findings that name this row

NICE's a-s14 section, S4 "the 'Send a specific piece of work local' row says every plugin agent is local": ruling 3 fixes it and ruling 4 drops it.

## 5. Forbidden reads

Transcripts under `~/.claude/projects`; `~/.local/state` beyond reading; every other repo but the two the from and wall rows name.

## 6. Report (one table, at most five bullets, under 600 words)

Acts with commit shas; acceptance output verbatim; the gate's id and exit; the hygiene target's exit; what the field finding means for the design's wording.
