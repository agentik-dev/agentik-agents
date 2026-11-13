"""The API lane's four places, found from the account's home (design/21 item 14).

The home is the account's in the password database, never `HOME`, and no `XDG_*` variable moves
any of the four: one day's log serves the account whatever a harness exported, and a file planted
under another root turns nothing on. This is the only code in the package that reads the password
database or the environment for a place. No variable is a test seam: a test hands `roots` in.
"""
import collections
import os
import pwd

Roots = collections.namedtuple("Roots", "home config state store")


class HomeError(Exception):
    """`home.none` () or `home.differs` (home, account)."""

    def __init__(self, code, **fields):
        Exception.__init__(self, code)
        self.code, self.fields = code, fields


def account(env=None):
    """Roots(home, config, state, store) under the account's home.

    Raises `home.none` when the database gives no absolute home, and `home.differs` when
    `env["HOME"]` is set and its real path is not the account's."""
    env = os.environ if env is None else env
    try:
        home = pwd.getpwuid(os.getuid()).pw_dir
    except (KeyError, OSError):
        home = ""
    if not home or not os.path.isabs(home):
        raise HomeError("home.none")
    given = env.get("HOME")
    if given and os.path.realpath(given) != os.path.realpath(home):
        raise HomeError("home.differs", home=given, account=home)
    config = os.path.join(home, ".config", "agentik", "agents")
    return Roots(home, os.path.join(config, "config.yaml"),
                 os.path.join(home, ".local", "state", "agentik-agents", "api"),
                 os.path.join(config, "secrets", "anthropic-api-key.sops.yaml"))


def tilde(path, home):
    """The path with the home shown as `~`, for a sentence."""
    if home and (path == home or path.startswith(home.rstrip("/") + "/")):
        return "~" + path[len(home.rstrip("/")):]
    return path
