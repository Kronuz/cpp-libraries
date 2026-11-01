# Audit: parsers (url-parser, boolean-parser, enum-reflection, datetime)

- Date: 2026-10-31. Kind: cluster audit of the October 2026 performance and correctness work (read-only).
- Repos: `url-parser:4424e25..2fee053`, `boolean-parser:41a20b5..adf5b11`, `enum-reflection:79fe3fa..7c64eb8`,
  `datetime:fce3d4d..ed7426b`.
- Machines: Apple M4 Pro, Intel Core i9-9980HK, a shared Linux x86-64 VM. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| UP1 x86 slower than start on 4-8 byte inputs with an escape | closed | `url-parser:a7ab7b8` | `url_parser_perf` (short-input ratio; fails with the fix reverted on x86 clang, not on GCC) |
| UP2 differential test blind to a decoder that forgets one separator | closed | `url-parser:f5a8f4f` | `url_parser_diff` (every separator subset) |
| UP3 docs: SWAR step, char-classify pin, unpushed pin commit | closed | `url-parser:9ce4c23`, `url-parser:a7ab7b8`, `url-parser:3a784a9` | - (docs and pin; `fix/overflow-64k` is gone from origin) |
| UP4 ada 1.2-1.3x faster on clean input | partly closed | `url-parser:a7ab7b8` | `url_parser_perf` (scan guard); left: on x86-64 ada is still 3-11% faster on clean 4 KB-64 KB (i9: 3% at 4 KB, 10% at 64 KB); faster than ada on arm64 |
| BP1 `PrintTree()` undefined behavior on a MAYBE node | closed | `boolean-parser:172a5c2` | `boolean_parser` (`test_print_tree`) |
| BP2 unbalanced `(` constructs without throwing | closed | `boolean-parser:172a5c2` | `boolean_parser` (`test_errors`), `boolean_parser_oracle` (every constructed queue parses) |
| BP3 arena comparator 2.4-4.7x faster | owner decision | `boolean-parser:505c341`, `boolean-parser:a18c057` | `boolean_parser` (`test_node_allocation`); the node pool and inline containers landed without an API change; the arena owner type that would close the rest changes the node API and is left to the owner (README, CHANGELOG) |
| ER1 forgeable 64-bit hash accepts a crafted name | closed | `enum-reflection:2a5da3a` | `enum_reflection_names` (forged names against a brute-force oracle) |
| ER2 docs: miss costs "a thousand" hits | closed | `enum-reflection:97c2969` | - (docs: 620-830x, about 500-770x after ER1) |
| DT1 pre-1970 fractions in `timestamp(tm_t)` / `to_tm_t(double)` | closed | `datetime:773205b` | `datetime` (pre-1970 asserts), `datetime_datemath` ("pre-epoch instants out of order"), `datetime_diff` |
| DT2 hygiene: `dbg/` binaries, no A/A row, no external comparator | partly closed | `datetime:ed7426b`, `datetime:03ef0e7` | -; `.gitignore` covers build trees; left: `dbg/` stays in history (rewriting it is the owner's decision, `03ef0e7`), and `bench/bench.cc` has no A/A row and no external comparator row |
| DT3 `normalizeMonths` O(n) loop and int overflow | closed | `datetime:773205b` | `datetime_datemath` (section 6, `normalizeMonths`) |

UP3 and ER2 are documentation findings; their closing commits change docs and a pin, so no test applies.

Audited 2026-10-31 13:00-14:35 PT. Subjects, each the origin default branch as fetched at the
start of the audit and re-fetched at the end:

| repo | start (last commit before 2026-10-30) | head audited | head at end |
|---|---|---|---|
| url-parser | `4424e25` | `2fee053` (code: `1f6aded`) | unchanged |
| boolean-parser | `41a20b5` | `adf5b11` (code: `bbf6109`) | unchanged |
| enum-reflection | `79fe3fa` | `7c64eb8` (code: `7d394c5`) | unchanged |
| datetime | `fce3d4d` | `03f36fa` at 13:00; `ed7426b` from 13:50 | `ed7426b`, unchanged |

Everything below was built and run by me; nothing is taken from earlier reports. Probes and mutants: see
[Probes](#probes) at the end. Hosts: Apple M4 Pro (arm64, NEON), the Intel Core i9-9980HK (x86_64; Apple clang 17, g++ 16.2;
SSE2 path; every timing under an exclusive timing hold), a shared Linux x86-64 VM (clang 12 ASan/UBSan and libFuzzer only; its gcc 11 ASan crashes at
start-up intermittently, 6 of 24 runs, on the START tree too, so it is the toolchain and not the code).

## Verdicts

| repo | verdict |
|---|---|
| url-parser | **BETTER WITH CONDITIONS** |
| boolean-parser | **BETTER** (one owner-authorized behavior change; conditions are follow-ups) |
| enum-reflection | **BETTER WITH CONDITIONS** (the change is small and right; the condition is a pre-existing hole the new API exposes) |
| datetime | **BETTER** |

No blocking finding in any repo: nothing a landed fix round must reopen. Three findings deserve the owner's attention before
the bar is called met: UP1 (x86 loses on 4-8 byte inputs), UP4 (ada is 1.2-1.3x faster on clean input) and ER1 (an untrusted name can be forged into a member).

---

## url-parser: BETTER WITH CONDITIONS

### What I checked

- **Tests.** `url_parser`, `url_parser_diff`, `url_parser_diff_swar` are registered (CMakeLists.txt) and run by the shared
  workflow on Linux x86_64 gcc/clang (SSE2 is the default scanner), arm64 (NEON), both macOS, FreeBSD, ASan+UBSan, TSan. Latest
  CI on main: success at `1f6aded` (push and the nightly schedule); `2fee053` is `[skip ci]` docs. All eight jobs pass.
- **Independent differential** (probe not kept): urldecode against a spec decoder I wrote from the README rules (not from
  `test/urldecode_old.h`), plus a digest of urldecode, every QueryParser lookup and every PathParser state/getter, over
  (A) every string up to length 5 (6 at level 2) over `% 4 G + & = NUL 0xff x B`, padded with 0..32 bytes before and 0..17 after so
  every block alignment is hit; (B) a special at every position of every length 0..100, plus every truncation right after it;
  (C) random long input; 14 substitute sets (4 are new: one substitute differing alone). Inputs sit in exactly-sized heap blocks.
  Level 2 = 51,163,420 checks. **start, head NEON, head SWAR: identical digest `7616011995dd577f`, and all equal the spec.**
  Level 1 (3.8M checks, 14 sets): `909fd3181b10c4b5` on head NEON, head SWAR, head x86 SSE2 (Apple clang 17 and g++ 16.2).
  Level 1 with the original 10 sets: `beb3e4fbef3c2f77` on start (gcc 11), head SSE2 (clang 12) and SWAR (gcc 11) under
  ASan+UBSan on the Linux VM, and head NEON on the M4 Pro. Large inputs (probe not kept: 65520..65552, 100000, 2^20±1, 4 MiB, 11 truncated
  tails, 3 substitute sets, 990 decodes) match the spec on NEON and SWAR.
- **Fuzz** (probe not kept; covered by `url-parser:fuzz/fuzz_parse.cc`; libFuzzer, ASan+UBSan, spec oracle for urldecode and a crash oracle for QueryParser/PathParser,
  substitutes drawn from the first bytes): NEON 24.2M runs, SWAR 23.7M runs (M4 Pro, Homebrew LLVM; Apple's ASan hangs at start-up on this
  macOS), x86 SSE2 2.85M and SWAR 2.55M runs (Linux VM, clang 12). No crash, no mismatch.
- **Mutants** (`url_U*`, mutants not kept; each run against my probe and against the repo's `url_parser_diff`, both under ASan+UBSan):

  | mutant | my probe | repo diff test |
  |---|---|---|
  | U1 `end - p >= 1` (truncated escape reads one past the end) | dies (heap-buffer-overflow) | dies (same) |
  | U2 block loop runs with W-1 bytes left | dies | dies |
  | U3 NEON index `>> 1` instead of `>> 2` | dies | dies (`MISMATCH`) |
  | U5/U6/U7 `mapped_separators` forgets `eq` / `colon` / `amp` | dies (SPEC MISMATCH) | **survives all three** |

  (A `>> 3` variant of U3 is behaviorally equivalent: a short index re-finds the byte on the next step.)
- **Compat.** `url_parser.h` is byte-identical to start; `QueryParser`/`PathParser` layouts unchanged; output bytes equal start
  on 51M checks. Not header-only before or after; header self-contained (clang libc++, g++ 16, `-std=c++17` and `-std=c++20`).
- **Scanner safety by reading** (url_parser.cc): every vector load is guarded by `end - p >= W` (decode_core:225, find:182); the
  over-copy of W bytes to the output needs `out room >= input remaining`, which holds because a step emits at most one byte per
  input byte (`o - o1 <= p - start`); the SWAR path locates the byte with a bytewise loop, so it has no endianness assumption;
  `_mm_loadu_si128`/`vld1q_u8` need no alignment; NUL is not special; the Subst set is never compared against NUL substitutes.

### Performance (my sweep, small-size probe merged into `url-parser:bench/bench_url.cc` and `url-parser:test/perf_guard.cc`, repo `bench/harness.h`, 137 rows x 2 runs each = A/A in-row, exclusive timing hold)

Start and head linked in two binaries, same inputs; "x" = start time / head time.

| host / compiler | rows | median x | head slower | headline rows (start -> head) |
|---|---|---|---|---|
| M4 Pro, clang 17 -O3 | 137 | 2.56 | **0** (min 1.01 at n=4) | urldecode 1 KiB clean 2496 -> 61 ns (40.9x); QueryParser init+3 lookups 1 KiB clean 5733 -> 1716 ns (3.3x); PathParser n=256 1714 -> 303 ns (5.7x) |
| i9, Apple clang 17 -O3 | 137 | 2.91 | **5** (0.74-0.86x) | 1 KiB clean 3745 -> 107 ns (34.9x); QueryParser 1 KiB clean 8867 -> 1355 ns (6.5x); PathParser n=256 2912 -> 859 ns (3.4x) |
| i9, g++ 16.2 -O3 | 137 | 1.89 | **17** (0.59-0.99x) | 1 KiB clean 2017 -> 124 ns (16.3x); QueryParser 1 KiB clean 5635 -> 1788 ns (3.2x); PathParser n=256 2094 -> 761 ns (2.8x) |

A/A (the two "current" runs of one binary, per row) is 0..13% on arm (the machine's load average was 14-28 during the holds; the 4 KiB clean A/A row spread 8-36%) and
0-5% on x86. The large wins and the regressions below are far outside that. The repo's own bench (`url_parser_bench` with ada, M4 Pro only)
is under UP4.

### Findings

**UP1 (non-blocking, but breaks "no arm-only wins"): on x86, head is slower than start on inputs of 4-8 bytes with an escape.**
Repro: the small-size sweep above linked against `4424e25` and `2fee053`, run under an exclusive timing hold on the i9.

| row | start | head | x | A/A |
|---|---:|---:|---:|---|
| urldecode(default) n=4 few-esc, clang | 15.9 | 21.6 | 0.74 | 0.6% / 0.0% |
| urldecode(query set) n=4 few-esc, clang | 15.7 | 20.8 | 0.76 | 1.3% / 2.4% |
| urldecode(default) n=4 few-esc, g++ 16 | 12.6 | 21.1 | 0.60 | 0.0% / 0.9% |
| urldecode(query set) n=4 seps, g++ 16 | 12.3 | 20.9 | 0.59 | 3.3% / 0.5% |
| urldecode(default) n=4 clean, g++ 16 | 12.2 | 16.9 | 0.72 | 1.6% / 0.6% |
| urldecode(default) n=8 25%esc, g++ 16 | 19.9 | 24.6 | 0.81 | 1.0% / 2.4% |

Absolute cost is 3-8 ns; the arm numbers show no loss (0 of 137 rows), and from 8 bytes up head wins on clang. On g++ 16 the
rows n=15..31 with escapes (7 rows) are level to slightly slower (0.94-1.00x; A/A up to 4.6%), and n=8 with escapes is 0.76-0.91x. I tried the obvious cause (the `Scanner` ctor broadcasting 2 or 5 vector constants
for input that never reaches a block): a scalar path for `size < 16` that skips it (mutant `url_perf1`, not kept; same digest `909fd318...`) was
**not** faster (n=4 few-esc 25.0 ns). The cost is therefore elsewhere (`resize(size)` zero-fill plus `resize(n)` in the non-C++23
`fill()`, or the second pass setup); it is not isolated. Suggested: measure `fill()` against reserve-and-append for `size < 16`, and
put an x86 row beside the M-series numbers in the README (it has none).

**UP2 (test gap, non-blocking): the differential test cannot see a decoder that forgets one separator.** `test/urldecode_diff.cc:25`
(`param_sets`) has no set where exactly one of `amp`, `colon`, `eq` differs from its own character; mutants U5-U7 survive the repo's
suite (and the original tests). Head is correct on all of them (my probe). Fix: add `{' ','&',';','#',0}`, `{' ','&','#','=',0}`,
`{' ','#',';','=',0}` (three lines); they kill U5-U7.

**UP3 (docs, non-blocking).** README.md:86 and ARCHITECTURE.md:26 say "16 bytes per step (NEON, SSE2, or SWAR)"; the SWAR
fallback steps 8 bytes (`Scanner::W = 8`). CMakeLists.txt:9-10 and AGENTS.md:36 say char-classify is tracked at `GIT_TAG main`; line 14 pins
`306ecd9`. The remote still has the merged branch `fix/overflow-64k` (from 2026-10-28, before the campaign). A local commit
(`6e70f4c Pin char-classify at a890496`) was not pushed at audit time, so origin pinned a different char-classify SHA than the
local clone.

**UP4 (bar, non-blocking): level with or ahead of ada on escape-bearing input; ada is 1.2-1.3x faster on clean input.** The repo's own bench
(`url_parser_bench` with ada, M4 Pro, exclusive timing hold, the machine at load 14-28 so every row is inflated about 10-20% against the README):

| input | head | frozen old | LUT | ada `percent_decode` | head vs ada |
|---|---:|---:|---:|---:|---|
| 4 KiB clean | 188.7 ns (21.7 GB/s; A/A 187.4) | 8227 | 1426 | 160.4 | ada 1.18x faster (README: 157 vs 147 ns) |
| 4 KiB few escapes ('+'-free row) | 1010 (499) | 7962 | 2009 | 536 | head 1.07x faster |
| 4 KiB 25% `%XX` | 2609 | 6241 | 2211 | 2564 | level (LUT 1.18x faster than head) |
| 64 KiB clean | 2520 (26.0 GB/s) | 129,864 | 18,184 | 1931 (34.0 GB/s) | ada 1.31x faster |
| 64 KiB few escapes ('+'-free) | 16,673 (7450) | 128,034 | 36,177 | 8215 | head 1.10x faster |
| 64 KiB 25% `%XX` | 38,952 | 128,306 | 51,801 | 41,778 | head 1.07x faster |
| QueryParser init+3 lookups, 4 KiB | 6236 (A/A 6234) | 15,790 (old double decode) | | | 2.5x |

The README's four numbers reproduce within 2-6% except clean 4 KiB (157 -> 189 ns, within the load noise: ada moved 147 -> 160). Against the
frozen original the gain is 43x clean, 8x few escapes, 2.4x dense escapes. On clean input ada's `memchr` plus `memcpy` is still 1.2-1.3x
faster at 4 KiB-64 KiB: `urldecode` finds the first special byte 16 bytes per step and then `assign`s the whole input, so a clean input is
read twice; an unrolled find (2-4 vectors per step) is the untested candidate that could close it.

### Bar

Clearly better than the start on arm and, outside tiny inputs, on x86 (median 1.9-2.9x, clean input 16-50x). At the best comparator on
escape-bearing input (level or ahead), ada 1.2-1.3x faster on clean input (UP4), and slower than the start on 4-8 byte inputs on x86 (UP1). The single
changes that would get it there are UP1 (and UP2 to keep it closed) and a wider find loop for the clean path.

---

## boolean-parser: BETTER

### What I checked

- **Tests.** `boolean_parser`, `boolean_parser_diff`, `boolean_parser_oracle` registered; CI success at the code head `bbf6109`
  (all 8 jobs; the earlier two pushes were cancelled by `cancel-in-progress`, not failed; `adf5b11` is `[skip ci]` docs). The ASan job
  takes 27 minutes (limit 60) and is the long pole.
- **The oracle itself.** The documented grammar (README "Grammar and precedence": `NOT > AND > MAYBE > XOR > OR`, left associative,
  implicit OR at OR's level) matches `test/oracle.h`: its recursive descent has one level per operator in that order, a `level()`
  helper that loops left-associatively, and the implicit operator in the OR loop, and I could find no disagreement with the README
  table in its structure. **I then wrote a second oracle with a different structure** (probe not kept; covered by
  `boolean-parser:test/oracle.cc`: precedence climbing
  with binding powers read off the README table; it derives the tree, not the RPN, and checks the library's RPN queue and its `Parse()` AST
  against it with an RPN-to-tree stack that does not use `BuildTree`). Head has **zero** differences from it over every token sequence
  up to length 7 over `{a b AND OR XOR MAYBE NOT ( )}` (5.38M sequences, 28,070 accepted) and 4.5M random sequences of length 1..40
  with word, lower-case and symbol spellings, spacing, quoted phrases (3 seeds), and RPN agrees with the AST on all of them.
  Length 8 over the same vocabulary (48,427,560 sequences, 146,320 accepted, UBSan build) also has **zero** differences. Start has 10,570 differences
  at length 6, all in the documented classes (that is the owner-authorized fix). The repo's oracle test includes XOR/MAYBE only in its
  narrower vocabularies (5 tokens deep); my exhaustive run covers all five precedence levels together to length 7.
- **Mutants** against my probe and against the repo suite (mutants not kept): M1 `>=` to `>` in `pop_tighter` (dies: 512 diffs at length 5); M2 swap MAYBE/XOR
  precedence (dies: 16 diffs; **the repo's `diff` and `oracle` tests die too**, the smoke test passes); M3 forget `operand_ended` after `)`
  (dies: 206 diffs; repo diff and oracle die).
- **Lexer unchanged by the precedence fix.** A lexer probe (probe not kept; covered by `boolean-parser:test/diff.cc`) hashes every token (type, lexeme) and every lexical exception text from
  the public `Lexer` over 150,000 grammar-weighted inputs (quotes, escapes, brackets, `\r\n`/`\n\r` pairs, NUL, 0xff, lexemes of
  1000-1050 bytes, keyword look-alikes): **start and head give the identical digest** `b13163c9f7f1f116` (362,547 tokens, 53,737
  lexical errors) under ASan+UBSan on x86.
- **Fuzz** (now `boolean-parser:test/fuzz.cc`, built with `BOOLEAN_PARSER_FUZZ`; libFuzzer, ASan+UBSan, Linux VM): raw bytes through the lexer, shunting-yard and `Parse()`, and a token mode
  checked against the Pratt reference: 1.62M runs, no crash, no mismatch.
- **Compat.** Public classes and `BooleanTree` member signatures are source-compatible: `front/back/pop_front/pop_back/size/empty`
  keep their shapes (the queue is a vector with a head index). `Token` is move-friendly; copying still works. `std::list` is gone from
  the (private) queue. Header self-contained under C++17 (clang, g++ 16). **Behavior change (documented, owner-authorized):** RPN
  and tree shape change for chains of equal-precedence operators (`a | b | c` is now left grouped) and for implicit-OR
  placement (`a & b c` is `(a & b) | c`); `a NOT b` and `a ( NOT b )` are accepted, and `a NOT`, `a ()`, `( ) a` are rejected at
  `Parse()` (still accepted by the constructor, as before). A consumer that reads the RPN queue directly (Xapiand's query_dsl) sees the
  new order and must be rebuilt against it; CHANGELOG.md records the change under "Fixed", and README/ARCHITECTURE describe the new grammar.

### Performance (repo bench, `-DBOOLEAN_PARSER_BENCH=ON`, frozen original and an arena comparator in the same binary, exclusive timing hold)

| workload | M4 Pro old -> current | x | i9 old -> current | x | arena comparator vs current (M4 Pro / i9) |
|---|---|---:|---|---:|---|
| 2 terms | 258.9 -> 166.9 ns | 1.55 | 665.7 -> 435.9 | 1.53 | 2.7x / 2.6x faster than current |
| 5 terms mixed | 600.2 -> 329.8 | 1.82 | 1656.8 -> 865.1 | 1.92 | 2.6x / 3.3x |
| typical query | 782.0 -> 355.0 | 2.20 | 1883.4 -> 905.6 | 2.08 | 2.4x / 4.5x |
| 16 random terms | 3022.5 -> 1459.0 | 2.07 | 7416.7 -> 3548.4 | 2.09 | 2.8x / 4.7x |
| 128 random terms | 25.6 -> 11.09 us | 2.31 | 63.9 -> 28.5 us | 2.25 | 2.7x / 4.4x |
| 1024 random terms | 190.0 -> 104.0 us | 1.83 | 440.3 -> 243.6 us | 1.81 | 3.0x / 4.6x |
| deep nest 200 | 5194 -> 2638 ns | 1.97 | 10296 -> 5205 | 1.98 | current is 1.1x faster / comparator 1.2x faster |

A/A per row (the two "current" runs): M4 Pro 0.1-4.1%, i9 0.1-6.9%; printed trial spread 2-16% (M4 Pro) and 3-19% (i9). The CHANGELOG's before/after (743 -> 319 ns typical, 25.0 -> 10.6 us at
128 terms, 181 -> 99 us at 1024) is reproduced within 10%: the machine is not recorded there. No row is slower than the frozen
original on either host.

### Findings

**BP1 (pre-existing, non-blocking): `BooleanTree::PrintTree()` is undefined behavior for any tree with a MAYBE node.**
`BooleanParser.cc:372-373` (start `:324-325`) casts the MaybeNode to `AndNode*` and calls `getRightNode()` on the null result.
Repro (probe not kept; covered by `boolean-parser:test/test.cc` `test_print_tree`): `BooleanTree t("a MAYBE b"); t.Parse(); t.PrintTree();` -> UBSan "member call on null pointer
of type 'AndNode'" at start and at head. One-word fix (`MaybeNode`), untested by any registered test.

**BP2 (pre-existing, README claim, non-blocking).** README says malformed input "throws ... never undefined behavior". An unbalanced `(`
(`BooleanTree t("(a")`) constructs without throwing and leaves a `(` token in the RPN queue; only `Parse()` rejects it. Same at start.
A consumer that walks the RPN queue and never calls `Parse()` must check for it.

**BP3 (bar, owner decision).** An arena precedence-climbing comparator is 2.4-4.7x faster than the library on every row except deep nesting;
the remaining cost is one `make_unique` virtual node per term and operator, which `unique_ptr<BaseNode>` children (public API) fix in
place. The next step is an API decision (arena-backed nodes or a node pool), not a tuning change; nothing in this campaign's scope.

### Bar
Better than start (1.5-2.3x, no row worse, correct per the documented grammar, verified by two independent oracles), not at the
comparator floor, and the library has no external comparator row (the arena parser is the campaign's own).

---

## enum-reflection: BETTER WITH CONDITIONS

### What I checked
- `enum_try_type<E>(name) -> std::optional<E>` added, `enum_type` defined through it (enum.h:1294-1349). Test: `static_assert`s and runtime
  asserts in `test/test.cc:140-146` (hit, miss, empty name, case-insensitive); CTest `enum_reflection`; CI success at `7d394c5` (push and nightly).
  `enum_type`'s explicit specialization is unchanged for callers (still `constexpr`, still throws `std::out_of_range`, still usable in `static_assert`).
- **Compile cost** (A/B probe merged into `enum-reflection:bench/bench.cc`, which keeps the runtime rows; one 64-member enum, `clang++ -O2 -c`, 3 runs each): start 1.36/1.39/1.32 s, head 1.37/1.37/1.37 s; object
  16,936 B -> 17,544 B (+3.6%). The claim "one switch, no extra compile time per member" holds.
- **Runtime** (M4 Pro, exclusive timing hold, two runs each): `enum_type` hit 3.06/3.04 ns -> 3.01/3.00 ns; `enum_try_type` hit 3.00-3.01 ns, miss 3.31 ns;
  throwing miss 2.49/2.48 us (start) and 2.06/2.07 us (head); `enum_name` 1.45 ns both. So a throwing miss costs about 690-830 hits (the
  changelog says "about a thousand"; it is hundreds).
- Header self-contained (`<optional>`, `<stdexcept>` added); builds as C++20 as claimed; g++ 16 -std=c++17/20 syntax check passes.

### Findings

**ER1 (pre-existing, but the new API is the natural way to hit it; condition): a name is verified only by its 64-bit hash, and that
hash is forgeable.** `enum_find<E>(name)` returns the perfect-hash slot of `wordwise_ci::hash(name)` (hashes.hh:297-320) and the generated
`switch` (enum.h:1261-1266) matches slots, with no string compare. The hash is a chain of invertible steps (xor, multiply by an odd constant,
xor-shift), so a colliding string of length 15 (8-byte word plus 7-byte tail) needs about 2^8 tries. Repro (probe now
`enum-reflection:test/names_test.cc`, which forges a collision for every member; 727 tries):
`enum_try_type<Role>("\xa6|\x91no\xb2v\x1cg\xfb\x1f\xeb\xd2\xe3\x9d")` is `Role::Admin`; `enum_type` returns it without throwing.
Same at start through `enum_type` (same `enum_find`). Anyone parsing an enum from a request field with `enum_type`/`enum_try_type` to gate
behavior accepts crafted strings. API.md does not state that membership is hash-verified or case-insensitive beyond one clause.
Fix (small, runtime cost one memcmp on a hit): in `_ENUM_PHF_NAMES_CASE` also compare the candidate name (ASCII case-insensitively) before
returning; or document it. This is a security-review item for any consumer that feeds untrusted text to it.

**ER2 (docs).** README/API say a miss "costs about a thousand times a hit"; measured 690-830x on the M4 Pro.

### Bar
The change is small, correct, free at compile time and run time, and the 700x miss fix is real. There is no comparator row for the
throwing/non-throwing split beyond the survey's `flat_hash_map` (2 ns miss), which `enum_try_type` (3.3 ns) matches.

---

## datetime: BETTER

Audited at `03f36fa` (13:00), then `ed7426b` (13:50), after the landed fix commits (month normalization, `is_utc`,
docs, untracked `dbg/`). The "+12M and is_utc" fix is in `03f36fa`; `6dcc958` repaired the differential test it broke on gcc.

### What I checked
- **Tests.** `datetime`, `datetime_diff` (20000 iterations), `datetime_datemath` registered; all pass here on the M4 Pro and on the i9
  (Apple clang 17). CI: `03f36fa` **failed** on linux-x86_64-gcc (`datetime_diff`: 3 mismatches of 13.8M, "throw Year is out of
  range" state dumps on a base month 24), `6dcc958` and `4e5edd1` and the head `ed7426b` (a docs commit) are **green on all 8 jobs**.
  The failed run was a test-side miss (the comparison of post-throw state), repaired in `6dcc958`; I found no code bug in it.
- **Independent behavior probe** (probe not kept; covered by `datetime_diff`): 2 x 250,000 inputs x 9 operations (`Iso8601Parser` both overloads, `isDate`, `isDatetime`,
  `isTime`, `isTimedelta`, `DatetimeParser`, `TimeParser`, `TimedeltaParser`) on grammar-built ISO, basic-form, loose and `||` date-math
  strings, a third of them mutated (random byte, insert, delete). Start (built without UBSan because it has the documented overflow UB)
  versus head: 11.9k differing lines of 2.25M per seed. **Every difference is in a documented class**: loose-format `Z` (was a throw),
  loose-format offset (`is_utc` now set), month arithmetic (`+12M` and friends), 64-bit date-math overflow, negative time field, a
  fraction dot with no digits; none outside (my classifier flagged 78 lines that were loose offsets with one-digit hours; same class).
  Head is **clean under ASan+UBSan** (Homebrew LLVM, M4 Pro) on 150,000 further mixed/mutated inputs (1.35M operations), and under UBSan on
  500,000.
- **Properties without a reference** (same probe, `props` mode, 300,000 random valid dates): `timestamp` equals a days-from-civil I wrote, `to_tm_t`
  and `iso8601 -> DatetimeParser` round-trip, `toordinal`, `getDays_month`, `isleapYear` agree; start and head behave identically (see DT1 for
  the one failing family).
- **Mutants** on the riskiest claim (the month fix), whole repo suite (mutants not kept): D1 (truncating division instead of `floor_div` in `add_term`)
  dies in all 3 tests; D2 (restore `mon % 12` in `normalizeMonths`, the original bug) dies in `datetime_diff` and `datetime_datemath`
  and **passes the smoke test**, which is why the oracle tests matter.
- **Compat.** `datetime.h` differs from start only in a comment. `std::regex` objects `date_re`/`date_math_re` still exported and unused.
  Documented behavior fixes only (CHANGELOG 2026-10-31, each with its oracle). Header self-contained (clang, g++ 16 at c++17/c++20); the
  library itself needs C++20 `<format>` (it does not build on gcc 11, the Linux VM, at start or at head).

### Performance (repo bench, `-DDATETIME_BUILD_BENCH=ON`, frozen old vs new in one binary, best of 7, exclusive timing hold)

| row | M4 Pro old -> new | x | i9 old -> new | x |
|---|---|---:|---|---:|
| parse YYYY-MM-DD | 47.9 -> 9.6 ns | 5.0 | 102.6 -> 18.9 | 5.4 |
| parse ...T00:00:00 | 93.4 -> 14.4 | 6.5 | 194.7 -> 30.7 | 6.3 |
| parse .ffffffZ | 113.1 -> 19.2 | 5.9 | 249.2 -> 37.2 | 6.7 |
| parse ...+hh:mm | 254.7 -> 29.3 | 8.7 | 547.9 -> 53.0 | 10.3 |
| parse 2020/01/02 03:04:05 (loose) | 1488.6 -> 18.2 | 81.9 | 4452.0 -> 37.9 | 117.6 |
| parse ...\|\|+1d/d (date math) | 827.3 -> 55.1 | 15.0 | 2092.6 -> 93.5 | 22.4 |
| isDatetime .ffffffZ | 88.8 -> 14.9 | 6.0 | 181.1 -> 28.8 | 6.3 |
| iso8601 trim | 242.8 -> 28.2 | 8.6 | 521.9 -> 49.3 | 10.6 |
| iso8601 full | 250.4 -> 31.3 | 8.0 | 526.6 -> 67.2 | 7.8 |
| to_tm_t(time_t) | 38.6 -> 8.1 | 4.8 | 80.9 -> 16.3 | 5.0 |

Every claim in LESSONS/CHANGELOG (5-9x ISO, ~80x loose, ~15x date math) reproduces; the x86 gains are larger. No row is slower. The bench
prints best-of-7 and no spread or A/A row; each row's old and new results are first checked equal on 4096 inputs, so the numbers are honest, but the
table cannot show noise.

### Findings

**DT1 (pre-existing, found by the audit, identical at start and head): `timestamp(tm_t)` and `to_tm_t(double)` treat a pre-1970 fraction as
sign-magnitude, so timestamps of pre-1970 datetimes with a fraction are not monotonic.** Repro (probe now the pre-1970 asserts in
`datetime:test/test.cc` and section 5 of `datetime:test/datemath_test.cc`):
23:59:58.9 -> -2.9, 23:59:59.0 -> -1.0, 23:59:59.1 -> -1.1 (the correct values are -1.1, -1.0, -0.9). 59,161 of 300,000 random valid dates (the
pre-1970 ones with a nonzero fraction) differ from days-from-civil by exactly `-2*fsec`; `to_tm_t` inverts the same convention, so round trips pass and the test
suite cannot see it. Post-1970 is correct. Not part of the campaign's scope; an owner call (change the convention or document it).

**DT2 (hygiene).** `7acfefd` committed `dbg/` build binaries (about 3 MB: `dbg/datetime_diff_test`, `dbg/datetime_datemath_test`, `dbg/datetime_test`); `ed7426b`
untracked them, but they remain in history. The bench has no A/A row (see above). No external comparator row exists (no `strptime`/`std::chrono::parse`/absl
row), so "at or near the best comparator" is not measured: ISO date in 9.6-18.9 ns and datetime in 14.4-30.7 ns are in the range of
hand-rolled fixed-width parsers plus validation, but I did not time one.

**DT3 (pre-existing, minor).** `normalizeMonths(int&, int&)` is a public function: `mon < 1` loops once per 12 months (about 180M
iterations for `INT_MIN`), and `year += (mon - 1) / 12` overflows `int` for `year` near `INT_MAX`. Not reachable from the string parsers (they use the 64-bit path).

### Bar
Large, reproduced wins on both ISAs, no regression, five real bugs and the month bug fixed with oracles that die under mutation. Not shown
against an external comparator; that and DT1 are the follow-ups.

---

## Cross-cutting notes

- Linux VM gcc 11 ASan: intermittent `AddressSanitizer:DEADLYSIGNAL` at start-up (6 of 24 runs; the start tree crashes the same way and so
  does the NOALARM build); clang 12 ASan ran clean 8 of 8. Treat gcc-11 ASan results there as void; CI uses clang for ASan.
- Apple clang 17 ASan hangs at start-up on the M4 Pro's macOS (`AsanInitFromRtl` spins in `StaticSpinMutex::LockSlow`); Homebrew LLVM's ASan works.

## Probes

Where each probe of this audit lives now:

| probe | what it did | home |
|---|---|---|
| `url_probe.cc` | independent spec differential + digest | (probe not kept) |
| `url_big_probe.cc` | large inputs against the spec decoder | (probe not kept) |
| `url_fuzz.cc` | libFuzzer, spec oracle | (probe not kept; covered by `url-parser:fuzz/fuzz_parse.cc`) |
| `url.dict` | libFuzzer dictionary | (probe not kept) |
| `url_bench.cc` | small-size sweep, start against head | `url-parser:bench/bench_url.cc` (8 and 16 byte rows) and `url-parser:test/perf_guard.cc` (4 to 16 bytes with escapes, CTest `url_parser_perf`) |
| `bool_oracle_probe.cc` | Pratt oracle (`exhaustive N`, `random COUNT SEED`) | (probe not kept; covered by `boolean-parser:test/oracle.cc`, CTest `boolean_parser_oracle`) |
| `bool_lex_probe.cc` | lexer digest, start against head | (probe not kept; covered by `boolean-parser:test/diff.cc`, CTest `boolean_parser_diff`) |
| `bool_fuzz.cc` | libFuzzer, Pratt reference | `boolean-parser:test/fuzz.cc` (`BOOLEAN_PARSER_FUZZ`) |
| `bool_preexisting_probe.cc` | BP1 and BP2 repros | `boolean-parser:test/test.cc` (`test_print_tree`, `test_errors`) |
| `enum_forge_probe.cc` | ER1 forged name | `enum-reflection:test/names_test.cc` (CTest `enum_reflection_names`) |
| `enum_ab.cc` | compile cost and lookup timing, start against head | `enum-reflection:bench/bench.cc` (lookup rows; compile time is in the CHANGELOG, not in the bench) |
| `dt_probe.cc` | behavior probe (`text COUNT SEED`, `props COUNT`) | (probe not kept; covered by `datetime:test/diff_test.cc`, CTest `datetime_diff`) |
| `dt_preepoch_probe.cc` | DT1 repro | `datetime:test/test.cc` (pre-1970 asserts) and `datetime:test/datemath_test.cc` (section 5, CTest `datetime_datemath`) |

The mutants (`bool_M1-3`, `boolrepo_M2/M3`, `url_U1-U7`, `url_perf1`, `dt_D1/D2`), the raw outputs and the start and head trees
were not kept; U5-U7 are killed by `url_parser_diff` since `url-parser:f5a8f4f`.

**Not run:** the url-parser repo bench (ada rows) on x86 and the 4 KiB/64 KiB rows there (my x86 sweep stops at 1 KiB); TSan
(no concurrent code in these four); FreeBSD, MSVC, arm32 and big-endian (SWAR is endian-free by reading and tested only little-endian);
datetime on the Linux VM (gcc 11 has no `<format>`); an external comparator for datetime; a security review of `PathParser`'s state machine
beyond 48M fuzz runs and the spec check of its buffers.
