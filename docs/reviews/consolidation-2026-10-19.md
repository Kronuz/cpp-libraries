# Kronuz C++ libraries: duplication, drift, bloat, missing extractions, and slow primitives

- Date: 2026-10-19. Kind: system review; a read-only consolidation audit.
- Libraries reviewed at `origin/main`: completion `7734544`, journal `dbf753f`, consensus `61149a2`,
  reactor `1c37def`, threadpool `394aaea`, scheduler `fb464cb`, metrics `c975765`, allocators
  `b7daa52`, hashes `7ab0c23`, cluster `84e6b01`, http `dc3be77`, logger `8c5afcd`, stash `2908b48`,
  pki `4e7d279`, task `bbb2e14`, residency `4a7b816`, io `1336f85`, fs `a7a7693`, sha256 `2bb34f0`,
  compressors `ed590c8`, varint `21af82a`, bitpack `abf8972`, flume `113f421`, storage `671eaac`.
- Consumers reviewed: strata `main` `3c86484` (plus the peer-transport and durability branches where
  cited); Xapiand own code at `7e8cccb7d` (plus `tls/d1-gate`, `design/pki`, `fix/failover`; nothing
  under `src/xapian/` or `sortable_serialise` opened); Detent `main` `a18b35e` (its docs,
  `cmake/dependencies.json`, and the cited call sites).
- Checked against `AGENTS.md` at `d181ffe` (rule 1 and the catalog), strata's system review
  (SYS-2, SYS-8, SYS-12, SYS-13), and threadpool's `docs/research/scheduler.md`.
- Probes (kept at `~/.scratch/consolidation/probes/`): `hash_rates` (Kronuz/sha256 against OpenSSL 3
  EVP; journal's CRC-32C against `hashes::crc32c`; 64 MiB, best of 3, digests compared; run at
  `nice -n 19` under a light hold, so absolute rates are indicative), `owner_locks` (whether the two
  owner locks exclude each other), `mk_opts` (whether `make_posix_io` accepts `PosixIOOptions`),
  `pins.tsv` (every Kronuz pin by consumer).
- Not run: test suites, sanitizers, fuzzing, benchmarks beyond the hash probe, Linux, FreeBSD, arm64,
  SHA-NI hosts, network or FUSE filesystems.

## Verdict

Consolidation needed: 11 items now, 16 when next touched (plus the catalog corrections), 15 left
with a reason. Two "now" items are correctness defects: CL-2 (two owners can lock one directory)
and CL-12 (pki key files created without a directory sync).

Already sound: `cluster`'s split is acyclic; journal delegates reservation arithmetic to
`allocators` (`journal/include/journal/admission.h:50`); strata and residency use `hashes::crc32c`;
strata uses the catalog's `varint`, `bitpack`, `termdict`, `fst` and `docset`; consensus's recovery
bound exists once (`61149a2`).

## Map

```
strata  -> completion(7734544) -> allocators, metrics; threadpool(628679a), hashes, residency
Detent  -> consensus(b7073bb) -> journal(57e6250) -> completion(5251cf9); reactor/http/cluster(e19afd9)
Xapiand -> reactor/http/cluster(e19afd9), threadpool, scheduler, io, fs, storage; pki on design/pki only
consensus(61149a2) -> journal(cb66f3d) -> completion(5251cf9);  journal(dbf753f) -> completion(21809c7)
```

## Consolidate now

Sizes: S under 100 changed lines, M 100–500, L over 500. "Both" means strata's lead and Detent's
maintainer.

### CL-1. Two CRC-32C implementations; journal's is 19× slower (S, both)

- journal `codec.h:37-61` has a byte-table `Checksum`/`crc32c()`, used by journal batches, manifests,
  artifacts and turn logs, and by consensus's snapshot CRC (`snapshot.h:60-89`, `worker.h:787`).
