# Kronuz C++ Libraries

Eighty small, standalone C++ libraries, each in its own repository under
[github.com/Kronuz](https://github.com/Kronuz). This repo is the index: what exists, what
each one is for, and how to use them together.

They came out of [Xapiand](https://github.com/Kronuz/Xapiand), a distributed RESTful
search engine, over about a decade of building it. Whenever a piece grew sharp enough and
self-contained enough to stand on its own, it was carved out, given a README and a test
suite, and released.

There is no framework here. No umbrella header, no common runtime, no registration step.
Each library is one idea with a narrow surface, most are header-only, and you take the two
you need and ignore the rest.

## Using one

Every repo exposes a CMake target named `<name>::<name>` and pulls its own dependencies
through `FetchContent`, so linking one target puts the whole transitive header set on your
include path.

```cmake
include(FetchContent)
FetchContent_Declare(hashes
  GIT_REPOSITORY https://github.com/Kronuz/hashes.git
  GIT_TAG        main)
FetchContent_MakeAvailable(hashes)

target_link_libraries(my_app PRIVATE hashes::hashes)
```

C++20 is the norm, C++17 for a handful. Tests and demos only build when a repo is the
top-level project, so pulling a library in does not build its suite. `GIT_TAG main` tracks
the tip; pin a SHA when you need reproducibility. MIT licensed, apart from `cpp-btree`
(Apache 2.0).

The include filename often differs from the repo name: `char-classify` gives `chars.hh`,
`constexpr-phf` gives `phf.hh`, `enum-reflection` gives `enum.h`. [AGENTS.md](AGENTS.md)
lists the real include line for every one.

## Build status

Every library builds and runs its tests on Linux (x86_64 with GCC and Clang, arm64),
macOS (arm64, x86_64), and FreeBSD, plus an ASan and UBSan build, through the shared
workflow in [`.github/workflows/cmake.yml`](.github/workflows/cmake.yml).

Assertions stay live in every build, the standard library's own checks are on, a
ThreadSanitizer job runs alongside ASan and UBSan, and every repository runs nightly.
[`tools/preflight.sh`](tools/preflight.sh) runs the same matrix locally, on macOS and on
Linux and FreeBSD VMs, before a push.

| | | |
|---|---|---|
| [allocators](https://github.com/Kronuz/allocators) [![CI](https://github.com/Kronuz/allocators/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/allocators/actions/workflows/ci.yml) | [analysis](https://github.com/Kronuz/analysis) [![CI](https://github.com/Kronuz/analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/analysis/actions/workflows/ci.yml) | [atomic-shared-ptr](https://github.com/Kronuz/atomic-shared-ptr) [![CI](https://github.com/Kronuz/atomic-shared-ptr/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/atomic-shared-ptr/actions/workflows/ci.yml) |
| [base-x](https://github.com/Kronuz/base-x) [![CI](https://github.com/Kronuz/base-x/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/base-x/actions/workflows/ci.yml) | [bitpack](https://github.com/Kronuz/bitpack) [![CI](https://github.com/Kronuz/bitpack/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/bitpack/actions/workflows/ci.yml) | [bkd](https://github.com/Kronuz/bkd) [![CI](https://github.com/Kronuz/bkd/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/bkd/actions/workflows/ci.yml) |
| [bloom-filter](https://github.com/Kronuz/bloom-filter) [![CI](https://github.com/Kronuz/bloom-filter/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/bloom-filter/actions/workflows/ci.yml) | [boolean-parser](https://github.com/Kronuz/boolean-parser) [![CI](https://github.com/Kronuz/boolean-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/boolean-parser/actions/workflows/ci.yml) | [cartesian](https://github.com/Kronuz/cartesian) [![CI](https://github.com/Kronuz/cartesian/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/cartesian/actions/workflows/ci.yml) |
| [char-classify](https://github.com/Kronuz/char-classify) [![CI](https://github.com/Kronuz/char-classify/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/char-classify/actions/workflows/ci.yml) | [cluster](https://github.com/Kronuz/cluster) [![CI](https://github.com/Kronuz/cluster/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/cluster/actions/workflows/ci.yml) | [completion](https://github.com/Kronuz/completion) [![CI](https://github.com/Kronuz/completion/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/completion/actions/workflows/ci.yml) |
| [compressors](https://github.com/Kronuz/compressors) [![CI](https://github.com/Kronuz/compressors/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/compressors/actions/workflows/ci.yml) | [consensus](https://github.com/Kronuz/consensus) [![CI](https://github.com/Kronuz/consensus/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/consensus/actions/workflows/ci.yml) | [constexpr-phf](https://github.com/Kronuz/constexpr-phf) [![CI](https://github.com/Kronuz/constexpr-phf/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/constexpr-phf/actions/workflows/ci.yml) |
| [ctrie](https://github.com/Kronuz/ctrie) [![CI](https://github.com/Kronuz/ctrie/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/ctrie/actions/workflows/ci.yml) | [cuuid](https://github.com/Kronuz/cuuid) [![CI](https://github.com/Kronuz/cuuid/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/cuuid/actions/workflows/ci.yml) | [datetime](https://github.com/Kronuz/datetime) [![CI](https://github.com/Kronuz/datetime/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/datetime/actions/workflows/ci.yml) |
| [docset](https://github.com/Kronuz/docset) [![CI](https://github.com/Kronuz/docset/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/docset/actions/workflows/ci.yml) | [double-metaphone](https://github.com/Kronuz/double-metaphone) [![CI](https://github.com/Kronuz/double-metaphone/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/double-metaphone/actions/workflows/ci.yml) | [endian](https://github.com/Kronuz/endian) [![CI](https://github.com/Kronuz/endian/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/endian/actions/workflows/ci.yml) |
| [enum-reflection](https://github.com/Kronuz/enum-reflection) [![CI](https://github.com/Kronuz/enum-reflection/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/enum-reflection/actions/workflows/ci.yml) | [epoch](https://github.com/Kronuz/epoch) [![CI](https://github.com/Kronuz/epoch/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/epoch/actions/workflows/ci.yml) | [errno-names](https://github.com/Kronuz/errno-names) [![CI](https://github.com/Kronuz/errno-names/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/errno-names/actions/workflows/ci.yml) |
| [escape](https://github.com/Kronuz/escape) [![CI](https://github.com/Kronuz/escape/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/escape/actions/workflows/ci.yml) | [flume](https://github.com/Kronuz/flume) [![CI](https://github.com/Kronuz/flume/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/flume/actions/workflows/ci.yml) | [fs](https://github.com/Kronuz/fs) [![CI](https://github.com/Kronuz/fs/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/fs/actions/workflows/ci.yml) |
| [fst](https://github.com/Kronuz/fst) [![CI](https://github.com/Kronuz/fst/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/fst/actions/workflows/ci.yml) | [fusefilter](https://github.com/Kronuz/fusefilter) [![CI](https://github.com/Kronuz/fusefilter/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/fusefilter/actions/workflows/ci.yml) | [hashes](https://github.com/Kronuz/hashes) [![CI](https://github.com/Kronuz/hashes/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/hashes/actions/workflows/ci.yml) |
| [htm](https://github.com/Kronuz/htm) [![CI](https://github.com/Kronuz/htm/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/htm/actions/workflows/ci.yml) | [http](https://github.com/Kronuz/http) [![CI](https://github.com/Kronuz/http/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/http/actions/workflows/ci.yml) | [http-log](https://github.com/Kronuz/http-log) [![CI](https://github.com/Kronuz/http-log/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/http-log/actions/workflows/ci.yml) |
| [http-parser](https://github.com/Kronuz/http-parser) [![CI](https://github.com/Kronuz/http-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/http-parser/actions/workflows/ci.yml) | [io](https://github.com/Kronuz/io) [![CI](https://github.com/Kronuz/io/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/io/actions/workflows/ci.yml) | [iterators](https://github.com/Kronuz/iterators) [![CI](https://github.com/Kronuz/iterators/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/iterators/actions/workflows/ci.yml) |
| [journal](https://github.com/Kronuz/journal) [![CI](https://github.com/Kronuz/journal/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/journal/actions/workflows/ci.yml) | [lazy](https://github.com/Kronuz/lazy) [![CI](https://github.com/Kronuz/lazy/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/lazy/actions/workflows/ci.yml) | [located-exception](https://github.com/Kronuz/located-exception) [![CI](https://github.com/Kronuz/located-exception/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/located-exception/actions/workflows/ci.yml) |
| [logger](https://github.com/Kronuz/logger) [![CI](https://github.com/Kronuz/logger/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/logger/actions/workflows/ci.yml) | [lru-cache](https://github.com/Kronuz/lru-cache) [![CI](https://github.com/Kronuz/lru-cache/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/lru-cache/actions/workflows/ci.yml) | [math](https://github.com/Kronuz/math) [![CI](https://github.com/Kronuz/math/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/math/actions/workflows/ci.yml) |
| [md5](https://github.com/Kronuz/md5) [![CI](https://github.com/Kronuz/md5/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/md5/actions/workflows/ci.yml) | [metrics](https://github.com/Kronuz/metrics) [![CI](https://github.com/Kronuz/metrics/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/metrics/actions/workflows/ci.yml) | [msgpack](https://github.com/Kronuz/msgpack) [![CI](https://github.com/Kronuz/msgpack/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/msgpack/actions/workflows/ci.yml) |
| [nanosleep](https://github.com/Kronuz/nanosleep) [![CI](https://github.com/Kronuz/nanosleep/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/nanosleep/actions/workflows/ci.yml) | [prism](https://github.com/Kronuz/prism) [![CI](https://github.com/Kronuz/prism/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/prism/actions/workflows/ci.yml) | [queue](https://github.com/Kronuz/queue) [![CI](https://github.com/Kronuz/queue/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/queue/actions/workflows/ci.yml) |
| [radix-router](https://github.com/Kronuz/radix-router) [![CI](https://github.com/Kronuz/radix-router/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/radix-router/actions/workflows/ci.yml) | [random](https://github.com/Kronuz/random) [![CI](https://github.com/Kronuz/random/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/random/actions/workflows/ci.yml) | [reactor](https://github.com/Kronuz/reactor) [![CI](https://github.com/Kronuz/reactor/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/reactor/actions/workflows/ci.yml) |
| [repr](https://github.com/Kronuz/repr) [![CI](https://github.com/Kronuz/repr/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/repr/actions/workflows/ci.yml) | [residency](https://github.com/Kronuz/residency) [![CI](https://github.com/Kronuz/residency/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/residency/actions/workflows/ci.yml) | [scheduler](https://github.com/Kronuz/scheduler) [![CI](https://github.com/Kronuz/scheduler/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/scheduler/actions/workflows/ci.yml) |
| [sha256](https://github.com/Kronuz/sha256) [![CI](https://github.com/Kronuz/sha256/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/sha256/actions/workflows/ci.yml) | [snowball](https://github.com/Kronuz/snowball) [![CI](https://github.com/Kronuz/snowball/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/snowball/actions/workflows/ci.yml) | [soundex](https://github.com/Kronuz/soundex) [![CI](https://github.com/Kronuz/soundex/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/soundex/actions/workflows/ci.yml) |
| [split](https://github.com/Kronuz/split) [![CI](https://github.com/Kronuz/split/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/split/actions/workflows/ci.yml) | [stash](https://github.com/Kronuz/stash) [![CI](https://github.com/Kronuz/stash/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/stash/actions/workflows/ci.yml) | [static-string](https://github.com/Kronuz/static-string) [![CI](https://github.com/Kronuz/static-string/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/static-string/actions/workflows/ci.yml) |
| [storage](https://github.com/Kronuz/storage) [![CI](https://github.com/Kronuz/storage/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/storage/actions/workflows/ci.yml) | [strict-stox](https://github.com/Kronuz/strict-stox) [![CI](https://github.com/Kronuz/strict-stox/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/strict-stox/actions/workflows/ci.yml) | [string-similarity](https://github.com/Kronuz/string-similarity) [![CI](https://github.com/Kronuz/string-similarity/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/string-similarity/actions/workflows/ci.yml) |
| [stringified](https://github.com/Kronuz/stringified) [![CI](https://github.com/Kronuz/stringified/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/stringified/actions/workflows/ci.yml) | [strings](https://github.com/Kronuz/strings) [![CI](https://github.com/Kronuz/strings/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/strings/actions/workflows/ci.yml) | [system](https://github.com/Kronuz/system) [![CI](https://github.com/Kronuz/system/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/system/actions/workflows/ci.yml) |
| [task](https://github.com/Kronuz/task) [![CI](https://github.com/Kronuz/task/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/task/actions/workflows/ci.yml) | [term-color](https://github.com/Kronuz/term-color) [![CI](https://github.com/Kronuz/term-color/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/term-color/actions/workflows/ci.yml) | [termdict](https://github.com/Kronuz/termdict) [![CI](https://github.com/Kronuz/termdict/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/termdict/actions/workflows/ci.yml) |
| [threadpool](https://github.com/Kronuz/threadpool) [![CI](https://github.com/Kronuz/threadpool/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/threadpool/actions/workflows/ci.yml) | [time-point](https://github.com/Kronuz/time-point) [![CI](https://github.com/Kronuz/time-point/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/time-point/actions/workflows/ci.yml) | [times](https://github.com/Kronuz/times) [![CI](https://github.com/Kronuz/times/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/times/actions/workflows/ci.yml) |
| [traceback](https://github.com/Kronuz/traceback) [![CI](https://github.com/Kronuz/traceback/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/traceback/actions/workflows/ci.yml) | [uinteger_t](https://github.com/Kronuz/uinteger_t) [![CI](https://github.com/Kronuz/uinteger_t/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/uinteger_t/actions/workflows/ci.yml) | [unicode](https://github.com/Kronuz/unicode) [![CI](https://github.com/Kronuz/unicode/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/unicode/actions/workflows/ci.yml) |
| [url-parser](https://github.com/Kronuz/url-parser) [![CI](https://github.com/Kronuz/url-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/url-parser/actions/workflows/ci.yml) | [utype](https://github.com/Kronuz/utype) [![CI](https://github.com/Kronuz/utype/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/utype/actions/workflows/ci.yml) | [varint](https://github.com/Kronuz/varint) [![CI](https://github.com/Kronuz/varint/actions/workflows/ci.yml/badge.svg)](https://github.com/Kronuz/varint/actions/workflows/ci.yml) |

## What's here

**Foundations: bytes, strings, parsing.** `char-classify`, `static-string`, `strings`,
`split`, `repr`, `escape`, `stringified`, `strict-stox`, `utype`, `math`, `endian`,
`iterators`, `lazy`

**Compile time, hashing, identifiers, containers.** `constexpr-phf`, `ctrie`, `fst`, `termdict`, `hashes`,
`enum-reflection`, `uinteger_t`, `base-x`, `cuuid`, `md5`, `sha256`, `random`,
`bloom-filter`, `fusefilter`, `lru-cache`, `generation-cache`, `cpp-btree`

**Concurrency, time, and the operating system.** `task`, `threadpool`, `queue`, `stash`,
`scheduler`, `atomic-shared-ptr`, `allocators`, `nanosleep`, `epoch`, `time-point`,
`times`, `datetime`, `residency`, `io`, `fs`, `completion`

**Networking, serialization, storage.** `reactor`, `server`, `http`, `http-parser`,
`http-log`, `radix-router`, `url-parser`, `compressors`, `varint`, `bitpack`, `docset`, `bkd`, `flume`, `storage`,
`msgpack`, `journal`, `consensus`, `cluster`, `prism`

**Domain: geospatial, text, diagnostics.** `cartesian`, `htm`, `double-metaphone`,
`soundex`, `string-similarity`, `unicode`, `snowball`, `analysis`, `boolean-parser`, `logger`, `term-color`, `traceback`,
`located-exception`, `errno-names`, `system`, `metrics`

Dependencies run one way and stay shallow: forty-four of the eighty pull nothing
first-party at all. The service stack is the deepest chain,
`reactor -> http-parser -> http -> http-log -> prism`, and
[prism](https://github.com/Kronuz/prism) is the worked example of the whole thing
assembled into a running HTTP server.

## Full reference

[**AGENTS.md**](AGENTS.md) carries the detail: every library with its include line, CMake
target, dependencies, internal design, key API, a working example, and the cases where it
is the wrong tool. It also holds the rules for modifying one of these libraries, which
matter because several applications depend on them and most of those applications are not
in front of you.

It is written for coding agents, but it is the same reference a person wants.

## Background

The design notes behind each library are being written up as the *Familiars* series on
[kronuz.github.io](https://kronuz.github.io/blog/), still in draft, alongside the story of
the search engine they all came out of.
