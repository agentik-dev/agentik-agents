## Local agent lane credentials

No setup is required to start. Run `claude-local` and the lane works with no key configured anywhere. If `localrig` finds no llama key in the environment or in sops, it generates a random one for that run. It hands that key to `llama-server` through a 0600 file, and writes the same value into the router's `backends.json`. That is safer than a shared fixed key: the value is never reused and never written anywhere shared. `localrig` prints a one-line note on how to persist it, if you choose to.

### What these keys are, and are not

They are not cloud credentials. They authenticate this Mac's own inference servers to this Mac's own router, both over loopback. The threat they address is a stray process on the same machine posting prompts to a model server that is listening locally. The router strips the seat's own credential before it reaches a local backend and substitutes the backend's key. That seat credential never reaches a local backend at all.

The keys live in `secrets/local-backends.sops.yaml`, encrypted with sops using age, with two entries: `llama_api_key` and `unsloth_api_key`. Only the values are encrypted, so a diff shows which secret changed without showing it. Recipients and the `encrypted_regex` live in `.sops.yaml`. The encrypted file is safe to commit. The age private key is not: it lives at `~/.config/sops/age/keys.txt`, mode 600, backed up in the password manager.

Resolution order, per key:

1. The environment variable (`LOCALRIG_LLAMA_KEY` for llama, `LOCALRIG_UNSLOTH_KEY` for unsloth) wins if it is set.
2. Otherwise, sops, decrypted only at the moment the key is needed.
3. Otherwise, a fallback: a fresh random key for llama, or the key Unsloth Studio printed to its own log for unsloth. This is the last resort before an error.

`localrig keys status` shows which source is in play per key, plus the stored value's length. It never shows the value itself.

### Commands

| Command | What it does | When to use it |
| --- | --- | --- |
| `localrig keys status` | Prints each key's source (environment, sops, or unset) and whether a value is stored, with its length. Never prints the value. | Check where a key is coming from, e.g. before debugging a 401. |
| `localrig keys init` | Generates a llama key and stores it in sops if none exists. Idempotent: if one is already stored, it says so and points to `set` instead. | First time you want a persistent llama key instead of a per-run random one. |
| `localrig keys set llama` / `localrig keys set unsloth` | Prompts for the value with input hidden, then writes it to sops. The value goes in on stdin, never in argv, so it never appears in `ps` or shell history. | Rotating a key, or entering one you already have. |
| `localrig keys sync-unsloth` | Captures the key Unsloth Studio printed once into its own log at first start, and stores it in sops. | After a fresh Unsloth Studio start, so a rebuild does not have to scrape the log again. |
| `localrig down llama` then `localrig up llama` | Restarts the llama backend so it picks up a changed key. | Right after `keys set llama` or `keys init`. |
| `localrig restart-router` | Restarts the router, which otherwise keeps the old key because it reads `backends.json` only at startup. | Right after any key change, alongside restarting the backend. |

### First-time setup on a new machine

1. Install sops and age: `brew install sops age`.
2. Put your age private key at `~/.config/sops/age/keys.txt`, mode 600. For a new identity, generate it with `age-keygen -o ~/.config/sops/age/keys.txt`. Then print the public half with `age-keygen -y` and add that line to `.sops.yaml`.
3. If you added a new recipient, re-wrap the existing secrets so that key can read them: `sops updatekeys secrets/local-backends.sops.yaml`. Run this only from a machine that can already decrypt the file. Adding a recipient to `.sops.yaml` alone does nothing for files that already exist.
4. Verify: `localrig keys status` should show `llama_api_key` sourced from sops.
5. Optional: run `localrig keys init` if no llama key is stored yet.

### One secret this machine still cannot decrypt

Neither of the two age recipients originally in `.sops.yaml` can decrypt anything on this Mac. sops reports `no master key was able to decrypt the file`, which is what `make doctor` flags as a failed decrypt check.

This machine's own age identity was added as a recipient on 2026-09-05. Because of that, `secrets/local-backends.sops.yaml`, created after the change, decrypts normally here. `secrets/anthropic-api-key.sops.yaml` predates the change and is still unreadable on this machine. Fixing it needs either `sops updatekeys` run from a machine holding one of the older keys, or rotating the secret with `claude-api-agent --setup-key`. Nothing in the local lane depends on this file.

### Rotation and revocation

Rotate a local key with `localrig keys set`, then restart the backend that uses it (see Commands above). No external service needs notifying.

Removing a person's age recipient from `.sops.yaml` stops future re-encryptions from including them. It does not retract what they already hold: the old ciphertext stays in git history, and their key still unwraps it. Actually retiring a local key means rotating it, which is cheap here because these credentials are local and self-issued.

### Verified behaviour

The key `llama-server` loads matches the sops value byte for byte. It is passed with `--api-key-file`, so it never appears in the process argv. A wrong key gets HTTP 401. The sops key gets HTTP 200. A call routed to local/llama returns from the right backend, and the key never appears in the router's ledger.

`tests/test-localrig.sh` asserts source precedence, that `status` never prints a value, and that the plaintext is absent from the ciphertext on disk. It also asserts that a missing secrets file still leaves the lane working.
