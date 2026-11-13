#!/usr/bin/python3
"""agents_plug: what agentik-agents prints so that the suite's `config`, `doctor` and `status`
can read it (packet ak7-plug-agents; the plug contract §3 to §5). The dispatcher runs it under
install-cli's interpreter as `agents_plug.py VERSION ARGS...`, ARGS one of `describe --json`,
`describe config --json [KEY]`, `doctor --json` or `lane` (`yes` and exit 0 when a local lane is
set up here, `no` and exit 1 when not, exit 3 on a fault: the text `doctor` takes only `no` as
none before it runs `agentroute --check`).

The settings are one table (SETTINGS) and the checks one list (CHECKS), each row data, so a
later row adds lines and no function. A setting's default is read from the script that owns it,
at run time, by the form it is written in (`env("NAME", "default")` in agentroute,
`${NAME:-default}` in the shell tools); none is typed here.

Room for the API lane, the next design's: no key here opens `api.`, no layer is named `user` and
no check is named `api`; those names are left to it.

Stdlib, 3.9. The describe and config reads open no socket and write nothing; `doctor --json` and
`lane` make one loopback connect, and `doctor --json` runs `agentroute --check --json` only where
a lane is set up.
"""
import __future__
import ast
import builtins
import fnmatch
import json
import math
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = "agents"
REMEDY = "/agents:install-cli"
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
                     "agentik", "pycache")

SUMMARY = "Shows every agent on this Mac and runs subagents on a local model."
REPO = "agentik-dev/agentik-agents"
PLUGIN = "agents@agentik"
NEEDS = [
    {"name": "claude", "kind": "program", "why": "the local lane runs it", "optional": True},
    {"name": "python3", "kind": "program",
     "why": "runs the router, the status read and install-cli", "optional": False},
]
# Each verb with its line of the dispatcher's `--help` table (tests/test-plug.py holds the two).
VERBS = [
    ("local", "claude-local ..."),
    ("status", "claude-agents status ..."),
    ("rig", "localrig ..."),
    ("route", "agentroute ..."),
    ("doctor", "each tool on PATH, python3, the local lane's check"),
    ("describe", "this tool, its verbs and its reads, as JSON (agents_plug.py)"),
    ("install-cli", "freeze this lib/, write the launcher, the agentik door and the old names' "
                    "links (agents_install.py, under python3)"),
]
READS = [
    {"kind": "config", "name": "settings", "argv": ["describe", "config", "--json"]},
    {"kind": "doctor", "name": "doctor", "argv": ["doctor", "--json"]},
    {"kind": "status", "name": "sessions", "argv": ["status", "--json"]},
]

# The settings: one row a group. `read` names how the script is read; `pattern` finds a variable
# in a shell script, its default after it; `verb` is the line a `launch` change starts.
SETTINGS = [
    {"group": "route", "script": "agentroute", "read": "python", "prefix": "AGENTROUTE_",
     "skip": ("BACKENDS",), "verb": "agentik agents local",
     "note": "The router reads it when it starts; a shell profile keeps it."},
    {"group": "backends", "script": "agentroute", "read": "backends", "prefix": "AGENTROUTE_",
     "variable": "BACKENDS",
     "note": "The rig writes the file, and a hand edit is lost at its next up or down."},
    {"group": "local", "script": "claude-local", "read": "shell", "prefix": "CLAUDE_LOCAL_",
     "pattern": r'(?m)^\s*[A-Za-z_][A-Za-z0-9_]*="?\$\{(CLAUDE_LOCAL_[A-Z0-9_]+):-',
     "verb": "agentik agents local",
     "note": "agents local reads it when it starts; a shell profile keeps it."},
    {"group": "rig", "script": "localrig", "read": "shell", "prefix": "LOCALRIG_",
     "pattern": r"\$\{(LOCALRIG_[A-Z0-9_]+):-", "verb": "agentik agents rig up {backend}",
     "note": "The rig reads it when it starts; a shell profile keeps it."},
]
DEFAULT_NOTE = ("It takes a declared backend's name, never a value, and copies that backend's "
                "fields to default.")
# The rig's backend a LOCALRIG_ variable belongs to, by its first word; else llama.
RIG_BACKEND = {"LLAMA": "llama", "Q8": "llama", "FLASH": "flash", "UNSLOTH": "unsloth",
               "MLX": "mlx", "OLLAMA": "mlx"}
