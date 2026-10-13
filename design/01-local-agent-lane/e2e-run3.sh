#!/bin/bash
cd "$(dirname "$0")"
printf 'alpha\nbeta\ngamma\n' > sample.txt
show() { python3 - "$1" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception as e: print("NO ENVELOPE:", e); sys.exit()
print({k:d.get(k) for k in ("is_error","subtype","num_turns","duration_ms","duration_api_ms","total_cost_usd")})
print("result:", repr((d.get("result") or "")[:200]))
print("usage:", d.get("usage"))
print("modelUsage:", json.dumps(d.get("modelUsage"))[:500])
print("denials:", d.get("permission_denials"))
PY
}
common() { export ANTHROPIC_BASE_URL=http://127.0.0.1:8787 ANTHROPIC_API_KEY=ollama ANTHROPIC_AUTH_TOKEN=ollama CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 CLAUDE_CODE_ATTRIBUTION_HEADER=0; unset CLAUDE_CODE_OAUTH_TOKEN; }
run() { local name=$1; shift; local S=$(date +%s); "$@" > "$name.json" 2> "$name.err"; local rc=$?; echo "exit=$rc wall=$(( $(date +%s) - S ))s"; show "$name.json"; echo "--- stderr ---"; head -c 600 "$name.err"; echo; }

echo "=== T1: bare, direct model, Read, effort low ==="; common
echo "Read the file $PWD/sample.txt and reply with exactly the number of lines it contains, nothing else." | \
run t1 claude --bare -p --model qwen3.8:27b-mtp-q8_0 --effort low --tools Read --permission-mode dontAsk --output-format json --add-dir "$PWD"

echo "=== T2: bare, alias haiku -> local, effort low ==="; common; export ANTHROPIC_DEFAULT_HAIKU_MODEL=qwen3.8:27b-mtp-q8_0
echo "Read the file $PWD/sample.txt and reply with the second line only." | \
run t2 claude --bare -p --model haiku --effort low --tools Read --permission-mode dontAsk --output-format json --add-dir "$PWD"
unset ANTHROPIC_DEFAULT_HAIKU_MODEL

echo "=== T3: bare, Bash tool, effort low ==="; common
echo "Run the shell command: wc -l $PWD/sample.txt   and report the count." | \
run t3 claude --bare -p --model qwen3.8:27b-mtp-q8_0 --effort low --tools Bash --permission-mode dontAsk --allowedTools "Bash(wc:*)" --output-format json --add-dir "$PWD"

echo "=== T4: NON-bare (full system prompt + CLAUDE.md + plugins), Read/Glob/Grep, effort low ==="; common
echo "Use Glob to list the files in $PWD, then Read sample.txt and reply with the first line only." | \
run t4 claude -p --model qwen3.8:27b-mtp-q8_0 --effort low --tools "Read Glob Grep" --permission-mode dontAsk --output-format json --add-dir "$PWD" --exclude-dynamic-system-prompt-sections

echo "=== T5: SEAT PASSTHROUGH via proxy (no key vars; saved claude.ai login), haiku, one turn ==="
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_DEFAULT_HAIKU_MODEL; export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
echo "Reply with the single word OK." | \
run t5 claude --bare -p --model haiku --effort low --tools "" --output-format json --exclude-dynamic-system-prompt-sections
echo "(bare mode ignores OAuth; if T5 failed with auth error, rerun non-bare below)"
echo "=== T5b: SEAT PASSTHROUGH non-bare ==="
echo "Reply with the single word OK." | \
run t5b claude -p --model haiku --effort low --tools "" --output-format json --exclude-dynamic-system-prompt-sections --setting-sources user
echo "=== DONE ==="
