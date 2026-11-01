# Lessons from the October 2026 performance and correctness work

The record of what the October 2026 work on these libraries taught: the surveys of 2026-10-30, and
the perf work, audits and fix rounds of 2026-10-31 ("the campaign" below). Each item says what went
wrong or what worked, why, the fix, and the number with the machine it was measured on. The machines
are described in [PERFORMANCE.md](PERFORMANCE.md#2-machines); the full measurements are in each
library's CHANGELOG (linked under its heading) and in the dated [reviews](reviews/). The themes come
first, then one section per library, grouped as in the catalog, then delivery.

## The themes

Almost every win came from one of ten mistakes, repeated across libraries.

1. **A general tool on a tiny, fixed-shape job.** `strto*`, `std::regex`, `std::format`,
   `gmtime_r`, `std::mt19937`+distribution, `uniform_int_distribution`, `std::map`. Each is
   correct and 10-100x too heavy for a 2-digit field, a hex nibble or a 6-bit draw.
   Keep the general path as the exact slow fallback, put a specialized fast path in front.
   (datetime 5-79x, strict-stox 3-4x, `random_string` 4-8x but `random_int` only 1.6x
   (3.9 to 2.4 ns), url-parser 50x on clean input.)
2. **Per-call setup that nobody asked for.** Zeroed 256 KB ring buffer per lz4 call, a
   full mt19937 init per UUID, two heap vectors per Levenshtein, a 4n+2 zero-filled buffer
   per escape, two `std::string` signatures per fst node. Measure the 16-byte case, not only
   1 MB: the setup is the whole cost there (lz4 decompress 256 B: 20-50x).
3. **Byte-at-a-time with a function call or a capacity check per byte.**
   `back_inserter`, `push_back`, `result += c`, FNV-1a beside xxh64. Size once, write through
   a pointer, scan runs of "boring" bytes in bulk (NEON/SSE2/SWAR). (lower 60x; repr's byte
   path 2.5-6.6x on arm and 1.5-3.2x on x86, [x86 survey](reviews/2026-10-30-survey-x86.md). repr's 54-940x is
   the `max_size` rows, an algorithmic fix that jumps over the elided middle instead of scanning it:
   [repr](#repr) item 1.)
4. **Textbook O(nm) where a word-parallel algorithm exists.** Levenshtein 46x, Jaro 150x
   with bit-vectors. Ask "is this a bit-vector problem?" before tuning a scalar loop.
5. **Synchronization that the common case does not need.** `notify_one` on every op,
   a 1 s polling `wait_for` hiding a lost-wakeup bug, an exclusive mutex around a read-mostly
   cache, a CAS loop on a counter that never saturates. Count waiters, fix the actual race,
   take the fast path only when provably safe. (queue 3.5x, gen-cache 4-7x, metrics 2.0x on arm64, threadpool 3-68x.)
6. **Hidden allocation in innocent places.** "Constants", temporaries, case-folding copies,
   `x = T{}` on a struct owning a vector, a decoded node copied per transition.
7. **Bench the API people call, not the kernel.** sha256 kernel was fine; the hex string
   around it was 13x slower. Always benchmark the public entry point at small sizes.
8. **Guessing the hotspot.** "scalar popcount" was wrong; the cost was a mispredicted
   bit-extraction loop. Cuuid "skip the twist" gave 1.5x, not 3x: the init chain is serial.
   Profile the stage before choosing the intrinsic.
9. **Behavior is a contract, including the bugs.** Jaro_Winkler returned Jaro, the Jaro match
   was non-standard, implicit OR regrouped neighbours, Bloom bit layout is a de facto format,
   `hash<Cartesian>` was a formatted string. The method that worked: freeze the old code and
   optimize against it (differential tests over random input, every byte at every position,
   mutants), then judge the old behavior against an independent oracle before deciding what is a
   bug. Under the owner's authorization the campaign then fixed defaults (standard Jaro and a real
   Jaro-Winkler, implicit-OR precedence, five datetime quirks), each with its changed input
   classes listed (old != new inside, old == new outside) and a consumer upgrade note; the Bloom
   layout stayed, and the faster filters are opt-in types.
10. **Missing tests hid real bugs while "optimizing".** Review found: exception-unsafe cache
    insert, a saturating counter visible as unsaturated, a lost task per 2M adds, a pool
    inside an allocator value that libc++ copies (heap corruption), `repr(max_size=1)` buffer
    overflow, `copy_file` without O_TRUNC. Tests that only count or follow the happy path
    never see these; property/differential/mutation tests do.

Five more are about correctness and delivery rather than speed.

11. **A frozen-copy differential reproduces bugs.** It proves the new code gives the old
    answers, wrong ones included. The perf work copied strict-stox's 63-byte cut into its fast
    path as "same results", and froze Jaro, Jaro-Winkler and weighted Levenshtein, the
    implicit-OR precedence bug and five datetime quirks. Independent oracles found them: libc
    `strto*` on the same bytes, brute force, rapidfuzz, a recursive-descent parser written from
    the grammar, Hinnant's days-from-civil. Use the frozen copy to show nothing else changed and
    an oracle to show the answer is right.
12. **Measure both instruction sets.** SWAR is not SIMD: repr gains 5.7x on 4 KB of printable
    text on arm and 3.0x on x86. A guard written for one architecture misses the other: XXH32
    pins its lanes to scalar registers on AArch64 only, which leaves x86 1.4-2.1x slower than the
    same code guarded on SSE2. A branch-predictor win can be arm-only: docset bitmap AND at
    density 0.1 was 3.6x on arm and 1.0x on x86 until it chose its routine per CPU. The READMEs
    quote arm; put an x86 row beside every ratio that depends on the architecture.
13. **A fix is delivered when the consumers' pins move.** FetchContent keeps the first
    declaration, so the top-level project's pins decide what runs. After the fixes landed,
    storage still pinned the compressors commit that reserves 64 MB for 98 KB of hostile LZ4
    (`0498bf5`), and Detent and Xapiand still ran the scheduler that loses tasks. Bump the
    consumers in waves, each green before the next, and give them one upgrade note
    ([UPGRADING-2026-10.md](UPGRADING-2026-10.md)). The pins and waves are under [Delivery](#delivery).
14. **The campaign repeated the original's duplication.** Optimizing each library alone copied
    kernels instead of sharing them: escape and repr carried the same 100-line table-and-SWAR
    kernel (byte-identical output over 1,598,720 checks), five libraries kept private byte-class
    scanners, url-parser added a second hex-digit table beside char-classify's, and datetime
    kept two calendar engines. It is the original's "duplicated scanners that silently
    diverged", one level up. The fix round moved the escape kernel and a block scanner into
    char-classify (`char-classify:d670574`) and datetime onto one calendar (`datetime:773205b`);
    url-parser's scanner and hex table and strings' case folding are still private copies. Before
    optimizing a mechanism, find its other copies and put the kernel in the shared leaf
    (char-classify) once.
15. **Process mistakes.** Build directories were committed, work went to a branch the consumers do not
    pin, a `[skip ci]` commit moved a FetchContent pin, a main went red on test inputs that depended
    on evaluation order, a per-thread cache had no cap, removing a timed poll exposed four missing
    notifies, and an `O_TRUNC` came before the same-file check. The audits caught each one; the
    change's own tests did not. The details and numbers are under [Delivery](#delivery).

Where the original design failed, in one line each: convenience over cost (reach for the std
facility), no benchmark habit at small sizes, hot paths written once and never profiled,
exported implementation details (regex objects, bit layouts) that froze the design, and
duplicated scanners that silently diverged.


## Foundations: bytes, strings, parsing

### char-classify

[CHANGELOG](https://github.com/Kronuz/char-classify/blob/main/CHANGELOG.md)

1. (A bug the perf work introduced.) The first escape and repr speedup copied one 100-line kernel into both
   repositories, and each repository's differential compared only with its own frozen copy, so nothing in either
   could notice the two drifting. The [system review](reviews/2026-10-31-system.md) found it with a byte-identity
   probe (1,598,720 checks, 0 mismatches). When a second library needs the loop you just optimized, move it into the
   library both already depend on before the copy exists, and test it once against an oracle written from the rules
   (an escaper in the test, every byte at every position), not against the code it replaces.
2. Reloading the block after every escape puts load, compare, movemask and ctz on the critical path of each escape,
   about 20 cycles. Compute the mask once and walk it: the chain is a one-cycle clear-lowest-bit and the stores are
   independent.
3. A fast path for few escapes is a slow path for many. All-binary input was 0.7-0.8x of the old byte loop until a
   block with six or more escapes went through the table instead (then 1.3x on an Intel Xeon, 1.8x on Apple silicon,
   11-30x where the old loop mispredicted). Put the densities in the bench (1, 3, 10, 25, 50, 100 percent), not one
   "mixed" row.
4. A branch on "this block is clean" beat a branch-free count: counting both masks for every block made 4 KB of
   printable text 1.5x faster, and testing the first mask for zero 2.5x. Baseline x86-64 has no popcnt, so
   `std::popcount` is a dozen shifts (or a library call); a 256-entry table is cheaper, and only the dirty blocks pay
   for it.
5. A call is as expensive as a one-byte escape. Moving the loops into a header stopped the compiler inlining them into
   `escape()`, and 1 to 8 byte inputs got 5-25% slower (`repr` made four calls). The fix was `always_inline` on the
   two thin functions and `noinline` on the vector loops, and the check was the `bl`/`call` in the disassembly, not
   another timing.
6. The tests must reach the code. The differentials' "every byte at every position" stopped at 17-byte windows; the
   vector loop runs only while 32 bytes remain, so every old test would have passed with it never executing. Make the
   window cover each loop's bound plus a block, and keep slack canaries around the output so an overrun that stays
   inside the allocation fails.
7. An equivalent mutant is information. "The SWAR test also flags 0x20" survived because a false positive only sends
   that block to the table path and the output is identical; the mutant that matters misses 0x1f. Write the mutant
   that breaks the output, and say which ones cannot (the dense-block threshold changes speed, not bytes).
8. Time variants in one binary, one sample each in rotating order, with the old code in a second slot as the A/A.
   Separate processes in a fixed order made the last variant 10% slower (thermal drift) and moved the 1 byte rows by
   15% on layout alone. Compile the variants from the same sources under renamed namespaces (`-Dchars=chars_v1`) so
   only the code differs.

### repr

[CHANGELOG](https://github.com/Kronuz/repr/blob/main/CHANGELOG.md)

1. "Elide the middle" must jump, not scan: `repr(..., max_size=64)` was O(n) (30 us at 64 KB); head and tail from
   arithmetic make it O(max_size) (33 ns, 940x). Check the boundary conventions of the old loop (a pre-incremented
   cursor shifts every comparison by one) with an exhaustive size x max_size differential.
2. A differential test against a frozen copy also finds latent bugs of the old code that the new code deliberately
   does not copy: `repr(max_size=1)` wrote past its one-byte buffer, an empty search string in `replace` never
   terminates, and the old loop used out-of-range pointer arithmetic for small inputs. Freeze the oracle first, then
   decide per finding.
3. The max_size == 1 overrun was only guarded inside the differential test, which skipped empty input and could not
   run the old code under ASan. A dedicated test now pins the exact outputs (max_size 1: bare quotes, max_size 2:
   quotes around "...") for sizes 0..20, all quote modes and both friendly modes; against the old implementation it
   fails (stray NUL). escape has no max_size parameter, so it has no equivalent.

See also [escape](#escape), items 1 to 3 (exact sizing, the SWAR block copy, SWAR against SIMD on x86), and
[char-classify](#char-classify), items 1 to 8 (the kernel repr shares with escape).

### escape

[CHANGELOG](https://github.com/Kronuz/escape/blob/main/CHANGELOG.md)

1. `string::resize(4n + 2)` for a worst-case bound zero-fills four times the input. A counting pass over a 256-entry
   output-length table plus one exact `resize` is cheaper, and the same table drives the writer so the two cannot
   drift: printable text 4-6x faster.
2. Do not look at bytes one at a time when most are plain. One 64-bit load tested with SWAR ("any byte < 0x20,
   >= 0x7f, backslash or quote?") bulk-copies clean blocks; a dirty block falls back to the table, so all-binary input
   pays one extra test per eight bytes and still gains (1.45x), where a pure run-copy loop was slower than the
   original.
3. SWAR is not SIMD, and an arm-only gain is a signal to look at x86. The 8-byte SWAR test gave printable text 5.7x on
   arm64 but 3.0x on x86, and nothing at all on mixed input at 64 KB (0.96-1.02x on an Intel Core i9-9980HK, while
   `absl::CEscape` was 2.3x faster). The classification was never the cost there; the cost was a data-dependent branch
   per escape. A 16-byte NEON or SSE2 test that finds the escapes from one mask (ctz, clear the lowest bit) took the
   same row from 148 us to 27 us on a GitHub Actions Linux x86 runner (5.4x, 2.8x faster than `absl::CEscape`) and
   from 54 us to 16 us on a GitHub Actions arm64 runner. In the final code on the i9 the row is 144 us to 39 us (3.7x;
   `absl::CEscape` 62 us), on the Apple M4 Pro 28 us to 13 us (2.1x).

See also [char-classify](#char-classify), items 1 to 8 (the kernel escape shares with repr).

### strings

[CHANGELOG](https://github.com/Kronuz/strings/blob/main/CHANGELOG.md)

1. Writing through `back_inserter` (or `push_back` in a loop) is a capacity check per byte and blocks vectorization.
   Copy the input once and transform in place with arithmetic (`c + 32` if `c - 'A' < 26`): `lower` 4 KB 7.4 us ->
   119 ns (62x), also 10x faster than `absl::AsciiStrToLower`. A 256-entry table lookup per byte is the scalar-only
   form.
2. Quadratic in-place edits: `std::string::replace` per match shifts the tail each time. With several matches and a
   size change, build the result in one pass (4 KB: 34.7 -> 11.2 us).
3. **Search once.** The first version looked for a second match to choose between two strategies and then repeated
   the search in the one it chose. The final one finds the matches before editing (an array of 16 on the stack, a
   vector for more), so no search repeats and each tail moves once: shrinking closes the gaps in one forward pass,
   growing with room moves each tail up last match first, growing without room builds the result in one exactly
   sized buffer. The candidates were measured against each other before one was kept (counting then rescanning,
   recording offsets, plain replace calls).
4. **Fixed costs decide the small rows.** A sizing pass plus `reserve` costs 2 to 4 ns more than three appends; the
   set-up of a vectorized loop costs more than four table lookups; recording match offsets and re-checking aliasing
   costs more than two `replace` calls on a 16-byte string. Below a size, do what the old code did (appends, a table
   lookup per byte, one `replace` per match), and use the new algorithm only where it pays: strings up to 32 B, up to
   four short joined strings, fewer than eight bytes.
5. **Inlining moves rows by 5 to 60% and cannot be predicted.** A one-element shortcut placed inside the shared
   `join_impl` made 1000-element joins 1.5x slower on the Intel Core i9-9980HK although it was never on that path, and
   a small path written inline in the public `join` did the same; the same code in a separate function did not. A
   helper layer in front of the short path cost 2 ns at two elements until it was written out by hand. Measure each
   structure on every compiler and CPU that matters (Apple clang and g++ 16 on x86, Apple M1 Pro and Apple M4 Pro),
   not only on the machine the change was written on.
6. **A new fast path must keep what the slow one guaranteed.** The old loop of `str.replace` calls kept a replacement
   that viewed into the string correct for one call only; an in-place compaction or a `resize` does not. The new paths
   copy such a search or replacement first (checked by a test with every size relation), instead of leaving a result
   that depended on the order of edits.
7. `indent` walked lines with `Split`, whose default skips empty pieces, so blank lines and the trailing newline
   vanished and "" became just the prefix. Reusing a general splitter for a line-preserving transform needs a
   round-trip property (join of the lines == the input); the Python `textwrap.indent` golden values caught it.
8. An empty search in `inplace_replace` never terminated (each insertion grew the string as fast as the cursor
   advanced). A loop that mutates what it scans needs a progress argument; the exhaustive small-domain test with the
   Python rule is the guard. The old code cannot even be run by a differential test, so the frozen copy is excluded.
9. `hasupper` called `isupper(char)`: locale dependent and undefined for negative chars. Use the same ASCII
   classification as the neighboring `upper`/`lower`; test all 256 byte values against `'A' <= c <= 'Z'`.
10. **A test cannot pin a speed, but it can pin what makes the speed.** The small-row regressions of item 11 were not
    testable by a timing, and an allocation counter does not work (GCC 16 folds replaced `operator new` counters). The
    tests check the buffer after the edit instead: the capacity of a grown result is within one allocation granule of
    its size, a shrinking or same-size edit keeps the data pointer and capacity, a string with room is edited in
    place. The pre-fix header fails them, as do 20 single-line mutants of the new paths (a mutant run beside the
    tests).
11. **A bench built around the target rows hides the corners.** The first pass benched 4 KB and 1000-element inputs,
    and reported 3x. On the i9 the same code was 0.84x on `replace` of 256 B with 64 matches, 0.92x on a single match,
    0.78 to 0.84x on `join` of 1 to 3 strings and 0.71x on `lower(string_view)` of 1 B, none of them in the bench or
    the changelog. The [text audit](reviews/2026-10-31-audit-text.md) found them with an edge bench. The repo's bench
    now has 68 rows: every size from 1 B to 4 KB, 0 to 1024 matches, shrinking, same-size and growing replacements,
    `upper`, the in-place forms and the predicate joins. Bench the grid around an optimization (size x count x
    direction) before claiming it.

See also [repr](#repr), item 2 (the empty search in `replace`, found by the differential test).

### stringified

[CHANGELOG](https://github.com/Kronuz/stringified/blob/main/CHANGELOG.md)

1. Passing a named rvalue reference to a member initializer copies (`_str(str)`): `std::move` it.
2. A new implicit single-argument constructor is a new conversion in every overload set that already takes the type.
   The earlier "alias C strings in `c_str()`" change added `stringified(const char*)` and made `f("abc")` ambiguous
   between `f(stringified)` and `f(std::string_view)`, and between `g(stringified)` and `g(const std::string&)`: a
   literal then reached each parameter by a different user-defined conversion, and two different constructors are
   never ranked. A constructor template does not fix it either (checked on Apple clang 17 and g++ 16); only `explicit`
   does, and direct initialization (`stringified(path)`, the only form in fs, storage and Xapiand) still picks it. The
   [text audit](reviews/2026-10-31-audit-text.md)'s overload probe caught it; the change had been verified only by the
   tests of the new behavior, none of which had a second overload.
3. The same constructor also made `stringified(static_string)` ambiguous, which the audit's probe did not cover:
   `static_string` converts to both `const char*` and `std::string_view`, and a plain `const char*` parameter makes
   the two viable. A template on the exact pointer types (`const char*`, `char*`) keeps such a type on the
   `std::string_view` constructor. Probe a new constructor with the family's own types, not only with literals.
4. A view-plus-owned-string class cannot copy the view: a short string's buffer lives inside the object, so a copied
   view dangles into the source, and a moved one into the moved-from object. Decide "view points at my own _str" by
   pointer equality and rebind after every copy/move.
5. "Peek at the byte after a string_view" is undefined behavior for any view not over a terminated buffer; track
   terminated-ness explicitly (whole std::string, own storage) instead of probing.
6. The API document had shown `log_line("from a literal")` as working, an example no compiler had seen, and the
   implicit constructor made it true. Documentation examples are code: `test/overload_test.cc` now builds the calls
   the document shows, `static_assert`s which conversions are implicit, and fails to build against the previous
   header, an implicit constructor, and a non-template explicit one (all three checked).
7. The tests that caught the dangling view and the over-read: sizes 0..80 (SSO and heap) across copy/move
   ctor/assign, source destroyed before use, under ASan (heap-use-after-free on the old header); a malloc'd exact-size
   buffer for the over-read.
8. Verification of the constructor fix ran on g++ 11, clang 12 and ASan+UBSan on the shared Linux x86-64 VM, and on
   the repository's own GitHub Actions runners (8 jobs, green), plus a GitHub Actions probe branch of fs and storage
   with their stringified pin moved to the fix. Nothing in the fix needed timing.

### strict-stox

[CHANGELOG](https://github.com/Kronuz/strict-stox/blob/main/CHANGELOG.md)

1. A wrapper around `strto*` that copies to a NUL-terminated buffer and saves/restores `errno` pays about 15 ns before
   any parsing. Put a cheap exact fast path in front: only inputs every `strto*` reads identically (optional `-`,
   digits of the base, whole string, no overflow), and decline everything else to the old code so errno/idx/exceptions
   stay identical: `stoi` 19.5 -> 6 ns (faster than `std::from_chars`).
2. A correct floating-point fast path needs no new dependency when the common case is easy: mantissa <= 2^53 and
   |decimal exponent| <= 22 make `m * 10^k` or `m / 10^k` one correctly rounded IEEE operation (Clinger): 19 -> 10 ns
   for short decimals. Decline long inputs by length up front: parsing a 17-digit value twice (fast attempt, then
   `strtod`) cost 30%. Eight-digits-at-a-time SWAR parsing did not pay on 5-8 digit inputs (an extra test per
   position); measure before keeping a clever step.
3. A fast path that accepts only the easy cases moves the common case onto the slow path. The Clinger-only path took
   mantissas up to 2^53 and exponents up to 1e22, which is none of the `%.17g` or JSON doubles people actually print:
   17-digit text still cost a full `strtod` (23-48 ns), and on top of that every dotted input paid a libc locale
   query. Before calling a fast path done, measure what share of realistic inputs it accepts (here 0% of 17-digit
   text).
4. A truncated 64-bit table of powers of five and ONE 64 x 64 -> 128 multiply decide all but about one 17-digit text
   in a thousand. The rest can decline to the path that already exists, so there is no second multiply, no 128-bit
   table (5 KB, not 10 KB) and no big-integer code in the hot path. The price of declining is 0.1% x 25 ns; the price
   of writing the exact tail is code that must itself be proven. Derive the decline rule from the error interval
   (exact product in `[P, P + 2^64)`: ambiguous iff a halfway point falls in it, one test on the low bits) instead of
   copying a rule whose derivation you cannot state.
5. `ERANGE` is part of the contract and libcs disagree on it for subnormals. Decline subnormal, zero-from-nonzero and
   infinite results (and anything that rounds up into the normal range from below it) instead of reproducing a libc's
   convention; it keeps one source of truth for errno.
6. Branch-free is not automatically faster. Reading digit runs with a count of trailing zero bits, a shift and three
   multiplies beat a byte loop for long runs; reading the 1..7 byte tail the same way with overlapping loads was 20-30%
   slower (8.4 -> 11.2 ns) than the byte loop on an Apple M1 Pro. Measure each "improvement" in its own binary.
7. A libc call in a hot path can cost as much as the work around it: `localeconv()` (3.6 ns on an Apple M4 Pro, 14 ns
   on an Intel Core i9-9980HK under macOS) against a 6-8 ns parse. `nl_langinfo(RADIXCHAR)` returns the same decimal
   point for a third of the cost on x86 (5.9 vs 14 ns) and nothing on arm64. Where the semantics (locale awareness)
   forbid dropping the call, keep it, put it last so it overlaps the arithmetic, and offer the opt-out as a macro and a
   recorded owner decision with both columns of numbers; do not flip a behavior to hit a speed target.
8. A slow path that takes work from libc has to be timed against libc on the rows it takes, before it is tuned. The
   first exact path (big integers for every text it decided) took 428 ns on subnormal text against libc's 27 ns on the
   M4 Pro (+1,500%), and 36 ns against 21 for exact halfway points of 16 digits. What fixed it was deciding before
   building: the table gives a candidate and says "surely below the smallest normal value"; a subnormal result is then
   `ERANGE` with no arithmetic unless the value is exactly representable, which needs `5^-q` to divide the digits as a
   number, so 713 digits or more for a `double` (every shorter text is inexact: a three-line test); texts of 19 digits
   or fewer with `|q| <= 27` compare in 128 bits; a short text does not rebuild a digit array. Result (M4 Pro, libc
   before -> now): subnormal 26.8 -> 17.5 ns, `stof` subnormal 64.8 -> 17.5, ties 58.5 -> 18.5 and 21.4 -> 15.9,
   overflow and underflow 30.4 -> 21.2, with every old row inside the spread and `fast_fp`'s instruction stream
   identical (M4 Pro, M1 Pro, i9). Write the benchmark rows for the new path first (halfway points, subnormals,
   overflow); the speed of the common path says nothing about them.
9. A fixed `char buf[64]` plus `strncpy` made the wrapper silently cut every input at 63 bytes, and a later
   `size != str.size()` check turned the cut into EINVAL, so valid long input failed. A fixed buffer needs an explicit
   fallback (heap) and a test one byte past each limit.
10. The earlier perf work copied the 63-byte limit into the fast path (n < 64, n <= 17) as "same results"; a
    differential test against a frozen copy of a bug reproduces the bug. The oracle must be libc on the same bytes.
11. Verification of the 63-byte fix: exhaustive strings up to 5 chars over a 10-letter alphabet, each also padded with
    62..200 zeros or spaces, against libc strto* (13.9M checks); the same test against the old header fails 2.9M of
    them.
12. The first fast path (70b8325) rounded |x| to nearest and applied the sign afterwards. Under `fesetround(FE_UPWARD)`
    that returns the wrong neighbor for every inexact negative text (2,358 of 30,012 random texts upward, 2,448
    downward, none toward zero), while the README said "identical to strtod". The
    [text audit](reviews/2026-10-31-audit-text.md)'s probe caught it by setting the mode and comparing with libc;
    199e0be answered with a guard (decline unless the mode is to nearest) and one test of 2,000 texts. State that the
    default hides (rounding mode, locale, errno, FP flags) needs a test in every state and a non-vacuity check: libc
    must give a different answer from the default for thousands of the texts (5,000 to 6,700 of 15,524 here), or the
    test passes with the guard deleted. Derive a few expected values by hand from the decimal (0.1 upward is the double
    above 0.1) so the oracle is not the thing under test.
13. A test that needs something the GitHub Actions runners lack is no test: the guard for a ',' decimal point ran only
    where `de_DE` was installed, so deleting the guard passed every test on the GitHub Actions Linux runners and the
    shared Linux x86-64 VM (the audit's mutant S1). Put a seam in the code (a macro for tests,
    `STRICT_STOX_DECIMAL_POINT`, replacing the `nl_langinfo` call at compile time) so the decision is tested
    everywhere, keep the real-locale test for the machines that have one (on glibc a locale can be built with
    `localedef` from a 6-line LC_NUMERIC source and `LOCPATH`), and make the mutant list name the test that must kill
    each mutant, so a conditional test cannot be the one that "kills" it.
14. `errno` for a subnormal result is not portable: glibc sets `ERANGE` only for an inexact one, Apple's libc for every
    one. The exact path returns `ERANGE` for the inexact (all libcs agree) and hands the exactly representable ones to
    libc, so each platform keeps its own answer, and the test compares the API with that platform's libc (ASan/UBSan,
    TSan, clang on glibc; macOS on GitHub Actions runners) rather than a convention. TSan on the Linux VM's kernel
    aborts at start ("unexpected memory mapping") unless run under `setarch -R`.
15. Test the property, not examples: "accepted implies identical to libc, with errno clear and the whole text
    consumed", plus an acceptance-rate floor (a path that declines everything is "correct"). Build the hard inputs, do
    not hope for them: the exact decimal expansion of the halfway point of every binade, its neighbors (+-1 in the last
    digit, truncated at 17..56 digits, truncated plus a trailing 1) with a 20-line big integer, at full length
    (770 digits), for `double` and `float`. Then break the code 34 ways (`tools/fp_mutants.py`); the survivors were
    informative: an exponent accumulator that wraps at 2^64 needed `1e18446744073709551616` in the list, and a mutant
    that is not a bug (strtod also accepts a leading '+') is a mutant to drop, not a test to add. Rereading the
    saturating accumulator found a hole no random test could reach: clamped at 10^5, a 7-digit exponent next to a
    mantissa of 10^5 digits cancels into an in-range q (`0.` + 99999 zeros + `1e1000001`, really 1e900000, came out as
    0.1). Saturate to a value that always declines, never to "a large number" that arithmetic can undo.
16. A mutant that survives is information about the test, and some survivors are legitimate: a reader window of 18
    digits or a zero scan that stops early only makes the fast path decline more, which no correctness test can see.
    Answer with a floor on the share taken (99.5% of in-range long text; measured 99.7% to 100%), fixed in size so the
    sample, and the verdict, are the same on every platform and under sanitizers. A third survivor (a non-zero scan
    that ignored the first byte of an eight-byte group) needed a text whose only evidence of being above a halfway
    point is one digit at the start of a run of zeros: build it from the halfway point itself (first 19 digits, next
    digit plus one, 0 to 23 zeros).
17. Survivors of the mutation run of the exact path were two different things. `slow_zero_sign`: a branch that only a
    direct call reaches (the fast path takes every all-zero text first), so the test calls the function directly.
    `slow_no_renorm`: the renormalization inside the comparison loop could not matter, because the candidate is below
    the value by less than 2^-59 of itself and the next comparison is then always "below": the loop ends with the
    carried mantissa and one renormalization after it is enough. A branch you can prove dead is deleted with the
    argument in a comment, not kept with a test that cannot reach it.
18. Oracles fail too, and a long run is how you find out. libstdc++ 11.2's `std::from_chars(double)` aborts on long
    input (`floating_from_chars.cc:78`, "alignment != 1"); Apple's libc `strtod` aborts on valid text such as
    `99004559013337762701442583720290300000000000.00000000000000` (`Assertion failed ... divideMPByMP, file
    strtofp.c, line 1390`; macOS 15.8 and 26.7, `strtof` is fine; even `awk` crashed on it). Keep libc (the contract)
    as the primary oracle, cap the secondary ones by length, trap SIGABRT around the libc call (siglongjmp), report the
    text as a libc bug instead of a mismatch and keep checking against the other oracles. `strict_stod` returns the
    right value for that text because the fast path takes it; texts the fast path declines still reach libc.
19. A libc oracle can be wrong, and the platform that shows it is the one you do not test by hand. The first GitHub
    Actions run of the exact path failed only on FreeBSD: `strtof` returned the smallest normal value (1.18e-38) with
    no errno for four texts of about 2e-44, and the API (right) said `ERANGE`. The test had an independent expectation
    for those texts (built from the halfway point of two neighbors, no libc), so the failure was classified in one
    run: print both answers in the message, then count a libc that is wrong by construction as a libc bug, never as a
    mismatch. Keep the exact expectation as the primary oracle and libc as the cross-check, and run a pre-landing CI
    before touching main (`workflow_dispatch` on a pushed branch runs the same 8 jobs).
20. Compare with a competitor in the same binary and report its best: `fast_float` moved by 10% between two builds of
    the same bench (code layout), a bigger effect than most of the micro-optimizations tried. Run every variant twice
    in the same session and print the second run's distance from the first (the A/A column).
21. The commit that landed after the audit was never reviewed, and its benchmark had no row for the branch it added.
    Text of more than 19 digits went through a second byte-by-byte pass over every digit the SWAR scan had just read:
    25 to 40 digits took 55 ns against 45 for `strtod` (and `fast_float` 30), 100 digits 173 ns (39), 800 digits
    1.36 us (135). Reading the same digits with eight-byte loads gives 20, 29 and 138 ns (i9: 107 -> 67, 196 -> 79,
    1,208 -> 262; `fast_float` 74, 80, 257). Every branch a change adds needs a benchmark row against the code it
    replaces and against the best comparator, including the rows nobody writes by hand (long inputs).
22. A benchmark population has to land in the code under test. 800 random digits with the decimal point anywhere
    overflow `double` 60% of the time, and overflow is declined to `strtod` on purpose (`ERANGE` has one source), so
    the row measured the decline path (1.3 us) instead of the digit reader (131 ns). Print the share the fast path
    takes next to the timing (the bench has a `fast%` column now) and keep generated values in range.
23. Measure a change to a cold function on every architecture, and compare the hot function's code before timing. The
    first form of the long-text fix handed the integer and fraction runs from `fast_fp` to `fp_long`: two more live
    values in the hot function. On the M4 Pro nothing moved; on the i9 the short rows were 3% to 17% slower (`stod` of
    1-9 digit integers 11.2 -> 12.9 ns, twice). The cure was to restore `fast_fp` to the text of the previous commit
    and let the cold function find what it needs (`memchr`, a few ns on the path nobody is in a hurry on), then diff
    the instruction streams of the hot function between the two headers: identical on clang and g++, x86_64 and arm64
    (a 10 line CI step that strips labels and numbers). The remaining difference was not code: a bench that holds two
    copies of a header in one process is decided by where each copy lands (the old copy measured 11.2 ns, and 12.2 as
    the only header of its binary). Time the two versions as the only header of separate binaries. A/A inside one
    process does not see this.
24. Sanitizer builds of a test with big-integer loops run 20x slower (and `nice 19` on a loaded machine starves them):
    scale the loops by a constant under `__SANITIZE_*`, and keep the full run for the native build. A cross-compiled
    bench binary built with the macOS 26 SDK fails at load on macOS 15 (`from_chars` symbols in libc++.dylib): build
    with `-mmacosx-version-min` and leave the missing comparator out.
## Hashing, identifiers, containers

### random

[CHANGELOG](https://github.com/Kronuz/random/blob/main/CHANGELOG.md)

1. `std::mt19937_64` + `uniform_int_distribution` behind a non-inlinable function is a poor fit for a
   convenience helper: 2.5 KiB of state and a division per draw. A 4-word xoshiro256++ plus Lemire's
   multiply-shift (division only on the rare reject path) took `random_int(0, 999999)` 3.9 -> 2.4 ns and
   the full-range draw 2.76 -> 2.43 ns. What is left is mostly the out-of-line call and the TLS access: once the
   engine is cheap, the call boundary is the floor (the [hash survey](reviews/2026-10-30-survey-hash.md)'s 5-10x
   compared against an inlined engine).
2. A string helper that spends one engine draw and one distribution call per character wastes 58 of
   every 64 random bits. Cutting one draw into ten 6-bit fields (reject 62/63, so each symbol stays exactly 1/62),
   sizing the string once and advancing a pointer branch-free took `random_string` 8/32/256 chars from
   28.6/118/885 ns to 7.9/31.5/104 ns (3.6x/3.8x/8.5x).
3. A thread_local with a constant initializer and POD type needs no init guard; seed lazily behind a flag.
   Seed all of the state from the entropy source (256 bits, not one 32-bit value).
4. Moving a function body from the .cc into a header changes what the compiler inlines. The seeding code landed in
   `random_int` (80 to 100 instructions with g++, 87 to 125 with clang) and clang outlined the string generator
   behind a call. Keep the cold path `noinline`, make the hot templates always-inline behind compiler-guarded macros,
   and compare the instruction counts of the exported functions with the old build, not only a benchmark.
5. Check uniformity, not just ranges: chi-square on ints (awkward ranges), reals, and per-position string symbols,
   with a threshold ~10 sigma out because the generator is unseeded. A bias mutant (`v < 61`) is caught.
6. A statistical test on an unseeded generator cannot see what makes it correct. Five of the
   [hash audit](reviews/2026-10-31-audit-hash.md)'s 13 mutants passed the perf work's tests: no Lemire rejection loop,
   two wrong engine rotations, a 32-bit seed, a broken portable multiply. Put the code under deterministic tests
   instead: template the engine and the range reductions, drive them with scripted words, and check against oracles
   that share nothing with the implementation (the authors' reference vectors, a 16-bit-limb schoolbook product, and
   exact counts over a whole 16-bit word space: each result hit by exactly floor(2^16 / range) accepted words). Test the
   code that ships, not a copy, and keep a mutant runner (30 mutants here) so a test that stops pinning a property
   shows up. The audit caught it by mutating.
7. Code that only one platform's compiler takes needs a CI job that takes it. `__builtin_expect` broke MSVC (the
   audit found it by reading); adding an MSVC job then found a second bug nobody had seen: `_umul128` returns the low
   half and writes the high half through its pointer, and the swapped version compiled and returned out-of-range
   draws on MSVC only, because every other GitHub Actions target has `__int128`. The new tests failed on it at once.
8. A benchmark's "before" column must cost what the old library cost, and its "after" must not be the best batch.
   The frozen comparator compiled in the same translation unit was inlined (`random_int` 3.9 ns against 4.36 for the
   real out-of-line library), which understated the speedups, and the bench printed the fastest of seven batches, so the
   README quoted 104 ns for 256 characters and 2.4 ns for `random_int` where the median of nine batches is 107 and 2.50
   (the audit's own harness measured 117 to 121 and 2.52). Make the comparator `noinline`, print the median and the
   batch spread, and state the machine and the command next to the number.
9. On the Intel Core i9-9980HK two builds of the same source differ by up to 25% on a 4 to 5 ns call, and the sign
   flips between builds: `random_int` ran 4.2 ns in one binary and 5.2 ns in the other, for the old library in one build
   and for the new one in the next. Apple clang's x86 output for the function was instruction-for-instruction the
   same (GCC 16's differed in register choice), so it was the placement of the code. Before treating a x86
   regression on a tiny call as real, diff the assembly, time the sources in more than one build (a trimmed bench, an
   aligned build), and report the spread across builds. The rows that do work (strings) were within 5% throughout.

### cuuid

[CHANGELOG](https://github.com/Kronuz/cuuid/blob/main/CHANGELOG.md)

1. Building a `std::mt19937` to read two outputs costs ~870 ns, and almost all of it is the 624-word init
   recurrence (a serial multiply chain with no closed form), not the twist. Computing only the 399 words the
   first two outputs depend on gave 1.5x (900 -> 590 ns), not the 3x one would guess from "skip the twist": the
   serial chain is the floor.
2. A pure function with a small hot working set deserves a tiny thread-local direct-mapped cache: `serialise` of the
   same id went 911 -> 9.4 ns (97x) and `generate(compact)` + `serialise` of the result now pay the chain once.
3. A mutex guarding "last = max(time, last + 1)" is a CAS loop on an atomic with the same sequence. (It is not
   lock-free, though: see 4.)
4. Before calling a change lock-free, find every lock on the path, and before reverting one, time it on every
   architecture. `generate()` still took `UUIDGenerator::operator()`'s static mutex (and `newUUID()`'s on macOS)
   before the claim ran, so the CHANGELOG's "lock-free" was wrong, as the [hash audit](reviews/2026-10-31-audit-hash.md)
   said. The audit also found no measurable effect, on the Apple M4 Pro and on the shared Linux x86-64 VM under load
   (90.9 ns either way, a 30% spread); the fix round reverted to the mutex on that, then timed the Intel Core
   i9-9980HK: the mutex costs 8 to 10% (about 10 ns) per `generate()` at one to four threads, with the control row
   unchanged, and a revert would have regressed an x86 row by more than the 3% allowed. The CAS stays, described as
   what it is: it removes the claim's own mutex acquire.
5. When a rewrite must reproduce a library engine bit for bit, test against the real engine
   (seeds: edges, dense low range, every flipped bit, 300k random), and compare wire bytes with a frozen copy of the
   old expander through the whole condense/uncondense path.
6. The change touched a concurrency property and added no concurrent test: a claim that reuses the last time, and one
   that stores instead of compare-exchanging, passed every test. A test written from the audit's probe (8 threads x 4,000
   ids: distinct bytes and wires, claimed times unique and increasing per thread) fails each of them in 6 runs of 6 on the
   i9. A mutant that removes the step altogether survives: `operator()` already hands out unique, increasing times, so the
   step is redundant when the mint is a v1 UUID. That is redundancy, not a test gap.
7. A doc can describe the prototype and be read as describing the codec. "No XOR fold, a clean 1 ms sort granularity"
   was the prototype's layout, pasted into the page of the shipped v6, which shares v1's compaction: the byte order is
   the 1.64 ms window's, and inside it 33% to 97% of consecutive ids from one thread sort below their predecessor.
   Pre-existing, found by the audit's probe. Fixed in the docs, pinned by a test, and left as a design decision: a finer
   order needs the exact time in the id, which the compact wire cannot carry (it keeps the low 14 bits only XORed into
   the clock).

### sha256

[CHANGELOG](https://github.com/Kronuz/sha256/blob/main/CHANGELOG.md)

1. `result += c` per hex character costs more than the SHA-256 kernel on short inputs: the legacy
   `SHA256(16 B)` took 252 ns against 18 ns for the kernel. Sizing the string once and writing pairs through a
   pointer: 252 -> 60 ns (4.2x) at 16 B, 270 -> 75 (3.6x) at 64 B, 578 -> 393 (1.5x) at 1 KiB. MD5: 161 -> 115 (1.4x),
   217 -> 168 (1.3x), 1.0x at 1 KiB. The rest is the kernel plus the save/restore contract of `getHash()`.
2. Benchmark the API people call (the string-returning one), not only the kernel.

### md5

[CHANGELOG](https://github.com/Kronuz/md5/blob/main/CHANGELOG.md)

See also [sha256](#sha256), items 1 and 2.

### hashes

[docs/BENCHMARKS.md](https://github.com/Kronuz/hashes/blob/main/docs/BENCHMARKS.md)

1. One serial dependency chain caps a hash at latency per word. Serial designs (one running multiply, FNV,
   `wordwise`) cannot use the multiplier's throughput: a multiply-xorshift chain is ~6 cycles per 8 B (5 GB/s) no
   matter how simple the mix, and throughput comes from independent lanes (4-8), not from a lighter mix. Wide lanes
   give 6-10x on long inputs but change the output, so decide the lane structure before the hash value is frozen in
   tables or on the wire ([hash survey](reviews/2026-10-30-survey-hash.md),
   [second-wave survey](reviews/2026-10-30-survey-second-wave.md)).
2. "Fast on short keys" does not transfer to long ones, and vice versa. A hash tuned for 4-8 B keyword dispatch ties
   XXH3 there and loses 8x at 4 KB; document the length range or provide both
   ([second-wave survey](reviews/2026-10-30-survey-second-wave.md)).
3. Bench hygiene: a fixed-input pure function folds to nothing (the hash survey's xxh64, `wordwise` and FNV rows at
   32 B and below read 0.5 to 3 ns and were void); consume a changing input or an opaque value, and read the clock
   once per batch (an 18 ns clock read swallows a 1 ns operation) ([hash survey](reviews/2026-10-30-survey-hash.md)).

See also [bloom-filter](#bloom-filter), item 1.

### bloom-filter

[CHANGELOG](https://github.com/Kronuz/bloom-filter/blob/main/CHANGELOG.md)

1. A second, byte-wise hash (FNV-1a, a dependent multiply chain) beside a fast one makes the
   cost scale with key length: 64-byte keys 67 ns vs 22 ns once all probes derive from one
   xxh64 pass (3x); 16-byte keys 26.7 -> 17.4 ns (1.5x). Derive extra words from one good hash.
2. Changing which bits a key sets is an on-disk-compatibility decision even when the class
   exposes no serialization. Ship the faster layout as a new opt-in type; keep the default
   frozen and prove it with a frozen-copy differential test.
3. Early-exit probe loops mispredict on mixed data; with independent loads, OR-accumulate all
   k tests and branch once (miss path 26 -> 17 ns together with item 1). On x86 this lost; see items 4 and 5.
4. Introduced by item 3 above: "OR-accumulate all k tests and branch once" was measured on arm only. On the Intel
   Core i9-9980HK the miss path of `FastBloomFilter` was slower than the legacy early-exit loop (16-byte keys, 131072:
   45 vs 36 ns with clang, 48 vs 34 with gcc; boost::bloom 23 and 28) because twenty probes of arithmetic cost more than
   a mispredict when the first probe usually decides. The [containers audit](reviews/2026-10-31-audit-containers.md)
   caught it by timing the same bench source on the second architecture. A loop shape that is a win on one core is a
   hypothesis on the next; time the miss path and the hit path separately on every architecture before generalizing a
   lesson.
5. The cure is between the two shapes: test the probes in groups of four (independent loads, OR-accumulated), branch once per group. At
   the design load 46% of the bits are set, so an absent key leaves after its first group 95% of the time: the branch is almost always
   taken the same way and a miss reads 4 words, not 20. Miss at 16 bytes: arm 18.1 -> 8.0 ns, i9 clang 45 -> 21, gcc 48 -> 23 (now ahead
   of the legacy type and of boost::bloom); 64 bytes: 23 -> 12 (arm), 64 -> 32 (i9). Hits and adds are unchanged, and group sizes 2, 4 and 5 are
   within noise of each other, so the exact size is not the point.
6. A blocked (one cache line) filter is fastest but costs false positives at the same size
   (1.3e-3 vs ~0 at 32 bits/key, k=20): report it, do not make it the default.
7. A performance fix needs a test that fails when it is reverted, and a timer cannot be that test. A thread-local counter of the words
   `contains` reads (a macro the header compiles away) with an average bound of 8 (4.2 expected, 20 reverted) fails deterministically on
   every GitHub Actions runner; the answers are held equal to a frozen copy of the previous implementation so that nothing else moves.
8. A compiler extension (`unsigned __int128`) in a non-template inline function is compiled by every includer. It broke `-Wpedantic -Werror`
   consumers (GCC) and cannot compile on MSVC or 32-bit targets, and the GitHub Actions matrix never built either. `__extension__` on a typedef under
   `__SIZEOF_INT128__`, a standard-C++ fallback checked against an independent oracle, and a CTest that builds the whole suite with the
   fallback forced (so it runs everywhere, not only where it is the default) plus one that compiles the header with `-Wpedantic -Werror`.

### generation-cache

[CHANGELOG](https://github.com/Kronuz/generation-cache/blob/main/CHANGELOG.md)

1. A cache's read path does not need ordering: replacing `std::map` (a tree walk of string
   compares inside the critical section) with a small open-addressing table took string-key
   `get` from 446 to 116 ns (3.8x) at n=100000 single threaded.
2. The same change plus a shared lock for readers took 4 threads from 2141 to 294 ns/op
   (7x): the hold time shrank and readers stopped serializing. Both matter; the lock alone
   leaves the tree walk under it.
3. A hash-only fast path must keep a fallback for keys that only have `operator<`; detect
   `std::hash` + `==` with a trait and keep the old container for the rest.
4. A table that never erases single entries needs no tombstones: the specialized container
   is ~60 lines. Remaining gap to abseil (116 vs 99 ns) is the copy of a heap-allocated value
   out of the lock, common to all comparators. (Item 5 found the gap was the lock.)
5. Before changing a data structure to close a gap to a comparator, swap the comparator's lock for yours. The 116 vs 99 ns gap to
   `absl::flat_hash_map` behind a `std::shared_mutex` was the lock: behind the same lock this table matches abseil's (166 vs 181 ns), and a
   one-byte-tag layout was no faster (179-183).
6. Introduced by the perf work (item 2): the first benchmark was 100000 string keys, where cache misses hide the lock, and `std::shared_mutex` was
   adopted for the four-thread gain. On a 64-entry `int` cache a `get` hit went from 7.8 to 11.9 ns on arm64 and from 18.4 to 37.7 on
   x86_64 (libc++ takes two mutex round trips per shared lock), and construct + destroy from 12.2 to 80.9 ns and from 54 to 291 ns. The
   [containers audit](reviews/2026-10-31-audit-containers.md)'s small-n rows found it. Time the shape where the lock is the whole operation,
   not only the one where it is invisible.
7. A reader-writer lock for short critical sections can be one atomic word and a mutex used only to wait: readers add and subtract,
   a writer takes the mutex, sets a flag and waits for the readers inside, a reader that meets the flag takes its add back and
   adds again under the mutex (no writer can set the flag without it). Small cache `get` hit: 3.6 ns arm64, 10.0 ns x86_64, faster than the
   original `std::mutex` (7.8, 18.4); four threads at 100000 keys on arm64: 84 ns against 333 with `std::shared_mutex`. A waiting writer holds new
   readers back on every platform, where `std::shared_mutex`'s fairness is the platform's (glibc prefers readers). The mutants that matter are the two
   that remove one half of the handshake (a reader that ignores the flag, a writer that does not wait); each fails `test/lock.cc` on GitHub Actions.
8. The first insert into a table that allocated 16 slots (384 B for `<int,int>`) cost more than one `std::map` node: construct, insert once,
   destroy was 188 ns against `std::map`'s 134 on x86_64 (37.5 vs 36.0 on arm64). The lock and the seed were not the cause; a decomposition
   (lock only, seed only, allocation only) showed the allocation: macOS x86_64 `malloc` costs about 82 ns above 256 B and about 36 below.
   Starting at 4 slots (`initial_bits = 2`, then doubling) put the row level with `std::map` on x86_64 (134 ns) and 22% under it on arm64
   (28 ns), with no loss on the other rows. Decompose a regression into its parts before guessing; the guess (lazy allocation, lock setup)
   was wrong, and the size of the first block was right. `test/first_insert.cc` asserts `capacity() <= 4` after one insert and fails
   against `initial_bits = 4` on all 8 GitHub Actions jobs.
9. A per-object `std::random_device` draw costs 70 ns (arm64) to 230 ns (x86_64) and can throw. Draw once per process, fold in the
   clock, the thread id and an address so a failing source costs quality and not an exception, and vary per table by address. The
   test replaces the entropy source with one that throws.
10. The table's `grow()` swapped in the new bit width and an empty table first, then moved the old slots in one at a time.
    When the move of a `Key` or `Value` threw (or the slot's implicit move-assign did, after copying `h` but before the
    `optional`), the new table was half full, the rest of the entries died with the old vector, and a slot could hold a
    hash with an empty `optional` that the next `get` dereferenced. The earlier fix (CR1 in
    [review D](reviews/2026-10-31-review-d-containers.md)) had made the single-slot insert exception safe and the README
    claimed the strong guarantee for `try_insert`, but the claim was checked on one path (a throwing `Key` copy at insert)
    and never on the path that runs unrelated work inside the same call. Build the whole replacement first, publish it
    with a non-throwing swap, and move only if every member's move is nothrow (else copy, decided per pair so a failed
    copy never follows a moved-from key), as `std::vector` does.
11. The oracle was a `std::map` model outside the cache and a sweep, not a single probe: arm a throwing copy/move (and,
    in unsanitized builds, `operator new`) to fail on the Nth operation, sweep N across every operation of an insert
    sequence that crosses three rehashes, and after each failure compare size and every key and value with the model, then
    retry the call and require it to succeed. One fixed N misses the failures that matter; the sweep found the old code
    wrong at N=0 (30 593 failed checks on macOS; an abort in libstdc++'s optional assertion on Linux).
12. Mutation checks name the test: always-move in `grow()` fails the injection sweeps (31 701 failed checks) and the
    "moves always throw" test; always-copy fails `nothrow_move_never_copies_on_rehash` (17 copies, want 1); the old
    `m_[key] = ...` in the `std::map` adapter fails the "ordered" sweep. Reading the sibling container for the same claim
    found a second bug: `m_[key]` inserts a default-constructed `Value` first, so a throwing assignment left a phantom
    entry. `insert_or_assign` builds the node from the value.
13. A seed does not defend against colliding `std::hash` values: keys with equal hashes collide in every cache whatever the seed. The
    CHANGELOG's "cannot be crafted offline to collide" overstated it; say what the mechanism does.
14. Replacing `operator new` in a test conflicts with the static ASan/TSan runtimes (multiple definition at link time),
    and under g++'s ASan on the shared Linux x86-64 VM even a trivial program with a malloc-based `operator new` dies in
    LSan. Gate the `bad_alloc` runs to unsanitized builds and keep the throwing-element sweeps (which cover the rehash) in
    the sanitizer jobs, with a live-object counter standing in for LSan.
15. A test that asserts a rate asserts the machine. The lock test's starvation cases ("a writer finished 1000 turns among four busy readers
    in N seconds") flaked on the FreeBSD VM of the GitHub Actions matrix, where one lock turn takes milliseconds. Check progress (100 turns,
    60 s ceiling), not speed.

### flat-map

[CHANGELOG](https://github.com/Kronuz/flat-map/blob/main/CHANGELOG.md)

1. `std::pair<K,V>` is never trivially copyable, so `vector::insert` shifts it element by
   element even for `<u64,u64>`; one `memmove` when both halves are trivially copyable took
   mid-vector insert from 290 to 167 ns at n=4096 and 5237 to 3605 ns at n=65536 (to boost parity).
2. A branchless lower bound (compare feeds a cmov, restricted to integral keys with the default
   ordering) made find 1.5-2x faster at every size (6.5 -> 3.3 ns at 256, 35 -> 24 ns at 65536) and
   beats boost's; keep `std::lower_bound` for other keys and custom comparators.
3. "Branchless" in the source is not branchless in the binary: Apple clang on x86 (X86 cmov
   conversion) turned the loop-carried `?:` of the lower bound back into a branch, and the shipped
   search ran like `std::lower_bound` on random queries (Intel Core i9-9980HK `<u64,u64>` n=4096: 55 vs 54 ns).
   Marking the compare `__builtin_unpredictable` (clang) or `__builtin_expect_with_probability(c, 1, 0.5)`
   (gcc) keeps the cmov: 55 -> 14 ns at n=4096, 114 -> 62 ns at 65536, with no source change that a
   test can see. Look at the asm (`cmov` in the loop, no `j` on the compare) and time a random
   stream on each ISA before calling a loop branchless; gcc kept the cmov on its own.
4. On arm64 the shape of the same loop is worth 20%: `const P* next = base + half; base =
   next[-1].first < k ? next : base;` is one `csel` on the 7-cycle chain; the index form, or loading
   `base[half-1]` and selecting `base + half`, costs a `csel` and an `add` (8-9 cycles). Returning
   pointers from the kernels also beat an index round trip. `noinline` on the prefetch kernel made
   `find` 7-17% slower (the caller reloaded and spilled around the call). Measure each form; do not
   reason from the C++.
5. Prefetching both candidates of the next step loses 7-12% below about 512 KiB and wins 10-35%
   above (arm64 needs about 2 MB, x86 about 0.5-1 MB): a size threshold, not a flag. The 1M-entry
   random `find` went 255 -> 109 ns on the i9 and 92 -> 83 ns on the Apple M1 Pro.
6. A fast path that helps large inputs can cost small ones by its fixed price: `memmove` on every
   insert is a libc call, which at 16 to 64 entries is slower than moving the entries (`<u32,u32>`
   n=16 on the Apple M4 Pro: 11.4 -> 16.6 ns; the crossover is about 64 entries on arm, 16-32 on x86
   libc++, 64 on x86 libstdc++). One constant (32 entries and 256 bytes) covers all three. Putting
   both search kernels in the insert path added about 2 ns by itself at n=16 (code size and
   inlining), so the insert path uses the plain kernel and an index. Time the smallest row of the
   table every time a larger one is optimized.
7. Differential tests for both: random op streams vs `std::map` across signed, unsigned, 8-bit
   and string keys, a custom comparator, and extreme-value probes.
8. Whether a byte shift of `std::pair` is valid is a rule, not a hunch: the pair is an
   implicit-lifetime type when both halves are trivially copyable and the pair is trivially
   copy/move-constructible and destructible, and `memmove` then creates the objects ([cstring.syn],
   C++20). The gate encodes that rule, with `volatile` excluded. FreeBSD's libc++ makes
   `std::pair<unsigned, unsigned>` non-trivially copy-constructible, which failed every positive
   `static_assert` on GitHub Actions: tests of a gate must name the standard library they expect each answer
   from, and the negative cases (self-pointing and assignment-counting entries) must hold everywhere.
9. Killing mutants showed which of the gate's clauses are checkable: forcing the shift on, dropping
   `volatile` and a threshold of 0 die in `flat_map_strategy`; dropping the pair-constructor clause
   survives on libstdc++ and Apple libc++, where it is implied by the others, and matters only on a
   libc++ like FreeBSD's. Say which clauses a test covers on which platform instead of claiming all.
10. A benchmark that replays the same few hundred keys lets the branch predictor memorize
    `std::lower_bound`: `<i8,u64>` n=100 took 4.7 ns with it and 6.4 ns branchless, but 26 vs 6.8 ns
    on a random stream. A single replayed column was hiding a 4x win and showing a 28% loss. Time
    both, say which one a number comes from, and decide the trade on the stream the callers run.

### btree

[CHANGELOG](https://github.com/Kronuz/btree/blob/master/CHANGELOG.md), [docs/perf/move-relocation.md](https://github.com/Kronuz/btree/blob/master/docs/perf/move-relocation.md)

1. `std::pair<const K, V>` move-constructs by COPYING the const key, so every node shift, split and
   rebalance of a `map<std::string, T>` mallocs and frees a string per slot (107,000 key copies for
   20,000 random inserts+erases; 7 after). Relocate the key through a mutable view (the library
   already const_casts in `swap`) when the key and mapped type are nothrow-movable: string-key random
   insert 495 -> 271 ns at n=200k, 341 -> 174 ns at 20k (parity with absl::btree, which was 1.8x faster).
   **Superseded:** the `const_cast` is undefined behavior and never landed; the live-union slot of item 3 below
   does the same moves legally.
2. An exception-safety scheme that copies first (keep a scratch bank of copied keys so a throwing copy
   leaves the node intact) is pure cost when moves cannot throw: gate it on the move guarantee, not
   on the copy one (`std::string` is nothrow-movable but not nothrow-copyable, so it always took the
   slow scratch path).
3. **Const-key pairs need the union, not a cast.** The container must hand out `std::pair<const K, V>&`, and
   relocation must move the key. Both hold only if the live object is a mutable `std::pair<K, V>` that the
   container reads through a `std::pair<const K, V>` view: a union `slot_type { value; mutable_value; }` whose
   lifetime begins with placement new, whose `mutable_value` member is constructed in place, and whose layout
   equivalence is static-asserted (size, alignment, member offsets). Relocate, swap and destroy through
   `mutable_value`; hand out `value`. This is Abseil's `map_slot_type`, and it costs nothing at run time: Apple
   clang emits identical code for `mutation_bench` with and without the live union.
4. **Why `const_cast` is not a shortcut.** Moving from a key that was created const, through `const_cast`, modifies
   a const object: undefined behavior ([dcl.type.cv]). Tests, ASan and UBSan all pass with it, which is the
   danger: they cannot show the absence of UB, and a compiler may assume a const subobject never changes (cache a
   key across a call, fold it under LTO). Our own first fix of the same copies (a non-default `main` branch,
   `0d40c97`) took that shortcut while a correct union-based fix sat on another branch. Before fixing anything,
   read the default branch and every open branch: the right fix may exist already.
5. **Correct was also faster.** Moving keys instead of copying them took string-key `emplace` at n=200k from 1658
   to 675 ns (Apple clang, Intel Core i9-9980HK) and from 1288 to 645 ns (GCC 16), against `absl::btree_map` at 615;
   `mutation_bench` with 200-byte keys dropped 32% (Clang) and 27% (GCC); the `u64` rows stayed within noise. The
   UB shortcut was not faster in any way that matters: 1-4% on string `emplace`, inside A/A spreads of 2-6%.
6. **How the bug arose.** Google's 2013 B-tree stored map slots as `std::pair<const K, V>` and relocated them by
   "moving" the pair during splits, rebalances, merges, erases and root swaps. Moving a pair with a const member
   copies that member, so with heap keys (`std::string` past the small-string buffer) every reshape allocated, and
   the code assumed a relocation could not fail. An allocation refused halfway through a split left a half-built
   node: entries lost or misordered, leaks, a double free on a later erase. Erasing 65,536 entries with 200-byte
   keys made 72,692 heap calls (0 after); inserting them made 420,230 (147,659 after). It survived six years
   because nothing refused allocations with long keys until Detent's sweep did.
7. **The verification found a second, older bug.** Values not built before the split (pairs larger than the
   256-byte target node, or with a throwing move) are constructed after it, and the split biases its values away
   from the insertion point: inserting at the front of a full leaf leaves that leaf empty until the value
   arrives. A refused allocation there left an empty leaf linked in the tree (iteration read destroyed slots)
   and `size()` one too high, on master too. A refusal sweep with a type from each side of every trait threshold
   (`static_assert` that the test types really take the late-construction path) found it; one fixed probe would
   not have. The repair merges the short leaf as erase does, and costs nothing on success.
8. Tests that pin the old scheme (a copy-failure budget, an allocation-refused fallback) must be
   rewritten to pin the new guarantee (zero copies, no allocation), not deleted.
9. **An "unexplained compiler abort" was the test, not the library.** GCC 16 assumes replaceable `operator
   new`/`delete` touch no global state (`-fassume-sane-operators-new-delete`, default on), and libstdc++ allocates
   through `__builtin_operator_new`. Tests that count allocations in globals read stale counts at `-O2` with
   C++20 and aborted, on the old header too. Make such counters `volatile`, and assert the test is not vacuous
   (at least one refusal happened), because the same assumption can also delete a budget store and make the test
   pass while testing nothing.
10. **Old toolchains lie in their own ways.** Clang 12 links ASan's runtime statically, whose `operator delete`
    clashes with a test's replacement at link time (use `-shared-libsan`); at `-O2` it also lost the count of
    `make_unique` temporaries passed to `erase` (balanced with `-fno-builtin`). A compile that failed left the
    previous binary in place, and that stale binary "passed": delete the output before each build.
11. Profile with the sampling profiler before reading code: the time sat in `emplace_unique_key_args`
    plus malloc/free (`_xzm_free` 12%), which pointed at hidden allocation rather than node layout.

### metrics

[CHANGELOG](https://github.com/Kronuz/metrics/blob/main/CHANGELOG.md)

1. A CAS loop used only to saturate is the cost, not the saturation: under contention the retries
   dominate (Apple M4 Pro: 4 threads 64-68 ns, 8 threads 322-340 ns per add; Intel Core i9-9980HK: 223-268 and
   591-782). A `fetch_add` fast path is 2.0x faster on arm64 and 2.6-4.2x on x86_64 at 4-8 threads, and 38%
   slower at 2 threads on arm64 (5.3 to 7.4 ns): claim the range, not "unchanged".
2. For a 14-entry sorted table the bucket index is just the count of entries below the value: a
   branchless counting loop replaces `std::lower_bound`; verify against lower_bound at every edge+-2.
3. Shared-cache-line false sharing in the histogram (115 ns/obs at 4 threads) is a layout change
   (striping), deliberately not done here: it changes `sizeof` and the ABI.
4. A `fetch_add` cannot saturate a word that any other path can lift to the maximum. It can sit
   preempted between its guard and its add for any length of time, so no guard on a loaded value
   is sound. The perf work's first version (`fetch_add`, then store the maximum) showed readers
   the wrap; its fix (guard on a load below 2^63, "exact") wrapped for good when a large add
   landed in between: 15618 of 20000 trials ended below the maximum on arm64 (CA2 in the
   [containers audit](reviews/2026-10-31-audit-containers.md)). The "one add in flight per thread" bound was
   argued for the small adds and forgotten for the large add on the same word, and the differential test never
   mixed them concurrently. The audit's probe (small adds racing one `add(UINT64_MAX)`) found it in seconds.
5. Keep the speedup where it can be proved: split the value over two words, small adds into one
   that only they write (so the in-flight bound covers every writer), everything else
   CAS-clamped in the other, and return the saturating sum. `ContendedCounter` is opt-in (16
   bytes); `AtomicCounter` is the CAS loop again, byte-identical machine code to the start.
6. Prove a lock-free claim by exhausting a small instance of the real code: template the counter
   on the word and the atomic, run it at 8 bits against a model atomic where every atomic call is
   a step, and explore every interleaving. It found the CA2 wrap in four steps and showed the
   in-flight bound is tight (8 adds hold, 9 wrap). Keep the broken designs (the old fast path,
   the first fetch_add version, no clamp, no `small_` check) in the test and require the checker
   to reject each; a checker that never rejected a wrong design proves nothing.

### queue

[CHANGELOG](https://github.com/Kronuz/queue/blob/main/CHANGELOG.md)

1. An unconditional `notify_one` per operation was the whole 2-3x gap to a 30-line
   mutex+deque: notify only when a waiter count (kept under the same mutex) is non-zero.
   An unbounded queue then never touches its push-side condvar. 12.8 -> 44.8 Mitems/s 1x1,
   9.4 -> 30.6 at 8x8; now at or above the naive baseline and 4-6x moodycamel Blocking.
2. A 1 s `wait_for` polling loop is a lost-wake-up workaround that also reads the clock on
   every call. Fix the cause (take the mutex around the flag store before `notify_all`,
   so a waiter between predicate and block cannot miss it) and use plain `wait(lk, pred)`.
3. State written only under a mutex does not need an atomic RMW: relaxed load + store keeps
   the lock-free reader and drops a locked instruction per item.
4. ...but the store must be release, not the default seq_cst: that is an `xchg` on x86, a
   full barrier inside the critical section (a `mov` with release; arm64 compiles both to
   `stlr`). Worth about 10% at 2x2 to 8x8 on x86.
5. The real x86 gap (Apple clang, Intel Core i9-9980HK: 0.92, 0.71, 0.57, 0.55 of a mutex+deque
   baseline at 1x1 to 8x8) was the call boundary, not the algorithm. `push_back` and
   `pop_front` were out-of-line templates that called an out-of-line `_push_wait` with a
   `unique_lock&`, so the lock lived in memory on every operation. Reading the code found
   nothing; two bisections found it in four runs: grow the baseline one feature at a time
   (waiter-gated notify +30%, atomic count -12%, flags in the predicate -20%, state behind
   a shared_ptr 0, all together parity), then swap one path of the real class for the
   simplest code (simple push + real pop: parity; real push + simple pop: 0.5x). Deciding
   the common case in an inline predicate and force-inlining the four hot operations gave
   1.16 to 1.25x (Apple clang), 1.25 to 1.47x (gcc 16) and, on arm64, 1.24 to 1.96x
   (was 1.05 to 1.65x).
6. Cache-line layout was the wrong theory: aligning the mutex, counters and flags, and
   moving the read-mostly fields off the deque's line, changed nothing measurable. Test a
   structural guess with a variant before building the explanation.
7. Removing the 1 s re-check (item 2) turned every missing notify into a permanent hang,
   not only the shutdown race it was removed for (introduced; CA1 in the
   [containers audit](reviews/2026-10-31-audit-containers.md)). The poll had been
   covering seven more paths: a consumer condvar shared by two `Queue`s on one state (a push
   woke the other `Queue`'s consumer, which slept again), `clear()` waking one producer (none
   when its own `Queue` was stopping), `QueueSet::erase` waking nobody, a pop at or above
   `threshold` waking nobody, a soft-limit refusal swallowing the only wake-up, an exception
   after a wake-up doing the same, and the destructor of a finished shared `Queue`.
   [Review D](reviews/2026-10-31-review-d-containers.md) passed it because its probes covered shutdown and
   one-queue push/pop. Before dropping a poll, list every state change that can make each waiter's predicate true
   and show which notify reaches a thread that acts on it; test each with threads confirmed parked (the
   waiter count under the mutex), one change, and a deadline plus watchdog, so the test fails
   instead of hanging. Nine of the 25 cases fail on the old header; a tenth did not compile.
8. `notify_one` is enough only when every waiter on that condition variable waits for the
   same thing and every woken waiter takes it or hands the wake-up on. A per-`Queue`
   predicate on a shared condvar broke the first; a refusal at the soft limit and a throw
   broke the second. Xapiand's failure-path `notify_all` ("FIXME: shouldn't be needed") was
   that hand-on; removing it was safe only while the poll ran.
9. A wake-up threshold cannot coexist with an untimed predicate wait: it only delays a
   wake-up the predicate already allows, and without a timer the delay is forever.
   `threshold` now has no effect; each freed slot wakes one producer, which is no herd.
10. A correctness fix can undo a perf fix without touching the fast path's logic. The
    wake-up hand-on first grew `_push_back_impl` until Apple clang stopped inlining it (the
    `unique_lock` back in memory, item 5). Force-inlined, it still lost 16% and 19% at 4x4
    and 8x8 on the i9 with the waits moved into separate out-of-line functions, wherever the
    condition variable lived (per `Queue`, on the state, cache-aligned). Back in the inline
    commit's shape (the wait inlined into the `_impl` body, the hand-on a guard armed only
    after a wait) it is 0.98-1.03x of that commit, inside the A/A. Disassembling
    `QueueAdapter::push` found the out-of-line call in a minute after hours of layout
    variants: read the hot function's code before building a layout theory.
11. Move assignment had been dropping the target's items without updating the shared count
    since the extraction: no test ever moved a `Queue`. Its oracle is the destructor (give the
    slots back, wake that state's producers). It also unlocked a mutex it had just destroyed
    and passed one mutex to `std::lock` twice; glibc ran both quietly and ASan and TSan stayed
    silent, so only reading the code found them. The count bug fails three tests on the old
    header.
12. Mutants that survive a deterministic liveness test usually mean the test's own
    setup delivered the wake-up: `end()` then `clear()` back to back let the broadcast from
    `end()` carry the parked producer through, so the clear-on-ended and destructor mutants
    lived until the queue was stopped before the producer parked.
13. A contended, oversubscribed throughput bench is bimodal and order dependent. Three
    consecutive best-of-3 runs of one binary gave Queue/baseline at 8x8 of 0.53, 0.48 and
    2.36, so a "0.64x on x86" verdict was noise on the shared Linux x86-64 VM under load. Interleave the
    candidates in rotated order, add an A/A column (the baseline twice), and report the
    median of per-round ratios with its quartiles.
14. Shared runners are not timing hosts: GitHub Actions' macOS runners (3-4 vCPUs) gave A/A spreads of
    10-27% at 8x8 and once showed a 40% "regression" that the i9 did not. They are fine for
    finding which binary to time; the number to quote comes from a quiet host.
## Concurrency, time, and the operating system

### datetime

[CHANGELOG](https://github.com/Kronuz/datetime/blob/main/CHANGELOG.md)

1. A general-purpose `strto*` wrapper (errno save, buffer copy, whitespace/sign/overflow
   handling) on a fixed-width 2-digit field is most of a fixed-format parser's cost. Read
   plain digits directly and keep the general grammar only as the slow path for odd bytes
   (it must stay exact: here `"+5"` and `" 5"` were accepted fields). ISO parse 41-230 ns
   -> 8-26 ns (5-9x).
2. An offset applied by formatting it as a date-math string and re-parsing it paid two
   allocations, two parses and two calendar round trips for one integer add. One sum of
   seconds (plus a same-day shortcut that only touches hour/min/sec) is 9x faster; keep the
   old intermediate-state effects (a throw after step one) observable only where they
   actually were.
3. `std::regex` as the fallback made the slow path a ~1.3 us cliff (80x slower than a
   scanner, slower than `strptime`). A small regular grammar whose optional parts each start
   with a distinct character needs no backtracking: a greedy scan picks the same captures.
   1320 ns -> 17 ns; date math via `regex_iterator` 760 ns -> 50 ns.
4. `std::format` per field plus string post-editing is ~9x slower than writing digits into a
   stack buffer. To match `{:.6f}` exactly, round the exact binary value in 128-bit integer
   arithmetic (ties to even); `llround(f * 1e6)` differs on exact ties such as k/128.
5. `gmtime_r` is a tz-aware libc call; for UTC use integer civil-from-days with floor
   division (35 ns -> 7 ns, 5x) and no hidden global state.
6. Exported `extern const std::regex` objects freeze an implementation detail into the ABI;
   they are kept but unused, so the library still pays their static-init cost.
7. Two engines for one calendar: `toordinal`, `timegm` and `timestamp(tm_t)` still went through a cumulative-days table and a
   hand-written ordinal, next to the days-from-civil core the parser had been moved to. One unsigned days-from-civil for
   years >= 1, after the same validation in the same order with the same messages (year, day below 1, month, day above the
   month length), removed the table and made them 1.6-1.8x faster (toordinal 3.1 -> 1.7 ns, `timegm` 4.7 -> 3.0 ns,
   `timestamp` 4.4 -> 2.9 ns on an Apple M4 Pro; 5.7 -> 3.4, 8.9 -> 5.1, 11.2 -> 6.9 ns on an Intel Core i9-9980HK). Keep
   the exception order a test: mutants that move the day threshold, drop the day check, offset the epoch by a day or loosen
   the year and month range each die on a named error, because the differential test feeds random invalid fields to the
   frozen original.
8. Two copies of one scanner (fill vs validate overload) had silently diverged on
   negative fields and fraction errors. One template with a `Fill` flag keeps them from
   drifting; a frozen copy of the old code plus a differential test (random, mutated and
   every-byte-at-every-position inputs, mutation-checked) is what makes such a rewrite safe.
9. (correctness fix) Five "preserved quirks" were fixed once the owner authorized it. How they arose:
   the original had two hand-copied scanners (fill vs validate) that diverged (signed vs
   unsigned compare, fraction parsed in one only), a code path (loose `Z`) that handed an
   empty string to a numeric parser, and date math done in `int` where `+2147483647d` or
   `7 * num` overflows (UB). The differential test had skipped the overflow inputs, so the
   UB stayed invisible. How verification caught/pins them: the fix lives in one scanner
   template, and the test compares BOTH overloads to a reference verdict written from the
   grammar (itself cross-checked against the old code everywhere they agree: 0 mismatches
   in 13.8M checks, so the oracle is not just a copy of the fix); each changed input class
   is asserted old != new and new == oracle, with a counter proving the class was hit. The
   date math is checked against Hinnant days-from-civil in 128-bit (52M checks, UBSan
   clean) plus an exhaustive 1..9999 brute-force day counter. Mutants (accept negatives,
   fraction `nd == 0`, restore the `Z` throw, drop the year bound, truncate `7 * n` to
   int) each fail a named test. The oracle test also exposed a sixth bug, left for the
   owner: `+12M` from December throws "Month must be in 1..12" (normalizeMonths turned a
   multiple of 12 into month 0: `mon %= 12` maps 12k to 0 and the else branch never
   runs; the carry needs `(mon-1)/12` and `(mon-1)%12+1`). Fixed in a follow-up with
   an exhaustive months test (all start months, N in -240..240, edge days) against the
   month model; the old tests missed it because random bases rarely land on a multiple
   of 12. The same follow-up made a loose-format offset set `is_utc` like the ISO path.
   The first push was red on one Linux job of the GitHub Actions runners only: the differential test's odd-base
   generator produced a base month 24, which throws the same "Year is out of range" in
   both versions but leaves month 0 (old) or month 12 (new) in the `tm_t`. A changed class
   needs its own oracle for the fields left behind by a throw: the old code on the base
   with the month already normalized.
10. (correctness fix, fix round) `timestamp(tm_t)` and `to_tm_t(double)` handled a fraction before 1970 in sign-magnitude:
   the fraction was subtracted from a negative whole-second count (23:59:58.9, 23:59:59.0 and 23:59:59.1 on 1969-12-31 gave
   -2.9, -1.0 and -1.1, so the instants came out of order), and `static_cast<time_t>(-2.9)` truncates toward zero and dropped
   the fraction. The fraction of an instant is the distance above the floor second on both sides of the epoch; `floor`, then
   add. It arose because every existing test started at 1970 (and random dates were mostly after it). The oracle takes
   fractions of an eighth, exactly representable, so double equality is exact and 128-bit integer days-from-civil gives the
   expected value; 59,161 of 300,000 random valid dates differed by exactly twice the fraction. The three instants in
   a row (ordered, one second apart) and `to_tm_t(-2.9) == 23:59:57.1` are the cheap named checks. Reverting the sign
   rule, or the truncation, fails them.
11. (correctness fix) `normalizeMonths(int&, int&)` looped once per twelve months for a month below 1 (about 180 million
   iterations for `INT_MIN`) and added `(mon - 1) / 12` to an int year (overflow near `INT_MAX`). Floor division in 64-bit
   arithmetic is O(1) and makes the range check one comparison; on a year outside int it throws and leaves both arguments
   unchanged. The test compares against a 128-bit model over every combination of extreme values and 100,000 random pairs,
   and bounds the time of the worst call, so the loop dies as a timeout instead of a wrong answer.
12. Function arguments are evaluated in an unspecified order: `f(draw(), draw())` drew left to right with clang and right to
   left with gcc on x86-64, so the same seed generated different inputs per compiler (digests
   300aac9e19bc9afe against ee72110919bac91f), and a failure found by one GitHub Actions job could not be reproduced with the
   other. One draw per statement fixes it; a digest of the generated inputs, recorded in the test and compared for the default
   run, keeps the fix honest and fails loudly if anyone writes the nested form again. A seed alone does not make a random test
   reproducible across compilers.
13. A limit enforced by a callee's buffer is not a limit. "1 to 62 fraction digits" held for `Iso8601Parser(str, tm)` only
   because `strict_stod` failed on a 64-byte buffer, while the validating overload counted digits. When strict-stox started
   to accept longer input, the two overloads disagreed and a pin-bump run on GitHub Actions runners went red on the
   differential test. State the limit where the parse is (explicit in `parse_fsec`, outside the hot path) and test its
   boundary (62 and 63 digits) in both overloads.
14. A one-line change on a cold path moved two unrelated rows of a 20-100 ns parse benchmark by 5-12%, in a different row for
   each way of writing it (the check inside `parse_fsec`, a separate out-of-line function, the check at the callers): the
   cost followed the code layout of the big scanner functions, and the frozen original in the same binary stayed flat. Time
   every variant interleaved with the baseline and the frozen copy on two machines before believing a regression or a fix
   of a few percent, and say in the table which rows moved on paths the change does not touch.

### scheduler

[CHANGELOG](https://github.com/Kronuz/scheduler/blob/main/CHANGELOG.md), [docs/perf/lazy-rearm.md](https://github.com/Kronuz/scheduler/blob/main/docs/perf/lazy-rearm.md)

1. **The loss fix cost a third of one producer's `add()` throughput, and only an audit's untargeted row showed it
   ([systems audit](reviews/2026-10-31-audit-systems.md) S2).** The new look at the wheel under the mutex ran on every pass
   with `sleeping` set, including passes that had already found a task due and would never wait, so a producer saw a
   "sleeping" worker with a past target and queued on the mutex to signal it: 401-411 ns per add became 503-526 ns (Apple
   M4 Pro). The handshake only matters when the worker may wait; a pass with work due skips it (390-424 ns). Benchmark the
   rows a fix does not target, and pin the property ("a pass with a task due never takes the sleep path") with a seam test
   that counts it.
2. **Making the consumer faster made four producers slower (+23%).** With stash's linear leaf walk the worker loops
   much faster, and two of its per-pass writes hit lines every producer touches on each call: a second exchange of
   `posted` before the walk, and `ending`, decremented and set back to -1 on every pass with no `finish()` pending
   (which also lost a `finish()` landing between the two). Removing both put the row back inside the old spread
   (462-595 against 432-615 ns). The old stash's "better" producer number came from a worker crippled by quadratic
   filing: on the Intel Core i9-9980HK that row never finished. Audit what the consumer writes per iteration, not only
   what it does.
3. A task fired up to 30 s late (counted as lost by a soak) when `add()` landed between the worker's `peep` and its
   sleep. The "Dekker pair" reasoning in [review H](reviews/2026-10-31-review-h-systems.md) was right for the new
   skip-signal logic but missed that the published wakeup can be *stale*: `add()` lowers it only if it is later than the
   task, so a stale-low value makes `add()` do nothing, and the worker not yet `sleeping` meant no signal either. A
   lock-free handshake needs the waiter to re-check the shared state *after* it announces it is asleep, not only before;
   here that is one more `peep` under the mutex, with seq_cst fences on both sides because the wheel's own atomics are
   acquire/release.
4. **A fence placed after the loads it was meant to order ([systems audit](reviews/2026-10-31-audit-systems.md) S1).**
   `add()` read the published wakeup time, then fenced, then read `sleeping`, and decided from the first read; with a
   release-only insert the C++ model allows that read to be stale. No run on any machine shows it, so a runtime test
   cannot fail on the revert. Read the order of operations out of the header and run it through a small store-buffer
   model in every interleaving (`scheduler_handshake_model`): the old order loses a task in 88 of 7 746 executions, the
   new one in none, and moving the fence back fails the test.
5. The burst test that showed it ("once per two million adds") was deleted rather than explained. The deterministic
   reproduction needed only a test seam that parks the worker between `peep` and the publish (`SCHEDULER_TEST_HOOK`,
   a no-op macro); it fails 3 of 3 before the fix. Park at the exact state the race needs (the hook is handed
   "published time equals the worker's local copy", otherwise the first parked pass was a benign one and the test passed
   on the broken code). Then keep the stress as a soak: 7 x 20 M adds lost 2 623 tasks before the fix, 0 of 140 M
   after, and a random-burst soak with 120 M adds stayed at 0 on both (a soak alone would have called the old code
   fine: the loss rate depends on the burst shape, so state the shape).
6. **A test made to pass instead of fixed ([producer hand-off review](reviews/2026-10-31-logger-producer-handoff.md),
   LPH-R10).** `producers` timed out under TSan because a backlog of overdue posted tasks is filed into one wheel leaf,
   whose chain every insert walked from its head: quadratic. Spreading the test's due times over a second hid it on the
   machine it was written on and still failed 3 of 5 on the loaded shared Linux x86-64 VM. The cause was in stash (fixed
   there, see [stash](#stash), item 1); the test is back to tasks due within 2 ms and passes 10 of 10 in 4.1-4.8 s.
7. TSan with two producers reports races inside stash's `put` on the old and the new scheduler alike; one producer is
   clean. Gate CI on the clean configuration and file the stash reports separately. See also [stash](#stash), item 2.

### stash

[CHANGELOG](https://github.com/Kronuz/stash/blob/main/CHANGELOG.md), [docs/perf/window-epoch.md](https://github.com/Kronuz/stash/blob/main/docs/perf/window-epoch.md)

1. **An append-only leaf whose inserts walk its chain from the head is quadratic in the values that share a slot.** Every
   value due in one finest slot, and every overdue key (filed at the floor), shares one leaf of 10-slot chunks, so 4 000
   inserts stepped over 1 998 000 nodes. Keep the furthest node any claim has resolved as a forward-only hint, with each
   node carrying its index (set before publication), and resume there: 1 000 steps. Through the scheduler, one producer's
   `add()` of tasks due now went from 390-424 to 224-252 ns (Apple M4 Pro) and a TSan run that files 200 000 overdue tasks
   from 5.6-31 s (timing out one run in three) to 4.4 s. Count the steps with a hook rather than timing them, so the
   regression test is exact.
2. **Read every TSan report against the TSan version ([systems audit](reviews/2026-10-31-audit-systems.md) L2).** Ten
   reports with two or more producers all paired an access with the constructor of a node the accessing thread had
   reached through a compare-exchange it lost. A failed CAS with `acquire` failure order is an acquire load in C++, but
   LLVM 12's runtime ignores the failure order (`(void)fmo`; LLVM 13 applies it). The same stress with `acq_rel` on
   success, which changes nothing for a failed CAS, gave 0 reports in 12 minutes against 13. Prove a suspected false
   positive with a variant that differs only in what the tool models.

### threadpool

[CHANGELOG](https://github.com/Kronuz/threadpool/blob/main/CHANGELOG.md)

Trivial task, 4 producers x 4 workers, Apple M4 Pro: old pool 127 ns/task, mutex + condvar pool 73, `asio::thread_pool` 110,
now 34 (Intel Core i9-9980HK: 533 / 226 / 389 / 146). One producer into 8 workers: old 2371, naive 1643, asio 1045, now 35.

1. **Every shared read-modify-write is a lock.** The old pool took the queue mutex twice per task and then did four
   atomic RMWs on two counters every producer and worker touched (`_enqueued` up and down, `_running` up and down), a
   clock read per dequeue (`now() + duration<double>` for a 100 ms timed wait) and a `notify_one` per enqueue. The counters
   cost what the lock did, and they were the part nobody saw. Keep counts in the lock that already guards the structure
   (a plain store) and per-owner flags summed on the rare read, and read the clock only when about to sleep.
2. **Give each role its own lock.** A chunked list with a tail lock and a head lock lets a producer and a consumer meet
   only on the slot a task moves through. Chunks of 64 slots are allocated by the producer and freed by the consumer that
   leaves them, with no reclamation scheme and exact FIFO (1 x 4: 262 -> 34 ns). A lock-free ticketed ring would have
   needed an overflow path and a way to free retired rings.
3. **Pick the lock by the hold time and the crowd.** The producers' lock is held about 30 ns by at most a few threads: a
   spin lock that yields after 64 spins (4 producers x 1 worker, Apple M1 Pro: 108-156 -> 53-79 ns), because a `std::mutex`
   waiter sleeps in the kernel for longer than the wait. The same spin lock on the consumers' side was 2-9x slower with 4 to
   8 workers (47 -> 116-385 ns): they stampede it. Where many contend, let the surplus sleep.
4. **Cache the other side's index.** Under the head lock a consumer keeps the tail position it last read; with a backlog
   it never reads the line the producers write (20-25% faster at 4 x 4 and 4 x 8, M1 Pro).
5. **Do not spin before you sleep without timing the round trip.** A 2-4 us spin before parking left throughput unchanged
   (within noise) and made `async(f).get()` 45% slower (5.3 -> 7.7 us, M1 Pro): the worker sleeps as the caller wakes, and
   a spinning worker keeps its core. Measure the call-and-wait path whenever a park policy changes.
6. **Signal when a sleeper exists and has not been signaled.** A seq_cst pair (producer: publish, then read the sleeper
   count; sleeper: register, then look at the queue once more) loses no wakeup, and a counted token per wakeup stops a burst
   from signaling once per task. In a flood `notify` is not called at all.
7. **Small-buffer the task.** libc++'s `std::function` holds 24 bytes inline and libstdc++'s 16, so a closure with 40 bytes of
   captures allocated per task (old pool, 1 x 4: 416 ns against 262 for a trivial one); a 48-byte inline task costs the same
   as an empty one. `async` through a `promise` instead of a `packaged_task` in a second closure is one allocation fewer.
8. **Do not batch on the consumer side of a pool.** Taking several tasks into a worker's local buffer cuts lock traffic,
   and deadlocks a task that blocks on a later one in its own worker's buffer. The shared FIFO cannot.
9. **A safety timeout hides lost wakeups; count its rescues, and pin the window.** The 100 ms wait turns a lost wakeup
   into 100 ms of latency, which no throughput test shows. A statistical burst test did not kill the mutant that removes
   the sleeper's second look (it survived); a hook that queues a task at that exact point does, deterministically. The
   statistical count also false-fires on a loaded GitHub Actions runner (a task arrives just after a worker's timeout), so
   its bound is a fraction of the bursts, not zero.
10. **A flood test needs a bound.** Producers that outrun an unbounded queue plus a `clear()` that ends only when the queue is
    empty never finish: the first stress test ran 359 s before ctest killed it (macOS x86) and stalled a Linux arm64
    GitHub Actions runner, while it passed on a slower machine. Bound the producers by `size()`, and give a stress test a
    watchdog that names its stage.
11. **TSan cannot see libstdc++'s exception refcount.** A worker that destroys a promise's state frees the exception
    another thread is reading through `what()`; the count is atomic in an uninstrumented library, so TSan reports a race. Read
    the message after the pool is joined.

### allocators

[CHANGELOG](https://github.com/Kronuz/allocators/blob/main/CHANGELOG.md), [docs/perf/construct-forwarding.md](https://github.com/Kronuz/allocators/blob/main/docs/perf/construct-forwarding.md)

1. A hand-written allocator with `construct(pointer, const T&)` as its only overload turns every move into a copy when a
   container calls `allocator_traits::construct(a, p, std::move(x))`: 1000 `push_back(T&&)` of a counting type made 2023
   copies and 0 moves (`std::allocator`: 0 copies, 2023 moves), which is the 1.9-2.6x the
   [second-wave survey](reviews/2026-10-30-survey-second-wave.md) measured for `vector<std::string>`. The standard contract
   needs no `construct` at all; leave it to `allocator_traits`, or make it a variadic forwarding template with `noexcept`
   following the element constructor. Add members only to change behavior.
2. The pool lived in a `shared_ptr` member initialized by default, so the converting constructor (rebind) ran the
   initializer: every rebound allocator was a new, empty pool. `A<T>(A<U>(a)) != a` is a violation of the allocator
   requirements that only shows up when something compares or frees across a rebind; the fix is to share a *family* and
   key the size classes by block size, so rebinding copies a handle (noexcept, allocation-free) and the oracle is the
   standard's own equality rules, tested exhaustively over a small matrix of pools and types.
3. A `noexcept` constructor that allocates turns `bad_alloc` into `terminate`; assert both `is_nothrow_constructible`
   and an operator-new counter around the conversion. Declare `propagate_on_container_*` and `is_always_equal`
   explicitly: with defaults, container swap of unequal allocators is undefined behavior.
4. Sharing state between copies makes thread misuse easier (a container copy used to share the original's unsynchronized
   pool). Make the copy own a new pool (`select_on_container_copy_construction`), document the single-thread contract, and
   make overlap detectable (an atomic flag around allocate/deallocate, on in debug builds). A friend template defined
   in a class template cannot read another specialization's private member (gcc rejects what clang allows): use a member.
5. The Allocator requirements make a move copy the allocator (the source's allocator is "unchanged and equal"), so no trait
   can give a moved-from container a pool of its own: it shares with the container that took its nodes. State that in the
   README and test it, instead of promising independence the standard rules out. A pool that serves one element per
   allocation cannot carry `vector`, `deque` or `unordered_map` past their first array, so the matrix covers node
   containers fully and the array containers only for what is observable (allocator identity, a clean `bad_alloc`).
6. **The library's own fix reopened the hole it closed ([systems audit](reviews/2026-10-31-audit-systems.md) AL1).** The
   identity fix set all three `propagate_on_*` traits to `true_type` as one decision and made copy *construction*
   independent, but copy *assignment* then handed the source's pool to the target: the README promised "a container copy
   gets its own pool", two threads on `d` and `e = d` corrupted the heap (ASan SEGV in `list::pop_front`, TSan race on the
   free list), and the repo's own test asserted the sharing ("POCCA: e takes d's allocator"), so green CI locked the bug
   in. The audit caught it by turning the README sentence into a probe. The three traits are three decisions: a trait that
   lets one container adopt another's mutable state (copy assignment) must be false when the contract promises
   independence; move assignment and swap move the state with its nodes and stay true. Test the contract (a copy never
   shares, with threads under ASan and TSan), not the implementation's choice.
7. A pool's identity can be observed from outside, with no access to its internals: the free list is LIFO, so a block freed
   through `x` is the next one handed out by `y` exactly when they draw on one pool. That is an oracle for `==` that every
   container operation can be checked against through `get_allocator()`. It ties the trait table to behavior: reverting
   the fix (or flipping any one of `propagate_on_container_{copy,move}_assignment`, `_swap`, the copy-construction hook,
   or `==`) fails a named runtime check even with the static asserts removed.
8. The oracle needs no knowledge of the allocator: run the same program with `std::allocator` and with yours and compare
   copy, move and destroy counters (vector, deque, list, map, unordered_map; a nothrow-move type, a throwing-move type, and a
   type that throws from copies and moves at a range of points). A throwing move must fall back to a copy in a vector
   reallocation, and the state after the exception must match too.
9. A test that goes through containers does not test the allocator's own members. Node containers rebind to a node type and
   construct a `value_type*` through the default path, so with libc++ no container test reached the pool's `construct`: a
   mutant of it (no `std::forward`) survived every container check until a direct `allocator_traits::construct(pool, p,
   std::move(x))` call and `noexcept` static asserts were added. Call the member itself as well.
10. Test-environment trap on the shared Linux x86-64 VM: gcc 11's ASan run under a systemd unit looped in the signal handler
   (`DEADLYSIGNAL` storm, 8 minutes of CPU) while the same binary passed from a shell, and gcc 11 TSan segfaulted on every
   test, including untouched ones, with ASLR off too; clang 12 TSan passed. Cap each test (`ctest --timeout`), set
   `ASAN_OPTIONS=handle_segv=0`, run under `setarch -R`, and read a crash that hits untouched tests as the toolchain. See
   also [logger](#logger), item 20.
11. Benchmark the non-trivial type: `vector<int>` tied `std::allocator`, `vector<std::string>` showed the bug.

### fs

[CHANGELOG](https://github.com/Kronuz/fs/blob/main/CHANGELOG.md)

1. `io::write` loops to the full count and returns the *partial* count after a later failure, so `bytes == -1` misses a
   write that ran out of room mid-chunk and the copy is silently truncated. A setrlimit(RLIMIT_FSIZE) one byte short of the
   source reproduces it with no special device (and on macOS); `/dev/full` fails every write, which the old check caught.
   Retry EINTR yourself rather than rely on a process-wide flag, and check the destination's `close`.
2. (Introduced by the short-write fix itself.) Adding `O_TRUNC` to the destination open, to stop a shorter copy leaving the
   old tail, made `copy_file` empty its source whenever source and destination were one file (a directory copied onto
   itself, a hard link, a symlink, a case-insensitive spelling): the open truncates before the first read, the read sees
   EOF, and the call returns 0. The tests of that fix used distinct files, so they could not see it; the
   [systems audit](reviews/2026-10-31-audit-systems.md) (FS1) caught it by running the copy onto itself. A fix that adds a
   destructive step (truncate, unlink, overwrite) needs a test where the destination aliases the source, by every
   spelling the platform has. The check belongs on the open descriptors (`fstat` dev/ino) before the destructive call, so
   no path can change between the check and the use; `O_TRUNC` ignored on a FIFO or device means the replacement
   `ftruncate` must apply only to regular files, or copying into a pipe breaks.

### logger

[CHANGELOG](https://github.com/Kronuz/logger/blob/main/CHANGELOG.md)

1. Signaling a sleeping consumer once per enqueue is a syscall per item, and "skip the signal when the
   consumer is awake" alone does not remove it when the consumer is faster than the producer: it drains,
   sleeps, and the next item wakes it again. Give routine items a small slack (one wheel tick, 1 ms) so the
   consumer sleeps to that time and the items queued meanwhile are due later than its wake time and need no
   signal. Producer cost with the consumer idle: 308 -> 236 ns per line (1 thread), 613 -> 360 ns (4
   threads); call-to-written 666 -> 460 ns.
2. Per-line `localtime_r` is not only a conversion: on macOS it re-reads `TZ` (`getenv_copy_np`), 106 of 122
   samples. Cache the broken-down time per thread per whole second and key it on the `TZ` string; a DST
   change lands on a whole second, so the cache is exact. The `getenv` per call is cheap next to the call it
   replaces.
3. The producer should pay for handing over a pointer, not for the structure's protocol. The producer path (the hand-off
   to the LOG thread) went from 476 to 75 ns a line on an Apple M1 Pro and from 715 to 225 ns on an Intel Core i9-9980HK.
   Moving the wheel insert to the consumer (a lock-free stack, one CAS, the consumer takes the whole stack with one
   exchange and files) was the change that mattered: the first working version cost 127 ns a line, and the formatting,
   clock, counter and thread-local cuts that followed brought it to 114, 107 and 76. The task carries its own link and an
   owning reference, so the hand-off allocates nothing.
4. The consumer inherits what the producer stopped paying. The first version filed every posted task into the wheel, and a
   slot is a chain of 10-entry chunks walked from the head, so thousands of "now" lines in one 1 ms slot cost thousands of
   hops each: the LOG thread drained at 8 us per line, with one 21 ms stall. Tasks whose wakeups never decrease (a
   fixed delay after each call) go into a plain arrival queue merged with the wheel; the drain fell from 664 to 281 ns a line.
   Look at the consumer's cost per item over time (`bench/drain.cc`) whenever the producer's cost drops.
5. Counters written from two sides are the hidden cost of "pending": one `std::atomic` that producers increment and the
   consumer decrements bounces a cache line on every line. Striped producer counters (a line each) plus one consumer-owned
   completed counter, read as completed first and then the stripes, cost nothing on the producer and cannot fall short.
6. Formatting: `std::vformat_to` into a reused string is 58 ns for two arguments on libc++. Writing plain `{}` fields over
   integers, `bool`, `char` and strings straight into a thread-local raw buffer, and handing anything else (a spec, an index, a
   null pointer) to `std::vformat`, was 76 ns for the whole call; a first version that appended to a `std::string` was 107.
   Check every accepted message against `std::vformat` on random and edge inputs, and keep each pattern's types in a list so the
   number of template instantiations stays linear (a four-argument cross product needed 12 GB to compile).
7. Clocks are most of the rest. Read the steady clock once and derive the wall stamp from it with an offset measured again
   every 20 ms (exact to the drift, within 2 us here); on macOS `mach_continuous_time` is 5.6 ns against 15.8 for
   `steady_clock::now` on the M1 Pro (19.7 against 36.5 on the i9), the same clock, so check at start-up that they agree.
   Thread-local accesses (`_tlv_get_addr`), `pthread_self` and `~exception_ptr` each showed in the profile: one thread-local
   block, no exception pointer on the common path.
8. Allocation decides the x86 number. On the i9 the record (`make_shared`, 56 ns) and the text (a 60-byte string, 84 ns) are 140 of
   225 ns, and the sum of two clocks, a record and the formatting, measured alone, is 220 ns; the M1 Pro allocates in a third of
   that. The next lever is a record pool and the text inside the record, not another micro-cut. Say so rather than claiming the
   target on the host that cannot reach it.
9. Hand-written digit formatting must keep the old behavior outside the common range (years past 9999,
   negative fractions, 11-digit epochs): keep `snprintf` there and prove it with a frozen-copy differential
   test over random and DST-edge times with `TZ` switched between calls (170k-460k comparisons).
10. When an optimization changes when something runs by a fixed slack, shift every item of that class alike:
   shifting only routine lines would let a later severe line overtake an earlier routine one. The 1 ms shift skipped
   `clears` lines, so a `clears` line due 0.3 ms out overtook an immediate line logged before it (the commit message said
   order was unchanged). Order-preserving shifts must be `max(due, now + k)` applied to every line: monotone in both due
   time and call time. The test states the contract (due order implies write order for lines logged in that order) and
   checks ~2.7 M pairs; it failed in round 0 on the old code.
11. A refusal path that tests "was the line due" must test the original due time, not the shifted one, or
   every line refused after `finish()` is lost instead of written.
12. Skipping a wake-up needs a flag published under the mutex and read after the wake time is lowered
   (sequentially consistent store/load pair), or a worker about to sleep misses the new task.
13. A stress test of the scheduler found a pre-existing loss on the unmodified code: about one task in two
   million, added from one thread while the wheel walks, never fires. Reproduce a flake against the baseline
   before blaming the change, and keep a test that exposes a known pre-existing race out of CI. See also
   [scheduler](#scheduler), item 5.
14. Merge by the key the structure files under, not by the time you asked for. When the consumer lags, the wheel files an
    overdue key at the floor of its last walk; ordering the queue by due time then lets a queue task overtake a wheel task
    posted before it. It never failed on a fast host and failed on a slow GitHub Actions runner (ASan), where the LOG thread
    was busy while lines were logged. The reproduction is a consumer held in a slow write while 400 tasks are posted; make
    that a round of the ordering test, and show the test fails with the fix reverted.
15. A review by someone who did not write the code (the
    [producer hand-off review](reviews/2026-10-31-logger-producer-handoff.md)) found what the tests could not: the close
    protocol that refuses a racing poster covered one of three exits from the worker loop (the countdown and `finish(0)`
    left a task on the stack holding itself: never run, never freed), and the worker filed tasks while holding its own
    mutex, so a destructor that posted deadlocked it. The stress test for the race had a nanosecond window and passed with
    the close removed. Test each exit and each lock with a seam: a hook between the poster's check and its push, a hook
    between the worker's peep and its sleep.
16. A README sentence that states a guarantee ("the first is never written after the second") must name the paths it
   covers: lines more severe than `LOG_ERR` and lines due at once after `finish()` begins are written at the call and
   can overtake queued ones ([systems audit](reviews/2026-10-31-audit-systems.md) L1). Turn the sentence into a probe
   before publishing it.
17. A frozen copy of the old implementation built as a second executable of the same scripted run, with the bytes required to be
    identical, is the differential test for a change like this. Keep timing out of it: the old library, run first, was starved for
    120 ms on a GitHub Actions runner and wrote a line late, so wait for the line to appear instead of sleeping, and leave a
    latency annotation out of the comparison (check it separately where it is certain). TSan builds skip it: the frozen
    library's relaxed counters give the test's own configuration writes no ordering.
18. A test generator can take the machine down. Pieces of a random format joined into a dynamic width (`{:` `{}` `}`), the next
    argument was a random `int`, and `std::vformat` allocated up to 2 GB twice per case: 21 GB resident on the M1 Pro, 30 GB
    under ASan, and the Linux jobs on GitHub Actions runners died with exit 143 ("the runner received a shutdown signal"),
    which reads as infrastructure. Bound generated values, and read a shutdown signal in the middle of a test as that test's
    memory first.
19. Size a concurrency test by what the structure does to a flood, not by what the machine can post. 200000 `post()`ed tasks due within
    2 ms are overdue by the time the worker files them, so stash files them all at the wheel's floor: one slot, a chain walked from its
    head for each insert, quadratic. Plain builds took 0.2 s and a TSan build more than 30 s (two failures on GitHub Actions
    runners, 6 of 7 runs in one review). Spread the due times into the future, keep the counts where the sanitizer builds
    finish in seconds, and let a join have a longer timeout than the loaded runner needs (a `finish(10)` that joins within
    2 s missed once under ASan). See also [scheduler](#scheduler), item 6, and [stash](#stash), item 1.
20. GCC 11's TSan on a 5.15 kernel dies at start-up (unexpected memory mapping); clang 12 with
   `setarch -R` runs, and a small `<format>`/`<source_location>` shim lets it build C++20 code. Keep the shim
   out of the repository.
21. A dependency fetched at a branch (`cppcodec` at `master`) is a build that can change under you; pin the commit the
   branch names today.
22. Measure the producer in two regimes. With the consumer busy, cache-line and allocator traffic between the
   threads (the entry is allocated by the producer and freed by the consumer) dominates and a removed syscall
   does not show: 1 producer stayed at about 405 ns steady. A burst benchmark with the consumer idle shows
   the producer's own work and matches a sampling profile. The "burst, LOG thread idle" benchmark is dominated by the
   first line's wakeup and the cores' ramp-up (14.8 us for line 0); compare the steady loop.
23. Measure the pieces before touching anything: a microbenchmark of each part of a call alone (`bench/parts.cc`)
    priced it on the M1 Pro as `steady_clock::now` 15.8 ns (six reads, about 100 ns), `std::vformat` of two arguments
    58 ns into a reused string, `make_shared` of the record 21.5 ns, a CAS 6.5 ns, a relaxed `fetch_add` 2 ns. A call that
    cost 476 ns was the wheel insert (announce, descent, chain walk, heap box), a counter the LOG thread also wrote, six clock reads
    and the formatting; no single piece was more than a third.
## Networking, serialization, storage

### url-parser

[CHANGELOG](https://github.com/Kronuz/url-parser/blob/main/CHANGELOG.md)

1. Decoding is O(bytes) in the original and should be O(interesting bytes): `push_back` per byte
   through two nested `switch`es ran at 0.5 GB/s whatever the input. Scanning 16 bytes per step
   (NEON/SSE2 compare against the 2-5 bytes that matter, SWAR fallback) and storing each block as it
   is scanned, then advancing the output only past the clean bytes, took clean 4 KB from 7.9 us to
   157 ns (50x, 26 GB/s, on par with ada's memchr-based `percent_decode` at 147 ns) and 64 KB clean
   from 124 us to 2.3 us.
2. Store first, decide after: writing the whole block and moving the output pointer by the index of
   the first special byte removes the separate "find run, memcpy run" pair (a call per run) and
   makes escape-dense input as cheap per escape as one vector load. The over-copy is safe because a
   decoder's output never outruns its input, so output room >= input remaining.
3. Which bytes are "special" depends on the call: only `%` and `+` unless a separator's substitute
   differs from itself. Pick the scan set per call (template on the count) rather than per byte.
4. A 256-entry nibble table (0xff = not hex) replaces the branchy `hexdigit` pair; `(hi | lo) != 0xff`
   validates both digits in one test. Escape-heavy input (25% `%XX`) 4 KB: 6.0 -> 2.5 us (2.4x), level
   with ada (2.5 us); the escape handling, not the scan, is the floor there.
5. When a function is called twice on the same bytes to produce two outputs of the same shape
   (`QueryParser::init`, `PathParser::init`), emit both in one pass: init + 3 lookups on a 4 KB query
   15.4 -> 6.1 us.
6. `resize()` zero-fills; `resize_and_overwrite` (C++23) does not. Pre-size and write through a raw
   pointer, shrink once; for input with nothing to decode skip the buffer fill entirely and
   `assign` (one memcpy).
7. A runtime-dispatched AVX2 skip (`__attribute__((target("avx2")))` plus `__builtin_cpu_supports`) took
   the 4 KB clean decode from 1.3-1.6x behind ada's memchr to 0.94-0.99x on x86; the rules that bite:
   no lambdas in the target function (they lose the target), `always_inline` helpers need the same
   target, and the skip must only skip (a superset filter), with the exact locate left to the SSE2 code.
8. An array in a hot function costs a stack-protector canary on every path through it (Ubuntu and macOS
   compile with `-fstack-protector-strong`): a 512 byte stack buffer slowed the clean and the tiny
   paths 10-30% until it moved into its own `noinline` function. Read the prologue of the function
   the small cases pass through.
9. Inlining is compiler-specific. Inlining `decode_core` into `QueryParser::init` slowed GCC 13 on x86-64
   by 25-30%, and `noinline` on it cost Apple clang 3-7% on the same rows: the attribute is GCC's only.
   The same goes for the stack-buffer path: on the Apple M4 Pro it lost 8-40% to the in-place decode below
   48 bytes (the copy reads back overlapping 16 byte stores and waits for them) and on the Intel Core
   i9-9980HK it won 2x: a per-arch constant, found by timing both chips.
10. The rewrite was timed on one chip and four sizes, and the [audit](reviews/2026-10-31-audit-parsers.md)
    found the rows around them. 4 to 8 byte inputs with an escape ran at 0.75x of the old decoder on the
    i9 (Apple clang), because the scanner set-up and the string's two resize calls cost more than decoding
    8 bytes (UP1). Inputs shorter than a block now take a byte loop that copies the clean prefix while it
    scans: clean input is one `std::string(q, size)`, dirty input finishes in a small buffer. Sweep the
    sizes below the block width on every chip before calling a SIMD rewrite done.
11. A benchmark that repeats one input teaches the branch predictor that input. The mask-driven pass was
    1.1x faster than the old loop at 4 KB of escapes and 0.82-0.88x at 64 KB on Intel cores (the i9 and
    a GitHub Actions Intel runner), where the count of specials per block is unpredictable; AMD and arm did
    not show it. The x86 mask pass now takes the first 4 KB of a call. Size sweeps must reach past what the
    predictor remembers.
12. A frozen copy of the old decoder as a test oracle, run on every length around the block size with a
    special byte at every position, plus random bytes and all separator-substitute sets, is what makes
    a SIMD rewrite of a decoder with odd corner cases (`%2B` -> `+` -> mapped again, `%` with fewer than
    two trailing bytes stays literal) safe. Build the portable fallback in the tests too.
13. The differential test of a decoder with `plus`, `amp`, `colon`, `eq` and `encoded` knobs has to enumerate
    every subset of remapped separators: a decoder that forgot one separator passed the old test because
    every parameter set remapped all of them or none (UP2; mutants U5-U7 survived it).
14. A timing guard needs its own revert check. The first floor (scan 4 vectors vs 1, 1.10) passed the
    reverted code on arm (1.17); at 1.30 every platform separates (final 1.47-4.7, reverted 0.97-1.17). The
    short-input guard fails with the fix reverted only where the regression exists (x86 clang: 1.21 on the
    i9, 1.39 on Linux), not on GCC runners, and says so in the test.
15. When the quiet timing hosts are booked, GitHub Actions runners are timing hosts for A/B: one job builds
    head and the change and runs both (x86 EPYC and Intel, Neoverse, Apple silicon). They are noisy in
    absolute terms (the same binary varies 2x between runner generations) and exact in ratios within a job;
    the Intel macOS runner reproduced the i9's 64 KB result that the other runners did not.

### http-parser

[CHANGELOG](https://github.com/Kronuz/http-parser/blob/main/CHANGELOG.md)

1. **A byte-at-a-time state machine pays its dispatch on bytes that decide nothing.** The loop head (load, header-size
   count) plus the indirect jump cost about 1.2 ns a byte, a URL byte about 3 ns more in `parse_url_char()`, and a header
   line went through the dispatch six times, a 256-byte chunk frame eight. Take runs of bytes at once (URL characters,
   `HTTP/d.d\r\n`, the end of a header value) and continue in the next state with a `goto` where one state always
   follows another. 1.3-1.8x on a request on an Apple M4 Pro, 1.6-2.3x on an Intel Core i9-9980HK, 6-7x on a 125-byte
   URL, chunked bodies 1.35x and 2.1x; the parser now matches llhttp on x86 and is 0-18% behind on Apple silicon.
2. **Two library calls per short value cost more than the value.** `find_crlf` called `memchr` twice per header value
   (3.4 ns, 10-16% of a header-heavy request). One 16-byte-block pass is faster, but it lost on 12 of 13 workloads when
   inlined into the loop and on arm64 when it was the only change: the vector code costs the big function its registers.
   Out of line and after the other three fast paths it wins. Order the changes, and re-measure the last one first on
   every compiler.
3. **A fast path is verified by the byte-at-a-time result, at every boundary.** A frozen copy of the old parser,
   compared on every callback, its offsets and every field of the struct, over every prefix, every single-byte change,
   every split point, every pause and failure, every byte value at every position of each fast path, and the 80 KB header
   limit at +-24 bytes for each field a run can cross (a run that adds its whole length and checks afterwards moves the
   overflow error). Then break each path on purpose (about 40 mutants) and require a failure. Two mutants survived the
   first test and each led to a new case.
4. **The same instruction savings land differently on each microarchitecture.** Jumping straight to the next state cut
   instructions 6-25% on x86-64 (callgrind) but from +3% to -16% on arm64, and time 27-55% on the i9 (Apple clang),
   5-20% on Linux x86-64 GitHub Actions runners, 6-18% on header rows of the M4 Pro (27% for chunk frames), and about
   nothing for headers on a macOS arm64 runner. Count instructions (callgrind on a GitHub Actions runner is exact and
   needs no quiet machine) to see what a change removed, and time it on the machines that matter before keeping it. A
   middle step can be slower than the one before it (three rows, M4 Pro) and the next one more than make up for it:
   judge the series, and the whole table.
5. **A win on one machine that loses on another is not a win for a library.** Taking the matching part of a special
   header name in one run cut a POST's instructions 5% on x86-64 and was 0-8% faster on every row of an M4 Pro, but on the
   i9 it was 4-10% slower on header-heavy GET rows over six interleaved rounds (and counts 1-1.6% more instructions
   there). Neither the instruction count nor one machine's timing predicted it. Time the last commit against the one
   before it on every machine before keeping it, and drop it (keep the patch and the numbers) when the sign differs.
   Binaries of the same source built on a GitHub Actions runner and on the i9 differ 2-10% on the same host, so compare
   binaries built the same way, interleaved, in one exclusive timing hold.

### http

[CHANGELOG](https://github.com/Kronuz/http/blob/main/CHANGELOG.md)

1. A watcher armed for every request pays for the rare event on the common path. The one-byte disconnect watch cost
   a second `recv` and a `kevent` per keep-alive request: with it, a 14-byte reply took 94.5 us at one connection on an
   Apple M4 Pro and 72.5 us on an Intel Core i9-9980HK against 64.3 and 33.2 us for a minimal Asio server. Reading ahead
   4096 bytes into the connection's own buffer keeps the feature (EOF cancels a running request, pipelined input ends the
   watch) and makes the pending read the next request's read: 80.8 and 55.2 us, and 46.3 to 36.1 us of CPU per request
   on the i9.
2. A timer used as a condition variable (`drain()` waiting for the pending read) costs a pipe `write` and `read` and
   a `kevent` per use on kqueue when it is the earliest timer; a capacity-1 channel that the completion signals costs
   none. A stale token is harmless when the wait loop asks the flag again, so the signal needs no "is anyone waiting".
3. A deadline per operation built as a timer plus an `||` of two coroutines is expensive per reply: with the
   production timeouts on, a request took 145.9 us and 113.4 us of CPU on the i9 and 27.0k req/s at 64 connections,
   against 86.8 us, 67.6 us and 48.4k req/s with the watch, the channel and one slice per reply.
4. Slicing each buffer of a reply for an inactivity bound turned one `sendmsg` into two. Slicing the buffers laid end
   to end keeps one send and copies nothing; a prototype that appended the body to the head added two allocations
   per reply. The test that pins it writes every size around the slice ends and compares the bytes.
5. A read-ahead needs a bound and an order, and both have to be tested where the code is reachable. The bound is
   "no new read until the bytes are consumed" (at most 4096 bytes outside the kernel, whatever the client sends), the
   order is "read() returns the buffer first". The guard against reading over unread bytes sits in `arm()`, which
   `watch()` never reaches while bytes wait (it returns first); only `monitor()`, the deferred-reply path, does. The
   first mutation run killed 5 of 7 mutants and the survivors were exactly that guard and the line that ends the
   watch on data: no test through `watch()` can see them. A test that calls `monitor()` with bytes waiting killed both.
6. Timing tests written for a fast host failed on both macOS GitHub Actions runners, not on Linux and not on the i9: a
   77-byte trickle at 10 ms a byte against a 2 s bound, and a reader that sleeps 20 ms per 64 KiB against a 300 ms slice.
   On a shared runner a sleep takes several times its length. Keep the nominal time under a tenth of the bound, and
   give a test whose failure is a hang its own short socket timeout so a mutant fails in seconds, not at the alarm.
7. g++ 11.2 (the shared Linux x86-64 VM) cannot sanitize C++20 coroutine code: with ASan the first coroutine frame is a
   null dereference (`basic_string::_M_data()` in a test lambda, `io_object_impl` in `coroutine_test`, in code this
   change never touched), UBSan's null check reports "member call on null pointer" on every frame, TSan segfaults
   before the first line of output, and `deferred_asio_test` loops on `DEADLYSIGNAL`. Only a test whose coroutines
   hold no locals (`timeouts_test`) ran clean under ASan there. Run coroutine code under sanitizers on gcc 13 or
   later, clang 17 or later, or Apple clang (GitHub Actions runners and an Apple M1 Pro), and read a crash in untouched
   code as the toolchain's. TSan on that kernel also needs `setarch -R`, and a `set -e` around the run loop hides every
   test after the first failure.
8. A parser that is 1.3x to 2.3x faster on its own benchmarks moved none of these rows beyond their spread (the
   `parser` column in the CHANGELOG): a 14-byte reply with a small request spends almost nothing in it. Measure the
   consumer's row before promising the library's number to a service.

### msgpack

[CHANGELOG](https://github.com/Kronuz/msgpack/blob/main/CHANGELOG.md)

1. Take the parser's arena instead of copying what it built. `MsgPack::unserialise` unpacked into a
   zone of its own and deep-copied the tree into a second one; msgpack-c has an `unpack(zone&, ...)`
   overload, and reading into the value's zone is 5 allocations and one 8 KB chunk instead of 7
   and two: 1.5x on arm64 (1.49x to 1.55x from 63 B to 104 KB), 1.53x to 2.01x on the Intel Core i9-9980HK.
   Look for the call that takes the destination before writing the copy.
2. A tree hashed by building an object per node and packing each leaf into its own 8 KB buffer is
   O(n) allocations (20 to 55 per call, 52 to 146 KB). Hashing the tree with a 256-byte stack buffer:
   7.9x (63 B), 3.9x (0.5 KB), 0 allocations, the same values (12.9x and 6.6x on the i9).
3. Stream to the writer rather than build a DOM to stream: `to_string` 1.3x to 2.5x on arm64, 1.58x to
   1.83x on the i9. Make the same calls in the same order and stop at the same `false`, or the partial text
   before a `NaN` differs.
4. The stream a packer writes to is the hot path of the packer. The first buffer for hashing a 104 KB
   array root had its growth code inline in `write`; the packer calls `write` for every field, the
   compiler stopped inlining it, and the row was 0.57x to 0.69x on x86_64 (1.07x on arm64, where it
   did not show). Marking the growth `noinline` and keeping `write` to a compare, a `memcpy` and an add
   made it 1.13x to 1.15x. Measure the large case on a second architecture and libc before landing a
   fast path for the small case.
5. A `const` method that fills a lazy index is a mutator. `hash()` merged repeated keys in the tree
   as a side effect, so a fast path that only reads would have changed what `serialise()` and copies
   give afterwards. The prototype in the [service survey](reviews/2026-10-31-survey-service.md) did that
   (its checksum differed on the one repeated-key document); the fix takes the tree path only when no key
   repeats and sends everything else to the old code, instead of reproducing the merge. Only a differential
   that runs random operations in random order (hash, then serialise, then copy) can see that; hash against
   a value alone cannot.
6. A frozen-copy differential finds the frozen code's bugs too. Its first run crashed in the frozen
   implementation (`erase` after a repeated-key merge dereferences the end iterator), and AddressSanitizer
   found a use after free on `push_back` onto an array of maps that the frozen copy has as well. Both were
   reproduced on the frozen copy before they were called pre-existing. The merge itself copies the wrong
   element (`*(p + 1)` for `*(q + 1)`): `{"a":1,"a":2,"b":3,"c":4}` becomes `{"a":2,"b":3,"b":3}`. The
   tests keep the behavior (they compare to the frozen copy) and skip the operations that crash it. Both
   were fixed in the next round (items 7 to 10).
7. Fix round: `std::vector<MsgPack>` copies its elements on reallocation unless the move constructor is
   `noexcept`, and `MsgPack(MsgPack&&)` was not. Each deep copy has a zone of its own that its children write
   strings into, so `push_back` onto an array of maps after touching some elements stored pointers into zones
   the vector then freed. One word fixes it; AddressSanitizer found the cause, a stack that said "freed in the
   destructor of a body during `reserve`". Assert `std::is_nothrow_move_constructible_v` for any type kept in
   a vector, and put that check last in the test so that the behavior is what fails when it is undone.
8. Say what the code means before fixing it. "Repeated key" had no stated semantics; the code's intent (overwrite
   the first value, drop the repeat) gives last-value-wins in the first one's position, and a `std::map` plus an
   order vector is the oracle. Every document of up to 6 entries over 3 keys (1092), plus 3000 random ones with
   repeats in 78% of them, find what the hand-written cases miss. The mutants for it: the old shift, no re-visit of
   the moved entry, first value wins, size not reduced.
9. A fix exposes what the bug hid. The deep copies used to reset each element's index of its children by
   accident; with the elements moved, `_update_array` left `_initialized` true over an emptied map and every
   later lookup failed. The first run after a fix is not the last: run the whole suite and read the first
   failing line.
10. Taking a guard out of a differential test re-exposes the oracle's own bugs, and a second libc shows them.
    The frozen code read freed memory on documents with a key that is not a string (a failed fill leaves the
    index half built, and the next fill takes the keys already indexed for repeats and deletes them) and on arrays
    of maps that grow; the Linux GitHub Actions runners never tripped over either, macOS libc++ under
    AddressSanitizer did within a minute. Feed the oracle what it gets right (the merged document), stop a sequence
    at the first exception, leave out the steps it gets wrong, say each in the file header, and record the third bug
    instead of fixing it.
11. A fill that throws has to leave what it found. `_init_map` indexed the entries before a key that is not a
    string and then threw, so the next fill took the keys already indexed for repeats and removed them from
    the tree (`{"a":1, 5:2}`: the second `erase("a")` left `{5:2}`). Check everything that can fail before the
    first change (one pass over the key types) instead of rolling back, and let the oracle be the input: after
    any sequence of calls, each one either throws the one exception or leaves `serialise()` equal to the bytes
    the map came as. 90 documents with every sequence of up to 3 of 12 operations (169,560 runs) found nothing
    a hand-written case had not, and the random part found two more problems next door.
12. Neighbors of a bug show up when its test edits things while it fails. `put` over a key whose value is a
    map that was already read leaves that value's index on the new value (an out-of-bounds read, in the frozen
    copy too), and a `lock()` that throws from a nested fill leaves the outer maps locked. Both are in the
    CHANGELOG as open; the test avoids the first. A model with a RAW kind (bytes it does not interpret) kept the
    model small while the documents carried maps it could not read.
13. `-fno-sanitize-recover` ignores UBSan suppressions (an unrecoverable report is printed whatever the
    file says), so undefined behavior in vendored code has to be fixed in place: `memcpy(dst, nullptr, 0)`
    for an empty string, in the unpacker and in the deep copy.
14. Count the allocator the arena uses. The first allocation test counted `operator new` and said
    "4 versus 4" because `msgpack::zone` allocates itself and its chunks with `malloc`; the saving was
    in the calls the test could not see. A test that cannot fail with the change reverted does not test
    the change: `tools/mutants.py` reverts each of the three and breaks 15 details, and a test must fail on each.
15. "Copy-on-write" in the README was never true: a `MsgPack` copy is a deep copy, 0.37 us at 0.5 KB
    against 3.6 ns for a `shared_ptr` copy. A claim about cost needs a test or a number next to it.
16. A row the change does not touch moved 2.4 to 3.8% in every document and every round. Building both trees with
    `-falign-functions=64` put it at 0.98 to 1.00: the difference was where the compiler placed the code. Measure
    the untouched rows too, and test the explanation (alignment, an unrelated edit) before dismissing or accepting
    a regression of a few percent.
17. Write the benchmark corpus by hand, without the libraries it feeds. Two programs that cannot share a header
    (msgpack-c 1.3.0 and 9.0.0 use the same names) then read the same four documents, and the generator can be
    checked byte for byte against the earlier corpus (all eight files were identical). A checksum of what each
    operation produced, compared by a script, caught nothing here and costs nothing.
18. Check a benchmark row against a known throughput before ranking with it. The nlohmann `dump` row in the
    [service survey](reviews/2026-10-31-survey-service.md) (74 us for 139 KB, 1.9 GB/s) was too fast for that
    library; measured again it takes 433 us (0.3 GB/s), and `to_string` goes from "3 to 4 times slower than
    nlohmann" to 1.5 times faster.

### compressors

[CHANGELOG](https://github.com/Kronuz/compressors/blob/main/CHANGELOG.md)

1. A one-shot built on a streaming class pays the class's whole life per call: a zeroed 256 KB ring
   (`make_unique<char[]>`), a codec stream, a hash state and a string per 2 KB block. Giving the one-shot its
   own loop took 256 B from 1.8 us to 0.44 us (compress) and 1.5 us to 0.03 us (decompress), 1 MB random 1.4x / 3.4x.
   The same mistake survived in the zstd and deflate wrappers, because the
   [systems survey](reviews/2026-10-30-survey-systems.md) graded them "maybe" (small absolute cost). Where the
   library's own streaming API is the oracle, the fast path is cheap to prove: the classes stay as the reference and
   the test compares bytes, exceptions and messages on damaged input. The costs there were a context per call (13 us
   on macOS x86, 1.1 us on Linux: `ZSTD_decompress` of 256 B is a context creation, not a decode), a worst-case string
   zero-filled and then copied, and a 16 KB zeroed buffer plus a string per block.
2. When the output of a codec depends on memory layout (LZ4's prefix mode vs external dictionary), a faster
   path must reproduce the layout, not only the data: contiguous input is equivalent to the ring until the
   ring wraps, so the fast path covers exactly that range and the ring takes over. A differential test with
   inputs at 256 KB +- one block, and a mutant that moves the wrap, is what proves it.
3. A buffer that is fully overwritten should not be zero-filled: a small stack buffer, a per-thread reuse, or
   an uninitialized `new char[]` replaces `string::resize` memsets.
4. Two spellings of "a zeroed string of n bytes" are not the same cost: growing an empty `std::string` with `resize(n)`
   took 2x as long as `std::string(n, '\0')` for a 64 KB frame under Apple's libc++ (1.96 us against 0.96) and tied
   elsewhere. The benches had the bounded and unbounded overloads side by side, and the gap between two rows that
   should be equal is what found it.
5. Compute a checksum only where it can be read: the digest nobody called cost 179 us per MB.
6. On AArch64 clang turns four scalar hash lanes into one NEON vector and runs at half speed (the multiply's
   latency is longer, and the lane chain is the bottleneck, not throughput). An empty `asm("" : "+r"(x))` per
   round pins them to scalar registers: XXH32 179 -> 87 us per MB, identical digests. That fix was true for one
   architecture and the perf work wrote it as if for all: the lane pin sat behind `__aarch64__` while clang and g++
   vectorize the lanes on x86 as well, where the head was 2-6x slower than upstream (g++ on Linux x86_64 501 us
   against 82 us per MiB; Apple clang on x86 277 against 138). The README claimed "upstream xxHash speed" without
   naming an architecture; the x86 table of the [system review](reviews/2026-10-31-system.md) caught it, and
   upstream's own guard (`__SSE2__ || __aarch64__`) had been in the comparator the whole time. A codegen workaround is
   a property of a compiler and a target, so it is measured on every target in the CI matrix, and the assembly of the
   unchanged target is diffed to show the fix touched only the target it was for.
7. The vendored XXH32 said "assume little-endian, the digest is never compared across hosts". storage persists it, so
   the assumption was a claim about callers that nobody had checked (grep for the callers before writing it). The
   kernel now reads through a host policy, which makes the byte-swapped path a template instantiation a test can run on
   any machine (an emulated big-endian load against published values); a hardware-only branch would have stayed
   unexecuted.
8. A faster function can slow its consumer when it changes the allocation pattern: with the one-shots in place
   storage's 1 MB zstd read fell from 740 to 430-450 MB/s (Linux, glibc). The returned 1 MB string was freed at the top
   of the heap on every record, glibc trimmed it back to the kernel, and the next record faulted 256 pages in again; the
   old path's three buffers happened to avoid the trim, and with trimming disabled (`MALLOC_TRIM_THRESHOLD_`) the new
   path was 5% faster. The compressors benches all passed; only the consumer's own row caught it, so the A/B includes
   the consumers' benches. The root fix is to stop allocating per record: `decompress_zstd(compressed, out)` decodes
   into a buffer the reader keeps (710-750 MB/s, and no allocation per call, which a counting `operator new` asserts).
9. Bound a decoder's output from the framing (blocks x block size) in a cheap header pass, and fall back to the
   streaming path above a cap, so a corrupt 1 MB input cannot reserve gigabytes. That rule was wrong as first applied:
   the estimate `blocks * 2 KB` came from a header walk of attacker-controlled 3-byte records, so 98 KB of input
   reserved 64 MB. The contiguous phase is bounded by the ring layout (256 KB), and what follows can grow with the
   decoded data, so no size read from the input is trusted for an allocation. The differential test against the
   stream classes stayed as the oracle; a counting `operator new` in the test turns "no big allocation" into an
   assertion (it fails with the fix reverted).
10. A "it allocates once" claim is testable: a counting `operator new` around the call fails with the fix reverted
    (74 allocations and 5.2 MB for a 1 MB stored deflate record, against 1 and the record's size).
11. The pending ASan fuzz run had written 63 GB of `AddressSanitizer:DEADLYSIGNAL` lines into its log and filled the
    disk of the shared Linux x86-64 VM after hours; the same seed rerun on the same binary finished clean, so the
    cause was not reproduced (a signal storm in the sanitizer, not a finding in the codec). Pipe fuzz output through
    `head -c` and run under a file-size limit.
## Search-engine building blocks

### fst

[CHANGELOG](https://github.com/Kronuz/fst/blob/main/CHANGELOG.md)

1. fst build: a registry keyed by one heap `std::string` signature per written node costs a
   malloc, a hash over a string and a cache miss per node. A flat open-addressing table of
   (64-bit hash, address), verified by decoding the node already in the output, produced the
   identical bytes 2.4x faster (220 -> 93 ns/key, 236k words), and `x = T{}` on a struct that
   owns a vector must be `clear()`.
2. fst range: building and copying a ~100-byte decoded node per transition was most of the
   iteration cost; frames of pointers plus a cursor that decode a transition when taken gave
   1.5x (55 -> 37 ns/key) with the same visit order.
3. The lean-frames `range` made `for_each` a call with two empty bounds and tested the bounds
   at every transition (introduced; [engine audit](reviews/2026-10-31-audit-engine.md) E5, which
   measured it in docset). GCC deletes the dead tests and was 2x to 8x faster than the original;
   LLVM 23 on the Intel Core i9-9980HK does not, and was 0.68x to 0.85x of the original on four
   key sets (Apple clang 17: 1.1x, the Apple M4 Pro: 1.5x). One template parameter on "bounded"
   (`for_each` instantiates the walk without the tests): 1.06x to 1.28x of the original on LLVM,
   and 3% to 10% faster on the other hosts. Time a perf change with every compiler the library is
   built with, GCC and LLVM, before saying how much it won, and make the constant-in-practice
   dimension a template parameter so no optimizer has to prove it. The vector of frames that is
   resized in place instead of pushed (one more variant) lost 25% on short `range` calls: 64
   zeroed frames per call.
4. Memory was never measured across sizes (introduced; [engine audit](reviews/2026-10-31-audit-engine.md)
   E3). The flat table of 16-byte (hash, address) slots at load <= 1/2 won on time at one
   dictionary size, but the table doubles, so bytes per node swing between 32 and 64 and the old
   and new table coexist while it grows: 300k random keys peaked at 1.34x the reference's RSS and
   3M at 1.47x (M4 Pro). A memory claim needs a sweep that straddles the doublings. `fst_memory`
   counts the heap through `operator new` over 15 sizes and fails for the old registry at 6 of
   them (1.48x at 5,000 keys, which no RSS probe at round sizes would have caught).
5. A slot of 32 hash bits plus a 32-bit address is 8 bytes and the table can grow from the
   stored bits alone (the tag is the index). A 24-bit tag with a 40-bit address would have
   re-decoded every node from the output at each doubling. Past 4 GiB of output the slots
   widen to 16 bytes. Peak RSS: 0.49-0.81x the reference at 100k-3M keys, builds as fast
   or faster on every host. A 3/4 load looked better (memory 0.35-0.5x, 1.6x faster at 300k
   on the shared Linux x86-64 VM) and was 8% slower at 300k on arm64: keep the old probe lengths.
6. `same_node()` is the check that makes a 64-bit hash safe, and with a good hash its rejecting
   branches almost never run (introduced; [engine audit](reviews/2026-10-31-audit-engine.md) E2):
   10 of 11 mutants of it passed the byte-for-byte differential test. A test-only macro that
   masks every hash to 0 makes every probe a collision; over every subset of small key sets it
   kills all 11. Test a verification step in the regime where what it guards against is the
   common case.
7. A test that replaces `operator new` links under ASan and fails to link under TSan (its
   runtime defines it): the third GitHub Actions run caught it; the test skips itself there. A
   new test target needs one run of every GitHub Actions job before it is trusted.
8. A perf commit added a sanitizer build directory (`ubsan/`, 68 files with local paths in
   `CMakeCache.txt`; [engine audit](reviews/2026-10-31-audit-engine.md) E1) because `.gitignore`
   listed only `build*/`. Ignore every build directory name before the first `git add -A`; the
   audit found it with `git ls-files`.
9. The 8-byte slot change (item 5) measured 3-8% slower on 32-1,024-key builds until it was
   bisected with variants of one function inside one interleaved run on GitHub Actions runners
   (three more machines and two compilers) before an exclusive timing hold was spent: the node
   writer extracted into a function (5-10%, fixed by `always_inline`), a per-node "narrow or wide"
   check (3%, moved to a counter the table already tested), and two slow-path branches
   (`[[unlikely]]`). Each effect showed on some compilers only (GCC 15, Apple clang 17 and 21,
   LLVM 23 differ), and an untouched function moved 5% with the layout: keep the hot path shaped
   like the old one, add the smallest change, and bisect by variants, not by reading.

### docset

[CHANGELOG](https://github.com/Kronuz/docset/blob/main/CHANGELOG.md)

1. The "scalar popcount on arm64" hypothesis was wrong. A NEON byte-count pass was
   neutral-to-slower than the fused AND+popcount loop; the real cost at density 0.1 was the
   `while (w) { ctz; w &= w-1 }` conversion, whose trip count (about 0.6 bits per word)
   mispredicts every word. Branch-free extraction of two bits per word: 830 -> 253 us (3.3x).
   Profile the stage before choosing the intrinsic.
2. The same C++ costs different amounts per ISA. `countr_zero(0)` is one instruction on
   arm64 and `bsf` plus a conditional move on x86 without BMI1, so the branch-free bit
   extraction that gave 3.5x on arm64 was 0.91x of the plain loop on Apple clang x86
   (1.00x on gcc). With BMI1 (`tzcnt`, `blsr`, a target-attribute function chosen at run
   time) the same form is 2.3x to 2.5x. Microbench the stage alone on each ISA, over many
   distinct inputs so the predictor cannot memorize one bitmap.
3. Choose the extraction by result size: two bits per word up to one bit per word on
   average, four above. Two bits everywhere lost to the plain loop above 2.5 bits per word
   on arm64 (0.78x at density 0.25); four per word at density 0.2 is 2.81x (arm64), 1.86x
   (x86 clang), 2.21x (x86 gcc 16).
4. Branchless lower bound (conditional select) for small sorted arrays: point `test()` 1.6-2.1x.
5. A branch-free lower bound written as a ternary compiled to a compare and branch under
   LLVM on x86-64 (a select on a loaded value is turned back into a branch unless the
   condition is marked unpredictable): point `test()` read 0.4-0.7x of the start on Apple
   clang x86 while arm64 and GCC read 1.6-3x, and the perf work had measured arm64 only.
   `__builtin_unpredictable` restores the conditional move (1.1-1.6x). No timing test pins
   this deterministically; a CTest that compiles the function to assembly and looks for the
   `cmov`/`csel` fails without the hint on x86 clang (and passes on GCC either way).
6. A stack-scratch AND that then memcpys the dense result lost 30% on dense rows for no gain
   on sparse ones: do not add a copy to save an allocation.
7. Inlining a rarely-taken loop into the callers slowed an unrelated operation: ANDNOT of
   two array containers was 7% slower on arm64 until the conversion went out of line and
   the dense path (a move) was small again.
8. Branch-free is not automatically faster. Rewriting the SSE difference with selects or
   arithmetic advances ran 0.69-0.9x on the Intel Core i9-9980HK and a Zen 3 server even over a
   pool of inputs: the branchy loop's carried chain is shorter than the unconditional store,
   popcount and select of the branch-free one. Picking the next block of the SSE union
   with selects is +20% on LLVM (Zen 3), +2% on Apple clang (i9) and -4% on GCC, so it is
   gated to clang. Measure each compiler.
9. A data-dependent loop with two exits per block (skip b values below the block, then
   scan b values inside it) mispredicts twice per block; scanning from the previous block
   end in one loop, with a few harmless extra compares, mispredicts once: NEON array ANDNOT
   1.5x.
10. The same merge algorithm costs fewer instructions with a better network: min/max plus
    interleaving the minima with the maxima (perfect shuffle, 17 instructions for 16 values)
    against min/max plus a half-cleaner sort of each half (about 28): 1.04-1.2x on x86, and
    the NEON union that had been the scalar merge is 1.9-2.8x faster at densities 1e-3 to
    0.03. Verify a network with the 0-1 principle (all pairs of sorted 0/1 vectors) before
    trusting random tests.
11. Reading the comparator's kernels found what profiling would have: CRoaring's difference
    handles the zero element once before the loop, so its loop always uses the cheap
    `pcmpistrm` and keeps the match mask in a vector register; docset tested for a zero on
    every step. Peeling the zero is 1.05-1.3x on the difference and 1.05x on the
    intersection (Apple clang x86).
12. When docset trails a library that runs the same algorithm, run both kernels on the same
    arrays in one process (docset's `subtract16` against CRoaring's `difference_vector16`,
    64 pairs cycled): the i9 gap at density 0.01 is in the kernels (difference 1.28x,
    union 1.19x, intersection 1.11x of CRoaring's time under Apple clang), not in the
    container code, and compiling the same kernels for AVX2 (VEX encoding) changed nothing
    (0.98-1.02 on Apple clang, gcc 16 and a Zen 3 server). Callgrind on Linux then showed
    the difference: 4.0k against 3.8k instructions per call (12% more branches), and the
    union: 12.7k against 7.9k, the clamped selects and head loads that replace a branch
    costing 60% more instructions for 2-20% fewer cycles. A branch-free loop has to be as
    lean as the branchy one to win.
13. The suspected regression (ANDNOT of dense bitmaps, 7%) did not reproduce on a quiet x86
    host or on arm64; the reproducible 7% was on other rows. Sweep ops x densities in one
    interleaved run with an A/A column before choosing what to fix.
14. A benchmark that repeats one input lets the branch predictor memorize the outcome of
    every data-dependent branch. The array ANDNOT kernel read 1.0x at 64 chunks and 0.58x
    at 256 chunks, and 1.42x or 0.58x between two builds that differed only in unrelated
    code: the row measured predictor aliasing, which moves with code layout. Time each
    operation over a pool of random inputs larger than the predictor holds (16 pairs here),
    one version per binary, and read the A/A column per row.
15. A comparison tool that gives the old binary the better of two runs against one run of
    the new one favors the old by the run-to-run noise, which on dense bitmap rows is 5-15%
    and made rows with unchanged code read 0.92-0.94. Give both sides the same number of
    runs and print A/A beside every row.

### bitpack

[CHANGELOG](https://github.com/Kronuz/bitpack/blob/main/CHANGELOG.md)

1. A kernel that reads through `uint8_t*`/`__m128i*` and stores through `uint32_t*` cannot keep
   input words in registers across the stores, so each row loads its words again: 44 vector
   loads for the 13 words of a block at width 13 (one per row plus one per spilling row), 32
   loads of the single word at width 1, 62 for 31 words at width 31, on arm64 and x86 alike. The
   source reads each word once; the asm does not. Count loads against words in the asm
   (`bench/asm_count.py`): `loads == B` is the check, and it is cheaper than timing.
2. The fix that generalizes is a sliding window, not an array. Rows advance by at most one
   word, so a kernel keeps the current word in a register and loads the next only when a row
   crosses into it: one load per word, in order, at most two live, every width, no alias
   analysis. Staging all B words in an array looked equivalent at small widths but spills on a
   16-register file from width 15 (36 stack accesses at width 31, more memory operations than
   the 62 reloads it replaced). Check the worst width on the smallest register file, not the
   width the prototype was timed at.
3. On arm64 the loads went from 1440 to 528 across widths 1 to 32 and the unpack instruction
   count fell 1% (width 31) to 37% (width 1), mean 19%, because `ldp` pairs the old reloads at
   high widths: the gain is at low and middle widths. On x86 SSE2 the two-operand shifts
   overwrite their input, so a word used by two rows is copied between registers where the old
   code loaded it twice: the load count falls to B but the instruction count stays the same
   (clang) or grows up to 13% (gcc 16). Loads that x86 issues two a cycle from L1 were not the
   bottleneck there: timed on an Intel Core i9-9980HK (twelve paired runs, Apple clang 17 and
   gcc 16) the SSE kernel gained 1.5% to 1.8% on unpack and lost 0.5% to 1% on unpack_delta,
   with rows at 0.86x to 0.89x on clang, so it was dropped. It had been its own commit for
   exactly this.
4. One idea can win in one kernel and lose in its neighbor. The same load-once change left
   unpack_delta at 1.00x with Apple clang (the carry chain bounds it at 3.4 integers per ns
   whatever it loads) and cost gcc 16 2% to 3% at widths 2 to 4 and 8, which only the paired
   runs per compiler showed; delta keeps the old kernel. Time every kernel the change touches,
   with every compiler the library is built with, and keep the change out of the ones it does
   not help.
5. The degenerate width is worth a look: at width 32 the packed block is the values, and the
   row loop copied it vector by vector. A memcpy made it 1.64x faster on arm64 (12.99 to 21.25
   integers per ns), faster than simdcomp. Do the same check at width 0 and at the widest width
   of any packer.
6. A perf-only refactor is proven by a frozen copy and a differential test (exact packed bytes,
   decoded values for every single-bit, maximum and complement pattern at every position,
   random blocks, and arbitrary bytes read as a packed block), then by mutating the logic that
   changed: never advancing, loading the wrong word, dropping the width 31 mask and a wrong
   first word each fail it. A 20-line Python model of the advance logic (values exact,
   loads == [0..B-1] for every width) was a cheap first check before any build.
7. A load count is not a speed. The asm said loads == B at every width, and the arm64 gain was
   still only 1.11x over widths 1 to 31 (rows 0.99x to 1.24x; 1.20x at width 1, where the 32
   stores bound the kernel), below the 1.2x the
   [second-wave survey](reviews/2026-10-30-survey-second-wave.md)'s prototype suggested; it did
   close the gap to simdcomp (0.88x to 1.00x). Decide a kernel change by paired timing, and read
   the instruction and store counts to see what bounds the kernel before expecting the load
   count to show up.
8. A harness that reports the best of nine 50 ms trials still moved a row by 0.88x to 1.17x
   between two runs of the same binary (a shared host at load 10 to 20). Alternating runs of
   the two builds, ten or more, and reporting the median of the paired ratios and the per-run
   geometric mean, ruled on rows the bench's own table could not. A row can also depend on the
   buffers' relative alignment (4 KiB aliasing between loads and stores), so a single row from
   one binary is not a regression until another binary or layout agrees.
9. The benchmark reference has to build on the host that is measured: the survey's gap to
   simdcomp on arm64 came from a scratch harness because the repo's reference was SSE-only
   (-msse4.1). The bench now builds simdcomp (it carries a NEON shim) on AArch64. Check a
   reference's edge semantics before comparing at the edges: simdcomp's d1 decoder at width 32
   copies without adding the base, so a 3.7x gap there was not a gap.
10. Time every ISA a change touches while its host can be reached: the SSE2 width 32 memcpy
    (item 5) stayed out of main for lack of an x86 number, because the i9 was unavailable for
    hours and then dropped off the network mid-run.
## Domain: text algorithms, geometry, query parsing

### string-similarity

[CHANGELOG](https://github.com/Kronuz/string-similarity/blob/main/CHANGELOG.md)

1. Levenshtein was the textbook O(n*m) scalar table with two `std::vector<size_t>` per call and
   `std::min({...})` (an initializer list) per cell. Edit distance with unit costs is a
   bit-vector problem: Myers/Hyyro advance 64 cells per word operation, so 300 chars went
   110 us -> 2.3 us and 3000 chars 11.3 ms -> 250 us (46x), at or ahead of rapidfuzz.
2. Trimming the common prefix and suffix first is free and makes near-identical words
   (the usual fuzzy-match input) 3x faster; the DP never needs to see them.
3. The default `icase=true` upper-cased both operands into new `std::string`s in the base
   class on every call. Fold into a stack buffer inside the kernel (heap only past 512
   bytes): one allocation per operand gone, 15-25% of a short-word call.
4. A per-call lookup table does not need the heap or a memset of 2 KB: for patterns up to one
   word, a 256-entry index of 16-bit row numbers plus at most 64 mask words on the stack is
   enough; longer patterns reuse thread-local scratch and clear only the entries they set.
5. Jaro's scalar scan is O(n * window). The same greedy rule (first unused equal character in
   the window) is a mask AND plus a lowest-set-bit; with a "first word not fully used" hint
   the scan stays O(1) words per character: 3000 chars 3.9 ms -> 26 us (150x).
6. For short inputs the cost is setup, not the algorithm: keeping the used set in a register
   and making the match branch free took Jaro on 5-12 letter words 103 -> 77 ns.
7. A latency chain, not the operation count, set the block kernel's speed. Each text
   column's blocks depend on each other through a carry (the horizontal delta leaving
   block w enters block w + 1), about 7 cycles per block, and the next column could not
   start until the reorder window reached it: 3000 chars cost 1.85 ns per block on arm64
   and 2.3 ns on x86, for ours and rapidfuzz's alike (both are the same block recurrence).
   Advancing two columns per visit of each block gives the core two independent chains
   and loads and stores each block's state half as often: 1.05 ns per block on arm64
   (1.8x) and 1.9 ns on x86 (1.25x), with the same bit operations. More columns do
   not help: three and four lose on x86-64 (16 registers) and six lose on arm64 (31).
   "Is this kernel latency-bound or throughput-bound?" is the first question for any
   bit-parallel recurrence; count the dependent operations per step before the total.
8. Ukkonen banding for long near-identical strings was left out at first (rapidfuzz was
   ~10% faster on 3000 chars with 1% edits) because the public API carries no distance
   bound; the retry does it without one, because an exact algorithm can use a bound the API
   does not have. Ukkonen's band (an alignment of cost at most k stays within k diagonals of
   the corner diagonal, width k + 1 once the length difference is taken out) needs k; start
   narrow (length difference + 63), and when the answer is above k, the failed run's result
   is an upper bound of the distance, which is the k of the one remaining run, exact by
   construction. The proof that makes a clipped table safe is one line: blocks that start
   below the band get "every vertical delta +1" and the first active block gets a +1 edge,
   both over-estimates, so the table is never below the true one and equals it on every
   alignment inside the band. 3000 chars with 1% edits: 250 us -> 14.7 us (17x) on arm64,
   13x on x86; 10000 chars 30x (rapidfuzz 2.7 ms -> ours 0.1 ms). Unrelated strings
   gain too (about 2x on 3000 random with 4 letters, together with item 7): the
   narrow run's result is about 0.65 n, a band of that covers 54% of the table.
   A doubling ladder would have cost 2.4x on those; jumping to the upper bound does not.
9. Read the assembly of a hot loop once. `hp[c] = 1; hn[c] = 0` over a two-element array
   became a call to `memset_pattern16` per group of columns (arm64 and x86): 64 calls
   in a 128 character compare, and a visible regression at 65-256 characters until
   initializing the elements one by one removed it. Moving the large multi-word path out
   of line (`noinline`) kept the one-word path's frame small, which is where a 13-40 ns
   near-identical word shows a prologue.
10. Tune a micro-architecture knob on every chip you ship to, and pick it per chip. Columns
    per pass, raw kernel, random 4-letter strings: on the Apple M1 Pro more was always better
    (300 chars: 1 column 4.1 us, 2 3.2, 3 3.1); on the Apple M4 Pro two columns were 7-8%
    slower than one at 288-384 characters (5 and 6 words) and 12% faster at 416-448 (7 words),
    while three was 1-9% faster than one at every length; on the Intel Core i9-9980HK two beat
    three and four (16 registers). One setting per target (3 on arm64, 2 elsewhere) is cheap;
    a single number tuned on the laptop at hand regressed the M4 Pro by 8% at 300 chars.
11. The small case deserves its own small type. Words of up to 64 characters built their
    masks through the general `Peq` constructor (one class, two layouts, an out-of-line
    call, a 512 byte table of 16-bit indices cleared per call) and multiplied by the row
    stride on every text character. An inline stack-only class with a 256 byte byte-index
    and no stride made random 4-16 character words 1.2-1.4x faster on the M4 Pro and
    1.1-1.2x on the i9 (near-identical words 1.1-1.3x): the biggest win for the
    shortest inputs came from the setup, not the recurrence (theme 2, per-call setup).
12. The common prefix is free in Jaro too. Equal leading characters match themselves
    position by position, hold no transposition and take the same positions out of every
    window, so only the rest is matched; the window bound must still come from the full
    lengths and the result formula from the full counts (an invariant, and the mutant
    that recomputes the bound from the remainders fails at once). With the register path
    for words, near-identical words went 1.7x (M4 Pro) and 65 characters with one edit 4.0x
    (M4 Pro), 4.5x (i9).
13. Zero-between-calls tables beat per-call index tables when the pattern is short enough
    to afford them: a 256-entry thread-local mask table (cleared by walking the pattern)
    for up to 64 characters was 1.25x faster than the stack `PeqWord` on random words on
    both the M4 Pro and the i9 (1.5x on the i9 for 20-40 characters); a flat table of 256
    rows x nb words (`DirectRows`, nb up to 64) for longer patterns removes the index load
    and the new-character branch of `Peq`. The invariant is that every path clears what it
    set (a destructor, not a trailing statement), and each table has its own "does not
    clear" mutant.
14. A per-key cursor is not free where it does not pay. Starting each character's scan at
    the first word of its row that can still hold a candidate (stored once per character,
    `min(w, last word of the window)`) cut 3000 random characters over 4 letters 1.7x and
    300 characters over 4 letters by 20%, and it costs a load and a store per character on
    workloads with no repeated work to skip: one repeated 300-character pair is 3.5% slower
    on the M4 Pro and 300 random high bytes stay 12% behind rapidfuzz there, while the i9 is
    ahead on both. Report that, not an average.
15. A non-standard result is a contract. Levenshtein's weighted DP seeds its left column with
    `i + 1` whatever the insert/delete cost is, and Jaro matches in two independent greedy
    passes; a fast path is only valid where it reproduces those exactly (here: costs 1,1 only).
    A frozen copy of the old code plus a bit-exact differential test (random, edge, wide byte
    values, word boundaries 63/64/65/128/129, mutated copies, mutation-checked) made the
    rewrite safe without having to decide what the right answer is.
16. Correctness fixes (owner-authorized; supersede item 15's "non-standard is a contract").
    How the bugs arose: `Jaro_Winkler` derived from `Jaro = StringMetric<Jaro>`, so the CRTP
    base cast to `Jaro` and the boost never ran (and `name()` said Jaro); Levenshtein's left
    column was `i + 1` regardless of the insert/delete cost; Jaro matched in two independent
    greedy passes with `t / 2.0` and a window that wrapped for length 1 (`"a"` vs `"A"`
    scored 0). All three were ported verbatim and then frozen by a bit-exact differential.
    How verification caught them: the differential only proves "same as before", so the
    oracle had to be independent: textbook full-matrix DP, a brute-force Jaro, and
    rapidfuzz-cpp on 1M random pairs (1e-12). Exhaustive small-alphabet tests (27M checks)
    found the Levenshtein bug in the first run; the differential now lists each corrected
    input class, asserts new == oracle everywhere, old == new outside the classes, and that
    old != new occurs inside each (so the class list cannot rot). Six mutants (revert each
    fix, off-by-one window, drop `t /= 2`, prefix length) each fail a named test. Beware a
    comparator's argument order: rapidfuzz's third `jaro_winkler_similarity` argument is a
    score cutoff, not the boost threshold; the old bench passed 0.7 there. The single-pass
    Jaro kernel (one Peq, not two) is also 1.5-2x faster than the two-pass one.
17. Hand-built regressions must survive the common prefix/suffix trim. Two of eleven
    mutants (accept a slightly wrong first result, retry with a narrower bound) survived
    random tests because trimming turned each crafted "insert here, delete nearby" case
    into a seven character problem; a low-entropy string with a few markers, shifted by
    one, keeps 800 characters after the trim and killed both. Every mutant also needs a
    timeout: one (a band bottom too short) never returned.
18. State derived in a constructor goes stale. `Sorensen_Dice` built its sorted bigrams
    in the constructor, as `string_view`s into its own `_str`. `PhoneticMetric` assigns
    the encoded string after construction (so the bigrams described the raw string and
    every pair with different codes scored 0), and a copy or move kept views into the
    source (use after free). The fix was to keep no derived state: a stateless kernel over
    the two strings. The test that found the first one is a matrix, wrapper x inner metric x
    (two-argument, bound), not the wrapper over its usual inner metric.
19. A forwarding constructor `template <class T> M(T&& s, bool icase)` is an exact match
    for a non-const lvalue of its own type and beats the copy constructor (`M b = a;`
    bound a string, or did not compile). Constrain it, `requires (!is_metric_v<T, M>)`
    (derived classes included, so a slice is also a copy), on every metric and wrapper.
    The test copies and moves from non-const and const lvalues and rvalues and through
    `vector` regrowth, because only regrowth moves a bound metric by itself.
20. A metamorphic oracle finds what a textbook oracle cannot: `icase=true` on (a, b) must
    equal `icase=false` on (fold(a), fold(b)), for every metric, two-argument and bound.
    It found one real class (Dice on two one-character strings that are equal only after
    folding) that the textbook formula has no opinion about; the rule it enforces is also
    the answer to the open question ("fold both, then compare"), so the oracle decided.
21. A cap needs a test that can reach it. The per-thread scratch kept the largest request
    ever seen (two 1 MiB strings left about 100 MB per thread). The cap (1 MiB, a block
    for the one call above it) is tested by building the same source twice, once with the
    default cap on strings whose masks need 1.3 MiB, once with a cap of 256 words on
    ordinary sizes, and checking the retained words after every call; the mutant that
    drops the cap leaves 241875 words against a cap of 131072. Check the return of
    `ensure` at every call site: it is null above the cap.
22. Sanitizer CI cost is a test-design property. The ASan+UBSan job on the GitHub Actions
    runners took 39m56s of its 60 because the oracle-heavy tests ran at -O0 with their full repetitions. -O1, a
    `STRSIM_SANITIZED` switch that cuts the repetitions (never the sizes or alphabets,
    so every boundary is still hit) and 40,000 rather than a million rapidfuzz pairs
    brought it to 2m48s; the normal job keeps the full counts. Add the boundary sizes
    (63/64/65, 4094..4098 for the direct rows, 256/512 for the stack buffers) as explicit
    cases, since fewer random repetitions find fewer of them by luck.
23. Compare the kernel through the same wrapper. The long bench rows time the public
    `distance` (equality check, normalization) against rapidfuzz, so the "before" column
    needs the same wrapper around the old kernel, or an unchanged 2.4 us row reads 6%
    slower than it is.
24. Single-pair benchmark rows are optimistic and can mislead the sign. One pair repeated
    lets the branch predictor learn the whole scan (300 random high bytes read 1.03x of
    rapidfuzz on a single pair and 1.33x on distinct pairs, on the M4 Pro). Time hundreds of
    distinct pairs per row and label the repeated-pair rows as such.
25. Layout noise on x86 is 10-20% on 25-60 ns rows with unchanged code (Coffee Lake, the
    JCC erratum). Build both sides with `-falign-functions=64
    -mbranches-within-32B-boundaries`, keep an A/A row in the same run, and compare the
    spread of the runs before reading a 3% difference. The same trap hit the M4 Pro once (a
    Levenshtein row moved 20% with no code change).
26. A failed build must not leave the previous binary behind. A test script on the shared
    Linux x86-64 VM ran `bin/<test>_<tag>` after a compile error (a stray brace, then an
    OOM-killed cc1plus on a loaded machine) and printed the old "passed" and, worse, the old
    mutant's FAILs: delete the output before building and treat "no output" as a failure.
    `xargs -I` also caps the expanded command at 255 bytes on macOS (a long include list
    made it silently build nothing): put the command in a script and pass the test name.

### soundex

[CHANGELOG](https://github.com/Kronuz/soundex/blob/main/CHANGELOG.md)

1. In-place `erase`/`insert` on a string (refined Soundex) is quadratic and allocating; one pass
   into a new string through a 256-entry class table was 66.8 -> 16.3 ns (4.1x).
2. (fix round) The four encoders and `Soundex<Impl>` each had an unconstrained
   `template <typename T> X(T&&)` that encodes a word. For a non-const lvalue or a const rvalue
   of the encoder itself, that beats the copy constructor (exact match against a conversion or
   an lvalue-ref bind), so `SoundexEnglish b = a;` and `vector::emplace_back(a)` did not
   compile. It came with the Xapiand code, not from the perf work; string-similarity's N1b
   (the same shape in its metrics, [string-similarity](#string-similarity) item 19) surfaced
   it, and the smoke test never copied an encoder, so nothing else would have. Constrain a
   forwarding constructor on its first line (`requires (!is_base_of_v<Impl, remove_cvref_t<T>>)`),
   and test copies from a non-const lvalue, a const rvalue, a derived class and `emplace_back`
   of a lvalue. `is_copy_constructible_v` cannot catch it (the failure is a hard error in the
   body, not SFINAE), so the test has to do the copy; with the constraint reverted it fails
   to build, and a copy constructor that drops the code is caught at run time (217 of 262
   checks).

### double-metaphone

[CHANGELOG](https://github.com/Kronuz/double-metaphone/blob/main/CHANGELOG.md), [docs/perf/encoder-cost.md](https://github.com/Kronuz/double-metaphone/blob/main/docs/perf/encoder-cost.md)

1. The rule table was never the cost; the glue around it was. A dictionary word took 132 ns:
   copying it into a `std::string`, a second pass over it for the Slavo-Germanic spellings that
   called a clamping `substr` plus a `string_view` compare at every position, two `std::string`
   keys appended to one class at a time through a runtime-length `append`, and a second key that
   `encode()` built and threw away. Cleaning into a stack buffer between blank padding (four in
   front, six behind), noting the spellings in the same pass, `match_at` as a
   compile-time-sized `memcmp`, and fixed key buffers copied once went to 61 ns (2.2x on words,
   1.6x to 2.0x on names, phrases and long text, Apple M4 Pro; 1.9x to 2.5x on every row on the
   Intel Core i9-9980HK).
2. Make "which output to build" a template parameter when control flow never reads the output.
   `encode` and `encode_alternate` are the same walk with the other key's appends compiled away;
   the output is the same bytes, so the frozen copy compares all three entry points on 7M inputs.
3. Pad a cursor instead of clamping each access. A "safe" `at()` and `substr()` that clamp to
   the word cost a compare and a branch per rule test; four blanks in front and six behind turn
   them into plain loads, and the padding must be as wide as the widest look-behind or
   look-ahead of any rule (an `assert` in `at()` checks it in Debug and sanitizer builds).
4. What is left is the rule walk: 37 of the 61 ns (13 ns cleaning, 7 ns copying the key out).
   A further cut would have to change how the walk dispatches on each letter; it was not
   attempted.
5. Mutation testing found an equivalent mutant, which is information: the blank in front of the
   first letter already stops a leading space from being kept, so the extra `out != first_` test
   was dead code. The code lost it, the mutant list lost the mutant, and the other 19 are killed
   by the differential test.
6. (fix round) `DoubleMetaphone(T&&)` had the same unconstrained forwarding constructor as
   soundex: copying a non-const lvalue did not compile (a const rvalue and a derived class
   neither). Pre-existing, not from the cleaning-pass change; the smoke and differential tests
   never copy an encoder. Constrained with
   `requires (!is_base_of_v<DoubleMetaphone, remove_cvref_t<T>>)`; `test/copy_move.cc` copies it
   every way (67 checks). See also [soundex](#soundex), item 2.

### htm

[CHANGELOG](https://github.com/Kronuz/htm/blob/main/CHANGELOG.md)

1. A fat value type in an inner loop costs as much as the math: the 25-level HTM descent built
   three `Cartesian` (48 bytes, SRID, scale, out-of-line ctor) per level. The same arithmetic on
   a plain 3-double struct, in the same operation order, gave bit-identical ids (72M checked
   points) and 894 -> 500 ns (1.8x); `getTrixelName(Cartesian)` through the id, 932 -> 567 ns.
   (Bit-identical in that build; item 4 is what that claim missed.)
2. Not everything is a win: replacing `ceil(log2(id))` by `bit_width` in `getTrixelName(id)` was
   no faster (52 vs 60 ns: the 27-char std::string allocation dominates), so it was not kept.
3. Keep floating-point expression order identical when a rewrite must stay bit-exact; compare
   against a frozen copy, and check that a mutant (`> 0` to `>= 0`) fails it (92k mismatches).
4. **"Bit-identical" held per build, not across builds, and the test could not tell.** Moving
   the HTM descent from out-of-line `Cartesian` operators to inline arithmetic on a three-double
   struct let the compiler fuse `a*b - c*d` into one FMA (clang within an expression on FMA
   hardware, GCC by default on arm64 and with `-mfma`). The ids then differed from those of
   plain IEEE arithmetic on 0.83% of random points, 4% of special values and 57% of points on
   trixel edges, and `htm_diff` passed because its frozen reference was built with the same
   flags in the same run. The audit found it by comparing builds with different flags. A stored
   key needs an oracle that does not depend on the compiler's FP mode (a reference that rounds
   every operation through a `volatile`, the old code built with `-ffp-contract=off`, a
   checked-in golden table) and a CTest that builds the code under `-ffp-contract=fast`.
5. **A pragma does not stop contraction everywhere; a barrier does, at a price; a probe
   picks.** Clang's `fp contract(off)` and GCC's `optimize("-ffp-contract=off")` keep the code
   fast (593 ns on arm64, the same as the code built with `-ffp-contract=off`), but clang
   ignores its pragma under an explicit `-ffp-contract=fast`. An empty `asm` on each product
   holds everywhere but costs 31% on arm64 (561 -> 738 ns; the compiler can no longer vectorize
   the cross products) and 15% on x86 with FMA. Multiplying by an opaque 1.0 (695 ns arm64,
   1012 ns x86 FMA) and one barrier per group of products (739, 909) were no better. The final
   design compiles both forms and, on the first call, runs the plain one on 48 points a fusing
   build gets wrong; any difference selects the barrier form. A build then cannot return other
   ids, whatever the flags, and the common build pays nothing for the guard. Where the target
   has no fused instruction (x86-64 without FMA) write the plain product in place: a one-line
   wrapper function was 8% slower than the same expression inline.
6. **When the timing hosts are starved, GitHub Actions runners are the lab.** The revert checks
   (old code, new tests: 7 of 8 jobs red), the mutant (7 of 8 red), the 8-platform correctness
   runs, and the bench binaries (built on the runners, downloaded as artifacts, timed in
   one-minute exclusive timing holds on the Apple M4 Pro and the Intel Core i9-9980HK) all ran
   without a local build on the timing hosts.

### cartesian

[CHANGELOG](https://github.com/Kronuz/cartesian/blob/main/CHANGELOG.md)

1. Hashing through a formatted string is slow and lossy at once: mixing the bits of the
   doubles is 217 -> 0.7 ns. Fold -0.0 into 0.0 so equal values hash equally.
2. `toLatLon` (122 ns) was left alone: it is sqrt/atan2/Newton-division bound; only the datum
   map lookup is avoidable and that is far below 1.3x.
3. **A comment that promises an invariant needs the test.** `std::hash<Cartesian>` mixed
   `x*scale` although `==` ignores `scale`, and its comment said equal points hash equally; the
   test checked signed zeros only. A normalized `Cartesian(3, 4, 0)` and `Cartesian(0.6, 0.8, 0)`
   are equal and hashed apart. Test `a == b` implies `hash(a) == hash(b)` over every pair of a
   small domain that varies every field (both zeros, signs, infinities, NaN, seven scales) and
   over random points; the revert failed it on all 8 GitHub Actions jobs.
4. **Time the "equivalent" rewrite, with enough digits.** Folding -0.0 on the bits (shift,
   compare, select) instead of `v += 0.0` cost 5% on arm64 and 14% on x86-64 on a 0.8 ns row,
   and showed only because the bench was printed to 0.001 ns instead of 0.1.
5. See also [htm](#htm), item 6.

### boolean-parser

[CHANGELOG](https://github.com/Kronuz/boolean-parser/blob/main/CHANGELOG.md)

1. The lexer built a `std::string symbol` per input byte for an error message that is
   practically never thrown, and appended the lexeme byte by byte. The lexeme is just a pointer
   range of the input (plus one reader rule: "\n\r" and "\r\n" count as one symbol, so the second
   byte is not in the lexeme); build it once when the token is returned. Plain runs inside a
   bare token or a quoted string are skipped with a tight loop.
2. Moving instead of copying: `Token` copies into the output list, the operator stack and back
   (`Token token_back = stack_operator.back()`) cost a string copy each; `std::move` through the
   shunting-yard and into `IdNode` removes them. `std::list<Token>` is a heap node per token: a
   vector with a head index keeps the same queue API with one allocation.
3. Small fixed costs show up once the per-byte work is gone: `strcasecmp` for five keywords (7%
   of a typical query) became length + first-letter dispatch; a 32-element `std::array<Operand>`
   zeroed and destroyed per `Parse` became raw storage constructed on demand.
4. Result: typical query 743 -> 319 ns (2.3x), 128 random terms 25.0 -> 10.6 us (2.4x), 2 terms
   254 -> 151 ns, 1024 terms 181 -> 99 us. An arena precedence-climbing parser with no heap nodes
   is still 2.5-3x faster: what remains is one `make_unique` virtual node per term and operator
   (alloc + free about 80 ns per term on an Apple M4 Pro), which the public node API
   (`unique_ptr<BaseNode>` children, `release_children`) fixes; a node pool would be the next
   step (item 5).
5. A node pool behind the existing API, instead of an arena: class-specific `operator new` and
   `operator delete` on the node base keep children plain `unique_ptr<BaseNode>` and every public
   type unchanged. A per-thread list per 16-byte size class, bounded at 256 blocks, saves about
   10 ns per node (an allocation and a free are most of a small node's cost) and is returned to
   the heap when the thread ends. Pitfalls, each pinned by a test or a mutant: a block is always
   allocated at its class size (a block allocated at the requested size and then freed into its
   class list is too small for the next request of that class, so `new` and `delete` share one
   `node_class()`), a tree may be destroyed on another thread (the blocks are ordinary heap
   blocks), and the pool hides a use after free from AddressSanitizer, so it is off there and a
   UBSan build runs with it on. On glibc and on macOS the allocator's own size rounding hides
   some overruns, so a mutant of the size class can survive as an equivalent one.
6. Inline storage for the token containers (16 for the queue, 8 for the operator stack) and for
   a 128-byte input removed the per-parse allocations for ordinary queries. Two ways of writing
   the same container measured differently, and so did the lexer: a lexeme assigned in place
   (`assign(ptr, n)`) looked cheaper and made 200 nested parentheses 1.4x slower (7.7 against
   5.3 us on an Intel Core i9-9980HK); a container that kept a mode flag read on every access was
   slower than one that kept its begin and end pointers in step with the heap vector. Measure
   each such variant interleaved with the baseline on the same host before keeping it; the one
   that wins on paper is not always the one that wins.
7. What remains against an arena precedence climber that builds no nodes (i9, ns per parse):
   2 terms 464 -> 146 (arena 160), typical query 955 -> 401 (220), 16 terms 3.74 -> 2.04 us
   (0.85), 128 terms 30.0 -> 17.6 us (7.1), 1024 terms 256 -> 252 us (57; the cache holds 256
   blocks per class, so a tree of 2,000 nodes still pays the heap), 200 nested parentheses
   6.15 -> 5.29 us (4.65). On the M4 Pro: 2 terms 156 -> 80 (56), typical 342 -> 218 (133), 128
   terms 10.8 -> 8.35 us (4.0), 1024 terms 104 -> 104 us (33.7). The rest is the virtual node per
   term, the `unique_ptr` ownership and the lexeme strings; closing it means an API change (an
   arena owner type), which is the owner's decision.
8. A hidden quirk must be pinned before it can be preserved: the pair rule of item 1, the
   `upState` that is never reset (a quote after `]` ends in the bracket state), a lexeme-size cap
   that can never fire (the lexeme has one byte when it is checked), and the implicit OR that is
   emitted after the next operand is already output (`a & b c` is `a OR (b AND c)`, `NOT a b` is
   `a OR (NOT b)`). A 140,000-input differential test against the old sources (compiled into the
   same binary with every global name prefixed, so no second copy of the library is needed at
   run time) found none of them missing; mutating the pair rule made it fail on the first `\r\n`
   input.
9. Fixed the quirk item 8 only preserved (precedence fix, owner-authorized): the shunting-yard
   emitted the next term, then popped tighter operators, and tested
   `precedence(cur) > precedence(top)`, which is also right-associative while the docs said "at
   least as tightly". It arose because the implicit operator was bolted onto the `Id` case
   instead of being treated as a binary operator that must follow the same pop-then-push order.
   A frozen-copy differential could only preserve the bug; what found its real extent was an
   independent recursive-descent oracle checked exhaustively on all 47 million token sequences
   of length <= 9 over {a, b, AND, OR, NOT, (, )}: it also exposed that old accepted malformed
   input (`a NOT` as `NOT a`, `a ()` as `a`) and mis-grouped `a ( b ) & c`. Keeping the
   differential honest meant writing the changed classes down structurally and asserting "old ==
   new outside, old != new in the sure subset, new == oracle everywhere"; two attempts at the
   class were too wide or too narrow and the exhaustive run said so within seconds. Mutants (old
   `toRPN`, `>` instead of `>=`, no implicit operator before NOT or `(`) each die on a named case.
10. (fix round) `PrintTree` cast a MAYBE node to `AndNode`: the MAYBE case was copied from the
    AND case and only the label changed, so it read a child through the wrong class (undefined
    behavior; a segfault in practice) for any tree with a MAYBE node, and no test printed one.
    The new test compares the output with an independent in-order renderer written in the test
    (not a copy of the code under test) and pins the exact layout of `a MAYBE b`; reverting the
    cast segfaults it, and a mutant that changes only the label dies on the layout.
11. (fix round) "Malformed input throws, never undefined behavior" was true for each input the
    author had tried and false for the state the constructor left behind: an unclosed `(` stayed
    in the RPN queue as a token that is not RPN. State the promise as an invariant over the
    object (the queue is empty or one well-formed expression) and establish it in the one place
    the state is produced: `validate()` folds the queue with an operand counter, as `BuildTree`
    folds it with nodes, and throws what `BuildTree` threw, so the exception a caller sees is the
    same and only the throwing stage moves up. An operand surplus is unreachable (adjacent
    operands always get an operator, explicit or implicit), and the exhaustive oracle and the
    fuzzer are what back that claim. Verify with the property, not with more examples: every
    queue the constructor returns must parse.
12. A fuzz target needs its own tests before its findings can be trusted. The first two
    "crashes" of the grammar-aware libFuzzer target (mutator that splices tokens and balances
    parentheses, an independent stack machine, the same oracle) were its own bugs: it looked for
    the word "Exception" in a dump that can contain a lexeme with that word, and it compared the
    message of a lexical error with a syntactic one that the parser reports in a different
    order. Make the harness say which side failed, and replay a known-bad input on it before a
    long run.

### enum-reflection

[CHANGELOG](https://github.com/Kronuz/enum-reflection/blob/main/CHANGELOG.md)

1. The throwing `enum_type<E>(name)` costs 2.3-2.9 us on a miss against 3 ns on a hit (about
   1000x; item 4 has the measured ratio). A lookup API that can miss should offer a result type
   (`std::optional`) next to the throwing form, and the throwing form should be defined in terms
   of it: `enum_try_type` shares the one switch, so it adds no compile time per enum member (the
   preprocessor recursion is the expensive part of this library).
2. A hash-keyed switch is not a lookup until the key is checked. The name switch trusted the
   64-bit hash, and the hash is invertible, so a 15 byte string forged to collide with a member
   returned that member (ER1). The fix compares the input with the member's name in each case
   (exact case first, then ASCII case-insensitive): a hit costs 1.3 ns more on the Apple M4 Pro
   (2.6 to 3.9) and 3.4 ns more on the Intel Core i9-9980HK (5.9 to 9.3), a miss 0.7-1.5 ns,
   compile time and the throwing miss are unchanged. Measure the price of the check and say it.
3. A test that forges collisions has to terminate: the prefixed forger searched three free bytes
   for a collision that does not always exist and hung the GitHub Actions run the first time. Simulate the search
   for every member before committing it, and bound every loop in a test by a count.
4. Write ratios from a measurement: the docs said a throwing miss costs "a thousand" times a hit;
   it is 620-830x (2.0 us against 2.6 ns on the M4 Pro, 3.7 us against 5.9 ns on the i9), now
   510-770x after ER1.

### unicode

[CHANGELOG](https://github.com/Kronuz/unicode/blob/main/CHANGELOG.md), [docs/perf/next-utf8.md](https://github.com/Kronuz/unicode/blob/main/docs/perf/next-utf8.md)

1. Put the common case first and inline. `next_utf8` ran three range comparisons on the lead
   byte before the one-byte case; an ASCII test in front, and the multi-byte decode in its own
   function with one bounds check and one combined continuation test, gave 1.567 to 0.273 ns per
   code point on English (5.7x) and 1.818 to 0.625 in the decode + classify + lowercase loop of a
   tokenizer (2.9x).
2. The price is on input that is not text: random bytes went from 2.998 to 4.137 ns (0.72x),
   because the added branch is taken half the time and unpredictably. Say so next to the table.
   Cyrillic and CJK stayed within the noise.
3. A bulk helper was written (`ascii_prefix`: the number of leading ASCII bytes, eight at a
   time) and measured, and not landed. In a loop that does a table lookup or two per code point
   it was at most 8% faster on English, and 0.7x to 0.8x on Cyrillic and CJK, where the ASCII
   runs are one byte long. Add a public helper only when the loop it serves gets 1.3x.
4. Fix round (its bar: no regression on any row). Item 2 was the regression: an ASCII test on
   the first byte costs 0.5 mispredicts per code point on random bytes (0.67x to 0.72x) and on
   the Intel Core i9-9980HK Cyrillic read 0.84x. The frozen chain tests the minority classes
   (`C2..DF`, `E0..EF`, `F0..F4`) and lets ASCII and stray bytes fall out of the last `else`,
   which is already the cheapest order for random input; putting ASCII first re-sorts it. The
   cure keeps the English win with a branch that is predictable in both regimes: test eight
   bytes for "all ASCII" (one load, one mask). On text it is true almost always, on random bytes
   it is almost never, and a window with anything else goes to the old chain. English is then
   2.3x (it was 5.7x), and no row is below 1.11x on the Apple M4 Pro and the Apple M1 Pro, 0.99x
   on the i9. Variants that did not win: the first byte with `b0 < 0xC2` (ASCII and stray bytes
   together, 0.71x on random), a lead-byte jump table, a 4-byte window (random 0.93x),
   likely/unlikely hints (worse on x86), and decoding the 2-, 3- and 4-byte sequences inline
   from the window word (mixed, worse on CJK, emoji and random).
5. A big function is not inlined into the caller's loop, and the loop then reloads `p` from
   memory every code point. The frozen `next_utf8` was a call per code point (the ASCII cost of
   1.6 to 2.0 ns was the call, not the comparisons). Read the assembly (`-S`, then look at the
   loop): keep the inline part to the window test, and put the rest out of line returning the
   code point and the next address as a two-word struct, which comes back in registers
   (rax:rdx, x0:x1) so `p` stays in one.
6. Two of 17 mutants survived: a lead-byte mask that the lead byte's range already implies
   (`b0 & 0x3F` for `0xC2..0xDF`) and lead bytes `0xF5..0xF7`, whose result the maximum-code-point
   check rejects anyway. Equivalent mutants say which bits the code never needed to mask; the
   two "does not compile" results were static_asserts in the test, which kill a mutant at
   compile time.
7. Equivalent mutants again: with the first byte in the mask, the other seven bytes of the
   window only decide how often the fast path is taken. Dropping the second byte (or only the
   first) changes no result; the mutant that matters drops both. A mutant that stops the cursor
   advancing makes a `static_assert` loop forever, which GCC reports as "non-constant
   condition", not "static assertion failed"; count both as killed at compile time.
8. A guard page (`mmap`, `mprotect(PROT_NONE)`, text ending at its edge) turns every read past
   `end` into a crash in a plain build, so mutants that widen the window's bounds die without a
   sanitizer. One g++ -O3 ASan run of the differential test on the shared Linux x86-64 VM, under
   load from other ASan and TSan builds, printed `AddressSanitizer:DEADLYSIGNAL` in a loop (a
   633 MB log); two reruns were clean. Cap logs with `| head -c`.
9. The same decode loop compiled into two programs measured 1.27 and 1.82 ns on the Cyrillic
   text (40% from code layout and alignment alone). A row's A/A column from one program does not
   catch that: alternate the old and new code over rounds in each program, and rebuild the
   comparison in a second program before believing a difference of 10%.
10. The alignment of the out-of-line function was worth 20% to 25% on the i9 (Cyrillic 0.82x to
    0.99x, CJK 1.10x to 1.36x for the same bytes) and it is not covered by shifting the loop:
    one copy of the callee serves all eight loop alignments. Build the bench with
    `-falign-functions=64` and without it, and decide on the mean. `aligned(64)` on the function
    made the good placement the shipped one. A scratch variant and the header measured 1.10x and
    0.82x on the same row until the callee's placement was equalized: measure the shipped header,
    not a copy of its algorithm.
11. An 8-alignment mean still leaves the host noise: the same unchanged `append_utf8` loop reads
    0.69x to 0.94x on the i9 and 0.98x to 1.02x on the Apple hosts. The M1 Pro (nothing else
    running under an exclusive timing hold) showed A/A 0.0% and layout 0.1% on every row: a quiet
    machine gives cleaner arm timings than a busy one.

### term-color

[CHANGELOG](https://github.com/Kronuz/term-color/blob/main/CHANGELOG.md), [docs/perf/collapse.md](https://github.com/Kronuz/term-color/blob/main/docs/perf/collapse.md)

1. A strip-the-escapes function is its plain-text copy. `collapse()` appended one byte at a
   time: 319 ns for 110 bytes with no escape at all and 266 us for 64 KB. Copying eight bytes at
   a time while none is ESC (the has-zero-byte test on `word ^ 0x1b1b...`) and handing a stretch
   of 64 bytes to `memchr` gives 36 ns and 2.06 us (8.8x and 129x).
2. A library call per short stretch costs more than the byte loop it replaces. The first version
   found each stretch with `memchr`: 10x on plain text, 1.17x on a decorated log line, 0.75x on a
   line of 48 escapes with a few characters between them (835.1 to 1116.7 ns). A
   long-plain-text row alone would have blessed it. Put the candidates (memchr, byte loops,
   eight-byte scan, eight-byte scan plus a scan for the end of each escape) in one scratch
   program and time them over short-stretch lines too: the last one gave 1.7x to 2.9x on the
   decorated-line rows, 3.6x to 5.3x on 64 KB with a color per 40 characters, and kept 125x on
   long plain text.
3. Walk a run once. Counting the escapes of a run and then walking it again to pick the tier's
   escape doubled the work on the escape-dense rows; copy the picked escape as the walk goes and
   rewind the output when the count is not a multiple of three.
4. Three `std::format` calls and two concatenations for 30 bytes of escapes: 203 ns. Writing the
   digits into a stack buffer is 38 ns (5.3x); every `(r, g, b)` is compared against the old
   class (16.7M x 2) to keep the float arithmetic bit-exact.
5. A policy that reads the environment on every call is a per-line cost: `NO_COLOR`, `COLORTERM`
   and `TERM` are 80 to 130 ns a `getenv` on macOS, as much as collapsing a log line. Deciding
   once (`resolve()`) and applying per line took the line from 721 to 174 ns (4.15x). The logger
   still calls `apply()` per line; adopting `resolve()` there is the owner's call because it
   makes an environment change visible at the next resolve, not the next line.
6. Argument-dependent lookup hijacks short common names. A free `apply(string_view, policy)` was
   selected as `std::apply` once a translation unit included `<tuple>` (a scratch benchmark
   did), because a non-const lvalue binds to its forwarding reference better than to
   `const policy&`. The overload became a member (`policy::apply`). A benchmark row for three
   `getenv` calls measured 0.7 ns: the compiler had hoisted them out of the loop. Check that a
   row that looks too good still calls what it claims to.
## Delivery

What it takes for a fix to reach the code that runs, and the process mistakes the audits caught. The
[system review](reviews/2026-10-31-system.md) has the evidence for items 1 to 6.

1. **A fix is delivered when the consumers' pins move.** Every in-family pin of a campaign repo was an
   ancestor of its fix, and most were older than the fix. storage pinned compressors `0498bf5`, the
   campaign's own LZ4 one-shot commit, where 98 KB of 3-byte headers reserves 64 MB and throws
   `bad_alloc` instead of `LZ4CorruptVolume` (fixed in `compressors:8f57675`). fs, storage and Xapiand
   pinned stringified `5b16ec9` (a dangling view after copy or move); datetime, msgpack, storage,
   Detent and Xapiand pinned strict-stox `21b7941` (valid input longer than 63 bytes fails with
   EINVAL); fs, soundex, string-similarity, system, traceback, Detent and Xapiand pinned strings
   `b42d3c4` (`inplace_replace` with an empty search never terminates, `indent` drops blank lines,
   `hasupper` depends on the locale); msgpack, Detent and Xapiand pinned repr `0fe9a1e`
   (`repr(max_size=1)` writes past its buffer); completion and journal pinned allocators `b7daa52`
   (rebound pool allocators compare unequal: heap corruption in `std::list`); Detent and Xapiand ran
   the scheduler that loses one task in two million adds. FetchContent keeps the first declaration,
   so the top-level project decides. Bump in waves, each green before the next (leaves' direct
   consumers first, then their consumers, then Detent and Xapiand), with one upgrade note for all of
   them ([UPGRADING-2026-10.md](UPGRADING-2026-10.md)).
2. **Never commit a build directory.** datetime carried `dbg/` (79 files, 5.4 MB: a `CMakeCache.txt`
   with local paths and four binaries) and fst `ubsan/` (68 files, 7.9 MB). fst is fetched with full
   history by strata and termdict, so every consumer's configure downloaded it. `git rm -r` and a
   `.gitignore` for `build*/` remove them from the tree (`datetime:ed7426b`, `fst:847aa0f`); they stay in
   history unless the owner rewrites it.
3. **Land on the default branch.** btree's default branch is `master`, which strata pins; the campaign
   pushed its btree work to `main`, three commits ahead of `master` and invisible to every consumer
   until the series was rebuilt on `master` (`btree:d81f2a3..512febb`). Ask the repository for its
   default branch before the first push.
4. **`[skip ci]` is for docs and comments only.** escape's docs-cleanup commit also moved a FetchContent
   pin, so the matrix never ran on a build change. Harmless that time; the later pin moves ran CI.
5. **Random test inputs must not depend on evaluation order.** datetime's main went red (run
   41235210764 on `03f36fa`): `linux-x86_64-gcc` failed `datetime_diff` with 3 mismatches in 13,797,729
   checks, all date-math throw paths where the old intermediate month was 0 and the new one carried
   into month 12 of the previous year (`-14y+13m+32s` on 5-24-13). The fix was right; the
   changed-class list missed "throw after a month carry". Only one of eight jobs hit it because the
   generator drew in unsequenced operands, `(chance(50) ? "+" : "-") + (chance(5) ? ...)`, and GCC on
   x86-64 evaluates them right to left, so each platform tested different inputs. Draw into named
   locals so every platform runs the same inputs (`datetime:6dcc958`, `datetime:c654278`).
6. **A per-thread cache needs a cap.** string-similarity's scratch grew to `(distinct + 1) * ceil(n / 64)`
   words times 1.5 per slot and never shrank: two 1 MiB strings through `Jaro` kept about 100 MB per
   thread for the thread's life, where compressors keeps at most 1 MB. string-similarity now keeps at
   most 1 MiB per thread, and a call that needs more takes a block of its own and frees it on return
   (`string-similarity:c0825ff`, `string_similarity_scratch`).
7. **A timed poll can hide lost wakeups.** Removing queue's 1 s polling `wait_for` turned four missing
   notifies it had masked into permanent hangs ([queue](#queue)).
8. **A new flag can turn a harmless call destructive.** fs's `copy_file` gained `O_TRUNC` before any check
   that source and destination differ, so copying a file onto itself emptied it and returned 0
   ([fs](#fs)).
9. **The audits found every item above; the change's own tests did not.** Each change was reviewed from
   a fresh context, start against head, with independent probes and mutants
   ([PERFORMANCE.md](PERFORMANCE.md#audits)).
10. **On a shared machine the queue for timing is the cost, not the timing.** Light builds waited behind
    queued exclusive holds for 15 minutes to 1.5 hours, and some never ran; one script that built,
    tested and timed one idea inside a single short hold started after 13 minutes. What worked: build
    every bench binary on CI (the same commit, several configurations) and only run them on the timing
    machines; batch each workstream's builds, tests, mutants and assembly counts into one script per
    machine; keep each hold to minutes with only the timed command inside it; and time every
    instruction set a change touches while its machine is reachable (bitpack's SSE2 width-32 `memcpy`
    stayed out of `main` for lack of an x86 number: [bitpack](#bitpack) item 10).
