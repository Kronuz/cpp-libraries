# escape: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/escape#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `f4efd99 2026-10-28 04:34:50 -0700 Credit Germán Méndez Bravo and bound Dubalu's years`
- HEAD: `114543f 2026-11-01 07:51:57 -0800 Shape the README to the family standard and drop the one-arrow diagram [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `escape.cc`, `escape.hh`; START links char-classify `306ecd9`, HEAD links char-classify `684a962`
- Bench source: bench/bench.cc (HEAD), with `test/escape_old.cc` (the frozen original)
- Rows dropped because the API is new since START: none
- Metric: column `new ns`; `old ns` (the frozen original) is the anchor
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -I w/escape-{start|head} -I w/char-classify-{p306|p684} w/escape-head/bench/bench.cc w/escape-head/test/escape_old.cc w/escape-{start|head}/escape.cc`
- Raw per-round outputs: `$GATE/raw/escape/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 25 | 2.884 | 2.875-2.953 | 1.002 | 0 | 1.044 printable 1 B |
| Intel i9-9980HK | 25 | 2.432 | 2.262-2.570 | 1.023 | 0 | 1.010 binary 2 B, quote " |

**Verdict: FASTER**; geomean 2.884 / 2.432 (Apple M4 Pro / Intel i9-9980HK).

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: none.
- Intel i9-9980HK: none.

## Notes

- Output is the same at START and HEAD (the repo's differential test against the frozen original). No row is made incomparable by a correctness change.
- START pins char-classify `306ecd9`; HEAD pins `684a962` (shared escaping kernel). Both are what each revision's CMakeLists names.
- Anchor column (`old ns`, the frozen original compiled into both binaries) stays at 1.0 within its spread.

## Apple M4 Pro: per-row results (library column)

| row                     |   START |    HEAD | START/HEAD |       range |   A/A | n | verdict |
| ----------------------- | ------: | ------: | ---------: | ----------: | ----: | : | ------: |
| printable 1 B           |    7.00 |    6.80 |     1.044x |   1.01-1.04 | 1.014 | 5 |   noise |
| printable 8 B           |    29.2 |    8.50 |     3.435x |   3.22-3.73 | 1.025 | 5 |  faster |
| printable 16 B          |    33.0 |    9.90 |     3.300x |   3.28-3.56 | 1.029 | 5 |  faster |
| printable 256 B         |   253.0 |    50.5 |     5.020x |   4.88-6.44 | 0.993 | 5 |  faster |
| printable 4 KB          |  3902.3 |   461.8 |     8.459x |   8.14-9.54 | 0.887 | 5 |  faster |
| printable 64 KB         | 66737.6 |  7501.5 |     8.897x |  8.32-10.01 | 1.004 | 5 |  faster |
| mixed 10% 256 B         |   327.3 |    76.0 |     4.243x |   4.18-4.31 | 1.014 | 5 |  faster |
| mixed 10% 64 KB         |  106504 | 14580.4 |     7.302x |   7.21-7.43 | 1.000 | 5 |  faster |
| ctl 1% 4 KB             |  5923.7 |   530.5 |    11.068x | 11.02-11.23 | 1.005 | 5 |  faster |
| ctl 10% 256 B           |   399.7 |    71.4 |     5.585x |   5.56-5.66 | 0.996 | 5 |  faster |
| ctl 10% 4 KB            |  6386.6 |   952.1 |     6.716x |   6.51-6.81 | 1.000 | 5 |  faster |
| ctl 10% 64 KB           |  110326 | 16929.7 |     6.517x |   6.42-6.67 | 0.994 | 5 |  faster |
| ctl 50% 4 KB            |  6431.7 |  1713.6 |     3.755x |   3.71-3.78 | 0.999 | 5 |  faster |
| binary 4 KB             |  3434.2 |  1761.8 |     1.943x |   1.92-2.00 | 0.886 | 5 |  faster |
| printable 2 B           |    7.10 |    6.20 |     1.145x |   1.10-1.16 | 1.029 | 5 |  faster |
| printable 4 B           |    9.00 |    7.10 |     1.254x |   1.21-1.32 | 1.023 | 5 |  faster |
| printable 7 B           |    29.8 |    8.50 |     3.506x |   3.34-3.59 | 1.036 | 5 |  faster |
| printable 15 B          |    34.6 |    11.4 |     3.089x |   2.92-3.37 | 1.000 | 5 |  faster |
| printable 1 B, no quote |    7.10 |    6.70 |     1.060x |   1.01-1.09 | 1.028 | 5 |   noise |
| printable 4 B, quote "  |    9.00 |    7.40 |     1.216x |   1.16-1.39 | 1.011 | 5 |  faster |
| printable 3 B, quote \1 |    8.80 |    7.60 |     1.147x |   1.10-1.24 | 1.024 | 5 |  faster |
| binary 2 B, quote "     |    7.10 |    6.70 |     1.061x |   1.03-1.07 | 1.000 | 5 |  faster |
| binary 4 B, quote "     |    9.80 |    7.60 |     1.289x |   1.25-1.43 | 1.022 | 5 |  faster |
| binary 16 B, quote "    |    35.7 |    33.1 |     1.095x |   1.04-1.17 | 1.040 | 5 |   noise |
| binary 4096 B, quote "  |  5858.4 |  1730.2 |     3.373x |   3.35-3.53 | 1.001 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 2.884 over 25 rows (min 1.044 printable 1 B; max 11.068 ctl 1% 4 KB)
per-run geomean: min 2.875, median 2.899, max 2.953 over 5 runs
A/A geomean 1.002

### Apple M4 Pro: anchor column (code that is the same in both builds; ratio should be 1)

| row                     |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| printable 1 B           |    6.90 |    6.80 |     1.015x | 0.99-1.06 | 1.030 | 5 |   noise |
| printable 8 B           |    28.6 |    28.1 |     1.018x | 0.97-1.06 | 0.962 | 5 |   noise |
| printable 16 B          |    32.3 |    32.2 |     0.991x | 0.94-1.04 | 1.000 | 5 |   noise |
| printable 256 B         |   274.8 |   306.4 |     0.897x | 0.72-1.27 | 0.821 | 5 |   noise |
| printable 4 KB          |  4098.2 |  4770.6 |     0.883x | 0.66-1.07 | 0.847 | 5 |   noise |
| printable 64 KB         | 74851.9 | 63863.3 |     1.015x | 0.84-1.24 | 1.002 | 5 |   noise |
| mixed 10% 256 B         |   328.2 |   331.0 |     0.986x | 0.97-1.20 | 1.006 | 5 |   noise |
| mixed 10% 64 KB         |  105452 |  105711 |     0.996x | 0.99-1.00 | 1.003 | 5 |   noise |
| ctl 1% 4 KB             |  5869.5 |  5921.5 |     0.996x | 0.98-1.02 | 1.001 | 5 |   noise |
| ctl 10% 256 B           |   398.4 |   402.6 |     0.987x | 0.98-1.01 | 0.990 | 5 |   noise |
| ctl 10% 4 KB            |  6227.5 |  6238.4 |     1.002x | 0.97-1.02 | 0.991 | 5 |   noise |
| ctl 10% 64 KB           |  109177 |  108923 |     1.001x | 0.99-1.01 | 0.999 | 5 |   noise |
| ctl 50% 4 KB            |  6408.3 |  6438.2 |     0.996x | 0.99-1.01 | 1.002 | 5 |   noise |
| binary 4 KB             |  3440.2 |  3446.4 |     0.986x | 0.83-1.01 | 0.985 | 5 |   noise |
| printable 2 B           |    6.70 |    6.70 |     1.000x | 0.94-1.09 | 0.957 | 5 |   noise |
| printable 4 B           |    8.80 |    8.60 |     1.035x | 0.95-1.08 | 1.023 | 5 |   noise |
| printable 7 B           |    28.8 |    28.0 |     1.036x | 0.97-1.08 | 1.036 | 5 |   noise |
| printable 15 B          |    35.1 |    34.8 |     0.989x | 0.89-1.04 | 1.015 | 5 |   noise |
| printable 1 B, no quote |    6.80 |    7.10 |     0.986x | 0.94-1.03 | 1.014 | 5 |   noise |
| printable 4 B, quote "  |    8.70 |    8.60 |     1.012x | 0.87-1.07 | 1.023 | 5 |   noise |
| printable 3 B, quote \1 |    8.60 |    8.70 |     0.989x | 0.93-1.02 | 1.012 | 5 |   noise |
| binary 2 B, quote "     |    6.80 |    6.80 |     1.015x | 0.93-1.06 | 0.986 | 5 |   noise |
| binary 4 B, quote "     |    9.40 |    9.20 |     1.022x | 0.95-1.08 | 1.032 | 5 |   noise |
| binary 16 B, quote "    |    38.1 |    35.7 |     1.095x | 0.91-1.31 | 1.027 | 5 |   noise |
| binary 4096 B, quote "  |  5894.9 |  5846.5 |     1.007x | 0.99-1.01 | 1.001 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.997 over 25 rows (min 0.883 printable 4 KB; max 1.095 binary 16 B, quote ")
per-run geomean: min 0.969, median 0.992, max 1.042 over 5 runs
A/A geomean 0.989

## Intel i9-9980HK: per-row results (library column)

| row                     |   START |    HEAD | START/HEAD |      range |   A/A | n | verdict |
| ----------------------- | ------: | ------: | ---------: | ---------: | ----: | : | ------: |
| printable 1 B           |    17.9 |    16.6 |     1.068x |  0.98-1.10 | 1.016 | 5 |   noise |
| printable 8 B           |    80.6 |    22.9 |     3.405x |  3.08-4.33 | 1.045 | 5 |  faster |
| printable 16 B          |    91.0 |    26.7 |     3.297x |  3.07-4.35 | 1.068 | 5 |  faster |
| printable 256 B         |   591.8 |   180.6 |     3.122x |  2.86-4.15 | 1.026 | 5 |  faster |
| printable 4 KB          |  8869.8 |  1000.8 |     8.671x | 7.91-10.89 | 1.078 | 5 |  faster |
| printable 64 KB         |  140820 | 23893.4 |     5.682x |  5.39-7.42 | 1.114 | 5 |  faster |
| mixed 10% 256 B         |   635.4 |   248.7 |     2.485x |  2.24-2.64 | 1.090 | 5 |  faster |
| mixed 10% 64 KB         |  176010 | 40535.9 |     4.154x |  3.99-4.45 | 1.085 | 5 |  faster |
| ctl 1% 4 KB             |  9139.5 |  1116.4 |     7.948x |  7.25-8.78 | 1.006 | 5 |  faster |
| ctl 10% 256 B           |   684.7 |   262.8 |     2.639x |  2.33-2.78 | 1.012 | 5 |  faster |
| ctl 10% 4 KB            | 10868.7 |  1982.1 |     5.473x |  4.63-5.58 | 0.992 | 5 |  faster |
| ctl 10% 64 KB           |  202803 | 48214.8 |     4.214x |  3.61-4.45 | 1.003 | 5 |  faster |
| ctl 50% 4 KB            | 16888.6 |  3493.2 |     4.904x |  4.34-5.07 | 1.040 | 5 |  faster |
| binary 4 KB             |  9194.2 |  3474.6 |     2.499x |  2.49-2.66 | 1.006 | 5 |  faster |
| printable 2 B           |    17.9 |    17.3 |     1.035x |  1.01-1.15 | 1.006 | 5 |   noise |
| printable 4 B           |    22.2 |    20.0 |     1.125x |  1.09-1.22 | 1.000 | 5 |  faster |
| printable 7 B           |    74.3 |    27.8 |     2.874x |  2.50-3.20 | 0.999 | 5 |  faster |
| printable 15 B          |    87.5 |    35.5 |     2.688x |  2.36-2.79 | 0.995 | 5 |  faster |
| printable 1 B, no quote |    17.2 |    18.4 |     1.011x |  0.89-1.05 | 1.030 | 5 |   noise |
| printable 4 B, quote "  |    22.2 |    21.6 |     1.094x |  0.95-1.12 | 0.980 | 5 |   noise |
| printable 3 B, quote \1 |    21.1 |    20.8 |     1.093x |  1.00-1.11 | 0.977 | 5 |   noise |
| binary 2 B, quote "     |    18.0 |    18.2 |     1.010x |  0.97-1.03 | 0.989 | 5 |   noise |
| binary 4 B, quote "     |    22.1 |    19.9 |     1.118x |  1.06-1.27 | 1.004 | 5 |   noise |
| binary 16 B, quote "    |    87.1 |    85.1 |     1.028x |  0.98-1.15 | 0.991 | 5 |   noise |
| binary 4096 B, quote "  |  9968.1 |  3300.6 |     3.136x |  3.00-3.75 | 1.026 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 2.432 over 25 rows (min 1.010 binary 2 B, quote "; max 8.671 printable 4 KB)
per-run geomean: min 2.262, median 2.445, max 2.570 over 5 runs
A/A geomean 1.023

### Intel i9-9980HK: anchor column (code that is the same in both builds; ratio should be 1)

| row                     |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| printable 1 B           |    17.9 |    16.3 |     1.082x | 1.01-1.10 | 1.000 | 5 |   noise |
| printable 8 B           |    80.2 |    71.9 |     1.062x | 1.02-1.38 | 1.068 | 5 |   noise |
| printable 16 B          |    90.8 |    83.5 |     1.026x | 0.96-1.39 | 1.076 | 5 |   noise |
| printable 256 B         |   595.6 |   546.6 |     1.044x | 0.98-1.38 | 1.085 | 5 |   noise |
| printable 4 KB          |  8882.8 |  8156.5 |     1.042x | 1.00-1.34 | 1.070 | 5 |   noise |
| printable 64 KB         |  141481 |  128176 |     1.100x | 1.00-1.35 | 1.129 | 5 |   noise |
| mixed 10% 256 B         |   630.5 |   574.8 |     1.042x | 0.99-1.18 | 1.048 | 5 |   noise |
| mixed 10% 64 KB         |  174006 |  159289 |     1.065x | 0.99-1.10 | 1.091 | 5 |   noise |
| ctl 1% 4 KB             |  9170.1 |  8359.3 |     1.082x | 1.00-1.12 | 1.013 | 5 |   noise |
| ctl 10% 256 B           |   667.9 |   662.7 |     1.000x | 0.95-1.03 | 0.999 | 5 |   noise |
| ctl 10% 4 KB            | 10815.2 | 10807.0 |     0.986x | 0.88-1.03 | 1.004 | 5 |   noise |
| ctl 10% 64 KB           |  200730 |  200512 |     0.996x | 0.86-1.05 | 1.004 | 5 |   noise |
| ctl 50% 4 KB            | 17039.5 | 17580.2 |     0.971x | 0.87-1.04 | 1.033 | 5 |   noise |
| binary 4 KB             |  9216.0 |  9113.9 |     0.987x | 0.95-1.02 | 1.002 | 5 |   noise |
| printable 2 B           |    18.9 |    18.4 |     1.023x | 0.99-1.06 | 1.011 | 5 |   noise |
| printable 4 B           |    22.6 |    22.6 |     1.012x | 0.96-1.10 | 1.012 | 5 |   noise |
| printable 7 B           |    73.1 |    76.9 |     0.989x | 0.89-1.09 | 1.001 | 5 |   noise |
| printable 15 B          |    92.7 |    95.8 |     1.000x | 0.87-1.07 | 1.011 | 5 |   noise |
| printable 1 B, no quote |    18.2 |    18.1 |     1.005x | 0.88-1.08 | 1.028 | 5 |   noise |
| printable 4 B, quote "  |    22.0 |    24.3 |     0.922x | 0.89-1.02 | 0.957 | 5 |   noise |
| printable 3 B, quote \1 |    21.2 |    22.8 |     0.992x | 0.92-1.00 | 0.976 | 5 |   noise |
| binary 2 B, quote "     |    17.7 |    18.3 |     0.995x | 0.97-1.02 | 0.977 | 5 |   noise |
| binary 4 B, quote "     |    22.3 |    22.1 |     1.025x | 0.97-1.17 | 1.004 | 5 |   noise |
| binary 16 B, quote "    |    87.8 |    86.5 |     1.002x | 0.98-1.14 | 1.004 | 5 |   noise |
| binary 4096 B, quote "  |  9819.8 | 10191.3 |     1.001x | 0.93-1.20 | 0.988 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.017 over 25 rows (min 0.922 printable 4 B, quote "; max 1.100 printable 64 KB)
per-run geomean: min 0.958, median 1.028, max 1.083 over 5 runs
A/A geomean 1.023
