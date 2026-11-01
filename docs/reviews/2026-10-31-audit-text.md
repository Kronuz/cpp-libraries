# Audit: text (repr, escape, strings, strict-stox, stringified)

- Date: 2026-10-31. Kind: cluster audit of the October 2026 performance and correctness work (read-only).
- Repos: `strict-stox:f0f7374..6d8731f`, `stringified:c8c9033..a60ce6c`, `strings:62fb121..efcc6e2`,
  `repr:2063945..e56ded0`, `escape:f4efd99..4c0bdda`.
- Machines: Intel Core i9-9980HK, a shared Linux x86-64 VM. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| CR1 strict-stox rounding mode, negative decimals | closed (the fast path declines unless the mode is to-nearest) | `strict-stox:199e0be`, `strict-stox:eab850c` | `strict_stox_rounding` |
| CR2 strict-stox locale guard untested | closed | `strict-stox:eab850c` | `strict_stox_locale_mock` (and `strict_stox_locale` where a comma locale is installed) |
| CR3 stringified implicit `const char*` constructor | closed | `stringified:0053465` | `stringified_overloads` |
| CR4 strings regressions on unbenched rows | open: `strings.hh` on `main` still reserves room for two matches in `inplace_replace` and the CHANGELOG lacks the 256 B rows; a fix is in progress on the `ci/cr4` branch on GitHub (WIP commits, latest `a1d9070`), not on `main` | - | - |
| CR5 repr/escape mixed input on x86 | closed (64 KB mixed on the i9: escape 3.70x, repr 3.32x over the 8-byte kernel; escape 1.6x faster than `absl::CEscape`) | `char-classify:d670574`, `escape:198ce98`, `repr:c15ee3d` | `escape:bench/bench.cc`, `repr:bench/bench.cc` ("mixed 10% 64 KB") |
| note: repr/escape/`lower` slower at 1-4 bytes | partly closed: the shared kernel is 1.00x-1.22x of the 8-byte kernel at 1-8 B (escape and repr CHANGELOGs), with no re-timing against the start code at 1-4 B; `lower(string_view)` at 1 B is unchanged on `main` (in the CR4 branch) | `char-classify:7eb6468` | - |
| note: strict-stox declined inputs pay for the attempt (20-digit ERANGE 0.86-0.92x) | open: no commit or CHANGELOG entry on `main` addresses the second parse | - | - |
| note: strict-stox `localeconv()` on every decimal with a dot | partly closed: `nl_langinfo(RADIXCHAR)` replaces `localeconv()` where `langinfo.h` exists (3-5 ns per CHANGELOG) and `STRICT_STOX_C_LOCALE` skips the query; it still runs on every decimal with a `.` | `strict-stox:199e0be` | `strict_stox_locale_mock` |
| note: strict-stox bench does not build from the README command | partly closed: `<algorithm>` is included before `namespace old` (`eab850c`); `std::from_chars(double)` is behind `STRICT_STOX_BENCH_NO_FC`, which neither the README nor CMake sets | `strict-stox:eab850c` | - |
| note: strict-stox `pow10` float table warning, `STRICT_STOX_FAST_FP` leaks | partly closed: both are gone from the header since the table-driven fast path; no `-Wconversion` build pins the warning | `strict-stox:199e0be` | - |
| note: repr and escape carry the same 100-line core; CMake comment over a pinned SHA; escape pin in a `[skip ci]` commit | closed (one kernel in char-classify; both CMake comments say the pin is a commit; the later pins are not `[skip ci]`) | `char-classify:d670574`, `repr:c15ee3d`, `escape:198ce98` | `chars_escape_kernel`, `repr_diff`, `escape_diff` |
| note: stringified `sizeof` grows by the `_terminated` flag, undocumented | open: `ARCHITECTURE.md` describes the member; no doc or CHANGELOG states the size change | - | - |
| bar: strings `join(vector<string>)` 1.5x behind `StrJoin` | open: `join` on `main` still reserves and appends | - | - |

The code fix for CR1 (`199e0be`) landed before its tests (`eab850c`). Against `6d8731f`'s header the rounding test fails
(`[upward] stod("-0.1") bits bfb999999999999a, libc bfb9999999999999`), and with the guard line deleted the locale mock test
fails while `strict_stox_fp`, `strict_stox_diff` and `strict_stox_long` pass; `strict-stox:tools/fp_mutants.py` has mutants for both guards.

Start = last commit before 2026-10-30 on `main`; head = `main` at 13:00 on 2026-10-31.

