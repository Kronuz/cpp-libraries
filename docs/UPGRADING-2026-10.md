# Moving pins past October 30, 2026

> Status: CURRENT (2026-10-31). Read from each library's `CHANGELOG.md` and default branch on
> 2026-10-31.

Consumers pin these libraries by commit, so nothing here reaches a build until a pin moves. This
note lists every change made on or after 2026-10-30 that changes a result, an exception or a build
when a pin moves past it. Each entry has the library, the start and fix commits, the inputs whose
results change, and how a consumer finds out whether it sends them. The full entries, with their
numbers and oracles, are in each library's `CHANGELOG.md`.

- **Start** is the library's default-branch head before 2026-10-30, the commit the October 31
  audits call start. A pin at or before it gives the old results.
- **Fix** is the first commit with the new results. Every later commit on the default branch
  carries it; no branch diverges.
- Xapiand (`3fe13a2f`, 1.0.0-alpha.10) and Detent's `cmake/dependencies.json` pin commits older
  than every fix below. In-family pins move in waves; compare a pin with the two columns.

**Two changes need an owner decision when Xapiand's pins move, because Xapiand's users see
them:** boolean-parser regroups queries and rejects some it accepted, and datetime changes which
strings parse as dates, and so how schema detection types a new field. string-similarity changes
the order of similarity-sorted results. The other changes fix crashes, hangs, wrong answers and
timing.

## Summary

