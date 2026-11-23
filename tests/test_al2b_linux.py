#!/usr/bin/python3
"""Packet al2b-linux-wall: the bubblewrap wall, run for real, on Linux.

Run as `python3 tests/test_al2b_linux.py [Class]`. Each test starts the real /usr/bin/bwrap around
a fake in a temp home; where `wall.backend()` is not "bwrap" (macOS, or a Linux machine where the
trial namespace fails) every class skips with one printed reason and the suite ends OK. The
argv, the trial, walled.sh and the probe's launcher are held where no namespace can be made, by
tests/test_al2b_argv.py.

No test starts tests/fake-claude, the real claude or sops: every fake is al2's or written here,
in a temp folder, on a PATH built from nothing. Every key is made up. Nothing leaves the machine:
NetTest's one outside connect runs only inside the wall, after the wall is seen to hold.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import test_al2_wall as al2  # noqa: E402  (its fakes, its builders, its temp home)

REPO = al2.REPO
LIB = os.path.join(REPO, "plugin", "lib")
PREFILTER = os.path.join(LIB, "apilane", "prefilter.sh")
wall = al2.load("wall")
probe = al2.load("probe")


def reason():
    """Why this file's classes skip here, or None where the bubblewrap wall is proved."""
    got = wall.backend()
    if got != "bwrap":
        return "the bubblewrap wall is not proved on %s (backend %r): the Linux half stays unrun" % (
            sys.platform, got)
    return None


class BwrapCase(unittest.TestCase):
    """A test that starts the real bubblewrap wall; the class skips, once, where there is none."""

    @classmethod
    def setUpClass(cls):
        why = reason()
        if why:
            raise unittest.SkipTest(why)

    def setUp(self):
        self.home = al2.Home(self)
        self.fake = self.home.write("tools/fake", "#!/bin/sh\nexec \"$@\"\n", 0o755)

    def walled(self, argv, read=(), write=(), net="all", env=None):
        cmd = wall.wrap([self.fake] + list(argv), read=list(read), write=list(write), net=net,
                        home=self.home.root)
        base = {"PATH": "/usr/bin:/bin", "HOME": self.home.root}
        base.update(env or {})
        return subprocess.run(cmd, capture_output=True, text=True, env=base, cwd="/", timeout=60)

    def refused(self, run, text):
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertNotIn(text, run.stdout + run.stderr)

    def holds(self):
        """The wall holds before anything else is tried: a canary under the home is unreadable."""
        canary = self.home.write("private/hold.txt", "hold-canary-text\n")
        self.refused(self.walled(["/bin/cat", canary], net="loopback"), "hold-canary-text")


class WallReadTest(BwrapCase):

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

    def test_tmp_outside_the_job_dir(self):
        folder = os.path.realpath(tempfile.mkdtemp(dir="/tmp", prefix="al2b-tmp-"))
        self.addCleanup(shutil.rmtree, folder, True)
        canary = os.path.join(folder, "canary.txt")
        with open(canary, "w", encoding="utf-8") as handle:
            handle.write("canary-tmp-text\n")
        self.refused(self.walled(["/bin/cat", canary], read=[self.job]), "canary-tmp-text")


class WallWriteTest(BwrapCase):

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

    def test_a_write_in_an_emptied_folder_never_reaches_the_disk(self):
        target = self.home.path("dropped.txt")
        run = self.walled(["/bin/sh", "-c", "echo w > '%s'" % target])
        self.assertFalse(os.path.exists(target), run.stdout + run.stderr)