| repo | start | head | verdict |
|---|---|---|---|
| strict-stox | f0f7374 | 6d8731f | **BETTER WITH CONDITIONS** (CR1, CR2) |
| stringified | c8c9033 | a60ce6c | **BETTER WITH CONDITIONS** (CR3) |
| strings | 62fb121 | efcc6e2 | **BETTER WITH CONDITIONS** (CR4) |
| repr | 2063945 | e56ded0 | **BETTER** (CR5 is a note) |
| escape | f4efd99 | 4c0bdda | **BETTER** (CR5 is a note) |

All five are much better than at the start, with correctness evidence I reproduced
independently. The conditions are four fixes of a few lines each. Two of them break
behavior the campaign said was unchanged: a rounding-mode divergence in strict-stox and an
overload ambiguity in stringified. The other two are an untested locale guard and small
regressions in strings on rows its benchmark did not target. Nothing found blocks the
existing callers (fs and storage use `stringified` only through direct initialization).

## Conditions (fix round)

**CR1 strict-stox: under a directed rounding mode the fast path differs from `strto*` for
negative decimals (introduced).** `strict-stox:strict_stox.hh` `fast_fp`, `out = neg ? -r : r` rounds |x|
and then negates. In FE_UPWARD that gives -(x rounded up), but strtod returns x rounded
up. glibc and macOS libc both follow the rounding mode. A probe (`rounding_section`; probe not kept,
covered by `strict-stox:test/rounding_test.cc`): 2372 / 30012 mismatches upward, 2384 downward, 0 toward zero
(a shared Linux x86-64 VM, g++ 11 -O2). On the Intel Core i9-9980HK (macOS) the counts are 2358, 2448 and 0. Example:
`stod("-.10")` upward gives -0.1, libc gives -0.099999999999999991. `stof("-0.1")` gives
-0.10000000149 against -0.09999999404. The start header called strtod, so it matched by
construction, and the header comment and README say "identical". Fix (one line): apply the
sign to the exact operand before the single rounding,
`const R m = neg ? -R(w) : R(w); r = k >= 0 ? m * pow10[k] : m / pow10[-k];`. Add
`rounding_section` as a test.

**CR2 strict-stox: the locale guard has no test.** I deleted
`if (dot && *std::localeconv()->decimal_point != '.') return false;` (mutant S1; probe not kept).
With it gone, `strict_stox_test`, `strict_stox_diff` and
`strict_stox_long` all still pass (the Linux VM, g++ 11). The probe's `locale_section` runs under
`de_DE.UTF-8` and in a `uselocale` thread. It finds 0 mismatches on head and 29,028 on the
mutant (the i9, macOS). Example: `stod("1.5e2")` gives 150 where libc gives EINVAL. Fix: add a
test that sets a ',' locale when one exists (it skips on the CI Linux runners, which have
no de_DE).

**CR3 stringified: the new implicit `stringified(const char*)` makes literal calls
ambiguous (introduced, source compatibility).** A probe (probe not kept; covered by
`stringified:test/overload_test.cc`) declares `f(stringified)` / `f(std::string_view)` and `g(stringified)` /
`g(const std::string&)` and calls each with `"abc"`. It compiles against start and fails
against head with `call to 'f' is ambiguous` and the same for `g`. Before, a literal needed
two user-defined conversions to reach `stringified`, so only the other overload was viable.
The CHANGELOG lists the constructor under "Added" with no compatibility note. Fix: mark it
`explicit`. Direct initialization still picks it (an exact match beats the `string_view`
constructor), so `c_str()` keeps aliasing literals. In-family callers (`fs:fs.cc`, `storage:storage.h`)
use direct initialization only.

**CR4 strings: regressions on rows the bench does not cover or the CHANGELOG leaves out
(the i9, Apple clang 17 -O3, under an exclusive timing hold).** Ratios are old/new, all runs listed:
- `replace` 1->3 chars, 256 B, 64 matches (in `strings_bench`, missing from the CHANGELOG
  table): **0.84 / 0.86 / 0.84** (1.52-1.58 us -> 1.81-1.84 us).
  `inplace_replace` reserves `str.size() + (rs - ss) * 2`, which is room for two matches,
  so the result reallocates as it grows.
- `replace` with a single match, 256 B (edge bench; probe not kept): **0.92 / 0.93** (120 -> 130 ns). The
  new code searches once for a second match, then the in-place loop repeats that search.
- `join(vector<string>)` with 1 / 2 / 3 elements: **0.79-0.80 / 0.78-0.80 / 0.84**
  (+2-4 ns). It gains 1.28x at 10 elements.

Fix: count the matches before reserving, or reserve for all of them. Reuse `next` in the
single-match path. Skip the sizing pass when `count <= 2`. Add the 256 B and single-match
rows to the CHANGELOG.

## Notes (non-blocking, follow-ups)

