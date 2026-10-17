---
allowed-tools: Bash(agentik-agents *), Bash(echo:*), Bash(tail:*), Agent, Read
description: Run a task on the LOCAL model (free, seat untouched) through the plugin's local-* agents, after checking this session is routed through the local router
disable-model-invocation: false
---

Run `$ARGUMENTS` on the local model by delegating it to one of this plugin's `local-*`
agents. This is the deterministic entry point for "use my local LLM": you type it, and
the steps happen in order. If `$ARGUMENTS` is empty, ask what to run locally.

Read `${CLAUDE_PLUGIN_ROOT}/skills/local-delegation/SKILL.md` and follow its six steps
precisely, with `$ARGUMENTS` as the task; your reply begins with its preflight line. If
you cannot read that file, stop and say so.

**If you cannot run the preflight at all** (Bash denied, tool unavailable), or it does not
pass, stop there: do **not** do the task yourself with Read/Grep and do **not** delegate
to a Claude model instead — the user asked for the local lane, and silently substituting
defeats the point of the command.
