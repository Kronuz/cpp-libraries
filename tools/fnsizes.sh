#!/usr/bin/env bash
# Prints the size of every function in an object file or binary, one row per symbol:
#
#   tools/fnsizes.sh [-m] FILE
#
# Row: SIZE TAB SECTION TAB DEMANGLED-NAME, sorted by section, then size (largest first), then
# name, so two runs over one build print the same table. Compare the tables of two builds with
# diff, or `sort -k3` them first when addresses moved.
#
#   ELF (Linux, FreeBSD): the sizes `nm -S` prints; the section is `text`.
#   Mach-O (macOS): `nm -S` prints 0, so a symbol's size is the distance to the next symbol in
#             its section, the last one ending at the section's end (from `size -m -l`).
#   -m        first line `#total` with the symbol count and the byte total.
#
# Exit status: 0 printed, 2 bad usage or unreadable file.
set -uo pipefail
total=0
while getopts "mh" opt; do
	case $opt in
	m) total=1 ;;
	*) sed -n '2,/^set -u/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
	esac
done
shift $((OPTIND - 1))
file="${1:-}"
[ -f "$file" ] || { echo "fnsizes: no such file: ${file:-<none>}" >&2; exit 2; }

if [ "$(uname -s)" = Darwin ]; then
	{ nm -n -m -U "$file"; echo "--"; size -m -l "$file"; } 2>/dev/null
else
	nm -S -C --defined-only "$file"
fi | FNSIZES_TOTAL=$total FNSIZES_MACHO=$([ "$(uname -s)" = Darwin ] && echo 1 || echo 0) python3 -I -c '
import os, re, subprocess, sys

macho = os.environ["FNSIZES_MACHO"] == "1"
rows = []  # (section, address, size or None, name)
if macho:
    text = sys.stdin.read()
    syms, _, sizes = text.partition("\n--\n")
    ends = {}  # section -> end address
    for m in re.finditer(r"Section (?:\((\w+), (\w+)\)|(\w+)): (\d+) \(addr 0x([0-9a-f]+)", sizes):
        seg = m.group(1)
        sect = m.group(2) or m.group(3)
        ends[sect] = int(m.group(5), 16) + int(m.group(4))
        ends.setdefault("segment " + sect, seg)
    for line in syms.splitlines():
        m = re.match(r"([0-9a-f]+) \((\w+),(\w+)\) (?:\[[^\]]*\] )*(?:non-external \(was a private external\) |non-external |external )(.*)", line)
        if not m or m.group(2) != "__TEXT" or m.group(4).startswith("__mh_"):
            continue
        rows.append((m.group(3), int(m.group(1), 16), None, m.group(4)))
    bysect = {}
    for r in rows:
        bysect.setdefault(r[0], []).append(r)
    rows = []
    for sect, items in bysect.items():
        items.sort(key=lambda r: (r[1], r[3]))
        for i, (s, a, _, n) in enumerate(items):
            nxt = next((b[1] for b in items[i + 1:] if b[1] > a), ends.get(sect, a))
            rows.append((s, a, nxt - a, n))
else:
    for line in sys.stdin:
        p = line.rstrip("\n").split(" ", 3)
        if len(p) == 4 and p[2] in ("T", "t", "W", "w", "i"):
            rows.append(("text", int(p[0], 16), int(p[1], 16), p[3]))

names = [r[3] for r in rows]
if macho and names:
    out = subprocess.run(["c++filt"], input="\n".join(names) + "\n", capture_output=True, text=True).stdout.split("\n")
    names = [o[1:] if o == n and o.startswith("_") and not o.startswith("__Z") else o for n, o in zip(names, out)]
rows = [(r[0], r[2], n) for r, n in zip(rows, names)]
rows.sort(key=lambda r: (r[0], -r[1], r[2]))
if os.environ["FNSIZES_TOTAL"] == "1":
    print("#total\t%d\t%d" % (len(rows), sum(r[1] for r in rows)))
for sect, size, name in rows:
    print("%d\t%s\t%s" % (size, sect, name))
'
