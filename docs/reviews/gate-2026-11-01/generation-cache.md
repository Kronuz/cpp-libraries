# Gate: generation-cache

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/generation-cache#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `00762bd` | 2026-10-22 04:40:27 -0700 | Link the shared C++ library catalog [skip ci] |
| HEAD (`origin/main` when pinned, 2026-11-01) | `30cd10c` | 2026-11-01 06:15:42 -0800 | Re-measure generation-cache and name abseil 20260817 |

Library sources changed between them (docs, tests, benches, CI excluded): 1 file changed, 219 insertions(+), 15 deletions(-).

## Method (common to every machine)

- Two worktrees of one clone, at START and at HEAD. The bench source is HEAD's (or, where stated, a copy of it with the rows START cannot compile removed, or a micro-bench written for the gate, not kept); each is compiled twice, once with `-I <START tree>` (binary A) and once with `-I <HEAD tree>` (binary B), same compiler, flags and source path. A/A is a byte copy of A.
- Flags: `c++ -std=c++20 -O3 -DNDEBUG -pthread` (Apple clang 17.0.0: M4 Pro `clang-1700.3.19.1`, i9 `clang-1700.6.4.2`). Comparator libraries are not linked or fetched. Only `flat-map`'s bench finds them by itself (`__has_include`): `absl::btree_map` is on the default include path of both machines and `boost::container::flat_map` on the i9's only, so that bench has abseil rows on the M4 and boost and abseil rows on the i9 (controls: they run no code of this repo).
- Rounds: every round runs each bench entry with A, B and AA (order `a b aa` on odd rounds, `aa b a` on even ones), under one `quiet strict` hold per repo and machine (on macOS a strict hold is exclusive). `runab.sh` writes one file per run; `ab_compare.py compare --format unit` pairs run i of A with run i of B (and of AA) and reports the median ratio.
- **Ratio = START time / HEAD time, so above 1 means HEAD is faster.** Throughputs are converted to ns per item. `A/A max dev` is the largest |ratio - 1| of A against its own copy over the same rounds: the measurement's noise. Rows marked `(control)` run code the change cannot reach (a standard-library or baseline arm); they show the noise floor and are left out of the geomean.
- A row is listed as "<0.97 outside A/A" when its ratio is below 0.97 and also below 1/(1 + A/A max dev).

## What was measured

- `bench/bench.cc` (`generation_cache_bench`), run with no arguments: string keys (`/api/v1/resource/<i>?etag=abc`, `Cache<string, string>`) at n = 64, 4096 and 100000 for `get` hits on 1 thread and on 4 threads (ns per operation, best of 5), then the small-cache rows (64 `int` keys, one thread): construct plus destroy, `get` hit, `get` miss. Each row is run against `OldCache` (a `std::map` behind a `std::mutex`, the original design, a control: a copy in the bench, not the library) and the library `Cache`.
- The bench drives the START API unchanged (`get`, `try_insert`, `generation`, `size`), so no row was dropped. Abseil is not on the include path.
- Library change in scope (`generation_cache.hh`): START is a `std::map` behind one `std::mutex`; HEAD is an open-addressing hash table (per-process-seeded `std::hash`, first insert 4 slots) behind a one-word reader-writer lock (readers share it with one atomic add; writers use a `std::mutex`), with the strong exception guarantee on `try_insert` and rehash.


### Apple M4 Pro

#### main (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| string n=64 old std::map+mutex 1 thread (control) | 39.20 | 38.90 | 1.013 | 0.96-1.02 | 3.0% | 3 |
| string n=64 old std::map+mutex 4 threads (control) | 119.1 | 118.4 | 0.953 | 0.89-1.06 | 44.0% | 3 |
| string n=64 Cache (this library) 1 thread | 39.10 | 30.40 | 1.294 | 1.28-1.31 | 1.3% | 3 |
| string n=64 Cache (this library) 4 threads | 114.6 | 63.40 | 1.882 | 1.81-2.29 | 18.7% | 3 |
| string n=4096 old std::map+mutex 1 thread (control) | 141.8 | 141.0 | 1.005 | 0.98-1.01 | 3.8% | 3 |
| string n=4096 old std::map+mutex 4 threads (control) | 509.2 | 520.1 | 0.980 | 0.85-0.99 | 16.6% | 3 |
| string n=4096 Cache (this library) 1 thread | 141.1 | 49.20 | 2.868 | 2.85-2.88 | 2.4% | 3 |
| string n=4096 Cache (this library) 4 threads | 494.6 | 64.60 | 7.551 | 6.94-9.26 | 35.8% | 3 |
| string n=100000 old std::map+mutex 1 thread (control) | 591.4 | 553.9 | 1.084 | 0.95-1.14 | 14.8% | 3 |
| string n=100000 old std::map+mutex 4 threads (control) | 1816.8 | 2017.9 | 0.939 | 0.89-0.94 | 14.1% | 3 |
| string n=100000 Cache (this library) 1 thread | 577.0 | 215.8 | 2.816 | 2.48-3.13 | 15.2% | 3 |
| string n=100000 Cache (this library) 4 threads | 1920.8 | 84.10 | 22.858 | 22.36-23.78 | 8.8% | 3 |
| small old std::map+mutex construct+destroy (control) | 12.70 | 12.50 | 1.016 | 1.00-1.05 | 6.7% | 3 |
| small old std::map+mutex get hit (control) | 8.000 | 7.990 | 0.996 | 0.99-1.01 | 1.7% | 3 |
| small old std::map+mutex get miss (control) | 8.700 | 8.730 | 0.994 | 0.98-1.01 | 2.8% | 3 |
| small Cache (this library) construct+destroy | 12.70 | 6.000 | 2.153 | 2.12-2.17 | 5.8% | 3 |
| small Cache (this library) get hit | 8.060 | 3.670 | 2.196 | 2.10-2.20 | 4.5% | 3 |
| small Cache (this library) get miss | 8.580 | 3.650 | 2.344 | 2.31-2.36 | 1.4% | 3 |

