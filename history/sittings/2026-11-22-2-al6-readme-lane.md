# Sitting 2026-11-22-2: agentik-agents, al6-readme-lane

| item | value |
|---|---|
| goal | the README's source gains the API lane: a fourth thing, two verbs, its own section, its design line; the wish list folds n37 into n36 |
| budget | about 90 tool calls, `claude-opus-5-5`; small change (hq entry 17), no packet |
| pin | `60aa679` on main, plugin 1.9.10 |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the source's five edits, each clause checked against the code; two clauses changed to what the code does (the `api status` cell, the wall's sentence)
- [x] the wish list: n37 leaves, n36's from cell as ruled, its finding cell cut to fit the row bound
- [x] doclint, recordlint, readme-top and the hygiene scans in the foreground, each clean at `b2edc42`

## Handover
- open by level: none yet
- If cut: the first unticked line above.
- The render of `README.md` is the coordinator's act; until it runs `make check` reads `readme: stale`, so no check is queued.
- decide, owner: the coordinator. The ruled n36 finding makes a row of 706 characters, and `scripts/recordlint` bounds a row at 400; the cell is cut to a row of 397 that keeps each fact but the quoted names, which the cited keys hold. Its consumer is the landing's lint; a fuller text goes to a cited file under `history/sessions/`, if wanted.

## While waiting
- none

## Next act
The coordinator's render of `README.md`, then `make check`, the review and the landing.

## Exit
Handed back with both rulings built and the lints clean; no check queued, since the README is stale until its render.
