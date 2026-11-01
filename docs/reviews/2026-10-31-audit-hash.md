# Audit: hash (random, cuuid, sha256, md5, hashes)

- Date: 2026-10-31. Kind: cluster audit of the October 2026 performance and correctness work (read-only).
- Repos: `random:115f3f3..94f156a`, `cuuid:d46c825..d03d8d1`, `sha256:e440b98..f581eea`, `md5:fbb8ff0..bed7236`,
  `hashes:de5b3ac` (no campaign commits). Start is the last commit before 2026-10-30 on `main`; head is `main` at audit
  time.
- Machines: Apple M4 Pro, a shared Linux x86-64 VM (AMD EPYC 7763). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| R1 tests do not pin unbiasedness, the engine or the seed width | closed | `random:8df54fb`, `random:86bd0f5`, `random:337c2fd` | `random_engine`, `random_engine_portable` (scalar multiply), `random_seed`, `random` (residues at 3 * 2^62 and ceil(2^65 / 3)); `random:tools/mutants.py` (30 mutants) |
| R2 `__builtin_expect` breaks MSVC | closed | `random:8df54fb`, `random:86bd0f5` | `random:.github/workflows/msvc.yml` (builds and runs the tests on MSVC; it caught the swapped `_umul128` halves fixed in `86bd0f5`) |
| R3 README/CHANGELOG timings do not reproduce | closed | `random:d1a4aed` | - (docs: `random_bench` prints the median of nine batches against a `noinline` copy; the README states the machine and the command) |
| C1 lock-free v6 `generate()` has no test | closed | `cuuid:00d3b64` | `cuuid_v6_threads` (kills c7 and c8 in 6 runs of 6) |
| C2 the CAS does nothing measurable; `generate()` is not lock-free | closed | `cuuid:00d3b64`, `cuuid:77af63f` | - (comment, CHANGELOG and AGENTS describe what the CAS removes; the claim is covered by `cuuid_v6_threads`) |
| C3 v6 ids are not byte-sortable inside the 1.64 ms window | closed | `cuuid:00d3b64` | `cuuid_v6` (`test_v6_canonical_order`); `docs/CUUID_V6.md` states the 1.64 ms granularity |
| C4 `expand_mt_compute` is a new exported symbol | no change | - | - (additive; `cuuid:AGENTS.md` records that it exists for `test/test_mt.cc`) |

R3 and C2 are documentation findings, so no test fails when they are reverted. For C2, `cuuid:00d3b64` put the mutex
back and `cuuid:77af63f` restored the CAS after timing the Intel Core i9-9980HK: the mutex costs 8 to 10% (about 10 ns)
per `generate()` at one to four threads there, and nothing on the M4 Pro. hashes (verdict NOT YET, no finding ID): `main`
has no wide-lane function yet; see [survey hash](2026-10-30-survey-hash.md) B-M2.

Start = last commit before 2026-10-30 on origin/main; head = origin/main at audit time. The probes, mutant scripts and
raw logs are not kept; each section names the repo test that now covers its probe.

| repo | start | head | verdict |
|---|---|---|---|
| random | 115f3f3 | 94f156a | **BETTER WITH CONDITIONS** |
| cuuid | d46c825 | d03d8d1 | **BETTER WITH CONDITIONS** |
| sha256 | e440b98 | f581eea | **BETTER** |
| md5 | fbb8ff0 | bed7236 | **BETTER** |
| hashes | de5b3ac | de5b3ac (no campaign commits) | **NOT YET** (untouched, no regression) |

No correctness bug introduced by the campaign was found in any repo. The conditions are test gaps on the two claims each change rests on.

Hosts: Apple M4 Pro (benches under an exclusive timing hold, 3 rounds start/head/start, so every ratio has an A/A);
a shared Linux x86-64 VM (AMD EPYC 7763, gcc 11.2, clang 12) for ASan/UBSan/TSan, x86 correctness and direction-only
numbers (load 8 to 16, not timing grade). The Intel Core i9-9980HK was not used for timing (see Not run).

