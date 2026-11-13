#!/usr/bin/python3
"""The probe's loopback stub of the provider's messages endpoint.

`Stub(reads)` binds `127.0.0.1` on a port the system picks and answers `POST /v1/messages`,
streamed or whole as the request asks, with a script: one turn a path of `reads`, each asking for
one `Read` of it, then a closing text. The turn is the number of assistant messages the request
carries, so a resent conversation gets the same answer. For each request it records the header
names that carried a credential and their values, the tools offered, the tool results sent
back, its turn and its body, all in memory. It serves nothing else and binds no other address.
"""

import http.server
import json
import threading

HOST = "127.0.0.1"
PATH = "/v1/messages"
CREDENTIAL_HEADERS = ("x-api-key", "authorization", "proxy-authorization", "cookie")
CREDENTIAL_WORDS = ("key", "token", "auth", "secret")


def _credential(name):
    name = name.lower()
    return name in CREDENTIAL_HEADERS or any(w in name for w in CREDENTIAL_WORDS)


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


class Stub:
    def __init__(self, reads, text="probe done"):
        self.reads = list(reads)
        self.text = text
        self.requests = []
        self.address = None
        self._lock = threading.Lock()
        self._server = None
        self._thread = None

    @property
    def url(self):
        return "http://%s:%d" % self.address

    def start(self):
        server = http.server.ThreadingHTTPServer((HOST, 0), _Handler)
        server.daemon_threads = True
        server.stub = self
        self._server = server
        self.address = server.server_address[:2]
        self._thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1},
                                        daemon=True)
        self._thread.start()
        return self.url

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(10)
            self._server = None

    def record(self, headers, body, raw):
        messages = body.get("messages") or []
        last = messages[-1] if messages else {}
        results = []
        if isinstance(last, dict) and isinstance(last.get("content"), list):
            for block in last["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    results.append({"tool_use_id": block.get("tool_use_id"),
                                    "text": _text_of(block.get("content")),
                                    "is_error": bool(block.get("is_error"))})
        turn = sum(1 for m in messages if isinstance(m, dict) and m.get("role") == "assistant")
        rec = {"credentials": {k.lower(): v for k, v in headers.items() if _credential(k)},
               "tools": [t.get("name") for t in body.get("tools") or [] if isinstance(t, dict)],
               "tool_results": results, "turn": turn, "body": raw}
        with self._lock:
            self.requests.append(rec)
            number = len(self.requests)
        return number, turn

    def reply(self, number, turn, model):
        """The script's message for this turn."""
        if turn < len(self.reads):
            block = {"type": "tool_use", "id": "toolu_stub_%d_%d" % (number, turn),
                     "name": "Read", "input": {"file_path": self.reads[turn]}}
            stop = "tool_use"
        else:
            block = {"type": "text", "text": self.text}
            stop = "end_turn"
        return {"id": "msg_stub_%d" % number, "type": "message", "role": "assistant",
                "model": model, "content": [block], "stop_reason": stop, "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1}}


def _events(message):
    """The streamed form of a whole message, as (event, data) pairs."""
    block = message["content"][0]
    head = dict(message, content=[], stop_reason=None)
    yield "message_start", {"type": "message_start", "message": head}
    if block["type"] == "tool_use":
        start = dict(block, input={})
        delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
    else:
        start = {"type": "text", "text": ""}
        delta = {"type": "text_delta", "text": block["text"]}
    yield "content_block_start", {"type": "content_block_start", "index": 0,
                                  "content_block": start}
    yield "content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta}
    yield "content_block_stop", {"type": "content_block_stop", "index": 0}
    yield "message_delta", {"type": "message_delta",
                            "delta": {"stop_reason": message["stop_reason"],
                                      "stop_sequence": None},
                            "usage": {"output_tokens": 1}}
    yield "message_stop", {"type": "message_stop"}


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "stub"

    def log_message(self, *args):
        pass

    def _nothing(self):
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = do_HEAD = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _nothing

    def _body(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            parts = []
            while True:
                size = int(self.rfile.readline().split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    self.rfile.readline()
                    return b"".join(parts)
                parts.append(self.rfile.read(size))
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def do_POST(self):
        if self.path.split("?", 1)[0] != PATH:
            self._nothing()
            return
        raw = self._body().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            self.send_response(400)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        stub = self.server.stub
        number, turn = stub.record(dict(self.headers.items()), body, raw)
        message = stub.reply(number, turn, body.get("model") or "stub")
        if body.get("stream"):
            out = "".join("event: %s\ndata: %s\n\n" % (ev, json.dumps(data))
                          for ev, data in _events(message)).encode()
            kind = "text/event-stream"
        else:
            out, kind = json.dumps(message).encode(), "application/json"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(out)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(out)
