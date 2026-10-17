#!/bin/bash
# test-readme.sh: scripts/readme-render (make readme's script) against fakes in a temp repo
# (a-s8): a fake renderer, a fake verifier and a fake python, so it spends nothing, needs
# no network and no claude, and writes only under its temp dir. Each case checks the exit,
# and each failure leaves README.md as it was, no sidecar and no temp file.
# bash 3.2 compatible (macOS default).
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REPO/scripts/readme-render"
D="$(mktemp -d)" || exit 2
trap 'rm -rf "$D"' EXIT
pass=0; fail=0
check() { if [ "$2" = 0 ]; then pass=$((pass + 1)); else fail=$((fail + 1)); echo "FAIL $1"; fi; }

# The fakes. The renderer logs the helper marks it was given, then exits $FAKE_RENDER_RC
# or writes its --out; the verifier exits $FAKE_VERIFY_RC; the python passes the PyYAML
# probe (-c) and runs the verifier with bash.
FAKES="$D/fakes/scripts"; mkdir -p "$FAKES"
cat > "$FAKES/respeak-render.sh" <<'EOF'
#!/bin/bash
out=
while [ $# -gt 0 ]; do case "$1" in --out) out="$2"; shift 2 ;; *) shift ;; esac; done
echo "depth=${CLAUDE_SESSION_DEPTH:-} helper=${CLAUDE_SESSION_HELPER:-}" > "$FAKE_LOG"
[ "${FAKE_RENDER_RC:-0}" = 0 ] || exit "$FAKE_RENDER_RC"
printf '# rendered\n\nThe fake renderer wrote this.\n' > "$out"
EOF
printf 'exit "${FAKE_VERIFY_RC:-0}"\n' > "$FAKES/respeak-verify-edit.py"
printf '#!/bin/bash\n[ "$1" = -c ] && exit 0\nexec /bin/bash "$@"\n' > "$D/python"
chmod 755 "$FAKES/respeak-render.sh" "$D/python"

n=0
fresh() {  # a new temp repo R: the source, the contract, the old README
  n=$((n + 1)); R="$D/repo$n"; mkdir -p "$R/design/readme"
  printf '# source\n' > "$R/design/readme/source.md"
  printf 'contract\n' > "$R/design/readme/contract.txt"
  printf '# old README\n' > "$R/README.md"
}
run() {  # the script on R with the fakes, plus the caller's assignments; sets rc
  env -u RESPEAK_RENDER_CMD CLAUDE_SESSION_DEPTH=0 RESPEAK_RENDER="$FAKES/respeak-render.sh" \
    RESPEAK_PYTHON="$D/python" FAKE_LOG="$R/.fake-log" "$@" "$SCRIPT" --repo "$R" > "$D/out" 2>&1
  rc=$?
}
untouched() {  # README as it was, no sidecar, no temp file left
  [ "$(cat "$R/README.md")" = "# old README" ] && [ ! -e "$R/design/readme/rendered.sha256" ] &&
    ! ls "$R"/.readme-render.* >/dev/null 2>&1
}

# no renderer: exit 2, naming the install line, nothing written
fresh; run RESPEAK_RENDER=
check "no renderer exits 2 (got $rc)" $([ "$rc" = 2 ]; echo $?)
check "no renderer names the install line" $(grep -q 'claude plugin install respeak@agentik' "$D/out"; echo $?)
check "no renderer leaves README" $(untouched; echo $?)

# a render: exit 0, the fake's README, a sidecar that shasum -c passes, the helper marks
fresh; run
check "a render exits 0 (got $rc)" $([ "$rc" = 0 ]; echo $?)
check "a render writes the fake's README" $(grep -q 'The fake renderer wrote this.' "$R/README.md"; echo $?)
check "a render's sidecar passes shasum -c" $(cd "$R" && shasum -a 256 -c --status design/readme/rendered.sha256; echo $?)
check "the renderer runs one level down, marked a helper" $(grep -q '^depth=1 helper=1$' "$R/.fake-log"; echo $?)
check "a render leaves no temp file" $(! ls "$R"/.readme-render.* >/dev/null 2>&1; echo $?)

# the renderer's 1 (the style gate): 1; its other exits: 2
fresh; run FAKE_RENDER_RC=1
check "the renderer's 1 exits 1 (got $rc)" $([ "$rc" = 1 ]; echo $?)
check "the renderer's 1 leaves README" $(untouched; echo $?)
fresh; run FAKE_RENDER_RC=3
check "the renderer's 3 exits 2 (got $rc)" $([ "$rc" = 2 ]; echo $?)
check "the renderer's 3 leaves README" $(untouched; echo $?)

# the verifier's no: 2
fresh; run FAKE_VERIFY_RC=1
check "the verifier's no exits 2 (got $rc)" $([ "$rc" = 2 ]; echo $?)
check "the verifier's no leaves README" $(untouched; echo $?)

# CLAUDE_SESSION_DEPTH=2: 2 before any write; the renderer never runs
fresh; run CLAUDE_SESSION_DEPTH=2
check "depth 2 exits 2 (got $rc)" $([ "$rc" = 2 ]; echo $?)
check "depth 2 never runs the renderer" $([ ! -e "$R/.fake-log" ]; echo $?)
check "depth 2 leaves README" $(untouched; echo $?)

printf 'test-readme: %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" = 0 ]
