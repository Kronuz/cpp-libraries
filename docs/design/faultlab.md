# faultlab design

Kronuz/faultlab (working name) is the one fault-injection library Xapiand, strata, prospect,
journal, consensus, storage and Detent share (Xapiand D95, Detent D104). This document fixes its
API and the migration onto it before any code moves; the repository is created when this lands.
Input: `docs/research/faultlab-survey.md` (cpp-libraries:d36a131), which maps the four crash
models, the seams and the users; this design does not repeat it.

Commits cited: completion:7731315, strata:491a1bd, prospect:eef601d, journal:8f3e410,
consensus:d1065e0, storage:e0e7bed, io:a67fd5c, Detent:abb78f7, Xapiand:df35965 (harness/cluster).

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

**F3. faultfs's model is the model, unchanged.** It is a superset of storage's CrashIO and
journal's MemoryIO in fault space (survey section 1). Its semantics stay as faultfs.hh:1-30
states them, and `crash(seed)` with the default policy consumes its random stream exactly as
today (faultfs.hh:250-334), so every existing seed rebuilds the same state and strata's sweeps
keep their coverage. Rejected: a new model merged from the four, which would re-derive what
faultfs already proves and change every seed.

**F4. One filesystem is one device; an `io` is one directory on it.** `io(filesystem&, std::string
directory = {})` roots an IO at a directory; `make_directory(path)` creates one, durable at once,
since `journal::IO` cannot create directories. `sync_directory` makes durable only that
directory's namespace changes; an ordering point is device-wide, as completion's ordered sync is
"ordered on the directory's device" (posix.h:194). Today faultfs is one flat directory (names with
`/` are refused, faultfs.hh:148), while journal's MemoryIO shares one disk among directories by
prefix (memory_io.h:121-125), which Detent uses (test_history_large_base.cc:180). Rejected: one
`filesystem` per directory, as strata's multi-directory tests do (`faultfs::filesystem fs, fs2`
in 8 tests): two directories of one node then lose power at different instants, and a barrier in
one cannot order the other.

**F5. Detent's Entries x Data variants are a crash policy.** `crash(seed, crash_policy)` fixes the
coins `crash` already flips instead of adding outcomes, so every pick is a state the IO contract
allows:

```cpp
enum class pick { coin, oldest, newest };
struct crash_policy {
	pick epochs = pick::coin;   // ordering points kept whole: none (oldest) or all (newest)
	pick names = pick::coin;    // namespace changes the epoch cut admits: none or all
	pick size = pick::coin;     // each dirty file's size: durable or current
	pick sectors = pick::coin;  // each 512-byte sector: old bytes or new
};
```

Detent's four variants (test_relay_mirror_crash.cc:27-28, test_agent_store_crash.cc:32-33) are
`names` in {oldest = Entries::Durable, newest = Entries::All} x `size` in {oldest = Data::Truncate,
newest = Data::Zeros} with `sectors = oldest`. Detent's model counts a barrier as a device flush
(test_relay_mirror_crash.cc:103-108), which is `epochs = newest`. Rejected: keeping Detent's `after_power_cut`
(test_relay_mirror_crash.cc:129-145) as a second reconstruction beside faultfs's: two models of
one contract can disagree, and it has neither sector tearing nor partial ordering epochs.

**F6. Three additions for the users faultfs does not serve yet.**

