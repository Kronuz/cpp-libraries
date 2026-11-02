# bitpack: START cd13f36 to HEAD 48adb4b

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/bitpack#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`): `cd13f36ac88da3e35bde622db706a2a24143e187`, 2026-10-22 04:39:01 -0700. HEAD is `origin/main` when the run started: `48adb4bee4b97fb47b457259416c02becde5ee8e`, 2026-11-01 04:24:40 -0800 (12 commits later). Measured 2026-11-01 by gate measurer g14a.

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64, NEON kernels), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja 1.13.2 |
| i9 | Intel i9-9980HK (8C/16T, x86-64, SSE2 kernels), macOS 15.8.1, Apple clang 17.0.0 (clang-1700.6.4.2), CMake 4.4.4, Ninja 1.13.2 |

- Both sides: `/usr/bin/clang++`, `-DCMAKE_BUILD_TYPE=Release` (`-O3 -DNDEBUG`), C++20 from the target, no `-march`. bitpack is header-only: `bitpack.hh` is the only library file. `BITPACK_BENCH_REFERENCE` (simdcomp / SIMD-BP128) is off: no dependency is fetched.
- START tree = HEAD's tree (HEAD's `bench/`, `test/`, `CMakeLists.txt`) with only `bitpack.hh` replaced by START's. `git diff --cached --stat HEAD` of the START tree: `bitpack.hh | 29 +---- 1 file changed, 1 insertion(+), 28 deletions(-)`. So START..HEAD adds 28 lines and removes 1 in the header: the NEON `unpack` kernels that load each input word once (`unpack_row` overload with a carried word, `unpack_rows`), the NEON width 32 `memcpy`, and comments in the SSE and delta sections. The x86-64 (SSE2) code is unchanged.
- Bench: HEAD's `bench/bench.cc` (`bitpack_bench`: `unpack`, `unpack_delta` and `unpack_scalar` throughput at widths 1 to 32, 96 rows) and `bench/unpack_alias.cc` (`bitpack_unpack_alias 5 32`: the median over 64 input offsets of `unpack` at widths 5 and 32, plus a `memcpy` control at width 32). Both compile against START unchanged; no row was dropped. Throughputs (integers per ns) are turned into ns per integer by a wrapper (`bpw.py`) so that every row is "lower is better" and the ratio reads START/HEAD, above 1 means HEAD is faster. The `alias memcpy w32 (control)` row is library-independent (a `memcpy` in the bench) and is left out of the geomeans.
- Each round runs A (START binary), B (HEAD binary), then A again (the A/A control) through `ab_compare.py run`, in one `quiet strict` hold (strict acts as exclusive on macOS). Range = min-max of the paired round ratios; A/A is the median ratio of START against START again.

## Commands

```sh
# M4: $GATE (clones in src/<repo>); i9: $GATE/bitpack (the clone, trees in .g/)
git worktree add --detach bitpack/head  48adb4bee4b97fb47b457259416c02becde5ee8e
git worktree add --detach bitpack/start 48adb4bee4b97fb47b457259416c02becde5ee8e
(cd bitpack/start && git rm -rq -- bitpack.hh && git checkout cd13f36ac88da3e35bde622db706a2a24143e187 -- bitpack.hh)
for s in head start; do
  cmake -S bitpack/$s -B bitpack/$s/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++
  cmake --build bitpack/$s/build --target bitpack_bench bitpack_unpack_alias -j4
done
# one hold per machine: 3 rounds of bitpack_bench, then 3 rounds of bitpack_unpack_alias 5 32
quiet strict 10 "gate bitpack A/B/A (bench, unpack_alias)" -- ./run.sh m4 3 3 "5 32"
quiet strict 10 "gate bitpack A/B/A (bench, unpack_alias)" -- ./run.sh i9 3 3 "5 32"
quiet strict 10 "gate bitpack confirm: bench only, second hold" -- ./run2.sh m4 3 0 ""   # M4 only
#   run.sh: ab_compare.py run --rounds 3 --format unit --label-a START --label-b HEAD A B   (A, B = wrapper scripts around the START and HEAD binaries)
```

