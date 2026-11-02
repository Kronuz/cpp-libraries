# Performance: method and comparators

How the libraries in this catalog are measured, and how a change shows that it is faster and
still gives the same answers. The October 2026 measurements live in the dated surveys and
reviews under [reviews/](reviews/); the [gate of 2026-11-01](reviews/gate-2026-11-01.md)
compares 51 libraries with their start. What they taught is in [LESSONS.md](LESSONS.md); the
fixes that change results, and the commits not to pin, are in
[UPGRADING-2026-10.md](UPGRADING-2026-10.md).

## 1. What this covers

The generic libraries of the catalog: text and bytes, hashing and identifiers, time, containers
and filters, parsers, text algorithms and geometry, the search-engine building blocks, systems
and concurrency, and the service stack (msgpack, reactor, http). A performance change aims to
match or beat the best comparable library while staying generic: every character type,
sequence, allocator and platform the library already supports, the same public API, the same
ABI-visible layouts, the same on-disk and on-wire bytes, and the same results. A change of
results is a behavior fix and follows its own rules (section 3).

- **Leaves stay leaves.** A benchmark lives in the library's `bench/` (or `benchmarks/`)
  directory and fetches its comparators itself; the library target never links them, and a leaf
  gains no dependency for speed.
- **First principles.** Fast paths are written from the papers and the algorithm; no GPL or
  LGPL code is copied.
- **Libraries in active development** (strata, prospect, termdict, fst, docset, bitpack,
  fusefilter, completion, task, journal, consensus, storage, cluster) take internal or additive
  changes only, start from the latest `main`, and name every compatibility hazard.
- **Not covered:** vendored third-party code (msgpack-c inside msgpack, the generated Snowball
  stemmers, the UCD tables in unicode).
- **uinteger_t and base-x** were measured in a campaign of their own, with A/A and interleaved A/B
  runs on quiet machines and GMP, Boost and the base58 codecs as comparators
  ([record](reviews/2026-10-31-uinteger_t-base-x.md)). Their benches are `bench/bench.cc`, built by
  hand or with `bench/run.sh`, with no CMake option.

## 2. Machines

Every number in these documents names its machine by hardware.

| name used in docs | CPU, cores, memory | OS | compilers | role |
|---|---|---|---|---|
| Apple M4 Pro | Apple M4 Pro, 14 cores, 48 GB | macOS 26 | Apple clang 17, Homebrew LLVM 23, Homebrew GCC 16.2 | arm64 timing and development; UBSan (AddressSanitizer is run on Linux) |
| Intel Core i9-9980HK | Intel Core i9-9980HK (Coffee Lake), 8 cores / 16 threads, 32 GB | macOS 15, x86-64 | Apple clang 17, Homebrew GCC 16.2, Homebrew LLVM 23 | x86-64 timing |
| Apple M1 Pro | Apple M1 Pro, 10 cores, 32 GB | macOS 27 | Apple clang 21 | a second arm64 machine: compiler and FMA-contraction checks, arm64 timing |
| shared Linux x86-64 VM | x86-64, 8 vCPUs, shared with other users | Linux, glibc 2.35 | g++ 11.2 (no `<format>`), clang 12 | ASan, TSan, glibc behavior; its timings are directional only |
| GitHub Actions runners | x86-64 and arm64 cloud CPUs (AMD EPYC, Intel Xeon, Neoverse-N2, Apple M1, by job) | Ubuntu 24.04 (x86-64 GCC and Clang, arm64 GCC), macOS 15 (arm64, x86-64), FreeBSD 14.3 | per job | the CI matrix of `.github/workflows/cmake.yml` on every push and nightly, ASan+UBSan and TSan jobs, callgrind instruction counts |

x86-64 binaries running under Rosetta on an Apple machine check correctness only; they are never
timed.

## 3. Correctness before speed

A faster path ships only with proof that it gives the old answers, and a behavior change only
with proof that the new answers are right. The two proofs are different tests.

**Frozen-copy differential.** The old implementation is copied into `test/` with its symbols
renamed and a "never edit" comment (`strict-stox:test/strict_stox_old.hh`,
`http-parser:test/http_parser_old.cc`, `queue:test/queue_frozen.h`, `msgpack:test/frozen_msgpack.h`,
`datetime:test/old/`). A CTest test, usually `<lib>_diff`, compares the two on random and edge
inputs: every byte value at every position of each fast path, sizes around every block
boundary, buffers that end inside a run, every split point of a streaming input. For a parser it
compares every callback, offset and struct field (`http_parser_diff`, about 1.8 million parses).
The differential proves that nothing else changed. It does not prove the answer is right: it
reproduces the old bugs, as it did for strict-stox's 63-byte cut, Jaro and Jaro-Winkler,
boolean-parser's implicit-OR precedence and five datetime quirks.

**Independent oracle.** Beside the differential, a test compares the result with something that
does not share the implementation's reasoning:

| library | oracle |
|---|---|
| strict-stox | libc `strto*` on the same bytes and `std::from_chars` (`test/long_test.cc`, `test/fp_test.cc`, `test/rounding_test.cc`, `test/locale_test.cc`) |
| string-similarity | textbook dynamic programs (`test/oracle.h`, `correctness.cc`); rapidfuzz-cpp under the bench option (`rapidfuzz_check.cc`) |
| boolean-parser | a recursive-descent parser written from the grammar (`test/oracle.h`), exhaustive to length 7 (9 in the deep run) |
| datetime | Hinnant's days-from-civil and a month-arithmetic model (`test/ref.h`, `datetime_datemath`) |
| sha256 | OpenSSL EVP (`test/openssl.cc`) |
| cuuid | `std::mt19937` for the v1 node expander (`test/test_mt.cc`) |
| docset | `std::set_intersection` and friends (`test/test.cc`) |
| msgpack | a `std::map` model of the merged document (`test/model.h`, `merge_test.cc`, `growth_test.cc`) |
| metrics | a model atomic run over every interleaving at 8 bits (`test/model.cc`) |
| unicode | Xapian 2.1.0's tables on all 1,114,112 code points |
| uinteger_t | GMP's `mpz_*` through `test/fuzz_gmp.cc` (local, conversions up to 64K limbs, not in CTest); an independent base-4 model of the quotient-only division (`test/divq_model.cc`); a naive DFT for the transform (`test/ntt_kernel.cc`); all 2^31 divisors at 16-bit limbs (`test/recip16.cc`) |
| base-x | Python's `base64` module for the `rfc4648*` presets and Bitcoin Core's and the XRP Ledger's base58 vectors (`test/test.cc`); a decode model in the fuzz target (`test/fuzz_decode.cc`); the text of every preset in `test/golden/encode.txt` |

