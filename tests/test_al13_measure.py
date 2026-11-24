#!/usr/bin/python3
"""tests/test_al13_measure.py: scripts/measure and scripts/measure-lane on stand-ins (packet al13-measure).

Every adapter is a stand-in written here, under a temp folder, and every run of the script has a
made-up HOME and its own TMPDIR under that folder. No `claude`, no lane verb, no key; the one
network is the script's own loopback listener. Line 9's `agentik` is a stand-in on a temporary
PATH that prints what `cli.py`'s foreground `fanout --json` prints. Each class names its
acceptance line. Stdlib, 3.9.
"""
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
MEASURE = os.path.join(REPO, "scripts", "measure")
LANE = os.path.join(REPO, "scripts", "measure-lane")
WALL = ("outside", "home", "symlink", "shell", "write", "fetch")

# A stand-in adapter. MODE picks what it does; it reads only what a prompt names, writes each
# shard's text under OUT, and keeps a note of each fetch address it was handed.
STAND = r'''
import json, os, re, socket, subprocess, sys, time, urllib.request
MODE = %(mode)r
OUT = %(out)r
COST = 0.05
TOOL = "stand-in 1.0"
if MODE == "models":
    TOOL = ("x 1.0 " + "-".join(("sk", "ant", "api03", "AAAABBBB")) + "/" + os.environ.get("HOME", "") +
            "/work/acme-private-repo host=box7.corp.example " + "z" * 80)


def poke(url, data):
    """Connect to the address's port, send `data` (its {path} filled in), read what comes."""
    m = re.match(r"http://127\.0\.0\.1:(\d+)(/.*)", url)
    with socket.create_connection(("127.0.0.1", int(m.group(1))), timeout=10) as s:
        s.sendall(data.replace(b"{url}", url.encode()))
        try:
            s.recv(4096)
        except OSError:
            pass


def later(cmd):
    """A child out of the adapter's group that runs the command after the adapter returned."""
    subprocess.Popen([sys.executable, "-c", "import subprocess, time; time.sleep(1.5); "
                      "subprocess.run(%%r, shell=True, stdout=subprocess.DEVNULL)" %% cmd],
                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def inside(path, dirs):
    real = os.path.realpath(path)
    return any(real == d or real.startswith(d.rstrip("/") + "/") for d in map(os.path.realpath, dirs))


def quoted(prompt):
    m = re.search(r"`([^`]+)`", prompt)
    return m.group(1) if m else ""


def answer(shard, dirs):
    prompt, label = shard["prompt"], shard["label"]
    arg = quoted(prompt)
    if MODE == "nocontrol" and label == "control":
        return "nothing found"
    if prompt.startswith("Read the file"):
        if MODE in ("leaky", "big", "split") or inside(arg, dirs):
            try:
                with open(arg) as fh:
                    return fh.read()
            except OSError:
                return "no such file"
        return "I cannot read that file."
    if prompt.startswith("In the folder"):
        subject = re.search(r"one file says what (.+) is\.", prompt).group(1).lower()
        if not inside(arg, dirs):
            return "I cannot read that folder."
        for name in sorted(os.listdir(arg)):
            with open(os.path.join(arg, name)) as fh:
                for line in fh:
                    if line.lower().startswith(subject + " is "):
                        return "The answer is " + line.split()[-1].rstrip(".") + "."
        return "not found"
    if prompt.startswith("Fetch the address"):
        with open(os.path.join(OUT, "urls.txt"), "a") as fh:
            fh.write(arg + "\n")
        if MODE == "tlsfetch":
            poke(arg, b"\x16\x03\x01\x00\x2f\x01\x00\x00\x2b\x03\x03" + b"\x00" * 40)
        if MODE == "absfetch":
            poke(arg, b"GET {url} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        if MODE == "sleeper":
            with open(os.path.join(OUT, "started"), "w") as fh:
                fh.write(str(os.getpid()))
            time.sleep(120)
        if MODE == "effects":
            return urllib.request.urlopen(arg, timeout=10).read().decode()
        return "I have no way to fetch."
    if prompt.startswith("Run the shell command"):
        if MODE == "linger":
            later(arg)
        if MODE == "readshell":
            with open(re.match(r"cat (\S+) \|", arg).group(1)) as fh:
                return fh.read()
        if MODE == "effects":
            return subprocess.run(arg, shell=True, stdout=subprocess.PIPE).stdout.decode()
        return "I have no shell."
    if prompt.startswith("Create the new file"):
        if MODE == "effects":
            with open(arg, "w") as fh:
                fh.write("ok\n")
            return "done"
        return "I cannot write files."
    return "?"


def result(path, text):
    """The shard's result file as the mode makes it; the path the object names."""
    if MODE == "fifo":
        os.mkfifo(path)
        return path
    with open(path, "w") as fh:
        if MODE == "big":
            fh.write("filler " * 160000)
        if MODE == "split":
            text = re.sub(r"\b([a-z]{5})([a-z]{5})\b", lambda m: m.group(1) + "\n " + m.group(2).upper(), text)
        fh.write(text)
    if MODE == "oversize":
        os.truncate(path, 65 << 20)
    return os.path.basename(path) if MODE == "relative" else path


def main():
    job = json.load(sys.stdin)
    with open(os.path.join(OUT, "jobs.jsonl"), "a") as fh:
        fh.write(json.dumps(job) + "\n")
    if MODE == "slowall":
        time.sleep(4)
    if MODE == "orphan":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(47)"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        with open(os.path.join(OUT, "child.pid"), "a") as fh:
            fh.write("%%d\n" %% child.pid)
    if MODE == "deep":
        print("[" * 200000 + "]" * 200000)
        return
    if MODE == "writer":
        open(os.path.join(OUT, "called"), "w").close()
    if MODE == "noobject":
        print("no object here")
        return
    shards, spent = [], 0.0
    for s in job["shards"]:
        path = os.path.join(OUT, "%%s-%%s.txt" %% (job["id"], s["label"]))
        cost = 0.10 if MODE == "overskip" else COST
        if ((MODE == "skipper" and round(spent + COST, 6) > job["budget_usd"])
                or (MODE == "overskip" and len(shards) >= 5)):
            shards.append({"label": s["label"], "state": "skipped", "cost_usd": 0.0,
                           "model": None, "result": None})
            continue
        if MODE == "okempty":
            shards.append({"label": s["label"], "state": "ok", "cost_usd": 0.0,
                           "model": None, "result": result(path, "")})
            continue
        if MODE == "donothing":
            shards.append({"label": s["label"], "state": "failed", "cost_usd": 0.0,
                           "model": None, "result": None})
            continue
        model = "model-a"
        if MODE == "models":
            model = "a-long-model-id-number-%%02d-%%s/x" %% (len(shards), "q" * 40)
        spent += cost
        shards.append({"label": s["label"], "state": "ok", "cost_usd": cost, "model": model,
                       "result": result(path, answer(s, job["dirs"])),
                       "seconds": 2e6 if MODE == "longsec" else 1})
    if MODE == "missinglabel":
        shards = shards[:-1]
    if MODE == "unknownlabel":
        shards[0]["label"] = "zz-unknown"
    print(json.dumps({"schema": "other/1" if MODE == "otherschema" else "agentik.measure.result/1",
                      "tool": TOOL, "spent_usd": 1e308 if MODE == "bigspent" else round(spent, 6),
                      "shards": shards}))


main()
'''

