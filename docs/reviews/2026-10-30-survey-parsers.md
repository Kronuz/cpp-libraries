# Survey E: parsers (url-parser, http-parser, radix-router, boolean-parser, enum-reflection)

- Date: 2026-10-30. Kind: performance survey of the parser cluster (E), before the October 2026 performance and correctness work (read-only; libraries unmodified).
- Repos (unmodified heads, the last commit before 2026-10-30): `url-parser:4424e25`, `http-parser:52a30d0`,
  `radix-router:35aab1b`, `boolean-parser:41a20b5`, `enum-reflection:79fe3fa`.
- Machines: Apple M4 Pro. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| E-W1 url-parser `urldecode` 32 B plain | landed | `url-parser:1f6aded`, `url-parser:a7ab7b8` | `url_parser_diff`, `url_parser_perf` |
| E-W2 url-parser `urldecode` 4 KB plain | landed | `url-parser:1f6aded`, `url-parser:a7ab7b8` | `url_parser_diff`, `url_parser_perf` |
| E-W3 url-parser `urldecode` 4 KB / 64 KB, 25% `%XX` | landed | `url-parser:1f6aded`, `url-parser:a7ab7b8` | `url_parser_diff` |
| E-W4 url-parser `QueryParser::init` decodes twice | landed | `url-parser:1f6aded` | `url_parser`, `url_parser_diff` |
| E-M1 url-parser `PathParser::init` | landed | `url-parser:1f6aded` | `url_parser` |
| E-M2 http-parser small GET | landed | `http-parser:19875e6..fa58924` | `http_parser_diff`, `http_parser_fuzz` |
| E-M3 http-parser browser GET | landed | `http-parser:19875e6..fa58924` | `http_parser_diff`, `http_parser_fuzz` |
| E-M4 http-parser 64 custom headers | landed | `http-parser:19875e6..fa58924` | `http_parser_diff`, `http_parser_fuzz` |
| E-M5 http-parser POST 1 KB / 64 KB | landed | `http-parser:19875e6..fa58924` | `http_parser_diff`, `http_parser_fuzz` |
| E-M6 http-parser chunked 16x256 B | landed | `http-parser:19875e6..fa58924` | `http_parser_diff`, `http_parser_fuzz` |
| E-M7 http-parser 32 pipelined GETs | landed | `http-parser:19875e6..fa58924` | `http_parser_diff`, `http_parser_fuzz` |
| E-M8 http-parser browser GET in 64 B segments | landed | `http-parser:19875e6..fa58924` | `http_parser_diff`, `http_parser_fuzz` |
| E-W5 boolean-parser "a AND b" | landed | `boolean-parser:2c8599c`, `boolean-parser:505c341` | `boolean_parser_diff` |
| E-W6 boolean-parser typical query | landed | `boolean-parser:2c8599c`, `boolean-parser:505c341` | `boolean_parser_diff` |
| E-W7 boolean-parser 16 / 128 / 1024 random terms | landed | `boolean-parser:2c8599c`, `boolean-parser:505c341` | `boolean_parser_diff` |
| E-M9 boolean-parser 200 nested parens | landed | `boolean-parser:2c8599c` | `boolean_parser_diff` |
| E-M10 enum-reflection non-throwing name lookup | landed | `enum-reflection:7d394c5` | `enum_reflection` |

The http-parser rows landed as one series of bulk scans and direct transitions; after it the parser is level with
llhttp on the Intel Core i9-9980HK and 0-18% behind it on the M4 Pro (http-parser CHANGELOG, 2026-10-31), and
`PathParser::init` plus `next` is 8-20% slower on the i9 since `url-parser:a7ab7b8` than at `9ce4c23` (url-parser
CHANGELOG, "Known"). The boolean-parser implicit-OR hazard below was fixed as an owner-authorized behavior change in
`boolean-parser:00b3021`.

Host: Apple M4 Pro, Apple clang 17, `-O3 -mcpu=native`, all timing under an exclusive timing hold.
Benchmarks: the survey's harnesses now live in `url-parser:bench/bench_url.cc` (ada and LUT columns),
`http-parser:bench/bench.cc` (llhttp column), `boolean-parser:bench/bench_bool.cc` (arena comparator) and
`enum-reflection:bench/bench.cc` (lookup rows; the comparator and compile-time rows: prototype not kept); the
radix-router segment-trie comparator: prototype not kept.
Method: median of 9 trials of about 40 ms each; "spread" = (max-min)/median across trials. Every row is run twice for ours
("#1", "#2 A/A"), so the A/A spread is visible. Libs unmodified. Every comparator row was first checked to return identical
results on the benchmark inputs (decoded bytes, parse stats, route values and param counts, canonical tree dump); a failed check voids the row (details in the notes).

