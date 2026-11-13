"""The API lane's verbs (design/21 items 10 to 17), behind `agentik agents fanout` and `api`.

    fanout JOB | <the short form> [--dry-run] [--yes] [--json]
    api status [--json] | api probe | api key set [--recipient R] | api key remove

and three the dispatcher alone calls: `unwalled` (exit 2 with one line where the file says on or
is refused, 0 in silence where it says off), `help-lines` and `doctor-block` (printed only while
the file says on). Off, every verb prints one line on stderr and exits 2; where no wall is proved
every verb refuses with the platform's line. Every other row is reached through one `parts`
object, imported here when none is handed in.
"""
import getpass
import json
import os
import platform
import re
import sys

SESSION = re.compile(r"[A-Za-z0-9-]{1,128}\Z")
VERB_FLAGS = ("--dry-run", "--yes", "--json")
PARTS = {
    "parse": ("job", "parse"), "plan": ("fanout", "plan"), "run": ("fanout", "run"),
    "day": ("ledger", "day"), "find_claude": ("argv", "find_claude"), "build_argv": ("argv", "build"),
    "build_env": ("env", "build"), "started": ("proc", "started"), "alive": ("proc", "alive"),
    "wall_backend": ("wall", "backend"), "wrap": ("wall", "wrap"), "check_dirs": ("wall", "check_dirs"),
    "key_load": ("key", "load"), "key_store": ("key", "store"), "key_remove": ("key", "remove"),
    "key_present": ("key", "present"), "probe_run": ("probe", "run"),
    "probe_ensure": ("probe", "ensure"), "probe_read": ("probe", "read"),
    "probe_passed": ("probe", "passed"), "cli_version": ("probe", "cli_version"),
}


class Parts:
    """The other rows' functions, each imported on first use."""

    def __getattr__(self, name):
        if name not in PARTS:
            raise AttributeError(name)
        import importlib
        module, attr = PARTS[name]
        fn = getattr(importlib.import_module("apilane." + module), attr)
        setattr(self, name, fn)
        return fn


class Usage(Exception):
    pass


def session_id(env=None):
    """CLAUDE_CODE_SESSION_ID when it is at most 128 letters, digits and dashes, else `none`."""
    value = (os.environ if env is None else env).get("CLAUDE_CODE_SESSION_ID", "")
    return value if SESSION.match(value) else "none"


def verb_words(argv):
    words = [argv[0]]
    if argv[0] == "api" and len(argv) > 1 and argv[1] in ("status", "probe", "key"):
        words.append(argv[1])
        if argv[1] == "key" and len(argv) > 2 and argv[2] in ("set", "remove"):
            words.append(argv[2])
    return " ".join(words)


def main(argv, *, roots=None, parts=None, stdin=None, stdout=None, stderr=None):
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    from apilane import config, messages, paths

    def err(text):
        stderr.write(text + "\n")
        stderr.flush()

    argv = list(argv)
    if not argv or argv[0] not in ("fanout", "api", "unwalled", "help-lines", "doctor-block"):
        err(messages.say("lane.usage"))
        return 2
    verb, quiet = argv[0], argv[0] in ("help-lines", "doctor-block")
    if roots is None:
        try:
            roots = paths.account()
        except paths.HomeError as e:
            if quiet:
                return 0
            err(messages.say(e.code, **e.fields))
            return 2
    try:
        lane = config.lane(roots)
    except config.ConfigFault as e:
        if quiet:
            return 0
        err(messages.say(e.code, **e.fields))
        return 2
    if quiet:
        if lane.enabled:
            parts = Parts() if parts is None else parts
            text = help_lines() if verb == "help-lines" else doctor_block(roots, lane, parts)
            stdout.write(text + "\n")
        return 0
    if verb == "unwalled":
        if not lane.enabled:
            return 0
        err(messages.say("wall.platform", platform=platform.system()))
        return 2
    if not lane.enabled:
        err(messages.say("off", verb=verb_words(argv), config=paths.tilde(roots.config, roots.home)))
        return 2
    parts = Parts() if parts is None else parts
    try:
        try:
            backend = parts.wall_backend()
        except ImportError:
            backend = None
        if backend is None:
            err(messages.say("wall.platform", platform=platform.system()))
            return 2
        if verb == "fanout":
            return fanout(argv[1:], roots, lane, parts, stdin, stdout, err)
        return api(argv[1:], roots, lane, parts, stdin, stdout, err)
    except Usage:
        err(messages.say("lane.usage"))
        return 2
    except ImportError as e:
        err(messages.say("module.missing", name=getattr(e, "name", None) or "a module"))
        return 2
    except Exception as e:   # noqa: BLE001 -- an error a user may see carries a code
        code = getattr(e, "code", None)
        if not isinstance(code, str):
            raise
        err(messages.say(code, **(getattr(e, "fields", None) or {})))
        return 1 if code == "probe.fail" and argv[:2] == ["api", "probe"] else 2


def help_lines():
    from apilane import messages
    return messages.say("help.fanout") + "\n" + messages.say("help.api")


def _as_dict(r):
    return dict(r._asdict()) if hasattr(r, "_asdict") else dict(vars(r))


