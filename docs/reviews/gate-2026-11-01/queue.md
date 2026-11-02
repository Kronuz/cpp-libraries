# Gate: queue

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/queue#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `7df74b2` | 2026-10-28 04:47:15 -0700 | Credit Germán Méndez Bravo and bound Dubalu's years |
| HEAD (`origin/main` when pinned, 2026-11-01) | `981bf92` | 2026-11-01 03:48:16 -0800 | Bring the README to the family standard [skip ci] |

Library sources changed between them (docs, tests, benches, CI excluded): 2 files changed, 259 insertions(+), 121 deletions(-).

## Method (common to every machine)

- Two worktrees of one clone, at START and at HEAD. The bench source is HEAD's (or, where stated, a copy of it with the rows START cannot compile removed, or a micro-bench written for the gate, not kept); each is compiled twice, once with `-I <START tree>` (binary A) and once with `-I <HEAD tree>` (binary B), same compiler, flags and source path. A/A is a byte copy of A.
- Flags: `c++ -std=c++20 -O3 -DNDEBUG -pthread` (Apple clang 17.0.0: M4 Pro `clang-1700.3.19.1`, i9 `clang-1700.6.4.2`). Comparator libraries are not linked or fetched. Only `flat-map`'s bench finds them by itself (`__has_include`): `absl::btree_map` is on the default include path of both machines and `boost::container::flat_map` on the i9's only, so that bench has abseil rows on the M4 and boost and abseil rows on the i9 (controls: they run no code of this repo).
- Rounds: every round runs each bench entry with A, B and AA (order `a b aa` on odd rounds, `aa b a` on even ones), under one `quiet strict` hold per repo and machine (on macOS a strict hold is exclusive). `runab.sh` writes one file per run; `ab_compare.py compare --format unit` pairs run i of A with run i of B (and of AA) and reports the median ratio.
- **Ratio = START time / HEAD time, so above 1 means HEAD is faster.** Throughputs are converted to ns per item. `A/A max dev` is the largest |ratio - 1| of A against its own copy over the same rounds: the measurement's noise. Rows marked `(control)` run code the change cannot reach (a standard-library or baseline arm); they show the noise floor and are left out of the geomean.
- A row is listed as "<0.97 outside A/A" when its ratio is below 0.97 and also below 1/(1 + A/A max dev).

## What was measured

- `benchmark/bench.cc` (`queue_bench`): million items per second for a bounded-ish blocking MPMC channel of ints, `total` = 2,000,000 items, best of 3 runs, at 1x1, 2x2, 4x4 and 8x8 producers x consumers, for `queue::Queue<int>` (the library), a 30-line `std::mutex` + `condition_variable` + `std::deque` baseline and `moodycamel::BlockingConcurrentQueue`. The last two are controls (neither touches `queue.h`). Throughputs are converted to ns per item (1000 / Mitems/s) so that the ratio reads START/HEAD like every other gate row.
- **No row was dropped.** HEAD's bench fetches the moodycamel header with CMake; START vendors it under `third_party/concurrentqueue/`, and both binaries use START's copy (`-I <START>/third_party/concurrentqueue`).
- Library change in scope (`queue.h`, 377 lines changed): untimed waits no longer poll once a second, notifications are sent only when a waiter exists (blocked-waiter counts under the mutex), the four hot operations are force-inlined with an inline fast path, `_cnt` is stored with release ordering, and the wake-up fixes of 2026-10-31 and 2026-11-01 (every state change that can release a waiter wakes one that can use it; move assignment gives back its items).


### Apple M4 Pro

#### main (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| queue::Queue<int> 1x1 | 76.34 | 17.77 | 4.250 | 4.00-4.81 | 9.2% | 3 |
| queue::Queue<int> 2x2 | 185.5 | 49.33 | 3.753 | 3.51-3.76 | 1.7% | 3 |
| queue::Queue<int> 4x4 | 139.3 | 42.00 | 3.158 | 3.07-3.35 | 6.5% | 3 |
| queue::Queue<int> 8x8 | 109.5 | 30.72 | 3.599 | 3.45-3.72 | 2.2% | 3 |
| mutex+condvar+deque 1x1 (control) | 34.53 | 33.62 | 1.027 | 0.82-1.14 | 39.3% | 3 |
| mutex+condvar+deque 2x2 (control) | 57.57 | 56.31 | 1.022 | 0.93-1.08 | 5.9% | 3 |
| mutex+condvar+deque 4x4 (control) | 57.67 | 56.37 | 1.010 | 0.96-1.07 | 11.8% | 3 |
| mutex+condvar+deque 8x8 (control) | 49.83 | 50.76 | 1.006 | 0.97-1.01 | 14.5% | 3 |
| moodycamel::Blocking 1x1 (control) | 107.1 | 104.3 | 0.971 | 0.91-1.11 | 13.8% | 3 |
| moodycamel::Blocking 2x2 (control) | 150.6 | 165.3 | 0.911 | 0.90-0.92 | 10.8% | 3 |
| moodycamel::Blocking 4x4 (control) | 167.2 | 175.7 | 0.972 | 0.95-1.00 | 7.6% | 3 |
| moodycamel::Blocking 8x8 (control) | 179.5 | 174.2 | 1.032 | 0.96-1.17 | 5.6% | 3 |

