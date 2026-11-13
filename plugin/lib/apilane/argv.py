"""The shard's command line, and the CLI it starts (design/21 items 28, 29; §9 R1-F5).

The argv is constructed, never filtered: there is no pass-through, so no caller flag can
widen it. The prompt travels on stdin and is never an argument; no key, token or base URL
is ever an argument. Claude Code resolves a repeated flag first-wins, so each flag is
written once.
"""
import math
import os

from . import types as _types

TOOLS = " ".join(_types.TOOLS)

# --add-dir does not confine Read, so the highest-value credential paths are denied for
# Read, Grep and Glob as a second layer behind --tools (the old wrapper's list, as it was).
# The kernel wall is the boundary; this is defence in depth. '~/...' is home-relative and
# '//...' absolute in Claude Code's rule syntax.
DENY_PATHS = (
    "~/.ssh/**",
    "~/.gnupg/**",
    "~/.aws/**",
    "~/.config/gh/**",
    "~/.kube/**",
    "~/.docker/**",
    "~/.netrc",
    "~/.config/claude-code/**",
    "~/.claude/**",
    "~/.claude.json",
    "~/.config/sops/**",
    "~/.git-credentials",
    "~/.npmrc",
    "~/.pypirc",
    "~/.config/gcloud/**",
    "~/.password-store/**",
    "~/.local/share/keyrings/**",
    "//proc/**",
)

# The flags a built argv must carry; a missing one is a bug in this module.
INVARIANT = ("--tools", "--allowedTools", "--disallowedTools", "--permission-mode",
             "--max-budget-usd", "--output-format")


class ClaudeNone(Exception):
    """No executable `claude` on the path searched."""

    code = "claude.none"

    def __init__(self, path):
        Exception.__init__(self, self.code)
        self.fields = {"path": path}

    def __str__(self):
        return self.code


def deny_reads():
    return " ".join("%s(%s)" % (t, p) for p in DENY_PATHS for t in _types.TOOLS)


def _value(flag, val):
    if not isinstance(val, str) or not val or val.startswith("-"):
        raise ValueError("%s: a value may not be empty or begin with '-'" % flag)
    return val


def _ceiling(val):
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError("--max-budget-usd: not a number")
    if not math.isfinite(val) or val < 0:
        raise ValueError("--max-budget-usd: not a non-negative finite number")
    return "%.4f" % val


def build(shard, *, claude, dirs, ceiling_usd, run_dir, restricted=True):
    """The child's argv: `claude` first, `--bare` second, the type's flags, then the dirs."""
    t = _types.TYPES.get(getattr(shard, "type", None))
    if t is None:
        raise ValueError("type: not one of %s" % ", ".join(sorted(_types.TYPES)))
    if not os.path.isabs(_value("claude", claude)) or not os.path.isabs(
            _value("run_dir", run_dir)):
        raise ValueError("claude and run_dir are absolute paths")
    argv = [claude, "--bare",
            "--tools", TOOLS,
            "--allowedTools", TOOLS,
            "--disallowedTools", deny_reads(),
            "--permission-mode", "dontAsk",
            "--permission-prompts", "none",
            "--max-budget-usd", _ceiling(ceiling_usd),
            "--exclude-dynamic-system-prompt-sections",
            "--output-format", "json",
            "--no-session-persistence"]
    if restricted:
        argv.append("--restricted")
    argv += ["--model", t.model, "--effort", _types.EFFORT[t.name]]
    if t.schema is not None:
        argv += ["--json-schema", t.schema]
    argv += ["--append-system-prompt", _types.ROLES[t.name], "--print"]
    for d in dirs:
        if not os.path.isabs(_value("--add-dir", d)):
            raise ValueError("--add-dir: %s is not an absolute path" % d)
        argv += ["--add-dir", d]
    for flag in INVARIANT:
        if flag not in argv:
            raise AssertionError("argv built without %s" % flag)
    return argv


def find_claude(path=None):
    """The real path of the first `claude` on `path` that resolves to an executable file.

    Under the wall the PATH name, often a link inside the denied home, does not start;
    the resolved path does, so the resolved path is what a shard runs.
    """
    if path is None:
        path = os.environ.get("PATH", "")
    for d in path.split(os.pathsep):
        if not d:
            continue
        real = os.path.realpath(os.path.join(d, "claude"))
        if os.path.isfile(real) and os.access(real, os.X_OK):
            return real
    raise ClaudeNone(path)
