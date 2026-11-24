#!/usr/bin/python3
"""The API lane's wall: one seam around a shard's process, a backend for each platform.

`backend()` names the wall proved on this platform, or None. `wrap(argv, ...)` returns the same
command behind that wall; it raises `wall.platform` where there is none, so the lane never runs
unwalled. `check_dirs(dirs, home=...)` returns each job dir's real path, or raises `wall.dir`.
Callers pass these few things and run what comes back: every wrapper name, profile and
platform path lives in a backend's section below, so a second backend changes this file alone.

The macOS backend (`sandbox-exec`) allows by default, then, by the write rule, denies every write
anywhere and re-allows writes to `/dev/null`, `/dev/tty` and `/dev/fd` alone; then it denies
every read and write under `/Users`, `/private/tmp`, `/Volumes` and the home (by real path and by
data-volume path), then re-allows the `read` folders and the folder of the command's own path for
reading and the `write` folders for reading and writing, then, by the `.git` rule, denies writes
to each `write` folder's own `.git` (the path alone where it is a file or a link, the path and
all under it where it is a folder; read once by `lstat`, never followed), then denies the secret
roots under the home last, so a later rule keeps a secret root inside a re-allowed folder
denied. So a shard writes its `write` folders and nothing else, for every type, and cannot
repoint its worktree's link at another repository. `net="loopback"` denies the network and
re-allows loopback alone, so no request can leave the machine.

What the wall does not hide, said once: the system's folders, `/opt` and `/Library`, the
account's temp and cache folders under `/private/var/folders` (readable, no longer writable), a
plaintext secret that sits inside a job dir, and a hard link inside a job dir to a file outside
it (measured: it reads). A `.git` made deeper in a `write` folder is not the wall's to stop.

The Linux backend (`bwrap`, bubblewrap) is proved where `/usr/bin/bwrap` is an executable file
and one trial namespace starts. It gives the command its own mount, process, IPC, host-name and
(where the kernel allows) cgroup namespaces, a fresh `/proc` and `/dev`, a new session and death
with its parent; it binds the root read-only, then replaces by empty folders the home, `/tmp`,
`/run` and `/var` whole (`/var/tmp` empty inside it), `/home`, `/media`, `/mnt` and `/nix` by
their real paths where they exist, and every other real folder directly under `/` but the short
system list below (`_BWRAP_KEEP`); it binds back read-only what a CLI needs inside those (the
nix store, and a trust file that `/etc/ssl` links into `/var`), the `read` folders and the
folder of the command's own path, and read-write the `write` folders, at their own paths, the
shallower mount first, so a deeper one wins; a `write` folder's own `.git`, where one is there,
is bound read-only over itself after the folder (the `.git` rule); and last it covers each
secret root a shard could still see by its real path, a folder by an empty one, a file by
`/dev/null`. The secret roots are
the list below and the platform's keyring. `net="loopback"` gives the command a network
namespace whose one interface is its own loopback; `net="all"` shares the host's, and where
`/etc/resolv.conf` points into `/run` or `/var` binds back read-only its folder, or the file
alone where it lies directly in one of those two, so names still resolve.

What it does not hide, said once: the system list's folders (`/etc`, `/usr`, `/opt`, `/snap`,
`/sys`) and the nix store, read-only; a socket file a shard may connect to, since a read-only
bind does not stop a connect: one under `/usr`, `/opt`, `/etc`, `/snap` or the nix store, and
one inside a `read` or `write` folder; under `net="all"` the resolver's own sockets in its folder
and the host's abstract sockets; a plaintext secret inside a job dir; and a hard link inside a
job dir to a file outside it. The emptied folders are writable inside and thrown away after.
"""

import os
import stat
import subprocess
import sys

# Under the home: the folders no shard may read, whatever folder it is handed.
SECRET_ROOTS = (".config/sops", ".config/agentik/agents/secrets", ".ssh", ".gnupg", ".aws",
                ".config/gh", "Library/Keychains", ".claude")
NETS = ("all", "loopback")


