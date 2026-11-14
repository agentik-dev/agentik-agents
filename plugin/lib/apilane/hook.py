"""The API lane's hook, in Python (design/21 items 11, 16, 17, 22).

`hooks/api-lane` starts this once, with -I, only when its cheap sh test passed: the event's name is
the argument and the event is on stdin. At SessionStart: on, item 11's sentence (or, where no wall
is proved, the platform's line); refused, one line with the file and line; off, nothing. At
UserPromptSubmit: the session's report line, whatever the switch says. Under a HOME that is not
the account's it prints nothing. It exits 0 always and writes no bytecode beside itself.
"""
import json
import os
import platform
import sys

sys.dont_write_bytecode = True


def _say(out, event, text):
    out.write(json.dumps({"hookSpecificOutput": {"hookEventName": event,
                                                 "additionalContext": text}}) + "\n")


def main(event, text, *, roots=None, backend=None, out=None):
    out = sys.stdout if out is None else out
    try:
        from apilane import config, messages, paths, report
        if roots is None:
            try:
                roots = paths.account()
            except paths.HomeError:
                return 0
        if event == "SessionStart":
            try:
                lane = config.lane(roots)
            except config.ConfigFault as e:
                _say(out, event, messages.say("hook.fault", **e.fields))
                return 0
            if not lane.enabled:
                return 0
            if backend is None:
                try:
                    from apilane import wall
                    backend = wall.backend
                except ImportError:
                    backend = lambda: None   # noqa: E731 -- no wall module is no proved wall
            if backend() is None:
                _say(out, event, messages.say("hook.platform", platform=platform.system()))
            else:
                _say(out, event, messages.say("hook.on"))
        elif event == "UserPromptSubmit":
            try:
                session = json.loads(text).get("session_id")
            except (ValueError, AttributeError):
                return 0
            line = report.line(session, roots, consume=True)
            if line is not None:
                _say(out, event, line)
    except Exception:   # noqa: BLE001 -- a hook never fails the session's turn
        return 0
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    data = sys.stdin.read()
    main(sys.argv[1] if len(sys.argv) > 1 else "", data)
    sys.exit(0)
