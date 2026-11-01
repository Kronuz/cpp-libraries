# Performance: method and comparators

How the libraries in this catalog are measured, and how a change shows that it is faster and
still gives the same answers. The October 2026 measurements live in the dated surveys and
reviews under [reviews/](reviews/); what they taught is in [LESSONS.md](LESSONS.md); the fixes
that change results, and the commits not to pin, are in [UPGRADING-2026-10.md](UPGRADING-2026-10.md).

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
  stemmers, the UCD tables in unicode), and `uinteger_t` and `base-x`.

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

To be filled from each repo's README and CHANGELOG once the repo benches land: one row per
library with its comparators, CMake options, bench target, and arm64 and x86-64 numbers.

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
