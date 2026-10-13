#!/usr/bin/env bash
#
# Regression tests for claude-api-agent's --profile containment.
#
# Drives the real wrapper end-to-end with a stub `claude` that prints its argv
# (and, when stdin is redirected, its stdin), so these exercise the actual code
# path. No API key is used and no request is made, so the suite is free to run.
#
#   tests/test-arg-handling.sh
#
# The wrapper's containment model is an ALLOW-LIST with a total parse: under
# --profile it CONSTRUCTS the child's argv rather than filtering the caller's,
# and the prompt is delivered on stdin so its text can never be parsed as a
# flag. This suite locks in the four bypasses that model was built to close,
# each confirmed against the real `claude` binary before the rewrite:
#
#   B1  --profile after a claude arg ran with ZERO containment flags
#   B2  a flag-shaped prompt (`-p "--dangerously-skip-permissions"`) reached
#       the child as a real flag
#   B3  capability-restoring caller flags (--tools, --settings, --agents,
#       --dangerously-skip-permissions) passed straight through
#   B4  an unlisted value-taking flag (--debug-file) shifted scan parity and
#       silently dropped the profile's spend ceiling
set -uo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WRAPPER="${REPO}/bin/claude-api-agent"

TMP="$(mktemp -d)"
trap 'rm -rf -- "$TMP"' EXIT

# Prints argv one per line, and (only when stdin is redirected) the stdin body
# on a single STDIN:[...] line so tests can assert prompt delivery.
cat > "${TMP}/fake-claude" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do printf '%s\n' "$a"; done
if [ ! -t 0 ]; then printf 'STDIN:['; cat; printf ']\n'; fi
EOF
chmod +x "${TMP}/fake-claude"

export CLAUDE_API_AGENT_CLAUDE_BIN="${TMP}/fake-claude"
export ANTHROPIC_API_KEY="sk-an""t-test-not-a-real-key"  # split so the hygiene scan reads no key shape
export CLAUDE_API_AGENT_NO_LOG=1
# Isolate from the real pin in the config home and any ambient proxy.
export CLAUDE_API_AGENT_PROXY_PIN_FILE="${TMP}/pin"
: > "${TMP}/pin"
unset HTTPS_PROXY https_proxy ALL_PROXY all_proxy 2>/dev/null || true

pass=0 fail=0
ok()   { printf '  PASS  %s\n' "$1"; (( ++pass )); }
bad()  { printf '  FAIL  %s\n     %s\n' "$1" "$2"; (( ++fail )); }

# Feed /dev/null as stdin so a bare profile run does not block, and so the
# prompt/stdin-conflict guard does not fire in tests that pass -p.
argv_of()   { "$WRAPPER" "$@" </dev/null 2>/dev/null; }
count_flag() { local f="$1"; shift; argv_of "$@" | grep -cx -- "$f"; }
value_of()   { local f="$1"; shift; argv_of "$@" | grep -A1 -x -- "$f" | sed -n '2p'; }
# True if the run was refused (non-zero exit, nothing to the child).
refuses()    { ! "$WRAPPER" "$@" </dev/null >/dev/null 2>&1; }

echo "== B1: --profile is honoured in any position, never forwarded =="

# The old bug: --profile after a claude arg ran with no containment flags.
for n in --allowedTools --disallowedTools --permission-mode --max-budget-usd; do
    c=$(count_flag "$n" --no-stdin -p "hi" --profile review)
    if (( c >= 1 )); then
        ok "profile-after-arg still emits ${n}"
    else
        bad "profile-after-arg still emits ${n}" "count=${c} (old bug: 0)"
    fi
done

echo "== B2: a flag-shaped prompt reaches the child on stdin, never argv =="

out=$(argv_of --profile review --no-stdin -p "--dangerously-skip-permissions")
if ! grep -qx -- "--dangerously-skip-permissions" <<<"$out"; then
    ok "flag-shaped prompt is absent from argv"
else
    bad "flag-shaped prompt is absent from argv" "reached argv"
fi
if grep -qxF -- "STDIN:[--dangerously-skip-permissions]" <<<"$out"; then
    ok "flag-shaped prompt delivered verbatim on stdin"
else
    bad "flag-shaped prompt delivered verbatim on stdin" "$(grep STDIN <<<"$out")"
fi
# And it is NOT refused -- a prompt is data, not an error.
if ! refuses --profile review --no-stdin -p "--dangerously-skip-permissions"; then
    ok "flag-shaped prompt runs (it is data, not a flag)"
else
    bad "flag-shaped prompt runs" "was refused"
fi

echo "== B3: capability-restoring caller flags are refused =="

for f in --dangerously-skip-permissions --allow-dangerously-skip-permissions \
         --tools --settings --agents --agent --mcp-config --permission-mode \
         --allowedTools --disallowedTools --setting-sources; do
    if refuses --profile review --no-stdin "$f" x; then
        ok "refuses ${f}"
    else
        bad "refuses ${f}" "wrapper ran instead of refusing"
    fi
