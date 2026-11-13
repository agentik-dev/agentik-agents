#!/usr/bin/env python3
"""Packet al2-wall: the API lane's wall, the key's store, the loopback stub and the probe.

Run as `python3 tests/test_al2_wall.py [Class]`. Each wall test starts the real
/usr/bin/sandbox-exec around this file's own fake, in a temp home; where `wall.backend()` is None,
as on Linux, or where a wall cannot start, it skips with one printed reason, as
tests/test-bare-machine.py does, and the suite still ends OK. CheckDirsTest, KeyTest, StubTest,
EnsureTest and WallStartTest's no-backend half need no wall and run everywhere.

No test starts tests/fake-claude, the real claude, sops or age-keygen: every fake is written here,
into a temp folder, on a PATH built from nothing. Every key is made up. Nothing leaves the
machine: the stub binds loopback, and NetTest's one outside connect runs only inside the wall.
"""

import importlib
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from unittest import mock

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(REPO, "plugin", "lib"))

VERSION = "9.9.9"
SCHEMA = "agentik.api.probe/1"
PROBE_KEYS = {"schema", "cli_version", "at", "ok", "restricted", "checks"}
CHECKS = ["key", "tools", "walled", "restricted", "read"]
MACOS_ADDS = ("__CF_USER_TEXT_ENCODING",)  # the system sets it at every exec on macOS


def load(name):
    return importlib.import_module("apilane." + name)


def fake_python():
    """A real interpreter outside any home, so a fake starts under the wall (no shim's env)."""
    try:
        run = subprocess.run(["/usr/bin/python3", "-c", "import sys; print(sys.executable)"],
                             capture_output=True, text=True, timeout=60,
                             env={"PATH": "/usr/bin:/bin"})
        if run.returncode == 0 and run.stdout.strip():
            return os.path.realpath(run.stdout.strip())
    except OSError:
        pass
    return os.path.realpath(sys.executable)


FAKE_PY = fake_python()


def wall_starts():
    try:
        return subprocess.run(["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)",
                               "/usr/bin/true"], capture_output=True, timeout=30).returncode == 0
    except OSError:
        return False


class Home:
    """A temp home, real path, removed at the end."""

    def __init__(self, case):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="al2-home-"))
        case.addCleanup(shutil.rmtree, self.root, True)

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def mkdir(self, *parts):
        p = self.path(*parts)
        os.makedirs(p, exist_ok=True)
        return p

    def write(self, rel, text, mode=0o644):
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(p, mode)
        return p

    def roots(self):
        cfg = self.path(".config", "agentik", "agents")
        return types.SimpleNamespace(
            home=self.root, config=os.path.join(cfg, "config.yaml"),
            state=self.path(".local", "state", "agentik-agents", "api"),
            store=os.path.join(cfg, "secrets", "anthropic-api-key.sops.yaml"))


def code(exc):
    return getattr(exc, "code", None), getattr(exc, "fields", None)


class WallCase(unittest.TestCase):
    """A test that starts the real wall: it skips, with its reason printed, where none starts."""

    def setUp(self):
        self.wall = load("wall")
        self.home = Home(self)
        self.fake = self.home.write("tools/fake", "#!/bin/sh\n"
                                    "if [ -n \"$FAKE_MARK\" ]; then : > \"$FAKE_MARK\"; fi\n"
                                    "exec \"$@\"\n", 0o755)

    def need_wall(self):
        if self.wall.backend() is None:
            self.skipTest("no wall backend on %s: the walled half stays unrun" % sys.platform)
        if not wall_starts():
            self.skipTest("sandbox-exec cannot start a wall here: the walled half stays unrun")

    def walled(self, argv, read=(), write=(), net="all", env=None, profile_edit=None):
        self.need_wall()
        cmd = self.wall.wrap([self.fake] + list(argv), read=list(read), write=list(write),
                             net=net, home=self.home.root)
        if profile_edit:
            cmd = profile_edit(cmd)
        base = {"PATH": "/usr/bin:/bin", "HOME": self.home.root}
        base.update(env or {})
        return subprocess.run(cmd, capture_output=True, text=True, env=base, cwd="/", timeout=60)

    def refused(self, run, text):
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertNotIn(text, run.stdout + run.stderr)


