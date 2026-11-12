# Packet p1: the plugin's descriptions under 1,024 bytes, held by `make check`

The brief as a private hq wrote it (its `history/sessions/BRIEF-2026-11-11-plugins-p1-description-gate.md`), in this repo's packet shape; its acceptance line, `make check` green, is the verify row here, and the acceptance cell holds targeted lines.

| item | value |
|---|---|
| from | agentik-hq brief p1 of 2026-11-11; hq design/09 §1 (F7), §2 (the row "A plugin's descriptions"), §6, §9 step 4; the owner's yes to question 7 of hq design/09; agentik-commons packet p1 (`scripts/plugin-description-bytes`, branch `p1-description-gate` at 06a2cf5) |
| pin | agents main c204a3c, plugin 1.5.5; worktree `.claude/worktrees/p1-description-gate`, branch `p1-description-gate`, cut there |
| wall | this worktree; read agentik-hq, agentik-commons and the other agentik repos, never write there; no push, `--amend`, rebase, merge, real `make install` or `install-cli`; `claude` only as the check's `claude plugin validate`; no relay verb or binary; no bare `make` |
| may touch | `plugin/commands/*.md` and `plugin/agents/*.md` and `plugin/skills/local-delegation/SKILL.md` (frontmatter only), `plugin/lib/share/local-explore.md` (its agent's copy), `plugin/hooks/hooks.json` and `plugin/hooks/local-guard` (new), `plugin/.claude-plugin/plugin.json`, `scripts/plugin-description-bytes` and `scripts/vendored.sha256`, `tests/test-descriptions.py` (new), `Makefile`, `.hygiene-allow`, `NICE_TO_HAVE.md`, this packet, a charter under `history/sittings/` |
| acceptance | `scripts/plugin-description-bytes plugin` exits 0, its last line `total N of 1024 B` with N at most 1024 (c204a3c: `total 3195 of 1024 B`, exit 1); `python3 tests/test-descriptions.py` OK (c204a3c: red); `shasum -a 256 -c scripts/vendored.sha256` exits 0 with a `scripts/plugin-description-bytes: OK` line; `grep -c 'agentik agents local' plugin/agents/local-implement.md plugin/agents/local-review.md plugin/agents/local-summarize.md plugin/agents/local-test.md` 0 in each frontmatter line (c204a3c: 1 each); `grep -qF '"version": "1.6.1"' plugin/.claude-plugin/plugin.json` exits 0; `scripts/hygiene` and `scripts/doclint` exit 0 |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict` in one background Bash, last |
| budget | One commit per group by explicit path, the packet first. `claude-opus-5-5`, high |

## 1. What the source says

- **The owner, 2026-11-11.** "The plugins hide the commands only the owner types, under 1,024 B a plugin: yes." "A focus should be on avoiding Claude.md bloat".
- **hq design/09 §1, F7.** A skill's or command's description is in context in every main session unless it sets `disable-model-invocation: true`; a general-purpose helper carries the skill list and the agent-type list too.
- **hq design/09 §9 step 4.** "`disable-model-invocation: true` on the commands only the owner types; the 1,024 B gate in `make check` ... agentik-agents' five repeated caveats cut to one; a tool list on each helper agent type that needs neither Skill nor Agent".
- **At the pin**, measured by commons' script: 3,195 B (delegate-local 152, install-cli 90, status 118, local-delegation 191, local-explore 455, local-implement 452, local-review 398, local-summarize 451, local-test 423, scribe 465). The five local-* descriptions open with the same 95-byte caveat. The plugin ships no hook, so a local-* call in a plain session reaches the API with `model: local/default` and fails there, in the API's words.

## 2. Rulings

0. This packet, committed first; then the failing tests.
1. **R3, hidden.** `delegate-local` and `install-cli` set `disable-model-invocation: true`: nothing in the plugin tells the model to start them (the skill's line 12 says the command "follows these same steps", which starts nothing). `status` stays visible: each local agent's description says "/agents:status shows which". No body changes.
2. **R4, the cut.** Each visible description says what the thing is for and when, once. The caveat (local model, free but slow, only in a session started by `agentik agents local`, never for judgment) is said once, in `local-explore`'s description, which a model choosing among the five reads first, as "Every agents:local-* type ..."; the skill's description drops it, since the skill's own preflight refuses an unrouted session. `plugin/lib/share/local-explore.md` stays its agent byte for byte (a-s18).
3. **R4, the plain failure.** `plugin/hooks/local-guard`, a PreToolUse hook on `Agent|Task`: an `agents:local-*` call in a session whose `ANTHROPIC_BASE_URL` is not a loopback `http://` address is denied with one sentence naming `agentik agents local`; every other call, and every call in a loopback session, passes with no output. Exit 0 always.
4. **R5.** Every agent here states its `tools`, none with Skill or Agent: nothing to add.
5. **R1 in the check.** `scripts/plugin-description-bytes` copied from commons' branch, its sum added to `scripts/vendored.sha256` as `sync` writes it; `make check` runs it as `descriptions`.
6. **R6.** Plugin 1.6.0, a minor: a new hook; 1.6.1 after the hook's command line was fixed on the branch (`plugin-version-check` asks again). README quotes no description.

## 3. Interfaces

- `scripts/plugin-description-bytes [--max BYTES] [PLUGIN_DIR]`: commons' (packet p1 there).
- `plugin/hooks/local-guard`: stdin a PreToolUse event; stdout nothing, or `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": ...}}`.

- **Tests.** `tests/test-descriptions.py`, run by `make test`: T1 the script exits 0 on `plugin/`; T2 the two hidden commands set it, bodies byte-equal to c204a3c's (sha256); T3 every visible description non-empty, a skill's under 201 characters (doclint); T4 `agentik agents local` in one agent description only; T5 the hook: deny for `agents:local-explore` unset and remote, pass for loopback, for `agents:scribe`, for no input; T6 the vendored copy is listed.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

A file over 8 KB whole; the owner's state under `~/.local/state`; transcripts.

## 6. Report

The branch and sha; the gate's id and its line; the bytes before and after; each description rewritten, old and new; choices; leftovers.
