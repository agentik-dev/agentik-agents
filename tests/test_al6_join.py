#!/usr/bin/python3
"""tests/test_al6_join.py: the API lane's join (packet al6-join).

Every place is handed in: `roots` under a temp home, a stand-in for each part the lane would
reach. No test reads the real config file, state folder or gate list, starts `claude`, reads a
key or opens a socket. Stdlib, 3.9.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
LIB = os.path.join(REPO, "plugin", "lib")
sys.dont_write_bytecode = True
sys.path.insert(0, LIB)

from apilane import cli, config, paths  # noqa: E402

OFF = ('agentik agents fanout: the API lane is off on this machine. To turn it on, add "api:" '
       'and, indented under it, "enabled: true" to ~/.config/agentik/agents/config.yaml; then '
       '"agentik agents api status" lists the steps left.')
NOTE = "claude-fanout: the name is now agentik agents fanout; this one ends on 2026-12-31."


def walled_in_sh():
    """What prefilter.sh's apilane_walled says on this platform."""
    got = subprocess.run(["/bin/sh", "-c", 'apilane_dir=$1; . "$1/prefilter.sh"; apilane_walled',
                          "sh", os.path.join(LIB, "apilane")], stdin=subprocess.DEVNULL)
    return got.returncode == 0


def backend():
    from apilane import wall
    return wall.backend()


class Temp(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix="al6-")
        self.addCleanup(shutil.rmtree, self.t, True)
        home = os.path.join(self.t, "home")
        os.makedirs(home)
        conf = os.path.join(home, ".config", "agentik", "agents")
        self.roots = paths.Roots(home, os.path.join(conf, "config.yaml"),
                                 os.path.join(home, ".local", "state", "agentik-agents", "api"),
                                 os.path.join(conf, "secrets", "anthropic-api-key.sops.yaml"))

    def write_config(self, text):
        os.makedirs(os.path.dirname(self.roots.config), exist_ok=True)
        with open(self.roots.config, "w", encoding="utf-8") as fh:
            fh.write(text)


class OffVerbTest(Temp):
    def test_walled_agrees(self):
        self.assertEqual(walled_in_sh(), backend() is not None)

    def test_off_line(self):
        if backend() is None:
            print("skip: no wall is proved on this platform, so fanout is the stub",
                  file=sys.stderr)
            return
        tools = os.path.join(self.t, "tools")
        os.makedirs(tools)
        mark = os.path.join(self.t, "mark")
        old = os.path.join(tools, "claude-fanout")
        with open(old, "w") as fh:
            fh.write('#!/bin/sh\n: > "%s"\n' % mark)
        os.chmod(old, 0o755)
        parts = mock.Mock(side_effect=AssertionError("no part is called while off"))
        for argv in (["fanout", "a", "b"], ["fanout", "--help"]):
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.dict(os.environ, {"PATH": tools + os.pathsep + "/usr/bin:/bin"}):
                rc = cli.main(argv, roots=self.roots, parts=parts, stdout=out, stderr=err)
            self.assertEqual((rc, out.getvalue(), err.getvalue()), (2, "", OFF + "\n"), argv)
        self.assertFalse(os.path.exists(mark))


class ForwardTest(Temp):
    def setUp(self):
        super().setUp()
        self.lib = os.path.join(self.t, "lib")
        os.makedirs(self.lib)
        shutil.copy(os.path.join(LIB, "claude-fanout"), self.lib)
        stand = os.path.join(self.lib, "agentik-agents")
        with open(stand, "w") as fh:
            fh.write('#!/bin/sh\nfor a; do printf "[%s]\\n" "$a"; done\n')
        os.chmod(stand, 0o755)
        os.chmod(os.path.join(self.lib, "claude-fanout"), 0o755)
        self.bin = os.path.join(self.t, "bin")
        os.makedirs(self.bin)
        os.symlink(os.path.join(self.lib, "claude-fanout"), os.path.join(self.bin, "claude-fanout"))
        self.argv = [os.path.join(self.bin, "claude-fanout"), "--budget-usd", "2", "a b", "", "-x"]
        self.want = "[fanout]\n[--yes]\n[--budget-usd]\n[2]\n[a b]\n[]\n[-x]\n"

    def test_pipe(self):
        got = subprocess.run(self.argv, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual((got.returncode, got.stdout, got.stderr), (0, self.want, ""))

    def test_terminal(self):
        import pty
        master, slave = pty.openpty()
        try:
            got = subprocess.run(self.argv, stdout=subprocess.PIPE, stderr=slave, text=True,
                                 stdin=subprocess.DEVNULL)
            import select
            seen = b""
            while select.select([master], [], [], 1.0)[0]:
                chunk = os.read(master, 4096)
                if not chunk:
                    break
                seen += chunk
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)
        self.assertEqual(got.stdout, self.want)
        self.assertEqual(seen.decode().replace("\r\n", "\n"), NOTE + "\n")


    def test_status_names_an_old_one(self):
        self.assertEqual(cli.old_forward(path=self.bin), os.path.join(self.bin, "claude-fanout"))
        os.unlink(os.path.join(self.bin, "claude-fanout"))
        os.symlink(os.path.join(LIB, "claude-fanout"), os.path.join(self.bin, "claude-fanout"))
        self.assertIsNone(cli.old_forward(path=self.bin))
        self.assertIsNone(cli.old_forward(path=os.path.join(self.t, "none")))