done

echo "== B4: an unlisted value-taking flag is refused, not silently absorbed =="

if refuses --profile review --no-stdin --debug-file "--max-budget-usd=77777" -p x; then
    ok "refuses --debug-file (unlisted)"
else
    bad "refuses --debug-file (unlisted)" "wrapper ran"
fi
# The ceiling is intact on a normal run.
if [[ "$(value_of --max-budget-usd --profile review --no-stdin -p hi)" == "10" ]]; then
    ok "profile ceiling present on a normal run"
else
    bad "profile ceiling present on a normal run" "not 10"
fi

echo "== value rules: a flag value may not itself look like a flag =="

if refuses --profile review --no-stdin --model "--evil" -p x; then
    ok "refuses a leading-dash flag value"
else
    bad "refuses a leading-dash flag value" "accepted"
fi
if refuses --profile review --no-stdin --max-budget-usd "not-a-number" -p x; then
    ok "refuses a non-numeric --max-budget-usd"
else
    bad "refuses a non-numeric --max-budget-usd" "accepted"
fi

echo "== allowed overrides win, in bare and joined form =="

if [[ "$(value_of --model --profile review --no-stdin --model claude-opus-5 -p hi)" == "claude-opus-5" ]] \
   && (( $(count_flag --model --profile review --no-stdin --model claude-opus-5 -p hi) == 1 )); then
    ok "bare --model override replaces the profile's copy"
else
    bad "bare --model override replaces the profile's copy" "wrong value or count"
fi
if [[ "$(value_of --max-budget-usd --profile review --no-stdin --max-budget-usd=0.5 -p hi)" == "0.5" ]] \
   && (( $(count_flag --max-budget-usd --profile review --no-stdin --max-budget-usd=0.5 -p hi) == 1 )); then
    ok "joined --max-budget-usd=0.5 replaces the profile's copy"
else
    bad "joined --max-budget-usd=0.5 replaces the profile's copy" "wrong value or count"
fi
n=$(count_flag --effort --profile review --no-stdin --model claude-opus-5 -p hi)
if (( n == 0 )); then
    ok "--model override drops the profile's --effort"
else
    bad "--model override drops the profile's --effort" "effort count=${n}"
fi

echo "== --prompt-file requires a regular file (no silent empty prompt) =="

printf 'body from a file' > "${TMP}/pf.txt"
out=$(argv_of --profile explore --no-stdin --prompt-file "${TMP}/pf.txt")
if grep -qxF -- "STDIN:[body from a file]" <<<"$out"; then
    ok "--prompt-file delivers a regular file's contents on stdin"
else
    bad "--prompt-file delivers a regular file's contents on stdin" "$(grep STDIN <<<"$out")"
fi
# A directory passes -r but cat fails; the old code ran with an empty prompt.
if refuses --profile explore --no-stdin --prompt-file "${TMP}"; then
    ok "--prompt-file <directory> is refused, not run with an empty prompt"
else
    bad "--prompt-file <directory> is refused" "ran anyway"
fi

echo "== the prompt never appears in the child's argv under --profile =="

out=$(argv_of --profile review --no-stdin -p "ordinary prompt text")
if ! grep -qx -- "ordinary prompt text" <<<"$out"; then
    ok "prompt text is not an argv token"
else
    bad "prompt text is not an argv token" "found in argv"
fi
if grep -qxF -- "STDIN:[ordinary prompt text]" <<<"$out"; then
    ok "prompt text delivered on stdin"
else
    bad "prompt text delivered on stdin" "$(grep STDIN <<<"$out")"
fi

echo "== post-assembly invariant + profile defaults =="

# --tools is the flag that actually enforces read-only (--allowedTools only
# pre-approves; it does not restrict). Every profile must emit it, and it must
# carry exactly the read-only set.
for prof in review explore analyze; do
    if [[ "$(value_of --tools --profile "$prof" --no-stdin -p hi)" == "Read Grep Glob" ]]; then
        ok "${prof} emits --tools \"Read Grep Glob\""
    else
        bad "${prof} emits --tools \"Read Grep Glob\"" \
            "got '$(value_of --tools --profile "$prof" --no-stdin -p hi)'"
    fi
done
# It cannot be overridden by a caller (not on the allow-list): refused.
if refuses --profile review --no-stdin --tools "Bash" -p x; then
    ok "caller --tools is refused (cannot widen the toolset)"
else
    bad "caller --tools is refused" "accepted"
fi

for n in --tools --allowedTools --disallowedTools --permission-mode --max-budget-usd --output-format; do
    if (( $(count_flag "$n" --profile review --no-stdin -p hi) >= 1 )); then
        ok "review emits ${n}"
    else
        bad "review emits ${n}" "missing"
    fi
done
if [[ "$(value_of --effort --profile explore --no-stdin -p hi)" == "low" ]]; then
    ok "explore profile emits its defaults"
else
    bad "explore profile emits its defaults" "effort not low"
fi

echo "== pass-through mode: own options after claude args are refused, not forwarded =="

