# Packet ak7-plug-agents: agents answers `describe`; `doctor --json` exists, and no lane set up is a note, not a failure

The brief as the hq wrote it for row ak7, in this repo's packet shape. Its interface is the plug's contract, shared by five tools and the suite's reader in agentik-commons (`plugins/suite/lib/agentik_suite/tools.py`, `config.py`); its sections 2 to 7 are copied below as section 2.

| item | value |
|---|---|
| from | agentik-hq row ak7 (design/15 §4 P4, P5, P9, P10; §13); the plug's contract; hq entries 6 and 37 |
| pin | agentik-agents main c0193bd, plugin 1.6.3; worktree `.claude/worktrees/ak7-plug-agents`, branch `ak7-plug-agents`; nothing linked from main |
| wall | this worktree; no push, `--amend`, rebase, merge, install or landing; no `claude` process, no model run, no key read; `doctor`, `route --check` and any verb that may probe run only under `sandbox-exec` with the network denied; no relay verb; a `make` only through the session gate's queue |
| may touch | `plugin/lib/agents_plug.py` (new); `plugin/lib/agentik-agents`; `plugin/lib/agentroute` (`check`, `main`); `plugin/lib/claude-agents` (the `status --json` print); `plugin/lib/agents_install.py` only if the freeze names its files (it does not: the freeze walks `lib/`); `tests/test-plug.py` (new); `tests/test-dispatch.sh`; `tests/test-status.py`; `tests/test-bare-machine.py` (R7's text, see section 3); `Makefile` (`test`'s two lists); `plugin/.claude-plugin/plugin.json`; `NICE_TO_HAVE.md`; this packet; a charter under `history/sittings/` |
| acceptance | section 1's Acceptance table, lines 1 to 13 |
| verify | `make check`, once, last, through `agentik session gate run`, then `agentik session gate wait <id> --strict --timeout 540` in the foreground |
| budget | one commit for this packet, one for the tests seen red, one per ruling group, the version alone last; stop at 90 tool calls with the act in flight committed |

## Baseline at the pin

Measured at c0193bd on 2026-11-13 in a temp HOME, sandboxed: `describe --json`, `describe config --json` and `doctor --json` exit 2 with the dispatcher's usage lines; `status --json` with no sessions folder exits 1 with one line on stderr and leaves 51 files under `~/Library/Caches/com.apple.python`.

## 1. The brief

### The owner's words

"Make plugin configuration discoverable and drill down." The suite's `agentik config agents` lists this tool's settings and `agentik config agents.route.local_max_tokens` prints one as a card. Today its settings are environment variables a person finds only by reading four scripts.

### The ledger

The repo keeps no `DECISIONS.md` and no `CLAUDE.md`. Cited: hq entry 6 (`/usr/bin/python3`, a 3.9 floor, the standard library alone), hq entry 37 (made-up names in fixtures and the packet; no address but loopback).

### Rulings

