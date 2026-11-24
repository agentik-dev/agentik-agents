#!/usr/bin/python3
"""Packet al9a-write-wall: the write rule and the `.git` rule under the real bubblewrap wall.

Run as `python3 tests/test_al9a_linux.py [Class]`. Each test starts the real /usr/bin/bwrap around
al2b's fake in a temp home, with a worktree that `git worktree add` made from a throwaway repo
there; where `wall.backend()` is not "bwrap" every class skips with al2b's one reason and the
suite ends OK. The macOS cases, and the argv on both backends, are tests/test_al9a_wall.py's.

On bwrap the root is read-only and `/tmp`, `/var/tmp` and the home are tmpfs thrown away at the
end, so an outside write either fails with a read-only error or lands in a tmpfs and is gone
once the wall has ended: each case asserts the disk outside holds nothing. RecordedTest's two
cases assert only that they ran, and print what they found.

No test starts tests/fake-claude, the real claude or sops. Every key is made up; the stub binds
loopback inside the wall.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import test_al2_wall as al2  # noqa: E402
import test_al2b_linux as al2b  # noqa: E402  (its reason, its walled case)
import test_al9a_wall as al9a  # noqa: E402  (the worktree, the fake writer, the stand-in type)

wall = al2b.wall
probe = al2b.probe


class WriteCase(al2b.BwrapCase):
    """A temp home with a worktree, a run folder's stand-in and a read dir."""

    def setUp(self):
        super().setUp()
        if al9a.GIT is None:
            self.skipTest("no git here: the worktree cannot be made")
        self.tree = al9a.worktree(self.home.root)
        self.run_dir = self.home.mkdir("run")
        self.job = self.home.mkdir("job")
        self.git_bytes = al9a.read_bytes(os.path.join(self.tree, ".git"))

    def sh(self, script, write=None, env=None):
        return self.walled(["/bin/sh", "-c", script], read=[self.job],
                           write=[self.run_dir, self.tree] if write is None else write, env=env)

    def gone(self, path):
        self.addCleanup(lambda: os.path.lexists(path) and os.unlink(path))
        return path

    def left_nothing(self, target):
        self.gone(target)
        run = self.sh("printf al9a-out > '%s'" % target)
        self.assertFalse(os.path.lexists(target), "%s landed: %s" % (target, run.stderr))
        return run


class WriteLandsTest(WriteCase):
    """Acceptance 1."""

    def test_the_worktree_and_the_run_folder_take_their_files(self):
        a, r = os.path.join(self.tree, "a.txt"), os.path.join(self.run_dir, "r.txt")
        run = self.sh("printf al9a-a > '%s' && printf al9a-r > '%s'" % (a, r))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(al9a.read_bytes(a), b"al9a-a")
        self.assertEqual(al9a.read_bytes(r), b"al9a-r")


class WriteRefusedTest(WriteCase):
    """Acceptance 2: a read dir refused; the account's TMPDIR and /var/tmp leave nothing."""

    def test_a_read_dir(self):
        run = self.left_nothing(os.path.join(self.job, "b.txt"))
        self.assertNotEqual(run.returncode, 0)

    def test_the_accounts_tmpdir(self):
        self.left_nothing(os.path.join(os.path.realpath(tempfile.gettempdir()),
                                       "al9a-temp-%d.txt" % os.getpid()))

    def test_var_tmp(self):
        self.left_nothing(os.path.join(os.path.realpath("/var/tmp"),
                                       "al9a-vartmp-%d.txt" % os.getpid()))


class GitRefusedTest(WriteCase):
    """Acceptance 3: the worktree's `.git` written, truncated, removed or replaced."""

    def tearDown(self):
        g = os.path.join(self.tree, ".git")
        self.assertTrue(os.path.isfile(g) and not os.path.islink(g))
        self.assertEqual(al9a.read_bytes(g), self.git_bytes)

    def attempt(self, script):
        run = self.sh(script % {"g": os.path.join(self.tree, ".git"), "t": self.tree})
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_written(self):
        self.attempt("printf 'gitdir: /made/up\\n' >> '%(g)s'")

    def test_truncated(self):
        self.attempt(": > '%(g)s'")

    def test_removed(self):
        self.attempt("/bin/rm -f '%(g)s'")

    def test_replaced_by_a_rename(self):
        self.gone(os.path.join(self.tree, "x"))
        self.attempt("printf 'gitdir: /made/up\\n' > '%(t)s/x' && /bin/mv -f '%(t)s/x' '%(g)s'")


class GitArgvTest(WriteCase):
    """Acceptance 4 on the real backend: the `.git` bind follows the worktree's own."""

    def test_the_git_bind_follows_the_folders_own(self):
        cmd = wall.wrap([self.fake, "/bin/true"], read=[self.job], write=[self.run_dir, self.tree],
                        net="all", home=self.home.root)
        g = os.path.join(self.tree, ".git")
        pairs = [tuple(cmd[i:i + 3]) for i in range(len(cmd) - 2)]
        self.assertIn(("--ro-bind", g, g), pairs)
        self.assertGreater(pairs.index(("--ro-bind", g, g)),
                           pairs.index(("--bind", self.tree, self.tree)))
        rg = os.path.join(self.run_dir, ".git")
        self.assertNotIn(("--ro-bind", rg, rg), pairs)


