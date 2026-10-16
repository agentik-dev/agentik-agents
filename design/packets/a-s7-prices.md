# Packet a-s7: the cost tool's three stale numbers

| item | value |
|---|---|
| from | NICE_TO_HAVE.md's three S4 rows on `bin/claude-costs` (research fix item 1, 2026-10-14; found again by the research site's audit of 2026-10-16): the seat lane's cache writes at 1.25x, Haiku 5.5's long-prompt tier recorded but never applied, `claude-sonnet-5` at $3/$15 |
| pin | branch `a-s7-prices` off main 35026ca; worktree `.claude/worktrees/a-s7-prices`; a hand-run builder |
| wall | this repo only. No push, merge, tag, `--amend`, rebase or `git stash`. No live `claude`, no API call, no `claude plugin` verb. Never build a relay binary or run a relay verb. Never read a transcript or a real `~/.claude.json`: the tests use synthetic ones. One `make check`, started only when no other check runs on the machine |
| may touch | `bin/claude-costs`, `bin/claude-agents`, `tests/test-costs.py`, `README.md`, `NICE_TO_HAVE.md`, this packet |
| acceptance | `/usr/bin/python3 tests/test-costs.py 2>&1 \| tail -1` reads `N passed, 0 failed` (main: 66 passed); `/usr/bin/python3 tests/test-status.py 2>&1 \| tail -1` and `/usr/bin/python3 tests/test-apirun.py 2>&1 \| tail -1` each read `N passed, 0 failed` (main: 122 and 81); the branch's `tests/test-costs.py` run in a scratch copy holding main's `bin/` prints FAIL on each named check of §3; `grep -c 'one_request=True' bin/claude-agents` reads 2 |
| budget | one builder sitting, 40 turns, checkpoint at 32; one commit per act |
| verify | `make check` |

## 1. What the source says
- The Anthropic "Pricing" page (platform.claude.com/docs/en/about-claude/pricing), as of 2026-10-14: a five-minute cache write bills 1.25x input and a one-hour write 2x. Sonnet 5 lists at $2/$10 per million input/output tokens with a $0.20 cache read (0.1x); a footnote says its launch price, introductory through 2026-08-31, is now its standard price and the rise to $3/$15 will not occur. Haiku 5.5 lists at $0.10/$0.50 up to 100,000 prompt tokens and $0.50/$2.50 above, with a $0.05 cache read and $0.625 (five-minute) and $1 (one-hour) writes above it; the prompt length counts input, cache reads and cache writes, and each request is priced on its own.
- "How Claude Code uses prompt caching" (code.claude.com/docs/en/prompt-caching), as of 2026-10-14: on a Claude subscription within plan usage the main conversation gets the one-hour lifetime, while subagents, workflows, forks, compaction and session titles get five minutes; on an API key every request gets five minutes.
- The tool on main: `read_subscription_lane` sums Claude Code's recorded `costUSD` and prices nothing itself; no function reads `LONG_PROMPT_TIERS`; `PRICES["claude-sonnet-5"]` is (3.00, 15.00). `bin/claude-agents` prices each `message.id`, one request, through `predicted_cost`: the status verb's cost scan and the fold's `progress.json`.

## 2. The numbers (each from §1, none from memory)
- The seat lane's cache write: 2x input (one hour). The API lane's: 1.25x (five minutes), unchanged.
- Haiku 5.5 above 100,000 prompt tokens: $0.50 input, $2.50 output; its cache read and writes follow from that input at 0.1x, 1.25x and 2x ($0.05, $0.625, $1), as the page lists them.
- `claude-sonnet-5`: $2 input, $10 output; its cache read at 0.1x ($0.20), as the page lists it.

## 3. Rulings
1. **The seat lane prices its writes at the one-hour 2x.** `SEAT_CACHE_WRITE_MULT = 2.0`; `predicted_cost` takes `write_mult` (default `CACHE_WRITE_MULT`, so the API lane is unchanged). `read_subscription_lane` reprices each model's tokens at list with `write_mult=SEAT_CACHE_WRITE_MULT`: a priced model's `usd` is that figure and Claude Code's `costUSD` is kept as `recorded_usd`; an unpriced model keeps its `costUSD`. The lane's total sums the `usd` figures, and `--json` adds `recorded_usd`. `lastModelUsage` carries no TTL, so the seat's subagent, fork and compaction writes (five minutes) are priced at 2x too: an upper bound on those writes, as the docstring and the README say. Named check: "the seat lane prices cache writes at the one-hour 2x".
2. **Haiku 5.5's tier applies per request.** `rates(model, when, prompt=None)` returns the tier's rates when `prompt` is over the threshold, beside the introductory window it already honours. `predicted_cost(..., one_request=True)` takes the usage as one request and picks the tier by its prompt (input + cache reads + cache writes). The default, `False`, prices an aggregate at the base tier, a lower bound for a long-prompt Haiku 5.5 run: a sum of short requests can pass 100,000 while none of them does. The two per-message sites in `bin/claude-agents` pass `one_request=True`. Named checks: "haiku 5.5: one request over 100,000 prompt tokens is priced at the long-prompt tier" and "the status cost scan and the fold price each message as one request".
3. **`claude-sonnet-5` is $2/$10.** The `PRICES` row and its comment cite the page as of 2026-10-14; `INTRO_PRICING` stays empty, and its comment keeps the August billing finding as history; `price_table_drift` withholds the cache figure if this account is still billed $3/$15. The fixtures priced at $3/$15 move to $2/$10, and the drift fixture bills at $3 so that it still disagrees. Named check: "claude-sonnet-5 is priced at the page's 2/10".
4. **The prose.** No `design/readme/source.md` exists, so the README's lines change in place: the seat-lane bullet, the self-check's Sonnet 5 paragraph and "Prompt cache economics". In NICE_TO_HAVE.md the seat-lane and Sonnet 5 rows become answered-by-a-s7 notes, and the Haiku 5.5 row keeps its per-run part. Nothing under `plugin/` changes, so `plugin.json` keeps its version.

## 4. Forbidden reads
Transcripts; a real `~/.claude.json`; anything under `~/.local/state`.

## 5. Report
At most six lines: the head, each item fixed or kept with its reason, the checks added, the `make check` result, anything left out.

## 6. Charter (builder sitting 2026-10-16)
- goal: rulings 1-4, the acceptance lines green, each named check red against main's `bin/`.
- budget: 40 turns, checkpoint at 32; at most 90 tool calls.
- pin: branch `a-s7-prices`, worktree `.claude/worktrees/a-s7-prices`, off 35026ca.
- acts:
  0. this packet.
  1. rulings 1-4: each named check red first, then the fix.
  2. no `plugin/` change, so no version bump; `make check`; the charter closes.
- handover: filled at close.
