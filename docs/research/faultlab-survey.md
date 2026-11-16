# faultlab survey (2026-11-16)

## 1. Crash models: four, not two

| Model | Granularity | Survives a crash | Namespace / rename | Barriers | Media faults | Enumeration |
|---|---|---|---|---|---|---|
| storage CrashIO (test/crashio.h:34-106, test_crash.cc:85-99) | op K applied whole or its first 512 B only (test_crash.cc:173) | every earlier write, always: fsyncs are logged (crashio.h:21,102) and never read by `reconstruct` | none: create is instant (crashio.h:35-47), no rename/unlink/dir sync | none (fsync = no-op) | none (bit rot and truncation are hand-edited images, test_crash.cc:186-301) | every log prefix x {0, 512} (deterministic) |
| strata faultfs (include/strata/core/faultfs.hh:1-60, crash() ~250) | each 512 B sector old/new; zeros past durable size; size old or new | only synced bytes for certain; fault::keep models Linux failed-sync (hh:60-70) | create/replace/remove replayed in order, survive per coin until sync_directory; rename atomic | order_files_and_directory epochs, chained (hh:11-24) | EIO / bit-flip reads (media), ENOSPC, short writes, damaged writes, failed syncs | power_off_after(n) + mutations() = every point; crash(seed) = random torn state; tests loop 50-512 seeds |
| journal MemoryIO (journal/include/journal/memory_io.h:30-100) | 512 B sectors, kept or not (random) | durable + pending sectors | durable_names changes at sync_directory; replace/remove logged | none (sync = durable) | none | Disk::cut tick throws PowerLoss at op N: every point; seeded sectors |
| Detent recorder (Detent/tests/detent_relay/test_relay_mirror_crash.cc:1-150, 320-355) | whole files; no tearing | per inode staged (fsync) vs durable (device flush; Linux fsync = durable) from the REAL PosixIO via replace_sync_calls | staged vs durable directory; variants Entries{Durable,All} x Data{Truncate,Zeros} | models macOS fsync/F_BARRIERFSYNC/F_FULLFSYNC as observed | none | snapshot after every primitive (hook labels), plus a nested cut inside recovery and a process-kill case |

**Verdict.** CrashIO is a strict subset of faultfs: faultfs has everything it checks (prefix sweep, a torn write) plus durability, namespace, barriers, media faults. CrashIO even ignores its own fsync log. journal MemoryIO is also a subset of faultfs (it lacks barriers, faults, per-epoch ordering) but contributes the per-op `cut` tick, which faultfs covers with power_off_after. Detent's recorder is different: it observes the real PosixIO call sequence on a real disk, so it proves what PosixIO issues, not what a model keeps. In fault space it is a subset of faultfs (its Entries x Data variants approximate faultfs epochs and zeros-past-size), but that real-sequence check cannot be replaced by a model. Keep it as a recording decorator over any IO.

## 2. File-I/O seams

| Seam | Interface | Implemented by | Used by |
|---|---|---|---|
| kronuz::journal::IO + File (completion/include/completion/io.h:74-255) | File: size, read_at, write_at, truncate, sync, sync_data, map, inspect, try_lease. IO: open_existing(_read_only), create_exclusive, replace, remove, scan_directory, sync_directory, sync_files / order_files_and_directory (:231-249), acquire_owner, lock_owner, entry_footprint | PosixIO (completion/posix.h:611), faultfs::io, journal MemoryIO; backends BSD/Linux/Asio via completion primitives (SyncFiles, OrderFiles, SyncData; sync-files.md) | journal (3 headers), strata (~20 files; index.hh, catalog.hh take `journal::IO&`), consensus (2), prospect (5), Detent (11), Xapiand (4) |
| PosixIO::replace_sync_calls (posix.h:498) | swaps fsync / fcntl / sync_file_range | PosixIO | Detent recorder, completion sync_calls_test |
| storage IO policy (storage/storage_io.h:20-120, `STORAGE_IO_HEADER`/`STORAGE_DEFAULT_IO`, storage.h:73-85) | 14 static fd methods: open close lseek read write pread pwrite fsync full_fsync fallocate fadvise lock_shared lock_exclusive ftruncate | DefaultIO, CrashIO, XapiandStorageIO (Xapiand/src/xapiand_storage_io.h, forwards to io::) | Storage<...> template: 43 IO:: call sites in storage.h (1753 lines); Xapiand shard/manager, Detent authority service |
| Kronuz/io (io/io.hh:199-460, `IO_RANDOM_ERRORS_HEADER`:98) | fd functions open close read/write/pread/pwrite lseek unlink fsync full_fsync fallocate fadvise; macro hooks RANDOM_ERRORS_IO/NET_ERRNO_RETURN | io.cc; Xapiand/src/xapiand_io_random_errors.h (probabilistic errno) | Xapiand, XapiandStorageIO, pki/src/directory.cc (full_fsync) |
| completion barriers (docs/mechanisms/sync-files.md, barriers.md, commit-barriers.md, completion-seam.md) | sync_files_and_directory (durable), order_files_and_directory (macOS F_BARRIERFSYNC; Linux = durable), SyncData primitive; HeldCompletion hold/execute/deliver/fail/drop tickets (a crash-ordering tool, in-flight granularity) | PosixIO; the Asio driver | strata commits, journal turn logs, Detent mirror |
| raw calls elsewhere | Detent/src/detent_local/directory.cc:42 fsync; Detent detent_cli/daemon.cc, detent_authority/service.cc; pki/src/directory.cc:208; Xapiand xapiand_fsyncher.h | direct | those only |

