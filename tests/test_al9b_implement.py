#!/usr/bin/python3
"""Packet al9b-implement-type: the writing type, its key, its job, its worktree and the commit.

Run as `python3 tests/test_al9b_implement.py [Class]`. Every repo is a throwaway this file makes
under its temp root, with a git identity of its own in a temp global config; every fan-out gets
stand-ins for its probe, key and started, and a run_shard that writes into the worktree as a
writer would, but RealWallTest, which runs the real `run_shard` under the real wall around a
fake CLI this file writes (it skips where no wall starts). No test starts the real claude or
tests/fake-claude, reads a key, or touches the live state root or user file. LinuxWriteTest is
the Linux machine's, skipped here with one reason.
"""
import collections
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types as pytypes
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
LIB = os.path.join(os.path.dirname(HERE), "plugin", "lib")
sys.path.insert(0, LIB)
sys.path.insert(0, HERE)
from apilane import argv as A  # noqa: E402
from apilane import cli as CLI  # noqa: E402
from apilane import config as C  # noqa: E402
from apilane import fanout as F  # noqa: E402
from apilane import hook as H  # noqa: E402
from apilane import job as J  # noqa: E402
from apilane import messages as M  # noqa: E402
from apilane import run as RUN  # noqa: E402
from apilane import runs as RUNS  # noqa: E402
from apilane import types as T  # noqa: E402
from apilane import write as W  # noqa: E402

GIT = shutil.which("git", path="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin")
KEY = "made-up-value-not-a-key-0123456789"
# The pin's (a207132) argv of each read type, and its row, role and effort, by sha256.
PIN = {"review": ("1a9450616ae05b7c11f00952f2348e0b42369abbd6ef10390ba83c8fc267d6d0",
                  "0ec8598fca24a54dd4939153aa2d9cf0c55410952180520b4974d075961b94fa"),
       "explore": ("1e33eeacdf738fabe5df76203d72a3cffa0af6fb614d5afe9864f4ecec711933",
                   "f0f0830593869b41e7e6d2430f44f8989643e9b2e79e4c8c5c8d45fd85251391"),
       "analyze": ("00befc9dce896e79d224e2bef63b5b4118f4fb2871fd2ba3890d31053a98c222",
                   "69567d47929a978cbd5fc1b3ec8e5d4b97eb503c1fb920898b32755517927d98")}
ShardResult = collections.namedtuple(
    "ShardResult", "label type state cost_usd estimated result_path reason model")


