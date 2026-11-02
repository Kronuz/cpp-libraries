# Gate: soundex (START 89f9d51 vs HEAD b9d094c)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/soundex#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Soundex encoders. HEAD carries one speed change (SoundexEnglish encodes in a single pass through a 256-entry class table) and constrained word constructors so encoders copy. French, German and Spanish code is unchanged apart from that constructor constraint, so those rows are controls.

**Verdict: FASTER. `SoundexEnglish` is 3.2-4.3x faster on the M4 and 2.6-3.2x on the i9 (single-pass encoder); French, German and Spanish are unchanged (1.00). No row below 0.97.**

## Machines, compiler, commands

| | Apple M4 Pro | Intel i9-9980HK |
|---|---|---|
| host | the M4 Pro, arm64, 14 cores, macOS 26.7.2 | the i9, x86_64, 8C/16T, macOS 15 |
| compiler | Apple clang 17.0.0 (clang-1700.3.19.1) | Apple clang 17.0.0 (clang-1700.6.4.2) |
| flags (both sides) | `-std=c++20 -O3 -DNDEBUG` | `-std=c++20 -O3 -DNDEBUG` |
| sessions | `quiet strict`: string-similarity at 10:55 (5 rounds + the Jaccard follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:14 (about 1 minute of timed runs in all) | `quiet strict`: string-similarity at 11:32 (5 rounds + the follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:55 (one minute of timed runs). A first i9 session (09:19, other work running) is kept as a cross-check |

Commands (per machine, from `$GATE`):

```
clang++ -std=c++20 -O3 -DNDEBUG -I. -Isoundex-{start,head} -Ideps/{strings,char-classify,split,static-string,repr,term-color} gate_soundex.cc -o build/<arch>/soundex-{start,head}
quiet strict 10 ... -- ./rounds.sh 5     # per round and repo: START, HEAD, START (the A/A control)
python3 cpp-libraries/tools/ab_compare.py compare --a results/<arch>/soundex/a --b .../b --aa .../aa --output csv
```

`soundex-start` is built from the worktree at `89f9d51`, `soundex-head` from `b9d094c`; the `strings` dependency (needed by French, German, Spanish) is `485f882`, the same for both (HEAD's pin). Source: `gate_soundex.cc` + `gate_common.h` (public API only). Row 1 is the "new" column of `bench/bench.cc` at HEAD; the other rows are additions. Rows dropped because HEAD's API does not exist at START: `SoundexEnglish::encode(std::string_view)` (START's `encode` forwards to `_encode(std::string)`; it does not compile for a `string_view`) and copying a non-const lvalue encoder (does not compile at START).

## Results

Ratio = START / HEAD (above 1: HEAD is faster). `A/A` is the largest deviation from 1 of the five paired START-against-START ratios of the same session (the noise of that row on that machine, worst round; a row is called slower only when its ratio is below 1 / (1 + A/A) and below 0.97). `VOID` marks a row whose answers differ between START and HEAD (a correctness change, see the notes): its ratio is shown but the row is outside the first geomean.

| row | M4 START | M4 HEAD | M4 ratio | M4 A/A | i9 START | i9 HEAD | i9 ratio | i9 A/A | note |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| SoundexEnglish::encode | 70.4 ns | 17.0 ns | 4.166 | 2.5% | 94.2 ns | 29.4 ns | 3.174 | 5.2% |  |
| SoundexEnglish().encode(word), as bench.cc | 70.6 ns | 16.4 ns | 4.279 | 2.0% | 94.4 ns | 36.3 ns | 2.548 | 5.5% |  |
| SoundexEnglish::encode text 20-60 chars | 431.7 ns | 134.8 ns | 3.152 | 5.1% | 592.4 ns | 225.7 ns | 2.613 | 3.0% |  |
| SoundexEnglish(word).encode() | 71.1 ns | 21.8 ns | 3.291 | 3.9% | 95.2 ns | 36.8 ns | 2.595 | 4.5% |  |
| SoundexFrench::encode | 242.9 ns | 240.1 ns | 1.000 | 2.0% | 650.0 ns | 567.0 ns | 1.149 | 5.6% |  |
| SoundexGerman::encode | 173.2 ns | 172.9 ns | 1.002 | 3.3% | 342.2 ns | 339.0 ns | 1.010 | 5.7% |  |
| SoundexSpanish::encode | 188.2 ns | 188.5 ns | 1.000 | 4.0% | 416.3 ns | 386.9 ns | 1.082 | 4.8% |  |

## Geomean (START / HEAD)

| machine | geomean, comparable rows | n | geomean, all rows (VOID included) | n |
|---|--:|--:|--:|--:|
| M4 | 2.108 | 7 | 2.108 | 7 |
| i9 | 1.830 | 7 | 1.830 | 7 |
| i9, first session (09:19, other jobs' work running, noisier) | 1.772 | 7 | 1.772 | 7 |

## Rows with ratio < 0.97 outside the A/A spread

None.

## Notes

- Every row has equal answers at START and HEAD (the `chk` of the results matches), so none is VOID.
- `bench/bench.cc` at HEAD times a frozen copy (`test/frozen.h`) against the library; it is the reference encoder from before the single-pass rewrite, not START's header, so it is not used here: START's own header is built instead.

- M4 session (Sun Nov  1 12:15:31 PST 2026): 5 rounds; per-round geomean of the START/START ratios over all rows: 1.007, 0.999, 0.999, 0.994, 1.009 (load average at start / end: 7.60 8.12 8.57 / 7.56 8.10 8.56; row ratios are medians over the rounds, so a disturbed round does not move them).
- i9 session (Sun Nov  1 12:55:25 PST 2026): 5 rounds; per-round geomean of the START/START ratios over all rows: 1.023, 0.981, 0.989, 1.001, 1.005 (load average at start / end: 9.00 7.43 7.04 / 8.44 7.34 7.01; row ratios are medians over the rounds, so a disturbed round does not move them).
