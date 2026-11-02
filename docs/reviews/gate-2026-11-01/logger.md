# Gate: logger

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/logger#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `logger:ce27b90` (`ce27b9054098ecc3eb5f3430882b56649397653a`) | 2026-10-28 04:46:55 -0700 | Credit Germán Méndez Bravo and bound Dubalu's years |
| HEAD (`origin/main`, fetched 2026-11-01 ~09:00) | `logger:035af41` (`035af41460d5d48ed4a443f1deb86138f8f4b2bb`) | 2026-11-01 04:21:23 -0800 | Shape the README to the family standard [skip ci] |

Library sources changed between them (docs, tests, benches, CI, CMake excluded): `logger.cc` and `logger.h`, 763 insertions and 65 deletions. The benches (`bench/*.cc`), most tests and `test/frozen/` (a frozen copy of the pre-change implementation) are new since START. What changed (from `CHANGELOG.md`): the producer hands each record to the LOG thread with one compare-exchange (the scheduler's `post()` / `post_ordered()`) instead of a wheel insert; the macros format into a per-thread reusable buffer; the pending count is a striped producer counter plus a consumer-owned counter; one steady-clock read per call with the wall-clock stamp derived from it; the default timestamp caches the broken-down local time per second; **an async line due within one wheel tick (1 ms) is now scheduled 1 ms after the call** (accepted latency trade-off, README); ordered posts are ordered per thread.

## Method

- Rig: `$GATE/logger/` on both machines. Worktrees of one clone, all at HEAD: `head/` as is, `start/` with `logger.cc logger.h` taken from START (`git rm` then `git checkout ce27b90 --`; `$GATE/raw/logger/m4/start-diffstat.txt`: `logger.cc | 452`, `logger.h | 376`, nothing else). Both use HEAD's CMake and HEAD's `bench/*.cc` (the benches use the public API only; all of them compile against START).
- **Fixed dependencies (the verdict rows):** both sides, both machines, HEAD's CMake pins, byte-identical checkouts (`start/` is configured with `-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_<NAME>=head/build/_deps/<name>-src` for every dependency, so START's logger runs on HEAD's scheduler): `scheduler:34631ecac97b59b25fc5185b3ad2ebe5aa5b9efc` (with `stash:78a18f3162de8d482fa2e3c480d1a3e9cf862537`, `threadpool:628679a2e27b563cf2709a6f35f98f1657baf7b3`, `random:a6c4f6c1d2d82d03c73f421a624de238edc823c5`), `term-color:534e30905b1a40ae1f18dbde46b039dd4333747b`, `static_string:eb1efcb39f4d8bb4fd20a9ea91498a288d25aca2`, `cppcodec:8019b8b580f8573c33c50372baec7039dfe5a8ce`, `fmt:e69e5f977d458f2650bb346dadf2ad30c5320281` (10.2.1, the synchronous comparator).
- **Supplementary "stack" column:** START's logger sources with the dependencies START's own CMake pinned, built in `stack/` with HEAD's benches: `scheduler:2cbea95b0bbfee638b73f36ae11ab4e4fb6f4cd5` (which pins `stash:351ef2e0fb69c3648eb1e33439ced4a50443200b`, `threadpool:628679a` (unchanged) and `random:6487253c9e7a4855ccbea36f7a66cea5fef7d381`); `term-color` is unchanged and START's `cppcodec` at `master` is the same commit as HEAD's pin. It is compared against HEAD (no A/A, fewer rounds) and answers "what the logger a user had at START costs now, scheduler included". It is not used for the verdict.
- Compiler (both machines): Apple clang 17.0.0, `/usr/bin/clang++`, CMake `-G Ninja -DCMAKE_BUILD_TYPE=Release -DLOGGER_BUILD_BENCH=ON` = `-O3 -DNDEBUG -std=gnu++20`, no `-march`. M4: `clang-1700.3.19.1`, arm64, macOS 26.7.2, 14 cores. i9: `clang-1700.6.4.2`, x86_64, macOS 15.8.1, i9-9980HK 8 cores / 16 threads.
- Builds: `nice -n 19 cmake --build {head,start,stack}/build --target logger_bench logger_steady logger_drain -j4`, **outside a hold** because the `quiet light` request was starved for more than 15 minutes by queued strict holds (M4 09:27 to 09:41, i9 09:29 to 09:45), which the recipe allows. Each binary was smoke-run unheld once before the strict hold (all rows present).
- Measurement: one `quiet strict` hold per machine running `gate.sh` (raw dir), `ab_compare.py run` interleaving A = START, B = HEAD and A/A = START again. Rows (`bench/` header comments say how each reports):
  - `lg` (`logger_bench`; no arguments): median of 5 runs inside each process, ns per `L_INFO`, for 1 and 4 producer threads plus the LOG thread: `burst` (LOG thread idle, the producer's own work), `steady` (producers while the LOG thread drains), `end-to-end` (first call until the last line is written), and `comparator: fmt + mutex + counting sink` (fmt only; it runs no logger code, so its ratio is the noise floor). `--section '^--- (\d+ producer thread\(s\))' --regex '^(?P<row>\S.*?)\s+median\s+(?P<value>[0-9.]+)\s'`. 7 rounds on the M4, 5 on the i9. The `min` column of the same output is read as a second table.
  - `drain 200000` (`logger_drain`): 200 000 lines from one thread, then the LOG thread drains; rows `produced` (ns per line on the producer) and `drained` (ns per line from the first call to the last line written, which includes the 1 ms deferral). 9 rounds on the M4, 7 on the i9.
  - `steady 4` (`logger_steady`): a producer loop for 4 s while the LOG thread drains; the row is the final cumulative "ns per line produced" (a 1-line wrapper `bin/steady.{start,head}` keeps the last line). 5 rounds on the M4, 3 on the i9.
  - `latency` (a 30-line `latency.cc` written for the gate, not kept, public API only): one isolated `L_INFO` every 5 ms, 300 samples, nanoseconds from the call until the handler runs (median and p90). It measures the 1 ms deferral that the throughput benches cannot show. Built by reusing the `logger_drain` compile and link commands (`latbuild.sh`). Run in a second short hold on the M4 and at the end of the i9 hold.
  - `parts` (`bench/parts.cc`) is **not a logger benchmark**: it includes only the standard library and times clocks, atomics, `std::format` and `malloc` in isolation, so it cannot differ between START and HEAD. Not run (it also contains an arm64-only `mrs cntvct_el0` row and does not compile on the i9).
- The tables are `ab_compare.py compare --output csv` over the saved runs, formatted by `mkrep.py`. `A/A spread` is the largest |A/A ratio - 1| over the rounds. A row is called slower when its ratio is below 0.97 and ab_compare's verdict is `slower` (ratio / (1 + A/A spread) < 1). Ratio = START / HEAD for times, so above 1 means HEAD is faster. The geomean is over the logger rows; the fmt comparator rows are noise controls and are left out of it (the geomean with them is printed too).

## Results

### Apple M4 Pro (the M4 Pro)

#### lg median ns/line

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / L_INFO burst (LOG thread idle) | 339.6 | 65.5 | 5.241 | 4.86-5.58 | 0.980 | 11.8% | 7 | faster |
| 1 producer thread(s) / L_INFO steady (wall / calls) | 253.3 | 60.9 | 4.022 | 3.60-4.61 | 0.937 | 16.0% | 7 | faster |
| 1 producer thread(s) / L_INFO end-to-end (produce + drain) | 707.6 | 332.6 | 2.073 | 1.91-2.26 | 0.991 | 9.5% | 7 | faster |
| 1 producer thread(s) / comparator: fmt + mutex + counting sink | 26.1 | 26.2 | 0.992 | 0.98-1.01 | 1.024 | 7.8% | 7 | noise |
| 4 producer thread(s) / L_INFO burst (LOG thread idle) | 459.5 | 123.4 | 3.584 | 2.81-4.52 | 0.975 | 8.9% | 7 | faster |
| 4 producer thread(s) / L_INFO steady (wall / calls) | 197.3 | 155.5 | 1.235 | 1.09-1.44 | 0.971 | 12.0% | 7 | faster |
| 4 producer thread(s) / L_INFO end-to-end (produce + drain) | 700.0 | 316.8 | 2.228 | 2.09-2.29 | 0.991 | 1.1% | 7 | faster |
| 4 producer thread(s) / comparator: fmt + mutex + counting sink | 81.1 | 82.2 | 0.991 | 0.95-1.04 | 0.981 | 9.4% | 7 | noise |

#### lg min ns/line (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / L_INFO burst (LOG thread idle) | 311.9 | 61.6 | 4.998 | 4.71-5.47 | 0.976 | 16.0% | 7 | faster |
| 1 producer thread(s) / L_INFO steady (wall / calls) | 223.9 | 55.5 | 4.027 | 3.86-4.33 | 1.009 | 6.6% | 7 | faster |
| 1 producer thread(s) / L_INFO end-to-end (produce + drain) | 661.3 | 324.8 | 2.048 | 1.98-2.15 | 0.994 | 4.3% | 7 | faster |
| 1 producer thread(s) / comparator: fmt + mutex + counting sink | 25.0 | 25.0 | 1.000 | 0.96-1.01 | 0.992 | 1.6% | 7 | noise |
| 4 producer thread(s) / L_INFO burst (LOG thread idle) | 424.6 | 106.2 | 3.996 | 3.66-4.42 | 0.954 | 12.1% | 7 | faster |
| 4 producer thread(s) / L_INFO steady (wall / calls) | 167.1 | 135.7 | 1.189 | 0.95-1.48 | 1.037 | 49.2% | 7 | noise |
| 4 producer thread(s) / L_INFO end-to-end (produce + drain) | 681.6 | 309.0 | 2.237 | 2.11-2.30 | 0.978 | 6.2% | 7 | faster |
| 4 producer thread(s) / comparator: fmt + mutex + counting sink | 79.3 | 79.1 | 0.986 | 0.68-1.07 | 1.010 | 35.3% | 7 | noise |

#### drain ns/line (200000 lines)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| produced | 311.5 | 91.7 | 3.451 | 2.93-3.82 | 0.963 | 23.5% | 9 | faster |
| drained | 728.1 | 344.0 | 2.120 | 2.03-2.23 | 0.978 | 10.6% | 9 | faster |

#### steady ns/line produced (4 s)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| produced | 282.1 | 67.6 | 4.300 | 3.94-4.37 | 1.000 | 4.7% | 5 | faster |

#### single-line latency ns (300 isolated lines, 5 ms apart) (reported in the slow-row list, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| median | 19666.0 | 1.26e+06 | 0.016 | 0.01-0.02 | 0.919 | 18.1% | 5 | slower |
| p90 | 36667.0 | 1.27e+06 | 0.029 | 0.02-0.03 | 0.969 | 35.0% | 5 | slower |

#### STACK (START sources + START's own dependency pins) against HEAD: lg median ns/line (informational, not in the geomean)

| row | STACK | HEAD | STACK/HEAD | range | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / L_INFO burst (LOG thread idle) | 436.7 | 65.6 | 6.477 | 6.42-6.92 | 5 | faster |
| 1 producer thread(s) / L_INFO steady (wall / calls) | 457.1 | 64.7 | 6.951 | 6.35-8.22 | 5 | faster |
| 1 producer thread(s) / L_INFO end-to-end (produce + drain) | 739.2 | 336.2 | 2.235 | 2.09-2.31 | 5 | faster |
| 1 producer thread(s) / comparator: fmt + mutex + counting sink | 25.8 | 26.0 | 0.996 | 0.97-1.01 | 5 | noise |
| 4 producer thread(s) / L_INFO burst (LOG thread idle) | 725.0 | 133.1 | 5.547 | 5.03-5.88 | 5 | faster |
| 4 producer thread(s) / L_INFO steady (wall / calls) | 455.7 | 150.2 | 3.262 | 2.76-3.43 | 5 | faster |
| 4 producer thread(s) / L_INFO end-to-end (produce + drain) | 782.4 | 319.1 | 2.453 | 2.35-2.58 | 5 | faster |
| 4 producer thread(s) / comparator: fmt + mutex + counting sink | 85.8 | 78.1 | 1.126 | 0.97-1.15 | 5 | faster |

#### STACK against HEAD: drain ns/line (informational, not in the geomean)

| row | STACK | HEAD | STACK/HEAD | range | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| produced | 507.0 | 95.9 | 5.323 | 4.06-5.86 | 7 | faster |
| drained | 788.2 | 360.2 | 2.169 | 2.07-2.24 | 7 | faster |

#### STACK against HEAD: steady ns/line produced (informational, not in the geomean)

| row | STACK | HEAD | STACK/HEAD | range | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| produced | 491.3 | 66.3 | 7.394 | 7.38-7.85 | 3 | faster |

#### STACK against HEAD: single-line latency ns (informational, not in the geomean)

| row | STACK | HEAD | STACK/HEAD | range | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| median | 18666.0 | 1.26e+06 | 0.015 | 0.01-0.02 | 3 | slower |
| p90 | 35458.0 | 1.27e+06 | 0.028 | 0.03-0.03 | 3 | slower |

geomean over 11 primary rows: 2.371
geomean without the fmt comparator rows (9 rows): 2.878
STACK/HEAD geomean over 9 logger rows (no comparator, no latency): 4.170

rows < 0.97 outside the A/A spread:
- single-line latency ns (300 isolated lines, 5 ms apart): median: 0.016 (A/A spread 18.1%)
- single-line latency ns (300 isolated lines, 5 ms apart): p90: 0.029 (A/A spread 35.0%)

### Intel i9-9980HK

#### lg median ns/line

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / L_INFO burst (LOG thread idle) | 1045.3 | 350.0 | 3.100 | 2.83-3.25 | 1.043 | 13.2% | 5 | faster |
| 1 producer thread(s) / L_INFO steady (wall / calls) | 639.7 | 236.7 | 2.708 | 2.52-2.93 | 0.994 | 7.9% | 5 | faster |
| 1 producer thread(s) / L_INFO end-to-end (produce + drain) | 1561.0 | 712.6 | 2.202 | 1.92-2.30 | 0.991 | 4.2% | 5 | faster |
| 1 producer thread(s) / comparator: fmt + mutex + counting sink | 59.5 | 61.8 | 0.995 | 0.90-1.09 | 1.012 | 10.0% | 5 | noise |
| 4 producer thread(s) / L_INFO burst (LOG thread idle) | 759.6 | 335.2 | 2.293 | 2.07-2.38 | 1.002 | 3.9% | 5 | faster |
| 4 producer thread(s) / L_INFO steady (wall / calls) | 212.0 | 84.5 | 2.552 | 2.47-2.66 | 1.007 | 4.2% | 5 | faster |
| 4 producer thread(s) / L_INFO end-to-end (produce + drain) | 1554.7 | 809.8 | 1.939 | 1.83-2.04 | 1.016 | 3.0% | 5 | faster |
| 4 producer thread(s) / comparator: fmt + mutex + counting sink | 177.3 | 178.9 | 1.025 | 0.96-1.04 | 0.987 | 5.4% | 5 | noise |

#### lg min ns/line (informational, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / L_INFO burst (LOG thread idle) | 955.3 | 321.0 | 2.955 | 2.83-3.03 | 1.138 | 16.9% | 5 | faster |
| 1 producer thread(s) / L_INFO steady (wall / calls) | 608.2 | 223.1 | 2.844 | 2.61-2.96 | 0.976 | 4.7% | 5 | faster |
| 1 producer thread(s) / L_INFO end-to-end (produce + drain) | 1523.1 | 657.0 | 2.325 | 2.01-2.36 | 1.003 | 5.1% | 5 | faster |
| 1 producer thread(s) / comparator: fmt + mutex + counting sink | 58.7 | 60.7 | 0.998 | 0.89-1.11 | 0.995 | 10.0% | 5 | noise |
| 4 producer thread(s) / L_INFO burst (LOG thread idle) | 721.9 | 299.1 | 2.390 | 2.29-2.60 | 0.981 | 3.0% | 5 | faster |
| 4 producer thread(s) / L_INFO steady (wall / calls) | 203.1 | 78.0 | 2.595 | 2.48-2.72 | 1.001 | 3.9% | 5 | faster |
| 4 producer thread(s) / L_INFO end-to-end (produce + drain) | 1531.8 | 754.9 | 1.970 | 1.86-2.09 | 1.021 | 5.4% | 5 | faster |
| 4 producer thread(s) / comparator: fmt + mutex + counting sink | 175.7 | 175.6 | 1.020 | 1.00-1.03 | 1.024 | 5.2% | 5 | noise |

#### drain ns/line (200000 lines)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| produced | 719.6 | 294.7 | 2.448 | 2.40-2.61 | 0.994 | 5.6% | 7 | faster |
| drained | 1598.8 | 748.1 | 2.137 | 2.10-2.22 | 0.991 | 5.6% | 7 | faster |

#### steady ns/line produced (4 s)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| produced | 650.4 | 221.2 | 2.940 | 2.94-2.94 | 1.000 | 2.4% | 3 | faster |

#### single-line latency ns (300 isolated lines, 5 ms apart) (reported in the slow-row list, not in the geomean)

| row | START | HEAD | START/HEAD | range | A/A | A/A spread | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| median | 55630.0 | 1.51e+06 | 0.037 | 0.04-0.04 | 1.016 | 3.7% | 5 | slower |
| p90 | 96994.0 | 1.56e+06 | 0.062 | 0.06-0.06 | 0.992 | 6.4% | 5 | slower |

#### STACK (START sources + START's own dependency pins) against HEAD: lg median ns/line (informational, not in the geomean)

| row | STACK | HEAD | STACK/HEAD | range | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 producer thread(s) / L_INFO burst (LOG thread idle) | 1158.6 | 330.9 | 3.632 | 2.73-3.73 | 3 | faster |
| 1 producer thread(s) / L_INFO steady (wall / calls) | 734.2 | 235.8 | 3.186 | 3.11-3.30 | 3 | faster |
| 1 producer thread(s) / L_INFO end-to-end (produce + drain) | 1568.1 | 778.4 | 2.007 | 2.01-2.31 | 3 | faster |
| 1 producer thread(s) / comparator: fmt + mutex + counting sink | 59.3 | 62.8 | 0.944 | 0.87-1.04 | 3 | slower |
| 4 producer thread(s) / L_INFO burst (LOG thread idle) | 1069.7 | 322.1 | 3.457 | 3.12-3.52 | 3 | faster |
| 4 producer thread(s) / L_INFO steady (wall / calls) | 471.9 | 84.9 | 5.643 | 5.54-5.74 | 3 | faster |
| 4 producer thread(s) / L_INFO end-to-end (produce + drain) | 1653.3 | 776.2 | 2.148 | 2.10-2.16 | 3 | faster |
| 4 producer thread(s) / comparator: fmt + mutex + counting sink | 173.8 | 179.4 | 0.968 | 0.96-1.01 | 3 | slower |

#### STACK against HEAD: drain ns/line (informational, not in the geomean)

| row | STACK | HEAD | STACK/HEAD | range | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| produced | 777.2 | 299.9 | 2.675 | 2.55-2.74 | 7 | faster |
| drained | 1600.4 | 768.8 | 2.100 | 2.04-2.25 | 7 | faster |

#### STACK against HEAD: steady ns/line produced (informational, not in the geomean)

| row | STACK | HEAD | STACK/HEAD | range | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| produced | 725.3 | 225.0 | 3.235 | 3.19-3.27 | 3 | faster |

#### STACK against HEAD: single-line latency ns (informational, not in the geomean)

| row | STACK | HEAD | STACK/HEAD | range | n | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| median | 51829.0 | 1.52e+06 | 0.034 | 0.03-0.04 | 3 | slower |
| p90 | 95691.0 | 1.56e+06 | 0.061 | 0.06-0.06 | 3 | slower |

geomean over 11 primary rows: 2.088
geomean without the fmt comparator rows (9 rows): 2.454
STACK/HEAD geomean over 9 logger rows (no comparator, no latency): 2.965

rows < 0.97 outside the A/A spread:
- single-line latency ns (300 isolated lines, 5 ms apart): median: 0.037 (A/A spread 3.7%)
- single-line latency ns (300 isolated lines, 5 ms apart): p90: 0.062 (A/A spread 6.4%)


## Findings

### Rows < 0.97 outside the A/A spread

| machine | row | START | HEAD | START/HEAD | cause |
|---|---|---:|---:|---:|---|
| M4 | single-line latency, median (isolated `L_INFO` to handler) | 19.7 us | 1.26 ms | 0.016 | accepted trade-off, below |
| M4 | single-line latency, p90 | 36.7 us | 1.27 ms | 0.029 | same |
| i9 | single-line latency, median | 55.6 us | 1.51 ms | 0.037 | same |
| i9 | single-line latency, p90 | 97.0 us | 1.56 ms | 0.062 | same |

No throughput row is slower on either machine: every `lg`, `drain` and `steady` row for the logger is between 1.2x and 5.2x faster, and the fmt comparator rows (code the change cannot reach) sit at 0.99 to 1.03.

**Cause (accepted latency trade-off, not a regression of the producer path).** `CHANGELOG.md` 2026-10-31: "An async line due within one wheel tick (1 ms) is now scheduled 1 ms after the call, so the LOG thread sleeps to that time and the lines queued meanwhile need no signal. A hard crash within that millisecond loses the line." The README states it ("a routine line is written up to 1 ms after the call"). START signalled the LOG thread for every line, so an isolated line reached the handler in 20 to 55 us; HEAD lets it wait for the wheel's next tick. The measured HEAD latency is 1.26 ms (M4) and 1.51 ms (i9): the 1 ms floor plus the tick and wake-up. The deferral is one of the changes behind the cheaper producer path (no per-line signal); the others are the lock-free `post()` hand-off, the per-thread format buffer and the single clock read. These rows are my own micro-bench (`latency.cc`); the repo's benches do not measure it. Lines more severe than `LOG_ERR` are written on the calling thread and are not delayed (CHANGELOG 2026-11-01, `test/order.cc`); this measurement is the routine `L_INFO` path.

Unexplained rows: none. (In the stack tables the fmt comparator rows read 0.94 to 1.13 with no A/A and 3 to 5 rounds: that is the noise floor of those reads, not a finding.)

### Rows dropped or not comparable

- `bench/parts.cc` is not a logger benchmark (standard library only, an arm64-only `mrs cntvct_el0` row) and has no START / HEAD difference to measure. Not run.
- The end-to-end rows (`lg` end-to-end, `drain` `drained`) include the 1 ms deferral once per run, which is about 20 ns per line at 50 000 lines and 5 ns at 200 000. That makes them slightly pessimistic for HEAD; they are still 1.9x to 2.5x faster.
- `lg`'s `steady` and `burst` rows measure the producer's own cost, the quantity the producer-path work targeted; `drain`'s `produced` and `steady 4` do the same on one thread. START's `Logger::log` path on HEAD's scheduler uses `add()`, which HEAD's scheduler made cheaper than at START, so the fixed-dependency column understates what a user who upgrades the whole stack sees (the stack column).
- Correctness changes in range (`CHANGELOG.md`): the 1 ms shift now applies to every scheduled line including `clears` lines (a fix that adds at most a tick, not CPU); ordered posts are ordered per thread; a refusal inside the LOG thread no longer reaches the poster. None changes the amount of work a benchmark row measures beyond what is described above.

### Holds and load

| machine | hold | queued | started | ended | uptime load (1, 5, 15 min) at start / at end |
|---|---|---|---|---|---|
| M4 | M4 hold (main A/B/A + stack) | 09:43 | 10:28:00 | 10:31:45 | 10.30 13.47 15.11 / 11.20 12.24 14.18 |
| M4 | M4 hold (latency) | 10:36 | 11:59:03 | 11:59:45 | 11.60 9.56 10.07 / 11.97 9.95 10.19 |
| i9 | i9 hold (main + stack + latency) | 09:47, requeued 10:36 | 11:21:18 | 11:25:28 | 6.28 6.60 7.01 / 10.02 7.66 7.33 |

On macOS a strict hold is exclusive, but the M4 load average stayed at 10 to 15 through every hold (other jobs' non-`quiet` work, which is not ours to stop); the A/A control absorbs it. The A/A spread of the M4 latency row is 18 to 35 percent, far inside the 60x difference. The builds ran unheld after `quiet light` starved for more than 15 minutes (recipe).

Raw per-run files, ab_compare outputs and hold logs: `$GATE/raw/logger/{m4,i9}/` (`lg/ drain/ steady/ latency/ stack-*/`, `*.md`, `uptime.txt`, `hold-*.log`); scripts `gate.sh lat.sh latency.cc latbuild.sh build.sh build2.sh stackcfg.sh mkrep.py`.

SUMMARY repo=logger m4_geomean=2.878 i9_geomean=2.454 m4_slow=2/0.016 i9_slow=2/0.037 unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- Single-line latency, from an isolated `L_INFO` to the handler, median and p90 (M4 0.016 and
  0.029, i9 0.037 and 0.062): accepted. A line due within one 1 ms wheel tick is written 1 ms after
  the call, so producers rarely signal the LOG thread. These rows come from the gate's own
  micro-bench and are not in the geomean of 2.878 and 2.454. A change that
  writes an isolated line at once is in progress.
