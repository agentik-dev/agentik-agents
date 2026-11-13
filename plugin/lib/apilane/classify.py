"""The substance check: `classify` and its four validators, as the old fan-out had them
(design/21 item 31), and `verdict`, which maps them onto a shard's named state.

A measured fan-out produced shards that ran 8 to 10 turns, cost real money and returned
schema-valid placeholder output while the envelope reported success. `--json-schema`
validates shape, not content, so every result is checked for substance before it counts.
An empty result, a placeholder summary, a review with no finding under the job's dirs and
a budget abort each read as a named state, never `ok`. New here: a result that holds the
key's value or an age secret key's prefix reads `leak`, and its text is neither written
nor returned.
"""
import pathlib
import re

# Substance thresholds the old fan-out kept beside its validators. A degenerate shard
# produced a 4-character summary, so these sit well above that.
MIN_SUMMARY_CHARS = 40
MIN_PROSE_CHARS = 80
MIN_ISSUE_CHARS = 25

PLACEHOLDER_TOKENS = {
    "test", "todo", "tbd", "example", "placeholder", "foo", "bar", "n/a",
    "none", "sample", "dummy", "xxx", "lorem ipsum", "summary", "string",
}

STATUS_OK = "ok"
STATUS_DEGENERATE = "degenerate"
STATUS_ERROR = "error"
STATUS_BUDGET = "budget_exhausted"
STATUS_UNPARSEABLE = "unparseable"

# The prefix an age secret key starts with, written in two parts so no file holds it whole.
AGE_PREFIX = "AGE-SECRET" + "-KEY-"


def _looks_placeholder(text):
    """True if `text` is a filler non-answer rather than real content.

    Deliberately not length-based: a terse real answer ('deadlock', 'use-after-free', a
    git SHA, 'TOCTOU') passes. Filler is empty, a known filler token, a single token of
    two characters or fewer, or nothing alphanumeric at all.
    """
    t = (text or "").strip().lower().rstrip(".!?")
    if not t:
        return True
    if t in PLACEHOLDER_TOKENS:
        return True
    if not re.search(r"[a-z0-9]", t):
        return True
    if len(t) <= 2:
        return True
    return False


def _resolve_finding_path(raw, roots):
    """True if `raw` names a real file at or under one of the roots.

    A citation counts only if it resolves to an existing file within a root the run was
    given, so an absolute /etc/passwd or arbitrary prose does not pass as one.
    """
    if not raw:
        return False
    raw = re.sub(r":\d+(:\d+)?$", "", raw.strip())
    if not raw:
        return False
    roots_res = [pathlib.Path(r).resolve() for r in roots]
    candidates = []
    p = pathlib.Path(raw)
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates += [pathlib.Path(r) / p for r in roots]
    for c in candidates:
        try:
            rc = c.resolve()
        except Exception:
            continue
        if not rc.exists():
            continue
        for root in roots_res:
            try:
                rc.relative_to(root)
                return True
            except ValueError:
                continue
    return False


def validate_structured(obj, roots):
    """Content check for a schema type. Returns (ok, reasons).

    Rejects only a genuine non-answer: not an object, a missing or placeholder summary,
    findings that are not a list, or a non-empty findings list in which no finding cites
    a file that exists. Substance is judged over the findings as a set, so one terse
    finding does not poison the shard, and an empty list is a legitimate answer.
    """
    reasons = []
    if not isinstance(obj, dict):
        return False, ["structured_output is not an object"]

    summary = obj.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        reasons.append("summary is missing or empty")
    elif _looks_placeholder(summary):
        reasons.append("summary is placeholder text")

    findings = obj.get("findings")
    if not isinstance(findings, list):
        reasons.append("findings is not a list")
        return (not reasons), reasons

    if findings:
        real_paths = sum(
            1 for f in findings
            if isinstance(f, dict) and _resolve_finding_path(str(f.get("file") or ""), roots)
        )
        if real_paths == 0:
            reasons.append(
                "none of the %d findings cite a file that exists "
                "under the reviewed roots" % len(findings))

    return (not reasons), reasons


def validate_prose(text):
    """Content check for a prose type: rejects only empty or placeholder output."""
    t = (text or "").strip()
    if not t:
        return False, ["result is empty"]
    if _looks_placeholder(t):
        return False, ["result is placeholder text"]
    return True, []


def classify(envelope, raw_rc, roots, structured):
    """Map a finished shard onto a status plus reasons."""
    if envelope is None:
        return STATUS_UNPARSEABLE, ["no JSON envelope (exit %s)" % raw_rc]

    terminal = envelope.get("terminal_reason")
    if terminal == "budget_exhausted":
        return STATUS_BUDGET, ["shard hit its own ceiling; result discarded"]

    # `subtype` reports "success" even on an API error, so it is never a success signal.
    if envelope.get("is_error"):
        detail = str(envelope.get("result") or "").strip()[:200]
        return STATUS_ERROR, ["%s: %s" % (terminal or "error", detail) if detail
                              else str(terminal)]

    if structured:
        so = envelope.get("structured_output")
        if so is None:
            return STATUS_DEGENERATE, ["no structured_output in a --json-schema run"]
        ok, reasons = validate_structured(so, roots)
    else:
        ok, reasons = validate_prose(str(envelope.get("result") or ""))

    return (STATUS_OK if ok else STATUS_DEGENERATE), reasons


def holds_secret(text, key):
    """True when `text` holds the key's value or an age secret key's prefix."""
    if not text:
        return False
    if key and key in text:
        return True
    return AGE_PREFIX in text.upper()


# A degenerate reason's opening words, and the state and reason code it reads as.
_DEGENERATE = (
    ("result is empty", "empty", "invalid:empty"),
    ("summary is missing or empty", "empty", "invalid:empty"),
    ("no structured_output", "empty", "invalid:empty"),
    ("structured_output is not an object", "placeholder", "invalid:structured"),
    ("result is placeholder text", "placeholder", "invalid:placeholder"),
    ("summary is placeholder text", "placeholder", "invalid:placeholder"),
    ("findings is not a list", "placeholder", "invalid:findings"),
    ("none of the", "placeholder", "invalid:citations"),
)


def verdict(envelope, raw_rc, roots, structured, *, raw, key):
    """(state, reason) for a finished shard; no text of the result is in either.

    `raw` is everything the child printed, checked for a secret before anything else.
    """
    if holds_secret(raw, key):
        return "leak", None
    status, reasons = classify(envelope, raw_rc, roots, structured)
    if status == STATUS_OK:
        return "ok", None
    if status == STATUS_BUDGET:
        return "ceiling", None
    if status in (STATUS_UNPARSEABLE, STATUS_ERROR):
        if raw_rc:
            return "failed", "exit:%s" % raw_rc
        return "failed", "invalid:envelope" if status == STATUS_UNPARSEABLE else "invalid:error"
    first = reasons[0] if reasons else ""
    for opening, state, reason in _DEGENERATE:
        if first.startswith(opening):
            return state, reason
    return "placeholder", "invalid:result"
