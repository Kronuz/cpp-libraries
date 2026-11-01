# Review H: cluster H performance commits (post-landing)

- Date: 2026-10-31. Kind: post-landing code review of the cluster H performance commits (read-only).
- Repos: compressors `0498bf5` (lz4 one-shots, XXH32), storage `cc36919`, logger `dc1fe62`, scheduler
  `02a72ea`/`bd3c671`, allocators `085331c`, fs `14932b9`.
- Machines: Apple M4 Pro (macOS arm64), a shared Linux x86-64 VM (gcc 11, clang 12). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| CR1 scheduler loses a task about once per 2M adds | closed | `scheduler:36afada` | `scheduler` (`test_add_between_peep_and_sleep`), `scheduler_soak_burst` |
| CR2 allocators rebind identity, `noexcept`, `propagate_on_container_*` | closed | `allocators:2fc537f` | `allocators_pool` |
| CR3 allocators copies share one unsynchronized pool | closed | `allocators:2fc537f`, `allocators:e38f759` | `allocators_propagation`, `allocators_pool` |
| CR4 lz4 decompress allocation amplification | closed | `compressors:8f57675`, `storage:7cabb43` | `compressors_lz4_oneshot` (98 KB of 3-byte blocks stay under 1 MB) |
| CR5 lz4 per-thread scratch kept for the thread's life | no change | `compressors:9bd24af` | - (documented in `compressors:docs/API.md`) |
| CR6 logger 1 ms coalescing reorders lines | closed | `logger:06a27d2` | `logger_order` |
| CR7 logger timestamp cache ignores `/etc/localtime` | open | - | - (open: the docs name only `TZ`; no commit references CR7) |
| CR8 fs `copy_file` short write and close | closed | `fs:0b5f78e` | `fs` (RLIMIT_FSIZE, `/dev/full` and FIFO cases) |
| CR9 storage `read(limit, args)` loop | no change | `storage:cc36919` | `storage` (the systems audit's mutant fails 5 of 8 CTest tests) |

The [systems audit](2026-10-31-audit-systems.md) re-checked every finding (its "Review H findings" table). CR3 was reopened there by
copy assignment (AL1) and closed by `allocators:e38f759`; the fs fix this review approved (`14932b9`) introduced FS1,
closed by `fs:d6d8bc2`. CR5 is the design (one 16 KB `LZ4_stream_t` and up to 1 MB of scratch per thread); the
audit asked only that it be documented (its C2).

## Verdict: APPROVE (landed), with one non-blocking correctness item to schedule (CR1) and two design notes.

No blocking finding. The lz4 rewrite is byte-identical to the stream classes in everything I threw at it.

## Blocking
None.

## Findings (non-blocking, ordered by weight)

- **CR1 scheduler (pre-existing, unfixed, ungated): a task is lost about once per 2M adds.** The commit message of
  bd3c671 says a burst test "drops a task for good about once per two million adds on the unmodified scheduler too"
  and then deletes the burst test instead of finding the cause. A lost scheduled task is a correctness bug in a
  library; the stronger test that would have exposed it is gone. Whether 02a72ea changes the rate is unmeasured.
  The new skip-signal logic itself reads correct to me (scheduler.h:322-326 `sleeping.store(true)` under the mutex
  then reload of `atom_next_wakeup_time`; add() scheduler.h:359-365 lowers the atom, then loads `sleeping`; both
  seq_cst, a Dekker pair, so one side always sees the other). Remaining suspects for the old loss, unverified:
  the worker's `compare_exchange_strong(next_wakeup_time, wakeup_time)` at ~scheduler.h:309 overwriting a lowered
  atom after `peep` missed a task added between peep and the CAS (ABA-ish on a time_point), and wheel `walk`/`clean`.
  Recommend: re-add the burst stress as a non-gating soak (nightly), run it under TSan, and bisect the loss.
- **CR2 allocators: rebind conversion starts a fresh pool, so `A<T>(A<U>(a)) != a`** (allocators.h, converting
  ctor `memory_pool_allocator(const memory_pool_allocator<_Tp1>&) noexcept { }`; the default member initialiser
  `std::make_shared` runs in it). The standard allocator requirement is that a rebound-and-back allocator compares
  equal; here it does not. Also: the converting ctor is `noexcept` but allocates (`make_shared` can throw, so
  `bad_alloc` would call `std::terminate`); every default-constructed or rebound allocator now costs a heap
  allocation; no `operator==` across different `T`; `propagate_on_container_*` and `is_always_equal` are not
  declared (defaults: false), so container swap of two lists with different pools is UB and move-assign falls back to
  elementwise moves. Works for std::list/std::map (tests, up to 5000), which is what the commit targets.
- **CR3 allocators: thread-safety unchanged on paper, but sharing makes it easier to violate.** Copies now share one
  unsynchronised pool (ARCHITECTURE.md says "not thread-safe"). A container copy (select_on_container_copy_construction
  = copy) now shares the pool with the original, so copying a list to another thread races on the free list. Before,
  the copy was broken outright, so this is not a regression, but document that a copied container must stay on one
  thread, or give the copy a fresh pool via `select_on_container_copy_construction`.
- **CR4 lz4 decompress: allocation amplification on untrusted input** (compressor_lz4.cc, `Scratch scratch(blocks *
  LZ4_BLOCK_SIZE)` in `decompress_lz4`). A ~98 KB input of 3-byte headers (blocks ~= 32768) makes a 64 MB
  uninitialised `new char[]` before any block is decoded (the cap is `max_estimate` 64 MB, then the old class). Pages
  are untouched so RSS stays small, but a service that decompresses attacker input per request reserves 650x its
  input in virtual memory and may fail a `new` with `bad_alloc` instead of `LZ4CorruptVolume`. The old class grew with
  actual output. Suggest the header walk also stop at the first block that cannot decode, or cap by something
  smaller than 64 MB for the up-front estimate. Not exploitable for memory corruption (see below).
- **CR5 lz4: per-thread 1 MB scratch retained for the thread's life** (`Scratch::cache`, thread_local `unique_ptr`).
  Harmless for a few threads, 1 MB x threads on a big pool; also `EncoderState` (LZ4_stream_t, 16 KB) per thread.
  Note only.
- **CR6 logger: the 1 ms coalescing can reorder lines within one wheel tick** (logger.cc `add`, `wakeup < now +
  kCoalesce`). Immediate async lines move to `now+1ms`; an explicit deferred line due in (now+1ms, ...) is not moved,
  so a line created earlier with an explicit due time 0.95 ms ahead can now fire after one with a due time 1.05 ms
  ahead. The commit message says order is unchanged; it is unchanged only among lines the shift applies to. Wheel
  resolution is 1 ms so this is within the quantum. Every async line also waits 1 ms, so a crash within 1 ms of a
  log call loses it (before: a signal-latency window). Document.
- **CR7 logger timestamp cache**: reads `getenv("TZ")` and compares a string per line (cheap) but is not invalidated by
  a change of `/etc/localtime` when TZ is unset (glibc's `localtime_r` does not re-read either; on macOS it does,
  so behaviour on macOS differs only in that rare case). Per-thread, no sharing, no race beyond the existing
  `getenv`/`setenv` one. Differential test against the frozen formatter is what makes this safe; I did not re-run it.
- **CR8 fs copy_file**: all the fixes are correct as read (O_TRUNC, `dst_fd` test, closes on error returns, dir
  closer). Remaining: the final `io::close(dst_fd)` result and partial-write handling (`bytes` from `io::write` is not
  compared to the count read: a short write truncates the copy silently, fs.cc ~line 392). `io::write` may be a full-write
  wrapper; I did not check.
- **CR9 storage read(limit,args)**: the new loop (storage.h:1633-1660) is correct as read: first chunk on the stack, a
  second read confirms the end (and runs the footer check), then reads straight into a doubling string; `resize(len)`
  at the end. If `read()` throws mid-way the partial string is discarded, same as before. `ret.size()*2` cannot be 0
  there because `ret` already has >= 2 KB. Not exercised by me beyond reading; tests exist in the commit.

## What I verified

- **lz4 byte identity and damaged input** (probe `fz.cc`, probe not kept; covered by `compressors:compressors_lz4_oneshot`,
  `compressors_corrupt` and `compressors:fuzz/fuzz_lz4.cc`; built as `fz_ub`: -O2 UBSan, run with MallocScribble +
  MallocGuardEdges on macOS arm64): 12000 random streams x 6 mutations (bit flip, truncation, random byte writes,
  trailing junk, deleted range) plus 60000 pure-garbage inputs, lengths around 0, 2 KB, 254 KB (the ring wrap),
  512 KB, 700 KB; kinds random, text, sparse. Compared `compress_lz4` with `LZ4CompressData` bytes, round trips, and
  `decompress_lz4` with `LZ4DecompressData` for (threw?, bytes). Result: 0 mismatches, about 48,000 damaged inputs
  rejected, same verdict and bytes as the old classes each time. By reading: output offsets are bounded (the
  decoder passes LZ4_BLOCK_SIZE as capacity; scratch is `blocks * 2048`; the ring is 256 KB + 2 KB and `roff <
  wrap_size` before each write), the header walk validates `cmpBytes` against `cmp_capacity` and remaining input
  before use, and `decBytes <= 0` throws. The wrap switch (`total < wrap_size` for decode, `off < wrap_size` for
  encode) matches the classes' ring semantics, because the dictionary content is the same bytes in `out`/`in`.
- XXH32: scalar-lane asm barrier is `__aarch64__`-only and does not change digests; the commit has a differential
  test; I did not rerun the benchmark.
- scheduler: reading above; the deterministic wake test replaces the stress.

## Not run

- ASan/TSan on the Apple M4 Pro: sanitizer binaries do not start there (a hello-world with `-fsanitize=thread`
  prints nothing; an ASan fuzz binary hung in dyld). The shared Linux x86-64 VM's toolchain (gcc 11, clang 12) has no `<format>`,
  so scheduler/logger/storage (threadpool.hh, exception.h) cannot be built there. An ASan+UBSan build of the lz4 fuzz
  with a shimmed exception header (same `fz.cc`) was started on the Linux VM and had not finished when this was
  written; ASan result: **unknown**.
- TSan on scheduler, logger, allocators; the logger differential test; storage tests; the scheduler burst soak;
  zstd/deflate (untouched by these commits); benchmarks.

## Probes

`fz.cc` (differential lz4 fuzz) and its builds `fz_ub` and `fz_asan`: probe not kept; covered by
`compressors:compressors_lz4_oneshot` (bytes and verdicts against the stream classes on damaged input, around the
256 KB wrap), `compressors_corrupt` and `compressors:fuzz/fuzz_lz4.cc`. `exc_shim.h` (the exception-header shim for the
Linux VM) and a scheduler checkout at bd3c671 with a TSan build that does not start on the M4 Pro: probe not kept.
