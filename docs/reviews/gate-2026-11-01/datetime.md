# gate: datetime

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/datetime#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Status: **measured on both machines, 7 rounds each.** **FASTER**: M4 geomean 6.44, i9 geomean 7.44 over 27 library rows; no row below 0.97
on either machine.

| | sha | date |
|---|---|---|
| START | `fce3d4d` | 2026-10-28 |
| HEAD | `672fde6` (origin/main at 2026-11-01 10:27; library files identical to `3c9adbe`, the later commits change the README) | 2026-11-01 |

START is the original extraction (`std::regex`, `strto*`, `gmtime_r`, `std::format` chains). HEAD (2026-10-30 and 10-31) replaces them with
hand-written scanners and an integer civil calendar, and fixes a list of defects (below). `datetime.cc` changed by about 1,350 lines,
`datetime.h` by 7. The `strict-stox` pin (`21b7941`) is the same on both sides.

## Machines, compiler, commands

| | CPU | OS | compiler |
|---|---|---|---|
| M4 | Apple M4 Pro (14 cores) | macOS, arm64 | Apple clang 17.0.0 (clang-1700.3.19.1) |
| i9 | Intel i9-9980HK (8C/16T) | macOS 15, x86_64 | Apple clang 17.0.0 (clang-1700.6.4.2) |

- Benchmarks (HEAD's sources, one source for both builds): `datetime_bench` (`bench/bench.cc` with the frozen original
  `test/old/datetime_old.cc` linked in: `old` column = frozen original, `new` column = the library, ns per call) and `datetime_compare`
  (`bench/compare.cc`, new in HEAD: the library against a hand-written ISO parser, civil-calendar algorithms, libc `strptime`+`timegm` and
  abseil; the `ours` column is the row, the comparators are controls). Both build against START's library; no row is dropped.
