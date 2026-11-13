#!/usr/bin/python3
"""tests/test-plug.py: the plug's reads (packet ak7-plug-agents, the plug contract §3 to §7).

Every run is in a temp HOME with the XDG_* folders under it and no AGENTROUTE_*, CLAUDE_LOCAL_*
or LOCALRIG_* variable but those a case names. Every run of the plugin's launcher is under a
sandbox that denies the network, so no probe leaves this machine and none reaches loopback
either; the doctor's own connections are also recorded in-process by a stub. Stdlib, 3.9.
"""
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True
REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LIB = os.path.join(REPO, "plugin", "lib")
A = os.path.join(REPO, "plugin", "bin", "agentik-agents")
SANDBOX = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
DESCRIBE_KEYS = {"schema", "ok", "tool", "version", "summary", "repo", "plugin", "needs", "verbs",
                 "reads"}
SETTING_KEYS = {"key", "value", "default", "type", "choices", "summary", "source", "change", "live",
                "values"}
TYPES = {"string", "integer", "number", "boolean", "list", "path", "secret"}
VERBS = ["local", "status", "rig", "route", "doctor", "describe", "install-cli"]
WORD = "zebrafog-quill"          # a made-up credential: it must appear nowhere in an answer
R6 = {
    "route.listen": "The loopback address the router listens on.",
    "route.upstream": "Where the router sends a request for a Claude model, its headers untouched.",
    "route.local_url": "The backend a `local/default` request is sent to.",
    "route.local_model": "The model a `local/default` request runs on.",
    "route.local_default_effort": "The effort a local request gets when it names none.",
    "route.local_max_effort": "The highest effort a local request may ask for.",
    "route.local_max_tokens": "The most output tokens a local request may ask for.",
    "route.local_concurrency": "How many local requests run at once; the rest wait their turn.",
    "route.timeout_s": "The seconds the router waits on a backend before it gives up.",
    "route.log": "The file the router writes one line a request to: sizes and names, never content.",
    "backends.default.url": "Where this backend answers.",
    "backends.default.model": "The model this backend serves when a request names none.",
}


def read(name):
    with open(os.path.join(LIB, name), encoding="utf-8") as handle:
        return handle.read()


def sandbox_applies():
    try:
        return subprocess.run(SANDBOX + ["/usr/bin/true"], capture_output=True,
                              timeout=30).returncode == 0
    except OSError:
        return False


SANDBOXED = sandbox_applies()