def sha(obj):
    return hashlib.sha256(json.dumps(obj).encode()).hexdigest()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def put(path, text="made-up\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    return path


class World(unittest.TestCase):
    """A temp root: a home, a git identity, a repo `proj` with hooks and an fsmonitor that each
    write a mark, and the lane's roots."""

    def setUp(self):
        if GIT is None:
            self.skipTest("no git here: no throwaway repo can be made")
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="al9b-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.home = os.path.join(self.root, "home")
        gitconfig = put(os.path.join(self.root, "gitconfig"),
                        "[user]\n\tname = made-up\n\temail = made-up@localhost\n"
                        "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n")
        env = mock.patch.dict(os.environ, {"HOME": self.home, "GIT_CONFIG_GLOBAL": gitconfig,
                                           "GIT_CONFIG_NOSYSTEM": "1"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)   # al11: the lane reads it; restored at stop
        self.repo = os.path.join(self.home, "code", "proj")
        os.makedirs(self.repo)
        put(os.path.join(self.repo, "README.md"))
        put(os.path.join(self.repo, "src", "a.txt"), "one\n")
        put(os.path.join(self.repo, ".gitignore"), "*.log\nbuild/\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", "README.md", "src/a.txt", ".gitignore")
        self.git("commit", "-q", "-m", "one")
        self.marks = os.path.join(self.root, "marks")
        os.makedirs(self.marks)
        hooks = os.path.join(self.root, "hooks")
        for name in ("pre-commit", "post-commit", "post-checkout", "commit-msg",
                     "reference-transaction", "prepare-commit-msg"):
            p = put(os.path.join(hooks, name), "#!/bin/sh\ntouch '%s/%s'\n" % (self.marks, name))
            os.chmod(p, 0o755)
        fsmon = put(os.path.join(self.root, "fsmonitor.sh"),
                    "#!/bin/sh\ntouch '%s/fsmonitor'\n" % self.marks)
        os.chmod(fsmon, 0o755)
        self.git("config", "core.hooksPath", hooks)
        self.git("config", "core.fsmonitor", fsmon)
        self.roots = pytypes.SimpleNamespace(
            home=self.home, config=os.path.join(self.home, ".config/agentik/agents/config.yaml"),
            state=os.path.join(self.home, ".local/state/agentik-agents/api"),
            store=os.path.join(self.home, ".config/agentik/agents/secrets/k.sops.yaml"))

    def git(self, *argv, cwd=None):
        p = subprocess.run([GIT, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                            "-C", cwd or self.repo] + list(argv), capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=60)
        if p.returncode != 0:
            raise AssertionError("git %s: %s" % (argv, p.stderr.decode()))
        return p.stdout.decode().strip()

    def lane(self, repos=None, **kw):
        base = dict(enabled=True, max_fanout_usd=2.0, max_day_usd=10.0, console_limit_usd=5.0,
                    proxy=None, ca_file=None,
                    write_repos=(self.repo,) if repos is None else tuple(repos))
        base.update(kw)
        return pytypes.SimpleNamespace(**base)

    def job(self, id="w1", label="fix", repo=None, frm="main", shards=None):
        return J.Job(id, 1.0, (), shards or (J.Shard(label, "implement", "make it so"),), None, 4,
                     900, None, repo or self.repo, frm)

    def no_marks(self):
        self.assertEqual(sorted(os.listdir(self.marks)), [])

    def tree_of(self, path):
        """Each entry under `path` but its `.git`, with its bytes or its link's text."""
        out = {}
        for root, dirs, files in os.walk(path):
            if root == path:
                dirs[:] = [d for d in dirs if d != ".git"]
            for n in dirs + files:
                p = os.path.join(root, n)
                rel = os.path.relpath(p, path)
                if rel == ".git":
                    continue
                if os.path.islink(p):
                    out[rel] = "link:" + os.readlink(p)
                elif os.path.isfile(p):
                    out[rel] = read_bytes(p)
                elif not os.path.isdir(p):
                    out[rel] = "special"
        return out

    def worktree(self, id="w1", frm="main"):
        """The plan and the worktree step, as the fan-out takes them."""
        w = W.plan(self.job(id=id, frm=frm), self.lane(), self.roots)
        self.assertIsNone(W.make(w))
        return w

    def settle(self, w, **kw):
        kw.setdefault("state", "ok")
        return W.settle(w, label="fix", run=w["branch"] + "-01", key=KEY, home=self.home, **kw)

    def fan(self, job, writes=None, state="ok", probe_raises=False, lane=None, **kw):
        """A fan-out with stand-ins; `writes(worktree)` is the shard's work."""
        self.calls, self.shard_kw = [], []

        def run_shard(shard, **k):
            self.calls.append("shard")
            self.shard_kw.append(k)
            run_dir = os.path.join(self.roots.state, "runs", "%s-%02d" % (k["fanout"], k["number"]))
            os.makedirs(run_dir, exist_ok=True)
            RUN._write_json(os.path.join(run_dir, "run.json"), {"id": k["fanout"] + "-01",
                                                                "type": shard.type})
            if writes:
                writes(k["write"]["worktree"])
            return ShardResult(shard.label, shard.type, state, 0.01, False, None, None, "m")

        def probe(c):
            self.calls.append("probe")
            if probe_raises:
                raise F.FanoutError("probe.fail", check="writer", detail="x")
            return {"ok": True, "restricted": None}

        def key():
            self.calls.append("key")
            return KEY

        self.events = []
        args = dict(run_shard=run_shard, wrap=lambda a, **k: list(a), key=key, ensure_probe=probe,
                    started=lambda pid: "s", emit=lambda e, **f: self.events.append((e, f)),
                    check_dirs=lambda d, home: [os.path.realpath(x) for x in d])
        args.update(kw)
        return F.run(job, lane=lane or self.lane(), roots=self.roots, session="sess-1",
                     claude="/bin/false", **args)

    def run_json(self, fid="w1"):
        with open(os.path.join(self.roots.state, "runs", fid + "-01", "run.json")) as fh:
            return json.load(fh)


# -- 1, 15: the type and its argv ---------------------------------------------------------------

class TypeTest(unittest.TestCase):
    def test_implement(self):
        t = T.TYPES["implement"]
        self.assertEqual((t.name, t.model, t.tools, t.schema, t.writes),
                         ("implement", "claude-sonnet-5-5", ("Read", "Edit"), None, True))
        self.assertEqual(T.EFFORT["implement"], "high")
        role = T.ROLES["implement"]
        for words in ("working folder", "no shell", ".git", "CLAUDE.md", "DECISIONS.md",
                      "settings.json", "hooks/", "fifty lines", "which test proves it",
                      "Read and Edit", "empty old_string", "new_string"):
            self.assertIn(words, role)

    def test_role_names_no_write_tool(self):
        """al9c W4: the role names the tools as built; `Write` is no tool of the type."""
        self.assertNotIn("Write", T.ROLES["implement"])
        self.assertNotIn("Write", T.TYPES["implement"].tools)

    def test_read_rows_are_the_pins(self):
        for name, (_argv, row) in PIN.items():
            t = T.TYPES[name]
            self.assertFalse(t.writes)
            self.assertEqual(sha([list(t)[:4], T.ROLES[name], T.EFFORT[name]]), row, name)

    def test_priced(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "plugin", "scripts"))
        import test_al1_run as al1
        prices = al1.load_prices()
        self.assertIn(T.TYPES["implement"].model, prices)
        sonnets = sorted(m for m in prices if m.startswith("claude-sonnet-"))
        self.assertEqual(T.TYPES["implement"].model, T.TYPES["review"].model)
        self.assertTrue(sonnets)


class ArgvTest(unittest.TestCase):
    def build(self, kind):
        return A.build(pytypes.SimpleNamespace(type=kind, label="l", prompt="p"),
                       claude="/opt/x/claude", dirs=["/w"], ceiling_usd=0.5, run_dir="/r")

    def test_writer(self):
        a = self.build("implement")
        flag = lambda f: a[a.index(f) + 1]   # noqa: E731
        self.assertEqual(flag("--tools"), "Read Edit")       # al9c W1
        self.assertEqual(flag("--allowedTools"), "Read Edit")
        denied = flag("--disallowedTools").split(" ")
        self.assertEqual(denied[-6:], ["Write", "Bash", "WebFetch", "WebSearch", "Agent", "Task"])
        for p in A.DENY_PATHS:
            for t in ("Read", "Edit"):
                self.assertIn("%s(%s)" % (t, p), denied)
        self.assertEqual([d for d in denied if d.startswith("Write(")], [])
        self.assertEqual(len(denied), 2 * len(A.DENY_PATHS) + 6)
        read = self.build("explore")
        strip = lambda v: [x for i, x in enumerate(v) if i == 0 or v[i - 1] not in (   # noqa: E731
            "--tools", "--allowedTools", "--disallowedTools", "--model", "--effort",
            "--append-system-prompt")]
        self.assertEqual(strip(a), strip(read))

    def test_read_argv_is_the_pins(self):
        for name, (argv, _row) in PIN.items():
            self.assertEqual(sha(self.build(name)), argv, name)


# -- 2, 4: the key ------------------------------------------------------------------------------

class KeyTest(World):
    def config(self, text):
        put(self.roots.config, text)

    def test_parses(self):
        self.config("api:\n  enabled: true\n  write_repos: [/a/b, /c]\n")
        lane = C.lane(self.roots)
        self.assertEqual(lane.write_repos, ("/a/b", "/c"))
        self.assertEqual(lane[:6], (True, 2.0, 10.0, None, None, None))
        self.assertEqual(C.DEFAULTS.write_repos, ())
        self.assertEqual(C.Lane._fields[-1], "write_repos")

    def test_refused(self):
        for value in ("[a/b]", "3", "/a/b", "[[/a]]", "[/a, 3]"):
            self.config("api:\n  enabled: true\n  write_repos: %s\n" % value)
            with self.assertRaises(C.ConfigFault) as cm:
                C.lane(self.roots)
            self.assertEqual(cm.exception.fields["line"], 3, value)

    def test_listed(self):
        import agents_plug as plug
        rows = {s["key"]: s for s in plug.api_settings(self.roots)}
        s = rows["api.write_repos"]
        self.assertEqual((s["default"], s["value"], s["type"]), ([], [], "list"))
        self.config("api:\n  enabled: true\n  write_repos: [/a/b]\n")
        s = {s["key"]: s for s in plug.api_settings(self.roots)}["api.write_repos"]
        self.assertEqual((s["value"], s["source"]["layer"], s["source"]["line"]),
                         (["/a/b"], "user", 3))


# -- 3, 7, 8, 10, 13: the job's refusals ----------------------------------------------------------

class Parts(CLI.Parts):
    def wall_backend(self):
        return "stand-in"


class JobRefusedTest(World):
    def cli(self, obj, *flags):
        out, errs = io.StringIO(), []
        with mock.patch.object(CLI, "session_id", lambda env=None: "sess-1"):
            rc = CLI.main(["fanout", "-"] + list(flags), roots=self.roots, parts=Parts(),
                          stdin=io.StringIO(json.dumps(obj)), stdout=out,
                          stderr=pytypes.SimpleNamespace(write=errs.append, flush=lambda: None))
        return rc, out.getvalue(), "".join(errs)

    def obj(self, **kw):
        base = {"id": "w1", "budget_usd": 1.0, "repo": self.repo,
                "shards": [{"label": "fix", "type": "implement", "prompt": "p"}]}
        base.update(kw)
        return base

    def test_off(self):
        before = self.tree_of(self.repo)
        for repos in ("", "  write_repos: []\n"):
            put(self.roots.config, "api:\n  enabled: true\n  max_day_usd: 0.5\n" + repos)
            rc, _out, err = self.cli(self.obj(budget_usd=5.0), "--dry-run")
            self.assertEqual(rc, 2, err)
            self.assertIn("writing type is off", err)
            self.assertIn(self.roots.config, err)
            self.assertIn("api block", err)
        self.assertFalse(os.path.exists(self.roots.state))
        self.assertEqual(self.tree_of(self.repo), before)

    def test_shape(self):
        with self.assertRaises(J.JobError) as cm:
            J.from_obj(self.obj(shards=[{"type": "implement", "prompt": "p"}] * 2))
        self.assertEqual(cm.exception.code, "write.shape")
        with self.assertRaises(J.JobError) as cm:
            J.from_obj(self.obj(shards=[{"type": "implement", "prompt": "p"},
                                        {"type": "review", "prompt": "p"}]))
        self.assertEqual(cm.exception.code, "write.shape")
        for key in ("repo", "from"):
            with self.assertRaises(J.JobError) as cm:
                J.from_obj({"budget_usd": 1, key: "x", "shards": [{"type": "review",
                                                                    "prompt": "p"}]})
            self.assertEqual((cm.exception.code, cm.exception.fields["field"]), ("job.shape", key))

    def test_repo(self):
        os.makedirs(os.path.join(self.root, "elsewhere"))
        link = os.path.join(self.root, "link")
        os.symlink(self.repo, link)
        missing = os.path.join(self.home, "code", "gone")
        sub = os.path.join(self.repo, "src")
        lane = self.lane([self.repo, missing, sub])
        for repo, why in ((os.path.join(self.root, "elsewhere"), "unlisted"), (missing, "missing"),
                          (sub, "not-top")):
            with self.assertRaises(W.WriteError) as cm:
                F.plan(self.job(repo=repo), lane=lane, roots=self.roots)
            self.assertEqual((cm.exception.code, cm.exception.fields["why"]), ("write.repo", why))
        self.assertEqual(F.plan(self.job(repo=link), lane=lane, roots=self.roots)["write"]["repo"],
                         self.repo)

    def test_from(self):
        self.git("tag", "v1")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        for frm in ("v1", "origin/main", self.git("rev-parse", "HEAD"), "nope"):
            with self.assertRaises(W.WriteError) as cm:
                F.plan(self.job(frm=frm), lane=self.lane(), roots=self.roots)
            self.assertEqual(cm.exception.code, "write.from", frm)

    def test_short(self):
        with self.assertRaises(J.JobError) as cm:
            J.from_argv(["--budget-usd", "1", "--profile", "implement", "do it"])
        self.assertEqual(cm.exception.code, "write.short")
        put(self.roots.config, "api:\n  enabled: true\n  write_repos: [%s]\n" % self.repo)
        out, errs = io.StringIO(), []
        rc = CLI.main(["fanout", "--budget-usd", "1", "--profile", "implement", "--yes", "x"],
                      roots=self.roots, parts=Parts(), stdin=io.StringIO(""), stdout=out,
                      stderr=pytypes.SimpleNamespace(write=errs.append, flush=lambda: None))
        self.assertEqual(rc, 2)
        self.assertIn("short form", "".join(errs))
        self.assertFalse(os.path.exists(self.roots.state))

    def test_taken(self):
        os.makedirs(os.path.join(self.repo, ".claude", "worktrees", "w1"))
        with self.assertRaises(W.WriteError) as cm:
            F.plan(self.job(), lane=self.lane(), roots=self.roots)
        self.assertEqual(cm.exception.code, "write.taken")
        self.git("branch", "w2")
        with self.assertRaises(W.WriteError) as cm:
            F.plan(self.job(id="w2"), lane=self.lane(), roots=self.roots)
        self.assertEqual(cm.exception.code, "write.taken")

    def test_detach_child_reads_repo_and_from(self):
        job = self.job(frm="dev")
        obj = CLI.job_obj(job)
        self.assertEqual((obj["repo"], obj["from"]), (self.repo, "dev"))
        self.assertEqual(J.from_obj(obj), job)
        read = J.Job("r1", 1.0, (), (J.Shard("a", "review", "p"),), None, 4, 900)
        self.assertNotIn("repo", CLI.job_obj(read))
        self.assertEqual(sorted(CLI.job_obj(read)), sorted(
            ["schema", "id", "tag", "budget_usd", "dirs", "shards", "max_shard_usd", "jobs",
             "timeout_sec"]))


# -- 11: the model's line -----------------------------------------------------------------------

class HookTest(World):
    def line(self, text):
        put(self.roots.config, text)
        out = io.StringIO()
        H.main("SessionStart", "{}", roots=self.roots, backend=lambda: "stand-in", out=out)
        return json.loads(out.getvalue())["hookSpecificOutput"]["additionalContext"]

    def test_sentence(self):
        on = M.say("hook.on")
        self.assertEqual(self.line("api:\n  enabled: true\n"), on)
        self.assertEqual(self.line("api:\n  enabled: true\n  write_repos: []\n"), on)
        self.assertEqual(self.line("api:\n  enabled: true\n  write_repos: [%s]\n" % self.repo),
                         on + " A writing type, implement, edits one new worktree of a listed "
                         "repo and the lane commits it on a branch of the job's id; it has no "
                         "shell and never pushes.")


# -- 12, 14, 16, 17, 25, 26, 27, 30: the fan-out's steps and the commit ----------------------------

class OrderTest(World):
    def test_probe_fails_first(self):
        with self.assertRaises(F.FanoutError):
            self.fan(self.job(), probe_raises=True)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".claude")))
        self.assertFalse(os.path.exists(os.path.join(self.roots.state, "usage.jsonl")))

    def test_worktree_fails_skips(self):
        put(os.path.join(self.repo, ".claude"), "a file where a folder goes\n")
        res = self.fan(self.job())
        self.assertEqual((res.shards[0].state, res.shards[0].reason), ("skipped", "worktree"))
        self.assertEqual(res.spent_usd, 0.0)
        self.assertEqual(self.calls, ["probe", "key"])
        self.assertEqual(res.write["commit"], "none")

    def test_order_and_dry_run(self):
        p = F.plan(self.job(), lane=self.lane(), roots=self.roots)
        text = M.plan(p, self.lane())
        tree = os.path.join(self.repo, ".claude", "worktrees", "w1")
        self.assertIn("writes %s, branch w1 from main at %s" % (tree, self.git("rev-parse", "main")),
                      text)
        self.assertFalse(os.path.exists(tree))
        seen = []
        res = self.fan(self.job(), writes=lambda t: seen.append(os.path.isdir(t)))
        self.assertEqual(seen, [True])
        self.assertEqual(self.calls, ["probe", "key", "shard"])
        self.assertEqual(res.write["commit"], "none")
        self.assertEqual(res.shards[0].state, "empty")
        self.no_marks()

    def test_git_link_refused(self):
        real = W.git

        def git(path, *args):
            out = real(path, *args)
            if args[:2] == ("worktree", "add"):
                g = os.path.join(args[2], ".git")
                os.rename(g, g + ".real")
                os.symlink(g + ".real", g)
            return out
        with mock.patch.object(W, "git", git):
            res = self.fan(self.job())
        self.assertEqual(res.shards[0].reason, "worktree")
        self.assertIn(".git is not a regular file", res.write["error"])
        self.assertNotIn("shard", self.calls)


