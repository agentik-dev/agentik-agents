# Packet a-s8: the conventions, slice two

| item | value |
|---|---|
| from | `NICE_TO_HAVE.md`'s S3 row "the conventions, slice two"; agentik-commons `GUIDE.md` §1, §4 to §7, §9 at e59a318; the code at bbd1c7d |
| pin | `main` at bbd1c7d plus this packet's commit; agentik-session `main` at 2bce6a7, read-only; a linked worktree, branch `a-s8-conventions-two` |
| wall | this repo only. No push, merge, tag, `--amend`, rebase, `git stash`, network or install. No `claude` but `make validate`'s, which spends nothing; never `make readme`; no relay binary or verb; no write under `~/.claude`, `~/.config` or `~/.local/state`. One command at a time; one `make check`, last, alone on the machine. Before the report, `make doclint` exits 0 and `make hygiene` reads `hits outside allowlist: 0` |
| may touch | `scripts/doclint`, `scripts/readme-render`, `Makefile`, `.hygiene-allow`, `design/packets/a-s[134567]-*.md` and `design/packets/spent/` (those six, `git mv` only), `plugin/commands/delegate-local.md`, `plugin/commands/delegate-review.md`, `plugin/commands/delegate-implement-brief-template.md`, `plugin/implement-brief.md`, `plugin/skills/delegated-review/SKILL.md`, `plugin/skills/local-delegation/SKILL.md`, `plugin/.claude-plugin/plugin.json` (`version`), `README.md` (Tests, Layout), `design/readme/source.md`, `design/readme/contract.txt`, `design/readme/rendered.sha256`, `tests/test-readme.sh`, `NICE_TO_HAVE.md`, `design/packets/a-s8-conventions-two.md`, `history/sittings/*.md`, `history/sessions/NEXT`. Nothing else |
| acceptance | `test -x scripts/doclint && grep -c -E '^DOCLINT_SHA = 26eaf2c84aadb822\|^scripts/doclint: renamed$' Makefile .hygiene-allow` reads Makefile:1 and .hygiene-allow:1 (main: nothing); `git diff -M100% --name-status main -- design/packets \| grep -c '^R100'` reads 6 (main: 0); `cat history/sittings/2026-10-13-[12].md \| grep -c -E '^# Sitting [-0-9]+: agentik-agents, \|^## (Done-ness\|Next act)$'` reads 6 (main: 0); `grep -c '' plugin/commands/*.md \| grep -c -E ':(3[1-9]\|[4-9][0-9]\|[0-9]{3,})$'` reads 0 (main: 3); `grep -c '"version": "1.2.1"' plugin/.claude-plugin/plugin.json` reads 1 (main: 0); `grep -c -E '^check-unlocked: test lint doclint hygiene validate( \|$)\|^(lint\|doclint\|validate\|readme):' Makefile` reads 5 (main: 0); `grep -c -E '^[0-9a-f]{64}  ' design/readme/rendered.sha256; git diff --no-index --quiet design/readme/source.md README.md; echo $?` read 2 and 0 (main: no file, 1); `bash tests/test-readme.sh 2>&1 \| tail -1` reads test-readme: N passed, 0 failed, N at least 5 (main: no file); `grep -c 'answered by a-s8' NICE_TO_HAVE.md` reads 1 (main: 0) |
| budget | 90 turns, 180k context, `claude-opus-5-5`; five acts, one commit each; the charter opens with doclint's five rows |
| verify | `make check` |

## 1. What the source says (quoted)

NICE row 4: doclint, hygiene and `.hygiene-allow` in `check`; "the README via respeak (`design/readme/source.md`, the sidecar, the freshness check)", with the Explore paragraph; `validate`, which "fails on the reserved `claude-code-agents` name until the rename"; `claude plugin test`; `doctor`; the 3.12.7 pin, the shebangs; three long commands. GUIDE §5: `check` runs "`test`, `lint`, `doclint`, `hygiene`, `validate` (60 s), README freshness"; §6: doclint "stays byte-identical across the repos", and sync copies agentik, hygiene, bounded; §7: a change under `plugin/` bumps the version. Entries 26 and 25 bind. The survey: agentik-research `research/synthesis/tools-agents.md` §2.9, §4.1, §4.4.

Landed at bbd1c7d: the vendored scripts at rf1 bytes (sync-rf1); `hygiene` in `check`, `.hygiene-allow`, the name `agents`, `doctor` (agentik-r1-agents, public-r1); the Explore paragraph's "built at launch", which `tests/test-rig.sh` asserts. No `3.12.7` outside NICE and a-s4.

Measured: agentik-session's doclint refuses 33 here. Charters 6: each title, `## Done-ness`, `## Next act`. Packets 21, in the six spent ones: three over 9,216 bytes, eight suite lines, ten sections. Plugin 6: commands of 92, 65 and 69 lines, the last without `allowed-tools`; skill descriptions of 560 and 675 chars. Copied in, it is hygiene's one new hit (renamed); a README copy adds none.

## 2. Rulings

