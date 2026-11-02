# Gate: metrics

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/metrics#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `645d729` | 2026-10-22 04:39:57 -0700 | Link the shared C++ library catalog [skip ci] |
| HEAD (`origin/main` when pinned, 2026-11-01) | `7513d1e` | 2026-11-01 04:22:01 -0800 | Shape the README to the family standard; move the design to ARCHITECTURE.md [skip ci] |

Library sources changed between them (docs, tests, benches, CI excluded): 1 file changed, 57 insertions(+), 12 deletions(-).

## Method (common to every machine)

- Two worktrees of one clone, at START and at HEAD. The bench source is HEAD's (or, where stated, a copy of it with the rows START cannot compile removed, or a micro-bench written for the gate, not kept); each is compiled twice, once with `-I <START tree>` (binary A) and once with `-I <HEAD tree>` (binary B), same compiler, flags and source path. A/A is a byte copy of A.
- Flags: `c++ -std=c++20 -O3 -DNDEBUG -pthread` (Apple clang 17.0.0: M4 Pro `clang-1700.3.19.1`, i9 `clang-1700.6.4.2`). Comparator libraries are not linked or fetched. Only `flat-map`'s bench finds them by itself (`__has_include`): `absl::btree_map` is on the default include path of both machines and `boost::container::flat_map` on the i9's only, so that bench has abseil rows on the M4 and boost and abseil rows on the i9 (controls: they run no code of this repo).
- Rounds: every round runs each bench entry with A, B and AA (order `a b aa` on odd rounds, `aa b a` on even ones), under one `quiet strict` hold per repo and machine (on macOS a strict hold is exclusive). `runab.sh` writes one file per run; `ab_compare.py compare --format unit` pairs run i of A with run i of B (and of AA) and reports the median ratio.
- **Ratio = START time / HEAD time, so above 1 means HEAD is faster.** Throughputs are converted to ns per item. `A/A max dev` is the largest |ratio - 1| of A against its own copy over the same rounds: the measurement's noise. Rows marked `(control)` run code the change cannot reach (a standard-library or baseline arm); they show the noise floor and are left out of the geomean.
- A row is listed as "<0.97 outside A/A" when its ratio is below 0.97 and also below 1/(1 + A/A max dev).

## What was measured

- `bench/bench.cc` (`metrics_bench`): 1,000,000 `observe` calls per histogram kind, xorshift values below 1e8 ns, best of 3 passes per run. Rows: `owner` (`DurationHistogram<Counter>`), `atomic` (`AtomicDurationHistogram`), `owner_with_two_clocks` (adds two `steady_clock` reads per observation), and `disabled` (the random-number loop alone, no `observe`: a control).
- `bench/counter_bench.cc` (`metrics_counter_bench`): contended `add`, ns per add per thread, best of 5, at 1, 2, 4 and 8 threads, for `AtomicCounter`, a standalone copy of the original CAS loop and a bare `fetch_add` (the last two are controls).
- **Rows dropped because START cannot compile them:** HEAD's `bench.cc` also times `ContendedDurationHistogram` and HEAD's `counter_bench.cc` also times `ContendedCounter`. Both types are new (2026-10-31); START has no counterpart, so those two rows (one in each bench) are removed from a copy of each file (`gate/patched/metrics/`). Everything else is HEAD's source unchanged.
- Library change in scope (`metrics.hh`): `DurationHistogram::observe` finds its bucket by counting the bounds below the value (14 compares, no branches) where START called `std::lower_bound`; `AtomicCounter` became a template instantiation with the same compare-exchange loop (START's loop and HEAD's compile to the same operations); `ContendedCounter` is new. `Counter` is unchanged.


### Apple M4 Pro

#### histogram (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| histogram observe disabled (control) | 1.606 | 1.601 | 1.003 | 1.00-1.01 | 0.4% | 3 |
| histogram observe owner | 3.412 | 2.418 | 1.412 | 1.41-1.41 | 0.3% | 3 |
| histogram observe atomic | 3.926 | 2.345 | 1.673 | 1.67-1.68 | 0.7% | 3 |
| histogram observe owner_with_two_clocks | 38.27 | 34.66 | 1.109 | 1.10-1.11 | 0.7% | 3 |

#### counter (`counter_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| threads=1 CAS loop (control) | 2.100 | 2.100 | 1.000 | 1.00-1.00 | 0.0% | 3 |
| threads=1 AtomicCounter | 2.100 | 2.100 | 1.000 | 1.00-1.00 | 0.0% | 3 |
| threads=1 bare fetch_add (control) | 1.800 | 1.800 | 1.000 | 1.00-1.00 | 0.0% | 3 |
| threads=2 CAS loop (control) | 5.400 | 5.100 | 1.000 | 0.95-1.06 | 30.1% | 3 |
| threads=2 AtomicCounter | 5.200 | 5.100 | 1.040 | 0.92-1.06 | 12.5% | 3 |
| threads=2 bare fetch_add (control) | 7.500 | 7.500 | 0.919 | 0.75-1.05 | 9.2% | 3 |
| threads=4 CAS loop (control) | 63.70 | 56.70 | 1.134 | 0.90-1.67 | 52.4% | 3 |
| threads=4 AtomicCounter | 60.60 | 68.60 | 1.001 | 0.88-1.08 | 20.2% | 3 |
| threads=4 bare fetch_add (control) | 34.10 | 29.90 | 1.140 | 1.10-1.27 | 48.6% | 3 |
| threads=8 CAS loop (control) | 255.0 | 272.7 | 0.935 | 0.57-1.08 | 48.7% | 3 |
| threads=8 AtomicCounter | 304.0 | 300.0 | 1.046 | 0.70-1.17 | 49.9% | 3 |
| threads=8 bare fetch_add (control) | 187.6 | 159.5 | 1.017 | 1.00-1.25 | 56.6% | 3 |

