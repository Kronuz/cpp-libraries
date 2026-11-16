# Sync cost: does any caller need a cheaper-than-durable sync?

Question (faultlab F9 / D4): is a sync weaker than durable needed by any caller, or does batching hide the durable cost? Numbers only; no recommendation.

Host: macOS 15 (Darwin 24.6) x86_64 Intel, APFS, the internal SSD. Not run: Linux (no VM was free; the qemu VMs on 18762/18763 are Detent's and 18772/18774 strata's, left alone). Not run: arm64 macOS. The probe and interposer sources are in Xapiand `.scratch/sync-cost/` (`probe.cc`, `interpose.c`), not committed. Counts are one run each; the light jobs shared the host with each other, so wall times and rates in section 2 are contended and are not benchmarks.

## 1. Cost per call

`probe.cc`: append N bytes to one file, then one sync call; 150 calls per cell after 5 warm-up; per-call p50/p99. Job `261116-150517-107e27` (exclusive, 11.4 s). macOS has no `fdatasync`; completion maps it to F_FULLFSYNC there.

| Bytes | fsync p50 / p99 ms | F_BARRIERFSYNC p50 / p99 ms | F_FULLFSYNC p50 / p99 ms | F_FULLFSYNC vs fsync (p50) |
|---:|---:|---:|---:|---:|
| 4 KiB | 0.113 / 0.174 | 0.461 / 2.051 | 20.79 / 36.88 | 184x slower |
| 64 KiB | 0.145 / 0.599 | 0.520 / 1.868 | 20.82 / 25.25 | 144x slower |
| 1 MiB | 0.532 / 0.586 | 0.943 / 2.096 | 22.84 / 25.00 | 43x slower |

macOS `fsync` returns once the data reaches the drive's cache; it is not durable against power loss. F_FULLFSYNC is the durable call. The write itself is 0.01 to 0.3 ms.

## 2. Frequency under existing benchmarks

`interpose.c` is a `DYLD_INSERT_LIBRARIES` shim counting `fsync`, `fcntl(F_FULLFSYNC)` and `fcntl(F_BARRIERFSYNC)` calls and their time, in every thread of the process; no source was edited on any branch. It sees completion's PosixIO calls because they go through libc. Share = time inside sync calls over process wall (calls in several threads can overlap, so a share is an upper bound).

| Caller and command | Job | Wall s | fsync | F_FULLFSYNC | Barrier | F_FULLFSYNC per s | Time in syncs |
|---|---|---:|---:|---:|---:|---:|---:|
| journal: `journal_bench` (192 durable batches, 1/32/256 ops) at journal:8f3e410 | 261116-150924-33d8c1 | 26.6 | 198 | 591 | 0 | 22.2 | 22.3 s, 84% |
| strata: `kv_strata fillrandom --durability sync --batch 100` (sync1 row), strata:491a1bdc | 261116-150926-6ba536 | 15.7 | 307 | 373 | 0 | 23.8 | 13.0 s, 83% |
| strata: same, `--batch 1` | 261116-150926-6ba536 | 20.6 | 533 | 648 | 0 | 31.5 | 18.7 s, 91% |
| strata: `--durability wal --batch 1` (wal1 row) | 261116-150929-9c1519 | 0.77 | 7 | 9 | 0 | 11.7 | 0.37 s, 48% |
| Xapiand: RESTORE `/bench/?commit`, 20,000 docs, `.scratch/build-repin` x86_64 binary of 3 Nov | 261116-150932-02ba12 | 60.6 | 223 | 40 | 25 | 0.66 | 3.3 s, 5% |
| Xapiand: 300 single `PUT`, then a 15 s idle tail | 261116-151138-b4a62b | 17.7 | 173 | 30 | 20 | 1.7 | 1.6 s, 9% |

