# Survey I: second wave (journal ... allocators)

- Date: 2026-10-31. Kind: performance survey of the second-wave libraries against same-space comparators, part of the
  October 2026 performance and correctness work (read-only; prototypes in scratch copies).
- Repos: bitpack, hashes, allocators (and threadpool, http-parser by reference) at `main` on 2026-10-31; the source
  records no commit heads.
- Machines: Apple M4 Pro (arm64 macOS, Apple clang 17). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| I-W1 bitpack `unpack`: load each input word once | landed (NEON); the SSE2 twin was tried and dropped (bitpack CHANGELOG 2026-10-31, "Not changed") | `bitpack:494a727`, `bitpack:41cc024` (width 32 `memcpy`) | `bitpack_differential`, `bitpack_differential_portable`; load counts in `bitpack:bench/asm_check.cc` |
| I-W2 hashes: additive wide-lane `wordwise` | open: no commit on hashes `main` (head `971ea8c`) references it; `bench/candidate_wordwise8.hh` and `bench/compare.cc` exist only on an unmerged branch on origin (`b5-wip`) | - | - |
| I-M1 hashes `wordwise` at 16-128 B | not pursued: no commit on hashes `main` references it | - | - |
| I-W3 allocators: `construct` perfect forwarding | landed | `allocators:7cdb0f8`, `allocators:ea0c5e6` (bench) | `allocators_construct` |

I-W3 is on allocators `main`: `construct` is a variadic forwarding template with `noexcept` following the element
constructor, and `allocators_bench` has the `vector<std::string>` rows (CHANGELOG 2026-10-31: 1000 `push_back(T&&)`
make 0 copies and 2023 moves, as with `std::allocator`). I-W1 landed for the NEON `unpack` kernels only; `unpack_delta`
and the SSE2 kernels keep their row-wise loads.

Host: Apple M4 Pro (arm64 macOS), Apple clang 17, `-O3` (allocators `-O2`), libs at `main` after `git pull`
(`allocators` had uncommitted edits to `allocators.h` in its working tree; they were left alone).
Benchmarks: the survey's own harnesses (`bp.cc`, `hs.cc`, `al.cc`, `al2.cc`, `bp_asm*.cc`; probe not kept: the bitpack rows
are covered by `bitpack:bench/bench.cc` and `bitpack:bench/asm_check.cc`, the allocator rows by `allocators:bench/bench.cc`
and `allocators_construct`).
All timings under an exclusive timing hold. Ratios are `ours / comparator` unless stated, so above 1.0 means ours is slower.
"A/A" is the same binary measured twice in the same run. Every comparator's output was checked equal to ours first
(bitpack: unpacked ints identical for all widths timed; hashes: not comparable bit-for-bit, so the rows are
speed-only and the new hash gets its own quality checks; allocators: a copy/move counter).
The machine was shared throughout; arm rows are best-of-N inside one exclusive hold.

## Coverage

| library | status |
|---|---|
| bitpack | surveyed: unpack gap cause found and fixed in a scratch copy (below) |
| hashes (wordwise) | surveyed vs XXH3 / XXH64 / abseil; additive wide-lane hash prototyped (below) |
| allocators (`vanilla_allocator`) | surveyed: the 2x is `construct(const T&)` copying (below) |
| threadpool (`ThreadPool::enqueue`) | already measured in [the systems survey](2026-10-30-survey-systems.md) (162 ns/task vs 76 ns naive pool, 1.0x vs asio); the WorkPool research in the repo targets it; not re-measured |
| http-parser | already measured in [the parsers survey](2026-10-30-survey-parsers.md) (1.5-2.0x behind llhttp). I did not find a low-risk win without a profile and did not attempt one; verdict stays "maybe, large effort" |
| unicode, snowball, analysis, termdict | already covered by the [text](2026-10-30-survey-text.md), [algo](2026-10-30-survey-algo.md) and [engine](2026-10-30-survey-engine.md) surveys; no new row |
| journal completion consensus cluster flume pki residency bkd queryparser sortable | no same-space comparator available, vendored or from Homebrew (WAL, raft, flume, PKI, file residency, BKD tree, query parser, sortable serialisation): skipped per the survey method |
| wordwise | there is no `wordwise` repo (`github.com/Kronuz/wordwise` 404). It is the `wordwise` / `wordwise_ci` class inside `hashes:hashes.hh`; surveyed there |

## Summary table