Standing rules. The charter, `history/sittings/2026-10-16-<n>-a-s8.md`, opens at act 1 and closes before the last commit. Each act's first acceptance line is red on the pin, its red line in the commit message. A `.hygiene-allow` row only for a hit the scan names, under a `#` reason.

1. **Act 1, doclint.** `scripts/doclint`: agentik-session's, `cp`, mode 755, never edited. Sync does not carry it: `vendored.sha256` keeps three lines, the Makefile pins it as `DOCLINT_SHA`; `.hygiene-allow` gains `scripts/doclint: renamed`, and this packet a `sibling` row. Its docstring's rules run over tracked and untracked-not-ignored files. The six spent packets move whole by `git mv` to `design/packets/spent/`, which it does not read: a spent packet is a record (§9), and its lists, which only canonical bytes change, lift no size or section refusal; their `.hygiene-allow` rows follow. Each charter, three lines: the title `<date>-<n>: agentik-agents, <its packet>`, `## Acts` to `## Done-ness`, `## Exit` to `## Next act`.
2. **Act 2, the plugin.** `delegate-local` and `delegate-review` keep frontmatter, `$ARGUMENTS` and the stop line, then follow `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/SKILL.md`, which gains any step only the command had (the verbatim preflight line too). `delegate-implement-brief-template` keeps its name and `disable-model-invocation: true`, gains `allowed-tools: Read`, and shows its old body, moved to `${CLAUDE_PLUGIN_ROOT}/implement-brief.md`. Each skill `description`: one line under 200 chars, the trigger phrases it drops in the body's opening. `plugin.json` `1.2.1` (§7); commons' marketplace line is the coordinator's.
3. **Act 3, the Makefile.** `lint`: the syntax checks out of `check-unlocked`, and `bash -n scripts/readme-render`. `doclint`: the `DOCLINT_SHA` check, then the script. `hygiene`: the sums, then the scan. `validate`: `scripts/bounded --wall 60 -- claude plugin validate plugin/`, else `validate: unrun, no claude on PATH`, exit 2. `check-unlocked: test lint doclint hygiene validate`, then the freshness check. No `claude plugin test`: `plugin/` has no Mod. `doctor` stays. A `validate` refusal is fixed under `plugin/`, unless it is of the name (§6).
4. **Act 4, the README via respeak.** The README's Tests section names the new gate and `make readme`, its Layout the new paths; then `cp README.md design/readme/source.md` and, last, `shasum -a 256 design/readme/source.md README.md > design/readme/rendered.sha256`, a by-hand technical render; the first respeak render spends, a later act. From agentik-session: `contract.txt` less its `<img>` and `Status:` clauses; `scripts/readme-render` less step 1 (the status line), `RESPEAK_PYTHON` as agentik-decisions sets it; the `readme` and freshness lines. Without respeak, `make readme` exits 2 naming `claude plugin install respeak@agentik` and writes nothing; `make check` needs only `shasum`, fresh while the three files agree, stale (exit 2) once the source changes unrendered. `tests/test-readme.sh` (bash 3.2, fakes, a temp repo), in `make test`: no renderer, 2; a render, the fake's README, a sidecar `shasum -c` passes; the renderer's 1, 1; the verifier's no, 2; `CLAUDE_SESSION_DEPTH=2`, 2 before any write; each failure leaves README. The Explore paragraph enters the source as it reads.
5. **Act 5, the record.** NICE row 4 reads "answered by a-s8" with what is left; one `make check`; the charter closes.
6. **Left, filed in act 5.** The shebangs and 3.12.7 pin (entry 26) move eight tools' interpreter for every caller: their own packet (S3). `claude plugin test` with a Mod (S4). The first render: 83,568 bytes, five times agentik-session's, whose round took about 525 s of its 900 (S4).

## 3. Interfaces (signatures, not prose)

`Makefile`: `DOCLINT_SHA`, `RESPEAK_RENDER ?=`, `RESPEAK_PYTHON ?=`; new `lint`, `doclint`, `validate`, `readme`; `check-unlocked: test lint doclint hygiene validate`. `scripts/readme-render [--repo DIR]`: 0 written and stamped; 1 the style gate; 2 setup, the renderer's other exits or the verifier.

## 4. Findings that name this row

NICE row 4 (S3) and its Explore clause; the survey's §4.1 and §4.4; agentik-hq `HANDOFF.md` item 9.

## 5. Forbidden reads

Transcripts; `~/.claude/projects`; a real `~/.claude.json`; `~/.local/state`; `README.md` whole (`grep -n`, `sed -n`). No other repo but agentik-session's `scripts/doclint`, `scripts/readme-render`, `design/readme/contract.txt`, Makefile lines 1-8 and 55-72; agentik-decisions' Makefile line 121; agentik-commons' `GUIDE.md`.

## 6. Report (capped)

At most 150 words. The table: each acceptance line; `make lint`, `doclint`, `validate` exits; `make hygiene`'s and each suite's last line; `make check`. Bullets: each act's red line; choices beyond §2, with consumers; anything filed. The one fork: if `claude plugin validate plugin/` refuses the name `agents`, the rename is the owner's: its error line, and stop after act 3. Last line: branch, head sha.
