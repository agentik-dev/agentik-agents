# Delegated-implement brief template

A reusable header for briefing a headless **implementer** run (`agentik-agents api
--profile analyze --model claude-opus-5`, or a fresh un-profiled run when the
implementer must edit — the profiles are read-only). Distilled from measured
failures driving this lane against a job-queue service's repo.

## Why this exists — the `implement-e` failure (2026-08-14)

One implement run spent **53 turns / $6.44** and emitted only its test file and a
docs edit — it front-loaded reading and ran out of turn/budget headroom before
emitting the actual code, then *described* the un-emitted files in its
integration notes as if delivered. A continuation run with the header below
finished the same work in **17 turns / $1.93**, complete. The delta was output
discipline, not capability.

## The header (paste at the top of every implement brief)

```
OUTPUT DISCIPLINE (read first — this is the #1 cause of a wasted run):
- CAPTURE RULE (load-bearing): only your SINGLE FINAL message is captured — a
  `--profile` run emits `--output-format json`, whose `result` is the last
  assistant message and nothing before it. So do ALL your reading FIRST, then
  emit EVERY file together in one final message. `## NEW`/`## EDIT` blocks
  spread across turns are LOST (this cost a real run). Do not interleave reading
  and emitting.
- Do the bounded reading below, then emit — no preamble, no plan, no
  exploratory wandering (the opposite failure: a run that reads for 50 turns and
  emits almost nothing). Read the named files, then write everything.
- Emit files in THIS order in that final message: <list every file,
  smallest/most-foundational first>.
- A file you cannot finish: OMIT it entirely and name it in the notes. NEVER
  describe an edit in prose without emitting the OLD/NEW block for it — a
  described-but-unemitted file reads as done and is not.
- Integration notes: 10 lines max, AFTER all the code blocks, in that same
  final message.

READ ONLY THESE FILES before writing (naming them is what keeps the run cheap —
every extra exploratory read is a turn, and turns are the bill):
  <exact path list — the contract test, the 2–4 files being edited, the 1–2
   type/interface definitions the new code binds to. Nothing else.>

FORMAT: `## NEW <path>` + one fenced code block; `## EDIT <path>` + one or more
`### OLD` / `### NEW` pairs whose OLD is a byte-exact, unique excerpt COPIED from
the current file (never from memory).
```

## Companion rules for the driver (you)

- **Split large slices into two calls**: (1) the contract/test file, then (2) the
  implementation with that test pasted in as "the contract — make it compile and
  pass; where it disagrees with the prose below, the test wins." The test becomes
  a precise, cheap spec and the second run cannot drift.
- **Apply with a strict applier that fails closed on any anchor mismatch**, and
  **pass the expected file list to it** so a partial emit is caught immediately
  rather than discovered at `go build`. (See `apply-slice.py`'s
  expected-files check.)
- **Verify every finding before acting** — an implementer's integration note is a
  claim, not a fact; a delegated review's finding is a lead. Read the cited lines.
- **Stagger parallel implementers by ~15s** so the second pays a cache read, not a
  second cache write (measured ~2.4x cheaper on the shared prefix).
- **Run substantial implements in the background**; a foreground timeout kill
  forfeits the spend and it is still on the bill.
```