## Results

| library | workload | ours | best comparator | ratio (A/A spread) | diagnosis | est. win | effort | verdict | outcome |
|---|---|---|---|---|---|---|---|---|---|
| url-parser | `urldecode` 32 B plain | 91 ns | ada `percent_decode` 17 ns; LUT single pass 26 ns | 5.3x vs ada, 3.4x vs LUT (A/A 89 ns, ±10%) | per-byte `push_back` through two nested `switch`es; hex via `hexdec`; no skip of plain runs; result string `reserve`d but written via `push_back` (size check + capacity check per byte) | 3-5x | S | **CLEAR WIN** | E-W1 |
| url-parser | `urldecode` 4 KB plain | 9.99 µs (0.41 GB/s) | ada 0.45 µs (9.1 GB/s); LUT 2.07 µs (2.0 GB/s) | 22x vs ada, 4.8x vs LUT (A/A 9.84 µs) | same; ada wins plain input by scanning for the first `%` and copying the rest in bulk | 5-20x on plain input | S | **CLEAR WIN** | E-W2 |
| url-parser | `urldecode` 4 KB / 64 KB, 25% `%XX` | 8.4-9.4 µs / 175 µs | LUT 1.32 µs / 25.7 µs; ada 2.45 µs / 38.9 µs | 6.4x vs LUT, 3.4x vs ada | hex nibble decode through `chars::hexdigit` branches; byte-at-a-time output | 4-6x | S | **CLEAR WIN** | E-W3 |
| url-parser | `QueryParser::init` + 3 `next` (64 B / 512 B / 4 KB) | 406 ns / 2.63 µs / 22.4 µs | decode once + `string_view` split scan: 71 ns / 459 ns / 3.5 µs | 5.7x / 5.7x / 6.4x (A/A within 5%) | `init` decodes the query **twice** (`query` with `\1`/`\0` separators, `query_decoded`) plus two heap strings; both strings have identical length so one pass can fill both | 4-6x | S | **CLEAR WIN** (same fix) | E-W4 |
| url-parser | `PathParser::init` + `next` loop (short to 45-byte paths) | 45-220 ns | none like-for-like (ada parses WHATWG URLs: 201 ns for a full URL, different job) | n/a (A/A within 10%) | `normalize_path` string + two `urldecode` strings (3 allocations once the path leaves SSO) plus a backwards byte state machine with `std::string` temporaries | est. 2x | M | maybe (follows the urldecode fix for free: 1.3-1.6x) | E-M1 |
| http-parser (Joyent 2.7.1) | small GET, 3 headers, 98 B | 120 ns | llhttp 9.4: 70 ns; pico-style scan 31 ns (ceiling, one-shot, unvalidated) | 1.70x vs llhttp, 3.9x vs pico (A/A 122 ns) | byte-at-a-time state machine; `COUNT_HEADER_SIZE` + `PARSING_HEADER` checked per byte; `header_state` matcher run per char of every header name (connection / content-length / upgrade / transfer-encoding); URL chars classified by `parse_url_char` state transition per byte | 1.3-1.7x | L | maybe | E-M2 |
| http-parser | browser GET, 14 headers, 700 B | 410 ns (1.58 GB/s) | llhttp 242 ns (2.67 GB/s); pico-style 154 ns | 1.69x vs llhttp, 2.7x vs pico (A/A 408 ns) | as above | 1.4-1.7x | L | maybe | E-M3 |
| http-parser | 64 custom headers, 2.6 KB | 1478 ns | llhttp 994 ns; pico-style 784 ns | 1.49x vs llhttp (A/A 1482 ns) | as above | 1.3x | L | maybe | E-M4 |
| http-parser | POST 1 KB / 64 KB body (content-length) | 149 / 105 ns | llhttp 83 / 67 ns | 1.8x / 1.6x (header phase dominates; the body skip is already O(1)) | fixed per-message cost (header phase) | 1.3-1.6x | L | maybe | E-M5 |
| http-parser | chunked 16x256 B | 287 ns | llhttp 177 ns | 1.62x | per-chunk size-line state machine | 1.4x | L | maybe | E-M6 |
| http-parser | 32 pipelined small GETs | 3.92 µs | llhttp 1.96 µs | 2.0x | per-message init/begin/complete cost is high (`http_parser_init` + callbacks reload) | 1.5-2x | L | maybe | E-M7 |
| http-parser | browser GET in 64 B segments | 504 ns | llhttp 312 ns | 1.61x | as above plus resume overhead | 1.4x | L | maybe | E-M8 |
| radix-router | 16 / 128 / 1024 routes, static hit | 21 / 29 / 35 ns | segment trie on `absl::flat_hash_map` 29 / 27 / 27 ns | 0.7x / 1.06x / 1.3x (A/A 20 / 29 / 33 ns; 1024-route row ±37%) | near parity; first-byte `indices` linear scan and `std::string` edge compare | n/a | n/a | already good | - |
| radix-router | param hit (`/:id`, `/:id/items/:item`, `/by-name/:name/details`) | 35 / 46 / 62 ns | segment trie 36 / 36 / 37 ns | 1.0x / 1.3x / 1.7x (A/A 35 / 41 / 58 ns, ±10-16%) | param capture does `std::vector::emplace_back` into `Params` and a failed-branch `truncate`; deep trees pay linear `indices` scan per node | 1.2-1.5x on huge tables | S | already good | - |
| radix-router | miss | 12 ns at all sizes | segment trie 20-23 ns | 0.55x (ours faster) | early byte mismatch | n/a | n/a | already good | - |
| radix-router | build 1024 routes | 110 µs | segment trie 98 µs | 1.1x | `make_unique` per node | negligible | n/a | already good | - |
| boolean-parser | "a AND b" (2 terms) | 228 ns | precedence climbing into an arena, `string_view` lexemes: 56 ns | 4.0x (A/A 218 ns) | see below | 3x | M | **CLEAR WIN** | E-W5 |
| boolean-parser | typical `title:"hello world" AND (author:bob OR author:alice) AND NOT draft` | 612 ns | 125 ns | 4.7x (A/A 585 ns) | `Lexer::NextToken` builds a `std::string symbol` per input byte, appends the lexeme byte by byte, copies it into `Token` (`set_lexeme(const&)`), `IsStringOperator` copies the lexeme again; `Token` is copied into `std::list` (one heap node per token), copied again via `stack_operator`/`token_back`; `IdNode` copies the lexeme a third time; one `make_unique` virtual node per operator | 2.5-3x without API change; 4-5x with an arena | M | **CLEAR WIN** | E-W6 |
| boolean-parser | 16 / 128 / 1024 random terms (10 B/term) | 2.26 µs / 20.4 µs / 154 µs | 0.47 / 3.8 / 32.3 µs | 4.8x / 5.3x / 4.8x (A/A 2.27 / 20.2 / 169 µs; last row ±17%) | linear: ~140 ns per term, ~5x the comparator at every size | 3x | M | **CLEAR WIN** | E-W7 |
| boolean-parser | 200 nested parens | 3.6 µs | 2.7 µs | 1.34x | dominated by operator-stack pushes of copied `Token`s | 1.3x | M | maybe (same fix) | E-M9 |
| enum-reflection | `enum_name(value)`, 8 / 32 / 128 dense, 32 sparse | 0.3 / 1.3 / 1.5 / 1.3 ns | dense array index 0.3 ns; binary search 1.8-5.6 ns | 1.0x at 8; 4-5x slower than a bare array at 32-128 but 2.6-3.7x faster than binary search for sparse | perfect hash + switch is O(1) | none | n/a | already good | - |
| enum-reflection | `enum_type<E>(name)` hit, 8 / 32 / 128 / 32 sparse | 3.0 / 3.2 / 3.6 / 3.3 ns | `absl::flat_hash_map` 4.9 / 4.7 / 4.6 / 4.8 ns; magic_enum-style linear scan 6.2 / 19.3 / 57.8 / 16.7 ns; sorted binary search 11-20 ns | 0.6-0.8x vs flat_hash_map (ours faster); 2-16x faster than linear scan (A/A within 3%) | one FNV-1a over the name plus PHF slot plus switch | none | n/a | already good | - |
| enum-reflection | `enum_type<E>(unknown name)` | 2.3-2.9 µs (throws `std::out_of_range`) | `enum_find` (no throw) 2.2 ns; flat_hash_map miss 2 ns | ~1100x slower than the non-throwing form | exception cost; API only offers the throwing `enum_type`. `enum_find<E>(name)` exists but returns an opaque slot, not a checked value | n/a (API) | S | maybe (add a non-throwing `enum_try_type` → `std::optional<E>`; additive, not a perf rewrite) | E-M10 |
| enum-reflection | compile time, 200 members in one TU (8+32+128+32), 8 uses | 4.6 s vs 0.2 s empty TU (3 runs: 4.58-4.65) | none benchmarked (magic_enum scales with range, not members) | ~23 ms per member; object size 25 KB | preprocessor `_ENUM_M<n>` recursion repeated 6 times per enum (values, names, phf values, phf names, two switches) and two `constexpr` PHF constructions per enum | compile-time only | M | not worth it (documented: "❌ very many members") | - |

