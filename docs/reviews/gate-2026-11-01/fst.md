# fst: START 12657aa to HEAD 39245fa

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/fst#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

START is the last commit on `main` before 2026-10-30 (`git log --before=2026-10-30T00:00 -1 origin/main`): `12657aaaa1dc83db388f99df3eeb95d7cbc451bd`, 2026-10-22 04:39:36 -0700. HEAD is `origin/main` when the run started: `39245fa056a8c7d16fa79fa771b51b307b0ba572`, 2026-11-01 04:12:01 -0800 (18 commits later). Measured 2026-11-01 by gate measurer g14a.

## Setup

| machine | hardware, OS, toolchain |
|---|---|
| M4 | Apple M4 Pro (14C, arm64), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), CMake 4.4.5, Ninja 1.13.2 |
| i9 | Intel i9-9980HK (8C/16T, x86-64), macOS 15.8.1, Apple clang 17.0.0 (clang-1700.6.4.2), CMake 4.4.4, Ninja 1.13.2 |

- Both sides: `/usr/bin/clang++`, `-DCMAKE_BUILD_TYPE=Release` (`-O3 -DNDEBUG`), C++20 from the target, no `-march`. fst is header-only: `fst.hh` is the only library file.
- START tree = HEAD's tree (HEAD's `bench/`, `test/`, `CMakeLists.txt`) with only `fst.hh` replaced by START's. `git diff --cached --stat HEAD` of the START tree: `fst.hh | 329 ++++---- 1 file changed, 47 insertions(+), 282 deletions(-)`. No dependencies (no FetchContent).
- Bench: HEAD's `bench/cmp_bench.cc` (`fst_cmp_bench`: word-list rows and edge rows, 20 rows), `bench/bench.cc` (`fst_bench`: build rate, lookup p50 and block-index floor of the fst row, 3 rows) and `bench/build_rss.cc` (`fst_build_rss`, an extra). Corpus: `/usr/share/dict/words` (235,976 keys, sha256 `be41ad97...bbab9`, identical on both machines). Every HEAD bench source compiles and runs against START's `fst.hh`; no row was dropped.
- `fst_cmp_bench` prints a `new` column (the `fst::` code of the binary) next to an `old` column (the frozen reference `test/fst_old.hh`). `diff <(git show 12657aa:fst.hh) test/fst_old.hh` differs only in the `namespace` line and one comment line, so `old` is START's code. The ratios below are cross-binary: the `new` column of the START binary (A) against the `new` column of the HEAD binary (B), through a wrapper (`fstw.py`) that prints only that column. The HEAD binary's own in-process `old/new` ratio is a cross-check below. `fst_build_rss.start` reports builder/reference 1.00x at every size, which also shows `fst_old.hh` is START.
- Each round runs A (START binary), B (HEAD binary), then A again (the A/A control) through `ab_compare.py run`, in one `quiet strict` hold (strict acts as exclusive on macOS). Ratio = START time / HEAD time: above 1 means HEAD is faster; range = min-max over the paired rounds; A/A is the median ratio of START against START again.

## Commands

```sh
# M4: $GATE (clones in src/<repo>); i9: $GATE/fst (the clone, trees in .g/)
git worktree add --detach fst/head  39245fa056a8c7d16fa79fa771b51b307b0ba572
git worktree add --detach fst/start 39245fa056a8c7d16fa79fa771b51b307b0ba572
(cd fst/start && git rm -rq -- fst.hh && git checkout 12657aaaa1dc83db388f99df3eeb95d7cbc451bd -- fst.hh)
for s in head start; do
  cmake -S fst/$s -B fst/$s/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++
  cmake --build fst/$s/build --target fst_cmp_bench fst_bench fst_build_rss -j4
done
# M4, one hold: M4 hold (3 rounds of cmp_bench, then 5 rounds of fst_bench)
quiet strict 10 "gate fst A/B/A" -- ./run.sh m4 3 m4 "" 5
#   = ab_compare.py run --rounds 3 --format unit --label-a START --label-b HEAD A B -- /usr/share/dict/words
#   = ab_compare.py run --rounds 5 --format unit ... wa_bench.sh wb_bench.sh -- /usr/share/dict/words
# i9, two holds (one run of the whole bench is 60-80 s there, so 3 rounds do not fit in 10 minutes):
quiet strict 10 ... -- ./run.sh i9 4 d d 5       # EDGE_ROW_FILTER "d": groups build, random, decimal (+ word rows), then fst_bench x5
quiet strict 10 ... -- ./run.sh i9 3 long long 0 # group long, word rows excluded
```

