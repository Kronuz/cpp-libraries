# Gate: fs (micro-bench, the repo has no bench)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). The repository's README has no benchmark command; the gate timed a micro-bench written for it, not kept. `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

`fs` has no bench (`examples/db_layout.cc` is a usage example), so this gate uses a micro-bench. Library changes since START in `fs.cc` and `fs.hh`: `normalize_path` rewritten in three correctness steps (no walk off a default-constructed view, an empty path stays empty, the first component of a relative path is popped by `..`); `mkdirs("")` returns false; `build_path_index("/name")` uses `/`; `copy_file` rewritten (opens the destination without `O_TRUNC`, `fstat`s both descriptors and refuses the same device and inode, `ftruncate`s a regular destination, copies with a short-write and EINTR loop, checks `close`, closes the `DIR`); `delete_files`, `quarantine_files`, `move_files`, `exists`, `mkdir`, `opendir` are unchanged code. The rest of the diff is docs, `CMakeLists.txt` (dependency pins, new test targets) and tests (about 900 lines).

Hot entry points: `normalize_path` (pure, called on every path of a Xapiand database), `exists`, `mkdirs`, `build_path_index`, `copy_file`, `delete_files`. Micro-bench `fs/micro.cc`: `np_*` rows (16 shapes that give the same bytes at START and HEAD: plain, relative, `.`/`..`, trailing slash, `slashed`, repeated slashes, `keep_slash`, a Xapiand-like path, 40 components, 20 `..` pairs, leading `.`/`..`, `.`, `/`, `..` at the end and at the root); `exists_present`, `exists_missing`, `mkdirs_existing`, `build_path_index_existing` (one `stat` each); `mkdirs_new3` (three new directories, removed outside the timer); `copy_file_8x4K_fresh` and `copy_file_1MiB_fresh` (the destination is removed outside the timer, then one `copy_file` of a directory of eight 4 KiB files or one 1 MiB file); `delete_files_16_control` (16 files created outside the timer, unchanged code: a control). Rows are ns per call. The checksums agree between START and HEAD on both machines for every row of the main table.

## Versions and rig

- START `ce16118f9a71f80a4474e71e3333948a49149a5a` (2026-10-28 04:34 -0700), HEAD `d172a133b869ce750d3d36ed27bed13174253d9b` (2026-11-01 05:30 -0800); both are first-parent commits of origin/main, fetched 2026-11-01.
- Both sides are HEAD's tree with START's library sources overlaid (`git diff --cached --stat HEAD` in the START tree):
```
 fs.cc | 151 ++++++++----------------------------------------------------------
 fs.hh |  10 +----
 2 files changed, 20 insertions(+), 141 deletions(-)
(library paths replaced from START: fs.cc fs.hh fs_trace.h)
```
- M4: Apple M4 Pro (14 cores, 48 GiB), macOS 26.7.2, Apple clang 17.0.0 (clang-1700.3.19.1), target arm64-apple-darwin25.6.0, `python3` 3.12.16.
- i9: Intel Core i9-9980HK @ 2.40 GHz (8C/16T, 32 GiB), macOS 15.8.1 x86_64, Apple clang 17.0.0 (clang-1700.6.4.2), target x86_64-apple-darwin24.6.0, `python3` 3.15.0.
- Flags (CMake Release, same both sides and both machines): `/usr/bin/clang++ -O3 -DNDEBUG -std=gnu++20` (`-arch arm64` on the M4; no `-march`). Dependencies are held fixed at HEAD's pins for both sides (START's own CMake pinned older `strings` and `stringified`; the START tree is built with `-DFETCHCONTENT_SOURCE_DIR_{IO,STRINGS,SPLIT,STRINGIFIED}` pointing at HEAD's checkouts, so the dependency sources are byte-identical): io 1336f85, strings 485f882, split aa9857a, stringified 0053465, and, pulled in by strings, char_classify a890496, repr b47e947, static_string eb1efcb, term_color 534e309 (same SHAs on both machines).

Commands (run from `$GATE`, same on both machines):

