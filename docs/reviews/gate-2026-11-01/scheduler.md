# Gate: scheduler

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/scheduler#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `scheduler:ae3f0f9` (`ae3f0f9ca028de81b2c458e7320e2c922abba33b`) | 2026-10-28 04:47:25 -0700 | Credit Germán Méndez Bravo and bound Dubalu's years |
| HEAD (`origin/main`, fetched 2026-11-01 ~09:00) | `scheduler:1087108` (`1087108d906abec8f1bc6cc950f273f3182b917b`) | 2026-11-01 03:59:55 -0800 | Bring the README to the family standard [skip ci] |

Library sources changed between them (docs, tests, benches, CI, CMake excluded): `scheduler.h` only, 358 insertions and 19 deletions. `debouncer.h`, `callable_traits.hh` and `scheduler_trace.h` are byte-identical. What changed in `scheduler.h` (from `CHANGELOG.md`): `post()` / `post_ordered()` (lock-free producer hand-off; new API), `add()` skips the wake-up signal while the worker is awake, the lost-task fix (a `peep` under the mutex before the worker sleeps), the worker walks at once when a pass finds a task due, `add()` fences before it reads the published wakeup time. The debouncer's lazy re-arm is not new: it is already in START (2026-10-20, CHANGELOG entry 2026-10-28), contrary to the brief's hint.

## Method

