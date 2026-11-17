# Packet ag1-old-name-links: a tool started by an old name keeps its frozen tree through later installs

The hq's brief for row ag1-old-name-links, in this repo's packet shape.

| item | value |
|---|---|
| from | the hq's row ag1-old-name-links (its install and upgrade review of 2026-11-16, finding 8) |
| pin | main 95cfbbc, plugin 1.9.4 (ia1-new-machine merged); worktree `.claude/worktrees/ag1-old-name-links`, branch `ag1-old-name-links`; nothing linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or landing; no `claude`, no model, no router, no rig, no network; no relay verb; every probe in a temp HOME and a temp prefix with a stand-in `ps`; `make` only through the gate queue |
| may touch | `plugin/lib/agents_install.py`, `plugin/lib/agentik-agents`; `tests/test_ag1_old_names.py` (new), `tests/test-bare-machine.py`; `Makefile` (the test list); `NICE_TO_HAVE.md` (one row); `plugin/.claude-plugin/plugin.json`; this packet; a charter |
| untouched | `plugin/lib/agentik_install.py` and `plugin/bin/*` (vendored, R5), `scripts/*`, the tools' own files |
| acceptance | section 6's lines 1 to 3 |
| verify | `make check`, once, last, through `agentik session gate run`, then `gate wait --strict` |
| budget | a commit each: packet, the tests seen red, R1 to R4, 1.9.5 alone |

## 1. What the source says

The owner, 2026-11-16: "Use up to 2 Fable agents to review our upgrade/install so far. Use up to 8 opus agents to build anything to help us with install/upgrade concerns." His standing ask: "setup and doctor usable today".

The review's finding 8: an old name in the bin folder is an absolute link into one frozen tree. A process started through it has the link's path on its command line. Each later install points the link at the new tree after its prune, and the prune's `named()` resolves the process's path through the link as it points now, so the tree the process runs from counts live at the first later install only, and the third removes it.

Baseline at 95cfbbc, in a temp HOME and prefix with a stand-in `ps` showing `/usr/bin/python3 <bin>/agentroute serve`, the four old links into the first tree T0, then installs of three versions: the prune's lines `removed 0, kept 2 (1 live, ...)`, `removed 0, kept 3 (1 live, ...)`, then `prune-trees: removed 1, kept 3 (1 live, the newest 3)`, and T0 is gone; the one counted live was the tree the link pointed at.

## 2. Rulings

- R1: a process started by an old name has, on its command line as `ps` shows it, a path inside the tree it runs from, so every later prune counts that tree live while the process runs. A small file or link of ours that execs the tree's file is in scope; a link straight to the tool's file in a tree is not.
- R2: ia1's rules hold: an old name is written only where one of ours stands (`agentik_install._old_link`); a new machine gets none; a person's own file is passed over byte for byte and named as today.
- R3: a machine holding the old absolute links is moved to the new form by the next `install-cli` (this plugin has no SessionStart refresh). A process running through an old link at that moment keeps its tree through that install and the ones after it.
- R4: `make uninstall` and the suite's remove (`agentik_install.uninstall`) take the new form as ours and keep a person's file.
- R5: the vendored `agentik_install.py` is not edited. R6: `UNTIL` and its words stay.
- R7: tests first, failing at the pin, in a temp HOME and prefix with a stand-in `ps`.

## 3. Interfaces

- `agents_install.link_old(bin_dir, tree, err, names=OLD, held=())` returns `(linked, left, passed)` as ia1's; an old name's target is `<tree>/agentik-agents`; a name in `held` is not touched.
- `agents_install.held_old(bin_dir, share, names, ps="ps")`: the old names of the old form a running process names.
- `install-cli`'s stdout line for a held name: `kept <names> in <bin> -> its tree: a running process started by that name runs from it; an install after it ends moves it`.
- The dispatcher: invoked by a link named an old name, it execs `<its tree>/<name>` with the args unchanged.

The form, and why. Each old name is a link of install-cli's to the dispatcher, `<tree>/agentik-agents`, in the newest tree. Invoked under an old name, the dispatcher execs the tool beside its own resolved path, `<tree>/<name>`, so the kernel's command line for the tool names the tree. Two other forms were ruled out by the vendored module: a link to the launcher (as the session tool's old name) loses the name, since the launcher execs its runner without `$0`; and a regular file at the old name is no row of `uninstall`'s plan, which takes links alone, so the suite's remove would leave it. The new form is a link resolving into the share, which both uninstalls already take.

A link of the old form (to `<tree>/<name>`) is held where it points while a running process names `<bin>/<name>`: such a process runs from the tree the link points at, and the prune counts it live only through the link. A link of the new form is never held. A process list that cannot be read holds nothing (the prune keeps every tree then).

## 4. Findings that name this row

The review's finding 8. Filed here: NICE n64, claude-fanout (the API lane's forward) keeps the link form the old names left; the brief names the old names alone. Not built: a process started through an old link that an install before this packet already moved names no tree, so nothing can keep its tree.

## 5. Forbidden reads

The real `~/.local`, `~/.claude`, `~/.config` and anything under `~/.local/state`; a relay ledger.

## 6. Report

`T` is `tests/test_ag1_old_names.py`. Lines: 1 the finding's reproduction ends with T0 standing and the prune's last line `removed 0, kept 4 (1 live, the newest 3)` (`T` test_1, R3; test_4, R1); 2 `ls -l` of the bin folder before and after an install over old absolute links (`T` test_2); 3 `make check` green through the queue, hygiene with `--require-private --commits main..HEAD` exit 0.
