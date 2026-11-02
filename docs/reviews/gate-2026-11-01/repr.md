# repr: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/repr#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `2063945 2026-10-28 04:47:21 -0700 Credit Germán Méndez Bravo and bound Dubalu's years`
- HEAD: `d10d763 2026-11-01 07:50:43 -0800 Shape the README to the family standard and drop the one-arrow diagram [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `repr.cc`, `repr.hh`; START links char-classify `306ecd9` (its pin at START), HEAD links char-classify `684a962` (its pin at HEAD)
- Bench source: bench/bench.cc (HEAD), with `test/repr_old.cc` (the frozen original)
- Rows dropped because the API is new since START: none
- Metric: column `new ns` (the library); `old ns` (the frozen original, identical code in both builds) is the anchor
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -I w/repr-{start|head} -I w/char-classify-{p306|p684} w/repr-head/bench/bench.cc w/repr-head/test/repr_old.cc w/repr-{start|head}/repr.cc`
- Raw per-round outputs: `$GATE/raw/repr/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 27 | 4.399 | 4.334-4.489 | 0.959 | 0 | 1.001 friendly=false 4096 B |
| Intel i9-9980HK | 27 | 3.854 | 3.636-3.984 | 0.975 | 0 | 1.000 printable 1 B |

**Verdict: FASTER**; geomean 4.399 / 3.854 (Apple M4 Pro / Intel i9-9980HK).

Geomean without the rows that are not comparable or are algorithmic changes (`max_size=64 on (4|64) KB`): Apple M4 Pro 3.189; Intel i9-9980HK 2.808. HEAD locates the kept head and tail by arithmetic and never visits the elided middle, where START walks all of it (the cost no longer depends on input size), so those two rows measure an algorithm, not a kernel.

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: none.
- Intel i9-9980HK: none.

## Notes

- Output is the same at START and HEAD (the repo's differential test against the frozen original). No row is made incomparable by a correctness change.
- Dependencies differ by design: START pins char-classify `306ecd9` and uses `chars.hh` only; HEAD pins `684a962` and uses the shared escaping kernel (`chars_escape.hh`). Both are what each revision's CMakeLists names.
- The two `max_size=64` rows on 4 KB and 64 KB (51x to 1000x) are an algorithmic change (the elided middle is no longer visited), not a per-byte speedup; the geomean line above is also given without them.
- Anchor column (`old ns`, the frozen original compiled into both binaries) stays at 1.0 within its spread, so the two builds are comparable.
- `friendly=false` 16 B and 4 KB are flat on the M4 (1.00x) and faster on the i9 (1.11x noise, 1.57x at 4 KB).

## Apple M4 Pro: per-row results (library column)

| row                      |   START |    HEAD | START/HEAD |          range |   A/A | n | verdict |
| ------------------------ | ------: | ------: | ---------: | -------------: | ----: | : | ------: |
| printable 1 B            |    7.70 |    6.60 |     1.152x |      1.12-1.25 | 0.951 | 5 |  faster |
| printable 4 B            |    10.3 |    7.20 |     1.417x |      1.28-1.45 | 0.880 | 5 |  faster |
| printable 7 B            |    29.4 |    8.70 |     3.400x |      3.28-3.57 | 0.923 | 5 |  faster |
| printable 8 B            |    28.4 |    10.4 |     2.731x |      2.54-3.05 | 0.897 | 5 |  faster |
| printable 15 B           |    35.8 |    13.9 |     2.613x |      2.42-2.76 | 0.923 | 5 |  faster |
| printable 16 B           |    33.0 |    12.4 |     2.718x |      2.54-3.03 | 0.868 | 5 |  faster |
| printable 256 B          |   311.5 |    53.0 |     5.802x |      5.69-6.24 | 0.924 | 5 |  faster |
| printable 4 KB           |  4759.0 |   467.8 |    10.171x |     9.89-12.19 | 0.992 | 5 |  faster |
| printable 64 KB          | 75330.7 |  7804.6 |     9.678x |     9.38-10.88 | 0.832 | 5 |  faster |
| mixed 10% 256 B          |   381.5 |    77.3 |     4.959x |      4.93-5.02 | 0.979 | 5 |  faster |
| mixed 10% 64 KB          |  108595 | 13283.5 |     8.199x |      8.13-8.73 | 1.008 | 5 |  faster |
| ctl 1% 4 KB              |  5916.6 |   515.5 |    11.485x |    11.33-11.62 | 0.994 | 5 |  faster |
| ctl 10% 256 B            |   404.4 |    73.3 |     5.431x |      5.39-5.74 | 0.996 | 5 |  faster |
| ctl 10% 4 KB             |  6394.6 |   866.7 |     7.406x |      7.26-7.49 | 0.998 | 5 |  faster |
| ctl 10% 64 KB            |  113308 | 15343.8 |     7.348x |      7.20-7.78 | 0.992 | 5 |  faster |
| ctl 50% 4 KB             |  6899.4 |  1698.8 |     4.070x |      4.02-4.17 | 0.989 | 5 |  faster |
| binary 4 KB              |  3691.0 |  1769.7 |     2.119x |      1.85-2.49 | 0.988 | 5 |  faster |
| max_size=64 on 4 B       |    23.5 |    7.60 |     3.078x |      2.88-3.23 | 0.919 | 5 |  faster |
| max_size=64 on 4 KB      |  2177.4 |    36.2 |    60.149x |    58.72-61.84 | 0.991 | 5 |  faster |
| max_size=64 on 64 KB     | 33555.7 |    33.5 |   998.874x | 984.44-1023.19 | 0.996 | 5 |  faster |
| printable 1 B, no quote  |    7.90 |    6.70 |     1.179x |      1.13-1.26 | 0.963 | 5 |  faster |
| printable 4 B, no quote  |    10.0 |    7.00 |     1.444x |      1.33-1.51 | 0.980 | 5 |  faster |
| printable 8 B, no quote  |    29.5 |    10.4 |     2.825x |      2.74-3.10 | 0.976 | 5 |  faster |
| printable 16 B, no quote |    36.7 |    11.9 |     3.041x |      2.71-3.27 | 1.000 | 5 |  faster |
| friendly=false 1 B       |    7.10 |    6.00 |     1.183x |      1.16-1.22 | 0.973 | 5 |  faster |
| friendly=false 16 B      |    25.9 |    25.1 |     1.004x |      0.96-1.16 | 0.992 | 5 |   noise |
| friendly=false 4096 B    |  1355.3 |  1346.3 |     1.001x |      0.99-1.03 | 1.008 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 4.399 over 27 rows (min 1.001 friendly=false 4096 B; max 998.874 max_size=64 on 64 KB)
per-run geomean: min 4.334, median 4.432, max 4.489 over 5 runs
A/A geomean 0.959

### Apple M4 Pro: anchor column (code that is the same in both builds; ratio should be 1)

| row                      |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------ | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| printable 1 B            |    7.90 |    7.70 |     1.038x | 0.99-1.06 | 0.988 | 5 |   noise |
| printable 4 B            |    11.8 |    11.9 |     1.000x | 0.87-1.06 | 0.983 | 5 |   noise |
| printable 7 B            |    30.6 |    31.1 |     0.990x | 0.95-1.06 | 0.987 | 5 |   noise |
| printable 8 B            |    30.2 |    29.9 |     1.010x | 0.97-1.13 | 0.961 | 5 |   noise |
| printable 15 B           |    39.7 |    38.2 |     1.039x | 0.90-1.19 | 0.966 | 5 |   noise |
| printable 16 B           |    35.9 |    36.0 |     0.947x | 0.81-1.11 | 0.907 | 5 |   noise |
| printable 256 B          |   324.8 |   327.4 |     1.029x | 0.79-1.19 | 0.911 | 5 |   noise |
| printable 4 KB           |  5051.7 |  4869.8 |     1.025x | 0.98-1.05 | 0.997 | 5 |   noise |
| printable 64 KB          | 83370.9 | 86831.5 |     0.903x | 0.86-1.21 | 0.971 | 5 |   noise |
| mixed 10% 256 B          |   389.4 |   393.7 |     0.973x | 0.96-1.04 | 0.925 | 5 |   noise |
| mixed 10% 64 KB          |  109226 |  109953 |     0.994x | 0.94-1.00 | 0.987 | 5 |   noise |
| ctl 1% 4 KB              |  5999.1 |  6254.5 |     0.959x | 0.87-1.02 | 0.881 | 5 |   noise |
| ctl 10% 256 B            |   414.5 |   413.9 |     0.997x | 0.85-1.02 | 0.948 | 5 |   noise |
| ctl 10% 4 KB             |  6515.4 |  6495.1 |     0.993x | 0.96-1.00 | 0.993 | 5 |   noise |
| ctl 10% 64 KB            |  113428 |  114159 |     0.988x | 0.89-1.04 | 0.969 | 5 |   noise |
| ctl 50% 4 KB             |  6954.7 |  6929.7 |     1.004x | 0.93-1.01 | 0.980 | 5 |   noise |
| binary 4 KB              |  4421.5 |  3655.1 |     1.157x | 0.95-1.26 | 1.029 | 5 |   noise |
| max_size=64 on 4 B       |    24.3 |    23.9 |     1.017x | 1.00-1.03 | 0.976 | 5 |   noise |
| max_size=64 on 4 KB      |  2168.1 |  2178.5 |     0.995x | 0.98-1.02 | 0.991 | 5 |   noise |
| max_size=64 on 64 KB     | 33527.1 | 33411.6 |     0.998x | 0.99-1.02 | 0.999 | 5 |   noise |
| printable 1 B, no quote  |    8.10 |    7.80 |     1.025x | 0.93-1.07 | 0.975 | 5 |   noise |
| printable 4 B, no quote  |    9.70 |    10.2 |     0.941x | 0.90-1.00 | 0.933 | 5 |   noise |
| printable 8 B, no quote  |    30.7 |    29.0 |     1.077x | 0.89-1.11 | 1.081 | 5 |   noise |
| printable 16 B, no quote |    37.0 |    35.2 |     1.054x | 0.84-1.09 | 1.023 | 5 |   noise |
| friendly=false 1 B       |    7.10 |    7.10 |     0.986x | 0.97-1.01 | 0.973 | 5 |   noise |
| friendly=false 16 B      |    25.6 |    25.0 |     1.044x | 0.92-1.05 | 1.016 | 5 |   noise |
| friendly=false 4096 B    |  1346.7 |  1357.1 |     0.981x | 0.98-1.05 | 1.007 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.005 over 27 rows (min 0.903 printable 64 KB; max 1.157 binary 4 KB)
per-run geomean: min 0.951, median 1.005, max 1.034 over 5 runs
A/A geomean 0.975

## Intel i9-9980HK: per-row results (library column)

| row                      |   START |    HEAD | START/HEAD |         range |   A/A | n | verdict |
| ------------------------ | ------: | ------: | ---------: | ------------: | ----: | : | ------: |
| printable 1 B            |    20.1 |    20.0 |     1.000x |     0.96-1.18 | 1.026 | 5 |   noise |
| printable 4 B            |    26.8 |    22.3 |     1.219x |     1.16-1.36 | 1.008 | 5 |  faster |
| printable 7 B            |    84.9 |    31.7 |     2.955x |     2.65-3.23 | 0.999 | 5 |  faster |
| printable 8 B            |    86.9 |    31.1 |     2.871x |     2.26-3.17 | 1.008 | 5 |  faster |
| printable 15 B           |   107.4 |    41.1 |     2.588x |     2.13-2.67 | 0.986 | 5 |  faster |
| printable 16 B           |   101.1 |    35.6 |     2.658x |     2.32-3.54 | 0.985 | 5 |  faster |
| printable 256 B          |   732.9 |   211.7 |     3.203x |     2.98-4.29 | 0.959 | 5 |  faster |
| printable 4 KB           | 10171.1 |  1106.3 |     9.141x |    8.47-10.13 | 0.878 | 5 |  faster |
| printable 64 KB          |  176335 | 27123.1 |     6.586x |     5.81-7.55 | 0.934 | 5 |  faster |
| mixed 10% 256 B          |   773.8 |   275.9 |     2.761x |     2.49-2.87 | 0.852 | 5 |  faster |
| mixed 10% 64 KB          |  208714 | 44589.8 |     4.694x |     4.19-5.56 | 0.897 | 5 |  faster |
| ctl 1% 4 KB              | 11331.7 |  1225.0 |     9.240x |    8.03-11.58 | 0.989 | 5 |  faster |
| ctl 10% 256 B            |   821.7 |   299.9 |     2.751x |     2.47-2.91 | 0.970 | 5 |  faster |
| ctl 10% 4 KB             | 13193.9 |  2024.5 |     6.412x |     5.40-7.23 | 0.979 | 5 |  faster |
| ctl 10% 64 KB            |  231374 | 49187.6 |     4.753x |     4.14-5.24 | 0.996 | 5 |  faster |
| ctl 50% 4 KB             | 18546.6 |  3493.9 |     5.478x |     4.40-5.96 | 0.997 | 5 |  faster |
| binary 4 KB              | 10639.3 |  3603.2 |     2.981x |     2.38-3.27 | 1.025 | 5 |  faster |
| max_size=64 on 4 B       |    78.6 |    24.7 |     3.229x |     3.16-3.53 | 1.018 | 5 |  faster |
| max_size=64 on 4 KB      |  6887.5 |   133.9 |    51.208x |   46.88-57.67 | 0.983 | 5 |  faster |
| max_size=64 on 64 KB     | 96677.6 |   122.9 |   791.142x | 768.09-894.27 | 0.937 | 5 |  faster |
| printable 1 B, no quote  |    21.0 |    19.7 |     1.055x |     0.96-1.10 | 0.981 | 5 |   noise |
| printable 4 B, no quote  |    28.0 |    21.9 |     1.284x |     1.14-1.51 | 0.959 | 5 |  faster |
| printable 8 B, no quote  |    85.9 |    30.0 |     2.835x |     2.55-3.23 | 0.994 | 5 |  faster |
| printable 16 B, no quote |   105.4 |    33.6 |     3.128x |     2.75-3.49 | 0.971 | 5 |  faster |
| friendly=false 1 B       |    19.6 |    18.4 |     1.065x |     0.96-1.29 | 1.008 | 5 |   noise |
| friendly=false 16 B      |    86.1 |    76.6 |     1.113x |     1.09-1.13 | 1.020 | 5 |   noise |
| friendly=false 4096 B    |  4205.9 |  2673.9 |     1.573x |     1.31-1.61 | 0.981 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 3.854 over 27 rows (min 1.000 printable 1 B; max 791.142 max_size=64 on 64 KB)
per-run geomean: min 3.636, median 3.854, max 3.984 over 5 runs
A/A geomean 0.975

### Intel i9-9980HK: anchor column (code that is the same in both builds; ratio should be 1)

| row                      |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------ | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| printable 1 B            |    21.2 |    20.8 |     1.019x | 0.95-1.21 | 1.039 | 5 |   noise |
| printable 4 B            |    27.1 |    27.2 |     1.007x | 0.99-1.14 | 1.004 | 5 |   noise |
| printable 7 B            |    83.5 |    83.9 |     1.101x | 0.99-1.12 | 1.001 | 5 |   noise |
| printable 8 B            |    86.7 |    86.9 |     1.017x | 0.81-1.12 | 1.014 | 5 |   noise |
| printable 15 B           |    96.0 |    96.9 |     0.992x | 0.80-1.02 | 0.992 | 5 |   noise |
| printable 16 B           |    94.3 |    96.7 |     0.883x | 0.72-1.17 | 1.009 | 5 |   noise |
| printable 256 B          |   658.8 |   722.9 |     0.892x | 0.82-1.17 | 0.894 | 5 |   noise |
| printable 4 KB           |  9674.8 | 10739.8 |     0.889x | 0.79-0.99 | 0.895 | 5 |   noise |
| printable 64 KB          |  160988 |  160561 |     1.062x | 0.85-1.12 | 0.920 | 5 |   noise |
| mixed 10% 256 B          |   685.4 |   701.0 |     0.982x | 0.89-1.13 | 0.880 | 5 |   noise |
| mixed 10% 64 KB          |  171652 |  167014 |     1.035x | 0.93-1.23 | 0.915 | 5 |   noise |
| ctl 1% 4 KB              | 10942.8 | 10781.3 |     0.991x | 0.90-1.19 | 1.032 | 5 |   noise |
| ctl 10% 256 B            |   742.3 |   719.6 |     1.022x | 0.93-1.10 | 1.040 | 5 |   noise |
| ctl 10% 4 KB             | 11948.2 | 11613.1 |     1.034x | 0.82-1.11 | 0.976 | 5 |   noise |
| ctl 10% 64 KB            |  183171 |  184184 |     0.989x | 0.90-1.10 | 0.988 | 5 |   noise |
| ctl 50% 4 KB             | 15933.2 | 15734.2 |     1.034x | 0.84-1.11 | 1.000 | 5 |   noise |
| binary 4 KB              |  8341.2 |  8150.2 |     1.032x | 0.83-1.14 | 1.000 | 5 |   noise |
| max_size=64 on 4 B       |    78.0 |    78.3 |     0.998x | 0.99-1.10 | 1.010 | 5 |   noise |
| max_size=64 on 4 KB      |  3571.6 |  3593.9 |     0.993x | 0.89-1.11 | 0.990 | 5 |   noise |
| max_size=64 on 64 KB     | 48786.0 | 54019.4 |     0.905x | 0.90-1.00 | 0.926 | 5 |   noise |
| printable 1 B, no quote  |    21.0 |    21.4 |     0.968x | 0.90-1.02 | 0.986 | 5 |   noise |
| printable 4 B, no quote  |    28.1 |    28.2 |     0.986x | 0.87-1.11 | 0.972 | 5 |   noise |
| printable 8 B, no quote  |    85.2 |    85.9 |     0.977x | 0.91-1.18 | 0.992 | 5 |   noise |
| printable 16 B, no quote |   105.3 |   103.4 |     1.015x | 0.90-1.17 | 1.004 | 5 |   noise |
| friendly=false 1 B       |    19.3 |    19.5 |     1.005x | 0.91-1.18 | 1.000 | 5 |   noise |
| friendly=false 16 B      |    86.2 |    84.9 |     1.011x | 1.00-1.04 | 1.016 | 5 |   noise |
| friendly=false 4096 B    |  4206.4 |  4312.4 |     0.974x | 0.87-1.00 | 0.974 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.992 over 27 rows (min 0.883 printable 16 B; max 1.101 printable 7 B)
per-run geomean: min 0.932, median 0.993, max 1.028 over 5 runs
A/A geomean 0.979
