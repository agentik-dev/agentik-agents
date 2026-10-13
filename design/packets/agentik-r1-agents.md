# Packet agentik-r1-agents: the `agentik-agents` dispatcher, the `agents@agentik` plugin, the agents state folders

| item | value |
|---|---|
| from | agentik-commons `design/agentik-r1.md` §4.1–§4.3, §5.1–§5.3, §6.1, §6.2 (this repo's row), §6.3 (c1 c15 c17–c19), §8.1–§8.2, §10 (D2 D3); step 0 landed in the owner's ledger (2026-10-13). The builder reads THIS packet, those sections and §5; nothing else |
| pin | `main` at `78ce312` or later; agentik-commons `main` after agentik-r1-commons merges; branch and worktree `agentik-r1-agents`, off main; a hand-run builder |
| wall | this repo only; agentik-commons read-only (its `scripts/sync` writes here). No push, `--amend`, rebase, network or API call. Merged without installing (§8.1 step 2): `make install` only into a `mktemp -d` BINDIR; no `claude plugin` command; never start a router or `pkill -f`. Never write in `~/.local/state` or `~/.config`, read a transcript, or build or run a relay binary or verb |
| may touch | `bin/*` (`bin/agentik-agents` new), `plugin/**` (`plugin/commands/agents-status.md` becomes `status.md`), `tests/*`, `Makefile`, `README.md`, `.gitignore`, `.sops.yaml`, `.hygiene-allow`, `scripts/{agentik,hygiene,bounded,vendored.sha256}` by sync only, `NICE_TO_HAVE.md`; delete `.claude-plugin/marketplace.json`. Under `design/`, only this packet's §6 report |
| acceptance | `test -e .claude-plugin/marketplace.json; echo $?` reads `1`; `test -x bin/agentik-agents; echo $?` reads `0`; `grep -c '"name": "agents"' plugin/.claude-plugin/plugin.json` reads `1`; `test -f plugin/commands/status.md; echo $?` reads `0` |
| budget | 120 turns, 150k context; commit per act; checkpoint at 80% |
| verify | `make check` |

## 1. What the source says

- **§4.1–§4.3.** `agentik-agents` is a sh dispatcher installed by `make install`; the eight scripts stay as they are, aliases until 2026-12-31 (r2 moves them to `libexec/`). Its verbs are §4.2's table exactly (`api`, the six key verbs, `profiles`, `help api`, `fanout costs local`, `status fold`, `rig`, `route`, `doctor`); `queue-mvp` gets no verb.
- **§5.1–§5.2, D2.** The plugin becomes `agents@agentik`: `/agents:status` (was `agents-status`), `/agents:delegate-*`, `agents:local-*`, the two skills; plugin code calls the dash name; `allowed-tools` becomes `Bash(agentik-agents *)`. This repo's `marketplace.json` is deleted.
- **§6.3.** c1: `bin/claude-agents:104` reads the session plugin's state folder, now `agentik-session`. c15: the `.hygiene-allow` rows are renamed. c17: state `agentroute/` → `agentik-agents/route/` (`AGENTROUTE_STATE_DIR` wins); c18: state `claude-api-agent/` → `agentik-agents/api/` (`CLAUDE_API_AGENT_LOG` wins); c19: `~/.config/agentroute/` → `~/.config/agentik/agents/route/`. Folders move in the cold window, not here.
- **§6.2, §6.1.** (a) `bin/{claude-local,localrig,queue-mvp}`; (b) `mkt.json`, `plugin.json`, `plugin/agents/local-*.md`, `delegate-local.md`, the two `SKILL.md`, `README.md`, `Makefile:84`; (c) as above; test `tests/test-status.py`. Exceptions: the eight names, the `x-claude-code-*` headers, hygiene's patterns.
- **§8.2, D3.** Vendor `scripts/{agentik,hygiene,bounded}` by commons' `scripts/sync`; `renamed` reads 0; the install also installs the vendored `agentik`. Fails before: `agentik-agents setup-key` reaches a stub `claude-api-agent --setup-key`.

**Live hits** (lines per file). Clear 17: `marketplace.json` 2, `.gitignore` 1, `.sops.yaml` 3, `README.md` 116, `plugin.json` 1, `plugin/agents/local-*` 5, `plugin/commands/*` 30, the two skills 17. Allow 20 (ruling 6): `Makefile` 13, `.hygiene-allow` 6, `bin/*` 151 over 8 files, `tests/*` 80 over 10 files. Plus one charter, `history/sittings/2026-10-13-1.md` 2 (ruling 7).

## 2. Rulings (decided inside the record, one sentence each)

1. The dispatcher runs each script from its own resolved directory (`readlink -f "$0"`), so a test copies it beside stubs; r2 points it at `libexec/`.
2. It execs with the args unchanged; no verb or an unknown one prints usage on stderr and exits 2; `--help` and `help` print the verb table with each script (the alias map, kept out of the README); `--version` prints `agentik-agents 1.2.0`.
3. `doctor` prints one row per tool on PATH (the eight, `agentik-agents`, `agentik`), then `claude-api-agent --key-status` and `agentroute --check`, and exits 0: it reports, it does not gate; the Makefile's `doctor` runs it.
4. A c-item reader takes the new path when it exists, else the old one when it exists, else the new; a writer writes where its reader resolved; the env overrides still win.
5. The scripts print no rename note in r1 (kept as they are, §4.1); a line printed for a person names the `agentik agents …` form.
6. Rows `bin/*`, `tests/*` (aliases, fallbacks, headers not ours), `Makefile` (alias install lines), `.hygiene-allow`, `scripts/hygiene` (its patterns), each `: renamed` with its reason; the old plugin name still goes from them (line 14).
7. `history/sittings/*: renamed  # per-packet records (§5.3)`, since commons' newest-per-suffix rule counts each packet charter as live.
8. `make install` links `agentik-agents` and the eight into `$(BINDIR)` and copies `scripts/agentik` there; `uninstall` leaves `agentik`, which other tools install too; `plugin-install` prints the commons marketplace line and `claude plugin install agents@agentik`.
9. `check-unlocked` adds `sh -n bin/agentik-agents`, `shasum -a 256 -c --status scripts/vendored.sha256` and `tests/test-dispatch.sh`; `tests/test-hygiene.py` only swaps its expected exits (1 hit, 2 usage).
10. The README is rewritten around `agentik agents <verb>`, naming none of the eight; `1.2.0` stays (r2 bumps the major).

Any further fork: decide inside the record; log it in §6.

## 3. Interfaces

| item | contract |
|---|---|
| `bin/agentik-agents` | POSIX sh, `sh -n` clean; §1's verbs, rulings 1–3 |
| `tests/test-dispatch.sh` | stubs echo `$#:$*`; a case per verb row, exit 2, `--version` |
| c1, c17–c19 | the readers in `bin/*` per ruling 4; `test-localrig.sh`, `test-agentroute.py` cover new, old and neither; `test-status.py` covers c1 |
| plugin | `name` `agents`; `allowed-tools: Bash(agentik-agents *)` plus the non-agents tools each file has today; calls are `agentik-agents <verb>` |

## 4. Findings that name this row

None. The table below is the whole acceptance (the header row holds its read-only subset; `verify` is the gate line). Run in the worktree after the last commit. `S` stands for `d=$(mktemp -d); cp bin/agentik-agents $d/; for s in claude-api-agent claude-agents agentroute; do printf '#!/bin/sh\necho "$#:$*"\n' > $d/$s; chmod +x $d/$s; done`.

| # | line | reads |
|---|---|---|
| 1 | `make check >/dev/null 2>&1; echo $?` | `0` |
| 2 | `scripts/hygiene --json \| python3 -c 'import json,sys;print(sum(f["group"]=="renamed" for f in json.load(sys.stdin)["files"]))'` | `0` |
| 3 | `S; $d/agentik-agents setup-key; rm -r $d` | `1:--setup-key` |
| 4 | `S; $d/agentik-agents api p1 'a b'; $d/agentik-agents profiles; $d/agentik-agents help api; rm -r $d` | `2:p1 a b`, `1:--list-profiles`, `1:--wrapper-help` |
| 5 | `S; $d/agentik-agents status; $d/agentik-agents route --check; rm -r $d` | `1:status`, `1:--check` |
| 6 | `bin/agentik-agents nosuch 2>/dev/null; echo $?; bin/agentik-agents --version` | `2`, `agentik-agents 1.2.0` |
| 7 | `d=$(mktemp -d); make install BINDIR=$d >/dev/null; ls $d \| wc -l; test -L $d/agentik-agents && test -f $d/agentik && ! test -L $d/agentik && echo ok; rm -r $d` | `10`, `ok` |
| 8 | `d=$(mktemp -d); for m in 0 1; do [ $m = 1 ] && mkdir $d/agentroute; env -u AGENTROUTE_STATE_DIR XDG_STATE_HOME=$d XDG_CONFIG_HOME=$d python3 -c 'import runpy;print(runpy.run_path("bin/agentroute",run_name="probe")["STATE_DIR"])' \| sed "s\|$d/\|\|"; done; rm -r $d` | `agentik-agents/route`, `agentroute` |
| 9 | `grep -rh '^allowed-tools' plugin \| grep -c 'Bash(agentik-agents \*)'` | `6` |
| 10 | `shasum -a 256 -c scripts/vendored.sha256 \| grep -c ': OK$'` | `3` |
| 11 | `C="$(git rev-parse --path-format=absolute --git-common-dir)/../../agentik-commons"; cmp -s scripts/hygiene "$C/scripts/hygiene" && cmp -s scripts/agentik "$C/bin/agentik" && echo same` | `same` |
| 12 | `test -e .claude-plugin/marketplace.json; echo $?` | `1` |
| 13 | `ls plugin/commands \| grep -c '^agents-status'` | `0` |
| 14 | `git grep -l 'claude-code-agent[s]' -- . ':!design' ':!history' ':!NICE_TO_HAVE.md' \| wc -l` | `0` |
| 15 | `git status --short \| wc -l` | `0` |

Fails before: line 3 (no dispatcher), and lines 2, 7, 8, 12.

## 5. Forbidden reads

Read-only outside this repo: `$C` (line 11): `design/agentik-r1.md` (the sections in `from`), `GUIDE.md`; run `"$C/scripts/sync" .` once.

Forbidden: transcripts, `~/.local/state`, `~/.config` (hygiene reads its private list; never print it), the owner's ledger, other repos.

## 6. Report (under 1,500 words)

Each line's output; commits; rulings beyond §2; `NICE_TO_HAVE.md` adds.
