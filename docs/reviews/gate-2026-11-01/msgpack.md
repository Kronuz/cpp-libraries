# msgpack: START 3c408cf to HEAD 4bb04dd

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/msgpack#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`); HEAD is `origin/main` when this run started.

**Status: complete** (m4 3 of 3 rounds, i9 3 of 3 rounds). 

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64), macOS 26 (Darwin 25.6.0), Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja |
| i9 | Intel i9-9980HK (8C/16T, x86-64), macOS 15 (Darwin 24.6.0), Apple clang 17.0.0 (clang-1700.6.4.2), CMake, Ninja |

- Bench: HEAD's `benchmarks/pack_unpack.cc` (`msgpack_benchmark`) on the four documents of `benchmarks/corpus.h`; rows are `msgpack` (the library) and `msgpack-c1.3` (the bundled msgpack-c, unchanged code, used here as an anchor for code placement). START `3c408cf`; HEAD `4bb04dd`. The comparison library build (`msgpack_compare`) is not built.
- Rows carry a checksum of the document: a row whose START and HEAD checksums differ would be VOID.
- Builds: Release (`-O3 -DNDEBUG`), same compiler and flags for both sides, library sources only differ (see Commands).
- Every round runs START, HEAD, then START again (the A/A control, a second copy of the START binary), interleaved in one hold; ratios are the median of the paired rounds, START time / HEAD time (above 1 is faster now). `A/A dev` is the largest |A/A - 1| over the rounds.

## Commands

```sh
git clone https://github.com/Kronuz/msgpack && cd msgpack
# START 3c408cf939342d3a8fc589d21625175d90b2adb0   HEAD 4bb04dd02e16031aad58c986d87d7f9033b81a18
git worktree add --detach trees/msgpack-head 4bb04dd02e16031aad58c986d87d7f9033b81a18
git worktree add --detach trees/msgpack-start 4bb04dd02e16031aad58c986d87d7f9033b81a18
(cd trees/msgpack-start && git rm -rq -- msgpack.h msgpack.hpp msgpack_patcher.* msgpack_exception.h likely.h msgpack/ xchange/ && git checkout 3c408cf939342d3a8fc589d21625175d90b2adb0 -- msgpack.h msgpack.hpp msgpack_patcher.* msgpack_exception.h likely.h msgpack/ xchange/)   # HEAD's tree and bench, START's library files
cmake -S trees/msgpack-{head,start} -B trees/msgpack-{head,start}/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DMSGPACK_BUILD_BENCH=ON
cmake --build trees/msgpack-{head,start}/build --target msgpack_benchmark    # bench: benchmarks/pack_unpack.cc (HEAD's)
# each round, in one quiet strict hold (<= 10 min): START, HEAD, START again (copy of the START binary)
for side in start head startcopy; do bin/msgpack.msgpack_benchmark.$side > out/msgpack/<a|b|aa>-N.txt; done
python3 rig/gate.py REPO m4|i9      # paired ratios via cpp-libraries/tools/ab_compare.py (read_runs, compare)
```

## Summary

| machine | set | rounds | rows | geomean START/HEAD | A/A geomean | rows <0.97 outside A/A | worst | rows <0.97 inside A/A |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| m4 | all | 3 | 57 | 1.214 | 0.998 | 1 | 0.953 | 2 |
|  |  | anchors | 32 | 0.976 | | | | |
| i9 | all | 3 | 57 | 1.273 | 0.995 | 1 | 0.938 | 0 |
|  |  | anchors | 32 | 1.013 | | | | |

## Rows below 0.97 outside the A/A spread

**m4**

