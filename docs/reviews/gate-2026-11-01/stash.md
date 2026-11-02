# stash gate: START vs HEAD

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/stash#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Question: is `stash` at HEAD substantially better than at the start of the campaign, and is any row slower than it was?

**Answer: faster almost everywhere, with one small confirmed regression.** Every insert-throughput and p99 row of `bench_structures` and `bench_scheduler`, every bursty-producer row but one p999 and every `bench_steady` row at depth 1 024 and 16 384 has a ratio above 1 (library-row geomean 1.75x on the M4 Pro, 1.80x on the i9; bursty add p99 up to 9.5x lower), because HEAD no longer walks the chain from the leaf's head for every insert (`78a18f3`: filling a leaf of `n` values stepped over about n^2/(2 Size) nodes, now about n/Size). The shallow-depth `bench_steady` rows at depth 64 with 4 and 14 producers have a p99 that is 4% to 12% worse (insert p50 unchanged); that is consistent with the claim hint's extra atomic work on a leaf's first insert and reproduced on both machines. The verdict is SLOWER-ROWS by the gate's rule.

## Setup

| | |
|---|---|
| START | `2e2b75f587e26cf59a5b15c9e573eaa277a7b6fe`, 2026-10-28 04:52 -0700 (last `origin/main` commit before 2026-10-30) |
| HEAD | `0b188b4279ef9b89089aca281b446351b96e129e`, 2026-11-01 06:14 -0800 |
| Library change | `stash.h` only, in `78a18f3` "Resume an insert's chain walk at the leaf's furthest claimed node" (2026-10-31; `stash.h` +44/-7, `test/test.cc` +43): `StashValues::put` resumes its walk at `atom_claim_hint` (the furthest chain node a claim resolved) instead of the leaf's head, each chain node carries its index, the leaf grows 16 bytes and each node 8. The other commits are docs and `bench/RESULTS.md`. `bench/*.cc` and `bench/CMakeLists.txt` are identical at START and HEAD. |
| M4 | Apple M4 Pro, 14 cores (10P+4E), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5 |
| i9 | Intel i9-9980HK, 8 cores / 16 threads, macOS 15.8.1, Apple clang 17.0.0 (clang-1700.6.4.2), CMake 4.4.4 |
| Flags | `bench/CMakeLists.txt` as is: `-DCMAKE_BUILD_TYPE=Release` (`-O3 -DNDEBUG`), `-std=gnu++20`, no `-march`, `/usr/bin/clang++`, Ninja |
| Asio | 1.30.2, `12e0ce9e0500bf0f247dbd1ae894272656456079`: fetched once by the HEAD configure, passed to the START tree as `-DFETCHCONTENT_SOURCE_DIR_ASIO`, same SHA on the i9 |

START tree: HEAD's tree with `stash.h` and `stash_trace.h` taken from START (`git diff --cached --stat HEAD` in that tree):

```
 stash.h | 51 +++++++--------------------------------------------
 1 file changed, 7 insertions(+), 44 deletions(-)
```

Benchmarks (all four in `bench/`, built twice from the same sources; all rows exist in both binaries, nothing dropped):

| group | binary and arguments | what the rows are | rounds |
|---|---|---|---|
| structures | `bench_structures 150000` (M4) / `75000` (i9); default 2 000 000 | stash insert throughput (reported as ns per insert = 1000 / Mops, best of 3) and p99 of the producer's insert, 1/2/4/8/14 producers + 1 consumer, keys `now+uniform(0,100ms)` ("A-spread") and `now` ("B-convergent"); controls: mutex heap, mutex multimap, mutex deque, Vyukov MPSC, sharded queue | 3 |
| scheduler | `bench_scheduler 100000` (M4) / `60000` (i9); default 1 000 000 | the same two workloads for stash against the mutex heap and `asio::steady_timer` (controls) | 3 |
| steady | `bench_steady 250`; default 600 ms | per-arm latency p50 / p99 / p999 at a held depth of 64, 1 024, 16 384 with 1/4/14 producers (best of 2); controls: heap, asio | 3 |
| bursty | `bench_bursty 2 8 500 2000 256 1024` (the defaults) | 256 and 1 024 threads adding bursts of 8 between 0.5 to 2 ms sleeps: add p50 / p99 / p999 | 3 |

`bench_scheduler` needs only `stash.h` and Asio (not the scheduler library), so it is included. `bench_structures` and `bench_scheduler` totals are 13x to 17x below the defaults, to fit one hold: fewer keys share a leaf than in a default run, and the claim-walk saving grows with the keys per leaf, so the default totals would show larger speed-ups, not smaller.

Each group is one `ab_compare.py run --format unit --rounds 3 --save DIR START HEAD -- ARGS` (A, B, A again per round, interleaved) through a wrapper (`norm.py`) that re-emits the bench tables as `label  12.3 ns` rows. `ab_compare` prints in ns. Ratio = START/HEAD, above 1 means HEAD is faster. "A/A" is the median of A against A; "A/A dev" the largest |ratio-1| of an A/A pair; a row is "slower" when ratio x (1 + A/A dev) < 1. Control rows (heap, multimap, deque, Vyukov, sharded, Asio) run code that did not change; they show the noise of the rig and are summarised, not in the geomean.

Commands:

```
prep (both machines):  $GATE/raw/stash/scripts/prep.sh     # worktrees, overlay, cmake -S bench -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ (START: -DFETCHCONTENT_SOURCE_DIR_ASIO=...)
build:                 $GATE/raw/stash/scripts/build.sh    # nice -n 19 cmake --build build-{head,start} -j4  (unheld, see rig notes)
hold 1:                quiet strict 10 "..." -- ./hold.sh {m4,i9}       # structures steady scheduler bursty
hold 2 (confirm):      quiet strict 10 "..." -- ./hold2.sh {m4,i9}    # bench_steady 300, 5 rounds
raw: $GATE/raw/stash/{m4,i9}/ (hold 1), $GATE/raw/stash/{m4,i9}/confirm/ (hold 2); every group has a-NNN/b-NNN/aa-NNN (START/HEAD/START again), <group>.md (ab_compare's own table, all rows incl. controls), rawbench/ (the benches' own output)
```

## Apple M4 Pro