1. `void kill()`: a process death. Every handle goes stale and owner locks release, as after
   `crash`, but current and durable state both stay, so a later `crash` still loses the unsynced
   part (Detent's `after_kill`, test_relay_mirror_crash.cc:263-281).
2. `filesystem snapshot() const`: a deep copy, for the recorder's per-event states (F10) and for
   sweeping cut points from one prefix.
3. `bool powered_off() const`: true once `power_off_after` has run out. journal's power cut throws
   `PowerLoss`, not a `std::exception`, so callers' handlers cannot swallow it (memory_io.h:55-58);
   faultfs fails with EIO and keeps failing until `crash` (faultfs.hh:220-226), and a test asks
   this instead of catching a type.

**F7. Public API.** One table, everything a test touches. Existing members are at faultfs.hh lines
given; new ones are marked.

| Group | Member | Where |
|---|---|---|
| Device | `filesystem(std::uint64_t capacity = ~0)`, `set_capacity`, `used`, `make_directory` (new) | 158, 243, 350 |
| Crash points | `power_off_after(n)`, `mutations()`, `powered_off()` (new) | 222, 227 |
| Power loss | `crash(seed, crash_policy = {})` (policy new), `kill()` (new), `snapshot()` (new) | 250 |
| Sector tearing | 512-byte sectors old or new, zeros past the durable size, size old or new | 8-10, 288-296 |
| Namespace durability | create, replace (atomic), remove replayed in order, kept per coin until `sync_directory` | 11-12, 300-327 |
| Ordering epochs | `io::order_files_and_directory`: chained epochs, staged bytes ahead of later changes | 14-21, 705 |
| Operation faults | `add_fault(fault{op, nth, error, after, keep})`, `clear_faults`; `op` gains `preallocate` (new) | 55-67, 163 |
| ENOSPC | capacity checked on writes and `preallocate` (new) | 24, 505 |
| Short and damaged writes | `short_writes(max)`, `damage_writes(min, at, count)`, `damaged_writes()` | 203-219 |
| Media faults | `add_media_fault(path, media::{read_error, bit_flip}, begin, end, times)`, `media_hits()` | 69, 174, 191 |
| Counters | `syncs()`, `calls()` | 233, 239 |
| Environment | `classify`, `set_trust`, `map_files` | 181, 186, 198 |
| Inspection | `view(path)`, `list(directory = {})` | 338, 344 |
| IO | `io(filesystem&, std::string directory = {})` (directory new) | 614 |

**F8. Two seam additions on `journal::File` (completion io.h:74-95).**

```cpp
enum class Advice { Normal, Sequential, Random, WillNeed, DontNeed };
// Grows the file to at least offset + length, zero-filled, reserving the space so later writes
// in that range do not fail with ENOSPC. Throws std::system_error (ENOSPC, EIO) on failure.
// Default: truncate(max(size(), offset + length)), which grows the size without a reservation.
virtual void preallocate(std::uint64_t offset, std::uint64_t length);
// A hint; never fails and never changes the bytes. Default: nothing.
virtual void advise(std::uint64_t offset, std::uint64_t length, Advice) noexcept {}
```

PosixFile implements `preallocate` with storage's code, F_PREALLOCATE then `ftruncate` on macOS
and `posix_fallocate` elsewhere (storage_io.h:231-258), and `advise` with `posix_fadvise` on Linux
only (storage_io.h:260-266). faultfs counts `preallocate` as a mutation and as capacity, so a
fault rule or a full device fails it before the first byte, the case storage relies on
(storage.h:1430-1446). Rejected: a no-op default for `preallocate` (the survey's proposal),
because storage's callers expect the size to grow (storage.h:547, 1438) and a no-op would break
them on every backend that does not override it.

**F9. Sync: one durable `sync` (pending the owner's ruling).** Lead's default: `File::sync` and
`sync_data` stay the only syncs and both are durable, as PosixFile makes them (F_FULLFSYNC on macOS,
posix.h:174-191). Storage's per-file cheap path (plain fsync on macOS, storage_io.h:208-219, chosen
when `STORAGE_FULL_SYNC` is off, storage.h:149, 1211-1242) becomes a per-process setting of
completion's barrier policy (`PosixIOOptions`, posix.h:596-609, where `full_flush_ordering` already
chooses the ordering strength): a process that opts for ordered syncs gets F_BARRIERFSYNC for
`sync` on macOS. faultfs mirrors that setting with one switch, `ordered_syncs(bool)`, under which
`File::sync` is an ordering point (F7's epochs) rather than durable. Storage maps `fsync` to
`sync_data` and `full_fsync` to `sync`.
Options for the owner: (a) this default; (b) `sync(Strength)` per call, which gives every caller
two ways and makes faultfs model a third durability; (c) strength fixed per file at open, which
keeps storage's flag but splits one process's files across two guarantees. Recommendation: (a).

**F10. A recording `IO` decorator replaces Detent's sync hooks.**

```cpp
class recorder final : public kronuz::journal::IO {
public:
	recorder(std::shared_ptr<kronuz::journal::IO> real, filesystem& shadow);
	void note(std::string label);   // a labelled event, e.g. from Detent's MirrorTesting hook
	void add_fault(const fault&);   // fails the real call before or after it, as faultfs rules do
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
directly, or on a real directory through `materialize`.
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
Both copies become one `recorder.h` of about 200 lines with its own tests. The survey's "~150"
assumed the scenario shrinks too; it does not need to.

**F11. One seeded scenario line.** Every faultlab user derives all its randomness from one seed
(C++ `std::mt19937_64`, Python `random.Random`) and prints, on failure, one line that replays it:

```
faultlab/1 name=fields_test.crash seed=11 cut=513 pick=coin,newest,oldest,oldest
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
   `p`, `seed`).

`time` is seconds since the run started, or a logical clock in in-process tests; the checker only
needs it non-decreasing per client (history.py:138-139). Rejected: a separate fault log beside the
history, which would need two clocks aligned to say which fault overlapped which operation.

**F13. One checker: Xapiand's history.py moves to faultlab.** Its three checks (written, prefix,
linearizable, history.py:22-33) and selftest.py move unchanged; `load` learns to set aside
`scenario` and `fault` lines, which it now rejects (history.py:131-132), and a violation report
lists the faults inside the violating operations' interval. A new consistency model joins as a
named check in the same file. Rejected: a C++ checker beside it, a second implementation of the
same verdict; C++ tests write the log and call the Python checker as a test step.

