# Sitting 2026-11-13-2: ak7-plug-agents, the fix of review 1 and phase 2

| item | value |
|---|---|
| goal | review 1's R1-F1 to R1-F3 fixed, a failing test first; its NICE rows filed; then main merged after al0-fanout-stub, al0's notes filed, 1.7.0 |
| budget | 90 tool calls; `claude-opus-5-5`; one commit per finding |
| pin | worktree `.claude/worktrees/ak7-plug-agents`, branch `ak7-plug-agents` at 6b17003, off main c0193bd |
| window | builder, one sitting, spawned by a hq sitting of 2026-11-13 |
| agents | none |
| exit | done: R1-F1 to R1-F3 fixed, main merged, 1.7.0; gate 20261113-101007-1534 exit 0 on 71fc3cc; record handed to the hq |

## Done-ness
- [x] act 1, 5563d4d: R1-F1, every fault a read can meet held to one object (N6 with it).
- [x] act 2, 691630e: N5, the text `doctor` reads a dead plug as a lane, not as none.
- [x] act 3, 9676923: R1-F2, a derived key takes the env source of what feeds it (N1 with it).
- [x] act 4, 30d04f2: R1-F3, `backends.default.*`'s line names a backend.
- [x] act 5, 78977d4: NICE rows n10 to n14 (R1-F4, N2, N3, N4, N7); N1, N5, N6 fixed, so not filed.
- [x] act 6: main merged at 4df9bab (main 2c18f11); al0's review notes n15 to n23 at 9b1c321; 1.7.0 alone at 71fc3cc (plugin-version-check passes, no 1.7.1).
- [x] act 7: gate 20261113-101007-1534 exit 0 in 2 min on 71fc3cc.

## Decided (reversible, logged)
- A number JSON has no word for (nan, inf) is printed as its text; the answer is dumped with `allow_nan=False`.
- Any fault inside a read is the contract's §2 answer, code `unreadable`, exit 2; `lane` exits 3 on a fault.
- `lane` prints `yes` or `no`; the text `doctor` takes only `no` as no lane.
- A feed is a variable of the tool's three prefixes or `AGENTIK_*`; `HOME` and `XDG_*` are this machine's, so a default is computed with them.
- R1-F3 keeps kind `command`, spelled with `BACKEND`, the note saying it takes a backend's name: `fixed` would say it cannot be changed, and it can.
- The merge's byte compare moves its reference from c0193bd to 78977d4, ak7's last commit before the merge: ak7 adds table lines.
- The dispatcher prints §2's answer where the plug printed nothing and did not exit 2 (its usage).

## Handover
- None: review 2 reads 6b17003..71fc3cc.

## Next act
- None in this row: review 2 over the fix and the merge.
