#!/usr/bin/env python3
"""Packet p1 (hq design/09 §2, §9 step 4): the plugin's loaded descriptions at most 1,024 B,
the commands only the owner types hidden with their bodies unchanged, the local caveat said
once, and the local-guard hook that denies a local agent in a session the router does not
serve, in one plain sentence. Run as `python3 tests/test-descriptions.py`; spends nothing."""
import hashlib
import json
import os
import re
import subprocess
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugin"
GUARD = PLUGIN / "hooks" / "local-guard"
# the bodies (after the frontmatter's closing ---) at c204a3c, the pin
HIDDEN = {
    "delegate-local": "fd4e2ec432278cf439a0d197f0b4289926a8014a6f0cc77df00a79157bc09e0e",
    "install-cli": "f41efe609967d9bdd4f248ce6e13ea5578c93818c6c2abb1e66d3fe371d33067",
}


def split(path):
    text = path.read_text(encoding="utf-8")
    _, head, body = text.split("---\n", 2)
    return head, body


def description(head):
    m = re.search(r"(?m)^description: (.*)$", head)
    return m.group(1).strip().strip('"') if m else ""


def guard(event, base_url=None):
    env = {"PATH": "/usr/bin:/bin"}
    if base_url is not None:
        env["ANTHROPIC_BASE_URL"] = base_url
    data = event if isinstance(event, str) else json.dumps(event)
    p = subprocess.run([str(GUARD)], input=data, capture_output=True, text=True, env=env, timeout=30)
    return p.returncode, p.stdout, p.stderr


def call(kind):
    return {"hook_event_name": "PreToolUse", "tool_name": "Agent",
            "tool_input": {"subagent_type": kind, "description": "d", "prompt": "p"}}


class DescriptionsTest(unittest.TestCase):
    def test_t1_the_sum_is_under_the_ceiling(self):
        p = subprocess.run([str(REPO / "scripts" / "plugin-description-bytes"), str(PLUGIN)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        total = int(re.search(r"^total (\d+) of 1024 B$", p.stdout, re.M).group(1))
        self.assertLessEqual(total, 1024)

    def test_t2_hidden_commands_keep_their_bodies(self):
        for name, digest in HIDDEN.items():
            head, body = split(PLUGIN / "commands" / (name + ".md"))
            self.assertIn("\ndisable-model-invocation: true\n", "\n" + head, name)
            self.assertEqual(hashlib.sha256(body.encode("utf-8")).hexdigest(), digest, name)
        head, _ = split(PLUGIN / "commands" / "status.md")
        self.assertNotIn("disable-model-invocation: true", head)

    def test_t3_visible_descriptions_non_empty_and_bounded(self):
        files = (sorted((PLUGIN / "agents").glob("*.md")) + [PLUGIN / "commands" / "status.md"]
                 + sorted((PLUGIN / "skills").glob("*/SKILL.md")))
        for path in files:
            head, _ = split(path)
            text = description(head)
            self.assertTrue(text, path)
            if path.name == "SKILL.md":
                self.assertLess(len(text), 201, path)

    def test_t4_the_local_caveat_is_said_once(self):
        said = [p.name for p in sorted((PLUGIN / "agents").glob("local-*.md"))
                if "agentik agents local" in description(split(p)[0])]
        self.assertEqual(said, ["local-explore.md"])
        self.assertEqual((PLUGIN / "agents" / "local-explore.md").read_bytes(),
                         (PLUGIN / "lib" / "share" / "local-explore.md").read_bytes())

    def test_t5_the_guard_denies_a_local_agent_outside_the_router(self):
        for url in (None, "", "https://api.anthropic.com", "http://gateway.example:8787"):
            code, out, err = guard(call("agents:local-explore"), url)
            self.assertEqual((code, err), (0, ""), url)
            got = json.loads(out)["hookSpecificOutput"]
            self.assertEqual(got["hookEventName"], "PreToolUse")
            self.assertEqual(got["permissionDecision"], "deny")
            self.assertEqual(got["permissionDecisionReason"],
                             "agents:local-explore runs on the local model, which answers only in a "
                             "session started by `agentik agents local`; this session was not, so "
                             "nothing ran. Use a Claude model, or start the session with "
                             "`agentik agents local`.")

    def test_t5_the_guard_passes_everything_else(self):
        for url in ("http://127.0.0.1:8787", "http://localhost:9000", "http://[::1]:8787"):
            self.assertEqual(guard(call("agents:local-test"), url), (0, "", ""), url)
        for kind in ("agents:scribe", "general-purpose", "local-explore", "Explore"):
            self.assertEqual(guard(call(kind)), (0, "", ""), kind)
        self.assertEqual(guard(""), (0, "", ""))
        self.assertEqual(guard("not json agents:local-x"), (0, "", ""))
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "Agent|Task")
        self.assertEqual(hooks["PreToolUse"][0]["hooks"][0]["command"], "/bin/sh")
        self.assertEqual(hooks["PreToolUse"][0]["hooks"][0]["args"],
                         ["${CLAUDE_PLUGIN_ROOT}/hooks/local-guard"])
        self.assertTrue(os.access(GUARD, os.X_OK))

    def test_t7_the_guard_reads_a_large_input_whole_on_every_early_exit(self):
        # review F1: an exit before stdin is read leaves Claude Code's write of an event over
        # the pipe buffer (about 64 KB) failing with EPIPE, a hook error; 200 KB on each path
        big = "x" * 200000
        cases = (("loopback session", call("agents:local-explore"), "http://127.0.0.1:8787"),
                 ("not a local type", call("agents:scribe"), None),
                 ("malformed JSON, loopback", "{agents:local-explore " + big, "http://127.0.0.1:8787"),
                 ("malformed JSON, no router", "{agents:local-explore " + big, None))
        for name, event, url in cases:
            if not isinstance(event, str):
                event["tool_input"]["prompt"] = big
                event = json.dumps(event)
            env = {"PATH": "/usr/bin:/bin"}
            if url is not None:
                env["ANTHROPIC_BASE_URL"] = url
            p = subprocess.Popen(["/bin/sh", str(GUARD)], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            errors = []

            def write(data=event.encode("utf-8")):
                try:
                    p.stdin.write(data)
                    p.stdin.close()
                except OSError as e:  # BrokenPipeError: the hook exited unread
                    errors.append(e)

            writer = threading.Thread(target=write)
            writer.start()
            out, err = p.stdout.read(), p.stderr.read()
            code = p.wait(timeout=30)
            writer.join(timeout=30)
            self.assertEqual((errors, code, out, err), ([], 0, b"", b""), name)

    def test_t6_the_vendored_copy_is_listed(self):
        rows = (REPO / "scripts" / "vendored.sha256").read_text().splitlines()
        digest = hashlib.sha256((REPO / "scripts" / "plugin-description-bytes").read_bytes()).hexdigest()
        self.assertIn("%s  scripts/plugin-description-bytes" % digest, rows)


if __name__ == "__main__":
    unittest.main()