### Verdicts in one line

- CLEAR WIN: url-parser `urldecode` + `QueryParser::init` (3-6x, up to 20x on plain input); boolean-parser (4-5x).
- maybe: http-parser (1.5-2x gap to llhttp, large effort on vendored code); PathParser (follows decode fix); enum non-throwing lookup (API addition).
- already good: radix-router, enum-reflection runtime.

## CLEAR WINs

### 1. url-parser `urldecode` / `QueryParser::init`

- **Start files:** `url-parser:url_parser.cc` (`urldecode`, `QueryParser::init`, `PathParser::init`), `char-classify:chars.hh` (`hexdec`/`hexdigit`).
- **Single biggest change:** make `urldecode` a two-phase routine: `memchr`-style scan (or `find_first_of("%+&;=")`) for the first byte that needs mapping, copy the clean prefix in one `append`, then a 256-entry LUT loop writing through a raw pointer into a pre-sized buffer (resize once, shrink at the end). In `QueryParser::init`, fill `query` and `query_decoded` in one pass: both have the same length and the same positions (the code already relies on it in `get()`), so one loop can emit two bytes per input byte.
- **Must stay identical:** the output bytes for every input, including the odd cases: `%2B` decodes to `+` and is then mapped to `plus` (the second `switch`); `%` with fewer than two trailing bytes or with a non-hex digit stays literal `%`; `encoded` (when nonzero) replaces every decoded byte except `{`, `,`, `}`; `&`/`;`/`=` map to the supplied substitutes both when literal and when produced by `%XX`; the `\1` / `\0` separator conventions of `QueryParser::init`; the public signatures (`urldecode(const void*, size_t, ...)`, the `string_view` and array overloads).
- **Verification used:** my LUT decoder was byte-identical to `urldecode` on all 8 workloads; ada `percent_decode` identical after removing `+` and `%2B` (it has no `+` handling).