class ShardPlacesTest(World):
    def test_wrap_call(self):
        seen = []

        def wrap(argv, **kw):
            seen.append(kw)
            return ["/bin/sh", "-c", 'pwd > "$TMPDIR/../cwd"; printf "%s"' % json.dumps(
                {"type": "result", "subtype": "success", "is_error": False,
                 "result": "made-up", "total_cost_usd": 0.0}).replace('"', '\\"')]
        w = {"repo": self.repo, "worktree": self.repo, "branch": "b", "from": "main",
             "from_sha": "0"}
        lane = self.lane()
        common = dict(grant_usd=0.5, fanout="f1", session="s", roots=self.roots, lane=lane,
                      claude="/opt/x/claude", dirs=[self.home], timeout_sec=30, wrap=wrap,
                      key=lambda: KEY)
        RUN.run_shard(J.Shard("a", "review", "p"), number=1, **common)
        RUN.run_shard(J.Shard("b", "implement", "p"), number=2, write=w, **common)
        run1 = os.path.join(self.roots.state, "runs", "f1-01")
        run2 = os.path.join(self.roots.state, "runs", "f1-02")
        self.assertEqual(seen[0], {"read": [self.home], "write": [run1], "net": "all",
                                   "home": self.home})
        self.assertEqual(seen[1], {"read": [self.home], "write": [run2, self.repo], "net": "all",
                                   "home": self.home})
        with open(os.path.join(run2, "cwd")) as fh:
            self.assertEqual(os.path.realpath(fh.read().strip()), self.repo)
        with open(os.path.join(run1, "cwd")) as fh:
            self.assertEqual(os.path.realpath(fh.read().strip()), os.path.realpath(run1))


