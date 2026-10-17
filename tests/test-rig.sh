#!/usr/bin/env bash
#
# Tests for localrig and claude-local.
#
# Both tools were shipped untested, and four reproduced defects lived in exactly the paths
# a test would have walked: a BSD-incompatible chmod that aborted claude-local's cold start,
# a curl idiom that reported every dead port as alive, hand-built JSON that a backend-supplied
# model id could inject, and a key mask that only fired on strings of 12 characters or more.
#
# Everything here runs against stub HTTP servers and temp directories, with a fake `claude`
# first on PATH. No inference server is started and no real backend is touched. No real
# router is started either: the guard test collides with a decoy router this suite starts,
# and the cold-start tests run a copy of claude-local beside a stub router. Every process the
# suite starts is stopped in its EXIT trap, and the developer's own router is never signalled.
#
#     tests/test-rig.sh
set -uo pipefail
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LOCALRIG="$REPO/bin/localrig"
CLAUDE_LOCAL="$REPO/bin/claude-local"
passed=0; failed=0
check() { if [ "$1" = "0" ]; then printf '  PASS  %s\n' "$2"; passed=$((passed+1)); else printf '  FAIL  %s\n     %s\n' "$2" "${3:-}"; failed=$((failed+1)); fi; }
contains() { case "$1" in *"$2"*) return 0;; *) return 1;; esac; }

TMP="$(cd "$(mktemp -d)" && pwd -P)"   # physical: claude-local resolves its path with readlink -f
# A pid in $TMP/cold/pids was written by a stub router this suite's claude-local copy started;
# it is signalled only while its argv still names that stub.
stub_router_pids() {
  local p
  for p in $(cat "$TMP/cold/pids" 2>/dev/null); do
    contains "$(ps -o args= -p "$p" 2>/dev/null)" "$TMP/cold/bin/agentroute --serve" && echo "$p"
  done
}
cleanup() {
  local p
  for p in ${STUB_PID:-} ${DECOY_PID:-} $(stub_router_pids); do kill "$p" 2>/dev/null; done
  rm -rf "$TMP"
}
trap 'cleanup 2>/dev/null' EXIT   # quiet: the shell would report each job it reaps
export AGENTROUTE_STATE_DIR="$TMP/state" XDG_CONFIG_HOME="$TMP/config"

# A fake claude, first on PATH for the whole suite: it logs its argv and exits 2, as the real
# one does on an unknown flag. No test here reaches a real claude.
FAKE_CLAUDE_LOG="$TMP/claude.argv"
mkdir -p "$TMP/fakebin"
cat > "$TMP/fakebin/claude" <<EOF
#!/bin/sh
printf '%s\n' "\$*" >> "$FAKE_CLAUDE_LOG"
exit 2
EOF
chmod +x "$TMP/fakebin/claude"
export PATH="$TMP/fakebin:$PATH"
# neither folder exists under $TMP, so the new one is used (agentik-r1 6.3 c19)
BACKENDS="$TMP/config/agentik/agents/route/backends.json"

