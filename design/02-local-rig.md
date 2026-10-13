# design/02 — The local rig: several backends behind one router

Status: **RIG v0 IN TRIAL, uncommitted** — researched and stood up 2026-09-04/05 on the Mac.
Follows design/01 (the lane) and answers its open question: Ollama's llama runner cannot
reuse a prompt prefix across agents and serves this model single-slot. This document is
the research sweep, the rig shape we can iterate on, and the measurements that decide.
Evidence in `design/02-local-rig/`.

## 0. TL;DR

The bleeding edge for Qwen 3.8 27B on Apple silicon in September 2026 is not one server,
it is **three ideas**, and each maps onto a backend the router can already select by model
name (`local/<backend>`). **Measured outcome (§3.6d): none of them beats Ollama's own GGUF
runner on the case that recurs in a delegating session** — a new agent shape costs a
~30 s prefill everywhere, and the same agent's next task is cheapest on the runner we
already had (6.5 s). So the starting point keeps that runner as `local/default`, registers
the MLX build as `local/mlx` (2× prose decode, 10 s load), keeps llama-server one command
away for real 2-slot parallelism, and keeps Unsloth installed on demand. The lasting gains
were the rig itself (backends by model name, `localrig`, the ledger's `backend` column) and
the levers the numbers exposed: re-use agent shapes, keep agent prompts small, enforce
output discipline.

1. **Ollama's MLX engine** (`qwen3.8:27b-mxfp8`, 32 GB). Ollama's MLX runner has a
   *compressed prefix trie that shares KV and recurrent-state snapshots across
   conversations* (`x/mlxrunner/prefix_cache.go`) and a **native MTP drafter** for this
   model family (`x/models/qwen3_5/qwen3_5.go` loads the `mtp.*` head; `x/mlxrunner/mtp.go`).
   Those are exactly the two things the GGUF runner lacks on this architecture, and MTP
   is the one place MLX beats llama.cpp on Metal (llama.cpp's MTP is a measured net loss
   on Metal, ggml-org #23752; MTPLX shows 1.6–2.2× with MLX-native MTP). Cost: one
   32 GB pull, no new software, and the MLX runner is still strictly sequential
   (continuous batching PR #17317 open as of 2026-08-14).
2. **llama-server** (brew `llama.cpp` 0.4.0, build 10809) on **the GGUF Ollama already
   has on disk** (no download): `-np 2 --kv-unified` for two real slots,
   `--cache-ram 16384` host-memory prompt cache, `--ctx-checkpoints 128
   --checkpoint-min-step 128` so a hybrid model has a checkpoint before the point where
   one agent's system text diverges from another's, `--reasoning-budget` as a hard thinking
   cap, no MTP. The Ollama blob ships **no chat template** (Ollama renders in Go), so
   `--chat-template-file` with Qwen's published `chat_template.jinja` is mandatory for
   tool calls.
3. **Unsloth** (`unsloth run` / `unsloth start`, Desktop 2026-08-11+): on a Mac it is a
   Python 3.13 venv under `~/.unsloth/studio` wrapping a prebuilt llama-server (GGUF) with
   an Anthropic `/v1/messages` endpoint, API keys, a request monitor, Dynamic quants, and
   `--reasoning-effort` / `--disable-tools`. Its `unsloth start claude` auto-configures
   Claude Code end to end, which we do **not** want (the router owns that); as a backend it
   is llama-server with conveniences.

Also on the radar, not adopted: **Rapid-MLX** (brew, OpenAI+Anthropic, "radix + DeltaNet
RNN snapshots" cache, 0.08 s cached TTFT claim, 4-bit only for 27B), **MTPLX** (Mac app +
CLI, MLX-native MTP, SSD-persisted session cache, Anthropic API, attribution clause),
**oMLX** (SSD KV cache "fixes local coding agents"). All three are MLX servers by small
teams; the Ollama MLX engine gets us the same two properties inside software example-mac
already declares.

## 1. Research sweep (what changed since design/01, with sources)

| Finding | Source | Consequence |
|---|---|---|
| Ollama's MLX runner keeps a **compressed prefix trie** of per-layer snapshots "shared across conversations", with "prefix-aware eviction [that] keeps shared system prompts hot"; 8 GiB paged-out budget; on by default, no knob | `x/mlxrunner/prefix_cache.go`, Ollama MLX preview blog (2026-03-30) | cross-agent first turns should restore instead of re-prefill on the MLX path |
| Ollama's MLX Qwen 3.5-family model implements `SelfDraft` and loads the `mtp.*` head when present; `speculate.go` picks an MTP drafter with a learned depth controller | `x/models/qwen3_5/qwen3_5.go`, `x/mlxrunner/{mtp,speculate,speculate_depth}.go` | MTP speed-up on Apple silicon without llama.cpp's Metal penalty |
| Ollama MLX runner processes requests **serially**; `OLLAMA_NUM_PARALLEL` has no effect on it (issue 2026-07-21; continuous-batching PR #17317 open) | `x/mlxrunner/runner.go`, ollama issues | parallel agents still need llama-server |
| **MTP in llama.cpp is a net loss on Metal**: −11 % at 100 % acceptance, −28 % at n_max=6 (M1 Max, Qwen3.5-9B-MTP); "draft evaluation overhead on Metal exceeds the speculative gain" | ggml-org/llama.cpp #23752 (2026-05-27) | never pass `--spec-type draft-mtp` to llama-server here; Ollama's `-mtp-` GGUF tag may deserve the same A/B (D2 below) |
| llama-server hybrid-model cache: checkpoints are created at `--checkpoint-min-step` intervals (default 8192); "when no checkpoint clears the position threshold the server sets n_past to 0 and erases every checkpoint"; `--cache-reuse` "doesn't work with models that use recurrent state" | llama.cpp #21831, #22746, discussion #22354 | dense checkpoints (`--checkpoint-min-step 128 --ctx-checkpoints 128`) are the lever; `--cache-reuse` is not |
| A working Claude Code + llama-server recipe for a 27B hybrid: `-c 170000 -ngl 99 --flash-attn on -ctk q4_0 -ctv q4_0 --cache-ram 15000 --ctx-checkpoints 128 --checkpoint-min-step 128` plus `CLAUDE_CODE_ATTRIBUTION_HEADER=0`; result "restored context checkpoint, prompt eval time = 511 ms / 212 tokens" | mykolaaleksandrov.dev, 2026-06 | our flag set mirrors it; we keep KV at f16 (Qwen is resilient to KV quant but Metal pays 5–10 % for it, and memory is not the constraint here) |
| The much-indexed "host-memory prompt caching tutorial" (discussion #20574) is flagged by maintainers' commenters as AI-generated with non-existent flags | llama.cpp #20574 comments (2026-06/07) | ignored; flags verified against `llama-server --help` on this Mac |
| MLX vs llama.cpp on Apple silicon: MLX leads 20–87 % under ~14B; "the advantage collapses at 27B+ where memory bandwidth saturates"; at 8-bit "the advantage disappears" | community benchmarks (willitrunai, orcarouter, antekapetanovic M4 Max: MLX 84–108 vs llama.cpp 65–70 vs Ollama 40–46 tok/s on a 35B-A3B MoE) | for a dense 27B at 8-bit expect parity on raw decode; the MLX win here is MTP + the prefix cache, not bandwidth |
| Unsloth Dynamic v3 quants: `UD-Q8_K_XL` 29.3 GB, `UD-Q4_K_XL` 16.4 GB (Unsloth's "quality standard"); no MLX artifact from Unsloth for Qwen 3.8 (repos: GGUF, NVFP4, FP8, bnb-4bit) | huggingface.co/unsloth | if a 4-bit is ever needed for memory, UD-Q4_K_XL on llama-server is the pick; Unsloth's Mac API path is GGUF |
| Unsloth changelog Jul–Sep 2026: Desktop (08-11) with Claude Code/Codex connect, Qwen 3.8 (08-14), LAN access + auto-compaction (08-20), MTP on by default for Flash-Next/GLM (09-02) | unsloth.ai/docs/new/changelog | Unsloth is moving fast on exactly this use case; re-check monthly |
| Ollama 0.33.x: honors GGUF default params (0.33.3), MLX structured output, Claude Desktop gateway; brew is at 0.33.2 | ollama releases | nothing blocking; 0.33.3 when brew has it |

## 2. Rig v0 — the shape

```
claude-local ─▶ agentroute :8787 ─▶ claude-*            → api.anthropic.com (seat)
                                   ─▶ local/default     → Ollama :11434  qwen3.8:27b-mtp-q8_0 (GGUF runner)   [today's lane]
                                   ─▶ local/mlx         → Ollama :11434  qwen3.8:27b-mxfp8    (MLX runner: prefix trie + MTP)
                                   ─▶ local/llama       → llama-server :8081  same q8 GGUF blob (-np 2, cache-ram)
                                   ─▶ local/unsloth     → unsloth run :8888   (llama-server + Anthropic API + keys)
```

`~/.config/agentroute/backends.json` (written by `localrig up <name>`; `AGENTROUTE_BACKENDS`
overrides it) declares the backends; `localrig default <name>` copies one into the
`default` key, which is what `local/default` — every `local-*` agent and the launcher's
Explore override — resolves to. An agent picks a specific backend with `model:
local/<name>` (or `local/<name>/<model>`) and nothing else changes. `agentroute --check`
probes every backend (Ollama version and tag list, or `/v1/models` for Anthropic-format
servers); only the default gates a session, the others warn. The ledger gains a `backend`
column so the same agent run on two backends is comparable row by row.
Memory: q8 GGUF 31.5 GB + mxfp8 ~32 GB + llama-server 31.5 GB (mmap of the same blob, so
mostly shared page cache) + qwen3.6 38 GB for the chat server. Two of the three 27B copies can be
hot at once inside the 107 GiB Metal budget; all three is the eviction zone, so the trial
runs them one pair at a time.

### 2.1 Backend flag sets (as run)

- **llama** — `design/02-local-rig/llamarig.sh`: `llama-server -m <ollama q8 blob> --alias
  qwen3.8-27b-q8 -ngl all -c 65536 -np 2 --kv-unified --cache-ram 16384 --ctx-checkpoints
  128 --checkpoint-min-step 128 --jinja --reasoning-format auto --reasoning-budget 2048
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --api-key … --metrics --no-warmup
  --chat-template-file chat_template.jinja` (Qwen's published template, which handles
  `tools`, `enable_thinking`, `reasoning_effort`, `preserve_thinking`). Loads in 21 s from
  page cache; 31.5 GB RSS; tool call over `/v1/messages` in 5 s; prefill 194 tok/s, decode
  15.5 tok/s (no MTP).
- **mlx** — `ollama pull qwen3.8:27b-mxfp8`; served by the existing Ollama with no flag
  changes; `think` level from `output_config.effort` as today.
- **unsloth** — `unsloth run --model <gguf> -H 127.0.0.1 -p 8888 --disable-tools
  --reasoning-effort low …` (flags forwarded to its llama-server); backend auth
  `Bearer sk-unsloth-…` via `AGENTROUTE_BACKENDS`.

### 2.2 Two things every non-Ollama backend needs from the router (found 2026-09-04)

1. **A chat template.** Ollama's GGUF blobs carry no `tokenizer.chat_template` (Ollama
   renders prompts in Go, `model/renderers/qwen35.go`), so llama-server needs
   `--chat-template-file` with Qwen's published template (`design/02-local-rig/
   qwen3.8-chat_template.jinja`, 8.9 KB; handles `tools`, `enable_thinking`,
   `reasoning_effort`, `preserve_thinking`). Without it tool calls do not parse.
2. **Non-leading `role: system` messages folded away.** Claude Code appends
   `role: system` messages mid-conversation (the SessionStart hook context, the
   `<total_tokens>` reminder). Ollama ≥ 0.32.15 normalizes them; Qwen's template raises
   `System message must be at the beginning` and llama-server returns 500, which Claude
   Code retries in a loop. Isolated by reproduction: system-as-array with `cache_control`,
   Claude-style tool schemas (`$schema`, `additionalProperties`), `thinking: adaptive`,
   `metadata`, `context_management`, and tool_use/tool_result turns all pass; only the
   non-leading system message fails. `agentroute` 0.2.1 adds a per-backend
   `"fold_system": true` that appends such messages' text to the top-level `system`
   array (position lost, content kept; the reminder is still stripped, never folded).
   Ledger column `folded_system`.

## 3. Measurements

Same four tests per backend, same two 3-tool agent definitions (A and B differ only in
system text), same task, Claude Code 2.1.261 non-bare through `agentroute`, prompt ≈ 7.2k tokens on
llama-server and ≈ 6.1k on the Ollama runners (the same conversation tokenises differently
per backend and per template; quote it per backend, never as one number), of which ≈ 6.65k
is the shared prefix on llama-server (tool schemas + Claude Code's subagent
boilerplate). Logs: `design/02-local-rig/rig-*.log`.

### 3.1 Baseline — Ollama GGUF runner, `qwen3.8:27b-mtp-q8_0` (design/01 lane, 2026-09-04)

| Test | Result |
|---|---|
| new agent, turn 1 | full prefill every time: 27–49 s (5.3–6.2k tokens) |
| same agent, turn 2 | cached: 0.36–3.7 s |
| **different agent after another** | **full re-prefill** (single slot, no restorable checkpoint at the divergence point) |
| two agents at once | serialised (`n_seq_max = 1`) |
| decode | 11 tok/s prose, ~25 tok/s JSON/tool calls (MTP on the GGUF runner) |

> ⚠ **§3.2 through §3.4 are SUPERSEDED by §3.6d.** They were measured on a
> *late-divergence* prompt shape, where two agents shared everything but the last slice.
> Under real delegation (agents differing from the first token) the cross-agent restores
> reported below do not occur: see §3.6c (llama-server re-prefilled a new agent in full)
> and §3.6b (the MLX trie never converged). The per-backend decode rates and load times
> here still hold. Kept because the reversal is the finding.

### 3.2 `local/llama` — llama-server 0.4.0 on the same q8 blob (2026-09-05)

| Test | Result |
|---|---|
| L1 agent A, turn 1 | full prefill 7,169 tokens in 33.3 s (215 tok/s); turn 2: 28 new tokens, 0.34 s |
| **L2 agent B right after A** | **restored 6,653 cached tokens; prefilled only 516 new (2.6 s); whole first turn 10 s** |
| L3 agent A again after B | restored again: 516 new tokens, 2.5 s; both agents' prefixes live in the host cache |
| **L4 two agents at once** | **real parallelism**: slot 0 hit the cache (4 new tokens, 0.14 s) while slot 1 did a full 34 s prefill; both done in 47 s wall, correct answers |
| decode | 15.3–15.7 tok/s on every turn (no MTP; the dense 8-bit bandwidth floor) |
| correctness | 8/8 turns answered right (`gamma`, `beta`, `alpha`, `gamma`, `alpha`) |

What made the difference: `--cache-ram 16384` (host-memory copies of finished slots'
state) together with `--ctx-checkpoints 128 --checkpoint-min-step 128` (a recurrent-state
checkpoint every 128 tokens, so one exists just before the point where agent B's system
text diverges from agent A's). Cross-agent first turns fell from 27–49 s to ~10 s, and
that is the number that governs how a 10-agent session feels.

Costs: 32 GiB RSS for the second copy of the weights (mmap of Ollama's blob, page cache
shared, Metal allocation not), ~21 s to load, no MTP so prose is 15 tok/s rather than
Ollama's 11–25, and the two router-side shims (template file, `fold_system`).

### 3.3 `local/mlx` — Ollama MLX runner, `qwen3.8:27b-mxfp8` (2026-09-05)

| Test | Result |
|---|---|
| cold load | 10.1 s (vs 15–26 s for the GGUF builds); 34.1 GiB peak; `think:false` over native `/api/chat` returns clean content (the chat server gate passes) |
| prose throughput | **24.2 tok/s** with MTP (acceptance 0.70 on prose, 0.84–0.95 on tool calls); vs 11 on the GGUF runner and 15.5 on llama-server |
| M1 agent A, turn 1 | `cache miss total=7029 matched=0`: full prefill ~31 s (~225 tok/s); turn 2 `cache hit … left=28`: 1.2 s |
| M2 agent B after A | `cache miss total=7029 matched=7017 cached=0`: the trie **matched** 7,017 shared tokens but held no recurrent-state snapshot at that position (snapshots live only at node ends), so B paid a full 36 s prefill **once** — and its arrival split the trie at token 7,017 |
| **M3 agent A after B** | **`cache hit matched=7017 cached=7017 left=12`: 3.3 s first turn** (0.44 s to first byte) |
| **M4 two agents at once** | serialised by the runner but both hit the branch point: 3.7 s + 6.7 s, **9 s wall for both**; turns two 1.9–3.9 s |
| correctness | 8/8 (`gamma`, `beta`, `alpha`, `gamma`, `alpha`) |

The mechanism, from the runner's own log: the prefix trie needs a node boundary at the
point where two prompts diverge before it can restore there. The first distinct agent
shape creates that boundary at the end of the shared Claude Code prefix (tool schemas +
subagent boilerplate ≈ 7,017 tokens); every later agent shape sharing it restores in
under half a second. So the MLX path is "pay one extra full prefill per session, then
every new agent starts warm", against llama-server's "every new agent pays ~2.6 s".

### 3.4 Side by side

| | Ollama GGUF runner (today) | llama-server, tuned | **Ollama MLX runner** |
|---|---|---|---|
| new agent, first turn | 27–49 s, always | ~10 s (restores to a 128-token checkpoint) | 31–36 s the first two shapes, then **~3 s** |
| same agent, next turn | 0.4–3.7 s | 0.3 s | 0.9–1.2 s |
| two agents at once | serialised | **parallel** (47 s for a cold + a warm) | serialised, but both warm: **9 s** |
| decode, prose | 11 tok/s | 15.5 tok/s | **24 tok/s** (MTP) |
| decode, tool calls / JSON | ~25 tok/s | 15.5 tok/s | ~25–30 tok/s |
| cold load | 15–26 s | 21 s | **10 s** |
| resident | 31.5 GB | 32 GiB | 34 GiB peak |
| extra software / shims | none | brew llama.cpp; template file; `fold_system` | **none** (Ollama, one pull) |
| the chat server can share it | yes (mac-chat-deep) | no | yes (`think:false` gate passed) |

**Recommendation (D1) — SUPERSEDED by §3.6d, kept for the record:** make
`qwen3.8:27b-mxfp8` on Ollama's MLX runner the lane's `local/default`. It wins on every axis that a long delegating session feels — warm
first turns after the first two agents, 2× the prose decode, 10 s reload — and it costs
nothing example-mac does not already declare. Keep llama-server registered as `local/llama`
for the one thing MLX cannot do yet (two agents truly at once) and drop it the day
Ollama's MLX continuous batching lands. Retire the q8 GGUF once the chat server's deep route has
been moved to mxfp8 (D3), so the box holds one 27B copy again.

### 3.5 `local/unsloth` — Unsloth Studio API on `unsloth/Qwen3.8-27B-GGUF:UD-Q8_K_XL`

Install: `curl -fsSL https://unsloth.ai/install.sh | sh` → 2.4 GB under `~/.unsloth/studio`
(Python 3.13 venv via uv, prebuilt llama-server, MLX deps), a shim in `~/.local/bin`, an
app bundle in `~/Applications`, **no shell rc changes** (verified by diff). `unsloth run`
downloaded the 29 GB UD-Q8_K_XL to the Hugging Face cache and served it on `:8888` with
`--api-only -np 2 --max-seq-length 65536 --speculative-type off --disable-tools`; the
API key is printed once at startup and `/v1/models` answers 401 without it (which is why
the first trial wrapper mis-registered it — the key had not been printed yet). `/v1/models`
also lists a stale `mlx-community/Qwen3-VL-32B-Instruct-8bit` from the abandoned 2026-08
download in the HF cache (already an example-mac cleanup candidate).

⚠ The first `rig-unsloth.sh` run's U1–U4 rows are **not Unsloth numbers**: with no
`unsloth` entry in `backends.json`, `local/unsloth` fell through to the default backend
(the ledger's `model_out` says `qwen3.8:27b-mtp-q8_0`). They are kept in the sidecar as an
accidental second sample of the Ollama GGUF runner on the late-divergence shape. Unsloth's
own numbers come from §3.6.

### 3.6 Honest rerun — real delegation, early divergence (2026-09-05)

The A/B trials above varied only a late slice of the prompt (the `--agents` roster and the
final user line; the main thread answered directly). This rerun has a **seat main (Haiku)
really delegate** to two local subagents whose system prompts differ from the first
token, same three tools, A → B → A, on each backend, selected by agent model name alone
(`backends.json`, no env). Rows are the router ledger's local rows in order.

Prompt per subagent turn ≈ 5.3k tokens as the ledger counts it on the Ollama runners and
≈ 6.3k on llama-server (see the note in §3.1 about per-backend tokenisation); the shared
prefix (tool schemas + Claude Code's subagent boilerplate) is **1,633 tokens**, and everything after it is agent-specific.
Times are the router's `wall_s` for the subagent's request; "ttfb" is first body byte.

| Backend | A, turn 1 | A, turn 2 | **B, turn 1** (new agent) | B, turn 2 | **A again, turn 1** (same agent, new task) | A again, turn 2 | answers |
|---|---|---|---|---|---|---|---|
| Ollama GGUF runner (`default`) | 42.9 s (ttfb 38.9) | 1.0 s | **32.6 s** (full) | 1.3 s | **6.5 s** (ttfb 2.5: restore point kept) | 0.9 s | correct |
| Ollama MLX runner (`mlx`) | 37.7 s (ttfb 34.3) | 6.4 s | **28.6 s** (`matched=1633 cached=0` → full; B's arrival creates the branch at 1,633) | 2.7 s | **22.0 s** (`matched=6123 cached=1633 left=4502`: restored only to the branch point) | 2.5 s | correct |
| Unsloth (`unsloth`, llama-server defaults) | 44.2 s | 15.5 s | **37.0 s** | 5.6 s | **26.6 s** | 1.2 s | correct |
| llama-server tuned (`llama`) | not run — `localrig up llama` died on a `set -u` bug (`$!` after a subshell) and the leg fell through to the default; fixed, re-running (§3.6b) | | | | | | |

What this changes versus §3.4:

- **A brand-new agent shape costs a full prefill on every backend** (28–37 s here). The
  1,633-token shared prefix is too small to matter; the agent text is the bulk. Only a
  positional checkpoint just before the divergence (llama-server's 128-token
  `--checkpoint-min-step`) can cut that, and the tuned llama-server leg is the one that
  was not measured — it is now the deciding measurement.
- **Same agent, new task** separates the runners. Ollama 0.33's GGUF runner kept a restore
  point from A's earlier turn and re-prefilled ~0.5k tokens (6.5 s). The MLX trie stores
  whole-state snapshots only at node ends, so A' could restore only to the branch point
  B's arrival had created (1,633) and re-prefilled 4,502 tokens (22 s). A' itself creates
  a branch at ~6,133, so a *third* call of A should restore fully — that convergence is
  what the 4-delegation re-run (§3.6b) tests.
- Unsloth's server is llama-server without the checkpoint/cache tuning (Unsloth exposes
  `-np` and sampling, not `--checkpoint-min-step`), so it behaves like an untuned
  llama-server: no cross-agent restore, and its turn 2 was slowest (5.6–15.5 s; decode
  ~14 tok/s on UD-Q8_K_XL). Its value is the packaging (Dynamic quants, Anthropic API,
  keys, monitor), not the cache.
- MTP acceptance on the MLX runner stayed high on these agent turns (0.66–1.00), so its
  decode advantage (24 vs 15 tok/s) holds; it just does not fix prefill.

### 3.6b Re-run: MLX with a fourth delegation; the llama-server leg (2026-09-05)

**MLX, four delegations (A, B, A', A'')**, fresh runner (model had been unloaded):

| A₁ | A₂ | B₁ | B₂ | A′₁ | A′₂ | A″₁ | A″₂ |
|---|---|---|---|---|---|---|---|
| 34.4 s (`matched=0`) | 0.8 s | 28.4 s (`matched=1633 cached=0`) | 2.8 s | 22.4 s (`matched=6124 cached=1633 left=4505`) | 2.6 s | **21.8 s (`matched=6123 cached=1633 left=4507`)** | 6.4 s |

**No convergence.** The trie matched 6,123 of A″'s tokens but could restore only to 1,633,
exactly as for A′: A′'s arrival did not leave a restorable snapshot at the ~6,124
boundary. So on the MLX runner, "same agent, new task" costs a ~4.5k-token re-prefill
(~19 s) **every time** for this prompt shape; the only warm case is the literal
continuation of one agent's own conversation (turn 2+: 0.8–6.4 s). That is worse than
Ollama's own GGUF runner (6.5 s, §3.6) and reverses §3.4's conclusion, which was drawn from
a late-divergence shape where the branch point happened to sit at the end of the prompt.
All answers correct (`gamma, beta, alpha, 4`).

**llama-server tuned**: the leg ran, but the Haiku orchestrator delegated once, then
tried to do the task itself and stopped ("Read tool and Bash are denied in don't-ask").
The three rows it produced are the useful part: A₁ 35.6 s (full prefill, 6,280 tokens at
234 tok/s), then A₂ **`in 165, cache_read 6411`** and A₃ `in 166, cache_read 7229`, i.e.
llama-server restored the agent's state and prefilled only the new tokens (1.1 s each).
Cross-agent and same-agent-new-task on this backend are measured in §3.6c with a Sonnet
orchestrator told to use only the Agent tool.

### 3.6c Tuned llama-server, honest shape, Sonnet orchestrator (2026-09-05)

| A₁ | A₂ | B₁ | B₂ | A′₁ | A′₂ | A″₁ | A″₂ |
|---|---|---|---|---|---|---|---|
| 33.3 s (6,278 tokens, 234 tok/s, `cr 0`) | 6.3 s (`in 28, cr 6376`) | **36.2 s (full, `cr 0`)** | 5.3 s | **9.0 s (`in 516, cr 5762`)** | 1.3 s | 9.2 s (`in 518, cr 5762`) | 82.7 s (1,255 output tokens: the bare probe prompt rambled on "how many lines") |

Even with a checkpoint every 128 tokens, a **new agent shape re-prefilled in full**: the
1,633-token shared prefix did not restore. **Same agent, new task** restored to the last
512-token batch boundary (5,762 of 6,278) and prefilled 516 tokens in 2.4 s — every time,
no "pay once" penalty. Answers correct (`gamma, beta, alpha, 4 lines`).

### 3.6d The honest table

Real delegation, early divergence, Claude Code 2.1.261, one Mac. "New agent" = first call
of a differently-prompted agent; "same agent, new task" = a later call of an agent already
seen this session; "continue" = that agent's own next turn.

| Backend | new agent | same agent, new task | continue | decode (prose / tool calls) | parallel | load | extra software |
|---|---|---|---|---|---|---|---|
| **Ollama GGUF runner** `qwen3.8:27b-mtp-q8_0` (today's default) | 32.6 s | **6.5 s** | 0.9–1.3 s | 11 / ~25 tok/s | no | 15–25 s | none |
| Ollama MLX runner `qwen3.8:27b-mxfp8` | 28.4 s | 22 s, every time | 0.8–6.4 s | **24 / ~28 tok/s** | no | **10 s** | none (one pull) |
| llama-server tuned, same q8 blob | 36.2 s | 9.0 s | 1.3–6.3 s | 15.5 / 15.5 tok/s | **2 slots** | 21 s | brew llama.cpp, template, `fold_system` |
| Unsloth Studio API, UD-Q8_K_XL | 37.0 s | 26.6 s | 1.2–15.5 s | ~14 tok/s | 2 slots (-np 2) | ~25 s | 2.4 GB venv + 30 GB cache, key |

**What actually governs latency here is prefill bandwidth, not caching.** A new agent
shape is ~6.3k tokens at 210–235 tok/s on this GPU, i.e. ~30 s, on every backend; no
hybrid-model cache implementation we could find restores at an arbitrary early divergence
(llama.cpp's checkpoints resolve to 512-token batch boundaries in practice, and Ollama's
MLX trie only to existing branch points). What caches *can* do is make the second call of
the same agent cheap, and there Ollama's own GGUF runner (0.33's restore points) is the
best of the four at 6.5 s, with tuned llama-server close behind at 9 s.

**Decision (D1, revised from §3.4): keep the Ollama GGUF runner as `local/default`.** It
wins the case that recurs in a delegating session (same agent, new task), the chat server already
shares it, and it needs nothing new. §3.4's recommendation of mxfp8 was drawn from a
late-divergence shape and is withdrawn; the MLX runner stays registered as `local/mlx`
for what it is genuinely better at — long prose output (24 vs 11 tok/s) and fast reload —
and becomes the default the day its trie snapshots at split points or Ollama ships MLX
continuous batching. llama-server stays one `localrig up llama` away for a parallel burst.
Unsloth stays installed as `local/unsloth` on demand; its cache behaviour is untuned
llama-server and its value is packaging.

**The real levers, in order:** (1) fewer *distinct* agent shapes per session and
re-using them, since the second call is 5× cheaper than the first; (2) prompt size per
agent (tool count, agent text — ≈ 6.3k tokens today of which only 1.6k is shared);
(3) output discipline (A″₂'s 82 s was 1,255 tokens of rambling from a bare probe prompt;
the shipped `local-*` agents carry the strict final-message rule for exactly this);
(4) only then the backend.

## 3.7 How to iterate on this (the knobs, what to measure, how often)

The ledger (`~/.local/state/agentroute/requests.jsonl`) is the instrument: per request it
has `backend`, `model_out`, `agent_id`, `n_tools`, `input_tokens`, `cache_read_input_tokens`
(llama-server reports it; Ollama does not), `ttfb_s` (first body byte), `wall_s`,
`effort_out`, `stripped_reminders`, `folded_system`. `claude-costs` sums the lane.

| Knob | Where | What to watch |
|---|---|---|
| which backend is `local/default` | `localrig default mlx|llama|unsloth` | first-turn `ttfb_s` of a *new* agent shape; decode tok/s from the backend log |
| llama-server checkpoint density | `LOCALRIG_LLAMA_*` env before `localrig up llama` (`--checkpoint-min-step`, `--ctx-checkpoints`, `--cache-ram`) | `restored context checkpoint` vs `forcing full` in `llama-server.log`; RSS |
| llama-server slots | `LOCALRIG_LLAMA_SLOTS` (2 today) | two agents at once: both `wall_s` vs the sum; KV memory per slot |
| thinking cap | router `AGENTROUTE_LOCAL_MAX_EFFORT` (medium) and llama-server `--reasoning-budget` (2048) | `output_tokens` on turns that should be short |
| Ollama keep-alive | plist `OLLAMA_KEEP_ALIVE` (30m) | cold-load seconds on the first local row after idle |
| MLX vs GGUF for the chat server too | example-ops LiteLLM `mac-chat-deep` → `ollama_chat/qwen3.8:27b-mxfp8` | the chat server's `think:true` route wall time; then retire the q8 GGUF (one 27B copy) |
| Unsloth Dynamic quant | `LOCALRIG_UNSLOTH_VARIANT` (UD-Q8_K_XL; UD-Q4_K_XL is 16 GB) | correctness on the design/01 tasks first, speed second |
| MTP on the GGUF runner | Ollama tag `qwen3.8:27b-q8_0` (no `-mtp-`) vs `-mtp-q8_0` | prose tok/s; llama.cpp's own MTP loses on Metal, Ollama's runner has never been A/B'd here |

Cadence: re-run `design/02-local-rig/e2e-rig-honest.sh` after any of: an Ollama release
(MLX continuous batching, PR #17317, is the one to watch — it would make `mlx` the only
backend needed), a llama.cpp release that touches hybrid checkpoints, a Qwen 3.8 MoE or
Dynamic-quant drop (design/01 §6.1 gates), or a Claude Code release that changes the
subagent prompt shape (watch `input_tokens` for a 3-tool agent; ≈5.3k today).

## 4. Decisions queued for the owner

- **D1 which backend becomes `local/default` — DECIDED 2026-09-05 (§3.6d): the Ollama GGUF
  runner stays.** `local/mlx` registered, `local/llama` and `local/unsloth` on demand.
  Resting state after the trials: llama-server and Unsloth stopped, `backends.json` = {mlx}.
- **D2 Ollama's `-mtp-` GGUF tag vs the plain `q8_0` tag** on Metal: llama.cpp's MTP loses
  on Metal; Ollama's runner is llama.cpp's. Ollama measured 25 tok/s on structured output
  with MTP, so its implementation may differ, but it has never been A/B'd here.
- **D3 the chat server**: mxfp8 did not win the lane, so there is no forced move; the q8 GGUF stays
  the shared copy. Optional: move `mac-chat-deep` to mxfp8 for the chat server's *chat* decode speed
  (24 vs 11 tok/s prose) and then hold mxfp8 resident instead of q8 — an example-ops change,
  and it would flip the lane's default with it (one 27B copy is the constraint). Note this
  supersedes the sentence in §3.4 about retiring the q8 GGUF: under D1 the q8 IS the lane's
  default, so it cannot be retired while the lane points at it.
- **D4 Unsloth**: keep as a declared optional backend (2.4 GB venv + 30 GB cache), or
  remove the four paths listed in example-mac HANDOFF. Recommendation: remove the 30 GB model
  cache now (it re-downloads in ~12 min if wanted), keep the venv for a month of watching
  its changelog.
- **D5 example-mac**: Brewfile gains `llama.cpp`; the rig's LaunchAgents (if any) and the
  Unsloth install get declared or removed; `models.yaml` gains the mxfp8 entry.
