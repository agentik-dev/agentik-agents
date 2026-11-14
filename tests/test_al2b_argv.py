#!/usr/bin/python3
"""Packet al2b-linux-wall: the bubblewrap wall's parts that hold where no namespace can be made.

Run as `python3 tests/test_al2b_argv.py [Class]`, on any platform. BwrapArgvTest reads the argv
`wall.wrap` returns with the backend forced to "bwrap", and never runs it; TrialTest gives the
backend's trial a stand-in bwrap; WalledShTest runs walled.sh under /bin/sh with stand-in paths;
LauncherTest runs the probe's launcher with the wall forced to pass the argv through, on al2's
fake CLI against the loopback stub. The real wall's tests are tests/test_al2b_linux.py's.

No test starts tests/fake-claude, the real claude, sops or bwrap: every fake is al2's or written
here, in a temp folder. Every key is made up; the stub binds loopback.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import test_al2_wall as al2  # noqa: E402  (its fakes, its builders, its temp home)

REPO = al2.REPO
LIB = os.path.join(REPO, "plugin", "lib")
APILANE = os.path.join(LIB, "apilane")
wall = al2.load("wall")
probe = al2.load("probe")

ARITY = {"--die-with-parent": 0, "--new-session": 0, "--unshare-pid": 0, "--unshare-net": 0,
         "--ro-bind": 2, "--bind": 2, "--tmpfs": 1, "--dev": 1, "--proc": 1}


def ops(cmd):
    """The bwrap argv as (option, args) pairs up to `--`, and the command after it."""
    out, i = [], 1
    while cmd[i] != "--":
        name = cmd[i]
        if name not in ARITY:
            raise AssertionError("an option this wall does not use: %r" % name)
        out.append((name, tuple(cmd[i + 1:i + 1 + ARITY[name]])))
        i += 1 + ARITY[name]
    return out, cmd[i + 1:]


def within(path, folder):
    return path == folder or path.startswith(folder.rstrip("/") + "/")


def mounts(pairs):
    """Each mount op's destination, in order: (kind, dest)."""
    kinds = {"--ro-bind": "ro", "--bind": "rw", "--tmpfs": "empty", "--dev": "dev", "--proc": "proc"}
    return [(kinds[n], a[-1]) for n, a in pairs if n in kinds]