# The fields the router fills in each backend, and their types.
BACKEND_FIELDS = (("url", "string"), ("model", "string"), ("fold_system", "boolean"),
                  ("auth", "secret"))
SECRET = ("route.local_auth", "*.auth", "*_key")
PATH_NAMES = ("*_FILE", "*_BLOB", "*_GGUF", "*_MMPROJ", "*_DIR", "LOG")
CHOICES = {"local.explore": ["local", "inherit"]}
SUMMARIES = {
    "route.listen": "The loopback address the router listens on.",
    "route.upstream": "Where the router sends a request for a Claude model, its headers untouched.",
    "route.local_url": "The backend a `local/default` request is sent to.",
    "route.local_model": "The model a `local/default` request runs on.",
    "route.local_models": "More model names the router sends to the local backend, comma-separated.",
    "route.local_auth": "The authorization header the router sends to the default local backend.",
    "route.local_default_effort": "The effort a local request gets when it names none.",
    "route.local_max_effort": "The highest effort a local request may ask for.",
    "route.local_max_tokens": "The most output tokens a local request may ask for.",
    "route.local_concurrency": "How many local requests run at once; the rest wait their turn.",
    "route.local_strip_token_reminder": "Whether a local request loses the token reminder that "
                                        "defeats the prompt cache.",
    "route.backends_file": "The file the router reads its backends from, which the rig writes.",
    "route.ping_after_s": "The seconds a silent stream waits before the router sends a ping.",
    "route.ping_every_s": "The seconds between the pings the router sends while a stream is silent.",
    "route.timeout_s": "The seconds the router waits on a backend before it gives up.",
    "route.state_dir": "The folder the router keeps its state in.",
    "route.log": "The file the router writes one line a request to: sizes and names, never content.",
    "backends.*.url": "Where this backend answers.",
    "backends.*.model": "The model this backend serves when a request names none.",
    "backends.*.fold_system": "Whether a later system message is folded into the first, for "
                              "templates that refuse it.",
    "backends.*.auth": "The authorization header the router sends to this backend.",
    "local.subagent": "The model a subagent that names none runs on in a local session.",
    "local.explore": "Whether the built-in Explore agent runs on the local model or the session's.",
    "rig.ollama_url": "Where Ollama answers; the mlx backend is served from it.",
    "rig.q8_tag": "The Ollama tag whose GGUF file the llama backend runs.",
    "rig.q8_blob": "The GGUF file the llama backend runs, in place of the one its Ollama tag names.",
    "rig.llama_port": "The loopback port llama-server listens on, for the llama and flash backends.",
    "rig.flash_gguf": "The first GGUF file of the model the flash backend runs.",
    "rig.flash_mmproj": "The vision projector file the flash backend loads.",
    "rig.secrets_file": "The sops file the rig reads backend keys from.",
    "rig.unsloth_port": "The loopback port Unsloth Studio's API listens on.",
    "rig.mlx_tag": "The Ollama tag the mlx backend serves.",
    "rig.llama_ctx": "The context window, in tokens, llama-server gives the llama backend.",
    "rig.llama_slots": "How many requests the llama backend serves at once.",
    "rig.llama_cache_ram": "The megabytes of host memory llama-server keeps its prompt cache in.",
    "rig.llama_think_budget": "The most reasoning tokens a reply of the llama backend may spend.",
    "rig.flash_ctx": "The context window, in tokens, the flash backend gets.",
    "rig.flash_slots": "How many requests the flash backend serves at once.",
    "rig.unsloth_model": "The model Unsloth Studio downloads and serves for the unsloth backend.",
    "rig.unsloth_variant": "The GGUF variant of that model the unsloth backend runs.",
}

# The doctor's checks, in order: one row a check, `kind` naming how it is made.
TOOLS = ("agentroute", "claude-local", "localrig", "claude-agents", "agentik-agents", "agentik")
CHECKS = [{"name": t, "kind": "on_path", "missing": "note", "remedy": REMEDY} for t in TOOLS] + [
    {"name": "claude", "kind": "on_path", "missing": "warn", "remedy": None,
     "why": "the local lane runs it"},
    {"name": "python3", "kind": "python", "floor": (3, 9)},
    {"name": "lane", "kind": "lane", "timeout": 18},
]
NO_LANE = "no local lane is set up here, so the router, the upstream and the backends were not asked"
ROUTER_STATES = {"ok": "ok", "warn": "warn", "FAIL": "fail"}
OURS = ("AGENTROUTE_", "CLAUDE_LOCAL_", "LOCALRIG_")
# The variables a default may be computed from that are a setting, not this machine's folders:
# a default is computed with none of them set (review 1, R1-F2 and N1).
FEEDS = OURS + ("AGENTIK_",)


