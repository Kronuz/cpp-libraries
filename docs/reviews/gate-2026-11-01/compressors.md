# compressors: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/compressors#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `17873b2a332a34db80f7bd5938fa8be54666f398` 2026-10-28 04:27:28 -0700 "Credit Germán Méndez Bravo and bound Dubalu's years" (last origin/main commit before 2026-10-30)
- HEAD: `6bc4b4e9da579bfcf433e69181cdf9663fda0b0e` 2026-11-01 04:44:51 -0800 "Conform the README to the family standard [skip ci]" (origin/main fetched 2026-11-01 ~08:50; 13 commits after START)
- Library under test: `compressor_deflate.{h,cc}`, `compressor_lz4.{h,cc}`, `compressor_zstd.{h,cc}`, `compressor_io.h`, `compressor_scratch.h` (HEAD only), `exception.h`, `likely.h`, `xxh32_stream.h`. The START tree is HEAD's tree with those files taken from START (`git rm` then `git checkout 17873b2 -- PATHS`), so both sides use HEAD's `bench/`, `test/` and `CMakeLists.txt`. `git diff --cached --stat HEAD` of the START tree:

```
 compressor_deflate.cc |  97 +--------------------------
 compressor_deflate.h  |  16 +++--
 compressor_lz4.cc     | 182 +-------------------------------------------------
 compressor_lz4.h      |  30 +++++++--
 compressor_scratch.h  |  71 --------------------
 compressor_zstd.cc    | 133 +++++-------------------------------
 compressor_zstd.h     |  32 +++++----
 exception.h           |   2 +-
 xxh32_stream.h        | 104 ++++++++---------------------
 9 files changed, 105 insertions(+), 562 deletions(-)
```

- Benchmarks: HEAD's `bench/bench_lz4.cc`, `bench/bench_oneshot.cc`, `bench/bench_xxh32.cc` (`-DCOMPRESSORS_BENCH=ON`), built once per side. Every API they call exists at START (`compress_lz4_block`, `decompress_lz4_block`, `lz4_block_bound`, `decompress_zstd(view, max)`, the stream classes, `XXH32_*`), so no row is dropped: 48 + 104 + 15 = 167 rows on both machines, all present in both binaries.
- Rows: the benches print several columns per line. `rowfmt.py` (scratch, not kept) runs the binary and prints each column as one `label  N ns` row, so `ab_compare.py` pairs them. The benches check byte equality of every path against the stream classes and exit 1 on a mismatch; they print no checksum, so `ab_compare` has none to compare. Row suffixes: `stream` is the stream class (`LZ4CompressData`, `ZstdDecompressData`, ...), `oneshot` is `compress_*`/`decompress_*`, `bounded` is `decompress_zstd(view, max_size)`, `raw` is `compress_lz4_block`/`decompress_lz4_block`, `direct` is the codec's own call (`ZSTD_compress`, `compress2`, `uncompress`), `upstream` is xxHash v0.8.3 (`e626a72`). At START `oneshot` rows run through the stream classes, so `stream` and `oneshot` rows are the same code there; at HEAD `oneshot` has its own loop.
- Classes for the geomeans: stream-class = `stream` rows and `xxh32 ... chunks` (2 KB updates); one-shot = `oneshot`, `bounded` and `xxh32 ... one-update`; block-api = `raw`; control = `direct` and `upstream` (no library code in the timed path).

## Setup

