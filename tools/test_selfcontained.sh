#!/usr/bin/env bash
# Tests for selfcontained.sh against tools/testdata/selfcontained. Run: bash tools/test_selfcontained.sh
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
tool="$here/selfcontained.sh"
fixture="$here/testdata/selfcontained"
failures=0

check() {  # description, condition status
	if [ "$2" -eq 0 ]; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}
has() { grep -q -E -- "$1" <<<"$out"; }
hasf() { grep -q -F -- "$1" <<<"$out"; }
lacks() { ! grep -q -E -- "$1" <<<"$out"; }

out="$("$tool" -s 20 "$fixture" 2>&1)"; status=$?
check "c++20: exit status 1 with failing headers" $((status == 1 ? 0 : 1))
hasf "ok    c++20 good.hh"; check "good header passes" $?
hasf "ok    c++20 sub/nested.hh"; check "a nested header resolves its sibling" $?
hasf "ok    c++20 cxx20.hh"; check "a C++20 header passes at C++20" $?
hasf "FAIL  c++20 needs_vector.hh"; check "a missing include fails" $?
has "error"; check "the compiler's message is shown" $?
hasf "FAIL  c++20 no_guard.hh"; check "a header without a guard fails the second include" $?
lacks "broken_but_not_public|other_os"; check "test/ and .selfcontained-skip are not checked" $?
has ", 2 failed \(5 headers"; check "two failures among five headers" $?

out="$("$tool" -s 17 -x 'no_guard*' "$fixture" 2>&1)"; status=$?
hasf "FAIL  c++17 cxx20.hh"; check "a C++20 header fails at C++17" $?
lacks "no_guard"; check "-x skips a header" $?

out="$("$tool" -q -s 17 -s 20 -x 'no_guard*' -x 'needs_*' -x 'cxx20*' "$fixture" 2>&1)"; status=$?
check "only passing headers: exit status 0" $status
lacks "^ok "; check "-q hides passes" $?
hasf "selfcontained: 4 ok, 0 failed (2 headers, standards 17 20"; check "two standards over two headers" $?

printf 'cmake_minimum_required(VERSION 3.20)\nproject(t CXX)\nadd_library(t INTERFACE)\ntarget_compile_features(t INTERFACE cxx_std_17)\n' >"$here/testdata/selfcontained/CMakeLists.txt"
out="$("$tool" -x 'no_guard*' "$fixture" 2>&1)"
rm -f "$here/testdata/selfcontained/CMakeLists.txt"
hasf "FAIL  c++17 cxx20.hh"; check "the standard comes from CMakeLists.txt" $?

empty="$(mktemp -d)"
out="$("$tool" "$empty" 2>&1)"; status=$?
rmdir "$empty"
has "no public headers"; check "a tree with no headers is not an error" $((status))

out="$(CXX=no-such-compiler "$tool" -s 20 "$fixture" 2>&1)"; status=$?
check "an unusable compiler fails" $((status == 1 ? 0 : 1))

# CI downloads the script without the executable bit and runs it with bash.
copy="$(mktemp -d)"
cp "$tool" "$copy/selfcontained.sh"
chmod -x "$copy/selfcontained.sh"
out="$(bash "$copy/selfcontained.sh" -q -s 20 -x 'no_guard*' -x 'needs_*' "$fixture" 2>&1)"; status=$?
rm -rf "$copy"
check "a copy without the executable bit runs" $status
hasf "selfcontained: 3 ok, 0 failed"; check "... and checks the headers" $?

echo "$failures failed"
[ $failures -eq 0 ]