- R1, what stands. Every verb but `doctor` prints what it prints at the pin and exits as it exits, but for R8's two keys in `status --json`. `doctor`'s text changes in one place, R7's. The dispatcher stays POSIX sh and hands each tool its arguments unchanged. `agentroute --check`'s text and exit do not change.
- R2, the file: `plugin/lib/agents_plug.py`, new, `#!/usr/bin/python3`, the standard library alone, run by the dispatcher under the interpreter `install_cli` picks, as `agents_install.py` is. It holds the three reads, the settings table and the list of checks. In the dispatcher: a `describe` verb that hands its arguments to it; `doctor --json`, which does the same; `describe` in the usage line and in `table`. `install-cli`'s freeze carries the new file (see how `agents_install.py` is carried).
- R3, `describe --json`: the contract's §3. `tool` `agents`; `version` the dispatcher's `version`; `needs`: `claude` as an optional program (the local lane runs it), `python3` as a program; `verbs`: `local`, `status`, `rig`, `route`, `doctor`, `describe`, `install-cli`, each with its line of `table`, every `top` false; `reads`: the contract's `config` and `doctor` rows, then one `status` row, `sessions` (`status --json`): the name is the contract's §3, the part of the suite's `status` this read feeds.
- R4, the layers: `default` (path null); `rig` (the backends file, at the path `agentroute` computes; present when it exists; not travelling: the rig writes it); `env` (path null; present when any variable of R5 is set). No layer is named `user`.
- R5, the settings. A key is a group and the variable's own name in lower case:

  | group | from | keys |
  |---|---|---|
  | `route.` | each `AGENTROUTE_<NAME>` that `agentroute` reads through `env` or `env_num`, but `BACKENDS` | `route.listen`, `route.local_max_tokens` and so on |
  | `backends.` | each backend of `AGENTROUTE_BACKENDS`, else of the backends file, and the `default` backend the router adds where none names one (`load_backends`, then its `setdefault`), each field filled as the router fills it | `backends.<name>.url`, `.model`, `.fold_system`, `.auth` |
  | `local.` | `CLAUDE_LOCAL_SUBAGENT`, `CLAUDE_LOCAL_EXPLORE` | `local.subagent`, `local.explore` |
  | `rig.` | each `LOCALRIG_<NAME>` that `localrig` reads as `${NAME:-default}` | `rig.llama_port` and so on |

  - A default is read from the script that owns it, at run time, by the form it is written in (`env("NAME", "default")`, `${NAME:-default}`); it is never typed in `agents_plug.py`. A default that holds `$HOME` is expanded; one the script computes (a path through `migrated`, a nested `${...}`) is computed the same way here or given as null, and your record says which. A test fails when a variable of a group is in a script and not in the answer, or the reverse.
  - `value`: the variable when set and not empty, else the default, cast as the script casts it (`env_num`'s `int` or `float`; `LOCAL_MODELS` a list; `LOCAL_STRIP_TOKEN_REMINDER` a boolean by the script's own rule). `route.local_auth`, each `backends.<name>.auth` and any `*_KEY` are `secret`: `"(set)"` or null.
  - `source`: `env` for a set variable; `rig` with the file's path for a backend read from the file, its `line` null (JSON); else `default`.
  - A backends file, or an `AGENTROUTE_BACKENDS`, that is no JSON object: the router says so on stderr, ignores it and goes on (`load_backends`), so the read does too. It answers `ok` true, exit 0, with the backends the router would then use and one `warnings` row, `reason` `unreadable`, `key` null, `path` the file (null for the variable). The `rig` layer is `present`, since the file exists. A backend that is no object is left out, as the router leaves it out.
  - `change`, `live` false throughout: for `route.*`, `local.*` and `rig.*`, `launch`, the variable before the verb that reads it (`AGENTROUTE_LOCAL_MAX_TOKENS=VALUE agentik agents local`, `LOCALRIG_LLAMA_PORT=VALUE agentik agents rig up llama`), with the note that the router or the rig reads it when it starts and a shell profile keeps it. For `backends.*`, `command`, the rig's own verb that writes that backend, with the note that the rig writes the file and a hand edit is lost at its next `up` or `down`.
- R6, the summaries: one table in `agents_plug.py`, a key or a pattern to one sentence under 100 characters. These, word for word:

  | key | summary |
  |---|---|
  | `route.listen` | The loopback address the router listens on. |
  | `route.upstream` | Where the router sends a request for a Claude model, its headers untouched. |
  | `route.local_url` | The backend a `local/default` request is sent to. |
  | `route.local_model` | The model a `local/default` request runs on. |
  | `route.local_default_effort` | The effort a local request gets when it names none. |
  | `route.local_max_effort` | The highest effort a local request may ask for. |
  | `route.local_max_tokens` | The most output tokens a local request may ask for. |
  | `route.local_concurrency` | How many local requests run at once; the rest wait their turn. |
  | `route.timeout_s` | The seconds the router waits on a backend before it gives up. |
  | `route.log` | The file the router writes one line a request to: sizes and names, never content. |
  | `backends.*.url` | Where this backend answers. |
  | `backends.*.model` | The model this backend serves when a request names none. |

  Write the rest in the same voice from the comment and the code beside each variable: what it decides, present tense, no "This setting", no restating the key. List every sentence you wrote in your record: the coordinator passes them through respeak.
