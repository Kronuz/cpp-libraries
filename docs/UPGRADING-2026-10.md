# Moving pins past October 30, 2026

> Status: CURRENT (2026-11-01). Read from every library's `CHANGELOG.md`, its `git log` since
> 2026-10-30 and its default branch on GitHub at 2026-11-01 19:40 PST.

Consumers pin these libraries by commit, so nothing here reaches a build until a pin moves. This
note covers every library in the catalog: what changes when a pin moves past 2026-10-30 (results,
exceptions, API, builds) and what the move buys in speed. Each library's `CHANGELOG.md` has the
full entry, with the oracle and every number; the sections here say only what a consumer must
know and link there.

- **Start** is the library's default-branch head at 2026-10-30 00:00 PDT. A pin at or before it
  gives the old results.
- **Fix** is the first commit with the new results. Every later commit on the default branch
  carries it; no branch diverges.
- **Head** is the default branch on GitHub (`git ls-remote`) at 2026-11-01 19:40 PST. Commits after
  it are not covered here; read the library's CHANGELOG from that commit on.
- Xapiand (`3fe13a2f`, 1.0.0-alpha.10) and Detent's `cmake/dependencies.json` pin commits older
  than every fix below. In-family pins move in waves.

**Two changes need an owner decision when Xapiand's pins move, because Xapiand's users see
them:** boolean-parser regroups queries and rejects some it accepted, and datetime changes which
strings parse as dates, and so how schema detection types a new field. Others change what Xapiand
returns or stores: string-similarity's scores and so the order of similarity-sorted results; htm's
id of a point near a cell edge on builds that fuse multiply-adds (an index written by such a build
needs those points reindexed); msgpack's merge of a document's repeated keys; and fs, storage and
url-parser's normal form of a path (Python's `os.path.normpath`), which changes the paths built from
an empty data directory and from endpoints that hold a `..`.

**Five need code changes:** `http` handlers are coroutines, `reactor` has no worker pool and new
constructors, `http-log` follows `http`, scheduler's tasks no longer derive
`std::enable_shared_from_this`, and hashes' CRC-32C moved to `crc32c` (before the start, but Detent
pins a hashes from before the move). http-parser rejects what request smuggling relies on unless a
consumer sets `lenient_http_headers`. The other changes fix crashes, hangs, wrong answers and
timing.

## Updating an application (for agents)

The steps for an agent that owns an application built on these libraries (Xapiand, Detent, prism,
or any other).

1. **List its pins.** `tools/pins.sh -c <app>` lists every first-party `FetchContent_Declare` of the
   application on GitHub that is behind its library's head. A pin kept elsewhere (Detent's
   `cmake/dependencies.json`) is read by hand: the library, the commit, and who declares it first.
2. **Read each pinned library's row and section.** The [Summary](#summary) has one row per library,
   and every library whose results, API or build change has a section below. Act first on the rows
   marked **owner decision** (ask the owner before changing what users see) and **code change**.
