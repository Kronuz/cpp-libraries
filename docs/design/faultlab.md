# faultlab design

Kronuz/faultlab (working name) is the one fault-injection library Xapiand, strata, prospect,
journal, consensus, storage and Detent share (Xapiand D95, Detent D104). This document fixes its
API and the migration onto it before any code moves; the repository is created when this lands.
Input: `docs/research/faultlab-survey.md` (cpp-libraries:d36a131), which maps the four crash
models, the seams and the users; this design does not repeat it.

Commits cited: completion:7731315, strata:491a1bd, prospect:eef601d, journal:8f3e410,
consensus:d1065e0, storage:e0e7bed, io:a67fd5c, Detent:abb78f7, Xapiand:df35965 (harness/cluster).
Reviews folded in: Xapiand's design review (Xapiand:6853e3469, D1-D4) and Detent's (R1-R7, with
its answers to QD1-QD3); rulings in Xapiand PLAN D96 and the lead's notes.

## Shape

```
C++, header-only, needs completion/io.h only       Python, stdlib only, python3 -I
  faultlab/faultfs.h    crash and media model         faultlab/history.py   the one checker
  faultlab/recorder.h   recording IO decorator        faultlab/proxy.py     portable network tier
  faultlab/scenario.h   seeded scenario line          faultlab/netlab.py    Linux: netns, netem, nftables
  faultlab/events.h     JSON-line event writer        faultlab/disklab.py   Linux VM: dm-log-writes, dm-delay, dm-flakey
                         \___ one scenario line, one event log, read by the one checker ___/
```

## Decisions

**F1. One repository, two halves.** C++ headers that depend only on completion's `io.h`, and a
stdlib-only Python package, versioned together because the scenario line (F11) and the event log
(F12) are one contract both halves write. Consumers take it as a test-only dependency.
Rejected: faultfs inside completion, which owns `io.h` but is a production library that would ship
a test model in its headers and has no home for the Python half; two repositories, which would
version one contract twice.

**F2. Names.** Namespace `kronuz::faultlab`; faultfs keeps strata's type names (`filesystem`, `io`,
`file`, `fault`, `op`, `media`), so strata's move is an include and namespace edit. The map switch
`STRATA_FAULTFS_MAP` (faultfs.hh:159) becomes `FAULTLAB_MAP`. Rejected: keeping `strata::faultfs`,
which names the wrong owner for six repositories.

**F3. faultfs's model is the model; its default stays unchanged.** Its semantics stay as
faultfs.hh:1-30 states them, and `crash(seed)` with the default policy consumes its random stream
exactly as today (faultfs.hh:250-334), so every existing seed rebuilds the same state and strata's
sweeps keep their coverage. By default faultfs is not a superset of storage's CrashIO and
journal's MemoryIO: both leave a file that ends at a sector boundary partway through an unsynced
append, with no zero tail (memory_io.h:73-79; test_crash.cc:90, 94-96), while faultfs's size is
the durable one or the current one (faultfs.hh:284). The review's probe (job
261116-143957-91a3bb: faultfs sizes `0 1536`, MemoryIO `0 512 1024 1536`) shows it. The opt-in
`size_pick::sector` (F5) reaches those states, and the tests that replace MemoryIO and CrashIO
(steps 5, 6, 9) sweep with it. Rejected: changing the default size coin, which would re-record
every strata seed; a new model merged from the four, which would re-derive what faultfs already
proves.

**F4. One filesystem is one device; an `io` is one directory on it.** `io(filesystem&, std::string
directory = {})` roots an IO at a directory; `make_directory(path)` creates one, durable at once,
since `journal::IO` cannot create directories. `sync_directory` makes durable only that
directory's namespace changes; an ordering point is device-wide, as completion's ordered sync is
"ordered on the directory's device" (posix.h:194). Today faultfs is one flat directory (names with
`/` are refused, faultfs.hh:148), while journal's MemoryIO shares one disk among directories by
prefix (memory_io.h:121-125), which Detent uses (test_history_large_base.cc:180). A directory is
an entry of its parent: its parent's `scan_directory` lists it and `entry_footprint` reports it as
`EntryKind::Directory`, as PosixIO does, and `remove` of it throws as unlink does (MemoryIO hides
it, memory_io.h:168-169). `make_directory` is durable by fiat; the "directory lost after a crash"
state is not modelled, which MemoryIO lacks too. A name-prefixed view over one `io`, such as
journal-driver's `PrefixIO` (journal:5a959a1 host.h:214-245), is the caller's decorator, valid over
faultfs, and not a directory: its `sync_directory` stays the whole directory's. Rejected: one
`filesystem` per directory, as strata's multi-directory tests do (`faultfs::filesystem fs, fs2`
in 8 tests): two directories of one node then lose power at different instants, and a barrier in
one cannot order the other.

