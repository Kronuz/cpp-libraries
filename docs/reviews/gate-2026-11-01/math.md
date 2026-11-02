# Gate: math (micro-bench, the repo has no bench)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). The repository's README has no benchmark command; the gate timed a micro-bench written for it, not kept. `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

`math` has no bench, so this gate uses a micro-bench. The only library source that changed since START is `math.hh`: `modulus` was rewritten (a `!(mod > 0)` guard so a zero modulus throws, the magnitude of a negative `val` taken as an unsigned value in the wider of the two types, `val` reduced before it is narrowed); `add`/`sub` form the sum or difference in `T` (so `uint8_t`/`uint16_t` wrap) and the two-argument overloads start their flag at `false`; `min<double>` returns `lowest()`. The rest of the diff is docs, `CMakeLists.txt` (a UBSan test target) and tests (191 lines).

Hot entry points: `modulus(T, M)` for every pair of integer types, `add(x, y, overflow)`, `sub(x, y, overflow)`. Micro-bench `math/micro.cc`: 4096 pseudo-random inputs from a fixed xorshift64 seed, summed into a checksum. Rows: `modulus_i32_pos`, `_neg`, `_mixed` (random sign), `_pow2` (power-of-two moduli), `_const1000` (constant modulus), `modulus_i64`, `_u32`, `_u64`, `modulus_i32_by_u32`, `_i32_by_i64`, `_i64_by_i32` (mixed types, values that fit both so the results agree), and `add`/`sub` on `uint32_t`/`uint64_t` with the overflow flag (about a quarter of the pairs overflow) and without. Rows are ns per operation; the checksums agree between START and HEAD on both machines for all 17 rows.

## Versions and rig

- START `2730483144785dc73892e2274f37ad380a600729` (2026-10-28 04:47 -0700), HEAD `5486d04dcdc99579d5b9f2ff4df3f9b09f4e71a5` (2026-11-01 05:30 -0800); both are first-parent commits of origin/main, fetched 2026-11-01.
- Both sides are HEAD's tree with START's library sources overlaid (`git diff --cached --stat HEAD` in the START tree):
```
 math.hh | 54 ++++++++++++++----------------------------------------
 1 file changed, 14 insertions(+), 40 deletions(-)
(library path replaced from START: math.hh)
```
- M4: Apple M4 Pro (14 cores, 48 GiB), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), target arm64-apple-darwin25.6.0, `python3` 3.12.16.
- i9: Intel Core i9-9980HK @ 2.40 GHz (8C/16T, 32 GiB), macOS 15.8.1 x86_64, Apple clang 17.0.0 (clang-1700.6.4.2), target x86_64-apple-darwin24.6.0, `python3` 3.15.0.
- Flags (CMake Release, same both sides and both machines): `/usr/bin/clang++ -O3 -DNDEBUG -std=gnu++20` (`-arch arm64` on the M4; no `-march`). `math` is header-only and has no dependencies.

Commands (run from `$GATE`, same on both machines):

```
rig/prep.sh math      # worktrees head/ and start/ (START sources overlaid on HEAD)
rig/build.sh math     # cmake -S rig -B math/build-{head,start} -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DTREE=math/{head,start} -DMICRO=math/micro.cc -DLIB=math::math -DSTD=20
                         # cmake --build ... -j4  ->  math/micro.{start,head}
quiet strict <min> 'gate errno-names math micro A/B/A' -- rig/hold2.sh <m4|i9> errno-names math
  python3 ab_compare.py run --rounds 5 --save rig/out-<m>/math --output markdown --label-a START --label-b HEAD math/micro.start math/micro.head
quiet strict <min> 'gate confirm' -- rig/confirm.sh <m4|i9>     # second hold: the whole math micro again (math-confirm) and math/asm/order.{start,head} (math-order: the same source with the const1000 row moved first)
```
The micro-bench source is `micro.cc` next to this file's raw data (`$GATE/raw/math/micro.cc`); it prints `label  X ns  chk HEX`, each row the best of 7 repeats inside one run, with a checksum that must agree between START and HEAD (otherwise ab_compare voids the row).

