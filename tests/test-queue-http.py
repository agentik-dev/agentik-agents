#!/usr/bin/env python3
"""Tests for queue-mvp's HTTP lane: Api.request and what rides it.

Stub-driven: HOME is a temp dir set before the tool loads, so its default
state dir lands there and is removed after; the job-queue service is a
stub store on a loopback ThreadingHTTPServer (127.0.0.1, port 0), and the
agent lane is --dry-run's canned replay, so no socket leaves loopback,
nothing is served past this run and nothing is spent.

    tests/test-queue-http.py
"""
from __future__ import annotations

import http.server
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import threading
import urllib.parse
import uuid

REPO = pathlib.Path(__file__).resolve().parent.parent
TOOL = REPO / "bin" / "queue-mvp"

passed = failed = 0


def check(cond: bool, desc: str, detail: str = "") -> None:
    global passed, failed
    if cond:
        print(f"  PASS  {desc}")
        passed += 1
    else:
        print(f"  FAIL  {desc}\n     {detail}")
        failed += 1


def load():
    """bin/queue-mvp as a module, in sys.modules first: its dataclasses look it up."""
    sys.dont_write_bytecode = True      # no bin/__pycache__, no .pyc under Apple's caches
    loader = importlib.machinery.SourceFileLoader("queue_mvp", str(TOOL))
    spec = importlib.util.spec_from_loader("queue_mvp", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["queue_mvp"] = mod
    loader.exec_module(mod)
    return mod


class Store:
    """The job-queue service's endpoints queue-mvp calls, in memory.

    conflict picks a duplicate create's 409 shape: "job_id", "detail" or "bare";
    refuse_claims answers a claim with claimed: false; fail_next answers the next
    request with a 500 carrying that text.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.jobs: dict = {}
        self.keys: dict = {}
        self.transitions: dict = {}
        self.leases: dict = {}
        self.next_id = 100
        self.conflict = "job_id"
        self.refuse_claims = False
        self.fail_next = ""
        self.seen: list = []

    def handle(self, method: str, parts: list, query: dict, body: dict):
        if method == "POST" and parts == ["v1", "jobs"]:
            k = (body["class"], body["idempotency_key"])
            if k in self.keys:
                jid = self.keys[k]
                if self.conflict == "job_id":
                    return 409, {"error": "conflict", "job_id": jid}
                if self.conflict == "detail":
                    return 409, {"error": "conflict", "detail": f"key held by job_id={jid}"}
                return 409, {"error": "conflict"}
            self.next_id += 1
            job = {"id": self.next_id, "class": body["class"], "status": "pending",
                   "idempotency_key": body["idempotency_key"], "attempts": 0,
                   "max_attempts": body.get("max_attempts", 3),
                   "created_by": body.get("created_by")}
            self.jobs[job["id"]] = job
            self.keys[k] = job["id"]
            self.transitions[job["id"]] = []
            return 201, {"job": dict(job)}
        if method == "GET" and parts == ["v1", "jobs"]:
            cls, q = query.get("class", [""])[0], query.get("q", [""])[0]
            return 200, {"jobs": [dict(j) for j in self.jobs.values()
                                  if j["class"] == cls and q in j["idempotency_key"]]}
        if len(parts) >= 3 and parts[:2] == ["v1", "jobs"] and parts[2].isdigit() \
                and int(parts[2]) in self.jobs:
            job, tail = self.jobs[int(parts[2])], parts[3:]
            if method == "GET" and not tail:
                return 200, {"job": dict(job), "transitions": list(self.transitions[job["id"]])}
            if method == "POST" and tail == ["claim"]:
                if self.refuse_claims or job["status"] != "pending":
                    return 200, {"claimed": False}
                token = uuid.uuid4().hex
                job.update(status="leased", attempts=job["attempts"] + 1,
                           lease_owner=body.get("worker"))
                self.leases[job["id"]] = token
                return 200, {"claimed": True, "job": dict(job), "lease_token": token,
                             "lease_expires_at": "2026-10-17T12:15:00Z"}
            if method == "POST" and tail == ["transition"]:
                if body.get("lease_token") != self.leases.get(job["id"]):
                    return 409, {"error": "lease token mismatch"}
                self.transitions[job["id"]].append(
                    {"from": job["status"], "to": body["to"], "lease_token": body["lease_token"],
                     "detail": body.get("detail", "")})
                job["status"] = body["to"]
                return 200, {"job": dict(job)}
        return 404, {"error": "no route", "path": "/" + "/".join(parts)}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # quiet: the suite prints its own lines
        pass

    def reply(self, status: int, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def route(self, method: str) -> None:
        store = self.server.store
        url = urllib.parse.urlsplit(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        with store.lock:
            store.seen.append((method, url.path))
            if store.fail_next:
                raw, store.fail_next = store.fail_next, ""
                status, data = 500, raw.encode("utf-8")
            else:
                status, obj = store.handle(method, url.path.strip("/").split("/"),
                                           urllib.parse.parse_qs(url.query), body)
                data = json.dumps(obj).encode("utf-8")
        self.reply(status, data)

    def do_GET(self) -> None:
        self.route("GET")

    def do_POST(self) -> None:
        self.route("POST")


def free_port() -> int:
    """A loopback port nothing listens on: bound, read, closed."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def call(fn, *args, **kwargs):
    """fn's value and None, or None and what it raised: a raise is a FAIL line, not a crash."""
    try:
        return fn(*args, **kwargs), None
    except Exception as e:  # noqa: BLE001
        return None, e


def main(qm, home: pathlib.Path, base: str, store: Store) -> int:
    print("== Api.request and create_job on a loopback stub store ==")
    api = qm.Api(base, timeout=5)
    got, err = call(api.create_job, "triage", "t:one", {"x": 1})
    job, created = got or ({}, None)
    check(created is True and job.get("id") == 101 and ("POST", "/v1/jobs") in store.seen
          and store.jobs.get(101, {}).get("created_by") == qm.CREATED_BY,
          "create_job: a 201 returns the new job, created", f"{got!r} {err!r}")
    for shape in ("job_id", "detail", "bare"):
        store.conflict = shape
        key = f"t:dup-{shape}"
        first, _ = call(api.create_job, "triage", key, {})
        before = len(store.seen)
        got, err = call(api.create_job, "triage", key, {})
        again, created = got or ({}, None)
        lookup = ("GET", "/v1/jobs") in store.seen[before:]
        check(first is not None and created is False and again.get("id") == first[0]["id"]
              and lookup == (shape == "bare"),
              f"create_job: a 409 {'by ' + shape if shape != 'bare' else 'bare'} adopts the "
              f"existing id{' through the list lookup' if shape == 'bare' else ''}",
              f"{got!r} {err!r} seen={store.seen[before:]}")
    store.conflict = "job_id"

    store.fail_next = "store unavailable: disk full"
    _, err = call(api.get_job, 101)
    check(isinstance(err, qm.ApiError) and err.status == 500 and "disk full" in err.body
          and "disk full" in str(err),
          "a 500 raises ApiError carrying the response body", repr(err))

    body = {"class": "triage", "idempotency_key": "t:one", "payload": {}}
    got, err = call(api.request, "POST", "/v1/jobs", body, allow=(409,))
    status, obj = got or (None, {})
    _, raised = call(api.request, "POST", "/v1/jobs", body)
    check(status == 409 and obj.get("job_id") == 101
          and isinstance(raised, qm.ApiError) and raised.status == 409,
          "allow=(409,) returns the 409 and its body; without it the 409 raises",
          f"got={got!r} err={err!r} raised={raised!r}")

    _, err = call(qm.Api(f"http://127.0.0.1:{free_port()}", timeout=5).readyz)
    check(isinstance(err, qm.ApiError) and err.status == 0 and "connection failed" in err.body,
          "a refused port raises ApiError with status 0", repr(err))

    print("== seed, the claim and the ladder (--dry-run's canned agent) ==")
    state = home / "state"
    journal = qm.Journal(state, echo=False)
    st = qm.RunState(api=api, runner=qm.AgentRunner(state, journal, True), journal=journal,
                     max_api_usd=1.0, dry_run=True)
    ids, err = call(qm.seed, st)
    ids = ids or {}
    keys = sorted(s.key for s in qm.SEEDED_JOBS)
    check(sorted(ids) == keys and len(set(ids.values())) == 4
          and all(i in store.jobs for i in ids.values()),
          "seed creates the four mock jobs on the store", f"{ids!r} {err!r}")
    again, err = call(qm.seed, st)
    log = (state / "orchestrator.log").read_text()
    check(again == ids and log.count('"job_adopted"') == 4,
          "a second seed adopts the same four ids by their 409s", f"{again!r} {err!r}")

    spec = {s.key: s for s in qm.SEEDED_JOBS}
    store.refuse_claims = True
    out, err = call(qm.run_ladder, st, spec["B"], ids.get("B", 0))
    store.refuse_claims = False
    out = out or {}
    log = (state / "orchestrator.log").read_text()
    check(out.get("outcome") == "claim_failed" and '"claim_failed"' in log
          and store.transitions.get(ids.get("B")) == [],
          "claimed: false ends the ladder as claim_failed, journalled, no transition",
          f"{out!r} {err!r}")

    out, err = call(qm.run_ladder, st, spec["A"], ids.get("A", 0))
    out = out or {}
    check(out.get("outcome") == "accepted" and out.get("tier") == "junior"
          and store.jobs.get(ids.get("A"), {}).get("status") == "done",
          "job A climbs to accepted at junior, and the store holds it done", f"{out!r} {err!r}")
    trs = store.transitions.get(ids.get("A"), [])
    check(len(trs) == 1 and trs[0]["to"] == "done" and trs[0]["from"] == "leased"
          and trs[0]["lease_token"] == store.leases.get(ids.get("A")),
          "  with one done transition carrying the claim's lease token", f"{trs!r}")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="test-queue-http.")
    saved = {k: os.environ.get(k) for k in ("HOME", "no_proxy", "NO_PROXY")}
    server = None
    try:
        os.environ["HOME"] = tmp
        # loopback only: no proxy from the environment or the system's settings
        for k in [k for k in os.environ if k.lower().endswith("_proxy")]:
            del os.environ[k]
        os.environ["no_proxy"] = os.environ["NO_PROXY"] = "*"
        qm = load()
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server.store = Store()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        rc = main(qm, pathlib.Path(tmp), "http://127.0.0.1:%d" % server.server_address[1],
                  server.store)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(rc)
