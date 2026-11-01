# Packet a-s18: agents in its plugin

| item | value |
|---|---|
| from | agentik-hq HANDOFF 17, build 2; `~/code/agentik-hq/design/04-self-contained-plugins.md` §7 item 6, §2, §3, §6; hq entry 6 at a 3.9 floor; commons' c1 at 79ec094 |
| pin | agentik-agents main 9cb6c81, plugin 1.4.0; worktree `.claude/worktrees/a-s18-plugin`, branch `a-s18-plugin` |
| wall | this repo; read `~/code/agentik-commons` and `~/code/agentik-decisions/.claude/worktrees/d25-plugin` (d25's shape), never write there except running commons' `scripts/sync <this worktree>`; no push, `--amend`, rebase, merge, real `make install`, real `install-cli`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; no model server started, no `ollama` or `llama` verb, no request to `192.168.8.10` or `localhost` ports; a test never writes under the live `~/.local`, `~/.claude`, `~/.config`; never touch `~/.config/agentik/hooks-follow-launcher`; no relay verb; no `kill`, `pkill` or signal from a script; never a gate verb under a temp HOME |
| may touch | `bin/`, `share/` to `plugin/lib/` by `git mv`; `plugin/` (bin, lib, commands, skills, agents, `plugin.json`); `scripts/` (sync's copies, `vendored.sha256`); `Makefile`; `tests/`; `README.md`; `design/readme/*`; `NICE_TO_HAVE.md`; `.hygiene-allow` for paths only; this packet as the repo's packet file; a charter |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log>"`, then `agentik session gate wait <id>` in one background Bash, last; it exits 0 whatever the code: read the code from its line |
| budget | acts as in §2, one commit each. **Stop at 120k context or 90 tool calls:** commit the act in flight, write the exact resume line, report. `claude-opus-5-5` |

Read first, by sections: design/04 §2, §3, §7 item 6; commons' GUIDE §10 and `scripts/sync`; d25's branch for the shape (`plugin/lib/agentik-tool.conf`, the runner, its `install-cli` verb, `tests/test_bare_machine.py`).

## 1. What this is

Agents runs from its plugin and stops running from its checkout: today `make install` symlinks five tools from `bin/` into `~/.local/bin`. **Not here:** the `suite` plugin (c2); any change to the router's or the rig's behaviour.

## 2. Acts and rulings

0. This packet, committed first.
1. **The move, as c1 landed** (decided by hq, reversible): design/04 §7 item 6 says `plugin/bin` and `plugin/share`, written before c1. c1's `sync` places the canonical launcher only where `plugin/lib/` exists, so the code goes to `plugin/lib/`: `git mv bin/{agentik-agents,agentroute,claude-agents,claude-local,localrig} plugin/lib/` and `share/` to `plugin/lib/share/`. Each tool finds its siblings and `share/` relative to itself, as `localrig:71` does via `$REPO`; fix each lookup. Suite green, no behaviour change.
2. **The floor.** `agentroute` and `claude-agents` to `#!/usr/bin/python3`, running at 3.9.6; fix what doesn't run there. `claude-local` and `localrig` stay bash.
3. **The canonical form.** `plugin/lib/agentik-tool.conf` (`tool_name=agentik-agents`, `remedy=/agents:install-cli`, `runner=` the Python runner below, `old_name=`, `old_state=`). The runner is a small Python file that execs `/bin/sh <its dir>/agentik-agents "$@"`, the dispatcher, from the frozen tree, since the canonical launcher runs its runner under Python. Then commons' `scripts/sync` on this worktree. `install-cli` is a dispatcher verb (`agentik-agents install-cli`, and `/agents:install-cli`). It runs the canonical install, then links the four old names, `agentroute`, `claude-agents`, `claude-local` and `localrig`, from the bin dir into the frozen tree, each by a temp link and a rename. It replaces only a link or an absent path, never a regular file, and says so. They stay on PATH until 2026-12-31: session's `launch.py:37` and the dispatcher's own table name them.
4. **`make install`** keeps a dirty guard, then runs the plugin's `install-cli` with `HOME`/`PREFIX` honoured so a test can aim it at a temp home. `unlink-retired` stays. `uninstall` removes what install-cli wrote, and only links that point into its share.
5. **The bare-machine test.** `git archive HEAD plugin` into `$T/.claude/plugins/cache/agentik/agents/<version>/`, env exactly `HOME=$T`, `PATH=/usr/bin:/bin`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, a decoy in the cwd. Run `plugin/bin/agentik-agents status` and `route --check`, and `doctor` naming the local lane's prerequisites without failing (exit 0, the missing ones named). Then `install-cli` under `$T`: the launcher, the door, the four old names as links into the frozen tree, `--version` at the new version, and `agentroute --help` through its link. Nothing reaches a model server.
6. **Docs and the version.** README says install is `install-cli`; plugin `1.5.0`, one bump, last; the README count from the suite, the sidecar by hand, no `make readme` (it runs `claude`).

## 3. The stop

Stop and report, committing what is there, on: a tool that cannot run at 3.9 without a design change; the canonical module unable to name agents without editing it; the router or rig changing behaviour. A stop is a result.

## 4. Report (at most twelve lines)

The branch and sha; each gate's id and its code from the line; each act's result; the suite's counts; the bare test's commands and exits; anything decided or left over, and if you stopped, the exact resume line.
