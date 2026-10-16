# Kronuz C++ Libraries

About eighty small, standalone C++ libraries, each in its own repository under
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
the tip; pin a SHA when you need reproducibility. Everything is MIT licensed except
`cpp-btree` (Apache 2.0) and `static-string` (Boost 1.0). Some repos bundle third-party code under its own license:
`msgpack` (Boost 1.0 for msgpack-c), `snowball` (BSD 3-clause for the generated
stemmers), and `unicode` (the Unicode License for its tables).

The include filename often differs from the repo name: `char-classify` gives `chars.hh`,
`constexpr-phf` gives `phf.hh`, `enum-reflection` gives `enum.h`. [AGENTS.md](AGENTS.md)
lists the real include line for every one.

## Build status

Every library in the table below builds and runs its tests on Linux (x86_64 with GCC and Clang, arm64),
macOS (arm64, x86_64), and FreeBSD, plus an ASan and UBSan build, through the shared
workflow in [`.github/workflows/cmake.yml`](.github/workflows/cmake.yml).

Assertions stay live in every build, the standard library's own checks are on, a
ThreadSanitizer job runs alongside ASan and UBSan, and every repository runs nightly.
[`tools/preflight.sh`](tools/preflight.sh) runs the same matrix locally, on macOS and on
Linux and FreeBSD VMs, before a push.

