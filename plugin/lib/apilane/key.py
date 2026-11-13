#!/usr/bin/python3
"""The API lane's key: a SOPS store with age, at `roots.store`.

The store holds one YAML key, `anthropic_api_key`, the one the old wrapper wrote, so a store it
left reads as it is. The value reaches `sops` on its stdin only: never an argument, a file of its
own or a log line. It is encrypted for the recipient given, else for the one `age-keygen -y`
prints for the identity `sops` itself uses; this module never opens that identity, the child
does. `load` decrypts into memory. An `ANTHROPIC_API_KEY` in the caller's environment is never
read, and nothing here falls back to a plaintext file.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

YAML_KEY = "anthropic_api_key"
RECIPIENT = re.compile(r"age1[0-9a-z]{6,}\Z")
TIMEOUT = 120


class KeyStoreError(Exception):
    """An error a user may see: `code` and `fields`; `str()` is the code."""

    def __init__(self, code, **fields):
        super().__init__(code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


def present(roots):
    return os.path.isfile(roots.store)


def remove(roots):
    try:
        os.unlink(roots.store)
    except FileNotFoundError:
        return False
    return True


def load(roots):
    """The key, decrypted into memory."""
    if not present(roots):
        raise KeyStoreError("key.none", store=roots.store)
    sops = _tool("sops")
    run = _run([sops, "decrypt", "--extract", '["%s"]' % YAML_KEY, "--", roots.store])
    if run.returncode != 0:
        raise KeyStoreError("key.decrypt", rc=run.returncode)
    value = run.stdout.decode("utf-8", "replace").strip()
    if not value:
        raise KeyStoreError("key.none", store=roots.store)
    return value


def store(value, *, roots, recipient=None):
    """Encrypt `value` into the store, by a temp file and a rename, 0600 in a 0700 folder."""
    value = value.strip()
    if not value or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in value):
        raise ValueError("key.store: the value is empty or holds a control character")
    sops = _tool("sops")
    recipient = recipient if recipient is not None else _derive_recipient(roots)
    if not RECIPIENT.match(recipient):
        raise KeyStoreError("key.recipient")
    folder = os.path.dirname(roots.store)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chmod(folder, 0o700)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".store-", suffix=".tmp")
    try:
        doc = "%s: '%s'\n" % (YAML_KEY, value.replace("'", "''"))
        with os.fdopen(fd, "wb") as out:
            run = subprocess.run([sops, "encrypt", "--age", recipient, "--input-type", "yaml",
                                  "--output-type", "yaml", "/dev/stdin"],
                                 input=doc.encode("utf-8"), stdout=out,
                                 stderr=subprocess.DEVNULL, cwd=folder, timeout=TIMEOUT)
        del doc
        if run.returncode != 0:
            raise KeyStoreError("key.decrypt", rc=run.returncode)
        with open(tmp, "rb") as handle:
            body = handle.read()
        if b"ENC[" not in body:
            raise KeyStoreError("key.decrypt", rc=run.returncode)
        os.chmod(tmp, 0o600)
        os.replace(tmp, roots.store)
    except subprocess.TimeoutExpired:
        raise KeyStoreError("key.decrypt", rc="timeout")
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _tool(name):
    path = shutil.which(name)
    if path is None:
        raise KeyStoreError("key.tools", tool=name)
    return path


def _run(argv):
    try:
        return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise KeyStoreError("key.decrypt", rc="timeout")


def _identity_file(home):
    """Where `sops` looks for its age identity: SOPS_AGE_KEY_FILE, else its platform default."""
    named = os.environ.get("SOPS_AGE_KEY_FILE")
    if named:
        return named
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "sops", "age", "keys.txt")
    return os.path.join(home, ".config", "sops", "age", "keys.txt")


def _derive_recipient(roots):
    keygen = _tool("age-keygen")
    run = _run([keygen, "-y", _identity_file(roots.home)])
    if run.returncode != 0:
        raise KeyStoreError("key.recipient")
    lines = run.stdout.decode("utf-8", "replace").split()
    return lines[0] if len(lines) == 1 else ""