def set_(name):
    """A variable as the scripts read it: set and not empty."""
    return bool(os.environ.get(name))


def bare_environ():
    return {k: v for k, v in os.environ.items() if not k.startswith(FEEDS)}


def plain_one(value):
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, pathlib.PurePath):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, (tuple, list)):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def plain(value):
    """A value as JSON holds it: a number JSON has no word for (nan, inf) is its text, at any
    depth of a list or a mapping (review 2, R2-F1). It walks a copy with a stack, never by
    recursion, so a value nested as deep as json.loads takes cannot fail the read."""
    top = plain_one(value)
    stack = [top]
    while stack:
        here = stack.pop()
        if not isinstance(here, (list, dict)):
            continue
        for at in (range(len(here)) if isinstance(here, list) else list(here)):
            here[at] = plain_one(here[at])
            stack.append(here[at])
    return top


def type_of(value, name):
    if any(fnmatch.fnmatchcase(name, p) for p in PATH_NAMES):
        return "path"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, (list, set, frozenset, tuple)):
        return "list"
    return "string"


def summary_of(key):
    if key in SUMMARIES:
        return SUMMARIES[key]
    for pattern, text in SUMMARIES.items():
        if "*" in pattern and fnmatch.fnmatchcase(key, pattern):
            return text
    return "Read from the environment when the tool starts."


def secret(key):
    return any(fnmatch.fnmatchcase(key, p) for p in SECRET)


# --------------------------------------------------------------------------- the readers
DIGITS = re.compile(r"[0-9]+")   # what sh takes as a number: str.isdigit also takes "\u00b2"


def exists(path):
    """A path the router names, or None where its assignment could not run here."""
    return isinstance(path, str) and os.path.exists(path)


def read_python(row):
    """agentroute's `env`/`env_num` reads: each module-level assignment that holds one is run
    twice, from the script's own text, with the functions it defines: once as the router runs it,
    once with every `env` giving its default. [(NAME, value, default, feeds)], in the script's
    order; `feeds` are the variables, other than its own, that the value is computed from
    through the assignments it reads (review 1, R1-F2: `LOG` from `STATE_DIR`)."""
    path = os.path.join(HERE, row["script"])
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name in ("env", "env_num", "migrated")]
    reads = {"env", "env_num"}
    assigns = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            names = [c.args[0].value for c in ast.walk(node.value)
                     if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                     and c.func.id in reads and c.args and isinstance(c.args[0], ast.Constant)]
            assigns.append((node, names))
    # what an assignment with a read loads from the module (CONFIG_HOME, STATE_DIR, ...)
    wanted = {n.targets[0].id for n, names in assigns if names}
    grew = True
    while grew:
        grew = False
        for node, _ in assigns:
            if node.targets[0].id in wanted:
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Name) and sub.id not in wanted \
                            and any(a.targets[0].id == sub.id for a, _ in assigns):
                        wanted.add(sub.id)
                        grew = True
    reading = {n.targets[0].id: names for n, names in assigns}
    refers = {n.targets[0].id: {s.id for s in ast.walk(n.value) if isinstance(s, ast.Name)}
              & set(reading) for n, _ in assigns}

    def feeds(target, seen):
        out = set()
        for other in refers.get(target, ()) - seen:
            out |= set(reading[other]) | feeds(other, seen | {other})
        return out
    flags = __future__.annotations.compiler_flag

    def run(bare):
        ns = {"__builtins__": builtins, "os": os, "pathlib": pathlib, "sys": sys}
        exec(compile(ast.Module(body=defs, type_ignores=[]), path, "exec", flags, True), ns)
        if bare:
            ns["env"] = lambda name, default: default
        for node, _ in assigns:
            if node.targets[0].id not in wanted:
                continue
            try:
                exec(compile(ast.Module(body=[node], type_ignores=[]), path, "exec", flags, True), ns)
            except Exception:  # noqa: BLE001  a statement that cannot run here is left unread
                pass
        return ns

    live, bare = run(False), run(True)
    out = []
    for node, names in assigns:
        target = node.targets[0].id
        for name in names:
            if name in row.get("skip", ()):
                continue
            fed = sorted(row["prefix"] + n for n in feeds(target, {target}) - {name})
            out.append((name, plain(live.get(target)), plain(bare.get(target)), fed))
    return out


