#!/usr/bin/python3
"""Packet al9a-write-wall: the wall's write rule and `.git` rule, and the probe's writer's pass.

Run as `python3 tests/test_al9a_wall.py [Class]`. The write classes start the real
/usr/bin/sandbox-exec around al2's in-file fake, in a temp home, with a worktree that
`git worktree add` made from a throwaway repo there; where no macOS wall starts they skip with
al2's reason. ProfileTest and BwrapGitTest read the argv `wall.wrap` returns with the backend
forced, and run on any platform; StubCallsTest and PassedTest need no wall. The same cases under
the real bubblewrap wall are tests/test_al9a_linux.py's.

No test starts tests/fake-claude, the real claude or sops: every fake is written here or is al2's,
in a temp folder, on a PATH built from nothing. Every key is made up; the stub binds loopback.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import test_al2_wall as al2  # noqa: E402  (its fake, its builders, its temp home)
import test_al2b_argv as al2b  # noqa: E402  (its reading of a bwrap argv)

wall = al2.load("wall")
probe = al2.load("probe")
stubapi = al2.load("stubapi")
apitypes = al2.load("types")
GIT = shutil.which("git", path="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin")
DATA = "/System/Volumes/Data"
WRITE_RULE = '(deny file-write* (subpath "/"))'
STAND_IN = apitypes.Type("al9a-writer", "made-up-model", ("Read", "Edit", "Write"), None)
WRITER_CHECKS = ["key", "tools", "walled", "restricted", "write", "writewalled", "inert"]
# the pin's stub, its six replies to one made-up conversation: the sha256 measured at 82f2710
PIN_REPLIES = "677f945dc873c5ec1005eec261d4ef490157362c47f89177c41a004407fb7da8"


def git(*argv, cwd):
    env = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "HOME": cwd}
    subprocess.run([GIT, "-c", "core.hooksPath=/dev/null", "-C", cwd] + list(argv), env=env,
                   check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60)


def worktree(root):
    """A throwaway repo of one commit under `root` and a worktree of it: the worktree's path."""
    repo = os.path.join(root, "src", "repo")
    os.makedirs(repo)
    with open(os.path.join(repo, "README"), "w") as fh:
        fh.write("made-up\n")
    git("init", "-q", cwd=repo)
    git("add", "README", cwd=repo)
    git("-c", "user.name=made-up", "-c", "user.email=made-up@localhost", "-c",
        "commit.gpgsign=false", "commit", "-q", "-m", "one", cwd=repo)
    tree = os.path.join(root, "src", "tree")
    git("worktree", "add", "-q", "-b", "al9a", tree, cwd=repo)
    return os.path.realpath(tree)


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def profile(cmd):
    return cmd[cmd.index("-p") + 1]


class WriteCase(al2.WallCase):
    """A temp home with a worktree, a run folder's stand-in and a read dir."""

    def setUp(self):
        super().setUp()
        if GIT is None:
            self.skipTest("no git here: the worktree cannot be made")
        self.tree = worktree(self.home.root)
        self.run_dir = self.home.mkdir("run")
        self.job = self.home.mkdir("job")
        self.git_bytes = read_bytes(os.path.join(self.tree, ".git"))

    def sh(self, script, write=None):
        return self.walled(["/bin/sh", "-c", script], read=[self.job],
                           write=[self.run_dir, self.tree] if write is None else write)

    def gone(self, path):
        """Removed at the test's end, whatever it found."""
        def drop():
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, True)
            elif os.path.lexists(path):
                os.unlink(path)
        self.addCleanup(drop)
        return path

    def refused_write(self, target):
        self.gone(target)
        run = self.sh("printf al9a-out > '%s'" % target)
        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertFalse(os.path.lexists(target), "%s landed" % target)


