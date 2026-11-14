# walled.sh: the API lane's wall test for sh (packet al2b-linux-wall), sourced by prefilter.sh
# when it is readable beside it. POSIX sh; the test never forks and never decides: Python's
# wall.backend() does, after a trial namespace, so where the file is there and the trial fails
# the lane says its own platform line.

# The paths are set here, at the source, so the environment never aims them; a test may reset
# them after sourcing.
apilane_sandbox_exec=/usr/bin/sandbox-exec
apilane_bwrap=/usr/bin/bwrap

# A wall may be proved on this platform: sandbox-exec (macOS) or bwrap (Linux) is an executable
# file at its fixed path.
apilane_walled() {
	{ [ -f "$apilane_sandbox_exec" ] && [ -x "$apilane_sandbox_exec" ]; } ||
		{ [ -f "$apilane_bwrap" ] && [ -x "$apilane_bwrap" ]; }
}
