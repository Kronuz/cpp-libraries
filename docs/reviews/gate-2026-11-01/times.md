# gate: times

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). The repository's README has no benchmark command; the gate timed a micro-bench written for it, not kept. `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Status: **measured on both machines, 7 rounds and the same 12 rows each, with a micro-bench written for the gate (the repository has none).** **SAME** overall
(M4 geomean 1.168, i9 geomean 1.060), with trade-offs the CHANGELOG records: two rows below 0.97 on the M4 and three on the i9. The i9 table is the
final run (13:35, with the two chains through `as_double()`); the i9 run before it (11:58, ten rows, no `as_double()` chain) read geomean 1.058 and the same three rows below 0.97.

| | sha | date |
|---|---|---|
| START | `666dfdd` | 2026-10-28 |
| HEAD | `5bab3ee` (origin/main at 2026-11-01 10:27; the developer landed `1f1f9c0` at 09:06, after the first look at `e64ec94`) | 2026-11-01 |

`times` is header-only (`times.h`; `times.cc` is the pre-10.12 macOS clock shim). Library change START..HEAD, all in `times.h`:
`timespec_t(double)` keeps whole seconds in `time_t` (START went through `int`: undefined above 2^31) and folds a negative fraction into
`tv_nsec` in `[0, 1e9)`; `_adjust()` compares with integer constants instead of `1e9L`; the constructor has three code shapes
(`TIMES_CTOR_SHAPE`: portable, `trunc` with 64-bit lanes on arm64, `trunc` with a 32-bit count on x86 with SSE4.1); the six
`double <op> timespec_t` operators take `const timespec_t&` (START took a non-const reference, so `0.5 < now()` did not compile).

## Machines, compiler, commands

| | CPU | OS | compiler |
|---|---|---|---|
| M4 | Apple M4 Pro (14 cores) | macOS, arm64 | Apple clang 17.0.0 (clang-1700.3.19.1) |
| i9 | Intel i9-9980HK (8C/16T) | macOS 15, x86_64 | Apple clang 17.0.0 (clang-1700.6.4.2) |

- Micro-bench (`$GATE/micro/times_bench.cc`): one source compiled against START's `times.h` and against HEAD's: `c++ -std=c++20
  -O3 -DNDEBUG -DHAVE_CLOCK_GETTIME=1 -I<dir with that times.h>` (`gate-micro.sh times 666dfdd 5bab3ee`, same flags both sides). Rows, ns per
  operation, 4096 inputs read through an opaque pointer, best of 9 runs of about 15 ms: `+=`/`-=` pair, `as_double()`, `now()`,
  `timespec_t * double`, `timespec_t / double`, `double < timespec_t` (through a non-const copy so START compiles), `timespec_t(double)`
  over an array of positive values in [0, 2^31) and of negative ones, and the constructor in a dependent chain (the next input depends on
  the previous result). Inputs stay inside [0, 2^31) seconds, where START is defined.
- Rounds: `gate-run.sh times times_bench 7`: per round A, B, A again (the A/A control), interleaved, in one `quiet strict` hold per machine
  (`gate-hold.sh times`; M4 12:02:13 to 12:03:24, i9 13:35:12 to 13:36:15; the builds ran inside the holds; an earlier i9 run, 11:58:57 to 11:59:49,
  predates the `as_double()` chains). Ratios from `gate-cmp.py` (built
  on `ab_compare.py compare`): START/HEAD, above 1 = HEAD faster; "range" = min and max of the seven paired ratios; A/A = the first A against
  the second A; the verdict means outside the A/A spread.
