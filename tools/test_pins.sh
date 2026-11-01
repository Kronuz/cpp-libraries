#!/usr/bin/env bash
# Tests for pins.sh without the network: the CMake reader, and local-clone mode over repositories
# built here. Run: bash tools/test_pins.sh
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
tool="$here/pins.sh"
failures=0
tab=$'\t'

check() {  # description, status
	if [ "$2" -eq 0 ]; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}
has() { grep -q -F -- "$1" <<<"$out"; }
lacks() { ! grep -q -F -- "$1" <<<"$out"; }

# -- the reader --------------------------------------------------------------------------------
# shellcheck disable=SC2016
cmake='
cmake_minimum_required(VERSION 3.20)
set(HASHES_TAG 0123456789abcdef0123456789abcdef01234567)
include(FetchContent)
FetchContent_Declare(
  strict_stox
  GIT_REPOSITORY https://github.com/Kronuz/strict-stox.git
  GIT_TAG        21b7941c71064b5a4e52ffb50a2701ee4aae4c6c)  # a comment (with parens)
FetchContent_Declare(hashes GIT_REPOSITORY "https://github.com/kronuz/hashes" GIT_TAG ${HASHES_TAG})
fetchcontent_declare(tip
  GIT_REPOSITORY git@github.com:Kronuz/char-classify.git
  GIT_TAG main
)
FetchContent_Declare(floating GIT_REPOSITORY https://github.com/Kronuz/endian.git)
FetchContent_Declare(unset GIT_REPOSITORY https://github.com/Kronuz/math.git GIT_TAG ${NOT_SET})
FetchContent_Declare(fmt GIT_REPOSITORY https://github.com/fmtlib/fmt.git GIT_TAG 11.0.2)
FetchContent_Declare(other GIT_REPOSITORY https://github.com/someone/Kronuz-lookalike.git GIT_TAG v1)
# FetchContent_Declare(commented GIT_REPOSITORY https://github.com/Kronuz/commented.git GIT_TAG v1)
'
out="$(OWNER=Kronuz "$tool" --parse CMakeLists.txt <<<"$cmake")"
expected="CMakeLists.txt${tab}strict_stox${tab}strict-stox${tab}21b7941c71064b5a4e52ffb50a2701ee4aae4c6c
CMakeLists.txt${tab}hashes${tab}hashes${tab}0123456789abcdef0123456789abcdef01234567
CMakeLists.txt${tab}tip${tab}char-classify${tab}main
CMakeLists.txt${tab}floating${tab}endian${tab}
CMakeLists.txt${tab}unset${tab}math${tab}\${NOT_SET}"
same=0
[ "$out" = "$expected" ] || same=1
check "parse: first-party declares, with variables, comments and ssh URLs" $same
if [ $same -ne 0 ]; then diff <(echo "$out") <(echo "$expected"); fi

# -- local clones ------------------------------------------------------------------------------
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git_() { git -C "$1" -c user.name=t -c user.email=t@example.com "${@:2}"; }
commit() { echo "$2" >"$1/f"; git_ "$1" add f; git_ "$1" commit -q -m "$2"; git_ "$1" rev-parse HEAD; }
mkrepo() { mkdir -p "$work/$1"; git_ "$work/$1" init -q -b main; }

mkrepo dep
c1="$(commit "$work/dep" one)"
commit "$work/dep" two >/dev/null
c3="$(commit "$work/dep" three)"
git_ "$work/dep" checkout -q -b side "$c1"
side="$(commit "$work/dep" side)"
git_ "$work/dep" checkout -q main
git_ "$work/dep" branch -q feature "$c3"

consumer() {  # name, GIT_TAG
	mkrepo "$1"
	cat >"$work/$1/CMakeLists.txt" <<EOF
include(FetchContent)
FetchContent_Declare(dep GIT_REPOSITORY https://github.com/Kronuz/dep.git GIT_TAG $2)
EOF
	git_ "$work/$1" add CMakeLists.txt
	git_ "$work/$1" commit -q -m cmake
}
consumer cur "$c3"
consumer old "$c1"
consumer tip main
consumer split "$side"
consumer lost 0123456789abcdef0123456789abcdef01234567
consumer nodep "$c3"
sed -i.bak 's/dep.git/missing.git/' "$work/nodep/CMakeLists.txt"; rm "$work/nodep/CMakeLists.txt.bak"
git_ "$work/nodep" commit -q -a -m missing

out="$("$tool" -r "$work" 2>&1)"
row() { grep -E "^$1 +CMakeLists.txt +" <<<"$out"; }
row cur | grep -q "dep  *${c3:0:10}  *main  *current$"; check "local: a pin at the head is current" $?
row old | grep -q "dep  *${c1:0:10}  *main  *behind 2$"; check "local: a pin two commits back is behind 2" $?
row tip | grep -q "dep  *main  *main  *tracks main$"; check "local: GIT_TAG main tracks the branch" $?
row split | grep -q "diverged (+2 on main, +1 on the pin)$"; check "local: a pin on a side branch is diverged" $?
row lost | grep -q "pin not found$"; check "local: an unknown pin is not found" $?
row nodep | grep -q "dependency not found$"; check "local: a missing dependency is reported" $?
has "pins: 6 first-party pins in 7 repositories"; check "local: the summary counts pins and repositories" $?

out="$("$tool" -r "$work" -b 2>&1)"
lacks "current"; check "-b hides current pins" $?
lacks "tracks"; check "-b hides tracking pins" $?
has "behind 2"; check "-b keeps the behind pins" $?

out="$("$tool" -r "$work" cur tip 2>&1)"; status=$?
check "-c is off by default: exit status 0" $status
has "pins: 2 first-party pins in 2 repositories, 0 need attention"; check "REPO arguments limit the consumers" $?
"$tool" -r "$work" -c cur tip >/dev/null 2>&1; check "-c passes when nothing needs attention" $?
"$tool" -r "$work" -c old >/dev/null 2>&1; status=$?
check "-c fails when a pin is behind" $((status == 1 ? 0 : 1))
"$tool" -r "$work" nonexistent >/dev/null 2>&1; status=$?
check "an unknown consumer is a usage error" $((status == 2 ? 0 : 1))

echo "$failures failed"
[ $failures -eq 0 ]