Hold 1 (M4 hold): 2026-11-01 10:35:36 to 10:41:17. `uptime` at start `load averages: 10.73 12.20 13.76`; at the end `67.76 30.74 20.61` (the last group is `bench_bursty` with 1 024 threads).
Hold 2 (M4 hold c, `bench_steady 300`, 5 rounds): 11:16:17 to 11:20:26, load `8.59 9.54 10.73` to `26.96 19.56 14.89`.

### stash m4: groups bursty(3 A, 3 B, 3 A/A), scheduler(3 A, 3 B, 3 A/A), steady(3 A, 3 B, 3 A/A), structures(3 A, 3 B, 3 A/A)

| group | row | START | HEAD | START/HEAD | range | A/A | A/A dev | n | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| bursty | bursty threads=256 add p50 | 583.0 | 250.0 | 2.332 | 2.17-2.34 | 1.002 | 0.076 | 3 | faster |
| bursty | bursty threads=256 add p99 | 3417.0 | 875.0 | 3.905 | 3.57-4.14 | 1.065 | 0.101 | 3 | faster |
| bursty | bursty threads=256 add p999 | 18125.0 | 13791.0 | 1.318 | 1.27-1.34 | 1.029 | 0.035 | 3 | faster |
| bursty | bursty threads=1024 add p50 | 1375.0 | 250.0 | 5.168 | 4.73-5.50 | 1.032 | 0.060 | 3 | faster |
| bursty | bursty threads=1024 add p99 | 5083.0 | 1042.0 | 4.704 | 4.48-5.08 | 0.983 | 0.144 | 3 | faster |
| bursty | bursty threads=1024 add p999 | 44209.0 | 15375.0 | 2.772 | 2.75-3.67 | 1.034 | 0.144 | 3 | faster |
| scheduler | scheduler A-spread stash t=1 insert | 333.3 | 94.2 | 3.577 | 1.95-3.75 | 0.963 | 0.682 | 3 | faster |
| scheduler | scheduler A-spread stash t=2 insert | 226.2 | 93.9 | 2.403 | 1.51-2.91 | 1.089 | 0.468 | 3 | faster |
| scheduler | scheduler A-spread stash t=4 insert | 128.2 | 62.5 | 1.604 | 1.34-2.05 | 1.000 | 0.345 | 3 | faster |
| scheduler | scheduler A-spread stash t=8 insert | 101.3 | 68.6 | 1.475 | 1.35-1.67 | 1.073 | 0.103 | 3 | faster |
| scheduler | scheduler A-spread stash t=14 insert | 89.5 | 57.5 | 1.556 | 1.38-1.68 | 1.004 | 0.310 | 3 | faster |
| scheduler | scheduler A-spread stash t=1 p99 | 791.0 | 125.0 | 6.328 | 3.34-7.00 | 1.000 | 1.098 | 3 | faster |
| scheduler | scheduler A-spread stash t=2 p99 | 875.0 | 334.0 | 2.994 | 1.33-3.50 | 1.000 | 0.848 | 3 | faster |
| scheduler | scheduler A-spread stash t=4 p99 | 958.0 | 417.0 | 1.768 | 1.30-2.30 | 0.958 | 0.645 | 3 | faster |
| scheduler | scheduler A-spread stash t=8 p99 | 1125.0 | 875.0 | 1.444 | 1.23-1.48 | 1.040 | 0.107 | 3 | faster |
| scheduler | scheduler A-spread stash t=14 p99 | 1083.0 | 958.0 | 1.238 | 1.04-1.30 | 0.928 | 0.173 | 3 | faster |
| scheduler | scheduler B-convergent stash t=1 insert | 413.2 | 179.5 | 2.302 | 1.70-2.34 | 1.083 | 0.222 | 3 | faster |
| scheduler | scheduler B-convergent stash t=2 insert | 286.5 | 133.5 | 2.116 | 2.03-2.61 | 1.071 | 0.077 | 3 | faster |
| scheduler | scheduler B-convergent stash t=4 insert | 217.4 | 170.1 | 1.278 | 0.96-1.50 | 0.857 | 0.244 | 3 | faster |
| scheduler | scheduler B-convergent stash t=8 insert | 178.2 | 143.3 | 1.168 | 1.16-1.39 | 1.043 | 0.109 | 3 | faster |
| scheduler | scheduler B-convergent stash t=14 insert | 157.7 | 140.4 | 1.123 | 1.06-1.20 | 1.024 | 0.087 | 3 | faster |
| scheduler | scheduler B-convergent stash t=1 p99 | 750.0 | 375.0 | 2.000 | 1.20-2.37 | 1.187 | 0.384 | 3 | faster |
| scheduler | scheduler B-convergent stash t=2 p99 | 1084.0 | 583.0 | 1.787 | 1.45-2.38 | 1.001 | 0.191 | 3 | faster |
| scheduler | scheduler B-convergent stash t=4 p99 | 1750.0 | 1125.0 | 1.556 | 0.96-1.59 | 0.857 | 0.303 | 3 | faster |
| scheduler | scheduler B-convergent stash t=8 p99 | 2250.0 | 1792.0 | 1.277 | 1.26-1.32 | 0.981 | 0.224 | 3 | faster |
| scheduler | scheduler B-convergent stash t=14 p99 | 2959.0 | 2208.0 | 1.340 | 1.10-1.46 | 1.164 | 0.197 | 3 | faster |
| steady | steady D=64 stash t=1 p50 | 125.0 | 125.0 | 1.000 | 1.00-1.00 | 1.000 | 0.488 | 3 | noise |
| steady | steady D=64 stash t=1 p99 | 542.0 | 542.0 | 1.000 | 1.00-1.00 | 1.002 | 0.181 | 3 | noise |
| steady | steady D=64 stash t=1 p999 | 1041.0 | 917.0 | 1.227 | 1.00-1.25 | 0.956 | 0.250 | 3 | noise |
| steady | steady D=64 stash t=4 p50 | 334.0 | 334.0 | 1.000 | 0.89-1.12 | 1.000 | 0.126 | 3 | noise |
| steady | steady D=64 stash t=4 p99 | 958.0 | 1083.0 | 0.884 | 0.85-0.96 | 0.958 | 0.087 | 3 | slower |
| steady | steady D=64 stash t=4 p999 | 1708.0 | 1667.0 | 1.055 | 0.98-1.45 | 1.055 | 0.319 | 3 | noise |
| steady | steady D=64 stash t=14 p50 | 834.0 | 875.0 | 0.909 | 0.90-1.09 | 0.910 | 0.101 | 3 | noise |
| steady | steady D=64 stash t=14 p99 | 2083.0 | 2333.0 | 0.889 | 0.88-1.00 | 0.960 | 0.077 | 3 | slower |
| steady | steady D=64 stash t=14 p999 | 5375.0 | 6583.0 | 0.800 | 0.70-1.39 | 0.679 | 0.327 | 3 | noise |
| steady | steady D=1024 stash t=1 p50 | 167.0 | 83.0 | 2.012 | 2.01-2.51 | 1.000 | 0.246 | 3 | faster |
| steady | steady D=1024 stash t=1 p99 | 584.0 | 375.0 | 1.557 | 1.40-1.67 | 1.000 | 0.070 | 3 | faster |
| steady | steady D=1024 stash t=1 p999 | 1542.0 | 625.0 | 2.223 | 1.87-2.64 | 1.001 | 0.430 | 3 | faster |
| steady | steady D=1024 stash t=4 p50 | 375.0 | 292.0 | 1.428 | 1.28-1.50 | 0.901 | 0.099 | 3 | faster |
| steady | steady D=1024 stash t=4 p99 | 1084.0 | 917.0 | 1.272 | 1.13-1.30 | 0.999 | 0.036 | 3 | faster |
| steady | steady D=1024 stash t=4 p999 | 3292.0 | 1250.0 | 2.644 | 2.63-2.67 | 0.964 | 0.087 | 3 | faster |
| steady | steady D=1024 stash t=14 p50 | 916.0 | 750.0 | 1.236 | 1.16-1.28 | 1.047 | 0.105 | 3 | faster |
| steady | steady D=1024 stash t=14 p99 | 1959.0 | 1916.0 | 1.066 | 0.98-1.07 | 1.021 | 0.022 | 3 | faster |
| steady | steady D=1024 stash t=14 p999 | 5416.0 | 3292.0 | 1.417 | 0.71-2.64 | 0.963 | 0.287 | 3 | faster |
| steady | steady D=16384 stash t=1 p50 | 250.0 | 42.0 | 5.952 | 5.95-5.95 | 1.000 | 0.000 | 3 | faster |
| steady | steady D=16384 stash t=1 p99 | 708.0 | 250.0 | 2.832 | 2.67-2.84 | 0.944 | 0.063 | 3 | faster |
| steady | steady D=16384 stash t=1 p999 | 1333.0 | 584.0 | 2.283 | 1.87-2.61 | 1.063 | 0.135 | 3 | faster |
| steady | steady D=16384 stash t=4 p50 | 625.0 | 291.0 | 2.148 | 2.14-2.34 | 1.000 | 0.002 | 3 | faster |
| steady | steady D=16384 stash t=4 p99 | 2041.0 | 875.0 | 2.228 | 2.10-2.43 | 1.020 | 0.125 | 3 | faster |
| steady | steady D=16384 stash t=4 p999 | 4916.0 | 1125.0 | 3.934 | 2.92-4.37 | 1.093 | 0.296 | 3 | faster |
| steady | steady D=16384 stash t=14 p50 | 1000.0 | 750.0 | 1.333 | 1.33-1.50 | 0.961 | 0.077 | 3 | faster |
| steady | steady D=16384 stash t=14 p99 | 2625.0 | 1875.0 | 1.465 | 1.40-1.52 | 0.941 | 0.149 | 3 | faster |
| steady | steady D=16384 stash t=14 p999 | 9167.0 | 2959.0 | 3.729 | 2.72-4.53 | 1.020 | 0.290 | 3 | faster |
| structures | structures A-spread stash t=1 insert | 301.2 | 105.2 | 2.805 | 2.65-2.95 | 1.003 | 0.044 | 3 | faster |
| structures | structures A-spread stash t=2 insert | 196.5 | 102.0 | 1.932 | 1.78-1.99 | 0.904 | 0.148 | 3 | faster |
| structures | structures A-spread stash t=4 insert | 124.7 | 99.6 | 1.252 | 1.12-2.09 | 0.831 | 0.335 | 3 | noise |
| structures | structures A-spread stash t=8 insert | 122.1 | 69.7 | 1.751 | 1.64-2.17 | 1.073 | 0.374 | 3 | faster |
| structures | structures A-spread stash t=14 insert | 93.9 | 60.0 | 1.599 | 1.53-1.64 | 0.980 | 0.095 | 3 | faster |
| structures | structures A-spread stash t=1 p99 | 792.0 | 208.0 | 3.808 | 3.33-6.34 | 1.000 | 0.052 | 3 | faster |
| structures | structures A-spread stash t=2 p99 | 958.0 | 333.0 | 2.877 | 1.83-3.00 | 1.048 | 0.143 | 3 | faster |
| structures | structures A-spread stash t=4 p99 | 958.0 | 625.0 | 1.573 | 1.44-1.67 | 0.919 | 0.083 | 3 | faster |
| structures | structures A-spread stash t=8 p99 | 1250.0 | 834.0 | 1.409 | 1.37-1.50 | 0.964 | 0.143 | 3 | faster |
| structures | structures A-spread stash t=14 p99 | 1375.0 | 917.0 | 1.454 | 1.32-1.50 | 1.031 | 0.059 | 3 | faster |
| structures | structures B-convergent stash t=1 insert | 431.0 | 237.0 | 1.819 | 1.73-1.82 | 1.034 | 0.052 | 3 | faster |
| structures | structures B-convergent stash t=2 insert | 274.7 | 132.6 | 2.071 | 1.35-2.71 | 1.041 | 0.047 | 3 | faster |
| structures | structures B-convergent stash t=4 insert | 216.4 | 164.2 | 1.352 | 1.32-1.39 | 1.049 | 0.117 | 3 | faster |
| structures | structures B-convergent stash t=8 insert | 176.1 | 147.5 | 1.198 | 1.15-1.20 | 1.030 | 0.084 | 3 | faster |
| structures | structures B-convergent stash t=14 insert | 153.4 | 132.6 | 1.149 | 1.14-1.18 | 0.969 | 0.064 | 3 | faster |
| structures | structures B-convergent stash t=1 p99 | 750.0 | 542.0 | 1.384 | 1.38-1.73 | 1.000 | 0.056 | 3 | faster |
| structures | structures B-convergent stash t=2 p99 | 1041.0 | 750.0 | 1.333 | 1.14-1.39 | 0.962 | 0.077 | 3 | faster |
| structures | structures B-convergent stash t=4 p99 | 1375.0 | 1125.0 | 1.222 | 1.19-1.22 | 1.032 | 0.144 | 3 | faster |
| structures | structures B-convergent stash t=8 p99 | 2167.0 | 1875.0 | 1.195 | 1.16-1.24 | 1.000 | 0.078 | 3 | faster |
| structures | structures B-convergent stash t=14 p99 | 2542.0 | 2125.0 | 1.196 | 1.17-1.27 | 1.017 | 0.034 | 3 | faster |