- A (START) = HEAD's tree with `datetime.cc datetime.h` put back to `fce3d4d` (`git checkout fce3d4d -- datetime.cc datetime.h`), HEAD's
  CMakeLists; B (HEAD) = HEAD's tree. `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DDATETIME_BUILD_BENCH=ON && cmake --build
  build --target datetime_bench datetime_compare` (`-O3 -DNDEBUG`), same directory layout and flags for A and B.
- Rounds: `gate-run.sh datetime <target> 7`: per round A, B, A again (the A/A control), interleaved, all inside one `quiet strict` hold
  (`gate-hold.sh datetime`; M4 hold 11:03:55 to 11:04:33, i9 hold 10:56 to 10:57:32; the M4 build ran inside the hold). Ratios from
  `gate-cmp.py` (built on `ab_compare.py compare`): START/HEAD, above 1 = HEAD faster; "range" is the min and max of the seven paired
  ratios; A/A is the first A against the second A (its largest deviation is the A/A spread); the verdict `faster`/`slower` means outside
  that spread.
- Raw outputs: `$GATE/results/{m4,i9}/datetime/<target>/{a,b,aa}/`.

## M4 (7 rounds; every A/A deviation is 4.5% or less)

`datetime_bench`, ns per call: geomean 6.103 (per-run 5.893 / 6.116 / 6.239; A/A geomean 0.999).

| row                           |  START | HEAD | START/HEAD |       range |   A/A | n | verdict |
| ----------------------------- | -----: | ---: | ---------: | ----------: | ----: | : | ------: |
| parse YYYY-MM-DD              |   44.9 | 9.40 |     4.763x |   4.72-5.03 | 0.987 | 7 |  faster |
| parse ...T00:00:00            |   90.3 | 14.0 |     6.465x |   6.30-6.64 | 0.988 | 7 |  faster |
| parse ...Z                    |   90.2 | 14.2 |     6.469x |   6.04-6.93 | 1.018 | 7 |  faster |
| parse .ffffffZ                |  109.9 | 18.7 |     5.932x |   5.75-6.30 | 0.984 | 7 |  faster |
| parse ...+hh:mm               |  253.5 | 30.3 |     8.416x |   7.96-8.78 | 1.007 | 7 |  faster |
| parse .ffffff+hh:mm           |  259.4 | 32.9 |     7.866x |   7.72-8.39 | 1.008 | 7 |  faster |
| parse 2020/01/02 03:04:05     | 1395.2 | 17.5 |    79.926x | 77.02-84.21 | 0.998 | 7 |  faster |
| parse ...\|\|+1d/d            |  795.6 | 54.5 |    14.798x | 13.79-15.12 | 0.994 | 7 |  faster |
| isDatetime .ffffffZ           |   89.2 | 14.6 |     6.095x |   5.72-6.37 | 1.030 | 7 |  faster |
| iso8601 trim, mixed fsec, UTC |  236.1 | 25.0 |     9.444x |  8.02-10.74 | 0.993 | 7 |  faster |
| iso8601 full .000000          |  231.1 | 30.3 |     7.698x |   6.06-8.17 | 0.971 | 7 |  faster |
| to_tm_t(time_t)               |   36.9 | 7.90 |     4.658x |   4.52-5.01 | 1.016 | 7 |  faster |
| toordinal                     |   3.10 | 1.80 |     1.722x |   1.63-1.82 | 1.000 | 7 |  faster |
| timegm(tm_t)                  |   4.60 | 2.90 |     1.586x |   1.50-1.66 | 1.000 | 7 |  faster |
| timestamp(tm_t)               |   4.30 | 2.90 |     1.517x |   1.39-1.57 | 0.978 | 7 |  faster |
| to_tm_t(double)               |   37.2 | 7.90 |     4.679x |   4.28-5.05 | 1.005 | 7 |  faster |

`datetime_compare` (`ours` column), ns per call: geomean 6.956 (per-run 6.847 / 6.957 / 7.139; A/A geomean 1.006).

| row                       |  START | HEAD | START/HEAD |       range |   A/A | n | verdict |
| ------------------------- | -----: | ---: | ---------: | ----------: | ----: | : | ------: |
| parse YYYY-MM-DD          |   49.6 | 11.2 |     4.453x |   4.13-4.56 | 1.045 | 7 |  faster |
| parse ...T00:00:00        |   95.8 | 16.1 |     5.950x |   5.78-6.11 | 1.012 | 7 |  faster |
| parse ...Z                |   93.8 | 16.5 |     5.756x |   5.48-5.91 | 1.001 | 7 |  faster |
| parse .ffffffZ            |  114.2 | 20.5 |     5.626x |   5.40-6.09 | 1.006 | 7 |  faster |
| parse ...+hh:mm           |  247.7 | 28.7 |     8.639x |   8.48-9.19 | 0.989 | 7 |  faster |
| parse .ffffff+hh:mm       |  269.8 | 30.1 |     8.842x |   8.61-9.25 | 1.007 | 7 |  faster |
| parse 2020/01/02 03:04:05 | 1454.2 | 20.7 |    70.605x | 66.71-73.44 | 1.005 | 7 |  faster |
| timestamp(tm_t)           |   4.30 | 2.90 |     1.517x |   1.43-1.57 | 1.000 | 7 |  faster |
| to_tm_t(time_t)           |   36.6 | 9.10 |     4.033x |   3.96-4.16 | 1.000 | 7 |  faster |
| iso8601(tm_t), mixed fsec |  241.4 | 23.5 |    10.381x |   9.35-11.41 | 0.991 | 7 |  faster |
| isDatetime(.ffffffZ)      |   85.8 | 13.8 |     6.274x |   6.17-6.73 | 1.000 | 7 |  faster |

**M4 geomean 6.437** over the 27 library rows. Controls (the frozen original in `datetime_bench`, 16 rows; the hand-written, libc and
abseil comparators in `datetime_compare`, 17 rows; none calls the library): geomean 0.999 and 1.002, every row within 0.977 to 1.027.

## i9 (7 rounds; the machine was noisier: A/A deviations up to 18% on the first three rows)

`datetime_bench`, ns per call: geomean 7.019 (per-run 6.416 / 7.087 / 7.225; A/A geomean 1.039).

| row                           |  START | HEAD | START/HEAD |        range |   A/A | n | verdict |
| ----------------------------- | -----: | ---: | ---------: | -----------: | ----: | : | ------: |
| parse YYYY-MM-DD              |  122.2 | 21.3 |     5.737x |    3.03-6.82 | 1.184 | 7 |  faster |
| parse ...T00:00:00            |  233.2 | 34.6 |     6.698x |    5.69-7.69 | 1.184 | 7 |  faster |
| parse ...Z                    |  204.0 | 31.6 |     6.559x |    5.48-7.38 | 1.046 | 7 |  faster |
| parse .ffffffZ                |  260.1 | 38.8 |     6.756x |    6.26-7.04 | 1.044 | 7 |  faster |
| parse ...+hh:mm               |  581.3 | 54.8 |    10.608x |    9.71-11.03 | 1.010 | 7 |  faster |
| parse .ffffff+hh:mm           |  664.7 | 66.0 |     9.856x |    8.49-10.47 | 1.045 | 7 |  faster |
| parse 2020/01/02 03:04:05     | 4678.1 | 44.6 |   104.845x | 92.64-113.03 | 0.982 | 7 |  faster |
| parse ...\|\|+1d/d            | 2389.3 | 99.6 |    23.989x |  23.62-27.54 | 1.047 | 7 |  faster |
| isDatetime .ffffffZ           |  224.5 | 28.8 |     7.795x |    6.68-7.89 | 1.016 | 7 |  faster |
| iso8601 trim, mixed fsec, UTC |  586.0 | 50.8 |    11.673x |   10.50-12.50 | 1.013 | 7 |  faster |
| iso8601 full .000000          |  557.5 | 68.3 |     8.111x |    7.81-8.66 | 1.005 | 7 |  faster |
| to_tm_t(time_t)               |   87.5 | 16.5 |     5.305x |    5.27-5.51 | 1.046 | 7 |  faster |
| toordinal                     |   5.80 | 3.40 |     1.706x |    1.62-1.71 | 1.000 | 7 |  faster |
| timegm(tm_t)                  |   8.60 | 5.20 |     1.654x |    1.60-1.69 | 1.012 | 7 |  faster |
| timestamp(tm_t)               |   11.7 | 6.90 |     1.696x |    1.62-1.70 | 1.000 | 7 |  faster |
| to_tm_t(double)               |   90.6 | 21.9 |     4.137x |    3.96-4.17 | 1.009 | 7 |  faster |

`datetime_compare`, ns per call: geomean 8.109 (per-run 7.211 / 8.252 / 8.699; A/A geomean 1.021).

| row                       |  START | HEAD | START/HEAD |        range |   A/A | n | verdict |
| ------------------------- | -----: | ---: | ---------: | -----------: | ----: | : | ------: |
| parse YYYY-MM-DD          |  128.0 | 25.7 |     5.019x |    4.22-6.14 | 1.004 | 7 |  faster |
| parse ...T00:00:00        |  249.8 | 39.0 |     6.427x |    5.33-8.01 | 1.143 | 7 |  faster |
| parse ...Z                |  221.2 | 39.2 |     6.290x |    5.35-6.70 | 1.014 | 7 |  faster |
| parse .ffffffZ            |  274.0 | 43.7 |     6.272x |    5.27-6.60 | 0.999 | 7 |  faster |
| parse ...+hh:mm           |  600.6 | 55.9 |    10.950x |    8.79-12.08 | 1.017 | 7 |  faster |
| parse .ffffff+hh:mm       |  661.7 | 65.1 |    10.317x |    8.68-11.24 | 1.028 | 7 |  faster |
| parse 2020/01/02 03:04:05 | 4811.5 | 48.9 |   101.158x | 89.02-116.46 | 1.026 | 7 |  faster |
| timestamp(tm_t)           |   10.1 | 6.40 |     1.578x |    1.52-1.85 | 1.000 | 7 |  faster |
| to_tm_t(time_t)           |   90.1 | 20.6 |     4.279x |    4.17-5.03 | 0.999 | 7 |  faster |
| iso8601(tm_t), mixed fsec |  556.6 | 41.9 |    13.638x |   11.92-14.92 | 1.006 | 7 |  faster |
| isDatetime(.ffffffZ)      |  211.2 | 27.0 |     7.439x |    6.66-8.73 | 1.005 | 7 |  faster |

**i9 geomean 7.444** over the 27 library rows. Controls: geomean 1.049 (frozen original, 0.974 to 1.162, inside the A/A noise of that
run) and 0.998 (comparators).

## Rows below 0.97

None on either machine (0 of 27 on the M4, 0 of 27 on the i9). The two rows the CHANGELOG names as moving the wrong way between the 10-30
scanners and the 10-31 fixes (`parse ...+hh:mm` on the M4, `parse 2020/01/02 03:04:05` on the i9) are 8.4x and 105x faster than START.

## Correctness changes that make rows not directly comparable

`datetime_bench` stops with `DIFFERENT` if the frozen original and the library disagree on a bench input, and `datetime_compare` prints it
for a comparator that disagrees, so the timed inputs are outside the changed classes and every timed row does equal work. The behavior
changes, each with its input class and test, are in the CHANGELOG (2026-10-31): `+12M` and month multiples of 12 (was an error), a loose
offset sets `is_utc`, the two `Iso8601Parser` overloads agree (negative fields, empty or 63+ digit fractions rejected by both), a loose
`...Z` parses, date-math terms in 64-bit with a year-range error, timestamps before 1970 with a fraction, and `normalizeMonths` for extreme
months (a loop of 180 million iterations before). Inputs in those classes do different work in START and HEAD and are not timed.
