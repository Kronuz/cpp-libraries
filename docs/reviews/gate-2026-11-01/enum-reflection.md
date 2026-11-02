# enum-reflection: START 79fe3fa to HEAD ac5352d

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/enum-reflection#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`); HEAD is `origin/main` when this run started.

**Status: complete** (m4 3 of 3 rounds, i9 3 of 3 rounds). 

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64), macOS 26 (Darwin 25.6.0), Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja |
| i9 | Intel i9-9980HK (8C/16T, x86-64), macOS 15 (Darwin 24.6.0), Apple clang 17.0.0 (clang-1700.6.4.2), CMake, Ninja |

- Bench: HEAD's `bench/bench.cc` + `bench/enums.h`, built with Abseil disabled (`-DCMAKE_DISABLE_FIND_PACKAGE_absl=TRUE`: its headers must come before `enum.h`, and it is only a comparator) and with the timed `enum_try_type` miss rows deleted from the bench source on both sides (`rig/patch/enum-reflection.sh`).
- START `79fe3fa` has no `enum_try_type` (added 2026-10-30): the START binary is compiled with a shim (`rig/shim/enum_try_type_shim.h`, `-include`) that answers `enum_try_type` through `enum_type` and a catch. Rows that go through the shim are not START measurements and are listed apart; the comparison uses `enum_name` and `enum_type` rows only.
- Builds: Release (`-O3 -DNDEBUG`), same compiler and flags for both sides, library sources only differ (see Commands).
- Every round runs START, HEAD, then START again (the A/A control, a second copy of the START binary), interleaved in one hold; ratios are the median of the paired rounds, START time / HEAD time (above 1 is faster now). `A/A dev` is the largest |A/A - 1| over the rounds.

## Commands

```sh
git clone https://github.com/Kronuz/enum-reflection && cd enum-reflection
# START 79fe3fa66df510d1417ebf00b250adee70d926da   HEAD ac5352dd007b9dc02714ebe6dc5e65dcdf8f2b78
git worktree add --detach trees/enum-reflection-head ac5352dd007b9dc02714ebe6dc5e65dcdf8f2b78
git worktree add --detach trees/enum-reflection-start ac5352dd007b9dc02714ebe6dc5e65dcdf8f2b78
(cd trees/enum-reflection-start && git rm -rq -- enum.h && git checkout 79fe3fa66df510d1417ebf00b250adee70d926da -- enum.h)   # HEAD's tree and bench, START's library files
cmake -S trees/enum-reflection-{head,start} -B trees/enum-reflection-{head,start}/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DENUM_REFLECTION_BUILD_BENCH=ON -DCMAKE_DISABLE_FIND_PACKAGE_absl=TRUE
cmake --build trees/enum-reflection-{head,start}/build --target enum_reflection_bench    # bench: bench/bench.cc (HEAD's, minus the timed enum_try_type miss rows)
# each round, in one quiet strict hold (<= 10 min): START, HEAD, START again (copy of the START binary)
for side in start head startcopy; do bin/enum-reflection.enum_reflection_bench.$side > out/enum-reflection/<a|b|aa>-N.txt; done
python3 rig/gate.py REPO m4|i9      # paired ratios via cpp-libraries/tools/ab_compare.py (read_runs, compare)
```

## Summary

| machine | set | rounds | rows | geomean START/HEAD | A/A geomean | rows <0.97 outside A/A | worst | rows <0.97 inside A/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| m4 | all | 3 | 16 | 0.864 | 0.995 | 6 | 0.483 | 0 |
| i9 | all | 3 | 16 | 0.838 | 1.004 | 7 | 0.422 | 0 |

## Rows below 0.97 outside the A/A spread

**m4**

| row | START | HEAD | START/HEAD | A/A dev | cause |
|---|---:|---:|---:|---:|---|
| 128 dense value(name) hit enum_type | 3.87 ns | 8.02 ns | 0.483 | 1.8% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| Status hit enum_type (exact case) | 2.78 ns | 4.28 ns | 0.650 | 0.4% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| Method hit enum_type (exact case) | 2.82 ns | 4.24 ns | 0.677 | 2.1% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| 32 dense value(name) hit enum_type | 3.49 ns | 4.72 ns | 0.733 | 4.2% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| 8 dense value(name) hit enum_type | 3.15 ns | 4.26 ns | 0.739 | 1.2% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| 32 sparse value(name) hit enum_type | 3.53 ns | 4.63 ns | 0.759 | 3.8% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |

**i9**