- library rows: 73, geomean 1.745; A/A geomean 0.995
- control rows (unchanged code): 154, geomean 1.004, median 1.001, min 0.506, max 1.739
- per-group geomean: bursty 3.053 (n=6), scheduler 1.813 (n=20), steady 1.583 (n=27), structures 1.618 (n=20)
- slow rows (<0.97 and outside A/A): 2
  - steady / steady D=64 stash t=4 p99: 0.884 (range 0.85-0.96, A/A dev 0.087)
  - steady / steady D=64 stash t=14 p99: 0.889 (range 0.88-1.00, A/A dev 0.077)
- rows <0.97 but inside the A/A spread: 2
  - steady / steady D=64 stash t=14 p50: 0.909 (range 0.90-1.09, A/A dev 0.101)
  - steady / steady D=64 stash t=14 p999: 0.800 (range 0.70-1.39, A/A dev 0.327)

Confirmation hold 2 on the M4 Pro (`bench_steady` only):

### stash m4: groups steady(5 A, 5 B, 5 A/A)

| group | row | START | HEAD | START/HEAD | range | A/A | A/A dev | n | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| steady | steady D=64 stash t=1 p50 | 125.0 | 125.0 | 1.000 | 0.67-1.00 | 1.000 | 0.000 | 5 | noise |
| steady | steady D=64 stash t=1 p99 | 500.0 | 542.0 | 0.923 | 0.86-1.00 | 1.000 | 0.183 | 5 | noise |
| steady | steady D=64 stash t=1 p999 | 875.0 | 1000.0 | 0.954 | 0.83-1.08 | 0.952 | 0.221 | 5 | noise |
| steady | steady D=64 stash t=4 p50 | 334.0 | 334.0 | 1.000 | 1.00-1.12 | 0.901 | 0.123 | 5 | noise |
| steady | steady D=64 stash t=4 p99 | 958.0 | 1083.0 | 0.885 | 0.85-0.92 | 0.999 | 0.080 | 5 | slower |
| steady | steady D=64 stash t=4 p999 | 1500.0 | 1708.0 | 0.878 | 0.78-1.29 | 0.972 | 0.150 | 5 | noise |
| steady | steady D=64 stash t=14 p50 | 792.0 | 834.0 | 0.951 | 0.86-1.10 | 1.001 | 0.100 | 5 | noise |
| steady | steady D=64 stash t=14 p99 | 2166.0 | 2292.0 | 0.928 | 0.87-1.04 | 1.021 | 0.077 | 5 | slower |
| steady | steady D=64 stash t=14 p999 | 9916.0 | 7250.0 | 1.368 | 0.58-2.66 | 2.041 | 1.515 | 5 | noise |
| steady | steady D=1024 stash t=1 p50 | 167.0 | 83.0 | 2.012 | 1.99-2.51 | 1.000 | 0.000 | 5 | faster |
| steady | steady D=1024 stash t=1 p99 | 583.0 | 416.0 | 1.401 | 1.33-1.50 | 1.000 | 0.166 | 5 | faster |
| steady | steady D=1024 stash t=1 p999 | 1416.0 | 667.0 | 2.000 | 1.06-2.67 | 1.311 | 1.106 | 5 | noise |
| steady | steady D=1024 stash t=4 p50 | 417.0 | 292.0 | 1.284 | 1.25-1.43 | 1.112 | 0.112 | 5 | faster |
| steady | steady D=1024 stash t=4 p99 | 1125.0 | 917.0 | 1.227 | 1.04-1.36 | 1.047 | 0.365 | 5 | noise |
| steady | steady D=1024 stash t=4 p999 | 3209.0 | 1209.0 | 2.656 | 1.07-3.14 | 1.100 | 1.700 | 5 | noise |
| steady | steady D=1024 stash t=14 p50 | 834.0 | 709.0 | 1.175 | 1.11-1.24 | 1.052 | 0.117 | 5 | faster |
| steady | steady D=1024 stash t=14 p99 | 1958.0 | 1917.0 | 1.000 | 0.91-1.09 | 1.000 | 0.119 | 5 | noise |
| steady | steady D=1024 stash t=14 p999 | 5167.0 | 3000.0 | 1.937 | 0.46-2.92 | 1.345 | 1.625 | 5 | noise |
| steady | steady D=16384 stash t=1 p50 | 250.0 | 42.0 | 5.952 | 5.95-5.95 | 1.000 | 0.000 | 5 | faster |
| steady | steady D=16384 stash t=1 p99 | 708.0 | 250.0 | 2.832 | 2.50-2.84 | 1.066 | 0.134 | 5 | faster |
| steady | steady D=16384 stash t=1 p999 | 1208.0 | 666.0 | 1.811 | 1.24-2.54 | 1.000 | 0.525 | 5 | faster |
| steady | steady D=16384 stash t=4 p50 | 625.0 | 292.0 | 2.140 | 2.14-2.50 | 1.070 | 0.072 | 5 | faster |
| steady | steady D=16384 stash t=4 p99 | 1667.0 | 834.0 | 1.905 | 1.50-2.80 | 1.000 | 0.931 | 5 | noise |
| steady | steady D=16384 stash t=4 p999 | 2917.0 | 1125.0 | 2.188 | 1.69-4.22 | 1.045 | 1.923 | 5 | noise |
| steady | steady D=16384 stash t=14 p50 | 1042.0 | 709.0 | 1.472 | 1.33-1.56 | 1.042 | 0.088 | 5 | faster |
| steady | steady D=16384 stash t=14 p99 | 2541.0 | 1834.0 | 1.378 | 1.16-1.45 | 1.020 | 0.230 | 5 | faster |
| steady | steady D=16384 stash t=14 p999 | 7959.0 | 2708.0 | 2.968 | 0.96-4.53 | 0.834 | 1.423 | 5 | faster |

