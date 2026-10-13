---
allowed-tools: Bash(claude-fanout:*), Bash(claude-costs:*), Bash(mktemp:*), Bash(cat:*), Bash(jq:*), Write, Read
description: Delegate a read-only code review to headless API-billed agents under a hard budget cap, in the background
disable-model-invocation: false
---

Delegate a read-only code review of `$ARGUMENTS` to headless `claude --bare`
agents (billed to the separate API key via `claude-fanout`), running in the
background under one hard budget cap, then report the confirmed findings.

`$ARGUMENTS` is what to review — one or more file paths, a directory, or a short
description of the change. If it is empty, review the current git diff
(`git diff` / `git diff --staged`), and if that is empty, ask the user what to
review instead of guessing.

Follow these steps precisely.

1. **Decide the review dimensions and build a tasks file.** Pick 2–5 independent
   review angles appropriate to `$ARGUMENTS` (e.g. correctness bugs, security,
   error handling, concurrency, API misuse). Write a JSON array to a temp file,
   one object per dimension, each `{"label": "<dimension>", "prompt": "<a
   self-contained instruction naming the exact files to read and asking for
   file:line citations>"}`. The delegates see none of this conversation, so
   every prompt must name the files itself. Remember delegates are **read-only**
   — never ask them to run, test, edit, or verify anything; scope prompts to
   reading and reasoning only.

2. **Pick a budget.** Measured `review` shards run ~$0.20–$0.71 each; default to
   `--budget-usd` = (number of dimensions) × $1.00 unless the user gave a
   figure. State the budget you chose.

3. **Launch in the background.** (If `claude-fanout` is not on PATH, say `run make install
   in the repo` and stop.) Run `claude-fanout` with `run_in_background`
   (so the user keeps working and gets notified on completion):

   ```
   claude-fanout --budget-usd <N> --profile review -j <dimensions> \
     --id <short-slug-for-this-review> --phase review \
     --add-dir <repo-or-target-dir> \
     --tasks <tempfile> --out <tempdir>/run --json
   ```

   Use `--add-dir` for every directory whose files the prompts reference — a
   delegate can only read paths under an added dir plus its own reasoning. Tag
   `--id` with something the user will recognise (a ticket, a branch, a short
   description) so `claude-costs --by id` can roll it up later.

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

Do **not** apply any fix as part of this command — profiles are read-only and
the delegates cannot edit anyway. Reviewing is the deliverable; fixing is a
separate, explicit step the user asks for.
