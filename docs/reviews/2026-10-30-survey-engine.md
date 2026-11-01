# Cluster G survey: search-engine building blocks

- Date: 2026-10-30. Kind: cluster survey (G, engine) of the October 2026 performance work; read-only, libraries
  untouched.
- Repos: termdict, fst, docset, bitpack, fusefilter, analysis at `main` as pulled on 2026-10-30 (the survey recorded
  no commits; the [engine audit](2026-10-31-audit-engine.md) names the same starting points as fst `12657aa`, docset
  `cd38597`, bitpack `cd13f36`).
- Machines: Apple M4 Pro, Apple clang 17 `-O3`. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| G-M1 docset `set::and` at density 0.1 (bitmap x bitmap) | landed | `docset:d1aa406`, `docset:511c575` | `docset_diff` |
| G-M2 docset point `set::test(d)` | landed | `docset:d1aa406`, `docset:a6de748` | `docset_codegen`, `docset` |
| G-M3 bitpack `unpack` at widths >= 13 | landed | `bitpack:494a727`, `bitpack:41cc024` | `bitpack_differential` |
| G-M4 fst `for_each` / `range` iteration | landed | `fst:b08055f`, `fst:fe22b32` | `fst_diff` |
| G-M5 fst build (registry) | landed | `fst:b1e8ff3`, `fst:8058003`, `fst:aa3aa3a` | `fst_diff`, `fst_collide`, `fst_memory` |

