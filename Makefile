# claude-code-agents — install / test targets.
#
# The tools are bash + python3; there is nothing to compile. `install` just
# links the commands onto PATH (~/.local/bin, where `claude` already is); it is idempotent and reversible, and it
# only ever touches $(BINDIR) -- never anything else outside this repo.

SHELL := /bin/bash
REPO  := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
# ~/.local/bin is already on PATH here (claude itself lives there); override with BINDIR=
BINDIR ?= $(HOME)/.local/bin
TOOLS := claude-api-agent claude-fanout claude-costs agentroute claude-local localrig claude-agents queue-mvp

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sed 's/:.*## /\t/' | sort | awk -F'\t' '{printf "  %-12s %s\n", $$1, $$2}'

.PHONY: install
install: ## Symlink the tools into BINDIR (default ~/.local/bin); idempotent
	@mkdir -p -- "$(BINDIR)"
	@for t in $(TOOLS); do \
	  ln -sfn -- "$(REPO)/bin/$$t" "$(BINDIR)/$$t" \
	    && printf '  linked %s -> %s\n' "$(BINDIR)/$$t" "$(REPO)/bin/$$t"; \
	done
	@case ":$$PATH:" in *":$(BINDIR):"*) : ;; \
	  *) printf '  NOTE: %s is not on PATH; add it to use the bare command names.\n' "$(BINDIR)" ;; \
	esac

.PHONY: uninstall
uninstall: ## Remove the symlinks from BINDIR (only if they point back here)
	@for t in $(TOOLS); do \
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
	for t in tests/test-arg-handling.sh tests/test-run-path.sh tests/test-flag-pinning.sh tests/test-localrig.sh; do \
	  printf '=== %s ===\n' "$$t"; bash "$$t" || fail=1; \
	done; \
	for t in tests/test-fanout.py tests/test-costs.py tests/test-agentroute.py tests/test-status.py tests/test-apirun.py tests/test-hygiene.py; do \
	  printf '=== %s ===\n' "$$t"; python3 "$$t" || fail=1; \
	done; \
	exit $$fail

.PHONY: check check-unlocked
# conventions §5: one gate per tree (.check.lock), walled at 840 s (inside the relay's 900),
# held off above load 4 x cores. A last stderr line `bounded: stop: lock|load|wall` is unrun,
# never red. scripts/bounded is byte-identical to claude-code-session's; never edit it here.
check: ## The gate: check-unlocked under scripts/bounded (lock, 840 s wall, load 4)
	scripts/bounded --lock .check.lock --wall 840 --load 4 -- $(MAKE) check-unlocked

check-unlocked: ## The gate unbounded: syntax-check every tool, every test suite, then hygiene
	@bash -n bin/claude-api-agent && echo "  bin/claude-api-agent: bash syntax OK"
	@bash -n bin/claude-local && echo "  bin/claude-local: bash syntax OK"
	@bash -n bin/localrig && echo "  bin/localrig: bash syntax OK"
	@python3 -c "import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]" \
	  bin/claude-fanout bin/claude-costs bin/agentroute bin/claude-agents bin/queue-mvp \
	  && echo "  python tools: syntax OK"
	@$(MAKE) --no-print-directory test
	@$(MAKE) --no-print-directory hygiene

.PHONY: hygiene
# conventions §6: scripts/hygiene is byte-identical to agentik-session's; never edit it here.
# It scans for the generic groups in the file and the owner's terms in the private list kept
# outside the repo ($$AGENTIK_HYGIENE_PRIVATE, else ~/.config/agentik/hygiene-private.tsv).
hygiene: ## The public-hygiene scan (conventions §6): counts only, exit 2 on a hit outside .hygiene-allow
	scripts/hygiene

.PHONY: plugin-dev
plugin-dev: ## Print the command to load the plugin for ONE session (no persistent change)
	@printf 'Load /delegate-review and /delegate-costs for one session with:\n\n'
	@printf '  claude --plugin-dir %s\n\n' "$(REPO)/plugin"

.PHONY: plugin-install
plugin-install: ## Register + install the plugin persistently (Claude Code global config)
	@printf 'Persistent install (registers a local marketplace, then installs):\n\n'
	@printf '  claude plugin marketplace add %s\n' "$(REPO)"
	@printf '  claude plugin install claude-code-agents@claude-code-agents\n\n'
	@printf 'These mutate ~/.claude global plugin config, so run them yourself.\n'
	@printf 'Verify the manifest first with: claude plugin validate %s\n' "$(REPO)/plugin"

.PHONY: doctor
doctor: ## Report install/key/proxy/local-lane readiness (spends nothing)
	@for t in $(TOOLS); do \
	  p="$$(command -v $$t 2>/dev/null)"; \
	  printf '  %-18s %s\n' "$$t" "$${p:-NOT ON PATH}"; \
	done
	@echo ""
	@echo "  API lane:"
	@bin/claude-api-agent --key-status 2>&1 | sed 's/^/    /' || true
	@echo ""
	@echo "  Local lane (design/01):"
	@bin/agentroute --check 2>&1 | sed 's/^/    /' || true
	@echo ""
	@echo "  doctor reports; it does not gate. For a script, use the tool that returns a"
	@echo "  status: 'agentroute --check' exits non-zero on a FAIL row."
