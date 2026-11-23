# Packet ra1-agents-ready: the gate stays green with the working records gone, in both states

The hq's brief for row ra1: a rehearsal of the move that takes this repo's working records out of its tree. A scratch clone of this branch, every record removed and `records: out` declared, runs the whole `make check` twice: with no key (a stranger's clone, state `unset`) and with `agentik.records` naming a holder's copy of the removed records (the owner's clone, state `out`). A red that is a test's is mended here, in tests alone; a red that is the tool's stops the row.

| item | value |
|---|---|
| from | the hq's row ra1 (its rulings R1 to R6), the commons guide's section 12 (the record names, the line `records: out`, the key `agentik.records`) |
| pin | main 4e1b3da, plugin 1.10.0 (al2b-linux-wall merged); worktree `.claude/worktrees/ra1-agents-ready`, branch `ra1-agents-ready`; nothing linked |
| wall | this worktree, and two scratch folders outside every checkout; no push, `--amend`, rebase, merge, install, version or plugin update; nothing pushed from a scratch clone; the cut never run with `--go`; no `claude` started but the gate's own `claude plugin validate`; no API lane verb; no relay verb; `make` only through the gate queue |
| may touch | a fixture under `tests/` or a test's own temp copy, one commit per red (R4); this packet; a charter |
| untouched | everything under `plugin/` and `scripts/`, the `Makefile`, `.hygiene-allow` in this tree, every assertion of every test |
| acceptance | section 6 |
| verify | `make check`, once, last, through the gate queue, in this worktree |
| budget | a commit each: this packet and the charter; each red's mend, if any; the charter's last state |

## 1. What the source says

The coordinating repo's entry 63: each of the suite's public tools keeps its working records in the coordinating repo; as a tool's row lands, its charters, packets, wish list and questions move out of the public tree in one commit, and what is already pushed stays in the public history. An earlier move, unrehearsed, turned 31 tests red: tests that ran a verb on a folder inside the clone and so read the clone's records state. So this repo is rehearsed before it moves.

Baseline at 4e1b3da: `agentik records` prints `state: own`. Tracked paths under the record names: `history/` 42, `design/packets/` 36, `NICE_TO_HAVE.md` 1, none under `bugs/`, `HANDOFF.md`, `OPEN-QUESTIONS.md`, `relay/queue.yaml` or `.hygiene-live`; 79, and this packet and the charter add two.

## 2. Rulings

- R1, the scratch clone: a `git clone` of this branch with a local `main`; `git rm -r` of every tracked record path; `records: out` added as `.hygiene-allow`'s last line; one commit there alone. The removed records copied, each at its own path, under `repos/agentik-agents/` of a second scratch git repo, committed there: the holder's copy.
- R2, no key: `agentik records` in the scratch clone, then its whole `make check` through the gate queue.
- R3, the key set to the holder's copy: `agentik records` again, then the whole `make check` again.
- R4, a red that reads a record of the clone, or the clone's records state through a folder inside it, is mended in tests alone (a fixture under `tests/`, or a copy in a temp folder outside every repository), no assertion changed; a red that is the tool's own code stops the row and is reported with its reproduction; any other red is run once more.
- R5, nothing under `plugin/` moves, so no version moves; in this tree, which holds its records, `make check` is green on the head handed back.
- R6, `plugin/agents/scribe.md` names `history/` and `NICE_TO_HAVE.md` at the root, wrong in a repo that is out; it fails no gate and is a later row.

## 3. Interfaces

None changes. The rehearsal reads the resolver's states as the commons guide's section 12 gives them: `own`, `unset` (declared out, no key), `out` (the key resolves).

## 4. Findings that name this row

None in `NICE_TO_HAVE.md`. R6's line is the move's row's.

## 5. Forbidden reads

The real config file, state folder and gate list; any key store, `secrets` or sops folder; a relay ledger; the live home under a test.

## 6. Report

`S` is the scratch clone, records removed and `records: out` declared; `W` is this worktree.

| # | where | command | holds when |
|---|---|---|---|
| 1 | `S`, no key | `agentik records`; `make check` through the gate queue | `state: unset`; the check exits 0 |
| 2 | `S`, the key set | `agentik records`; `make check` through the gate queue | `state: out`, `records:` the holder's copy; the check exits 0 |
| 3 | `S` | each red on the way | its test, its cause in one line and the commit that mends it, or nothing turned red |
| 4 | `W` | `make check` through the gate queue; `scripts/hygiene --require-private`; the same with `--commits main..HEAD` | each exits 0 |

Baseline at 4e1b3da: lines 1 to 3 unrun (no such clone); line 4's check is the landing's of al2b-linux-wall, not rerun at the pin.