- A first i9 run had a flawed chain row: `x = p[i] + (double)(t.tv_nsec == LONG_MAX)` lets the compiler fold the comparison on START (its
  `tv_nsec` came from an `int`), removing the dependency, so it read START 0.37 ns against HEAD 1.20 ns. It is discarded
  (`results/i9/times.invalid-chain`). The chain now hides the range of `tv_nsec` from the compiler with an empty `asm` ("chain through
  `tv_nsec` only"), and a second chain through `as_double()` of the result was added (the CHANGELOG's own design).
- Raw outputs: `$GATE/results/m4/times/times_bench/{a,b,aa}/` and, for the i9, `results/i9/times/times_bench/{a,b,aa}/` (the earlier ten-row
  run is `results/i9/times.run1/times_bench/`).

## M4 (A/A within 1.2%)

| row                                                                  | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------------------------------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| += / -= pair                                                         |  1.45 |  1.28 |     1.134x | 1.13-1.15 | 1.001 | 7 |  faster |
| as_double()                                                          | 0.571 | 0.570 |     1.002x | 0.99-1.02 | 1.002 | 7 |   noise |
| now()                                                                |  12.4 |  12.6 |     0.982x | 0.97-0.99 | 1.003 | 7 |  slower |
| timespec_t * double                                                  |  1.01 | 0.689 |     1.464x | 1.45-1.47 | 1.001 | 7 |  faster |
| timespec_t / double                                                  |  1.20 | 0.730 |     1.640x | 1.63-1.67 | 1.003 | 7 |  faster |
| double < timespec_t                                                  | 0.747 | 0.744 |     1.003x | 0.99-1.01 | 0.999 | 7 |   noise |
| timespec_t(double), array, values in [0, 2^31)                       | 0.322 | 0.352 |     0.917x | 0.91-0.92 | 0.997 | 7 |  slower |
| timespec_t(double), array, values in (-2^31, 0] [folds now]          | 0.323 | 0.352 |     0.918x | 0.91-0.92 | 1.000 | 7 |  slower |
| timespec_t(double), chain through tv_nsec only, positive             |  10.1 |  7.37 |     1.384x | 1.35-1.42 | 0.992 | 7 |  faster |
| timespec_t(double), chain through tv_nsec only, negative [folds now] |  10.1 |  7.40 |     1.362x | 1.35-1.39 | 0.996 | 7 |  faster |
| timespec_t(double), chain through as_double(), positive              |  13.6 |  11.1 |     1.238x | 1.20-1.25 | 0.992 | 7 |  faster |
| timespec_t(double), chain through as_double(), negative [folds now]  |  13.6 |  11.2 |     1.222x | 1.21-1.24 | 0.994 | 7 |  faster |

ns per operation. **M4 geomean 1.168** over 12 rows (per-run 1.163 / 1.168 / 1.172; A/A geomean 0.998).

## i9 (final run, 7 rounds; A/A within 2.3%)

| row                                                                  | START | HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------------------------------------------------- | ----: | ---: | ---------: | --------: | ----: | : | ------: |
| += / -= pair                                                         |  4.38 | 4.39 |     0.997x | 0.94-1.05 | 1.006 | 7 |   noise |
| as_double()                                                          |  1.16 | 1.15 |     1.005x | 0.99-1.02 | 1.008 | 7 |   noise |
| now()                                                                |  25.1 | 24.5 |     1.023x | 1.01-1.06 | 0.991 | 7 |   noise |
| timespec_t * double                                                  |  5.14 | 3.40 |     1.512x | 1.48-1.57 | 0.992 | 7 |  faster |
| timespec_t / double                                                  |  6.00 | 3.51 |     1.701x | 1.67-1.75 | 1.001 | 7 |  faster |
| double < timespec_t                                                  |  2.24 | 2.42 |     0.925x | 0.90-0.96 | 0.990 | 7 |  slower |
| timespec_t(double), array, values in [0, 2^31)                       |  1.20 | 1.18 |     1.017x | 0.98-1.04 | 1.008 | 7 |   noise |
| timespec_t(double), array, values in (-2^31, 0] [folds now]          |  1.20 | 1.17 |     1.015x | 1.00-1.05 | 0.999 | 7 |   noise |
| timespec_t(double), chain through tv_nsec only, positive             |  1.77 | 2.12 |     0.821x | 0.81-0.86 | 1.020 | 7 |  slower |
| timespec_t(double), chain through tv_nsec only, negative [folds now] |  1.75 | 2.13 |     0.827x | 0.79-0.85 | 0.999 | 7 |  slower |
| timespec_t(double), chain through as_double(), positive              |  18.2 | 16.6 |     1.090x | 1.07-1.11 | 1.023 | 7 |  faster |
| timespec_t(double), chain through as_double(), negative [folds now]  |  17.9 | 16.6 |     1.079x | 1.06-1.10 | 0.990 | 7 |  faster |

ns per operation. **i9 geomean 1.060** over 12 rows (per-run 1.057 / 1.059 / 1.072; A/A geomean 1.002). The earlier i9 run (11:58, ten rows) gave 1.058, and
its three rows below 0.97 read 0.936, 0.829 and 0.830 against 0.925, 0.821 and 0.827 here: they reproduce.

## Rows below 0.97

| host | row | ratio | cause |
|---|---|---|---|
| M4 | `timespec_t(double)` over an array, positive | 0.917 | CHANGELOG trade-off: START's loop vectorized because it converted through `int` and did not normalize a negative value; HEAD converts to `time_t` and adds the borrow (4 vector operations per pair). CHANGELOG records 0.326 to 0.358 ns (1.10x slower) |
| M4 | `timespec_t(double)` over an array, negative | 0.918 | the same code path; the correctness fix (a folded `tv_nsec` in `[0, 1e9)`) is what costs it |
| i9 | `double < timespec_t` | 0.925 | CHANGELOG trade-off: the comparison reads the seconds first, which now wait for the nanosecond conversion that produces the borrow (CHANGELOG: 8% slower on the i9; 1/0.925 is 8.1%) |
| i9 | chain through `tv_nsec` only, positive and negative | 0.821, 0.827 | **not explained by the CHANGELOG, which measures a chain through the whole result and finds the i9 12% faster.** The gate's chain through `as_double()` of the result, the CHANGELOG's design, reads 1.090 and 1.079 on the i9 (HEAD 8 to 9% faster; M4 1.238 and 1.222), so the direction of the CHANGELOG's claim reproduces and the size is smaller. The two chains differ in what the next input waits for. A hypothesis, not measured: HEAD's `tv_nsec` is produced later (64-bit conversion, `trunc`, borrow) than START's `int` conversion, so a loop that waits only on `tv_nsec` pays that latency |

Inside A/A but near: M4 `now()` 0.982 (`clock_gettime`, not library code).

## Correctness changes that affect comparability

`timespec_t(double)` for a negative non-integral value now returns a folded value (`tv_sec` one lower, `tv_nsec` positive) instead of a
negative `tv_nsec`: the same instant, different fields, and more work per element. Values at or above 2^31 seconds are undefined at START and
are not timed. The six `double <op> timespec_t` operators did not compile for a `const timespec_t` at START; the bench compares through a
non-const copy.

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 `timespec_t(double)` over an array, positive 0.917 and negative 0.918, and the same on the i9
  (0.89): accepted, [times#1](https://github.com/Kronuz/times/issues/1). Start's loop vectorized
  through `int`; head converts to `time_t`, which keeps whole seconds past `INT_MAX`, and borrows into
  a positive `tv_nsec`.
- i9 chains through `tv_nsec` (0.821, 0.827) and `double < timespec_t` (0.925): fixed in
  `times:c6d1a90`. The rows timed a loop of single constructions, and x86 builds one value in 64-bit
  arithmetic as arm64 does: a loop of single constructions on the i9 is at start.