| library | workload | ours | best comparator | ratio (A/A) | diagnosis | est. win | effort | verdict | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| bitpack | `unpack` 128 ints, widths 1-31, 256 blocks | 0.043-0.081 ns/int | simdcomp `simdunpack` 0.038-0.069 | 1.14-1.33x slower (A/A 0.83-1.02) | **aliasing reloads**: `in` is `uint8_t*` (may alias anything) and `out` is written with `uint32_t` stores, so after each `str` the compiler must reload the next input word; asm at b=13 has 20 `ldr` for 13 words, simdcomp has 13. Not call-table, not `__restrict` on a copy (the inlined helpers lose it) | 12-25% at b<=24 | S | **CLEAR WIN** | I-W1 |
| bitpack | same, with all B input words loaded into registers first (scratch copy) | 0.037-0.075 | simdcomp 0.038-0.069 | patched/ours 0.75-0.94; patched vs simdcomp 0.97-1.12 (a tie) | removes the reloads; asm now 7 `ldp` for 13 words. B=32 gets slightly worse (1.07x), keep the old path for 32 | | | see above | I-W1 |
| hashes (wordwise) | 64-bit hash of 512 B / 4 KB / 64 KB | 58 ns / 689 ns / 11.7 us (5.6 GB/s) | XXH3 9.6 / 87 / 1387 ns; abseil 5.5 / 44 / 1055 ns | 6.1x / 7.9x / 8.4x slower than XXH3 | one serial dependency chain (xor, 64-bit multiply, xorshift per 8 B = about 6 cycles per word); no lanes | 6-8x on long keys | S | **CLEAR WIN** (additive class) | I-W2 |
| hashes (wordwise) | 16 / 32 / 64 / 128 B | 1.01 / 1.55 / 3.2 / 8.1 ns | XXH3 0.62 / 0.84 / 1.31 / 2.8 ns | 1.6x / 1.8x / 2.4x / 2.9x slower | same chain, plus byte-at-a-time word assembly in the constexpr path | 1.5-2x | M | maybe | I-M1 |
| hashes (wordwise) | 4 / 8 B | 0.63 / 0.64 ns | XXH3 0.64 / 0.63 | 1.0x | single block | none | | already good | - |
| hashes (`ww8` prototype) | 512 B / 4 KB / 64 KB | 17.2 ns / 104 ns / 1.91 us (34 GB/s) | XXH3 9.6 / 87 / 1387 ns | 1.8x / 1.2x / 1.4x slower than XXH3; 3.4x / 6.6x / 6.1x faster than wordwise | 8 independent lanes, 64 B per iteration, overlapping final block, same multiply-xorshift step per lane | | | prototype | I-W2 |
| hashes (`ww8` prototype) | 4-64 B | 1.3-1.7 ns (64 B: 5.2 ns) | wordwise 0.63-3.2 | slower than wordwise below 64 B and than XXH3 everywhere below 4 KB | my short-key path does two mix steps plus a heavier finaliser; 64 B pays the 8-lane setup | | | needs a tuned short path before it is worth shipping | I-W2 |
| allocators | `vector<int, vanilla_allocator>` push_back, n = 16 / 1000 / 100000 | 4.16 / 0.51 / 0.35 ns | `std::allocator` 4.67 / 0.52 / 0.33 | 0.89 / 0.98 / 1.07 (A/A 1.03 / 0.99 / 1.00) | none: trivial types are a tie | none | - | already good | - |
| allocators | `vector<std::string, vanilla_allocator>` push_back(rvalue), n = 16 / 1000 / 20000 | 63 / 66 / 85 ns | `std::allocator` 28 / 25 / 44 ns | **2.25x / 2.59x / 1.93x** (A/A 1.02 / 0.95 / 1.04) | `allocator::construct(pointer, const_reference)` is the only construct overload, so `allocator_traits::construct(a, p, std::move(x))` copy-constructs: every push and every reallocation relocation deep-copies the element instead of moving it | 2-2.6x for non-trivial element types | S | **CLEAR WIN** | I-W3 |
| threadpool | `enqueue` | see the [systems survey](2026-10-30-survey-systems.md) | | | | | | not re-measured | - |
| http-parser | see the [parsers survey](2026-10-30-survey-parsers.md) | | | | | | | not re-measured | - |

The "2x behind std" report in the survey plan is the `std::string` (non-trivial type) row; `vector<int>` is a tie. Cause confirmed by a
deterministic count (a type that counts constructions, 1000 push_backs; probe not kept, covered by `allocators_construct`):
`std::allocator` 0 copies / 2023 moves; `vanilla_allocator` 2023 copies / 0 moves.

## CLEAR WINS

### 1. bitpack `unpack` (and `unpack_delta`): load once, compute from registers
- Start files: `bitpack:bitpack.hh`, NEON `unpack_row` / `unpack_rows` / `unpack_delta_rows` (about lines 209-250); the SSE twin has the same shape.
- Single biggest change: in `unpack_rows` (and `unpack_delta_rows`) first load the B input words into a local `uint32x4_t w[B]`
  (`for i < B: w[i] = load_u32x4(in + 16*i)`), then have `unpack_row<B,R>` read `w[row::word]` and `w[row::word + 1]`. The compiler
  now cannot be forced to reload after each output store. The working scratch version was a copy of `bitpack.hh` with about 20
  lines changed (prototype not kept). Apply the same to the SSE path (the x86 compiler has the same alias problem: `__m128i` loads
  via `reinterpret_cast<const __m128i*>` are may_alias types and `out` is a store through a different type).
