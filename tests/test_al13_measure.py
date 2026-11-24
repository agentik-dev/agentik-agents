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
import json, os, re, subprocess, sys, time, urllib.request
MODE = %(mode)r
OUT = %(out)r
COST = 0.05


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
        if MODE == "leaky" or inside(arg, dirs):
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
        if MODE == "sleeper":
            with open(os.path.join(OUT, "started"), "w") as fh:
                fh.write(str(os.getpid()))
            time.sleep(120)
        if MODE == "effects":
            return urllib.request.urlopen(arg, timeout=10).read().decode()
        return "I have no way to fetch."
    if prompt.startswith("Run the shell command"):
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


def main():
    job = json.load(sys.stdin)
    if MODE == "writer":
        open(os.path.join(OUT, "called"), "w").close()
    if MODE == "noobject":
        print("no object here")
        return
    shards, spent = [], 0.0
    for s in job["shards"]:
        path = os.path.join(OUT, "%%s-%%s.txt" %% (job["id"], s["label"]))
        if MODE == "skipper" and round(spent + COST, 6) > job["budget_usd"]:
            shards.append({"label": s["label"], "state": "skipped", "cost_usd": 0.0,
                           "model": None, "result": None})
            continue
        with open(path, "w") as fh:
            fh.write(answer(s, job["dirs"]))
        spent += COST
        shards.append({"label": s["label"], "state": "ok", "cost_usd": COST,
                       "model": "model-a", "result": path, "seconds": 1})
    if MODE == "missinglabel":
        shards = shards[:-1]
    if MODE == "unknownlabel":
        shards[0]["label"] = "zz-unknown"
    print(json.dumps({"schema": "other/1" if MODE == "otherschema" else "agentik.measure.result/1",
                      "tool": "stand-in 1.0", "spent_usd": round(spent, 6), "shards": shards}))


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

    def measure(self, *args, env=None):
        return subprocess.run([sys.executable, MEASURE] + list(args), env=env or self.env(),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              stdin=subprocess.DEVNULL, timeout=300)

    def pair(self, lane_mode, old_mode, *more):
        lane, lout = self.stand(lane_mode)
        old, oout = self.stand(old_mode)
        got = self.measure("--lane", lane, "--old", old, *more)
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


if __name__ == "__main__":
    unittest.main()
