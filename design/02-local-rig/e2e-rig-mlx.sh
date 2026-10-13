#!/bin/bash
# Rig trial, backend "mlx": Ollama's MLX runner on qwen3.8:27b-mxfp8 (prefix trie across conversations + MTP).
# Same four tests as rig-llama.sh so the rows compare. Waits for the pull, frees llama-server's 32 GiB first.
cd "$(dirname "$0")"; STATE=~/.local/state/agentroute; LEDGER=$STATE/requests.jsonl; OL=~/Library/Logs/ollama.log; BIN=~/src/agentik-agents/bin
until ollama list 2>/dev/null | grep -q '27b-mxfp8'; do sleep 10; done; echo "pull complete: $(ollama list | grep 27b-mxfp8)"
pkill -f 'llama-server -m' && sleep 2; pgrep -f 'llama-server -m' >/dev/null && echo "llama-server still up" || echo "llama-server stopped (memory freed)"
for p in $(lsof -ti :8787); do kill -TERM $p; done; sleep 1
export AGENTROUTE_BACKENDS='{"mlx":{"url":"http://127.0.0.1:11434","model":"qwen3.8:27b-mxfp8"}}'
export AGENTROUTE_LOCAL_CONCURRENCY=2
( nohup "$BIN/agentroute" --serve >> "$STATE/agentroute.log" 2>&1 & ); sleep 1
"$BIN/agentroute" --check; echo
OLMARK=$(wc -l < "$OL")
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("  NO ENVELOPE:", e); sys.exit()
print("  ", {k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}, "result:", repr((d.get("result") or "")[:100]))
print("   modelUsage:", {m:(v["inputTokens"],v["outputTokens"]) for m,v in (d.get("modelUsage") or {}).items()})
PY
}
ollog() { tail -n +"$1" "$OL" | grep -iE 'prefix|cache|draft|accept|mtp|specul|prompt eval|eval count|load|mlx runner' | grep -vE 'GIN' | tail -n 12 | cut -c1-170; }
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=ollama ANTHROPIC_AUTH_TOKEN=ollama CLAUDE_CODE_ATTRIBUTION_HEADER=0; unset CLAUDE_CODE_OAUTH_TOKEN
printf 'alpha\nbeta\ngamma\n' > sample.txt
AG_A='{"agent-a":{"description":"reader A","prompt":"You are reader A, a terse read-only explorer. Read only the named file. Answer in one line.","tools":["Read","Glob","Grep"],"model":"local/mlx","effort":"low"}}'
AG_B='{"agent-b":{"description":"reader B","prompt":"You are reader B. You summarise files you are pointed at, in one short line, citing path:line.","tools":["Read","Glob","Grep"],"model":"local/mlx","effort":"low"}}'
echo "=== M0: cold load + smoke (native /api/chat think:false, chat-server path gate) ==="; S=$(date +%s)
curl -s --max-time 600 http://127.0.0.1:11434/api/chat -d '{"model":"qwen3.8:27b-mxfp8","stream":false,"think":false,"messages":[{"role":"user","content":"In one sentence, what is a NAS?"}]}' | python3 -c 'import sys,json; d=json.load(sys.stdin); m=d["message"]; print("  content_len", len(m.get("content","")), "thinking_len", len(m.get("thinking","")), "| eval", d.get("eval_count"), "tok in", round(d.get("eval_duration",0)/1e9,1), "s =", round(d.get("eval_count",0)/max(d.get("eval_duration",1)/1e9,0.001),1), "tok/s | prompt", d.get("prompt_eval_count"), "tok in", round(d.get("prompt_eval_duration",0)/1e9,2), "s | load", round(d.get("load_duration",0)/1e9,1), "s")'
echo "  wall=$(( $(date +%s) - S ))s"; curl -s http://127.0.0.1:11434/api/ps | python3 -c 'import sys,json; print("  resident:", [(x["name"], round(x["size_vram"]/1e9,1)) for x in json.load(sys.stdin)["models"]])'; grep -E 'starting (mlx|llama) runner' "$OL" | tail -1 | grep -oE 'starting [a-z]+ runner subprocess" model=[^ ]+' | sed 's/^/  /'
echo "=== M0b: prose throughput (MTP acceptance on free text) ==="; curl -s --max-time 600 http://127.0.0.1:11434/api/generate -d '{"model":"qwen3.8:27b-mxfp8","prompt":"Write a 250-word essay on the history of the NAS product line.","stream":false,"think":false,"options":{"num_predict":300}}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print("  gen", d.get("eval_count"), "tok @", round(d.get("eval_count",0)/max(d.get("eval_duration",1)/1e9,0.001),1), "tok/s | prefill", d.get("prompt_eval_count"), "@", round(d.get("prompt_eval_count",0)/max(d.get("prompt_eval_duration",1)/1e9,0.001),1), "tok/s")'
echo "=== M1: agent A, two turns ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
echo "Read $PWD/sample.txt and reply with its last line only." | claude -p --model local/mlx --effort low --agents "$AG_A" --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > M1.json 2> M1.err
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show M1.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"; ollog "$OLMARK"
echo; echo "=== M2: agent B right after A (cross-agent) ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s); OLMARK=$(wc -l < "$OL")
echo "Read $PWD/sample.txt and reply with its second line only." | claude -p --model local/mlx --effort low --agents "$AG_B" --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > M2.json 2> M2.err
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show M2.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"; ollog "$OLMARK"
echo; echo "=== M3: A again after B ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s); OLMARK=$(wc -l < "$OL")
echo "Read $PWD/sample.txt and reply with its first line only." | claude -p --model local/mlx --effort low --agents "$AG_A" --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > M3.json 2> M3.err
echo "  exit=$? wall=$(( $(date +%s) - S ))s"; show M3.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"; ollog "$OLMARK"
echo; echo "=== M4: two agents at once (MLX runner is serial; expect ~2x wall) ==="; M=$(wc -l < "$LEDGER"); S=$(date +%s)
( echo "Read $PWD/sample.txt and reply with its last line only." | claude -p --model local/mlx --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > M4a.json 2> M4a.err ) &
( echo "Read $PWD/sample.txt and reply with its first line only." | claude -p --model local/mlx --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > M4b.json 2> M4b.err ) &
wait; echo "  both done wall=$(( $(date +%s) - S ))s"; show M4a.json; show M4b.json; /usr/bin/python3 ../ledger-tail.py "$LEDGER" "$M"
echo "=== DONE ==="
