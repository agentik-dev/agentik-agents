"""install-cli for agentik-agents (hq design/04 section 3, packet a-s18), run by the dispatcher's
`install-cli` verb under Python.

The canonical install (agentik_install, beside this file) freezes this lib/, writes the launcher
and the `agentik` door. Then each old name, agentroute, claude-agents, claude-local and localrig,
is refreshed to a link to the dispatcher in the frozen tree, by a temp link and a rename, only
where a link of that name already stands in the bin dir, as agentik_install._old_link rules it: a
new machine gets none (packet ia1-new-machine). Run by an old name, the dispatcher execs the tool
beside it by its real path, so the process's command line names its tree and every later prune
counts that tree live (packet ag1-old-name-links). A link of the form before that packet, straight
to the tool's file in a tree, stays where it points while a running process names it by its path
in the bin dir and that tree still stands: the prune counts that process's tree live through the
link alone. They stay until
2026-12-31. A person's own file under one of the names
is left byte for byte and named in one stderr line, exit 0. While the API lane is on, a fifth,
claude-fanout, links to the lane's forward on any machine (packet al6, design/21 item 12), and a
path of that name that is not a link is left and named, exit 1; while the lane is off, a path of
that name is not touched.
Where a newer command install-cli placed stands, nothing is written and no link moves: the one
line install_cli() prints for that case says so, exit 0; `--force` places this tree over it.
Exit 0 done; 1 it could not, the reason on stderr (GUIDE section 10). Stdlib, 3.9.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import agentik_install  # noqa: E402

OLD = ("agentroute", "claude-agents", "claude-local", "localrig")
UNTIL = "2026-12-31"


# install_cli()'s line where a newer command is kept, with this verb's --force named (commons'
# agentik_install, row up3-forward-only); tests/test_ag1_old_names.py holds the two equal.
KEPT = "Left %s at %s, newer than this plugin's %s; --force places it."

FORWARD = "claude-fanout"
# What an old name links to in the tree: the dispatcher, which execs the tool by its real path.
DISPATCHER = "agentik-agents"
_NAME_CHAR = r"[A-Za-z0-9._-]"


def held_old(bin_dir, share, names=OLD, ps="ps"):
    """The old names whose link is the form before packet ag1-old-name-links, to `<tree>/<name>`
    in the share, and that a running process names by its path in bin_dir: the process runs from
    that tree, which the prune counts live only while the link resolves there (R3). A link to the
    dispatcher is never held; a process list that cannot be read holds none. It runs after the
    prune, so a link whose target the prune removed is never held: it moves like any other (a
    process the prune could not see, such as one whose path holds a space, has lost its tree)."""
    root = os.path.realpath(share).rstrip("/") + "/"
    old = []
    for name in names:
        path = os.path.join(bin_dir, name)
        real = os.path.realpath(path)
        if (os.path.islink(path) and real.startswith(root) and os.path.basename(real) == name
                and os.path.exists(real)):
            old.append(name)
    if not old:
        return set()
    text, _why = agentik_install.processes(ps)
    if text is None:
        return set()
    here = os.path.realpath(bin_dir)
    found = set()
    for token in set(re.findall(agentik_install._PATHS, text)):
        head, base = os.path.split(token)
        if base in old and os.path.realpath(head or "/") == here:
            found.add(base)
    for name in old:        # its path as spelled, which a folder with a space keeps whole
        if re.search(re.escape(os.path.join(bin_dir, name)) + "(?!%s)" % _NAME_CHAR, text):
            found.add(name)
    return found


def lane_on(err):
    """Whether the API lane is on: a wall proved here and the lane's file says on. No wall is off,
    saying nothing (review 1, R1-F2), so an old claude-fanout link stays where it points. A
    refusal is off; a refused file is one line on stderr."""
    try:
        from apilane import config, paths, wall
        if wall.backend() is None:
            return False
        return bool(config.lane(paths.account()).enabled)
    except ImportError:
        return False
    except Exception as e:  # noqa: BLE001 -- a refusal is off; a refused file is said
        if not isinstance(getattr(e, "code", None), str):
            raise
        if e.code != "config.fault":
            return False
        from apilane import messages
        print(messages.say(e.code, **(getattr(e, "fields", None) or {})), file=err)
        return False


def link_old(bin_dir, tree, err, names=OLD, held=()):
    """Each name in bin_dir to the tree: an old name to the dispatcher there, only where its link
    stands already and is not in `held`; claude-fanout to its own file, wherever no file holds it.
    (linked, left, passed): the names linked, those it could not link, and the old names a
    person's own file holds, left as they are."""
    linked, left, passed = [], [], []
    # The freeze writes 0644 but for the runner and the door, and the dispatcher runs each tool
    # from the tree whether its old name links or not (a1 F1): every chmod before any link. An old
    # name runs the dispatcher itself, so it is made executable too.
    old = [n for n in names if n in OLD]
    for name in ([DISPATCHER] if old else []) + list(names):
        try:
            os.chmod(os.path.join(tree, name), 0o755)
        except OSError as e:
            print("install-cli: %s: %s" % (os.path.join(tree, name), e), file=err)
            left.extend(old if name == DISPATCHER else [name])
    for name in names:
        path = os.path.join(bin_dir, name)
        target = os.path.join(tree, DISPATCHER if name in OLD else name)
        if name in left or name in held:
            continue
        if name in OLD and not agentik_install._old_link(bin_dir, name):
            if os.path.lexists(path):
                passed.append(name)
            continue
        if os.path.lexists(path) and not os.path.islink(path):
            print("install-cli: %s is not a link, left as it is; %s is not linked" % (path, name),
                  file=err)
            left.append(name)
            continue
        temp = os.path.join(bin_dir, ".%s.%d.tmp" % (name, os.getpid()))
        try:
            if os.path.lexists(temp):
                os.unlink(temp)
            os.symlink(target, temp)
            os.replace(temp, path)
        except OSError as e:
            try:
                os.unlink(temp)
            except OSError:
                pass
            print("install-cli: %s: %s" % (path, e), file=err)
            left.append(name)
            continue
        linked.append(name)
    return linked, left, passed