- `hashes/crc32c.hh` has SSE4.2/ARMv8 paths with a slice-by-8 fallback, used by strata and residency.
- Same polynomial, init and final XOR; 64 MiB digests match. journal 0.41 GB/s, hashes 7.7 GB/s.
- Migration: an additive `hashes::crc32c` target exposing only `crc32c.hh`; journal's functions
  forward to it, the table stays one release as deprecated; a fixture test that existing journal
  bytes still verify. No disk or wire byte changes.

### CL-2. Two owner locks that do not exclude each other (M, both)

- `acquire_owner(bool)` (`posix.h:419-430`) creates, syncs and flocks `owner.lock`; Detent uses it,
  and journal's bootstrap accounting relies on one `owner.lock`.
- `acquire_directory_owner()` (`posix.h:435-452`) flocks the directory descriptor; strata uses it.
- The probe held the file lock in one `PosixIO` and the directory lock in another, on one directory,
  both successfully. The file lock also lacks the EINTR retry and the `not_supported` mapping; the
  base `IO::acquire_directory_owner` throws, so journal's `MemoryIO` can't use it.
- Proposal: `acquire_owner(OwnerLockOptions{mode = file | directory | both})`; `both` takes the
  directory lock then the file lock and releases in reverse. Existing calls become presets.
- Migration: completion adds the overload, unified errors and a mutual-exclusion test; strata records
  why `directory` suffices or uses `both`; Detent moves to `both` on its next pin (its own note,
  `SHARED_LIBRARY_DECISIONS.md:182-187`); the bool form is deprecated after.
- Risk: medium (lock order; directory flock on network filesystems unprobed).

### CL-7. Pin skew (S, library maintainer)

- reactor `1c37def` (the UDP receive-loop fix) reaches no consumer: cluster, http, consensus, prism,
  Detent and Xapiand `master` pin `e19afd9`; only Xapiand's `fix/failover` pins `1c37def`.
- completion: strata `7734544`, journal `21809c7`, Detent `5251cf9`. `21809c7` made
  `AllocationContext` an alias of the allocators type, so type identity differs across pins.
- consensus: Detent is 70 commits behind on purpose (its Pass 3). threadpool: research-only commits.
- Migration: bump reactor in cluster, http, consensus and prism (one commit each, CI green before the
  next); journal pins completion `7734544`; consensus pins journal `dbf753f`; Xapiand `master`;
  Detent on its own schedule.

### CL-8. Track C does not name the recovery bound that exists (S, strata, docs)

`RetainedStatePolicy` (`retained_state.h:7-14`, `61149a2`) is the single policy Detent asked Track C
to consume (`SHARED_LIBRARY_DECISIONS.md:137`). strata's `track-c.md` never names it, and
`peer-transport.md:129` says the bound "stays Track C's". Add the decision row, express the node
budgets (TC:709-716) through it, correct line 129, close SYS-12.

### CL-12. pki key files are not durable after creation (S, Xapiand)

`directory.cc:195-215` creates with `O_EXCL`, writes, full-fsyncs and closes, but never syncs the
directory; a CA or node key can vanish after a power loss. Sync the directory (`F_FULLFSYNC` on
macOS) before `create` returns, and test the syscall sequence.

### CL-5. Four rules for one private key file (S, Xapiand and Detent)

Xapiand `master` (`tls.cc:30-32`: follows symlinks, refuses group/other bits, checks neither owner
nor links); Xapiand `tls/d1-gate` (`tls.cc:31-44`: 0640 when the group is the run-as group); pki
`Policy::key` (`private_file.h:38-44`: no symlink, one link, caller-owned, 0640 only with the
effective group); Detent (group read for any group; no TLS key check;
`SHARED_LIBRARY_DECISIONS.md:91-93`, which also says Xapiand accepts own-group 0640, untrue on
`master`). pki's `getegid()` is wrong for a root start that drops privileges. Proposal:
`private_file::check` in `io::trust` (CL-3), `Policy::key` taking `gid_t runs_as` defaulting to
`getegid()`; Xapiand, pki and Detent call it. The security reviewer agrees too.

### CL-3. Filesystem locality and file trust implemented twice (M, both, plus Xapiand's PKI owner)