# A stub Ollama: /api/tags lists one tag, and a model id chosen to break naive JSON building.
STUB_PORT=$(/usr/bin/python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
cat > "$TMP/stub.py" <<'PY'
import http.server, json, sys
EVIL = 'evil","url":"http://attacker.invalid:9","z":"'
class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/api/tags"):
            out = json.dumps({"models": [{"name": "qwen3.8:27b-mxfp8"}, {"name": EVIL}]}).encode()
        else:
            out = json.dumps({"version": "0.33.2"}).encode()
        self.send_response(200); self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
PY
/usr/bin/python3 "$TMP/stub.py" "$STUB_PORT" & STUB_PID=$!
for _ in $(seq 1 40); do curl -fsS -m 1 -o /dev/null "http://127.0.0.1:$STUB_PORT/api/tags" 2>/dev/null && break; sleep 0.1; done
export LOCALRIG_OLLAMA_URL="http://127.0.0.1:$STUB_PORT"

echo "== BSD portability: the idioms that broke a cold start =="
mkdir -p "$TMP/p"; err="$( { chmod 700 -- "$TMP/p"; } 2>&1 )"; chmod_rc=$?
check "$( [ "$chmod_rc" != "0" ] && echo 0 || echo 1 )" \
  "this platform's chmod really does reject a bare -- (so the cold-start bug was real here)" "rc=$chmod_rc: $err"
if grep -q 'chmod 700 -- ' "$CLAUDE_LOCAL" "$LOCALRIG"; then check 1 "no tool still calls chmod with a bare --"; else check 0 "no tool still calls chmod with a bare --"; fi

echo "== dead ports must not read as alive =="
DEAD=$(/usr/bin/python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
code=$(curl -s -m 1 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$DEAD/v1/models" 2>/dev/null) || code=000
check "$( [ "$code" = "000" ] && echo 0 || echo 1 )" \
  "the fixed idiom yields a bare 000 for a closed port (the old one appended a second and yielded 000000)" "got '$code'"
# match code, not the comment that explains why the idiom was removed
if grep -v '^[[:space:]]*#' "$LOCALRIG" | grep -q '|| echo 000'; then
  check 1 "localrig no longer appends a second 000 to curl's own"
else
  check 0 "localrig no longer appends a second 000 to curl's own"
fi

echo "== up mlx: registration, permissions, atomicity =="
out="$("$LOCALRIG" up mlx 2>&1)"; rc=$?
check "$rc" "up mlx succeeds against a reachable Ollama" "$out"
check "$( [ -f "$BACKENDS" ] && echo 0 || echo 1 )" "backends.json is written"
mode=$(stat -f '%Lp' "$BACKENDS" 2>/dev/null || stat -c '%a' "$BACKENDS" 2>/dev/null)
check "$( [ "$mode" = "600" ] && echo 0 || echo 1 )" "backends.json is mode 600 (it holds an API key)" "mode $mode"
/usr/bin/python3 -c "import json,sys; d=json.load(open('$BACKENDS')); sys.exit(0 if d['mlx']['url']=='$LOCALRIG_OLLAMA_URL' else 1)"
check "$?" "the mlx entry points at the configured Ollama, not an injected host"
check "$( contains "$out" "restart-router" && echo 0 || echo 1 )" \
  "up says the running router will not see the change until a restart" "$out"

echo "== a backend-supplied model id cannot inject JSON =="
out="$(LOCALRIG_MLX_TAG='evil","url":"http://attacker.invalid:9","z":"' "$LOCALRIG" up mlx 2>&1)"; rc=$?
/usr/bin/python3 - "$BACKENDS" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
bad = [k for k, v in d.items() if isinstance(v, dict) and "attacker.invalid" in str(v.get("url", ""))]
sys.exit(1 if bad else 0)
PY
check "$?" "no entry's url was redirected by a crafted model id" "rc=$rc out=$out"
/usr/bin/python3 -c "import json; json.load(open('$BACKENDS'))"
check "$?" "backends.json is still valid JSON after a hostile value"

echo "== default, and what down does to it =="
"$LOCALRIG" default mlx >/dev/null 2>&1
/usr/bin/python3 -c "import json,sys; d=json.load(open('$BACKENDS')); sys.exit(0 if d.get('default',{}).get('model')==d['mlx']['model'] else 1)"
check "$?" "default mlx copies the backend into the default key"
out="$("$LOCALRIG" default nosuch 2>&1)"; rc=$?
check "$( [ "$rc" != "0" ] && contains "$out" "not declared" && echo 0 || echo 1 )" \
  "default on an undeclared backend fails with a clear message" "$out"
out="$("$LOCALRIG" down mlx 2>&1)"
/usr/bin/python3 -c "import json,sys; d=json.load(open('$BACKENDS')); sys.exit(1 if 'default' in d else 0)"
check "$?" "down removes a default that pointed at the backend being removed (it used to orphan it at a dead port)" "$out"
check "$( contains "$out" "default also removed" && echo 0 || echo 1 )" "  and says so" "$out"

echo "== status: masking and readability =="
"$LOCALRIG" up mlx >/dev/null 2>&1
/usr/bin/python3 - "$BACKENDS" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); d = json.loads(p.read_text())
d["fake"] = {"url": "http://127.0.0.1:1", "model": "m", "auth": "Bearer short11chr"}   # 11 chars
p.write_text(json.dumps(d, indent=2) + "\n")
PY
out="$("$LOCALRIG" status 2>&1)"
check "$( contains "$out" "short11chr" && echo 1 || echo 0 )" \
  "a short API key is masked too (the old mask needed 12+ characters and printed it in full)" "$out"
check "$( contains "$out" "Bearer" && echo 0 || echo 1 )" "  the auth line is still shown, just masked"

echo "== the folders: the new one, else the old one while it alone exists, else the new =="
# agentik-r1 6.3 c17 (state) and c19 (config); AGENTROUTE_STATE_DIR still wins. The router
# address is a dead port, so status asks no router.
X="$TMP/folders"
for m in neither old new; do
  rm -rf "${X:?}"; mkdir -p "$X/config" "$X/state"
  case $m in
    old) mkdir -p "$X/config/agentroute" "$X/state/agentroute" ;;
    new) mkdir -p "$X/config/agentroute" "$X/state/agentroute" \
           "$X/config/agentik/agents/route" "$X/state/agentik-agents/route" ;;
  esac
  out="$(env -u AGENTROUTE_STATE_DIR XDG_CONFIG_HOME="$X/config" XDG_STATE_HOME="$X/state" \
         AGENTROUTE_LISTEN=127.0.0.1:1 "$LOCALRIG" status 2>&1)"
  case $m in
    old) want_c="$X/config/agentroute"; want_s="$X/state/agentroute"; other="$X/state/agentik-agents" ;;
    *) want_c="$X/config/agentik/agents/route"; want_s="$X/state/agentik-agents/route"; other="" ;;
  esac
  check "$( contains "$out" "backends.json ($want_c/backends.json)" && echo 0 || echo 1 )" \
    "$m: backends.json is read from ${want_c#"$X"/}" "$out"
  check "$( [ -d "$want_s" ] && { [ -z "$other" ] || [ ! -e "$other" ]; } && echo 0 || echo 1 )" \
    "$m: the state folder is ${want_s#"$X"/}, and no other is made"
