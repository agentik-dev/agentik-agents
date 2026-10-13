#!/usr/bin/python3
"""agentroute — prototype model-name router for Claude Code (stdlib only).

Claude Code -> http://127.0.0.1:8787 -> { local backend (Anthropic-format /v1/messages)
                                        | https://api.anthropic.com (headers forwarded verbatim) }
Routing key: the request body's `model`.  A model is LOCAL when it is listed in
AGENTROUTE_LOCAL_MODELS (comma list), or starts with "local/" (prefix stripped), or
contains ":" (an Ollama tag).  Everything else is forwarded to the upstream untouched,
so a claude.ai seat login keeps working (Authorization + anthropic-beta pass through).
count_tokens for a local model is answered with a chars/4 estimate (Ollama has no endpoint).
Every request is logged as one JSON line to AGENTROUTE_LOG (headers + body *shape*, no content).
"""
import http.client, http.server, json, os, socketserver, ssl, sys, time, urllib.parse

LISTEN   = os.environ.get("AGENTROUTE_LISTEN", "127.0.0.1:8787")
LOCAL    = os.environ.get("AGENTROUTE_LOCAL_URL", "http://127.0.0.1:11434")
UPSTREAM = os.environ.get("AGENTROUTE_UPSTREAM", "https://api.anthropic.com")
LOCAL_MODELS = {m.strip() for m in os.environ.get("AGENTROUTE_LOCAL_MODELS", "").split(",") if m.strip()}
LOG = os.environ.get("AGENTROUTE_LOG", "agentroute.jsonl")
HOP = {"connection","keep-alive","proxy-authenticate","proxy-authorization","te","trailer","transfer-encoding","upgrade","host","content-length","accept-encoding"}

def is_local(model):
    return bool(model) and (model in LOCAL_MODELS or model.startswith("local/") or ":" in model)

def conn_for(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme == "https":
        return http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=600, context=ssl.create_default_context()), u
    return http.client.HTTPConnection(u.hostname, u.port or 80, timeout=600), u

