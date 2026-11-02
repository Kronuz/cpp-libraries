# Gate: htm (START a0321ab vs HEAD fa1a27d)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/htm#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Hierarchical Triangular Mesh. HEAD runs the `getId` descent on plain three-double vectors and derives `getTrixelName(Cartesian)` from the id; it also makes the descent independent of floating-point contraction.

**Verdict: FASTER where it changed, SAME elsewhere. `getId(Cartesian)` is 1.55x (M4) and 1.69x (i9) faster and `getTrixelName(Cartesian)` 1.43x (M4) and 1.53x (i9); every other entry point is unchanged within the A/A spread. No row is below 0.97 outside the spread on either machine.**

## Machines, compiler, commands

| | Apple M4 Pro | Intel i9-9980HK |
|---|---|---|
| host | the M4 Pro, arm64, 14 cores, macOS 26.7.2 | the i9, x86_64, 8C/16T, macOS 15 |
| compiler | Apple clang 17.0.0 (clang-1700.3.19.1) | Apple clang 17.0.0 (clang-1700.6.4.2) |
| flags (both sides) | `-std=c++20 -O3 -DNDEBUG` | `-std=c++20 -O3 -DNDEBUG` |
| sessions | `quiet strict`: string-similarity at 10:55 (5 rounds + the Jaccard follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:14 (about 1 minute of timed runs in all) | `quiet strict`: string-similarity at 11:32 (5 rounds + the follow-up); htm (7 rounds), cartesian, double-metaphone, soundex (5 rounds each) in one short hold at 12:55 (one minute of timed runs). A first i9 session (09:19, other work running) is kept as a cross-check |

Commands (per machine, from `$GATE`):

```
clang++ -std=c++20 -O3 -DNDEBUG -I. -Ihtm-{start,head} -Ideps/cartesian gate_htm.cc htm-{start,head}/htm.cc htm-{start,head}/constraint.cc deps/cartesian/cartesian.cc -o build/<arch>/htm-{start,head}
quiet strict 10 ... -- ./rounds.sh 5
python3 cpp-libraries/tools/ab_compare.py compare --a results/<arch>/htm/a --b .../b --aa .../aa --output csv
```

Source: `gate_htm.cc` + `gate_common.h`. Rows 1-3 are the "new" column of `bench/bench.cc` at HEAD (20,000 random unit vectors, seed 42); the others are additions. `cartesian` is `49f4075` (HEAD's pin) for both sides, so only htm's own sources differ.

## Results

Ratio = START / HEAD (above 1: HEAD is faster). `A/A` is the largest deviation from 1 of the five paired START-against-START ratios of the same session (the noise of that row on that machine, worst round; a row is called slower only when its ratio is below 1 / (1 + A/A) and below 0.97). `VOID` marks a row whose answers differ between START and HEAD (a correctness change, see the notes): its ratio is shown but the row is outside the first geomean.

| row | M4 START | M4 HEAD | M4 ratio | M4 A/A | i9 START | i9 HEAD | i9 ratio | i9 A/A | note |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| getId(Cartesian) | 908.3 ns | 586.5 ns | 1.551 VOID | 1.4% | 1.37 us | 808.5 ns | 1.689 | 1.9% |  |
| getTrixelName(Cartesian) | 940.2 ns | 659.0 ns | 1.427 VOID | 1.3% | 1.49 us | 974.2 ns | 1.528 | 5.7% |  |
| getTrixelName(id) | 62.8 ns | 63.2 ns | 1.003 VOID | 3.7% | 145.6 ns | 158.1 ns | 0.921 | 10.9% | unchanged function (the htm.cc diff touches only getId and getTrixelName(Cartesian)) |
| getId(name) | 8.3 ns | 8.3 ns | 1.000 VOID | 3.1% | 11.7 ns | 12.0 ns | 0.974 | 18.9% | unchanged function |
| getCorners(name) | 465.6 ns | 463.1 ns | 1.002 VOID | 1.5% | 756.0 ns | 752.6 ns | 0.994 | 2.8% |  |
| getRange(name) | 8.3 ns | 8.3 ns | 1.000 | 8.8% | 12.2 ns | 11.8 ns | 1.014 | 17.9% |  |
| getRange(id, level 20) | 0.8 ns | 0.8 ns | 0.987 | 2.7% | 1.7 ns | 1.7 ns | 1.000 | 18.0% |  |
| midPoint | 3.4 ns | 3.4 ns | 1.021 | 5.9% | 6.7 ns | 6.7 ns | 1.004 | 18.2% |  |
| insideVertex_Trixel | 14.3 ns | 14.1 ns | 1.013 | 12.1% | 16.5 ns | 16.7 ns | 0.987 | 18.0% |  |
| range_union 2x2000 (whole call) | 10.00 us | 10.03 us | 0.971 | 8.6% | 25.53 us | 25.55 us | 0.995 | 16.1% |  |
| range_intersection 2x2000 (whole call) | 7.90 us | 7.92 us | 1.048 | 11.9% | 19.00 us | 19.02 us | 0.999 | 14.2% |  |
| range_exclusive_disjunction 2x2000 (whole call) | 14.16 us | 14.05 us | 0.991 | 13.2% | 39.10 us | 39.35 us | 0.978 | 16.1% |  |
| simplifyRanges 2000 (whole call) | 804.2 ns | 812.5 ns | 1.000 | 8.5% | 1.36 us | 1.39 us | 0.977 | 16.4% |  |
| getTrixels 200 ranges (whole call) | 7.29 us | 7.26 us | 1.009 | 16.2% | 16.59 us | 16.46 us | 1.008 | 10.6% |  |

## Geomean (START / HEAD)

| machine | geomean, comparable rows | n | geomean, all rows (VOID included) | n |
|---|--:|--:|--:|--:|
| M4 | 1.004 | 9 | 1.062 | 14 |
| i9 | 1.059 | 14 | 1.059 | 14 |
| i9, first session (09:19, other jobs' work running, noisier) | 1.053 | 14 | 1.053 | 14 |

## Rows with ratio < 0.97 outside the A/A spread

None.

Rows below 0.97 whose ratio is inside the A/A spread (not counted above; the session cannot tell them from noise):

- i9: getTrixelName(id): 0.921 (A/A 10.9%) - unchanged function (the htm.cc diff touches only getId and getTrixelName(Cartesian))

## Notes

- On the M4 the ids of START and HEAD differ for 161 of the 20,000 random points (0.8%), always in the last base-4 digit (level 25): the cause is the one HEAD's CHANGELOG (2026-10-31, "Make getId independent of FP contraction") fixes: START's descent is compiled with the compiler's default contraction (fused multiply-add on arm64), HEAD's is plain IEEE-754 whatever the compiler fuses (not re-verified here with a no-contraction START build). The rows that derive from ids (`getId`, `getTrixelName`, `getId(name)`, `getCorners(name)`) therefore have different checksums on the M4 and are VOID there by the tool's rule; the work per call is the same, so the ratio is a fair speed comparison. On the i9 (no FMA in the baseline x86-64 target) START and HEAD ids are identical.
- The M4 has more than one machine-dependent codegen path here: HEAD's `getId` runs a start-up probe (48 points) once, on the first call, to pick the plain or the rounded form; that cost is outside the timed loop.

- M4 session (Sun Nov  1 12:14:41 PST 2026): 7 rounds; per-round geomean of the START/START ratios over all rows: 1.059, 0.998, 0.994, 0.998, 0.997, 1.009, 0.991 (load average at start / end: 9.09 8.46 8.72 / 8.38 8.33 8.67; row ratios are medians over the rounds, so a disturbed round does not move them).
- i9 session (Sun Nov  1 12:54:03 PST 2026): 7 rounds; per-round geomean of the START/START ratios over all rows: 1.001, 0.897, 1.008, 1.008, 0.996, 0.993, 0.978 (load average at start / end: 5.87 6.80 6.81 / 5.52 6.68 6.77; row ratios are medians over the rounds, so a disturbed round does not move them).