- R7, the doctor read and F7.
  - A lane is set up when the backends file exists, or any `AGENTROUTE_*` variable is set, or something listens on the router's address (one loopback connect, 1 s). One function in `agents_plug.py` decides it, and the dispatcher's text `doctor` asks that function.
  - `agentroute --check --json`: one object, `{"ok": <as its exit>, "rows": [{"state", "what", "detail"}]}`, the same probes and the same exit as `--check`.
  - `doctor --json` prints the contract's §5. Its checks: one for each name the text `doctor` looks for on PATH, `ok` with the path, else `note` with the remedy `/agents:install-cli`, the first of the two the text `doctor` names and the one that runs where no launcher is on PATH (the contract's §5); `claude`, `ok` or `warn`; `python3`, `ok`, or `fail` below 3.9 or where it does not run. Then the lane: not set up, one check `lane`, status `note`, the detail saying no local lane is set up here so the router, the upstream and the backends were not asked; set up, one check for each row of `--check --json`, `FAIL` read as `fail`. Exit 0, as the text `doctor`.
  - The text `doctor`, where no lane is set up, prints one line under `Local lane:` in place of `--check`'s rows, and `--check` is not run, so nothing is sent to the upstream. Where a lane is set up its text is the pin's.
- R8, the status read: `status --json` prints its object with `"schema": "agentik.agents.sessions/1"` and `"ok": true` first, every other key as it is; `tests/test-status.py`'s one check of the top-level keys gains the two. With no sessions folder it keeps its line on stderr and its exit 1 (the contract's §6). The dispatcher's `status` verb sets `PYTHONPYCACHEPREFIX`, when it is unset, to `${XDG_CACHE_HOME:-$HOME/.cache}/agentik/pycache` before it runs `claude-agents`: measured at the pin, the read otherwise writes 51 bytecode files under `~/Library/Caches/com.apple.python` in a new HOME, and a suite read writes nothing outside the cache folder.
- R9, the room. A second design adds an API lane to this tool after you. Keep the settings as one table and the checks as one list, each row data, so a later row adds lines and no function. Define no key whose first segment is `api`, no layer named `user`, no check named `api`; say this in the module's head comment.

### The files