### 2. boolean-parser

- **Start files:** `BooleanLexer.cc` (`NextToken`), `BooleanToken.h`, `BooleanParser.cc` (`toRPN`, `BuildTree`), `IdNode.h`.
- **Single biggest change:** stop copying strings. In `NextToken`, scan with indices into the input (the input buffer is owned by `BooleanTree`, so a `string_view`/range is stable) and build `Token`'s lexeme once with `assign(begin, end)`; drop the per-byte `std::string symbol`/`lcSymbol`; `std::move` the `Token` into `stack_output`/`stack_operator` and the lexeme into `IdNode`. That alone removes most of the ~140 ns/term. Second step (API-visible): replace `std::list<Token>` with a vector-backed container.
- **Must stay identical:** the tree for every input, including the shunting-yard quirks that the tests may rely on (see hazards): right associativity, NOT precedence, the implicit-OR placement; the lexemes with quotes and bracket lists kept verbatim; `LexicalException` / `SyntacticException` messages; the 1024-byte lexeme cap; iterative destruction for deep trees; public `BooleanTree::front/back/pop_front/pop_back/empty/size` (exposed `stack_output`), `Parse()`, `root`, node class layout (`getLeftNode`, `getId`, `release_children`).

## API-compat hazards

- **boolean-parser implicit OR is emitted too late (behavior, not perf).** In `toRPN`, the default operator is pushed *after* the following Id has been output, so `a & b c` parses as `a OR (b AND c)`, not `(a AND b) OR c`; `x AND a b` likewise. A correct implicit-OR chain (`a b c`, `a OR b c`) works. I found this by fuzzing my precedence-climbing comparator against the library (20000 random expressions, 3-7 terms; all diffs involved implicit OR after a binary operator or before NOT/`(`). Any rewrite must either preserve the quirk or the owner must decide to fix it; tests built from random expressions must avoid it. Also right-associative (`a AND b AND c` is `a AND (b AND c)`) because `toRPN` pops only strictly tighter operators; `NOT` after an Id with no operator (`a NOT b`) is a syntax error.
- **boolean-parser exposes internals:** `stack_output` is a public-ish `std::list<Token>` via `front()/back()/pop_*`, and the demo drains it; `Token` is a class with `std::string` lexeme. Changing the container is source-visible.
- **url-parser:** `QueryParser::off`/`len` and `PathParser::off_*`/`len_*` are public data members pointing into internal buffers; `get()` computes `off - query.data() + query_decoded.data()`, so both buffers must keep identical length and layout. Any one-pass fill must preserve that. `QueryParser::init` stores the separator-coded string with `\1` for `=` and `\0` for `&`.
- **url-parser is not a general URL parser:** it is Xapiand's path/query dialect (`:command`, `@host`, `{selector}`); ada is only a comparator for `percent_decode` and as a scale reference. `url_parser.cc` includes `chars.hh` (char-classify) and has its own copy of `normalize_path`.
- **http-parser** is Joyent 2.7.1 with C API/ABI (bitfield layout of `struct http_parser`, `http_parser_settings`, `HTTP_PARSER_STRICT`, `http_parser_parse_url`); keep the struct layout. It is compiled as C++ and pulls in enum-reflection for its `ENUM()` tables, so enum.h's compile-time cost lands in every consumer TU.
- **enum-reflection:** name lookup is **case-insensitive** (`hhl` is FNV-1a over lowercased bytes) and verified only by the 64-bit hash, so `enum_type<Color>("RED")` returns `Color::Red`, and a different-case duplicate member name would collide. Near-miss probes accepted as valid in my run (2/251 at 32 members, 6/1004 at 128, 0/63 at 8) were all case-only variants. `enum_type` throws on a miss (2.3-2.9 µs). `enum_find(value)` is `constexpr` and builds its PHF per call site.
- **radix-router:** `Params` holds `string_view`s into the pattern and the looked-up path; `Router::find` clears params first. Keep that contract.