class MkdirTest(WriteCase):
    """Acceptance 6: `mkdir -p` of three new folders by absolute path, recorded and asserted."""

    def test_mkdir_p_three_new_folders(self):
        deep = os.path.join(self.tree, "n1", "n2", "n3")
        run = self.sh("/bin/mkdir -p '%s'" % deep)
        print("\nmkdir -p under bwrap: exit %d, %s%s" % (
            run.returncode, "made" if os.path.isdir(deep) else "not made",
            (": " + run.stderr.strip()) if run.stderr.strip() else ""))
        # expected on Linux: the parents exist in the mount tree, so EEXIST, and it is made
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(os.path.isdir(deep))


class RecordedTest(WriteCase):
    """Acceptance 9: two outcomes recorded, each asserting only that it ran (§4 items 1 and 3)."""

    def test_a_rename_from_the_run_folders_tmpdir_into_the_worktree(self):
        tmp = self.home.mkdir("run", "tmp")
        src, dst = os.path.join(tmp, "f.txt"), os.path.join(self.tree, "f.txt")
        code = ("import errno, os, sys; print('al9a-ran'); open(sys.argv[1], 'w').write('x')\n"
                "try:\n    os.rename(sys.argv[1], sys.argv[2]); print('renamed')\n"
                "except OSError as e:\n    print('rename failed:', errno.errorcode.get(e.errno))")
        run = self.walled(["/usr/bin/python3", "-I", "-c", code, src, dst], read=[self.job],
                          write=[self.run_dir, self.tree], env={"TMPDIR": tmp})
        print("\nrename from TMPDIR into the worktree: exit %d, %s" % (
            run.returncode, (run.stdout + run.stderr).strip().replace("\n", " | ")))
        self.assertIn("al9a-ran", run.stdout)

    def test_the_one_file_read_only_bind_over_git(self):
        run = self.sh("echo al9a-started")
        print("\none-file --ro-bind over .git: exit %d, %s" % (
            run.returncode, (run.stdout + run.stderr).strip().replace("\n", " | ")))
        self.assertIsInstance(run.returncode, int)


class WriterProbeTest(al2b.ProbeCase):
    """Acceptance 8 for 11: the writer's pass with the stub inside the wall."""

    def test_the_writers_pass(self):
        if al9a.GIT is None:
            self.skipTest("no git here: the throwaway repo cannot be made")
        claude = self.home.write("tools/claude-w-good", al9a.FAKE_WRITER % {
            "py": al2.FAKE_PY, "mode": "good", "version": al2.VERSION}, 0o755)
        rec = probe.run(claude=claude, roots=self.roots, build_argv=al9a.build_argv,
                        build_env=al2.build_env, writer=True, writer_type=al9a.STAND_IN)
        print("\nthe writer object under bwrap: " + json.dumps(rec.get("writer")))
        checks = {c["name"]: c["ok"] for c in rec["writer"]["checks"]}
        self.assertEqual(checks, dict.fromkeys(al9a.WRITER_CHECKS, True), rec["writer"])
        self.assertEqual(os.listdir(self.roots.state), ["probe.json"])


def widen_out(argv, *, read, write, net, home):
    """The stand-in under bwrap: the real wall, with the temp folder and /var/tmp alone bound
    writable, so the direct attempt's write there lands on the disk. The read dir stays as the
    wall has it: writable, the refusing fake's own write would land there and the CLI's attempt
    would be named, where the case means to prove the direct one."""
    out = [os.path.realpath(tempfile.gettempdir()), os.path.realpath("/var/tmp")]
    return wall.wrap(argv, read=read, write=list(write) + out, net=net, home=home)


class WriterWalledTest(al2b.ProbeCase):
    """R2 of brief 2: `writewalled` under bwrap proves the wall by the direct attempt."""

    def run_writer(self, mode, **kw):
        if al9a.GIT is None:
            self.skipTest("no git here: the throwaway repo cannot be made")
        claude = self.home.write("tools/claude-w-" + mode, al9a.FAKE_WRITER % {
            "py": al2.FAKE_PY, "mode": mode, "version": al2.VERSION}, 0o755)
        rec = probe.run(claude=claude, roots=self.roots, build_argv=al9a.build_argv,
                        build_env=al2.build_env, writer=True, writer_type=al9a.STAND_IN, **kw)
        c = {c["name"]: c for c in rec["writer"]["checks"]}["writewalled"]
        print("\nwritewalled under bwrap, %s: %s" % (mode, json.dumps(c)))
        self.assertEqual(al9a.leftovers(), [])
        return c

    def test_a_cli_that_refuses_itself_under_a_widened_wall(self):
        c = self.run_writer("refuse", wrap=widen_out, inside=True)
        self.assertIs(c["ok"], False)
        self.assertTrue(c["detail"].startswith("the direct attempt: "), c)

    def test_a_wall_that_starts_nothing(self):
        c = self.run_writer("good", wrap=al9a.starts_nothing)
        self.assertEqual((c["ok"], c["detail"]), (False, "the direct attempt: it did not run"))

    def test_under_the_real_wall(self):
        c = self.run_writer("refuse")
        self.assertIs(c["ok"], True, c)
        self.assertTrue(c["detail"].startswith("neither attempt's outside writes landed"), c)


if __name__ == "__main__":
    unittest.main(verbosity=2)
