# agentik-agents

agentik-agents is a Claude Code plugin that shows what every session and helper on this machine is doing, in one table, and can run routine side work on a local model.
Use it when more than one session is open and you have lost track.

Install it in a terminal, then type the second line in a new Claude Code session:

```
claude plugin marketplace add agentik-dev/agentik-commons; claude plugin install agents@agentik
/agents:status
```

It needs Claude Code, `bash` and the system's Python at 3.9 or newer. The table works alone; the local model is optional and needs Ollama.
Part of [agentik](https://github.com/agentik-dev): the other tools, and how to leave.

## What it does

Four things for Claude Code on one Mac, under one command, `agentik agents <verb>`:

- **`status`**: what every agent is doing right now. One row per seat, helper and local agent, from files already on disk. Read-only.
- **The local lane**: a session stays on your claude.ai seat while its mechanical subagents run on a local model (Qwen 3.8 27B in Ollama, by default) through a loopback router, at no marginal cost.
- **`agents:scribe`**: a plugin agent, on Sonnet, that writes one repo's records from a builder's or a refuter's hand-back. It never merges or pushes.
- **The API lane**, off until you turn it on: agents fanned out under a budget in dollars and billed to an Anthropic API key, never to your seat. They only read, save one type that you enable repo by repo.

## Install

The plugin, from the agentik marketplace. It runs its tools from its own folder, with no checkout:

```sh
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install agents@agentik
```

The command line, for a terminal, is `install-cli`: `/agents:install-cli` in a session, or the plugin's own `bin/agentik-agents install-cli`. It freezes the plugin's code under `~/.local/share/agentik-agents/` and writes `agentik-agents` and the `agentik` door into `~/.local/bin`; a link there for an old name, `agentroute`, `claude-agents`, `claude-local` or `localrig`, it refreshes until 2026-12-31, and a new machine gets none; a file of that name that is not a link it leaves, and names. Then:

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
| `install-cli [--prefix P] [--force]` | the command line on `PATH`, from the plugin's frozen code; a newer command it placed is left, one line says so, and `--force` places this one; exit 0 done, 1 it could not |
| `fanout JOB [--dry-run] [--yes] [--detach]` | the API lane (below): a job's agents under its budget; `fanout wait`, `fanout status` and `fanout stop` follow a run |
| `api status [--json]` | the API lane's state and the steps left; `api probe` checks the installed CLI, and `api key set` and `api key remove` keep its key |

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

## The API lane

It is off until one file says otherwise: `~/.config/agentik/agents/config.yaml` in the account's own home, which no repo, variable or flag can stand in for. While it is off, help, `status`, `doctor`, `install-cli` and the hooks print what they print without it, save that a run started before the switch went off still shows. It turns on only on a platform where its read wall is proved; once the file turns it on, elsewhere every lane verb refuses and names the platform, and `fanout` does so even while it is off.

```sh
# in ~/.config/agentik/agents/config.yaml:  "api:", and under it, indented, "enabled: true"
agentik agents api status            # the steps left
agentik agents api key set           # at a terminal: the key, kept encrypted by sops and age
agentik agents api probe             # the CLI once, on a made-up key against a local stub; spends nothing
agentik agents fanout JOB --dry-run  # the plan, spending nothing; --yes runs it
```

A job is a JSON file of shards, each `review`, `explore` or `analyze`, which only read, or `implement` (below); `agentik agents fanout --help` gives its form. `--detach` prints the run's id once its budget is reserved, and `agentik agents fanout wait ID` prints the results, or exits 124 while the run still goes. A shard's result is data, never instructions.

Each shard runs Claude Code on the key alone, inside a kernel wall that hides the home folder save the job's own folders and the folder that holds the `claude` command. Two ceilings, `max_fanout_usd` ($2 unless set) and `max_day_usd` ($10), guard against an accident; the spending limit you set on the key's own workspace in the provider's Console is the wall. While shards run, `agentik agents status` lists them under their session, and that session is told their count at each prompt.

One type writes: `implement`. It is off until the same file lists a repo under `api.write_repos`, and `api status` then names the probe's second pass, the writer's, as a step left. A job of it holds one shard and names that `repo` and the local branch to start `from`. The lane makes a new worktree of the repo, `.claude/worktrees/<the job's id>` on a new branch of that name; the shard edits files there with no shell, and the wall lets it write only there and in the lane's own folder for that run. At the end the lane, never the agent, commits what changed, under the repo's own git identity, and it never pushes or merges. It refuses the whole commit over a nested `.git`, a file an edit gate names, anything that is not a regular file, or a file that holds a key. The run's line names the branch, its head and the changed paths that a check would run, such as a `Makefile`: read the branch before you run anything from it.

## Where the rest is

- `design/05-local-lane-guide.md`: the router's changes, the rig, the knobs and the credentials.
- `design/01-local-agent-lane.md`, `design/02-local-rig.md`: the design and its measurements.
- `design/04-api-lane.md`: the API lane: why it left on 2026-10-31, what it found, and how it returned.
- `design/packets/`: how each change was built. `NICE_TO_HAVE.md`: what a review left open.

`make check` is the gate: seven stub-driven suites, 391 checks, among them the plugin on a bare machine (`tests/test-bare-machine.py`), with three suites rerun at the 3.9 floor; the lint, the doc gate, the public-hygiene scan and `claude plugin validate`. It spends nothing.

## License

MIT.