**Hold waits.** On the M4 the first strict hold queued (2026-11-01 09:35) had not started after 45 minutes (about 40 strict holds from other gate runs were queued); the work was split into short holds so each could win a slot, and the first ones started at 11:08:34 (math, in the combined M4 hold, 11:08:40 to 11:09:17); the confirmation hold ran 11:34:26 to 11:37:57. On the i9: the first strict hold queued (09:51) was replaced at 10:35 by four waiters (all repos, errno-names+math, io, fs); math started at 11:54:56 (i9 hold a, 11:54:56 to 11:56:51); the confirmation hold ran 11:40:19 to 11:46:33 and actually ran before the main math hold. Light holds starved for more than 15 minutes on both machines, so the micro-benches were built outside a hold with `nice -n 19` (small builds: one or two translation units each). No unheld timing is used in the tables below.

## Apple M4 Pro

**math micro-bench (5 rounds, A/B/A interleaved)**

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| modulus_i32_pos       |  1.08 |  1.09 |     0.996x | 0.99-1.00 | 0.998 | 5 |   noise |
| modulus_i32_neg       |  1.09 |  1.09 |     1.000x | 0.99-1.02 | 0.992 | 5 |   noise |
| modulus_i32_mixed     |  1.07 |  1.09 |     0.988x | 0.98-0.99 | 0.992 | 5 |   noise |
| modulus_i32_pow2      |  1.05 |  1.06 |     0.998x | 0.99-1.00 | 0.999 | 5 |   noise |
| modulus_i32_const1000 | 0.841 | 0.917 |     0.913x | 0.90-0.98 | 1.006 | 5 |  slower |
| modulus_i64           |  1.05 |  1.05 |     1.002x | 0.99-1.01 | 0.994 | 5 |   noise |
| modulus_u32           | 0.515 | 0.521 |     0.988x | 0.98-1.00 | 1.000 | 5 |   noise |
| modulus_u64           | 0.522 | 0.537 |     0.974x | 0.95-0.98 | 1.000 | 5 |   noise |
| modulus_i32_by_u32    |  1.06 |  1.08 |     0.987x | 0.98-1.00 | 1.001 | 5 |   noise |
| modulus_i32_by_i64    |  1.05 |  1.04 |     1.001x | 0.99-1.02 | 0.994 | 5 |   noise |
| modulus_i64_by_i32    |  1.07 |  1.08 |     1.002x | 0.99-1.04 | 0.988 | 5 |   noise |
| add_u32_flag          | 0.326 | 0.330 |     0.988x | 0.98-1.00 | 0.991 | 5 |   noise |
| sub_u32_flag          | 0.356 | 0.355 |     1.003x | 0.99-1.01 | 1.000 | 5 |   noise |
| add_u64_flag          | 0.336 | 0.330 |     1.018x | 1.00-1.03 | 1.003 | 5 |  faster |
| sub_u64_flag          | 0.356 | 0.357 |     0.994x | 0.99-1.01 | 0.997 | 5 |   noise |
| add_u32_noflag        | 0.337 | 0.337 |     1.000x | 1.00-1.01 | 1.000 | 5 |   noise |
| sub_u64_noflag        | 0.338 | 0.338 |     0.997x | 0.99-1.01 | 1.003 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.991 over 17 rows (min 0.913 modulus_i32_const1000; max 1.018 add_u64_flag)
per-run geomean: min 0.989, median 0.993, max 0.997 over 5 runs
A/A geomean 0.998

uptime at the start and end of each run (hold):

```
math start: 11:08:40 11:08  up 5 days, 16:33, 14 users, load averages: 9.39 10.05 11.72
math end rc=0: 11:09:17 11:09  up 5 days, 16:34, 14 users, load averages: 8.63 9.77 11.55
math-confirm start: 11:34:27 11:34  up 5 days, 16:59, 14 users, load averages: 10.32 10.57 11.95
math-confirm end rc=0: 11:35:05 11:35  up 5 days, 17 hrs, 14 users, load averages: 9.90 10.46 11.85
math-order start: 11:35:05 11:35  up 5 days, 17 hrs, 14 users, load averages: 9.90 10.46 11.85
math-order end rc=0: 11:35:42 11:35  up 5 days, 17 hrs, 14 users, load averages: 11.92 10.88 11.94
```

## Intel i9-9980HK

