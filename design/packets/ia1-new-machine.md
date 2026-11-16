# Packet ia1-new-machine: no old name's link on a new machine, a person's own file passed over with exit 0, and a status table that answers alone

The hq's brief for row ia1-new-machine, in this repo's packet shape.

| item | value |
|---|---|
| from | the hq's row ia1-new-machine (its first-install review, findings 2, 6 and 12, agents' half) |
| pin | main 649651c, plugin 1.9.3 (sy2-sync merged); worktree `.claude/worktrees/ia1-new-machine`, branch `ia1-new-machine`; nothing linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or landing; no `claude`, no model, no network; no relay verb; every probe in a temp HOME and a temp prefix; `make` only through the gate queue |
| may touch | `plugin/lib/agents_install.py`, `plugin/lib/agentik-agents`, `plugin/lib/agents_plug.py`, `plugin/lib/claude-agents`; `plugin/commands/status.md`, `plugin/commands/install-cli.md`; `Makefile`; `README.md` with `design/readme/source.md` and its sums; `tests/test-bare-machine.py`, `tests/test_al6_join.py`, `tests/test-plug.py`, `tests/test-status.py`; `NICE_TO_HAVE.md` (n61, n62 leave); `plugin/.claude-plugin/plugin.json`; this packet; a charter |
| untouched | `plugin/lib/agentik_install.py` (vendored; its `_old_link` is the rule), `plugin/bin/*`, `scripts/*` |
| acceptance | section 6's lines 1 to 5 |
| verify | `make check`, once, last, through `agentik session gate run`, then `gate wait --strict` |
| budget | a commit each: packet, the tests seen red, R1 and R2, R3, R4 and R5, 1.9.4 alone |

## 1. What the source says

The owner, 2026-11-16: "Use up to 8 opus agents to build anything to help us with install/upgrade concerns." His standing ask: "setup and doctor usable today".

The review's finding 2: a person's own `~/.local/bin/claude-local` stops the suite's setup at agents' `install-cli` (exit 1), and a first setup writes the four old names the plan never showed; the doctor lists them as wanted. Finding 6: `agentik-agents status` with no session plugin exits 1 (`cannot read the sessions dir`), so the README's "The table works alone" fails. Finding 12: `/agents:status` sends a plugin-only person to `make install`.

Baseline at 649651c, each in a temp HOME: a regular file `claude-local` makes `install-cli` exit 1, twice, the file kept; a new prefix gets `agentroute`, `claude-agents`, `claude-local` and `localrig`; a prefix holding our four links has each refreshed to the new tree; `status` with no sessions folder exits 1.

## 2. Rulings

- R1: each of the four old names is linked only where a link of that name already stands and is ours to refresh, as `agentik_install._old_link` rules it; a new machine gets none. claude-fanout (the API lane's forward, al6) keeps its own rule.
- R2: a person's own file under one of the four is left byte for byte and `install-cli` exits 0, one stderr line naming what was left; on every run.
- R3: the doctor, text and `--json`, no longer lists the four as wanted; an old name whose link stands on PATH is a note.
- R4: `status` with the sessions folder missing draws an empty table and exits 0, with one line saying the rows come from the session plugin and none of its sessions has run here (text: the table's last line; `--json`: stderr). A folder that exists and cannot be read stays exit 1.
- R5: `plugin/commands/status.md` names `/agents:install-cli` where the command is not on PATH, never `make install`; its words for the missing folder follow R4.
- R6: the README's "The table works alone" is made true by R4; its first lines keep their form. Its install-cli sentence (line 33) says what R1 does.
- R7: tests first, failing at the pin, for R1, R2 and R4, in a temp HOME; delete none. Assertions that pinned the old behaviour are rewritten to the rulings.

## 3. Interfaces

- `agents_install.link_old(bin_dir, tree, err, names=OLD)` returns `(linked, left, passed)`: the names linked, those it could not link (exit 1), and the old names a person's own file holds (exit 0).
- `install-cli`'s stderr line for R2: `install-cli: left <names> in <bin> as it is: not a link, so no old name's to refresh`.
- `claude-agents`: `collect()` sets `_absent` when the sessions folder does not exist (`FileNotFoundError`); `ABSENT` is R4's line.
- `agents_plug`: `TOOLS` is `agentik-agents`, `agentik`; `OLD_NAMES` rows are of kind `old_name`, a `note` only where a link stands on PATH, else no row.
- `make uninstall` says nothing of an old name that is absent.

## 4. Findings that name this row

The review's findings 2, 6 and 12 (agents' half); NICE n61 and n62, which leave with this row. Not built here: commons' setup quoting the last line of a failed step (finding 2's second half); relay's `/relay:doctor` (finding 12's other half).

## 5. Forbidden reads

The real `~/.local`, `~/.claude`, `~/.config` and anything under `~/.local/state`; a relay ledger.

## 6. Report

`B` is `tests/test-bare-machine.py`, `J` `tests/test_al6_join.py`, `S` `tests/test-status.py`, `P` `tests/test-plug.py`. Lines: 1 a person's `claude-local`: exit 0, the file as it was, a second run the same (`B` test_6, `J` InstallTest test_old_name_file); 2 a new prefix after `install-cli`: none of the four (`B` test_5, test_7, `J` InstallTest test_off); 3 a prefix holding our four links: each refreshed (`B` test_15); 4 `status` with no sessions folder: exit 0 and the line (`B` test_1, `S` its exit codes, `P` test_10); 5 `make check` green through the queue, hygiene with `--require-private --commits main..HEAD` exit 0.
