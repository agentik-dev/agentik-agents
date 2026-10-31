# design/05: the local lane, the guide

The README is a page; this is the rest of what it said about the local lane, moved here by
packet a-s17 with its words kept but for the lines that named the API lane. Design and
evidence: `design/01-local-agent-lane.md`, `design/02-local-rig.md`.

## The lane (`agentik agents local`, `agentik agents route`)

A session on this lane costs neither money nor much seat capacity: an interactive session stays on the **claude.ai seat** (Fable on the main
thread) while its **subagents run on the M4 Max's local model** (Qwen 3.8 27B in Ollama)
at zero marginal cost. Design and evidence: `design/01-local-agent-lane.md`.

Claude Code allows one API endpoint per session, so the split happens in a tiny
loopback router that routes **by model name**:

```
agentik agents local  →  the router 127.0.0.1:8787  →  claude-* models: api.anthropic.com, headers verbatim (seat kept)
                                             →  local/* or name:tag: Ollama /v1/messages (Anthropic format, native)
```

| You want to… | Do | Notes |
| --- | --- | --- |
| A seat session whose subagents are local | `agentik agents local [claude args]` | Starts the router if needed, runs `agentik agents route --check`, refuses to start on a FAIL, then execs `claude` with no credential variable so the seat stays active. It also sets `CLAUDE_CODE_ATTRIBUTION_HEADER=0`, `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1`, `API_TIMEOUT_MS`, `CLAUDE_CODE_SUBAGENT_MODEL=sonnet`, and passes `--agents` with a local `Explore` override (skipped, with a warning, if you pass your own `--agents`). Plain `claude` is untouched. |
| Send a specific piece of work local | Ask for `local-explore`, `local-summarize`, `local-review`, `local-implement`, `local-test` — or the built-in `Explore` | The `local-*` plugin agents (`plugin/agents/`), each with `model: local/default` and an explicit `effort`. The launcher also overrides the built-in `Explore` with a 3-tool session-scoped definition on the local model. Agents that name no model (`general-purpose` and kin) default to **`sonnet`**, not local: they carry every tool in the session, and 54 tool schemas are a 31k-token prompt — three minutes of prefill per turn on the 27B (measured). `CLAUDE_LOCAL_SUBAGENT=local/default` or `inherit` changes that; `CLAUDE_LOCAL_EXPLORE=inherit` leaves Explore alone. |
| Have a land's records written | name `agents:scribe` with the hand-back, the repo and the records wanted | Sonnet; the merge message to a file, the note, the record commit by explicit path; it never merges or pushes |
| Keep a piece of work on Claude | name `sonnet` / `opus` / `fable` in the Agent call | Model names decide the route; nothing else does. Forks always stay on the main model. |
| See what the lane did | the ledger `~/.local/state/agentik-agents/route/requests.jsonl` | $0 by construction; tokens, wall time, agent ids. No prompt content is ever logged. |
| Preflight only | `agentik agents route --check` | router · upstream · Ollama version ≥ 0.33.0 (0.33.2 is what was measured) · model present · policy. |

**What the router changes on local routes, and why (all measured on this Mac, 2026-09-04):**

- Drops Claude Code's `<total_tokens>…</total_tokens>` reminder system message. It
  changes every turn and defeats Ollama's prompt cache on this hybrid model: turn two
  prefilled in **35.6 s with it, 0.38 s without** (best case, not a guarantee: the two runs also differed in system-prompt length (3,682 against 3,629 characters) and were never compared directly, and 0.38 s was measured under `--exclude-dynamic-system-prompt-sections --setting-sources user`, not the flags the launcher uses (design/01 §14 Cache B)). Upstream
  requests keep it.
- Injects `output_config.effort: low` when absent and clamps anything above `medium`.
  Qwen 3.8 defaults to `xhigh` reasoning and spent **4,299 thinking tokens / 4m56s** on a
  three-line file when unpinned; at `low` the same task took 45 s.
- Clamps `max_tokens` to 8192 (Claude Code asks for 32000; at ~15 tok/s that is a
  35-minute runaway budget).
