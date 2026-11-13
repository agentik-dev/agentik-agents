#!/usr/bin/env python3
"""Tests for row al1: one API-lane shard, from its type to its record.

Every run here starts tests/fake-claude, linked as `claude` into a bin folder that is the
whole PATH, in a temp home; no real CLI starts, no request leaves the machine and the keys
are made up. The old wrapper's and the old fan-out's cases are ported under their old
names (claude-api-agent's tests/test-arg-handling.sh, test-flag-pinning.sh,
test-run-path.sh and test-apirun.py; claude-fanout's tests/test-fanout.py, at d8ca583).

    python3 tests/test_al1_run.py [Class]
"""
import importlib
import importlib.machinery
import importlib.util
import inspect
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import types as pytypes
import unittest

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "plugin" / "lib"))
FAKE = str((REPO / "tests" / "fake-claude").resolve())
STATUS_TOOL = REPO / "plugin" / "lib" / "claude-agents"

# Made up, and shaped like no real key.
KEY = "made-up-lane-key-7f3a9c2e"
AGE = "AGE-SECRET" + "-KEY-1MADEUPMADEUPMADEUP"
ENV_SECRETS = {
    "CLAUDE_CODE_OAUTH_TOKEN": "made-up-oauth-41d2",
    "ANTHROPIC_AUTH_TOKEN": "made-up-auth-93be",
    "GH_TOKEN": "made-up-gh-58c1",
    "AWS_SECRET_ACCESS_KEY": "made-up-aws-0d7e",
    "NPM_TOKEN": "made-up-npm-c6a4",
    "OPENAI_API_KEY": "made-up-other-2f90",
}
PROMPT_SECRET = "made-up-prompt-secret-e81b"
SECRETS = [KEY] + list(ENV_SECRETS.values()) + [PROMPT_SECRET]


def mod(name):
    return importlib.import_module("apilane." + name)