**F5. A crash policy: fixed picks, and one opt-in size.** `crash(seed, crash_policy)` fixes coins
`crash` already flips, so every fixed pick is a state the IO contract allows and the default
(`coin` everywhere) is F3's unchanged stream:

```cpp
enum class epoch_pick { coin, none, all };              // ordering points kept whole
enum class name_pick { coin, durable, all, additions }; // namespace ops the epoch cut admits
enum class size_pick { coin, durable, current, sector };// each dirty file's size
enum class sector_pick { coin, old, fresh };            // each 512-byte sector's bytes
struct crash_policy {
	epoch_pick epochs = epoch_pick::coin;
	name_pick names = name_pick::coin;
	size_pick size = size_pick::coin;
	sector_pick sectors = sector_pick::coin;
};
```

`name_pick::additions` keeps every create, link and replace the epoch cut admits and drops every
remove. `size_pick::sector` is opt-in: it draws a cut at any sector boundary from the durable size
to the current one, which reaches MemoryIO's and CrashIO's partial-append states (F3).

Detent's four variants (test_relay_mirror_crash.cc:27-28, test_agent_store_crash.cc:32-33) are
`names` in {`durable` = Entries::Durable, `additions` = Entries::All} x `size` in {`durable` =
Data::Truncate, `current` = Data::Zeros}, with `sectors = old` and `epochs = all` (Detent counts a
barrier as a device flush, test_relay_mirror_crash.cc:103-108). Entries::All is the durable
namespace overlaid with every live name (test_relay_mirror_crash.cc:129-133); `additions` is its
legal half: new names present and removed names still there, the collector's case. Its other half,
both names of one rename, breaks atomic `replace` and is dropped as illegal. "Legal" here means
allowed by the IO contract faultfs models (an independent coin per namespace operation, `replace`
atomic), not reachable on a real filesystem: journaled ext4, xfs and APFS persist directory
operations in prefix order, so neither `additions` nor the both-names state occurs there. Rejected: `names =
all` for Entries::All, which applies the removes and loses the collector's case; keeping Detent's
`after_power_cut` as a second reconstruction beside faultfs's, two models of one contract that can
disagree and that has neither sector tearing nor partial epochs.

**F6. Three additions for the users faultfs does not serve yet.**

1. `void kill()`: a process death. Every handle goes stale and owner locks release, as after
   `crash`, but current state, durable state and staged ordering epochs all stay, so a later
   `crash` still loses the unsynced part in epoch order (Detent's `after_kill`,
   test_relay_mirror_crash.cc:263-281).
2. `filesystem snapshot() const`: a deep copy, for the recorder's per-event states (F10) and for
   sweeping cut points from one prefix.
3. `bool powered_off() const`: true once `power_off_after` has run out. journal's power cut throws
   `PowerLoss`, not a `std::exception`, so callers' handlers cannot swallow it (memory_io.h:55-58);
   faultfs fails with EIO and keeps failing until `crash` (faultfs.hh:220-226), and a test asks
   this instead of catching a type. Code under test then runs its error paths after the cut
   (consensus core.h:256 swallows `std::exception`), so tests check `powered_off()` per step and
   bound their retry loops (steps 5 to 7).

**F7. Public API.** One table, everything a test touches. Existing members are at faultfs.hh lines
given; new ones are marked.

