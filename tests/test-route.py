#!/usr/bin/env python3
"""Tests for agentroute.

Runs the real router as a subprocess against two stub backends (an "upstream" and a
"local" one) on loopback, so routing, header policy, the local-only adjustments,
streaming pass-through, pings, count_tokens, the ledger, and --check are all exercised
with no network, no key, and no model.

    tests/test-route.py
"""
from __future__ import annotations

import http.client
import http.server
import json
import os
import pathlib
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
ROUTER = REPO / "plugin" / "lib" / "agentroute"
# the router runs under this suite's interpreter: the pin under make (a-s9)
PY = sys.executable

# Every router this suite starts with Popen is listed here and stopped in the finally around
# main(), so a check that raises mid-suite cannot leave one running, and a SIGTERM (which would
# skip a finally) is turned into SystemExit first. The `--serve` calls made with
# subprocess.run need no entry: run() kills its child on a timeout or an exception.
ROUTERS: list[subprocess.Popen] = []


def stop_routers() -> None:
    for proc in ROUTERS:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

passed = failed = 0


def check(cond: bool, desc: str, detail: str = "") -> None:
    global passed, failed
    if cond:
        print(f"  PASS  {desc}")
        passed += 1
    else:
        print(f"  FAIL  {desc}\n     {detail}")
        failed += 1


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------------- stubs
SSE = (b'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_1","type":"message","role":"assistant",'
       b'"model":"MODEL","content":[],"usage":{"input_tokens":100,"cache_read_input_tokens":50,"cache_creation_input_tokens":0,"output_tokens":0}}}\n\n'
       b'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n'
       b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"OK"}}\n\n'
       b'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n'
       b'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":7}}\n\n'
       b'event: message_stop\ndata: {"type":"message_stop"}\n\n')


class Stub(http.server.BaseHTTPRequestHandler):
    """Records every request on the class; answers like an Anthropic-format backend."""
    protocol_version = "HTTP/1.1"
    seen: list = []
    name = "stub"
    models = ["stub:q8", "other:tag"]

    def log_message(self, *a):
        pass

    def _record(self, body):
        type(self).seen.append({"method": self.command, "path": self.path,
                                "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})

    def do_HEAD(self):
        self._record(None)
        self.send_response(200); self.send_header("content-length", "0"); self.end_headers()

    def do_GET(self):
        self._record(None)
        if self.path.startswith("/api/version"):
            out = json.dumps({"version": "0.33.2"}).encode()
        elif self.path.startswith("/api/tags"):
            out = json.dumps({"models": [{"name": m} for m in type(self).models]}).encode()
        else:
            out = b"{}"
        self.send_response(200); self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n)
        body = json.loads(raw) if raw else {}
        self._record(body)
        delay = float(body.get("stub_delay") or self.headers.get("x-stub-delay") or 0)
        if delay:
            time.sleep(delay)
        if body.get("model") == "err:model":
            out = json.dumps({"type": "error", "error": {"type": "invalid_request_error", "message": "nope"}}).encode()
            self.send_response(400); self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out); return
        if body.get("stream"):
            die_after = int(body.get("stub_die_after") or self.headers.get("x-stub-die-after") or 0)
            self.send_response(200); self.send_header("content-type", "text/event-stream")
            self.send_header("transfer-encoding", "chunked"); self.end_headers()
            for i, part in enumerate(SSE.replace(b"MODEL", body.get("model", "?").encode()).split(b"\n\n")):
                if not part:
                    continue
                if die_after and i >= die_after:      # simulate an OOM / model eviction
                    # a half-written chunk header, then a hard close: what a dying
                    # inference server actually leaves on the wire
                    try:
                        self.wfile.write(b"ff\r\n"); self.wfile.flush()
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    try:
                        self.connection.close()
                    except OSError:
                        pass
                    self.close_connection = True
                    return
                chunk = part + b"\n\n"
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk)); self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n"); self.wfile.flush(); return
        out = json.dumps({"id": "msg_1", "type": "message", "role": "assistant", "model": body.get("model"),
                          "content": [{"type": "text", "text": "OK"}], "stop_reason": "end_turn",
                          "usage": {"input_tokens": 100, "output_tokens": 7}}).encode()
        self.send_response(200); self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)


