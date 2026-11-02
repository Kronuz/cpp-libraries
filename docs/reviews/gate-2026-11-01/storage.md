# storage: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/storage#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `7b9abd11eee13d1381ed79d236fe6ff6aa325e0a` 2026-10-28 04:52:55 -0700 "Credit Germán Méndez Bravo and bound Dubalu's years" (last origin/main commit before 2026-10-30)
- HEAD: `42b10539aa2ec714a57861bcd4957eccd526ddd6` 2026-11-01 05:30:38 -0800 "Pop the first component of a relative path in the vendored normalizer" (origin/main fetched 2026-11-01 ~08:50; 24 commits after START)
- Library under test: `storage.h`, `storage_fs.h`, `storage_io.h` (`storage_trace.h` and `likely.h` are identical at both). The START tree is HEAD's tree with those three files taken from START (`git rm`, `git checkout 7b9abd1 -- PATHS`), so both sides use HEAD's `examples/bench.cc`, `CMakeLists.txt` and test sources. `git diff --cached --stat HEAD` of the START tree:

```
 storage.h    | 532 +++--------------------------------------------------------
 storage_fs.h |  61 ++-----
 storage_io.h |  71 +-------
 3 files changed, 38 insertions(+), 626 deletions(-)
```

- Benchmark: HEAD's `examples/bench.cc` (`storage_bench`): 8 scenarios (small = 50000 x 256 B, large = 200 x 1 MiB; none, LZ4, zstd, deflate), write and read MB/s, plus a `raw` row after each none/LZ4/zstd scenario (liblz4/libzstd and `pwrite`/`pread` alone, no storage code: a floor and a control). It builds and runs against START's headers, so no row is dropped: 14 lines x (write, read) = 28 rows on both machines. `rowfmt.py` (scratch) turns each MB/s into ns per MB (lower is better) and carries the on-disk compression ratio as `chk`; it was equal for every row pair on both sides (no VOID row).
- One edit to the bench in every tree, identical on both sides: its scratch directory template `/tmp/storage_bench.XXXXXX` is `<scratch>/storage/tmp/sb.XXXXXX` (same APFS volume as `/tmp`, so the same filesystem), and the wrapper deletes it after each run (a run writes more than 1 GB).
- Dependencies (primary, held fixed): HEAD's CMake pins, the same checkouts in both trees (`FETCHCONTENT_SOURCE_DIR_*` from the head tree): compressors `fe0e7127512ac14c57e9083733dcd48d2b701de8`, errno-names `0ec0801ff7b4d32412d33b2c7e041c6b55f38d14`, strict-stox `5d979797b9799afcdacc0c004c229e2d61af1341`, stringified `0053465ae99fb0f344f3c7a16dc88b4ec473ceb0`. Identical SHAs on the i9.
- Supplementary stack column: START's own tree and START's own pins (compressors `ed590c87201afd270afbfbb2d58d5d467c6d23b6`, errno-names `73b74938b3a455423cdf4c0039372dc1fe3b71c7`, strict-stox `21b7941c71064b5a4e52ffb50a2701ee4aae4c6c`, stringified `5b16ec9cff9b5aebf783dfecd713e1c2a3084c42`), with HEAD's `bench.cc`, against HEAD. No A/A; fewer rounds. The verdict uses the fixed-dependency rows.

## Setup