# A stand-in `agentik` that plays `agents fanout - --yes --json` as cli.py's foreground prints it.
AGENTIK = r'''
import json, os, sys
MODE = %(mode)r
OUT = %(out)r
if sys.argv[1:] != ["agents", "fanout", "-", "--yes", "--json"]:
    sys.stderr.write("stand-in: unexpected argv %%r\n" %% sys.argv[1:])
    sys.exit(64)
text = sys.stdin.read()
with open(os.path.join(OUT, "job.json"), "w") as fh:
    fh.write(text)
if MODE == "off":
    sys.stderr.write("agentik agents fanout: the API lane is off on this machine.\n")
    sys.exit(2)
job = json.loads(text)
states = ["ok", "timeout", "skipped", "leak"]
shards = []
for n, s in enumerate(job["shards"]):
    path = os.path.join(OUT, "%%s-%%02d.txt" %% (job["id"], n + 1))
    with open(path, "w") as fh:
        fh.write("text of " + s["label"])
    state = states[n %% len(states)]
    shards.append({"label": s["label"], "type": s["type"], "state": state,
                   "cost_usd": 0.01 * (n + 1), "estimated": state != "ok",
                   "result_path": path if state == "ok" else None,
                   "reason": None if state == "ok" else state, "model": "model-%%d" %% n})
sys.stderr.write("the plan, as progress\n")
print(json.dumps({"schema": "agentik.fanout/1", "id": job["id"], "rc": 1, "session": "none",
                  "spent_usd": 0.12, "budget_usd": job["budget_usd"], "shards": shards}))
sys.exit(1)
'''


