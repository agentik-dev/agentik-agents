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
            os.close(slave)
            slave = None
            seen = b""
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                seen += chunk
        finally:
            if slave is not None:
                os.close(slave)
            os.close(master)
        self.assertEqual(got.stdout, self.want)
        self.assertEqual(seen.decode().replace("\r\n", "\n"), NOTE + "\n")


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


if __name__ == "__main__":
    unittest.main()
