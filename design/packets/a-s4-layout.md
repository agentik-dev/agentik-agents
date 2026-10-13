# Packet a-s4: the agents plugin under the shared conventions, slice one: layout, manifests, LICENSE, version, a bounded check

| item | value |
|---|---|
| from | the owner's plugin review, 2026-10-13 (example-mac `history/observer/plugin-review-2026-10-13.md`, the consistency section, S3 "bring agents under the conventions"); the owner's answer at 08:54: consistency in all five, agents first; portfolio entry 26; claude-code-session `design/conventions.md` §1, §2, §5, §7 |
| pin | branch `a-s4-layout` off main; worktree `.claude/worktrees/a-s4-layout`; a hand-run builder |
| wall | this repo only. No push, merge, tag, `--amend` or rebase. No live `claude` beyond `claude plugin validate` and `claude plugin test`, which spend nothing; no API call. Never start a router; kill only a pid your run started; never `pkill -f`. Never build a relay binary or run a relay verb. Never install or update a plugin |
| may touch | `plugin/` (new), `bin/claude-local` (the observer's path fix, 7f54979), `.gitignore`, `agents/`, `commands/`, `skills/`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `LICENSE` (new), `2` (removed), `scripts/bounded` (new), `Makefile`, `README.md`, `tests/*`, `NICE_TO_HAVE.md`, this packet |
| acceptance | `ls plugin/.claude-plugin/plugin.json plugin/commands plugin/agents plugin/skills >/dev/null; echo $?` prints 0; `ls -d agents commands skills .claude-plugin/plugin.json 2 2>/dev/null \| wc -l` reads 0; `python3 -c "import json;print(json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['source'])"` prints `./plugin`; `grep -rlE 'CLAUDE_PLUGIN_ROOT\}/(\.\.\|bin)' plugin \| wc -l` reads 0; `python3 -c "import json;d=json.load(open('plugin/.claude-plugin/plugin.json'));print(len(d['description'])<200,d['version'],d['license'])"` prints `True 1.2.0 MIT`; `head -1 LICENSE \| grep -c MIT` reads 1; `shasum -a 256 scripts/bounded \| cut -c1-12` prints `4fdfdc1df943`; `make -n check \| grep -c 'scripts/bounded'` reads at least 1; `make test; echo $?` ends 0 |
| budget | one builder sitting; one commit per act; act 1 the move |
| verify | the observer runs `make check` once on the branch, and after the merge `claude plugin marketplace update claude-code-agents` |

## 1. What the source says
- The plugin sits at the repo root: `agents/`, `commands/`, `skills/` and `.claude-plugin/plugin.json`. `marketplace.json` ships it with `"source": "."`, so the plugin cache gets the tests, `design/` and `secrets/local-backends.sops.yaml`.
- Four `${CLAUDE_PLUGIN_ROOT}/bin/…` fallbacks in `commands/` reach the tools through the plugin root.
- `plugin.json` holds name, a 370-character description, version `1.1.1` (never bumped since bbeff2a) and author. It has no license, homepage, repository or keywords, and `marketplace.json`'s entry has no version.
- The repo has no LICENSE, though entry 26 says the plugin repos are MIT. There is an empty tracked file `2` from 76b7e54.
- `make check` only syntax-checks (`Makefile:51-57`). `TOOLS` (`:11`) lacks `queue-mvp`.
- Conventions §1 is the target. The tools stay at the root on PATH via `make install`. `plugin/` is self-contained and names no path outside itself. `marketplace.json` reads `source: "./plugin"`. `scripts/bounded` is byte-identical to the session's copy, sha256 `4fdfdc1d…`, as listed in §6.

## 2. Rulings
1. `git mv` `agents/`, `commands/`, `skills/` and `.claude-plugin/plugin.json` into `plugin/`. `bin/`, `tests/`, `design/`, `secrets/` and `share/` stay at the root. Any test that names an old path follows the move.
2. Commands call each tool by its bare name on PATH. Where a tool may be missing, a command says `run make install in the repo` and stops. No `${CLAUDE_PLUGIN_ROOT}` path leaves `plugin/`.
3. `plugin.json` (§2):
   - It keeps `name` `claude-code-agents`; the agentik rename decides the name, not this packet.
   - `description` is under 200 characters, with no owner data.
   - `version` `1.2.0`: the `status` verb, and `/agents-status` replacing `/local-status`.
   - `author {name}`, `license` `MIT`, `keywords`.
   - `homepage` and `repository` both read `https://github.com/<owner>/claude-code-agents`.
4. `marketplace.json`: `source` `./plugin`, and the entry gains `version` `1.2.0`. The version is kept in these two places only; there is no tag in this packet.
5. `LICENSE`: MIT, copyright 2026 the owner. Remove `2`.
6. `make check` runs `scripts/bounded --lock .check.lock --wall 840 --load 4 -- $(MAKE) check-unlocked`, where `check-unlocked` is the present syntax checks plus `test`. Copy `scripts/bounded` byte for byte from claude-code-session; `.check.lock` goes in `.gitignore`. `TOOLS` gains `queue-mvp`.
7. Out of this slice, filed S3 in `NICE_TO_HAVE.md` as one row naming slice two:
   - `doclint`, `hygiene` and `.hygiene-allow`
   - README via respeak (`design/readme/source.md`, the sidecar, the freshness check)
   - `validate`, which fails on the reserved name until the rename
   - `claude plugin test plugin`
   - a `doctor` target
   - the 3.12.7 pin and the mixed shebangs

## 3. Interfaces
No tool or command changes its behaviour. The plugin's install path moves from the repo root to `plugin/`, which reaches sessions only after a marketplace update.

## 4. Findings that name this row
The owner's review: the consistency section's S3 row for agents, and the agents section's S3 rows on `make check`, LICENSE and the plugin's place, and its S4 row on the file `2`.

## 5. Forbidden reads
Transcripts whole; anything under `~/.local/state/agent-relay`.

## 6. Report
At most 200 words:
- each act's commit
- each acceptance line's result
- the list of moved paths
- the choices made

## 7. Charter (builder sitting 2026-10-13)
- goal: rulings 1-7 above, the acceptance lines green, one commit per act.
- budget: one sitting; at most 90 tool calls; checkpoint at 80%.
- pin: branch `a-s4-layout`, worktree `.claude/worktrees/a-s4-layout`, off 5a6bb3f.
- acts:
  1. the move (ruling 1), tests following it. done: `agents/`, `commands/`, `skills/`, `.claude-plugin/plugin.json` under `plugin/` by `git mv`; no test named an old path; `plugin-dev`/`plugin-install` hints name `$(REPO)/plugin`; make test rc 0 (99 passed), make check rc 0
  2. commands reach tools on PATH only (ruling 2). done: the four `${CLAUDE_PLUGIN_ROOT}/bin` fallbacks and their `*/bin/<tool> *` allowed-tools gone; each command and both skills say `run make install in the repo` and stop when a tool is missing; `plugin/` names no `bin/`; make test rc 0 (99 passed), make check rc 0
  3. manifests, LICENSE, `2` removed (rulings 3-5). done: plugin.json 1.2.0, a 172-char description, author, homepage, repository, MIT, keywords; marketplace `./plugin` and `1.2.0`; LICENSE MIT 2026 the owner; `2` removed; make test rc 0 (99 passed); `claude plugin validate plugin` (run once) rc 1, its one error the reserved name, as expected
  4. `make check` under `scripts/bounded`, `.check.lock` ignored, `TOOLS` gains `queue-mvp` (ruling 6). done: `scripts/bounded` sha256 4fdfdc1df943 (cmp-identical); `check` runs `check-unlocked` (the syntax checks, then `test`) under it; `make check-unlocked` rc 0 (99 passed); `make -n check | grep -c scripts/bounded` 1
  5. the slice-two row in NICE_TO_HAVE.md (ruling 7), README paths current. done: one S3 row naming slice two (ruling 7's six, plus the three commands over 30 lines and the README's stale Explore-copy claim); README's `--plugin-dir`, layout block, manifest, validate, `make install` and `make check` lines name the new paths
- choices:
  - a fake `claude` (exits 1) is first on PATH for every `make test`, so no test reaches the live binary; flag-pinning SKIPs under it.
  - `marketplace.json`'s `source` moves in act 3 with the rest of ruling 4, so acts 1-2 alone leave it at `.`.
  - the stop line went into every command and skill that calls a tool, not only the four with fallbacks; delegate-costs names `claude-costs`, not `bin/claude-costs`.
  - LICENSE is the session's MIT text without its claude-nextsession attribution paragraph, which is that repo's own.
  - marketplace.json's top-level description loses "on this Mac" and its plugin entry's description equals plugin.json's.
  - the python syntax check also parses `bin/queue-mvp`, since `TOOLS` now names it; `check-unlocked` runs `test` by `$(MAKE)` after the syntax checks.
  - `.gitignore` is not in `may touch`, but ruling 6 and the caller's act 4 name it: touched on the ruling's word, one line.
  - README: "all seven" suites reads "all eight" (four shell, four python), fixed in the line that names `make check`.
- handover:
  - decide, owner: the coordinator. The move breaks `bin/claude-local`'s Explore override (it reads `$REPO/agents/local-explore.md`; reproduced, filed S1 in NICE_TO_HAVE.md), and `bin/` is outside `may touch`. Consumer: the merge, or a one-line packet that names `bin/claude-local`.
- exit: done, acts 1-5 landed. The nine acceptance lines green; `make check` (the verify line) run once, rc 0 in 34 s, 99 passed; no `agentroute --serve` before or after. A fake claude was first on PATH for every make run (flag-pinning SKIPs under it). Open: the S1 `bin/claude-local` path, the coordinator's to place.

- observer's verify (2026-10-13): the S1 above was fixed on the branch by the observer at 7f54979 (`bin/claude-local` reads `plugin/agents/local-explore.md`; test-localrig 63/63) and its row left NICE_TO_HAVE.md. One adversary: PASS, 0 BLOCK; its note that no test catches a stale path is filed S3.