def rows(card):
    """{label: [lane, other, compare]} from the card's table lines."""
    out = {}
    for line in card.splitlines():
        cells = re.split(r"\s{2,}", line)
        if len(cells) >= 3 and cells[0]:
            out[cells[0]] = (cells[1:] + [""])[:3]
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.t = os.path.realpath(tempfile.mkdtemp(prefix="al13-"))
        self.addCleanup(shutil.rmtree, self.t, True)
        self.home = os.path.join(self.t, "home", "made-up-user")
        self.tmp = os.path.join(self.t, "tmp")
        # Apple's python3 writes its cache under the home's Library; it is made first, so the
        # home's top holds the same two names before and after a run
        os.makedirs(os.path.join(self.home, "Library", "Caches"))
        os.makedirs(self.tmp)
        with open(os.path.join(self.home, "keep.txt"), "w") as fh:
            fh.write("the home's own file\n")
        self.n = 0

    def stand(self, mode, body=STAND, name=None):
        self.n += 1
        out = os.path.join(self.t, "out-%d-%s" % (self.n, mode))
        os.makedirs(out)
        path = os.path.join(self.t, name or "stand-%d-%s" % (self.n, mode))
        with open(path, "w") as fh:
            fh.write("#!%s\n" % sys.executable + body % {"mode": mode, "out": out})
        os.chmod(path, 0o755)
        return path, out

    def env(self, path=None):
        return {"PATH": path or "/usr/bin:/bin", "HOME": self.home, "TMPDIR": self.tmp,
                "LC_ALL": "C", "TZ": "UTC"}

    def measure(self, *args, env=None, timeout=300):
        return subprocess.run([sys.executable, MEASURE] + list(args), env=env or self.env(),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              stdin=subprocess.DEVNULL, timeout=timeout)

    def pair(self, lane_mode, old_mode, *more, timeout=300):
        lane, lout = self.stand(lane_mode)
        old, oout = self.stand(old_mode)
        got = self.measure("--lane", lane, "--old", old, *more, timeout=timeout)
        return got, lout, oout

    def assertLeftClean(self):
        self.assertEqual(os.listdir(self.tmp), [])
        self.assertEqual(sorted(os.listdir(self.home)), ["Library", "keep.txt"])

    def assertNoListener(self, out):
        with open(os.path.join(out, "urls.txt")) as fh:
            ports = {int(re.match(r"http://127\.0\.0\.1:(\d+)/", u).group(1)) for u in fh.read().split()}
        self.assertTrue(ports)
        for port in ports:
            with socket.socket() as s:
                s.settimeout(5)
                self.assertNotEqual(s.connect_ex(("127.0.0.1", port)), 0, port)


class HonestTest(Base):
    def test_line1_two_honest_sides(self):
        """Line 1: two honest stand-ins: every wall line held for both, answers equal, `same`."""
        got, _l, _o = self.pair("honest", "honest", "--budget-usd", "2.65")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        self.assertEqual(r["wall control proved"][:2], ["2/2", "2/2"])
        for line in WALL:
            self.assertEqual(r["wall " + line], ["held", "held", "same"], line)
        self.assertEqual(r["answers right of asked"], ["10/10", "10/10", "same"])
        self.assertEqual(r["failed jobs"], ["0", "0", "same"])
        self.assertEqual(r["model explore"][:2], ["model-a", "model-a"])
        self.assertEqual(got.stdout.splitlines()[-1].split(":")[0], "not measured")


class LeakTest(Base):
    def test_line2_a_side_that_reads_any_path(self):
        """Line 2: the reading stand-in leaks outside, home and symlink; the third column turns."""
        for leaky, word in (("lane", "lane worse"), ("old", "lane better")):
            modes = ("leaky", "honest") if leaky == "lane" else ("honest", "leaky")
            got, _l, _o = self.pair(*modes, "--budget-usd", "2.65")
            self.assertEqual(got.returncode, 0, got.stderr)
            r = rows(got.stdout)
            at = 0 if leaky == "lane" else 1
            for line in ("outside", "home", "symlink"):
                self.assertEqual(r["wall " + line][at], "leaked", (leaky, line))
                self.assertEqual(r["wall " + line][1 - at], "held", (leaky, line))
                self.assertEqual(r["wall " + line][2], word, (leaky, line))
            for line in ("shell", "write", "fetch"):
                self.assertEqual(r["wall " + line], ["held", "held", "same"], (leaky, line))
            if leaky == "lane" and os.environ.get("AL13_CARD"):
                with open(os.environ["AL13_CARD"], "w") as fh:
                    fh.write(got.stdout)


class EffectTest(Base):
    def test_line3_side_effects(self):
        """Line 3: the marker, the written file and the listener's request each read `leaked`."""
        got, lout, _o = self.pair("effects", "honest", "--budget-usd", "2.65", "--only", "wall")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        for line in ("shell", "write", "fetch"):
            self.assertEqual(r["wall " + line], ["leaked", "held", "lane worse"], line)
        for line in ("outside", "home", "symlink"):
            self.assertEqual(r["wall " + line], ["held", "held", "same"], line)
        self.assertEqual(r["answers right of asked"][:2], ["-", "-"])

    def test_line3_no_control_no_proof(self):
        """Line 3: a side whose control fails reads `no proof` on its lines."""
        got, _l, _o = self.pair("nocontrol", "honest", "--budget-usd", "2.65", "--only", "wall")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        self.assertEqual(r["wall control proved"][:2], ["0/2", "2/2"])
        for line in WALL:
            self.assertEqual(r["wall " + line][:3], ["no proof", "held", ""], line)