**Geomean START/HEAD (Apple M4 Pro): 1.162** over 7 library rows (controls, 9 rows: 1.014)

Rows >1.03: 5; within 0.97-1.03: 2; <0.97: 0 (0 outside the A/A spread, 0 inside it).

### Intel i9-9980HK

#### histogram (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| histogram observe disabled (control) | 1.777 | 1.715 | 1.041 | 0.91-1.04 | 9.1% | 3 |
| histogram observe owner | 6.830 | 6.005 | 1.132 | 1.00-1.14 | 6.7% | 3 |
| histogram observe atomic | 19.18 | 16.13 | 1.119 | 1.06-1.20 | 3.9% | 3 |
| histogram observe owner_with_two_clocks | 85.94 | 82.23 | 1.040 | 0.97-1.05 | 4.6% | 3 |

#### counter (`counter_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| threads=1 CAS loop (control) | 7.800 | 8.000 | 0.975 | 0.97-0.98 | 3.8% | 3 |
| threads=1 AtomicCounter | 7.600 | 8.000 | 0.974 | 0.95-1.00 | 10.0% | 3 |
| threads=1 bare fetch_add (control) | 4.400 | 4.500 | 0.978 | 0.98-1.02 | 13.6% | 3 |
| threads=2 CAS loop (control) | 66.80 | 71.10 | 0.920 | 0.86-0.95 | 8.1% | 3 |
| threads=2 AtomicCounter | 66.80 | 73.10 | 0.912 (<0.97, inside A/A) | 0.88-0.91 | 12.0% | 3 |
| threads=2 bare fetch_add (control) | 24.90 | 25.40 | 1.008 | 0.90-1.08 | 17.4% | 3 |
| threads=4 CAS loop (control) | 233.7 | 222.0 | 1.043 | 0.99-1.12 | 14.0% | 3 |
| threads=4 AtomicCounter | 232.1 | 216.6 | 1.072 | 0.99-1.17 | 20.0% | 3 |
| threads=4 bare fetch_add (control) | 67.20 | 62.90 | 1.026 | 0.90-1.08 | 26.2% | 3 |
| threads=8 CAS loop (control) | 562.6 | 505.5 | 1.087 | 0.93-1.12 | 26.3% | 3 |
| threads=8 AtomicCounter | 561.2 | 517.9 | 1.021 | 0.99-1.08 | 31.2% | 3 |
| threads=8 bare fetch_add (control) | 132.3 | 138.0 | 0.936 | 0.82-1.08 | 20.5% | 3 |

**Geomean START/HEAD (Intel i9-9980HK): 1.036** over 7 library rows (controls, 9 rows: 1.000)

Rows >1.03: 4; within 0.97-1.03: 2; <0.97: 1 (0 outside the A/A spread, 1 inside it).

## Findings: metrics

- **Faster.** The histogram `observe` rows, the rows that exercise the changed code, are 1.41x (`owner`) and 1.67x (`atomic`) faster on the M4 Pro and 1.13x / 1.12x on the i9; the A/A spread of those rows is 0.3-0.7% on the M4 and 4-7% on the i9. `owner_with_two_clocks` is 1.11x (M4) and 1.04x (i9): the two `steady_clock::now()` calls dominate it (35-85 ns of the 35-86 ns).
- **Rows below 0.97 outside the A/A spread: none** on either machine. One row is below 0.97 inside its spread: `threads=2 AtomicCounter` on the i9 at 0.912 (A/A max dev 12.0%, and the CAS-loop control in the same run reads 0.920). `AtomicCounter` runs the same compare-exchange loop at START and at HEAD, so that row is noise, not a regression.
- **The contended counter rows cannot resolve a difference of less than 20-50%**: A/A max deviation is 9-31% on the i9 and 12-57% on the M4 at 2, 4 and 8 threads (3 rounds, 5 bests each, a loop of 2M contended CAS operations on a shared cache line). The verdict on `AtomicCounter` rests on the code (identical loop) and on the 1-thread rows (equal to the displayed digit on the M4: 2.1 against 2.1 ns; 7.6 against 8.0 ns on the i9, 0.974, inside its 10% A/A).
- **Not comparable:** `ContendedCounter` / `ContendedDurationHistogram` (new; their bench rows are dropped, see above). HEAD's tests add the saturation proof and the mutation checks; no behaviour of the START API changed (`AtomicCounter` and `Counter` saturate exactly as before).
- Geomean over the library rows is dominated by the 1-thread and histogram rows: M4 1.162, i9 1.036.

**Verdict: FASTER** (histogram `observe` 1.1-1.7x; counters unchanged).