- library rows: 27, geomean 1.514; A/A geomean 1.056
- control rows (unchanged code): 54, geomean 0.958, median 1.000, min 0.392, max 1.424
- per-group geomean: steady 1.514 (n=27)
- slow rows (<0.97 and outside A/A): 2
  - steady / steady D=64 stash t=4 p99: 0.885 (range 0.85-0.92, A/A dev 0.080)
  - steady / steady D=64 stash t=14 p99: 0.928 (range 0.87-1.04, A/A dev 0.077)
- rows <0.97 but inside the A/A spread: 4
  - steady / steady D=64 stash t=1 p99: 0.923 (range 0.86-1.00, A/A dev 0.183)
  - steady / steady D=64 stash t=1 p999: 0.954 (range 0.83-1.08, A/A dev 0.221)
  - steady / steady D=64 stash t=4 p999: 0.878 (range 0.78-1.29, A/A dev 0.150)
  - steady / steady D=64 stash t=14 p50: 0.951 (range 0.86-1.10, A/A dev 0.100)

## Intel i9-9980HK

Hold 1 (i9 hold): 11:25:29 to 11:32:01, `uptime` load `10.02 7.66 7.33` to `40.11 17.06 11.04` (the last group runs 1 024 threads again).
Hold 2 (i9 hold c, `bench_steady 300`, 5 rounds): 12:58:47 to 13:03:01, load `9.50 7.90 7.26` to `8.50 8.25 7.60`.

