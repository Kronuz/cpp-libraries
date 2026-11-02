# Gate: errno-names (micro-bench, the repo has no bench)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). The repository's README has no benchmark command; the gate timed a micro-bench written for it, not kept. `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

`errno-names` has no bench (`examples/demo.cc` is a tour), so this gate uses a micro-bench. The only library change since START is in `error.hh`: the table of descriptions is now filled through `describe_with`, two overloads that read either `strerror_r` form (the XSI `int` one on macOS, the GNU `char*` one on glibc); this runs once, when the table is first built. `name()` and `description()` (the lookups) and `errnos.h` are byte-identical. The rest of the diff is docs, `CMakeLists.txt` (two new test targets) and tests.

Hot entry points: `error::name(int)` and `error::description(int)`, each a bounds check and a load from a function-local static table (a thread-safe static guard on every call). Micro-bench `errno-names/micro.cc`: `name_known` / `description_known` over every errno the platform defines, `name_any` / `description_any` over -20..279 (known, empty slots, out of range), `name_unknown` / `description_unknown` over values outside the table, and `init_first_call` (the first `description()` call of the process, which builds both tables: one sample per run). Rows are ns per call; the checksums (sums of lengths and first characters) agree between START and HEAD on both machines.

## Versions and rig

- START `a5ab101151d32ab9502c2cdfd2b4022aefd970ae` (2026-10-28 04:34 -0700), HEAD `0ec0801ff7b4d32412d33b2c7e041c6b55f38d14` (2026-11-01 04:17 -0800); both are first-parent commits of origin/main, fetched 2026-11-01.
- Both sides are HEAD's tree with START's library sources overlaid (`git diff --cached --stat HEAD` in the START tree):
```
 error.hh | 29 ++++++++---------------------
 1 file changed, 8 insertions(+), 21 deletions(-)
(library paths replaced from START: error.hh errnos.h)
```
- M4: Apple M4 Pro (14 cores, 48 GiB), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), target arm64-apple-darwin25.6.0, `python3` 3.12.16.
- i9: Intel Core i9-9980HK @ 2.40 GHz (8C/16T, 32 GiB), macOS 15.8.1 x86_64, Apple clang 17.0.0 (clang-1700.6.4.2), target x86_64-apple-darwin24.6.0, `python3` 3.15.0.
- Flags (CMake Release, same both sides and both machines): `/usr/bin/clang++ -O3 -DNDEBUG -std=gnu++17` (`-arch arm64` on the M4; no `-march`). `errno-names` is header-only and has no dependencies.

Commands (run from `$GATE`, same on both machines):

```
rig/prep.sh errno-names      # worktrees head/ and start/ (START sources overlaid on HEAD)
rig/build.sh errno-names     # cmake -S rig -B errno-names/build-{head,start} -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DTREE=errno-names/{head,start} -DMICRO=errno-names/micro.cc -DLIB=errno_names::errno_names -DSTD=17
                         # cmake --build ... -j4  ->  errno-names/micro.{start,head}
quiet strict <min> 'gate errno-names math micro A/B/A' -- rig/hold2.sh <m4|i9> errno-names math
  python3 ab_compare.py run --rounds 5 --save rig/out-<m>/errno-names --output markdown --label-a START --label-b HEAD errno-names/micro.start errno-names/micro.head
```
The micro-bench source is `micro.cc` next to this file's raw data (`$GATE/raw/errno-names/micro.cc`); it prints `label  X ns  chk HEX`, each row the best of 7 repeats inside one run, with a checksum that must agree between START and HEAD (otherwise ab_compare voids the row).

**Hold waits.** On the M4 the first strict hold queued (2026-11-01 09:35) had not started after 45 minutes (about 40 strict holds from other gate runs were queued); the work was split into short holds so each could win a slot, and the first ones started at 11:08:34 (errno-names, in the combined M4 hold, 11:08:34 to 11:08:40). On the i9: the first strict hold queued (09:51) was replaced at 10:35 by four waiters (all repos, errno-names+math, io, fs); errno-names started at 11:54:38 (i9 hold a, 11:54:38 to 11:54:56). Light holds starved for more than 15 minutes on both machines, so the micro-benches were built outside a hold with `nice -n 19` (small builds: one or two translation units each). No unheld timing is used in the tables below.