done
out="$(env AGENTROUTE_STATE_DIR="$X/pinned" XDG_CONFIG_HOME="$X/config" XDG_STATE_HOME="$X/state" \
       AGENTROUTE_LISTEN=127.0.0.1:1 "$LOCALRIG" status 2>&1)"
check "$( [ -d "$X/pinned" ] && echo 0 || echo 1 )" "AGENTROUTE_STATE_DIR still wins over both folders"

echo "== status: the router asked is the copy's own bin/agentroute, never PATH's =="
# a-s12: a copy of localrig beside a stub bin/agentroute that prints a marker, a decoy
# agentroute first on PATH printing another; the router and Ollama are dead ports.
OWN="$TMP/own"; mkdir -p "$OWN/bin" "$OWN/decoy"
cp "$LOCALRIG" "$OWN/bin/localrig"
printf '#!/bin/sh\necho "own router saw $*"\n' > "$OWN/bin/agentroute"
printf '#!/bin/sh\necho "decoy router saw $*"\n' > "$OWN/decoy/agentroute"
chmod +x "$OWN/bin/agentroute" "$OWN/decoy/agentroute"
out="$(PATH="$OWN/decoy:$PATH" AGENTROUTE_LISTEN=127.0.0.1:1 LOCALRIG_OLLAMA_URL=http://127.0.0.1:1 \
       "$OWN/bin/localrig" status 2>&1)"
check "$( contains "$out" "router:" && contains "$out" "own router saw --check" && echo 0 || echo 1 )" \
  "status runs the copy's own bin/agentroute --check" "$out"
check "$( contains "$out" "decoy router" && echo 1 || echo 0 )" "  and never PATH's agentroute" "$out"
nopath=$(printf '%s\n' "$PATH" | tr ':' '\n' | while read -r d; do [ -x "$d/agentroute" ] || printf '%s:' "$d"; done)
out="$(PATH="${nopath%:}" AGENTROUTE_LISTEN=127.0.0.1:1 LOCALRIG_OLLAMA_URL=http://127.0.0.1:1 \
       "$OWN/bin/localrig" status 2>&1)"
check "$( contains "$out" "router:" && contains "$out" "own router saw --check" && echo 0 || echo 1 )" \
  "  and asks it when no agentroute is on PATH at all" "$out"

