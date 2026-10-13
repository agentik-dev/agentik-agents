#!/bin/bash
# Rig trial, backend "unsloth": Unsloth Studio API (llama-server underneath) on unsloth/Qwen3.8-27B-GGUF:UD-Q8_K_XL.
cd "$(dirname "$0")"; export PATH="$HOME/.local/bin:$PATH"; STATE=~/.local/state/agentroute; LEDGER=$STATE/requests.jsonl; UL=$STATE/unsloth.log; BIN=~/src/agentik-agents/bin
echo "--- free our MLX trial model (the chat server's qwen3.6 stays) ---"; ollama stop qwen3.8:27b-mxfp8 2>&1 | tail -1; sleep 2
curl -s http://127.0.0.1:11434/api/ps | python3 -c 'import sys,json; print("  resident:", [(x["name"], round(x["size_vram"]/1e9,1)) for x in json.load(sys.stdin)["models"]])'
: > "$UL"; S=$(date +%s); echo "--- localrig up unsloth (downloads ~29 GB on first run) ---"
"$BIN/localrig" up unsloth 2>&1 | sed 's/sk-unsloth-\([A-Za-z0-9_-]\{6\}\)[A-Za-z0-9_-]*/sk-unsloth-\1…/g'; echo "  up after $(( $(date +%s) - S ))s"
echo "--- unsloth log: backend/model/flags ---"; grep -iE 'llama-server|mlx|backend|loaded|model|slots|ctx|listening|port|key' "$UL" | grep -viE 'download|progress|%' | sed 's/sk-unsloth-\([A-Za-z0-9_-]\{6\}\)[A-Za-z0-9_-]*/sk-unsloth-\1…/g' | tail -14 | cut -c1-170
for p in $(lsof -ti :8787); do kill -TERM $p; done; sleep 1
unset AGENTROUTE_BACKENDS; export AGENTROUTE_LOCAL_CONCURRENCY=2
( nohup "$BIN/agentroute" --serve >> "$STATE/agentroute.log" 2>&1 & ); sleep 1
"$BIN/agentroute" --check | sed 's/sk-unsloth-\([A-Za-z0-9_-]\{6\}\)[A-Za-z0-9_-]*/sk-unsloth-\1…/g'; echo
KEY=$(python3 -c 'import json,os; d=json.load(open(os.path.expanduser("~/.config/agentroute/backends.json"))); print(d["unsloth"]["auth"])'); PORT=8888
echo "=== U0: smoke tool call via Unsloth /v1/messages ==="; S=$(date +%s)
curl -s -m 300 http://127.0.0.1:$PORT/v1/messages -H "Authorization: $KEY" -H 'content-type: application/json' -d '{"model":"x","max_tokens":120,"output_config":{"effort":"low"},"tools":[{"name":"read_file","description":"Read a file","input_schema":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}],"messages":[{"role":"user","content":"Read /etc/hosts using the tool."}]}' | head -c 400; echo; echo "  wall=$(( $(date +%s) - S ))s"
echo "=== U0b: prose throughput ==="; S=$(date +%s); curl -s -m 300 http://127.0.0.1:$PORT/v1/messages -H "Authorization: $KEY" -H 'content-type: application/json' -d '{"model":"x","max_tokens":300,"thinking":{"type":"disabled"},"messages":[{"role":"user","content":"Write a 250-word essay on the history of the NAS product line."}]}' | python3 -c 'import sys,json; d=json.load(sys.stdin); u=d.get("usage",{}); print("  out", u.get("output_tokens"), "tokens")'; echo "  wall=$(( $(date +%s) - S ))s"
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("  NO ENVELOPE:", e); sys.exit()
print("  ", {k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}, "result:", repr((d.get("result") or "")[:100]))
print("   modelUsage:", {m:(v["inputTokens"],v["outputTokens"]) for m,v in (d.get("modelUsage") or {}).items()})
PY
}
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=ollama ANTHROPIC_AUTH_TOKEN=ollama CLAUDE_CODE_ATTRIBUTION_HEADER=0; unset CLAUDE_CODE_OAUTH_TOKEN
printf 'alpha\nbeta\ngamma\n' > sample.txt
AG_A='{"agent-a":{"description":"reader A","prompt":"You are reader A, a terse read-only explorer. Read only the named file. Answer in one line.","tools":["Read","Glob","Grep"],"model":"local/unsloth","effort":"low"}}'
AG_B='{"agent-b":{"description":"reader B","prompt":"You are reader B. You summarise files you are pointed at, in one short line, citing path:line.","tools":["Read","Glob","Grep"],"model":"local/unsloth","effort":"low"}}'
run() { local lab=$1 ag=$2 prompt=$3; echo; echo "=== $lab ==="; local M=$(wc -l < "$LEDGER") S=$(date +%s); echo "$prompt" | claude -p --model local/unsloth --effort low --agents "$ag" --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > "$lab.json" 2> "$lab.err"; echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show "$lab.json"; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M" | sed 's/Bearer sk-un/Bearer sk-un…/'; }
run U1 "$AG_A" "Read $PWD/sample.txt and reply with its last line only."
run U2 "$AG_B" "Read $PWD/sample.txt and reply with its second line only."
run U3 "$AG_A" "Read $PWD/sample.txt and reply with its first line only."
echo; echo "=== U4: two agents at once ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
( echo "Read $PWD/sample.txt and reply with its last line only." | claude -p --model local/unsloth --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > U4a.json 2> U4a.err ) &
( echo "Read $PWD/sample.txt and reply with its first line only." | claude -p --model local/unsloth --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > U4b.json 2> U4b.err ) &
wait; echo "  both done wall=$(( $(date +%s) - S ))s"; show U4a.json; show U4b.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M" | sed 's/Bearer sk-un/Bearer sk-un…/'
echo "--- unsloth log: cache/timing tail ---"; grep -E 'prompt eval|eval time|restored|forcing full|n_tokens' "$UL" | tail -10 | cut -c1-160
echo "=== DONE ==="