def main(argv=None, out=sys.stdout, err=sys.stderr, lane=None):
    parser = argparse.ArgumentParser(prog="agentik-agents install-cli",
                                     description="Freeze this plugin's lib/, write the launcher, "
                                     "the agentik door and the old names' links.")
    parser.add_argument("--prefix", help="the install's root (default ~/.local)")
    parser.add_argument("--force", action="store_true",
                        help="place this plugin's command over a newer one install-cli placed")
    args = parser.parse_args(argv)
    try:
        done = agentik_install.install(args.prefix, force=args.force)
    except (OSError, KeyError, ValueError) as e:
        print("install-cli: %s" % e, file=err)
        return 1
    if done["kept"]:
        # a newer command stands: nothing was written and no old name's link moves (row sy3-sync
        # R3); the line is agentik_install.install_cli's for that case, its words and its format
        print(KEPT % (agentik_install.shown(done["launcher"]), done["kept"], done["version"]),
              file=out)
        return 0
    print("installed %s -> %s (%s); %s" % (done["launcher"], done["tree"], done["version"],
                                          done["door"]), file=out)
    for line in done["pruned"]:
        print(line, file=out)
    bin_dir = os.path.dirname(done["launcher"])
    names = OLD + (FORWARD,) if (lane_on(err) if lane is None else lane) else OLD
    held = held_old(bin_dir, os.path.dirname(done["tree"]))
    linked, left, passed = link_old(bin_dir, done["tree"], err, names, held)
    if held:
        print("kept %s in %s -> its tree: a running process started by that name runs from it; "
              "an install after it ends moves it" % (", ".join(n for n in OLD if n in held), bin_dir),
              file=out)
    if passed:
        print("install-cli: left %s in %s as it is: not a link, so no old name's to refresh"
              % (", ".join(passed), agentik_install.shown(bin_dir)), file=err)
    if linked:
        print("linked %s in %s -> the tree (the old names, until %s)"
              % (", ".join(linked), bin_dir, UNTIL), file=out)
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