---

## random

**Verdict: BETTER WITH CONDITIONS.** The new generator is correct and 1.1x to 10x faster. Its own tests cannot detect losing the properties the change exists to provide.

### Blocking (conditions)

**R1. The tests do not pin unbiasedness, the engine, or the seed width.** `test/test.cc` uses chi-square at 10 sigma on coarse buckets (`test_uniformity`, `test.cc:184-279`).
Mutants of `random.cc` run against the repo's own test (Linux VM, gcc 11; mutant script not kept, `random:tools/mutants.py` now holds 30 mutants):

| mutant | repo test | audit probes |
|---|---|---|
| m1 drop the Lemire rejection loop (`random.cc:102`) | **survives** | killed (`probe_stats`: R=3*2^62 value mod 3, normal-approximation z about 1.9e5) |
| m8 `rotl(s0+s3, 22)` (`random.cc:42`) | **survives** | killed (`probe_engine`) |
| m9 `rotl(s3, 44)` (`random.cc:49`) | **survives** | killed (`probe_engine`) |
| m11 seed `hi` word = 0 (32 bits of entropy, `random.cc:59`) | **survives** | killed (`probe_engine`: random_device call count) |
| m13 scalar `mulhi` drops `p01 >> 32` (`random.cc:90`) | survives (never compiled: every CI target has `__int128`) | not exercised on int128 hosts; `probe_mock_scalar` passes on unmodified head |
| m3 field 62 accepted; m4/m5 field 61 rejected; m6 range off by one; m7 constant seed; m10 52-bit real; m12 time offset dropped | killed | killed |
| m2 `lo + 1 < threshold` | survives | survives (differs with probability about 2^-64 per draw; equivalent) |

The wide-range test (`test.cc:210`, R = 3*2^62) checks only the three coarse thirds, which a missing rejection step leaves uniform; the bias shows in `value % 3`
(P(0) = 1/2 without the loop). AGENTS.md says "keep the rejection step, it is what makes them unbiased" and nothing enforces it.
Fix: (a) add `random_int(0, 3<<62 - 1) % 3` and `% 2` at R = ceil(2^65/3) to the chi-square block (from `probe_stats`);
(b) a known-answer test for the engine (state {1,2,3,4} gives 41943041, 58720359, 3588806011781223, 3591011842654386, ...) and for "one seeding = 8 random_device words per thread"
(`probe_engine` does both with a scripted `<random>`, through a `next()` hook); (c) compile the scalar `mulhi` in one CI job (`-U__SIZEOF_INT128__`).

### Evidence it is correct (all pass on head)

The probes are not kept; `random:test/engine_test.cc`, `random:test/scripted_device.hh` and `random:test/seed_test.cc` cover them.

- `probe_engine` (unmodified `random.cc` over a scripted `std::random_device`): xoshiro256++ output equals the published vector and an independent transcription for 100k draws; an all-zero seed is redrawn;
  each thread seeds lazily, exactly once, with 8 words; 8 threads x 200k interleaved draws equal single-thread references per seed (per-thread isolation).
- `probe_mock` (`random.cc` with `next()` hooked): `random_int` equals the Lemire rule written independently with `2^64 mod R` in `__int128` on 119,641 adversarial draws
  (bucket edges, rejected values, 26 ranges up to 2^64-1; 9,711 involve a rejection) including the number of draws consumed; the rule is exactly uniform on a 16-bit word for every R in 1..2000;
  197,902 `random_time` cases (negative, full-width, `milliseconds::min()..max()`) equal the unsigned-offset spec; 1,204 `random_string` cases (lengths 0..300, accept-all, 90%-reject, all-'0') equal a naive field-by-field reference, value and draw count.
  Also passes with the scalar `mulhi` (`-U__SIZEOF_INT128__`), and under ASan+UBSan.