def shell_default(text, start):
    """The text of a `${NAME:-default}` default from `start` to its closing brace."""
    depth, i = 1, start
    while i < len(text):
        if text.startswith("${", i):
            depth, i = depth + 1, i + 2
            continue
        if text[i] == "}":
            depth -= 1
            if not depth:
                return text[start:i]
        i += 1
    return text[start:]


def expand(text, environ):
    """A shell default as sh computes it: `${NAME:-alt}`, `${NAME}` and `$NAME`."""
    out, i = [], 0
    while i < len(text):
        if text.startswith("${", i):
            inner = shell_default(text, i + 2)
            name, sep, alt = inner.partition(":-")
            got = environ.get(name, "")
            out.append(got if got else (expand(alt, environ) if sep else ""))
            i += 2 + len(inner) + 1
            continue
        m = re.match(r"\$([A-Za-z_][A-Za-z0-9_]*)", text[i:])
        if m:
            out.append(environ.get(m.group(1), ""))
            i += len(m.group(0))
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def read_shell(row):
    """[(NAME less the prefix, value, default, feeds)], each variable once, in the script's order;
    `feeds` are the settings' variables its default names (FEEDS), whose value moves it."""
    with open(os.path.join(HERE, row["script"]), encoding="utf-8") as handle:
        text = handle.read()
    bare, seen, out = bare_environ(), set(), []
    for m in re.finditer(row["pattern"], text):
        var = m.group(1)
        if var in seen:
            continue
        seen.add(var)
        name = var[len(row["prefix"]):]
        alt = shell_default(text, m.end())
        default = expand(alt, bare) or None
        fed = sorted({n for n in re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)", alt)
                      if n.startswith(FEEDS) and n != var})
        raw = os.environ.get(var) or None
        value = raw if raw is not None else (expand(alt, os.environ) or None)
        if default is not None and DIGITS.fullmatch(default):
            default = int(default)
            value = int(value) if isinstance(value, str) and DIGITS.fullmatch(value) else value
        out.append((name, value, default, fed))
    return out


# --------------------------------------------------------------------------- the settings
def setting(key, value, default, kind, source, change, values=None):
    value, default = plain(value), plain(default)
    if kind == "secret":
        value, default = ("(set)" if value else None), None
    rows = values
    if rows is None:
        rows = [] if default is None else [{"layer": "default", "value": default}]
        if source["layer"] != "default":
            row = {"layer": source["layer"], "value": value}
            if source["path"] is not None:
                row.update(path=source["path"], line=source["line"])
            rows.append(row)
    return {"key": key, "value": value, "default": default, "type": kind,
            "choices": CHOICES.get(key), "summary": summary_of(key), "source": source,
            "change": change, "live": False, "values": rows}


def launch(row, var, name):
    backend = RIG_BACKEND.get(name.split("_", 1)[0], "llama")
    return {"kind": "launch", "command": "%s=VALUE %s" % (var, row["verb"].format(backend=backend)),
            "path": None, "block": None, "note": row["note"]}


ENV = {"layer": "env", "path": None, "line": None}
DEFAULT = {"layer": "default", "path": None, "line": None}


def from_env(row, found):
    out = []
    for name, value, default, fed in found:
        var = row["prefix"] + name
        key = "%s.%s" % (row["group"], name.lower())
        kind = "secret" if secret(key) else type_of(default if default is not None else value, name)
        moved = set_(var) or any(set_(f) for f in fed)
        out.append(setting(key, value, default, kind, ENV if moved else DEFAULT,
                           launch(row, var, name)))
    return out


