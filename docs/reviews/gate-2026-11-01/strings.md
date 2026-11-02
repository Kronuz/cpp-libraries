# strings: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/strings#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `62fb121 2026-10-28 04:53:11 -0700 Credit Germán Méndez Bravo and bound Dubalu's years`
- HEAD: `cc0359b 2026-11-01 06:02:22 -0800 Shape the README to the family standard [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `strings.hh`, `strings.cc`; each side with the dependency pins its own CMakeLists names: START char-classify `306ecd9` + repr `0fe9a1e`, HEAD char-classify `a890496` + repr `b47e947`; split `aa9857a`, static-string `eb1efcb`, term-color `534e309` on both
- Bench source: bench/bench.cc (HEAD), with `test/strings_old.hh` (frozen original of join, upper, lower, replace)
- Rows dropped because the API is new since START: none
- Metric: column `new` (the library); `old` (the frozen original) is the anchor
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -I w/strings-{start|head} -I w/repr-{p0fe|pb47} -I w/char-classify-{p306|pa89} -I w/split-paa9 -I w/static-string-peb1 -I w/term-color-p534 -I w/strings-head/test w/strings-head/bench/bench.cc w/strings-{start|head}/strings.cc w/repr-{p0fe|pb47}/repr.cc`
- Raw per-round outputs: `$GATE/raw/strings/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 68 | 2.096 | 2.078-2.106 | 1.000 | 4 | 0.880 join(vector<string>) 4 |
| Intel i9-9980HK | 68 | 1.665 | 1.662-1.682 | 1.002 | 1 | 0.893 join(vector<string>) 2 |

**Verdict: SLOWER-ROWS (4 on the Apple M4 Pro, 1 on the Intel i9-9980HK)**; geomean 2.096 / 1.665 (Apple M4 Pro / Intel i9-9980HK).

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: 4
  - `join(vector<string>) 4`: 0.880 (round range 0.81-0.92, A/A deviation 0.039). same as `join` of 2: listed in CHANGELOG 2026-11-01 (0.94 on the M4 there; 0.88 here, the frozen original in the same binary does not move).
  - `join(vector<string>) 2`: 0.920 (round range 0.90-0.94, A/A deviation 0.011). CHANGELOG 2026-11-01 lists `join` of 2 to 4 short strings among the rows left under 0.97 (M4 0.94/0.99/1.00, i9 0.95/0.97/0.96): the original's append behind a test of the count and the first element's size, kept from the audit fix; this build measures it lower on the M4 (the frozen original in the same binary does not move, 0.98-1.00), so the size of the gap is not in the changelog.
  - `join(vector<string>) 3`: 0.934 (round range 0.91-0.96, A/A deviation 0.038). same as `join` of 2: listed in CHANGELOG 2026-11-01 (0.99 on the M4 there).
  - `replace 1->3, 256 B, 3 matches`: 0.944 (round range 0.92-0.97, A/A deviation 0.041). CHANGELOG 2026-11-01 lists `replace` of 256 B with 2 and 3 matches among the rows under 0.97 (M4 0.97 at one match; i9 0.95/0.96 at 3 and 2 matches): one out-of-line copy of eight paths where the original's few lines inline into the call site; 0.5 to 2 ns.
- Intel i9-9980HK: 1
  - `join(vector<string>) 2`: 0.893 (round range 0.88-0.91, A/A deviation 0.048). CHANGELOG 2026-11-01 lists `join` of 2 to 4 short strings among the rows left under 0.97 (M4 0.94/0.99/1.00, i9 0.95/0.97/0.96): the original's append behind a test of the count and the first element's size, kept from the audit fix; this build measures it lower on the M4 (the frozen original in the same binary does not move, 0.98-1.00), so the size of the gap is not in the changelog.

## Notes

- The frozen original in the bench (`old` column, `test/strings_old.hh`) is compiled into both binaries from the same source, so its ratio (anchor column) measures the build, not the library. On the M4 the anchor is flat (five rows differ by 1% to 4%). On the i9 eleven anchor rows move by 7% to 33% with identical source (`lower` 2, 4, 8 B, 256 B and 4 KB, `upper` 8 B and 4 KB, `replace` 1->3 of 256 B with 1 and 3 matches, `inplace_upper` 4 KB), which is code placement and inlining between two compilations of the bench; library-column rows of those kinds carry that much doubt on the i9. The flagged rows are not among them: their anchors are 0.97 to 1.00 (M4 join 2, 3, 4 and replace with 3 matches 0.979, 0.970, 0.997, 0.983; i9 join 2 1.000).
- The gate's table has 68 rows, all of HEAD's bench; none is dropped. START and HEAD each use the dependencies their own CMakeLists pins (START: char-classify `306ecd9`, repr `0fe9a1e`; HEAD: char-classify `a890496`, repr `b47e947`), so `repr` / `chars` are not the same code on the two sides (only `lower`/`upper`/`join`/`replace` are timed).
- Correctness changes since START that do more work: `replace` copies a search or replacement that views into the string being edited, and `indent`, `hasupper` and `inplace_replace` handle an empty search (CHANGELOG 2026-10-31). No bench row uses an aliasing view or an empty search, so no row is made incomparable.
- The slowest rows are the ones the CHANGELOG (2026-11-01) lists as left under 0.97. The same bench in the CHANGELOG was run by CI builds; these are builds made here with the commands above, so the magnitudes differ by a few percent.

## Apple M4 Pro: per-row results (library column)

| row                                     |   START |   HEAD | START/HEAD |       range |   A/A | n | verdict |
| --------------------------------------- | ------: | -----: | ---------: | ----------: | ----: | : | ------: |
| lower(string_view) 1 B                  |    2.30 |   2.30 |     1.000x |   0.96-1.00 | 1.000 | 5 |   noise |
| upper(string_view) 1 B                  |    2.30 |   2.30 |     1.000x |   1.00-1.00 | 1.000 | 5 |   noise |
| inplace_lower 1 B                       |    2.70 |   2.00 |     1.350x |   1.30-1.60 | 0.929 | 5 |  faster |
| inplace_upper 1 B                       |    2.70 |   2.00 |     1.350x |   1.30-1.40 | 1.000 | 5 |  faster |
| lower(string_view) 2 B                  |    2.80 |   2.80 |     1.000x |   0.97-1.04 | 1.000 | 5 |   noise |
| upper(string_view) 2 B                  |    2.80 |   2.80 |     1.000x |   0.97-1.00 | 1.000 | 5 |   noise |
| inplace_lower 2 B                       |    4.50 |   3.40 |     1.324x |   1.24-1.32 | 1.000 | 5 |  faster |
| inplace_upper 2 B                       |    4.40 |   3.70 |     1.189x |   1.14-1.24 | 1.022 | 5 |  faster |
| lower(string_view) 4 B                  |    4.70 |   4.70 |     1.000x |   0.98-1.04 | 1.000 | 5 |   noise |
| upper(string_view) 4 B                  |    4.70 |   4.70 |     1.000x |   0.98-1.02 | 1.000 | 5 |   noise |
| inplace_lower 4 B                       |    4.60 |   3.40 |     1.353x |   1.31-1.41 | 1.000 | 5 |  faster |
| inplace_upper 4 B                       |    4.60 |   3.80 |     1.211x |   1.15-1.24 | 1.000 | 5 |  faster |
| lower(string_view) 8 B                  |    9.00 |   3.30 |     2.727x |   2.62-2.73 | 1.011 | 5 |  faster |
| upper(string_view) 8 B                  |    8.90 |   3.30 |     2.667x |   2.65-2.73 | 1.000 | 5 |  faster |
| inplace_lower 8 B                       |    6.10 |   2.80 |     2.143x |   1.71-2.30 | 1.017 | 5 |  faster |
| inplace_upper 8 B                       |    5.80 |   2.80 |     2.103x |   2.00-2.31 | 0.967 | 5 |  faster |
| lower(string_view) 16 B                 |    20.7 |   4.60 |     4.500x |   4.43-4.70 | 0.990 | 5 |  faster |
| upper(string_view) 16 B                 |    20.8 |   4.50 |     4.727x |   4.50-4.73 | 1.005 | 5 |  faster |
| inplace_lower 16 B                      |    8.00 |   2.80 |     2.857x |   2.82-3.00 | 0.988 | 5 |  faster |
| inplace_upper 16 B                      |    8.10 |   2.70 |     2.963x |   2.89-3.00 | 1.000 | 5 |  faster |
| lower(string_view) 32 B                 |    76.5 |   18.2 |     4.203x |   4.05-4.29 | 1.000 | 5 |  faster |
| upper(string_view) 32 B                 |    76.5 |   18.3 |     4.164x |   4.10-4.41 | 1.004 | 5 |  faster |
| inplace_lower 32 B                      |    10.1 |   3.70 |     2.703x |   2.66-3.16 | 1.010 | 5 |  faster |
| inplace_upper 32 B                      |    10.1 |   3.40 |     2.971x |   2.70-3.12 | 1.010 | 5 |  faster |
| lower(string_view) 256 B                |   566.5 |   23.7 |    23.713x | 23.42-24.11 | 0.999 | 5 |  faster |
| upper(string_view) 256 B                |   567.2 |   23.2 |    24.545x | 23.79-24.75 | 1.009 | 5 |  faster |
| inplace_lower 256 B                     |    80.8 |   6.80 |    11.910x | 11.68-11.93 | 0.995 | 5 |  faster |
| inplace_upper 256 B                     |    80.3 |   6.80 |    11.809x | 11.72-12.09 | 1.000 | 5 |  faster |
| lower(string_view) 4096 B               |  7885.3 |  127.8 |    61.745x | 60.91-68.27 | 0.995 | 5 |  faster |
| upper(string_view) 4096 B               |  7925.9 |  127.4 |    61.821x | 57.98-64.70 | 1.002 | 5 |  faster |
| inplace_lower 4096 B                    |  1073.8 |   69.1 |    15.517x | 15.37-16.14 | 0.997 | 5 |  faster |
| inplace_upper 4096 B                    |  1074.4 |   68.6 |    15.652x | 15.45-15.82 | 1.001 | 5 |  faster |
| join(vector<string>) 1                  |    5.00 |   4.80 |     1.042x |   1.02-1.06 | 1.000 | 5 |  faster |
| join(vector<int>) 1                     |    11.4 |   7.30 |     1.589x |   1.52-1.60 | 0.991 | 5 |  faster |
| join(vector<string>) 2                  |    9.20 |   10.0 |     0.920x |   0.90-0.94 | 1.011 | 5 |  slower |
| join(vector<int>) 2                     |    24.1 |   15.0 |     1.623x |   1.53-1.66 | 1.017 | 5 |  faster |
| join(vector<string>) 3                  |    28.1 |   30.1 |     0.934x |   0.91-0.96 | 1.018 | 5 |  slower |
| join(vector<int>) 3                     |    36.1 |   24.3 |     1.456x |   1.40-1.61 | 0.989 | 5 |  faster |
| join(vector<string>) 4                  |    32.1 |   36.3 |     0.880x |   0.81-0.92 | 1.022 | 5 |  slower |
| join(vector<int>) 4                     |    68.4 |   50.5 |     1.347x |   1.28-1.39 | 1.012 | 5 |  faster |
| join(vector<string>) 10                 |    78.6 |   61.6 |     1.274x |   1.24-1.30 | 1.014 | 5 |  faster |
| join(vector<int>) 10                    |   172.2 |  121.5 |     1.444x |   1.39-1.46 | 1.011 | 5 |  faster |
| join(vector<string>, pred) 10           |   101.4 |   71.2 |     1.424x |   1.36-1.53 | 0.994 | 5 |  faster |
| join(vector<string>) 1000               |  5086.3 | 4869.6 |     1.028x |   1.01-1.09 | 0.999 | 5 |  faster |
| join(vector<int>) 1000                  | 13478.4 | 8701.5 |     1.554x |   1.54-1.60 | 1.003 | 5 |  faster |
| join(vector<string>, pred) 1000         |  5489.0 | 4726.8 |     1.162x |   1.11-1.23 | 0.998 | 5 |  faster |
| join(vector<string>) 1 x 60 B           |    17.8 |   17.9 |     0.994x |   0.97-1.02 | 0.989 | 5 |   noise |
| join(vector<string>) 2 x 60 B           |    40.5 |   25.7 |     1.607x |   1.52-1.66 | 0.990 | 5 |  faster |
| join(vector<string>) 3 x 60 B           |    58.5 |   32.5 |     1.840x |   1.75-1.95 | 0.998 | 5 |  faster |
| replace 1->3, 16 B, 2 matches           |    28.5 |   28.8 |     0.990x |   0.94-1.00 | 1.032 | 5 |   noise |
| replace 1->3, 32 B, 4 matches           |    83.4 |   85.9 |     0.983x |   0.93-1.04 | 0.993 | 5 |   noise |
| replace 1->3, 256 B, 64 matches         |   938.6 |  604.2 |     1.546x |   1.53-1.59 | 0.995 | 5 |  faster |
| replace 1->3, 256 B, 16 matches         |   252.7 |  162.1 |     1.571x |   1.53-1.58 | 1.002 | 5 |  faster |
| replace 1->3, 256 B, 3 matches          |    64.1 |   68.1 |     0.944x |   0.92-0.97 | 0.997 | 5 |  slower |
| replace 1->3, 256 B, 2 matches          |    52.7 |   54.1 |     0.976x |   0.93-1.00 | 0.998 | 5 |   noise |
| replace 1->3, 256 B, 1 match            |    39.2 |   38.6 |     1.008x |   0.98-1.04 | 0.987 | 5 |   noise |
| replace 1->3, 256 B, no match           |    27.6 |   28.3 |     0.975x |   0.97-1.01 | 0.986 | 5 |  slower |
| replace 1->3, 4 KB, 1024 matches        | 35685.2 | 8056.6 |     4.426x |   4.38-4.55 | 1.005 | 5 |  faster |
| replace 1->3, 4 KB, 1 match             |   182.4 |  180.5 |     1.006x |   1.00-1.03 | 0.992 | 5 |   noise |
| replace 1->1, 256 B, 16 matches         |   144.1 |  115.8 |     1.234x |   1.22-1.28 | 0.994 | 5 |  faster |
| replace 1->1, 256 B, 64 matches         |   489.3 |  413.0 |     1.185x |   1.17-1.21 | 1.005 | 5 |  faster |
| replace 3->1, 256 B, 64 matches         |   754.4 |  495.0 |     1.525x |   1.50-1.54 | 0.996 | 5 |  faster |
| replace 3->1, 256 B, 2 matches          |    49.8 |   51.1 |     0.990x |   0.97-1.01 | 0.992 | 5 |   noise |
| replace 3->1, 4 KB, 1024 matches        | 31099.1 | 7355.1 |     4.216x |   4.21-4.34 | 1.001 | 5 |  faster |
| replace 3->0, 256 B, 64 matches         |   746.1 |  496.7 |     1.524x |   1.49-1.55 | 1.011 | 5 |  faster |
| replace 2->5, 256 B, 32 matches         |   475.8 |  305.4 |     1.560x |   1.55-1.61 | 1.015 | 5 |  faster |
| inplace_replace 1->3, 256 B, 64 matches |   765.8 |  556.3 |     1.372x |   1.35-1.39 | 1.004 | 5 |  faster |
| inplace_replace 3->1, 256 B, 64 matches |   691.3 |  471.8 |     1.464x |   1.43-1.49 | 0.995 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 2.096 over 68 rows (min 0.880 join(vector<string>) 4; max 61.821 upper(string_view) 4096 B)
per-run geomean: min 2.078, median 2.100, max 2.106 over 5 runs
A/A geomean 1.000

### Apple M4 Pro: anchor column (code that is the same in both builds; ratio should be 1)

| row                                     |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| lower(string_view) 1 B                  |    2.30 |    2.30 |     1.000x | 0.96-1.00 | 1.000 | 5 |   noise |
| upper(string_view) 1 B                  |    2.30 |    2.30 |     1.000x | 0.96-1.00 | 1.000 | 5 |   noise |
| inplace_lower 1 B                       |    2.80 |    2.70 |     1.037x | 0.93-1.19 | 1.071 | 5 |   noise |
| inplace_upper 1 B                       |    2.80 |    2.90 |     0.966x | 0.82-1.11 | 0.933 | 5 |   noise |
| lower(string_view) 2 B                  |    2.80 |    2.80 |     1.000x | 1.00-1.00 | 1.000 | 5 |   noise |
| upper(string_view) 2 B                  |    2.80 |    2.80 |     1.000x | 0.97-1.00 | 1.000 | 5 |   noise |
| inplace_lower 2 B                       |    4.40 |    4.40 |     1.000x | 0.98-1.05 | 1.047 | 5 |   noise |
| inplace_upper 2 B                       |    4.50 |    4.50 |     1.000x | 0.93-1.07 | 1.000 | 5 |   noise |
| lower(string_view) 4 B                  |    4.70 |    4.70 |     0.979x | 0.98-1.00 | 0.979 | 5 |   noise |
| upper(string_view) 4 B                  |    4.70 |    4.70 |     1.000x | 0.98-1.04 | 1.000 | 5 |   noise |
| inplace_lower 4 B                       |    4.60 |    4.70 |     0.979x | 0.96-1.00 | 1.000 | 5 |   noise |
| inplace_upper 4 B                       |    4.60 |    4.60 |     1.000x | 0.96-1.00 | 1.000 | 5 |   noise |
| lower(string_view) 8 B                  |    8.90 |    8.90 |     1.000x | 0.99-1.00 | 1.000 | 5 |   noise |
| upper(string_view) 8 B                  |    8.90 |    9.00 |     0.989x | 0.98-1.00 | 1.000 | 5 |   noise |
| inplace_lower 8 B                       |    6.00 |    6.10 |     1.000x | 0.97-1.03 | 1.000 | 5 |   noise |
| inplace_upper 8 B                       |    5.90 |    6.00 |     0.983x | 0.95-1.02 | 0.967 | 5 |   noise |
| lower(string_view) 16 B                 |    20.8 |    20.9 |     0.995x | 0.99-1.00 | 1.000 | 5 |   noise |
| upper(string_view) 16 B                 |    20.8 |    20.8 |     0.995x | 0.99-1.01 | 0.991 | 5 |   noise |
| inplace_lower 16 B                      |    8.10 |    8.20 |     0.988x | 0.95-1.04 | 0.988 | 5 |   noise |
| inplace_upper 16 B                      |    8.00 |    8.10 |     0.988x | 0.97-1.03 | 1.012 | 5 |   noise |
| lower(string_view) 32 B                 |    75.8 |    76.6 |     0.988x | 0.98-1.03 | 0.990 | 5 |   noise |
| upper(string_view) 32 B                 |    76.2 |    77.7 |     0.983x | 0.97-0.99 | 1.004 | 5 |  slower |
| inplace_lower 32 B                      |    10.0 |    10.1 |     0.990x | 0.98-1.03 | 0.990 | 5 |   noise |
| inplace_upper 32 B                      |    10.1 |    10.1 |     1.000x | 0.99-1.01 | 1.000 | 5 |   noise |
| lower(string_view) 256 B                |   565.2 |   565.8 |     0.998x | 0.99-1.01 | 1.001 | 5 |   noise |
| upper(string_view) 256 B                |   565.1 |   564.1 |     0.994x | 0.99-1.01 | 0.999 | 5 |   noise |
| inplace_lower 256 B                     |    80.0 |    80.3 |     0.996x | 0.99-1.02 | 0.994 | 5 |   noise |
| inplace_upper 256 B                     |    80.7 |    81.1 |     0.998x | 0.99-1.01 | 0.999 | 5 |   noise |
| lower(string_view) 4096 B               |  7886.0 |  7924.4 |     0.993x | 0.99-1.00 | 1.002 | 5 |   noise |
| upper(string_view) 4096 B               |  7912.8 |  7884.4 |     1.004x | 1.00-1.01 | 1.002 | 5 |   noise |
| inplace_lower 4096 B                    |  1079.3 |  1075.8 |     1.000x | 1.00-1.00 | 0.998 | 5 |   noise |
| inplace_upper 4096 B                    |  1081.9 |  1083.1 |     0.999x | 0.98-1.02 | 1.000 | 5 |   noise |
| join(vector<string>) 1                  |    5.00 |    5.10 |     0.980x | 0.94-1.00 | 1.000 | 5 |   noise |
| join(vector<int>) 1                     |    11.6 |    11.7 |     0.983x | 0.97-1.01 | 0.983 | 5 |   noise |
| join(vector<string>) 2                  |    9.20 |    9.40 |     0.979x | 0.96-1.00 | 0.989 | 5 |  slower |
| join(vector<int>) 2                     |    24.2 |    23.8 |     1.029x | 0.97-1.04 | 1.017 | 5 |  faster |
| join(vector<string>) 3                  |    29.0 |    29.2 |     0.970x | 0.94-1.05 | 1.025 | 5 |   noise |
| join(vector<int>) 3                     |    37.5 |    36.4 |     1.022x | 0.99-1.09 | 1.011 | 5 |   noise |
| join(vector<string>) 4                  |    32.5 |    32.6 |     0.997x | 0.97-1.06 | 1.025 | 5 |   noise |
| join(vector<int>) 4                     |    67.2 |    67.4 |     1.000x | 0.98-1.01 | 1.000 | 5 |   noise |
| join(vector<string>) 10                 |    77.8 |    80.0 |     0.990x | 0.95-1.04 | 1.014 | 5 |   noise |
| join(vector<int>) 10                    |   168.2 |   170.2 |     0.990x | 0.97-1.03 | 0.991 | 5 |   noise |
| join(vector<string>, pred) 10           |   130.6 |   126.6 |     1.007x | 0.97-1.06 | 0.989 | 5 |   noise |
| join(vector<string>) 1000               |  5031.4 |  5080.8 |     0.990x | 0.98-1.00 | 0.993 | 5 |   noise |
| join(vector<int>) 1000                  | 13353.5 | 13289.5 |     0.995x | 0.99-1.02 | 0.995 | 5 |   noise |
| join(vector<string>, pred) 1000         |  8689.4 |  8586.3 |     1.007x | 1.00-1.04 | 1.011 | 5 |   noise |
| join(vector<string>) 1 x 60 B           |    17.6 |    18.2 |     0.983x | 0.96-1.01 | 1.000 | 5 |   noise |
| join(vector<string>) 2 x 60 B           |    39.7 |    40.9 |     0.976x | 0.93-1.05 | 0.974 | 5 |   noise |
| join(vector<string>) 3 x 60 B           |    58.6 |    60.3 |     0.982x | 0.96-1.01 | 0.983 | 5 |   noise |
| replace 1->3, 16 B, 2 matches           |    28.0 |    29.2 |     0.962x | 0.90-0.99 | 0.979 | 5 |   noise |
| replace 1->3, 32 B, 4 matches           |    83.7 |    85.8 |     0.986x | 0.95-1.01 | 1.012 | 5 |   noise |
| replace 1->3, 256 B, 64 matches         |   938.9 |   933.4 |     0.996x | 0.99-1.03 | 0.989 | 5 |   noise |
| replace 1->3, 256 B, 16 matches         |   250.4 |   258.7 |     0.973x | 0.95-1.04 | 1.010 | 5 |   noise |
| replace 1->3, 256 B, 3 matches          |    63.9 |    65.4 |     0.983x | 0.97-1.04 | 0.997 | 5 |   noise |
| replace 1->3, 256 B, 2 matches          |    52.8 |    52.9 |     0.992x | 0.98-1.03 | 1.030 | 5 |   noise |
| replace 1->3, 256 B, 1 match            |    39.7 |    39.1 |     1.008x | 1.01-1.03 | 1.015 | 5 |   noise |
| replace 1->3, 256 B, no match           |    27.9 |    27.9 |     0.996x | 0.98-1.03 | 1.004 | 5 |   noise |
| replace 1->3, 4 KB, 1024 matches        | 35839.3 | 35411.3 |     1.010x | 1.01-1.01 | 1.008 | 5 |   noise |
| replace 1->3, 4 KB, 1 match             |   181.0 |   182.8 |     0.989x | 0.99-1.02 | 0.990 | 5 |   noise |
| replace 1->1, 256 B, 16 matches         |   144.0 |   149.4 |     0.968x | 0.95-0.98 | 1.003 | 5 |  slower |
| replace 1->1, 256 B, 64 matches         |   482.2 |   506.8 |     0.959x | 0.95-1.00 | 1.010 | 5 |  slower |
| replace 3->1, 256 B, 64 matches         |   759.8 |   766.0 |     1.003x | 0.96-1.01 | 1.016 | 5 |   noise |
| replace 3->1, 256 B, 2 matches          |    51.7 |    51.6 |     1.002x | 0.97-1.02 | 1.016 | 5 |   noise |
| replace 3->1, 4 KB, 1024 matches        | 31114.0 | 31132.7 |     1.005x | 0.99-1.01 | 0.998 | 5 |   noise |
| replace 3->0, 256 B, 64 matches         |   737.3 |   751.7 |     0.983x | 0.94-1.04 | 1.020 | 5 |   noise |
| replace 2->5, 256 B, 32 matches         |   474.3 |   485.3 |     0.984x | 0.95-1.00 | 1.011 | 5 |   noise |
| inplace_replace 1->3, 256 B, 64 matches |   761.7 |   766.2 |     1.003x | 0.99-1.02 | 1.004 | 5 |   noise |
| inplace_replace 3->1, 256 B, 64 matches |   690.3 |   684.9 |     1.002x | 0.99-1.02 | 1.007 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.993 over 68 rows (min 0.959 replace 1->1, 256 B, 64 matches; max 1.037 inplace_lower 1 B)
per-run geomean: min 0.988, median 0.994, max 1.001 over 5 runs
A/A geomean 1.001

## Intel i9-9980HK: per-row results (library column)

| row                                     |   START |    HEAD | START/HEAD |       range |   A/A | n | verdict |
| --------------------------------------- | ------: | ------: | ---------: | ----------: | ----: | : | ------: |
| lower(string_view) 1 B                  |    7.30 |    6.80 |     1.075x |   1.04-1.25 | 1.028 | 5 |   noise |
| upper(string_view) 1 B                  |    7.10 |    6.90 |     1.029x |   1.00-1.12 | 1.014 | 5 |   noise |
| inplace_lower 1 B                       |    6.80 |    6.20 |     1.066x |   1.05-1.29 | 1.000 | 5 |   noise |
| inplace_upper 1 B                       |    6.90 |    6.30 |     1.063x |   0.97-1.25 | 1.015 | 5 |   noise |
| lower(string_view) 2 B                  |    9.30 |    8.70 |     1.068x |   0.97-1.27 | 1.000 | 5 |  faster |
| upper(string_view) 2 B                  |    8.80 |    7.80 |     1.158x |   0.98-1.29 | 1.000 | 5 |  faster |
| inplace_lower 2 B                       |    7.10 |    6.60 |     1.046x |   0.96-1.18 | 1.014 | 5 |   noise |
| inplace_upper 2 B                       |    7.10 |    6.50 |     1.046x |   0.97-1.25 | 1.000 | 5 |   noise |
| lower(string_view) 4 B                  |    13.4 |    12.6 |     1.072x |   0.98-1.18 | 0.985 | 5 |   noise |
| upper(string_view) 4 B                  |    13.0 |    10.3 |     1.300x |   1.17-1.39 | 1.008 | 5 |  faster |
| inplace_lower 4 B                       |    7.40 |    6.80 |     1.103x |   0.97-1.12 | 1.013 | 5 |   noise |
| inplace_upper 4 B                       |    7.50 |    7.20 |     1.056x |   1.01-1.21 | 0.987 | 5 |   noise |
| lower(string_view) 8 B                  |    22.1 |    11.5 |     1.922x |   1.69-2.11 | 0.995 | 5 |  faster |
| upper(string_view) 8 B                  |    21.7 |    11.3 |     1.920x |   1.84-2.04 | 1.019 | 5 |  faster |
| inplace_lower 8 B                       |    11.0 |    10.6 |     1.037x |   1.00-1.16 | 1.009 | 5 |   noise |
| inplace_upper 8 B                       |    11.1 |    10.6 |     1.048x |   0.92-1.21 | 1.018 | 5 |   noise |
| lower(string_view) 16 B                 |    40.7 |    12.7 |     3.230x |   3.10-3.43 | 1.007 | 5 |  faster |
| upper(string_view) 16 B                 |    40.9 |    11.9 |     3.437x |   3.28-3.61 | 1.050 | 5 |  faster |
| inplace_lower 16 B                      |    14.6 |    10.5 |     1.415x |   1.35-1.49 | 1.007 | 5 |  faster |
| inplace_upper 16 B                      |    14.8 |    10.4 |     1.413x |   1.37-1.62 | 1.000 | 5 |  faster |
| lower(string_view) 32 B                 |   110.8 |    53.0 |     2.157x |   1.98-2.18 | 0.992 | 5 |  faster |
| upper(string_view) 32 B                 |   108.7 |    52.5 |     2.083x |   1.85-2.41 | 1.017 | 5 |  faster |
| inplace_lower 32 B                      |    15.5 |    8.00 |     1.890x |   1.80-2.04 | 0.994 | 5 |  faster |
| inplace_upper 32 B                      |    15.6 |    8.00 |     1.902x |   1.76-2.06 | 1.006 | 5 |  faster |
| lower(string_view) 256 B                |   708.0 |   110.3 |     6.556x |   5.62-6.88 | 1.003 | 5 |  faster |
| upper(string_view) 256 B                |   748.0 |   118.1 |     6.334x |   5.61-7.31 | 1.001 | 5 |  faster |
| inplace_lower 256 B                     |    72.8 |    16.3 |     4.466x |   4.35-4.53 | 1.010 | 5 |  faster |
| inplace_upper 256 B                     |    73.3 |    16.5 |     4.312x |   4.26-4.65 | 0.985 | 5 |  faster |
| lower(string_view) 4096 B               |  7849.8 |   253.7 |    30.869x | 30.33-33.55 | 0.993 | 5 |  faster |
| upper(string_view) 4096 B               |  8902.8 |   253.8 |    35.421x | 34.40-36.29 | 0.986 | 5 |  faster |
| inplace_lower 4096 B                    |  1055.9 |   166.3 |     6.288x |   6.20-6.76 | 0.976 | 5 |  faster |
| inplace_upper 4096 B                    |  1056.5 |   167.7 |     6.259x |   5.85-6.70 | 0.992 | 5 |  faster |
| join(vector<string>) 1                  |    12.9 |    12.1 |     1.059x |   1.00-1.28 | 0.985 | 5 |   noise |
| join(vector<int>) 1                     |    28.0 |    20.6 |     1.320x |   1.28-1.53 | 1.011 | 5 |  faster |
| join(vector<string>) 2                  |    20.6 |    22.9 |     0.893x |   0.88-0.91 | 0.985 | 5 |  slower |
| join(vector<int>) 2                     |    52.1 |    36.4 |     1.424x |   1.35-1.48 | 0.987 | 5 |  faster |
| join(vector<string>) 3                  |    70.0 |    71.6 |     0.978x |   0.90-1.05 | 0.984 | 5 |   noise |
| join(vector<int>) 3                     |    78.7 |    53.7 |     1.460x |   1.36-1.59 | 1.012 | 5 |  faster |
| join(vector<string>) 4                  |    78.0 |    82.4 |     0.979x |   0.93-1.00 | 0.983 | 5 |   noise |
| join(vector<int>) 4                     |   151.4 |   118.1 |     1.279x |   1.24-1.36 | 0.984 | 5 |  faster |
| join(vector<string>) 10                 |   175.1 |   136.4 |     1.288x |   1.11-1.36 | 0.970 | 5 |  faster |
| join(vector<int>) 10                    |   382.8 |   299.0 |     1.280x |   1.19-1.54 | 1.009 | 5 |  faster |
| join(vector<string>, pred) 10           |   222.0 |   176.4 |     1.245x |   1.09-1.29 | 0.997 | 5 |  faster |
| join(vector<string>) 1000               | 10431.1 |  9830.0 |     1.089x |   1.02-1.15 | 1.005 | 5 |  faster |
| join(vector<int>) 1000                  | 28184.8 | 18126.1 |     1.555x |   1.50-1.60 | 1.021 | 5 |  faster |
| join(vector<string>, pred) 1000         | 11906.1 | 10119.5 |     1.177x |   1.14-1.23 | 1.015 | 5 |  faster |
| join(vector<string>) 1 x 60 B           |    51.2 |    53.5 |     0.966x |   0.86-1.01 | 0.994 | 5 |   noise |
| join(vector<string>) 2 x 60 B           |   100.6 |    61.4 |     1.624x |   1.56-1.88 | 1.022 | 5 |  faster |
| join(vector<string>) 3 x 60 B           |   153.3 |    67.3 |     2.298x |   2.22-2.76 | 1.019 | 5 |  faster |
| replace 1->3, 16 B, 2 matches           |    60.0 |    62.1 |     0.966x |   0.91-0.98 | 0.980 | 5 |   noise |
| replace 1->3, 32 B, 4 matches           |   191.2 |   196.8 |     0.973x |   0.96-1.00 | 1.016 | 5 |   noise |
| replace 1->3, 256 B, 64 matches         |  1777.5 |  1203.1 |     1.443x |   1.42-1.64 | 1.002 | 5 |  faster |
| replace 1->3, 256 B, 16 matches         |   626.0 |   483.7 |     1.293x |   1.26-1.35 | 0.985 | 5 |  faster |
| replace 1->3, 256 B, 3 matches          |   200.5 |   206.1 |     0.988x |   0.96-0.99 | 1.001 | 5 |   noise |
| replace 1->3, 256 B, 2 matches          |   181.6 |   179.9 |     1.054x |   0.97-1.07 | 1.008 | 5 |   noise |
| replace 1->3, 256 B, 1 match            |   154.5 |   141.9 |     1.089x |   0.96-1.13 | 1.012 | 5 |   noise |
| replace 1->3, 256 B, no match           |   126.8 |   119.3 |     1.082x |   0.96-1.17 | 1.002 | 5 |  faster |
| replace 1->3, 4 KB, 1024 matches        | 38710.3 | 13040.0 |     3.004x |   2.86-3.06 | 0.975 | 5 |  faster |
| replace 1->3, 4 KB, 1 match             |   182.5 |   188.1 |     0.954x |   0.86-1.02 | 1.017 | 5 |   noise |
| replace 1->1, 256 B, 16 matches         |   382.4 |   284.1 |     1.319x |   1.26-1.53 | 1.031 | 5 |  faster |
| replace 1->1, 256 B, 64 matches         |  1090.6 |   803.0 |     1.357x |   1.29-1.40 | 0.989 | 5 |  faster |
| replace 3->1, 256 B, 64 matches         |  1487.7 |   941.2 |     1.507x |   1.45-1.72 | 0.994 | 5 |  faster |
| replace 3->1, 256 B, 2 matches          |   175.5 |   154.5 |     1.132x |   1.04-1.15 | 1.005 | 5 |  faster |
| replace 3->1, 4 KB, 1024 matches        | 37464.9 | 12732.9 |     2.973x |   2.92-3.07 | 0.976 | 5 |  faster |
| replace 3->0, 256 B, 64 matches         |  1263.4 |   933.1 |     1.360x |   1.34-1.39 | 0.984 | 5 |  faster |
| replace 2->5, 256 B, 32 matches         |  1045.4 |   785.6 |     1.328x |   1.22-1.58 | 0.997 | 5 |  faster |
| inplace_replace 1->3, 256 B, 64 matches |  1319.5 |  1006.4 |     1.298x |   1.20-1.41 | 1.015 | 5 |  faster |
| inplace_replace 3->1, 256 B, 64 matches |  1108.9 |   822.6 |     1.360x |   1.22-1.37 | 1.017 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.665 over 68 rows (min 0.893 join(vector<string>) 2; max 35.421 upper(string_view) 4096 B)
per-run geomean: min 1.662, median 1.670, max 1.682 over 5 runs
A/A geomean 1.002

### Intel i9-9980HK: anchor column (code that is the same in both builds; ratio should be 1)

| row                                     |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| --------------------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| lower(string_view) 1 B                  |    7.20 |    6.60 |     1.077x | 1.06-1.26 | 1.014 | 5 |   noise |
| upper(string_view) 1 B                  |    7.30 |    7.20 |     1.014x | 0.97-1.13 | 1.086 | 5 |   noise |
| inplace_lower 1 B                       |    6.90 |    6.60 |     1.015x | 0.99-1.17 | 1.030 | 5 |   noise |
| inplace_upper 1 B                       |    6.90 |    6.70 |     1.030x | 0.93-1.17 | 1.000 | 5 |   noise |
| lower(string_view) 2 B                  |    9.00 |    8.00 |     1.125x | 1.06-1.22 | 1.024 | 5 |  faster |
| upper(string_view) 2 B                  |    8.30 |    9.10 |     0.912x | 0.84-1.07 | 1.025 | 5 |   noise |
| inplace_lower 2 B                       |    7.00 |    7.20 |     0.972x | 0.93-1.11 | 1.014 | 5 |   noise |
| inplace_upper 2 B                       |    7.20 |    7.00 |     1.000x | 0.96-1.13 | 0.986 | 5 |   noise |
| lower(string_view) 4 B                  |    13.0 |    10.2 |     1.327x | 1.21-1.38 | 1.076 | 5 |  faster |
| upper(string_view) 4 B                  |    12.6 |    13.0 |     0.977x | 0.76-0.99 | 1.047 | 5 |   noise |
| inplace_lower 4 B                       |    7.50 |    7.70 |     0.947x | 0.87-1.00 | 0.987 | 5 |   noise |
| inplace_upper 4 B                       |    7.70 |    7.90 |     0.987x | 0.95-1.07 | 1.000 | 5 |   noise |
| lower(string_view) 8 B                  |    18.6 |    16.7 |     1.102x | 0.98-1.18 | 0.979 | 5 |  faster |
| upper(string_view) 8 B                  |    19.3 |    21.9 |     0.877x | 0.83-0.92 | 1.032 | 5 |  slower |
| inplace_lower 8 B                       |    10.9 |    11.1 |     0.991x | 0.96-1.02 | 0.991 | 5 |   noise |
| inplace_upper 8 B                       |    11.0 |    10.9 |     1.009x | 0.97-1.10 | 1.000 | 5 |   noise |
| lower(string_view) 16 B                 |    33.9 |    32.8 |     1.015x | 0.95-1.04 | 1.018 | 5 |   noise |
| upper(string_view) 16 B                 |    35.8 |    40.6 |     0.893x | 0.79-0.94 | 1.034 | 5 |   noise |
| inplace_lower 16 B                      |    14.7 |    14.5 |     1.021x | 0.91-1.14 | 1.007 | 5 |   noise |
| inplace_upper 16 B                      |    15.0 |    14.6 |     1.007x | 0.93-1.11 | 1.014 | 5 |   noise |
| lower(string_view) 32 B                 |   112.8 |    98.3 |     1.102x | 1.10-1.17 | 1.060 | 5 |   noise |
| upper(string_view) 32 B                 |   109.5 |   110.0 |     0.996x | 0.88-1.05 | 1.013 | 5 |   noise |
| inplace_lower 32 B                      |    15.6 |    15.7 |     0.993x | 0.90-1.04 | 1.038 | 5 |   noise |
| inplace_upper 32 B                      |    15.5 |    14.7 |     1.000x | 0.96-1.08 | 0.994 | 5 |   noise |
| lower(string_view) 256 B                |   803.3 |   677.1 |     1.200x | 1.06-1.22 | 0.976 | 5 |  faster |
| upper(string_view) 256 B                |   710.1 |   755.6 |     0.935x | 0.91-0.99 | 1.056 | 5 |  slower |
| inplace_lower 256 B                     |    71.1 |    72.0 |     0.989x | 0.98-1.01 | 0.996 | 5 |   noise |
| inplace_upper 256 B                     |    72.2 |    71.7 |     1.007x | 0.98-1.14 | 1.024 | 5 |   noise |
| lower(string_view) 4096 B               |  9856.2 |  7612.2 |     1.280x | 1.16-1.35 | 1.014 | 5 |  faster |
| upper(string_view) 4096 B               |  7622.2 |  8794.0 |     0.866x | 0.85-0.89 | 0.988 | 5 |  slower |
| inplace_lower 4096 B                    |  1060.8 |  1060.2 |     0.990x | 0.99-1.01 | 0.985 | 5 |   noise |
| inplace_upper 4096 B                    |  1072.8 |  1073.1 |     0.977x | 0.89-1.05 | 0.999 | 5 |  slower |
| join(vector<string>) 1                  |    13.3 |    12.6 |     1.032x | 1.01-1.10 | 1.008 | 5 |   noise |
| join(vector<int>) 1                     |    27.9 |    27.0 |     1.004x | 1.00-1.09 | 0.982 | 5 |   noise |
| join(vector<string>) 2                  |    20.8 |    20.8 |     1.000x | 0.93-1.03 | 0.968 | 5 |   noise |
| join(vector<int>) 2                     |    52.7 |    53.0 |     0.991x | 0.94-1.04 | 0.981 | 5 |   noise |
| join(vector<string>) 3                  |    67.7 |    69.0 |     0.994x | 0.92-1.03 | 0.952 | 5 |   noise |
| join(vector<int>) 3                     |    78.2 |    78.3 |     1.004x | 0.87-1.13 | 0.994 | 5 |   noise |
| join(vector<string>) 4                  |    81.0 |    80.7 |     1.042x | 0.96-1.07 | 0.997 | 5 |   noise |
| join(vector<int>) 4                     |   154.3 |   153.6 |     1.005x | 0.95-1.15 | 1.008 | 5 |   noise |
| join(vector<string>) 10                 |   169.7 |   176.8 |     0.977x | 0.89-0.99 | 0.974 | 5 |   noise |
| join(vector<int>) 10                    |   384.2 |   387.6 |     0.963x | 0.87-1.16 | 0.977 | 5 |   noise |
| join(vector<string>, pred) 10           |   286.7 |   276.9 |     1.030x | 0.91-1.06 | 1.017 | 5 |   noise |
| join(vector<string>) 1000               | 10178.2 | 10607.6 |     0.951x | 0.89-1.06 | 1.001 | 5 |   noise |
| join(vector<int>) 1000                  | 27738.7 | 27297.4 |     1.011x | 0.98-1.05 | 0.987 | 5 |   noise |
| join(vector<string>, pred) 1000         | 17110.5 | 17055.0 |     0.994x | 0.94-1.05 | 0.999 | 5 |   noise |
| join(vector<string>) 1 x 60 B           |    50.0 |    51.9 |     0.977x | 0.86-0.98 | 0.986 | 5 |   noise |
| join(vector<string>) 2 x 60 B           |   103.0 |   102.6 |     1.002x | 0.93-1.04 | 1.016 | 5 |   noise |
| join(vector<string>) 3 x 60 B           |   158.4 |   163.2 |     0.930x | 0.91-1.11 | 1.009 | 5 |   noise |
| replace 1->3, 16 B, 2 matches           |    60.7 |    61.4 |     0.989x | 0.91-1.02 | 0.990 | 5 |   noise |
| replace 1->3, 32 B, 4 matches           |   193.0 |   194.0 |     1.002x | 0.95-1.07 | 1.024 | 5 |   noise |
| replace 1->3, 256 B, 64 matches         |  1770.3 |  1725.4 |     1.028x | 0.95-1.08 | 1.000 | 5 |   noise |
| replace 1->3, 256 B, 16 matches         |   636.2 |   641.1 |     0.995x | 0.90-1.03 | 1.000 | 5 |   noise |
| replace 1->3, 256 B, 3 matches          |   204.5 |   193.7 |     1.070x | 1.01-1.12 | 0.988 | 5 |  faster |
| replace 1->3, 256 B, 2 matches          |   178.5 |   167.0 |     1.076x | 1.01-1.13 | 1.018 | 5 |   noise |
| replace 1->3, 256 B, 1 match            |   160.3 |   137.1 |     1.184x | 1.03-1.23 | 0.966 | 5 |  faster |
| replace 1->3, 256 B, no match           |   131.5 |   113.8 |     1.152x | 1.10-1.24 | 1.054 | 5 |   noise |
| replace 1->3, 4 KB, 1024 matches        | 38991.6 | 38790.6 |     1.016x | 0.89-1.13 | 1.016 | 5 |   noise |
| replace 1->3, 4 KB, 1 match             |   183.0 |   178.7 |     1.004x | 0.92-1.07 | 1.019 | 5 |   noise |
| replace 1->1, 256 B, 16 matches         |   368.1 |   357.7 |     1.032x | 0.97-1.06 | 0.980 | 5 |   noise |
| replace 1->1, 256 B, 64 matches         |  1101.0 |  1086.4 |     1.007x | 0.97-1.07 | 1.020 | 5 |   noise |
| replace 3->1, 256 B, 64 matches         |  1462.4 |  1462.7 |     0.982x | 0.95-1.14 | 1.002 | 5 |   noise |
| replace 3->1, 256 B, 2 matches          |   173.7 |   163.7 |     1.102x | 1.05-1.24 | 1.122 | 5 |   noise |
| replace 3->1, 4 KB, 1024 matches        | 37463.0 | 37539.9 |     0.995x | 0.99-1.03 | 0.941 | 5 |   noise |
| replace 3->0, 256 B, 64 matches         |  1296.6 |  1212.3 |     1.053x | 1.01-1.08 | 1.005 | 5 |   noise |
| replace 2->5, 256 B, 32 matches         |  1061.7 |  1069.8 |     1.004x | 0.88-1.11 | 1.006 | 5 |   noise |
| inplace_replace 1->3, 256 B, 64 matches |  1320.2 |  1314.1 |     0.997x | 0.96-1.11 | 0.997 | 5 |   noise |
| inplace_replace 3->1, 256 B, 64 matches |  1147.2 |  1133.5 |     0.994x | 0.93-1.07 | 1.003 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.015 over 68 rows (min 0.866 upper(string_view) 4096 B; max 1.327 lower(string_view) 4 B)
per-run geomean: min 1.007, median 1.014, max 1.022 over 5 runs
A/A geomean 1.007

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- `join(vector<string>)` of 2, 3 and 4 short strings (M4 0.920, 0.934 and 0.880; i9 0.893) and
  `replace` 1 to 3 characters, 256 B, 3 matches (M4 0.944): fixed in `strings:4f7fd80`, which runs
  the original's code for small joins and a few matches. They are at parity with start; rows at 0.94
  to 0.96 move with the layout: open, [strings#2](https://github.com/Kronuz/strings/issues/2).
