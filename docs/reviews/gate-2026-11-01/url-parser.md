# url-parser: START 4424e25 to HEAD 2c9ea8e

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/url-parser#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`); HEAD is `origin/main` when this run started.

**Status: complete** (m4 3 of 3 rounds, i9 3 of 3 rounds). 

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64), macOS 26 (Darwin 25.6.0), Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja |
| i9 | Intel i9-9980HK (8C/16T, x86-64), macOS 15 (Darwin 24.6.0), Apple clang 17.0.0 (clang-1700.6.4.2), CMake, Ninja |

- Bench: HEAD's `bench/bench_url.cc` (+ `bench/harness.h`, `test/urldecode_old.h`) with the ada comparator off (`-DURL_PARSER_BENCH_ADA=OFF`, those rows only compare ada); only the `current #1` rows (the library) are compared, the in-binary `current #2 (A/A)`, `frozen old` and `LUT` rows are not.
- START `4424e25` is the byte-at-a-time decoder with the 10-28 overflow bound; HEAD `2c9ea8e` is `origin/main` at 08:46 on 2026-11-01 (the url-parser developer was still landing changes; HEAD is pinned to that sha on both machines).
- START builds the same HEAD tree with `url_parser.cc` and `url_parser.h` taken from START; HEAD's CMake pins char-classify for both.
- Builds: Release (`-O3 -DNDEBUG`), same compiler and flags for both sides, library sources only differ (see Commands).
- Every round runs START, HEAD, then START again (the A/A control, a second copy of the START binary), interleaved in one hold; ratios are the median of the paired rounds, START time / HEAD time (above 1 is faster now). `A/A dev` is the largest |A/A - 1| over the rounds.

## Commands

```sh
git clone https://github.com/Kronuz/url-parser && cd url-parser
# START 4424e25c53c54ae5697ddae2dd643885d921b4e2   HEAD 2c9ea8e
git worktree add --detach trees/url-parser-head 2c9ea8e
git worktree add --detach trees/url-parser-start 2c9ea8e
(cd trees/url-parser-start && git rm -rq -- url_parser.cc url_parser.h && git checkout 4424e25c53c54ae5697ddae2dd643885d921b4e2 -- url_parser.cc url_parser.h)   # HEAD's tree and bench, START's library files
cmake -S trees/url-parser-{head,start} -B trees/url-parser-{head,start}/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DURL_PARSER_BENCH=ON -DURL_PARSER_BENCH_ADA=OFF
cmake --build trees/url-parser-{head,start}/build --target url_parser_bench    # bench: bench/bench_url.cc (HEAD's)
# each round, in one quiet strict hold (<= 10 min): START, HEAD, START again (copy of the START binary)
for side in start head startcopy; do bin/url-parser.url_parser_bench.$side > out/url-parser/<a|b|aa>-N.txt; done
python3 rig/gate.py REPO m4|i9      # paired ratios via cpp-libraries/tools/ab_compare.py (read_runs, compare)
```

## Summary

| machine | set | rounds | rows | geomean START/HEAD | A/A geomean | rows <0.97 outside A/A | worst | rows <0.97 inside A/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| m4 | all | 3 | 28 | 7.987 | 1.002 | 0 | - | 0 |
| i9 | all | 3 | 28 | 7.750 | 0.990 | 0 | - | 0 |

## Context: HEAD against the frozen original in the bench

The bench also times a frozen copy of the pre-campaign code (`test/urldecode_old.h`, `test/frozen`, `test/http_parser_old.cc`) in the same process as HEAD. This is not START (START is already past some of the work); it shows where HEAD stands against the original. Ratio is original time / HEAD time, median over the rounds.

| machine | rows | geomean original/HEAD | worst row | best row |
|---|---:|---:|---|---|
| m4 | 16 | 5.61 | url urldecode 32B 25%-escapes 1.27 | url urldecode 65536B clean 83.95 |
| i9 | 16 | 8.55 | url urldecode 32B few-escapes 2.56 | url urldecode 65536B clean 162.71 |

## Rows below 0.97 outside the A/A spread

None.

## Correctness changes that affect comparability

