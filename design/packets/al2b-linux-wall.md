# Packet al2b-linux-wall: a second wall, bubblewrap, behind the seam the first wall built

The hq's brief for row al2b, in this repo's packet shape: the API lane's wall on Linux, so the lane can turn on there. Built on macOS, where no Linux namespace can be made: the Linux classes are written here and run on a Linux machine afterwards; the tests that can run here hold the argv, the trial, the `sh` side and the probe's launcher.

| item | value |
|---|---|
| from | the hq's row al2b (design/21 §5 items 13, 29, 30, risk 6, §9; its Amendment 2), and the brief's own amendment: built on the Mac, proved on Linux afterwards |
| pin | main 2b81b47, plugin 1.9.0 (al6-join and al7-detach merged); worktree `.claude/worktrees/al2b-linux-wall`, branch `al2b-linux-wall`; nothing linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install, version or plugin update; no `claude`, real or `tests/fake-claude`: every test writes its own fake in a temp home; no key read, no real `sops`, no network; no relay verb; `make` only through the gate queue |
| may touch | `plugin/lib/apilane/wall.py` (the second backend), `probe.py` (R4), `stubapi.py` (`start` takes a port, default 0, for R4's launcher); new `plugin/lib/apilane/walled.sh`, `tests/test_al2b_linux.py`, `tests/test_al2b_argv.py`; `tests/test_al2_wall.py`'s no-backend test (it also hides the bwrap path, since Linux now has a backend); the `Makefile`'s two test lists; this packet; a charter |
| untouched | `argv.py`, `env.py`, `run.py`, `job.py`, `ledger.py`, `fanout.py`, `paths.py`, `config.py`, `report.py`, `hook.py`, `cli.py`, `messages.py`, `prefilter.sh`, the dispatcher and its stub, `tests/test-dispatch.sh`, `plugin.json` |
| acceptance | section 6 |
| verify | `make check`, once, last, through `agentik session gate run`; `plugin-version-check` reds this branch, since the version (1.10.0) is the second round's, by the hq's ruling |
| budget | a commit each: this packet and the charter; the tests seen red; the backend and the `sh` side; the probe's launcher; the lists |

## 1. What the source says

The owner: "Also, the work machine is invoking [the old fan-out name] directly, so see if you can create a better mechanism." That machine is Linux, the one machine that uses the fan-out today. The lane was proved on macOS, where its wall is the system's own; on Linux it refuses to turn on, by design, because it has no wall it has proved there.

The target's facts, as the hq read them: Ubuntu 24.04, kernel 6.8, x86_64, a KVM guest; `/usr/bin/bwrap`, bubblewrap 0.9.0, and an ordinary user may make the namespace there (that release restricts unprivileged user namespaces by default, so the trial namespace decides, never the file's presence); `landlock` among the kernel's modules; `/usr/bin/python3` 3.12.3; the CLI inside the home (`~/.local/bin/claude`, a link to a file under `~/.local/share/claude/versions/`).

Baseline at 2b81b47, on this Mac: `wall.backend()` prints `sandbox-exec`; `tests/test_al2_wall.py` ends `OK` (34 tests) under both interpreters; `tests/test_al2b_linux.py`, `tests/test_al2b_argv.py` and `plugin/lib/apilane/walled.sh` do not exist.

## 2. Rulings

