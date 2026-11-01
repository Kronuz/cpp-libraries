# Survey H: systems / concurrency / IO

- Date: 2026-10-30. Kind: performance survey of the systems cluster (compressors, storage, logger, threadpool,
  atomic-shared-ptr, io, fs, task, allocators; scheduler, stash, completion, journal, strata and prospect by reference),
  read-only; libraries were not modified.
- Repos: `main` of each library when the survey ran: compressors `dc4474b`, storage `e4c5746`, logger `ce27b90`,
  threadpool `ab02e17`, atomic-shared-ptr `9a2582e`, io `3893d47`, fs `ce16118`, task `9a85e89`, allocators `e8fb173`,
  scheduler `ae3f0f9`, stash `2e2b75f`.
- Machines: Apple M4 Pro (macOS arm64, 14 cores, Apple clang 17, `-O2`). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| H-W1 compressors lz4 one-shots | landed | `compressors:0498bf5`, `compressors:8f57675` | `compressors_lz4_oneshot` (bytes and verdicts against the stream classes); `compressors:bench/bench_lz4.cc` |
| H-W2 compressors XXH32 | landed | `compressors:0498bf5` (AArch64), `compressors:533bee4` (SSE2) | `compressors_xxh32`; `compressors:bench/bench_xxh32.cc` |
| H-W3 storage lz4 read/write (via compressors) | landed | `storage:cc36919` | `storage` |
| H-W4 logger producer (signal per line) | landed | `scheduler:02a72ea`, `logger:dc1fe62`, `logger:c7332d6` | `logger_producer`, `logger_order`; `logger:bench/lg.cc` |
| H-W5 logger consumer timestamp | landed | `logger:dc1fe62` | `logger_timestamp` (differential against the frozen formatter) |
| H-M1 zstd one-shot decompress | landed | `compressors:62e6b62`, `compressors:fe0e712` | `compressors_oneshot`; `compressors:bench/bench_oneshot.cc` |
| H-M2 zstd one-shot compress | landed | `compressors:62e6b62` | `compressors_oneshot` |
| H-M3 deflate one-shot decompress | landed | `compressors:62e6b62` | `compressors_oneshot` |
| H-M4 storage zstd reads | landed | `storage:5106e67` | `storage` |
| H-M5 threadpool `enqueue` on trivial tasks | landed | `threadpool:12f1516` | `pool_diff`, `pool_stress`, `small_task`; `threadpool:bench/enqueue_bench.cc` |
| H-M6 allocators `vector` push_back | landed | `allocators:7cdb0f8` | `allocators_construct`; `allocators:bench/bench.cc` |

H-M6 landed as a different fix from the guess in the row. The [second-wave survey](2026-10-30-survey-second-wave.md)
measured `vector<int>` as a tie and traced the 2x to `construct(pointer, const_reference)` copying instead of moving,
which shows on `vector<std::string>`; `allocators:7cdb0f8` forwards `construct` (string rows 1.9-2.4x -> 1.00-1.05x of
`std::allocator` on the M4 Pro, `vector<int>` within its spread, allocators `CHANGELOG.md`). The bugs this survey found
have no row: the `std::list` heap corruption was fixed by `allocators:085331c` (tests through `std::list` and
`std::map`), the pool copy and equality hazard by `allocators:2fc537f`, and the fs `copy_file` hazards by `fs:14932b9`
and `fs:0b5f78e`; [review H](2026-10-31-review-h-systems.md) and the [systems audit](2026-10-31-audit-systems.md) follow
them.

## Method

Benchmarks: harnesses written for this survey (`comp.cc comp2.cc tp.cc lg.cc asp.cc stor.cc alloc.cc iob.cc`).
`stor.cc`'s raw `pwrite`/`pread` plus LZ4/zstd rows are now the "raw" rows of `storage:examples/bench.cc`
(`storage_bench`), and `alloc.cc`'s pool against `std::pmr` is `allocators:bench/compare_pmr.cc`
(`allocators_compare_pmr`). The rest were not kept; the repos' own benches cover the rows that landed:
`compressors:bench/bench_lz4.cc`, `compressors:bench/bench_xxh32.cc`, `compressors:bench/bench_oneshot.cc`,
`logger:bench/lg.cc`, `threadpool:bench/enqueue_bench.cc`, `allocators:bench/bench.cc`.
Every row was timed under an exclusive timing hold. "A/A spread" is max/min over 5 repetitions of the same binary
in the same run (not a separate A/A pair), so a ratio inside that spread is a tie. Ratios are
`ours / comparator`, so above 1.0 means ours is slower. Libraries were not modified. Comparator results were
checked equal to ours where the output is comparable (round trips for the codecs, same digest for XXH32,
same bytes for the lz4 prototype); rows without a check say so.