class WallSecretTest(BwrapCase):

    def test_a_secret_root_inside_a_read_folder_stays_hidden(self):
        keys = self.home.write(".config/sops/age/keys.txt", "made-up-identity-text\n", 0o600)
        plain = self.home.write(".config/plain.txt", "plain-config-text\n")
        config = self.home.path(".config")
        self.refused(self.walled(["/bin/cat", keys], read=[config]), "made-up-identity-text")
        self.refused(self.walled(["/bin/ls", "-A", os.path.dirname(keys)], read=[config]),
                     "keys.txt")
        run = self.walled(["/bin/cat", plain], read=[config])
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("plain-config-text", run.stdout)

    def test_the_keyring_and_a_secret_file_inside_a_read_folder(self):
        ring = self.home.write(".local/share/keyrings/login.keyring", "made-up-ring-text\n")
        gh = self.home.write(".config/gh", "made-up-gh-text\n")
        self.refused(self.walled(["/bin/cat", ring], read=[self.home.path(".local", "share")]),
                     "made-up-ring-text")
        run = self.walled(["/bin/cat", gh], read=[self.home.path(".config")])
        self.assertNotIn("made-up-gh-text", run.stdout + run.stderr)

    def test_a_secret_root_linked_out_of_the_home(self):
        outside = os.path.realpath(tempfile.mkdtemp(prefix="al2b-out-"))
        self.addCleanup(shutil.rmtree, outside, True)
        real = os.path.join(outside, "real-secrets")
        os.makedirs(real)
        with open(os.path.join(real, "key.txt"), "w", encoding="utf-8") as handle:
            handle.write("made-up-linked-text\n")
        link = self.home.path(".config", "agentik", "agents", "secrets")
        os.makedirs(os.path.dirname(link))
        os.symlink(real, link)
        run = self.walled(["/bin/cat", os.path.join(link, "key.txt")],
                          read=[self.home.path(".config"), outside])
        self.refused(run, "made-up-linked-text")
        run = self.walled(["/bin/cat", os.path.join(real, "key.txt")], read=[outside])
        self.refused(run, "made-up-linked-text")


class DoubtTest(BwrapCase):
    """What the argv alone cannot settle: /proc, the runtime folder, and the child's end."""

    def test_proc_shows_no_process_outside_the_wall(self):
        marker = "AL2B_MARK=made-up-proc-text"
        outside = subprocess.Popen(["/bin/sleep", "30"], env={"PATH": "/usr/bin:/bin",
                                                               "AL2B_MARK": marker.split("=")[1]})
        self.addCleanup(outside.wait)
        self.addCleanup(outside.kill)
        run = self.walled(["/bin/cat", "/proc/%d/environ" % outside.pid])
        self.refused(run, "made-up-proc-text")
        run = self.walled(["/bin/ls", "/proc/%d" % outside.pid])
        self.assertNotEqual(run.returncode, 0, run.stdout)

    def test_the_runtime_folder_is_empty(self):
        # R2 of the second round: absent is stricter than empty, and holds too (the first run
        # saw `/run/user` covered, so the uid's folder absent); a name in it still fails
        uid = str(os.getuid())
        folder = "/run/user/" + uid
        if not os.path.isdir(folder):
            self.skipTest("no %s on this machine" % folder)
        listing = self.walled(["/bin/ls", "-A", "/run/user"])
        self.assertNotIn(uid, listing.stdout.split(), listing.stdout)
        run = self.walled(["/bin/ls", "-A", folder])
        self.assertEqual(run.stdout, "", "a name of %s shows inside the wall" % folder)
        if run.returncode != 0:
            self.assertIn("No such file", run.stderr, run.stderr)

    def test_killing_the_wall_ends_its_child(self):
        out = self.home.mkdir("out")
        tick = os.path.join(out, "tick")
        cmd = wall.wrap([self.fake, "/bin/sh", "-c",
                         "while :; do date +%s%N > \"$1/tick\"; sleep 0.1; done", "sh", out],
                        read=[], write=[out], net="all", home=self.home.root)
        child = subprocess.Popen(cmd, env={"PATH": "/usr/bin:/bin", "HOME": self.home.root},
                                 cwd="/", start_new_session=True)
        deadline = time.time() + 20
        while not os.path.exists(tick) and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(os.path.exists(tick), "the walled child never wrote")
        os.killpg(child.pid, signal.SIGKILL)
        child.wait(10)
        time.sleep(1.0)
        before = os.stat(tick).st_mtime_ns
        time.sleep(1.5)
        self.assertEqual(os.stat(tick).st_mtime_ns, before, "the walled child outlived its wall")


NET_CHILD = r'''
import socket, sys, threading, time
port_out = int(sys.argv[1])
server = socket.socket(); server.bind(("127.0.0.1", 0)); server.listen(1)
threading.Thread(target=lambda: server.accept()[0].close(), daemon=True).start()
socket.create_connection(server.getsockname(), timeout=5).close()
print("loopback ok")
try:
    socket.create_connection(("127.0.0.1", port_out), timeout=3).close()
    print("outside stub reached")
except OSError:
    print("outside stub unreached")
t = time.time()
try:
    socket.create_connection(("192.0.2.1", 9), timeout=3)
    print("outside connected")
except socket.timeout:
    print("outside timeout")
except OSError as e:
    print("outside refused %.2f" % (time.time() - t))
'''


