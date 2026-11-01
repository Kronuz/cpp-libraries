# Survey D: codes / filters / containers

- Date: 2026-10-30. Kind: cluster survey of the October 2026 performance and correctness work (read-only, before any change).
- Repos: the default-branch heads on 2026-10-30: `queue:7df74b2`, `bloom-filter:0410185`, `generation-cache:00762bd`,
  `flat-map:a9a52b0`, `btree:25f9494`, `metrics:645d729`, `lru-cache:7dd23eb`, `varint:d9631ab`, `ctrie:4b6eb1b`,
  `constexpr-phf:dd7a9ff`.
- Machines: Apple M4 Pro. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| D-W1 queue: notify only when a waiter exists, drop the 1 s poll | landed | `queue:b1b38b0`, `queue:44211ce` | `queue_concurrent`, `queue_liveness` |
| D-W2 bloom-filter: one hash pass instead of xxh64 plus FNV-1a | landed | `bloom-filter:c32355b`, `bloom-filter:08f5e15` | `bloom_filter` |
| D-W3 generation-cache: hash table instead of `std::map`, shared reads | landed | `generation-cache:715f2af`, `generation-cache:32a2b4a` | `generation_cache_differential`, `generation_cache_lock` |
| D-M1 flat_map: memmove insert for trivially copyable halves | landed | `flat-map:85520ce`, `flat-map:ce9aa85` | `flat_map_search_insert`, `flat_map_strategy` |
| D-M2 flat_map: branchless lower bound for integer keys | landed | `flat-map:85520ce`, `flat-map:ce9aa85` | `flat_map_search_insert`, `flat_map_strategy` |
| D-M3 btree: string-key random insert 0.55x of absl | landed | `btree:d81f2a3`, `btree:a56261d` | `key_relocation` |
| D-M4 metrics: `fetch_add` fast path for `AtomicCounter` | landed | `metrics:4890fc0` | `metrics_model`, `metrics_differential` |
| D-M5 metrics: histogram bucket by counting | landed | `metrics:aa7a3d8` | `metrics_differential` |
| D-M6 metrics: striped `AtomicDurationHistogram` | not pursued | - | - (layout and ABI change, recorded in [LESSONS](../LESSONS.md#metrics)) |
| D-M7 lru-cache: single-hash `emplace` | not pursued | - | - (lru-cache `main` has no commit after 2026-10-29) |

D-W2 shipped as the opt-in `FastBloomFilter<N>` and `BlockedBloomFilter<N>`; `BloomFilter<N>` keeps its bits, as the
hazard below requires. D-M4 landed first as a plain `fetch_add` (`metrics:aa7a3d8`), which wrapped under concurrent
large adds (review D CR2, audit CA2); `metrics:4890fc0` made `AtomicCounter` the CAS loop again and moved the fast
path into the opt-in two-word `ContendedCounter`. D-M3 was a correctness fix as well: the slots copied their const
keys on every relocation. The follow-ups are in [the post-landing review](2026-10-31-review-d-containers.md) and
[the containers audit](2026-10-31-audit-containers.md), which also traces the lru-cache hit-count mismatch below to
lru-cache's documented `capacity + 1` overshoot.

Host: Apple M4 Pro, Apple clang 17, `-O3 -DNDEBUG`, all timings under an exclusive timing hold, best of 5-7 runs.
Benchmarks: a survey harness per library (prototype not kept). The repo benches that now cover the rows are
`bloom-filter:bench/bloom_bench.cc` (boost::bloom), `flat-map:bench/bench.cc`, `btree:benchmarks/string_insert_bench.cc`
(absl::btree_map), `generation-cache:bench/bench.cc` (absl::flat_hash_map), `metrics:bench/counter_bench.cc`,
`varint:bench/bench.cc` and `constexpr-phf:bench/compare.cc` (`phf_compare`, also for ctrie); lru-cache has no bench.
queue and constexpr-phf use the benches already in their repos (`queue:benchmark/bench.cc`,
`constexpr-phf:bench/{compare,bench}.cc`).
Ratio = comparator time / ours: **>1 means ours is faster, <1 means ours is slower.** "A/A" = ours timed twice in the same run (max/min of the two bests). Every comparator was checked for identical results on the benchmark inputs before timing (lru: see hazard note; bloom: no false negatives, FP rates listed, because a different bloom has different false positives by design).

## Table

| library | workload | ours | best comparator | ratio (A/A) | diagnosis | est. win | effort | verdict | outcome |
|---|---|---|---|---|---|---|---|---|---|
| **queue** | blocking MPMC int push/pop 1x1 / 2x2 / 4x4 / 8x8 (Mitems/s; best of 3, no A/A in the bench) | 12.99 / 4.72 / 6.40 / 9.41 | plain mutex+condvar+deque 41.29 / 14.99 / 17.43 / 20.93 (moodycamel Blocking 10.4 / 7.6 / 5.7 / 4.9) | 0.31x / 0.31x / 0.37x / 0.45x | The library is 2.2-3.2x slower than a 30-line naive queue. Every successful `pop` calls `_push_cond.notify_one()` (default `_threshold` is size_t(-1), so always true) even when nobody can be waiting on an unbounded queue; every push notifies `_pop_cond`. The default timeout (-1) loops `wait_for(lk, 1s, pred)`, which reads the steady clock on every call even when the predicate already holds. Extra `shared_ptr` indirection and an atomic `_cnt` under the lock. | 2-3x | M | **CLEAR WIN** | D-W1 |
| **bloom-filter** | contains(miss), N=131072, 16-byte keys | 24.7 ns | boost::bloom::filter<u64,20> 8.0 ns (prehashed key) / own blocked k=12 12.8 ns | 0.32x (1.06) | Two full hash passes per key: xxh64 plus a byte-at-a-time FNV-1a (a dependent multiply chain, ~0.7 ns/byte), then 20 independent probes in a 512 KB bitset. | 2.5-3x short keys | S | **CLEAR WIN** | D-W2 |
| | contains(miss), N=131072, 64-byte keys | 63.7 ns | boost 8.4 ns | 0.13x (1.01) | FNV-1a dominates: 64 bytes is ~45 ns of the 54 ns add. | 7x long keys | S | CLEAR WIN | D-W2 |
| | add, N=8192 (32 KB, L1) 16 B | 15.2 ns | boost 5.9 ns | 0.39x (1.01) | same | 2.5x | S | CLEAR WIN | D-W2 |
| **generation-cache** | `get` hit, string keys, 1 thread, n=100000 | 93 ns | mutex + absl::flat_hash_map 32 ns / shared_mutex + absl 35 ns | 0.35x (1.01) | `std::map<Key,Value>`: O(log n) string compares, one cache miss per tree level. n=64: 53 vs 29 ns (0.54x); n=4096: 77 vs 27 (0.35x). | 2-3x single thread | S | **CLEAR WIN** | D-W3 |
| | `get` hit, 4 threads, n=100000 | 1535 ns/op | shared_mutex + absl map 268 / mutex + absl 557 | 0.17x (1.02) | the same, plus exclusive `std::mutex` for readers; the tree walk executes inside the critical section so contention scales with the walk. n=4096 0.32x. | 3-6x multi-thread | S-M | CLEAR WIN | D-W3 |
| **flat_map** | random insert u64, n=4096 / 65536 | 286 / 5229 ns | boost flat_map 167 / 3596 ns | 0.58x / 0.69x (1.01) | `vector<pair<K,V>>::insert` with `std::pair` is not trivially copyable, so the shift is an element-wise move loop, not a memmove (boost memmoves). It is the O(n) shifting that remains; std::map is 53-110 ns (inherent to flat arrays). | 1.5x insert-heavy | S | maybe (only for insert-heavy use; use `builder` for bulk, which already exists) | D-M1 |
| | find u64 | n=256: 6.0, 4096: 9.5-9.7, 65536: 33.7-35.8 ns | branchless lower_bound 3.6 / 5.1 / 22.6; boost 6.3 / 9.9 / 36.1 | 0.59x / 0.54x / 0.67x vs branchless (1.00) | `std::lower_bound` with a lambda compare is a branchy loop: mispredicts about half of ~log2 n compares. Equal to boost, 1.7-2.5x faster than std::map. | 1.5-1.9x lookups | S | maybe (clear for large n; keep comparator genericity: branchless only when `Key` is arithmetic and Compare is `std::less`) | D-M2 |
| | string find n=32 | 17.5 ns | boost 16.7 ns | 0.95x | parity | - | - | already good | - |
| **btree** | u64 insert / find / erase / iterate n=1k..1M | 15.5-88.6 ns insert; 8.2-82 find | absl::btree_map 15.1-89.3 insert; 10.7-82 find | 0.97-1.01 insert, 1.00-1.29 find, 1.06-1.44 erase (A/A 1.0-1.4 at n=1000) | at parity or better than abseil (1.8-3x faster than std::map). | none | - | already good | - |
| | **string key** random insert n=200k | 433 ns | absl::btree 240 ns | **0.55x** (1.02-1.06) | Unexplained, not yet profiled. Same for `emplace`, `try_emplace`, `operator[]`; sorted insert 0.78x; string find 0.95x. Suspects: node-split/rebalance moves of non-relocatable `std::string` slots, or node layout/size choice for 32-byte slots. | 1.8x string-key random insert | M | **maybe** (profile first; likely a CLEAR WIN for string-keyed maps) | D-M3 |
| **metrics** | `AtomicCounter::add` 4 / 8 threads contended | 15.1 / 41.3 ns | `fetch_add` 7.4 / 27.0 ns | 0.49x / 0.65x (1.06-1.07) | saturating add implemented as a CAS loop; contended CAS retries. (2 threads: ours 1.40x faster; 1 thread 0.88x.) | 1.5-2x contended | S | maybe | D-M4 |
| | `DurationHistogram::observe` (plain / atomic), 1 thread | 2.29 / 3.10 ns | counting scan + fetch_add 1.85 / 2.00 ns | 0.81x / 0.65x (1.01-1.02) | `std::lower_bound` over 14 bounds, then 4 saturating CAS adds. | 1.2-1.5x | S | maybe (the same change as above) | D-M5 |
| | shared `AtomicDurationHistogram`, 4 threads | 115 ns/obs | - | - | all 15 buckets + count/sum/max share ~3 cache lines: false sharing. A per-thread stripe would be a layout change. | 5x+ | M (ABI/size change) | maybe | D-M6 |
| | `Counter::add` plain | 0.47 ns | `+=` 0.08 | 0.16x | the comparator vectorizes; in real code (non-loop) the saturation is a few ALU ops. Not a real gap. | - | - | not worth it | - |
| **lru-cache** | find_and_renew / miss emplace, skewed keys, cap 1k / 64k / 1M, u64 | 22.0 / 31.0 / 91.7 ns | std::list + unordered_map 25.6 / 42.8 / 89.8 ns | 1.16x / 1.38x / 0.98x (1.01-1.4) | intrusive links in the unordered_map node: already better than the textbook structure. At 1M, bound by hash-node cache misses (an open-addressing table would help). String keys cap 64k: 65.4 vs 70.9 ns (1.08x). `emplace` does `find` then `emplace` (two hashes) and copies the pair. **Note: hit counts differ from the reference by <0.1% at cap 1k and 64k (653353 vs 652900); the rows are directional.** | 10-30% | M | already good (maybe: single-hash emplace) | D-M7 |
| **varint** | LEB128 decode, 1 byte / 1-3 bytes / u32 / u64 | 0.49 / 1.77 / 2.48 / 6.84 ns | protobuf-style 8-byte-load fast path 1.13 / 2.64 / 3.03 / 7.71 | 2.3x / 1.5x / 1.2x / 1.1x (1.02-1.09) | the simple loop already beats the SWAR version on arm64 (`varint:AGENTS.md` records a rejected candidate). | none | - | already good | - |
| | LEB128 encode | 0.25 / 1.57 / 1.41 / 5.07 | clz-count encode 0.47 / 1.60 / 1.60 / 5.51 | 1.9x / 1.0x / 1.1x / 1.1x | already good. | none | - | already good | - |
| | `unserialise_length`, 90% short | 0.92 ns | short-path first | 1.03x | already good. | none | - | already good | - |
| | `serialise_string` returning `std::string` | 4.6 ns | write into buffer 2.3 ns | 0.51x | allocation-free SSO, but a `std::string` per call; the `char*` overloads exist already. API-level, not a library bug. | - | - | not worth it | - |
| **ctrie** | find, 24 words, 50% hit | 1.89 ns | unordered_map 5.09 / absl flat_hash 4.52 | 2.7x / 2.4x (1.03) | compile-time type-trie: already good for small sets. Compile time grows with the set (not measured). | none | - | already good | - |
| **constexpr-phf** | dispatch on fixed sparse int keys, N=6..1000 | 0.47-0.57 ns | unordered_map 1.0-1.8 ns; binary-search switch 1.5-7.9 ns; if-ladder 1.2-129 ns | 2-3.4x vs unordered_map | the library's own bench: division-free multiply-shift, O(1), flat. | none | - | already good | - |

## CLEAR WINs

### 1. queue (`queue:queue.h`)
- Start files: `queue.h` `push_back`/`push_front`/`pop_front`/`pop_back` (~lines 258-345), `_pop_wait`/`_push_wait` (71-123), `QueueState` (hard/soft limit, threshold).
- Biggest change: stop notifying when no one waits. Track waiter counts under the mutex (incremented before `wait`, decremented after) and call `notify_one` only if `waiters > 0`; and drop the `wait_for(…1s…)` polling loop for the no-timeout case in favor of `wait(lk, pred)` (the poll interval exists so a missed wake-up recovers; with waiter counts and `finish()/end()` doing `notify_all` it is unnecessary, but confirm with the concurrent test).
- Target: >= the naive mutex+deque baseline (41 / 15 / 17 / 21 Mitems/s).
- Must stay identical: public API (`push/pop` timeouts: >0 timed, 0 try, <0 block forever; hard/soft limit/threshold semantics; `finish()`, `end()`, `force`); exactly-once delivery (test/concurrent.cc under TSan/ASan).

### 2. bloom-filter (`bloom-filter:bloom_filter.hh`)
- Start file: `bloom_filter.hh` `hash()`.
- Biggest change: derive the second hash from the xxh64 value (e.g. odd constant multiply/rotate-xor of `h1`, or xxh64 with a different seed) instead of a second full byte-wise `fnv1ah64` pass. Next step: compute the 20 probe positions with a cheap multiply sequence (the `% m` is already a mask since m = N*32 is a power of two for the shipped N).
- Must stay identical: API (`add/contains(data,len,salt)`, template N), the no-false-negatives guarantee and the ~1e-6 false-positive rate (verify on 131072 random keys). **Hazard: bit positions change; if any caller persisted the bitset bytes (it is a raw `std::bitset`), old data would no longer match. The class exposes no serialization, but check the users.** `salt` must still change the probe set.
- Do not switch to a blocked filter without noting that the false-positive rate worsens (blocked k=12 measured 419 FP in 131072 vs 0).

### 3. generation-cache (`generation-cache:generation_cache.hh`)
- Start file: `generation_cache.hh` (one `std::map` and one `std::mutex`).
- Biggest change: when `Key` is hashable use a hash map (flat open addressing), with the same generation/clear semantics; fall back to `std::map` otherwise (`if constexpr` on `std::hash<Key>` / a trait). Second step: `shared_mutex` for `get`.
- Must stay identical: API (`get`, `get_with_generation`, `try_insert` rejecting stale generations, `clear` bumping the generation, `size`), a `std::map`-only key type must still compile. **Hazard: no iteration order is exposed, so switching is safe; value types must stay copyable out of the lock.**

## Maybes (ordered by promise)
1. btree string-key random insert is 1.8x slower than absl::btree (u64 is at parity). Profile `emplace_unique_key_args` / node split with std::string slots first.
2. flat_map: branchless lower_bound for arithmetic keys (1.5-1.9x lookup, n>=256); trivially-relocatable shift for insert (1.5x).
3. metrics: `fetch_add` fast path with saturation fix-up for `AtomicCounter` (1.5-2x contended); bucket find by counting; optional striping.
4. lru-cache: single hash on `emplace`.

## LESSONS

The lessons for these libraries are in [LESSONS](../LESSONS.md): [queue](../LESSONS.md#queue),
[bloom-filter](../LESSONS.md#bloom-filter), [generation-cache](../LESSONS.md#generation-cache),
[flat-map](../LESSONS.md#flat-map), [btree](../LESSONS.md#btree), [metrics](../LESSONS.md#metrics). Three of the
survey's points are recorded only here:

- Node/slot layouts tuned for `uint64` (btree) may not carry to non-trivially-relocatable keys (`std::string`); benchmark the key types users really use, not just integers.
- Intrusive-list-in-hash-node LRU beats the textbook `list + unordered_map` (one allocation, no second lookup) and the library already does this; simple scalar LEB128 loops already beat SWAR tricks on arm64: measure before "optimizing".
- Compile-time dispatch structures (ctrie, phf) are already 2-3x faster than runtime hash maps for small fixed sets: leave them alone.

## API-compat hazards
- bloom-filter: changing hash/probe layout changes which bits are set (data persisted by raw bitset becomes invalid); `sizeof(BloomFilter<N>)` is 512 KB for N=131072 (stack hazard).
- generation-cache: Key currently needs only `operator<`; a hash-based path must keep a `std::map` fallback.
- queue: `Queue` copies share `QueueState` via `shared_ptr`; keep that; timeout semantics (`-1` block, `0` try) must survive removing the 1 s poll.
- flat_map: iterators/references invalidate on mutation; the static_assert on nothrow moves limits value types.
- metrics: counter saturation at UINT64_MAX is observable behavior; a `fetch_add` path must still saturate.
- lru-cache: eviction ordering and `DropAction` callbacks are observable; the hit counts differed slightly from a reference LRU at small capacities (<0.1%), which the survey did not explain.
