# flume: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/flume#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `7184cb4137aef0853001baea52ddc52731c3ab43` 2026-10-22 04:39:34 -0700 "Link the shared C++ library catalog [skip ci]" (last origin/main commit before 2026-10-30)
- HEAD: `20a3e8cf4e971c6f167065516f9057a857be518d` 2026-11-01 05:58:00 -0800 "Measure the codec throughput on two machines and restore it" (origin/main fetched 2026-11-01 ~08:50; 5 commits after START)
- Library under test: `flume.h` (the only library file). The START tree is HEAD's tree with `flume.h` taken from START (`git rm`, `git checkout 7184cb4 -- flume.h`), so both sides use HEAD's `benchmarks/bench.cc`, `CMakeLists.txt` and test sources. `git diff --cached --stat HEAD` of the START tree: `flume.h | 57 +++++-------------------` (7 insertions, 50 deletions).
- What changed in `flume.h` (`git diff START..HEAD -- flume.h`): `Receiver(sink, max_block = 0)`, an opt-in cap for untrusted senders (checks `max_block_ != 0` before waiting for a block, picks `Codec::decompress(block, max_block_)` when the codec has it, bounds the decoded size, releases the buffer on `Error`); `max_block_for(block_size)`; `ZstdCodec::decompress(view, max_size)`; comment text. With the default `max_block = 0` the receive path gains a few predictable compares per block. `Sender` is textually unchanged.
- Benchmark as shipped: HEAD's `benchmarks/bench.cc` (zstd L1/L3/L6/L9, lz4, deflate over a 32 MiB replication-like corpus in 64 KB blocks) calls `ZstdCodec<N>::compress/decompress(view)` and the compressors codecs directly. It never instantiates `Sender` or `Receiver`, so it cannot see any change in `flume.h`: the `flume_bench` binaries built against START's and HEAD's `flume.h` are byte-identical (`cmp` says so on both machines). Its rows therefore measure the compressors library, which is held fixed, and are a second noise control (identical binary, still up to 0.96-1.08 per row on the i9).
- Added row set (micro-bench, scratch only: `$GATE/flume/micro.cc`, 58 lines, appended to each tree's CMake as target `flume_micro`): an 8 MiB payload written to a file; `Sender<Writer>` sends it through an in-memory writer, `Receiver<Sink>` is fed the framed bytes in chunks; best of 9 passes, ns per MiB of plain data, `chk` = hash of the framed bytes (send) and byte count mixed with sampled bytes (receive), equal on both sides. Rows: `L1 text 64K feed 64K`, `L1 text 64K feed 1K`, `L1 text 4K feed 512` (many small blocks and partial feeds), `L1 random 64K feed 4K`, `L1 zeros 64K feed 4K` (cheap decode, so the Receiver's own per-block work shows), and `L6 text 64K feed 64K` (`ZstdCodec<>`, flume's default), each as `send` and `receive`. `send` runs the unchanged Sender and acts as a control; `receive` runs the changed Receiver. It uses only API that exists at START, so no row is dropped.
- Rows dropped: none. Not measured: `Receiver(sink, max_block)` with a cap (new API; the default path is what existing callers run).

## Setup

| | Apple M4 Pro | Intel i9-9980HK |
| --- | --- | --- |
| host | the M4 Pro, 14 cores, macOS 26.7.2, arm64 | the i9, 8C/16T, macOS 15 (Darwin 24.6.0), x86_64 |
| compiler | Apple clang 17.0.0 (clang-1700.3.19.1), `/usr/bin/clang++` | Apple clang 17.0.0 (clang-1700.6.4.2), `/usr/bin/clang++` |
| flags | CMake Release (`-O3 -DNDEBUG`, `-std=gnu++20` from the targets), no `-march` | the same, `-arch x86_64` |
| compressors (fixed) | `8f57675a9630590419ccd1f748720eafb542165f`, HEAD's CMake pin, the same checkout (`FETCHCONTENT_SOURCE_DIR_COMPRESSORS`) in both trees | the same SHA, fetched by the i9's own configure |
| lz4, zstd, zlib | Homebrew lz4 1.10.0, zstd 1.5.7_1; SDK zlib 1.2.12 | the same versions (`/usr/local`) |
| hold | `quiet strict`, 2026-11-01 10:56:48 to 10:59:56 PST; `uptime` load at start 11.58 12.33 14.08, at end 10.33 11.52 13.38 | `quiet strict`, 10:52:46 to 10:57:07; load at start 6.19 7.25 7.43, at end 8.26 7.60 7.49 |
| rounds | 15 (A = START, B = HEAD, A' = START again, interleaved) | 12 |

## Commands

```
# both machines (i9: $GATE/flume, PREFIX=/usr/local; M4: PREFIX=/opt/homebrew)
prep-any.sh flume SRC 7184cb4 20a3e8cf4e971c6f167065516f9057a857be518d PREFIX
#   worktrees head/ (HEAD), start/ (HEAD + START's flume.h), stack/ (START's own tree with HEAD's bench.cc);
#   micro.cc target appended to the CMakeLists of all three; then per tree
cmake -S TREE -B TREE/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=/usr/bin/clang++ -DCMAKE_PREFIX_PATH=PREFIX
#   start/ gets -DFETCHCONTENT_SOURCE_DIR_COMPRESSORS=head/build/_deps/compressors-src
nice -n 19 cmake --build TREE/build --target flume_bench flume_micro -j4
quiet strict 10 "gate flume A/B/A rounds" -- hold.sh flume {m4,i9} {15,12}
#   ab_compare.py run --rounds N --format unit --output markdown --save out-M/micro w/micro.start w/micro.head
#   ab_compare.py run --rounds N ... w/codec.start w/codec.head
#   supplementary, no A/A: w/micro.stack w/micro.head and w/codec.stack w/codec.head
```

`w/codec.*` and `w/micro.*` are wrappers (`rowfmt.py`) that run the binary and print each number as a `label  N ns` row (throughputs become ns per MB; the codec rows carry the compressed byte count as `chk`, equal on both sides). Builds ran outside a hold: the `quiet light` requests queued from 09:06 (M4) and 09:14 (i9) behind pending strict holds and had starved for more than 15 minutes; each target set built in seconds. Raw runs, markdown reports, hold logs and `uptime` files are in `$GATE/raw/flume/{m4,i9}/`.

## Summary

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios. Slow = under 0.97 and outside the A/A spread.

| machine | rows | geomean | micro `send` (control) | micro `receive` | `bench.cc` codec rows (identical binary) | rows < 0.97 outside A/A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Apple M4 Pro | 24 (12 micro + 12 codec) | 1.001 | 1.001 | 0.999 | 1.002 | 0 |
| Intel i9-9980HK | 24 | 1.006 | 0.978 | 1.013 | 1.018 | 0 |

Supplementary stack column (START with the compressors SHA its own CMake pinned, `ed590c87201afd270afbfbb2d58d5d467c6d23b6`, against HEAD with `8f57675`; no A/A, tables below): geomean of STACK/HEAD on the M4 is 1.176 for micro and 1.125 for the codec rows, on the i9 1.007 and 1.139. These come from the compressors work (lz4 decompress up to 2.7x on the M4, zstd one-shots), not from `flume.h`. The verdict uses the fixed-compressors rows.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: none.
- Intel i9-9980HK: none.

Rows below 0.97 but inside the A/A spread (noise; not counted): i9 `L1 text 64K feed 1K send` 0.956, `L1 text 64K feed 64K send` 0.964, `L1 text 4K feed 512 send` 0.969, `deflate/zlib decompress` 0.963 (A/A 1.055). The `send` rows run `Sender`, which `git diff` shows unchanged, and `deflate/zlib decompress` runs in a binary identical for both sides, so these are the i9's noise floor under other sessions' load.

## Notes

- The Receiver's default path (no cap) costs nothing measurable: `receive` rows are 0.999 (M4) and 1.013 (i9) against `send` control rows at 1.001 and 0.978.
- Behavior with `max_block` set is new API and not part of this comparison.
- This is a micro-bench plus a codec bench that does not touch the changed code. `examples/pipe_file.cc` is the only other program in the repo and is not a benchmark.

## Apple M4 Pro: per-row results

### micro (Sender / Receiver)

| row                           |   START |    HEAD | START/HEAD |     range |   A/A |  n | verdict |
| ----------------------------- | ------: | ------: | ---------: | --------: | ----: | -: | ------: |
| L1 text 64K feed 64K send     | 1971438 | 1980245 |     0.999x | 0.98-1.03 | 1.000 | 15 |   noise |
| L1 text 64K feed 64K receive  | 1050281 | 1050885 |     0.996x | 0.98-1.02 | 0.999 | 15 |   noise |
| L1 text 64K feed 1K send      | 1975234 | 1966854 |     1.003x | 0.98-1.03 | 0.999 | 15 |   noise |
| L1 text 64K feed 1K receive   | 1056500 | 1054766 |     1.000x | 0.98-1.03 | 1.006 | 15 |   noise |
| L1 text 4K feed 512 send      | 3626880 | 3618479 |     1.001x | 0.98-1.05 | 1.003 | 15 |   noise |
| L1 text 4K feed 512 receive   | 1689276 | 1692651 |     0.996x | 0.99-1.01 | 0.999 | 15 |   noise |
| L1 random 64K feed 4K send    |  279651 |  278375 |     1.004x | 0.92-1.10 | 0.979 | 15 |   noise |
| L1 random 64K feed 4K receive |  150750 |  150557 |     1.015x | 0.98-1.03 | 0.991 | 15 |   noise |
| L1 zeros 64K feed 4K send     |  176354 |  176167 |     1.001x | 0.94-1.11 | 0.994 | 15 |   noise |
| L1 zeros 64K feed 4K receive  |  433781 |  435432 |     0.990x | 0.95-1.03 | 0.987 | 15 |   noise |
| L6 text 64K feed 64K send     | 7241010 | 7246234 |     0.999x | 0.99-1.01 | 1.002 | 15 |   noise |
| L6 text 64K feed 64K receive  |  890958 |  889432 |     0.996x | 0.98-1.02 | 0.997 | 15 |   noise |

runs: START 15, HEAD 15, A/A 15; a ratio above 1 means HEAD is faster
geomean 1.000 over 12 rows (min 0.990 L1 zeros 64K feed 4K receive; max 1.015 L1 random 64K feed 4K receive)
per-run geomean: min 0.988, median 1.002, max 1.021 over 15 runs
A/A geomean 0.996

### benchmarks/bench.cc (codec rows)

| row                                |   START |    HEAD | START/HEAD |     range |   A/A |  n | verdict |
| ---------------------------------- | ------: | ------: | ---------: | --------: | ----: | -: | ------: |
| lz4 (classic) compress             |  484966 |  487092 |     1.000x | 0.92-1.05 | 0.987 | 15 |   noise |
| lz4 (classic) decompress           |  126438 |  127535 |     1.009x | 0.92-1.05 | 0.996 | 15 |   noise |
| deflate/zlib compress              | 4694836 | 4739336 |     0.991x | 0.95-1.03 | 0.990 | 15 |   noise |
| deflate/zlib decompress            |  385802 |  384172 |     1.012x | 0.98-1.05 | 1.002 | 15 |   noise |
| zstd L1 (fast) compress            |  602410 |  602410 |     0.997x | 0.97-1.03 | 1.003 | 15 |   noise |
| zstd L1 (fast) decompress          |  333778 |  332447 |     1.001x | 0.98-1.06 | 0.997 | 15 |   noise |
| zstd L3 (zstd default) compress    |  734754 |  733138 |     1.000x | 0.99-1.03 | 1.001 | 15 |   noise |
| zstd L3 (zstd default) decompress  |  330907 |  328515 |     1.007x | 0.98-1.03 | 1.001 | 15 |   noise |
| zstd L6 (flume default) compress   | 2840909 | 2824859 |     1.006x | 0.98-1.03 | 1.008 | 15 |   noise |
| zstd L6 (flume default) decompress |  284252 |  286041 |     0.997x | 0.98-1.03 | 1.000 | 15 |   noise |
| zstd L9 compress                   | 5154639 | 5154639 |     1.000x | 0.98-1.02 | 1.000 | 15 |   noise |
| zstd L9 decompress                 |  273523 |  273000 |     1.002x | 0.97-1.02 | 0.988 | 15 |   noise |

runs: START 15, HEAD 15, A/A 15; a ratio above 1 means HEAD is faster
geomean 1.002 over 12 rows (min 0.991 deflate/zlib compress; max 1.012 deflate/zlib decompress)
per-run geomean: min 0.992, median 1.002, max 1.015 over 15 runs
A/A geomean 0.998

### Stack column (STACK = START with its own pinned compressors), micro

| row                           |   STACK |    HEAD | STACK/HEAD |     range |  n | verdict |
| ----------------------------- | ------: | ------: | ---------: | --------: | -: | ------: |
| L1 text 64K feed 64K send     | 2050042 | 1945448 |     1.048x | 1.04-1.07 | 15 |  faster |
| L1 text 64K feed 64K receive  | 1138167 | 1043568 |     1.093x | 1.08-1.11 | 15 |  faster |
| L1 text 64K feed 1K send      | 2048698 | 1941333 |     1.047x | 1.02-1.07 | 15 |  faster |
| L1 text 64K feed 1K receive   | 1147307 | 1042547 |     1.089x | 1.08-1.12 | 15 |  faster |
| L1 text 4K feed 512 send      | 3686922 | 3598203 |     1.024x | 1.01-1.05 | 15 |   noise |
| L1 text 4K feed 512 receive   | 1769599 | 1673901 |     1.057x | 1.04-1.07 | 15 |  faster |
| L1 random 64K feed 4K send    |  370495 |  273443 |     1.376x | 1.25-1.49 | 15 |  faster |
| L1 random 64K feed 4K receive |  247036 |  148438 |     1.674x | 1.60-1.75 | 15 |  faster |
| L1 zeros 64K feed 4K send     |  274552 |  172000 |     1.573x | 1.38-1.71 | 15 |  faster |
| L1 zeros 64K feed 4K receive  |  526198 |  431401 |     1.217x | 1.16-1.28 | 15 |  faster |
| L6 text 64K feed 64K send     | 7300969 | 7188141 |     1.015x | 1.00-1.03 | 15 |   noise |
| L6 text 64K feed 64K receive  |  981656 |  886380 |     1.107x | 1.10-1.12 | 15 |  faster |

runs: STACK 15, HEAD 15; a ratio above 1 means HEAD is faster
geomean 1.176 over 12 rows (min 1.015 L6 text 64K feed 64K send; max 1.674 L1 random 64K feed 4K receive)
per-run geomean: min 1.146, median 1.176, max 1.204 over 15 runs

### Stack column, codec rows

| row                                |   STACK |    HEAD | STACK/HEAD |     range |  n | verdict |
| ---------------------------------- | ------: | ------: | ---------: | --------: | -: | ------: |
| lz4 (classic) compress             |  698812 |  463607 |     1.496x | 1.43-1.58 | 15 |  faster |
| lz4 (classic) decompress           |  341064 |  125094 |     2.735x | 2.62-2.88 | 15 |  faster |
| deflate/zlib compress              | 4807692 | 4807692 |     1.000x | 0.99-1.01 | 15 |   noise |
| deflate/zlib decompress            |  379363 |  379363 |     1.001x | 0.98-1.04 | 15 |   noise |
| zstd L1 (fast) compress            |  600962 |  602047 |     0.996x | 0.96-1.02 | 15 |   noise |
| zstd L1 (fast) decompress          |  332116 |  332557 |     0.999x | 0.96-1.04 | 15 |   noise |
| zstd L3 (zstd default) compress    |  734214 |  733138 |     1.000x | 0.97-1.06 | 15 |   noise |
| zstd L3 (zstd default) decompress  |  329381 |  327225 |     1.012x | 0.99-1.04 | 15 |   noise |
| zstd L6 (flume default) compress   | 2808989 | 2816901 |     1.000x | 0.97-1.03 | 15 |   noise |
| zstd L6 (flume default) decompress |  281452 |  284172 |     0.991x | 0.94-1.03 | 15 |   noise |
| zstd L9 compress                   | 5154639 | 5128205 |     1.005x | 0.98-1.03 | 15 |   noise |
| zstd L9 decompress                 |  273973 |  273523 |     1.002x | 0.99-1.03 | 15 |   noise |

runs: STACK 15, HEAD 15; a ratio above 1 means HEAD is faster
geomean 1.125 over 12 rows (min 0.991 zstd L6 (flume default) decompress; max 2.735 lz4 (classic) decompress)
per-run geomean: min 1.113, median 1.128, max 1.139 over 15 runs

## Intel i9-9980HK: per-row results

### micro (Sender / Receiver)

| row                           |    START |     HEAD | START/HEAD |     range |   A/A |  n | verdict |
| ----------------------------- | -------: | -------: | ---------: | --------: | ----: | -: | ------: |
| L1 text 64K feed 64K send     |  3252854 |  3358110 |     0.964x | 0.87-1.08 | 1.004 | 12 |   noise |
| L1 text 64K feed 64K receive  |  1481838 |  1512524 |     0.982x | 0.88-1.13 | 1.017 | 12 |   noise |
| L1 text 64K feed 1K send      |  3268635 |  3415698 |     0.956x | 0.91-1.09 | 0.994 | 12 |   noise |
| L1 text 64K feed 1K receive   |  1499453 |  1522288 |     0.973x | 0.86-1.08 | 1.017 | 12 |   noise |
| L1 text 4K feed 512 send      |  5385758 |  5623767 |     0.969x | 0.94-1.01 | 0.971 | 12 |   noise |
| L1 text 4K feed 512 receive   |  2395546 |  2391122 |     1.008x | 0.92-1.04 | 0.975 | 12 |   noise |
| L1 random 64K feed 4K send    |   750323 |   759709 |     0.992x | 0.88-1.38 | 0.940 | 12 |   noise |
| L1 random 64K feed 4K receive |   378218 |   369778 |     1.007x | 0.90-1.09 | 0.967 | 12 |   noise |
| L1 zeros 64K feed 4K send     |   480573 |   475105 |     0.993x | 0.85-1.24 | 0.964 | 12 |   noise |
| L1 zeros 64K feed 4K receive  |   458286 |   458388 |     1.003x | 0.87-1.43 | 0.985 | 12 |   noise |
| L6 text 64K feed 64K send     | 14727898 | 14870527 |     0.995x | 0.93-1.03 | 0.942 | 12 |   noise |
| L6 text 64K feed 64K receive  |  1479700 |  1306073 |     1.110x | 0.95-1.19 | 1.076 | 12 |   noise |

runs: START 12, HEAD 12, A/A 12; a ratio above 1 means HEAD is faster
geomean 0.995 over 12 rows (min 0.956 L1 text 64K feed 1K send; max 1.110 L6 text 64K feed 64K receive)
per-run geomean: min 0.950, median 1.000, max 1.029 over 12 runs
A/A geomean 0.987

### benchmarks/bench.cc (codec rows)

| row                                |    START |     HEAD | START/HEAD |     range |   A/A |  n | verdict |
| ---------------------------------- | -------: | -------: | ---------: | --------: | ----: | -: | ------: |
| lz4 (classic) compress             |   853243 |   841045 |     1.023x | 0.93-1.11 | 1.019 | 12 |   noise |
| lz4 (classic) decompress           |   239879 |   241431 |     1.001x | 0.78-1.20 | 0.971 | 12 |   noise |
| deflate/zlib compress              |  6920498 |  6896552 |     1.007x | 0.95-1.07 | 1.010 | 12 |   noise |
| deflate/zlib decompress            |   825430 |   869582 |     0.963x | 0.84-1.16 | 1.055 | 12 |   noise |
| zstd L1 (fast) compress            |  1127638 |  1124163 |     0.983x | 0.89-1.15 | 0.998 | 12 |   noise |
| zstd L1 (fast) decompress          |   540420 |   514463 |     1.077x | 0.86-1.31 | 1.043 | 12 |   noise |
| zstd L3 (zstd default) compress    |  1628734 |  1540836 |     1.024x | 0.94-1.18 | 0.981 | 12 |   noise |
| zstd L3 (zstd default) decompress  |   560696 |   558349 |     1.014x | 0.88-1.21 | 1.016 | 12 |   noise |
| zstd L6 (flume default) compress   |  8771930 |  8621330 |     1.031x | 0.88-1.12 | 1.023 | 12 |   noise |
| zstd L6 (flume default) decompress |   568463 |   530058 |     1.065x | 0.88-1.28 | 1.053 | 12 |   noise |
| zstd L9 compress                   | 13157895 | 12903763 |     1.032x | 0.88-1.13 | 0.967 | 12 |   noise |
| zstd L9 decompress                 |   535053 |   528133 |     0.996x | 0.84-1.09 | 1.005 | 12 |   noise |

runs: START 12, HEAD 12, A/A 12; a ratio above 1 means HEAD is faster
geomean 1.018 over 12 rows (min 0.963 deflate/zlib decompress; max 1.077 zstd L1 (fast) decompress)
per-run geomean: min 0.898, median 1.023, max 1.064 over 12 runs
A/A geomean 1.011

### Stack column, micro

| row                           |    STACK |     HEAD | STACK/HEAD |     range |  n | verdict |
| ----------------------------- | -------: | -------: | ---------: | --------: | -: | ------: |
| L1 text 64K feed 64K send     |  3288689 |  3286900 |     0.999x | 0.91-1.06 | 12 |   noise |
| L1 text 64K feed 64K receive  |  1529464 |  1510476 |     1.007x | 0.95-1.07 | 12 |   noise |
| L1 text 64K feed 1K send      |  3342526 |  3433041 |     0.990x | 0.94-1.08 | 12 |   noise |
| L1 text 64K feed 1K receive   |  1521432 |  1512702 |     1.018x | 0.95-1.12 | 12 |   noise |
| L1 text 4K feed 512 send      |  5527122 |  5494678 |     0.994x | 0.95-1.07 | 12 |   noise |
| L1 text 4K feed 512 receive   |  2400897 |  2422317 |     0.998x | 0.95-1.12 | 12 |   noise |
| L1 random 64K feed 4K send    |   770538 |   764996 |     1.016x | 0.90-1.23 | 12 |   noise |
| L1 random 64K feed 4K receive |   374441 |   383839 |     0.990x | 0.85-1.48 | 12 |   noise |
| L1 zeros 64K feed 4K send     |   487686 |   483741 |     1.009x | 0.83-1.32 | 12 |   noise |
| L1 zeros 64K feed 4K receive  |   458183 |   433978 |     1.067x | 0.85-1.45 | 12 |  faster |
| L6 text 64K feed 64K send     | 14960134 | 14674268 |     1.022x | 0.94-1.09 | 12 |   noise |
| L6 text 64K feed 64K receive  |  1331561 |  1393326 |     0.980x | 0.81-1.15 | 12 |   noise |

runs: STACK 12, HEAD 12; a ratio above 1 means HEAD is faster
geomean 1.007 over 12 rows (min 0.980 L6 text 64K feed 64K receive; max 1.067 L1 zeros 64K feed 4K receive)
per-run geomean: min 0.957, median 1.009, max 1.078 over 12 runs

### Stack column, codec rows

| row                                |    STACK |     HEAD | STACK/HEAD |     range |  n | verdict |
| ---------------------------------- | -------: | -------: | ---------: | --------: | -: | ------: |
| lz4 (classic) compress             |  1317669 |   841043 |     1.577x | 1.49-1.67 | 12 |  faster |
| lz4 (classic) decompress           |   583021 |   252494 |     2.356x | 2.08-2.96 | 12 |  faster |
| deflate/zlib compress              |  6826018 |  6969403 |     0.976x | 0.92-1.04 | 12 |   noise |
| deflate/zlib decompress            |   868812 |   838436 |     1.061x | 0.82-1.30 | 12 |  faster |
| zstd L1 (fast) compress            |  1173199 |  1121748 |     1.050x | 0.91-1.13 | 12 |  faster |
| zstd L1 (fast) decompress          |   526913 |   523424 |     0.980x | 0.89-1.22 | 12 |   noise |
| zstd L3 (zstd default) compress    |  1663935 |  1519771 |     1.077x | 0.97-1.17 | 12 |  faster |
| zstd L3 (zstd default) decompress  |   546637 |   512560 |     1.085x | 0.89-1.19 | 12 |  faster |
| zstd L6 (flume default) compress   |  8512026 |  8659469 |     1.004x | 0.82-1.09 | 12 |   noise |
| zstd L6 (flume default) decompress |   548747 |   542312 |     1.002x | 0.88-1.21 | 12 |   noise |
| zstd L9 compress                   | 13423423 | 12743506 |     1.025x | 0.92-1.12 | 12 |   noise |
| zstd L9 decompress                 |   543060 |   524660 |     1.002x | 0.87-1.29 | 12 |   noise |

runs: STACK 12, HEAD 12; a ratio above 1 means HEAD is faster
geomean 1.139 over 12 rows (min 0.976 deflate/zlib compress; max 2.356 lz4 (classic) decompress)
per-run geomean: min 1.070, median 1.134, max 1.238 over 12 runs

SUMMARY repo=flume m4_geomean=1.001 i9_geomean=1.006 m4_slow=0/- i9_slow=0/- unexplained=0 verdict=SAME