class BwrapArgvTest(unittest.TestCase):

    def setUp(self):
        self.home = al2.Home(self)
        self.fake = self.home.write("tools/fake", "#!/bin/sh\nexec \"$@\"\n", 0o755)
        patches = [mock.patch.object(wall, "backend", lambda: "bwrap"),
                   mock.patch.object(wall, "_BWRAP_EMPTY_IF", ())]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def wrap(self, argv=("/bin/cat", "x"), read=(), write=(), net="all"):
        return wall.wrap([self.fake] + list(argv), read=list(read), write=list(write), net=net,
                         home=self.home.root)

    def test_the_wrapper_its_flags_and_the_command(self):
        cmd = self.wrap(["/bin/echo", "a b", "it's"])
        self.assertEqual(cmd[0], "/usr/bin/bwrap")
        pairs, rest = ops(cmd)
        self.assertEqual(rest, [self.fake, "/bin/echo", "a b", "it's"])
        names = [n for n, _ in pairs]
        for flag in ("--die-with-parent", "--new-session", "--unshare-pid"):
            self.assertEqual(names.count(flag), 1, flag)
        self.assertNotIn("--unshare-net", names)
        self.assertEqual(pairs[names.index("--ro-bind")], ("--ro-bind", ("/", "/")))
        m = mounts(pairs)
        self.assertEqual(m[:3], [("ro", "/"), ("dev", "/dev"), ("proc", "/proc")])

    def test_loopback_alone_unshares_the_network(self):
        pairs, _ = ops(self.wrap(net="loopback"))
        self.assertEqual([n for n, _ in pairs].count("--unshare-net"), 1)
        with self.assertRaises(ValueError):
            self.wrap(net="none")

    def test_the_home_and_temp_folders_are_emptied_before_any_bind_inside(self):
        job = self.home.mkdir("work", "job")
        run = os.path.realpath(tempfile.mkdtemp(prefix="al2b-run-"))
        self.addCleanup(shutil.rmtree, run, True)
        m = mounts(ops(self.wrap(read=[job], write=[run]))[0])
        empty = [d for k, d in m if k == "empty"]
        for folder in (self.home.root, os.path.realpath("/tmp"), os.path.realpath("/var/tmp")):
            self.assertIn(folder, empty)
            at = m.index(("empty", folder))
            later = [d for k, d in m[:at] if k in ("ro", "rw") and d != "/" and within(d, folder)]
            self.assertEqual(later, [], "bound inside %s before it was emptied" % folder)

    def test_read_write_and_the_cli_folder_are_bound_as_asked(self):
        job = self.home.mkdir("work", "job with 'quote")
        out = self.home.mkdir("out")
        link = self.home.path("job-link")
        os.symlink(job, link)
        pairs, _ = ops(self.wrap(read=[link], write=[out]))
        self.assertIn(("--ro-bind", (job, job)), pairs)
        self.assertIn(("--bind", (out, out)), pairs)
        tools = os.path.dirname(self.fake)
        self.assertIn(("--ro-bind", (tools, tools)), pairs)
        self.assertNotIn(("--bind", (job, job)), pairs)
        with self.assertRaises(ValueError):
            wall.wrap([link], read=[], write=[], net="all", home=self.home.root)

    def test_the_deeper_mount_comes_later(self):
        outer = self.home.mkdir("work")
        inner = self.home.mkdir("work", "out")
        hidden = self.home.mkdir("work", "cache")
        with mock.patch.object(wall, "_BWRAP_EMPTY_IF", (hidden, self.home.path("absent"))):
            m = mounts(ops(self.wrap(read=[outer], write=[inner]))[0])
        self.assertLess(m.index(("ro", outer)), m.index(("rw", inner)))
        self.assertLess(m.index(("ro", outer)), m.index(("empty", hidden)))
        self.assertNotIn(("empty", self.home.path("absent")), m)

    def test_the_secret_roots_are_covered_last(self):
        self.home.write(".config/sops/age/keys.txt", "made-up\n", 0o600)
        self.home.write(".config/gh", "made-up\n")
        self.home.mkdir(".ssh")
        self.home.mkdir(".local", "share", "keyrings")
        outside = os.path.realpath(tempfile.mkdtemp(prefix="al2b-out-"))
        self.addCleanup(shutil.rmtree, outside, True)
        real = os.path.join(outside, "real-secrets")
        os.makedirs(real)
        link = self.home.path(".config", "agentik", "agents", "secrets")
        os.makedirs(os.path.dirname(link))
        os.symlink(real, link)
        config, share = self.home.path(".config"), self.home.path(".local", "share")
        pairs, _ = ops(self.wrap(read=[config, share, outside]))
        binds = [i for i, (n, a) in enumerate(pairs)
                 if n in ("--ro-bind", "--bind") and a[0] == a[1] and a[1] != "/"]
        covers = pairs[max(binds) + 1:]
        sops = self.home.path(".config", "sops")
        ring = self.home.path(".local", "share", "keyrings")
        gh = self.home.path(".config", "gh")
        for cover in (("--tmpfs", (sops,)), ("--tmpfs", (ring,)), ("--tmpfs", (real,)),
                      ("--ro-bind", ("/dev/null", gh))):
            self.assertIn(cover, covers)
        for n, a in covers:
            self.assertTrue(n == "--tmpfs" or a[0] == "/dev/null", (n, a))
        dests = [d for _, d in mounts(pairs)]
        self.assertNotIn(self.home.path(".ssh"), dests)   # hidden by the empty home already
        self.assertNotIn(link, dests)                      # covered by its real path

    def test_no_backend_still_raises(self):
        with mock.patch.object(wall, "backend", lambda: None):
            with self.assertRaises(wall.WallError) as cm:
                self.wrap()
        self.assertEqual(str(cm.exception), "wall.platform")