SOCK_CHILD = r'''
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(3)
try:
    s.connect(sys.argv[1])
    print("reached")
except OSError as e:
    print("refused %s" % type(e).__name__)
'''


class Listener:
    """A path socket outside the wall that answers every connect; stopped at the test's end."""

    def __init__(self, test, path):
        import socket
        import threading
        self.path = path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        test.addCleanup(self.stop)
        self.sock.listen(4)
        self.sock.settimeout(0.2)
        self.done = False
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while not self.done:
            try:
                conn, _ = self.sock.accept()
                conn.close()
            except OSError:
                continue

    def stop(self):
        self.done = True
        self.sock.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass


class RunSocketTest(BwrapCase):
    """L1: a socket file under `/run`, which the first wall left readable, is not reached."""

    def test_a_socket_under_run_is_refused_and_one_in_a_write_folder_is_reached(self):
        self.holds()
        lock = "/run/lock"   # world-writable on the target, and not emptied by the first wall
        if not (os.path.isdir(lock) and os.access(lock, os.W_OK)):
            self.skipTest("no writable %s on this machine" % lock)
        outside = Listener(self, os.path.join(lock, "al2b-%d.sock" % os.getpid()))
        out = self.home.mkdir("out")
        inside = Listener(self, os.path.join(out, "al2b.sock"))
        for net in ("loopback", "all"):
            run = self.walled([al2.FAKE_PY, "-I", "-c", SOCK_CHILD, outside.path], net=net)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(run.stdout.startswith("refused"), (net, run.stdout))
        run = self.walled([al2.FAKE_PY, "-I", "-c", SOCK_CHILD, inside.path], write=[out],
                          net="loopback")
        self.assertEqual(run.stdout.strip(), "reached", run.stderr)


class ResolverTest(BwrapCase):
    """L1: `/run` is emptied whole; under net="all" alone the resolver's folder is back."""

    def test_the_resolver_under_all_alone(self):
        folder = wall._bwrap_resolver()
        if folder is None:
            self.skipTest("/etc/resolv.conf does not point into /run on this machine")
        name = os.path.basename(os.path.realpath("/etc/resolv.conf"))
        run = self.walled(["/bin/cat", "/etc/resolv.conf"], net="all")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("nameserver", run.stdout)
        run = self.walled(["/bin/ls", "-A", folder], net="loopback")
        self.assertNotIn(name, run.stdout.split(), run.stdout)
        run = self.walled(["/bin/ls", "-A", "/run"], net="all")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.split(), [folder.split("/")[2]], run.stdout)


class RootTest(BwrapCase):
    """L2: every real folder directly under `/` off the system list is empty inside the wall."""

    def test_the_roots_own_folders_are_empty_and_the_system_stays(self):
        self.assertEqual(wall._bwrap_top(["al2b-made-up-data", "usr", "opt", "etc"]),
                         ["/al2b-made-up-data"])
        top = wall._bwrap_top()
        self.assertIn("/tmp", top)
        bound = os.path.realpath(self.home.root)   # the fake's folder is in it, bound back
        for folder in top:
            with self.subTest(folder=folder):
                # empty, but for the first step on the way to the one folder bound inside it
                way = bound[len(folder):].strip("/").split("/")[:1] if wall._within(bound, folder) else []
                run = self.walled(["/bin/ls", "-A", folder], net="loopback")
                self.assertEqual((run.returncode, run.stdout.split()), (0, way), run.stderr)
        run = self.walled(["/bin/ls", "/usr/bin"])
        self.assertIn("python3", run.stdout.split(), run.stderr)


class NamespaceTest(BwrapCase):
    """L3: the command's IPC, host-name and cgroup namespaces are not the host's."""

    def test_ipc_uts_and_cgroup_are_its_own(self):
        for ns in ("ipc", "uts", "cgroup"):
            with self.subTest(ns=ns):
                here = os.readlink("/proc/self/ns/" + ns)
                run = self.walled(["/usr/bin/readlink", "/proc/self/ns/" + ns])
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertNotEqual(run.stdout.strip(), here)


