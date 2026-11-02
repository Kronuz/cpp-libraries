# strict-stox: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/strict-stox#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `f0f7374 2026-10-28 04:52:59 -0700 Credit Germán Méndez Bravo and bound Dubalu's years`
- HEAD: `c1c9bc1 2026-11-01 07:57:17 -0800 Shape the README to the family standard and move the tables to docs/perf [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `strict_stox.hh`
- Bench source: bench/bench.cc (HEAD), derived copy `bench_gate.cc`: the `fast%` column (which reads `strict_stox_detail::fast_fp`, absent at START) is stubbed to 0, and `-DSTRICT_STOX_BENCH_NO_FC` drops the `std::from_chars` comparator column (unavailable in the i9's SDK); the same file for both builds
- Rows dropped because the API is new since START: none (the `fast%` column is a share, not a time)
- Metric: column `new` (the library); `old` (the frozen original header) is the anchor
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -DSTRICT_STOX_BENCH_NO_FC -I w/strict-stox-{start|head} -I w/strict-stox-head/test w/strict-stox-head/bench/bench_gate.cc`
- Raw per-round outputs: `$GATE/raw/strict-stox/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 34 | 1.753 | 1.740-1.763 | 1.003 | 6 | 0.509 stod 800 digits |
| Intel i9-9980HK | 34 | 1.518 | 1.497-1.534 | 0.992 | 7 | 0.429 stod 800 digits |

**Verdict: SLOWER-ROWS (6 on the Apple M4 Pro, 7 on the Intel i9-9980HK)**; geomean 1.753 / 1.518 (Apple M4 Pro / Intel i9-9980HK).

Geomean without the rows that are not comparable or are algorithmic changes (`800 digits`): Apple M4 Pro 1.820; Intel i9-9980HK 1.578. START parsed only the first 63 bytes of the text (a 64-byte buffer), HEAD parses all 800 digits: that row is not comparable.

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: 6
  - `stod 800 digits`: 0.509 (round range 0.51-0.52, A/A deviation 0.017). not comparable: START copied the text into `char buf[64]` and parsed its first 63 bytes (CHANGELOG 2026-10-31, 'Parse input of any length instead of cutting it at 63 bytes'); HEAD parses all 800 digits, so the row does about 13x the input work and now returns the right value.
  - `stof inf, nan`: 0.808 (round range 0.78-0.85, A/A deviation 0.045). accepted trade-off, same section of docs/perf/README.md: a declined text pays the attempt on top of `strtod`/`strtof`.
  - `stod inf, nan`: 0.825 (round range 0.80-0.83, A/A deviation 0.006). accepted trade-off, same section of docs/perf/README.md: a declined text pays the attempt on top of `strtod`/`strtof`.
  - `stod " 1.5" (white space)`: 0.828 (round range 0.82-0.84, A/A deviation 0.010). accepted trade-off, documented in docs/perf/README.md 'Declined and failing text': text the fast path declines pays the attempt on top of `strto*` (4 to 5 ns on the M4 Pro, 9 to 11 ns on the i9).
  - `stof " 1.5" (white space)`: 0.833 (round range 0.83-0.85, A/A deviation 0.020). accepted trade-off, documented in docs/perf/README.md 'Declined and failing text': text the fast path declines pays the attempt on top of `strto*` (4 to 5 ns on the M4 Pro, 9 to 11 ns on the i9).
  - `stoll 20 digits (ERANGE)`: 0.861 (round range 0.85-0.89, A/A deviation 0.021). accepted trade-off, same section of docs/perf/README.md (`stoll` 20 digits 28.1 to 32.6 ns on the M4, 66.3 to 75.9 on the i9); the subnormal/overflow `stod`/`stof` rows are the opposite: faster, now decided without libc.
- Intel i9-9980HK: 7
  - `stod 800 digits`: 0.429 (round range 0.40-0.44, A/A deviation 0.041). not comparable: START copied the text into `char buf[64]` and parsed its first 63 bytes (CHANGELOG 2026-10-31, 'Parse input of any length instead of cutting it at 63 bytes'); HEAD parses all 800 digits, so the row does about 13x the input work and now returns the right value.
  - `stod inf, nan`: 0.734 (round range 0.69-0.76, A/A deviation 0.050). accepted trade-off, same section of docs/perf/README.md: a declined text pays the attempt on top of `strtod`/`strtof`.
  - `stof inf, nan`: 0.761 (round range 0.74-0.79, A/A deviation 0.058). accepted trade-off, same section of docs/perf/README.md: a declined text pays the attempt on top of `strtod`/`strtof`.
  - `stof " 1.5" (white space)`: 0.820 (round range 0.80-0.86, A/A deviation 0.119). accepted trade-off, documented in docs/perf/README.md 'Declined and failing text': text the fast path declines pays the attempt on top of `strto*` (4 to 5 ns on the M4 Pro, 9 to 11 ns on the i9).
  - `stod odd integers 2^53..2^54 (ties)`: 0.821 (round range 0.81-0.85, A/A deviation 0.049). unexplained, i9 only (the same row on the M4 is not under 0.97): docs/perf/README.md and the CHANGELOG record it faster than `strtod` on the i9 too (42.8 to 36.8 ns); here START measures 33.5 ns and HEAD 40.1 with an A/A of 1.02. HEAD's exact path decides these halfway points after the table declines them.
  - `stod " 1.5" (white space)`: 0.854 (round range 0.83-0.88, A/A deviation 0.117). accepted trade-off, documented in docs/perf/README.md 'Declined and failing text': text the fast path declines pays the attempt on top of `strto*` (4 to 5 ns on the M4 Pro, 9 to 11 ns on the i9).
  - `stoll 20 digits (ERANGE)`: 0.881 (round range 0.84-0.90, A/A deviation 0.015). accepted trade-off, same section of docs/perf/README.md (`stoll` 20 digits 28.1 to 32.6 ns on the M4, 66.3 to 75.9 on the i9); the subnormal/overflow `stod`/`stof` rows are the opposite: faster, now decided without libc.

## Notes

- START's `strict_stox.hh` is the thin wrapper over `strto*` (the same code as the frozen `test/strict_stox_old.hh`, which is the bench's `old` column and the anchor). HEAD adds the table-driven fast path, the 8-byte long-text reader and the exact decimal path.
- Correctness changes that make rows not comparable as speed: HEAD parses text of any length (START cut it at 63 bytes, CHANGELOG 2026-10-31), so the 100 and 800 digit rows do more work at HEAD than START did on the same text; HEAD also decides the ambiguous long texts exactly instead of calling libc. The 2^52..2^53 tie, subnormal and overflow rows are the new exact path against `strtod`.
- The bench's `fast%` column (share of the pool the fast path takes) is stubbed to 0 in the gate copy because `strict_stox_detail::fast_fp` does not exist at START; the `std::from_chars` column is dropped on both builds (`-DSTRICT_STOX_BENCH_NO_FC`).
- Rows whose text the fast path declines (white space, a sign, a prefix, base 0, `inf`/`nan`, 20 digit overflow) pay the attempt on top of `strto*` and are expected to be slower than START; they are the rows to read in the list above.

## Apple M4 Pro: per-row results (library column)

| row                                 | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| stoi 1-9 digits                     |  19.3 |  5.50 |     3.491x | 3.42-3.53 | 0.990 | 5 |  faster |
| stoull 1-19 digits                  |  26.8 |  6.50 |     4.154x | 4.00-4.32 | 0.996 | 5 |  faster |
| stoul base 16                       |  26.0 |  5.20 |     4.981x | 4.91-5.08 | 0.996 | 5 |  faster |
| stoll " 42" (white space)           |  16.6 |  15.5 |     1.065x | 1.06-1.13 | 0.994 | 5 |  faster |
| stoll "+42"                         |  16.5 |  15.0 |     1.101x | 1.05-1.13 | 1.012 | 5 |  faster |
| stoll "42", base 0                  |  16.1 |  14.8 |     1.082x | 1.04-1.13 | 0.994 | 5 |  faster |
| stoll "0x1f", base 16               |  16.2 |  14.7 |     1.102x | 1.09-1.12 | 1.012 | 5 |  faster |
| stoll "abc" (EINVAL)                |  12.3 |  10.5 |     1.170x | 1.15-1.18 | 1.000 | 5 |  faster |
| stoll 20 digits (ERANGE)            |  28.2 |  32.5 |     0.861x | 0.85-0.89 | 1.004 | 5 |  slower |
| stod 1.234-like (short)             |  19.4 |  8.50 |     2.274x | 2.23-2.28 | 1.005 | 5 |  faster |
| stod 1-9 digit integers             |  16.0 |  4.50 |     3.556x | 3.45-3.67 | 1.000 | 5 |  faster |
| stod 17 digits (x/7)                |  26.1 |  10.3 |     2.529x | 2.49-2.56 | 1.016 | 5 |  faster |
| stod 17 digits, any exponent        |  31.0 |  11.7 |     2.627x | 2.57-2.66 | 1.013 | 5 |  faster |
| stod shortest repr (JSON-like)      |  30.7 |  10.9 |     2.811x | 2.76-2.87 | 1.013 | 5 |  faster |
| stod 1.5e-7-like                    |  27.4 |  10.3 |     2.670x | 2.58-2.71 | 1.015 | 5 |  faster |
| stod 25-40 digits                   |  43.9 |  20.0 |     2.195x | 2.13-2.22 | 1.007 | 5 |  faster |
| stod 100 digits                     |  67.6 |  28.4 |     2.380x | 2.37-2.41 | 1.007 | 5 |  faster |
| stod 800 digits                     |  65.6 | 128.0 |     0.509x | 0.51-0.52 | 1.002 | 5 |  slower |
| stof 1.234-like (short)             |  20.5 |  9.20 |     2.228x | 2.18-2.29 | 1.000 | 5 |  faster |
| stof 9 digits                       |  23.3 |  7.10 |     3.286x | 3.28-3.34 | 1.004 | 5 |  faster |
| stof 25-40 digits                   |  41.8 |  22.9 |     1.825x | 1.77-1.84 | 1.000 | 5 |  faster |
| stod " 1.5" (white space)           |  19.3 |  23.4 |     0.828x | 0.82-0.84 | 1.000 | 5 |  slower |
| stod inf, nan                       |  17.9 |  21.8 |     0.825x | 0.80-0.83 | 0.994 | 5 |  slower |
| stod near DBL_MAX                   |  25.0 |  10.5 |     2.404x | 2.35-2.42 | 1.020 | 5 |  faster |
| stof " 1.5" (white space)           |  20.8 |  24.8 |     0.833x | 0.83-0.85 | 1.000 | 5 |  slower |
| stof inf, nan                       |  18.1 |  22.4 |     0.808x | 0.78-0.85 | 1.011 | 5 |  slower |
| stof near FLT_MAX                   |  20.3 |  9.40 |     2.158x | 2.12-2.20 | 0.990 | 5 |  faster |
| stod exact ties 2^52..2^53 + .5     |  55.8 |  19.1 |     2.917x | 2.81-2.97 | 1.005 | 5 |  faster |
| stod odd integers 2^53..2^54 (ties) |  18.3 |  16.4 |     1.116x | 1.10-1.13 | 1.011 | 5 |  faster |
| stod subnormal (ERANGE)             |  22.2 |  18.1 |     1.227x | 1.21-1.27 | 0.987 | 5 |  faster |
| stod overflow, underflow (ERANGE)   |  24.4 |  21.8 |     1.119x | 1.11-1.14 | 0.988 | 5 |  faster |
| stof odd integers 2^24..2^25 (ties) |  34.0 |  12.7 |     2.656x | 2.62-2.68 | 1.000 | 5 |  faster |
| stof subnormal (ERANGE)             |  65.9 |  18.3 |     3.584x | 3.46-3.66 | 1.011 | 5 |  faster |
| stof overflow (ERANGE)              |  23.0 |  17.6 |     1.307x | 1.28-1.33 | 1.013 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.753 over 34 rows (min 0.509 stod 800 digits; max 4.981 stoul base 16)
per-run geomean: min 1.740, median 1.753, max 1.763 over 5 runs
A/A geomean 1.003

### Apple M4 Pro: anchor column (code that is the same in both builds; ratio should be 1)

| row                                 | START | HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | ----: | ---: | ---------: | --------: | ----: | : | ------: |
| stoi 1-9 digits                     |  19.5 | 19.5 |     0.990x | 0.97-1.03 | 0.990 | 5 |   noise |
| stoull 1-19 digits                  |  26.8 | 26.4 |     1.011x | 0.97-1.05 | 0.996 | 5 |   noise |
| stoul base 16                       |  26.6 | 26.5 |     1.015x | 0.98-1.02 | 0.996 | 5 |  faster |
| stoll " 42" (white space)           |  16.4 | 16.6 |     0.988x | 0.97-1.06 | 1.006 | 5 |   noise |
| stoll "+42"                         |  16.6 | 16.5 |     1.018x | 1.00-1.02 | 1.012 | 5 |   noise |
| stoll "42", base 0                  |  16.4 | 16.2 |     1.006x | 0.96-1.02 | 1.018 | 5 |   noise |
| stoll "0x1f", base 16               |  16.2 | 16.2 |     1.006x | 0.97-1.01 | 1.006 | 5 |   noise |
| stoll "abc" (EINVAL)                |  12.4 | 12.5 |     0.992x | 0.98-1.02 | 1.008 | 5 |   noise |
| stoll 20 digits (ERANGE)            |  28.0 | 28.1 |     1.004x | 0.98-1.01 | 1.000 | 5 |   noise |
| stod 1.234-like (short)             |  19.3 | 19.5 |     0.990x | 0.98-1.01 | 0.990 | 5 |   noise |
| stod 1-9 digit integers             |  15.7 | 16.0 |     0.994x | 0.95-1.01 | 1.006 | 5 |   noise |
| stod 17 digits (x/7)                |  25.9 | 26.0 |     0.996x | 0.99-1.00 | 1.008 | 5 |   noise |
| stod 17 digits, any exponent        |  30.6 | 30.5 |     1.010x | 0.96-1.03 | 1.017 | 5 |   noise |
| stod shortest repr (JSON-like)      |  30.3 | 30.6 |     0.997x | 0.98-1.01 | 1.003 | 5 |   noise |
| stod 1.5e-7-like                    |  27.0 | 27.1 |     0.996x | 0.99-1.01 | 0.989 | 5 |   noise |
| stod 25-40 digits                   |  43.6 | 43.9 |     0.986x | 0.96-1.02 | 0.989 | 5 |   noise |
| stod 100 digits                     |  67.7 | 67.5 |     0.999x | 0.99-1.01 | 1.004 | 5 |   noise |
| stod 800 digits                     |  65.7 | 65.5 |     1.003x | 0.99-1.01 | 1.006 | 5 |   noise |
| stof 1.234-like (short)             |  21.4 | 20.9 |     1.009x | 1.00-1.04 | 1.005 | 5 |   noise |
| stof 9 digits                       |  23.3 | 23.5 |     0.987x | 0.98-1.00 | 1.000 | 5 |   noise |
| stof 25-40 digits                   |  41.8 | 42.0 |     0.998x | 0.96-1.02 | 1.000 | 5 |   noise |
| stod " 1.5" (white space)           |  19.2 | 19.3 |     0.990x | 0.95-1.02 | 0.995 | 5 |   noise |
| stod inf, nan                       |  18.0 | 18.1 |     0.989x | 0.98-1.00 | 1.011 | 5 |   noise |
| stod near DBL_MAX                   |  24.9 | 24.8 |     1.004x | 1.00-1.01 | 1.004 | 5 |   noise |
| stof " 1.5" (white space)           |  21.0 | 21.3 |     0.986x | 0.97-0.99 | 1.000 | 5 |   noise |
| stof inf, nan                       |  18.0 | 18.4 |     0.994x | 0.97-1.02 | 1.000 | 5 |   noise |
| stof near FLT_MAX                   |  20.5 | 20.6 |     0.995x | 0.96-1.04 | 1.015 | 5 |   noise |
| stod exact ties 2^52..2^53 + .5     |  55.3 | 55.2 |     0.998x | 0.99-1.01 | 1.009 | 5 |   noise |
| stod odd integers 2^53..2^54 (ties) |  18.4 | 18.1 |     1.011x | 0.99-1.03 | 1.005 | 5 |   noise |
| stod subnormal (ERANGE)             |  22.4 | 22.3 |     1.004x | 1.00-1.01 | 1.004 | 5 |   noise |
| stod overflow, underflow (ERANGE)   |  24.5 | 24.4 |     1.000x | 0.98-1.03 | 0.996 | 5 |   noise |
| stof odd integers 2^24..2^25 (ties) |  34.0 | 34.0 |     0.991x | 0.97-1.01 | 0.994 | 5 |   noise |
| stof subnormal (ERANGE)             |  65.5 | 65.5 |     1.000x | 0.98-1.00 | 0.989 | 5 |   noise |
| stof overflow (ERANGE)              |  23.2 | 23.0 |     1.013x | 1.01-1.01 | 1.013 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.999 over 34 rows (min 0.986 stof " 1.5" (white space); max 1.018 stoll "+42")
per-run geomean: min 0.995, median 0.998, max 1.003 over 5 runs
A/A geomean 1.003

## Intel i9-9980HK: per-row results (library column)

| row                                 | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| stoi 1-9 digits                     |  43.5 |  10.8 |     4.102x | 3.96-4.18 | 0.982 | 5 |  faster |
| stoull 1-19 digits                  |  61.1 |  14.8 |     4.074x | 3.73-4.46 | 0.973 | 5 |  faster |
| stoul base 16                       | 101.4 |  13.1 |     7.860x | 7.69-8.00 | 0.993 | 5 |  faster |
| stoll " 42" (white space)           |  40.7 |  41.7 |     0.954x | 0.87-1.00 | 1.010 | 5 |   noise |
| stoll "+42"                         |  39.2 |  40.1 |     0.974x | 0.94-1.01 | 0.953 | 5 |   noise |
| stoll "42", base 0                  |  37.7 |  39.7 |     0.982x | 0.94-0.99 | 0.992 | 5 |   noise |
| stoll "0x1f", base 16               |  40.3 |  40.5 |     1.013x | 0.94-1.04 | 1.000 | 5 |   noise |
| stoll "abc" (EINVAL)                |  28.6 |  25.4 |     1.144x | 1.11-1.15 | 1.007 | 5 |  faster |
| stoll 20 digits (ERANGE)            |  70.8 |  80.4 |     0.881x | 0.84-0.90 | 1.003 | 5 |  slower |
| stod 1.234-like (short)             |  42.0 |  20.1 |     2.112x | 2.07-2.14 | 1.007 | 5 |  faster |
| stod 1-9 digit integers             |  31.1 |  11.7 |     2.686x | 2.61-2.70 | 0.984 | 5 |  faster |
| stod 17 digits (x/7)                |  51.5 |  26.0 |     1.996x | 1.97-2.02 | 0.983 | 5 |  faster |
| stod 17 digits, any exponent        |  58.0 |  31.5 |     1.810x | 1.66-1.87 | 0.986 | 5 |  faster |
| stod shortest repr (JSON-like)      |  65.5 |  34.8 |     1.883x | 1.81-2.16 | 0.989 | 5 |  faster |
| stod 1.5e-7-like                    |  53.9 |  29.1 |     1.887x | 1.82-1.97 | 1.006 | 5 |  faster |
| stod 25-40 digits                   | 114.3 |  65.8 |     1.723x | 1.63-1.77 | 0.961 | 5 |  faster |
| stod 100 digits                     | 116.5 |  80.7 |     1.462x | 1.41-1.54 | 1.000 | 5 |  faster |
| stod 800 digits                     | 110.3 | 258.8 |     0.429x | 0.40-0.44 | 0.993 | 5 |  slower |
| stof 1.234-like (short)             |  47.1 |  23.4 |     2.004x | 1.98-2.02 | 1.000 | 5 |  faster |
| stof 9 digits                       |  43.1 |  22.2 |     1.950x | 1.86-2.14 | 1.014 | 5 |  faster |
| stof 25-40 digits                   | 109.2 |  76.7 |     1.409x | 1.39-1.43 | 1.006 | 5 |  faster |
| stod " 1.5" (white space)           |  43.9 |  51.4 |     0.854x | 0.83-0.88 | 0.979 | 5 |  slower |
| stod inf, nan                       |  30.8 |  42.7 |     0.734x | 0.69-0.76 | 1.003 | 5 |  slower |
| stod near DBL_MAX                   |  55.5 |  29.0 |     1.961x | 1.78-2.06 | 1.010 | 5 |  faster |
| stof " 1.5" (white space)           |  46.5 |  57.5 |     0.820x | 0.80-0.86 | 0.998 | 5 |  slower |
| stof inf, nan                       |  31.9 |  41.5 |     0.761x | 0.74-0.79 | 0.988 | 5 |  slower |
| stof near FLT_MAX                   |  48.3 |  26.7 |     1.836x | 1.79-1.87 | 0.978 | 5 |  faster |
| stod exact ties 2^52..2^53 + .5     | 118.6 |  45.5 |     2.646x | 2.53-2.67 | 1.000 | 5 |  faster |
| stod odd integers 2^53..2^54 (ties) |  33.5 |  40.1 |     0.821x | 0.81-0.85 | 1.018 | 5 |  slower |
| stod subnormal (ERANGE)             |  54.6 |  49.9 |     1.093x | 1.02-1.13 | 1.021 | 5 |  faster |
| stod overflow, underflow (ERANGE)   |  50.5 |  48.1 |     1.041x | 0.94-1.09 | 0.986 | 5 |   noise |
| stof odd integers 2^24..2^25 (ties) |  72.9 |  30.9 |     2.388x | 2.28-2.63 | 0.972 | 5 |  faster |
| stof subnormal (ERANGE)             | 140.7 |  46.6 |     3.000x | 2.97-3.08 | 0.969 | 5 |  faster |
| stof overflow (ERANGE)              |  47.5 |  43.9 |     1.110x | 1.07-1.13 | 0.983 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.518 over 34 rows (min 0.429 stod 800 digits; max 7.860 stoul base 16)
per-run geomean: min 1.497, median 1.513, max 1.534 over 5 runs
A/A geomean 0.992

### Intel i9-9980HK: anchor column (code that is the same in both builds; ratio should be 1)

| row                                 | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| stoi 1-9 digits                     |  44.0 |  44.5 |     0.977x | 0.88-1.09 | 0.993 | 5 |   noise |
| stoull 1-19 digits                  |  60.0 |  63.4 |     0.962x | 0.85-1.02 | 0.993 | 5 |   noise |
| stoul base 16                       | 101.9 | 101.2 |     1.007x | 0.92-1.03 | 1.010 | 5 |   noise |
| stoll " 42" (white space)           |  40.8 |  41.2 |     0.981x | 0.96-1.00 | 1.002 | 5 |   noise |
| stoll "+42"                         |  39.8 |  41.2 |     0.973x | 0.96-1.03 | 0.973 | 5 |   noise |
| stoll "42", base 0                  |  38.0 |  40.3 |     0.940x | 0.85-1.10 | 0.997 | 5 |   noise |
| stoll "0x1f", base 16               |  40.1 |  42.1 |     0.943x | 0.91-1.01 | 0.988 | 5 |  slower |
| stoll "abc" (EINVAL)                |  29.6 |  29.6 |     0.986x | 0.95-1.02 | 1.047 | 5 |   noise |
| stoll 20 digits (ERANGE)            |  70.9 |  72.1 |     0.974x | 0.93-1.03 | 1.007 | 5 |   noise |
| stod 1.234-like (short)             |  40.8 |  43.1 |     0.947x | 0.94-0.97 | 1.017 | 5 |  slower |
| stod 1-9 digit integers             |  30.8 |  32.2 |     0.969x | 0.94-0.99 | 0.994 | 5 |  slower |
| stod 17 digits (x/7)                |  51.2 |  52.0 |     0.975x | 0.97-0.99 | 0.988 | 5 |   noise |
| stod 17 digits, any exponent        |  59.0 |  58.7 |     1.019x | 0.95-1.03 | 1.029 | 5 |   noise |
| stod shortest repr (JSON-like)      |  65.9 |  65.7 |     0.982x | 0.96-1.07 | 0.976 | 5 |   noise |
| stod 1.5e-7-like                    |  55.2 |  53.5 |     1.022x | 0.99-1.06 | 0.984 | 5 |   noise |
| stod 25-40 digits                   | 116.1 | 115.5 |     0.997x | 0.98-1.03 | 0.975 | 5 |   noise |
| stod 100 digits                     | 117.0 | 118.4 |     0.974x | 0.97-1.08 | 0.979 | 5 |   noise |
| stod 800 digits                     | 111.6 | 111.5 |     1.002x | 0.91-1.04 | 1.027 | 5 |   noise |
| stof 1.234-like (short)             |  48.2 |  47.3 |     1.006x | 0.97-1.05 | 0.998 | 5 |   noise |
| stof 9 digits                       |  43.2 |  43.5 |     1.007x | 0.98-1.01 | 0.993 | 5 |   noise |
| stof 25-40 digits                   | 111.0 | 108.9 |     1.002x | 0.99-1.12 | 1.042 | 5 |   noise |
| stod " 1.5" (white space)           |  42.6 |  44.2 |     0.947x | 0.91-0.98 | 0.986 | 5 |  slower |
| stod inf, nan                       |  31.4 |  33.0 |     0.932x | 0.90-1.01 | 1.040 | 5 |  slower |
| stod near DBL_MAX                   |  54.8 |  55.1 |     0.995x | 0.86-1.01 | 0.983 | 5 |   noise |
| stof " 1.5" (white space)           |  49.1 |  49.3 |     1.017x | 0.96-1.15 | 0.994 | 5 |   noise |
| stof inf, nan                       |  32.6 |  32.1 |     1.003x | 1.00-1.02 | 0.997 | 5 |   noise |
| stof near FLT_MAX                   |  51.0 |  51.3 |     0.994x | 0.98-1.04 | 0.986 | 5 |   noise |
| stod exact ties 2^52..2^53 + .5     | 118.7 | 120.6 |     0.978x | 0.92-1.01 | 0.993 | 5 |   noise |
| stod odd integers 2^53..2^54 (ties) |  33.2 |  34.0 |     0.988x | 0.95-1.02 | 1.009 | 5 |   noise |
| stod subnormal (ERANGE)             |  53.3 |  54.2 |     0.994x | 0.95-1.02 | 1.017 | 5 |   noise |
| stod overflow, underflow (ERANGE)   |  50.2 |  52.3 |     0.959x | 0.92-0.98 | 0.982 | 5 |  slower |
| stof odd integers 2^24..2^25 (ties) |  72.7 |  74.2 |     0.987x | 0.94-1.01 | 0.980 | 5 |   noise |
| stof subnormal (ERANGE)             | 139.5 | 141.3 |     0.976x | 0.93-1.04 | 1.001 | 5 |   noise |
| stof overflow (ERANGE)              |  48.6 |  50.1 |     0.960x | 0.94-1.02 | 0.990 | 5 |  slower |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.981 over 34 rows (min 0.932 stod inf, nan; max 1.022 stod 1.5e-7-like)
per-run geomean: min 0.974, median 0.983, max 0.987 over 5 runs
A/A geomean 0.999

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- `stod` of 800 digits (M4 0.509, i9 0.429): not comparable. Start parsed only the first 63
  bytes; head parses all 800 and returns the right value.
- Declined text, which tries the fast path and then calls `strto*`: `inf, nan` (M4 0.808 and 0.825,
  i9 0.734 and 0.761), `" 1.5"` with leading space (M4 0.828 and 0.833, i9 0.820 and 0.854), `stoll`
  of 20 digits, `ERANGE` (M4 0.861, i9 0.881): accepted in `docs/perf/`. Fix in progress.
- i9 `stod` of odd integers between 2^53 and 2^54 (ties) 0.821: open, i9 only. Fix in progress.