```
rig/prep.sh fs      # worktrees head/ and start/ (START sources overlaid on HEAD)
rig/build.sh fs     # cmake -S rig -B fs/build-{head,start} -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DTREE=fs/{head,start} -DMICRO=fs/micro.cc -DLIB=fs::fs -DSTD=20
                         # cmake --build ... -j4  ->  fs/micro.{start,head}
quiet strict <min> 'gate fs micro A/B/A' -- rig/hold2.sh <m4|i9> fs
  python3 ab_compare.py run --rounds 5 --save rig/out-<m>/fs-diff ... fs/micro.start fs/micro.head -- $GATE/fs/data diff    # rows whose result differs (not comparable)
  python3 ab_compare.py run --rounds 5 (4 on the i9) --save rig/out-<m>/fs ... fs/micro.start fs/micro.head -- $GATE/fs/data      # the main table
quiet strict <min> 'gate confirm' -- rig/confirm.sh <m4|i9> fs-copy     # second hold, 7 rounds: ab_compare ... fs/micro-copy.start fs/micro-copy.head -- fs/data copy
```
The micro-bench source is `micro.cc` next to this file's raw data (`$GATE/raw/fs/micro.cc`); it prints `label  X ns  chk HEX`, each row the best of 4 repeats inside one run, with a checksum that must agree between START and HEAD (otherwise ab_compare voids the row). `$GATE/raw/fs/micro.cc` is the final file: it gained a `copy` mode (only the two `copy_file_*_fresh` rows) after the main holds, for the confirmation hold; the other modes and rows are unchanged.

**Hold waits.** On the M4 the first strict hold queued (2026-11-01 09:35) had not started after 45 minutes (about 40 strict holds from other gate runs were queued); the work was split into short holds so each could win a slot, and the first ones started at 11:04:34 (fs, M4 hold c, 11:04:34 to 11:08:33). On the i9: the first strict hold queued (09:51) was replaced at 10:35 by four waiters (all repos, errno-names+math, io, fs); the fs hold started at 11:00:11 (i9 hold c, 11:00:11 to 11:05:03; 4 rounds to fit the hold). Light holds starved for more than 15 minutes on both machines, so the micro-benches were built outside a hold with `nice -n 19` (small builds: one or two translation units each). No unheld timing is used in the tables below. The only unheld numbers are the per-commit split of `normalize_path` on the M4, labelled as a diagnostic where it appears.

## Apple M4 Pro

**fs micro-bench, comparable rows**

