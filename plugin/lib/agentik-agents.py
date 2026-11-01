"""agentik-agents' runner, the file both canonical launchers run under Python (GUIDE §10, packet
a-s18). The tools are sh, bash and Python scripts behind one sh dispatcher, so it restores the
parent's environment and execs /bin/sh on the dispatcher beside it, the args unchanged."""
import os
import sys

here = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, here)
import agentik_install  # noqa: E402  (-I leaves this folder off sys.path)

agentik_install.restore_parent_env()
os.execv("/bin/sh", ["/bin/sh", os.path.join(here, "agentik-agents")] + sys.argv[1:])