class InstallTest(Temp):
    OLD = ("agentroute", "claude-agents", "claude-local", "localrig")

    def install(self, lane):
        import agents_install
        prefix = os.path.join(self.roots.home, "P")
        out, err = io.StringIO(), io.StringIO()
        env = {"HOME": self.roots.home, "XDG_CACHE_HOME": os.path.join(self.t, "cache")}
        with mock.patch.dict(os.environ, env):
            rc = agents_install.main(["--prefix", prefix], out=out, err=err, lane=lane)
        return rc, out.getvalue(), err.getvalue(), os.path.join(prefix, "bin")

    def plant(self, kind):
        bin_dir = os.path.join(self.roots.home, "P", "bin")
        os.makedirs(bin_dir, exist_ok=True)
        path = os.path.join(bin_dir, "claude-fanout")
        outside = os.path.join(self.t, "old-claude-fanout")
        with open(outside, "w") as fh:
            fh.write("#!/bin/sh\n")
        if kind == "link":
            os.symlink(outside, path)
        elif kind == "dangling":
            os.symlink(os.path.join(self.t, "gone"), path)
        else:
            with open(path, "w") as fh:
                fh.write("#!/bin/sh\n")
        return path, outside

    def test_off(self):
        path, outside = self.plant("link")
        rc, out, err, bin_dir = self.install(False)
        self.assertEqual(rc, 0, err)
        self.assertIn("linked %s in %s -> the tree (the old names, until 2026-12-31)\n"
                      % (", ".join(self.OLD), bin_dir), out)
        self.assertEqual(os.readlink(path), outside)
        for n in self.OLD:
            self.assertTrue(os.path.islink(os.path.join(bin_dir, n)), n)

    def test_on(self):
        path, _ = self.plant("link")
        rc, out, err, bin_dir = self.install(True)
        self.assertEqual(rc, 0, err)
        self.assertIn("linked %s, claude-fanout in" % ", ".join(self.OLD), out)
        share = os.path.realpath(os.path.join(self.roots.home, "P", "share"))
        self.assertTrue(os.path.realpath(path).startswith(share + os.sep), os.readlink(path))
        self.assertTrue(os.access(os.path.realpath(path), os.X_OK))

    def test_on_dangling(self):
        path, _ = self.plant("dangling")
        rc, _, err, _ = self.install(True)
        self.assertEqual(rc, 0, err)
        self.assertTrue(os.path.exists(path))

    def test_on_plain_file(self):
        path, _ = self.plant("file")
        rc, out, err, _ = self.install(True)
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.islink(path))
        self.assertIn("%s is not a link, left as it is; claude-fanout is not linked" % path, err)


