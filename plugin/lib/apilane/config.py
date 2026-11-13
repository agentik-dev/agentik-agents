"""The API lane's one reader of its switch (design/21 items 14 to 16).

`lane(roots)` reads the user file by GUIDE section 3's strict subset, the suite's own rules, and
alone says on, off or refused. The parser below (`Fault`, `_uncomment`, `_split`, `_scalar`,
`_value`, `parse`) is ported whole from agentik-commons
`plugins/suite/lib/agentik_suite/settings.py` at d795d4a; no other reader is written here.
Keys outside `api` are not this reader's and are left alone.
"""
import collections
import json
import os
import re
import stat

Lane = collections.namedtuple(
    "Lane", "enabled max_fanout_usd max_day_usd console_limit_usd proxy ca_file")
DEFAULTS = Lane(False, 2.0, 10.0, None, None, None)
KEYS = ("enabled", "max_fanout_usd", "max_day_usd", "console_limit_usd", "proxy", "ca_file")
MONEY = ("max_fanout_usd", "max_day_usd", "console_limit_usd")


class ConfigFault(Exception):
    """`config.fault` (path, line, why)."""

    def __init__(self, path, line, why):
        Exception.__init__(self, "config.fault")
        self.code, self.fields = "config.fault", {"path": path, "line": line, "why": why}


# -- ported whole from agentik-commons plugins/suite/lib/agentik_suite/settings.py at d795d4a --

KEY = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_-]*):(?:[ ]+(.*))?\Z")
NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
REFUSED = "&*|>!%@`"


class Fault(Exception):
    def __init__(self, line, why):
        Exception.__init__(self, why)
        self.line, self.why = line, why


def _uncomment(raw):
    """The line without its comment: a `#` at the start or after a space, outside quotes."""
    quote = None
    for i, ch in enumerate(raw):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"" and (i == 0 or raw[i - 1] in " [{,:"):
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] == " "):
            return raw[:i].rstrip(" ")
    return raw.rstrip(" ")


def _split(inner, n):
    parts, quote, start = [], None, 0
    for i, ch in enumerate(inner):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "[]{}":
            raise Fault(n, "a nested list or mapping")
        elif ch == ",":
            parts.append(inner[start:i])
            start = i + 1
    parts.append(inner[start:])
    parts = [p.strip() for p in parts]
    if parts == [""]:
        return []
    if "" in parts:
        raise Fault(n, "an empty item")
    return parts


def _scalar(text, n):
    if not text:
        return None
    if text[0] in REFUSED:
        raise Fault(n, "%s, which the subset does not take" % text[0])
    if text[0] == '"':
        try:
            value = json.loads(text)
        except ValueError:
            raise Fault(n, "a quoted value that does not close")
        if not isinstance(value, str):
            raise Fault(n, "a quoted value that does not close")
        return value
    if text[0] == "'":
        if len(text) < 2 or not text.endswith("'") or "'" in text[1:-1].replace("''", ""):
            raise Fault(n, "a quoted value that does not close")
        return text[1:-1].replace("''", "'")
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if text in ("null", "~"):
        return None
    if NUMBER.match(text):
        return float(text) if "." in text else int(text)
    if ": " in text or text.endswith(":") or text.startswith("- ") or text in ("-", "---"):
        raise Fault(n, "a value that reads as a key or an item")
    return text


def _value(text, n):
    if text.startswith("["):
        if not text.endswith("]"):
            raise Fault(n, "a list that does not close")
        return [_scalar(p, n) for p in _split(text[1:-1], n)]
    if text.startswith("{"):
        if not text.endswith("}"):
            raise Fault(n, "a mapping that does not close")
        found = {}
        for part in _split(text[1:-1], n):
            m = KEY.match(part)
            if not m or m.group(1) in found:
                raise Fault(n, "a mapping item that is not one key and a value")
            found[m.group(1)] = _scalar(m.group(2) or "", n)
        return found
    return _scalar(text, n)