**math micro-bench (5 rounds, A/B/A interleaved)**

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| modulus_i32_pos       |  2.41 |  2.41 |     1.003x | 1.00-1.01 | 1.003 | 5 |   noise |
| modulus_i32_neg       |  2.66 |  2.66 |     1.007x | 0.97-1.02 | 1.003 | 5 |   noise |
| modulus_i32_mixed     |  3.76 |  3.84 |     0.978x | 0.96-1.01 | 1.003 | 5 |   noise |
| modulus_i32_pow2      |  3.77 |  3.90 |     0.968x | 0.93-0.98 | 1.004 | 5 |  slower |
| modulus_i32_const1000 |  2.05 |  2.19 |     0.934x | 0.91-0.99 | 0.963 | 5 |   noise |
| modulus_i64           |  8.56 |  8.95 |     0.958x | 0.95-0.96 | 1.000 | 5 |  slower |
| modulus_u32           |  1.82 |  2.06 |     0.891x | 0.87-0.90 | 1.016 | 5 |  slower |
| modulus_u64           |  6.07 |  6.31 |     0.973x | 0.94-0.98 | 1.002 | 5 |  slower |
| modulus_i32_by_u32    |  4.00 |  3.59 |     1.108x | 1.10-1.13 | 0.988 | 5 |  faster |
| modulus_i32_by_i64    |  3.63 |  3.21 |     1.127x | 1.10-1.15 | 1.003 | 5 |  faster |
| modulus_i64_by_i32    |  3.75 |  3.83 |     0.965x | 0.96-0.99 | 0.997 | 5 |  slower |
| add_u32_flag          | 0.654 | 0.676 |     0.964x | 0.93-0.99 | 1.008 | 5 |  slower |
| sub_u32_flag          | 0.737 | 0.730 |     1.016x | 0.99-1.02 | 1.001 | 5 |  faster |
| add_u64_flag          | 0.651 | 0.652 |     0.995x | 0.98-1.05 | 1.003 | 5 |   noise |
| sub_u64_flag          | 0.737 | 0.743 |     0.987x | 0.98-1.01 | 0.999 | 5 |   noise |
| add_u32_noflag        | 0.479 | 0.479 |     0.998x | 0.96-1.03 | 0.998 | 5 |   noise |
| sub_u64_noflag        | 0.488 | 0.479 |     1.017x | 1.00-1.05 | 1.008 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.992 over 17 rows (min 0.891 modulus_u32; max 1.127 modulus_i32_by_i64)
per-run geomean: min 0.983, median 0.990, max 0.998 over 5 runs
A/A geomean 1.000

uptime at the start and end of each run (hold):

```
math start: 11:54:56 11:54  up 30 days, 17:48, 5 users, load averages: 9.63 8.48 8.41
math end rc=0: 11:56:51 11:56  up 30 days, 17:50, 5 users, load averages: 7.88 8.53 8.47
math-confirm start: 11:40:19 11:40  up 30 days, 17:34, 5 users, load averages: 7.70 8.22 8.78
math-confirm end rc=0: 11:42:18 11:42  up 30 days, 17:36, 5 users, load averages: 7.98 8.07 8.64
math-order start: 11:42:18 11:42  up 30 days, 17:36, 5 users, load averages: 7.98 8.07 8.64
math-order end rc=0: 11:44:17 11:44  up 30 days, 17:38, 5 users, load averages: 6.07 7.50 8.35
```

## Geomean (comparable rows, START/HEAD, above 1 = HEAD faster)

- M4: 0.991
- i9: 0.992

## Confirmation holds

