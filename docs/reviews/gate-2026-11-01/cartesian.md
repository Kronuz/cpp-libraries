# Gate: cartesian (START 6eab8ed vs HEAD e60debd)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/cartesian#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Geodesy and 3-vectors. `cartesian.cc` is identical at START and HEAD; the only code change is `std::hash<Cartesian>` (bit mixing instead of hashing `to_string()`, folding -0.0 into 0.0). The other rows are controls for unchanged code.

**Verdict: FASTER. `std::hash<Cartesian>` is 170-326x faster and an `unordered_set<Cartesian>` insert+find of 20,000 points 8.6-13x faster. Everything else is unchanged code at 1.00; three rows are 0.86-0.90x outside their A/A spread (two constructors on the M4, `operator==` on the i9) and all three are code placement: the machine code is identical in the two binaries.**

## Machines, compiler, commands

| | Apple M4 Pro | Intel i9-9980HK |
|---|---|---|
| host | the M4 Pro, arm64, 14 cores, macOS 26.7.2 | the i9, x86_64, 8C/16T, macOS 15 |
| compiler | Apple clang 17.0.0 (clang-1700.3.19.1) | Apple clang 17.0.0 (clang-1700.6.4.2) |
| flags (both sides) | `-std=c++20 -O3 -DNDEBUG` | `-std=c++20 -O3 -DNDEBUG` |
| sessions | `quiet strict`: string-similarity at 10:55 (5 rounds + the Jaccard follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:14 (about 1 minute of timed runs in all) | `quiet strict`: string-similarity at 11:32 (5 rounds + the follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:55 (one minute of timed runs). A first i9 session (09:19, other work running) is kept as a cross-check |

Commands (per machine, from `$GATE`):

```
clang++ -std=c++20 -O3 -DNDEBUG -I. -Icartesian-{start,head} gate_cartesian.cc cartesian-{start,head}/cartesian.cc -o build/<arch>/cartesian-{start,head}
quiet strict 10 ... -- ./rounds.sh 5
python3 cpp-libraries/tools/ab_compare.py compare --a results/<arch>/cartesian/a --b .../b --aa .../aa --output csv
```

Source: `gate_cartesian.cc` + `gate_common.h`. Row 1 is the "new" column of `bench/bench.cc` at HEAD (50,000 normal-distributed points, seed 3); the other rows are additions.

## Results

Ratio = START / HEAD (above 1: HEAD is faster). `A/A` is the largest deviation from 1 of the five paired START-against-START ratios of the same session (the noise of that row on that machine, worst round; a row is called slower only when its ratio is below 1 / (1 + A/A) and below 0.97). `VOID` marks a row whose answers differ between START and HEAD (a correctness change, see the notes): its ratio is shown but the row is outside the first geomean.

| row | M4 START | M4 HEAD | M4 ratio | M4 A/A | i9 START | i9 HEAD | i9 ratio | i9 A/A | note |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| hash<Cartesian> | 218.7 ns | 0.8 ns | 271.910 | 1.7% | 455.5 ns | 2.2 ns | 205.545 | 2.9% |  |
| hash<Cartesian> (WGS84 points) | 254.9 ns | 0.8 ns | 326.218 | 0.6% | 482.2 ns | 2.2 ns | 216.559 | 2.7% |  |
| Cartesian(lat, lon, h, DEGREES) WGS84 | 17.5 ns | 20.3 ns | 0.874 | 2.8% | 32.3 ns | 31.6 ns | 1.016 | 1.9% |  |
| Cartesian(lat, lon, h, DEGREES) OSGB36 (Helmert) | 20.3 ns | 22.6 ns | 0.899 | 1.8% | 46.9 ns | 48.5 ns | 0.966 | 3.6% |  |
| Cartesian(x, y, z) | 1.0 ns | 1.0 ns | 1.000 | 3.0% | 2.1 ns | 2.1 ns | 1.000 | 5.5% |  |
| toGeodetic | 121.8 ns | 123.2 ns | 0.997 | 2.2% | 176.8 ns | 177.2 ns | 0.995 | 7.4% |  |
| toLatLon | 120.7 ns | 120.5 ns | 1.006 | 2.3% | 176.1 ns | 176.4 ns | 0.987 | 3.4% |  |
| distance | 6.8 ns | 6.8 ns | 1.007 | 3.2% | 8.7 ns | 8.7 ns | 0.978 | 8.2% |  |
| operator* (dot) | 0.8 ns | 0.8 ns | 1.000 | 4.1% | 1.7 ns | 1.8 ns | 0.994 | 5.4% |  |
| operator^ (cross) | 1.0 ns | 1.0 ns | 1.000 | 4.0% | 2.4 ns | 2.4 ns | 1.000 | 5.2% |  |
| norm | 0.8 ns | 0.8 ns | 1.000 | 2.7% | 1.8 ns | 1.7 ns | 1.065 | 5.8% |  |
| to_string | 215.4 ns | 213.2 ns | 1.012 | 1.8% | 444.6 ns | 455.9 ns | 0.975 | 2.2% |  |
| operator== | 1.0 ns | 1.0 ns | 1.000 | 2.0% | 1.5 ns | 1.7 ns | 0.860 | 4.0% |  |
| unordered_set<Cartesian> insert+find, 20000 (whole batch) | 9.74 ms | 759.83 us | 12.950 | 2.0% | 20.74 ms | 2.49 ms | 8.312 | 3.0% |  |

## Geomean (START / HEAD)

| machine | geomean, comparable rows | n | geomean, all rows (VOID included) | n |
|---|--:|--:|--:|--:|
| M4 | 2.667 | 14 | 2.667 | 14 |
| i9 | 2.467 | 14 | 2.467 | 14 |
| i9, first session (09:19, other jobs' work running, noisier) | 2.421 | 14 | 2.421 | 14 |

## Rows with ratio < 0.97 outside the A/A spread

- M4: **Cartesian(lat, lon, h, DEGREES) WGS84**: 0.874 (A/A 2.8%): code placement, not work: `cartesian.cc` is byte-identical at START and HEAD, and the instruction streams of `toCartesian` and the constructor in the two M4 benchmark binaries are identical (`otool -tvV` diff: only the `adrp` page numbers differ; the functions sit 0x348 bytes apart). The i9 session shows 1.02.
- M4: **Cartesian(lat, lon, h, DEGREES) OSGB36 (Helmert)**: 0.899 (A/A 1.8%): same function, same cause (identical machine code, shifted placement); i9 0.97, inside its spread.
- i9: **operator==**: 0.860 (A/A 4.0%): code placement, not work: `operator==` is out of line in `cartesian.cc` (byte-identical at START and HEAD); its 23 instructions are identical in the two i9 binaries (`otool -tvV` diff empty) and the function sits at 0x7fa0 in one and 0xa910 in the other. M4: 1.00.

Rows below 0.97 whose ratio is inside the A/A spread (not counted above; the session cannot tell them from noise):

- i9: Cartesian(lat, lon, h, DEGREES) OSGB36 (Helmert): 0.966 (A/A 3.6%)

## Notes

- The two `hash<Cartesian>` rows time the hash call only; their values differ by design (a different function), so their checksum is not compared. The `unordered_set` row compares counts of found elements and its answers match.
- Every row except the hash and the `unordered_set` rows is unchanged code (`cartesian.cc` is byte-identical). They guard against a regression and move only with code placement: the two rows flagged above have identical machine code in the START and HEAD binaries (checked with `otool -tvV`) and sit at different addresses.

- M4 session (Sun Nov  1 12:14:52 PST 2026): 5 rounds; per-round geomean of the START/START ratios over all rows: 0.997, 1.005, 1.003, 1.008, 0.995 (load average at start / end: 8.38 8.33 8.67 / 8.02 8.25 8.63; row ratios are medians over the rounds, so a disturbed round does not move them).
- i9 session (Sun Nov  1 12:54:17 PST 2026): 5 rounds; per-round geomean of the START/START ratios over all rows: 0.986, 0.989, 1.000, 0.971, 1.003 (load average at start / end: 5.52 6.68 6.77 / 5.41 6.59 6.74; row ratios are medians over the rounds, so a disturbed round does not move them).

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 `Cartesian(lat, lon, h, DEGREES)` WGS84 0.874 and OSGB36 0.899, i9 `operator==` 0.860:
  placement. `cartesian.cc`'s instruction streams are identical at start and head; each row reads
  about 1.0 on the other machine.
