#!/usr/bin/env bash
# tests/test-dispatch.sh: bin/agentik-agents execs the tool beside it with the args
# unchanged (agentik-r1 4.2). The tools here are stubs that echo `$#:$*`, in a temp dir
# beside a copy of the dispatcher, and one installed link, so nothing real runs and
# nothing is spent.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
D="$(mktemp -d)"
trap 'rm -r "${D:?}"' EXIT
cp "$REPO/bin/agentik-agents" "$D/"
for s in claude-local claude-agents localrig agentroute; do
  printf '#!/bin/sh\necho "$#:$*"\n' > "$D/$s"
  chmod +x "$D/$s"
done
A="$D/agentik-agents"
pass=0 fail=0

# expect NAME WANT CMD...: CMD's stdout is WANT and it exits 0.
expect() {
  local name=$1 want=$2 got code
  shift 2
  got="$("$@" 2>/dev/null)"; code=$?
  if [ "$got" = "$want" ] && [ "$code" = 0 ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL %s: got [%s] exit %s, want [%s]\n' "$name" "$got" "$code" "$want"
  fi
}

# expect_exit NAME CODE CMD...: CMD exits CODE with nothing on stdout.
expect_exit() {
  local name=$1 want=$2 got code
  shift 2
  got="$("$@" 2>/dev/null)"; code=$?
  if [ "$code" = "$want" ] && [ -z "$got" ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL %s: exit %s stdout [%s], want exit %s\n' "$name" "$code" "$got" "$want"
  fi
}

# the local lane
expect "local" "2:-p hi" "$A" local -p hi
# the status tool
expect "status" "1:status" "$A" status
expect "status args" "2:status --json" "$A" status --json
# the local rig and the router
expect "rig" "1:up" "$A" rig up
expect "route" "1:--check" "$A" route --check
# version and help
expect "--version" "agentik-agents 1.4.0" "$A" --version
for h in --help help -h; do
  got="$("$A" "$h")"; code=$?
  if [ "$code" = 0 ] && printf '%s\n' "$got" | grep -q '^  route \.\.\. *agentroute \.\.\.$'; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1)); printf 'FAIL %s: exit %s\n' "$h" "$code"
  fi
done
# usage: no verb, an unknown verb, a stray arg; usage goes to stderr only
expect_exit "no verb" 2 "$A"
expect_exit "unknown verb" 2 "$A" nosuch
expect_exit "help unknown" 2 "$A" help nosuch
expect_exit "--version arg" 2 "$A" --version x
expect_exit "doctor arg" 2 "$A" doctor x
# the API lane's verbs left with packet a-s17: each is a usage error now, like any unknown verb
for v in api setup-key key-status edit-key remove-key pin-proxy usage profiles fanout costs fold queue-mvp; do
  expect_exit "$v is gone" 2 "$A" "$v"
done
expect_exit "help api is gone" 2 "$A" help api
if "$A" nosuch 2>&1 >/dev/null | grep -q '^usage: agentik agents'; then
  pass=$((pass + 1))
else
  fail=$((fail + 1)); echo "FAIL usage line on stderr"
fi
# exit codes pass through
printf '#!/bin/sh\nexit 7\n' > "$D/localrig"
expect_exit "exit passes through" 7 "$A" rig status
# an installed link runs the tools beside its target, not beside the link
mkdir "$D/bin"
ln -s "$A" "$D/bin/agentik-agents"
expect "via link" "1:--check" "$D/bin/agentik-agents" route --check
# doctor reports and exits 0, the router's check from beside it
got="$(PATH="$D/bin:/usr/bin:/bin" "$A" doctor)"; code=$?
if [ "$code" = 0 ] && ! printf '%s\n' "$got" | grep -q 'API lane' \
   && printf '%s\n' "$got" | grep -q '^    1:--check$' \
   && printf '%s\n' "$got" | grep -q "^  agentik-agents  *$D/bin/agentik-agents$" \
   && printf '%s\n' "$got" | grep -q '^  agentik  *NOT ON PATH$'; then
  pass=$((pass + 1))
else
  fail=$((fail + 1)); printf 'FAIL doctor: exit %s\n%s\n' "$code" "$got"
fi
# doctor's python3 row (a-s10, portfolio entry 26): PATH's python3 and its version against the
# 3.9 floor, from stubs first on PATH, and the gate's pin when a .python-version beside a copy's
# bin/ names another version; doctor still exits 0 (entry 25)
for v in 3.8.12 3.12.7; do
  mkdir "$D/py-$v" && printf '#!/bin/sh\necho %s\n' "$v" > "$D/py-$v/python3" && chmod +x "$D/py-$v/python3"
done
mkdir "$D/py-bad" && printf '#!/bin/sh\nexit 1\n' > "$D/py-bad/python3" && chmod +x "$D/py-bad/python3"
mkdir "$D/nopy" && for t in readlink dirname sed; do ln -s "$(command -v "$t")" "$D/nopy/$t"; done
for c in nopin pin pin-comment; do
  mkdir -p "$D/$c/bin" && cp "$REPO/bin/agentik-agents" "$D/agentroute" "$D/$c/bin/"
