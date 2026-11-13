"""The shard's environment: an allow-list, and nothing else passes (design/21 item 28).

Billing follows the credential: under --bare the CLI reads only ANTHROPIC_API_KEY, and
since nothing of the caller's environment is copied, no OAuth token, auth token, caller's
base URL or Node variable can arrive. ANTHROPIC_BASE_URL appears only when the caller hands
one in, which only the probe does (its loopback stub).
"""
import os

LANG = "en_US.UTF-8"
TERM = "dumb"


def build(*, key, run_dir, home, path, proxy=None, ca_file=None, base_url=None):
    if not isinstance(key, str) or not key:
        raise ValueError("key: empty")
    env = {
        "PATH": path,
        "HOME": home,
        "LANG": LANG,
        "TERM": TERM,
        "TMPDIR": os.path.join(run_dir, "tmp"),
        "CLAUDE_CONFIG_DIR": os.path.join(run_dir, "config"),
        "ANTHROPIC_API_KEY": key,
    }
    if proxy:
        env["HTTPS_PROXY"] = proxy
        env["https_proxy"] = proxy
    if ca_file:
        env["NODE_EXTRA_CA_CERTS"] = ca_file
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    return env