## 3. Proposed concept: one file-I/O seam

Adopt `kronuz::journal::IO`/`File` as THE seam. It is already virtual, complete (directory durability, ordered group sync, owner locks, rename, scan) and used by 5 libraries. faultfs is its fault implementation. Needed in addition, all with default no-op:

1. `File::preallocate(offset, len)` (storage fallocate).
2. `File::advise(offset, len, hint)` (fadvise).
3. A cheap-vs-full sync choice on `sync` (storage's STORAGE_FULL_SYNC; today `sync_data` is F_FULLFSYNC on macOS and there is no cheap fsync). Needs an owner ruling.

Positional I/O only: storage's lseek/read/write become read_at/write_at. Locks map to acquire_owner. Then:

- faultfs moves out of strata into a header-only lib depending only on completion/io.h (it already includes only that; namespace `strata::faultfs` renamed).
- A recording `IO` decorator (Detent recorder's job) replaces the PosixIO sync hooks.
- Detent's Entries x Data variants become a faultfs crash policy flag.

## 4. Migration size

| Library | Lines (rough) | Work |
|---|---|---|
| strata | ~60 test files, mechanical | include + namespace rename |
| journal | delete 175 (memory_io.h); 7 files (4 tests, 3 fuzz) | Disk::cut -> power_off_after; power_loss -> crash(seed) |
| consensus | 4 tests | same |
| Detent | 5 power-cut tests; mirror recorder 475 -> ~150 | faultfs + recording decorator |
| storage | largest: 43 call sites in storage.h plus crashio.h (106) and test_crash.cc rewrite; Xapiand XapiandStorageIO (~25) and io/ random-errors hook retire to a faultfs rule or decorator | Storage template parameter becomes `journal::IO&`; fd members become `unique_ptr<File>`; no shim |
| Kronuz/io | random-errors macros dropped for faultfs fault rules in tests | after storage |

## 5. Network and process half

- Detent tests/detent_system/network.py (170 lines): PeerLink/PeerMesh, userspace asyncio TCP proxy per peer, `isolate(index)`/`heal(index)` only; TLS pass-through.
- Xapiand harness/cluster on quest/xapiand/cluster-harness: proxy.py (263) has Link/Mesh: per directed pair, `partition`, `heal`, `reset`, `cap(mbit)` token bucket, `isolate(node)`, bandwidth self-check; cluster.py (257): process cluster with SIGSTOP `pause`/`resume`, `kill_now`; history.py (365): JSON-line history (Recorder/load/check): written, prefix (D10), linearizable (Gibbons-Korach) over per-key registers with unique values; checklist.py, selftest.py.
- Detent: SIGSTOP voters at test_relay_service.py:199-213; Kronuz/consensus peers_test.cc `Timing` presets (compact/loaded, :182-184), not a fault lab.
- No delay, loss, reorder, duplicate or tc/netem/toxiproxy/dm-flakey anywhere (grep over Detent, Xapiand/harness, consensus, cluster). The Xapiand proxy is a superset of Detent's (adds reset and bandwidth).

### Checker language

Python. Both repos' system tests are Python (network.py, run_*.py; harness/cluster), the history checker is already pure Python with `python3 -I`, runs on macOS, and consumes JSON lines, so a C++ test can emit the history. faultfs and the scenario format stay C++ header-only.
