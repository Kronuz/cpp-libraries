#!/usr/bin/env bash
# Coordinates heavy work on this host between agents. A measurement (benchmark, profile,
# timed merge) holds a quiet file in ~/.scratch/quiet/. A strict hold (A/Bs, gate runs, where
# a few percent matters) means nobody compiles, runs test suites, or starts another
# measurement. A light hold (single-threaded or informational runs) allows compiles and
# tests at `nice -n 19` with at most 4 parallel jobs. A hold is live while its process runs
# and before its deadline; dead or expired holds are removed on sight.
#   quiet.sh run NAME MINUTES WHAT -- CMD...  hold while CMD runs (released on any exit)
#   quiet.sh hold NAME MINUTES WHAT [PID]     hold until release, the deadline, or PID's exit
#   quiet.sh release NAME
#   quiet.sh check                            exit 0 when free, 2 when only light holds
#                                             live, 1 for a strict hold; prints the holds
#   quiet.sh wait [--light]                   block until free (or only light holds)
# QUIET_LEVEL=light makes run and hold light; strict is the default.
set -uo pipefail
dir="${QUIET_DIR:-$HOME/.scratch/quiet}"
mkdir -p "$dir"

live() {  # file: true when its pid runs (0: no pid) and its deadline is ahead
	local pid until
	pid=$(sed -n 's/^pid=//p' "$1") until=$(sed -n 's/^until=//p' "$1")
	[ -n "$until" ] && [ "$(date +%s)" -lt "$until" ] || return 1
	[ "${pid:-0}" = 0 ] || kill -0 "$pid" 2>/dev/null
}
holds() {  # prints live holds, removes the rest; returns 1 for none, 2 for light only, 0 for strict
	local any=1 f level
	for f in "$dir"/*; do
		[ -f "$f" ] || continue
		if live "$f"; then
			level=$(sed -n 's/^level=//p' "$f")
			level=${level:-strict}
			echo "$(basename "$f") [$level]: $(sed -n 's/^what=//p' "$f") (since $(sed -n 's/^since=//p' "$f"), until $(date -r "$(sed -n 's/^until=//p' "$f")" +%T 2>/dev/null || date -d @"$(sed -n 's/^until=//p' "$f")" +%T))"
			if [ "$level" = light ]; then [ $any = 1 ] && any=2; else any=0; fi
		else
			rm -f "$f"
		fi
	done
	return $any
}
write() {  # name, minutes, what, pid
	printf 'what=%s\nsince=%s\nuntil=%s\npid=%s\nhost=%s\nlevel=%s\n' "$3" "$(date +%T)" "$(($(date +%s) + 60 * $2))" "$4" "$(hostname -s)" "${QUIET_LEVEL:-strict}" > "$dir/$1.tmp" &&
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
check)
	holds
	case $? in 1) exit 0 ;; 2) exit 2 ;; *) exit 1 ;; esac
	;;
wait)
	while true; do
		holds > /dev/null
		r=$?
		[ $r = 1 ] && break
		[ $r = 2 ] && [ "${2:-}" = --light ] && break
		sleep 30
	done
	;;
*)
	sed -n '2,10p' "$0" >&2
	exit 2
	;;
esac
