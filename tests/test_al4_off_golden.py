#!/usr/bin/python3
"""Packet al4-report, ruling 9 (design/21 item 16): off is byte-identical to today.

Part A, always: the launcher's stdout, stderr and exit, bare and for help, --help, status,
status --json, doctor, install-cli --prefix and an unknown verb, and each hook's for a fixture
event, are byte-equal between this tree and a copy of it with plugin/lib/apilane/ removed, in three
off homes: no user file; `api:` with `enabled: false`; other keys only. Part B, while the branch is
ahead of main: the same captures are byte-equal to a `git archive` of the merge base. The homes
hold a seat and a helper, so rows exist. Masked: `generated`, a row's `elapsed_s`, the temp paths,
the frozen tree's hash. `doctor` runs only under a sandbox-exec profile that denies the network;
where that cannot run, the doctor captures alone skip with one printed reason. Not compared, by
design: `fanout` and `api` (the lane's named exception) and `--version`.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PLUGIN = os.path.join(REPO, "plugin")
SANDBOX = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
HOMES = {"no-file": None, "enabled-false": "api:\n  enabled: false\n",
         "other-keys": "local:\n  subagent: x\n"}
VERBS = [("bare", []), ("help", ["help"]), ("--help", ["--help"]), ("status", ["status"]),
         ("status --json", ["status", "--json"]), ("doctor", ["doctor"]),
         ("install-cli", ["install-cli", "--prefix", "{prefix}"]), ("unknown verb", ["nosuch"])]
EVENTS = {
    "PreToolUse": {"session_id": "s-golden", "hook_event_name": "PreToolUse", "tool_name": "Agent",
                   "tool_input": {"subagent_type": "general-purpose", "prompt": "read"}},
    "SessionStart": {"session_id": "s-golden", "hook_event_name": "SessionStart", "source": "startup"},
    "UserPromptSubmit": {"session_id": "s-golden", "hook_event_name": "UserPromptSubmit",
                         "prompt": "hi"},
}


def git(*argv):
    return subprocess.run(["git", *argv], cwd=REPO, check=True, capture_output=True).stdout


def merge_base():
    """The merge base with main, or None on main itself (or with no main to read)."""
    try:
        head = git("rev-parse", "HEAD").decode().strip()
        base = git("merge-base", "HEAD", "main").decode().strip()
    except subprocess.CalledProcessError:
        return None
    return None if base == head else base


def sandbox_applies():
    try:
        return subprocess.run(SANDBOX + ["/usr/bin/true"], capture_output=True,
                              timeout=30).returncode == 0
    except OSError:
        return False


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))


def build_home(home, config):
    """A seat and a helper the status tool lists, and the user file when there is one."""
    now = time.time()
    sid, aid = "s-golden", "a0f1"
    proj = os.path.join(home, ".claude", "projects", "work")
    transcript = os.path.join(proj, sid + ".jsonl")
    seat = os.path.join(home, ".local", "state", "agentik-session", "sessions", sid)
    os.makedirs(seat)
    with open(os.path.join(seat, "meter.json"), "w") as fh:
        json.dump({"session_id": sid, "model": "claude-x", "context": 1000, "window": 200000,
                   "turns": 1, "transcript": {"path": transcript}, "builders": []}, fh)
    sub = os.path.join(proj, sid, "subagents")
    os.makedirs(sub)
    with open(os.path.join(sub, "agent-%s.jsonl" % aid), "w") as fh:
        # started a day and more ago: the text's elapsed column reads in hours, stable here
        fh.write(json.dumps({"type": "user", "timestamp": iso(now - 26 * 3600 - 1800),
                             "message": {"role": "user", "content": "go"}}) + "\n")
    with open(os.path.join(sub, "agent-%s.meta.json" % aid), "w") as fh:
        json.dump({"description": "a helper"}, fh)
    if config is not None:
        d = os.path.join(home, ".config", "agentik", "agents")
        os.makedirs(d)
        with open(os.path.join(d, "config.yaml"), "w") as fh:
            fh.write(config)


class OffGolden(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.t = os.path.realpath(tempfile.mkdtemp(prefix="al4-golden-"))
        cls.addClassCleanup(shutil.rmtree, cls.t, True)
        cls.trees = {}
        for name in ("this", "bare"):
            dst = os.path.join(cls.t, name, "plugin")
            shutil.copytree(PLUGIN, dst, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
            cls.trees[name] = dst
        shutil.rmtree(os.path.join(cls.trees["bare"], "lib", "apilane"))
        cls.base = merge_base()
        if cls.base:
            dst = os.path.join(cls.t, "base")
            os.makedirs(dst)
            subprocess.run(["tar", "-x", "-C", dst], input=git("archive", cls.base, "plugin"),
                           check=True)
            cls.trees["base"] = os.path.join(dst, "plugin")
        cls.homes = {}
        for name, config in HOMES.items():
            home = os.path.join(cls.t, "home-" + name)
            build_home(home, config)
            cls.homes[name] = home
        cls.sandboxed = sandbox_applies()
        if not cls.sandboxed:
            print("skip: the doctor captures; sandbox-exec cannot deny the network here",
                  file=sys.stderr)

    def env(self, tree, home):
        return {"HOME": home, "PATH": "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": self.trees[tree],
                "CLAUDE_PLUGIN_DATA": os.path.join(self.t, "data-" + tree)}

    def mask(self, tree, text):
        text = text.decode("utf-8", "replace")
        text = text.replace(self.trees[tree], "<PLUGIN>").replace(self.t, "<T>")
        text = re.sub(r"<T>/prefix-%s-" % re.escape(tree), "<T>/prefix-", text)
        text = re.sub(r"\b[0-9a-f]{40}\b", "<HASH>", text)
        text = re.sub(r'"generated": "[^"]*"', '"generated": "<GENERATED>"', text)
        return re.sub(r'"elapsed_s": \d+', '"elapsed_s": <ELAPSED>', text)

    def launch(self, tree, home, name, argv):
        prefix = os.path.join(self.t, "prefix-%s-%s" % (tree, os.path.basename(home)))
        cmd = [os.path.join(self.trees[tree], "bin", "agentik-agents")]
        cmd += [a.format(prefix=prefix) for a in argv]
        if name == "doctor":
            cmd = SANDBOX + cmd
        p = subprocess.run(cmd, env=self.env(tree, home), capture_output=True, timeout=120,
                           cwd=home)
        return p.returncode, self.mask(tree, p.stdout), self.mask(tree, p.stderr)

    def hooks(self, tree, home, event):
        """Every hook the tree's hooks.json runs on the event: stdout and stderr joined, the
        largest exit; a tree with none for the event is (0, "", "")."""
        with open(os.path.join(self.trees[tree], "hooks", "hooks.json")) as fh:
            spec = json.load(fh)["hooks"].get(event, [])
        rc, out, err = 0, b"", b""
        for group in spec:
            for h in group["hooks"]:
                args = [a.replace("${CLAUDE_PLUGIN_ROOT}", self.trees[tree]) for a in h.get("args", [])]
                p = subprocess.run([h["command"]] + args, input=json.dumps(EVENTS[event]).encode(),
                                   env=self.env(tree, home), capture_output=True, timeout=30)
                rc, out, err = max(rc, p.returncode), out + p.stdout, err + p.stderr
        return rc, self.mask(tree, out), self.mask(tree, err)

    def compare(self, others):
        for hname, home in self.homes.items():
            for name, argv in VERBS:
                if name == "doctor" and not self.sandboxed:
                    continue
                with self.subTest(home=hname, capture=name, against=others):
                    got = {tree: self.launch(tree, home, name, argv) for tree in ("this",) + others}
                    for other in others:
                        self.assertEqual(got["this"], got[other])
            for event in EVENTS:
                with self.subTest(home=hname, hook=event, against=others):
                    got = {tree: self.hooks(tree, home, event) for tree in ("this",) + others}
                    for other in others:
                        self.assertEqual(got["this"], got[other])

    def test_a_without_the_lane(self):
        self.compare(("bare",))

    def test_b_against_the_merge_base(self):
        if not self.base:
            print("skip: part B; HEAD is main's merge base, so there is no branch to compare",
                  file=sys.stderr)
            return
        self.compare(("base",))


if __name__ == "__main__":
    unittest.main()
