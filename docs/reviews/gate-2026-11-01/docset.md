# docset: START cd38597 to HEAD 2b503bd

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/docset#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`): `cd38597278bf2cd91a4f85d79247b856c3d77265`, 2026-10-22 04:39:23 -0700. HEAD is `origin/main` when the run started: `2b503bd18b3de28dbf300b708d3ab30e64d0a203`, 2026-11-01 08:03:51 -0800 (13 commits later). Measured 2026-11-01 by gate measurer g14a.

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64, NEON kernels), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja 1.13.2 |
| i9 | Intel i9-9980HK (8C/16T, x86-64, SSE4.2/AVX2/BMI1 kernels picked at run time), macOS 15.8.1, Apple clang 17.0.0 (clang-1700.6.4.2), CMake 4.4.4, Ninja 1.13.2 |

- Both sides: `/usr/bin/clang++`, `-DCMAKE_BUILD_TYPE=Release` (`-O3 -DNDEBUG`), C++20 from the target, no `-march`. docset is header-only: `docset.hh` is the only library file. `DOCSET_BENCH_REFERENCE` is off: no CRoaring is fetched or built.
- START tree = HEAD's tree (HEAD's `bench/`, `test/`, `CMakeLists.txt`) with only `docset.hh` replaced by START's. `git diff --cached --stat HEAD` of the START tree: `docset.hh | 377 +++---- 1 file changed, 59 insertions(+), 318 deletions(-)`. No dependencies.
- Bench: HEAD's `bench/ab_bench.cc`, built as `docset_ab_new` once against START's `docset.hh` (A) and once against HEAD's (B); universe 2^22 (the default), 52 rows: AND, OR and ANDNOT over ten density pairs (30 rows, each timed over a pool of 16 or 4 random inputs, so the branch predictor cannot memorize one input), AND and ANDNOT of two bitmaps with 20 to 400 members per chunk in the result (10 rows), iteration (4 rows) and point `test()` (8 rows). The bitmap-result rows were added to `ab_bench.cc` after START but use only `docset::set` API that START has, so all 52 rows compile and run on both sides. Each row is the best of 15 windows of 20 ms.
- `test/docset_old.hh` is START's code: `diff <(git show cd38597:docset.hh) test/docset_old.hh` differs in the `namespace` line and one comment line. It was not used as a stand-in; both binaries are built from the same `ab_bench.cc` source with the overlay, which keeps the code layout closer than a binary holding both versions.
- Each round runs A (START binary), B (HEAD binary), then A again (the A/A control) through `ab_compare.py run`, in one `quiet strict` hold (strict acts as exclusive on macOS). Ratio = START time / HEAD time: above 1 means HEAD is faster; range = min-max over the paired rounds; A/A is the median ratio of START against START again.

## Commands

```sh
# M4: $GATE (clones in src/<repo>); i9: $GATE/docset (the clone, trees in .g/)
git worktree add --detach docset/head  2b503bd18b3de28dbf300b708d3ab30e64d0a203
git worktree add --detach docset/start 2b503bd18b3de28dbf300b708d3ab30e64d0a203
(cd docset/start && git rm -rq -- docset.hh && git checkout cd38597278bf2cd91a4f85d79247b856c3d77265 -- docset.hh)
for s in head start; do
  cmake -S docset/$s -B docset/$s/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++
  cmake --build docset/$s/build --target docset_ab_new -j4
done
# one hold per machine, 5 rounds (one run is 19 s on the M4, 22 s on the i9)
quiet strict 10 "gate docset A/B/A (ab_bench)" -- ./run.sh m4 5
quiet strict 10 "gate docset A/B/A (ab_bench)" -- ./run.sh i9 5
quiet strict 10 "gate docset confirm: ab_bench second hold" -- ./run2.sh m4 5   # M4 only
#   run.sh: ab_compare.py run --rounds 5 --regex '^(?P<row>\S.*?)\s+(?P<value>[0-9.]+)$' --label-a START --label-b HEAD docset_ab_new.start docset_ab_new.head
```