| | Apple M4 Pro | Intel i9-9980HK |
| --- | --- | --- |
| host | the M4 Pro, 14 cores, macOS 26.7.2, arm64 | the i9, 8C/16T, macOS 15 (Darwin 24.6.0), x86_64 |
| compiler | Apple clang 17.0.0 (clang-1700.3.19.1), `/usr/bin/clang++` | Apple clang 17.0.0 (clang-1700.6.4.2), `/usr/bin/clang++` |
| flags | `-O3 -DNDEBUG -std=gnu++20 -arch arm64`, CMake Release, no `-march` | `-O3 -DNDEBUG -std=gnu++20 -arch x86_64`, CMake Release, no `-march` |
| zlib | SDK 1.2.12 | SDK 1.2.12 |
| lz4, zstd | Homebrew lz4 1.10.0, zstd 1.5.7_1 (`/opt/homebrew`) | Homebrew lz4 1.10.0, zstd 1.5.7_1 (`/usr/local`) |
| xxHash (bench control) | `e626a72bc2321cd320e953a0ccf1584cad60f363` (v0.8.3), the same checkout passed to both trees | the same SHA, fetched by the i9's own configure |
| hold | `quiet strict`, 2026-11-01 09:55:13 to 09:57:44 PST; `uptime` at start: load 21.26 24.16 19.92, at end: 19.46 22.01 19.70 | `quiet strict`, 10:14:15 to 10:17:45; `uptime` at start: load 6.41 7.79 7.25, at end: 8.21 7.59 7.26 |
| rounds | 15 (A = START, B = HEAD, A' = START again, interleaved) | 15 |

The M4 load was high for the whole hold (other sessions' unmanaged work: 14 cores, load 20); the A/A column is the measure of how much that mattered.

## Commands

```
# both machines (i9: $GATE/compressors, PREFIX=/usr/local; M4: PREFIX=/opt/homebrew)
prep.sh SRC 17873b2 6bc4b4e9da579bfcf433e69181cdf9663fda0b0e PREFIX     # worktrees head/ and start/, then
cmake -S head  -B head/build  -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DCMAKE_PREFIX_PATH=PREFIX -DCOMPRESSORS_BENCH=ON
cmake -S start -B start/build <same> -DFETCHCONTENT_SOURCE_DIR_XXHASH_UPSTREAM=head/build/_deps/xxhash_upstream-src
nice -n 19 cmake --build {head,start}/build --target compressors_bench_lz4 compressors_bench_oneshot compressors_bench_xxh32 -j4
# one strict hold per machine
quiet strict 10 "gate compressors A/B/A rounds" -- hold.sh compressors {m4,i9} 15
#   for k in lz4 oneshot xxh32:
#     ab_compare.py run --rounds 15 --format unit --output markdown --save out-M/$k w/$k.start w/$k.head
```

Builds ran outside a hold: on the M4 the `quiet light` request queued from 09:06 to 09:21 behind pending strict holds (light starved more than 15 min), the three targets then built in 3 s; on the i9 the same from 09:14 to 09:29. Raw runs (`a-NNN.txt`, `b-NNN.txt`, `aa-NNN.txt`), the markdown reports, the hold logs and the `uptime` files are in `$GATE/raw/compressors/{m4,i9}/`.

## Summary

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios. "Slow" = ratio under 0.97 and outside the A/A spread (ab_compare's verdict `slower`: the ratio is farther from 1 than the largest A/A deviation of the row).

| machine | rows | geomean | stream-class | one-shot | block-api | control | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 167 | 1.273 | 1.122 (53 rows) | 1.750 (61) | 1.005 (16) | 1.001 (37) | 1 | 0.639 `xxh32 n=256 one-update` |
| Intel i9-9980HK | 167 | 1.281 | 1.066 (53) | 1.868 (61) | 0.996 (16) | 0.997 (37) | 0 | none (lowest ratio 0.849 `zstd random 1048576B compress stream`, inside its A/A spread) |

The controls (the codecs' own calls and upstream xxHash, identical code on both sides) sit at 1.001 and 0.997, so the two sides are comparable. The one-shot paths are the big wins (lz4 decompress of 256 B 48x on the M4, 38x at 4 KB on the i9, zstd and deflate decompress of small inputs 2-3x). The stream classes gain from the faster XXH32 (every 2 KB LZ4 block is hashed) and are otherwise flat.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: `xxh32 n=256 one-update` 0.639 (START 10.8 ns, HEAD 16.9 ns; range over 15 rounds 0.21-0.66, A/A 1.000). Cause: `533bee4` "Pin the XXH32 lanes on SSE2 and read the input little-endian everywhere" adds `__asm__("" : "+r"(acc))` in `round()`, which keeps the four lanes in scalar registers on AArch64 and SSE2, as upstream xxHash does. HEAD's 16.9 ns equals upstream xxHash (16.7 ns, the `upstream` row, 1.000x). START's NEON-packed lanes were slower for long inputs (1 MiB in one update: 166834 ns against 87250, 1.91x slower) and for the same 256 B fed through the 2 KB-chunk loop (`n=256 chunks` 47.7 ns against 17.5, 2.73x slower), but faster for 256 B hashed in one update by back-to-back independent calls (10.8 ns). Unheld diagnostic (not a result): HEAD's header with only that `__asm__` line removed, compiled with the bench's flags, prints 11.0 ns for `n=256 one-update` and 48.5 ns for `chunks`, the START numbers, so the line is the whole cause. The CHANGELOG records the AArch64 and x86 gains for large inputs and the library's own users (lz4 hashes 2 KB blocks: `chunks` 2.06x to 2.73x faster for n = 16 B to 1 MiB) and does not name this row: a cost of the change that the CHANGELOG does not mention. `xxh32 n=16 one-update` is 0.810 (1.7 to 2.1 ns) and inside the A/A spread (range 0.63-0.89 at the timer's resolution). On the i9 the same rows are 1.028x and 1.375x (the pin helps there).
- Intel i9-9980HK: none.
- Second hold for the M4 row: `quiet strict`, 2026-11-01 10:19:50 to 10:20:06, `compressors_bench_xxh32` only, 25 rounds (`uptime` load 19.28 17.50 16.62 at start, 17.81 17.26 16.55 at end): `xxh32 n=256 one-update` 0.639 (10.8 ns to 16.7 ns, range 0.63-0.67 over 25 rounds, A/A 1.000), the same value as the first hold, so the row is real. `n=16 one-update` is 0.810 again (1.7 ns to 2.1 ns, range 0.63-1.00, A/A 1.000; ab_compare calls it noise because the row's A/A rounds span 0.88-1.35 at this 0.1 ns resolution). Raw runs are in `$GATE/raw/compressors/m4b/`.

Rows below 0.97 but inside the A/A spread (noise on a loaded host; not counted): M4 `zstd random 65536B decompress stream` 0.923 (A/A 1.136), `zstd random 256B decompress stream` 0.961, `lz4 random 65536B compress raw` 0.964, `lz4 random 256B decompress stream` 0.966; i9 thirteen rows between 0.849 and 0.966, all `zstd`/`deflate` rows whose own `direct` controls move as much (`zstd random 65536B compress direct` 0.940, `decompress direct` 0.954).

## Rows dropped or not comparable

- Dropped: none; every API in the three benches exists at START.
- `decompress_lz4` now sizes its buffers by the decoded data instead of the block headers (`8f57675`, with the bounds hardening in `f157dab`/`dc4474b`): a correctness and memory-safety change (a crafted 98 KB stream no longer reserves 64 MB). Both the START and HEAD `oneshot` rows decode the same bytes with the same verdict; the HEAD path is a different algorithm (own loop, no stream class), so those rows measure the one-shot rewrite (`0498bf5`), hardening included. No `lz4 ... decompress` row is slower than START on either machine (stream-class 256 B rows 0.966 on the M4 and 0.982 on the i9, both inside the A/A spread). The hardening cost, if any, is below the measurement's resolution here.
- `compress_lz4`/`decompress_lz4` rows at START go through the stream classes, so a `oneshot` ratio is the one-shot rewrite's gain, not a like-for-like kernel speed-up.
- `zstd ... compress oneshot` and `decompress oneshot` at HEAD run on the thread's reused contexts (`62e6b62`); START creates a context per call, so these rows compare designs.

## Apple M4 Pro: per-row results

### bench_lz4

| row                                    |   START |    HEAD | START/HEAD |       range |   A/A |  n | verdict |
| -------------------------------------- | ------: | ------: | ---------: | ----------: | ----: | -: | ------: |
| lz4 random 256B compress stream        |  1852.0 |  1854.0 |     0.999x |   0.95-1.08 | 1.002 | 15 |   noise |
| lz4 random 256B compress oneshot       |  1842.0 |   474.0 |     3.837x |   3.11-5.28 | 1.007 | 15 |  faster |
| lz4 random 256B compress raw           |   440.0 |   447.0 |     1.019x |   0.73-1.29 | 0.978 | 15 |   noise |
| lz4 random 256B decompress stream      |  1499.0 |  1544.0 |     0.966x |   0.93-1.08 | 0.983 | 15 |   noise |
| lz4 random 256B decompress oneshot     |  1536.0 |    31.0 |    48.484x | 40.42-50.48 | 0.990 | 15 |  faster |
| lz4 random 256B decompress raw         |    8.00 |    7.00 |     1.000x |   0.78-1.33 | 1.000 | 15 |   noise |
| lz4 random 4096B compress stream       |  3024.0 |  2720.0 |     1.110x |   1.08-1.18 | 0.979 | 15 |  faster |
| lz4 random 4096B compress oneshot      |  3034.0 |   834.0 |     3.615x |   3.46-3.93 | 0.999 | 15 |  faster |
| lz4 random 4096B compress raw          |   553.0 |   552.0 |     1.007x |   0.94-1.08 | 1.009 | 15 |   noise |
| lz4 random 4096B decompress stream     |  2322.0 |  1899.0 |     1.211x |   1.06-1.28 | 1.000 | 15 |  faster |
| lz4 random 4096B decompress oneshot    |  2366.0 |   115.0 |    20.956x | 18.51-22.16 | 0.999 | 15 |  faster |
| lz4 random 4096B decompress raw        |    47.0 |    47.0 |     1.000x |   0.92-1.13 | 1.000 | 15 |   noise |
| lz4 random 65536B compress stream      | 27500.0 | 22500.0 |     1.220x |   1.13-1.29 | 1.014 | 15 |  faster |
| lz4 random 65536B compress oneshot     | 27500.0 | 11750.0 |     2.300x |   2.23-2.47 | 1.005 | 15 |  faster |
| lz4 random 65536B compress raw         |  2208.0 |  2250.0 |     0.964x |   0.93-1.06 | 1.000 | 15 |   noise |
| lz4 random 65536B decompress stream    | 18042.0 | 12166.0 |     1.488x |   1.39-1.55 | 0.995 | 15 |  faster |
| lz4 random 65536B decompress oneshot   | 18125.0 |  1667.0 |    10.873x |  8.74-11.41 | 1.000 | 15 |  faster |
| lz4 random 65536B decompress raw       |   666.0 |   666.0 |     1.059x |   0.88-1.20 | 1.059 | 15 |   noise |
| lz4 random 1048576B compress stream    |  448834 |  353125 |     1.287x |   1.21-1.32 | 1.001 | 15 |  faster |
| lz4 random 1048576B compress oneshot   |  445000 |  226583 |     1.978x |   1.91-2.03 | 0.995 | 15 |  faster |
| lz4 random 1048576B compress raw       | 23375.0 | 22958.0 |     1.016x |   0.98-1.04 | 1.007 | 15 |   noise |
| lz4 random 1048576B decompress stream  |  256625 |  163458 |     1.575x |   1.54-1.64 | 1.002 | 15 |  faster |
| lz4 random 1048576B decompress oneshot |  256750 | 38375.0 |     6.741x |   6.29-6.98 | 1.002 | 15 |  faster |
| lz4 random 1048576B decompress raw     | 13917.0 | 13917.0 |     1.009x |   0.85-1.08 | 1.021 | 15 |   noise |
| lz4 text 256B compress stream          |  1888.0 |  1866.0 |     1.010x |   0.96-1.07 | 0.984 | 15 |   noise |
| lz4 text 256B compress oneshot         |  1858.0 |   501.0 |     3.675x |   3.42-4.06 | 0.982 | 15 |  faster |
| lz4 text 256B compress raw             |   489.0 |   512.0 |     1.009x |   0.82-1.07 | 0.958 | 15 |   noise |
| lz4 text 256B decompress stream        |  1479.0 |  1450.0 |     1.007x |   0.97-1.08 | 0.986 | 15 |   noise |
| lz4 text 256B decompress oneshot       |  1525.0 |    74.0 |    20.324x | 17.48-21.93 | 1.015 | 15 |  faster |
| lz4 text 256B decompress raw           |    58.0 |    58.0 |     1.000x |   0.98-1.05 | 1.000 | 15 |   noise |
| lz4 text 4096B compress stream         |  6723.0 |  6475.0 |     1.038x |   1.02-1.10 | 1.006 | 15 |  faster |
| lz4 text 4096B compress oneshot        |  6661.0 |  4564.0 |     1.464x |   1.43-1.52 | 0.997 | 15 |  faster |
| lz4 text 4096B compress raw            |  5190.0 |  5208.0 |     0.997x |   0.95-1.03 | 0.996 | 15 |   noise |
| lz4 text 4096B decompress stream       |  3498.0 |  3127.0 |     1.120x |   1.07-1.19 | 1.001 | 15 |  faster |
| lz4 text 4096B decompress oneshot      |  3503.0 |  1338.0 |     2.640x |   2.57-2.72 | 0.990 | 15 |  faster |
| lz4 text 4096B decompress raw          |  1387.0 |  1371.0 |     1.026x |   0.92-1.08 | 1.016 | 15 |   noise |
| lz4 text 65536B compress stream        | 84625.0 | 80459.0 |     1.048x |   1.02-1.09 | 1.000 | 15 |  faster |
| lz4 text 65536B compress oneshot       | 84625.0 | 68500.0 |     1.228x |   1.18-1.30 | 0.989 | 15 |  faster |
| lz4 text 65536B compress raw           | 78667.0 | 78666.0 |     0.992x |   0.97-1.05 | 0.998 | 15 |   noise |
| lz4 text 65536B decompress stream      | 36583.0 | 31125.0 |     1.174x |   1.14-1.24 | 0.990 | 15 |  faster |
| lz4 text 65536B decompress oneshot     | 36916.0 | 20959.0 |     1.748x |   1.69-1.81 | 1.001 | 15 |  faster |
| lz4 text 65536B decompress raw         | 23542.0 | 23459.0 |     0.998x |   0.96-1.04 | 1.009 | 15 |   noise |
| lz4 text 1048576B compress stream      | 1339833 | 1256417 |     1.068x |   1.02-1.10 | 1.003 | 15 |  faster |
| lz4 text 1048576B compress oneshot     | 1329667 | 1115000 |     1.183x |   1.16-1.24 | 1.002 | 15 |  faster |
| lz4 text 1048576B compress raw         | 1092666 | 1097917 |     0.989x |   0.96-1.06 | 0.997 | 15 |   noise |
| lz4 text 1048576B decompress stream    |  555208 |  474583 |     1.177x |   1.11-1.20 | 1.006 | 15 |  faster |
| lz4 text 1048576B decompress oneshot   |  558625 |  337458 |     1.645x |   1.60-1.77 | 1.015 | 15 |  faster |
| lz4 text 1048576B decompress raw       |  335500 |  335208 |     0.999x |   0.95-1.03 | 1.002 | 15 |   noise |

runs: START 15, HEAD 15, A/A 15; a ratio above 1 means HEAD is faster
geomean 1.673 over 48 rows (min 0.964 lz4 random 65536B compress raw; max 48.484 lz4 random 256B decompress oneshot)
per-run geomean: min 1.646, median 1.677, max 1.722 over 15 runs
A/A geomean 1.000

### bench_oneshot

| row                                        |    START |     HEAD | START/HEAD |     range |   A/A |  n | verdict |
| ------------------------------------------ | -------: | -------: | ---------: | --------: | ----: | -: | ------: |
| zstd random 256B compress stream           |    772.0 |    768.0 |     1.007x | 0.95-1.05 | 0.995 | 15 |   noise |
| zstd random 256B compress oneshot          |    773.0 |    620.0 |     1.265x | 1.19-1.30 | 1.004 | 15 |  faster |
| zstd random 256B compress direct           |    708.0 |    700.0 |     1.007x | 0.97-1.05 | 0.993 | 15 |   noise |
| zstd random 256B decompress stream         |    151.0 |    156.0 |     0.961x | 0.90-1.15 | 0.987 | 15 |   noise |
| zstd random 256B decompress oneshot        |    150.0 |     49.0 |     3.083x | 2.92-3.32 | 0.993 | 15 |  faster |
| zstd random 256B decompress bounded        |    120.0 |     48.0 |     2.479x | 2.41-2.76 | 1.000 | 15 |  faster |
| zstd random 256B decompress direct         |     92.0 |     93.0 |     0.978x | 0.94-1.02 | 1.000 | 15 |   noise |
| deflate random 256B compress stream        |   8223.0 |   8194.0 |     1.003x | 0.96-1.02 | 0.992 | 15 |   noise |
| deflate random 256B compress oneshot       |   8240.0 |   8317.0 |     1.002x | 0.93-1.03 | 1.005 | 15 |   noise |
| deflate random 256B compress direct        |   7981.0 |   8012.0 |     1.003x | 0.97-1.03 | 1.003 | 15 |   noise |
| deflate random 256B decompress stream      |    270.0 |    270.0 |     1.012x | 0.93-1.17 | 1.007 | 15 |   noise |
| deflate random 256B decompress oneshot     |    271.0 |    110.0 |     2.473x | 2.33-2.83 | 1.011 | 15 |  faster |
| deflate random 256B decompress direct      |     55.0 |     55.0 |     1.000x | 0.93-1.22 | 1.000 | 15 |   noise |
| zstd random 4096B compress stream          |   2738.0 |   2827.0 |     0.973x | 0.94-1.03 | 0.999 | 15 |   noise |
| zstd random 4096B compress oneshot         |   2725.0 |   2048.0 |     1.333x | 1.29-1.40 | 0.994 | 15 |  faster |
| zstd random 4096B compress direct          |   2647.0 |   2683.0 |     0.982x | 0.94-1.03 | 1.003 | 15 |   noise |
| zstd random 4096B decompress stream        |    266.0 |    262.0 |     1.000x | 0.95-1.11 | 0.989 | 15 |   noise |
| zstd random 4096B decompress oneshot       |    263.0 |    115.0 |     2.296x | 2.17-2.44 | 0.996 | 15 |  faster |
| zstd random 4096B decompress bounded       |    195.0 |    113.0 |     1.732x | 1.63-2.46 | 1.011 | 15 |  faster |
| zstd random 4096B decompress direct        |    137.0 |    135.0 |     1.015x | 0.97-1.25 | 1.007 | 15 |   noise |
| deflate random 4096B compress stream       |  35404.0 |  35233.0 |     1.005x | 0.96-1.03 | 0.993 | 15 |   noise |
| deflate random 4096B compress oneshot      |  35346.0 |  35358.0 |     1.003x | 0.96-1.04 | 0.989 | 15 |   noise |
| deflate random 4096B compress direct       |  34773.0 |  34783.0 |     1.004x | 0.97-1.03 | 0.996 | 15 |   noise |
| deflate random 4096B decompress stream     |    593.0 |    590.0 |     1.015x | 0.94-1.07 | 0.985 | 15 |   noise |
| deflate random 4096B decompress oneshot    |    584.0 |    379.0 |     1.546x | 1.40-1.92 | 0.988 | 15 |  faster |
| deflate random 4096B decompress direct     |    273.0 |    275.0 |     0.993x | 0.96-1.05 | 0.982 | 15 |   noise |
| zstd random 65536B compress stream         |  12959.0 |  13083.0 |     0.987x | 0.92-1.11 | 0.984 | 15 |   noise |
| zstd random 65536B compress oneshot        |  12959.0 |   9250.0 |     1.413x | 1.36-1.57 | 1.000 | 15 |  faster |
| zstd random 65536B compress direct         |  10000.0 |  10125.0 |     0.996x | 0.96-1.08 | 1.008 | 15 |   noise |
| zstd random 65536B decompress stream       |   3000.0 |   3250.0 |     0.923x | 0.78-1.22 | 1.136 | 15 |   noise |
| zstd random 65536B decompress oneshot      |   3375.0 |   1041.0 |     3.322x | 3.00-3.82 | 1.013 | 15 |  faster |
| zstd random 65536B decompress bounded      |   1125.0 |   1041.0 |     1.084x | 1.00-1.27 | 1.035 | 15 |   noise |
| zstd random 65536B decompress direct       |    750.0 |    750.0 |     1.000x | 0.85-1.27 | 1.059 | 15 |   noise |
| deflate random 65536B compress stream      |   670666 |   671875 |     0.994x | 0.93-1.07 | 1.002 | 15 |   noise |
| deflate random 65536B compress oneshot     |   664375 |   664708 |     1.001x | 0.93-1.07 | 0.997 | 15 |   noise |
| deflate random 65536B compress direct      |   661458 |   654292 |     1.007x | 0.95-1.05 | 1.004 | 15 |   noise |
| deflate random 65536B decompress stream    |   9833.0 |   9958.0 |     0.996x | 0.95-1.06 | 0.996 | 15 |   noise |
| deflate random 65536B decompress oneshot   |  10042.0 |   5333.0 |     1.883x | 1.80-1.97 | 0.984 | 15 |  faster |
| deflate random 65536B decompress direct    |   4125.0 |   4083.0 |     1.000x | 0.98-1.04 | 1.000 | 15 |   noise |
| zstd random 1048576B compress stream       |   121958 |   123875 |     0.985x | 0.92-1.05 | 0.986 | 15 |   noise |
| zstd random 1048576B compress oneshot      |   122334 |   106583 |     1.147x | 1.10-1.25 | 1.011 | 15 |  faster |
| zstd random 1048576B compress direct       |  95000.0 |  97333.0 |     0.987x | 0.95-1.08 | 0.996 | 15 |   noise |
| zstd random 1048576B decompress stream     |  41542.0 |  40667.0 |     0.993x | 0.87-1.27 | 0.937 | 15 |   noise |
| zstd random 1048576B decompress oneshot    |  40875.0 |  17916.0 |     2.246x | 2.14-2.52 | 0.932 | 15 |  faster |
| zstd random 1048576B decompress bounded    |  17959.0 |  17875.0 |     1.005x | 0.96-1.05 | 0.984 | 15 |   noise |
| zstd random 1048576B decompress direct     |  13167.0 |  13084.0 |     0.994x | 0.92-1.05 | 0.966 | 15 |   noise |
| deflate random 1048576B compress stream    | 14802042 | 14687083 |     1.009x | 1.00-1.03 | 1.008 | 15 |   noise |
| deflate random 1048576B compress oneshot   | 14708375 | 14650916 |     1.003x | 0.99-1.03 | 1.004 | 15 |   noise |
| deflate random 1048576B compress direct    | 14579792 | 14554875 |     1.002x | 0.97-1.03 | 1.001 | 15 |   noise |
| deflate random 1048576B decompress stream  |   137167 |   137209 |     1.005x | 0.91-1.07 | 1.003 | 15 |   noise |
| deflate random 1048576B decompress oneshot |   136917 |  71667.0 |     1.910x | 1.77-2.03 | 1.004 | 15 |  faster |
| deflate random 1048576B decompress direct  |  65041.0 |  65292.0 |     1.008x | 0.93-1.07 | 0.995 | 15 |   noise |
| zstd text 256B compress stream             |   1114.0 |   1107.0 |     1.018x | 0.95-1.09 | 1.008 | 15 |   noise |
| zstd text 256B compress oneshot            |   1113.0 |    951.0 |     1.172x | 1.11-1.26 | 1.012 | 15 |  faster |
| zstd text 256B compress direct             |   1048.0 |   1048.0 |     0.998x | 0.98-1.04 | 0.996 | 15 |   noise |
| zstd text 256B decompress stream           |    384.0 |    379.0 |     1.011x | 0.97-1.04 | 1.010 | 15 |   noise |
| zstd text 256B decompress oneshot          |    372.0 |    253.0 |     1.482x | 1.43-1.55 | 1.008 | 15 |  faster |
| zstd text 256B decompress bounded          |    335.0 |    252.0 |     1.324x | 1.26-1.40 | 1.006 | 15 |  faster |
| zstd text 256B decompress direct           |    311.0 |    309.0 |     1.003x | 0.96-1.04 | 1.016 | 15 |   noise |
| deflate text 256B compress stream          |   4462.0 |   4419.0 |     1.003x | 0.97-1.04 | 0.993 | 15 |   noise |
| deflate text 256B compress oneshot         |   4460.0 |   4496.0 |     1.012x | 0.97-1.05 | 1.008 | 15 |   noise |
| deflate text 256B compress direct          |   4252.0 |   4192.0 |     1.020x | 0.95-1.05 | 1.005 | 15 |   noise |
| deflate text 256B decompress stream        |   1363.0 |   1365.0 |     1.002x | 0.96-1.04 | 1.001 | 15 |   noise |
| deflate text 256B decompress oneshot       |   1358.0 |   1179.0 |     1.151x | 1.11-1.19 | 0.995 | 15 |  faster |
| deflate text 256B decompress direct        |   1358.0 |   1340.0 |     1.004x | 0.96-1.04 | 1.002 | 15 |   noise |
| zstd text 4096B compress stream            |   9586.0 |   9461.0 |     1.013x | 0.98-1.05 | 0.999 | 15 |   noise |
| zstd text 4096B compress oneshot           |   9634.0 |   8506.0 |     1.133x | 1.09-1.17 | 1.004 | 15 |  faster |
| zstd text 4096B compress direct            |   9510.0 |   9460.0 |     1.003x | 0.98-1.03 | 1.004 | 15 |   noise |
| zstd text 4096B decompress stream          |   4366.0 |   4346.0 |     1.007x | 0.94-1.06 | 1.009 | 15 |   noise |
| zstd text 4096B decompress oneshot         |   4375.0 |   4124.0 |     1.056x | 1.01-1.09 | 1.006 | 15 |  faster |
| zstd text 4096B decompress bounded         |   4215.0 |   4118.0 |     1.016x | 0.99-1.12 | 1.004 | 15 |   noise |
| zstd text 4096B decompress direct          |   4177.0 |   4160.0 |     1.012x | 0.95-1.05 | 1.014 | 15 |   noise |
| deflate text 4096B compress stream         |  32196.0 |  32296.0 |     0.999x | 0.96-1.06 | 0.992 | 15 |   noise |
| deflate text 4096B compress oneshot        |  31931.0 |  31704.0 |     1.002x | 0.96-1.06 | 1.004 | 15 |   noise |
| deflate text 4096B compress direct         |  31504.0 |  31185.0 |     1.004x | 0.95-1.07 | 0.995 | 15 |   noise |
| deflate text 4096B decompress stream       |   3098.0 |   3070.0 |     1.013x | 0.97-1.04 | 0.987 | 15 |   noise |
| deflate text 4096B decompress oneshot      |   3048.0 |   2802.0 |     1.092x | 1.05-1.15 | 0.991 | 15 |  faster |
| deflate text 4096B decompress direct       |   2756.0 |   2757.0 |     1.008x | 0.96-1.05 | 1.005 | 15 |   noise |
| zstd text 65536B compress stream           |  81208.0 |  80625.0 |     1.007x | 0.97-1.10 | 1.011 | 15 |   noise |
| zstd text 65536B compress oneshot          |  81458.0 |  77875.0 |     1.048x | 1.01-1.09 | 1.002 | 15 |   noise |
| zstd text 65536B compress direct           |  80459.0 |  79791.0 |     1.001x | 0.95-1.04 | 0.987 | 15 |   noise |
| zstd text 65536B decompress stream         |  42041.0 |  41375.0 |     0.999x | 0.97-1.07 | 1.013 | 15 |   noise |
| zstd text 65536B decompress oneshot        |  41334.0 |  40792.0 |     1.011x | 0.98-1.07 | 1.000 | 15 |   noise |
| zstd text 65536B decompress bounded        |  40708.0 |  40458.0 |     1.002x | 0.96-1.05 | 1.004 | 15 |   noise |
| zstd text 65536B decompress direct         |  40292.0 |  39875.0 |     1.000x | 0.98-1.05 | 0.999 | 15 |   noise |
| deflate text 65536B compress stream        |  1488833 |  1477209 |     1.015x | 0.94-1.06 | 1.002 | 15 |   noise |
| deflate text 65536B compress oneshot       |  1483458 |  1491500 |     0.994x | 0.96-1.07 | 0.993 | 15 |   noise |
| deflate text 65536B compress direct        |  1462667 |  1459166 |     1.007x | 0.96-1.04 | 1.009 | 15 |   noise |
| deflate text 65536B decompress stream      |  27333.0 |  26875.0 |     1.011x | 0.97-1.95 | 1.008 | 15 |   noise |
| deflate text 65536B decompress oneshot     |  27167.0 |  24375.0 |     1.109x | 1.08-1.13 | 1.022 | 15 |  faster |
| deflate text 65536B decompress direct      |  21833.0 |  21625.0 |     1.006x | 0.98-1.06 | 1.002 | 15 |   noise |
| zstd text 1048576B compress stream         |  1239000 |  1248834 |     0.995x | 0.94-1.03 | 1.008 | 15 |   noise |
| zstd text 1048576B compress oneshot        |  1238292 |  1217250 |     1.009x | 0.96-1.07 | 1.010 | 15 |   noise |
| zstd text 1048576B compress direct         |  1219792 |  1210459 |     1.009x | 0.95-1.04 | 0.992 | 15 |   noise |
| zstd text 1048576B decompress stream       |   630584 |   623916 |     1.006x | 0.95-1.06 | 1.008 | 15 |   noise |
| zstd text 1048576B decompress oneshot      |   625417 |   604750 |     1.037x | 1.00-1.06 | 0.997 | 15 |   noise |
| zstd text 1048576B decompress bounded      |   604000 |   601459 |     1.008x | 0.98-1.03 | 1.012 | 15 |   noise |
| zstd text 1048576B decompress direct       |   600458 |   597625 |     1.000x | 0.95-1.05 | 1.001 | 15 |   noise |
| deflate text 1048576B compress stream      | 26190042 | 26106125 |     1.005x | 0.99-1.02 | 1.001 | 15 |   noise |
| deflate text 1048576B compress oneshot     | 26202167 | 26228041 |     1.001x | 0.98-1.02 | 1.000 | 15 |   noise |
| deflate text 1048576B compress direct      | 26108667 | 26182000 |     0.997x | 0.99-1.02 | 1.002 | 15 |   noise |
| deflate text 1048576B decompress stream    |   468125 |   475458 |     0.988x | 0.93-1.06 | 0.981 | 15 |   noise |
| deflate text 1048576B decompress oneshot   |   464500 |   379959 |     1.236x | 1.17-1.29 | 0.977 | 15 |  faster |
| deflate text 1048576B decompress direct    |   355042 |   352333 |     1.001x | 0.96-1.05 | 0.987 | 15 |   noise |

runs: START 15, HEAD 15, A/A 15; a ratio above 1 means HEAD is faster
geomean 1.110 over 104 rows (min 0.923 zstd random 65536B decompress stream; max 3.322 zstd random 65536B decompress oneshot)
per-run geomean: min 1.096, median 1.115, max 1.134 over 15 runs
A/A geomean 1.000

### bench_xxh32

| row                        |   START |    HEAD | START/HEAD |     range |   A/A |  n | verdict |
| -------------------------- | ------: | ------: | ---------: | --------: | ----: | -: | ------: |
| xxh32 n=16 chunks          |    5.60 |    2.70 |     2.074x | 1.93-2.15 | 1.000 | 15 |  faster |
| xxh32 n=16 one-update      |    1.70 |    2.10 |     0.810x | 0.63-0.89 | 1.000 | 15 |   noise |
| xxh32 n=16 upstream        |    1.50 |    1.50 |     1.000x | 0.80-1.00 | 1.000 | 15 |   noise |
| xxh32 n=256 chunks         |    47.7 |    17.5 |     2.729x | 2.67-2.84 | 1.000 | 15 |  faster |
| xxh32 n=256 one-update     |    10.8 |    16.9 |     0.639x | 0.21-0.66 | 1.000 | 15 |  slower |
| xxh32 n=256 upstream       |    16.5 |    16.7 |     1.000x | 0.96-1.01 | 1.000 | 15 |   noise |
| xxh32 n=2048 chunks        |   361.7 |   167.5 |     2.176x | 2.10-2.23 | 1.001 | 15 |  faster |
| xxh32 n=2048 one-update    |   201.9 |   165.4 |     1.220x | 1.20-1.27 | 1.000 | 15 |  faster |
| xxh32 n=2048 upstream      |   165.2 |   165.6 |     1.000x | 0.97-1.03 | 1.004 | 15 |   noise |
| xxh32 n=65536 chunks       | 11458.0 |  5500.0 |     2.098x | 2.02-2.15 | 1.000 | 15 |  faster |
| xxh32 n=65536 one-update   | 10250.0 |  5500.0 |     1.901x | 1.82-1.94 | 1.000 | 15 |  faster |
| xxh32 n=65536 upstream     |  5416.0 |  5500.0 |     1.000x | 0.96-1.03 | 1.000 | 15 |   noise |
| xxh32 n=1048576 chunks     |  183666 | 89208.0 |     2.057x | 2.02-2.17 | 0.988 | 15 |  faster |
| xxh32 n=1048576 one-update |  166834 | 87250.0 |     1.911x | 1.83-1.96 | 1.000 | 15 |  faster |
| xxh32 n=1048576 upstream   | 86875.0 | 87417.0 |     1.001x | 0.96-1.04 | 1.000 | 15 |   noise |

runs: START 15, HEAD 15, A/A 15; a ratio above 1 means HEAD is faster
geomean 1.378 over 15 rows (min 0.639 xxh32 n=256 one-update; max 2.729 xxh32 n=256 chunks)
per-run geomean: min 1.272, median 1.360, max 1.392 over 15 runs
A/A geomean 0.999

## Intel i9-9980HK: per-row results

### bench_lz4

| row                                    |   START |    HEAD | START/HEAD |       range |   A/A |  n | verdict |
| -------------------------------------- | ------: | ------: | ---------: | ----------: | ----: | -: | ------: |
| lz4 random 256B compress stream        |  6421.0 |  6467.0 |     0.985x |   0.84-1.21 | 0.983 | 15 |   noise |
| lz4 random 256B compress oneshot       |  5760.0 |   564.0 |    10.550x |  9.43-13.52 | 1.005 | 15 |  faster |
| lz4 random 256B compress raw           |   340.0 |   386.0 |     0.971x |   0.84-1.13 | 0.997 | 15 |   noise |
| lz4 random 256B decompress stream      |  5177.0 |  5221.0 |     0.982x |   0.85-1.11 | 0.997 | 15 |   noise |
| lz4 random 256B decompress oneshot     |  5162.0 |   147.0 |    34.462x | 30.89-41.56 | 1.025 | 15 |  faster |
| lz4 random 256B decompress raw         |    15.0 |    15.0 |     1.000x |   0.88-1.33 | 1.067 | 15 |   noise |
| lz4 random 4096B compress stream       |  8022.0 |  7905.0 |     1.049x |   0.91-1.15 | 1.028 | 15 |   noise |
| lz4 random 4096B compress oneshot      |  8011.0 |  1660.0 |     4.921x |   4.10-5.30 | 1.028 | 15 |  faster |
| lz4 random 4096B compress raw          |  1068.0 |  1071.0 |     0.992x |   0.88-1.06 | 0.993 | 15 |   noise |
| lz4 random 4096B decompress stream     |  6350.0 |  6050.0 |     1.026x |   0.93-1.14 | 1.010 | 15 |   noise |
| lz4 random 4096B decompress oneshot    |  6345.0 |   166.0 |    38.019x | 33.13-42.11 | 1.019 | 15 |  faster |
| lz4 random 4096B decompress raw        |    56.0 |    56.0 |     1.000x |   0.86-1.08 | 1.000 | 15 |   noise |
| lz4 random 65536B compress stream      | 48551.0 | 44349.0 |     1.091x |   0.93-1.19 | 1.018 | 15 |   noise |
| lz4 random 65536B compress oneshot     | 48470.0 | 24344.0 |     1.987x |   1.69-2.16 | 1.012 | 15 |  faster |
| lz4 random 65536B compress raw         |  5392.0 |  5419.0 |     0.987x |   0.48-1.92 | 1.029 | 15 |   noise |
| lz4 random 65536B decompress stream    | 25816.0 | 21198.0 |     1.214x |   1.02-1.32 | 1.007 | 15 |  faster |
| lz4 random 65536B decompress oneshot   | 25748.0 |  2905.0 |     8.863x |  7.22-10.32 | 1.010 | 15 |  faster |
| lz4 random 65536B decompress raw       |  1449.0 |  1483.0 |     0.971x |   0.82-1.11 | 1.018 | 15 |   noise |
| lz4 random 1048576B compress stream    |  831865 |  884791 |     1.014x |   0.81-1.31 | 0.959 | 15 |   noise |
| lz4 random 1048576B compress oneshot   |  958983 |  545389 |     1.630x |   1.36-2.16 | 0.982 | 15 |  faster |
| lz4 random 1048576B compress raw       | 66610.0 | 66528.0 |     0.997x |   0.33-1.21 | 0.993 | 15 |   noise |
| lz4 random 1048576B decompress stream  |  470333 |  308355 |     1.613x |   0.93-1.86 | 0.975 | 15 |  faster |
| lz4 random 1048576B decompress oneshot |  463698 | 77806.0 |     5.241x |   3.94-7.09 | 1.008 | 15 |  faster |
| lz4 random 1048576B decompress raw     | 37590.0 | 35609.0 |     1.021x |   0.80-1.26 | 0.977 | 15 |   noise |
| lz4 text 256B compress stream          |  6081.0 |  5948.0 |     1.013x |   0.82-1.20 | 0.982 | 15 |   noise |
| lz4 text 256B compress oneshot         |  5784.0 |   575.0 |    10.856x |  8.88-11.96 | 1.046 | 15 |  faster |
| lz4 text 256B compress raw             |   442.0 |   490.0 |     1.002x |   0.84-1.05 | 0.995 | 15 |   noise |
| lz4 text 256B decompress stream        |  5329.0 |  5584.0 |     0.990x |   0.75-1.12 | 0.991 | 15 |   noise |
| lz4 text 256B decompress oneshot       |  5226.0 |   240.0 |    22.113x | 16.95-25.03 | 0.994 | 15 |  faster |
| lz4 text 256B decompress raw           |   121.0 |   122.0 |     0.992x |   0.69-1.69 | 1.000 | 15 |   noise |
| lz4 text 4096B compress stream         | 11751.0 | 11453.0 |     1.028x |   0.88-1.24 | 0.982 | 15 |   noise |
| lz4 text 4096B compress oneshot        | 11577.0 |  5107.0 |     2.274x |   1.87-2.63 | 0.998 | 15 |  faster |
| lz4 text 4096B compress raw            |  5471.0 |  5467.0 |     0.999x |   0.84-1.19 | 1.000 | 15 |   noise |
| lz4 text 4096B decompress stream       |  8001.0 |  7641.0 |     1.044x |   0.88-1.27 | 1.013 | 15 |   noise |
| lz4 text 4096B decompress oneshot      |  7942.0 |  1792.0 |     4.425x |   3.76-5.15 | 1.000 | 15 |  faster |
| lz4 text 4096B decompress raw          |  2031.0 |  1964.0 |     1.000x |   0.84-1.19 | 1.002 | 15 |   noise |
| lz4 text 65536B compress stream        |  106776 | 97956.0 |     1.050x |   0.88-1.25 | 1.003 | 15 |   noise |
| lz4 text 65536B compress oneshot       |  106608 | 76025.0 |     1.355x |   1.14-1.61 | 1.000 | 15 |  faster |
| lz4 text 65536B compress raw           | 88489.0 | 84702.0 |     0.999x |   0.84-1.19 | 1.000 | 15 |   noise |
| lz4 text 65536B decompress stream      | 52774.0 | 47806.0 |     1.125x |   0.70-1.53 | 1.015 | 15 |   noise |
| lz4 text 65536B decompress oneshot     | 59299.0 | 27716.0 |     1.969x |   1.01-2.52 | 1.044 | 15 |  faster |
| lz4 text 65536B decompress raw         | 34514.0 | 34396.0 |     1.001x |   0.54-1.63 | 1.002 | 15 |   noise |
| lz4 text 1048576B compress stream      | 1662606 | 1605882 |     1.045x |   0.88-1.25 | 1.033 | 15 |   noise |
| lz4 text 1048576B compress oneshot     | 1652082 | 1428409 |     1.234x |   0.96-1.46 | 0.998 | 15 |  faster |
| lz4 text 1048576B compress raw         | 1222119 | 1222458 |     1.000x |   0.88-1.22 | 1.000 | 15 |   noise |
| lz4 text 1048576B decompress stream    |  899987 |  850102 |     1.072x |   0.87-1.28 | 1.038 | 15 |   noise |
| lz4 text 1048576B decompress oneshot   |  904317 |  493660 |     1.831x |   1.51-2.06 | 1.002 | 15 |  faster |
| lz4 text 1048576B decompress raw       |  425834 |  425596 |     0.999x |   0.88-1.19 | 1.000 | 15 |   noise |

runs: START 15, HEAD 15, A/A 15; a ratio above 1 means HEAD is faster
geomean 1.749 over 48 rows (min 0.971 lz4 random 65536B decompress raw; max 38.019 lz4 random 4096B decompress oneshot)
per-run geomean: min 1.507, median 1.736, max 1.854 over 15 runs
A/A geomean 1.006

### bench_oneshot

| row                                        |    START |     HEAD | START/HEAD |     range |   A/A |  n | verdict |
| ------------------------------------------ | -------: | -------: | ---------: | --------: | ----: | -: | ------: |
| zstd random 256B compress stream           |   2343.0 |   2337.0 |     1.003x | 0.97-1.07 | 0.997 | 15 |   noise |
| zstd random 256B compress oneshot          |   2339.0 |   1927.0 |     1.222x | 1.13-1.28 | 0.994 | 15 |  faster |
| zstd random 256B compress direct           |   2042.0 |   2045.0 |     0.995x | 0.85-1.10 | 0.999 | 15 |   noise |
| zstd random 256B decompress stream         |    536.0 |    559.0 |     0.975x | 0.80-1.06 | 0.967 | 15 |   noise |
| zstd random 256B decompress oneshot        |    541.0 |    218.0 |     2.482x | 2.04-2.78 | 0.954 | 15 |  faster |
| zstd random 256B decompress bounded        |    396.0 |    217.0 |     1.800x | 1.51-2.19 | 0.988 | 15 |  faster |
| zstd random 256B decompress direct         |    238.0 |    238.0 |     0.996x | 0.77-1.17 | 1.000 | 15 |   noise |
| deflate random 256B compress stream        |  18543.0 |  18494.0 |     1.004x | 0.84-1.12 | 0.995 | 15 |   noise |
| deflate random 256B compress oneshot       |  18344.0 |  18257.0 |     0.999x | 0.85-1.03 | 0.985 | 15 |   noise |
| deflate random 256B compress direct        |  17446.0 |  17574.0 |     0.996x | 0.82-1.09 | 0.991 | 15 |   noise |
| deflate random 256B decompress stream      |    741.0 |    727.0 |     1.018x | 0.85-1.23 | 1.021 | 15 |   noise |
| deflate random 256B decompress oneshot     |    733.0 |    300.0 |     2.428x | 2.04-2.81 | 1.010 | 15 |  faster |
| deflate random 256B decompress direct      |    147.0 |    151.0 |     0.987x | 0.80-1.19 | 1.000 | 15 |   noise |
| zstd random 4096B compress stream          |   6751.0 |   7617.0 |     1.002x | 0.83-1.14 | 1.002 | 15 |   noise |
| zstd random 4096B compress oneshot         |   6738.0 |   5973.0 |     1.159x | 0.98-1.38 | 0.986 | 15 |   noise |
| zstd random 4096B compress direct          |   6438.0 |   6468.0 |     0.999x | 0.85-1.18 | 0.998 | 15 |   noise |
| zstd random 4096B decompress stream        |    480.0 |    503.0 |     0.958x | 0.84-1.20 | 0.960 | 15 |   noise |
| zstd random 4096B decompress oneshot       |    484.0 |    183.0 |     2.656x | 2.33-3.29 | 0.994 | 15 |  faster |
| zstd random 4096B decompress bounded       |    341.0 |    180.0 |     1.863x | 1.66-2.23 | 0.995 | 15 |  faster |
| zstd random 4096B decompress direct        |    244.0 |    241.0 |     1.017x | 0.89-1.19 | 1.000 | 15 |   noise |
| deflate random 4096B compress stream       |  52633.0 |  52222.0 |     1.005x | 0.84-1.17 | 0.993 | 15 |   noise |
| deflate random 4096B compress oneshot      |  52156.0 |  52570.0 |     0.993x | 0.84-1.14 | 0.994 | 15 |   noise |
| deflate random 4096B compress direct       |  51283.0 |  51272.0 |     1.001x | 0.84-1.14 | 1.003 | 15 |   noise |
| deflate random 4096B decompress stream     |    972.0 |    962.0 |     1.018x | 0.87-1.30 | 1.025 | 15 |   noise |
| deflate random 4096B decompress oneshot    |    968.0 |    469.0 |     2.023x | 1.76-2.53 | 1.017 | 15 |  faster |
| deflate random 4096B decompress direct     |    325.0 |    327.0 |     0.997x | 0.86-1.14 | 1.000 | 15 |   noise |
| zstd random 65536B compress stream         |  28594.0 |  28811.0 |     0.950x | 0.71-1.14 | 0.991 | 15 |   noise |
| zstd random 65536B compress oneshot        |  28499.0 |  20508.0 |     1.344x | 0.88-1.62 | 0.985 | 15 |  faster |
| zstd random 65536B compress direct         |  24618.0 |  25436.0 |     0.940x | 0.68-1.16 | 0.981 | 15 |   noise |
| zstd random 65536B decompress stream       |   3848.0 |   3910.0 |     0.988x | 0.83-1.12 | 0.990 | 15 |   noise |
| zstd random 65536B decompress oneshot      |   3845.0 |   2225.0 |     1.725x | 1.49-1.95 | 0.994 | 15 |  faster |
| zstd random 65536B decompress bounded      |   2391.0 |   2221.0 |     1.079x | 0.92-1.20 | 0.981 | 15 |   noise |
| zstd random 65536B decompress direct       |   1452.0 |   1490.0 |     0.954x | 0.83-1.14 | 1.001 | 15 |   noise |
| deflate random 65536B compress stream      |  1167149 |  1173319 |     0.966x | 0.85-1.15 | 1.001 | 15 |   noise |
| deflate random 65536B compress oneshot     |  1160764 |  1186342 |     0.966x | 0.84-1.06 | 0.993 | 15 |   noise |
| deflate random 65536B compress direct      |  1137431 |  1144416 |     0.995x | 0.84-1.16 | 0.991 | 15 |   noise |
| deflate random 65536B decompress stream    |  12238.0 |  12464.0 |     1.001x | 0.84-1.11 | 0.992 | 15 |   noise |
| deflate random 65536B decompress oneshot   |  12091.0 |   6478.0 |     1.873x | 1.34-2.17 | 0.986 | 15 |  faster |
| deflate random 65536B decompress direct    |   4715.0 |   4925.0 |     0.962x | 0.81-1.13 | 0.997 | 15 |   noise |
| zstd random 1048576B compress stream       |   342750 |   353306 |     0.849x | 0.63-1.27 | 0.953 | 15 |   noise |
| zstd random 1048576B compress oneshot      |   334332 |   282820 |     1.202x | 1.04-1.76 | 0.924 | 15 |   noise |
| zstd random 1048576B compress direct       |   239209 |   263834 |     0.971x | 0.83-1.24 | 0.950 | 15 |   noise |
| zstd random 1048576B decompress stream     |  85976.0 |  94119.0 |     0.953x | 0.77-1.21 | 0.932 | 15 |   noise |
| zstd random 1048576B decompress oneshot    |  81934.0 |  57896.0 |     1.540x | 1.29-1.95 | 0.919 | 15 |  faster |
| zstd random 1048576B decompress bounded    |  51035.0 |  57906.0 |     0.958x | 0.80-1.21 | 0.928 | 15 |   noise |
| zstd random 1048576B decompress direct     |  32380.0 |  36609.0 |     0.951x | 0.80-1.20 | 0.933 | 15 |   noise |
| deflate random 1048576B compress stream    | 22786342 | 22519675 |     0.998x | 0.97-1.08 | 0.997 | 15 |   noise |
| deflate random 1048576B compress oneshot   | 22835100 | 22594464 |     1.014x | 0.95-1.09 | 0.998 | 15 |   noise |
| deflate random 1048576B compress direct    | 22205767 | 21953491 |     1.002x | 0.95-1.10 | 0.999 | 15 |   noise |
| deflate random 1048576B decompress stream  |   453855 |   451881 |     0.980x | 0.69-1.32 | 0.973 | 15 |   noise |
| deflate random 1048576B decompress oneshot |   448553 |   107975 |     3.676x | 2.70-5.08 | 0.955 | 15 |  faster |
| deflate random 1048576B decompress direct  |  91460.0 |  89872.0 |     0.985x | 0.67-1.70 | 0.875 | 15 |   noise |
| zstd text 256B compress stream             |   2311.0 |   2301.0 |     0.987x | 0.83-1.20 | 0.980 | 15 |   noise |
| zstd text 256B compress oneshot            |   2296.0 |   1896.0 |     1.197x | 1.01-1.45 | 0.999 | 15 |  faster |
| zstd text 256B compress direct             |   2229.0 |   2088.0 |     1.004x | 0.89-1.19 | 0.996 | 15 |   noise |
| zstd text 256B decompress stream           |    928.0 |    844.0 |     1.031x | 0.94-1.19 | 1.032 | 15 |   noise |
| zstd text 256B decompress oneshot          |    958.0 |    550.0 |     1.588x | 1.52-1.92 | 1.031 | 15 |  faster |
| zstd text 256B decompress bounded          |    789.0 |    548.0 |     1.305x | 1.23-1.56 | 1.001 | 15 |  faster |
| zstd text 256B decompress direct           |    620.0 |    583.0 |     1.005x | 0.95-1.19 | 1.002 | 15 |   noise |
| deflate text 256B compress stream          |  39404.0 |   9215.0 |     1.086x | 0.10-9.01 | 1.066 | 15 |   noise |
| deflate text 256B compress oneshot         |   9162.0 |   9036.0 |     1.045x | 0.14-8.81 | 1.004 | 15 |   noise |
| deflate text 256B compress direct          |  34568.0 |   8442.0 |     1.185x | 0.09-8.61 | 1.008 | 15 |   noise |
| deflate text 256B decompress stream        |   2278.0 |   2269.0 |     0.990x | 0.84-1.22 | 1.034 | 15 |   noise |
| deflate text 256B decompress oneshot       |   2271.0 |   1868.0 |     1.206x | 1.00-1.50 | 1.032 | 15 |  faster |
| deflate text 256B decompress direct        |   2209.0 |   2209.0 |     0.998x | 0.84-1.22 | 1.047 | 15 |   noise |
| zstd text 4096B compress stream            |  14343.0 |  14226.0 |     0.993x | 0.84-1.23 | 1.017 | 15 |   noise |
| zstd text 4096B compress oneshot           |  14302.0 |  13211.0 |     1.069x | 0.92-1.31 | 1.009 | 15 |   noise |
| zstd text 4096B compress direct            |  13420.0 |  13893.0 |     0.988x | 0.88-1.17 | 1.004 | 15 |   noise |
| zstd text 4096B decompress stream          |   5720.0 |   5715.0 |     1.002x | 0.84-1.19 | 1.004 | 15 |   noise |
| zstd text 4096B decompress oneshot         |   5700.0 |   5373.0 |     1.068x | 0.89-1.26 | 1.000 | 15 |   noise |
| zstd text 4096B decompress bounded         |   5511.0 |   5372.0 |     1.031x | 0.91-1.22 | 0.998 | 15 |   noise |
| zstd text 4096B decompress direct          |   5338.0 |   5455.0 |     0.999x | 0.86-1.19 | 0.998 | 15 |   noise |
| deflate text 4096B compress stream         |  93520.0 |   121748 |     0.930x | 0.58-1.74 | 1.008 | 15 |   noise |
| deflate text 4096B compress oneshot        |   122479 |   116775 |     1.005x | 0.56-1.88 | 1.052 | 15 |   noise |
| deflate text 4096B compress direct         |   120984 |   110244 |     0.988x | 0.70-1.87 | 1.107 | 15 |   noise |
| deflate text 4096B decompress stream       |   5711.0 |   5706.0 |     1.001x | 0.88-1.13 | 0.999 | 15 |   noise |
| deflate text 4096B decompress oneshot      |   5680.0 |   5261.0 |     1.091x | 0.96-1.21 | 1.001 | 15 |   noise |
| deflate text 4096B decompress direct       |   5259.0 |   5268.0 |     1.000x | 0.88-1.14 | 1.000 | 15 |   noise |
| zstd text 65536B compress stream           |   156129 |   155305 |     1.018x | 0.82-1.32 | 0.998 | 15 |   noise |
| zstd text 65536B compress oneshot          |   157731 |   133092 |     1.212x | 1.01-1.46 | 0.995 | 15 |   noise |
| zstd text 65536B compress direct           |   134193 |   139478 |     0.990x | 0.85-1.19 | 1.000 | 15 |   noise |
| zstd text 65536B decompress stream         |  51840.0 |  60407.0 |     0.952x | 0.78-1.18 | 0.999 | 15 |   noise |
| zstd text 65536B decompress oneshot        |  51923.0 |  59549.0 |     0.988x | 0.80-1.22 | 0.998 | 15 |   noise |
| zstd text 65536B decompress bounded        |  55251.0 |  59337.0 |     1.023x | 0.82-1.26 | 1.000 | 15 |   noise |
| zstd text 65536B decompress direct         |  49868.0 |  51671.0 |     1.004x | 0.78-1.40 | 0.999 | 15 |   noise |
| deflate text 65536B compress stream        |  2000224 |  2003828 |     0.998x | 0.89-1.13 | 0.987 | 15 |   noise |
| deflate text 65536B compress oneshot       |  2034184 |  1967991 |     1.028x | 0.87-1.21 | 1.060 | 15 |   noise |
| deflate text 65536B compress direct        |  2005083 |  1970466 |     1.010x | 0.82-1.19 | 0.992 | 15 |   noise |
| deflate text 65536B decompress stream      |  57840.0 |  55311.0 |     1.019x | 0.84-1.18 | 1.011 | 15 |   noise |
| deflate text 65536B decompress oneshot     |  57226.0 |  50330.0 |     1.093x | 0.90-1.26 | 1.004 | 15 |   noise |
| deflate text 65536B decompress direct      |  48036.0 |  46022.0 |     1.007x | 0.84-1.18 | 1.041 | 15 |   noise |
| zstd text 1048576B compress stream         |  2286842 |  2304191 |     1.002x | 0.90-1.18 | 0.987 | 15 |   noise |
| zstd text 1048576B compress oneshot        |  2530373 |  2151475 |     1.067x | 1.01-1.23 | 1.024 | 15 |   noise |
| zstd text 1048576B compress direct         |  2200652 |  2162593 |     0.996x | 0.86-1.15 | 0.999 | 15 |   noise |
| zstd text 1048576B decompress stream       |   829139 |   829934 |     0.998x | 0.88-1.20 | 0.994 | 15 |   noise |
| zstd text 1048576B decompress oneshot      |   829782 |   794356 |     1.046x | 0.92-1.25 | 1.003 | 15 |   noise |
| zstd text 1048576B decompress bounded      |   796160 |   783579 |     1.002x | 0.88-1.20 | 1.005 | 15 |   noise |
| zstd text 1048576B decompress direct       |   776667 |   775049 |     1.000x | 0.84-1.20 | 0.994 | 15 |   noise |
| deflate text 1048576B compress stream      | 33457754 | 33306145 |     0.999x | 0.98-1.06 | 0.996 | 15 |   noise |
| deflate text 1048576B compress oneshot     | 33601347 | 33227317 |     1.005x | 0.98-1.06 | 1.008 | 15 |   noise |
| deflate text 1048576B compress direct      | 33543078 | 33303971 |     1.005x | 0.97-1.05 | 1.009 | 15 |   noise |
| deflate text 1048576B decompress stream    |  1344933 |  1331949 |     1.006x | 0.89-1.17 | 0.979 | 15 |   noise |
| deflate text 1048576B decompress oneshot   |  1388692 |   966017 |     1.427x | 1.06-1.62 | 0.921 | 15 |  faster |
| deflate text 1048576B decompress direct    |   773167 |   829791 |     1.000x | 0.84-1.19 | 0.971 | 15 |   noise |

runs: START 15, HEAD 15, A/A 15; a ratio above 1 means HEAD is faster
geomean 1.103 over 104 rows (min 0.849 zstd random 1048576B compress stream; max 3.676 deflate random 1048576B decompress oneshot)
per-run geomean: min 0.989, median 1.093, max 1.210 over 15 runs
A/A geomean 0.995

### bench_xxh32

| row                        |   START |   HEAD | START/HEAD |     range |   A/A |  n | verdict |
| -------------------------- | ------: | -----: | ---------: | --------: | ----: | -: | ------: |
| xxh32 n=16 chunks          |    14.9 |   8.30 |     1.795x | 1.52-2.13 | 1.000 | 15 |  faster |
| xxh32 n=16 one-update      |    7.20 |   7.00 |     1.028x | 0.89-1.24 | 0.987 | 15 |   noise |
| xxh32 n=16 upstream        |    4.80 |   4.80 |     1.000x | 0.83-1.17 | 1.000 | 15 |   noise |
| xxh32 n=256 chunks         |    69.3 |   40.0 |     1.726x | 1.46-2.07 | 1.000 | 15 |  faster |
| xxh32 n=256 one-update     |    51.0 |   37.1 |     1.375x | 1.17-1.63 | 1.000 | 15 |  faster |
| xxh32 n=256 upstream       |    35.4 |   35.4 |     1.000x | 0.84-1.19 | 1.000 | 15 |   noise |
| xxh32 n=2048 chunks        |   470.0 |  286.6 |     1.640x | 1.38-1.95 | 1.000 | 15 |  faster |
| xxh32 n=2048 one-update    |   448.8 |  283.7 |     1.582x | 1.33-1.88 | 1.000 | 15 |  faster |
| xxh32 n=2048 upstream      |   282.4 |  282.5 |     0.999x | 0.84-1.19 | 1.000 | 15 |   noise |
| xxh32 n=65536 chunks       | 14745.0 | 9081.0 |     1.624x | 1.37-1.93 | 1.000 | 15 |  faster |
| xxh32 n=65536 one-update   | 14550.0 | 8921.0 |     1.631x | 1.37-1.94 | 0.999 | 15 |  faster |
| xxh32 n=65536 upstream     |  8923.0 | 8924.0 |     1.000x | 0.84-1.19 | 1.000 | 15 |   noise |
| xxh32 n=1048576 chunks     |  235696 | 147780 |     1.593x | 1.34-1.89 | 1.000 | 15 |  faster |
| xxh32 n=1048576 one-update |  220529 | 136928 |     1.612x | 1.36-1.97 | 1.000 | 15 |  faster |
| xxh32 n=1048576 upstream   |  144098 | 144114 |     1.000x | 0.84-1.19 | 1.000 | 15 |   noise |

runs: START 15, HEAD 15, A/A 15; a ratio above 1 means HEAD is faster
geomean 1.336 over 15 rows (min 0.999 xxh32 n=2048 upstream; max 1.795 xxh32 n=16 chunks)
per-run geomean: min 1.152, median 1.338, max 1.548 over 15 runs
A/A geomean 0.999

SUMMARY repo=compressors m4_geomean=1.273 i9_geomean=1.281 m4_slow=1/0.639 i9_slow=0/- unexplained=0 verdict=SLOWER-ROWS

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 `xxh32 n=256 one-update` 0.639: fixed in `compressors:430870c`, `5203edb` and `94a3758`: short
  updates run start's inlined update on AArch64 and stay inline on x86, and the NEON kernel is gone.
  Every XXH32 row is at or above start on both machines: 256 B in one update takes 10.9 ns at start
  and 8.4 now on the M4 Pro, 42.8 and 32.6 on the i9. The bench has the chained-hash row (a hash that
  waits for the previous digest), and [compressors#5](https://github.com/Kronuz/compressors/issues/5)
  is closed.
