#!/bin/bash
cd "$(dirname "$0")"
echo "=== keep-alive in server config ==="; grep -oE 'OLLAMA_KEEP_ALIVE:[^ ]*' ~/Library/Logs/ollama.log | tail -1
echo "=== Gate A: native /api/chat think:false on q8 (the chat server path) ==="
S=$(date +%s)
curl -s --max-time 300 http://127.0.0.1:11434/api/chat -d '{"model":"qwen3.8:27b-mtp-q8_0","stream":false,"think":false,"messages":[{"role":"user","content":"In one sentence, what is a NAS?"}]}' \
 | python3 -c 'import sys,json; d=json.load(sys.stdin); m=d["message"]; print("content_len", len(m.get("content","")), "thinking_len", len(m.get("thinking","")), "| eval", d.get("eval_count"), "tok in", round(d.get("eval_duration",0)/1e9,1), "s | load", round(d.get("load_duration",0)/1e9,1), "s"); print("content:", m.get("content","")[:160])'
echo "gate A wall=$(( $(date +%s) - S ))s"
echo "=== Gate B: non-bare Claude Code, NO shim, effort low, Read/Glob/Grep (T4 shape) ==="
export ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_API_KEY=ollama ANTHROPIC_AUTH_TOKEN=ollama CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 CLAUDE_CODE_ATTRIBUTION_HEADER=0; unset CLAUDE_CODE_OAUTH_TOKEN
S=$(date +%s)
echo "Use Glob to list the files in $PWD, then Read sample.txt and reply with the first line only." | \
claude -p --model qwen3.8:27b-mtp-q8_0 --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > tB.json 2> tB.err
echo "exit=$? wall=$(( $(date +%s) - S ))s"
python3 - <<'PY'
import json
try: d=json.load(open("tB.json"))
except Exception as e: print("NO ENVELOPE", e); raise SystemExit
print({k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}); print("result:", repr((d.get("result") or "")[:160]))
u=d.get("usage") or {}; print("usage in/out:", u.get("input_tokens"), u.get("output_tokens"))
PY
echo "--- stderr ---"; head -c 400 tB.err; echo
echo "=== cache behaviour per turn (ollama log since restart) ==="
grep -E 'task.n_tokens|forcing full|prompt eval time|GIN.*(v1/messages|api/chat)' ~/Library/Logs/ollama.log | grep -A3 -E 'task.n_tokens' | grep -vE '^--$' | tail -16 | cut -c1-150
echo "=== DONE ==="
