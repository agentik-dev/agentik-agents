# Packet al2-wall: the wall around a shard, the key's store, and the probe that spends nothing

The API lane's second row of four (al1 to al4, design/21 §5 of the coordinating repo), cut from its brief in this repo's packet shape. Three builders work beside it from the same pin; a join merges the four.

| item | value |
|---|---|
| from | the coordinating repo's design/21 (the API lane returns), §2 item 11, §3.5 items 27, 29, 30, §9 R1-F5 to R1-F7; its seams page for rows al1 to al6; the old wrapper's key functions at d8ca583 |
| pin | agents main c0193bd, plugin 1.6.3; worktree `.claude/worktrees/al2-wall`, branch `al2-wall`, cut there |
| wall | this worktree only; no push, `--amend`, rebase, merge, install or version bump; no `make` (the join runs the gate); no `claude` started, real or `tests/fake-claude`: every test runs its own fake in a temp home on a PATH built from nothing; the real `sops` and `age-keygen` never run; no key read, printed or copied; nothing leaves the machine; no relay verb or binary |
| may touch | `plugin/lib/apilane/wall.py`, `key.py`, `probe.py`, `stubapi.py`; `tests/test_al2_wall.py`; this packet; a charter under `history/sittings/`. Not `apilane/__init__.py` (al1's), `tests/fake-claude`, the `Makefile`, `.hygiene-allow`, `plugin.json`, the dispatcher, the hooks |
| acceptance | `python3 tests/test_al2_wall.py WallReadTest`; `python3 tests/test_al2_wall.py WallWriteTest`; `python3 tests/test_al2_wall.py WallSecretTest`; `python3 tests/test_al2_wall.py WallStartTest`; `python3 tests/test_al2_wall.py CheckDirsTest`; `python3 tests/test_al2_wall.py NetTest`; `python3 tests/test_al2_wall.py KeyTest`; `python3 tests/test_al2_wall.py StubTest`; `python3 tests/test_al2_wall.py ProbeTest`; `python3 tests/test_al2_wall.py ProbeArgvTest`; `python3 tests/test_al2_wall.py EnsureTest`; each again as `/usr/bin/python3`, each ends `OK` (baseline: the file does not exist; `ls plugin/lib/apilane` prints `No such file or directory`); `scripts/hygiene` exits 0; `scripts/doclint` exits 0 |
| verify | none in this row: the join runs `make check` through the gate queue, since the version check reds a branch that changes `plugin/` with no bump and the bump is the join's |
| budget | Level S1, `claude-opus-5-5` high; one commit per ruling group; stop at 90 tool calls with the act in flight committed |

## 1. What the source says

The owner's words: "I need a Fable designer to recover the claude fanout to API lane agents. I want this designed and brought up to the current standards of our existing plugins. [...] If the API lane is disabled we shouldn't see anything beyond what we see today."

## 2. Rulings

- R1. This row owns the four modules and the test above, nothing else. It prints nothing and holds no sentence a user reads: it raises an error with a `code` and `fields` (seams §1, §2). Until the join the package imports as a namespace.
- R2, the wall. One seam, one backend. `wall.backend()` is `"sandbox-exec"` on macOS where `/usr/bin/sandbox-exec` is an executable file, else `None`; `wall.wrap(argv, *, read, write, net, home)` raises `wall.platform` with no backend: the lane never runs unwalled. Every wrapper name, profile and macOS path stays in the backend's code, so a Linux backend changes `wall.py` alone. The profile allows by default, denies reads and writes under `/Users`, `/private/tmp`, `/Volumes` and the home (real and data-volume paths), re-allows `read` (and `argv[0]`'s folder) for reading and `write` for both, then denies the secret roots last: under the home, `.config/sops`, `.config/agentik/agents/secrets`, `.ssh`, `.gnupg`, `.aws`, `.config/gh`, `Library/Keychains`, `.claude`. `net="loopback"` denies the network and re-allows loopback. A path holding a quote or a newline is refused, never escaped.
- R3, the job's dirs. `wall.check_dirs(dirs, *, home)` returns real paths or raises `wall.dir` with `why` `root`, `home` (the home, or a folder holding it), `secret` (a secret root, inside one or holding one) or `missing`. Measured: a job dir that is the home's parent re-allowed a shell history file.
- R4, what the wall does not hide: the system's folders, `/opt` and `/Library`, the account's temp and cache folders under `/private/var/folders`, a plaintext secret inside a job dir, and a hard link inside a job dir to a file outside it (measured: it reads).
- R5, the key. `roots.store`, SOPS with age, the YAML key `anthropic_api_key` the old wrapper used. `key.store` pipes the value to `sops` on stdin, for the recipient given or the one `age-keygen -y` prints for the identity `sops` uses; this module never opens that identity. Written by a temp file and a rename, 0600 in a 0700 folder. `key.load`, `key.present`, `key.remove`. Codes `key.none`, `key.tools`, `key.decrypt`, `key.recipient`. An `ANTHROPIC_API_KEY` in the caller's environment is never read.
- R6, the stub. A loopback HTTP server on `127.0.0.1` and a port the system picks; it answers the messages endpoint, streamed or whole, with three turns that each ask for one `Read` and a closing text, and records each request's credential headers, tools offered and tool results.
- R7, the probe. `probe.run` runs the CLI once, 60 s at most, on the shard's own argv and environment builders, under `wrap(..., read=[job], write=[run_dir], net="loopback")`, with a made-up key new each run and the stub's base URL. Five checks: `key`, `tools`, `walled`, `restricted` (recorded, never deciding `ok`), `read`. A CLI that refuses `--restricted` beside `--bare` is run again without it and records `restricted` null. `<state>/probe.json` by a rename, 0600; its folders removed.
- R8, the pass. `probe.cli_version`, `probe.read`, `probe.passed` (an ok record for that exact version), `probe.ensure` (the record on disk when it passes, else `emit("probe.start")`, a run, and `probe.fail` when not ok).
- R9, no way out: under `net="loopback"` no request can leave the machine, whatever the CLI does with its base URL.

## 3. Interfaces

The seams page's §5, which this row builds as written: `wall.backend() -> str or None`; `wall.wrap(argv, *, read, write, net, home) -> list`; `wall.check_dirs(dirs, *, home) -> list`; `key.load(roots) -> str`, `key.present(roots) -> bool`, `key.store(value, *, roots, recipient=None)`, `key.remove(roots) -> bool`; `probe.cli_version(claude)`, `probe.read(roots)`, `probe.passed(roots, version)`, `probe.run(*, claude, roots, build_argv=None, build_env=None, wrap=None) -> dict`, `probe.ensure(..., emit=None) -> dict`; `probe.json` is `{"schema": "agentik.api.probe/1", "cli_version", "at", "ok", "restricted", "checks": [{"name", "ok", "detail"}]}`. `stubapi.Stub(reads)`: `start() -> base_url`, `stop()`, `requests`.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

A file over 8 KB whole; a relay ledger or a reference snapshot whole; anything under a `secrets` folder, a sops folder or a key store on this machine.

## 6. Report

The branch and its head; each acceptance line under both interpreters with its tally and any skip; how each test failed before its code; the choices made inside the rulings. Not built here: one shard's argv, environment and run (al1); the fan-out that calls `probe.ensure` (al3); the `api` verbs and the hidden prompt (al4); the first run of the probe on the real CLI (after the install); a wall off macOS (a later row behind this seam).
