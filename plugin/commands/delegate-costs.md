---
allowed-tools: Bash(agentik-agents *)
description: Report delegated-agent API spend, seat-absorbed work, and token-efficiency advice
disable-model-invocation: false
---

Run `agentik-agents costs` and report what it shows (if `agentik-agents` is not on PATH,
say `run make install in the agentik-agents repo` and stop). If `$ARGUMENTS` names a tag key
(e.g. `id` or `phase`), pass it as `agentik-agents costs --by $ARGUMENTS` to group the spend.

Relay, without embellishment:
- The **API lane** (actual dollars billed to the API key) and how much of it
  "bought nothing" (errored or substanceless runs).
- The **subscription lane** (seat-absorbed work, list-priced) — and that the two
  lanes are different units and are never summed.
- Any **tuning advice** the tool prints (waste rate, output-cost share, cache
  hit rate, cost dispersion, per-phase overhead).
- If it prints **`PRICE TABLE DISAGREES`**, surface that prominently — the
  built-in list prices no longer match this account's billing and
  the costs tool needs its `PRICES` table updated.

Do not compute your own totals; report the tool's numbers.
