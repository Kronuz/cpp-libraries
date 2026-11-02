# Gate: string-similarity (START ddfb8d1 vs HEAD 682dd2e)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/string-similarity#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

String metrics. HEAD has bit-parallel banded Levenshtein and Jaro kernels, a multiset Sorensen_Dice, and several correctness fixes (standard Jaro, a real Jaro_Winkler, PhoneticMetric encoding its operands).

**Verdict: FASTER, with one SLOWER-ROWS flag. Levenshtein is 2.4-5.0x faster on words and 50-1400x on long strings (answers identical); Jaro and Jaro-Winkler are 3-37x faster (317-417x on the 3000-character pair) and Dice 22-110x, but their answers changed on purpose (VOID rows). One control row, `Jaccard 300 chars` (kernel unchanged), is 0.75x on the i9 inside the combined benchmark binary only (1.10-1.15x faster when built alone; 0.99 on the M4): code placement, see below.**

## Machines, compiler, commands

| | Apple M4 Pro | Intel i9-9980HK |
|---|---|---|
| host | the M4 Pro, arm64, 14 cores, macOS 26.7.2 | the i9, x86_64, 8C/16T, macOS 15 |
| compiler | Apple clang 17.0.0 (clang-1700.3.19.1) | Apple clang 17.0.0 (clang-1700.6.4.2) |
| flags (both sides) | `-std=c++20 -O3 -DNDEBUG` | `-std=c++20 -O3 -DNDEBUG` |
| sessions | `quiet strict`: string-similarity at 10:55 (5 rounds + the Jaccard follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:14 (about 1 minute of timed runs in all) | `quiet strict`: string-similarity at 11:32 (5 rounds + the follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:55 (one minute of timed runs). A first i9 session (09:19, other work running) is kept as a cross-check |

Commands (per machine, from `$GATE`):

```
clang++ -std=c++20 -O3 -DNDEBUG -I. -Istring-similarity-{start,head} -Ideps/{strings,char-classify,split,static-string,repr,term-color,soundex} gate_strsim.cc -o build/<arch>/strsim-{start,head}
quiet strict 10 ... -- ./rounds.sh 5
python3 cpp-libraries/tools/ab_compare.py compare --a results/<arch>/strsim/a --b .../b --aa .../aa --output csv
```

Source: `gate_strsim.cc` + `gate_common.h`-style harness (best of 5 repeats, ns per call). The workloads (word pairs, near pairs, 300-10000 character strings, related strings, Dice sets) and row names follow `bench/bench.cc` at HEAD with the same seeds; the frozen legacy copies and rapidfuzz of that file are not linked because START's own sources are built instead. `strings` is `485f882` and `soundex` `4f192a7` (HEAD's pins) for both sides, so `strings::upper` and the encoder are the same code in both builds (START at its own date used an older `strings`; that only matters for the `icase=true` rows, which START's base class folds through `strings::upper`).

## Results

Ratio = START / HEAD (above 1: HEAD is faster). `A/A` is the largest deviation from 1 of the five paired START-against-START ratios of the same session (the noise of that row on that machine, worst round; a row is called slower only when its ratio is below 1 / (1 + A/A) and below 0.97). `VOID` marks a row whose answers differ between START and HEAD (a correctness change, see the notes): its ratio is shown but the row is outside the first geomean.

| row | M4 START | M4 HEAD | M4 ratio | M4 A/A | i9 START | i9 HEAD | i9 ratio | i9 A/A | note |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| Levenshtein random words | 106.8 ns | 37.9 ns | 2.787 | 9.4% | 295.4 ns | 78.3 ns | 3.769 | 8.2% | answers bit-identical |
| Levenshtein random words (rerun) | 93.3 ns | 37.4 ns | 2.496 | 7.3% | 294.7 ns | 81.9 ns | 3.621 | 11.6% | answers bit-identical |
| Levenshtein near words | 114.2 ns | 34.0 ns | 3.333 | 4.6% | 284.1 ns | 61.9 ns | 4.626 | 10.8% | answers bit-identical |
| Levenshtein random words icase=true | 113.5 ns | 46.2 ns | 2.428 | 13.6% | 321.6 ns | 87.8 ns | 3.696 | 14.0% | answers bit-identical |
| Levenshtein 300 chars, 4 letters | 114.02 us | 2.23 us | 51.237 | 1.4% | 336.95 us | 4.07 us | 85.600 | 6.9% | answers bit-identical |
| Levenshtein 3000 chars, 4 letters | 11.76 ms | 95.37 us | 122.923 | 1.5% | 33.88 ms | 180.17 us | 186.211 | 5.0% | answers bit-identical |
| Levenshtein 3000 chars, ~1% edits | 11.73 ms | 13.81 us | 843.010 | 1.3% | 13.25 ms | 26.13 us | 510.476 | 5.0% | answers bit-identical |
| Levenshtein 1000 chars, 4 letters | 1.29 ms | 15.04 us | 85.605 | 1.6% | 3.80 ms | 28.26 us | 132.157 | 5.7% | answers bit-identical |
| Levenshtein 3000 chars, 26 letters | 11.66 ms | 132.62 us | 87.735 | 1.7% | 19.06 ms | 248.86 us | 75.117 | 6.7% | answers bit-identical |
| Levenshtein 3000 chars, ~1% edits (indels too) | 11.74 ms | 14.09 us | 830.762 | 2.1% | 13.68 ms | 25.89 us | 532.263 | 16.2% | answers bit-identical |
| Levenshtein 3000 chars, ~5% edits, 4 letters | 11.75 ms | 29.84 us | 393.377 | 1.8% | 26.93 ms | 56.49 us | 483.716 | 12.9% | answers bit-identical |
| Levenshtein 3000 chars, ~10% edits, 4 letters | 11.57 ms | 36.85 us | 315.270 | 1.3% | 26.54 ms | 69.71 us | 375.739 | 10.5% | answers bit-identical |
| Levenshtein 3000 vs 3100 chars, 4 letters | 12.12 ms | 103.60 us | 117.126 | 2.0% | 34.45 ms | 193.90 us | 178.033 | 5.0% | answers bit-identical |
| Levenshtein 10000 chars, 26 letters | 131.04 ms | 1.35 ms | 97.228 | 0.7% | 223.32 ms | 2.48 ms | 91.071 | 3.6% | answers bit-identical |
| Levenshtein 10000 chars, ~1% edits | 130.40 ms | 90.90 us | 1434.944 | 0.9% | 146.38 ms | 169.70 us | 860.653 | 5.6% | answers bit-identical |
| Jaro random words | 118.4 ns | 34.5 ns | 3.435 VOID | 7.5% | 324.3 ns | 65.4 ns | 5.022 VOID | 9.4% | answers changed: standard Jaro |
| Jaro_Winkler random words | 117.7 ns | 35.2 ns | 3.396 VOID | 4.0% | 326.1 ns | 68.9 ns | 4.732 VOID | 9.7% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Jaro_Winkler near words | 117.4 ns | 36.1 ns | 3.257 VOID | 4.0% | 343.6 ns | 74.0 ns | 4.532 VOID | 9.7% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Jaro_Winkler near words icase=true | 128.7 ns | 39.9 ns | 3.227 VOID | 14.0% | 373.3 ns | 80.4 ns | 4.727 VOID | 9.4% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Jaro 300 chars | 32.17 us | 1.26 us | 25.538 VOID | 2.3% | 80.13 us | 2.46 us | 33.308 VOID | 16.7% | answers changed: standard Jaro |
| Jaro 3000 chars | 3.81 ms | 12.11 us | 315.500 | 1.7% | 10.47 ms | 24.74 us | 422.230 | 6.6% | equal answers |
| Jaro 20-40 chars, 2 edits | 687.5 ns | 60.0 ns | 11.432 VOID | 3.4% | 1.43 us | 138.1 ns | 10.390 VOID | 4.4% | answers changed: standard Jaro |
| Jaro_Winkler 20-40 chars, 2 edits | 672.6 ns | 62.8 ns | 10.691 VOID | 3.7% | 1.42 us | 140.4 ns | 10.153 VOID | 8.4% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Jaro 64 chars, 1 edit | 2.00 us | 90.0 ns | 22.238 VOID | 2.3% | 3.88 us | 161.0 ns | 24.081 VOID | 5.1% | answers changed: standard Jaro |
| Jaro_Winkler 64 chars, 1 edit | 2.02 us | 90.9 ns | 21.863 VOID | 3.0% | 3.90 us | 164.7 ns | 23.704 VOID | 6.1% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Jaro 65 chars, 1 edit | 2.06 us | 92.8 ns | 22.014 VOID | 1.4% | 3.94 us | 171.6 ns | 22.892 VOID | 5.1% | answers changed: standard Jaro |
| Jaro_Winkler 65 chars, 1 edit | 2.05 us | 94.8 ns | 21.378 VOID | 3.4% | 3.90 us | 174.9 ns | 22.309 VOID | 4.9% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Jaro 129 chars, 1 edit | 7.70 us | 288.9 ns | 26.508 VOID | 1.0% | 12.59 us | 560.1 ns | 22.343 VOID | 5.0% | answers changed: standard Jaro |
| Jaro_Winkler 129 chars, 1 edit | 7.63 us | 292.2 ns | 26.070 VOID | 0.8% | 12.66 us | 570.3 ns | 21.812 VOID | 2.6% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Jaro 300 chars, 3 edits | 40.88 us | 1.12 us | 36.255 VOID | 0.8% | 53.90 us | 2.36 us | 23.274 VOID | 2.7% | answers changed: standard Jaro |
| Jaro_Winkler 300 chars, 3 edits | 40.86 us | 1.10 us | 37.185 VOID | 1.5% | 54.27 us | 2.29 us | 23.599 VOID | 3.7% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Jaro 300 chars, high bytes | 37.80 us | 2.74 us | 13.814 VOID | 1.2% | 37.41 us | 4.73 us | 7.833 VOID | 2.2% | answers changed: standard Jaro |
| Jaro_Winkler 300 chars, high bytes | 37.94 us | 2.55 us | 14.882 VOID | 1.2% | 37.03 us | 4.78 us | 7.733 VOID | 4.1% | answers changed: now a real Jaro-Winkler (START returned plain Jaro) |
| Dice 1-2 chars | 22.1 ns | 11.8 ns | 1.880 | 2.9% | 42.3 ns | 19.9 ns | 2.222 | 9.8% |  |
| Dice random words | 622.3 ns | 22.3 ns | 27.733 VOID | 4.0% | 1.32 us | 51.1 ns | 26.677 VOID | 6.0% | answers changed: bigram multiset |
| Dice near words | 578.1 ns | 24.0 ns | 24.076 VOID | 4.2% | 1.21 us | 52.6 ns | 22.599 VOID | 6.4% | answers changed: bigram multiset |
| Dice random words icase=true | 640.4 ns | 28.9 ns | 22.497 VOID | 2.5% | 1.40 us | 64.2 ns | 21.726 VOID | 5.8% | answers changed: bigram multiset |
| Dice 20-40 chars, 2 edits | 3.78 us | 46.6 ns | 80.939 VOID | 1.7% | 7.07 us | 99.7 ns | 69.181 VOID | 3.7% | answers changed: bigram multiset |
| Dice 64 chars, 4 letters | 8.66 us | 77.6 ns | 110.606 VOID | 1.4% | 15.26 us | 144.1 ns | 105.673 VOID | 2.0% | answers changed: bigram multiset |
| Dice 129 chars, 4 letters | 6.19 us | 188.0 ns | 33.371 VOID | 4.9% | 9.00 us | 249.3 ns | 36.334 VOID | 9.8% | answers changed: bigram multiset |
| Dice 300 chars, 4 letters | 14.87 us | 413.4 ns | 36.054 VOID | 3.5% | 21.04 us | 568.5 ns | 37.020 VOID | 4.5% | answers changed: bigram multiset |
| Dice 3000 chars, 4 letters | 140.28 us | 4.03 us | 34.852 VOID | 0.9% | 189.41 us | 5.44 us | 34.788 VOID | 4.8% | answers changed: bigram multiset |
| Jaccard random words | 476.6 ns | 485.6 ns | 0.996 | 2.8% | 1.14 us | 1.11 us | 1.044 | 10.3% | unchanged kernel (control) |
| LCSubstr random words | 85.6 ns | 84.0 ns | 0.947 | 16.0% | 180.5 ns | 186.2 ns | 0.978 | 4.3% | unchanged kernel (control) |
| LCSubsequence random words | 92.5 ns | 97.8 ns | 0.946 | 13.5% | 197.8 ns | 204.2 ns | 0.981 | 9.9% | unchanged kernel (control) |
| Jaccard 300 chars | 2.27 us | 2.27 us | 0.989 | 10.1% | 2.10 us | 2.66 us | 0.750 | 5.4% | unchanged kernel (control) |
| LCSubstr 300 chars | 42.84 us | 41.68 us | 1.031 | 2.5% | 66.19 us | 47.38 us | 1.378 | 7.6% | unchanged kernel (control) |
| LCSubsequence 300 chars | 49.12 us | 48.43 us | 1.014 | 3.1% | 82.30 us | 82.73 us | 0.995 | 9.0% | unchanged kernel (control) |
| PhoneticMetric<SoundexEnglish,Levenshtein> random words | 91.1 ns | 86.7 ns | 1.057 VOID | 3.2% | 276.5 ns | 176.4 ns | 1.577 VOID | 5.2% | HEAD encodes both operands; START compared the raw strings (less work) |

## Geomean (START / HEAD)

| machine | geomean, comparable rows | n | geomean, all rows (VOID included) | n |
|---|--:|--:|--:|--:|
| M4 | 20.801 | 23 | 18.696 | 49 |
| i9 | 23.165 | 23 | 19.459 | 49 |
| i9, first session (09:19, other jobs' work running, noisier) | 23.154 | 23 | 19.296 | 49 |

## Rows with ratio < 0.97 outside the A/A spread

- i9: **Jaccard 300 chars**: 0.750 (A/A 5.4%): unexplained at the instruction level, but binary-dependent, not kernel-dependent: i9 only, 0.75x inside the 49-row `gate_strsim` binary (A/A 0.99, clean session), yet 1.10-1.15x FASTER in `gate_jac.cc` (same call, same strings, five metrics in the binary); M4 0.99 and 1.06. The unchanged `LCSubstr 300 chars` moves the other way on the i9 (1.38-1.45x faster in both binaries). The Jaccard kernel and its header are unchanged (one `requires` clause), so this is code placement or inlining of an unchanged kernel in a header-only template, not extra work.

Rows below 0.97 whose ratio is inside the A/A spread (not counted above; the session cannot tell them from noise):

- M4: LCSubstr random words: 0.947 (A/A 16.0%)
- M4: LCSubsequence random words: 0.946 (A/A 13.5%)

## M4: Jaccard, LCSubstr and LCSubsequence in a process of their own (gate_jac.cc)

The same calls as the control rows above, on a fresh heap and after the long-string metrics have run, to separate the kernel from the heap state.

| row                                                |     START |    HEAD | START/HEAD |           range |   A/A | n | verdict |
| -------------------------------------------------- | --------: | ------: | ---------: | --------------: | ----: | : | ------: |
| Jaccard 300 chars, fresh heap                      |    2264.6 |  2129.8 |     1.056x |       1.03-1.08 | 1.013 | 5 |  faster |
| LCSubstr 300 chars, fresh heap                     |   40948.1 | 40249.2 |     1.019x |       0.98-1.05 | 0.981 | 5 |   noise |
| LCSubsequence 300 chars, fresh heap                |   49807.3 | 49255.8 |     1.001x |       0.96-1.02 | 0.992 | 5 |   noise |
| prelude Levenshtein 10000                          | 131042666 | 1333000 |    97.881x |    97.25-101.51 | 1.001 | 5 |  faster |
| prelude Jaro 10000                                 |  39504292 | 36000.0 |  1092.488x | 1082.33-1119.31 | 1.005 | 5 |  faster |
| Jaccard 300 chars, after long-string metrics       |    2226.2 |  2108.6 |     1.064x |       1.03-1.11 | 1.017 | 5 |  faster |
| LCSubstr 300 chars, after long-string metrics      |   41824.8 | 41550.6 |     1.023x |       0.98-1.04 | 1.020 | 5 |   noise |
| LCSubsequence 300 chars, after long-string metrics |   50034.4 | 50227.3 |     0.995x |       0.97-1.00 | 1.001 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 4.335 over 8 rows (min 0.995 LCSubsequence 300 chars, after long-string metrics; max 1092.488 prelude Jaro 10000)
per-run geomean: min 4.290, median 4.315, max 4.377 over 5 runs
A/A geomean 1.004

## i9: Jaccard, LCSubstr and LCSubsequence in a process of their own (gate_jac.cc)

The same calls as the control rows above, on a fresh heap and after the long-string metrics have run, to separate the kernel from the heap state.

| row                                                |     START |    HEAD | START/HEAD |         range |   A/A | n | verdict |
| -------------------------------------------------- | --------: | ------: | ---------: | ------------: | ----: | : | ------: |
| Jaccard 300 chars, fresh heap                      |    2558.8 |  2273.9 |     1.105x |     1.05-1.27 | 0.989 | 5 |  faster |
| LCSubstr 300 chars, fresh heap                     |   63996.1 | 45021.8 |     1.445x |     1.30-1.45 | 0.984 | 5 |  faster |
| LCSubsequence 300 chars, fresh heap                |   82174.8 | 79729.3 |     1.019x |     0.99-1.06 | 1.021 | 5 |   noise |
| prelude Levenshtein 10000                          | 224803359 | 2404241 |    92.486x |   91.74-95.46 | 1.005 | 5 |  faster |
| prelude Jaro 10000                                 |  49749145 |  127594 |   381.560x | 329.12-390.74 | 1.004 | 5 |  faster |
| Jaccard 300 chars, after long-string metrics       |    2561.8 |  2219.0 |     1.153x |     1.12-1.17 | 1.027 | 5 |  faster |
| LCSubstr 300 chars, after long-string metrics      |   63600.3 | 45789.8 |     1.382x |     1.32-1.47 | 0.978 | 5 |  faster |
| LCSubsequence 300 chars, after long-string metrics |   80677.2 | 81068.8 |     0.981x |     0.97-1.06 | 0.970 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 4.160 over 8 rows (min 0.981 LCSubsequence 300 chars, after long-string metrics; max 381.560 prelude Jaro 10000)
per-run geomean: min 4.042, median 4.147, max 4.265 over 5 runs
A/A geomean 0.997

## Notes

- VOID rows are the ones whose answers legitimately changed: `Jaro` (standard algorithm: repeated characters and odd out-of-order counts differ), `Jaro_Winkler` (START returned the plain Jaro score; HEAD computes Jaro-Winkler), `Sorensen_Dice` (multiset bigrams instead of distinct bigrams) and `PhoneticMetric` (START compared the raw strings; HEAD encodes both operands first, so HEAD does the encoding work START skipped). `Jaro` on the single 3000-character pair and `Dice` 1-2 characters return equal answers and are not VOID. The Levenshtein rows (unit costs) are bit-identical, including every long row.
- The `Levenshtein random words (rerun)` row repeats the first row inside the same process: its spread against the first is the in-process noise.
- Jaccard, LCSubstr and LCSubsequence kernels are unchanged (their headers gained one `requires` clause); their rows are controls.

- M4 session (Sun Nov  1 10:55:06 PST 2026): 5 rounds; per-round geomean of the START/START ratios over all rows: 0.994, 1.010, 0.997, 0.998, 1.003 (load average at start / end: 11.39 11.82 14.10 / 11.58 12.33 14.08; row ratios are medians over the rounds, so a disturbed round does not move them).
- i9 session (Sun Nov  1 11:32:02 PST 2026): 5 rounds; per-round geomean of the START/START ratios over all rows: 0.984, 1.017, 1.011, 0.985, 1.017 (load average at start / end: 40.11 17.06 11.04 / 8.47 12.66 10.24; row ratios are medians over the rounds, so a disturbed round does not move them).

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- i9 Jaccard on 300 characters 0.750: placement. The kernel is unchanged, it reads 1.10 to 1.15 in
  an isolated build, and the M4 Pro reads 0.99.