completion `posix.h:198-235` (`FilesystemClass`) and `validate_file` (`:113-119`); pki
`directory.cc:240-301` (`check_local_filesystem`) and `private_file.h:27-50` (whose comment says it
is "completion's journal rule", written "so it can move"). They disagree:

| Type | completion | pki |
|---|---|---|
| tmpfs | local | refused |
| overlayfs | local | refused |
| bcachefs | local | refused (unknown) |
| msdos/exfat on macOS and BSDs | local | refused |

They answer different questions ("is local" vs "keeps POSIX modes and locks"). Proposal: one
header-only `io::trust` INTERFACE target returning `{local, posix_modes, name}`, with `private_file`
moved in verbatim, fetched `EXCLUDE_FROM_ALL`. completion forwards (`FilesystemClass` gains a trailing
`posix_modes`); pki forwards and refuses as today; both copies deleted a release later.

### CL-4. Three warn-or-refuse policies for the same environment risks (M, both, plus the owner)

PosixIO refuses a symlinked root and a shared directory unless `PosixIOOptions` admits them
(`posix.h:368-411`); strata layers `nonlocal_policy` and `trust_policy` on top, defaulting to warn
(`index.hh:322-355`, `:2319-2355`); pki refuses everything (`directory.cc:118-156`); Detent keeps a
strict default (`SHARED_LIBRARY_DECISIONS.md:186`). strata's trust warning fires only if the host also
passed `allow_shared_directory`: one decision split across two layers. Proposal: completion owns
`assess_directory(const IO&) -> DirectoryAssessment` and `DirectoryPolicy` with presets `warn` (the
owner's rule) and `strict` (Detent); correctness checks (no-follow on entries, owner, one link, same
device) stay unconditional. Migration: completion adds them with PosixIO's defaults unchanged; strata
calls `warn`; Detent `strict`; pki after Q2.

### CL-6. strata's byte budget re-derives `allocators::ByteAccount` (M, strata)

strata `budget.hh:15-91` (`try_grow`, `grow` past capacity, partial `shrink`, `pressure(reserve)`,
`peak`) names a `ledger` library that was never created; the core became
`allocators/resources.h:160-253`, whose `ByteAccount` has the parent hierarchy strata wants but
throws on admit and has no grow, partial shrink or pressure. Add `try_admit -> optional`,
`ByteCharge::try_grow`, `grow_past_limit`, `shrink` and `ByteAccount::pressure(reserve)`; strata's
`byte_budget` becomes an alias.

### CL-10. Kronuz/sha256 has no hardware path, so designs route around it (M, strata; Detent informed)

`sha256.cc` is portable only, and its global `SHA256` class collides with OpenSSL's `SHA256()`
(`LIBRARY_BOUNDARIES.md:277`). Bypasses: consensus `transport/tls.h:17`, `profile.h:33`; pki
`fingerprint.cc`; strata's durability design (DMS-5, OpenSSL EVP for every file and a SHA-256 per
segment at flush, `durability-modes.md:470,1595`). Measured here without SHA-NI: Kronuz 0.278 GB/s,
EVP 0.455 GB/s (EVP 1.6× faster). Estimated from published figures, not measured: with SHA-NI or
ARMv8 SHA2, EVP reaches about 1.5–2.3 GB/s per core, so ours would be about 5–8× slower; the
durability design assumes 0.5 and 1.5 GB/s (`:1730-1732`). Proposal: three kernels behind runtime
dispatch (x86_64 CPUID leaf 7 EBX bit 29; arm64 `HWCAP_SHA2`/`__ARM_FEATURE_SHA2`; portable), a
namespaced `kronuz::sha256::hasher`/`digest()` beside the old class, per-kernel NIST vectors, and a
README benchmark against EVP. Then DMS-5 names Kronuz/sha256 and strata's core hashes without
OpenSSL; TLS-adjacent digests stay on EVP (those binaries link OpenSSL anyway).

### CL-9. Four power-loss filesystems with different crash models (L, both)

