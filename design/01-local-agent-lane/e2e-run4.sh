#!/bin/bash
cd "$(dirname "$0")"
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("NO ENVELOPE:", e); sys.exit()
print({k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms","duration_api_ms")})
print("result:", repr((d.get("result") or "")[:200]))
print("usage:", {k:d["usage"].get(k) for k in ("input_tokens","output_tokens","cache_read_input_tokens","cache_creation_input_tokens")} if d.get("usage") else None)
print("modelUsage:", json.dumps(d.get("modelUsage"))[:600])
print("denials:", d.get("permission_denials"))
PY
}
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=ollama ANTHROPIC_AUTH_TOKEN=ollama CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 CLAUDE_CODE_ATTRIBUTION_HEADER=0; unset CLAUDE_CODE_OAUTH_TOKEN
echo "=== T4 (rerun, shim on): NON-bare, Read/Glob/Grep, effort low ==="
S=$(date +%s)
echo "Use Glob to list the files in $PWD, then Read sample.txt and reply with the first line only." | \
claude -p --model qwen3.8:27b-mtp-q8_0 --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > t4.json 2> t4.err
echo "exit=$? wall=$(( $(date +%s) - S ))s"; show t4.json; echo "--- stderr ---"; head -c 600 t4.err; echo
echo "=== T6: integration — seat main (haiku) spawns local subagent ==="
./run6.sh
echo "=== DONE ==="
