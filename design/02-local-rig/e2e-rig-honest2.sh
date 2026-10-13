#!/bin/bash
# Honest cross-agent test: a SEAT main (haiku) really delegates to two local subagents whose system
# prompts differ from the first token (same 3 tools), A -> B -> A, on each backend in turn.
# Backends are selected by agent model name only; the router reads ~/.config/agentroute/backends.json.
cd "$(dirname "$0")"; export PATH="$HOME/.local/bin:$PATH"; STATE=~/.local/state/agentroute; LEDGER=$STATE/requests.jsonl; BIN=~/src/agentik-agents/bin
printf 'alpha\nbeta\ngamma\n' > sample.txt
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN AGENTROUTE_BACKENDS
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 CLAUDE_CODE_ATTRIBUTION_HEADER=0 CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1 API_TIMEOUT_MS=1800000
mask() { sed -E 's/sk-unsloth-([A-Za-z0-9_-]{6})[A-Za-z0-9_-]*/sk-unsloth-\1…/g'; }
restart_router() { for p in $(lsof -ti :8787); do kill -TERM $p; done; sleep 1; ( AGENTROUTE_LOCAL_CONCURRENCY=2 nohup "$BIN/agentroute" --serve >> "$STATE/agentroute.log" 2>&1 & ); sleep 1; "$BIN/agentroute" --check | mask; }
rows() { /usr/bin/python3 - "$LEDGER" "$1" <<'PY'
import json, sys
path, skip = sys.argv[1], int(sys.argv[2])
for i, l in enumerate(open(path)):
    if i < skip: continue
    r = json.loads(l)
    if r.get("route") != "local": continue
    u = r.get("usage") or {}
    print("    %-8s %-22s agent %-8s wall %6.1f  ttfb %6s  in %5s  cr %5s  out %4s  eff %s" % (
        r.get("backend"), str(r.get("model_out"))[:22], str(r.get("agent_id"))[:8], r.get("wall_s", 0) or 0, r.get("ttfb_s"),
        u.get("input_tokens"), u.get("cache_read_input_tokens"), u.get("output_tokens"), r.get("effort_out")))
PY
}
run_backend() { # name
  local B=$1; echo; echo "################ backend: $B ################"
  local AG; AG=$(cat <<JSON
{"probe-a":{"description":"Reader A. Reads one named file and reports one line from it.","prompt":"You are Reader A, a terse read-only explorer on a small local model. Read ONLY the file named in the task with the Read tool, then answer in ONE line with exactly what was asked. No preamble.","tools":["Read","Glob","Grep"],"model":"local/$B","effort":"low","maxTurns":6},
 "probe-b":{"description":"Reader B. Summarises a named file's contents briefly.","prompt":"You are Reader B. Your job is careful, literal reading: open the named file with Read, then report exactly the requested line and cite it as path:line. One short line, nothing else.","tools":["Read","Glob","Grep"],"model":"local/$B","effort":"low","maxTurns":6}}
JSON
)
  local M; M=$(wc -l < "$LEDGER"); local S; S=$(date +%s)
  echo "Do these three delegations ONE AT A TIME, in order, waiting for each result: (1) delegate to probe-a: read $PWD/sample.txt and report its last line; (2) delegate to probe-b: read $PWD/sample.txt and report its second line; (3) delegate to probe-a again: read $PWD/sample.txt and report its first line; (4) delegate to probe-a once more: read $PWD/sample.txt and report how many lines it has. Then reply with the four reported values separated by commas and nothing else." | \
  claude -p --model haiku --effort low --agents "$AG" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > "H-$B.json" 2> "H-$B.err"
  echo "  exit=$? wall=$(( $(date +%s) - S ))s"
  /usr/bin/python3 - "H-$B.json" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("  NO ENVELOPE:", e); sys.exit()
print("  ", {k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms")}, "result:", repr((d.get("result") or "")[:80]))
print("   modelUsage:", {m:(v["inputTokens"],v["outputTokens"]) for m,v in (d.get("modelUsage") or {}).items()})
PY
  grep -vE 'unrecognized_model' "H-$B.err" | head -c 300; echo "  local rows (A1 A2 | B1 B2 | A1 A2 | A1 A2 expected):"; rows "$M"
}
ollama stop qwen3.8:27b-mtp-q8_0 2>/dev/null; ollama stop qwen3.8:27b-mxfp8 2>/dev/null; sleep 2
curl -s http://127.0.0.1:11434/api/ps | python3 -c 'import sys,json; print("resident:", [(x["name"], round(x["size_vram"]/1e9,1)) for x in json.load(sys.stdin)["models"]])'
echo "=== llama (llama-server on the q8 blob, tuned) ==="; "$BIN/localrig" up llama | mask; restart_router | grep -E 'backend|model'; run_backend llama
echo; echo "--- llama-server cache lines (this run) ---"; grep -E 'restored context checkpoint|forcing full|prompt eval time' "$STATE/llama-server.log" | tail -10 | sed -E 's/^[0-9.]+ I //' | cut -c1-150
"$BIN/localrig" down llama | mask; sleep 2
echo; echo "=== mlx, 4 delegations (does the trie converge on same-agent-new-task?) ==="; "$BIN/localrig" up mlx | mask; restart_router | grep -E 'backend|model'; OM=$(wc -l < ~/Library/Logs/ollama.log | tr -d ' '); run_backend mlx
echo "--- mlx runner cache lines (this run) ---"; tail -n +"$OM" ~/Library/Logs/ollama.log | grep -E 'prefix_cache' | cut -c1-200
echo "=== DONE ==="