| row | START | HEAD | START/HEAD | A/A dev | cause |
|---|---:|---:|---:|---:|---|
| 128 dense value(name) hit enum_type | 8.90 ns | 21.1 ns | 0.422 | 3.1% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| Method hit enum_type (exact case) | 5.86 ns | 10.8 ns | 0.545 | 1.2% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| Status hit enum_type (exact case) | 6.80 ns | 11.2 ns | 0.593 | 3.2% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| 32 dense value(name) hit enum_type | 7.56 ns | 11.3 ns | 0.671 | 6.7% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| 32 sparse value(name) hit enum_type | 8.15 ns | 10.9 ns | 0.742 | 12.4% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| 8 dense value(name) hit enum_type | 8.03 ns | 10.7 ns | 0.755 | 4.4% | CHANGELOG 2026-10-31 Fixed: `enum_type` and `enum_try_type` now compare the input with the member's name when the hash hits (a 15-byte string forged to share a member's hash was accepted at START); the CHANGELOG's own before/after is about +50% on a hit (M4 2.5-2.6 -> 3.9-4.0 ns). Accepted correctness cost. |
| 128 dense name(value) enum_name | 3.40 ns | 3.87 ns | 0.879 | 2.6% | unexplained |

## Correctness changes that affect comparability

- HEAD verifies the name after the hash (security fix: forged hash collisions were accepted by START), so a hit does more work by design: the rows below are the accepted cost of that fix.

## Rows dropped or not compared

- `enum_try_type` rows (hit, lower-case hit; START has no such function, the START binary reaches it through the shim) and the near-miss line are listed apart as not comparable; the timed `enum_try_type` miss rows are deleted from the bench source on both sides.
- The bench's alternatives (array by value, binary search by value, linear scan, sorted array) are comparators, not the library; they are listed apart.

## Verdict