Raw outputs: `$GATE/raw/bitpack/{m4,i9,m4-confirm}/` (`save-*` are the ab_compare run files, `raw-*` the benches' own output). Wrappers, `run.sh` and the disassembly comparison (`dis/cmp_kernels.py`) are in `$GATE/bitpack/`.

## M4 (Apple M4 Pro): the code that changed

`bitpack_bench`, 3 rounds, M4 hold:

| row         | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| simd w01    | 0.044 | 0.036 |     1.206x | 1.19-1.23 | 1.014 | 3 |  faster |
| simd+d1 w01 | 0.290 | 0.289 |     1.006x | 0.99-1.02 | 1.000 | 3 |   noise |
| scalar w01  | 0.152 | 0.152 |     1.002x | 0.99-1.01 | 0.994 | 3 |   noise |
| simd w02    | 0.042 | 0.040 |     1.091x | 1.04-1.12 | 0.993 | 3 |  faster |
| simd+d1 w02 | 0.292 | 0.291 |     1.003x | 0.99-1.01 | 0.997 | 3 |   noise |
| scalar w02  | 0.277 | 0.279 |     0.992x | 0.99-1.01 | 0.981 | 3 |   noise |
| simd w03    | 0.046 | 0.040 |     1.138x | 1.08-1.38 | 1.049 | 3 |   noise |
| simd+d1 w03 | 0.294 | 0.292 |     1.009x | 1.00-1.01 | 1.006 | 3 |   noise |
| scalar w03  | 0.429 | 0.426 |     1.009x | 1.00-1.01 | 0.987 | 3 |   noise |
| simd w04    | 0.045 | 0.043 |     1.034x | 1.02-1.07 | 1.008 | 3 |  faster |
| simd+d1 w04 | 0.292 | 0.293 |     0.997x | 1.00-1.00 | 0.997 | 3 |   noise |
| scalar w04  | 0.264 | 0.270 |     0.984x | 0.96-0.99 | 1.005 | 3 |  slower |
| simd w05    | 0.046 | 0.051 |     0.911x | 0.83-0.98 | 1.007 | 3 |  slower |
| simd+d1 w05 | 0.296 | 0.294 |     1.000x | 1.00-1.01 | 0.997 | 3 |   noise |
| scalar w05  | 0.429 | 0.431 |     0.991x | 0.98-1.00 | 0.991 | 3 |   noise |
| simd w06    | 0.055 | 0.046 |     1.171x | 1.16-1.22 | 1.107 | 3 |  faster |
| simd+d1 w06 | 0.292 | 0.294 |     0.988x | 0.99-1.00 | 0.991 | 3 |  slower |
| scalar w06  | 0.422 | 0.420 |     1.004x | 1.00-1.01 | 0.992 | 3 |   noise |
| simd w07    | 0.049 | 0.047 |     1.064x | 1.04-1.30 | 1.008 | 3 |   noise |
| simd+d1 w07 | 0.292 | 0.293 |     0.994x | 0.98-1.00 | 0.991 | 3 |   noise |
| scalar w07  | 0.461 | 0.461 |     1.005x | 0.99-1.01 | 1.000 | 3 |   noise |
| simd w08    | 0.051 | 0.048 |     1.057x | 1.05-1.13 | 0.998 | 3 |   noise |
| simd+d1 w08 | 0.292 | 0.292 |     0.997x | 0.99-1.00 | 1.003 | 3 |   noise |
| scalar w08  | 0.326 | 0.360 |     0.903x | 0.90-0.91 | 1.010 | 3 |  slower |
| simd w09    | 0.057 | 0.050 |     1.147x | 1.12-1.17 | 0.966 | 3 |  faster |
| simd+d1 w09 | 0.297 | 0.293 |     1.003x | 1.00-1.01 | 0.997 | 3 |   noise |
| scalar w09  | 0.503 | 0.503 |     0.995x | 0.99-1.00 | 1.005 | 3 |   noise |
| simd w10    | 0.060 | 0.050 |     1.185x | 1.15-1.29 | 1.075 | 3 |  faster |
| simd+d1 w10 | 0.295 | 0.293 |     1.000x | 1.00-1.01 | 1.000 | 3 |   noise |
| scalar w10  | 0.529 | 0.524 |     1.011x | 1.01-1.04 | 1.005 | 3 |   noise |
| simd w11    | 0.063 | 0.052 |     1.215x | 1.21-1.24 | 1.001 | 3 |  faster |
| simd+d1 w11 | 0.299 | 0.300 |     0.994x | 0.99-1.00 | 0.994 | 3 |   noise |
| scalar w11  | 0.524 | 0.535 |     0.979x | 0.98-1.00 | 0.974 | 3 |   noise |
| simd w12    | 0.066 | 0.052 |     1.294x | 1.26-1.30 | 1.013 | 3 |  faster |
| simd+d1 w12 | 0.296 | 0.296 |     1.003x | 0.99-1.01 | 0.997 | 3 |   noise |
| scalar w12  | 0.505 | 0.505 |     1.000x | 0.99-1.01 | 1.000 | 3 |   noise |
| simd w13    | 0.066 | 0.055 |     1.215x | 1.16-1.22 | 1.005 | 3 |  faster |
| simd+d1 w13 | 0.299 | 0.299 |     1.006x | 0.99-1.01 | 0.994 | 3 |   noise |
| scalar w13  | 0.559 | 0.559 |     0.994x | 0.99-1.05 | 1.011 | 3 |   noise |
| simd w14    | 0.064 | 0.057 |     1.123x | 1.07-1.13 | 1.004 | 3 |  faster |
| simd+d1 w14 | 0.295 | 0.296 |     0.997x | 0.99-1.00 | 0.997 | 3 |   noise |
| scalar w14  | 0.575 | 0.562 |     1.017x | 0.98-1.08 | 0.972 | 3 |   noise |
| simd w15    | 0.069 | 0.056 |     1.217x | 1.19-1.23 | 1.017 | 3 |  faster |
| simd+d1 w15 | 0.299 | 0.300 |     0.997x | 1.00-1.01 | 0.994 | 3 |   noise |
| scalar w15  | 0.621 | 0.610 |     1.019x | 0.99-1.02 | 0.988 | 3 |   noise |
| simd w16    | 0.063 | 0.059 |     1.070x | 1.06-1.11 | 0.992 | 3 |  faster |
| simd+d1 w16 | 0.292 | 0.291 |     1.003x | 0.99-1.01 | 1.003 | 3 |   noise |
| scalar w16  | 0.318 | 0.321 |     0.994x | 0.99-1.00 | 0.990 | 3 |   noise |
| simd w17    | 0.068 | 0.060 |     1.135x | 1.12-1.15 | 0.997 | 3 |  faster |
| simd+d1 w17 | 0.299 | 0.300 |     0.997x | 0.98-1.00 | 1.003 | 3 |   noise |
| scalar w17  | 0.602 | 0.606 |     1.000x | 0.98-1.01 | 1.012 | 3 |   noise |
| simd w18    | 0.069 | 0.065 |     1.065x | 1.03-1.07 | 1.011 | 3 |  faster |
| simd+d1 w18 | 0.298 | 0.299 |     0.994x | 0.99-1.00 | 0.997 | 3 |   noise |
| scalar w18  | 0.474 | 0.581 |     0.815x | 0.81-0.82 | 0.981 | 3 |  slower |
| simd w19    | 0.073 | 0.066 |     1.106x | 1.06-1.15 | 0.994 | 3 |  faster |
| simd+d1 w19 | 0.295 | 0.296 |     0.997x | 0.99-1.01 | 0.988 | 3 |   noise |
| scalar w19  | 0.495 | 0.493 |     1.005x | 0.99-1.00 | 1.000 | 3 |  faster |
| simd w20    | 0.071 | 0.066 |     1.083x | 1.08-1.09 | 0.996 | 3 |  faster |
| simd+d1 w20 | 0.296 | 0.296 |     1.000x | 0.99-1.01 | 1.000 | 3 |   noise |
| scalar w20  | 0.478 | 0.581 |     0.827x | 0.80-0.83 | 0.990 | 3 |  slower |
| simd w21    | 0.076 | 0.067 |     1.113x | 1.10-1.14 | 1.005 | 3 |  faster |
| simd+d1 w21 | 0.295 | 0.293 |     1.006x | 0.99-1.01 | 1.003 | 3 |   noise |
| scalar w21  | 0.503 | 0.535 |     0.940x | 0.92-0.94 | 1.000 | 3 |  slower |
| simd w22    | 0.076 | 0.066 |     1.151x | 1.15-1.15 | 1.012 | 3 |  faster |
| simd+d1 w22 | 0.294 | 0.295 |     0.991x | 0.99-1.01 | 0.997 | 3 |  slower |
| scalar w22  | 0.556 | 0.515 |     1.083x | 1.08-1.08 | 1.000 | 3 |  faster |
| simd w23    | 0.077 | 0.069 |     1.119x | 1.09-1.15 | 1.002 | 3 |  faster |
| simd+d1 w23 | 0.291 | 0.293 |     0.994x | 0.99-1.00 | 0.997 | 3 |   noise |
| scalar w23  | 0.513 | 0.508 |     1.015x | 1.01-1.02 | 1.005 | 3 |  faster |
| simd w24    | 0.073 | 0.069 |     1.069x | 1.06-1.09 | 0.992 | 3 |  faster |
| simd+d1 w24 | 0.292 | 0.293 |     0.997x | 0.99-1.00 | 1.003 | 3 |   noise |
| scalar w24  | 0.463 | 0.546 |     0.851x | 0.85-0.85 | 0.986 | 3 |  slower |
| simd w25    | 0.081 | 0.070 |     1.160x | 1.16-1.18 | 1.002 | 3 |  faster |
| simd+d1 w25 | 0.292 | 0.292 |     0.997x | 0.99-1.01 | 0.997 | 3 |   noise |
| scalar w25  | 0.535 | 0.532 |     1.005x | 1.00-1.01 | 0.989 | 3 |   noise |
| simd w26    | 0.080 | 0.070 |     1.149x | 1.15-1.16 | 0.994 | 3 |  faster |
| simd+d1 w26 | 0.292 | 0.293 |     0.997x | 0.99-1.00 | 1.003 | 3 |   noise |
| scalar w26  | 0.562 | 0.549 |     1.022x | 1.02-1.02 | 1.006 | 3 |  faster |
| simd w27    | 0.082 | 0.072 |     1.136x | 1.12-1.15 | 0.999 | 3 |  faster |
| simd+d1 w27 | 0.292 | 0.292 |     1.003x | 0.99-1.01 | 1.000 | 3 |   noise |
| scalar w27  | 0.578 | 0.581 |     0.994x | 0.99-1.01 | 1.000 | 3 |   noise |
| simd w28    | 0.081 | 0.074 |     1.096x | 1.09-1.11 | 0.994 | 3 |  faster |
| simd+d1 w28 | 0.291 | 0.291 |     1.000x | 1.00-1.00 | 1.000 | 3 |   noise |
| scalar w28  | 0.505 | 0.505 |     0.995x | 0.99-1.01 | 0.995 | 3 |  slower |
| simd w29    | 0.084 | 0.073 |     1.142x | 1.14-1.15 | 0.993 | 3 |  faster |
| simd+d1 w29 | 0.293 | 0.292 |     1.009x | 0.99-1.01 | 1.003 | 3 |   noise |
| scalar w29  | 0.592 | 0.592 |     1.000x | 0.99-1.00 | 1.024 | 3 |   noise |
| simd w30    | 0.084 | 0.074 |     1.133x | 1.13-1.14 | 0.994 | 3 |  faster |
| simd+d1 w30 | 0.292 | 0.294 |     0.991x | 0.99-1.02 | 0.991 | 3 |  slower |
| scalar w30  | 0.614 | 0.606 |     1.006x | 1.00-1.01 | 0.994 | 3 |   noise |
| simd w31    | 0.085 | 0.076 |     1.128x | 1.11-1.14 | 0.991 | 3 |  faster |
| simd+d1 w31 | 0.293 | 0.292 |     1.006x | 1.00-1.01 | 1.003 | 3 |   noise |
| scalar w31  | 0.565 | 0.565 |     1.000x | 0.99-1.01 | 1.006 | 3 |   noise |
| simd w32    | 0.078 | 0.048 |     1.620x | 1.61-1.68 | 1.003 | 3 |  faster |
| simd+d1 w32 | 0.292 | 0.292 |     1.003x | 1.00-1.00 | 1.003 | 3 |   noise |
| scalar w32  | 0.181 | 0.181 |     0.996x | 0.99-1.00 | 1.004 | 3 |   noise |

runs: START 3, HEAD 3, A/A 3; a ratio above 1 means HEAD is faster
geomean 1.037 over 96 rows (min 0.815 scalar w18; max 1.620 simd w32)
per-run geomean: min 1.038, median 1.038, max 1.039 over 3 runs
A/A geomean 1.001

`bitpack_unpack_alias 5 32`, 3 rounds, same hold:

| row                        | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| alias unpack w05           | 0.048 | 0.047 |     1.029x | 1.02-1.06 | 0.998 | 3 |  faster |
| alias unpack w32           | 0.078 | 0.046 |     1.690x | 1.69-1.71 | 1.001 | 3 |  faster |
| alias memcpy w32 (control) | 0.044 | 0.044 |     0.998x | 0.99-1.01 | 1.002 | 3 |   noise |

runs: START 3, HEAD 3, A/A 3; a ratio above 1 means HEAD is faster
geomean 1.202 over 3 rows (min 0.998 alias memcpy w32 (control); max 1.690 alias unpack w32)
per-run geomean: min 1.200, median 1.207, max 1.214 over 3 runs
A/A geomean 1.000

Geomean over the 98 library rows (96 bench rows + 2 alias rows): **1.042** (the 96 `bitpack_bench` rows alone: 1.037). Rows below 0.97 outside the A/A spread: 6, worst 0.815 (below).

uptime, M4 hold start / between the two benches / end:

Sun Nov  1 10:41:53 PST 2026  |  `10:41  up 5 days, 16:06, 14 users, load averages: 39.10 28.01 20.08`
Sun Nov  1 10:48:24 PST 2026  |  `10:48  up 5 days, 16:13, 14 users, load averages: 9.24 14.41 16.15`
Sun Nov  1 10:50:44 PST 2026  |  `10:50  up 5 days, 16:15, 14 users, load averages: 9.75 12.73 15.21`

The hold started at a load of 39 (the strict wait for the load to settle ends after 10 minutes) and ran at 9-10 for the rest; the A/A column absorbs it (A/A geomean 1.001).

Second hold on the M4 (M4 hold b, `bitpack_bench` only, 3 rounds, load 6-7 throughout; full table in `$GATE/raw/bitpack/m4-confirm/bench.md`): geomean 1.042 over 96 rows, A/A geomean 1.006. Rows below 0.97 outside A/A:

| row | hold 1 | hold 2 (confirm) |
|---|---:|---:|
| simd w05 | 0.911 (0.83-0.98) | 0.844 (0.82-0.86) |
| scalar w08 | 0.903 | 0.907 |
| scalar w18 | 0.815 | 0.829 |
| scalar w20 | 0.827 | 0.806 |
| scalar w21 | 0.940 | 0.946 |
| scalar w24 | 0.851 | 0.853 |
| simd w06 | 1.171 (A/A 1.107, noisy) | 0.933 (0.86-1.10) |

The six rows of hold 1 reproduce in hold 2; `simd w06` flips sign between the holds (range 0.86-1.10) and is counted as noise.

## i9 (Intel i9-9980HK): no code change

`bitpack_bench.start` and `bitpack_bench.head` are byte-identical on the i9 (`cmp` says identical; sha256 `b635cfb8...f2af026c`), and so are the two `bitpack_unpack_alias` binaries (sha256 `0e69afff...96caf3a`): the START..HEAD diff of `bitpack.hh` on x86-64 is comments only. The table below is therefore two runs of one binary, which gives an empirical noise floor for this machine and this bench.

`bitpack_bench`, 3 rounds, i9 hold:

| row         | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| simd w01    | 0.108 | 0.105 |     1.038x | 0.98-1.04 | 1.025 | 3 |   noise |
| simd+d1 w01 | 0.204 | 0.205 |     0.992x | 0.97-1.02 | 1.018 | 3 |   noise |
| scalar w01  | 0.286 | 0.295 |     0.969x | 0.95-0.99 | 1.003 | 3 |  slower |
| simd w02    | 0.107 | 0.112 |     0.952x | 0.95-0.99 | 1.010 | 3 |  slower |
| simd+d1 w02 | 0.198 | 0.203 |     0.978x | 0.97-0.99 | 0.947 | 3 |   noise |
| scalar w02  | 0.680 | 0.685 |     0.993x | 0.99-1.02 | 0.973 | 3 |   noise |
| simd w03    | 0.108 | 0.105 |     1.026x | 0.97-1.05 | 0.976 | 3 |   noise |
| simd+d1 w03 | 0.202 | 0.203 |     0.996x | 0.97-1.04 | 1.006 | 3 |   noise |
| scalar w03  |  1.12 |  1.11 |     1.011x | 1.01-1.05 | 1.022 | 3 |   noise |
| simd w04    | 0.112 | 0.110 |     1.014x | 1.01-1.06 | 1.053 | 3 |   noise |
| simd+d1 w04 | 0.203 | 0.197 |     1.020x | 1.01-1.03 | 1.037 | 3 |   noise |
| scalar w04  | 0.641 | 0.645 |     0.987x | 0.97-1.00 | 1.013 | 3 |   noise |
| simd w05    | 0.110 | 0.112 |     0.977x | 0.96-1.02 | 1.020 | 3 |   noise |
| simd+d1 w05 | 0.206 | 0.208 |     0.983x | 0.97-0.99 | 0.998 | 3 |   noise |
| scalar w05  |  1.14 |  1.14 |     1.000x | 0.97-1.03 | 0.977 | 3 |   noise |
| simd w06    | 0.112 | 0.113 |     1.020x | 0.97-1.05 | 0.991 | 3 |   noise |
| simd+d1 w06 | 0.203 | 0.203 |     1.002x | 0.99-1.03 | 0.974 | 3 |   noise |
| scalar w06  |  1.22 |  1.20 |     1.012x | 1.01-1.02 | 0.988 | 3 |   noise |
| simd w07    | 0.117 | 0.113 |     1.052x | 0.95-1.06 | 1.020 | 3 |   noise |
| simd+d1 w07 | 0.216 | 0.206 |     1.043x | 1.02-1.05 | 1.050 | 3 |   noise |
| scalar w07  |  1.20 |  1.18 |     1.012x | 1.01-1.05 | 1.012 | 3 |   noise |
| simd w08    | 0.117 | 0.119 |     0.979x | 0.95-1.00 | 1.027 | 3 |   noise |
| simd+d1 w08 | 0.224 | 0.228 |     0.987x | 0.97-0.99 | 1.007 | 3 |   noise |
| scalar w08  | 0.730 | 0.746 |     0.978x | 0.96-0.99 | 1.000 | 3 |   noise |
| simd w09    | 0.115 | 0.118 |     0.972x | 0.94-1.03 | 0.961 | 3 |   noise |
| simd+d1 w09 | 0.209 | 0.216 |     0.969x | 0.96-0.99 | 0.975 | 3 |  slower |
| scalar w09  |  1.04 |  1.05 |     1.000x | 0.99-1.00 | 0.969 | 3 |   noise |
| simd w10    | 0.119 | 0.115 |     0.962x | 0.96-1.04 | 1.025 | 3 |   noise |
| simd+d1 w10 | 0.216 | 0.208 |     1.036x | 1.02-1.05 | 1.028 | 3 |   noise |
| scalar w10  |  1.09 |  1.05 |     1.033x | 1.03-1.04 | 1.011 | 3 |   noise |
| simd w11    | 0.124 | 0.118 |     1.029x | 1.00-1.06 | 1.033 | 3 |   noise |
| simd+d1 w11 | 0.217 | 0.217 |     1.002x | 0.98-1.03 | 1.017 | 3 |   noise |
| scalar w11  |  1.09 |  1.11 |     0.978x | 0.97-0.99 | 0.989 | 3 |   noise |
| simd w12    | 0.119 | 0.121 |     0.975x | 0.96-0.98 | 0.950 | 3 |   noise |
| simd+d1 w12 | 0.208 | 0.209 |     0.994x | 0.95-1.00 | 0.971 | 3 |   noise |
| scalar w12  |  1.04 |  1.06 |     0.979x | 0.98-0.99 | 0.958 | 3 |   noise |
| simd w13    | 0.122 | 0.120 |     1.016x | 0.97-1.02 | 0.974 | 3 |   noise |
| simd+d1 w13 | 0.221 | 0.219 |     1.011x | 1.00-1.03 | 1.000 | 3 |   noise |
| scalar w13  |  1.14 |  1.11 |     1.011x | 1.00-1.02 | 1.011 | 3 |   noise |
| simd w14    | 0.125 | 0.119 |     1.045x | 0.99-1.08 | 1.037 | 3 |   noise |
| simd+d1 w14 | 0.220 | 0.218 |     1.009x | 0.97-1.05 | 1.022 | 3 |   noise |
| scalar w14  |  1.14 |  1.12 |     1.023x | 0.97-1.03 | 1.023 | 3 |   noise |
| simd w15    | 0.123 | 0.130 |     0.945x | 0.93-1.02 | 0.993 | 3 |  slower |
| simd+d1 w15 | 0.216 | 0.225 |     0.973x | 0.95-0.98 | 0.994 | 3 |  slower |
| scalar w15  |  1.16 |  1.15 |     1.000x | 0.99-1.02 | 1.012 | 3 |   noise |
| simd w16    | 0.122 | 0.126 |     0.974x | 0.94-0.99 | 0.960 | 3 |   noise |
| simd+d1 w16 | 0.221 | 0.222 |     1.002x | 0.99-1.01 | 1.022 | 3 |   noise |
| scalar w16  | 0.303 | 0.300 |     1.006x | 1.00-1.02 | 1.036 | 3 |   noise |
| simd w17    | 0.131 | 0.122 |     1.018x | 0.97-1.07 | 1.004 | 3 |   noise |
| simd+d1 w17 | 0.228 | 0.224 |     1.025x | 1.00-1.04 | 1.018 | 3 |   noise |
| scalar w17  |  1.22 |  1.16 |     1.037x | 1.00-1.05 | 1.024 | 3 |   noise |
| simd w18    | 0.126 | 0.130 |     0.971x | 0.92-1.02 | 1.005 | 3 |  slower |
| simd+d1 w18 | 0.227 | 0.228 |     0.993x | 0.96-1.00 | 1.020 | 3 |   noise |
| scalar w18  |  1.16 |  1.20 |     0.965x | 0.96-0.97 | 0.965 | 3 |   noise |
| simd w19    | 0.128 | 0.131 |     0.953x | 0.92-0.99 | 0.982 | 3 |   noise |
| simd+d1 w19 | 0.228 | 0.232 |     0.986x | 0.98-1.00 | 0.973 | 3 |   noise |
| scalar w19  |  1.20 |  1.20 |     1.000x | 0.96-1.04 | 0.976 | 3 |   noise |
| simd w20    | 0.131 | 0.133 |     0.988x | 0.99-1.01 | 1.021 | 3 |   noise |
| simd+d1 w20 | 0.225 | 0.220 |     1.023x | 1.00-1.03 | 1.016 | 3 |   noise |
| scalar w20  |  1.19 |  1.18 |     1.012x | 1.01-1.05 | 1.024 | 3 |   noise |
| simd w21    | 0.133 | 0.133 |     0.999x | 0.96-1.07 | 1.016 | 3 |   noise |
| simd+d1 w21 | 0.238 | 0.236 |     0.998x | 0.99-1.03 | 1.028 | 3 |   noise |
| scalar w21  |  1.25 |  1.27 |     0.988x | 0.98-1.00 | 1.012 | 3 |   noise |
| simd w22    | 0.129 | 0.134 |     0.969x | 0.90-0.98 | 0.981 | 3 |  slower |
| simd+d1 w22 | 0.230 | 0.243 |     0.947x | 0.94-1.01 | 0.966 | 3 |  slower |
| scalar w22  |  1.22 |  1.25 |     0.976x | 0.94-1.01 | 0.976 | 3 |  slower |
| simd w23    | 0.131 | 0.136 |     0.972x | 0.97-1.02 | 0.997 | 3 |   noise |
| simd+d1 w23 | 0.236 | 0.241 |     0.976x | 0.97-1.03 | 0.977 | 3 |   noise |
| scalar w23  |  1.30 |  1.27 |     1.013x | 1.00-1.03 | 1.013 | 3 |   noise |
| simd w24    | 0.136 | 0.139 |     0.970x | 0.96-1.00 | 1.016 | 3 |  slower |
| simd+d1 w24 | 0.226 | 0.230 |     0.984x | 0.97-1.04 | 1.027 | 3 |   noise |
| scalar w24  |  1.19 |  1.20 |     0.988x | 0.99-1.00 | 1.012 | 3 |   noise |
| simd w25    | 0.135 | 0.143 |     0.942x | 0.87-0.98 | 0.991 | 3 |  slower |
| simd+d1 w25 | 0.243 | 0.246 |     0.960x | 0.94-1.00 | 0.967 | 3 |   noise |
| scalar w25  |  1.33 |  1.32 |     1.000x | 0.99-1.01 | 1.000 | 3 |   noise |
| simd w26    | 0.132 | 0.142 |     0.931x | 0.92-1.03 | 0.955 | 3 |  slower |
| simd+d1 w26 | 0.235 | 0.239 |     0.984x | 0.95-1.00 | 0.944 | 3 |   noise |
| scalar w26  |  1.28 |  1.30 |     1.000x | 0.96-1.00 | 0.987 | 3 |   noise |
| simd w27    | 0.140 | 0.138 |     1.021x | 1.00-1.05 | 1.025 | 3 |   noise |
| simd+d1 w27 | 0.249 | 0.248 |     1.005x | 1.00-1.05 | 1.035 | 3 |   noise |
| scalar w27  |  1.33 |  1.37 |     0.986x | 0.96-1.01 | 1.000 | 3 |   noise |
| simd w28    | 0.143 | 0.142 |     1.006x | 0.97-1.03 | 1.030 | 3 |   noise |
| simd+d1 w28 | 0.238 | 0.246 |     0.955x | 0.95-0.98 | 0.988 | 3 |  slower |
| scalar w28  |  1.30 |  1.32 |     0.987x | 0.97-1.00 | 0.987 | 3 |   noise |
| simd w29    | 0.142 | 0.145 |     0.980x | 0.98-0.98 | 1.001 | 3 |   noise |
| simd+d1 w29 | 0.246 | 0.253 |     0.971x | 0.96-1.01 | 0.982 | 3 |   noise |
| scalar w29  |  1.35 |  1.39 |     1.013x | 0.97-1.01 | 0.987 | 3 |   noise |
| simd w30    | 0.146 | 0.143 |     1.030x | 1.02-1.06 | 1.044 | 3 |   noise |
| simd+d1 w30 | 0.257 | 0.253 |     1.031x | 1.00-1.07 | 1.037 | 3 |   noise |
| scalar w30  |  1.37 |  1.37 |     1.014x | 0.99-1.01 | 1.014 | 3 |   noise |
| simd w31    | 0.148 | 0.150 |     0.975x | 0.96-1.02 | 1.033 | 3 |   noise |
| simd+d1 w31 | 0.256 | 0.257 |     0.995x | 0.97-1.01 | 1.020 | 3 |   noise |
| scalar w31  |  1.39 |  1.43 |     0.959x | 0.92-1.01 | 0.986 | 3 |   noise |
| simd w32    | 0.146 | 0.150 |     0.960x | 0.95-1.00 | 0.999 | 3 |  slower |
| simd+d1 w32 | 0.198 | 0.199 |     1.002x | 0.98-1.02 | 0.969 | 3 |   noise |
| scalar w32  | 0.314 | 0.313 |     1.003x | 0.98-1.01 | 0.978 | 3 |   noise |

runs: START 3, HEAD 3, A/A 3; a ratio above 1 means HEAD is faster
geomean 0.994 over 96 rows (min 0.931 simd w26; max 1.052 simd w07)
per-run geomean: min 0.990, median 0.997, max 0.998 over 3 runs
A/A geomean 1.001

`bitpack_unpack_alias 5 32`, 3 rounds, same hold:

| row                        | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| alias unpack w05           | 0.111 | 0.113 |     0.987x | 0.94-0.99 | 0.989 | 3 |   noise |
| alias unpack w32           | 0.142 | 0.145 |     0.978x | 0.98-1.01 | 0.989 | 3 |   noise |
| alias memcpy w32 (control) | 0.117 | 0.119 |     0.962x | 0.96-1.02 | 0.980 | 3 |   noise |

runs: START 3, HEAD 3, A/A 3; a ratio above 1 means HEAD is faster
geomean 0.976 over 3 rows (min 0.962 alias memcpy w32 (control); max 0.987 alias unpack w05)
per-run geomean: min 0.959, median 0.975, max 1.004 over 3 runs
A/A geomean 0.986

Geomean over the 98 library rows: **0.993** (the 96 `bitpack_bench` rows alone: 0.994; true ratio 1.000 by construction). 10 of the 96 bench rows read below 0.97 outside the A/A band (worst 0.931, `simd w26`), all of them noise between two runs of the same file: the A/A of 3 rounds is a poor bound on this machine under a load of 5-12 from other sessions.

uptime, i9 hold start / between the two benches / end:

Sun Nov  1 11:12:27 PST 2026  |  `11:12  up 30 days, 17:06, 5 users, load averages: 11.55 7.34 7.33`
Sun Nov  1 11:18:57 PST 2026  |  `11:18  up 30 days, 17:12, 5 users, load averages: 5.45 6.90 7.19`
Sun Nov  1 11:21:17 PST 2026  |  `11:21  up 30 days, 17:15, 5 users, load averages: 6.28 6.60 7.01`

## Rows below 0.97 outside the A/A spread

M4 (6 rows, reproduced in a second hold):

| row | ratio START/HEAD | cause |
|---|---:|---|
| scalar w18 | 0.815 | Code placement, not code. `unpack_scalar` is unchanged and its machine code is the same in both binaries: 33 of 33 `unpack_scalar<B>` instantiations have identical instruction streams in the START and HEAD bench binaries after normalizing addresses (`otool -tV`, `dis/cmp_kernels.py`); only the addresses move. The campaign's own before/after runs show the same shift (`perf/bitpack-unpack-loads/results-arm-final2`: scalar w18 2.03 integers/ns in the previous kernels' build, 1.66 in the new one). |
| scalar w20 | 0.827 | Same: identical code, different placement (campaign runs: 1.88 against 1.77). |
| scalar w24 | 0.851 | Same (campaign runs: 2.13 against 1.81). |
| scalar w08 | 0.903 | Same. |
| scalar w21 | 0.940 | Same. |
| simd w05 | 0.911 (hold 2: 0.844) | The one `unpack` row the CHANGELOG (2026-10-31) says does not follow the load-once kernel: "0.99x in the paired runs ... 0.92x in two later builds of the bench that contain the same width 5 kernel: the row moves with the layout of the binary, not with the kernel". The same width 5 kernel reads 1.029x faster (median over 64 input offsets) in `bitpack_unpack_alias` in this gate. |

