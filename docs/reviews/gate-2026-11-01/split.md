# split: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/split#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `27dbc41 2026-10-28 04:52:48 -0700 Credit Germán Méndez Bravo and bound Dubalu's years`
- HEAD: `4b3010c 2026-11-01 07:53:40 -0800 Shape the README to the family standard and drop the diagram [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `split.h` (unchanged between START and HEAD: `git diff START HEAD -- split.h` is empty; the repo gained only the benchmark and its CMake target)
- Bench source: bench/compare.cc (HEAD)
- Rows dropped because the API is new since START: none
- Metric: column `ours` (the library) against the comparator column as anchor
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -I w/split-{start|head} w/split-head/bench/compare.cc`
- Raw per-round outputs: `$GATE/raw/split/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 21 | 0.995 | 0.987-1.002 | 0.993 | 1 | 0.946 iterator Split<string_view>, 65536 B memchr loop, no vector |
| Intel i9-9980HK | 21 | 1.006 | 0.993-1.017 | 0.999 | 0 | 0.982 split() char, keep blanks, 65536 B memchr loop |

**Verdict: SAME (identical source; the one row under 0.97 on the M4 is code placement of two builds of one file)**; geomean 0.995 / 1.006 (Apple M4 Pro / Intel i9-9980HK).

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: 1
  - `iterator Split<string_view>, 65536 B memchr loop, no vector`: 0.946 (round range 0.93-1.01, A/A deviation 0.043). no library change: `split.h` is byte-identical at START and HEAD, so this is the layout of two builds of the same code (the A/A deviation of the row is 0.04, round range 0.93-1.01); not a regression.
- Intel i9-9980HK: none.

## Notes

- `split.h` is byte-identical at START and HEAD; the repo's change since START is the comparison benchmark and its CMake target only. The two builds therefore run the same code, and every ratio here is the layout and noise of two compilations of one source: the geomeans are 0.995 (M4) and 1.006 (i9).
- Anchor column (the memchr / find loops written in the bench, same code in both builds) is given for reference.

## Apple M4 Pro: per-row results (library column)

| row                                                                        |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------------------------------------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| split() char, 64 B memchr loop                                             |    75.5 |    76.7 |     0.990x | 0.97-1.00 | 0.993 | 5 |   noise |
| split() char, 64 B string_view::find loop                                  |    75.4 |    76.5 |     0.996x | 0.97-1.04 | 0.993 | 5 |   noise |
| split() char, keep blanks, 64 B memchr loop                                |    89.8 |    90.3 |     1.000x | 0.99-1.01 | 0.999 | 5 |   noise |
| iterator Split<string_view>, 64 B memchr loop, no vector                   |    37.4 |    37.4 |     1.008x | 1.00-1.01 | 0.995 | 5 |   noise |
| iterator Split<string> (copies the source), 64 B memchr loop, no vector    |    67.2 |    68.2 |     0.996x | 0.99-1.00 | 0.994 | 5 |   noise |
| split() "::", 64 B string_view::find loop                                  |   105.7 |   106.8 |     1.002x | 0.99-1.01 | 1.006 | 5 |   noise |
| split() first_of ",;", 64 B find_first_of loop                             |   138.0 |   136.7 |     1.006x | 0.99-1.02 | 1.002 | 5 |   noise |
| split() char, 1024 B memchr loop                                           |   823.2 |   827.0 |     0.999x | 0.99-1.00 | 0.994 | 5 |   noise |
| split() char, 1024 B string_view::find loop                                |   816.0 |   811.4 |     1.006x | 0.97-1.02 | 0.992 | 5 |   noise |
| split() char, keep blanks, 1024 B memchr loop                              |   819.7 |   823.1 |     0.992x | 0.98-1.01 | 0.998 | 5 |   noise |
| iterator Split<string_view>, 1024 B memchr loop, no vector                 |   732.5 |   732.0 |     0.999x | 0.98-1.02 | 0.997 | 5 |   noise |
| iterator Split<string> (copies the source), 1024 B memchr loop, no vector  |  1029.8 |  1030.2 |     1.000x | 0.98-1.02 | 1.004 | 5 |   noise |
| split() "::", 1024 B string_view::find loop                                |   919.9 |   918.5 |     1.002x | 0.98-1.02 | 1.010 | 5 |   noise |
| split() first_of ",;", 1024 B find_first_of loop                           |   921.7 |   934.4 |     0.984x | 0.93-1.07 | 1.011 | 5 |   noise |
| split() char, 65536 B memchr loop                                          | 56263.3 | 56049.3 |     1.011x | 1.00-1.03 | 0.992 | 5 |   noise |
| split() char, 65536 B string_view::find loop                               | 56280.9 | 56863.0 |     0.997x | 0.97-1.04 | 0.990 | 5 |   noise |
| split() char, keep blanks, 65536 B memchr loop                             | 56293.3 | 56564.1 |     0.999x | 0.98-1.02 | 0.999 | 5 |   noise |
| iterator Split<string_view>, 65536 B memchr loop, no vector                | 53910.8 | 56783.4 |     0.946x | 0.93-1.01 | 0.973 | 5 |  slower |
| iterator Split<string> (copies the source), 65536 B memchr loop, no vector | 77484.4 | 78397.1 |     0.996x | 0.95-1.01 | 0.963 | 5 |   noise |
| split() "::", 65536 B string_view::find loop                               | 72307.9 | 73247.1 |     0.990x | 0.98-1.01 | 0.980 | 5 |   noise |
| split() first_of ",;", 65536 B find_first_of loop                          | 59445.6 | 61816.7 |     0.978x | 0.87-1.02 | 0.959 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.995 over 21 rows (min 0.946 iterator Split<string_view>, 65536 B memchr loop, no vector; max 1.011 split() char, 65536 B memchr loop)
per-run geomean: min 0.987, median 0.997, max 1.002 over 5 runs
A/A geomean 0.993

### Apple M4 Pro: anchor column (code that is the same in both builds; ratio should be 1)

| row                                                                        |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------------------------------------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| split() char, 64 B memchr loop                                             |    74.2 |    75.8 |     0.994x | 0.96-1.02 | 0.987 | 5 |   noise |
| split() char, 64 B string_view::find loop                                  |   100.4 |   100.0 |     1.011x | 0.99-1.02 | 1.010 | 5 |   noise |
| split() char, keep blanks, 64 B memchr loop                                |    89.1 |    91.7 |     0.981x | 0.95-1.01 | 1.006 | 5 |   noise |
| iterator Split<string_view>, 64 B memchr loop, no vector                   |    26.1 |    25.7 |     1.012x | 0.99-1.03 | 1.000 | 5 |  faster |
| iterator Split<string> (copies the source), 64 B memchr loop, no vector    |    26.1 |    25.8 |     1.004x | 0.98-1.02 | 1.000 | 5 |   noise |
| split() "::", 64 B string_view::find loop                                  |   106.9 |   106.6 |     1.007x | 0.99-1.03 | 0.998 | 5 |   noise |
| split() first_of ",;", 64 B find_first_of loop                             |   138.8 |   139.1 |     0.994x | 0.97-1.07 | 0.992 | 5 |   noise |
| split() char, 1024 B memchr loop                                           |   835.9 |   835.7 |     1.000x | 0.99-1.02 | 0.999 | 5 |   noise |
| split() char, 1024 B string_view::find loop                                |   917.9 |   930.2 |     0.991x | 0.97-1.01 | 0.993 | 5 |   noise |
| split() char, keep blanks, 1024 B memchr loop                              |   834.0 |   833.1 |     1.003x | 0.99-1.01 | 0.992 | 5 |   noise |
| iterator Split<string_view>, 1024 B memchr loop, no vector                 |   762.0 |   758.8 |     1.004x | 0.99-1.03 | 0.997 | 5 |   noise |
| iterator Split<string> (copies the source), 1024 B memchr loop, no vector  |   760.4 |   763.8 |     1.000x | 0.99-1.01 | 0.998 | 5 |   noise |
| split() "::", 1024 B string_view::find loop                                |   911.5 |   916.6 |     0.990x | 0.98-1.02 | 1.006 | 5 |   noise |
| split() first_of ",;", 1024 B find_first_of loop                           |   947.7 |   902.8 |     1.048x | 0.90-1.07 | 0.992 | 5 |   noise |
| split() char, 65536 B memchr loop                                          | 56722.3 | 56753.6 |     1.010x | 1.00-1.01 | 1.007 | 5 |   noise |
| split() char, 65536 B string_view::find loop                               | 79676.8 | 80074.9 |     0.995x | 0.99-1.02 | 0.987 | 5 |   noise |
| split() char, keep blanks, 65536 B memchr loop                             | 58834.6 | 58522.0 |     1.002x | 0.98-1.02 | 0.996 | 5 |   noise |
| iterator Split<string_view>, 65536 B memchr loop, no vector                | 56707.5 | 55862.0 |     1.011x | 0.99-1.02 | 1.030 | 5 |   noise |
| iterator Split<string> (copies the source), 65536 B memchr loop, no vector | 56067.9 | 55120.6 |     1.009x | 0.98-1.06 | 1.008 | 5 |   noise |
| split() "::", 65536 B string_view::find loop                               | 73096.4 | 73963.9 |     0.992x | 0.98-1.00 | 0.993 | 5 |   noise |
| split() first_of ",;", 65536 B find_first_of loop                          | 59601.9 | 58434.6 |     1.039x | 0.97-1.10 | 0.924 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.004 over 21 rows (min 0.981 split() char, keep blanks, 64 B memchr loop; max 1.048 split() first_of ",;", 1024 B find_first_of loop)
per-run geomean: min 0.997, median 1.002, max 1.015 over 5 runs
A/A geomean 0.996

## Intel i9-9980HK: per-row results (library column)

| row                                                                        |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------------------------------------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| split() char, 64 B memchr loop                                             |   224.6 |   219.5 |     1.028x | 0.99-1.07 | 1.004 | 5 |   noise |
| split() char, 64 B string_view::find loop                                  |   219.7 |   219.3 |     1.007x | 0.92-1.05 | 0.987 | 5 |   noise |
| split() char, keep blanks, 64 B memchr loop                                |   271.0 |   265.6 |     1.020x | 0.99-1.04 | 1.005 | 5 |   noise |
| iterator Split<string_view>, 64 B memchr loop, no vector                   |    82.3 |    82.9 |     1.011x | 0.95-1.03 | 0.998 | 5 |   noise |
| iterator Split<string> (copies the source), 64 B memchr loop, no vector    |   125.9 |   125.6 |     1.043x | 0.94-1.07 | 1.000 | 5 |   noise |
| split() "::", 64 B string_view::find loop                                  |   252.7 |   255.2 |     0.988x | 0.95-1.02 | 0.963 | 5 |   noise |
| split() first_of ",;", 64 B find_first_of loop                             |   327.1 |   320.6 |     1.011x | 1.00-1.05 | 1.009 | 5 |   noise |
| split() char, 1024 B memchr loop                                           |  1244.8 |  1249.2 |     0.996x | 0.95-1.02 | 1.004 | 5 |   noise |
| split() char, 1024 B string_view::find loop                                |  1247.7 |  1239.2 |     1.024x | 0.95-1.05 | 1.011 | 5 |   noise |
| split() char, keep blanks, 1024 B memchr loop                              |  1278.7 |  1270.8 |     1.003x | 0.97-1.04 | 0.991 | 5 |   noise |
| iterator Split<string_view>, 1024 B memchr loop, no vector                 |  1250.1 |  1236.8 |     1.017x | 0.99-1.03 | 0.986 | 5 |   noise |
| iterator Split<string> (copies the source), 1024 B memchr loop, no vector  |  1297.5 |  1305.4 |     0.991x | 0.97-1.02 | 0.995 | 5 |   noise |
| split() "::", 1024 B string_view::find loop                                |  1646.6 |  1660.3 |     0.994x | 0.96-1.04 | 1.002 | 5 |   noise |
| split() first_of ",;", 1024 B find_first_of loop                           |  1668.2 |  1678.5 |     0.991x | 0.94-1.05 | 1.002 | 5 |   noise |
| split() char, 65536 B memchr loop                                          | 67726.6 | 67925.2 |     0.996x | 0.93-1.06 | 0.988 | 5 |   noise |
| split() char, 65536 B string_view::find loop                               | 67989.1 | 67702.0 |     1.012x | 0.97-1.02 | 1.000 | 5 |   noise |
| split() char, keep blanks, 65536 B memchr loop                             | 63204.6 | 66074.8 |     0.982x | 0.87-1.08 | 1.016 | 5 |   noise |
| iterator Split<string_view>, 65536 B memchr loop, no vector                | 91635.2 | 92009.8 |     0.994x | 0.97-1.02 | 1.020 | 5 |   noise |
| iterator Split<string> (copies the source), 65536 B memchr loop, no vector | 89902.0 | 88669.3 |     1.001x | 1.00-1.03 | 1.015 | 5 |   noise |
| split() "::", 65536 B string_view::find loop                               | 81312.9 | 81766.6 |     1.009x | 0.98-1.04 | 0.985 | 5 |   noise |
| split() first_of ",;", 65536 B find_first_of loop                          |  137907 |  134992 |     1.004x | 0.96-1.04 | 1.007 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.006 over 21 rows (min 0.982 split() char, keep blanks, 65536 B memchr loop; max 1.043 iterator Split<string> (copies the source), 64 B memchr loop, no vector)
per-run geomean: min 0.993, median 1.000, max 1.017 over 5 runs
A/A geomean 0.999

### Intel i9-9980HK: anchor column (code that is the same in both builds; ratio should be 1)

| row                                                                        |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------------------------------------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| split() char, 64 B memchr loop                                             |   220.2 |   216.7 |     1.023x | 0.95-1.05 | 0.998 | 5 |   noise |
| split() char, 64 B string_view::find loop                                  |   254.1 |   251.9 |     1.016x | 0.96-1.09 | 1.025 | 5 |   noise |
| split() char, keep blanks, 64 B memchr loop                                |   270.2 |   263.7 |     1.016x | 0.95-1.15 | 1.010 | 5 |   noise |
| iterator Split<string_view>, 64 B memchr loop, no vector                   |    45.5 |    44.9 |     1.020x | 0.87-1.13 | 0.998 | 5 |   noise |
| iterator Split<string> (copies the source), 64 B memchr loop, no vector    |    45.1 |    44.7 |     1.013x | 0.95-1.14 | 0.980 | 5 |   noise |
| split() "::", 64 B string_view::find loop                                  |   259.2 |   250.3 |     1.021x | 0.99-1.05 | 0.984 | 5 |   noise |
| split() first_of ",;", 64 B find_first_of loop                             |   326.1 |   330.4 |     0.992x | 0.93-1.03 | 0.978 | 5 |   noise |
| split() char, 1024 B memchr loop                                           |  1215.9 |  1210.4 |     1.001x | 0.87-1.08 | 0.983 | 5 |   noise |
| split() char, 1024 B string_view::find loop                                |  1748.4 |  1765.9 |     0.993x | 0.98-1.03 | 1.009 | 5 |   noise |
| split() char, keep blanks, 1024 B memchr loop                              |  1248.2 |  1233.2 |     1.032x | 0.94-1.11 | 0.983 | 5 |   noise |
| iterator Split<string_view>, 1024 B memchr loop, no vector                 |   820.7 |   812.3 |     1.017x | 0.99-1.03 | 1.014 | 5 |   noise |
| iterator Split<string> (copies the source), 1024 B memchr loop, no vector  |   808.2 |   806.1 |     1.014x | 0.96-1.05 | 1.006 | 5 |   noise |
| split() "::", 1024 B string_view::find loop                                |  1728.1 |  1711.7 |     1.010x | 0.91-1.11 | 1.002 | 5 |   noise |
| split() first_of ",;", 1024 B find_first_of loop                           |  1864.0 |  1873.8 |     0.995x | 0.98-1.01 | 0.988 | 5 |   noise |
| split() char, 65536 B memchr loop                                          | 64932.3 | 64438.6 |     1.008x | 1.00-1.04 | 1.010 | 5 |   noise |
| split() char, 65536 B string_view::find loop                               | 93245.8 | 92165.2 |     1.012x | 0.94-1.07 | 1.002 | 5 |   noise |
| split() char, keep blanks, 65536 B memchr loop                             | 61766.9 | 64489.2 |     0.962x | 0.89-1.07 | 1.001 | 5 |  slower |
| iterator Split<string_view>, 65536 B memchr loop, no vector                | 56370.8 | 56895.2 |     0.991x | 0.88-1.01 | 1.022 | 5 |   noise |
| iterator Split<string> (copies the source), 65536 B memchr loop, no vector | 57990.4 | 56413.8 |     1.021x | 0.98-1.04 | 1.041 | 5 |   noise |
| split() "::", 65536 B string_view::find loop                               | 85009.8 | 85335.7 |     0.996x | 0.95-1.03 | 0.995 | 5 |   noise |
| split() first_of ",;", 65536 B find_first_of loop                          |  153857 |  151310 |     0.990x | 0.94-1.15 | 0.995 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.007 over 21 rows (min 0.962 split() char, keep blanks, 65536 B memchr loop; max 1.032 split() char, keep blanks, 1024 B memchr loop)
per-run geomean: min 0.987, median 1.013, max 1.015 over 5 runs
A/A geomean 1.001

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 iterator over 65,536 B with the `memchr` loop 0.946: placement. `split.h` is byte-identical.
