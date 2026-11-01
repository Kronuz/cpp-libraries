# Cluster J survey: msgpack, reactor, http (and a read of compressors)

- Date: 2026-10-31. Kind: performance survey of the service libraries against same-space comparators, part of the
  October 2026 performance and correctness work (read-only; prototypes in modified copies of the headers).
- Repos: msgpack, reactor, http at `main` on 2026-10-31; compressors read only (head `9f6fab3`). The source records no
  other commit heads.
- Machines: Apple M4 Pro (all rows), Intel Core i9-9980HK (msgpack rows), a shared Linux x86-64 VM (checksums and
  sanitizers only). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| J-W1 msgpack `unserialise` copies the tree it unpacked | landed | `msgpack:ca77ada` | `msgpack_alloc` (killed by the `revert_unserialise` mutant), `msgpack_diff`, `msgpack_lifetime` |
| J-W2 msgpack `hash()` allocates per child and per leaf | landed; a map with a repeated key (or a key that is not a string) takes the filling path, as the hazard below asks | `msgpack:f2f9f78` | `msgpack_alloc` (`revert_hash`), `msgpack_diff` |
| J-W3 msgpack `to_string()` builds a RapidJSON `Document` | landed; the hand-written JSON writer (the next step, M) was not done | `msgpack:987c111` | `msgpack_alloc` (`revert_to_string`), `msgpack_diff` |
| J-W4 http one-byte disconnect watch | landed: the watch reads ahead 4096 bytes and its pending read is the next request's read | `http:9f4c93f` | `readahead` (seven mutants fail it) |
| J-W5 http per-operation timers and split writes (timeouts on) | landed: `drain()` waits on a channel, a reply is sliced across its head and body together; one deadline per phase was not done | `http:9f4c93f` | `readahead`, `timeouts` |
| J-M1 msgpack lazy `Body` per node (visit every node) | owner decision: msgpack CHANGELOG 2026-10-31 "Not done" holds the per-size `Body` freelist for a decision on cross-thread frees and retained memory per thread | - | - |
| J-M2 msgpack first touch fills each map (3 lookups) | owner decision: the same `Body` design and the same pending decision as J-M1 | - | - |
| J-M3 msgpack copy is a deep copy, not copy-on-write | not pursued: the docs now say a copy is a deep copy; the copy itself is unchanged | `msgpack:83e352d` | - |
| J-M4 msgpack building a record (an 8 KB zone chunk per scalar) | not pursued: no commit on msgpack `main` references it | - | - |

The duplicate-key hazard under J-W2 was a bug of its own: the fix round made a repeated key merge as last value wins in
the position of the first (`msgpack:d054ea1`, `msgpack_merge`), stopped `push_back` onto an array of maps from reading freed
memory (`msgpack:c913966`, `msgpack_growth`), and made a fill that throws leave the map as it was (`msgpack:d8fa3e6`,
`msgpack_failed_fill`). The server rows now have a home in http: `http:bench/server_compare.cc` (Asio, `reactor::TcpServer` and
`http` with and without the timeouts, driven by `bench/compare.sh`, `http:5749f41`), and `http:examples/bench_http.cc` takes
`--timeouts`; the before and after numbers on both machines are in http's CHANGELOG (2026-10-31).