class WallReadTest(WallCase):

    def setUp(self):
        super().setUp()
        self.canary = self.home.write("private/canary.txt", "canary-home-text\n")
        self.job = self.home.mkdir("job")
        self.home.write("job/file.txt", "job-file-text\n")
        os.symlink(self.canary, os.path.join(self.job, "link.txt"))

    def test_by_path(self):
        self.refused(self.walled(["/bin/cat", self.canary], read=[self.job]), "canary-home-text")

    def test_through_a_symlink_in_a_job_dir(self):
        self.refused(self.walled(["/bin/cat", os.path.join(self.job, "link.txt")],
                                 read=[self.job]), "canary-home-text")

    def test_from_a_child_sh(self):
        self.refused(self.walled(["/bin/sh", "-c", "/bin/cat '%s'" % self.canary],
                                 read=[self.job]), "canary-home-text")

    def test_by_listing_its_folder(self):
        self.refused(self.walled(["/bin/ls", os.path.dirname(self.canary)], read=[self.job]),
                     "canary.txt")

    def test_a_job_file_reads(self):
        run = self.walled(["/bin/cat", os.path.join(self.job, "file.txt")], read=[self.job])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("job-file-text", run.stdout)

    def test_private_tmp_outside_the_job_dir(self):
        self.need_wall()
        folder = os.path.realpath(tempfile.mkdtemp(dir="/private/tmp", prefix="al2-tmp-"))
        self.addCleanup(shutil.rmtree, folder, True)
        canary = os.path.join(folder, "canary.txt")
        with open(canary, "w", encoding="utf-8") as handle:
            handle.write("canary-tmp-text\n")
        self.refused(self.walled(["/bin/cat", canary], read=[self.job]), "canary-tmp-text")


class WallWriteTest(WallCase):

    def test_write_folder_takes_a_file_and_read_folder_refuses(self):
        job, out = self.home.mkdir("job"), self.home.mkdir("out")
        run = self.walled(["/bin/sh", "-c", "echo w > '%s/new.txt'" % out], read=[job],
                          write=[out])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(os.path.isfile(os.path.join(out, "new.txt")))
        run = self.walled(["/bin/sh", "-c", "echo w > '%s/new.txt'" % job], read=[job],
                          write=[out])
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(job, "new.txt")))


class WallSecretTest(WallCase):

    def test_a_secret_root_inside_a_read_folder_stays_denied(self):
        keys = self.home.write(".config/sops/age/keys.txt", "made-up-identity-text\n", 0o600)
        plain = self.home.write(".config/plain.txt", "plain-config-text\n")
        config = self.home.path(".config")
        self.refused(self.walled(["/bin/cat", keys], read=[config]), "made-up-identity-text")
        run = self.walled(["/bin/cat", plain], read=[config])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("plain-config-text", run.stdout)


class WallStartTest(WallCase):

    def test_a_fake_under_the_home_starts_as_argv0(self):
        out = self.home.mkdir("out")
        mark = os.path.join(out, "mark")
        run = self.walled(["/bin/echo", "started"], write=[out], env={"FAKE_MARK": mark})
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("started", run.stdout)
        self.assertTrue(os.path.exists(mark))

    def test_a_broken_profile_exits_65_and_leaves_no_mark(self):
        out = self.home.mkdir("out")
        mark = os.path.join(out, "mark")

        def broken(cmd):
            cmd = list(cmd)
            at = cmd.index("-p") + 1
            cmd[at] = cmd[at] + "(deny file-read* (subpath"
            return cmd
        run = self.walled(["/bin/echo", "started"], write=[out], env={"FAKE_MARK": mark},
                          profile_edit=broken)
        self.assertEqual(run.returncode, 65, run.stderr)
        self.assertFalse(os.path.exists(mark))

    def test_no_backend_raises_wall_platform(self):
        with mock.patch.object(self.wall.sys, "platform", "linux"):
            self.assertIsNone(self.wall.backend())
            with self.assertRaises(Exception) as cm:
                self.wall.wrap([self.fake], read=[], write=[], net="all", home=self.home.root)
        self.assertEqual(code(cm.exception), ("wall.platform", {"platform": "linux"}))
        self.assertEqual(str(cm.exception), "wall.platform")


