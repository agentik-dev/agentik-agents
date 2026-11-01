# Packet a-s18, amendment 2: round 2's regression

The amendment as a private hq wrote it (its `history/sessions/BRIEF-2026-11-01-a-s18-a2.md`), in this repo's packet shape beside [the packet](a-s18-plugin.md) and [amendment 1](a-s18-plugin-a1.md), which stand; its home paths put in words for the public scan.

| item | value |
|---|---|
| from | a-s18's refuter, round 2, FAIL at d656fe0 on a regression (hq sitting 2026-11-01-1); amendment 1 and the packet stand. The review rule (this Mac's ledger, entry 20): no round 3; the gate and the new tests are the proof, as sc3's round-2 regressions were |
| pin | branch `a-s18-plugin` at d656fe0, worktree `.claude/worktrees/a-s18-plugin` |
| wall | amendment 1's, unchanged |
| may touch | `Makefile`, `tests/`, `NICE_TO_HAVE.md`, this amendment beside the others, the branch's charter; `plugin/` not at all (so no bump; if `plugin-version-check` asks for one, stop and report) |
| acceptance | `/usr/bin/python3 tests/test-bare-machine.py` exits 0, the new tests for acts 1 to 3 in it; `PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 scripts/plugin-version-check` exits 0 |
| verify | amendment 1's: `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id>` in one background Bash, last; read the code from its line |
| budget | One commit per act. **Stop at 50k context or 35 tool calls.** `claude-opus-5-5` |

## 1. What the source says (quoted)

Round 2 found one regression amendment 1 brought in (F1, PREFIX's normalisation) and two S4s in the same Makefile lines; this amendment takes all three.

## 2. Rulings

0. This amendment beside amendment 1, a line in the charter.
1. **F1 (S3, regression), `Makefile:39`.** `PFX := $(abspath $(PREFIX))` splits a path at its spaces: with `HOME="$S/ro-src/John Smith"` under a read-only parent, `make install` exits 2 with "Permission denied: '$S/ro-src/John '"; 66da0db installed there. Fix: normalise PREFIX inside the recipe's shell (`/usr/bin/python3 -c 'import os,sys;print(os.path.abspath(sys.argv[1]))' "$(PREFIX)"` or the like), quoted everywhere it is used, for install and uninstall alike. Test: a HOME with a space, install then uninstall, nothing left of agents, and install's launcher runs `--version`.
2. **F2 (S4), `Makefile:74`.** `make uninstall BINDIR=$T/else` ignores BINDIR and removes the default PREFIX's install, exit 0, while `install` refuses it. Fix: the same `$(origin BINDIR)` guard on uninstall, exit 2, nothing removed. Test.
3. **F3 (S4, a deletion of a live share), `Makefile:91`.** With `C/share` a symlink to `../A/share`, install PREFIX=A, uninstall PREFIX=C removes A's share, exit 0, and A's launcher then says "is gone", rc 3. Fix: remove the share only when its realpath is `PFX/share/agentik-agents` with PFX itself resolved, else say why it stays, exit 2. Test.
4. **The header,** `Makefile:6`: say what install touches, and that Python leaves `$HOME/.cache/agentik/pycache` (and Apple's `Library/Caches/com.apple.python`); one S4 NICE line for that residue and for zsh's `PREFIX=~/x` landing inside the checkout (install and uninstall agree; 66da0db the same).
5. The gate, last.

## 3. Interfaces

`make install` and `make uninstall` keep `PREFIX`; both refuse a `BINDIR` on the command line, exit 2. `uninstall` exits 2 when it keeps the share.

## 4. Findings that name this row

F1 to F3 above; the residue and the `PREFIX=~/x` note to `NICE_TO_HAVE.md` (act 4).

## 5. Forbidden reads

The packet's: a file over 8 KB whole; a relay ledger or a reference snapshot whole; anything outside the wall's reads.

## 6. Report

At most six lines: the head sha; each act's commit; the gate's id and code from its line; the new tests' names and the round-2 repros rerun, each with its exit.