**F14. Network: one interface, two tiers.** `partition(a, b)`, `heal(a=None, b=None)`,
`isolate(n)`, `reset(a, b)`, `cap(mbit)` on both tiers; `delay`, `loss`, `reorder`, `duplicate`
on netlab only, where the proxy raises `Unsupported` rather than skip silently. Each call writes
its fault event.

- proxy (portable, unprivileged): Xapiand's proxy.py moves as is (Link, Mesh, proxy.py:59-185), a
  superset of Detent's PeerMesh (network.py: isolate and heal only).
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
| history checker, proxy tier, process faults (SIGSTOP, SIGKILL) | yes | yes | yes |
| netlab | yes | no | no |
| disklab | in a VM | Linux VM | Linux VM |

FreeBSD equivalents (dummynet, gnop) are not built: one lab per mechanism, and a Linux VM runs on
every host. Rejected: a lab per platform, three implementations of one fault.

**F16. Migration: callers first, the original deleted last, no shim.** Each step lands in one
repository with its CI green on every platform. A consumer moves to faultlab while the old copy
still exists, so both copies live for at most the steps between, never both in one target; the
owning repository deletes its copy once no pinned consumer includes it.

## Migration order

| # | Repository | Size (counted at the commits above) | Work |
|---|---|---|---|
| 0 | completion | io.h +2 virtuals, PosixFile overrides, tests | F8; F9 if ruled (a) |
| 1 | faultlab | faultfs.h from strata (784 lines) plus F4-F7; recorder.h (~200); scenario.h, events.h; Python: history.py (365), selftest.py (446), proxy.py (263), proxy_test.py (99) from Xapiand | new repository, CI on Linux, macOS, FreeBSD |
| 2 | prospect | 19 files include strata's faultfs | include and namespace |
| 3 | strata | 40 tests, 3 benches, CMakeLists, `FAULTLAB_MAP` in 5 files; delete core/faultfs.hh (the survey's ~60 counted more loosely) | include and namespace; every seed keeps its state (F3) |
| 4 | Xapiand | harness/cluster imports faultlab's history and proxy; its copies go | path only |
| 5 | consensus | 3 tests on MemoryIO (shared_cluster, shared_worker, peers; the survey said 4) | `Disk::cut` to `power_off_after`, `power_loss()` to `crash(seed)` |
| 6 | journal | 4 tests, 3 fuzz files (framing, journal, shared_store, turn_log_power; fuzz_framing, fuzz_turn_log, replay) | as consensus; `PowerLoss` catches to `powered_off()` |
| 7 | Detent (owns it; after journal-driver lands, per D104) | cluster_harness.hh and 4 authority tests on MemoryIO; mirror crash (475) and agent-store crash (512) onto the recorder; test_agent_store.cc's failing syncs (:448-453) to recorder faults; network.py onto the proxy tier | Detent's own quests |
| 8 | journal | delete memory_io.h (175) | after step 7 pins |
| 9 | storage | `Storage<IO>` takes `journal::IO&`, fd members become `std::unique_ptr<File>`; 47 `IO::` uses in storage.h (the survey counted 43 call sites); crashio.h (106) and test_crash.cc (309) onto faultfs; Xapiand's xapiand_storage_io.h (62) goes | needs F9's ruling |
| 10 | io, Xapiand | io.hh's `IO_RANDOM_ERRORS_HEADER` hooks (io.hh:96-98) and Xapiand's xapiand_io_random_errors.h (64) retire for faultfs rules | last: io's fd functions serve Xapiand until storage moves |

The quest lists journal before consensus and Detent; journal moves its tests at step 6 but deletes
memory_io.h only at step 8, after its last consumer, so no pinned repository breaks.

Checks for the build steps: each step's CI green on every platform; after step 3,
`git grep strata::faultfs` is empty in strata and prospect; after step 8, `git grep memory_io.h`
is empty in journal, consensus and Detent; after step 9, `git grep CrashIO` is empty in storage;
faultlab's own suite proves F5 (for random operation sequences, every `crash(seed, policy)` state
equals some `crash(seed')` state) and F3 (a recorded table of strata seeds and the states they
rebuild, unchanged).