- **CR5 repr/escape, x86 is not arm: mixed input gains nothing at 64 KB.** On the i9, 3 runs:
  mixed 10% 64 KB is repr 0.98-1.02x and escape **0.96-0.98x** (150.5-156.3 us against
  old 147.0-151.1 us). `absl::CEscape` does it in 61.7-65.3 us, 2.3x faster. The same input
  at 256 B gains 1.5-1.67x. That points at mispredicted 1/2/4-way `switch` branches once
  the pattern is too long for the predictor to learn; this is my inference, not profiled.
  The CHANGELOGs claim 2.8-3.5x for "10% non-printable" with no platform caveat. Binary
  4 KB: 1.31-1.37x, absl 1.3x faster.
- **repr/escape, 1-4 byte inputs (edge bench):** repr without a quote is 0.80-0.83x at 1 B
  and 0.86-0.88x at 4 B (+3.5 ns). escape is 0.91-1.02x and 0.94-0.95x. From 8 B up the
  gain is 2.6-3.3x. `lower(string_view)` is 0.71-0.72x at 1 B (+2 ns) and 2.1x at 8 B.
- **strict-stox, inputs the fast path declines pay for the attempt (edge bench):**
  `" 42"`, `"+42"`, base 0 and `"0x1f"` are 0.95-1.01x; `" 1.5"` is 0.95-0.98x; a 20-digit
  ERANGE is **0.86-0.92x**, because the fast path parses up to the overflow and `strtol`
  then parses again. On the 17-digit `stod` row, g++ 16 gives 0.95-0.96x with an A/A of
  0.96-0.99x (noise) and llvm 23 gives 1.01-1.08x.
- **strict-stox, `localeconv()` on every decimal with a dot.** `stod("3.14")` takes 21.1-21.3 ns
  and `stod("1e-5")` 10.0-10.4 ns, so about 11 ns of the fast path is that call on the i9
  (macOS). POSIX also does not require `localeconv` to be thread safe; glibc rewrites a static
  `lconv` on each call.
- **strict-stox bench does not build from the README command** on macOS 15 with Apple
  clang 17, where `from_chars(double)` is unavailable before macOS 26, or with g++ 16.
  `namespace old { #include "strict_stox_old.hh" }` pulls `<algorithm>` into `old` because
  bench.cc does not include it first; diff_test.cc does. I timed it with `-include algorithm`
  and, for llvm 23, `-D_LIBCPP_DISABLE_AVAILABILITY`.
- strict-stox: `pow10` initializes a `float` table from `1e11`, a new
  `-Wfloat-conversion` warning in a public header (g++ 11 `-Wconversion`).
  `STRICT_STOX_FAST_FP` leaks out of the header.
- repr.cc and escape.cc carry the same 100-line core twice. [LESSONS](../LESSONS.md) names duplicated
  scanners as a failure mode, and the campaign plan ([PERFORMANCE.md](../PERFORMANCE.md)) asked for one shared core. Their CMake comment
  "track its tip with GIT_TAG main" sits over a pinned SHA (pre-existing). escape's
  char-classify pin bump (306ecd9 -> a890496) landed in a `[skip ci]` commit. It builds and
  passes ctest on the i9 (macOS).
- stringified: `sizeof` grows by the `_terminated` flag. This is ODR-only for a header-only
  type, but undocumented. The CHANGELOG says the tests pass under GCC 11 ASan. On the Linux VM,
  GCC 11's libasan loops in `AsanOnDeadlySignal` at startup (an environment problem, see
  [LESSONS](../LESSONS.md)), so I could not confirm GCC; clang 12 passes.
- Every head is a `[skip ci]` commit. I checked the diffs since the last CI-run commit: docs,
  comment-only code edits, and escape's pin. The last CI run on each default branch is green
  on all 8 jobs (Linux gcc/clang/arm64, macOS arm64/x86, FreeBSD, ASan+UBSan, TSan). There
  are no stray remote branches.

## Evidence

**Correctness (independent probes; each kills a mutant on the riskiest claim).**

