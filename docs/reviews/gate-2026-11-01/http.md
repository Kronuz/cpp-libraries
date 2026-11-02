# http: START c23bb99 to HEAD 3caaeda

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/http#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`); HEAD is `origin/main` when this run started.

**Status: complete** (m4 3 of 3 rounds, i9 3 of 3 rounds). 

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64), macOS 26 (Darwin 25.6.0), Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja |
| i9 | Intel i9-9980HK (8C/16T, x86-64), macOS 15 (Darwin 24.6.0), Apple clang 17.0.0 (clang-1700.6.4.2), CMake, Ninja |

- START `c23bb99` (10-29, handler `handle()` is synchronous) and HEAD `3caaeda` (coroutine handlers, BodyStream, request cancellation, read-ahead watch, body cap) are built whole, each with its own pinned dependencies (reactor, http-parser, compressors), because START's `http_asio.h` does not compile against HEAD's pinned reactor. The comparison is therefore the stack as shipped at each commit, not the http headers alone: HEAD also carries the hardened http-parser and the newer reactor.
- HEAD's `bench/server_compare.cc` uses the coroutine handler API and cannot be built at START, so two benches replace it: (1) `rig/overlay/http/gate_micro.cc` (written for this gate, 4 request shapes through `http::RequestParser::feed` + `take`, the entry point every request passes through, compiles against both); (2) each side's own `examples/bench_http.cc` (a fixed 'Hello, World!' response through `HttpAsioService`) driven by `wrk` over loopback on 2 reactors, keep-alive, 8 and 64 connections, 4 s each (`rig/e2e_http.sh`).
- Builds: Release (`-O3 -DNDEBUG`), same compiler and flags for both sides, library sources only differ (see Commands).
- Every round runs START, HEAD, then START again (the A/A control, a second copy of the START binary), interleaved in one hold; ratios are the median of the paired rounds, START time / HEAD time (above 1 is faster now). `A/A dev` is the largest |A/A - 1| over the rounds.

## Commands

```sh
git clone https://github.com/Kronuz/http && cd http
# START c23bb991db31dae9dc7eac6e8099d9322366e4dc   HEAD 3caaedaac0e366ad045fc3b9efc751346f17dbb8
git worktree add --detach trees/http-head 3caaedaac0e366ad045fc3b9efc751346f17dbb8
git worktree add --detach trees/http-start c23bb991db31dae9dc7eac6e8099d9322366e4dc      # whole START tree, START's pinned dependencies
cmake -S trees/http-{head,start} -B trees/http-{head,start}/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ (START's and HEAD's own CMakeLists)
cmake --build trees/http-{head,start}/build --target http_micro bench_http    # bench: rig/overlay/http/gate_micro.cc (written for this gate) and each side's own examples/bench_http.cc under wrk
# each round, in one quiet strict hold (<= 10 min): START, HEAD, START again (copy of the START binary)
for side in start head startcopy; do bin/http.http_micro.$side > out/http/<a|b|aa>-N.txt; done
python3 rig/gate.py REPO m4|i9      # paired ratios via cpp-libraries/tools/ab_compare.py (read_runs, compare)
```

## Summary

| machine | set | rounds | rows | geomean START/HEAD | A/A geomean | rows <0.97 outside A/A | worst | rows <0.97 inside A/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| m4 | micro: RequestParser | 3 | 4 | 1.253 | 0.998 | 0 | - | 0 |
| m4 | e2e: bench_http under wrk (req/s) | 3 | 2 | 1.002 | 1.000 | 0 | - | 0 |
| i9 | micro: RequestParser | 3 | 4 | 1.327 | 0.993 | 0 | - | 0 |
| i9 | e2e: bench_http under wrk (req/s) | 3 | 2 | 0.846 | 0.981 | 2 | 0.836 | 0 |

## Rows below 0.97 outside the A/A spread

**i9 / e2e: bench_http under wrk (req/s)**