## Questions for Detent's lead (open)

**QD1. Is an IO-level recorder enough for the relay mirror and agent store crash tests?** F10
records the program's IO calls into faultfs and leaves PosixIO's syscall mapping to completion's
sync_calls_test. Detent's recorders today watch the syscalls themselves. Options: (a) the
IO-level recorder, recovery run on faultfs; (b) the same, recovery on a real directory through
`materialize`; (c) keep a syscall recorder in Detent. Recommendation: (a), with (b) for the cases
that read the directory directly (`mirror_matches`).

**QD2. Which crash picks should the relay and agent-store matrices sweep?** F5 reproduces the four
Entries x Data variants with `epochs = newest`. Options: (a) those four only, deterministic as
today; (b) the four plus N seeds of the default policy at every cut point, which also tears
sectors and cuts epochs; (c) seeds only. Recommendation: (b), with N chosen by the run time Detent
accepts.

**QD3. Do Detent's system histories fit the one checker?** D104 names the relay partition and
outage runs, consensus-transport A6's placed process stops and voter-read-freshness A2. F12 and
F13 offer per-key registers with unique values checked for written, prefix and linearizable reads,
and `pause`/`resume` events from the driver. Options: (a) Detent's histories map onto keys and
values as they are; (b) Detent adds a named check (for example "never older than the quorum's
seal") to history.py; (c) placed stops need an in-process hook (a stop at a labelled code point)
that faultlab supplies. Recommendation: (a) or (b) per test, and placed stops driven from outside
by waiting for the event the process logs, with no signal code in faultlab.

## First buildable steps

1. Owner rules F9.
2. completion: F8 (`preallocate`, `advise`) with PosixFile and tests.
3. Create Kronuz/faultlab from strata's faultfs.hh with F2-F7, its tests (including F3's seed
   table) and CI; then the recorder, scenario and events headers; then the Python half.
