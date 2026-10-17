# agentik-agents — install / test targets.
#
# The tools are sh, bash and python3; there is nothing to compile. `install` links the
# dispatcher, agentik-agents, and the eight tools it runs onto PATH (~/.local/bin, where
# `claude` already is), and copies the vendored agentik front door there (agentik-r1 D3).
# It is idempotent and reversible, and it only ever touches $(BINDIR) -- never anything
# else outside this repo. The eight keep their names as aliases until 2026-12-31.

SHELL := /bin/bash
REPO  := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
# ~/.local/bin is already on PATH here (claude itself lives there); override with BINDIR=
BINDIR ?= $(HOME)/.local/bin
TOOLS := claude-api-agent claude-fanout claude-costs agentroute claude-local localrig claude-agents queue-mvp
LINKS := agentik-agents $(TOOLS)
# scripts/doclint is the session plugin's doc gate, copied byte for byte (conventions §6);
# sync does not carry it, so `doclint` checks it against this pin first (a-s8).
DOCLINT_SHA = 26eaf2c84aadb822f8d63a0257b063afcc0ba6d9bbcf1d2d856abe4c6388341f

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sed 's/:.*## /\t/' | sort | awk -F'\t' '{printf "  %-12s %s\n", $$1, $$2}'

.PHONY: install
install: ## Symlink agentik-agents and its tools into BINDIR (default ~/.local/bin), copy agentik there; idempotent
	@mkdir -p -- "$(BINDIR)"
	@for t in $(LINKS); do \
	  ln -sfn -- "$(REPO)/bin/$$t" "$(BINDIR)/$$t" \
	    && printf '  linked %s -> %s\n' "$(BINDIR)/$$t" "$(REPO)/bin/$$t"; \
	done
	@tmp="$(BINDIR)/.agentik.$$$$" \
	  && cp -- "$(REPO)/scripts/agentik" "$$tmp" && chmod 0755 "$$tmp" \
	  && mv -f -- "$$tmp" "$(BINDIR)/agentik" \
	  && printf '  copied %s (the agentik front door, vendored)\n' "$(BINDIR)/agentik"
	@case ":$$PATH:" in *":$(BINDIR):"*) : ;; \
	  *) printf '  NOTE: %s is not on PATH; add it to use the bare command names.\n' "$(BINDIR)" ;; \
	esac

.PHONY: uninstall
uninstall: ## Remove the symlinks from BINDIR (only if they point back here); agentik stays, other tools install it too
	@for t in $(LINKS); do \
	  link="$(BINDIR)/$$t"; \
	  if [ -L "$$link" ] && [ "$$(readlink -f -- "$$link")" = "$(REPO)/bin/$$t" ]; then \
	    rm -- "$$link" && printf '  removed %s\n' "$$link"; \
	  else \
	    printf '  skipped %s (not our symlink)\n' "$$link"; \
	  fi; \
	done

.PHONY: test
test: ## Run every test suite (stub-driven ones spend nothing; pinning needs claude)
	@fail=0; \
	for t in tests/test-dispatch.sh tests/test-arg-handling.sh tests/test-run-path.sh tests/test-flag-pinning.sh tests/test-rig.sh; do \
	  printf '=== %s ===\n' "$$t"; bash "$$t" || fail=1; \
	done; \
	for t in tests/test-fanout.py tests/test-costs.py tests/test-route.py tests/test-status.py tests/test-apirun.py tests/test-hygiene.py; do \
	  printf '=== %s ===\n' "$$t"; python3 "$$t" || fail=1; \
	done; \
	exit $$fail

.PHONY: check check-unlocked lint doclint hygiene validate
# conventions §5: one gate per tree (.check.lock), walled at 840 s (inside the relay's 900),
# held off above load 4 x cores. A last stderr line `bounded: stop: lock|load|wall` is unrun,
# never red. scripts/{agentik,hygiene,bounded} are vendored from agentik-commons by its
# scripts/sync, which writes scripts/vendored.sha256; scripts/doclint is the session
# plugin's, pinned by DOCLINT_SHA above; never edit any of the four here.
check: ## The gate: check-unlocked under scripts/bounded (lock, 840 s wall, load 4)
	scripts/bounded --lock .check.lock --wall 840 --load 4 -- $(MAKE) check-unlocked

check-unlocked: test lint doclint hygiene validate ## The gate unbounded: test, lint, doclint, hygiene, validate

lint: ## Syntax-check every tool (sh, bash, python)
	@sh -n bin/agentik-agents && echo "  bin/agentik-agents: sh syntax OK"
	@bash -n bin/claude-api-agent && echo "  bin/claude-api-agent: bash syntax OK"
	@bash -n bin/claude-local && echo "  bin/claude-local: bash syntax OK"
	@bash -n bin/localrig && echo "  bin/localrig: bash syntax OK"
	@python3 -c "import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]" \
	  bin/claude-fanout bin/claude-costs bin/agentroute bin/claude-agents bin/queue-mvp \
	  && echo "  python tools: syntax OK"

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

validate: ## claude plugin validate on plugin/, walled at 60 s (spends nothing); exit 2 when no claude
	@command -v claude >/dev/null 2>&1 || { echo "validate: unrun, no claude on PATH"; exit 2; }
	scripts/bounded --wall 60 -- claude plugin validate plugin/

.PHONY: plugin-dev
plugin-dev: ## Print the command to load the plugin for ONE session (no persistent change)
	@printf 'Load /agents:delegate-review and /agents:delegate-costs for one session with:\n\n'
	@printf '  claude --plugin-dir %s\n\n' "$(REPO)/plugin"

.PHONY: plugin-install
plugin-install: ## Print the lines that install the plugin persistently (Claude Code global config)
	@printf 'Persistent install (adds the agentik marketplace, then installs):\n\n'
	@printf '  claude plugin marketplace add agentik-dev/agentik-commons\n'
	@printf '  claude plugin install agents@agentik\n\n'
	@printf 'These mutate ~/.claude global plugin config, so run them yourself.\n'
	@printf 'Verify the manifest first with: claude plugin validate %s\n' "$(REPO)/plugin"

.PHONY: doctor
doctor: ## Report install/key/proxy/local-lane readiness (spends nothing): agentik agents doctor
	@bin/agentik-agents doctor