Raw outputs: `$GATE/raw/fst/{m4,i9}/` (`save-*` are the ab_compare run files, `raw-*` the benches' own output with the old/new and A/A columns). The wrappers, `run.sh` and the build script are in `$GATE/fst/`.

## M4 (Apple M4 Pro)

`fst_cmp_bench`, 3 rounds, M4 hold:

| row                                 |   START |   HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | ------: | -----: | ---------: | --------: | ----: | : | ------: |
| words build                         |   270.3 |   99.4 |     2.714x | 2.65-2.73 | 1.042 | 3 |  faster |
| words for_each                      |    59.3 |   34.0 |     1.719x | 1.68-1.75 | 1.002 | 3 |  faster |
| build 1 random keys                 |   338.1 |  290.0 |     1.161x | 1.16-1.17 | 1.008 | 3 |  faster |
| build 4 random keys                 |   337.9 |  177.6 |     1.921x | 1.88-1.93 | 0.988 | 3 |  faster |
| build 16 random keys                |   404.6 |  123.8 |     3.260x | 3.24-3.29 | 1.001 | 3 |  faster |
| build 64 random keys                |   338.1 |   85.9 |     3.938x | 3.93-3.95 | 1.012 | 3 |  faster |
| build 256 random keys               |   328.6 |   80.6 |     4.100x | 4.08-4.12 | 0.985 | 3 |  faster |
| build 1024 random keys              |   319.0 |   83.6 |     3.834x | 3.74-3.84 | 0.992 | 3 |  faster |
| build 4096 random keys              |   328.0 |  102.8 |     3.191x | 3.07-3.25 | 1.001 | 3 |  faster |
| build 300k random 12-letter keys    |  2268.4 |  420.6 |     5.776x | 5.31-6.19 | 0.983 | 3 |  faster |
| for_each 200k random keys           |    71.5 |   41.5 |     1.723x | 1.70-1.76 | 1.011 | 3 |  faster |
| range from a prefix, first 1 keys   |   159.8 |  102.4 |     1.563x | 1.56-1.58 | 1.007 | 3 |  faster |
| range from a prefix, first 10 keys  |   784.6 |  532.2 |     1.476x | 1.47-1.50 | 1.006 | 3 |  faster |
| range from a prefix, first 100 keys |  6709.2 | 4684.2 |     1.432x | 1.41-1.48 | 0.968 | 3 |  faster |
| intersect, 3-byte prefix, all keys  |   788.5 |  811.6 |     0.972x | 0.94-0.99 | 0.986 | 3 |   noise |
| get, 1024 keys                      |    66.1 |   66.6 |     0.992x | 0.98-1.00 | 1.014 | 3 |   noise |
| build 300k decimal keys             |    67.9 |   36.5 |     1.886x | 1.82-1.90 | 0.987 | 3 |  faster |
| for_each 300k decimal keys          |    9.30 |   4.70 |     1.979x | 1.98-2.00 | 0.989 | 3 |  faster |
| build 20k keys of 200 bytes         | 91665.2 | 9221.4 |     9.940x | 9.41-9.99 | 1.007 | 3 |  faster |
| for_each 20k keys of 200 bytes      |  2080.7 | 1129.4 |     1.842x | 1.77-1.90 | 0.998 | 3 |  faster |

runs: START 3, HEAD 3, A/A 3; a ratio above 1 means HEAD is faster
geomean 2.281 over 20 rows (min 0.972 intersect, 3-byte prefix, all keys; max 9.940 build 20k keys of 200 bytes)
per-run geomean: min 2.266, median 2.274, max 2.286 over 3 runs
A/A geomean 0.999

`fst_bench` (the fst row: build ns/key from Mkeys/s, lookup p50, block-index floor), 5 rounds, same hold:

| row                | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------ | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| fst build (ns/key) | 290.7 | 111.1 |     2.528x | 2.44-2.67 | 0.945 | 5 |  faster |
| fst lookup p50     | 156.4 | 160.7 |     0.979x | 0.88-1.09 | 0.951 | 5 |   noise |
| block index floor  | 115.8 | 114.0 |     1.001x | 0.92-1.03 | 1.003 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.353 over 3 rows (min 0.979 fst lookup p50; max 2.528 fst build (ns/key))
per-run geomean: min 1.271, median 1.384, max 1.403 over 5 runs
A/A geomean 0.966

Geomean over the 23 timing rows: **2.131** (20 + 3 rows; the 20 `fst_cmp_bench` rows alone: 2.281). One row sits at 0.972 (`intersect`, noise in this hold) and is confirmed below 0.97 in a second hold, below. A/A geomean 0.999 (`fst_cmp_bench`).

uptime, M4 hold, start / end of the `fst_cmp_bench` part and end of the hold:

Sun Nov  1 09:57:45 PST 2026  |  `9:57  up 5 days, 15:22, 14 users, load averages: 19.46 22.01 19.70`
Sun Nov  1 10:05:45 PST 2026  |  `10:05  up 5 days, 15:30, 14 users, load averages: 10.13 14.42 16.79`
Sun Nov  1 10:06:16 PST 2026  |  `10:06  up 5 days, 15:31, 14 users, load averages: 9.02 13.76 16.47`

The hold started at 9:57 with the machine at load 19 (the strict wait for the load to settle ends at 10 minutes) and finished at 10:06 at load 9; the A/A rows absorb it (A/A 0.97-1.04 per row, geomean 0.999).

Cross-check, the HEAD binary's own in-process ratio (reference = START code, median of the 3 runs of the hold; same 11-trial interleaving the bench uses for its A/A):

| row | in-binary START/HEAD (median of runs) | in-binary A/A | runs |
| --- | ---: | ---: | ---: |
| words build | 2.55 | 0.98 | 3 |
| words for_each | 1.71 | 1.00 | 3 |
| build 1 random keys | 1.17 | 1.01 | 3 |
| build 4 random keys | 1.90 | 1.00 | 3 |
| build 16 random keys | 3.29 | 1.00 | 3 |
| build 64 random keys | 3.94 | 1.00 | 3 |
| build 256 random keys | 4.15 | 1.00 | 3 |
| build 1024 random keys | 3.72 | 1.00 | 3 |
| build 4096 random keys | 3.11 | 1.00 | 3 |
| build 300k random 12-letter keys | 5.66 | 0.98 | 3 |
| for_each 200k random keys | 1.73 | 0.99 | 3 |
| range from a prefix, first 1 keys | 1.68 | 1.01 | 3 |
| range from a prefix, first 10 keys | 1.68 | 1.01 | 3 |
| range from a prefix, first 100 keys | 1.61 | 1.02 | 3 |
| intersect, 3-byte prefix, all keys | 0.96 | 1.01 | 3 |
| get, 1024 keys | 0.99 | 1.01 | 3 |
| build 300k decimal keys | 1.85 | 1.00 | 3 |
| for_each 300k decimal keys | 1.98 | 1.00 | 3 |
| build 20k keys of 200 bytes | 9.31 | 1.00 | 3 |
| for_each 20k keys of 200 bytes | 1.81 | 1.00 | 3 |

## i9 (Intel i9-9980HK)

`fst_cmp_bench` groups build, random and decimal plus the word rows, 4 rounds, i9 hold a:

| row                                 |   START |   HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | ------: | -----: | ---------: | --------: | ----: | : | ------: |
| words build                         |   602.6 |  181.6 |     3.260x | 3.16-3.33 | 1.009 | 4 |  faster |
| words for_each                      |    73.2 |   59.0 |     1.238x | 1.20-1.41 | 1.006 | 4 |  faster |
| build 1 random keys                 |  1035.0 |  673.1 |     1.532x | 1.48-1.63 | 1.023 | 4 |  faster |
| build 4 random keys                 |  1028.0 |  451.2 |     2.272x | 2.20-2.30 | 1.012 | 4 |  faster |
| build 16 random keys                |  1237.7 |  285.6 |     4.252x | 4.21-4.46 | 1.010 | 4 |  faster |
| build 64 random keys                |   989.9 |  182.9 |     5.370x | 5.23-5.42 | 1.038 | 4 |  faster |
| build 256 random keys               |   940.7 |  180.6 |     5.231x | 4.99-5.26 | 1.032 | 4 |  faster |
| build 1024 random keys              |   855.1 |  222.8 |     3.805x | 3.53-3.89 | 1.014 | 4 |  faster |
| build 4096 random keys              |   826.2 |  247.0 |     3.401x | 3.02-3.42 | 0.998 | 4 |  faster |
| build 300k random 12-letter keys    |  3685.1 |  774.1 |     4.869x | 4.58-5.33 | 1.009 | 4 |  faster |
| for_each 200k random keys           |    91.0 |   69.9 |     1.305x | 1.24-1.32 | 0.992 | 4 |  faster |
| range from a prefix, first 1 keys   |   432.9 |  276.6 |     1.574x | 1.51-1.65 | 1.019 | 4 |  faster |
| range from a prefix, first 10 keys  |  1607.4 | 1170.8 |     1.408x | 1.34-1.44 | 1.020 | 4 |  faster |
| range from a prefix, first 100 keys | 11298.1 | 9395.0 |     1.203x | 1.12-1.28 | 1.016 | 4 |  faster |
| intersect, 3-byte prefix, all keys  |  1978.4 | 1914.8 |     1.039x | 0.95-1.06 | 1.014 | 4 |   noise |
| get, 1024 keys                      |   107.1 |  108.2 |     0.989x | 0.80-1.03 | 0.999 | 4 |   noise |
| build 300k decimal keys             |   180.4 |   68.0 |     2.741x | 2.15-2.84 | 1.013 | 4 |  faster |
| for_each 300k decimal keys          |    14.5 |   11.4 |     1.268x | 1.04-1.31 | 1.004 | 4 |  faster |

runs: START 4, HEAD 4, A/A 4; a ratio above 1 means HEAD is faster
geomean 2.187 over 18 rows (min 0.989 get, 1024 keys; max 5.370 build 64 random keys)
per-run geomean: min 2.063, median 2.179, max 2.241 over 4 runs
A/A geomean 1.013

`fst_bench`, 5 rounds, same hold:

| row                | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------ | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| fst build (ns/key) | 628.9 | 214.6 |     3.071x | 2.61-3.81 | 0.988 | 5 |  faster |
| fst lookup p50     | 170.2 | 169.5 |     1.064x | 0.90-1.09 | 0.969 | 5 |   noise |
| block index floor  | 177.9 | 161.4 |     1.035x | 0.86-1.35 | 0.983 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.501 over 3 rows (min 1.035 block index floor; max 3.071 fst build (ns/key))
per-run geomean: min 1.346, median 1.457, max 1.779 over 5 runs
A/A geomean 0.980

`fst_cmp_bench` group long, 3 rounds, i9 hold b (word rows excluded):

| row                            |  START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------------ | -----: | ------: | ---------: | --------: | ----: | : | ------: |
| build 20k keys of 200 bytes    | 143609 | 23294.3 |     6.095x | 5.74-6.30 | 1.019 | 3 |  faster |
| for_each 20k keys of 200 bytes | 2475.5 |  1753.7 |     1.405x | 1.39-1.58 | 1.000 | 3 |  faster |

runs: START 3, HEAD 3, A/A 3; a ratio above 1 means HEAD is faster
geomean 2.926 over 2 rows (min 1.405 for_each 20k keys of 200 bytes; max 6.095 build 20k keys of 200 bytes)
per-run geomean: min 2.926, median 2.954, max 3.013 over 3 runs
A/A geomean 1.009

Geomean over the 23 timing rows (18 + 2 `fst_cmp_bench` rows + 3 `fst_bench` rows): **2.136** (the 20 `fst_cmp_bench` rows alone: 2.252). Rows below 0.97: none (worst row 0.989, `get, 1024 keys`, range 0.80-1.03).

uptime, i9 hold a start / mid / end, and i9 hold b start / end:

Sun Nov  1 11:46:33 PST 2026  |  `11:46  up 30 days, 17:40, 5 users, load averages: 6.97 7.65 8.30`
Sun Nov  1 11:53:44 PST 2026  |  `11:53  up 30 days, 17:47, 5 users, load averages: 8.16 8.44 8.41`
Sun Nov  1 11:54:37 PST 2026  |  `11:54  up 30 days, 17:48, 5 users, load averages: 6.25 7.88 8.21`
Sun Nov  1 10:22:11 PST 2026  |  `10:22  up 30 days, 16:15, 5 users, load averages: 6.08 7.12 7.16`
Sun Nov  1 10:30:02 PST 2026  |  `10:30  up 30 days, 16:23, 5 users, load averages: 7.25 7.24 7.15`

The i9 carried a load of 6-8 from other sessions during both holds (strict does not pin cores on macOS, and the other work was not under a hold). Per-row ranges are wider than on the M4 (`get` 0.80-1.03, `block index floor` 0.86-1.35 over 5 rounds); the identical-binary control of the bitpack gate on the same machine spread by 0.93-1.05 per row in 3 rounds.

Cross-check, the HEAD binary's own in-process ratio (median of the runs of the holds):

| row | in-binary START/HEAD (median of runs) | in-binary A/A | runs |
| --- | ---: | ---: | ---: |
| words build | 3.21 | 0.99 | 4 |
| words for_each | 1.21 | 0.99 | 4 |
| build 1 random keys | 1.56 | 1.00 | 4 |
| build 4 random keys | 2.29 | 1.00 | 4 |
| build 16 random keys | 4.29 | 1.00 | 4 |
| build 64 random keys | 5.29 | 1.02 | 4 |
| build 256 random keys | 5.27 | 1.00 | 4 |
| build 1024 random keys | 3.89 | 1.01 | 4 |
| build 4096 random keys | 3.38 | 0.98 | 4 |
| build 300k random 12-letter keys | 4.66 | 1.02 | 4 |
| for_each 200k random keys | 1.29 | 1.00 | 4 |
| range from a prefix, first 1 keys | 1.54 | 1.00 | 4 |
| range from a prefix, first 10 keys | 1.27 | 1.00 | 4 |
| range from a prefix, first 100 keys | 1.03 | 1.00 | 4 |
| intersect, 3-byte prefix, all keys | 1.01 | 1.00 | 4 |
| get, 1024 keys | 0.99 | 1.02 | 4 |
| build 300k decimal keys | 2.50 | 1.06 | 4 |
| for_each 300k decimal keys | 1.35 | 0.99 | 4 |
| build 20k keys of 200 bytes | 5.91 | 1.02 | 3 |
| for_each 20k keys of 200 bytes | 1.53 | 1.02 | 3 |

## Extra: peak resident set of one build (not in the geomean)

`fst_build_rss` (peak RSS of a process that builds one FST from N sorted random 12-letter keys, the sorted keys included; each measurement in its own process). "reference" is START's builder (`fst_old.hh`), "builder" is HEAD's. Run unheld at nice 19 (a memory measurement does not depend on the load; the light holds starved for over 15 minutes). The START binary row set shows builder = reference (1.00x), the HEAD binary shows the saving.

M4:
```
== fst_build_rss.head (unheld, nice 19; peak RSS is not a timing)
peak RSS of a process that builds one FST from N random 12-letter keys, the sorted keys included
      keys    fst bytes     keys MiB  reference MiB    builder MiB     ratio
    100000      2118529          3.7           46.0           22.9     0.50x
    300000      6106550          8.3          110.0           75.5     0.69x
   1000000     18207568         24.3          343.5          155.5     0.45x
   2000000     33251090         47.2          646.0          306.1     0.47x
   3000000     47508164         70.1          809.7          585.0     0.72x
== fst_build_rss.start (unheld, nice 19; peak RSS is not a timing)
peak RSS of a process that builds one FST from N random 12-letter keys, the sorted keys included
      keys    fst bytes     keys MiB  reference MiB    builder MiB     ratio
    100000      2118529          3.7           46.0           46.0     1.00x
    300000      6106550          8.3          110.1          110.4     1.00x
   1000000     18207568         24.3          344.9          345.0     1.00x
   2000000     33251090         47.2          645.5          646.2     1.00x
   3000000     47508164         70.1          810.0          811.1     1.00x
```
i9:
```
== fst_build_rss.head (unheld, nice 19; peak RSS is not a timing)
peak RSS of a process that builds one FST from N random 12-letter keys, the sorted keys included
      keys    fst bytes     keys MiB  reference MiB    builder MiB     ratio
    100000      2118529          3.0           45.2           23.9     0.53x
    300000      6106550          7.6          109.5           75.1     0.69x
   1000000     18207568         23.6          343.6          162.7     0.47x
   2000000     33251090         46.5          644.6          314.5     0.49x
   3000000     47508164         69.3          809.0          592.5     0.73x
== fst_build_rss.start (unheld, nice 19; peak RSS is not a timing)
peak RSS of a process that builds one FST from N random 12-letter keys, the sorted keys included
      keys    fst bytes     keys MiB  reference MiB    builder MiB     ratio
    100000      2118529          3.0           44.9           45.0     1.00x
    300000      6106550          7.6          108.6          108.7     1.00x
   1000000     18207568         23.6          343.7          343.7     1.00x
   2000000     33251090         46.5          644.6          644.7     1.00x
   3000000     47508164         69.4          809.0          809.0     1.00x
```

## Rows below 0.97 outside the A/A spread

i9: none. M4: one row, `intersect, 3-byte prefix, all keys`.

| hold | rounds | START/HEAD | range | A/A | verdict | HEAD binary's own old/new (A/A) |
|---|---:|---:|---:|---:|---|---:|
| M4 hold (first, all rows) | 3 | 0.972 | 0.94-0.99 | 0.986 | noise | 0.96 (1.01) |
| M4 hold b (second, group random) | 5 | 0.953 | 0.93-0.97 | 0.995 | slower | 0.96 (1.02) |
| both holds pooled | 8 | 0.959 | 0.93-0.99 | 0.990 | | |

The second hold was run because the row appeared on the M4 only (the i9 reads 1.039, range 0.95-1.06, in-process 1.01). It confirms a loss of about 4 percent on the M4. Cause: not isolated. `intersect` and the node decoder it uses are not in the START..HEAD diff of `fst.hh` (the diff touches the includes, the new `walk<bounded>` behind `range` and `for_each`, and the builder), and in the START binary the same source compiled twice (`fst_old::` and `fst::`) reads 0.98 (median of 16 runs, 0.96-1.01). In the HEAD binary the unchanged source compiled as `fst::map::intersect` reads 0.96 against `fst_old::map::intersect` (8 runs, 0.95-0.99). So the loss is the compiler's codegen or layout of the unchanged function next to the new header code (about 2 to 4 percent, a few percent of which the START binary already shows between two copies), not an algorithm change; the instruction streams are inlined into the bench's timing loop and were not separated. Counted as unexplained.

Second hold, M4 hold b (group random plus the word rows, 5 rounds, load 7-10):

| row                                 |  START |   HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | -----: | -----: | ---------: | --------: | ----: | : | ------: |
| words build                         |  241.9 |   98.3 |     2.499x | 2.34-2.52 | 0.999 | 5 |  faster |
| words for_each                      |   58.6 |   34.2 |     1.713x | 1.66-1.75 | 0.998 | 5 |  faster |
| for_each 200k random keys           |   69.2 |   40.5 |     1.702x | 1.68-1.75 | 1.001 | 5 |  faster |
| range from a prefix, first 1 keys   |  151.6 |   98.0 |     1.543x | 1.48-1.56 | 0.991 | 5 |  faster |
| range from a prefix, first 10 keys  |  757.0 |  514.3 |     1.467x | 1.45-1.51 | 0.992 | 5 |  faster |
| range from a prefix, first 100 keys | 6418.2 | 4590.4 |     1.398x | 1.37-1.44 | 1.001 | 5 |  faster |
| intersect, 3-byte prefix, all keys  |  781.9 |  820.3 |     0.953x | 0.93-0.97 | 0.995 | 5 |  slower |
| get, 1024 keys                      |   63.5 |   63.8 |     1.002x | 0.98-1.02 | 1.003 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.472 over 8 rows (min 0.953 intersect, 3-byte prefix, all keys; max 2.499 words build)
per-run geomean: min 1.452, median 1.465, max 1.483 over 5 runs
A/A geomean 0.998

Sun Nov  1 12:28:41 PST 2026  |  `12:28  up 5 days, 17:53, 14 users, load averages: 10.43 7.68 7.84`
Sun Nov  1 12:30:42 PST 2026  |  `12:30  up 5 days, 17:55, 14 users, load averages: 7.95 7.58 7.78`

Other rows near the line, not counted: `get, 1024 keys` 0.992 (M4) and 0.989 (i9), `fst_bench` lookup p50 0.979 (M4, range 0.88-1.09, A/A 0.951) and 1.064 (i9): noise.

## Rows dropped or not comparable

None dropped. The word-list rows exist in both binaries; the START side runs the signature-string registry builder that HEAD replaced, so the build rows measure exactly that change (output bytes are identical: the bench aborts if the two outputs differ, and the HEAD binary printed `identical=1` in every run).

## Rig notes

- Light holds (builds) starved on both machines for over 15 minutes (a queue of 30 strict holds), so the builds of this repo ran unheld at nice 19 after that wait; no timing was taken outside a hold, except a smoke run of each binary (all rows present, outputs identical) before the first strict hold.
- The second M4 hold (M4 hold b) ran the `random` group only, 5 rounds, to confirm the `intersect` row.
- On the i9 the 3-round whole-bench run does not fit in 10 minutes (START side 80 s per run), hence two holds with the bench's own `EDGE_ROW_FILTER`.

SUMMARY repo=fst m4_geomean=2.131 i9_geomean=2.136 m4_slow=1/0.953 i9_slow=0/- unexplained=1 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 `intersect`, 3-byte prefix, all keys, 0.953 (0.972 in the first hold): placement. `intersect`
  is unchanged; the new header code beside it moves it.
