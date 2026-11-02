# term-color: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/term-color#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `032ef09 2026-10-28 05:00:07 -0700 Credit only Germán Méndez Bravo in the 2026 collapse.hh`
- HEAD: `af77283 2026-11-01 04:02:54 -0800 Shorten the README's first sentence to the repository description [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `collapse.hh`, `color_tools.hh`, `ansi_color.hh`, `colors.h`; static-string `eb1efcb` on both
- Bench source: bench/bench.cc (HEAD), derived copy `bench_gate.cc` without the `apply(resolved) auto` row (it calls `term_color::resolve()`, new after START); frozen originals `test/collapse_old.hh`, `test/color_tools_old.hh`
- Rows dropped because the API is new since START: `log line apply(resolved) auto` (new API `resolve()`)
- Metric: column `new` (the library); `old` (the frozen original) is the anchor
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -I w/term-color-{start|head} -I w/static-string-peb1 w/term-color-head/bench/bench_gate.cc`
- Raw per-round outputs: `$GATE/raw/term-color/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 27 | 6.104 | 5.914-6.170 | 0.996 | 0 | 1.781 log line apply auto+auto |
| Intel i9-9980HK | 27 | 4.589 | 4.509-4.662 | 0.993 | 0 | 1.512 log line apply never (strip) |

**Verdict: FASTER**; geomean 6.104 / 4.589 (Apple M4 Pro / Intel i9-9980HK).

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: none.
- Intel i9-9980HK: none.

## Notes

- START's `collapse()` appended plain text a byte at a time and walked each run of escapes twice; HEAD writes into one buffer sized to the input, scans eight bytes at a time and writes `color::ansi()` digit by digit (CHANGELOG 2026-10-31). Output is identical (the repo's differential test against the frozen copies).
- `term_color::resolve()` / `policy::apply()` are new since START, so the bench row `apply(resolved) auto` is dropped from the gate copy; `apply()` itself exists at START and is measured.
- The `old` column (frozen `test/collapse_old.hh`, `test/color_tools_old.hh`) is the anchor; the CHANGELOG records 0.0% to 3.6% run-to-run (8.2% on one 64K row) for it.

## Apple M4 Pro: per-row results (library column)

| row                          |   START |    HEAD | START/HEAD |         range |   A/A | n | verdict |
| ---------------------------- | ------: | ------: | ---------: | ------------: | ----: | : | ------: |
| plain collapse none          |   318.0 |    35.8 |     9.127x |     8.83-9.33 | 0.993 | 5 |  faster |
| plain collapse ansi16        |   307.9 |    35.0 |     8.826x |     7.99-9.14 | 0.998 | 5 |  faster |
| plain collapse ansi256       |   305.3 |    34.5 |     8.771x |     7.82-9.09 | 0.991 | 5 |  faster |
| plain collapse truecolor     |   299.0 |    35.8 |     8.411x |     7.79-8.91 | 1.008 | 5 |  faster |
| log line collapse none       |   320.0 |   134.8 |     2.382x |     2.34-2.43 | 0.990 | 5 |  faster |
| log line collapse ansi16     |   510.3 |   186.2 |     2.741x |     2.54-2.92 | 1.009 | 5 |  faster |
| log line collapse ansi256    |   504.1 |   176.3 |     2.899x |     2.62-3.01 | 1.005 | 5 |  faster |
| log line collapse truecolor  |   509.0 |   178.9 |     2.828x |     2.63-3.01 | 1.036 | 5 |  faster |
| colorful collapse none       |   836.9 |   453.8 |     1.811x |     1.80-1.84 | 0.996 | 5 |  faster |
| colorful collapse ansi16     |  1472.7 |   681.8 |     2.128x |     2.05-2.20 | 0.996 | 5 |  faster |
| colorful collapse ansi256    |  1417.3 |   664.1 |     2.134x |     2.06-2.26 | 0.986 | 5 |  faster |
| colorful collapse truecolor  |  1453.8 |   676.8 |     2.137x |     2.06-2.19 | 0.982 | 5 |  faster |
| 64K plain collapse none      |  255562 |  2062.5 |   123.909x | 117.80-129.84 | 0.981 | 5 |  faster |
| 64K plain collapse ansi16    |  253479 |  2052.0 |   124.382x | 122.95-127.66 | 0.992 | 5 |  faster |
| 64K plain collapse ansi256   |  254625 |  2031.2 |   125.029x | 120.59-127.63 | 1.005 | 5 |  faster |
| 64K plain collapse truecolor |  253792 |  2062.5 |   124.904x | 120.61-127.98 | 0.999 | 5 |  faster |
| 64K color collapse none      | 62843.8 | 12041.8 |     5.324x |     5.09-5.41 | 1.004 | 5 |  faster |
| 64K color collapse ansi16    | 80687.5 | 16927.2 |     4.726x |     4.61-5.01 | 0.978 | 5 |  faster |
| 64K color collapse ansi256   | 80177.0 | 15500.0 |     5.133x |     5.06-5.40 | 0.998 | 5 |  faster |
| 64K color collapse truecolor | 79322.8 | 19510.2 |     4.093x |     3.72-4.39 | 0.979 | 5 |  faster |
| log line apply always+auto   |   636.7 |   310.2 |     2.055x |     1.96-2.08 | 1.002 | 5 |  faster |
| log line apply auto+auto     |   728.5 |   412.1 |     1.781x |     1.71-1.80 | 1.004 | 5 |  faster |
| log line apply always+256    |   495.3 |   173.7 |     2.947x |     2.69-3.05 | 1.004 | 5 |  faster |
| log line apply never (strip) |   292.3 |   132.2 |     2.201x |     2.06-2.32 | 1.007 | 5 |  faster |
| plain apply never (strip)    |   210.6 |    36.3 |     5.819x |     5.64-5.90 | 0.978 | 5 |  faster |
| runtime color::ansi          |   203.3 |    37.1 |     5.521x |     5.38-5.85 | 0.993 | 5 |  faster |
| runtime name_color().ansi    |   282.2 |    95.1 |     2.992x |     2.56-3.02 | 0.984 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 6.104 over 27 rows (min 1.781 log line apply auto+auto; max 125.029 64K plain collapse ansi256)
per-run geomean: min 5.914, median 6.122, max 6.170 over 5 runs
A/A geomean 0.996

### Apple M4 Pro: anchor column (code that is the same in both builds; ratio should be 1)

| row                          |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ---------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| plain collapse none          |   320.6 |   323.9 |     1.003x | 0.96-1.02 | 1.011 | 5 |   noise |
| plain collapse ansi16        |   304.8 |   305.3 |     0.989x | 0.97-1.02 | 0.983 | 5 |   noise |
| plain collapse ansi256       |   307.1 |   305.0 |     0.996x | 0.97-1.01 | 1.003 | 5 |   noise |
| plain collapse truecolor     |   305.0 |   304.5 |     0.995x | 0.96-1.04 | 1.013 | 5 |   noise |
| log line collapse none       |   320.0 |   321.3 |     0.994x | 0.96-1.01 | 0.994 | 5 |   noise |
| log line collapse ansi16     |   508.8 |   512.7 |     0.992x | 0.95-1.00 | 0.997 | 5 |   noise |
| log line collapse ansi256    |   504.4 |   496.7 |     1.016x | 0.97-1.03 | 0.990 | 5 |   noise |
| log line collapse truecolor  |   509.8 |   507.3 |     1.012x | 0.98-1.08 | 1.036 | 5 |   noise |
| colorful collapse none       |   841.1 |   828.4 |     1.017x | 0.97-1.04 | 0.998 | 5 |   noise |
| colorful collapse ansi16     |  1437.2 |  1455.7 |     0.984x | 0.93-1.03 | 0.982 | 5 |   noise |
| colorful collapse ansi256    |  1417.0 |  1417.2 |     1.003x | 0.94-1.07 | 0.985 | 5 |   noise |
| colorful collapse truecolor  |  1453.9 |  1427.2 |     1.008x | 0.96-1.04 | 0.994 | 5 |   noise |
| 64K plain collapse none      |  256000 |  270667 |     0.945x | 0.92-0.98 | 0.955 | 5 |   noise |
| 64K plain collapse ansi16    |  257177 |  250469 |     1.007x | 0.98-1.08 | 0.993 | 5 |   noise |
| 64K plain collapse ansi256   |  253302 |  255198 |     0.993x | 0.98-1.03 | 0.990 | 5 |   noise |
| 64K plain collapse truecolor |  256583 |  257386 |     1.002x | 0.97-1.03 | 1.000 | 5 |   noise |
| 64K color collapse none      | 63958.5 | 64250.0 |     1.018x | 0.96-1.02 | 1.022 | 5 |   noise |
| 64K color collapse ansi16    | 80562.5 | 81948.0 |     0.978x | 0.96-1.01 | 0.981 | 5 |   noise |
| 64K color collapse ansi256   | 80812.5 | 80468.8 |     1.007x | 0.96-1.05 | 0.997 | 5 |   noise |
| 64K color collapse truecolor | 79979.0 | 82416.5 |     0.977x | 0.96-1.03 | 0.985 | 5 |   noise |
| log line apply always+auto   |   633.6 |   639.3 |     0.992x | 0.93-1.02 | 0.988 | 5 |   noise |
| log line apply auto+auto     |   728.8 |   743.8 |     0.997x | 0.96-1.05 | 1.015 | 5 |   noise |
| log line apply always+256    |   497.4 |   511.1 |     0.981x | 0.97-1.00 | 1.004 | 5 |   noise |
| log line apply never (strip) |   292.3 |   285.3 |     1.025x | 0.96-1.03 | 0.996 | 5 |   noise |
| plain apply never (strip)    |   209.5 |   205.6 |     1.024x | 1.00-1.06 | 0.970 | 5 |   noise |
| runtime color::ansi          |   204.1 |   200.7 |     1.020x | 0.97-1.05 | 0.984 | 5 |   noise |
| runtime name_color().ansi    |   281.1 |   278.3 |     1.005x | 0.98-1.04 | 0.982 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.999 over 27 rows (min 0.945 64K plain collapse none; max 1.025 log line apply never (strip))
per-run geomean: min 0.972, median 0.998, max 1.011 over 5 runs
A/A geomean 0.994

## Intel i9-9980HK: per-row results (library column)

| row                          |  START |    HEAD | START/HEAD |       range |   A/A | n | verdict |
| ---------------------------- | -----: | ------: | ---------: | ----------: | ----: | : | ------: |
| plain collapse none          |  376.2 |    75.4 |     5.229x |   4.71-5.77 | 1.001 | 5 |  faster |
| plain collapse ansi16        |  376.4 |    75.3 |     5.380x |   4.71-5.71 | 1.051 | 5 |  faster |
| plain collapse ansi256       |  372.0 |    72.9 |     5.333x |   5.08-5.62 | 1.000 | 5 |  faster |
| plain collapse truecolor     |  372.1 |    71.3 |     5.360x |   5.05-5.63 | 1.001 | 5 |  faster |
| log line collapse none       |  650.1 |   308.4 |     2.128x |   1.76-2.41 | 1.002 | 5 |  faster |
| log line collapse ansi16     | 1026.6 |   445.6 |     2.314x |   2.18-2.51 | 0.997 | 5 |  faster |
| log line collapse ansi256    | 1014.8 |   438.7 |     2.215x |   2.21-2.51 | 1.004 | 5 |  faster |
| log line collapse truecolor  | 1021.7 |   446.6 |     2.297x |   2.17-2.50 | 1.001 | 5 |  faster |
| colorful collapse none       | 1622.9 |   964.7 |     1.682x |   1.60-1.91 | 0.999 | 5 |  faster |
| colorful collapse ansi16     | 2700.7 |  1531.0 |     1.812x |   1.63-1.91 | 1.000 | 5 |  faster |
| colorful collapse ansi256    | 2731.4 |  1459.3 |     1.816x |   1.79-1.91 | 0.998 | 5 |  faster |
| colorful collapse truecolor  | 2679.1 |  1479.6 |     1.808x |   1.80-1.90 | 1.002 | 5 |  faster |
| 64K plain collapse none      | 180109 |  3014.8 |    59.686x | 58.44-61.43 | 1.000 | 5 |  faster |
| 64K plain collapse ansi16    | 180180 |  3008.8 |    59.790x | 59.04-61.43 | 0.996 | 5 |  faster |
| 64K plain collapse ansi256   | 180572 |  3061.8 |    60.636x | 58.83-61.02 | 0.999 | 5 |  faster |
| 64K plain collapse truecolor | 180448 |  2991.0 |    60.219x | 59.03-60.93 | 1.002 | 5 |  faster |
| 64K color collapse none      | 112677 | 22385.8 |     5.034x |   4.82-5.06 | 0.999 | 5 |  faster |
| 64K color collapse ansi16    | 144942 | 35277.0 |     4.102x |   3.93-4.13 | 1.000 | 5 |  faster |
| 64K color collapse ansi256   | 143397 | 34963.0 |     4.098x |   3.90-4.12 | 0.955 | 5 |  faster |
| 64K color collapse truecolor | 143989 | 35386.0 |     4.041x |   3.91-4.09 | 0.957 | 5 |  faster |
| log line apply always+auto   | 1072.1 |   530.4 |     2.009x |   1.95-2.02 | 0.972 | 5 |  faster |
| log line apply auto+auto     | 1139.0 |   596.7 |     1.898x |   1.85-1.93 | 0.993 | 5 |  faster |
| log line apply always+256    |  971.0 |   441.9 |     2.201x |   2.09-2.22 | 0.957 | 5 |  faster |
| log line apply never (strip) |  463.6 |   306.7 |     1.512x |   1.42-1.67 | 0.962 | 5 |  faster |
| plain apply never (strip)    |  250.8 |    66.8 |     3.736x |   3.35-4.23 | 0.975 | 5 |  faster |
| runtime color::ansi          |  435.6 |    80.8 |     5.431x |   5.14-6.39 | 0.994 | 5 |  faster |
| runtime name_color().ansi    |  534.8 |   167.7 |     3.184x |   3.03-3.73 | 0.999 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 4.589 over 27 rows (min 1.512 log line apply never (strip); max 60.636 64K plain collapse ansi256)
per-run geomean: min 4.509, median 4.612, max 4.662 over 5 runs
A/A geomean 0.993

### Intel i9-9980HK: anchor column (code that is the same in both builds; ratio should be 1)

| row                          |  START |   HEAD | START/HEAD |     range |   A/A | n | verdict |
| ---------------------------- | -----: | -----: | ---------: | --------: | ----: | : | ------: |
| plain collapse none          |  376.4 |  369.6 |     0.988x | 0.88-1.08 | 1.001 | 5 |   noise |
| plain collapse ansi16        |  376.3 |  369.7 |     1.000x | 0.96-1.06 | 1.049 | 5 |   noise |
| plain collapse ansi256       |  372.6 |  360.0 |     1.000x | 0.99-1.05 | 1.000 | 5 |   noise |
| plain collapse truecolor     |  372.5 |  360.1 |     1.000x | 0.96-1.05 | 1.000 | 5 |   noise |
| log line collapse none       |  605.5 |  605.7 |     1.005x | 0.85-1.14 | 0.999 | 5 |   noise |
| log line collapse ansi16     |  950.6 |  906.0 |     1.049x | 1.00-1.14 | 1.006 | 5 |   noise |
| log line collapse ansi256    |  931.6 |  886.0 |     1.010x | 1.00-1.14 | 0.999 | 5 |   noise |
| log line collapse truecolor  |  950.4 |  902.4 |     1.008x | 1.01-1.14 | 1.002 | 5 |   noise |
| colorful collapse none       | 1485.4 | 1481.5 |     1.003x | 0.96-1.05 | 1.001 | 5 |   noise |
| colorful collapse ansi16     | 2462.8 | 2575.9 |     1.001x | 0.92-1.05 | 0.997 | 5 |   noise |
| colorful collapse ansi256    | 2508.0 | 2388.4 |     1.007x | 1.00-1.06 | 1.002 | 5 |   noise |
| colorful collapse truecolor  | 2434.5 | 2414.3 |     1.007x | 1.00-1.06 | 1.000 | 5 |   noise |
| 64K plain collapse none      | 180095 | 179714 |     1.001x | 1.00-1.00 | 1.000 | 5 |   noise |
| 64K plain collapse ansi16    | 180189 | 180234 |     1.000x | 1.00-1.00 | 0.999 | 5 |   noise |
| 64K plain collapse ansi256   | 180120 | 180207 |     1.000x | 1.00-1.00 | 1.000 | 5 |   noise |
| 64K plain collapse truecolor | 180024 | 179901 |     1.000x | 0.97-1.00 | 0.999 | 5 |   noise |
| 64K color collapse none      | 109680 | 109384 |     1.003x | 0.96-1.00 | 0.999 | 5 |   noise |
| 64K color collapse ansi16    | 137576 | 137440 |     1.001x | 0.95-1.00 | 0.998 | 5 |   noise |
| 64K color collapse ansi256   | 135786 | 136532 |     0.994x | 0.96-1.01 | 0.992 | 5 |   noise |
| 64K color collapse truecolor | 136686 | 136930 |     0.997x | 0.95-1.00 | 0.957 | 5 |   noise |
| log line apply always+auto   | 1002.9 |  993.6 |     1.008x | 0.97-1.01 | 0.957 | 5 |   noise |
| log line apply auto+auto     | 1072.4 | 1061.4 |     1.009x | 0.97-1.01 | 0.958 | 5 |   noise |
| log line apply always+256    |  894.1 |  891.3 |     1.005x | 0.93-1.01 | 0.959 | 5 |   noise |
| log line apply never (strip) |  470.3 |  462.4 |     1.020x | 0.95-1.05 | 0.976 | 5 |   noise |
| plain apply never (strip)    |  205.4 |  198.0 |     1.006x | 0.94-1.15 | 0.994 | 5 |   noise |
| runtime color::ansi          |  431.9 |  437.3 |     0.998x | 0.96-1.17 | 0.996 | 5 |   noise |
| runtime name_color().ansi    |  534.2 |  537.0 |     1.004x | 0.95-1.18 | 1.000 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.004 over 27 rows (min 0.988 plain collapse none; max 1.049 log line collapse ansi16)
per-run geomean: min 0.991, median 1.012, max 1.018 over 5 runs
A/A geomean 0.994
