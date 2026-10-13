# Raw material: adversarial review round, 2026-09-05 (input to respeak)

Five Opus reviewers, run in parallel against claude-code-agents, each given a separate
surface, told to assume the code was broken, to cite file:line, and to reproduce before
reporting. Known items were excluded up front (command namespacing, the Remote Control
trade-off, one pre-existing failing check in tests/test-fanout.py).

## Reviewer 1 — CLI ergonomics
11 findings. Preflight failure named no remedy but "disable the safety check". Default-backend
FAIL rows carried no next action while the optional-backend rows did. Duplicate router daemons
accumulated silently (three were alive). restart-router killed by port with a wrong-port
fallback. localrig's header claimed claude-local restarts the router; it does not. status rows
were truncated to the interpreter path and its "(none)" branch was dead code. down left a stale
default. No --help/--version on the shell tools. Local lane absent from Requirements and doctor.
--check had no verdict line and warn read as ok. README said "Two cost lanes" after the third landed.

## Reviewer 2 — flow and docs-vs-code
Journeys: down orphans local/default with no way back but hand-editing JSON. Fresh-machine
prerequisites (Ollama, the model pull, the version floor, llama.cpp) stated nowhere. The
built-in Explore override is a hardcoded duplicate of agents/local-explore.md that drifts.
backends.json holds an API key outside sops. A content-addressed blob sha is hardcoded.
Contradictions: design/02 sections 3.2-3.4 still asserted the conclusion 3.6d reversed;
README still sold the MLX prefix cache; test counts, tool lists and env knobs stale; the
Ollama floor stated as both 0.33.0 and 0.33.2; one measurement quoted as 5.3k, 6.3k and 7.2k.
Honesty: a "forcing full prompt re-processing, 7,201 tokens" line quoted for a run whose log
does not contain it (it belongs to a different task); "the only difference is the reminder"
when the dump records system_len 3682 vs 3629; the 0.38 s headline measured under flags
claude-local does not use, with a contradicting production run omitted; prefill floor raised
from 87 to 120 tok/s with no run behind it; an n=1 caveat dropped between design and README.

## Reviewer 3 — the router
13 findings, all reproduced against stub backends. HIGH: the local header policy was a
two-entry deny list, so Cookie, ANTHROPIC_CUSTOM_HEADERS values and a future auth header
reached the local backend verbatim. HIGH: a backend dying mid-stream escaped the exception
handling, leaving a chunked response with no terminator and no ledger row. HIGH: a chunked
request body was silently dropped, and with no model left to route on the request went
upstream on the seat's credential. HIGH: a non-dict backend value, a non-numeric env var or
a LISTEN without a colon crashed at import. MEDIUM: --check crashed on a non-JSON 200 and
printed nothing at all; folding dropped non-text blocks and cache_control silently; hostile
body types killed the request with no response and no row; the ":" heuristic sent real
bedrock and :beta Claude ids to the local model; HEAD/204/304 were framed as chunked.
Verified sound: concurrency at 12 simultaneous streams (peak in-flight exactly 2, no
corruption), semaphore never leaked, the seat token never reached the ledger, python 3.9.

## Reviewer 4 — shell and cost accounting
HIGH: claude-local's `chmod --` aborts under set -e on BSD, in the one branch that runs when
the router is not yet up. HIGH: answering() reported dead ports as alive because curl already
prints 000 and `|| echo 000` appended a second. HIGH: hand-built JSON was injectable from a
model id supplied by a backend, able to redirect every local prompt off-box. HIGH: pkill -f
blast radius. MEDIUM: down orphans default; restart-router can abort before restarting;
non-atomic config write with a readable window on the key; status masked only keys of 12+
characters so the 11-character default printed in full; the key rode in curl argv every 10s.
Python: a valid-JSON non-object line crashed all three lanes; --since silently discarded
undated rows; the equivalent figure omitted the cache reads printed one line above; the whole
ledger was slurped into memory; non-numeric usage raised; rows with no backend merged into the
real "default" backend.

## Reviewer 5 — plugin surface
HIGH: `tools:` is not a skill frontmatter field and is silently ignored, so both skills granted
nothing — including the Bash the fail-closed preflight depends on. HIGH: no agent description
said local/default only resolves in a routed session. HIGH: the fail-closed contract was
unfalsifiable, because the model was told to run a preflight but never to show it, and two
sanctioned escapes let it never go local while obeying the letter. HIGH: the prompt-injection
warning was absent from the entire local lane while local-implement holds Bash, Edit and Write.
MEDIUM: local-implement never reported its worktree path, so the caller could not find the
edits; local-test was ordered to echo 60 lines of log at 15 tokens a second; two agents competed
for the same job; a Bash allow-rule pattern matched nothing; any loopback URL passed the
preflight; maxTurns 40 is 20-40 minutes on this model.

## Self-inflicted, worth recording
While verifying the pkill finding, the reviewer's own cleanup line — pkill -f 'agentroute
--serve' — matched the shell command containing that string and killed the production router
along with the throwaway. The hazard stopped being theoretical. Three orphaned daemons were
cleared as a side effect and the router was restored.

## What was fixed
Router 0.4.0: header allow-list; 404 for an undeclared backend; SSE error plus terminator plus
ledger row on mid-stream death; 411 on a chunked body; claude-named ids stay upstream; config
validated rather than fatal; hostile bodies answered; fold keeps cache_control and counts what
it drops; correct framing for bodyless responses; --check survives non-JSON and prints a verdict.
Tests 67 to 87.
Shell: chmod fixed; answering() fixed; JSON via argv with an atomic 0600 write; pidfiles with
argv verification instead of pkill; down clears a matching default; restart-router verifies
before killing; unconditional key masking; key out of argv via --api-key-file and curl --config;
the requested Unsloth model matched rather than the first listed; --help and --version.
Costs: non-object lines skipped; undated rows kept and counted; cache reads priced; streaming
read; numeric coercion; unrecorded backends bucketed separately. Tests 45 to 50.
Plugin: allowed-tools on both skills; the routed-session precondition in all five agent
descriptions; a mandatory verbatim preflight line; injection warnings; worktree hand-back;
log-to-file instead of regurgitation; overlap removed; allow-rule patterns corrected.
Docs: three unsupported claims corrected, a superseded banner over design/02 3.2-3.4, stale
counts and lists fixed, local lane requirements stated.

## State
All suites green except the one pre-existing fanout check in an untouched file. Live router
restarted on 0.4.0, 8 ok / 0 warn / 0 FAIL, an undeclared backend rejected with a message
naming what is declared, a real local call still answering. Committed and pushed.