class CommitTest(World):
    def writes(self, tree):
        put(os.path.join(tree, "README.md"), "changed\n")
        put(os.path.join(tree, "new.txt"))
        put(os.path.join(tree, "a", "b", "c", "deep.txt"))

    def test_commit(self):
        other = os.path.join(self.root, "other")
        self.git("worktree", "add", "-q", "-b", "other", other)
        before = (self.git("status", "--porcelain"), self.git("rev-parse", "HEAD"),
                  read_bytes(os.path.join(self.repo, ".git", "index")), self.tree_of(self.repo),
                  self.tree_of(other))
        res = self.fan(self.job(), writes=self.writes)
        w = res.write
        self.assertEqual(w["commit"], "ok", w)
        tree = os.path.join(self.repo, ".claude", "worktrees", "w1")
        self.assertEqual(sorted(w["paths"]), ["README.md", "a/b/c/deep.txt", "new.txt"])
        self.assertEqual(self.git("log", "-1", "--format=%B", "w1"),
                         "w1: fix\n\napi lane implement, run w1-01, state ok")
        self.assertEqual(self.git("rev-parse", "w1"), w["head"])
        self.assertEqual(self.git("rev-parse", "w1~1"), self.git("rev-parse", "main"))
        self.no_marks()
        after = (self.git("status", "--porcelain"), self.git("rev-parse", "HEAD"),
                 read_bytes(os.path.join(self.repo, ".git", "index")),
                 {k: v for k, v in self.tree_of(self.repo).items() if not k.startswith(".claude")},
                 self.tree_of(other))
        self.assertEqual(after[1:], before[1:])
        self.assertEqual(after[0], "?? .claude/")      # the worktree's own folder, nothing else
        self.assertTrue(os.path.isdir(tree))
        self.assertEqual(self.git("for-each-ref", "refs/remotes"), "")
        rec = self.run_json()
        for k in ("repo", "worktree", "branch", "from", "from_sha", "head", "paths", "ignored",
                  "commit"):
            self.assertIn(k, rec)
        line = M.shard(res.shards[0], w)
        self.assertIn("branch w1 at %s, 3 paths" % w["head"][:7], line)

    def test_line_names_check_paths_and_ignored(self):
        def writes(t):
            for rel in ("Makefile", "scripts/x", ".claude/notes", ".github/ci.yml",
                        ".gitattributes", "out.log"):
                put(os.path.join(t, rel))
        res = self.fan(self.job(), writes=writes)
        line = M.shard(res.shards[0], res.write)
        self.assertIn("read before any check: .claude/notes, .gitattributes, .github/ci.yml, "
                      "Makefile, scripts/x", line)
        self.assertIn("ignored, not committed: out.log", line)
        self.assertEqual(res.write["ignored"], ["out.log"])
        self.assertNotIn("out.log", self.git("show", "--name-only", "--format=", "w1"))
        self.assertEqual(M.say("doctor.row", name="x", value="y").strip()[:1], "x")

    def test_fix_round(self):
        self.fan(self.job(), writes=self.writes)
        res = self.fan(self.job(id="w1-2", frm="w1"), writes=lambda t: put(
            os.path.join(t, "new.txt"), "again\n"))
        self.assertEqual(res.write["commit"], "ok")
        self.assertEqual(self.git("rev-parse", "w1-2~1"), self.git("rev-parse", "w1"))
        self.no_marks()

    def test_end_states(self):
        for n, state in enumerate(("timeout", "ceiling", "failed")):
            res = self.fan(self.job(id="e%d" % n), writes=self.writes, state=state)
            self.assertEqual(res.write["commit"], "ok")
            self.assertIn("state %s" % state, self.git("log", "-1", "--format=%B", "e%d" % n))

    def test_no_identity(self):
        with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull,
                                          "GIT_AUTHOR_NAME": "", "EMAIL": ""}):
            self.git("config", "user.useConfigOnly", "true")
            res = self.fan(self.job(), writes=self.writes)
        w = res.write
        self.assertEqual(w["commit"], "refused:git")
        self.assertTrue(w["error"])
        self.assertEqual(res.shards[0].state, "ok")
        self.assertEqual(self.run_json()["error"], w["error"])
        self.assertIn("worktree left: " + w["worktree"], M.shard(res.shards[0], w))

    def test_mismatch(self):
        def step(tree, paths, message):
            put(os.path.join(tree, "extra.txt"))
            return W.commit_paths(tree, paths + ["extra.txt"], message)
        res = self.fan(self.job(), writes=self.writes,
                       settle_write=lambda w, **k: W.settle(w, commit_step=step, **k))
        w = res.write
        self.assertEqual(w["commit"], "refused:mismatch")
        self.assertIn("extra.txt", w["committed"])
        self.assertEqual(self.git("rev-parse", "w1"), w["head"])
        self.assertIn("committed", self.run_json())
        self.assertIn("refused:mismatch", M.shard(res.shards[0], w))

    def test_lane_end_on_json_and_wait(self):
        res = self.fan(self.job(), writes=self.writes)
        obj = {"shards": [dict(res.shards[0]._asdict(), write=res.write)]}
        out = io.StringIO()
        RUNS_run = {"id": "w1", "end": dict(obj, rc=0, spent_usd=0.01, budget_usd=1.0),
                    "log": None}
        CLI.show("wait", {"run": RUNS_run, "kind": "ended", "row": {"shards_ok": 1,
                                                                    "shards_failed": 0}},
                 False, 1, out, lambda s: None)
        self.assertIn("branch w1 at", out.getvalue())


