#!/usr/bin/env bash
#
# Regression tests for claude-api-agent's run path: exit-code fidelity, the
# logging subprocess's environment, envelope detection, and the age-key deny
# rule. Uses stub `claude` binaries, so no API key is used and no request is
# made.
#
#   tests/test-run-path.sh
set -uo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WRAPPER="${REPO}/bin/claude-api-agent"

TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT
# Every run now writes a run dir beside the usage log (packet a-s5); keep the
# runs that set no CLAUDE_API_AGENT_LOG out of the real state dir.
export XDG_STATE_HOME="${TMP}/state"
# ... and a caller's exported CLAUDE_API_AGENT_LOG is never written either.
export CLAUDE_API_AGENT_LOG="${TMP}/state/agentik-agents/api/usage.jsonl"

# Emits a large JSON envelope, then exits 7. Large enough that a downstream
# reader closing early produces a real SIGPIPE.
cat > "${TMP}/big-claude" <<'EOF'
#!/usr/bin/env bash
printf '{"total_cost_usd":0.01,"session_id":"x","filler":"'
head -c 200000 /dev/zero | tr '\0' 'x'
printf '"}\n'
exit 7
EOF

# Prints its argv, and keeps a copy: under --profile the wrapper folds the
# child's stdout (stream-json) and prints only a result event, so the profile
# cases read the copy.
cat > "${TMP}/small-claude" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do printf '%s\\n' "\$a"; done
for a in "\$@"; do printf '%s\\n' "\$a"; done > "${TMP}/small.argv"
EOF

# Stands in for python3 so the test can observe the logger's environment.
mkdir -p "${TMP}/shadow"
cat > "${TMP}/shadow/python3" <<'EOF'
#!/usr/bin/env bash
cat > /dev/null
printf 'key=%s\n' "${ANTHROPIC_API_KEY:+PRESENT}" >> "$PROBE_OUT"
EOF
chmod +x "${TMP}/big-claude" "${TMP}/small-claude" "${TMP}/shadow/python3"

export ANTHROPIC_API_KEY="sk-an""t-test-not-a-real-key"  # split so the hygiene scan reads no key shape

pass=0 fail=0
ok()  { printf '  PASS  %s\n' "$1"; (( ++pass )); }
bad() { printf '  FAIL  %s\n     %s\n' "$1" "$2"; (( ++fail )); }

echo "== exit-code fidelity =="

# The capture path (taken whenever a JSON envelope is logged) buffers the
# child's output and must replay the child's own exit code -- including when
# the caller's consumer closes the pipe early and `cat` dies of SIGPIPE.
CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/big-claude" CLAUDE_API_AGENT_LOG="${TMP}/usage.jsonl" \
    "$WRAPPER" --output-format json -p hi 2>/dev/null | head -c 10 >/dev/null
rc=${PIPESTATUS[0]}
if [[ "$rc" == 7 ]]; then
    ok "capture path preserves child exit code through SIGPIPE"
else
    bad "capture path preserves child exit code through SIGPIPE" "expected 7, got ${rc}"
fi