G-M1's diagnosis below (scalar popcount on NEON) was wrong: the cost was the per-bit bitmap-to-array conversion, and
a NEON popcount pass was neutral or slower ([LESSONS](../LESSONS.md#docset)). G-M3's cause was aliasing after all:
the kernels read the packed block through `uint8_t`, which may alias the output, so each input word was loaded again
after every store; `bitpack:494a727` loads each word once ([LESSONS](../LESSONS.md#bitpack)).

Libs: termdict fst docset bitpack fusefilter analysis (all in active development; latest main pulled).
Host: Apple M4 Pro (arm64), Apple clang 17 `-O3`. All timings under an exclusive timing hold; ratio is comparator/ours
(>1 = ours faster) and every row's output was checked identical first (bytes for bitpack, counts for docset,
no false negatives for fusefilter, values for fst/termdict).
Bench code and raw output: prototype not kept. The comparators live in the repo benches: `bitpack:bench/bench.cc`
(simdcomp), `docset:bench/bench.cc` (CRoaring), `fst:bench/bench.cc` and `fst:bench/cmp_bench.cc`,
`termdict:bench/bench.cc`, `fusefilter:bench/bench.cc`, `analysis:bench/bench.cc`. Libs untouched.
Noise: the host was shared with other timed work; A/A is 1.00-1.27 and the in-run spread is up to 1.9x on some
rows, so only ratios clearly outside that are read as real.

## Results

| library | workload | ours | best comparator | ratio (A/A) | diagnosis | win size | effort | verdict | outcome |
|---|---|---|---|---|---|---|---|---|---|
| docset | AND/OR/ANDNOT/iterate/count, 2^24 universe, 1e-6..0.5 density | 18 ns count .. 5.8 ms iterate | CRoaring | mostly 0.1-0.8 (we win); A/A ~1.0 | already beats it | n/a | n/a | already good | - |
| docset | `set::and` materialized, density 0.1 (bitmap x bitmap, result ~655/chunk) | 880 us | CRoaring 497 us | 1.76x slower | bitmap AND writes a full 8 KiB scratch, popcounts per word (scalar `cnt`+`addv` on NEON: `combine_words_generic`, no NEON path), then `from_bitmap` converts to an array with a ctz loop and a second allocation. CRoaring takes the cardinality first and writes the array directly | 1.5-1.8x on that row only | low | maybe | G-M1 |
| docset | `set::test(d)` probes, 1k-50k members in 2^20 | 11 ns (1k/1k), 17 ns (50k/50k) | CRoaring 4.7 / 9.2 ns | 0.43x / 0.53x (we lose 2x) | `std::binary_search` over the uint16 array (branchy) plus a branchy `lower_bound` over `keys_`. Micro-test: branchless search is 1.3-1.5x faster than `std::binary_search` at n=16..3000 (alone 3.5 ns of the 11) | ~1.5-2x on point probes | low | maybe | G-M2 |
| docset | AND / OR of 1k-300k lists (materialized), conjunction via `advance()`, build from sorted | raw output not kept | CRoaring | 1.2-1.9x (and), 1.0-1.6x (or), 2-7x (advance), 1.3-6.4x (build) faster | SIMD intersect, flat arrays | n/a | n/a | already good | - |
| bitpack | unpack 128 ints, widths 1-31 | 0.048-0.080 ns/int | simdcomp (NEON via neon128.h) | 0.66-0.89x (comp faster by 12-50%, A/A up to 1.18) | unresolved: not call-table overhead (direct template call same), not pointer aliasing (`__restrict` on a copy: no change). Needs asm inspection | up to 1.2-1.4x at widths >= 13 | medium | maybe | G-M3 |
| bitpack | pack, widths 1-31 | 0.042-0.075 ns/int | simdcomp `simdpackwithoutmask` | 0.56-0.77x at b<=13, ~1.0-1.2x above | ours masks every input (safe); simdcomp's "withoutmask" does not. Not a like-for-like gap | 1.3-1.7x only if an unmasked variant is added | low | not worth it (pack is encode side) | - |
| bitpack | unpack_delta | 0.25-0.29 ns/int | simdcomp `simdunpackd1` | 1.01-1.03 (A/A 1.0-1.13) | both bound by the carry chain across blocks (my harness feeds the previous block's last value) | none | n/a | already good | - |
| bitpack | max_bits | 0.020-0.025 ns/int | simdcomp `maxbits` | 1.0-1.44x faster | | n/a | n/a | already good | - |
| bitpack | bytes on disk | identical to simdcomp for all widths tried (1,3,7,8,13,17,24,31) | | same | layout equals SIMD-BP128 | | | | - |
| fusefilter | lookup 10k..10M keys, present / absent | 1.1-1.8 ns | blocked bloom 10 b/key; absl flat_hash_set | 2.7-3.2x (bloom present), 8-11x (bloom absent), 1.0-3.3x (hash set) | 3 loads, one mulhi per slot, pipelines across keys | n/a | n/a | already good | - |
| fusefilter | build | 19-36 ns/key (10k..1M) | no like-for-like binary-fuse implementation to hand; hash-set insert is 3-4 ns | not comparable (hash insert builds no filter) | partitioned counting pass + peeling; literature binary fuse builds at ~30-100 ns/key, so this is in range | n/a | n/a | already good | - |
| fst | `get` present, 236k words | 134 ns | std::map 241; absl btree_map 146; sorted vector bsearch 168; absl hash map 10.5 | 1.8x / 1.1x / 1.2x faster; 12x slower than a hash map | tree-walk with one dependent load per byte; the structure's purpose is size (6.2 B/key vs ~40+) | n/a | n/a | already good | - |
| fst | full ordered iteration `for_each` | 55.8 ns/key | std::map in-order 3.2 ns/key | 17x slower | `range()` keeps a std::vector of `frame{node(~100 B), ...}` and decodes a full `node` struct per transition (copied twice); per-byte `key.push_back/pop_back`. No SIMD or table decode. Not a query hot path (term enumeration, merges, regex via `intersect`) | est. 1.5-2x | medium | maybe | G-M4 |
| fst | build | 226 ns/key (words), 1.1 Mkeys/s on Wikipedia (README) | std::map sorted-hint insert 149 ns/key | 0.66x | profile (sample): ~25% `unordered_map<std::string,...>::find` (cache-missy), ~12% `string::push_back`, ~10% malloc/free from `stack_[d] = pending{}` resetting each node's `vector<arc>`, rehashes, the registry stores one heap `std::string` signature per written node and never evicts | est. 2-3x | medium | maybe (see hazards) | G-M5 |
| termdict | `find` present/absent, 236k words | 216 / 219 ns | absl btree_map 144; sorted-vec bsearch 174; fst::get 141 | 0.67x / 0.81x / 0.65x | block scan after `floor_value` on the index FST; this set is cache-resident, so the README's 4M-term advantage vs Lucene (memory-latency bound) does not show. Already the subject of three earlier tuning campaigns (`termdict:docs/perf/`) | n/a | n/a | already good / explored | - |
| termdict | build | 56.8 ns/key | fst build 232 ns/key | 4.1x faster | | n/a | n/a | already good | - |
| analysis | text -> terms, stem none, 7.8 MB synthetic dictionary text | 9.9 ns/byte (101 MB/s) | naive ASCII split + tolower + same map (not equal semantics) | 0.73x of the naive floor | already near what the map insert costs; README claims 1.8x over Xapian's `TermGenerator` (not re-run: no Xapian here) | n/a | n/a | already good | - |
| analysis | stem some (English) | 27 ns/byte (37 MB/s) | none available | n/a | dominated by snowball stemming, which is the snowball library's cluster | n/a | n/a | not worth it here | - |

## Clear wins

None by the bar "clear, large, safe": the cluster is already at or ahead of its comparators almost everywhere, which
fits libraries written against those comparators. The best candidates, all `maybe`:

1. **fst builder registry** (2-3x on build; G-M5). Start: `fst:fst.hh` `builder::write`, `registry_`, `freeze_after`.
   Biggest change: replace `unordered_map<std::string,uint64_t>` with a flat open-addressing table of
   `(64-bit hash, address)` that verifies a hit by comparing the freshly encoded node bytes against `out_` at the
   address, and stop re-creating `pending` (clear its `arcs` instead of `= pending{}`). Must stay identical: the
   output bytes (exact minimization, same node dedup), `insert` ordering checks and exceptions. Hazard: capping or
   evicting the registry (rust-fst style) is faster still but changes the produced FST bytes and size; do not.
2. **docset bitmap AND at mid density + point `test()`** (1.5-2x on those rows; G-M1, G-M2). Start: `docset:docset.hh`
   `detail::intersect(container, container)`, `combine_words` (add a NEON popcount-accumulate: `vcntq_u8` over
   16-byte chunks and one horizontal add per chunk), `container::test`, `set::test`. Biggest change: AND as popcount
   first, then write an array or a bitmap directly; branchless search in the array container and in `keys_`.
   Must stay identical: set contents, the 4096 array/bitmap threshold, `count()`. Internal only.
3. **fst `range`/`for_each`** (1.5-2x; G-M4). Start: `fst::map::range`. Biggest change: store only `address` + cursor in
   the frame and decode transitions lazily; avoid the `node` copy.
4. **bitpack unpack** (<= 1.2-1.4x at widths >= 13; G-M3). Needs an asm-level look first: the cause is not the call table
   nor aliasing (both tested). Layout must stay byte-identical (it already equals SIMD-BP128, which is a asset).

## API / format compat hazards

- bitpack's on-disk layout is fixed and byte-identical to simdcomp/SIMD-BP128; any "faster layout" is a format break.
  `bitpack::pack` masks its inputs; an unmasked fast path must be a new function, not a behavior change.
- fst's serialized form ("FST1", nodes children-first, chain/general headers, 16-byte trailer) is the format; a builder
  that dedups differently (bounded registry) still yields a valid FST but different bytes and size. Anything that
  promises reproducible builds or checksums over the bytes (strata, termdict's index) would notice.
- fst's `range`/`for_each` callback contract: `f(key, value)` returns bool (false stops); `key` is a view valid only
  during the call. Keep it.
- termdict stores its index as an fst over every Nth block key and its blocks in a documented format; both libraries
  are being changed concurrently on perf branches (`forward-seek`, `seek-decode`, `validate-at-open`); rebase before
  touching.
- docset's container shapes (array <= 4096, bitmap above, no run containers) are visible through serialization or a
  frozen form (`fuzz_frozen`); results of ops must keep the same container choice if frozen bytes are compared.
- fusefilter's serialized filter (seed, segment_length, segment_count_length, fingerprints) and its hashing
  (`mix`, `mulhi`) define what a persisted filter answers; a faster build must produce the same table bytes or
  accept a version bump.
- docset has x86 paths behind runtime `target("sse4.2")`/avx2 checks and a NEON path; the arm64 popcount gap above
  does not exist on x86 (the library's own README ratios were taken on x86), so any change needs both measured.

## LESSONS

The lessons for these libraries are in [LESSONS: fst](../LESSONS.md#fst), [docset](../LESSONS.md#docset) and
[bitpack](../LESSONS.md#bitpack). Two points from this survey are not there:

- Comparing like for like matters: simdcomp's `pack` "without mask" and our masked `pack` are different contracts, and
  my delta benchmark was limited by the cross-block carry for both libraries. Check the contract before ranking.
- The designs that won were the ones built against a named comparator with identical bytes (bitpack vs SIMD-BP128,
  docset vs CRoaring): the comparator both set the bar and made equality checkable.
