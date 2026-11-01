# Survey A: text/bytes

- Date: 2026-10-30. Kind: cluster survey of the October 2026 performance and correctness work (read-only; cluster A, text).
- Repos: the default branches before the work began: `strings:62fb121`, `strict-stox:f0f7374`, `escape:f4efd99`,
  `repr:2063945`, `stringified:c8c9033`, `char-classify:a890496`, `split:27dbc41`, `unicode:d80b6bb`, `endian:a625b94`,
  `math:2730483`, `utype:6e2c2a8`, `static-string:e0a3d6e`.
- Machines: Apple M4 Pro (recorded in the survey as "Apple Silicon arm64"). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| A-W1 strings `lower`/`upper` | landed | `strings:f2413ff` | `strings_diff` |
| A-W2 strict-stox clean-input fast path (ints, then `stod`/`stof`) | landed (integers and short decimals first, the table-driven `stod`/`stof` without a new dependency second) | `strict-stox:70b8325`, `strict-stox:199e0be` | `strict_stox_diff`, `strict_stox_fp` |
| A-W3 escape/repr exact size and block copy | landed (the shared 16-byte kernel followed in `char-classify:d670574`) | `escape:711fe8d`, `repr:3191c08` | `escape_diff`, `repr_diff`, `chars_escape_kernel` |
| A-W4 repr `max_size` skips the elided middle | landed | `repr:3191c08` | `repr_diff`, `repr` (`test_tiny_max_size`) |
| A-W5 stringified moves the rvalue string | landed | `stringified:d8a7726` | `stringified` (regression test on `data()`) |
| A-M1 char-classify `tolower` arithmetic | not pursued: `chars::tolower` keeps its 256-entry table on `main`; the bulk case went to arithmetic in `strings::lower`/`upper` (`strings:f2413ff`) and to `chars::simd::ascii_lower`/`ascii_upper` (`char-classify:d670574`) | - | - |
| A-M2 strings `join` (strings and integers) | landed | `strings:f2413ff` | `strings_diff` |
| A-M3 strings `replace` in one pass | landed | `strings:f2413ff` | `strings_diff` |
| A-M4 strings `indent` | landed as a behavior fix (Python `textwrap.indent` semantics; its speed was not recorded) | `strings:bb85615` | `strings_fix` |
| A-M5 unicode `next_utf8` ASCII fast path | landed (per code point, eight-byte ASCII window; the bulk helper was measured and not landed, see [LESSONS](../LESSONS.md#unicode)) | `unicode:7c7d6ad..2e5d92a` | `unicode_diff` |

The API-compat hazards below have no Resolution rows. The `indent`, `hasupper`, `stringified` copy/move/`c_str()` and
63-byte truncation hazards were fixed as behavior changes (`strings:bb85615`, `stringified:1c1fb3e`, `strict-stox:7d7f5dd`);
[UPGRADING-2026-10.md](../UPGRADING-2026-10.md) lists them for consumers. The strings regressions on small inputs that the
`join`/`replace` changes introduced are CR4 of the [text audit](2026-10-31-audit-text.md).

Host: Apple M4 Pro (arm64), Apple clang 17, `-O3 -std=c++20`, abseil 20260817 (Homebrew), fast_float (a local checkout).
Bench: one cluster harness with sections `text|strings|stox|unicode` (harness not kept; the repo benches of strings,
strict-stox, escape, repr and unicode carry these comparators).
Method: best of 7 samples of ~8 ms each, ours / comparator / ours again (A/A column = spread between the two ours runs).
Every row checks the comparator returns identical results; "NO(void)" rows are not used for ranking.
Ratio = ours/comparator, so >1 means we are slower. ns are per call unless the lib column says per-element (stox, unicode,
char-classify rows are per element/byte). `proto` comparators are 30-line prototypes in the harness (prototype not kept; no new deps).

## Table

| library | workload | ours | best comparator | ratio (A/A) | diagnosis | win | effort | verdict | outcome |
|---|---|---|---|---|---|---|---|---|---|
| strings | `lower/upper(string_view)` 256 B / 4 KB | 534 ns / 7.5 us | absl::AsciiStrToLower 117 ns / 1.18 us | 4.6x / 6.4x (2-4%) | `std::transform` into `back_inserter` on an empty string: a `push_back` per byte (capacity check + possible realloc), no vectorization; also a 256-entry table lookup per char | 5-6x | S | **CLEAR WIN** | A-W1 |
| strings | `inplace_lower` 4 KB | 1.09 us | absl in-place 1.21 us | 0.90 (2%) | table lookup per byte; absl uses same idea | none | - | already good | - |
| strict-stox | `strict_stoi` nothrow, 1-9 digits | 21 ns | std::from_chars 5.4 ns | 3.9x (3%) | per call: zero-init 64 B stack buffer, `strncpy`, `errno` thread-local read/write x3 (via `__error()`), `strtol` (locale-aware, accepts ws/+/prefix), then a range check | 3-4x | S-M | **CLEAR WIN** | A-W2 |
| strict-stox | `strict_stoull` 1-19 dig / `stoul` base 16 | 24 ns | from_chars 8.4 / 7.9 ns; SimpleHexAtoi 6.7 | 2.9x / 3.1x (3-5%) | same | ~3x | S | CLEAR WIN (same fix) | A-W2 |
| strict-stox | `strict_stod` / `stof` | 25.5 / 26 ns | fast_float 10.6 / 13.0 ns | 2.4x / 2.0x (1-2%) | same overhead on top of `strtod` (which is itself ~15 ns); absl::SimpleAtod is 20.7 ns (1.2x) | 2.4x | S | CLEAR WIN (same fix; fast_float is a dependency issue, see hazards) | A-W2 |
| escape / repr | `escape` text 16 B-64 KB (printable) | 1.3 ns/B (29 ns@16, 5.4 us@4 KB) | proto LUT+run-copy 0.64 ns/B; absl::CEscape 0.54 ns/B (output differs: void) | 1.9-2.1x (3-18%) | `ret.resize(4n+2)` zero-fills 4x the input then shrinks; per-byte `switch` with a branchy 4-way classify and one byte-store at a time | ~2x | S | **CLEAR WIN** | A-W3 |
| escape / repr | mixed (10% non-printable) | 340 ns@256, 98 us@64 KB | proto 242 ns, 70 us | 1.4-1.5x | same | 1.4x | S | (same fix) | A-W3 |
| escape / repr | binary (all `\xNN`) | 5.6 us@4 KB | proto (run-copy) 7.6 us | 0.73x | already fine; a run-copy prototype is *slower* here, so keep a per-byte path for escapes | none | - | already good (do not regress) | - |
| repr | `repr(p, n, friendly, q, max_size=64)` on 4 KB / 64 KB | 1.9 us / 30 us | escape of 64 B: 107 ns | 18x / 289x (2-10%) | the elided middle is still walked byte-by-byte (compare per byte); cost is O(n) instead of O(max_size) | 18-290x for large inputs | S | **CLEAR WIN** (algorithmic) | A-W4 |
| repr | `friendly=false` 4 KB-64 KB | 0.29 ns/B | proto hexall 0.46 ns/B | 0.63-0.76 | table-driven already | none | - | already good | - |
| char-classify | `char_repr` hex-encode | 0.26 ns/B | absl::BytesToHexString 0.25 | 0.97-1.0 | LUT of 2-byte pairs; matches | none | - | already good | - |
| char-classify | `is_alpha` / `is_hexdigit` count over 64 KB | 0.2 ns/B | absl::ascii_isalpha 0.2, std::isalpha 0.4, arithmetic 0.1 | 1.0 / 1.24 | 4-byte table lookup, flags in one word; fine | <1.3x | - | already good | - |
| char-classify | `tolower` loop, 64 KB | 0.2 ns/B | arithmetic `c+32 if upper` 0.03 ns/B | 6.8x (5%) | a 256-byte table lookup per byte blocks auto-vectorization; the arithmetic form vectorizes | 6x on bulk loops | S | maybe (single-char use unchanged; mostly matters through `strings::lower/upper`, which the strings fix covers) | A-M1 |
| char-classify | `hexdec` 4 KB bytes | 1.5 ns | arithmetic nibble 0.7 ns | 2.3x (3%) | two-table lookups plus sentinel checks and `*ptr` store per byte | 2x of a tiny cost | S | not worth it | - |
| split | `strings::split(char)` / iterator / `"::"` / `find_first_of`, 1 KB and 64 KB | 0.82 us / 54 us | absl::StrSplit 1.0 us / 73 us; hand memchr 0.82 / 54 | 0.68-0.81 (vs absl); 1.0 (vs memchr) | `std::string::find` -> memchr; already at the hand-written floor | none | - | already good (beats absl) | - |
| strings | `join(vector<string>)` 10 / 1000 elems | 73 ns / 4.3 us | absl::StrJoin 34 ns / 2.7 us | 2.1x / 1.6x | no `reserve`: appends grow the string repeatedly; reverse-iterator + `std::to_string` per element; `join` with predicate also builds a full-size filtered copy | 1.6-2x | S | maybe | A-M2 |
| strings | `join(vector<int>)` 1000 | 13.6 us | absl::StrJoin 9.2 us | 1.5x | `std::to_string(int)` makes a temporary string per element, no reserve | 1.5x | S | maybe (fold into the join fix) | A-M2 |
| strings | `replace` 1 -> 3 chars, 256 B / 4 KB | 35 ns / 1.28 us | absl::StrReplaceAll 63 ns / 0.70 us | 0.55x / 1.83x | repeated `std::string::replace` shifts the tail on every hit: O(n x matches) once the match count is large | 1.8x at 4 KB, grows with size | S | maybe | A-M3 |
| strings | `indent`, 200 lines | 3.7 us | manual find/append 2.2 us (not identical, see hazards) | 1.68x (void) | `Split` iterator with look-ahead + `result.reserve` too small (reserves `lines*level` but the content is appended, so it still grows) | ~1.7x | S | maybe (semantics change risk, see hazards) | A-M4 |
| strings | `trim`, `startswith/endswith`, `format` | 5.3 ns, 0.7 ns, 90 ns | absl 4.0 ns, 0.7 ns, std::format 92 ns | 1.31 / 1.04 / 0.98 | `find_first_not_of` with a 6-char set; wrapper over `std::vformat` costs nothing | none | - | already good | - |
| strings | `hasupper` 4 KB | 0.4 ns/B | range loop 0.3 ns/B | 1.5x | calls libc `isupper` (locale-dependent) | small | - | not worth it (but locale hazard) | - |
| strings | `from_bytes` | 87 ns | snprintf 60 ns (not identical, void) | n/a | `long double` `log`/`pow`/`round` + `std::format("{}", double)` | n/a | - | not worth it (cold, formatting for humans) | - |
| stringified | `stringified(std::string&&)` 4 KB | 120 ns | `std::string` move 60 ns | 2.0x (15%, noisy) | `_str(str)` copies: the named rvalue-reference parameter is an lvalue, so the std::string is copied, not moved | 2x on large strings | S (one `std::move`) | CLEAR WIN, tiny (but fix has dangling-view interplay, see hazards) | A-W5 |
| unicode | `tolower` / `category_of` (`is_letter`) over 64 K code points | 0.4 ns (ASCII), 0.4-0.5 ns (mixed) | ASCII fast path + table 0.3 / 1.4 ns | 1.2-1.3x (ASCII), 0.3x (mixed) | two-stage table, branch-free; faster than an ASCII-first branch on mixed text | none | - | already good | - |
| unicode | `next_utf8` decode | 0.7 ns/cp ASCII, 1.2 ns/cp mixed | ASCII-branch-first 0.3 ns, 8-byte ASCII-run skip 0.1 | 2.5x-7x on pure ASCII, 0.5x on mixed (branch-first is slower on mixed) | the leading-byte ladder runs three range compares before falling through to the 1-byte case | up to 7x on pure ASCII bulk decode | S | maybe (only if a bulk decode API is added; per-cp API is fine) | A-M5 |
| unicode | `append_utf8` | 1.8 / 3.6 ns/cp | same with `reserve` | 1.00 | one `push_back` per byte, no reserve | none | - | already good | - |
| endian | `htobe*`/`bswap*` macros | - | `__builtin_bswap*` | - | macros resolve to compiler builtins on clang/gcc (reviewed, one `rev` instruction) | none | - | already good (not benchmarked: nothing to measure) | - |
| math | `modulus`, `add`, `sub`, `min/max<T>` | - | - | - | trivial scalar code; `add/sub` overflow checks `x + y < x` are UB for signed T (hazard) | none | - | not worth it | - |
| utype | `toUType` | - | `static_cast` | - | zero-cost `constexpr` | none | - | already good | - |
| static-string | compile-time concat | - | - | - | `constexpr` types resolved at compile time; no runtime path to optimize | none | - | not worth it | - |

## CLEAR WINs

### 1. strings `lower`/`upper` (string_view and rvalue-string overloads)
- Start files: `strings:strings.hh` (`lower`, `upper`, `inplace_lower`, `inplace_upper`); `char-classify:chars.hh` (`tolower`/`toupper`).
- Single biggest change: size the result up front (`result.resize(str.size())` or `std::string result(str)`) and transform in place. Replace the 256-byte table in `chars::tolower/toupper` with the arithmetic form `c + ((unsigned char)(c - 'A') < 26) * 32`, which the compiler vectorizes (6.8x on bulk loops, measured).
- Must stay identical: ASCII-only mapping, bytes >= 0x80 unchanged, `constexpr`-ness and `noexcept` of `chars::tolower/toupper`, function signatures and overloads (`lower(string&&)` returning by move).
- Expected: lower/upper(string_view) 4.6-6.4x faster, reaching or beating `absl::AsciiStrToLower`.

### 2. strict-stox (`strict_stoi/stoul/stoull/stod/stof...`)
- Start file: `strict-stox:strict_stox.hh` (`Stox::_stox`).
- Single biggest change: a fast path for the common clean input (optional `-`, ASCII digits, end of string) using `std::from_chars` (ints) and a small in-header decimal parser or `strtod` only for floating point; fall back to the existing `strtox` path for anything else (leading whitespace, `+`, `0x` prefixes, base 0, overflow, trailing junk with `idx`). Drop the 64-byte `char buf[64]{}` zero-init and `strncpy` by passing a NUL-terminated copy only on the fallback path.
- Must stay identical: error semantics (EINVAL/ERANGE strings in the throwing form, `errno_save` contents, `idx` position, `errno` preserved across calls), accepted syntax (`strtol` accepts leading whitespace, `+`, and `0x`/octal prefix for base 16/0; `from_chars` does not), truncation to 63 bytes, results for all types listed (`stoi` range-checks against `int`, `stou` unsigned, etc.). Decide explicitly whether the 63-byte truncation is a feature.
- Expected: 3-4x for ints, ~2.4x for doubles (floating point must stay correct to the last bit; `strtod` is correctly rounded, so a fast path must be too: fast_float is correctly rounded but is a new dependency; the leaf-library rule forbids it. Implement an Eisel-Lemire fast path from the paper or keep `strtod` and only remove the wrapper overhead).

### 3. escape / repr (shared loop)
- Start files: `escape:escape.cc`, `repr:repr.cc`, `char-classify:chars.hh` (`char_repr`).
- Single biggest change: stop zero-filling a 4n+2 buffer (`ret.resize(size)` then `resize(d - buff)`): compute the exact length in a first pass with a 256-entry length table (1/2/4 per byte, quote-aware), `resize` once, and copy runs of printable bytes with `memcpy`. Keep the per-byte path for escape-heavy input (a pure run-copy loop was 1.3x *slower* on binary in the bench; use a hybrid: run-copy only when the next 8 bytes are printable).
- Must stay identical: output bytes, including lower-case hex, `\\`, `\n`, `\r`, `\t` escapes, quote handling (`'\0'` none, `'\1'` means `'`), and the `max_size` 2/3-1/3 elision with `...`. `repr(friendly=true)` == `escape`: `repr` should call the shared core.
- Expected: ~2x on printable text, 1.4x mixed, 0 on all-binary (already fine).

### 4. repr with `max_size` on large inputs
- Start file: `repr:repr.cc`.
- Single biggest change: when `max_size != 0`, after emitting the head and the `...`, jump `q` directly to `max_b` instead of testing every elided byte. Cost becomes O(max_size) instead of O(n).
- Must stay identical: exact output, including the boundary conditions at `max_a`/`max_b` (the `q++` pre-increment makes the comparisons off by one: copy the existing arithmetic exactly and test with sizes around `max_size`).
- Expected: 18x at 4 KB, ~290x at 64 KB (30 us down to ~0.1 us).

### 5. stringified(std::string&&)
- Start file: `stringified:stringified.hh`.
- Change: `_str(std::move(str))`. Tiny win (2x on large strings) but see the dangling-view hazard: the `_str_view(_str)` must be set after the move (it is, member order), but the move constructor of `stringified` itself has the SSO problem below.

## Maybes (small, mechanical; bundle with #1)
- `strings::join`: `reserve` the total size up front (sum of element sizes + delimiters), iterate forward, avoid `std::to_string` temp for integer types (use `std::to_chars` into the result buffer); drop the filtered-copy in the predicate overload. 1.5-2x.
- `strings::inplace_replace`: build the result out of place (single pass) when there is more than one match.
- `strings::indent`: see hazard; if the dropped-blank-line behavior is not intended, a find-based loop is ~1.7x.
- `unicode::next_utf8`: if a bulk decoder is ever needed, add an ASCII fast path; per-code-point cost is already ~1 ns.

## API-compat hazards found while reading
- **`strings::indent` drops blank lines and the trailing newline**: `indent("a\n\nb\n", ' ', 2)` returns `"  a\n  b"` (verified). `Split` with default `skip_blank` skips empty fields. Any optimization must either preserve this or the change is a behavior change the owner has to approve.
- **`stringified` move constructor**: `_str_view(std::move(v._str_view))` copies a view that points into the source's `_str`. For a short (SSO) string the view then points into the moved-from object's inline buffer, which is dangling in the new object. Move-assignment has the same issue. (Not changed; report only.)
- **`stringified::c_str()`** reads `_str_view.data()[size()]` to test for a NUL terminator. For a `string_view` that is not NUL-terminated and ends at the end of a mapping, that is a one-byte out-of-bounds read.
- **`stringified(const stringified&)`** copies only the view, not `_str`; the copy dangles if the source dies first.
- **strict-stox**: `strtol`-based semantics are broader than `from_chars` (leading whitespace, `+`, base prefixes, locale decimal point in `strtod`), and long inputs are truncated at 63 bytes (a 64+-character numeric string with an `idx` out parameter silently parses a prefix). `errno` is saved/restored by the wrapper, which a rewrite must keep. `Stox` statics are non-const global objects (`static Stox<...> _strict_stoi` in a header): one per TU.
- **`strings::hasupper`** uses libc `isupper` (locale-dependent for bytes >= 0x80 on some libcs); `chars::` functions are ASCII only.
- **`strings::format`** swallows all exceptions and returns the raw format string on error.
- **`strings.hh` injects overloads into `namespace std`** (`std::to_string` for strings and objects): technically UB, and it is relied on by `join`. Leave as is.
- **`Split<>`** inherits from `std::iterator` (deprecated in C++17, removed-warning on clang 17), the iterator holds a pointer to the `Split` object: iterating a temporary `Split(...)` in a range-for over a *prvalue string* is fine only because `str` is stored by value; keep.
- **`math::add/sub`** use `x + y < x` as the overflow check, which is UB for signed `T`.
- **`chars::hexdigit`** returns `0xffffffff` (`NO_HEXDIGIT`) for non-hex; `hexdec` returns -1 and leaves the pointer untouched on failure; both are part of the API.
- **`repr/escape`** `assert(quote ...)` is the only validation; any other quote char is treated as no-quote-escape but still emitted.

## LESSONS

The lessons of this cluster are in [LESSONS](../LESSONS.md): [repr](../LESSONS.md#repr), [escape](../LESSONS.md#escape),
[strings](../LESSONS.md#strings), [strict-stox](../LESSONS.md#strict-stox), [stringified](../LESSONS.md#stringified),
[char-classify](../LESSONS.md#char-classify), [unicode](../LESSONS.md#unicode). Two points of the survey are not there:

- **Do the cheap thing first on the common input, in front of the general decoder.** The table-driven two-stage lookups (`unicode`) and `memchr`-backed `split` are already at the floor; the gaps were all in the glue (allocation, zero-fill, errno), not the core algorithms.
- **Local `constexpr` tables inside inline functions (`chars::tolower`) are fine under clang -O3 (they land in rodata), but they make the function's cost model depend on the optimizer.** Prefer one `inline constexpr` namespace-scope table.
