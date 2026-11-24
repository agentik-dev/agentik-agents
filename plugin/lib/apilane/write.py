"""The lane's git for its writing type, `implement` (design/32 B6, B7, E15, F19 to F22).

A writing job names one repo the user file's `api.write_repos` lists and a local branch to
start from. The plan checks both and that the worktree's path and the job id's branch are
free; after the reservation the lane makes `<repo>/.claude/worktrees/<id>` on a branch `<id>`,
outside the wall; after the shard it lists what the shard changed, refuses the whole run on a
nested `.git`, a gated file, anything but a regular file or a file holding a key, else adds
exactly those paths, commits them under the repo's own git identity and compares the commit
with the list. Every git here runs as `G`: hooks and the fsmonitor off, pathspecs literal.
The lane never pushes, merges, fetches or removes a worktree. Nothing here prints: a function
returns a record or raises a `WriteError` with a `code` and `fields` (seams section 2).
"""
import fnmatch
import os
import shlex
import stat
import subprocess

G_FLAGS = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "--literal-pathspecs")
STATUS = ("status", "--porcelain", "-z", "--no-renames", "--untracked-files=all",
          "--ignored=matching", "--ignore-submodules=all")
# The environment's git variables that would point a git at another repo, index or tree.
GIT_ENV_DROPPED = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE",
                   "GIT_PREFIX", "GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS",
                   "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS")
GATED_NAMES = ("claude.md", "decisions.md", "settings.json", "settings.local.json", "edit-gates")
KEY_PREFIX = b"AGE-SECRET-KEY-1"
# A changed path that runs outside a wall at a check: read before any check runs (E16). GNU make
# reads `GNUmakefile` and `makefile` before `Makefile`.
CHECK_TOPS = ("scripts", ".claude", ".github")
MAKE_NAMES = ("Makefile", "makefile", "GNUmakefile")
GLOB = frozenset("*?[")
TIMEOUT_SEC = 120
LIST_CAP = 64 * 1024     # a list's bytes read, at most, as the session plugin reads one


class WriteError(Exception):
    def __init__(self, code, **fields):
        Exception.__init__(self, code)
        self.code = code
        self.fields = fields

    def __str__(self):
        return self.code


def _git():
    for d in ("/usr/bin", "/usr/local/bin", "/opt/homebrew/bin", "/bin"):
        p = os.path.join(d, "git")
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return "git"


def G(path, *args):
    """The argv of one of the lane's gits at `path`."""
    return [_git()] + list(G_FLAGS) + ["-C", path] + list(args)


