# Audit: systems (compressors, storage, logger, scheduler, allocators, fs)

- Date: 2026-10-31. Kind: cluster audit of the October 2026 performance and correctness work (read-only), from a
  fresh context, 13:00-14:40, with the re-checks of FS1 (20:45-22:45) and AL1 appended.
- Repos: `compressors:dc4474b..d82b1d8`, `storage:e4c5746..f48e5da`, `logger:ce27b90..5299eb3`,
  `scheduler:ae3f0f9..5fa44d1`, `allocators:e8fb173..3e3dfb2`, `fs:ce16118..ad95736`; start is
  `git log origin/main --before=2026-10-30 -1`, head is `origin/main` at the time of the audit. Re-checks: `fs:d6d8bc2`,
  `allocators:e38f759` and `allocators:ea0c5e6`.
- Machines: Apple M4 Pro, Intel Core i9-9980HK, Apple M1 Pro, a shared Linux x86-64 VM (clang 12, g++ 11.2), GitHub
  Actions runners. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| FS1 `copy_file` empties a source that is also the destination | closed | `fs:d6d8bc2` | `fs` (`test_copy_file_same_file`) |
| ST1 storage pins compressors before the CR4 fix | closed | `storage:7cabb43` | `compressors_lz4_oneshot` (in compressors: 98 KB of 3-byte blocks stay under 1 MB) |
| AL1 copy assignment shares the pool | closed | `allocators:e38f759` | `allocators_propagation`, `allocators_pool` |
| C1 fuzz target does not reach the new `decompress_lz4` | open | - | - (open: `compressors:fuzz/fuzz_lz4.cc` mode 0 still compares only the two stream classes; no commit references C1; damaged input does reach `decompress_lz4` in `compressors_lz4_oneshot`) |
| C2 per-thread lz4 state and scratch undocumented | no change | `compressors:9bd24af` | - (kept by design, now documented in `compressors:docs/API.md`) |
| L1 logger README ordering sentence overclaims | partly closed | `logger:f95ff17` | - (README scoped to lines through the LOG thread and names the two kinds that overtake; no test pins them) |
| L2 TSan reports in stash with several producers | not a defect | `stash:0efcd0f` | `stash_concurrent` (four producers, clean under CI's clang 18 TSan) |
| S1 `add()` reads the published wakeup before its fence | closed | `scheduler:62a4fe8` | `scheduler_handshake_model` |
| S2 single-producer `add()` 1.33x slower after the loss fix | closed | `scheduler:62a4fe8` | `scheduler_post` (`busy_pass`); `scheduler:bench/bench_post.cc` |
| N1 README thread paragraph silent on moving a container | open | - | - (open: `allocators:README.md:88-92` lists copying as safe and says nothing of moving; no commit references N1) |
| N2 `a = {}` and `a.clear()` read like a re-pool | open | - | - (open: the README names only move-assigning a fresh container) |
| N3 `splice`/`merge` after `e = d` | open | - | - (open: the CHANGELOG entry for `e38f759` does not mention it) |

L2 was refuted by `stash:0efcd0f`: every report pairs an access with the construction of an object reached through a
lost compare-exchange, which acquires on failure; LLVM 12's TSan runtime ignores the failure order (LLVM 13 applies it),
and with acq_rel on success the same 12-minute run gives 0 reports. The allocators `construct` forwarding fix that was in
flight at the audit landed as `allocators:7cdb0f8` (test `allocators_construct`). Two follow-ups of the FS1 re-check
have no ID and stay open: the repo test has no `st_dev` case (two mounts that hand out the same inode number), and
the no-`S_ISREG` mutant is caught only on Linux. The review H findings table below is resolved in
[review H](2026-10-31-review-h-systems.md).

## Summary

| repo | start -> head | verdict | blocking |
|---|---|---|---|
| compressors | dc4474b -> d82b1d8 | **BETTER** | none |
| storage | e4c5746 -> f48e5da | **BETTER WITH CONDITIONS** | pin still at 0498bf5: H's CR4 (64 MB from 98 KB) still live in storage |
| logger | ce27b90 -> 5299eb3 | **BETTER WITH CONDITIONS** | none; README ordering sentence is false as written (doc fix) |
| scheduler | ae3f0f9 -> 5fa44d1 | **BETTER** | none; S2: the loss fix costs 1.33x on single-producer `add()` throughput (M1 Pro), S1: one formal fence gap |
| allocators | e8fb173 -> 3e3dfb2 | **BETTER WITH CONDITIONS** | AL1: copy-assignment shares the pool; heap corruption reproduced |
| fs | ce16118 -> ad95736 | **NOT YET** | FS1: `copy_file` empties the source when src and dst are the same file (introduced) |

CI (GitHub Actions runners): the last code commit of every repo is green on all 8 jobs (Linux gcc/clang x86_64, arm64, macOS arm64/x86_64,
FreeBSD, ASan+UBSan, TSan); the heads are `[skip ci]` doc-only commits (diffs checked: docs only). Every new test
is registered in CTest and runs in those jobs. No campaign branch is left on any remote (the remote branches
`fix/lz4-bounds`, `phase7c/l6-streamed-write`, `wip/walk-based-clean`, `track/http-integration` all predate
2026-10-30). All six stay C++20 as before; `allocators.h`, `scheduler.h`, `compressor_lz4.h`, `fs.hh` compile alone.

## Blocking

### FS1 (fs, introduced by 14932b9): `copy_file` destroys its source when source and destination are one file
`fs.cc:374` opens the destination with `O_TRUNC` before reading the source. When both paths name the same inode
(directory copied onto itself, `copy_file(d, d, false, "f", "f")`, or a destination that is a hard link or
symlink to the source) the open truncates the source to 0 bytes, the read loop sees EOF at once, and the call
returns **0**. Probe `fs_self.cc` (probe not kept; covered by `fs:test/test.cc` `test_copy_file_same_file`), on the
shared Linux x86-64 VM with clang 12:

| case | start | head |
|---|---|---|
| `copy_file(d, d)` | rc 0, 39 -> 39 bytes | rc 0, 39 -> **0 bytes** |
| `copy_file(d, d, false, "f", "f")` | rc 0, 39 -> 39 | rc 0, 39 -> **0** |
| dst `e/f` hard link of `d/f` | rc 0, 39 -> 39 | rc 0, 39 -> **0** |

Fix: open the destination without `O_TRUNC`, `fstat` both descriptors, refuse (or skip) when `st_dev`/`st_ino`
match, then `ftruncate(dst_fd, 0)`; add the three cases above to `test_copy_file`. Everything else in the
copy_file rework is right (see fs below).

### ST1 (storage): main still pins compressors 0498bf5, so H's CR4 is still live in storage
`storage:CMakeLists.txt:27` pins `0498bf5`, the commit *before* the decoder-sizing fix (8f57675). Every lz4 record
read goes through `decompress_lz4` before the footer checksum is checked, so a corrupt or hostile volume still
gets the up-front `blocks * 2 KB` reservation (up to 64 MB, `bad_alloc` instead of `StorageCorruptVolume`). The
pin bump existed only as an unpushed local commit. Condition: push it (with the strict-stox / stringified pins it
carries) and let CI run.

### AL1 (allocators, introduced by 2fc537f): container copy-assignment shares the pool, against the README contract
`allocators.h:336` sets `propagate_on_container_copy_assignment = true_type`. After `e = d`, `e` holds `d`'s pool
family, while the README (`README.md:69-73`) and `ARCHITECTURE.md:112-115` say a container *copy* gets a new pool
and "copying a container to another thread is safe". Copy-construction does get a new pool
(`select_on_container_copy_construction`); copy-assignment does not. Probe `alloc_probe.cc` (probe not kept; covered by
`allocators:allocators_propagation`) part 3: `List d{1,2,3}, e{9}; e = d;` then one thread churns `d`, another `e`:
- ASan+UBSan (Linux VM): `SEGV ... in std::__detail::_List_node_base::_M_unhook()` from `list::pop_front` (heap corrupted).
- TSan (Linux VM): data race `pool_class::allocate` (allocators.h:172) vs `pool_class::deallocate` (allocators.h:189), and a
  race in `pool_family::get` (allocators.h:261) on the lazily filled class vector.
- The repo's own test asserts the sharing (`test/pool.cc:208`, "POCCA: e takes d's allocator").
Fix: `propagate_on_container_copy_assignment = std::false_type` (what `std::pmr::polymorphic_allocator` does; the
copy then allocates from `e`'s own pool, no UB because the allocator is not replaced), keep POCMA/POCS true, and flip
the test. Or, if sharing on copy-assign is wanted, say so in the README thread paragraph; the code and the prose
cannot both stand. Moved-from containers also keep the family (POCMA plus copy-as-move); worth one README sentence.

## compressors: BETTER

What changed: `compress_lz4`/`decompress_lz4` became out-of-line loops that bypass the stream classes (contiguous up to
the 256 KB ring wrap, a ring after it), the decoder sizes buffers from decoded data (8f57675), and XXH32 pins its lanes
to scalar registers on AArch64 only.

Correctness, with evidence:
- **Hostile input, ASan+UBSan (Linux VM, clang 12, `setarch -R`, `ASAN_OPTIONS=max_allocation_size_mb=64`)**: my driver
  `lz4_fz.cc` (probe not kept; covered by `compressors:compressors_lz4_oneshot`, `compressors_corrupt` and
  `compressors:fuzz/fuzz_lz4.cc`) (oracle: the unchanged `LZ4DecompressData`, verdict + bytes; inputs 0-1.3 MB weighted
  at the wrap and second wrap; 11 mutations incl. forced header lengths 0/max/max+1/one-past-input, block
  reorder/duplicate/drop, splices; syntactic LZ4 blocks with random match offsets 1..65535 after a valid prefix so
  references land in prefix, extDict-from-contiguous and ring; garbage): 78 seeds x 1000 iterations = **624 000
  comparisons, 435 000 rejected, 105 000 valid decodes past the wrap, 0 mismatches, 0 ASan/UBSan reports, no allocation
  over 64 MB**. Half the runs used a build whose `Scratch` is an exact-size heap block (the stack/thread-local cache
  otherwise hides overruns from ASan). libFuzzer (`lz4_lf.cc`, probe not kept; covered by `compressors:fuzz/fuzz_lz4.cc`;
  raw bytes and one framed block after a 300 KB prefix, ASan+UBSan, 2 x 20 min): 300 000 execs, cov 1691, 0 crashes.
- **Mutant**: ring buffer 1 KB short in `decompress_lz4` -> heap-buffer-overflow on seed 1 (the fuzz bites). Two
  off-by-one mutants of the contiguous capacity and wrap test survived and are equivalent: the bound has exactly one
  byte of slack, and decoding is layout-independent once the 64 KB history is kept (reasoned, not a gap).
- Byte identity with the classes: the repo test, my fuzz (every round-trip compares `compress_lz4` with the class),
  and storage volume files (below) agree. On-disk format unchanged.
- CR4 is fixed here: header-derived sizes no longer reach an allocation; hostile streams that pass the contiguous
  phase reserve at most 16x the input (computed: 100 MB of 3-byte blocks -> 1.6 GB virtual; documented in README:81-84).

Performance (`bench_comp.cc`, probe not kept; covered by `compressors:bench/bench_lz4.cc`, `bench_xxh32.cc` and
`bench_oneshot.cc`; same source against both trees, median of 9, spread = max/min; run order start, head, head for
the A/A):

| row | Apple M4 Pro start | head (A/A) | Intel Core i9-9980HK start | head (A/A) |
|---|---|---|---|---|
| lz4 c random 256 B | 1947 ns | 345 / 330 (5.8x) | 5841 | 473 / 461 (12.5x) |
| lz4 d random 256 B | 1631 ns | 35.0 / 36.8 (45x) | 5370 | 113 / 111 (48x) |
| lz4 c / d random 1 MB | 469 / 266 us | 240 / 40.6 (1.95x / 6.6x) | 946 / 503 | 540 / 77 (1.75x / 6.5x) |
| lz4 c / d text 1 MB | 1409 / 592 us | 1165 / 352 (1.21x / 1.68x) | 1796 / 1011 | 1369-1433 / 492-507 (1.25x / 2.0x) |
| lz4 d random 300 KB (past wrap) | 87.5 us | 11.1 (7.9x) | 111 | 21.6-22.6 (5x) |
| XXH32 stream 1 MB | 193 us | 91.4 / 91.8 (2.1x) | 205 | 202 / 206 (1.0x, AArch64-only change, expected) |
| zstd d 4 KB random (control) | 278 ns | 300 / 289 | 560 | 473 / 522 |
| deflate d 1 MB text (control) | 484 us | 485 / 490 | 1406 | 1442 / 1422 |

Spreads 1.01-1.2 on the M4 Pro (some 256 B rows 1.3-1.9), 1.05-1.5 on the i9. Claims
confirmed or beaten (256 B decompress "20-50x" holds; 1 MB random decompress 3.4x claimed, 6.6x measured). Control
rows (untouched zstd/deflate) move within their spread on both. No x86 regression; XXH32 is unchanged on x86 as
designed. The 256 B decompress (35 ns) now beats the [survey](2026-10-30-survey-systems.md)'s byte-identical
prototype (63 ns); the remaining gap to a raw `LZ4_decompress_safe` (7.8 ns) is framing plus the returned `std::string`.

Non-blocking:
- C1 `fuzz/fuzz_lz4.cc:57-61`: no mode feeds arbitrary bytes to `decompress_lz4` (mode 0 runs only the classes; modes 2-3
  feed it valid or class-checked streams), so the new decoder is not in the repo's libFuzzer target. Add
  `decompress_lz4` to mode 0 against `by_data`, as the `lz4_lf.cc` probe does.
- C2 ([review H](2026-10-31-review-h-systems.md) CR5, still open, undocumented): per thread, `compress_lz4` keeps a
  16 KB `LZ4_stream_t` and both one-shots a scratch of up to 1 MB (`compressor_lz4.cc:472, 515`) for the thread's
  life. Say it in README.
- Bar: at the comparator for decompress. Compress at 256 B is about 330 ns on the M4 Pro, dominated by the full 16 KB
  `LZ4_resetStream` per call (`compressor_lz4.cc:519`); not measured separately.

## storage: BETTER WITH CONDITIONS (ST1)

- **Format identity** (`stor_fmt.cc`, probe not kept; Linux VM): 63 records per volume (21 sizes from 0 B to 1 MB+3,
  around 2 KB, 64 KB, the 256 KB wrap and 3 x 256 KB; random, text, runs) for none/lz4/zstd/deflate. Volumes written by
  head twice and by start are **byte-identical** (`cmp`, 16.3 / 8.2 / 6.6 / 6.3 MB). Head reads start's volumes and
  start reads head's, whole-record and 2 KB-chunked: 4 x 63 records OK each way.
- `read(limit, args)` (storage.h:1632-1660, H's CR9): correct as read; mutant (drop one byte for records over 4 KB)
  fails 5 of 8 CTest tests, so the suite covers it although the commit added none.
- Performance: not re-run here (both timing hosts were busy); the read and write wins are the lz4
  one-shot wins above, which storage calls once per record.

## logger: BETTER WITH CONDITIONS (doc)

- Ordering contract, `test/order.cc`: passes on head (2 797 958 ordered pairs); with 06a27d2 reverted (shift skips
  `clears` lines) it fails in round 0 (Apple M1 Pro, clang 21). Timestamp differential `test/timestamp.cc`: 169 820
  comparisons identical on macOS arm64.
- finish() drain (`lg_finish.cc`, probe not kept; covered by `logger:logger_order`, its `finish()` case; 4 producers
  logging until and after a random `finish()`, 60 runs each): **0 lines lost or duplicated** on start and head (head
  logs 3x more lines in the window).
- L1 (doc, pre-existing behaviour, new claim): README:110-112 says "Of two lines due in the order they were logged, the
  first is never written after the second". False for two cases on both start and head: (a) an async line
  (`L_INFO`..`L_ERR`, `ASYNC_LOG_LEVEL` = `LOG_ERR`, logger.h:338) followed by a synchronous one (`L_CRIT`+, written inline):
  `lg_sync.cc` (probe not kept) puts the CRIT first in 1999/2000 pairs on start and 2000/2000 on head; (b) across
  `finish()`: lines refused after it are written inline before the drained ones (`lg_finish`: about 195 of 200
  post-finish lines per run overtake, start and head alike). Scope the sentence to lines that go through the LOG thread
  and to before `finish()`.
- L2 (pre-existing, escalate to the stash owner): with two or more producers on one scheduler, TSan reports data races
  inside stash `StashValues::put` / `Stash::Data::get` (stash.h:1018, atomic read vs an earlier plain write in chunk
  setup; 10 distinct reports in 15 min on the Linux VM). Many producers is the logger's normal mode. The
  campaign recorded it ([LESSONS](../LESSONS.md#scheduler); scheduler AGENTS.md: "with two, TSan reports races inside
  stash's multi-producer `put`") and gated CI on one producer, but nobody has said whether it is a real race or a
  missing annotation, and stash main (2e2b75f) differs from the pin by one line, so it is still there. Not introduced.
- Performance (`bench/lg.cc`, M1 Pro under a 3-core background load, so indicative only; start, head, head, start):

| row | start | head |
|---|---|---|
| 1 producer, end-to-end ns/line | 822 / 825 | 520 / 519 (1.58x) |
| 1 producer, steady (LOG thread draining) | 491 / 494 | 492 / 491 (tie) |
| 1 producer, burst (LOG thread idle) | 1596 / 1579 (spread 1.03-2.9) | 1508 / 1524 (spread 1.25-3.8) |
| 4 producers, steady | 607 / 672 | 339 / 334 (1.9x) |
| 4 producers, end-to-end | 964 / 1003 | 530 / 535 (1.85x) |

  The four-producer and end-to-end wins reproduce; the README's one-producer figure (235 ns burst on the M4 Pro) did not
  reproduce on the M1 Pro (no 1-producer producer-side gain there). M4 Pro rerun: see Not run.

## scheduler: BETTER

- **Lost wake-up (H CR1) is fixed.** Independent stress `sched_stress.cc` (probe not kept; covered by
  `scheduler:test/soak.cc`, the `scheduler_soak` tests): each producer keeps one task in flight (due now / +0-200 us /
  +0-3 ms), waits for it, and adds the next one at once or after a random spin or sleep, so the next `add()` lands
  while the worker is between its walk and its sleep; with one producer per scheduler nothing else can rescue a missed
  wake-up, and a task not fired within 1 s counts as lost (the worker's idle target is 30 s).

| build | config | adds | lost | notes |
|---|---|---|---|---|
| head, TSan (Linux VM, clang 12) | 3 sched x 1 producer, 20 min | 4 560 207 | **0** | 0 TSan reports; max late 302 ms |
| head, TSan | 1 sched x 3 producers, 15 min | 3 508 352 | **0** | stash races, L2 |
| head, -O2 (Linux VM) | 3x1 and 1x3, 5 runs of 10-15 min | 18 562 296 | **0** | |
| start ae3f0f9, TSan | 3x1, 15 s | 5 741 | **42** | |
| head minus the late `peep` (mutant), TSan | 3x1, 15 s | 4 054 | **45** | |
| start / mutant, -O2 (M4 Pro) | 3x1, 10 s | 17 999 / 17 040 | 18 / 19 | head: 43 292 adds, 0 |

  So the stress finds the old bug in seconds (about 1 in 100-1000 adds, against the repo soak's 1 in 60 000) and finds
  none in 26.6 M adds on head. A few tasks on head fired 0.6-3.3 s late (the 3.3 s one in an uninstrumented run); in all
  5 instrumented ones `add()` itself had taken the same 0.6-1.1 s before returning (the task's due time is stamped on
  entry, the put happens later), so the delay is on the producer's side of the put: VM preemption at nice 10 and load 17
  fits; a stall inside stash's put cannot be excluded from these runs. Two later 10-minute runs at lower load had none
  (max 30 ms).
- **S2, regression on an untargeted row: single-producer `add()` throughput.** `sched_add_bench.cc` (probe not kept;
  covered by `scheduler:bench/bench_post.cc`, its `add()` row; P producers each add 200 000 immediate tasks while the
  worker drains; median of 5; two interleaved rounds), M1 Pro, clang 21:

| ns per add | start ae3f0f9 | bd3c671 (skip-signal only) | head (plus the loss fix) |
|---|---|---|---|
| 1 producer | 410 / 413 | 403 / 403 | **540 / 538 (1.33x slower)** |
| 4 producers (slowest) | 1301 / 1321 | 987 / 975 | 996 / 1061 (1.27x faster) |

  A/A inside each version is within 2 %. The cost comes with 36afada: its second `peep` and fence run under the mutex
  with `sleeping` set on every worker pass, even when the first `peep` already found a due task and the worker will not
  wait. Likely mechanism (not profiled): a single producer then finds `sleeping` true and queues on the mutex to
  signal. The Linux VM was too noisy to decide (start 578-873, head 629-936 ns); the i9 run was not made. Single change
  that should recover it: when the first `peep` returns a task due at or before `now`, skip the lock/`sleeping`/second-peep
  block and walk at once (nothing sleeps, so there is no wake-up to lose); verify with this bench and the stress above.
- **Fence reasoning.** The worker side is right: `sleeping.store(true)` then the seq_cst fence (scheduler.h:336-343),
  then the reload and the late `peep`. If `add()`'s `sleeping` load misses that store, its fence precedes the worker's
  in S, so the late peep sees the wheel put. The comment's other half ("either add() sees `sleeping` and signals") is
  not what the code does: `add()` signals only if `next >= wakeup || next <= now`, where `next` is the atom value it
  loaded *before* its fence (scheduler.h:381-388). Because stash's put is release-only (not in S), `add()` can read a
  stale published time X with now < X < wakeup, see `sleeping`, and skip the signal, while the worker's CAS raised the
  atom to Y > wakeup and its late peep, ordered before `add()`'s fence, missed the put: the task waits until Y (up to
  30 s). The C++ model allows it; hardware needs the put to stay in the store buffer across a whole worker pass plus
  an early (spurious) worker wake, so it is not observable (none in 26.6 M adds, and TSan cannot model it). S1, non-blocking:
  move `add()`'s fence to right after `scheduler_queue.add()` (before the atom load); then the worker's raising CAS
  precedes the load in S, `add()` sees Y, lowers it and signals. A mutant of either fence is not detectable on x86 TSO.
- CI runs the soak (`scheduler_soak`, 300 000 adds, and the burst mode, 60 000) and the deterministic interleaving test
  (`SCHEDULER_TEST_HOOK`), one producer; the multi-producer TSan race (L2) is outside CI.
- Performance: the skip-signal change (02a72ea) is a clear win with several producers (1.3x above, 1.9x through the
  logger); the loss fix gives back a third with one producer (S2).

## allocators: BETTER WITH CONDITIONS (AL1)

- Allocator requirements, randomized (`alloc_probe.cc`, probe not kept; covered by `allocators:allocators_propagation`;
  ASan+UBSan and TSan, Linux VM): 200 rounds of allocators made by default construction, copy, move, copy-assignment and
  int->Big->double->int rebind chains; for every pair, `==`/`!=` equal "same family" both ways and across value types,
  rebind round trips compare equal, and 300 alloc/free steps per round free storage through a random equal allocator
  rebound there and back: OK. `std::list` splice between equal allocators, move, and map/set/forward_list churn
  (20 000 ops): OK, no ASan report.
- Mutant: converting constructor not sharing the family -> `test/pool.cc` fails (`back == a`, line 81).
- AL1 above is the one contract hole. H's CR2 is closed; CR3 is closed for copy-construction but reopened by
  copy-assignment.
- In flight: a `construct` perfect-forwarding fix (with `test/construct.cc`) was not on origin/main at 14:38; re-check
  pending (see Not run). It landed later as `allocators:7cdb0f8` (see Resolution). Main's
  `construct(pointer, const_reference)` copies on `allocator_traits::construct(a, p, std::move(x))` and does not compile
  for move-only types through the generic `allocator<T>` (pre-existing).

## fs: NOT YET (FS1)

- The rest of `copy_file` is right, read against fs.cc:313-433 and by probe: `DirCloser` closes the directory on every
  return, the source is closed when the destination open fails, short writes loop and fail with the error, EINTR is
  retried on read and write, a failing `close(dst)` is reported. The repo's fault tests (RLIMIT_FSIZE one chunk short,
  `/dev/full`, a FIFO under a 2 ms `SIGALRM`, fd-leak check) pass on the Linux VM.
- Pre-existing, not introduced: `d_type == DT_REG` skips every file on filesystems that report `DT_UNKNOWN`; a
  `file_name` that does not exist returns 0; the copy is always mode 0644.

## Review H findings

| H | status | evidence |
|---|---|---|
| CR1 scheduler loss | **closed** | 36afada; 0 lost in 26.6 M stress adds (TSan and -O2); start and mutant lose in seconds; one formal gap left (S1); costs 1.33x on 1-producer adds (S2) |
| CR2 rebind identity / noexcept / POC* | **closed** | randomized requirement probe; pool.cc mutant |
| CR3 shared pool across threads | **partial** | copy-construction gets a new pool and overlap detection exists; copy-assignment still shares (AL1) |
| CR4 lz4 allocation amplification | **closed in compressors, open in storage** | 8f57675 + 64 MB ASan cap over 624 k inputs; storage pins 0498bf5 (ST1) |
| CR5 per-thread lz4 scratch | open (note) | not documented (C2) |
| CR6 logger coalescing reorder | **closed** | 06a27d2, order.cc fails on the revert; finish() drains (0 lost in 60 runs on head, 60 on start); doc overclaim L1 |
| CR7 TZ cache vs /etc/localtime | open (note) | unchanged and undocumented; glibc behaves the same |
| CR8 copy_file short write / close | **closed** | 0b5f78e and its fault tests; but FS1 introduced by 14932b9 |
| CR9 storage read loop | **closed** | mutant caught by 5 tests; format and cross-reads identical |

## Probes

Where each probe of this audit lives now:

- `sched_stress.cc` and its mutant build: probe not kept; covered by `scheduler:test/soak.cc` (`scheduler_soak`,
  `scheduler_soak_burst`, `scheduler_soak_producers`).
- `lz4_fz.cc`, `lz4_lf.cc`: probe not kept; covered by `compressors:compressors_lz4_oneshot`, `compressors_corrupt` and
  `compressors:fuzz/fuzz_lz4.cc` (C1 is the gap left in the fuzz target).
- `bench_comp.cc` and its output: probe not kept; covered by `compressors:bench/bench_lz4.cc`, `bench_xxh32.cc` and
  `bench_oneshot.cc`.
- `stor_fmt.cc`: probe not kept.
- `alloc_probe.cc`: probe not kept; covered by `allocators:allocators_propagation`.
- `fs_self.cc`: probe not kept; covered by `fs:test/test.cc` `test_copy_file_same_file`.
- `lg_finish.cc`: probe not kept; covered by `logger:logger_order` (its `finish()` case). `lg_sync.cc`: probe not kept.
- `sched_add_bench.cc`: probe not kept; covered by `scheduler:bench/bench_post.cc` (its `add()` row).
- The Linux VM's format shim (enough of `<format>` for threadpool, exception.h, stringified and static-string under
  g++ 11's libstdc++), the exact-scratch compressors copy, the mutants, the hand-built logger start/head trees used on
  the M1 Pro and the logger build used for an M4 Pro rerun of `bench/lg.cc`: not kept.

## Not run

- Storage bench start vs head, the scheduler add bench on x86, and a quiet M4 Pro rerun of the logger bench: both timing
  hosts were busy for most of the audit. The logger and scheduler rows above come from the M1 Pro (a 3-core background
  load during the logger bench; load 2 during the scheduler bench).
- Logger and fs under TSan (they need `<format>`/`<source_location>` beyond the Linux VM shim; CI's TSan job covers them).
- The allocators `construct` fix re-check: origin/main still 3e3dfb2 at 14:38; re-check it when it lands (perfect
  forwarding, move-only types, `noexcept` spec, both tracking modes). It landed as `allocators:7cdb0f8`.

## Re-check FS1

2026-10-31 20:45-22:45. Subject: Kronuz/fs `d6d8bc2` ("Refuse copy_file onto the same file instead of emptying it"),
from a fresh clone. origin/main has since moved to `8848b49` (only `mkdirs` and `build_path_index` changed;
`copy_file` is untouched), so `d6d8bc2` is what was read and run. Runs: the M4 Pro under an exclusive timing hold
(about 3 minutes) and the Linux VM under a light hold; the macOS disk images were detached and removed afterwards.

**Ruling: CLOSED.** The destination is opened without `O_TRUNC` (`fs.cc:378`), both descriptors are `fstat`ed
(`fs.cc:386`), a matching `st_dev`/`st_ino` returns `-1` with both closed and nothing written (`fs.cc:392-396`), and
only a regular destination is `ftruncate`d, after the check (`fs.cc:400-402`, `EINTR` retried). Source bytes survived
every same-file spelling I could build, on macOS arm64 (APFS, HFS+) and Linux x86_64 (ext4, tmpfs), and plain copies,
including across filesystems, still copy.

Results (macOS arm64 = M4 Pro, APFS; Linux VM = Linux x86_64, clang 12, ASan+UBSan):

| check | fix `d6d8bc2` | pre-fix `fs.cc` (`487c401`) / mutant |
|---|---|---|
| the audit's `fs_self.cc` probe (dir onto itself, file onto itself, hard link) | rc -1 x3, source 39 -> 39 bytes | rc 0 x3, source 39 -> **0 bytes** ("SOURCE DESTROYED") |
| repo test `test_copy_file_same_file` (`test/test.cc:167`, run at `:415`) | passes on macOS and the Linux VM | revert: fails 22 checks on macOS, 19 on the Linux VM (the commit message's numbers) |
| mutant m1, truncate before the check | | fails 22 (macOS), 19 (Linux VM) |
| mutant m4, no `ftruncate` | | fails 1 (`test/test.cc:130`, the shorter-copy case) on both |
| mutant m3, no `S_ISREG` guard | | fails on the Linux VM (`test/test.cc:398-399`, the FIFO under `SIGALRM`); **survives on macOS** (`ftruncate` on a FIFO does not fail there) |
| mutant m6, inode only | | survives the repo test on both; **killed by my cross-filesystem probe** (below) |
| my `edge_fs1` probe, same filesystem | 33 cases, 0 failures (macOS); 0 failures, no sanitizer report (Linux VM) | `edge_pre`: 55 failures |
| `edge_fs1` TOCTOU stress, 3 swaps x 3 s | source damaged 0 times in 34,790 calls (macOS); 0 on the Linux VM | source damaged 5,183 / 2,658 / 8,226 times |
| `edge_fs1` cross filesystem | all pairs pass (below) | `edge_pre`: "symlink on the other volume to the source" empties the source in all 12 pairs (rc 0) |

`edge_fs1` is not kept: `fs:test/test.cc` `test_copy_file_same_file` covers the same-filesystem spellings (hard link,
symlink to the same file, directory onto itself); the cross-filesystem and TOCTOU cases are not in the repo test.
What `edge_fs1` covers (all refused with `-1`, source intact, no descriptor leak): `./d`, `d/../d`, `d//./`,
`e/../d`, absolute against relative; a symlink to the source file (relative, absolute, a three-link chain, in the same
directory) and to the directory (as source, as destination, both); a hard link in another and in the same directory;
case-folded `D`/`F` (APFS folds case here); NFC against NFD names (APFS treats them as one file); the macOS firmlink
spelling (`/proc/self/cwd` on the Linux VM); a read-only source onto itself. Controls that must copy, and do: `f` to `g`
in one directory, a 20000-byte destination replaced by the 5000-byte source, a symlink to a different file. FIFO
destination: the reader gets all 5000 bytes, the FIFO is still a FIFO, rc 0 (on macOS `ftruncate` on a FIFO does not
fail, which is why m3 survives there). A symlink to `/dev/null` as destination: rc 0,
`/dev/null` still a character device.

Cross filesystem. The M4 Pro's `/tmp` and home are one APFS volume, so I attached two APFS images and one HFS+ image
(`hdiutil`): 12 ordered pairs among the home volume and the three images, each copying over an existing file, back, a symlink on the other
volume to the source (refused), and a directory copy. All pass. One pair (HFS+ -> APFS) held files with the **same
inode number (43) on different devices**: the fix copied it (rc 0), the inode-only mutant refused it (rc -1), so the
`st_dev` half of the check is needed and present. On the Linux VM, `/home` (ext4) and the two tmpfs mounts (`/dev/shm`,
`/tmp`) give 6 ordered pairs, all pass; no tmpfs pair shared an inode number, so m6 survived there.

TOCTOU: none for FS1. The identity is taken from the two open descriptors, so no later change to either path can
point the truncate at the source: a descriptor's inode never changes, and two inodes never merge. The stress swaps
`e/f` between a link to the source and a different file while `copy_file` runs, in three variants; the source never
lost a byte, and the only effect of the race is the existing one (bytes written to an inode a rename has just
unlinked, rc 0).

Code read (what each line gives, so the table is not the only evidence):
- `fs.cc:378` opens the destination `O_CREAT | O_WRONLY`, no `O_TRUNC`. `fs.cc:386` `fstat`s both descriptors (both
  closed on failure). `fs.cc:392` refuses (`-1`, both closed) when `st_dev` and `st_ino` match, before anything is
  written. `fs.cc:400-402` `ftruncate`s only a regular destination, retrying `EINTR`. That is what the finding asked for.
- The identity comes from the open descriptors, so no path can change between the check and the truncate: swapping the
  destination path (symlink, hard link, rename) or the source after `readdir` cannot make the truncate hit the source,
  because a descriptor's inode never changes and two inodes never merge. I find no TOCTOU window for FS1. A rename
  over the destination after the open only sends the bytes to an unlinked inode (the pre-existing last-writer case).
- Spellings (`./`, `..`, `//`, absolute, symlink chain, hard link, firmlink, `/proc/self/cwd`, case folding) all reduce
  to one `(st_dev, st_ino)` pair by construction; `test/test.cc:167-287` lists them.
- Repo test: `ctest` passed 2/2 (`fs`, `fs_db_layout`) at `d6d8bc2` on the M4 Pro (Debug, `cmake -G Ninja`), and
  `test_fix` passed again under the exclusive hold and on the Linux VM under ASan+UBSan.
- The new behaviour is documented: `fs.hh:58-62`, `README.md`, `CHANGELOG.md` (a directory copy stops at the first
  failure, so a same-file match mid-directory leaves later files uncopied). `L_ERR` is a no-op unless the host
  defines `FS_TRACE_HEADER`, so the refusal is silent and only visible as `-1`.

Follow-ups (none blocks FS1):
- The repo test has no `st_dev` coverage: an inode-only comparison (m6) passes it on macOS and on Linux. My
  `edge_m6_ino_only` kills it only where two volumes hand out the same inode number (the APFS and HFS+ images did). A
  test with two `hdiutil` or tmpfs mounts would pin it; skipped when the filesystems do not collide.
- m3 (no `S_ISREG` guard) is caught only on Linux, by the FIFO-under-`SIGALRM` test (`test/test.cc:398-399`); the commit
  message's "fails the FIFO copy" holds there, not on macOS.
- `copy_file` returns `-1` silently unless the host defines `FS_TRACE_HEADER` (`L_ERR` is a no-op by default), and a
  directory copy stops at the first refusal, so files after a same-file match are not copied; both are documented
  (`fs.hh:58-62`, `README.md`, `CHANGELOG.md`).

Not run:
- The M1 Pro and the i9 (both unavailable), so macOS x86_64 and a second arm64 host were not run in this re-check; the
  commit message says the macOS x86_64 runner ran 22 same-file checks.
- TSan, benchmarks. ASan+UBSan ran on the Linux VM only; ASan hangs on the M4 Pro.

## Re-check AL1

**CLOSED.** No new finding. Three non-blocking notes (N1-N3 below).

Subject: allocators `e38f759` (fix) on `3e3dfb2` (audit head), main `ea0c5e6`. The construct forwarding is `7cdb0f8`;
`ea0c5e6` is the vector `push_back` benchmark on top of it. `git diff 3e3dfb2 ea0c5e6 -- allocators.h` changes code in
three places only: `propagate_on_container_copy_assignment` (`allocators.h:343`, now `false_type`; `:344-346` still
`true_type`, `true_type`, `false_type`) and the two `construct` templates; the rest is comments. From a fresh clone,
with the audit's `alloc_probe.cc` and `al1_leftovers.cc` (probes not kept; `allocators:test/propagation.cc` covers copy,
move and swap over the node containers) and two mutants (`pocca`, `soccc`). Hosts: Linux VM (clang 12 + g++ 11.2,
glibc 2.35, libstdc++; ASan+UBSan, TSan with clang only), M1 Pro (Apple clang 21, libc++; ASan+UBSan, TSan). Each run
was under an exclusive timing hold. CI at `e38f759` (run 41271878424) and `ea0c5e6` (41281017007) is green,
`linux-asan-ubsan` and `linux-tsan` included, with `allocators_pool`, `allocators_propagation` and (head)
`allocators_construct` passed in both.

**The audit's probe, part 3 (`e = d`, then two threads churn `d` and `e`).**

| build | `3e3dfb2` | `e38f759` | `ea0c5e6` |
|---|---|---|---|
| shares pool after `e = d` | 1 | 0 (M1 Pro) | 0 (M1 Pro, Linux VM) |
| ASan+UBSan, M1 Pro | UBSan abort, null member access in libc++ `list:604` (the corrupted free list) | clean, 0 | clean, 0 |
| ASan+UBSan, Linux VM clang 12 | 197,148 overlap detections, then a hang (240 s alarm) | not run | 0 detections, rc 0 |
| TSan, M1 Pro | race `pool_class::allocate`, `allocators.h:172`, 7 detections | clean | clean |
| TSan, Linux VM clang 12 (`setarch -R`) | race `allocators.h:172`, 99,838 detections | not run | 0 detections, no report |
| g++ 11 `-D_GLIBCXX_DEBUG -D_GLIBCXX_ASSERTIONS`, Linux VM | not run | not run | 0 detections |

**Revert the fix: the tests fail** (M1 Pro, Apple clang 21, `allocators.h:343` set back to `true_type` in a scratch copy).
- As shipped, `test/propagation.cc:103` and `test/pool.cc:69` stop the build (`static_assert` on the trait).
- With `static_assert` defined away (`-Dstatic_assert(...)=`) the behavioural checks fail on their own:
  `test/propagation.cc:123` (`shares(e.get_allocator(), e_alloc)`, plain and TSan builds) and `test/pool.cc:211`
  (`e.get_allocator() == e_allocator && ...`). So the tests bite on the sharing, not only on the trait.
- Second mutant, `select_on_container_copy_construction` returning `*this` (`allocators.h:383`): `test/propagation.cc:113`
  and `test/pool.cc:229` abort (copy-construction sharing, the CR3 half that was already closed).
- Head, unmodified: `allocators_propagation` and `allocators_pool` pass under ASan+UBSan and TSan on the M1 Pro and on
  the Linux VM, and with g++ 11 `-D_GLIBCXX_ASSERTIONS` on the Linux VM.

**What the fix leaves** (`al1_leftovers.cc`: every case below on all six node containers, `list`,
`forward_list`, `set`, `multiset`, `map`, `multimap`, unless it says otherwise). `ok-all` is clean (0 misuse detections,
0 check failures, no sanitizer report) under ASan+UBSan on the M1 Pro and the Linux VM, under TSan on the Linux VM
(clang 12, libstdc++), and with libstdc++ debug and assertion checks. The same program against the `3e3dfb2` header, and
against the `true_type` mutant, fails (check failures at `al1_leftovers.cc:112` and `:150`, plus the `allocators.h:172`
race under TSan).

1. **Moved-from container keeps the pool.** Confirmed, on libc++ and libstdc++: after `C b(std::move(a))`, `a` and `b`
   share the family. That is mandated, not a regression: the Allocator requirements make `A a(std::move(a1))` leave `a1`
   unchanged and equal to `a`, and the move constructor already copied the allocator at `3e3dfb2` (`allocators.h:369` at
   head; the user-declared copy constructor suppresses a move one). The documented rule (`README.md:84-86`,
   `allocators.h:313-315`) is correct and the hazard is real: using the moved-from container while the moved-to one is on
   another thread (reuse it; copy-assign into it; `a = {}` then reuse; `race-moved-0/1/2`) is a TSan race
   (`allocate` vs `allocate`/`deallocate`, `allocators.h:174-191`) and a SIGSEGV in a plain `-O2` build (M1 Pro, all three).
   The escape hatch the README names works: `a = C{}`, `a = std::move(fresh)` and `a.swap(fresh)` give `a` its own pool
   (hatch table, both standard libraries), and moving a container into a thread, re-pooling the original, then running
   both is clean under TSan and ASan. What does **not** re-pool (still shares): `a = fresh` (copy assignment, the
   AL1 case), `a = {}` (initializer-list assignment) and `a.clear()`. Not new: at `3e3dfb2` a copy-assignment into a
   moved-from container swapped in the source's allocator instead, which shared with the source; the fix trades one
   sharing for the one the move already made.
2. **Copy construction.** `select_on_container_copy_construction` returns a new family (`allocators.h:383-385`);
   copies handed to threads (closure capture, a `std::function` and its copy, `vector<list>` growth and copy) never
   share with the source or with each other, and run concurrently with it clean.
3. **Swap of unequal allocators.** `propagate_on_container_swap` is `true_type` (`allocators.h:345`, asserted in the
   probe and `test/propagation.cc:105`). Member `swap`, `std::swap`, ADL `swap`, swap with an empty container and with
   itself all hand the pools over with the nodes (identity checked through the free list); the swapped containers then
   run on two threads clean. libstdc++'s `-D_GLIBCXX_DEBUG -D_GLIBCXX_ASSERTIONS` allocator-equality check, which fires
   only when `propagate_on_container_swap` is false, did not.
4. **Nested containers.** `map<string, list<int, A>>`, `vector<list<int, A>>` (copy assignment shrinking and growing,
   growth by reallocation), `map<..., scoped_allocator_adaptor<A<pair>, A<int>>>` (the copy gets a new outer and a new
   inner pool, copy assignment keeps the target's; this also runs the forwarded `construct` of `7cdb0f8` with
   `piecewise_construct` and allocator arguments) and `map<string, vector<int, A>>` (the pool refuses arrays: the second
   `push_back` throws `bad_alloc` and leaves the map valid; copy and assign of one-element vectors work). No two inner
   lists across maps share a pool; three and four threads churning the copies are clean.

Notes (none blocks AL1):
- N1. `README.md:88-92` lists copying a container as safe across threads but not moving; only the sentence at `:84-86`
  covers it. One clause would close it: moving a container to another thread is safe only if the moved-from one is not
  used again or is re-pooled right away (before any other use: by reasoning, a `clear()` inside the move assignment of a
  non-empty moved-from container would return nodes to the still-shared pool; not run).
- N2. `a = {}` and `a.clear()` read like resets and are not: they keep the shared pool. The README says "move-assigning a
  fresh container", which is right; a half sentence naming `= {}` would stop the misreading.
- N3. Consequence of the fix, standard-conformant and not covered by the changelog: after `e = d` the two containers are
  no longer equal, so `splice`/`merge` between them is outside the container precondition (from memory, libstdc++'s
  `list::splice` checks allocator equality and aborts; not run).

Not run:
- g++ 11 TSan: `g++ -fsanitize=thread` crashes on `int main(){return 0;}` on the Linux VM (rc 139, glibc 2.35), so
  libstdc++ TSan means clang 12 over libstdc++ headers. TSan on the Linux VM also needs `setarch x86_64 -R` (the first
  TSan runs died with "unexpected memory mapping" and are not counted).
- The M1 Pro TSan `ok-all` run predates a fix of my own probe: it reported six races, all my shared `next` counter in
  `handoff_copy` (`al1_leftovers.cc:74`), none with an `allocators.h` frame; the fixed probe ran clean under TSan on the
  Linux VM only. `e38f759` itself ran on the M1 Pro only (the Linux VM ran head); `race-moved-*` on the Linux VM stopped
  at the first run, which hung to the 240 s alarm, so the plain-build crashes are the M1 Pro's.
- No i9 or M4 Pro runs, no benchmarks, `allocators_construct` only through CI.
