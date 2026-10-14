# design/01 — The local agent lane: Fable orchestrates, Qwen 3.8 27B does the legwork

Status: **BUILT (S1–S4), uncommitted** — designed and built 2026-09-04 from research plus
measured runs on this Mac. §12 tracks the slices; §11 logs what was applied to the
machine. Evidence and the prototype live in `design/01-local-agent-lane/`.

## 0. TL;DR

Claude Code has **one API endpoint per session**, so "Fable on the main thread, subagents on
the local model" cannot be expressed in agent frontmatter today (anthropics/claude-code
#38698 is open). The split has to happen in a proxy that routes **by model name**, or at a
process boundary. This design does the first with a stdlib router (~743 lines today)
(`agentroute`) and keeps the second (the existing `claude-api-agent` wrapper) as a
zero-cost lane for read-only shards.

Three facts make the router trivial and were verified live today:

1. **Ollama already speaks the Anthropic Messages API** (`/v1/messages`, streaming, tools,
   thinking) and **maps Claude Code's `output_config.effort` onto Qwen's thinking level**.
   No OpenAI translation layer is needed, which is the whole reason claude-code-router
   exists. Unsloth's server speaks the same format.
2. **A session whose only override is `ANTHROPIC_BASE_URL` stays on the claude.ai seat.**
   Claude Code forwards the OAuth bearer plus the `oauth-2025-04-20` beta; a router that
   passes headers through verbatim keeps Fable on the Team seat (proved in run T5b).
3. **Subagent `model:` frontmatter accepts any string** when a base URL is set, so
   `.claude/agents/local-*.md` with `model: qwen3.8:27b-mtp-q8_0` + `effort: low` is
   the whole per-agent routing mechanism.

The tuning that matters, in order: pin `effort` on every local agent (Qwen 3.8 defaults
to **xhigh** reasoning and spent **5 minutes / 4,299 thinking tokens** on a three-line
file when unpinned), run Ollama **≥ 0.33.2** (done 2026-09-04; 0.32.12 500'd on every non-bare
Claude Code request), keep Claude Code's `<total_tokens>` reminder message away from the
local backend (the router strips it; with it present every subagent turn re-prefills from
zero, 36 s, without it turn two prefills in 0.4 s), keep
local agents to **one or two at a time** (qwen35 is a single-slot architecture in Ollama),
and never map the `haiku` alias to the local model (it also drives Claude Code's
background calls).

## 1. Goal and non-goals

**Goal.** A long interactive session on `claude-fable-5-1[1m]` (effort xhigh, as today)
where Fable delegates mechanical and mid-judgment work to the M4 Max's Qwen 3.8 27B at
zero marginal cost and zero seat-window consumption, keeps Sonnet/Opus available for the
middle rungs, and keeps forks and deep design on Fable. The lane must be opt-in per
session, must not change how a plain `claude` behaves, and must be observable (what
ran where, how long, how many tokens).

**Non-goals.** Replacing Fable on the main thread with a local model; routing the main
thread through a cloud gateway; changing Ollama's LAN duty for the chat server/LiteLLM; a GUI.

## 2. What was researched

### 2.1 `claude-code-agents` (this repo) — as-is

- Three tools on PATH: `claude-api-agent` (a `claude --bare` wrapper billed to a
  SOPS-encrypted API key), `claude-fanout` (N shards under one dollar pool), `claude-costs`
  (two lanes: API cash vs seat-absorbed). Plus `/claude-code-agents:delegate-review`, `/claude-code-agents:delegate-costs`, the
  `delegated-review` skill, and `bin/queue-mvp` (a tier ladder sonnet → opus → fable).
- Profiles are read-only by `--tools "Read Grep Glob"`; the wrapper builds argv from an
  allow-list and **strips `ANTHROPIC_BASE_URL` before exec** (override with
  `CLAUDE_API_AGENT_ALLOW_ENDPOINT_OVERRIDE=1`). Under `--bare` the toolset is really
  Bash/Edit/Read; Grep/Glob are dropped silently (README, "SANDBOX FACTS").
- Measured economics already in the README: review shards $0.20–0.71, 33% of spend bought
  nothing, output share of cost 46%. The "deciding vs doing" advisory is exactly the
  slot a free local rung fills.
- Nothing in the repo knows about a third, free lane. `claude-costs` prices from a table;
  a local run reports a bogus `costUSD` with `costBasis: "unknown"` (observed today) and
  must be treated as $0.

### 2.2 claude-code-router (musistudio) — what it is in September 2026

- **v3.0.22 (2026-08-24), 37.1k stars, MIT.** v3 is a rewrite: an Electron desktop app plus
  a local gateway on `127.0.0.1:3456` and a web UI on `:3458`; config lives in
  `config.sqlite` (the old `~/.claude-code-router/config.json` is only a migration
  source). Deps: `@the-next-ai/ai-gateway`, `better-sqlite3`, `pm2`, `electron-updater`.
- Routing: a built-in "Claude Code" route; custom rules with header/body conditions and
  request rewrites; **Node.js script rules** (async function body with `input.body`,
  `input.headers`, `api.fetch`, `api.fs`); per-rule fallback/retry. Subagent routing is
  **prompt-tag injection**: when models carry a Description, CCR rewrites the `Agent`
  tool description so the model prefixes spawned prompts with
  `<CCR-SUBAGENT-MODEL>provider/model</CCR-SUBAGENT-MODEL>`, which CCR strips and routes.
- Agent Config "profiles" launch Claude Code via `ccr "<profile>"` with per-tier overrides
  (Fable/Opus/Sonnet/Haiku model fields) and gateway model discovery for `/model`.
- It **can import the local Claude Code OAuth login as a provider** ("Claude Code import
  reads local Claude Code OAuth credentials"), so the seat is preservable through it too.
- Verdict for example-ops: capable, but it is a GUI control plane with sqlite state,
  an npm/Electron dependency surface and a fast release cadence, and its core value
  (Anthropic→OpenAI translation) is unnecessary here because both candidate backends
  speak Anthropic format natively. It conflicts with example-mac's declare→reconcile→verify
  posture (no declarative config to freeze). Its subagent mechanism also relies on
  prompt-tag injection, whereas Claude Code 2.1.251+ has first-class frontmatter/env
  model selection. Kept as Option A in §4 for completeness.

### 2.3 Claude Code 2.1.261 — the routing facts that matter

- Subagent model precedence (v2.1.251+): Agent-tool `model` param → frontmatter `model`
  → `CLAUDE_CODE_SUBAGENT_MODEL` → session model. Frontmatter accepts aliases or a
  "full model ID"; with a custom base URL "Claude Code passes any model string through
  without validation" (verified: `--model qwen3.8:27b-mtp-q8_0` runs, with a harmless
  `[claude-code:unrecognized_model]` stderr line).
- The Agent tool's per-invocation `model` enum is `sonnet|opus|haiku|fable` only. Forks
  always use the main model. `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` pins everything.
- `effort` frontmatter (v2.1.242+) and `--effort` are sent as `output_config.effort`
  **even for unrecognized models** (captured on the wire); `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1`
  exists as a belt-and-braces switch.
