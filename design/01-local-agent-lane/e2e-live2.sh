#!/bin/bash
cd "$(dirname "$0")"
LEDGER=~/.local/state/agentroute/requests.jsonl; BIN=~/src/agentik-agents/bin; SP=..
mark() { wc -l < "$LEDGER"; }
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("  NO ENVELOPE:", e); sys.exit()
print("  ", {k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}, "result:", repr((d.get("result") or "")[:120]))
print("   modelUsage:", {m:(v["inputTokens"],v["outputTokens"]) for m,v in (d.get("modelUsage") or {}).items()})
PY
}
run() { # label, extra-env (string), prompt, claude args...
  local label=$1 extra=$2 prompt=$3; shift 3
  echo; echo "=== $label ==="; local M=$(mark) S=$(date +%s)
  ( unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN; export $extra
    echo "$prompt" | "$BIN/claude-local" -p --model haiku --effort low --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user "$@" > "$label.json" 2> "$label.err" )
  echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show "$label.json"; grep -vE '^  ok|unrecognized_model' "$label.err" | head -c 300; /usr/bin/python3 "$SP/ledger-tail.py" "$LEDGER" "$M"
}
run B2 "X=1" "Delegate to the local-explore subagent: have it read $PWD/sample.txt and report the second line. Then reply with only what it reported." --plugin-dir ~/src/agentik-agents
run C1 "X=1" "Use the Explore subagent to find which file directly inside $PWD contains the word gamma. Reply with the file name only."
run C2 "CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1" "Use the Explore subagent to find which file directly inside $PWD contains the word gamma. Reply with the file name only."
run C3 "X=1" "Use the general-purpose subagent to read $PWD/sample.txt and report its first line. Reply with only what it reported."
echo "=== DONE ==="
