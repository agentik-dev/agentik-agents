#!/bin/bash
# The deterministic path, as the user would hit it: installed plugin (no --plugin-dir), claude-local, slash commands.
cd "$(dirname "$0")"; LEDGER=~/.local/state/agentroute/requests.jsonl
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("  NO ENVELOPE:", e); sys.exit()
print("  ", {k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}); print("   result:", (d.get("result") or "")[:700].replace("\n","\n           "))
print("   modelUsage:", {m:(v["inputTokens"],v["outputTokens"]) for m,v in (d.get("modelUsage") or {}).items()})
PY
}
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN
echo "=== D1: /local-status via claude-local (installed plugin) ==="; S=$(date +%s)
echo "/claude-code-agents:local-status" | claude-local -p --model haiku --effort low --permission-mode dontAsk --output-format json --setting-sources user > E1.json 2> E1.err; echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show E1.json; grep -vE '^  ok' E1.err | head -c 300
echo; echo "=== D2: /delegate-local via claude-local (installed plugin) ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
echo "/claude-code-agents:delegate-local which file directly inside $PWD contains the word gamma? Name the file only." | claude-local -p --model haiku --effort low --permission-mode dontAsk --output-format json --add-dir "$PWD" --setting-sources user > E2.json 2> E2.err; echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show E2.json; grep -vE '^  ok' E2.err | head -c 300; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"
echo; echo "=== D3: /delegate-local in a PLAIN claude session (must refuse, not fail) ==="; S=$(date +%s)
echo "/claude-code-agents:delegate-local read $PWD/sample.txt and report the first line" | claude -p --model haiku --effort low --permission-mode dontAsk --output-format json --add-dir "$PWD" --setting-sources user > E3.json 2> E3.err; echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show E3.json; head -c 300 E3.err
echo "=== DONE ==="
