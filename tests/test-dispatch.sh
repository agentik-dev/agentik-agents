#!/usr/bin/env bash
# tests/test-dispatch.sh: bin/agentik-agents execs the tool beside it with the args
# unchanged (agentik-r1 4.2). The tools here are stubs that echo `$#:$*`, in a temp dir
# beside a copy of the dispatcher, and one installed link, so nothing real runs and
# nothing is spent.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
D="$(mktemp -d)"
# F holds the fanout cases' PATH folders, outside the dispatcher's own folder D (packet al0)
F="$(mktemp -d)"
trap 'rm -r "${D:?}" "${F:?}"' EXIT
cp "$REPO/plugin/lib/agentik-agents" "$D/"
# the version is plugin.json's, the one pin: a frozen tree holds a copy beside the dispatcher (a-s18)
cp "$REPO/plugin/.claude-plugin/plugin.json" "$D/plugin.json"
V="$(/usr/bin/python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$D/plugin.json")"
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
expect "--version" "agentik-agents $V" "$A" --version
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
for v in setup-key key-status edit-key remove-key pin-proxy usage profiles costs fold queue-mvp; do
  expect_exit "$v is gone" 2 "$A" "$v"
done
# the API lane's two verbs (al4): a copy beside apilane/, under HOME at this temp folder, so the
# real user file is never read; the lane refuses there in one stderr line that names HOME, never
# the usage line. fanout reaches the lane only where a wall is proved; elsewhere, with no file
# under this HOME, it is main's usage error
mkdir "$D/lane"
cp "$REPO/plugin/lib/agentik-agents" "$D/lane/"
cp -R "$REPO/plugin/lib/apilane" "$D/lane/apilane"
lane_case() {
  local name=$1 err code
  shift
  err="$(HOME="$D" XDG_CACHE_HOME="$D/cache" "$D/lane/agentik-agents" "$@" 2>&1 >/dev/null)"; code=$?
  if [ "$code" = 2 ] && [ "$(printf '%s\n' "$err" | wc -l | tr -d ' ')" = 1 ] \
     && printf '%s\n' "$err" | grep -q 'HOME' && ! printf '%s\n' "$err" | grep -q '^usage:'; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1)); printf 'FAIL %s: exit %s stderr [%s]\n' "$name" "$code" "$err"
  fi
}
lane_case "api names HOME" api x
if [ -x /usr/bin/sandbox-exec ]; then
  lane_case "fanout names HOME" fanout x
else
  expect_exit "fanout with no wall and no file" 2 env HOME="$D" "$D/lane/agentik-agents" fanout x
fi
expect_exit "help api is gone" 2 "$A" help api
if "$A" nosuch 2>&1 >/dev/null | grep -q '^usage: agentik agents'; then
  pass=$((pass + 1))
else
  fail=$((fail + 1)); echo "FAIL usage line on stderr"
fi
if "$A" nosuch 2>&1 >/dev/null | grep -q -x 'verbs: local status rig route doctor describe install-cli help'; then
  pass=$((pass + 1))
else
  fail=$((fail + 1)); echo "FAIL the usage's verbs line (describe among them, ak7)"
fi

