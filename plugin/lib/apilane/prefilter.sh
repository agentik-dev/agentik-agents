# prefilter.sh: the API lane's cheap tests (design/21 item 16), POSIX sh, sourced by the hook
# and by the dispatcher, which set apilane_dir to this file's folder before sourcing it.
#
# The test never decides: it only spares a Python start. So it is true wherever the one reader
# (config.py) would say on or refused, and wherever the report would print a line. Neither test
# forks: no command substitution, no external tool, only the shell's own words and globs.

# The user file under $HOME is a regular, readable file that holds the word "api".
apilane_wants_start() {
	case ${HOME:-} in /*) ;; *) return 1 ;; esac
	apilane_f=$HOME/.config/agentik/agents/config.yaml
	[ -f "$apilane_f" ] && [ -r "$apilane_f" ] || return 1
	while IFS= read -r apilane_l || [ -n "$apilane_l" ]; do
		case $apilane_l in *api*) return 0 ;; esac
	done <"$apilane_f"
	return 1
}

# The event's text: true when this session's live folder holds a .json record; when no session
# id of at most 128 letters, digits and dashes can be cut from the event, when any session's does.
apilane_wants_prompt() {
	case ${HOME:-} in /*) ;; *) return 1 ;; esac
	apilane_live=$HOME/.local/state/agentik-agents/api/live
	apilane_s=
	apilane_r=${1-}
	case $apilane_r in
	*'"session_id":'*)
		apilane_r=${apilane_r#*\"session_id\":}
		while :; do
			case $apilane_r in ' '*) apilane_r=${apilane_r# } ;; *) break ;; esac
		done
		case $apilane_r in
		'"'*)
			apilane_r=${apilane_r#\"}
			case $apilane_r in *'"'*) apilane_s=${apilane_r%%\"*} ;; esac
			;;
		esac
		;;
	esac
	case $apilane_s in
	'' | *[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-]*) apilane_s= ;;
	esac
	[ "${#apilane_s}" -le 128 ] || apilane_s=
	if [ -n "$apilane_s" ]; then
		for apilane_f in "$apilane_live/$apilane_s"/*.json; do
			[ -e "$apilane_f" ] && return 0
		done
		return 1
	fi
	for apilane_f in "$apilane_live"/*/*.json; do
		[ -e "$apilane_f" ] && return 0
	done
	return 1
}

# A wall is proved on this platform: the first backend's, sandbox-exec. A later backend's row
# adds walled.sh beside this file to redefine it, so it edits no line here.
apilane_walled() {
	[ -f /usr/bin/sandbox-exec ] && [ -x /usr/bin/sandbox-exec ]
}

if [ -n "${apilane_dir:-}" ] && [ -r "$apilane_dir/walled.sh" ]; then
	. "$apilane_dir/walled.sh"
fi