def read_backends(row, route, state):
    """The router's backends (load_backends, then its setdefault and its fill), each field a
    setting; an unreadable source is a warning and the router's empty map, as the router does."""
    var = row["prefix"] + row["variable"]
    file = route["route.backends_file"]["value"]
    raw, origin, path = os.environ.get(var, ""), "env", None
    if not raw and exists(file):
        origin, path = "rig", file
        try:
            with open(file, encoding="utf-8") as handle:
                raw = handle.read()
        except (OSError, UnicodeDecodeError):
            raw = None
    found = {}
    if raw is None or raw:
        try:
            found = json.loads(raw)
            if not isinstance(found, dict):
                raise ValueError("not an object")
        except (TypeError, ValueError, RecursionError):  # RecursionError: nested past the limit
            print("agents: %s is not a JSON object; ignoring it, as the router does"
                  % (path or var), file=sys.stderr)
            state["warnings"].append({"key": None, "reason": "unreadable", "value": None,
                                      "path": path, "line": None})
            found = {}
    url, model = route["route.local_url"], route["route.local_model"]
    auth = route["route.local_auth"]
    origins = {name: origin for name in found}
    if "default" not in found:
        found["default"] = {"url": url["value"], "model": model["value"],
                            "auth": state["local_auth"]}
        origins["default"] = "router"
    for name in list(found):
        if not isinstance(found[name], dict):
            del found[name]
    if "default" not in found:
        found["default"] = {"url": url["value"], "model": model["value"], "auth": ""}
        origins["default"] = "router"
    out = []
    for name, b in found.items():
        filled = {"url": str(b.get("url") or url["value"]).rstrip("/"),
                  "model": b.get("model", model["value"]), "auth": b.get("auth", ""),
                  "fold_system": b.get("fold_system", False)}
        # default is set by naming a backend the rig declares, never by a value (review 1, R1-F3)
        command, note = (("agentik agents rig default BACKEND", DEFAULT_NOTE) if name == "default"
                         else ("agentik agents rig up %s" % name, row["note"]))
        change = {"kind": "command", "command": command, "path": None, "block": None,
                  "note": note}
        feeds = {"url": url, "model": model, "auth": auth}
        for field, kind in BACKEND_FIELDS:
            default = None
            if name == "default":
                default = {"url": url["default"], "model": model["default"],
                           "fold_system": False}.get(field)
            if origins[name] == "router":
                source = feeds[field]["source"] if field in feeds else DEFAULT
            elif origins[name] == "rig":
                source = {"layer": "rig", "path": path, "line": None}
            else:
                source = ENV
            out.append(setting("backends.%s.%s" % (name, field), filled[field], default, kind,
                               source, change))
    return out


def config(key=None):
    state = {"warnings": [], "local_auth": os.environ.get("AGENTROUTE_LOCAL_AUTH", "")}
    settings, route, any_set = [], {}, False
    for row in SETTINGS:
        if row["read"] == "backends":
            got = read_backends(row, route, state)
            any_set = any_set or set_(row["prefix"] + row["variable"])
        else:
            found = read_python(row) if row["read"] == "python" else read_shell(row)
            got = from_env(row, found)
            any_set = any_set or any(set_(row["prefix"] + f[0]) or any(set_(v) for v in f[3])
                                     for f in found)
        if row["group"] == "route":
            route = {s["key"]: s for s in got}
        settings.extend(got)
    file = route["route.backends_file"]["value"]
    file = file if isinstance(file, str) else None
    layers = [{"name": "default", "path": None, "present": True, "travels": False},
              {"name": "rig", "path": file, "present": exists(file), "travels": False},
              {"name": "env", "path": None, "present": any_set, "travels": False}]
    if key is not None:
        settings = [s for s in settings if s["key"] == key]
    return {"schema": "agentik.config/1", "ok": True, "tool": TOOL, "layers": layers,
            "settings": settings, "warnings": state["warnings"]}


def describe(version):
    return {"schema": "agentik.describe/1", "ok": True, "tool": TOOL, "version": version,
            "summary": SUMMARY, "repo": REPO, "plugin": PLUGIN, "needs": NEEDS,
            "verbs": [{"name": n, "summary": s, "top": False} for n, s in VERBS],
            "reads": READS}


# --------------------------------------------------------------------------- the doctor
def lane_set_up():
    """A local lane is set up here when the backends file exists, any AGENTROUTE_* variable is
    set, or something answers a loopback connect on the router's address inside 1 s."""
    if any(k.startswith("AGENTROUTE_") and v for k, v in os.environ.items()):
        return True
    route = {}
    for row in SETTINGS:
        if row["read"] == "python":
            route = {"%s.%s" % (row["group"], f[0].lower()): f[1] for f in read_python(row)}
            break
    if os.path.exists(str(route.get("route.backends_file", ""))):
        return True
    host, _, port = str(route.get("route.listen", "")).rpartition(":")
    host = host.strip("[]")
    if not port.isdigit() or not (host.startswith("127.") or host in ("localhost", "::1")):
        return False
    try:
        socket.create_connection((host, int(port)), timeout=1).close()
        return True
    except (OSError, OverflowError, ValueError):
        return False


def check_on_path(c):
    path = shutil.which(c["name"])
    if path:
        return [{"name": c["name"], "status": "ok", "detail": path, "remedy": None}]
    why = " (%s)" % c["why"] if c.get("why") else ""
    return [{"name": c["name"], "status": c["missing"], "detail": "not on PATH" + why,
             "remedy": c["remedy"]}]


