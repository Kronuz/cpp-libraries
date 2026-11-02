# Gate: allocators

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/allocators#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `e8fb173` | 2026-10-28 04:26:55 -0700 | Credit Germán Méndez Bravo and bound Dubalu's years |
| HEAD (`origin/main` when pinned, 2026-11-01) | `c558fa7` | 2026-11-01 03:51:03 -0800 | Shape the README to the family standard [skip ci] |

Library sources changed between them (docs, tests, benches, CI excluded): 1 file changed, 246 insertions(+), 30 deletions(-).

## Method (common to every machine)

- Two worktrees of one clone, at START and at HEAD. The bench source is HEAD's (or, where stated, a copy of it with the rows START cannot compile removed, or a micro-bench written for the gate, not kept); each is compiled twice, once with `-I <START tree>` (binary A) and once with `-I <HEAD tree>` (binary B), same compiler, flags and source path. A/A is a byte copy of A.
- Flags: `c++ -std=c++20 -O3 -DNDEBUG -pthread` (Apple clang 17.0.0: M4 Pro `clang-1700.3.19.1`, i9 `clang-1700.6.4.2`). Comparator libraries are not linked or fetched. Only `flat-map`'s bench finds them by itself (`__has_include`): `absl::btree_map` is on the default include path of both machines and `boost::container::flat_map` on the i9's only, so that bench has abseil rows on the M4 and boost and abseil rows on the i9 (controls: they run no code of this repo).
- Rounds: every round runs each bench entry with A, B and AA (order `a b aa` on odd rounds, `aa b a` on even ones), under one `quiet strict` hold per repo and machine (on macOS a strict hold is exclusive). `runab.sh` writes one file per run; `ab_compare.py compare --format unit` pairs run i of A with run i of B (and of AA) and reports the median ratio.
- **Ratio = START time / HEAD time, so above 1 means HEAD is faster.** Throughputs are converted to ns per item. `A/A max dev` is the largest |ratio - 1| of A against its own copy over the same rounds: the measurement's noise. Rows marked `(control)` run code the change cannot reach (a standard-library or baseline arm); they show the noise floor and are left out of the geomean.
- A row is listed as "<0.97 outside A/A" when its ratio is below 0.97 and also below 1/(1 + A/A max dev).

## What was measured

- `bench/bench.cc` (`allocators_bench`): `std::vector<T, allocators::allocator<T, vanilla_allocator>>` `push_back` against `std::vector<T>`, ns per element, best of 11, for `vector<int>` at n = 16, 1000 and 100000 and `vector<string>` `push_back(T&&)` at n = 16, 1000 and 20000. The `std::allocator` column is a control (standard library only). The bench's own A/A column is not used; the gate's A/A copy replaces it.
- `$GATE/own/pool_direct.cc` (a micro-bench written for the gate, 60 lines, not kept): `memory_pool_allocator<Node>::allocate(1)` / `deallocate` called directly on one allocator, no container and no allocator copies, ns per operation, best of 9: steady-state free-list reuse, refill of 1,000 and 100,000 blocks, a fresh pool per run (chunk growth plus destruction) and frees in random order, with `std::allocator` as the control. This is the one use of the pool that is correct at START (see below).
- **Not comparable: `bench/compare_pmr.cc` (pool against `std::pmr`).** It builds `std::list` and `std::map` on `memory_pool_allocator`. At START the pool lives inside the allocator value and libc++ copies the allocator, so these containers corrupt the heap after a few elements (fixed 2026-10-30: "the pool lived inside the allocator value, so a copy allocated from its own deque and freed it when the temporary died"). The START binary of `compare_pmr` traps (`SIGTRAP`, no output) on the quick run (`--quick`, run once on the M4 as a crash check, not timed), consistent with that bug, so no START row exists; HEAD runs and checks its arms' checksums.
- Deterministic check, copies and moves of 1000 `push_back(T&&)` of a counting type (`allocators_bench --counts`): `std::allocator` 0 copies / 2023 moves; `vanilla_allocator` **2023 copies / 0 moves at START**, 0 copies / 2023 moves at HEAD (`construct` forwarded only `const T&`).
- Library change in scope (`allocators.h`, 276 lines changed): `construct` perfect-forwards (copy/move/`noexcept` as `std::allocator`); `memory_pool_allocator` shares a pool family through a `shared_ptr` handle (chunked storage, bump pointer, LIFO free list, one size class per block size) instead of holding a `std::deque` in the allocator value; propagation traits, equality, rebind identity and a debug-only overlap check were added. `allocators.cc` is unchanged.


