---
allowed-tools: Bash(claude-costs:*)
description: Report delegated-agent API spend, seat-absorbed work, and token-efficiency advice
disable-model-invocation: false
---

Run `claude-costs` and report what it shows (if it is not on PATH, say `run make install
in the repo` and stop). If `$ARGUMENTS` names a tag key
(e.g. `id` or `phase`), pass it as `--by $ARGUMENTS` to group the spend.

Relay, without embellishment:
- The **API lane** (actual dollars billed to the API key) and how much of it
  "bought nothing" (errored or substanceless runs).
- The **subscription lane** (seat-absorbed work, list-priced) — and that the two
  lanes are different units and are never summed.
- Any **tuning advice** the tool prints (waste rate, output-cost share, cache
  hit rate, cost dispersion, per-phase overhead).
- If it prints **`PRICE TABLE DISAGREES`**, surface that prominently — the
  built-in list prices no longer match this account's billing and
  `claude-costs` needs its `PRICES` table updated.

Do not compute your own totals; report the tool's numbers.
