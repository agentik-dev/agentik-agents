"""A fan-out's job: the JSON form, the short form, and the pick between them.

design/21 item 10. Nothing here prints; a refusal is a JobError with a `code`
and `fields` (seams section 2): job.shape, job.id, job.flag, job.type.
"""
import binascii
import collections
import json
import math
import os
import re
import sys
import time

SCHEMA = "agentik.fanout.job/1"
DEFAULT_JOBS = 4
DEFAULT_TIMEOUT_SEC = 900
DEFAULT_PROFILE = "review"
LABEL_MAX = 80
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")
KEYS = ("schema", "id", "budget_usd", "dirs", "shards", "max_shard_usd", "jobs",
        "timeout_sec")
SHARD_KEYS = ("label", "type", "prompt")
# The old fan-out's flags that the lane does not take, each refused by name.
REFUSED = ("--model", "--out", "--claude-arg", "--phase", "--stagger-sec")
VALUED = ("--budget-usd", "--profile", "--tasks", "--add-dir", "-j", "--jobs",
          "--max-shard-usd", "--timeout-sec", "--id")

Shard = collections.namedtuple("Shard", "label type prompt")
Job = collections.namedtuple(
    "Job", "id budget_usd dirs shards max_shard_usd jobs timeout_sec")


class JobError(Exception):
    def __init__(self, code, **fields):
        Exception.__init__(self, code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


def _shape(field, why):
    return JobError("job.shape", field=field, why=why)


def _types(types):
    if types is None:
        from apilane import types as _t
        types = _t.TYPES
    return set(types)


def _number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _positive(obj, key, default):
    if obj.get(key) is None:
        return default
    value = obj[key]
    if not _number(value):
        raise _shape(key, "kind")
    if value <= 0:
        raise _shape(key, "range")
    return value


def new_id(now=None):
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now))
    return "f-%s-%s" % (stamp, binascii.hexlify(os.urandom(2)).decode())


def from_obj(obj, *, types=None):
    """Validate a decoded job object; return the Job."""
    known = _types(types)
    if not isinstance(obj, dict):
        raise _shape("job", "object")
    for key in obj:
        if key not in KEYS:
            raise _shape(key, "unknown")
    if "schema" in obj and obj["schema"] != SCHEMA:
        raise _shape("schema", "value")
    jid = obj.get("id")
    if jid is None:
        jid = new_id()
    elif not isinstance(jid, str):
        raise _shape("id", "kind")
    elif not ID_RE.match(jid):
        raise JobError("job.id", id=jid)
    if obj.get("budget_usd") is None:
        raise _shape("budget_usd", "missing")
    budget = float(_positive(obj, "budget_usd", None))
    dirs = obj.get("dirs", [])
    if not isinstance(dirs, list) or not all(isinstance(d, str) and d for d in dirs):
        raise _shape("dirs", "kind")
    raw = obj.get("shards")
    if not isinstance(raw, list):
        raise _shape("shards", "kind" if "shards" in obj else "missing")
    if not raw:
        raise _shape("shards", "empty")
    shards = []
    for n, item in enumerate(raw):
        where = "shards[%d]" % n
        if not isinstance(item, dict):
            raise _shape(where, "kind")
        for key in item:
            if key not in SHARD_KEYS:
                raise _shape("%s.%s" % (where, key), "unknown")
        label = item.get("label")
        if label is None:
            label = "s%d" % (n + 1)
        elif (not isinstance(label, str) or not label or len(label) > LABEL_MAX
              or not label.isprintable()):
            raise _shape(where + ".label", "label")
        kind = item.get("type")
        if not isinstance(kind, str):
            raise _shape(where + ".type", "kind" if "type" in item else "missing")
        if kind not in known:
            raise JobError("job.type", type=kind)
        prompt = item.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise _shape(where + ".prompt", "kind" if "prompt" in item else "missing")
        shards.append(Shard(label, kind, prompt))
    max_shard = _positive(obj, "max_shard_usd", None)
    jobs = obj.get("jobs", DEFAULT_JOBS)
    if not isinstance(jobs, int) or isinstance(jobs, bool):
        raise _shape("jobs", "kind")
    if jobs < 1:
        raise _shape("jobs", "range")
    timeout = _positive(obj, "timeout_sec", DEFAULT_TIMEOUT_SEC)
    if isinstance(timeout, float) and timeout.is_integer():
        timeout = int(timeout)
    return Job(jid, budget, tuple(dirs), tuple(shards),
               None if max_shard is None else float(max_shard), jobs, timeout)