| row | START | HEAD | START/HEAD | A/A dev | cause |
|---|---:|---:|---:|---:|---|
| msgpack med write | 480 ns | 501 ns | 0.953 | 3.9% | code placement, not the library: the bundled msgpack-c rows (unchanged code) move by the same amount in the same runs (the same operation on msgpack-c reads 0.950, or the anchors' geomean where there is none); CHANGELOG 2026-11-01: the `write` rows read 2.4-3.8% slower with no change to their path and 0.98-1.00 with every function aligned to 64 bytes |

**i9**

| row | START | HEAD | START/HEAD | A/A dev | cause |
|---|---:|---:|---:|---:|---|
| msgpack small copy(filled) | 306 ns | 326 ns | 0.938 | 3.9% | unexplained beyond placement: HEAD adds the repeated-key merge and the failed-fill check to the fill path (CHANGELOG 2026-11-01 measured them at <= 6%); the row is below the anchors |

## Rows below 0.97 but inside the A/A spread (noise, not flagged)

- m4: msgpack small write: 0.948 (A/A dev 6.5%, range 0.925-1.002)
- m4: msgpack med lookup3[]: 0.966 (A/A dev 3.7%, range 0.965-1.026)

## Correctness changes that affect comparability

- HEAD merges repeated map keys (last value wins), moves array elements when an array grows, checks every key before a fill changes anything (failed-fill check), and writes NaN/Inf as null in `to_string()`: operations with more work per call by design. A copy is a deep copy at both commits.

## Verdict

FASTER overall (3 rounds on each machine; geomean 1.21x on the M4 and 1.27x on the i9 over the 57 library rows; `hash` 1.2-7.8x on the M4 and 1.2-14.1x on the i9, `json-write` 1.2-2.3x and 1.4-1.7x, `read` 1.4-1.5x and 1.5-1.9x). One library row is below 0.97 outside the A/A spread on each machine. M4: `med write` at 0.953, which sits with the unchanged msgpack-c anchor rows of the same runs (their geomean is 0.976; the same operation on msgpack-c reads 0.950), so it is code placement; two more M4 rows, `small write` 0.948 and `med lookup3[]` 0.966, are below 0.97 inside their A/A spread and the `write` rows follow their anchors. i9: `small copy(filled)` at 0.938 (6.6% slower) where the anchors' geomean is 1.013; HEAD adds the repeated-key merge and the failed-fill check to the fill path, which the CHANGELOG measured at up to 6%, so the row is a little past that and not explained further here.

## Rows: m4

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| msgpack small read | 303 ns | 200 ns | 1.491 | 1.462-1.585 | 4.1% | faster |
| msgpack small read+walk | 1035 ns | 910 ns | 1.110 | 1.103-1.150 | 11.3% | noise |
| msgpack small walk(filled) | 174 ns | 174 ns | 0.998 | 0.991-1.000 | 2.7% | noise |
| msgpack small read+lookup3 | 884 ns | 804 ns | 1.098 | 1.029-1.103 | 4.1% | faster |
| msgpack small lookup3 | 44.1 ns | 44.7 ns | 0.995 | 0.978-1.004 | 3.5% | noise |
| msgpack small lookup3[] | 81.6 ns | 80.7 ns | 0.973 | 0.968-1.045 | 2.3% | slower |
| msgpack small write | 120 ns | 123 ns | 0.948 | 0.925-1.002 | 6.5% | noise |
| msgpack small copy | 122 ns | 121 ns | 0.982 | 0.964-1.003 | 3.1% | noise |
| msgpack small copy(filled) | 121 ns | 123 ns | 0.985 | 0.935-0.988 | 1.6% | noise |
| msgpack small update | 835 ns | 746 ns | 1.110 | 1.036-1.144 | 4.0% | faster |
| msgpack small merge | 995 ns | 997 ns | 0.998 | 0.945-1.023 | 1.9% | noise |
| msgpack small json-write | 544 ns | 235 ns | 2.331 | 2.317-2.439 | 1.6% | faster |
| msgpack small json-read | 503 ns | 501 ns | 1.005 | 0.943-1.020 | 4.5% | noise |
| msgpack small hash | 450 ns | 57.5 ns | 7.753 | 7.578-7.840 | 1.3% | faster |
| msgpack med read | 1028 ns | 708 ns | 1.445 | 1.406-1.458 | 1.9% | faster |
| msgpack med read+walk | 5085 ns | 4776 ns | 1.065 | 1.041-1.087 | 2.1% | faster |
| msgpack med walk(filled) | 1118 ns | 1090 ns | 1.026 | 0.988-1.034 | 4.0% | noise |
| msgpack med read+lookup3 | 2776 ns | 2439 ns | 1.138 | 1.075-1.141 | 5.6% | faster |
| msgpack med lookup3 | 64.5 ns | 65.2 ns | 0.982 | 0.980-1.013 | 3.0% | noise |
| msgpack med lookup3[] | 120 ns | 122 ns | 0.966 | 0.965-1.026 | 3.7% | noise |
| msgpack med write | 480 ns | 501 ns | 0.953 | 0.913-0.963 | 3.9% | slower |
| msgpack med copy | 374 ns | 371 ns | 0.987 | 0.950-1.025 | 2.0% | noise |
| msgpack med copy(filled) | 371 ns | 367 ns | 0.991 | 0.932-1.012 | 1.3% | noise |
| msgpack med update | 2582 ns | 2275 ns | 1.135 | 1.088-1.149 | 1.7% | faster |
| msgpack med merge | 2939 ns | 2642 ns | 1.112 | 1.055-1.120 | 1.5% | faster |
| msgpack med json-write | 2056 ns | 1310 ns | 1.579 | 1.472-1.619 | 3.0% | faster |
| msgpack med json-read | 2313 ns | 2303 ns | 1.003 | 0.994-1.018 | 1.8% | noise |
| msgpack med hash | 1522 ns | 379 ns | 3.972 | 3.950-4.050 | 2.5% | faster |
| msgpack med build | 12.1 us | 9432 ns | 1.282 | 1.225-1.302 | 3.8% | faster |
| msgpack large read | 195.4 us | 130.5 us | 1.481 | 1.465-1.502 | 1.4% | faster |
| msgpack large read+walk | 1.08 ms | 1.01 ms | 1.051 | 1.051-1.070 | 1.4% | faster |
| msgpack large walk(filled) | 253.8 us | 243.2 us | 1.032 | 1.021-1.057 | 4.6% | noise |
| msgpack large read+lookup3 | 203.8 us | 141.2 us | 1.444 | 1.439-1.447 | 0.9% | faster |
| msgpack large lookup3 | 60.1 ns | 61.4 ns | 0.984 | 0.976-0.989 | 2.1% | noise |
| msgpack large lookup3[] | 112 ns | 111 ns | 1.014 | 0.996-1.045 | 1.1% | faster |
| msgpack large write | 93.2 us | 95.1 us | 0.975 | 0.974-0.985 | 5.7% | noise |
| msgpack large copy | 66.3 us | 66.9 us | 0.991 | 0.970-1.001 | 1.8% | noise |
| msgpack large copy(filled) | 66.5 us | 66.3 us | 0.994 | 0.970-1.003 | 1.4% | noise |
| msgpack large update | 296.2 us | 236.1 us | 1.250 | 1.228-1.264 | 1.1% | faster |
| msgpack large merge | 299.6 us | 236.6 us | 1.259 | 1.258-1.266 | 1.6% | faster |
| msgpack large json-write | 343.7 us | 206.1 us | 1.737 | 1.581-1.822 | 9.8% | faster |
| msgpack large json-read | 376.5 us | 382.5 us | 0.983 | 0.983-0.987 | 0.6% | slower |
| msgpack large hash | 97.4 us | 82.9 us | 1.171 | 1.140-1.175 | 0.4% | faster |
| msgpack wide read | 16.4 us | 10.9 us | 1.508 | 1.384-1.549 | 1.0% | faster |
| msgpack wide read+walk | 128.9 us | 123.6 us | 1.046 | 1.043-1.052 | 4.1% | faster |
| msgpack wide walk(filled) | 33.2 us | 32.2 us | 1.029 | 0.990-1.036 | 4.7% | noise |
| msgpack wide read+lookup3 | 95.8 us | 90.2 us | 1.062 | 1.051-1.063 | 1.5% | faster |
| msgpack wide lookup3 | 32.5 ns | 32.8 ns | 0.991 | 0.991-1.000 | 1.8% | noise |
| msgpack wide lookup3[] | 56.6 ns | 54.2 ns | 1.018 | 1.004-1.060 | 4.2% | noise |
| msgpack wide write | 12.3 us | 10.5 us | 1.050 | 0.991-1.200 | 21.9% | noise |
| msgpack wide copy | 5407 ns | 5499 ns | 0.977 | 0.969-0.983 | 1.7% | slower |
| msgpack wide copy(filled) | 5403 ns | 5461 ns | 0.988 | 0.987-0.992 | 1.1% | slower |
| msgpack wide update | 106.1 us | 102.1 us | 1.039 | 1.035-1.039 | 1.9% | faster |
| msgpack wide merge | 122.7 us | 117.8 us | 1.055 | 1.036-1.064 | 4.2% | faster |
| msgpack wide json-write | 28.6 us | 23.4 us | 1.191 | 1.174-1.263 | 20.6% | noise |
| msgpack wide json-read | 28.2 us | 28.0 us | 1.010 | 1.006-1.037 | 1.9% | noise |
| msgpack wide hash | 45.3 us | 6190 ns | 7.325 | 7.031-7.484 | 6.0% | faster |

Anchor rows (msgpack-c 1.3 bundled in the bench, same code on both sides), m4:

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| anchor:msgpack-c1.3 small read | 160 ns | 165 ns | 0.969 | 0.947-0.975 | 3.6% | noise |
| anchor:msgpack-c1.3 small read+walk | 192 ns | 198 ns | 0.957 | 0.936-0.985 | 2.7% | slower |
| anchor:msgpack-c1.3 small walk(raw) | 33.0 ns | 33.2 ns | 0.988 | 0.959-1.003 | 0.6% | slower |
| anchor:msgpack-c1.3 small read+lookup3 | 191 ns | 194 ns | 0.976 | 0.925-0.983 | 2.4% | slower |
| anchor:msgpack-c1.3 small lookup3(linear) | 30.2 ns | 30.6 ns | 0.987 | 0.950-0.990 | 4.4% | noise |
| anchor:msgpack-c1.3 small write | 104 ns | 106 ns | 0.979 | 0.945-1.018 | 6.0% | noise |
| anchor:msgpack-c1.3 small write(reused) | 83.5 ns | 86.0 ns | 0.971 | 0.960-0.992 | 2.3% | slower |
| anchor:msgpack-c1.3 small copy | 77.3 ns | 75.9 ns | 1.008 | 0.946-1.022 | 5.7% | noise |
| anchor:msgpack-c1.3 med read | 655 ns | 678 ns | 0.960 | 0.935-0.986 | 3.9% | slower |
| anchor:msgpack-c1.3 med read+walk | 1014 ns | 1027 ns | 0.986 | 0.940-0.995 | 2.7% | noise |
| anchor:msgpack-c1.3 med walk(raw) | 354 ns | 352 ns | 1.004 | 0.967-1.011 | 1.7% | noise |
| anchor:msgpack-c1.3 med read+lookup3 | 730 ns | 744 ns | 0.986 | 0.930-0.988 | 3.8% | noise |
| anchor:msgpack-c1.3 med lookup3(linear) | 49.0 ns | 54.1 ns | 0.888 | 0.879-1.004 | 10.6% | slower |
| anchor:msgpack-c1.3 med write | 462 ns | 477 ns | 0.950 | 0.947-0.989 | 2.6% | slower |
| anchor:msgpack-c1.3 med write(reused) | 433 ns | 460 ns | 0.940 | 0.931-0.952 | 3.6% | slower |
| anchor:msgpack-c1.3 med copy | 325 ns | 322 ns | 1.010 | 0.948-1.011 | 1.0% | noise |
| anchor:msgpack-c1.3 large read | 128.0 us | 131.4 us | 0.973 | 0.958-0.995 | 1.6% | slower |
| anchor:msgpack-c1.3 large read+walk | 199.1 us | 203.6 us | 0.981 | 0.972-0.983 | 2.9% | noise |
| anchor:msgpack-c1.3 large walk(raw) | 71.9 us | 72.3 us | 0.994 | 0.990-1.001 | 0.8% | noise |
| anchor:msgpack-c1.3 large read+lookup3 | 127.6 us | 132.2 us | 0.962 | 0.955-0.974 | 2.5% | slower |
| anchor:msgpack-c1.3 large lookup3(linear) | 42.9 ns | 46.1 ns | 0.920 | 0.913-0.950 | 1.7% | slower |
| anchor:msgpack-c1.3 large write | 90.8 us | 93.7 us | 0.963 | 0.962-0.969 | 3.8% | slower |
| anchor:msgpack-c1.3 large write(reused) | 90.3 us | 91.9 us | 0.977 | 0.941-0.983 | 2.1% | slower |
| anchor:msgpack-c1.3 large copy | 66.5 us | 66.5 us | 0.990 | 0.959-1.009 | 0.7% | slower |
| anchor:msgpack-c1.3 wide read | 10.7 us | 10.9 us | 0.991 | 0.944-1.014 | 3.0% | noise |
| anchor:msgpack-c1.3 wide read+walk | 16.1 us | 15.8 us | 0.994 | 0.987-1.015 | 3.4% | noise |
| anchor:msgpack-c1.3 wide walk(raw) | 4969 ns | 4944 ns | 1.007 | 1.003-1.026 | 6.6% | noise |
| anchor:msgpack-c1.3 wide read+lookup3 | 14.0 us | 14.1 us | 0.989 | 0.982-0.998 | 4.1% | noise |
| anchor:msgpack-c1.3 wide lookup3(linear) | 3155 ns | 3137 ns | 1.006 | 0.989-1.010 | 3.2% | noise |
| anchor:msgpack-c1.3 wide write | 11.1 us | 11.3 us | 0.989 | 0.900-1.133 | 31.3% | noise |
| anchor:msgpack-c1.3 wide write(reused) | 10.1 us | 10.8 us | 0.934 | 0.705-1.069 | 11.7% | noise |
| anchor:msgpack-c1.3 wide copy | 5294 ns | 5264 ns | 1.002 | 0.987-1.013 | 1.1% | noise |

## Rows: i9

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| msgpack small read | 742 ns | 482 ns | 1.540 | 1.463-1.576 | 7.2% | faster |
| msgpack small read+walk | 3540 ns | 3202 ns | 1.113 | 1.025-1.127 | 4.0% | faster |
| msgpack small walk(filled) | 541 ns | 539 ns | 1.004 | 0.950-1.037 | 3.3% | noise |
| msgpack small read+lookup3 | 3118 ns | 2906 ns | 1.073 | 1.058-1.082 | 4.8% | faster |
| msgpack small lookup3 | 150 ns | 146 ns | 1.010 | 0.999-1.035 | 2.0% | noise |
| msgpack small lookup3[] | 252 ns | 237 ns | 1.059 | 1.046-1.072 | 2.8% | faster |
| msgpack small write | 208 ns | 204 ns | 1.020 | 1.016-1.069 | 9.1% | noise |
| msgpack small copy | 312 ns | 314 ns | 1.020 | 0.981-1.031 | 0.8% | faster |
| msgpack small copy(filled) | 306 ns | 326 ns | 0.938 | 0.876-0.964 | 3.9% | slower |
| msgpack small update | 2728 ns | 2436 ns | 1.094 | 1.084-1.138 | 7.7% | faster |
| msgpack small merge | 3484 ns | 3523 ns | 0.989 | 0.925-1.011 | 4.7% | noise |
| msgpack small json-write | 778 ns | 478 ns | 1.604 | 1.536-1.665 | 2.6% | faster |
| msgpack small json-read | 1230 ns | 1264 ns | 0.974 | 0.968-1.008 | 0.5% | slower |
| msgpack small hash | 1650 ns | 117 ns | 14.142 | 14.052-14.302 | 6.3% | faster |
| msgpack med read | 2024 ns | 1359 ns | 1.525 | 1.483-1.549 | 4.3% | faster |
| msgpack med read+walk | 21.8 us | 20.3 us | 1.059 | 1.059-1.100 | 1.2% | faster |
| msgpack med walk(filled) | 2983 ns | 2968 ns | 0.997 | 0.996-1.022 | 6.3% | noise |
| msgpack med read+lookup3 | 9636 ns | 8496 ns | 1.130 | 1.116-1.134 | 4.4% | faster |
| msgpack med lookup3 | 188 ns | 182 ns | 1.044 | 1.021-1.051 | 0.8% | faster |
| msgpack med lookup3[] | 346 ns | 331 ns | 1.040 | 1.015-1.063 | 1.7% | faster |
| msgpack med write | 836 ns | 793 ns | 1.043 | 1.029-1.056 | 2.4% | faster |
| msgpack med copy | 723 ns | 739 ns | 0.974 | 0.971-1.007 | 3.8% | noise |
| msgpack med copy(filled) | 748 ns | 740 ns | 1.010 | 0.937-1.034 | 6.9% | noise |
| msgpack med update | 7592 ns | 6774 ns | 1.112 | 1.102-1.126 | 2.1% | faster |
| msgpack med merge | 8622 ns | 8098 ns | 1.065 | 1.045-1.115 | 4.6% | faster |
| msgpack med json-write | 3165 ns | 2035 ns | 1.562 | 1.451-1.595 | 3.8% | faster |
| msgpack med json-read | 4245 ns | 4283 ns | 0.988 | 0.982-1.010 | 1.1% | slower |
| msgpack med hash | 4764 ns | 696 ns | 6.844 | 6.652-7.043 | 2.3% | faster |
| msgpack med build | 42.6 us | 32.5 us | 1.292 | 1.278-1.426 | 6.8% | faster |
| msgpack large read | 343.3 us | 214.5 us | 1.617 | 1.534-1.618 | 2.9% | faster |
| msgpack large read+walk | 5.05 ms | 4.29 ms | 1.164 | 1.079-1.230 | 15.7% | faster |
| msgpack large walk(filled) | 670.8 us | 673.2 us | 0.997 | 0.946-1.023 | 2.0% | noise |
| msgpack large read+lookup3 | 404.9 us | 263.9 us | 1.534 | 1.514-1.537 | 3.9% | faster |
| msgpack large lookup3 | 155 ns | 157 ns | 0.994 | 0.983-1.015 | 1.5% | noise |
| msgpack large lookup3[] | 297 ns | 284 ns | 1.045 | 1.021-1.047 | 2.4% | faster |
| msgpack large write | 145.7 us | 135.3 us | 1.076 | 1.065-1.088 | 2.2% | faster |
| msgpack large copy | 130.5 us | 128.3 us | 1.015 | 0.998-1.041 | 2.0% | noise |
| msgpack large copy(filled) | 129.7 us | 128.0 us | 1.010 | 1.004-1.044 | 4.1% | noise |
| msgpack large update | 523.8 us | 389.7 us | 1.363 | 1.232-1.375 | 3.4% | faster |
| msgpack large merge | 522.8 us | 392.0 us | 1.338 | 1.315-1.341 | 6.4% | faster |
| msgpack large json-write | 519.0 us | 302.5 us | 1.722 | 1.665-1.733 | 33.5% | faster |
| msgpack large json-read | 735.1 us | 718.8 us | 1.024 | 1.003-1.031 | 26.4% | noise |
| msgpack large hash | 157.6 us | 133.5 us | 1.180 | 1.115-1.305 | 27.0% | noise |
| msgpack wide read | 42.6 us | 21.7 us | 1.947 | 1.911-1.961 | 26.6% | faster |
| msgpack wide read+walk | 533.0 us | 513.0 us | 1.065 | 1.018-1.073 | 17.8% | noise |
| msgpack wide walk(filled) | 83.0 us | 83.8 us | 0.992 | 0.989-1.013 | 12.9% | noise |
| msgpack wide read+lookup3 | 459.3 us | 427.5 us | 1.079 | 1.002-1.088 | 5.1% | faster |
| msgpack wide lookup3 | 96.9 ns | 93.4 ns | 1.036 | 1.017-1.067 | 3.6% | noise |
| msgpack wide lookup3[] | 169 ns | 166 ns | 1.015 | 1.013-1.022 | 3.3% | noise |
| msgpack wide write | 15.4 us | 14.2 us | 1.087 | 1.074-1.090 | 3.7% | faster |
| msgpack wide copy | 12.8 us | 12.9 us | 0.973 | 0.968-1.004 | 6.4% | noise |
| msgpack wide copy(filled) | 12.9 us | 13.1 us | 0.991 | 0.986-1.039 | 6.2% | noise |
| msgpack wide update | 466.9 us | 439.3 us | 1.062 | 1.057-1.092 | 4.1% | faster |
| msgpack wide merge | 520.7 us | 489.8 us | 1.065 | 1.049-1.125 | 4.1% | faster |
| msgpack wide json-write | 38.3 us | 26.8 us | 1.445 | 1.394-1.470 | 4.3% | faster |
| msgpack wide json-read | 87.4 us | 75.0 us | 1.132 | 1.118-1.202 | 21.7% | noise |
| msgpack wide hash | 165.5 us | 15.1 us | 10.871 | 10.798-11.120 | 3.6% | faster |

Anchor rows (msgpack-c 1.3 bundled in the bench, same code on both sides), i9:

| row | START | HEAD | START/HEAD | range | A/A dev | verdict |
|---|---:|---:|---:|---:|---:|---|
| anchor:msgpack-c1.3 small read | 353 ns | 362 ns | 0.986 | 0.915-0.993 | 6.0% | noise |
| anchor:msgpack-c1.3 small read+walk | 425 ns | 442 ns | 0.966 | 0.959-0.984 | 6.0% | noise |
| anchor:msgpack-c1.3 small walk(raw) | 60.7 ns | 61.4 ns | 0.981 | 0.943-1.012 | 3.0% | noise |
| anchor:msgpack-c1.3 small read+lookup3 | 423 ns | 430 ns | 0.984 | 0.972-1.040 | 3.0% | noise |
| anchor:msgpack-c1.3 small lookup3(linear) | 52.3 ns | 53.5 ns | 0.974 | 0.972-0.991 | 2.8% | noise |
| anchor:msgpack-c1.3 small write | 161 ns | 157 ns | 1.021 | 1.009-1.026 | 0.5% | faster |
| anchor:msgpack-c1.3 small write(reused) | 119 ns | 108 ns | 1.111 | 1.088-1.123 | 3.7% | faster |
| anchor:msgpack-c1.3 small copy | 152 ns | 152 ns | 1.007 | 0.979-1.028 | 5.2% | noise |
| anchor:msgpack-c1.3 med read | 1178 ns | 1188 ns | 0.992 | 0.927-1.034 | 4.9% | noise |
| anchor:msgpack-c1.3 med read+walk | 1747 ns | 1739 ns | 0.999 | 0.982-1.041 | 3.5% | noise |
| anchor:msgpack-c1.3 med walk(raw) | 482 ns | 476 ns | 1.011 | 1.009-1.016 | 2.7% | noise |
| anchor:msgpack-c1.3 med read+lookup3 | 1341 ns | 1386 ns | 0.950 | 0.946-1.000 | 3.2% | slower |
| anchor:msgpack-c1.3 med lookup3(linear) | 86.0 ns | 85.5 ns | 1.006 | 1.004-1.012 | 2.8% | noise |
| anchor:msgpack-c1.3 med write | 702 ns | 665 ns | 1.065 | 1.031-1.068 | 2.5% | faster |
| anchor:msgpack-c1.3 med write(reused) | 658 ns | 620 ns | 1.062 | 0.997-1.078 | 7.1% | noise |
| anchor:msgpack-c1.3 med copy | 598 ns | 580 ns | 0.992 | 0.984-1.067 | 6.4% | noise |
| anchor:msgpack-c1.3 large read | 224.3 us | 213.9 us | 1.048 | 0.999-1.070 | 5.4% | noise |
| anchor:msgpack-c1.3 large read+walk | 318.2 us | 312.2 us | 1.024 | 1.014-1.034 | 4.2% | noise |
| anchor:msgpack-c1.3 large walk(raw) | 99.4 us | 103.4 us | 0.962 | 0.947-0.997 | 2.9% | slower |
| anchor:msgpack-c1.3 large read+lookup3 | 209.6 us | 219.9 us | 0.955 | 0.916-0.989 | 5.4% | noise |
| anchor:msgpack-c1.3 large lookup3(linear) | 70.5 ns | 69.3 ns | 1.017 | 1.017-1.030 | 2.4% | noise |
| anchor:msgpack-c1.3 large write | 141.6 us | 131.8 us | 1.074 | 1.073-1.079 | 1.9% | faster |
| anchor:msgpack-c1.3 large write(reused) | 138.7 us | 131.8 us | 1.072 | 1.012-1.088 | 2.5% | faster |
| anchor:msgpack-c1.3 large copy | 131.0 us | 127.0 us | 1.033 | 1.010-1.054 | 4.3% | noise |
| anchor:msgpack-c1.3 wide read | 21.4 us | 21.0 us | 1.024 | 0.952-1.099 | 27.4% | noise |
| anchor:msgpack-c1.3 wide read+walk | 28.6 us | 29.3 us | 0.985 | 0.970-0.990 | 16.2% | noise |
| anchor:msgpack-c1.3 wide walk(raw) | 7511 ns | 7552 ns | 0.995 | 0.976-1.004 | 3.6% | noise |
| anchor:msgpack-c1.3 wide read+lookup3 | 28.8 us | 29.4 us | 0.982 | 0.967-1.004 | 1.2% | slower |
| anchor:msgpack-c1.3 wide lookup3(linear) | 7446 ns | 7489 ns | 0.997 | 0.994-1.009 | 5.6% | noise |
| anchor:msgpack-c1.3 wide write | 15.2 us | 13.8 us | 1.093 | 1.091-1.110 | 1.4% | faster |
| anchor:msgpack-c1.3 wide write(reused) | 15.0 us | 13.6 us | 1.106 | 1.094-1.113 | 3.4% | faster |
| anchor:msgpack-c1.3 wide copy | 12.9 us | 13.1 us | 0.980 | 0.980-0.994 | 3.6% | noise |

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 medium document `write` 0.953: placement. The unchanged msgpack-c rows move by the same amount
  (0.950), and with every function aligned to 64 bytes the row reads 0.98 to 1.00 (CHANGELOG).
- i9 small document copy after a fill 0.938: accepted. A fill merges repeated keys and checks the
  keys first; the CHANGELOG measures that check at up to 6%.
