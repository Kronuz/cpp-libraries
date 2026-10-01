# AGENTS.md: Kronuz C++ Libraries

The agent-facing reference for the C++ library collection under
[github.com/Kronuz](https://github.com/Kronuz). The human overview is in `README.md`; this
file is the working detail: every library, its real API, how it works, and the rules for
changing one.

If you are an agent doing C++ work in this ecosystem, read "Rules of engagement" and "Pick
by task" before you write anything.

## What this is

About sixty small, standalone C++ libraries, each in its own public repository under
[github.com/Kronuz](https://github.com/Kronuz). They were extracted from
[Xapiand](https://github.com/Kronuz/Xapiand), a distributed RESTful search engine, over
roughly a decade of building it. Whenever a piece grew sharp enough and self-contained
enough to stand alone, it was carved out, given a README and a test suite, and released.

They are not a framework. There is no umbrella header, no common runtime, and no
registration step. Each library is one idea with a narrow surface, and most are
header-only. You take the two you need and ignore the rest.

**Treat this document as the starting point for any C++ work in this ecosystem.** Before
writing a thread pool, a timer wheel, an LRU cache, an HTTP parser, a perfect hash, a
geospatial index or a string utility, check the index below. Most of it already exists
here, already has tests, and is already used in production by at least one real system.

## Rules of engagement

Read this section before changing anything.

1. **Use whatever fits.** Every library here is available to you. Prefer reusing one over
   writing an equivalent from scratch. Prefer composing several over building a monolith.
2. **These are our libraries.** You may modify them. You do not need to work around a
   limitation, vendor a patched copy, or reimplement a piece because it is slightly wrong.
   Fix it at the source.
3. **Preserve the public API and on-disk/on-wire compatibility.** Other applications
   depend on these, and several of them are not in front of you. Adding is safe. Renaming,
   removing, reordering an enum, changing a default, or altering a serialization format is
   not. If a breaking change is genuinely the right answer, say so explicitly and call it
   out rather than slipping it in.
4. **You have real freedom inside that constraint.** Optimize the implementation, fix
   bugs, improve diagnostics, tighten types, add tests, extend documentation, and add new
   capabilities as additive and modular pieces: a new overload, a new policy parameter, a
   new optional header. That is all encouraged.
5. **Keep them small.** The value of each library is that it does one thing and pulls in
   almost nothing. Do not add a dependency to a leaf library for convenience. Do not grow
   a general-purpose abstraction layer inside a library that currently has none. If an
   addition would make the library harder to drop into an unrelated project, it belongs in
   the caller instead, or in a new library.
6. **Match the local conventions.** Each repo has a README, a test suite, usually an
   `examples/demo.cc`, and a CMakeLists with an explanatory comment on every dependency.
   Keep all four current when you change something.

## Consuming a library

The convention is uniform across the collection. Each repo exposes a CMake target named
`<name>::<name>` (dashes become underscores, so `char-classify` gives
`char_classify::char_classify`), and pulls its own first-party dependencies through
`FetchContent`. You link one target and the whole transitive header set lands on your
include path.

```cmake
include(FetchContent)
FetchContent_Declare(hashes
  GIT_REPOSITORY https://github.com/Kronuz/hashes.git
  GIT_TAG        main)
FetchContent_MakeAvailable(hashes)

target_link_libraries(my_app PRIVATE hashes::hashes)
```

Facts worth knowing before you wire anything up:

- **Most are header-only** (`INTERFACE` targets). A minority compile a `.cc`: `repr`,
  `strings`, `htm`, `sha256`, `compressors`, `cartesian`, `traceback` and a few others.
  Either way, linking the target is the correct move.
- **C++20 is the norm**, C++17 for a handful (`constexpr-phf`, `uinteger_t`, `base-x`,
  `lru-cache`, `split`, `static-string`, `cpp-btree`, `located-exception`).
- **The include filename often differs from the repo name.** `char-classify` gives
  `chars.hh`, `constexpr-phf` gives `phf.hh`, `enum-reflection` gives `enum.h`,
  `lru-cache` gives `lru.h`, `errno-names` gives `errnos.h`, `iterators` gives
  `itertools.hh`, `located-exception` gives `exception.h`. Each entry below states the
  real include line.
- **Tests and demos only build when the repo is the top-level project**, so pulling a
  library into your build does not build its test suite.
- **`GIT_TAG main` tracks the tip.** For anything reproducible, pin a commit SHA.
- **Licensing is MIT** across the collection, with `cpp-btree` under Apache 2.0.
- **Third-party dependencies are rare and localized.** The networking stack wants
  standalone Asio; `compressors` wants zlib, lz4 and zstd; `hashes` optionally detects an
  xxHash header and falls back to its own implementation when absent.

## Pick by task

| You need | Use |
| --- | --- |
| Classify or case-fold ASCII, no locale | `char-classify` |
| Join, split, trim, pad, humanize bytes/durations | `strings` |
| Split without allocating | `split` |
| Log bytes that may contain control characters | `repr`, `escape` |
| Accept "anything string-like" as one parameter | `stringified` |
| Parse a number and reject trailing junk | `strict-stox` |
| Compile-time string type, concatenation | `static-string` |
| Defer an expensive log argument | `lazy` |
| Enum to its underlying integer | `utype` |
| Modulo of negatives, saturating add/sub | `math` |
| Byte-order conversion, including 56-bit | `endian` |
| Hash a string at compile time, switch on it | `hashes` |
| O(1) dispatch over a fixed integer key set | `constexpr-phf` |
| Fixed word set to index, no hashing | `ctrie` |
| Enum to string and back, generated | `enum-reflection` |
| Integers wider than 64 bits | `uinteger_t` |
| Base58/62/64/32 encoding, checksums | `base-x` |
| UUIDs with a compact wire form | `cuuid` |
| MD5 / SHA-256 digests | `md5`, `sha256` |
| Random values, jitter, test data | `random` |
| Probabilistic membership, bounded memory | `bloom-filter` |
| Bounded cache with LRU and TTL | `lru-cache` |
| Cache invalidated wholesale on a write/version change, not per-entry | `generation-cache` |
| Ordered map/set with better locality than `std::map` | `cpp-btree` |
| Fixed-size worker pool | `threadpool` |
| Bounded blocking MPMC queue | `queue` |
| Cancellable delayed tasks, debounce | `scheduler` |
| The lock-free slot store under a timer wheel | `stash` |
| Atomic operations over `shared_ptr` | `atomic-shared-ptr` |
| Custom allocators, memory pools | `allocators` |
| Precise sleep, EINTR-safe | `nanosleep` |
| Current time since epoch | `epoch`, `times`, `time-point` |
| Parse and format ISO-8601, date math | `datetime` |
| EINTR-safe read/write, safe fd handling | `io` |
| mkdir -p, glob delete, directory copy | `fs` |
| fd counts, RAM, disk and inode usage | `system` |
| TCP/UDP reactor pool, graceful shutdown | `reactor` |
| Generic connection server engine | `server` |
| HTTP/1.1 application framework | `http` |
| Streaming HTTP/1.x parser only | `http-parser` |
| Access logging middleware | `http-log` |
| Route paths with named parameters | `radix-router` |
| Parse URLs and query strings | `url-parser` |
| deflate / lz4 / zstd in memory | `compressors` |
| Send a file over a byte channel, framed and checked | `flume` |
| Append-only compressed blob store | `storage` |
| MessagePack values, copy-on-write | `msgpack` |
| Multicast bus, Raft, membership gossip | `cluster` |
| Geodetic to geocentric coordinates | `cartesian` |
| Spherical spatial index over the whole planet | `htm` |
| Phonetic matching of names | `double-metaphone`, `soundex` |
| Edit distance, Jaro-Winkler, similarity | `string-similarity` |
| Parse a boolean query expression | `boolean-parser` |
| Deferred, lock-free logging | `logger` |
| ANSI color with graceful downgrade | `term-color` |
| Stack traces, crash handlers | `traceback` |
| Exceptions that capture the throw site | `located-exception` |
| errno to its symbolic name | `errno-names` |
| A worked example of the whole stack | `prism` |

## How they layer

Dependencies run one way and stay shallow. Thirty-two libraries pull nothing
first-party at all.

```
leaves        char-classify  static-string  split  strict-stox  stringified  endian
              constexpr-phf  ctrie  uinteger_t  utype  math  io  stash  threadpool
              queue  reactor  radix-router  compressors  cartesian  lru-cache
              generation-cache  ...

utilities     repr -> char-classify          escape -> char-classify
              strings -> char-classify, repr, split, static-string, term-color
              term-color -> static-string    hashes -> char-classify, static-string
              base-x -> uinteger_t           md5/sha256 -> endian

services      enum-reflection -> constexpr-phf, hashes
              scheduler -> stash, threadpool          logger -> scheduler, term-color
              http-parser -> enum-reflection          storage -> compressors, ...
              traceback -> errno-names, nanosleep, strings, term-color

stack         http     -> compressors, http-parser, radix-router, reactor
              http-log -> http, logger, repr, strings
              prism    -> http, http-log, logger, traceback
```

`prism` is the worked example: a small HTTP application server assembled from the
libraries above. Read it first if you are building a service.

---

## The libraries

Entries state the real include line, the CMake target, the C++ standard, first-party
dependencies, how the thing actually works, the key API, a short example, and when not to
reach for it. The "do not use it when" bullets are the load-bearing ones; read them.

## Foundations: bytes, strings, parsing

*The bottom of the stack. Almost everything else depends on some of these.*

### char-classify
[github.com/Kronuz/char-classify](https://github.com/Kronuz/char-classify) &middot; depends on: none
- **What it is:** Header-only constexpr classification and case folding for ASCII bytes, with no locale and no `<cctype>`.
- **Header / target:** `#include "chars.hh"`; target `char_classify::char_classify`; C++20.
- **How it works:** A constexpr 256-entry table packs character properties and hex values into bit fields, so every query is one indexed load and a mask. All classification and case conversion helpers are inline constexpr, which makes them usable inside constant expressions and inside other constexpr parsers. `char_repr` produces an escaped printable form for a single byte.
- **Key API:**
  - `is_space`, `is_alpha`, `is_upper`, `is_digit`, `is_alnum`, `is_ascii`, `is_keyword`, `is_hexdigit`
  - `hexdigit(char) -> unsigned`, `hexdec(const char**) -> int`
  - `tolower(char)`, `toupper(char)`
  - Flags: `IS_SPACE`, `IS_ALPHA`, `IS_UPPER`, `IS_DIGIT`, `IS_HEX_DIGIT`, `IS_ASCII`, `IS_KEYWORD`, `IS_NON_HEX`
- **Example:**
  ```cpp
  #include "chars.hh"

  static_assert(is_digit('7'));
  static_assert(hexdigit('A') == 10);
  constexpr char c = toupper('x');
  ```
- **Use it when:**
  - Parsing ASCII protocol syntax where locale must not matter.
  - Classifying bytes inside a constexpr parser.
  - Decoding hex without `<cctype>`.
- **Do not use it when / gotchas:**
  - Not Unicode aware and not locale aware, by design.
  - The API is byte oriented; feed it `char`, not a decoded code point.

### static-string
[github.com/Kronuz/static-string](https://github.com/Kronuz/static-string) &middot; depends on: none
- **What it is:** A constexpr compile-time string type with concatenation and integer rendering, usable as a template argument.
- **Header / target:** `#include "static_string.hh"`; target `static_string::static_string`; C++17 (optional `std::format` support).
- **How it works:** `static_string<N, T>` stores characters in a template-selected literal or array representation, so size is part of the type. `string("...")`, `string(char)`, `to_string<N>()` and `char_to_string<c>()` build constexpr values, and `operator+` stays a `static_string` when both sides are compile-time. A `std::formatter` specialization integrates with `std::format`.
- **Key API:**
  - `static_string::static_string<N, T>`
  - `string(const char (&)[N])`, `string(char)`
  - `to_string<int>()`, `char_to_string<char>()`
  - `operator+` across static strings, literals and chars
- **Example:**
  ```cpp
  #include "static_string.hh"

  constexpr auto prefix = string("item-");
  constexpr auto name   = prefix + to_string<42>();
  static_assert(name.size() == 8);
  ```
- **Use it when:**
  - Building compile-time names, keys or format fragments.
  - Concatenating literals and integer constants during template instantiation.
- **Do not use it when / gotchas:**
  - Not a replacement for `std::string`; the length is part of the type.
  - Mixing with runtime values yields `std::string` and drops the compile-time property.

### strings
[github.com/Kronuz/strings](https://github.com/Kronuz/strings) &middot; depends on: `char-classify`, `repr`, `split`, `static-string`, `term-color`
- **What it is:** The general string utility belt: join, split, format, trim, case conversion, padding, and human-readable byte/duration formatting.
- **Header / target:** `#include "strings.hh"`; target `strings::strings`; C++20. Compiled (`strings.cc`), not header-only.
- **How it works:** Inline and compiled helpers over `std::string`, `std::string_view` and `std::vector`. `join` supports a distinct final delimiter (for "a, b and c") and an optional per-item predicate; `format` wraps `std::format` with special handling for static strings. Most transformations allocate and return a new string, while the `trim` family returns views into the caller's buffer and `inplace_*` variants mutate the argument.
- **Key API:**
  - `join(vector, delim[, last_delim][, pred]) -> string`
  - `split(const S&, const T&) -> vector<S>`
  - `format(string_view, Args&&...) -> string`
  - `left`, `center`, `right`, `indent`
  - `startswith`, `endswith`, `hasupper`
  - `upper`, `lower`, `inplace_upper`, `inplace_lower`
  - `replace`, `inplace_replace`
  - `ltrim`, `rtrim`, `trim` (return `string_view`)
  - `from_bytes`, `from_small_time`, `from_time`, `from_delta`
- **Example:**
  ```cpp
  #include "strings.hh"

  std::vector<std::string> parts{"one", "two", "three"};
  auto joined = join(parts, ", ", " and ");   // "one, two and three"
  auto fields = split(std::string{"a:b:c"}, ':');
  auto clean  = trim("  value  ");            // string_view into the argument
  ```
- **Use it when:**
  - You need the ordinary string operations C++ does not ship.
  - Rendering byte counts, durations or deltas for humans.
- **Do not use it when / gotchas:**
  - `trim` returns a view; the source must outlive it.
  - Most other helpers allocate, so avoid them on a hot path.
  - It pulls `term-color` and `repr` transitively, which is heavier than it looks.

### split
[github.com/Kronuz/split](https://github.com/Kronuz/split) &middot; depends on: none
- **What it is:** A tiny lazy string splitter that yields `string_view` fields without building a vector.
- **Header / target:** `#include "split.h"`; target `split::split`; C++17.
- **How it works:** `Split<S, T>` holds the source and the separator and exposes begin/end iterators that advance field by field, so it is a range-for adaptor rather than an eager container. Nothing is allocated and no copy of the source is made, which is what separates it from `strings::split`.
- **Key API:**
  - `template <typename S = std::string, typename T = char> class Split`
  - Iterator/range interface for range-based `for`
- **Example:**
  ```cpp
  #include "split.h"

  Split<std::string_view, char> fields{"a,b,c", ','};
  for (auto field : fields) {
      // field is a string_view, no allocation
  }
  ```
- **Use it when:**
  - Iterating delimited text once, without materializing a vector.
  - Splitting in a hot path where allocation matters.
- **Do not use it when / gotchas:**
  - Not a CSV parser: no quoting, no escaping.
  - The source must outlive the iterators and any view they produce.
  - Check the constructor form for your chosen `S`/`T` before copying the example.

### repr
[github.com/Kronuz/repr](https://github.com/Kronuz/repr) &middot; depends on: `char-classify`
- **What it is:** Turns arbitrary bytes into a single-line printable representation for logs and diagnostics.
- **Header / target:** `#include "repr.hh"`; target `repr::repr`; C++20. Compiled (`repr.cc`).
- **How it works:** Overloads accept pointer plus size, pointer ranges, strings, string views, literals and byte arrays. Printable ASCII passes through, everything else is escaped, and the result is a freshly allocated `std::string`. Options control friendly formatting, the quote character, and a maximum size for truncating large buffers.
- **Key API:**
  - `repr(const void*, size_t, bool friendly = true, char quote = '\'', size_t max_size = 0) -> string`
  - `repr(const void* begin, const void* end, ...) -> string`
  - `repr(string/string_view, ...) -> string`
- **Example:**
  ```cpp
  #include "repr.hh"

  std::string_view bytes{"ok\n\0x", 5};
  auto printable = repr(bytes);   // escaped, single line, safe to log
  ```
- **Use it when:**
  - Logging protocol or binary data that may contain control bytes.
  - Producing copy-pasteable diagnostics.
  - Truncating a large buffer for an error message.
- **Do not use it when / gotchas:**
  - Allocates on every call; not for hot paths.
  - It is a diagnostic representation, not a reversible encoding.
  - Use a size-aware overload for data with embedded NULs.

### escape
[github.com/Kronuz/escape](https://github.com/Kronuz/escape) &middot; depends on: `char-classify`
- **What it is:** C-string style escaping of a byte buffer, with a configurable quote character.
- **Header / target:** `#include "escape.hh"`; target `escape::escape`; C++20.
- **How it works:** The raw overload walks the buffer and returns an escaped `std::string`; convenience overloads take `std::string`, `std::string_view` and char arrays. `repr` is the higher-level presentation layer built on the same idea, so prefer `repr` for logging and `escape` when you specifically want quoted C-style output.
- **Key API:**
  - `escape(const void*, size_t, char quote = '\'') -> string`
  - `escape(string/string_view, char quote = '\'') -> string`
- **Example:**
  ```cpp
  #include "escape.hh"

  auto quoted = escape(std::string_view{"line\nnext"}, '"');
  ```
- **Use it when:**
  - Quoting user or protocol text for an error message.
  - Escaping control characters before writing output.
- **Do not use it when / gotchas:**
  - Escapes only; there is no unescape counterpart here.
  - Use the pointer/size overload for data that is not NUL-terminated.

### stringified
[github.com/Kronuz/stringified](https://github.com/Kronuz/stringified) &middot; depends on: none
- **What it is:** A wrapper that turns any value into a `string_view`, owning the buffer when it has to.
- **Header / target:** `#include "stringified.hh"`; target `stringified::stringified`; C++20.
- **How it works:** The constructor converts its argument to a string representation and exposes it as a `string_view`. When the source is already a string or view it borrows; otherwise it materializes and owns storage, which is what lets a single function parameter type accept both without an allocation in the common case.
- **Key API:**
  - `class stringified`, constructed from a value
  - `string_view` conversion and accessors
  - `std::formatter<stringified>`
- **Example:**
  ```cpp
  #include "stringified.hh"

  void log_it(stringified s) { /* s converts to string_view */ }
  log_it("literal");
  log_it(42);
  ```
- **Use it when:**
  - A function should accept "anything string-like" behind one parameter type.
  - Normalizing heterogeneous values to text at an API boundary.
- **Do not use it when / gotchas:**
  - Materializes eagerly; it is not lazy.
  - The view is valid only while the `stringified` object is alive.

### strict-stox
[github.com/Kronuz/strict-stox](https://github.com/Kronuz/strict-stox) &middot; depends on: none
- **What it is:** Whole-string numeric parsing that rejects trailing junk, overflow and partial consumption, unlike `std::stoi`.
- **Header / target:** `#include "strict_stox.hh"`; target `strict_stox::strict_stox`; C++20.
- **How it works:** `Stox<F>` wraps the C conversion functions and centralizes the three checks people forget: `errno`, the end pointer, and the range. Each `strict_*` function takes a `std::string_view`, optionally reports the consumed index, and has a `noexcept` overload that writes the saved `errno` instead of throwing. Integer overloads take an explicit base.
- **Key API:**
  - `strict_stoi`, `strict_stou`, `strict_stol`, `strict_stoul`, `strict_stoll`, `strict_stoull`, `strict_stoz`
  - `strict_stof`, `strict_stod`, `strict_stold`
  - `strict_*(string_view, size_t* idx = nullptr[, int base])`
  - `strict_*(int* errno_save, string_view, size_t* idx = nullptr[, int base]) noexcept`
- **Example:**
  ```cpp
  #include "strict_stox.hh"

  int err = 0;
  auto n = strict_stoi(&err, "12345");   // err == 0
  auto bad = strict_stoi(&err, "12abc"); // err set, no exception
  ```
- **Use it when:**
  - Parsing configuration, CLI arguments or protocol fields.
  - You need the `noexcept`/errno form on a path that must not throw.
- **Do not use it when / gotchas:**
  - Input is a `string_view`; the caller owns the storage.
  - Strictness is the point: whitespace and trailing characters are rejected, not skipped.

### utype
[github.com/Kronuz/utype](https://github.com/Kronuz/utype) &middot; depends on: none
- **What it is:** `toUType`, a one-function header that converts an enum to its exact underlying integer type.
- **Header / target:** `#include "utype.hh"`; target `utype::utype`; C++20.
- **How it works:** A single `constexpr noexcept` function template using `std::underlying_type_t<E>` and a `static_cast`, so nothing widens and nothing is inserted at runtime.
- **Key API:**
  - `template <typename E> constexpr std::underlying_type_t<E> toUType(E) noexcept`
- **Example:**
  ```cpp
  #include "utype.hh"

  enum class State : std::uint8_t { Idle, Running };
  constexpr auto v = toUType(State::Running);  // std::uint8_t
  ```
- **Use it when:**
  - Serializing an enum with its declared width.
  - Indexing or bit-packing without scattering casts through the code.
- **Do not use it when / gotchas:**
  - Returns the declared underlying type, which may be narrower than `int`.

### math
[github.com/Kronuz/math](https://github.com/Kronuz/math) &middot; depends on: none
- **What it is:** Integer helpers: mathematical modulo for negative values, and overflow-detecting saturating add/sub.
- **Header / target:** `#include "math.hh"`; target `math::math`; C++20.
- **How it works:** `modulus` normalizes a remainder into `[0, mod)` rather than following C++'s sign-of-dividend rule. `add`/`sub` detect unsigned wraparound, optionally report it through a `bool&`, and return the saturated bound instead of wrapping. `min<T>`/`max<T>` map an accuracy vector to representable bounds via explicit specializations.
- **Key API:**
  - `modulus(T val, M mod) -> M`
  - `add(T, T[, bool& overflow]) -> T`, `sub(T, T[, bool& overflow]) -> T`
  - `min<T>(const vector<uint64_t>&)`, `max<T>(const vector<uint64_t>&)`
- **Example:**
  ```cpp
  #include "math.hh"

  auto m = modulus(-7, 3);          // 2, not -1
  bool overflowed = false;
  auto v = add(std::uint32_t{0xffffffff}, 1u, overflowed);  // saturates
  ```
- **Use it when:**
  - Wrapping ring buffers or circular indexes with possibly negative offsets.
  - Arithmetic that must saturate rather than wrap.
- **Do not use it when / gotchas:**
  - `modulus` throws for a non-positive modulus.
  - `add`/`sub` are for unsigned types; do not rely on them for signed overflow.

### endian
[github.com/Kronuz/endian](https://github.com/Kronuz/endian) &middot; depends on: none
- **What it is:** A portability layer giving uniform byte-order macros across Linux, macOS and BSD, including 56-bit (7 byte) conversions.
- **Header / target:** `#include "endian.hh"`; target `endian::endian`; C++20.
- **How it works:** The header maps each platform's native endian and byte-swap spelling onto one set of names, filling gaps with compiler builtins or portable fallbacks. The 56-bit operations pack or unpack seven bytes and discard the eighth, which is how compact record headers fit an integer into 7 bytes.
- **Key API:**
  - `bswap16/32/64`
  - `htobe16/32/64`, `be16/32/64toh`
  - `htole16/32/64`, `le16/32/64toh`
  - `htobe56`, `be56toh`, `htole56`, `le56toh`
- **Example:**
  ```cpp
  #include "endian.hh"

  std::uint32_t host = 0x11223344;
  auto wire = htobe32(host);
  auto back = be32toh(wire);
  ```
- **Use it when:**
  - Reading or writing fixed-width integers in a wire or file format.
  - You need one spelling that compiles on macOS and Linux.
- **Do not use it when / gotchas:**
  - These are macros, not type-safe functions.
  - The 56-bit forms keep only the low 56 bits; the top byte is dropped silently.

### iterators
[github.com/Kronuz/iterators](https://github.com/Kronuz/iterators) &middot; depends on: none
- **What it is:** Lazy iterator adaptors: `transform`, `chain` and `reversed`, as range-for wrappers.
- **Header / target:** `#include "itertools.hh"`, `#include "reversed.hh"`; target `iterators::iterators`; C++20.
- **How it works:** `Transform<F, I>` stores a callable plus an iterator pair and applies the callable on dereference, so nothing is allocated and nothing is computed until iterated. `Chain<I1, I2>` holds two ranges and switches at the first one's end. `reversed` delegates to `std::rbegin`/`std::rend`.
- **Key API:**
  - `itertools::transform(F, I begin, I end)`
  - `itertools::chain(I1, I1, I2, I2)`
  - `reversed(T&& iterable)`
- **Example:**
  ```cpp
  #include "itertools.hh"
  #include "reversed.hh"

  for (auto v : itertools::transform([](int n){ return n*2; }, xs.begin(), xs.end())) {}
  for (auto v : reversed(xs)) {}
  ```
- **Use it when:**
  - You want a lightweight map or concat in a range-for and are not on C++20 ranges.
  - Iterating in reverse without copying.
- **Do not use it when / gotchas:**
  - These are forward-iterator wrappers, not conforming C++20 ranges; prefer `std::ranges` in new code that can use it.
  - `chain` requires compatible dereference types.
  - `reversed` must not outlive its iterable.

### lazy
[github.com/Kronuz/lazy](https://github.com/Kronuz/lazy) &middot; depends on: none
- **What it is:** Deferred evaluation: `eval`, `lazy_eval` and the `LAZY(expr)` macro, so an expensive argument is only computed if it is actually used.
- **Header / target:** `#include "lazy.hh"`; target `lazy::lazy`; C++20.
- **How it works:** `eval` invokes an invocable or forwards a plain value. `lazy_eval<L>` holds a reference to a callable and evaluates it on call, on explicit conversion, on stream insertion, or through its `std::formatter`. `LAZY(expr)` wraps an expression in a by-reference lambda. The canonical use is a log call whose arguments cost real work: the expression never runs if the level is disabled.
- **Key API:**
  - `eval(F&& invocable)`, `eval(Val&& value)`
  - `lazy_eval<L>`, `make_lazy_eval(L&&)`
  - `LAZY(expr)`
- **Example:**
  ```cpp
  #include "lazy.hh"

  auto snapshot = LAZY(expensive_dump());
  log_debug("state: {}", snapshot);   // expensive_dump() runs only if emitted
  ```
- **Use it when:**
  - Log or error arguments that are costly to build.
  - Deferring a computation behind a uniform callable interface.
- **Do not use it when / gotchas:**
  - `LAZY` captures by reference; everything it touches must outlive the wrapper.
  - It is deferred, not memoized: each query re-evaluates.
  - `lazy_eval` stores a reference to the callable and is non-copyable.

## Compile time, hashing, identifiers, containers

*Work done by the compiler instead of the CPU, plus hashes, ids and the container types.*

### constexpr-phf
[github.com/Kronuz/constexpr-phf](https://github.com/Kronuz/constexpr-phf) &middot; depends on: none
- **What it is:** A minimal perfect hash function for a fixed set of integer keys, computed entirely at compile time.
- **Header / target:** `#include "phf.hh"`; target `constexpr_phf`; C++17.
- **How it works:** `phf::make_phf` builds a two-level CHD-style table during constant evaluation, so the search for a collision-free assignment happens in the compiler and never at runtime. Lookup then costs a division-free multiply-shift plus one displacement load, returning a dense slot index. The keys and table live inside the resulting `constexpr` object, so there is no static initialization and no allocation.
- **Key API:**
  - `template <typename ItemType, size_t NumItems> class phf`
  - `make_phf(const ItemType (&items)[NumItems])`
  - lookup via `operator()` returning a slot, `phf::npos` when absent
- **Example:**
  ```cpp
  #include "phf.hh"

  constexpr int keys[] = {11, 42, 99};
  constexpr auto table = phf::make_phf(keys);
  static_assert(table(42) < 3);
  ```
- **Use it when:**
  - Dispatching on a fixed set of integer ids, opcodes or hashed strings.
  - Replacing a long `switch` or a linear scan with an O(1) dense index.
- **Do not use it when / gotchas:**
  - The key set must be fixed, unique and integer-like; hash strings first (see `hashes`).
  - Large or awkward key sets make compilation slow, and that cost is paid on every build.

### ctrie
[github.com/Kronuz/ctrie](https://github.com/Kronuz/ctrie) &middot; depends on: none
- **What it is:** A compile-time compressed trie mapping a fixed set of words to their insertion index.
- **Header / target:** `#include "ctrie.hh"`; C++20. Undocumented: the repo contains only the header and a CMakeLists.
- **How it works:** `ctrie::build` constructs a type-level trie from `Word` types, assigning each terminal an index in argument order, so the structure exists purely in the type system. Lookup walks character nodes and returns `ctrie::npos` for an unknown or non-terminal word. Because it is a trie rather than a hash it never needs to see the whole key when a prefix already fails, which is its advantage over a perfect hash for string dispatch.
- **Key API:**
  - `ctrie::build(Words...)`, `operator""_cword`
  - `find(const char*)`, `find(const char*, const char*)`, `find(const char*, size_t)`
  - `find(std::string)`, `find(std::string_view)`, `ctrie::npos`
- **Example:**
  ```cpp
  #include "ctrie.hh"

  constexpr auto words = ctrie::build("apple"_cword, "banana"_cword);
  static_assert(words.find("banana") == 1);
  ```
- **Use it when:**
  - Mapping a fixed vocabulary of short words to indexes with no hashing and no allocation.
  - Dispatching on keywords where early prefix rejection helps.
- **Do not use it when / gotchas:**
  - Undocumented, so treat the header as the contract and pin the commit.
  - Matching is exact, including case.

### hashes
[github.com/Kronuz/hashes](https://github.com/Kronuz/hashes) &middot; depends on: `char-classify`, `static-string`
- **What it is:** Compile-time and runtime non-cryptographic hash families (xxHash, FNV-1a, djb2) plus string-switch user-defined literals.
- **Header / target:** `#include "hashes.hh"`; target `hashes::hashes`; C++20.
- **How it works:** Every family has a `constexpr` form, which is what makes `switch (fnv1ah32(s)) { case "GET"_fnv1a: ... }` legal. The runtime xxh64/xxh32 paths defer to the real `XXH64()`/`XXH32()` when an xxHash header is detected through `__has_include`, and fall back to the portable constexpr implementation when it is not, so the fast path is opt-in without a hard dependency. `jump_consistent_hash` implements Lamping-Veach bucket assignment for sharding.
- **Key API:**
  - `xxh64::hash(...)`, `xxh32::hash(...)`
  - `fnv1ah16/32/64`, case-insensitive `fnv1ah32ci/64ci`
  - `djb2h8/16/32/64`
  - `operator""_xx`, `operator""_fnv1a`
  - `jump_consistent_hash(uint64_t, int32_t)`, `jump_consistent_hash(string_view, int32_t)`
- **Example:**
  ```cpp
  #include "hashes.hh"

  switch (fnv1ah32(method)) {
      case "GET"_fnv1a:  break;
      case "POST"_fnv1a: break;
  }
  auto shard = jump_consistent_hash(std::string_view("user-42"), 128);
  ```
- **Use it when:**
  - Compile-time string dispatch without a chain of `strcmp`.
  - Hash table keys, cache keys, or consistent sharding across N buckets.
- **Do not use it when / gotchas:**
  - None of these are cryptographic. Never use them for passwords, signatures or anything adversarial.
  - Case-insensitive variants fold through `char-classify`, so they are ASCII only.

### enum-reflection
[github.com/Kronuz/enum-reflection](https://github.com/Kronuz/enum-reflection) &middot; depends on: `constexpr-phf`, `hashes`
- **What it is:** Enum to string and string to enum conversion generated at compile time, via a perfect hash rather than a handwritten table.
- **Header / target:** `#include "enum.h"`; target `enum_reflection::enum_reflection`; C++20.
- **How it works:** The `ENUM_CLASS`/`ENUM` macros declare the enum and, from the same member list, generate constexpr name tables plus a perfect-hash lookup in both directions. Sparse or explicitly valued enumerators are supported because the value side is hashed rather than indexed. Everything resolves at compile time, so the name lookup costs no more than an array access.
- **Key API:**
  - `ENUM_CLASS(Name, Underlying, members...)`, `ENUM(Name, members...)`
  - `enum_name(Enum) -> std::string_view`
  - `enum_type<Enum>(std::string_view) -> Enum`
  - `enum_find(Enum)`, `enum_find<Enum>(std::string_view)`
- **Example:**
  ```cpp
  #include "enum.h"

  ENUM_CLASS(Color, std::uint8_t, Red, Green, Blue)
  static_assert(enum_name(Color::Green) == "Green");
  static_assert(enum_type<Color>("Blue") == Color::Blue);
  ```
- **Use it when:**
  - Config parsing, logging or serialization that needs enum names.
  - You would otherwise hand-maintain a parallel name array that drifts.
- **Do not use it when / gotchas:**
  - It generates the enum; it cannot reflect an enum declared elsewhere.
  - `enum_type` throws `std::out_of_range` on an unknown name, while `enum_name` returns an empty view on an unknown value. The asymmetry is easy to miss.

### uinteger_t
[github.com/Kronuz/uinteger_t](https://github.com/Kronuz/uinteger_t) &middot; depends on: none
- **What it is:** An arbitrary-precision unsigned integer in a single header, with base 2 to 36 parsing and rendering.
- **Header / target:** `#include "uinteger_t.hh"`; target `uinteger_t`; C++17.
- **How it works:** The value is stored in dynamically sized limbs, with full operator coverage (arithmetic, bitwise, shifts, comparison, stream output) so it behaves like a native integer where possible. Construction accepts integrals, strings in an explicit base, vectors and raw limbs. Conversions back to native types deliberately truncate to the low limb rather than throwing.
- **Key API:**
  - `uinteger_t()`, `uinteger_t(value)`, `uinteger_t(string, base)`
  - full arithmetic, bitwise and shift operators with compound forms
  - `str(int base = 10)`, `bits()`, `divmod(rhs)`, `compare(lhs, rhs)`
- **Example:**
  ```cpp
  #include "uinteger_t.hh"

  uinteger_t a("beee", 16);
  auto b = a * a;
  auto text = b.str(16);
  ```
- **Use it when:**
  - Arithmetic wider than 64 bits without pulling in GMP or Boost.
  - Base conversion of large values (this is what `base-x` uses it for).
- **Do not use it when / gotchas:**
  - No `0x`/`0b` prefix handling; pass the base explicitly. Bases outside 2 to 36 are rejected.
  - Casting to a native type silently truncates to the low limb; division by zero throws `std::domain_error`.
  - It specializes standard arithmetic type traits, which can trip diagnostics on some libc++ toolchains.

### base-x
[github.com/Kronuz/base-x](https://github.com/Kronuz/base-x) &middot; depends on: `uinteger_t`
- **What it is:** BaseX encoding and decoding for any alphabet, with ready-made Base16/32/58/62/64/66 variants including checksums.
- **Header / target:** `#include "base_x.hh"`; target `base_x`; C++17.
- **How it works:** Encoding treats the input as one arbitrary-precision integer and repeatedly divides by the alphabet size, which is why it needs `uinteger_t` and why it handles alphabets that are not a power of two (Base58, Base62). Factory structs preconfigure the common alphabets, and modifiers add case folding, a check character, a checksum or block padding.
- **Key API:**
  - `encode(...)`, `decode(...)`, `is_valid(...)`
  - modifiers: `ignore_case`, `with_checksum`, `with_check`, `block_padding`
  - factories: `Base16::base16()`, `Base32::crockford()`, `Base58::bitcoin()`, `Base62::base62()`, `Base64::url()`
- **Example:**
  ```cpp
  #include "base_x.hh"

  auto encoded = Base58::bitcoin().encode("Hello world!");
  auto decoded = Base58::bitcoin().decode(encoded);
  bool ok = Base62::base62chk().is_valid(encoded);
  ```
- **Use it when:**
  - Rendering a binary id as a compact, human-typeable string.
  - You need a specific alphabet: Bitcoin Base58, Crockford Base32, URL-safe Base64.
- **Do not use it when / gotchas:**
  - `decode` throws `std::invalid_argument` on a bad character, check digit or checksum.
  - Alphabets differ in ordering and case rules; pick the exact factory instead of assuming a standard.
  - Big-integer division makes it slower than a table-driven Base64 for bulk data.

### cuuid
[github.com/Kronuz/cuuid](https://github.com/Kronuz/cuuid) &middot; depends on: `char-classify`, `endian`
- **What it is:** A condensed UUID value type: generate, parse, format, and serialize UUIDs in a compact wire form.
- **Header / target:** `#include "cuuid.hh"`, plus `#include "cuuid_v1.hh"` for v1 fields; target `cuuid::cuuid`; C++20.
- **How it works:** `UUID` wraps the 16 bytes and `UUIDGenerator` produces new ones through the platform backend. The interesting part is serialization: the full form is a `0x01` tag byte followed by 16 bytes, but RFC 4122 v1 values that fit the expected shape are packed into a much shorter condensed encoding, which is what "condensed" means in the name. The v1 header exposes node, timestamp, clock sequence, variant and version.
- **Key API:**
  - `UUID`, `UUIDGenerator`
  - `serialise()`, `unserialise(...)`
  - `is_valid(...)`, `is_serialised(...)`
  - v1 field accessors in `cuuid_v1.hh`
- **Example:**
  ```cpp
  #include "cuuid_v1.hh"

  UUIDGenerator gen;
  UUID id = gen();
  std::string wire = id.serialise();
  UUID back = UUID::unserialise(wire);
  ```
- **Use it when:**
  - Storing many UUIDs where the compact encoding saves real space.
  - You need UUID v1 timestamp or node fields.
- **Do not use it when / gotchas:**
  - The wire format is project-specific; do not feed it to a generic UUID parser or expect interop.
  - Requires platform UUID headers.

### md5
[github.com/Kronuz/md5](https://github.com/Kronuz/md5) &middot; depends on: `endian`
- **What it is:** MD5 digests for content fingerprinting and compatibility with existing MD5-based formats.
- **Header / target:** `#include "md5.h"`; target `md5::md5`; C++20.
- **How it works:** A standard MD5 compression implementation supporting both one-shot buffers and incremental `add()` calls, holding the digest state internally and producing a 32-character lowercase hex string.
- **Key API:**
  - `class MD5`, constructed from a buffer or string view
  - `operator()(const void*, size_t)` / `operator()(string_view)` -> 32 hex chars
  - `add(const void*, size_t)` for streaming, then `getHash()`
- **Example:**
  ```cpp
  #include "md5.h"

  MD5 md5;
  std::string hex = md5("Hello World");       // one shot, 32 hex chars
  md5.add(more, n);                           // or stream, then:
  std::string streamed = md5.getHash();
  ```
- **Use it when:**
  - Content addressing or cache keys where collisions are not adversarial.
  - Interoperating with a format that already specifies MD5.
- **Do not use it when / gotchas:**
  - MD5 is cryptographically broken. Never use it for passwords, signatures or authenticity.
  - Pass explicit lengths for buffers containing NUL bytes.

### sha256
[github.com/Kronuz/sha256](https://github.com/Kronuz/sha256) &middot; depends on: `endian`
- **What it is:** SHA-256 digests, 32 bytes or 64 hex characters, for integrity checks and content ids.
- **Header / target:** `#include "sha256.h"`; target `sha256::sha256`; C++20. Compiled, not header-only.
- **How it works:** A standard SHA-256 compression implementation with incremental `add()` plus one-shot buffer and string overloads, tracking the 256-bit state and exposing both raw digest bytes and hex text.
- **Key API:**
  - `class SHA256`, constructed from buffer or string
  - `operator()(const void*, size_t)` / `operator()(string_view)` -> 64 hex chars
  - `add(const void*, size_t)` for streaming, then `getHash()`
  - `getHash(unsigned char buffer[HashBytes])` for raw bytes
- **Example:**
  ```cpp
  #include "sha256.h"

  SHA256 sha256;
  std::string hex = sha256("Hello World");    // one shot, 64 hex chars
  sha256.add(more, n);                        // or stream, then:
  std::string streamed = sha256.getHash();
  ```
- **Use it when:**
  - Verifying file or message integrity.
  - Deriving stable content identifiers.
- **Do not use it when / gotchas:**
  - A bare hash is not a MAC and not password storage; use HMAC or a KDF for those.
  - Link the target; the header alone does not carry every symbol.

### random
[github.com/Kronuz/random](https://github.com/Kronuz/random) &middot; depends on: none
- **What it is:** Four small helpers for random reals, integers, durations and strings.
- **Header / target:** `#include "random.hh"`; target `random::random`; C++20.
- **How it works:** Thin wrappers over `<random>` with inclusive ranges, plus a random string generator. The duration helper returns `std::chrono::milliseconds`, which is the form you want for jitter and backoff.
- **Key API:**
  - `double random_real(double initial, double last)`
  - `std::uint64_t random_int(std::uint64_t initial, std::uint64_t last)`
  - `std::chrono::milliseconds random_time(milliseconds initial, milliseconds last)`
  - `std::string random_string(size_t length)`
- **Example:**
  ```cpp
  #include "random.hh"

  auto delay = random_time(10ms, 1s);   // retry jitter
  auto token = random_string(32);
  ```
- **Use it when:**
  - Retry jitter, backoff and test fixtures.
  - You want one call instead of engine plus distribution boilerplate.
- **Do not use it when / gotchas:**
  - Not cryptographic; do not generate secrets, tokens or keys with it.
  - Uses global state and is not documented as thread-safe or reproducible.

### bloom-filter
[github.com/Kronuz/bloom-filter](https://github.com/Kronuz/bloom-filter) &middot; depends on: `hashes`
- **What it is:** A fixed-size Bloom filter: no false negatives, bounded memory, no allocation.
- **Header / target:** `#include "bloom_filter.hh"`; target `bloom_filter::bloom_filter`; C++20.
- **How it works:** `BloomFilter<N>` holds an inline `std::bitset<N * 32>` and sets 20 probe bits derived from the hashes library, so memory is about `4 * N` bytes and entirely inline. A non-zero salt selects an independent view of the same bit array, letting one filter serve several logical sets.
- **Key API:**
  - `template <size_t N = 131072> class BloomFilter`
  - `void add(const char*, size_t, uint64_t salt = 1)`
  - `bool contains(const char*, size_t, uint64_t salt = 1) const`
- **Example:**
  ```cpp
  #include "bloom_filter.hh"

  BloomFilter<8192> seen;
  seen.add(key, len);
  if (!seen.contains(key, len)) { /* definitely absent */ }
  ```
- **Use it when:**
  - Skipping an expensive lookup for keys that are definitely absent.
  - A bounded memory membership summary.
- **Do not use it when / gotchas:**
  - `true` means probably present; only `false` is definitive.
  - No removal, and no resizing. Large `N` must not go on the stack.
  - The salt must be non-zero and must match between `add` and `contains`.

### lru-cache
[github.com/Kronuz/lru-cache](https://github.com/Kronuz/lru-cache) &middot; depends on: none
- **What it is:** An LRU cache with optional TTL and policy callbacks on eviction.
- **Header / target:** `#include "lru.h"`; target `lru_cache`; C++17.
- **How it works:** An `unordered_map` whose nodes are linked through an intrusive doubly linked list, giving O(1) lookup, recency relink and eviction without a second container. `aging_lru` adds expiry timestamps and a second age-ordered list so TTL trimming is also O(1) amortized. Not thread-safe.
- **Key API:**
  - `lru::lru<Key, T, ...>`, `lru::aging_lru<Key, T, ...>`
  - `emplace`, `insert`, `find`, `at`, `get`, `operator[]`
  - `find_and_leave`, `find_and_renew`, `find_and_relink`
  - `erase`, `clear`, `trim`, `exists`, `size`, `max_size`
- **Example:**
  ```cpp
  #include "lru.h"

  lru::lru<int, std::string> cache(2);
  cache.emplace(1, "one");
  cache.emplace(2, "two");
  cache.emplace(3, "three");   // evicts key 1
  ```
- **Use it when:**
  - A bounded cache with predictable eviction.
  - You need TTL expiry or a callback to veto/handle eviction.
- **Do not use it when / gotchas:**
  - Not thread-safe; wrap it yourself for concurrent use.
  - `find` renews recency, `exists` does not. Picking the wrong one silently changes eviction order.
  - A plain `lru` with a non-zero TTL asserts; use `aging_lru`.

### generation-cache
[github.com/Kronuz/generation-cache](https://github.com/Kronuz/generation-cache) &middot; depends on: none
- **What it is:** A thread-safe cache invalidated as a whole group by a generation bump, not individually by LRU/TTL.
- **Header / target:** `#include "generation_cache.hh"`; target `generation_cache`; header-only; C++17.
- **How it works:** A `std::map` and a generation counter behind one mutex. `clear()` erases every entry and bumps the generation. A reader captures the generation alongside its lookup (`get_with_generation`); `try_insert` only commits if that generation still matches current, so a value computed before a concurrent `clear()` but inserted after it is silently dropped instead of resurrecting stale data.
- **Key API:**
  - `generation_cache::Cache<Key, Value>`
  - `get`, `get_with_generation`, `try_insert`, `clear`, `size`, `generation`
- **Example:**
  ```cpp
  #include "generation_cache.hh"

  generation_cache::Cache<int, std::string> cache;
  auto lookup = cache.get_with_generation(42);
  if (!lookup.value) {
      auto value = expensive_compute(42);
      cache.try_insert(42, value, lookup.generation);
  }
  cache.clear(); // e.g. when the source state this was computed from changes
  ```
- **Use it when:**
  - Many readers derive an expensive Value from a Key against one shared mutable source of truth that changes in discrete steps (a write, a new version), and every cached result is valid until the next step and wrong after it -- no per-entry ranking applies.
- **Do not use it when / gotchas:**
  - You want size-bounded or recency-bounded eviction instead -- use `lru-cache`.
  - No built-in size cap; the natural bound comes from how many distinct keys the caller's own domain can reach (see its `ARCHITECTURE.md`).
  - One mutex guards the whole cache; not sharded, not lock-free.

### cpp-btree
[github.com/Kronuz/cpp-btree](https://github.com/Kronuz/cpp-btree) &middot; depends on: none
- **What it is:** Cache-friendly B-tree ordered containers, a near drop-in for `std::map` and `std::set`.
- **Header / target:** `#include "btree/map.h"`, `#include "btree/set.h"`; C++17. A modernized port of Google's cpp-btree, and the most widely used repo in the collection (280+ stars).
- **How it works:** Each node stores many sorted values instead of one, so a lookup touches far fewer cache lines than the pointer-per-element red-black tree behind `std::map`, and the container uses substantially less memory per element. The trade is that mutation can move values between nodes.
- **Key API:**
  - `btree::map<Key, T, Compare, Allocator, TargetNodeSize>`
  - `btree::set<Key, ...>`, plus multimap and multiset variants
  - the usual `insert`, `find`, `erase`, `lower_bound`, iteration
- **Example:**
  ```cpp
  #include "btree/map.h"

  btree::map<int, std::string> m;
  m.emplace(2, "two");
  m.emplace(1, "one");
  auto it = m.find(2);
  ```
- **Use it when:**
  - A large ordered map or set where lookup locality and memory matter.
  - You want ordered iteration without `std::map`'s per-node allocation.
- **Do not use it when / gotchas:**
  - Iterator invalidation is stricter than `std::map`: insert and erase can invalidate iterators, so it is not a blind drop-in.
  - No CMake target in the repo; add the include directory yourself.

## Concurrency, time, and the operating system

*Threads, queues, timers, clocks and the syscalls that need wrapping.*

### threadpool
[github.com/Kronuz/threadpool](https://github.com/Kronuz/threadpool) &middot; depends on: none
- **What it is:** A fixed-size C++20 worker pool with fire-and-forget, bulk, and future-returning task submission.
- **Header / target:** `#include "threadpool.hh"`; CMake target `threadpool::threadpool`; C++20.
- **How it works:** `ThreadPool` owns long-lived worker threads and a shared `BlockingConcurrentQueue`. The bundled queues are mutex-backed `std::deque` implementations, not lock-free queues. Workers wait with a timed condition-variable dequeue, execute tasks, and update atomic counters for state queries. The target is a static library because thread primitives are implemented in `thread.cc`; task and queue templates are header-defined.
- **Key API:**
  - `ThreadPool<TaskType = std::function<void()>, ThreadPolicyType policy = regular>`
  - `ThreadPool(const char* format, size_t num_threads, size_t queue_size = 1000)`
  - `enqueue(Func&&) -> bool`
  - `enqueue_bulk(It first, size_t count) -> bool`
  - `async(Func&&, Args&&...) -> std::future<R>`
  - `end()`, `finish()`, `clear()`
  - `join(timeout = 60s) -> bool`
  - `size()`, `running_size()`, `threadpool_workers()`
  - `TaskQueue<std::packaged_task<R(Args...)>>::enqueue`, `call`, `clear`
- **Example:**
  ```cpp
  #include "threadpool.hh"
  ThreadPool<> pool("W{:02}", 4);
  pool.enqueue([] { do_some_work(); });
  auto result = pool.async([](int a, int b) { return a + b; }, 2, 3);
  int sum = result.get();
  pool.end();
  pool.join();
  ```
- **Use it when:**
  - A bounded pool of reusable worker threads is needed.
  - Tasks need either fire-and-forget or `std::future` results.
  - Worker naming and pool state counters are useful.
- **Do not use it when / gotchas:**
  - Do not assume the bundled queues are lock-free.
  - `finish()` can stop workers before queued tasks drain; use `end()` for graceful draining.
  - The compile-time thread policy tags are currently runtime-ignored.

### queue
[github.com/Kronuz/queue](https://github.com/Kronuz/queue) &middot; depends on: none
- **What it is:** A header-only, bounded, blocking, double-ended MPMC queue.
- **Header / target:** `#include "queue.h"`; CMake target `queue::queue`; C++20.
- **How it works:** `queue::Queue<T, Container>` wraps a `std::deque` with one mutex, separate producer and consumer condition variables, and an atomic item count. Pushes and pops can block forever, return immediately, or wait for a specified number of seconds. `end()` rejects new pushes while allowing consumers to drain; `finish()` rejects all operations and wakes waiters. `QueueSet<Key>` adds uniqueness using a list and hash map.
- **Key API:**
  - `queue::Queue<T, Container = std::deque<T>>`
  - `Queue(hard_limit = -1, soft_limit = -1, threshold = -1)`
  - `push_back(value, timeout = -1, force = false) -> bool`
  - `push_front(value, timeout = -1, force = false) -> bool`
  - `pop_front(out, timeout = -1) -> bool`
  - `pop_back(out, timeout = -1) -> bool`
  - `front(out) -> bool`, `clear()`, `empty()`, `size()`, `count()`
  - `end()`, `finish()`
  - `QueueSet<Key>` with `update`, `leave`, and `renew` duplicate policies
- **Example:**
  ```cpp
  #include "queue.h"
  queue::Queue<int> q(1024);
  q.push_back(42);
  int value;
  if (q.pop_front(value, 0.05)) {
      use(value);
  }
  q.end();
  q.finish();
  ```
- **Use it when:**
  - A blocking channel needs bounded capacity and back-pressure.
  - Consumers need FIFO and LIFO access or per-operation timeouts.
  - Shutdown must distinguish draining from immediate termination.
- **Do not use it when / gotchas:**
  - All queue mutation is mutex-serialized; it is not a lock-free throughput queue.
  - Timeout values are seconds as `double`: negative blocks forever, zero is non-blocking.
  - `end()` rejects pushes but still permits pops until the queue is empty.

### stash
[github.com/Kronuz/stash](https://github.com/Kronuz/stash) &middot; depends on: none
- **What it is:** A header-only C++17 lock-free hierarchical slot store for keyed, time-ordered values.
- **Header / target:** `#include "stash.h"`; CMake target is not clearly exposed in the repository metadata; C++17.
- **How it works:** `Stash` is a lazily grown chunked array of atomic pointers, with overflow chunks linked through atomic publication. Producers reserve and publish slots with compare-exchange and do not take locks. `StashSlots` maps integer keys to nested stash levels using `(key / Div) % Mod`; `StashValues` provides an append-only leaf with atomic write and consumer cursors. A single consumer walks, peeks, and cleans while producers add concurrently.
- **Key API:**
  - `Stash<T, Size, Reserved = false>`
  - `StashSlots<T, Size, Div, Mod>`
  - `StashValues<T, Size>`
  - `StashContext::{walk, peep, clean}`
  - `StashContext::next(...)`, `Stash::add(...)`
  - `stash_reserved<T>()`
- **Example:**
  ```cpp
  #include "stash.h"
  StashValues<int*, 16> values;
  StashContext context(0);
  values.add(context, 0, new int(42));
  int* value = nullptr;
  context.op = StashContext::Operation::walk;
  values.next(context, &value);
  ```
- **Use it when:**
  - A scheduler or timer wheel needs lock-free producer insertion.
  - One consumer can walk and reclaim entries in key order.
  - Multiple time resolutions can be represented by nested slot levels.
- **Do not use it when / gotchas:**
  - The design assumes a single consumer for sequential walking and cleanup.
  - Producers can allocate chunks and overflow nodes lazily; insertion is not allocation-free.
  - Keys outside the configured hierarchy or wheel horizon can throw or be discarded by higher-level users.

### scheduler
[github.com/Kronuz/scheduler](https://github.com/Kronuz/scheduler) &middot; depends on: `stash`, `threadpool`
- **What it is:** A C++20 timer scheduler built on a lock-free hierarchical time wheel and worker-thread execution.
- **Header / target:** `#include "scheduler.h"`; CMake target `scheduler::scheduler` if enabled by the repository; C++20.
- **How it works:** The scheduler stores shared scheduled tasks in nested `StashSlots` levels covering progressively larger time intervals. A scheduler thread waits on a condition variable, walks due entries, and optionally dispatches them to a `ThreadPool`. `ScheduledTask::clear()` uses an atomic one-shot claim and cancellation flag, including a final cancellation check after dispatch. The default wheel horizon is approximately 24 hours; scheduling beyond it is dropped with an injectable trace hook.
- **Key API:**
  - `ScheduledTask<...>::operator()()`, `clear(bool internal = false)`, `cancelled()`
  - `Scheduler<ScheduledTaskImpl, policy>`
  - `ThreadedScheduler<ScheduledTaskImpl, policy>`
  - `BaseScheduler::add(task)`, `end(wait = 10)`
  - `SchedulerQueue::add`, `walk`, `peep`, `clean`
- **Example:**
  ```cpp
  #include "scheduler.h"
  struct Job {
      void operator()() { work(); }
  };
  Scheduler<Job> scheduler("jobs");
  auto task = std::make_shared<Job>();
  scheduler.add(task, std::chrono::steady_clock::now() + 1s);
  task->clear();
  ```
- **Use it when:**
  - Many delayed tasks need timer-wheel rather than heap scheduling.
  - Producers must schedule concurrently without taking a queue mutex.
  - Cancellation must suppress a task dispatched but not yet started.
- **Do not use it when / gotchas:**
  - Tasks scheduled beyond the wheel horizon are silently discarded unless trace hooks are enabled.
  - The wheel requires the `stash` single-consumer traversal model.
  - Scheduler execution and task callbacks can allocate through `shared_ptr` and the thread pool.

### atomic-shared-ptr
[github.com/Kronuz/atomic-shared-ptr](https://github.com/Kronuz/atomic-shared-ptr) &middot; depends on: none
- **What it is:** A portable atomic wrapper or alias for atomic operations on `std::shared_ptr<T>`.
- **Header / target:** `#include "atomic_shared_ptr.h"`; CMake target `atomic-shared-ptr::atomic-shared-ptr` if discoverable; C++20 when using the standard specialization, otherwise compatible with the compiler's shared-pointer atomic facilities.
- **How it works:** On libraries implementing `__cpp_lib_atomic_shared_ptr`, `atomic_shared_ptr<T>` aliases `std::atomic<std::shared_ptr<T>>`. Otherwise it wraps the free `std::atomic_*` shared-pointer functions. Operations are atomic at the shared-pointer level, but `is_lock_free()` reflects the platform implementation and may be false.
- **Key API:**
  - `atomic_shared_ptr<T>`
  - `load(order = seq_cst) -> std::shared_ptr<T>`
  - `store(std::shared_ptr<T>, order = seq_cst)`
  - `exchange(std::shared_ptr<T>, order = seq_cst)`
  - `compare_exchange_weak/strong(expected, desired, order)`
  - `is_lock_free() -> bool`
- **Example:**
  ```cpp
  #include "atomic_shared_ptr.h"
  atomic_shared_ptr<int> value{std::make_shared<int>(1)};
  auto current = value.load();
  value.store(std::make_shared<int>(2));
  auto old = value.exchange(std::make_shared<int>(3));
  ```
- **Use it when:**
  - A shared object must be replaced atomically while readers retain ownership.
  - Copy-on-write or lock-free publication uses `shared_ptr` lifetime management.
- **Do not use it when / gotchas:**
  - Do not assume operations are lock-free; check `is_lock_free()`.
  - The wrapper itself is non-copyable and non-movable.
  - Atomic pointer replacement does not make the pointed-to object mutable-state safe.

### allocators
[github.com/Kronuz/allocators](https://github.com/Kronuz/allocators) &middot; depends on: none
- **What it is:** C++17 allocator implementations for system allocation tracking and single-object memory pooling.
- **Header / target:** `#include "allocators.h"`; CMake target `allocators::allocators`; C++17.
- **How it works:** `vanilla_allocator` delegates allocation and deallocation to the library implementation without tracking. `tracked_allocator` records allocation totals, exposed through `total_allocated()` and `local_allocated()`. `allocator<T, Allocator>` adapts either backend to the standard allocator interface. `memory_pool_allocator<T>` stores blocks in a `std::deque`, reuses freed single-object blocks through an intrusive free list, and rejects allocations other than exactly one object.
- **Key API:**
  - `allocators::vanilla_allocator::{allocate, deallocate}`
  - `allocators::tracked_allocator::{allocate, deallocate}`
  - `allocators::allocator<T, Allocator>::allocate`, `deallocate`, `construct`, `destroy`
  - `allocators::memory_pool_allocator<T>::allocate(1)`, `deallocate`, `construct`, `destroy`
  - `allocators::total_allocated()`, `local_allocated()`
- **Example:**
  ```cpp
  #include "allocators.h"
  using A = allocators::allocator<int, allocators::tracked_allocator>;
  A alloc;
  int* p = alloc.allocate(1);
  alloc.construct(p, 42);
  alloc.destroy(p);
  alloc.deallocate(p, 1);
  ```
- **Use it when:**
  - Standard containers need allocation accounting.
  - A container repeatedly allocates and frees one fixed-size object type.
- **Do not use it when / gotchas:**
  - `memory_pool_allocator<T>` only accepts `allocate(1)` and is not thread-safe.
  - The pool retains its backing `std::deque` storage until allocator destruction.
  - `tracked_allocator` counters are instrumentation, not a synchronization mechanism.

### nanosleep
[github.com/Kronuz/nanosleep](https://github.com/Kronuz/nanosleep) &middot; depends on: none
- **What it is:** A small EINTR-safe nanosecond sleep helper.
- **Header / target:** `#include "nanosleep.h"`; CMake target `nanosleep::nanosleep` if discoverable; C++17.
- **How it works:** The inline overload converts an unsigned nanosecond count to `timespec` and calls POSIX `nanosleep`. If interrupted, it retries using the remaining duration in the modified `timespec`, so signals do not shorten the requested sleep. Zero returns immediately and no heap allocation occurs.
- **Key API:**
  - `nanosleep(unsigned long long nsec)`
- **Example:**
  ```cpp
  #include "nanosleep.h"
  nanosleep(5'000'000);  // approximately 5 ms
  ```
- **Use it when:**
  - A polling or retry loop needs a signal-resilient short sleep.
  - A dependency-free POSIX nanosecond delay is sufficient.
- **Do not use it when / gotchas:**
  - It blocks the calling thread and has normal scheduler granularity.
  - It is POSIX-specific and does not provide cancellation or a deadline abstraction.
  - The function shares the global name `nanosleep`, so include and overload interactions should be checked.

### epoch
[github.com/Kronuz/epoch](https://github.com/Kronuz/epoch) &middot; depends on: none
- **What it is:** A header-only helper returning the current system-clock Unix epoch in a selected duration unit.
- **Header / target:** `#include "epoch.hh"`; CMake target `epoch::epoch` if discoverable; C++17.
- **How it works:** `epoch::now<Period>()` obtains `std::chrono::system_clock::now()`, subtracts its epoch, casts to `Period`, and returns the integral duration count. It is inline, non-allocating, and not monotonic because it follows wall-clock time.
- **Key API:**
  - `template<typename Period = std::chrono::seconds> epoch::now() noexcept`
- **Example:**
  ```cpp
  #include "epoch.hh"
  auto seconds = epoch::now<>();
  auto millis = epoch::now<std::chrono::milliseconds>();
  ```
- **Use it when:**
  - Unix timestamps are needed in seconds, milliseconds, or another chrono period.
  - Wall-clock time is intentionally required.
- **Do not use it when / gotchas:**
  - Do not use it for elapsed-time measurement or timeout ordering; the system clock can jump.
  - Resolution is limited by the clock and the requested duration cast.
  - The return type is the period's integral `count()` type.

### time-point
[github.com/Kronuz/time-point](https://github.com/Kronuz/time-point) &middot; depends on: none
- **What it is:** Header-only C++17 conversion helpers between chrono time points and unsigned nanosecond values.
- **Header / target:** `#include "time_point.hh"`; CMake target `time-point::time-point` if discoverable; C++17.
- **How it works:** `time_point_to_ullong` duration-casts any `std::chrono::time_point` to nanoseconds since that clock's epoch. `time_point_from_ullong` constructs a time point from an unsigned nanosecond count, defaulting to `std::chrono::steady_clock`. The header also contains an EINTR-safe inline nanosecond sleep helper and performs no dynamic allocation.
- **Key API:**
  - `time_point_to_ullong(std::chrono::time_point<Clock>) -> unsigned long long`
  - `time_point_from_ullong<Clock = std::chrono::steady_clock>(unsigned long long)`
  - `nanosleep(unsigned long long)`
- **Example:**
  ```cpp
  #include "time_point.hh"
  auto now = std::chrono::steady_clock::now();
  auto raw = time_point_to_ullong(now);
  auto restored = time_point_from_ullong(raw);
  ```
- **Use it when:**
  - A time point must be stored or exchanged as integer nanoseconds.
  - A timer-wheel key needs a compact chrono conversion.
- **Do not use it when / gotchas:**
  - The integer is meaningful only with the same clock epoch and clock type.
  - Unsigned conversion is unsuitable for negative time points or durations.
  - Do not confuse steady-clock values with Unix epoch timestamps.

### times
[github.com/Kronuz/times](https://github.com/Kronuz/times) &middot; depends on: none
- **What it is:** A C++17 `timespec` value type with normalization, arithmetic, comparisons, and current-wall-clock helpers.
- **Header / target:** `#include "times.h"`; CMake target `times::times`; C++17.
- **How it works:** `timespec_t` derives from `timespec`, normalizes seconds and nanoseconds after arithmetic, and supports conversion to and from fractional seconds. `now()` reads `CLOCK_REALTIME`, using platform-specific `clock_gettime` support on macOS when needed. Operations are inline and allocation-free.
- **Key API:**
  - `timespec_t(double seconds = 0)`
  - `clear()`, `set_now()`, `as_double()`
  - `operator+`, `operator-`, `operator+=`, `operator-=`
  - `operator*`, `operator/` with `double`
  - relational operators
  - `now() -> timespec_t`
- **Example:**
  ```cpp
  #include "times.h"
  auto start = now();
  timespec_t delay(0.25);
  auto deadline = start + delay;
  if (now() >= deadline) handle_timeout();
  ```
- **Use it when:**
  - Existing POSIX APIs use `timespec` but arithmetic is needed.
  - A wall-clock fractional-second value needs normalization and comparison.
- **Do not use it when / gotchas:**
  - `now()` uses `CLOCK_REALTIME`, not a monotonic clock.
  - The `double` representation loses precision for very large timestamps.
  - The type inherits public `timespec` fields; callers can create invalid values by mutating them directly.

### datetime
[github.com/Kronuz/datetime](https://github.com/Kronuz/datetime) &middot; depends on: `strict-stox`
- **What it is:** A C++17 parser and formatter for ISO-8601 dates, times, time zones, date math, and numeric timestamps.
- **Header / target:** `#include "datetime.h"`; CMake target `datetime::datetime`; C++17.
- **How it works:** The compiled implementation validates and parses date/time strings with regular expressions, converts between calendar structures, `time_t`, system-clock points, and floating-point timestamps, and formats ISO-8601 output. `Datetime::tm_t` represents calendar fields with fractional seconds and UTC state; `clk_t` represents time or durations with a signed zone offset. It uses exceptions derived from `std::runtime_error` for invalid input and performs no concurrency synchronization.
- **Key API:**
  - `Datetime::DatetimeParser`, `Iso8601Parser`
  - `Datetime::processDateMath`, `computeDateMath`, `computeTimeZone`
  - `Datetime::toordinal`, `timegm`, `to_tm_t`, `timestamp`
  - `Datetime::iso8601`, `isDate`, `isDatetime`
  - `Datetime::TimeParser`, `time_to_string`, `isTime`
  - `Datetime::TimedeltaParser`, `timedelta_to_string`, `isTimedelta`
  - `DatetimeError`, `DateISOError`, `TimeError`, `TimedeltaError`
- **Example:**
  ```cpp
  #include "datetime.h"
  auto parsed = Datetime::DatetimeParser("2026-09-29T13:41:07Z");
  double ts = Datetime::timestamp(parsed);
  auto text = Datetime::iso8601(ts);
  ```
- **Use it when:**
  - ISO-8601 parsing and formatting must match the library's date-math behavior.
  - Calendar values need conversion to timestamps or `time_t`.
  - Time and timedelta strings need validation and formatting.
- **Do not use it when / gotchas:**
  - Invalid input can throw `DatetimeError` subclasses; callers must handle it.
  - `tm_t` and `clk_t` are value structures, not synchronized shared state.
  - Floating-point timestamps have microsecond-oriented precision and are not arbitrary-precision time values.

### io
[github.com/Kronuz/io](https://github.com/Kronuz/io) &middot; depends on: none
- **What it is:** A C++20 compiled POSIX file and socket layer that retries selected EINTR failures and handles short-count I/O.
- **Header / target:** `#include "io.hh"`; CMake target `io::io`; C++20.
- **How it works:** `io::read`, `write`, and `pwrite` loop to transfer the requested count, while `pread` returns after one positional read. `RetryAfterSignal` retries `-1/EINTR` while the process-wide `ignore_eintr()` flag is enabled; `close()` intentionally is not retried because retrying can close a reused descriptor. `open()` sets `O_CLOEXEC` and rejects descriptors below `IO_MINIMUM_FILE_DESCRIPTOR`; durability and allocation helpers use platform-specific fallbacks. The implementation is a static library in `io.cc`.
- **Key API:**
  - `io::ignore_eintr() -> std::atomic_bool&`
  - `io::RetryAfterSignal(F, args...)`
  - `io::open(path, flags, mode)`, `close(fd)`
  - `read`, `write`, `pread`, `pwrite`
  - `fcntl`, `unchecked_fcntl`, `fstat`, `lseek`
  - `mkstemp`, `mkdtemp`, `unlink`
  - `fsync`, `full_fsync`, `fallocate`, `fadvise`
  - `send`, `recv`, `accept`, `connect`, and socket helpers
- **Example:**
  ```cpp
  #include "io.hh"
  int fd = io::open("data.bin", O_RDWR | O_CREAT, 0644);
  const char data[] = "hello";
  io::write(fd, data, sizeof(data) - 1);
  io::fsync(fd);
  io::close(fd);
  ```
- **Use it when:**
  - File or socket operations need centralized EINTR and partial-transfer handling.
  - Data files must not accidentally consume stdin, stdout, or stderr descriptors.
  - Cross-platform durability, preallocation, or advisory-I/O fallbacks are needed.
- **Do not use it when / gotchas:**
  - `close()` deliberately does not retry on EINTR.
  - Full-count `read` and `write` can block until the requested buffer is transferred; they are not single-syscall wrappers.
  - `ignore_eintr()` is process-wide and changes retry behavior globally.

### fs
[github.com/Kronuz/fs](https://github.com/Kronuz/fs) &middot; depends on: `io`, `split`, `stringified`, `strings`
- **What it is:** A C++20 compiled filesystem helper library for recursive directories, glob operations, file movement, and path normalization.
- **Header / target:** `#include "fs.hh"`; CMake target `fs::fs`; C++20.
- **How it works:** The static implementation combines directory APIs, `fnmatch`, temporary-file creation, and the EINTR-safe `io` layer. `normalize_path` is a pure string operation that collapses repeated separators and `.`/`..` components. Recursive copy, move, delete, and quarantine operations allocate strings and directory structures as needed; no global thread-safety guarantee is documented.
- **Key API:**
  - `delete_files(path, patterns = {"*"})`
  - `quarantine_files(path, patterns = {"*"}, suffix = ".quarantine.XXXXXX")`
  - `move_files(src, dst)`
  - `exists(path)`, `mkdir(path)`, `mkdirs(path)`
  - `build_path_index(path_index)`
  - `opendir(path, create = false)`, `find_file_dir`
  - `copy_file(src, dst, create = true, file_name = "", new_name = "")`
  - `normalize_path(src, slashed = false, keep_slash = false)`
- **Example:**
  ```cpp
  #include "fs.hh"
  mkdirs("/var/data/shard/3");
  if (exists("/var/data/shard/3"))
      delete_files("/var/data/shard/3", {"*.tmp", "*.lock"});
  auto clean = normalize_path("a/b/../c");
  ```
- **Use it when:**
  - A directory tree needs recursive creation, copy, move, or cleanup.
  - Matching files must be deleted or quarantined by glob pattern.
  - Paths need lexical normalization without filesystem access.
- **Do not use it when / gotchas:**
  - `normalize_path` is lexical and does not resolve symlinks or verify path existence.
  - Recursive operations can allocate and perform many syscalls; they are not atomic transactions.
  - Logging is a no-op unless `FS_TRACE_HEADER` is supplied, so failures must be checked through return values or exceptions.

## Networking, serialization, storage

*The service stack: sockets to HTTP to persistence. `prism` shows them assembled.*

### reactor
[github.com/Kronuz/reactor](https://github.com/Kronuz/reactor) &middot; depends on: none
- **What it is:** A header-only standalone Asio runtime that accepts TCP connections, distributes them across reactor threads, and shuts them down cleanly.
- **Header / target:** `#include "reactor.h"` and optionally `#include "reactor_udp.h"`; CMake target `reactor::reactor`; C++20; requires standalone Asio.
- **How it works:** `TcpServer` runs shared-nothing Asio `io_context` reactors, normally one per core, and invokes a coroutine `Session` for each accepted socket. Linux uses `SO_REUSEPORT`; macOS and BSD use a shared acceptor fallback. Each reactor has an offload thread pool and bounded `gate()`, while tracked `Abortable` operations are cancelled before reactor shutdown. `UdpServer` provides one receive loop, multicast options, and an exposed `io()` for timers and protocol state.
- **Key API:**
  - `reactor::TcpServer(reactors, workers, queue, Session)`
  - `void TcpServer::start(port)`
  - `void TcpServer::stop()`
  - `asio::awaitable<void> Session(asio::ip::tcp::socket, reactor::Reactor&)`
  - `Reactor::pool()`, `Reactor::gate()`, `Reactor::track(Abortable&)`
  - `reactor::UdpServer(Datagram)`, `set_options(UdpOptions)`, `start(port)`, `send(bytes)`
- **Example:**
  ```cpp
  #include "reactor.h"
  asio::awaitable<void> echo(asio::ip::tcp::socket s, reactor::Reactor&) {
      char buf[1024];
      auto n = co_await s.async_read_some(asio::buffer(buf), asio::use_awaitable);
      co_await asio::async_write(s, asio::buffer(buf, n), asio::use_awaitable);
  }
  int main() { reactor::TcpServer s(4, 2, 256, echo); s.start(8080); }
  ```
- **Use it when:**
  - Building a custom TCP protocol or coroutine-based network service.
  - You need per-core reactors, bounded blocking work, or graceful cancellation.
- **Do not use it when / gotchas:**
  - It does not parse HTTP or provide application framing.
  - Sessions must cooperate with cancellation and must offload blocking work.

### server
[github.com/Kronuz/server](https://github.com/Kronuz/server) &middot; depends on: `compressors`, `queue`
- **What it is:** A legacy libev TCP server engine with CRTP accept-loop and per-connection state-machine bases extracted from Xapiand.
- **Header / target:** `#include "base_server.h"` and `#include "base_client.h"`; target is the server library target defined by the project; C++17; includes vendored libev and may use `Kronuz/queue` and `Kronuz/compressors`.
- **How it works:** `MetaBaseServer<ServerImpl>` owns the accept loop, while `BaseClient<ClientImpl>` implements the connection read/write FSM. `worker.h` supplies the libev worker tree and lifecycle watchers, and `buffer.h` handles writes. Host-specific logging, fatal handling, client accounting, and compatibility types are injected through redirectable headers and hooks.
- **Key API:**
  - `server::MetaBaseServer<ServerImpl>`
  - `server::BaseClient<ClientImpl>`
  - `server::Worker`
  - `SERVER_FATAL(code)`, `SERVER_ON_CLIENT_CREATED()`, `SERVER_ON_CLIENT_DESTROYED()`
  - Client implementation hooks such as `on_read`
- **Example:**
  ```cpp
  #include "base_server.h"
  #include "base_client.h"
  struct Client : server::BaseClient<Client> {
      void on_read() { /* consume input and write response */ }
  };
  struct App : server::MetaBaseServer<App> {
      /* accept Client connections */
  };
  ```
- **Use it when:**
  - Maintaining or extending the extracted Xapiand/libev server architecture.
  - A host needs custom client state machines and compatibility hooks.
- **Do not use it when / gotchas:**
  - It is a Leg-1 prototype, not the newer coroutine stack.
  - The file-transfer compressor path is real, but the client compressor itself is described as a prototype pass-through in the README.

### http
[github.com/Kronuz/http](https://github.com/Kronuz/http) &middot; depends on: `compressors`, `http-parser`, `radix-router`, `reactor`
- **What it is:** A C++20 coroutine HTTP/1.1 framework that turns parsed requests into `HttpHandler` calls and writes buffered or streamed responses.
- **Header / target:** `#include "http_handler.h"`, `#include "http_message.h"`, `#include "http_router.h"`, and `#include "http_asio.h"`; target `http::http`; C++20; requires standalone Asio.
- **How it works:** `HttpAsioService` adapts a `reactor::TcpServer` session to HTTP. `RequestParser` wraps the callback-driven zero-copy parser and either buffers the body or sends chunks to a `BodySink`. `HttpHandler` receives a value-like `Request`, and `ResponseWriter` supports fixed `Content-Length` responses or chunked streaming, with optional offload to a bounded Asio thread pool. Router dispatch, content negotiation, compression, ETags, and single-range responses are separate helpers.
- **Key API:**
  - `struct HttpHandler { virtual void handle(const Request&, ResponseWriter&) = 0; }`
  - `class ResponseWriter`: `send(status, body)`, `status(code)`, `set_header(name, value)`, `write(chunk)`, `end()`
  - `class BodySink`
  - `class Router`
  - `class RequestParser`
  - `class HttpAsioService`
  - `bool HttpHandler::should_offload(const Request&) const`
- **Example:**
  ```cpp
  #include "http_asio.h"
  #include "http_router.h"

  class App : public http::HttpHandler {
      http::Router router_;
  public:
      App() {
          router_.route("GET", "/", [](const http::Request&, http::ResponseWriter& r,
                                       const http::Params&) { r.send(200, "hello\n"); });
      }
      void handle(const http::Request& q, http::ResponseWriter& r) override {
          router_.handle(q, r);
      }
  };

  App app;
  http::HttpAsioService service(app, 4, 2, 256);
  service.start(8080);
  ```
- **Use it when:**
  - Implementing an HTTP service without exposing sockets, parsers, or reactor details to handlers.
  - Responses need streaming bodies, transparent compression, or request-body streaming.
- **Do not use it when / gotchas:**
  - `ResponseWriter::end()` completes the response; returning from `handle()` does not.
  - A handler that buffers the request body can consume unbounded application-sized input; use `BodySink` for large uploads.

### http-parser
[github.com/Kronuz/http-parser](https://github.com/Kronuz/http-parser) &middot; depends on: `enum-reflection`
- **What it is:** A compiled, callback-driven, zero-copy HTTP/1.x parser that accepts incremental input and custom HTTP methods.
- **Header / target:** `#include "http_parser.h"`; target `http_parser::http_parser`; C++20; requires `enum-reflection`.
- **How it works:** The parser is a state machine preserving parse state across arbitrary `http_parser_execute()` calls. Data callbacks receive slices of the caller's input buffer, so the parser does not retain message contents or allocate application storage. It handles HTTP/1.0 and 1.1, chunked and fixed-length bodies, keep-alive, upgrades, pauses, and typed parse errors. Xapiand-specific verbs are included alongside standard methods.
- **Key API:**
  - `http_parser_init(http_parser*, http_parser_type)`
  - `http_parser_settings_init(http_parser_settings*)`
  - `size_t http_parser_execute(http_parser*, settings*, data, len)`
  - `http_should_keep_alive(const http_parser*)`
  - `http_parser_pause(http_parser*, int)`
  - `HTTP_PARSER_ERRNO(parser)`
  - `http_method_str(http_method)`, `http_status_str(http_status)`
- **Example:**
  ```cpp
  #include "http_parser.h"
  http_parser p;
  http_parser_settings s;
  http_parser_init(&p, HTTP_REQUEST);
  http_parser_settings_init(&s);
  s.on_url = [](http_parser*, const char* p, size_t n) { return 0; };
  http_parser_execute(&p, &s, "GET / HTTP/1.1\r\n\r\n", 18);
  ```
- **Use it when:**
  - Parsing HTTP incrementally from sockets or custom transports.
  - The protocol must accept nonstandard methods such as `SEARCH`, `COUNT`, or `DUMP`.
- **Do not use it when / gotchas:**
  - Callback slices are not retained; copy data you need after the callback.
  - A single logical URL, header, or body may arrive through multiple callbacks, so append rather than assign.

### http-log
[github.com/Kronuz/http-log](https://github.com/Kronuz/http-log) &middot; depends on: `http`, `logger`, `repr`, `strings`
- **What it is:** An `http::HttpHandler` middleware that captures and renders HTTP request and response exchanges through Kronuz logger.
- **Header / target:** `#include "http_log.h"`; target `http-log::http-log` if consumed through its CMake target; C++20; requires `http` and the Kronuz logger stack.
- **How it works:** `AccessLog` wraps another `HttpHandler`, logs request metadata before dispatch, and wraps the response writer to capture status, headers, timing, and a bounded body preview. `Options` supplies body prettification, preview selection, capture limits, and per-status log levels. It recognizes text and structured content, can preview images in iTerm2, and logs handler exceptions while converting an unstarted response into a 500 response.
- **Key API:**
  - `class AccessLog : public http::HttpHandler`
  - `AccessLog(http::HttpHandler&, Options = {})`
  - `struct Options`
  - `using Prettify = std::function<std::optional<std::string>(std::string_view, std::string_view)>`
  - `using CanPreview = std::function<bool(std::string_view)>`
  - `method_palette(method)`, `status_palette(status)`
- **Example:**
  ```cpp
  #include "http_log.h"

  App app;                       // your http::HttpHandler
  http_log::AccessLog logged(app);
  http::HttpAsioService service(logged, 4, 2, 256);
  service.start(8080);
  ```
- **Use it when:**
  - Every request and response needs consistent access logging.
  - JSON, MsgPack, YAML, or binary response previews need service-specific formatting.
- **Do not use it when / gotchas:**
  - Body capture is bounded and large or incomplete bodies are summarized.
  - Image previews require a compatible terminal and appropriate log level.

### radix-router
[github.com/Kronuz/radix-router](https://github.com/Kronuz/radix-router) &middot; depends on: none
- **What it is:** A header-only generic radix-tree router for static paths, named parameters, and catch-all segments.
- **Header / target:** `#include "radix_router.h"`; target `radix-router::radix-router`; C++20.
- **How it works:** `Router<T>` stores route values in a compressed radix tree, splitting common static prefixes instead of allocating one node per character. Static branches are checked before parameter and catch-all branches. Matching is transport-agnostic and writes captured values into a reusable `Params` object, avoiding URL or HTTP dependencies.
- **Key API:**
  - `template <typename T> class Router`
  - `void Router<T>::insert(std::string_view pattern, T value)`
  - `const T* Router<T>::find(std::string_view path, Params&) const`
  - `class Params`: `add`, `get`, `clear`, `truncate`, `size`
  - Patterns: `/static`, `/:name`, `/*name`
- **Example:**
  ```cpp
  #include "radix_router.h"
  radix::Router<int> routes;
  routes.insert("/users/:id", 42);
  radix::Params p;
  if (auto* value = routes.find("/users/7", p))
      std::cout << p.get("id");
  ```
- **Use it when:**
  - Dispatching HTTP, RPC, or command paths with low allocation overhead.
  - You need named single-segment or remainder captures.
- **Do not use it when / gotchas:**
  - Wildcards must be named and only one wildcard is allowed per path segment.
  - Conflicting parameter names or catch-all modes at the same position are rejected.

### url-parser
[github.com/Kronuz/url-parser](https://github.com/Kronuz/url-parser) &middot; depends on: `char-classify`
- **What it is:** A header-only URL path and query parser with percent decoding and reusable cursor-based parsers.
- **Header / target:** `#include "url_parser.h"`; target `url-parser::url-parser`; C++20; requires `char-classify`.
- **How it works:** `urldecode()` decodes a byte buffer with configurable separators and plus handling. `QueryParser` walks key/value pairs while `PathParser` performs a backward pass to peel off the path, final ID, optional command, host, and slice components. The parsers return `std::string_view` slices into the input and can be rewound and reused.
- **Key API:**
  - `urldecode(input, plus, amp, colon, eq, encoded)`
  - `QueryParser::init(std::string_view)`, `next(...)`, `get()`, `rewind()`
  - `PathParser::init(std::string_view)`, `next()`
  - `PathParser::get_pth()`, `get_hst()`, `get_id()`, `get_slc()`, `get_cmd()`
- **Example:**
  ```cpp
  #include "url_parser.h"
  url::QueryParser q;
  q.init("a=1&b=two");
  while (q.next()) {
      auto value = q.get();
  }
  ```
- **Use it when:**
  - Splitting REST paths and query strings without constructing an AST.
  - Parsing repeatedly from stable input buffers.
- **Do not use it when / gotchas:**
  - Returned views refer to the input and require that input to remain alive.
  - The path parser has Xapiand-specific notions such as IDs, commands, hosts, and slices.

### compressors
[github.com/Kronuz/compressors](https://github.com/Kronuz/compressors) &middot; depends on: none
- **What it is:** A C++20 static library exposing interchangeable deflate, LZ4, and Zstandard buffer codecs plus deflate/LZ4 file-descriptor streaming.
- **Header / target:** `#include "compressor_deflate.h"`, `#include "compressor_lz4.h"`, or `#include "compressor_zstd.h"`; target `compressors::compressors`; C++20; requires zlib, lz4, and zstd.
- **How it works:** Each codec has a CRTP block-streaming base and matching data classes, while free functions cover whole-buffer use. Deflate can emit raw deflate or gzip; LZ4 uses a sequence of length-prefixed blocks; Zstd emits standard frames. Deflate and LZ4 also stream file descriptors through EINTR-safe I/O helpers. Reusable data objects support `reset()` to reuse scratch buffers.
- **Key API:**
  - `compress_deflate(std::string_view)`, `decompress_deflate(std::string_view)`
  - `compress_lz4(std::string_view)`, `decompress_lz4(std::string_view)`
  - `compress_zstd(std::string_view)`, `decompress_zstd(std::string_view)`
  - `DeflateCompressData`, `LZ4CompressData`, `ZstdCompressData`
  - `*CompressFile`, `*DecompressFile` for deflate and LZ4
- **Example:**
  ```cpp
  #include "compressor_zstd.h"
  std::string packed = compress_zstd(payload);
  std::string plain = decompress_zstd(packed);
  assert(plain == payload);
  ```
- **Use it when:**
  - Compressing complete buffers or iterating compressed blocks.
  - You need gzip interoperability, LZ4 speed, or Zstd ratio.
- **Do not use it when / gotchas:**
  - Formats are not interchangeable; each backend only decodes its own output.
  - Zstd is buffer-only in this library, unlike deflate and LZ4.

### flume
[github.com/Kronuz/flume](https://github.com/Kronuz/flume) &middot; depends on: `compressors`
- **What it is:** A header-only C++20 framed file-transfer layer that compresses bounded blocks and verifies the complete stream with XXH32.
- **Header / target:** `#include "flume.h"`; target `flume::flume`; C++20.
- **How it works:** `Sender<Writer>` reads an fd in chunks, compresses each block with an injected codec, writes a varint length and block, then emits a zero terminator and checksum. `Receiver<Sink>` accepts arbitrarily split input, reconstructs blocks into a sink, and verifies the XXH32 of uncompressed bytes. The channel is injected, so the same framing works with sockets, response buffers, libev queues, or other transports.
- **Key API:**
  - `template<class Writer> class Sender`
  - `Sender(Writer&, int input_fd)`, `bool send()`
  - `template<class Sink> class Receiver`
  - `Receiver(Sink&)`, `Status feed(const char*, size_t)`
  - `Receiver::Status::{Continue,Done,Error}`
  - Codec policies such as `ZstdCodec<6>`, `LZ4Codec`
- **Example:**
  ```cpp
  #include "flume.h"
  flume::Sender<SocketWriter> tx(writer, input_fd);
  bool ok = tx.send();
  flume::Receiver<FdSink> rx(sink);
  auto status = rx.feed(bytes, count);
  ```
- **Use it when:**
  - Transferring large files or database snapshots over a byte channel.
  - Memory must remain bounded and corruption or truncation must be detected.
- **Do not use it when / gotchas:**
  - It is a transport framing layer, not a general message queue.
  - The codec is part of the wire format; both endpoints must agree on codec family.

### storage
[github.com/Kronuz/storage](https://github.com/Kronuz/storage) &middot; depends on: `compressors`, `errno-names`, `strict-stox`, `stringified`
- **What it is:** A header-only append-only compressed multi-volume blob store with stable record offsets.
- **Header / target:** `#include "storage.h"`; target `storage::storage`; C++17; compression support requires `compressors`.
- **How it works:** `Storage<Header, BinHeader, Footer, IO>` appends opaque records into fixed-size blocks across volume files and returns an offset for later lookup. Record metadata selects compression per record, preserving compatibility with legacy LZ4 volumes while supporting Zstd and deflate. Header, binary header, footer, and POSIX I/O are policy/template seams; commit supports synchronous, full, no-sync, and host-provided asynchronous fsync. Optional footer policies validate checksums and raise `StorageCorruptVolume`.
- **Key API:**
  - `template<class Header, class BinHeader, class Footer, class IO = storage::DefaultIO> class Storage`
  - `Storage(path, StorageFsyncFn)`
  - `open(name, flags)`, `close()`
  - `write(data)`, `write_file(fd)`
  - `seek(offset)`, `read()`
  - `commit()`
  - `get_volumes_range(prefix)`
  - Flags: `STORAGE_CREATE_OR_OPEN`, `STORAGE_WRITABLE`, `STORAGE_COMPRESS_ZSTD`, `STORAGE_COMPRESS_LZ4`, `STORAGE_COMPRESS_DEFLATE`
- **Example:**
  ```cpp
  #include "storage.h"
  using Blobs = Storage<StorageHeader, StorageBinHeader, StorageBinFooter>;
  Blobs s("/var/data/", nullptr);
  s.open("vol.0", STORAGE_CREATE_OR_OPEN | STORAGE_WRITABLE);
  auto off = s.write("record");
  s.commit();
  ```
- **Use it when:**
  - Storing immutable blobs with stable offsets and append-heavy writes.
  - You need multi-volume discovery, optional compression, or injected durability policies.
- **Do not use it when / gotchas:**
  - It is not a transactional database or key/value index.
  - The reference footer has no checksum; supply a footer policy if corruption detection is required.

### msgpack
[github.com/Kronuz/msgpack](https://github.com/Kronuz/msgpack) &middot; depends on: `atomic-shared-ptr`, `constexpr-phf`, `enum-reflection`, `hashes`, `located-exception`, `repr`, `strict-stox`
- **What it is:** A header-heavy MessagePack and JSON-like copy-on-write value library with serialization, adaptors, and RFC 6902 patching.
- **Header / target:** `#include "msgpack.h"` and optionally `#include "msgpack.hpp"` or `#include "msgpack_patcher.h"`; target `msgpack::msgpack`; C++17; CMake fetches support libraries and RapidJSON.
- **How it works:** `MsgPack` provides JSON-like maps and arrays backed by copy-on-write storage, typed accessors, selectors, and MessagePack serialization. The bundled `msgpack-c` headers provide low-level pack/unpack and buffer types. `apply_patch()` implements add, remove, replace, move, copy, test, and Xapiand-specific increment/decrement operations over the DOM. RapidJSON and `std::string_view` adaptors are included.
- **Key API:**
  - `class MsgPack`
  - `MsgPack::ARRAY()`
  - `doc["key"]`, `push_back(value)`
  - `std::string MsgPack::serialise() const`
  - `static MsgPack MsgPack::unserialise(std::string_view)`
  - `apply_patch(const MsgPack&, MsgPack&)`
  - Low-level `msgpack::pack`, `msgpack::unpack`, `msgpack::sbuffer`
- **Example:**
  ```cpp
  #include "msgpack.h"
  #include "msgpack_patcher.h"
  MsgPack doc = {{"name", "Neo"}, {"tags", {"chosen"}}};
  doc["tags"].push_back("operator");
  auto wire = doc.serialise();
  auto copy = MsgPack::unserialise(wire);
  ```
- **Use it when:**
  - Passing structured values between services or persisting JSON-like documents.
  - You need copy-on-write mutation and JSON-Patch operations.
- **Do not use it when / gotchas:**
  - The bundled MessagePack headers and wrapper have different licensing terms.
  - Its default RapidJSON parse flags accept comments, trailing commas, and `NaN`/`Inf`, which is not strict JSON.

### cluster
[github.com/Kronuz/cluster](https://github.com/Kronuz/cluster) &middot; depends on: `reactor`
- **What it is:** A header-only UDP multicast substrate providing typed, token-scoped bus framing and a generic Raft implementation.
- **Header / target:** `#include "bus.h"` and `#include "raft.h"`; target `cluster::cluster`; C++20; requires standalone Asio transitively through `reactor`.
- **How it works:** `cluster::Bus` owns one multicast UDP socket and receive loop, and frames messages as version, type, serialized token, and content. It rejects malformed frames, newer versions, out-of-range types, and mismatched cluster tokens before dispatching on the bus reactor thread. `cluster::Raft` supplies terms, roles, votes, append, commit, election, and application hooks, but membership gossip is not implemented despite the README describing that future layer.
- **Key API:**
  - `cluster::Bus(major, minor, token, max_type, Handler)`
  - `set_options(reactor::UdpOptions)`
  - `start(port)`, `send(type, payload)`, `io()`
  - `cluster::Raft` with injected bus, node, state, and apply seams
  - Message frame: `[major][minor][type][serialise_string(token)][content]`
- **Example:**
  ```cpp
  #include "bus.h"
  cluster::Bus bus(1, 0, "my-cluster", 32,
      [](int type, std::string_view body, const auto&) { dispatch(type, body); });
  bus.set_options({});
  bus.start(58880);
  bus.send(5, payload);
  ```
- **Use it when:**
  - Building multicast discovery, replicated state, or leader-election substrates.
  - You need Raft without binding the library to a database or shard model.
- **Do not use it when / gotchas:**
  - Membership gossip/node-table support is not implemented.
  - The application must supply node types, lifecycle hooks, message codecs, and command application.

### prism
[github.com/Kronuz/prism](https://github.com/Kronuz/prism) &middot; depends on: `http`, `http-log`, `logger`, `traceback`
- **What it is:** A C++20 HTTP application server that composes reactor, HTTP parsing/routing, compression, access logging, and error handling into a runnable service.
- **Header / target:** Prism is primarily an executable worked example rather than a reusable public-header target; inspect `src/main.cc` and the CMake target `prism`; C++20; dependencies are fetched through CMake, including standalone Asio, `reactor`, `http`, `http-parser`, `radix-router`, `compressors`, `logger`, `term-color`, and `traceback`.
- **How it works:** Prism builds a plain `http::Router` of views on top of `HttpAsioService`. Reactor owns the per-core Asio loops and off-reactor worker pool; HTTP owns parser integration, request/response framing, negotiation, conditional requests, ranges, and compression. Access logging wraps the handler, captures response metadata and bounded bodies, and converts uncaught handler failures into logged 500 responses with optional tracebacks. The demo routes show content negotiation, echoing, JSON logging, image previews, and compression.
- **Key API:**
  - `http::Router`
  - `http::HttpHandler`
  - `http::ResponseWriter::send`, `status`, `write`, `end`
  - `http::HttpAsioService`
  - CLI: `prism [PORT] [-v|-vv|-q] [--no-tracebacks]`
- **Example:**
  ```cpp
  // prism wires router + access log + compression + traceback together.
  // See the repo's own main() for the assembled form; the shape is the
  // http::HttpHandler subclass shown under `http`, plus:
  http::HttpAsioService service(logged, 4, 2, 256);
  service.enable_compression();
  service.start(8880);
  ```
- **Use it when:**
  - Starting a conventional HTTP service with logging, compression, negotiation, and errors already wired.
  - Learning the intended composition of the Kronuz networking libraries.
- **Do not use it when / gotchas:**
  - The repository is a complete demo/application shell, not a single-purpose HTTP primitive.
  - Replace the demo routes with application handlers rather than reimplementing the transport stack.

## Domain: geospatial, text, diagnostics

*Geometry, phonetics and the observability tools.*

### cartesian
[github.com/Kronuz/cartesian](https://github.com/Kronuz/cartesian) &middot; depends on: none
- **What it is:** C++ geodesy and 3-vector library converting latitude, longitude, and ellipsoid height to geocentric Cartesian coordinates on WGS84.
- **Header / target:** `#include "cartesian.h"`; CMake target `cartesian::cartesian`; C++20.
- **How it works:** Compiled, not header-only, with datum and ellipsoid tables in `cartesian.cc`. Geodetic inputs are converted to geocentric coordinates and non-WGS84 inputs are transformed to WGS84 with a seven-parameter Helmert transform. `Cartesian` also supplies vector algebra, normalization, angular distance, formatting, and `std::hash`; operations use `double`.
- **Key API:**
  - `Cartesian(double lat, double lon, double height, Units units, int SRID = WGS84)`
  - `Cartesian(double x, double y, double z, int SRID = WGS84)`
  - `toGeodetic() -> std::tuple<double, double, double>`
  - `toLatLon() -> std::pair<double, double>`
  - `toDegMinSec() -> std::string`
  - `norm()`, `normalize()`, `inverse()`, `distance(const Cartesian&)`
  - `Cartesian::is_SRID_supported(int)`, `getSRID()`
  - Operators `*` for dot/scalar multiplication, `^` for cross product, and vector arithmetic
- **Example:**
  ```cpp
  #include "cartesian.h"
  Cartesian sf(37.7749, -122.4194, 0.0,
               Cartesian::Units::DEGREES);
  auto [lat, lon, height] = sf.toGeodetic();
  double angle = sf.distance(Cartesian(40.7128, -74.0060, 0.0,
                                       Cartesian::Units::DEGREES));
  ```
- **Use it when:**
  - Converting supported geodetic datums to WGS84-centered vectors.
  - Computing vector or angular relationships between locations.
  - Converting between geodetic and geocentric representations.
- **Do not use it when / gotchas:**
  - It models a unit-sphere direction for some operations, not full ellipsoidal geodesics.
  - Only the built-in SRIDs are supported: WGS84, NAD83/27, OSGB36, TM75, TM65, ED79, ED50, TOYA, DHDN, OEG, AGD84, SAD69, PUL42, MGI1901, GGRS87, and WGS72.
  - Unsupported SRIDs, latitude outside ±90 degrees, and zero-norm normalization throw `CartesianError`.

### htm
[github.com/Kronuz/htm](https://github.com/Kronuz/htm) &middot; depends on: `cartesian`
- **What it is:** C++ implementation of Hierarchical Triangular Mesh spatial indexing over the unit sphere.
- **Header / target:** `#include "htm.h"`; CMake target `htm::htm`; C++20.
- **How it works:** HTM recursively subdivides eight spherical root triangles into four children per level. A trixel has an `N` or `S` name followed by base-4 digits and a corresponding 64-bit ID; ancestor names are prefixes and ancestor ID ranges cover descendant trixels. The compiled implementation also provides spherical-cap constraints, corner geometry, range conversion, and boolean set operations over sorted trixels or ranges.
- **Key API:**
  - `HTM::getTrixelName(const Cartesian&)`, `getTrixelName(uint64_t)`
  - `HTM::getId(const Cartesian&)`, `getId(std::string_view)`
  - `HTM::getCorners(name)`, `getRange(name)`, `getRange(id, level)`
  - `HTM::getTrixels(...)`, `getIdTrixels(...)`
  - `HTM::trixel_union`, `trixel_intersection`, `trixel_exclusive_disjunction`
  - Corresponding `range_*` operations over sorted `range_t` vectors
  - `Constraint(Cartesian center, double radius)`
  - Constraint helpers such as `getBoundingCircle`, `intersectConstraints`, and `intersection`
- **Example:**
  ```cpp
  #include "htm.h"
  Cartesian syd(-33.8688, 151.2093, 0.0,
                Cartesian::Units::DEGREES);
  auto name = HTM::getTrixelName(syd);
  auto id = HTM::getId(syd);
  auto range = HTM::getRange(name);
  ```
- **Use it when:**
  - Indexing spherical points by hierarchical spatial cells.
  - Turning circular spherical queries into trixel or integer-ID ranges.
  - Performing boolean operations on sorted spatial-cell sets.
- **Do not use it when / gotchas:**
  - It indexes the unit sphere, not an ellipsoid or geodetic datum directly.
  - Inputs should be `Cartesian` directions; use `cartesian` first for latitude/longitude and datum conversion.
  - Set and range operations expect sorted trixel or range vectors.

### double-metaphone
[github.com/Kronuz/double-metaphone](https://github.com/Kronuz/double-metaphone) &middot; depends on: none
- **What it is:** Compiled C++20 implementation of Lawrence Philips' Double Metaphone phonetic encoder.
- **Header / target:** `#include "double_metaphone.h"`; CMake target `double_metaphone::double_metaphone`; C++20.
- **How it works:** The implementation applies rule-based pronunciation handling for English spellings and common foreign readings. It emits a primary and alternate key using the phonetic alphabet `A B F H J K L M N P R S T W X 0`, where `0` represents the “th” sound. The implementation is compiled because the rule set is large; encoding is linear in the input length.
- **Key API:**
  - `DoubleMetaphone()`
  - `DoubleMetaphone(std::string_view word)`
  - `encode() -> std::string`
  - `encode(std::string_view word) -> std::string` for the primary key
  - `encode_alternate(std::string_view word) -> std::string`
  - `encode_both(std::string_view word) -> std::pair<std::string, std::string>`
  - `name()`, `description()`
- **Example:**
  ```cpp
  #include "double_metaphone.h"
  DoubleMetaphone dm;
  auto primary = dm.encode("Smith");          // "SM0"
  auto alternate = dm.encode_alternate("Smith"); // "XMT"
  auto both = dm.encode_both("Schmidt");      // {"XMT", "SMT"}
  ```
- **Use it when:**
  - Matching names despite silent letters or spelling differences.
  - Comparing primary and plausible alternate pronunciations.
  - Building phonetic search keys for predominantly English names.
- **Do not use it when / gotchas:**
  - It is not a general multilingual pronunciation engine; foreign-language handling is limited to rules in the Double Metaphone specification.
  - `encode()` returns only the primary key; compare both keys when alternate pronunciations matter.
  - Keys are phonetic approximations and can produce collisions or miss pronunciations outside the rule set.

### soundex
[github.com/Kronuz/soundex](https://github.com/Kronuz/soundex) &middot; depends on: `strings`
- **What it is:** Header-only C++20 CRTP library providing refined language-specific Soundex encoders.
- **Header / target:** `#include "english_soundex.h"`, `#include "french_soundex.h"`, `#include "german_soundex.h"`, or `#include "spanish_soundex.h"`; CMake target `soundex::soundex`; C++20.
- **How it works:** `Soundex<Impl>` supplies the common cached-code API and each language subclass supplies its phonetic rules inline. The variants are refined encoders, not classic four-character Soundex: vowels are retained and codes are not truncated. The supported algorithms are refined English Soundex, Soundex 2 for French, Kölner Phonetik for German, and the PostgreSQL Spanish Soundex variant.
- **Key API:**
  - `Soundex<Impl>`
  - `SoundexEnglish`, `SoundexFrench`, `SoundexGerman`, `SoundexSpanish`
  - `Encoder(std::string_view word)`
  - `encode() -> std::string`
  - `encode(std::string_view word) -> std::string`
  - `name()`, `description()`
- **Example:**
  ```cpp
  #include "english_soundex.h"
  #include "spanish_soundex.h"
  auto a = SoundexEnglish("Robert").encode(); // "R901096"
  auto b = SoundexEnglish("Rupert").encode(); // "R901096"
  auto c = SoundexSpanish("Vaca").encode();   // "B1020"
  ```
- **Use it when:**
  - Matching approximate names within one of the four supported language rule sets.
  - You need header-only phonetic encoding and a reusable encoder interface.
  - You want longer refined codes rather than classic fixed-width Soundex.
- **Do not use it when / gotchas:**
  - Do not expect classic four-character Soundex output; `Robert` produces `R901096`.
  - Choose the language-specific encoder deliberately; the rules and collisions differ by language.
  - French, German, and Spanish headers require the sibling `strings` library.

### string-similarity
[github.com/Kronuz/string-similarity](https://github.com/Kronuz/string-similarity) &middot; depends on: `soundex`, `strings`
- **What it is:** Header-only C++20 collection of normalized string similarity and distance metrics.
- **Header / target:** Include the specific metric header, such as `#include "levenshtein.h"`, `#include "jaro.h"`, `#include "jaro_winkler.h"`, `#include "lcsubstr.h"`, `#include "lcsubsequence.h"`, `#include "jaccard.h"`, `#include "sorensen_dice.h"`, or `#include "phonetic_metric.h"`; CMake target `string_similarity::string_similarity`; C++20.
- **How it works:** `StringMetric<Impl>` provides a common bound-or-unbound interface with `distance()` and `similarity()` in `[0,1]`. Levenshtein uses normalized edit distance, Jaro uses matched characters and transpositions, Jaro-Winkler adds a common-prefix boost, LCSubstr and LCSubsequence compute longest contiguous and non-contiguous matches, Jaccard compares character sets, and Sørensen-Dice compares character bigrams. `PhoneticMetric<Encoder, Metric>` encodes both inputs before delegating to another metric; the metrics are inline templates.
- **Key API:**
  - `StringMetric<Impl>`
  - `Metric(std::string_view fixed = {}, bool icase = true)`
  - `distance(a, b) -> double`, `similarity(a, b) -> double`
  - `Levenshtein`, `Jaro`, `Jaro_Winkler`, `LCSubstr`, `LCSubsequence`
  - `Jaccard`, `Sorensen_Dice`
  - `PhoneticMetric<Encoder, Metric>`
  - `name()`, `description()`
- **Example:**
  ```cpp
  #include "levenshtein.h"
  #include "jaro_winkler.h"
  Levenshtein lev;
  auto d = lev.distance("kitten", "sitting");
  Jaro_Winkler jw;
  auto s = jw.similarity("MARTHA", "MARHTA");
  ```
- **Use it when:**
  - Ranking approximate text matches with normalized scores.
  - Comparing names using Jaro-Winkler or phonetic encodings.
  - Measuring set, bigram, substring, subsequence, or edit similarity.
- **Do not use it when / gotchas:**
  - Metrics default to case-insensitive comparison by upper-casing inputs; pass `false` when case matters.
  - Empty inputs produce distance `1` and similarity `0`, including the identical-empty case according to the documented behavior.
  - Jaccard operates on character sets and Sørensen-Dice on character bigrams, not word tokens.

### boolean-parser
[github.com/Kronuz/boolean-parser](https://github.com/Kronuz/boolean-parser) &middot; depends on: none
- **What it is:** C++17 lexer and parser that converts boolean query text into an RPN token stream and optionally an AST.
- **Header / target:** `#include "BooleanParser.h"`; CMake target `boolean_parser::boolean_parser`; C++17.
- **How it works:** The constructor lexes input with a byte-oriented lexer and applies Dijkstra's shunting-yard algorithm to produce a `std::list<Token>` RPN queue. `Parse()` consumes the queue to build typed AST nodes. Operators are precedence-ordered as `NOT > AND > MAYBE > XOR > OR`, and adjacent terms receive an implicit `OR`.
- **Key API:**
  - `explicit BooleanTree(std::string_view input)`
  - `Parse()`
  - `empty()`, `size()`, `front()`, `back()`, `pop_front()`, `pop_back()`
  - `Token::get_type()`, `Token::get_lexeme()`
  - `BaseNode::getType()`
  - Binary nodes `getLeftNode()`, `getRightNode()`
  - `NotNode::getNode()`, `IdNode::getId()`
  - `PrintTree()`
- **Example:**
  ```cpp
  #include "BooleanParser.h"
  BooleanTree tree("a OR (b AND NOT c)");
  while (!tree.empty()) {
      const Token& token = tree.front();
      tree.pop_front();
  }
  ```
- **Use it when:**
  - Parsing small boolean query languages.
  - Consuming RPN directly to construct a domain-specific query.
  - Building an inspectable AST for boolean expressions.
- **Do not use it when / gotchas:**
  - Constructing or consuming the RPN queue mutates the tree; call `Parse()` before consuming it if you need the AST.
  - Quoted phrases and bracket lists are single `Id` tokens with delimiters preserved.
  - Malformed input throws `LexicalException` or `SyntacticException`; oversized tokens and unclosed delimiters are rejected.

### logger
[github.com/Kronuz/logger](https://github.com/Kronuz/logger) &middot; depends on: `scheduler`, `term-color`
- **What it is:** C++20 asynchronous and deferred logger designed for low-contention hot paths and cancellable slow-operation messages.
- **Header / target:** `#include "logger.h"`; CMake target `logger::logger`; C++20.
- **How it works:** Severe messages write inline, routine messages are queued to a LOG thread keyed at the current time, and delayed messages are scheduled at `now + delay`. A returned `Log` handle can cancel or replace a delayed message atomically; dropping it cancels or swaps it according to the macro. Handlers receive each line, and `max_pending` provides optional backpressure by dropping excess routine asynchronous messages and emitting a coalesced summary.
- **Key API:**
  - `Logging::config` with `log_level`, color, timestamp, thread, location, marker, and pending-message settings
  - `Logging::hooks` with exception, backtrace, thread-name, and timestamp callbacks
  - `Logging::add_handler(std::unique_ptr<Logger>)`, `Logging::finish()`
  - `StreamLogger`, `StderrLogger`, `SysLog`
  - Macros `L_INFO`, `L_WARNING`, `L_ERR`, `L_EXC`, `L_*_ONCE`, `L_DELAYED_*`, `L_TIMED`, `L_STACKED`, `L_PRINT`
  - `Log::clear()`, `unlog()`, `age()`
- **Example:**
  ```cpp
  #include "logger.h"
  int main() {
      Logging::config.log_level = LOG_INFO;
      Logging::add_handler(std::make_unique<StderrLogger>());
      L_INFO("starting with {} workers", 8);
      L_DELAYED_200("request {} is slow", request_id);
      Logging::finish();
  }
  ```
- **Use it when:**
  - Many threads log routine messages from hot paths.
  - Slow-operation notices are armed and usually cancelled.
  - One ordered writer thread and predefined handlers are sufficient.
- **Do not use it when / gotchas:**
  - It is not a general structured logging framework with arbitrary sinks and routing.
  - A delayed message must be cleared or unlogged according to the intended macro behavior before the operation completes.
  - Call `Logging::finish()` during orderly shutdown to drain and stop the logging thread.

### term-color
[github.com/Kronuz/term-color](https://github.com/Kronuz/term-color) &middot; depends on: `static-string`
- **What it is:** Header-only C++20 library for compile-time ANSI colors with runtime terminal-depth resolution.
- **Header / target:** `#include "colors.h"` for named colors and `rgb()`/`brgb()`, `#include "color_tools.hh"` for runtime colors, and `#include "collapse.hh"` for resolution; CMake target `term_color::term_color`; C++20.
- **How it works:** Named colors are `static_string` constants containing stacked ANSI 16-color, 256-color, and 24-bit truecolor escapes in that order. Compile-time concatenation makes expressions such as `RED + "text" + CLEAR_COLOR` constants. `collapse()` reduces stacked escapes to one depth, while `apply()` also handles TTY gating, `NO_COLOR`, and automatic/always/never policy; `color_tools.hh` supplies runtime HSV-to-RGB conversion and a runtime `color` class.
- **Key API:**
  - Named constants such as `RED`, `STEEL_BLUE`, `CLEAR_COLOR`, `NO_COLOR`
  - `rgb(r, g, b)`, `brgb(r, g, b)`, `rgba(...)`, `brgba(...)`
  - `hsv2rgb(h, s, v, r, g, b)`
  - `color::ansi()`, `color::ansi(bool bold)`
  - `collapse(std::string_view, depth)`, `apply(std::string_view, mode, target, bool isatty)`
  - `detect_depth()`
- **Example:**
  ```cpp
  #include "colors.h"
  #include "collapse.hh"
  std::string line = std::string(RED) + "error" + CLEAR_COLOR;
  auto plain = term_color::collapse(line, term_color::depth::none);
  auto tty = term_color::apply(line, term_color::mode::automatic,
                               term_color::target::automatic, true);
  ```
- **Use it when:**
  - Defining a compile-time color palette for CLI or log output.
  - Resolving colors consistently for TTYs, pipes, files, and `NO_COLOR`.
  - Converting runtime HSV/RGB values to ANSI escapes.
- **Do not use it when / gotchas:**
  - Stacked truecolor escapes are best-effort; collapse them for sinks requiring one known tier.
  - A separate adjacent SGR escape can make a stacked run length non-multiple-of-three and prevent `collapse()` from recognizing it; use `brgb()` for bold.
  - Include `CLEAR_COLOR` around colored output when composing raw escapes.

### traceback
[github.com/Kronuz/traceback](https://github.com/Kronuz/traceback) &middot; depends on: `errno-names`, `nanosleep`, `strings`, `term-color`
- **What it is:** C++20 call-stack capture, symbolization, optional macOS source locations, and opt-in whole-process crash dumping.
- **Header / target:** `#include "traceback.h"`; CMake target `traceback::traceback`; C++20.
- **How it works:** The default compiled library captures return addresses and resolves symbols with `dladdr` and `abi::__cxa_demangle`, returning demangled names and offsets. On macOS, optional `atos` integration adds file and line information. `TRACEBACK_HOOKS` adds a fixed lock-free thread registry and SIGUSR2-based all-thread stack collection; `TRACEBACK_THROW_HOOKS` additionally interposes C++ throws and global allocators to retain throw-site stacks.
- **Key API:**
  - `traceback::capture(size_t skip = 1, size_t max = 128)`
  - `traceback::describe(const void*)`
  - `traceback::format(std::string_view, size_t skip = 2, size_t max = 128)`
  - `traceback::format(const std::source_location&, ...)`
  - `traceback::enable_atos(bool)`, `atos_enabled()`
  - `traceback::backtrace()`, `traceback::traceback(...)`
  - With `TRACEBACK_HOOKS`: `register_thread`, `deregister_thread`, `thread_registration`, `dump_callstacks`, `callstacks_snapshot`
  - With `TRACEBACK_THROW_HOOKS`: `exception_callstack`
- **Example:**
  ```cpp
  #include "traceback.h"
  std::string report = traceback::format(
      std::source_location::current());
  auto frames = traceback::capture();
  ```
- **Use it when:**
  - Formatting best-effort backtraces in error paths.
  - Adding optional all-thread crash reports to a native process.
  - Enabling macOS `atos` file/line resolution when symbol names are insufficient.
- **Do not use it when / gotchas:**
  - Build with `-fno-omit-frame-pointer` for reliable optimized stack walking.
  - Keep `TRACEBACK_THROW_HOOKS` off unless throw-site stacks are required; allocator interposition conflicts with allocators and sanitizers and can corrupt heaps.
  - The crash dumper is opt-in, has fixed registry/frame limits, and requires signal-handler installation and thread registration.

### located-exception
[github.com/Kronuz/located-exception](https://github.com/Kronuz/located-exception) &middot; depends on: none
- **What it is:** C++20 exception hierarchy that captures throw-site function, file, and line and formats messages with `std::format`.
- **Header / target:** `#include "exception.h"`; CMake target `located_exception`; C++20.
- **How it works:** Compiled `exception.cc` supplies out-of-line constructors and lazy message/context formatting. `BaseException` stores pointers to `__func__` and `__FILE__` plus the source line, while derived types also inherit matching standard exceptions. `THROW` captures the current throw site and `RETHROW` preserves the original location through a caught variable named `exc`.
- **Key API:**
  - `BaseException::function`, `filename`, `line`
  - `get_message()`, `get_context()`, `empty()`
  - `Exception`, `Error`, `InvalidArgument`, `OutOfRange`, `SystemExit`
  - `THROW(type, format, args...)`
  - `RETHROW(type, format, args...)`
  - `SystemExit(int code)`
- **Example:**
  ```cpp
  #include "exception.h"
  void load() {
      THROW(InvalidArgument, "bad value {}", 7);
  }
  try {
      load();
  } catch (const BaseException& exc) {
      std::printf("%s\n", exc.get_context());
  }
  ```
- **Use it when:**
  - Errors need origin information without a full backtrace.
  - Exceptions should be catchable as both project-specific and standard exception types.
  - Throw-site messages benefit from C++20 formatting.
- **Do not use it when / gotchas:**
  - It captures one throw location, not a call stack.
  - `RETHROW` requires the caught exception variable to be named exactly `exc`.
  - The formatting backend is part of the ABI; keep C++ standard and `WITHOUT_FORMAT` settings consistent between library and consumers.

### errno-names
[github.com/Kronuz/errno-names](https://github.com/Kronuz/errno-names) &middot; depends on: none
- **What it is:** Header-only C++17 mapping from platform-defined `errno` values to symbolic names and descriptions.
- **Header / target:** `#include "error.hh"` for the API, optionally `#include "errnos.h"` for the generated platform errno table; CMake target `errno_names`; C++17.
- **How it works:** The headers build a compile-time list of errno constants available on the current platform and use it to map integer values to names. `error::name(int)` returns the symbolic constant, while `error::description(int)` uses `strerror_r`-derived descriptions. The table is platform-sensitive and descriptions are initialized according to the libc locale when first built.
- **Key API:**
  - `error::name(int errnum) -> std::string_view` or string-like result
  - `error::description(int errnum) -> std::string`
  - Unknown values map to `"UNKNOWN"` and `"Unknown error"`
- **Example:**
  ```cpp
  #include "error.hh"
  #include <cerrno>
  int err = ENOENT;
  auto name = error::name(err);
  auto description = error::description(err);
  ```
- **Use it when:**
  - Logging system-call failures with stable symbolic names.
  - Reporting both `EINVAL`-style identifiers and human-readable descriptions.
  - Supporting Linux, macOS, and BSD errno sets without hardcoding one platform.
- **Do not use it when / gotchas:**
  - It is not an error-handling or exception framework.
  - Symbolic coverage is limited to errno constants defined by the build platform.
  - Descriptions come from libc and can vary with locale and initialization timing.

### system
[github.com/Kronuz/system](https://github.com/Kronuz/system) &middot; depends on: `io`, `strings`
- **What it is:** C++20 compiled library for process, memory, file-descriptor, filesystem, and platform information.
- **Header / target:** `#include "system.hh"` for process/system probes and `#include "memory_stats.h"` for memory and disk statistics; CMake target `system::system`; C++20.
- **How it works:** The library has compiled `system.cc` and `memory_stats.cc` units with portable feature detection rather than a generated `config.h`. On Linux it reads `/proc` and `/proc/self/fd` through EINTR-safe I/O helpers; platform-specific implementations provide process and resource statistics. `memory_stats.h` exposes current and total memory, virtual memory, inode, and disk counters, while `system.hh` exposes file limits and compiler/OS/architecture strings.
- **Key API:**
  - `get_open_files_per_proc()`, `get_max_files_per_proc()`
  - `get_open_files_system_wide()`, `get_max_files_system_wide()`
  - `get_current_ram() -> std::pair<int64_t, int64_t>`
  - `get_total_virtual_used()`, `get_total_ram()`
  - `get_current_memory_by_process(bool resident = true)`
  - `get_total_virtual_memory()`
  - `get_total_inodes()`, `get_free_inodes()`
  - `get_total_disk_size()`, `get_free_disk_size()`
  - `check_compiler()`, `check_OS()`, `check_architecture()`
- **Example:**
  ```cpp
  #include "system.hh"
  #include "memory_stats.h"
  auto open = get_open_files_per_proc();
  auto ram = get_current_ram();
  auto disk = get_free_disk_size();
  ```
- **Use it when:**
  - Exposing process resource counters in diagnostics or health endpoints.
  - Reporting memory, virtual-memory, inode, and disk capacity.
  - Displaying compile-time platform and architecture information.
- **Do not use it when / gotchas:**
  - Counters are platform-dependent and may be unavailable or approximate on some systems.
  - `/proc`-based probes require a compatible proc filesystem; do not assume Linux semantics elsewhere.
  - It is not a portable replacement for a complete OS metrics agent or telemetry system.

---

## Building a service

The shortest path from nothing to a running HTTP service, and what each layer owns.

- **`reactor`** is the bottom: `reactor::TcpServer` runs coroutine sessions across a
  shared-nothing reactor pool, `reactor::UdpServer` handles datagrams and multicast. It
  owns accept, thread distribution and graceful shutdown, and nothing above the socket.
- **`http-parser`** owns incremental HTTP/1.x syntax only. It accepts a byte at a time and
  knows nothing about routing, storage, compression or dispatch.
- **`http`** joins the two through `http_asio.h` / `HttpAsioService`: its session feeds
  bytes to the parser, builds an `http::Request`, calls your `HttpHandler`, and frames
  whatever you write to the `ResponseWriter`.
- **`radix-router`** is the path-dispatch primitive underneath `http::Router`. Use it
  directly when you need path routing that is not HTTP.
- **`http-log`** wraps a handler rather than sitting beside it, so the request path is
  `reactor -> http-parser/http -> http-log -> your handler`.
- **`compressors`** supplies the codecs used for response compression, storage records and
  flume blocks.
- **`storage`** and **`flume`** are the persistence and transfer pair: append-only blobs
  with stable offsets, and framed checksummed file transfer over any byte channel.
- **`cluster`** sits beside the TCP path on `reactor::UdpServer` for multicast framing and
  Raft transport. A single-node service does not need it.

The minimum viable service. Note the real shape: your application subclasses
`http::HttpHandler`, owns a `Router`, and registers routes with
`route(method, path, handler)` where the handler takes three arguments including
`http::Params` for the named path parameters.

```cpp
#include "http_asio.h"
#include "http_router.h"

class App : public http::HttpHandler {
    http::Router router_;
public:
    App() {
        router_.route("GET", "/kv/:key",
            [](const http::Request&, http::ResponseWriter& resp, const http::Params& p) {
                resp.send(200, std::string(p.get("key")));
            });
    }
    void handle(const http::Request& req, http::ResponseWriter& resp) override {
        router_.handle(req, resp);
    }
};

App app;
http::HttpAsioService service(app, /*reactors=*/4, /*workers=*/2, /*queue_limit=*/256);
service.start(8080);
```

Override `on_request_body` on your handler to stream a request body instead of buffering
it. See [`examples/kv_store.cc`](https://github.com/Kronuz/http/blob/main/examples/kv_store.cc)
for the complete version.

Wrap the router in `http_log::AccessLog` to get request logging, add `traceback` for crash
handlers, and you have approximately what `prism` is. Read
[prism](https://github.com/Kronuz/prism) for the assembled version.

---

## If you modify a library

Working rules, in priority order.

1. **Add, do not break.** New overloads, new optional parameters with defaults, new
   headers and new policy hooks are all safe. Renames, removals, changed defaults,
   reordered enumerators and altered serialization formats are not. `cuuid`, `storage`,
   `flume` and `msgpack` all have formats that persist beyond the process; changing them
   silently breaks readers you cannot see.
2. **Keep the dependency set honest.** A leaf library that suddenly pulls three others
   stops being droppable into an unrelated project. Every existing dependency in a
   CMakeLists carries a comment explaining exactly which include forced it. Continue that
   practice, or do not add the dependency.
3. **Update the four artifacts together.** README, tests, `examples/demo.cc`, and the
   CMake comments. A change that updates only the header leaves the next agent with a
   README that lies.
4. **Prove performance claims.** Several of these libraries exist specifically because a
   generic answer was too slow, and some carry benchmarks (`hashes` has one comparing hash
   families for perfect-hash dispatch). If you optimize, measure before and after on a
   realistic workload and put the numbers in the commit message.
5. **Preserve the constexpr property.** `char-classify`, `hashes`, `constexpr-phf`,
   `ctrie`, `static-string` and `enum-reflection` are valuable precisely because they work
   during constant evaluation. An innocuous-looking change can quietly push a function to
   runtime. Keep the `static_assert`s in the tests; they are the guard.
6. **Respect the stated non-goals.** Several READMEs say plainly what a library is not:
   `hashes` is not cryptographic, `repr` is not reversible, `split` is not a CSV parser,
   `bloom-filter` cannot remove. Do not fix these by expanding scope. Write a new library.

## Provenance

All of these were extracted from [Xapiand](https://github.com/Kronuz/Xapiand), a
distributed RESTful search engine built on Xapian, which remains the largest consumer and
the reason most of them have the shape they do. The design notes behind each one are being
written up as the *Familiars* series on
[kronuz.github.io](https://kronuz.github.io/blog/), which is still in draft and not yet
published, so this file is the current reference.

Repository: `https://github.com/Kronuz/<name>` for every library named here.