<table>
<tr>
<td><a href="https://github.com/Kronuz/allocators/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/allocators/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/allocators">allocators</a></td>
<td><a href="https://github.com/Kronuz/analysis/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/analysis/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/analysis">analysis</a></td>
<td><a href="https://github.com/Kronuz/atomic-shared-ptr/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/atomic-shared-ptr/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/atomic-shared-ptr">atomic-shared-ptr</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/base-x/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/base-x/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/base-x">base-x</a></td>
<td><a href="https://github.com/Kronuz/bitpack/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/bitpack/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/bitpack">bitpack</a></td>
<td><a href="https://github.com/Kronuz/bkd/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/bkd/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/bkd">bkd</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/bloom-filter/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/bloom-filter/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/bloom-filter">bloom-filter</a></td>
<td><a href="https://github.com/Kronuz/boolean-parser/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/boolean-parser/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/boolean-parser">boolean-parser</a></td>
<td><a href="https://github.com/Kronuz/cartesian/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/cartesian/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/cartesian">cartesian</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/char-classify/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/char-classify/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/char-classify">char-classify</a></td>
<td><a href="https://github.com/Kronuz/cluster/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/cluster/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/cluster">cluster</a></td>
<td><a href="https://github.com/Kronuz/completion/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/completion/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/completion">completion</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/compressors/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/compressors/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/compressors">compressors</a></td>
<td><a href="https://github.com/Kronuz/consensus/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/consensus/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/consensus">consensus</a></td>
<td><a href="https://github.com/Kronuz/constexpr-phf/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/constexpr-phf/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/constexpr-phf">constexpr-phf</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/ctrie/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/ctrie/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/ctrie">ctrie</a></td>
<td><a href="https://github.com/Kronuz/cuuid/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/cuuid/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/cuuid">cuuid</a></td>
<td><a href="https://github.com/Kronuz/datetime/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/datetime/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/datetime">datetime</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/docset/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/docset/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/docset">docset</a></td>
<td><a href="https://github.com/Kronuz/double-metaphone/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/double-metaphone/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/double-metaphone">double-metaphone</a></td>
<td><a href="https://github.com/Kronuz/endian/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/endian/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/endian">endian</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/enum-reflection/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/enum-reflection/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/enum-reflection">enum-reflection</a></td>
<td><a href="https://github.com/Kronuz/epoch/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/epoch/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/epoch">epoch</a></td>
<td><a href="https://github.com/Kronuz/errno-names/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/errno-names/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/errno-names">errno-names</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/escape/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/escape/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/escape">escape</a></td>
<td><a href="https://github.com/Kronuz/flume/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/flume/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/flume">flume</a></td>
<td><a href="https://github.com/Kronuz/fs/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/fs/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/fs">fs</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/fst/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/fst/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/fst">fst</a></td>
<td><a href="https://github.com/Kronuz/fusefilter/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/fusefilter/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/fusefilter">fusefilter</a></td>
<td><a href="https://github.com/Kronuz/hashes/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/hashes/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/hashes">hashes</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/htm/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/htm/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/htm">htm</a></td>
<td><a href="https://github.com/Kronuz/http/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/http/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/http">http</a></td>
<td><a href="https://github.com/Kronuz/http-log/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/http-log/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/http-log">http-log</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/http-parser/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/http-parser/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/http-parser">http-parser</a></td>
<td><a href="https://github.com/Kronuz/io/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/io/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/io">io</a></td>
<td><a href="https://github.com/Kronuz/iterators/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/iterators/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/iterators">iterators</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/journal/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/journal/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/journal">journal</a></td>
<td><a href="https://github.com/Kronuz/lazy/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/lazy/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/lazy">lazy</a></td>
<td><a href="https://github.com/Kronuz/located-exception/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/located-exception/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/located-exception">located-exception</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/logger/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/logger/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/logger">logger</a></td>
<td><a href="https://github.com/Kronuz/lru-cache/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/lru-cache/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/lru-cache">lru-cache</a></td>
<td><a href="https://github.com/Kronuz/math/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/math/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/math">math</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/md5/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/md5/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/md5">md5</a></td>
<td><a href="https://github.com/Kronuz/metrics/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/metrics/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/metrics">metrics</a></td>
<td><a href="https://github.com/Kronuz/msgpack/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/msgpack/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/msgpack">msgpack</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/nanosleep/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/nanosleep/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/nanosleep">nanosleep</a></td>
<td><a href="https://github.com/Kronuz/prism/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/prism/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/prism">prism</a></td>
<td><a href="https://github.com/Kronuz/queue/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/queue/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/queue">queue</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/radix-router/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/radix-router/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/radix-router">radix-router</a></td>
<td><a href="https://github.com/Kronuz/random/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/random/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/random">random</a></td>
<td><a href="https://github.com/Kronuz/reactor/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/reactor/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/reactor">reactor</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/repr/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/repr/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/repr">repr</a></td>
<td><a href="https://github.com/Kronuz/residency/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/residency/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/residency">residency</a></td>
<td><a href="https://github.com/Kronuz/scheduler/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/scheduler/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/scheduler">scheduler</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/sha256/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/sha256/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/sha256">sha256</a></td>
<td><a href="https://github.com/Kronuz/snowball/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/snowball/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/snowball">snowball</a></td>
<td><a href="https://github.com/Kronuz/soundex/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/soundex/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/soundex">soundex</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/split/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/split/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/split">split</a></td>
<td><a href="https://github.com/Kronuz/stash/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/stash/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/stash">stash</a></td>
<td><a href="https://github.com/Kronuz/static-string/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/static-string/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/static-string">static-string</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/storage/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/storage/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/storage">storage</a></td>
<td><a href="https://github.com/Kronuz/strict-stox/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/strict-stox/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/strict-stox">strict-stox</a></td>
<td><a href="https://github.com/Kronuz/string-similarity/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/string-similarity/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/string-similarity">string-similarity</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/stringified/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/stringified/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/stringified">stringified</a></td>
<td><a href="https://github.com/Kronuz/strings/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/strings/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/strings">strings</a></td>
<td><a href="https://github.com/Kronuz/system/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/system/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/system">system</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/task/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/task/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/task">task</a></td>
<td><a href="https://github.com/Kronuz/term-color/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/term-color/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/term-color">term-color</a></td>
<td><a href="https://github.com/Kronuz/termdict/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/termdict/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/termdict">termdict</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/threadpool/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/threadpool/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/threadpool">threadpool</a></td>
<td><a href="https://github.com/Kronuz/time-point/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/time-point/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/time-point">time-point</a></td>
<td><a href="https://github.com/Kronuz/times/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/times/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/times">times</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/traceback/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/traceback/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/traceback">traceback</a></td>
<td><a href="https://github.com/Kronuz/uinteger_t/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/uinteger_t/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/uinteger_t">uinteger_t</a></td>
<td><a href="https://github.com/Kronuz/unicode/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/unicode/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/unicode">unicode</a></td>
</tr>
<tr>
<td><a href="https://github.com/Kronuz/url-parser/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/url-parser/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/url-parser">url-parser</a></td>
<td><a href="https://github.com/Kronuz/utype/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/utype/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/utype">utype</a></td>
<td><a href="https://github.com/Kronuz/varint/actions/workflows/ci.yml"><img src="https://github.com/Kronuz/varint/actions/workflows/ci.yml/badge.svg" alt="CI"></a> <a href="https://github.com/Kronuz/varint">varint</a></td>
</tr>
</table>

Three have no CI yet: `cpp-btree` (a script-driven test), `generation-cache`, and
`server` (an early libev prototype that `reactor` and `http` superseded).

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

Dependencies run one way and stay shallow: more than half pull nothing first-party
at all. The service stack is the deepest chain,
`reactor` and `http-parser` under `http`, then `http-log`, then `prism`, and
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
