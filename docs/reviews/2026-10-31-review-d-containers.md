# Review D: cluster D performance commits (post-landing)

- Date: 2026-10-31. Kind: post-landing review of the cluster D performance commits of the October 2026 work (read-only).
- Repos: `queue:b1b38b0`, `metrics:aa7a3d8`, `btree:0d40c97` (head of a non-default `main` branch, never on
  `master`), `generation-cache:715f2af`, `bloom-filter:c32355b`, `flat-map:85520ce`.
- Machines: Apple M4 Pro, a shared Linux x86-64 VM. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| CR1 generation-cache: failed insert leaves a poisoned slot | closed | `generation-cache:89baa5b` | `generation_cache_differential` (throwing-key case) |
| CR2 metrics: saturation not monotonic for readers | closed | `metrics:4890fc0` | `metrics_model`, `metrics_differential` |
| CR3 btree: `const_cast` key moves are formally UB | closed | `btree:d81f2a3`, `btree:a56261d` | `key_relocation` |
| CR4 generation-cache: `shared_mutex` can starve writers; adversarial keys | closed | `generation-cache:32a2b4a` | `generation_cache_lock` (starvation cases) |
| CR5 bloom-filter: Blocked FP rate ~3 orders worse | no change | - | - (documented in the README, ~1.3e-3) |
| CR6 flat-map: memmove insert on `std::pair` | not a defect | `flat-map:ce9aa85` | `flat_map_strategy` |

CR2's first fix (`metrics:9207dd3`) narrowed the race and did not close it ([containers audit](2026-10-31-audit-containers.md)
CA2); `4890fc0` restored the CAS loop. CR3's `const_cast` version never reached `master`: the slots there are a live
union of `std::pair<Key, T>` and `std::pair<const Key, T>`, and `key_relocation` fails on the copying header before it.
CR4's adversarial-key part stays as documented (no change); `generation-cache:49a86e9` removed the README's claim
that keys cannot be crafted to collide. CR6 was decided in the containers audit ("Memmove decision"): `memmove`
creates the implicit-lifetime pairs; `ce9aa85` gates the shift on exactly that rule and excludes `volatile`. The
verdict "Queue is sound" did not hold: the containers audit found four lost-wake-up classes (CA1 there), closed in
`queue:e94be7d`.

Reviewed on origin main: queue b1b38b0, metrics aa7a3d8, btree 0d40c97, generation-cache 715f2af,
bloom-filter c32355b, flat-map 85520ce.
Environment: Apple M4 Pro (clang, under a light hold) and a shared Linux x86-64 VM (clang++, ASan+UBSan, TSan with `setarch -R`).

## Verdict: APPROVE WITH CONDITIONS

Two real defects (CR1, CR2) need fixes. Queue is sound. btree has a formal-UB note with a correct alternative (CR3).

## Blocking (conditions of approval)

**CR1 generation-cache: failed insert leaves a poisoned slot (`generation_cache.hh:110-111`).**
`s.h = h` is stored before `s.kv.emplace(key, std::move(value))`. If the Key copy throws (bad_alloc on a
string key), the slot keeps `h != 0` with a disengaged `optional`; `size_` is not incremented. A later
`find`/`insert_or_assign` with the same hash dereferences `s.kv->first` on an empty optional (UB).
Probe `gencache_probe.cc` (probe not kept; covered by `generation_cache_exception_safety`): after a throwing insert,
`size()==1` but `get(2)` returns FOUND (garbage), no sanitizer
report (reads stale storage). The old `std::map` path was strong-exception safe. Fix: emplace first, then set
`s.h = h` and `++size_` (or construct the pair before touching the slot). Add a throwing-copy test to
`test/differential.cc`.

**CR2 metrics: saturation is no longer monotonic for readers (`metrics.hh:45-52`).**
The comment claims a reader sees the wrapped value only after "2^64 accumulated units". One `add(UINT64_MAX)`
(e.g. a negative duration cast to u64 into `sum_ns`) pins the counter, and then every further `add` wraps and
re-pins. Probe `metrics_saturation_probe.cc` (probe not kept; covered by `metrics_differential` and `metrics_model`)
(4 writers `add(1)` on a pinned counter): a reader saw a value
below max in **75% of samples** (lowest 0), on macOS and on Linux/TSan. Final value is correct (max), single-
thread edges match the CAS version, so the differential test did not catch it. Snapshots/rates can show `sum_ns`
near 0. Fix options: (a) restore the CAS loop; (b) keep the fast path only when `load < 2^63 && amount < 2^32`
(a thread count below 2^31 then cannot wrap, so no repair store is needed) and use the CAS loop otherwise.
At minimum correct the false comment/README claim; add the pinned-counter reader probe to `test/differential.cc`.

## Non-blocking