class UpstreamStub(Stub):
    seen = []
    name = "upstream"


class LocalStub(Stub):
    seen = []
    name = "local"


class MlxStub(Stub):
    """A second local backend (non-Ollama shape: /v1/models only)."""
    seen = []
    name = "mlx"
    models = ["qwen-mlx-8bit"]

    def do_GET(self):
        self._record(None)
        if self.path.startswith("/api/"):
            self.send_response(404); self.send_header("content-length", "0"); self.end_headers(); return
        out = json.dumps({"data": [{"id": m} for m in type(self).models]}).encode()
        self.send_response(200); self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)


def start(handler, port):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def request(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    h = {"content-type": "application/json"}
    h.update(headers or {})
    raw = json.dumps(body).encode() if body is not None else None
    c.request(method, path, body=raw, headers=h)
    r = c.getresponse()
    data = r.read()
    hdrs = {k.lower(): v for k, v in r.getheaders()}
    c.close()
    return r.status, hdrs, data


def wait_port(port, secs=5.0) -> bool:
    end = time.time() + secs
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def main() -> int:
    up_port, loc_port, rt_port, mlx_port = free_port(), free_port(), free_port(), free_port()
    start(UpstreamStub, up_port)
    start(LocalStub, loc_port)
    start(MlxStub, mlx_port)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="agentroute-test-"))
    env = dict(os.environ,
               AGENTROUTE_LISTEN=f"127.0.0.1:{rt_port}",
               AGENTROUTE_UPSTREAM=f"http://127.0.0.1:{up_port}",
               AGENTROUTE_LOCAL_URL=f"http://127.0.0.1:{loc_port}",
               AGENTROUTE_LOCAL_MODEL="stub:q8",
               AGENTROUTE_LOCAL_AUTH="Bearer test-local-key",
               AGENTROUTE_BACKENDS=json.dumps({"mlx": {"url": f"http://127.0.0.1:{mlx_port}", "model": "qwen-mlx-8bit", "auth": "Bearer mlx-key"},
                                               "llama": {"url": f"http://127.0.0.1:{mlx_port}", "model": "qwen-mlx-8bit", "fold_system": True}}),
               AGENTROUTE_LOCAL_MAX_TOKENS="100",
               AGENTROUTE_PING_AFTER_S="0.5", AGENTROUTE_PING_EVERY_S="0.3",
               AGENTROUTE_STATE_DIR=str(tmp), AGENTROUTE_LOG=str(tmp / "requests.jsonl"))
    proc = subprocess.Popen([PY, str(ROUTER), "--serve"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ROUTERS.append(proc)
    check(wait_port(rt_port), "router comes up on its loopback port")

    def ledger(min_rows: int | None = None, timeout: float = 3.0):
        """Rows so far. The server appends AFTER the last chunk reaches the client, so a
        read straight after a request can race the write; pass min_rows to wait for it."""
        p = tmp / "requests.jsonl"
        end = time.time() + timeout
        while True:
            rows = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
            if min_rows is None or len(rows) >= min_rows or time.time() > end:
                return rows
            time.sleep(0.02)

    # The server appends its ledger row AFTER the last byte reaches the client, so a read
    # straight after a response can return the PREVIOUS request's row. row_after() takes the
    # count from BEFORE the request; waiting for "the length I just read" is a no-op, and it
    # produced a load-dependent flake that reported the wrong backend.
    def row_after(n_before, timeout=5.0):
        rows = ledger(min_rows=n_before + 1, timeout=timeout)
        assert len(rows) > n_before, f"no ledger row appeared within {timeout}s"
        return rows[-1]

    # Every request records how many rows existed before it was sent, so last_row() can wait
    # for a row that belongs to THAT request. Without this, a read straight after a response
    # returns the previous request's row whenever the machine is busy, which is why the suite
    # flaked only under `make test` and never in isolation.
    _send = globals()["request"]   # the local `def request` below shadows the name for the
    _pre = {"n": 0}                # whole function, so take the module-level one explicitly

    def request(*a, **kw):                     # noqa: F811 - deliberate local shadow
        _pre["n"] = len(ledger())
        return _send(*a, **kw)

    def last_row(timeout=5.0):
        return row_after(_pre["n"], timeout=timeout)

    SECRET = "sk-an" "t-oat01-THISISASEATTOKEN-abcdefghijklmnop"  # split: the hygiene secret group
    base_body = {"model": "claude-opus-5", "max_tokens": 32000, "stream": False,
                 "system": [{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}],
                 "messages": [{"role": "user", "content": "hi"},
                              {"role": "system", "content": [{"type": "text", "text": "<total_tokens>999 tokens left</total_tokens>"}]}]}

    print("== upstream: verbatim pass-through keeps the seat ==")
    UpstreamStub.seen.clear()
    st, hd, data = request(rt_port, "POST", "/v1/messages?beta=true", base_body,
                           {"Authorization": f"Bearer {SECRET}", "anthropic-beta": "oauth-2025-04-20,claude-code-20250219",
                            "anthropic-version": "2023-06-01", "x-claude-code-session-id": "sess-1"})
    seen = UpstreamStub.seen[-1]
    check(st == 200 and json.loads(data)["content"][0]["text"] == "OK", "upstream response relayed", f"{st} {data[:80]!r}")
    check(seen["path"] == "/v1/messages?beta=true", "path and query forwarded", seen["path"])
    check(seen["headers"].get("authorization") == f"Bearer {SECRET}", "Authorization forwarded byte-for-byte")
    check(seen["headers"].get("anthropic-beta") == "oauth-2025-04-20,claude-code-20250219", "anthropic-beta forwarded verbatim")
    check(seen["body"] == base_body, "upstream body untouched (reminder kept, max_tokens kept, no effort injected)",
          json.dumps(seen["body"])[:200])
    rows = ledger(min_rows=1)
    check(rows and rows[-1]["route"] == "upstream" and rows[-1]["session_id"] == "sess-1", "ledger row: route=upstream with session id",
          json.dumps(rows[-1:])[:200])
    check(SECRET not in (tmp / "requests.jsonl").read_text() and rows[-1]["auth_prefix"] == f"Bearer {SECRET}"[:12],
          "ledger never holds the credential (12-char prefix only)")
    check(rows[-1].get("usage", {}).get("input_tokens") == 100, "usage parsed from a non-streaming upstream body", str(rows[-1].get("usage")))

    print("== local: routing by model name ==")
    for model, want in (("stub:q8", "stub:q8"), ("local/default", "stub:q8"), ("local/other:tag", "other:tag")):
        LocalStub.seen.clear()
        b = dict(base_body, model=model)
        st, hd, data = request(rt_port, "POST", "/v1/messages?beta=true", b, {"Authorization": f"Bearer {SECRET}", "x-api-key": "k"})
        seen = LocalStub.seen[-1] if LocalStub.seen else {"body": {}, "headers": {}}
        check(st == 200 and seen["body"].get("model") == want, f"{model} -> local backend as {want}", f"{st} got {seen['body'].get('model')}")
    check("authorization" in seen["headers"] and seen["headers"]["authorization"] == "Bearer test-local-key",
          "seat credential NOT forwarded to the local backend; AGENTROUTE_LOCAL_AUTH injected instead", str(seen["headers"].get("authorization")))
    check("x-api-key" not in seen["headers"], "x-api-key stripped on local routes")

    print("== local: an UNDECLARED backend name is an error, not the default ==")
    LocalStub.seen.clear(); MlxStub.seen.clear()
    st, hd, data = request(rt_port, "POST", "/v1/messages", dict(base_body, model="local/typo"))
    body_txt = data.decode("utf-8", "replace")
    check(st == 404 and not LocalStub.seen and not MlxStub.seen,
          "local/<undeclared> returns 404 and reaches NO backend (silently serving the default "
          "made a whole measurement run report the wrong model)", f"{st} local={len(LocalStub.seen)} mlx={len(MlxStub.seen)}")
    check("typo" in body_txt and "localrig up" in body_txt and "default" in body_txt,
          "  the 404 names the bad backend, what IS declared, and how to add it", body_txt[:200])
    check(last_row()["route"] == "local-unknown-backend" and last_row()["status"] == 404,
          "  ledger records the rejection", json.dumps(last_row())[:160])

    print("== routing: Claude model ids that contain a colon stay upstream ==")
    for model in ("anthropic.claude-3-5-sonnet-20241022-v2:0", "claude-sonnet-4-5:beta"):
        UpstreamStub.seen.clear(); LocalStub.seen.clear()
        request(rt_port, "POST", "/v1/messages", dict(base_body, model=model), {"Authorization": f"Bearer {SECRET}"})
        check(len(UpstreamStub.seen) == 1 and not LocalStub.seen,
              f"{model} -> upstream (a colon does not make it local)",
              f"upstream={len(UpstreamStub.seen)} local={len(LocalStub.seen)}")

    print("== local headers: allow-list, so a NEW credential header cannot leak ==")
    LocalStub.seen.clear()
    request(rt_port, "POST", "/v1/messages", dict(base_body, model="stub:q8"),
            {"Authorization": f"Bearer {SECRET}", "x-api-key": "k", "Cookie": f"sessionKey={SECRET}",
             "x-gateway-token": "gw-secret", "anthropic-auth-token": "future-oat-token",
             "anthropic-beta": "oauth-2025-04-20", "x-claude-code-agent-id": "agent-9"})
    hdrs = LocalStub.seen[-1]["headers"]
    leaked = [k for k in ("cookie", "x-gateway-token", "anthropic-auth-token", "x-api-key") if k in hdrs]
    check(not leaked, "no unlisted header reaches the local backend (Cookie / custom / future auth)", f"leaked: {leaked}")
    check(hdrs.get("authorization") == "Bearer test-local-key" and hdrs.get("anthropic-beta") == "oauth-2025-04-20"
          and hdrs.get("x-claude-code-agent-id") == "agent-9",
          "  the backend's own auth and the allow-listed headers still arrive", str(hdrs.get("authorization")))
    check(SECRET not in json.dumps(hdrs), "  the seat token appears nowhere in what the backend saw")
    check(seen["path"] == "/v1/messages", "local path normalised to /v1/messages (no ?beta)", seen["path"])
    check(not UpstreamStub.seen or all("stub:q8" not in json.dumps(s["body"]) for s in UpstreamStub.seen),
          "local requests never reach the upstream")

    print("== rig: multiple local backends by model name ==")
    for model, want_backend, want_model, want_auth in (
            ("local/mlx", MlxStub, "qwen-mlx-8bit", "Bearer mlx-key"),
            ("local/mlx/other-8bit", MlxStub, "other-8bit", "Bearer mlx-key"),
            ("local/llama", MlxStub, "qwen-mlx-8bit", None),
            ("local/default", LocalStub, "stub:q8", "Bearer test-local-key"),
            ("local/stub:q8", LocalStub, "stub:q8", "Bearer test-local-key")):
        LocalStub.seen.clear(); MlxStub.seen.clear()
        st, hd, data = request(rt_port, "POST", "/v1/messages", dict(base_body, model=model), {"Authorization": f"Bearer {SECRET}"})
        got = want_backend.seen[-1] if want_backend.seen else {"body": {}, "headers": {}}
        other = LocalStub if want_backend is MlxStub else MlxStub
        check(st == 200 and got["body"].get("model") == want_model and not other.seen,
              f"{model} -> {want_backend.name} as {want_model}", f"{st} {got['body'].get('model')} other_seen={len(other.seen)}")
        check(got["headers"].get("authorization") == want_auth, f"  auth for {model} = {want_auth}", str(got["headers"].get("authorization")))
        expected_backend = ("mlx" if model.startswith("local/mlx")
                            else "llama" if model == "local/llama" else "default")
        row = last_row()
        check(row.get("backend") == expected_backend,
              f"  ledger backend field for {model}", f"got {row.get('backend')!r}, want {expected_backend!r}")

    print("== fold_system: non-leading system messages folded for backends that need it ==")
    MlxStub.seen.clear()
    b = dict(base_body, model="local/llama")
    b["messages"] = [{"role": "user", "content": "hi"},
                     {"role": "system", "content": [{"type": "text", "text": "SessionStart hook additional context: x"}]},
                     {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
                     {"role": "user", "content": "more"},
                     {"role": "system", "content": [{"type": "text", "text": "<total_tokens>5 tokens left</total_tokens>"}]}]
    request(rt_port, "POST", "/v1/messages", b)
    got = MlxStub.seen[-1]["body"]
    check(all(m.get("role") != "system" for m in got["messages"]) and len(got["messages"]) == 3,
          "llama backend: every non-leading system message removed from messages", json.dumps(got["messages"])[:200])
    check(got["system"][-1] == {"type": "text", "text": "SessionStart hook additional context: x"} and len(got["system"]) == 2,
          "  hook context folded into the top-level system array; reminder stripped, not folded", json.dumps(got["system"])[:200])
    row = last_row()
    check(row.get("folded_system") == 1 and row.get("stripped_reminders") == 1, "  ledger: folded_system=1 stripped_reminders=1", json.dumps(row)[:200])
    LocalStub.seen.clear()
    b["model"] = "local/default"
    request(rt_port, "POST", "/v1/messages", b)
    got = LocalStub.seen[-1]["body"]
    check(sum(1 for m in got["messages"] if m.get("role") == "system") == 1 and "folded_system" not in last_row(),
          "default (Ollama) backend: non-leading system messages kept, only the reminder stripped", json.dumps(got["messages"])[:200])

    print("== local: the four adjustments ==")
    body = seen["body"]
    check(all(m.get("role") != "system" for m in body["messages"]), "<total_tokens> reminder system message stripped",
          json.dumps(body["messages"])[:200])
    check(body["system"] == base_body["system"], "top-level system array kept intact")
    check(body.get("output_config", {}).get("effort") == "low", "effort injected as low when absent", str(body.get("output_config")))
    check(body["max_tokens"] == 100, "max_tokens clamped to AGENTROUTE_LOCAL_MAX_TOKENS", str(body["max_tokens"]))
    for eff_in, eff_out in (("xhigh", "medium"), ("max", "medium"), ("medium", "medium"), ("low", "low")):
        LocalStub.seen.clear()
        b = dict(base_body, model="stub:q8", output_config={"effort": eff_in}, max_tokens=50)
        request(rt_port, "POST", "/v1/messages", b)
        got = LocalStub.seen[-1]["body"]
        check(got["output_config"]["effort"] == eff_out, f"effort {eff_in} -> {eff_out}", str(got["output_config"]))
    check(got["max_tokens"] == 50, "max_tokens below the clamp is left alone")
    # a real mid-conversation system message that is NOT the reminder must survive
    LocalStub.seen.clear()
    b = dict(base_body, model="stub:q8")
    b["messages"] = [{"role": "user", "content": "hi"}, {"role": "system", "content": "SessionStart hook additional context: x"}]
    request(rt_port, "POST", "/v1/messages", b)
    check(any(m.get("role") == "system" for m in LocalStub.seen[-1]["body"]["messages"]),
          "non-reminder system messages are kept")
    row = last_row()
    check(row["route"] == "local" and row["model_in"] == "stub:q8" and row["effort_out"] == "low" and row["stripped_reminders"] == 0,
          "ledger row carries model/effort/stripped fields", json.dumps(row)[:240])

    print("== local: count_tokens estimate ==")
    st, hd, data = request(rt_port, "POST", "/v1/messages/count_tokens?beta=true", dict(base_body, model="stub:q8"))
    check(st == 200 and isinstance(json.loads(data).get("input_tokens"), int) and json.loads(data)["input_tokens"] > 0,
          "count_tokens answered locally with an integer estimate", f"{st} {data[:80]!r}")
    check(last_row()["route"] == "local-count-estimate", "ledger row: local-count-estimate")

    print("== streaming pass-through ==")
    LocalStub.seen.clear()
    st, hd, data = request(rt_port, "POST", "/v1/messages", dict(base_body, model="stub:q8", stream=True),
                           {"x-claude-code-agent-id": "agent-7", "x-claude-code-parent-agent-id": "main-1"})
    check(st == 200 and hd.get("content-type", "").startswith("text/event-stream"), "SSE status and content-type relayed", f"{st} {hd}")
    check(data == SSE.replace(b"MODEL", b"stub:q8"), "SSE body relayed byte-exact", repr(data[:120]))
    row = last_row()
    check(row.get("usage") == {"input_tokens": 100, "output_tokens": 7, "cache_read_input_tokens": 50, "cache_creation_input_tokens": 0},
          "usage parsed from message_start + message_delta", str(row.get("usage")))
    check(row.get("agent_id") == "agent-7" and row.get("parent_agent_id") == "main-1", "agent ids recorded", json.dumps(row)[:200])
    # Timing-sensitive: under load (make test runs suites back to back) even a "fast"
    # response can cross PING_AFTER_S, and a ping then is correct behaviour, not a defect.
    fast_enough = (row.get("ttfb_s") or 0) < float(env["AGENTROUTE_PING_AFTER_S"])
    check(row.get("ttfb_s") is not None and (row.get("pinged") == 0 or not fast_enough),
          "fast response: ttfb recorded, and pings only if it actually crossed the ping threshold",
          str(row))

    print("== pings during a silent prefill ==")
    st, hd, data = request(rt_port, "POST", "/v1/messages", dict(base_body, model="stub:q8", stream=True, stub_delay=1.4))
    check(st == 200 and data.startswith(b"event: ping\n"), "router committed 200/SSE and sent ping events before the backend answered",
          repr(data[:80]))
    check(data.count(b"event: ping") >= 1 and data.endswith(SSE.replace(b"MODEL", b"stub:q8")[-40:]),
          "pings precede an otherwise intact stream", repr(data[-60:]))
    check(last_row().get("pinged", 0) >= 1, "ledger counts the pings", str(last_row().get("pinged")))

    print("== a backend that dies MID-STREAM terminates the response and is logged ==")
    st, hd, data = request(rt_port, "POST", "/v1/messages", dict(base_body, model="stub:q8", stream=True, stub_die_after=1))
    check(b"event: error" in data and b"mid-response" in data,
          "client gets an SSE error instead of a stream that never ends", repr(data[-200:]))
    row = last_row()
    check(row.get("truncated") is True and "mid-response" in (row.get("error") or ""),
          "  the ledger records the truncation (it used to record nothing at all)", json.dumps(row)[:200])

    print("== hostile bodies do not kill the request or the server ==")
    for label, b in (("tools is an int", dict(base_body, model="stub:q8", tools=5)),
                     ("messages is a string", dict(base_body, model="stub:q8", messages="hi")),
                     ("system is an int", dict(base_body, model="stub:q8", system=3))):
        try:
            st, hd, data = request(rt_port, "POST", "/v1/messages", b)
            ok = st in (200, 400, 500)
        except Exception as exc:
            ok = False; st = repr(exc)
        check(ok, f"{label}: answered rather than dropping the connection", str(st))
    st, _, _ = request(rt_port, "POST", "/v1/messages", dict(base_body, model="stub:q8"))
    check(st == 200, "  the server still serves after hostile bodies")

    print("== a chunked request body is refused, not silently dropped ==")
    c = http.client.HTTPConnection("127.0.0.1", rt_port, timeout=10)
    c.putrequest("POST", "/v1/messages"); c.putheader("content-type", "application/json")
    c.putheader("transfer-encoding", "chunked"); c.endheaders()
    payload = json.dumps({"model": "stub:q8", "messages": [{"role": "user", "content": "hi"}]}).encode()
    c.send(b"%x\r\n%s\r\n0\r\n\r\n" % (len(payload), payload))
    r = c.getresponse(); body = r.read(); c.close()
    check(r.status == 411 and b"Content-Length" in body,
          "chunked body -> 411 (it used to drop the prompt and relay upstream on the seat token)",
          f"{r.status} {body[:120]!r}")

    print("== HEAD and 204 are not framed as chunked ==")
    c = http.client.HTTPConnection("127.0.0.1", rt_port, timeout=10)
    c.request("HEAD", "/v1/messages", headers={"content-length": "0"})
    r = c.getresponse(); r.read(); te = r.getheader("transfer-encoding"); c.close()
    check(te is None, "HEAD carries no transfer-encoding", str(te))

    print("== malformed config is survivable ==")
    for label, extra in (("backend value is a string", {"AGENTROUTE_BACKENDS": '{"mlx": "http://127.0.0.1:9"}'}),
                         ("backend value is null", {"AGENTROUTE_BACKENDS": '{"mlx": null}'}),
                         ("max_tokens is not a number", {"AGENTROUTE_LOCAL_MAX_TOKENS": "lots"}),
                         ("ping interval is not a number", {"AGENTROUTE_PING_AFTER_S": "soon"})):
        r = subprocess.run([PY, str(ROUTER), "--check"], env=dict(env, **extra), capture_output=True, text=True)
        check("Traceback" not in r.stderr and r.returncode in (0, 1),
              f"{label}: --check reports instead of crashing at import", (r.stderr or r.stdout)[:200])
    r = subprocess.run([PY, str(ROUTER), "--serve"], env=dict(env, AGENTROUTE_LISTEN="127.0.0.1"),
                       capture_output=True, text=True, timeout=10)
    check(r.returncode == 2 and "host:port" in r.stderr, "LISTEN without a port is refused clearly", r.stderr[:160])

    print("== backend error relayed ==")
    st, hd, data = request(rt_port, "POST", "/v1/messages", dict(base_body, model="err:model"))
    check(st == 400 and b"invalid_request_error" in data, "non-200 backend status and body relayed when not yet committed", f"{st} {data[:80]!r}")
    check(last_row()["status"] == 400 and "nope" in last_row().get("error", ""), "ledger row records the error")
    # committed (pinging) then error: the client gets an SSE error event, not a hang
    st, hd, data = request(rt_port, "POST", "/v1/messages", dict(base_body, model="err:model", stream=True, stub_delay=0.9))
    check(st == 200 and b"event: error" in data and b"backend 400" in data, "error after commit arrives as an SSE error event", repr(data[-160:]))

    print("== /api/hello answered locally ==")
    UpstreamStub.seen.clear()
    st, hd, data = request(rt_port, "HEAD", "/api/hello")
    check(st == 200 and not UpstreamStub.seen, "HEAD /api/hello -> 200 without touching the upstream", f"{st} {len(UpstreamStub.seen)}")

    print("== --check ==")
    r = subprocess.run([PY, str(ROUTER), "--check"], env=env, capture_output=True, text=True)
    check(r.returncode == 0 and "backend default" in r.stdout and "ollama 0.33.2" in r.stdout and "backend mlx" in r.stdout
          and "qwen-mlx-8bit present on mlx" in r.stdout, "--check passes against healthy stubs and probes every backend",
          r.stdout + r.stderr)
    r2 = subprocess.run([PY, str(ROUTER), "--check"], env=dict(env, AGENTROUTE_LOCAL_MODEL="missing:model"), capture_output=True, text=True)
    check(r2.returncode == 1 and "missing on default: missing:model" in r2.stdout, "--check fails closed when the model is not served", r2.stdout)
    dead = json.dumps({"mlx": {"url": f"http://127.0.0.1:{free_port()}", "model": "x"}})
    r4 = subprocess.run([PY, str(ROUTER), "--check"], env=dict(env, AGENTROUTE_BACKENDS=dead), capture_output=True, text=True)
    check(r4.returncode == 0 and "warn  backend mlx" in r4.stdout and "optional backend" in r4.stdout,
          "--check only warns when a NON-default backend is down", r4.stdout)
    # backends file: used when the env var is absent; a "default" key overrides LOCAL_URL/LOCAL_MODEL
    bf = tmp / "backends.json"
    bf.write_text(json.dumps({"default": {"url": f"http://127.0.0.1:{mlx_port}", "model": "qwen-mlx-8bit", "auth": "Bearer mlx-key"}}))
    env_file = {k: v for k, v in env.items() if k != "AGENTROUTE_BACKENDS"}
    env_file["AGENTROUTE_BACKENDS_FILE"] = str(bf)
    r5 = subprocess.run([PY, str(ROUTER), "--check"], env=env_file, capture_output=True, text=True)
    check(r5.returncode == 0 and "qwen-mlx-8bit present on default" in r5.stdout,
          "backends file's default key becomes local/default when the env var is unset", r5.stdout)

    print("== bind policy ==")
    r3 = subprocess.run([PY, str(ROUTER), "--serve"], env=dict(env, AGENTROUTE_LISTEN=f"0.0.0.0:{free_port()}"),
                        capture_output=True, text=True, timeout=10)
    check(r3.returncode == 2 and "loopback" in r3.stderr, "refuses to bind a non-loopback address", r3.stderr)

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    check(not (tmp / "agentroute.pid").exists(), "pidfile removed on SIGTERM")

    print("== the folders: the new one, else the old one while it alone exists, else the new ==")
    # agentik-r1 6.3 c17 (state) and c19 (config), read at import; AGENTROUTE_STATE_DIR wins.
    probe = ("import runpy; g = runpy.run_path(%r, run_name='probe'); "
             "print(g['STATE_DIR']); print(g['BACKENDS_FILE'])" % str(ROUTER))
    with tempfile.TemporaryDirectory() as fd:
        x = pathlib.Path(fd)
        base = {k: v for k, v in os.environ.items()
                if not k.startswith("AGENTROUTE_") and not k.startswith("XDG_")}
        base.update(XDG_STATE_HOME=str(x / "state"), XDG_CONFIG_HOME=str(x / "config"))

        def folders(extra=None) -> list[str]:
            out = subprocess.run([PY, "-c", probe], env=dict(base, **(extra or {})),
                                 capture_output=True, text=True, timeout=30).stdout
            return [os.path.relpath(line, fd) for line in out.split()]
        new = ["state/agentik-agents/route", "config/agentik/agents/route/backends.json"]
        old = ["state/agentroute", "config/agentroute/backends.json"]
        check(folders() == new, "neither folder: the new ones", str(folders()))
        (x / "state" / "agentroute").mkdir(parents=True)
        (x / "config" / "agentroute").mkdir(parents=True)
        check(folders() == old, "only the old folders: the old ones", str(folders()))
        (x / "state" / "agentik-agents" / "route").mkdir(parents=True)
        (x / "config" / "agentik" / "agents" / "route").mkdir(parents=True)
        check(folders() == new, "both: the new ones", str(folders()))
        check(folders({"AGENTROUTE_STATE_DIR": str(x / "pinned")})[0] == "pinned",
              "AGENTROUTE_STATE_DIR still wins")
        check(not (x / "pinned").exists(), "importing the router makes no folder")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(128 + signal.SIGTERM))
    try:
        rc = main()
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)   # a second TERM must not cut the cleanup short
        stop_routers()
    sys.exit(rc)
