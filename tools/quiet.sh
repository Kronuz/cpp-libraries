#!/usr/bin/env bash
# Coordinates heavy work on this host between agents. A measurement (benchmark, profile,
# timed merge) holds a quiet file in ~/.scratch/quiet/; while any live hold exists, nobody
# compiles, runs test suites, or starts another measurement. A hold is live while its
# process runs and before its deadline; dead or expired holds are removed on sight.
#   quiet.sh run NAME MINUTES WHAT -- CMD...  hold while CMD runs (released on any exit)
#   quiet.sh hold NAME MINUTES WHAT [PID]     hold until release, the deadline, or PID's exit
#   quiet.sh release NAME
#   quiet.sh check                            exit 0 when free; else print holds, exit 1
#   quiet.sh wait                             block until free, then exit 0
set -uo pipefail
dir="${QUIET_DIR:-$HOME/.scratch/quiet}"
mkdir -p "$dir"

live() {  # file: true when its pid runs (0: no pid) and its deadline is ahead
	local pid until
	pid=$(sed -n 's/^pid=//p' "$1") until=$(sed -n 's/^until=//p' "$1")
	[ -n "$until" ] && [ "$(date +%s)" -lt "$until" ] || return 1
	[ "${pid:-0}" = 0 ] || kill -0 "$pid" 2>/dev/null
}
holds() {  # prints live holds, removes the rest; true when any is live
	local any=1 f
	for f in "$dir"/*; do
		[ -f "$f" ] || continue
		if live "$f"; then
			echo "$(basename "$f"): $(sed -n 's/^what=//p' "$f") (since $(sed -n 's/^since=//p' "$f"), until $(date -r "$(sed -n 's/^until=//p' "$f")" +%T 2>/dev/null || date -d @"$(sed -n 's/^until=//p' "$f")" +%T))"
			any=0
		else
			rm -f "$f"
		fi
	done
	return $any
}
write() {  # name, minutes, what, pid
	printf 'what=%s\nsince=%s\nuntil=%s\npid=%s\nhost=%s\n' "$3" "$(date +%T)" "$(($(date +%s) + 60 * $2))" "$4" "$(hostname -s)" > "$dir/$1.tmp" &&
		mv "$dir/$1.tmp" "$dir/$1"
}

case "${1:-}" in
run)
	name=$2 minutes=$3 what=$4; shift 4; [ "${1:-}" = -- ] && shift
	write "$name" "$minutes" "$what" $$
	trap 'rm -f "$dir/$name"' EXIT
	"$@"
	;;
hold) write "$2" "$3" "$4" "${5:-0}" ;;
release) rm -f "$dir/$2" ;;
check) ! holds ;;
wait)
	while holds > /dev/null; do sleep 30; done
	;;
*)
	sed -n '2,10p' "$0" >&2
	exit 2
	;;
esac