def fanout(rest, roots, lane, parts, stdin, stdout, err):
    from apilane import messages, report
    if rest[:1] in (["--help"], ["-h"]):
        stdout.write(messages.say("fanout.help") + "\n")
        return 0
    dry, yes, as_json = (f in rest for f in VERB_FLAGS)
    args = [a for a in rest if a not in VERB_FLAGS]
    if not args:
        raise Usage()
    job = parts.parse(args, stdin=stdin)
    plan = parts.plan(job, lane=lane, roots=roots)
    if as_json:
        if dry or not yes:
            stdout.write(json.dumps({"schema": "agentik.fanout/1", "plan": plan}) + "\n")
    elif dry or not yes:
        stdout.write(messages.plan(plan, lane) + "\n")
    else:                       # running: stdout is one line a shard, the plan is progress
        err(messages.plan(plan, lane))
    stdout.flush()
    if dry:
        return 0
    if not yes:
        if not (hasattr(stdin, "isatty") and stdin.isatty()):
            err(messages.say("yes.need"))
            return 2
        err(messages.say("ask").rstrip("\n"))
        if stdin.readline().strip().lower() not in ("y", "yes"):
            err(messages.say("no.answer"))
            return 1
    session = session_id()
    claude = parts.find_claude()

    def emit(event, **fields):
        if event == "reserved":
            err(messages.say("reserved", **fields))
        elif event in ("shard.start", "shard.end"):
            line = report.line(session, roots, alive=parts.alive)
            if line:
                err(line)
        elif event == "done":
            err(messages.say("done", **fields))

    def ensure_probe(path):
        return parts.probe_ensure(claude=path, roots=roots, build_argv=parts.build_argv,
                                  build_env=parts.build_env, wrap=parts.wrap, emit=emit)

    result = parts.run(job, lane=lane, roots=roots, session=session, claude=claude, wrap=parts.wrap,
                       key=lambda: parts.key_load(roots), ensure_probe=ensure_probe,
                       started=parts.started, emit=emit)
    shards = list(result.shards or [])
    if as_json:
        stdout.write(json.dumps({"schema": "agentik.fanout/1", "id": result.id, "rc": result.rc,
                                 "session": session, "spent_usd": result.spent_usd,
                                 "budget_usd": result.budget_usd,
                                 "shards": [_as_dict(s) for s in shards]}) + "\n")
    else:
        for s in shards:
            stdout.write(messages.shard(s) + "\n")
    stdout.flush()
    return result.rc


def api(rest, roots, lane, parts, stdin, stdout, err):
    from apilane import messages
    sub = rest[0] if rest else None
    if sub == "status" and rest[1:] in ([], ["--json"]):
        stdout.write(status(roots, lane, parts, as_json=rest[1:] == ["--json"]) + "\n")
        return 0
    if sub == "probe" and len(rest) == 1:
        claude = parts.find_claude()
        rec = parts.probe_run(claude=claude, roots=roots, build_argv=parts.build_argv,
                              build_env=parts.build_env, wrap=parts.wrap) or {}
        for c in rec.get("checks") or []:
            stdout.write(messages.say("probe.check", mark="ok" if c.get("ok") else "FAIL",
                                      name=c.get("name"), detail=c.get("detail") or "") + "\n")
        ok = bool(rec.get("ok"))
        stdout.write(messages.say("probe.ok" if ok else "probe.bad", version=rec.get("cli_version")) + "\n")
        return 0 if ok else 1
    if sub == "key" and rest[1:2] == ["set"]:
        extra = rest[2:]
        recipient = None
        if extra:
            if len(extra) != 2 or extra[0] != "--recipient":
                raise Usage()
            recipient = extra[1]
        if not (hasattr(stdin, "isatty") and stdin.isatty()):
            err(messages.say("tty.need", verb="api key set"))
            return 2
        first = getpass.getpass("API key: ")
        second = getpass.getpass("API key, again: ")
        if first != second:
            err(messages.say("key.differ"))
            return 2
        if not first.strip():
            err(messages.say("key.empty"))
            return 2
        parts.key_store(first.strip(), roots=roots, recipient=recipient)
        stdout.write(messages.say("key.set", store=roots.store) + "\n")
        return 0
    if sub == "key" and rest[1:] == ["remove"]:
        gone = parts.key_remove(roots)
        stdout.write(messages.say("key.removed" if gone else "key.absent", store=roots.store) + "\n")
        return 0
    raise Usage()


def _gated(roots):
    path = os.path.join(roots.home, ".claude", "edit-gates")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = [l.strip() for l in fh]
    except (OSError, UnicodeDecodeError):
        return False, path
    shown = "~" + roots.config[len(roots.home.rstrip("/")):]
    return roots.config in lines or shown in lines, path


def _live(roots):
    from apilane import report
    base = os.path.join(roots.state, "live")
    found = []
    try:
        sessions = sorted(os.listdir(base))
    except OSError:
        return found
    for s in sessions:
        for _path, rec in report._records(os.path.join(base, s)):
            if not rec.get("ended"):
                found.append({"fanout": rec.get("fanout"), "pid": rec.get("pid"), "session": s})
    return found