- Rig: `$GATE/scheduler/` on both machines. Two worktrees of one clone, both at HEAD: `head/` as is, `start/` with `scheduler.h debouncer.h callable_traits.hh scheduler_trace.h` taken from START (`git rm` then `git checkout ae3f0f9 --`; `$GATE/raw/scheduler/m4/start-diffstat.txt`: `scheduler.h | 377 +++---` and nothing else). Both use HEAD's CMake, HEAD's `bench/bench_churn.cc` (byte-identical to START's) and HEAD's `bench/bench_post.cc`.
- `bench_post.cc` needs `post()` / `post_ordered()`, which START lacks. In `start/` only, those two `switch` arms are `std::abort()` and the mode list is `{make_only, add}` (`start-bench_post.patch` in the raw dir, 3 lines). **Dropped rows (HEAD only, no START counterpart):** `post()` and `post_ordered()` at 1 and 4 producer threads. Their HEAD numbers are listed below for reference.
- Dependencies frozen and byte-identical on both sides, on both machines (HEAD's CMake pins; `start/` is configured with `-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_{STASH,THREADPOOL,RANDOM}` pointing at `head/build/_deps/*-src`): `stash:78a18f3162de8d482fa2e3c480d1a3e9cf862537`, `threadpool:628679a2e27b563cf2709a6f35f98f1657baf7b3`, `random:a6c4f6c1d2d82d03c73f421a624de238edc823c5`. START's own CMake pinned `stash:351ef2e` and `random:6487253`; they are not used here, so the numbers isolate `scheduler.h` (START's wheel inserts run on HEAD's faster stash; a START-with-its-own-stash column was not measured).
- Compiler (both machines): Apple clang 17.0.0, `/usr/bin/clang++`, CMake `-G Ninja -DCMAKE_BUILD_TYPE=Release -DSCHEDULER_BENCH=ON` = `-O3 -DNDEBUG -std=gnu++20`, no `-march`. M4: `clang-1700.3.19.1`, arm64, macOS 26.7.2, CMake 4.4.5, 14 cores. i9: `clang-1700.6.4.2`, x86_64, macOS 15.8.1, CMake 4.4.4, i9-9980HK 8 cores / 16 threads.
- Builds ran as `nice -n 19 cmake --build {head,start}/build --target scheduler_bench_churn scheduler_bench_post -j4` **outside a hold**: the `quiet light` request was starved for more than 15 minutes by queued strict holds (M4 09:06 to 09:21, i9 09:08 to 09:24), which the recipe allows. Each build took about 2 s. Each binary was smoke-run once, unheld, before the strict hold (all rows present).
- Measurement: one `quiet strict` hold per machine running `gate.sh` (in the raw dir). `ab_compare.py run` interleaves A = START binary, B = HEAD binary and A/A = START again every round. Threads are the benches' own: `bench_post` runs 1 and 4 producer threads plus the scheduler's worker thread; `bench_churn` runs 2 producer threads and the debouncer's 2-thread scheduler.
  - `bench_post` (no arguments; 200 000 tasks per producer, median of 5 inside each run), 9 rounds: `ab_compare.py run --rounds 9 --save OUT/post --section '^--- (\d+ producer thread\(s\))' --regex '^(?P<row>\S.*?)\s+median\s+(?P<value>[0-9.]+)\s' bin/post.start bin/post.head`. Value = the bench's median ns per task.
  - `bench_churn` (`15 100000 1000 2 4 400 1200 2000`: 15 s of 100 000 touches/s over 1000 keys from 2 threads, then a 4 s drain; the committer's debounce / busy / force timeouts of 1 s / 3 s / 8 to 10 s are shortened to 0.4 s / 1.2 s / 2 s with the bench's own knobs, so a run is 19 s), 5 rounds: `ab_compare.py run --rounds 5 --save OUT/churn --regex '^peak:.*(?P<row>CPU) (?P<value>[0-9.]+) (?P<unit>s)$' bin/churn.start bin/churn.head -- 15 100000 1000 2 4 400 1200 2000`. The bench is rate-paced (touches/s are fixed), so wall time says nothing; the cost is the process CPU seconds it prints. `bin/churn.{start,head}` are 5-line wrappers that print `bench exit N` and exit 0, so a lost-task exit code 1 would not abort `ab_compare`. Peak heap, peak RSS, touches and calls fired are read from the same saved runs and shown as informational rows (the heap is printed to 0.1 MB: quantised).
  - The tables are `ab_compare.py compare --output csv` over the saved runs, formatted by `mkrep.py`. `A/A spread` is the largest |A/A ratio - 1| over the rounds. A row is called slower when its ratio is below 0.97 and ab_compare's verdict is `slower` (ratio / (1 + A/A spread) < 1).
- Confirm holds: the `make only` rows were flagged slower on one machine only, so a second short strict hold per machine (`confirm.sh`) re-ran `bench_post` alone for 15 rounds (same binaries). They are the last section of the results.
- Ratio = START / HEAD for times, so above 1 means HEAD is faster. The `make only` rows time `std::make_shared<Trivial>()`, the bench's baseline for the cost every other row shares; `Trivial` derives from the library's `ScheduledTask`, so it is not a pure control (see the findings).

## Results

### Apple M4 Pro (the M4 Pro)

#### bench_post median ns/task

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / make only | 37.3 | 38.2 | 0.961 | 0.84-1.01 | 1.008 | 4.7% | 9 | noise |
| 1 producer thread(s) / add() | 201.9 | 201.3 | 1.006 | 0.88-1.09 | 1.018 | 15.8% | 9 | noise |
| 4 producer thread(s) / make only | 43.7 | 45.4 | 0.909 | 0.82-1.02 | 0.965 | 8.5% | 9 | slower |
| 4 producer thread(s) / add() | 896.6 | 645.9 | 1.397 | 1.31-1.51 | 0.987 | 5.9% | 9 | faster |

#### bench_post min ns/task (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / make only | 36.9 | 37.2 | 0.976 | 0.85-1.01 | 1.008 | 2.5% | 9 | noise |
| 1 producer thread(s) / add() | 182.0 | 181.3 | 1.059 | 0.85-1.16 | 1.007 | 23.5% | 9 | noise |
| 4 producer thread(s) / make only | 39.9 | 43.3 | 0.936 | 0.86-0.96 | 0.990 | 5.5% | 9 | slower |
| 4 producer thread(s) / add() | 878.5 | 594.7 | 1.501 | 1.30-1.79 | 0.990 | 4.6% | 9 | faster |

#### bench_churn CPU s

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CPU | 0.820 | 0.790 | 1.114 | 0.89-1.13 | 0.901 | 32.4% | 5 | noise |

#### bench_churn peak heap MB (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| heap | 0.900 | 0.900 | 1.000 | 0.87-1.12 | 1.000 | 28.6% | 5 | noise |

#### bench_churn peak RSS MB (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| RSS | 3.200 | 3.100 | 1.032 | 0.94-1.06 | 1.031 | 6.5% | 5 | noise |

#### bench_churn touches (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| touches | 1.5e+06 | 1.5e+06 | 1.000 | 1.00-1.00 | 1.000 | 0.0% | 5 | noise |

#### bench_churn fired (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| fired | 8000.0 | 8000.0 | 1.000 | 1.00-1.00 | 1.000 | 0.0% | 5 | noise |

geomean over 5 primary rows: 1.064

rows < 0.97 outside the A/A spread:
- bench_post median ns/task: 4 producer thread(s) / make only: 0.909 (A/A spread 8.5%)

### Intel i9-9980HK

#### bench_post median ns/task

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / make only | 145.5 | 152.3 | 0.943 | 0.87-1.04 | 0.992 | 6.7% | 9 | noise |
| 1 producer thread(s) / add() | 399.6 | 411.6 | 0.977 | 0.93-1.02 | 0.989 | 6.3% | 9 | noise |
| 4 producer thread(s) / make only | 140.2 | 151.0 | 0.929 | 0.89-0.98 | 0.969 | 8.0% | 9 | noise |
| 4 producer thread(s) / add() | 1683.0 | 636.0 | 2.593 | 2.51-2.99 | 0.995 | 12.7% | 9 | faster |

#### bench_post min ns/task (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / make only | 136.1 | 145.2 | 0.906 | 0.84-1.07 | 1.023 | 11.2% | 9 | noise |
| 1 producer thread(s) / add() | 396.6 | 400.7 | 0.981 | 0.94-1.04 | 0.999 | 7.4% | 9 | noise |
| 4 producer thread(s) / make only | 136.3 | 143.5 | 0.944 | 0.92-0.97 | 0.989 | 7.6% | 9 | noise |
| 4 producer thread(s) / add() | 1583.4 | 574.3 | 2.737 | 2.62-3.04 | 1.009 | 23.2% | 9 | faster |

#### bench_churn CPU s

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CPU | 2.550 | 2.540 | 1.000 | 0.87-1.58 | 1.011 | 19.0% | 5 | noise |

#### bench_churn peak heap MB (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| heap | 0.800 | 0.900 | 0.900 | 0.87-1.00 | 1.000 | 14.3% | 5 | noise |

#### bench_churn peak RSS MB (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| RSS | 4.400 | 4.600 | 0.956 | 0.93-0.98 | 1.000 | 2.3% | 5 | slower |

#### bench_churn touches (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| touches | 1.5e+06 | 1.5e+06 | 1.000 | 1.00-1.00 | 1.000 | 0.0% | 5 | noise |

#### bench_churn fired (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| fired | 8000.0 | 8000.0 | 1.000 | 1.00-1.00 | 1.000 | 0.0% | 5 | noise |

geomean over 5 primary rows: 1.173

rows < 0.97 outside the A/A spread:
- none

### Confirm holds (bench_post alone, 15 rounds, same binaries)

#### m4

##### bench_post median ns/task

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / make only | 36.1 | 37.4 | 0.965 | 0.92-0.99 | 1.006 | 3.4% | 15 | slower |
| 1 producer thread(s) / add() | 163.0 | 160.4 | 0.978 | 0.88-1.15 | 0.987 | 20.8% | 15 | noise |
| 4 producer thread(s) / make only | 40.2 | 43.9 | 0.921 | 0.88-1.02 | 1.005 | 11.5% | 15 | noise |
| 4 producer thread(s) / add() | 849.4 | 648.8 | 1.307 | 1.22-1.39 | 0.988 | 9.3% | 15 | faster |

##### bench_post min ns/task (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / make only | 35.4 | 36.6 | 0.970 | 0.96-0.99 | 0.997 | 2.0% | 15 | slower |
| 1 producer thread(s) / add() | 144.5 | 142.7 | 1.013 | 0.87-1.10 | 1.030 | 13.5% | 15 | noise |
| 4 producer thread(s) / make only | 39.4 | 41.8 | 0.945 | 0.90-1.04 | 1.000 | 2.9% | 15 | slower |
| 4 producer thread(s) / add() | 784.9 | 621.2 | 1.275 | 1.13-1.40 | 1.020 | 16.1% | 15 | faster |

geomean over 4 primary rows: 1.033

rows < 0.97 outside the A/A spread:
- bench_post median ns/task: 1 producer thread(s) / make only: 0.965 (A/A spread 3.4%)

#### i9

##### bench_post median ns/task

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / make only | 131.1 | 135.2 | 0.962 | 0.87-1.07 | 0.989 | 10.2% | 15 | noise |
| 1 producer thread(s) / add() | 390.9 | 395.7 | 0.981 | 0.92-1.04 | 1.006 | 4.3% | 15 | noise |
| 4 producer thread(s) / make only | 137.2 | 146.7 | 0.965 | 0.86-1.01 | 0.993 | 7.5% | 15 | noise |
| 4 producer thread(s) / add() | 1568.5 | 615.1 | 2.569 | 2.37-2.69 | 0.991 | 9.5% | 15 | faster |

##### bench_post min ns/task (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / make only | 125.0 | 130.1 | 0.958 | 0.88-1.04 | 1.000 | 5.8% | 15 | noise |
| 1 producer thread(s) / add() | 381.9 | 387.5 | 0.987 | 0.94-1.02 | 1.003 | 3.6% | 15 | noise |
| 4 producer thread(s) / make only | 134.4 | 141.1 | 0.956 | 0.90-1.02 | 0.999 | 8.0% | 15 | noise |
| 4 producer thread(s) / add() | 1499.2 | 563.3 | 2.623 | 2.48-2.89 | 1.005 | 8.9% | 15 | faster |

geomean over 4 primary rows: 1.237

rows < 0.97 outside the A/A spread:
- none


## Findings

### Rows < 0.97 outside the A/A spread

| machine | row | START | HEAD | START/HEAD | cause |
|---|---|---:|---:|---:|---|
| M4 | 1 producer, `make only` (confirm hold, 15 rounds; A/A spread 3.4%) | 36.1 ns | 37.4 ns | 0.965 | `ScheduledTask` 48 to 96 B, below. The main hold read 0.961 (inside its 4.7% spread). |
| M4 | 4 producers, `make only` (main hold, 9 rounds; A/A spread 8.5%) | 43.7 ns | 45.4 ns | 0.909 | same. The confirm hold read 0.921 inside an 11.5% spread (its `min` column 0.945, outside a 2.9% spread). |
| i9 | none outside the spread; the same two rows read 0.943 and 0.929 (main) and 0.962 and 0.965 (confirm) | 131 to 146 ns | 135 to 152 ns | 0.93 to 0.97 | same cause and direction, but inside A/A spreads of 6.7 to 10.2%, so by the rule it is not counted |

**Cause (a library cost, small).** The only rows that are not faster or unchanged are the two `make only` rows, which time `std::make_shared<Trivial>()` where `Trivial` derives from the library's `ScheduledTask`. HEAD's `ScheduledTask` gained the `post()` hand-off fields (`post_next`, `post_hold` (a `shared_ptr`), `post_ordered`, `ingest_seq`): `sizeof(ScheduledTask)` (and of `Trivial`) is **48 bytes at START and 96 bytes at HEAD** (`sizeof.cc`, measured on both machines; the `make_shared` block grows from about 64 to about 112 bytes). Every task the caller allocates is that much larger and is zero-initialised, which costs 1 to 4 ns (3 to 8 percent of a 37 to 45 ns allocation) on the M4 and 7 to 11 ns (5 to 8 percent of 140 to 150 ns) on the i9, and 48 more bytes of memory per live task. It is the price of `post()` / `post_ordered()` (CHANGELOG 2026-10-31, "producer hand-off"); an `add()`-only user pays it without using `post()`. The `add()` rows contain the same allocation, so at one thread their net `add()` cost is unchanged within noise (START 254 ns, HEAD 259 ns on the i9 after subtracting `make only`; M4 164 and 163 ns).

Unexplained rows: none.

### What improved

- `add()` from four producers: **1.40x faster on the M4 (896.6 to 645.9 ns per task, 1.31 in the 15-round confirm) and 2.59x on the i9 (1683 to 636 ns)**. Causes in the CHANGELOG: `add()` skips the wake-up signal while the worker is awake (2026-10-31), and a worker pass that finds a task due walks at once without taking the mutex (audit S2), so producers no longer queue on the mutex to signal a worker that is not asleep.
- `add()` from one producer: unchanged within noise (M4 1.006 / 0.978 in the confirm, i9 0.977).
- `bench_churn` (debouncer touches, 100 000/s): CPU 0.82 s to 0.79 s (M4) and 2.55 s to 2.54 s (i9), inside a 19 to 32 percent A/A spread, so unchanged. Peak heap, peak RSS and the debouncer's tasks alive are unchanged (1000 keys: about 1000 tasks alive, heap under 1 MB), touches are paced to 1 500 500 and the calls fired are 8000 on both sides, and **every touched key fired its last touch on both sides (`keys whose last touch never fired: 0`, 5 of 5 runs, both machines)**. The i9 shows peak RSS 4.4 to 4.6 MB (ratio 0.956, outside a 2.3 percent spread, the M4 does not): 48 more bytes times about a thousand live tasks is 48 KB, so the task size explains little of the 0.2 MB; it is an informational row, not in the geomean, and I did not chase it. The debouncer's lazy re-arm that makes this bench cheap is already in START, so the bench cannot show a gain.
- New API with no START counterpart (rows dropped): `post()` and `post_ordered()`. HEAD's medians for reference, ns per task including the 38 to 150 ns `make only`: M4 1 producer 56.7 and 89.4, 4 producers 587.1 and 688.6 (`add()` 201.3 and 645.9); i9 1 producer 157.5 and 160.3, 4 producers 285.1 and 300.6 (`add()` 411.6 and 636.0). On the i9 with four producers `post()` costs less than half of `add()`.

### Rows dropped or not comparable

- `post()` and `post_ordered()` rows (new API, 8 rows of HEAD data above): no START counterpart; START's bench copy aborts if reached and does not list them.
- Correctness changes in range: the lost-task fix (a `peep` under the mutex before the worker sleeps) adds a little work to every worker sleep, and START's window (about one `add()` in 60 000 in a 20 000-task burst soak, CHANGELOG 2026-10-31) did not show in `bench_churn` (0 stale keys on both sides), so it does not make a row incomparable.
- The stash pin is HEAD's on both sides (frozen), so START's `add()` runs on the faster stash HEAD pins (CHANGELOG: one producer's `add()` of tasks due now 390 to 224 ns on the M4 from the stash pin alone, a CHANGELOG figure that this gate did not measure). A user who upgrades scheduler and stash together gains more on `add()` than the fixed-dependency numbers show.

### Holds and load

| machine | hold | queued | started | ended | uptime load (1, 5, 15 min) at start / at end |
|---|---|---|---|---|---|
| M4 | M4 hold (main) | 09:23 | 10:20:54 | 10:26:34 | 15.56 16.77 16.41 / 13.06 14.83 15.73 |
| M4 | M4 hold confirm (`bench_post`, 15 rounds) | 11:14 | 12:16:10 | 12:17:29 | 7.37 7.96 8.49 / 8.52 8.19 8.53 |
| i9 | i9 hold (main) | 09:27; the waiter died at 10:27 when the remote command's 3600 s timeout expired, requeued 10:29 | 11:05:04 | 11:11:29 | 9.38 8.23 7.79 / 2.89 5.56 6.75 |
| i9 | i9 hold confirm (`bench_post`, 15 rounds) | 11:14 | 12:43:49 | 12:46:26 | 8.13 6.62 6.53 / 8.01 6.68 6.53 |

On macOS a strict hold is exclusive, yet the M4 load average was 13 to 17 at the start of the main hold (other jobs' non-`quiet` work, which is not ours to stop) and 7 to 9 in the confirm; the A/A control absorbs it and bounds what the tables can resolve (the churn CPU row cannot resolve better than about plus or minus 20 percent at this load; `bench_post` rows resolve 3 to 10 percent). The builds ran unheld after `quiet light` starved for more than 15 minutes (recipe).

Raw per-run files, ab_compare outputs and hold logs: `$GATE/raw/scheduler/{m4,i9,m4-confirm,i9-confirm}/` (`post/ churn/` runs, `*.md`, `uptime.txt`, `hold-*.log`, `start-bench_post.patch`); scripts `gate.sh confirm.sh build.sh mkrep.py sizeof.cc`.

SUMMARY repo=scheduler m4_geomean=1.064 i9_geomean=1.173 m4_slow=2/0.909 i9_slow=0/- unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 "make only" with 1 producer 0.965 and 4 producers 0.909: fixed in `scheduler:eb2483b` and
  `e7b4f83`. The hand-off and filing fields share one union, and `ScheduledTask` no longer derives
  `std::enable_shared_from_this`, so a task is 56 bytes. "make only" is 10% to 15% faster than start:
  30.7 and 35.6 ns on the M4 Pro (start 35.9 and 40.4), 119.8 and 125.8 ns on the i9 (start 134.8 and
  139.5). [scheduler#2](https://github.com/Kronuz/scheduler/issues/2) is closed.
