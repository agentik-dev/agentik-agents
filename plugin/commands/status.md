---
allowed-tools: Bash(agentik-agents *), Bash(echo:*)
description: What every agent on this Mac is doing now (seats, their helpers, the local lane), and whether the local lane is usable
disable-model-invocation: false
---

Report what the agents on this Mac are doing. Run, in order, and relay the results plainly.
Call `agentik-agents` by its bare name; if it is not on PATH, say `run make install in the
agentik-agents repo` and stop.

1. `echo "${ANTHROPIC_BASE_URL:-unset}"` — say whether **this session** is routed through
   the local router (an `http://127.0.0.1:…` address) or not. If not, say that local agents
   are unavailable here and that `agentik agents local` is the launcher that routes a session.
2. `agentik-agents status` — relay the table: one row per seat (a session) and one per
   helper under it, with its lane (`seat`, `helper`, or `local`), model, elapsed time, turns, context, cost, last tool and
   state (`busy`, `idle`, `quiet` or `done`). A seat's cost is its whole session's; a
   `local` helper costs 0. If it prints `no agents in the last 30 min`, say so. An exit of 1
   means the session plugin's state dir could not be read: say that, and nothing more.
3. `agentik-agents route --check` — relay the table. Any `FAIL` row is the headline for the local lane.

Keep it to the facts the commands printed. Do not diagnose beyond what a `FAIL` row says,
and do not start, restart, stop or reconfigure anything from this command.