class WriteLandsTest(WriteCase):
    """Acceptance 1."""

    def test_the_worktree_and_the_run_folder_take_their_files(self):
        a, r = os.path.join(self.tree, "a.txt"), os.path.join(self.run_dir, "r.txt")
        run = self.sh("printf al9a-a > '%s' && printf al9a-r > '%s'" % (a, r))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(read_bytes(a), b"al9a-a")
        self.assertEqual(read_bytes(r), b"al9a-r")

    def test_a_read_shards_profile_holds_the_rule(self):
        self.need_wall()
        cmd = wall.wrap([self.fake, "/usr/bin/true"], read=[self.job], write=[self.run_dir],
                        net="all", home=self.home.root)
        self.assertIn(WRITE_RULE, profile(cmd).splitlines())
        target = self.gone(os.path.join(os.path.realpath(tempfile.gettempdir()),
                                        "al9a-read-type-%d" % os.getpid()))
        run = self.sh("printf x > '%s'" % target, write=[self.run_dir])
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse(os.path.lexists(target))


class WriteRefusedTest(WriteCase):
    """Acceptance 2: four outside writes refused, nothing left."""

    def test_a_read_dir(self):
        self.refused_write(os.path.join(self.job, "b.txt"))

    def test_the_accounts_temp_folder(self):
        self.refused_write(os.path.join(os.path.realpath(tempfile.gettempdir()),
                                        "al9a-temp-%d.txt" % os.getpid()))

    def test_a_folder_made_under_private_var_folders(self):
        temp = os.path.realpath(tempfile.gettempdir())
        if not temp.startswith("/private/var/folders/"):
            self.skipTest("the account's temp folder is not under /private/var/folders here")
        try:
            folder = tempfile.mkdtemp(prefix="al9a-", dir=os.path.dirname(temp))
        except OSError as e:
            self.skipTest("the account cannot make a folder beside its temp folder: %s" % e)
        self.gone(folder)
        self.refused_write(os.path.join(folder, "c.txt"))

    def test_private_var_tmp(self):
        self.refused_write(os.path.join(os.path.realpath("/var/tmp"),
                                        "al9a-vartmp-%d.txt" % os.getpid()))


class GitRefusedTest(WriteCase):
    """Acceptance 3: the worktree's `.git` link written, truncated, removed or replaced."""

    def tearDown(self):
        git_path = os.path.join(self.tree, ".git")
        self.assertTrue(os.path.isfile(git_path) and not os.path.islink(git_path))
        self.assertEqual(read_bytes(git_path), self.git_bytes)

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


class MkdirTest(WriteCase):
    """Acceptance 6: `mkdir -p` of three new folders by absolute path, recorded."""

    def test_mkdir_p_three_new_folders(self):
        deep = os.path.join(self.tree, "n1", "n2", "n3")
        run = self.sh("/bin/mkdir -p '%s'" % deep)
        print("\nmkdir -p under the write rule: exit %d, %s%s" % (
            run.returncode, "made" if os.path.isdir(deep) else "not made",
            (": " + run.stderr.strip()) if run.stderr.strip() else ""))
        # measured at the head: BSD mkdir -p walks from `/` and stops with EPERM at the first
        # folder the wall denies (here the temp home), not EEXIST; Python's makedirs, which
        # walks up from the leaf, makes the same three (WriterPassTest's deep file)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("Operation not permitted", run.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tree, "n1")))


class DeviceTest(WriteCase):
    """Acceptance 5: the three devices take writes; the fake starts and exits."""

    def test_dev_null_and_dev_fd_1(self):
        mark = os.path.join(self.run_dir, "mark")
        self.need_wall()
        script = "echo gone > /dev/null && echo seen > /dev/fd/1"
        cmd = wall.wrap([self.fake, "/bin/sh", "-c", script], read=[self.job],
                        write=[self.run_dir], net="all", home=self.home.root)
        run = subprocess.run(cmd, capture_output=True, text=True, cwd="/", timeout=60,
                             env={"PATH": "/usr/bin:/bin", "HOME": self.home.root,
                                  "FAKE_MARK": mark})
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, "seen\n")
        self.assertTrue(os.path.exists(mark))

    def test_dev_tty_where_there_is_a_terminal(self):
        try:
            os.close(os.open("/dev/tty", os.O_WRONLY))
        except OSError:
            self.skipTest("this test has no terminal: /dev/tty stays unrun")
        run = self.sh("printf '' > /dev/tty")
        self.assertEqual(run.returncode, 0, run.stderr)