**Geomean START/HEAD (Apple M4 Pro): 3.669** over 4 library rows (controls, 8 rows: 0.993)

Rows >1.03: 4; within 0.97-1.03: 0; <0.97: 0 (0 outside the A/A spread, 0 inside it).

### Intel i9-9980HK

#### main (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| queue::Queue<int> 1x1 | 335.6 | 97.28 | 3.438 | 3.33-3.51 | 2.7% | 3 |
| queue::Queue<int> 2x2 | 606.1 | 131.6 | 4.691 | 4.33-4.70 | 5.5% | 3 |
| queue::Queue<int> 4x4 | 909.1 | 191.6 | 4.619 | 4.57-5.25 | 7.3% | 3 |
| queue::Queue<int> 8x8 | 1190.5 | 219.3 | 5.241 | 5.13-5.94 | 10.1% | 3 |
| mutex+condvar+deque 1x1 (control) | 114.4 | 115.2 | 0.993 | 0.99-1.00 | 3.2% | 3 |
| mutex+condvar+deque 2x2 (control) | 170.1 | 159.7 | 1.049 | 0.99-1.11 | 10.8% | 3 |
| mutex+condvar+deque 4x4 (control) | 220.8 | 216.0 | 1.060 | 1.01-1.08 | 15.7% | 3 |
| mutex+condvar+deque 8x8 (control) | 268.1 | 264.6 | 0.997 | 0.94-1.02 | 9.6% | 3 |
| moodycamel::Blocking 1x1 (control) | 94.97 | 92.34 | 0.991 | 0.98-1.08 | 11.0% | 3 |
| moodycamel::Blocking 2x2 (control) | 134.8 | 135.3 | 1.000 | 1.00-1.04 | 2.8% | 3 |
| moodycamel::Blocking 4x4 (control) | 85.54 | 84.89 | 1.006 | 0.97-1.03 | 6.1% | 3 |
| moodycamel::Blocking 8x8 (control) | 63.78 | 61.58 | 1.036 | 0.96-1.04 | 24.1% | 3 |

**Geomean START/HEAD (Intel i9-9980HK): 4.445** over 4 library rows (controls, 8 rows: 1.016)

Rows >1.03: 4; within 0.97-1.03: 0; <0.97: 0 (0 outside the A/A spread, 0 inside it).

## Findings: queue

- **M4 Pro (3 rounds): `queue::Queue<int>` is 3.2-4.3x faster at every shape**: 1x1 4.25x (76.3 -> 17.8 ns per item), 2x2 3.75x (185.5 -> 49.3), 4x4 3.16x (139.3 -> 42.0), 8x8 3.60x (109.5 -> 30.7). A/A max dev 1.7-9.2%, and the worst paired ratio of any shape is 3.07x. Geomean 3.67 over the 4 library rows. The control arms, which run no code of this repo, read 1.01-1.03 (mutex+condvar+deque, geomean of its 4 rows 1.01) and 0.91-1.03 (moodycamel).
- **i9 (3 rounds, one strict hold, 13:22 to 13:25 on 2026-11-01): `queue::Queue<int>` is 3.4-5.2x faster at every shape**: 1x1 3.44x (335.6 -> 97.3 ns per item), 2x2 4.69x (606.1 -> 131.6), 4x4 4.62x (909.1 -> 191.6), 8x8 5.24x (1190.5 -> 219.3). A/A max dev 2.7-10.1%, and the worst paired ratio of any shape is 3.33x. Geomean 4.445 over the 4 library rows. The control arms read 0.99-1.06 (mutex+condvar+deque, geomean of its 4 rows 1.02) and 0.99-1.04 (moodycamel, 1.01); their A/A max dev reaches 15.7% and 24.1%, so single control rows move by that much.
- **Against the CHANGELOG's i9 table** (ratio of the mutex baseline's time to the queue's, 1x1 / 2x2 / 4x4 / 8x8): HEAD reads 1.18 / 1.21 / 1.13 / 1.21 here against the CHANGELOG's 1.16 / 1.25 / 1.16 / 1.17 after the inline fast path, so the owner's HEAD numbers reproduce. START reads 0.34 / 0.28 / 0.24 / 0.23 against the CHANGELOG's 0.92 / 0.71 / 0.57 / 0.55 "before"; that "before" is the state before the inline fast path, an intermediate commit and not START, so the gate's START gap is the larger one.
- **Rows below 0.97 outside the A/A spread: none** among the library rows on either machine. One M4 control row reads 0.911 (moodycamel 2x2, A/A 10.8%): noise in code this repo does not own.
- **Why:** START notified on every operation and re-checked every untimed wait once a second; HEAD counts blocked waiters under the mutex, notifies only when one exists, and runs the push/pop fast path inline.
- **Correctness changes that make no row not comparable:** the wake-up fixes (a state change that can release a waiter now wakes one that can use it: `clear()`, `QueueSet::erase`, a pop below the hard limit, destruction of a shared state) and move assignment giving back its items change only blocked or reassigning paths, which this bench never takes (`Queue<int>` here is unbounded and never blocks a producer).

**Verdict: FASTER** on both machines (M4 3.2-4.3x, geomean 3.67; i9 3.4-5.2x, geomean 4.45); no library row below 0.97.