**m4 math-confirm**

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| modulus_i32_pos       |  1.10 |  1.10 |     1.004x | 1.00-1.01 | 1.006 | 5 |   noise |
| modulus_i32_neg       |  1.10 |  1.09 |     1.014x | 0.98-1.02 | 1.004 | 5 |  faster |
| modulus_i32_mixed     |  1.09 |  1.09 |     1.014x | 0.98-1.02 | 1.006 | 5 |   noise |
| modulus_i32_pow2      |  1.06 |  1.06 |     1.004x | 0.98-1.02 | 1.008 | 5 |   noise |
| modulus_i32_const1000 | 0.844 | 0.915 |     0.993x | 0.92-1.01 | 1.002 | 5 |   noise |
| modulus_i64           |  1.05 |  1.07 |     0.987x | 0.97-1.01 | 0.995 | 5 |   noise |
| modulus_u32           | 0.515 | 0.524 |     0.983x | 0.98-1.02 | 1.002 | 5 |  slower |
| modulus_u64           | 0.523 | 0.547 |     0.954x | 0.94-0.97 | 1.002 | 5 |  slower |
| modulus_i32_by_u32    |  1.07 |  1.09 |     0.997x | 0.98-1.00 | 1.003 | 5 |   noise |
| modulus_i32_by_i64    |  1.05 |  1.05 |     0.996x | 0.97-1.02 | 1.002 | 5 |   noise |
| modulus_i64_by_i32    |  1.08 |  1.09 |     0.993x | 0.97-1.03 | 0.993 | 5 |   noise |
| add_u32_flag          | 0.332 | 0.329 |     1.003x | 1.00-1.02 | 1.009 | 5 |   noise |
| sub_u32_flag          | 0.356 | 0.355 |     1.003x | 0.99-1.01 | 0.992 | 5 |   noise |
| add_u64_flag          | 0.339 | 0.332 |     1.009x | 0.99-1.03 | 0.997 | 5 |  faster |
| sub_u64_flag          | 0.357 | 0.356 |     1.003x | 0.99-1.02 | 0.997 | 5 |   noise |
| add_u32_noflag        | 0.339 | 0.337 |     1.006x | 1.00-1.01 | 1.003 | 5 |   noise |
| sub_u64_noflag        | 0.339 | 0.339 |     1.000x | 0.99-1.00 | 1.000 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.998 over 17 rows (min 0.954 modulus_u64; max 1.014 modulus_i32_mixed)
per-run geomean: min 0.988, median 0.995, max 1.009 over 5 runs
A/A geomean 1.001

**m4 math-order**

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| modulus_i32_const1000 | 0.895 | 0.850 |     1.006x | 1.00-1.12 | 1.010 | 5 |   noise |
| modulus_i32_pos       |  1.10 |  1.10 |     1.001x | 0.99-1.02 | 0.996 | 5 |   noise |
| modulus_i32_neg       |  1.08 |  1.10 |     1.004x | 0.99-1.01 | 0.999 | 5 |   noise |
| modulus_i32_mixed     |  1.10 |  1.10 |     1.000x | 1.00-1.02 | 1.001 | 5 |   noise |
| modulus_i32_pow2      |  1.06 |  1.06 |     0.998x | 0.99-1.02 | 0.998 | 5 |   noise |
| modulus_i64           |  1.06 |  1.07 |     0.993x | 0.99-1.00 | 0.999 | 5 |   noise |
| modulus_u32           | 0.519 | 0.522 |     0.994x | 0.99-1.00 | 0.998 | 5 |   noise |
| modulus_u64           | 0.530 | 0.548 |     0.967x | 0.96-0.98 | 1.000 | 5 |  slower |
| modulus_i32_by_u32    |  1.08 |  1.08 |     0.993x | 0.98-1.01 | 1.000 | 5 |   noise |
| modulus_i32_by_i64    |  1.06 |  1.06 |     1.005x | 1.00-1.01 | 1.004 | 5 |   noise |
| modulus_i64_by_i32    |  1.09 |  1.09 |     1.001x | 0.99-1.01 | 1.010 | 5 |   noise |
| add_u32_flag          | 0.331 | 0.332 |     1.003x | 0.99-1.02 | 1.000 | 5 |   noise |
| sub_u32_flag          | 0.356 | 0.357 |     0.994x | 0.99-1.01 | 1.003 | 5 |   noise |
| add_u64_flag          | 0.332 | 0.338 |     0.985x | 0.97-1.00 | 1.006 | 5 |   noise |
| sub_u64_flag          | 0.358 | 0.359 |     0.997x | 0.99-1.01 | 1.000 | 5 |   noise |
| add_u32_noflag        | 0.339 | 0.339 |     1.006x | 0.99-1.01 | 0.991 | 5 |   noise |
| sub_u64_noflag        | 0.341 | 0.340 |     1.006x | 0.99-1.01 | 1.006 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.997 over 17 rows (min 0.967 modulus_u64; max 1.006 add_u32_noflag)
per-run geomean: min 0.995, median 0.997, max 1.006 over 5 runs
A/A geomean 1.001

