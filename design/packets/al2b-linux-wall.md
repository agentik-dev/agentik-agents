# Packet al2b-linux-wall: a second wall, bubblewrap, behind the seam the first wall built

The hq's brief for row al2b: the API lane's wall on Linux, so the lane can turn on there. Built on macOS, where no namespace can be made: the Linux classes are written here and run on a Linux machine afterwards; the tests that run here hold the argv, the trial, the `sh` side and the launcher.

| item | value |
|---|---|
| from | the hq's row al2b (design/21 §5 items 13, 29, 30, risk 6, §9, Amendment 2) and its brief's amendment |
| pin | main 2b81b47, plugin 1.9.0 (al6-join and al7-detach merged); worktree `.claude/worktrees/al2b-linux-wall`, branch `al2b-linux-wall`; nothing linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install, version or plugin update; no `claude`, real or `tests/fake-claude`: every test writes its own fake in a temp home; no key read, no real `sops`, no network; no relay verb; `make` only through the gate queue |
| may touch | `plugin/lib/apilane/wall.py` (the second backend), `probe.py` (R4), `stubapi.py` (`start` takes a port, default 0, for R4's launcher); new `plugin/lib/apilane/walled.sh`, `tests/test_al2b_linux.py`, `tests/test_al2b_argv.py`; `tests/test_al2_wall.py`'s no-backend test (it also hides the bwrap path, since Linux now has a backend); the `Makefile`'s two test lists; this packet; a charter |
| untouched | `argv.py`, `env.py`, `run.py`, `job.py`, `ledger.py`, `fanout.py`, `paths.py`, `config.py`, `report.py`, `hook.py`, `cli.py`, `messages.py`, `prefilter.sh`, the dispatcher and its stub, `tests/test-dispatch.sh`, `plugin.json` |
| acceptance | section 6 |
| verify | `make check`, once, last, through the gate queue; `plugin-version-check` reds the branch, since 1.10.0 is the second round's |
| budget | a commit each: this packet and the charter; the tests seen red; the backend and the `sh` side; the probe's launcher; the lists |

## 1. What the source says

The owner: "Also, the work machine is invoking [the old fan-out name] directly, so see if you can create a better mechanism." That machine is Linux, the one machine that uses the fan-out today. The lane was proved on macOS, where its wall is the system's own; on Linux it refuses to turn on, by design, because it has no wall it has proved there.

The target: Ubuntu 24.04, kernel 6.8, a KVM guest; `/usr/bin/bwrap` 0.9.0, and an ordinary user may make the namespace there (the release restricts it by default, so the trial decides, never the file); `/usr/bin/python3` 3.12.3; the CLI inside the home (`~/.local/bin/claude`, a link into `~/.local/share/claude/versions/`).

Baseline at 2b81b47, here: `wall.backend()` prints `sandbox-exec`; `tests/test_al2_wall.py` ends `OK` (34) under both interpreters; the two new tests and `walled.sh` do not exist.

## 2. Rulings

- R1: the table's "may touch"; the seam, `wall.backend()` and `wall.wrap(argv, *, read, write, net, home)`, as al2 built it; no caller changes.
- R2, the backend. `wall.backend()` is `"bwrap"` on Linux where `/usr/bin/bwrap` is an executable file and one trial namespace starts (a shard's flags around `/bin/true`, 10 s at most, kept for the process); else `None`. `wall.wrap` then returns a `bwrap` argv: `--die-with-parent`, `--new-session`, `--unshare-pid` with a fresh `/proc` and `/dev`; the root bound read-only; the account's home, `/tmp` and `/var/tmp` replaced by empty folders, and `/home`, `/media`, `/mnt`, `/run/media` and `/run/user` (the account's agent and bus sockets) where they exist, as macOS denies `/Users` and `/Volumes`; each `read` folder and the folder of `argv[0]` bound read-only at its own path; each `write` folder bound read-write; and last, every secret root that a shard could still see covered by an empty one. `"loopback"` adds `--unshare-net`, whose one interface is its own loopback. Every path is an argument of its own.
- R2's order. `bwrap` mounts in the order of its arguments, so the empty folders and the binds are sorted by depth, the shallower first, an empty folder before a bind at the same path: a bound folder that holds an emptied one (`/var`) is emptied again inside. The covers come last.
- R2's covers. The secret roots are al2's list, plus the platform's own place for the keychain, `.local/share/keyrings`. Each is covered by its real path (a link inside the home resolves there), when it exists and lies inside a bound folder or outside every emptied one: a folder by an empty one, a file by `/dev/null`. A secret root that does not exist is left alone, so a cover never makes a folder on the disk.
- R2's CLI. The seam asks for `argv[0]` by its real path, so the folder bound is the CLI's resolved one. The macOS profile re-allows nothing else under the home, nor does this one: the CLI's settings are in `CLAUDE_CONFIG_DIR`, in the run folder.
- R3, as on macOS. `wall.check_dirs` is unchanged. What the wall does not hide on Linux, said once in `wall.py`'s docstring: the system's folders (`/etc`, `/usr`, `/opt`, `/var` but its temp folder, `/srv`, `/sys`, `/run` but the two above) read-only, a plaintext secret inside a job dir, a hard link inside a job dir to a file outside it, and under `net="all"` the host's abstract sockets. The emptied folders are writable inside the wall and thrown away at its end.
- R4, the probe. A network namespace has a loopback of its own, so the stub starts inside the wall. Where `probe.run` is handed the real `wall.wrap` and the backend is `"bwrap"` (or `inside` says so), it picks a free port, builds the argv and environment from the two builders with the base URL on it, and wraps one launcher, `/usr/bin/python3 -I -c <code> <lib> <out> <env names> <reads> -- <argv>`, with `<lib>` and the CLI's folder read and a folder of its own written. Inside, the launcher starts the stub on that port, runs the CLI on its stdin and on the environment's named variables alone, writes the stub's requests to `<out>`, and exits with the CLI's exit. The five checks and `probe.json` do not change. A stand-in `wrap` keeps the stub outside; the macOS path does not change.
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
| 7 | here | `A BwrapArgvTest`; `A TrialTest`; `A WalledShTest`; `A LauncherTest` | `OK`: R2's argv and order, the backend forced; a stand-in `bwrap` absent, failing, passing; `walled.sh` with stand-in paths; the stub first, the builders' argv and environment, the CLI's exit |
| 8 | both | every suite `make test` names | each `OK`; on Linux the macOS wall's tests skip |
| 9 | here | hygiene; doclint; `make check` | exit 0 but `plugin-version-check` |

Each test of lines 1 to 7 is written first and seen to fail: here, the lines of `A` fail, and the classes of `L` skip.