- `probe_stats` (30M draws per row, Wilson-Hilferty z, fail at |z| > 6): all rows within |z| < 2.4 on arm64 and x86 (ranges 2..10^6, 3*2^62, ceil(2^65/3), 2^64-1, 10^19; `random_time`; 53 mantissa bits of `random_real`; string symbols, first/last position, 23 adjacent-pair tables, per-thread).
- TSan (clang 12 `-no-pie` under `setarch -R`; gcc 11 and clang 12 libtsan fail on that kernel even for a hello world): `random_test` and `probe_engine` clean. ASan+UBSan: repo test, `probe_stats`, `probe_mock` clean.
- Pre-existing, unchanged: `random_real(1, 2)` can return `last` (u = 1 - 2^-53 rounds up); documented as closed `[a, b]` in `docs/API.md`. `initial > last` is UB before and returns a wrapped value now. A fork child shares the parent's per-thread state (both versions).

### Non-blocking

- **R2.** `__builtin_expect` (`random.cc:74,100`) is GCC/Clang only: MSVC cannot compile `random.cc` now (start could). The `__SIZEOF_INT128__` fallback shows portability was intended. Use `[[unlikely]]` (C++20, already required).
- **R3.** README/CHANGELOG say `random_string(256)` 104 ns and `random_int` 2.4 ns; measured 117 to 121 ns (+13 to 16%) and 2.52 ns (+5%) on the M4 Pro. The "before" column is a frozen in-TU copy that the compiler inlines (random_int 3.9, string 29/118/885);
  the real start library is slower (4.36, 33.5/148/1062), so the speedups in the docs are understated, not overstated.
- README footer says Dubalu 2015-2018; the file headers say 2015-2019.

### Numbers (M4 Pro, Apple clang 17 -O3, ns/op, median [min-max], 6 start runs / 3 head runs; A/B probe not kept, `random:bench/bench.cc` times the same rows)

| row | start | head | ratio | A/A spread (start) |
|---|---:|---:|---:|---|
| random_int(0,999999) | 4.36 [4.35-4.43] | 2.52 [2.52-2.52] | 1.73x | 2% |
| random_int(0,2^64-1) | 3.39 | 2.65 | 1.28x | 0% |
| random_int(1,6) | 8.12 | 2.54 | 3.20x | 0.5% |
| random_real(0,1) | 2.90 | 2.55 | 1.14x | 0.3% |
| random_time(100ms,500ms) | 7.36 | 2.52 | 2.92x | 0.7% |
| random_string(1) | 6.92 | 3.94 | 1.76x | 1% |
| random_string(8) | 33.55 | 7.98 | 4.20x | 0.4% |
| random_string(16) | 64.15 | 11.73 | 5.47x | 0.7% |
| random_string(32) | 148.4 [147.6-153.0] | 31.73 | 4.68x | 3.5% |
| random_string(64) | 271.8 | 43.45 | 6.25x | 0.3% |
| random_string(256) | 1062 [1036-1087] | 119.5 [117-121] | 8.89x | 5% |
| random_string(1024) | 4116 | 389 [386-416] | 10.6x | 1.7% |