- Serialises local requests (the `qwen35` runner is single-slot; a second agent's prefill
  evicts the first's cache), and emits SSE `ping` events during a long silent prefill so
  Claude Code's 300-second stream watchdog does not fire.
- Answers `count_tokens` with a chars/4 estimate (Ollama has no such endpoint) and strips
  the seat's credential from anything sent to the local backend.

**What it deliberately does not do:** touch upstream requests (byte-for-byte relay, so
the OAuth bearer and every `anthropic-beta` value reach Anthropic unchanged), bind
anything but loopback, or hold a credential of its own.

**Two things about this that will bite you if nobody says them.** The launcher's built-in
`Explore` override is built at launch: the `agentik agents local` launcher (`explore_agent_json`) reads
`plugin/agents/local-explore.md` from this checkout and passes its prompt and tools with
`--agents`. An edit to that file reaches the override on the next launch through the
symlink, while the installed plugin's `agents:local-explore` needs `claude plugin update`,
so the two can differ until you update the plugin. And `~/.config/agentik/agents/route/backends.json` holds the Unsloth API
key in cleartext at mode 600. It is per-machine state, deliberately outside git and
outside sops, so a rebuild re-creates it with `agentik agents rig up`; do not freeze it into a
dotfiles repo without encrypting it first.

**Sizing the local model (Qwen 3.8 27B q8_0, Ollama 0.33.2, M4 Max 128 GB):** prefill
~87–230 tok/s; generation 11 tok/s prose, ~25 tok/s for JSON and tool calls (MTP draft
acceptance is what makes tool-heavy turns fast). **Tool schemas are the prompt:** a 3-tool
agent's turn is ~5.4k tokens (first turn 30–60 s, later turns seconds), a 50-tool one
~26k (146 s), a 54-tool one ~31k (172 s; that agent's turn *two* repeated the full
prefill — cause not isolated, n=1). Keep a local agent's `tools:` list under ~8 and
its turns under ~15k tokens; the ledger's `n_tools` and `input_tokens` columns show which
agent is oversize.

**Trade-offs to know:** while `ANTHROPIC_BASE_URL` is a non-Anthropic host, Claude Code
disables Remote Control — use plain `claude` for those sessions. Voice dictation is
disabled only while a key, token or `apiKeyHelper` is active, which the launcher keeps
unset ("Connect Claude Code to an LLM gateway",
<https://code.claude.com/docs/en/llm-gateway-connect>, as of 2026-10-14).
Local agents get a delegate's trust rules: `Read` is not confined to
`--add-dir`, prompt injection through read content is the threat, and a smaller model is
*more* suggestible. Never point a local agent at untrusted content. The seat still pays
for every delegation turn on the main thread, so batch small asks into one local task.

**Local lane requirements:** Ollama **≥ 0.33.0**
running, the model pulled (`ollama pull qwen3.8:27b-mtp-q8_0`, ~30 GB), and python3.
`agentik agents rig up llama` also needs `brew install llama.cpp`; `agentik agents rig up unsloth` needs
Unsloth (`curl -fsSL https://unsloth.ai/install.sh | sh`) and downloads ~29 GB on first
run. `agentik agents route --check` names whichever of these is missing.

**The rig: more than one local backend.** `agentik agents rig up llama` starts llama-server on the
GGUF Ollama already has (two slots, host prompt cache, dense checkpoints, Qwen's template
from `share/`), `agentik agents rig up flash` starts llama-server on Qwen3.8 Flash-Next (Unsloth's
UD-IQ4_XS from `~/models`, the full 262144 ctx, one slot, mlock, and `--metrics` for
example-mac's llm-exporter; it shares :8081 with `llama`, so bring up one or the other),
`agentik agents rig up mlx` registers Ollama's MLX build (`qwen3.8:27b-mxfp8`,
2x the prose decode via MTP and a 10 s reload; its cross-conversation prefix cache did
**not** speed up a new agent shape when measured, see design/02 §3.6d), `agentik agents rig up unsloth` starts Unsloth's API server on
its Dynamic GGUF. Each writes `~/.config/agentik/agents/route/backends.json`, which the router
reads at start, so an agent selects a backend with `model: local/<name>` (or
`local/<name>/<model>`) and nothing else changes; `agentik agents rig default <name>` makes one of
them the `local/default` every `local-*` agent uses (restart the router after either). `agentik agents rig status` shows what is up and
what the router sees; `agentik agents rig down` stops it. Measurements and the reasoning are in
`design/02-local-rig.md`.

**Knobs** (env, all optional). Router: `AGENTROUTE_BACKENDS` (JSON, overrides the
backends file), `AGENTROUTE_BACKENDS_FILE`, `AGENTROUTE_UPSTREAM`, `AGENTROUTE_LOCAL_MODELS`,
`AGENTROUTE_TIMEOUT_S`, `AGENTROUTE_PING_AFTER_S` / `_EVERY_S`, `AGENTROUTE_STATE_DIR`.
Launcher: `CLAUDE_LOCAL_SUBAGENT` (sonnet), `CLAUDE_LOCAL_EXPLORE` (local|inherit),
`CLAUDE_LOCAL_NO_PREFLIGHT`. Backends: `LOCALRIG_LLAMA_PORT` / `_SLOTS` / `_CTX` /
`_CACHE_RAM` / `_THINK_BUDGET` / `_KEY`, `LOCALRIG_UNSLOTH_MODEL` / `_VARIANT` / `_KEY`,
`LOCALRIG_MLX_TAG`, `LOCALRIG_Q8_BLOB`. And:
`AGENTROUTE_LISTEN` (127.0.0.1:8787),
`AGENTROUTE_LOCAL_URL` (http://127.0.0.1:11434 — point it at an Unsloth server to swap
backends, with `AGENTROUTE_LOCAL_AUTH="Bearer sk-unsloth-…"`), `AGENTROUTE_LOCAL_MODEL`
(what `local/default` resolves to), `AGENTROUTE_LOCAL_DEFAULT_EFFORT` / `_MAX_EFFORT`,
`AGENTROUTE_LOCAL_MAX_TOKENS`, `AGENTROUTE_LOCAL_CONCURRENCY`,
`AGENTROUTE_LOCAL_STRIP_TOKEN_REMINDER=0` to keep the reminder, `AGENTROUTE_LOG`.
`tests/test-route.py` drives the real router against stub backends (87 checks, no
network, no model).

## Credentials

No setup is required to start. Run `agentik agents local` and the lane works with no key configured anywhere. If `agentik agents rig` finds no llama key in the environment or in sops, it generates a random one for that run. It hands that key to `llama-server` through a 0600 file, and writes the same value into the router's `backends.json`. That is safer than a shared fixed key: the value is never reused and never written anywhere shared. `agentik agents rig` prints a one-line note on how to persist it, if you choose to.

### What these keys are, and are not

They are not cloud credentials. They authenticate this Mac's own inference servers to this Mac's own router, both over loopback. The threat they address is a stray process on the same machine posting prompts to a model server that is listening locally. The router strips the seat's own credential before it reaches a local backend and substitutes the backend's key. That seat credential never reaches a local backend at all.

The keys live in `local-backends.sops.yaml` in the secrets directory, outside the repo (`$AGENTIK_AGENTS_SECRETS`, else `${XDG_CONFIG_HOME:-$HOME/.config}/agentik/agents/secrets`; the directory 0700, the files 0600), encrypted with sops using age, with two entries: `llama_api_key` and `unsloth_api_key`. Only the values are encrypted, so a diff shows which secret changed without showing it. Recipients and the `encrypted_regex` live in `.sops.yaml`. Nothing under `secrets/` is committed, ciphertext included. The age private key lives at `~/.config/sops/age/keys.txt`, mode 600, backed up in the password manager.

Resolution order, per key:

1. The environment variable (`LOCALRIG_LLAMA_KEY` for llama, `LOCALRIG_UNSLOTH_KEY` for unsloth) wins if it is set.
2. Otherwise, sops, decrypted only at the moment the key is needed.
3. Otherwise, a fallback: a fresh random key for llama, or the key Unsloth Studio printed to its own log for unsloth. This is the last resort before an error.

`agentik agents rig keys status` shows which source is in play per key, plus the stored value's length. It never shows the value itself.

### Where a new provider's key goes

One file, one naming rule, and nothing to edit in `.sops.yaml`.

Put it in `local-backends.sops.yaml` in the secrets directory under the name `<provider>_api_key`, using
`agentik agents rig keys set <provider>`. The provider name is whatever you call that backend in
`AGENTROUTE_BACKENDS` or `agentik agents rig`, so a vLLM server you route to as `local/vllm` uses
`vllm_api_key`.

| You are adding | Key name | How |
| --- | --- | --- |
| A local server the router talks to (llama.cpp, Unsloth, vLLM, LM Studio, an MLX server) | `<provider>_api_key` | `agentik agents rig keys set <provider>` |
| A cloud endpoint you route to instead of Anthropic | `<provider>_api_key`, plus `AGENTROUTE_UPSTREAM` or a backend entry carrying its `auth` | `agentik agents rig keys set <provider>` |

`secrets/` is ignored whole in `.gitignore`: the store lives outside the repo, so neither a
copy an old checkout left in the tree nor a decrypted spill can be committed.
`tests/test-rig.sh` checks that git tracks nothing there and that both are refused.

`.sops.yaml` needs no edit because `encrypted_regex` matches by suffix, not by a list of
names: anything ending `_api_key`, `_key`, `_token`, `_secret`, `_password`, or
`_credential` is encrypted. A list has to be updated for every new provider, and forgetting
writes that value to git in the clear. That failure was reproduced on 2026-09-05 with an
`openrouter_key`, which is why the pattern is a suffix now.

One sharp edge worth knowing: **the rule is copied into each file when it is created.**
Editing `.sops.yaml` does not change files that already exist, so a file written under an
older rule keeps that older rule and can still admit a cleartext value. To bring a file up
to date, decrypt it, delete it, and re-encrypt it. `tests/test-rig.sh` builds a store of invented values
under a throwaway identity, never reading the real one, and fails if a credential-shaped
value in it is unencrypted, or if its embedded rule has drifted from `.sops.yaml`.

Any key is also overridable per run without touching sops, as `LOCALRIG_<PROVIDER>_KEY`.
That wins over the stored value, which is what `agentik agents rig keys status` reports in its source
column.

### Commands

| Command | What it does | When to use it |
| --- | --- | --- |
| `agentik agents rig keys status` | Prints each key's source (environment, sops, or unset) and whether a value is stored, with its length. Never prints the value. | Check where a key is coming from, e.g. before debugging a 401. |
| `agentik agents rig keys init` | Generates a llama key and stores it in sops if none exists. Idempotent: if one is already stored, it says so and points to `set` instead. | First time you want a persistent llama key instead of a per-run random one. |
| `agentik agents rig keys set llama` / `agentik agents rig keys set unsloth` | Prompts for the value with input hidden, then writes it to sops. The value goes in on stdin, never in argv, so it never appears in `ps` or shell history. | Rotating a key, or entering one you already have. |
| `agentik agents rig keys sync-unsloth` | Captures the key Unsloth Studio printed once into its own log at first start, and stores it in sops. | After a fresh Unsloth Studio start, so a rebuild does not have to scrape the log again. |
| `agentik agents rig down llama` then `agentik agents rig up llama` | Restarts the llama backend so it picks up a changed key. | Right after `keys set llama` or `keys init`. |
| `agentik agents rig restart-router` | Restarts the router, which otherwise keeps the old key because it reads `backends.json` only at startup. | Right after any key change, alongside restarting the backend. |

### First-time setup on a new machine

1. Install sops and age: `brew install sops age`.
2. Put your age private key at `~/.config/sops/age/keys.txt`, mode 600. For a new identity, generate it with `age-keygen -o ~/.config/sops/age/keys.txt`. Then print the public half with `age-keygen -y` and add that line to `.sops.yaml`.
3. If you added a new recipient, re-wrap the existing secrets so that key can read them: `sops updatekeys ~/.config/agentik/agents/secrets/local-backends.sops.yaml`, from the repo so sops reads `.sops.yaml`. Run this only from a machine that can already decrypt the file. Adding a recipient to `.sops.yaml` alone does nothing for files that already exist.
4. Verify: `agentik agents rig keys status` should show `llama_api_key` sourced from sops.
5. Optional: run `agentik agents rig keys init` if no llama key is stored yet.

### There is no API key in this repo

This repo ships **no** Anthropic API key. One used to live at
`secrets/anthropic-api-key.enc.yaml`; it was removed on 2026-09-05 and the key revoked in
the Console. It had been encrypted to two identities that predate the move off the owner's former GitHub org, neither of which is this Mac, so nothing here could read it, and
the API lane had never been run on this machine.

Two things worth keeping straight. Deleting an encrypted file does not retire the key
inside it: the ciphertext stays in git history and on the remote, so revoking in the
Console is the control that actually works. And adding a recipient to `.sops.yaml` does not
re-wrap files that already exist; only `sops updatekeys` does that.

The local agent lane needs none of this.

### Rotation and revocation

Rotate a local key with `agentik agents rig keys set`, then restart the backend that uses it (see Commands above). No external service needs notifying.

Removing a person's age recipient from `.sops.yaml` stops future re-encryptions from including them. It does not retract what they already hold: the old ciphertext stays in git history, and their key still unwraps it. Actually retiring a local key means rotating it, which is cheap here because these credentials are local and self-issued.

### Verified behaviour

The key `llama-server` loads matches the sops value byte for byte. It is passed with `--api-key-file`, so it never appears in the process argv. A wrong key gets HTTP 401. The sops key gets HTTP 200. A call routed to local/llama returns from the right backend, and the key never appears in the router's ledger.

`tests/test-rig.sh` asserts source precedence, that `status` never prints a value, and that the plaintext is absent from the ciphertext on disk. It also asserts that a missing secrets file still leaves the lane working.