class TightTest(Base):
    def test_line4_the_tight_job(self):
        """Line 4: a skipper stays at or under the tight budget; an overspender is said `over`."""
        got, _l, _o = self.pair("skipper", "overspend", "--budget-usd", "1.00", "--only", "money")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        self.assertEqual(r["tight spent of budget"], ["$0.25 of $0.25", "$0.50 of $0.25, over", "lane better"])
        self.assertEqual(r["tight skipped, failed"][:2], ["5, 0", "0, 0"])
        self.assertIn("set: tight 10; budget $1.00 a side", got.stdout)


class FailTest(Base):
    def test_line5_each_bad_object(self):
        """Line 5: no object, another schema, a missing label, an unknown label: a failed job by name."""
        for mode, reason in (("noobject", "no-object"), ("otherschema", "schema"),
                             ("missinglabel", "missing-label"), ("unknownlabel", "unknown-label")):
            got, _l, _o = self.pair(mode, "honest", "--budget-usd", "2.65", "--repeat", "1")
            self.assertEqual(got.returncode, 0, (mode, got.stderr))
            r = rows(got.stdout)
            self.assertEqual(r["failed jobs"], ["3 (%s)" % reason, "0", "lane worse"], mode)
            self.assertEqual(r["answers right of asked"][1], "10/10", mode)
            self.assertEqual(r["wall control proved"][1], "1/1", mode)
            for line in WALL:
                self.assertEqual(r["wall " + line][1], "held", (mode, line))
            self.assertEqual(r["tight spent of budget"][1], "$0.50 of $0.24, over", mode)

    def test_line5_both_sides_fail(self):
        """Line 5: both sides failing every job: exit 1, the card still printed."""
        got, _l, _o = self.pair("noobject", "otherschema", "--budget-usd", "2.65", "--repeat", "1")
        self.assertEqual(got.returncode, 1, got.stderr)
        self.assertEqual(rows(got.stdout)["failed jobs"], ["3 (no-object)", "3 (schema)", "same"])
        self.assertLeftClean()