- Keep B == 32 on the old path (plain copy; the array version was 1.07x slower there).
- Must stay identical: output of `unpack`/`unpack_delta` for every width (tests round-trip every width and compare scalar vs SIMD), packed bytes, API.
  Measured: unpacked ints identical to simdcomp's for all 20 widths timed.
- Measured: patched is 0.75-0.94x the time of the current code and 0.97-1.12x of simdcomp's (B=32 1.07x). 256 blocks per call, 15 reps; the "ours" A/A
  spread in this run was 0.83-1.02 (the first measurement of each width was noisy), but the patched/ours direction is the same at all 13 widths timed.
- Not yet done: `unpack_delta` (carry chain bound, the [engine survey](2026-10-30-survey-engine.md) measured 1.01-1.03 already), and `pack` (already ties above b=13; below is the masking that survey found).

### 2. hashes: an additive wide-lane hash (`wordwise_wide`, prototyped as `ww8`)
- Start files: `hashes:hashes.hh` (`class wordwise`, ~line 226). Add a new class; do not change `wordwise` output (perfect-hash keyword tables and stored hashes depend on it).
- Design that measured: 8 lanes seeded `seed + P*k`, each `a = (a ^ w) * P; a ^= a >> 29` over 8 B words, 64 B per iteration, last block read overlapped
  (`len - 64`) so there is no byte tail loop, lanes folded with distinct odd weights and a rotate, then the existing finaliser. For `len <= 32`, overlapping loads.
  (prototype not kept)
- Quality checks run: 2M structured long keys and 2M short counter keys, 0 duplicate 64-bit hashes; avalanche 31.9-32.0 of 64 bits for key lengths 1, 3, 7, 12, 20, 40, 64, 100, 300.
  This is not SMHasher; it must pass SMHasher (or the repo's `bench/collisions.cc`) before shipping.
- Result: 3.4x / 6.6x / 6.1x faster than `wordwise` at 512 B / 4 KB / 64 KB, **still 1.2-1.8x behind XXH3 and 1.7-1.8x behind abseil**: the claim "beats XXH3" is not met.
  Below 64 B it is slower than `wordwise`; a tuned short path (one mix step per 8 B, 1-3 / 4-8 / 9-16 length classes like XXH3) is the missing piece. Gate the wide path at `len >= 128`.
- `wordwise` itself is fine where it is used (short keywords in a perfect-hash dispatch): it ties XXH3 at 4-8 B, which is the case its README documents. The gap shows at 16 B and above.
- Constexpr: the prototype uses `memcpy` loads, so a constexpr wide class needs the byte-assembly form `wordwise` uses (or `std::bit_cast` on an array), and will be slower at compile time.

### 3. allocators: add `construct` perfect forwarding (or delete `construct`/`destroy`)
- Start file: `allocators:allocators.h`, class `allocator<_Tp, _Allocator>` (`construct(pointer, const_reference)`, `destroy`, `address`, `max_size`). These are C++03-era members.
- Single biggest change: delete `construct` and `destroy` (C++20 `allocator_traits` supplies placement-new forwarding and `destroy_at`), or make `construct` a variadic forwarding template.
  Check `rebind`: it is already provided. C++20 deprecates/removes `address`, `max_size` members (traits supply them); keep `max_size` (it is used by `allocate`).
- Must stay identical: `allocate`/`deallocate` behaviour, equality (`operator==` returns true), `rebind::other`, header API for users that call `a.construct(p, v)` directly with a `const T&`
  (the variadic form accepts it).
- Expected: `vector<std::string>` push_back 2-2.6x faster (ties `std::allocator`); no change for trivial types.
- Hazard: a pool-check change to `allocators.h` was in flight at the same time; rebase against it.

## API compat hazards
- bitpack: none for the unpack change (internal). A new unmasked `pack` would have to be a new function (the engine survey's note).
- hashes: new hash must be a new class name; changing `wordwise::hash` values breaks perfect-hash tables, `hh()` literals and anything persisted.
- allocators: removing `construct(pointer, const_reference)` could break code that calls it explicitly with a non-forwardable argument (unlikely); the variadic form is a superset.

## LESSONS

The lessons for these libraries are in [bitpack](../LESSONS.md#bitpack), [hashes](../LESSONS.md#hashes) and
[allocators](../LESSONS.md#allocators). Two from this survey are not recorded there:

- **One serial dependency chain caps a hash at latency / word.** A multiply-xorshift chain is ~6 cycles per 8 B (5 GB/s) no matter how simple; throughput comes from independent lanes (4-8), not from a lighter mix.
- **"Fast on short keys" does not transfer to long ones, and vice versa.** A hash tuned for 4-8 B keyword dispatch ties XXH3 there and loses 8x at 4 KB; document the length range or provide both.