| | Apple M4 Pro | Intel i9-9980HK |
| --- | --- | --- |
| host | the M4 Pro, 14 cores, macOS 26.7.2, arm64, internal SSD | the i9, 8C/16T, macOS 15 (Darwin 24.6.0), x86_64, internal SSD |
| compiler | Apple clang 17.0.0 (clang-1700.3.19.1), `/usr/bin/clang++` | Apple clang 17.0.0 (clang-1700.6.4.2), `/usr/bin/clang++` |
| flags | CMake Release (`-O3 -DNDEBUG`, `-std=gnu++20`), no `-march` | the same, x86_64 |
| lz4, zstd, zlib | Homebrew lz4 1.10.0, zstd 1.5.7_1; SDK zlib 1.2.12 | the same versions (`/usr/local`) |
| hold | `quiet strict`, 2026-11-01 11:25:55 to 11:32:44 PST; `uptime` load at start 11.38 14.28 13.88, at end 8.42 10.63 12.16 | `quiet strict`, 10:39:07 to 10:45:20; load at start 7.84 7.63 7.45, at end 9.37 8.31 7.79 |
| rounds | 7 (A = START, B = HEAD, A' = START again); stack 7, no A/A; diagnostic 5 | 5; stack 3, no A/A; second hold 7 (+ diagnostic 5) |

## Commands

```
# both machines (i9: $GATE/storage, PREFIX=/usr/local; M4: PREFIX=/opt/homebrew)
prep-any.sh storage SRC 7b9abd1 42b10539aa2ec714a57861bcd4957eccd526ddd6 PREFIX
#   worktrees head/ (HEAD), start/ (HEAD + START's three headers), stack/ (START's tree, HEAD's bench.cc);
#   sed on examples/bench.cc in all three (scratch dir); then per tree
cmake -S TREE -B TREE/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DCMAKE_PREFIX_PATH=PREFIX
#   start/ gets -DFETCHCONTENT_SOURCE_DIR_{COMPRESSORS,ERRNO_NAMES,STRICT_STOX,STRINGIFIED}=head/build/_deps/<name>-src
nice -n 19 cmake --build TREE/build --target storage_bench -j4
quiet strict 10 "gate storage A/B/A rounds" -- hold.sh storage {m4,i9} {7,5} {7,3}
#   ab_compare.py run --rounds N --format unit --output markdown --save out-M/storage w/storage.start w/storage.head
#   ab_compare.py run --rounds S --no-aa ... w/storage.stack w/storage.head            # stack column
```

Builds ran outside a hold: the `quiet light` requests queued from 09:06 (M4) and 09:14 (i9) behind pending strict holds and had starved for more than 15 minutes; each tree built in seconds. Raw runs, markdown reports, hold logs and `uptime` files are in `$GATE/raw/storage/{m4,i9,m4sw,i9b}/`.

## Summary

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios. Slow = under 0.97 and outside the A/A spread.

| machine | rows | geomean | engine reads (8) | engine writes (8) | raw floor rows (12, control) | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 28 | 1.007 | 1.140 | 0.897 | 1.001 | 2 | 0.704 `small blobs, lz4 write` |
| Intel i9-9980HK | 28 | 0.983 (second hold 0.978) | 0.941 (second hold 0.928) | 0.995 | 1.004 | 3 (2 in the first hold, 3 in the second) | 0.719 `large blobs, lz4 read` (second hold) |

Reads of uncompressed 1 MiB records are 1.8x (M4) and 1.14x (i9) faster at HEAD (`cc36919` reads a whole record into the result instead of a string per 2 KB chunk). Stack column (START with its own pins against HEAD, STACK/HEAD geomean): M4 1.133, i9 1.109; `small blobs, lz4` write and read are 1.8x and 2.2x (M4), 3.1x and 2.6x (i9) faster there, the compressors' lz4 one-shots. The rows that are slow in the primary comparison are also slow in the stack column, so they come from `storage.h` and not from the pins: M4 small writes `none` 0.783, `zstd` 0.906, `deflate` 0.901 (`lz4` is 1.795 there, the compressors gain); i9 `large blobs, zstd read` 0.920 (`lz4` and `deflate` are faster there).

## Rows below 0.97 outside the A/A spread

### Apple M4 Pro: 2 rows (`small blobs, lz4 write`, `small blobs, deflate write`), cause known

- `small blobs, lz4 write` 0.704 (START 5.98 ms per MB, HEAD 8.51; range over 7 rounds 0.56-0.97; A/A 0.959) and `small blobs, deflate write` 0.915 (range 0.52-1.01; A/A 1.002). The same pattern is inside the A/A spread for the other small writes: `none` 0.819, `zstd` 0.876, and for `large blobs, lz4 write` 0.918. HEAD's rounds are bimodal on these rows (for `none`: 4.0, 9.1, 4.1, 9.0, 8.5, 9.8, 5.0 ms per MB against 3.9-7.0 for START and 4.5-6.4 for the A/A copy).
- Cause: `sync_dir()` in `commit()` (`217e731`, review finding L6-N1: "commit() fsyncs the volume directory once after the storage created the file, between the data sync and the header write"). It is a durability fix (a record a commit acknowledged could vanish with its directory entry) and the CHANGELOG records the streamed write but not this cost. Evidence, second M4 hold sw (below), the small-write scenario alone as 15 fresh volumes per run: START against HEAD, medians 0.795 (`none`), 0.905 (`lz4`), 0.939 (`zstd`), 0.952 (`deflate`) with A/A 1.00-1.03, best-of-15 equal (0.97-1.00), so the cost is in the tail of the distribution; HEAD with `sync_dir()` returning at once is 1.38x, 1.26x, 1.19x, 1.12x faster (medians) and lands on the START medians (4.19 against 4.05, 6.06 against 5.85, 15.3 against 14.9, 23.7 against 23.6 ms per MB); reverting the `F_PREALLOCATE` length change from the same commit moves nothing (0.84-1.06, mixed signs). Size: a median 1.4 to 2.9 ms per MB at 12.2 MB, about 17 to 35 ms per new volume; with a 200 MiB volume it is below the noise (`large blobs` writes are 0.92-1.02, inside the spread).
- On the i9 the small writes are 0.964-1.014 (all inside the spread): the directory fsync does not show there.
- Confirmation: the second hold re-ran the scenario (same code path as the bench rows) rather than the whole bench; the first hold's 7 paired rounds and the stack column (`none` 0.783, `zstd` 0.906, `deflate` 0.901 against START with its own pins) agree.

### Intel i9-9980HK: 3 rows (`large blobs, lz4 read`, `large blobs, zstd read`, `large blobs, deflate read`), cause located

- First hold (5 rounds): `large blobs, zstd read` 0.763 (START 1.53 ms per MB, HEAD 1.98; range 0.69-0.96; A/A 1.040) and `large blobs, deflate read` 0.789 (range 0.75-0.88; A/A 0.977) outside the spread; `large blobs, lz4 read` 0.727 (range 0.69-1.14) inside it. Second i9 hold b (the whole bench again, 7 rounds, no stack column; 12:22:43 to 12:30:21; load 4.18 4.82 6.22 at start, 7.35 6.48 6.52 at end): `large blobs, lz4 read` 0.719 (range 0.59-0.76; A/A 0.955), `zstd` 0.750 (0.73-0.77; A/A 0.993), `deflate` 0.801 (0.72-0.89; A/A 1.072), all three outside the spread, so the rows are real on this host. Second-hold geomean 0.978 (first hold 0.983); the small writes are 0.977-1.023 there.
- The extra cost is the same for the three codecs (+0.41 to +0.50 ms per MB in the two holds), while the uncompressed read is faster at HEAD (1.15x). The M4 shows none of it (`large blobs` compressed reads 1.03, 1.01, 1.04). Stack column (START with its own pins against HEAD, 3 rounds): `zstd` 0.920 (slower), `lz4` 1.088 and `deflate` 1.117 (the compressors gains offset it).
- Cause: `Storage::read()` result assembly, from `cc36919` "Read whole records without per-chunk strings". The diagnostic in the second hold reads the same 1 MiB records whole (`read()`) and in 2 KB chunks (`read(buf, 2048)`, which decodes the record and copies it out but builds no result): whole `lz4` 0.683, `zstd` 0.729, `deflate` 0.756 (all outside the spread), chunked 0.953, 1.008, 0.969 (inside), and for uncompressed records whole 1.095, chunked 0.988. So decoding is as fast as at START and the added time is in building the result: HEAD grows it by doubling `resize` (zero-filled, freshly allocated pages) and copies the decoded record into it, where START appended 2 KB strings. The mechanism (zero-fill and page faults, which cost more on this x86 host than on the M4) is the likely reading and was not isolated with a variant. The CHANGELOG describes this change as an improvement ("a compressed record is served from its decompressed copy in one memcpy per doubling") and does not list this cost.

## Rows dropped or not comparable

- Dropped: none.
- Correctness changes between START and HEAD that add work to a path the bench times: `sync_dir()` (an `fsync` of the volume's directory after a volume is created, `217e731`), the volume lock taken at open (`flock` plus `fstat`), `F_PREALLOCATE` length fix on macOS (`storage_io.h`), and the damaged-record exception mapping on read. The write rows therefore compare a writer that makes the new volume's directory entry durable against one that does not.
- The streamed record write, orphan-volume reclaim and path-normalizer fixes are new or fixed surfaces the bench does not call.

## Apple M4 Pro: per-row results

### storage_bench (START vs HEAD, fixed dependencies)

| row                                 |    START |     HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | -------: | -------: | ---------: | --------: | ----: | : | ------: |
| small blobs, none write             |  4452360 |  8539710 |     0.819x | 0.43-1.11 | 0.883 | 7 |   noise |
| small blobs, none read              |  5065856 |  4980080 |     1.036x | 0.51-1.09 | 0.950 | 7 |   noise |
| small blobs, raw pwrite/pread write |  5274262 |  5393743 |     1.008x | 0.78-1.19 | 0.970 | 7 |   noise |
| small blobs, raw pwrite/pread read  |  1144427 |  1169180 |     0.982x | 0.94-1.03 | 1.016 | 7 |   noise |
| small blobs, lz4 write              |  5984440 |  8510638 |     0.704x | 0.56-0.97 | 0.959 | 7 |  slower |
| small blobs, lz4 read               |  5428882 |  5509642 |     0.984x | 0.55-1.81 | 0.985 | 7 |   noise |
| small blobs, raw lz4 write          |  7267442 |  7183908 |     1.003x | 0.96-1.16 | 1.022 | 7 |   noise |
| small blobs, raw lz4 read           |  1274535 |  1269036 |     1.000x | 0.96-1.04 | 1.002 | 7 |   noise |
| small blobs, zstd write             | 15037594 | 17123288 |     0.876x | 0.56-1.04 | 1.009 | 7 |   noise |
| small blobs, zstd read              | 11600928 | 11428571 |     1.044x | 0.73-1.32 | 0.734 | 7 |   noise |
| small blobs, raw zstd write         | 17636684 | 16891892 |     1.031x | 0.95-1.13 | 1.049 | 7 |   noise |
| small blobs, raw zstd read          |  7401924 |  7374631 |     1.007x | 0.97-1.03 | 1.000 | 7 |   noise |
| small blobs, deflate write          | 24390244 | 26525199 |     0.915x | 0.52-1.01 | 1.002 | 7 |  slower |
| small blobs, deflate read           | 15060241 | 10787487 |     1.364x | 0.71-1.51 | 1.026 | 7 |   noise |
| large blobs, none write             |  1043515 |  1067464 |     0.978x | 0.82-1.74 | 0.940 | 7 |   noise |
| large blobs, none read              |   380185 |   208438 |     1.825x | 0.51-1.84 | 1.020 | 7 |  faster |
| large blobs, raw pwrite/pread write |   160699 |   164579 |     0.962x | 0.55-8.96 | 0.935 | 7 |   noise |
| large blobs, raw pwrite/pread read  |  72167.3 |  72387.7 |     1.003x | 0.97-1.04 | 1.004 | 7 |   noise |
| large blobs, lz4 write              |  1660302 |  1862891 |     0.918x | 0.83-1.00 | 1.005 | 7 |   noise |
| large blobs, lz4 read               |   517893 |   507099 |     1.031x | 0.65-1.59 | 0.999 | 7 |   noise |
| large blobs, raw lz4 write          |  1253133 |  1243626 |     1.038x | 0.82-1.18 | 0.971 | 7 |   noise |
| large blobs, raw lz4 read           |   314446 |   314120 |     0.998x | 0.99-1.03 | 1.001 | 7 |   noise |
| large blobs, zstd write             |  2061006 |  2068252 |     1.015x | 0.90-1.33 | 0.998 | 7 |   noise |
| large blobs, zstd read              |   800448 |   784929 |     1.006x | 0.99-1.34 | 0.994 | 7 |   noise |
| large blobs, raw zstd write         |  1776514 |  1811922 |     0.984x | 0.94-1.03 | 0.977 | 7 |   noise |
| large blobs, raw zstd read          |   630358 |   630557 |     0.998x | 0.98-1.01 | 0.995 | 7 |   noise |
| large blobs, deflate write          | 27548209 | 27777778 |     0.992x | 0.98-1.01 | 1.003 | 7 |   noise |
| large blobs, deflate read           |   585035 |   565579 |     1.038x | 0.98-1.61 | 1.011 | 7 |   noise |

runs: START 7, HEAD 7, A/A 7; a ratio above 1 means HEAD is faster
geomean 1.007 over 28 rows (min 0.704 small blobs, lz4 write; max 1.825 large blobs, none read)
per-run geomean: min 0.946, median 1.001, max 1.086 over 7 runs
A/A geomean 0.979

### Stack column (STACK = START with its own pins)

| row                                 |    STACK |     HEAD | STACK/HEAD |     range | n | verdict |
| ----------------------------------- | -------: | -------: | ---------: | --------: | : | ------: |
| small blobs, none write             |  4478280 |  5302227 |     0.783x | 0.55-1.39 | 7 |  slower |
| small blobs, none read              |  5385030 |  5025126 |     1.121x | 0.56-2.13 | 7 |  faster |
| small blobs, raw pwrite/pread write |  5446623 |  5305040 |     1.033x | 0.84-1.32 | 7 |  faster |
| small blobs, raw pwrite/pread read  |  1139471 |  1140251 |     1.005x | 0.97-1.05 | 7 |   noise |
| small blobs, lz4 write              | 11600928 |  6631300 |     1.795x | 0.73-2.06 | 7 |  faster |
| small blobs, lz4 read               | 11723329 |  5402485 |     2.203x | 1.18-3.09 | 7 |  faster |
| small blobs, raw lz4 write          |  7012623 |  7241130 |     0.972x | 0.82-1.02 | 7 |   noise |
| small blobs, raw lz4 read           |  1302932 |  1280738 |     0.986x | 0.94-1.03 | 7 |   noise |
| small blobs, zstd write             | 15772871 | 17301038 |     0.906x | 0.66-1.01 | 7 |  slower |
| small blobs, zstd read              | 11990408 | 15174507 |     1.060x | 0.58-1.10 | 7 |  faster |
| small blobs, raw zstd write         | 17035775 | 16778523 |     1.022x | 0.98-1.05 | 7 |   noise |
| small blobs, raw zstd read          |  7558579 |  7363770 |     1.019x | 0.99-1.04 | 7 |   noise |
| small blobs, deflate write          | 24752475 | 27322404 |     0.901x | 0.74-1.03 | 7 |  slower |
| small blobs, deflate read           | 11961722 | 10741139 |     1.122x | 1.06-1.88 | 7 |  faster |
| large blobs, none write             |  1130199 |  1119194 |     1.010x | 0.67-1.24 | 7 |   noise |
| large blobs, none read              |   484379 |   209771 |     2.441x | 0.92-4.19 | 7 |  faster |
| large blobs, raw pwrite/pread write |   131900 |   124977 |     1.032x | 0.97-1.28 | 7 |  faster |
| large blobs, raw pwrite/pread read  |  72160.0 |  72692.4 |     1.022x | 0.97-1.06 | 7 |   noise |
| large blobs, lz4 write              |  1933114 |  1660027 |     1.179x | 0.94-1.21 | 7 |  faster |
| large blobs, lz4 read               |   845166 |   502513 |     1.709x | 1.11-2.18 | 7 |  faster |
| large blobs, raw lz4 write          |  1145082 |  1140771 |     1.009x | 0.96-1.07 | 7 |   noise |
| large blobs, raw lz4 read           |   312549 |   312862 |     1.001x | 0.99-1.01 | 7 |   noise |
| large blobs, zstd write             |  1952744 |  1859082 |     1.050x | 0.92-1.09 | 7 |  faster |
| large blobs, zstd read              |   913576 |   790764 |     1.148x | 0.88-1.17 | 7 |  faster |
| large blobs, raw zstd write         |  1588310 |  1580278 |     1.000x | 0.99-1.02 | 7 |   noise |
| large blobs, raw zstd read          |   626841 |   631832 |     0.992x | 0.99-1.01 | 7 |   noise |
| large blobs, deflate write          | 27472527 | 27548209 |     0.997x | 0.99-1.01 | 7 |   noise |
| large blobs, deflate read           |   854628 |   561640 |     1.516x | 1.00-1.57 | 7 |  faster |

runs: STACK 7, HEAD 7; a ratio above 1 means HEAD is faster
geomean 1.133 over 28 rows (min 0.783 small blobs, none write; max 2.441 large blobs, none read)
per-run geomean: min 1.029, median 1.120, max 1.186 over 7 runs

### Diagnostic: 1 MiB record reads, whole `read()` and 2 KB chunks (`largeread.cc`, in the same hold)

| row                        |  START |   HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------- | -----: | -----: | ---------: | --------: | ----: | : | ------: |
| large none read whole      | 342455 | 190664 |     1.794x | 1.75-1.84 | 0.993 | 5 |  faster |
| large none read chunked    | 288965 | 288763 |     0.989x | 0.97-1.03 | 1.005 | 5 |   noise |
| large lz4 read whole       | 467799 | 458223 |     1.022x | 1.01-1.03 | 1.000 | 5 |  faster |
| large lz4 read chunked     | 422991 | 424587 |     1.005x | 0.98-1.01 | 1.004 | 5 |   noise |
| large zstd read whole      | 761509 | 752705 |     1.011x | 1.01-1.01 | 0.996 | 5 |  faster |
| large zstd read chunked    | 718611 | 714262 |     1.000x | 0.99-1.01 | 0.996 | 5 |   noise |
| large deflate read whole   | 524643 | 519381 |     1.007x | 0.97-1.04 | 0.998 | 5 |   noise |
| large deflate read chunked | 473248 | 480270 |     0.990x | 0.95-1.01 | 0.988 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.079 over 8 rows (min 0.989 large none read chunked; max 1.794 large none read whole)
per-run geomean: min 1.072, median 1.079, max 1.083 over 5 runs
A/A geomean 0.997

### Diagnostic M4 hold sw (11:52:26 to 11:59:02; load 11.33 9.45 10.49 at start, 8.96 9.01 9.88 at end): the small write alone, 50000 x 256 B into a fresh volume (`smallwrite.cc`), median and best of 15 volumes per run

START against HEAD (5 rounds, A/A):

| row                        |    START |     HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------- | -------: | -------: | ---------: | --------: | ----: | : | ------: |
| small none write median    |  4045974 |  5445239 |     0.795x | 0.67-0.88 | 1.021 | 5 |  slower |
| small none write best      |  3822343 |  3934362 |     0.972x | 0.89-1.00 | 1.022 | 5 |   noise |
| small lz4 write median     |  5850433 |  6463935 |     0.905x | 0.64-1.08 | 1.027 | 5 |   noise |
| small lz4 write best       |  5659416 |  5696246 |     0.999x | 0.94-1.11 | 1.011 | 5 |   noise |
| small zstd write median    | 14910068 | 16070366 |     0.939x | 0.81-0.97 | 1.012 | 5 |  slower |
| small zstd write best      | 14576418 | 14797851 |     0.986x | 0.96-1.03 | 1.007 | 5 |   noise |
| small deflate write median | 23587342 | 24887323 |     0.952x | 0.91-0.97 | 1.002 | 5 |  slower |
| small deflate write best   | 23261068 | 23269499 |     1.002x | 0.98-1.01 | 1.007 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.941 over 8 rows (min 0.795 small none write median; max 1.002 small deflate write best)
per-run geomean: min 0.861, median 0.940, max 0.959 over 5 runs
A/A geomean 1.014

HEAD against HEAD with the `F_PREALLOCATE` length change reverted (copy of HEAD's `storage_io.h` in scratch; 5 rounds, no A/A):

| row                        |     HEAD | OLDFALLOC | HEAD/OLDFALLOC |     range | n | verdict |
| -------------------------- | -------: | --------: | -------------: | --------: | : | ------: |
| small none write median    |  5199060 |   5261759 |         0.963x | 0.84-1.41 | 5 |  slower |
| small none write best      |  3906707 |   4187839 |         0.936x | 0.87-1.28 | 5 |  slower |
| small lz4 write median     |  7034525 |   7744700 |         0.841x | 0.76-1.22 | 5 |  slower |
| small lz4 write best       |  5883983 |   5850747 |         1.003x | 0.97-1.08 | 5 |   noise |
| small zstd write median    | 18017799 |  16944688 |         1.060x | 0.91-1.11 | 5 |  faster |
| small zstd write best      | 15052070 |  14953663 |         1.012x | 1.00-1.02 | 5 |   noise |
| small deflate write median | 26614374 |  26090817 |         1.015x | 0.96-1.04 | 5 |   noise |
| small deflate write best   | 23963484 |  23350624 |         1.008x | 0.99-1.03 | 5 |   noise |

runs: HEAD 5, OLDFALLOC 5; a ratio above 1 means OLDFALLOC is faster
geomean 0.978 over 8 rows (min 0.841 small lz4 write median; max 1.060 small zstd write median)
per-run geomean: min 0.953, median 0.984, max 1.058 over 5 runs

HEAD against HEAD with `sync_dir()` returning at once (copy of HEAD's `storage.h` in scratch; 5 rounds, no A/A):

| row                        |     HEAD | NODIRSYNC | HEAD/NODIRSYNC |     range | n | verdict |
| -------------------------- | -------: | --------: | -------------: | --------: | : | ------: |
| small none write median    |  5907821 |   4189437 |         1.381x | 1.28-1.59 | 5 |  faster |
| small none write best      |  4180849 |   3826053 |         1.099x | 1.00-1.23 | 5 |  faster |
| small lz4 write median     |  7638320 |   6063616 |         1.260x | 1.16-1.36 | 5 |  faster |
| small lz4 write best       |  5987492 |   5727461 |         1.029x | 1.01-1.05 | 5 |   noise |
| small zstd write median    | 18205198 |  15337520 |         1.187x | 1.09-1.27 | 5 |  faster |
| small zstd write best      | 15290815 |  14783648 |         1.034x | 1.00-1.05 | 5 |  faster |
| small deflate write median | 26681484 |  23672747 |         1.115x | 1.07-1.15 | 5 |  faster |
| small deflate write best   | 23786342 |  23387511 |         1.012x | 1.00-1.03 | 5 |   noise |

runs: HEAD 5, NODIRSYNC 5; a ratio above 1 means NODIRSYNC is faster
geomean 1.134 over 8 rows (min 1.012 small deflate write best; max 1.381 small none write median)
per-run geomean: min 1.101, median 1.133, max 1.174 over 5 runs

## Intel i9-9980HK: per-row results

### storage_bench (START vs HEAD, fixed dependencies)

| row                                 |    START |     HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | -------: | -------: | ---------: | --------: | ----: | : | ------: |
| small blobs, none write             |  8695652 |  8810573 |     0.964x | 0.95-1.05 | 0.973 | 5 |   noise |
| small blobs, none read              | 13513514 | 13003901 |     1.028x | 0.99-1.06 | 0.975 | 5 |   noise |
| small blobs, raw pwrite/pread write | 13568521 | 13793103 |     0.984x | 0.97-1.05 | 0.999 | 5 |   noise |
| small blobs, raw pwrite/pread read  |  3265839 |  3364738 |     0.958x | 0.90-1.05 | 0.913 | 5 |   noise |
| small blobs, lz4 write              | 11547344 | 11376564 |     1.005x | 0.98-1.07 | 1.006 | 5 |   noise |
| small blobs, lz4 read               | 15174507 | 14347202 |     1.067x | 1.00-1.13 | 1.014 | 5 |   noise |
| small blobs, raw lz4 write          | 16260163 | 16181230 |     0.991x | 0.88-1.11 | 1.063 | 5 |   noise |
| small blobs, raw lz4 read           |  3532321 |  3439972 |     1.042x | 0.86-1.09 | 1.020 | 5 |   noise |
| small blobs, zstd write             | 25839793 | 25974026 |     1.008x | 0.91-1.08 | 1.013 | 5 |   noise |
| small blobs, zstd read              | 23094688 | 21367521 |     1.090x | 1.00-1.12 | 1.009 | 5 |  faster |
| small blobs, raw zstd write         | 35211268 | 32573290 |     1.035x | 0.98-1.12 | 0.983 | 5 |   noise |
| small blobs, raw zstd read          | 11337868 | 10964912 |     1.046x | 0.98-1.08 | 0.997 | 5 |   noise |
| small blobs, deflate write          | 48076923 | 46728972 |     1.014x | 1.00-1.16 | 1.038 | 5 |   noise |
| small blobs, deflate read           | 23419204 | 22573363 |     1.026x | 1.00-1.11 | 0.993 | 5 |   noise |
| large blobs, none write             |  3311258 |  3249919 |     1.000x | 0.89-1.30 | 0.994 | 5 |   noise |
| large blobs, none read              |  1153669 |   979720 |     1.141x | 1.10-1.38 | 1.002 | 5 |  faster |
| large blobs, raw pwrite/pread write |   424556 |   425441 |     0.992x | 0.98-7.23 | 1.003 | 5 |   noise |
| large blobs, raw pwrite/pread read  |   187998 |   177730 |     1.026x | 0.94-1.86 | 1.031 | 5 |   noise |
| large blobs, lz4 write              |  3091190 |  3145643 |     0.983x | 0.93-1.62 | 1.014 | 5 |   noise |
| large blobs, lz4 read               |  1126507 |  1595151 |     0.727x | 0.69-1.14 | 0.994 | 5 |   noise |
| large blobs, raw lz4 write          |  1579529 |  1608234 |     1.003x | 0.95-1.34 | 0.994 | 5 |   noise |
| large blobs, raw lz4 read           |   465398 |   487329 |     0.950x | 0.87-1.02 | 0.987 | 5 |   noise |
| large blobs, zstd write             |  3648304 |  3755163 |     0.998x | 0.91-1.16 | 1.009 | 5 |   noise |
| large blobs, zstd read              |  1533507 |  1976675 |     0.763x | 0.69-0.96 | 1.040 | 5 |  slower |
| large blobs, raw zstd write         |  3095017 |  2998501 |     1.016x | 0.97-1.05 | 1.037 | 5 |   noise |
| large blobs, raw zstd read          |   937207 |   900414 |     1.011x | 0.94-1.09 | 0.988 | 5 |   noise |
| large blobs, deflate write          | 48543689 | 48543689 |     0.990x | 0.98-1.01 | 1.005 | 5 |  slower |
| large blobs, deflate read           |  1751313 |  2220249 |     0.789x | 0.75-0.88 | 0.977 | 5 |  slower |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.983 over 28 rows (min 0.727 large blobs, lz4 read; max 1.141 large blobs, none read)
per-run geomean: min 0.971, median 0.985, max 1.171 over 5 runs
A/A geomean 1.002

### Stack column

| row                                 |    STACK |     HEAD | STACK/HEAD |     range | n | verdict |
| ----------------------------------- | -------: | -------: | ---------: | --------: | : | ------: |
| small blobs, none write             |  8771930 |  8561644 |     1.031x | 1.00-1.04 | 3 |  faster |
| small blobs, none read              | 13386881 | 13037810 |     1.027x | 0.98-1.20 | 3 |   noise |
| small blobs, raw pwrite/pread write | 13440860 | 13812155 |     0.973x | 0.90-1.06 | 3 |   noise |
| small blobs, raw pwrite/pread read  |  3360215 |  3304693 |     1.002x | 0.96-1.06 | 3 |   noise |
| small blobs, lz4 write              | 35335689 | 11248594 |     3.067x | 3.02-3.21 | 3 |  faster |
| small blobs, lz4 read               | 37593985 | 14347202 |     2.630x | 2.62-2.64 | 3 |  faster |
| small blobs, raw lz4 write          | 15625000 | 16420361 |     0.950x | 0.95-1.00 | 3 |  slower |
| small blobs, raw lz4 read           |  3436426 |  3557453 |     0.961x | 0.88-0.99 | 3 |  slower |
| small blobs, zstd write             | 29761905 | 26525199 |     1.128x | 1.05-1.16 | 3 |  faster |
| small blobs, zstd read              | 23696682 | 22624434 |     1.068x | 1.04-1.08 | 3 |  faster |
| small blobs, raw zstd write         | 35211268 | 34722222 |     1.007x | 1.00-1.01 | 3 |   noise |
| small blobs, raw zstd read          | 11520737 | 11441648 |     0.999x | 0.99-1.08 | 3 |   noise |
| small blobs, deflate write          | 48309179 | 46948357 |     1.029x | 0.98-1.04 | 3 |   noise |
| small blobs, deflate read           | 26246719 | 22831050 |     1.110x | 1.11-1.16 | 3 |  faster |
| large blobs, none write             |  3411805 |  3182686 |     1.005x | 0.90-1.22 | 3 |   noise |
| large blobs, none read              |  1168224 |   951656 |     1.267x | 1.20-1.29 | 3 |  faster |
| large blobs, raw pwrite/pread write |   425333 |   433107 |     0.982x | 0.87-1.00 | 3 |   noise |
| large blobs, raw pwrite/pread read  |   173874 |   171996 |     1.023x | 0.97-1.08 | 3 |   noise |
| large blobs, lz4 write              |  3424658 |  3034901 |     1.100x | 1.05-1.13 | 3 |  faster |
| large blobs, lz4 read               |  1682935 |  1580278 |     1.088x | 1.02-1.11 | 3 |  faster |
| large blobs, raw lz4 write          |  1526718 |  1541545 |     0.976x | 0.97-1.08 | 3 |   noise |
| large blobs, raw lz4 read           |   506329 |   493340 |     1.006x | 0.97-1.08 | 3 |   noise |
| large blobs, zstd write             |  4228330 |  3785011 |     1.109x | 1.09-1.12 | 3 |  faster |
| large blobs, zstd read              |  1761184 |  1879346 |     0.920x | 0.87-0.94 | 3 |  slower |
| large blobs, raw zstd write         |  3137747 |  3095975 |     0.996x | 1.00-1.02 | 3 |   noise |
| large blobs, raw zstd read          |   926012 |   948317 |     1.007x | 0.91-1.06 | 3 |   noise |
| large blobs, deflate write          | 48309179 | 48076923 |     1.005x | 0.99-1.01 | 3 |   noise |
| large blobs, deflate read           |  2417795 |  2212389 |     1.117x | 1.02-1.16 | 3 |  faster |

runs: STACK 3, HEAD 3; a ratio above 1 means HEAD is faster
geomean 1.109 over 28 rows (min 0.920 large blobs, zstd read; max 3.067 small blobs, lz4 write)
per-run geomean: min 1.103, median 1.110, max 1.116 over 3 runs

### Second i9 hold b: storage_bench again (7 rounds, A/A)

| row                                 |    START |     HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------------- | -------: | -------: | ---------: | --------: | ----: | : | ------: |
| small blobs, none write             |  8361204 |  8643042 |     0.977x | 0.93-1.10 | 0.987 | 7 |   noise |
| small blobs, none read              | 13568521 | 13175231 |     1.045x | 0.94-1.25 | 0.991 | 7 |   noise |
| small blobs, raw pwrite/pread write | 13227513 | 13386881 |     0.984x | 0.93-1.08 | 1.007 | 7 |   noise |
| small blobs, raw pwrite/pread read  |  3270111 |  3330003 |     1.013x | 0.95-1.04 | 1.025 | 7 |   noise |
| small blobs, lz4 write              | 11111111 | 11086475 |     0.990x | 0.91-1.06 | 0.987 | 7 |   noise |
| small blobs, lz4 read               | 14641288 | 14285714 |     1.025x | 0.87-1.12 | 0.997 | 7 |   noise |
| small blobs, raw lz4 write          | 15455951 | 16025641 |     1.003x | 0.84-1.06 | 1.017 | 7 |   noise |
| small blobs, raw lz4 read           |  3439972 |  3514938 |     0.969x | 0.68-1.07 | 0.999 | 7 |   noise |
| small blobs, zstd write             | 25839793 | 25575448 |     0.982x | 0.93-1.03 | 0.987 | 7 |   noise |
| small blobs, zstd read              | 21978022 | 21097046 |     1.017x | 0.94-1.11 | 1.031 | 7 |   noise |
| small blobs, raw zstd write         | 33557047 | 33898305 |     0.983x | 0.96-1.06 | 1.003 | 7 |   noise |
| small blobs, raw zstd read          | 10952903 | 10799136 |     1.014x | 0.98-1.10 | 1.003 | 7 |   noise |
| small blobs, deflate write          | 46728972 | 45248869 |     1.023x | 0.91-1.07 | 1.023 | 7 |   noise |
| small blobs, deflate read           | 22371365 | 21978022 |     1.018x | 0.93-1.05 | 0.998 | 7 |   noise |
| large blobs, none write             |  3122073 |  3063725 |     1.022x | 0.95-1.33 | 1.017 | 7 |   noise |
| large blobs, none read              |  1105705 |   934842 |     1.152x | 1.12-1.26 | 1.011 | 7 |  faster |
| large blobs, raw pwrite/pread write |   329717 |   323551 |     1.019x | 1.00-3.28 | 1.011 | 7 |   noise |
| large blobs, raw pwrite/pread read  |   185336 |   179565 |     1.004x | 0.98-1.13 | 1.025 | 7 |   noise |
| large blobs, lz4 write              |  2865330 |  2937720 |     0.977x | 0.97-1.00 | 0.974 | 7 |   noise |
| large blobs, lz4 read               |  1086012 |  1504664 |     0.719x | 0.59-0.76 | 0.955 | 7 |  slower |
| large blobs, raw lz4 write          |  1426534 |  1410636 |     1.031x | 0.94-1.31 | 1.035 | 7 |   noise |
| large blobs, raw lz4 read           |   443262 |   461255 |     1.031x | 0.78-1.11 | 0.958 | 7 |   noise |
| large blobs, zstd write             |  3505082 |  3680530 |     0.978x | 0.89-1.00 | 0.986 | 7 |   noise |
| large blobs, zstd read              |  1376084 |  1871608 |     0.750x | 0.73-0.77 | 0.993 | 7 |  slower |
| large blobs, raw zstd write         |  2908668 |  2830456 |     1.031x | 0.99-1.12 | 1.013 | 7 |   noise |
| large blobs, raw zstd read          |   879894 |   914829 |     0.950x | 0.91-1.03 | 0.984 | 7 |   noise |
| large blobs, deflate write          | 46948357 | 47169811 |     0.991x | 0.98-1.00 | 1.005 | 7 |   noise |
| large blobs, deflate read           |  1671402 |  2083333 |     0.801x | 0.72-0.89 | 1.072 | 7 |  slower |

runs: START 7, HEAD 7, A/A 7; a ratio above 1 means HEAD is faster
geomean 0.978 over 28 rows (min 0.719 large blobs, lz4 read; max 1.152 large blobs, none read)
per-run geomean: min 0.956, median 0.977, max 1.021 over 7 runs
A/A geomean 1.003

### Diagnostic in the second hold: 1 MiB record reads, whole `read()` and 2 KB chunks (5 rounds, A/A)

| row                        |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| large none read whole      |  962798 |  865005 |     1.095x | 1.06-1.16 | 0.966 | 5 |   noise |
| large none read chunked    |  735646 |  749183 |     0.988x | 0.92-1.00 | 0.993 | 5 |   noise |
| large lz4 read whole       |  877537 | 1285643 |     0.683x | 0.56-0.71 | 0.987 | 5 |  slower |
| large lz4 read chunked     |  662499 |  679563 |     0.953x | 0.86-1.01 | 0.945 | 5 |   noise |
| large zstd read whole      | 1212095 | 1670270 |     0.729x | 0.67-0.79 | 0.989 | 5 |  slower |
| large zstd read chunked    | 1036381 | 1030469 |     1.008x | 0.95-1.05 | 0.987 | 5 |   noise |
| large deflate read whole   | 1394661 | 1868821 |     0.756x | 0.66-0.82 | 0.980 | 5 |  slower |
| large deflate read chunked | 1205985 | 1236518 |     0.969x | 0.92-1.06 | 0.991 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.886 over 8 rows (min 0.683 large lz4 read whole; max 1.095 large none read whole)
per-run geomean: min 0.841, median 0.885, max 0.903 over 5 runs
A/A geomean 0.980

SUMMARY repo=storage m4_geomean=1.007 i9_geomean=0.983 m4_slow=2/0.704 i9_slow=3/0.719 unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 small blobs, lz4 write 0.704 and deflate write 0.915: accepted. `commit()` syncs the volume
  directory once after creating the file (`storage:217e731`), a durability fix; the CHANGELOG records
  the cost.
- i9 large blobs, whole read: lz4 0.719, zstd 0.763, deflate 0.789: fixed in `storage:890cc71` (test
  `9e8c856`). A whole `read()` is sized once from the record and decoded in place; compressed whole
  reads on the i9 are 1.17 to 1.65 times start's speed (lz4 per MiB: 929,661 ns at start, 1,401,993
  at the gate's head, 591,983 now).