Raw outputs: `$GATE/raw/docset/{m4,i9,m4-confirm}/` (`save/` holds each run's output). Scripts: `$GATE/docset/`.

## M4 (Apple M4 Pro)

M4 hold, 5 rounds:

| row                                   |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| and d=0.001 x 0.001                   |  5514.4 |  5447.9 |     1.013x | 0.99-1.02 | 1.002 | 5 |   noise |
| or d=0.001 x 0.001                    | 18758.2 |  8483.0 |     2.201x | 2.20-2.22 | 1.005 | 5 |  faster |
| andnot d=0.001 x 0.001                |  3952.3 |  3590.7 |     1.101x | 1.10-1.11 | 0.999 | 5 |  faster |
| and d=0.01 x 0.01                     | 48774.6 | 48863.5 |     0.991x | 0.99-1.01 | 0.996 | 5 |  slower |
| or d=0.01 x 0.01                      |  165700 | 59590.5 |     2.777x | 2.74-2.82 | 1.003 | 5 |  faster |
| andnot d=0.01 x 0.01                  | 69477.2 | 46136.5 |     1.504x | 1.49-1.54 | 0.998 | 5 |  faster |
| and d=0.031 x 0.031                   |  143312 |  144026 |     0.996x | 0.98-1.00 | 0.999 | 5 |   noise |
| or d=0.031 x 0.031                    |  521451 |  266953 |     1.954x | 1.92-1.99 | 0.998 | 5 |  faster |
| andnot d=0.031 x 0.031                |  233289 |  146314 |     1.580x | 1.56-1.60 | 0.999 | 5 |  faster |
| and d=0.07 x 0.07                     |  109236 | 55651.4 |     1.981x | 1.91-2.01 | 0.972 | 5 |  faster |
| or d=0.07 x 0.07                      | 17035.1 | 14112.0 |     1.208x | 0.99-1.22 | 0.998 | 5 |  faster |
| andnot d=0.07 x 0.07                  | 17261.3 | 15169.9 |     1.139x | 1.03-1.15 | 0.993 | 5 |  faster |
| and d=0.1 x 0.1                       |  217101 | 64906.1 |     3.359x | 3.29-3.46 | 1.005 | 5 |  faster |
| or d=0.1 x 0.1                        | 16804.3 | 17099.6 |     0.984x | 0.98-0.99 | 1.007 | 5 |   noise |
| andnot d=0.1 x 0.1                    | 16936.2 | 16800.8 |     1.008x | 0.99-1.02 | 0.996 | 5 |   noise |
| and d=0.2 x 0.2                       |  370670 |  122530 |     3.034x | 2.89-3.06 | 0.982 | 5 |  faster |
| or d=0.2 x 0.2                        | 17162.2 | 17016.5 |     1.012x | 0.99-1.01 | 1.003 | 5 |  faster |
| andnot d=0.2 x 0.2                    | 16902.9 | 16709.3 |     1.018x | 0.97-1.05 | 0.997 | 5 |   noise |
| and d=0.25 x 0.25                     |  244681 |  177132 |     1.376x | 1.30-1.45 | 0.977 | 5 |  faster |
| or d=0.25 x 0.25                      | 16802.4 | 17064.2 |     0.980x | 0.98-1.00 | 1.003 | 5 |   noise |
| andnot d=0.25 x 0.25                  | 16910.5 | 16786.4 |     1.008x | 0.98-1.01 | 0.999 | 5 |   noise |
| and d=0.1 x 0.9                       | 17024.4 | 16737.9 |     1.019x | 0.98-1.03 | 0.996 | 5 |   noise |
| or d=0.1 x 0.9                        | 17065.8 | 16830.3 |     1.019x | 1.00-1.03 | 0.990 | 5 |   noise |
| andnot d=0.1 x 0.9                    |  213609 | 64628.4 |     3.342x | 3.21-3.43 | 0.980 | 5 |  faster |
| and d=0.5 x 0.5                       | 16938.7 | 16997.8 |     0.995x | 0.99-1.01 | 0.995 | 5 |   noise |
| or d=0.5 x 0.5                        | 16739.4 | 16992.7 |     0.979x | 0.96-1.01 | 0.992 | 5 |   noise |
| andnot d=0.5 x 0.5                    | 16940.2 | 16786.7 |     1.006x | 1.00-1.03 | 0.991 | 5 |   noise |
| and d=0.9 x 0.9                       | 16725.3 | 16477.5 |     1.018x | 1.00-1.03 | 0.993 | 5 |   noise |
| or d=0.9 x 0.9                        | 17142.8 | 16844.3 |     1.017x | 1.01-1.03 | 1.001 | 5 |   noise |
| andnot d=0.9 x 0.9                    | 16864.5 | 16621.6 |     1.012x | 1.00-1.05 | 1.007 | 5 |   noise |
| and bitmaps, 20 members per chunk     | 40045.6 | 41810.2 |     0.955x | 0.95-0.96 | 0.996 | 5 |  slower |
| andnot bitmaps, 20 members per chunk  | 42021.1 | 42146.2 |     0.996x | 0.99-1.00 | 0.999 | 5 |   noise |
| and bitmaps, 40 members per chunk     | 43406.3 | 51472.4 |     0.843x | 0.84-0.86 | 1.001 | 5 |  slower |
| andnot bitmaps, 40 members per chunk  | 46231.9 | 51081.5 |     0.900x | 0.89-0.91 | 0.997 | 5 |  slower |
| and bitmaps, 80 members per chunk     | 48138.7 | 52341.5 |     0.919x | 0.91-0.93 | 0.988 | 5 |  slower |
| andnot bitmaps, 80 members per chunk  | 52629.2 | 51933.5 |     1.012x | 0.99-1.02 | 1.004 | 5 |   noise |
| and bitmaps, 160 members per chunk    | 66483.1 | 53614.2 |     1.245x | 1.16-1.27 | 1.025 | 5 |  faster |
| andnot bitmaps, 160 members per chunk | 66633.6 | 53005.5 |     1.251x | 1.21-1.27 | 0.996 | 5 |  faster |
| and bitmaps, 400 members per chunk    |  132041 | 56733.8 |     2.322x | 2.24-2.41 | 0.992 | 5 |  faster |
| andnot bitmaps, 400 members per chunk |  130896 | 56433.2 |     2.336x | 2.30-2.39 | 0.996 | 5 |  faster |
| iterate d=0.001                       |   681.8 |   685.6 |     0.993x | 0.96-1.02 | 0.997 | 5 |   noise |
| iterate d=0.01                        |  2772.0 |  2754.8 |     1.004x | 1.00-1.01 | 1.005 | 5 |   noise |
| iterate d=0.1                         |  471292 |  469156 |     1.005x | 0.99-1.05 | 1.007 | 5 |   noise |
| iterate d=0.5                         | 1547635 | 1549606 |     1.001x | 0.98-1.03 | 0.996 | 5 |   noise |
| test d=0.001 (ns/probe)               |    16.6 |    14.1 |     1.176x | 1.14-1.18 | 0.994 | 5 |  faster |
| test d=0.01 (ns/probe)                |    28.5 |    13.4 |     2.120x | 2.10-2.15 | 0.993 | 5 |  faster |
| test d=0.03 (ns/probe)                |    27.4 |    17.3 |     1.590x | 1.57-1.62 | 0.996 | 5 |  faster |
| test d=0.1 (ns/probe)                 |    5.70 |    3.40 |     1.676x | 1.65-1.68 | 1.000 | 5 |  faster |
| test d=0.5 (ns/probe)                 |    5.70 |    3.40 |     1.676x | 1.68-1.68 | 1.000 | 5 |  faster |
| test 1 chunk, 8 members (ns/probe)    |    3.40 |    2.20 |     1.500x | 1.42-1.64 | 1.000 | 5 |  faster |
| test 1 chunk, 4096 array (ns/probe)   |    12.6 |    7.20 |     1.750x | 1.73-1.76 | 1.000 | 5 |  faster |
| test 65536 chunks x 1 (ns/probe)      |    38.6 |    26.0 |     1.485x | 1.48-1.51 | 1.005 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.306 over 52 rows (min 0.843 and bitmaps, 40 members per chunk; max 3.359 and d=0.1 x 0.1)
per-run geomean: min 1.297, median 1.305, max 1.309 over 5 runs
A/A geomean 0.997

Geomean: **1.306** over 52 rows. Rows below 0.97 outside the A/A spread: 4, worst 0.843 (below). The second hold (M4 hold b, 5 rounds, load 7-10; full table in `$GATE/raw/docset/m4-confirm/ab.md`) gives geomean 1.301, the same four rows below 0.97 (0.954, 0.829, 0.898, 0.913) and no other.

uptime, M4 hold start / end, M4 hold b start / end:

Sun Nov  1 11:41:24 PST 2026  |  `11:41  up 5 days, 17:06, 14 users, load averages: 10.35 12.74 12.60`
Sun Nov  1 11:46:02 PST 2026  |  `11:46  up 5 days, 17:11, 14 users, load averages: 9.46 10.60 11.62`
Sun Nov  1 12:24:01 PST 2026  |  `12:24  up 5 days, 17:49, 14 users, load averages: 7.26 7.21 7.93`
Sun Nov  1 12:28:40 PST 2026  |  `12:28  up 5 days, 17:53, 14 users, load averages: 10.43 7.68 7.84`

The CHANGELOG (2026-11-01) says `or` and `andnot` at density 0.07 and `test` of an 8-member chunk swing by 10 to 17 percent from run to run of the same two binaries on the M4; here those rows read 1.21, 1.14 and 1.50 with ranges up to 0.99-1.22 (`or d=0.07`), all on the faster side.

## i9 (Intel i9-9980HK)

i9 hold, 5 rounds:

| row                                   |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| and d=0.001 x 0.001                   |  7576.1 |  7307.9 |     1.037x | 0.97-1.10 | 1.036 | 5 |   noise |
| or d=0.001 x 0.001                    | 21359.9 | 17500.0 |     1.220x | 1.17-1.28 | 1.003 | 5 |  faster |
| andnot d=0.001 x 0.001                | 10063.7 |  9067.4 |     1.114x | 1.06-1.14 | 0.998 | 5 |  faster |
| and d=0.01 x 0.01                     | 42269.2 | 39062.6 |     1.061x | 1.03-1.12 | 1.021 | 5 |  faster |
| or d=0.01 x 0.01                      | 78007.4 | 61892.2 |     1.241x | 1.19-1.27 | 1.031 | 5 |  faster |
| andnot d=0.01 x 0.01                  | 43911.7 | 37556.7 |     1.167x | 1.14-1.25 | 1.015 | 5 |  faster |
| and d=0.031 x 0.031                   |  121104 |  118588 |     0.999x | 0.95-1.17 | 1.035 | 5 |   noise |
| or d=0.031 x 0.031                    |  334717 |  316286 |     1.055x | 1.01-1.25 | 1.003 | 5 |   noise |
| andnot d=0.031 x 0.031                |  118711 | 99277.2 |     1.178x | 1.13-1.44 | 0.962 | 5 |  faster |
| and d=0.07 x 0.07                     |  223813 |  137110 |     1.600x | 1.54-1.70 | 1.012 | 5 |  faster |
| or d=0.07 x 0.07                      | 36956.7 | 39121.6 |     0.945x | 0.94-1.00 | 0.978 | 5 |   noise |
| andnot d=0.07 x 0.07                  | 38585.3 | 39266.7 |     0.983x | 0.93-1.05 | 1.008 | 5 |   noise |
| and d=0.1 x 0.1                       |  331396 |  145880 |     2.306x | 2.14-2.43 | 0.946 | 5 |  faster |
| or d=0.1 x 0.1                        | 37443.6 | 37859.7 |     1.000x | 0.89-1.13 | 0.993 | 5 |   noise |
| andnot d=0.1 x 0.1                    | 38673.1 | 37643.0 |     1.011x | 0.92-1.15 | 1.077 | 5 |   noise |
| and d=0.2 x 0.2                       |  544699 |  277715 |     1.929x | 1.84-2.08 | 1.008 | 5 |  faster |
| or d=0.2 x 0.2                        | 37210.8 | 38913.8 |     0.969x | 0.91-1.08 | 0.991 | 5 |   noise |
| andnot d=0.2 x 0.2                    | 38262.8 | 36946.0 |     0.998x | 0.96-1.06 | 1.013 | 5 |   noise |
| and d=0.25 x 0.25                     |  365609 |  316114 |     1.203x | 1.10-1.22 | 0.994 | 5 |  faster |
| or d=0.25 x 0.25                      | 38245.2 | 37591.2 |     0.994x | 0.97-1.18 | 0.974 | 5 |   noise |
| andnot d=0.25 x 0.25                  | 37926.6 | 37538.1 |     1.002x | 0.94-1.13 | 0.927 | 5 |   noise |
| and d=0.1 x 0.9                       | 38139.9 | 38524.1 |     1.002x | 0.95-1.05 | 1.004 | 5 |   noise |
| or d=0.1 x 0.9                        | 37786.8 | 37503.2 |     0.996x | 0.87-1.03 | 0.994 | 5 |   noise |
| andnot d=0.1 x 0.9                    |  336893 |  143790 |     2.280x | 2.25-2.43 | 0.969 | 5 |  faster |
| and d=0.5 x 0.5                       | 38973.2 | 38207.8 |     1.023x | 0.91-1.16 | 1.057 | 5 |   noise |
| or d=0.5 x 0.5                        | 38774.1 | 37553.4 |     1.033x | 0.95-1.08 | 1.017 | 5 |   noise |
| andnot d=0.5 x 0.5                    | 37954.8 | 36729.1 |     1.024x | 0.97-1.05 | 1.029 | 5 |   noise |
| and d=0.9 x 0.9                       | 39012.7 | 38505.7 |     1.013x | 0.94-1.07 | 1.015 | 5 |   noise |
| or d=0.9 x 0.9                        | 37719.6 | 37890.6 |     1.011x | 0.99-1.06 | 1.010 | 5 |   noise |
| andnot d=0.9 x 0.9                    | 37338.5 | 39144.3 |     0.975x | 0.92-0.99 | 1.006 | 5 |   noise |
| and bitmaps, 20 members per chunk     | 61189.4 | 74516.0 |     0.819x | 0.80-0.90 | 0.974 | 5 |  slower |
| andnot bitmaps, 20 members per chunk  | 73710.9 | 72611.8 |     1.002x | 0.96-1.02 | 1.002 | 5 |   noise |
| and bitmaps, 40 members per chunk     | 74917.7 | 81537.7 |     0.930x | 0.88-0.95 | 0.990 | 5 |  slower |
| andnot bitmaps, 40 members per chunk  | 82818.3 | 82347.4 |     1.004x | 0.95-1.07 | 1.002 | 5 |   noise |
| and bitmaps, 80 members per chunk     |  101130 | 97832.8 |     1.000x | 0.94-1.08 | 0.981 | 5 |   noise |
| andnot bitmaps, 80 members per chunk  | 99431.4 | 99631.7 |     0.986x | 0.98-1.07 | 1.006 | 5 |   noise |
| and bitmaps, 160 members per chunk    |  151091 |  138568 |     1.095x | 1.02-1.14 | 0.990 | 5 |   noise |
| andnot bitmaps, 160 members per chunk |  144795 |  135179 |     1.042x | 0.95-1.09 | 1.031 | 5 |   noise |
| and bitmaps, 400 members per chunk    |  257980 |  139628 |     1.874x | 1.71-1.91 | 1.005 | 5 |  faster |
| andnot bitmaps, 400 members per chunk |  248582 |  137388 |     1.799x | 1.74-1.93 | 0.988 | 5 |  faster |
| iterate d=0.001                       |  1121.3 |  1112.0 |     1.008x | 0.98-1.05 | 1.007 | 5 |   noise |
| iterate d=0.01                        | 10793.4 | 10758.6 |     1.001x | 0.97-1.01 | 0.981 | 5 |   noise |
| iterate d=0.1                         |  728121 |  717839 |     1.020x | 0.99-1.05 | 1.001 | 5 |   noise |
| iterate d=0.5                         | 1805728 | 1823835 |     0.995x | 0.98-1.00 | 0.997 | 5 |   noise |
| test d=0.001 (ns/probe)               |    23.7 |    22.1 |     1.071x | 1.03-1.09 | 1.009 | 5 |  faster |
| test d=0.01 (ns/probe)                |    38.9 |    23.7 |     1.601x | 1.60-1.67 | 1.013 | 5 |  faster |
| test d=0.03 (ns/probe)                |    42.8 |    29.8 |     1.436x | 1.41-1.46 | 0.961 | 5 |  faster |
| test d=0.1 (ns/probe)                 |    10.8 |    9.70 |     1.104x | 1.10-1.20 | 1.000 | 5 |  faster |
| test d=0.5 (ns/probe)                 |    10.8 |    9.60 |     1.110x | 1.06-1.14 | 1.019 | 5 |  faster |
| test 1 chunk, 8 members (ns/probe)    |    8.60 |    6.10 |     1.426x | 1.39-1.47 | 1.023 | 5 |  faster |
| test 1 chunk, 4096 array (ns/probe)   |    23.0 |    15.6 |     1.484x | 1.45-1.53 | 1.000 | 5 |  faster |
| test 65536 chunks x 1 (ns/probe)      |    57.1 |    48.0 |     1.167x | 1.13-1.22 | 0.984 | 5 |  faster |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.145 over 52 rows (min 0.819 and bitmaps, 20 members per chunk; max 2.306 and d=0.1 x 0.1)
per-run geomean: min 1.143, median 1.149, max 1.155 over 5 runs
A/A geomean 1.001

Geomean: **1.145** over 52 rows. Rows below 0.97 outside the A/A spread: 2, worst 0.819 (below). Two more rows read below 0.97 inside the A/A band (`or d=0.07 x 0.07` 0.945, `or d=0.2 x 0.2` 0.969).

uptime, i9 hold start / end:

Sun Nov  1 10:45:21 PST 2026  |  `10:45  up 30 days, 16:39, 5 users, load averages: 9.37 8.31 7.79`
Sun Nov  1 10:50:45 PST 2026  |  `10:50  up 30 days, 16:44, 5 users, load averages: 8.72 7.78 7.61`

The i9 carried a load of 8-9 from other sessions (strict does not pin cores on macOS). Its noise is wide: the A/A ratios reach 0.927 and 1.077 on single rows, and the identical-binary control of the bitpack gate on this machine spread by 0.93-1.05 per row in 3 rounds. The dense OR, ANDNOT, AND and iteration rows (density 0.07 and above) run code that did not change and read 0.94-1.06 here.

## Rows below 0.97 outside the A/A spread

M4 (4 rows; the same four in both holds):

| row | hold 1 | hold 2 | cause |
|---|---:|---:|---|
| and bitmaps, 40 members per chunk | 0.843 | 0.829 | HEAD takes the branch-free extraction above `extract_loop_max` = 32 members on arm64 (`pick_extract_form`, CHANGELOG 2026-11-01); START's per-word loop is the same loop HEAD still uses up to 32. The limit comes from `micro_extract`'s isolated crossover (39-43 members on the M4). End to end the START loop is still ahead at 40 and 80 members per chunk and behind from 160 (1.245x), so the crossover of this bench lies between 80 and 160. The CHANGELOG gives M4 end-to-end numbers only for 20 members against the previous header, not for these rows. |
| andnot bitmaps, 40 members per chunk | 0.900 | 0.898 | Same. |
| and bitmaps, 80 members per chunk | 0.919 | 0.913 | Same. `andnot` at 80 members reads 1.012 and 1.021, so the loss is not uniform across the pair. |
| and bitmaps, 20 members per chunk | 0.955 | 0.954 | HEAD runs the same plain loop as START at this size, but the conversion moved out of line (`container::fill_array`, `noinline`, `resize(card + 2)`, then `resize(card)`, behind `extract_bits`): the CHANGELOG (`511c575`) keeps it out of line so that the dense path of `intersect` and `subtract` stays small (ANDNOT of two arrays at density 0.03 was 7 percent slower with it inlined). About 28 ns per chunk, 4.5 percent here. `andnot` at 20 members reads 1.00 through the same call. |

The wins on the same rows from 160 members up (1.25x, 2.3x at 400) and the 20-member row of the CHANGELOG (1.23x on the M4) are against the previous header, which took the branch-free form at every size; against START the 20 to 80 member rows are the ones the loop of START served well.

i9 (2 rows, both also slower on the M4):

| row | ratio | cause |
|---|---:|---|
| and bitmaps, 20 members per chunk | 0.819 (0.80-0.90) | The out-of-line conversion, as on the M4, but its size is not explained: HEAD runs the same plain loop as START here (the x86-64 loop limit is 96), `andnot` at 20 members through the same `fill_array` reads 1.002, and START's own `and` row is 956 ns per chunk against 1152 for its `andnot` row (HEAD: 1164 and 1135). Unexplained. |
| and bitmaps, 40 members per chunk | 0.930 (0.88-0.95) | Same; `andnot` at 40 reads 1.004. Unexplained. |

The CHANGELOG says "no row on the i9 is more than 2% slower" than the previous header; against START the two AND rows are slower.

## Rows dropped or not comparable

- Not run: `bench/bench.cc` (the CRoaring comparison; `DOCSET_BENCH_REFERENCE` stays off as the brief says), `bench/cmp_bench.cc` (AND, ANDNOT and `test()` against `test/docset_old.hh` in one binary; its rows are a subset of `ab_bench`'s) and `bench/micro_extract.cc` (it times `docset::detail::extract_*`, routines added after START, against variants of themselves; it has no START counterpart).
- No `ab_bench` row was dropped. Results are identical between the versions (`test/diff.cc` compares every operation with `test/docset_old.hh`), so the rows are comparable.

## Rig notes

- Light holds (builds) starved on both machines for over 15 minutes (a queue of 30 strict holds), so this repo's builds ran unheld at nice 19 after that wait; no timing was taken outside a hold except a smoke run of each binary before the first strict hold.
- The M4 hold started at a load of 10 (the strict wait for the load to settle ends after 10 minutes); the A/A geomean is 0.997.

SUMMARY repo=docset m4_geomean=1.306 i9_geomean=1.145 m4_slow=4/0.843 i9_slow=2/0.819 unexplained=2 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- AND of two bitmaps with 40 members per chunk (M4 0.843), 80 (M4 0.919), ANDNOT with 40 (M4
  0.900): above `extract_loop_max` (32 on arm64) head takes the branch-free extraction. Fix in
  progress.
- AND with 20 members per chunk (M4 0.955, i9 0.819) and 40 (i9 0.930): the array conversion moved
  out of line (`container::fill_array`), about 28 ns per chunk; the size on the i9 is unexplained.
  Fix in progress.