| Library | Start | Fix | What changes | Consumers |
|---|---|---|---|---|
| [boolean-parser](#boolean-parser) | `41a20b5` | `00b3021` | Query grouping; malformed queries rejected | Xapiand: **owner decision** |
| [datetime](#datetime) | `fce3d4d` | `fe618d8`, `03f36fa` | Which strings parse; `+12M`; `is_utc` | Xapiand: **owner decision** |
| [string-similarity](#string-similarity) | `ddfb8d1` | `efba168`, `0939c0c` | Jaro, Jaro-Winkler, Dice, weighted Levenshtein, phonetic scores | Xapiand sort keys |
| [strict-stox](#strict-stox) | `f0f7374` | `7d7f5dd` | Input of 64 bytes or more parses | datetime, msgpack, storage, Detent, Xapiand |
| [strings](#strings) | `62fb121` | `bb85615` | `indent`, empty-search `replace`, `hasupper` | fs, soundex, string-similarity, system, traceback, Detent, Xapiand |
| [stringified](#stringified) | `c8c9033` | `1c1fb3e`, `2c78a1d` | Use after free fixed; one new ambiguity | fs, storage, Xapiand |
| [repr](#repr) | `2063945` | `3191c08` | `max_size == 1` | msgpack, strings, Detent, Xapiand |
| [allocators](#allocators) | `e8fb173` | `085331c`, `2fc537f` | Pool sharing, equality, propagation | none found |
| [scheduler](#scheduler) | `ae3f0f9` | `36afada` | A task no longer waits out the 30 s idle sleep | logger, Detent, Xapiand |
| [logger](#logger) | `ce27b90` | `dc1fe62`, `c7332d6` | Write delay, crash window, timestamps | Detent, Xapiand, http-log, prism |
| [compressors](#compressors) | `17873b2` | `f157dab`, `8f57675` | Damaged input throws instead of overflowing | storage, flume, http, strata, Detent, Xapiand |
| [generation-cache](#generation-cache) | `00762bd` | `715f2af`, `89baa5b`, `2930a64` | Exception paths; construction reads `random_device` | Detent |
| [fs](#fs) | `ce16118` | `14932b9`, `0b5f78e` | `copy_file` truncates and reports short writes | Xapiand |
| [btree](#btree) | `25f9494` | `d81f2a3`, `a56261d`, `512febb` | Allocation-failure behavior; slot layout | strata, Detent |
| [cartesian](#cartesian) | `6eab8ed` | `79ed663` | `std::hash<Cartesian>` values | none found |
| [random](#random) | `115f3f3` | `0667b61` | The sequence | scheduler, Detent, Xapiand |

## Commits not to pin

Some changes broke something that a later commit fixes or that is still open. Pin before the
first column or at or after the second.

| Library | Broken from | Fixed in | What goes wrong |
|---|---|---|---|
| compressors | `0498bf5` | `8f57675` | A crafted 98 KB LZ4 stream makes `decompress_lz4` reserve 64 MB; a refused allocation throws `bad_alloc` instead of `LZ4CorruptVolume`. |
| logger | `dc1fe62` | `06a27d2` | A `clears` line due within 1 ms can be written before an immediate line logged earlier. |
| generation-cache | `715f2af` | `2930a64` | A `Key` or `Value` copy or move that throws in `try_insert` or in a rehash loses entries or leaves a slot that a later `get` dereferences. |
| metrics | `aa7a3d8` | open (audit CA2) | `AtomicCounter::add(1)` racing an add that saturates the counter can wrap it, permanently. `9207dd3` narrows the window and does not close it. |
| queue | `b1b38b0` | open (audit CA1) | Four waits block forever: two `Queue`s sharing one state, `clear()` with parked pushers, `QueueSet::erase`, and a pop that leaves the size at or above the threshold but below the hard limit. |
| fs | `14932b9` | open (audit FS1) | `copy_file` onto the same file (the same path, a hard link or a symlink to it) truncates the source to 0 bytes and returns 0. |
| allocators | `2fc537f` | open (audit AL1) | Container copy-assignment shares the source's pool, so the two containers used from two threads corrupt the heap. |

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

Every other input gives the same RPN queue and tree.

Detect: build boolean-parser as the top-level project. `old_dump` (`test/frozen/frozen_dump.cc`,
the original sources under `Old` names) and `new_dump` (`test/new_dump.cc`) render one input's RPN
queue and tree, or its exception; run both over a log of real queries and compare.
`oracle::changed_class` in `test/oracle.h` classifies a token sequence without parsing it.

## datetime

Start `fce3d4d`, fixes `fe618d8` (parsing) and `03f36fa` (months, loose offsets). Xapiand calls
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

Detect: `test/old/` holds the original as namespace `DatetimeOld`, and `test/diff_test.cc` lists
each class with its oracle. Run stored date strings and logged date-math expressions through both
and compare `isDatetime`, the `tm_t` and the exception.

## string-similarity

Start `ddfb8d1`, fixes `efba168` and `0939c0c`. Xapiand sorts by these metrics
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
  differently.
- `PhoneticMetric` encodes both operands before the inner metric runs; it compared the raw
  strings.

Unit-cost Levenshtein, LCSubstr, LCSubsequence and Jaccard are unchanged.

Detect: `test/legacy_metrics.h` holds the old Levenshtein, Jaro and Jaro_Winkler, and
`test/differential.cc` names the classes. Run a sample of sort queries before and after.

## strict-stox

Start `f0f7374`, fix `7d7f5dd`. Valid input of 64 bytes or more (100 leading zeros, a long run of
whitespace, a long decimal) was rejected as `EINVAL`, or, with an `idx`, parsed as its first 63
bytes with a wrong `idx`. It parses as libc `strto*` does on the same bytes. Shorter input is
unchanged, and the table-driven `stod`/`stof` path (`199e0be`) returns the bits, end, `errno` and
exceptions `strtod` returns.

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

Start `c8c9033`, fixes `1c1fb3e` and `2c78a1d`.

- Copying or moving a `stringified` that owned its text kept a view into the source, which
  dangled once the source died (heap use after free under ASan). The copy views its own storage.
- `c_str()` read the byte after a view over an exact-size buffer. It copies once instead.
- `2c78a1d` adds an implicit `stringified(const char*)`. A string literal passed to an overload set
  that takes both `stringified` and `std::string_view` or `std::string` becomes ambiguous
  (audit-text CR3). In-family callers use direct initialization and compile.

Detect: valid programs get the same text. A program that read a copy after its source died sees
the right text instead of freed memory. The ambiguity is a compile error at the bump.

## repr

Start `2063945`, fix `3191c08`. `repr(..., max_size = 1)` with a quote wrote both quotes past a
one-byte buffer and returned a string ending in a stray NUL; it returns the two quotes. Every
other output is byte-identical (`test/diff_test.cc` against `test/repr_old.cc`).

Detect: calls with `max_size` 1.

## allocators

Start `e8fb173`, fixes `085331c` and `2fc537f`. Every copy of a `memory_pool_allocator` had its own
pool, so a `std::list` or `std::map` freed nodes into the wrong pool and corrupted the heap after a
few elements. Copies and rebinds share one pool family and compare equal;
`propagate_on_container_copy_assignment`, `_move_assignment` and `_swap` are `true_type`,
`is_always_equal` is `false_type`, and a copy-constructed container gets a new pool. See AL1
above for copy assignment.

Detect: containers over `memory_pool_allocator`. Xapiand, completion and journal use only the
tracking allocators and the resource accounts.

## scheduler

Start `ae3f0f9`, fix `36afada`. A task added between the worker's last look at the wheel and its
sleep could wait up to the worker's 30 s idle target: 2,623 of 140 million adds in a burst soak.
It runs when due. Nothing else changes; `post()` and `post_ordered()` (`5ad60fc`) are new calls.

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
  and throws `LZ4CorruptVolume` instead of `bad_alloc` (`8f57675`, see the table above).

Valid streams decode to the same bytes, and the compressed bytes are unchanged.

Detect: catch sites for decompression errors, and any input that decompressed to an empty result.

## generation-cache

Start `00762bd`, changes `715f2af`, `89baa5b` and `2930a64`.

- A cache whose key has `std::hash` reads `std::random_device` twice when it is constructed
  (`89baa5b`); `std::random_device` throws `std::system_error` where no entropy source is
  available.
- `try_insert` has the strong exception guarantee, a rehash that throws keeps every entry, and the
  `operator<` adapter no longer keeps a default-constructed entry when `Value`'s move throws.
  Paths that do not throw return the same values.

Detect: caches constructed where `std::random_device` can fail, and keys or values whose copy or
move can throw.

## fs

Start `ce16118`, fixes `14932b9` and `0b5f78e`.

- `copy_file` over a longer existing file kept the old tail; the destination is truncated.
- A failed destination open went on to write to descriptor -1; it returns `-1`.
- A short write (a full disk, `RLIMIT_FSIZE`) left a truncated copy and returned 0; it returns
  `-1`, as does a failed `close` of the destination. The partial file stays in place.

See FS1 above for copying a file onto itself.

Detect: callers that copy over existing files, or that treat 0 as success on a full disk.

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

Start `6eab8ed`, fix `79ed663`. `std::hash<Cartesian>` hashes the coordinate bits instead of
`to_string()`, so every hash value and the iteration order of unordered containers keyed on
`Cartesian` change. No family library or Xapiand persists the values.

Detect: stored hash values, or tests that depend on unordered iteration order.

## random

Start `115f3f3`, fix `0667b61`. The generator is xoshiro256++ seeded with 256 bits, and the ranges
use Lemire's method, so every sequence differs. The API has no seed, so no sequence was
reproducible before either; ranges, inclusiveness and the `random_string` alphabet are unchanged.

Detect: tests that assert exact draws.

## Unchanged results

These libraries changed between start and head with results identical to start, checked by a
differential test against a frozen copy of the old code: cuuid (wire bytes), docset, enum-reflection
(`enum_try_type` is new), escape, flat-map, fst, htm, md5, sha256, soundex, storage (the on-disk
format), threadpool and url-parser. bloom-filter keeps `BloomFilter<N>` bit for bit;
`FastBloomFilter<N>` and `BlockedBloomFilter<N>` are new and set different bits, so a bitset
persisted from one type does not load into another.