echo "== keys: sops-backed, env-overridable, never printed =="
# The store lives outside the repo ($AGENTIK_AGENTS_SECRETS, else the config home's
# agentik/agents/secrets), so this suite never reads the real one: it builds a throwaway
# age identity and a store of invented values under $TMP, under the rule in .sops.yaml.
want="$(grep -oE "encrypted_regex: '.*'" "$REPO/.sops.yaml" | sed "s/encrypted_regex: '//; s/'$//")"
fake="invented-llama-key-$$"
store=""
if command -v sops >/dev/null 2>&1 && command -v age-keygen >/dev/null 2>&1; then
  age-keygen -o "$TMP/age.key" >/dev/null 2>&1
  recip="$(age-keygen -y "$TMP/age.key" 2>/dev/null)"
  if [ -n "$recip" ] && printf "llama_api_key: '%s'\nunsloth_api_key: ''\nnote: cleartext by design\n" "$fake" \
      | ( cd "$TMP" && sops encrypt --age "$recip" --encrypted-regex "$want" \
            --input-type yaml --output-type yaml /dev/stdin ) > "$TMP/keys.enc.yaml" 2>/dev/null \
      && [ -s "$TMP/keys.enc.yaml" ]; then
    store="$TMP/keys.enc.yaml"
  fi