class LiteralTest(World):
    def test_names(self):
        w = self.worktree()
        for name in (":(exclude)x", ":(top)y", "*"):
            put(os.path.join(w["worktree"], name))
        rec = self.settle(w)
        self.assertEqual(rec["commit"], "ok", rec)
        self.assertEqual(sorted(self.git("show", "--name-only", "--format=", "w1").split("\n")),
                         ["*", ":(exclude)x", ":(top)y"])


class RefusedTest(World):
    def refused(self, why, make, expect=None):
        w = self.worktree(id="r%d" % len(self.seen))
        self.seen.append(why)
        make(w["worktree"])
        before = self.tree_of(w["worktree"])
        rec = self.settle(w)
        self.assertEqual(rec["commit"] if why != "leak" else rec["state"], why, rec)
        self.assertEqual(self.tree_of(w["worktree"]), before)
        self.assertEqual(self.git("rev-parse", w["branch"]), w["from_sha"])
        if expect:
            for p in expect:
                self.assertIn(p, rec["refused"])
                self.assertIn(p, M.write_text(rec))
        return rec

    def setUp(self):
        super().setUp()
        self.seen = []

    def test_nested(self):
        def nested_repo(t):
            os.makedirs(os.path.join(t, "inner"))
            self.git("init", "-q", cwd=os.path.join(t, "inner"))
        for make, path in (
                (lambda t: put(os.path.join(t, "sub", ".git", "config")), "sub/.git"),
                (lambda t: put(os.path.join(t, "up", ".GIT")), "up/.GIT"),
                (lambda t: put(os.path.join(t, "s", ".git"), "gitdir: /x\n"), "s/.git"),
                (nested_repo, "inner"),
                (lambda t: put(os.path.join(t, "build", ".git", "x")), "build/.git")):
            self.refused("refused:nested", make, [path])

    def test_gated(self):
        put(os.path.join(self.home, "code", ".claude", "edit-gates"), "# made-up\nproj/locked/*\n")
        for make, path in (
                (lambda t: put(os.path.join(t, "x", "y", "CLAUDE.md")), "x/y/CLAUDE.md"),
                (lambda t: put(os.path.join(t, "DECISIONS.md")), "DECISIONS.md"),
                (lambda t: put(os.path.join(t, "cfg", "settings.json")), "cfg/settings.json"),
                (lambda t: put(os.path.join(t, "hooks", "run.sh")), "hooks/run.sh"),
                (lambda t: put(os.path.join(t, "edit-gates")), "edit-gates"),
                (lambda t: put(os.path.join(t, "locked", "a.txt")), "locked/a.txt")):
            self.refused("refused:gated", make, [path])

    def test_gated_by_the_worktrees_list(self):
        self.git("checkout", "-q", "-b", "gates")
        put(os.path.join(self.repo, ".claude", "edit-gates"), "deep/**/*.lock\n")
        self.git("add", ".claude/edit-gates")
        self.git("commit", "-q", "-m", "gates")
        w = W.plan(self.job(id="g1", frm="gates"), self.lane(), self.roots)
        self.assertIsNone(W.make(w))
        put(os.path.join(w["worktree"], "deep", "a", "b", "x.lock"))
        rec = self.settle(w)
        self.assertEqual((rec["commit"], rec["refused"]), ("refused:gated", ["deep/a/b/x.lock"]))

    def test_grammar(self):
        m = W.gate_match
        self.assertTrue(m("a/**/b", "a/b"))
        self.assertTrue(m("a/**/b", "a/x/y/b"))
        self.assertFalse(m("*.md # comment", "x.md"))     # brief 2 R3: `#` mid-line is the name's
        self.assertTrue(m("./x", "x"))
        self.assertFalse(m("*.md", "d/x.md"))
        self.assertTrue(m("[ab]?.txt", "a1.txt"))
        for line in ("/x", "~/x", "a/../x", "# x", ""):
            self.assertFalse(m(line, "x"), line)
        self.assertTrue(m("README", "readme", fold=True))
        self.assertFalse(m("README", "readme"))

    def test_kind_and_leak(self):
        target = put(os.path.join(self.root, "secret.txt"), KEY)
        self.refused("refused:kind", lambda t: os.symlink("/etc/hosts", os.path.join(t, "l")),
                     ["l"])
        self.refused("refused:kind", lambda t: os.mkfifo(os.path.join(t, "fifo")), ["fifo"])
        self.refused("refused:kind", lambda t: os.symlink(target, os.path.join(t, "k")), ["k"])
        self.refused("leak", lambda t: put(os.path.join(t, "k.txt"), "x " + KEY), ["k.txt"])
        self.refused("leak", lambda t: put(os.path.join(t, "age.txt"), "AGE-SECRET-KEY-1QQQ"),
                     ["age.txt"])

    def test_empty_and_ignored(self):
        w = self.worktree()
        rec = self.settle(w)
        self.assertEqual((rec["state"], rec["commit"]), ("empty", "none"))
        w = self.worktree(id="w2")
        put(os.path.join(w["worktree"], "x.log"))
        rec = self.settle(w)
        self.assertEqual((rec["state"], rec["commit"], rec["ignored"]), ("empty", "none",
                                                                         ["x.log"]))
        self.assertIn("ignored, not committed: x.log", M.write_text(rec))


# -- 5, 28, 29: the doctor, a lost run, the sweep -------------------------------------------------