class CheckDirsTest(unittest.TestCase):

    def setUp(self):
        self.wall = load("wall")
        self.home = Home(self)

    def why(self, d):
        with self.assertRaises(Exception) as cm:
            self.wall.check_dirs([d], home=self.home.root)
        c, fields = code(cm.exception)
        self.assertEqual(c, "wall.dir")
        return fields["why"]

    def test_root_home_secret_missing(self):
        self.assertEqual(self.why("/"), "root")
        self.assertEqual(self.why(self.home.root), "home")
        self.assertEqual(self.why(os.path.dirname(self.home.root)), "home")
        other = os.path.realpath(tempfile.mkdtemp(prefix="al2-link-"))
        self.addCleanup(shutil.rmtree, other, True)
        os.symlink(self.home.root, os.path.join(other, "to-home"))
        self.assertEqual(self.why(os.path.join(other, "to-home")), "home")
        self.assertEqual(self.why(self.home.mkdir(".ssh")), "secret")
        self.assertEqual(self.why(self.home.mkdir(".ssh", "inner")), "secret")
        self.assertEqual(self.why(self.home.mkdir(".config")), "secret")
        self.assertEqual(self.why(self.home.mkdir("Library")), "secret")
        self.assertEqual(self.why(self.home.write("work/a-file.txt", "x")), "missing")
        self.assertEqual(self.why(self.home.path("nowhere")), "missing")

    def test_a_good_dir_is_its_real_path(self):
        good = self.home.mkdir("work", "project")
        os.symlink(good, self.home.path("link-to-project"))
        got = self.wall.check_dirs([self.home.path("link-to-project"), good],
                                   home=self.home.root)
        self.assertEqual(got, [good, good])


class NetTest(WallCase):

    def test_loopback_reaches_the_stub_and_the_outside_is_refused(self):
        self.need_wall()
        stub = load("stubapi").Stub(reads=[])
        stub.start()
        self.addCleanup(stub.stop)
        port = stub.address[1]
        child = ("import socket, sys, time\n"
                 "s = socket.create_connection(('127.0.0.1', %d), timeout=5); s.close()\n"
                 "print('loopback ok')\n"
                 "t = time.time()\n"
                 "try:\n"
                 "    socket.create_connection(('192.0.2.1', 9), timeout=3)\n"
                 "    print('outside connected')\n"
                 "except PermissionError:\n"
                 "    print('outside refused %%.2f' %% (time.time() - t))\n"
                 "except OSError as e:\n"
                 "    print('outside other %%s' %% e)\n" % port)
        # the wall must hold before the outside connect is tried: a home canary is unreadable
        canary = self.home.write("private/canary.txt", "net-canary-text\n")
        self.refused(self.walled(["/bin/cat", canary], net="loopback"), "net-canary-text")
        run = self.walled([FAKE_PY, "-I", "-c", child], net="loopback")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("loopback ok", run.stdout)
        self.assertIn("outside refused", run.stdout, run.stdout)
        self.assertLess(float(run.stdout.split("outside refused")[1].split()[0]), 1.0)


SOPS = r'''#!%(py)s
import json, os, sys
LOG = %(log)r
args = sys.argv[1:]
data = sys.stdin.read() if "encrypt" in args else ""
with open(os.path.join(LOG, "argv.jsonl"), "a") as handle:
    handle.write(json.dumps(["sops"] + args) + "\n")
if os.path.exists(os.path.join(LOG, "fail")):
    sys.exit(1)
if args[:1] == ["encrypt"]:
    with open(os.path.join(LOG, "stdin.txt"), "a") as handle:
        handle.write(data)
    name, _, value = data.strip().partition(": ")
    value = value[1:-1].replace("''", "'")
    sys.stdout.write("%%s: ENC[AES256_GCM,data:%%s,type:str]\nsops:\n    version: fake\n"
                     %% (name, value.encode().hex()))
    sys.exit(0)
if args[:1] == ["decrypt"]:
    with open(args[-1]) as handle:
        text = handle.read()
    print(bytes.fromhex(text.split("data:")[1].split(",")[0]).decode())
    sys.exit(0)
sys.exit(3)
'''

