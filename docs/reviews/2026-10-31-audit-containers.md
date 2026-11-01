# Audit: containers (queue, bloom-filter, generation-cache, flat-map, metrics; lru-cache, varint, ctrie)

- Date: 2026-10-31; re-checks of CA2 and CA1 after the fix round (CA1 on 2026-11-01). Kind: cluster audit of the
  October 2026 performance and correctness work (read-only).
- Repos: `queue:7df74b2..1787904`, `metrics:645d729..bdf4b29`, `generation-cache:00762bd..2930a64`,
  `flat-map:a9a52b0..27e68bb`, `bloom-filter:0410185..c09f715`; unchanged `lru-cache:7dd23eb`, `varint:d9631ab`,
  `ctrie:4b6eb1b`. Re-checks: `metrics:50d8bb8`, `queue:31552f9`.
- Machines: Apple M4 Pro, Intel Core i9-9980HK, Apple M1 Pro (the CA2 re-check), a shared Linux x86-64 VM, GitHub
  Actions runners (CI). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| CA1 queue: four missing notifies hang forever | closed | `queue:e94be7d`, `queue:31552f9` | `queue_liveness`, `queue_liveness_stress` |
| CA2 metrics: `AtomicCounter::add` still wraps | closed | `metrics:4890fc0` | `metrics_model`, `metrics_differential` |
| CA3 generation-cache: rehash exception safety | closed | `generation-cache:2930a64` | `generation_cache_exception_safety` |
| CA4 generation-cache: untargeted rows regressed | closed | `generation-cache:49a86e9`, `generation-cache:32a2b4a`, `generation-cache:e8bb884` | `generation_cache_seed`, `generation_cache_lock`, `generation_cache_first_insert` |
| CA5 flat-map: branchless search loses on x86 | partly closed | `flat-map:ce9aa85` | `flat_map_strategy` (prefetch kernel); the conditional-move hint has no test, and the replayed `<i8,u64>` n=100 find stays slower on the i9 |
| CA6 flat-map: small-n insert regressed on arm | closed | `flat-map:ce9aa85` | `flat_map_strategy` (shift policy per tail length) |
| CA7 bloom-filter: `FastBloomFilter` misses slower on x86 | closed | `bloom-filter:08f5e15` | `bloom_filter` (words read per miss) |
| CA8 bloom-filter: `unsigned __int128` in every includer | closed | `bloom-filter:77dca4c` | `bloom_filter_pedantic`, `bloom_filter_portable` |
| CA9 metrics: "1 and 2 threads were unchanged" is false | closed | `metrics:8c8ad90` | - (documentation) |
| CA10 queue: x86 below the naive baseline at 2+ threads | closed | `queue:44211ce` | - (performance; re-check CA1) |
| CA11 hygiene: local merged branches | closed | - | - (origin has only `main` in all five repos) |
| RC1 catalog still carries the withdrawn `AtomicCounter` claim | closed (docs; the metrics entry describes both counters) | `cpp-libraries:455fae2` | - |
| RC2 two proof steps checked only at 8 bits or one schedule | open | - | - (`metrics` main is still `50d8bb8`, the re-checked head) |

CA9, CA10 and CA11 are documentation, timing and hygiene findings: no test can fail on them, and they count as closed
on the commit (CA9), on the re-check's interleaved timing (CA10) and on the branch lists of origin (CA11). CA5: the
i9 replayed `<i8,u64>` n=100 find is 6.4 ns against 5.0 with `std::lower_bound` (26 vs 6.8 ns on a random stream);
`flat-map`'s CHANGELOG keeps the branchless search for every integer key by choice. `flat-map`'s CHANGELOG also
records a new x86 gap after the CA6 fix: insert into 64 to 256 entries on the i9 is 27 to 43% slower than on
2026-10-30, cause not isolated. The CA1 re-check's three notes outside CA1 (teardown with parked threads, the move
constructor from a moved-from `Queue`, moodycamel on x86 in the README) have no ID; none is addressed on `queue:31552f9`.

Fresh-context audit of the 2026-10-30/31 work against the audit brief ([PERFORMANCE.md](../PERFORMANCE.md)). btree
skipped (being consolidated).

| repo | start | head audited | verdict |
|---|---|---|---|
| queue | 7df74b2 | 1787904 | **NOT YET**: CA1, four lost-wake-up classes hang forever (start recovered in 1 s) |
| metrics | 645d729 | bdf4b29 | **NOT YET**: CA2, saturation wraps (review D CR2 not closed) |
| generation-cache | 00762bd | 2930a64 (pushed 13:30, during the audit) | **BETTER WITH CONDITIONS** (CA3, CA4) |
| flat-map | a9a52b0 | 27e68bb | **BETTER WITH CONDITIONS** (CA5, CA6) |
| bloom-filter | 0410185 | c09f715 | **BETTER WITH CONDITIONS** (CA7, CA8) |
| lru-cache, varint, ctrie | 7dd23eb, d9631ab, 4b6eb1b | unchanged | **UNCHANGED**: no campaign commits, CI green, at the bar per [survey D](2026-10-30-survey-containers.md) |

