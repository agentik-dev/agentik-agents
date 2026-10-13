#!/bin/bash
# Two-turn non-bare runs through the router with a full system-prompt dump.
# Run A: default env  -> expect the system prompt to change between turns (reminder block).
# Run B: CLAUDE_CODE_TOTAL_TOKENS_REMINDER=off -> expect identical system prompt, turn-2 cache reuse.
cd "$(dirname "$0")"
until ! pgrep -f requal.sh >/dev/null; do sleep 5; done
for p in $(lsof -ti :8787); do kill -TERM $p; done; sleep 1
rm -f ../sysdump-A.jsonl ../sysdump-B.jsonl
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=ollama ANTHROPIC_AUTH_TOKEN=ollama CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 CLAUDE_CODE_ATTRIBUTION_HEADER=0; unset CLAUDE_CODE_OAUTH_TOKEN
run() { # $1 = label, $2 = dump file
  (AGENTROUTE_DEBUG_SYSTEM=$2 AGENTROUTE_LOG=$PWD/../agentroute.jsonl nohup /usr/bin/python3 ../agentroute.py > ../agentroute.out 2>&1 &); sleep 1
  S=$(date +%s)
  echo "Read $PWD/sample.txt and reply with its last line only." | \
  claude -p --model qwen3.8:27b-mtp-q8_0 --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections --setting-sources user > "$1.json" 2> "$1.err"
  echo "$1: exit=$? wall=$(( $(date +%s) - S ))s result=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(repr((d.get("result") or "")[:60]), d.get("num_turns"), "turns")' "$1.json" 2>&1)"
  for p in $(lsof -ti :8787); do kill -TERM $p; done; sleep 1
}
echo "=== Run A (reminder ON) ==="; run cacheA ../sysdump-A.jsonl
echo "=== Run B (CLAUDE_CODE_TOTAL_TOKENS_REMINDER=off) ==="; export CLAUDE_CODE_TOTAL_TOKENS_REMINDER=off; run cacheB ../sysdump-B.jsonl
echo "=== system prompt diff per run (turn1 vs turn2) ==="
python3 - <<'PY'
import json, difflib
for lab in ("A","B"):
    rows=[json.loads(l) for l in open(f"../sysdump-{lab}.jsonl")]
    print(f"--- run {lab}: {len(rows)} requests")
    if len(rows)>=2:
        a=json.dumps(rows[0]["system"],indent=0).splitlines(); b=json.dumps(rows[1]["system"],indent=0).splitlines()
        d=[l for l in difflib.unified_diff(a,b,lineterm="",n=0) if l.startswith(("+","-")) and not l.startswith(("+++","---"))]
        print("system diff lines:", len(d)); [print("   ", l[:200]) for l in d[:8]]
        print("turn2 messages roles:", [m["role"] for m in rows[1]["messages"]])
PY
echo "=== ollama cache lines for these runs ==="
grep -E 'task.n_tokens|forcing full|cached n_tokens = [0-9]{4,}, memory_seq_rm|prompt eval time' ~/Library/Logs/ollama.log | tail -14 | cut -c1-140
echo "=== DONE ==="