### stash i9: groups bursty(3 A, 3 B, 3 A/A), scheduler(3 A, 3 B, 3 A/A), steady(3 A, 3 B, 3 A/A), structures(3 A, 3 B, 3 A/A)

| group | row | START | HEAD | START/HEAD | range | A/A | A/A dev | n | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| bursty | bursty threads=256 add p50 | 1152.0 | 289.0 | 3.986 | 3.77-4.20 | 0.998 | 0.072 | 3 | faster |
| bursty | bursty threads=256 add p99 | 17982.0 | 1890.0 | 9.454 | 8.00-9.52 | 0.982 | 0.173 | 3 | faster |
| bursty | bursty threads=256 add p999 | 32119.0 | 20800.0 | 1.489 | 1.48-1.54 | 1.014 | 0.083 | 3 | faster |
| bursty | bursty threads=1024 add p50 | 2671.0 | 287.0 | 9.323 | 9.31-9.43 | 0.997 | 0.014 | 3 | faster |
| bursty | bursty threads=1024 add p99 | 7117.0 | 2171.0 | 3.278 | 2.90-3.76 | 0.957 | 0.053 | 3 | faster |
| bursty | bursty threads=1024 add p999 | 38423.0 | 48657.0 | 0.790 | 0.65-1.04 | 0.648 | 0.389 | 3 | noise |
| scheduler | scheduler A-spread stash t=1 insert | 518.1 | 320.5 | 1.592 | 1.58-1.69 | 1.027 | 0.062 | 3 | faster |
| scheduler | scheduler A-spread stash t=2 insert | 289.0 | 208.3 | 1.471 | 1.34-1.51 | 1.035 | 0.040 | 3 | faster |
| scheduler | scheduler A-spread stash t=4 insert | 167.8 | 116.1 | 1.464 | 1.42-1.49 | 1.059 | 0.123 | 3 | faster |
| scheduler | scheduler A-spread stash t=8 insert | 95.1 | 63.7 | 1.477 | 1.33-1.60 | 1.035 | 0.104 | 3 | faster |
| scheduler | scheduler A-spread stash t=14 insert | 64.9 | 43.6 | 1.487 | 1.25-1.51 | 1.000 | 0.103 | 3 | faster |
| scheduler | scheduler A-spread stash t=1 p99 | 835.0 | 375.0 | 2.237 | 2.14-2.44 | 1.013 | 0.083 | 3 | faster |
| scheduler | scheduler A-spread stash t=2 p99 | 851.0 | 403.0 | 2.112 | 2.05-2.29 | 1.054 | 0.072 | 3 | faster |
| scheduler | scheduler A-spread stash t=4 p99 | 909.0 | 445.0 | 2.043 | 1.94-2.05 | 1.032 | 0.066 | 3 | faster |
| scheduler | scheduler A-spread stash t=8 p99 | 952.0 | 506.0 | 1.967 | 1.65-2.08 | 1.025 | 0.144 | 3 | faster |
| scheduler | scheduler A-spread stash t=14 p99 | 1091.0 | 588.0 | 1.870 | 1.73-2.00 | 1.026 | 0.141 | 3 | faster |
| scheduler | scheduler B-convergent stash t=1 insert | 507.6 | 434.8 | 1.173 | 1.15-1.18 | 0.990 | 0.015 | 3 | faster |
| scheduler | scheduler B-convergent stash t=2 insert | 373.1 | 229.9 | 1.590 | 1.58-1.83 | 1.019 | 0.036 | 3 | faster |
| scheduler | scheduler B-convergent stash t=4 insert | 279.3 | 137.7 | 2.103 | 1.86-2.15 | 0.978 | 0.125 | 3 | faster |
| scheduler | scheduler B-convergent stash t=8 insert | 176.7 | 103.6 | 1.682 | 1.66-1.74 | 1.011 | 0.036 | 3 | faster |
| scheduler | scheduler B-convergent stash t=14 insert | 139.5 | 75.9 | 1.838 | 1.75-1.89 | 1.036 | 0.039 | 3 | faster |
| scheduler | scheduler B-convergent stash t=1 p99 | 576.0 | 435.0 | 1.324 | 1.22-1.34 | 0.987 | 0.059 | 3 | faster |
| scheduler | scheduler B-convergent stash t=2 p99 | 1020.0 | 548.0 | 1.861 | 1.53-2.19 | 1.050 | 0.086 | 3 | faster |
| scheduler | scheduler B-convergent stash t=4 p99 | 2432.0 | 716.0 | 3.221 | 3.07-3.47 | 1.005 | 0.046 | 3 | faster |
| scheduler | scheduler B-convergent stash t=8 p99 | 2360.0 | 1060.0 | 2.184 | 2.12-2.91 | 0.937 | 0.215 | 3 | faster |
| scheduler | scheduler B-convergent stash t=14 p99 | 3266.0 | 1419.0 | 2.266 | 2.26-2.35 | 0.999 | 0.037 | 3 | faster |
| steady | steady D=64 stash t=1 p50 | 192.0 | 179.0 | 1.073 | 1.02-1.07 | 1.000 | 0.016 | 3 | faster |
| steady | steady D=64 stash t=1 p99 | 439.0 | 416.0 | 1.055 | 0.97-1.07 | 0.991 | 0.058 | 3 | noise |
| steady | steady D=64 stash t=1 p999 | 2956.0 | 4398.0 | 0.540 | 0.20-0.79 | 0.756 | 0.538 | 3 | slower |
| steady | steady D=64 stash t=4 p50 | 313.0 | 303.0 | 1.017 | 0.96-1.03 | 1.013 | 0.020 | 3 | noise |
| steady | steady D=64 stash t=4 p99 | 712.0 | 751.0 | 0.928 | 0.84-0.95 | 0.975 | 0.042 | 3 | slower |
| steady | steady D=64 stash t=4 p999 | 18558.0 | 20634.0 | 1.045 | 0.75-8.27 | 0.917 | 0.212 | 3 | noise |
| steady | steady D=64 stash t=14 p50 | 536.0 | 532.0 | 1.000 | 0.99-1.02 | 0.998 | 0.031 | 3 | noise |
| steady | steady D=64 stash t=14 p99 | 1260.0 | 1363.0 | 0.924 | 0.91-0.93 | 1.000 | 0.013 | 3 | slower |
| steady | steady D=64 stash t=14 p999 | 4933.0 | 6337.0 | 0.778 | 0.55-2.21 | 1.028 | 0.209 | 3 | slower |
| steady | steady D=1024 stash t=1 p50 | 211.0 | 173.0 | 1.220 | 1.21-1.32 | 1.014 | 0.104 | 3 | faster |
| steady | steady D=1024 stash t=1 p99 | 499.0 | 382.0 | 1.306 | 1.30-1.35 | 1.016 | 0.105 | 3 | faster |
| steady | steady D=1024 stash t=1 p999 | 1952.0 | 776.0 | 2.488 | 0.51-2.63 | 1.064 | 0.171 | 3 | faster |
| steady | steady D=1024 stash t=4 p50 | 408.0 | 268.0 | 1.515 | 1.46-1.52 | 0.990 | 0.041 | 3 | faster |
| steady | steady D=1024 stash t=4 p99 | 1060.0 | 604.0 | 1.764 | 1.64-1.79 | 1.017 | 0.061 | 3 | faster |
| steady | steady D=1024 stash t=4 p999 | 25233.0 | 20497.0 | 1.281 | 1.18-1.42 | 1.095 | 0.300 | 3 | noise |
| steady | steady D=1024 stash t=14 p50 | 617.0 | 444.0 | 1.390 | 1.37-1.44 | 1.003 | 0.030 | 3 | faster |
| steady | steady D=1024 stash t=14 p99 | 1541.0 | 1122.0 | 1.371 | 1.35-1.39 | 1.015 | 0.025 | 3 | faster |
| steady | steady D=1024 stash t=14 p999 | 2948.0 | 2206.0 | 1.495 | 1.14-1.70 | 0.976 | 0.231 | 3 | faster |
| steady | steady D=16384 stash t=1 p50 | 272.0 | 144.0 | 1.929 | 1.88-2.02 | 1.004 | 0.104 | 3 | faster |
| steady | steady D=16384 stash t=1 p99 | 653.0 | 341.0 | 1.937 | 1.91-2.08 | 1.024 | 0.091 | 3 | faster |
| steady | steady D=16384 stash t=1 p999 | 2090.0 | 2007.0 | 1.085 | 0.53-8.04 | 0.892 | 5.447 | 3 | noise |
| steady | steady D=16384 stash t=4 p50 | 640.0 | 266.0 | 2.400 | 2.36-2.41 | 1.005 | 0.132 | 3 | faster |
| steady | steady D=16384 stash t=4 p99 | 1951.0 | 612.0 | 3.109 | 3.01-3.22 | 1.019 | 0.028 | 3 | faster |
| steady | steady D=16384 stash t=4 p999 | 24252.0 | 17694.0 | 1.515 | 1.27-2.27 | 0.946 | 0.829 | 3 | noise |
| steady | steady D=16384 stash t=14 p50 | 905.0 | 419.0 | 2.160 | 2.12-2.26 | 1.000 | 0.034 | 3 | faster |
| steady | steady D=16384 stash t=14 p99 | 2684.0 | 1087.0 | 2.443 | 2.43-2.54 | 1.038 | 0.062 | 3 | faster |
| steady | steady D=16384 stash t=14 p999 | 16444.0 | 2247.0 | 7.511 | 5.09-8.51 | 1.174 | 0.284 | 3 | faster |
| structures | structures A-spread stash t=1 insert | 561.8 | 324.7 | 1.730 | 1.70-1.78 | 0.966 | 0.051 | 3 | faster |
| structures | structures A-spread stash t=2 insert | 325.7 | 195.3 | 1.631 | 1.61-1.77 | 0.980 | 0.057 | 3 | faster |
| structures | structures A-spread stash t=4 insert | 184.8 | 113.2 | 1.628 | 1.62-1.84 | 0.983 | 0.026 | 3 | faster |
| structures | structures A-spread stash t=8 insert | 110.2 | 65.5 | 1.683 | 1.65-1.90 | 1.076 | 0.105 | 3 | faster |
| structures | structures A-spread stash t=14 insert | 67.8 | 43.1 | 1.575 | 1.34-1.70 | 0.976 | 0.125 | 3 | faster |
| structures | structures A-spread stash t=1 p99 | 966.0 | 318.0 | 2.936 | 2.91-3.12 | 0.988 | 0.019 | 3 | faster |
| structures | structures A-spread stash t=2 p99 | 1030.0 | 369.0 | 2.791 | 2.48-3.01 | 1.008 | 0.045 | 3 | faster |
| structures | structures A-spread stash t=4 p99 | 1116.0 | 411.0 | 2.715 | 2.64-2.81 | 0.994 | 0.068 | 3 | faster |
| structures | structures A-spread stash t=8 p99 | 1162.0 | 496.0 | 2.416 | 2.26-2.56 | 0.984 | 0.154 | 3 | faster |
| structures | structures A-spread stash t=14 p99 | 1261.0 | 603.0 | 2.081 | 2.07-2.57 | 1.002 | 0.146 | 3 | faster |
| structures | structures B-convergent stash t=1 insert | 523.6 | 444.4 | 1.172 | 1.16-1.21 | 1.016 | 0.021 | 3 | faster |
| structures | structures B-convergent stash t=2 insert | 386.1 | 222.7 | 1.791 | 1.69-1.80 | 1.035 | 0.048 | 3 | faster |
| structures | structures B-convergent stash t=4 insert | 288.2 | 145.1 | 1.977 | 1.91-2.02 | 1.079 | 0.089 | 3 | faster |
| structures | structures B-convergent stash t=8 insert | 177.3 | 102.9 | 1.732 | 1.70-1.74 | 1.011 | 0.014 | 3 | faster |
| structures | structures B-convergent stash t=14 insert | 134.9 | 75.0 | 1.796 | 1.79-1.85 | 0.991 | 0.030 | 3 | faster |
| structures | structures B-convergent stash t=1 p99 | 584.0 | 449.0 | 1.322 | 1.30-1.39 | 0.990 | 0.041 | 3 | faster |
| structures | structures B-convergent stash t=2 p99 | 1066.0 | 572.0 | 1.864 | 1.67-2.01 | 1.008 | 0.065 | 3 | faster |
| structures | structures B-convergent stash t=4 p99 | 2407.0 | 766.0 | 3.142 | 3.13-3.15 | 1.036 | 0.037 | 3 | faster |
| structures | structures B-convergent stash t=8 p99 | 2657.0 | 1059.0 | 2.509 | 2.38-2.57 | 0.974 | 0.029 | 3 | faster |
| structures | structures B-convergent stash t=14 p99 | 3273.0 | 1401.0 | 2.360 | 2.27-2.38 | 1.020 | 0.029 | 3 | faster |

