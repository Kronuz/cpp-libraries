# Gate: double-metaphone (START 91c17a2 vs HEAD 1ca7a70)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/double-metaphone#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Double Metaphone encoder. HEAD builds one key per call (`encode` no longer builds both) and cleans the word in one pass; the keys are unchanged.

**Verdict: FASTER. Every operation on every word set is 1.6-2.2x faster on the M4 and 1.9-2.7x on the i9; keys are identical. No row below 0.97.**

## Machines, compiler, commands

| | Apple M4 Pro | Intel i9-9980HK |
|---|---|---|
| host | the M4 Pro, arm64, 14 cores, macOS 26.7.2 | the i9, x86_64, 8C/16T, macOS 15 |
| compiler | Apple clang 17.0.0 (clang-1700.3.19.1) | Apple clang 17.0.0 (clang-1700.6.4.2) |
| flags (both sides) | `-std=c++20 -O3 -DNDEBUG` | `-std=c++20 -O3 -DNDEBUG` |
| sessions | `quiet strict`: string-similarity at 10:55 (5 rounds + the Jaccard follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:14 (about 1 minute of timed runs in all) | `quiet strict`: string-similarity at 11:32 (5 rounds + the follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:55 (one minute of timed runs). A first i9 session (09:19, other work running) is kept as a cross-check |

Commands (per machine, from `$GATE`):

```
clang++ -std=c++20 -O3 -DNDEBUG -I. -Idouble-metaphone-{start,head} gate_dmeta.cc double-metaphone-{start,head}/double_metaphone.cc -o build/<arch>/dmeta-{start,head}
quiet strict 10 ... -- ./rounds.sh 5
python3 cpp-libraries/tools/ab_compare.py compare --a results/<arch>/dmeta/a --b .../b --aa .../aa --output csv
```

Source: `gate_dmeta.cc` + `gate_common.h`. The word sets and the four operations are those of `bench/bench.cc` at HEAD (generated words, names, phrases, long words); added: the system dictionary `/usr/share/dict/words` (235,976 words). `test/double_metaphone_old.cc` (the frozen copy that bench uses) was diffed against START's `double_metaphone.cc`: identical except a 3-line header comment, so HEAD's own "old" column is START; here START's tree is built anyway.

## Results

Ratio = START / HEAD (above 1: HEAD is faster). `A/A` is the largest deviation from 1 of the five paired START-against-START ratios of the same session (the noise of that row on that machine, worst round; a row is called slower only when its ratio is below 1 / (1 + A/A) and below 0.97). `VOID` marks a row whose answers differ between START and HEAD (a correctness change, see the notes): its ratio is shown but the row is outside the first geomean.

| row | M4 START | M4 HEAD | M4 ratio | M4 A/A | i9 START | i9 HEAD | i9 ratio | i9 A/A | note |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| words encode | 152.5 ns | 83.8 ns | 1.839 | 1.9% | 286.1 ns | 130.9 ns | 2.180 | 2.6% |  |
| words encode_alternate | 152.8 ns | 84.6 ns | 1.807 | 1.5% | 284.6 ns | 131.0 ns | 2.172 | 3.5% |  |
| words encode_both | 153.5 ns | 93.8 ns | 1.632 | 2.4% | 287.9 ns | 152.8 ns | 1.883 | 1.5% |  |
| words construct+encode() | 155.0 ns | 84.8 ns | 1.835 | 1.8% | 286.7 ns | 131.3 ns | 2.190 | 3.4% |  |
| names encode | 115.5 ns | 53.9 ns | 2.119 | 2.9% | 241.8 ns | 110.9 ns | 2.185 | 4.3% |  |
| names encode_alternate | 114.4 ns | 54.5 ns | 2.138 | 2.7% | 244.0 ns | 110.7 ns | 2.184 | 4.2% |  |
| names encode_both | 114.8 ns | 62.4 ns | 1.828 | 4.5% | 243.1 ns | 129.5 ns | 1.875 | 3.5% |  |
| names construct+encode() | 114.6 ns | 54.6 ns | 2.116 | 5.6% | 243.1 ns | 110.8 ns | 2.170 | 3.9% |  |
| phrases encode | 1.00 us | 573.2 ns | 1.742 | 1.0% | 2.07 us | 868.7 ns | 2.394 | 1.5% |  |
| phrases encode_alternate | 995.5 ns | 578.0 ns | 1.725 | 1.1% | 2.08 us | 857.3 ns | 2.419 | 1.1% |  |
| phrases encode_both | 994.7 ns | 605.2 ns | 1.638 | 2.7% | 2.08 us | 960.0 ns | 2.177 | 3.2% |  |
| phrases construct+encode() | 1.02 us | 598.1 ns | 1.708 | 1.1% | 2.12 us | 919.6 ns | 2.313 | 1.4% |  |
| long encode | 5.66 us | 2.84 us | 1.987 | 6.4% | 10.75 us | 4.70 us | 2.286 | 4.8% |  |
| long encode_alternate | 5.54 us | 2.95 us | 1.874 | 3.2% | 10.57 us | 4.63 us | 2.278 | 7.3% |  |
| long encode_both | 5.56 us | 2.96 us | 1.811 | 3.0% | 10.70 us | 5.24 us | 1.998 | 7.9% |  |
| long construct+encode() | 5.50 us | 2.98 us | 1.850 | 3.9% | 10.68 us | 4.78 us | 2.223 | 5.0% |  |
| sysdict encode | 131.2 ns | 59.2 ns | 2.222 | 1.8% | 257.5 ns | 95.8 ns | 2.696 | 1.4% |  |
| sysdict encode_alternate | 130.3 ns | 59.4 ns | 2.196 | 1.3% | 258.1 ns | 95.2 ns | 2.720 | 2.3% |  |
| sysdict encode_both | 130.9 ns | 67.4 ns | 1.931 | 1.4% | 261.1 ns | 113.3 ns | 2.291 | 3.3% |  |
| sysdict construct+encode() | 132.4 ns | 60.8 ns | 2.170 | 0.8% | 259.7 ns | 95.6 ns | 2.696 | 1.9% |  |

## Geomean (START / HEAD)

| machine | geomean, comparable rows | n | geomean, all rows (VOID included) | n |
|---|--:|--:|--:|--:|
| M4 | 1.900 | 20 | 1.900 | 20 |
| i9 | 2.255 | 20 | 2.255 | 20 |
| i9, first session (09:19, other jobs' work running, noisier) | 2.246 | 20 | 2.246 | 20 |

## Rows with ratio < 0.97 outside the A/A spread

None.

## Notes

- All rows have equal answers at START and HEAD (the `chk` of every key matches), so none is VOID.

- M4 session (Sun Nov  1 12:15:00 PST 2026): 5 rounds; per-round geomean of the START/START ratios over all rows: 0.995, 0.993, 1.003, 0.997, 1.005 (load average at start / end: 8.02 8.25 8.63 / 7.60 8.12 8.57; row ratios are medians over the rounds, so a disturbed round does not move them).
- i9 session (Sun Nov  1 12:54:30 PST 2026): 5 rounds; per-round geomean of the START/START ratios over all rows: 0.996, 1.009, 0.984, 1.006, 0.987 (load average at start / end: 5.41 6.59 6.74 / 9.00 7.43 7.04; row ratios are medians over the rounds, so a disturbed round does not move them).