class DoctorTest(World):
    def test_check(self):
        missing = os.path.join(self.home, "code", "gone")
        lane = self.lane([self.repo, missing, os.path.join(self.repo, "src")])
        rows = CLI.write_check(self.roots, lane)
        self.assertEqual([r.split()[-1] for r in rows[:2]], ["ok", "missing"])
        self.assertTrue(rows[2].endswith("not a repo top"))
        self.assertIn("api write", rows[0])
        parts = pytypes.SimpleNamespace(wall_backend=lambda: "x", key_present=lambda r: True,
                                        probe_read=lambda r: None)
        with mock.patch.object(CLI, "old_forward", lambda path=None: None):
            on = CLI.doctor_block(self.roots, self.lane(), parts)
            off = CLI.doctor_block(self.roots, self.lane([]), parts)
        self.assertIn("api write", on)
        self.assertNotIn("api write", off)

    def lost_run(self, writes):
        w = self.worktree()
        writes(w["worktree"])
        run_dir = os.path.join(self.roots.state, "runs", "w1-01")
        os.makedirs(run_dir)
        RUN._write_json(os.path.join(run_dir, "run.json"), dict(w, id="w1-01", state="running"))
        return w

    def test_lost(self):
        w = self.lost_run(lambda t: put(os.path.join(t, "new.txt")))
        found = W.lost(self.run_json(), home=self.home)
        self.assertEqual(found["paths"], ["new.txt"])
        self.assertEqual(len(found["lines"]), 2)
        self.assertIn(" add -- new.txt && git ", found["lines"][0])
        self.assertIn("worktree remove --force", found["lines"][1])
        left = RUNS.left(self.roots, home=self.home)
        self.assertEqual([x["worktree"] for x in left], [w["worktree"]])
        self.assertIn("worktree left: %s" % w["worktree"],
                      "\n".join(CLI.write_check(self.roots, self.lane())))
        self.assertEqual(self.git("rev-parse", "w1"), w["from_sha"])

    def test_lost_nested_prints_removal_alone(self):
        self.lost_run(lambda t: put(os.path.join(t, "sub", ".git", "x")))
        found = W.lost(self.run_json(), home=self.home)
        self.assertEqual(len(found["lines"]), 1)
        self.assertIn("worktree remove --force", found["lines"][0])

    def test_sweep_leaves_the_worktree(self):
        w = self.lost_run(lambda t: None)
        old = time.time() - 8 * 86400
        for root, dirs, files in os.walk(os.path.join(self.roots.state, "runs")):
            for n in dirs + files + [""]:
                os.utime(os.path.join(root, n), (old, old))
        RUNS.sweep(self.roots, alive=lambda *a: False)
        self.assertFalse(os.path.exists(os.path.join(self.roots.state, "runs", "w1-01")))
        self.assertTrue(os.path.isdir(w["worktree"]))
        self.assertEqual(self.git("rev-parse", "w1"), w["from_sha"])


# -- review 1's fixes (brief 2, R1 to R5) ---------------------------------------------------------

def dead_pid():
    p = subprocess.Popen(["/usr/bin/true"])
    p.wait(10)
    return p.pid


def started_of(pid):
    from apilane import proc
    return proc.started(pid) or "Thu Jan  1 00:00:00 1970"


class LeftTest(World):
    """R1 (F1) and R4 (F4): what `runs.left` and the doctor's check name."""

    def left_run(self, id, writes, pid=None):
        """A writing run's worktree and run.json; its fan-out's start.json names `pid`."""
        w = W.plan(self.job(id=id), self.lane(), self.roots)
        self.assertIsNone(W.make(w))
        writes(w["worktree"])
        self.record(id, dict(w, state="running"), pid)
        return w

    def record(self, id, rec, pid=None):
        run_dir = os.path.join(self.roots.state, "runs", id + "-01")
        os.makedirs(run_dir)
        RUN._write_json(os.path.join(run_dir, "run.json"), dict(rec, id=id + "-01"))
        pid = dead_pid() if pid is None else pid
        RUNS.write(self.roots, id, "start.json", {"pid": pid, "pid_started": started_of(pid)})

    def removal_alone(self, w):
        left = [x for x in RUNS.left(self.roots, home=self.home) if x["worktree"] == w["worktree"]]
        self.assertEqual(len(left), 1)
        self.assertTrue(left[0]["refused"])
        self.assertEqual(len(left[0]["lines"]), 1, left[0]["lines"])
        self.assertIn("worktree remove --force", left[0]["lines"][0])
        text = "\n".join(CLI.write_check(self.roots, self.lane()))
        self.assertIn("worktree left: %s" % w["worktree"], text)
        self.assertNotIn(" add -- ", text)
        self.assertIn("worktree remove --force", text)

    def test_lost_run_with_an_age_key_prints_removal_alone(self):
        w = self.left_run("lk", lambda t: put(os.path.join(t, "age.txt"), "AGE-SECRET-KEY-1QQQQ"))
        self.removal_alone(w)

    def test_settle_refused_as_leak_prints_removal_alone(self):
        w = W.plan(self.job(id="lk8"), self.lane(), self.roots)
        self.assertIsNone(W.make(w))
        put(os.path.join(w["worktree"], "notes.txt"), "x " + KEY)
        rec = self.settle(w)
        self.assertEqual(rec["state"], "leak")
        self.record("lk8", rec)
        self.removal_alone(w)

    def test_lost_scans_for_the_key_where_given(self):
        w = self.left_run("lk9", lambda t: put(os.path.join(t, "notes.txt"), "x " + KEY))
        self.assertTrue(W.lost(self.run_json("lk9"), home=self.home, key=KEY)["refused"])
        self.assertFalse(W.lost(self.run_json("lk9"), home=self.home)["refused"])
        self.assertEqual(w["branch"], "lk9")

    def test_live_run_not_left_dead_one_is(self):
        live = self.left_run("lv", lambda t: put(os.path.join(t, "half.txt")), pid=os.getpid())
        dead = self.left_run("dd", lambda t: put(os.path.join(t, "half.txt")))
        got = [x["worktree"] for x in RUNS.left(self.roots, home=self.home)]
        self.assertEqual(got, [dead["worktree"]])
        self.assertNotIn(live["worktree"], "\n".join(CLI.write_check(self.roots, self.lane())))


class FromTest(World):
    """R2 (F2): `from` is a local branch's name and nothing else."""
    cli = JobRefusedTest.cli
    obj = JobRefusedTest.obj

    def test_revisions_refused(self):
        put(os.path.join(self.repo, "two.txt"))
        self.git("add", "two.txt")
        self.git("commit", "-q", "-m", "two")
        put(self.roots.config, "api:\n  enabled: true\n  write_repos: [%s]\n" % self.repo)
        for frm in ("main~1", "main^", "main@{1}", "main^{commit}", "@{-1}", "-x"):
            with self.assertRaises(W.WriteError) as cm:
                F.plan(self.job(frm=frm), lane=self.lane(), roots=self.roots)
            self.assertEqual(cm.exception.code, "write.from", frm)
            rc, out, err = self.cli(self.obj(**{"from": frm}), "--dry-run")
            self.assertEqual(rc, 2, (frm, out, err))
            self.assertIn("is not a local branch", err)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".claude")))
        self.assertFalse(os.path.exists(self.roots.state))
        self.assertEqual(self.git("branch", "--list", "w1"), "")

    def test_branches_pass(self):
        self.git("branch", "feat/x")
        for frm in ("main", "feat/x"):
            self.assertEqual(F.plan(self.job(frm=frm), lane=self.lane(),
                                    roots=self.roots)["write"]["from_sha"],
                             self.git("rev-parse", "main"))