AGE_KEYGEN = r'''#!%(py)s
import json, os, sys
LOG = %(log)r
with open(os.path.join(LOG, "argv.jsonl"), "a") as handle:
    handle.write(json.dumps(["age-keygen"] + sys.argv[1:]) + "\n")
if os.path.exists(os.path.join(LOG, "keygen-fail")):
    sys.exit(1)
print("age1madeuprecipientqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq")
'''


class KeyTest(unittest.TestCase):

    VALUE = "made-up-value-with-a-'quote-0123"

    def setUp(self):
        self.key = load("key")
        self.home = Home(self)
        self.roots = self.home.roots()
        self.log = self.home.mkdir("log")
        self.bin = self.home.mkdir("bin")
        self.empty = self.home.mkdir("empty-bin")
        for name, body in (("sops", SOPS), ("age-keygen", AGE_KEYGEN)):
            self.home.write("bin/" + name, body % {"py": FAKE_PY, "log": self.log}, 0o755)
        env = mock.patch.dict(os.environ, {"PATH": self.bin, "HOME": self.home.root,
                                           "ANTHROPIC_API_KEY": "planted-env-value"},
                              clear=True)
        env.start()
        self.addCleanup(env.stop)

    def argvs(self):
        p = os.path.join(self.log, "argv.jsonl")
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def raises(self, fn, *a, **kw):
        with self.assertRaises(Exception) as cm:
            fn(*a, **kw)
        return code(cm.exception)

    def test_store_load_remove(self):
        self.key.store(self.VALUE, roots=self.roots)
        with open(os.path.join(self.log, "stdin.txt"), encoding="utf-8") as handle:
            self.assertIn("anthropic_api_key: '%s'" % self.VALUE.replace("'", "''"),
                          handle.read())
        for argv in self.argvs():
            self.assertNotIn("made-up-value", " ".join(argv))
        ident = (os.path.join(self.home.root, "Library", "Application Support", "sops", "age",
                              "keys.txt") if sys.platform == "darwin"
                 else os.path.join(self.home.root, ".config", "sops", "age", "keys.txt"))
        self.assertIn(["age-keygen", "-y", ident], self.argvs())
        self.assertEqual(stat.S_IMODE(os.stat(self.roots.store).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.roots.store)).st_mode), 0o700)
        self.assertEqual(os.listdir(os.path.dirname(self.roots.store)),
                         [os.path.basename(self.roots.store)])
        self.assertTrue(self.key.present(self.roots))
        self.assertEqual(self.key.load(self.roots), self.VALUE)
        self.assertTrue(self.key.remove(self.roots))
        self.assertFalse(self.key.remove(self.roots))
        self.assertFalse(self.key.present(self.roots))

    def test_the_recipient_given_and_sops_age_key_file(self):
        self.key.store(self.VALUE, roots=self.roots, recipient="age1givenrecipientqqqq")
        self.assertFalse([a for a in self.argvs() if a[0] == "age-keygen"])
        self.assertTrue([a for a in self.argvs() if "age1givenrecipientqqqq" in a])
        os.environ["SOPS_AGE_KEY_FILE"] = self.home.path("elsewhere", "keys.txt")
        self.key.store(self.VALUE, roots=self.roots)
        self.assertIn(["age-keygen", "-y", self.home.path("elsewhere", "keys.txt")],
                      self.argvs())

    def test_codes(self):
        self.assertEqual(self.raises(self.key.load, self.roots),
                         ("key.none", {"store": self.roots.store}))
        self.key.store(self.VALUE, roots=self.roots)
        open(os.path.join(self.log, "fail"), "w").close()
        self.assertEqual(self.raises(self.key.load, self.roots), ("key.decrypt", {"rc": 1}))
        os.unlink(os.path.join(self.log, "fail"))
        open(os.path.join(self.log, "keygen-fail"), "w").close()
        self.assertEqual(self.raises(self.key.store, self.VALUE, roots=self.roots),
                         ("key.recipient", {}))
        os.environ["PATH"] = self.empty
        self.assertEqual(self.raises(self.key.load, self.roots), ("key.tools", {"tool": "sops"}))
        self.assertEqual(self.raises(self.key.store, self.VALUE, roots=self.roots,
                                     recipient="age1givenrecipientqqqq"),
                         ("key.tools", {"tool": "sops"}))

    def test_a_planted_environment_key_is_never_returned(self):
        self.key.store(self.VALUE, roots=self.roots)
        self.assertEqual(self.key.load(self.roots), self.VALUE)
        self.key.remove(self.roots)
        c, _ = self.raises(self.key.load, self.roots)
        self.assertEqual(c, "key.none")


