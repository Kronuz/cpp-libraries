# gate: md5

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/md5#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Status: **measured on both machines, 5 rounds each.** **FASTER**: M4 geomean 1.133, i9 geomean 1.159 over 5 library rows; no row below 0.97
on either machine. Only the short inputs change (the hex conversion); 64 KiB and 1 MiB are the unchanged compression function (1.00).

| | sha | date |
|---|---|---|
| START | `fbb8ff0` | 2026-10-28 |
| HEAD | `6e4005f` (origin/main at 2026-11-01 10:27) | 2026-11-01 |

Library change START..HEAD: `md5.cc` only (`MD5::getHash()` sizes the hex string once and fills two characters per byte instead of `+=`
per character, 12 changed lines). The compression function is unchanged. The endian pin moved from `f6269f0` (START) to `8db745f` (HEAD):
the A build is given START's pin (`gate-pins.py`), so each side has the endian header it shipped with.

## Machines, compiler, commands

| | CPU | OS | compiler | OpenSSL linked by the bench |
|---|---|---|---|---|
| M4 | Apple M4 Pro (14 cores) | macOS, arm64 | Apple clang 17.0.0 (clang-1700.3.19.1) | 4.1.0 |
| i9 | Intel i9-9980HK (8C/16T) | macOS 15, x86_64 | Apple clang 17.0.0 (clang-1700.6.4.2) | 4.0.3 |

- Benchmark: `md5_hex_bench` (`bench/hex_bench.cc`, HEAD's source, uses only API that START has): ns per `MD5` hex string at 16, 64, 1024,
  65536 and 1048576 bytes, best of windows, with OpenSSL EVP columns. Library column `MD5 hex`; the three EVP columns are controls.
- A (START) = HEAD's tree with `md5.cc md5.h` put back to `fbb8ff0`, HEAD's CMakeLists, START's endian pin; B (HEAD) = HEAD's tree.
  `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DMD5_BUILD_BENCH=ON && cmake --build build --target md5_hex_bench`
  (`-O3 -DNDEBUG`).
- Rounds: 5 (7 s a run), A, B, A again per round, interleaved, in one `quiet strict` hold per machine (`gate-hold.sh md5`; M4 11:39:08 to
  11:41:23, i9 11:56:51 to 11:58:55; the builds ran inside the holds). Ratios from `gate-cmp.py` (built on `ab_compare.py compare`):
  START/HEAD, above 1 = HEAD faster; "range" = min and max of the five paired ratios; A/A = the first A against the second A.
- Raw outputs: `$GATE/results/{m4,i9}/md5/md5_hex_bench/{a,b,aa}/`.

## M4

| row               |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| MD5 hex 16 B      |   162.8 |   114.0 |     1.429x | 1.38-1.43 | 1.005 | 5 |  faster |
| MD5 hex 64 B      |   216.8 |   170.6 |     1.268x | 1.26-1.27 | 1.001 | 5 |  faster |
| MD5 hex 1024 B    |  1416.1 |  1374.6 |     1.031x | 1.01-1.04 | 0.990 | 5 |  faster |
| MD5 hex 65536 B   | 82570.0 | 82645.8 |     1.000x | 1.00-1.01 | 1.003 | 5 |   noise |
| MD5 hex 1048576 B | 1319676 | 1318177 |     1.001x | 0.99-1.01 | 1.000 | 5 |   noise |

ns per hex string. **M4 geomean 1.133** (per-run 1.123 / 1.133 / 1.138; A/A geomean 1.000). Control (the three OpenSSL EVP columns, 15 rows):
geomean 1.003, every row 0.997 to 1.011. Rows below 0.97: **none**.

## i9

| row               |   START |    HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------- | ------: | ------: | ---------: | --------: | ----: | : | ------: |
| MD5 hex 16 B      |   267.5 |   179.0 |     1.488x | 1.47-1.52 | 0.998 | 5 |  faster |
| MD5 hex 64 B      |   349.5 |   258.0 |     1.353x | 1.32-1.37 | 0.995 | 5 |  faster |
| MD5 hex 1024 B    |  1745.6 |  1643.3 |     1.061x | 1.04-1.07 | 1.003 | 5 |  faster |
| MD5 hex 65536 B   | 94587.3 | 95735.8 |     0.988x | 0.97-1.02 | 1.001 | 5 |   noise |
| MD5 hex 1048576 B | 1528486 | 1549964 |     0.992x | 0.97-1.01 | 0.996 | 5 |   noise |

ns per hex string. **i9 geomean 1.159** (per-run 1.152 / 1.154 / 1.176; A/A geomean 0.999). Control (EVP columns, 15 rows): geomean 1.008, every
row 0.986 to 1.056. Rows below 0.97: **none**.

## Rows below 0.97

None on either machine. (The two long rows on the i9 read 0.988 and 0.992, inside their ranges 0.97 to 1.02: the compression function is
unchanged.)

## Correctness changes that affect comparability

None: identical hex output (differential test against the byte-at-a-time conversion, lengths 0 to 300). CHANGELOG: 16 bytes 161 to 115 ns on
the M4 Pro; measured here 162.8 to 114.0 ns.