### Apple M4 Pro

#### vector-push-back (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| vector<int> n=16 allocators::allocator<vanilla> | 4.230 | 4.270 | 0.991 | 0.95-1.04 | 4.2% | 3 |
| vector<int> n=16 std::allocator (control) | 4.530 | 4.530 | 1.018 | 1.00-1.03 | 4.7% | 3 |
| vector<int> n=1000 allocators::allocator<vanilla> | 0.520 | 0.540 | 0.963 **<0.97** | 0.95-0.98 | 3.6% | 3 |
| vector<int> n=1000 std::allocator (control) | 0.520 | 0.530 | 1.000 | 0.98-1.00 | 4.0% | 3 |
| vector<int> n=100000 allocators::allocator<vanilla> | 0.350 | 0.360 | 0.972 | 0.97-1.00 | 2.9% | 3 |
| vector<int> n=100000 std::allocator (control) | 0.330 | 0.330 | 1.000 | 0.97-1.00 | 3.1% | 3 |
| vector<string> push_back(&&) n=16 allocators::allocator<vanilla> | 58.58 | 24.82 | 2.380 | 2.31-2.38 | 3.0% | 3 |
| vector<string> push_back(&&) n=16 std::allocator (control) | 24.69 | 24.71 | 1.008 | 0.97-1.02 | 3.9% | 3 |
| vector<string> push_back(&&) n=1000 allocators::allocator<vanilla> | 71.16 | 38.19 | 1.849 | 1.84-1.87 | 1.8% | 3 |
| vector<string> push_back(&&) n=1000 std::allocator (control) | 36.09 | 36.44 | 0.997 | 0.98-1.00 | 3.3% | 3 |
| vector<string> push_back(&&) n=20000 allocators::allocator<vanilla> | 85.47 | 42.11 | 1.997 | 1.98-2.09 | 4.0% | 3 |
| vector<string> push_back(&&) n=20000 std::allocator (control) | 39.52 | 39.52 | 0.990 | 0.99-1.03 | 1.9% | 3 |

#### pool-direct (`pool_direct`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| alloc+free steady (free list) | 1.154 | 1.295 | 0.896 (<0.97, inside A/A) | 0.89-1.06 | 188.9% | 3 |
| alloc n=1000 then free n, reused | 1.655 | 0.997 | 1.687 | 1.63-1.72 | 0.8% | 3 |
| alloc n=100000 then free n, reused | 2.120 | 1.544 | 1.376 | 1.37-1.38 | 1.9% | 3 |
| fresh pool, alloc n=1000 (bump + destroy) | 2.207 | 2.186 | 1.010 | 1.00-1.02 | 2.0% | 3 |
| fresh pool, alloc n=100000 (bump + destroy) | 2.441 | 1.849 | 1.317 | 1.30-1.33 | 2.1% | 3 |
| alloc n=100000, free in random order | 8.812 | 8.411 | 1.037 | 1.03-1.07 | 3.3% | 3 |
| control std::allocator alloc+free steady (control) | 11.77 | 11.80 | 1.008 | 1.00-1.01 | 0.6% | 3 |

**Geomean START/HEAD (Apple M4 Pro): 1.300** over 12 library rows (controls, 7 rows: 1.003)

Rows >1.03: 7; within 0.97-1.03: 3; <0.97: 2 (1 outside the A/A spread, 1 inside it).

### Intel i9-9980HK