def _env():
    env = dict(os.environ)
    for k in GIT_ENV_DROPPED:
        env.pop(k, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(path, *args):
    """(rc, stdout bytes, stderr text) of `G path args`."""
    try:
        p = subprocess.run(G(path, *args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=_env(), timeout=TIMEOUT_SEC)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, b"", str(e)
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")


def _first(text):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return lines[0] if lines else ""


def writing(job):
    """True when the job's one shard is of a writing type."""
    from apilane import job as _job
    return any(_job.writes(s.type) for s in job.shards)


def repo_state(path):
    """`ok`, `missing` or `not-top` for a listed repo, by real path. A repo whose `.git` is no
    folder (a linked worktree, a submodule) is `not-top`: the lane nests no worktree in one."""
    real = os.path.realpath(path)
    if not os.path.isdir(real):
        return "missing"
    dotgit = os.path.join(real, ".git")
    if os.path.islink(dotgit) or not os.path.isdir(dotgit):
        return "not-top"
    rc, out, _err = git(real, "rev-parse", "--show-toplevel")
    if rc != 0 or os.path.realpath(os.fsdecode(out.strip())) != real:
        return "not-top"
    return "ok"


def _branch_sha(repo, name):
    rc, out, _err = git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/%s^{commit}" % name)
    return out.decode().strip() if rc == 0 and out.strip() else None


def _local_branch(repo, name):
    """The sha of the local branch `name`, or None where `name` is anything but a branch's own
    name: `git check-ref-format --branch` refuses it, or no exact `refs/heads/<name>` exists, so
    `main~1`, `main^`, `main@{1}` and `main^{commit}` are refused as a tag or a sha is."""
    if not isinstance(name, str) or not name or name.startswith("-"):
        return None
    rc, out, _err = git(repo, "check-ref-format", "--branch", name)
    if rc != 0 or out.decode("utf-8", "replace").strip() != name:
        return None
    rc, _out, _err = git(repo, "show-ref", "--verify", "--quiet", "refs/heads/" + name)
    return _branch_sha(repo, name) if rc == 0 else None


def plan(job, lane, roots):
    """The plan's checks of a writing job (A4, B6, B7), in order; the place it would make."""
    listed = tuple(getattr(lane, "write_repos", ()) or ())
    if not listed:
        raise WriteError("write.off", config=roots.config)
    real = os.path.realpath(job.repo)
    if not os.path.isabs(job.repo) or real not in [os.path.realpath(r) for r in listed]:
        raise WriteError("write.repo", repo=job.repo, why="unlisted")
    state = repo_state(real)
    if state != "ok":
        raise WriteError("write.repo", repo=job.repo, why=state)
    from_sha = _local_branch(real, job.from_branch)
    if from_sha is None:
        raise WriteError("write.from", repo=real, **{"from": job.from_branch})
    tree = os.path.join(real, ".claude", "worktrees", job.id)
    if os.path.lexists(tree):
        raise WriteError("write.taken", path=tree, id=job.id)
    if _branch_sha(real, job.id) is not None:
        raise WriteError("write.taken", path="branch " + job.id, id=job.id)
    return {"repo": real, "worktree": tree, "branch": job.id, "from": job.from_branch,
            "from_sha": from_sha}


def make(w, check_dirs=None, home=None):
    """The worktree step, after the reservation (B6): None when made, else its reason."""
    rc, _out, err = git(w["repo"], "worktree", "add", w["worktree"], "-b", w["branch"], w["from"])
    if rc != 0:
        return "worktree:" + (_first(err) or "git exit %d" % rc)
    try:   # the wall's rule for a linked .git covers the link alone (agents' n76)
        mode = os.lstat(os.path.join(w["worktree"], ".git")).st_mode
    except OSError:
        mode = 0
    if not stat.S_ISREG(mode):
        return "worktree:.git is not a regular file"
    if check_dirs is not None:
        try:
            check_dirs([w["worktree"]], home=home)
        except Exception as e:   # noqa: BLE001 -- the wall's refusal is the shard's reason
            return "worktree:%s" % getattr(e, "code", type(e).__name__)
    return None


# -- the list, and what refuses it (E15 a to d) ---------------------------------------------

def listing(tree):
    """(changed, ignored, deleted): the paths `G status` lists, worktree-relative."""
    rc, out, err = git(tree, *STATUS)
    if rc != 0:
        raise WriteError("write.list", path=tree, why=_first(err))
    changed, ignored, deleted = [], [], []
    for entry in out.split(b"\0"):
        if len(entry) < 4:
            continue
        xy, rel = entry[:2], os.fsdecode(entry[3:])
        if xy == b"!!":
            ignored.append(rel)
        else:
            changed.append(rel)
            if b"D" in xy:
                deleted.append(rel)
    return changed, ignored, deleted


def _parts(rel):
    return [p for p in rel.split("/") if p]


def _folds(tree):
    """True where the volume folds case: `.GIT` names the worktree's `.git`."""
    return os.path.lexists(os.path.join(tree, ".GIT"))


def _walk(tree, rel):
    """Every entry under a listed folder, by `lstat`, never through a link."""
    top = os.path.join(tree, rel.rstrip("/"))
    found = []
    for root, dirs, files in os.walk(top, followlinks=False):
        for name in dirs + files:
            found.append(os.path.relpath(os.path.join(root, name), tree))
    return found


def _gitpart(rel):
    return any(x.lower() == ".git" for x in _parts(rel))


def nested(tree, changed, ignored):
    """R10 b: each listed path with a `.git` part in any case, each listed folder, and each
    `.git` found under a listed folder by `lstat`, never through a link."""
    bad = []
    for rel in changed + ignored:
        name = rel.rstrip("/")
        p = os.path.join(tree, name)
        if _gitpart(rel) or rel.endswith("/"):
            bad.append(name)
        if os.path.isdir(p) and not os.path.islink(p):
            bad.append(name)
            bad += [r for r in _walk(tree, name) if _gitpart(r)]
    return sorted(set(bad))


def _gate_lines(path):
    """A list's lines as the session plugin reads them: stripped, an empty line or one that
    starts with `#` dropped; a `#` anywhere else is part of the line."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(LIST_CAP)
    except OSError:
        return []
    out = []
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _relative(line):
    """A repo's or a folder's line as it matches, or None for one that matches nothing: a
    leading `./` stripped, then one starting with `/` or `~`, or holding a `..` part."""
    while line.startswith("./"):
        line = line[2:]
    if not line or line.startswith("/") or line.startswith("~") or ".." in line.split("/"):
        return None
    return line


def _seg(pats, segs):
    if not pats:
        return not segs
    if pats[0] == "**":
        return any(_seg(pats[1:], segs[i:]) for i in range(len(segs) + 1))
    return bool(segs) and fnmatch.fnmatchcase(segs[0], pats[0]) and _seg(pats[1:], segs[1:])


def _match(name, pat, fold=False):
    """One grammar: a line with no glob is one file; `*`, `?` and a bracket stay in a segment,
    a segment that is `**` is any depth, none included."""
    if fold:
        name, pat = name.casefold(), pat.casefold()
    return name == pat or (bool(GLOB & set(pat)) and _seg(pat.split("/"), name.split("/")))


def gate_match(line, rel, fold=False):
    """One line of a repo's or a folder's edit-gates list against a path relative to it."""
    line = line.strip()
    if not line or line.startswith("#"):
        return False
    pat = _relative(line)
    return pat is not None and _match(rel, pat, fold)


def _inside(a, homes):
    return any(a.startswith(h.rstrip("/") + "/") and a != h for h in homes)


def _homes(home):
    return {os.path.abspath(home), os.path.realpath(home)} if home else set()


def gate_lists(repo, home):
    """Each `(folder, its list)` above the repo and strictly inside the home, nearest first, as
    the session plugin walks them: a folder with a checkout above it holds no folder list, and
    only a list that exists is read."""
    homes = _homes(home)
    dirs, d = [], os.path.dirname(repo)
    while _inside(d, homes):
        dirs.append(d)
        d = os.path.dirname(d)
    gits = [os.path.lexists(os.path.join(x, ".git")) for x in dirs]
    out = []
    for i, d in enumerate(dirs):
        lf = os.path.join(d, ".claude", "edit-gates")
        if any(gits[i + 1:]) or not os.path.lexists(lf):
            continue
        out.append((d, [r for r in map(_relative, _gate_lines(lf)) if r is not None]))
    return out


def user_lines(home):
    """The user's own list, `<home>/.claude/edit-gates`: its lines that start with `/` or `~/`,
    read against the home folder; a relative line there matches nothing."""
    if not home:
        return []
    out = []
    for line in _gate_lines(os.path.join(home, ".claude", "edit-gates")):
        if line.startswith("~/"):
            out.append(os.path.normpath(home.rstrip("/") + "/" + line[2:]))
        elif line.startswith("/"):
            out.append(os.path.normpath(line))
    return out


def gated(tree, repo, home, changed):
    """R10 c: each changed path the lane's fixed names hold, or that the session plugin's
    matcher would gate as the file `<repo>/<rel>`, the worktree's own list read as the repo's:
    the repo's list matches `rel`, a folder's list the path from that folder, and the user's
    list the absolute path. Written here; nothing is imported from another plugin."""
    fold = _folds(tree)
    mine = _gate_lines(os.path.join(tree, ".claude", "edit-gates"))
    above = gate_lists(repo, home)
    user = user_lines(home)
    bad = []
    for rel in changed:
        parts = _parts(rel)
        low = [p.lower() for p in parts]
        p = os.path.join(repo, rel)
        if (low and low[-1] in GATED_NAMES) or "hooks" in low[:-1] \
                or any(gate_match(l, rel, fold) for l in mine) \
                or any(_match(p[len(d):].lstrip("/"), x, fold) for d, lines in above
                       for x in lines) \
                or any(_match(p, q, fold) for u in user
                       for q in ({u} if GLOB & set(u) else {u, os.path.realpath(u)})):
            bad.append(rel)
    return bad


def odd(tree):
    """(strange, gits): every entry of the worktree but its own `.git` that is no folder, file
    or link, since git's list never names a FIFO, a socket or a device (R11 d); and every
    `.git` below its top, in any case (R10 b)."""
    strange, gits = [], []
    for root, dirs, files in os.walk(tree, followlinks=False):
        if root == tree:
            dirs[:] = [d for d in dirs if d != ".git"]
            files = [f for f in files if f != ".git"]
        for name in dirs + files:
            p = os.path.join(root, name)
            rel = os.path.relpath(p, tree)
            if name.lower() == ".git":
                gits.append(rel)
            try:
                mode = os.lstat(p).st_mode
            except OSError:
                continue
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode)):
                strange.append(rel)
    return strange, gits


def kinds(tree, changed, key):
    """R11 d: (kind, leak): each changed path not a regular file nor a deletion; each regular
    file holding the key's value or an age key's prefix, opened without following a link."""
    kind, leak = [], []
    needles = [KEY_PREFIX] + ([key.encode()] if key else [])
    for rel in changed:
        p = os.path.join(tree, rel)
        try:
            mode = os.lstat(p).st_mode
        except FileNotFoundError:
            continue                    # a deletion
        if not stat.S_ISREG(mode):
            kind.append(rel)
            continue
        try:
            fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            kind.append(rel)
            continue
        with os.fdopen(fd, "rb") as fh:
            if not stat.S_ISREG(os.fstat(fh.fileno()).st_mode):
                kind.append(rel)
                continue
            data = fh.read()
        if any(n in data for n in needles):
            leak.append(rel)
    return kind, leak


def _control(rel):
    return any(ord(c) < 0x20 or ord(c) == 0x7f for c in rel)


def shown(rel):
    """A path as a line or a record names it: each control character as `\\xNN`, so no path
    can start a line of its own."""
    return "".join("\\x%02x" % ord(c) if ord(c) < 0x20 or ord(c) == 0x7f else c for c in rel)


def _shown_rec(rec):
    for k in ("paths", "ignored", "check", "refused", "committed"):
        if isinstance(rec.get(k), list):
            rec[k] = [shown(x) for x in rec[k]]
    return rec


def check_paths(changed, ignored):
    """The changed paths that run outside a wall at a check (E16)."""
    out = []
    for rel in changed:
        parts = _parts(rel)
        if (parts and parts[-1] in MAKE_NAMES) or (parts and parts[0] in CHECK_TOPS) \
                or (parts and parts[-1].startswith(".git")):
            out.append(rel)
    return out


# -- the commit (E15 d to g, F22) --------------------------------------------------------------

def commit_paths(tree, paths, message):
    """`G add -- <paths>`, then `G commit`: (ok, git's first stderr line)."""
    rc, _o, err = git(tree, "add", "--", *paths)
    if rc != 0:
        return False, _first(err) or "git add exit %d" % rc
    rc, _o, err = git(tree, "commit", "-q", "-m", message[0], "-m", message[1])
    if rc != 0:
        return False, _first(err) or "git commit exit %d" % rc
    return True, None


def head(tree):
    rc, out, _e = git(tree, "rev-parse", "HEAD")
    return out.decode().strip() if rc == 0 else None


def committed(tree):
    rc, out, _e = git(tree, "show", "--name-only", "-z", "--no-renames", "--format=", "HEAD")
    return sorted(os.fsdecode(p) for p in out.split(b"\0") if p) if rc == 0 else []


def settle(w, *, state, label, run, key=None, home=None, commit_step=None):
    """After the shard (R10, R11): the record R12 names. A refused run commits nothing and
    leaves the worktree as it is; the shard's `state` stands but for `empty` and `leak`. A
    changed or ignored path holding a control character is `refused:kind`, and every path the
    record names is `shown`."""
    return _shown_rec(_settle(w, state=state, label=label, run=run, key=key, home=home,
                              commit_step=commit_step))


def _settle(w, *, state, label, run, key, home, commit_step):
    rec = dict(w, head=w.get("from_sha"), paths=[], ignored=[], commit="none", refused=[],
               state=state)
    tree = w["worktree"]
    if state in ("wall", "leak"):
        return rec
    try:
        changed, ignored, _deleted = listing(tree)
    except WriteError as e:
        rec.update(commit="refused:git", error=e.fields.get("why"))
        return rec
    rec.update(paths=sorted(changed), ignored=sorted(ignored),
               check=check_paths(changed, ignored))
    bad = sorted(r for r in changed + ignored if _control(r))
    if bad:
        rec.update(commit="refused:kind", refused=bad)
        return rec
    strange, gits = odd(tree)
    bad = sorted(set(nested(tree, changed, ignored) + gits))
    if bad:
        rec.update(commit="refused:nested", refused=bad)
        return rec
    bad = gated(tree, w["repo"], home, changed)
    if bad:
        rec.update(commit="refused:gated", refused=bad)
        return rec
    kind, leak = kinds(tree, changed, key)
    kind = sorted(set(kind + strange))
    if kind:
        rec.update(commit="refused:kind", refused=kind)
        return rec
    if leak:
        rec.update(state="leak", refused=sorted(leak))
        return rec
    if not changed:
        if state == "ok":
            rec["state"] = "empty"
        return rec
    message = ("%s: %s" % (w["branch"], label),
               "api lane implement, run %s, state %s" % (run, state))
    ok, err = (commit_step or commit_paths)(tree, sorted(changed), message)
    if not ok:
        rec.update(commit="refused:git", error=err)
        return rec
    rec["head"] = head(tree)
    got = committed(tree)
    if set(got) != set(changed):
        rec.update(commit="refused:mismatch", committed=got)
        return rec
    rec["commit"] = "ok"
    return rec


def lost(rec, home=None, key=None):
    """A writing run that left its worktree uncommitted (F19): its changed paths, and the two
    lines a person runs, or the removal alone where a path would be refused as `settle`
    refuses it: nested, gated, a control character, anything but a regular file, or a file
    holding a key. The leak scan looks for the key's value where the caller holds one, and for
    an age key's prefix always; the doctor and `fanout status` hold no key, so there the prefix
    scan alone runs. A record `settle` refused as a leak stays refused."""
    tree, repo = rec.get("worktree"), rec.get("repo")
    if not tree or not repo or not os.path.isdir(tree):
        return None
    try:
        changed, ignored, _d = listing(tree)
    except WriteError:
        changed, ignored = [], []
    refused = rec.get("state") == "leak" or any(_control(r) for r in changed + ignored)
    if not refused:
        strange, gits = odd(tree)
        kind, leak = kinds(tree, changed, key)
        refused = bool(nested(tree, changed, ignored) or gits or gated(tree, repo, home, changed)
                       or kind or leak or strange)
    remove = "git -C %s worktree remove --force %s" % (shlex.quote(repo), shlex.quote(tree))
    lines = [remove]
    if changed and not refused:
        g = " ".join(["git"] + [shlex.quote(a) for a in G(tree)[1:]])
        lines = ["%s add -- %s && %s commit" % (
            g, " ".join(shlex.quote(c) for c in sorted(changed)), g), remove]
    return {"worktree": tree, "repo": repo, "paths": sorted(shown(c) for c in changed),
            "lines": lines, "refused": bool(refused)}