def shape(body):
    """Body skeleton for the log: keys, sizes, tool names, thinking/effort — never content."""
    if not isinstance(body, dict): return {"raw_len": len(body) if body else 0}
    s = {"keys": sorted(body.keys()), "model": body.get("model"), "stream": body.get("stream"),
         "max_tokens": body.get("max_tokens"), "thinking": body.get("thinking"),
         "output_config": body.get("output_config"), "tool_choice": body.get("tool_choice"),
         "n_messages": len(body.get("messages") or []),
         "n_tools": len(body.get("tools") or []), "tools": [t.get("name") for t in (body.get("tools") or [])][:40],
         "tool_extra_keys": sorted({k for t in (body.get("tools") or []) for k in t if k not in ("name","description","input_schema")}),
         "system_len": len(json.dumps(body.get("system"))) if body.get("system") is not None else 0,
         "system_blocks": len(body["system"]) if isinstance(body.get("system"), list) else (1 if body.get("system") else 0),
         "system_cache_control": [b.get("cache_control") for b in body["system"] if isinstance(b, dict)] if isinstance(body.get("system"), list) else None,
         "msgs_cache_control": sum(1 for m in (body.get("messages") or []) for b in (m.get("content") if isinstance(m.get("content"), list) else []) if isinstance(b, dict) and b.get("cache_control")),
         "system_head": (body["system"][0].get("text","")[:120] if isinstance(body.get("system"), list) and body["system"] and isinstance(body["system"][0], dict) else str(body.get("system"))[:120]),
         "body_len": len(json.dumps(body))}
    if "metadata" in body: s["metadata_keys"] = sorted(body["metadata"].keys())
    if "context_management" in body: s["context_management"] = body["context_management"]
    return s

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _read(self):
        n = int(self.headers.get("content-length") or 0)
        return self.rfile.read(n) if n else b""
    def _relay(self, target_base, path, raw, body_json, route, t0):
        conn, u = conn_for(target_base)
        hdrs = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        hdrs["host"] = u.netloc
        if raw is not None: hdrs["content-length"] = str(len(raw))
        try:
            conn.request(self.command, path, body=raw, headers=hdrs)
            resp = conn.getresponse()
        except Exception as e:
            self.send_error(502, f"upstream error: {e}"); self._log(route, path, body_json, 502, t0, str(e)); return
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in HOP: continue
            self.send_header(k, v)
        self.send_header("transfer-encoding", "chunked"); self.send_header("connection", "close")
        self.end_headers()
        n = 0; first = None
        while True:
            chunk = resp.read1(65536)
            if not chunk: break
            if first is None: first = time.time() - t0
            n += len(chunk)
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk)); self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n"); self.wfile.flush(); conn.close()
        self._log(route, path, body_json, resp.status, t0, None, n, first)
    def _log(self, route, path, body_json, status, t0, err=None, n=0, first=None):
        rec = {"ts": round(t0,3), "method": self.command, "path": path, "route": route, "status": status,
               "wall_s": round(time.time()-t0,2), "ttfb_s": round(first,2) if first else None, "resp_bytes": n,
               "headers": {k: (v if k.lower() not in ("authorization","x-api-key") else v[:12]+"…") for k, v in self.headers.items()},
               "body": shape(body_json), "err": err}
        with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    def do_HEAD(self): self._route()
    def do_GET(self): self._route()
    def do_POST(self): self._route()
    def _route(self):
        t0 = time.time(); raw = self._read() if self.command == "POST" else None
        path = self.path; p = urllib.parse.urlsplit(path).path
        body = None
        if raw:
            try: body = json.loads(raw)
            except Exception: body = None
        model = body.get("model") if isinstance(body, dict) else None
        if p.startswith("/v1/messages") and is_local(model):
            if model.startswith("local/"):
                body["model"] = model[len("local/"):]
            # SHIM (Ollama < 0.32.15 rejects non-leading `role: system` messages with
            # "system message must be at the beginning"): fold them into the top-level
            # `system` array. Lossy on position; the real fix is Ollama >= 0.33.x.
            if os.environ.get("AGENTROUTE_FOLD_SYSTEM") and isinstance(body.get("messages"), list):
                sysmsgs = [m for m in body["messages"] if m.get("role") == "system"]
                if sysmsgs:
                    sysarr = body.get("system") or []
                    if isinstance(sysarr, str): sysarr = [{"type": "text", "text": sysarr}]
                    for m in sysmsgs:
                        c = m.get("content")
                        blocks = [{"type": "text", "text": c}] if isinstance(c, str) else [b for b in c if b.get("type") == "text"]
                        for b in blocks: b.pop("cache_control", None)
                        sysarr.extend(blocks)
                    body["system"] = sysarr
                    body["messages"] = [m for m in body["messages"] if m.get("role") != "system"]
                    body["_shim_folded"] = len(sysmsgs)
            folded = body.pop("_shim_folded", 0)
            if os.environ.get("AGENTROUTE_DEBUG_SYSTEM"):
                # DEBUG ONLY: dump the full system array + message roles/first-100-chars per turn
                with open(os.environ["AGENTROUTE_DEBUG_SYSTEM"], "a") as f:
                    f.write(json.dumps({"ts": time.time(), "system": body.get("system"),
                        "messages": [{"role": m.get("role"), "head": (m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content")))[:100]} for m in body.get("messages") or []]}) + "\n")
            raw = json.dumps(body).encode()
            if folded: body["shim_system_folded"] = folded
            if p.endswith("/count_tokens"):
                est = max(1, len(raw) // 4)
                out = json.dumps({"input_tokens": est}).encode()
                self.send_response(200); self.send_header("content-type","application/json")
                self.send_header("content-length", str(len(out))); self.send_header("connection","close"); self.end_headers(); self.wfile.write(out)
                self._log("local-count-estimate", path, body, 200, t0); return
            return self._relay(LOCAL, "/v1/messages", raw, body, "local", t0)
        return self._relay(UPSTREAM, path, raw, body, "upstream", t0)

class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True; allow_reuse_address = True

if __name__ == "__main__":
    host, port = LISTEN.rsplit(":", 1)
    print(f"agentroute listening on {LISTEN}; local={LOCAL} upstream={UPSTREAM} local_models={sorted(LOCAL_MODELS)} log={LOG}", flush=True)
    S((host, int(port)), H).serve_forever()