- R1, what is owned: the table's "may touch". The seam is `wall.backend() -> str or None` and `wall.wrap(argv, *, read, write, net, home) -> list`; every caller passes those five things and runs what comes back. No caller changes.
- R2, the backend. `wall.backend()` is `"bwrap"` on Linux where `/usr/bin/bwrap` is an executable file and one trial namespace starts (the same flags a shard gets, around `/bin/true`, 10 s at most, its result kept for the process); else `None`, and the lane goes on refusing. `wall.wrap` then returns a `bwrap` argv: `--die-with-parent`, `--new-session` (no terminal to write to), `--unshare-pid` with a fresh `/proc` (no other process's files or environment) and a fresh `/dev`; the root bound read-only; the account's home, `/tmp` and `/var/tmp` replaced by empty folders, and `/home`, `/media`, `/mnt`, `/run/media` and `/run/user` (the account's agent and bus sockets) where they exist, as macOS denies `/Users` and `/Volumes`; each `read` folder and the folder of `argv[0]` bound read-only at its own path; each `write` folder bound read-write; and last, every secret root that a shard could still see covered by an empty one. `net="all"` shares the network; `"loopback"` adds `--unshare-net`: a namespace whose one interface is its own loopback. Every path is an argument of its own, never text in a shell line.
- R2's order. `bwrap` mounts in the order of its arguments, so the empty folders and the binds are sorted by depth, the shallower first, an empty folder before a bind at the same path: an empty home comes before what is bound back inside it, and a bound folder that holds an emptied one (a `read` folder `/var`) is emptied again inside. The covers come after every bind.
- R2's covers. The secret roots are al2's list, plus the platform's own place for the keychain, `.local/share/keyrings`. Each is covered by its real path (a link inside the home resolves there), when it exists and lies inside a bound folder or outside every emptied one: a folder by an empty one, a file by `/dev/null`. A secret root that does not exist is left alone, so a cover never makes a folder on the disk.
- R2's CLI. The seam already asks for `argv[0]` by its real path, so the folder bound is the CLI's resolved folder (`~/.local/share/claude/versions/`), which is not a secret root. The macOS profile re-allows nothing else under the home, so neither does this one: the CLI's settings are in `CLAUDE_CONFIG_DIR` inside the run folder.
- R3, as on macOS. `wall.check_dirs` is unchanged. What the wall does not hide on Linux, said once in `wall.py`'s docstring: the system's folders (`/etc`, `/usr`, `/opt`, `/var` but its temp folder, `/srv`, `/sys`, `/run` but the two above) read-only, a plaintext secret inside a job dir, a hard link inside a job dir to a file outside it, and under `net="all"` the host's abstract sockets. The emptied folders are writable inside the wall and thrown away at its end.
- R4, the probe. A network namespace has a loopback of its own, so the stub must start inside the wall. Where `probe.run` is handed the real `wall.wrap` and `wall.backend()` is `"bwrap"` (or its `inside` argument says so), it picks a port free here, builds the shard's argv and environment from the two builders with the base URL on that port, and wraps one launcher: `/usr/bin/python3 -I -c <code> <lib> <out> <reads> -- <the CLI's argv>`. Inside the wall the launcher starts the stub on that port, runs the CLI with its own environment and stdin unchanged, stops the stub, writes the stub's requests to `<out>` in a folder of its own (bound read-write beside the run folder; `<lib>` bound read-only), and exits with the CLI's exit. The probe reads the requests back; the five checks and `probe.json` do not change. A stand-in `wrap` (al2's tests) keeps the stub outside, as before; the macOS path does not change.
- R5, the `sh` side. `walled.sh`, POSIX `sh`, redefines `apilane_walled` as true where `/usr/bin/sandbox-exec` or `/usr/bin/bwrap` is an executable file, by `[` alone (no fork); the two paths are variables set when the file is sourced, so a test can aim them. `prefilter.sh` already sources it. Where the file is there but the trial fails (a release that restricts the namespace), the two differ: the dispatcher hands the verb to the lane, and the user meets the lane's own platform line, exit 2, not the stub.
- Not built in this round: R6 (the stub's removal) and R7 (1.10.0), and acceptance lines 8 and the stub's part of 9; both wait on the Linux proof.

## 3. Interfaces

The seam as al2 built it, unchanged. `probe.run(..., inside=None)` and `probe.ensure(..., inside=None)`: `None` is R4's rule. `probe.launch(args) -> int`, the launcher's body. `stubapi.Stub.start(port=0)`. `walled.sh`'s `apilane_walled`, `apilane_sandbox_exec`, `apilane_bwrap`.

## 4. Findings that name this row

al7's packet names this row for the Linux wall and the stub's removal. None in `NICE_TO_HAVE.md`.

## 5. Forbidden reads

The real config file, state folder and gate list; any key store, `secrets` or sops folder; a relay ledger.

## 6. Report

`L` is `tests/test_al2b_linux.py`, `A` is `tests/test_al2b_argv.py`; each runs as `python3 X <class>` and `/usr/bin/python3 X <class>`. On a platform where `wall.backend()` is not `"bwrap"` every class of `L` skips with one printed reason.

| # | where | command | holds when |
|---|---|---|---|
| 1 | Linux | `L WallReadTest` | `OK`: a canary under a temp home unreadable by its path, through a symlink in a job dir, from a child `sh`, by listing; a job file reads; a canary in `/tmp` outside the job dir unreadable |
| 2 | Linux | `L WallWriteTest`; `L WallSecretTest` | `OK`: the `write` folder takes a file, a `read` folder refuses one; with the temp home's `.config` a `read` folder, its sops folder stays unreadable |
| 3 | Linux | `L NetTest` | `OK`: under `"loopback"` a connect to the documentation range fails at once; a server started inside the wall is reached on loopback |
| 4 | Linux | `L ProbeTest` | `OK`, on the test's own fake CLI: the five checks pass with the stub inside the wall; each of al2's scripted failures fails the same check |
| 5 | Linux | `L ProbeArgvTest` | `OK`: the fake recorded exactly the argv and environment the stand-in builders returned |
| 6 | Linux | `L AgreeTest` | `OK`: `apilane_walled` is true and `wall.backend()` is `"bwrap"` |
| 7a | here | `A BwrapArgvTest` | `OK`: R2's argv and its order, with the backend forced |
| 7b | here | `A TrialTest` | `OK`: a stand-in `bwrap` absent, failing its trial, passing it |
| 7c | here | `A WalledShTest` | `OK`: `walled.sh` under `/bin/sh` with stand-in paths |
| 7d | here | `A LauncherTest` | `OK`: the stub starts first; the CLI's argv and environment are the builders'; the launcher's exit is the CLI's |
| 8 | both | every suite the `Makefile`'s `test` names | each ends `OK`; the macOS wall's tests skip on Linux with their reason |
| 9 | both | `scripts/hygiene`; `scripts/doclint`; `make check` through the queue here | exit 0 but `plugin-version-check`, red until 1.10.0 |

Each test of lines 1 to 7 is written first and seen to fail: here, the lines of `A` fail, and the classes of `L` skip.
