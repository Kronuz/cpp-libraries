# Survey B: hash/id (hashes md5 sha256 crc32c cuuid random sortable)

- Date: 2026-10-30. Kind: performance survey of cluster B (hash and id libraries), the starting point of the October 2026
  performance work.
- Repos (heads surveyed, the last commit before 2026-10-30): `hashes:de5b3ac`, `md5:fbb8ff0`, `sha256:e440b98`,
  `crc32c:b60a8e5`, `cuuid:d46c825`, `random:115f3f3`, `sortable:1aa2f98`.
- Machines: Apple M4 Pro. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| B-W1 sha256 legacy `SHA256` class hex | landed | `sha256:385ec42` | `sha256` (frozen byte-at-a-time conversion, lengths 0..300), `sha256_openssl` |
| B-W2 random `random_int` | landed | `random:0667b61..a6c4f6c` | `random`, `random_engine`, `random_engine_portable`, `random_seed` |
| B-W3 random `random_real` | landed | `random:0667b61..a6c4f6c` | `random`, `random_engine` |
| B-W4 random `random_string` | landed | `random:0667b61..a6c4f6c` | `random`, `random_engine` (strings against a field-by-field reference) |
| B-W5 cuuid v1 `serialise`/`unserialise`/`generate(compact)` | landed | `cuuid:b7b785f` | `cuuid_mt` (`test_wire_identical`, expander against `std::mt19937`) |
| B-M1 md5 one-shot hex at small sizes | landed | `md5:4cd8c47` | `md5` (frozen-conversion differential, lengths 0..300); the OpenSSL oracle `md5:test/openssl.cc` is not on `main` yet |
| B-M2 hashes wide-lane hash beside `wordwise` | open | - | -: `hashes` `main` has no wide-lane function and no performance commit since the survey; the hash audit measured `wordwise` 6.9x to 9.0x behind XXH3 from 1 KiB to 128 KiB |
| B-M3 hashes `mixer::mix(u64)` | not pursued | - | -: the hash audit measured 0.76 ns against XXH3 1.01 and XXH64 1.05 ([audit](2026-10-31-audit-hash.md#hashes)); values unchanged |
| B-M4 cuuid v6 `generate` | landed | `cuuid:b7b785f`, `cuuid:77af63f` | `cuuid_v6_threads` (the claim only; see below) |

B-W2 to B-W4 are one change (survey CLEAR WIN 1); `random:8df54fb` and `random:86bd0f5` added the deterministic engine,
seed and rejection tests after the [hash audit](2026-10-31-audit-hash.md) (R1, R2). B-M4: what landed is the monotonic
time claim as a CAS, which removes one mutex acquire; `generate()` still takes `UUIDGenerator::operator()`'s mutex and,
on macOS, `newUUID()`'s. It measured 8 to 10% (about 10 ns) on the Intel Core i9-9980HK and nothing on the M4 Pro
(`cuuid:77af63f`). The survey's 2-4x design (own clock, atomic counter, one random node source) was not pursued.

Host: Apple M4 Pro, Apple clang 17, `-O3 -mcpu=native`, one thread. Bench: a cluster harness and a cuuid v1 probe
(prototype not kept; the sha256 rows are covered by `sha256:bench/hex_bench.cc` and `sha256:test/openssl.cc`, the
crc32c rows by `crc32c:bench/crc32c.cc`, the random rows by `random:bench/bench.cc`, the cuuid v1 rows by
`cuuid:benchmarks/v1_bench.cc`). Timed under an exclusive timing hold. Best of 5 windows of >= 80 ms, batched so the
clock read (~18 ns) does not dominate.

Identity checks (all passed, `ALL IDENTITY CHECKS OK`): md5 vs OpenSSL EVP md5 (hex), sha256 kernel and legacy class
vs EVP, crc32c vs a `__crc32cd` loop, `xxh64::hash` vs `XXH64` (same output), cuuid v6 serialise/unserialise roundtrip.
Rows that compare against a *different* function (wordwise vs XXH3/absl, sortable vs fixed-width flip, random vs
xoshiro) are speed context only, not output-equivalent.

Spread: no separate A/A. Two full runs (first with a coarse timer, second batched) agree within about 8% on every
row at 100 ns and up (e.g. md5 1 MiB 1.09x then 1.10x; sha256 1 KiB 0.73x then 0.74x). The ratios below are the batched run.

**Void rows** (the compiler hoists/folds the pure call on the fixed input, so the ns/op is not trustworthy):
crc32c 16 B / 64 B (0.5 and 2 ns), hashes xxh64/wordwise/fnv at <= 32 B (0.5 to 3 ns), cuuid "boost to_string" (0.25 ns).
The 1 KiB and larger rows, and everything at 100 ns or more, are sound.

## Table

| library | workload | ours | best comparator | ratio (ours/cmp) | diagnosis | est. win | effort | verdict | Outcome |
|---|---|---:|---|---:|---|---|---|---|---|
| sha256 | kernel digest 16 B / 64 B | 18 / 33 ns | OpenSSL EVP | 0.14 / 0.22 | already SHA2-ext, no EVP ctx overhead | none | - | already good (beats EVP 4-7x) | - |
| sha256 | kernel digest 1 KiB / 64 KiB / 1 MiB | 335 ns / 21.1 us / 330 us | OpenSSL EVP | 0.74 / 0.99 / 1.03 | hardware bound | none | - | already good | - |
| sha256 | **legacy `SHA256` class `operator()` hex**, 16 B / 64 B / 1 KiB | 250 / 264 / 577 ns | own `kronuz::sha256::digest` | 13.5x / 8.0x / 1.7x vs the kernel digest | same kernel; the extra ~230 ns is `getHash()`: copy state, `processBuffer`, byte-at-a-time `result += ` hex of 64 chars | ~150-200 ns per hash (4-6x at small sizes) | S | **CLEAR WIN** (small, legacy API only) | B-W1 |
| md5 | one-shot hex, 16 B / 64 B | 160 / 220 ns | OpenSSL EVP md5 (raw) | 0.93 / 0.94 | scalar either side; ours includes hex string | ~30-50% at small sizes from hex | S | maybe (same hex fix as sha256) | B-M1 |
| md5 | 1 KiB / 64 KiB / 1 MiB | 1344 ns / 76.4 us / 1.23 ms (0.87 GB/s) | OpenSSL EVP md5 | 1.05 / 1.08 / 1.10 | MD5 is a serial dependency chain; Brumme scalar, OpenSSL also scalar asm | <= 10% (unrolled/ scheduled asm-style round macro) | M | not worth it (MD5 is legacy; no SIMD for one stream) | - |
| crc32c | 64 KiB / 1 MiB | 2.9 us / 46 us (22.8 GB/s) | naive single-lane `__crc32cd` loop | 0.47 / 0.46 | 3 interleaved lanes already | none | - | already good (2.1x vs naive) | - |
| crc32c | 1 KiB | 86 ns | naive loop | 0.99 | below the 3 KiB lane threshold | up to ~1.5x with a 2-lane path at 512 B-3 KiB | S | not worth it | - |
| hashes | `xxh64::hash` 100 B / 1 KiB / 100 KiB | 5.6 / 39.3 / 4108 ns | `XXH64` (same output) | 1.00 / 1.00 / 0.99 | constexpr impl matches the C one | none | - | already good | - |
| hashes | `wordwise` 8 / 16 / 32 B | 0.51 / 0.72 / 1.40 ns (small ones may be partly folded) | XXH3_64 / absl::Hash | 0.4-0.8 / 0.8-1.0 | one-multiply-per-word chain is short | none | - | already good for short keys (its use case) | - |
| hashes | `wordwise` 1 KiB / 100 KiB | 141 ns / 18.8 us (5.3 GB/s) | absl::Hash / XXH3_64 | 16.8x / 8.8x (vs XXH3: 6.6x / 8.8x) | single 64-bit lane; each word waits on the previous multiply (latency-bound, ~1 word / 1.1 ns) | 6-10x on long keys, but only by changing the output for len >= 64 | M | maybe (add a new wide-lane function, never change `wordwise` values: phf tables and callers pin them) | B-M2 |
| hashes | `fnv1a64` 16 B / 100 B / 1 KiB / 100 KiB | 4.5 / 61.7 / 956 ns / 100 us | XXH3_64 | 3.5x / 14x / 45x / 47x | byte-at-a-time multiply chain by definition | n/a | - | not worth it (it is FNV; doc already steers to wordwise) | - |
| hashes | `mixer::mix(u64)` batch | 0.53 ns/key | absl::Hash<u64> | 2.2x (0.93x vs XXH3 8 B) | probably two multiplies in the chain vs absl's single 128-bit fold | <= 2x on integer keys | S | maybe (changes output; hash-table callers only, so low hazard if not persisted) | B-M3 |
| random | `random_int(0,999999)` batch / single call | 4.3 ns / 7.3 ns | xoshiro256++ + Lemire range | 5.8x / 10.1x | mt19937_64 (2.5 KiB state, periodic 312-word twist) + `uniform_int_distribution` (division/rejection per call) + TLS guard check | 5-10x | S | **CLEAR WIN** | B-W2 |
| random | `random_real(0,1)` | 2.8 ns | xoshiro, 53-bit | 3.1x | same engine, `generate_canonical` loop | 3x | S | **CLEAR WIN** | B-W3 |
| random | `random_string` 8 / 32 / 256 | 33 / 145 / 998 ns | xoshiro + one multiply pick per 6 bits | 1.3x / 4.9x / 7.4x | one engine draw and one `uniform_int_distribution` (division) per character, `push_back` per char | 5-7x for 32+ chars | S | **CLEAR WIN** | B-W4 |
| cuuid | **v1 `serialise`/`unserialise`/`generate(compact)`** | 904 / 867 / 932 ns | (no peer; v1 without compaction 91 ns) | ~10x vs 91 ns floor | `expand_mt(seed)` builds a `std::mt19937` (624-word seed init, then the first draw twists all 624) to read two outputs; measured 820 ns of the ~900 | 3x (init only the ~400 words the first two outputs need) to 8-10x with a tiny per-thread seed cache (generate then serialise reuse the seed) | M | **CLEAR WIN** (v1 wire only) | B-W5 |
| cuuid | v6 `generate` | 91 ns | boost `random_generator` (v4, no clock) | 6.8x (not equivalent semantics) | libuuid `uuid_generate_time` + global `std::mutex` in `UUIDGenerator::newUUID` (macOS) + a second static mutex in `generate()` | 2-4x (own clock + atomic counter + one random node source) | M | maybe | B-M4 |
| cuuid | v6 serialise / unserialise | 9.3 / 11.8 ns | (none) | - | splitmix expander, cheap | none | - | already good | - |
| cuuid | `to_string` | 21 ns | boost to_string | n/a (boost row void) | 36-char hex with per-byte appends | <= 2x | S | not worth it | - |
| cuuid | parse string | 7.5 ns | boost `string_generator` 14.8 ns | 0.51 | table lookups | none | - | already good (2x ahead) | - |
| sortable | encode double / int64 (variable-length) | 1.9 / 1.85 ns | fixed 8-byte flip+bswap (different format) | ~10x, not output-equivalent | does per-value normalisation (exponent, significand strip, escapes); this is the cost of the variable-length order-preserving format | <= 1.5x by tuning | M | not worth it | - |
| sortable | decode -> number / -> double | 4.2 / 5.3 ns | (none) | - | strict validating decode | small | - | already good | - |

## CLEAR WINS

### 1. random: replace mt19937_64 + `uniform_int_distribution` (3-10x)
- Start files: `random:random.cc` (79 lines), `random.hh`.
- Single biggest change: swap the engine to a small-state generator (xoshiro256++ or PCG64) seeded once per thread
  from `std::random_device` (keep `thread_local`, but use a plain POD state with constant-init guard-free TLS where
  possible), and draw ranges with Lemire's unbiased multiply-shift (`unsigned __int128`) instead of
  `uniform_int_distribution`. `random_real`: `(x >> 11) * 0x1p-53` scaled into [initial, last). `random_string`: take
  one 64-bit draw per ~10 characters (6 bits each) with a bias-free pick (Lemire on 62, or 6-bit rejection),
  write into a pre-sized `std::string` instead of `push_back`.
- Must stay identical: the four function signatures and `random.hh`; the ranges are inclusive for ints,
  `[initial, last)`-style for real as today (keep whatever `uniform_real_distribution` guarantees, including
  `last` exclusive); `random_string` alphabet `[0-9a-zA-Z]` and length; thread safety (per-thread state); the full
  range `random_int(0, UINT64_MAX)` and `initial == last`. There is no seed API and the sequences are
  nondeterministic, so changing the engine changes no observable contract. Do not weaken seeding (the old code
  seeded from `random_device`; if it is only a 32-bit seed, seed all 256 bits from several draws).
- Hazards: not a CSPRNG before or after; do not advertise it as one. The fixed bench figures used a slightly
  biased pick for the string row; the real change must be unbiased.

### 2. cuuid v1: stop constructing `std::mt19937` per condense (3-10x on v1 paths)
- Start files: `cuuid:cuuid_v1.cc` (`expand_mt`, line ~61), `cuuid_common.cc` (`calculate_node`, `crush_fields`, `condense`, `uncondense`).
- Single biggest change: `expand_mt(seed)` only needs `mt19937(seed)`'s first two outputs. Compute state words
  0..398 by the init recurrence (`mt[i] = 1812433253*(mt[i-1]^(mt[i-1]>>30)) + i`), then the first two tempered
  outputs from words {0,1,2,397,398} directly, skipping the other ~225 init steps and the whole 624-word twist
  (about 3x). Then add a one-entry (or 4-entry) thread-local cache keyed by seed, since `generate()` compaction is
  usually followed by `serialise` on the same value (another ~2x). Measured: mt19937 construct + 2 draws = 820 ns
  of a 904 ns serialise.
- Must stay identical: the wire bytes of every v1 condensed UUID (the node is `mt19937(seed)` outputs 0 and 1,
  `(a << 32) | b`); verify with a differential test over millions of seeds against the real `std::mt19937`, plus
  the existing v1 round-trip tests. v6 keeps `expand_splitmix` untouched.
- Hazards: the seed is already unique per fresh UUID (it hashes the time), so a cache helps only repeated work on one id.

### 3. sha256/md5 legacy class: fast hex and no `getHash()` state copy (4-6x on short inputs, legacy API only)
- Start files: `sha256:sha256.cc` (`SHA256::getHash`, `operator()`), `md5:md5.cc` (`MD5::getHash`, line ~355).
- Single biggest change: build the 64/32-char hex string in one `std::string(n, '\0')` with a 2-byte-per-iteration
  table or the `to_hex` that the namespaced API already has; for the one-shot `operator()`, run the namespaced
  `digest` and hex it, without the save/restore of the partial state. The kernel itself is already within 1% of EVP.
- Must stay identical: the digest bytes and lowercase hex, `getHash()` leaving the stream appendable (the stated
  contract), `BlockSize`/`HashBytes` enums, `MD5`/`SHA256` ABI (private members unchanged), `add()` semantics for
  partial buffers.
- Hazards: `MD5` and `SHA256` here are global-namespace names that clash with OpenSSL's `SHA256()`; do not rename.

## Maybe / not worth it
- `hashes::wordwise` is latency-bound on long keys (8.8x behind XXH3 at 100 KiB, 6.6x at 1 KiB) but fine up to
  32-100 B, which is what it is for. Any speedup beyond len < 64 changes hash values. If wanted, add a separate
  wide-lane hash; never edit `wordwise`.
- `mixer::mix(u64)`: 2.2x behind absl's integer hash; only matters for table hashing and would change values.
- cuuid v6 `generate`: 91 ns, two mutexes and a libuuid call per id; a lock-free generator is possible but the
  monotonic guarantee and platform node semantics make it a design change, not a tweak.
- md5 is within 10% of OpenSSL; sha256 kernel and crc32c are already at the hardware limit.
- sortable has no like-for-like comparator; ~2 ns per encode is cheap for a variable-length order-preserving format.

## Ranked wins
1. random_string 32-256 chars: 4.9-7.4x; random_int 5.8x batch / 10x single call; random_real 3.1x.
2. cuuid v1 serialise/unserialise/generate: ~10x against its own non-compacting floor (904 ns vs ~90 ns); realistic 3-10x.
3. sha256/md5 legacy hex path: ~4-13x on short inputs vs the library's own kernel (250 ns vs 18 ns).

## LESSONS

The lessons of this cluster are in [LESSONS.md](../LESSONS.md): [random](../LESSONS.md#random),
[cuuid](../LESSONS.md#cuuid), [sha256](../LESSONS.md#sha256), [md5](../LESSONS.md#md5). Two are recorded only here:

- Serial hash designs (one running multiply, FNV, wordwise) cannot use the multiplier throughput; wide lanes give 6-10x
  on long inputs but change the output, so decide the lane structure before the hash value is frozen in tables or on
  the wire.
- Bench hygiene: a fixed-input pure function folds to nothing; consume a changing input or an opaque value, and read
  the clock once per batch (an 18 ns clock read swallows a 1 ns operation).

## API-compat hazards
- `MD5` / `SHA256` live in the global namespace (the namespaced `kronuz::sha256` exists to avoid OpenSSL's clash).
- `hashes::wordwise`, `xxh64`, `fnv1a`, `djb2h`, `mixer` outputs are consumed by constexpr-phf tables and must not change.
- v1 cuuid wire/condensed bytes depend on the exact `std::mt19937` stream; v6 on splitmix. Both frozen on disk.
- `random_*` has no seed or reproducibility contract today, so the engine may change; keep thread-safety and ranges.
- sortable: the byte format defines sort order and is persisted; encode/decode must stay bit-exact.