class ProfileTest(unittest.TestCase):
    """Acceptance 4, the macOS profile, the backend forced: the `.git` rule by what `lstat` sees."""

    def setUp(self):
        self.home = al2.Home(self)
        self.fake = self.home.write("tools/fake", "#!/bin/sh\nexec \"$@\"\n", 0o755)
        p = mock.patch.object(wall, "backend", lambda: "sandbox-exec")
        p.start()
        self.addCleanup(p.stop)

    def rules(self, *write):
        cmd = wall.wrap([self.fake], read=[], write=list(write), net="all", home=self.home.root)
        return profile(cmd).splitlines()

    def git_rule(self, rules):
        return [r for r in rules if r.startswith("(deny file-write* ") and ".git" in r]

    def test_the_write_rule_and_the_devices_follow_allow_default(self):
        rules = self.rules(self.home.mkdir("run"))
        self.assertEqual(rules[1:4], ["(allow default)", WRITE_RULE,
                                      '(allow file-write* (literal "/dev/null") '
                                      '(literal "/dev/tty") (subpath "/dev/fd"))'])
        self.assertTrue(rules[-1].startswith("(deny file-read* file-write* "))   # secrets last

    def test_a_git_file_gets_the_literal_rule(self):
        w = self.home.mkdir("w")
        self.home.write("w/.git", "gitdir: /made/up\n")
        rules = self.rules(w)
        g = os.path.join(w, ".git")
        self.assertEqual(self.git_rule(rules), ['(deny file-write* (literal "%s") (literal "%s"))'
                                                % (g, DATA + g)])
        allow = [i for i, r in enumerate(rules) if r.startswith("(allow file-read* file-write*")]
        self.assertGreater(rules.index(self.git_rule(rules)[0]), allow[0])

    def test_a_git_folder_gets_literal_and_subpath(self):
        w = self.home.mkdir("w")
        self.home.mkdir("w", ".git")
        g = os.path.join(w, ".git")
        self.assertEqual(self.git_rule(self.rules(w)), [
            '(deny file-write* (literal "%s") (literal "%s") (subpath "%s") (subpath "%s"))'
            % (g, DATA + g, g, DATA + g)])

    def test_the_run_folder_gets_neither(self):
        self.assertEqual(self.git_rule(self.rules(self.home.mkdir("run"))), [])

    def test_a_git_link_is_never_followed(self):
        w, target = self.home.mkdir("w"), self.home.mkdir("elsewhere")
        os.symlink(target, os.path.join(w, ".git"))
        rules = self.rules(w)
        g = os.path.join(w, ".git")
        self.assertEqual(self.git_rule(rules), ['(deny file-write* (literal "%s") (literal "%s"))'
                                                % (g, DATA + g)])
        self.assertNotIn(target, "\n".join(self.git_rule(rules)))

    def test_the_signature_is_unchanged(self):
        import inspect
        self.assertEqual(str(inspect.signature(wall.wrap)), "(argv, *, read, write, net, home)")


class BwrapGitTest(al2b.BwrapArgvTest):
    """Acceptance 4 on bwrap's argv, built here without starting it."""

    def test_the_git_bind_follows_the_folders_own(self):
        w, run = self.home.mkdir("w"), self.home.mkdir("run")
        self.home.write("w/.git", "gitdir: /made/up\n")
        m = al2b.mounts(al2b.ops(self.wrap(write=[run, w]))[0])
        g = os.path.join(w, ".git")
        self.assertIn(("ro", g), m)
        self.assertGreater(m.index(("ro", g)), m.index(("rw", w)))
        self.assertNotIn(("ro", os.path.join(run, ".git")), m)


# BwrapArgvTest's own tests run in their file; here, this class's alone
for _name in [n for n in dir(al2b.BwrapArgvTest) if n.startswith("test_")]:
    setattr(BwrapGitTest, _name, None)