**Geomean START/HEAD (Apple M4 Pro): 3.224** over 9 library rows (controls, 9 rows: 0.997)

Rows >1.03: 9; within 0.97-1.03: 0; <0.97: 0 (0 outside the A/A spread, 0 inside it).

### Intel i9-9980HK

#### main (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| string n=64 old std::map+mutex 1 thread (control) | 174.7 | 171.8 | 1.007 | 0.99-1.04 | 3.3% | 3 |
| string n=64 old std::map+mutex 4 threads (control) | 686.6 | 662.7 | 1.052 | 1.02-1.08 | 7.0% | 3 |
| string n=64 Cache (this library) 1 thread | 177.0 | 86.30 | 2.064 | 2.02-2.08 | 2.2% | 3 |
| string n=64 Cache (this library) 4 threads | 697.4 | 69.90 | 9.977 | 9.58-10.19 | 4.4% | 3 |
| string n=4096 old std::map+mutex 1 thread (control) | 363.3 | 372.1 | 0.976 | 0.97-1.05 | 6.0% | 3 |
| string n=4096 old std::map+mutex 4 threads (control) | 2208.9 | 2179.2 | 1.012 | 0.99-1.07 | 5.4% | 3 |
| string n=4096 Cache (this library) 1 thread | 364.8 | 126.2 | 2.891 | 2.77-3.03 | 5.2% | 3 |
| string n=4096 Cache (this library) 4 threads | 2211.1 | 74.20 | 29.560 | 28.93-33.88 | 6.9% | 3 |
| string n=100000 old std::map+mutex 1 thread (control) | 939.2 | 919.3 | 1.024 | 1.01-1.03 | 2.2% | 3 |
| string n=100000 old std::map+mutex 4 threads (control) | 2781.8 | 2691.7 | 1.033 | 1.01-1.04 | 5.5% | 3 |
| string n=100000 Cache (this library) 1 thread | 911.6 | 433.7 | 2.102 | 2.04-2.20 | 0.4% | 3 |
| string n=100000 Cache (this library) 4 threads | 2808.1 | 118.3 | 23.737 | 22.72-23.86 | 5.0% | 3 |
| small old std::map+mutex construct+destroy (control) | 61.20 | 63.10 | 0.968 | 0.95-0.97 | 4.3% | 3 |
| small old std::map+mutex get hit (control) | 19.02 | 21.09 | 0.911 | 0.90-0.99 | 4.1% | 3 |
| small old std::map+mutex get miss (control) | 20.91 | 21.01 | 1.003 | 0.97-1.00 | 3.5% | 3 |
| small Cache (this library) construct+destroy | 54.20 | 26.30 | 2.061 | 1.96-2.16 | 4.8% | 3 |
| small Cache (this library) get hit | 18.27 | 10.94 | 1.668 | 1.67-1.67 | 2.0% | 3 |
| small Cache (this library) get miss | 20.26 | 10.90 | 1.859 | 1.84-1.87 | 2.7% | 3 |

**Geomean START/HEAD (Intel i9-9980HK): 4.353** over 9 library rows (controls, 9 rows: 0.998)

Rows >1.03: 9; within 0.97-1.03: 0; <0.97: 0 (0 outside the A/A spread, 0 inside it).

## Findings: generation-cache

- **M4 Pro (3 rounds): faster on every library row, none below 0.97.** String keys, `get` hit: n=64 1.29x (1 thread) and 1.88x (4 threads); n=4096 2.87x and 7.55x; n=100000 2.82x and 22.9x. Small cache, 64 `int` keys: construct+destroy 2.15x, `get` hit 2.20x, `get` miss 2.34x. Geomean 3.22 over the 9 library rows. The `old std::map+mutex` control rows read 0.94-1.08 (A/A spread up to 44% on the 4-thread ones), so the shifts of 1.3-23x are not noise.
- **i9 (3 rounds): faster on every library row, none below 0.97.** n=64: 2.06x (1 thread) and 9.98x (4 threads); n=4096: 2.89x and 29.6x; n=100000: 2.10x and 23.7x; small cache: construct+destroy 2.06x, `get` hit 1.67x, `get` miss 1.86x. Geomean 4.35 over the 9 library rows; the 9 control rows read 0.91-1.05 (geomean 0.998), A/A max dev of the library rows 0.4-6.9%. An earlier one-round run (the hold ended during round 2) gave the same picture (geomean 4.49).
- The multi-thread gain is the point of the change: START serialises every `get` on one mutex (M4, n=100000: 577 ns per operation on 1 thread, 1,921 ns on 4; i9: 912 ns and 2,808 ns), HEAD's readers share a one-word lock (M4 216 ns and 84 ns; i9 434 ns and 118 ns).
- **Rows below 0.97 outside the A/A spread: none**, on either machine. HEAD's CHANGELOG notes the one row that was slower than the `std::map` it replaced before the 4-slot change ("construct, insert once, destroy"; 134 ns on x86_64 against 134 ns for the `std::map` after it); that row is not in `bench/bench.cc` and was not timed here.
- **Correctness changes, none that makes a row not comparable:** the rehash and `try_insert` exception-safety fixes touch only throwing paths ("Results change only on the throwing paths"). The per-cache hash seed changes the layout of keys in the table, not any returned value.

**Verdict: FASTER** (2-30x on `get`, 2x on construction; the control arm unchanged).