class NetTest(BwrapCase):

    def test_loopback_is_the_walls_own_and_the_outside_is_refused(self):
        self.holds()
        stub = al2.load("stubapi").Stub(reads=[])
        stub.start()
        self.addCleanup(stub.stop)
        run = self.walled([al2.FAKE_PY, "-I", "-c", NET_CHILD, str(stub.address[1])],
                          net="loopback")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("loopback ok", run.stdout)
        self.assertIn("outside stub unreached", run.stdout)
        self.assertIn("outside refused", run.stdout, run.stdout)
        self.assertLess(float(run.stdout.split("outside refused")[1].split()[0]), 1.0)


class ProbeCase(BwrapCase):

    def setUp(self):
        super().setUp()
        self.roots = self.home.roots()

    def cli(self, mode="good", record=None):
        return self.home.write("tools/claude-" + mode, al2.FAKE_CLI % {
            "py": al2.FAKE_PY, "mode": mode, "record": record, "version": al2.VERSION}, 0o755)

    def run_probe(self, mode="good", **kw):
        return probe.run(claude=self.cli(mode), roots=self.roots, build_argv=al2.build_argv,
                         build_env=al2.build_env, **kw)

    def checks(self, rec):
        return {c["name"]: c["ok"] for c in rec["checks"]}


class ProbeTest(ProbeCase):

    def test_all_five_pass_with_the_stub_inside(self):
        rec = self.run_probe("good")
        self.assertEqual(self.checks(rec), dict.fromkeys(al2.CHECKS, True), rec)
        self.assertIs(rec["ok"], True)
        with open(os.path.join(self.roots.state, "probe.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), rec)
        self.assertEqual(os.listdir(self.roots.state), ["probe.json"])

    def test_a_bearer_token_fails_key(self):
        rec = self.run_probe("bearer")
        self.assertIs(self.checks(rec)["key"], False)
        self.assertIs(rec["ok"], False)

    def test_bash_offered_fails_tools(self):
        rec = self.run_probe("bash")
        self.assertIs(self.checks(rec)["tools"], False)
        self.assertIs(rec["ok"], False)

    def test_a_wrap_that_walls_nothing_fails_walled(self):
        rec = self.run_probe("outside", wrap=al2.open_wrap, inside=True)
        self.assertIs(self.checks(rec)["walled"], False)
        self.assertIs(rec["ok"], False)

    def test_the_outside_canary_stays_out_by_the_wall(self):
        # on macOS the system temp folder is outside the wall, so `outside` reads it there;
        # here the wall empties /tmp, so the read fails and restricted is true
        rec = self.run_probe("outside")
        self.assertIs(rec["restricted"], True, rec)
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

    def test_the_fake_ran_exactly_what_the_builders_gave(self):
        rec_dir = os.path.realpath(tempfile.mkdtemp(prefix="al2b-rec-"))
        self.addCleanup(shutil.rmtree, rec_dir, True)
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

        def walled(argv, **kw):
            calls.append(("wrap", dict(kw), list(argv)))
            kw["write"] = list(kw["write"]) + [rec_dir]
            return wall.wrap(argv, **kw)

        rec = probe.run(claude=claude, roots=self.roots, build_argv=b_argv, build_env=b_env,
                        wrap=walled, inside=True)
        self.assertIs(rec["ok"], True, rec)
        (seen,) = [json.load(open(os.path.join(rec_dir, n))) for n in os.listdir(rec_dir)]
        got = {kind: (kw, out) for kind, kw, out in calls}
        self.assertEqual(seen["argv"], got["argv"][1])
        env = {k: v for k, v in seen["env"].items() if k not in al2.MACOS_ADDS}
        self.assertEqual(env, got["env"][1])
        wrap_kw, wrapped = got["wrap"]
        self.assertEqual(wrap_kw["net"], "loopback")
        self.assertEqual(wrap_kw["read"][0], got["argv"][0]["dirs"][0])
        self.assertEqual(wrap_kw["write"][0], got["argv"][0]["run_dir"])
        self.assertEqual(wrapped[wrapped.index("--") + 1:], got["argv"][1])


class AgreeTest(BwrapCase):

    def test_sh_and_python_agree(self):
        got = subprocess.run(["/bin/sh", "-c", 'apilane_dir=$1; . "$1/prefilter.sh"; apilane_walled',
                              "sh", os.path.join(LIB, "apilane")], stdin=subprocess.DEVNULL)
        self.assertEqual(got.returncode, 0)
        self.assertEqual(wall.backend(), "bwrap")


if __name__ == "__main__":
    unittest.main(verbosity=2)