def check_python(c):
    path = shutil.which("python3")
    if not path:
        return [{"name": c["name"], "status": "fail", "detail": "not on PATH", "remedy": None}]
    try:
        got = subprocess.run([path, "-I", "-X", "pycache_prefix=" + CACHE, "-c",
                              "import platform; print(platform.python_version())"],
                             capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        version = got.stdout.strip() if got.returncode == 0 else ""
    except Exception:  # noqa: BLE001  any fault is "does not run" (review 1, R1-F1)
        version = ""
    parts = re.match(r"(\d+)\.(\d+)", version)
    if not parts:
        return [{"name": c["name"], "status": "fail", "detail": "%s does not run" % path,
                 "remedy": None}]
    if (int(parts.group(1)), int(parts.group(2))) < c["floor"]:
        return [{"name": c["name"], "status": "fail",
                 "detail": "%s at %s, below %d.%d" % ((version, path) + c["floor"]), "remedy": None}]
    return [{"name": c["name"], "status": "ok", "detail": "%s at %s" % (version, path),
             "remedy": None}]


def check_lane(c):
    if not lane_set_up():
        return [{"name": c["name"], "status": "note", "detail": NO_LANE, "remedy": None}]
    argv = [sys.executable, "-I", "-X", "pycache_prefix=" + CACHE,
            os.path.join(HERE, "agentroute"), "--check", "--json"]
    try:
        got = subprocess.run(argv, capture_output=True, text=True, timeout=c["timeout"],
                             stdin=subprocess.DEVNULL)
        rows = json.loads(got.stdout)["rows"]
        return [{"name": r["what"].strip(), "status": ROUTER_STATES.get(r["state"], "warn"),
                 "detail": r["detail"], "remedy": None} for r in rows]
    except Exception as e:  # noqa: BLE001  any answer it cannot read (review 1, R1-F1)
        return [{"name": c["name"], "status": "fail",
                 "detail": "the router's check gave no answer: %s" % (str(e).splitlines() or [""])[0],
                 "remedy": None}]


KINDS = {"on_path": check_on_path, "python": check_python, "lane": check_lane}


def doctor():
    checks = []
    for c in CHECKS:
        checks.extend(KINDS[c["kind"]](c))
    return {"schema": "agentik.doctor/1", "ok": True, "tool": TOOL,
            "failed": sum(c["status"] == "fail" for c in checks),
            "warned": sum(c["status"] == "warn" for c in checks), "checks": checks}


# --------------------------------------------------------------------------- main
USAGE = "usage: agentik agents describe --json | describe config --json [KEY] | doctor --json"


def fault(schema, e):
    """The contract's §2 answer for a read that could not run."""
    return {"schema": schema, "ok": False, "tool": TOOL,
            "error": {"code": "unreadable",
                      "message": "%s: %s" % (type(e).__name__, (str(e).splitlines() or [""])[0]),
                      "remedy": REMEDY}}


def main(argv=None, out=sys.stdout, err=sys.stderr):
    """Each read prints one object and a newline; any fault inside one is §2's answer, exit 2,
    never a traceback (review 1, R1-F1). `lane` exits 3 on a fault, so no fault reads as 1."""
    argv = sys.argv[1:] if argv is None else argv
    version, args = (argv[0], argv[1:]) if argv else ("0.0.0-unknown", [])
    if args == ["lane"]:
        try:
            up = lane_set_up()
        except Exception:  # noqa: BLE001
            return 3
        out.write("yes\n" if up else "no\n")
        return 0 if up else 1
    if args == ["describe", "--json"]:
        schema, read = "agentik.describe/1", lambda: describe(version)
    elif args == ["doctor", "--json"]:
        schema, read = "agentik.doctor/1", doctor
    elif args[:1] == ["describe"] and args[1:2] == ["config"] and args.count("--json") == 1 \
            and len(args) <= 4:
        rest = [a for a in args[2:] if a != "--json"]
        schema, read = "agentik.config/1", lambda: config(rest[0] if rest else None)
    else:
        print(USAGE, file=err)
        return 2
    try:
        text, code = json.dumps(read(), allow_nan=False), 0
    except Exception as e:  # noqa: BLE001  a MemoryError aside, any fault is held here
        text, code = json.dumps(fault(schema, e)), 2
    out.write(text + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