def load_plug():
    spec = importlib.util.spec_from_file_location("agents_plug_under_test",
                                                  os.path.join(LIB, "agents_plug.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Plug(unittest.TestCase):

    def setUp(self):
        if not SANDBOXED:
            self.skipTest("sandbox-exec cannot deny the network here; the reads stay unrun")
        self.t = os.path.realpath(tempfile.mkdtemp(prefix="agents-plug-"))
        self.addCleanup(shutil.rmtree, self.t, True)
        self.home = os.path.join(self.t, "home")
        os.makedirs(self.home)
        self.cache = os.path.join(self.home, ".cache")
        self.config = os.path.join(self.home, ".config")
        self.backends = os.path.join(self.config, "agentik", "agents", "route", "backends.json")

    def env(self, **extra):
        env = {"HOME": self.home, "PATH": "/usr/bin:/bin", "TERM": "dumb",
               "XDG_CONFIG_HOME": self.config, "XDG_CACHE_HOME": self.cache,
               "XDG_STATE_HOME": os.path.join(self.home, ".local", "state"),
               "XDG_DATA_HOME": os.path.join(self.home, ".local", "share")}
        env.update(extra)
        return env

    def run_a(self, *argv, **extra):
        start = time.monotonic()
        run = subprocess.run(SANDBOX + [A, *argv], cwd=self.t, env=self.env(**extra),
                             capture_output=True, timeout=60)
        run.seconds = time.monotonic() - start
        return run

    def answer(self, run, code=0):
        self.assertEqual(run.returncode, code, run.stdout + run.stderr)
        self.assertNotIn(b"\x1b", run.stdout)
        self.assertTrue(run.stdout.endswith(b"\n") and run.stdout.count(b"\n") == 1,
                        run.stdout[-200:])
        return json.loads(run.stdout.decode("utf-8"))

    def snapshot(self):
        keep = os.path.join(self.cache, "agentik") + os.sep
        seen = {}
        for here, _, files in os.walk(self.home):
            for name in files:
                path = os.path.join(here, name)
                if path.startswith(keep):
                    continue
                with open(path, "rb") as handle:
                    seen[os.path.relpath(path, self.home)] = handle.read()
        return seen

    def unchanged(self, before):
        self.assertEqual(sorted(self.snapshot()), sorted(before))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(os.path.exists(os.path.join(self.home, "Library")),
                         "a read made HOME/Library")

    def write_backends(self, text):
        os.makedirs(os.path.dirname(self.backends), exist_ok=True)
        with open(self.backends, "w", encoding="utf-8") as handle:
            handle.write(text)

    def config_read(self, *argv, **extra):
        return self.answer(self.run_a("describe", "config", "--json", *argv, **extra))

    @staticmethod
    def by_key(doc):
        return {s["key"]: s for s in doc["settings"]}

    # 1
    def test_1_describe(self):
        before = self.snapshot()
        run = self.run_a("describe", "--json")
        doc = self.answer(run)
        self.assertLess(run.seconds, 1.0)
        self.assertTrue(DESCRIBE_KEYS <= set(doc), sorted(DESCRIBE_KEYS - set(doc)))
        self.assertEqual(list(doc)[:2], ["schema", "ok"])
        self.assertEqual((doc["schema"], doc["ok"], doc["tool"]), ("agentik.describe/1", True, "agents"))
        with open(os.path.join(REPO, "plugin", ".claude-plugin", "plugin.json")) as handle:
            self.assertEqual(doc["version"], json.load(handle)["version"])
        self.assertLess(len(doc["summary"]), 80)
        self.assertEqual(doc["plugin"], "agents@agentik")
        self.assertEqual([n["name"] for n in doc["needs"]], ["claude", "python3"])
        self.assertEqual([n["optional"] for n in doc["needs"]], [True, False])
        self.assertEqual([v["name"] for v in doc["verbs"]], VERBS)
        self.assertFalse(any(v["top"] for v in doc["verbs"]))
        helped = subprocess.run([A, "--help"], env=self.env(), capture_output=True, text=True).stdout
        for verb in doc["verbs"]:
            line = re.search(r"(?m)^  %s\b.*$(\n {20,}.*$)*" % re.escape(verb["name"]), helped)
            self.assertIsNotNone(line, verb["name"])
            right = " ".join(line.group(0).split())
            self.assertTrue(right.endswith(verb["summary"]), (right, verb["summary"]))
        self.assertEqual([(r["kind"], r["name"], r["argv"]) for r in doc["reads"]],
                         [("config", "settings", ["describe", "config", "--json"]),
                          ("doctor", "doctor", ["doctor", "--json"]),
                          ("status", "sessions", ["status", "--json"])])
        for argv in (("describe",), ("describe", "nosuch", "--json")):
            run = self.run_a(*argv)
            self.assertEqual(run.returncode, 2, argv)
            self.assertEqual(run.stdout, b"")
        self.assertIn(b"describe --json", self.run_a("describe").stderr)
        self.unchanged(before)

    # 2
    def test_2_config(self):
        before = self.snapshot()
        doc = self.config_read()
        self.assertEqual((doc["schema"], doc["ok"], doc["tool"]), ("agentik.config/1", True, "agents"))
        names = [layer["name"] for layer in doc["layers"]]
        self.assertEqual(names, ["default", "rig", "env"])
        self.assertEqual([layer["present"] for layer in doc["layers"]], [True, False, False])
        self.assertEqual(doc["layers"][1]["path"], self.backends)
        self.assertEqual(doc["warnings"], [])
        keys = [s["key"] for s in doc["settings"]]
        self.assertEqual(len(keys), len(set(keys)))
        for s in doc["settings"]:
            self.assertEqual(set(s), SETTING_KEYS, s["key"])
            self.assertRegex(s["key"], r"^[a-z0-9_-]+(\.[a-z0-9_-]+)+$")
            self.assertFalse(s["key"].startswith("api."))
            self.assertIn(s["type"], TYPES, s["key"])
            self.assertEqual(s["source"], {"layer": "default", "path": None, "line": None}, s["key"])
            self.assertTrue(all(v["layer"] in names for v in s["values"]), s["key"])
            self.assertEqual(set(s["change"]), {"kind", "command", "path", "block", "note"})
            self.assertIs(s["live"], False)
            self.assertTrue(s["summary"].endswith(".") and len(s["summary"]) < 100, s["key"])
            self.assertEqual(s["summary"].count(". "), 0, s["key"])
            self.assertFalse(s["summary"].startswith("This setting"), s["key"])
            if s["default"] is not None:
                self.assertEqual(s["value"], s["default"], s["key"])
        by = self.by_key(doc)
        held = int(re.search(r'env_num\("LOCAL_MAX_TOKENS", "(\d+)"\)', read("agentroute")).group(1))
        self.assertEqual(by["route.local_max_tokens"]["value"], held)
        self.assertEqual(by["route.local_max_tokens"]["default"], held)
        self.assertIs(type(by["route.local_max_tokens"]["value"]), int)
        for key, summary in R6.items():
            self.assertEqual(by[key]["summary"], summary, key)
        self.assertEqual(by["route.local_auth"]["type"], "secret")
        self.assertIsNone(by["route.local_auth"]["value"])
        self.assertIs(by["route.local_strip_token_reminder"]["value"], True)
        self.assertEqual(by["route.local_models"]["value"], [])
        self.assertIs(type(by["route.timeout_s"]["value"]), float)
        self.assertNotIn("$HOME", by["rig.flash_gguf"]["default"])
        self.assertTrue(by["rig.flash_gguf"]["default"].startswith(self.home + "/"))
        self.assertEqual(by["backends.default.url"]["value"], by["route.local_url"]["value"])
        change = by["rig.llama_port"]["change"]
        self.assertEqual((change["kind"], change["command"]),
                         ("launch", "LOCALRIG_LLAMA_PORT=VALUE agentik agents rig up llama"))
        change = by["backends.default.url"]["change"]
        self.assertEqual(change["kind"], "command")
        self.assertTrue(change["command"].startswith("agentik agents rig "), change)
        self.unchanged(before)

    # 3
    def test_3_env(self):
        before = self.snapshot()
        doc = self.config_read(AGENTROUTE_LOCAL_MAX_TOKENS="4096", AGENTROUTE_LOCAL_AUTH=WORD)
        self.assertTrue(doc["layers"][2]["present"])
        s = self.by_key(doc)["route.local_max_tokens"]
        self.assertEqual(s["value"], 4096)
        self.assertEqual(s["source"], {"layer": "env", "path": None, "line": None})
        self.assertEqual([v["layer"] for v in s["values"]], ["default", "env"])
        self.assertEqual(s["change"]["kind"], "launch")
        self.assertTrue(s["change"]["command"].startswith("AGENTROUTE_LOCAL_MAX_TOKENS=VALUE "))
        self.assertIs(s["live"], False)
        by = self.by_key(doc)
        self.assertEqual(by["route.local_auth"]["value"], "(set)")
        self.assertEqual(by["backends.default.auth"]["value"], "(set)")
        run = self.run_a("describe", "config", "--json", AGENTROUTE_LOCAL_AUTH=WORD)
        self.assertNotIn(WORD.encode(), run.stdout + run.stderr)
        self.unchanged(before)

    # 4
    def test_4_backends(self):
        self.write_backends(json.dumps({"tortoise": {"url": "http://127.0.0.1:9911/",
                                                     "model": "slowpoke"}}))
        before = self.snapshot()
        doc = self.config_read()
        self.assertEqual(doc["layers"][1], {"name": "rig", "path": self.backends, "present": True,
                                            "travels": False})
        by = self.by_key(doc)
        self.assertEqual(by["backends.tortoise.url"]["value"], "http://127.0.0.1:9911")
        self.assertEqual(by["backends.tortoise.model"]["value"], "slowpoke")
        self.assertIs(by["backends.tortoise.fold_system"]["value"], False)
        self.assertIsNone(by["backends.tortoise.auth"]["value"])
        self.assertEqual(by["backends.tortoise.url"]["source"],
                         {"layer": "rig", "path": self.backends, "line": None})
        self.assertIn("backends.default.url", by)
        doc = self.config_read(AGENTROUTE_BACKENDS=json.dumps({"hare": {"url": "http://127.0.0.1:9922"}}))
        by = self.by_key(doc)
        self.assertNotIn("backends.tortoise.url", by)
        self.assertEqual(by["backends.hare.url"]["value"], "http://127.0.0.1:9922")
        self.assertEqual(by["backends.hare.url"]["source"], {"layer": "env", "path": None, "line": None})
        self.unchanged(before)

    # 5
    def test_5_every_variable_both_ways(self):
        before = self.snapshot()
        keys = set(self.by_key(self.config_read()))
        route = set(re.findall(r'\benv(?:_num)?\("([A-Z0-9_]+)"', read("agentroute"))) - {"BACKENDS"}
        local = set(re.findall(r'(?m)^[A-Za-z_]+="?\$\{(CLAUDE_LOCAL_[A-Z0-9_]+):-',
                               read("claude-local")))
        rig = set(re.findall(r"\$\{(LOCALRIG_[A-Z0-9_]+):-", read("localrig")))
        self.assertEqual(local, {"CLAUDE_LOCAL_SUBAGENT", "CLAUDE_LOCAL_EXPLORE"})
        for group, names, cut in (("route", route, ""), ("local", local, "CLAUDE_LOCAL_"),
                                  ("rig", rig, "LOCALRIG_")):
            want = {"%s.%s" % (group, n[len(cut):].lower()) for n in names}
            have = {k for k in keys if k.startswith(group + ".")}
            self.assertTrue(want, group)
            self.assertEqual(have, want, group)
        self.unchanged(before)

    # 6
    def test_6_keyed_and_unreadable(self):
        before = self.snapshot()
        doc = self.config_read("route.listen")
        self.assertEqual([s["key"] for s in doc["settings"]], ["route.listen"])
        self.assertEqual(len(doc["layers"]), 3)
        self.assertEqual(self.config_read("nosuch")["settings"], [])
        self.unchanged(before)
        self.write_backends("{not json")
        before = self.snapshot()
        doc = self.config_read()
        self.assertIs(doc["ok"], True)
        self.assertEqual(doc["warnings"], [{"key": None, "reason": "unreadable", "value": None,
                                            "path": self.backends, "line": None}])
        self.assertIs(doc["layers"][1]["present"], True)
        by = self.by_key(doc)
        self.assertEqual(by["backends.default.url"]["value"], by["route.local_url"]["value"])
        self.unchanged(before)

    # 7
    def test_7_route_check_json(self):
        argv = SANDBOX + [sys.executable, os.path.join(LIB, "agentroute"), "--check"]
        text = subprocess.run(argv, env=self.env(), capture_output=True, timeout=60)
        run = subprocess.run(argv + ["--json"], env=self.env(), capture_output=True, timeout=60)
        doc = self.answer(run, text.returncode)
        self.assertEqual(set(doc), {"ok", "rows"})
        self.assertIs(doc["ok"], text.returncode == 0)
        rows = {r["what"].strip(): r for r in doc["rows"]}
        self.assertEqual(rows["router"]["state"], "FAIL")
        self.assertTrue(all(set(r) == {"state", "what", "detail"} for r in doc["rows"]))

    # 8
    def test_8_doctor_json(self):
        run = self.run_a("doctor", "--json")
        self.assertLess(run.seconds, 3.0)
        doc = self.answer(run)
        self.assertEqual((doc["schema"], doc["ok"], doc["tool"], doc["failed"]),
                         ("agentik.doctor/1", True, "agents", 0))
        names = [c["name"] for c in doc["checks"]]
        self.assertEqual([c["status"] for c in doc["checks"] if c["name"] == "lane"], ["note"])
        self.assertNotIn("router", names)
        self.assertNotIn("upstream", names)
        self.assertEqual(doc["warned"], sum(c["status"] == "warn" for c in doc["checks"]))
        for c in doc["checks"]:
            self.assertEqual(set(c), {"name", "status", "detail", "remedy"})
            self.assertIn(c["status"], ("ok", "note", "warn", "fail"))
        self.assertEqual({c["name"]: c["remedy"] for c in doc["checks"]}["agentroute"],
                         "/agents:install-cli")
        # the stub: the doctor read in-process, every connection and child recorded
        plug, off, children = load_plug(), [], []

        def connect(sock, address):
            if not str(address[0]).startswith("127.") and address[0] not in ("::1", "localhost"):
                off.append(address)
            raise ConnectionRefusedError(address)

        real_run = subprocess.run

        def run_child(argv, *a, **k):
            children.append(argv)
            return real_run(argv, *a, **k)

        out = io.StringIO()
        with mock.patch.dict(os.environ, self.env(), clear=True), \
                mock.patch.object(socket.socket, "connect", connect), \
                mock.patch.object(socket.socket, "connect_ex", lambda s, a: connect(s, a)), \
                mock.patch.object(subprocess, "run", run_child):
            self.assertEqual(plug.main(["0.0.0-test", "doctor", "--json"], out=out), 0)
        self.assertEqual(off, [])
        self.assertFalse([c for c in children if any("agentroute" in str(w) for w in c)], children)
        self.assertEqual(json.loads(out.getvalue())["failed"], 0)
        # with a backends file the lane is set up: the router's rows, its FAIL a fail, exit 0
        self.write_backends(json.dumps({"tortoise": {"url": "http://127.0.0.1:9911"}}))
        doc = self.answer(self.run_a("doctor", "--json"))
        status = {c["name"]: c["status"] for c in doc["checks"]}
        self.assertEqual(status["router"], "fail")
        self.assertIn("upstream", status)
        self.assertNotIn("lane", status)
        self.assertEqual(doc["failed"], sum(c["status"] == "fail" for c in doc["checks"]))

    # 9
    def test_9_doctor_text(self):
        run = self.run_a("doctor")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        out = run.stdout.decode()
        lane = out.split("  Local lane:\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(len(lane.splitlines()), 1, lane)
        self.assertIn("no local lane is set up here", lane)
        self.assertNotRegex(out, r"(?m)^ +FAIL ")
        self.write_backends(json.dumps({"tortoise": {"url": "http://127.0.0.1:9911"}}))
        out = self.run_a("doctor").stdout.decode()
        self.assertRegex(out, r"(?m)^      FAIL  router ")
        self.assertRegex(out, r"(?m)^      (ok|warn|FAIL) +backend tortoise ")

    # 10
    def test_10_status(self):
        before = self.snapshot()
        empty = os.path.join(self.t, "sessions")
        os.makedirs(empty)
        # R1: the object stays as the pin prints it (indented), so it is read whole, not as a line
        run = self.run_a("status", "--json", CLAUDE_AGENTS_SESSIONS_DIR=empty)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn(b"\x1b", run.stdout)
        doc = json.loads(run.stdout.decode("utf-8"))
        self.assertEqual(list(doc)[:2], ["schema", "ok"])
        self.assertEqual((doc["schema"], doc["ok"]), ("agentik.agents.sessions/1", True))
        self.assertEqual(list(doc)[2:], ["generated", "since_min", "agents"])
        run = self.run_a("status", "--json")
        self.assertEqual(run.returncode, 1)
        self.assertEqual(run.stdout, b"")
        self.assertEqual(len(run.stderr.decode().splitlines()), 1, run.stderr)
        self.assertIn(b"cannot read the sessions dir", run.stderr)
        self.unchanged(before)

    def strict(self, run, code=0):
        """answer(), and the object is strict JSON: no NaN or Infinity."""
        doc = self.answer(run, code)

        def refuse(word):
            raise AssertionError("not JSON: %s in %r" % (word, run.stdout[:200]))
        json.loads(run.stdout.decode("utf-8"), parse_constant=refuse)
        return doc

    def tree(self):
        """A copy of plugin/ under the temp dir, to break one file of it."""
        copy = os.path.join(self.t, "plugin")
        shutil.copytree(os.path.join(REPO, "plugin"), copy, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        return copy

    # review 1, R1-F1: no input a read takes ends in a traceback, an empty stdout or a word
    # that is not JSON; each answer is one object, ok true where the router goes on
    def test_11_no_traceback(self):
        deep = "[" * 1000
        cases = [({}, deep), ({"AGENTROUTE_BACKENDS": deep}, None),
                 ({"AGENTROUTE_BACKENDS": '{"x": {"model": NaN}}'}, None),
                 ({"AGENTROUTE_BACKENDS": '{"x": {"model": 1e400}}'}, None),
                 ({"AGENTROUTE_PING_AFTER_S": "nan"}, None),
                 ({"AGENTROUTE_TIMEOUT_S": "-inf"}, None),
                 ({"LOCALRIG_LLAMA_PORT": "²"}, None)]
        for extra, text in cases:
            with self.subTest(extra=sorted(extra), file=bool(text)):
                if os.path.exists(self.backends):
                    os.remove(self.backends)
                if text:
                    self.write_backends(text)
                doc = self.strict(self.run_a("describe", "config", "--json", **extra))
                self.assertIs(doc["ok"], True)
                if text or extra.get("AGENTROUTE_BACKENDS") == deep:
                    self.assertEqual([w["reason"] for w in doc["warnings"]], ["unreadable"])
                    self.assertIn("backends.default.url", self.by_key(doc))
                self.strict(self.run_a("doctor", "--json", **extra))
        if os.path.exists(self.backends):
            os.remove(self.backends)
        by =self.by_key(self.strict(self.run_a("describe", "config", "--json",
                                                AGENTROUTE_PING_AFTER_S="nan",
                                                LOCALRIG_LLAMA_PORT="²")))
        self.assertEqual(by["route.ping_after_s"]["value"], "nan")
        self.assertEqual(by["rig.llama_port"]["value"], "²")
        # a config folder the reads cannot look into: the router's file is no path here
        locked = os.path.join(self.config, "agentik")
        os.makedirs(os.path.join(locked, "agents"), exist_ok=True)
        os.chmod(locked, 0)
        self.addCleanup(os.chmod, locked, 0o700)
        doc = self.strict(self.run_a("describe", "config", "--json"))
        self.assertEqual(doc["layers"][1], {"name": "rig", "path": None, "present": False,
                                            "travels": False})
        self.assertIsNone(self.by_key(doc)["route.backends_file"]["value"])
        self.strict(self.run_a("doctor", "--json"))
        os.chmod(locked, 0o700)
        # any other fault inside a read: the contract's §2 answer, exit 2, never a traceback
        plug = load_plug()
        for argv, schema in ((["describe", "--json"], "describe"),
                             (["describe", "config", "--json"], "config"),
                             (["doctor", "--json"], "doctor")):
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(plug, "describe", side_effect=RecursionError("made-up")), \
                    mock.patch.object(plug, "config", side_effect=AttributeError("made-up")), \
                    mock.patch.object(plug, "doctor", side_effect=LookupError("made-up")):
                self.assertEqual(plug.main(["0.0.0-test"] + argv, out=out, err=err), 2)
            doc = json.loads(out.getvalue())
            self.assertEqual((doc["schema"], doc["ok"], doc["tool"], doc["error"]["code"]),
                             ("agentik.%s/1" % schema, False, "agents", "unreadable"))
            self.assertEqual(out.getvalue().count("\n"), 1)
        with mock.patch.object(plug, "lane_set_up", side_effect=OSError("made-up")):
            self.assertEqual(plug.main(["0.0.0-test", "lane"], out=io.StringIO()), 3)
        # review 1, N6: the plug gone, or dying before it answers: the dispatcher answers §2
        copy = self.tree()
        script = os.path.join(copy, "lib", "agents_plug.py")
        with open(script, encoding="utf-8") as handle:
            body = handle.read()
        for broken in (None, 'raise RuntimeError("made-up")\n' + body):
            if broken is None:
                os.remove(script)
            else:
                with open(script, "w", encoding="utf-8") as handle:
                    handle.write(broken)
            for argv, schema in ((["describe", "--json"], "describe"),
                                 (["describe", "config", "--json", "route.log"], "config"),
                                 (["doctor", "--json"], "doctor")):
                with self.subTest(broken=broken is not None, argv=argv):
                    run = subprocess.run(SANDBOX + [os.path.join(copy, "lib", "agentik-agents")]
                                         + argv, cwd=self.t, env=self.env(), capture_output=True,
                                         timeout=60)
                    doc = self.strict(run, 2)
                    self.assertEqual((doc["schema"], doc["ok"], doc["error"]["code"]),
                                     ("agentik.%s/1" % schema, False, "unreadable"))
        # a malformed argv stays the usage on stderr, exit 2, nothing on stdout
        run = self.run_a("describe", "--bogus")
        self.assertEqual((run.returncode, run.stdout), (2, b""))
        self.assertIn(b"usage:", run.stderr)

    # review 1, N5: a plug that dies is no answer, so the text doctor asks the router as at the
    # pin; only the plug's own "no" is the one line
    def test_12_doctor_text_dead_plug(self):
        copy = self.tree()
        script = os.path.join(copy, "lib", "agents_plug.py")
        with open(script, encoding="utf-8") as handle:
            body = handle.read()
        with open(script, "w", encoding="utf-8") as handle:
            handle.write('raise RuntimeError("made-up")\n' + body)
        run = subprocess.run(SANDBOX + [os.path.join(copy, "lib", "agentik-agents"), "doctor"],
                             cwd=self.t, env=self.env(AGENTROUTE_LISTEN="127.0.0.1:9"),
                             capture_output=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        out = run.stdout.decode()
        self.assertNotIn("no local lane is set up here", out)
        self.assertRegex(out, r"(?m)^      FAIL  router ")
        plug = load_plug()
        for up, word, code in ((True, "yes", 0), (False, "no", 1)):
            out = io.StringIO()
            with mock.patch.object(plug, "lane_set_up", return_value=up):
                self.assertEqual(plug.main(["0.0.0-test", "lane"], out=out), code)
            self.assertEqual(out.getvalue(), word + "\n")

    # review 1, R1-F2: a key whose value moves with a variable, its own or one its value is
    # computed from, reads source env with an env row last; its default never moves
    def test_13_derived(self):
        before = self.snapshot()
        base = self.by_key(self.config_read())
        names = set(re.findall(r'\benv(?:_num)?\("([A-Z0-9_]+)"', read("agentroute"))) - {"BACKENDS"}
        names = {"AGENTROUTE_" + n for n in names}
        for script in ("claude-local", "localrig"):
            names |= set(re.findall(r"\$\{((?:CLAUDE_LOCAL|LOCALRIG|AGENTIK)_[A-Z0-9_]+)",
                                    read(script)))
        self.assertIn("AGENTIK_AGENTS_SECRETS", names)
        moved = set()
        for var in sorted(names):
            plain = [s for k, s in base.items() if s["change"]["command"]
                     and s["change"]["command"].startswith(var + "=")]
            was = plain[0]["value"] if plain else None
            value = ("off" if isinstance(was, bool) else "7" if isinstance(was, (int, float))
                     else "/srv/made-up/v")
            doc = self.config_read(**{var: value})
            for key, s in self.by_key(doc).items():
                if key not in base or s["value"] == base[key]["value"]:
                    continue
                with self.subTest(var=var, key=key):
                    moved.add(key)
                    self.assertEqual(s["source"], {"layer": "env", "path": None, "line": None})
                    self.assertEqual(s["values"][-1], {"layer": "env", "value": s["value"]})
                    self.assertEqual(s["default"], base[key]["default"])
                    self.assertIs(doc["layers"][2]["present"], True)
        self.assertTrue({"route.log", "rig.secrets_file", "backends.default.url"} <= moved, moved)
        s = self.by_key(self.config_read("route.log", AGENTROUTE_STATE_DIR="/srv/made-up/state"))
        s = s["route.log"]
        self.assertEqual(s["value"], "/srv/made-up/state/requests.jsonl")
        self.assertEqual([v["layer"] for v in s["values"]], ["default", "env"])
        s = self.by_key(self.config_read("rig.secrets_file", AGENTIK_AGENTS_SECRETS="/srv/sec"))
        s = s["rig.secrets_file"]
        self.assertEqual(s["value"], "/srv/sec/local-backends.sops.yaml")
        self.assertEqual(s["default"], os.path.join(self.config, "agentik", "agents", "secrets",
                                                    "local-backends.sops.yaml"))
        self.unchanged(before)


if __name__ == "__main__":
    unittest.main(verbosity=1)