## Summary table

| library | workload | ours | best comparator | ratio (spread) | diagnosis | est. win | effort | verdict | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| compressors (lz4) | `decompress_lz4`, 256 B random | 1420 ns | `LZ4_decompress_safe` 7.8 ns (raw block; different framing) / byte-identical prototype 63 ns | 22x vs prototype (1.02) | per call: 256 KB ring buffer zeroed by `make_unique<char[]>`, `LZ4_createStreamDecode`, per-block `std::string`, XXH32 on every block | 5-20x small and incompressible; 1.6-2x text | S | **CLEAR WIN** | H-W1 |
| compressors (lz4) | `compress_lz4`, 256 B text | 1780 ns | byte-identical prototype 431 ns | 4.1x (1.07) | same fixed cost, plus the XXH32 digest nobody reads | 4x small, 2-3.4x random, 1.2x text | S | **CLEAR WIN** | H-W1 |
| compressors (lz4) | `compress_lz4` / `decompress_lz4`, 1 MB random | 441 us / 251 us | prototype 222 us / 55 us | 2.0x / 4.6x (1.02 / 1.03) | per-block string + memcpy + XXH32 (179 us per MB) | 2-4.6x | S | **CLEAR WIN** | H-W1 |
| compressors (XXH32) | lib streaming XXH32 over 1 MB, 2 KB chunks | 179 us | upstream `XXH32` 86 us (same digest, checked) | 2.1x (1.05) | scalar 4-lane loop the compiler does not vectorize; upstream's is 2x faster | 2.1x on every checksum (lz4 stream, storage footers) | S | **CLEAR WIN** | H-W2 |
| compressors (zstd) | `decompress_zstd`, 64 KB random | 3254 ns | `ZSTD_decompress` 742 ns | 4.4x (1.04) | zero-filled `resize`, then the iterator `append`s a second copy | 3-4x on stored/incompressible; text is a tie (1.04) | S | maybe | H-M1 |
| compressors (zstd) | `compress_zstd`, 1 MB random | 127 us | `compress_zstd_into` 92 us / `ZSTD_compress` 95 us | 1.34x (1.09) | bound-sized zero-filled string, per-call context | 1.3x on incompressible; text is a tie | S | maybe | H-M2 |
| compressors (deflate) | `decompress_deflate`, 256 B / 1 MB random | 252 ns / 131 us | `uncompress` 53 ns / 69 us | 4.8x / 1.9x (1.03 / 1.27) | `inflateInit` per call, copy, zero-fill | small absolute | S | maybe | H-M3 |
| compressors (deflate) | `compress_deflate`, all sizes | 36.8 us at 4 KB | zlib `compress2` 36.6 us | 1.01 (1.03) | zlib-bound | none | - | already good | - |
| storage | `read()` of one lz4 record, 1 KB / 16 KB / 256 KB | 3.15 us / 15.0 us / 200 us | pread + `LZ4_decompress_safe` 0.59 / 5.4 / 81 us | 5.3x / 2.8x / 2.5x (1.04 / 1.05 / 1.07) | `storage_decompress` goes through `decompress_lz4` (above) plus `read()` copies in 2 KB `std::string` chunks | 2.5-5x lz4 reads | S (inherits compressors fix; plus one chunk copy) | **CLEAR WIN** (via compressors) | H-W3 |
| storage | `write()` of one lz4 record, 1 KB / 256 KB | 3.9 us / 445 us | `LZ4_compress_default` + pwrite 2.5 / 269 us | 1.6x / 1.65x | `compress_lz4` overhead (comparator pays a syscall per record, storage batches) | ~1.5x | S | **CLEAR WIN** (via compressors) | H-W3 |
| storage | zstd read / write, 1 KB to 256 KB | 3.7 us ... 232 us / 5.4 ... 484 us | pread + `ZSTD_decompress` 2.5 ... 160 us / `ZSTD_compress` + pwrite 5.3 ... 406 us | read 1.45-1.5x (1.03-1.04); write 1.0-1.19x | read: decompress copy + 2 KB chunking; write: codec-bound | 1.4x on reads | S | maybe | H-M4 |
| logger | `L_INFO` producer cost, 1 thread, no I/O sink | 392 ns | spdlog-style sync (fmt + mutex + no-op sink) 29 ns; `fmt::format_to` 24.5 ns | 13.5x (1.06) | `make_shared<Logging>` (about 200 B, string, `exception_ptr`, `source_location`), 3 clock reads, stash insert 25% of producer samples, `condition_variable::notify_one` on every line 23% | producer 390 -> about 250 ns | M | **CLEAR WIN** (producer notify; consumer below) | H-W4 |
| logger | `L_INFO`, 4 producer threads | 1015 ns | sync 444 ns (mutex contended) | 2.3x (1.23) | same, plus `notify_one` contention | about 2x | M | see above | H-W4 |
| logger | consumer (LOG thread) per line | about 20% in `localtime_r` -> `getenv("TZ")`, 6 `snprintf` calls to format the timestamp | one cached UTC offset per second, integer formatting | profile only | per-line `localtime_r` and `snprintf` | about 2x sustained drain rate | S | **CLEAR WIN** (profile; not A/B timed) | H-W5 |
| logger | `L_DEBUG` filtered out | 1.3 ns | - | - | one compare against the level | - | - | already good | - |
| threadpool | `ThreadPool::enqueue`, 4 producers x 100k trivial tasks, 4 workers | 162 ns/task | mutex + condvar naive pool 76 ns; `asio::thread_pool` 165 ns | 2.1x vs naive (1.09); 1.0x vs asio | `std::function` per task, `blocking_concurrent_queue` semaphore signal per enqueue, `_enqueued` RMW | up to 2x on trivial-task floods | L | maybe (the repo's `WorkPool` research already targets this) | H-M5 |
| threadpool | `ThreadPool::enqueue`, 1 producer x 100k | 187 ns/task | naive 112; asio 250 | 1.7x vs naive; 0.75x vs asio | same | | | maybe | H-M5 |
| threadpool | future round trip | 6.9 us | asio `post` + promise 6.35 us; `std::async` 13.3 us | 1.09 vs asio (1.05-1.11); 0.52 vs `std::async` | wake latency dominates | none | - | already good | - |
| atomic-shared-ptr | `load()`, 1 thread | 7.3 ns | per-object spinlock 3.5 ns; mutex 5.9 ns | 2.1x vs spinlock (1.1) | Apple libc++ lacks P0718, so the wrapper is the free `std::atomic_load` functions: a global mutex pool | 4 ns | - | not worth it | - |
| atomic-shared-ptr | `load()`, 2 / 4 / 8 threads | 22 / 123 / 165 ns | `std::mutex` per object 20 / 97 / 128 ns | 1.1 / 1.3 / 1.3x (1.06) | refcount cache-line bouncing dominates for everyone; the spinlock collapses (2347 ns at 8) | none available without a different design (hazard pointers) | L | not worth it | - |
| io | `io::pread` / `io::pwrite` 64 B to 1 MB, `open`+`close` | 384 ns ... 38 us | raw `::pread` / `::pwrite` | 0.93-1.10 (1.01-1.16) | thin wrapper, trace macros compile out | none | - | already good | - |
| fs | `normalize_path` | 50 ns | `lexically_normal` 160 ns | 0.31 (1.09) | single pass, no allocation per component | ours is faster | - | already good | - |
| fs | `exists` | 855 ns | `::stat` 864, `std::filesystem::exists` 881 | 0.99 | syscall-bound | none | - | already good | - |
| fs | `copy_file` 64 MB, 4 KB buffer | 33.6 ms | `cp -c` 30.5 ms (clone fallback) | 1.1 (1.48) | 4 KB read/write loop; a larger buffer or `fcopyfile` would help, but the timing is noisy | about 1.5x possible | S | not worth it | - |
| task | no-op task create + await + destroy | 9.8 ns, 0 allocations | none (no comparator for a coroutine task) | - | the repo's own gate bench | - | - | already good | - |
| allocators | `std::list<int, memory_pool_allocator<int>>`, 1000 pushes | **crashes** (heap corruption) | `std::list<int>` 13.1 us | void | see hazards | - | - | BUG, not perf | - |
| allocators | `std::map` churn (insert n, erase n/2, insert n/2), 1000 / 100000 nodes | pool 76.0 us / 17.3 ms | malloc 100.1 us / 19.4 ms; `pmr::unsynchronized_pool_resource` 88.8 us / 18.7 ms | pool 0.76 / 0.89 of malloc; 0.86 / 0.92 of pmr (spread 1.04-1.06) | free-list reuse of fixed nodes; already ahead of malloc | none | - | already good | - |
| allocators | `std::list<int>` build + destroy 1000 / 100000 nodes | pool unusable (crash) | malloc 13.0 us / 1.44 ms; `pmr::monotonic_buffer_resource` 3.0 us / 0.32 ms; pmr pool 4.9 us / 0.46 ms | pmr 4.3x / 4.5x faster than malloc | the pool cannot be measured here | - | - | blocked by the bug below | - |
| allocators | `vector<int, allocator<int, vanilla_allocator>>` push 1e5 | 65.6 us | `std::vector<int>` 31.8 us | 2.06x (1.10) | guess: custom `construct`/`destroy` members stop libc++ using memcpy on growth; not profiled | 2x on trivial element types | S | maybe | H-M6 |
| scheduler, stash | arming timed tasks, spread keys, 14 threads | `stash:bench/RESULTS.md`: p99 1.4-1.8 us against 65 us-1.2 ms for a locked heap and Asio `steady_timer` | asio::steady_timer, mutex + heap | not re-run | the sparse wheel is already the comparison | - | - | already good (not re-run) | - |
| completion, journal | `journal_bench` append batches | fsync-bound by construction | raw `pwrite` + `F_FULLFSYNC` | not run | the cost is the device flush, not the library | - | - | not worth it (code read only) | - |
| strata, prospect | their own benches against RocksDB, Lucene, tantivy, xapian | not re-run | see `docs/perf` in each repo | - | known open items are in `prospect:docs/perf/query-gap-merged.md` (about 300 ns vs 90 ns per touched block, a format-13 question) | - | - | covered by those repos' own performance work | - |

## CLEAR WINS in detail

### 1. compressors: `compress_lz4` / `decompress_lz4` (and everything on top: storage)

Evidence (`comp.cc`, `comp2.cc`, prototypes not kept; ours vs a prototype that emits the same bytes, spread 1.01-1.09):

| input | compress ours / proto | decompress ours / proto |
|---|---|---|
| 256 B text | 1780 / 431 ns (4.1x) | 1449 / 93 ns (15.6x) |
| 256 B random | 1609 / 382 ns (4.2x) | 1420 / 64 ns (22x) |
| 4 KB random | 2935 / 861 ns (3.4x) | 2305 / 366 ns (6.3x) |
| 64 KB random | 27.3 / 11.6 us (2.4x) | 18.4 / 3.6 us (5.1x) |
| 64 KB text | 81.0 / 63.6 us (1.27x) | 34.3 / 19.9 us (1.72x) |
| 1 MB random | 441 / 222 us (2.0x) | 251 / 55 us (4.6x) |
| 1 MB text | 1517 / 1246 us (1.22x) | 538 / 331 us (1.63x) |

The prototype is `fast_compress` / `fast_decompress` in `comp2.cc` (prototype not kept): one thread-local `LZ4_stream_t`,
2 KB blocks straight from the input into the output string with `LZ4_compress_fast_continue`, the same 2-byte length
prefix, no XXH32, no ring buffer copy. Its output was byte-identical to `compress_lz4` for every input up to 256 KB and
for 1 MB random, and **not** identical for 1 MB text (the ring buffer wraps at 256 KB and the dictionary seen
after the wrap differs); the stream still decodes with the library's decoder in all cases.

- Start files: `compressors:compressor_lz4.h` (`compress_lz4`, `decompress_lz4`, `LZ4BlockStreaming`), `compressor_lz4.cc` (`LZ4CompressData::init/next`, `LZ4DecompressData::next`), `xxh32_stream.h`.
- Single biggest change: make the one-shot `compress_lz4(string_view)` / `decompress_lz4(string_view)` bypass the iterator classes: no `make_unique<char[]>` zeroing of the 256 KB ring, no per-block `std::string`, no XXH32 update (the digest is only reachable through `get_digest()` on the class, which the free functions never expose), output appended directly.
- Must stay identical: the LZ4 framing on disk (2-byte block length then the block, 2 KB blocks, dependent blocks), so records written by old builds decode and new records decode on old builds. Because ring wrap changes the dictionary at 256 KB, either replicate it (`LZ4_loadDict`/save at the same offsets) or cap the fast path at 256 KB and keep the class for larger input; test with a corpus above 256 KB. Keep the `LZ4CompressData` / `LZ4DecompressData` class API and `get_digest()`.
- Prototype caveat: `fast_decompress` sizes its output from the input and would break the dictionary pointer on regrow; the real one needs the decompressed size or a chunked output.

### 2. compressors: XXH32

`compressors::XXH32_*` takes 179 us per MB (5.9 GB/s) against upstream `XXH32` at 86 us (12 GB/s), digests equal
for all sizes tested (a mismatch would have printed `XXH MISMATCH`; none did). It is on the critical path of the lz4
stream, of the storage footer and `bin_hash` (every record read and written) and of the v2 header checksum.

- Start file: `compressors:xxh32_stream.h` (`XXH32_update` main loop).
- Change: process the 16-byte stripe as four independent lanes with the multiply and rotate written so the compiler keeps the lanes in registers, or use NEON for the four lanes; keep the one-shot path separate from the buffered carry.
- Must stay identical: the digest for every length and seed, and the streaming state layout if `XXH32_state_t` is public (it is in namespace `compressors`, so treat the struct as ABI).

### 3. storage read/write (inherits 1 and 2)

`storage_decompress` / `storage_compress` call `decompress_lz4` / `compress_lz4`, so lz4 records pay the fixed cost above:
read of a 1 KB record 3.15 us against 0.59 us for pread + `LZ4_decompress_safe` (5.3x), 2.5x at 256 KB, write 1.6x. Zstd
records are within 1.0-1.5x. Separate small item: `Storage::read()` hands the record out in `LZ4_BLOCK_SIZE` (2 KB)
chunks and the convenience `read()` builds each with `ret += std::string(buf, n)` (one allocation and two copies
per 2 KB; `storage.h` around line 1633).

- Start files: `storage:storage.h` (`storage_decompress`, `read(uint32_t, void*)` convenience overload).
- Change: fix compressors first; then let `read()` size the string to `_record.size() - _record_offset` and copy once.
- Must stay identical: the on-disk record layout and footer checksum values, the chunked `read(buf, size, ...)` semantics for streaming consumers.

### 4. logger

Producer side, 1 thread, no-op handler: 392 ns per `L_INFO` against 29 ns for the sync pattern and 24.5 ns for
`fmt::format_to` (`lg.cc`, probe not kept; covered by `logger:bench/lg.cc`; `L_DEBUG` filtered out is 1.3 ns).
4 producers: 1015 ns each. A `sample` profile of the
producer (531 samples in `main`): `Logging::add` 357, of which stash insert 135 and
`std::condition_variable::notify_one` 124 (a `psynch_cvsignal` syscall for every line); format and message
construction about 110; `Logging` object allocation and three `steady_clock::now()` reads the rest. Consumer (LOG thread,
512 samples in `BaseScheduler::operator()`): `localtime_r` 122 (106 of them in `getenv_copy_np`, macOS re-reads `TZ`
on every call), then about 6 `vsnprintf` calls for the timestamp gradient (about 150), `Logging::clean` and string appends.
I did not A/B-time a fix, so the win sizes are estimates from the profile.

- Start files: `logger:logger.cc` (`Logging::add` at line 560, `Logging::operator()` at 620-700, `hooked_timestamp`), `scheduler:scheduler.h` (`BaseScheduler::add`, the notify).
- Changes, biggest first: (a) skip the `notify_one` when the LOG thread is already awake or its wake time is not later than the new item's (needs a flag in `BaseScheduler`, so it is a scheduler change and affects every scheduler user); (b) cache the local UTC offset per whole second and format the timestamp with integer code instead of `snprintf`; (c) read the clock once per call and reuse it for `created_at`, `wakeup` and the `will_schedule` test.
- Must stay identical: log line text and timestamp format, ordering by wake time, backpressure and drop counting, the `Logger`, `LogHooks` and `LogConfig` surfaces, behavior across a `TZ` change (invalidate the cached offset when the hook or `TZ` changes).

## Maybes

- **threadpool**: the naive mutex + condvar pool moves trivial tasks about 1.7-2.1x faster than `ThreadPool::enqueue` and ties `asio::thread_pool` at 4 producers. Not profiled, so the cause is a guess (type-erased `std::function` plus the semaphore signal per enqueue in the moodycamel blocking queue plus `_enqueued`). Real tasks rarely cost 100 ns, so the win is only for task floods. The repo's `research/` and `WorkPool` target this; `ThreadPool` is used by the scheduler and logger, so any change is a shared hazard.
- **zstd / deflate one-shot decompress** and **zstd compress**: a zero-filled `std::string::resize` plus a second copy through the iterator: 3-4x on incompressible data, ties on text. Small internal change; best done with the lz4 fix.

## Compat hazards and bugs found

- **allocators: `std::list<int, memory_pool_allocator<int>>` corrupts the heap** (Apple clang 17 libc++, `-O0` and `-O2`). 1 element works; 10 or more elements abort inside `malloc` (`EXC_BREAKPOINT`). `std::map` through the pool works up to 1000 elements. The README example uses 3 elements. The tests in `test/test.cc` use the allocator directly with `long` and never through a container. Root cause not isolated (ASan hangs at start-up on the Apple M4 Pro, so no report); `alloc_bug.cc N WHICH` reproduced it (probe not kept; covered by `allocators:allocators_pool`). Treat the pool's rows as void until a developer fixes it.
- `memory_pool_allocator` copy and equality: `operator==` compares `this` addresses, and the implicit copy copies the deque and the free-list head, so a copied allocator owns a free list that points into the original's storage. Read from the code, not tested.
- **fs `copy_file`**: opens the destination with `O_CREAT | O_WRONLY` and no `O_TRUNC` (a shorter copy over a longer file leaves the old tail); the destination open failure check tests `src_fd` (`fs.cc` line 370); early error returns leak both descriptors and the `DIR*`. Read from the code, not tested.
- **logger**: after `Logging::finish()` the scheduler refuses new lines and every routine `L_INFO` silently becomes a synchronous inline write (my first benchmark run measured this by mistake; the 700 ns rows were discarded). Worth a documented contract or a sticky "stopped" log line.
- **atomic-shared-ptr**: on Apple libc++ `is_lock_free()` is false and every `load` takes a global mutex; consumers must not assume wait-free reads. `sizeof` is 16.
- **compressors**: the lz4 wire format is the library's own (2-byte length framing, 2 KB dependent blocks), not LZ4 frame; any speedup must keep the bytes. `XXH32_state_t` is exposed in namespace `compressors`.
- `ThreadPool` and `Scheduler` are shared by logger, stash users and Xapiand-era callers; the thread-policy enum (`ThreadPolicyType`) is part of the surface.
- Active development: strata, prospect, completion, journal, storage and task were not changed or deeply benchmarked here; storage is the only one with a clear lead (it inherits the compressors fix).

## LESSONS

The lessons of this survey are in [LESSONS](../LESSONS.md): [compressors](../LESSONS.md#compressors),
[logger](../LESSONS.md#logger), [allocators](../LESSONS.md#allocators), [threadpool](../LESSONS.md#threadpool).
These four are not written there:

- Copying a result out of an iterator into the caller's string (`append(*it)`) doubles the memory traffic that a direct decode into the destination avoids; decompressors that know the output size should write into the final buffer.
- A "wrapper" over the standard library (`atomic_shared_ptr`, `io::pread`) that adds no state costs nothing, and the measurements say so: do not optimize it, make it retire to the standard type when the toolchain catches up.
- Test an allocator through the containers it is meant for, at sizes past a handful of elements; a direct unit test of `allocate` and `deallocate` missed a heap corruption.
- Benchmarks that stop a worker mid-run (`finish()`) measure the fallback path; check that the path you think you time is the one that runs (the first logger numbers were synchronous).