#### vector-push-back (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| vector<int> n=16 allocators::allocator<vanilla> | 13.92 | 13.80 | 0.995 | 0.99-1.06 | 7.6% | 3 |
| vector<int> n=16 std::allocator (control) | 14.03 | 13.92 | 1.008 | 0.99-1.01 | 2.1% | 3 |
| vector<int> n=1000 allocators::allocator<vanilla> | 1.180 | 1.200 | 0.983 | 0.96-1.01 | 5.0% | 3 |
| vector<int> n=1000 std::allocator (control) | 1.020 | 0.990 | 1.041 | 0.93-1.05 | 3.0% | 3 |
| vector<int> n=100000 allocators::allocator<vanilla> | 0.650 | 0.650 | 1.000 | 1.00-1.00 | 1.5% | 3 |
| vector<int> n=100000 std::allocator (control) | 0.460 | 0.450 | 1.022 | 0.98-1.04 | 4.4% | 3 |
| vector<string> push_back(&&) n=16 allocators::allocator<vanilla> | 184.2 | 86.74 | 2.124 | 2.09-2.17 | 2.3% | 3 |
| vector<string> push_back(&&) n=16 std::allocator (control) | 88.94 | 87.28 | 1.019 | 1.01-1.04 | 6.4% | 3 |
| vector<string> push_back(&&) n=1000 allocators::allocator<vanilla> | 221.6 | 130.7 | 1.693 | 1.67-1.74 | 4.8% | 3 |
| vector<string> push_back(&&) n=1000 std::allocator (control) | 127.3 | 129.3 | 0.985 | 0.98-1.00 | 2.1% | 3 |
| vector<string> push_back(&&) n=20000 allocators::allocator<vanilla> | 276.6 | 143.8 | 1.959 | 1.89-1.96 | 1.4% | 3 |
| vector<string> push_back(&&) n=20000 std::allocator (control) | 134.9 | 137.2 | 0.991 | 0.96-0.99 | 2.7% | 3 |

#### pool-direct (`pool_direct`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| alloc+free steady (free list) | 0.741 | 2.020 | 0.352 **<0.97** | 0.35-0.42 | 11.6% | 3 |
| alloc n=1000 then free n, reused | 3.212 | 2.587 | 1.246 | 1.23-1.27 | 3.6% | 3 |
| alloc n=100000 then free n, reused | 3.630 | 3.156 | 1.156 | 1.12-1.18 | 2.1% | 3 |
| fresh pool, alloc n=1000 (bump + destroy) | 3.757 | 2.908 | 1.292 | 1.26-1.30 | 3.9% | 3 |
| fresh pool, alloc n=100000 (bump + destroy) | 3.515 | 1.996 | 1.761 | 1.74-1.77 | 12.6% | 3 |
| alloc n=100000, free in random order | 17.43 | 15.46 | 1.115 | 1.11-1.15 | 6.2% | 3 |
| control std::allocator alloc+free steady (control) | 40.81 | 39.55 | 1.032 | 1.00-1.06 | 2.1% | 3 |

**Geomean START/HEAD (Intel i9-9980HK): 1.199** over 12 library rows (controls, 7 rows: 1.014)

Rows >1.03: 8; within 0.97-1.03: 3; <0.97: 1 (1 outside the A/A spread, 0 inside it).

## Findings: allocators

- **M4 Pro (3 rounds, 12 library rows): geomean 1.300.**
  - **`vector<std::string>` `push_back(T&&)` is 1.85-2.38x faster** (n=16 58.6 -> 24.8 ns, n=1000 71.2 -> 38.2, n=20,000 85.5 -> 42.1); the `std::allocator` control in the same runs reads 0.99-1.01, and HEAD now equals it (24.8 / 38.2 / 42.1 against 24.7 / 36.4 / 39.5). The cause is deterministic and measured here: `construct` forwarded only `const T&`, so START made 2023 copies and 0 moves for 1000 `push_back(T&&)` and HEAD 0 copies and 2023 moves, as `std::allocator`.
  - **The pool, called directly (`pool_direct`)**: refill of 1,000 blocks 1.69x (1.655 -> 0.997 ns per operation), of 100,000 blocks 1.38x, a fresh pool of 100,000 blocks (chunk growth, bump, destruction) 1.32x, 1,000 fresh 1.01x, frees in random order 1.04x; the `std::allocator` control 1.008.
