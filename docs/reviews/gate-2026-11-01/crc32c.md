# gate: crc32c

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/crc32c#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Status: **measured on both machines, 3 rounds each.**
**FASTER** on both: geomean 1.478 on the M4 and 1.387 on the i9 over 10 rows; no row below 0.97 on the M4, one on the i9 (16 B, 0.957).

| | sha | date |
|---|---|---|
| START | `b60a8e5` | 2026-10-22 |
| HEAD | `3a09465` (origin/main at 2026-11-01 13:00, unchanged since 10:07; the library file is the one of `ce14992` at 08:52, `3a09465` changes the bench and CMake only) | 2026-11-01 |

The developer landed `ce14992` ("Run lanes in tiers and short buffers on one chain") after the gate started at `b635172`; HEAD above includes
it. START..HEAD library change: `include/crc32c/crc32c.hh` only (106 lines added, 41 removed). The hardware path runs in tiers (3 lanes of
1 KiB, then 256 B, then 128 B, 32 on AArch64), a plain chain below the smallest stride (384 B on x86-64, 96 B on AArch64), lane merge through
compile-time tables; detection calls `__builtin_cpu_init()` first and caches in a constant-initialized byte (a CRC taken during static
initialization no longer pins the run to slice-by-8). Values and the public interface are unchanged.

## Machines, compiler, commands

| | CPU | OS | compiler |
|---|---|---|---|
| M4 | Apple M4 Pro (14 cores) | macOS, arm64 | Apple clang 17.0.0 (clang-1700.3.19.1) |
| i9 | Intel i9-9980HK (8C/16T) | macOS 15, x86_64 | Apple clang 17.0.0 (clang-1700.6.4.2) |

- Benchmark: HEAD's `bench/crc32c.cc` (`crc32c_bench`): GB/s per call at 16, 64, 128, 256, 512, 1024, 2048, 4096, 65536 and 1048576 bytes, best of 7
  trials of 0.2 s, columns `hw` (the library, `kronuz::crc32c::crc32c`), `loop` (a plain loop of the CPU's CRC instruction, checked against the
  library), `slice8` and `byte` (table paths from `detail::`). HEAD's bench uses `detail::hardware_available()`, `detail::table_update` and
  `detail::tables`: **it compiles against START's `include/` unchanged** (checked with g++ 11.2 `-O3` on the Linux VM, and built with Apple clang
  on the M4), so no row is dropped. Library row = `hw`; `loop`, `slice8` and `byte` are controls (the table paths and the instruction loop
  are not what changed).
- A (START) = HEAD's tree with `include/crc32c/crc32c.hh` put back to `b60a8e5` (`git checkout b60a8e5 -- include/crc32c/crc32c.hh`),
  HEAD's CMakeLists; B (HEAD) = HEAD's tree. `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCRC32C_BUILD_BENCHMARKS=ON && cmake
  --build build --target crc32c_bench` (`-O3 -DNDEBUG`; the Google-crc32c reference rows are opt-in and off).
- Rounds: `gate-run.sh crc32c crc32c_bench`: per round A, B, A again (the A/A control), interleaved, in one `quiet strict` hold (`gate-hold.sh
  crc32c`; M4 12:50:31 to 12:59:33, the build ran inside the hold). A run takes 59 s, so the planned 4 rounds would not fit the 10-minute hold:
  the run was stopped after round 3 (and the partial fourth `a` removed) to end inside it. On the i9 the plan's run estimate was set to 60 s (it said 32)
  and the combo given a 590 s budget (`hold-ea.sh crc32c 590`, a copy of `gate-hold.sh` with a settable budget), so it planned exactly 3 rounds and
  none was cut: 13:40:46 to 13:49:44 inside its 10-minute hold, the build (clone included) taking 6 s of it. Ratios from `gate-cmp.py` (built on `ab_compare.py
  compare`); the numbers are GB/s and the column reads HEAD/START throughput, so above 1 means HEAD is faster, as in every table of the gate.
  "range" = min and max of the three paired ratios; A/A = the first A against the second A; the verdict means outside the A/A spread.
- An earlier M4 attempt at 12:31 failed in its build (no timing was taken): two drivers with the same hold name `gateea-crc32c` ran at once and
  removed each other's worktree. One driver per repo fixed it.
- Raw outputs: `$GATE/results/m4/crc32c/crc32c_bench/{a,b,aa}/` and `results/i9/crc32c/crc32c_bench/{a,b,aa}/`.

## M4 (A/A within 1.8%)

| row                   | START | HEAD | HEAD/START |     range |   A/A | n | verdict |
| --------------------- | ----: | ---: | ---------: | --------: | ----: | : | ------: |
| hw (crc32c) 16 B      |  13.3 | 13.4 |     1.008x | 0.99-1.01 | 0.998 | 3 |   noise |
| hw (crc32c) 64 B      |  28.9 | 29.7 |     1.026x | 1.01-1.06 | 0.982 | 3 |   noise |
| hw (crc32c) 128 B     |  23.5 | 28.1 |     1.195x | 1.19-1.22 | 0.988 | 3 |  faster |
| hw (crc32c) 256 B     |  17.6 | 25.1 |     1.425x | 1.42-1.44 | 0.997 | 3 |  faster |
| hw (crc32c) 512 B     |  13.3 | 23.7 |     1.773x | 1.75-1.78 | 0.996 | 3 |  faster |
| hw (crc32c) 1024 B    |  11.6 | 26.9 |     2.321x | 2.30-2.36 | 1.002 | 3 |  faster |
| hw (crc32c) 2048 B    |  10.8 | 26.0 |     2.386x | 2.37-2.39 | 0.998 | 3 |  faster |
| hw (crc32c) 4096 B    |  17.7 | 29.1 |     1.644x | 1.64-1.65 | 0.998 | 3 |  faster |
| hw (crc32c) 65536 B   |  22.1 | 29.8 |     1.347x | 1.34-1.35 | 0.991 | 3 |  faster |
| hw (crc32c) 1048576 B |  22.0 | 28.6 |     1.302x | 1.29-1.31 | 1.006 | 3 |  faster |

