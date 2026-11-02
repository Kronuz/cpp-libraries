# threadpool gate: START vs HEAD

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/threadpool#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Question: is `threadpool` at HEAD substantially better than at the start of the campaign, and is any row slower than it was?

**Answer: much faster on the rows it was built for, with one confirmed slower row family.** `ThreadPool::enqueue` of a trivial task is 3.4x to 33x faster on both machines (library-row geomean 2.0x on the M4 Pro, 2.3x on the i9), the bare-pool burst is 15x to 25x faster, the pool's CPU per task at one task per microsecond is 3.7x lower on the i9 (1.1x to 2.1x on the M4 Pro), the median start delay is up to 2.9x lower, and the idle CPU of 4 and 8 workers and a future round trip are unchanged. Two things are slower and reproduced: a `TaskGroup` burst on a pool with 14 to 16 workers (HEAD takes 3.6x as long on the i9 and 5.5x on the M4 Pro in the confirmation holds; at 4 workers HEAD is 1.4x to 1.5x faster) and, on the i9 only, the p99 start delay at one task per microsecond (0.62x). The verdict is SLOWER-ROWS by the gate's rule.

## Setup

| | |
|---|---|
| START | `e961e447f9ea444081b9f13a68f82d633d499fc4`, 2026-10-29 22:14 -0700 (last `origin/main` commit before 2026-10-30) |
| HEAD | `287b87740d667419e632799b34566db639dd023e`, 2026-11-01 06:06 -0800 |
| Library change | `12f1516` "Give ThreadPool its own queue and small-buffer tasks": `threadpool.hh` (126 lines changed), new `pool_queue.h` and `small_task.h`. The other seven commits are tests, the benchmark, docs and README. |
| M4 | Apple M4 Pro, 14 cores (10P+4E), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5 |
| i9 | Intel i9-9980HK, 8 cores / 16 threads, macOS 15.8.1, Apple clang 17.0.0 (clang-1700.6.4.2), CMake 4.4.4 |
| Flags | `-DCMAKE_BUILD_TYPE=Release` (`-O3 -DNDEBUG`), `-std=gnu++20`, no `-march`, `-DCMAKE_CXX_COMPILER=/usr/bin/clang++`, Ninja; START additionally `-DGATE_NO_POST` (below) |
| Asio | 1.30.2, `12e0ce9e0500bf0f247dbd1ae894272656456079`, one checkout fetched on the M4 and the same SHA on the i9, passed as `-DASIO_INCLUDE_DIR` to both trees |

START tree: HEAD's tree (HEAD's CMake, `bench/`, `test/`) with only the library's own files taken from START (`threadpool.hh thread.hh thread.cc task_group.hh work_pool.hh concurrent_queue.h blocking_concurrent_queue.h likely.h config.h.in threadpool_trace.h`) and `pool_queue.h`, `small_task.h` removed. `git diff --cached --stat HEAD` in the START tree:

```
 pool_queue.h  | 344 ----------------------------------------------------------
 small_task.h  | 174 -----------------------------
 threadpool.hh | 126 +++++++--------------
 3 files changed, 39 insertions(+), 605 deletions(-)
```