- Gateway contract (docs "llm-gateway-protocol"): endpoints `/v1/messages?beta=true`,
  optional `/v1/messages/count_tokens` (falls back gracefully), `HEAD /api/hello`,
  optional `GET /v1/models` (discovery off unless `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`,
  and only IDs containing "claude"/"anthropic" are shown). Forward `anthropic-beta` and
  `anthropic-version` verbatim; stream unbuffered. Watchdogs ("Enterprise network
  configuration", code.claude.com/docs/en/network-config, "Streaming idle watchdogs", as
  of 2026-10-14): on the direct Anthropic API, 180 s to first byte, 300 s between parsed
  events and 180 s between bytes; behind a custom `ANTHROPIC_BASE_URL` such as this
  router, no first-byte deadline, and 300 s for both the event and byte watchdogs
  (`CLAUDE_STREAM_IDLE_TIMEOUT_MS`, `CLAUDE_BYTE_STREAM_IDLE_TIMEOUT_MS`; the body idle
  timeout, `API_FORCE_IDLE_TIMEOUT`, does not run on these connections). `API_TIMEOUT_MS`
  default 600000: read from the 2.1.261 docs, not re-checked against a current page.
- Seat semantics (docs "llm-gateway"): "Setting only [`ANTHROPIC_BASE_URL`], without a
  gateway credential, doesn't replace the subscription … a saved claude.ai login remains
  the active credential." Proved in T5b. Cost of that mode ("Connect Claude Code to an
  LLM gateway", code.claude.com/docs/en/llm-gateway-connect, as of 2026-10-14): **Remote
  Control is disabled** while the base URL is a non-Anthropic host. Voice dictation is
  disabled only while `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` or an `apiKeyHelper` is
  active, which the launcher clears, so the docs say it stays on (not re-tested). A
  credential, unlike a bare base URL, replaces the login and ends plan limits ("Other LLM
  gateways", code.claude.com/docs/en/llm-gateway), and Anthropic does not support
  non-Claude models behind a gateway, so this lane runs outside that support.
- `ANTHROPIC_DEFAULT_HAIKU_MODEL` is "also used for background functionality" — the
  reason the local model must not be aliased as `haiku`.
- Attribution block: stable since v2.1.181 behind a custom base URL, but for a
  third-party upstream set `CLAUDE_CODE_ATTRIBUTION_HEADER=0` so it never enters the
  local prompt cache key.
- Concurrency: default 20 subagents (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`); spawn depth 3.
  Both read from the 2.1.261 docs and not re-checked against a current page or
  re-measured (NICE_TO_HAVE.md).

### 2.4 Ollama's Anthropic compatibility (server 0.32.12 running; brew has 0.33.2; 0.33.3 out 2026-09-02)

- `/v1/messages` supports streaming, system prompts, multi-turn, base64 images, tools,
  thinking; not `tool_choice`, `metadata`, prompt caching, `count_tokens` (404).
- Source (`anthropic/anthropic.go`): `thinking.type=enabled|disabled` → `think:true|false`;
  otherwise `output_config.effort` → `think:"low"|"medium"|"high"` (`xhigh`→`high`).
  Claude Code sends `thinking:{type:"adaptive"}` for unknown models, so **effort is the
  lever**. `max_tokens` → `num_predict`; temperature/top_p/top_k/stop pass through.
- **0.32.12 defects hit today:** (a) `500 "system message must be at the beginning"` on
  every non-bare Claude Code request (it injects a mid-conversation `role:system`
  message; fixed by "renderers/qwen: tolerate non-leading system messages" in 0.32.14
  and "Qwen 3.8 system messages are now normalized" in 0.32.15); (b) hybrid/recurrent
  models re-prefill from zero when the context checkpoint doesn't match (llama.cpp
  #22384; Ollama 0.33.0: "prefill restore points are now trustworthy by construction …
  on models with recurrent layers this previously forced a request matching 46k of 47k
  tokens to reprocess from zero") and "fixed a hang where agent clients cancel long
  prefills". (c) `qwen35` = `n_seq_max = 1`: **no parallel requests** (sched.go warning;
  `OLLAMA_NUM_PARALLEL=4` is inert for this model). (d) **The `<total_tokens>` reminder breaks the prompt cache.** Claude Code appends a
  mid-conversation `role: system` message `<total_tokens>N tokens left</total_tokens>`
  after each user turn (its own `CLAUDE_CODE_TOTAL_TOKENS_REMINDER` feature). Ollama
  ≥ 0.32.15 no longer 500s on non-leading system messages; it normalizes them, and the
  shrinking countdown then lands in the prompt prefix, so llama.cpp logs "forcing
  full prompt re-processing" on every turn of a hybrid model. Measured on 0.33.2: turn
  two with the reminder present re-prefilled all 7,201 tokens in 35.6 s; with the
  reminder absent it reused 7,106 of 7,133 cached tokens and prefilled in 0.38 s
  (best case, not a guarantee: the two runs also differed in system-prompt length (3,682 against 3,629 characters) and were never compared directly, and 0.38 s was measured under `--exclude-dynamic-system-prompt-sections --setting-sources user`, not the flags the launcher uses (§14 Cache B)).
  Ollama's own `ollama launch claude` sets `CLAUDE_CODE_TOTAL_TOKENS_REMINDER=off` for
  exactly this reason (`cmd/launch/claude.go`). This design strips the message in the
  router for local routes only, so the main thread keeps its reminder.
- `ollama launch claude` exists (configures Claude Code for a local model) — not used
  here because it would take the whole session local.

### 2.5 Qwen 3.8 27B (released 2026-08-14, Apache-2.0)

- Dense 27.3B, hybrid Gated-DeltaNet:attention 3:1, native 262,144 ctx (1M with YaRN),
  vision, tools, thinking **on by default at `reasoning_effort: xhigh`** with
  `preserve_thinking` (thinking blocks are replayed across turns — context grows fast).
- Official sampling: thinking mode `temperature 1.0, top_p 0.95, top_k 20, min_p 0,
  presence 0`; non-thinking `0.7 / 0.80 / 20 / presence 1.5`. **Ollama's model defaults
  already equal the thinking-mode set** (`ollama show`), so no Modelfile is needed.
- Agentic coding: SWE-bench Pro 61.7%, Terminal Bench 2.1 73.0% (model card). Community
  reports of "zero failed tool calls across a multi-hour agentic session".
- On this box (models.yaml + today): bf16 gen 9.9 (prose) / 25.1 (structured) tok/s;
  **q8_0 11.0 prose / 25.7 JSON / 22.6 short-think** tok/s, prefill 87–229 tok/s;
  MTP draft acceptance is what makes tool calls fast (1.00) and prose slow (~0.3).
  LiteLLM's note: q8 is only ~1.24× bf16, so 4-bit should be read as ~20–24 tok/s, not
  a size-scaled 40+. **The only way back to 80 tok/s is an MoE model** (qwen3.6 35B-A3B
  is still on disk for exactly that reason).

### 2.6 Unsloth (Studio / Desktop / `unsloth run`)

- `unsloth run --model unsloth/Qwen3.8-27B-GGUF:<quant>` starts an API server
  (default bind 127.0.0.1, `-H 0.0.0.0 -p 8888` to expose) exposing **`POST /v1/messages`
  (Anthropic, "Claude Code, Anthropic SDK") and `/v1/chat/completions`**, bearer keys
  `sk-unsloth-…`, streaming, native tool calling in both formats, `--reasoning on/off`,
  `--reasoning-effort medium`, `-c 131072`; runtime flags are forwarded to the underlying
  **llama-server** ("API automatically exposes via llama-server"). Unsloth's own Claude
  Code page adds `CLAUDE_CODE_ATTRIBUTION_HEADER=0` (KV-cache invalidation), and
  `--disable-tools` so Claude Code's tools are the only tools.
- On macOS, Studio does MLX and GGUF inference (training is Linux/NVIDIA only); whether
  the **API** path can serve an MLX build on Mac is not documented — treat as "verify".
- Qwen 3.8 doc: `--chat-template-kwargs '{"reasoning_effort":"medium"}'` sets a
  **server-wide** reasoning floor; GGUF sizes: UD-Q4_K_XL ~17.9 GB, 6-bit 23–26, 8-bit 31,
  BF16 56. llama-server adds `-np N` (parallel slots), `--ctx-checkpoints`,
  `--cache-reuse`, `--reasoning-budget N`.

## 3. The constraint that shapes everything

One session = one `ANTHROPIC_BASE_URL` = one credential. Therefore:

```
                         ┌────────────────────────────────────────────┐
  claude (Fable, seat)   │ agentroute  127.0.0.1:8787                 │
  ANTHROPIC_BASE_URL ───▶│  body.model has ':' / "local/" prefix?     │
  no credential var      │    yes ─▶ http://127.0.0.1:11434/v1/messages│──▶ Ollama (qwen3.8 q8)
                         │    no  ─▶ https://api.anthropic.com  ──────│──▶ Fable / Opus / Sonnet / Haiku
                         │           (headers verbatim: OAuth bearer, │     on the Team seat
                         │            anthropic-beta, x-claude-code-*)│
                         └────────────────────────────────────────────┘
```

Everything else is configuration: which agents carry a local `model:`, what `effort`
they get, and how the ledger records it.

## 4. Options considered

| | A. claude-code-router v3 | **B. `agentroute` (this design)** | C. out-of-process local delegates | D. NAS LiteLLM as the gateway |
|---|---|---|---|---|
| Mechanism | Electron gateway + sqlite rules + prompt-tag subagent routing | small stdlib proxy routing by model name; frontmatter picks the model | `claude-api-agent --lane local` children with `ANTHROPIC_BASE_URL` → Ollama | Point the session at LiteLLM's Anthropic endpoint; routes decide |
| Seat preserved | Yes (imports the OAuth login) | **Yes** (verbatim passthrough, proved) | Yes (main session untouched) | No — LiteLLM would need the API key for Claude routes |
| In-session Agent tool, background agents, SendMessage/resume | Yes | **Yes** | No (results come back as JSON envelopes) | Yes |
| Effort → Qwen thinking | via rewrites | **native** (`output_config.effort` passes through) | native | needs `think` wiring per route |
| Declarative / example-mac-freezable | No (sqlite) | **Yes** (env + files) | Yes | Yes (already declared in example-ops) |
| Failure surface | large, moving | tiny, ours | tiny, ours | NAS hop; OpenAI↔Anthropic translation on `ollama_chat` risks tool fidelity |
| Remote Control in that session | lost | lost | **kept** | lost |

**Decision: B as the primary lane, C kept as the complementary zero-cost read-only lane.**
A is documented, not adopted. D stays what it is (the chat server's gateway).

## 5. Architecture

### 5.1 `agentroute` — the router

**Built: `bin/agentroute`** (Python stdlib, `#!/usr/bin/python3`, ~743 lines; D6),
tested by `tests/test-agentroute.py` (87 checks against stub backends, no network).
Prototype kept at `design/01-local-agent-lane/agentroute-prototype.py`. Behaviour:

- Bind **127.0.0.1 only**. Route by `body.model`: local if listed in
  `AGENTROUTE_LOCAL_MODELS`, or has a `local/` prefix (stripped), or contains `:` (an
  Ollama tag). Everything else → `AGENTROUTE_UPSTREAM` (default `https://api.anthropic.com`)
  with every header except hop-by-hop forwarded **byte-for-byte**.
- Local requests: forward to `AGENTROUTE_LOCAL_URL` `/v1/messages` (Ollama or Unsloth,
  both Anthropic-format). Answer `count_tokens` with a chars/4 estimate. Knobs, all
  defaulted safely:
  - `AGENTROUTE_LOCAL_DEFAULT_EFFORT=low` — inject `output_config.effort` when absent;
    clamp `xhigh|max` → `medium` (guards against the 5-minute spiral).
  - `AGENTROUTE_LOCAL_MAX_TOKENS=8192` — clamp `max_tokens` (Claude Code sends 32000; on
    a 15 tok/s model that is a 35-minute runaway budget). Session-wide
    `CLAUDE_CODE_MAX_OUTPUT_TOKENS` would also cap Fable, so do it here.
  - `AGENTROUTE_LOCAL_CONCURRENCY=1` — a semaphore so interleaved agents don't thrash the
    single slot's context checkpoints; queued requests still get keep-alive pings.
  - Emit an SSE comment (`: ping`) every 15 s until the first upstream byte — Ollama is
    silent during prefill and Claude Code aborts a 300 s silent stream.
  - `AGENTROUTE_LOCAL_STRIP_TOKEN_REMINDER=1` (default on) — drop any `role:system`
    message whose text is a `<total_tokens>…</total_tokens>` block before forwarding to
    a local backend. This is what makes turn two of a local agent cost 0.4 s instead of
    36 s (§2.4 d). Upstream requests are never touched. Fallback: the session-wide
    `CLAUDE_CODE_TOTAL_TOKENS_REMINDER=off`, which also blinds Fable.
  - `AGENTROUTE_FOLD_SYSTEM=1` — the shim that folded mid-conversation `role:system`
    messages into the top-level `system` array for Ollama < 0.32.15. Retired with the
    0.33.2 upgrade for OLLAMA. ⚠ NOT retired overall: design/02 §2.2 found that
    llama-server with Qwen's template still rejects a non-leading `role: system` message,
    so folding is now a PER-BACKEND option (`"fold_system": true`) that Ollama leaves off
    and llama-server/Unsloth turn on.
- Ledger: one JSON line per request to `~/.local/state/agentroute/requests.jsonl`:
  route, model, status, wall, TTFB, `usage` (parsed from the final `message_delta` when
  streaming), `x-claude-code-session-id`, `x-claude-code-agent-id`,
  `x-claude-code-parent-agent-id`, effort, and the body **shape** (keys, sizes, tool
  names) — never content, never the bearer token (log a prefix only).
- Supervision: an example-mac-tracked LaunchAgent `com.example.agentroute` (RunAtLoad, KeepAlive),
  or start-on-demand from the launcher below. Either way declared in example-mac.

### 5.2 The launcher — opt-in per session

**Built: `bin/claude-local`** (bash; linked by `make install`). Shape:

```sh
exec env ANTHROPIC_BASE_URL=http://127.0.0.1:8787 \
         CLAUDE_CODE_ATTRIBUTION_HEADER=0 \
         CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1 \
         CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
         API_TIMEOUT_MS=1800000 \
         CLAUDE_CODE_SUBAGENT_MODEL=qwen3.8:27b-mtp-q8_0 \
     claude "$@"          # no ANTHROPIC_API_KEY / AUTH_TOKEN: the seat stays active
```

As built the launcher sets `ANTHROPIC_BASE_URL`, `CLAUDE_CODE_ATTRIBUTION_HEADER=0`,
`CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1`, `API_TIMEOUT_MS=1800000`, (D5 revised)
`CLAUDE_CODE_SUBAGENT_MODEL=sonnet`, and passes `--agents` with a session-scoped `Explore`
definition (Read/Glob/Grep, `local/default`, effort low) that overrides the built-in — the
only way to move Explore, since `CLAUDE_CODE_SUBAGENT_MODEL` does not reach built-ins and
`_FORCE` drags the whole 50-tool prompt along with it; it deliberately does **not** set
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` (a seat session should behave like one) nor
`CLAUDE_CODE_TOTAL_TOKENS_REMINDER=off` (the router strips the reminder on local routes,
Fable keeps it). Its preflight table goes to stderr so `-p --output-format json` stays
clean (a bug found and fixed in the live run). Model names use the `local/` prefix:
`local/default` resolves in the router to `AGENTROUTE_LOCAL_MODEL`, so a model swap is one
environment variable rather than five agent files.
It first checks the router is answering `HEAD /api/hello` and that the local backend
lists the model, and refuses to start otherwise (a read that fails is unknown, not
worked around). Plain `claude` is untouched, so ordinary sessions keep Remote Control.
`CLAUDE_CODE_SUBAGENT_MODEL` is the one contestable line (D5). The original plan was
`local/default` so every unnamed subagent, Explore and Plan included, would run local.
Measurement overturned both halves: the env var does not reach the built-ins at all, and
the unnamed custom agent that actually shows up is `general-purpose`, whose 54-tool prompt
is 31k tokens — three minutes of prefill per turn on the 27B (§14 C3). So unnamed agents
default to `sonnet` (the tiering rule's floor for anything that is not explicitly local),
Explore is overridden by name with a 3-tool definition, and Plan stays on the seat.

### 5.3 Agent definitions — where the routing actually happens

**Built: `agents/local-*.md`** in this plugin (scoped IDs `claude-code-agents:local-…`),
carried by `claude --plugin-dir` or the installed marketplace; `claude plugin validate .`
passes. Every file says `model: local/default` plus an explicit `effort`:

| Agent | tools | model | effort | Use for |
|---|---|---|---|---|
| `local-explore` | Read, Glob, Grep | `local/default` | low | "where is X", file triage, inventories, log reading |
| `local-summarize` | Read, Glob | same | low | condense a file/dir/transcript into N lines for Fable's context |
| `local-review` | Read, Glob, Grep | same | medium | first-pass correctness/security review; findings are leads |
| `local-implement` | Read, Edit, Write, Bash, Glob, Grep; `isolation: worktree`; `maxTurns: 40` | same | medium | bounded mechanical edits with a named test to run; Fable verifies |
| `local-test` | Bash, Read | same | low | run a named test/lint/build and report the output verbatim |

Every one carries `model:` and `effort:` explicitly (the [[agent-model-tiering]] rule:
never inherit without a stated reason). Prompts follow the README's implement-brief
discipline: name the files to read, forbid exploration beyond them, demand the answer
in one final message. `memory:` is left off (a 27B at low effort should not be curating
persistent notes).

### 5.4 The ladder, revised

| Rung | Model | When Fable should pick it |
|---|---|---|
| 0 **local** | qwen3.8 27B q8, effort low/medium | mechanical and bounded: retrieval, summaries, inventories, first-pass review, run-the-tests, bulk edits with a test as the contract |
| 1 sonnet | `claude-sonnet-5` | scripted work that needs reliability across many files, or when rung 0 returned `degenerate`/unsure |
| 2 opus | `claude-opus-5` | resolution, curation, building, review that decides |
| 3 fable | main thread / forks only | orchestration, design, anything a wrong answer makes expensive |

`bin/queue-mvp`'s ladder gains rung 0 (junior → local, attempt 2 → sonnet, 3 → opus,
4 → fable) once the lane is in. Rung 0 is entered only through a named `local-*` agent
(small tool list); an unnamed agent lands on rung 1. Escalation stays objective: the acceptance check, not the
model's confidence.

### 5.5 Complement: the out-of-process lane

Add `--lane local` to `claude-api-agent`/`claude-fanout`: sets `ANTHROPIC_BASE_URL` to
the router, `ANTHROPIC_API_KEY=local` (bare mode needs *a* key variable; the router
ignores it), forces `--effort low`, and replaces the dollar budget with a wall-clock cap.
Use it for `/claude-code-agents:delegate-review` shards where money is the reason not to run them today.
Results arrive as the same JSON envelope; `claude-costs` books them as lane "local".

## 6. Tuning for Qwen 3.8 27B on the M4 Max

| Knob | Setting | Why (measured unless noted) |
|---|---|---|
| Build | **`qwen3.8:27b-mtp-q8_0`** (31.5 GB resident) | already pulled and already the chat server's `mac-chat-deep`, so agents and the chat server share one resident model; bf16 (54 GB) buys fidelity nobody can see at 10 tok/s. A UD-Q4_K_XL (~18 GB, ~20–24 tok/s) is the fallback if memory gets tight (D2) |
| Effort | `low` for retrieval/summaries/tests, `medium` for review/implement; never unset | unpinned = xhigh = 4,299 thinking tokens / 4m56s on a trivial question; `low` answered the same task in 45 s over two turns |
| Sampling | leave Ollama defaults (temp 1.0, top_p 0.95, top_k 20, min_p 0) | equal to Qwen's official thinking-mode set; Claude Code sends none |
| Context | leave 262,144 (KV is cheap on a 3:1 hybrid; q8 loads at 31.5 GB with full ctx) | per-request `num_ctx` can't be set on the Anthropic path anyway |
| Prompt size | budget **≤ 15k tokens** per local agent turn; **tool count is the lever** — a local agent's `tools:` list should stay under ~8 | tool schemas ARE the prompt: 3 tools ≈ 5.4k tokens (a custom `local-*` agent), 50 tools ≈ 26k (built-in Explore under `_FORCE`, 146 s first turn), 54 tools ≈ 31k (`general-purpose`, 172 s first turn and again 180 s on turn two); the router ledger records `n_tools` and `input_tokens` per request so an oversize agent is visible |
| Prompt cache | Ollama ≥ 0.33.0 (0.33.2 measured) **and** the `<total_tokens>` reminder stripped for local routes | measured on 0.33.2: turn two = 35.6 s with the reminder, **0.38 s** without (7,106 of 7,133 tokens cached). ⚠ measured with `--exclude-dynamic-system-prompt-sections --setting-sources user` and an API-key env — NOT the flag set `claude-local` uses —, the two runs' system prompts differed (3,682 against 3,629 characters) and were never compared directly (§14 Cache B), and one production run (§14 Live C3) re-prefilled in full on turn two *with* the strip active. Best case, not a guarantee |
| Concurrency | 1 (router semaphore); at most 2 local agents in flight from Fable | single slot; a second agent's prefill invalidates the first's checkpoints; 4-way tests gave 1.39× at best (models.yaml) |
| Output cap | router clamps `max_tokens` to 8192 for local | 32000 × 15 tok/s = 35 min worst case |
| Keep-alive | `OLLAMA_KEEP_ALIVE=30m` (or `-1`) in the LaunchAgent | 5 m default evicts between agent calls; reload ≈ 15–26 s; ties to design/35 D5 sleep policy |
| Server | **Ollama ≥ 0.33.2** (brew) replacing the 0.32.12 sideload | non-leading system messages; recurrent-layer restore points; cancel-hang fix |
| Timeouts | `API_TIMEOUT_MS=1800000`; router pings during prefill | 10-min default vs 35-s prefills is fine today; pings protect the 300-s byte watchdog |
| Thinking replay | accept | `preserve_thinking` inflates context by the thinking length each turn (4.5k → 8.9k in one turn at xhigh); low effort keeps it small |

**Memory budget.** Metal budget 107.5 GiB. q8 31.5 + qwen3.6 45 (the chat server fast/context) +
qwen3-vl 37 (photo batches) = 113.5 → eviction churn only if all three are hot; the
agents add nothing new because they ride the q8 already resident for `mac-chat-deep`.
Running Unsloth **beside** Ollama (§7) adds another 31 GB and breaks this budget; it
must replace, not join.

### 6.1 Model watch (D2 outcome, 2026-09-04)

q8_0 stays. Two kinds of successor are worth watching for, with different bars:

- **An MoE Qwen 3.8 variant** (active parameters ≲ 10B). This is the only route back to
  the ~80 tok/s the 3.6 35B-A3B build had, and models.yaml already names it as the
  option that "would dominate both". It would replace q8 for the lane *and* for the chat server.
- **An "uncensored"/abliterated 3.8-27B fine-tune** (community GGUFs such as the Ridge
  build already exist). Only if refusals ever block legitimate local work, which this
  lane's task mix (code, ops, summaries) rarely triggers. Abliteration commonly degrades
  tool-call formatting and instruction following, so treat it as a fidelity risk first
  and a feature second.

Gates before any swap (models.yaml's requalification list plus this lane's):
`ollama show` `requires` ≤ the running server; tool-call smoke through the Anthropic
path (a `tool_use` with correct arguments); `output_config.effort` → `think` still maps;
native `think:false` clean content if the chat server will share it; measured gen tok/s and
**dense-or-MoE stated**; resident GB against the 107.5 GiB Metal budget with the
photo VL model hot; turn-2 cache reuse (§10 check 4); and the five T1–T4/T6b tasks
from §14 answered correctly at effort low. `design/01-local-agent-lane/bench-ollama.py`
and the e2e scripts are the harness. Cadence: check the Qwen org on Hugging Face,
the Ollama library, and unsloth.ai/docs/models monthly; a candidate that only ships
as GGUF is a §7 trigger, not a reason to skip the gates.

## 7. The Unsloth variant

Worth it only for what Ollama can't do on this architecture: **parallel slots**
(`-np 2..4` via llama-server, with the prompt cache shared), a **server-wide reasoning
floor** (`--chat-template-kwargs '{"reasoning_effort":"low"}'`), `--reasoning-budget`, and
a possibly faster MLX build (unverified on the API path). Plug-in shape is unchanged:

```sh
unsloth run --model unsloth/Qwen3.8-27B-GGUF:UD-Q8_K_XL -H 127.0.0.1 -p 8888 \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --chat-template-kwargs '{"reasoning_effort":"low"}' -c 65536 -np 2 --disable-tools
AGENTROUTE_LOCAL_URL=http://127.0.0.1:8888 AGENTROUTE_LOCAL_AUTH='Bearer sk-unsloth-…'
```

The router treats it as just another `AGENTROUTE_LOCAL_URL`; nothing in Claude Code
changes.

### 7.1 What would make us switch (D3 outcome, 2026-09-04: not now, criteria recorded)

Any one of these, measured rather than assumed:

1. **Parallel local agents.** The ledger shows a second local agent queued behind the
   first more than ~30% of the time, or a workflow wants three or four mechanical agents
   at once. Ollama's runner is single-slot for `qwen35`; llama-server `-np 2..4` with a
   unified KV pool is real concurrency. Pass bar: two concurrent T4-shape agents each
   finish within 1.5× their solo time.
2. **A hard thinking cap.** Effort medium still produces spirals. Ollama has no
   thinking-token limit (the router's `max_tokens` clamp is a proxy); llama-server has
   `--reasoning-budget N` and a server-wide `reasoning_effort` floor via
   `--chat-template-kwargs`.
3. **Model availability lag.** Ollama needed a release (0.32.12) before Qwen 3.8 loaded
   at all. A §6.1 candidate (MoE, Dynamic quant, fine-tune) that exists only as a GGUF
   runs on llama-server the day it lands.
4. **Prompt-cache control.** After the 0.33 upgrade, §10 check 4 still fails often
   enough to matter. llama-server exposes `--ctx-checkpoints`, `--cache-reuse`,
   `--cache-ram`, `--slot-save-path` (KV survives a restart) and `--cache-type-k/v q8_0`
   for long agent contexts.
5. **MLX speed.** Unsloth's Mac API path can serve an MLX 8-bit build and it measures
   ≥ 1.5× the q8 GGUF's generation rate on the bench script (the 4-bit MLX guess in
   models.yaml is ~35–40 tok/s; that is the number to beat honestly, at 8-bit).
6. **Quality per GB.** Memory forces a 4-bit and Unsloth Dynamic (UD-Q4_K_XL) beats
   Ollama's stock q4 on the §6.1 gates.

What it costs, and would have to be solved in the same change:

- **The LAN role.** the chat server's LiteLLM routes point at Ollama on `:11434` as `ollama_chat/`
  with `think:false`, chosen because the OpenAI-compatible path returned empty content.
  Unsloth would take that over as an `openai/` route to `:8888` with per-route
  `chat_template_kwargs` (`enable_thinking: false` or `reasoning_effort`), and
  llama-server's `--reasoning-format` (thoughts into `reasoning_content`) is the likely
  fix for the empty-content trap. Re-verify it; it has bitten three model generations.
- **Memory.** It replaces the q8 in Ollama; two 31 GB copies do not fit beside qwen3-vl
  and qwen3.6. Ollama would keep only the photo VL model.
- **Ops shape.** A curl-installed Python app with its own updater and Desktop UI, a
  LaunchAgent, an example-mac declaration, `--disable-tools` always on (its server-side
  tools would shadow Claude Code's), and the `sk-unsloth-…` key into the password manager/sops.
- **Unknowns for the trial:** MLX on the API path; KV memory per slot at 64k context;
  tool-call parsing on the MTP GGUFs under Metal (the llama.cpp report of corrupted
  output was CUDA-specific); whether llama-server emits anything during prefill (the
  router's pings cover it either way).

Trial shape (one evening, reversible): install with `curl -fsSL https://unsloth.ai/install.sh | sh`;
run the command above on `127.0.0.1:8888` while Ollama keeps the LAN (31 + 31 GB fits
if qwen3.6 and qwen3-vl are cold); point one session's router at it with
`AGENTROUTE_LOCAL_URL`; run §10 checks 3–5 plus the two-concurrent test; compare
ledger numbers side by side. Switch = LiteLLM route move + LaunchAgent + models.yaml
entry; rollback = flip `AGENTROUTE_LOCAL_URL` back.

## 8. Long-session considerations

- **Main thread:** `claude-fable-5-1[1m]`, effort xhigh, thinking always on (Fable
  semantics). Delegation is what keeps the 1M window from filling: local agents return
  a paragraph, not a file dump. Keep `autoCompactWindow` at its default; the router's
  ledger shows when a subagent's *own* context is growing (thinking replay).
- **Seat window:** the lane exists to spare the 5-hour window ([[check-usage-before-fanouts]]).
  Fable still pays for every delegation turn (the Agent call and the result), so
  batch small asks into one local task.
- **Background agents:** subagents run in the background by default with fork mode on;
  local ones take 30–120 s per turn, so Fable should launch them and keep working, then
  read the notification. `maxTurns` on `local-implement` turns runaways into partial
  results Fable can resume.
- **Attribution:** every subagent request carries `x-claude-code-agent-id` (lowercase, seen on
  the wire in T6); the main thread's rows carry only `X-Claude-Code-Session-Id`; the ledger plus
  `claude-costs --lane local` answer "what did that agent cost in wall time and tokens".
- **What the session loses** under the loopback router (a non-Anthropic base URL, no
  credential; "Connect Claude Code to an LLM gateway" and "How Claude Code uses prompt
  caching", code.claude.com/docs, as of 2026-10-14): Remote Control; the first-byte
  deadline (it does not run behind a custom base URL; the 300 s byte and event
  watchdogs still do); MCP tool search, so MCP tools load upfront; and fast mode's
  availability check still goes to the Anthropic API rather than the router. Voice
  dictation is keyed on a credential (a key, token or helper), not on the base URL, so
  it stays on while the launcher keeps those unset. If a session needs Remote Control,
  use plain `claude` plus the out-of-process lane (§5.5).
- **Sleep:** an unattended long session on this Mac still hits design/35 D5 (pmset sleep
  at ~11 min). Unresolved there; unchanged here.

## 9. Security posture

- The router listens on loopback only and never has a credential of its own. The seat's
  OAuth bearer transits a local process owned by this user — the same trust as the
  `claude` binary. Log a 12-char prefix of `Authorization`, never the token.
- The local lane has **no key at all**; the wrapper's key-stripping and endpoint-pinning
  logic is untouched for the API lane.
- Local models get the same tool boundaries (`tools:` allow-lists, `--tools` under
  `--profile`) and the same caveats: `Read` is not confined to `--add-dir`; prompt
  injection through read content is the threat; never run a local agent over untrusted
  content, exactly as the README says for API delegates. A smaller model is *more*
  suggestible, not less.
- `local-implement` runs in a worktree; Fable verifies with the tests, not the agent's
  claim.

## 10. Verification (acceptance checks) — status 2026-09-04

| # | Check | Status |
|---|---|---|
| 1 | router answers, `--check` green (upstream, Ollama ≥ 0.33, model, policy) | **pass** (live) |
| 2 | seat passthrough: `--model haiku` row upstream with `Bearer sk-an…` and the oauth beta | **pass** (T5b, B2, C1–C4) |
| 3 | subagent rows local with effort low and an agent id; parent stays upstream | **pass** (B2, C4) |
| 4 | 3-tool local turn < 60 s, turn two < 2 s | **pass** (A 0.37 s, B2 0.36 s, C4 1.95 s); fails with the reminder present (35.6 s) |
| 5 | effort injected/clamped, max_tokens clamped | **pass** (stub tests; live A clamped xhigh → medium on the wire) |
| 6 | `claude-costs` third lane, $0, tokens + wall | **pass** (live block shows 6 requests / 34k tokens / $0 / Sonnet-list $0.11 at the time of the run) |
| 7 | `make test` green | **agentroute 87/87, costs 50/50, arg-handling 58/58, run-path 22/22, flag-pinning 14/14; fanout 44/45** — the one failure ("delegates were actually running before the interrupt") is in an untouched file and reproduces at HEAD in isolation, so it predates this work |

Original list:

1. `curl -sI http://127.0.0.1:8787/api/hello` → 200; `agentroute --check` reports
   upstream reachable, local backend lists `qwen3.8:27b-mtp-q8_0`, Ollama version ≥ 0.33.2.
2. `claude-local -p --model haiku "OK"` → answer, and the ledger row shows route
   `upstream`, `Authorization: Bearer sk-an…`, `anthropic-beta` containing `oauth-2025-04-20`.
3. `claude-local -p --model sonnet --agents '<local-explore json>' "delegate…"` → the
   subagent's rows show route `local`, `effort: low`, an `x-claude-code-agent-id`, and
   the parent's rows stay upstream.
4. A 3-tool local turn prefills in < 60 s and its second turn prefills in < 2 s. Passed
   2026-09-04 on 0.33.2 with the reminder stripped (0.38 s); fails with it present (35.6 s),
   so this check also guards the router's strip rule. (The pair is a best case, not a
   direct comparison: the runs differed in system-prompt length, 3,682 against 3,629
   characters, and 0.38 s was measured under flags the launcher does not use; §14 Cache B.)
5. A local run with no effort in the request gets `effort: low` injected (router test),
   and `max_tokens` is clamped.
6. `claude-costs` shows three lanes; the local lane is $0 with token and wall totals.
7. `make test` green, including a stub-backend test for streaming pass-through and the
   count_tokens estimate.

## 11. Owner steps

**Log 2026-09-04 (steps 1 and 2 done, owner-authorized):** `brew upgrade ollama`
0.33.0 → 0.33.2; example-mac `launchd/com.ollama.serve.plist` restored to
`/opt/homebrew/bin/ollama` with `OLLAMA_KEEP_ALIVE=30m` and the override comment
replaced by a dated note; `make launchd`; `launchctl bootout` + `bootstrap` (server was
idle, no LAN request in flight); version 0.33.2 verified on 127.0.0.1 and 192.0.2.10;
`ollama list` shows all four models. Gates: native `/api/chat` `think:false` on q8
returned clean content (the chat server path); a non-bare Claude Code run that 500'd on 0.32.12
completed (3 turns, 98 s); `~/.local/opt/ollama-0.32.12` (484 MB) removed. example-mac
`models/models.yaml` and `models/models.txt` updated (version, install method,
keep-alive, the q8 entry that was missing since 2026-08-14); all three files are
uncommitted in example-mac, and `make status` shows only pre-existing dotfile drift.

**Log 2026-09-04, later:** owner ran `sudo pmset -c sleep 0`; the Mac's host record declares
`pmset-sleep=0` and `scripts/verify` agrees. Repo renamed `claude-code-api-agents` →
`claude-code-agents` (directory, plugin, marketplace), remote moved from the unreachable
the owner's former GitHub org to `github.com/<owner>/claude-code-agents` (private) and pushed;
example-mac `repos.yaml` updated and the portfolio map regenerated. `~/.claude/settings.json`
now registers the marketplace under the new name and the plugin is installed, so a plain
session knows the `/claude-code-agents:delegate-local` command and the `local-delegation` skill exist. The
install is a cached snapshot (`~/.claude/plugins/cache/claude-code-agents/…/1.1.0`):
edits to agents, commands or skills reach sessions only after
`claude plugin update claude-code-agents@claude-code-agents` or a version bump.

**Still owner-only:** example-mac `make freeze` + commit (plist, roster, the Mac's host record, HANDOFF,
repos.yaml, and the settings.json/CLAUDE.md dotfile mirrors).

Original sequence, for the record:

1. **Ollama server upgrade (example-mac). DONE 2026-09-04.** `brew upgrade ollama` (→ 0.33.2 or newer), restore
   `launchd/com.ollama.serve.plist` to `/opt/homebrew/bin/ollama`, add
   `OLLAMA_KEEP_ALIVE=30m`, `make launchd`, kickstart, `rm -rf ~/.local/opt/ollama-0.32.12`
   — exactly the REVERT written in `models/models.yaml`. Then re-run the requalification
   gates there (native `think:false`, resident VRAM, LiteLLM timeout) because the chat server rides
   the same server.
2. **Roster drift (example-mac). DONE 2026-09-04.** `models.yaml`/`models.txt` didn't list
   `qwen3.8:27b-mtp-q8_0` (pulled after the 2026-08-05 inventory) and still say all three
   LiteLLM routes are on bf16; LiteLLM actually split to 3.6 fast / 3.8-q8 deep. Fold in
   at the next `make freeze`.
3. **Decide D1–D6** below.
4. Then I build slices S1–S4 (§12) and run the checks in §10; nothing touches the seat
   until step 2 of §10 passes.

## 12. Build plan (status 2026-09-04)

- **S1 router — DONE.** `bin/agentroute`: routing, header policy, the four local
  adjustments, pings, count_tokens estimate, ledger, `--check`, loopback-only bind;
  `tests/test-agentroute.py` 87/87. Running on this Mac now (started on demand).
- **S2 launcher + agents — DONE.** `bin/claude-local`; five `agents/local-*.md`; README
  "Lane 3"; deterministic entry points per this plugin's own doctrine: `/claude-code-agents:delegate-local`,
  `/claude-code-agents:local-status`, and the `local-delegation` skill, all of which preflight
  `ANTHROPIC_BASE_URL` (local agents fail in a plain `claude` session). PATH: `~/bin` was
  never on this Mac's PATH, so `make install` now defaults to `~/.local/bin` — the
  directory `claude` itself lives in — and nothing in a shell rc changes. What needs PATH
  is only the launcher you type; the agents, commands and skill are loaded by Claude Code
  from the plugin directory and need no PATH at all.
- **S3 ledger → `claude-costs` — DONE.** LOCAL LANE block and `local_lane` JSON: requests,
  sessions, agents, tokens, wall, errors, reminders stripped, pings, and a Sonnet-5-list
  "what it spared" figure; `tests/test-costs.py` 50/50.
- **S4 example-mac declarations — DONE** (uncommitted in example-mac): ollama plist on brew +
  keep-alive, `models.yaml`/`models.txt` roster, the Mac's host record posture `pmset-sleep=0`
  and the inference-host role, HANDOFF D5 closed. The router itself has **no LaunchAgent**:
  `claude-local` starts it on demand and it is not a LAN service, so there is nothing for
  example-mac to reconcile beyond the repo being present.
- **S5 (optional) `--lane local`** for the wrapper and fanout (§5.5).
- **S6 (optional) Unsloth backend** behind the same router, after D3.

## 13. Open decisions (owner)

- **D1** Ollama upgrade path: brew 0.33.2 now (recommended) vs wait for 0.33.3 in brew.
- **D2** Quant: stay on q8_0 (recommended; shared with the chat server) vs UD-Q4_K_XL for ~2× speed.
- **D3** Unsloth: not now (recommended) / trial as a replacement backend after S1–S4.
- **D4** `OLLAMA_KEEP_ALIVE` 30m vs -1, and the design/35 D5 sleep policy it depends on.
- **D5** `CLAUDE_CODE_SUBAGENT_MODEL` in the launcher (Explore/Plan go local by default)
  — recommended yes; Fable can still name `sonnet`/`opus` per call.
- **D6** Router language: Python stdlib in this repo (recommended, matches
  `claude-fanout`) vs a Go binary in the example-app idiom.

### 13.1 Decisions taken (owner, 2026-09-04)

| | Decision | Consequence |
|---|---|---|
| D1 | Upgrade now | brew 0.33.2; example-mac plist back on `/opt/homebrew/bin/ollama`; sideload retired (see §11 log) |
| D2 | q8_0 stays; watch for MoE or uncensored successors | §6.1 gates govern any swap |
| D3 | Unsloth not now | §7.1 lists the triggers, costs and the trial shape |
| D4 | Accepted | `OLLAMA_KEEP_ALIVE=30m` in the plist; `sudo pmset -c sleep 0` is the owner's command, after which the Mac's host record posture flips to `pmset-sleep=0` in the same change |
| D5 | Default taken, then **revised by measurement** (§14 C1–C4) | Built-in Explore is overridden by a session-scoped `--agents` definition on `local/default` (the env var never reaches built-ins). Unnamed agents default to **`sonnet`**, not local: the unnamed ones are `general-purpose` and kin, which carry every tool in the session (54 tools ≈ 31k tokens ≈ 3 min of prefill per turn on the 27B). Plan stays on the session model. `CLAUDE_LOCAL_SUBAGENT=local/default` restores the original intent for anyone who wants it. |
| D6 | Accepted | Python stdlib router in `bin/` |

## 14. Evidence (2026-09-04, this Mac, Ollama 0.32.12, Claude Code 2.1.261)

Scripts and the wire log are in `design/01-local-agent-lane/`.

| Run | Setup | Result |
|---|---|---|
| bench | `/api/generate`, q8_0 | prose 300 tok: 11.0 tok/s (prefill 87 tok/s); JSON: 25.7 tok/s; think=low arithmetic: 22.6 tok/s; load 0.2 s (warm) |
| T0 | `claude --bare`, Read, **no effort** | turn 1: 4,438-token prompt, 19.4 s prefill @ 229 tok/s; turn 2: **4,299 output tokens in 4m56s** (thinking spiral); killed on turn 3 at 8,889 tokens |
| T1 | same, `--effort low`, via router | 2 turns, 45 s wall, TTFB 20.5 s then 0.5 s (cache hit, 27 new tokens); 8,983 in / 428 out |
| T2 | `--model haiku` with `ANTHROPIC_DEFAULT_HAIKU_MODEL=qwen3.8…` | routed local, 9 s (warm prefix), correct answer — works, but rejected as a mechanism (§2.3) |
| T3 | `--tools Bash`, effort low | `wc -l` executed, "3 lines", 32 s |
| T4 | non-bare, Read/Glob/Grep, effort low | **500 on 0.32.12** ("system message must be at the beginning"); with the fold shim: 7,050-token prompt, 34.6 s prefill @ 204 tok/s, 45.6 s turn 1; **turn 2 re-prefilled all 7,414 tokens (41 s)** — no cache reuse |
| T5 | `--bare`, no key vars | "Not logged in" — bare ignores OAuth (expected) |
| T5b | non-bare, only `ANTHROPIC_BASE_URL`, `--model haiku` | **seat passthrough works**: upstream row shows `Authorization: Bearer sk-an…`, `anthropic-beta: oauth-2025-04-20,…`; Haiku answered; 10,431 cache-creation tokens |
| T6 | seat main (haiku) spawns `local-explore` (`--agents` JSON: `model: qwen3.8…`, `effort: low`) | **routing works**: main rows upstream on the OAuth bearer, subagent rows local with `effort: low` and an `x-claude-code-agent-id` header; stderr tags them `query_source: agent:custom:local-explore`. First attempt failed the *task* because the harness launched the parent with `--tools Agent`, which also stripped Read from the subagent (it thrashed on denials for 17,954 local input tokens — the README's degenerate-delegate pattern, reproduced locally at $0) |
| Gate A | Ollama 0.33.2, native `/api/chat` `think:false`, q8 | clean 231-char answer, empty thinking, 45 tok in 3.2 s (the chat server path intact) |
| Gate B | Ollama 0.33.2, non-bare Claude Code, no shim | the request that 500'd on 0.32.12 completes: 3 turns, 98 s; turns still re-prefilled (7,051 → 7,451 tokens, ~36–39 s each) |
| Cache A | 0.33.2, two turns, reminder present | turn 2 re-prefilled: 35.6 s wall, `prompt eval time = 35994.82 ms / 7004 tokens` (task 218). ⚠ an earlier draft quoted "forcing full prompt re-processing, 7,201 tokens" here; that log line belongs to Gate B's tasks 19/87, not to this run — the harness's `tail -14` had truncated task 218's own `task.n_tokens` line |
| Cache B | 0.33.2, two turns, `CLAUDE_CODE_TOTAL_TOKENS_REMINDER=off` | **turn 2 cached 7,106 of 7,133 tokens, prefill 0.38 s**; answer `gamma` correct. The visible difference is the trailing `<total_tokens>` message. ⚠ NOT "the only" difference: `reminder-dump-summary-2026-09-04.json` records `system_len` 3682 (A) vs 3629 (B) — 53 characters apart — and the harness only diffed turn 1 vs turn 2 *within* each run, never A vs B |
| Live A | **production router**, non-bare, `--model local/default`, Read/Glob/Grep, no `--effort` | `local/` prefix accepted by Claude Code and resolved to q8; the session's default `xhigh` effort arrived on the wire and the router clamped it to `medium`; 2 turns, 56 s, turn 2 TTFB **0.37 s**; answer `gamma` |
| Live B2 | `claude-local -p --model haiku --plugin-dir .` delegating to `claude-code-agents:local-explore` | end to end through the launcher: main on the seat (OAuth bearer, ~60k cache-read tokens per turn — the seat's prompt cache survives the relay), subagent local at `effort: low`, 2 turns 6.5 s + 6.1 s (warm), answer `beta`; a stdout-pollution bug in the launcher's preflight was found and fixed |
| Live C1 | `claude-local`, main asks the **built-in Explore** | Explore ran on **Haiku upstream**, not local: `CLAUDE_CODE_SUBAGENT_MODEL` does not reach the built-ins (docs: "Setting CLAUDE_CODE_SUBAGENT_MODEL by itself doesn't change the model the built-in Explore and Plan subagents run on"). Fix: the launcher now passes a session-scoped `--agents` override named `Explore` on `local/default` (C4 below) |
| Live C2 | `claude-local` + `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`, built-in Explore | Explore went local — dragging its **50-tool** prompt: 26,456 input tokens, **146 s** first turn (139 s prefill), then 26 s and 28 s (cache reused). Answer poor (listed files instead of the one match). `_FORCE` rejected as a mechanism |
| Live C3 | `claude-local`, `general-purpose` agent (no model → `CLAUDE_CODE_SUBAGENT_MODEL=local/default`) | routed local as designed and answered `alpha` correctly, but with **54 tools = 31,136 input tokens**: 172 s first turn and **180 s again on turn two** (full re-prefill; cause not isolated, n=1). 360 s wall for a three-line file. This is what moved D5's default to `sonnet` |
| Live C4 | `claude-local`, built-in Explore **overridden by the launcher's `--agents` definition** (3 tools, `local/default`, effort low) | **works**: `query_source: agent:custom:Explore`, routed local with 5,289 input tokens; turn 1 36 s (27 s prefill), turn 2 TTFB **1.95 s** (cache reused); correct answer `sample.txt`. Turn 2 generated 1,683 output tokens at ~22 tok/s (80 s) — the model echoed its Grep results before summarising; the agent prompt's "one final message, three-line summary" rule needs tightening or a lower `max_tokens` on that agent |
| Live E1–E3 | installed plugin (cached snapshot), slash commands | bare `/local-status` and `/delegate-local` → "Unknown command" (plugin commands are namespaced); `/claude-code-agents:local-status` via `claude-local`: 13 s, deterministic table; `/claude-code-agents:delegate-local` via `claude-local`: local-explore 2 turns (35 s, 15 s), **144 and 161 output tokens** after the prompt tightening (was 1,683), correct answer; in a **plain** session with Bash denied, Haiku skipped the preflight and did the task itself with Read — the command and skill now say explicitly to stop rather than substitute |
| T6b | same, parent with default tools | **clean pass**: answer `beta`, 87 s wall; subagent 3 turns (33 s, 34 s, 2.3 s — the third reused the cache), 24,885 local input / 165 output tokens; main 2 turns on the seat |

Wire facts captured by the router: Claude Code sends `thinking:{type:"adaptive",display:"omitted"}`,
`output_config:{effort}`, `max_tokens: 32000`, `context_management: clear_thinking`,
`metadata.user_id`, `cache_control` on system blocks, betas
`claude-code-20250219, interleaved-thinking-2025-05-14, thinking-token-count-2026-05-13,
context-management-2025-06-27, prompt-caching-scope-2026-01-05, mid-conversation-system-2026-04-07,
effort-2025-11-24`; Ollama accepted all of it. The seat request additionally carried
`oauth-2025-04-20` and `extended-cache-ttl-2025-04-11`.

### Sources

- Claude Code docs: model-config, sub-agents, llm-gateway, llm-gateway-connect,
  llm-gateway-protocol, env-vars (code.claude.com, read 2026-09-04)
- anthropics/claude-code issue #38698 (per-agent provider routing; open, 2026-03-25)
- Ollama: docs.ollama.com/api/anthropic-compatibility; `anthropic/anthropic.go` (main);
  releases v0.32.14, v0.32.15, v0.33.0–v0.33.3; ollama/ollama issue #13949
- ggml-org/llama.cpp issue #22384 (hybrid/recurrent checkpoint restore); tools/server/README
- musistudio/claude-code-router: README, `docs/src/content/docs/en/configuration/{routing,profiles,providers,agents/claude-code}.md`, package.json (v3.0.22)
- Qwen/Qwen3.8-27B model card; unsloth.ai/docs/models/qwen3.8; unsloth.ai/docs/basics/api;
  unsloth.ai/docs/basics/claude-code; unsloth.ai/docs/new/studio
- example-mac `models/models.yaml`, the Mac's host record; example-ops `example-app/stacks/litellm/config/config.yaml`