strata `faultfs.hh` (522 lines: per-sector keep/new/zero past the durable size, namespace operations
replayed in order and each kept or dropped, EIO/ENOSPC rules, capacity, short writes, media faults,
both owner locks, trust and classification knobs); journal `memory_io.h` (168 lines, public include
tree; namespace all-or-nothing at power loss, one cut, prefix-shared disks, no directory lock);
`journal/test/journal_test.cc:45-180` (a third `MemoryIO`); consensus `worker_test.cc:45`
(`FaultIO`). A journal or consensus bug that depends on out-of-order namespace survival is invisible
to their tests, and every new `IO` virtual is added four times. Proposal: strata's faultfs becomes
`completion::testing` (`completion/testing/faultfs.h`, built by no one by default), gaining journal's
prefix directories and a throwing cut; journal's `memory_io` forwards; consensus's `FaultIO` stays
(it injects at the PosixIO level). New failures are triaged as possible real bugs (C2).

## When next touched

- **CL-11 (S–M, both).** Three counted-admission types: reactor `OffloadGate` (`reactor.h:84-99`),
  reactor `ConnectionAdmission` (`connection_admission.h:19-92`), http `TlsAdmission`
  (`http_asio_tls.h:45-51`); the manual pairing at `http_asio.h:780-796` is where Detent found a
  plaintext 503 escaping. One `reactor::Admission`, old names as aliases.
- **CL-13 (L).** Five ways to run work on threads: `threadpool`; reactor's per-reactor
  `asio::thread_pool` (`reactor.h:104-115`); strata's raw threads in flush (`index.hh:2053`) and
  bisection (`bisection.hh:541`) despite `executor.hh:2`; completion's fallback workers; scheduler's
  pool (`scheduler.h:395`). threadpool's research (R1–R3) found two unaware pools and a 7 µs wall /
  20 µs CPU wake per task. reactor takes an external executor (additive); strata's flush and
  bisection run on its executor (`phase3/bisection-pool` starts it); implement R1–R3.
- **CL-14 (S–M).** xxHash: `hashes.hh:44-52` has `xxh32` only if an `xxhash.h` is on the include
  path; Xapiand gets it by accident from lz4's `lib/`; compressors vendors XXH32. A standalone
  `hashes/xxhash.hh` that compressors uses.
- **CL-15 (S).** journal and consensus throw "unsupported" as `Corruption`
  (`journal.h:714-716`, `storage.h:238-241`); strata separates them. Add `journal::Unsupported`
  derived from `Corruption`; record the convention.
