# design/04: the API lane, and why it left

Status: **removed**, by packet a-s17 (`design/packets/a-s17-cut.md`), on the owner's word of 2026-10-31. The code last stands at commit d8ca583, plugin 1.3.2. This is the note the removal keeps. Nothing here runs.

## What it was

Headless Claude Code runs billed to an Anthropic API key, a Console project, rather than the seat:

| piece | at d8ca583 | what it did |
|---|---|---|
| the wrapper | `bin/claude-api-agent`, the verbs `api`, `setup-key`, `key-status`, `edit-key`, `remove-key`, `pin-proxy`, `usage`, `profiles`, `help api` | one `claude --bare -p` run on the key, under a role profile and a spend ceiling; the key's SOPS store; the usage log and run dirs under `~/.local/state/agentik-agents/api/` |
| the fan-out | `bin/claude-fanout`, the verb `fanout` | concurrent shards under one hard dollar budget |
| the cost tool | `bin/claude-costs`, the verb `costs` | API dollars, seat-absorbed work at list rates and the free local lane, side by side, with tuning advice |
| the status rows | `bin/claude-agents`, lane `api` and the internal `fold` | each run live, nested under the seat that launched it |
| the queue MVP | `bin/queue-mvp` | an interim orchestrator over a durable job queue, each attempt one API run, a model-tier ladder on failure |
| the plugin | `/agents:delegate-review`, `/agents:delegate-costs`, `/agents:delegate-implement-brief-template`, the skill `delegated-review` | the session's entry points to the above |

## Why it left

The owner's pick of build 3 of a review of 2026-10-31: the plugin is cut to `status`, the local lane and `scribe`. The review's reason, confirmed at d8ca583: this Mac holds no usage log, since `~/.local/state/agentik-agents/` does not exist, and the README itself said the lane "had never been run on this machine". Its figures come from runs of August 2026 elsewhere. It had no recorded consumer and cost about 5,900 lines of tools and 2,700 of tests to keep. No agentik repo called it.

The separation it stood for still holds in principle: the seat for the human, a key for what must not drain the seat. It comes back when something has a measured need for that, and not before.

## What it found, worth keeping

- **Billing follows the credential.** `claude --bare` reads only `ANTHROPIC_API_KEY` or `apiKeyHelper`, never OAuth or the keychain, so it cannot fall back to the seat; the wrapper also unset `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_AUTH_TOKEN` in its own process.
- **`--add-dir` does not confine `Read`.** A probe with `--add-dir` on a scratch folder read the age private key. The threat is prompt injection through what a delegate reads. The local lane carries the same warning.
- **Containment by allow-list.** A `--profile` delegate had `--tools` limited to `Read`, `Grep` and `Glob` and refused the flags that restore capability. Under `--bare`, a probe of 2026-08-19 found only `Read` working.
- **A budget is a mid-run abort.** `--max-budget-usd` is checked between requests: a $0.01 cap spent $0.0117, 1.2 times, and returned an empty result. So a fan-out reserved from one pool and deflated each shard's ceiling by 1.35.
- **Delegation fails quietly and still bills.** Three of four delegates that tried a denied tool returned a schema-valid placeholder after full cost, one at $2.15 over 14 turns. Each run needed a substance check, since the envelope said success.
- **Output discipline.** One implement run spent 53 turns and $6.44 and never emitted its code; a continuation under a header that says to write first finished in 17 turns and $1.93. The header is `plugin/implement-brief.md` at d8ca583.
- **Prices are a table that goes stale.** The cost tool compared predicted against billed per model and withheld its cache figure past 2% drift. That check left with it; the table itself stays in `bin/claude-agents` for the `status` cost column.

## To bring it back

The code and its text stand at d8ca583:

```sh
git show d8ca583:bin/claude-api-agent
git show d8ca583:README.md            # its sections "How the separation works" to "Removing the key"
git log d8ca583 -- bin/claude-api-agent bin/claude-fanout bin/claude-costs bin/queue-mvp
```

Its suites were `tests/test-arg-handling.sh`, `tests/test-run-path.sh`, `tests/test-flag-pinning.sh`, `tests/test-apirun.py`, `tests/test-fanout.py`, `tests/test-costs.py`, `tests/test-queue.py` and `tests/test-queue-http.py`. The packets that built it, `a-s5-status-api`, `a-s7-prices`, `a-s11-queue-floor` and `a-s13-apirun-race`, say why each piece reads as it did.
