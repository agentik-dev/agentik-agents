"""install-cli for agentik-agents (hq design/04 section 3, packet a-s18), run by the dispatcher's
`install-cli` verb under Python.

The canonical install (agentik_install, beside this file) freezes this lib/, writes the launcher
and the `agentik` door. Then each old name, agentroute, claude-agents, claude-local and localrig,
becomes a link from the bin dir into the frozen tree, by a temp link and a rename; they stay on
PATH until 2026-12-31. A path that is anything but a link or absent is left as it is and named.
Exit 0 done; 1 it could not, the reason on stderr (GUIDE section 10). Stdlib, 3.9.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import agentik_install  # noqa: E402

OLD = ("agentroute", "claude-agents", "claude-local", "localrig")
UNTIL = "2026-12-31"


def link_old(bin_dir, tree, err):
    """Each old name in bin_dir to its file in tree; the names left unlinked."""
    left = []
    for name in OLD:
        path = os.path.join(bin_dir, name)
        target = os.path.join(tree, name)
        if os.path.lexists(path) and not os.path.islink(path):
            print("install-cli: %s is not a link, left as it is; %s is not linked" % (path, name),
                  file=err)
            left.append(name)
            continue
        temp = os.path.join(bin_dir, ".%s.%d.tmp" % (name, os.getpid()))
        try:
            os.chmod(target, 0o755)      # the freeze writes 0644 but for the runner and the door
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
    return left


def main(argv=None, out=sys.stdout, err=sys.stderr):
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
    left = link_old(bin_dir, done["tree"], err)
    linked = [n for n in OLD if n not in left]
    if linked:
        print("linked %s in %s -> the tree (the old names, until %s)"
              % (", ".join(linked), bin_dir, UNTIL), file=out)
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