def load_prices():
    loader = importlib.machinery.SourceFileLoader("al1_status_tool", str(STATUS_TOOL))
    spec = importlib.util.spec_from_loader("al1_status_tool", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m.PRICES


def unpriced(types_map, prices):
    return sorted(n for n, t in types_map.items() if t.model not in prices)


class Patched:
    """os.environ with some names set for the length of a with block."""

    def __init__(self, **values):
        self.values = values
        self.saved = {}

    def __enter__(self):
        for k, v in self.values.items():
            self.saved[k] = os.environ.get(k)
            os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class World(unittest.TestCase):
    """A temp home with a bin folder holding only `claude`, a job dir and a state root."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="al1-"))
        self.home = os.path.join(self.root, "home")
        self.bin = os.path.join(self.root, "bin")
        self.work = os.path.join(self.root, "work")
        for d in (self.home, self.bin, self.work):
            os.makedirs(d)
        os.symlink(FAKE, os.path.join(self.bin, "claude"))
        with open(os.path.join(self.work, "a.py"), "w") as f:
            f.write("print('a')\n")
        self.roots = pytypes.SimpleNamespace(
            home=self.home,
            config=os.path.join(self.home, ".config/agentik/agents/config.yaml"),
            state=os.path.join(self.home, ".local/state/agentik-agents/api"),
            store=os.path.join(self.home, ".config/agentik/agents/secrets/k.sops.yaml"))
        self.lane = pytypes.SimpleNamespace(
            enabled=True, max_fanout_usd=2.0, max_day_usd=10.0, console_limit_usd=None,
            proxy=None, ca_file=None)
        self.rec = os.path.join(self.root, "record.json")
        self.key_calls = 0
        self.wraps = []

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def key(self):
        self.key_calls += 1
        return KEY

    def stand_in(self, argv, **kw):
        self.wraps.append((list(argv), kw))
        return list(argv)

    def run_mode(self, mode, *, type="explore", extra="", wrap=None, timeout=30,
                 grant=0.5, number=1, restricted=True, label=None):
        run = mod("run")
        claude = mod("argv").find_claude(self.bin)
        prompt = "fake-mode: %s\nfake-record: %s\n%s" % (mode, self.rec, extra)
        shard = pytypes.SimpleNamespace(label=label or ("shard " + mode), type=type,
                                        prompt=prompt)
        return run.run_shard(
            shard, grant_usd=grant, fanout="f1", number=number, session="sess-1",
            roots=self.roots, lane=self.lane, claude=claude, dirs=[self.work],
            timeout_sec=timeout, restricted=restricted, wrap=wrap or self.stand_in,
            key=self.key)

    def run_dir(self, number=1):
        return os.path.join(self.roots.state, "runs", "f1-%02d" % number)

    def run_json(self, number=1):
        with open(os.path.join(self.run_dir(number), "run.json")) as f:
            return json.load(f)

    def record(self):
        if not os.path.exists(self.rec):
            return None
        with open(self.rec) as f:
            return json.load(f)

    def files_under(self, top):
        out = []
        for d, dirs, files in os.walk(top):
            out += [os.path.join(d, x) for x in dirs + files]
        return out


class TypesTest(unittest.TestCase):
    def test_three_types(self):
        t = mod("types").TYPES
        self.assertEqual(sorted(t), ["analyze", "explore", "review"])
        for name, ty in t.items():
            self.assertEqual(ty.name, name)
            self.assertEqual(ty.tools, ("Read", "Grep", "Glob"))
        self.assertEqual(t["review"].model, "claude-sonnet-5-5")
        self.assertEqual(t["explore"].model, "claude-sonnet-5-5")
        self.assertEqual(t["analyze"].model, "claude-opus-5-5")
        self.assertIsNotNone(t["review"].schema)
        self.assertIsNone(t["explore"].schema)
        self.assertIsNone(t["analyze"].schema)
        schema = json.loads(t["review"].schema)
        self.assertEqual(schema["required"], ["summary", "findings"])

    def test_each_model_is_priced(self):
        prices = load_prices()
        self.assertEqual(unpriced(mod("types").TYPES, prices), [])

    def test_unpriced_type_fails_the_same_check(self):
        tmod = mod("types")
        made_up = dict(tmod.TYPES)
        made_up["guess"] = tmod.Type("guess", "claude-made-up-9", tmod.TOOLS, None)
        self.assertEqual(unpriced(made_up, load_prices()), ["guess"])

    def test_no_writing_type(self):
        for ty in mod("types").TYPES.values():
            self.assertFalse({"Bash", "Edit", "Write"} & set(ty.tools))

    def test_role_prompts_came_back(self):
        tmod = mod("types")
        self.assertIn("reviewing code read-only", tmod.ROLES["review"])
        self.assertIn("investigating a codebase read-only", tmod.ROLES["explore"])
        self.assertIn("analyzing a system read-only", tmod.ROLES["analyze"])
        self.assertEqual(tmod.EFFORT, {"review": "medium", "explore": "low", "analyze": "high"})


class ArgvTest(World):
    def build(self, type="review", **kw):
        a = mod("argv")
        shard = pytypes.SimpleNamespace(label="l", type=type,
                                        prompt=kw.pop("prompt", "ordinary prompt text"))
        args = dict(claude="/opt/x/claude", dirs=[self.work], ceiling_usd=0.5 / 1.35,
                    run_dir=os.path.join(self.root, "run"))
        args.update(kw)
        return a.build(shard, **args)

    def value(self, argv, flag):
        return argv[argv.index(flag) + 1]

    def test_claude_first_bare_second(self):
        argv = self.build()
        self.assertEqual(argv[:2], ["/opt/x/claude", "--bare"])

    def test_signature_has_no_pass_through(self):
        params = list(inspect.signature(mod("argv").build).parameters)
        self.assertEqual(params, ["shard", "claude", "dirs", "ceiling_usd", "run_dir",
                                  "restricted"])
        for extra in ("claude_arg", "out", "phase", "stagger_sec", "model"):
            with self.assertRaises(TypeError):
                self.build(**{extra: "x"})

    def test_new_flags(self):
        argv = self.build()
        self.assertEqual(self.value(argv, "--permission-prompts"), "none")
        self.assertIn("--no-session-persistence", argv)
        self.assertIn("--restricted", argv)

    def test_restricted_false_drops_only_restricted(self):
        on = self.build()
        off = self.build(restricted=False)
        self.assertEqual([x for x in on if x != "--restricted"], off)
        self.assertEqual(len(on), len(off) + 1)

    def test_no_argument_holds_the_key(self):
        with Patched(ANTHROPIC_API_KEY=KEY, **ENV_SECRETS):
            for t in ("review", "explore", "analyze"):
                for a in self.build(type=t):
                    for s in [KEY] + list(ENV_SECRETS.values()):
                        self.assertNotIn(s, a)
                    self.assertNotIn("ANTHROPIC_BASE_URL", a)

    # test-arg-handling.sh, "post-assembly invariant + profile defaults"
    def test_each_type_emits_tools_read_grep_glob(self):
        for t in ("review", "explore", "analyze"):
            self.assertEqual(self.value(self.build(type=t), "--tools"), "Read Grep Glob")

    def test_review_emits_the_six_invariant_flags(self):
        argv = self.build()
        for f in ("--tools", "--allowedTools", "--disallowedTools", "--permission-mode",
                  "--max-budget-usd", "--output-format"):
            self.assertGreaterEqual(argv.count(f), 1, f)
        self.assertEqual(self.value(argv, "--permission-mode"), "dontAsk")

    def test_explore_profile_emits_its_defaults(self):
        self.assertEqual(self.value(self.build(type="explore"), "--effort"), "low")

    def test_models_and_schema(self):
        tmod = mod("types")
        for t in ("review", "explore", "analyze"):
            argv = self.build(type=t)
            self.assertEqual(self.value(argv, "--model"), tmod.TYPES[t].model)
            self.assertEqual(self.value(argv, "--append-system-prompt"), tmod.ROLES[t])
        self.assertEqual(self.value(self.build(), "--json-schema"), tmod.TYPES["review"].schema)
        self.assertNotIn("--json-schema", self.build(type="explore"))

    def test_deny_rules(self):
        deny = self.value(self.build(), "--disallowedTools").split(" ")
        for rule in ("Read(~/.ssh/**)", "Grep(~/.ssh/**)", "Glob(~/.ssh/**)",
                     "Read(~/.claude.json)", "Read(~/.config/sops/**)", "Glob(//proc/**)",
                     "Read(~/.aws/**)", "Read(~/.config/gh/**)", "Read(~/.claude/**)"):
            self.assertIn(rule, deny)
        self.assertEqual(len(deny), 3 * len(mod("argv").DENY_PATHS))

    # "redundant --output-format json does not duplicate the flag"; "child still sees json"
    def test_output_format_json_once(self):
        argv = self.build()
        self.assertEqual(argv.count("--output-format"), 1)
        self.assertEqual(self.value(argv, "--output-format"), "json")

    # B4: "profile ceiling present on a normal run"
    def test_ceiling_present(self):
        argv = self.build(ceiling_usd=0.5 / 1.35)
        self.assertEqual(argv.count("--max-budget-usd"), 1)
        self.assertEqual(self.value(argv, "--max-budget-usd"), "%.4f" % (0.5 / 1.35))

    def test_one_add_dir_a_dir(self):
        other = os.path.join(self.root, "other")
        argv = self.build(dirs=[self.work, other])
        pairs = [argv[i + 1] for i, a in enumerate(argv) if a == "--add-dir"]
        self.assertEqual(pairs, [self.work, other])

    # B2 and "the prompt never appears in the child's argv"
    def test_prompt_never_in_argv(self):
        for p in ("ordinary prompt text", "--dangerously-skip-permissions"):
            self.assertNotIn(p, self.build(prompt=p))

    # value rules: "refuses a leading-dash flag value", "refuses a non-numeric --max-budget-usd"
    def test_value_rules(self):
        with self.assertRaises(ValueError):
            self.build(dirs=["-rf"])
        with self.assertRaises(ValueError):
            self.build(dirs=["relative/dir"])
        for bad in ("0.5", float("nan"), float("inf"), -1.0, None):
            with self.assertRaises(ValueError):
                self.build(ceiling_usd=bad)
        with self.assertRaises(ValueError):
            self.build(type="write")

    # "profile role prompt states the real toolset (Read alone, Grep/Glob absent)"
    def test_role_prompt_states_the_real_toolset(self):
        role = self.value(self.build(type="analyze"), "--append-system-prompt")
        self.assertIn("Grep and Glob do", role)
        self.assertNotIn("exactly Read, Grep, and Glob", role)

    # test-flag-pinning.sh, held on the built argv (the CLI's own --help is the probe's)
    def test_flag_pins(self):
        argv = self.build()
        flags = [a for a in argv[1:] if a.startswith("--")]
        for f in ("--model", "--effort", "--max-budget-usd", "--add-dir", "--tools"):
            self.assertIn(f, argv)
            self.assertFalse(self.value(argv, f).startswith("-"), f)
        i = argv.index("--print")
        self.assertTrue(i + 1 == len(argv) or argv[i + 1].startswith("--"),
                        "--print is boolean: the prompt is stdin")
        for f in ("--dangerously-skip-permissions", "--settings", "--agents",
                  "--fallback-model", "--claude-arg", "-p"):
            self.assertNotIn(f, argv)
        for f in set(flags) - {"--add-dir"}:
            self.assertEqual(flags.count(f), 1, "%s once: first-wins cannot be contested" % f)


class FindClaudeTest(World):
    def test_link_resolves_to_its_target(self):
        target_dir = os.path.join(self.root, "real")
        os.makedirs(target_dir)
        target = os.path.join(target_dir, "claude-1.2.3")
        shutil.copy(FAKE, target)
        os.chmod(target, 0o755)
        links = os.path.join(self.root, "links")
        os.makedirs(links)
        os.symlink(target, os.path.join(links, "claude"))
        self.assertEqual(mod("argv").find_claude(links), target)

    def test_folder_and_non_executable_are_passed_over(self):
        d1 = os.path.join(self.root, "d1")
        os.makedirs(os.path.join(d1, "claude"))
        d2 = os.path.join(self.root, "d2")
        os.makedirs(d2)
        with open(os.path.join(d2, "claude"), "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(os.path.join(d2, "claude"), 0o644)
        path = os.pathsep.join([d1, d2, self.bin])
        self.assertEqual(mod("argv").find_claude(path), FAKE)

    def test_none_found_raises_claude_none(self):
        a = mod("argv")
        empty = os.path.join(self.root, "empty")
        os.makedirs(empty)
        with self.assertRaises(Exception) as cm:
            a.find_claude(empty)
        self.assertEqual(cm.exception.code, "claude.none")
        self.assertEqual(cm.exception.fields, {"path": empty})
        self.assertEqual(str(cm.exception), "claude.none")

    def test_default_is_the_process_path(self):
        with Patched(PATH=self.bin):
            self.assertEqual(mod("argv").find_claude(), FAKE)


class EnvTest(World):
    BASE = {"PATH", "HOME", "LANG", "TERM", "TMPDIR", "CLAUDE_CONFIG_DIR",
            "ANTHROPIC_API_KEY"}

    def build(self, **kw):
        args = dict(key=KEY, run_dir=os.path.join(self.root, "run"), home=self.home,
                    path=self.bin)
        args.update(kw)
        return mod("env").build(**args)

    def test_caller_tokens_never_arrive(self):
        with Patched(ANTHROPIC_BASE_URL="http://made-up.invalid", NODE_OPTIONS="--require x",
                     NODE_EXTRA_CA_CERTS="/made/up.pem", **ENV_SECRETS):
            e = self.build()
        self.assertEqual(set(e), self.BASE)
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                     "NODE_OPTIONS", "NODE_EXTRA_CA_CERTS"):
            self.assertNotIn(name, e)
        for v in ENV_SECRETS.values():
            self.assertNotIn(v, e.values())

    def test_the_allow_list(self):
        rd = os.path.join(self.root, "run")
        e = self.build()
        self.assertEqual(e["ANTHROPIC_API_KEY"], KEY)
        self.assertEqual(e["HOME"], self.home)
        self.assertEqual(e["PATH"], self.bin)
        self.assertTrue(e["TMPDIR"].startswith(rd + os.sep))
        self.assertTrue(e["CLAUDE_CONFIG_DIR"].startswith(rd + os.sep))

    def test_base_url_only_when_given(self):
        self.assertNotIn("ANTHROPIC_BASE_URL", self.build())
        e = self.build(base_url="http://127.0.0.1:9")
        self.assertEqual(e["ANTHROPIC_BASE_URL"], "http://127.0.0.1:9")
        self.assertEqual(set(e), self.BASE | {"ANTHROPIC_BASE_URL"})

    def test_proxy_and_ca_when_given(self):
        e = self.build(proxy="http://proxy.invalid:8080", ca_file="/made/up/ca.pem")
        self.assertEqual(e["HTTPS_PROXY"], "http://proxy.invalid:8080")
        self.assertEqual(e["https_proxy"], "http://proxy.invalid:8080")
        self.assertEqual(e["NODE_EXTRA_CA_CERTS"], "/made/up/ca.pem")


class ClassifyTest(World):
    def envelope(self, **kw):
        e = {"type": "result", "subtype": "success", "is_error": False,
             "terminal_reason": "completed", "total_cost_usd": 0.1, "num_turns": 4}
        e.update(kw)
        return e

    GOOD = {"summary": "A substantive summary of what the review actually found, "
                       "long enough to clear the substance threshold.",
            "findings": [{"file": "a.py", "line": 1, "severity": "low",
                          "issue": "A concrete and adequately described problem statement."}]}
    DEGENERATE = {"summary": "test", "findings": [{"file": "a", "severity": "low",
                                                   "issue": "test"}]}

    def c(self, env, rc=0, structured=True):
        return mod("classify").classify(env, rc, [self.work], structured)

    # test-fanout.py, "result classification"
    def test_substantive_result_ok(self):
        self.assertEqual(self.c(self.envelope(structured_output=self.GOOD))[0], "ok")

    def test_placeholder_result_degenerate(self):
        st, reasons = self.c(self.envelope(structured_output=self.DEGENERATE))
        self.assertEqual(st, "degenerate")
        self.assertTrue(reasons, "degenerate shard explains why")

    def test_api_error_is_error(self):
        st, reasons = self.c(self.envelope(is_error=True, terminal_reason="api_error",
                                           result="Invalid API key"), rc=1)
        self.assertEqual(st, "error")
        self.assertIn("api_error", " ".join(reasons))

    def test_ceiling_trip_budget_exhausted(self):
        env = self.envelope(is_error=True, subtype="error_max_budget_usd",
                            terminal_reason="budget_exhausted", result="")
        self.assertEqual(self.c(env, rc=1)[0], "budget_exhausted")

    def test_non_json_unparseable(self):
        self.assertEqual(self.c(None, rc=1)[0], "unparseable")

    def test_missing_structured_output_degenerate(self):
        self.assertEqual(self.c(self.envelope())[0], "degenerate")

    # "result validation rejects only genuine non-answers"
    def test_v1_clean_answer_accepted(self):
        so = {"summary": "No actionable defects found.", "findings": []}
        self.assertEqual(self.c(self.envelope(structured_output=so))[0], "ok")

    def test_v2_one_terse_finding_does_not_poison(self):
        good = {"file": "a.py", "issue": "a concrete and adequately described problem statement"}
        so = {"summary": "Nineteen findings across the reader.",
              "findings": [good] * 18 + [{"file": "a.py", "issue": "race"}]}
        self.assertEqual(self.c(self.envelope(structured_output=so))[0], "ok")

    def test_genuine_placeholder_still_rejected(self):
        self.assertEqual(self.c(self.envelope(structured_output=self.DEGENERATE))[0],
                         "degenerate")

    # the four validators, as they were
    def test_validators(self):
        cl = mod("classify")
        for t in ("", "test", "TODO.", "a", "--", "...", "lorem ipsum"):
            self.assertTrue(cl._looks_placeholder(t), t)
        for t in ("deadlock", "use-after-free", "TOCTOU"):
            self.assertFalse(cl._looks_placeholder(t), t)
        self.assertTrue(cl._resolve_finding_path("a.py:12", [self.work]))
        self.assertTrue(cl._resolve_finding_path(os.path.join(self.work, "a.py"), [self.work]))
        self.assertFalse(cl._resolve_finding_path("/etc/passwd", [self.work]))
        self.assertFalse(cl._resolve_finding_path("", [self.work]))
        self.assertEqual(cl.validate_prose(""), (False, ["result is empty"]))
        self.assertEqual(cl.validate_prose("bin/tool:78"), (True, []))
        self.assertEqual(cl.validate_structured([], [self.work])[0], False)
        ok, why = cl.validate_structured({"summary": "x" * 50, "findings": "no"}, [self.work])
        self.assertEqual((ok, why), (False, ["findings is not a list"]))

    # the named states, never ok
    def v(self, env, rc=0, structured=True, raw=None, key=KEY):
        raw = json.dumps(env) if raw is None else raw
        return mod("classify").verdict(env, rc, [self.work], structured, raw=raw, key=key)

    def test_named_states(self):
        self.assertEqual(self.v(self.envelope(structured_output=self.GOOD)), ("ok", None))
        self.assertEqual(self.v(self.envelope(result=""), structured=False),
                         ("empty", "invalid:empty"))
        self.assertEqual(self.v(self.envelope(result="test"), structured=False),
                         ("placeholder", "invalid:placeholder"))
        self.assertEqual(self.v(self.envelope(structured_output=self.DEGENERATE))[0],
                         "placeholder")
        no_cite = {"summary": "A real summary of a real review of the reader.",
                   "findings": [{"file": "nowhere.py", "issue": "a described problem"}]}
        self.assertEqual(self.v(self.envelope(structured_output=no_cite)),
                         ("placeholder", "invalid:citations"))
        abort = self.envelope(is_error=True, terminal_reason="budget_exhausted", result="")
        self.assertEqual(self.v(abort, rc=1), ("ceiling", None))
        self.assertEqual(self.v(None, rc=3, raw=""), ("failed", "exit:3"))
        self.assertEqual(self.v(self.envelope(is_error=True, result="x"), rc=1),
                         ("failed", "exit:1"))

    def test_leak(self):
        cl = mod("classify")
        for secret in (KEY, AGE, AGE.lower()):
            env = self.envelope(result="Here it is: " + secret)
            got = self.v(env, structured=False)
            self.assertEqual(got[0], "leak")
            self.assertNotIn(secret, repr(got))
            self.assertTrue(cl.holds_secret("x" + secret + "y", KEY))
        self.assertFalse(cl.holds_secret("an ordinary answer", KEY))
        got = self.v(None, rc=0, raw="garbage " + KEY)
        self.assertEqual(got[0], "leak")
        self.assertNotIn(KEY, repr(got))


class ProcTest(unittest.TestCase):
    def test_this_process(self):
        p = mod("proc")
        s = p.started(os.getpid())
        self.assertTrue(s)
        self.assertTrue(p.alive(os.getpid(), s))
        self.assertFalse(p.alive(os.getpid(), "Mon Jan  1 00:00:00 2001"))
        self.assertFalse(p.alive(os.getpid(), None))

    def test_an_exited_pid_is_not_alive(self):
        p = mod("proc")
        child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                                 stdin=subprocess.PIPE)
        s = p.started(child.pid)
        self.assertTrue(s)
        self.assertTrue(p.alive(child.pid, s))
        child.stdin.close()
        child.wait()
        self.assertIsNone(p.started(child.pid))
        self.assertFalse(p.alive(child.pid, s))

    def test_no_such_pid(self):
        p = mod("proc")
        self.assertIsNone(p.started(0))
        self.assertIsNone(p.started(-5))
        self.assertFalse(p.alive(0, "x"))


class RunTest(World):
    def test_ok_with_the_envelopes_cost(self):
        r = self.run_mode("cost")
        self.assertEqual((r.state, r.cost_usd, r.estimated, r.reason),
                         ("ok", 0.0421, False, None))
        self.assertEqual((r.label, r.type, r.model), ("shard cost", "explore",
                                                      "claude-sonnet-5-5"))
        self.assertEqual(r.result_path, os.path.join(self.run_dir(), "result.json"))
        self.assertEqual(self.key_calls, 1)
        argv, kw = self.wraps[0]
        self.assertEqual(kw, {"read": [self.work], "write": [self.run_dir()], "net": "all",
                              "home": self.home})
        rec = self.record()
        self.assertEqual(rec["argv"][1:], argv[1:])
        self.assertEqual(argv[0], FAKE)
        self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "%.4f" % (0.5 / 1.35))
        self.assertEqual(rec["env"]["ANTHROPIC_API_KEY"], KEY)
        self.assertNotEqual(rec["pgid"], os.getpgid(0), "the child has its own group")

    def test_review_cites_a_file_under_the_dirs(self):
        r = self.run_mode("cost", type="review")
        self.assertEqual((r.state, r.reason), ("ok", None))

    def test_no_cost_books_the_grant(self):
        r = self.run_mode("nocost", grant=0.3)
        self.assertEqual((r.state, r.cost_usd, r.estimated, r.reason),
                         ("ok", 0.3, True, "no-cost"))

    def test_nan_cost_books_the_grant(self):
        r = self.run_mode("nan", grant=0.3)
        self.assertEqual((r.cost_usd, r.estimated), (0.3, True))

    def test_the_abort_is_ceiling(self):
        r = self.run_mode("abort")
        self.assertEqual((r.state, r.cost_usd, r.estimated, r.result_path),
                         ("ceiling", 0.0117, False, None))
        self.assertFalse(os.path.exists(os.path.join(self.run_dir(), "result.json")))

    def test_the_sleeper_is_timeout_and_its_group_is_gone(self):
        t0 = time.time()
        r = self.run_mode("sleep", timeout=1, grant=0.4)
        self.assertLess(time.time() - t0, 20)
        self.assertEqual((r.state, r.reason, r.cost_usd, r.estimated),
                         ("timeout", "timeout:1", 0.4, True))
        rec = self.record()
        gone = False
        for _ in range(50):
            try:
                os.killpg(rec["pgid"], 0)
            except ProcessLookupError:
                gone = True
                break
            except PermissionError:
                pass
            time.sleep(0.1)
        self.assertTrue(gone, "the shard's process group is gone")
        self.assertIsNone(mod("proc").started(rec["grandchild"]))

    def test_a_wall_that_exits_65_is_wall(self):
        r = self.run_mode("cost", wrap=lambda argv, **kw: ["/bin/sh", "-c", "exit 65"])
        self.assertEqual((r.state, r.reason), ("wall", "wall:65"))
        self.assertIsNone(self.record(), "the fake recorded no call")

    def test_a_wrapper_that_does_not_exist_is_wall(self):
        r = self.run_mode("cost", wrap=lambda argv, **kw: [os.path.join(self.root, "nope")])
        self.assertEqual((r.state, r.cost_usd, r.estimated), ("wall", 0.0, False))
        self.assertIsNone(self.record())

    # test-run-path.sh, "exit-code fidelity"; test-apirun.py, "a crash: no result event"
    def test_exit_codes_pass_through(self):
        r = self.run_mode("crash")
        self.assertEqual((r.state, r.reason), ("failed", "exit:3"))
        self.assertEqual(self.run_json()["rc"], 3)
        self.assertEqual(self.run_json()["state"], "failed")
        r = self.run_mode("garbage", number=2)
        self.assertEqual((r.state, r.reason), ("failed", "exit:7"))
        self.assertEqual(self.run_json(2)["rc"], 7)

    def test_api_error_is_failed(self):
        r = self.run_mode("error")
        self.assertEqual((r.state, r.reason), ("failed", "exit:1"))

    def test_named_states_on_the_fake(self):
        self.assertEqual(self.run_mode("empty").state, "empty")
        self.assertEqual(self.run_mode("placeholder", number=2).state, "placeholder")
        self.assertEqual(self.run_mode("placeholder", type="review", number=3).state,
                         "placeholder")

    def test_echoed_key_is_leak(self):
        r = self.run_mode("echo")
        self.assertEqual((r.state, r.result_path), ("leak", None))
        self.assertNotIn(KEY, repr(r))
        self.assertFalse(os.path.exists(os.path.join(self.run_dir(), "result.json")))

    # B2: "flag-shaped prompt is absent from argv / delivered verbatim on stdin / runs"
    def test_flag_shaped_prompt_on_stdin(self):
        r = self.run_mode("cost", extra="--dangerously-skip-permissions")
        rec = self.record()
        self.assertEqual(r.state, "ok")
        self.assertNotIn("--dangerously-skip-permissions", rec["argv"])
        self.assertTrue(rec["stdin"].endswith("\n--dangerously-skip-permissions"))

    def test_restricted_goes_to_the_argv(self):
        self.run_mode("cost", restricted=False)
        self.assertNotIn("--restricted", self.record()["argv"])
        self.run_mode("cost", number=2)
        self.assertIn("--restricted", self.record()["argv"])

    # test-run-path.sh, "interpreter hooks are stripped"
    def test_child_env_is_the_allow_list(self):
        with Patched(NODE_OPTIONS="--require x", NODE_EXTRA_CA_CERTS="/x.pem",
                     ANTHROPIC_BASE_URL="http://made-up.invalid", **ENV_SECRETS):
            self.run_mode("cost")
        env = self.record()["env"]
        for name in ("NODE_OPTIONS", "NODE_EXTRA_CA_CERTS", "ANTHROPIC_BASE_URL") + tuple(
                ENV_SECRETS):
            self.assertNotIn(name, env)
        self.assertEqual(env["HOME"], self.home)
        self.assertTrue(env["TMPDIR"].startswith(self.run_dir() + os.sep))

    def test_lane_proxy_reaches_the_child(self):
        self.lane.proxy = "http://proxy.invalid:3128"
        self.run_mode("cost")
        self.assertEqual(self.record()["env"]["HTTPS_PROXY"], "http://proxy.invalid:3128")


class SecretsTest(World):
    MODES = [("cost", {}), ("nocost", {}), ("abort", {}), ("sleep", {"timeout": 1}),
             ("echo", {}), ("empty", {}), ("placeholder", {"type": "review"}),
             ("crash", {}), ("wall", {})]

    def test_eight_secrets_nowhere(self):
        self.assertEqual(len(set(SECRETS)), 8)
        with Patched(**ENV_SECRETS):
            for n, (mode, kw) in enumerate(self.MODES, 1):
                if os.path.exists(self.rec):
                    os.unlink(self.rec)
                if mode == "wall":
                    kw = dict(wrap=lambda argv, **k: ["/bin/sh", "-c", "exit 65"])
                r = self.run_mode("cost" if mode == "wall" else mode, number=n,
                                  extra=PROMPT_SECRET, **kw)
                for s in SECRETS:
                    self.assertNotIn(s, repr(r), mode)
                rec = self.record()
                if rec:
                    for s in SECRETS:
                        for a in rec["argv"]:
                            self.assertNotIn(s, a, mode)
                    for name in ENV_SECRETS:
                        self.assertNotIn(name, rec["env"], mode)
                for path in self.files_under(self.roots.state):
                    if os.path.isfile(path):
                        with open(path, "rb") as f:
                            body = f.read()
                        for s in SECRETS:
                            self.assertNotIn(s.encode(), body, "%s: %s" % (mode, path))


class RecordTest(World):
    START = {"schema", "id", "pid", "pid_started", "type", "model", "label", "session",
             "fanout", "grant_usd", "started", "state"}
    END = START | {"rc", "ended", "cost_usd"}

    def test_run_json_at_the_start_and_at_the_end(self):
        box = {}
        th = threading.Thread(target=lambda: box.setdefault(
            "r", self.run_mode("sleep", timeout=3, grant=0.25)))
        th.start()
        path = os.path.join(self.run_dir(), "run.json")
        mid = None
        for _ in range(100):
            if os.path.exists(path):
                with open(path) as f:
                    mid = json.load(f)
                ino_mid = os.stat(path).st_ino
                break
            time.sleep(0.05)
        self.assertIsNotNone(mid)
        self.assertEqual(set(mid), self.START)
        self.assertEqual((mid["schema"], mid["id"], mid["state"], mid["grant_usd"]),
                         ("agentik.api.run/1", "f1-01", "running", 0.25))
        self.assertEqual((mid["session"], mid["fanout"], mid["type"], mid["model"]),
                         ("sess-1", "f1", "explore", "claude-sonnet-5-5"))
        self.assertTrue(mid["started"].endswith("Z"))
        self.assertTrue(mod("proc").alive(mid["pid"], mid["pid_started"]),
                        "mid-run: run.json's pid is the live child's")
        th.join(30)
        end = self.run_json()
        self.assertEqual(set(end), self.END)
        self.assertEqual((end["state"], end["cost_usd"]), ("timeout", 0.25))
        self.assertTrue(end["ended"].endswith("Z"))
        self.assertIsInstance(end["rc"], int)
        self.assertNotEqual(ino_mid, os.stat(path).st_ino, "the end is one rename")
        self.assertEqual(box["r"].state, "timeout")

    def test_modes(self):
        self.run_mode("cost")
        self.assertEqual(stat.S_IMODE(os.stat(self.roots.state).st_mode), 0o700)
        for path in [os.path.join(self.roots.state, "runs")] + self.files_under(
                os.path.join(self.roots.state, "runs")):
            want = 0o700 if os.path.isdir(path) else 0o600
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), want, path)
        names = sorted(os.listdir(self.run_dir()))
        self.assertIn("run.json", names)
        self.assertIn("result.json", names)
        self.assertIn("stderr.txt", names)

    def test_no_prompt_or_result_text_in_run_json(self):
        self.run_mode("cost", extra=PROMPT_SECRET)
        with open(os.path.join(self.run_dir(), "run.json")) as f:
            body = f.read()
        for s in (PROMPT_SECRET, "fake-mode", "The answer is", KEY):
            self.assertNotIn(s, body)


class FakeIsFakeTest(World):
    def test_the_claude_on_the_path_is_the_fake(self):
        found = mod("argv").find_claude(self.bin)
        self.assertEqual(found, FAKE)
        self.assertEqual(os.path.basename(found), "fake-claude")
        with open(found) as f:
            self.assertIn("fake-claude: a stand-in", f.read(400))
        self.assertEqual(os.environ.get("PATH", "").split(os.pathsep).count(self.bin), 0)


if __name__ == "__main__":
    unittest.main()