Per unit of work: journal 3.08 F_FULLFSYNC and 1 fsync per batch (a 1-op batch p50 was 126 ms contended, 62 ms alone in earlier measurement, three flushes of about 21 ms); strata sync1 about 5.2 F_FULLFSYNC per `--batch 1` operation (648 over 128 operations) and about 5 per 100-op batch (373 over 72 batches); Xapiand RESTORE 40 F_FULLFSYNC for 20,000 docs (one per 500 docs).

## 3. Share of wall time, F_FULLFSYNC against fsync

"All fsync" re-prices every F_FULLFSYNC at the fsync p50 of section 1 (0.12 ms) and leaves everything else as measured. It is arithmetic on the table above for a closed loop where the sync is serial with the work, not a second measurement; for the kv and journal rows the remaining wall is the benchmark's own loop.

| Caller | Measured sync share | Share if all fsync | Naive wall change | Already batches? |
|---|---:|---:|---:|---|
| journal | 84% | 8% | 26.6 to 4.7 s (5.6x faster) | Yes: one durable flush set per append_batch; 256-op groups give 256x the ops per flush (p50 batch time unchanged) |
| strata sync1, batch 100 | 83% | 17% | 4.8x faster | Yes: `sync_files` makes a commit's data files one device flush, still about 5 F_FULLFSYNC per commit |
| strata sync1, batch 1 | 91% | 27% | 8.1x faster | Same mechanism; one op per commit, so no amortization over operations |
| strata wal | 48% | 6% | on a 0.77 s run: noise | Writes not synced per op (9 F_FULLFSYNC for 100,000 ops) |
| Xapiand RESTORE | 5% | 3% | 1.02x | Yes: commit-level, 40 flushes for 20,000 docs |
| Xapiand PUT | 9% | 4% | 1.06x | WAL sync debounced (below); 30 F_FULLFSYNC for 300 PUTs |

## 4. Xapiand's fsyncher (src/xapiand_fsyncher.h)

Code read at Xapiand master (f920f9042 plus `opts.cc` defaults).

| Item | Value |
|---|---|
| (a) syncs requested per second by callers | Not measured: the requests are calls to the WAL's `_async_fsync` hook (wal.cc:108, 117), which no libc interposer sees and which cannot be counted without a source edit. The upper bound is the number of WAL commits |
| (b) syncs issued after the debounce | 0 observed on threads named `FS*` (the fsyncher's pool, `"FS{:02}"`) in both Xapiand runs above, including a 15 s tail after 300 PUTs: the fsyncher path was not exercised. The syncs in section 2 come from other threads (commit and storage paths). Thread-name attribution is the only evidence; a binary of 3 Nov, not current master |
| (c) debounce window | Per fd key: first request fires after 500 ms (`FSYNCHER_DEBOUNCE_TIMEOUT`); each further request moves it to now+800 ms (`..._BUSY_TIMEOUT`), but never past a forced deadline drawn once from 2500 to 3500 ms after the first request. After a sync fires the key is throttled 1000 ms (`FSYNCHER_THROTTLE_TIME`). An acknowledged write can wait 0.5 s when idle, 2.5 to 3.5 s under steady load |
| Ack before or after sync | Before. The WAL opens with `STORAGE_ASYNC_SYNC` (wal.cc:62); `do_sync` hands `(fd, full)` to the hook and `commit()` returns (storage.h:148, 1205-1212). The comment at storage.h:148 says never to use it for a record acknowledged to a client |
| Strength | `STORAGE_FULL_SYNC` is not set for the WAL, so the hook runs `fsync` (`full_fsync` false), which on macOS is the cache-level fsync of section 1, not F_FULLFSYNC |

## Magnitudes

1. F_FULLFSYNC costs 21 to 23 ms per call on this Mac and fsync 0.1 to 0.5 ms: 43x to 184x.
2. journal and strata's sync rows spend 83% to 91% of wall in F_FULLFSYNC even though they batch; they issue 22 to 32 per second, one every 30 to 45 ms.
3. Xapiand's measured paths spend 5% to 9% in syncs; the fsyncher is the only caller that acknowledges before sync, and it was not exercised here.
4. Linux and arm64 costs are not measured, so the table says nothing about them.