Repo bench (`random_bench`, same source linked with start/head): head 1.61x/1.13x/1.12x/3.6x/3.8x/8.3x on the six rows (start library: 0.82x to 0.97x against the frozen copy).
No row regressed. Comparators: inlined xoshiro256++ + Lemire 0.74 ns per int (the floor without the call and TLS access); `mt19937_64` + `uniform_int_distribution` 3.39 ns; naive `mt19937_64` string 30/135/990 ns; a naive inlined xoshiro string 22/36/190 ns
(the library's 8.0/31.7/119 beats it). x86 direction (EPYC, gcc 11, loaded, not timing grade): int 12.6-15.6 ns to 2.9-6.1 ns, `random_string(256)` 2.5-2.6 us to 0.32-0.38 us, no row slower.

Bar: at the best comparator for an out-of-line, thread-safe API. The remaining 1.8 ns over the inline floor is the call plus the macOS TLV access. No speed change needed; R1 is the condition.

---

## cuuid

**Verdict: BETTER WITH CONDITIONS.** The v1 wire is byte-identical and the v1 paths are 1.5x to 92x faster; the v6 change has no test and no measurable effect.

### Blocking (condition)

**C1. The lock-free v6 `generate()` (`cuuid_v6.cc:112-119`) has no test.** `test_v6_generator` is single-threaded (`test/test_v6.cc:92`, N = 2000). The campaign replaced a mutex with a CAS and added no threaded test.
Mutants (gcc 11; mutant script not kept): c7 `next = prev` (duplicate times) and c8 (plain store instead of the CAS loop) **survive** `cuuid_test`, `cuuid_v6_test`, `cuuid_mt_test` and a 1.6M-record wire dump;
`probe_v6_threads` (8 threads x 20,000 ids; distinct bytes, distinct wires, claimed time recovered from the time field and the clock field XOR the process clock sequence, strictly increasing per thread; now `cuuid:test/test_v6_threads.cc`) kills both.
Head passes it: 800,000 ids and 800,000 distinct claimed times on x86 Release and on arm64; under TSan (clang 12, 8 x 4,000 ids) it passes with no race reported. Fix: add it to `test/` (about 20 lines of the probe) and register it in CTest.

### Non-blocking

- **C2. The CAS does nothing measurable and `generate()` is not lock-free.** `UUIDGenerator::newUUID` still takes `UUIDGenerator::mtx` on Apple (`cuuid_v1.cc:619-626`) and `operator()` still takes a static mutex (`cuuid_v1.cc:711-714`) before v6's CAS runs.
  v6 `generate` 1 thread: 90.9 ns both (the libuuid 100 ns tick floor); per-thread wall ns/id at 2/4/8 threads: start 240/649/1488, head 211/535/1364, with A/A spread 460 to 717 and 933 to 1628 (about 30%): no signal. On Linux libuuid costs 13 us per id and swamps everything.
  The comment "Lock-free" (`cuuid_v6.cc:112`) and the CHANGELOG line overstate it. Revert, or keep it and say what it removes.
- **C3 (pre-existing, both revisions). v6 `generate()` ids are not byte-sortable inside the 1.64 ms compaction window.** `probe_v6_threads 1 100000`: 96.5% (start) and 55.0% (head) of consecutive ids from one thread sort below their predecessor
  (the rate depends on the process clock sequence). `make()` runs the shared `crush_fields`, which folds the low 14 time bits into the clock field XOR the clock sequence. `docs/CUUID_V6.md` says "no XOR fold, no clock scrambling; a clean 1 ms sort granularity",
  `cuuid_v6.cc:101-104` says "sortable". `COMPARISON.md` states the 1.64 ms floor correctly. The ids stay unique and decode exactly; only the sub-window order claim is wrong.
- **C4.** `expand_mt_compute` is a new exported symbol (`cuuid_common.h:237`), there for the test. Additive, harmless.

### Wire identity vs start (`wire_dump`, seed-deterministic, no clock; probe not kept, covered by `cuuid:test/test_mt.cc` `test_wire_identical`)

1,606,524 records per run, each a digest of everything the codec produces for one input: v1 `compact_crush` then `serialise`/`unserialise`/`to_string`/dispatch under both codecs; v1 as given; edge times (0, 1, base+-k, 2^60-1, pre-2016 wraps) x clocks x nodes (multicast, 0, max);
128 salts x clocks (many distinct mt19937 seeds); 400,000 random byte strings through `UUID::unserialise`, `cuuid_v6::unserialise`, `cuuid::unserialise` (both codecs) including error outcomes; random v3/v4/v5/v7/v8/v1/v6 bytes (full form); v6 `make`/`from_fields`/`serialise`/`unserialise`.
Result: start == head byte for byte on **x86_64 gcc 11** (sha256 of the digest file 513aa032...dbe4) and on **arm64 Apple clang 17** (29667605...87b1), and clean under ASan+UBSan on the Linux VM.
(The two platforms' files differ from each other only because the probe builds its inputs with unspecified argument evaluation order; start vs head is what matters and each was compared on one compiler.)
Repo `test_mt.cc` compares `expand_mt_compute` with the real `std::mt19937` on edge seeds, 20,000 dense, every flipped bit, 300,000 random. Mutants c1 (cache ignores the seed), c2 (init one word short), c3 (live tempering bit), c4, c5, c6 (index shift, out of bounds) are all killed by `test_mt`/`test`.
(My first c3 changed bit 0 of a mask applied to `v << 7`, which is dead; it survived as an equivalent mutant.) `cuuid_common.cc.o` is byte-identical start vs head, so v6 `serialise`/`unserialise` are the same machine code.
Tests registered in CTest: `cuuid`, `cuuid_v6`, `cuuid_mt`; all pass on Release arm64/x86, ASan+UBSan and TSan (Linux VM). Public API and layouts unchanged; no new dependency (endian, char-classify pinned as before).

### Numbers (M4 Pro, ns, median of 6 start / 3 head; `probe_v6_bench`, not kept; repo `v1_bench` (`cuuid:benchmarks/v1_bench.cc`) agrees within 1%)

| row | start | head | ratio | claim |
|---|---:|---:|---:|---|
| v1 serialise, new id (4096 distinct) | 932.6 [930.6-933.3] | 616.0 [615.9-616.2] | 1.51x | 900 to 590 (+4%) |
| v1 unserialise, new id | 957 | 619 | 1.55x | |
| v1 serialise, repeated id | 931.6 | 10.1 | 92x | 911 to 9 |
| v1 unserialise, repeated id | 961 | 11.4 | 84x | |
| v1 generate(compact) + serialise | 1943 | 682 | 2.85x | |
| v1 generate(compact) (repo bench) | 1006-1013 | 675-692 | 1.46x | |
| v6 serialise / unserialise | 10.4 / 13.0 | 10.6 / 12.0 | 1.0x | unchanged |
| v6 generate, 1 thread | 90.9 | 90.9 | 1.0x | |
| v1 to_string / parse | 21.3 / 7.2 | 20.8 / 7.3 | 1.0x | |

Spread start vs start: v1 rows under 0.5%, v6 serialise 6%. Non-target rows did not move. The 8-entry cache never hurts the miss case (the 4096-distinct row is the miss case and still wins 1.5x).
x86 direction (EPYC, loaded): v1 serialise new 4.25-4.65 us to 0.79-0.83 us, repeated 2.2 us to 23-39 ns. One loaded-VM v6 serialise sample was 40-45 ns against 27-35 ns for start; that code is byte-identical, so this is noise, but I did not re-time it on a quiet x86 host.

Bar: v6 (the default) is 10 ns and 12 ns. v1's remaining 616 ns is the serial init chain (398 dependent multiplies at about 1.5 ns); it is at its floor for one id. A batch decode that interleaves chains would be the only further step; not needed for a legacy codec.

---

## sha256

**Verdict: BETTER.** Hex conversion of the legacy `SHA256` class and `to_hex` is 1.5x to 4.2x faster, byte-identical, at or above OpenSSL's hex-returning path. The kernels are untouched.

- Correctness (`probe_hex`, probe not kept; the sha256 half is covered by `sha256:test/openssl.cc`; both revisions pass on arm64 Apple clang and x86 gcc 11): 64,201 lengths (0..4200 and random up to 8000) at random misalignments: one-shot pointer and `string_view`, reuse after `operator()`, streaming with random chunk splits and `getHash()` (hex and raw) at random cut points, `reset()`, all equal to OpenSSL EVP; the namespaced `digest`+`to_hex` and `hasher` over 4,201 lengths. Hex is lowercase and exactly 64 characters.
- Repo test adds a frozen byte-at-a-time conversion over lengths 0..300 plus continue-after-`getHash()`. Mutants (nibble order, nibble mask, one byte short, one byte dropped in `getHash` or `to_hex`): the four `getHash()` mutants are killed by `test.cc`; the `to_hex` mutant survives `test.cc` alone, and `kernels.cc` (registered as `sha256_kernels`) compares `to_hex` with known digests (`kernels.cc:117,132,140,174`), so the registered suite kills it (by reading; I did not run `sha256_kernels` against the mutant).
- CI: success on 385ec42 (push) and nightly; tests `sha256`, `sha256_kernels`, `sha256_openssl` registered. Headers unchanged.

Numbers (M4 Pro, ns, 3 rounds; A/A under 1%; `bench_hex` (probe not kept) and the repo `sha256_hex_bench`):

| size | legacy start | legacy head | ratio | OpenSSL EVP raw / EVP + hex | head vs EVP+hex |
|---|---:|---:|---:|---:|---:|
| 16 B | 256.2 | 60.0 to 62.3 | 4.2x | 88.7 / 129 | 2.1x faster |
| 64 B | 273 | 75.8 to 78.9 | 3.6x | 91.6 / 141 | 1.9x faster |
| 1 KiB | 594 | 401 to 407 | 1.48x | 417 / 467 | 1.16x faster |
| 64 KiB | 22.4 us | 22.2 us | 1.0x | 22.1 / 22.2 us | equal |
| 1 MiB | 355.3 us | 355.4 us | 1.0x | 353.6 us | equal (0.5%) |

Namespaced `digest` kernel: 19.1 ns at 16 B (EVP 88.7). x86 (EPYC with SHA-NI, loaded): legacy 16 B 288-306 to 168 ns, 64 B 322-342 to 209 ns, 1 MiB kernel 660 us against EVP 662 us. The x86 SHA-NI/portable kernels are unchanged and covered by `sha256_kernels`; I did not time the non-SHA-NI portable kernel on the i9.
Claim check: README "about 60 ns" at 16 B confirmed (60 to 62).

## md5

**Verdict: BETTER.** Same change, smaller win, same proof; bulk throughput stays about 8% behind OpenSSL's assembly (unchanged, scalar).

- Correctness: the 64,201-length probe above (md5 legacy class vs EVP; probe not kept), start and head, arm64 and x86. Repo test adds the frozen-conversion differential (0..300). Mutants high nibble masked, low nibble first, one byte short: killed (ASan abort or assertion).
- CI success on 4cd8c47 and nightly; `md5` registered; `md5_hex_bench` builds with `-DMD5_BUILD_BENCH=ON` exactly as the README command says. Header unchanged.

| size | legacy start | legacy head | ratio | OpenSSL EVP raw / + hex |
|---|---:|---:|---:|---:|
| 16 B | 164.9 | 117.1 to 117.7 | 1.41x | 122 / 160 (head 1.37x faster than EVP+hex) |
| 64 B | 218 | 172 to 173 | 1.27x | 191 / 231 |
| 1 KiB | 1439 | 1394 | 1.03x | 1318 / 1362 (head 6% slower) |
| 64 KiB | 83.5 us | 83.4 us | 1.0x | 77.0 us (head 8.3% slower) |
| 1 MiB | 1334 us | 1334 us | 1.0x | 1232 us (head 8.3% slower, 0.79 GB/s) |

x86 (EPYC, loaded): a 10% gap at 64 KiB and 1 MiB. Claim check: README "about 115 ns" at 16 B confirmed (115.7 to 118.4). Bar: MD5 is one serial dependency chain; 8% behind hand-scheduled asm is near; not worth more.

---

## hashes

**Verdict: NOT YET.** origin/main has no campaign commit (head = start = de5b3ac). Nothing regressed; nothing improved. CI green (nightly runs 41206875606, 41070977413).

- Against xxHash 0.8.4 (`bench_hashes`, probe not kept; M4 Pro, exclusive, ns): `xxh64::hash` (the constexpr code, `STRING_KIT_HAS_XXHASH=0`) equals `XXH64` on 13 sizes x 2,000 random offsets and runs within 0 to 7% of it (4 B 1.17 vs 1.11; 100 B 6.48 vs 6.49; 128 KiB 5558 vs 5553).
  `wordwise` beats XXH3_64bits up to 32 B (4 B 0.76 vs 1.30; 16 B 1.09 vs 1.30; 32 B 1.79 vs 1.82), ties near 48 B (2.53 vs 2.66), then falls behind: 1.3x at 64-100 B, 3.6x at 256 B, 6.9x at 1 KiB, 8.8x at 16 KiB, 9.0x at 128 KiB (5.1 GB/s against 46 GB/s).
  `fnv1a64` is 47x behind at 128 KiB (by definition). `mixer::mix(u64)` 0.76 ns against XXH3 1.01 and XXH64 1.05.
- For its stated job (string switch keys, a few to 32 bytes) it is already at or ahead of the best comparator. For anything over 64 bytes it is 1.3x to 9x behind, and the values are frozen (call sites store them), so `wordwise` cannot change.
- **Single change to reach the bar:** add a new wide-lane function (4 independent 64-bit lanes over 32-byte blocks, new values) beside `wordwise`, as [survey B](2026-10-30-survey-hash.md) recommended; evidence is the 6.9x to 9x long-key gap above, with parity at 48 B so short keys keep using `wordwise`.
- Hygiene: no `CHANGELOG.md` (the other four have one). Three pre-campaign remote branches remain (`cl-1-crc32c-extract`, `cl-1-crc32c-leaf` 3 commits ahead of main, `fix/fold32-collisions` already contained in main). A local clone carried an unpushed commit 0eb141d ("Pin char-classify at a890496") that was not on origin; the review reads origin.

---

## Hygiene and compatibility (random, cuuid, sha256, md5)

- CI: every default branch has green runs on its last code commit (random a6c4f6c, cuuid b7b785f, sha256 385ec42, md5 4cd8c47) and green nightlies. The head commits are docs-only `[skip ci]`, so the head SHA itself has no run; the next nightly covers it.
  random's first push (0667b61) failed on the Threads link and a6c4f6c fixed it; the default branch history has one red commit.
- No stray branches or open PRs in random, cuuid, sha256, md5. READMEs are present tense; a grep for history narration (previously, used to, no longer, was fixed, ...) over README/ARCHITECTURE/AGENTS/docs/code found none. CHANGELOG.md holds the history in all four.
- README bench commands reproduce: `random_bench`, `cuuid_v1_bench`, `sha256_hex_bench`, `md5_hex_bench` all build from the stated cmake line.
- API and bytes: `random.hh`, `sha256.h`, `md5.h`, `cuuid_v1.hh`, `cuuid_v6.hh` unchanged; the only header delta is `cuuid_common.h` (one added declaration). Serialized/wire bytes identical (cuuid, above; hex strings identical). `random`'s sequence changes, but it has no seed API and says so.
  Language level unchanged (C++20 everywhere, `constinit` already required). No new dependency in any leaf.

## Not run

- **Intel Core i9-9980HK**: no timing and no GCC 16 build. Consequences: no quiet x86 numbers for any repo, no non-SHA-NI sha256 portable-kernel timing, no quiet re-time of the v6 serialise sample.
- The arm64 correctness probes ran at `nice -n 19` outside a hold, about 3 minutes of one core, no timing. Timing ran under an exclusive timing hold.
- ASan hangs on the M4 Pro; ASan, UBSan and TSan ran on the Linux VM only. TSan there needs clang 12 with `-fno-pie -no-pie` under `setarch x86_64 -R`.
- No MSVC, Windows, FreeBSD or big-endian build (R2 and the scalar `mulhi` are by reading plus the `-U__SIZEOF_INT128__` build).
- No re-run of the campaign's own fix-round artifacts; no fuzzing beyond the 1.6M-record wire dump and the 64k-length hash probes.