| row                       |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| np_plain                  |    10.6 |    15.2 |     0.692x | 0.65-0.73 | 1.000 | 5 |  slower |
| np_relative               |    9.60 |    13.4 |     0.716x | 0.69-0.73 | 0.989 | 5 |  slower |
| np_dots                   |    23.5 |    29.8 |     0.783x | 0.78-0.80 | 1.026 | 5 |  slower |
| np_trailing_slash         |    14.5 |    20.7 |     0.714x | 0.69-0.73 | 1.000 | 5 |  slower |
| np_slashed                |    14.5 |    18.9 |     0.762x | 0.75-0.79 | 1.028 | 5 |  slower |
| np_repeated_slashes       |    17.1 |    24.2 |     0.712x | 0.64-0.77 | 0.989 | 5 |  slower |
| np_keep_slash             |    13.7 |    19.3 |     0.703x | 0.67-0.76 | 1.007 | 5 |  slower |
| np_xapiand_path           |    49.5 |    64.6 |     0.778x | 0.72-0.82 | 1.000 | 5 |  slower |
| np_long                   |   298.4 |   357.1 |     0.837x | 0.83-0.86 | 1.007 | 5 |  slower |
| np_long_dots              |   276.5 |   353.8 |     0.785x | 0.77-0.79 | 0.996 | 5 |  slower |
| np_leading_dot            |    9.80 |    13.6 |     0.721x | 0.70-0.76 | 1.000 | 5 |  slower |
| np_leading_dotdot         |    10.7 |    15.0 |     0.715x | 0.68-0.75 | 1.009 | 5 |  slower |
| np_dot                    |    6.70 |    7.40 |     0.919x | 0.85-0.96 | 1.030 | 5 |   noise |
| np_root                   |    6.40 |    7.90 |     0.810x | 0.74-0.85 | 1.016 | 5 |  slower |
| np_abs_dotdot_end         |    13.5 |    17.4 |     0.767x | 0.74-0.78 | 1.023 | 5 |  slower |
| np_abs_dotdot_root        |    14.9 |    17.7 |     0.829x | 0.79-0.85 | 1.041 | 5 |  slower |
| exists_present            |   615.1 |   607.5 |     1.010x | 0.98-1.02 | 1.008 | 5 |   noise |
| exists_missing            |   419.8 |   418.8 |     1.007x | 0.98-1.02 | 0.998 | 5 |   noise |
| mkdirs_existing           |   616.5 |   613.7 |     1.003x | 0.99-1.01 | 1.010 | 5 |   noise |
| build_path_index_existing |   623.2 |   621.4 |     1.010x | 0.98-1.02 | 1.010 | 5 |   noise |
| mkdirs_new3               |  113323 |  106174 |     1.015x | 0.82-1.14 | 1.047 | 5 |   noise |
| copy_file_8x4K_fresh      |  612073 |  630057 |     0.971x | 0.93-0.99 | 0.990 | 5 |   noise |
| copy_file_1MiB_fresh      | 1281702 | 1343687 |     0.987x | 0.76-1.15 | 0.976 | 5 |   noise |
| delete_files_16_control   |  437502 |  441978 |     0.986x | 0.97-1.13 | 1.004 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.835 over 24 rows (min 0.692 np_plain; max 1.015 mkdirs_new3)
per-run geomean: min 0.827, median 0.831, max 0.838 over 5 runs
A/A geomean 1.008

**fs rows whose result differs between START and HEAD (not comparable; no checksum)**

| row                      |  START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------ | -----: | ------: | ---------: | --------: | ----: | : | ------: |
| np_empty                 |   5.50 |    4.40 |     1.273x | 1.25-1.32 | 1.018 | 5 |  faster |
| np_relative_pop          |   11.1 |    14.6 |     0.755x | 0.69-0.82 | 1.009 | 5 |  slower |
| np_relative_pop_all      |   13.6 |    16.8 |     0.840x | 0.80-0.85 | 1.000 | 5 |  slower |
| copy_file_8x4K_overwrite | 590762 | 1037704 |     0.567x | 0.52-0.80 | 0.990 | 5 |  slower |
| copy_file_1MiB_overwrite | 575818 | 1968090 |     0.435x | 0.19-0.68 | 0.929 | 5 |  slower |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.724 over 5 rows (min 0.435 copy_file_1MiB_overwrite; max 1.273 np_empty)
per-run geomean: min 0.625, median 0.724, max 0.776 over 5 runs
A/A geomean 0.989

uptime at the start and end of each run (hold):

```
fs-diff start: 11:04:34 11:04  up 5 days, 16:29, 14 users, load averages: 9.08 10.44 12.41
fs-diff end rc=0: 11:05:28 11:05  up 5 days, 16:30, 14 users, load averages: 8.54 10.02 12.13
fs start: 11:05:28 11:05  up 5 days, 16:30, 14 users, load averages: 8.54 10.02 12.13
fs end rc=0: 11:08:33 11:08  up 5 days, 16:33, 14 users, load averages: 9.67 10.13 11.77
fs-copy start: 11:35:42 11:35  up 5 days, 17 hrs, 14 users, load averages: 11.92 10.88 11.94
fs-copy end rc=0: 11:37:57 11:37  up 5 days, 17:02, 14 users, load averages: 9.40 10.23 11.53
```

## Intel i9-9980HK

**fs micro-bench, comparable rows**

