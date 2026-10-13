#!/usr/bin/env bash
#
# Pins the wrapper's allow-list against the REAL `claude` binary.
#
#   tests/test-flag-pinning.sh
#
# The --profile allow-list in claude-api-agent hard-codes six caller flags and
# their arity (all value-taking). That table is only safe as long as it matches
# claude's actual flag surface: if a future release changes a flag's arity,
# renames it, or removes it, the wrapper would misbuild the child's argv. This
# test parses `claude --help` and fails CI when the surface drifts, so the
# breakage surfaces at build time rather than as a silent containment or
# budget bug at runtime.
#
# It also checks that the capability-restoring flags the wrapper REFUSES still
# exist in claude -- a refusal is only meaningful if the flag it refuses is
# real. If claude renames --dangerously-skip-permissions, the wrapper's refusal
# of the old name becomes dead code and the new name would need adding.
#
# Skips cleanly (exit 0) when claude is not installed, so the stub-driven
# suites remain the offline gate and this is the online one.
set -uo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE="${CLAUDE_API_AGENT_CLAUDE_BIN:-$(command -v claude 2>/dev/null || true)}"

if [[ -z "$CLAUDE" || ! -x "$CLAUDE" ]]; then
    echo "  SKIP  claude binary not found; flag-pinning check not run"
    exit 0
fi

HELP="$("$CLAUDE" --help 2>&1)" || { echo "  SKIP  'claude --help' failed"; exit 0; }

pass=0 fail=0
ok()  { printf '  PASS  %s\n' "$1"; (( ++pass )); }
bad() { printf '  FAIL  %s\n     %s\n' "$1" "$2"; (( ++fail )); }

# A flag is value-taking in claude's help if its line shows "--flag <...>".
# Boolean flags show no angle-bracket operand.
flag_line() { grep -oE -- "(^|[[:space:]])(-[a-zA-Z], )?${1}( <[^>]+>)?" <<<"$HELP" | head -1; }
flag_exists()      { grep -qE -- "(^|[[:space:]])${1}([[:space:], =]|\$)" <<<"$HELP"; }
flag_takes_value() { flag_line "$1" | grep -q " <"; }

echo "== allow-listed flags exist and are value-taking =="
for f in --model --fallback-model --effort --max-budget-usd --add-dir; do
    if ! flag_exists "$f"; then
        bad "${f} exists in claude" "not in --help; allow-list entry is stale"
    elif ! flag_takes_value "$f"; then
        bad "${f} is value-taking" "claude now treats it as boolean; arity in profile_flag_allowed() is wrong"
    else
        ok "${f} exists and takes a value"
    fi
done

echo "== -p / --print are boolean (prompt is a positional / stdin) =="
# The rewrite depends on -p being boolean: the prompt is delivered on stdin,
# not as -p's value. If claude makes -p value-taking, revisit set_prompt().
for f in -p --print; do
    if flag_exists "$f" && ! flag_takes_value "$f"; then
        ok "${f} is boolean"
    else
        bad "${f} is boolean" "claude may have changed -p arity; the stdin prompt path assumes boolean"
    fi
done

echo "== --tools exists and can restrict the built-in toolset =="
# --tools is what enforces read-only in every profile. If claude removes it or
# changes it so it no longer restricts, the read-only guarantee silently ends.
if flag_exists --tools; then
    ok "--tools still exists"
else
    bad "--tools still exists" "gone from claude; profiles can no longer enforce read-only"
fi
if grep -qiE -- '--tools.*(disable all|available tools|built-in)' <<<"$HELP"; then
    ok "--tools still documents restricting the built-in set"
else
    bad "--tools still documents restricting the built-in set" \
        "help text changed; re-verify it still removes Bash before trusting profiles"
fi

echo "== refused capability flags still exist (refusal stays meaningful) =="
for f in --dangerously-skip-permissions --tools --settings --agents --permission-mode; do
    if flag_exists "$f"; then
        ok "${f} still exists (wrapper correctly refuses it)"
    else
        bad "${f} still exists" "claude renamed/removed it; the wrapper's refusal is now dead code"
    fi
done

printf '\n%d passed, %d failed\n' "$pass" "$fail"
(( fail == 0 ))