class GateTableTest(World):
    """R3 (F3, L2): the lane's matcher answers what the session plugin's `gated` answers for the
    file `<repo>/<rel>`, the worktree's own list read as the repo's. Each answer below is the
    session's, written out; the third column is True where the matcher at 57039b3 answered
    otherwise."""

    WORKTREE_LIST = ("docs/a#b.md\n./secret.txt\n#hash.txt\n*.md # note\n/abs.txt\n../up.txt\n"
                     "lib/*.py\ndeep/**/x.lock\nexact\n")
    ONE_UP = "gp/one.txt\n./gp/dot.txt\ngp/sub/*.txt # x\n"
    TWO_UP = "mid/gp/two.txt\ngp/two-wrong.txt\n"
    TABLE = (   # (rel, the session's answer, the pin answered otherwise)
        ("docs/a#b.md", True, True),          # review: `#` inside a line is part of the name
        ("docs/a", False, True),
        ("secret.txt", True, True),           # review: a leading `./` is stripped
        ("two.txt", True, True),              # review: a list two levels up, from that folder
        ("user.txt", True, True),             # review: the user's list, a `~/` line
        ("abs/k.txt", True, True),            # the user's list, an absolute glob
        ("rel-in-user.txt", False, True),     # the user's list: a relative line matches nothing
        ("a.md", False, True),                # `*.md # note` is one pattern
        ("#hash.txt", False, False),          # a line that starts with `#` is a comment
        ("abs.txt", False, False),
        ("up.txt", False, False),
        ("lib/x.py", True, False),
        ("lib/sub/x.py", False, False),
        ("deep/a/b/x.lock", True, False),
        ("deep/x.lock", True, False),
        ("exact", True, False),
        ("exact/more", False, False),
        ("one.txt", True, False),
        ("dot.txt", True, True),              # a leading `./` is stripped in a folder's list
        ("sub/a.txt", False, True),
        ("two-wrong.txt", False, True),       # two up is matched as `mid/gp/<rel>`
        (".claude/settings.local.json", True, True),
        ("x/y/settings.local.json", True, True),
    )

    def setUp(self):
        super().setUp()
        self.deep = os.path.join(self.home, "deep", "mid", "gp")
        put(os.path.join(self.deep, "README.md"))
        put(os.path.join(self.deep, ".claude", "edit-gates"), self.WORKTREE_LIST)
        self.git("init", "-q", "-b", "main", cwd=self.deep)
        self.git("add", "README.md", ".claude/edit-gates", cwd=self.deep)
        self.git("commit", "-q", "-m", "one", cwd=self.deep)
        put(os.path.join(self.home, "deep", "mid", ".claude", "edit-gates"), self.ONE_UP)
        put(os.path.join(self.home, "deep", ".claude", "edit-gates"), self.TWO_UP)
        put(os.path.join(self.home, ".claude", "edit-gates"),
            "~/deep/mid/gp/user.txt\n%s/deep/mid/gp/abs/*.txt\ngp/rel-in-user.txt\n" % self.home)

    def worktree_of(self, id):
        w = W.plan(self.job(id=id, repo=self.deep), self.lane([self.deep]), self.roots)
        self.assertIsNone(W.make(w))
        return w

    def test_table(self):
        self.assertGreaterEqual(len(self.TABLE), 12)
        w = self.worktree_of("t1")
        wrong = [(rel, want) for rel, want, _pin in self.TABLE
                 if bool(W.gated(w["worktree"], self.deep, self.home, [rel])) != want]
        self.assertEqual(wrong, [])

    def test_settings_local_refused(self):
        w = self.worktree_of("t2")
        put(os.path.join(w["worktree"], ".claude", "settings.local.json"), "{}\n")
        put(os.path.join(w["worktree"], "a", "b", "settings.local.json"), "{}\n")
        rec = W.settle(w, state="ok", label="fix", run="t2-01", key=KEY, home=self.home)
        self.assertEqual((rec["commit"], rec["refused"]),
                         ("refused:gated", [".claude/settings.local.json",
                                            "a/b/settings.local.json"]))


class MovedConfigTest(World):
    """al11 R1, R2: `$CLAUDE_CONFIG_DIR/edit-gates` is joined with the home's own list."""

    def answer(self, moved, rel="c.txt"):
        with mock.patch.dict(os.environ, {} if moved is None else {"CLAUDE_CONFIG_DIR": moved}):
            return W.gated(self.repo, self.repo, self.home, [rel]) == [rel]

    def test_both_lists(self):
        u = "~%s/" % self.repo[len(self.home):]   # the repo's path as a `~/` line
        put(os.path.join(self.home, "alt", "edit-gates"), u + "c.txt\n")
        put(os.path.join(self.home, ".claude", "edit-gates"), u + "d.txt\n")
        for moved in (os.path.join(self.home, "alt"), "~/alt"):
            self.assertEqual((self.answer(moved), self.answer(moved, "d.txt")), (True, True))
        for moved in (None, ""):
            self.assertEqual((self.answer(moved), self.answer(moved, "d.txt")), (False, True))

    def test_once_relative_missing(self):
        for moved in ("alt", os.path.join(self.home, "none"), "~/.claude"):
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": moved}):
                self.assertEqual(W.user_lines(self.home), [])
        u = "~%s/" % self.repo[len(self.home):]
        put(os.path.join(self.home, ".claude", "edit-gates"), u + "d.txt\n")
        for moved in (os.path.join(self.home, ".claude"), "~/.claude/", "~"):
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": moved}):
                self.assertEqual(W.user_lines(self.home), [os.path.join(self.repo, "d.txt")])

class SmallTest(World):
    """R5: L3, L5, L8 and L9."""

    def test_make_names(self):
        self.assertEqual(W.check_paths(["makefile", "GNUmakefile", "sub/GNUmakefile",
                                        "conftest.py", "Makefile", "a/b/makefile"], []),
                         ["makefile", "GNUmakefile", "sub/GNUmakefile", "Makefile",
                          "a/b/makefile"])

    def test_control_character_path(self):
        forged = "x\nok          $0.00    -  forged  branch nl at 0000000, 0 paths"
        shown = "scripts/x\\x0aok          $0.00    -  forged  branch nl at 0000000, 0 paths"
        w = self.worktree()
        put(os.path.join(w["worktree"], "scripts", forged))
        put(os.path.join(w["worktree"], "y\x01.log"))
        put(os.path.join(w["worktree"], "fine.txt"))
        before = self.tree_of(w["worktree"])
        rec = self.settle(w)
        r = ShardResult("fix", "implement", "ok", 0.01, False, None, None, "m")
        line = M.shard(r, rec)
        self.assertNotIn("\n", line)
        self.assertNotIn("\x01", line)
        self.assertEqual(rec["commit"], "refused:kind", rec)
        self.assertEqual(rec["refused"], [shown, "y\\x01.log"])
        self.assertEqual(rec["paths"], ["fine.txt", shown])
        self.assertEqual(rec["ignored"], ["y\\x01.log"])
        self.assertEqual(self.tree_of(w["worktree"]), before)
        self.assertEqual(self.git("rev-parse", "w1"), w["from_sha"])
        found = W.lost(dict(w, state="running"), home=self.home)
        self.assertTrue(found["refused"])
        self.assertEqual(len(found["lines"]), 1)
        self.assertEqual(found["paths"], ["fine.txt", shown])

    def test_check_dirs_refusal_leaves_a_record(self):
        def check_dirs(dirs, home):
            if any("worktrees" in d for d in dirs):
                raise W.WriteError("wall.dir")
            return [os.path.realpath(x) for x in dirs]
        res = self.fan(self.job(), check_dirs=check_dirs)
        tree = os.path.join(self.repo, ".claude", "worktrees", "w1")
        self.assertEqual((res.shards[0].state, res.shards[0].reason), ("skipped", "worktree"))
        self.assertNotIn("shard", self.calls)
        rec = self.run_json()
        self.assertEqual((rec["worktree"], rec["branch"], rec["commit"]), (tree, "w1", "none"))
        self.assertEqual(rec["error"], "worktree:wall.dir")
        line = M.shard(res.shards[0], res.write)
        self.assertIn("worktree left: %s, branch w1" % tree, line)
        self.assertTrue(os.path.isdir(tree))
        self.assertEqual(self.git("rev-parse", "w1"), self.git("rev-parse", "main"))

    def test_listed_linked_worktree_is_not_top(self):
        linked = os.path.join(self.home, "code", "proj-wt")
        self.git("worktree", "add", "-q", "-b", "lw", linked)
        with self.assertRaises(W.WriteError) as cm:
            F.plan(self.job(repo=linked), lane=self.lane([linked]), roots=self.roots)
        self.assertEqual((cm.exception.code, cm.exception.fields["why"]), ("write.repo", "not-top"))
        self.assertEqual(W.repo_state(linked), "not-top")
        self.assertEqual(W.repo_state(self.repo), "ok")