| row                       |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| np_plain                  |    26.3 |    38.1 |     0.701x | 0.64-0.73 | 0.984 | 4 |  slower |
| np_relative               |    22.5 |    33.2 |     0.684x | 0.62-0.76 | 0.980 | 4 |  slower |
| np_dots                   |    53.4 |    76.1 |     0.695x | 0.68-0.71 | 0.993 | 4 |  slower |
| np_trailing_slash         |    30.2 |    50.8 |     0.606x | 0.55-0.62 | 0.998 | 4 |  slower |
| np_slashed                |    28.9 |    48.8 |     0.590x | 0.58-0.61 | 0.980 | 4 |  slower |
| np_repeated_slashes       |    36.3 |    64.1 |     0.565x | 0.54-0.60 | 0.964 | 4 |  slower |
| np_keep_slash             |    26.8 |    49.9 |     0.532x | 0.51-0.57 | 0.938 | 4 |  slower |
| np_xapiand_path           |   113.3 |   165.8 |     0.690x | 0.65-0.75 | 0.984 | 4 |  slower |
| np_long                   |   502.5 |  1115.8 |     0.447x | 0.44-0.46 | 0.973 | 4 |  slower |
| np_long_dots              |   696.5 |  1017.8 |     0.686x | 0.67-0.69 | 1.018 | 4 |  slower |
| np_leading_dot            |    24.9 |    34.2 |     0.726x | 0.71-0.74 | 1.037 | 4 |  slower |
| np_leading_dotdot         |    28.0 |    38.3 |     0.730x | 0.71-0.77 | 1.067 | 4 |  slower |
| np_dot                    |    16.8 |    19.6 |     0.877x | 0.83-0.88 | 1.063 | 4 |  slower |
| np_root                   |    16.3 |    18.9 |     0.853x | 0.79-0.92 | 1.063 | 4 |  slower |
| np_abs_dotdot_end         |    32.1 |    45.2 |     0.712x | 0.69-0.77 | 1.023 | 4 |  slower |
| np_abs_dotdot_root        |    36.2 |    50.0 |     0.730x | 0.69-0.76 | 1.045 | 4 |  slower |
| exists_present            |  1775.8 |  1788.5 |     0.991x | 0.98-1.00 | 1.000 | 4 |   noise |
| exists_missing            |  1216.6 |  1226.6 |     0.990x | 0.99-1.00 | 0.963 | 4 |   noise |
| mkdirs_existing           |  1803.6 |  1800.6 |     0.998x | 0.98-1.01 | 0.992 | 4 |   noise |
| build_path_index_existing |  1828.3 |  1802.5 |     1.013x | 1.00-1.03 | 1.010 | 4 |   noise |
| mkdirs_new3               |  151982 |  152037 |     1.002x | 0.96-1.03 | 0.968 | 4 |   noise |
| copy_file_8x4K_fresh      | 1099946 | 1144057 |     0.957x | 0.95-0.97 | 1.001 | 4 |   noise |
| copy_file_1MiB_fresh      | 3669798 | 3718042 |     0.994x | 0.98-1.05 | 0.990 | 4 |   noise |
| delete_files_16_control   |  571305 |  559220 |     1.022x | 0.98-1.11 | 0.974 | 4 |   noise |

runs: START 4, HEAD 4, A/A 4; a ratio above 1 means HEAD is faster
geomean 0.763 over 24 rows (min 0.447 np_long; max 1.022 delete_files_16_control)
per-run geomean: min 0.759, median 0.762, max 0.770 over 4 runs
A/A geomean 1.000

**fs rows whose result differs between START and HEAD (not comparable; no checksum)**

| row                      |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------ | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| np_empty                 |    15.0 |    12.5 |     1.192x | 1.12-1.24 | 0.980 | 5 |  faster |
| np_relative_pop          |    28.7 |    40.2 |     0.692x | 0.63-0.77 | 0.996 | 5 |  slower |
| np_relative_pop_all      |    34.9 |    46.2 |     0.747x | 0.72-0.84 | 1.020 | 5 |  slower |
| copy_file_8x4K_overwrite |  342148 |  859830 |     0.388x | 0.37-0.41 | 1.018 | 5 |  slower |
| copy_file_1MiB_overwrite | 1928162 | 2539606 |     0.753x | 0.74-0.79 | 0.997 | 5 |  slower |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.710 over 5 rows (min 0.388 copy_file_8x4K_overwrite; max 1.192 np_empty)
per-run geomean: min 0.688, median 0.719, max 0.731 over 5 runs
A/A geomean 1.002