GB/s. **M4 geomean 1.478** over the 10 library rows (per-run 1.474 / 1.480 / 1.482; A/A geomean 0.996). Control (instruction loop, slice-by-8 and
byte-table columns, 30 rows; not library code): geomean 1.002, every row 0.981 to 1.148 (the 1.148 is the 16-byte instruction loop, a
placement-sensitive row, which the CHANGELOG also records for the library's 16-byte row). The CHANGELOG's own table (M4, `-O3`): 64 B 30.4 to 30.2,
512 B 13.9 to 24.2, 4 KiB 18.4 to 29.9, 1 MiB 22.4 to 29.5; this gate reads 28.9 to 29.7, 13.3 to 23.7, 17.7 to 29.1 and 22.0 to 28.6.
Rows below 0.97: **none**.

## i9 (A/A within 5.7%: the 1 KiB row, 1.057; the others within 2.1%)

| row                   | START | HEAD | HEAD/START |     range |   A/A | n | verdict |
| --------------------- | ----: | ---: | ---------: | --------: | ----: | : | ------: |
| hw (crc32c) 16 B      |  3.92 | 3.75 |     0.957x | 0.95-0.96 | 1.000 | 3 |  slower |
| hw (crc32c) 64 B      |  14.0 | 16.8 |     1.201x | 1.19-1.20 | 1.001 | 3 |  faster |
| hw (crc32c) 128 B     |  23.2 | 27.5 |     1.185x | 1.17-1.20 | 0.997 | 3 |  faster |
| hw (crc32c) 256 B     |  23.3 | 24.1 |     1.029x | 1.03-1.04 | 0.988 | 3 |   noise |
| hw (crc32c) 512 B     |  18.5 | 25.3 |     1.350x | 1.35-1.37 | 0.979 | 3 |  faster |
| hw (crc32c) 1024 B    |  15.9 | 25.4 |     1.600x | 1.53-1.61 | 1.057 | 3 |  faster |
| hw (crc32c) 2048 B    |  13.0 | 29.3 |     2.260x | 2.25-2.26 | 0.996 | 3 |  faster |
| hw (crc32c) 4096 B    |  17.5 | 30.1 |     1.734x | 1.69-1.78 | 1.003 | 3 |  faster |
| hw (crc32c) 65536 B   |  20.9 | 30.8 |     1.475x | 1.47-1.48 | 1.003 | 3 |  faster |
| hw (crc32c) 1048576 B |  20.0 | 29.9 |     1.502x | 1.47-1.51 | 0.991 | 3 |  faster |

GB/s. **i9 geomean 1.387** over the 10 library rows (per-run 1.380 / 1.382 / 1.390; A/A geomean 1.001). Control (30 rows; not library code): geomean
0.999, every row 0.936 to 1.084 (the 0.936 is the 16-byte instruction loop, the row that read 1.148 on the M4, and 1.084 is the 64-byte one). The
CHANGELOG's own table (i9, `-O3`, best of three runs before and after `ce14992`) gives 64 B 13.7 to 19.4, 512 B 18.8 to 25.5, 4 KiB 18.2 to 30.4,
1 MiB 20.4 to 30.1 GB/s and 16 B 3.8 to 4.0 (no row slower); this gate reads 14.0 to 16.8, 18.5 to 25.3, 17.5 to 30.1, 20.0 to 29.9 and 3.92 to
3.75. The ratios of the 512 B, 4 KiB and 1 MiB rows agree with the CHANGELOG's within 4% (1.36, 1.67 and 1.48 there; 1.35, 1.73 and 1.50 here); the 64 B
row gains 1.20x here against the CHANGELOG's 1.42x, and the 16 B row moves the other way (0.957 here, 1.05 there).
Rows below 0.97: **one**, `hw (crc32c) 16 B`.

## Rows below 0.97

| host | row | ratio | cause |
|---|---|---|---|
| i9 | `hw (crc32c) 16 B` | 0.957 | outside the A/A spread (A/A 1.000, range 0.95-0.96, 3.92 to 3.75 GB/s, a 4% loss on a 16-byte call). **Not shown to be the library's code:** HEAD's 16-byte path is the plain chain (it is below the 384 B stride), and the control `instruction loop 16 B` (a loop of the CPU's CRC instruction that runs no library code) reads 0.936 in the same runs, the same direction and a larger size; the 16 B rows are the placement-sensitive ones (M4: the same control reads 1.148, and the CHANGELOG records the library's 16-byte row as placement-sensitive). Not explained further here; the CHANGELOG's own i9 measurement of this row reads 3.8 to 4.0 |

None on the M4.

## Correctness changes that affect comparability

None for the timed rows (values identical; tests against a bitwise oracle at every tier boundary).

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- i9 `hw (crc32c) 16 B` 0.957: fixed in `crc32c:f004191` (`update()` inlines into `crc32c()`, so the
  short path is one call): 4.45 GB/s against start's 3.76.