**i9 math-confirm**

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| modulus_i32_pos       |  2.50 |  2.53 |     0.992x | 0.96-1.00 | 1.009 | 5 |   noise |
| modulus_i32_neg       |  2.73 |  2.75 |     0.988x | 0.97-1.02 | 0.997 | 5 |   noise |
| modulus_i32_mixed     |  3.84 |  4.04 |     0.950x | 0.92-0.99 | 0.965 | 5 |   noise |
| modulus_i32_pow2      |  3.90 |  4.01 |     0.973x | 0.92-1.01 | 0.963 | 5 |   noise |
| modulus_i32_const1000 |  2.16 |  2.25 |     0.980x | 0.87-1.08 | 1.002 | 5 |   noise |
| modulus_i64           |  8.69 |  9.11 |     0.954x | 0.94-1.00 | 1.005 | 5 |  slower |
| modulus_u32           |  1.83 |  2.06 |     0.891x | 0.88-0.91 | 1.015 | 5 |  slower |
| modulus_u64           |  6.24 |  6.51 |     0.949x | 0.93-0.98 | 1.016 | 5 |   noise |
| modulus_i32_by_u32    |  4.21 |  3.75 |     1.107x | 1.08-1.17 | 0.996 | 5 |  faster |
| modulus_i32_by_i64    |  3.67 |  3.27 |     1.116x | 1.07-1.18 | 0.986 | 5 |  faster |
| modulus_i64_by_i32    |  3.85 |  4.04 |     0.951x | 0.91-1.01 | 0.990 | 5 |  slower |
| add_u32_flag          | 0.657 | 0.694 |     0.944x | 0.93-0.96 | 0.981 | 5 |  slower |
| sub_u32_flag          | 0.752 | 0.745 |     1.009x | 0.99-1.02 | 0.983 | 5 |   noise |
| add_u64_flag          | 0.682 | 0.658 |     1.030x | 1.01-1.08 | 1.024 | 5 |   noise |
| sub_u64_flag          | 0.749 | 0.756 |     0.989x | 0.96-1.08 | 0.988 | 5 |   noise |
| add_u32_noflag        | 0.501 | 0.481 |     1.010x | 0.99-1.05 | 1.031 | 5 |   noise |
| sub_u64_noflag        | 0.504 | 0.488 |     1.012x | 1.00-1.05 | 1.004 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.989 over 17 rows (min 0.891 modulus_u32; max 1.116 modulus_i32_by_i64)
per-run geomean: min 0.987, median 0.992, max 1.001 over 5 runs
A/A geomean 0.997

**i9 math-order**

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| modulus_i32_const1000 |  2.23 |  2.23 |     0.984x | 0.97-1.04 | 0.995 | 5 |   noise |
| modulus_i32_pos       |  2.47 |  2.46 |     1.006x | 0.99-1.03 | 1.003 | 5 |   noise |
| modulus_i32_neg       |  2.74 |  2.70 |     1.017x | 0.97-1.08 | 1.040 | 5 |   noise |
| modulus_i32_mixed     |  4.04 |  3.93 |     1.017x | 1.00-1.06 | 1.041 | 5 |   noise |
| modulus_i32_pow2      |  4.07 |  3.93 |     1.000x | 0.96-1.07 | 1.018 | 5 |   noise |
| modulus_i64           |  9.08 |  9.16 |     0.992x | 0.98-1.00 | 0.989 | 5 |   noise |
| modulus_u32           |  1.82 |  2.10 |     0.876x | 0.85-0.91 | 0.972 | 5 |  slower |
| modulus_u64           |  6.52 |  6.43 |     1.016x | 0.93-1.04 | 1.001 | 5 |   noise |
| modulus_i32_by_u32    |  3.83 |  3.70 |     1.036x | 0.95-1.10 | 0.987 | 5 |   noise |
| modulus_i32_by_i64    |  3.11 |  3.09 |     0.996x | 0.97-1.04 | 1.012 | 5 |   noise |
| modulus_i64_by_i32    |  3.98 |  3.98 |     1.008x | 0.95-1.05 | 1.014 | 5 |   noise |
| add_u32_flag          | 0.688 | 0.678 |     0.994x | 0.92-1.07 | 0.994 | 5 |   noise |
| sub_u32_flag          | 0.746 | 0.760 |     0.999x | 0.98-1.01 | 0.993 | 5 |   noise |
| add_u64_flag          | 0.674 | 0.668 |     0.994x | 0.96-1.03 | 0.985 | 5 |   noise |
| sub_u64_flag          | 0.750 | 0.763 |     1.001x | 0.97-1.01 | 1.019 | 5 |   noise |
| add_u32_noflag        | 0.489 | 0.493 |     0.994x | 0.99-1.01 | 1.025 | 5 |   noise |
| sub_u64_noflag        | 0.496 | 0.483 |     1.039x | 0.99-1.05 | 1.002 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.998 over 17 rows (min 0.876 modulus_u32; max 1.039 sub_u64_noflag)
per-run geomean: min 0.984, median 0.998, max 1.009 over 5 runs
A/A geomean 1.005