**CR3 btree: `const_cast` key moves are formally UB (`btree.h:355`, `:2928`; `:341` pre-existing).**
`first` of `pair<const Key,T>` is a const object created by placement-new; moving from it modifies a const object
([dcl.type.cv]). No compiler miscompiles it today (slots are raw heap bytes; ASan/UBSan probe
`btree_probe.cc` (probe not kept; covered by `key_relocation` and `ownership_move`) with string keys vs std::map,
unique_ptr mapped and a throwing-move key: ok), but it is a latent
hazard under LTO/devirtualized value-propagation of const members. Correct alternative: store slots as
`std::pair<Key,T>` (mutable_value_type, the abseil approach) and expose `value_type&` through the existing
`reinterpret_cast`/`std::launder` accessors (`btree.h:708-711`); relocation then moves `.first` legitimately.
Alternatively, end the lifetime and rebuild by copy only when not nothrow-movable (the previous behavior). An
architecture decision, since it changes slot type across the node layout.
The `kMovesParts` fallback for throwing moves works (probe ok). The shifted-slot move in `emplace_nonfull` relies on
`eligible` (nothrow moves); correct.

**CR4 generation-cache: reader-preferring `shared_mutex` can starve `try_insert`/`clear`** under saturating readers
(glibc default). Not hit by the probe (2000 clears completed with 4 readers), but unbounded in theory. Also an
unrandomized `std::hash` with linear probing at load 0.5 degrades to O(n) under adversarial keys (same as
unordered_map; the mix is a fixed function). `grow()` also runs when overwriting an existing key (harmless).

**CR5 bloom-filter: Blocked FP rate is ~3 orders worse.** Measured (4M absent keys, N=131072 keys): legacy 2.5e-7,
Fast 0, Blocked 1.5e-3 (65536 keys: 5.4e-4; 200000: 3.8e-3). README already says ~1.3e-3; OK as documented.
Fast tracks legacy at all loads; no false negatives anywhere (`bloom_probe.cc`, probe not kept; covered by
`bloom_filter`). `unsigned __int128` makes the
header GCC/clang-only; `const_cast` in `BlockedBloomFilter::add` (`bloom_filter.hh:174`) is on a non-const member
and is legal. Salt is only used for `d`, not the block, so different salts share a block (fine).

**CR6 flat-map: memmove insert on `std::pair` (`flat_map.hh:249`)** is technically not valid for a non-trivially-
copyable `pair` even when both halves are; works on all tested ABIs. Branchless search is correct: `flatmap_probe.cc`
(probe not kept; covered by `flat_map_search_insert`)
vs std::map (int/unsigned/int8/uint8/int64/uint64, mixed-width queries, sizes 0..3000) ok under ASan+UBSan.

## Queue (the main risk): no finding

- Lost wake-up: every waiter increments the count and blocks under the same mutex; notifiers read the count under
  the mutex; `_wake_all` lock/unlock (`queue.h:216`) orders the flag store before any in-flight waiter. Stale-count
  cases (notified-but-not-yet-awake waiter, stolen item, timed-out waiter) leave no item stranded.
- Mutants killed by `queue_wake_stress.cc` (probe not kept; covered by `queue_liveness` and `queue_concurrent`)
  (shutdown race with parked pushers/poppers, exactly-once with
  mixed timed/untimed poppers; watchdog reports HANG): M1 (`_wake_all` without the lock) hangs;
  M2 (untimed pop path does not count its waiter) hangs, but only in `untimed` mode: with a mix of timed
  poppers the 5 s timeout masks it, so the repo's own concurrent test would not catch M2 (note for test authors).
- Real code: probe and repo `concurrent.cc` pass under ASan and TSan (Linux), 500 iterations each, plus the M4 Pro at -O1.
- Close semantics: end/finish/destructor wake both condvars; behavior unchanged. Minor: an exception from
  `wait` would leave the waiter count incremented (`queue.h` ++/-- are not RAII); not reachable in practice.

## Probes

`queue_wake_stress.cc` (probe not kept; covered by `queue_liveness` and `queue_concurrent`), the mutant headers
`mutant_queue_M1_nolock.h` and `mutant_queue_M2_nowaitercount.h` (now the `wake-all-no-lock` and
`untimed-consumer-uncounted` edits of `queue:tools/mutants.py`), `metrics_saturation_probe.cc` (probe not kept; covered by
`metrics_differential` and `metrics_model`), `gencache_probe.cc` (probe not kept; covered by
`generation_cache_exception_safety`), `flatmap_probe.cc` (probe not kept; covered by `flat_map_search_insert`),
`btree_probe.cc` (probe not kept; covered by `key_relocation` and `ownership_move`), `bloom_probe.cc` (probe not kept;
covered by `bloom_filter`).

Not run: repo-native ctest suites for btree/flat-map/bloom/gencache (probes only), benchmarks (barred), MSVC/GCC
builds, Windows, libc++ vs libstdc++ matrix for shared_mutex fairness, TSan on btree/gencache (single-thread btree;
gencache probe ran under ASan+UBSan only, TSan not run on it), local macOS ASan (hung at startup in the sandbox).