done
printf '3.12.7\n' > "$D/pin/.python-version"
# read as pyenv reads it (fix round 1): the first word of the first line not blank or a comment
printf "# the gate's pin\n3.12.7 # pyenv reads the first word\n" > "$D/pin-comment/.python-version"
# expect_row NAME WANT COPY PATH: the copy's doctor under PATH exits 0 and prints the row WANT
expect_row() {
  local name=$1 want=$2 got code
  got="$(PATH="$4" "$D/$3/bin/agentik-agents" doctor 2>/dev/null)"; code=$?
  if [ "$code" = 0 ] && printf '%s\n' "$got" | grep -q -x -F -- "$(printf '  %-18s %s' python3 "$want")"; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1)); printf 'FAIL doctor python3, %s: exit %s, want [%s]\n%s\n' "$name" "$code" "$want" "$got"
  fi
}
expect_row "3.8.12" "$D/py-3.8.12/python3 3.8.12 (below 3.9)" nopin "$D/py-3.8.12:/usr/bin:/bin"
expect_row "3.12.7" "$D/py-3.12.7/python3 3.12.7 (3.9 or later)" nopin "$D/py-3.12.7:/usr/bin:/bin"
expect_row "3.8.12 under the pin" "$D/py-3.8.12/python3 3.8.12 (below 3.9; the gate pins 3.12.7)" pin "$D/py-3.8.12:/usr/bin:/bin"
expect_row "3.12.7 under the pin" "$D/py-3.12.7/python3 3.12.7 (3.9 or later)" pin "$D/py-3.12.7:/usr/bin:/bin"
expect_row "the pin's comment form" "$D/py-3.8.12/python3 3.8.12 (below 3.9; the gate pins 3.12.7)" pin-comment "$D/py-3.8.12:/usr/bin:/bin"
expect_row "does not run" "$D/py-bad/python3 does not run" nopin "$D/py-bad:/usr/bin:/bin"
expect_row "not on PATH" "NOT ON PATH" nopin "$D/nopy"
# the dispatcher is POSIX sh
if sh -n "$REPO/bin/agentik-agents"; then pass=$((pass + 1)); else fail=$((fail + 1)); echo "FAIL sh -n"; fi
# the plugin's edges (a-s6): plugin/ ships alone and reaches the tools through this dispatcher,
# so its manifest is the only one, a marketplace here (if one returns) ships plugin/, not the
# repo root, and no file under plugin/ names a path outside it
if [ -f "$REPO/plugin/.claude-plugin/plugin.json" ] && [ ! -e "$REPO/.claude-plugin/plugin.json" ]; then
  pass=$((pass + 1))
else
  fail=$((fail + 1)); echo "FAIL plugin manifest: want plugin/.claude-plugin/plugin.json and none at the root"
fi
# (into a file: bash 3.2 misparses a heredoc inside $( ) that holds a backtick)
/usr/bin/python3 - "$REPO" > "$D/plugin-paths" 2>&1 <<'PY'
import json, os, re, sys
repo = sys.argv[1]
market = os.path.join(repo, ".claude-plugin", "marketplace.json")
if os.path.exists(market):
    for p in json.load(open(market)).get("plugins", []):
        if p.get("source") != "./plugin":
            print("marketplace.json sources %s at %r, not './plugin'" % (p.get("name"), p.get("source")))
root = os.path.realpath(os.path.join(repo, "plugin"))
ref = re.compile(r"\$\{?CLAUDE_PLUGIN_ROOT\}?(/[^\s`'\"()]*)?")
for d, _, files in os.walk(root):
    for f in sorted(files):
        path = os.path.join(d, f)
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except UnicodeDecodeError:
            continue
        rel = os.path.relpath(path, repo)
        for n, line in enumerate(lines, 1):
            for m in ref.finditer(line):
                t = os.path.realpath(root + (m.group(1) or ""))
                if not (t == root or (t.startswith(root + os.sep) and os.path.exists(t))):
                    print("%s:%d names %s, not a file inside plugin/" % (rel, n, m.group(0)))
            if re.search(r"(^|[^.])\.\./", line) or re.search(r"\$\{?REPO\b", line):
                print("%s:%d names a path outside plugin/" % (rel, n))
PY
got="$(cat "$D/plugin-paths")"
if [ -z "$got" ]; then pass=$((pass + 1)); else fail=$((fail + 1)); printf 'FAIL plugin paths:\n%s\n' "$got"; fi

# the interpreter (a-s9, portfolio entry 26): the two python tools run on `env python3`, the
# pin under make; the floor is 3.9, so each one's --help exits 0 under Apple's python3 with a
# temp HOME and nothing else inherited, skipped where that python3 does not run
PYTOOLS="agentroute claude-agents"
for t in $PYTOOLS; do
  first="$(head -1 "$REPO/bin/$t")"
  if [ "$first" = '#!/usr/bin/env python3' ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1)); printf 'FAIL %s line 1: [%s], want [#!/usr/bin/env python3]\n' "$t" "$first"
  fi
done
if /usr/bin/python3 -c '' >/dev/null 2>&1; then
  mkdir "$D/home"
  for t in $PYTOOLS; do
    if env -i HOME="$D/home" PATH=/usr/bin:/bin /usr/bin/python3 "$REPO/bin/$t" --help >/dev/null 2>&1; then
      pass=$((pass + 1))
    else
      fail=$((fail + 1)); printf 'FAIL %s --help under /usr/bin/python3 (the 3.9 floor)\n' "$t"
    fi
  done
else
  echo "skip: the 3.9 floor, /usr/bin/python3 -c '' fails"
fi

printf 'test-dispatch: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" = 0 ]
