#!/usr/bin/python3
"""The API lane's wall: one seam around a shard's process, one backend today.

`backend()` names the wall proved on this platform, or None. `wrap(argv, ...)` returns the same
command behind that wall; it raises `wall.platform` where there is none, so the lane never runs
unwalled. `check_dirs(dirs, home=...)` returns each job dir's real path, or raises `wall.dir`.
Callers pass these few things and run what comes back: every wrapper name, profile and
platform path lives in a backend's section below, so a second backend changes this file alone.

The macOS backend (`sandbox-exec`) allows by default, then denies every read and write under
`/Users`, `/private/tmp`, `/Volumes` and the home (by real path and by data-volume path), then
re-allows the `read` folders and the folder of the command's own path for reading and the `write`
folders for reading and writing, then denies the secret roots under the home last, so a later
rule keeps a secret root inside a re-allowed folder denied. `net="loopback"` denies the network
and re-allows loopback alone, so no request can leave the machine.

What the wall does not hide, said once: the system's folders, `/opt` and `/Library`, the
account's temp and cache folders under `/private/var/folders`, a plaintext secret that sits
inside a job dir, and a hard link inside a job dir to a file outside it (measured: it reads).
"""

import os
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


def _literal(path):
    for ch in path:
        if ch in '"\\' or ord(ch) < 0x20 or ord(ch) == 0x7f:
            raise ValueError("wall: a path holding a quote, a backslash or a control character "
                             "is refused: %r" % path)
    return '(subpath "%s")' % path


def _filters(paths):
    seen, out = set(), []
    for p in paths:
        for q in _both(p):
            if q not in seen:
                seen.add(q)
                out.append(_literal(q))
    return " ".join(out)


def _sandbox_exec_wrap(argv, *, read, write, net, home):
    home_real = _canon(home)
    reads = [_canon(p) for p in read] + [os.path.dirname(argv[0])]
    writes = [_canon(p) for p in write]
    rules = ["(version 1)", "(allow default)",
             "(deny file-read* file-write* %s)" % _filters(list(_DENIED) + [home_real])]
    if reads:
        rules.append("(allow file-read* %s)" % _filters(reads))
    if writes:
        rules.append("(allow file-read* file-write* %s)" % _filters(writes))
    rules.append("(deny file-read* file-write* %s)" % _filters(_secret_paths(home_real)))
    if net == "loopback":
        rules.append("(deny network*)")
        rules.append('(allow network* (remote ip "localhost:*"))')
        rules.append('(allow network* (local ip "localhost:*"))')
    return [_SANDBOX_EXEC, "-p", "\n".join(rules)] + argv