Benchmarks (HEAD's sources, built twice):

- `bench/enqueue_bench.cc` (new at HEAD, never existed at START). It compiles against START's `ThreadPool` except one call, `new_pool.post(...)`, an API added at HEAD. A three-line `#ifndef GATE_NO_POST` guard around that one latency row (`$GATE/raw/threadpool/scripts/gate-bench.patch`) is applied to the bench in both trees; the START build defines `GATE_NO_POST`. Dropped row: `latency new post+promise` (HEAD only). Nothing else differs.
- `bench/kernel_time.cc` (exists at START, unchanged): rows `today` (bare `ThreadPool`) and `today-tg` (`TaskGroup` over it) exercise the changed code; `workpool`, `workgroup` and `condvar` do not and are controls.
- `bench/research_ab.sh` and `bench/work_pool_research.hh` build the research harness for the WorkPool prototypes; `ThreadPool` appears there only as one of several baselines, so they are not run.
- The bench's `old ThreadPool` column is `test/threadpool_old.hh`, which differs from START's `threadpool.hh` only by a header comment and a `namespace threadpool_old` wrapper (`diff` checked), so in either binary it is START's code: a control that shares the process with the pool under test. In the START binary `old` and `new` are the same code (geomean of old/new over the 18 grid cells of the 3 runs: 1.09 on the M4 Pro, 1.05 on the i9).
- `mutex+cv naive` and `asio::thread_pool` rows are controls.

Knobs (one run of the whole mode is 10 to 30 s; the bench defaults are 7 reps x 100 000 tasks):

| group | command (ARGS after `--`) | rounds |
|---|---|---|
| grid | `enqueue_bench 4 20000`: W in {1,4,8} x P in {1,4} x {shared, local, cap40}; min of 4 reps after a warm-up | 3 |
| latency | `enqueue_bench 5 1 latency`: `async(f).get()`, 4 workers | 3 |
| trickle | `enqueue_bench 1 5000 trickle`: 1 producer, a task per 1000 / 5000 / 50 000 ns, 4 workers, start delay median and p99, pool CPU per task | 3 |
| idle | `enqueue_bench 1 1 idle`: CPU of 4 and 8 idle workers over 4 s | 3 |
| kernel | `kernel_time 1`: user, sys per op, one trial, 14 workers (M4) / 16 workers (i9) | 3 |
| confirmation hold | `kernel_time 1`, `kernel_time 1 4`, `enqueue_bench 1 20000 trickle` | 3 each |

Each group is one `ab_compare.py run --format unit --rounds 3 --save DIR START HEAD -- ARGS` (A, B, A again per round, interleaved), through a wrapper (`norm.py`) that re-emits the bench tables as `label  12.3 ns` rows (the grid's `min` per cell; throughputs are not involved). `ab_compare` prints every unit as ns: idle rows are CPU microseconds per second x 1000 (1 280 000 = 1.28 ms per second = 0.128% of a core); `kt ... user/sys` are microseconds per op x 1000 (per second of idle for the idle rows). `kt handoff` rows are dominated by the bench's own 20 000-pause gap (about 0.19 ms on the M4, 0.8 ms on the i9) and say nothing about the pool; they are kept for completeness. Ratio = START/HEAD, above 1 means HEAD is faster. "A/A" is the median of A against A; "A/A dev" the largest |ratio-1| of an A/A pair; a row is "slower" when ratio x (1 + A/A dev) < 1.

Commands:

```
prep (both machines):  $GATE/raw/threadpool/scripts/prep.sh      # worktrees, overlay, cmake -G Ninja ... -DTHREADPOOL_BUILD_BENCH=ON -DASIO_INCLUDE_DIR=...
build:                 nice -n 19 cmake --build build-{head,start} --target enqueue_bench kernel_time -j4    # unheld, see rig notes
hold 1:                quiet strict 10 "..." -- ./hold.sh {m4,i9}                      # grid latency trickle idle kernel
hold 2 (confirm):      quiet strict 10 "..." -- ./hold2.sh {m4,i9}                   # kernel kernelt4 trickle(N=20000)
raw: $GATE/raw/threadpool/{m4,i9}/ (hold 1), $GATE/raw/threadpool/{m4,i9}/confirm/ (hold 2); every group has a-NNN/b-NNN/aa-NNN (START/HEAD/START again), <group>.md (ab_compare's own table, all rows incl. controls), rawbench/ (the benches' own output)
```

## Apple M4 Pro

Hold 1 (M4 hold): 2026-11-01 10:13:18 to 10:19:50. `uptime` at start `load averages: 20.78 14.96 15.63`, at end `19.28 17.50 16.62` (other sessions' processes; the hold was exclusive; A/A geomean 0.92 shows it: the grid rows are 3x to 10x so they are unaffected, the p99 rows are not usable here).
Hold 2 (M4 hold c, confirmation): 12:04:37 to 12:11:15, load `6.55 8.24 9.36` to `6.66 7.22 8.44` (quieter).

### threadpool m4: groups grid(3 A, 3 B, 3 A/A), idle(3 A, 3 B, 3 A/A), kernel(3 A, 3 B, 3 A/A), latency(3 A, 3 B, 3 A/A), trickle(3 A, 3 B, 3 A/A)

| group | row | START | HEAD | START/HEAD | range | A/A | A/A dev | n | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| grid | enq shared P1xW1 new ThreadPool min | 57.6 | 12.9 | 5.318 | 3.13-5.82 | 0.858 | 0.297 | 3 | faster |
| grid | enq local P1xW1 new ThreadPool min | 59.8 | 17.7 | 3.437 | 2.97-3.53 | 0.927 | 0.122 | 3 | faster |
| grid | enq cap40 P1xW1 new ThreadPool min | 92.6 | 17.5 | 5.197 | 4.82-5.72 | 1.234 | 0.381 | 3 | faster |
| grid | enq shared P4xW1 new ThreadPool min | 77.3 | 15.3 | 5.052 | 3.28-5.96 | 0.996 | 0.197 | 3 | faster |
| grid | enq local P4xW1 new ThreadPool min | 80.4 | 13.2 | 5.591 | 4.00-6.63 | 0.937 | 0.097 | 3 | faster |
| grid | enq cap40 P4xW1 new ThreadPool min | 120.2 | 12.7 | 9.519 | 8.89-10.02 | 0.986 | 0.082 | 3 | faster |
| grid | enq shared P1xW4 new ThreadPool min | 206.5 | 39.6 | 5.188 | 4.72-5.33 | 1.032 | 0.341 | 3 | faster |
| grid | enq local P1xW4 new ThreadPool min | 210.2 | 37.5 | 5.171 | 5.10-5.61 | 0.950 | 0.050 | 3 | faster |
| grid | enq cap40 P1xW4 new ThreadPool min | 197.4 | 37.8 | 4.700 | 2.19-9.87 | 0.865 | 0.758 | 3 | faster |
| grid | enq shared P4xW4 new ThreadPool min | 143.5 | 34.9 | 3.727 | 3.54-4.44 | 0.979 | 0.134 | 3 | faster |
| grid | enq local P4xW4 new ThreadPool min | 135.7 | 33.6 | 4.310 | 3.21-4.45 | 0.916 | 0.217 | 3 | faster |
| grid | enq cap40 P4xW4 new ThreadPool min | 226.0 | 37.4 | 6.043 | 5.54-6.88 | 0.982 | 0.020 | 3 | faster |
| grid | enq shared P1xW8 new ThreadPool min | 311.6 | 57.1 | 6.438 | 3.05-19.76 | 0.347 | 3.632 | 3 | faster |
| grid | enq local P1xW8 new ThreadPool min | 366.0 | 51.4 | 10.027 | 3.58-10.98 | 0.778 | 2.380 | 3 | faster |
| grid | enq cap40 P1xW8 new ThreadPool min | 472.6 | 37.3 | 10.991 | 10.35-20.59 | 0.960 | 0.663 | 3 | faster |
| grid | enq shared P4xW8 new ThreadPool min | 142.3 | 34.1 | 4.564 | 4.12-4.81 | 1.035 | 0.166 | 3 | faster |
| grid | enq local P4xW8 new ThreadPool min | 159.7 | 35.0 | 4.563 | 3.59-6.48 | 1.157 | 0.336 | 3 | faster |
| grid | enq cap40 P4xW8 new ThreadPool min | 243.7 | 31.9 | 7.639 | 6.42-10.63 | 0.978 | 0.199 | 3 | faster |
| idle | idle new ThreadPool w=4 cpu-per-s | 380000 | 390000 | 0.974 | 0.95-1.14 | 1.000 | 0.079 | 3 | noise |
| idle | idle new ThreadPool w=8 cpu-per-s | 740000 | 770000 | 0.948 | 0.89-1.00 | 0.974 | 0.075 | 3 | noise |
| kernel | kt handoff today wall | 188200 | 189600 | 0.997 | 0.98-1.01 | 0.997 | 0.020 | 3 | noise |
| kernel | kt handoff today user | 186388 | 187937 | 0.996 | 0.98-1.01 | 0.997 | 0.017 | 3 | noise |
| kernel | kt handoff today sys | 6799.0 | 6457.0 | 1.071 | 0.97-1.10 | 1.013 | 0.091 | 3 | noise |
| kernel | kt burst today wall | 3580.0 | 210.0 | 17.048 | 3.83-26.21 | 1.323 | 0.668 | 3 | faster |
| kernel | kt burst today user | 1045.0 | 206.0 | 4.845 | 1.97-5.07 | 1.270 | 0.609 | 3 | faster |
| kernel | kt burst today sys | 12686.0 | 1162.0 | 10.917 | 2.52-17.01 | 1.310 | 0.707 | 3 | faster |
| kernel | kt idle today user | 229000 | 236000 | 0.981 | 0.86-1.00 | 0.974 | 0.165 | 3 | noise |
| kernel | kt idle today sys | 1035500 | 1143500 | 0.906 | 0.90-1.10 | 1.030 | 0.122 | 3 | noise |
| kernel | kt handoff today-tg wall | 188800 | 186800 | 1.012 | 0.96-1.02 | 0.992 | 0.013 | 3 | noise |
| kernel | kt handoff today-tg user | 187346 | 185343 | 1.013 | 0.97-1.02 | 0.997 | 0.010 | 3 | faster |
| kernel | kt handoff today-tg sys | 6612.0 | 6276.0 | 1.073 | 0.87-1.08 | 0.962 | 0.057 | 3 | faster |
| kernel | kt burst today-tg wall | 510.0 | 935.0 | 0.599 | 0.32-1.57 | 0.709 | 0.446 | 3 | slower |
| kernel | kt burst today-tg user | 605.0 | 694.0 | 0.895 | 0.67-1.09 | 0.861 | 0.204 | 3 | noise |
| kernel | kt burst today-tg sys | 2999.0 | 4934.0 | 0.608 | 0.28-2.88 | 0.572 | 0.706 | 3 | noise |
| kernel | kt idle today-tg user | 232000 | 258500 | 0.897 | 0.87-1.14 | 1.000 | 0.115 | 3 | noise |
| kernel | kt idle today-tg sys | 1061000 | 1107000 | 1.022 | 0.95-1.15 | 0.948 | 0.148 | 3 | noise |
| latency | latency new async #1 | 9304.0 | 9065.0 | 1.026 | 1.00-1.18 | 1.093 | 0.291 | 3 | noise |
| latency | latency new async #2 | 8110.0 | 8372.0 | 1.141 | 0.86-1.14 | 1.042 | 0.179 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool delay-median #1 | 8209.0 | 2875.0 | 2.855 | 1.29-3.92 | 0.810 | 0.242 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-p99 #1 | 42708.0 | 97792.0 | 0.464 | 0.11-2.37 | 0.458 | 0.810 | 3 | slower |
| trickle | trickle gap=1000 new ThreadPool pool-cpu #1 | 2216.0 | 1280.0 | 2.081 | 0.97-3.03 | 1.125 | 0.138 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-median #2 | 8125.0 | 3166.0 | 2.566 | 1.68-2.74 | 0.907 | 0.354 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-p99 #2 | 48041.0 | 17250.0 | 1.976 | 0.15-5.01 | 0.810 | 0.773 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool pool-cpu #2 | 2148.0 | 1855.0 | 1.085 | 1.01-3.01 | 0.993 | 0.110 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool delay-median #1 | 3542.0 | 3417.0 | 1.000 | 0.84-1.05 | 0.955 | 0.069 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool delay-p99 #1 | 23334.0 | 21542.0 | 1.190 | 0.03-1.32 | 0.674 | 0.812 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool pool-cpu #1 | 5728.0 | 5890.0 | 0.970 | 0.90-1.23 | 0.912 | 0.129 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool delay-median #2 | 3584.0 | 3375.0 | 1.037 | 1.02-1.12 | 1.000 | 0.083 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool delay-p99 #2 | 34250.0 | 25000.0 | 1.225 | 0.81-11.36 | 1.435 | 11.173 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool pool-cpu #2 | 5654.0 | 5970.0 | 0.947 | 0.86-0.96 | 0.911 | 0.135 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-median #1 | 6792.0 | 6625.0 | 1.025 | 1.01-1.05 | 0.975 | 0.030 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-p99 #1 | 56375.0 | 62833.0 | 0.873 | 0.78-1.18 | 0.348 | 1.071 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool pool-cpu #1 | 4647.0 | 4444.0 | 1.091 | 1.05-1.12 | 1.042 | 0.064 | 3 | faster |
| trickle | trickle gap=50000 new ThreadPool delay-median #2 | 6708.0 | 6958.0 | 0.964 | 0.89-1.04 | 1.012 | 0.038 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-p99 #2 | 37458.0 | 71667.0 | 0.523 | 0.14-86.87 | 0.893 | 60.282 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool pool-cpu #2 | 4031.0 | 4325.0 | 0.839 | 0.79-1.03 | 0.896 | 0.222 | 3 | noise |

- library rows: 56, geomean 2.009; A/A geomean 0.922
- control rows (unchanged code): 138, geomean 0.944, median 0.978, min 0.155, max 3.662
- supplementary median-of-reps rows (library): 18, geomean 6.180
- per-group geomean: grid 5.658 (n=18), idle 0.961 (n=2), kernel 1.422 (n=16), latency 1.082 (n=2), trickle 1.128 (n=18)
- slow rows (<0.97 and outside A/A): 2
  - kernel / kt burst today-tg wall: 0.599 (range 0.32-1.57, A/A dev 0.446)
  - trickle / trickle gap=1000 new ThreadPool delay-p99 #1: 0.464 (range 0.11-2.37, A/A dev 0.810)
- rows <0.97 but inside the A/A spread: 10
  - idle / idle new ThreadPool w=8 cpu-per-s: 0.948 (range 0.89-1.00, A/A dev 0.075)
  - kernel / kt idle today sys: 0.906 (range 0.90-1.10, A/A dev 0.122)
  - kernel / kt burst today-tg user: 0.895 (range 0.67-1.09, A/A dev 0.204)
  - kernel / kt burst today-tg sys: 0.608 (range 0.28-2.88, A/A dev 0.706)
  - kernel / kt idle today-tg user: 0.897 (range 0.87-1.14, A/A dev 0.115)
  - trickle / trickle gap=5000 new ThreadPool pool-cpu #2: 0.947 (range 0.86-0.96, A/A dev 0.135)
  - trickle / trickle gap=50000 new ThreadPool delay-p99 #1: 0.873 (range 0.78-1.18, A/A dev 1.071)
  - trickle / trickle gap=50000 new ThreadPool delay-median #2: 0.964 (range 0.89-1.04, A/A dev 0.038)
  - trickle / trickle gap=50000 new ThreadPool delay-p99 #2: 0.523 (range 0.14-86.87, A/A dev 60.282)
  - trickle / trickle gap=50000 new ThreadPool pool-cpu #2: 0.839 (range 0.79-1.03, A/A dev 0.222)
- rows only in HEAD: ['latency: latency new post+promise #1', 'latency: latency new post+promise #2']

Confirmation hold 2 on the M4 Pro (14 workers for `kernel`, 4 for `kernelt4`):

### threadpool m4: groups kernel(3 A, 3 B, 3 A/A), kernelt4(3 A, 3 B, 3 A/A), trickle(3 A, 3 B, 3 A/A)

| group | row | START | HEAD | START/HEAD | range | A/A | A/A dev | n | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| kernel | kt handoff today wall | 183400 | 185600 | 0.988 | 0.96-1.00 | 1.001 | 0.010 | 3 | slower |
| kernel | kt handoff today user | 180974 | 182737 | 0.992 | 0.99-1.00 | 0.999 | 0.010 | 3 | noise |
| kernel | kt handoff today sys | 6411.0 | 6632.0 | 0.945 | 0.84-1.06 | 1.036 | 0.056 | 3 | slower |
| kernel | kt burst today wall | 3765.0 | 155.0 | 24.871 | 17.93-46.38 | 1.030 | 0.063 | 3 | faster |
| kernel | kt burst today user | 1129.0 | 152.0 | 7.428 | 5.64-9.40 | 1.026 | 0.026 | 3 | faster |
| kernel | kt burst today sys | 13907.0 | 1029.0 | 13.242 | 13.21-21.59 | 1.020 | 0.037 | 3 | faster |
| kernel | kt idle today user | 177000 | 215000 | 0.843 | 0.82-0.93 | 1.145 | 0.153 | 3 | slower |
| kernel | kt idle today sys | 1146000 | 1366000 | 0.839 | 0.79-1.17 | 1.076 | 0.398 | 3 | noise |
| kernel | kt handoff today-tg wall | 182000 | 184800 | 0.993 | 0.98-1.01 | 0.998 | 0.016 | 3 | noise |
| kernel | kt handoff today-tg user | 180043 | 182705 | 0.995 | 0.98-1.01 | 1.002 | 0.016 | 3 | noise |
| kernel | kt handoff today-tg sys | 6494.0 | 6527.0 | 0.962 | 0.96-1.06 | 0.985 | 0.065 | 3 | noise |
| kernel | kt burst today-tg wall | 465.0 | 2565.0 | 0.181 | 0.16-0.29 | 0.869 | 0.196 | 3 | slower |
| kernel | kt burst today-tg user | 573.0 | 1368.0 | 0.419 | 0.39-0.51 | 0.944 | 0.074 | 3 | slower |
| kernel | kt burst today-tg sys | 4491.0 | 14280.0 | 0.296 | 0.28-0.40 | 0.900 | 0.117 | 3 | slower |
| kernel | kt idle today-tg user | 179000 | 189500 | 0.945 | 0.89-1.15 | 0.970 | 0.056 | 3 | slower |
| kernel | kt idle today-tg sys | 1264500 | 1181500 | 1.058 | 1.03-1.21 | 0.969 | 0.078 | 3 | noise |
| kernelt4 | kt handoff today wall | 184400 | 183400 | 1.003 | 1.00-1.01 | 0.998 | 0.009 | 3 | noise |
| kernelt4 | kt handoff today user | 181993 | 180785 | 1.004 | 1.00-1.01 | 0.997 | 0.012 | 3 | noise |
| kernelt4 | kt handoff today sys | 6313.0 | 6211.0 | 1.022 | 1.00-1.04 | 0.999 | 0.040 | 3 | noise |
| kernelt4 | kt burst today wall | 240.0 | 105.0 | 2.286 | 2.18-2.50 | 0.962 | 0.040 | 3 | faster |
| kernelt4 | kt burst today user | 158.0 | 167.0 | 0.946 | 0.83-0.98 | 1.045 | 0.105 | 3 | noise |
| kernelt4 | kt burst today sys | 638.0 | 239.0 | 2.669 | 2.54-2.93 | 0.991 | 0.038 | 3 | faster |
| kernelt4 | kt idle today user | 71500.0 | 71500.0 | 0.888 | 0.86-1.07 | 1.000 | 0.126 | 3 | noise |
| kernelt4 | kt idle today sys | 286000 | 266500 | 1.073 | 0.73-1.29 | 0.883 | 0.240 | 3 | noise |
| kernelt4 | kt handoff today-tg wall | 184200 | 183800 | 1.002 | 0.99-1.01 | 1.003 | 0.007 | 3 | noise |
| kernelt4 | kt handoff today-tg user | 182404 | 181856 | 1.004 | 0.99-1.01 | 1.003 | 0.008 | 3 | noise |
| kernelt4 | kt handoff today-tg sys | 6075.0 | 6230.0 | 0.970 | 0.97-1.06 | 0.982 | 0.034 | 3 | noise |
| kernelt4 | kt burst today-tg wall | 335.0 | 245.0 | 1.380 | 1.37-1.41 | 1.032 | 0.062 | 3 | faster |
| kernelt4 | kt burst today-tg user | 538.0 | 313.0 | 1.668 | 1.65-1.91 | 1.063 | 0.070 | 3 | faster |
| kernelt4 | kt burst today-tg sys | 777.0 | 594.0 | 1.308 | 1.22-1.34 | 1.012 | 0.038 | 3 | faster |
| kernelt4 | kt idle today-tg user | 68500.0 | 76000.0 | 0.928 | 0.83-0.96 | 0.904 | 0.154 | 3 | noise |
| kernelt4 | kt idle today-tg sys | 334000 | 319500 | 1.009 | 0.99-1.13 | 1.026 | 0.110 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool delay-median #1 | 7542.0 | 2458.0 | 2.933 | 2.92-3.29 | 1.040 | 0.321 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-p99 #1 | 29083.0 | 16750.0 | 1.759 | 1.74-2.17 | 1.281 | 0.532 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool pool-cpu #1 | 2059.0 | 1853.0 | 1.110 | 1.10-1.11 | 1.008 | 0.117 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool delay-median #2 | 7417.0 | 2542.0 | 2.874 | 2.83-2.92 | 1.028 | 0.106 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-p99 #2 | 37458.0 | 17625.0 | 2.125 | 1.86-5.36 | 1.189 | 1.910 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool pool-cpu #2 | 2092.0 | 1852.0 | 1.138 | 1.13-1.15 | 1.004 | 0.066 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-median #1 | 3458.0 | 3417.0 | 1.012 | 0.84-1.02 | 1.012 | 0.159 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool delay-p99 #1 | 19292.0 | 19875.0 | 1.009 | 0.63-1.02 | 0.977 | 0.187 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool pool-cpu #1 | 4328.0 | 5340.0 | 0.811 | 0.59-0.83 | 0.878 | 0.259 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool delay-median #2 | 3459.0 | 3458.0 | 1.000 | 0.96-1.01 | 0.988 | 0.024 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool delay-p99 #2 | 18667.0 | 18417.0 | 1.014 | 0.11-1.25 | 1.109 | 0.154 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool pool-cpu #2 | 4543.0 | 4598.0 | 0.988 | 0.81-1.16 | 1.172 | 0.257 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-median #1 | 5917.0 | 5791.0 | 1.015 | 1.00-1.10 | 1.007 | 0.117 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-p99 #1 | 20166.0 | 17250.0 | 1.150 | 0.99-1.35 | 1.150 | 0.360 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool pool-cpu #1 | 3755.0 | 3631.0 | 1.044 | 0.99-1.06 | 0.998 | 0.080 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-median #2 | 6125.0 | 5667.0 | 1.023 | 1.00-1.08 | 1.014 | 0.038 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-p99 #2 | 20208.0 | 16417.0 | 1.163 | 0.93-1.46 | 1.022 | 0.240 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool pool-cpu #2 | 3849.0 | 3557.0 | 1.046 | 1.03-1.11 | 1.009 | 0.040 | 3 | faster |

- library rows: 50, geomean 1.226; A/A geomean 1.012
- control rows (unchanged code): 98, geomean 0.904, median 0.988, min 0.376, max 1.500
- per-group geomean: kernel 1.247 (n=16), kernelt4 1.187 (n=16), trickle 1.243 (n=18)
- slow rows (<0.97 and outside A/A): 6
  - kernel / kt handoff today sys: 0.945 (range 0.84-1.06, A/A dev 0.056)
  - kernel / kt idle today user: 0.843 (range 0.82-0.93, A/A dev 0.153)
  - kernel / kt burst today-tg wall: 0.181 (range 0.16-0.29, A/A dev 0.196)
  - kernel / kt burst today-tg user: 0.419 (range 0.39-0.51, A/A dev 0.074)
  - kernel / kt burst today-tg sys: 0.296 (range 0.28-0.40, A/A dev 0.117)
  - kernel / kt idle today-tg user: 0.945 (range 0.89-1.15, A/A dev 0.056)
- rows <0.97 but inside the A/A spread: 7
  - kernel / kt idle today sys: 0.839 (range 0.79-1.17, A/A dev 0.398)
  - kernel / kt handoff today-tg sys: 0.962 (range 0.96-1.06, A/A dev 0.065)
  - kernelt4 / kt burst today user: 0.946 (range 0.83-0.98, A/A dev 0.105)
  - kernelt4 / kt idle today user: 0.888 (range 0.86-1.07, A/A dev 0.126)
  - kernelt4 / kt handoff today-tg sys: 0.970 (range 0.97-1.06, A/A dev 0.034)
  - kernelt4 / kt idle today-tg user: 0.928 (range 0.83-0.96, A/A dev 0.154)
  - trickle / trickle gap=5000 new ThreadPool pool-cpu #1: 0.811 (range 0.59-0.83, A/A dev 0.259)

## Intel i9-9980HK

Hold 1 (i9 hold): 10:00:25 to 10:10:16, `uptime` load `7.90 6.43 6.77` to `6.36 6.60 6.63`.
Hold 2 (i9 hold c): 12:31:17 to 12:42:03, load `7.04 6.60 6.56` to `4.87 5.55 6.18`.

### threadpool i9: groups grid(3 A, 3 B, 3 A/A), idle(3 A, 3 B, 3 A/A), kernel(3 A, 3 B, 3 A/A), latency(3 A, 3 B, 3 A/A), trickle(3 A, 3 B, 3 A/A)

| group | row | START | HEAD | START/HEAD | range | A/A | A/A dev | n | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| grid | enq shared P1xW1 new ThreadPool min | 231.7 | 31.8 | 7.426 | 6.28-7.46 | 1.055 | 0.080 | 3 | faster |
| grid | enq local P1xW1 new ThreadPool min | 225.9 | 28.3 | 7.651 | 7.17-8.04 | 1.045 | 0.055 | 3 | faster |
| grid | enq cap40 P1xW1 new ThreadPool min | 347.9 | 30.3 | 11.482 | 10.77-12.56 | 0.952 | 0.050 | 3 | faster |
| grid | enq shared P4xW1 new ThreadPool min | 281.8 | 37.7 | 7.475 | 6.56-7.57 | 0.984 | 0.074 | 3 | faster |
| grid | enq local P4xW1 new ThreadPool min | 263.0 | 40.0 | 6.692 | 6.31-6.70 | 0.940 | 0.069 | 3 | faster |
| grid | enq cap40 P4xW1 new ThreadPool min | 390.7 | 43.4 | 8.774 | 8.13-10.20 | 0.986 | 0.024 | 3 | faster |
| grid | enq shared P1xW4 new ThreadPool min | 1727.8 | 120.0 | 13.745 | 13.52-14.95 | 0.947 | 0.061 | 3 | faster |
| grid | enq local P1xW4 new ThreadPool min | 1694.4 | 115.8 | 14.433 | 13.76-16.46 | 0.961 | 0.104 | 3 | faster |
| grid | enq cap40 P1xW4 new ThreadPool min | 2899.9 | 106.5 | 24.722 | 21.43-29.94 | 0.903 | 0.285 | 3 | faster |
| grid | enq shared P4xW4 new ThreadPool min | 483.3 | 138.5 | 3.534 | 3.49-3.95 | 0.968 | 0.091 | 3 | faster |
| grid | enq local P4xW4 new ThreadPool min | 467.4 | 126.3 | 3.812 | 3.70-3.85 | 1.001 | 0.061 | 3 | faster |
| grid | enq cap40 P4xW4 new ThreadPool min | 687.4 | 127.5 | 5.251 | 4.86-5.40 | 0.958 | 0.091 | 3 | faster |
| grid | enq shared P1xW8 new ThreadPool min | 2957.1 | 272.1 | 8.493 | 3.05-33.83 | 0.551 | 0.854 | 3 | faster |
| grid | enq local P1xW8 new ThreadPool min | 5664.9 | 171.5 | 33.128 | 24.26-34.38 | 1.015 | 0.036 | 3 | faster |
| grid | enq cap40 P1xW8 new ThreadPool min | 5758.6 | 293.3 | 19.145 | 16.03-22.03 | 0.997 | 0.312 | 3 | faster |
| grid | enq shared P4xW8 new ThreadPool min | 685.6 | 191.0 | 3.620 | 3.59-3.81 | 0.930 | 0.189 | 3 | faster |
| grid | enq local P4xW8 new ThreadPool min | 721.2 | 200.5 | 3.542 | 3.30-4.32 | 1.017 | 0.066 | 3 | faster |
| grid | enq cap40 P4xW8 new ThreadPool min | 1627.6 | 173.7 | 9.539 | 9.19-10.17 | 1.028 | 0.062 | 3 | faster |
| idle | idle new ThreadPool w=4 cpu-per-s | 1280000 | 1280000 | 1.000 | 0.84-1.03 | 0.955 | 0.200 | 3 | noise |
| idle | idle new ThreadPool w=8 cpu-per-s | 2780000 | 2890000 | 0.962 | 0.95-1.01 | 1.026 | 0.135 | 3 | noise |
| kernel | kt handoff today wall | 823000 | 814600 | 0.993 | 0.99-1.01 | 1.011 | 0.013 | 3 | noise |
| kernel | kt handoff today user | 815360 | 811262 | 0.997 | 0.99-1.01 | 1.007 | 0.008 | 3 | noise |
| kernel | kt handoff today sys | 11418.0 | 10797.0 | 1.020 | 1.02-1.06 | 1.088 | 0.122 | 3 | noise |
| kernel | kt burst today wall | 5685.0 | 360.0 | 15.792 | 15.04-23.00 | 1.008 | 0.013 | 3 | faster |
| kernel | kt burst today user | 3794.0 | 597.0 | 6.355 | 5.36-8.53 | 1.006 | 0.014 | 3 | faster |
| kernel | kt burst today sys | 12509.0 | 4295.0 | 2.912 | 2.74-3.92 | 1.009 | 0.020 | 3 | faster |
| kernel | kt idle today user | 1251000 | 1277000 | 0.928 | 0.90-0.99 | 1.038 | 0.065 | 3 | slower |
| kernel | kt idle today sys | 5332000 | 8020500 | 0.613 | 0.61-0.89 | 0.735 | 0.399 | 3 | slower |
| kernel | kt handoff today-tg wall | 825200 | 810400 | 1.015 | 1.00-1.03 | 1.010 | 0.032 | 3 | noise |
| kernel | kt handoff today-tg user | 820768 | 805912 | 1.014 | 1.00-1.03 | 1.009 | 0.029 | 3 | noise |
| kernel | kt handoff today-tg sys | 11103.0 | 10573.0 | 1.048 | 1.00-1.05 | 1.054 | 0.078 | 3 | noise |
| kernel | kt burst today-tg wall | 1695.0 | 5135.0 | 0.337 | 0.31-0.35 | 0.927 | 0.085 | 3 | slower |
| kernel | kt burst today-tg user | 3146.0 | 4843.0 | 0.642 | 0.62-0.70 | 0.981 | 0.092 | 3 | slower |
| kernel | kt burst today-tg sys | 19661.0 | 20380.0 | 0.961 | 0.96-1.00 | 0.936 | 0.108 | 3 | noise |
| kernel | kt idle today-tg user | 1251500 | 1191000 | 1.079 | 1.05-1.12 | 0.964 | 0.087 | 3 | noise |
| kernel | kt idle today-tg sys | 7470000 | 6666000 | 1.205 | 0.83-1.27 | 0.989 | 0.160 | 3 | faster |
| latency | latency new async #1 | 9011.0 | 8823.0 | 1.030 | 1.02-1.03 | 0.941 | 0.066 | 3 | noise |
| latency | latency new async #2 | 8889.0 | 9001.0 | 0.982 | 0.96-1.00 | 0.995 | 0.033 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool delay-median #1 | 6786.0 | 7547.0 | 0.987 | 0.90-1.22 | 0.983 | 0.134 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool delay-p99 #1 | 39650.0 | 69565.0 | 0.651 | 0.36-1.13 | 1.083 | 0.425 | 3 | slower |
| trickle | trickle gap=1000 new ThreadPool pool-cpu #1 | 7651.0 | 1985.0 | 3.672 | 3.62-3.85 | 0.998 | 0.100 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-median #2 | 6983.0 | 7105.0 | 0.983 | 0.92-1.31 | 0.998 | 0.051 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool delay-p99 #2 | 36592.0 | 63148.0 | 0.676 | 0.31-0.74 | 0.869 | 0.345 | 3 | slower |
| trickle | trickle gap=1000 new ThreadPool pool-cpu #2 | 7482.0 | 1993.0 | 3.668 | 3.55-3.96 | 0.998 | 0.087 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-median #1 | 6515.0 | 2540.0 | 2.555 | 2.45-2.69 | 0.949 | 0.057 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-p99 #1 | 32376.0 | 19039.0 | 1.307 | 1.29-2.07 | 0.906 | 0.237 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool pool-cpu #1 | 7523.0 | 7302.0 | 1.026 | 1.02-1.05 | 0.984 | 0.025 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-median #2 | 6864.0 | 2559.0 | 2.674 | 2.67-2.76 | 1.072 | 0.098 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-p99 #2 | 44026.0 | 23790.0 | 2.726 | 1.47-5.52 | 1.619 | 2.157 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool pool-cpu #2 | 7655.0 | 7479.0 | 1.021 | 1.00-1.10 | 1.015 | 0.067 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-median #1 | 4750.0 | 4500.0 | 1.056 | 0.90-1.10 | 0.995 | 0.037 | 3 | faster |
| trickle | trickle gap=50000 new ThreadPool delay-p99 #1 | 50154.0 | 47299.0 | 1.019 | 1.01-1.08 | 1.005 | 0.105 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool pool-cpu #1 | 5558.0 | 5531.0 | 1.043 | 0.97-1.05 | 1.001 | 0.048 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-median #2 | 4426.0 | 4281.0 | 1.040 | 0.91-1.08 | 0.985 | 0.058 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-p99 #2 | 51455.0 | 49026.0 | 0.947 | 0.92-1.18 | 1.055 | 0.156 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool pool-cpu #2 | 5449.0 | 5537.0 | 0.984 | 0.96-1.04 | 1.027 | 0.087 | 3 | noise |

- library rows: 56, geomean 2.342; A/A geomean 0.984
- control rows (unchanged code): 138, geomean 0.989, median 0.991, min 0.595, max 1.787
- supplementary median-of-reps rows (library): 18, geomean 8.400
- per-group geomean: grid 8.594 (n=18), idle 0.981 (n=2), kernel 1.275 (n=16), latency 1.006 (n=2), trickle 1.325 (n=18)
- slow rows (<0.97 and outside A/A): 6
  - kernel / kt idle today user: 0.928 (range 0.90-0.99, A/A dev 0.065)
  - kernel / kt idle today sys: 0.613 (range 0.61-0.89, A/A dev 0.399)
  - kernel / kt burst today-tg wall: 0.337 (range 0.31-0.35, A/A dev 0.085)
  - kernel / kt burst today-tg user: 0.642 (range 0.62-0.70, A/A dev 0.092)
  - trickle / trickle gap=1000 new ThreadPool delay-p99 #1: 0.651 (range 0.36-1.13, A/A dev 0.425)
  - trickle / trickle gap=1000 new ThreadPool delay-p99 #2: 0.676 (range 0.31-0.74, A/A dev 0.345)
- rows <0.97 but inside the A/A spread: 3
  - idle / idle new ThreadPool w=8 cpu-per-s: 0.962 (range 0.95-1.01, A/A dev 0.135)
  - kernel / kt burst today-tg sys: 0.961 (range 0.96-1.00, A/A dev 0.108)
  - trickle / trickle gap=50000 new ThreadPool delay-p99 #2: 0.947 (range 0.92-1.18, A/A dev 0.156)
- rows only in HEAD: ['latency: latency new post+promise #1', 'latency: latency new post+promise #2']

Confirmation hold 2 on the i9 (16 workers for `kernel`, 4 for `kernelt4`):

### threadpool i9: groups kernel(3 A, 3 B, 3 A/A), kernelt4(3 A, 3 B, 3 A/A), trickle(3 A, 3 B, 3 A/A)

| group | row | START | HEAD | START/HEAD | range | A/A | A/A dev | n | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| kernel | kt handoff today wall | 800600 | 798400 | 0.996 | 0.99-1.01 | 0.997 | 0.005 | 3 | noise |
| kernel | kt handoff today user | 796517 | 793518 | 0.999 | 0.99-1.01 | 0.997 | 0.004 | 3 | noise |
| kernel | kt handoff today sys | 9672.0 | 9619.0 | 0.997 | 0.97-1.09 | 1.041 | 0.054 | 3 | noise |
| kernel | kt burst today wall | 5605.0 | 370.0 | 15.356 | 14.84-15.54 | 1.015 | 0.039 | 3 | faster |
| kernel | kt burst today user | 3752.0 | 696.0 | 5.504 | 5.27-5.51 | 1.010 | 0.029 | 3 | faster |
| kernel | kt burst today sys | 12527.0 | 4531.0 | 2.820 | 2.68-2.82 | 1.019 | 0.039 | 3 | faster |
| kernel | kt idle today user | 1283000 | 1318500 | 1.064 | 0.97-1.08 | 1.081 | 0.229 | 3 | noise |
| kernel | kt idle today sys | 6446500 | 6332500 | 1.009 | 0.88-1.08 | 0.982 | 0.069 | 3 | noise |
| kernel | kt handoff today-tg wall | 798800 | 796600 | 1.008 | 0.98-1.01 | 1.013 | 0.017 | 3 | noise |
| kernel | kt handoff today-tg user | 795615 | 794260 | 1.008 | 0.99-1.01 | 1.014 | 0.014 | 3 | noise |
| kernel | kt handoff today-tg sys | 9721.0 | 9889.0 | 1.002 | 0.93-1.00 | 1.037 | 0.043 | 3 | noise |
| kernel | kt burst today-tg wall | 1715.0 | 6165.0 | 0.278 | 0.25-0.29 | 1.043 | 0.105 | 3 | slower |
| kernel | kt burst today-tg user | 3067.0 | 5591.0 | 0.547 | 0.54-0.58 | 1.047 | 0.128 | 3 | slower |
| kernel | kt burst today-tg sys | 20846.0 | 22414.0 | 0.930 | 0.89-0.95 | 1.031 | 0.166 | 3 | noise |
| kernel | kt idle today-tg user | 1331000 | 1182500 | 1.073 | 1.06-1.27 | 0.992 | 0.212 | 3 | noise |
| kernel | kt idle today-tg sys | 6461500 | 6108500 | 0.827 | 0.81-1.08 | 0.938 | 0.334 | 3 | noise |
| kernelt4 | kt handoff today wall | 801200 | 797200 | 1.005 | 1.00-1.01 | 1.001 | 0.007 | 3 | noise |
| kernelt4 | kt handoff today user | 797351 | 794379 | 1.004 | 1.00-1.01 | 1.000 | 0.007 | 3 | noise |
| kernelt4 | kt handoff today sys | 9158.0 | 8749.0 | 1.024 | 1.01-1.05 | 1.037 | 0.037 | 3 | noise |
| kernelt4 | kt burst today wall | 1720.0 | 230.0 | 7.333 | 7.07-8.00 | 1.030 | 0.100 | 3 | faster |
| kernelt4 | kt burst today user | 1278.0 | 428.0 | 3.005 | 2.87-3.22 | 1.020 | 0.078 | 3 | faster |
| kernelt4 | kt burst today sys | 3796.0 | 528.0 | 7.277 | 6.91-7.53 | 1.023 | 0.086 | 3 | faster |
| kernelt4 | kt idle today user | 351500 | 318000 | 1.039 | 0.97-1.15 | 1.049 | 0.068 | 3 | noise |
| kernelt4 | kt idle today sys | 896500 | 831500 | 0.900 | 0.84-1.33 | 0.878 | 0.217 | 3 | noise |
| kernelt4 | kt handoff today-tg wall | 798400 | 799800 | 1.003 | 1.00-1.01 | 1.007 | 0.016 | 3 | noise |
| kernelt4 | kt handoff today-tg user | 797537 | 798321 | 1.004 | 1.00-1.01 | 1.010 | 0.015 | 3 | noise |
| kernelt4 | kt handoff today-tg sys | 8830.0 | 9070.0 | 0.964 | 0.96-1.08 | 0.984 | 0.061 | 3 | noise |
| kernelt4 | kt burst today-tg wall | 1150.0 | 755.0 | 1.523 | 1.44-1.82 | 1.041 | 0.217 | 3 | faster |
| kernelt4 | kt burst today-tg user | 2164.0 | 1171.0 | 1.845 | 1.78-2.15 | 1.031 | 0.176 | 3 | faster |
| kernelt4 | kt burst today-tg sys | 2552.0 | 2005.0 | 1.273 | 1.20-1.43 | 1.033 | 0.155 | 3 | faster |
| kernelt4 | kt idle today-tg user | 341500 | 355500 | 0.991 | 0.95-1.10 | 0.973 | 0.146 | 3 | noise |
| kernelt4 | kt idle today-tg sys | 918000 | 944500 | 1.020 | 0.70-1.06 | 0.964 | 0.373 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool delay-median #1 | 7046.0 | 5567.0 | 1.247 | 0.91-1.28 | 1.010 | 0.027 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-p99 #1 | 32744.0 | 58461.0 | 0.617 | 0.25-0.78 | 0.839 | 0.371 | 3 | slower |
| trickle | trickle gap=1000 new ThreadPool pool-cpu #1 | 7259.0 | 1954.0 | 3.715 | 3.51-3.77 | 0.957 | 0.070 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-median #2 | 6988.0 | 5539.0 | 1.266 | 1.07-1.35 | 1.011 | 0.024 | 3 | faster |
| trickle | trickle gap=1000 new ThreadPool delay-p99 #2 | 44730.0 | 52413.0 | 0.853 | 0.49-1.07 | 0.975 | 0.600 | 3 | noise |
| trickle | trickle gap=1000 new ThreadPool pool-cpu #2 | 7231.0 | 1964.0 | 3.727 | 3.50-3.81 | 0.954 | 0.047 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-median #1 | 6649.0 | 2536.0 | 2.622 | 2.55-2.67 | 0.939 | 0.123 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-p99 #1 | 31530.0 | 24092.0 | 1.309 | 1.22-1.52 | 0.717 | 0.385 | 3 | noise |
| trickle | trickle gap=5000 new ThreadPool pool-cpu #1 | 7418.0 | 7197.0 | 1.031 | 1.02-1.05 | 0.977 | 0.027 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-median #2 | 6666.0 | 2544.0 | 2.611 | 2.60-2.69 | 0.962 | 0.053 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool delay-p99 #2 | 39169.0 | 24622.0 | 1.600 | 1.20-1.67 | 0.938 | 0.305 | 3 | faster |
| trickle | trickle gap=5000 new ThreadPool pool-cpu #2 | 7506.0 | 7140.0 | 1.046 | 1.02-1.05 | 0.983 | 0.022 | 3 | faster |
| trickle | trickle gap=50000 new ThreadPool delay-median #1 | 4342.0 | 4287.0 | 1.013 | 0.98-1.02 | 0.997 | 0.021 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-p99 #1 | 47252.0 | 46365.0 | 1.001 | 0.99-1.06 | 1.001 | 0.103 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool pool-cpu #1 | 5459.0 | 5373.0 | 1.003 | 0.99-1.04 | 1.036 | 0.037 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-median #2 | 4236.0 | 4369.0 | 0.959 | 0.95-0.99 | 0.966 | 0.067 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool delay-p99 #2 | 47872.0 | 47461.0 | 1.039 | 0.89-1.08 | 1.008 | 0.068 | 3 | noise |
| trickle | trickle gap=50000 new ThreadPool pool-cpu #2 | 5393.0 | 5367.0 | 1.000 | 0.95-1.01 | 0.976 | 0.049 | 3 | noise |

- library rows: 50, geomean 1.349; A/A geomean 0.990
- control rows (unchanged code): 98, geomean 0.985, median 0.994, min 0.758, max 1.800
- per-group geomean: kernel 1.243 (n=16), kernelt4 1.482 (n=16), trickle 1.335 (n=18)
- slow rows (<0.97 and outside A/A): 3
  - kernel / kt burst today-tg wall: 0.278 (range 0.25-0.29, A/A dev 0.105)
  - kernel / kt burst today-tg user: 0.547 (range 0.54-0.58, A/A dev 0.128)
  - trickle / trickle gap=1000 new ThreadPool delay-p99 #1: 0.617 (range 0.25-0.78, A/A dev 0.371)
- rows <0.97 but inside the A/A spread: 6
  - kernel / kt burst today-tg sys: 0.930 (range 0.89-0.95, A/A dev 0.166)
  - kernel / kt idle today-tg sys: 0.827 (range 0.81-1.08, A/A dev 0.334)
  - kernelt4 / kt idle today sys: 0.900 (range 0.84-1.33, A/A dev 0.217)
  - kernelt4 / kt handoff today-tg sys: 0.964 (range 0.96-1.08, A/A dev 0.061)
  - trickle / trickle gap=1000 new ThreadPool delay-p99 #2: 0.853 (range 0.49-1.07, A/A dev 0.600)
  - trickle / trickle gap=50000 new ThreadPool delay-median #2: 0.959 (range 0.95-0.99, A/A dev 0.067)

## Rows < 0.97 outside the A/A spread

A row counts as real when it is below 0.97 and outside the A/A spread in one hold and again in the second hold or on the other machine.

| row | M4 Pro (hold 1 / hold 2) | i9 (hold 1 / hold 2) | cause |
|---|---|---|---|
| `kt burst today-tg wall` (`TaskGroup` burst of 200 000 items, 14 / 16 workers) | 0.599 / **0.181** | 0.337 / **0.278** | Probable, inferred from the code and the thread-count diagnostic, not profiled and not named in the CHANGELOG: every worker re-posts its group's ticket (`TaskGroup::dispatch` calls `pool->enqueue`) and takes the next one, so 14 to 16 workers hammer the new queue's two locks, the producers' spin lock (`PoolSpinMutex`, "a producer preempted inside the tail lock holds up the other producers", ARCHITECTURE.md known limitations) and the consumers' `std::mutex`, where moodycamel's queue had lock-free producers. With 4 workers (`kernel_time 1 4`) the same row is 1.38x (M4) and 1.52x (i9) faster at HEAD; the bare-pool burst is 15x to 25x faster at 14 to 16 workers, since there only one thread produces. |
| `kt burst today-tg user` | 0.895 (inside spread) / **0.419** | 0.642 / **0.547** | same |
| `kt burst today-tg sys` | 0.608 (inside spread) / **0.296** | 0.961 (inside spread) / 0.930 (inside spread) | same; sys time is only slower on the M4 Pro |
| `trickle gap=1000 delay-p99 #1` (one task per microsecond into 4 workers, p99 of submit-to-start) | 0.464 / not reproduced (1.76x faster) | 0.651 / **0.617** (`#2`: 0.676 / 0.853 inside spread) | Probable, not isolated: the CHANGELOG's coalesced wake ("an enqueue signals only when a worker sleeps and has not been signaled"); the same change cuts the pool's CPU per task 3.7x on the i9 (7.3 to 2.0 microseconds) and the median start delay 1.25x there (2.9x on the M4 Pro). A trade of tail for CPU. Confirmed on the i9 only; the M4 Pro's hold 1 value is load noise (A/A dev 0.81). |

Flagged in one hold and not reproduced, counted as noise: `kt idle today user` (14 to 16 idle workers; M4 hold 2 0.843 with A/A dev 0.153, M4 hold 1 0.981, i9 hold 1 0.928 with dev 0.065, i9 hold 2 1.064) and `kt idle today sys` (i9 hold 1 0.613 with dev 0.399; every other observation inside the spread). The absolute differences are 0.01 to 0.04 ms of CPU per second, below 0.005% of a core; `enqueue_bench idle` (4 and 8 idle workers) shows 0.97 / 0.95 on the M4 Pro and 1.00 / 0.96 on the i9, all inside the spread. `kt handoff today sys` (0.945, hold 2 on the M4 Pro) and `kt idle today-tg user` (0.945) are 5% inside a tight A/A and appear in no other hold.

## Rows dropped or not comparable

- `latency new post+promise` (HEAD only: `ThreadPool::post` does not exist at START).
- `enq ... med` rows (median of the reps) are in `$GATE/raw/threadpool/*/grid.md`; the verdict uses `min`, the bench's own figure. Geomean of the median rows: 6.18 (M4 Pro), 8.40 (i9).
- `async` now builds one allocation fewer and `enqueue` constructs the task before it counts it (CHANGELOG): the rows do the same observable work; no row measures a bug fix that makes HEAD do more or less work, except that `kt burst today` at HEAD no longer allocates for a small closure (that is the speed-up).
- `trickle ... pool-cpu` is process CPU minus wall time (the producer spins one core); values below 1 ns are floored to 1 for the ratio.

## Rig notes

- The M4 Pro is never quiet: `uptime` shows 7 to 20 during "exclusive" holds, from other sessions' leaked processes (not killed). The A/A pairs absorb it; hold 1's p99 rows on the M4 Pro are not usable, which is why the second hold ran when the load was 6.6.
- Holds waited 17 minutes (i9 hold 1), 41 minutes (M4 hold 1), 1 h 44 min (M4 hold 2) and 2 h 18 min (i9 hold 2) in a queue of 20 to 40 strict holds from other gate runs. The builds waited 15 minutes for a light slot (the strict queue blocks light holds) and then ran at `nice -n 19 -j4` outside a hold, as the recipe allows after starvation; no timing was taken outside a hold.
- i9 hold 2 ran 46 s past its 10-minute deadline (`kernel_time` takes 32 s a run on the i9): the last rounds of the `kernelt4` group (a diagnostic, not a gate row) may not have been held. The `kernel` and `trickle` groups finished inside the deadline (12:36:02 and 12:37:27).

SUMMARY repo=threadpool m4_geomean=2.009 i9_geomean=2.342 m4_slow=3/0.181 i9_slow=3/0.278 unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- `TaskGroup` burst of tiny tasks on 14 to 16 workers, wall, user and system time (M4 0.181 to
  0.608, i9 0.278 to 0.642): fixed in `threadpool:5d97d35`. A group lists one ticket at a time, and
  a worker runs the group's next task while only the group's tickets wait. 3 to 4 times faster than
  start on both machines: 125 ns a task on 16 workers of the M4 Pro (start 490), 515 on the i9 (start
  1,725).
- i9 trickle, one task every microsecond, p99 delay 0.651 (0.617 in a second hold): owner decision,
  [threadpool#3](https://github.com/Kronuz/threadpool/issues/3). The p99 is 61 to 90 µs against
  start's 35 to 47, for a quarter of start's pool CPU per task (2.0 µs against 7.4), and the median
  is lower (6.2 to 6.6 µs against 6.9 to 7.0). On the M4 Pro the row is 3 times better than start.