## Apple M4 Pro

**errno-names micro-bench (5 rounds, A/B/A interleaved)**

| row                 |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| init_first_call     | 25125.0 | 24792.0 |     1.011x | 0.92-1.04 | 1.029 | 5 |   noise |
| name_known          |    1.10 |    1.09 |     1.007x | 1.00-1.01 | 1.009 | 5 |   noise |
| description_known   |    1.16 |    1.16 |     1.003x | 0.98-1.01 | 0.999 | 5 |   noise |
| name_any            |   0.920 |   0.920 |     0.994x | 0.97-1.02 | 1.012 | 5 |   noise |
| description_any     |   0.860 |   0.871 |     0.995x | 0.98-1.02 | 0.997 | 5 |   noise |
| name_unknown        |   0.633 |   0.632 |     0.991x | 0.95-1.05 | 0.992 | 5 |   noise |
| description_unknown |   0.591 |   0.587 |     1.010x | 0.98-1.03 | 1.010 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.001 over 7 rows (min 0.991 name_unknown; max 1.011 init_first_call)
per-run geomean: min 0.975, median 0.999, max 1.020 over 5 runs
A/A geomean 1.007

uptime at the start and end of each run (hold):

```
errno-names start: 11:08:34 11:08  up 5 days, 16:33, 14 users, load averages: 9.67 10.13 11.77
errno-names end rc=0: 11:08:40 11:08  up 5 days, 16:33, 14 users, load averages: 9.39 10.05 11.72
```

## Intel i9-9980HK

**errno-names micro-bench (5 rounds, A/B/A interleaved)**

| row                 |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| init_first_call     | 43703.0 | 42188.0 |     1.017x | 0.69-1.56 | 1.131 | 5 |   noise |
| name_known          |    4.17 |    4.14 |     1.010x | 0.98-1.02 | 1.001 | 5 |   noise |
| description_known   |    4.46 |    4.47 |     0.994x | 0.98-1.03 | 0.996 | 5 |   noise |
| name_any            |    5.05 |    5.04 |     0.998x | 0.96-1.02 | 1.005 | 5 |   noise |
| description_any     |    2.21 |    2.21 |     0.996x | 0.99-1.03 | 1.007 | 5 |   noise |
| name_unknown        |    1.93 |    1.93 |     1.000x | 0.96-1.02 | 0.996 | 5 |   noise |
| description_unknown |    1.92 |    1.91 |     0.998x | 1.00-1.02 | 1.005 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.002 over 7 rows (min 0.994 description_known; max 1.017 init_first_call)
per-run geomean: min 0.946, median 1.012, max 1.059 over 5 runs
A/A geomean 1.019

uptime at the start and end of each run (hold):

```
errno-names start: 11:54:38 11:54  up 30 days, 17:48, 5 users, load averages: 5.83 7.76 8.16
errno-names end rc=0: 11:54:56 11:54  up 30 days, 17:48, 5 users, load averages: 9.63 8.48 8.41
```

## Geomean (comparable rows, START/HEAD, above 1 = HEAD faster)

- M4: 1.001
- i9: 1.002

## Rows < 0.97 outside the A/A spread

None. No row has a ratio below 0.97 outside the A/A spread on either machine (M4 min 0.991, i9 min 0.994; `init_first_call`, a single sample per run, ranges 0.92-1.04 on the M4 and 0.69-1.56 on the i9 and is noise).

## Rows dropped or not comparable

- Nothing dropped: HEAD's micro-bench compiles against START's `error.hh`.
- Not measured: the fix itself. On Linux/glibc START filled every description with `Unknown error: N` (the GNU `strerror_r` returns `char*`, which START compared with 0); HEAD reads it correctly. macOS has the XSI `strerror_r` that START already read right, so both sides do the same work here and the Linux behaviour change is not timed (no Linux machine in this gate).
- The verdict for this repo is SAME: the only non-doc change is in code that runs once at the first call, and the lookups are source-identical.

SUMMARY repo=errno-names m4_geomean=1.001 i9_geomean=1.002 m4_slow=0/- i9_slow=0/- unexplained=0 verdict=SAME
