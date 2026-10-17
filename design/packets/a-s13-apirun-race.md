# Packet a-s13: test-apirun's mid-run read waits for the tool it races

| item | value |
|---|---|
| from | the coordinator's `make check` on `a-s12-polish` at 810457a (2026-10-17 03:40 and 03:44, load 3.3 to 4.5): `tests/test-apirun.py` FAIL `mid-run: progress.json shows the first message and its tool while the stream pauses`, `last_tool: None`; alone on main at 3b4d4dd, 4 of 5 runs red (03:42, load 3.2 to 3.5), 1 of 3 on the branch (03:41); the a-s12 builder's check green at load 5 to 9 (03:24); the relay's `design/packets/ar35-load-tolerant-tests.md` §2 ruling 4 and `design/packets/ar93-load-flakes.md` §2 ruling 1 (read-only, the device); portfolio entries 15, 25, 26 |
| pin | `main` at 3b4d4dd plus this packet's commit; a linked worktree, branch `a-s13-apirun-race` |
| wall | a-s12's, verbatim: this repo only. No push, merge, tag, `--amend`, rebase, `git stash`, network, install or `pyenv install`. No `claude` but `make check`'s `validate`; never `make readme`; no relay binary or verb; no write under `~/.claude`, `~/.config`, `~/.pyenv` or `~/.local/state`. One command at a time; one `make check`, last, started only when `ps -axo command \| grep -E '(^\|/)make( \|$)' \| grep -v grep` prints nothing. Before the report, `make doclint` exits 0 and `make hygiene` reads `hits outside allowlist: 0` |
| may touch | `tests/test-apirun.py` (the slow run's poll and its checks only), `NICE_TO_HAVE.md` (one row), `design/packets/a-s13-apirun-race.md`, `history/sittings/*.md`. Nothing else |
| acceptance | `for i in 1 2 3 4 5; do PYTHONDONTWRITEBYTECODE=1 python3 tests/test-apirun.py 2>&1 \| tail -1; done \| grep -c '0 failed'` reads 5 (main: 1 of 5 at 03:42); `for i in 1 2 3; do PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tests/test-apirun.py 2>&1 \| tail -1; done \| grep -c '0 failed'` reads 3 (main: measure it); `grep -c 'pj.get("last_tool")' tests/test-apirun.py` reads 6 (main: 5), counting the poll's read beside the five checks'; `grep -c 'answered by a-s13' NICE_TO_HAVE.md; grep -c -v -E '^- \*\*S[1-4] · \|^#\|^$' NICE_TO_HAVE.md` read 1 and 0 (main: 0, 0); `git diff --stat 3b4d4dd -- plugin bin \| wc -l` reads 0 |
| budget | 25 turns, 180k context, `claude-opus-5-5`; two acts, one commit each: the packet's, then the fix with its row |
| verify | `make check` |

## 1. What the source says (quoted)

`tests/test-apirun.py:335-346`: the slow run's poll, every 50 ms under a 15 s deadline, breaks on the first `progress.json` whose `turns == 1`, and reads `run.json` then; the check at line 358 wants `pj.get("last_tool") == "Read"` from that same read. The fake (`tests/test-apirun.py:122-131`, `FAKE_MODE=slow`) writes every `head` event at once, then waits for `FAKE_GO`; the wrapper writes `progress.json` as the stream arrives, so the message's write (`turns` 1, no tool yet) can land before the tool's, and a quiet machine lets the poll read between the two. Measured as the table's `from` says: red 4 of 5 on main alone at load 3.2 to 3.5, red in two of the coordinator's checks, green in the builder's at load 5 to 9.

## 2. Rulings

Standing rules. The charter, `history/sittings/<date>-<n>-a-s13.md`, opens at act 1 and closes before the last commit; no home path. The fix's first acceptance line is red on the pin, its count in the commit message. Nothing under `bin/` or `plugin/` changes.

1. **The device** (AR35's ruling 4, AR93's ruling 1): the poll waits for the event the check reads, `pj.get("turns") == 1 and pj.get("last_tool")`, under the same 15 s deadline; a miss keeps the same FAIL text with the last read, so a wrapper that never records the tool still reds. No sleep added, no assertion dropped, no production value changed.
2. **The record.** One NICE row in the repo's row shape (`- **S1 · tests/test-apirun.py: the mid-run read races the wrapper's second progress write** (the coordinator's check, 2026-10-17): answered by a-s13 (`design/packets/a-s13-apirun-race.md`): …`), naming the two check reds and the 4 of 5.

## 3. Interfaces (signatures, not prose)

None; test-only.

## 4. Findings that name this row

The coordinator's check logs (agentik-hq, sitting 2026-10-17-1's charter); nothing in NICE before this row.

## 5. Forbidden reads

Transcripts; `~/.claude/projects`; `README.md` whole; no other repo but the two relay packets named in `from`.

## 6. Report (capped)

At most 100 words: each acceptance line's value; `make doclint`, `make hygiene`'s last line, `make check`; the red line's count on the pin; last line branch and head sha. No fork.
