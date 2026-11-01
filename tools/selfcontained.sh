#!/usr/bin/env bash
# Checks that every public header of a repository compiles alone: one translation unit per
# header, holding nothing but `#include "header"` twice (the second include checks the guard),
# compiled with -fsyntax-only at the standard the repository requests.
#
#   tools/selfcontained.sh [-s STD]... [-I DIR]... [-b BUILD [-C ARGS]] [-x GLOB]... [-f FLAG]...
#                          [-c CXX] [-j N] [-q] [REPO_DIR]
#
#   -s STD    C++ standard to check (17, 20, 23); repeat to check several. Default: the lowest
#             cxx_std_NN or CXX_STANDARD NN in CMakeLists.txt, else 20.
#   -I DIR    extra include directory (a dependency's headers).
#   -b BUILD  a CMake build tree whose FetchContent sources (BUILD/_deps/*-src) are put on the
#             include path; configured first when it holds no CMakeCache.txt.
#   -C ARGS   arguments for that configure (space separated), such as -DNAME=ON.
#   -x GLOB   skip headers whose path from REPO_DIR, or whose spelling, matches GLOB
#             (repeatable): a header that needs a platform or a macro its includer sets.
#             `.selfcontained-skip` in REPO_DIR lists more, one GLOB per line.
#   -f FLAG   extra compiler flag, such as -DNAME=1.
#   -c CXX    compiler (default $CXX, else c++).
#   -j N      jobs (default: the CPU count).
#   -q        print the failures only.
#
# Public headers are the tracked and untracked *.h, *.hh, *.hpp and *.hxx files, outside test,
# tests, bench, benchmark(s), fuzz, example(s), doc(s), tools, third_party, vendor, ext,
# prototype and build directories. A header under include/ is spelled without that prefix.
# Exit status: 0 every header compiles, 1 one does not, 2 bad usage or a failed configure.
set -uo pipefail

# One check, run by xargs: self --one STD HEADER, with the settings in the environment.
if [ "${1:-}" = --one ]; then
	std=$2 header=$3
	id="${std}_${header//\//__}"
	inc=() flags=()
	IFS=$'\n' read -r -d '' -a inc <<<"$SC_INC" || true
	IFS=$'\n' read -r -d '' -a flags <<<"$SC_FLAGS" || true
	if printf '#include "%s"\n#include "%s"\n' "$header" "$header" |
		"$SC_CXX" -x c++ -std="c++$std" -fsyntax-only ${inc[@]+"${inc[@]}"} ${flags[@]+"${flags[@]}"} - \
			>"$SC_OUT/$id.log" 2>&1; then
		echo ok >"$SC_OUT/$id"
	else
		{
			echo FAIL
			grep -E -m 6 'error|Error' "$SC_OUT/$id.log" || head -n 6 "$SC_OUT/$id.log"
		} >"$SC_OUT/$id"
	fi
	exit 0
fi

usage() { sed -n '2,/^set -u/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//' >&2; exit 2; }

self="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
stds=() incs=() flags=() skips=() build="" cmake_args="" quiet=0
cxx="${CXX:-c++}"
jobs="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
while getopts "s:I:b:C:x:f:c:j:qh" opt; do
	case $opt in
	s) stds+=("$OPTARG") ;;
	I) incs+=("-I$(cd "$OPTARG" && pwd)") ;;
	b) build=$OPTARG ;;
	C) cmake_args=$OPTARG ;;
	x) skips+=("$OPTARG") ;;
	f) flags+=("$OPTARG") ;;
	c) cxx=$OPTARG ;;
	j) jobs=$OPTARG ;;
	q) quiet=1 ;;
	*) usage ;;
	esac
done
shift $((OPTIND - 1))
repo="$(cd "${1:-.}" && pwd)" || usage

if [ ${#stds[@]} -eq 0 ]; then
	std=$(grep -h -o -E '(cxx_std_|CXX_STANDARD[ ]+)[0-9]+' "$repo/CMakeLists.txt" 2>/dev/null |
		grep -o '[0-9]*$' | sort -n | head -n 1)
	stds=("${std:-20}")
fi

if [ -n "$build" ]; then
	mkdir -p "$build"
	if [ ! -f "$build/CMakeCache.txt" ]; then
		# shellcheck disable=SC2086
		if ! cmake -S "$repo" -B "$build" $cmake_args >"$build/configure.log" 2>&1; then
			tail -n 20 "$build/configure.log" >&2
			echo "selfcontained: configure failed (see $build/configure.log)" >&2
			exit 2
		fi
	fi
	for dep in "$build"/_deps/*-src; do
		[ -d "$dep" ] || continue
		incs+=("-I$dep")
		[ -d "$dep/include" ] && incs+=("-I$dep/include")
	done
fi

incs=("-I$repo" ${incs[@]+"${incs[@]}"})
[ -d "$repo/include" ] && incs=("-I$repo/include" "${incs[@]}")

if [ -f "$repo/.selfcontained-skip" ]; then
	while IFS= read -r line; do
		case $line in '' | '#'*) ;; *) skips+=("$line") ;; esac
	done <"$repo/.selfcontained-skip"
fi

wanted() {
	case "/$1" in
	*/test/* | */tests/* | */bench/* | */benchmark/* | */benchmarks/* | */fuzz/* | */example/* | \
		*/examples/* | */doc/* | */docs/* | */tools/* | */third_party/* | */vendor/* | */ext/* | \
		*/prototype/* | */_deps/* | */build/* | */build-*/*) return 1 ;;
	esac
	local glob
	for glob in ${skips[@]+"${skips[@]}"}; do
		# shellcheck disable=SC2254
		case $1 in $glob) return 1 ;; esac
		# shellcheck disable=SC2254
		case ${1#include/} in $glob) return 1 ;; esac
	done
	return 0
}

if git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	listing="$(git -C "$repo" ls-files -co --exclude-standard -- '*.h' '*.hh' '*.hpp' '*.hxx')"
else
	listing="$(cd "$repo" && find . -type f \( -name '*.h' -o -name '*.hh' -o -name '*.hpp' \
		-o -name '*.hxx' \) | sed 's|^\./||')"
fi
headers=()
while IFS= read -r path; do
	[ -n "$path" ] && [ -f "$repo/$path" ] && wanted "$path" && headers+=("${path#include/}")
done <<<"$listing"
if [ ${#headers[@]} -eq 0 ]; then
	echo "selfcontained: no public headers in $repo"
	exit 0
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
SC_CXX=$cxx SC_OUT=$tmp
SC_INC="$(printf '%s\n' "${incs[@]}")"
SC_FLAGS="$(printf '%s\n' ${flags[@]+"${flags[@]}"})"
export SC_CXX SC_OUT SC_INC SC_FLAGS

for std in "${stds[@]}"; do
	for header in "${headers[@]}"; do printf '%s\0%s\0' "$std" "$header"; done
done | xargs -0 -n 2 -P "$jobs" "$self" --one

ok=0 failed=0
for std in "${stds[@]}"; do
	for header in "${headers[@]}"; do
		result="$tmp/${std}_${header//\//__}"
		if [ "$(head -n 1 "$result" 2>/dev/null)" = ok ]; then
			ok=$((ok + 1))
			[ $quiet -eq 1 ] || echo "ok    c++$std $header"
		else
			failed=$((failed + 1))
			echo "FAIL  c++$std $header"
			sed 1d "$result" 2>/dev/null | sed 's/^/      /'
		fi
	done
done
echo "selfcontained: $ok ok, $failed failed (${#headers[@]} headers, standards ${stds[*]}, compiler $cxx)"
[ $failed -eq 0 ]