uptime at the start and end of each run (hold):

```
fs-diff start: 11:00:11 11:00  up 30 days, 16:53, 5 users, load averages: 9.37 8.26 7.75
fs-diff end rc=0: 11:00:53 11:00  up 30 days, 16:54, 5 users, load averages: 7.28 7.84 7.62
fs start: 11:00:53 11:00  up 30 days, 16:54, 5 users, load averages: 7.28 7.84 7.62
fs end rc=0: 11:05:03 11:05  up 30 days, 16:58, 5 users, load averages: 9.38 8.23 7.79
fs-copy start: 11:44:17 11:44  up 30 days, 17:38, 5 users, load averages: 6.07 7.50 8.35
fs-copy end rc=0: 11:46:33 11:46  up 30 days, 17:40, 5 users, load averages: 6.97 7.65 8.30
```

## Geomean (comparable rows, START/HEAD, above 1 = HEAD faster)

- M4: 0.835
- i9: 0.763

## Confirmation holds

**m4 fs-copy**

| row                  |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| copy_file_8x4K_fresh |  800903 |  841752 |     0.943x | 0.91-0.98 | 0.980 | 7 |   noise |
| copy_file_1MiB_fresh | 1286961 | 1333785 |     0.923x | 0.62-1.23 | 0.835 | 7 |   noise |

runs: START 7, HEAD 7, A/A 7; a ratio above 1 means HEAD is faster
geomean 0.933 over 2 rows (min 0.923 copy_file_1MiB_fresh; max 0.943 copy_file_8x4K_fresh)
per-run geomean: min 0.764, median 0.944, max 1.099 over 7 runs
A/A geomean 0.905

**i9 fs-copy**

| row                  |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| copy_file_8x4K_fresh | 1126222 | 1172705 |     0.985x | 0.92-1.01 | 1.017 | 7 |   noise |
| copy_file_1MiB_fresh | 3719291 | 3721325 |     1.003x | 0.96-1.03 | 1.007 | 7 |   noise |

runs: START 7, HEAD 7, A/A 7; a ratio above 1 means HEAD is faster
geomean 0.994 over 2 rows (min 0.985 copy_file_8x4K_fresh; max 1.003 copy_file_1MiB_fresh)
per-run geomean: min 0.962, median 0.974, max 1.020 over 7 runs
A/A geomean 1.012

## Rows < 0.97 outside the A/A spread

ab_compare's `slower` verdict (ratio below 1/(1+largest A/A deviation)) with a ratio under 0.97.

- **M4: 15 of the 16 `np_*` rows**, 0.692x (`np_plain`) to 0.837x (`np_long`), typically 0.70-0.78x; only `np_dot` (0.919x) is inside the noise.
- **i9: all 16 `np_*` rows**, 0.447x (`np_long`, 502 ns to 1116 ns) to 0.877x (`np_dot`), typically 0.53-0.73x.

Cause (explained by the diff and the CHANGELOG, a correctness cost; the CHANGELOG records no performance note): `normalize_path` was rewritten three times since START. 2026-10-31 (`bf10f39`): the loop counts the bytes of `[src, end)` and the closing `/` instead of using `end - 1` (a default-constructed view crashed). 2026-11-01 (`7a10a04`, `d172a13`): an empty path stays empty and `..` pops the first component of a relative path, which adds three state variables (`first_dots`, `first_open`, `emptied`), a pop floor recomputed at every `/` and extra tests per byte. Every non-empty input still gives the same bytes (equal checksums), so the cost buys the fixes and nothing else.
Split by commit on the M4 (unheld diagnostic, so not a result: fs.cc of each commit linked into the same micro, CPU-bound rows, best of two runs): `np_plain` 10.5 ns at START, 12.0 ns at `bf10f39`, 12.0 ns at `7a10a04`, 15.3 ns at HEAD; `np_dots` 24.5, 27, 26, 32 ns; `np_repeated_slashes` 17-20, 19, 19, 25 ns; `np_long` 311-367, 346-359, 336, 357-374 ns (flat). About a third of the short-path cost comes from the view and empty-path fixes and the rest from the first-component pop. I did not split the i9's 2.2x on `np_long` by commit.
In absolute terms the added time is 3-5 ns per call on the M4 and 10-20 ns on the i9 for a short path (600 ns for a 40-component path on the i9), against 0.4-1.8 us for a single `stat` and 100-150 us for `mkdirs` of new directories.

