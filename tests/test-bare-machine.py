#!/usr/bin/env python3
"""Packet a-s18: the plugin on a bare machine (hq design/04 section 7's test, item 6).

`git archive HEAD plugin`, the whole plugin, goes into a temp home as a marketplace's cache would
hold it, and runs with the env exactly HOME, PATH=/usr/bin:/bin, CLAUDE_PLUGIN_ROOT and
CLAUDE_PLUGIN_DATA, from a cwd holding decoys: no clone path, no venv, no launcher. The verbs go
through plugin/bin/agentik-agents; then install-cli writes a launcher, the door and the four old
names' links under the temp home, never the real one, and `make install` does the same from a
committed copy of HEAD. `route --check` and `doctor` probe the router, the upstream and the local
backend, so they run under a sandbox that denies the network: nothing reaches a model server.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OLD = ("agentroute", "claude-agents", "claude-local", "localrig")
SANDBOX = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
DECOYS = ("agentik_install.py", "agents_install.py", "json.py", "argparse.py")


def git(*argv, cwd=REPO, **kw):
    return subprocess.run(["git", *argv], cwd=cwd, check=True, capture_output=True, **kw).stdout


def sandbox_applies():
    try:
        return subprocess.run(SANDBOX + ["/usr/bin/true"], capture_output=True,
                              timeout=30).returncode == 0
    except OSError:
        return False


class BareMachine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.t = os.path.realpath(tempfile.mkdtemp(prefix="agents-bare-"))
        cls.addClassCleanup(shutil.rmtree, cls.t, True)
        cls.version = json.loads(git("show", "HEAD:plugin/.claude-plugin/plugin.json"))["version"]
        cls.plugin = os.path.join(cls.t, ".claude", "plugins", "cache", "agentik", "agents",
                                  cls.version)
        os.makedirs(cls.plugin)
        subprocess.run(["tar", "-x", "--strip-components", "1", "-C", cls.plugin],
                       input=git("archive", "HEAD", "plugin"), check=True)
        cls.data = os.path.join(cls.t, ".claude", "plugins", "data", "agents-agentik")
        os.makedirs(cls.data)
        cls.cwd = os.path.join(cls.t, "work")
        os.makedirs(cls.cwd)
        # the decoys: -I and a script's own folder keep the cwd off sys.path, so none may load
        for name in DECOYS:
            with open(os.path.join(cls.cwd, name), "w", encoding="utf-8") as handle:
                handle.write("raise SystemExit('decoy %s imported')\n" % name)
        cls.sandboxed = sandbox_applies()
        cls.sessions = os.path.join(cls.t, ".local", "state", "agentik-session", "sessions")

    @classmethod
    def env(cls, home=None):
        return {"HOME": home or cls.t, "PATH": "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": cls.plugin,
                "CLAUDE_PLUGIN_DATA": cls.data}

    def run_tool(self, *argv, exe=None, home=None, net=False):
        cmd = [exe or os.path.join(self.plugin, "bin", "agentik-agents"), *argv]
        if net:
            if not self.sandboxed:
                self.skipTest("sandbox-exec cannot deny the network here; the probe stays unrun")
            cmd = SANDBOX + cmd
        run = subprocess.run(cmd, cwd=self.cwd, env=self.env(home), capture_output=True,
                             text=True, timeout=120)
        self.assertNotIn("decoy", run.stdout + run.stderr)
        return run

    def ok(self, run):
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return run

    def test_1_status(self):
        # with no session plugin's state, status says which folder it could not read, exit 1
        run = self.run_tool("status")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("cannot read the sessions dir %s" % self.sessions, run.stderr)
        # with the folder the session plugin writes, empty, it reads once and exits 0
        os.makedirs(self.sessions, exist_ok=True)
        self.ok(self.run_tool("status"))
        self.ok(self.run_tool("status", "--json"))

    def test_2_route_check(self):
        run = self.run_tool("route", "--check", net=True)
        # every probe is refused, so FAIL rows and exit 1: the check ran, and gated
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        for row in ("router", "upstream", "backend default", "local policy"):
            self.assertRegex(run.stdout, r"(?m)^  (ok|warn|FAIL) +%s " % re.escape(row))
        self.assertRegex(run.stdout, r"(?m)^  \d+ ok  \d+ warn  \d+ FAIL")

    def test_3_doctor(self):
        out = self.ok(self.run_tool("doctor", net=True)).stdout
        for name in OLD + ("agentik-agents", "agentik"):
            self.assertRegex(out, r"(?m)^  %s +NOT ON PATH$" % re.escape(name))
        self.assertRegex(out, r"(?m)^  claude +NOT ON PATH \(the local lane runs it\)$")
        self.assertIn("/agents:install-cli", out)
        self.assertRegex(out, r"(?m)^  python3 +/usr/bin/python3 3\.")
        self.assertIn("  Local lane:", out)
        self.assertRegex(out, r"(?m)^      FAIL  router ")
        self.assertRegex(out, r"(?m)^      FAIL  backend default ")

    def test_4_version(self):
        self.assertEqual(self.ok(self.run_tool("--version")).stdout,
                         "agentik-agents %s\n" % self.version)

    def installed(self, home):
        bindir = os.path.join(home, ".local", "bin")
        share = os.path.join(home, ".local", "share", "agentik-agents")
        return bindir, share

    def test_5_install_cli_under_the_temp_home(self):
        os.makedirs(self.sessions, exist_ok=True)       # for status through the launcher, below
        self.ok(self.run_tool("install-cli"))
        bindir, share = self.installed(self.t)
        launcher = os.path.join(bindir, "agentik-agents")
        with open(launcher, encoding="utf-8") as handle:
            self.assertIn("\nVERSION=%s\n" % self.version, handle.read())
        self.assertTrue(os.access(os.path.join(bindir, "agentik"), os.X_OK))
        trees = [n for n in os.listdir(share) if not n.startswith(".")]
        self.assertEqual(len(trees), 1, trees)
        tree = os.path.join(share, trees[0])
        for name in OLD:
            link = os.path.join(bindir, name)
            self.assertTrue(os.path.islink(link), link)
            self.assertEqual(os.readlink(link), os.path.join(tree, name))
            self.assertTrue(os.access(link, os.X_OK), link)
        self.assertEqual(self.ok(self.run_tool("--version", exe=launcher)).stdout,
                         "agentik-agents %s\n" % self.version)
        helped = self.ok(self.run_tool("--help", exe=os.path.join(bindir, "agentroute")))
        self.assertTrue(helped.stdout.startswith("usage: agentroute"), helped.stdout[:200])
        self.ok(self.run_tool("status", exe=launcher))
        # no clone path anywhere the install wrote
        for top, _dirs, files in os.walk(os.path.join(self.t, ".local")):
            for name in files:
                path = os.path.join(top, name)
                if not os.path.islink(path):
                    with open(path, "rb") as handle:
                        self.assertNotIn(REPO.encode(), handle.read(), path)

    def test_6_install_cli_leaves_a_regular_file(self):
        home = os.path.join(self.t, "home-with-files")
        bindir, share = self.installed(home)
        os.makedirs(bindir)
        with open(os.path.join(bindir, "localrig"), "w", encoding="utf-8") as handle:
            handle.write("mine\n")
        os.symlink("/nowhere/agentroute", os.path.join(bindir, "agentroute"))
        run = self.run_tool("install-cli", home=home)
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("localrig is not a link, left as it is", run.stderr)
        with open(os.path.join(bindir, "localrig"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "mine\n")
        self.assertTrue(os.readlink(os.path.join(bindir, "agentroute")).startswith(share + os.sep))
        launcher = os.path.join(bindir, "agentik-agents")
        self.assertTrue(os.path.isfile(launcher))
        # a1 F1: the refused name's tool is still executable in the tree, so its verb runs
        rig = self.run_tool("rig", "--version", exe=launcher, home=home)
        self.assertEqual(rig.returncode, 0, rig.stdout + rig.stderr)
        self.assertIn("localrig (agentik-agents)", rig.stdout)
        trees = [n for n in os.listdir(share) if not n.startswith(".")]
        for name in OLD:
            self.assertTrue(os.access(os.path.join(share, trees[0], name), os.X_OK), name)

    @classmethod
    def source(cls):
        """HEAD as a clean checkout of its own, made once, for `make install`'s dirty guard."""
        src = os.path.join(cls.t, "src")
        if not os.path.isdir(src):
            os.makedirs(src)
            subprocess.run(["tar", "-x", "-C", src], input=git("archive", "HEAD"), check=True)
            genv = {"HOME": cls.t, "PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1"}
            for argv in (["init", "-q"], ["add", "-A"],
                         ["-c", "user.name=t", "-c", "user.email=t", "commit", "-q",
                          "-m", "HEAD"]):
                git(*argv, cwd=src, env=genv)
        return src

    @staticmethod
    def make_env(home):
        """HOME and PATH only, never the caller's env: an exported PREFIX or XDG_* stays out."""
        return {"HOME": home, "PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1"}

    def make(self, home, *argv):
        return subprocess.run(["make", "-C", self.source(), "--no-print-directory", *argv],
                              env=self.make_env(home), capture_output=True, text=True,
                              timeout=120)

    def test_7_make_install_and_uninstall(self):
        src = self.source()
        home = os.path.join(self.t, "home-by-make")
        os.makedirs(home)
        make = lambda goal: self.make(home, goal)  # noqa: E731  (a1 F3: never the caller's env)
        bindir, share = self.installed(home)
        self.ok(make("install"))
        for name in OLD:
            self.assertTrue(os.readlink(os.path.join(bindir, name)).startswith(share + os.sep))
        with open(os.path.join(src, "dirt"), "w", encoding="utf-8") as handle:
            handle.write("x\n")
        refused = make("install")
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
        self.assertIn("refused, the tree is dirty", refused.stderr)
        os.unlink(os.path.join(src, "dirt"))
        mine = os.path.join(bindir, "claude-local")
        os.unlink(mine)
        os.symlink("/elsewhere/claude-local", mine)      # not install-cli's: uninstall skips it
        self.ok(make("uninstall"))
        self.assertFalse(os.path.lexists(os.path.join(bindir, "agentik-agents")))
        for name in ("agentroute", "claude-agents", "localrig"):
            self.assertFalse(os.path.lexists(os.path.join(bindir, name)), name)
        self.assertEqual(os.readlink(mine), "/elsewhere/claude-local")
        self.assertFalse(os.path.exists(share))
        self.assertTrue(os.path.isfile(os.path.join(bindir, "agentik")))

    def test_8_a_trailing_slash_prefix_round_trip_leaves_nothing(self):
        home = os.path.join(self.t, "home-slash")
        os.makedirs(home)
        prefix = os.path.join(home, "p") + "/"
        self.ok(self.make(home, "install", "PREFIX=" + prefix))
        run = self.ok(self.make(home, "uninstall", "PREFIX=" + prefix))
        self.assertNotIn("skipped", run.stdout + run.stderr)
        self.assertEqual(os.listdir(os.path.join(home, "p", "bin")), ["agentik"])  # the door stays
        self.assertFalse(os.path.lexists(os.path.join(home, "p", "share", "agentik-agents")))
        given = self.make(home, "install", "PREFIX=" + prefix, "BINDIR=" + os.path.join(home, "b"))
        self.assertEqual(given.returncode, 2, given.stdout + given.stderr)
        self.assertIn("BINDIR is not honoured", given.stderr)
        self.assertFalse(os.path.lexists(os.path.join(home, "b")))

    def test_9_a_launcher_not_ours_keeps_the_share(self):
        home = os.path.join(self.t, "home-not-ours")
        os.makedirs(home)
        bindir, share = self.installed(home)
        self.ok(self.make(home, "install"))
        launcher = os.path.join(bindir, "agentik-agents")
        os.unlink(launcher)
        with open(launcher, "w", encoding="utf-8") as handle:
            handle.write("mine\n")
        run = self.make(home, "uninstall")
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("%s stays" % share, run.stderr)
        self.assertTrue(os.path.isdir(share))
        with open(launcher, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "mine\n")

    def test_10_a_home_with_a_space(self):
        # a2 F1: make's $(abspath) split "John Smith" in two; a read-only parent makes the
        # split an error, and nothing may appear beside the home
        parent = os.path.join(self.t, "ro")
        home = os.path.join(parent, "John Smith")
        os.makedirs(home)
        bindir, share = self.installed(home)
        os.chmod(parent, 0o555)
        try:
            self.ok(self.make(home, "install"))
            self.assertEqual(os.listdir(parent), ["John Smith"])
            launcher = os.path.join(bindir, "agentik-agents")
            self.assertEqual(self.ok(self.run_tool("--version", exe=launcher, home=home)).stdout,
                             "agentik-agents %s\n" % self.version)
            run = self.ok(self.make(home, "uninstall"))
            self.assertNotIn("skipped", run.stdout + run.stderr)
        finally:
            os.chmod(parent, 0o755)
        self.assertEqual(os.listdir(bindir), ["agentik"])                  # the door stays
        self.assertFalse(os.path.lexists(share))

    def test_11_uninstall_refuses_bindir(self):
        # a2 F2: uninstall ignored BINDIR and removed the default PREFIX's install
        home = os.path.join(self.t, "home-bindir")
        os.makedirs(home)
        bindir, share = self.installed(home)
        self.ok(self.make(home, "install"))
        before = sorted(os.listdir(bindir))
        run = self.make(home, "uninstall", "BINDIR=" + os.path.join(home, "else"))
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("uninstall: refused, BINDIR is not honoured", run.stderr)
        self.assertNotIn("removed", run.stdout + run.stderr)
        self.assertEqual(sorted(os.listdir(bindir)), before)
        self.assertTrue(os.path.isdir(share))

    def test_12_a_share_through_a_symlink_stays(self):
        # a2 F3: with C/share a link to ../A/share, uninstall PREFIX=C removed A's live share
        home = os.path.join(self.t, "home-linked")
        a, c = os.path.join(home, "A"), os.path.join(home, "C")
        os.makedirs(a)
        os.makedirs(c)
        os.symlink(os.path.join("..", "A", "share"), os.path.join(c, "share"))
        self.ok(self.make(home, "install", "PREFIX=" + a))
        run = self.make(home, "uninstall", "PREFIX=" + c)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("stays: it resolves to %s" % os.path.join(a, "share", "agentik-agents"),
                      run.stderr)
        self.assertTrue(os.path.isdir(os.path.join(a, "share", "agentik-agents")))
        launcher = os.path.join(a, "bin", "agentik-agents")
        self.assertEqual(self.ok(self.run_tool("--version", exe=launcher, home=home)).stdout,
                         "agentik-agents %s\n" % self.version)


if __name__ == "__main__":
    unittest.main(verbosity=2)
