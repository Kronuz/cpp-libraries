# boolean-parser: START 41a20b5 to HEAD 00ce82d

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/boolean-parser#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`); HEAD is `origin/main` when this run started.

**Status: complete** (m4 3 of 3 rounds, i9 3 of 3 rounds). 

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64), macOS 26 (Darwin 25.6.0), Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja |
| i9 | Intel i9-9980HK (8C/16T, x86-64), macOS 15 (Darwin 24.6.0), Apple clang 17.0.0 (clang-1700.6.4.2), CMake, Ninja |

- Bench: HEAD's `bench/bench_bool.cc` + `test/new_dump.cc` (+ the frozen original in `test/frozen`, which only feeds the `frozen old` rows); only `current #1` is compared. START `41a20b5` (10-28) has no `BooleanTokenVector.h`; HEAD `00ce82d`.
- Builds: Release (`-O3 -DNDEBUG`), same compiler and flags for both sides, library sources only differ (see Commands).
- Every round runs START, HEAD, then START again (the A/A control, a second copy of the START binary), interleaved in one hold; ratios are the median of the paired rounds, START time / HEAD time (above 1 is faster now). `A/A dev` is the largest |A/A - 1| over the rounds.

## Commands

```sh
git clone https://github.com/Kronuz/boolean-parser && cd boolean-parser
# START 41a20b53e259639dc723455e8a502d467819e026   HEAD 00ce82d146b24e45c65d639a2332e1a267a7c7c4
git worktree add --detach trees/boolean-parser-head 00ce82d146b24e45c65d639a2332e1a267a7c7c4
git worktree add --detach trees/boolean-parser-start 00ce82d146b24e45c65d639a2332e1a267a7c7c4
(cd trees/boolean-parser-start && git rm -rq -- the root-level *.cc and *.h (the library); BooleanTokenVector.h exists only at HEAD && git checkout 41a20b53e259639dc723455e8a502d467819e026 -- the root-level *.cc and *.h (the library); BooleanTokenVector.h exists only at HEAD)   # HEAD's tree and bench, START's library files
cmake -S trees/boolean-parser-{head,start} -B trees/boolean-parser-{head,start}/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DBOOLEAN_PARSER_BENCH=ON
cmake --build trees/boolean-parser-{head,start}/build --target boolean_parser_bench    # bench: bench/bench_bool.cc (HEAD's)
# each round, in one quiet strict hold (<= 10 min): START, HEAD, START again (copy of the START binary)
for side in start head startcopy; do bin/boolean-parser.boolean_parser_bench.$side > out/boolean-parser/<a|b|aa>-N.txt; done
python3 rig/gate.py REPO m4|i9      # paired ratios via cpp-libraries/tools/ab_compare.py (read_runs, compare)
```

## Summary

| machine | set | rounds | rows | geomean START/HEAD | A/A geomean | rows <0.97 outside A/A | worst | rows <0.97 inside A/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| m4 | all | 3 | 7 | 2.705 | 0.991 | 0 | - | 0 |
| i9 | all | 3 | 7 | 3.431 | 1.006 | 0 | - | 0 |

## Context: HEAD against the frozen original in the bench

The bench also times a frozen copy of the pre-campaign code (`test/urldecode_old.h`, `test/frozen`, `test/http_parser_old.cc`) in the same process as HEAD. This is not START (START is already past some of the work); it shows where HEAD stands against the original. Ratio is original time / HEAD time, median over the rounds.

| machine | rows | geomean original/HEAD | worst row | best row |
|---|---:|---:|---|---|
| m4 | 7 | 2.73 | bool 1024 terms random 1.76 | bool typical query 3.51 |
| i9 | 7 | 3.43 | bool 1024 terms random 1.90 | bool typical query 5.02 |

## Rows below 0.97 outside the A/A spread

None.

## Correctness changes that affect comparability

- HEAD fixes implicit-`OR` precedence and left associativity in `toRPN` (CHANGELOG 2026-10-31): inputs with adjacent terms or repeated same-level operators produce a different RPN queue and tree than START, and malformed input now throws at construction (`validate()`). The `random terms` rows contain such inputs, so those rows parse a different tree on each side; the 2 terms, 5 terms mixed, typical query and nested rows have no implicit OR and build the same tree.

## Verdict

FASTER. No row below 0.97 on either machine: geomean 2.7x on the M4 (1.8x to 3.5x per row) and 3.4x on the i9 (1.9x to 5.1x). The `random terms` rows parse a different tree on each side (the implicit-OR fix), see Correctness.

## Rows: m4

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| bool 2 terms current #1 | 262 ns | 80.0 ns | 3.252 | 3.221-3.289 | 1.4% | faster |
| bool 5 terms mixed current #1 | 601 ns | 198 ns | 3.028 | 2.972-3.030 | 1.9% | faster |
| bool typical query current #1 | 772 ns | 223 ns | 3.455 | 3.397-3.477 | 7.1% | faster |
| bool 16 terms random current #1 | 2930 ns | 1031 ns | 2.842 | 2.762-2.878 | 3.2% | faster |
| bool 128 terms random current #1 | 25.5 us | 8225 ns | 3.097 | 3.017-3.174 | 2.6% | faster |
| bool 1024 terms random current #1 | 185.8 us | 104.0 us | 1.782 | 1.747-1.795 | 11.3% | faster |
| bool deep nest 200 current #1 | 5028 ns | 2532 ns | 1.987 | 1.979-2.022 | 2.7% | faster |

## Rows: i9

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| bool 2 terms current #1 | 699 ns | 147 ns | 4.739 | 4.685-4.920 | 3.6% | faster |
| bool 5 terms mixed current #1 | 1690 ns | 395 ns | 4.282 | 4.137-4.292 | 3.9% | faster |
| bool typical query current #1 | 1977 ns | 391 ns | 5.059 | 5.043-5.177 | 4.9% | faster |
| bool 16 terms random current #1 | 7724 ns | 2042 ns | 3.816 | 3.768-4.302 | 10.0% | faster |
| bool 128 terms random current #1 | 66.2 us | 17.6 us | 3.761 | 3.680-3.813 | 1.3% | faster |
| bool 1024 terms random current #1 | 463.1 us | 247.6 us | 1.870 | 1.860-1.880 | 3.9% | faster |
| bool deep nest 200 current #1 | 10.8 us | 5332 ns | 2.030 | 2.006-2.095 | 5.7% | faster |
