#!/usr/bin/env bash
# CI's matrix before a push: build and test a repository's working tree with assert() live
# and the standard library's hardening on this Mac (plus ASan and UBSan with Homebrew LLVM),
# and on strata's Linux and FreeBSD gate VMs. Prints one line per platform.
#   tools/preflight.sh REPO_DIR [mac|linux|freebsd ...]
# The VMs come from strata's tools/vm scripts (STRATA, default ~/code/Kronuz/strata).
set -uo pipefail
repo="$(cd "${1:?usage: preflight.sh REPO_DIR [platforms]}" && pwd)"; shift
name="$(basename "$repo")"
platforms=("${@:-mac linux freebsd}"); platforms=(${platforms[*]})
strata="${STRATA:-$HOME/code/Kronuz/strata}"
scratch="$HOME/.scratch/preflight/$name"; mkdir -p "$scratch"
flags="-O2 -g"  # RelWithDebInfo without NDEBUG
status=0
# Another agent's measurement holds the host quiet (tools/quiet.sh): wait for it.
if ! "$(dirname "$0")/quiet.sh" check >&2; then echo "preflight: waiting for the host to be quiet" >&2; "$(dirname "$0")/quiet.sh" wait; fi

run_local() {  # label, build dir, compiler, extra flags
	local label=$1 dir=$2 cxx=$3 extra=$4
	if cmake -S "$repo" -B "$dir" -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_CXX_COMPILER="$cxx" \
		"-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=$flags $extra" >"$dir.log" 2>&1 &&
		cmake --build "$dir" --parallel 8 >>"$dir.log" 2>&1 &&
		ctest --test-dir "$dir" --output-on-failure --no-tests=ignore >>"$dir.log" 2>&1; then
		echo "$label: ok"
	else echo "$label: FAILED ($dir.log)"; status=1; fi
}
run_vm() {  # label, vm script, extra flags
	local label=$1 vm=$2 extra=$3
	# Tracked and untracked files that exist, minus ignored ones (scratch data, build trees).
	(cd "$repo" && git ls-files -co --exclude-standard -z | perl -0ne 'print if -e substr($_, 0, -1)' | xargs -0 tar -czf "$scratch/tree.tgz")
	if "$strata/tools/vm/$vm" ssh "rm -rf ~/preflight/$name && mkdir -p ~/preflight/$name && cd ~/preflight/$name && tar xzf - &&
		cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo '-DCMAKE_CXX_FLAGS_RELWITHDEBINFO=$flags $extra' >build.log 2>&1 &&
		cmake --build build --parallel 4 >>build.log 2>&1 && ctest --test-dir build --output-on-failure --no-tests=ignore >>build.log 2>&1 ||
		{ tail -40 build.log; exit 1; }" <"$scratch/tree.tgz" >"$scratch/$label.log" 2>&1; then
		echo "$label: ok"
	else echo "$label: FAILED ($scratch/$label.log)"; status=1; fi
}

for p in "${platforms[@]}"; do
	case $p in
	mac)
		run_local mac-hardened "$scratch/mac" c++ "-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE"
		llvm=/usr/local/opt/llvm/bin; [ -x "$llvm/clang++" ] || llvm=/opt/homebrew/opt/llvm/bin
		run_local mac-asan-ubsan "$scratch/mac-asan" "$llvm/clang++" "-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer"
		;;
	linux) run_vm linux linux.sh "-D_GLIBCXX_ASSERTIONS" ;;
	freebsd) run_vm freebsd freebsd.sh "" ;;
	*) echo "unknown platform $p"; status=2 ;;
	esac
done
exit $status
