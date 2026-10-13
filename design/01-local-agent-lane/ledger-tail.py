#!/usr/bin/python3
"""ledger-tail.py <ledger> <skip_lines> — print agentroute rows after line N, compactly."""
import json, sys
path, skip = sys.argv[1], int(sys.argv[2])
for i, l in enumerate(open(path)):
    if i < skip: continue
    r = json.loads(l)
    if r.get("path", "").startswith("/api/hello"): continue
    u = r.get("usage") or {}
    print("  %-8s %-4s wall %6.1f ttfb %6s | %-22s -> %-22s | eff %6s->%-6s | strip %s | msgs %s tools %s | in %s out %s cr %s | agent %s | auth %s:%s" % (
        r.get("route"), r.get("status"), r.get("wall_s", 0) or 0, r.get("ttfb_s"), str(r.get("model_in"))[:22], str(r.get("model_out"))[:22],
        r.get("effort_in"), r.get("effort_out"), r.get("stripped_reminders", "-"), r.get("n_messages"), r.get("n_tools"),
        u.get("input_tokens"), u.get("output_tokens"), u.get("cache_read_input_tokens"), str(r.get("agent_id"))[:8], r.get("auth_kind"), (r.get("auth_prefix") or "")[:10]))