# fanout (packet al0): a stub verb that hands the call to the claude-fanout on PATH, unchanged
# but for each --yes before a --; with none on PATH, or one that resolves inside the dispatcher's
# own folder, exit 2 and nothing run; its help alone, as the only argument, runs nothing. From
# al6 the stub is the verb only where no wall is proved, so these cases run on N, a copy beside
# apilane/ whose walled.sh says no wall, under HOME at a temp folder with no file; one runs once
# more on A, which has no apilane/
N="$F/nowall"
mkdir -p "$N" "$F/home" "$F/stub" "$F/none" "$F/own"
cp "$REPO/plugin/lib/agentik-agents" "$N/"
cp -R "$REPO/plugin/lib/apilane" "$N/apilane"
echo 'apilane_walled() { return 1; }' > "$N/apilane/walled.sh"
printf '#!/bin/sh\necho "argc=$#"; for a; do printf "[%%s]\\n" "$a"; done\nexit 7\n' > "$F/stub/claude-fanout"
chmod +x "$F/stub/claude-fanout"
printf '#!/bin/sh\n: > "%s/ran"\nexit 9\n' "$F" > "$N/own-forward"
chmod +x "$N/own-forward"
ln -s "$N/own-forward" "$F/own/claude-fanout"
NO_TOOL='agentik agents fanout: the API lane is not in this version yet, and no claude-fanout is on PATH to hand the call to.'
OWN='agentik agents fanout: the claude-fanout on PATH is this tool'"'"'s own forward, and the API lane is not in this version yet.'
fan_help() {
  printf '%s\n' 'usage: agentik agents fanout [--yes] ARGS...' \
    'For now it hands ARGS to the claude-fanout on PATH, each --yes before a -- dropped.' \
    "The API lane's own fan-out takes this name in a later version." \
    "claude-fanout on PATH: $1"
}
# fan NAME OUT ERR CODE DIR ARGS...: `A fanout ARGS` with DIR first on PATH prints exactly OUT on
# stdout and ERR on stderr, and exits CODE
fan() {
  local name=$1 wout=$2 werr=$3 wcode=$4 dir=$5 out err code
  shift 5
  out="$(HOME="$F/home" PATH="$dir:/usr/bin:/bin" "${EXE:-$N/agentik-agents}" fanout "$@" 2>"$F/err")"; code=$?
  err="$(cat "$F/err")"
  if [ "$out" = "$wout" ] && [ "$err" = "$werr" ] && [ "$code" = "$wcode" ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    printf 'FAIL fanout %s: exit %s stdout [%s] stderr [%s], want exit %s [%s] [%s]\n' \
      "$name" "$code" "$out" "$err" "$wcode" "$wout" "$werr"
  fi
}
fan "args as given" "$(printf 'argc=5\n[--budget-usd]\n[2]\n[a b]\n[]\n[-x]')" "" 7 "$F/stub" \
  --budget-usd 2 'a b' '' -x
fan "--yes before --" "$(printf 'argc=5\n[--budget-usd]\n[2]\n[p]\n[--]\n[--yes]')" "" 7 "$F/stub" \
  --yes --budget-usd 2 p --yes -- --yes
fan "--yes alone" "argc=0" "" 7 "$F/stub" --yes
fan "no args" "argc=0" "" 7 "$F/stub"
fan "--yes= kept" "$(printf 'argc=2\n[--yes=1]\n[-yes]')" "" 7 "$F/stub" --yes=1 -yes
fan "--help not alone" "$(printf 'argc=2\n[--help]\n[x]')" "" 7 "$F/stub" --help x
# packet al7: where no wall is proved the detached forms reach the old tool unchanged
fan "--detach" "$(printf 'argc=2\n[--detach]\n[x]')" "" 7 "$F/stub" --detach x
fan "wait" "$(printf 'argc=4\n[wait]\n[x]\n[--timeout]\n[540]')" "" 7 "$F/stub" wait x --timeout 540
fan "none on PATH" "" "$NO_TOOL" 2 "$F/none" x
fan "own forward" "" "$OWN" 2 "$F/own" x
if [ ! -e "$F/ran" ]; then pass=$((pass + 1)); else fail=$((fail + 1)); echo "FAIL fanout: the own forward ran"; fi
fan "--help" "$(fan_help "$F/stub/claude-fanout")" "" 0 "$F/stub" --help
fan "-h" "$(fan_help "$F/stub/claude-fanout")" "" 0 "$F/stub" -h
fan "--help, none on PATH" "$(fan_help none)" "" 0 "$F/none" --help
EXE="$A" fan "args as given, no apilane/" "$(printf 'argc=5\n[--budget-usd]\n[2]\n[a b]\n[]\n[-x]')" "" 7 \
  "$F/stub" --budget-usd 2 'a b' '' -x
# in the no-wall copy, a file that says on: one line, exit 2, and the old tool is not run (under a
# temp HOME the lane names HOME first; the platform's own line is test_al4_report's PlatformTest)
mkdir -p "$F/home/.config/agentik/agents" "$F/mark"
printf 'api:\n  enabled: true\n' > "$F/home/.config/agentik/agents/config.yaml"
printf '#!/bin/sh\n: > "%s/mark/ran"\n' "$F" > "$F/mark/claude-fanout"
chmod +x "$F/mark/claude-fanout"
err="$(HOME="$F/home" XDG_CACHE_HOME="$F/cache" PATH="$F/mark:/usr/bin:/bin" "$N/agentik-agents" fanout x 2>&1 >/dev/null)"; code=$?
if [ "$code" = 2 ] && [ "$(printf '%s\n' "$err" | wc -l | tr -d ' ')" = 1 ] && [ ! -e "$F/mark/ran" ] \
   && ! printf '%s\n' "$err" | grep -q '^usage:'; then
  pass=$((pass + 1))
else
  fail=$((fail + 1)); printf 'FAIL fanout, no wall, file on: exit %s [%s]\n' "$code" "$err"
fi
rm -f "$F/home/.config/agentik/agents/config.yaml"
# R6: the table and every usage line stay byte for byte what they were at the pin, stdout,
# stderr and exit; skipped where the pin's object is not in this clone. The pin was c0193bd; it
# moved, by ak7-plug-agents's merge of main, to that row's last commit before the merge, whose
# table holds its `doctor [--json]` and `describe` lines and whose verbs line names `describe`
PIN=78977d4
if git -C "$REPO" cat-file -e "$PIN:plugin/lib/agentik-agents" 2>/dev/null; then
  mkdir "$F/pin" && git -C "$REPO" show "$PIN:plugin/lib/agentik-agents" > "$F/pin/agentik-agents"
  chmod +x "$F/pin/agentik-agents"
  for c in --help help "" nosuchverb fanout; do
    set -- "$c"; [ -n "$c" ] || set --
    for w in pin now; do
      if [ "$w" = pin ]; then x="$F/pin/agentik-agents"; else x="$A"; fi
      PATH="$F/none:/usr/bin:/bin" "$x" "$@" > "$F/$w.out" 2> "$F/$w.err"; echo "$?" > "$F/$w.code"
    done
    # `fanout` alone is the verb now: only its exit code and empty stdout are the pin's
    if [ "$c" = fanout ]; then
      cmp -s "$F/pin.code" "$F/now.code" && [ ! -s "$F/now.out" ] && ok=1 || ok=
    else
      cmp -s "$F/pin.out" "$F/now.out" && cmp -s "$F/pin.err" "$F/now.err" && cmp -s "$F/pin.code" "$F/now.code" && ok=1 || ok=
    fi
    if [ -n "$ok" ]; then pass=$((pass + 1)); else fail=$((fail + 1)); printf 'FAIL [%s] differs from %s\n' "$c" "$PIN"; fi
  done
else
  echo "skip: R6's byte compare, $PIN is not in this clone"
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
# 3.9 floor, from stubs first on PATH, and the gate's pin when a .python-version at a copy's root
# above plugin/lib/ names another version; doctor still exits 0 (entry 25)
for v in 3.8.12 3.12.7; do
  mkdir "$D/py-$v" && printf '#!/bin/sh\necho %s\n' "$v" > "$D/py-$v/python3" && chmod +x "$D/py-$v/python3"
done
mkdir "$D/py-bad" && printf '#!/bin/sh\nexit 1\n' > "$D/py-bad/python3" && chmod +x "$D/py-bad/python3"
mkdir "$D/nopy" && for t in readlink dirname sed; do ln -s "$(command -v "$t")" "$D/nopy/$t"; done
for c in nopin pin pin-comment; do
  mkdir -p "$D/$c/plugin/lib" && cp "$REPO/plugin/lib/agentik-agents" "$D/agentroute" "$D/$c/plugin/lib/"
done
printf '3.12.7\n' > "$D/pin/.python-version"
# read as pyenv reads it (fix round 1): the first word of the first line not blank or a comment
printf "# the gate's pin\n3.12.7 # pyenv reads the first word\n" > "$D/pin-comment/.python-version"
# expect_row NAME WANT COPY PATH: the copy's doctor under PATH exits 0 and prints the row WANT
expect_row() {
  local name=$1 want=$2 got code
  got="$(PATH="$4" "$D/$3/plugin/lib/agentik-agents" doctor 2>/dev/null)"; code=$?
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
if sh -n "$REPO/plugin/lib/agentik-agents"; then pass=$((pass + 1)); else fail=$((fail + 1)); echo "FAIL sh -n"; fi
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

# the interpreter (a-s9, a-s18, hq entry 6): the two python tools run on `/usr/bin/python3`,
# the one interpreter a fresh Mac and this one share; the floor is 3.9, so each one's --help
# exits 0 under Apple's python3 with a temp HOME and nothing else inherited, skipped where that
# python3 does not run
PYTOOLS="agentroute claude-agents"
for t in $PYTOOLS; do
  first="$(head -1 "$REPO/plugin/lib/$t")"
  if [ "$first" = '#!/usr/bin/python3' ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1)); printf 'FAIL %s line 1: [%s], want [#!/usr/bin/python3]\n' "$t" "$first"
  fi
done
if /usr/bin/python3 -c '' >/dev/null 2>&1; then
  mkdir "$D/home"
  for t in $PYTOOLS; do
    if env -i HOME="$D/home" PATH=/usr/bin:/bin /usr/bin/python3 "$REPO/plugin/lib/$t" --help >/dev/null 2>&1; then
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
