# http-parser: START 52a30d0 to HEAD ef12ec6

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/http-parser#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`); HEAD is `origin/main` when this run started.

**Status: complete** (m4 3 of 3 rounds, i9 3 of 3 rounds). 

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64), macOS 26 (Darwin 25.6.0), Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja |
| i9 | Intel i9-9980HK (8C/16T, x86-64), macOS 15 (Darwin 24.6.0), Apple clang 17.0.0 (clang-1700.6.4.2), CMake, Ninja |

- Bench: HEAD's `bench/bench.cc` (the `new` column is the library under test; the `old` frozen copy and `llhttp` columns are not compared), default arguments. START `52a30d0` is the 2.7.1 fork with no bulk scans; HEAD `ef12ec6` has the scans, direct transitions and the request-framing hardening (strict by default). enum-reflection is pinned at HEAD's commit on both sides.
- Builds: Release (`-O3 -DNDEBUG`), same compiler and flags for both sides, library sources only differ (see Commands).
- Every round runs START, HEAD, then START again (the A/A control, a second copy of the START binary), interleaved in one hold; ratios are the median of the paired rounds, START time / HEAD time (above 1 is faster now). `A/A dev` is the largest |A/A - 1| over the rounds.

## Commands

```sh
git clone https://github.com/Kronuz/http-parser && cd http-parser
# START 52a30d0ea662fd911cb155456b3f46c3c8a2aa88   HEAD ef12ec6b75ef29f024698a1fced200ae4c87afdc
git worktree add --detach trees/http-parser-head ef12ec6b75ef29f024698a1fced200ae4c87afdc
git worktree add --detach trees/http-parser-start ef12ec6b75ef29f024698a1fced200ae4c87afdc
(cd trees/http-parser-start && git rm -rq -- http_parser.cc http_parser.h http_parser_enums.h likely.h && git checkout 52a30d0ea662fd911cb155456b3f46c3c8a2aa88 -- http_parser.cc http_parser.h http_parser_enums.h likely.h)   # HEAD's tree and bench, START's library files
cmake -S trees/http-parser-{head,start} -B trees/http-parser-{head,start}/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DHTTP_PARSER_BUILD_BENCH=ON
cmake --build trees/http-parser-{head,start}/build --target http_parser_bench    # bench: bench/bench.cc (HEAD's)
# each round, in one quiet strict hold (<= 10 min): START, HEAD, START again (copy of the START binary)
for side in start head startcopy; do bin/http-parser.http_parser_bench.$side > out/http-parser/<a|b|aa>-N.txt; done
python3 rig/gate.py REPO m4|i9      # paired ratios via cpp-libraries/tools/ab_compare.py (read_runs, compare)
```

## Summary

| machine | set | rounds | rows | geomean START/HEAD | A/A geomean | rows <0.97 outside A/A | worst | rows <0.97 inside A/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| m4 | all | 3 | 13 | 1.784 | 1.003 | 0 | - | 0 |
| i9 | all | 3 | 13 | 2.170 | 1.010 | 0 | - | 0 |

## Context: HEAD against the frozen original in the bench

The bench also times a frozen copy of the pre-campaign code (`test/urldecode_old.h`, `test/frozen`, `test/http_parser_old.cc`) in the same process as HEAD. This is not START (START is already past some of the work); it shows where HEAD stands against the original. Ratio is original time / HEAD time, median over the rounds.

| machine | rows | geomean original/HEAD | worst row | best row |
|---|---:|---:|---|---|
| m4 | 13 | 1.78 | response 200 (8 hdr) 1.24 | long URL (125B) 8.05 |
| i9 | 13 | 2.23 | 1 short header 1.66 | long URL (125B) 8.23 |

## Rows below 0.97 outside the A/A spread

None.

## Correctness changes that affect comparability

- HEAD rejects what request smuggling relies on and frames responses as RFC 9112 does unless `lenient_http_headers` is set; the bench's messages are well formed, so every row parses the same bytes to the same events. The strict build compiles the parse loop twice (`execute<lenient>`).

## Verdict

FASTER. All 13 rows are faster on both machines: geomean 1.8x on the M4 (1.2x to 8.1x) and 2.2x on the i9 (1.5x to 8.1x); no row below 0.97; HEAD adds request-framing hardening and the bench's well-formed messages pay nothing visible for it.

## Rows: m4

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| small GET (3 hdr) | 126 ns | 67.1 ns | 1.873 | 1.871-1.952 | 2.4% | faster |
| browser GET (14 hdr) | 430 ns | 272 ns | 1.580 | 1.574-1.655 | 3.6% | faster |
| 64 custom headers | 1537 ns | 1040 ns | 1.466 | 1.456-1.486 | 0.3% | faster |
| POST 1KB body | 152 ns | 103 ns | 1.470 | 1.460-1.531 | 2.9% | faster |
| POST 64KB body | 110 ns | 79.1 ns | 1.387 | 1.358-1.431 | 2.2% | faster |
| chunked 16x256B | 292 ns | 169 ns | 1.726 | 1.713-1.775 | 2.2% | faster |
| 32 pipelined small GET | 4100 ns | 1957 ns | 2.095 | 2.073-2.145 | 1.6% | faster |
| browser GET, 64B segments | 520 ns | 370 ns | 1.403 | 1.392-1.437 | 1.8% | faster |
| response 200 (8 hdr) | 208 ns | 168 ns | 1.240 | 1.222-1.275 | 1.0% | faster |
| request line only | 68.3 ns | 30.2 ns | 2.269 | 2.237-2.278 | 0.6% | faster |
| 1 short header | 54.1 ns | 41.7 ns | 1.307 | 1.291-1.307 | 1.1% | faster |
| 1 long header (117B) | 61.8 ns | 44.6 ns | 1.386 | 1.370-1.397 | 0.5% | faster |
| long URL (125B) | 426 ns | 52.5 ns | 8.114 | 7.842-8.209 | 5.7% | faster |

## Rows: i9

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| small GET (3 hdr) | 343 ns | 159 ns | 2.212 | 2.086-2.255 | 6.9% | faster |
| browser GET (14 hdr) | 1126 ns | 565 ns | 1.988 | 1.862-2.003 | 5.6% | faster |
| 64 custom headers | 4204 ns | 2027 ns | 2.098 | 1.943-2.158 | 2.1% | faster |
| POST 1KB body | 420 ns | 227 ns | 1.863 | 1.815-1.933 | 4.6% | faster |
| POST 64KB body | 301 ns | 185 ns | 1.622 | 1.591-1.754 | 5.3% | faster |
| chunked 16x256B | 911 ns | 415 ns | 2.198 | 2.137-2.207 | 5.6% | faster |
| 32 pipelined small GET | 10.4 us | 4308 ns | 2.385 | 2.261-2.408 | 7.0% | faster |
| browser GET, 64B segments | 1288 ns | 859 ns | 1.461 | 1.452-1.702 | 3.0% | faster |
| response 200 (8 hdr) | 572 ns | 331 ns | 1.735 | 1.727-1.803 | 8.5% | faster |
| request line only | 168 ns | 63.9 ns | 2.615 | 2.606-2.746 | 3.1% | faster |
| 1 short header | 166 ns | 95.7 ns | 1.711 | 1.708-1.732 | 1.5% | faster |
| 1 long header (117B) | 176 ns | 102 ns | 1.756 | 1.728-1.794 | 1.9% | faster |
| long URL (125B) | 887 ns | 109 ns | 8.125 | 8.109-8.556 | 6.9% | faster |