def status(roots, lane, parts, *, as_json=False):
    """`api status`: the steps left, then the lane's places, key, probe, limits, day and runs."""
    from apilane import messages, report
    key = bool(parts.key_present(roots))
    probe = parts.probe_read(roots)
    try:
        day, day_fault = parts.day(roots), None
    except Exception as e:   # noqa: BLE001 -- the log's fault is shown, the rest still prints
        if not isinstance(getattr(e, "code", None), str):
            raise
        day, day_fault = None, messages.say(e.code, **(getattr(e, "fields", None) or {}))
    gated, gates = _gated(roots)
    running = len(report.rows(roots, alive=parts.alive))
    live = _live(roots)
    probe_ok = bool(probe and probe.get("ok"))
    steps = []
    if lane.console_limit_usd is None:
        steps.append(messages.say("step.limit", config=roots.config))
    if not gated:
        steps.append(messages.say("step.gates", config=roots.config, gates=gates))
    if not key:
        steps.append(messages.say("step.key"))
    if not probe_ok:
        steps.append(messages.say("step.probe"))
    old = old_forward()
    if old:
        steps.append(messages.say("step.old", path=old))
    if as_json:
        return json.dumps({"schema": "agentik.api.status/1", "enabled": lane.enabled,
                           "config": roots.config, "state": roots.state, "store": roots.store,
                           "key": key, "probe": probe, "console_limit_usd": lane.console_limit_usd,
                           "max_fanout_usd": lane.max_fanout_usd, "max_day_usd": lane.max_day_usd,
                           "day": day, "day_fault": day_fault, "running": running, "live": live,
                           "gated": gated, "steps_left": len(steps)})
    out = []
    if steps:
        out += [messages.say("first.run"), "Steps left:"] + steps
    out.append(messages.say("status.head", running=running, s="" if running == 1 else "s"))
    out += ["config:    " + roots.config, "state:     " + roots.state, "key store: " + roots.store,
            "key:       " + ("set" if key else "not set")]
    if probe_ok:
        out.append("probe:     ok at CLI %s" % probe.get("cli_version"))
    elif probe:
        out.append("probe:     failed at CLI %s; owed: agentik agents api probe" % probe.get("cli_version"))
    else:
        out.append("probe:     owed: agentik agents api probe")
    if lane.console_limit_usd is None:
        out.append(messages.say("limit.none"))
    else:
        out.append(messages.say("limit.stated", limit=messages.money(lane.console_limit_usd)))
    out.append("ceilings:  %s a fan-out, %s a day" % (messages.cents(lane.max_fanout_usd),
                                                     messages.cents(lane.max_day_usd)))
    if day_fault:
        out.append(day_fault)
    else:
        out.append("%s of %s today" % (messages.cents((day or {}).get("sum_usd", 0.0)),
                                       messages.cents(lane.max_day_usd)))
        for u in (day or {}).get("unsettled") or []:
            out.append("reserved, no settle: %s %s, pid %s" % (
                u.get("fanout"), messages.cents(u.get("budget_usd")), u.get("pid")))
    for f in live:
        out.append("live fan-out: %s, pid %s" % (f["fanout"], f["pid"]))
    if not gated:
        out.append(messages.say("gates.note", config=roots.config, gates=gates))
    return "\n".join(out)


def old_forward(path=None):
    """A claude-fanout on PATH that is not this tool's forward (packet al6, R4), or None."""
    import shutil
    found = shutil.which("claude-fanout", path=path)
    if not found:
        return None
    mine = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                        "claude-fanout")
    return None if os.path.realpath(found) == os.path.realpath(mine) else found


def doctor_block(roots, lane, parts):
    """The lane's block in `doctor`, while the file says on. It reads files and PATH only."""
    from apilane import messages

    def row(name, fn):
        try:
            value = fn()
        except ImportError:
            value = "not in this install"
        except Exception as e:   # noqa: BLE001 -- doctor reports, it does not gate
            value = messages.say(e.code, **e.fields) if isinstance(getattr(e, "code", None), str) else "unreadable"
        return messages.say("doctor.row", name=name, value=value)

    def wall():
        name = parts.wall_backend()
        return name or "none proved on %s: the lane cannot turn on here" % platform.system()

    def probe():
        rec = parts.probe_read(roots)
        if rec and rec.get("ok"):
            return "ok at CLI %s" % rec.get("cli_version")
        return "owed: agentik agents api probe"

    limit = (messages.say("limit.stated", limit=messages.money(lane.console_limit_usd))
             if lane.console_limit_usd is not None else messages.say("limit.none"))
    return "\n".join([
        messages.say("doctor.head"),
        messages.say("doctor.row", name="switch", value="on, in " + roots.config),
        row("wall", wall),
        row("key", lambda: "set" if parts.key_present(roots) else "not set: agentik agents api key set"),
        row("probe", probe),
        messages.say("doctor.row", name="limit", value=limit),
    ] + ([messages.say("doctor.row", name="old name",
                       value=messages.say("doctor.old", path=old_forward()))]
         if old_forward() else []))


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    sys.exit(main(sys.argv[1:]))