def _decode(text):
    try:
        return json.loads(text)
    except ValueError:
        raise _shape("job", "json")


def load(source, *, types=None, stdin=None):
    """Read a job from a JSON file, or from stdin when `source` is `-`."""
    if source == "-":
        text = (stdin or sys.stdin).read()
    else:
        try:
            with open(source) as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            raise _shape("job", "unreadable")
    return from_obj(_decode(text), types=types)


def _tasks(path):
    """The old fan-out's --tasks: a JSON array, JSON lines or plain lines."""
    try:
        with open(path) as f:
            raw = f.read()
    except (OSError, UnicodeDecodeError):
        raise _shape("tasks", "unreadable")
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
        items = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line[0] in "{\"":
                try:
                    line = json.loads(line)
                except ValueError:
                    pass
            items.append(line)
    else:
        if isinstance(data, dict):
            data = data.get("tasks")
        if not isinstance(data, list):
            raise _shape("tasks", "kind")
        items = data
    out = []
    for item in items:
        if isinstance(item, str):
            out.append({"prompt": item})
        elif isinstance(item, dict):
            for key in item:
                if key not in ("label", "prompt"):
                    raise _shape("tasks.%s" % key, "unknown")
            out.append(dict(item))
        else:
            raise _shape("tasks", "kind")
    return out


def _value(flag, text, kind):
    try:
        value = kind(text)
    except ValueError:
        raise _shape(flag.lstrip("-").replace("-", "_"), "kind")
    if kind is float and not math.isfinite(value):
        raise _shape(flag.lstrip("-").replace("-", "_"), "kind")
    return value


def from_argv(argv, *, types=None):
    """The short form, made into the job its JSON twin would be."""
    opts = {"--add-dir": []}
    prompts = []
    args = list(argv)
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if arg == "--":
            prompts.extend(args[i:])
            break
        if not arg.startswith("-") or arg == "-":
            prompts.append(arg)
            continue
        name, eq, inline = arg.partition("=")
        if name in REFUSED:
            raise JobError("job.flag", flag=name)
        if name not in VALUED:
            raise JobError("job.flag", flag=name)
        if eq:
            value = inline
        elif i < len(args):
            value = args[i]
            i += 1
        else:
            raise _shape(name.lstrip("-").replace("-", "_"), "value")
        if name == "--add-dir":
            opts[name].append(value)
        else:
            opts["--jobs" if name == "-j" else name] = value
    obj = {"schema": SCHEMA}
    if "--budget-usd" not in opts:
        raise _shape("budget_usd", "missing")
    obj["budget_usd"] = _value("--budget-usd", opts["--budget-usd"], float)
    profile = opts.get("--profile", DEFAULT_PROFILE)
    tasks = _tasks(opts["--tasks"]) if "--tasks" in opts else []
    tasks.extend({"prompt": p} for p in prompts)
    for task in tasks:
        task["type"] = profile
    obj["shards"] = tasks
    obj["dirs"] = opts["--add-dir"]
    if "--id" in opts:
        obj["id"] = opts["--id"]
    if "--jobs" in opts:
        obj["jobs"] = _value("--jobs", opts["--jobs"], int)
    if "--max-shard-usd" in opts:
        obj["max_shard_usd"] = _value("--max-shard-usd", opts["--max-shard-usd"], float)
    if "--timeout-sec" in opts:
        obj["timeout_sec"] = _value("--timeout-sec", opts["--timeout-sec"], float)
    return from_obj(obj, types=types)


def parse(argv, *, types=None, stdin=None):
    """The short form when --budget-usd is given, else one JOB argument."""
    argv = list(argv)
    if any(a == "--budget-usd" or a.startswith("--budget-usd=") for a in argv):
        return from_argv(argv, types=types)
    if len(argv) != 1:
        raise _shape("JOB", "count")
    return load(argv[0], types=types, stdin=stdin)