- **M4 rows below 0.97 outside the A/A spread: 1.** `vector<int>` n=1000: 0.520 -> 0.540 ns per element, ratio 0.963 (A/A max dev 3.6%; the bench prints two decimals, so one step is 2% of 0.52). The `vector<int>` rows at n=16 (0.991) and n=100,000 (0.972, 0.35 -> 0.36 ns) are at the same quantisation; HEAD's CHANGELOG puts the `vector<int>` rows within 2.6% on the M4 (0.1% on the i9) and says what remains over `std::allocator` is libc++'s bulk relocation for allocators with no `construct` member. Cause: the `construct` template (the `noexcept` clause now follows the element constructor), at most a few percent of a 0.5 ns operation; accepted in the CHANGELOG ("dropping the members gives string parity but slows `vector<int>` growth by up to 9% (M4) and 54% (i9)").
- **M4: one row below 0.97 inside its A/A spread, probably a real cost:** `pool_direct` steady state (`allocate(1)` then `deallocate` of one block through the free list), START 1.154 ns, HEAD 1.295 ns, ratio 0.896. The A/A max dev of 189% comes from one A/A run of 0.404 ns in round 3 (the A runs read 1.154, 1.148, 1.167 and the other A/A runs 1.162, 1.154); HEAD read 1.091, 1.295, 1.303. HEAD's `allocate` reaches the free list through a cached size-class pointer in a `shared_ptr`-owned family where START kept the list head inside the allocator, so about 0.14 ns per allocate+free pair is plausible; the same code is 1.3-1.7x faster once the free list refills over many blocks.
- **Not comparable (correctness):** `compare_pmr` (pool on `std::list` / `std::map` against `std::pmr`) traps at START (heap corruption through allocator copies, fixed 2026-10-30), so it has HEAD rows only. At HEAD a container copy gets its own pool and move assignment and swap carry the pool with the nodes; START had no such rules.
- **i9 (3 rounds, one strict hold 13:25 to 13:26 on 2026-11-01, 12 library rows): geomean 1.199.**
  - **`vector<std::string>` `push_back(T&&)` is 1.69-2.12x faster** (n=16 184.2 -> 86.7 ns, n=1000 221.6 -> 130.7, n=20,000 276.6 -> 143.8); the `std::allocator` control reads 0.99-1.02, and HEAD equals it (86.7 / 130.7 / 143.8 against 87.3 / 129.3 / 137.2). This reproduces the CHANGELOG's i9 numbers (187 / 227 / 284 -> 89 / 131 / 143 ns; `std::allocator` 88 / 130 / 141).
  - **`vector<int>`**: 0.995, 0.983 and 1.000 at n = 16, 1000 and 100,000 (A/A max dev 7.6%, 5.0%, 1.5%), all inside the spread and none below 0.97; the CHANGELOG puts them within 0.1% on the i9.
  - **The pool, called directly**: refill of 1,000 blocks 1.25x (3.212 -> 2.587 ns per operation), of 100,000 blocks 1.16x, a fresh pool of 1,000 blocks 1.29x and of 100,000 blocks 1.76x, frees in random order 1.12x; the `std::allocator` control 1.032.
- **Rows below 0.97 on the i9: 1, outside the A/A spread.** `pool_direct` steady state (`allocate(1)` then `deallocate` of one block through the free list): START 0.741 ns, HEAD 2.020, ratio **0.352** (round range 0.35-0.42; A/A max dev 11.6%). The three rounds agree: A 0.844 / 0.741 / 0.711, A/A 0.756 / 0.715 / 0.760, HEAD 2.014 / 2.113 / 2.020. The same source reads 0.896 on the M4, so this is a 2.7x slowdown of the one-block allocate+free pair on x86. The cause is not investigated here. A hypothesis, not measured: HEAD reaches the free list through the `shared_ptr`-owned family and a cached size-class pointer, so each `allocate` waits on the previous `deallocate`'s store to memory, where START kept the list head in the allocator value and the compiler could hold it in a register across the loop. Every row that has more than one block live is faster at HEAD (1.12-1.76x), so the cost shows only in code that allocates and frees the same single block over and over.

**Verdict: FASTER** on both machines (M4 geomean 1.30, i9 geomean 1.20; strings 1.7-2.4x, pool refill 1.2-1.7x), with one slower row: the one-block steady-state pool pair, 0.896 on the M4 (inside its A/A spread) and 0.352 on the i9 (outside it), and the `vector<int>` quantisation rows to watch.

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- i9 `pool_direct` steady state (allocate one block, free it) 0.352: fixed on the M4 Pro and narrowed
  on the i9 in `allocators:6eb7fb2` (an allocator alone in its family keeps its freed blocks in a
  local list, `88c5ae6` adds the row to the bench). The pair takes 0.66 ns on the M4 Pro against
  start's 1.16, and 1.00 ns on the i9 against start's 0.74 (2.03 at the gate's head). The i9
  remainder is the cost of the AL1 fix, which stopped copy assignment from sharing a pool: accepted,
  [allocators#1](https://github.com/Kronuz/allocators/issues/1). `allocators:6975ee8` also aligns the
  tracked allocator's blocks to 16 bytes, misaligned under UBSan at start too.
- M4 `vector<int>` n=1000 0.963: accepted. `construct`'s `noexcept` clause follows the element's
  constructor (the forwarding fix), a few percent of a 0.5 ns operation; in the CHANGELOG.