class WallError(Exception):
    """An error a user may see: `code` and `fields`; `str()` is the code."""

    def __init__(self, code, **fields):
        super().__init__(code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


# -- the seam ----------------------------------------------------------------------------------

def backend():
    """The name of the wall proved on this platform, or None."""
    if sys.platform == "darwin" and _sandbox_exec_ready():
        return "sandbox-exec"
    if sys.platform.startswith("linux") and _bwrap_ready():
        return "bwrap"
    return None


def wrap(argv, *, read, write, net, home):
    """`argv` behind this platform's wall, as an argv to run as it is."""
    name = backend()
    if name is None:
        raise WallError("wall.platform", platform=sys.platform)
    argv = list(argv)
    if not argv or not os.path.isabs(argv[0]) or os.path.realpath(argv[0]) != argv[0]:
        raise ValueError("wall.wrap: argv[0] must be an absolute real path")
    if net not in NETS:
        raise ValueError("wall.wrap: net is %r, not one of %s" % (net, ", ".join(NETS)))
    if name == "bwrap":
        return _bwrap_wrap(argv, read=read, write=write, net=net, home=home)
    return _sandbox_exec_wrap(argv, read=read, write=write, net=net, home=home)


def check_dirs(dirs, *, home):
    """Each job dir's real path; `wall.dir` for one the wall cannot guard."""
    home_real = _canon(home)
    secrets = _secret_paths(home_real)
    out = []
    for d in dirs:
        real = _canon(d)
        if not os.path.isdir(real):
            raise WallError("wall.dir", dir=d, why="missing")
        if real == "/":
            raise WallError("wall.dir", dir=d, why="root")
        if _within(home_real, real):
            raise WallError("wall.dir", dir=d, why="home")
        if any(_within(real, s) or _within(s, real) for s in secrets):
            raise WallError("wall.dir", dir=d, why="secret")
        out.append(real)
    return out


def _within(path, folder):
    """True when `path` is `folder` or lies under it."""
    return path == folder or path.startswith(folder.rstrip("/") + "/")


def _secret_paths(home_real):
    """Each secret root by its path under the real home, and by its own real path."""
    out = []
    for rel in SECRET_ROOTS:
        p = os.path.join(home_real, rel)
        for q in (p, _canon(p)):
            if q not in out:
                out.append(q)
    return out


# -- the macOS backend: sandbox-exec -------------------------------------------------------------

_SANDBOX_EXEC = "/usr/bin/sandbox-exec"
_DATA_VOLUME = "/System/Volumes/Data"
_DENIED = ("/Users", "/private/tmp", "/Volumes")


def _sandbox_exec_ready():
    return os.path.isfile(_SANDBOX_EXEC) and os.access(_SANDBOX_EXEC, os.X_OK)


def _canon(path):
    """The real path, with a data-volume prefix taken off where it names the same file."""
    real = os.path.realpath(path)
    if real.startswith(_DATA_VOLUME + "/"):
        bare = real[len(_DATA_VOLUME):]
        try:
            if os.path.samefile(real, bare):
                return bare
        except OSError:
            pass
    return real


def _both(path):
    """A path and its data-volume twin, both of which the kernel may report."""
    out = [path]
    if not path.startswith(_DATA_VOLUME + "/"):
        out.append(_DATA_VOLUME + path)
    return out


def _literal(path, kind="subpath"):
    for ch in path:
        if ch in '"\\' or ord(ch) < 0x20 or ord(ch) == 0x7f:
            raise ValueError("wall: a path holding a quote, a backslash or a control character "
                             "is refused: %r" % path)
    return '(%s "%s")' % (kind, path)


def _filters(paths, kind="subpath"):
    seen, out = set(), []
    for p in paths:
        for q in _both(p):
            if q not in seen:
                seen.add(q)
                out.append(_literal(q, kind))
    return " ".join(out)


# The write rule's devices, the only paths outside the `write` folders a shard may write.
_DEVICES = ('(literal "/dev/null")', '(literal "/dev/tty")', '(subpath "/dev/fd")')


def _git_kind(folder):
    """What a `write` folder's own `.git` is, by one `lstat` (a link is never followed): "folder",
    "file" (a file, a link or any other kind), or None where there is none."""
    try:
        st = os.lstat(os.path.join(folder, ".git"))
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError:
        return "folder"
    return "folder" if stat.S_ISDIR(st.st_mode) else "file"


def _git_rules(writes):
    """The `.git` rule's filters for the `write` folders: a literal for each `.git`, a subpath too
    where it is a folder; '' where none holds one."""
    out = []
    for w in writes:
        kind = _git_kind(w)
        if kind is None:
            continue
        git = os.path.join(w, ".git")
        out.append(_filters([git], "literal"))
        if kind == "folder":
            out.append(_filters([git]))
    return " ".join(out)


def _sandbox_exec_wrap(argv, *, read, write, net, home):
    home_real = _canon(home)
    reads = [_canon(p) for p in read] + [os.path.dirname(argv[0])]
    writes = [_canon(p) for p in write]
    rules = ["(version 1)", "(allow default)",
             '(deny file-write* (subpath "/"))',
             "(allow file-write* %s)" % " ".join(_DEVICES),
             "(deny file-read* file-write* %s)" % _filters(list(_DENIED) + [home_real])]
    if reads:
        rules.append("(allow file-read* %s)" % _filters(reads))
    if writes:
        rules.append("(allow file-read* file-write* %s)" % _filters(writes))
    gits = _git_rules(writes)
    if gits:
        rules.append("(deny file-write* %s)" % gits)
    rules.append("(deny file-read* file-write* %s)" % _filters(_secret_paths(home_real)))
    if net == "loopback":
        rules.append("(deny network*)")
        rules.append('(allow network* (remote ip "localhost:*"))')
    return [_SANDBOX_EXEC, "-p", "\n".join(rules)] + argv


# -- the Linux backend: bwrap (bubblewrap) -------------------------------------------------------

_BWRAP = "/usr/bin/bwrap"
# Emptied always (the home is added by its real path): the temp folder, and the runtime folder and
# `/var` whole, with every socket file in them (a container daemon's, the system bus, the
# account's agent, lxd's, sssd's, a `/var/run` that is a real folder): a read-only bind does not
# stop a connect, so a folder that may hold one is emptied, never kept. `/var/tmp` comes back
# empty inside it, as before.
_BWRAP_RUN = "/run"
_BWRAP_VAR = "/var"
_BWRAP_EMPTY = ("/tmp",)
# Emptied where they exist, by their real paths, so a link to a disk elsewhere is followed: the
# other homes and the mounted disks.
_BWRAP_EMPTY_IF = ("/home", "/media", "/mnt")
# `/nix` is emptied where it exists (its daemon's socket is under `/nix/var`) and its store alone
# comes back, read-only, since a CLI installed through nix runs from there.
_BWRAP_NIX = "/nix"
# The folders directly under `/` that stay, read-only: the system's own (`/etc`, `/sys`, and the
# program and library folders where they are real, not links into `/usr`), the ones a CLI is
# installed in (`/usr` with `/usr/local`, `/opt`, `/snap`, whose mounts are read-only images),
# and `/dev` and `/proc`, made fresh. Every other real folder there (`/var`, `/nix`, `/srv`,
# `/boot`, `/root`, a machine's own `/data`) is emptied, and what is bound comes back after it.
_BWRAP_KEEP = ("bin", "dev", "etc", "lib", "lib32", "lib64", "libx32", "opt", "proc", "sbin",
               "snap", "sys", "usr")
# What a CLI needs under `/var` to start and to reach the provider, bound back read-only after
# `/var` is emptied: the trust files a TLS client reads, where one is a link out of `/etc/ssl`
# into `/var` (openSUSE's `/etc/ssl/certs` and `/etc/ssl/ca-bundle.pem` point into
# `/var/lib/ca-certificates`), by the link's target. Nothing else: the CLI and its runtime start
# from the home and `/usr` (the target's are files there, or links into `/usr/share`).
_BWRAP_TLS = ("/etc/ssl/certs", "/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem",
              "/etc/ssl/ca-bundle.pem")
# Where `/etc/resolv.conf` points into `/run` or `/var`, what of it is bound back under net="all".
_RESOLV = "/etc/resolv.conf"
# al2's secret roots and this platform's place for the keychain.
_BWRAP_SECRET_ROOTS = SECRET_ROOTS + (".local/share/keyrings",)
_BWRAP_FLAGS = ("--die-with-parent", "--new-session", "--unshare-pid", "--unshare-ipc",
                "--unshare-uts", "--unshare-cgroup-try")
_TRIAL_TIMEOUT = 10
_TRIED = {}


def _bwrap_ready():
    """`_BWRAP` is an executable file and one namespace with a shard's flags starts; kept."""
    if _BWRAP not in _TRIED:
        _TRIED[_BWRAP] = _bwrap_trial(_BWRAP)
    return _TRIED[_BWRAP]


def _bwrap_trial(path):
    if not (os.path.isfile(path) and os.access(path, os.X_OK)):
        return False
    argv = ([path] + list(_BWRAP_FLAGS) + ["--unshare-net", "--ro-bind", "/", "/",
                                            "--dev", "/dev", "--proc", "/proc",
                                            "--tmpfs", "/tmp", "--", "/bin/true"])
    try:
        done = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin"},
                              timeout=_TRIAL_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def _bwrap_top(names=None):
    """Every real folder directly under `/` off `_BWRAP_KEEP`, by path. `names` stands in for
    the root's listing of real folders (a test cannot make a folder under `/`)."""
    if names is None:
        try:
            listed = os.listdir("/")
        except OSError:
            listed = []
        names = [n for n in listed
                 if os.path.isdir("/" + n) and not os.path.islink("/" + n)]
    return sorted("/" + n for n in names if n not in _BWRAP_KEEP)


def _bwrap_whole():
    """The folders emptied whole at their top, by their real paths: the runtime folder and `/var`."""
    return [os.path.realpath(p) for p in (_BWRAP_RUN, _BWRAP_VAR)]


def _bwrap_resolver():
    """What is bound back under net="all" for `/etc/resolv.conf`, where it points into a folder
    emptied whole: the file alone where it lies directly in that folder (a bind of the folder
    itself would bring back all of `/run`), else its own folder; None where it points elsewhere."""
    real = os.path.realpath(_RESOLV)
    if real == _RESOLV or not os.path.isfile(real):
        return None
    for whole in _bwrap_whole():
        if real != whole and _within(real, whole):
            folder = os.path.dirname(real)
            return real if folder == whole else folder
    return None


def _bwrap_back():
    """What the wall binds back read-only inside a folder it empties, by real path: each trust
    file of `_BWRAP_TLS` that is a link into `/var`, and the nix store where `/nix` is a folder."""
    var = os.path.realpath(_BWRAP_VAR)
    out = []
    for p in _BWRAP_TLS:
        real = os.path.realpath(p)
        if real != var and _within(real, var) and os.path.exists(real) and real not in out:
            out.append(real)
    store = os.path.join(_BWRAP_NIX, "store")
    if os.path.isdir(_BWRAP_NIX) and os.path.isdir(store):
        out.append(os.path.realpath(store))
    return out


def _depth(path):
    return 0 if path == "/" else path.rstrip("/").count("/")


def _bwrap_wrap(argv, *, read, write, net, home):
    home_real = _canon(home)
    emptied = []
    for p in list(_BWRAP_EMPTY) + [_BWRAP_RUN, _BWRAP_VAR, os.path.join(_BWRAP_VAR, "tmp")] \
            + [p for p in _BWRAP_EMPTY_IF + (_BWRAP_NIX,) if os.path.isdir(p)] + _bwrap_top():
        q = os.path.realpath(p)
        if q not in emptied:
            emptied.append(q)
    if home_real not in emptied:
        emptied.append(home_real)
    reads = [_canon(p) for p in read] + [os.path.dirname(argv[0])] + _bwrap_back()
    resolver = _bwrap_resolver() if net == "all" else None
    if resolver:
        reads.append(resolver)
    writes = [_canon(p) for p in write]
    # bwrap mounts in argument order: the shallower first, an empty folder before a bind at the
    # same path, a write after a read, so the deeper and the later win
    ops = [(d, 0, "--tmpfs") for d in emptied] + [(d, 1, "--ro-bind") for d in reads] \
        + [(d, 2, "--bind") for d in writes] \
        + [(os.path.join(d, ".git"), 3, "--ro-bind") for d in writes if _git_kind(d)]
    ops.sort(key=lambda op: (_depth(op[0]), op[1]))
    out = [_BWRAP] + list(_BWRAP_FLAGS)
    if net == "loopback":
        out.append("--unshare-net")
    out += ["--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"]
    seen = set()
    for path, _, flag in ops:
        if (path, flag) in seen:
            continue
        seen.add((path, flag))
        out += [flag, path] if flag == "--tmpfs" else [flag, path, path]
    # last, each secret root a shard could still see, by its real path: inside a bound folder,
    # or outside every emptied one (a link under the home that points out of it)
    bound, covered = reads + writes, []
    for rel in _BWRAP_SECRET_ROOTS:
        q = _canon(os.path.join(home_real, rel))
        if q in covered or not os.path.exists(q):
            continue
        if any(_within(q, b) for b in bound) or not any(_within(q, e) for e in emptied):
            covered.append(q)
            out += ["--tmpfs", q] if os.path.isdir(q) else ["--ro-bind", "/dev/null", q]
    return out + ["--"] + argv