- library rows: 73, geomean 1.800; A/A geomean 0.998
- control rows (unchanged code): 154, geomean 0.999, median 0.996, min 0.669, max 1.245
- per-group geomean: bursty 3.326 (n=6), scheduler 1.800 (n=20), steady 1.466 (n=27), structures 1.974 (n=20)
- slow rows (<0.97 and outside A/A): 4
  - steady / steady D=64 stash t=1 p999: 0.540 (range 0.20-0.79, A/A dev 0.538)
  - steady / steady D=64 stash t=4 p99: 0.928 (range 0.84-0.95, A/A dev 0.042)
  - steady / steady D=64 stash t=14 p99: 0.924 (range 0.91-0.93, A/A dev 0.013)
  - steady / steady D=64 stash t=14 p999: 0.778 (range 0.55-2.21, A/A dev 0.209)
- rows <0.97 but inside the A/A spread: 1
  - bursty / bursty threads=1024 add p999: 0.790 (range 0.65-1.04, A/A dev 0.389)

Confirmation hold 2 on the i9 (`bench_steady` only):

### stash i9: groups steady(5 A, 5 B, 5 A/A)

| group | row | START | HEAD | START/HEAD | range | A/A | A/A dev | n | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| steady | steady D=64 stash t=1 p50 | 186.0 | 173.0 | 1.075 | 0.99-1.09 | 1.027 | 0.087 | 5 | noise |
| steady | steady D=64 stash t=1 p99 | 418.0 | 402.0 | 1.054 | 1.02-1.09 | 0.995 | 0.086 | 5 | noise |
| steady | steady D=64 stash t=1 p999 | 3603.0 | 2644.0 | 1.193 | 0.40-7.35 | 1.708 | 3.670 | 5 | noise |
| steady | steady D=64 stash t=4 p50 | 310.0 | 299.0 | 1.043 | 1.03-1.09 | 1.027 | 0.076 | 5 | noise |
| steady | steady D=64 stash t=4 p99 | 679.0 | 709.0 | 0.958 | 0.90-0.98 | 0.990 | 0.078 | 5 | noise |
| steady | steady D=64 stash t=4 p999 | 17356.0 | 17237.0 | 0.972 | 0.95-2.83 | 0.811 | 0.818 | 5 | noise |
| steady | steady D=64 stash t=14 p50 | 535.0 | 528.0 | 1.009 | 0.96-1.06 | 1.006 | 0.087 | 5 | noise |
| steady | steady D=64 stash t=14 p99 | 1214.0 | 1317.0 | 0.922 | 0.86-0.96 | 0.997 | 0.108 | 5 | noise |
| steady | steady D=64 stash t=14 p999 | 2171.0 | 3760.0 | 0.753 | 0.49-1.16 | 0.565 | 1.803 | 5 | noise |
| steady | steady D=1024 stash t=1 p50 | 206.0 | 162.0 | 1.258 | 1.22-1.33 | 0.990 | 0.048 | 5 | faster |
| steady | steady D=1024 stash t=1 p99 | 485.0 | 352.0 | 1.378 | 1.29-1.46 | 0.996 | 0.045 | 5 | faster |
| steady | steady D=1024 stash t=1 p999 | 1819.0 | 790.0 | 2.089 | 0.68-2.40 | 0.901 | 0.241 | 5 | faster |
| steady | steady D=1024 stash t=4 p50 | 403.0 | 253.0 | 1.593 | 1.56-1.69 | 1.005 | 0.031 | 5 | faster |
| steady | steady D=1024 stash t=4 p99 | 1046.0 | 560.0 | 1.837 | 1.78-1.88 | 1.016 | 0.035 | 5 | faster |
| steady | steady D=1024 stash t=4 p999 | 22218.0 | 16345.0 | 1.412 | 1.14-1.45 | 1.126 | 0.325 | 5 | faster |
| steady | steady D=1024 stash t=14 p50 | 615.0 | 431.0 | 1.411 | 1.35-1.47 | 1.016 | 0.086 | 5 | faster |
| steady | steady D=1024 stash t=14 p99 | 1554.0 | 1112.0 | 1.397 | 1.31-1.44 | 1.020 | 0.095 | 5 | faster |
| steady | steady D=1024 stash t=14 p999 | 10983.0 | 2998.0 | 3.663 | 0.76-6.23 | 3.428 | 4.402 | 5 | noise |
| steady | steady D=16384 stash t=1 p50 | 270.0 | 138.0 | 1.957 | 1.91-2.01 | 0.982 | 0.033 | 5 | faster |
| steady | steady D=16384 stash t=1 p99 | 645.0 | 324.0 | 1.994 | 1.97-2.02 | 0.992 | 0.030 | 5 | faster |
| steady | steady D=16384 stash t=1 p999 | 3470.0 | 1675.0 | 4.111 | 1.04-22.20 | 1.803 | 9.923 | 5 | noise |
| steady | steady D=16384 stash t=4 p50 | 644.0 | 264.0 | 2.420 | 2.39-2.71 | 1.005 | 0.013 | 5 | faster |
| steady | steady D=16384 stash t=4 p99 | 1879.0 | 600.0 | 3.137 | 3.08-3.23 | 1.014 | 0.029 | 5 | faster |
| steady | steady D=16384 stash t=4 p999 | 24708.0 | 17698.0 | 1.405 | 1.36-1.48 | 1.003 | 0.106 | 5 | faster |
| steady | steady D=16384 stash t=14 p50 | 898.0 | 400.0 | 2.234 | 2.19-2.29 | 1.012 | 0.035 | 5 | faster |
| steady | steady D=16384 stash t=14 p99 | 2561.0 | 1047.0 | 2.446 | 2.42-2.46 | 0.998 | 0.026 | 5 | faster |
| steady | steady D=16384 stash t=14 p999 | 10351.0 | 2054.0 | 5.633 | 2.92-6.62 | 1.074 | 0.197 | 5 | faster |

