# agentik-agents — install / test targets.
#
# The tools are sh, bash and python3; there is nothing to compile. `install` links the
# dispatcher, agentik-agents, and the four tools it runs onto PATH (~/.local/bin, where
# `claude` already is), and copies the vendored agentik front door there (agentik-r1 D3).
# It is idempotent and reversible, and it only ever touches $(PFX)/bin and its share -- never
# anything else outside this repo. The four keep their names as aliases until 2026-12-31.

SHELL := /bin/bash
REPO  := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
# The interpreter pin (portfolio entry 26, a-s9): .python-version's 3.12.7, resolved once as
# agentik-relay's Makefile does, then first on PATH as agentik-session's puts its venv: under
# make every `env python3` (the tools, scripts/bounded, the suites' children) is the pin,
# never pyenv's shim. Outside make a caller's python3 is its own; the floor is 3.9.
PY := $(shell pyenv which python3 2>/dev/null || command -v python3)
export PATH := $(dir $(PY)):$(PATH)
# a-s10: `test` names the interpreter it runs first (F2), with `pin: absent` when $(PY) is
# not .python-version's; then reruns the stdlib suites under Apple's python3, the 3.9 floor
# (F4), which the pin alone never exercises: test-route and test-status run their tools under
# their own interpreter, test-rig the bash tools' inline `python3` under a
# temp link first on PATH. PIN is read as pyenv reads the file: the first word of the first line
# that is not blank or a comment, CRs dropped; the compare is string equality, so any 3.12.7 is it.
PIN   := $(shell awk '{ gsub(/\r/, "") } $$1 != "" && $$1 !~ /^\#/ { print $$1; exit }' $(REPO)/.python-version 2>/dev/null)
PYV   := $(shell $(PY) -c 'import platform; print(platform.python_version())' 2>/dev/null)
FLOOR := /usr/bin/python3
ifeq ($(PIN),)
PYNOTE := (pin: absent; $(if $(wildcard $(REPO)/.python-version),.python-version names no version,no .python-version))
else ifeq ($(PYV),$(PIN))
PYNOTE := (pin: $(PIN))
else
PYNOTE := (pin: absent; .python-version says $(PIN))
endif
# install-cli's root (a-s18): PREFIX defaults to $(HOME)/.local, so HOME or PREFIX aims install
# and uninstall at a temp home; ~/.local/bin is already on PATH here (claude itself lives there).
# PREFIX reaches the recipes through the environment, and PFX_SH sets the shell's $pfx to it as
# install-cli reads it (os.path.abspath: no trailing or doubled slash, no . or ..), so uninstall
# judges by the paths install-cli wrote (a1 F2); never make's $(abspath), which splits a path at
# its spaces (a2 F1). Every use is quoted. install-cli writes into $pfx/bin and takes no bin dir
# of its own, so there is no BINDIR: `install` refuses one given.
PREFIX ?= $(HOME)/.local
export PREFIX
ABSPATH = $(FLOOR) -I -c 'import os, sys; print(os.path.abspath(sys.argv[1]))'
REALPATH = $(FLOOR) -I -c 'import os, sys; print(os.path.realpath(sys.argv[1]))'
PFX_SH  = pfx="$$($(ABSPATH) "$$PREFIX")" || exit 2; bin="$$pfx/bin"; share="$$pfx/share/agentik-agents"
TOOLS := agentroute claude-local localrig claude-agents
# The API lane's tools, gone with packet a-s17: a link of theirs that still points into this
# checkout would dangle, so install and uninstall remove it and touch no other file.
RETIRED := claude-api-agent claude-fanout claude-costs queue-mvp
# scripts/doclint is the session plugin's doc gate, copied byte for byte (conventions §6);
# sync does not carry it, so `doclint` checks it against this pin first (a-s8).
DOCLINT_SHA = 26eaf2c84aadb822f8d63a0257b063afcc0ba6d9bbcf1d2d856abe4c6388341f
# make readme's renderer: the newest installed respeak, under either marketplace name, and
# its python (PyYAML) from pyenv. Both are read only by the readme recipe.
RESPEAK_RENDER ?= $(shell for f in $(HOME)/.claude/plugins/cache/*/respeak/*/scripts/respeak-render.sh; do \
	v=$${f%/scripts/*}; echo "$${v\#\#*/} $$f"; done | sort -V | tail -1 | cut -d' ' -f2-)
RESPEAK_PYTHON ?= $(shell { pyenv prefix agentik-respeak || pyenv prefix claude-code-respeak; } 2>/dev/null)/bin/python3

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sed 's/:.*## /\t/' | sort | awk -F'\t' '{printf "  %-12s %s\n", $$1, $$2}'

.PHONY: install
install: ## Refuse a dirty tree, then the plugin's install-cli under PREFIX (default ~/.local): the launcher, the agentik door, the old names' links into a frozen tree
	@if [ "$(origin BINDIR)" = "command line" ]; then \
	  echo "install: refused, BINDIR is not honoured: install-cli writes into PREFIX/bin; set PREFIX" >&2; exit 2; fi
	@if [ -n "$$(git status --porcelain 2>/dev/null)" ] || ! git rev-parse --verify --quiet HEAD >/dev/null; then \
	  echo "install: refused, the tree is dirty or has no HEAD; commit first" >&2; exit 2; fi
	@$(PFX_SH); plugin/bin/agentik-agents install-cli --prefix "$$pfx"
	@$(MAKE) --no-print-directory unlink-retired
	@$(PFX_SH); case ":$$PATH:" in *":$$bin:"*) : ;; \
	  *) printf '  NOTE: %s is not on PATH; add it to use the bare command names.\n' "$$bin" ;; \
	esac