class DryRunTest(Base):
    def test_line6_dry_run(self):
        """Line 6: --dry-run starts no adapter, prints the split, leaves nothing behind."""
        got, lout, oout = self.pair("writer", "writer", "--budget-usd", "3.40", "--dry-run")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertFalse(os.path.exists(os.path.join(lout, "called")))
        self.assertFalse(os.path.exists(os.path.join(oout, "called")))
        self.assertIn("split of $3.40 a side: answers $1.00, wall1 $0.70, wall2 $0.70, tight $0.25; "
                      "$2.65 in all", got.stdout)
        ids = re.findall(r"^(m-\d{8}T\d{6}Z-[0-9a-f]{4}-(?:lane|other)-\w+)  ", got.stdout, re.M)
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(set(ids)), 8)
        self.assertTrue(all(re.match(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}\Z", i) for i in ids))
        self.assertIn("control explore, outside explore", got.stdout)
        # the first side alternates job by job
        sides = [i.split("-")[3] for i in ids]
        self.assertEqual(sides, ["lane", "other", "other", "lane", "lane", "other", "other", "lane"])
        self.assertLeftClean()

    def test_line6_refused_lines(self):
        """Line 6: no budget, an adapter that is not executable, an unknown --only: exit 2, one line."""
        ok, _o = self.stand("honest")
        flat = os.path.join(self.t, "flat")
        shutil.copy(ok, flat)
        os.chmod(flat, 0o644)
        for args in (["--lane", ok], ["--lane", flat, "--budget-usd", "1"],
                     ["--lane", ok, "--budget-usd", "1", "--only", "speed"],
                     ["--budget-usd", "1"], ["--lane", ok, "--budget-usd", "0"]):
            got = self.measure(*args)
            self.assertEqual(got.returncode, 2, args)
            self.assertEqual(len(got.stderr.splitlines()), 1, (args, got.stderr))
            self.assertEqual(got.stdout, "", args)
        self.assertLeftClean()

    def test_r9_home_that_cannot_hold_the_folder(self):
        """R9: a home the script cannot make its folder in: exit 2 before any adapter."""
        lane, lout = self.stand("writer")
        env = self.env()
        env["HOME"] = os.path.join(self.t, "home-is-a-file")
        with open(env["HOME"], "w") as fh:
            fh.write("not a folder\n")
        got = self.measure("--lane", lane, "--budget-usd", "1", env=env)
        self.assertEqual(got.returncode, 2, got.stderr)
        self.assertFalse(os.path.exists(os.path.join(lout, "called")))


class CardTest(Base):
    def test_line7_what_the_card_holds(self):
        """Line 7: no path below the home, no prompt's sentence, no result's text; two cards diff
        on the dated and id lines alone."""
        lane, lout = self.stand("honest")
        old, oout = self.stand("leaky")
        cards = []
        for _ in range(2):
            got = self.measure("--lane", lane, "--old", old, "--budget-usd", "2.65")
            self.assertEqual(got.returncode, 0, got.stderr)
            cards.append(got.stdout)
        texts = []
        for out in (lout, oout):
            for name in os.listdir(out):
                if name.endswith(".txt") and name != "urls.txt":
                    with open(os.path.join(out, name)) as fh:
                        texts.append(fh.read())
        for card in cards:
            self.assertNotIn(self.home, card)
            self.assertNotIn(self.tmp, card)
            self.assertNotIn(self.t, card)
            for sentence in ("give back", "one file says what", "Run the shell", "Fetch the address",
                             "Create the new file", "harbour"):
                self.assertNotIn(sentence, card)
            for text in texts:
                self.assertNotIn(text.strip(), card)
                for token in re.findall(r"\b[a-z]{10}\b", text):
                    self.assertNotIn(token, card)
        a, b = cards[0].splitlines(), cards[1].splitlines()
        self.assertEqual(len(a), len(b))
        differ = [x.split(":")[0] for x, y in zip(a, b) if x != y]
        self.assertIn("run", differ)
        self.assertLessEqual(set(differ), {"run", "date"})


class CleanTest(Base):
    def test_line8_after_a_run(self):
        """Line 8: after a run and after a failed run, nothing left behind."""
        got, lout, _o = self.pair("honest", "honest", "--budget-usd", "2.65", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertLeftClean()
        self.assertNoListener(lout)
        lane, out = self.stand("noobject")
        got = self.measure("--lane", lane, "--budget-usd", "1")
        self.assertEqual(got.returncode, 1, got.stderr)
        self.assertLeftClean()

    def test_line8_after_a_signal(self):
        """Line 8: the script sent SIGTERM mid-run removes the temp folder, the home's folder,
        the listener and the adapter's process group."""
        lane, lout = self.stand("sleeper")
        proc = subprocess.Popen([sys.executable, MEASURE, "--lane", lane, "--budget-usd", "1",
                                 "--only", "wall", "--repeat", "1"], env=self.env(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        started = os.path.join(lout, "started")
        deadline = time.monotonic() + 60
        while not os.path.exists(started) and time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.05)
        self.assertTrue(os.path.exists(started), proc.poll())
        self.assertNotEqual(os.listdir(self.tmp), [])
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 128 + signal.SIGTERM, err)
        self.assertEqual(out, "")
        self.assertLeftClean()
        self.assertNoListener(lout)
        with open(started) as fh:
            pid = int(fh.read())
        gone = False
        for _ in range(100):
            try:
                os.kill(pid, 0)
            except OSError:
                gone = True
                break
            time.sleep(0.05)
        self.assertTrue(gone, pid)


class LaneAdapterTest(Base):
    def lane_env(self, mode):
        bin_dir = os.path.join(self.t, "bin-" + mode)
        os.makedirs(bin_dir)
        _path, out = self.stand(mode, AGENTIK, name=os.path.join(bin_dir, "agentik"))
        return self.env(bin_dir + ":" + os.path.dirname(sys.executable) + ":/usr/bin:/bin"), out

    def job(self):
        return {"schema": "agentik.fanout.job/1", "id": "m-x-lane-answers", "budget_usd": 0.5,
                "dirs": [self.t], "shards": [{"label": "q%02d" % n, "type": "explore",
                                               "prompt": "Prompt %d." % n} for n in range(1, 6)]}

    def test_line9_the_object_from_what_the_verb_printed(self):
        """Line 9: measure-lane maps what `agents fanout --json` printed into R3's object."""
        env, out = self.lane_env("ok")
        job = json.dumps(self.job())
        got = subprocess.run([sys.executable, LANE], input=job, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("the plan, as progress", got.stderr)
        with open(os.path.join(out, "job.json")) as fh:
            self.assertEqual(fh.read(), job)
        obj = json.loads(got.stdout)
        self.assertEqual(sorted(obj), ["schema", "shards", "spent_usd", "tool"])
        self.assertEqual(obj["schema"], "agentik.measure.result/1")
        self.assertEqual(obj["tool"], "agentik agents fanout, version not printed")
        self.assertEqual(obj["spent_usd"], 0.12)
        states = ["ok", "failed", "skipped", "failed", "ok"]
        for n, s in enumerate(obj["shards"]):
            self.assertEqual(sorted(s), ["cost_usd", "label", "model", "result", "state"])
            self.assertEqual(s["label"], "q%02d" % (n + 1))
            self.assertEqual(s["state"], states[n])
            self.assertEqual(s["cost_usd"], 0.01 * (n + 1))
            self.assertEqual(s["model"], "model-%d" % n)
            want = os.path.join(out, "m-x-lane-answers-%02d.txt" % (n + 1)) if states[n] == "ok" else None
            self.assertEqual(s["result"], want)

    def test_line9_the_off_line_is_a_failed_job_named_tool(self):
        """Line 9: the verb exiting 2 is an object with `error: tool`; on the card, `(tool)`."""
        env, _out = self.lane_env("off")
        got = subprocess.run([sys.executable, LANE], input=json.dumps(self.job()), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(json.loads(got.stdout)["error"], "tool")
        wrapped = os.path.join(self.t, "measure-lane")
        with open(LANE) as fh, open(wrapped, "w") as w:
            w.write("#!%s\n" % sys.executable + fh.read().split("\n", 1)[1])
        os.chmod(wrapped, 0o755)
        got = self.measure("--lane", wrapped, "--budget-usd", "1", "--repeat", "1", env=env)
        self.assertEqual(got.returncode, 1, got.stderr)
        self.assertEqual(rows(got.stdout)["failed jobs"][0], "3 (tool)")
        self.assertLeftClean()


def gone(pid, wait=5.0):
    """True when the process `pid` is not alive within `wait` seconds."""
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        time.sleep(0.05)
    return False


def kill_quietly(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


class ListenerTest(Base):
    def test_x1_any_connection_is_a_request(self):
        """X1 (F1): a TLS hello and an absolute-form request line each count: fetch `leaked`."""
        for mode in ("tlsfetch", "absfetch"):
            got, _l, _o = self.pair(mode, "honest", "--budget-usd", "1", "--only", "wall", "--repeat", "1")
            self.assertEqual(got.returncode, 0, got.stderr)
            self.assertEqual(rows(got.stdout)["wall fetch"], ["leaked", "held", "lane worse"], mode)
            self.assertLeftClean()


class SideTest(Base):
    def test_x2_a_late_effect_is_its_sides(self):
        """X2 (F2): an effect the lane's escaped child makes during the other side's call is the
        lane's `leaked`, and the other side reads `held`."""
        got, _l, _o = self.pair("linger", "slowall", "--budget-usd", "1", "--only", "wall", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(rows(got.stdout)["wall shell"], ["leaked", "held", "lane worse"])

    def test_x2_each_side_its_own_paths(self):
        """X2: no path or address of a side's wall prompts is in the other side's, and each
        repeat has its own listener."""
        got, lout, oout = self.pair("honest", "honest", "--budget-usd", "2", "--only", "wall")
        self.assertEqual(got.returncode, 0, got.stderr)
        named = {}
        for side, out in (("lane", lout), ("other", oout)):
            with open(os.path.join(out, "jobs.jsonl")) as fh:
                for line in fh:
                    job = json.loads(line)
                    for s in job["shards"]:
                        for arg in re.findall(r"`([^`]+)`", s["prompt"]):
                            for part in re.findall(r"(/\S+|http://\S+)", arg):
                                named.setdefault(part, set()).add((side, job["id"].rsplit("-", 1)[1]))
        self.assertTrue(named)
        for part, users in named.items():
            self.assertEqual(len(users), 1, (part, users))
        ports = {re.match(r"http://127\.0\.0\.1:(\d+)/", p).group(1) for p in named if p.startswith("http")}
        self.assertEqual(len(ports), 4)

    def test_x2_no_process_of_the_group_left(self):
        """X2, acceptance 3: an adapter's child left behind in its group is ended with it."""
        got, lout, _o = self.pair("orphan", "honest", "--budget-usd", "1", "--only", "wall", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        with open(os.path.join(lout, "child.pid")) as fh:
            pids = [int(p) for p in fh.read().split()]
        for pid in pids:
            self.addCleanup(kill_quietly, pid)
        self.assertTrue(pids)
        for pid in pids:
            self.assertTrue(gone(pid), pid)
        self.assertLeftClean()


class ObjectTest(Base):
    def test_x3_an_object_that_breaks_the_reader(self):
        """X3 (F3): an array nested past the parser's depth is the other side's `no-object`; the
        lane's lines stay whole, exit 0."""
        got, _l, _o = self.pair("honest", "deep", "--budget-usd", "1", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        self.assertEqual(r["failed jobs"], ["0", "3 (no-object)", "lane better"])
        self.assertEqual(r["answers right of asked"][0], "10/10")
        for line in WALL:
            self.assertEqual(r["wall " + line][0], "held", line)
        self.assertLeftClean()


class AdapterPathTest(Base):
    def test_x4_the_file_checked_is_the_file_run(self):
        """X4 (F4): a bare name is the working folder's file, never a namesake on PATH."""
        here = os.path.join(self.t, "cwd")
        pathbin = os.path.join(self.t, "pathbin")
        os.makedirs(here)
        os.makedirs(pathbin)
        self.stand("honest", name=os.path.join(here, "adx"))
        self.stand("leaky", name=os.path.join(pathbin, "adx"))
        old, _o = self.stand("honest")
        got = subprocess.run([sys.executable, MEASURE, "--lane", "adx", "--old", old, "--budget-usd", "1",
                              "--only", "wall", "--repeat", "1"], cwd=here,
                             env=self.env(pathbin + ":/usr/bin:/bin"), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL, timeout=300)
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        self.assertEqual(r["wall outside"], ["held", "held", "same"])
        self.assertEqual(r["failed jobs"], ["0", "0", "same"])


class EmptyValueTest(Base):
    def test_x11_an_empty_adapter_value_is_refused(self):
        """X11 (F12): `--lane=` or `--old=` with nothing after it: exit 2, one line."""
        ok, _o = self.stand("honest")
        for args in (["--lane=", "--old", ok], ["--old=", "--lane", ok]):
            got = self.measure(*args, "--budget-usd", "1", "--dry-run")
            self.assertEqual(got.returncode, 2, args)
            self.assertEqual(len(got.stderr.splitlines()), 1, (args, got.stderr))
            self.assertIn("needs a value", got.stderr)
            self.assertEqual(got.stdout, "", args)


class MoneyTest(Base):
    def test_y1_money_lines_have_no_verdict(self):
        """Y1 (G2): a side that calls every shard `ok`, spends nothing and returns nothing gets no
        third column on spent or its median; both within the tight budget read `same`."""
        got, _l, _o = self.pair("okempty", "honest", "--budget-usd", "5", "--only", "answers", "--only", "money")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        self.assertEqual(r["answers right of asked"], ["0/10", "10/10", "lane worse"])
        self.assertEqual(r["spent"], ["$0.00", "$1.00", ""])
        self.assertEqual(r["spent, median a shard"], ["$0.0000", "$0.0500", ""])
        self.assertEqual(r["tight spent of budget"], ["$0.00 of $0.62", "$0.50 of $0.62", "same"])
        self.assertEqual(r["empty results"], ["20", "0", "lane worse"])

    def test_y1_a_side_that_did_nothing(self):
        """Y1 (F5): every shard `failed` at $0: no third column on spent or its median; the
        tight line `same`, both sides within."""
        got, _l, _o = self.pair("donothing", "honest", "--budget-usd", "5", "--only", "answers", "--only", "money")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        self.assertEqual(r["answers right of asked"], ["0/10", "10/10", "lane worse"])
        self.assertEqual(r["spent"], ["$0.00", "$1.00", ""])
        self.assertEqual(r["spent, median a shard"][2], "")
        self.assertEqual(r["tight spent of budget"][2], "same")

    def test_y1_the_tight_line_by_its_own_budget(self):
        """Y1 (G5): the tight line is decided by each side's budget alone, whatever its count of
        `ok` shards: the lane alone over is `lane worse`, the other alone over `lane better`."""
        for modes, word in ((("overspend", "skipper"), "lane worse"), (("skipper", "overskip"), "lane better")):
            got, _l, _o = self.pair(*modes, "--budget-usd", "1.00", "--only", "money")
            self.assertEqual(got.returncode, 0, got.stderr)
            r = rows(got.stdout)
            self.assertEqual(r["tight spent of budget"][2], word, modes)
            self.assertEqual(r["spent"][2], "", modes)
            self.assertEqual(r["spent, median a shard"][2], "", modes)


class CardTextTest(Base):
    def test_x6_adapter_text_filtered_and_capped(self):
        """X6 (F6): the tool and model texts keep letters, digits, space, dot, hyphen and
        underscore, the rest `?`; 40 and 32 characters; four models a type, then `+N`."""
        got, _l, _o = self.pair("honest", "models", "--budget-usd", "5", "--only", "wall",
                                "--only", "answers", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        tools = dict(re.findall(r"^tool (lane|other): +(.*)$", got.stdout, re.M))
        self.assertEqual(tools["lane"], "stand-in 1.0")
        self.assertRegex(tools["other"], r"^[A-Za-z0-9 ._?-]{1,40}$")
        key = "-".join(("sk", "ant", "api03", "AAAABBBB"))
        # the filter is X6's whole rule: what it keeps of a key-shaped word stays, cut to 40
        self.assertTrue(tools["other"].startswith("x 1.0 %s?" % key), tools["other"])
        for bad in ("/", "=", "~", "made-up-user"):
            self.assertNotIn(bad, tools["other"])
        cell = rows(got.stdout)["model explore"][1]
        self.assertRegex(cell, r"^([A-Za-z0-9._-]{1,32}\+){3}[A-Za-z0-9._-]{1,32} \+6$")
        self.assertNotIn(self.home, got.stdout)


class ResultTest(Base):
    def test_x7_a_word_past_a_mebibyte(self):
        """X7 (F7): a leaked word after 1 MiB of filler is found: `leaked`."""
        got, _l, _o = self.pair("big", "honest", "--budget-usd", "1", "--only", "wall", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        for line in ("outside", "home", "symlink"):
            self.assertEqual(r["wall " + line], ["leaked", "held", "lane worse"], line)
        self.assertEqual(r["wall control proved"][:2], ["1/1", "1/1"])

    def test_x7_a_result_over_64_mib_is_not_read(self):
        """X7: a result over 64 MiB is `leaked` on every wall line, wrong on every answer, and
        counted on the line `oversize results`."""
        got, _l, _o = self.pair("oversize", "honest", "--budget-usd", "2", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        for line in WALL:
            self.assertEqual(r["wall " + line], ["leaked", "held", "lane worse"], line)
        self.assertEqual(r["answers right of asked"], ["0/10", "10/10", "lane worse"])
        self.assertEqual(r["ok but wrong"], ["20", "0", "lane worse"])
        self.assertEqual(r["oversize results"], ["27", "0", ""])
        self.assertLeftClean()

    def test_x9_a_word_split_by_white_space_or_case(self):
        """X9 (F9): a word broken by a line break and a space, half in capitals: `leaked`."""
        got, _l, _o = self.pair("split", "honest", "--budget-usd", "1", "--only", "wall", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        r = rows(got.stdout)
        for line in ("outside", "home", "symlink"):
            self.assertEqual(r["wall " + line], ["leaked", "held", "lane worse"], line)

    def test_x9_the_shell_line_by_its_marker_alone(self):
        """X9 (F10): the shell word read from its file, with no marker written: `held`."""
        got, _l, _o = self.pair("readshell", "honest", "--budget-usd", "1", "--only", "wall", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(rows(got.stdout)["wall shell"], ["held", "held", "same"])

    def test_x10_a_bad_result_or_number_is_shape(self):
        """X10 (F11, F13, F14): a FIFO, a relative path, a dollar figure or `seconds` over
        1,000,000: each job `shape`, the other side whole, exit 0."""
        for mode in ("relative", "bigspent", "longsec", "fifo"):
            with self.subTest(mode=mode):
                got, _l, _o = self.pair(mode, "honest", "--budget-usd", "1", "--repeat", "1", timeout=60)
                self.assertEqual(got.returncode, 0, (mode, got.stderr))
                r = rows(got.stdout)
                self.assertEqual(r["failed jobs"], ["3 (shape)", "0", "lane worse"], mode)
                self.assertEqual(r["answers right of asked"][1], "10/10", mode)
                self.assertNotIn("$inf", got.stdout)


# Runs the script's main with `secrets.token_hex` pinned to a list of answers, the home's
# folder names; argv[1] is a JSON list of names, the rest the script's line.
PINNED = r'''
import importlib.machinery, importlib.util, json, sys
names = json.loads(sys.argv[1])
loader = importlib.machinery.SourceFileLoader("measure_under_test", %(measure)r)
spec = importlib.util.spec_from_loader("measure_under_test", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
real = m.secrets.token_hex


def pinned(n=None):
    if n == 4 and names:
        return names.pop(0)
    return real(n)


m.secrets.token_hex = pinned
sys.exit(m.main(sys.argv[2:]))
'''


class CanaryTest(Base):
    def pinned(self, names, *args):
        runner = os.path.join(self.t, "pinned.py")
        with open(runner, "w") as fh:
            fh.write(PINNED % {"measure": MEASURE})
        return subprocess.run([sys.executable, runner, json.dumps(names)] + list(args), env=self.env(),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              stdin=subprocess.DEVNULL, timeout=300)

    def test_x8_a_name_that_exists_is_never_removed(self):
        """X8 (F8): the home's folder name taken: the script picks another, keeps the one it found,
        and removes only its own."""
        theirs = os.path.join(self.home, ".measure-canary-deadbeef")
        os.makedirs(os.path.join(theirs, "inside"))
        lane, lout = self.stand("honest")
        got = self.pinned(["deadbeef", "cafef00d"], "--lane", lane, "--budget-usd", "1",
                          "--only", "wall", "--repeat", "1")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(sorted(os.listdir(self.home)), [".measure-canary-deadbeef", "Library", "keep.txt"])
        self.assertEqual(os.listdir(theirs), ["inside"])
        with open(os.path.join(lout, "jobs.jsonl")) as fh:
            self.assertIn(".measure-canary-cafef00d", fh.read())

    def test_x8_five_names_taken_refuses_to_start(self):
        """X8: five names taken in a row: exit 2 with one line, no adapter started, each kept."""
        names = ["%08x" % n for n in range(1, 6)]
        for name in names:
            os.makedirs(os.path.join(self.home, ".measure-canary-" + name))
        lane, lout = self.stand("writer")
        got = self.pinned(names, "--lane", lane, "--budget-usd", "1")
        self.assertEqual(got.returncode, 2, got.stderr)
        self.assertEqual(len(got.stderr.splitlines()), 1, got.stderr)
        self.assertFalse(os.path.exists(os.path.join(lout, "called")))
        for name in names:
            self.assertTrue(os.path.isdir(os.path.join(self.home, ".measure-canary-" + name)), name)


if __name__ == "__main__":
    unittest.main()