- library rows: 27, geomean 1.629; A/A geomean 1.067
- control rows (unchanged code): 54, geomean 0.980, median 0.987, min 0.674, max 1.179
- per-group geomean: steady 1.629 (n=27)
- slow rows (<0.97 and outside A/A): 0
- rows <0.97 but inside the A/A spread: 3
  - steady / steady D=64 stash t=4 p99: 0.958 (range 0.90-0.98, A/A dev 0.078)
  - steady / steady D=64 stash t=14 p99: 0.922 (range 0.86-0.96, A/A dev 0.108)
  - steady / steady D=64 stash t=14 p999: 0.753 (range 0.49-1.16, A/A dev 1.803)

## Rows < 0.97 outside the A/A spread

A row counts as real when it is below 0.97 and outside the A/A spread in one hold and again in the second hold or on the other machine.

| row (`bench_steady`, depth 64, arm latency in ns) | M4 Pro hold 1 / hold 2 | i9 hold 1 / hold 2 | cause |
|---|---|---|---|
| `steady D=64 stash t=4 p99` | **0.884** (958 to 1083 ns) / **0.885** | **0.928** (712 to 751 ns) / 0.958 (inside spread) | Probable, from the diff and the shape of the rows, not isolated: p50 is unchanged and only the p99 moves (+40 to +250 ns), only at depth 64 where almost every insert opens a new leaf. `StashValues::put` now does an acquire load of `atom_claim_hint` and, on a leaf's first claim, a CAS to publish it, and the leaf is 16 bytes bigger (CHANGELOG 2026-10-31 states the size, not a time cost). The trade buys the removal of the quadratic chain walk, worth up to 9x on the other rows (geomean 1.75x to 1.80x). |
| `steady D=64 stash t=14 p99` | **0.889** (2083 to 2333 ns) / **0.928** | **0.924** / 0.922 (inside spread) | same |

