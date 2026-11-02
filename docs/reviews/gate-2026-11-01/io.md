# Gate: io (micro-bench, the repo has no bench)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). The repository's README has no A/B benchmark (its `io_bench` is a throughput demo); the gate timed a micro-bench written for it, not kept. `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

`io` has no bench of its own (`examples/bench.cc` is a throughput demo on `/tmp`, not an A/B harness), so this gate uses a micro-bench. Since START the library source changed in one place: `io::pread` in `io.cc` now loops to the full count (and stops at end of file), where it used to return after one `::pread`; `io.hh` changed only in comments. Everything else (`read`, `write`, `pwrite`, `open`, `close`, `fstat`, `lseek`) is byte-identical code. The rest of `git diff START..HEAD` is docs (README, ARCHITECTURE, AGENTS, CHANGELOG), `CMakeLists.txt` (a new test target) and tests (`test/pread_test.cc`, `test/pread_interpose.cc`).

Hot entry points: `io::open`, `io::close`, `io::read`, `io::write`, `io::pread`, `io::pwrite` (EINTR-safe wrappers, `io.cc`), and the inline `io::fstat`, `io::lseek`, `io::unlink` (`io.hh`). Micro-bench `io/micro.cc`: a 16 MiB file on the data disk (`$GATE/io/data`, page-cached, never fsynced); rows `pread_4K` and `pread_64K` at pseudo-random 4 KiB-aligned offsets, `pread_4K_tail_100B` (only 100 bytes left before the end of file: the one shape whose syscall count changed), `pread_at_eof`, `pwrite_4K`, `pwrite_64K`, `read_4K_seq`, `write_4K_seq`, `open_close`, `fstat`, `lseek`. Every row is ns per call; the checksums (bytes read, byte counts, `st_size`, offsets) agree between START and HEAD on both machines.

## Versions and rig

- START `3893d47fb416ead9b52db604d8b148ef24a6fef6` (2026-10-28 04:35 -0700), HEAD `93ddcaf3953e9e2abd0ea0615313fa1accb57c16` (2026-11-01 05:13 -0800); both are first-parent commits of origin/main, fetched 2026-11-01.
- Both sides are HEAD's tree with START's library sources overlaid (`git diff --cached --stat HEAD` in the START tree):
```
 io.cc | 10 ++++++----
 io.hh |  8 ++------
 2 files changed, 8 insertions(+), 10 deletions(-)
(library paths replaced from START: io.cc io.hh io_trace.h likely.h)
```
- M4: Apple M4 Pro (14 cores, 48 GiB), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), target arm64-apple-darwin25.6.0, `python3` 3.12.16.
- i9: Intel Core i9-9980HK @ 2.40 GHz (8C/16T, 32 GiB), macOS 15.8.1 x86_64, Apple clang 17.0.0 (clang-1700.6.4.2), target x86_64-apple-darwin24.6.0, `python3` 3.15.0.
- Flags (CMake Release, same both sides and both machines): `/usr/bin/clang++ -O3 -DNDEBUG -std=gnu++20` (`-arch arm64` on the M4; no `-march`). `io` has no dependencies.

Commands (run from `$GATE`, same on both machines):

```
rig/prep.sh io      # worktrees head/ and start/ (START sources overlaid on HEAD)
rig/build.sh io     # cmake -S rig -B io/build-{head,start} -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DTREE=io/{head,start} -DMICRO=io/micro.cc -DLIB=io::io -DSTD=20
                         # cmake --build ... -j4  ->  io/micro.{start,head}
quiet strict <min> 'gate io micro A/B/A' -- rig/hold2.sh <m4|i9> io
  python3 ab_compare.py run --rounds 5 --save rig/out-<m>/io --output markdown --label-a START --label-b HEAD io/micro.start io/micro.head -- $GATE/io/data
```
The micro-bench source is `micro.cc` next to this file's raw data (`$GATE/raw/io/micro.cc`); it prints `label  X ns  chk HEX`, each row the best of 4 repeats inside one run, with a checksum that must agree between START and HEAD (otherwise ab_compare voids the row).

**Hold waits.** On the M4 the first strict hold queued (2026-11-01 09:35) had not started after 45 minutes (about 40 strict holds from other gate runs were queued); the work was split into short holds so each could win a slot, and the first ones started at 11:08 (io, in the combined M4 hold, 11:09:17 to 11:10:30). On the i9: the first strict hold queued (09:51) was replaced at 10:35 by four waiters (all repos, errno-names+math, io, fs); the io hold started at 10:50:46 (i9 hold b, 10:50:46 to 10:52:45). Light holds starved for more than 15 minutes on both machines, so the micro-benches were built outside a hold with `nice -n 19` (small builds: one or two translation units each). No unheld timing is used in the tables below.

## Apple M4 Pro

**io micro-bench (5 rounds, A/B/A interleaved)**

