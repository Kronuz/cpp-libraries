# Moving pins past October 30, 2026

> Status: CURRENT (2026-11-01). Read from each library's `CHANGELOG.md` and default branch at
> 2026-11-01 16:45 PST.

Consumers pin these libraries by commit, so nothing here reaches a build until a pin moves. This
note covers the libraries the October 30-31 performance campaign touched, and lists every change
made to them from 2026-10-30 on that changes a result, an exception or a build when a pin moves
past it. Each entry has the library, the start and fix commits, the inputs whose results change,
and how a consumer finds out whether it sends them. The full entries, with their numbers and
oracles, are in each library's `CHANGELOG.md`; libraries outside the campaign (completion,
journal, consensus, cluster, strata, prospect) keep theirs there too.

- **Start** is the library's default-branch head at 2026-10-30 00:00 PDT, before the first
  change listed here. A pin at or before it gives the old results.
- **Fix** is the first commit with the new results. Every later commit on the default branch
  carries it; no branch diverges.
- Xapiand (`3fe13a2f`, 1.0.0-alpha.10) and Detent's `cmake/dependencies.json` pin commits older
  than every fix below. In-family pins move in waves; compare a pin with the two columns.

**Two changes need an owner decision when Xapiand's pins move, because Xapiand's users see
them:** boolean-parser regroups queries and rejects some it accepted, and datetime changes which
strings parse as dates, and so how schema detection types a new field. Three more change what
Xapiand returns or stores: string-similarity changes the order of similarity-sorted results, htm
changes the id of a point near a cell edge on builds that fuse multiply-adds (arm64, x86 with
FMA), so an index written by such a build needs those points reindexed, and msgpack merges a
document's repeated keys. fs, storage and url-parser normalize a path as Python's
`os.path.normpath` does, which changes the paths Xapiand builds from an empty data directory and
from endpoints whose paths hold a `..`.

**Three need code changes when the pins move:** `http` handlers are coroutines, `reactor` has no
worker pool and new constructors, and `http-log` follows `http`. http-parser rejects what request
smuggling relies on unless a consumer sets `lenient_http_headers`. The other changes fix crashes,
hangs, wrong answers and timing.

## Summary

