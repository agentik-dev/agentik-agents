#!/usr/bin/python3
import json, urllib.request, time, sys
M = sys.argv[1] if len(sys.argv) > 1 else "qwen3.8:27b-mtp-q8_0"
def gen(prompt, think, n=300):
    body = {"model": M, "prompt": prompt, "stream": False, "think": think,
            "options": {"num_predict": n}}
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate",
        data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    t = time.time(); r = json.load(urllib.request.urlopen(req, timeout=600)); w = time.time() - t
    pe = r.get("prompt_eval_count", 0); ped = r.get("prompt_eval_duration", 1) / 1e9
    ec = r.get("eval_count", 0); ed = r.get("eval_duration", 1) / 1e9
    print(f"{M} think={think!s:5} wall={w:6.1f}s prefill={pe} tok @ {pe/ped:6.1f} tok/s  gen={ec} tok @ {ec/ed:5.1f} tok/s  load={r.get('load_duration',0)/1e9:.1f}s")
    return r
gen("Write a 250-word essay on the history of the NAS product line.", False)
gen("Return ONLY a JSON object with keys name, path, lines for the files: /etc/hosts (11 lines), /etc/passwd (120 lines), /etc/group (90 lines) as an array under key files.", False, 200)
gen("What is 17*23? Answer with the number only.", "low", 400)