## Rows < 0.97 outside the A/A spread

Counted when the ratio is below 0.97 with an ab_compare `slower` verdict in a hold and the second hold does not contradict it.

**M4 (1 row, worst 0.954x)**
- `modulus_u64`: 0.974x in the main hold (noise verdict, range 0.95-0.98), 0.954x in the confirmation hold (`slower`, 0.94-0.97), 0.967x in `math-order` (`slower`). `modulus_u32` points the same way (0.988x, 0.983x, 0.994x). Cause (explained): the zero-modulus guard. CHANGELOG 2026-11-01: "`modulus(val, 0)` divided by zero ... the guard was `mod < 0`; it is now `!(mod > 0)`". For an unsigned modulus `mod < 0` is constant false, so START had no check at all; HEAD tests `mod == 0` on every call (arm64 asm of the loop: a `cbz` inside it; START has none). A correctness fix with a few percent on a division-bound unsigned loop.
- Not counted: `modulus_i32_const1000` 0.913x in the main hold (range 0.90-0.98, `slower`) but 0.993x in the confirmation hold, 1.006x when the row runs first in the program (`math-order`), and the loop's machine code is the same instruction sequence at the same address in the START and HEAD binaries (`otool -tv`; only register numbers differ), as it is when compiled alone. A binary-layout artifact, not the library.

**i9 (4 rows, worst 0.891x)**
- `modulus_u32`: 0.891x (0.87-0.90), 0.891x in the confirmation hold, 0.876x in `math-order`. Same cause as above: x86-64 asm of the loop has `testl; je` added per call that START lacks; at about 1.8 ns per call the check is about 0.24 ns. Real.
- `modulus_i64` 0.958x, `modulus_i64_by_i32` 0.965x, `add_u32_flag` 0.964x (`slower`), reproduced in the confirmation hold (0.954x, 0.951x, 0.944x) but 0.992x, 1.008x, 0.994x in `math-order`, which is the same library code in a binary with the rows reordered. The `add` loop compiles to identical x86-64 code for START and HEAD (diffed), and the `i64` loops differ in one jump mnemonic (`js` against `jle`, the `mod < 0` / `!(mod > 0)` test). I attribute these three to the layout of the micro-binary, not to the library; they are counted because two holds with the same binaries reproduced them.
- Not counted: `modulus_i32_pow2` 0.968x in the main hold, 0.973x (noise) in the confirmation; `modulus_u64` 0.973x then 0.949x (noise verdict), the same zero-guard cause as `modulus_u32`.

Faster on the i9 (not a goal, an effect of the rewrite): `modulus_i32_by_u32` 1.108x and `modulus_i32_by_i64` 1.127x (1.107x, 1.116x in the confirmation hold): the x86-64 loop of START has 18 division sites (signed and unsigned paths) against 2 in HEAD's, which divides unsigned in the wider type; I did not isolate which START path costs.

## Rows dropped or not comparable

- Not timed because the results differ by design (a fixed bug that now does more or different work): `add`/`sub` on `uint8_t` and `uint16_t` (START never reported overflow because the sum was promoted to `int`), `modulus` of the lowest value of a signed type (undefined behaviour at START), `modulus` with a zero modulus (division by zero at START, an exception at HEAD), `modulus` with a `val` outside the modulus type's range (START truncated it first), and `min<double>` (a constant, `min()` against `lowest()`).
- All timed rows use inputs on which START and HEAD return the same value (the checksums agree).
- `max<T>`, `min<T>` over an accuracy list are trivial constants and are not timed.

SUMMARY repo=math m4_geomean=0.991 i9_geomean=0.992 m4_slow=1/0.954 i9_slow=4/0.891 unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 `modulus_u64` 0.954 and i9 `modulus_u32` 0.891: accepted. `modulus` tests for a zero
  modulus on every call, about 0.24 ns, and throws `std::invalid_argument` where start was
  undefined.
- i9 `modulus_i64` 0.958, `modulus_i64_by_i32` 0.965 and `add_u32_flag` 0.964: placement. The
  x86-64 code is identical, and the rows read 0.992 to 1.008 in a run with the rows in another
  order.
