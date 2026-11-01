# Packet a-s19, amendment 1: the scribe's done rows, its id command, the acceptance lines

The amendment as a private hq wrote it (its `history/sessions/BRIEF-2026-11-01-a-s19-a1.md`), in this repo's packet shape, as the packet copy `design/packets/a-s19-rows.md` was: its home paths put in words for the public scan, its wall and verify the packet's rows copied unchanged, and its acceptance cell targeted lines (doclint's suite rule).

| item | value |
|---|---|
| from | a-s19's refuter round 1 (PASS at 8387eac; F1, F2, F3 S4 and observations b, c), sitting 2026-11-01-2-hq: S4s that ride, since the scribe goes live on install |
| pin | branch `a-s19-rows` at 8387eac, worktree `.claude/worktrees/a-s19-rows` in this repo's checkout; continue there |
| wall | the packet's row, unchanged: this repo; read agentik-hq, agentik-commons and the other agentik repos at main, never write there, except that commons' `scripts/sync <this worktree>` writes into this worktree; no push, `--amend`, rebase, merge, real `make install`, real `install-cli`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; a test never writes under the live `~/.local`, `~/.claude`, `~/.config`; never touch `~/.config/agentik/hooks-follow-launcher`; no relay verb or binary; no `kill`, `pkill` or signal from a script; never a gate verb under a temp HOME; zsh here, `bash -c` for bash syntax; `rm -r` only as `"${VAR:?}"` |
| may touch | `plugin/agents/scribe.md`, `design/packets/a-s19-rows.md` (its acceptance cell only), this amendment as `design/packets/a-s19-rows-a1.md`, the branch's charter |
| acceptance | `grep -qF 'leaves the table in the commit that marks it' plugin/agents/scribe.md` exits 0 (act 1); `grep -qF "grep -oE '[0-9]+'" plugin/agents/scribe.md` exits 0 (act 2); `grep -qF 'GUIDE §9' plugin/agents/scribe.md` exits 0 (act 3); `grep -qxF "$(printf '\tscripts/recordlint')" Makefile` exits 0 (act 4); `scripts/doclint` exits 0; `scripts/hygiene` exits 0 |
| verify | the packet's row, unchanged: `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id>` in one background Bash, last. It exits 0 whatever the job's code: read the code from its line; recordlint's line is in the log |
| budget | One commit per act. **Stop at 60k context or 40 tool calls:** commit the act in flight, write the exact resume line, report. `claude-opus-5-5` |

## 1. What the source says (quoted)

Read first: agentik-hq's `design/05-records-as-tables.md` §2, by sections. Its HANDOFF paragraph: "A done row leaves in the commit that marks it, as one line in `history/handoff-done.md`, so its number resolves." Its NICE paragraph: "`id` is `n<k>`, never reused."

The refuter round 1 of a-s19 passed at 8387eac and named three S4s and two observations; they ride now, since the scribe goes live on install. **Not here:** any other change to the packet's acts.

## 2. Rulings

0. This amendment, committed first.
1. **F1, the done row.** `scribe.md`'s record-lines step: a HANDOFF row marked done leaves the table in the commit that marks it, appended as one line to `history/handoff-done.md` (`<#> <item>, done <date> <sha>`; design/05 §2).
2. **F2, the id command.** Replace the bare `git log -p -- NICE_TO_HAVE.md` with the filtered line, printed in the text: `{ grep -oE '^\| n[0-9]+ ' NICE_TO_HAVE.md; git log -p -- NICE_TO_HAVE.md \| grep -oE '^[-+]\| n[0-9]+ '; } \| grep -oE '[0-9]+' \| sort -n \| tail -1` (the highest; the next is one more). Check it on a scratch repo with a removed row, and that its output in this repo is one line.
3. **Observations b and c.** `scribe.md:18`'s "only the files your brief names" admits the overflow file under `history/sessions/` that `:45-46` names; one pointer for the cells' meanings: "the shape is commons GUIDE §9's rows paragraph" (state words, the `repo` short name, `item` at 80 characters). Short; the file stays under doclint's caps.
4. **F3, the acceptance lines.** In the packet copy's acceptance cell: act 3 checks the recipe line (`grep -qxF "$(printf '\tscripts/recordlint')" Makefile`, or what this Makefile's recipe line is exactly), and one line checks act 1 in `scribe.md` (a `grep -qF` of a phrase it must hold).
5. The packet's verify line, last; read the code from the gate's line.

## 3. Interfaces

- `history/handoff-done.md`: one line per done row, `<#> <item>, done <date> <sha>`.
- The id command of ruling 2: prints the highest `n<k>` number ever used in `NICE_TO_HAVE.md`, its rows and the rows its history removed; the next id is one more.

## 4. Findings that name this row

a-s19's refuter round 1: F1 (the done row's move unwritten), F2 (the bare `git log -p` unfiltered), F3 (the Makefile acceptance line too loose, act 1 unchecked), all S4; observations b (the overflow file outside "only the files your brief names") and c (the cells' meanings unpointed).

## 5. Forbidden reads

A file over 8 KB whole; a relay ledger or a reference snapshot whole; anything outside the wall's reads.

## 6. Report

At most six lines: the sha; each act's commit; the gate's id and its code from its line; scribe.md's bytes.