Seen once and not reproduced, counted as noise (the p999 of a 250 to 300 ms run is set by a few scheduler preemptions; the A/A pairs differ by up to 3.7x): `steady D=64 t=1 p999` (i9 hold 1 0.540 with A/A dev 0.538; i9 hold 2 1.193, M4 1.227 and 0.954), `steady D=64 t=14 p999` (i9 0.778 outside a spread of 0.209 in hold 1, 0.753 inside a spread of 1.8 in hold 2; M4 0.800 inside, 1.368), `bursty threads=1024 add p999` (i9 0.790 inside a spread of 0.389), `steady D=64 t=14 p50` (M4 0.909 and 0.951, both inside a spread of 0.10; i9 1.000). Every other row on both machines is above 0.97.

## Rows dropped or not comparable

- None dropped: all 73 stash rows exist in both binaries.
- The speed-ups are not the same work done faster: HEAD removes a quadratic chain walk, so the rows that put many keys into one leaf (A-spread at low producer counts, B-convergent, bursty) do far fewer chain steps than START. The ratio there measures the fix, not a constant-factor change. API, results and orders are unchanged (CHANGELOG 2026-10-31).
- `bench_scheduler` and `bench_structures` use smaller totals than their defaults; `bench_steady` runs 250 ms per configuration instead of 600 ms.
- Insert rows are `1000 / Mops` of the bench's best-of-3 line (Mops has two decimals, so a 100 ns row is quantised to about 1%).

## Rig notes

- Holds waited 67 minutes (M4 hold 1, queued 09:28), 1 h 42 min (i9 hold 1, queued 09:43), 33 minutes (M4 hold 2, queued 10:43) and 1 h 25 min (i9 hold 2) in a queue of 20 to 40 strict holds from other gate runs. The builds waited 15 minutes for a light slot (the strict queue blocks light holds) and then ran at `nice -n 19 -j4` outside a hold, as the recipe allows after starvation; no timing was taken outside a hold.
- A short unheld smoke run of every binary (tiny arguments, all rows present, nothing recorded) preceded the first hold.
- The M4 Pro load average is 7 to 20 before and after the holds (other sessions' processes); the A/A pairs absorb it.

SUMMARY repo=stash m4_geomean=1.745 i9_geomean=1.800 m4_slow=2/0.884 i9_slow=2/0.922 unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- `steady D=64` p99 with 4 and 14 arming threads (M4 0.884 and 0.889, i9 0.928 and 0.924):
  accepted. `put` loads the leaf's claim hint and makes one compare-exchange on a leaf's first
  claim, and a leaf is 16 bytes larger (CHANGELOG). The same change removed a quadratic chain walk,
  which is most of the 1.745 and 1.800. On the i9 the rows are inside the spread in a second hold.