def post(url, body, headers=None):
    req = urllib.request.Request(url + "/v1/messages", data=json.dumps(body).encode(),
                                 headers=dict({"content-type": "application/json"},
                                              **(headers or {})))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=10) as resp:
        return resp.headers.get("content-type", ""), resp.read().decode()


def from_stream(text):
    """Assemble a streamed reply into the whole message's content and stop reason."""
    content, stop, partial = [], None, {}
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        ev = json.loads(line[6:])
        if ev["type"] == "content_block_start":
            content.append(dict(ev["content_block"]))
            partial[ev["index"]] = ""
        elif ev["type"] == "content_block_delta":
            d = ev["delta"]
            if d["type"] == "input_json_delta":
                partial[ev["index"]] += d["partial_json"]
            else:
                content[ev["index"]]["text"] = content[ev["index"]].get("text", "") + d["text"]
        elif ev["type"] == "content_block_stop" and content[ev["index"]]["type"] == "tool_use":
            content[ev["index"]]["input"] = json.loads(partial[ev["index"]] or "{}")
        elif ev["type"] == "message_delta":
            stop = ev["delta"]["stop_reason"]
    return content, stop


class StubTest(unittest.TestCase):

    def setUp(self):
        self.stub = load("stubapi").Stub(reads=["/made/up/one", "/made/up/two", "/made/up/3"])
        self.url = self.stub.start()
        self.addCleanup(self.stub.stop)

    def test_binds_loopback_alone(self):
        self.assertTrue(self.url.startswith("http://127.0.0.1:"), self.url)
        self.assertEqual(self.stub.address[0], "127.0.0.1")
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 9))     # a UDP connect sends nothing: it picks an address
            mine = probe.getsockname()[0]
        except OSError:
            mine = None
        finally:
            probe.close()
        if mine and not mine.startswith("127."):
            with self.assertRaises(OSError):
                socket.create_connection((mine, self.stub.address[1]), timeout=2).close()

    def test_plays_its_script_and_records(self):
        messages = [{"role": "user", "content": "go"}]
        tools = [{"name": "Read"}, {"name": "Grep"}]
        heads = {"x-api-key": "made-up-test-key", "authorization": "Bearer made-up-bearer"}
        seen = []
        for turn in range(4):
            body = {"model": "m", "max_tokens": 9, "messages": messages, "tools": tools,
                    "stream": turn % 2 == 1}
            kind, text = post(self.url, body, heads)
            if turn % 2:
                self.assertIn("text/event-stream", kind)
                content, stop = from_stream(text)
            else:
                reply = json.loads(text)
                content, stop = reply["content"], reply["stop_reason"]
            seen.append((content, stop))
            messages.append({"role": "assistant", "content": content})
            if stop == "tool_use":
                messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": content[0]["id"],
                     "content": "result-%d" % turn}]})
        for turn, path in enumerate(["/made/up/one", "/made/up/two", "/made/up/3"]):
            content, stop = seen[turn]
            self.assertEqual(stop, "tool_use")
            self.assertEqual([(b["type"], b["name"], b["input"]["file_path"]) for b in content],
                             [("tool_use", "Read", path)])
        self.assertEqual(seen[3][1], "end_turn")
        self.assertEqual(seen[3][0][0]["type"], "text")
        self.assertEqual(len(self.stub.requests), 4)
        for rec in self.stub.requests:
            self.assertEqual(rec["credentials"], {"x-api-key": "made-up-test-key",
                                                  "authorization": "Bearer made-up-bearer"})
            self.assertEqual(rec["tools"], ["Read", "Grep"])
        self.assertEqual(self.stub.requests[0]["tool_results"], [])
        self.assertIn("result-2", [r["text"] for r in self.stub.requests[3]["tool_results"]])

    def test_serves_nothing_else(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for req in (urllib.request.Request(self.url + "/"),
                    urllib.request.Request(self.url + "/v1/models"),
                    urllib.request.Request(self.url + "/v1/other", data=b"{}")):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                opener.open(req, timeout=10)
            self.assertEqual(cm.exception.code, 404)
        self.assertEqual(self.stub.requests, [])


FAKE_CLI = r'''#!%(py)s
import json, os, sys, urllib.request
MODE = %(mode)r
RECORD = %(record)r
args = sys.argv[1:]
if args[:1] == ["--version"]:
    print("%(version)s (Fake Code)")
    sys.exit(0)
if RECORD:
    with open(os.path.join(RECORD, "%%d.json" %% os.getpid()), "w") as handle:
        json.dump({"argv": sys.argv, "env": dict(os.environ)}, handle)
restricted = "--restricted" in args
if MODE == "noflag" and restricted:
    sys.stderr.write("error: unknown option '--restricted'\n")
    sys.exit(1)
dirs = [os.path.realpath(args[i + 1]) for i, a in enumerate(args) if a == "--add-dir"]
base = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
heads = {"content-type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"]}
if MODE == "bearer":
    heads["authorization"] = "Bearer " + os.environ["ANTHROPIC_API_KEY"]
tools = ["Read", "Grep", "Glob"] + (["Bash"] if MODE == "bash" else [])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def inside(p):
    p = os.path.realpath(p)
    return any(p == d or p.startswith(d + "/") for d in dirs)

messages = [{"role": "user", "content": "probe"}]
for turn in range(8):
    body = {"model": "fake", "max_tokens": 64, "messages": messages,
            "tools": [{"name": t, "input_schema": {"type": "object"}} for t in tools]}
    req = urllib.request.Request(base + "/v1/messages", data=json.dumps(body).encode(),
                                 headers=heads)
    with opener.open(req, timeout=20) as resp:
        reply = json.load(resp)
    messages.append({"role": "assistant", "content": reply["content"]})
    if reply.get("stop_reason") != "tool_use":
        break
    results = []
    for block in reply["content"]:
        if block.get("type") != "tool_use":
            continue
        path = block["input"].get("file_path", "")
        if MODE == "noread":
            text, err = "not read", True
        elif restricted and MODE != "outside" and not inside(path):
            text, err = "outside the working directories", True
        else:
            try:
                with open(path) as handle:
                    text, err = handle.read(), False
            except OSError as e:
                text, err = "read failed: %%s" %% e.strerror, True
        results.append({"type": "tool_result", "tool_use_id": block["id"], "content": text,
                        "is_error": err})
    messages.append({"role": "user", "content": results})
print(json.dumps({"type": "result", "result": "done"}))
'''


def build_argv(shard, *, claude, dirs, ceiling_usd, run_dir, restricted=True):
    argv = [claude, "--bare", "-p", shard.prompt, "--max-budget-usd", "%.4f" % ceiling_usd]
    for d in dirs:
        argv += ["--add-dir", d]
    return argv + (["--restricted"] if restricted else [])


def build_env(*, key, run_dir, home, path, proxy=None, ca_file=None, base_url=None):
    env = {"PATH": path, "HOME": home, "LANG": "en_US.UTF-8", "TERM": "dumb", "TMPDIR": run_dir,
           "CLAUDE_CONFIG_DIR": os.path.join(run_dir, "config"), "ANTHROPIC_API_KEY": key}
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    return env


def open_wrap(argv, *, read, write, net, home):
    """A stand-in that walls nothing."""
    return list(argv)


class ProbeCase(WallCase):

    def setUp(self):
        super().setUp()
        self.probe = load("probe")
        self.roots = self.home.roots()

    def cli(self, mode="good", record=None):
        return self.home.write("tools/claude-" + mode, FAKE_CLI % {
            "py": FAKE_PY, "mode": mode, "record": record, "version": VERSION}, 0o755)

    def run_probe(self, mode="good", wrap=None, **kw):
        if wrap is None:
            self.need_wall()
        return self.probe.run(claude=self.cli(mode), roots=self.roots, build_argv=build_argv,
                              build_env=build_env, wrap=wrap, **kw)

    def checks(self, rec):
        return {c["name"]: c["ok"] for c in rec["checks"]}


class ProbeTest(ProbeCase):

    def test_all_five_pass_and_the_record(self):
        left = set(os.listdir(tempfile.gettempdir()))
        rec = self.run_probe("good")
        self.assertEqual(self.checks(rec), dict.fromkeys(CHECKS, True), rec)
        self.assertIs(rec["ok"], True)
        self.assertIs(rec["restricted"], True)
        path = os.path.join(self.roots.state, "probe.json")
        with open(path, encoding="utf-8") as handle:
            disk = json.load(handle)
        self.assertEqual(disk, rec)
        self.assertEqual(set(disk), PROBE_KEYS)
        self.assertEqual(disk["schema"], SCHEMA)
        self.assertEqual(disk["cli_version"], VERSION)
        self.assertTrue(disk["at"].endswith("Z"))
        self.assertEqual([c["name"] for c in disk["checks"]], CHECKS)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(os.listdir(self.roots.state), ["probe.json"])
        self.assertEqual(set(os.listdir(tempfile.gettempdir())) - left, set())

    def test_a_bearer_token_fails_key(self):
        rec = self.run_probe("bearer")
        self.assertIs(self.checks(rec)["key"], False)
        self.assertIs(rec["ok"], False)

    def test_bash_offered_fails_tools(self):
        rec = self.run_probe("bash")
        self.assertIs(self.checks(rec)["tools"], False)
        self.assertIs(rec["ok"], False)

    def test_a_wrap_that_walls_nothing_fails_walled(self):
        rec = self.run_probe("outside", wrap=open_wrap)
        self.assertIs(self.checks(rec)["walled"], False)
        self.assertIs(rec["ok"], False)

    def test_reading_the_outside_canary_is_restricted_false_and_ok(self):
        rec = self.run_probe("outside")
        self.assertIs(rec["restricted"], False)
        self.assertIs(self.checks(rec)["restricted"], False)
        self.assertIs(rec["ok"], True, rec)

    def test_a_refused_flag_runs_again_and_records_null(self):
        rec = self.run_probe("noflag")
        self.assertIsNone(rec["restricted"])
        self.assertIs(rec["ok"], True, rec)

    def test_never_reading_fails_read(self):
        rec = self.run_probe("noread")
        self.assertIs(self.checks(rec)["read"], False)
        self.assertIs(rec["ok"], False)


class ProbeArgvTest(ProbeCase):

    def test_the_fake_ran_exactly_what_the_builders_and_wrap_gave(self):
        rec_dir = self.home.mkdir("rec")
        claude = self.cli("good", record=rec_dir)
        calls = []

        def b_argv(shard, **kw):
            out = build_argv(shard, **kw)
            calls.append(("argv", kw, out))
            return out

        def b_env(**kw):
            out = build_env(**kw)
            calls.append(("env", kw, out))
            return out

        def wrap(argv, **kw):
            out = list(argv)
            calls.append(("wrap", kw, out))
            return out

        keys = []
        for _ in range(2):
            del calls[:]
            for name in os.listdir(rec_dir):
                os.unlink(os.path.join(rec_dir, name))
            self.probe.run(claude=claude, roots=self.roots, build_argv=b_argv,
                           build_env=b_env, wrap=wrap)
            (seen,) = [json.load(open(os.path.join(rec_dir, n))) for n in os.listdir(rec_dir)]
            got = {kind: (kw, out) for kind, kw, out in calls}
            self.assertEqual(seen["argv"], got["wrap"][1])
            env = {k: v for k, v in seen["env"].items() if k not in MACOS_ADDS}
            self.assertEqual(env, got["env"][1])
            argv_kw, env_kw, wrap_kw = got["argv"][0], got["env"][0], got["wrap"][0]
            job = argv_kw["dirs"][0]
            self.assertEqual(argv_kw["ceiling_usd"], 0.05)
            self.assertIs(argv_kw["restricted"], True)
            self.assertEqual(argv_kw["claude"], claude)
            self.assertEqual(wrap_kw, {"read": [job], "write": [argv_kw["run_dir"]],
                                       "net": "loopback", "home": self.roots.home})
            self.assertEqual(env_kw["run_dir"], argv_kw["run_dir"])
            self.assertEqual(env_kw["home"], self.roots.home)
            self.assertTrue(env_kw["base_url"].startswith("http://127.0.0.1:"))
            self.assertFalse(env_kw["key"].startswith("sk-"))
            keys.append(env_kw["key"])
        self.assertNotEqual(keys[0], keys[1])


class EnsureTest(ProbeCase):

    def write_record(self, **over):
        rec = {"schema": SCHEMA, "cli_version": VERSION, "at": "2026-01-01T00:00:00Z",
               "ok": True, "restricted": True,
               "checks": [{"name": n, "ok": True, "detail": ""} for n in CHECKS]}
        rec.update(over)
        os.makedirs(self.roots.state, exist_ok=True)
        with open(os.path.join(self.roots.state, "probe.json"), "w", encoding="utf-8") as h:
            json.dump(rec, h)
        return rec

    def ensure(self, mode="good"):
        self.runs, self.events = [], []

        def b_argv(shard, **kw):
            self.runs.append(kw)
            return build_argv(shard, **kw)
        return self.probe.ensure(claude=self.cli(mode), roots=self.roots, build_argv=b_argv,
                                 build_env=build_env, wrap=open_wrap,
                                 emit=lambda ev, **f: self.events.append((ev, f)))

    def test_a_passing_record_returns_with_no_run(self):
        rec = self.write_record()
        self.assertEqual(self.ensure(), rec)
        self.assertEqual((self.runs, self.events), ([], []))

    def test_a_new_version_runs_once_and_emits(self):
        self.write_record(cli_version="9.9.8")
        rec = self.ensure()
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(self.events, [("probe.start", {"cli_version": VERSION})])
        self.assertIs(rec["ok"], True, rec)
        self.assertEqual(rec["cli_version"], VERSION)
        self.ensure()
        self.assertEqual((self.runs, self.events), ([], []))

    def test_a_failing_run_raises_probe_fail(self):
        with self.assertRaises(Exception) as cm:
            self.ensure("bash")
        c, fields = code(cm.exception)
        self.assertEqual(c, "probe.fail")
        self.assertEqual(fields["check"], "tools")
        self.assertIn("detail", fields)

    def test_passed(self):
        self.assertFalse(self.probe.passed(self.roots, VERSION))
        self.assertIsNone(self.probe.read(self.roots))
        self.write_record()
        self.assertTrue(self.probe.passed(self.roots, VERSION))
        self.assertFalse(self.probe.passed(self.roots, "9.9.8"))
        self.write_record(ok=False)
        self.assertFalse(self.probe.passed(self.roots, VERSION))
        with open(os.path.join(self.roots.state, "probe.json"), "w", encoding="utf-8") as h:
            h.write("not json {")
        self.assertFalse(self.probe.passed(self.roots, VERSION))
        self.assertIsNone(self.probe.read(self.roots))

    def test_cli_version_is_the_first_word(self):
        self.assertEqual(self.probe.cli_version(self.cli()), VERSION)


if __name__ == "__main__":
    unittest.main(verbosity=2)
