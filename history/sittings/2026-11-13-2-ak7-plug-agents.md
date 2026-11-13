# Sitting 2026-11-13-2: ak7-plug-agents, the fix of review 1 and phase 2

| item | value |
|---|---|
| goal | review 1's R1-F1 to R1-F3 fixed, a failing test first; its NICE rows filed; then main merged after al0-fanout-stub, al0's notes filed, 1.7.0 |
| budget | 90 tool calls; `claude-opus-5-5`; one commit per finding |
| pin | worktree `.claude/worktrees/ak7-plug-agents`, branch `ak7-plug-agents` at 6b17003, off main c0193bd |
| window | builder, one sitting, spawned by a hq sitting of 2026-11-13 |
| agents | none |
| exit | in flight |

## Done-ness
- [x] act 1: R1-F1, every fault a read can meet held to one object (N6 with it).
- [ ] act 2: N5, the text `doctor` reads a dead plug as a lane, not as none.
- [ ] act 3: R1-F2, a derived key takes the env source of what feeds it.
- [ ] act 4: R1-F3, `backends.default.*`'s line names a backend.
- [ ] act 5: NICE rows R1-F4, N1 to N4, N7.
- [ ] act 6: main merged after al0, al0's notes filed, 1.7.0 last under `plugin/`.
- [ ] act 7: the gate, once.

## Decided (reversible, logged)
- A number JSON has no word for (nan, inf) is printed as its text; the answer is dumped with `allow_nan=False`.
- Any fault inside a read is the contract's §2 answer, code `unreadable`, exit 2; `lane` exits 3 on a fault.
- The dispatcher prints §2's answer where the plug printed nothing and did not exit 2 (its usage).

## Handover
- None yet.

## Next act
- Act 2.
