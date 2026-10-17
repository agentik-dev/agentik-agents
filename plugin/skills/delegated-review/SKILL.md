---
name: delegated-review
description: Delegate a read-only code review to headless API-billed agents under a hard budget cap, in the background; never for applying fixes or a quick inline review.
allowed-tools: Bash(agentik-agents *), Bash(mktemp:*), Bash(cat:*), Bash(jq:*), Write, Read
---

# Delegated code review

Use this when the user asks to review, audit, or find bugs in code "in the background",
"in parallel", "with the API key / API budget", "while I keep working", "with the
fan-out", or "have the agents review X" — i.e. when the review should be offloaded to the
separate API key rather than done inline on the seat. Do NOT use it for applying fixes
(the delegates are read-only) or for a quick inline review the user wants answered
directly in this session.

Offload a **read-only** code review to headless `claude --bare` agents billed to
the separate API key, under one hard budget cap, in the background — then report
the confirmed findings. The `/agents:delegate-review` command follows these same steps.

The tool, `agentik-agents` (its verbs `fanout`, `costs` and `api`), is on `PATH`; if it is
not, say `run make install in the agentik-agents repo` and stop.

**The boundary that governs everything:** a delegate has only `Read`, `Grep`,
`Glob` — no `Bash`, `Edit`, or `Write`. So delegation is for *analysis that
produces a report*, never for doing the work. A delegate cannot run, test, edit,
or verify anything by executing it. If a review needs command output, capture it
to a file first and `--add-dir` its directory — asking a delegate to run
something makes it thrash to a useless, still-billed placeholder.

## Steps

Follow these steps precisely. The target is what the user named; if none, review the
current git diff (`git diff` / `git diff --staged`), and if that is empty, ask the user
what to review instead of guessing.

1. **Decide the review dimensions and build a tasks file.** Pick 2–5 independent
   review angles for the target (e.g. correctness bugs, security, error handling,
   concurrency, API misuse). Write a JSON array to a temp file, one object per
   dimension, each `{"label": "<dimension>", "prompt": "<a self-contained instruction
   naming the exact files to read and asking for file:line citations>"}`. The delegates
   see none of this conversation, so every prompt must name the files itself, and they
   are **read-only**: never ask them to run, test, edit, or verify anything; scope
   prompts to reading and reasoning only.

2. **Pick a budget.** Measured `review` shards run ~$0.20–$0.71 each; default to
   `--budget-usd` = (number of dimensions) × $1.00 unless the user gave a figure.
   State the budget you chose.
   **Budget a dimension by how many files it fans over, not evenly.** A shard
   that must cross-check many files — a docs-consistency pass, a "trace every
   caller" hunt, a whole-package security review — burns far more turns (the
   real cost) than a single-file correctness check, and at a flat per-shard cap
   it is the one that budget-dies and returns *nothing* (measured twice this
   corpus: a docs shard at $1 and a token-security shard at $1.32, both wasted).
   Give the broad dimension 2–3× the cap, split it into narrower shards (one
   named doc vs one named code file), or run it solo — never let the widest
   dimension share the same cap as a one-file check.

3. **Launch in the background** with `run_in_background`, so the user keeps
   working and is notified on completion:

   ```
   agentik-agents fanout --budget-usd <N> --profile review -j <dimensions> \
     --id <short-slug-for-this-review> --phase review \
     --add-dir <repo-or-target-dir> \
     --tasks <tempfile> --out <tempdir>/run --json
   ```

   Use `--add-dir` for every directory whose files the prompts reference — a
   delegate can only read paths under an added dir plus its own reasoning. Tag
   `--id` with something the user will recognise (a ticket, a branch, a short
   description) so `agentik-agents costs --by id` can roll it up later.

4. **When it completes, read `<tempdir>/run/fanout.json`** and report:
   - Findings from shards whose `status` is `ok`, grouped by severity, each as
     `file:line — issue`. Ignore shards that are `degenerate`, `error`,
     `unparseable`, or `budget_exhausted`, but say how many there were and that
     their spend was wasted.
   - The spend line: `spent_usd` (note if `spent_usd_is_upper_bound` is true).
   - Any `denied_tools` — that means a delegate hit its read-only limit and may
     have thrashed; if a whole dimension degenerated, note that the fix is to
     pre-supply facts, not re-run.

5. **Verify before presenting as fact.** A delegate's finding is a *lead*, not a
   confirmed bug. For each finding you are about to report as real, confirm it
   against the actual code yourself (read the cited lines) before stating it
   plainly. Present unverified findings explicitly as "reported, unverified".

Never apply fixes here — reviewing is the deliverable; fixing is a separate, explicit
step the user asks for. Use `agentik-agents costs` (or the `/agents:delegate-costs`
command) afterward to see what it cost.