fi
if [ -n "$store" ]; then
  export SOPS_AGE_KEY_FILE="$TMP/age.key" LOCALRIG_SECRETS_FILE="$store"
  out="$("$LOCALRIG" keys status 2>&1)"; rc=$?
  check "$rc" "keys status runs" "$out"
  check "$( contains "$out" "$fake" && echo 1 || echo 0 )" \
    "keys status does NOT print the key value" "$out"
  check "$( contains "$out" "llama_api_key" && echo 0 || echo 1 )" "  but does name the key and its source"
  check "$( grep -qF "$fake" "$store" && echo 1 || echo 0 )" \
    "the plaintext key is not present in the encrypted file"
  # env beats sops
  src="$(LOCALRIG_LLAMA_KEY=env-override "$LOCALRIG" keys status 2>&1 | awk '/llama_api_key/{print $2}')"
  check "$( [ "$src" = "environment" ] && echo 0 || echo 1 )" \
    "an env var overrides the stored key, and status says so" "source=$src"
  src="$("$LOCALRIG" keys status 2>&1 | awk '/llama_api_key/{print $2}')"
  check "$( [ "$src" = "sops" ] && echo 0 || echo 1 )" "without the env var the source is sops" "source=$src"
  out="$(printf 'x\n' | "$LOCALRIG" keys set 'bad name/../etc' 2>&1)"; rc=$?
  check "$( [ "$rc" != "0" ] && contains "$out" "alphanumeric" && echo 0 || echo 1 )" \
    "keys set rejects a malformed provider name (any well-formed one is allowed by design)" "$out"
  out="$("$LOCALRIG" keys set 2>&1)"; rc=$?
  check "$( [ "$rc" != "0" ] && contains "$out" "usage" && echo 0 || echo 1 )" \
    "keys set with no provider prints usage" "$out"
  out="$("$LOCALRIG" keys nonsense 2>&1)"; rc=$?
  check "$( [ "$rc" != "0" ] && echo 0 || echo 1 )" "an unknown keys subcommand fails" "$out"

  # Two ways this went wrong, both reproduced on 2026-09-05: a key name outside the
  # encrypted_regex is written in the clear, and the regex is baked into each FILE, so
  # editing .sops.yaml does not apply to files that already exist.
  bad=""
  while IFS= read -r line; do
    case "$line" in
      *"ENC[AES256_GCM"*) continue ;;          # encrypted, fine
      *': ""'|*": ''"|*': ') continue ;;       # empty: no secret present, nothing to encrypt
    esac
    bad="$bad ${line%%:*}"
  done < <(grep -E '^[A-Za-z0-9_-]*(_api_key|_key|_token|_secret|_password|_credential):' "$store" || true)
  check "$( [ -z "$bad" ] && echo 0 || echo 1 )" \
    "every credential-shaped value in a store made under .sops.yaml's rule is encrypted" "cleartext:$bad"
  have="$(grep -oE 'encrypted_regex: .*' "$store" | tail -1 | sed 's/encrypted_regex: //')"
  check "$( [ "$have" = "$want" ] && echo 0 || echo 1 )" \
    "  and the store carries .sops.yaml's encrypted_regex (a stale one silently leaks new keys)" \
    "file has '$have', .sops.yaml says '$want'"

  # a newly-named provider key must encrypt without anyone editing .sops.yaml
  cp "$store" "$TMP/newprov.yaml"
  printf 'brand-new-provider-secret\n' | LOCALRIG_SECRETS_FILE="$TMP/newprov.yaml" "$LOCALRIG" keys set somenewprovider >/dev/null 2>&1
  line="$(grep -E '^somenewprovider_api_key:' "$TMP/newprov.yaml" || true)"
  check "$( contains "$line" "ENC[AES256_GCM" && echo 0 || echo 1 )" \
    "a provider nobody listed in advance still gets encrypted" "$line"
  back="$(sops decrypt --extract '["somenewprovider_api_key"]' -- "$TMP/newprov.yaml" 2>/dev/null | tr -d '\r\n')"
  check "$( [ "$back" = "brand-new-provider-secret" ] && echo 0 || echo 1 )" "  and round-trips" "got '$back'"
  unset LOCALRIG_SECRETS_FILE SOPS_AGE_KEY_FILE
else
  check 0 "SKIPPED keys tests (sops or age-keygen unavailable)"
fi

echo "== the key store lives outside the repo =="
# The default store is the secrets directory: $AGENTIK_AGENTS_SECRETS, else the XDG config
# home's agentik/agents/secrets (this suite's XDG_CONFIG_HOME is under $TMP).
out="$("$LOCALRIG" keys status 2>&1)"
check "$( contains "$out" "$XDG_CONFIG_HOME/agentik/agents/secrets/local-backends.sops.yaml" && echo 0 || echo 1 )" \
  "by default the store is read from the config home, not the repo" "$out"
out="$(AGENTIK_AGENTS_SECRETS="$TMP/elsewhere" "$LOCALRIG" keys status 2>&1)"
check "$( contains "$out" "$TMP/elsewhere/local-backends.sops.yaml" && echo 0 || echo 1 )" \
  "  and AGENTIK_AGENTS_SECRETS moves it" "$out"
out="$(AGENTIK_AGENTS_SECRETS="$TMP/elsewhere" "$REPO/bin/claude-api-agent" --key-status 2>&1)"
check "$( contains "$out" "$TMP/elsewhere/anthropic-api-key.sops.yaml" && echo 0 || echo 1 )" \
  "  claude-api-agent reads its key from the same directory" "$out"
tracked="$(cd "$REPO" && git ls-files -- secrets 2>/dev/null)"
check "$( [ -z "$tracked" ] && echo 0 || echo 1 )" "git tracks nothing under secrets/" "$tracked"
# a store or a decrypted copy left in the tree by an old checkout must be impossible to commit
for probe in secrets/local-backends.sops.yaml secrets/zz-spill-probe.yaml; do
  ( cd "$REPO" && git check-ignore -q "$probe" )
  check "$( [ "$?" = "0" ] && echo 0 || echo 1 )" "  .gitignore refuses $probe"
done

echo "== a missing secrets file must not break the lane =="
out="$(LOCALRIG_SECRETS_FILE=$TMP/does-not-exist.yaml "$LOCALRIG" keys status 2>&1)"; rc=$?
check "$rc" "keys status with no secrets file still succeeds" "$out"
check "$( contains "$out" "per-run random" && echo 0 || echo 1 )" \
  "  and says the lane still works without any key setup" "$out"

echo "== claude-local: help and version exit before starting anything =="
out="$("$CLAUDE_LOCAL" --help 2>&1)"; rc=$?
check "$( [ "$rc" = "0" ] && contains "$out" "claude-local" && echo 0 || echo 1 )" \
  "claude-local --help describes claude-local and exits 0 (it used to exec 'claude --help')" "rc=$rc"
check "$( contains "$out" "Remote Control" && echo 0 || echo 1 )" "  and states the Remote Control trade-off"
out="$("$CLAUDE_LOCAL" --version 2>&1)"; rc=$?
check "$( [ "$rc" = "0" ] && contains "$out" "router:" && echo 0 || echo 1 )" \
  "claude-local --version reports its own name and the router version" "rc=$rc out=$out"

echo "== claude-local: the Explore override is built from plugin/agents/local-explore.md =="
# a-s6: a-s4 moved the agents into plugin/. A launcher left reading the old place only warns and
# leaves Explore on the session model, so the override is built here, by the launcher's own
# function with REPO at this tree, and its model is checked.
out="$( eval "$(sed -n '/^explore_agent_json() {$/,/^}$/p' "$CLAUDE_LOCAL")"; explore_agent_json 2>&1 )"; rc=$?
model="$(printf '%s' "$out" | /usr/bin/python3 -c 'import json, sys
e = json.load(sys.stdin)["Explore"]
print(e["model"] if e["prompt"].strip() and e["tools"] else "empty")' 2>/dev/null)"
check "$( [ "$rc" = "0" ] && [ "$model" = "local/default" ] && echo 0 || echo 1 )" \
  "explore_agent_json builds the Explore override from plugin/agents/local-explore.md, on model local/default" \
  "rc=$rc model=${model:-none} ${out##*$'\n'}"

echo "== help, version, and unknown commands =="
for a in --help -h help; do "$LOCALRIG" "$a" >/dev/null 2>&1; check "$?" "localrig $a exits 0"; done
"$LOCALRIG" --version >/dev/null 2>&1; check "$?" "localrig --version exits 0"
"$LOCALRIG" no-such-command >/dev/null 2>&1
check "$( [ "$?" = "2" ] && echo 0 || echo 1 )" "an unknown command exits 2, not 0"
out="$("$LOCALRIG" bogus 2>&1)"; check "$( contains "$out" "--help" && echo 0 || echo 1 )" "  and points at --help" "$out"

gone() {   # gone PID: true once PID has exited (polls up to 3 s)
  local _
  for _ in $(seq 1 30); do kill -0 "$1" 2>/dev/null || return 0; sleep 0.1; done
  return 1
}

echo "== claude-local: refuses to add a second router =="
# The decoy is an `agentroute --serve` this suite starts and stops, so the guard always has a
# router to collide with, whatever else runs on this machine. NOT --help/--version: both exit
# before the router logic. Any other argument reaches the guard, which dies before exec.
mkdir -p "$TMP/decoy/bin"
printf '#!/usr/bin/python3\nimport time\ntime.sleep(600)\n' > "$TMP/decoy/bin/agentroute"
chmod +x "$TMP/decoy/bin/agentroute"
"$TMP/decoy/bin/agentroute" --serve & DECOY_PID=$!
disown "$DECOY_PID"
for _ in $(seq 1 40); do pgrep -f "$TMP/decoy/bin/agentroute --serve" >/dev/null && break; sleep 0.05; done
before="$(pgrep -f 'bin/agentroute --serve' | sort)"
: > "$FAKE_CLAUDE_LOG"
out="$(CLAUDE_LOCAL_NO_PREFLIGHT=1 AGENTROUTE_LISTEN=127.0.0.1:$DEAD "$CLAUDE_LOCAL" --not-a-real-flag 2>&1)"; rc=$?
after="$(pgrep -f 'bin/agentroute --serve' | sort)"
check "$( [ "$rc" != "0" ] && contains "$out" "refusing to start a second router" && echo 0 || echo 1 )" \
  "with a router already running but not answering here, claude-local refuses rather than spawning another" "rc=$rc $out"
check "$( [ ! -s "$FAKE_CLAUDE_LOG" ] && echo 0 || echo 1 )" "  and never reaches claude" "$(cat "$FAKE_CLAUDE_LOG")"
check "$( [ "$before" = "$after" ] && echo 0 || echo 1 )" "  and starts no router of its own" "before: $before; after: $after"
code=$(curl -s -m 1 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$DEAD/api/hello" 2>/dev/null) || code=000
check "$( [ "$code" = "000" ] && echo 0 || echo 1 )" "  and afterwards nothing listens on :$DEAD" "got '$code'"
kill "$DECOY_PID" 2>/dev/null; gone "$DECOY_PID"
check "$?" "  the decoy router is stopped"; DECOY_PID=

echo "== claude-local: a cold start stops the router it started only while it has not answered =="
# A copy of claude-local beside a stub router. The stub writes its pid to $TMP/cold/pids;
# STUB_SERVE=mute makes it never answer; its --check returns STUB_CHECK_RC after sleeping
# STUB_CHECK_SLEEP seconds. The fake pgrep scopes the guard to this stub, so a router the
# developer runs cannot take the refusal branch here (the guard itself is tested above).
# claude-local runs no claude before its exec, so the pre-exec failures are the router's: it
# never answers, or its preflight fails. A router that answered may already serve another
# launcher, so only the first is stopped.
COLD="$TMP/cold"; mkdir -p "$COLD/bin" "$COLD/fakebin"
cp "$CLAUDE_LOCAL" "$COLD/bin/claude-local"
ln -s "$REPO/plugin" "$COLD/plugin"   # the copy builds its Explore override from $REPO/plugin (a-s6)
cat > "$COLD/bin/agentroute" <<'PY'
#!/usr/bin/python3
import http.server, os, sys, time
if sys.argv[1:2] == ["--check"]:
    time.sleep(float(os.environ.get("STUB_CHECK_SLEEP", "0")))
    sys.exit(int(os.environ.get("STUB_CHECK_RC", "0")))
if sys.argv[1:2] == ["--version"]:
    print("stub"); sys.exit(0)
with open(os.environ["STUB_PIDS"], "a") as f:
    f.write("%d\n" % os.getpid())
if os.environ.get("STUB_SERVE") == "mute":
    time.sleep(600); sys.exit(0)
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_HEAD(self):
        self.send_response(200); self.send_header("content-length", "0"); self.end_headers()
    do_GET = do_HEAD
host, port = os.environ["AGENTROUTE_LISTEN"].rsplit(":", 1)
http.server.HTTPServer((host, int(port)), H).serve_forever()
PY
cat > "$COLD/fakebin/pgrep" <<EOF
#!/bin/sh
exec /usr/bin/pgrep -f "$COLD/bin/agentroute --serve"
EOF
chmod +x "$COLD/bin/claude-local" "$COLD/bin/agentroute" "$COLD/fakebin/pgrep"
: > "$COLD/pids"
COLD_PORT=$(/usr/bin/python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
cold() {   # cold ENV=VAL... : run the copy once, new stub pid in $cold_pid, claude's argv in the log
  local n; n=$(wc -l < "$COLD/pids"); : > "$FAKE_CLAUDE_LOG"
  out="$(env "$@" STUB_PIDS="$COLD/pids" AGENTROUTE_LISTEN="127.0.0.1:$COLD_PORT" PATH="$COLD/fakebin:$PATH" \
         "$COLD/bin/claude-local" --not-a-real-flag 2>&1)"; rc=$?
  cold_pid=$(sed -n "$((n+1))p" "$COLD/pids")
}
stop_stubs() {   # between cases: a stub a red run left behind must not answer for the next
  local p; for p in $(stub_router_pids); do kill "$p" 2>/dev/null; gone "$p"; done
}

cold STUB_SERVE=mute
check "$( [ "$rc" != "0" ] && contains "$out" "did not come up" && echo 0 || echo 1 )" \
  "a router that never answers stops claude-local before exec" "rc=$rc $out"
check "$( [ ! -s "$FAKE_CLAUDE_LOG" ] && echo 0 || echo 1 )" "  and claude never runs" "$(cat "$FAKE_CLAUDE_LOG")"
gone "${cold_pid:-0}"; check "$?" "  and the router it started is stopped, not orphaned" "$(ps -o pid,ppid,args -p "${cold_pid:-0}" 2>&1)"
stop_stubs

# Launcher A starts the router, which answers; launcher B, started meanwhile, finds it
# answering and reuses it; then A's preflight fails. The router is B's session's now, so A
# must leave it running (once a router answers, it is never its starter's to stop).
n=$(wc -l < "$COLD/pids"); : > "$FAKE_CLAUDE_LOG"
env STUB_CHECK_RC=1 STUB_CHECK_SLEEP=1.5 STUB_PIDS="$COLD/pids" AGENTROUTE_LISTEN="127.0.0.1:$COLD_PORT" \
  PATH="$COLD/fakebin:$PATH" "$COLD/bin/claude-local" --launcher-a > "$TMP/a.out" 2>&1 & launcher=$!
for _ in $(seq 1 100); do curl -fsS -m 1 -o /dev/null -I "http://127.0.0.1:$COLD_PORT/api/hello" 2>/dev/null && break; sleep 0.05; done
env STUB_PIDS="$COLD/pids" AGENTROUTE_LISTEN="127.0.0.1:$COLD_PORT" PATH="$COLD/fakebin:$PATH" \
  "$COLD/bin/claude-local" --launcher-b >/dev/null 2>&1; rc_b=$?
wait "$launcher"; rc=$?
check "$( [ "$rc" != "0" ] && grep -q 'preflight failed' "$TMP/a.out" && [ "$rc_b" = "2" ] && echo 0 || echo 1 )" \
  "launcher A fails its preflight after launcher B reused the router A started" "A rc=$rc, B rc=$rc_b: $(cat "$TMP/a.out")"
check "$( [ "$(wc -l < "$COLD/pids")" -eq $((n+1)) ] && grep -q -- '--launcher-b' "$FAKE_CLAUDE_LOG" \
          && ! grep -q -- '--launcher-a' "$FAKE_CLAUDE_LOG" && echo 0 || echo 1 )" \
  "  B started no router of its own and reached claude; A never did" "$(cat "$COLD/pids" "$FAKE_CLAUDE_LOG")"
code=$(curl -s -m 1 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$COLD_PORT/api/hello" 2>/dev/null) || code=000
check "$( [ "$code" = "200" ] && echo 0 || echo 1 )" "  and A leaves the router answering under B's session" "got '$code'"
stop_stubs

n=$(wc -l < "$COLD/pids")
env STUB_SERVE=mute STUB_PIDS="$COLD/pids" AGENTROUTE_LISTEN="127.0.0.1:$COLD_PORT" PATH="$COLD/fakebin:$PATH" \
  "$COLD/bin/claude-local" --not-a-real-flag >/dev/null 2>&1 & launcher=$!
for _ in $(seq 1 40); do [ "$(wc -l < "$COLD/pids")" -gt "$n" ] && break; sleep 0.05; done
cold_pid=$(sed -n "$((n+1))p" "$COLD/pids")
kill -TERM "$launcher"; wait "$launcher" 2>/dev/null; rc=$?   # quiet: no job notice
check "$( [ "$rc" = "143" ] && [ -n "$cold_pid" ] && echo 0 || echo 1 )" \
  "a launcher sent SIGTERM while it waits for the router exits 143" "rc=$rc pid=$cold_pid"
gone "${cold_pid:-0}"; check "$?" "  and the router it started is stopped, not orphaned" "$(ps -o pid,ppid,args -p "${cold_pid:-0}" 2>&1)"
stop_stubs

cold STUB_CHECK_RC=0
check "$( [ "$rc" = "2" ] && echo 0 || echo 1 )" "a good cold start execs claude, and claude's exit status is the launcher's" "rc=$rc $out"
check "$( grep -q -- '--not-a-real-flag' "$FAKE_CLAUDE_LOG" && echo 0 || echo 1 )" \
  "  claude gets the caller's arguments unchanged" "$(cat "$FAKE_CLAUDE_LOG")"
check "$( grep -F -- '--agents {"Explore": ' "$FAKE_CLAUDE_LOG" | grep -qF '"model": "local/default"' \
          && ! contains "$out" "could not build the Explore override" && echo 0 || echo 1 )" \
  "  and the Explore override, built from the plugin's agent file, puts Explore on local/default" "$out"
kill -0 "${cold_pid:-0}" 2>/dev/null
check "$?" "  and the router outlives the exec, as designed, even when claude rejects an argument"
[ -n "$cold_pid" ] && kill "$cold_pid" 2>/dev/null; gone "${cold_pid:-0}"
check "$?" "  the stub router is stopped"
code=$(curl -s -m 1 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$COLD_PORT/api/hello" 2>/dev/null) || code=000
check "$( [ "$code" = "000" ] && echo 0 || echo 1 )" "  and afterwards nothing listens on :$COLD_PORT" "got '$code'"

echo
printf '%d passed, %d failed\n' "$passed" "$failed"
[ "$failed" -eq 0 ]