3. **Skip the bad ranges.** No pin may fall inside a range of [Commits not to pin](#commits-not-to-pin),
   including the ranges a library carries through its own pins.
4. **Move pins dependency first.** FetchContent keeps the first declaration of a name, so the
   application declares a shared dependency before the libraries that use it, at the newest commit
   any of them needs: uinteger_t before base-x, scheduler (at or after `5ad60fc`) before logger,
   http-parser and reactor before http. Leaves move first, then their consumers.
5. **Rebuild, test and diff.** Run the application's tests, then run its stored inputs through the
   old and the new build on the input classes each section names, and compare the results. Several
   libraries ship the old code as a frozen copy for this (each section's "Detect" says where).
6. **Fix the API breaks.** `http` handlers return `asio::awaitable<void>` and `HttpAsioService` takes
   `(handler, reactors, in_flight_limit)`; `reactor::TcpServer` takes `(reactors, admission_limit,
   session)` and `Reactor::pool()` is gone; `http_log::AccessLog::handle` is a coroutine; a scheduler
   task that calls `shared_from_this()` derives `std::enable_shared_from_this` itself; code that
   includes hashes' `crc32c.hh` includes `<crc32c/crc32c.hh>` and links `crc32c::crc32c`.
7. **Measure the hot path.** Time the application's own hot path at the old and the new pins
   (`tools/ab_compare.py` runs both binaries interleaved with an A/A control). The "What you get"
   column says what each library gained in its own benchmarks; the application's number is the one
   that counts.
8. **Record it.** The application's `CHANGELOG.md` names each library moved (old pin, new pin), the
   sections acted on, the results that changed and the owner decisions taken.

A message an owner can paste to the agent of an application:

> Move this application's pins of the Kronuz C++ libraries to their current heads. Follow
> "Updating an application (for agents)" in
> https://github.com/Kronuz/cpp-libraries/blob/main/docs/UPGRADING-2026-10.md step by step: list
> the pins, read each library's Summary row and section, act on the owner-decision and
> code-change rows first and ask me before changing anything users see, avoid the commits not to
> pin, move dependencies first, rebuild, run the tests and diff the input classes each section
> names, measure the hot path before and after, and record what you adopted in the CHANGELOG.
> Report what changed, what you did not adopt and why, and every decision you need from me.

## Summary

One row per library, alphabetical. "What you get" is the [gate](reviews/gate-2026-11-01.md)'s
geomean of start's time over head's on the Apple M4 Pro and the Intel Core i9-9980HK (above 1 is
faster at head; "gate 2.71 / 3.43" reads M4 Pro / i9), with the fixes that landed after the gate
where they move it; for a library outside the gate, the CHANGELOG's or README's own number. "Same
results" means a frozen-copy differential test holds every output to start's.

| Library | Start | Head | What changes | What you get | Consumers |
|---|---|---|---|---|---|
| [allocators](#allocators) | `e8fb173` | `b01d3d7` | Pool sharing, equality, propagation; `construct` moves; tracked blocks 16-byte aligned; layout | gate 1.30 / 1.20; one-block pool pair 0.66 ns against 1.16 (M4 Pro) | completion, journal |
| analysis | `991ff33` | `158c81b` | Same results (unicode and snowball pins move) | 1.8 to 2.7x Xapian's `TermGenerator` (README) | prospect, queryparser |
| atomic-shared-ptr | `9a2582e` | `9af0aa7` | Docs only | unchanged | msgpack, Detent |
| [base-x](#base-x) | `54a9326` | `14d086c` | RFC 4648 text and decoding; Bitcoin and Ripple leading zeros; all-zero bytes; stricter `decode` and `is_valid` | 32-byte base58 encode 49.7 ns, decode 52.1 (M4 Pro), over 10x start | Xapiand |
| bitpack | `cd13f36` | `ca99608` | Same results | gate 1.04 / 0.99 (the i9 binaries are identical) | prospect |
| bkd | `4ddc2cf` | `dfc04d4` | Docs only | unchanged | none |
| [bloom-filter](#bloom-filter) | `0410185` | `05bd553` | `BloomFilter` keeps its bits; two new filter types; `BLOOM_FILTER_NO_INT128` | gate 1.00 / 0.98; `FastBloomFilter` 16-byte miss 8.0 ns against 27.7 (M4 Pro) | none |
| [boolean-parser](#boolean-parser) | `41a20b5` | `85110af` | **Owner decision:** query grouping; malformed queries throw at construction | gate 2.71 / 3.43 | Xapiand |
| [btree](#btree) | `25f9494` | `45c8206` | Allocation-failure behavior; slot layout | gate 1.07 / 1.12; string `emplace` 2.4x (Clang) | strata, Detent |
| [cartesian](#cartesian) | `6eab8ed` | `05cab81` | `std::hash<Cartesian>` values | gate 2.67 / 2.47 | htm |
| [char-classify](#char-classify) | `a890496` | `57613ed` | Same results; new block scanners and escaping kernel | gate 1.01 / 1.00; the kernel is escape's and repr's speedup | cuuid, escape, hashes, pki, repr, strings, url-parser, Detent |
| [cluster](#cluster) | `4d894db` | `4863feb` | Its reactor pin crosses reactor's code change | not measured | Detent |
| [completion](#completion) | `03cef1d` | `8644a8e` | Its metrics and allocators pins move (`AtomicCounter` is an alias) | not measured | journal, strata, Detent |
| [compressors](#compressors) | `17873b2` | `5c54128` | Damaged input throws; XXH32 on big-endian hosts and past 4 GiB; `XXH32_state_t` fields | gate 1.27 / 1.28; XXH32 256 B 8.4 ns against 10.9 (M4 Pro) | flume, http, storage, strata, Detent |
| [consensus](#consensus) | `a4c28e0` | `63ba7d9` | Its journal, completion and reactor pins move | not measured | Detent |
| constexpr-phf | `dd7a9ff` | `e545aec` | Same results and API: docs, and the ctrie pin of its comparison benchmark | none; the library code is start's | enum-reflection, hashes, msgpack, Detent |
| [crc32c](#crc32c) | `b60a8e5` | `0d5460d` | Same values; the hashes `crc32c.hh` it replaces is gone | gate 1.48 / 1.39; 1 MiB 29.8 GB/s against 19.9 (i9) | journal, residency, strata |
| ctrie | `4b6eb1b` | `c6c2887` | Docs only | unchanged | constexpr-phf (bench) |
| cuuid | `d46c825` | `b2243cb` | Same wire bytes | gate 2.27 / 1.97 | none |
| [datetime](#datetime) | `fce3d4d` | `babf3f5` | **Owner decision:** which strings parse; `+12M`; `is_utc`; fractions before 1970; field widths | gate 6.44 / 7.44 | Xapiand |
| docset | `cd38597` | `dcbd528` | Same results | gate 1.31 / 1.15 | prospect |
| [double-metaphone](#double-metaphone) | `91c17a2` | `b3191c4` | Same keys; copying from a non-const lvalue compiles | gate 1.90 / 2.26 | none |
| endian | `a625b94` | `a24942e` | Docs only | unchanged | cuuid, md5, sha256, Detent |
| [enum-reflection](#enum-reflection) | `79fe3fa` | `f953508` | A crafted name no longer matches a member; `enum_try_type`; bench option renamed | hits 1.01 to 1.35x start (the gate's 0.86 / 0.84 was before the table lookup) | http-parser, msgpack, Detent, Xapiand |
| epoch | `4f9e76a` | `de7efdf` | Docs only | unchanged | none |
| [errno-names](#errno-names) | `a5ab101` | `cfe571a` | Descriptions on glibc | gate 1.00 / 1.00 | storage, traceback, Xapiand |
| escape | `f4efd99` | `b5d9f30` | Same output | gate 2.88 / 2.43 | none |
| flat-map | `a9a52b0` | `9fe0bd9` | Same answers | gate 1.46 / 1.91 | Detent |
| [flume](#flume) | `7184cb4` | `defd5a1` | `Receiver(sink, max_block)`; big-endian XXH32 footer through compressors | gate 1.00 / 1.01 | none |
| [fs](#fs) | `ce16118` | `aa06315` | `copy_file` truncates, refuses the same file, reports short writes; empty paths; `normalize_path` is `os.path.normpath` | `normalize_path` 1.25 / 1.66 geomean (the gate's 0.84 / 0.76 was before the one-pass loop) | Xapiand |
| fst | `12657aa` | `7338f56` | Same bytes | gate 2.13 / 2.14 | strata, termdict |
| fusefilter | `a42bd15` | `0665ee0` | Same results; `filter8::build` reorders its work | build 3.9x and 2.9x faster at 1M and 10M keys on the M4 Pro, 3.9x and 3.2x on the i9; faster than xor_singleheader (9.7 vs 18.8 ns per key at 1M, M4 Pro) | strata |
| [generation-cache](#generation-cache) | `00762bd` | `38a2d39` | Exception paths; writers no longer starve; layout | gate 3.22 / 4.35 | Detent |
| [hashes](#hashes) | `de5b3ac` | `a050f6b` | Same values; `crc32c.hh` gone since `aba7865` (2026-10-20) | unchanged | bloom-filter, enum-reflection, msgpack, strata, Detent |
| [htm](#htm) | `a0321ab` | `1e041ef` | Ids of points near a cell edge on fusing builds | gate 1.00 / 1.06; `getId` 591 ns against 914 (M4 Pro) | Xapiand |
| [http](#http) | `c23bb99` | `df661f7` | **Code change:** coroutine handlers; trailers; `CONNECT`; the disconnect watch | gate parser 1.25 / 1.33; i9 end to end 1.08 / 0.99 at 8 / 64 connections | http-log, prism, Detent |
| [http-log](#http-log) | `6ee47af` | `1c856fd` | **Code change:** `AccessLog::handle` is a coroutine | not measured | prism, Detent |
| [http-parser](#http-parser) | `52a30d0` | `145c905` | Rejects request smuggling unless lenient; two new error numbers | gate 1.78 / 2.17 | http, Detent |
| [io](#io) | `3893d47` | `89d6b0f` | `pread` reads to the full count | gate 0.94 / 0.96 (the extra `pread` at end of file) | fs, pki, system, Xapiand |
| [iterators](#iterators) | `55cd86b` | `c71360c` | Same types; no `std::iterator` base | unchanged | none |
| [journal](#journal) | `d564dfe` | `df25694` | Its completion pin moves; fetches allocators and crc32c | not measured | consensus, Detent |
| lazy | `78a8281` | `b7d840a` | Docs only | unchanged | none |
| located-exception | `4dcb2b4` | `9cce2c7` | Docs only | unchanged | msgpack |
| [logger](#logger) | `ce27b90` | `a82454b` | Write delay of a burst; timestamps; order across threads | gate 2.88 / 2.45; producer `L_INFO` 225 ns against 715 (i9) | http-log, prism, Detent |
| lru-cache | `7dd23eb` | `df0ebc8` | Docs and bench only | gate 0.97 / 1.14 (placement) | Detent |
| [math](#math) | `2730483` | `e125467` | 8- and 16-bit overflow; `modulus` of the lowest value and of zero; `min<double>` | gate 0.99 / 0.99 (the zero-modulus guard) | Xapiand |
| md5 | `fbb8ff0` | `3c7fe15` | Same output | gate 1.13 / 1.16 | none |
| [metrics](#metrics) | `645d729` | `db490b4` | `AtomicCounter` is an alias of a template; new contended types | gate 1.16 / 1.04 | completion, Detent |
| [msgpack](#msgpack) | `3c408cf` | `f470c92` | Repeated keys; growing arrays of maps; `replace` and `put` over a read value; `erase()`'s count; JSON of non-string keys and NaN | gate 1.21 / 1.27 | Xapiand |
| [namegen](#namegen) | `70bd983` (fantasyname) | `3eb14ce` | Every alternative equally likely; one engine per thread; target name | a name 2.1 to 2.9x faster (M4 Pro) | Xapiand |
| nanosleep | `c894531` | `974680b` | Docs only | unchanged | time-point, traceback |
| persistent-map | `938d65e` | `d7acbb5` | Docs only | unchanged | none |
| pki | `cce99b0` | `c662da1` | Same results (io and char-classify pins) | unchanged | none |
| prism | `17ce07e` | `bcc9860` | The application: coroutine handlers and its libraries' changes | not measured | none |
| prospect | | `ec34afb` | The owner's active work: its formats change between phases; it has no CHANGELOG, so read its [docs/STATUS.md](https://github.com/Kronuz/prospect/blob/main/docs/STATUS.md) | | |
| queryparser | `8a9798f` | `f554cd3` | Same results (analysis pin) | unchanged | none |
| [queue](#queue) | `7df74b2` | `4fa1eb1` | Who a pop or `clear()` wakes; `count()` after move assignment | gate 3.67 / 4.45 | server, Xapiand |
| radix-router | `35aab1b` | `74ab7ce` | Docs and bench only | gate 1.02 / 1.00 | http, Detent |
| [random](#random) | `115f3f3` | `e040c2b` | The sequence | gate 3.02 / 5.65 | scheduler, Detent, Xapiand |
| [reactor](#reactor) | `ef26c30` | `ade618d` | **Code change:** no worker pool, `AdmissionGate`, constructors | not measured | cluster, consensus, http, prism, Detent |
| [repr](#repr) | `2063945` | `56d3800` | `max_size == 1` | gate 4.40 / 3.85 | http-log, msgpack, strings, Detent, Xapiand |
| residency | `f4206c7` | `a0a183c` | Docs only (task pin) | unchanged | strata |
| [scheduler](#scheduler) | `ae3f0f9` | `80acde0` | **Code change:** no `shared_from_this()` on a task; a task no longer waits out the idle sleep | gate 1.06 / 1.17; "make only" 10 to 15% faster than start | logger, Detent, Xapiand |
| sha256 | `e440b98` | `55a44ca` | Same output | gate 1.41 / 1.11 | Detent |
| snowball | `51582e3` | `3efcd0f` | Docs and bench only | unchanged | analysis, prospect |
| sortable | `1aa2f98` | `33ed972` | Docs only | unchanged | none |
| [soundex](#soundex) | `89f9d51` | `4622467` | Same codes; copying an encoder compiles | gate 2.11 / 1.83 | string-similarity |
| split | `27dbc41` | `40af1a2` | Docs only | gate 1.00 / 1.01 | fs, strings, Detent |
| [stash](#stash) | `2e2b75f` | `8fa5d2a` | Same results; leaf and chain-node layout | gate 1.75 / 1.80 | scheduler, Detent |
| static-string | `e0a3d6e` | `46561fa` | Docs only | unchanged | hashes, strings, term-color, Detent |
| [storage](#storage) | `7b9abd1` | `cfb59f6` | Records past 4 GiB; damaged records; volume locks; base paths | gate 1.01 / 0.98; i9 compressed whole reads 1.17 to 1.65x start | Xapiand |
| strata | | `2d1066b` | The owner's active work: its formats change between phases; it has no CHANGELOG, so read its [docs/STATUS.md](https://github.com/Kronuz/strata/blob/main/docs/STATUS.md) | | prospect |
| [strict-stox](#strict-stox) | `f0f7374` | `b947d77` | Input of 64 bytes or more parses; no libc for undecided decimals | gate 1.75 / 1.52; every row at least 1.07x start | datetime, msgpack, storage, Detent, Xapiand |
| [string-similarity](#string-similarity) | `ddfb8d1` | `1e0a211` | Jaro, Jaro-Winkler, Dice, weighted Levenshtein, phonetic scores | gate 20.8 / 23.2 on unchanged answers | Xapiand |
| [stringified](#stringified) | `c8c9033` | `07c9505` | Copies no longer dangle; `c_str()` stays in bounds | gate 1.05 / 1.20 on unchanged rows | fs, storage, Xapiand |
| [strings](#strings) | `62fb121` | `2a75908` | `indent`, empty-search `replace`, `hasupper` | gate 2.10 / 1.67 | fs, http-log, soundex, string-similarity, system, traceback, Detent, Xapiand |
| system | `c5b8e50` | `c1e19ab` | Same results (io and strings pins) | unchanged | none |
| task | `9a85e89` | `8cad661` | Docs only | unchanged | prospect, residency, strata |
| [term-color](#term-color) | `032ef09` | `4af732e` | Same output; `resolve()` and `policy` | gate 6.10 / 4.59 | logger, strings, traceback, Detent |
| termdict | `cdb8042` | `d7f5954` | Same results (fst and varint pins) | unchanged | strata |
| [threadpool](#threadpool) | `e961e44` | `ad0af33` | Same results; `TaskGroup` scheduling; queued task type; `post()`, `ending()` | gate 2.01 / 2.34; `TaskGroup` burst 3 to 4x start | scheduler, strata, Detent |
| [time-point](#time-point) | `2f1f7f9` | `fec2589` | Instants before the epoch on clocks finer than a nanosecond; coarse clocks build | gate 1.00 / 0.99 | none |
| [times](#times) | `666dfdd` | `0403e5c` | Seconds past `int`; fractions on x86; negative values folded | gate 1.17 / 1.06 | none |
| [traceback](#traceback) | `099d795` | `6846ee3` | `dump_callstacks` prints a blank line after each thread header | not measured | prism |
| [uinteger_t](#uinteger_t) | `85316dd` | `f3203ab` | Digits outside the base throw; base-256 leading zero bytes; `x *= 1` after a right shift; `sizeof` 88 and its own container | decimal `str()` 43 to 530x and parsing 57 to 121x start (M1 Pro) | base-x, Xapiand |
| unicode | `d80b6bb` | `297413c` | Same tables and decoding | gate 1.31 / 1.22 | analysis, prospect |
| [url-parser](#url-parser) | `4424e25` | `e528e77` | `normalize_path` and `PathParser` on empty, `.` and `..` paths | gate 7.99 / 7.75 | Xapiand |
| utype | `6e2c2a8` | `b2cac7a` | Docs only | unchanged | none |
| varint | `d9631ab` | `ac6003e` | Docs and bench only | unchanged | cluster, strata, termdict, Detent |

## Commits not to pin

Some changes broke something that a later commit fixes. Pin before the first column or at or after
the second. The last rows are libraries whose own pin, inside the range, carries a dependency's bad
range to a consumer that takes the dependency through them.

| Library | Broken from | Fixed in | What goes wrong |
|---|---|---|---|
| allocators | `2fc537f` | `e38f759` | Container copy assignment shares the source's pool, so the two containers used from two threads corrupt the heap. |
| base-x | `8572a00` | `fdee12d` | Does not compile: it calls uinteger_t's chunk primitives, which the uinteger_t it pins lacks. |
| base-x | `1687e9a` | `8935fe6` | Does not compile: it calls `digits()` and `from_digits()`, which the uinteger_t it pins (`aeeeb67`) lacks. |
| base-x | `2507a82` | `b468653` | On a 32-bit `size_t`, an RFC 4648 encode of 512 MiB or more wraps its digit count and writes wrong text. |
| bloom-filter | `c32355b` | `77dca4c` | An unconditional `unsigned __int128` breaks every includer on MSVC, on 32-bit targets and under GCC `-Wpedantic -Werror`. |
| compressors | `0498bf5` | `8f57675` | A crafted 98 KB LZ4 stream makes `decompress_lz4` reserve 64 MB; a refused allocation throws `bad_alloc` instead of `LZ4CorruptVolume`. |
| fs | `14932b9` | `d6d8bc2` | `copy_file` onto the same file (the same path, a hard link or a symlink to it) truncates the source to 0 bytes and returns 0. |
| fst | `b1e8ff3` | `8058003` | Verifying a node-registry hit reads past the end of the bytes the builder has written (heap use after free under ASan). |
| generation-cache | `715f2af` | `2930a64` | A `Key` or `Value` copy or move that throws in `try_insert` or in a rehash loses entries or leaves a slot that a later `get` dereferences. |
| http | `bda9b5a` | `fce24c6` | A streamed body cut short reads as a clean end of file, and a throwing `on_cancel` callback is a heap use after free or escapes `io_context::run()`; until `7bdb90a` a feed error also left the handler holding a freed frame. |
| logger | `dc1fe62` | `06a27d2` | A `clears` line due within 1 ms can be written before an immediate line logged earlier. |
| metrics | `aa7a3d8` | `4890fc0` | `AtomicCounter::add` racing an add that saturates the counter can wrap it, permanently (`9207dd3` narrows the window and does not close it). |
| queue | `b1b38b0` | `e94be7d` | Waits block forever: two `Queue`s sharing one state, `clear()` with parked producers, `QueueSet::erase`, and a pop that leaves the size at or above the threshold. |
| random | `0667b61` | `86bd0f5` | On MSVC: `0667b61` does not compile, and from `8df54fb` the 128-bit multiply swaps its halves, so `random_int` returns values outside its range on x64. |
| string-similarity | `0939c0c` | `c0825ff` | `PhoneticMetric<Encoder, Sorensen_Dice>` bound to a string scores 0 for every pair whose codes differ. |
| strict-stox | `70b8325` | `199e0be` | The fast path ignores the rounding mode: under `fesetround(FE_UPWARD)`, `strict_stod("-0.1")` gives `-0.1` where libc gives `-0.099999999999999991`. |
| stringified | `2c78a1d` | `0053465` | A string literal passed to an overload set over `stringified` and `std::string_view` or `const std::string&` is ambiguous and does not compile. |
| uinteger_t | `8f1345e` | `dabd824` | A refused allocation of the carry limb in `x += y` or `++x` leaves `x` holding the wrapped sum, untrimmed. |
| uinteger_t | `bd7bab1` | `819daa4` | On a 32-bit `size_t`, `digits()` or `from_digits()` of 512 MiB or more wraps a size and writes past its buffer. |
| uinteger_t | `6e74834` | `b012716` | On a 32-bit `size_t`, `digits()` of a value of 2^32 bits or more wraps its bit count and returns wrong digits. |
| completion | `5ef01ad` | `43d3fef` | Pins metrics `9207dd3` and allocators `2fc537f`, inside their ranges above (completion uses neither path). |
| fs | `487c401` | `c4bf223` | Pins stringified `2c78a1d`, inside its range above. |
| http-log | `c7772ab` | `d2315b8` | Pins http commits inside http's range above. |
| journal | `d5b8bc1` | `c733261` | Pins allocators `2fc537f`, inside its range above (journal uses only the resource accounts). |

## Libraries

Each section has the same four parts: the inputs whose results change, what a build or the API
needs, how a consumer finds out, and what the move buys. The CHANGELOG link has the rest.

### allocators

Start `e8fb173`, fixes `085331c`, `2fc537f`, `e38f759`, `7cdb0f8`, `e075c1b`, `9f575e3`; head `6eb7fb2`.
[CHANGELOG](https://github.com/Kronuz/allocators/blob/main/CHANGELOG.md)

- **Changes:** copies and rebinds of a `memory_pool_allocator` share one pool family and compare
  equal (every copy had its own pool, so a `std::list` or `std::map` freed nodes into the wrong one);
  move assignment and swap propagate the pool, copy assignment does not, and a copy-constructed
  container gets a new pool. `construct` perfect-forwards, so an object moved into such a container
  is left moved-from. In the tracked build (`XAPIAND_TRACKED_MEM`) blocks are 16-byte aligned; on
  Apple arm64 they were 8 mod 16 (`e075c1b`).
- **Build and API:** `memory_pool_allocator` gains a local free list (`9f575e3`), so its size grows:
  rebuild every translation unit together. Builds without `NDEBUG`, or with `ALLOCATORS_POOL_CHECK`,
  abort when two threads use one pool at once (`set_pool_misuse_handler` replaces the abort). The
  resource headers are unchanged.
- **Detect:** containers over these allocators, and code that reads an object after moving it into
  one. Xapiand uses only `total_allocated()`; completion and journal use only the resource accounts.
- **What you get:** gate 1.30 / 1.20. The one-block pool pair takes 0.66 ns on the M4 Pro against
  start's 1.16; on the i9 1.00 against 0.74, the cost of not sharing a pool on copy assignment
  ([allocators#1](https://github.com/Kronuz/allocators/issues/1)).

### base-x

Start `54a9326`, fixes `8935fe6`, `c3965ec`, `d1fda10`, `36dd216`, `712c643`, `f702d6d`, `b8fc1a2`,
`10a5f0b`, `2507a82`, `b468653`, `d3d9f23`, `27be05e`, `c599da0`; head `14d086c` (on `master`).
[CHANGELOG](https://github.com/Kronuz/base-x/blob/master/CHANGELOG.md),
[record](reviews/2026-10-31-uinteger_t-base-x.md)

- **Changes:**
  - The RFC 4648 presets write and read the bytes, as Python's `base64` does: leading zero bytes are
    kept (`0x01` was `Q===` in base64 and is `AQ==`), every base32 and base64 text of 32 bytes or more
    changes, `Base16::rfc4648()` writes two digits per byte, and empty is empty (`c3965ec`, `2507a82`).
  - `Base58::bitcoin()` and `ripple()` keep leading zero bytes both ways (`00 00 61 62 63` was `ZiCa`
    and is `11ZiCa`) (`27be05e`); `bitcoinchk()`, `ripplechk()` and the other presets keep the numeric
    text.
  - All-zero bytes are one zero digit with no check character in every numeric preset
    (`Base16::base16()` was empty and is `0`; `dubaluchk()` was `zN` and is `z`) (`8935fe6`, `b8fc1a2`).
  - `decode` throws on text after the padding, on a NUL in an alphabet without padding, on an
    unknown Crockford check byte and on empty `*chk` text, and leaves a `uinteger_t` result as it was
    when it throws (`d3d9f23`, `36dd216`, `712c643`, `10a5f0b`, `c599da0`).
  - `is_valid` accepts `=` padding and Crockford's extended check characters and rejects a digit
    after the padding (`f702d6d`); `encode` into a non-empty result pads and sums only its own text
    (`d1fda10`).
- **Build and API:** the target, C++17 and the options are unchanged. New: the `BaseX::leading_zeros`
  flag and `BASEX_NO_SIMD`; new throws "Error: Encoded string is too short" and `std::length_error`
  "Error: Too many bytes". Head pins uinteger_t `291dab8` (its header is unchanged since `afdded1`);
  a project that pins both declares uinteger_t first, at or after base-x's pin.
- **Detect:** `test/golden/encode.txt` holds every preset's text. Encode and decode a sample of stored
  texts with both pins: RFC 4648 text of bytes that start below 0x10 or run to 32 bytes, Bitcoin and
  Ripple base58 with leading zero bytes, and all-zero inputs are the classes that move. None of the
  ids Xapiand mints changes text ([record](reviews/2026-10-31-uinteger_t-base-x.md)).
- **What you get:** a 32-byte base58 key encodes and decodes over 10 times faster than start
  (CHANGELOG); 49.7 and 52.1 ns on an M4 Pro against Firedancer's 41.4 and 44.0 and libbase58's 1,234
  and 179, and 149 and 205 ns on an i9 against Firedancer's 71.8 and 91.2 (README).

### bloom-filter

Start `0410185`, changes `c32355b`, `08f5e15`, `77dca4c`; head `05bd553`.
[CHANGELOG](https://github.com/Kronuz/bloom-filter/blob/main/CHANGELOG.md)

- **Changes:** `BloomFilter<N>` keeps its bits. `FastBloomFilter<N>` and `BlockedBloomFilter<N>` are
  new and set different bits, so a bitset persisted from one type does not load into another.
- **Build and API:** `BLOOM_FILTER_NO_INT128` (`77dca4c`); the hashes pin moves past the removal of
  hashes' `crc32c.hh`.
- **Detect:** bitsets persisted from one type and loaded into another.
- **What you get:** gate 1.00 / 0.98 on `BloomFilter`; a `FastBloomFilter` 16-byte miss takes 8.0 ns
  against 27.7 for `BloomFilter` on the M4 Pro.

### boolean-parser

Start `41a20b5`, fixes `00b3021`, `172a5c2`; head `85110af`.
[CHANGELOG](https://github.com/Kronuz/boolean-parser/blob/main/CHANGELOG.md)

- **Changes (owner decision):** an implicit `OR` obeys precedence (`a AND b c` was `a OR (b AND c)`
  and is `(a AND b) OR c`; `NOT a b` is `(NOT a) OR b`); an implicit `OR` before `NOT` or `(` parses
  (`a NOT b` was rejected); a repeated binary operator groups to the left, which changes what `MAYBE`
  means; malformed input that start accepted by dropping operands (`a NOT`, `a ()`), an unclosed `(`
  and an operator without operands throw `SyntacticException` from the constructor. `PrintTree()` of a
  `MAYBE` node no longer crashes. Xapiand builds its query from the RPN queue.
- **Build and API:** `BooleanTree` holds its first tokens and input bytes inline, and nodes come from
  a per-thread cache, so the layout grows; the node API is unchanged.
- **Detect:** `old_dump` (`test/frozen/`) and `new_dump` render one input's queue and tree; run both
  over a log of real queries. `oracle::changed_class` in `test/oracle.h` classifies a token sequence.
- **What you get:** gate 2.71 / 3.43; a typical query parses in 344 ns against 780 on the M4 Pro.

### btree

Start `25f9494`, fixes `d81f2a3`, `a56261d`, `512febb`, `599e853`; head `45c8206` (on `master`).
[CHANGELOG](https://github.com/Kronuz/btree/blob/master/CHANGELOG.md)

- **Changes:** with keys on the heap, a refused allocation during a split, rebalance, merge, erase or
  root replacement lost or misordered entries, leaked or double-freed; a refused insertion now leaves
  the tree unchanged and erase allocates nothing. A failed construction after a split no longer leaves
  `size()` one too high, and a move-only mapped value that throws during root growth keeps its keys.
  Maps accept move-only keys.
- **Build and API:** a map slot is a union of `std::pair<Key, T>` and `std::pair<const Key, T>`; node
  layout and sizes are unchanged. Rebuild every translation unit against one revision.
- **Detect:** allocation-failure tests, allocation counts, and builds that mix header revisions.
- **What you get:** gate 1.07 / 1.12; `emplace` of string keys 2.4 times faster with Clang and 2.0
  with GCC; 65,536 erases with 200-byte keys make no heap calls (72,692 at start).

### cartesian

Start `6eab8ed`, fixes `79ed663`, `7066e9e`; head `05cab81`.
[CHANGELOG](https://github.com/Kronuz/cartesian/blob/main/CHANGELOG.md)

- **Changes:** `std::hash<Cartesian>` hashes the bits of `x`, `y`, `z` and the SRID, the fields
  `operator==` compares, instead of `to_string()`. Every hash value and the iteration order of
  unordered containers keyed on `Cartesian` change, and two points that compare equal but differ in
  `scale` hash alike.
- **Detect:** stored hash values, or tests that depend on unordered iteration order. No family
  library or Xapiand persists them.
- **What you get:** gate 2.67 / 2.47; a hash takes 0.77 ns on the M4 Pro, where `to_string()` took
  214.

### char-classify

Start `a890496`, additions `d670574`, `7eb6468`, `684a962`; head `57613ed`.
[CHANGELOG](https://github.com/Kronuz/char-classify/blob/main/CHANGELOG.md)

- **Changes:** none; `chars.hh` gives the same answers.
- **Build and API:** new headers `chars_simd.hh` (`FirstOf<N>`, `Outside<N>`, `find_outside`,
  `ascii_lower`, `ascii_upper`) and `chars_escape.hh` (the escaping kernel of escape and repr), plus
  `chars::hex_value`; `CHARS_NO_SIMD` selects the portable backend.
- **Detect:** nothing to detect.
- **What you get:** gate 1.01 / 1.00 on `chars.hh`; the kernel is most of escape's 2.88 / 2.43 and
  repr's 4.40 / 3.85.

### cluster

Start `4d894db`, head `4863feb`. No change of its own code; its pins move.
[CHANGELOG](https://github.com/Kronuz/cluster/blob/main/CHANGELOG.md)

- **Changes:** none in cluster. Its reactor pin moves from `fe8c5ce` to `c6b2c3e`, across reactor's
  `67e22a6` (see [reactor](#reactor)); its varint pin moves over bench and docs commits.
- **Build and API:** `Bus` already uses `UdpServer(on_datagram)`, so cluster's API is unchanged. A
  consumer that takes reactor through cluster's pin gets reactor's new constructors.
- **Detect:** the build of code that uses reactor directly.
- **What you get:** not measured against start; the README's Performance section times the bus and
  an election.

### completion

Start `03cef1d`, head `8644a8e`. Its own code adds tests; its pins move.
[CHANGELOG](https://github.com/Kronuz/completion/blob/main/CHANGELOG.md)

- **Changes:** none in completion's results.
- **Build and API:** the metrics pin moves to `d7d4c4d`, where `AtomicCounter` is
  `BasicAtomicCounter<std::uint64_t, std::atomic>`: a forward declaration `class AtomicCounter;`
  breaks and mangled names change. The allocators pin moves to `6eb7fb2` (resource headers unchanged).
  `AllocationContext` and `OwnedAllocator<T>` alias the `allocators::resources` types since `21809c7`
  (2026-10-19, before the start, filed under 2026-10-30 in the CHANGELOG); Detent pins `5251cf9`,
  before it. Rebuild dependents together; persisted bytes are unchanged.
- **Detect:** the build.
- **What you get:** not measured.

### compressors

Start `17873b2`, fixes `f157dab`, `8f57675`, `533bee4`, `430870c`; head `5c54128`.
[CHANGELOG](https://github.com/Kronuz/compressors/blob/main/CHANGELOG.md)

- **Changes:** a damaged LZ4 record whose length exceeds the block buffer overflowed the heap and
  throws `LZ4CorruptVolume`; a zstd frame that claims more than 32,768 bytes per compressed byte
  throws `ZstdCorruptVolume`; a zlib stream with a preset dictionary throws `DeflateException`;
  `decompress_lz4` sizes its buffers by the decoded data and throws `LZ4CorruptVolume` instead of
  `bad_alloc`. `XXH32` reads little-endian on every host, so a big-endian host's digest changes and
  matches upstream (storage persists it). One `XXH32` update of 4 GiB and 5 bytes or more digested as
  a short input; it matches upstream (`430870c`). Valid streams decode to the same bytes, and the
  compressed bytes are unchanged.
- **Build and API:** `XXH32_state_t` keeps its lanes as `v[4]` (it was `v1` to `v4`);
  `COMPRESSORS_XXH32_PLAIN_BELOW` tunes the short-update path (`94a3758`); `decompress_zstd(compressed,
  out)` is new; the one-shots are out of line.
- **Detect:** catch sites for decompression errors, any input that decompressed to an empty result,
  digests written on a big-endian host, and code that names `XXH32_state_t`'s fields.
- **What you get:** gate 1.27 / 1.28; the one-shot calls 1.75 / 1.87; XXH32 of 256 B in one update
  takes 8.4 ns on the M4 Pro (start 10.9) and 32.6 on the i9 (start 42.8).

### consensus

Start `a4c28e0`, head `63ba7d9`. No change of its own library code; its pins move.
[CHANGELOG](https://github.com/Kronuz/consensus/blob/main/CHANGELOG.md)

- **Changes:** the demo ticks inside the election window, so its proposal commits (`259b217`).
- **Build and API:** the journal pin moves to `eb99e70`, which fetches allocators and crc32c (journal's
  CRC-32C comes from `crc32c`, with the same stored bytes) and moves completion across its aliasing and
  metrics' alias (see [completion](#completion)). The transport's reactor pin moves to `c6b2c3e`: timer
  and posted-callback exceptions go to `L_EXC`, and a repeating `PeriodicTimer` rearms before it
  propagates one.
- **Detect:** the build.
- **What you get:** not measured against start; the README's Performance section times a
  checkpoint.

### crc32c

Start `b60a8e5`, changes `ce14992`, `f004191`; head `0d5460d`.
[CHANGELOG](https://github.com/Kronuz/crc32c/blob/main/CHANGELOG.md)

- **Changes:** none; values are unchanged. Detection calls `__builtin_cpu_init()` first: a CRC taken
  during static initialization on macOS no longer keeps the whole run on the table path.
- **Build and API:** `detail::x86_update` and `arm_update` are `detail::hardware_update` and
  `hardware_plain` (namespace `detail` only). hashes' `crc32c.hh`, `hashes::crc32c`, `Crc32c` and
  `crc32c_combine` are gone since `hashes:aba7865`, with no forwarding header: include
  `<crc32c/crc32c.hh>`, use `kronuz::crc32c::`, link `crc32c::crc32c`.
- **Detect:** the build, for code that includes hashes' `crc32c.hh`.
- **What you get:** gate 1.48 / 1.39; on the i9, 16 B 4.45 GB/s against 3.76, 4 KiB 29.9 against
  17.8, 1 MiB 29.8 against 19.9; on the M4 Pro, 1 MiB 29.1 against 22.1.

### datetime

Start `fce3d4d`, fixes `fe618d8`, `03f36fa`, `773205b`, `22d1f6a`, `0dc7345`; head `babf3f5`.
[CHANGELOG](https://github.com/Kronuz/datetime/blob/main/CHANGELOG.md)

- **Changes (owner decision):** a negative hour, minute or second is `OUT_OF_RANGE`; a fraction dot
  with no digits or more than 62 is `ERROR` (`isDatetime` accepted both); a loose-format time ending in
  `Z` parses as UTC and one with an offset sets `is_utc`; `2020-12-15||+12M` is `2021-12-15` (it threw);
  date math is 64-bit and a result outside years 1 to `INT_MAX` throws `Year is out of range`; a
  timestamp before 1970 with a fraction converts right (`-2.9` was 23:59:58.0 and is 23:59:57.1).
  Xapiand calls `isDate` and `isDatetime` for schema detection, so a new field whose first value is in
  a changed class gets another type. `TimedeltaParser("")` throws without reading out of bounds.
- **Build and API:** the strict-stox pin moves to `752cf9f`. A datetime before `22d1f6a` built with a
  strict-stox at `c1c9bc1` or later accepts a 63-digit fraction and a 64-character date-math term; move
  the two pins together.
- **Detect:** `test/old/` holds the original (`DatetimeOld`), and `test/diff_test.cc` lists each class
  with its oracle; run stored date strings and logged date-math expressions through both.
- **What you get:** gate 6.44 / 7.44; an ISO 8601 parse takes 8 to 26 ns against 41 to 230 (CHANGELOG).

### double-metaphone

Start `91c17a2`, head `b3191c4`. [CHANGELOG](https://github.com/Kronuz/double-metaphone/blob/main/CHANGELOG.md)

- **Changes:** none; every key equals start's (`test/diff_test.cc`).
- **Build and API:** `DoubleMetaphone b = a;` from a non-const lvalue, and `emplace_back(a)`, compile
  (`41656f1`).
- **Detect:** nothing to detect.
- **What you get:** gate 1.90 / 2.26; a dictionary word encodes in 61 ns against 132 on the M4 Pro.

### enum-reflection

Start `79fe3fa`, fixes `7d394c5`, `2a5da3a`, `36cf117`; head `f953508`.
[CHANGELOG](https://github.com/Kronuz/enum-reflection/blob/main/CHANGELOG.md)

- **Changes:** `enum_type` and `enum_try_type` compare the name after the hash matches, so a string
  built to share a member's 64-bit hash (15 bytes were enough) misses: `enum_type` throws
  `std::out_of_range`, `enum_try_type` returns `std::nullopt`. Every real name gives the same answer,
  ASCII case-insensitively as before.
- **Build and API:** `enum_try_type` is new (`7d394c5`). `enum.h` includes `<bit>`, `<cstddef>`,
  `<cstdint>`, `<cstring>` and `<type_traits>`, and its compile time halves (`36cf117`). The bench
  option is `ENUM_REFLECTION_BUILD_BENCH` (it was `ENUM_REFLECTION_BENCH`, with no alias). The hashes
  pin moves past the removal of hashes' `crc32c.hh`.
- **Detect:** lookups of names that are not members; only a crafted string changes. Xapiand passes
  schema properties to `enum_type<StemStrategy>`.
- **What you get:** hits are 1.01 to 1.35 times start's speed, except the 8-member hit on the M4 Pro
  (0.94, the cost of verifying a hit; [enum-reflection#1](https://github.com/Kronuz/enum-reflection/issues/1)).

### errno-names

Start `a5ab101`, fix `0ec0801`; head `cfe571a`.
[CHANGELOG](https://github.com/Kronuz/errno-names/blob/main/CHANGELOG.md)

- **Changes:** `error::description()` returned `"Unknown error: N"` for every errno on glibc; it
  returns libc's text there (`description(ENOENT)` is `"No such file or directory"`). macOS is
  unchanged.
- **Detect:** log lines on Linux; storage, traceback and Xapiand's I/O traces describe errors through
  it.
- **What you get:** gate 1.00 / 1.00.

### flume

Start `7184cb4`, change `d34313e`; head `defd5a1`.
[CHANGELOG](https://github.com/Kronuz/flume/blob/main/CHANGELOG.md)

- **Changes:** none by default. Through its compressors pin a big-endian host's XXH32 footer changes
  and matches a little-endian peer.
- **Build and API:** `Receiver(sink, max_block)`, `max_block()` and `max_block_for()` cap what a
  sender can make the receiver hold; the default 0 behaves as before.
- **Detect:** transfers between hosts of different byte order.
- **What you get:** gate 1.00 / 1.01.

### fs

Start `ce16118`, fixes `14932b9`, `0b5f78e`, `d6d8bc2`, `8848b49`, `bf10f39`, `7a10a04`, `d172a13`,
`8e5f3d2`; head `aa06315`. [CHANGELOG](https://github.com/Kronuz/fs/blob/main/CHANGELOG.md)

- **Changes:**
  - `copy_file` truncates a longer destination, returns `-1` on a failed open, a short write (a full
    disk, `RLIMIT_FSIZE`) or a failed `close`, and refuses the same file (another spelling, a hard
    link, a symlink) before writing anything.
  - `mkdirs("")` and `build_path_index("")` return `false` and create nothing.
  - `normalize_path` returns Python's `os.path.normpath` form: `""`, `.`, `./`, `x/..`, `x/../` and
    `./x/..` are `.` (the empty path was `/`); a `..` removes the component before it, the first one of
    a relative path included (`a/../b` was `a/b` and is `b`); a relative path keeps the `..` it cannot
    remove (`../a` was `./a`); the root absorbs it; `./a` is `a`; `...` is a name; `//x` is `/x`. A
    non-empty input without a `.` gives the bytes it gave. Pins from `7a10a04` to before `8e5f3d2` give
    answers of neither kind.
- **Build and API:** pins move (io, strings, split, stringified).
- **Detect:** callers that copy over existing files, treat 0 as success on a full disk, copy a
  directory onto itself or pass an empty path. Xapiand's `master` normalizes its data and working
  directories (`src/main.cc:652`, `:709`), endpoint paths (`src/endpoint.cc:242`) and the WAL's base
  path (`src/database/wal.cc:729`): an empty data directory resolved to `/` and resolves to `.`.
  `test_normalize_path_table` holds `os.path.normpath`'s output for 55 inputs.
- **What you get:** `normalize_path` geomean 1.25 on the M4 Pro and 1.66 on the i9 after the one-pass
  loop (`c91b457`), every comparable row faster than start but `np_relative` on the M4 Pro (0.92,
  [fs#1](https://github.com/Kronuz/fs/issues/1)).

### generation-cache

Start `00762bd`, changes `715f2af`, `89baa5b`, `2930a64`, `32a2b4a`, `49a86e9`; head `38a2d39`.
[CHANGELOG](https://github.com/Kronuz/generation-cache/blob/main/CHANGELOG.md)

- **Changes:** `try_insert` has the strong exception guarantee, a rehash that throws keeps every
  entry, and the `operator<` adapter no longer keeps a default-constructed entry when `Value`'s move
  throws. A waiting writer holds new readers back on every platform, so continuous readers no longer
  starve `try_insert` and `clear`. Paths that do not throw return the same values.
- **Build and API:** a one-word reader-writer lock replaces `std::shared_mutex`, so `Cache`'s layout
  changes; the seed is drawn once per process, and constructing a `Cache` cannot throw.
- **Detect:** keys or values whose copy or move can throw, and workloads that read while another
  thread inserts.
- **What you get:** gate 3.22 / 4.35.

### hashes

Start `de5b3ac`, head `a050f6b`. Same values.
[CHANGELOG](https://github.com/Kronuz/hashes/blob/main/CHANGELOG.md)

- **Changes:** none since the start.
- **Build and API:** `crc32c.hh`, `hashes::crc32c`, `hashes::Crc32c` and `hashes::crc32c_combine` were
  removed at `aba7865` (2026-10-20, before the start), with no forwarding header. A pin at or before
  `7ab0c23` (Detent's, and bloom-filter's and enum-reflection's at their starts) still has them, and
  moving it removes them: include `<crc32c/crc32c.hh>`, use `kronuz::crc32c::`, link `crc32c::crc32c`
  ([crc32c](#crc32c)).
- **Detect:** the build.
- **What you get:** unchanged.

### htm

Start `a0321ab`, fixes `cf5177b`, `9006a84`; head `1e041ef`.
[CHANGELOG](https://github.com/Kronuz/htm/blob/main/CHANGELOG.md)

- **Changes:** `getId(Cartesian)` turns floating-point contraction off. A compiler that fused a
  multiply into an add (clang on Apple Silicon or with FMA, GCC on arm64, `-ffp-contract=fast`) put a
  point within rounding of a trixel edge in the neighboring trixel: 0.83% of random points. Every
  build returns the ids of a build without contraction; builds that never fused are unchanged.
- **Detect:** `test/golden.h` holds 396 points with their ids. Xapiand indexes HTM ranges: run the
  old and new `getId` over stored points on the build that wrote the index, and reindex the points
  whose id differs.
- **What you get:** gate 1.00 / 1.06; `getId` takes 591 ns against 914 on the M4 Pro.

### http

Start `c23bb99`, fixes `bda9b5a`, `fce24c6`, `25f4b99`, `3caaeda`, `c37474a`; head `df661f7`.
[CHANGELOG](https://github.com/Kronuz/http/blob/main/CHANGELOG.md)

- **Changes:** trailer fields go to `Request::trailers`, and `header()` reads the header section only
  (a trailer field reached the handler as a header). A `CONNECT` is answered and the connection
  closed. After an HTTP/1.0 request with `Transfer-Encoding` the connection closes. A streamed body cut
  short ends with `connection_reset`, not end of file. Requests that [http-parser](#http-parser)
  rejects are refused. On plain TCP the disconnect watch starts when the handler first calls
  `on_cancel()`, `cancelled()` or `cancel_reason()`, and a peek at that moment reports an earlier
  hang-up; a handler that never asks never sees one. TLS and streamed bodies are watched from the
  start (`c37474a`).
- **Build and API (code change, `bda9b5a`, 2026-10-30, no CHANGELOG entry):**
  `HttpHandler::handle` is `asio::awaitable<void> handle(Request&, ResponseWriter&)` and `Router`
  routes are coroutines; the worker pool, `should_offload`, `BodyReader` and `ChannelBodyReader` are
  gone, and a streamed body is a `BodyStream` read with `co_await`. `HttpAsioService(handler, reactors,
  in_flight_limit, ...)` replaces the `workers` and `queue_limit` arguments; a refused request gets 503
  with `Retry-After: 1`, and a buffered body over 16 MiB gets 413. `http::CancelWatch` and
  `Request::set_cancel_watch` are new, and `Request` gains a pointer: rebuild.
- **Detect:** the build; then handlers that read trailers through `header()`, clients that send
  `CONNECT` or keep an HTTP/1.0 chunked connection open, uploads over 16 MiB to a buffering handler,
  and handlers that expect a hang-up without asking.
- **What you get:** gate 1.25 / 1.33 on the request parser; end to end on the i9 93.7k and 98.7k req/s
  at 8 and 64 connections against start's 87.3k and 98.0k; the M4 Pro is unchanged (`wrk` sets the
  rate).

### http-log

Start `6ee47af`, fix `c7772ab`; head `1c856fd`.
[CHANGELOG](https://github.com/Kronuz/http-log/blob/main/CHANGELOG.md)

- **Changes:** none in what it logs.
- **Build and API (code change):** `AccessLog::handle` is a coroutine that awaits the inner handler,
  as [http](#http) requires, and `AccessLog` no longer forwards `should_offload`. cppcodec is pinned at
  `8019b8b` (it tracked `master`). Move its pin with http's and logger's.
- **Detect:** the build.
- **What you get:** not measured.

### http-parser

Start `52a30d0`, fixes `21c8f30`, `ab8377c`, `62ac7f3`, `0aeec14`, `e2f23b9`, `5cb4409`; head
`145c905`. [CHANGELOG](https://github.com/Kronuz/http-parser/blob/main/CHANGELOG.md)

- **Changes:** unless a consumer sets `parser->lenient_http_headers = 1` after `http_parser_init()`,
  the parser rejects what request smuggling relies on, as upstream http_parser 2.8 to 2.9.4 and llhttp
  do: a
  bare LF (`HPE_CR_EXPECTED`, new); obs-fold and control bytes in a value
  (`HPE_INVALID_HEADER_TOKEN`); a request `Transfer-Encoding` other than exactly `chunked`
  (`HPE_INVALID_TRANSFER_ENCODING`, new); a malformed or trailer `Content-Length`
  (`HPE_INVALID_CONTENT_LENGTH`); a malformed chunk line (`HPE_INVALID_CHUNK_SIZE`); a missing or odd
  version (`HPE_INVALID_VERSION`); a response with `Transfer-Encoding` and `Content-Length`
  (`HPE_UNEXPECTED_CONTENT_LENGTH`) or a malformed status (`HPE_INVALID_STATUS`). After an HTTP/1.0
  message with `Transfer-Encoding` the connection closes; a 1xx, 204 or 304 response has no body; only
  101 upgrades. `http_parser_parse_url()` no longer reads past `buflen`.
- **Build and API:** the two new error numbers come after `HPE_UNKNOWN`, so the others keep their
  values; `struct http_parser` keeps its size. The enum-reflection pin moves to `610203f`.
- **Detect:** `test/diff.cc`'s `changed_class()` names the inputs whose result changes; replay logged
  requests through both pins. With `lenient_http_headers` set the parser reports what start reported.
- **What you get:** gate 1.78 / 2.17.

### io

Start `3893d47`, fix `6524ce0`; head `89d6b0f`.
[CHANGELOG](https://github.com/Kronuz/io/blob/main/CHANGELOG.md)

- **Changes:** `io::pread` loops to the full count, as `io.hh` documents: it stops at end of file
  (the bytes so far) or on an error (the bytes so far, `-1` when none). It returned after one
  `::pread`. A read that reaches end of file makes one more `pread`, which returns 0.
- **Detect:** callers that took a short `pread` for end of file or looped themselves. Xapiand's
  `Storage` policy sees only the extra call at end of file.
- **What you get:** gate 0.94 / 0.96, the extra call (0.99 / 1.01 without that row).

### iterators

Start `55cd86b`, change `e87b125`; head `c71360c`.
[CHANGELOG](https://github.com/Kronuz/iterators/blob/main/CHANGELOG.md)

- **Changes:** none; `std::iterator_traits` reads the same types.
- **Build and API:** `transform` and `chain` declare their member typedefs instead of deriving the
  deprecated `std::iterator`, so the `-Wdeprecated-declarations` warnings are gone and an
  `is_base_of<std::iterator<...>>` test is false.
- **Detect:** nothing to detect.
- **What you get:** unchanged.

### journal

Start `d564dfe`, head `df25694`. Its pins move.
[CHANGELOG](https://github.com/Kronuz/journal/blob/main/CHANGELOG.md)

- **Changes:** its completion pin moves from `21809c7` to `42e74ea`, which brings completion's barrier
  fix: macOS barrier errors other than `ENOTSUP`, `EOPNOTSUPP` or `ENOTTY` are returned, where they were
  retried into success. The stored CRC-32C bytes are unchanged.
- **Build and API:** journal fetches allocators and crc32c; `crc32c()` and `Checksum` forward to
  `kronuz::crc32c`. The completion range brings the one owner lock (journal still calls
  `acquire_owner(bool)`) and metrics' `AtomicCounter` alias ([completion](#completion)).
- **Detect:** the build, and barrier errors on macOS.
- **What you get:** not measured against start.

### logger

Start `ce27b90`, changes `dc1fe62`, `c7332d6`, `bb2d16c`; head `a82454b`.
[CHANGELOG](https://github.com/Kronuz/logger/blob/main/CHANGELOG.md)

- **Changes:** a line that finds nothing pending is written at once (`bb2d16c`); a burst of routine,
  deferred or `clears` lines due within 1 ms of the call is written 1 ms after it, so a hard crash
  inside that millisecond loses them. Timestamps come from the steady clock with a wall offset
  measured every 20 ms (within 2 µs of `system_clock`). Lines are ordered per thread; across threads a
  line may wait behind one due microseconds later. When the LOG thread cannot file a line it runs it
  if due and drops it otherwise. Every other byte written is identical.
- **Build and API:** logger needs a scheduler with `post()` (`5ad60fc` or later): a consumer that
  declares scheduler itself pins it there or later. cppcodec is pinned at `8019b8b`.
- **Detect:** log readers that rely on nanosecond timestamps or on sub-millisecond order across
  threads, and the last lines before a crash.
- **What you get:** gate 2.88 / 2.45; a producer's `L_INFO` costs 225 ns against 715 on the i9, and an
  isolated line reaches the handler in 16.8 µs (M4 Pro) and 42.5 µs (i9) against start's 21.7 and
  58.5.

### math

Start `2730483`, fixes `01ad763`, `5486d04`; head `e125467`.
[CHANGELOG](https://github.com/Kronuz/math/blob/main/CHANGELOG.md)

- **Changes:** `add` and `sub` on `uint8_t` and `uint16_t` report overflow (`add<uint8_t>(250, 10)`
  returned 4 with the flag clear). `modulus` of `INT_MIN`, `LONG_MIN`, `LLONG_MIN` and the lowest
  `int8_t` and `int16_t` returns the least non-negative residue (it was undefined), and
  `modulus(300, uint8_t{7})` is 6 (it was 2). `modulus(val, 0)` throws `std::invalid_argument`.
  `min<double>` is `lowest()`, not about 2.2e-308. Every other result is unchanged.
- **Detect:** the inputs above. Xapiand calls `modulus` in `src/query_dsl.cc` and
  `src/multivalue/generate_terms.cc`.
- **What you get:** gate 0.99 / 0.99, the zero-modulus guard.

### metrics

Start `645d729`, fix `4890fc0`; head `db490b4`.
[CHANGELOG](https://github.com/Kronuz/metrics/blob/main/CHANGELOG.md)

- **Changes:** `AtomicCounter` is start's compare-exchange loop again.
- **Build and API:** `AtomicCounter` is `BasicAtomicCounter<std::uint64_t, std::atomic>`, so a
  forward declaration `class AtomicCounter;` breaks and mangled names change. New:
  `ContendedCounter`, `ContendedDurationHistogram`, `BasicAtomicCounter`, `BasicContendedCounter`. The
  bench builds only with `METRICS_BUILD_BENCH`.
- **Detect:** the build.
- **What you get:** gate 1.16 / 1.04; `ContendedCounter` adds in 194 to 200 ns with eight threads on
  the M4 Pro, against 190 for a bare `fetch_add`.

### msgpack

Start `3c408cf`, fixes `d054ea1`, `c913966`, `d8fa3e6`, `f083ad7`, `adac439`, `1c851dc`; head
`f470c92`. [CHANGELOG](https://github.com/Kronuz/msgpack/blob/main/CHANGELOG.md)

- **Changes:**
  - A map that repeats a key is merged at its first fill: the last value wins in the first
    position (`{"a":1,"a":2,"b":3,"c":4}` was `{"a":2,"b":3,"b":3}` and is `{"a":2,"b":3,"c":4}`).
  - Pushing onto an array of maps after writing into one no longer reads freed memory, and references
    to an element's children survive growth.
  - Filling a map with a key that is not a string throws and leaves the map as it was.
  - `replace()` and `put()` over a value that was read use the new value's index; replacing a value
    locked on its own throws `const_error`; a `lock()` that throws leaves nothing locked; `erase()`
    returns 1 for the last element (it returned 0) (`f083ad7`).
  - `to_string()` and `as_document()` write a key that is not a string as its JSON text (`5` as `"5"`;
    they gave garbage or crashed), `update()` changes nothing when it throws for a reason of its
    arguments (`adac439`), and `to_string()` writes a NaN or infinite float as `null`, where the text
    stopped (`1c851dc`).
- **Build and API:** benches build only with `MSGPACK_BUILD_BENCH`; the strict-stox, repr and
  enum-reflection pins move.
- **Detect:** documents that repeat a key, have a key that is not a string or hold a NaN; code that
  grows an array of maps after writing into it, replaces a value it has read, or counts what `erase()`
  returns. Xapiand stores its documents as `MsgPack`.
- **What you get:** gate 1.21 / 1.27; `unserialise` 1.5 to 2.0 times faster, `hash()` 3.9 to 7.9
  times, `to_string` 1.5 to 2.5 times.

### namegen

namegen is the C++ generator of the `Kronuz/fantasyname` fork, moved to its own repository with its
history; start is the fork's `70bd983`, fixes `c0f9393`, `72b3f1c`, `fd7ab7f`, `c8faf70`; head
`3eb14ce`. [CHANGELOG](https://github.com/Kronuz/namegen/blob/main/CHANGELOG.md)

- **Changes:** every alternative of a choice has probability 1/n (the first and last came up half
  as often), so patterns with more than two alternatives give other names for a seed. Each thread has
  its own engine (`toString()` from several threads raced on one). `combinations()` saturates at
  `SIZE_MAX` (it wrapped).
- **Build and API:** the target is `namegen::namegen`, with `fantasyname::fantasyname` and
  `fantasyname` as aliases; `NameGen::engine()` and `Generator::generate(std::mt19937&)` are new.
- **Detect:** tests that pin the names drawn from a seed. Xapiand names its nodes with it
  (`src/xapiand_namegen.h`).
- **What you get:** compiling a pattern 2.8 to 29 times faster and a name 2.1 to 2.9 times on the M4
  Pro (`sV'i`: 68 ns against 191).

### queue

Start `7df74b2`, fixes `e94be7d`, `31552f9`; head `4fa1eb1`.
[CHANGELOG](https://github.com/Kronuz/queue/blob/main/CHANGELOG.md)

- **Changes:** untimed waits no longer re-check every second, and every state change that can release
  a parked thread wakes one that can use it: two `Queue`s on one state wake only their own consumers;
  `clear()` and `QueueSet::erase` wake parked producers; a pop wakes a producer whenever it leaves room;
  a producer that waited and does not push wakes the next. Move assignment returns the target's items
  to its state, so `count()` no longer reads high. `QueueSet::clear()` compiles.
- **Detect:** code that relied on a parked producer staying parked until a later push or pop, and
  readers of `count()` on a state shared by several queues.
- **What you get:** gate 3.67 / 4.45.

### random

Start `115f3f3`, fix `0667b61`; head `e040c2b`.
[CHANGELOG](https://github.com/Kronuz/random/blob/main/CHANGELOG.md)

- **Changes:** the generator is xoshiro256++ seeded with 256 bits and the ranges use Lemire's method,
  so every sequence differs. There is no seed API, so no sequence was reproducible before either;
  ranges, inclusiveness and the `random_string` alphabet are unchanged.
- **Detect:** tests that assert exact draws.
- **What you get:** gate 3.02 / 5.65; `random_int(0, 999999)` 2.50 ns against 4.43 (M4 Pro).

### reactor

Start `ef26c30`, fixes `67e22a6`, `76c32b4`; head `ade618d`.
[CHANGELOG](https://github.com/Kronuz/reactor/blob/main/CHANGELOG.md) (it begins on 2026-11-01; the
rest comes from the commits)

- **Changes:** the accept loop keeps accepting after a connection that reset while queued (on macOS
  `accept` returned `EINVAL`, and the listener disappeared). `TcpServer::stop()` aborts every tracked
  request, waits up to a grace (5 s), then forces what a stalled peer still holds.
- **Build and API (code change, `67e22a6`):** nothing runs off a reactor's loop: `Reactor::pool()`, the
  `workers` arguments and the worker pools are gone, and `OffloadGate` is `AdmissionGate`. The
  constructors are `TcpServer(reactors, admission_limit, session)` and `UdpServer(on_datagram)`;
  `Reactor::track` takes an `Abortable&`.
- **Detect:** the build.
- **What you get:** not measured against start; level with plain Asio on the M4 Pro (README).

### repr

Start `2063945`, fix `3191c08`; head `56d3800`.
[CHANGELOG](https://github.com/Kronuz/repr/blob/main/CHANGELOG.md)

- **Changes:** `repr(..., max_size = 1)` with a quote wrote both quotes past a one-byte buffer; it
  returns the two quotes. Every other output is byte-identical.
- **Detect:** calls with `max_size` 1.
- **What you get:** gate 4.40 / 3.85.

### scheduler

Start `ae3f0f9`, fixes `36afada`, `62a4fe8`, `34631ec`, `eb2483b`, `e7b4f83`; head `80acde0`.
[CHANGELOG](https://github.com/Kronuz/scheduler/blob/main/CHANGELOG.md)

- **Changes:** a task added between the worker's last look at the wheel and its sleep could wait up
  to the 30 s idle target; it runs when due. A `finish()` that landed between two steps of the worker
  is no longer lost (`34631ec`).
- **Build and API (code change, `e7b4f83`):** `ScheduledTask` no longer derives
  `std::enable_shared_from_this`, so `shared_from_this()` and `weak_from_this()` on a task do not
  compile; a task that needs them derives `std::enable_shared_from_this` on its own type. Xapiand and
  every catalog library were checked: none calls them on a task. `ScheduledTask` is 56 bytes (48 at
  start, 96 with `post()`): rebuild every translation unit. `post()` and `post_ordered()` are new.
- **Detect:** the build; timers that fired late fire on time.
- **What you get:** gate 1.06 / 1.17; "make only" is 10 to 15% faster than start (30.7 ns against 35.9
  on the M4 Pro, 119.8 against 134.8 on the i9), and `post()` costs a producer a sixth of `add()`
  (57 ns against 367 on an Apple M1 Pro).

### soundex

Start `89f9d51`, head `4622467`. [CHANGELOG](https://github.com/Kronuz/soundex/blob/main/CHANGELOG.md)

- **Changes:** none; every code equals start's.
- **Build and API:** copying an encoder from a non-const lvalue or a const rvalue compiles (`407e7d1`).
- **Detect:** nothing to detect.
- **What you get:** gate 2.11 / 1.83.

### stash

Start `2e2b75f`, changes `78a18f3`, `528ccef`, `b0fce1c`; head `8fa5d2a`.
[CHANGELOG](https://github.com/Kronuz/stash/blob/main/CHANGELOG.md)

- **Changes:** none; results and orders are unchanged.
- **Build and API:** a leaf is 16 bytes larger and each chain node 8 (`78a18f3`): rebuild every
  translation unit. `STASH_CLAIM_HINT_HOOK` is a new test hook.
- **Detect:** nothing to detect.
- **What you get:** gate 1.75 / 1.80; filling one leaf is linear, not quadratic (4,000 inserts step over
  1,000 nodes, not 1,998,000). Depth-64 p99 is 0.90 to 0.97 of start, a trade kept until the owner
  rules ([stash#1](https://github.com/Kronuz/stash/issues/1)).

### storage

Start `7b9abd1`, fixes `90aec94`, `a1e49db`, `217e731`, `934b7d9`, `42b1053`, `b141849`; head
`cfb59f6`. [CHANGELOG](https://github.com/Kronuz/storage/blob/main/CHANGELOG.md)

- **Changes:** `read()` and `write()` of a record past 4 GiB of byte offset used a 32-bit product
  (a read ended, a write put its blocks in the wrong place); `growfile()` overflowed past about 1.6
  GiB; a damaged flags byte throws `StorageCorruptVolume`. A writable open holds a shared `flock` and
  `reclaim_volumes` the exclusive one (`EWOULDBLOCK` when they meet); `commit()` syncs the volume
  directory once after creating the file. macOS `fallocate` reserves the length, not offset plus
  length. The vendored `normalize_path` follows [fs](#fs): `Storage("", ...)` opened `/vol.0` at the
  root and opens `./vol.0`. The on-disk format is unchanged.
- **Build and API:** `Storage::StreamWriter` and `reclaim_volumes` are new; an IO policy may provide
  `lock_shared`, `lock_exclusive` and `ftruncate`.
- **Detect:** volumes written or read past 4 GiB, damaged volumes, hosts that open a volume while
  reclaiming, and base paths that are empty or hold `.` or `..`.
- **What you get:** gate 1.01 / 0.98; compressed whole reads on the i9 1.17 to 1.65 times start's
  speed; small-blob writes pay the directory fsync (0.70 to 0.92 on the M4 Pro).

### strict-stox

Start `f0f7374`, fixes `7d7f5dd`, `a1b03fb`; head `b947d77`.
[CHANGELOG](https://github.com/Kronuz/strict-stox/blob/main/CHANGELOG.md)

- **Changes:** valid input of 64 bytes or more (100 leading zeros, a long decimal) was rejected as
  `EINVAL`, or parsed as its first 63 bytes with a wrong `idx`; it parses as libc `strto*` does. The
  decimals its table cannot decide are converted by an exact comparison instead of libc: Apple's
  `strtod` aborted the process on some texts, and FreeBSD's `strtof` returned the smallest normal
  float with no `errno` for some subnormal texts, where `stof` gives `ERANGE`. Shorter input is
  unchanged.
- **Detect:** values of 64 bytes or more that reach a `strict_*` call. `STRICT_STOX_C_LOCALE` changes
  results in a locale whose decimal point is not `.` and is off unless a consumer defines it.
- **What you get:** gate 1.75 / 1.52; every row but `stod` of 800 digits is at least 1.07 times start's
  speed on both machines.

### string-similarity

Start `ddfb8d1`, fixes `efba168`, `0939c0c`, `c0825ff`; head `1e0a211`.
[CHANGELOG](https://github.com/Kronuz/string-similarity/blob/main/CHANGELOG.md)

- **Changes:** `Jaro_Winkler` adds the prefix boost (it returned the plain Jaro score); `Jaro` uses the
  standard window and transposition count; weighted `Levenshtein` is right, and with both costs 0 gives
  0, not NaN; `Sorensen_Dice` counts bigrams as a multiset, and a copied or moved bound one scores
  against its own string; `PhoneticMetric` encodes both operands. Unit-cost Levenshtein, LCSubstr,
  LCSubsequence and Jaccard are unchanged. Xapiand sorts by these metrics, so result order changes.
- **Build and API:** copying a bound metric from a non-const lvalue compiles.
- **Detect:** `test/legacy_metrics.h` holds the old Levenshtein, Jaro and Jaro_Winkler; run a sample of
  sort queries before and after.
- **What you get:** gate 20.8 / 23.2 on the rows whose answers did not change.

### stringified

Start `c8c9033`, fixes `1c1fb3e`, `0053465`; head `07c9505`.
[CHANGELOG](https://github.com/Kronuz/stringified/blob/main/CHANGELOG.md)

- **Changes:** a copy or move of a `stringified` that owned its text views its own storage (it kept
  a view into the source, which dangled); `c_str()` of a bare view copies once instead of reading past
  it. Valid programs get the same text.
- **Build and API:** `stringified(const char*)` returns a C string from `c_str()` without a copy.
- **Detect:** a program that read a copy after its source died sees the right text.
- **What you get:** gate 0.80 / 0.85 with the rows whose behavior changed, 1.05 / 1.20 without them.

### strings

Start `62fb121`, fix `bb85615`; head `2a75908`.
[CHANGELOG](https://github.com/Kronuz/strings/blob/main/CHANGELOG.md)

- **Changes:** `indent` keeps blank lines and the trailing newline, with no prefix on blank lines
  (`indent("a\n\nb", ' ', 2)` is `"  a\n\n  b"`); `replace` with an empty search inserts at every
  position, as Python does (it never returned); `hasupper` tests ASCII `A`-`Z` only.
- **Detect:** `indent` on text with blank lines, any empty search string (the old code hangs), and
  `hasupper` on non-ASCII text in a program that sets a locale. traceback's crash dumps change through
  `indent` ([traceback](#traceback)).
- **What you get:** gate 2.10 / 1.67; joins and replaces with a few matches at parity with start
  ([strings#2](https://github.com/Kronuz/strings/issues/2)).

### term-color

Start `032ef09`, addition `e2e6465`; head `4af732e`.
[CHANGELOG](https://github.com/Kronuz/term-color/blob/main/CHANGELOG.md)

- **Changes:** none; `collapse()` and `color::ansi()` give start's bytes.
- **Build and API:** `resolve(mode, target, is_terminal)` returns a `policy` whose `apply()` decides
  `NO_COLOR` and the depth once.
- **Detect:** nothing to detect.
- **What you get:** gate 6.10 / 4.59.

### threadpool

Start `e961e44`, changes `12f1516`, `5d97d35`; head `ad0af33`.
[CHANGELOG](https://github.com/Kronuz/threadpool/blob/main/CHANGELOG.md)

- **Changes:** results, order, `max_concurrency`, `cancel`, `wait`, `end` and `finish` are unchanged.
  A `TaskGroup` burst runs on the workers that hold its tickets, and a group lists one ticket at a
  time, so which worker runs a group's task can differ. A callable that throws while it is stored is
  not counted, and `enqueue_bulk` wakes up to `count` sleepers.
- **Build and API:** `TaskWrapper<std::function<void()>>` holds a `SmallTask` with 48 bytes inline
  instead of a `std::function`: rebuild every translation unit. `post()` and `ending()` are new.
- **Detect:** code that relies on which worker runs a group's tasks.
- **What you get:** gate 2.01 / 2.34; a `TaskGroup` burst on 16 workers takes 125 ns a task against
  490 on the M4 Pro and 515 against 1,725 on the i9. The i9's p99 delay for one task every microsecond
  is 61 to 90 µs against start's 35 to 47, for a quarter of the pool's CPU, a trade kept until the
  owner rules ([threadpool#3](https://github.com/Kronuz/threadpool/issues/3)).

### time-point

Start `2f1f7f9`, fix `624c2e9`; head `fec2589`.
[CHANGELOG](https://github.com/Kronuz/time-point/blob/main/CHANGELOG.md)

- **Changes:** a conversion that drops precision rounds toward negative infinity: only an instant
  before the epoch on a clock finer than a nanosecond changes (-1500 ps was -1 ns and is -2 ns).
  Nanosecond clocks give the same values bit for bit.
- **Build and API:** `time_point_from_ullong<Clock>` builds for a clock coarser than a nanosecond
  (libc++'s `system_clock`), rounding down to the tick, and `time_point_to_ullong` takes any duration;
  `time_point_to_llong` and `time_point_from_llong` are new.
- **Detect:** `test/diff.cc` names the one class that changes.
- **What you get:** gate 1.00 / 0.99.

### times

Start `666dfdd`, fixes `cb75580`, `1f1f9c0`, `c6d1a90`; head `0403e5c`.
[CHANGELOG](https://github.com/Kronuz/times/blob/main/CHANGELOG.md)

- **Changes:** `timespec_t(double)` keeps whole seconds past `int` (`timespec_t(3e9)` was
  `{2147483647, 2147483647}` on arm64 and `{INT_MIN, INT_MIN}` on x86); the fraction is scaled in
  `double`, so on x86 `timespec_t(0.3)` is 300000000 ns (it was 299999999; 536,298 of 1,111,104
  decimals change on x86, none on arm64); a negative value with a fraction is folded (`-0.5` is
  `{-1, 500000000}`).
- **Build and API:** comparisons with a `double` on the left take `const timespec_t&`, so
  `0.5 < now()` compiles; `TIMES_CTOR_SHAPE` selects the constructor's shape.
- **Detect:** `test/diff.cc` lists the classes against the frozen old code.
- **What you get:** gate 1.17 / 1.06; construction over an array 0.92 / 0.89 of start, the cost of the
  borrow ([times#1](https://github.com/Kronuz/times/issues/1)).

### traceback

Start `099d795`, head `6846ee3`. Its strings pin moves.
[CHANGELOG](https://github.com/Kronuz/traceback/blob/main/CHANGELOG.md)

- **Changes:** `dump_callstacks` (`TRACEBACK_HOOKS`) passes each traceback through `strings::indent`,
  which keeps the leading blank line, so a blank line follows each `<Thread ...>` header.
- **Detect:** parsers of crash dumps.
- **What you get:** not measured.

### uinteger_t

Start `85316dd`, fixes `a39ede0`, `bd7bab1`, `6ff439f`, `d50f9bd`, `204eed1`, `8f1345e`, `10cf088`,
`eb588dc`, `819daa4`, `b012716`; head `f3203ab` (on `master`; `uinteger_t.hh` unchanged since
`afdded1`). [CHANGELOG](https://github.com/Kronuz/uinteger_t/blob/master/CHANGELOG.md),
[record](reviews/2026-10-31-uinteger_t-base-x.md)

- **Changes:**
  - A character that is not a digit below the base, or a byte 0x80 or above, throws
    `std::invalid_argument` (`uinteger_t("9", 8)` was 9) (`bd7bab1`).
  - Base-256 bytes with leading zeros parse right (an all-zero buffer was a zero unequal to 0, and 8 or
    more zero bytes broke `==`, `<` and `bits()`); a division by such a zero throws `std::domain_error`
    (`eb588dc`).
  - `x *= 1`, or any self-assignment, after `x >>= 64` or more keeps the shifted value, and a
    moved-from value is zero (`6ff439f`).
  - A left shift by a `uinteger_t` count of 2^64 or more throws `std::length_error` ("Error: Shift too
    large"), not `std::bad_alloc` (`6ff439f`, `d50f9bd`).
  - Products without `unsigned __int128` and on MSVC are right (`a39ede0`); the bad-base message of
    `str()` names 256 (`204eed1`); on a 32-bit `size_t` a conversion of 512 MiB or more throws
    `std::length_error` before it allocates (`819daa4`, `b012716`).
- **Build and API:** `sizeof(uinteger_t)` is 88 (56 at start) and an inline value points into itself,
  so no `memcpy` or `realloc`; `container` is the library's own small vector with `digit*` iterators.
  `UINTEGER_T_INLINE_LIMBS` and every tuning macro need one value per program. New: `digits()`,
  `from_digits()`, public `compare`, `mul(r, a, b)` and `divmod(q, r, a, b)`; `5 << big` compiles. Copy
  assignment allocates before it releases. The target, C++17 and the options are unchanged; a
  translation unit that prints or parses costs about twice the compile work with the default
  `UINTEGER_T_RADIX_UNROLL`.
- **Detect:** text with characters outside its base or bytes 0x80 and above, base-256 buffers with
  leading zero bytes and divisions by them, shifts by a `uinteger_t` count, and code that treats
  `container` as a `std::vector` or copies a value with `memcpy`.
- **What you get:** decimal `str()` 43 to 530 times and parsing 57 to 121 times faster than start on 2
  to 4,096 limbs (Apple M1 Pro, [record](reviews/2026-10-31-uinteger_t-base-x.md)); 4,096-bit decimal
  printing takes 0.57 (M4 Pro) and 0.76 (i9) of GMP 6.3.0's time, and the other rows 1.0 to 2.6 times
  GMP's; Boost's `cpp_int` takes 1.05 to about 130 times uinteger_t's time except for decimal parsing up
  to 4,096 bits (README).

### url-parser

Start `4424e25`, fixes `2c9ea8e`, `1cdcb53`; head `e528e77`.
[CHANGELOG](https://github.com/Kronuz/url-parser/blob/main/CHANGELOG.md)

- **Changes:** its `normalize_path` follows [fs](#fs) byte for byte (start returned `""` for the empty
  path and for `.` with `keep_slash`, `x` for `x/..`, and kept the last component as written with
  `keep_slash`). `PathParser` follows it, with the current directory as the empty path: `a/..` is the
  empty path (it was the path `a/..` with the id `..`), `a/b/..` is the path `a`, `a/../b` is no path and
  the id `b` (it was the path `a` and the id `b`), and `../a` is the path `..` with the id `a` (it was the
  path `.`). `PathParser::init(std::string_view())` no longer crashes.
- **Detect:** request paths with `.`, `..` or `...` components; Xapiand's search views parse paths
  with `PathParser`. `test/normalize_path_test.cc` holds `os.path.normpath`'s output for 55 inputs.
- **What you get:** gate 7.99 / 7.75.