Hosts: Apple M4 Pro (Apple clang 17, under an exclusive timing hold); Intel Core i9-9980HK (Apple clang 17 timing
under an exclusive hold; gcc 16.2 builds); a shared Linux x86-64 VM (clang 12 TSan, gcc 11 ASan+UBSan, `setarch -R`).
Every timing is start and head built from the same bench source, each run twice; the two values are the A/A spread.
Probes, mutants and logs were not kept; each finding names the repo test or bench that now covers its probe.

## Blocking

**CA1 queue: removing the 1 s poll turned four missing notifies into permanent hangs (introduced).**
The campaign fixed the shutdown race (`_wake_all`) and made untimed waits `wait(lk, pred)`, but four other state changes
that make a parked waiter's predicate true still wake nobody, or the wrong thread. At start each of these recovered
through the 1 s `wait_for` loop. Now the waiter sleeps until some unrelated operation happens to notify it.
Probe `queue_liveness.cc` (probe not kept; covered by `queue_liveness`) (`./a.out all 10 2000`; "stuck" means still blocked after 2 s):

| case | code | head M4 Pro / Linux VM gcc / i9 | start |
|---|---|---|---|
| two `Queue`s sharing one `QueueState` (documented, ARCHITECTURE "Shared state"): push to A, `notify_one` on the shared `_pop_cond` wakes B's popper, which re-blocks | `queue.h:300-307` | 20/20, 5/10, 3/3 stuck | 0 stuck, ~1000 ms |
| `clear()` frees N slots and wakes one parked pusher | `queue.h:365-374`, `:522-531` | 5/5, 6/10, 3/3 | 0, ~1000 ms |
| `QueueSet::erase` frees a slot and wakes nobody | `queue.h:534-545` | 5/5, 6/10, 3/3 | 0, ~1000 ms |
| pop leaves size >= `_threshold` but `_cnt < _hard_limit`: no notify, the pusher waits with room (ARCHITECTURE: "a push blocks while `_cnt >= _hard_limit`") | `queue.h:336`, `:350` | 5/5, 8/10, 3/3 | 0, ~1000 ms |

Linux iterations that pass are ones where the 2 ms park window lost to the loaded VM. None of this is covered:
`test/concurrent.cc` exercises shutdown and one-queue push/pop only. Fix: `clear()` → `notify_all` on `_push_cond`
when `_push_waiters`; `erase` → `notify_one`; shared state → per-`Queue` pop condvar, or `notify_all` when
`_state.use_count() > 1`; threshold → also notify when the pop takes `_cnt` from `_hard_limit` to below it (or
document threshold as strict hysteresis and fix the ARCHITECTURE sentence). Add the four cases to `concurrent.cc`
with the existing watchdog. Review D's "Queue is sound" missed these (calibration note: its probes covered
shutdown and one-queue wake-up only).