# -- 17 under the real wall, and 31 on Linux ------------------------------------------------------

FAKE = r'''#!%(py)s
import json, os, sys
if sys.argv[1:2] == ["--version"]:
    print("9.9.9 (Fake Code)")
    sys.exit(0)
sys.stdin.read()
def put(rel, text):
    p = os.path.join(os.getcwd(), rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)
put("README.md", "changed\n")
put("new.txt", "made-up\n")
put("a/b/c/deep.txt", "made-up\n")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 2,
                  "result": "Changed README.md; tests/x proves it.", "total_cost_usd": 0.01}))
'''


class RealWallTest(World):
    """Acceptance 17: the real run_shard under the real wall; a fake CLI writes in its cwd."""

    def setUp(self):
        super().setUp()
        import test_al2_wall as al2
        from apilane import wall
        if wall.backend() is None or (sys.platform == "darwin" and not al2.wall_starts()):
            self.skipTest("no wall starts here: the walled half stays unrun")
        self.claude = put(os.path.join(self.root, "tools", "claude"), FAKE % {"py": al2.FAKE_PY})
        os.chmod(self.claude, 0o755)

    def test_writes_and_commits(self):
        from apilane import wall
        res = self.fan(self.job(), run_shard=RUN.run_shard, wrap=wall.wrap,
                       check_dirs=wall.check_dirs)
        self.assertEqual(res.shards[0].state, "ok", self.run_json())
        self.assertEqual(res.write["commit"], "ok", res.write)
        self.assertEqual(sorted(res.write["paths"]), ["README.md", "a/b/c/deep.txt", "new.txt"])
        self.no_marks()

    def fan(self, job, **kw):
        return World.fan(self, job, **kw) if False else F.run(
            job, lane=self.lane(), roots=self.roots, session="sess-1", claude=self.claude,
            key=lambda: KEY, ensure_probe=lambda c: {"ok": True, "restricted": None},
            started=lambda pid: "s", emit=lambda e, **f: None, **kw)


SLEEPER = r'''#!%(py)s
import os, sys, time
if sys.argv[1:2] == ["--version"]:
    print("9.9.9 (Fake Code)")
    sys.exit(0)
with open(os.path.join(os.getcwd(), "started.txt"), "w") as fh:
    fh.write("started\n")
time.sleep(120)
'''


def sleepers(path):
    """The host's pids of the processes whose command line names `path`, from the host's own
    process table (/proc where there is one, else ps): never a pid a walled process wrote, since
    the Linux wall's pid namespace numbers its processes apart from the host's (al9c W5)."""
    names = {path, os.path.realpath(path)}
    found = []
    if os.path.isdir("/proc/self"):
        for n in os.listdir("/proc"):
            if not n.isdigit():
                continue
            try:
                with open("/proc/%s/cmdline" % n, "rb") as fh:
                    argv = fh.read().decode("utf-8", "replace").split("\0")
            except OSError:
                continue
            if names & set(argv):
                found.append(int(n))
        return found
    out = subprocess.run(["/bin/ps", "-axo", "pid=,command="], capture_output=True,
                         text=True).stdout
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        if names & set(cmd.split()):
            found.append(int(pid))
    return found

CHILD = r'''
import json, sys, types
sys.path.insert(0, sys.argv[1])
from apilane import fanout, job as J, run, wall
a = json.loads(sys.argv[2])
roots = types.SimpleNamespace(**a["roots"])
lane = types.SimpleNamespace(**a["lane"])
job = J.Job("k1", 1.0, (), (J.Shard("fix", "implement", "p"),), None, 4, 900, None, a["repo"], "main")
fanout.run(job, lane=lane, roots=roots, session="sess-1", claude=a["claude"], run_shard=run.run_shard,
           wrap=wall.wrap, check_dirs=wall.check_dirs, key=lambda: "made-up-value",
           ensure_probe=lambda c: {"ok": True, "restricted": None}, started=lambda pid: "s")
'''


class LinuxWriteTest(World):
    """Acceptance 31: lines 17 and 28 under bubblewrap, on the Linux machine."""

    def setUp(self):
        if not sys.platform.startswith("linux"):
            self.skipTest("the Linux wall's half: run on the Linux machine")
        super().setUp()

    def test_write_lands_in_the_worktree(self):
        case = RealWallTest("test_writes_and_commits")
        result = unittest.TestResult()
        case.run(result)
        self.assertEqual((result.errors, result.failures, result.skipped), ([], [], []))

    def test_killed_fanout_leaves_no_process(self):
        import test_al2_wall as al2
        claude = put(os.path.join(self.root, "tools", "claude"), SLEEPER % {"py": al2.FAKE_PY})
        os.chmod(claude, 0o755)
        arg = json.dumps({"roots": vars(self.roots), "lane": vars(self.lane()), "repo": self.repo,
                          "claude": claude})
        child = subprocess.Popen([sys.executable, "-c", CHILD, LIB, arg], start_new_session=True)
        mark = os.path.join(self.repo, ".claude", "worktrees", "k1", "started.txt")
        for _ in range(400):
            if os.path.exists(mark) and os.path.getsize(mark):
                break
            time.sleep(0.05)
        self.assertTrue(os.path.exists(mark), "the sleeper never started")
        self.assertNotEqual(sleepers(claude), [], "the host's table shows no sleeper")
        os.kill(child.pid, 9)
        child.wait(10)
        left = sleepers(claude)
        for _ in range(100):
            if not left:
                break
            time.sleep(0.05)
            left = sleepers(claude)
        self.assertEqual(left, [], "the killed fan-out left its sleeper running")
        self.assertEqual(self.git("rev-parse", "k1"), self.git("rev-parse", "main"))
        self.assertEqual(W.lost(self.run_json("k1"), home=self.home)["paths"], ["started.txt"])


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1] + sys.argv[1:], verbosity=1)
