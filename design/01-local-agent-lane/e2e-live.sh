#!/bin/bash
# Live e2e through the PRODUCTION router (bin/agentroute on 127.0.0.1:8787, real Ollama 0.33.2).
cd "$(dirname "$0")"
LEDGER=~/.local/state/agentroute/requests.jsonl
BIN=~/src/agentik-agents/bin
mark() { wc -l < "$LEDGER" 2>/dev/null || echo 0; }
rows_since() { tail -n +"$(( $1 + 1 ))" "$LEDGER" | python3 -c '
import sys,json
for l in sys.stdin:
    r=json.loads(l)
    if r.get("path","").startswith("/api/hello"): continue
    u=r.get("usage") or {}
    print(f"  {r[\"route\"]:<8} {str(r.get(\"status\")):<4} wall {r.get(\"wall_s\",0):6.1f} ttfb {str(r.get(\"ttfb_s\")):>6} | {str(r.get(\"model_in\"))[:22]:<22} -> {str(r.get(\"model_out\"))[:22]:<22} | eff {str(r.get(\"effort_in\")):>6}->{str(r.get(\"effort_out\")):<6} | strip {r.get(\"stripped_reminders\",\"-\")} | msgs {r.get(\"n_messages\")} tools {r.get(\"n_tools\")} | in {u.get(\"input_tokens\")} out {u.get(\"output_tokens\")} | agent {str(r.get(\"agent_id\"))[:8]} | auth {r.get(\"auth_kind\")}:{r.get(\"auth_prefix\",\"\")[:10]}")
'; }
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("  NO ENVELOPE:", e); sys.exit()
print("  ", {k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}, "result:", repr((d.get("result") or "")[:120]))
print("   modelUsage:", {m:(v["inputTokens"],v["outputTokens"]) for m,v in (d.get("modelUsage") or {}).items()})
PY
}
printf 'alpha\nbeta\ngamma\n' > sample.txt

echo "=== A: non-bare, --model local/default, two turns (reminder strip -> cache reuse through the production router) ==="
M=$(mark); S=$(date +%s)
( export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=ollama ANTHROPIC_AUTH_TOKEN=ollama CLAUDE_CODE_ATTRIBUTION_HEADER=0; unset CLAUDE_CODE_OAUTH_TOKEN
  echo "Read $PWD/sample.txt and reply with its last line only." | \
  claude -p --model local/default --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > A.json 2> A.err )
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show A.json; echo "  stderr: $(head -c 200 A.err)"; rows_since "$M"

echo; echo "=== B: claude-local launcher — seat main (haiku) delegates to the plugin's local-explore ==="
M=$(mark); S=$(date +%s)
( unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN
  echo "Delegate to the local-explore subagent: have it read $PWD/sample.txt and report the second line. Then reply with only what it reported." | \
  "$BIN/claude-local" -p --model haiku --effort low --plugin-dir ~/src/agentik-agents --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > B.json 2> B.err )
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show B.json; echo "  stderr: $(grep -v '^  ok' B.err | head -c 400)"; rows_since "$M"

echo; echo "=== C: D5 — built-in Explore agent (names no model) should go local via CLAUDE_CODE_SUBAGENT_MODEL ==="
M=$(mark); S=$(date +%s)
( unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN
  echo "Use the Explore subagent to find which file directly inside $PWD contains the word gamma. Reply with the file name only." | \
  "$BIN/claude-local" -p --model haiku --effort low --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > C.json 2> C.err )
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show C.json; echo "  stderr: $(grep -v '^  ok' C.err | head -c 400)"; rows_since "$M"
echo "=== DONE ==="