**CA2 metrics: `AtomicCounter::add` still wraps; the "exact saturation" fix is wrong (introduced, CR2 open).**
`metrics.hh:46-56`. The fast path loads `current < 2^63`, then `fetch_add`s. Between the load and the `fetch_add`,
another thread's `add(big)` takes the CAS path and lifts the value to `UINT64_MAX`. The `fetch_add` then wraps,
and the wrap is permanent: no later fix-up. AGENTS.md and README ("cannot wrap with fewer than 2^31 threads ...
Saturation is exact") consider only `observe_max`. A large `add` on the same counter does the same, and it is the
documented case: a negative duration cast to u64 into `sum_ns`. Probe `metrics_wrap_probe.cc` (probe not kept;
covered by `metrics_differential` and `metrics_model`) (4 threads
`add(1)` x200 racing one `add(UINT64_MAX)`; correct final value is `UINT64_MAX`):

| | M4 Pro clang | i9 clang | Linux VM gcc 11 |
|---|---|---|---|
| head: trials ending below max | 15618/20000 (lowest 1) | 4753/5000 (lowest 0) | 72/5000 (lowest 118) |
| start (CAS loop) | 0/20000 | 0/5000 | 0/5000 |

`test/differential.cc` never mixes small and large adds on one counter concurrently, so it passes. I see no
CAS-free fix: a fast add can sit preempted between its load and its `fetch_add` for any length of time, so no
slow-path clamp is safe. Options: restore the CAS loop (exact; 4-thread contended cost goes back from ~32 to ~66 ns
arm, from ~88 to ~245 ns x86), or keep `fetch_add` and document that saturation is best-effort under concurrent
large adds (an owner decision: README and AGENTS both promise exact). Add the probe to `differential.cc` either way.

## Non-blocking

**CA3 generation-cache: rehash exception safety (closed during the audit).** At 718a0fb, a throwing copy inside
`grow()` left a slot with `h != 0` and an empty `optional` (the same poisoned slot as CR1, reached through the
rehash) and dropped the rest of the old table. Probe `gencache_grow_probe.cc` (probe not kept; covered by `generation_cache_exception_safety`) (a Key with a user-declared
destructor, so its moves are copies; bad_alloc on the 4th copy): libc++ hardened build traps in `get()`; an
unhardened build finds 3 of 8 keys with `size()==8`. 2930a64 builds the new table aside and swaps it in. The probe
passes for throw points 1..12. The new `test/exception_safety.cc` traps on 718a0fb's header and passes on 2930a64.
CI for 2930a64 is green. ASan+UBSan (gcc 11, 3 runs) and TSan (5 runs of the differential test) pass on the VM.

**CA4 generation-cache: untargeted rows regressed.** Same bench source (`extra_bench.cc`, now rows in
`generation-cache:bench/bench.cc` and `flat-map:bench/bench.cc`), start vs head:

| row | arm start → head | x86 start → head |
|---|---|---|
| `Cache<int,int>` n=64 `get` hit, 1 thread | 8.06/8.07 → 11.8/12.4 ns (+50%) | 18.6/18.7 → 34.7/35.8 ns (+90%) |
| construct + destroy | 12.5/12.7 → 83.5/90.9 ns (6.8x) | 51.0/51.1 → 264/270 ns (5.2x) |
| string `get` n=64, 1 thread | 39.6/42.4 → 42.5/42.7 ns (no gain) | 170/172 → 109/111 ns |

The `get` cost is libc++'s `shared_mutex` (two mutex round trips per shared lock) on a short critical section. The
construction cost is two `std::random_device` draws for the seed (`generation_cache.hh:75`). Targeted rows hold:
string `get` n=100000, 1/4 threads: arm 462-533/1586-1880 → 237-257/350-371 ns; x86 902-925/2677-2686 → 460-462/
570-592 ns, at parity with `shared_mutex`+absl at 4 threads (571-605 x86, 369-508 arm). But 1 thread is 2x the
README's 116 ns on this run and 1.2-2x slower than `mutex`+absl (106-127 arm, 369-381 x86). Fix: seed from the
table's address plus a counter, or once per process, not per cache. The lock is the trade-off the design chose;
the README should name the small-cache single-thread cost. The seed only spreads index bits: a full `std::hash`
collision (crafted offline against libstdc++'s fixed-seed murmur or libc++'s CityHash) collides regardless, so the
CHANGELOG's "cannot be crafted offline to collide" overstates it.

**CA5 flat-map: the branchless search loses on x86 for 8-bit keys, large n and wide elements.** `flat_map.hh:209-225`.

| row (find, ns) | arm start → head | x86 start → head |
|---|---|---|
| u64 n=256 | 6.3/6.5 → 3.6/3.7 | 41.9/42.1 → 23.8/25.5 |
| u64 n=4096 | 11.1/11.2 → 6.3/6.3 | 60.3/61.2 → 59.1/60.2 (boost 52-61) |
| u64 n=65536 | 39.2/40.1 → 26.1/26.8 | **111.6/112.7 → 120.3/121.6** (boost 111-115) |
| `<i8,u64>` n=100 | 4.49/4.61 → 3.29/3.29 | **4.82/4.93 → 6.54/6.62** |
| `<u64,string>` n=1024 | 8.6/8.7 → 5.1/5.1 | **35.7/36.3 → 40.2/40.8** |

Arm wins every row; x86 loses 8-35% on three. This is the brief's "arm-only win with x86 loss". Fix candidates,
untested: prefetch both next midpoints in the loop (Khuong-Morin), and keep `std::lower_bound` for `sizeof(Key) == 1`.
Inserts on x86 got faster everywhere (u64 n=4096 665 → 196-200 ns, boost 205-248).

**CA6 flat-map: small-n insert regressed on arm.** `<u32,u32>` n=16 9.59/9.69 → 14.97/15.10 ns (+56%), n=64
13.6/13.7 → 18.4/18.6 (+35%), `<i8,u64>` n=100 12.7/12.9 → 16.3/16.5 (+28%); x86 is flat or better. Suspect the
`push_back` + `memmove` + `memcpy` sequence, which writes each new element twice, plus the `value_type` temporary
that `try_emplace` now builds (`flat_map.hh:280`). Fix candidate: take the memmove path only above a small tail
length. Targeted rows confirmed: arm u64 insert n=4096 303 → 172 ns, n=65536 5430 → 3750-3784 (boost 3760-3786).

**Memmove decision (owner question, review D CR6): not exploitable UB for any type that reaches it.**
`insert_at` (`flat_map.hh:239-253`) memmoves only when `Key` and `T` are both trivially copyable. `std::pair<K,T>`
itself is not trivially copyable: its assignment is user-provided. It is an implicit-lifetime type, though: the
standard specifies its copy and move constructors as defaulted (trivial here) and its destructor as trivial when
both halves have trivial destructors. The library needs C++20, where `memmove` implicitly creates objects of
implicit-lifetime types in the destination ([intro.object]/10-13, [cstring.syn]). The new pairs' `first` and
`second` are trivially copyable subobjects, so the copied bytes give their values, and the vector's pointers refer
to them by transparent replacement ([basic.life]/8). libc++ marks `pair` trivially relocatable under the same
condition and relocates it with memmove. No compiler optimizes on this, and nothing would let it: the copy goes
through `void*`.
- Types that would break (self-referential or address-registered: libstdc++ `std::string`, `std::list`, anything
  with a back-pointer) are not trivially copyable, so the gate sends them to `vector::insert`. The gate is
  load-bearing: a mutant that memmoves every type (mutant not kept; `flat_map_strategy` fails with the gate forced on) fails the repo test and my probe with ASan
  `stack-use-after-scope` under gcc 11/libstdc++ (libc++ strings would hide it).
- Formal edge: `volatile`-qualified halves (`flat_map<int, volatile int>`) count as trivially copyable, and a
  non-volatile `memmove` of a volatile object is formally UB. Nobody does this, and `vector` itself is shaky there.
  Adding `!std::is_volatile_v<T>` to the gate closes it.
- Under C++17 (pre-P0593) this would be formally UB; the header requires C++20, so that case does not arise.

Other flat-map mutants: comparator gate forced on (`std::greater<>` searched with `<`) is killed by the repo test
(abort). `base[half-1]` → `base[half]` survives, but it is an equivalent mutant: both forms are correct lower bounds.
My property probe (`flatmap_props.cc`, probe not kept; covered by `flat_map_comparators`: explicit `std::less<int32>`, bool, char, padded PODs,
`std::array<char,3>`, string/string, int8 with int16/int64 transparent queries in and out of range, uint8 with
uint64) passes under ASan+UBSan with gcc 11 and libstdc++.

**CA7 bloom-filter: `FastBloomFilter` misses are slower than legacy on x86 at 16 B and far behind boost.**
Miss ns, N=131072: arm legacy 27.9/28.3, Fast 18.4/18.6, Blocked 15.5/15.6, boost 19.2/19.2 (README's 26.7/17.4/14.7/17.0
holds within ~6%). x86: legacy 34.6/35.3, **Fast 38.3/39.0**, Blocked 31.0/32.8, **boost 22.8/23.6**; 64 B: legacy
86.3/89.3, Fast 58.6/62.1, boost 32.6/38.1. On x86 the all-20-probes OR-accumulate ([LESSONS](../LESSONS.md#bloom-filter), bloom-filter lesson 3) costs more
than the legacy early exit on a miss. The README's table is arm-only. Hit and add improve on x86
(add 43.4-44.8 → 36.4-37.9). The default type is unchanged, and its bit layout is pinned by a frozen-copy test.

**CA8 bloom-filter: `unsigned __int128` in a non-template inline function (`bloom_filter.hh:102`).** Every TU that
includes the header compiles it, even one that uses only `BloomFilter`. GCC `-Wpedantic` now warns (`ISO C++ does
not support '__int128'`), which breaks `-Werror -Wpedantic` consumers, and MSVC cannot compile the header (not a
claimed platform). Fix: `__extension__` on a typedef, or make `reduce` a template.

**CA9 metrics: "1 and 2 threads were unchanged" is false on arm.** 2 threads: CAS 5.3/5.5 → `AtomicCounter` 7.4/7.5 ns
(+38%; bare `fetch_add` 6.5/6.7). x86 2 threads improve (60.6/66.6 → 36.9/45.5). Contended gains are 2.0x on arm
(4 threads 64.4/68.0 → 32.3/32.8, 8 threads 322/340 → 161/169), not the CHANGELOG's 2.7x. x86: 2.6-4.2x
(223/268 → 86/90, 591/782 → 187/187). Histogram `observe`: arm 3.4 → 2.4 ns, atomic 3.9 → 2.1 ns; x86 6.2-7.1 →
5.7-6.3 ns, atomic 17.8-20.3 → 14.3-18.0 ns. Moot if CA2 restores the CAS loop.

**CA10 queue: x86 is below the naive baseline at 2+ threads.** Mitems/s 1x1/2x2/4x4/8x8. arm: start 12.2-15.0/5.6-5.7/
6.7-7.0/8.1-9.0 → head 48.2-48.9/19.9-20.8/21.7-22.5/27.7-29.4; naive 43.5-47.0/21.4-22.7/19.0-22.0/20.1-20.5;
moodycamel 7.6-10.3/5.9-6.4/5.4-5.7/5.8-6.0 (README claims hold). x86: start 2.9-3.0/1.5-1.6/1.1/0.9 → head
8.3-8.5/4.1-4.3/2.5-2.8/2.1; naive 9.0-9.1/5.8-6.1/4.0-4.3/3.9-4.1; **moodycamel 11.3-11.8/7.5-7.7/11.7-12.4/15.8-16.9**.
One cause measured: `_cnt_add`/`_cnt_sub` use a seq_cst `store`, which is an `xchg` (a locked op) on x86. A relaxed
store (a relaxed-store build of the bench, not kept; the release store landed in `queue:44211ce`) gives 9.2-9.8/4.9/2.7-2.8/2.3 (+8-18% at 1x1, 2x2 and 8x8, flat at 4x4). That does
not close the gap at 4x4 and 8x8; the rest is unexplained. x86 queue work was in progress at the time.

**CA11 hygiene.** Local, merged, unpushed branches remain in the working clones: `perf/queue`, `perf/bloom`, `perf/gencache`,
`perf/flatmap`, `perf/metrics` (each 0 commits ahead of origin/main); delete them. The remotes have only `main`. Every head is
CI-green on all 8 jobs. Each `[skip ci]` doc commit touches docs only, except queue's 1787904, which also trims a
`queue.h` comment (8 lines, comment-only, checked). READMEs and comments are present tense; CHANGELOGs hold the
history. flat-map's CI skips TSan, which is fine for a single-threaded library.

## Review D findings

[Review D](2026-10-31-review-d-containers.md), as of this audit:

| D | status | evidence |
|---|---|---|
| CR1 gencache poisoned slot | **closed** (89baa5b; rehash variant closed in 2930a64) | `test/differential.cc` ThrowKey; CA3 probe |
| CR2 metrics saturation | **open**: monotonic for a pinned counter, but wraps permanently while being pinned | CA2 |
| CR3 btree | out of scope | |
| CR4 gencache fairness / adversarial keys | documented (README:133); seed added, see CA4 caveat | README:133-156 |
| CR5 bloom Blocked FP | documented; confirmed 172/131072 (16 B), 217 (64 B) = 1.3-1.7e-3; Fast 0 | bench |
| CR6 flat-map memmove | decided: not exploitable UB (above) | mutant + reasoning |
| "Queue is sound" | **wrong**: CA1 | `queue_liveness.cc` |

## Per repo

**queue: NOT YET.** Correctness: TSan ctest x30 (VM, clang 12) passes, as does review D's `queue_wake_stress` under
TSan (300 iterations mixed, 300 untimed); gcc 16 build and ctest pass; but CA1. Perf: 3.3-3.9x arm, 2.4-2.8x x86;
at or above naive on arm, below on x86 at 2+ threads (CA10). Compat: API and default behavior unchanged except the
liveness regression. Bar: fix CA1; then CA10 is the x86 gap.

**metrics: NOT YET.** CA2 breaks the one documented contract it changed. Bucket count: the differential test
covers every edge ±2 plus 200k random values against `lower_bound`; TSan x10 and gcc 16 pass. Bar: restore exactness (CA2);
the contended cost then needs a layout change (striping, an ABI change), as the survey said.

**generation-cache: BETTER WITH CONDITIONS.** 2-5x faster string `get` (CA4 numbers), the CR1 and rehash exception
bugs closed with revert-checked tests, TSan x30 (718a0fb) + x5 (2930a64) clean, builds as C++17 as it claims, gcc 16
passes. Conditions: CA4 (per-cache `random_device` and the small-cache `shared_mutex` cost: document or seed
cheaply). Bar: near absl at 4 threads; 1.2-2x behind `mutex`+absl at 1 thread.

**flat-map: BETTER WITH CONDITIONS.** u64 insert at boost parity (arm and x86), find 1.5-1.7x faster on arm, memmove
gate sound. Conditions: CA5 (x86 find regressions on three rows), CA6 (arm small-n insert). Bar: name CA5's prefetch
or an 8-bit/size gate as the next change.

**bloom-filter: BETTER WITH CONDITIONS.** Additive types, default bit layout frozen and tested. My property probe
(`bloom_props.cc`, probe not kept; covered by `bloom_filter`: N=1000/1024/8192/131072, loads 0.5-2, salts 1-5, key lengths 0-69) finds no false negatives; Fast tracks legacy FP everywhere,
including non-power-of-two N (load 1: 1.0e-5 vs 1.25e-5 at N=1000; load 2: 8.5e-4 vs 8.6e-4 at 131072); Blocked is
1.3-1.5e-3 at load 1 and 0.9-1.0e-2 at load 2 (legacy 0.9-1.2e-3).
Conditions: CA8 (pedantic/MSVC), CA7 (state the x86 numbers; the miss path loses to legacy on x86 at 16 B).

**lru-cache, varint, ctrie: UNCHANGED.** No commits since before 2026-10-30; nightly CI green. Survey D put varint
and ctrie at or above their comparators; lru-cache is 1.16-1.38x the list+map textbook at cap 1k/64k and 0.98x at 1M.
The survey's unexplained hit-count mismatch (653353 vs 652900) is the documented `capacity + 1` overshoot:
`trim_and` runs before the insert (`lru-cache:lru.h:351`, `ARCHITECTURE.md:142`). `lru::lru(2)` holds 3 entries after 3
emplaces (`lru_cap_probe.cc`, probe not kept; covered by `lru_cache`). Pre-existing, documented; not a bug. lru.h uses deprecated `std::iterator`
(`lru.h:60`), which warns under libc++ (pre-existing).

## Verdict

queue and metrics block (CA1, CA2): each regressed a documented guarantee, liveness and saturation, behind
green CI. generation-cache, flat-map and bloom-filter are better than at start, with conditions. Escalate CA2
to the owner (exactness against contended cost is a contract decision) and CA1's shared-state fix to a design review
(per-queue pop condvar changes `QueueState`'s role).

Not run: GCC timing (gcc 16 build + ctest only); Windows/MSVC; FreeBSD (CI only); glibc `shared_mutex` timing (the VM is not a timing host, so CA4 is
measured on libc++ only); Apple M1 Pro; TSan on flat-map/bloom (single-threaded); a re-review of btree.

## Re-check CA2

**CA2: CLOSED** at `Kronuz/metrics` main 50d8bb8 (fix 4890fc0, flake fix 8c8ad90). No new blocking finding; two
non-blocking ones (RC1, RC2).

**The fix.** `metrics.hh:48-62` `BasicAtomicCounter::add` is the clamping CAS loop again (`:50-55`), `observe_max` a CAS
(`:56-60`), `get` one relaxed load (`:61`); `AtomicCounter` is the 64-bit alias (`:100`). Its generated code for
`add`, `add()`, `observe_max` and `get` is instruction for instruction the start's (645d729) on arm64 (43 lines) and
x86_64 (42), Apple clang 17 `-O2 -S`, labels stripped (probe not kept). `ContendedCounter` is `:72-98`, alias
`:101`. README, AGENTS.md and CHANGELOG now say that no `fetch_add` fast path can be added to a single word, and say
`add` and `observe_max` may be mixed on `AtomicCounter` only.

**The auditor's probe** (`metrics_wrap_probe.cc`, probe not kept; covered by `metrics_differential` and
`metrics_model`; 4 threads `add(1)` x200 vs one `add(UINT64_MAX)`), same source,
head vs the audited header (bdf4b29) as the control:

| | M4 Pro (clang 17) | Linux VM (gcc 11, glibc 2.35) |
|---|---|---|
| head `AtomicCounter` | 0/20000 (was 15618/20000) | 0/5000 (was 72/5000) |
| head `ContendedCounter` | 0/20000 | 0/5000 |
| bdf4b29 `AtomicCounter` (control) | 2984/5000 | 703/5000 |

**Trying to break `ContendedCounter`** (my probe `ca2_exact_probe.cc`, probe not kept: 6 writers and 2 readers per trial,
amounts drawn from {1, 2^32-1, 2^32, 2^32+1, 2^40, 2^62, 2^63-1, 2^63, MAX-1, MAX}; oracle `min(seed + sum, MAX)` in
u128; each reader checks `get()` against the saturated sum of finished adds below and of started adds above, never
decreasing, and MAX staying MAX; five seed modes put `small_` and `large_` on both thresholds, mode 4 puts `small_` at
or above 2^63; add-only and mixed add/`observe_max`):

| attempt | result on head |
|---|---|
| torn or non-monotonic reader across the two words | 0 violations in every run: M4 Pro 500 trials x 10 passes, VM 400 x 10, plus TSan runs. The same probe fails on bdf4b29: 13 reads below the finished-add bound and 2 decreases (M4 Pro), 3 and 1 (VM) |
| saturation at the boundary: `small_` = 2^63-1 with 6 threads x400 `add(2^32-1)`; `large_` within 2^36 of MAX; `small_` >= 2^63 | exact in every trial (0/100 and 0/80 inexact); `get()` never above the started total |
| `observe_max` interleavings | model: `observe_max` alone (422 scenarios), and add mixed with `observe_max` on `AtomicCounter` (18) hold in every interleaving. `ContendedCounter` mixed add and `observe_max` is out of contract: it cannot wrap (`observe_max` only touches `large_`) and my mixed mode stays between `sat(sum of adds)` and `sat(adds + maxima)` with no decrease, but the value is not a maximum |
| the bound is real: 8-bit `ContendedCounter`, `small_` = 127, n threads `add(15)` once | n=8: 0/10000 (M4 Pro), 0/8000 (VM). n=16, outside the bound: 99/10000 and 511/3000 inexact on M4 Pro, 0 on VM and M1 Pro. At 64 bits the worst `small_` is 2^63-1 + n(2^32-1) = 2^64 - 2^31 - 1 at n = 2^31 |
| my reading of the proof | holds: the first add that takes `small_` to 2^63 is itself counted among the n; each thread's next load sees its own previous add (per-word coherence), so it adds at most once after that. A reader's `get()` is `small(t1) + large(t2)`, which lies between the values at t1 and t2 and need not be a value the counter held at one instant. The docs claim only "never decreases"; not probed |

Beyond the suite, exhaustive over every interleaving with the repo's model code (extensions not kept, 8 bits):
`ContendedCounter` 2 threads x3 and 3 threads x2 adds across 2^7 with a reader (792 scenarios, 4.1M states);
4 threads x2 adds from `small_` 127 and 120 (95.0M states); saturating through both words with a reader (585
scenarios, 1.65M states); `AtomicCounter` multi-add (168 scenarios, 6.2M states); n = 5 and 6 threads `add(15)` from
127 (0.5M and 44.9M states): all hold. The suite checks 8 hold and 9 wrap on the single worst schedule; I did not
complete the exhaustive run for 7 to 9 threads (it did not finish at 7).

**Revert check** (mutant copies not kept; same result on M4 Pro and the VM):

| change | `metrics_model` | `metrics_differential` | my probe |
|---|---|---|---|
| the old fast path put back in `BasicAtomicCounter::add` | fails: "value decreased from 255 to 14" (schedule 0 0 0 0 1 0 0 1) | fails at `differential.cc:264` | fails on the VM; the real bdf4b29 header fails it as well: wrap race 1201/1500 below MAX (M4 Pro) |
| `small_` check removed from `ContendedCounter::add` | fails: "value decreased from 245 to 4", init [200,0], 4 x `a15` | fails (`:103`, the 16-bit instance; the 64-bit one passes, see RC2) | fails only in mode 4: 33/200 and 49/300 inexact, readers 8704 and 1005361 below the finished bound |

**Sanitizers.** CI at 50d8bb8 is green on all 8 jobs; `linux-tsan` runs `metrics`, `metrics_model` (9.0 s) and
`metrics_differential` (15.7 s), `linux-asan-ubsan` the same three (17.6 s). Locally, clean (no report, exit 0):
TSan on `test.cc`, `differential.cc` and my probe, both counters (twice for the tests on the VM): VM clang 12 with `setarch -R`, M4 Pro Homebrew
LLVM 23.1.4, M1 Pro Apple clang 21; UBSan on M4 Pro and M1 Pro (tests and probe); ASan+UBSan on the VM (g++ 11): `test.cc`,
`differential.cc`, `model.cc` at the CI flags (`-O0`, 42 s) and at `-O1`, and the `AtomicCounter` probe. One `-O1`
ASan run of `model.cc` on the loaded VM died after 8m20 (8 `AddressSanitizer:DEADLYSIGNAL`, 7 min of system time)
and did not recur in two reruns; I put it down to the host. The `ContendedCounter` probe under ASan reached mode 2 in
250 s (ASan is slow with two spinning readers) and was clean up to there. Toolchain failures, not code: g++ 11 TSan
segfaults at startup on the VM (0.1 s, with `setarch -R`), and Apple clang 17 TSan segfaults at startup on the M4 Pro (even
`test.cc`). ThreadSanitizer sees only the relaxed operations, and `test/model.cc` is sequentially consistent, so
weak-memory behavior rests on the per-word coherence argument and the real-thread probes (M4 Pro, M1 Pro, x86).

**RC1 (low, docs, outside the repo): the catalog still carries the withdrawn claim.** `cpp-libraries:AGENTS.md:2390`
(main, same text on GitHub): "`AtomicCounter::add` is one `fetch_add` while the counter is below 2^63 ... contended adds
cost about what a bare `fetch_add` costs ... Saturation is exact." The saturation sentence is true again; the
`fetch_add` and cost sentences are not, and `ContendedCounter` is missing from the Key API (`:2377`). Fix: say
`AtomicCounter` is a CAS loop and `ContendedCounter` is the opt-in two-word counter, with the README's contended-counters
paragraph and its use-with-`add`-or-`observe_max` rule.

**RC2 (low, test gap): two of the proof's steps are checked only at 8 bits or one schedule.** The model never has
a thread add more than once across 2^7 (`grid` with `per_thread` > 1 starts from zero), and the 8-or-9 bound runs one
schedule; my scenarios above pass and could be added at the cost of about 4M states for the 2x3 family. And
`metrics_differential` at 64 bits does not kill the `small_`-check mutant (`small_` cannot reach 2^63 by real adds);
the 16-bit instance and the model do, so keep both.

Not run: benchmarks, so the CHANGELOG and README performance tables, and CA9's numbers, are unchecked;
a weak-memory model checker; exhaustive 7 to 9 thread schedules; gcc 16. Hosts: the M4 Pro under an exclusive hold,
the M1 Pro, the Linux VM (exclusive holds, then a light hold after its reboot). Probes and logs were not kept. No commits.

## Re-check CA1

Re-check, 2026-11-01 00:17-01:40. Subject: Kronuz/queue main `e94be7d` (the fix) on top of `44211ce` (inline fast
path). Main moved to `31552f9` (move assignment) during the re-check, and every claim below holds at `31552f9`.
Hosts: Apple M4 Pro (Apple clang 17, under an exclusive hold) and the Linux VM (gcc 11 and clang 12, under an
exclusive hold). Probes, scripts, mutant headers and logs were not kept. No commits.

**CA1: CLOSED** at `31552f9`. `e94be7d` closes the four classes; `31552f9` closes the move-assignment class (below).

| check | with the fix | fix removed |
|---|---|---|
| auditor's `queue_liveness.cc all 10 2000` | 0/40 stuck (M4 Pro `e94be7d`, VM gcc `31552f9`); `all 5` 0 stuck under ASan+UBSan and TSan | `44211ce`, `1787904`: clear, erase, threshold 2/2 stuck each |
| `test/liveness.cc` (25 cases at `e94be7d`, 26 at `31552f9`) | OK x5 M4 Pro, x3 VM gcc, x3 TSan, x1 ASan+UBSan | `44211ce` header: the 9 cases the commit names fail; `e94be7d` header with `31552f9` tests: the move case fails and `test.cc:321` aborts |
| `liveness stress` | 2000 rounds OK (M4 Pro, VM gcc, TSan); 400 rounds under ASan+UBSan | `44211ce`: hang at round 18; `1787904`: round 4 |
| review D `queue_wake_stress`, mixed and untimed | 1000+1000 OK (M4 Pro, VM gcc); 300+300 under TSan and ASan+UBSan, 0 reports | |
| `test/concurrent.cc` | OK (ctest on M4 Pro; VM gcc; 200000 items under TSan and ASan+UBSan, 0 reports) | |
| CI at `31552f9` | 8/8 jobs green (linux-tsan runs liveness and stress) | |

Review D's mutants, applied again to the `e94be7d` header. M1 (no empty critical section in `_wake_all`) survives
`liveness.cc` but dies in `concurrent.cc` ("shutdown race: waiter lost wake-up", iter 40) and in D's stress (HANG in
both modes). M2 (untimed consumer uncounted) dies in `liveness.cc` (watchdog exit 3), `concurrent.cc` ("untimed wake:
hang") and D's untimed stress. M2p is its producer twin, which I added. It dies in `liveness.cc` (the producer cases
never see their threads park) and in `concurrent.cc` (the bounded run hangs and is killed at 120 s). D's stress
misses it.

Transitions, enumerated from `queue.h` at `31552f9`. A consumer of Q waits on Q's own `_pop_cond` (`:115`) for
`Q._finished || Q._ending || !Q._items_queue.empty()`. A producer waits on the state's `_push_cond` for
`Q._finished || Q._ending || _cnt < _hard_limit`. Every wake decision (`_pop_waiters`, `_room_freed`) is made under
`_state->_mutex`. Every waiter counts itself and blocks under that same mutex, so a notify sent after the unlock is
not lost. `end()` and `finish()` store their flags outside the lock; the empty critical section (`:291`) orders those
stores before the broadcast.

| change | code | wakes | covered by |
|---|---|---|---|
| `push_back`/`push_front`, forced, timed, non-blocking | `:398-403`, `:413-417` | one consumer of this Queue | 4 push cases, shared-state case, timed+untimed |
| `QueueSet::push` (new key; renewal) | `:528-535` | one consumer; a failed renewal reports its slot (`:529`) | QueueSet push case. A renewal fails only on a stopping queue (no force, no shared state), so `:529` is unreachable, as ARCHITECTURE says |
| `pop_back`/`pop_front`, `QueueSet::pop`, `QueueSet::erase` | `:431-435`, `:443-446`, `:602-605`, `:629-632` | `_room_freed(1)` (`:82-87`): one producer, if one is parked and `_cnt < _hard_limit`; the threshold no longer gates it | pop x2, threshold, QueueSet pop and erase; timed and non-blocking pops: my `nbpop` |
| `clear()`, `QueueSet::clear()` | `:459-462`, `:612-616` | all for n > 1, one for n = 1, also when stopping | clear x2, ended shared A; n = 1: my `clearone` |
| `end()`, `finish()` | `:290-294`, `:378-392` | all, on both condvars | 4 stop cases; mutant M1 |
| destructor | `:366-376` | all, on both, under the lock | finished shared A; running A: my `destroy` |
| move assignment | `:319-355` | as `clear()`, after unlocking; one lock on a shared state; returns at once on self-assignment | `31552f9` liveness case and `test.cc`; my `moveleak`, `movenowait`, `moveshared`, `selfmove` |
| a refusal at the soft limit after waiting; an insert or take that throws after waiting | `:150-156`; `_hand_on` `:205-218` | the next waiter, under the lock | soft-limit case, two throwing cases |
| a deadline; the limits; move construction | | nothing. A deadline changes no state; the limits have no setter (ARCHITECTURE.md:198); move construction moves the count and the items together | |

I find no transition that wakes the wrong condvar, uses the wrong count, or wakes nobody. The "one is enough"
argument in ARCHITECTURE ("Wake-ups") holds. The consumers on a `_pop_cond` wait for one thing. The producers on
`_push_cond` wait for room or for their own Queue to stop, and a stop is a broadcast. Every woken thread that does not
use its wake-up hands it on.

The extra probe, `recheck_probe.cc` (probe not kept), covers the transitions the tests skipped at `e94be7d`: non-blocking
and timed pops, a running A destroyed on a shared state, a one-slot `clear()`, and four move-assignment cases. At
`e94be7d` and at `44211ce` all four move cases fail:
- B's producer is STUCK; the state's count is 1 with no item in any Queue.
- A later push on that state is refused.
- `a = std::move(b)` with both on one state deadlocks in `std::lock` (child killed at 3 s).
- `a = std::move(a)` deadlocks the same way.

This bug predates the audit (start had the same `operator=`), so it is not CA1, and the 1 s poll could not have
recovered it. At `31552f9` all 8 cases pass on the M4 Pro, with VM gcc 11, and under ASan+UBSan. Under TSan the
5 cases that do not fork pass.

**CA10: CLOSED**, on the timing recorded with the fix. I did not time it (this re-check ran no benchmarks).
- The fix's interleaved i9 log (not kept) has 12 rounds of the same
  `benchmark/bench.cc`, whose mutex+condvar+deque baseline has not changed since extraction.
- I recomputed it. Queue/baseline at 1x1, 2x2, 4x4, 8x8: 1.14, 1.17, 1.20, 1.13 at `44211ce`;
  1.17, 1.18, 1.19, 1.13 at `e94be7d` (per-round lows 0.98-1.14); 0.88, 0.67, 0.56, 0.56 at `1787904`. The
  `1787904` ratios match the audit's 0.92/0.71/0.63/0.53.
- Structure (script not kept, Apple clang `-O3 -arch x86_64`): at `1787904`, `push_back` and `pop_front` are
  out of line, each with an `xchg` (the seq_cst count store). At main both are inlined into the caller and the file
  has no `xchg`.
- `31552f9` does not touch the hot path.
- README's "1.16x to 1.25x" (x86, Apple clang) comes from the `44211ce` commit run. The 12-round run gives 1.13-1.20x,
  within its A/A spread.

New findings: none.

Outside CA1 (one line each):
- Destroying a Queue while its own threads are parked is undefined behavior. They wake into a destroyed Queue, and into a destroyed mutex if it held the last reference, yet ARCHITECTURE.md:172 says teardown "releases any thread still blocked on it" (wording from start, `:142`).
- The move constructor dereferences `q._state` (`queue.h:309`), so moving from a moved-from Queue crashes (this predates the audit).
- README's x86 paragraph does not say that moodycamel beats Queue 2-4x on x86 at 4x4/8x8 (audit table).
- Tooling. Apple clang 17 `-fsanitize=thread` binaries segfault at startup on the M4 Pro. gcc 11 ASan on the VM loops on `AddressSanitizer:DEADLYSIGNAL` without `setarch -R`; one run wrote 936 MB before I killed it and deleted the file.

Not run: TSan on macOS (the startup segfault; TSan ran on the VM and in CI); benchmarks (CA10 rests
on the fix's log plus the asm); the Apple M1 Pro;
FreeBSD and Windows (CI's FreeBSD job is green); the forking move cases (`moveshared`, `selfmove`) under TSan.
