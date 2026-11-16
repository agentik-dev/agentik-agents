---
description: "Give the terminal the CLI: freeze this plugin's code and write the agentik-agents launcher"
argument-hint: "[--prefix DIR]"
disable-model-invocation: true
allowed-tools: [Bash(*/bin/agentik-agents install-cli*)]
---

!`${CLAUDE_PLUGIN_ROOT}/bin/agentik-agents install-cli $ARGUMENTS`

The plugin's own launcher runs this, never one on PATH: the one on PATH may be the old one or
the broken one this repairs. It freezes the plugin's lib/ under the user's
.local/share/agentik-agents/, writes .local/bin/agentik-agents and the agentik door, refreshes
the links for the old names agentroute, claude-agents, claude-local and localrig only where they
already stand (a new machine gets none; a file of that name that is not a link it leaves, and
names), and prunes old trees no live process names. Report the lines it printed, or its error and
exit code. Do not retry unless the user asks.