## Notes on comparators and voids

- ada: `ada::unicode::percent_decode` (built from ada's single-file `ada.cpp`). Different `+` semantics, so rows use `+`-free input; first run had a mismatch from `%2B` decoding to `+` (ada) vs `' '` (ours), fixed in the input generator, not by loosening the check.
- llhttp 9.4.3 (brew) and Joyent 2.7.1 returned identical method, URL bytes, header field bytes, header value bytes and body bytes on all 8 workloads. The pico-style scanner (one-shot, no validation, no streaming, `memchr`) is a ceiling and was only checked on the 5 non-chunked, non-pipelined workloads; it returned identical totals.
- Router comparators: `absl::flat_hash_map<string,int>` exact match is not a router (no params) and is shown only as the floor for static hits (5 ns); the segment trie is my own comparator and agrees with the radix tree on values and param counts on all lookups (tables are chosen so no backtracking is needed). boost has no HTTP-style path router, so there is no boost row.
- enum-reflection comparators: dense array index, sorted binary search, linear scan (magic_enum's method for string to enum), and `absl::flat_hash_map<string_view,E>`. magic_enum itself was not available locally; I did not add a dependency. Identity of all four against `enum_name`/`enum_type` was checked on every member.
- boolean-parser comparator: my own precedence-climbing parser with an arena; identity is the canonical prefix dump, checked on all timed inputs (random inputs avoid the implicit-OR quirk, see hazards).
- Absolute magnitudes: the 128-term and 1024-term boolean rows have bytes/ns around 0.1 GB/s for ours; the typical query costs 0.6 µs, which matters only if queries are parsed per request.

## LESSONS

The lessons of this survey are in [LESSONS.md](../LESSONS.md): [url-parser](../LESSONS.md#url-parser),
[http-parser](../LESSONS.md#http-parser), [boolean-parser](../LESSONS.md#boolean-parser),
[enum-reflection](../LESSONS.md#enum-reflection). Two points are recorded only here:

- **A tree-per-segment radix router with a first-byte index is already at the speed of hash-based segment tries;** the data structure was the right choice and the remaining gap (1.3-1.7x on very large param tables) is allocation/`vector` bookkeeping, not algorithmic.
- **Compile-time perfect hashing (PHF + switch) turns enum name lookup into 3 ns,** faster than a hash map and 5-20x faster than a linear scan; the price is paid in the preprocessor (about 23 ms per enum member). Preprocessor recursion that repeats the full member list six times scales linearly with members but with a large constant.
