#!/bin/bash
cd "$(dirname "$0")"
until ! pgrep -f live2.sh >/dev/null; do sleep 3; done
LEDGER=~/.local/state/agentroute/requests.jsonl; BIN=~/src/agentik-agents/bin; SP=..
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("  NO ENVELOPE:", e); sys.exit()
print("  ", {k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}, "result:", repr((d.get("result") or "")[:120]))
print("   modelUsage:", {m:(v["inputTokens"],v["outputTokens"]) for m,v in (d.get("modelUsage") or {}).items()})
PY
}
echo "=== C4: launcher's session-scoped Explore override -> local ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
( unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN
  echo "Use the Explore subagent to find which file directly inside $PWD contains the word gamma. Reply with the file name only." | \
  "$BIN/claude-local" -p --model haiku --effort low --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > C4.json 2> C4.err )
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show C4.json; grep -vE '^  ok|unrecognized_model' C4.err | head -c 300; /usr/bin/python3 "$SP/ledger-tail.py" "$LEDGER" "$M"
echo "=== DONE ==="