| Group | Member | Where |
|---|---|---|
| Device | `filesystem(std::uint64_t capacity = ~0)`, `set_capacity`, `used`, `make_directory` (new) | 158, 243, 350 |
| Crash points | `power_off_after(n)`, `mutations()`, `powered_off()` (new) | 222, 227 |
| Power loss | `crash(seed, crash_policy = {})` (policy new), `kill()` (new), `snapshot()` (new) | 250 |
| Sector tearing | 512-byte sectors old or new, zeros past the durable size, size old or new (or any sector boundary between, opt-in `size_pick::sector`) | 8-10, 288-296 |
| Namespace durability | create, link (new), replace (atomic), remove replayed in order, kept per coin until `sync_directory`; a link draws a coin only when one is logged, so F3's seeds hold | 11-12, 300-327 |
| Ordering epochs | `io::order_files_and_directory`: chained epochs, staged bytes ahead of later changes | 14-21, 705 |
| Operation faults | `add_fault(fault{op, nth, error, after, keep})`, `clear_faults`; `op` gains `link`, `preallocate`, `lease` (new) | 55-67, 163 |
| File members | `inspect()` (new: kind, size, inode, the process's owner, links as the names that reach it, permissions); `try_lease(LeaseMode)` (new: a per-inode lease table, false when held, released by `kill()` and `crash()`); `map_shared(length)` (new, F8); today io.h:85-88 throw | 465-610 |
| ENOSPC | capacity checked on writes and `preallocate` (new) | 24, 505 |
| Short and damaged writes | `short_writes(max)`, `damage_writes(min, at, count)`, `damaged_writes()` | 203-219 |
| Media faults | `add_media_fault(path, media::{read_error, bit_flip}, begin, end, times)`, `media_hits()` | 69, 174, 191 |
| Counters | `syncs()`, `calls()` | 233, 239 |
| Environment | `classify`, `set_trust`, `map_files` | 181, 186, 198 |
| Inspection | `view(path)`, `list(directory = {})` | 338, 344 |
| IO | `io(filesystem&, std::string directory = {})` (directory new); `link`, `inspect_entry`, `lock_owner(OwnerLockOptions)` (new; today io.h:227, 255-257 throw) | 614 |

**F8. Four seam additions (completion io.h, Xapiand PLAN D96).** Three on `journal::File`
(io.h:74-95), one on `journal::IO` (io.h:155-257):

```cpp
enum class Advice { Normal, Sequential, Random, WillNeed, DontNeed };
// Grows the file to at least offset + length, zero-filled, reserving the space so later writes
// in that range do not fail with ENOSPC. Throws std::system_error (ENOSPC, EIO) on failure.
// Default: truncate(max(size(), offset + length)), which grows the size without a reservation.
virtual void preallocate(std::uint64_t offset, std::uint64_t length);
// A hint; never fails and never changes the bytes. Default: nothing.
virtual void advise(std::uint64_t offset, std::uint64_t length, Advice) noexcept {}
// A writable view of [0, length) shared with the file; requires size() >= length. Null when
// the backend cannot map. Stores reach the file without a write call; not durable until sync.
virtual std::shared_ptr<SharedMapping> map_shared(std::uint64_t length) { return nullptr; }
// IO: a second name for source's file. Never replaces: throws std::system_error(EEXIST) when
// destination exists. Default: throws not_supported, as the other optional members do.
virtual void link(std::string_view source, std::string_view destination);
```

`SharedMapping` is `Mapping` (io.h:62-70) with a writable `std::span<char> words()`. PosixFile maps
it with `mmap(PROT_READ | PROT_WRITE, MAP_SHARED)`, as Detent's ChangeWriter does raw today
(change_file.cc:73). faultfs backs it with a buffer it folds into the inode at the next call into
the filesystem (a read included) and at `crash`, as one write of the changed sectors through the
ordinary write path: a store is visible to the next call, is ordered as a write made at that
call, and at a crash each changed 512-byte sector keeps its old bytes or its new ones, the sector
model unchanged. Truncating below a live shared mapping aborts, as `map_files` does for `map`.

PosixFile implements `preallocate` with storage's code, F_PREALLOCATE then `ftruncate` on macOS
and `posix_fallocate` elsewhere (storage_io.h:231-258); where the filesystem does not support it
(EOPNOTSUPP, ENOSYS, EINVAL, which storage tolerates today, storage.h:1438-1444; FreeBSD ZFS
returns EINVAL), it falls back to the default's `truncate` growth, so every caller sees one
contract and storage's tolerance code goes. `advise` uses `posix_fadvise` on Linux only
(storage_io.h:260-266). PosixIO implements `link` with `linkat` on its directory handle, the call
Detent's stores make raw today (mirror.cc:45, 249; agent_store.cc:84, 382). faultfs counts
`preallocate` as a mutation and as capacity, so a fault rule or a full device fails it before the
first byte (storage.h:1430-1446). Rejected: a no-op default for `preallocate` (the survey's
proposal): storage.h:1438 relies on the size growing to the record's extent, and storage.h:547's
growth, though it only warns on failure, would silently stop; publishing with `replace` instead of
`link`, which cannot refuse an existing destination.

**F9. Sync: always durable (pending the owner's ruling).** Lead's default: `File::sync` and
`sync_data` are durable in every process, F_FULLFSYNC on macOS (posix.h:174-191), and no caller
can ask for less. The only process-wide setting is a switch for tests and benchmarks
(`PosixIOOptions`, posix.h:596-609) that weakens every sync of the process at once to the
platform's plain fsync; it is never a barrier-only mode, and no caller selects it per file or per
call. Storage's `STORAGE_FULL_SYNC` (storage.h:149, 1211-1242) maps onto that switch: storage calls
`sync_data` where it calls `fsync` today and `sync` where it calls `full_fsync`, both durable, and
a deployment that ran without `STORAGE_FULL_SYNC` sets the switch instead. faultfs models only the
durable contract; a process with the switch set is not crash-tested.
Options for the owner: (a) this default; (b) `sync(Strength)` per call, which gives every caller
two ways and makes faultfs model a third durability; (c) strength fixed per file at open, which
keeps storage's flag but splits one process's files across two guarantees. Recommendation: (a).

**F10. A recording `IO` decorator replaces Detent's sync hooks.**

```cpp
class recorder final : public kronuz::journal::IO {
public:
	// The shadow is the directory `directory` of `shadow`, as F4's io is.
	recorder(std::shared_ptr<kronuz::journal::IO> real, filesystem& shadow, std::string directory = {});
	void note(std::string label);   // a labelled event, e.g. from Detent's MirrorTesting hook
	void add_fault(const fault&);   // fails the real call before or after it, as faultfs rules do
	// Throws unless the shadow's current names and bytes equal load(real_directory); the files in
	// `length_only` (mapped through map_shared, whose stores the shadow never sees) by length only.
	void verify(const std::filesystem::path& real_directory, std::span<const std::string_view> length_only = {}) const;
	struct event { std::string label; filesystem state; };
	const std::vector<event>& events() const;
};
filesystem load(const std::filesystem::path& directory);                  // a durable shadow of a real directory
void materialize(const filesystem&, const std::filesystem::path& directory); // its current names and bytes, on disk
```

Every call goes to the real IO and then to the shadow faultfs; after each mutating primitive the
recorder appends `{label, shadow.snapshot()}`. A group sync goes to the real IO once, keeping
PosixIO's shared flush, and to the shadow as its individual primitives, one event each. A cut after
event i is `events[i].state.crash(seed, policy)` or `.kill()`; recovery then runs on that faultfs
directly, or on a real directory through `materialize`. `map_shared` goes to the real file only,
so the shadow holds a mapped file's name and length, not its words. A run ends with `verify()`: a program
that changes the directory outside the seam (a raw `linkat`, a raw write through the directory fd)
leaves the shadow behind the real directory and fails loudly there, instead of sweeping states
that never matched the run.

Prerequisite for Detent (step 7): the recorder sees only calls through `journal::IO`. Detent's
stores take a concrete `PosixIO` (mirror.cc:30, 151; agent_store.cc:70, 251), publish with raw
`linkat` (mirror.cc:45, 249; agent_store.cc:84, 382), `fstat` the directory (mirror.cc:120;
agent_store.cc:201) and open `change` through `detail::ChangeWriter` on the directory fd
(agent_store.cc:208). Before their crash tests move, they take `journal::IO`, publish with
`IO::link` (F8), move the ownership check into `directory_trust()` (io.h:146-153), and open every
file through the IO; faultfs implements `inspect_entry` and `lock_owner` (F7). AgentStore also
holds generations with `File::try_lease` and inspects files with `File::inspect` (agent_store.cc:359,
530), which faultfs gains (F7). Its ChangeWriter creates, sizes and inspects `change` through the IO
(`create_exclusive`, `truncate`, `inspect`), keeping the creation-to-sizing kill cut (D59 F1) in the
shadow, and maps the words with `map_shared`; the agent-store run ends with
`verify(dir, {"change"})`, which compares `change` by length, as today's test models it
(test_agent_store_crash.cc:63-64).
This proves the program's call sequence against the IO contract on every platform. What PosixIO
turns that contract into (fsync, F_FULLFSYNC, F_BARRIERFSYNC, sync_file_range) stays proven by
completion's own sync_calls_test.cc, the one remaining user of `replace_sync_calls`
(posix.h:686-703). Rejected: keeping the syscall-level recorder, now copied twice in Detent
(test_relay_mirror_crash.cc:17-160 and test_agent_store_crash.cc:21-128, 145-166, 299-345), each with its own
per-platform rule for which fsync is durable (test_relay_mirror_crash.cc:74-119).

Size against the 475 lines of test_relay_mirror_crash.cc: its disk model, hooks, reconstruction
and kill (lines 17-160 and 263-319, about 200 lines) go, and `record_run` (227-262) shrinks to
about 15 lines; the scenario (steps, lineage, `recovered`, `matrix`, `main`, about 250 lines)
stays, so the test lands near 275 lines. test_agent_store_crash.cc (512) loses the same parts.
Both copies become one `recorder.h` of about 200 lines with its own tests, including a link and
a `verify` failure on a raw write. The survey's "~150" assumed the scenario shrinks too; it does
not need to.

**F11. One seeded scenario line.** Every faultlab user derives all its randomness from one seed
(C++ `std::mt19937_64`, Python `random.Random`) and prints, on failure, one line that replays it:

```
faultlab/1 name=mirror_crash.first seed=11 cut=513 pick=all,additions,current,old
```

Space-separated `key=value`; `name` and `seed` required; `cut` (the `power_off_after` count),
`pick` (F5, in field order) and any further keys optional. `FAULTLAB_SCENARIO=<line>` runs exactly
that case. `scenario.h` and `scenario.py` parse and print it. For process runs the seed drives the
fault schedule, so a rerun repeats the schedule, not the thread interleaving. Rejected: a JSON
scenario, which a header-only C++ half cannot read without a parser dependency (the lead's rule:
nothing beyond completion).

**F12. One JSON-line event log.** One file per run, one object per line, written by in-process
tests (`events.h`) and process harnesses alike:

1. First line `{"scenario": "<F11 line>"}`.
2. Operations exactly as history.py reads them today (history.py:1-36, 92-111): `client`, `op`,
   `key`, `value`, `level`, `outcome`, `time`, and optional `node`, `launch`.
3. Faults: `{"fault": KIND, "time": T, ...}` with KIND one of `partition`, `heal`, `isolate`,
   `reset`, `cap`, `delay`, `loss`, `reorder`, `duplicate` (network); `pause`, `resume`, `kill`,
   `restart` (process); `power_cut`, `media`, `enospc` (disk); arguments by name (`nodes`, `ms`,
   `p`, `seed`, and `at=<label>` for a stop placed at a labelled code point).
4. Harness records: any line with a `kind` key belongs to the harness that wrote it (Detent's
   `events.jsonl` metadata, actor output and phase marks, runtime.py:118-132) and the checker sets
   it aside, so one run keeps one log.

`time` is seconds since the run started, or a logical clock in in-process tests; the checker only
needs it non-decreasing per client (history.py:138-139). Rejected: a separate fault log beside the
history, which would need two clocks aligned to say which fault overlapped which operation.

**F13. One checker: Xapiand's history.py moves to faultlab.** Its three checks (written, prefix,
linearizable, history.py:22-33) and selftest.py move unchanged; `load` learns to set aside
`scenario`, `fault` and `kind` lines, which it now rejects (history.py:122-132), and a violation
report lists the faults inside the violating operations' interval. Two named checks join, from
Detent's answers (QD3): `monotonic`, a node the log marks durable never reads older than it served,
across launches (`prefix` resets at a restart, history.py:240-246); and `seal`, a read returns a
seal no older than any seal a completed read or acknowledgement observed before it began, the read
half of linearizability over a monotone counter (about 20 lines). Rejected: a C++ checker beside it, a second implementation of the
same verdict; C++ tests write the log and call the Python checker as a test step.

**F14. Network: one interface, two tiers.** `partition(a, b)`, `heal(a=None, b=None)`,
`isolate(n)`, `reset(a, b)`, `cap(mbit)` on both tiers; `delay`, `loss`, `reorder`, `duplicate`
on netlab only, where the proxy raises `Unsupported` rather than skip silently. Each call writes
its fault event.

- proxy (portable, unprivileged): Xapiand's proxy.py moves (Link, Mesh, proxy.py:59-185). Its
  `isolate` holds bytes silently and delivers them on heal; Detent's PeerMesh `isolate` closes live
  connections and refuses new ones (network.py:100-104, 156-166), which is `isolate` plus `reset`
  here. Both stay, named so; Detent's step 7 picks one per run and records it. The moved `Mesh.close`
  raises a forward task's failure, as PeerMesh does, instead of discarding it (proxy.py:189-191).
- netlab (Linux, root or a user namespace): a network namespace per node joined by veth pairs;
  netem on each for delay, loss, reorder, duplicate and rate; nftables per directed pair for
  partition (drop) and reset (reject with tcp reset).

Rejected: toxiproxy or another daemon, a dependency for what netem and 263 lines of asyncio do.

**F15. Disk: disklab on Linux VMs only.** dm-log-writes records every write with its flush and
FUA marks, and replays to any mark: the states a real filesystem leaves at a real power cut, which
faultfs models but cannot prove. dm-delay slows the device, dm-flakey fails or drops writes for a
window. These need root and a block device, so they run inside the qemu VMs of Xapiand's
cluster-vm-tier quest (cluster-release.md D14), never on the host and never on AWS.

What runs where:

| Part | Linux | macOS | FreeBSD |
|---|---|---|---|
| faultfs, recorder, scenario, events (C++) | yes | yes | yes |
| history checker, proxy tier, process fault events (the harness sends SIGSTOP and SIGKILL) | yes | yes | yes |
| netlab | yes | no | no |
| disklab | in a VM | Linux VM | Linux VM |

faultlab carries no signal code: whole-process stops are the harness's (test_relay_service.py:212-224),
and stops at a code point stay in the test at labelled hooks (QD3). FreeBSD equivalents (dummynet,
gnop) are not built: one lab per mechanism, and a Linux VM runs on every host. Rejected: a lab per platform, three implementations of one fault.

**F16. Migration: callers first, the original deleted last, no shim.** Each step lands in one
repository with its CI green on every platform. A consumer moves to faultlab while the old copy
still exists, so both copies live for at most the steps between, never both in one target; the
owning repository deletes its copy once no pinned consumer includes it.

## Migration order

| # | Repository | Size (counted at the commits above) | Work |
|---|---|---|---|
| 0 | completion | io.h +4 virtuals and `SharedMapping` (F8), PosixFile and PosixIO overrides, tests | F8; F9 if ruled (a) |
| 1 | faultlab | faultfs.h from strata (784 lines) plus F4-F7; recorder.h (~200); scenario.h, events.h; Python: history.py (365) with `monotonic` and `seal`, selftest.py (446), proxy.py (263), proxy_test.py (99) from Xapiand | new repository, CI on Linux, macOS, FreeBSD |
| 2 | prospect | 19 files include strata's faultfs | include and namespace |
| 3 | strata | 40 tests, 3 benches, CMakeLists, `FAULTLAB_MAP` in 5 files; delete core/faultfs.hh (the survey's ~60 counted more loosely) | include and namespace; every seed keeps its state (F3) |
| 4 | Xapiand | harness/cluster imports faultlab's history and proxy; its copies go | path only |
| 5 | journal | 4 tests, 3 fuzz files at journal:8f3e410 (framing, journal, shared_store, turn_log_power; fuzz_framing, fuzz_turn_log, replay); recount at journal-driver's landing, which adds host_test, driver_test and placement_test on `MemoryIO(disk, "host/")` (journal:5a959a1); host_test's name-based `RecordingIO` stays a test decorator | `Disk::cut` to `power_off_after`, `power_loss()` to `crash(seed)` with `size_pick::sector`; `PowerLoss` catches to `powered_off()` per step; MemoryIO's syncing `truncate` (memory_io.h:105) becomes faultfs's unsynced one |
| 6 | consensus | 3 tests on MemoryIO (shared_cluster, shared_worker, peers; the survey said 4) | as journal; the `PowerLoss` catches (shared_cluster_test.cc:191, shared_worker_test.cc:221, 248) and core.h:256's fence need bounded retries |
| 7 | Detent (owns it; after journal-driver lands, per D104) | first: stores retyped to `journal::IO`, `link`, `directory_trust()`, ChangeWriter through the IO (F10); then cluster_harness.hh and 4 authority tests on MemoryIO; mirror crash (475) and agent-store crash (512) onto the recorder, ending with `verify()`; test_agent_store.cc's failing syncs (:448-453) to recorder faults; network.py onto the proxy tier | Detent's own quests; one job shows F5's four picks reproduce the old model's states before `after_power_cut` goes (QD2) |
| 8 | journal | delete memory_io.h (175) | after step 7 pins |
| 9 | storage | `Storage<IO>` takes `journal::IO&`, fd members become `std::unique_ptr<File>`; 47 `IO::` uses in storage.h (the survey counted 43 call sites); crashio.h (106) and test_crash.cc (309) onto faultfs with `size_pick::sector`; Xapiand's xapiand_storage_io.h (62) goes | needs F9's ruling |
| 10 | io, Xapiand | io.hh's `IO_RANDOM_ERRORS_HEADER` hooks (io.hh:96-98) and Xapiand's xapiand_io_random_errors.h (64) retire for faultfs rules | last: io's fd functions serve Xapiand until storage moves |

Journal moves its own tests first (step 5), so faultfs's namespace subsets and unsynced truncate
surface journal bugs in journal, not in consensus; it deletes memory_io.h only at step 8, after
its last consumer, so no pinned repository breaks.

Checks for the build steps: each step's CI green on every platform; after step 3,
`git grep strata::faultfs` is empty in strata and prospect; after step 8, `git grep memory_io.h`
is empty in journal, consensus and Detent; after step 9, `git grep CrashIO` is empty in storage;
faultlab's own suite proves F5 (each fixed pick's state equals `crash` with that field's coins
forced, checked directly), F3 (a recorded table of strata seeds and the states they rebuild,
unchanged), `size_pick::sector` (the review's probe, `.scratch/review-faultlab-design-design/sizes.cc`
in Xapiand, as a test: every MemoryIO and CrashIO state over random append sequences is a faultlab
state), `link` (a crash of link then unlink of the temporary before `sync_directory` keeps
only POSIX-reachable states), `try_lease` (a lease held at a cut is released by `kill()`), and
`map_shared` (stores torn per sector at a crash, never past an ordering point they followed).

## Questions for Detent's lead (answered)

Detent's review (R1-R7) answered all three; the answers are folded into F4, F10, F12-F15 and step 7.

**QD1. Is an IO-level recorder enough?** Yes, once its stores go through the seam (F10's
prerequisite, F8's `link`). Recovery runs on faultfs, with `materialize` only for `mirror_matches`
and anything that reads the directory directly. PosixIO's syscall mapping is pinned per primitive
and platform by completion's sync_calls_test.cc (:131-151, :193-197, :254-299); `verify()` keeps
the premise honest when new code adds a raw syscall. Recovery on faultfs drops the per-state
`materialize`, which is where the 900 s ctest budgets go.

**QD2. Which picks?** The four fixed picks (F5) at every cut, plus N seeds of the default policy at
the outer cuts only, not on nested restart-and-cut recordings, deduplicated by state fingerprint as
`g_outcomes` does. Each seed derives from the F11 base seed and the cut index, so a failure prints
its replay line. N is measured after the move, inside the 900 s timeout, since the recorder cuts
after every primitive. One job, before `after_power_cut` is deleted, shows that for each recorded
run the four picks give the old model's four states, less the both-names states F5 drops as
illegal, which the job lists.

**QD3. Do Detent's histories fit the checker?** Relay partition and outage runs: as they are
(unique producer and sequence per key, writers.py:118-127; outage reads are `prefix` reads with
`node`). A relay never serving older history across restarts: the named `monotonic` check (F13).
voter-read-freshness A2: the named `seal` check (F13). consensus-transport A6: its verdicts are
timing assertions inside the test, not histories; it uses F11's line and F12's `pause`/`resume`
events only. Stops: whole-process pauses at a test phase can come from outside; a stop at a code
point cannot, since an outside signal on a log line races a drain that finishes first (R2), so it
stays in the test at a labelled hook. Follow-ups, decided here: `isolate` semantics (R3, F14) and
the `kind` lines (R4, F12).

## First buildable steps

1. Owner rules F9.
2. completion: F8 (`preallocate`, `advise`, `map_shared`, `link`) with PosixFile, PosixIO and tests.
3. Create Kronuz/faultlab from strata's faultfs.hh with F2-F7, its tests (F3's seed table, the
   sector probe, link) and CI; then the recorder, scenario and events headers; then the Python half.
