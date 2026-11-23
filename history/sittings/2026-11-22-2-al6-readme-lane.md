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
- `README.md` is a byte copy of the source again (as on main); the sidecar is re-stamped. The review's F1 and F2 are closed by the copy, and N1 to N4 by four word fixes in the lane section.
- decide, owner: the coordinator. The ruled n36 finding makes a row of 706 characters, and `scripts/recordlint` bounds a row at 400; the cell is cut to a row of 397 that keeps each fact but the quoted names, which the cited keys hold. Its consumer is the landing's lint; a fuller text goes to a cited file under `history/sessions/`, if wanted.

## While waiting
- none

## Next act
The check, the second review and the landing.

## Exit
Fix round done: README.md copied from the source, the sidecar redone, four lane sentences as the code reads (N1 to N4); hygiene run, the check queued.