def parse(text):
    """(tree, lines): the file's mappings, and each key's line by its dotted path."""
    root, lines = {}, {}
    stack = [(0, root, "")]  # the open mappings: indent, mapping, path prefix
    open_key = None  # (indent, mapping, key, path) of a key that has no value on its line
    open_list = None  # (indent, list) of the list whose items are being read
    for n, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw:
            raise Fault(n, "a tab; the subset indents with spaces")
        body = _uncomment(raw)
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(" "))
        content = body.strip()
        if content == "-" or content.startswith("- "):
            if open_key and indent >= open_key[0]:
                items = []
                open_key[1][open_key[2]] = items
                open_list, open_key = (indent, items), None
            elif not (open_list and indent == open_list[0]):
                raise Fault(n, "a list item out of place")
            item = content[2:].strip()
            if item[:1] in ("[", "{") or item.startswith("- ") or KEY.match(item):
                raise Fault(n, "a list item that is not a plain value")
            open_list[1].append(_scalar(item, n))
            continue
        open_list = None
        if open_key and indent > open_key[0]:
            child = {}
            open_key[1][open_key[2]] = child
            stack.append((indent, child, open_key[3] + "."))
        open_key = None
        while stack[-1][0] > indent:
            stack.pop()
        if stack[-1][0] != indent:
            raise Fault(n, "an indent that matches no key above it")
        m = KEY.match(content)
        if not m:
            raise Fault(n, "a line that is not a key and a value")
        mapping, prefix = stack[-1][1], stack[-1][2]
        key, path = m.group(1), stack[-1][2] + m.group(1)
        if key in mapping:
            raise Fault(n, "%s given twice" % path)
        lines[path] = n
        if m.group(2) is None:
            mapping[key] = None
            open_key = (indent, mapping, key, prefix + key)
        else:
            mapping[key] = _value(m.group(2).strip(), n)
    return root, lines


# -- the lane's reading of the tree -------------------------------------------------------------

def lane(roots):
    """Lane(enabled, max_fanout_usd, max_day_usd, console_limit_usd, proxy, ca_file).

    No file is the defaults. Refused, as `config.fault`: a path that is not a regular file (never
    opened), a file that cannot be read, any line outside the subset, an `api` that is not a
    mapping, an unknown key under `api`, an `enabled` other than true, True, false or False, a
    ceiling or `console_limit_usd` that is not a number above 0, a `proxy` or `ca_file` that is
    not a string."""
    path = roots.config
    try:
        st = os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        return DEFAULTS
    except OSError:
        raise ConfigFault(path, 0, "a file that cannot be read")
    if not stat.S_ISREG(st.st_mode):
        raise ConfigFault(path, 0, "not a regular file")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOCTTY", 0))
        with os.fdopen(fd, "rb") as fh:
            if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
                raise ConfigFault(path, 0, "not a regular file")
            text = fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        raise ConfigFault(path, 0, "a file that cannot be read")
    try:
        tree, lines = parse(text)
    except Fault as f:
        raise ConfigFault(path, f.line, f.why)
    if "api" not in tree:
        return DEFAULTS
    api = tree["api"]
    if not isinstance(api, dict):
        raise ConfigFault(path, lines.get("api", 0), "api is not a mapping of keys")
    line = lambda key: lines.get("api." + key, lines.get("api", 0))
    for key in api:
        if key not in KEYS:
            raise ConfigFault(path, line(key), "api.%s is not a key of the lane" % key)
    values = DEFAULTS._asdict()
    if "enabled" in api:
        if api["enabled"] is not True and api["enabled"] is not False:
            raise ConfigFault(path, line("enabled"), "api.enabled is true or false, nothing else")
        values["enabled"] = api["enabled"]
    for key in MONEY:
        if key in api:
            v = api[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not v > 0:
                raise ConfigFault(path, line(key), "api.%s is a number of dollars above 0" % key)
            values[key] = float(v)
    for key in ("proxy", "ca_file"):
        if key in api:
            if not isinstance(api[key], str) or not api[key]:
                raise ConfigFault(path, line(key), "api.%s is a string" % key)
            values[key] = api[key]
    return Lane(**values)