Host: Apple M4 Pro, arm64, macOS, Apple clang 17, `-O3 -DNDEBUG`, C++20. Every timing was taken under an exclusive timing hold
(four holds, each under 10 minutes; the third and fourth also built). Sources, corpus generator, prototypes and raw output
were the survey's own harness (msgpack rows: probe not kept; server rows: `http:bench/server_compare.cc`). The libs were not modified; prototypes are copies of the library headers
(prototype not kept). Comparators: vendored msgpack-c 1.3.0 used directly,
msgpack-c cpp_master (7.x), nlohmann::json 3.12, mpack 1.1, RapidJSON (the lib's pin); wrk 4 for the servers.
x86 (Intel Core i9-9980HK, macOS, Apple clang 17, one exclusive hold): msgpack rows for the library and the prototypes
only, below; the comparators and the servers were not run there (no asio or wrk installed).
A shared Linux x86-64 VM was used for checksums and sanitizers only.

## Top findings (ranked)

1. **CLEAR WIN, S: `MsgPack::unserialise` copies the tree it just unpacked.** `MsgPack(object)` deep-copies the unpacked
   tree into a second zone (7 mallocs and 18.9 KB where msgpack-c needs 3 and 10.3 KB). Adopting the unpacker's zone makes
   every document read 1.44-1.52x faster (63 B to 100 KB) and puts it within 2-30% of `unpack` alone; results identical.
2. **CLEAR WIN, S: `MsgPack::hash()` is 20-55 mallocs and 52-146 KB per call** (a `Body` per child, an 8 KB `sbuffer` per
   leaf). Hashing the tree: 8.8x (63 B) and 3.8x (0.5 KB) faster on map roots, 0 allocations, same values (hazard:
   duplicate keys, below).
3. **CLEAR WIN, S: `MsgPack::to_string` builds a RapidJSON `Document` per call** (9-10 mallocs, 68 KB). Driving the
   `Writer` from the tree: 2.7x / 1.43x / 1.37x / 1.38x faster, identical text. nlohmann's `dump` is still 3-4x faster
   than that (a hand-written writer is the next step, M).
4. **CLEAR WIN, M: `http` per-request overhead.** With the timeouts off, `http` answers in 90.7-91.9 us at one connection against
   59.6 us for a minimal Asio server (+52%); the cause is the connection's one-byte disconnect watch (removing it: 61.4 us),
   and a prototype that keeps the watch but reads ahead 4 KB instead of one byte gets 78.0 us. With the timeouts on (the
   production setting) `http` takes 140-144 us and 80 us of CPU per request at one connection, and 45.1 us of CPU and 27.5k req/s
   at 64 connections against Asio's 23.7 us and 43.5k; the read-ahead watch plus a channel for the timer plus one contiguous
   send brings that to 94.8 us / 44.9 us and 28.5 us CPU / 42.8k req/s, with the library's `asio_test`, `coroutine_test` and
   `timeouts_test` passing on the prototype header. `reactor` itself adds nothing (61.1 us vs 62.0 us).
5. **Maybe, large:** the lazy `Body` per node. After `unserialise`, touching a 0.5 KB document through the `MsgPack` API costs
   82-137 mallocs and 5-6x what msgpack-c needs (3 mallocs): 5,070 ns to visit every node against 971 ns (msgpack-c 7) and
   816 ns (mpack). A per-size freelist for the `Body` blocks gives only 1.06-1.24x. The README's "copies share storage
   until one changes" is not what the code does: a copy is a deep copy (100x a `shared_ptr` copy at 0.5 KB), though still 2-6x
   cheaper than `nlohmann::json`'s.

## Results (arm64, ns unless noted; spread is (max-min)/median over 9 reps of >= 25 ms)

Documents (generated by the harness, keys sorted so every library sees the same order): small 63 B, med 502 B (15 keys,
nested maps and arrays: a typical record), large 104 KB (200 records), wide 8.9 KB (1,000 keys). Hold-to-hold drift of the
unchanged `ours` rows between the first and third holds: median 0.981 over 72 rows (0.86 to 1.15). Every row in the raw
output carries a checksum of the decoded content; a script checks them across binaries.

### msgpack

| library | workload (small / med / large / wide) | ours | best comparator | ratio (A/A spread) | diagnosis | win | effort | verdict | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| msgpack | `unserialise` | 299 / 1,047 / 196,784 / 16,741 | msgpack-c 7 `unpack` 164 / 637 / 120,150 / 9,680 (1.3: 155 / 668 / 127,242 / 10,652); mpack `tree_parse` 60 / 275 / 60,121 / 4,918 (borrows the input); nlohmann `from_msgpack` 438 / 2,359 / 490,114 / 115,699 | 1.8x / 1.6x / 1.6x / 1.7x vs msgpack-c 7 (3-5%); 0.68x / 0.44x / 0.40x / 0.14x vs nlohmann | the unpacked tree is deep-copied into a second zone with a new 8 KB chunk | 1.5x | S | **CLEAR WIN** | J-W1 |
| msgpack | `unserialise` + visit every node | 1,109 / 5,070 / 1,082,011 / 127,800 | mpack 130 / 816 / 168,908 / 12,108; msgpack-c 7 193 / 971 / 200,554 / 14,950; nlohmann 477 / 2,680 / 577,782 / 121,356 | 8.5x / 6.2x / 6.4x / 10.6x vs mpack; 2.3x / 1.9x / 1.9x / 1.05x vs nlohmann (3-4%) | `_fill` makes a `shared_ptr<Body>` (about 216 B with its block) per node, two per map entry and an `unordered_map` node: 137 mallocs, 42 KB per med doc (msgpack-c 3, 10 KB); `*it`/`it.value()` hash a key per step | up to 5x | M-L | maybe (design) | J-M1 |
| msgpack | `unserialise` + 3 lookups | 936 / 2,760 / 203,300 / 95,729 | mpack 116 / 395 / 62,894 / 11,108; msgpack-c 7 193 / 692 / 122,264 / 13,014; nlohmann 510 / 2,439 / 494,513 / 116,860 | 8x / 7x / 3.2x / 8.6x vs mpack; 1.8x / 1.1x / 0.41x / 0.82x vs nlohmann | the first touch fills each map on the path: 82 mallocs and 31.7 KB for 3 lookups in a med doc | 3-8x | M-L | maybe (design) | J-M2 |
| msgpack | 3 lookups, already filled | 46 / 65 / 60 / 33 | nlohmann `at` 58 / 92 / 84 / 113; RapidJSON DOM 33 / 57 / 46 / 3,524 | 0.8x / 0.7x / 0.7x / 0.3x | hash lookup, 0 allocations | - | - | already good | - |
| msgpack | `serialise` | 122 / 514 / 99,015 / 11,664 (wide: 32%, void) | nlohmann `to_msgpack` 74 / 399 / 55,843 / 6,755; msgpack-c 7 `pack` 132 / 520 / 94,962 / 8,458 | 1.65x / 1.29x / 1.77x / 1.7x vs nlohmann; 0.92x-1.04x vs msgpack-c (4-11%) | msgpack-c's packer plus an 8 KB `sbuffer` and a copy into the string (2 mallocs, 8.7 KB) | <= 1.15x without a new packer | S | not worth it (a `std::string` pack stream was 0.67-0.89x: slower) | - |
| msgpack | `MsgPack` copy | 115 / 369 / 67,922 / 5,404 | nlohmann copy 239 / 1,279 / 288,833 / 35,164; msgpack-c deep copy 76 / 327 / 67,868 / 5,377 | 0.48x / 0.29x / 0.24x / 0.15x vs nlohmann; 1.5x / 1.13x / 1.0x / 1.0x vs msgpack-c | a deep copy (4 mallocs, 8.5 KB), not copy-on-write; a `shared_ptr` copy is 3.6 ns | 100x if COW | L | maybe (design: `Body::_parent`) | J-M3 |
| msgpack | `to_string()` | 531 / 2,131 / 336,191 / 29,032 | nlohmann `dump` 59 / 360 / 74,455 / 7,660; RapidJSON `Writer` over a prebuilt DOM 251 / 1,497 / 231,719 / 16,607 | 9.0x / 5.9x / 4.5x / 3.8x vs nlohmann; 2.1x / 1.4x / 1.45x / 1.7x vs the Writer | builds a `rapidjson::Document` through the adaptor per call (9 mallocs, 68 KB; `as_document` alone 196 / 608 / 99,412 / 8,240) | 1.4-2.7x, then 3-4x more with a hand writer | S, then M | **CLEAR WIN** | J-W3 |
| msgpack | `hash()` | 459 / 1,511 (map roots; array roots as `serialise`) | `serialise` 122 / 514 | 3.8x / 2.9x | 20 / 55 mallocs and 52 / 146 KB: a `Body` per child, an 8 KB `sbuffer` and a string per leaf | 8.8x / 3.8x | S | **CLEAR WIN** | J-W2 |
| msgpack | update path: `unserialise` + set one field + `serialise` | 810 / 2,550 / 301,089 / 106,645 | nlohmann 546 / 2,866 / 550,986 / 123,694 | 1.5x / 0.89x / 0.55x / 0.86x | fill + the costs above | - | - | follows the rows above | - |
| msgpack | JSON text -> `MsgPack` (round 1) | 487 / 2,317 / 387,513 / 28,247 | RapidJSON `Parse` 354 / 1,664 / 281,869 / 17,912; nlohmann `parse` 408 / 2,470 / 516,149 / 118,926 | 1.4x / 1.4x / 1.4x / 1.6x vs RapidJSON | the adaptor adds about 40% to the parse | - | - | already good | - |
| msgpack | build the 0.5 KB record | 17,999 (initializer list), 8,033 (`operator[]`) | `msgpack::packer` into an sbuffer 491 | 37x / 16x | 790 mallocs and 1.24 MB per document: every scalar is a `MsgPack` with its own 8 KB zone chunk (`MsgPack(42)` 64 ns, 4 mallocs) | 2-5x | M | maybe | J-M4 |

x86 (i9, ns; spreads 4-46%, mostly 5-15%): the prototypes of the next table, same checksums (240 rows, only the
duplicate-key document differs). `unserialise` small / med / large / wide 727 / 2,058 / 344,518 / 42,079 vs 552 / 1,370 / 218,125 / 22,213 with the
adopted zone (1.32x / 1.50x / 1.58x / 1.89x; msgpack-c `unpack` alone 348 / 1,212 / 213,203 / 22,007); `to_string` 805 / 3,184 /
534,970 / 41,252 vs 500 / 2,170 / 318,604 / 26,468 (1.61x / 1.47x / 1.68x / 1.56x); `hash()` 1,642 / 4,754 vs 125 / 795 (13.1x /
6.0x; the 100 KB array root 0.41x, as above); `serialise` with a `std::string` stream 0.46-0.56x (dropped); `copy` 1.00-1.03x.
The fill cost is much larger here: `unserialise` + visit every node is 7.7x / 12.6x / 14.4x / 19x what msgpack-c needs (3,452 /
21,756 / 4,676,969 / 538,048 vs 447 / 1,728 / 324,572 / 28,333), and the per-size freelist for `Body` is worth more: 1.16x / 1.60x /
1.70x / 1.40x on the visit, 1.22x / 1.29x / 1.10x / 1.52x on 3 lookups, 1.18x-1.50x on the update path (spreads up to 17%).

Prototypes on arm64 (same inputs; 240 rows compared, checksums equal except the duplicate-key document):

| change | row (small / med / large / wide) | before | after | ratio |
|---|---|---|---|---|
| adopt the unpack zone | `unserialise` | 299 / 1,047 / 196,784 / 16,741 | 204 / 705 / 129,854 / 11,599 | 1.47x / 1.49x / 1.52x / 1.44x |
| stream to the `Writer` | `to_string` | 531 / 2,131 / 336,191 / 29,032 | 195 / 1,486 / 246,155 / 21,012 | 2.73x / 1.43x / 1.37x / 1.38x |
| hash on the tree, 256-byte stack buffer | `hash()` small / med / large (array root) | 459 / 1,511 / 97,180 | 52 / 403 / 182,121 | 8.8x / 3.8x / 0.53x (array roots must keep the `sbuffer` path) |
| per-size freelist for `Body` | `unserialise` + visit / + 3 lookups / update path, med | 4,769 / 2,530 / 2,533 | 4,033 / 2,042 / 2,217 | 1.18x / 1.24x / 1.14x (137 -> 48 mallocs; 1.4-1.7x on x86): a maybe, with a thread-safety hazard |
| exact-size zone for a copy | `copy` | 115 / 369 / 67,922 | 119 / 376 / 67,672 | 1.0x, dropped |
| `std::string` pack stream | `serialise` | 122 / 514 / 99,015 | 138 / 767 / 148,064 | 0.89x / 0.67x / 0.67x, dropped |

### reactor and http (loopback, wrk, one reactor unless noted)

Servers answering the same 14-byte keep-alive reply: `asio` (plain Asio, an acceptor handing sockets round-robin, the layout
`TcpServer` uses on macOS), `reactor` (`reactor::TcpServer` with the same session body), `http` (`HttpAsioService` and a handler
writing the same body; `httpt` adds the idle/header/request/inactivity timeouts a service sets). "CPU" is the server's `getrusage`
user+system per request. wrk saturates at about 43k req/s on the M4 Pro, so CPU separates the servers there.

| library | workload | ours | best comparator | ratio (A/A spread) | diagnosis | win | effort | verdict | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| reactor | 1 connection, avg latency | 61.1 us (p50 58, p99 112) | Asio 62.0 us (A/A 62.3, then 59.6) | 0.99x (0.5%) | 2 `kevent`, 2 `recv`, 1 `send`, 0.00 mallocs per request, the same as Asio | - | - | already good | - |
| reactor | 64 connections | 24.1 us CPU (42,489 req/s) | Asio 23.9 us (42,850) | 1.01x | wrk-bound | - | - | already good | - |
| reactor | connection per request, 32 connections (round 1) | 43,545 conn/s | Asio 43,245 | 1.01x | 0.11 mallocs, 5 B per connection | - | - | already good | - |
| http (timeouts off) | 1 connection, avg latency | 90.7 us (p50 88, p99 129); first hold 95.4 | Asio 59.6 us | 1.52x (2%) | one-byte watch read per request: 5 `kevent` (Asio 2), 3 `recv` (2), 1 `sendmsg`, a wake-up pipe `write` + `read`, 12 mallocs (1.4 KB) | 31 us | M | **CLEAR WIN** | J-W4 |
| http (timeouts off) | 64 connections | 25.7 us CPU (43,512 req/s) | Asio 23.7 us (43,553) | 1.09x | the latency gap mostly disappears under load | - | - | not worth it | - |
| http (timeouts on) | 1 connection, avg latency | 140.3 us (p50 137, p99 187); first hold 148.6 | Asio 59.6 us | 2.35x | 60 mallocs and 9.2 KB per request, 10 `kevent`, 4 `read` + 5 `write` (wake-up pipe), 2 `sendmsg` (head and body written separately, each with its own timer and `||` of two coroutines) | 80 us | M | **CLEAR WIN** | J-W5 |
| http (timeouts on) | 64 connections | 45.1 us CPU (27,549 req/s); first hold 44.4 (28,222) | Asio 23.7 us (43,553) | 1.9x CPU, 0.63x req/s | same | 1.6x throughput | M | **CLEAR WIN** | J-W5 |
| http | connection per request (round 1) | 44,012 conn/s | Asio 43,245 | 1.02x | 12.5 mallocs and 1.5 KB per connection (Asio 0.0) | - | - | not worth it | - |

http prototypes (a modified copy of `http_asio.h` with compile-time switches, prototype not kept; 4 s runs; one connection unless noted; the baseline row is the
last hold, the other holds' baselines are within 3%):

| variant | timeouts off: latency / CPU / mallocs, `kevent`, `recv` per request | timeouts on: latency / CPU | 64 connections, timeouts on |
|---|---|---|---|
| baseline | 91.9 us / 41.0 us / 12, 5, 3 | 143.8 us / 81.5 us | 45.1 us CPU, 27,549 req/s |
| `done_` timer replaced by an `asio::experimental::channel` | 92.9 us / 39.7 us / 12, 4, 3 | 141.4 us / 80.1 us | - |
| head and body in one `send` (`ONEBUF`) | 92.9 us / 41.0 us / 15, 5, 3 | - | - |
| watch removed (`NOWATCH`; a bound, not a fix) | 61.4 us / 30.9 us / 7, 2, 2 | - | - |
| watch reads ahead 4 KB (`BIGWATCH`; keeps disconnect detection) | 78.0 us / 36.3 us / 9, 4, 2 | 123.9 us / 71.9 us | - |
| read-ahead watch + channel | 77.7 us / 34.8 us / -, -, - | - | - |
| read-ahead watch + channel + `ONEBUF` | 78.1 us / 34.9 us / 11, 3, 2 | 94.8 us / 44.9 us (34 mallocs, 5.0 KB, 6 `kevent`) | 28.5 us CPU, 42,799 req/s |
| watch removed + channel + `ONEBUF` | 61.1 us / 31.3 us / 10, 2, 2 | 79.6 us / 42.0 us | 28.1 us CPU, 43,012 req/s |
| Asio | 59.5 / 59.8 us (A/A) / 28.2 us / 0, 2, 2 | - | 23.7 us CPU, 43,553 req/s |

At 64 connections with the timeouts off, the read-ahead watch variants cost 25.3-25.6 us of CPU against 25.7 us for the baseline: the
change is for latency and for the timeouts-on path, not for saturated throughput. The watch is the whole +31 us when removed
outright; reading ahead keeps the feature and recovers 14 us of it; the timer replacement and the contiguous send matter only
together with the timeouts on (143.8 us to 94.8 us, 81.5 us to 44.9 us of CPU), where the timer race and the second `sendmsg` are
paid per read and per write. What remains of the +18 us at one connection with the watch kept is one more `kevent` per request.
The library's `asio_test`, `coroutine_test` and `timeouts_test` were built against the read-ahead + channel + `ONEBUF` header and all pass.

The syscall counts come from a dyld interposer (not kept), not dtruss/strace: SIP blocks dtruss and the
Linux VM has no strace. `recv` is counted once (the libc wrapper calls `recvfrom`, which the interposer also sees).
`sample` profiles of the server at one connection (not kept): `__recvfrom` 20.4 us and `__sendmsg` 10.9 us per
request against 6.2 and 3.3 us for Asio.

## CLEAR WINs: where to start, what to change, what must stay identical

### 1. `MsgPack::unserialise`

- Start files: `msgpack:msgpack.h`: `MsgPack::unserialise(const char*, size_t, size_t&)` (end of file) and `MsgPack::Body`'s
  constructors (`template <typename T> Body(T&&)`).
- Single biggest change: take the `msgpack::object_handle`'s zone (`std::shared_ptr<zone>(std::move(h.zone()))`) and keep its
  root object, instead of passing `h.get()` to the deep-copying `Body(T&&)`: one new `Body` constructor
  (`Body(adopt_tag, object_handle&&)`; prototype not kept).
- Must stay identical: the bytes of `serialise()`, `off` on return, every exception (same `unpack` call), growth and
  `_capacity` after a mutation, and that a `MsgPack` never points into its input buffer (the unpacker copies strings into the
  zone unless given a reference function): the `special#NN uaf` rows scribble over the input and re-serialise, and ran clean
  under ASan/UBSan on the Linux VM.

### 2. `MsgPack::hash()`

- Start file: `msgpack:msgpack.h` (`hash`).
- Single biggest change: hash the msgpack tree recursively (no `Body` per child) and pack a leaf into a 256-byte stack buffer;
  keep the `sbuffer`/string path for roots and leaves above the buffer and for array roots (the stack-buffer prototype is 0.53x
  on a 100 KB array). `std::hash<std::string_view>` of the same bytes equals `std::hash<std::string>`; the `hash#NN` rows agree.
- Must stay identical: the value (XOR of `hash(key) ^ hash(child)` over a map, `hash(packed bytes)` for every other type).
  **Hazard:** the current code fills the map first, and filling removes duplicate keys from the underlying tree (the last value
  wins, in the first key's position); a map with duplicate keys hashes, and afterwards serialises and copies, differently
  from the raw tree (`special#12`: `hash`, `copy`, `walk` differ). The fast path must detect duplicates (quadratic compare of the
  key hashes up to 64 keys, a set above) and fall back to the filling code.

### 3. `MsgPack::to_string(int indent)`

- Start files: `msgpack:msgpack.h` (`to_string`), `msgpack:xchange/rapidjson.hpp` (`convert` builds a `Document` per array
  element).
- Single biggest change: a recursive `accept(const msgpack::object&, Writer&)` making the calls `Document::Accept` makes
  (`Null/Bool/Uint64/Int64/Double/String/StartArray/EndArray/StartObject/Key/EndObject`), stopping at the first false.
- Must stay identical: the JSON text for every wire type (BIN as a string, EXT and UNDEFINED as null), `NaN`/`Inf` (the Writer
  refuses them and `to_string` returns the partial text: the prototype stops at the same call), the `indent` overload
  (`PrettyWriter`), key order and escaping; keep `as_document()`. 15 special documents (every integer and float width, NaN, Inf,
  -0.0, 5e-324, NUL and control bytes, UTF-8, 70 KB strings, 200 levels of nesting) give identical text.

### 4. http: the one-byte disconnect watch, and per-operation timers and split writes

- Start files: `http:http_asio.h`: `ConnectionInput` (`arm`, `drain`, `watch`, `completed`, `read(buffer, deadline)` with
  `read_completed || expire_read`), the `input->watch(...)` call in `serve_connection_body`, `write_with_progress` and
  `write_before_deadline` (each buffer written separately, each slice racing a timer). `reactor:reactor.h` is not involved.
- Single biggest change: read ahead in the watch (arm it with a 4 KB buffer, not one byte, and hand the bytes to the parser:
  -14 us at one connection; prototype `BIGWATCH`), or arm it only when the handler suspends (removing it: -30 us); write head and body as one gather or contiguous send; give a connection one deadline per
  phase that the completing operation cancels instead of a timer and an `||` of two coroutines per read and per write.
- Must stay identical: the bytes on the wire, `Request::cancel(CancelReason::Disconnect)` on a hang-up, the pipelined-byte rule
  (bytes read by the watch go back to the parser), every timeout's meaning (idle from the reply's end to the first byte, header
  from the first byte, inactivity per 64 KiB slice, request absolute), cancellation of a waiter ends the wait, and the library's
  `asio_test`, `coroutine_test`, `timeouts_test` pass unchanged.

## Compat hazards

- `MsgPack` is header-only and shares its layout with Xapiand's translation units: a new `Body` constructor is additive; any change
  to `Body`'s members changes every consumer's ABI.
- Adopting the zone relies on `object_handle::zone()` being a `unique_ptr` (C++11 and later).
- `serialise<B>()` keeps `B`; an explicit `serialise<msgpack::sbuffer>()` must still compile and return the same bytes.
- `hash()` is the one wrapper function whose result depends on filling (duplicate keys), above.
- A per-size `Body` freelist is thread-hostile unless blocks freed on another thread are returned to a bounded shared pool.
- `http_asio.h` is included by consumers: rebuild them together after any change to `ConnectionInput`.

## LESSONS

The lessons for these libraries are in [msgpack](../LESSONS.md#msgpack) and [http](../LESSONS.md#http). Two from this
survey are not recorded there, and a third whose closing point is not:

- A default scratch size (an 8 KB zone chunk for every scalar, an 8 KB `sbuffer` per `serialise`, a 790-malloc / 1.2 MB initializer
  list for a 0.5 KB record) is paid on every small value; size scratch space to the data or reuse it.
- Count calls, not just time: mallocs, `kevent` and `recv` located a 52% latency gap before any profile, and a combination of
  prototypes was needed to separate the cause (the watch) from the symptoms (timer, `sendmsg`).
- A condition variable made of a timer costs a pipe `write` + `read` and a `kevent` per use in a kqueue reactor when it is the
  earliest timer; a channel does the same with no syscalls. (It did not change latency here: count before attributing a gap.)

## Not benchmarked

- compressors zstd/deflate small-input wrappers: `compressors` was being changed at the time (head `9f6fab3`, a work-in-progress
  commit). Read only:
  `compress_zstd`/`decompress_zstd` already size the output from the frame header and copy once, and `compress_zstd_into` /
  `decompress_zstd_into` reuse per-thread contexts; deflate still calls `deflateInit2`/`inflateInit2` per call (the
  [systems survey](2026-10-30-survey-systems.md): 252 ns vs 53 ns for `uncompress` at 256 B, small in absolute terms).
- `reactor_udp.h`, `reactor_events.h` (`PeriodicTimer::again` posts to the loop and re-arms: protocol timers, not per request),
  `reactor_lag.h`, `reactor_tls.h`.

## Status and reproduction

Checked on the Linux VM (g++ 11.2, no timing): 240 checksum rows equal between the library and the prototypes except the
duplicate-key document; the per-size-freelist prototype equals the other on all 240; with `-fsanitize=address,undefined` the
library and both prototypes ran the whole corpus and the special documents with no report (leak detection off: g++ 11's LSan is
unreliable). The comparator binary agreed with the wrapper on the small and med documents; on the large one nlohmann agreed and
RapidJSON's default parse differed in the last bit of some doubles (`kParseFullPrecisionFlag` is off); that run stopped there, and
the check is now a warning (the Linux VM could not rebuild it: the compiler ran out of memory). Not done: x86 comparators and servers, a profile of the msgpack paths, the hand-written JSON writer.

The msgpack harness and the raw output were not kept (probe not kept). The server rows are re-run with
`http:bench/server_compare.cc` and `http:bench/compare.sh` (`-DHTTP_BUILD_BENCH=ON`).
