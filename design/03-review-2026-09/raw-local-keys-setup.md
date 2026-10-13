# Raw material: setting up local backend credentials (input to respeak)

Audience: the repo owner on a new machine, or a second person given access. Purpose: a
setup guide for the local agent lane's credentials. Goes in the README as a section.

## What these keys are and are not

They are not cloud credentials. They authenticate this Mac's own inference servers to this
Mac's router, both on loopback. The threat they address is a stray process on the same
machine posting prompts to a model server that is listening locally. The seat's own
credential never reaches a local backend; the router strips it and substitutes the
backend's key.

## The zero-setup path

Nothing is required to start. Run claude-local and the lane works. If no llama key is found
in the environment or in sops, localrig generates a random one for that run, hands it to
llama-server through a file, and puts the same value in the router's backends.json. This is
stronger than the fixed literal it replaced, because the value is never reused and never
written to a shared place. localrig prints a one-line note saying how to persist it.

## Where keys live

secrets/local-backends.sops.yaml, encrypted with sops using age. Two entries: llama_api_key
and unsloth_api_key. Only the values are encrypted, so a diff shows which secret changed
without showing it. Recipients and the encrypted_regex are in .sops.yaml. The file is safe
to commit; the age private keys are not and live at ~/.config/sops/age/keys.txt, mode 600,
backed up in the password manager.

## Resolution order, per key

1. The environment variable, LOCALRIG_LLAMA_KEY or LOCALRIG_UNSLOTH_KEY. Useful for a
   one-off or for CI, and it wins over everything.
2. sops, decrypted at the moment it is needed and never written to disk in the clear except
   the 0600 file llama-server reads.
3. For llama only, a per-run random key. For unsloth, the key its own server printed once
   into its log, which is the last resort before an error.

localrig keys status shows which source is in play per key, plus the length, and never the
value.

## Commands

localrig keys status. Prints each key name, its source (environment, sops, or unset), and
whether a value is stored with its length. Never prints a value.

localrig keys init. Generates a llama key and stores it in sops if there is none. Idempotent:
if one is already stored it says so and tells you to use set to rotate.

localrig keys set llama, or localrig keys set unsloth. Prompts for the value with the input
hidden, then writes it to sops. The value reaches sops on stdin, never in argv, so it does
not appear in ps or in shell history.

localrig keys sync-unsloth. Unsloth Studio generates its own key at first start and prints
it once into its log. This captures the running server's key into sops so a rebuild does not
have to scrape the log again.

After changing a key, restart the backend that uses it: localrig down llama, then
localrig up llama. The running router also needs localrig restart-router, because it reads
backends.json once at start.

## First-time setup on a new machine

1. Install sops and age: brew install sops age.
2. Put your age private key at ~/.config/sops/age/keys.txt, mode 600. If this is a new
   identity, generate it with age-keygen -o ~/.config/sops/age/keys.txt, then print the
   public half with age-keygen -y and add that line to .sops.yaml.
3. If you added a new recipient, re-wrap the existing secrets so the new key can read them:
   sops updatekeys secrets/local-backends.sops.yaml. This must be run from a machine that can
   already decrypt the file. Adding a recipient to .sops.yaml alone does nothing to files
   that already exist.
4. Verify: localrig keys status should show llama_api_key sourced from sops.
5. Optional: localrig keys init if no llama key is stored yet.

## A caveat recorded rather than hidden

On this Mac, neither of the two age recipients that were originally in .sops.yaml could
decrypt anything. sops reported that no master key was able to decrypt the file, which is
what make doctor reports as a failed decrypt check. This machine's age identity was added as
a recipient on 2026-09-05, so secrets/local-backends.sops.yaml, created after that change,
decrypts normally. secrets/anthropic-api-key.sops.yaml predates the change and is still
unreadable here. It needs either sops updatekeys run from a machine holding one of the older
keys, or rotation with claude-api-agent --setup-key. Nothing in the local lane depends on it.

## Rotation and revocation

Rotating a local key is localrig keys set, then restarting that backend. There is no
external service to notify. Removing a person's age recipient from .sops.yaml stops future
re-encryptions from including them, but does not retract what they already hold, because
the old ciphertext remains in git history and their key still unwraps it. Actually retiring
a local key means rotating it, which is cheap here precisely because these credentials are
local and self-issued.

## Verified behaviour

The key llama-server loads matches the sops value byte for byte. It is passed with
--api-key-file, so it is absent from the process argv. A wrong key gets HTTP 401 and the
sops key gets 200. A call routed to local/llama returns from the right backend, and the key
never appears in the router's ledger. tests/test-localrig.sh asserts the source precedence,
that status never prints a value, that the plaintext is absent from the ciphertext on disk,
and that a missing secrets file leaves the lane working.
