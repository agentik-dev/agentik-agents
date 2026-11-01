# agentik-agents

Three things for Claude Code on one Mac, under one command, `agentik agents <verb>`:

- **`status`**: what every agent is doing right now. One row per seat, helper and local agent, from files already on disk. Read-only.
- **The local lane**: a session stays on your claude.ai seat while its mechanical subagents run on a local model (Qwen 3.8 27B in Ollama, by default) through a loopback router, at no marginal cost.
- **`agents:scribe`**: a plugin agent, on Sonnet, that writes one repo's records from a builder's or a refuter's hand-back. It never merges or pushes.

## Install

The plugin, from the agentik marketplace. It runs its tools from its own folder, with no checkout:

```sh
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install agents@agentik
```

The command line, for a terminal, is `install-cli`: `/agents:install-cli` in a session, or the plugin's own `bin/agentik-agents install-cli`. It freezes the plugin's code under `~/.local/share/agentik-agents/` and writes `agentik-agents`, the `agentik` door and links for the old names `agentroute`, `claude-agents`, `claude-local` and `localrig` (until 2026-12-31) into `~/.local/bin`; a file there that is not a link it leaves, and names. Then:

```sh
agentik agents doctor
```

From a checkout, `make install` runs the same `install-cli` (it refuses a dirty tree; `PREFIX=` moves it), and `make uninstall` removes what it wrote.

It needs `bash`, `/usr/bin/python3` (3.9 or later; the tools are stdlib only) and Claude Code. The plugin gives `/agents:status`, `/agents:delegate-local`, `/agents:install-cli`, the agents `agents:local-explore`, `agents:local-summarize`, `agents:local-review`, `agents:local-implement`, `agents:local-test` and `agents:scribe`, and the skill `local-delegation`.

## The verbs

| verb | what it does |
|---|---|
| `status [--json] [--watch N] [--all] [--since MIN]` | every seat, helper and local agent now; exit 0 when the read works, 1 when the sessions folder cannot be read, 2 on a usage error |
| `local [claude args]` | a seat session whose subagents run on the local model; starts the router if needed and refuses to start on a failed check |
| `route ...` | the loopback router: Claude models to Anthropic, local models to the local server; `route --check` exits non-zero on a FAIL row |
| `rig ...` | bring local backends up and down, set the default, manage their keys |
| `doctor` | what is on `PATH`, `python3` and its version, the local lane's check; it reports and never gates |
| `install-cli [--prefix P]` | the command line on `PATH`, from the plugin's frozen code; exit 0 done, 1 it could not |

`agentik agents --help` prints the table with the tool each verb runs. `agentik` is the front door every agentik tool installs; `agentik-agents <verb>` is the same command.

## The local lane's setup

```sh
# Ollama 0.33.0 or later, running
ollama pull qwen3.8:27b-mtp-q8_0        # about 30 GB
agentik agents route --check            # names whatever is missing
agentik agents local                    # the session; ask for a local agent, or /agents:delegate-local <task>
```

Inside that session the model name decides the route: `local/*` goes to the local server, and `sonnet`, `opus` or `fable` stay on Claude. No key is needed to start. Keep a local agent under about 8 tools, and never point one at untrusted content: `Read` is not confined to `--add-dir`, and a small model is more suggestible than a frontier one.

The router keeps a ledger at `~/.local/state/agentik-agents/route/requests.jsonl`, with tokens, wall time and agent ids, and never a prompt. Other backends, `llama-server`, MLX and Unsloth, come up with `agentik agents rig up <name>`.

## Where the rest is

- `design/05-local-lane-guide.md`: the router's changes, the rig, the knobs and the credentials.
- `design/01-local-agent-lane.md`, `design/02-local-rig.md`: the design and its measurements.
- `design/04-api-lane.md`: the API-billed lane this plugin once carried, why it went, and how to bring it back.
- `design/packets/`: how each change was built. `NICE_TO_HAVE.md`: what a review left open.

`make check` is the gate: seven stub-driven suites, 391 checks, among them the plugin on a bare machine (`tests/test-bare-machine.py`), with three suites rerun at the 3.9 floor; the lint, the doc gate, the public-hygiene scan and `claude plugin validate`. It spends nothing.

## License

MIT.