| row                |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------ | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| pread_4K           |   422.2 |   419.9 |     0.967x | 0.92-1.18 | 0.993 | 5 |   noise |
| pread_64K          |  2016.3 |  2068.6 |     0.998x | 0.94-1.08 | 1.009 | 5 |   noise |
| pread_4K_tail_100B |   270.6 |   495.6 |     0.543x | 0.54-0.55 | 1.012 | 5 |  slower |
| pread_at_eof       |   217.6 |   217.8 |     0.994x | 0.94-1.03 | 1.012 | 5 |   noise |
| pwrite_4K          |  1136.9 |  1124.6 |     0.941x | 0.87-1.07 | 1.042 | 5 |   noise |
| pwrite_64K         |  2820.0 |  2708.7 |     0.976x | 0.95-1.07 | 1.009 | 5 |   noise |
| read_4K_seq        |   404.4 |   406.5 |     1.002x | 0.99-1.01 | 0.985 | 5 |   noise |
| write_4K_seq       |  1080.4 |  1081.1 |     1.002x | 0.80-1.04 | 1.032 | 5 |   noise |
| open_close         | 34777.1 | 35470.3 |     0.987x | 0.89-1.07 | 1.020 | 5 |   noise |
| fstat              |   241.0 |   238.0 |     1.016x | 1.00-1.02 | 1.002 | 5 |  faster |
| lseek              |   173.0 |   173.9 |     0.995x | 0.99-1.00 | 0.993 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.935 over 11 rows (min 0.543 pread_4K_tail_100B; max 1.016 fstat)
per-run geomean: min 0.906, median 0.921, max 0.962 over 5 runs
A/A geomean 1.010

uptime at the start and end of each run (hold):

```
io start: 11:09:17 11:09  up 5 days, 16:34, 14 users, load averages: 8.63 9.77 11.55
io end rc=0: 11:10:30 11:10  up 5 days, 16:35, 14 users, load averages: 8.60 9.53 11.31
```

## Intel i9-9980HK

**io micro-bench (5 rounds, A/B/A interleaved)**

| row                |  START |   HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------ | -----: | -----: | ---------: | --------: | ----: | : | ------: |
| pread_4K           | 1174.8 | 1182.5 |     1.009x | 0.94-1.05 | 1.011 | 5 |   noise |
| pread_64K          | 5768.3 | 5715.8 |     1.069x | 0.74-1.28 | 0.948 | 5 |   noise |
| pread_4K_tail_100B |  788.4 | 1428.9 |     0.551x | 0.54-0.56 | 1.018 | 5 |  slower |
| pread_at_eof       |  622.6 |  636.1 |     0.986x | 0.95-1.02 | 0.998 | 5 |   noise |
| pwrite_4K          | 2673.8 | 2629.3 |     0.985x | 0.94-1.28 | 1.071 | 5 |   noise |
| pwrite_64K         | 7061.6 | 6864.5 |     1.036x | 0.94-1.15 | 0.965 | 5 |   noise |
| read_4K_seq        | 1304.1 | 1240.9 |     1.000x | 0.96-1.06 | 1.067 | 5 |   noise |
| write_4K_seq       | 2856.1 | 2698.4 |     1.065x | 0.95-1.21 | 1.045 | 5 |   noise |
| open_close         | 7693.3 | 7566.9 |     1.015x | 0.98-1.09 | 1.044 | 5 |   noise |
| fstat              |  728.7 |  737.5 |     0.982x | 0.95-1.03 | 0.995 | 5 |   noise |
| lseek              |  486.3 |  489.8 |     0.994x | 0.97-1.00 | 0.994 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.959 over 11 rows (min 0.551 pread_4K_tail_100B; max 1.069 pread_64K)
per-run geomean: min 0.928, median 0.958, max 0.984 over 5 runs
A/A geomean 1.013

uptime at the start and end of each run (hold):

```
io start: 10:50:46 10:50  up 30 days, 16:44, 5 users, load averages: 8.72 7.78 7.61
io end rc=0: 10:52:45 10:52  up 30 days, 16:46, 5 users, load averages: 6.19 7.25 7.43
```

## Geomean (comparable rows, START/HEAD, above 1 = HEAD faster)

- M4: 0.935
- i9: 0.959
- M4 without `pread_4K_tail_100B`: 0.988
- i9 without `pread_4K_tail_100B`: 1.014

## Rows < 0.97 outside the A/A spread

- **`pread_4K_tail_100B`: M4 0.543x (range 0.54-0.55, A/A 1.01), i9 0.551x (0.54-0.56, A/A 1.02).** Cause (explained, deterministic, both machines): the CHANGELOG entry "`io::pread` returned after one `::pread`" (2026-11-01, `6524ce0 Loop io::pread to the full count`). When fewer bytes than asked are left before the end of the file, HEAD reads the 100 bytes and then issues a second `::pread` that returns 0, where START stopped after the first. That is one more syscall (about 230 ns on the M4, 640 ns on the i9, the `pread_at_eof` row) and it is the documented cost of the fix: the CHANGELOG itself notes that a full-count read "changes nothing ... except a second `pread` at the end of a file". Reads that return the full count (`pread_4K`, `pread_64K`) take the same single syscall in both.
- Candidates inside the A/A noise (not counted): M4 `pread_4K` 0.967x (range 0.92-1.18) and `pwrite_4K` 0.941x (0.87-1.07); neither reproduces on the i9 (1.009x and 0.985x), and the code of those paths is unchanged.

## Rows dropped or not comparable

- `pread_4K_tail_100B` is kept (and counted above), but note it measures a changed behaviour: START returns after one read, HEAD asks again to learn that the file ended. The returned bytes and counts are identical (equal checksums).
- No row was dropped: HEAD's micro-bench compiles against START's `io.cc` (it only uses API present at START).
- All other rows exercise code that is byte-identical between START and HEAD; their ratios are the A/A noise of the syscall path.

SUMMARY repo=io m4_geomean=0.935 i9_geomean=0.959 m4_slow=1/0.543 i9_slow=1/0.551 unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- `pread_4K_tail_100B` (M4 0.543, i9 0.551): accepted. `io::pread` loops to the full count
  (`io:6524ce0`), so a read that reaches end of file makes a second `pread`, which returns 0
  (about 230 ns on the M4 Pro, 640 ns on the i9). Start returned after one call.