if refuses "$@" -p x --no-stdin; then
    ok "refuses --no-stdin after claude args in pass-through"
else
    bad "refuses --no-stdin after claude args in pass-through" "forwarded silently"
fi

echo "== --output-format under --profile: redundant json is a no-op, other values refused =="

# The profile already sets --output-format json; a caller repeating it must not
# be refused for a flag that changes nothing (the papercut this case closes).
for form in "--output-format json" "--output-format=json"; do
    if ! refuses --profile review --no-stdin $form -p hi; then
        ok "redundant ${form} is tolerated"
    else
        bad "redundant ${form} is tolerated" "was refused"
    fi
done
# It stays a NO-OP: exactly one --output-format reaches the child, value json.
c=$(count_flag --output-format --profile review --no-stdin --output-format json -p hi)
if (( c == 1 )); then
    ok "redundant --output-format json does not duplicate the flag"
else
    bad "redundant --output-format json does not duplicate the flag" "count=${c}"
fi
if [[ "$(value_of --output-format --profile review --no-stdin --output-format json -p hi)" == "json" ]]; then
    ok "child still sees --output-format json"
else
    bad "child still sees --output-format json" "not json"
fi
# Any other value is still refused -- it would break the envelope capture path.
for form in "--output-format yaml" "--output-format=text" "--output-format stream-json"; do
    if refuses --profile review --no-stdin $form -p hi; then
        ok "refuses ${form}"
    else
        bad "refuses ${form}" "wrapper ran instead of refusing"
    fi
done

echo "== --help / -h as the sole argument prints the wrapper's own help =="

for h in --help -h; do
    if "$WRAPPER" "$h" </dev/null 2>&1 | grep -q "headless Claude Code billed to an Anthropic API key"; then
        ok "${h} prints wrapper help"
    else
        bad "${h} prints wrapper help" "did not print the wrapper banner"
    fi
done

# (summary moved to end of file — the sandbox-note section runs after this point)

# ---------------------------------------------------------------------------
# Sandbox-note injection (pass-through mode). The delegate must start knowing
# its real sandbox; measured failures: work lost to the .claude/ write denial,
# and turns burned discovering Grep/Glob are absent under --bare.
#
# Assertions capture argv_of output into a variable and string-match: a
# `| grep -q` pipeline here dies of SIGPIPE under this suite's pipefail.
# ---------------------------------------------------------------------------
printf '\nSandbox note:\n'

t='pass-through run gets exactly one --append-system-prompt carrying SANDBOX FACTS'
out="$(argv_of -p hi --model m)"
if [[ "$(count_flag --append-system-prompt -p hi --model m)" == 1 && "$out" == *'SANDBOX FACTS'* ]]; then
  ok "$t"; else bad "$t" "$(printf '%s' "$out" | head -5)"; fi

t='a caller --append-system-prompt is merged, note first, still one flag'
out="$(argv_of -p hi --append-system-prompt 'MY ROLE')"
if [[ "$(count_flag --append-system-prompt -p hi --append-system-prompt 'MY ROLE')" == 1 \
      && "$out" == *'SANDBOX FACTS'* && "$out" == *'MY ROLE'* ]]; then
  ok "$t"; else bad "$t" "$(printf '%s' "$out" | head -5)"; fi

t='the merged note lands ahead of the caller text'
if [[ "${out%%MY ROLE*}" == *'SANDBOX FACTS'* ]]; then ok "$t"; else bad "$t" "order wrong"; fi

t='--no-sandbox-note passes argv through untouched'
if [[ "$(count_flag --append-system-prompt --no-sandbox-note -p hi)" == 0 ]]; then ok "$t"; else bad "$t" "note injected anyway"; fi

t='CLAUDE_API_AGENT_NO_SANDBOX_NOTE=1 also skips the note'
if [[ "$(CLAUDE_API_AGENT_NO_SANDBOX_NOTE=1 "$WRAPPER" -p hi </dev/null 2>/dev/null | grep -cx -- --append-system-prompt)" == 0 ]]; then
  ok "$t"; else bad "$t" "note injected anyway"; fi

t='acceptEdits runs get the dot-directory warning'
out="$(argv_of -p hi --permission-mode acceptEdits)"
if [[ "$out" == *'.claude/'* ]]; then ok "$t"; else bad "$t" "no dot-dir line"; fi

t='runs without acceptEdits skip the acceptEdits paragraph'
out="$(argv_of -p hi)"
if [[ "$out" == *'acceptEdits:'* ]]; then bad "$t" "paragraph present"; else ok "$t"; fi

t='profile role prompt states the real toolset (Read alone, Grep/Glob absent)'
out="$(argv_of --profile analyze -p hi)"
if [[ "$out" == *'Grep and Glob do'* && "$out" != *'exactly Read, Grep, and Glob'* ]]; then
  ok "$t"; else bad "$t" "$(printf '%s' "$out" | grep -n 'Read' | head -3)"; fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
(( fail == 0 ))
