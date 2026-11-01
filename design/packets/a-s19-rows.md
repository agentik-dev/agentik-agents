# Packet a-s19: the scribe writes rows; agents' NICE as a table

The brief as a private hq wrote it (its `history/sessions/BRIEF-2026-11-01-a-s19.md`), in this repo's packet shape, its home paths put in words for the public scan; its acceptance line, `make check` green, is the verify row here, and the acceptance cell holds targeted lines (doclint's suite rule).

| item | value |
|---|---|
| from | agentik-hq HANDOFF 18 (build 7, the owner's word of 2026-11-01); agentik-hq's `design/05-records-as-tables.md` §2, §3, §4, §7 item 3, §12; hq entry 6 |
| pin | agents main 04bd575, plugin 1.5.1; commons main 05bc434 (c3's landing, recordlint in `sync`); worktree `.claude/worktrees/a-s19-rows`, branch `a-s19-rows`, cut there |
| wall | this repo; read agentik-hq, agentik-commons and the other agentik repos at main, never write there, except that commons' `scripts/sync <this worktree>` writes into this worktree; no push, `--amend`, rebase, merge, real `make install`, real `install-cli`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; a test never writes under the live `~/.local`, `~/.claude`, `~/.config`; never touch `~/.config/agentik/hooks-follow-launcher`; no relay verb or binary; no `kill`, `pkill` or signal from a script; never a gate verb under a temp HOME; zsh here, `bash -c` for bash syntax; `rm -r` only as `"${VAR:?}"` |
| may touch | `plugin/agents/scribe.md`, its tests if any, `scripts/` (by `sync` only), `Makefile`, `NICE_TO_HAVE.md`, `history/NICE-2026-11-01.md` (by `git mv` only), `.hygiene-allow`, `plugin/.claude-plugin/plugin.json`, the README's scribe lines and its sidecar if they name the NICE shape, this packet as the repo's packet file, a charter under `history/sittings/` |
| acceptance | `scripts/recordlint NICE_TO_HAVE.md` exits 0 and prints `held:` (baseline: `skip`); `shasum -a 256 -c scripts/vendored.sha256` exits 0 with a `scripts/recordlint: OK` line; `grep -qxF "$(printf '\tscripts/recordlint')" Makefile` exits 0 (act 3, the recipe line); `grep -qF 'a line is one row of it' plugin/agents/scribe.md` exits 0 (act 1); `test -f history/NICE-2026-11-01.md` exits 0; `scripts/hygiene` exits 0; `scripts/doclint` exits 0; `grep -qF '"version": "1.5.2"' plugin/.claude-plugin/plugin.json` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id>` in one background Bash, last. It exits 0 whatever the job's code: read the code from its line; recordlint's line is in the log |
| budget | One commit per act. **Stop at 100k context or 70 tool calls:** commit the act in flight, write the exact resume line, report. `claude-opus-5-5` |

## 1. What the source says (quoted)

Read first, by sections (`record <file> --sections`, then `--section`): design/05 §2, §3, §4; commons `GUIDE.md` §9 (its rows paragraph, new in c3); `plugin/agents/scribe.md` whole (it is the subject); commons' `scripts/recordlint`'s head comment.

The scribe writes NICE and HANDOFF lines in every repo, so it learns the row before any other repo converts; then agents converts its own NICE. **Not here:** any other repo's conversion; recordlint itself (c3, landed).

## 2. Rulings

0. This packet, committed first.
1. **The scribe's row line.** In `scribe.md`'s record-lines step: where the file holds design/05 §2's table, a NICE or HANDOFF line is one row of that table: one line, every `|` in a cell written `\|` (code spans too), at most 400 characters, evidence that does not fit to a cited file under `history/sessions/`; a NICE `id` is the highest `n<k>` ever used plus one (the file's rows and the removed rows in `git log -p -- NICE_TO_HAVE.md`), a HANDOFF `#` the highest in the table and `history/handoff-done.md` plus one; a `level` of `S1` to `S4`, S4 when unsure; a file still in bullets keeps bullets. Short; the file stays under the doclint caps.
2. **Resync.** commons' `scripts/sync <this worktree>`; commit what it places (recordlint and `vendored.sha256`).
3. **Makefile.** The `doclint` target runs `scripts/recordlint` after `scripts/doclint`.
4. **agents' NICE.** design/05 §3: `git mv NICE_TO_HAVE.md history/NICE-2026-11-01.md`, and in that commit `history/NICE-2026-11-01.md: sibling` under the `NICE_TO_HAVE.md: sibling` row of `.hygiene-allow`. A new `NICE_TO_HAVE.md`: a title, one head paragraph naming the archive, then the table under a `##`, holding the S1 to S3 items you confirm open on main (design/05 counts 5); ids from `n1`. recordlint green on it.
5. **The version.** Plugin 1.5.2, one bump, last; if `plugin-version-check` asks again after a later change, bump the patch.
6. The gate, last.

## 3. Interfaces

- NICE's table, design/05 §2: `\| id \| level \| area \| finding \| evidence \| from \|`; HANDOFF's: `\| # \| item \| level \| repo \| where \| state \|`.
- `scripts/recordlint [FILE...]`: exit 0 clean, 2 on any finding, 1 on usage; one line per file, `path: held: N rows` or `path: skip: why`.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

A file over 8 KB whole; a relay ledger or a reference snapshot whole; anything outside the wall's reads.

## 6. Report

At most ten lines: the branch and sha; each act's commit; the gate's id and its code from its line; the suite's counts; the NICE rows kept (ids, levels, one line each); anything left over, and if you stopped, the exact resume line.

Stop and report, committing what is there, on: `sync` placing anything beyond recordlint and its sha line that reds the check; hygiene red on a file you cannot allow without a new reason row; a doclint cap the scribe's new lines cannot meet. A stop is a result.
