# gate: cuuid

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/cuuid#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Status: **measured on both machines, 7 rounds each.** **FASTER**: M4 geomean 2.27 (1.29 without the two cache-hit rows), i9 geomean 1.97
(1.28); one row below 0.97 (i9, `cuuid_compare` v1 no-compact, 0.945, not reproduced by the same operation in `cuuid_v1_bench`).

| | sha | date |
|---|---|---|
| START | `d46c825` | 2026-10-28 |
| HEAD | `1113b92` (origin/main at 2026-11-01 10:27) | 2026-11-01 |

Library files that differ START..HEAD: `cuuid_v1.cc` (v1 compact node: the first two `std::mt19937(seed)` outputs from a partial
init-and-twist `expand_mt_compute` plus an 8-entry thread-local seed cache, instead of building the 624-word engine), `cuuid_v6.cc/.hh`
(v6 `generate()` claims its time with a CAS instead of a mutex), `cuuid_common.cc/.h`. Wire bytes are unchanged (`test/test_mt.cc`).
`CMakeLists.txt` moved the dependency pins (char-classify `306ecd9` to `65c1ff5`, endian `f6269f0` to `8db745f`): the A build is given
START's pins (`gate-pins.py`: `-DFETCHCONTENT_SOURCE_DIR_<DEP>` at the START commits), so each side has the dependency versions it shipped
with.

## Machines, compiler, commands

| | CPU | OS | compiler |
|---|---|---|---|
| M4 | Apple M4 Pro (14 cores) | macOS, arm64 | Apple clang 17.0.0 (clang-1700.3.19.1) |
| i9 | Intel i9-9980HK (8C/16T) | macOS 15, x86_64 | Apple clang 17.0.0 (clang-1700.6.4.2) |

- Benchmarks (HEAD's sources, one source for both builds, all build against START): `cuuid_benchmark` (`benchmarks/serialise_parse.cc`,
  total time for 100,000 ids, one pass), `cuuid_v1_bench` (`benchmarks/v1_bench.cc`, best-of ns per call, public API only), `cuuid_compare`
  (`benchmarks/compare.cc`: section A generation, B serialise/parse, G node reconstruction timed; C to F are size and sort-order checks, H the
  opt-in Boost section, not built).
- A (START) = HEAD's tree with every library file put back to `d46c825`, HEAD's CMakeLists, START's dependency pins; B (HEAD) = HEAD's tree.
  `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release && cmake --build build --target cuuid_benchmark cuuid_v1_bench cuuid_compare`
  (`-O3 -DNDEBUG`).
- Rounds: 7 per binary, A, B, A again per round, interleaved, inside one `quiet strict` hold (`gate-hold.sh cuuid`; M4 10:50:45 to 10:52:11,
  i9 10:57:33 to 10:58:47; the M4 build ran inside the hold). Ratios from `gate-cmp.py` (on `ab_compare.py compare`): START/HEAD, above 1 = HEAD
  faster; "range" = min and max of the seven paired ratios; A/A = the first A against the second A; the verdict means outside the A/A spread.
- Controls (inline UUIDv7, UUIDv6, ULID, Snowflake and `std::mt19937` in the benches; none calls the library) are summarized per table.
- Raw outputs: `$GATE/results/{m4,i9}/cuuid/<target>/{a,b,aa}/`.

## M4

`cuuid_benchmark` (ns, whole pass): geomean 1.220.

| row                           |    START |     HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------- | -------: | -------: | ---------: | --------: | ----: | : | ------: |
| serialise 100k ids (total ns) | 93892000 | 62187000 |     1.512x | 1.49-1.52 | 0.998 | 7 |  faster |
| parse 100k ids (total ns)     |  1119000 |  1091000 |     0.984x | 0.84-1.09 | 1.036 | 7 |   noise |

`cuuid_v1_bench` (ns per call): geomean 4.305 (1.29 without the two "same id" rows, see Notes).

| row                            | START |  HEAD | START/HEAD |       range |   A/A | n | verdict |
| ------------------------------ | ----: | ----: | ---------: | ----------: | ----: | : | ------: |
| v1 serialise (same id)         | 919.7 |  10.1 |    90.248x | 81.16-99.23 | 1.003 | 7 |  faster |
| v1 unserialise (same id)       | 946.0 |  11.2 |    84.536x | 73.43-86.77 | 0.998 | 7 |  faster |
| v1 serialise (4096 distinct)   | 920.5 | 602.8 |     1.527x |   1.51-1.54 | 1.000 | 7 |  faster |
| v1 unserialise (4096 distinct) | 946.9 | 611.3 |     1.552x |   1.53-1.57 | 1.002 | 7 |  faster |
| v1 generate (compact)          | 994.3 | 654.4 |     1.516x |   1.49-1.54 | 0.998 | 7 |  faster |
| v1 generate (no compact)       |  90.9 |  90.9 |     1.000x |   1.00-1.00 | 1.000 | 7 |   noise |
| v6 generate                    |  90.9 |  90.9 |     1.000x |   1.00-1.00 | 1.000 | 7 |   noise |

`cuuid_compare` (ns per call): geomean 1.322.

