# Packet a-s18, amendment 1: the refuter's round 1

The amendment as a private hq wrote it (its `history/sessions/BRIEF-2026-11-01-a-s18-a1.md`), in this repo's packet shape beside [the packet](a-s18-plugin.md), which stands; its home paths and the LAN's address put in words for the public scan.

| item | value |
|---|---|
| from | a-s18's refuter, round 1, FAIL at 66da0db (hq sitting 2026-11-01-1); the packet, hq's `history/sessions/BRIEF-2026-11-01-a-s18.md`, stands, this adds to it |
| pin | branch `a-s18-plugin` at 66da0db, worktree `.claude/worktrees/a-s18-plugin` |
| wall | the packet's wall, unchanged: this worktree only; no push, `--amend`, rebase, merge, real `make install`, real `install-cli`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; no model server, no `ollama`/`llama` verb, no request to the LAN's model server or a localhost port; a test never writes under the live `~/.local`, `~/.claude`, `~/.config`; never touch `~/.config/agentik/hooks-follow-launcher`; no relay verb; no `kill`, `pkill` or signal from a script; never a gate verb under a temp HOME; this Mac's shell is zsh, so `bash -c` for bash syntax |
| may touch | `plugin/lib/agents_install.py`, `Makefile`, `tests/`, `plugin/.claude-plugin/plugin.json` (only as act 4 says), `NICE_TO_HAVE.md`, this amendment as a packet file beside the packet, the branch's charter |
| acceptance | `/usr/bin/python3 tests/test-bare-machine.py` exits 0 (F1's and F2's tests in it); `PREFIX=$S/leak /usr/bin/python3 tests/test-bare-machine.py BareMachine.test_7_make_install_and_uninstall` exits 0 and the leak folder holds nothing; `bash tests/test-dispatch.sh` exits 0 |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id>` in one background Bash, last. It exits 0 whatever the job's code: read the code from its line |
| budget | One commit per act. **Stop at 80k context or 50 tool calls:** commit the act in flight, write the exact resume line, report. `claude-opus-5-5` |

## 1. What the source says (quoted)

The refuter's round 1 found three bugs it reproduced (F1 to F3) and leads that block nothing (act 5). The packet's acts 0 to 6 stand as landed; these acts follow them.

## 2. Rulings

0. This amendment, committed beside the packet, and a line in the branch's charter.
1. **F1 (S3), `plugin/lib/agents_install.py:27-34`.** A refused old name `continue`s past that tool's `chmod`, so the tool stays 0644 in the frozen tree and its dispatcher verb breaks. Repro: a regular file at `$T/.local/bin/localrig`, `install-cli` (exit 1, as specified), then `$T/.local/bin/agentik-agents rig --version` prints `localrig: Permission denied`, exit 126. Fix: chmod the four tools in a loop of their own before any link decision, and a test that holds the repro (refused name, its verb still runs through the dispatcher).
2. **F2 (S3), `Makefile:35-36, 67-79`.** `uninstall` judges "ours" by raw PREFIX/BINDIR text while install-cli normalises PREFIX and ignores BINDIR, and it deletes the share whatever it skipped, leaving a launcher that says "is gone" (exit 3) and four dangling links, exit 0. Repro: `make install PREFIX=$T/p/` then `make uninstall PREFIX=$T/p/` prints "skipped" five times, then removes `$T/p//share/agentik-agents`. With `BINDIR=$T/elsewhere`, install writes into PREFIX/bin and prints a misleading "not on PATH" note. Fix: compare normalised paths; remove the share only once the launcher has been removed (else say why it stays, exit nonzero); drop `BINDIR ?=` or pass it to install-cli, the builder's choice, one sentence in the charter. Tests: the trailing-slash PREFIX round trip leaves nothing behind; a launcher not ours keeps the share and says so.
3. **F3 (S4, taken here because the test is open), `tests/test-bare-machine.py:175`.** test_7 hands the caller's whole environment to `make`, so an exported PREFIX, BINDIR or XDG_* escapes the temp home. Repro: `PREFIX=$S/leak /usr/bin/python3 tests/test-bare-machine.py BareMachine.test_7_make_install_and_uninstall` fails and writes the launcher, door and four links into `$S/leak/bin`. Fix: build the env from HOME and PATH only (and what `make` needs), never the caller's; rerun that repro and see it pass with nothing in `$S/leak`.
4. **The version.** Run `plugin-version-check` as `make check` does. If a plugin change after the bump needs another, bump `plugin.json` to `1.5.1`, one bump, last, and the README or sidecar line that names the version; otherwise it stays 1.5.0. Say which.
5. **NICE.** One S4 line each in `NICE_TO_HAVE.md`, with the refuter's evidence: F4 (`plugin/lib/claude-local:120`, `plugin/lib/localrig:349,352`: `/agentroute --serve` is still an argv substring, `pgrep -fl` lists `notrouter "see /agentroute --serve"`; identify the router by its port or a pid file); install-cli writes the launcher before `link_old`'s chmod, a window that would give 126 (a lead, not reproduced); `link_old` runs after `agentik_install` releases its lock, so two installs could race on the links (a lead); the bare test's sandbox denies only the network, and a `(deny file-write*)` on the live home would make it a proof; in a frozen tree `claude-local`'s `explore_md` looks first at `<share>/agents/local-explore.md`, outside the tree; `python_row` reads `~/.local/share/.python-version` from a frozen tree; `design/01`, `design/04-api-lane` and `design/05` still name `bin/` paths.
6. The gate, last, as `verify` says.

## 3. Interfaces

Unchanged from the packet: `agentik-agents install-cli [--prefix P]`, exit 0 done, 1 it could not. `make install` and `make uninstall` keep `PREFIX`; `uninstall` exits nonzero when it keeps the share.

## 4. Findings that name this row

F1 to F3 above; F4 and the leads to `NICE_TO_HAVE.md` (act 5).

## 5. Forbidden reads

The packet's: a file over 8 KB whole; a relay ledger or a reference snapshot whole; anything outside the wall's reads.

## 6. Report

At most eight lines: the branch's head sha; each act's commit; the gate's id and its code from the line; the suite's counts; F3's repro rerun and what `$S/leak` holds after; the version, 1.5.0 or 1.5.1; anything left over, and if it stopped, the exact resume line.
