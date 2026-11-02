# radix-router: START 35aab1b to HEAD 206c530

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/radix-router#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`); HEAD is `origin/main` when this run started.

**Status: complete** (m4 3 of 3 rounds, i9 3 of 3 rounds). 

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64), macOS 26 (Darwin 25.6.0), Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja |
| i9 | Intel i9-9980HK (8C/16T, x86-64), macOS 15 (Darwin 24.6.0), Apple clang 17.0.0 (clang-1700.6.4.2), CMake, Ninja |

- Bench: HEAD's `bench/compare.cc` (radix::Router against a segment trie and a hash map of exact routes; `ours ns` is the column compared). `radix_router.h` is byte-identical at START and HEAD (`git diff 35aab1b origin/main -- radix_router.h` is empty), so the START and HEAD binaries are the same code and every ratio is placement and noise.
- Builds: Release (`-O3 -DNDEBUG`), same compiler and flags for both sides, library sources only differ (see Commands).
- Every round runs START, HEAD, then START again (the A/A control, a second copy of the START binary), interleaved in one hold; ratios are the median of the paired rounds, START time / HEAD time (above 1 is faster now). `A/A dev` is the largest |A/A - 1| over the rounds.

## Commands

```sh
git clone https://github.com/Kronuz/radix-router && cd radix-router
# START 35aab1bb5b58c9ba1aaa0d299783be1b53343255   HEAD 206c5305e17c9f681154eda64fa59e1cf4295776
git worktree add --detach trees/radix-router-head 206c5305e17c9f681154eda64fa59e1cf4295776
git worktree add --detach trees/radix-router-start 206c5305e17c9f681154eda64fa59e1cf4295776
(cd trees/radix-router-start && git rm -rq -- radix_router.h && git checkout 35aab1bb5b58c9ba1aaa0d299783be1b53343255 -- radix_router.h)   # HEAD's tree and bench, START's library files
cmake -S trees/radix-router-{head,start} -B trees/radix-router-{head,start}/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DRADIX_ROUTER_BUILD_BENCH=ON
cmake --build trees/radix-router-{head,start}/build --target radix_router_compare    # bench: bench/compare.cc (HEAD's)
# each round, in one quiet strict hold (<= 10 min): START, HEAD, START again (copy of the START binary)
for side in start head startcopy; do bin/radix-router.radix_router_compare.$side > out/radix-router/<a|b|aa>-N.txt; done
python3 rig/gate.py REPO m4|i9      # paired ratios via cpp-libraries/tools/ab_compare.py (read_runs, compare)
```

## Summary

| machine | set | rounds | rows | geomean START/HEAD | A/A geomean | rows <0.97 outside A/A | worst | rows <0.97 inside A/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| m4 | all | 3 | 12 | 1.020 | 1.016 | 0 | - | 0 |
| i9 | all | 3 | 12 | 1.003 | 0.995 | 0 | - | 0 |

## Rows below 0.97 outside the A/A spread

None.

## Verdict

SAME. `radix_router.h` is identical at START and HEAD, so the ratios are placement and noise: geomean 1.02 on the M4 (rows 0.98 to 1.05) and 1.00 on the i9 (rows 1.00 to 1.01), no row below 0.97 on either machine.

## Rows: m4

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| 16 routes static hit | segment trie on absl::flat_hash_map | 21.8 ns | 20.7 ns | 1.026 | 1.018-1.074 | 4.9% | noise |
| 16 routes static hit | exact paths in absl::flat_hash_map | 21.7 ns | 21.2 ns | 1.016 | 0.969-1.041 | 5.2% | noise |
| 16 routes param hit | segment trie on absl::flat_hash_map | 38.6 ns | 37.8 ns | 1.002 | 0.987-1.048 | 4.4% | noise |
| 16 routes miss | segment trie on absl::flat_hash_map | 12.5 ns | 12.4 ns | 1.006 | 0.981-1.064 | 3.6% | noise |
| 128 routes static hit | segment trie on absl::flat_hash_map | 29.3 ns | 28.1 ns | 1.037 | 0.995-1.124 | 9.2% | noise |
| 128 routes static hit | exact paths in absl::flat_hash_map | 29.0 ns | 27.8 ns | 1.041 | 0.976-1.095 | 9.2% | noise |
| 128 routes param hit | segment trie on absl::flat_hash_map | 43.5 ns | 44.0 ns | 1.005 | 0.982-1.022 | 5.1% | noise |
| 128 routes miss | segment trie on absl::flat_hash_map | 12.5 ns | 11.9 ns | 1.051 | 1.011-1.066 | 4.7% | faster |
| 1024 routes static hit | segment trie on absl::flat_hash_map | 35.5 ns | 35.0 ns | 1.025 | 0.923-1.253 | 21.7% | noise |
| 1024 routes static hit | exact paths in absl::flat_hash_map | 36.5 ns | 35.5 ns | 1.028 | 0.982-1.266 | 20.5% | noise |
| 1024 routes param hit | segment trie on absl::flat_hash_map | 58.0 ns | 59.1 ns | 0.981 | 0.929-1.088 | 10.4% | noise |
| 1024 routes miss | segment trie on absl::flat_hash_map | 12.0 ns | 11.7 ns | 1.024 | 0.995-1.069 | 5.6% | noise |

## Rows: i9

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| 16 routes static hit | segment trie on absl::flat_hash_map | 40.1 ns | 40.0 ns | 1.007 | 1.004-1.023 | 1.0% | noise |
| 16 routes static hit | exact paths in absl::flat_hash_map | 40.3 ns | 40.1 ns | 1.006 | 1.005-1.014 | 1.8% | noise |
| 16 routes param hit | segment trie on absl::flat_hash_map | 72.5 ns | 71.4 ns | 1.011 | 0.992-1.017 | 1.1% | noise |
| 16 routes miss | segment trie on absl::flat_hash_map | 25.6 ns | 26.0 ns | 0.997 | 0.977-1.005 | 3.6% | noise |
| 128 routes static hit | segment trie on absl::flat_hash_map | 56.7 ns | 58.0 ns | 0.999 | 0.974-1.009 | 3.9% | noise |
| 128 routes static hit | exact paths in absl::flat_hash_map | 57.5 ns | 57.2 ns | 1.004 | 0.973-1.016 | 1.7% | noise |
| 128 routes param hit | segment trie on absl::flat_hash_map | 89.1 ns | 89.3 ns | 1.003 | 0.975-1.024 | 5.2% | noise |
| 128 routes miss | segment trie on absl::flat_hash_map | 25.4 ns | 25.4 ns | 1.000 | 0.977-1.001 | 4.0% | noise |
| 1024 routes static hit | segment trie on absl::flat_hash_map | 88.5 ns | 87.0 ns | 1.004 | 1.002-1.020 | 2.0% | noise |
| 1024 routes static hit | exact paths in absl::flat_hash_map | 88.0 ns | 87.0 ns | 1.002 | 0.991-1.031 | 4.5% | noise |
| 1024 routes param hit | segment trie on absl::flat_hash_map | 121 ns | 120 ns | 1.003 | 0.959-1.034 | 3.8% | noise |
| 1024 routes miss | segment trie on absl::flat_hash_map | 25.2 ns | 25.2 ns | 1.004 | 1.003-1.009 | 3.7% | noise |
