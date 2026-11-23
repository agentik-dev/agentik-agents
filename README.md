# agentik-agents

agentik-agents is a Claude Code plugin that shows what every session and helper on this machine is doing, in one table, and that can run routine side work on a local model.
Use it when more than one session is open and you have lost track.

Install it in a terminal, then type the second line in a new Claude Code session:

```
claude plugin marketplace add agentik-dev/agentik-commons; claude plugin install agents@agentik
/agents:status
```

It needs Claude Code, `bash`, and the system's Python at 3.9 or newer. The table works on its own; the local model is optional, and it needs Ollama.
Part of [agentik](https://github.com/agentik-dev): the other tools, and how to leave.

## What it does

It does four things for Claude Code on one Mac, all under one command: `agentik agents <verb>`:

- **`status`**: shows what every agent is doing right now, with one row for each seat, helper, and local agent, read from files already on disk. It is read-only.
- **The local lane**: a session stays on your claude.ai seat, while its mechanical subagents run on a local model (Qwen 3.8 27B in Ollama, by default) through a loopback router, at no extra cost.
- **`agents:scribe`**: a plugin agent, running on Sonnet, that writes one repo's records from a builder's or a refuter's hand-back. It never merges or pushes.
- **The API lane**, off until you turn it on: it fans out read-only agents under one dollar budget, billed to an Anthropic API key, never to your seat.

## Install

Install the plugin from the agentik marketplace. It runs its tools from its own folder; no checkout is needed:

```sh
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install agents@agentik
```

The command line is `install-cli`. Run it in a terminal as `/agents:install-cli` in a session, or run the plugin's own `bin/agentik-agents install-cli` directly. It freezes the plugin's code under `~/.local/share/agentik-agents/`, and it writes `agentik-agents` and the `agentik` door into `~/.local/bin`. For an old name (`agentroute`, `claude-agents`, `claude-local`, or `localrig`), it refreshes a link there until 2026-12-31, and a new machine gets none of these links. If a file with that name already exists and is not a link, it leaves that file alone and reports its name. Then:

```sh
agentik agents doctor
```

From a checkout, `make install` runs the same `install-cli`. It refuses to run on a dirty tree, and `PREFIX=` changes where it installs. `make uninstall` removes what it wrote.

It needs `bash`, `/usr/bin/python3` (3.9 or later; the tools use only the standard library), and Claude Code. The plugin provides the commands `/agents:status`, `/agents:delegate-local`, and `/agents:install-cli`; the agents `agents:local-explore`, `agents:local-summarize`, `agents:local-review`, `agents:local-implement`, `agents:local-test`, and `agents:scribe`; and the skill `local-delegation`.

## The verbs

| verb | what it does |
|---|---|
| `status [--json] [--watch N] [--all] [--since MIN]` | Shows every seat, helper, and local agent right now. It exits 0 when the read works, 1 when it cannot read the sessions folder, and 2 on a usage error. |
| `local [claude args]` | Starts a seat session whose subagents run on the local model. It starts the router if needed, and it refuses to start if a check fails. |
| `route ...` | Runs the loopback router: it sends Claude models to Anthropic and local models to the local server. `route --check` exits non-zero when a row shows FAIL. |
| `rig ...` | Brings local backends up and down, sets the default, and manages their keys. |
| `doctor` | Reports what is on `PATH`, `python3` and its version, and the local lane's check. It only reports; it never blocks anything. |
| `install-cli [--prefix P] [--force]` | Puts the command line on `PATH`, built from the plugin's frozen code. If a newer command is already there, it leaves it in place and prints one line saying so; `--force` installs this one anyway. It exits 0 when it succeeds and 1 when it cannot. |
| `fanout JOB [--dry-run] [--yes] [--detach]` | Runs the API lane (described below): a job's read-only agents, under its budget. `fanout wait`, `fanout status`, and `fanout stop` follow a run. |
| `api status [--json]` | Shows the API lane's state and the steps left. `api probe` checks the installed CLI, and `api key set` and `api key remove` manage its key. |

`agentik agents --help` prints this table along with the tool each verb runs. `agentik` is the front door that every agentik tool installs; `agentik-agents <verb>` is the same command.

## The local lane's setup

```sh
# Ollama 0.33.0 or later, running
ollama pull qwen3.8:27b-mtp-q8_0        # about 30 GB
agentik agents route --check            # names whatever is missing
agentik agents local                    # the session; ask for a local agent, or /agents:delegate-local <task>
```

Inside that session the model name decides the route: `local/*` goes to the local server, and `sonnet`, `opus` or `fable` stay on Claude. No key is needed to start. Keep a local agent under about 8 tools, and never point one at untrusted content: `Read` is not confined to `--add-dir`, and a small model is more suggestible than a frontier one.

The router keeps a ledger at `~/.local/state/agentik-agents/route/requests.jsonl`. It records tokens, wall time, and agent ids, and it never records a prompt. Other backends (`llama-server`, MLX, and Unsloth) come up with `agentik agents rig up <name>`.

## The API lane

The API lane is off until one file says otherwise: `~/.config/agentik/agents/config.yaml`, in the account's own home. No repo, variable, or flag can stand in for that file. While the lane is off, help, `status`, `doctor`, `install-cli`, and the hooks print what they print without it. The lane turns on only on a platform where its read wall is proved; everywhere else, every lane verb refuses and names the platform.

```sh
# in ~/.config/agentik/agents/config.yaml:  "api:", and under it, indented, "enabled: true"
agentik agents api status            # the steps left
agentik agents api key set           # at a terminal: the key, kept encrypted by sops and age
agentik agents api probe             # the CLI once, on a made-up key against a local stub; spends nothing
agentik agents fanout JOB --dry-run  # the plan, spending nothing; --yes runs it
```

A job is a JSON file of shards. Each shard is a `review`, `explore`, or `analyze`, and every one only reads; `agentik agents fanout --help` shows the job file's form. `--detach` prints the run's id once its budget is reserved. `agentik agents fanout wait ID` prints the results, or exits 124 while the run is still going. A shard's result is data, never instructions.

Each shard runs Claude Code on the key alone, inside a kernel wall that hides the home folder except for the job's own folders and the folder Claude Code runs from. Two ceilings guard against an accident: `max_fanout_usd` ($2 unless set) and `max_day_usd` ($10). The real wall is the spending limit you set on the key's own workspace in the provider's Console. While shards run, `agentik agents status` lists them under their session, and that session is told their count at each prompt.

## Where the rest is

- `design/05-local-lane-guide.md`: covers the router's changes, the rig, the knobs, and the credentials.
- `design/01-local-agent-lane.md`, `design/02-local-rig.md`: the design and its measurements.
- `design/04-api-lane.md`: describes the API lane, including why it left on 2026-10-31, what it found, and how it returned.
- `design/packets/`: shows how each change was built. `NICE_TO_HAVE.md`: lists what a review left open.

`make check` is the gate. It runs seven stub-driven suites with 391 checks in total, including the plugin running on a bare machine (`tests/test-bare-machine.py`), with three of those suites rerun at the 3.9 floor. It also runs the lint, the doc gate, the public-hygiene scan, and `claude plugin validate`. It spends nothing.

## License

MIT.
