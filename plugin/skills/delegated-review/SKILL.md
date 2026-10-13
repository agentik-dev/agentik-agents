---
name: delegated-review
description: Delegate read-only code review to headless API-billed agents under a hard budget cap, running in the background. Use when the user asks to review, audit, or find bugs in code "in the background", "in parallel", "with the API key / API budget", "while I keep working", "with claude-fanout", or "have the agents review X" — i.e. when the review should be offloaded to the separate API key rather than done inline on the seat. Do NOT use for applying fixes (the delegates are read-only) or for a quick inline review the user wants answered directly in this session.
allowed-tools: Bash(claude-fanout:*), Bash(claude-costs:*), Bash(claude-api-agent:*), Bash(mktemp:*), Bash(cat:*), Bash(jq:*), Write, Read
---

# Delegated code review

Offload a **read-only** code review to headless `claude --bare` agents billed to
the separate API key, under one hard budget cap, in the background — then report
the confirmed findings. This is the same workflow as the `/claude-code-agents:delegate-review`
slash command; prefer the command when the user types it, and use this skill
when they ask for the same thing in natural language.

The tools (`claude-fanout`, `claude-costs`, `claude-api-agent`) are on `PATH`; if one is
not, say `run make install in the repo` and stop.

**The boundary that governs everything:** a delegate has only `Read`, `Grep`,
`Glob` — no `Bash`, `Edit`, or `Write`. So delegation is for *analysis that
produces a report*, never for doing the work. A delegate cannot run, test, edit,
or verify anything by executing it. If a review needs command output, capture it
to a file first and `--add-dir` its directory — asking a delegate to run
something makes it thrash to a useless, still-billed placeholder.

## Steps

1. **Build a tasks file.** Pick 2–5 independent review dimensions for the target.
   Write a JSON array to a temp file, one `{"label","prompt"}` per dimension;
   each prompt is self-contained (names the exact files to read; asks for
   `file:line` citations), because delegates see none of this conversation and
   cannot execute anything.

2. **Launch in the background** with `run_in_background`, so the user keeps
   working and is notified on completion:

   ```
   claude-fanout --budget-usd <N> --profile review -j <dimensions> \
     --id <recognisable-slug> --phase review \
     --add-dir <target-dir> --tasks <tempfile> --out <tempdir>/run --json
   ```

   Budget: measured `review` shards run ~$0.20–$0.71; default to dimensions ×
   $1.00 unless told otherwise. `--add-dir` every directory the prompts read.
   **Budget a dimension by how many files it fans over, not evenly.** A shard
   that must cross-check many files — a docs-consistency pass, a "trace every
   caller" hunt, a whole-package security review — burns far more turns (the
   real cost) than a single-file correctness check, and at a flat per-shard cap
   it is the one that budget-dies and returns *nothing* (measured twice this
   corpus: a docs shard at $1 and a token-security shard at $1.32, both wasted).
   Give the broad dimension 2–3× the cap, split it into narrower shards (one
   named doc vs one named code file), or run it solo — never let the widest
   dimension share the same cap as a one-file check.

3. **On completion, read `<tempdir>/run/fanout.json`** and report findings from
   `ok` shards (grouped by severity, `file:line — issue`); note how many shards
   were `degenerate`/`error`/`unparseable` and that their spend was wasted;
   report `spent_usd` (flag `spent_usd_is_upper_bound`); and surface any
   `denied_tools` as a sign a delegate hit its read-only limit.

4. **Verify before presenting as fact.** Confirm each finding against the cited
   code yourself before stating it plainly; mark anything unconfirmed as
   "reported, unverified". A delegate's finding is a lead, not a fact.

Never apply fixes here — reviewing is the deliverable. Use `claude-costs` (or the
`/claude-code-agents:delegate-costs` command) afterward to see what it cost.