class StubCallsTest(unittest.TestCase):
    """Acceptance 10."""

    def converse(self, stub, turns, results=True):
        url = stub.start()
        self.addCleanup(stub.stop)
        messages, seen = [{"role": "user", "content": "go"}], []
        for turn in range(turns):
            for stream in (False, True):
                body = {"model": "m", "max_tokens": 9, "messages": messages,
                        "tools": [{"name": "Read"}], "stream": stream}
                seen.append(al2.post(url, body, {"x-api-key": "made-up"}))
            kind, text = seen[-2]
            content = json.loads(text)["content"]
            messages.append({"role": "assistant", "content": content})
            if results and content[0]["type"] == "tool_use":
                messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": content[0]["id"],
                     "content": "result-%d" % turn}]})
        return seen

    def test_a_list_of_writes_and_reads(self):
        calls = [{"tool": "Write", "path": "/made/up/w.txt", "text": "made-up text"},
                 {"tool": "Read", "path": "/made/up/r.txt"}]
        stub = stubapi.Stub(reads=["/made/up/ignored"], calls=calls)
        seen = self.converse(stub, 3)
        whole = [json.loads(t)["content"][0] for _, t in seen[0::2]]
        self.assertEqual([(b["type"], b.get("name"), b.get("input")) for b in whole], [
            ("tool_use", "Write", {"file_path": "/made/up/w.txt", "content": "made-up text"}),
            ("tool_use", "Read", {"file_path": "/made/up/r.txt"}),
            ("text", None, None)])
        content, stop = al2.from_stream(seen[1][1])
        self.assertEqual((content[0]["name"], content[0]["input"], stop),
                         ("Write", {"file_path": "/made/up/w.txt", "content": "made-up text"},
                          "tool_use"))
        self.assertEqual([r["text"] for r in stub.results], ["result-0", "result-1"])

    def test_with_no_list_the_replies_are_the_pins(self):
        stub = stubapi.Stub(reads=["/made/up/one", "/made/up/two"])
        h = hashlib.sha256()
        for kind, text in self.converse(stub, 3, results=False):
            h.update(kind.encode() + b"\0" + text.encode() + b"\0")
        self.assertEqual(h.hexdigest(), PIN_REPLIES)


FAKE_WRITER = r'''#!%(py)s
import json, os, subprocess, sys, urllib.request
MODE = %(mode)r
args = sys.argv[1:]
if args[:1] == ["--version"]:
    print("%(version)s (Fake Code)")
    sys.exit(0)
restricted = "--restricted" in args
tools = args[args.index("--tools") + 1].split() if "--tools" in args else ["Read", "Grep", "Glob"]
writer = "Write" in tools
if MODE == "more":
    tools = tools + ["Bash"]
elif MODE == "less":
    tools = tools[:-1]
def hook(path):
    with open(path) as fh:
        command = json.load(fh)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    subprocess.call(["/bin/sh", "-c", command])
if writer and MODE == "hook":
    hook(os.path.join(os.getcwd(), ".claude", "settings.json"))
if writer and MODE == "confighook":
    hook(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "settings.json"))
if writer and MODE == "claudemd":
    with open(os.path.join(os.getcwd(), "CLAUDE.md")) as fh:
        mark = [l[6:].strip() for l in fh if l.startswith("mark: ")][0]
    with open(mark, "w") as fh:
        fh.write("honoured\n")
dirs = [os.path.realpath(args[i + 1]) for i, a in enumerate(args) if a == "--add-dir"]
base = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
heads = {"content-type": "application/json", "x-api-key": os.environ["ANTHROPIC_API_KEY"]}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def inside(p):
    p = os.path.realpath(p)
    return any(p == d or p.startswith(d + "/") for d in dirs)
messages = [{"role": "user", "content": "probe"}]
for turn in range(12):
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
        try:
            if block["name"] == "Write":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as fh:
                    fh.write(block["input"]["content"])
                text, err = "written", False
            elif restricted and not writer and not inside(path):
                text, err = "outside the working directories", True
            else:
                with open(path) as fh:
                    text, err = fh.read(), False
        except OSError as e:
            text, err = "failed: %%s" %% e.strerror, True
        results.append({"type": "tool_result", "tool_use_id": block["id"], "content": text,
                        "is_error": err})
    messages.append({"role": "user", "content": results})
print(json.dumps({"type": "result", "result": "done"}))
'''


