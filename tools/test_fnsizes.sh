#!/usr/bin/env bash
# Tests for fnsizes.sh over a small binary built here. Run: bash tools/test_fnsizes.sh
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
tool="$here/fnsizes.sh"
cxx="${CXX:-c++}"
work="$(mktemp -d "${TMPDIR:-/tmp}/fnsizes.XXXXXX")"
trap 'rm -rf "$work"' EXIT
failures=0

check() {  # description, condition status
	if [ "$2" -eq 0 ]; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi
}

cat >"$work/t.cc" <<'SRC'
#include <cstdio>
__attribute__((noinline)) int small_fn(int x) { return x * 3; }
__attribute__((noinline)) int big_fn(int x) {
	int s = 0;
	for (int i = 0; i < x; ++i) s += small_fn(i) ^ (i << 3);
	std::printf("%d\n", s);
	return s;
}
int main(int argc, char**) { return big_fn(argc) + small_fn(argc); }
SRC
"$cxx" -O1 -o "$work/t" "$work/t.cc" && "$cxx" -O1 -c -o "$work/t.o" "$work/t.cc"
check "the fixture builds" $?

for f in t t.o; do
	"$tool" "$work/$f" >"$work/$f.1"; s1=$?
	"$tool" "$work/$f" >"$work/$f.2"
	check "$f: exit status 0" $s1
	grep -q -E '^[1-9][0-9]*	[^	]+	small_fn\(int\)$' "$work/$f.1"; check "$f: small_fn has a nonzero size" $?
	grep -q -E '^[1-9][0-9]*	[^	]+	big_fn\(int\)$' "$work/$f.1"; check "$f: big_fn has a nonzero size" $?
	! grep -q -E '^0	' "$work/$f.1"; check "$f: no function has size 0" $?
	cmp -s "$work/$f.1" "$work/$f.2"; check "$f: two runs print the same table" $?
	big=$(awk -F'\t' '$3 == "big_fn(int)" {print $1}' "$work/$f.1")
	small=$(awk -F'\t' '$3 == "small_fn(int)" {print $1}' "$work/$f.1")
	[ "${big:-0}" -gt "${small:-0}" ]; check "$f: big_fn is larger than small_fn" $?
done

"$tool" -m "$work/t" | head -n 1 | grep -q -E '^#total	[1-9][0-9]*	[1-9][0-9]*$'; check "-m prints a total line" $?
"$tool" "$work/missing" 2>/dev/null; check "a missing file exits 2" $(($? == 2 ? 0 : 1))

echo "$failures failed"
[ $failures -eq 0 ]