`unpack_scalar` is the portable path: `unpack` runs it only without SSE2/NEON or with `BITPACK_NO_SIMD`, so on these two machines only a caller of `unpack_scalar` itself sees the five scalar rows.

The other 90 rows: `pack_simd` and `unpack_delta_simd` are identical in all 33 instantiations (their rows, `simd+d1`, read 0.988-1.009); the 30 `simd` rows at widths 1 to 31 other than w05 are 1.034x to 1.294x faster (width 31: 1.128x), and width 32 is 1.620x (the NEON `memcpy`; in `bitpack_unpack_alias` 1.690x).

i9: 10 rows read below 0.97 outside A/A (`scalar w01` 0.969, `simd w02` 0.952, `simd+d1 w09` 0.969, `simd w15` 0.945, `simd w22` 0.969, `simd+d1 w22` 0.947, `simd w25` 0.942, `simd w26` 0.931, `simd+d1 w28` 0.955, `simd w32` 0.960). The two binaries are the same bytes, so these are measurement noise, not a change; they count in the SUMMARY line because the rule counts rows, and they are explained.

## Rows dropped or not comparable

None dropped. `unpack` with `in == out` was never supported and at width 32 on NEON is now undefined (CHANGELOG 2026-10-31); the bench does not do it. Packed bytes and decoded values are unchanged (`test/differential.cc` compares HEAD against START's kernels), so the rows are comparable.

## Rig notes

- Light holds (builds) starved on both machines for over 15 minutes (a queue of 30 strict holds), so this repo's builds ran unheld at nice 19 after that wait; no timing was taken outside a hold except a smoke run of each binary before the first strict hold.
- One run of `bitpack_bench` has no knob and takes 43 s on the M4, so 3 rounds is what fits in a hold with the alias bench.

SUMMARY repo=bitpack m4_geomean=1.042 i9_geomean=0.993 m4_slow=6/0.815 i9_slow=10/0.931 unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 `scalar` widths 8, 18, 20, 21 and 24 (0.815 to 0.940): placement. `unpack_scalar` is
  unchanged and all 33 instantiations have identical machine code in both binaries.
- M4 `simd` width 5 (0.911, 0.844 in a second hold): placement. The same kernel reads 1.029 in
  `bitpack_unpack_alias`.
- i9, 10 rows from 0.931 to 0.969: noise. The i9 START and HEAD binaries are the same bytes.
