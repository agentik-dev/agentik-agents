"""A process's start time, so a recycled pid is never read as alive.

One implementation on every platform: `ps -o lstart= -p <pid>`, which macOS and Linux
both answer, in the C locale so the text compares. The time is to the second.
"""
import os
import subprocess

_PS = next((p for p in ("/bin/ps", "/usr/bin/ps") if os.access(p, os.X_OK)), "ps")


def started(pid):
    """The process's start time as `ps` prints it, or None when there is no such process."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    try:
        out = subprocess.run([_PS, "-o", "lstart=", "-p", str(pid)],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             env={"PATH": "/bin:/usr/bin", "LC_ALL": "C"},
                             universal_newlines=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    text = " ".join(out.stdout.split())
    if out.returncode != 0 or not text:
        return None
    return text


def alive(pid, started_at):
    """True only when `pid` lives and started at `started_at`."""
    if not started_at:
        return False
    now = started(pid)
    return now is not None and now == " ".join(str(started_at).split())