**Deliberate behavior changes** are listed input classes in the differential test: inside a
class the test asserts old != new and new == oracle, everywhere else old == new. The commit body
states the oracle; the CHANGELOG gives the old and new behavior; consumers get an entry in
[UPGRADING-2026-10.md](UPGRADING-2026-10.md).

**Mutants and revert checks.** `tools/mutants.py` (or `tools/fp_mutants.py`) edits the
implementation in named ways and requires a test to fail on each (strict-stox's float fast path,
http-parser's scans, unicode's decoder, msgpack's tree paths and fixes; double-metaphone, random,
sortable, term-color and string-similarity carry their own). Each repo's AGENTS.md says when to
run it. A fix's commit body states the revert run: the new test fails with the fix reverted.

**Fuzzing and sanitizers.** A fuzz target in `fuzz/` (or `test/fuzz.cc`) under `<LIB>_FUZZ`, a
replay over a committed corpus where there is one, and a nightly run where the input is
untrusted (http-parser on x86-64 and arm64). UBSan runs on macOS; ASan and TSan run on Linux
(the CI jobs and the shared VM). Concurrency code adds a stress test and a model or a hook that
pins the race (`scheduler`'s `SCHEDULER_TEST_HOOK`, `queue:test/liveness.cc`). Code shape that
the speed depends on is checked by a test too (`docset_codegen` asserts a conditional move,
`bitpack:bench/asm_check.cc`).

## 4. Timing protocol

**Identity first.** Every benchmark row checks that the comparator returns the same result as
the library on the same inputs. A row that disagrees is void and is not used for ranking.

**Release builds.** `-O3 -DNDEBUG` (or the repo's Release), on both sides. A debug build can
invert a conclusion.

**Holds.** Timing runs only while the machine is otherwise idle: an exclusive hold that stops
other work on the host (dedicated cores on Linux), one hold at a time, each under ten minutes.
Builds, tests and fuzzing run at low priority under a light hold. A timing taken on a loaded or
shared machine is labeled directional.

**Three stages.** A long run is the last step, never the first.

1. **Smoke.** Build both variants, run the identity check and each row once. Nothing is reported.
2. **Screen.** One hold, interleaved A/B, median of N, with an A/A column (the baseline against
   itself). A candidate survives when it is outside the A/A spread and reaches the target: 1.3x
   unless the change says otherwise. A gain inside the noise is reported as negligible.
3. **Confirm.** One binary per variant, since code layout alone moves a 20-100 ns row by 5-20%.
   Paired, interleaved runs in two holds; Clang and GCC; arm64 and x86-64; the untargeted rows
   (small sizes, other types, other compilers) as well as the targeted ones. Report the median
   and the spread. The budget: no row more than 3% slower on either instruction set.

**Inputs.** A row cycles through a pool of distinct inputs larger than the branch predictor
holds; a row that repeats one input measures predictor aliasing. Small sizes always get rows,
since per-call setup is the whole cost at 16 bytes. Rows that do repeat a pair say so.

**Layout on x86.** On the i9 an unchanged 25-60 ns row moves 10-20% with code layout. Both sides
build with `-falign-functions=64 -mbranches-within-32B-boundaries` when a few percent matter,
and an A/A row sits in the same run.

**Instruction counts.** Callgrind on a CI runner counts instructions exactly and needs no quiet
machine; it shows what a change removed. The same instruction savings land differently on each
microarchitecture, so a change is still timed on the machines that matter.

**Expiry.** A number names the commit, compiler, flags and machine it measured, and is
re-measured when the code under it changes.

**The paired comparison.** `tools/ab_compare.py` does the arithmetic of the screen and confirm
stages. `run A B` runs the baseline, the candidate and the baseline again in every round, one
after another with the same arguments, and reads what they print (Google Benchmark JSON or the
repositories' plain-text rows). It takes no hold: the machine is held around the command, and
the tool only orders the runs. Per row it reports:

- **Ratio.** The median over the rounds of the ratio of round *i* of A to round *i* of B (B to A
  for a throughput), so a drift of the machine inside a round cancels and a ratio above 1 always
  means B is faster. A and B are the medians of the raw values.
- **Range.** The lowest and highest paired ratio.
- **A/A.** The same ratio between the two runs of A. Its largest distance from 1 over the rounds
  is the row's noise band; without an A/A run the band is 3%.
- **Verdict.** `faster` or `slower` when the ratio is outside the band, else `noise`: a gain
  inside the noise is negligible and is reported so.
- **Identity.** A `chk HEX` on a row (or a `chk` counter in Google Benchmark) is its result
  checksum. A row whose paired checksums differ is `VOID`: it is left out of the geomean, and the
  exit status is 1.

The summary gives the geomean of the row ratios, the same geomean for each round (its minimum,
median and maximum show whether one round carries the result) and the A/A geomean.
`--budget 3` turns the 3% rule into an exit status: it fails when a row is more than 3% slower
and outside its noise band. Fewer than three rounds print a warning, since the range and the
A/A are then single draws. `--save DIR` keeps each run's output so that a confirm run in two
holds, or on the second instruction set, reads back with `compare --a ... --b ... --aa ...`
over the files of both holds; files pair by position after a natural sort of their names.
A paired ratio means something only when the runs were interleaved: files from two separate
holds still pair by position, but not in time, so their range and A/A are read with that in mind.

## 5. Both instruction sets

- **Paths.** NEON on arm64, SSE2 on x86-64, and a SWAR or scalar fallback for every vector path.
  Guards name each architecture (`__aarch64__`, `__ARM_NEON`, `__SSE2__`); a guard written for
  one architecture alone leaves the other on the slow path (XXH32 pinned its lanes to scalar
  registers on AArch64 only and ran 1.4-2.1x slower on x86 until the guard covered SSE2).
- **Above SSE2, at run time.** SSE4.2, AVX2, BMI1, SHA-NI and the ARMv8 crypto and CRC
  instructions are chosen by a run-time check (`docset`, `sha256`, `crc32c`), so one binary is
  correct on every CPU.
- **A switch and a test for the fallback.** `<LIB>_NO_SIMD` (`CHARS_NO_SIMD`, `BITPACK_NO_SIMD`,
  `DOCSET_NO_SIMD`, `URL_PARSER_NO_SIMD`, `HTTP_PARSER_NO_SIMD`) builds the portable path, and a
  CTest target reruns the SIMD-covering tests with it (`url_parser_diff_swar`, `escape_diff_swar`,
  `repr_diff_swar`, `docset_portable`, `bitpack_portable`, `strict_stox_fp_portable`).
- **An x86 cell beside every arch-sensitive ratio.** SWAR is not SIMD (repr gains 5.7x on 4 KB of
  printable text on arm64 and 3.0x on x86-64), and a branch-predictor win can be arm-only (docset
  bitmap AND at density 0.1 was 3.6x on arm64 and 1.0x on x86-64 until it chose its routine per
  CPU).
- **Byte order.** A library that assumes little-endian says so (bitpack: x86-64 and AArch64
  only).

## 6. Reporting

- **Commit body.** The numbers, machine, compiler and A/A spread; for a fix, the oracle, the
  changed input classes and the revert run.
- **CHANGELOG.md.** Keep a Changelog form, newest first, dated. Each entry has the old and new
  behavior, the before/after numbers with machine and spread, and the commit.
- **README "Performance".** The current numbers, the bench command and the machines, in the
  present tense, with no history.
- **docs/perf/&lt;topic&gt;.md.** The method, the rejected variants and the open items of one
  change, opening with "Measured &lt;date&gt; at `<repo>:<sha>`"
  (`btree:docs/perf/move-relocation.md`, `allocators:docs/perf/construct-forwarding.md`).
- **Dated reviews.** Surveys and audits go to [reviews/](reviews/), each opening with a
  Resolution table (finding, status, `repo:sha`, test).

### Surveys

A survey reads each library in a cluster, finds its hot paths, and benchmarks the public entry
points on realistic generic workloads, small to large, against the best comparator in the same
space (the standard library, Abseil, Boost, fmt, xxHash, fast_float, ada, rapidfuzz, llhttp,
OpenSSL, CRoaring, simdcomp). Each row records ours, the comparator, the ratio with its A/A
spread, the diagnosed cause (algorithm, allocation, branches, no SIMD, locale), the estimated
win and effort, and a verdict: **CLEAR WIN**, **maybe**, **already good** or **not worth it**.
Each CLEAR WIN names the start files, the single biggest suspected change, and what must stay
identical. A survey also records API-compatibility hazards and the design lessons behind the
slowness.

### Audits

An audit reviews a change from a fresh context, start (the last commit before the work) against
head, and rules **BETTER**, **BETTER WITH CONDITIONS** or **NOT YET** per repo, blocking findings
first with `file:line` and a reproduction:

1. **Correctness.** A test for every changed behavior, registered in CTest and run in CI; the
   differential covers the edge classes; at least one independent probe per changed mechanism
   and a mutant on the riskiest claim; introduced bugs separated from pre-existing ones.
2. **Performance.** The repo's own bench, start against head, with an A/A; claimed numbers and
   comparator rows confirmed or refuted; regressions on untargeted rows named; x86-64 measured
   when arch-specific code changed.
3. **Compatibility.** Public API, ABI-visible layouts, serialized bytes and defaults unchanged
   except the documented fixes; no new dependency in a leaf; C++17 libraries still build as
   C++17; headers self-contained.
4. **Generality.** Every type, character type, allocator and platform it claims; no arm-only win
   with an x86 loss; no endianness or alignment assumption; a tested scalar fallback.
5. **Hygiene.** CI green on the default branch; no stray branches; README present tense and the
   history in CHANGELOG; the bench reproducible from the README command.
6. **Bar.** Clearly better than at the start and at or near the best comparator; if not, the one
   change that would get it there, with evidence.

### Catalog checks

Two scripts check properties of the whole catalog rather than of one change.

**Headers alone.** `tools/selfcontained.sh REPO_DIR` compiles each public header as the only
content of a translation unit, included twice (the second include checks the guard), with
`-fsyntax-only` at the standard the repository's CMake requests, and prints one line per header.
`-b BUILD` puts the first-party dependencies of a configured build tree on the include path, `-s`
adds a standard, and `-x GLOB` or `.selfcontained-skip` leaves out a header that needs a platform
or a macro its includer sets. A repository runs it in CI with `headers: true` on the shared
workflow, under GCC and Clang. Its result is the audit's "headers self-contained" check (item 3
of the audit list above).

**Pins.** `tools/pins.sh` lists every first-party `FetchContent_Declare` of the owner's
repositories, read from each default branch, with the dependency's default branch, and the number
of commits the pin is behind it (`current`, `behind N`, `tracks BRANCH`, `ahead`, `diverged`,
`pin not found`, `unresolved`, `no GIT_TAG`). `-b` keeps the pins that need attention and `-c`
turns them into an exit status. A consumer keeps whatever its pin predates: the fixes of
[UPGRADING-2026-10.md](UPGRADING-2026-10.md) reach it when the pin moves, in waves, each green
before the next.

## 7. Comparator matrix

Where each library stands against what a reader would otherwise use, copied from the "Performance"
section of its README on the default branch (2026-11-01, 16:30 PST). Each library name links to that
section, which has the bench command, the compiler and every row. A cell gives the library's number
against the comparator's, in the unit of the "timed" column, on that machine: Apple M4 Pro (arm64)
or Intel Core i9-9980HK (x86-64), both with Apple clang 17 at `-O3` unless the cell names another
machine. A comparator written in the bench is the obvious hand-written alternative, not a library.

| library | comparator, version | timed | Apple M4 Pro | Intel Core i9-9980HK |
|---|---|---|---|---|
| [allocators](https://github.com/Kronuz/allocators#-performance) | `std::allocator`; libc++ 20.1 `pmr::unsynchronized_pool_resource` and `monotonic_buffer_resource` | build, use and destroy a list or map, as a fraction of `std::allocator`'s time | 0.55 to 0.82 of `std::allocator`; against the pmr pool faster on map churn (0.55 vs 0.68), slower on lists (0.56-0.68 vs 0.29-0.50); slower than monotonic on list build (0.59-0.68 vs 0.26-0.27) | 0.58 to 0.73; pmr pool: map churn 0.58 vs 0.66, lists 0.65-0.73 vs 0.20-0.27; monotonic 0.65-0.66 vs 0.13-0.18 |
| [analysis](https://github.com/Kronuz/analysis#-performance) | Xapian 2.1.0 `TermGenerator` | MB/s indexing 10,000 enwiki articles | 2.7x faster without stemming (81.8 vs 30.6), 2.3x with English stems (30.4 vs 13.2) | 1.9x (32.3 vs 17.0), 1.8x (12.9 vs 7.1) |
| [bitpack](https://github.com/Kronuz/bitpack#-performance) | simdcomp `d530177` (NEON, M4 Pro); SIMD-BP128 of SIMDCompressionAndIntersection `b809f38` (SSE2, i9) | integers per ns decoding 128-integer blocks | level with simdcomp: 1.00x averaged over widths 1-31, delta 1.01x; faster at 32 bits (21.25 vs 12.97) | level with SIMD-BP128: 0.99x averaged, delta 1.03x; slower at 32 bits (8.21 vs 10.73) |
| [bloom-filter](https://github.com/Kronuz/bloom-filter#-performance) | Boost 1.92.0 `boost::bloom::filter<std::uint64_t, 20>` | ns per `contains`, 16 and 64 B keys | `BlockedBloomFilter` faster or level (8.4 vs 18.7 on 16 B misses, 15.1 vs 15.4 on hits); `BloomFilter` slower (19.1-72.3 vs 15.4-23.2) | `BlockedBloomFilter` faster on every row (18.2 vs 23.0 to 42.7 vs 58.2); `BloomFilter` slower (35.6-96.3) |
| [boolean-parser](https://github.com/Kronuz/boolean-parser#-performance) | a precedence-climbing parser in the bench (a floor) | ns per full parse | 1.5x to 3.2x the climber's time (82 vs 56 ns; 104 vs 32.6 us at 1,024 terms); faster on 200 nested parentheses (2.54 vs 2.94 us) | level on `alpha AND beta` (155 ns each); 1.2x to 4.7x elsewhere (257 vs 55.2 us at 1,024 terms) |
| [btree](https://github.com/Kronuz/btree#-performance) | abseil 20260817.0 `absl::btree_map`; libc++ 20.1 `std::map` | ns per `emplace` and `find`, 200,000 random strings | against abseil slower `emplace` (302 vs 271), faster `find` (283 vs 306), with runs that vary by up to 37%; faster than `std::map` (379, 319) | slower than abseil (697 vs 628, 630 vs 556); `std::map`: faster `emplace` (757), level `find` (631) |
| [cartesian](https://github.com/Kronuz/cartesian#-performance) | hash-combine of `std::hash<double>` with Boost's `hash_combine` fold | ns per `std::hash<Cartesian>`, 50,000 points | faster (0.77 vs 0.85) | slower (1.96 vs 1.50) |
| [char-classify](https://github.com/Kronuz/char-classify#-performance) | libc++ 20.1 `std::isalpha`; abseil 20260817.0 hex; loops in the bench | ns per byte | 2.4x faster than `isalpha` (0.178 vs 0.433); hex encode 1.4x faster than abseil, decode slower (1.216 vs 0.356); lowercase 11.4x faster than a loop | 4.2x (0.263 vs 1.107); encode 2.0x faster, decode slower (2.100 vs 1.019); lowercase 10.1x |
| [compressors](https://github.com/Kronuz/compressors#-performance) | zstd 1.5.7 (level 3); zlib 1.2.12; xxHash 0.8.3 | ns per call against the codec's one-call API, random bytes | faster than zstd (621 vs 695; 8,833 vs 9,458); slower than zlib (108 vs 54 at 256 B, 75,500 vs 68,625 at 1 MB) | zstd 1,901 vs 2,043, 20,530 vs 24,709; zlib 269 vs 131, 102,797 vs 84,366; XXH32 124 vs 121 us per MiB |
| [constexpr-phf](https://github.com/Kronuz/constexpr-phf#-performance) | an `if` ladder in the bench; libc++ `std::unordered_map`; gperf 3.0.3 | ns per lookup, 6 to 1,000 sparse keys; 192 field names, half missing | faster than the ladder (0.53 vs 1.39 at 6 keys, vs 138 at 1,000) and `unordered_map` (0.48-0.53 vs 1.00-1.69); slower than gperf (14.1 vs 10.9) | slower than the ladder at 6 keys (0.98 vs 0.76), faster from 46 (1.17 vs 82.8 at 1,000); `unordered_map` 0.92-1.17 vs 2.55-10.3; gperf 21.4 vs 16.5 |
| [crc32c](https://github.com/Kronuz/crc32c#-performance) | a loop of the CPU's CRC instruction, in the bench | GB/s, one buffer per call, 64 B to 1 MiB | level below 96 B (30.3 vs 30.2 at 64 B), 1.2x to 2.7x faster from 128 B | slower at 64 and 128 B (19.4 vs 22.5, 28.6 vs 30.8), 1.25x to 2.7x faster from 512 B |
| [cuuid](https://github.com/Kronuz/cuuid#-performance) | Boost.UUID 1.92.0 | ns per parse, `to_string`, generate | parse faster (8.0 vs 70.6); `to_string` slower (27.5 vs 23.0); v6 generate slower (90.9 vs 13.7 for `random_generator`, 27.4 for `time_generator_v7`) | 23.8 vs 169.8; 69.1 vs 48.7; 117.1 vs 17.8 and 45.1 |
| [datetime](https://github.com/Kronuz/datetime#-performance) | an ISO 8601 parser in the bench; abseil 20260817.0; libc `strptime` + `timegm` | ns per parse or format | 1.2x to 3.2x the hand parser's time (10.4 vs 5.9 to 28.8 vs 8.9); faster than abseil (16.0 vs 100.8 to parse, 22.3 vs 1,128 to format) and `strptime` (19.7 vs 2,192) | 26.3 vs 15.1 to 62.7 vs 26.7; abseil 40.2 vs 264.1, 48.0 vs 2,008; `strptime` 56.3 vs 7,041 |
| [docset](https://github.com/Kronuz/docset#-performance) | CRoaring 5.4.0 (`db0d1e9`) | AND, OR, ANDNOT into a new set over 2^24 ids, as docset's time over CRoaring's | faster in every cell, 0.29 to 0.89 | faster in 13 of 15 cells (0.37 to 0.98); slower at density 1e-2 on OR (1.03) and ANDNOT (1.25) |
| [double-metaphone](https://github.com/Kronuz/double-metaphone#-performance) | PostgreSQL `dmetaphone.c`, `REL_17_0` | ns per `encode_both` | faster on words and names (69 vs 196, 77 vs 207); slower on phrases and texts (607 vs 334 ns, 2.9 vs 0.64 us), where PostgreSQL stops at four characters | 113 vs 496, 130 vs 534; slower 981 vs 712 ns, 5.3 vs 1.4 us |
| [enum-reflection](https://github.com/Kronuz/enum-reflection#-performance) | abseil 20260817.0 `flat_hash_map`; a linear scan in the bench | ns per name-to-value lookup | level with abseil at 32 members (4.8 vs 4.5), slower at 128 (8.4 vs 4.8) and on misses (3.2 vs 2.4); faster than a scan (4.8 vs 17.6) | 12.7 vs 12.1; 20.0 vs 13.5; misses 9.9 vs 6.0; scan 12.7 vs 43.0 |
| [escape](https://github.com/Kronuz/escape#-performance) | a per-byte `switch` loop in the bench; abseil 20260817.0 `absl::CEscape` (another format) | time per call, 16 B to 64 KB | faster than the loop (9.5 vs 34.1 ns at 16 B, 7.2 vs 161 us at 64 KB); level with `CEscape` at 16 B (9.5 vs 10.4 ns), faster from 256 B (7.2 vs 36.1 us at 64 KB) | loop 27.3 vs 79.1 ns, 25.9 vs 288 us; `CEscape` slower at 16 B (27.3 vs 19.8 ns), faster from 256 B (25.9 vs 65.5 us) |
| [flat-map](https://github.com/Kronuz/flat-map#-performance) | Boost.Container 1.92.0 `flat_map`; libc++ `std::map` | ns per `find`, 64 to 1,048,576 entries | 1.5x to 2.7x faster than Boost (2.8 vs 4.7 to 64.9 vs 177), faster than `std::map` (16.4 to 195); random insert into 4,096 entries slower than `std::map` (171 vs 37) | 1.5x to 4.2x faster than Boost; `std::map` 5.6 vs 19.3 to 101 vs 357 |
| [flume](https://github.com/Kronuz/flume#-performance) | bare zstd 1.5.7 at level 6, no framing or checksum (nothing else frames files this way; the codec is its bound) | MiB/s of a round trip, 32 MiB of JSON, one core | 303 vs 328 (the framing costs 7.6%) | 116 vs 124 (6.5%, within run-to-run spread) |
| [fst](https://github.com/Kronuz/fst#-performance) | abseil 20260817.0 `flat_hash_map`; marisa-trie v0.3.1; libc++ `std::map` | ns per `get`, 235,976 words; bytes per key | 8.7x slower than abseil (152 vs 18) at 6.20 vs 73.32 bytes per key; faster than marisa (331, at 3.15 bytes per key) and `std::map` (422) | 2.1x slower than abseil (145 vs 68); marisa 460; `std::map` 492 |
| [fusefilter](https://github.com/Kronuz/fusefilter#-performance) | FastFilter xor_singleheader `binary_fuse8_t` (`5426b7d`); Boost 1.92.0 Bloom filter at the same 0.39% false positives | ns per lookup and per key built, 1M and 10M keys | lookups level with the reference (1.6, 2.0); build slower (38.6 vs 20.1, 43.1 vs 26.0, [fusefilter#1](https://github.com/Kronuz/fusefilter/issues/1)); lookups faster than Bloom (1.6 vs 4.3) | lookups level (5.6 vs 5.8, 13.7 vs 12.8); build slower (104 vs 38, 126 vs 53); Bloom 13.6 |
| [generation-cache](https://github.com/Kronuz/generation-cache#-performance) | `std::map` + `std::mutex`; abseil 20260817.0 `flat_hash_map` + `std::mutex` or `std::shared_mutex` | ns per `get` hit, 100,000 keys, 1 and 4 threads | faster than map + mutex (142 vs 682; 72.9 vs 2,297); slower than abseil + mutex on 1 thread (142 vs 122, [generation-cache#1](https://github.com/Kronuz/generation-cache/issues/1)), faster on 4 (72.9 vs 578); faster than abseil + `shared_mutex` (175, 284) | 434 vs 1,049, 125 vs 2,855; abseil + mutex 434 vs 396 on 1 thread, 125 vs 1,857 on 4; `shared_mutex` 447, 599 |
| [hashes](https://github.com/Kronuz/hashes#-performance) | xxHash v0.8.4 `XXH64` and `XXH3_64bits`; abseil 20260817.0 `absl::Hash` | ns per hash, 4 B to 128 KiB | `xxh64` level with `XXH64` from 16 B, slower at 4 B (1.28 vs 1.08); `wordwise` ahead of `XXH3` to 16 B (0.74 vs 1.28 at 4 B), 7x behind at 1 KiB (148 vs 21.3); `absl::Hash` faster than both at every length | `xxh64` 2.73 vs 2.39 at 4 B; `wordwise` 1.92 vs 2.87 at 4 B, 177 vs 45.1 at 1 KiB; `absl::Hash` faster |
| [htm](https://github.com/Kronuz/htm#-performance) | SDSS HTM via gkhtm (`e319c99`); H3 4.5.0; Google S2 (`677c8ce`) | ns to name one point (`getId`) | faster than SDSS (591 vs 962); slower than H3 (497) and S2 (19.8), [htm#1](https://github.com/Kronuz/htm/issues/1) | SDSS 795 vs 1,517; H3 755; S2 36.2 |
| [http](https://github.com/Kronuz/http#-performance) | Boost 1.92.0 Beast; cpp-httplib v0.64.0; a minimal Asio 1.36.0 loop (a lower bound) | `wrk` `GET /`: us at 1 connection, req/s at 64 | slower than Beast at 1 connection (87.7 vs 73.2 us, [http#1](https://github.com/Kronuz/http/issues/1)), level at 64 (35,232 vs 35,312, `wrk`-bound); httplib 73.7 us, 13,326 req/s; Asio 70.8 us | Beast 56.6 vs 39.6 us, 84,642 vs 86,066 req/s; httplib 43.0 us, 22,472 req/s; Asio 33.8 us, 126,259 req/s |
| [http-parser](https://github.com/Kronuz/http-parser#-performance) | llhttp 9.4.3 | ns per message, 7 workloads | faster on 5 of 7 (66 vs 72, 3 headers; 51 vs 72, 125-byte URL); slower with 14 headers (262 vs 243) and a 1 KB POST body (101 vs 85) | faster on 6 of 7 (151 vs 174; 545 vs 589 with 14 headers); level on the POST body (218 each) |
| [journal](https://github.com/Kronuz/journal#-performance) | a loop of one `write` and one `F_FULLFSYNC` per batch, in the bench | ms per durable `append_batch()` | about 3x slower (13.0-15.0 vs 4.0-4.1 for one op), [journal#1](https://github.com/Kronuz/journal/issues/1) | 63.0-63.4 vs 21.0 |
| [logger](https://github.com/Kronuz/logger#-performance) | fmt 10.2.1 + `std::mutex`, writing nothing | ns per `L_INFO` paid by the producer | slower: 65 vs 27 with 1 producer, 135-139 vs 86-89 with 4, [logger#1](https://github.com/Kronuz/logger/issues/1) | 398-401 vs 60-61 with 1 producer; faster with 4 while draining (78-81 vs 179) |
| [lru-cache](https://github.com/Kronuz/lru-cache#-performance) | a `std::list` + `std::unordered_map` LRU in the bench | ns per `find_and_renew`, plus `emplace` on a miss | 1.22x faster at 1,024 entries, 1.34x at 65,536, 1.06x on strings; 0.95x at 1,048,576 | 0.97x at 1,024, 1.16x at 65,536, 0.99x at 1,048,576, 1.68x on strings |
| [md5](https://github.com/Kronuz/md5#-performance) | OpenSSL EVP MD5, 4.1.0 (M4 Pro) and 3.6.5 (i9) | ns per hex digest, 16 B to 1 MiB | slower than `EVP_MD_fetch` on every row, 0.65 to 0.93 (114.7 vs 75.1 ns at 16 B); faster than `EVP_md5()` to 64 B (114.7 vs 123.2) | 0.63 to 0.78 (191 vs 121 ns at 16 B); `EVP_md5()` 359 at 16 B |
| [metrics](https://github.com/Kronuz/metrics#-performance) | a bare relaxed `fetch_add`, which wraps | ns per add per thread on one shared counter | `ContendedCounter` level (6.8 vs 7.0 at 2 threads, 194 vs 190 at 8) | `ContendedCounter` slower (43.1 vs 28 at 2 threads, 180 vs 140 at 8) |
| [msgpack](https://github.com/Kronuz/msgpack#-performance) | msgpack-c `cpp-9.0.0`; nlohmann::json 3.12.0; mpack 1.1.1 | ns per call on a 502-byte record | read slower than msgpack-c (707 vs 635), write faster (504 vs 581), read and visit every node 4.9x slower (4,903 vs 995); read faster than nlohmann (5,272), slower than mpack (283) | 1,255 vs 1,198; 765 vs 1,268; 19,825 vs 1,744; nlohmann 13,392; mpack 596 |
| [namegen](https://github.com/Kronuz/namegen#-performance) | skeeto/fantasyname C port (`e5a4752`) | ns per name from a compiled pattern | slower on `sV'i` (68 vs 27), faster from `GREEK_NAMES` (95 vs 103) to `JAPANESE_NAMES_DIVERSE` (116 vs 1,449); one-shot compile and draw slower (262 vs 27 to 20,439 vs 1,449), [namegen#1](https://github.com/Kronuz/namegen/issues/1) | 130 vs 55; 208 vs 217 to 309 vs 2,996; one-shot 786 vs 55 to 72,427 vs 2,996 |
| [queue](https://github.com/Kronuz/queue#-performance) | a mutex, condition variable and deque in the bench; moodycamel `BlockingConcurrentQueue` (`1e2def4`) | million items per second, 1x1 to 8x8 producers and consumers | 1.04x to 2.35x the mutex queue (53.4 vs 22.8 at 1x1); 3.1x to 10x moodycamel (37.3 vs 3.7 at 8x8) | 1.13x to 1.25x the mutex queue; level with moodycamel at 1x1 and 2x2, behind at 4x4 and 8x8 (5.5 vs 8.2, 4.2 vs 7.7) |
| [radix-router](https://github.com/Kronuz/radix-router#-performance) | a segment trie on abseil 20260817.0 `flat_hash_map`, in the bench | ns per lookup, 16 to 1,024 routes | faster on misses (12.0 vs 22.6) and 16 static routes (20.5 vs 28.2); slower on parameter hits (37.2 vs 32.4, 57.0 vs 35.1) and 1,024 static routes (34.9 vs 25.0) | misses 25.3 vs 36.7; 16 static 39.6 vs 57.5; parameters 72.0 vs 57.2, 122.8 vs 63.3; 1,024 static 87.2 vs 47.9 |
| [random](https://github.com/Kronuz/random#-performance) | libc++ `std::mt19937_64` and uniform distributions | ns per draw | 1.2x to 8.6x faster (2.50 vs 2.93 for `random_real`, 120 vs 1,039 for `random_string(256)`) | 1.8x to 16x (6.14 vs 11.1; 297 vs 4,702) |
| [reactor](https://github.com/Kronuz/reactor#-performance) | plain standalone Asio `asio-1-36-0` | thousand echo round trips per second, loopback | level on 1 and 4 threads (33.4-33.9 vs 33.5-34.1, host-bound) | 3-4% slower on 1 thread (106.3-107.2 vs 110.3-110.4); overlapping on 4 |
| [repr](https://github.com/Kronuz/repr#-performance) | abseil 20260817.0 `absl::CEscape` (another format) | ns per `repr(bytes)`, 16 B to 64 KB | level at 16 B (10 each); 1.3x to 4.9x faster from 256 B | slower at 16 B (26 vs 16); 1.25x to 4.3x faster from 256 B |
| [scheduler](https://github.com/Kronuz/scheduler#-performance) | `std::priority_queue` + `std::mutex`, in the bench | ns per task armed 1 ms ahead, 1 and 4 producers | `post()` faster with 1 producer (44 vs 103-104), `add()` slower (160-162); `add()` faster with 4 (660-663 vs 1,212-1,241); firing a backlog slower (66-67 vs 63-64), [scheduler#1](https://github.com/Kronuz/scheduler/issues/1) | `post()` 164-168 vs 340-344, `add()` 399-404; 4 producers 604-612 vs 3,633-3,725; backlog 200-209 vs 103-105 |
| [sha256](https://github.com/Kronuz/sha256#-performance) | OpenSSL EVP 3.5.9 (M4 Pro), 3.6.5 (i9), 3.0.13 (CI) | GB/s, one message of 64 B or 64 MiB | 1.17x EVP's throughput at 64 B (1.783 vs 1.519), 0.99x at 64 MiB (2.980 vs 3.012); Neoverse-N2 CI: 2.33x and 1.00x | no SHA-NI, so the portable kernel: 0.61x (0.114 vs 0.187) and 0.46x (0.234 vs 0.513); AMD EPYC 7763 CI with SHA-NI: 1.27x and 1.00x |
| [snowball](https://github.com/Kronuz/snowball#-performance) | libstemmer `3a59de9` (`v3.1.1-116`) | ns per stemmed word, English, Russian, German | level, 0.99 to 1.02 (114 vs 113 ns English) | level, 1.00 to 1.03 (194 vs 195) |
| [split](https://github.com/Kronuz/split#-performance) | abseil 20260817.0 `absl::StrSplit`; `memchr` and `find` loops in the bench | ns per split of comma-separated text, 64 B to 64 KB | slower than abseil at 64 B (75 vs 62), 0.7 to 0.9 of its time from 1 KB (812 vs 989); level with the loop | 228 vs 129 at 64 B; 1.22 vs 1.53 us from 1 KB; iterator 1.4x to 1.5x the loop's time |
| [stash](https://github.com/Kronuz/stash#-performance) | `std::mutex` + `std::priority_queue` in the bench; Asio 1.30.2 `steady_timer` | p99 us to arm a timer, 14 threads, 64 to 16,384 pending | 1.8 to 2.1 against 71 to 1,210 (heap) and 263 to 1,025 (Asio) | 1.1 to 1.4 against 111 to 284 and 69 to 199 |
| [storage](https://github.com/Kronuz/storage#-performance) | liblz4 or libzstd and `pread` alone, no framing | MB/s reading 256 B and 1 MiB records | reads 1.2x to 5.3x slower (one range for both machines) | as on the M4 Pro |
| [strict-stox](https://github.com/Kronuz/strict-stox#-performance) | fast_float v8.3.3; libc `strtod`; `std::from_chars` | ns per parsed `double`, short to 100 digits | slower than fast_float on 4 of 5 rows (8.9 vs 6.4 short), faster at 100 digits (28.4 vs 121.7); faster than `strtod` (12.1-92.3) and `from_chars` (15.3-174.3) | fast_float 21.2 vs 13.5, 78.8 vs 164.2; `strtod` 29.9-145.8; `from_chars` not measured (needs macOS 26) |
| [string-similarity](https://github.com/Kronuz/string-similarity#-performance) | rapidfuzz-cpp v3.3.4 | time per pair, Levenshtein and Jaro, words to 3,000 characters | faster on 5 of 6 rows (14.0 vs 226.0 us, Levenshtein at 1% edits); slower on Jaro over random bytes (2.6 vs 2.4 us) | faster on all 6 (26.4 vs 306.2 us) |
| [strings](https://github.com/Kronuz/strings#-performance) | abseil 20260817.0 `AsciiStrToLower`, `StrJoin`, `StrReplaceAll` | ns per call, 8 B to 4 KB | `lower` 0.10 to 0.67 and `replace` 0.55 to 0.76 of abseil's time; `join` of strings 1.26 to 1.31 (4.93 vs 3.75 us) | `lower` 0.09 to 0.79, `replace` 0.59 to 0.66; `join` 1.31 to 1.39 (9.17 vs 6.57 us) |
| [task](https://github.com/Kronuz/task#-performance) | Asio `asio-1-36-0` `awaitable` + `co_spawn`, `post` | ns per no-op coroutine; yield and resume p50/p99 | faster no-op (9.2 vs 10.2); yield level (42/83 vs 42/84) | clang: 18.1 vs 30.4, yield 115/133 vs 148/171; g++ 16: no-op slower (56.4 vs 23.9), yield faster (90/101 vs 122/143) |
| [term-color](https://github.com/Kronuz/term-color#-performance) | a `string_view::find` loop in the bench; libc++ `std::regex_replace` | ns per line collapsed to one depth, 110 B to 64 KB | 0.33 to 0.38 of the loop's time on colored lines (160 vs 424); the loop is faster on plain text (26 vs 27); `std::regex` 90x to 3,700x slower | 0.46 to 0.67 (311 vs 465); plain text 70 vs 60; `std::regex` 13.6 us vs 70 ns |
| [termdict](https://github.com/Kronuz/termdict#-performance) | fst `39245fa` `get`; libc++ `std::unordered_map`, `std::binary_search` | ns per `find`, 235,976 words | slowest column: 239 against fst 146, `unordered_map` 46, binary search 190 | 422 against 126, 194, 321 |
| [threadpool](https://github.com/Kronuz/threadpool#-performance) | a mutex, condition variable and `std::deque<std::function>` pool in the bench; Asio 1.30.2 `thread_pool` | ns per trivial task, 1 to 4 producers, 1 to 8 workers | fastest on every row (11.3-38.7 vs 34.8-272.3 and 48.9-841.8); start delay faster (2.9-3.0 vs 5.7-6.0 and 3.5 us) | fastest on every row (30.0-197.6 vs 122.1-1,429.7 and 228.5-2,058.2); start delay slower (5.8-6.5 vs 5.2 and 3.1 us) |
| [unicode](https://github.com/Kronuz/unicode#-performance) | utf8cpp 4.2.1; Hoehrmann's DFA in the bench; utf8proc 2.11.3 | ns per code point, 2 MB of text, decode and decode + classify + lowercase | pipeline 1.2x to 4.1x faster than the three; decode 1.4x to 1.9x faster than utf8cpp, slower than the DFA on 3 ASCII-heavy rows (0.75 vs 0.57) and utf8proc on 2 (1.08 vs 0.93) | pipeline 1.1x to 3.4x faster; decode faster than all three on every row (1.05x to 3.4x) |
| [url-parser](https://github.com/Kronuz/url-parser#-performance) | ada `ada::unicode::percent_decode` (version not stated) | ns to decode 4 KB with nothing to decode | faster (108 vs 151) | slower (139 vs 135) |
| [varint](https://github.com/Kronuz/varint#-performance) | a byte loop in the bench; LLVM 23.1 `decodeULEB128`; protobuf v36.2 `ReadVarint64` | ns per LEB128 value, 1-byte to uniform 64-bit streams | level with the loop on 1-byte values, slower on longer (2.70 vs 1.97, 32-bit); faster than protobuf on short values (0.51 vs 1.80), slower on uniform (2.70 vs 2.37) | faster than the loop and LLVM on every row (12.80 vs 18.69 and 18.37, 64-bit); protobuf: faster on short, slower on uniform (5.85 vs 3.80) |

cluster, consensus and soundex time themselves without a comparator, and each README says why:
no other library writes Xapiand's discovery frame, other Raft libraries do different durability
work, and other Soundex libraries compute the classic four-character code. Of the libraries whose
README has no "Performance" section, completion, fs, prospect, strata, time-point and times have a
`bench/` directory; the rest have no bench.

uinteger_t and base-x, from their READMEs' Performance sections and `bench/results/`:

| library | comparators | bench | arm64 (Apple M1 Pro, Apple clang 21) | x86-64 (Intel Core i9-9980HK, Apple clang 17) |
|---|---|---|---|---|
| [uinteger_t](https://github.com/Kronuz/uinteger_t/blob/master/README.md#-performance) | GMP 6.3.0, Boost.Multiprecision 1.92 `cpp_int` | `bench/bench.cc` with `-DHAVE_GMP -lgmp -DHAVE_BOOST`, or `bench/run.sh` | 1.2 to 2.3 times GMP's time on most rows; decimal `str()` faster than GMP up to 4,096 bits; a million-bit product 2,818 us (GMP 2,120, Boost 23,571) | the same pattern; a million-bit product 5,354 us (GMP 3,051, Boost 24,251; versions not recorded) |
| [base-x](https://github.com/Kronuz/base-x/blob/master/README.md#-performance) | Firedancer's fixed-size base58 (32 and 64 bytes), libbase58 | `bench/bench.cc` with `-DHAVE_FD_BASE58 -DHAVE_LIBBASE58` | 32-byte base58 encode 74.3 ns (Firedancer 48.5, libbase58 2,086), decode 71.6 (63.3, 496); 64-byte decode 98.2 (198) | 32-byte encode 143.5 ns (Firedancer 69.6), decode 186.7 (88.5); 64-byte decode 277.2 (287.1) |

## 8. Open gaps

The findings of the 2026-10-31 audits and system review that remain open or partly closed on the
default branches as of 2026-11-01, one line each. The linked Resolution tables carry the detail.

**Text** ([audit](reviews/2026-10-31-audit-text.md#resolution), [survey](reviews/2026-10-30-survey-text.md#resolution))
- strings CR4: `inplace_replace` reserves room for two matches, so the 256 B, 64-match row is 0.84x of the start.
- strings: `join(vector<string>)` is 1.5x behind `absl::StrJoin`; `join` with 1-3 elements is 0.78-0.84x of the start.
- repr, escape, strings: inputs of 1-4 bytes were not re-timed against the start code.
- strict-stox: a declined input (20-digit overflow) is parsed twice, by the fast path and by `strtol` (0.86-0.92x).
- strict-stox: the decimal-point query (`nl_langinfo`) runs on every decimal with a `.` unless `STRICT_STOX_C_LOCALE`.
- strict-stox: the bench's `STRICT_STOX_BENCH_NO_FC` switch is set by neither the README nor CMake; no `-Wconversion` build.
- stringified: the size added by the `_terminated` flag is not documented.

**Hashing, identifiers, time** ([audit](reviews/2026-10-31-audit-hash.md#resolution), [hash survey](reviews/2026-10-30-survey-hash.md#resolution), [time survey](reviews/2026-10-30-survey-time.md#resolution), [x86 survey](reviews/2026-10-30-survey-x86.md#resolution))
- hashes: no wide-lane hash in the library; `wordwise` is 6.9-9.0x behind XXH3 from 1 KiB to 128 KiB, and the wide-lane candidate lives in the bench only (`hashes:bench/candidate_wordwise8.hh`).
- cuuid: v6 `generate()` still takes two mutexes; only the time claim is lock-free.
- datetime: `TimeParser` reads each field through `strict_stoul`; `time_to_string` is a chain of `std::format` calls.
- datetime: no old-against-new ratio on x86-64 for `iso8601` formatting and `to_tm_t`.
- strings: no x86-64 numbers for `lower`/`upper`.

**Big integers and base conversion** ([record](reviews/2026-10-31-uinteger_t-base-x.md#open), [uinteger_t open work](https://github.com/Kronuz/uinteger_t/blob/master/docs/OPEN-WORK.md), [base-x open work](https://github.com/Kronuz/base-x/blob/master/docs/OPEN-WORK.md))
- uinteger_t: 1.2 to 2.3 times GMP's time on most rows of the [README table](https://github.com/Kronuz/uinteger_t/blob/master/README.md#-performance); addition takes 0.43 ns per limb against GMP's 0.31 on the Apple M1 Pro, and the rest needs assembly.
- uinteger_t: decimal parsing up to 4,096 bits takes 1.1 to 1.5 times Boost `cpp_int`'s time on the Apple M1 Pro and 1.4 to 2.0 on the Intel Core i9-9980HK.
- uinteger_t: a 4-limb quotient by a 2,048-limb divisor takes 1.3 us against GMP's 0.09 (Intel Core i9-9980HK).
- uinteger_t: no modular arithmetic and no constant-time type; every kernel's time depends on its values.
- uinteger_t: no test forces the quotient-only kernel's fallback; no build has a 32-bit `size_t`, so the size guards' call sites are untested; no CI job builds MSVC.
- base-x: the table paths are AArch64 only; a 32-byte base58 encode takes 143.5 ns against Firedancer's 69.6 on the Intel Core i9-9980HK ([README](https://github.com/Kronuz/base-x/blob/master/README.md#-performance)).
- base-x: a 1 KiB base64 decode costs 3.0 ns per byte against 1.1 to encode (Apple M1 Pro).
- base-x: `test/test.cc` pins 13 of Bitcoin Core's 21 base58 vectors, and a Release CTest build compiles out its asserts.

**Containers** ([audit](reviews/2026-10-31-audit-containers.md#resolution))
- flat-map CA5: nothing tests the hint that keeps the search branchless; `<i8,u64>` find at n=100 on the i9 is 6.4 ns against 5.0 for `std::lower_bound`.
- flat-map: insert into 64-256 entries on x86-64 is 27-43% slower than at the start, cause not isolated.
- queue: ARCHITECTURE says teardown releases parked threads (destroying a queue with parked threads is undefined); moving from a moved-from queue crashes; the README omits that moodycamel is 2-4x faster on x86-64 at 4x4 and 8x8.

**Parsers** ([audit](reviews/2026-10-31-audit-parsers.md#resolution))
- url-parser UP4: on x86-64, ada is 3-11% faster on clean 4 KB-64 KB input (url-parser leads on arm64).
- datetime DT2: the `dbg/` build directory is still in history.
- boolean-parser BP3 (owner decision): the rest of the gap to an arena parser needs an arena owner type, which changes the node API.

**Text algorithms and geometry** ([audit](reviews/2026-10-31-audit-algo.md#resolution))
- string-similarity N3: a NaN `p` or `bt` passes `Jaro_Winkler::_check()`.
- soundex: the French, German and Spanish encoders still call `replace()` per rule.

**Engine** ([audit](reviews/2026-10-31-audit-engine.md#resolution))
- fst E1: the committed `ubsan/` build directory (with local paths in `CMakeCache.txt`) is still reachable in history.
- fst: `intersect` decodes a full node per transition; `range` already uses lean frames.
- fst: `hash_of` mixes the final flag and the final output into one value.
- fst: a bounded `range` costs O(L²) for long keys; `get_le` is little-endian only.
- fst: the CHANGELOG calls the `8058003` over-read a heap-use-after-free.
- docset: the `popcnt` target clone for the bitmap AND on x86-64 is partly done (`docset:511c575`).

**Systems** ([audit](reviews/2026-10-31-audit-systems.md#resolution), [review H](reviews/2026-10-31-review-h-systems.md#resolution), [logger hand-off](reviews/2026-10-31-logger-producer-handoff.md#resolution))
- compressors C1: the fuzz target's mode 0 compares the two stream classes only; arbitrary bytes never reach `decompress_lz4`.
- logger CR7: the per-second timestamp cache misses a change of `/etc/localtime` when `TZ` is unset.
- logger and scheduler LPH-R4, R5, R6: the memory-order fix in `pending_count()`, the seq_cst load in `push()` and the `try`/`catch` around `arrivals.push_back` have no test.
- fs: the same-file test has no `st_dev` case; the missing-`S_ISREG` mutant is caught only on Linux.

**Service** ([survey](reviews/2026-10-31-survey-service.md#resolution))
- msgpack (owner decision): a per-node `Body` freelist waits on a decision about cross-thread frees.
- http: one deadline per request phase is not done; the read-ahead watch, channel and sliced reply are.

**Across the catalog** ([system review](reviews/2026-10-31-system.md#resolution))
- Pins (S4, F10): datetime pins strict-stox `21b7941` (before `7d7f5dd`); completion and journal pin allocators `2fc537f` and completion pins metrics `9207dd3`; storage and msgpack pin strict-stox `5d97979`; storage and fs pin stringified `2c78a1d`; strata, termdict and prospect pin pre-campaign fst, docset, btree or compressors; Detent and Xapiand have not moved.
- C1, F15: no owner ruling yet for Xapiand on the boolean-parser and datetime behavior changes.
- C2: the nightly CI run has not yet covered every head after the fix round.
- F2, F3: url-parser keeps its own byte scanner and hex table, and strings its own `ascii_lower/upper`, beside char-classify's shared kernels.
- F12: benchmark options still come in several spellings (the rename list is in the catalog's AGENTS.md), and only some READMEs carry x86-64 rows.
