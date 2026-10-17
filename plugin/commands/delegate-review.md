---
allowed-tools: Bash(agentik-agents *), Bash(mktemp:*), Bash(cat:*), Bash(jq:*), Write, Read
description: Delegate a read-only code review to headless API-billed agents under a hard budget cap, in the background
disable-model-invocation: false
---

Delegate a read-only code review of `$ARGUMENTS` to headless `claude --bare`
agents (billed to the separate API key via `agentik-agents fanout`), running in the
background under one hard budget cap, then report the confirmed findings.

`$ARGUMENTS` is what to review — one or more file paths, a directory, or a short
description of the change. If it is empty, review the current git diff
(`git diff` / `git diff --staged`), and if that is empty, ask the user what to
review instead of guessing.

Read `${CLAUDE_PLUGIN_ROOT}/skills/delegated-review/SKILL.md` and follow its five steps
precisely, with `$ARGUMENTS` as the target. If you cannot read that file, stop and say so.

Do **not** apply any fix as part of this command — profiles are read-only and
the delegates cannot edit anyway. Reviewing is the deliverable; fixing is a
separate, explicit step the user asks for.