def build_argv(shard, **kw):
    """al2's builder, with the type's tools named as the CLI's `--tools`."""
    tools = STAND_IN.tools if shard.type == STAND_IN.name else apitypes.TOOLS
    return al2.build_argv(shard, **kw) + ["--tools", " ".join(tools)]


class WriterCase(al2.ProbeCase):

    def cli(self, mode="good", record=None):
        return self.home.write("tools/claude-w-" + mode, FAKE_WRITER % {
            "py": al2.FAKE_PY, "mode": mode, "version": al2.VERSION}, 0o755)

    def run_writer(self, mode="good", wrap=None, writer_type=STAND_IN, **kw):
        if wrap is None:
            self.need_wall()
        if GIT is None:
            self.skipTest("no git here: the throwaway repo cannot be made")
        return self.probe.run(claude=self.cli(mode), roots=self.roots, build_argv=build_argv,
                              build_env=al2.build_env, wrap=wrap, writer=True,
                              writer_type=writer_type, **kw)

    def wchecks(self, rec):
        return {c["name"]: c for c in rec["writer"]["checks"]}


def widen_to_read(argv, *, read, write, net, home):
    """A stand-in wall that lets the read dir's write through."""
    return wall.wrap(argv, read=read, write=list(write) + list(read[:1]), net=net, home=home)