SLOWER-ROWS, by design. Six `enum_type` hit rows are 0.48-0.76 of START on the M4 and six are 0.42-0.76 on the i9 (geomean 0.864 and 0.838): the verification added on 2026-10-31 (a hash hit is compared with the member's name before it is accepted; START accepted forged colliding strings). On both machines the miss rows through `enum_type` are 0.98-1.02 except the 128 dense miss (1.141 on the M4, 1.149 on the i9, faster). On the M4 the `enum_name` rows are unchanged (0.99-1.01). On the i9 one `enum_name` row is also outside the A/A spread: `128 dense name(value) enum_name` at 0.879 (range 0.83-0.90, A/A 2.6%), which the change does not touch and whose 8 and 32 member counterparts read 1.05 and 0.99; unexplained here.

## Rows: m4

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| Method hit enum_type (exact case) | 2.82 ns | 4.24 ns | 0.677 | 0.662-0.678 | 2.1% | slower |
| Method miss enum_type (throws) | 2059 ns | 2055 ns | 1.000 | 0.999-1.029 | 2.2% | noise |
| Status hit enum_type (exact case) | 2.78 ns | 4.28 ns | 0.650 | 0.626-0.694 | 0.4% | slower |
| Status miss enum_type (throws) | 2165 ns | 2205 ns | 0.982 | 0.980-0.987 | 1.0% | slower |
| 8 dense name(value) enum_name | 1.45 ns | 1.46 ns | 0.993 | 0.973-0.993 | 1.4% | noise |
| 8 dense value(name) hit enum_type | 3.15 ns | 4.26 ns | 0.739 | 0.713-0.782 | 1.2% | slower |
| 8 dense value(name) miss enum_type (throws) | 2656 ns | 2633 ns | 1.003 | 0.999-1.017 | 1.7% | noise |
| 32 dense name(value) enum_name | 1.44 ns | 1.45 ns | 0.993 | 0.973-1.007 | 1.4% | noise |
| 32 dense value(name) hit enum_type | 3.49 ns | 4.72 ns | 0.733 | 0.732-0.802 | 4.2% | slower |
| 32 dense value(name) miss enum_type (throws) | 3146 ns | 3128 ns | 1.005 | 0.997-1.011 | 0.9% | noise |
| 128 dense name(value) enum_name | 1.55 ns | 1.52 ns | 1.013 | 1.000-1.020 | 1.3% | faster |
| 128 dense value(name) hit enum_type | 3.87 ns | 8.02 ns | 0.483 | 0.474-0.493 | 1.8% | slower |
| 128 dense value(name) miss enum_type (throws) | 4135 ns | 3626 ns | 1.141 | 1.130-1.148 | 0.7% | faster |
| 32 sparse name(value) enum_name | 1.45 ns | 1.46 ns | 0.986 | 0.973-1.000 | 1.4% | slower |
| 32 sparse value(name) hit enum_type | 3.53 ns | 4.63 ns | 0.759 | 0.756-0.762 | 3.8% | slower |
| 32 sparse value(name) miss enum_type (throws) | 4097 ns | 4084 ns | 1.002 | 0.999-1.006 | 1.4% | noise |

Not comparable (shim or comparator rows), m4:

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| Method hit enum_try_type | 2.70 ns | 4.34 ns | 0.634 | 0.619-0.637 | 2.6% | slower |
| Method hit enum_try_type (lower) | 2.71 ns | 4.68 ns | 0.575 | 0.574-0.582 | 1.5% | slower |
| Status hit enum_try_type | 2.63 ns | 4.00 ns | 0.661 | 0.655-0.665 | 1.9% | slower |
| Status hit enum_try_type (lower) | 2.63 ns | 5.87 ns | 0.446 | 0.445-0.453 | 0.8% | slower |
| 8 dense name(value) array by value | 0.32 ns | 0.34 ns | 0.941 | 0.941-1.000 | 3.0% | slower |
| 8 dense name(value) binary search by value | 1.95 ns | 1.99 ns | 0.980 | 0.975-0.985 | 0.5% | slower |
| 8 dense value(name) hit linear scan | 0.89 ns | 0.98 ns | 0.908 | 0.907-0.908 | 8.2% | slower |
| 8 dense value(name) hit sorted array | 10.8 ns | 11.0 ns | 0.985 | 0.947-1.001 | 6.1% | noise |
| 32 dense name(value) array by value | 0.32 ns | 0.33 ns | 0.970 | 0.970-1.000 | 3.0% | slower |
| 32 dense name(value) binary search by value | 3.54 ns | 3.53 ns | 0.989 | 0.986-1.009 | 4.1% | noise |
| 32 dense value(name) hit linear scan | 17.6 ns | 17.6 ns | 1.001 | 0.969-1.005 | 1.2% | noise |
| 32 dense value(name) hit sorted array | 16.6 ns | 16.8 ns | 0.984 | 0.980-1.005 | 2.2% | noise |
| 128 dense name(value) array by value | 0.33 ns | 0.32 ns | 1.031 | 1.000-1.062 | 6.2% | noise |
| 128 dense name(value) binary search by value | 5.95 ns | 5.87 ns | 1.014 | 0.993-1.024 | 3.3% | noise |
| 128 dense value(name) hit linear scan | 63.1 ns | 63.5 ns | 0.994 | 0.985-1.003 | 0.7% | noise |
| 128 dense value(name) hit sorted array | 21.8 ns | 22.0 ns | 0.993 | 0.991-0.996 | 1.1% | noise |
| 32 sparse name(value) binary search by value | 3.56 ns | 3.55 ns | 0.997 | 0.997-1.017 | 2.3% | noise |
| 32 sparse value(name) hit linear scan | 17.7 ns | 17.3 ns | 1.020 | 1.005-1.056 | 2.6% | noise |
| 32 sparse value(name) hit sorted array | 16.5 ns | 16.5 ns | 0.999 | 0.990-1.004 | 0.8% | noise |

## Rows: i9

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| Method hit enum_type (exact case) | 5.86 ns | 10.8 ns | 0.545 | 0.541-0.555 | 1.2% | slower |
| Method miss enum_type (throws) | 3696 ns | 3705 ns | 0.998 | 0.993-1.022 | 1.1% | noise |
| Status hit enum_type (exact case) | 6.80 ns | 11.2 ns | 0.593 | 0.591-0.608 | 3.2% | slower |
| Status miss enum_type (throws) | 3916 ns | 4009 ns | 0.977 | 0.945-0.985 | 1.3% | slower |
| 8 dense name(value) enum_name | 3.18 ns | 3.05 ns | 1.046 | 0.997-1.050 | 2.6% | faster |
| 8 dense value(name) hit enum_type | 8.03 ns | 10.7 ns | 0.755 | 0.721-0.759 | 4.4% | slower |
| 8 dense value(name) miss enum_type (throws) | 4892 ns | 4812 ns | 1.018 | 1.003-1.020 | 2.4% | noise |
| 32 dense name(value) enum_name | 3.37 ns | 3.41 ns | 0.986 | 0.977-1.012 | 2.1% | noise |
| 32 dense value(name) hit enum_type | 7.56 ns | 11.3 ns | 0.671 | 0.658-0.699 | 6.7% | slower |
| 32 dense value(name) miss enum_type (throws) | 5819 ns | 5732 ns | 1.005 | 1.004-1.022 | 1.2% | noise |
| 128 dense name(value) enum_name | 3.40 ns | 3.87 ns | 0.879 | 0.826-0.899 | 2.6% | slower |
| 128 dense value(name) hit enum_type | 8.90 ns | 21.1 ns | 0.422 | 0.405-0.484 | 3.1% | slower |
| 128 dense value(name) miss enum_type (throws) | 7686 ns | 6626 ns | 1.149 | 1.121-1.165 | 3.1% | faster |
| 32 sparse name(value) enum_name | 3.38 ns | 3.15 ns | 1.097 | 1.041-1.102 | 7.9% | faster |
| 32 sparse value(name) hit enum_type | 8.15 ns | 10.9 ns | 0.742 | 0.724-0.792 | 12.4% | slower |
| 32 sparse value(name) miss enum_type (throws) | 7591 ns | 7475 ns | 1.019 | 1.003-1.025 | 2.0% | noise |

Not comparable (shim or comparator rows), i9:

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| Method hit enum_try_type | 6.17 ns | 9.74 ns | 0.633 | 0.620-0.654 | 3.4% | slower |
| Method hit enum_try_type (lower) | 6.14 ns | 13.5 ns | 0.452 | 0.449-0.475 | 3.8% | slower |
| Status hit enum_try_type | 6.00 ns | 10.5 ns | 0.566 | 0.566-0.572 | 1.8% | slower |
| Status hit enum_try_type (lower) | 6.07 ns | 18.3 ns | 0.331 | 0.326-0.359 | 13.5% | slower |
| 8 dense name(value) array by value | 0.38 ns | 0.38 ns | 1.000 | 0.950-1.053 | 5.3% | noise |
| 8 dense name(value) binary search by value | 2.63 ns | 2.95 ns | 0.881 | 0.877-0.913 | 4.0% | slower |
| 8 dense value(name) hit linear scan | 2.37 ns | 2.81 ns | 0.829 | 0.756-0.865 | 3.0% | slower |
| 8 dense value(name) hit sorted array | 18.1 ns | 19.7 ns | 0.919 | 0.887-0.935 | 1.5% | slower |
| 32 dense name(value) array by value | 0.48 ns | 0.46 ns | 1.043 | 0.941-1.065 | 6.5% | noise |
| 32 dense name(value) binary search by value | 5.31 ns | 4.96 ns | 1.103 | 1.048-1.104 | 4.0% | faster |
| 32 dense value(name) hit linear scan | 39.7 ns | 39.7 ns | 0.992 | 0.983-1.006 | 1.4% | noise |
| 32 dense value(name) hit sorted array | 32.4 ns | 32.3 ns | 1.001 | 0.975-1.004 | 3.2% | noise |
| 128 dense name(value) array by value | 0.38 ns | 0.48 ns | 0.813 | 0.704-0.826 | 9.5% | slower |
| 128 dense name(value) binary search by value | 6.53 ns | 6.74 ns | 1.000 | 0.871-1.012 | 4.3% | noise |
| 128 dense value(name) hit linear scan | 137 ns | 139 ns | 0.986 | 0.980-1.019 | 0.7% | slower |
| 128 dense value(name) hit sorted array | 57.1 ns | 62.5 ns | 0.913 | 0.909-0.930 | 3.1% | slower |
| 32 sparse name(value) binary search by value | 3.87 ns | 3.87 ns | 1.013 | 0.974-1.031 | 6.9% | noise |
| 32 sparse value(name) hit linear scan | 45.1 ns | 44.4 ns | 1.010 | 0.976-1.050 | 5.5% | noise |
| 32 sparse value(name) hit sorted array | 31.1 ns | 31.7 ns | 0.976 | 0.949-0.993 | 2.8% | noise |

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- `enum_type` hits on 8- to 128-member enums and on `Status` and `Method` (M4 0.483 to 0.759, i9
  0.422 to 0.755): accepted. A hit compares the name, ASCII case-insensitively, after the hash
  matches; start returned a member for any 15-byte string built to share its 64-bit hash. A faster
  check is in progress.
- i9 `enum_name` of a 128-member dense enum 0.879: open. The change does not touch it, and the 8- and
  32-member rows read 1.05 and 0.99. No issue filed.