.PHONY: uninstall
uninstall: ## Remove what install-cli wrote under PREFIX: its launcher, the old names' links that point into its share, then the share once the launcher is gone and it resolves under PREFIX; the agentik door stays, other tools install it too
	@if [ "$(origin BINDIR)" = "command line" ]; then \
	  echo "uninstall: refused, BINDIR is not honoured: install-cli writes into PREFIX/bin; set PREFIX" >&2; exit 2; fi
	@$(MAKE) --no-print-directory unlink-retired
	@$(PFX_SH); l="$$bin/agentik-agents"; gone=1; \
	if [ -f "$$l" ] && [ ! -L "$$l" ] && grep -qF -e "TREE=$$share/" -e "TREE='$$share/" "$$l"; then \
	  rm -- "$$l" && printf '  removed %s\n' "$$l" || gone=; \
	elif [ -e "$$l" ] || [ -L "$$l" ]; then gone=; \
	  printf '  skipped %s (not the launcher install-cli wrote)\n' "$$l"; fi; \
	for t in $(TOOLS); do \
	  link="$$bin/$$t"; \
	  case "$$(readlink -- "$$link" 2>/dev/null)" in \
	  "$$share"/*) rm -- "$$link" && printf '  removed %s\n' "$$link" ;; \
	  *) printf '  skipped %s (not a link into %s)\n' "$$link" "$$share" ;; \
	  esac; \
	done; \
	if [ -d "$$share" ] && [ ! -L "$$share" ]; then \
	  real="$$($(REALPATH) "$$share")" && want="$$($(REALPATH) "$$pfx")/share/agentik-agents" || exit 2; \
	  if [ "$$real" != "$$want" ]; then \
	    printf 'uninstall: %s stays: it resolves to %s, not under PREFIX %s\n' "$$share" "$$real" "$$want" >&2; exit 2; \
	  elif [ -n "$$gone" ]; then rm -rf -- "$$share" && printf '  removed %s\n' "$$share"; \
	  else printf 'uninstall: %s stays: %s is not the launcher install-cli wrote, and may run from it\n' "$$share" "$$l" >&2; exit 2; fi; \
	fi

# A retired tool's link goes only when it is a symlink whose target is this checkout's bin/;
# readlink without -f, since the target no longer exists.
.PHONY: unlink-retired
unlink-retired:
	@$(PFX_SH); for t in $(RETIRED); do \
	  link="$$bin/$$t"; \
	  if [ -L "$$link" ] && [ "$$(readlink -- "$$link")" = "$(REPO)/bin/$$t" ]; then \
	    rm -- "$$link" && printf '  removed %s (retired)\n' "$$link"; \
	  fi; \
	done

.PHONY: test
test: ## Run every test suite (stub-driven, they spend nothing), then the 3.9 floor's reruns
	@printf '%s\n' 'python3: $(PY) $(PYV) $(PYNOTE)'
	@fail=0; floor=; trap '[ -z "$$floor" ] || rm -rf -- "$${floor:?}"' EXIT; \
	for t in tests/test-dispatch.sh tests/test-rig.sh tests/test-readme.sh; do \
	  printf '=== %s ===\n' "$$t"; bash "$$t" || fail=1; \
	done; \
	for t in tests/test-route.py tests/test-status.py tests/test-hygiene.py tests/test-bare-machine.py; do \
	  printf '=== %s ===\n' "$$t"; $(PY) "$$t" || fail=1; \
	done; \
	if $(FLOOR) -c '' 2>/dev/null; then \
	  for t in tests/test-route.py tests/test-status.py; do \
	    printf '=== %s (the 3.9 floor) ===\n' "$$t"; $(FLOOR) "$$t" || fail=1; \
	  done; \
	  printf '=== %s (the 3.9 floor) ===\n' tests/test-rig.sh; \
	  if floor=$$(mktemp -d) && ln -s $(FLOOR) "$$floor/python3"; then \
	    PATH="$$floor:$$PATH" bash tests/test-rig.sh || fail=1; \
	  else echo "the 3.9 floor: no temp python3 link"; fail=1; fi; \
	else echo "skip: the 3.9 floor"; fi; \
	exit $$fail

.PHONY: check check-unlocked lint doclint hygiene validate readme
# conventions §5: one gate per tree (.check.lock), walled at 840 s (inside the relay's 900),
# held off above load 4 x cores. A last stderr line `bounded: stop: lock|load|wall` is unrun,
# never red. scripts/{agentik,hygiene,bounded} are vendored from agentik-commons by its
# scripts/sync, which writes scripts/vendored.sha256; scripts/doclint is the session
# plugin's, pinned by DOCLINT_SHA above; never edit any of the four here.
check: ## The gate: check-unlocked under scripts/bounded (lock, 840 s wall, load 4)
	scripts/bounded --lock .check.lock --wall 840 --load 4 -- $(MAKE) check-unlocked

check-unlocked: test lint doclint hygiene plugin-version-check validate ## The gate unbounded: test, lint, doclint, hygiene, validate, README freshness
	@if [ ! -f design/readme/source.md ]; then echo "readme: skipped, absent design/readme/source.md"; \
	elif shasum -c --status design/readme/rendered.sha256 2>/dev/null; then echo "readme: fresh"; \
	else echo "readme: stale, run make readme"; exit 2; fi

lint: ## Syntax-check every tool (sh, bash, python)
	@sh -n plugin/lib/agentik-agents && echo "  plugin/lib/agentik-agents: sh syntax OK"
	@bash -n plugin/lib/claude-local && echo "  plugin/lib/claude-local: bash syntax OK"
	@bash -n plugin/lib/localrig && echo "  plugin/lib/localrig: bash syntax OK"
	@$(PY) -c "import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]" \
	  plugin/lib/agentroute plugin/lib/claude-agents plugin/lib/agentik-agents.py plugin/lib/agents_install.py \
	  && echo "  python tools: syntax OK"
	@bash -n scripts/readme-render && echo "  scripts/readme-render: bash syntax OK"

doclint: ## The doc gate (conventions §5): scripts/doclint against DOCLINT_SHA, then the script
	@printf '%s  scripts/doclint\n' '$(DOCLINT_SHA)' | shasum -a 256 -c --status - \
	  || { echo "doclint: scripts/doclint is not DOCLINT_SHA; copy agentik-session's again" >&2; exit 2; }
	scripts/doclint

# conventions §6: scripts/hygiene is vendored from agentik-commons; never edit it here.
# It scans for the generic groups in the file and the owner's terms in the private list kept
# outside the repo ($$AGENTIK_HYGIENE_PRIVATE, else ~/.config/agentik/hygiene-private.tsv).
hygiene: ## The vendored copies' sums, then the public-hygiene scan (conventions §5, §6): exit 1 on a hit outside .hygiene-allow
	@shasum -a 256 -c --status scripts/vendored.sha256 \
	  || { shasum -a 256 -c scripts/vendored.sha256; exit 2; }
	@echo "  scripts/vendored.sha256: vendored copies OK"
	scripts/hygiene

.PHONY: plugin-version-check
plugin-version-check: ## The plugin-version check (GUIDE §7), under the pin: exit 1 when a file under plugin/ changed after plugin.json's version last moved
	PYTHONDONTWRITEBYTECODE=1 $(PY) scripts/plugin-version-check

readme: ## Render README.md from design/readme/source.md through respeak, technical mode (scripts/readme-render, walled at 2000 s: its budget)
	RESPEAK_RENDER="$(RESPEAK_RENDER)" RESPEAK_PYTHON="$(RESPEAK_PYTHON)" scripts/bounded --wall 2000 --load 4 -- scripts/readme-render

validate: ## claude plugin validate on plugin/, walled at 60 s (spends nothing); exit 2 when no claude
	@command -v claude >/dev/null 2>&1 || { echo "validate: unrun, no claude on PATH"; exit 2; }
	scripts/bounded --wall 60 -- claude plugin validate plugin/

.PHONY: plugin-dev
plugin-dev: ## Print the command to load the plugin for ONE session (no persistent change)
	@printf 'Load /agents:status and /agents:delegate-local for one session with:\n\n'
	@printf '  claude --plugin-dir %s\n\n' "$(REPO)/plugin"

.PHONY: plugin-install
plugin-install: ## Print the lines that install the plugin persistently (Claude Code global config)
	@printf 'Persistent install (adds the agentik marketplace, then installs):\n\n'
	@printf '  claude plugin marketplace add agentik-dev/agentik-commons\n'
	@printf '  claude plugin install agents@agentik\n\n'
	@printf 'These mutate ~/.claude global plugin config, so run them yourself.\n'
	@printf 'Verify the manifest first with: claude plugin validate %s\n' "$(REPO)/plugin"

.PHONY: doctor
doctor: ## Report install and local-lane readiness (spends nothing): agentik agents doctor
	@plugin/lib/agentik-agents doctor
