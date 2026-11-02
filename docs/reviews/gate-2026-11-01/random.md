# gate: random

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/random#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Status: **measured on both machines, 4 rounds each, HEAD's bench.** **FASTER**: M4 geomean 3.02, i9 geomean 5.65 over 11 library rows;
no row below 0.97 on either machine. An earlier i9 run (3 rounds, `3956907`'s bench revision, same library) gave 5.61.

| | sha | date |
|---|---|---|
| START | `115f3f3` | 2026-10-28 |
| HEAD | `db94f4d` (origin/main at 2026-11-01 10:27) | 2026-11-01 |

Library files that differ START..HEAD: `random.cc` (mt19937_64 + `std::uniform_*_distribution` replaced by xoshiro256++, Lemire
multiply-shift, 6-bit string fields; engine in the new internal `random_engine.hh`). `random.hh` is unchanged. Between `3956907` (first look)
and `db94f4d` only `bench/bench.cc`, CMake comments and docs changed: the library file is identical.

## Machines, compiler, commands

| | CPU | OS | compiler |
|---|---|---|---|
| M4 | Apple M4 Pro (14 cores) | macOS, arm64 | Apple clang 17.0.0 (clang-1700.3.19.1) |
| i9 | Intel i9-9980HK (8C/16T) | macOS 15, x86_64 | Apple clang 17.0.0 (clang-1700.6.4.2) |

- Benchmark: HEAD's `bench/bench.cc` (`random_bench`), one source for both builds. It times the library (`library`) against
  `std::mt19937_64` with `std::uniform_*_distribution` as Xapiand used it (`std`; `noinline`, START's implementation), median of nine
  batches per row, one thread, and checks that both stay inside their ranges. The comparator column is the control: START's library column
  and it agree within a few percent (M4 `random_int(0,999999)`: 4.39 ns library, 4.58 ns comparator).
- A (START) = HEAD's tree with `random.cc random.hh` put back to `115f3f3` (`git checkout 115f3f3 -- random.cc random.hh`), HEAD's
  CMakeLists; B (HEAD) = HEAD's tree. `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DRANDOM_BUILD_BENCH=ON && cmake --build
  build --target random_bench` (`-O3 -DNDEBUG`), same layout and flags for A and B.
- Rounds: `gate-run.sh random random_bench 4`: per round A, B, A again (the A/A control), interleaved, in one `quiet strict` hold per machine
  (`gate-hold.sh random`; M4 11:14:01 to 11:15:37, i9 12:06:39 to 12:12:55; the builds ran inside the holds). Ratios from `gate-cmp.py`
  (built on `ab_compare.py compare`): START/HEAD, above 1 = HEAD faster; "range" = min and max of the four paired ratios; A/A = the first A
  against the second A; the verdict means outside the A/A spread.
- Raw outputs: `$GATE/results/{m4,i9}/random/random_bench/{a,b,aa}/`; the first i9 run is in `results/i9/random.run1-3956907-bench/`.

## M4 (the machine was quiet: A/A within 0.5%)

| row                      |  START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------ | -----: | ----: | ---------: | --------: | ----: | : | ------: |
| random_int(0,999999)     |   4.39 |  2.48 |     1.768x | 1.76-1.81 | 1.003 | 4 |  faster |
| random_int(0,2^64-1)     |   3.26 |  2.48 |     1.312x | 1.30-1.35 | 1.005 | 4 |  faster |
| random_int(1,6)          |   8.21 |  2.46 |     3.340x | 3.30-3.40 | 1.002 | 4 |  faster |
| random_real(0,1)         |   2.91 |  2.50 |     1.161x | 1.16-1.17 | 1.002 | 4 |  faster |
| random_time(100ms,500ms) |   7.46 |  2.50 |     2.984x | 2.96-3.06 | 1.005 | 4 |  faster |
| random_string(1)         |   6.93 |  5.58 |     1.241x | 1.24-1.24 | 0.997 | 4 |  faster |
| random_string(8)         |   33.7 |  8.14 |     4.118x | 4.11-4.16 | 1.001 | 4 |  faster |
| random_string(16)        |   64.2 |  11.5 |     5.569x | 5.43-5.59 | 1.002 | 4 |  faster |
| random_string(32)        |  148.4 |  32.4 |     4.582x | 4.56-4.63 | 1.002 | 4 |  faster |
| random_string(64)        |  272.9 |  43.0 |     6.352x | 6.28-6.42 | 1.002 | 4 |  faster |
| random_string(256)       | 1036.8 | 120.0 |     8.643x | 8.59-8.72 | 1.000 | 4 |  faster |

ns per call. **M4 geomean 3.022** over 11 rows (per-run 3.005 / 3.025 / 3.051; A/A geomean 1.002). Control (the `std` comparator column, same
source in both binaries): geomean 1.002, every row 0.998 to 1.006. Rows below 0.97: **none**.

## i9 (the machine was noisier: A/A deviations up to 7.2%)

| row                      |  START |  HEAD | START/HEAD |       range |   A/A | n | verdict |
| ------------------------ | -----: | ----: | ---------: | ----------: | ----: | : | ------: |
| random_int(0,999999)     |   19.6 |  5.27 |     3.604x |   3.33-3.97 | 1.055 | 4 |  faster |
| random_int(0,2^64-1)     |   8.87 |  3.83 |     2.206x |   2.13-2.41 | 1.053 | 4 |  faster |
| random_int(1,6)          |   23.9 |  4.77 |     4.925x |   4.57-5.23 | 1.005 | 4 |  faster |
| random_real(0,1)         |   11.6 |  5.80 |     1.995x |   1.68-2.07 | 1.020 | 4 |  faster |
| random_time(100ms,500ms) |   23.9 |  4.80 |     4.978x |   4.58-5.47 | 1.048 | 4 |  faster |
| random_string(1)         |   27.8 |  9.44 |     2.878x |   2.71-3.16 | 1.046 | 4 |  faster |
| random_string(8)         |  158.1 |  16.7 |     9.484x |   9.22-9.94 | 1.027 | 4 |  faster |
| random_string(16)        |  288.1 |  25.7 |    11.228x | 11.18-15.72 | 1.005 | 4 |  faster |
| random_string(32)        |  661.1 |  83.2 |     8.032x |   7.60-8.56 | 1.046 | 4 |  faster |
| random_string(64)        | 1295.1 | 105.8 |    12.296x | 11.47-17.40 | 1.072 | 4 |  faster |
| random_string(256)       | 4782.6 | 299.7 |    16.011x | 13.98-17.09 | 1.009 | 4 |  faster |

ns per call. **i9 geomean 5.653** over 11 rows (per-run 5.472 / 5.663 / 6.100; A/A geomean 1.035). Control (the `std` comparator column):
geomean 1.024, every row 1.001 to 1.058. Rows below 0.97: **none**. The first i9 run (3 rounds, 09:09, `3956907`'s bench revision with `old`/`new`
labels) agrees: geomean 5.605, rows 1.9x to 16.5x, A/A within 4.6%.

## Rows below 0.97

None on either machine.

## Notes

- Correctness: the engine is not part of the contract (the API has no seed). The generator is seeded from 256 bits instead of 32 and draws
  are unbiased (Lemire rejection); `random_string` drops the old `sizeof(chrs) - 2` bound. Outputs are random either way, so the rows
  are comparable.
- CHANGELOG (2026-10-31): the library against itself before the bench was made `noinline` (`94f156a`) moved the `random_int` rows by up to
  25% either way with code placement on the i9 (same machine code); that is a layout effect of the benchmark, not a library cost. START
  here is `115f3f3` (the mt19937 code), so this does not enter the comparison.
