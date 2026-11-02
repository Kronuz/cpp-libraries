# unicode: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/unicode#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `d80b6bb 2026-10-22 04:40:36 -0700 Link the shared C++ library catalog [skip ci]`
- HEAD: `7405536 2026-11-01 03:58:04 -0800 Shape the README to the family standard [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `unicode.hh`, `unicode_tables.hh`
- Bench source: bench/bench.cc (HEAD), with `test/unicode_old.hh` (the frozen original)
- Rows dropped because the API is new since START: none
- Metric: column `new` in ns per code point (each decoder in eight loop copies shifted by 8 bytes, the bench reports the mean); `old` (the frozen original) is the anchor
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -I w/unicode-{start|head} w/unicode-head/bench/bench.cc`
- Raw per-round outputs: `$GATE/raw/unicode/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 27 | 1.305 | 1.288-1.320 | 1.003 | 0 | 0.988 english+ encode |
| Intel i9-9980HK | 27 | 1.224 | 1.212-1.249 | 0.998 | 0 | 0.955 emoji encode |

**Verdict: FASTER**; geomean 1.305 / 1.224 (Apple M4 Pro / Intel i9-9980HK).

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: none.
- Intel i9-9980HK: none.

## Notes

- START's `next_utf8` decided ASCII on the first byte; HEAD decides it on a window of eight bytes and sends the rest to an out-of-line `decode_utf8` that starts on a 64-byte boundary (CHANGELOG 2026-11-01). Decoded code points and bytes consumed are identical for every input, invalid sequences included.
- The bench runs each decoder in eight copies of the loop shifted by 8 bytes and reports the mean over the eight, because the same code runs up to 30% apart on the i9 depending on where its loop lands. The `old` column (frozen original `test/unicode_old.hh`) is the anchor and carries that layout noise in the bench's own `layout` column.
- `encode` rows (`append_utf8`) run the same code before and after.

## Apple M4 Pro: per-row results (library column)

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| english decode        |  1.67 | 0.755 |     2.207x | 2.03-2.40 | 0.982 | 5 |  faster |
| english pipeline      |  1.85 | 0.654 |     2.840x | 2.79-2.89 | 1.009 | 5 |  faster |
| english encode        | 0.792 | 0.784 |     1.004x | 1.00-1.03 | 1.005 | 5 |   noise |
| european decode       |  1.81 |  1.09 |     1.676x | 1.56-1.70 | 0.996 | 5 |  faster |
| european pipeline     |  1.94 |  1.09 |     1.778x | 1.76-1.81 | 1.003 | 5 |  faster |
| european encode       | 0.958 | 0.963 |     0.998x | 0.99-1.01 | 0.999 | 5 |   noise |
| english+ decode       |  1.77 | 0.973 |     1.793x | 1.75-1.93 | 0.999 | 5 |  faster |
| english+ pipeline     |  1.93 | 0.996 |     1.947x | 1.92-1.96 | 1.003 | 5 |  faster |
| english+ encode       | 0.906 | 0.917 |     0.988x | 0.97-1.03 | 1.003 | 5 |   noise |
| latin1 decode         |  1.81 |  1.11 |     1.603x | 1.58-1.69 | 0.998 | 5 |  faster |
| latin1 pipeline       |  1.89 |  1.08 |     1.743x | 1.73-1.76 | 0.997 | 5 |  faster |
| latin1 encode         | 0.927 | 0.938 |     1.001x | 0.98-1.01 | 0.998 | 5 |   noise |
| cyrillic decode       |  1.87 |  1.65 |     1.131x | 1.12-1.24 | 0.970 | 5 |   noise |
| cyrillic pipeline     |  2.57 |  2.00 |     1.293x | 1.09-1.42 | 1.092 | 5 |  faster |
| cyrillic encode       |  2.17 |  2.15 |     1.016x | 1.00-1.02 | 0.998 | 5 |   noise |
| cjk decode            |  1.83 |  1.58 |     1.147x | 1.08-1.37 | 0.940 | 5 |   noise |
| cjk pipeline          |  2.38 |  1.94 |     1.235x | 1.18-1.25 | 1.057 | 5 |  faster |
| cjk encode            |  2.53 |  2.51 |     1.009x | 1.01-1.01 | 0.995 | 5 |   noise |
| emoji decode          |  3.45 |  2.79 |     1.237x | 1.20-1.25 | 1.012 | 5 |  faster |
| emoji pipeline        |  3.88 |  3.21 |     1.206x | 1.20-1.22 | 1.002 | 5 |  faster |
| emoji encode          |  3.80 |  3.70 |     1.006x | 0.99-1.05 | 0.994 | 5 |   noise |
| random mix decode     |  6.10 |  4.65 |     1.305x | 1.29-1.32 | 1.016 | 5 |  faster |
| random mix pipeline   |  6.42 |  5.09 |     1.265x | 1.25-1.28 | 1.006 | 5 |  faster |
| random mix encode     |  5.67 |  5.60 |     1.001x | 1.00-1.01 | 1.014 | 5 |   noise |
| random bytes decode   |  3.00 |  2.54 |     1.165x | 1.16-1.19 | 0.991 | 5 |  faster |
| random bytes pipeline |  3.34 |  2.85 |     1.163x | 1.15-1.17 | 1.014 | 5 |  faster |
| random bytes encode   |  3.76 |  3.69 |     1.020x | 0.97-1.03 | 0.995 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.305 over 27 rows (min 0.988 english+ encode; max 2.840 english pipeline)
per-run geomean: min 1.288, median 1.305, max 1.320 over 5 runs
A/A geomean 1.003

### Apple M4 Pro: anchor column (code that is the same in both builds; ratio should be 1)

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| english decode        |  1.64 |  1.68 |     1.006x | 0.89-1.06 | 0.962 | 5 |   noise |
| english pipeline      |  1.85 |  1.83 |     1.009x | 1.00-1.01 | 1.005 | 5 |   noise |
| english encode        | 0.788 | 0.780 |     1.001x | 0.99-1.02 | 0.999 | 5 |   noise |
| european decode       |  1.75 |  1.79 |     0.996x | 0.95-1.04 | 0.984 | 5 |   noise |
| european pipeline     |  1.94 |  1.91 |     1.003x | 1.00-1.03 | 0.998 | 5 |   noise |
| european encode       | 0.977 | 0.963 |     1.015x | 1.01-1.04 | 1.003 | 5 |   noise |
| english+ decode       |  1.74 |  1.74 |     1.014x | 0.94-1.05 | 0.985 | 5 |   noise |
| english+ pipeline     |  1.95 |  1.89 |     1.025x | 1.01-1.03 | 1.005 | 5 |  faster |
| english+ encode       | 0.921 | 0.915 |     1.002x | 1.00-1.02 | 1.009 | 5 |   noise |
| latin1 decode         |  1.80 |  1.72 |     1.009x | 0.98-1.07 | 0.998 | 5 |   noise |
| latin1 pipeline       |  1.89 |  1.88 |     1.005x | 1.00-1.02 | 0.992 | 5 |   noise |
| latin1 encode         | 0.938 | 0.931 |     1.003x | 0.99-1.02 | 0.989 | 5 |   noise |
| cyrillic decode       |  1.91 |  1.87 |     1.031x | 0.83-1.28 | 0.995 | 5 |   noise |
| cyrillic pipeline     |  2.41 |  2.38 |     0.991x | 0.94-1.01 | 0.971 | 5 |   noise |
| cyrillic encode       |  2.13 |  2.13 |     1.002x | 0.99-1.00 | 1.000 | 5 |   noise |
| cjk decode            |  1.86 |  1.91 |     0.958x | 0.90-1.00 | 0.955 | 5 |   noise |
| cjk pipeline          |  2.40 |  2.38 |     1.009x | 0.82-1.05 | 1.048 | 5 |   noise |
| cjk encode            |  2.54 |  2.51 |     1.013x | 0.99-1.01 | 0.989 | 5 |   noise |
| emoji decode          |  3.48 |  3.43 |     1.008x | 0.97-1.07 | 0.997 | 5 |   noise |
| emoji pipeline        |  3.84 |  3.84 |     0.979x | 0.97-1.06 | 1.001 | 5 |   noise |
| emoji encode          |  3.71 |  3.74 |     1.010x | 0.99-1.02 | 1.009 | 5 |   noise |
| random mix decode     |  6.06 |  6.08 |     1.000x | 0.99-1.02 | 1.003 | 5 |   noise |
| random mix pipeline   |  6.47 |  6.46 |     0.996x | 0.99-1.02 | 0.996 | 5 |   noise |
| random mix encode     |  5.67 |  5.62 |     1.010x | 1.00-1.02 | 1.009 | 5 |   noise |
| random bytes decode   |  2.97 |  2.95 |     1.005x | 0.99-1.03 | 1.001 | 5 |   noise |
| random bytes pipeline |  3.32 |  3.24 |     1.018x | 1.00-1.03 | 0.999 | 5 |   noise |
| random bytes encode   |  3.64 |  3.66 |     0.996x | 0.97-1.02 | 0.991 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.004 over 27 rows (min 0.958 cjk decode; max 1.031 cyrillic decode)
per-run geomean: min 0.987, median 1.004, max 1.014 over 5 runs
A/A geomean 0.996

## Intel i9-9980HK: per-row results (library column)

| row                   | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| english decode        |  2.03 | 0.999 |     2.045x | 2.00-2.07 | 1.007 | 5 |  faster |
| english pipeline      |  3.02 |  1.58 |     1.911x | 1.81-1.92 | 0.991 | 5 |  faster |
| english encode        |  2.50 |  2.36 |     1.026x | 0.85-1.19 | 0.943 | 5 |   noise |
| european decode       |  2.28 |  1.50 |     1.528x | 1.44-1.57 | 1.004 | 5 |  faster |
| european pipeline     |  3.17 |  2.28 |     1.403x | 1.34-1.48 | 1.004 | 5 |  faster |
| european encode       |  2.85 |  2.85 |     0.987x | 0.95-1.05 | 1.004 | 5 |   noise |
| english+ decode       |  2.17 |  1.32 |     1.650x | 1.64-1.71 | 0.997 | 5 |  faster |
| english+ pipeline     |  3.14 |  2.01 |     1.553x | 1.52-1.60 | 0.986 | 5 |  faster |
| english+ encode       |  3.03 |  3.06 |     0.969x | 0.95-1.08 | 1.015 | 5 |   noise |
| latin1 decode         |  2.20 |  1.51 |     1.469x | 1.39-1.48 | 1.005 | 5 |  faster |
| latin1 pipeline       |  3.18 |  2.23 |     1.387x | 1.37-1.44 | 1.012 | 5 |  faster |
| latin1 encode         |  2.77 |  2.74 |     1.011x | 0.90-1.10 | 0.938 | 5 |   noise |
| cyrillic decode       |  2.72 |  2.73 |     1.001x | 0.98-1.03 | 0.990 | 5 |   noise |
| cyrillic pipeline     |  4.16 |  4.13 |     1.004x | 0.98-1.06 | 0.996 | 5 |   noise |
| cyrillic encode       |  6.04 |  5.67 |     1.021x | 0.91-1.11 | 1.013 | 5 |   noise |
| cjk decode            |  4.10 |  2.91 |     1.402x | 1.27-1.42 | 1.016 | 5 |  faster |
| cjk pipeline          |  5.20 |  4.08 |     1.270x | 1.22-1.31 | 0.998 | 5 |  faster |
| cjk encode            |  7.25 |  7.03 |     1.018x | 0.87-1.11 | 1.083 | 5 |   noise |
| emoji decode          |  6.34 |  5.01 |     1.291x | 1.23-1.32 | 0.988 | 5 |  faster |
| emoji pipeline        |  7.71 |  6.36 |     1.192x | 1.17-1.25 | 0.996 | 5 |  faster |
| emoji encode          |  9.89 |  9.65 |     0.955x | 0.85-1.14 | 0.982 | 5 |   noise |
| random mix decode     |  8.98 |  6.89 |     1.309x | 1.24-1.38 | 0.999 | 5 |  faster |
| random mix pipeline   |  10.3 |  8.53 |     1.204x | 1.20-1.23 | 1.003 | 5 |  faster |
| random mix encode     |  11.8 |  11.0 |     1.017x | 0.98-1.15 | 0.984 | 5 |   noise |
| random bytes decode   |  4.18 |  3.53 |     1.171x | 1.14-1.21 | 1.016 | 5 |  faster |
| random bytes pipeline |  5.09 |  4.94 |     1.038x | 1.02-1.05 | 1.003 | 5 |  faster |
| random bytes encode   |  6.95 |  6.88 |     1.012x | 0.96-1.05 | 0.972 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.224 over 27 rows (min 0.955 emoji encode; max 2.045 english decode)
per-run geomean: min 1.212, median 1.229, max 1.249 over 5 runs
A/A geomean 0.998

### Intel i9-9980HK: anchor column (code that is the same in both builds; ratio should be 1)

| row                   | START | HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------- | ----: | ---: | ---------: | --------: | ----: | : | ------: |
| english decode        |  2.04 | 2.07 |     0.984x | 0.98-1.00 | 1.013 | 5 |   noise |
| english pipeline      |  2.94 | 2.98 |     0.990x | 0.95-1.00 | 0.994 | 5 |   noise |
| english encode        |  1.76 | 1.69 |     0.963x | 0.90-1.27 | 0.968 | 5 |   noise |
| european decode       |  2.28 | 2.28 |     1.007x | 0.97-1.03 | 1.003 | 5 |   noise |
| european pipeline     |  3.15 | 3.32 |     0.935x | 0.91-1.00 | 1.018 | 5 |  slower |
| european encode       |  2.25 | 2.19 |     0.985x | 0.94-1.09 | 1.000 | 5 |   noise |
| english+ decode       |  2.17 | 2.18 |     0.989x | 0.98-1.03 | 0.987 | 5 |   noise |
| english+ pipeline     |  3.08 | 3.16 |     0.961x | 0.94-1.00 | 0.987 | 5 |   noise |
| english+ encode       |  2.05 | 2.12 |     0.987x | 0.91-1.05 | 1.001 | 5 |   noise |
| latin1 decode         |  2.21 | 2.21 |     1.000x | 0.97-1.03 | 1.004 | 5 |   noise |
| latin1 pipeline       |  3.13 | 3.21 |     0.974x | 0.94-1.00 | 1.010 | 5 |   noise |
| latin1 encode         |  2.08 | 1.98 |     0.995x | 0.92-1.10 | 0.939 | 5 |   noise |
| cyrillic decode       |  2.73 | 2.73 |     0.996x | 0.98-1.04 | 0.983 | 5 |   noise |
| cyrillic pipeline     |  4.08 | 4.10 |     0.995x | 0.98-1.05 | 0.998 | 5 |   noise |
| cyrillic encode       |  5.28 | 5.08 |     1.030x | 0.92-1.07 | 1.026 | 5 |   noise |
| cjk decode            |  4.12 | 4.05 |     1.005x | 0.87-1.04 | 1.008 | 5 |   noise |
| cjk pipeline          |  5.09 | 5.01 |     1.009x | 0.99-1.05 | 1.006 | 5 |   noise |
| cjk encode            |  6.11 | 6.07 |     1.021x | 0.82-1.05 | 1.082 | 5 |   noise |
| emoji decode          |  6.39 | 6.35 |     1.007x | 0.96-1.04 | 0.995 | 5 |   noise |
| emoji pipeline        |  7.62 | 7.55 |     0.997x | 0.99-1.05 | 0.991 | 5 |   noise |
| emoji encode          |  8.41 | 8.29 |     1.015x | 0.84-1.15 | 0.962 | 5 |   noise |
| random mix decode     |  9.03 | 8.94 |     0.997x | 0.95-1.04 | 1.000 | 5 |   noise |
| random mix pipeline   |  10.2 | 10.4 |     0.988x | 0.98-1.00 | 1.000 | 5 |   noise |
| random mix encode     |  10.1 | 9.89 |     1.017x | 0.95-1.11 | 0.974 | 5 |   noise |
| random bytes decode   |  4.15 | 4.13 |     0.994x | 0.99-1.02 | 1.006 | 5 |   noise |
| random bytes pipeline |  5.05 | 5.21 |     0.975x | 0.95-0.98 | 0.999 | 5 |  slower |
| random bytes encode   |  6.22 | 6.14 |     1.018x | 0.97-1.11 | 0.981 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.994 over 27 rows (min 0.935 european pipeline; max 1.030 cyrillic encode)
per-run geomean: min 0.984, median 0.991, max 1.019 over 5 runs
A/A geomean 0.997