| row | START | HEAD | START/HEAD | A/A dev | cause |
|---|---:|---:|---:|---:|---|
| http   e2e keepalive c=64 R=2 rps | 99.9 us | 82.9 us | 0.836 | 4.7% | unexplained |
| http   e2e keepalive c=8 R=2 rps | 87.7 us | 75.1 us | 0.856 | 3.3% | unexplained |

## Correctness changes that affect comparability

- HEAD adds a body-size cap check, trailer handling and CONNECT handling to `RequestParser` and a 4096-byte read-ahead watch to the connection; each is work START did not do.

## Verdict

FASTER on the request parser (micro geomean 1.25x on the M4 and 1.33x on the i9: the HEAD stack carries the hardened http-parser with the bulk scans). End to end (`bench_http` under `wrk`, 3 rounds) it is SAME on the M4 (1.00x at 8 and 64 connections: the loopback and `wrk` set the rate, not the framework) and SLOWER on the i9: HEAD serves 14-16% fewer requests per second (8 connections 87.7k to 75.1k, ratio 0.856; 64 connections 99.9k to 82.9k, ratio 0.836; A/A dev 3.3% and 4.7%, and every round agrees). The cause is not found here: the two sides differ in the whole stack (coroutine handlers, request cancellation, read-ahead watch, body cap, the newer reactor and the hardened http-parser), and START is built with its own pins, so this is the stack as shipped. The START and HEAD columns of the two e2e rows are requests per second, which the table prints with a time unit.

## Rows: m4 / micro: RequestParser

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| http GET minimal current #1 | 120 ns | 92.8 ns | 1.304 | 1.287-1.325 | 3.8% | faster |
| http GET browser 9 headers current #1 | 715 ns | 555 ns | 1.280 | 1.249-1.316 | 1.4% | faster |
| http POST 100B body current #1 | 286 ns | 255 ns | 1.122 | 1.105-1.139 | 2.8% | faster |
| http POST chunked 3 chunks current #1 | 249 ns | 189 ns | 1.316 | 1.293-1.323 | 0.4% | faster |

## Rows: m4 / e2e: bench_http under wrk (req/s)

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| http   e2e keepalive c=8 R=2 rps | 39,727 | 39,802 | 1.002 | 0.988-1.014 | 2.7% | noise |
| http   e2e keepalive c=64 R=2 rps | 40,425 | 40,667 | 1.003 | 1.003-1.006 | 0.8% | noise |

## Rows: i9 / micro: RequestParser

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| http GET minimal current #1 | 310 ns | 239 ns | 1.311 | 1.279-1.315 | 3.9% | faster |
| http GET browser 9 headers current #1 | 1833 ns | 1400 ns | 1.316 | 1.307-1.341 | 1.4% | faster |
| http POST 100B body current #1 | 775 ns | 623 ns | 1.252 | 1.244-1.260 | 2.3% | faster |
| http POST chunked 3 chunks current #1 | 650 ns | 453 ns | 1.434 | 1.427-1.436 | 1.3% | faster |

## Rows: i9 / e2e: bench_http under wrk (req/s)

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| http   e2e keepalive c=8 R=2 rps | 87,678 | 75,072 | 0.856 | 0.844-0.870 | 3.3% | slower |
| http   e2e keepalive c=64 R=2 rps | 99,949 | 82,908 | 0.836 | 0.765-0.837 | 4.7% | slower |

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- i9 end to end, keep-alive, 64 connections 0.836 and 8 connections 0.856: fixed in `http:c37474a`
  (on plain TCP the disconnect watch starts when the handler first asks about cancellation, and a
  buffered reply leaves in one write; `ea388ef` records the M4 Pro numbers). The i9 serves 93.7k and
  98.7k req/s at 8 and 64 connections against start's 87.3k and 98.0k; on the M4 Pro `wrk` sets the
  rate (about 37,000 req/s) and the CPU per request is 21.7 µs against start's 22.5. One-connection
  latency against Boost.Beast is [http#1](https://github.com/Kronuz/http/issues/1).
