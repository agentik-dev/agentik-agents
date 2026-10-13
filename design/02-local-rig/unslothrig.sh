#!/bin/bash
# rig v0 / backend "unsloth": Unsloth Studio's API server (llama-server underneath) on Unsloth's own
# Dynamic GGUF, which ships WITH a chat template (Ollama's blob does not). First run downloads
# ~29 GB (UD-Q8_K_XL). Notes from `unsloth run --help` (2026.9.2):
#   --api-only            headless API, no web UI (the Tauri/desktop path)
#   -np 2                 llama-server slots (Unsloth default is 4; each slot gets ctx/N)
#   --speculative-type off   Unsloth "auto" may pick MTP; MTP is a net loss on Metal in llama.cpp
#   --disable-tools       Unsloth's server-side tools (web search, code exec) must not shadow Claude Code's
#   --max-seq-length      runtime context (0 = model default; we cap for two slots)
#   sampling flags        pin Qwen's thinking-mode set; effort comes per request via the router
# The API key is auto-generated and printed once (label = --api-key-name); put it in
# AGENTROUTE_BACKENDS as "auth": "Bearer sk-unsloth-…" (or keep it in ~/.config/agentroute/… later).
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
MODEL=${UNSLOTHRIG_MODEL:-unsloth/Qwen3.8-27B-GGUF}
VARIANT=${UNSLOTHRIG_VARIANT:-UD-Q8_K_XL}
PORT=${UNSLOTHRIG_PORT:-8888}
LOG=${UNSLOTHRIG_LOG:-$HOME/.local/state/agentroute/unsloth.log}
exec unsloth run --model "$MODEL" --gguf-variant "$VARIANT" \
  -H 127.0.0.1 -p "$PORT" --api-only -np 2 --max-seq-length 65536 \
  --speculative-type off --disable-tools --api-key-name agentroute \
  --temperature 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  >> "$LOG" 2>&1
