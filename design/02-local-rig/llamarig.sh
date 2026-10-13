#!/bin/bash
# rig v0 / backend "llama": llama-server on the GGUF Ollama already has on disk (no download),
# tuned for Claude Code subagents on a hybrid (Gated-DeltaNet) model on Metal:
#   --cache-ram 16384           host-memory prompt cache: keeps several agents' prefixes restorable
#   --ctx-checkpoints 128 --checkpoint-min-step 128   dense recurrent-state checkpoints so a divergence
#                               point (agent text after the shared tool block) has a checkpoint before it
#   -np 2 --kv-unified          two slots sharing one KV pool (Ollama serves this arch single-slot)
#   -c 65536                    total pool; 32k per slot is plenty for ≤15k-token agent turns
#   no --spec-type              MTP is a net loss on Metal in llama.cpp (ggml-org #23752)
#   --reasoning-budget 2048     hard cap on thinking tokens; the router still pins effort low
#   --jinja                     required for tool calls on /v1/messages
set -euo pipefail
BLOB=${LLAMARIG_MODEL:-$HOME/.ollama/models/blobs/sha256-2bb22714289826d7b9e0ba376c3ce47d08bce39abe598745857c44d88c09bdbf}
PORT=${LLAMARIG_PORT:-8081}
LOG=${LLAMARIG_LOG:-$HOME/.local/state/agentroute/llama-server.log}
ALIAS=${LLAMARIG_ALIAS:-qwen3.8-27b-q8}
EXTRA=()
[[ -n "${LLAMARIG_TEMPLATE:-}" ]] && EXTRA+=(--chat-template-file "$LLAMARIG_TEMPLATE")
[[ -n "${LLAMARIG_MMPROJ:-}" ]] && EXTRA+=(--mmproj "$LLAMARIG_MMPROJ")
exec "$(brew --prefix llama.cpp)/bin/llama-server" \
  -m "$BLOB" --alias "$ALIAS" --host 127.0.0.1 --port "$PORT" \
  -ngl all -c 65536 -np 2 --kv-unified \
  --cache-ram 16384 --ctx-checkpoints 128 --checkpoint-min-step 128 \
  --jinja --reasoning-format auto --reasoning-budget 2048 \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --api-key "${LLAMARIG_API_KEY:-local-llama}" --metrics --no-warmup \
  "${EXTRA[@]+"${EXTRA[@]}"}" >> "$LOG" 2>&1