| Library | Start | Fix | What changes | Consumers |
|---|---|---|---|---|
| [boolean-parser](#boolean-parser) | `41a20b5` | `00b3021`, `172a5c2` | Query grouping; malformed queries throw at construction | Xapiand: **owner decision** |
| [datetime](#datetime) | `fce3d4d` | `fe618d8`, `03f36fa`, `773205b`, `22d1f6a` | Which strings parse; `+12M`; `is_utc`; fractions before 1970; field widths with a newer strict-stox | Xapiand: **owner decision** |
| [string-similarity](#string-similarity) | `ddfb8d1` | `efba168`, `0939c0c`, `c0825ff` | Jaro, Jaro-Winkler, Dice, weighted Levenshtein, phonetic scores | Xapiand sort keys |
| [htm](#htm) | `a0321ab` | `cf5177b`, `9006a84` | Ids of points near a cell edge on fusing builds | Xapiand geo index: reindex |
| [msgpack](#msgpack) | `3c408cf` | `d054ea1`, `c913966`, `d8fa3e6`, `f083ad7`, `adac439`, `1c851dc` | Maps that repeat a key or have a non-string key; growing arrays of maps; `replace` and `put` over a read value; `erase()`'s count; `to_string()` of non-string keys and NaN | Xapiand documents |
| [enum-reflection](#enum-reflection) | `79fe3fa` | `2a5da3a` | A crafted name no longer matches a member | http-parser, msgpack, Xapiand |
| [storage](#storage) | `7b9abd1` | `90aec94`, `a1e49db`, `217e731`, `b141849` | Records past 4 GiB; damaged records; volume locks; an empty, `.` or `..` base path | Xapiand |
| [strict-stox](#strict-stox) | `f0f7374` | `7d7f5dd`, `a1b03fb` | Input of 64 bytes or more parses; decimals libc aborted on | datetime, msgpack, storage, Detent, Xapiand |
| [strings](#strings) | `62fb121` | `bb85615` | `indent`, empty-search `replace`, `hasupper` | fs, soundex, string-similarity, system, traceback, Detent, Xapiand |
| [stringified](#stringified) | `c8c9033` | `1c1fb3e` | Copies no longer dangle; `c_str()` stays in bounds | fs, storage, Xapiand |
| [repr](#repr) | `2063945` | `3191c08` | `max_size == 1` | msgpack, strings, Detent, Xapiand |
| [allocators](#allocators) | `e8fb173` | `085331c`, `2fc537f`, `e38f759`, `7cdb0f8` | Pool sharing, equality, propagation; `construct` moves | none found |
| [queue](#queue) | `7df74b2` | `e94be7d`, `31552f9` | Who a pop or `clear()` wakes; `count()` after move assignment | server, Xapiand |
| [scheduler](#scheduler) | `ae3f0f9` | `36afada`, `62a4fe8` | A task no longer waits out the 30 s idle sleep | logger, Detent, Xapiand |
| [logger](#logger) | `ce27b90` | `dc1fe62`, `c7332d6` | Write delay, crash window, timestamps | Detent, Xapiand, http-log, prism |
| [compressors](#compressors) | `17873b2` | `f157dab`, `8f57675`, `533bee4`, `430870c` | Damaged input throws; XXH32 on big-endian hosts and past 4 GiB; `XXH32_state_t` fields | storage, flume, http, strata, Detent, Xapiand |
| [generation-cache](#generation-cache) | `00762bd` | `715f2af`, `89baa5b`, `2930a64`, `32a2b4a` | Exception paths; writers no longer starve | Detent |
| [fs](#fs) | `ce16118` | `14932b9`, `0b5f78e`, `d6d8bc2`, `8848b49`, `bf10f39`, `8e5f3d2` | `copy_file` truncates, refuses the same file, reports short writes; empty paths; `normalize_path` is `os.path.normpath` | Xapiand |
| [btree](#btree) | `25f9494` | `d81f2a3`, `a56261d`, `512febb` | Allocation-failure behavior; slot layout | strata, Detent |
| [cartesian](#cartesian) | `6eab8ed` | `79ed663`, `7066e9e` | `std::hash<Cartesian>` values | none found |
| [random](#random) | `115f3f3` | `0667b61` | The sequence | scheduler, Detent, Xapiand |
| [url-parser](#url-parser) | `4424e25` | `2c9ea8e`, `1cdcb53` | `normalize_path` and `PathParser` on empty, `.` and `..` paths | Xapiand |
| [http-parser](#http-parser) | `52a30d0` | `21c8f30`, `ab8377c`, `62ac7f3`, `0aeec14`, `e2f23b9`, `5cb4409` | Rejects request smuggling unless lenient; new error numbers | http, http-log, prism, Detent |
| [http](#http) | `c23bb99` | `bda9b5a`, `fce24c6`, `25f4b99`, `3caaeda` | Coroutine handlers (**code change**); trailers; `CONNECT`; HTTP/1.0 with Transfer-Encoding closes | http-log, prism, Detent |
| [reactor](#reactor) | `ef26c30` | `67e22a6`, `76c32b4` | No worker pool; `AdmissionGate`; constructors (**code change**) | http, cluster, consensus, prism, Detent |
| [http-log](#http-log) | `6ee47af` | `c7772ab` | `AccessLog::handle` is a coroutine (**code change**) | prism, Detent |
| [times](#times) | `666dfdd` | `cb75580`, `1f1f9c0` | Seconds past `int`; fractions on x86; negative values folded | none found |
| [time-point](#time-point) | `2f1f7f9` | `624c2e9` | Instants before the epoch on clocks finer than a nanosecond; coarse clocks build | none found |
| [io](#io) | `3893d47` | `6524ce0` | `pread` reads to the full count | fs, pki, system, Xapiand |
| [math](#math) | `2730483` | `01ad763`, `5486d04` | 8- and 16-bit overflow; `modulus` of the lowest value and of zero; `min<double>` | Xapiand |
| [errno-names](#errno-names) | `a5ab101` | `0ec0801` | Descriptions on glibc | storage, traceback, Xapiand |
| [namegen](#namegen) | `70bd983` (in `Kronuz/fantasyname`) | `c0f9393`, `72b3f1c`, `fd7ab7f`, `c8faf70` | Every alternative equally likely, so a seed gives other names; one engine per thread | Xapiand |
| [uinteger_t](#uinteger_t) | `85316dd` | `a39ede0`, `bd7bab1`, `6ff439f`, `10cf088`, `eb588dc` | Digits outside the base throw; base-256 leading zero bytes; `x *= 1` after a right shift; `sizeof` 88 and its own container | base-x, Xapiand |
| [base-x](#base-x) | `54a9326` | `8935fe6`, `c3965ec`, `b8fc1a2`, `2507a82`, `d3d9f23`, `27be05e`, `c599da0` | RFC 4648 text and decoding; Bitcoin and Ripple leading zeros; all-zero bytes; stricter `decode` and `is_valid` | Xapiand (the ids it mints keep their text) |

## Commits not to pin

Some changes broke something that a later commit fixes. Pin before the first column or at or after
the second.

| Library | Broken from | Fixed in | What goes wrong |
|---|---|---|---|
| compressors | `0498bf5` | `8f57675` | A crafted 98 KB LZ4 stream makes `decompress_lz4` reserve 64 MB; a refused allocation throws `bad_alloc` instead of `LZ4CorruptVolume`. |
| strict-stox | `70b8325` | `199e0be` | The fast path ignores the rounding mode: under `fesetround(FE_UPWARD)`, `strict_stod("-0.1")` gives `-0.1` where libc gives `-0.099999999999999991` (2,358 of 30,012 random texts). |
| logger | `dc1fe62` | `06a27d2` | A `clears` line due within 1 ms can be written before an immediate line logged earlier. |
| generation-cache | `715f2af` | `2930a64` | A `Key` or `Value` copy or move that throws in `try_insert` or in a rehash loses entries or leaves a slot that a later `get` dereferences. |
| fst | `b1e8ff3` | `8058003` | Verifying a node-registry hit reads past the end of the bytes the builder has written (heap use after free under ASan). |
| string-similarity | `0939c0c` | `c0825ff` | `PhoneticMetric<Encoder, Sorensen_Dice>` bound to a string scores 0 for every pair whose codes differ. |
| stringified | `2c78a1d` | `0053465` | A string literal passed to an overload set over `stringified` and `std::string_view` or `const std::string&` is ambiguous and does not compile. |
| metrics | `aa7a3d8` | `4890fc0` | `AtomicCounter::add` racing an add that saturates the counter can wrap it, permanently (`9207dd3` narrows the window and does not close it). |
| queue | `b1b38b0` | `e94be7d` | Waits block forever: two `Queue`s sharing one state, `clear()` with parked producers, `QueueSet::erase`, and a pop that leaves the size at or above the threshold. |
| fs | `14932b9` | `d6d8bc2` | `copy_file` onto the same file (the same path, a hard link or a symlink to it) truncates the source to 0 bytes and returns 0. |
| allocators | `2fc537f` | `e38f759` | Container copy assignment shares the source's pool, so the two containers used from two threads corrupt the heap. |
| uinteger_t | `8f1345e` | `dabd824` | A refused allocation of the carry limb in `x += y` or `++x` leaves `x` half written, with a zero top limb. |
| uinteger_t | `bd7bab1` | `819daa4` | On a 32-bit `size_t`, `digits()` or `from_digits()` of 512 MiB or more wraps a size and writes past its buffer. |
| uinteger_t | `6e74834` | `b012716` | On a 32-bit `size_t`, `digits()` of a value of 2^32 bits or more wraps its bit count and returns wrong digits. |
| base-x | `8572a00` | `fdee12d` | Does not compile: it calls uinteger_t's chunk primitives, which the uinteger_t it pins lacks. |
| base-x | `1687e9a` | `8935fe6` | Does not compile: it calls `digits()` and `from_digits()`, which the uinteger_t it pins (`aeeeb67`) lacks. |
| base-x | `2507a82` | `b468653` | On a 32-bit `size_t`, an RFC 4648 encode of 512 MiB or more wraps its digit count and writes wrong text. |
| random | `0667b61` | `86bd0f5` | On MSVC: `0667b61` does not compile, and from `8df54fb` the 128-bit multiply swaps its halves, so `random_int` returns values outside its range on x64. |

## boolean-parser

Start `41a20b5`, fix `00b3021`. Xapiand builds its query from the RPN queue
(`src/query_dsl.cc:952`), so a regrouped query matches different documents.

Inputs that change:

- An implicit `OR` (two operands with no operator between them: a term or `)`, then a term, `(`
  or `NOT`) that follows another operator in the same parentheses. `a AND b c` was
  `a OR (b AND c)` and is `(a AND b) OR c`; `NOT a b` was `a OR (NOT b)` and is `(NOT a) OR b`.
- An implicit `OR` before `NOT` or `(`. `a NOT b` and `a ( NOT b )` were rejected and parse now;
  `a ( b ) & c` was `(a OR b) AND c` and is `a OR (b AND c)`.
- One binary operator repeated in a group groups to the left: `a | b | c` is `(a | b) | c`. `AND`,
  `OR` and `XOR` keep their truth table with a different RPN queue; `MAYBE` changes meaning.
- Malformed input that the old queue accepted by dropping operands (`a NOT`, `a ()`, `( ) a`,
  `a ( NOT )`) throws `SyntacticException`. A rejected input's message may name a different
  token.
- An unclosed `(` (`(a`, `a AND (b`) or an operator without its operands (`a AND`, `AND a`) left
  a token that is not RPN in the queue, and the error came from `Parse()` or never. Xapiand reads
  the queue without calling `Parse()`, so these queries reached it. The constructor throws the
  `SyntacticException` that `Parse()` gave for the same input (`172a5c2`).

Every other input gives the same RPN queue and tree. `PrintTree()` on a tree with a `MAYBE` node
was undefined behavior (a segfault in practice) and prints the tree.

Detect: build boolean-parser as the top-level project. `old_dump` (`test/frozen/frozen_dump.cc`,
the original sources under `Old` names) and `new_dump` (`test/new_dump.cc`) render one input's RPN
queue and tree, or its exception; run both over a log of real queries and compare.
`oracle::changed_class` in `test/oracle.h` classifies a token sequence without parsing it.

## datetime

Start `fce3d4d`, fixes `fe618d8` (parsing), `03f36fa` (months, loose offsets) and `773205b`
(timestamps before 1970). Xapiand calls
`isDate` and `isDatetime` for schema detection (`src/database/schema.cc:5156-5164`) and when it
serializes values (`src/serialise.cc:819-823`). A new field whose first value is in the second
class below is no longer detected as a date, and the schema keeps the type it gets instead.

Inputs that change:

- A negative hour, minute or second (`2020-01-02T-3:04:05`). The filling `Iso8601Parser`, which
  `DatetimeParser` uses, accepted it; both overloads return `OUT_OF_RANGE`.
- A fraction dot with no digits (`2020-01-02T03:04:05.`, `...:05.Z`) or with more than 62 digits.
  The validating overload, which `isDatetime` uses, accepted it; both return `ERROR`.
- A loose-format time ending in `Z` (`2020/01/02 03:04:05Z`) threw; it parses as UTC.
- A loose-format time with an offset (`2020/01/02 03:04:05+05:30`) sets `is_utc`. The instant is
  unchanged.
- Month arithmetic that lands on a multiple of 12. `2020-12-15||+12M` threw
  `Month must be in 1..12` and is `2021-12-15`; a `tm_t` whose month is 24, 36, ... normalizes to
  month 12 instead of 0.
- A date-math term that overflows `int` (`+2147483647d`) was undefined behavior. Date math is
  64-bit, and a result outside years 1 to `INT_MAX` throws `Year is out of range`.
- A timestamp before 1970 with a fraction. `timestamp(tm_t)` of 1969-12-31T23:59:58.9 was -2.9
  and is -1.1; `to_tm_t(-2.9)` was 23:59:58.0 and is 23:59:57.1, and `iso8601(double)` follows.
  Timestamps from 1970 on and whole-second timestamps are unchanged.
- `normalizeMonths` looped once per twelve months below 1 (about 180 million times for
  `INT_MIN`) and overflowed for a year near `INT_MAX`; it throws `Year is out of range` and
  leaves its arguments unchanged. The string parsers never reach it with such values.

`toordinal`, `timegm` and `timestamp(tm_t)` compute from one calendar routine; their exceptions,
messages and order are unchanged.

A datetime pin before `22d1f6a` built with a strict-stox at `c1c9bc1` or later accepts a time or
timedelta fraction of 63 digits or more and a date-math term of 64 characters (`+0...010d`): its
`TimeParser` and `TimedeltaParser` took their width limit from strict-stox, which read only 63
bytes until `c1c9bc1`. From `22d1f6a` datetime checks the widths itself (62 digits, 63
characters), with the results of a build on strict-stox `21b7941`. Move the two pins together.

Detect: `test/old/` holds the original as namespace `DatetimeOld`, and `test/diff_test.cc` lists
each class with its oracle. Run stored date strings and logged date-math expressions through both
and compare `isDatetime`, the `tm_t` and the exception.

## string-similarity

Start `ddfb8d1`, fixes `efba168`, `0939c0c` and `c0825ff`. Xapiand sorts by these metrics
(`src/multivalue/keymaker.cc:635-690`), so result order changes. Serialized metric parameters
still load, and Xapiand's subclasses compiled against `0a31357` (system review probe
`xap_metric.cc`).

Inputs that change:

- `Jaro_Winkler` returned the plain Jaro score. It adds the prefix boost
  `jd + l * p * (1 - jd)` when `jd > bt` (0.7), so every pair with a common prefix and a Jaro score
  above 0.7 scores higher.
- `Jaro` uses the standard window and transposition count: pairs with repeated characters or an
  odd number of out-of-order matches score differently, and two one-character strings equal only
  after case folding score 1 instead of 0.
- `Levenshtein` with an insert or delete cost other than 1 was wrong; with both costs 0 it
  returned NaN and returns distance 0.
- `Sorensen_Dice` counts bigrams as a multiset: strings with a repeated bigram (`"aaaa"`) score
  differently. With `icase`, two one-character strings equal after folding score 1 instead of 0.
- A copy or move of a bound `Sorensen_Dice` scored against its source's string (a use after free
  once the source was gone). It scores against its own (`c0825ff`). Xapiand's sort keys hold
  `SerialisableMetric<Sorensen_Dice>` (`keymaker.cc:690`).
- `PhoneticMetric` encodes both operands before the inner metric runs; it compared the raw
  strings.
- Copying a bound metric from a non-const lvalue (`Levenshtein b = a;`) did not compile; it
  copies.

Unit-cost Levenshtein, LCSubstr, LCSubsequence and Jaccard are unchanged.

Detect: `test/legacy_metrics.h` holds the old Levenshtein, Jaro and Jaro_Winkler, and
`test/differential.cc` names the classes. Run a sample of sort queries before and after.

## htm

Start `a0321ab`, fixes `cf5177b` and `9006a84`. `getId(Cartesian)` left its products to the
compiler, and a compiler that fuses a multiply into the add or subtract that uses it rounds once
instead of twice: clang on any CPU with FMA (Apple Silicon, x86 with `-mfma` or
`-march=haswell`), GCC by default on arm64 and with `-mfma`, and any compiler under
`-ffp-contract=fast`. A point within rounding of a trixel edge then landed in the neighboring
trixel: 0.83% of random points, 0.65% of a one-degree grid and 57% of points on trixel edges,
against plain IEEE-754 arithmetic (Apple clang 17 on arm64). `getId` turns contraction off, so
every build returns the ids of a build without it. Builds that never fused (x86-64 without FMA,
`-ffp-contract=off`) return the same ids as before.

Xapiand indexes the HTM ranges of each geometry (`src/database/schema.cc:5535-5600`). An index
written by a fusing build files those points under the neighboring cell; after the bump, the
points to reindex are the ones whose id differs between the old and the new build.

Detect: `test/golden.h` holds 396 points with their ids, 96 of them points a fusing build gets
wrong; run the old and new `getId` over stored points on the build that wrote the index.

## enum-reflection

Start `79fe3fa`, fix `2a5da3a`. `enum_type<E>(name)` and `enum_try_type<E>(name)` matched on a
64-bit hash of the name alone, and the hash is invertible, so a string built to share a member's
hash (15 bytes were enough) returned that member. Each lookup compares the name with the member's,
ASCII case-insensitively as before; such a string misses (`enum_type` throws
`std::out_of_range`, `enum_try_type` returns `std::nullopt`). Every real member name gives the same
answer. Xapiand passes schema properties to `enum_type<StemStrategy>`
(`src/database/schema.cc:7094`).

Detect: lookups of names that are not members; only a crafted string changes.

## msgpack

Start `3c408cf`, fixes `d054ea1`, `c913966` and `d8fa3e6`. Xapiand stores its documents as
`MsgPack`.

- A map that repeats a key is merged when it is first filled (a lookup, a walk, `hash()`,
  `erase`): the last value wins in the position of the first occurrence, so
  `{"a":1,"a":2,"b":3,"c":4}` is `{"a":2,"b":3,"c":4}`. It was `{"a":2,"b":3,"b":3}`: `c` was
  lost, `b` repeated, and a later `erase(key)` dereferenced the end iterator. `hash()`,
  `serialise()` and copies after the first fill follow the merged map; a map nothing has filled
  serializes as it came. Documents without a repeated key are unchanged.
- Pushing onto an array of maps after writing through one of its elements read freed memory: a
  growing `std::vector<MsgPack>` copied its elements, because the move constructor was not
  `noexcept`. It moves them.
- Filling a map with a key that is not a string throws "MAP keys must be of type STR", and the
  throw leaves the map as it was. It indexed the keys before the bad one first, so a second fill
  dropped them: on `{"a":1, 5:2}` the second `erase("a")` left `serialise()` at `810502`.

- `replace()` and `put()` over a key whose old value was a map or an array that had been read
  went by the old value's entries (an assertion, or an out-of-bounds read); they use the new
  value's. Replacing a value that was locked on its own throws `const_error`, as assigning to it
  does (`f083ad7`).
- A `lock()` that throws leaves nothing locked; it left the maps above a bad one locked
  (`f083ad7`).
- `erase()` returns 1 for the last element of a map or an array, as for any other; it returned 0
  (`f083ad7`).
- References to the children of an array element stay valid when the array grows, and a failed
  allocation leaves the document consistent with its own bytes (`f083ad7`).
- `to_string()` and `as_document()` write a key that is not a string as its compact JSON text,
  quoted (`5` as `"5"`, `true` as `"true"`, `null` and an ext as `"null"`). They read every key as
  a string, which gave garbage text or a crash (`adac439`).
- `update()` changes nothing when it throws for a reason of its arguments (a key that is not a
  string in the way of the merge, a target that cannot be read by key, a constant or locked
  value); it applied the entries before the failing one (`adac439`).
- `to_string()` writes a NaN or infinite float as `null`; the text stopped at it, so
  `{"v":NaN,"w":1}` gave `{"v":` (`1c851dc`, documented in `4bb04dd`). `as_document()` keeps the
  number.

`unserialise`, `hash()` and `to_string()` are faster with identical results (`ca77ada`,
`f2f9f78`, `987c111`). The CHANGELOG keeps three known problems for an owner decision: an
allocation that fails part way through `update()` leaves the entries before it applied, a
reference to a child of a value that is replaced, erased or cleared goes with the value, and the
JSON Patch helper, threads and a failing `msgpack::zone` allocation are outside its hunt test.

Detect: documents that repeat a key, have a key that is not a string or hold a NaN or an
infinity; code that grows an array of maps after writing into it, replaces a value it has read,
or counts what `erase()` returns.

## storage

Start `7b9abd1`, fixes `90aec94`, `a1e49db` and `217e731`. Xapiand stores its documents' blobs
with it.

- `read()` bounded a record with a 32-bit product, so a record starting past 4 GiB of byte offset
  read as end of file; it reads.
- A record whose flags byte is damaged into "compressed" escaped `read()` as the codec's own
  exception; it throws `StorageCorruptVolume`.
- `growfile()` multiplied in `int` and overflowed once a volume passed about 1.6 GiB; the product
  is `off_t`.
- A writable open holds a shared `flock` on the volume, and `reclaim_volumes` takes the exclusive
  one; a writable open that finds a reclaim holding the volume fails with `EWOULDBLOCK`.
  `commit()` syncs the volume directory once after creating the file.
- The vendored `normalize_path` follows [fs](#fs)'s (`934b7d9`, `42b1053`, `b141849`).
  `Storage("", ...)` opened `/vol.0` at the root of the filesystem; an empty, `.` or `a/..` base
  path is `./` and opens `./vol.0` in the working directory. A `..` removes the component before
  it (`a/../b` was `a/b` and is `b`). Pins from `934b7d9` to before `b141849` give `""` for an
  empty base path, which also opens in the working directory.

The on-disk format is unchanged, and the compressors pin carries the compressors fixes above.

Detect: volumes past 4 GiB, damaged volumes, hosts that open a volume while reclaiming, and base
paths that are empty, `.`, or contain `..`.

## strict-stox

Start `f0f7374`, fix `7d7f5dd`. Valid input of 64 bytes or more (100 leading zeros, a long run of
whitespace, a long decimal) was rejected as `EINVAL`, or, with an `idx`, parsed as its first 63
bytes with a wrong `idx`. It parses as libc `strto*` does on the same bytes. Shorter input is
unchanged, and the table-driven `stod`/`stof` path (`199e0be`) returns the bits, end, `errno` and
exceptions `strtod` returns.

`a1b03fb` converts the decimals its table cannot decide with an exact big-integer comparison
instead of calling libc. The values are libc's where libc is right; Apple's `strtod` aborted the
process on some texts (`99004559013337762701442583720290300000000000.00000000000000` is one), and
`strict_stod` returns their value. On FreeBSD, `stof` of some texts between two subnormal floats
returned the smallest normal float with no `errno`, as FreeBSD's `strtof` does; it gives `ERANGE`.

Detect: values of 64 bytes or more that reach a `strict_*` call; with the old pin they fail with
`EINVAL`. `STRICT_STOX_C_LOCALE` changes results in a locale whose decimal point is not `.`, and
is off unless a consumer defines it.

## strings

Start `62fb121`, fix `bb85615`.

- `indent` keeps blank lines and the trailing newline (blank and whitespace-only lines get no
  prefix), and an empty string stays empty. It dropped both and turned `""` into the prefix.
  `indent("a\n\nb", ' ', 2)` is `"  a\n\n  b"`.
- `replace` and `inplace_replace` with an empty search never returned. They insert the
  replacement at every position, as Python's `str.replace` does.
- `hasupper` tests ASCII `A`-`Z`. It used the locale's `isupper`, which in Latin-1 is true for
  0xC0 to 0xDE, and was undefined for a negative `char`.

Detect: `indent` calls on text with blank lines or a trailing newline; any empty search string
(the old code hangs on it); `hasupper` on non-ASCII text in a program that sets a locale.
`test/fix_test.cc` keeps the old `indent` beside the new one.

## stringified

Start `c8c9033`, fix `1c1fb3e`.

- Copying or moving a `stringified` that owned its text kept a view into the source, which
  dangled once the source died (heap use after free under ASan). The copy views its own storage.
- `c_str()` read the byte after a view over an exact-size buffer. It copies once instead.
- An explicit `stringified(const char*)` (`0053465`) returns a C string from `c_str()` without a
  copy. A call that compiled at start compiles the same way; see the skip table for `2c78a1d`.

Detect: valid programs get the same text. A program that read a copy after its source died sees
the right text instead of freed memory.

## repr

Start `2063945`, fix `3191c08`. `repr(..., max_size = 1)` with a quote wrote both quotes past a
one-byte buffer and returned a string ending in a stray NUL; it returns the two quotes. Every
other output is byte-identical (`test/diff_test.cc` against `test/repr_old.cc`).

Detect: calls with `max_size` 1.

## allocators

Start `e8fb173`, fixes `085331c`, `2fc537f`, `e38f759` and `7cdb0f8`.

- Every copy of a `memory_pool_allocator` had its own pool, so a `std::list` or `std::map` freed
  nodes into the wrong pool and corrupted the heap after a few elements. Copies and rebinds share
  one pool family and compare equal. `propagate_on_container_move_assignment` and `_swap` are
  `true_type`, `propagate_on_container_copy_assignment` is `false_type` (a copy-assigned
  container keeps its own pool), `is_always_equal` is `false_type`, and a copy-constructed
  container gets a new pool.
- `allocator<T, Backend>::construct` and `memory_pool_allocator<T>::construct` took only
  `const T&`, so `push_back(std::move(x))` and every `vector` reallocation copied. They
  perfect-forward, as `std::allocator` does: an object moved into such a container is left
  moved-from, where it stayed intact before.

Builds without `NDEBUG`, or with `ALLOCATORS_POOL_CHECK`, abort when two threads use one pool at
the same time; `allocators::set_pool_misuse_handler` replaces the abort (`2fc537f`).

Detect: containers over these allocators, and code that reads an object after moving it into one.
Xapiand uses only `allocators::total_allocated()`; completion and journal use only the resource
accounts.

## queue

Start `7df74b2`, fixes `e94be7d` and `31552f9`. At start, a parked thread that a state change
should have released waited for the next one-second re-check; untimed waits no longer re-check
(`b1b38b0`, see the skip table), and every state change that can release a parked thread wakes
one that can use it.

- Two `Queue`s on one `QueueState` each have their own consumer condition variable, so a push no
  longer wakes the other queue's consumer.
- `clear()` wakes every parked producer (one when it freed one slot), whatever its own queue's
  flags; `QueueSet::erase` wakes one.
- A pop wakes a producer whenever it leaves the count below the hard limit; `threshold` no longer
  affects waking.
- A producer that waited and then does not push (soft limit, shutdown, an exception) wakes the
  next one.
- Move assignment returns the target's dropped items to its state, so `count()` no longer reads
  high and producers of other queues on that state see the room.
- `QueueSet::clear()` compiles.

Detect: code that relied on a parked producer staying parked until a later push or pop, and
readers of `count()` on a state shared by several queues.

## scheduler

Start `ae3f0f9`, fixes `36afada` and `62a4fe8`. A task added between the worker's last look at
the wheel and its sleep could wait up to the worker's 30 s idle target: 2,623 of 140 million adds
in a burst soak. It runs when due. `62a4fe8` closes the same window in the memory model (`add()`
read the published wakeup before its fence), which no run on arm64 or x86 showed. Nothing else
changes; `post()` and `post_ordered()` (`5ad60fc`) are new calls.

Detect: timers that fired late fire on time.

## logger

Start `ce27b90`, changes `dc1fe62` and `c7332d6`.

- A routine, deferred or `clears` line due within 1 ms of its call is written 1 ms after the call,
  so a hard crash inside that millisecond loses it.
- The timestamp comes from the steady clock with an offset to the wall clock measured every 20 ms:
  within 2 us of `system_clock` at the default microsecond precision, and a step of the wall clock
  shows within 20 ms.
- Lines are ordered per thread. Across threads a line may wait behind one due microseconds later.
- When filing a line fails on the LOG thread (an allocation failure, or a wakeup the wheel
  refuses), the LOG thread runs the line if it is due and drops it otherwise; the caller no longer
  sees the refusal.

Otherwise the bytes written are identical (`test/transcript.cc` against `test/frozen/`).

Detect: log readers that rely on nanosecond timestamps or on order across threads below a
millisecond, and the last lines before a crash.

## compressors

Start `17873b2`, fixes `f157dab` and `8f57675`.

- A damaged LZ4 record whose 16-bit length exceeds the 2,072-byte block buffer overflowed the heap
  in `LZ4DecompressData` and `LZ4DecompressFile`; it throws `LZ4CorruptVolume`. A block LZ4 rejects
  is reported as `LZ4CorruptVolume` too (`f157dab`).
- A zstd frame whose header claims more than 32,768 bytes per compressed byte aborted in the
  allocator; it throws `ZstdCorruptVolume` (`f157dab`).
- A zlib stream with the preset-dictionary flag decompressed to an empty string; it throws
  `DeflateException` (`f157dab`).
- `decompress_lz4` sizes its buffers by the decoded data: hostile input allocates under 1 MB
  and throws `LZ4CorruptVolume` instead of `bad_alloc` (`8f57675`, see the skip table).
- `XXH32` reads its input little-endian on every host (`533bee4`). A big-endian host computed a
  digest that differed from upstream xxHash and from a little-endian host, and storage persists
  it, so its volumes failed their checksums elsewhere. Little-endian digests are unchanged.
- One `XXH32` update of 4 GiB and 5 bytes or more wrapped its 32-bit length counter below 16 and
  digested the input as a short one, unlike upstream xxHash; the update's own length sets the
  flag (`430870c`).
- `XXH32_state_t` keeps its four lanes as `v[4]`; code that names `v1` to `v4` does not compile
  (`430870c`).

Valid streams decode to the same bytes, and the compressed bytes are unchanged. `compress_zstd`,
`decompress_zstd` and `decompress_deflate` are out of line now (`62e6b62`), with the same bytes and
exceptions.

Detect: catch sites for decompression errors, any input that decompressed to an empty result,
and LZ4 digests written on a big-endian host.

## generation-cache

Start `00762bd`, changes `715f2af`, `89baa5b`, `2930a64` and `32a2b4a`.

- `try_insert` has the strong exception guarantee, a rehash that throws keeps every entry, and the
  `operator<` adapter no longer keeps a default-constructed entry when `Value`'s move throws.
  Paths that do not throw return the same values.
- Readers take a one-word reader-writer lock instead of `std::shared_mutex`, and a waiting writer
  holds new readers back on every platform. With `std::shared_mutex` the fairness was the
  platform's (glibc prefers readers), so continuous readers could starve `try_insert` and
  `clear`.
- The hash seed is drawn once per process (`49a86e9`); constructing a `Cache` cannot throw.

Detect: keys or values whose copy or move can throw, and workloads that read continuously while
another thread inserts.

## fs

Start `ce16118`, fixes `14932b9`, `0b5f78e`, `d6d8bc2`, `8848b49` and `bf10f39`.

- `copy_file` over a longer existing file kept the old tail; the destination is truncated.
- A failed destination open went on to write to descriptor -1; it returns `-1`.
- A short write (a full disk, `RLIMIT_FSIZE`) left a truncated copy and returned 0; it returns
  `-1`, as does a failed `close` of the destination. The partial file stays in place.
- `copy_file` onto the same file (another spelling of the path, a hard link, a symlink) returns
  `-1` before writing anything, as `cp` refuses "identical" files. In a directory copy that stops
  the copy at that file.
- `mkdirs("")` and `build_path_index("")` read past an empty view (a crash, or `true`); they
  return `false` and create nothing.
- `normalize_path` returns the lexical normal form of Python's `os.path.normpath`, and the
  current directory has one spelling, `.` (`7a10a04`, `d172a13`, `8e5f3d2`). `""`, `.`, `./`,
  `x/..`, `x/../` and `./x/..` are `.` (`./` with `slashed`, and with `keep_slash` when the input
  ends in `/`); the empty path was `/`, the root. A `..` removes the component before it, the
  first one of a relative path included (`a/../b` was `a/b` and is `b`); a relative path keeps
  the `..` it cannot remove (`..` was `.` and `../a` was `./a`; they stay `..` and `../a`); the
  root absorbs it (`/..` is `/`); a leading `./` is dropped (`./a` is `a`); and a component of
  three or more dots is a name (`...` popped two components). A run of leading `/` is one root
  (`//x` is `/x`, where `os.path.normpath` keeps two). A default-constructed view is the empty
  path; with `keep_slash` it crashed (`bf10f39`). A non-empty input without a `.` gives the bytes
  it gave. Pins from `7a10a04` to before `8e5f3d2` give answers of neither kind: the empty path is
  `""`, and `..` keeps start's rules until `d172a13`.

Detect: callers that copy over existing files, that treat 0 as success on a full disk, that copy
a directory onto itself, or that pass an empty path to `mkdirs`. Xapiand's `master` normalizes its
data and working directories (`src/main.cc:652`, `:709`), endpoint paths (`src/endpoint.cc:242`)
and the WAL's base path (`src/database/wal.cc:729`): an empty data directory resolved to `/` and
resolves to `.`, so a caller that must refuse an empty directory checks before normalizing.
`test_normalize_path_table` holds `os.path.normpath`'s output for 55 inputs.

## btree

Start `25f9494` (on `master`), fixes `d81f2a3`, `a56261d` and `512febb`.

- With keys on the heap (`std::string` past the small-string buffer), a refused allocation during
  a split, rebalance, merge, erase or root replacement lost or misordered entries, leaked, or
  double-freed. A refused insertion leaves contents, structure and live allocations unchanged, and
  erase allocates nothing.
- A value whose construction fails after a split no longer leaves `size()` one too high or an empty
  leaf in the tree.
- Maps accept move-only keys.
- A map slot is a union of `std::pair<Key, T>` and `std::pair<const Key, T>`. Node layout and sizes
  are unchanged; rebuild every translation unit that includes btree against the same revision.

Detect: allocation-failure tests, allocation counts (65,536 erases with 200-byte keys made 72,692
heap calls and make none), and builds that mix header revisions.

## cartesian

Start `6eab8ed`, fixes `79ed663` and `7066e9e`. `std::hash<Cartesian>` hashes the bits of `x`,
`y`, `z` and the SRID, the fields `operator==` compares, instead of `to_string()`. Every hash
value and the iteration order of unordered containers keyed on `Cartesian` change, and two points
that compare equal but differ in `scale` (`Cartesian(3, 4, 0)` after `normalize()` and
`Cartesian(0.6, 0.8, 0)`) hash alike, so an `unordered_set` finds one with the other. No family
library or Xapiand persists the values.

Detect: stored hash values, or tests that depend on unordered iteration order.

## random

Start `115f3f3`, fix `0667b61`. The generator is xoshiro256++ seeded with 256 bits, and the ranges
use Lemire's method, so every sequence differs. The API has no seed, so no sequence was
reproducible before either; ranges, inclusiveness and the `random_string` alphabet are unchanged.

Detect: tests that assert exact draws.

## url-parser

Start `4424e25`, fixes `2c9ea8e` and `1cdcb53`. url-parser carries its own copy of fs's
`normalize_path`, which `PathParser::init` runs first, and gives fs's bytes on every input.

- `normalize_path` follows `os.path.normpath` as in [fs](#fs). Start returned `""` for the empty
  path and for `.` with `keep_slash`, and `x` for `x/..`; with `keep_slash` the last component
  stayed as written (`a/..` stayed `a/..`), and `../x` was `./x`.
- `PathParser` follows it, with one rule of its own: the current directory, however it is
  spelled, is the empty path (no path, no id). `a/..` is the empty path (it was the path `a/..`
  with the id `..`), `a/b/..` is the path `a` (it was `a/b/..`), `a/../b` is no path and the id
  `b` (it was the path `a` and the id `b`), and `../a` is the path `..` with the id `a` (it was the
  path `.`). `a/b/../c`, `x//y` and `foo/./bar` parse as they did.
- `PathParser::init(std::string_view())` crashed; a null view is the empty path (`2c9ea8e`).

Pins from `2c9ea8e` to before `1cdcb53` have fs's intermediate rules (`a/..` is `.`, `../a` is
`./a`).

Detect: request paths with `.`, `..` or `...` components. Xapiand's search views parse paths with
`PathParser` (`src/server/search_views.cc` on `master`). `test/normalize_path_test.cc` holds
`os.path.normpath`'s output for 55 inputs.

## http-parser

Start `52a30d0`, fixes `21c8f30`, `ab8377c`, `62ac7f3`, `0aeec14`, `e2f23b9` and `5cb4409`;
http pins `c7023b0`, which carries them. Unless a consumer sets `parser->lenient_http_headers = 1`
after `http_parser_init()`, the parser rejects what request smuggling relies on, as upstream
http_parser 2.8 to 2.9.4 and llhttp do. Each case stops `http_parser_execute()` with
`HTTP_PARSER_ERRNO(parser)` set:

- A bare LF ending the request line, a header line or the headers: `HPE_CR_EXPECTED` (new).
- obs-fold (a header line that starts with a space or a tab), and a control byte other than HT,
  or DEL, anywhere in a header value: `HPE_INVALID_HEADER_TOKEN`. Start checked only the first
  byte of a value or of an `execute()` call, so its verdict depended on where the input was split.
- In a request, a `Transfer-Encoding` that is not exactly `chunked`, an empty one, or `chunked`
  twice: `HPE_INVALID_TRANSFER_ENCODING` (new). In a response, an empty `Transfer-Encoding` or one
  after `chunked` is the same error, and a `Transfer-Encoding` with a `Content-Length` is
  `HPE_UNEXPECTED_CONTENT_LENGTH`.
- A `Content-Length` with a space between digits, an empty one, or one in a trailer section:
  `HPE_INVALID_CONTENT_LENGTH`.
- A space after a chunk size, or a chunk extension that is not `;name[=token|"quoted"]`:
  `HPE_INVALID_CHUNK_SIZE`.
- A request line without a version, or a version with more than one digit a side or other than
  0.9, 1.0, 1.1 or 2.0: `HPE_INVALID_VERSION`. A response status that is not one space and three
  digits: `HPE_INVALID_STATUS`.
- After an HTTP/1.0 message with `Transfer-Encoding`, `http_should_keep_alive()` is 0 and the next
  byte is `HPE_CLOSED_CONNECTION`, whatever `Connection` says.
- A 1xx, 204 or 304 response has no body whatever its framing fields say, and only a 101 is an
  upgrade.

The two new error numbers come after `HPE_UNKNOWN`, so the others keep their values. The private
`index` field of `struct http_parser` is 5 bits and a private `extra_flags` takes the other 2; the
struct's size is unchanged. `http_parser_parse_url()` reads only the port's own digits: it read on
past `buflen` when the buffer was not NUL-terminated. With `lenient_http_headers` set, the parser
reports what start reported, request smuggling included.

Detect: `test/diff.cc`'s `changed_class()` names the inputs whose result changes; replay logged
requests through both pins. A client that ends lines with a bare LF or folds headers gets an error.

## http

Start `c23bb99`, fixes `bda9b5a`, `fce24c6`, `25f4b99` and `3caaeda`; `e70ba34` pins http-parser at
`c7023b0`. The first changes the source of every handler (`bda9b5a`, 2026-10-30; the CHANGELOG
has no entry for it):

- `HttpHandler::handle` is `asio::awaitable<void> handle(Request&, ResponseWriter&)`, awaited on
  the connection's loop, and `Router` routes are coroutines. The worker pool, `should_offload`,
  `BodyReader` and `ChannelBodyReader` are gone; a streamed body is a `BodyStream` read with
  `co_await`.
- `HttpAsioService(handler, reactors, in_flight_limit, ...)` replaces the `workers` and
  `queue_limit` arguments. A request is admitted at the end of its headers through reactor's
  `AdmissionGate`, and a refused one is answered 503 with `Retry-After: 1`. A buffered body is
  capped, 16 MiB by default, and a longer one is answered 413.
- A request is cancelled (`Request::cancel`, `Request::on_cancel`) when the client hangs up or the
  service shuts down. The handler's frame is never destroyed early, and its response is still
  attempted.

For requests that reach a handler:

- A streamed body cut short by the client ends with `connection_reset`, not end of file
  (`fce24c6`).
- Trailer fields go to `Request::trailers`, and `header()` reads the header section only: a field
  in a chunked request's trailer reached the handler as a header (`25f4b99`).
- A `CONNECT` is answered and the connection closed; the bytes after its header section were
  served as the next request (`25f4b99`).
- After an HTTP/1.0 request with `Transfer-Encoding` the connection closes, whatever `Connection`
  says (`3caaeda`), and requests that [http-parser](#http-parser) rejects are refused.

Detect: the build. Then handlers that read trailers through `header()`, clients that send
`CONNECT` or keep an HTTP/1.0 chunked connection open, and uploads over 16 MiB to a handler that
buffers the body.

## reactor

Start `ef26c30`, fixes `67e22a6` and `76c32b4`. reactor's CHANGELOG begins on 2026-11-01; this
comes from the commits.

- Nothing runs off a reactor's loop: `Reactor::pool()`, the `workers` constructor argument and the
  worker pools of `TcpServer` and `UdpServer` are gone, and `OffloadGate` is `AdmissionGate` (a
  per-reactor in-flight cap, 0 for none, a move-only `Lease`, a refusal counter). The
  constructors are `TcpServer(reactors, admission_limit, session)` and `UdpServer(on_datagram)`
  (`67e22a6`).
- `Reactor::track` takes an `Abortable&`, linked into a list touched on the reactor's loop only.
  `TcpServer::stop()` asks every tracked request to stop, waits up to a grace (5 s), then forces
  what a stalled peer still holds and waits for the sessions (`67e22a6`).
- The accept loop keeps accepting after a connection that reset while it was queued; on macOS
  `accept` returned `EINVAL` for it, the loop threw, and the listener disappeared (`76c32b4`).

Detect: the build. cluster and consensus pin reactor `4083bdb`, which carries both.

## http-log

Start `6ee47af`, fix `c7772ab`. `AccessLog::handle` is a coroutine that awaits the inner handler,
as [http](#http) requires, and `AccessLog` no longer forwards `should_offload`; its error mapping,
buffered-response logging and capture are unchanged. Move its pin with http's.

Detect: the build.

## times

Start `666dfdd`, fixes `cb75580` and `1f1f9c0`.

- `timespec_t(double)` keeps whole seconds past `int`: `timespec_t(3e9)` was
  `{2147483647, 2147483647}` on arm64 and `{-2147483648, -2147483648}` on x86, and is
  `{3000000000, 0}`. `*` and `/` keep large values too. A Unix time after January 2038 did not fit.
- The fraction is scaled in `double` on every platform. On x86, whose `long double` has 80 bits,
  about half of the decimal fractions came out one nanosecond short: `timespec_t(0.3)` had
  `tv_nsec = 299999999`, and `timespec_t(0.3) + timespec_t(0.7)` was not one second. Of 1,111,104
  decimals of one to six digits, 536,298 change on x86 and none on arm64.
- A negative value with a fraction has `tv_nsec` in `[0, 1e9)`: `timespec_t(-0.5)` was
  `{0, -500000000}` and is `{-1, 500000000}`: the same instant, which now compares equal to the
  same instant made by arithmetic.
- The comparisons with a `double` on the left take a `const timespec_t&`, so `0.5 < now()`
  compiles.

Detect: `test/diff.cc` lists the classes against the frozen old code: values of 2^31 seconds and
more, negative values with a fraction, and fractions on x86.

## time-point

Start `2f1f7f9`, fix `624c2e9`.

- A conversion that drops precision rounds toward negative infinity (`std::chrono::floor`), not
  toward zero. Only an instant before the epoch on a clock finer than a nanosecond, at a tick that
  is not a whole nanosecond, changes: -1500 ps was -1 ns and is -2 ns. On nanosecond clocks the
  values are the same, bit for bit.
- `time_point_from_ullong<Clock>` builds for a clock coarser than a nanosecond (libc++'s
  `system_clock` ticks in microseconds) and rounds down to the tick, and `time_point_to_ullong`
  takes a `time_point` of any duration. Both failed to compile.
- `time_point_to_llong` and `time_point_from_llong` give the same count signed, so instants
  before the epoch order like the instants.

Detect: `test/diff.cc` names the one class that changes.

## io

Start `3893d47`, fix `6524ce0`. `io::pread` loops to the full count, as `io.hh` documents for
`read`, `write`, `pread` and `pwrite`: it advances the offset by each count until the buffer is
full, a read returns 0 (end of file: the bytes so far) or a read fails (the bytes so far, `-1` when
none). It returned after one `::pread`. A read that reaches end of file makes one more `pread`,
which returns 0.

Detect: callers that took a short `pread` for end of file or looped themselves. journal, storage,
completion, residency and strata do not call `io::pread`. Xapiand's `Storage` policy forwards to it
and compares the count with the header size or accepts any count but `-1`, so it sees only the
extra call at end of file.

## math

Start `2730483`, fixes `01ad763` and `5486d04`. Xapiand calls `modulus` (`src/query_dsl.cc`,
`src/multivalue/generate_terms.cc` on `master`).

- `add` and `sub` on `uint8_t` and `uint16_t` report overflow. The sum was formed in `int` and
  never wrapped, so `add<uint8_t>(250, 10)` returned 4 with the flag clear. `uint32_t` and
  `uint64_t` are unchanged.
- `modulus` of `INT_MIN`, `LONG_MIN` or `LLONG_MIN` was undefined behavior and returns the least
  non-negative residue (`modulus(INT_MIN, 7)` is 5), as do the lowest `int8_t` and `int16_t`
  (`modulus(INT16_MIN, 1000)` is 232). With a modulus type narrower than `val`,
  `modulus(300, uint8_t{7})` was 2 and is 6.
- `modulus(val, 0)` divided by zero; it throws `std::invalid_argument("Modulus must be positive")`,
  as a negative modulus does.
- `min<double>` is `std::numeric_limits<double>::lowest()`. It was `min()`, the smallest positive
  normal double, about 2.2e-308.

Every other result is unchanged. Detect: the inputs above.

## errno-names

Start `a5ab101`, fix `0ec0801`. `error::description()` returned `"Unknown error: N"` for every
errno on glibc, where g++ and clang++ select the GNU `strerror_r`; it returns libc's text there
(`description(ENOENT)` is `"No such file or directory"`). macOS is unchanged.

Detect: log lines on Linux. storage and traceback describe errors through it, and so do Xapiand's
I/O traces (`src/xapiand_io_trace.h` and others on `master`).

## namegen

namegen is the C++ generator of the `Kronuz/fantasyname` fork, moved to its own repository with its
history; start is the fork's `70bd983`. Xapiand names its nodes with it (`src/xapiand_namegen.h`).

- Every alternative of a choice, and every entry of a symbol, has probability 1/n (`c0f9393`). The
  original rounded a draw to the nearest integer, so the first and last alternatives came up half
  as often (`v` gave `a` and `y` 10% of the time, `e`, `i`, `o` and `u` 20%). Patterns whose
  choices have at most two alternatives give the original's names for a seed; others do not.
- Each thread has its own engine; `toString()` from several threads raced on one (`72b3f1c`).
  `NameGen::engine()` is the thread's engine, and `Generator::generate(std::mt19937&)` draws from
  the caller's.
- `combinations()` saturates at `SIZE_MAX`; it wrapped around (`fd7ab7f`).
- The CMake target is `namegen::namegen`, with `fantasyname::fantasyname` and `fantasyname` as
  aliases (`c8faf70`).

Detect: tests that pin the names drawn from a seed.

## uinteger_t

Start `85316dd`, fixes `a39ede0`, `bd7bab1`, `6ff439f`, `10cf088` and `eb588dc`. uinteger_t and
base-x had a campaign of their own on the same days ([record](reviews/2026-10-31-uinteger_t-base-x.md)).
base-x and Xapiand build on it, and FetchContent keeps the first declaration, so Xapiand's own
uinteger_t pin decides which uinteger_t base-x gets. Xapiand's `xapiand` branch pins `a383e37`
(`Xapiand:bc19f0c0`); `3fe13a2f` pins a commit from before the start.

Inputs that change:

- A character that is a digit but not below the base was folded into the value (`uinteger_t("9", 8)`
  was 9, `uinteger_t("g", 16)` was 16); it throws `std::invalid_argument` (`Error: Not a digit in
  base 8: '9' at 1`). So does a byte 0x80 or above, which indexed the digit table with a negative
  value where `char` is signed (`"1é"` in base 16 parsed as 0x100) (`bd7bab1`).
- A base-256 parse (`uinteger_t(bytes, 256)`) kept leading zero limbs. An all-zero buffer, or the
  single `00` byte that `uinteger_t(0).str(256)` writes, gave a zero that compared unequal to 0 and
  was true as a `bool`; with 8 or more leading zero bytes `==`, `<` and `bits()` were wrong (eight
  zero bytes and `01` had 65 bits and was not 1); a division by a parsed zero divided by zero
  (undefined behavior, `SIGFPE` on x86-64). The parse skips leading zero bytes, and the division
  throws `std::domain_error` (`eb588dc`).
- After an in-place right shift of 64 bits or more, `x *= 1` (and any self copy-assignment) gave
  back the shifted-out limbs, and a value moved from had `size()` 2^64 - 1, so `bool`, `bits()` and
  comparisons read out of bounds. They give the shifted value and zero (`6ff439f`).
- A left shift of a nonzero value by a `uinteger_t` count of 2^64 bits or more threw `std::bad_alloc`;
  it throws `std::length_error` ("Shift too large") (`6ff439f`; at 32- and 16-bit limbs `d50f9bd`).
  A right shift by such a count gives zero, as before.
- Targets without `unsigned __int128` and MSVC computed wrong products: the portable multiply-add
  wrapped its middle sum, and the MSVC paths passed a full carry limb as a one-bit carry and left a
  product's low limb unset (`a39ede0`). GCC and Clang on 64-bit targets are unchanged.
- `str()` with a bad base says "Base must be in the range [2, 36] or 256" (it said "[2, 36]")
  (`204eed1`). On a 32-bit `size_t`, a conversion whose bit or digit count does not fit (512 MiB of
  base-256 digits) throws `std::length_error` before it allocates (`819daa4`, `b012716`).

What changes for the build:

- `uinteger_t::container` is the library's own small vector, not `std::vector<digit>`: its iterators
  are `digit*`, and it has only the members the class uses (`8f1345e`). Code that treats it as a
  `std::vector` does not compile.
- `sizeof(uinteger_t)` is 88 on LP64 (56 at start, 24 from `6ff439f`, 80 at `8f1345e`, 88 from
  `10cf088`). Up to 8 limbs live in the object, and the object points into itself while they do,
  so `memcpy` or `realloc` of one leaves it pointing at the old storage. `UINTEGER_T_INLINE_LIMBS`
  and every tuning macro must have one value in all the translation units of a program.
- Moves are `noexcept` and leave the source zero; moving an inline value copies its limbs, so
  pointers into the source do not follow the new owner (`6ff439f`, `8f1345e`).
- `compare(lhs, rhs)` and `divmod(q, r, lhs, rhs)` are public (`compare` was documented, and a call
  did not compile), and `mul(r, lhs, rhs)` is new (`d1be6ed`); so are `digits()` and `from_digits()`
  (`bd7bab1`). A native integer on the left of a shift (`5 << big`) and `signed char` compound
  assignments compile (`1d96eea`). `divmod_small`, `mul_add_small` and `base_chunk` were public only
  from `aeeeb67` to `bd7bab1`; code written against those commits does not compile after them.

Valid input gives the same values and text: `str()` and parsing match the original header byte for
byte in bases 2 to 36, and the arithmetic matches GMP; the faster kernels return the same results.

Detect: text that reaches a string constructor with characters outside its base or bytes 0x80 and
above (it throws now); base-256 buffers with leading zero bytes, and divisions by a value parsed
from bytes; left shifts by a `uinteger_t` count; code that treats `container` as a `std::vector`,
copies a `uinteger_t` with `memcpy`, or sets `UINTEGER_T_*` macros per translation unit.

## base-x

Start `54a9326`, fixes `8935fe6`, `c3965ec`, `d1fda10`, `36dd216`, `712c643`, `f702d6d`, `b8fc1a2`,
`2507a82`, `d3d9f23`, `27be05e` and `c599da0`. Its text also depends on the uinteger_t it is built
with: the results below are each commit's with the uinteger_t its `CMakeLists.txt` pins, so a
project that declares uinteger_t itself keeps that pin at or after base-x's (`919698e` pins
`a383e37`). Xapiand's `xapiand` branch pins `919698e` (`Xapiand:bc19f0c0`); `3fe13a2f` pins a
commit from before the start.

Text that `encode` writes:

- The RFC 4648 presets (`Base16::rfc4648()`, `Base32::rfc4648()` and `rfc4648hex()`,
  `Base64::rfc4648()`, `rfc4648url()` and `rfc4648url_unpadded()`) write the bytes, as Python's
  `base64` does. In base32 and base64, below 32 bytes the text changes when the first byte is below
  0x08 or 0x04: `0x01` was `Q===` in base64, which decodes to `00`, and is `AQ==`. From 32 bytes on,
  every base32 and base64 text changes; the old one was misaligned (`c3965ec`). Every leading zero
  byte is kept (six zero bytes and `0x01` were `Q===` and are `AAAAAAAAAQ==`), `Base16::rfc4648()`
  writes two digits per byte, so a first byte below 0x10 gains a digit (`0x01` was `1` and is `01`),
  an empty buffer is the empty text (it threw), and a `uinteger_t` 0 is `AA==` (it was `A`)
  (`2507a82`).
- `Base58::bitcoin()` and `ripple()` write each leading zero byte as a leading zero digit:
  `00 00 61 62 63` was `ZiCa` and is `11ZiCa`, two zero bytes were `1` and are `11`, and an empty
  buffer is the empty text (it threw) (`27be05e`). `bitcoinchk()`, `ripplechk()` and the other
  presets keep the numeric text.
- Bytes that are all zero encode as one zero digit with no check character in every numeric
  preset. The power-of-two presets wrote the empty text (`Base16::base16()` is `0`,
  `Base64::base64()` is `A`) until `8935fe6`, and the check presets of the other bases wrote a check
  character after the digit (`Base59::dubaluchk()` was `zN` and is `z`, `Base58::base58chk()` was
  `0v` and is `0`) until `b8fc1a2`. Each of those texts decodes to one zero byte, as does the
  digit and check character that `8935fe6` to `dd2124e` wrote in the power-of-two check presets
  (`Base16::base16chk()` `0f`).
- `encode` into a non-empty result pads and sums only the text it appends: after `xy`,
  `Base64::rfc4648()` writes `xyYQ==` for `a` (it wrote `xyYQ`) (`d1fda10`).

What `decode` and `is_valid` accept:

- The RFC 4648 presets return the bytes their digits hold: each leading zero digit is a zero byte,
  digits past the last whole byte are dropped (`ABC` in base64 was `10` and is `00 10`; one digit
  `A` was one zero byte and is none), the empty text is no bytes (it was one zero byte), and
  `Base16::rfc4648()` drops the last of an odd count of digits (`ABC` was `0A BC` and is `AB`)
  (`2507a82`).
- `Base58::bitcoin()` and `ripple()` return a zero byte for each leading zero digit: `11ZiCa` was
  `61 62 63` and is `00 00 61 62 63`, `11` was one zero byte and is two, and the empty text was one
  zero byte and is none (`27be05e`).
- Text after the padding throws `std::invalid_argument` (`YWI=junk` decoded as `ab`), and a check or
  checksum character after the padding is read after all of it (`d3d9f23`). A NUL byte in an
  alphabet without padding throws (`ab\0cd` decoded as `ab`) (`36dd216`), and so does an unknown
  byte in `Base32::crockfordchk()`'s check position (`10?` decoded as 32) (`712c643`). The empty
  text in a `*chk` alphabet throws `std::invalid_argument` (it threw `std::bad_alloc`) (`10a5f0b`).
- `decode` into a `uinteger_t` leaves it as it was when it throws: on a bad character from
  `8935fe6`, and on a failed check or checksum character from `c599da0`. It held the digits before
  the bad character, or the decoded value.
- `is_valid` accepts `=` padding (`YWI=` was invalid) and `crockfordchk()`'s extended check
  characters (`10*`), and rejects a digit after the padding; in six presets, `crockfordchk()` and
  `dubaluchk()` among them, it answers differently for text that ends in an ignored character
  (`f702d6d`).
- Checksums are summed in 64 bits: the `int` sum overflowed (undefined behavior) at about 34
  million base64 characters (`10a5f0b`). On a 32-bit `size_t` an RFC 4648 encode of 512 MiB or more
  throws `std::length_error` (`b468653`).

`encode` and `decode` call uinteger_t's `digits()` and `from_digits()` from `1687e9a` on, so a
hand-copied `uinteger_t.hh` older than `bd7bab1` does not compile with them.

Xapiand's `xapiand` branch keeps `Base59::dubaluchk()` UUID text (`src/serialise.cc:52`),
`Base62::inverted()` node ids (`src/manager.h:73`) and `Base64::rfc4648url_unpadded()` `_id`s
(`src/database/schema.cc:2856`).
None of the ids it mints changes text: a compact cuuid wire never starts with a zero byte, and
20,000 v6 and 20,000 v1 ids minted on 2026-11-01 were 8 bytes starting with 0x4c, which encode as
before. An `_id` minted from a wire whose first byte is below 0x04, or of 32 bytes or more, would
change. Its `is_valid` of a `~` UUID text (`src/serialise.cc:93`) answers differently for text that
ends in an ignored character.

Detect: `test/golden/encode.txt` holds every preset's text at head for a fixed set of inputs.
Encode a sample of the stored inputs with the old and the new pin and compare, and decode stored
texts with both: RFC 4648 text of bytes that start below 0x10 or run to 32 bytes, Bitcoin and
Ripple base58 of bytes with leading zeros, and all-zero inputs are the classes that move.

## Unchanged results

These libraries changed between start and head with results identical to start, checked by a
differential test against a frozen copy of the old code: bitpack, char-classify (its new block
scanners and escaping kernel serve escape and repr, whose output is unchanged), cuuid (wire
bytes), docset, double-metaphone, escape, flat-map, fst, md5, sha256, soundex, term-color,
threadpool and unicode.

Three grow a type, so every translation unit of a program needs one revision: a stash leaf is 16
bytes larger and each chain node 8 (`stash:78a18f3`), scheduler's `ScheduledTask` grows from 48 to
96 bytes with `post()`, and threadpool's `TaskWrapper<std::function<void()>>` holds a `SmallTask`
with 48 bytes of inline storage instead of a `std::function` (`threadpool:12f1516`). metrics' `AtomicCounter` is
start's compare-exchange loop again, and `ContendedCounter` is a new type. bloom-filter keeps
`BloomFilter<N>` bit for bit; `FastBloomFilter<N>` and `BlockedBloomFilter<N>` are new and set
different bits, so a bitset persisted from one type does not load into another.