- **CL-16 (M).** Four identity sources (journal `random_identity`, strata `identity_seed`, consensus
  `RAND_bytes`, completion's instance counter); the decided per-IO source hasn't landed. An
  `IdentitySource` on `IO`.
- **CL-17 (M, Detent leads).** http's `StreamAllocator` → `allocators::OwnedAllocator`.
- **CL-18 (L, Detent).** Detent's private ledgers and no `allocators` link; its resource adoption pass.
- **CL-19 (S).** completion's types in two namespaces; `api.h:30-50` omits `FilesystemClass`,
  `DirectoryTrust`, `PosixIOOptions`; `make_posix_io` takes no options. Add the overload and aliases.
- **CL-20 (M).** `residency::file` and `File::map` are two read-only mappings; residency's prefetch
  can't reach strata's files. The `backend` concept accepts a span or a `Mapping`.
- **CL-21 (S).** strata hand-rolls LEB128 in hot loops (`bisection.hh:364-409`,
  `reorder.hh:197-204`). `varint::leb128::decode_trusted` and an append encoder, with a benchmark.
- **CL-22 (S).** Xapiand `src/length.cc:40-98` duplicates varint's length codec with weaker checks
  (`shift == 63` allowed; `len += 255` can wrap). Forward to varint; bytes identical.
- **CL-23 (S).** consensus's planned SPKI pins use `pki::spki_sha256`; fix
  `DEPENDENCY_UPGRADES.md:125` (`reactor::pki` → `Kronuz/pki`).
- **CL-24 (M).** A/B statistics written three times (strata `bench/phase2/gate.py` and `bench/ab.py`,
  threadpool `research/summarize.py`, Detent `library_adoption_compare.py`); strata's
  `tools/vm/quiet_trials.sh` gates hosts beside `quiet`. `cpp-libraries/tools/bench/` (stdlib
  Python); `quiet_trials.sh` takes a `quiet run` hold.
- **CL-25 (S–M).** consensus's `tools/mutants.sh` is generic; move it to `cpp-libraries/tools/` with
  per-repo mutant lists.
- **CL-26 (S).** bitpack at width 32: `unpack` 6.71 vs SIMD-BP128's 7.94 integers/ns,
  `unpack_delta` 5.04 vs 6.76 (`bitpack/README.md`). A width-32 copy path and a measured AVX2 decode.
- **CL-28 (S).** `io::fsync` is `fdatasync` on Linux with no full flush on macOS, and `full_fsync` is
  `fdatasync` on Linux (`io.hh:141-147`, `:406-413`). Document it; add `sync_data`/`sync_durable`
  aliases with completion's semantics.

## Leave, with a reason

- **L-a.** `cluster::Raft` beside `consensus`: waits for Detent's step-10 measurement.
- **L-b.** Per-group and shared turn-log backends: waits for T6 (SYS-8).
- **L-c.** Fuzz CMake glue: a shared module adds a dependency to every leaf library.
- **L-d.** Two logging conventions: stable; the catalog should state "new libraries do not log".
- **L-e.** strata's executor: an adapter, not a copy.
- **L-f.** strata's `rate_limiter`: one consumer.
- **L-g.** strata's `ordered.hh` vs `sortable_serialise`: GPL clean room.
- **L-h.** allocators' legacy allocator beside resources: targets isolate them.
- **L-i.** compressors' wrappers: no missing fast path.
- **L-j.** completion's EINTR loops: keeps it header-only and free of io's error seams.
- **L-k.** Sort helpers: one consumer.
- **L-l.** Xapiand's `fsyncher`: its storage path is retiring.
- **L-m.** Per-format checksummed frames: frozen; CL-1 removes the shared part.
- **L-n.** Limits helpers: per domain.
- **CL-27.** Endian helpers per format: frozen encodings.

## Bloat: what grew in the wrong library

| Library | Carries | Belongs in | Finding |
|---|---|---|---|
| journal | CRC-32C table | `hashes::crc32c` | CL-1 |
| journal | `memory_io.h` (a test IO) | `completion::testing` | CL-9 |
| completion | types in `kronuz::journal` | aliases, then `kronuz::io::completion` | CL-19 |
| compressors | vendored XXH32 | `hashes::xxhash` | CL-14 |
| http | `StreamAllocator`, `TlsAdmission` | `allocators`, `reactor::Admission` | CL-17, CL-11 |
| reactor | two admission types | one | CL-11 |
| strata | `faultfs`, `budget` | `completion::testing`, `allocators` | CL-9, CL-6 |
| allocators | legacy tracked allocator | leave (targets isolate it) | L-h |

```
before                                      after
journal -> completion -> allocators,metrics journal -> completion -> allocators, metrics, io::trust
compressors (own XXH32)                     journal -> hashes::crc32c   compressors -> hashes::xxhash
pki -> io                                   pki -> io::trust
http -> reactor                             http -> reactor, allocators::resources
4 private test IOs                          tests -> completion::testing
```

The four new targets are header-only with no dependencies of their own, fetched `EXCLUDE_FROM_ALL`;
no cycles, and no consumer builds more than it links.

## Missing extractions

| Code | Lives in | Needed by | Home |
|---|---|---|---|
| Power-loss filesystem | strata | journal, consensus | `completion::testing` (CL-9) |
| Byte budget with pressure | strata | Detent, Track C | `allocators` (CL-6) |
| Warn-or-refuse directory policy | strata `index.hh:2319-2355` | Detent, pki | `completion` (CL-4) |
| Key-file rule | Xapiand, pki | Detent | `io::trust` (CL-5) |
| A/B statistics, host gating | strata, threadpool, Detent | every performance engineer | `cpp-libraries/tools/bench` (CL-24) |
| Mutant runner | consensus | strata, journal | `cpp-libraries/tools` (CL-25) |
| Trusted LEB128 | strata | termdict and docset callers | `varint` (CL-21) |

## Primitives to optimize rather than bypass

| Primitive | Missing fast path | Gain and source | Bypass removable? | Bucket |
|---|---|---|---|---|
| journal CRC-32C | use `hashes::crc32c` | 19×, measured | n/a | now |
| sha256 | SHA-NI, ARMv8 SHA2, dispatch, namespaced API | 1.6× measured here; ~5–8× estimated | yes for strata's core; no for TLS binaries | now |
| xxh32/xxh64 | self-contained runtime and streaming | removes a build-machine dependency | yes (compressors' copy) | next |
| bitpack | width-32 copy; AVX2 | 16–25% at width 32 (README); AVX2 unmeasured | n/a | next |
| varint | trusted and bulk decode | unmeasured | yes (strata's copies) | next |
| thread wakeups | threadpool R1 | 7 µs wall / 20 µs CPU per task (research note) | yes (reactor's asio pool) | next |
| lz4/zstd wrappers | none found | none | n/a | leave |
| sort/memcmp | none in catalog | n/a | n/a | leave |

## Ranking: consolidate now

| Rank | Item | Size | Who |
|---|---|---|---|
| 1 | CL-1 CRC-32C to `hashes` | S | Both |
| 2 | CL-2 one owner-lock call | M | Both |
| 3 | CL-7 pins | S | Maintainer |
| 4 | CL-8 Track C names `RetainedStatePolicy` | S | strata |
| 5 | CL-12 pki directory sync | S | Xapiand |
| 6 | CL-5 one key-file rule | S | Xapiand, Detent |
| 7 | CL-3 `io::trust` | M | Both |
| 8 | CL-4 policy presets | M | Both, owner |
| 9 | CL-6 strata budget onto `ByteAccount` | M | strata |
| 10 | CL-10 sha256 hardware kernels | M | strata |
| 11 | CL-9 `completion::testing` | L | Both |

## Contradictions with `AGENTS.md` (`d181ffe`)

1. pki has no catalog entry and no "Pick by task" row (rule 1).
2. completion: "refuses shared or untrusted directories" (`:1433`) is now only the default; its Key
   API omits `acquire_directory_owner`, `directory_trust`, `directory_filesystem`, `PosixIOOptions`;
   `make_posix_io` doesn't take the constructor's options.
3. `xxh32::hash` is listed unconditionally (`:603`) but exists only with an xxHash header.
4. "CRC-32C → hashes" (`:117`), but journal and consensus use journal's table.
5. threadpool's entry lacks `TaskGroup`.
6. Two separate pools (`:135`, `:1444`) not noted as separate.
7. The layering diagram (`:203`) omits `allocators` and consensus's optional reactor and OpenSSL.
8. `io`'s `fsync` semantics are not stated.
9. strata's `budget.hh` names a nonexistent `ledger` library.

## Conditions

- **C1.** Every change is additive first: old names forward and stay one release as deprecated, with
  tests that today's bytes and refusals are unchanged.
- **C2.** CL-9's stricter crash model is never weakened to pass tests; new failures are triaged as
  possible real bugs.
- **C3.** CL-10's gain is measured on a SHA-NI or ARMv8 host before DMS-5 changes.
- **C4.** Catalog corrections land in the same series as the library change they describe.

## Open questions

- **Q1.** strata admits FUSE even under `refuse`: keep it as a named row of the policy, or drop it?
- **Q2.** Is a CA directory on a network or FUSE filesystem an environment risk (warn) or a security
  invariant (refuse, as pki does)?
- **Q3.** Is a per-consumer preset the intended answer to Detent's strict default, or should the
  library default change at a major version?

## Owner's answers (2026-10-19)

- **Q1.** Keep it: FUSE's type is never refused, a named row of the shared policy (an unsupported
  lock still refuses under `refuse`).
- **Q2.** Refuse: private key material (a CA or node key directory) on a network or FUSE filesystem
  is a security invariant, not an environment risk. Ordinary data warns.
- **Q3.** Per-consumer presets; the library's strict default stays, so nothing changes for Detent.
- Order: strata-only and Xapiand-only items start now (CL-12, CL-8, CL-10, CL-6); items marked
  "Both" wait for Detent's position on this report.

## Responses

- **Detent (2026-10-19):** accepts CL-1, CL-2, CL-3, CL-4, CL-5, CL-7, CL-9, CL-11, CL-17 and CL-18
  with conditions, in `Detent/docs/CONSOLIDATION_RESPONSE.md`; CL-2 first.
- **strata (2026-10-19), on CL-2's "migrate strata's mutable storage owners to `both`":** strata
  stays directory-only and records why. Format 13 retired `owner.lock` on purpose (small-indexes
  D2, SI-R17), and the `files::pre_freeze` bump makes every pre-lock strata binary refuse a format-13
  index, so a strata directory only ever sees directory-only owners. strata and Detent never own the
  same directory. The unsafe pairing Detent names (a file-only writer and a directory-only writer on
  one directory) therefore cannot arise for strata's directories; Detent moving its own owners to
  `both` closes it for Detent's. strata adopts `acquire_owner(OwnerLockOptions{directory})` when the
  unified call lands, with the same refusals. If a future host must share a directory across both
  protocols, that host uses `both`.
- **strata (2026-10-20), on Detent's create-time condition for directory-only ownership:** Detent is
  right that format 13's version check needs a committed manifest, so a fresh or interrupted
  create is not covered by it: a pre-lock strata creator holding only `owner.lock` and a new
  directory-only creator could both enter before the first manifest. strata's answer is that no such
  creator exists: strata has never shipped a release (its only tags are development bookmarks,
  `format13-main-base-82db600` and `format13-prefold-f2c19c6`), so every pre-lock strata binary is a
  development build, which small-indexes D2 already puts out of scope. Directory-only therefore
  stands with nothing to build. If strata ever has to coexist with an older released build, the
  fallback is to take `owner.lock` as well during create, before the first manifest, and remove it
  after the first commit, which excludes old creators in both orders.
- **For Detent, from strata's replays (2026-10-20):** two pre-existing flakes reproduce on
  unmodified Detent: `test_local_paged_snapshot_plan` throws an uncaught `StoragePressure` (2 of 300
  runs on main's headers), and the distribution/snapshot catch-up group (`poll_publisher`,
  `snapshot_catchup`, `multivoter`) fails or segfaults under `-j3`/`-j4` load (2 of 3 runs on
  unmodified Detent).
- **Landed (2026-10-20):** CL-2 on completion main `ca0889d` (`acquire_owner(OwnerLockOptions)`, `{}`
  refused at compile time, atomic held claims; no consumer protocol changed); CL-12, CL-8, CL-10
  earlier. CL-1 is in review on branches (hashes `cl-1-crc32c-leaf`, journal `cl-1-crc32c-forward`).
- **Detent (2026-10-20), on strata's answer:** accepts directory-only ownership under that
  compatibility boundary: pre-lock development builds are unsupported. Any future old-release
  compatibility must cover both creator arrival orders. CL-2 is ready for Detent's qualified
  adoption; CL-1 stays blocked on its target composition (the `HASHES_FAMILIES` fetch-order
  question); the two flakes stay open as Detent release work; Detent prioritizes adopting stash's
  correctness fix and measuring its footprint.
- **Detent (2026-10-20), on CL-1's fix:** accepts the separate `hashes_crc32c` population name
  (`SOURCE_SUBDIR crc32c-leaf`), including a possible second clone, pending the final SHAs and a
  clean-build qualification. Detent will separate the reproduced 45-second timeout in
  `poll_publisher` from the unconfirmed segfault in its failure record and check its direct
  scheduler and stash use. It noted that a caller ignoring the scheduler's new `bool` still loses a
  refused task silently. For the logger (owner, 2026-10-20): a deferred log is a slow-work
  watchdog, so a refused one is never written immediately; it stays armed, and at its cancel point
  it is written only if its deadline has passed.
