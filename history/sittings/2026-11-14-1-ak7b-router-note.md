# Sitting 2026-11-14-1: agentik-agents, ak7b-router-note, the first build

| item | value |
|---|---|
| goal | a local lane set up whose router is not started reads as a note in both doctors; `route --check` gates as before; the next patch; the gate once |
| budget | the builder's 90 tool calls; `claude-opus-5-5` |
| pin | worktree `.claude/worktrees/ak7b-router-note`, branch `ak7b-router-note`, off main 2b81b47 (plugin 1.9.0); nothing linked |
| window | builder, one sitting, spawned by an hq sitting of 2026-11-14; a small change, no packet |
| agents | none |

## Done-ness
- [x] act 0: this charter.
- [x] act 1, R1 to R4: the router's check marks its row `not_started: true` where the connect is refused (absent on every other row, text and exit unchanged); the plug's lane read gives that row `note`, its detail naming the address and `agentik agents local`; the text doctor prints it as one line and out of the count, through the plug's `lane text`, and asks the router as at the pin when the plug cannot answer. Tests 19 to 23 in `tests/test-plug.py`; 19, 20 and 22 red at 2b81b47, all green.
- [x] act 2, R5: plugin 1.9.1, alone in the last commit under `plugin/`.
- [x] act 3: the gate once on this commit, the branch's tip (its id in the coordinator's record).

## Handover
- decide, owner: the coordinator: the new tests run under a sandbox that lets loopback through (to ports they bind and close, or their own listener), since a denied connect is no refused one; the router's address is a variable in them, as the router reads it from one only; consumer: the review.
- decide, owner: the coordinator: the command the note names is `agentik agents local`, since the README says it starts the router when needed; consumer: the review.

## Next act
The coordinator's review and the landing.

## Exit
R1 to R5 built and committed, each behind a test; hygiene and the version check clean; the gate runs on this commit.