Candidates inside the A/A spread (not counted): `copy_file_8x4K_fresh` 0.971x on the M4 (0.93-0.99) and 0.943x in the M4 confirmation hold (0.91-0.98, A/A 0.98); 0.957x on the i9 (0.95-0.97) and 0.985x in the i9 confirmation hold (0.92-1.01); `copy_file_1MiB_fresh` 0.987x and 0.923x (A/A 0.84, useless) on the M4, 0.994x and 1.003x on the i9. HEAD's `copy_file` makes three more syscalls per copied file (two `fstat` for the same-file identity check, one `ftruncate`), which fits a 1-5 % cost on the 8-file directory; the 1 MiB copy is dominated by 512 read/write syscalls and shows nothing.

## Rows dropped or not comparable

- `np_empty`, `np_relative_pop`, `np_relative_pop_all` (table `fs-diff`, time only, no checksum): the result differs by design. START returns `/` for an empty path and `a/b/c` for `a/../b/c`; HEAD returns an empty path and `b/c`. `np_empty` is 1.27x faster on the M4 and 1.19x on the i9 because HEAD does no work; the two pop rows are 0.755x / 0.840x (M4) and 0.692x / 0.747x (i9) because HEAD performs the pop START skipped.
- `copy_file_8x4K_overwrite`, `copy_file_1MiB_overwrite` (table `fs-diff`): copying over an existing file. START opened the destination without `O_TRUNC` and wrote in place (the bug that kept a longer file's old tail, fixed 2026-10-30); HEAD truncates first. 0.567x / 0.435x on the M4 and 0.388x / 0.753x on the i9 are the price of truncating and rewriting the blocks, not a regression of the same work. The `*_fresh` rows (destination removed outside the timer) are the comparable ones.
- Not benchmarked: `normalize_path` and `mkdirs` on an empty or default-constructed view (undefined behaviour at START), `quarantine_files`, `move_files`, `opendir`, `mkdir` (unchanged code). `delete_files_16_control` is the control for unchanged code: 0.986x on the M4 and 1.022x on the i9, both noise.
- The `np_*` shapes are all inputs on which START and HEAD return the same bytes, so the comparison holds the output fixed.

SUMMARY repo=fs m4_geomean=0.835 i9_geomean=0.763 m4_slow=15/0.692 i9_slow=16/0.447 unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- Every `normalize_path` row (M4 0.692 to 0.837 on 15 of 16; i9 0.447 to 0.877): fixed in
  `fs:c91b457`, restored in `fs:32e564e` after `f4439d8` (CHANGELOG `a6cd8bb`). The three correctness
  fixes (an empty path, a default-constructed view, `..` popping the first component of a relative
  path) left it 1.3 to 2.2 times slower than start; the one-pass loop builds the result on the
  stack. It is faster than start on all 14 comparable rows on the i9 (1.33 to 1.94 times) and on 12
  rows on the M4 Pro (1.10 to 1.65 times, one tie), except `np_relative` at 0.92 on the M4 Pro, the
  cost of the relative-path `..` fix: accepted, [fs#1](https://github.com/Kronuz/fs/issues/1).
  `tools/normpath_oracle.py` generates the oracle table. storage (`d8d7b38`) and url-parser
  (`4dc3556`) carry the same loop.
- `np_empty`, `np_relative_pop`, `np_relative_pop_all` and the `copy_file` overwrite rows: not
  comparable (an empty path, a `..` that pops, `O_TRUNC`). `copy_file`'s identity check and
  `ftruncate` are an accepted correctness cost.
