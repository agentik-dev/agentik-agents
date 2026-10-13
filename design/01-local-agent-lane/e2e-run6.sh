#!/bin/bash
# T6 integration: main thread on the claude.ai seat (haiku, via the router), spawning a
# custom subagent whose frontmatter pins a LOCAL model + effort low. Verifies: OAuth
# passthrough, subagent model routing by name, effort propagation, agent-id headers.
cd "$(dirname "$0")"
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 CLAUDE_CODE_ATTRIBUTION_HEADER=0
AG='{"local-explore":{"description":"Read-only local explorer for mechanical file questions.","prompt":"You are a read-only file explorer. Use the Read tool to read the file named in the task and answer tersely. Never guess; read first.","tools":["Read","Glob","Grep"],"model":"qwen3.8:27b-mtp-q8_0","effort":"low"}}'
S=$(date +%s)
echo "Delegate to the local-explore subagent: have it read $PWD/sample.txt and report the second line. Then reply with only what it reported." | \
claude -p --model haiku --effort low --agents "$AG" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > t6b.json 2> t6b.err
echo "exit=$? wall=$(( $(date +%s) - S ))s"
python3 - <<'PY'
import json
try: d=json.load(open("t6b.json"))
except Exception as e: print("NO ENVELOPE", e); raise SystemExit
print({k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms","total_cost_usd")})
print("result:", repr((d.get("result") or "")[:300]))
print("modelUsage:", json.dumps(d.get("modelUsage"))[:700])
PY
echo "--- stderr ---"; head -c 800 t6b.err; echo
