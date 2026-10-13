#!/bin/bash
# Rig trial, backend "llama" (llama-server on the Ollama q8 blob, -np 2, cache-ram 16G, dense checkpoints).
# Measures the two things Ollama's llama runner could not do: cross-agent prefix restore, and two agents at once.
cd "$(dirname "$0")"; STATE=~/.local/state/agentroute; LEDGER=$STATE/requests.jsonl; SL=$STATE/llama-server.log; BIN=~/src/agentik-agents/bin
for p in $(lsof -ti :8787); do kill -TERM $p; done; sleep 1
export AGENTROUTE_BACKENDS='{"llama":{"url":"http://127.0.0.1:8081","model":"qwen3.8-27b-q8","auth":"Bearer local-llama","fold_system":true}}'
export AGENTROUTE_LOCAL_CONCURRENCY=2
( nohup "$BIN/agentroute" --serve >> "$STATE/agentroute.log" 2>&1 & ); sleep 1
"$BIN/agentroute" --check; echo
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("  NO ENVELOPE:", e); sys.exit()
print("  ", {k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}, "result:", repr((d.get("result") or "")[:100]))
print("   modelUsage:", {m:(v["inputTokens"],v["outputTokens"]) for m,v in (d.get("modelUsage") or {}).items()})
PY
}
srvlog() { grep -E 'restored context checkpoint|forcing full prompt|prompt eval time|n_tokens =|cache' "$SL" | tail -n "$1" | sed -E 's/^[0-9.]+ I //' | cut -c1-150; }
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=ollama ANTHROPIC_AUTH_TOKEN=ollama CLAUDE_CODE_ATTRIBUTION_HEADER=0; unset CLAUDE_CODE_OAUTH_TOKEN
printf 'alpha\nbeta\ngamma\n' > sample.txt
AG_A='{"agent-a":{"description":"reader A","prompt":"You are reader A, a terse read-only explorer. Read only the named file. Answer in one line.","tools":["Read","Glob","Grep"],"model":"local/llama","effort":"low"}}'
AG_B='{"agent-b":{"description":"reader B","prompt":"You are reader B. You summarise files you are pointed at, in one short line, citing path:line.","tools":["Read","Glob","Grep"],"model":"local/llama","effort":"low"}}'
echo "=== L1: agent A, two turns (within-agent cache) ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
echo "Read $PWD/sample.txt and reply with its last line only." | claude -p --model local/llama --effort low --agents "$AG_A" --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > L1.json 2> L1.err
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show L1.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"; srvlog 6
echo; echo "=== L2: agent B right after A (cross-agent: shared tool prefix, different system text) ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
( export ANTHROPIC_BASE_URL=http://127.0.0.1:8787; echo "Read $PWD/sample.txt and reply with its second line only." | claude -p --model local/llama --effort low --agents "$AG_B" --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > L2.json 2> L2.err )
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show L2.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"; srvlog 6
echo; echo "=== L3: A again (is A's prefix still restorable from host cache after B ran?) ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
echo "Read $PWD/sample.txt and reply with its first line only." | claude -p --model local/llama --effort low --agents "$AG_A" --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > L3.json 2> L3.err
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show L3.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"; srvlog 6
echo; echo "=== L4: two agents AT ONCE (-np 2) ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
( echo "Read $PWD/sample.txt and reply with its last line only." | claude -p --model local/llama --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > L4a.json 2> L4a.err ) &
( echo "Read $PWD/sample.txt and reply with its first line only." | claude -p --model local/llama --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > L4b.json 2> L4b.err ) &
wait; echo "  both done wall=$(( $(date +%s) - S ))s"; show L4a.json; show L4b.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"; srvlog 10
echo "=== DONE ==="