class WriterPassTest(WriterCase):
    """Acceptance 11, 12, 14: the writer's pass under the real wall."""

    def test_all_pass_and_the_throwaway_repo_is_gone(self):
        rec = self.run_writer("good")
        self.assertIs(rec["ok"], True, rec)
        w = rec["writer"]
        self.assertEqual(set(w), {"version", "ok", "checks"})
        self.assertEqual([c["name"] for c in w["checks"]], WRITER_CHECKS)
        self.assertEqual({n: c["ok"] for n, c in self.wchecks(rec).items()},
                         dict.fromkeys(WRITER_CHECKS, True), w)
        self.assertEqual((w["version"], w["ok"]), (al2.VERSION, True))
        self.assertEqual(self.wchecks(rec)["tools"]["detail"], "offered: Edit, Read, Write")
        with open(os.path.join(self.roots.state, "probe.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), rec)
        self.assertEqual(os.listdir(self.roots.state), ["probe.json"])
        self.assertTrue(self.probe.passed(self.roots, al2.VERSION, writer=True))
        print("\nthe writer object: " + json.dumps(w))

    def test_a_wall_that_lets_one_through_fails_writewalled(self):
        rec = self.run_writer("good", wrap=widen_to_read)
        c = self.wchecks(rec)["writewalled"]
        self.assertEqual((c["ok"], c["detail"]), (False, "landed: the read dir"))
        self.assertIs(rec["writer"]["ok"], False)
        self.assertIs(rec["ok"], True)       # the reader's verdict is its own

    def test_a_wall_that_walls_nothing_names_every_write_and_git(self):
        rec = self.run_writer("good", wrap=al2.open_wrap)
        c = self.wchecks(rec)["writewalled"]
        self.assertIs(c["ok"], False)
        for name in ("the read dir", "the account's temp folder", "/var/tmp", ".git"):
            self.assertIn(name, c["detail"])
        self.assertIs(self.wchecks(rec)["write"]["ok"], True)

    def test_one_tool_more_or_less_fails_tools(self):
        for mode, said in (("more", "offered beyond Read, Edit, Write: Bash"),
                           ("less", "not offered: Write")):
            rec = self.run_writer(mode)
            self.assertEqual((self.wchecks(rec)["tools"]["ok"],
                              self.wchecks(rec)["tools"]["detail"]), (False, said))
            self.assertIs({c["name"]: c["ok"] for c in rec["checks"]}["tools"], False, mode)


class InertTest(WriterCase):
    """Acceptance 13: each plant, honoured in turn, fails `inert` and is named."""

    def test_each_plant(self):
        for mode, plant in (("hook", "worktree-settings"), ("claudemd", "worktree-claude-md"),
                            ("confighook", "config-settings")):
            rec = self.run_writer(mode)
            c = self.wchecks(rec)["inert"]
            self.assertEqual((c["ok"], c["detail"]), (False, "took effect: " + plant), mode)
            self.assertEqual(os.listdir(self.roots.state), ["probe.json"])

    def test_the_claude_md_in_a_request_fails_inert(self):
        real = stubapi.Stub.record

        def planted(stub, headers, body, raw):   # as if the CLI had loaded it into its prompt
            tree = os.path.join(self.roots.state, "probe", "writer", "tree", "CLAUDE.md")
            if os.path.exists(tree):
                raw += open(tree).read().splitlines()[0]
            return real(stub, headers, body, raw)
        with mock.patch.object(stubapi.Stub, "record", planted):
            rec = self.run_writer("good")
        self.assertEqual(self.wchecks(rec)["inert"]["detail"], "took effect: worktree-claude-md")


class PassedTest(WriterCase):
    """Acceptance 15: a reader never waits on the writer."""

    def write_record(self, **over):
        rec = {"schema": al2.SCHEMA, "cli_version": al2.VERSION, "at": "2026-01-01T00:00:00Z",
               "ok": True, "restricted": True,
               "checks": [{"name": n, "ok": True, "detail": ""} for n in al2.CHECKS]}
        rec.update(over)
        os.makedirs(self.roots.state, exist_ok=True)
        with open(os.path.join(self.roots.state, "probe.json"), "w", encoding="utf-8") as h:
            json.dump(rec, h)

    def test_passed_reader_and_writer(self):
        self.write_record()     # the pin's shape: no writer object
        self.assertTrue(self.probe.passed(self.roots, al2.VERSION))
        self.assertFalse(self.probe.passed(self.roots, al2.VERSION, writer=True))
        self.write_record(writer={"version": "9.9.8", "ok": True, "checks": []})
        self.assertTrue(self.probe.passed(self.roots, al2.VERSION))
        self.assertFalse(self.probe.passed(self.roots, al2.VERSION, writer=True))
        self.write_record(writer={"version": al2.VERSION, "ok": False, "checks": []})
        self.assertTrue(self.probe.passed(self.roots, al2.VERSION))
        self.assertFalse(self.probe.passed(self.roots, al2.VERSION, writer=True))
        self.write_record(writer={"version": al2.VERSION, "ok": True, "checks": []})
        self.assertTrue(self.probe.passed(self.roots, al2.VERSION, writer=True))
        self.write_record(ok=False, writer={"version": al2.VERSION, "ok": True, "checks": []})
        self.assertFalse(self.probe.passed(self.roots, al2.VERSION, writer=True))

    def test_no_writing_type_runs_no_writers_pass(self):
        self.assertIsNone(apitypes.TYPES.get("implement"))
        for kw in ({"writer_type": None}, {}):
            seen = []

            def b_argv(shard, **k):
                seen.append(shard.type)
                return build_argv(shard, **k)
            rec = self.probe.run(claude=self.cli(), roots=self.roots, build_argv=b_argv,
                                 build_env=al2.build_env, wrap=al2.open_wrap, writer=True, **kw)
            self.assertNotIn("writer", rec)
            self.assertEqual(seen, ["explore"])
            self.assertFalse(self.probe.passed(self.roots, al2.VERSION, writer=True))
            self.assertTrue(self.probe.passed(self.roots, al2.VERSION))

    def test_ensure_without_writer_runs_no_writers_attempt(self):
        seen = []

        def b_argv(shard, **k):
            seen.append(shard.type)
            return build_argv(shard, **k)
        rec = self.probe.ensure(claude=self.cli(), roots=self.roots, build_argv=b_argv,
                                build_env=al2.build_env, wrap=al2.open_wrap)
        self.assertEqual((seen, "writer" in rec), (["explore"], False))
        with self.assertRaises(Exception) as cm:
            self.probe.ensure(claude=self.cli(), roots=self.roots, build_argv=b_argv,
                              build_env=al2.build_env, wrap=al2.open_wrap, writer=True,
                              writer_type=None)
        self.assertEqual(al2.code(cm.exception)[0], "probe.fail")
        self.assertEqual(al2.code(cm.exception)[1]["check"], "writer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
