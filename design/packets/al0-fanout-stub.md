# Packet al0: `agentik agents fanout`, a stub that hands the call to the old tool on PATH

The brief as a private hq wrote it (row `al0-fanout-stub` of 2026-11-13), in this repo's packet shape; `make check` is the verify row, the acceptance cell holds targeted lines.

| item | value |
|---|---|
| from | agentik-hq brief al0 of 2026-11-13; the owner's words of that day (section 1) |
| pin | agents main c0193bd, plugin 1.6.3; worktree `.claude/worktrees/al0-fanout-stub`, branch `al0-fanout-stub`, cut there |
| wall | this worktree; never the worktree `ak7-plug-agents`; no push, `--amend`, rebase, merge, real install or plugin update; no `claude`, no model run, no key read; no relay verb or binary; no bare `make`; `doctor` and `route --check` only under a wall that denies the network |
| may touch | `plugin/lib/agentik-agents`, `plugin/.claude-plugin/plugin.json`, `tests/test-dispatch.sh`, `tests/test-bare-machine.py`, this packet, a charter under `history/sittings/` |
| acceptance | with a stub `claude-fanout` (prints `argc=$#`, each argument in brackets, exits 7) first on a temp PATH of `/usr/bin:/bin`: `A fanout --budget-usd 2 'a b' '' -x` prints `argc=5` and the five as given, exit 7; `A fanout --yes --budget-usd 2 p --yes -- --yes` prints `argc=5`: `--budget-usd`, `2`, `p`, `--`, `--yes`, exit 7; with none on PATH `A fanout x` exits 2, stdout empty, R3's line on stderr; with a link to a file inside the dispatcher's folder, R4's line, exit 2, the file not run; `A fanout --help` R5's four lines, exit 0, the stub not run; `A --help`, `A help`, `A`, `A nosuchverb` byte-equal to c0193bd; the same through an installed launcher; R8's link kept; `bash tests/test-dispatch.sh` and `tests/test-bare-machine.py` green. At c0193bd every `fanout` call exits 2 with the usage lines |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c 'make check > <scratch log> 2>&1'`, then `agentik session gate wait <id> --strict --timeout 540`, in the foreground, last |
| budget | One commit per group by explicit path, the packet first, then the tests, then the code. `claude-opus-5-5`, high |

## 1. What the source says

- **The owner, 2026-11-13.** "Can you stub out an entry point for agentik to direct claude-code to use the fanout for the time being. Then we can install it with a stub".
- A second computer calls an older tool, `claude-fanout`, by name. The API lane that replaces it is designed and not built; its front door will be `agentik agents fanout`. This row gives that verb now as a pass-through, so the name installs and works today and keeps working when the real fan-out lands behind it.

## 2. Rulings

0. This packet, committed first; then the failing tests; then the code.
1. **R1, the verb.** One function and one `case` arm, `fanout`. It finds `claude-fanout` with `command -v` and `exec`s it with the caller's arguments unchanged in number, order and bytes, so its output and exit are the caller's.
2. **R2, `--yes`.** Each argument exactly `--yes` before a `--` argument is dropped; after a `--` nothing is. No other argument is read, changed or checked.
3. **R3, no old tool.** stderr `agentik agents fanout: the API lane is not in this version yet, and no claude-fanout is on PATH to hand the call to.`, exit 2, stdout empty.
4. **R4, no loop.** When the found tool's resolved path (`readlink -f`) lies inside the dispatcher's folder `$here`, it is not run: exit 2, stderr `agentik agents fanout: the claude-fanout on PATH is this tool's own forward, and the API lane is not in this version yet.`
5. **R5, help.** `fanout --help` or `fanout -h`, as the only argument: four lines on stdout, exit 0, the old tool not run.
6. **R6, not listed.** `--help`, `help` and every usage line print what they print at the pin; the verb is in no table, and no hook, skill, agent, command, description, README line or `doctor` row changes.
7. **R7.** Two lines of the dispatcher's head comment say `fanout` is this packet's stub until the lane's rows land, and what it does. POSIX `sh`.
8. **R8, the install.** No install code changes; a test holds that `install-cli --prefix P` keeps a `P/bin/claude-fanout` link to a file outside the tree, pointing where it did.
9. **R9.** Plugin 1.6.4, a patch, in the last commit that touches `plugin/`.

## 3. Interfaces

- `agentik agents fanout [--yes] ARGS...`: exec of PATH's `claude-fanout` with ARGS (R2's drop applied); exit its code; 2 under R3 or R4; 0 for R5's help.
- **Tests.** `tests/test-dispatch.sh`: the stub cases (R1 to R5), the pin's dispatcher from git for R6's byte compare (skipped where the pin's object is absent), the old "fanout is gone" case dropped from the retired list. `tests/test-bare-machine.py`: the seven `fanout` calls through the launcher `install-cli --prefix P` writes, and R8.

- **Not built.** The lane itself: no wall, key read, ceiling, job file, count, setting, hook line or forward of the old name. `Makefile`'s `RETIRED`, `agents_install.py` and every description stay as they are.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

A file over 8 KB whole; the worktree `ak7-plug-agents`; the owner's state under `~/.local/state`; any key; transcripts.

## 6. Report

The branch and sha; the gate's id and its line; each acceptance line as seen; choices; leftovers.