| row                     |  START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------- | -----: | ----: | ---------: | --------: | ----: | : | ------: |
| A cuuid v1 (no compact) |   91.6 |  91.5 |     0.999x | 1.00-1.01 | 1.000 | 7 |   noise |
| A cuuid v1 (compact)    | 1002.7 | 661.1 |     1.510x | 1.49-1.54 | 0.995 | 7 |  faster |
| B cuuid compact ser     |  931.3 | 616.1 |     1.515x | 1.50-1.53 | 0.999 | 7 |  faster |
| B cuuid compact parse   |  955.7 | 616.9 |     1.549x | 1.53-1.55 | 1.001 | 7 |  faster |
| B cuuid expanded ser    |  934.3 | 613.1 |     1.526x | 1.50-1.56 | 1.009 | 7 |  faster |
| B cuuid expanded parse  |   10.2 |  10.3 |     0.990x | 0.96-1.05 | 1.000 | 7 |   noise |

**M4 geomean 2.269** over the 15 library rows (1.294 without the two cache-hit rows). Controls: `cuuid_compare` 10 rows geomean 0.997
(0.968 to 1.020), `cuuid_v1_bench` `mt19937(seed) + 2 draws` 0.993. Rows below 0.97: **none**.

## i9 (the machine was noisier; A/A deviations up to 5.5%)

`cuuid_benchmark` (ns, whole pass): geomean 1.226.

| row                           |    START |     HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------------- | -------: | -------: | ---------: | --------: | ----: | : | ------: |
| serialise 100k ids (total ns) | 96960000 | 65434000 |     1.509x | 1.39-1.53 | 1.005 | 7 |  faster |
| parse 100k ids (total ns)     |  2297000 |  2384000 |     0.996x | 0.69-1.08 | 0.945 | 7 |   noise |

`cuuid_v1_bench` (ns per call): geomean 3.251.

| row                            |  START |  HEAD | START/HEAD |       range |   A/A | n | verdict |
| ------------------------------ | -----: | ----: | ---------: | ----------: | ----: | : | ------: |
| v1 serialise (same id)         |  936.4 |  25.5 |    36.375x | 35.86-43.53 | 1.011 | 7 |  faster |
| v1 unserialise (same id)       |  951.9 |  32.0 |    29.841x | 28.93-34.73 | 1.004 | 7 |  faster |
| v1 serialise (4096 distinct)   |  931.4 | 631.6 |     1.468x |   1.34-1.55 | 0.997 | 7 |  faster |
| v1 unserialise (4096 distinct) |  934.8 | 645.4 |     1.453x |   1.34-1.58 | 0.992 | 7 |  faster |
| v1 generate (compact)          | 1002.8 | 699.2 |     1.470x |   1.31-1.52 | 1.001 | 7 |  faster |
| v1 generate (no compact)       |   92.4 |  91.0 |     1.000x |   0.92-1.06 | 1.001 | 7 |   noise |
| v6 generate                    |  111.7 | 101.1 |     1.126x |   1.06-1.24 | 1.045 | 7 |   noise |

`cuuid_compare` (ns per call): geomean 1.287.

| row                     |  START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ----------------------- | -----: | ----: | ---------: | --------: | ----: | : | ------: |
| A cuuid v1 (no compact) |   91.8 |  97.1 |     0.945x | 0.92-1.09 | 0.998 | 7 |  slower |
| A cuuid v1 (compact)    | 1030.0 | 721.2 |     1.418x | 1.39-1.56 | 0.994 | 7 |  faster |
| B cuuid compact ser     |  977.3 | 650.7 |     1.502x | 1.33-1.61 | 0.971 | 7 |  faster |
| B cuuid compact parse   |  999.9 | 649.1 |     1.520x | 1.40-1.61 | 1.004 | 7 |  faster |
| B cuuid expanded ser    |  960.1 | 647.8 |     1.481x | 1.42-1.67 | 0.989 | 7 |  faster |
| B cuuid expanded parse  |   24.3 |  23.9 |     1.004x | 0.95-1.13 | 0.987 | 7 |   noise |

**i9 geomean 1.970** over the 15 library rows (1.278 without the two cache-hit rows). Controls: `cuuid_compare` 10 rows geomean 0.975
(0.812 to 1.267, sub-10 ns rows that swing with the A/A spread), `cuuid_v1_bench` `mt19937(seed) + 2 draws` 0.985.

## Rows below 0.97

One: **i9 `cuuid_compare` "A cuuid v1 (no compact)", 0.945** (91.8 to 97.1 ns, range 0.92 to 1.09, A/A spread 3.3%, flagged outside it).
Unexplained, and probably not a library cost: the same operation (`UUIDGenerator::operator()(false)`, the platform mint, code the change
does not touch) reads 1.000 (0.92 to 1.06) in `cuuid_v1_bench` on the same machine in the same hold, and 0.999 on the M4. The
`cuuid_compare` row is one 200,000-call pass per run, not a best-of. A re-run with more rounds would settle it.

## Notes: correctness and comparability

None for the timed rows: the compact node is bit-identical to the engine's (differential test over many seeds), the v6 CAS yields the same
sequence, wire bytes are unchanged. The two "same id" rows of `cuuid_v1_bench` hit the new 8-entry seed cache (10 to 32 ns against 920 to
950 ns); they are real for a `generate()` followed by `serialise()` of the same id, but not the per-id cost, which the "4096 distinct" rows
give (1.45x to 1.55x). The geomeans are quoted with and without them. `v6 generate`: the CAS removed the claim's own mutex (CHANGELOG: 8 to
10% on the i9, none on the M4, whose platform mint sets the floor): 1.126 on the i9, 1.000 on the M4. CHANGELOG figures agree (M4 v1
serialise 900 to 590 ns, i9 not given there).

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- i9 `cuuid_compare` v1 without compaction 0.945: placement. The same operation reads 1.000 in
  `cuuid_v1_bench` in the same hold.