| repo | probe | result | mutant (repo tests / probe) |
|---|---|---|---|
| strict-stox | (probe not kept; covered by `strict-stox:test/long_test.cc`, `test/rounding_test.cc`, `test/locale_test.cc`), libc oracle: random ints in bases 0/2/8/10/16/34-36 with signs, spaces and `0x`; fast-path-shaped decimals compared bit-exact; 50-310 byte padded inputs; the 120-135 byte stack-buffer edge; embedded NUL; errno kept; exception kind | 8.2M checks, 0 mismatches (the Linux VM, g++ 11 -O2); 1.46M under clang 12 ASan+UBSan, 0; the i9 (macOS) de_DE 0 | S2 (2^54 mantissa limit): diff 6, long 2 / probe 1634. S1 (no locale guard): **all pass** / probe 29,028 |
| stringified | (probe not kept; covered by `stringified:test/test.cc`): sizes 0-80 and up to 300, copy/move ctor and assign over three target kinds, source destroyed first, chains, self-assign, swap, vector growth, exact-size heap view | clang 12 ASan+UBSan (the Linux VM): 10,234 checks, 0 failures; start header: stack-use-after-scope in `c_str()` on the first case | `owns()` returns false: repo test heap-use-after-free / probe stack-use-after-scope |
| repr, escape | (probe not kept; covered by `char-classify:test/escape_kernel_test.cc`), reference written from the contract: every byte at every position of 1-40 byte windows at offsets 0/5/10/15, random mixes up to 70 KB, max_size sweep including `SIZE_MAX` | 11.43M checks, 0 failures (clang 12 ASan+UBSan and g++ 11 -O2, the Linux VM) | M1 (no quote test in `dirty8`): repr diff 27,002, escape diff 14,592, probe 82,763. M2 (0x7f missed): repr diff 1,414, escape diff 886, probe 16,999 |
| strings | (probe not kept; covered by `strings:test/fix_test.cc`): lower/upper/hasupper over all bytes; join over int, long long, ull, char, signed and unsigned char, short, double, string, string_view and bool, with a predicate; `inplace_replace` against Python `str.replace` with overlapping patterns | 341,003 checks, 0 failures (Apple clang ASan+UBSan, the i9) | R1 (overlapping matches): diff_test 13,622 / probe 5,716 |

The frozen copies in each repo's `test/` are byte-identical to the start code except for the
function names (strict-stox, repr, escape diffed).

**Performance, x86** (Intel Core i9-9980HK, macOS 15, exclusive timing hold, 3 runs; strict-stox with g++ 16
and llvm 23/libc++, the rest with Apple clang 17 -O3 and Homebrew absl). A/A for strict-stox is
an old-vs-old build of the same bench: 0.96-1.02 on every row.

| row | old -> new (ns), speedup | comparator |
|---|---|---|
| stoi 1-9 digits | 41.4-42.4 -> 10.8-11.7 (g++), 3.6-3.9x; 9.2-9.7 (llvm) | from_chars 10.1-10.4 (libstdc++), 12.6-12.8 (libc++) |
| stoull 1-19 / stoul hex | 64-67 -> 14.9-16.2, 4.1x / 100-102 -> 13.7-15.1, 6.8-7.4x | from_chars 18.4-18.7 / 20.2-20.8 |
| stod short decimals | 38.1-40.8 -> 23.0-23.9, 1.7x | fast_float 12.6-13.0, from_chars 16.3-17.2 (libstdc++) |
| repr printable 16 B / 4 KB / 64 KB | 2.6-2.8x / 3.6-3.7x / 2.4-2.7x | CEscape: 1.5x faster at 16 B; ours 1.6x faster at 4 KB; tie at 64 KB |
| repr max_size=64, 4 KB / 64 KB | 27-28x / 433-447x (arm claim 54x / 940x) | |
| escape printable 16 B / 4 KB | 3.1-3.3x / 2.4-2.5x | CEscape 1.3x faster at 16 B; ours 1.35x faster at 4 KB |
| lower(string_view) 4 KB | 7.3-7.6 us -> 244-251 ns, 30x | AsciiStrToLower 2.6-2.8 us (ours 11x faster) |
| join(vector<int>) 1000 / join(vector<string>) 1000 | 1.45x / 1.04-1.09x | StrJoin tie / **StrJoin 1.5x faster** (6.4 vs 9.5-9.9 us) |
| replace 4 KB, 1024 matches | 1.48-1.56x (arm claim 3.1x) | StrReplaceAll tie |

**Bar.** Every library is clearly better than at the start. The rows that are not yet at
or near the best comparator, each with the one change that would close it:
- strict-stox `stod` short decimals, 1.8x behind fast_float on x86: stop calling
  `localeconv()` per call (about 11 ns of 21, measured above), for example
  `nl_langinfo(RADIXCHAR)`, measured first.
- strings `join(vector<string>)`, 1.5x behind StrJoin: `resize` to the exact total and
  `memcpy` each piece instead of `reserve` plus `append`, which checks capacity on every
  append.
- repr/escape mixed or binary input on x86, 1.3-2.3x behind CEscape: emit a dirty block
  without a branch, storing a 4-byte table entry per byte and advancing by its length.
  This rests on the 256 B against 64 KB evidence in CR5 and is unprofiled.

**Not run.** Arm re-timing of the claimed numbers on the Apple M4 Pro and the Apple M1 Pro. GCC ASan: the Linux VM's GCC 11
libasan loops at startup. TSan: no concurrent code changed.