- HEAD's `normalize_path` (the helper `PathParser::init` runs first) pops `..` like any other component (`a/..` is `.`, `a/../b` is `b`) and accepts a null view; the bench's paths contain no `..`, so the PathParser rows do the same work on both sides.
- START is itself slower than the decoder from before the campaign on short input (the bench's `frozen old` row: START 18.3 ns against 11.6 ns at 8 B clean on the M4), so START/HEAD ratios above overstate the gain against the original; the table 'Context' gives HEAD against that original.

## Verdict

FASTER. Every row is faster at HEAD on both machines (geomean 8.0x on the M4, 7.8x on the i9); no row is below 0.97. The smallest gain is a short path (`PathParser::init` + `next`, 8 B: 1.65x on the M4, 1.53x on the i9). Against the pre-campaign decoder the bench carries, HEAD is faster on every row too (see Context).

## Rows: m4

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| url urldecode 8B clean current #1 | 18.3 ns | 5.80 ns | 3.211 | 3.017-3.224 | 8.1% | faster |
| url urldecode 8B few-escapes current #1 | 18.5 ns | 5.80 ns | 3.190 | 3.136-3.241 | 4.4% | faster |
| url urldecode 8B 25%-escapes current #1 | 18.2 ns | 5.60 ns | 3.250 | 3.232-3.393 | 7.3% | faster |
| url urldecode 16B clean current #1 | 34.9 ns | 4.90 ns | 7.122 | 7.020-7.143 | 5.7% | faster |
| url urldecode 16B few-escapes current #1 | 34.4 ns | 7.80 ns | 4.300 | 4.244-4.603 | 8.3% | faster |
| url urldecode 16B 25%-escapes current #1 | 32.2 ns | 11.2 ns | 2.892 | 2.875-2.911 | 4.7% | faster |
| url urldecode 32B clean current #1 | 93.1 ns | 18.3 ns | 5.060 | 5.055-5.291 | 4.7% | faster |
| url urldecode 32B few-escapes current #1 | 84.7 ns | 32.4 ns | 2.614 | 2.567-2.832 | 5.8% | faster |
| url urldecode 32B 25%-escapes current #1 | 72.0 ns | 40.4 ns | 1.819 | 1.760-1.858 | 3.6% | faster |
| url urldecode 256B clean current #1 | 681 ns | 26.9 ns | 25.137 | 24.880-25.331 | 7.6% | faster |
| url urldecode 256B few-escapes current #1 | 642 ns | 45.5 ns | 14.691 | 14.090-14.827 | 6.7% | faster |
| url urldecode 256B 25%-escapes current #1 | 534 ns | 74.9 ns | 7.087 | 7.044-7.248 | 3.9% | faster |
| url urldecode 4096B clean current #1 | 10.6 us | 123 ns | 85.399 | 85.121-89.396 | 3.9% | faster |
| url urldecode 4096B few-escapes current #1 | 10.8 us | 594 ns | 17.599 | 17.383-18.220 | 4.2% | faster |
| url urldecode 4096B 25%-escapes current #1 | 8836 ns | 1133 ns | 7.771 | 7.671-7.965 | 3.8% | faster |
| url urldecode 65536B clean current #1 | 163.9 us | 1567 ns | 104.274 | 103.721-108.031 | 5.2% | faster |
| url urldecode 65536B few-escapes current #1 | 170.6 us | 10.2 us | 16.677 | 16.170-16.747 | 3.4% | faster |
| url urldecode 65536B 25%-escapes current #1 | 181.3 us | 17.7 us | 10.222 | 10.175-10.261 | 2.0% | faster |
| url QueryParser init+3next 64B current #1 | 373 ns | 93.5 ns | 4.046 | 3.993-4.092 | 5.5% | faster |
| url QueryParser init+3next 512B current #1 | 2820 ns | 428 ns | 6.618 | 6.445-6.723 | 2.7% | faster |
| url QueryParser init+3next 4096B current #1 | 22.9 us | 3030 ns | 7.500 | 7.493-7.616 | 2.3% | faster |
| url QueryParser clean 128B current #1 | 730 ns | 30.1 ns | 24.408 | 24.269-25.205 | 6.1% | faster |
| url QueryParser clean 1024B current #1 | 5357 ns | 66.9 ns | 79.594 | 79.340-88.199 | 14.1% | faster |
| url PathParser init+next 8B current #1 | 56.6 ns | 34.7 ns | 1.646 | 1.482-1.731 | 4.7% | faster |
| url PathParser init+next 16B current #1 | 106 ns | 40.7 ns | 2.631 | 2.604-2.680 | 7.1% | faster |
| url PathParser init+next 32B current #1 | 252 ns | 74.5 ns | 3.412 | 3.375-3.478 | 3.3% | faster |
| url PathParser init+next 64B current #1 | 452 ns | 59.0 ns | 7.505 | 7.403-7.775 | 3.3% | faster |
| url PathParser init+next 256B current #1 | 1648 ns | 149 ns | 11.103 | 10.772-11.181 | 3.7% | faster |

## Rows: i9

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| url urldecode 8B clean current #1 | 32.9 ns | 10.9 ns | 2.963 | 2.912-3.101 | 9.8% | faster |
| url urldecode 8B few-escapes current #1 | 32.0 ns | 10.4 ns | 3.077 | 2.963-3.218 | 27.8% | faster |
| url urldecode 8B 25%-escapes current #1 | 31.9 ns | 10.7 ns | 2.981 | 2.890-3.230 | 16.0% | faster |
| url urldecode 16B clean current #1 | 62.1 ns | 10.7 ns | 5.634 | 5.477-5.914 | 11.1% | faster |
| url urldecode 16B few-escapes current #1 | 57.8 ns | 16.7 ns | 3.429 | 3.353-3.503 | 11.1% | faster |
| url urldecode 16B 25%-escapes current #1 | 54.2 ns | 17.2 ns | 3.248 | 3.151-3.289 | 13.7% | faster |
| url urldecode 32B clean current #1 | 194 ns | 51.6 ns | 3.646 | 3.634-3.762 | 15.4% | faster |
| url urldecode 32B few-escapes current #1 | 168 ns | 68.3 ns | 2.451 | 2.448-2.706 | 15.0% | faster |
| url urldecode 32B 25%-escapes current #1 | 151 ns | 37.2 ns | 4.070 | 3.883-4.264 | 15.9% | faster |
| url urldecode 256B clean current #1 | 1408 ns | 113 ns | 12.458 | 11.697-13.142 | 30.0% | faster |
| url urldecode 256B few-escapes current #1 | 1362 ns | 98.2 ns | 13.818 | 13.667-14.365 | 8.9% | faster |
| url urldecode 256B 25%-escapes current #1 | 1228 ns | 167 ns | 7.102 | 5.921-7.570 | 6.6% | faster |
| url urldecode 4096B clean current #1 | 18.5 us | 148 ns | 127.333 | 124.719-135.671 | 27.0% | faster |
| url urldecode 4096B few-escapes current #1 | 20.5 us | 847 ns | 24.034 | 24.015-24.223 | 8.0% | faster |
| url urldecode 4096B 25%-escapes current #1 | 21.5 us | 1809 ns | 11.908 | 11.412-12.530 | 11.2% | faster |
| url urldecode 65536B clean current #1 | 363.1 us | 2367 ns | 161.561 | 148.248-176.964 | 14.1% | faster |
| url urldecode 65536B few-escapes current #1 | 374.9 us | 27.8 us | 13.221 | 13.172-16.272 | 18.0% | faster |
| url urldecode 65536B 25%-escapes current #1 | 394.4 us | 42.4 us | 8.970 | 8.917-9.483 | 10.1% | faster |
| url QueryParser init+3next 64B current #1 | 762 ns | 179 ns | 4.359 | 4.229-4.578 | 11.1% | faster |
| url QueryParser init+3next 512B current #1 | 5578 ns | 826 ns | 6.757 | 6.575-6.917 | 6.7% | faster |
| url QueryParser init+3next 4096B current #1 | 43.4 us | 6982 ns | 6.168 | 6.115-6.924 | 13.8% | faster |
| url QueryParser clean 128B current #1 | 1315 ns | 61.8 ns | 21.094 | 17.099-21.586 | 3.7% | faster |
| url QueryParser clean 1024B current #1 | 9977 ns | 137 ns | 70.192 | 68.411-72.877 | 7.0% | faster |
| url PathParser init+next 8B current #1 | 121 ns | 77.6 ns | 1.532 | 1.530-1.645 | 6.2% | faster |
| url PathParser init+next 16B current #1 | 200 ns | 89.2 ns | 2.244 | 1.914-2.322 | 3.4% | faster |
| url PathParser init+next 32B current #1 | 581 ns | 185 ns | 3.450 | 3.058-3.633 | 4.7% | faster |
| url PathParser init+next 64B current #1 | 909 ns | 162 ns | 5.696 | 5.510-5.998 | 1.3% | faster |
| url PathParser init+next 256B current #1 | 3322 ns | 406 ns | 8.243 | 8.037-8.428 | 1.1% | faster |