class PlugTest(Temp):
    def plug(self):
        import agents_plug
        return agents_plug

    def test_config(self):
        doc = self.plug().config(roots=self.roots)
        user = [l for l in doc["layers"] if l["name"] == "user"]
        self.assertEqual(user, [{"name": "user", "path": self.roots.config, "present": False,
                                 "travels": False}])
        api = {s["key"]: s for s in doc["settings"] if s["key"].startswith("api.")}
        self.assertEqual(sorted(api), sorted("api." + k for k in config.KEYS))
        for k in config.KEYS:
            self.assertEqual(api["api." + k]["value"], getattr(config.DEFAULTS, k), k)
            self.assertIn("by hand", api["api." + k]["change"]["note"], k)
        self.write_config("api:\n  enabled: true\n  max_day_usd: 4\n")
        doc = self.plug().config(roots=self.roots)
        api = {s["key"]: s for s in doc["settings"] if s["key"].startswith("api.")}
        self.assertEqual(api["api.max_day_usd"]["value"], 4.0)
        self.assertEqual(api["api.max_day_usd"]["source"]["layer"], "user")
        self.assertTrue([l for l in doc["layers"] if l["name"] == "user"][0]["present"])

    def test_rider(self):
        self.assertEqual(self.plug().SUMMARIES["route.state_dir"],
                         "The folder that holds the router's pid file and, by default, its "
                         "request log.")

    def doctor(self, lane):
        plug = self.plug()
        parts = mock.Mock()
        parts.key_present.return_value = True
        parts.probe_read.return_value = {"ok": True, "cli_version": "9.9.9"}
        parts.wall_backend.return_value = "made-up"
        with mock.patch.dict(plug.KINDS, {"lane": lambda c: [], "python": lambda c: []}):
            return plug.doctor(lane=lane, roots=self.roots, parts=parts)

    def test_doctor(self):
        off = self.doctor(config.DEFAULTS)
        self.assertEqual([c for c in off["checks"] if c["name"].startswith("api")], [])
        on = self.doctor(config.DEFAULTS._replace(enabled=True))
        names = [c["name"] for c in on["checks"] if c["name"].startswith("api")]
        self.assertEqual(names, ["api key", "api probe", "api limit", "api wall", "api gates"])


# -- the money lines: real modules, the fake CLI, the loopback stub (packet al6, R6) ------------

