"""install-cli for agentik-agents (hq design/04 section 3, packet a-s18), run by the dispatcher's
`install-cli` verb under Python.

The canonical install (agentik_install, beside this file) freezes this lib/, writes the launcher
and the `agentik` door. Then each old name, agentroute, claude-agents, claude-local and localrig,
is refreshed to its file in the frozen tree, by a temp link and a rename, only where a link of that
name already stands in the bin dir, as agentik_install._old_link rules it: a new machine gets none
(packet ia1-new-machine). They stay until 2026-12-31. A person's own file under one of the names
is left byte for byte and named in one stderr line, exit 0. While the API lane is on, a fifth,
claude-fanout, links to the lane's forward on any machine (packet al6, design/21 item 12), and a
path of that name that is not a link is left and named, exit 1; while the lane is off, a path of
that name is not touched.
Exit 0 done; 1 it could not, the reason on stderr (GUIDE section 10). Stdlib, 3.9.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import agentik_install  # noqa: E402

OLD = ("agentroute", "claude-agents", "claude-local", "localrig")
UNTIL = "2026-12-31"


FORWARD = "claude-fanout"


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


def link_old(bin_dir, tree, err, names=OLD):
    """Each name in bin_dir to its file in tree: an old name only where its link stands already,
    claude-fanout wherever no file holds it. (linked, left, passed): the names linked, those it
    could not link, and the old names a person's own file holds, left as they are."""
    linked, left, passed = [], [], []
    # The freeze writes 0644 but for the runner and the door, and the dispatcher runs each tool
    # from the tree whether its old name links or not (a1 F1): every chmod before any link.
    for name in names:
        try:
            os.chmod(os.path.join(tree, name), 0o755)
        except OSError as e:
            print("install-cli: %s: %s" % (os.path.join(tree, name), e), file=err)
            left.append(name)
    for name in names:
        path = os.path.join(bin_dir, name)
        target = os.path.join(tree, name)
        if name in left:
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
    args = parser.parse_args(argv)
    try:
        done = agentik_install.install(args.prefix)
    except (OSError, KeyError, ValueError) as e:
        print("install-cli: %s" % e, file=err)
        return 1
    print("installed %s -> %s (%s); %s" % (done["launcher"], done["tree"], done["version"],
                                          done["door"]), file=out)
    for line in done["pruned"]:
        print(line, file=out)
    bin_dir = os.path.dirname(done["launcher"])
    names = OLD + (FORWARD,) if (lane_on(err) if lane is None else lane) else OLD
    linked, left, passed = link_old(bin_dir, done["tree"], err, names)
    if passed:
        print("install-cli: left %s in %s as it is: not a link, so no old name's to refresh"
              % (", ".join(passed), agentik_install.shown(bin_dir)), file=err)
    if linked:
        print("linked %s in %s -> the tree (the old names, until %s)"
              % (", ".join(linked), bin_dir, UNTIL), file=out)
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
