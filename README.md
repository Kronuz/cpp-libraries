# Kronuz C++ Libraries

Sixty-four small, standalone C++ libraries, each in its own repository under
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

## What's here

**Foundations: bytes, strings, parsing.** `char-classify`, `static-string`, `strings`,
`split`, `repr`, `escape`, `stringified`, `strict-stox`, `utype`, `math`, `endian`,
`iterators`, `lazy`

**Compile time, hashing, identifiers, containers.** `constexpr-phf`, `ctrie`, `hashes`,
`enum-reflection`, `uinteger_t`, `base-x`, `cuuid`, `md5`, `sha256`, `random`,
`bloom-filter`, `lru-cache`, `cpp-btree`

**Concurrency, time, and the operating system.** `threadpool`, `queue`, `stash`,
`scheduler`, `atomic-shared-ptr`, `allocators`, `nanosleep`, `epoch`, `time-point`,
`times`, `datetime`, `io`, `fs`

**Networking, serialization, storage.** `reactor`, `server`, `http`, `http-parser`,
`http-log`, `radix-router`, `url-parser`, `compressors`, `flume`, `storage`, `msgpack`,
`cluster`, `prism`

**Domain: geospatial, text, diagnostics.** `cartesian`, `htm`, `double-metaphone`,
`soundex`, `string-similarity`, `boolean-parser`, `logger`, `term-color`, `traceback`,
`located-exception`, `errno-names`, `system`

Dependencies run one way and stay shallow: thirty-one of the sixty-four pull nothing
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
