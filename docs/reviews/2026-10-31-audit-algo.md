# Audit: algo (string-similarity, htm, cartesian, soundex, double-metaphone)

- Date: 2026-10-31. Kind: cluster audit of the October 2026 performance and correctness work (read-only).
- Repos: `string-similarity:ddfb8d1..0a31357`, `htm:a0321ab..f2f9109`, `cartesian:6eab8ed..0f38814`,
  `soundex:89f9d51..8b863da`, `double-metaphone:91c17a2` (no campaign commits).
- Machines: Apple M1 Pro (timing and mutants), Intel Core i9-9980HK (correctness probe, sanitizers), a shared Linux
  x86-64 VM (sanitizers), GitHub Actions runners (CI). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| A1 bound `PhoneticMetric<Encoder, Sorensen_Dice>` scores 0 | closed | `string-similarity:c0825ff` | `string_similarity_correctness` (`phonetic_dice`, all four inner metrics, both forms) |
| A2 Sorensen_Dice slower than at the start, 6-40 allocations per call | closed (per-thread bigram table, 0 allocations; before/after table in CHANGELOG) | `string-similarity:c0825ff`, `string-similarity:206f76b` | `string_similarity_differential` (against `test/frozen_dice.h`), `string_similarity_correctness` |
| A3 ASan job near its time limit; rapidfuzz cross-check never runs | closed (ASan job at `-O1` with fewer repetitions over the same lengths, `test/sanitizer.h`; `linux-asan-ubsan` took 2m40s on run 41283263532) | `string-similarity:c0825ff` | `string_similarity_rapidfuzz_check` |
| A4 README omits the rows where rapidfuzz is ahead (and the Bar's prefix strip) | closed (README lists the measured rows on the M4 Pro and the i9 with rapidfuzz beside them, including the row where rapidfuzz is ahead; Jaro strips the common prefix) | `string-similarity:206f76b` | `string_similarity_correctness` (`jaro_direct_rows`) |
| N1 `Sorensen_Dice` copies and moves leave dangling views | closed | `string-similarity:c0825ff` | `string_similarity_copy` |
| N1b non-const lvalue copy of a bound metric does not compile | closed (same fix in `soundex:407e7d1` and `double-metaphone:41656f1`) | `string-similarity:c0825ff` | `string_similarity_copy`, `soundex_copy`, `double_metaphone_copy` |
| N2 bound form compares the folded string with the raw argument | closed | `string-similarity:c0825ff` | `string_similarity_correctness` (`icase_<metric>`) |
| N3 Jaro-Winkler at `jd == bt` untested; NaN `p`/`bt` accepted | partly closed: `jw_boundary` landed; NaN `p` and `bt` still pass `_check()` (`jaro_winkler.h`: `_p < 0.0 \|\| _p > MAX_P` is false for NaN) | `string-similarity:c0825ff` | `string_similarity_correctness` (`jw_boundary`) |
| N4 `docs/API.md` snippet does not compile; ARCHITECTURE and `jaro.h` comments | closed | `string-similarity:c0825ff` | `string_similarity_api_doc` |
| N5 scratch never shrinks | closed (at most 1 MiB per thread, `STRSIM_MAX_SCRATCH_WORDS`) | `string-similarity:c0825ff` | `string_similarity_scratch`, `string_similarity_scratch_small` |
| N6 string-similarity pins the pre-campaign soundex | closed (soundex pinned at `4f192a7`) | `string-similarity:b946013` | `string_similarity_correctness` (`phonetic` checks, against the pinned encoder) |
| N7 local branch `perf/strsim` in a workspace clone | no change: nothing on origin, which has only `main` | - | - |
| H1 no HTM comparator to show "at or near the best" | no change: `htm:bench/bench.cc` still compares only with the frozen reference; no HTM library exists to compare with | - | - |
| H2 only arithmetic-preserving speedups keep the ids | no change (guidance; the H3 fix keeps every product rounded on its own) | - | - |
| H3 ids depend on the compiler's FP contraction | closed (`getId` is IEEE-754 arithmetic as written whatever the contraction mode; 396 golden ids) | `htm:cf5177b`, `htm:9006a84` | `htm_diff`, `htm_fma`, `htm_rounded` |
| C1 `hash<Cartesian>` breaks `a == b` implies equal hashes when `scale` differs | closed | `cartesian:7066e9e`, `cartesian:49f4075` | `cartesian` (`test_hash_scale`, `test_hash_domain`, `test_hash_random`) |
| S1 German/Spanish/French encoders still run `replace()` | open: `french_soundex.h`, `german_soundex.h` and `spanish_soundex.h` still call `replace()` on soundex `main` (`407e7d1`); no commit addresses them | - | - |
| S2 the two repos' CI do not test each other at head | closed (as N6) | `string-similarity:b946013` | `string_similarity_correctness` |
| D1 double-metaphone fuzz and speed | no change: the fuzz run found nothing; the single-key mode the note names landed later | `double-metaphone:82ee696` | `double_metaphone_diff` |

A2, A3 and A4 are performance, CI and documentation findings: their tests check the new code's results, and no test
fails when a speed-up, a CI setting or a README row is reverted.

## Summary

Start = last commit before 2026-10-30 on `origin/main`; head = `origin/main` at 13:00-14:30.

| repo | start | head | verdict |
|---|---|---|---|
| string-similarity | ddfb8d1 | 0a31357 | **BETTER WITH CONDITIONS** (A1-A4) |
| htm | a0321ab | f2f9109 | **BETTER WITH CONDITIONS** (H3) |
| cartesian | 6eab8ed | 0f38814 | **BETTER WITH CONDITIONS** (C1) |
| soundex | 89f9d51 | 8b863da | **BETTER** (notes S1-S2) |
| double-metaphone | 91c17a2 | 91c17a2 | **UNCHANGED** (no campaign commits; D1) |

Nothing blocks landing: no campaign-introduced defect in a changed mechanism survived my probes.
The kernels (blocked Levenshtein, one-pass Jaro, the HTM descent, the Soundex table) match
independent references on 22-24 M comparisons per platform (HTM: the start tree itself, 13.2 M
points, identical under the default flags), and 53.7 M Soundex inputs. The conditions are: a dead
combination the PhoneticMetric fix left behind (A1), a Dice regression on rows the campaign did
not target (A2), CI cost and coverage (A3), a README table that leaves out the rows where
rapidfuzz wins (A4), HTM ids that depend on the compiler's FP contraction (H3), and a false
guarantee in cartesian's new hash (C1).

## Method and hosts (read this before the numbers)

- Correctness probes, each built against the start and head trees (from `git archive`): a
  string-similarity probe (probe not kept; covered by `string-similarity:test/correctness.cc` and
  `test/oracle.h`), an HTM probe (its check now lives in `htm:test/diff_test.cc`, CTests `htm_diff`
  and `htm_fma`), a Soundex generator (probe not kept; covered by `soundex:test/diff_test.cc`), a
  cartesian probe (now `cartesian:test/test.cc`, `test_hash_scale` and `test_hash_domain`), a
  Double Metaphone fuzzer (probe not kept; covered by `double-metaphone:fuzz/fuzz_encode.cc`), a
  string-similarity thread probe (probe not kept; covered by `string-similarity:test/threads.cc`
  and `test/copy_move.cc`), an allocation probe (probe not kept; covered by
  `string_similarity_scratch_small`) and a Jaro-Winkler boundary probe (now
  `string-similarity:test/correctness.cc`, `jw_boundary`); A/B benches built from the same source
  against the start and head trees (probe not kept; covered by `string-similarity:bench/bench.cc`
  and the htm, cartesian, soundex and double-metaphone benches), and a Jaro prototype (prototype
  not kept). References were written fresh for this audit (a column-major int64 Levenshtein, a
  Jaro with flags on both sides, a hash-map Dice), plus rapidfuzz-cpp 3.3.4. Mutants: 27
  string-similarity mutants (the script is now `string-similarity:tools/mutants.py`, which carries 69) and 5 HTM mutants (probe not kept; covered by
  `htm:test/diff_test.cc`).
- Timing host: **Apple M1 Pro (arm64, Apple clang 21 -O3, no hold tool there; load 1-2 during the
  runs, nothing else benchmarking, three interleaved head/start runs per binary, best of 7 rounds
  per row)**. The head-vs-head spread in the tables is the A/A. **The Apple M4 Pro (the host behind
  the CHANGELOG/README numbers) was not measured.** Ratios, not absolute ns, are comparable with
  the repos' numbers.
- x86: Intel Core i9-9980HK (Apple clang 17) ran the correctness probe (-O2, and ASan+UBSan) and
  the repo's own three tests. **Its x86 timing and the GCC-16 `-march=haswell` HTM runs were not
  run.** No claim below is an x86 timing.
- Linux VM (g++ 11, no `<format>`): ASan/UBSan only, with a `<format>` stub and
  `-DSTATIC_STRING_NO_FORMAT` (the code under test never formats). TSan will not start there
  ("unexpected memory mapping").
- CI: `gh run list` on all five repos: the push run for every changed head is green on all 8
  jobs (linux x86 gcc/clang, arm64 gcc, macOS arm64/x86, FreeBSD, ASan+UBSan, TSan). Latest nightly
  runs are green. Only `main` exists on each remote.

---

## string-similarity

### Conditions

**A1. `PhoneticMetric<Encoder, Sorensen_Dice>` in bound form returns 0 for every pair whose codes
differ (pre-existing; the PhoneticMetric fix and "the other metrics were checked against
brute-force oracles" missed it).** `phonetic_metric.h:84-90` builds the inner metric with
`Metric(false)` and assigns `this->_str = encode()` afterwards. `Sorensen_Dice` fills
`_str_bigrams` only in its own `(T&&, bool)` constructor (`sorensen_dice.h:43,101-103`), so
`_similarity(str2)` (`sorensen_dice.h:72`) intersects with an empty vector. The string-similarity
probe, section 6 (`phon.bound.dice`): 252 failures of 784. Repro:
`PhoneticMetric<SoundexEnglish, Sorensen_Dice> p("Robert"); p.similarity(std::string("Rubin"))`
gives 0; the codes R901096 and R90108 share 4 of 11 bigram slots, 0.727. The same code is in
the start tree (read, not run). Two-argument form, Levenshtein, Jaro and Jaro-Winkler are right.
Fix: have `Sorensen_Dice::_similarity(str2)` bigram `_str` on the call (or lazily), which also
removes N1. Add the four inner metrics to `correctness.cc`'s `phonetic` block (it tests only
Levenshtein).

**A2. Sorensen_Dice is slower than at the start on rows the campaign did not target, and it
allocates 6-40 times per call (introduced by the multiset fix).** M1 Pro, start/head, head
spread <= 6%:
`Dice 1-2 chars` 25.6 -> 39.0 ns (0.66x), `Dice 63/64/65/127/128/129 chars, 4 letters` 0.78-0.86x,
`Dice 300 chars, 4 letters` 17.3 -> 23.0 us (0.75x). It is faster on words (1.4-1.7x) because
the old code built `std::set`s. `get_bigrams` (`sorensen_dice.h:48-54`) has no `reserve` and
sorts, and the < 2 characters case no longer returns before building two vectors.
The allocation probe: 6 (5 chars), 14 (64), 20 (300), 26 (3000) allocations per call, 40 with `icase`;
Levenshtein, Jaro and Jaro-Winkler are 0 up to 512 characters. Fix: early return when either
operand has fewer than 2 characters, `reserve(size - 1)`, or count bigrams in a 64 K-entry
table (one pass, no sort, no allocation).

**A3. CI: the ASan+UBSan job takes 39m56s of its 60-minute limit and the rapidfuzz cross-check
never runs.** `test/differential.cc` runs in full under ASan (CTest registers it with no
argument, `CMakeLists.txt:65`; its `quick` mode, `differential.cc:227,246`, is never used).
Run 41231661193: `linux-asan-ubsan` 39m56s (overall runs of the last three pushes: 15m21s,
42m35s, 40m00s). One slow runner fails the job. `quick` cannot simply be switched on: it drops every length >= 255, and the
mutants that move the stack/heap switch points (below, M11, M20, M22) survive it. Split the
test instead (full lengths, fewer repetitions under a sanitizer). `test/rapidfuzz_check.cc`
(the "1e-12 on a million pairs" claim) is only built with `-DSTRING_SIMILARITY_BUILD_BENCH=ON`
and is in no CI job; the brute-force oracle in `correctness.cc` is, and agrees (my probe checks
both orders against rapidfuzz as well: 0 mismatches).

**A4. The README table omits the rows where rapidfuzz is ahead, and its Jaro rows do not match
what I measure.** README (M4 Pro): Jaro random words 77 vs 66 ns, Jaro 3000 chars 26 vs 22 us.
M1 Pro, same rapidfuzz 3.3.4, `bench/bench.cc` shapes: 59.8 vs 84.5 ns and 18.1 vs 42.6 us (ours
ahead). Whichever host is right, the table is a five-row selection. Rows I measure where head
is slower than rapidfuzz (head/rapidfuzz, M1 Pro):

| row | head ns | rapidfuzz ns | head/rf | head spread |
|---|---|---|---|---|
| Jaro, 20-40 char sentences | 183.7 | 127.8 | 1.44 | 0.4% |
| Jaro-Winkler, same | 184.0 | 134.9 | 1.36 | 2.6% |
| Jaro, 64 chars, 1% edits | 239.6 | 115.8 | 2.07 | 0.4% |
| Jaro, 65 chars, 1% edits | 414.0 | 98.1 | 4.22 | 0.3% |
| Jaro-Winkler, 65 chars, 1% edits | 415.7 | 102.5 | 4.06 | 0.3% |
| Jaro, 300 chars, high bytes | 2200.9 | 1928.0 | 1.14 | 1.3% |
| Levenshtein, 3000 chars, 4 letters | 379,966 | 354,773 | 1.07 | 1.5% |
| Levenshtein, 3000 chars, 1% edits | 360,654 | 323,116 | 1.12 | 1.7% |

The 1%-edit Levenshtein gap is string-similarity lesson 8 in [LESSONS](../LESSONS.md#string-similarity)
(no banding); the README does not say so. Either put these rows in the README or close them (see Bar).

### Notes (non-blocking)

- **N1 (pre-existing, confirmed at start): `Sorensen_Dice` copies and moves leave dangling
  views.** `_str_bigrams` holds `string_view`s into the source's `_str`. The thread probe's case 1
  under ASan (g++ 11): copy a bound `Sorensen_Dice`, destroy the source, call `similarity` gives
  heap-use-after-free; short strings (SSO) make a `std::vector<Sorensen_Dice>` regrowth the same.
  Same root as A1: store nothing that points into the object.
- **N1b (pre-existing, start and head): a non-const lvalue copy of any bound metric does not
  compile.** `Levenshtein a("abc", false); Levenshtein b = a;` picks the forwarding constructor
  (`basic_string_metric.h:48`, same in each subclass). Constrain it with
  `requires (!std::same_as<std::remove_cvref_t<T>, Impl>)`.
- **N2 (pre-existing quirk): the bound form compares the *folded* stored string with the raw
  argument** (`basic_string_metric.h:82,128`), so `Sorensen_Dice(a, icase=true)` bound to `"a"` gives
  0 for `"a"` while the two-argument form gives 1 (`dice.bound`, 2 failures). Other metrics hide it
  because they compute 1.0 anyway.
- **N3: tests are strong but not tight.** Mutation results are below. The one real gap: Jaro-Winkler
  at `jd == bt` (M26, `jaro_winkler.h` `jd <= _bt` to `<`) survives all three tests. Head is right
  (the boundary probe, now `string-similarity:test/correctness.cc` `jw_boundary`: no boost at
  `bt == jd`, boost one ulp below; rapidfuzz agrees). NaN `p`/`bt` pass the constructor check
  (pre-existing).
- **N4: docs.** `docs/API.md` usage snippet does not compile (string literals: `T&&` deduces an
  array, `str1.empty()` fails; needs `std::string` arguments and `#include "levenshtein.h"`).
  `ARCHITECTURE.md:37` says `Levenshtein` and `Jaro` define the `_icase_*` kernels; `Jaro_Winkler`
  does too. `jaro.h:28` carries a merged comment (`#include <bit> // for std::countr_zero // for
  std::min, std::max`).
- **N5: scratch never shrinks.** `Scratch::ensure` keeps the largest buffer per thread and per slot
  (`bitparallel.h:56-73`); a 1 M-character pattern leaves about 48 MB per thread. Fine for the
  stated use; worth one line in AGENTS.md.
- **N6: pins.** `CMakeLists.txt` pins `soundex` at fd0e069, which predates the campaign, so CI
  tests `PhoneticMetric` against the old encoder (identical output, per soundex's diff test).
- **N7:** the local clone of string-similarity still has a branch `perf/strsim`; nothing on the
  remote.

### Evidence

**Correctness (head).** The string-similarity probe: Levenshtein with 15 cost pairs (0..4 including (0,k),
(k,0), (0,0)), `icase` on/off, two-argument and bound forms; Jaro and Jaro-Winkler (five `p`/`bt`
pairs, both argument orders, bound form) against my references and rapidfuzz; Dice and PhoneticMetric
over four inner metrics. Inputs: every string up to length 5 over `{a,A,b,0xff}`; the 32 x 32
lattice of lengths {1,2,3,31..33,62..66,126..130,190..194,254..258,319..321,383..385} where first
and last characters are forced to differ and a random prefix/suffix is added, so the length left
after trimming, which is what picks the single-word or blocked kernel, sits on every word
boundary; random, lowercase, mixed-case, all 256 byte values and 0x80-0xFF-only with NUL; 1-edit
and few-edit pairs at 5..1025; skewed lengths (1-65 against 70-2000). Results:

| host / build | checks | failures |
|---|---|---|
| i9, clang 17 -O2 (scale 1) | 22,378,831 | 254 (A1: 252, N2: 2) |
| i9, clang 17 -O1 ASan+UBSan | 22,378,831 | the same 254; no sanitizer report |
| M1 Pro, clang 21 -O2 (scale 2) | 23,870,155 | the same 254 |

Every failure is in a pre-existing class (A1, N2). Levenshtein (all costs), Jaro, Jaro-Winkler and
Dice (two-argument) are exact against the references (Jaro and Jaro-Winkler to 1e-12 against
rapidfuzz, in both argument orders), including 63/64/65/127/128/129 as raw lengths and as trimmed
lengths, high bytes, case folding of all 256 bytes (ASCII-only, `chars::toupper` and `strings::upper`
agree), the fold buffer (511-514) and the Jaro match buffer (512/513).
The thread probe's case 0: 8 threads x 12,000 mixed-length comparisons, 0 mismatches (ASan, g++ 11).
TSan did not start on the Linux VM; CI's TSan job runs only single-threaded tests.

**Repo tests.** `test.cc`, `correctness.cc`, `differential.cc` are all registered in CTest
(`CMakeLists.txt:59,65,70`) and run in CI. Built and run by hand (i9, clang 17 -O2): 20 checks;
28,217,314 checks; 4,477,828 checks, 0 failures.

**Mutation check of the riskiest claim (the blocked and single-word kernels).** 27 single-token
mutants (the script is now `string-similarity:tools/mutants.py`), repo tests at -O2 (stopping at the first failing test) and, for
memory-safety mutants, with ASan+UBSan and `differential quick` (M1 Pro, clang 21).
- Killed by `correctness.cc` (or `test.cc`): M01 carry out `Ph>>62`, M02 carry `hn` wrong,
  M03 last-bit `m % 64`, M04 score without `Mh`, M05 no top carry-in, M06 `Eh` without `hn`,
  M13/M14 Jaro start/end window masks, M17 no `t/2`, M18 window `+1`, M19 single-word window,
  M21 weighted seed `i+1`, M23 zero-cost guard, M24 distinct bigrams, M25 prefix 5, M27 no phonetic
  encode: 16/16 behavior-changing mutants.
- Killed under ASan/UBSan: M10 stale TLS index, M12 small-Peq threshold.
- Survived: M07, M08, M15, M16 are result-neutral (suffix trim, pattern orientation, the `lo`
  hint are optimizations); M09 (rows buffer one row short) is hidden by `Scratch::ensure`'s slack
  (at least 128 words, then 1.5x); M26 is N3. M11 (fold buffer 513), M20 (Jaro match buffer 513),
  M22 (weighted DP stack 257) survive the repo suite in `quick` sanitizer mode, which skips lengths
  above 193. My probe kills all three under ASan (stack-buffer-overflow at 513, 513 and 257). The full
  `differential` reaches 300/513/700, so CI's full ASan run should kill them (not rerun; 40 min).

**Allocation claim (README "No allocation per call").** True: 0 allocations per call in steady
state for Levenshtein, Jaro and Jaro-Winkler up to 512 characters, `icase` on or off; Jaro and
Jaro-Winkler allocate once above 512 (match buffer), and with `icase` Levenshtein 2, Jaro 3 (fold
heap strings); weighted Levenshtein 1 above 256. Start: 2-18 per call.

**Performance (M1 Pro, clang 21 -O3, ns per call, best of 7, three interleaved runs; spread is
head max/min - 1 across those runs; rapidfuzz columns from the same binaries).** The full table with
every row was not kept. Selection:

| row | start | head | start/head | head spread | rapidfuzz | head/rf |
|---|---|---|---|---|---|---|
| Lev random words | 126.4 | 58.4 | 2.16x | 0.2% | 100.9 | 0.58 |
| Lev near words | 147.1 | 41.8 | 3.52x | 0.2% | 67.3 | 0.62 |
| Lev sentences 20-40 | 1,414.8 | 79.2 | 17.9x | 5.1% | 110.4 | 0.72 |
| Lev 1-2 chars | 54.0 | 19.2 | 2.81x | 1.6% | 22.3 | 0.86 |
| Lev random words icase | 165.0 | 64.3 | 2.57x | 1.2% | - | - |
| Lev weighted (2,1) | 126.2 | 91.1 | 1.39x | 0.2% | - | - |
| Lev 64 / 65 / 128 / 129 chars, 4 letters | 5,681 / 5,892 / 24,116 / 24,494 | 339 / 522 / 1,022 / 1,257 | 16.8 / 11.3 / 23.6 / 19.5x | 0.3-3.0% | 398 / 758 / 1,341 / 1,658 | 0.85 / 0.69 / 0.76 / 0.76 |
| Lev 64 chars, 1% edits | 5,627 | 46.9 | 120x | 0.0% | 77.2 | 0.61 |
| Lev 300 chars, 4 letters | 136,895 | 4,212 | 32.5x | 3.1% | 4,846 | 0.87 |
| Lev 3000 chars, 4 letters | 14,057,334 | 379,966 | 37.0x | 1.5% | 354,773 | 1.07 |
| Jaro random words | 153.7 | 59.8 | 2.57x | 0.2% | 84.5 | 0.71 |
| Jaro near words | 157.4 | 61.6 | 2.56x | 0.4% | 75.5 | 0.82 |
| Jaro bound 'international' vs words | 182.3 | 48.6 | 3.75x | 0.6% | - | - |
| Jaro 128 chars, 4 letters | 6,954 | 650 | 10.7x | 0.8% | 861 | 0.76 |
| Jaro 300 chars, 4 letters | 39,996 | 1,636 | 24.5x | 0.3% | 2,134 | 0.77 |
| Jaro 3000 chars | 4,039,892 | 18,129 | 223x | 1.7% | 42,550 | 0.43 |
| Jaro-Winkler random / near words | 153.8 / 157.8 | 63.0 / 67.6 | 2.44 / 2.33x | 0.2 / 0.1% | 87.8 / 82.2 | 0.72 / 0.82 |
| Phonetic<Soundex,Lev> random words | 145.7 | 133.7 | 1.09x | 2.4% | - | - |
| Dice random words / near words | 715.9 / 663.2 | 493.6 / 470.1 | 1.45 / 1.41x | 0.2% | - | - |
| Dice 1-2 chars | 25.6 | 39.0 | **0.66x** | 1.0% | - | - |
| Dice 63-129 chars, 4 letters | 3,777-7,806 | 4,524-9,855 | **0.78-0.86x** | 1.2-3.9% | - | - |
| Dice 300 chars, 4 letters | 17,304 | 22,954 | **0.75x** | 1.5% | - | - |

The claimed speedups reproduce (Levenshtein 2.2-3.5x on words and 17-120x on long strings; Jaro
2.6-5x and 220x). The `icase` fold adds 6-37 ns (e.g. 46.9 -> 83.5 on 128 characters), not an
allocation. Comparator rows: Levenshtein is ahead of rapidfuzz on every word, sentence and
64-300-character row; behind on 3000 characters (A4). Jaro is ahead on words and from 128 characters
up and behind on the rows in A4.

**Compatibility.** `Jaro_Winkler` is no longer a `Jaro` (documented). `Levenshtein`, `Jaro`,
`Jaro_Winkler`, `Sorensen_Dice` and `PhoneticMetric` results change only in the classes the
CHANGELOG lists (the differential test asserts both sides of each class). Public signatures are
unchanged; `Jaro::jaro` is new and public. No new dependency; the bench fetches rapidfuzz only
behind its option. All eleven headers compile alone at C++20 (clang, no warnings under
`-Wall -Wextra -Wshadow -Wpedantic` with clang and gcc 16); the library claims C++20 (`requires`).
The kernels use 64-bit integer words only (no endianness, alignment or intrinsic dependence), so
there is no scalar fallback to test. README, ARCHITECTURE and AGENTS read in the present tense; the
history is in `CHANGELOG.md`.

**Bar.** Clearly better than at the start (2-40x on every targeted row, none slower except Dice, A2).
At or near the best comparator: Levenshtein yes (faster than rapidfuzz everywhere but 3000
characters); Jaro no on mid-length and long near-identical strings. **The single change: strip the
common prefix in `Jaro::jaro` before building the masks** (rapidfuzz does this in
`Jaro_impl.hpp`: `remove_common_prefix`, with `CommonChars += prefix`; the stripped characters
match themselves position by position, so the match count grows by the prefix length, the
transposition count is unchanged, and the window bound still comes from the full lengths).
Evidence, the Jaro prototype (prototype not kept; the change landed as `string-similarity:206f76b`)
(M1 Pro, clang 21 -O3, 512 pairs per row, results identical to `Jaro::jaro` within 1e-12 on every
pair, 0 mismatches), ns per call:

| pairs | head | + prefix strip | speedup | rapidfuzz (bench table) |
|---|---|---|---|---|
| words 3-12, 1 edit | 51.5 | 37.8 | 1.36x | - |
| 20-40 chars, 2 edits | 130.5 | 92.7 | 1.41x | 127.8 (sentences) |
| 64 chars, 1 edit | 250.0 | 136.3 | 1.83x | 115.8 |
| 65 chars, 1 edit | 515.5 | 142.6 | 3.61x | 98.1 |
| 129 chars, 1 edit | 916.6 | 541.6 | 1.69x | - |
| 64 / 65 chars, unrelated | 264.9 / 439.2 | 270.4 / 391.4 | 0.98 / 1.12x | 316.9 / 496.0 |

The gain is the prefix, not the loop. A second prototype in the same file, a direct 256-entry
mask table with incrementally updated window masks (the other candidate from rapidfuzz's
single-word code), gives 1.00-1.10x on every row, so the loop is not the bottleneck. The strip also
explains the 65-character cliff: with one edit the remainder falls to at most 64 characters, so
the pair leaves the blocked path (head 414 -> 143 ns here; rapidfuzz 98). Unrelated strings, the
case head already wins, are unchanged. A production version needs the blocked path to take the
shared bound as well; I prototyped only the single-word remainder and fall back otherwise (129
characters: 1.69x).

---

## htm

**Verdict: BETTER WITH CONDITIONS (H3).** Identical to the start under the default contraction
modes of Apple clang; not under `-ffp-contract=fast`.

**Correctness.** The HTM probe builds against the real start tree and the head tree and writes
`getId` as raw uint64 and `getTrixelName(Cartesian)` strings; `cmp` of the two outputs:
**13,181,369 points and 680,299 names, byte-identical**, M1 Pro clang 21 at -O0 and -O2. Points:
25^3 special values (0, -0, +-1, +-0.5, 1/sqrt2, 1/sqrt3, 1e-300, 1e-16, DBL_MIN, denormals, 1e300,
2, -3, NaN, +-inf) as raw and normalized triples; the 1-degree latitude/longitude grid with both
poles and the antimeridian through the lat/lon constructor, plus 1/8-degree sweeps along lon 0,
+-90, 180 and the equator and at 89.999999; 1.5 M Gaussian-normalized, 0.375 M cube-uniform
(unnormalized) and 0.375 M lat/lon-uniform points (each lat/lon point also as its raw x, y, z);
and, built with plain arithmetic independent of the library, trixel
vertices, edge midpoints, centroids and one-ulp neighbours per coordinate down to level 26, plus
points on arcs. Mutants of the descent (probe not kept: `> 0` to `>= 0`, reciprocal-multiply
normalization, regrouped dot product, reordered sqrt sum, a changed child test order): **5/5 killed
by both the repo's `diff_test.cc` and my probe**, including the two that only move points within
rounding of an edge. The CI diff test also passes on linux-arm64-gcc (contraction on by default).
The code spreads `getId`'s arithmetic into `triple()` inline, where the old path went through
out-of-line `Cartesian` operators; that is where a compiler that fuses across statements can
diverge, and H3 shows it does.

**H3. The ids are bit-identical to the start only where the compiler does not fuse across
statements; under clang `-ffp-contract=fast` they differ on 0.68% of random points (the same size
as the start's own flag-to-flag variation).** M1 Pro, clang 21, the 13.18 M points above, start
tree vs head tree built with the same flags (script and results not kept; the check lives in
`htm:test/diff_test.cc` under CTest `htm_fma`):

| flags | start vs head, differing ids |
|---|---|
| `-O2` (default `-ffp-contract=on`) | 0 of 13,181,369 |
| `-O3 -ffp-contract=off` | 0 of 13,181,369 |
| `-O3 -ffp-contract=fast` | 6,154,658 (specials 2.83%, lat/lon grid 0.41%, **random points 17,844 of 2,625,000 = 0.68%**, edge points 59%) |

The same table for start against start with different flags: `-O2` vs `-O3 -ffp-contract=off`
differ on 21,667 random points (0.83%); `-O2` vs `-O3 -ffp-contract=fast` on 17,844 (0.68%).
So the algorithm's last levels sit at the double-precision noise floor, and an id there depends on
how the compiler fuses `a*b - c*d` and the dot product; the divergence of random points is confined to
the deepest digits (start `on` vs `off`: digit 1 = 16,280, 2 = 4,088, 3 = 985, 4 = 236, 5 = 59,
6 = 18, 7 = 1, counted from the leaf). Head under `fast` reproduces start under the default `on`
(23,950 differing bytes of 105 M), so head is no less stable across flags than the
start; but the claim "ids are bit-identical" and the README's "ids are stored in indexes, so the
encoding must not change" hold per build configuration, not across them, and the diff test cannot see
it because its frozen reference is built with the same flags in the same run. GCC fuses across
statements by default on aarch64 and on x86 with `-mfma`/`-march=haswell`+; CI's linux-arm64-gcc job
passes the diff test, which says GCC's fusion matches here, but I could not run GCC 16 `-march=haswell`
(see Method). Fix: a CTest that compares `getId` with a checked-in table of golden ids (a few
hundred points, including near-edge and level-25 points) so any build whose contraction changes an id
fails; say in README/AGENTS.md that indexes need the same FP contraction on the writer and the
reader (or compile `htm.cc` and `cartesian.cc` with `-ffp-contract=off` and accept a one-time id
change, an owner decision).

**Performance (M1 Pro, ns per call, three interleaved runs, head spread <= 3%):** `getId(Cartesian)`
1117 -> 697 (1.60x); poles and axes 682 -> 386 (1.76x); `getTrixelName(Cartesian)` 1199 -> 787
(1.52x); `getTrixelName(id)` and `getId(name)` unchanged (1.00x, 91 and 13.9 ns). The CHANGELOG gives
no number; [LESSONS](../LESSONS.md#htm) says 1.8x on the M4 Pro. Reproduced as 1.5-1.8x.

**Compatibility.** Public signatures unchanged. `getTrixelName(Cartesian)` is now
`getTrixelName(getId(coord))`: equal on all 680,299 names, including NaN and infinities. That
path now relies on the unchanged `ceil(log2(id))` in `getTrixelName(id)`, which is computed in
double for ids up to 2^54; for valid ids the later `++` and `&= ~1` absorb the off-by-one that
rounding can produce (an id just above 2^53 converts to 2^53), and the 680 K names confirm it. The
CMake build pins `cartesian` at 34bf069 (before the hash change).

**Notes.**
- H1: `bench/bench.cc` compares only with the frozen reference, and there is no HTM library in
  the tree to compare with. "At or near the best comparator" cannot be shown; against the plain
  3-double descent it matches ([survey](2026-10-30-survey-algo.md): 489 ns).
- H2: what would go further: the descent does 3 sqrt and 9 triple products per level. Any algebraic
  shortcut (no sqrt, an error-bounded filter) changes ids at the noise floor of H3, so only
  arithmetic-preserving speedups (batching the three midpoint square roots) keep them.

---

## cartesian

**Verdict: BETTER WITH CONDITIONS (C1).**

**C1. The new hash breaks `a == b` implies `hash(a) == hash(b)` when `scale` differs, and the
header comment and ARCHITECTURE.md say equal points hash equally (pre-existing behavior kept,
claim introduced).** `operator==` compares `x, y, z, SRID` (`cartesian.cc:195-198`); `scale` is a public
member that `normalize()` sets to the old norm. The hash mixes `x * scale` (`cartesian.h:226-228`).
The cartesian probe (start and head both fail): `Cartesian n(3,4,0); n.normalize();` (x = 0.6, y = 0.8,
scale = 5) and `Cartesian m(0.6, 0.8, 0.0)`: `n == m` is true, the hashes differ, and
`std::unordered_set<Cartesian>{m}.count(n)` is 0. The start hash had the same flaw (it printed
`x*scale`). The comment at `cartesian.h:212-215` ("Equal points hash equally, including 0.0 and
-0.0") and `ARCHITECTURE.md:118-120` ("so equal points hash equally") are false as written; the
test (`test.cc` `test_hash`) checks only signed zeros. Fix: hash exactly what `==` compares (`x`,
`y`, `z`, SRID); the `to_string()` rationale no longer applies. Add the `normalize()` case to
`test_hash`.

**Evidence.** Start and head, the cartesian probe (M1 Pro): start also fails `-0.0 vs 0.0` (fixed at head).
Distribution (head): 65,341 lat/lon grid points, 1,000,000 Gaussian points and 100,000 points
1e-12 apart all give distinct 64-bit hashes (start: the 100,000 close points all collided into 1
value). Weak spot, not a blocker: a 100^3 integer lattice reaches a maximum bucket load of 21 in
2^20 power-of-two buckets (random keys: 9); the mix is one multiply and one xor-shift per
coordinate, so doubles with empty low mantissa bits cluster. Libraries using prime bucket counts
(libc++, libstdc++) see 9.

**Performance (M1 Pro):** `std::hash<Cartesian>` 286.5 -> 2.2 ns (130x; CHANGELOG says about 300x,
M4 Pro); `unordered_set<Cartesian>` insert 317.8 -> 36.1 (8.8x), find 302.2 -> 18.9 (16.0x); unchanged
rows: constructor lat/lon 19.3 -> 19.7 (0.98x), `toLatLon` 143.5 -> 143.6, `distance` 17.2 -> 17.0,
`to_string` 284.5 -> 284.1, `operator==` 2.2 -> 2.2 (head spread <= 3.7%). No regression.

**Compatibility.** Hash values change (documented; none of the family persists them: a grep of
the family's clones finds no user outside cartesian itself). `noexcept` added to the hash. Header
adds `<cstring>` only; self-contained.

---

## soundex

**Verdict: BETTER.**

**Correctness.** The Soundex generator against the start and head trees, M1 Pro: **53,659,554 inputs
identical** (every string up to length 6 over a 17-symbol alphabet with one symbol per Soundex class
in both cases, a space, a digit, a hyphen, 0xE9, NUL; 4 M random byte, lowercase and mixed strings
of 0-39 bytes; the named words), through `SoundexEnglish().encode(s)`, `SoundexEnglish(s).encode()`
and, at head, `encode(std::string_view)` and `encode(const char*)`; the entry points agree with each
other. German and Spanish changed in comments only.

**Performance (M1 Pro):** words 3-12 85.4 -> 30.2 ns (2.83x); 40-80 characters 598 -> 214 (2.80x);
mixed punctuation 139 -> 51 (2.72x); constructor + `encode()` 100 -> 37 (2.71x); head spread <=
1.8%. The CHANGELOG claims no number; [LESSONS](../LESSONS.md#soundex) says 4.1x on the M4 Pro
(66.8 -> 16.3 ns). The M1 Pro ratio is 2.7-2.8x.

**Compatibility.** `_encode(std::string_view)` accepts what `_encode(std::string)` accepted
(`std::string`, `const char*`) and also `std::string_view`, which did not compile before.
Output identical. C++20, header self-contained.

**Notes.** S1: only English changed; the German/Spanish/French encoders still run `replace()` over
the string, so the gains do not extend to them. S2: `string-similarity` pins the pre-campaign soundex
(N6), so the two repos' CI do not test each other at head.

---

## double-metaphone

**Verdict: UNCHANGED.** No commits since 91c17a2 (2026-10-28). By the survey bar
([PERFORMANCE.md](../PERFORMANCE.md)) it is not better than at the start because nothing moved;
nothing is worse either.
- D1: the fuzzer (ASan+UBSan, M1 Pro): 300,000 random and adversarial inputs (any byte, rule-trigger
  letters, Latin-1 lead bytes, punctuation, 0-63 bytes, plus strings of 1 K, 64 K, 1 M) give no
  sanitizer report; keys use only the documented alphabet; determinism, `encode` ==
  `encode_both().first`, case-insensitivity and the bound constructor hold. Eight of my nine
  published-value expectations match; the ninth ("Thompson" gives `TMPSN` where I remembered
  `TMSN`) is what the repo's own `test/test.cc:62-64` pins as the reference behavior, so I withdraw it.
- Speed (A/B build, unchanged rows, M1 Pro): 205.1 / 204.6 ns per word, 1374.8 / 1371.9 ns for 40-80
  characters (start/head). The [survey](2026-10-30-survey-algo.md)'s "not worth it" (`encode`
  computes both keys and drops one) stands unless the owner wants it: single-key mode is the one change.
- No `CHANGELOG.md` and no `bench/`; neither is needed while nothing changes.

---

## Not run

- Apple M4 Pro timing (the claimed-number host). All speed ratios above are M1 Pro.
- x86 timing, and HTM with GCC (16, `-march=haswell`, default `-ffp-contract=fast`): not run (see
  Method). H3 is therefore measured with clang `-ffp-contract=fast` on arm64 only.
- The README bench command through CMake (needs `cmake`; the M1 Pro has none).
- TSan (does not start on the Linux VM); the full-size ASan differential on mutants M11, M20, M22.
- Sanitizers on arm64; GCC on arm64 (CI covers linux-arm64-gcc for correctness only).
- A prototype of the Dice fix (A2); only the Jaro change under Bar was prototyped.