FAKE = os.path.join(REPO, "tests", "fake-claude")
SESSION = "sess-e2e"
SOPS = r"""#!/usr/bin/python3
import sys
args = sys.argv[1:]
if args[:1] == ["encrypt"]:
    name, _, value = sys.stdin.read().strip().partition(": ")
    value = value[1:-1].replace("''", "'")
    sys.stdout.write("%s: ENC[AES256_GCM,data:%s,type:str]\nsops:\n    version: fake\n"
                     % (name, value.encode().hex()))
    sys.exit(0)
if args[:1] == ["decrypt"]:
    with open(args[-1]) as handle:
        text = handle.read()
    print(bytes.fromhex(text.split("data:")[1].split(",")[0]).decode())
    sys.exit(0)
sys.exit(3)
"""
AGE_KEYGEN = "#!/bin/sh\necho age1madeuprecipient%s\n" % ("q" * 40)
CHILD = r"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from apilane import cli, paths
roots = paths.Roots(*sys.argv[2:6])
sys.exit(cli.main(["fanout", sys.argv[6], "--yes"], roots=roots))
"""


def made_up(name):
    """A made-up value, new each run, shaped like no real key."""
    import secrets
    return "made-up-%s-%s" % (name, secrets.token_hex(6))


def wait_for(cond, limit=60.0):
    import time
    end = time.time() + limit
    while time.time() < end:
        got = cond()
        if got:
            return got
        time.sleep(0.05)
    return cond()


class Lane(Temp):
    """A temp home with the lane on, its key stored by a fake sops, the fake CLI copied into a
    PATH built from nothing, and a job dir outside the home."""

    def setUp(self):
        super().setUp()
        if backend() is None:
            self.skipTest("no wall is proved on this platform: the lane cannot run here")
        from apilane import key
        self.bin = os.path.join(self.t, "bin")
        self.records = os.path.join(self.bin, "fake-records")
        os.makedirs(self.records)
        shutil.copy(FAKE, os.path.join(self.bin, "claude"))
        for name, body in (("sops", SOPS), ("age-keygen", AGE_KEYGEN)):
            with open(os.path.join(self.bin, name), "w") as fh:
                fh.write(body)
        for name in ("claude", "sops", "age-keygen"):
            os.chmod(os.path.join(self.bin, name), 0o755)
        self.work = os.path.join(self.t, "work")
        os.makedirs(self.work)
        with open(os.path.join(self.work, "a.py"), "w") as fh:
            fh.write("x = 1\n")
        self.release = os.path.join(self.records, "release")
        self.addCleanup(self.let_go)
        self.write_config("api:\n  enabled: true\n  console_limit_usd: 50\n  max_day_usd: 3\n")
        self.key = made_up("lane-key")
        self.env_secrets = {n: made_up(n.lower()) for n in (
            "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN", "GH_TOKEN",
            "AWS_SECRET_ACCESS_KEY", "NPM_TOKEN", "OPENAI_API_KEY")}
        self.prompt_secret = made_up("prompt-secret")
        self.secrets = [self.key] + list(self.env_secrets.values()) + [self.prompt_secret]
        self.env = dict(self.env_secrets, PATH=self.bin + os.pathsep + "/usr/bin:/bin",
                        CLAUDE_CODE_SESSION_ID=SESSION,
                        SOPS_AGE_KEY_FILE=os.path.join(self.t, "age", "keys.txt"))
        with mock.patch.dict(os.environ, self.env):
            key.store(self.key, roots=self.roots)

    def let_go(self):
        with open(self.release, "w"):
            pass

    def job(self, fid, budget, shards, stub=None):
        path = os.path.join(self.t, fid + ".json")
        items = []
        for label, kind in shards:
            prompt = "fake-mode: hold\nfake-record: %s\nfake-release: %s\n" % (
                os.path.join(self.records, label + ".json"), self.release)
            if stub is not None:
                prompt += "fake-stub: %s\n" % stub
            items.append({"label": label, "type": kind,
                          "prompt": prompt + self.prompt_secret + "\nFind the reader of a.py.\n"})
        with open(path, "w") as fh:
            import json
            json.dump({"id": fid, "budget_usd": budget, "dirs": [self.work], "jobs": 3,
                       "shards": items}, fh)
        return path

    def log(self):
        import json
        try:
            with open(os.path.join(self.roots.state, "usage.jsonl")) as fh:
                return [json.loads(l) for l in fh if l.strip()]
        except OSError:
            return []

    def record(self, name):
        import json
        with open(os.path.join(self.records, name)) as fh:
            return json.load(fh)

    def starts(self):
        try:
            with open(os.path.join(self.records, "starts.log")) as fh:
                return fh.read().splitlines()
        except OSError:
            return []

    def held(self, labels):
        return all(os.path.exists(os.path.join(self.records, l + ".json")) for l in labels)

    def hook(self):
        import json
        from apilane import hook
        out = io.StringIO()
        hook.main("UserPromptSubmit", json.dumps({"session_id": SESSION}), roots=self.roots,
                  out=out)
        text = out.getvalue()
        return json.loads(text)["hookSpecificOutput"]["additionalContext"] if text else ""


class EndToEndTest(Lane):
    SHARDS = (("x1", "explore"), ("x2", "explore"), ("r1", "review"))

    def test_end_to_end(self):
        import threading
        from apilane import probe, report, stubapi
        log = self.log

        class LogStub(stubapi.Stub):
            seen = []

            def record(self, headers, body, raw):
                self.seen.append(log())
                return super().record(headers, body, raw)

        stub = LogStub(reads=[])
        stub.start()
        self.addCleanup(stub.stop)
        job = self.job("e2e-1", 2, self.SHARDS, stub=stub.url)
        out, err, box = io.StringIO(), io.StringIO(), {}

        def run():
            box["rc"] = cli.main(["fanout", job, "--yes"], roots=self.roots, stdout=out,
                                 stderr=err)

        with mock.patch.dict(os.environ, self.env):
            th = threading.Thread(target=run)
            th.start()
            try:
                held = wait_for(lambda: self.held(l for l, _ in self.SHARDS))
                want = "api lane: 3 agents running (2 explore, 1 review), $0.00 of $2.00 spent"
                mid = wait_for(lambda: report.line(SESSION, self.roots) == want and want
                               ) or report.line(SESSION, self.roots)
                rows = report.rows(self.roots)
            finally:
                self.let_go()
                th.join(120)
        self.assertTrue(held, err.getvalue())
        self.assertFalse(th.is_alive())
        self.assertEqual(box.get("rc"), 0, err.getvalue())
        # the probe passed on the fake; its argv has a shard's flags, differing in the
        # prompt and the ceiling (and the folder it is handed) alone
        rec = probe.read(self.roots)
        self.assertTrue(rec and rec["ok"], rec)
        mine = [n for n in os.listdir(self.records) if n[0].isdigit()]
        self.assertEqual(len(mine), 1, mine)
        p, s = self.record(mine[0]), self.record("x1.json")
        self.assertEqual(p["mode"], "stub")
        flags = lambda argv: [a for a in argv if a.startswith("--")]
        self.assertEqual(flags(p["argv"]), flags(s["argv"]))
        differ = [p["argv"][i - 1] for i in range(len(p["argv"])) if p["argv"][i] != s["argv"][i]]
        self.assertEqual(differ, ["--max-budget-usd", "--add-dir"])
        self.assertEqual(p["stdin"], probe.PROMPT)
        self.assertNotEqual(p["stdin"], s["stdin"])
        # the fake's first start found the reservation in the log
        self.assertTrue(stub.seen)
        first = [l for l in stub.seen[0] if l.get("fanout") == "e2e-1"]
        self.assertEqual([(l["kind"], l["budget_usd"]) for l in first], [("reserve", 2.0)])
        # mid-run
        self.assertEqual(mid, want)
        self.assertEqual(sorted(r["what"] for r in rows),
                         ["api explore: x1", "api explore: x2", "api review: r1"])
        self.assertEqual({(r["parent"], r["lane"], r["state"]) for r in rows},
                         {(SESSION, "api", "running")})
        # at the end: three shard lines and one settle
        kinds = [l["kind"] for l in self.log() if l.get("fanout") == "e2e-1"]
        self.assertEqual((kinds.count("reserve"), kinds.count("shard"), kinds.count("settle")),
                         (1, 3, 1), kinds)
        first, second = self.hook(), self.hook()
        self.assertEqual(first.count("fan-out e2e-1 ended: 3 ok, 0 failed"), 1, first)
        self.assertEqual(second, "")
        # eight planted secrets: in no file under the temp home, in no recorded argv
        self.assertEqual(len(set(self.secrets)), 8)
        for root, _dirs, files in os.walk(self.roots.home):
            for name in files:
                with open(os.path.join(root, name), "rb") as fh:
                    body = fh.read()
                for secret in self.secrets:
                    self.assertNotIn(secret.encode(), body, os.path.join(root, name))
        for name in os.listdir(self.records):
            if name.endswith(".json"):
                for a in self.record(name)["argv"]:
                    for secret in self.secrets:
                        self.assertNotIn(secret, a, name)


class KillTest(Lane):
    SHARDS = (("k1", "explore"), ("k2", "explore"), ("k3", "review"))

    def test_kill_9(self):
        import signal
        from apilane import ledger
        job = self.job("kill-1", 2, self.SHARDS)
        env = dict(self.env, HOME=self.roots.home)
        child = subprocess.Popen([sys.executable, "-I", "-c", CHILD, LIB] + list(self.roots)
                                 + [job], env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            reserved = wait_for(lambda: [l for l in self.log() if l.get("kind") == "reserve"]
                                and self.held(l for l, _ in self.SHARDS))
        finally:
            if child.poll() is None:
                os.kill(child.pid, signal.SIGKILL)
            child.wait(30)
        self.assertTrue(reserved, child.stderr.read().decode())
        child.stderr.close()
        self.assertEqual(child.returncode, -signal.SIGKILL)
        self.let_go()
        day = ledger.day(self.roots)
        self.assertEqual(day["sum_usd"], 2.0)
        self.assertEqual([u["fanout"] for u in day["unsettled"]], ["kill-1"])
        # a second fan-out that would pass the day's ceiling is refused and starts no fake
        before, lines = len(self.starts()), len(self.log())
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env):
            rc = cli.main(["fanout", self.job("kill-2", 2, (("m1", "explore"),)), "--yes"],
                          roots=self.roots, stdout=out, stderr=err)
        self.assertEqual(rc, 2, err.getvalue())
        self.assertIn("$2.00", err.getvalue())
        self.assertEqual(len(self.starts()), before)
        self.assertFalse(os.path.exists(os.path.join(self.records, "m1.json")))
        self.assertEqual(len(self.log()), lines)
        # the hook's next prompt: the stopped line with the budget, once
        first, second = self.hook(), self.hook()
        stopped = "fan-out kill-1 stopped without a close: its whole $2.00 counts against today"
        self.assertEqual(first.count(stopped), 1, first)
        self.assertEqual(second, "")


if __name__ == "__main__":
    unittest.main()