rc=$(CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/big-claude" CLAUDE_API_AGENT_LOG="${TMP}/usage.jsonl" \
     "$WRAPPER" --output-format json -p hi >/dev/null 2>&1; echo $?)
if [[ "$rc" == 7 ]]; then
    ok "capture path preserves child exit code without a pipe"
else
    bad "capture path preserves child exit code without a pipe" "expected 7, got ${rc}"
fi

echo "== the logging subprocess gets no credentials =="

: > "${TMP}/probe.out"
PROBE_OUT="${TMP}/probe.out" PATH="${TMP}/shadow:$PATH" \
    CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/big-claude" CLAUDE_API_AGENT_LOG="${TMP}/usage.jsonl" \
    "$WRAPPER" --output-format json -p hi >/dev/null 2>&1
if grep -q '^key=$' "${TMP}/probe.out" 2>/dev/null; then
    ok "usage logger does not inherit ANTHROPIC_API_KEY"
elif grep -q 'PRESENT' "${TMP}/probe.out" 2>/dev/null; then
    bad "usage logger does not inherit ANTHROPIC_API_KEY" "key was present in logger environ"
else
    bad "usage logger does not inherit ANTHROPIC_API_KEY" "probe did not run (no output)"
fi

echo "== envelope detection is position-aware =="

# A prompt containing the literal flag must not route a text-format run onto
# the capture path.
out=$(CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/small-claude" \
      "$WRAPPER" -p "--output-format" --output-format text 2>/dev/null | head -1)
if [[ "$out" == "--bare" ]]; then
    ok "prompt '--output-format' does not flip run to the capture path"
else
    bad "prompt '--output-format' does not flip run to the capture path" "first argv line: '${out}'"
fi

echo "== age-key deny rule covers relative paths =="

for v in "keys.txt" "./secrets/keys.txt" "${HOME}/.config/sops/age/keys.txt"; do
    : > "${TMP}/small.argv"
    SOPS_AGE_KEY_FILE="$v" CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/small-claude" \
        "$WRAPPER" --profile explore --no-stdin -p hi >/dev/null 2>&1
    n=$(grep -c 'keys.txt' "${TMP}/small.argv")
    if (( n > 0 )); then
        ok "SOPS_AGE_KEY_FILE='${v}' produces a deny rule"
    else
        bad "SOPS_AGE_KEY_FILE='${v}' produces a deny rule" "no deny rule emitted"
    fi
done

echo "== proxy pinning =="

# The pin lives outside the repo: by default the config home's agentik/agents/proxy-pin.conf.
CFG="${TMP}/cfg"
env -u CLAUDE_API_AGENT_PROXY_PIN_FILE -u https_proxy -u ALL_PROXY -u all_proxy \
    XDG_CONFIG_HOME="$CFG" HTTPS_PROXY=http://pinned.example:3128 \
    "$WRAPPER" --pin-proxy </dev/null >/dev/null 2>&1
dflt="${CFG}/agentik/agents/proxy-pin.conf"
if [[ -f "$dflt" ]] && grep -qx 'http://pinned.example:3128' "$dflt"; then
    ok "--pin-proxy writes the pin in the config home"
else
    bad "--pin-proxy writes the pin in the config home" "no pin at $dflt"
fi
mode="$(stat -f '%Lp' "$dflt" 2>/dev/null || stat -c '%a' "$dflt" 2>/dev/null)"
if [[ "$mode" == 600 ]]; then ok "  the pin is mode 0600"; else bad "  the pin is mode 0600" "mode $mode"; fi
if [[ -z "$(git -C "$(dirname -- "$WRAPPER")/.." ls-files -- proxy-pin.conf)" ]]; then
    ok "  and git tracks no proxy-pin.conf"
else
    bad "  and git tracks no proxy-pin.conf" "tracked"
fi
out=$(env -u CLAUDE_API_AGENT_PROXY_PIN_FILE -u https_proxy -u ALL_PROXY -u all_proxy \
    -u CLAUDE_API_AGENT_EXPECTED_PROXY XDG_CONFIG_HOME="${TMP}/cfg-none" \
    HTTPS_PROXY=http://any.example:3128 CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/small-claude" \
    "$WRAPPER" --profile explore --no-stdin -p hi 2>&1 >/dev/null)
if [[ "$out" == *"no pin is configured"* ]]; then
    ok "a missing pin file takes the no-pin path"
else
    bad "a missing pin file takes the no-pin path" "$out"
fi

PIN="${TMP}/proxy-pin.conf"
printf '# comment\nhttp://good.example:8080\n' > "$PIN"

# Point at an isolated pin file so the real one is never touched, and
# clear the ambient proxy so each case controls its own state.
proxyrun() {
    env -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy \
        -u CLAUDE_API_AGENT_EXPECTED_PROXY \
        CLAUDE_API_AGENT_PROXY_PIN_FILE="$PIN" \
        CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/small-claude" \
        "$@" "$WRAPPER" --profile explore --no-stdin -p hi 2>&1 >/dev/null
}

if [[ -z "$(proxyrun env HTTPS_PROXY=http://good.example:8080)" ]]; then
    ok "matching proxy is silent"
else
    bad "matching proxy is silent" "unexpected warning"
fi

# Capture before matching. Piping into `grep -q` under `set -o pipefail` is
# racy: grep exits at the first match and closes the pipe, so the wrapper can
# die of SIGPIPE mid-write and poison the pipeline's status.
out=$(proxyrun env HTTPS_PROXY=http://evil.example:3128)
if [[ "$out" == *"PROXY CHANGED"* ]]; then
    ok "changed proxy warns"
else
    bad "changed proxy warns" "no PROXY CHANGED warning"
fi

out=$(proxyrun env)
if [[ "$out" == *"pinned"* ]]; then
    ok "pinned but absent proxy warns"
else
    bad "pinned but absent proxy warns" "no warning"
fi

: > "$PIN"
out=$(proxyrun env HTTPS_PROXY=http://any.example:8080)
if [[ "$out" == *"no pin is configured"* ]]; then
    ok "proxy with no pin warns"
else
    bad "proxy with no pin warns" "no warning"
fi

if [[ -z "$(proxyrun env)" ]]; then
    ok "no proxy and no pin is silent"
else
    bad "no proxy and no pin is silent" "unexpected warning"
fi

echo "== interpreter hooks are stripped =="

for v in NODE_OPTIONS NODE_EXTRA_CA_CERTS; do
    out=$(env "$v=/tmp/x" CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/small-claude" \
              CLAUDE_API_AGENT_PROXY_PIN_FILE="$PIN" \
              "$WRAPPER" --profile explore --no-stdin -p hi 2>&1 >/dev/null)
    if [[ "$out" == *"ignoring inherited ${v}"* ]]; then
        ok "${v} is stripped"
    else
        bad "${v} is stripped" "not stripped"
    fi
done

echo "== usage log records substance, not content =="

qlog="${TMP}/quality.jsonl"
rm -f "$qlog"
emit() {
    cat > "${TMP}/q-claude" <<EOF
#!/usr/bin/env bash
printf '%s\n' '$1'
EOF
    chmod +x "${TMP}/q-claude"
    CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/q-claude" CLAUDE_API_AGENT_LOG="$qlog" \
        CLAUDE_API_AGENT_PROXY_PIN_FILE="$PIN" \
        "$WRAPPER" --profile review --no-stdin -p hi >/dev/null 2>&1
}

# The failure this exists for: expensive, schema-valid, substanceless, and
# reported as a success by every field in the envelope.
emit '{"total_cost_usd":0.5,"num_turns":8,"is_error":false,"subtype":"success","terminal_reason":"completed","structured_output":{"summary":"test","findings":[{"file":"a"}]}}'
emit '{"total_cost_usd":0.2,"num_turns":5,"is_error":false,"subtype":"success","terminal_reason":"completed","structured_output":{"summary":"A properly substantive summary of the review findings goes here.","findings":[{"file":"bin/x"}]}}'
emit '{"total_cost_usd":0,"num_turns":1,"is_error":true,"subtype":"success","terminal_reason":"api_error","result":"Invalid API key"}'

quals=$(python3 -c "
import json,sys
print(','.join(json.loads(l)['quality'] for l in open('$qlog')))
" 2>/dev/null)
if [[ "$quals" == "thin,ok,error" ]]; then
    ok "quality verdict distinguishes thin / ok / error"
else
    bad "quality verdict distinguishes thin / ok / error" "got '${quals}'"
fi

# Sizes are metadata; the answer itself must never be written to the log.
sizes=$(python3 -c "
import json
rows=[json.loads(l) for l in open('$qlog')]
print(all(isinstance(r.get('summary_chars'), int) and r['summary_chars'] > 0
          for r in rows[:2]))
" 2>/dev/null)
if [[ "$sizes" == "True" ]] && ! grep -q 'substantive summary' "$qlog"; then
    ok "log records sizes but not the answer text"
else
    bad "log records sizes but not the answer text" "sizes=${sizes}; $(head -c 200 "$qlog")"
fi

summary=$(CLAUDE_API_AGENT_LOG="$qlog" "$WRAPPER" --usage 2>&1)
if [[ "$summary" == *"returned almost nothing"* && "$summary" == *'$0.5000'* ]]; then
    ok "--usage surfaces spend that bought nothing"
else
    bad "--usage surfaces spend that bought nothing" "$summary"
fi
if [[ "$summary" == *"api_error"* && "$summary" != *"success  \$0.0000"* ]]; then
    ok "--usage reports terminal_reason, not the misleading subtype"
else
    bad "--usage reports terminal_reason, not the misleading subtype" "$summary"
fi

echo "== run tags =="

tlog="${TMP}/tags.jsonl"
rm -f "$tlog"
emit_tagged() {
    cat > "${TMP}/t-claude" <<'EOF'
#!/usr/bin/env bash
printf '{"total_cost_usd":0.1,"num_turns":2,"is_error":false,"subtype":"success","terminal_reason":"completed","result":"a substantive prose result long enough to clear the substance threshold"}\n'
EOF
    chmod +x "${TMP}/t-claude"
    CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/t-claude" CLAUDE_API_AGENT_LOG="$tlog" \
        CLAUDE_API_AGENT_PROXY_PIN_FILE="$PIN" \
        "$WRAPPER" "$@" --profile explore --no-stdin -p hi >/dev/null 2>&1
}

emit_tagged --tag id=e1 --tag phase=triage
CLAUDE_API_AGENT_TAGS="id=e2,phase=fix" emit_tagged --tag shard=7

got=$(python3 -c "
import json
print('|'.join(json.dumps(json.loads(l)['tags'], sort_keys=True) for l in open('$tlog')))
" 2>/dev/null)
want='{"id": "e1", "phase": "triage"}|{"id": "e2", "phase": "fix", "shard": "7"}'
if [[ "$got" == "$want" ]]; then
    ok "tags are recorded from both --tag and CLAUDE_API_AGENT_TAGS"
else
    bad "tags are recorded from both --tag and CLAUDE_API_AGENT_TAGS" "got ${got}"
fi

# A malformed tag must stop the run rather than silently mis-attribute spend.
for bad_tag in "BadKey=x" "noequals" "empty="; do
    if CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/t-claude" CLAUDE_API_AGENT_PROXY_PIN_FILE="$PIN" \
       "$WRAPPER" --tag "$bad_tag" --profile explore --no-stdin -p hi >/dev/null 2>&1; then
        bad "rejects malformed tag '${bad_tag}'" "wrapper ran instead of refusing"
    else
        ok "rejects malformed tag '${bad_tag}'"
    fi
done

printf '\n%d passed, %d failed\n' "$pass" "$fail"
(( fail == 0 ))