`plugin/lib/agents_plug.py` (new); `plugin/lib/agentik-agents` (two verbs, the usage line, `table`, `doctor`'s lane block, `status`'s prefix); `plugin/lib/agentroute` (`check` and `main`: `--json`); `plugin/lib/claude-agents` (the one print of `status --json`); `plugin/lib/agents_install.py` only if the freeze names its files; `tests/test-plug.py` (new); `tests/test-dispatch.sh` (the usage line); `tests/test-status.py` (the one check of the top-level keys); the `Makefile` (`test`'s two lists); `plugin/.claude-plugin/plugin.json`; `NICE_TO_HAVE.md`; the packet; the sitting's record under `history/sittings/`.

### Acceptance

`A` is the worktree's `plugin/bin/agentik-agents`. Every line runs in a temp HOME with the `XDG_*` variables under it and no `AGENTROUTE_*`, `CLAUDE_LOCAL_*` or `LOCALRIG_*` variable but those the line names; every line that may probe runs under `tests/test-bare-machine.py`'s sandbox, which denies the network. Measured at `c0193bd`, and again on 2026-11-13 in a temp HOME: lines 1 to 6 and 8 exit 2 with the dispatcher's usage lines; `status --json` opens with `generated` where a sessions folder exists, exits 1 with one line on stderr where none does, and either way leaves 51 files under `~/Library/Caches/com.apple.python`; line 11's suite prints `ok` false, `error.code` `no_answer`, exit 2; `--version` takes 0.03 to 0.06 s. Read from the code, not run: the text `doctor` with no lane prints a `FAIL router` row, sends a HEAD to the upstream and exits 0.

| # | line |
|---|---|
| 1 | `A describe --json`: exit 0, one object with every key of the contract's §3, three reads, seven verbs, every `top` false, no ESC byte, under 1 s. `A describe` and `A describe nosuch --json`: exit 2 |
| 2 | `A describe config --json`: exit 0; every setting has every key of the contract's §4; every `source.layer` is `default`; `route.local_max_tokens` is the integer `agentroute` holds as its default, with `default` the same; no key opens `api.`; no layer is `user` |
| 3 | with `AGENTROUTE_LOCAL_MAX_TOKENS=4096`: that key is 4096, `source` `{"layer": "env", "path": null, "line": null}`, `values` are `default` then `env`, `change.kind` `launch`, `change.command` opens `AGENTROUTE_LOCAL_MAX_TOKENS=VALUE `, `live` false. With `AGENTROUTE_LOCAL_AUTH` set to a made-up word: `route.local_auth` is `"(set)"` and the word is nowhere in the output |
| 4 | a backends file holding one made-up backend: `backends.<name>.url` is its url, `source` `rig` with the file's path; the `rig` layer `present` true. With `AGENTROUTE_BACKENDS` set as well: the variable's backends, `source` `env` |
| 5 | a test reads `agentroute`, `claude-local` and `localrig` and holds the answer's keys to the variables each reads, both ways |
| 6 | `A describe config --json route.listen` prints that one setting; `... nosuch` prints `settings` `[]`, exit 0. A backends file that is not JSON: exit 0, `ok` true, one `warnings` row with `reason` `unreadable` naming the file, the `rig` layer `present`, and `backends.default.url` equal to `route.local_url` |
| 7 | `plugin/lib/agentroute --check --json`, sandboxed, nothing listening: one object, `rows` holding a `router` row whose `state` is `FAIL`, the exit `--check`'s |
| 8 | `A doctor --json`, nothing set up, with a stub that records any connection off loopback: `schema` `agentik.doctor/1`, `ok` true, `failed` 0, one check `lane` with `status` `note`, no check named `router` or `upstream`, exit 0, inside 3 s, and the stub recorded nothing. With a backends file: the lane's rows are there, the `router` check `fail`, exit 0 |
| 9 | `A doctor`, nothing set up: `Local lane:` is followed by one line and no `FAIL`; with a backends file, the pin's rows |
| 10 | `A status --json` with `CLAUDE_AGENTS_SESSIONS_DIR` naming an empty folder: exit 0, the first two keys are `schema` (`agentik.agents.sessions/1`) and `ok`, the pin's three keys after them. With no sessions folder: the pin's line on stderr, exit 1. After lines 1 to 6 and after both of these: every file under HOME outside `$XDG_CACHE_HOME/agentik/` is as it was, and HOME holds no `Library` folder |
| 11 | by hand, once, recorded in your hand-back: with `C` the agentik-commons checkout beside this repo and `T` a new temp folder holding `home/` and `bin/agentik-agents`, a two-line `sh` file that execs `A`: `env -i HOME=$T/home PATH=$T/bin:/usr/bin:/bin TERM=dumb $C/plugins/suite/bin/agentik-suite config agents.route.local_max_tokens --json` prints `ok` true, `tool` `agents`, `key` `route.local_max_tokens`, `setting.change.kind` `launch`; `... config agents` groups the keys under `route`, `local`, `rig`; `... config` lists `agents` as `answers` with `0 changed` |
| 12 | `tests/test-plug.py` (new, named in both lists of the `Makefile`'s `test`), `tests/test-dispatch.sh`, `tests/test-route.py` and `tests/test-bare-machine.py` pass, under `/usr/bin/python3` too; an old test changes only where it pins the usage line or `status --json`'s top-level keys, and the record names each |
| 13 | `make check`, once, last, through the gate queue, green |

Write the tests of lines 1 to 10 first and see each fail.

### Not built

A settings file for this tool, an `api` key or check (the next design's). A `term` module or a catalogue here (ak10). A human `describe`. A write of any setting. A change to what `route --check` probes. The suite's side: the doctor read's consumer, the fallback row's removal. The README: its source changes only if a test pins the verb list; say so.

No fork for the owner.

Version: `1.7.0` in `plugin/.claude-plugin/plugin.json`, the one place, alone in the last commit that touches `plugin/`. At a phase 2 the coordinator names the next version.

Rules: commit by explicit path (`git add <paths>`), never `-A`, `-u` or `commit -a`; never push; never run `relay`; a `make` only through `agentik session gate run`; never run the text `doctor` or `route --check` outside the sandbox, since each reaches the upstream; no hostname, address but loopback, email, person's name, account detail or private repo's name in this public repo. No landing, no install.

## 2. Interface: the plug contract, sections 2 to 7

### 2. The envelope (P4)

Every answer opens `{"schema": "agentik.<read>/1", "ok": true, "tool": "<name>", ...}`. `tool` is the name less `agentik-`. A new key never raises the number; a reader ignores a key it does not know; the suite reads a number above 1 as not adopted.

A read that could not run prints, still on stdout, and exits 2:

```json
{"schema": "agentik.config/1", "ok": false, "tool": "demo",
 "error": {"code": "bad_file", "message": "/home/u/.config/agentik/demo/config.yaml:7: a tab in the indent", "remedy": null}}
```

`code` is a lowercase word with `_`; `message` is one line holding the file and line where there is one; `remedy` is a command a person can run, or null. `ok: true` means the read ran, never that what it found is good.

### 3. `describe --json`

The one fixed argv. `describe` with no `--json` exits 2 with one line naming `describe --json`; an unknown word after `describe` exits 2.

```json
{"schema": "agentik.describe/1", "ok": true,
 "tool": "demo", "version": "1.2.0",
 "summary": "Paints each line of a report in the colour its level asks for.",
 "repo": "example/agentik-demo", "plugin": "demo@agentik",
 "needs": [{"name": "git", "kind": "program", "why": "reads the cwd's repo", "optional": false}],
 "verbs": [{"name": "paint", "summary": "Paint a report.", "top": false},
           {"name": "doctor", "summary": "Check the tool and what it needs.", "top": false}],
 "reads": [{"kind": "config", "name": "settings", "argv": ["describe", "config", "--json"]},
           {"kind": "doctor", "name": "doctor", "argv": ["doctor", "--json"]},
           {"kind": "status", "name": "queue", "argv": ["queue", "status", "--json"]}]}
```

| key | type | rule |
|---|---|---|
| `version` | string | what `--version` prints after the name |
| `summary` | string | one sentence, under 80 characters, what the tool does for its user |
| `repo` | string | `<owner>/<repo>` of the public repo |
| `plugin` | string or null | `<name>@agentik`; null for a tool with no plugin |
| `needs` | list | what must be on the machine for the tool to run. `kind`: `program` (an executable on PATH), `package` (a Python package), `plugin` (a `<name>@agentik`) or `toolchain` (needed to build it). `why`: a clause. `optional`: true when the tool runs without it and says so |
| `verbs` | list | every first-level verb, in help's order; `summary` is help's own line for it. `top` true claims `agentik <verb>` for this tool (P2): false unless the brief names the verb |
| `reads` | list | each other read by its argv. `kind` `config` and `doctor`: at most one each, with the names and argvs above, the same in every tool. `kind` `status`: any number, each naming a read the tool already has. The suite's `status`, as designed, draws a part by the read's `name`, and the five names it draws are `sessions`, `gate`, `unattended`, `backlog` and `run`: a tool whose read feeds one of those parts gives it that name, and a read with another name is listed and never run by it. It may add words after a status read's `argv` (for `backlog`: `--order FILE` and the checkouts), so the `argv` ends where the tool's own options and paths may follow |

The suite refuses the whole answer when a key of the table is missing, when `needs`, `verbs` or `reads` is not a list, when a read's `kind` is another word or its `argv` is not a list of strings, or when two reads are `config` or two are `doctor`.

### 4. The config read: `describe config --json [KEY]`

```json
{"schema": "agentik.config/1", "ok": true, "tool": "demo",
 "layers": [
  {"name": "default", "path": null, "present": true, "travels": false},
  {"name": "user", "path": "/home/u/.config/agentik/demo/config.yaml", "present": true, "travels": true},
  {"name": "repo", "path": "/work/site/.claude/agentik/config.yaml", "present": false, "travels": false},
  {"name": "env", "path": null, "present": true, "travels": false}],
 "settings": [
  {"key": "paint.colour", "value": "dark", "default": "light", "type": "string",
   "choices": ["light", "dark"], "summary": "The palette each painted line uses.",
   "source": {"layer": "user", "path": "/home/u/.config/agentik/demo/config.yaml", "line": 4},
   "change": {"kind": "edit", "command": null, "path": "/home/u/.config/agentik/demo/config.yaml",
              "block": "paint:\n  colour: dark", "note": null},
   "live": true,
   "values": [{"layer": "default", "value": "light"}, {"layer": "user", "value": "dark"}]},
  {"key": "width", "value": 80, "default": 80, "type": "integer", "choices": null,
   "summary": "The column a painted line is cut at.",
   "source": {"layer": "default", "path": null, "line": null},
   "change": {"kind": "command", "command": "agentik demo set width VALUE", "path": null,
              "block": null, "note": "Holds for this session only."},
   "live": true, "values": [{"layer": "default", "value": 80}]},
  {"key": "token", "value": "(set)", "default": null, "type": "secret", "choices": null,
   "summary": "The key the demo service is called with.",
   "source": {"layer": "env", "path": null, "line": null},
   "change": {"kind": "launch", "command": "DEMO_TOKEN=VALUE agentik demo paint", "path": null,
              "block": null, "note": null},
   "live": false, "values": [{"layer": "env", "value": "(set)"}]}],
 "warnings": [
  {"key": "paint.color", "reason": "unknown", "value": null,
   "path": "/home/u/.config/agentik/demo/config.yaml", "line": 9}]}
```

**Layers**, lowest first, every layer the tool reads whether or not its file exists.

| key | rule |
|---|---|
| `name` | from this list where it fits: `default` (what ships: code or a shipped file), `user`, `repo`, `local` (a repo file git ignores), `env`, `launch` (a flag or a profile named at start), `session` (this session only). **The user's file is named `user`**: the suite's list prints that layer's path beside the tool |
| `path` | the absolute path, or null where the layer is no file. A file the tool would read is named even when absent |
| `present` | whether the file exists; for `env`, whether any of its variables is set; `default` is true |
| `travels` | true for a file that is the user's own configuration and is worth carrying to a new machine: `agentik config --user-files` prints these. False for what ships, a repo's file (git carries it), state and the environment |

A name may repeat where a tool reads several files of one kind, one a folder: each row has its own `path`, and a `values` row of such a layer carries its `path` and `line`.

**Settings.** One row a leaf: a mapping is never a value, its leaves are keys.

| key | type | rule |
|---|---|---|
| `key` | string | a dotted path of `[a-z0-9_-]` segments, unique, stable. The suite cuts `<tool>.<key>` at the first dot, and past 20 keys groups by the first segment, so the first segment is the group a person would look under |
| `value` | string, number, boolean, null or a flat list | what the tool would use now, here. A secret is `"(set)"` or null, never its text |
| `default` | the same type, or null | the value on a machine where nothing is set: what ships and nothing else, so no file of the user's or of a repo, no variable and no flag. Where what ships is more than one layer (session's shipped defaults, then its shipped profile), `default` is what they give together, so a new machine reads `0 changed`. The suite marks a setting as changed when `default` is not null and `value != default`, so the two are one JSON type: never `80` against `"80"`. Null where there is no default; such a key never reads as changed |
| `type` | string | `string`, `integer`, `number`, `boolean`, `list`, `path` or `secret` |
| `choices` | list or null | every value the tool takes, when the set is closed |
| `summary` | string | one sentence under 100 characters: what the setting decides, in the present tense, for someone who has not read the code. It never opens "This setting" and never restates the key |
| `source` | object | the highest layer that sets the key. `layer` is a name of `layers`; `path` that layer's file or null; `line` the 1-based line the key stands on in that file, or null where the layer is no text file. Unset anywhere: `{"layer": "default", "path": <the shipped file or null>, "line": <its line or null>}` |
| `change` | object | all five keys, null where unused. `kind` `command`: `command` is the exact line, spelled `agentik <tool> ...`, the value as `VALUE`. `edit`: `path` is the file to edit and `block` the lines as they would stand in it, current value included, joined by `\n`, no final newline; the file is the one of the layer in force when a person can edit that layer, else the user's file, since an edit below the layer in force changes nothing here. `launch`: `command` is the start line with its flag or variable. `fixed`: `note` says why it cannot be changed. `note`, with any kind, is one sentence on what the change does not do |
| `live` | boolean | true when a change holds from the next read; false when it holds from the next session or the next start |
| `values` | list | `{layer, value}` for each layer that sets the key, lowest first, `default` among them where there is one. The card prints them in order. A row may also carry that layer's `path` and `line` |

**With KEY**: `settings` holds that one setting, or is `[]` when the tool has no such key, still `ok: true`, exit 0 (the suite then asks again with no key, to name the nearest). `layers` and `warnings` are whole either way.

**Warnings**, each `{key, reason, value, path, line}`: `reason` `unknown` for a key in a file that the tool does not read, `choice` for a value outside `choices` (with the `value`), `unreadable` (key null) for a file the tool skips because it cannot parse it, `ignored` for a key the tool knows and does not take from that file (a key that only a project's file may set, set in the user's). The suite prints them under the tool's list with the file and line; it has words for the first two today, and prints any other with the unknown-key line.

**A file that does not parse** is reported as the tool treats it. A tool that refuses to run on it answers §2's error, code `bad_file`, exit 2. A tool that skips the layer and goes on answers `ok` true with that layer `present` and one `unreadable` warning.

### 5. The doctor read: `doctor --json`

```json
{"schema": "agentik.doctor/1", "ok": true, "tool": "demo", "failed": 1, "warned": 0,
 "checks": [
  {"name": "python", "status": "ok", "detail": "3.9.6 at /usr/bin/python3", "remedy": null},
  {"name": "service", "status": "note", "detail": "no service is configured, so nothing was asked of one", "remedy": null},
  {"name": "launcher", "status": "fail", "detail": "the launcher is 1.1.0, older than the plugin's 1.2.0", "remedy": "agentik demo install-cli"}]}
```

- `status` is `ok`, `note` (true and worth a line, nothing to do), `warn` (worth a look, never a failure) or `fail`. A thing that is not set up because the user never asked for it is a `note`, never a `fail`.
- `detail` is one line. `remedy` is one command a person can run, or null: a shell line, or a slash command (`/demo:install-cli`) where the thing to mend is the launcher a shell line would run. A line that works only inside the tool's checkout (`make install`) is no remedy. `name` may repeat.
- `failed` and `warned` count the statuses. `ok` is true whenever the read ran: a tool whose `doctor --json` gave `ok` the meaning "no check failed" moves that meaning to `failed`, and says so in its record.
- A check keeps every key it printed before this row (`ok`, `warn`) beside the new ones.
- The exit and the text form stay the tool's own: the suite computes its exit from the statuses and reads the object whatever the tool's exit was.
- The read ends inside 20 s whatever does not answer: a check that waits on a socket or a process has a timeout of its own. It never leaves this machine unless the user set up the thing it asks, and never writes outside the tool's own state.

### 6. A status read

A read the tool already has, named in `reads` by its argv. Where it prints an object, the object gains `"schema"` and `"ok": true` as its first two keys and keeps every other key as it was. The schema is `agentik.<tool>.<name>/1`, or `agentik.<verb>/1` for a verb the tool claims at the top level; a read that already carries a `schema` keeps it. Where a read prints something else today (a bare `null`, a list), it is named as it is and its shape is left to the row that owns that read. The same holds where a read has nothing to read and exits non-zero with a line on stderr (a meter read with no meter exits 2; a sessions read with no sessions folder exits 1, both measured): the exit and the line stay, and the suite reads a non-zero exit as a source it could not read.

### 7. What the tests of every tool hold, whatever its language

1. `describe --json`: exit 0; stdout is one object; every key of §3; no `ESC` byte; under 1 s.
2. Every read named in `reads` runs by `agentik-<tool>` plus its `argv` and prints one object with `schema` and `ok`, in a fixture that gives the read something to print (§6 names the cases with nothing).
3. The config read with no key, in a temp HOME with no file: every setting has every key of §4, no `source.path` lies under the temp HOME, and every `source.layer` and every `values[].layer` is a name of `layers`.
4. A user file that sets one key at a known line: that setting's `source` is `{"layer": "user", "path": <that file>, "line": <that line>}`, its `values` end with the user's, and the keyed read prints that setting alone.
5. The keyed read of a key the tool does not have: `settings` is `[]`, exit 0.
6. A user file with a key the tool does not know: one `warnings` row with its line.
7. A layer file that does not parse: `ok` false, `error.code` `bad_file`, the file in `error.message`, exit 2; or, in a tool that skips such a file, `ok` true and one `unreadable` warning naming it.
8. After every read but the doctor read: the temp HOME outside `$XDG_CACHE_HOME/agentik/` holds the files it held before, byte for byte, `~/Library/Caches` among them. The doctor read may add files under the tool's own state folder and nowhere else.
9. Every `summary` is one sentence under its bound, and no two settings share a `key`.

## 3. Where the brief and the code met

- `tests/test-bare-machine.py`'s `test_3_doctor` pinned the text `doctor`'s `FAIL router` rows with nothing set up; R7 removes those rows there, so that test holds R7's one line instead, and a second case with a backends file holds the pin's rows.
- The freeze (`agentik_install._freeze`) walks the whole `lib/`, so `agents_plug.py` travels with no change to `agents_install.py`.

## 4. Forbidden reads

A file over 8 KB whole; a relay ledger or a reference snapshot whole; anything outside the wall's reads.
