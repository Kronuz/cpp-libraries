# gate: time-point

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). The repository's README has no benchmark command; the gate timed a micro-bench written for it, not kept. `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Status: **measured on both machines, 7 rounds each, with a micro-bench written for the gate (the repository has none).**
**SAME**: M4 geomean 0.999, i9 geomean 0.994 over the 5 rows START can build; no row below 0.97 on either machine.

| | sha | date |
|---|---|---|
| START | `2f1f7f9` | 2026-10-28 |
| HEAD | `fa72b62` (origin/main at 2026-11-01 10:27, unchanged since 07:12) | 2026-11-01 |

`time-point` is header-only (`time_point.hh`; it includes the pinned `nanosleep.h`, `256aaf6`, the same on both sides). Library change
START..HEAD, in `time_point.hh` only: `time_point_to_ullong` deduces `time_point<Clock, Duration>` for any duration; the conversions go
through `floor_to` (the implicit conversion when lossless, else `std::chrono::floor`, so an instant before the epoch never rounds later),
which makes `time_point_from_ullong<system_clock>` build on libc++; new `time_point_to_llong` / `time_point_from_llong`; the unsigned pair
is the two's complement image of the signed pair.

## Hot entry points

`time_point_to_ullong(tp)` and `time_point_from_ullong<Clock>(n)` (nanosecond counts for storage and wire formats), on `steady_clock`
(identity on a nanosecond clock) and `system_clock` (microsecond ticks on libc++).

## Machines, compiler, commands

| | CPU | OS | compiler |
|---|---|---|---|
| M4 | Apple M4 Pro (14 cores) | macOS, arm64 | Apple clang 17.0.0 (clang-1700.3.19.1) |
| i9 | Intel i9-9980HK (8C/16T) | macOS 15, x86_64 | Apple clang 17.0.0 (clang-1700.6.4.2) |

- Micro-bench (`$GATE/micro/time_point_bench.cc`): one source compiled against START's header and HEAD's:
  `c++ -std=c++20 -O3 -DNDEBUG -I<dir with that header> -I<nanosleep>` (`gate-micro.sh time-point 2f1f7f9 fa72b62`), with `-DGATE_NEW_API`
  on the HEAD build only for the two rows START cannot build (`time_point_from_ullong<system_clock>` and `time_point_to_llong`; they are
  "only in B" and left out of the geomean). Five rows common to both: `to_ullong(steady tp)`, `from_ullong<steady>(n)`, `to_ullong(system tp)`,
  `from_ullong(to_ullong(steady tp))`, `to_ullong(system_clock::now())`; 4096 inputs read through an opaque pointer, best of 9 runs of about
  15 ms, ns per operation.
- Rounds: `gate-run.sh time-point time_point_bench 7`: per round A, B, A again (the A/A control), interleaved, in one `quiet strict` hold per
  machine (`gate-hold.sh time-point`; M4 12:15:37 to 12:16:09, i9 12:46:26 to 12:46:59; the builds ran inside the holds). Ratios from
  `gate-cmp.py` (built on `ab_compare.py compare`): START/HEAD, above 1 = HEAD faster; "range" = min and max of the seven paired ratios;
  A/A = the first A against the second A.
- Raw outputs: `$GATE/results/{m4,i9}/time-point/time_point_bench/{a,b,aa}/`.

## M4 (A/A within 0.6%)

| row                                       | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| time_point_to_ullong(steady tp)           | 0.065 | 0.065 |     1.000x | 0.98-1.00 | 1.000 | 7 |   noise |
| time_point_from_ullong<steady>(n)         | 0.065 | 0.065 |     1.000x | 0.98-1.02 | 1.000 | 7 |   noise |
| time_point_to_ullong(system tp)           | 0.164 | 0.164 |     1.000x | 0.99-1.02 | 1.006 | 7 |   noise |
| from_ullong(to_ullong(steady tp))         | 0.065 | 0.065 |     1.000x | 0.97-1.00 | 1.000 | 7 |   noise |
| time_point_to_ullong(system_clock::now()) |  14.3 |  14.4 |     0.995x | 0.98-1.02 | 1.004 | 7 |   noise |

ns per operation. **M4 geomean 0.999** over the 5 common rows (per-run 0.994 / 0.998 / 1.004; A/A geomean 1.002); two rows only in HEAD
(`from_ullong<system_clock>`, `to_llong`), which START does not build on libc++. Rows below 0.97: **none**. The CHANGELOG's own table
(M4): 0.061 to 0.061 ns, 0.164 to 0.162 ns, `now()` 14.0 ns both; this gate reads 0.065, 0.164 and 14.3 to 14.4 ns.

## i9 (A/A within 1.4%)

| row                                       | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| time_point_to_ullong(steady tp)           | 0.068 | 0.069 |     0.986x | 0.99-1.00 | 0.986 | 7 |   noise |
| time_point_from_ullong<steady>(n)         | 0.069 | 0.069 |     1.000x | 0.97-1.03 | 1.000 | 7 |   noise |
| time_point_to_ullong(system tp)           | 0.304 | 0.306 |     0.993x | 0.96-1.02 | 1.000 | 7 |   noise |
| from_ullong(to_ullong(steady tp))         | 0.068 | 0.069 |     0.986x | 0.97-1.00 | 1.000 | 7 |   noise |
| time_point_to_ullong(system_clock::now()) |  27.6 |  27.5 |     1.007x | 0.99-1.02 | 0.995 | 7 |   noise |

ns per operation (hold 12:46:26 to 12:46:59). **i9 geomean 0.994** over the 5 common rows (per-run 0.977 / 0.994 / 1.012; A/A geomean 0.996).
The CHANGELOG's own table (i9): 0.069 to 0.068 ns, 0.301 to 0.298 ns, `now()` 27.2 ns both; this gate reads 0.068 to 0.069, 0.304 to 0.306 and
27.6 to 27.5 ns. Rows below 0.97: **none**.

## Rows below 0.97

None on either machine.

## Correctness changes that affect comparability

Only an instant before the epoch on a clock finer than a nanosecond at a non-whole-nanosecond tick rounds differently (-1500 ps: START -1 ns,
HEAD -2 ns); no timed row uses one. START does not build `from_ullong<system_clock>` on libc++.