STAND_IN = "#!/bin/sh\nprintf '%%s\\n' \"$@\" >> '%(log)s'\n%(body)s\n"


class TrialTest(unittest.TestCase):

    def setUp(self):
        self.t = os.path.realpath(tempfile.mkdtemp(prefix="al2b-trial-"))
        self.addCleanup(shutil.rmtree, self.t, True)
        self.log = os.path.join(self.t, "log")
        patches = [mock.patch.object(wall, "_TRIED", {}),
                   mock.patch.object(wall, "_TRIAL_TIMEOUT", 2)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def stand_in(self, body, mode=0o755):
        path = os.path.join(self.t, "bwrap-%d" % len(os.listdir(self.t)))
        with open(path, "w") as handle:
            handle.write(STAND_IN % {"log": self.log, "body": body})
        os.chmod(path, mode)
        return path

    def ready(self, path):
        with mock.patch.object(wall, "_BWRAP", path):
            return wall._bwrap_ready()

    def test_absent_not_executable_failing_hanging(self):
        self.assertFalse(self.ready(os.path.join(self.t, "nowhere")))
        self.assertFalse(self.ready(self.stand_in("exit 0", 0o644)))
        self.assertFalse(self.ready(self.t))
        self.assertFalse(self.ready(self.stand_in("exit 1")))
        self.assertFalse(self.ready(self.stand_in("exec sleep 30")))

    def test_passing_and_what_it_was_asked(self):
        path = self.stand_in("exit 0")
        self.assertTrue(self.ready(path))
        with open(self.log) as handle:
            asked = handle.read().splitlines()
        for flag in ("--unshare-net", "--unshare-pid", "--die-with-parent", "--new-session"):
            self.assertIn(flag, asked)
        at = asked.index("--ro-bind")
        self.assertEqual(asked[at:at + 3], ["--ro-bind", "/", "/"])
        self.assertEqual(asked[-2:], ["--", "/bin/true"])

    def test_the_trial_runs_once_and_backend_names_it_on_linux_alone(self):
        path = self.stand_in("exit 0")
        with mock.patch.object(wall, "_BWRAP", path):
            with mock.patch.object(wall.sys, "platform", "linux"):
                self.assertEqual(wall.backend(), "bwrap")
                self.assertEqual(wall.backend(), "bwrap")
                cmd = wall.wrap([os.path.realpath("/bin/sh")], read=[], write=[], net="all",
                                home=self.t)
            with mock.patch.object(wall.sys, "platform", "freebsd"):
                self.assertIsNone(wall.backend())
        self.assertEqual(cmd[0], path)
        with open(self.log) as handle:
            self.assertEqual(handle.read().splitlines().count("/bin/true"), 1)
        failing = self.stand_in("exit 1")
        with mock.patch.object(wall, "_BWRAP", failing), \
                mock.patch.object(wall.sys, "platform", "linux"):
            self.assertIsNone(wall.backend())


class WalledShTest(unittest.TestCase):

    def setUp(self):
        self.t = os.path.realpath(tempfile.mkdtemp(prefix="al2b-sh-"))
        self.addCleanup(shutil.rmtree, self.t, True)

    def sh(self, script, *args, env=None):
        return subprocess.run(["/bin/sh", "-c", script, "sh", APILANE] + list(args),
                              env=env or {"PATH": "/usr/bin:/bin"}, capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=10)

    def walled(self, sandbox_exec, bwrap):
        run = self.sh('. "$1/walled.sh"; apilane_sandbox_exec=$2; apilane_bwrap=$3; '
                      'apilane_walled', sandbox_exec, bwrap)
        return run.returncode == 0

    def file(self, name, mode):
        path = os.path.join(self.t, name)
        with open(path, "w") as handle:
            handle.write("#!/bin/sh\n")
        os.chmod(path, mode)
        return path

    def test_either_file_executable_is_true(self):
        none = os.path.join(self.t, "nowhere")
        exe, plain = self.file("exe", 0o755), self.file("plain", 0o644)
        self.assertFalse(self.walled(none, none))
        self.assertTrue(self.walled(none, exe))
        self.assertTrue(self.walled(exe, none))
        self.assertFalse(self.walled(none, plain))
        self.assertFalse(self.walled(plain, self.t))

    def test_the_fixed_paths_win_over_the_environment(self):
        run = self.sh('. "$1/walled.sh"; printf "%s\\n" "$apilane_sandbox_exec" "$apilane_bwrap"',
                      env={"PATH": "/usr/bin:/bin", "apilane_bwrap": self.t,
                           "apilane_sandbox_exec": self.t})
        self.assertEqual(run.stdout.splitlines(), ["/usr/bin/sandbox-exec", "/usr/bin/bwrap"])

    def test_prefilter_sources_it(self):
        exe = self.file("exe", 0o755)
        none = os.path.join(self.t, "nowhere")
        base = 'apilane_dir=$1; . "$1/prefilter.sh"; apilane_sandbox_exec=$2; apilane_bwrap=$3; '
        self.assertEqual(self.sh(base + "apilane_walled", none, exe).returncode, 0)
        self.assertEqual(self.sh(base + "apilane_walled", none, none).returncode, 1)
        self.assertEqual(self.sh("sh -n \"$1/walled.sh\"").returncode, 0)

    def test_it_agrees_with_the_backend_here(self):
        run = self.sh('apilane_dir=$1; . "$1/prefilter.sh"; apilane_walled')
        self.assertEqual(run.returncode == 0, wall.backend() is not None)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


STDIN_CLI = r'''#!%(py)s
import json, os, sys
with open(%(record)r, "w") as handle:
    json.dump({"argv": sys.argv, "env": dict(os.environ), "stdin": sys.stdin.read()}, handle)
sys.exit(7)
'''


class LauncherTest(unittest.TestCase):

    def setUp(self):
        self.home = al2.Home(self)
        self.roots = self.home.roots()

    def cli(self, mode="good", record=None):
        return self.home.write("tools/claude-" + mode, al2.FAKE_CLI % {
            "py": al2.FAKE_PY, "mode": mode, "record": record, "version": al2.VERSION}, 0o755)

    def launch(self, cli_argv, reads, out, env, stdin=""):
        cmd = [probe._launch_python(), "-I", "-c", probe._LAUNCH, LIB, out, ",".join(env)] \
            + reads + ["--"] + cli_argv
        return subprocess.run(cmd, env=env, input=stdin, capture_output=True, text=True,
                              timeout=60, cwd=self.home.root)

    def test_the_stub_first_the_cli_unchanged_and_its_exit(self):
        record = self.home.path("stdin.json")
        cli = self.home.write("tools/stdin-cli", STDIN_CLI % {"py": al2.FAKE_PY,
                                                              "record": record}, 0o755)
        out = self.home.path("requests.json")
        # LANG set, so the fake's own interpreter coerces no locale into its environment
        env = {"PATH": "/usr/bin:/bin", "HOME": self.home.root, "LANG": "en_US.UTF-8",
               "ANTHROPIC_API_KEY": "made-up-1",
               "ANTHROPIC_BASE_URL": "http://127.0.0.1:%d" % free_port()}
        run = self.launch([cli, "-p", "a b"], ["/x/one"], out, env, stdin="the prompt")
        self.assertEqual(run.returncode, 7, run.stderr)
        with open(record) as handle:
            seen = json.load(handle)
        self.assertEqual(seen["argv"], [cli, "-p", "a b"])
        self.assertEqual({k: v for k, v in seen["env"].items() if k not in al2.MACOS_ADDS}, env)
        self.assertEqual(seen["stdin"], "the prompt")
        with open(out) as handle:
            self.assertEqual(json.load(handle), [])

        good = self.cli("good")
        job = self.home.mkdir("job")
        notes = self.home.write("job/notes.txt", "launch-notes-text\n")
        run = self.launch([good, "--add-dir", job], [notes], out, env)
        self.assertEqual(run.returncode, 0, run.stderr)
        with open(out) as handle:
            reqs = json.load(handle)
        self.assertEqual([r["turn"] for r in reqs], [0, 1])
        self.assertIn("launch-notes-text", reqs[1]["body"])
        self.assertEqual(reqs[0]["credentials"]["x-api-key"], "made-up-1")

    def test_a_cli_that_cannot_start_is_127(self):
        out = self.home.path("requests.json")
        env = {"PATH": "/usr/bin:/bin", "ANTHROPIC_BASE_URL": "http://127.0.0.1:%d" % free_port()}
        run = self.launch([self.home.path("nowhere")], [], out, env)
        self.assertEqual(run.returncode, 127, run.stderr)
        with open(out) as handle:
            self.assertEqual(json.load(handle), [])

    def test_the_probe_wraps_the_launcher_and_runs_the_builders_unchanged(self):
        rec_dir = self.home.mkdir("rec")
        claude = self.cli("good", record=rec_dir)
        calls = []

        def b_argv(shard, **kw):
            out = al2.build_argv(shard, **kw)
            calls.append(("argv", kw, out))
            return out

        def b_env(**kw):
            out = al2.build_env(**kw)
            calls.append(("env", kw, out))
            return out

        def passing(argv, **kw):
            calls.append(("wrap", kw, list(argv)))
            return list(argv)

        rec = probe.run(claude=claude, roots=self.roots, build_argv=b_argv, build_env=b_env,
                        wrap=passing, inside=True)
        self.assertEqual({c["name"]: c["ok"] for c in rec["checks"]},
                         dict.fromkeys(al2.CHECKS, True), rec)
        (seen,) = [json.load(open(os.path.join(rec_dir, n))) for n in os.listdir(rec_dir)]
        got = {kind: (kw, out) for kind, kw, out in calls}
        argv_kw, argv_out = got["argv"]
        env_kw, env_out = got["env"]
        wrap_kw, wrapped = got["wrap"]
        self.assertEqual(seen["argv"], argv_out)
        self.assertEqual({k: v for k, v in seen["env"].items() if k not in al2.MACOS_ADDS}, env_out)
        job, run_dir = argv_kw["dirs"][0], argv_kw["run_dir"]
        self.assertEqual(wrap_kw["net"], "loopback")
        self.assertEqual(wrap_kw["home"], self.roots.home)
        self.assertEqual(wrap_kw["read"][:3], [job, os.path.realpath(LIB),
                                               os.path.dirname(os.path.realpath(claude))])
        self.assertEqual(wrap_kw["write"][0], run_dir)
        self.assertEqual(len(wrap_kw["write"]), 2)
        stub_dir = wrap_kw["write"][1]
        at = wrapped.index("--")
        self.assertEqual(wrapped[:5], [probe._launch_python(), "-I", "-c", probe._LAUNCH,
                                       os.path.realpath(LIB)])
        self.assertTrue(within(wrapped[5], stub_dir), wrapped[5])
        self.assertEqual(wrapped[6], ",".join(sorted(env_out)))
        self.assertEqual(len(wrapped[7:at]), 3)
        self.assertEqual(wrapped[at + 1:], argv_out)
        self.assertTrue(env_kw["base_url"].startswith("http://127.0.0.1:"))
        self.assertFalse(env_kw["key"].startswith("sk-"))
        self.assertEqual(os.listdir(self.roots.state), ["probe.json"])

    def test_the_stub_goes_inside_only_for_the_real_bwrap_wall(self):
        def stand_in(argv, **kw):
            return list(argv)
        with mock.patch.object(wall, "backend", lambda: "bwrap"):
            self.assertTrue(probe._stub_inside(wall.wrap))
            self.assertFalse(probe._stub_inside(stand_in))
        with mock.patch.object(wall, "backend", lambda: "sandbox-exec"):
            self.assertFalse(probe._stub_inside(wall.wrap))
        with mock.patch.object(wall, "backend", lambda: None):
            self.assertFalse(probe._stub_inside(wall.wrap))


if __name__ == "__main__":
    unittest.main(verbosity=2)
