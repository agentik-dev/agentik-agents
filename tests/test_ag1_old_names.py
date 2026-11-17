#!/usr/bin/python3
"""Packet ag1-old-name-links: a tool started by an old name keeps its tree through later installs.

An old name (agentroute, claude-agents, claude-local, localrig) is a link of install-cli's to the
dispatcher in the newest frozen tree, which execs the tool there by its real path, so a process
started by the old name has that tree on its command line and every later prune counts the tree
live (R1). A link of the old form, straight to a tool's own file in a tree, is moved to the new
form by the next install-cli, but stays where it points while a process names it by its path in
the bin folder: the prune counts that process's tree live through the link alone (R3). ia1's rules
hold (R2), and both uninstalls take the new form and keep a person's file (R4).

Each case runs in a temp HOME and a temp prefix, with a stand-in `ps` first on PATH that prints
the probe's line and the lines a case writes, and copies of this tree's plugin/ under five
versions, so each install freezes a tree of its own. No router, rig or model starts: the one
tool a case starts runs a stand-in `bash`, which records its arguments and exits.
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
VERSIONS = ("1.6.4", "1.9.0", "1.9.3", "1.9.4", "1.9.5")
PASSED = ("install-cli: left %s in %s as it is: not a link, so no old name's to refresh\n")
PS = """#!/bin/sh
[ ! -e '%(dir)s/ps-fails' ] || exit 1
printf '    1 /sbin/init AGENTIK_PRUNE_PROBE=%%s\\n' "$AGENTIK_PRUNE_PROBE"
cat '%(dir)s/ps-lines' 2>/dev/null
exit 0
"""
BASH = """#!/bin/sh
printf '%%s\\n' "$@" > '%(dir)s/argv'
"""


class OldNames(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.t = os.path.realpath(tempfile.mkdtemp(prefix="agents-ag1-"))
        cls.addClassCleanup(shutil.rmtree, cls.t, True)
        cls.plugins = []
        for ver in VERSIONS:
            copy = os.path.join(cls.t, "plugins", ver)
            shutil.copytree(os.path.join(REPO, "plugin"), copy, symlinks=True,
                            ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
            manifest = os.path.join(copy, ".claude-plugin", "plugin.json")
            with open(manifest, encoding="utf-8") as handle:
                data = json.load(handle)
            data["version"] = ver
            with open(manifest, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
            cls.plugins.append(copy)

    def setUp(self):
        self.home = os.path.join(self.t, self.id().rsplit(".", 1)[-1])
        self.stub = os.path.join(self.home, "stub")
        self.at("P")
        os.makedirs(self.stub)
        self.write(os.path.join(self.stub, "ps"), PS % {"dir": self.home}, 0o755)

    def at(self, name):
        """The case's prefix, `name` under its HOME, with an empty bin folder."""
        self.prefix = os.path.join(self.home, name)
        self.bin = os.path.join(self.prefix, "bin")
        self.share = os.path.join(self.prefix, "share", "agentik-agents")
        os.makedirs(self.bin)

    def write(self, path, text, mode=0o644):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(path, mode)

    def ps(self, *lines):
        """The processes the stand-in `ps` shows beside its probe's line."""
        self.write(os.path.join(self.home, "ps-lines"), "".join(l + "\n" for l in lines))

    def install(self, i):
        plugin = self.plugins[i]
        run = subprocess.run([os.path.join(plugin, "bin", "agentik-agents"), "install-cli",
                              "--prefix", self.prefix],
                             env={"HOME": self.home, "PATH": self.stub + ":/usr/bin:/bin",
                                  "CLAUDE_PLUGIN_ROOT": plugin,
                                  "CLAUDE_PLUGIN_DATA": os.path.join(self.home, "data")},
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return run

    @staticmethod
    def tree(run):
        """The frozen tree install-cli's first line names; its path may hold a space."""
        return re.search(r"^installed .+? -> (.+?) \([^()]*\); ", run.stdout, re.M).group(1)

    @staticmethod
    def pruned(run):
        return re.findall(r"^prune-trees: removed .*$", run.stdout, re.M)[-1]

    def old_link(self, tree, name):
        """An old name as a machine before this packet holds it: absolute, to the tool's file."""
        os.symlink(os.path.join(tree, name), os.path.join(self.bin, name))

    # ---- R3 and the finding's reproduction -------------------------------------------------

    def test_1_a_process_through_an_old_absolute_link_keeps_its_tree(self):
        t0 = self.tree(self.install(0))
        link = os.path.join(self.bin, "agentroute")
        self.old_link(t0, "agentroute")
        self.ps("  4242 /usr/bin/python3 %s serve" % link)
        lines = []
        for i in (1, 2, 3):
            run = self.install(i)
            lines.append(self.pruned(run))
            self.assertTrue(os.path.isdir(t0), (i, lines))
            self.assertEqual(os.readlink(link), os.path.join(t0, "agentroute"), i)
            self.assertIn("kept agentroute in %s -> its tree" % self.bin, run.stdout)
        self.assertEqual(lines[-1], "prune-trees: removed 0, kept 4 (1 live, the newest 3)")
        # the process ends: the next install moves the link to the new form, and t0 goes
        self.ps()
        run = self.install(3)
        self.assertEqual(os.readlink(link), os.path.join(self.tree(run), "agentik-agents"))
        self.assertFalse(os.path.exists(t0))
        self.assertEqual(self.pruned(run), "prune-trees: removed 1, kept 3 (0 live, the newest 3)")

    def test_10_a_held_link_whose_tree_the_prune_removed_moves(self):
        # review 1, F1: the prune cuts a process's path at a space, so with a space in the prefix
        # it never counts t0 live and removes it at the third install. A link is held only while
        # its target stands: then it moves like any other, and no `kept` line names it.
        self.at("P q")
        t0 = self.tree(self.install(0))
        link = os.path.join(self.bin, "agentroute")
        self.old_link(t0, "agentroute")
        self.ps("  4242 /usr/bin/python3 %s serve" % link)
        for i in (1, 2):
            run = self.install(i)
            self.assertEqual(os.readlink(link), os.path.join(t0, "agentroute"), i)
            self.assertIn("kept agentroute in %s -> its tree" % self.bin, run.stdout)
        run = self.install(3)
        self.assertFalse(os.path.exists(t0), "the case wants the prune to take t0: %s"
                         % self.pruned(run))
        self.assertEqual(os.readlink(link), os.path.join(self.tree(run), "agentik-agents"))
        self.assertNotIn("kept agentroute", run.stdout)
        helped = subprocess.run([link, "--help"], env={"HOME": self.home, "PATH": "/usr/bin:/bin"},
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(helped.returncode, 0, helped.stderr)
        self.assertTrue(helped.stdout.startswith("usage: agentroute"), helped.stdout[:200])

    def test_2_an_upgrade_with_no_process_moves_every_old_link(self):
        t0 = self.tree(self.install(0))
        for name in OLD:
            self.old_link(t0, name)
        self.ps()
        run = self.install(1)
        self.assertEqual(run.stderr, "")
        self.assertIn("linked %s in %s -> the tree" % (", ".join(OLD), self.bin), run.stdout)
        t1 = self.tree(run)
        for name in OLD:
            link = os.path.join(self.bin, name)
            self.assertEqual(os.readlink(link), os.path.join(t1, "agentik-agents"), name)
            self.assertTrue(os.access(link, os.X_OK), name)
        helped = subprocess.run([os.path.join(self.bin, "agentroute"), "--help"],
                                env={"HOME": self.home, "PATH": "/usr/bin:/bin"},
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(helped.returncode, 0, helped.stderr)
        self.assertTrue(helped.stdout.startswith("usage: agentroute"), helped.stdout[:200])

    def test_3_a_list_it_cannot_read_moves_the_link(self):
        t0 = self.tree(self.install(0))
        self.old_link(t0, "localrig")
        self.write(os.path.join(self.home, "ps-fails"), "")
        run = self.install(1)
        self.assertEqual(os.readlink(os.path.join(self.bin, "localrig")),
                         os.path.join(self.tree(run), "agentik-agents"))
        self.assertIn("keeping every tree", run.stdout)

    # ---- R1: a tool started by an old name names its tree ---------------------------------

    def test_4_a_tool_started_by_an_old_name_names_its_tree(self):
        t0 = self.tree(self.install(0))
        self.old_link(t0, "localrig")
        self.ps()
        t1 = self.tree(self.install(1))
        link = os.path.join(self.bin, "localrig")
        fake = os.path.join(self.home, "fake")
        os.makedirs(fake)
        self.write(os.path.join(fake, "bash"), BASH % {"dir": self.home}, 0o755)
        started = subprocess.run([link, "up"], env={"HOME": self.home,
                                                    "PATH": fake + ":/usr/bin:/bin"},
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(started.returncode, 0, started.stderr)
        with open(os.path.join(self.home, "argv"), encoding="utf-8") as handle:
            argv = handle.read().split("\n")
        self.assertEqual(argv[:2], [os.path.join(t1, "localrig"), "up"])
        self.ps("  4243 bash %s up" % argv[0])
        lines = []
        for i in (2, 3, 4):
            run = self.install(i)
            lines.append(self.pruned(run))
            self.assertTrue(os.path.isdir(t1), (i, lines))
            self.assertEqual(os.readlink(link), os.path.join(self.tree(run), "agentik-agents"))
        self.assertEqual(lines[-1], "prune-trees: removed 0, kept 4 (1 live, the newest 3)")

    def test_5_the_new_form_moves_while_a_shell_names_it(self):
        # a shell's `_` names the old name's path; the new form holds nothing, so it moves
        t0 = self.tree(self.install(0))
        self.old_link(t0, "agentroute")
        self.ps()
        self.install(1)
        link = os.path.join(self.bin, "agentroute")
        self.ps("  77 /bin/zsh -l _=%s" % link)
        run = self.install(2)
        self.assertEqual(os.readlink(link), os.path.join(self.tree(run), "agentik-agents"))
        self.assertNotIn("kept agentroute", run.stdout)

    # ---- R2: ia1's rules ------------------------------------------------------------------

    def test_6_a_new_prefix_gets_no_old_name(self):
        self.ps()
        self.install(1)
        self.install(2)
        self.assertEqual(sorted(os.listdir(self.bin)), ["agentik", "agentik-agents"])

    def test_7_a_persons_file_is_passed_over(self):
        self.ps()
        mine = os.path.join(self.bin, "localrig")
        self.write(mine, "mine\n", 0o755)
        t0 = self.tree(self.install(0))
        self.old_link(t0, "agentroute")
        for i in (1, 2):
            run = self.install(i)
            self.assertEqual(run.stderr, PASSED % ("localrig", "~/P/bin"))
            self.assertFalse(os.path.islink(mine))
            with open(mine, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "mine\n")
            self.assertEqual(os.readlink(os.path.join(self.bin, "agentroute")),
                             os.path.join(self.tree(run), "agentik-agents"))
        for name in ("claude-agents", "claude-local"):
            self.assertFalse(os.path.lexists(os.path.join(self.bin, name)), name)

    # ---- R4: both uninstalls take the new form and keep a person's file -------------------

    def upgraded(self):
        """A prefix holding the new form at agentroute and a person's file at claude-local."""
        self.ps()
        t0 = self.tree(self.install(0))
        self.old_link(t0, "agentroute")
        mine = os.path.join(self.bin, "claude-local")
        self.write(mine, "mine\n", 0o755)
        run = self.install(1)
        ours = os.path.join(self.bin, "agentroute")
        self.assertEqual(os.readlink(ours), os.path.join(self.tree(run), "agentik-agents"))
        return ours, mine

    def gone_but_mine(self, ours, mine):
        self.assertFalse(os.path.lexists(ours))
        self.assertFalse(os.path.lexists(os.path.join(self.bin, "agentik-agents")))
        self.assertFalse(os.path.exists(self.share))
        with open(mine, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "mine\n")

    def test_8_the_suites_remove_takes_the_new_form(self):
        ours, mine = self.upgraded()
        code = ("import json, sys; sys.path.insert(0, sys.argv[1]); import agentik_install as a; "
                "a.PS = sys.argv[2]; print(json.dumps(a.uninstall('agentik-agents', sys.argv[3])))")
        run = subprocess.run(["/usr/bin/python3", "-I", "-c", code,
                              os.path.join(self.plugins[1], "lib"), os.path.join(self.stub, "ps"),
                              self.prefix],
                             env={"HOME": self.home, "PATH": "/usr/bin:/bin"},
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr)
        rows = [tuple(r) for r in json.loads(run.stdout)]
        self.assertIn((ours, "link", "removed"), rows)
        self.assertNotIn(mine, [r[0] for r in rows])
        self.gone_but_mine(ours, mine)

    def test_9_make_uninstall_takes_the_new_form(self):
        ours, mine = self.upgraded()
        run = subprocess.run(["make", "-C", REPO, "--no-print-directory", "uninstall"],
                             env={"HOME": self.home, "PATH": "/usr/bin:/bin",
                                  "PREFIX": self.prefix, "GIT_CONFIG_NOSYSTEM": "1"},
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("  removed %s\n" % ours, run.stdout)
        self.assertIn("  skipped %s (not a link into %s)\n" % (mine, self.share), run.stdout)
        self.gone_but_mine(ours, mine)


if __name__ == "__main__":
    unittest.main(verbosity=2)
