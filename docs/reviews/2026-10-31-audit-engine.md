# Audit: engine (fst, docset; bitpack not landed)

- Date: 2026-10-31. Kind: cluster audit of the October 2026 performance and correctness work (read-only), fresh
  context, 13:00-16:30.
- Repos: `fst:12657aa..c57e01f`, `docset:cd38597..2bc55cc`, `bitpack:cd13f36` (not audited); consumer strata `93b5322`.
- Machines: Apple M4 Pro, Intel Core i9-9980HK, a shared Linux x86-64 VM (GCC 11 sanitizers). Method:
  [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| E1 fst: build directory `ubsan/` committed | partly closed | `fst:847aa0f` | - (removed and ignored; history not rewritten, so the files, local paths in `CMakeCache.txt` included, stay reachable from `b08055f`) |
| E2 fst: registry hit verification untested by CI | closed | `fst:9af3f3f` | `fst_collide` (`FST_TEST_HASH_MASK=0`) |
| E3 fst: peak build memory regresses at some sizes | closed | `fst:aa3aa3a` | `fst_memory` (fails for the previous registry at 6 of 15 sizes), `fst_diff_wide` |
| E4 docset: array ANDNOT 1.5-1.8x slower on arm64 at mid density | closed | `docset:511c575`, `docset:a6de748`, `docset:d919e11` | `docset_ab_new` / `docset_ab_old` with `bench/ab_compare.py` (benchmark) |
| E5 docset: x86-64 clang slower on both targeted rows | closed | `docset:511c575`, `docset:a6de748`, `docset:b53ccf9`, `fst:fe22b32` | `docset_codegen` (fails on x86-64 clang without the hint); `docset_diff` |
| docset-N1 `diff.cc` exercises the `keys_` search only up to 6 chunks | closed | `docset:a6de748` | `docset` (test.cc: `lower_bound_index` at every probe value up to n = 4097, 65,536 chunks, doc 0xffffffff) |
| docset-N2 comment on `lower_bound_index` false for LLVM x86-64 | closed | `docset:a6de748` | `docset_codegen` |
| docset-N3 no run containers; frozen form untouched | no change | - | - (observation; prospect and strata unaffected) |
| docset-N4 `from_bitmap` leaves 2 spare `uint16_t` per array | no change | - | - (the branch-free extraction stores past the last slot; `fill_array` sizes card + 2 by design) |
| fst-N1 `hash_of` collision between final flag and final output | open | - | - (open: `hash_of` on `main` still seeds with `is_final` and mixes `final_output` in; no commit references it; `same_node()` keeps the bytes right) |
| fst-N2 1-key build 0.90x on arm64 (16 KiB first table) | closed | `fst:aa3aa3a` | - (timing: first table 8 KiB; CHANGELOG `build, 1 keys` 1.29x on the M4 Pro, 1.10x on the i9) |
| fst-N3 `intersect` still decodes a full `node` per transition | open | - | - (open: `intersect` on `main` keeps `frame{node, ...}`; the Bar's "lean frames for `intersect`" has no commit) |
| fst-N4 README table from the start; CHANGELOG calls the `8058003` bug heap-use-after-free | partly closed | `fst:7376bd9` | - (README re-measured on the M4 Pro; CHANGELOG still says "heap-use-after-free" for the over-read) |
| fst-N5 `range` with non-empty `hi` is O(L^2) per key; `get_le` assumes little-endian | open | - | - (pre-existing; open: the bounded walk on `main` still compares the whole path with `hi` at each step, `get_le` is unchanged) |

E4 is a performance finding, so no CTest test can fail on its revert: the audit traced it to code layout, the fix round
to a benchmark that timed one input repeatedly (the branch predictor memorized it), and the separate-binary benchmark
that cycles inputs is what now shows array ANDNOT at 1.14x, 1.50x and 1.57x of the start on the M4 Pro
(`docset:a6de748`). The bitpack aliasing change landed after the audit as `bitpack:494a727` and was not audited.

| repo | start | head | campaign commits | verdict |
|---|---|---|---|---|
| fst | `12657aa` | `c57e01f` | `b1e8ff3` registry, `b08055f` range, `8058003` over-read fix, `c57e01f` docs | **BETTER WITH CONDITIONS** |
| docset | `cd38597` | `2bc55cc` | `d1aa406` test() and conversion, `2bc55cc` docs | **NOT YET** |
| bitpack | `cd13f36` | `cd13f36` | nothing on origin; the aliasing change was uncommitted | not audited |

Both heads differ from their last CI run (`8058003`, `d1aa406`; green on all 8 jobs: linux x86_64 gcc/clang,
linux arm64, macOS arm64/x86_64, FreeBSD, ASan+UBSan, TSan) only in comments and docs (`[skip ci]`). The new
`fst_diff` and `docset_diff` tests are in CTest, so every CI job runs them. GitHub has no campaign branch (only
`main`). During the audit `7376bd9` (fst) and `28943f2` (docset) landed, README and CHANGELOG only; the findings
apply to them unchanged. Output bytes: fst builds byte-identical FSTs on every set tried, and strata's format-14 segment fixtures
pass against fst head; docset's set contents, container shapes and `freeze` bytes are identical.

Probes: the audit's fst and docset probes, edge benches, A/B harness, memory probe, collision probes, hash variants and
mutants were not kept. Where each now lives is given at its first use below.

## docset

### Blocking

**E5. On x86-64 with clang (Apple clang 17, and LLVM 23 by codegen), both targeted rows got slower.** The
"branchless" `lower_bound_index` (docset.hh:687-700) compiles to a conditional branch on x86-64 under LLVM, not a
`cmov` (Apple clang 17 `-target x86_64-apple-macos13 -O3`: `cmpw; jae; addq; jmp`; Homebrew LLVM 23 for
`x86_64-linux-gnu`, also with `-march=x86-64-v3`: 0 `cmov` in `set::test`; arm64: 2 `csel`). The two-bits-per-word
conversion (docset.hh:776-787) calls `countr_zero` on words that may be zero; without BMI1 (the macOS and generic
x86-64 baseline) LLVM guards each `bsf` with a branch, which is exactly the mispredict the change removed on arm.
Measured on the Intel Core i9-9980HK, Apple clang 17 -O3, under an exclusive timing hold (the README's own CRoaring
platform):

| row | start | head | head speedup | A/A |
|---|---:|---:|---:|---:|
| `test()` d 0.001 / 0.01 / 0.03 / 0.1-0.5 (`cmp_bench`, 2 runs) | | | **0.41 / 0.56-0.58 / 0.63-0.65 / 0.38x** | 0.99-1.02 |
| `test()` 1 chunk 8 members / 4096-array / 256 bitmaps / 65,536 chunks | 8.4 / 22.8 / 13.9 / 55.6 ns | 15.7 / 55.2 / 38.0 / 86.0 | **0.54 / 0.42 / 0.37 / 0.67x** | 1.00-1.04 |
| AND d=0.1 (`cmp_bench`) | 1309-1321 us | 1729-1758 | **0.74-0.76x** | 1.01 |
| AND d=0.1, repo `bench.cc` (separate binaries) | 1316 us | 1753 | 0.75x; vs CRoaring 1.02 -> **1.36** | |
| ANDNOT d=0.1 x 0.9 (array results) / AND d=0.07 | | | **0.75 / 0.70x** | 1.01 |

GCC 16.2 on the same host is the other way round (`test()` 2.2-2.9x, AND d=0.1 1.04-1.06x, edge `test()` rows
1.7-3.6x), which is why the [X86 survey](2026-10-30-survey-x86.md) (GCC 11) saw a win. Linux and macOS clang users
get the loss.
Candidate fix (not kept; the landed fix is `docset:a6de748`), 3 lines: `__builtin_unpredictable(base[half] < x)`
under clang in `lower_bound_index`, and `countr_zero(w | (1ull << 63))` for the two blind extractions (the top bit
cannot change the lowest set bit, and an empty word yields 63, a junk slot that `k` does not advance past). Codegen: 2
`cmov` in `set::test`, no guard before the two `bsf`. It passes the docset probe, the repo's `diff.cc` and `test.cc`
(arm64). Measured with it on the i9, Apple clang 17, exclusive hold: `test()` 1.08-1.64x faster than the
start (`cmp_bench`, 2 runs, A/A 1.00-1.02; head was 0.38-0.65x), edge `test()` rows 1.13-1.52x, AND d=0.1
2.04-2.11x (head 0.74-0.76x), AND d=0.07 1.46x; separate binaries AND d=0.1 322-328 us -> 153-155. Array ANDNOT
(unchanged code) still moves with layout under it, 0.88-0.90x at d=0.01 and 0.031 (E4).
The uncommitted `perf/andnot-x86` work in docset independently fixes the conversion half with a BMI1
`tzcnt`/`blsr` path behind `__builtin_cpu_supports("bmi")` and a plain loop otherwise: separate binaries on the
i9, AND d=0.1 old 323.9-327.1 us, head 428.4-437.8, WIP 141.5-143.0 (clang; 2.29x over start), and GCC 16 old
395.8-400.7, head 385.4-391.5, WIP 154.9-157.5 (2.56x). It does not touch `lower_bound_index`, so the `test()`
half of E5 stays open. Condition to land: both halves fixed, and x86-64 clang and GCC rows next to the arm64 ones in the
CHANGELOG. Since `28943f2` the README's CRoaring table is arm64 only (M4 Pro); on the i9 with Apple clang, head's AND
at d=0.1 is 1.36x CRoaring 5.2.3's time (start: 1.02).

### Conditions

**E4. Array-container ANDNOT is 1.5-1.8x slower on arm64 at mid density** (untargeted row). `a - b` at density
0.031 x 0.031 (about 2,030 members per chunk, arrays, `subtract16`, code unchanged), separate binaries
(the A/B harness, now `docset:bench/ab_bench.cc`; one version per binary, best of 15 x 20 ms, 5 alternating pairs):
start 86.5-97.2 us, head 133.8-158.2 us (0.55-0.68x). The shared-binary edge bench (its rows now in
`docset:bench/cmp_bench.cc`): 0.66x and 0.68x [0.55..0.95], A/A 1.07-1.10.
Cause is code layout: head with the old conversion loop (mutant not kept) 83.8-94.3 us; head with
`-falign-functions=64 -mllvm -align-all-nofallthru-blocks=6` 84.2 us; the uncommitted `perf/andnot-x86` work in
docset (conversion out of line, `noinline`) 97.5 us. On x86-64 the row is 0.94-0.96x with clang
(old 109.3-110.6 us, new 115.9-116.3) and 0.99x with GCC 16 (separate binaries, 3 pairs each). The repo's `docset_cmp_bench` cannot see this kind of effect: it compiles old and new into one
binary (its `andnot` d=0.1 row reads 0.91x on arm64 there, while separate binaries show that row 1.17-1.22x
faster). Condition: land the out-of-line conversion, and gate perf claims with separate start/head binaries on
arm64 and x86-64 (clang and GCC).

### Non-blocking

- **docset-N1.** `diff.cc` never builds more than 6 chunks, so the repo exercises the `keys_` search only up to n=6
  (`test.cc`: 16). The audit's docset probe (probe not kept; covered by `docset:test/test.cc`, CTest `docset`) checks
  `lower_bound_index` against `std::lower_bound` for every x in 0..65535 at n in
  {0-5, 7-9, 15-17, 31-33, 63-65, 100, 255-257, 300, 1000, 4095, 4096, 65535, 65536}, and `set::test` on a
  65,536-chunk set and at doc 0xffffffff; worth a cheap test.
- **docset-N2.** The comment at docset.hh:687-689 ("the compiler emits a conditional select") is false for LLVM on x86-64.
- **docset-N3.** docset has no run containers; the frozen form (`freeze`, `frozen_view`) and container shapes are untouched.
  prospect uses only `freeze`, `frozen_view` and the iterator concept, none changed; strata links no docset.
- **docset-N4.** `from_bitmap` leaves 2 spare `uint16_t` of capacity per converted array: 4 bytes per array container.

### Evidence

- The docset probe (probe not kept; covered by `docset:test/test.cc` and `docset:test/diff.cc`): (1)
  `lower_bound_index` exhaustive as above; (2) `from_bitmap` against the reference
  at 0, 1-4, 63-65, 127-129, 3071, 4094-4098, 8192, 65535, 65536 bits in five patterns (packed at the top so the
  last words are full, packed at the bottom, bit 63 of each word, exactly 3 per word, random) and 2,000 random
  bitmaps with 0-64 bits per word: card, shape, contents and `test` equal; (3) full-chunk ANDNOT and bitmap AND
  with results of exactly 0-3, 4095, 4096, 4097, 65535, 65536 members in chunks 0, 1 and 65535; (4) one doc in
  each of the 65,536 chunks, empty sets, doc 0xffffffff; (5) 80 random multi-chunk sets over densities 0..1
  straddling 4,096 per chunk. Per result: count, per-chunk shape (key, array/bitmap, card), members, and
  `freeze` bytes equal the reference; `test` agrees on boundary docs and 40k random probes. Identical on arm64
  (SIMD and `DOCSET_NO_SIMD`), x86-64 Apple clang 17 (SSE/AVX2 dispatch, and `DOCSET_NO_SIMD`), x86-64 GCC 16.2,
  and GCC 11 ASan+UBSan+`_GLIBCXX_ASSERTIONS` on a shared Linux x86-64 VM. Digests match per standard library
  (libc++ arm64 = libc++ x86-64 `aea0cd5a`; libstdc++ GCC 16 = libstdc++ GCC 11 `6c493dbc`; the random generators
  differ between the two libraries).
- Repo `docset_diff` and `docset_test` pass under GCC 11 ASan+UBSan on the Linux VM (`docset_diff` needs
  `LD_BIND_NOW=1` there: without it the ASan report path recursed in lazy symbol binding and wrote a 15 GB log; the
  CI clang ASan job passes it).
- Mutants against the repo tests: D1 (third-bit loop removed) killed by `diff.cc` and `test.cc`; D2 (no padding)
  killed only under ASan (heap-buffer-overflow), which the CI ASan job provides; D3 (`lower_bound_index` drops the
  final step) killed by both.

### Performance, arm64 (Apple M4 Pro, Apple clang 17 -O3, exclusive timing hold)

| row | start | head | ratio (spread) | A/A | claim |
|---|---:|---:|---:|---:|---|
| `test()` d 0.001 / 0.01 / 0.03 / 0.1-0.5 (`cmp_bench`, 2 runs) | | | 1.14-1.15 / 2.17-2.20 / 1.61-1.67 / 1.67-1.70x | 0.98-1.02 | 1.6-2.1x: holds on arm64 |
| `test()` 1 chunk 8 / 4096-array / 256 bitmaps / 65,536 chunks | 3.4 / 12.8 / 7.9 / 39.1 ns | 2.3 / 7.1 / 4.7 / 26.3 | 1.47 / 1.72 / 1.69 / 1.44x | ~1.0 | |
| AND d=0.1 (`cmp_bench`) | 952-977 us | 276-277 | 3.52-3.54x | 1.01-1.02 | 830 -> 253, 3.3x: holds on arm64 |
| AND d=0.1, separate binaries (64 chunks) | 112-132 us | 64-66 | 1.7-2.0x | | |
| ANDNOT d=0.1 x 0.9 (array results), separate binaries | 157-169 us | 65-66 | 2.4-2.6x | | |
| ANDNOT d=0.1 / 0.5 (bitmap results), separate binaries | 16.8-17.6 / 17.0-17.6 us | 14.3-14.6 / 16.4-17.0 | 1.17-1.22 / 1.0-1.05x | | |
| **ANDNOT d=0.031 (arrays), separate binaries** | 86.5-97.2 us | 133.8-158.2 | **0.55-0.68x** | | E4 |
| AND / OR d=0.01, 0.031, 0.5 | | | 0.97-1.02x | | unchanged |

Against CRoaring (repo `bench.cc`, start and head binaries; ratio docset/roaring, below 1 = docset faster; arm64
against CRoaring at `db0d1e9`, x86-64 against 5.2.3 `f2b1a55`, the CMake pin):
on arm64, AND d=0.1 went 1.77 -> **0.49** and every other row stays below 1 except OR at d=0.001 (1.08 -> 1.07)
and d=0.01 (1.00 -> 1.00). On x86-64 Apple clang, AND d=0.1 went 1.02 -> **1.36** (E5); OR d=0.01 stays 1.13.

## fst

### Blocking

**E1. A build directory is committed** (`b08055f`): `ubsan/` holds 77 files, 7.7 MB, including Mach-O arm64
binaries (`ubsan/fst_test`, `fst_diff`, `fst_bench`, `fst_cmp_bench`), object files and a `CMakeCache.txt` with
local user paths. `.gitignore` covers `build*/` only. Repro: `git ls-files ubsan | wc -l` = 77 at
`c57e01f`. Fix: `git rm -r ubsan` and ignore it. No secrets in it (checked).

### Conditions

**E2. The registry's hit verification is untested by CI.** `same_node()` (fst.hh:678-708) is what keeps the output
byte-identical when two different nodes share a 64-bit hash, and the repo tests never reach its rejecting
branches. Mutants run against the repo's `diff.cc` + `test.cc`, and against the audit's fst probe built with
`hash & 0xfff` (forced collisions; probe not kept, the forced-collision test is now `fst:test/collide.cc`, CTest
`fst_collide`):

| mutant (not kept) | repo tests | collision probe |
|---|---|---|
| M1: general node, targets not compared | **pass** | killed (4 cases differ) |
| M3: chain node, target not compared | **pass** | killed (30) |
| M4: general node, outputs not compared | **pass** | killed (decimal case) |
| M2: any hash hit accepted | killed by `diff.cc` | killed (30) |

M2 dies in `diff.cc` only through rare real collisions such as the one below. Add a test hook that weakens the
hash (a `FST_TEST_HASH_MASK` macro, or a hasher parameter defaulting to the current one) and run `diff.cc` under
it in CTest. The code is right today: forced-collision builds (hash variants with all hashes equal, `& 3` and
`& 0xfff`; not kept) give bytes identical to the reference on every probe case, on arm64 and x86-64.

**E3. Peak build memory regresses at some sizes** (untargeted, not in the CHANGELOG). The table keeps load <= 0.5
with 16-byte slots and holds both arrays during `grow()`, so memory per written node saws between about 32 and
96 bytes; the start's `unordered_map<std::string,...>` cost about 65. A memory probe (probe not kept), peak RSS of
one build of N random 12-letter keys, arm64:

| keys | start | head | head/start |
|---:|---:|---:|---:|
| 100k | 40.0 MiB | 32.3 MiB | 0.81 |
| 300k (1.37M nodes, table 4.2M slots) | 87.1 MiB | 125.6 MiB | **1.44** |
| 1M | 290.0 MiB | 245.1 MiB | 0.85 |
| 2M | 532.0 MiB | 487.1 MiB | 0.92 |
| 3M (9.22M nodes, table 33.5M slots = 512 MiB) | 603.5 MiB | 967.1 MiB | **1.60** |

Fix: 8-byte slots (40-bit address plus a 24-bit hash tag; the full hash is recomputed from the pending node) or a
0.75-0.8 load limit.

### Non-blocking

- **fst-N1.** `hash_of` seeds with `is_final` and then xors `final_output` in: `mix(0x51, 0x6e) == mix(0x3f, 0)`
  (checked), so a final node with final output 110 collides with the non-final node with the same arcs. `same_node`
  keeps the bytes right; the dictionary build sees 0 false hits in 662k probes (probe not kept). Hash `is_final`
  separately.
- **fst-N2.** Building a 1-key FST: 0.90x [0.83..1.11] on arm64 (353 -> 401 ns), 1.38x and 1.10x faster on x86
  clang/GCC: the first write zeroes a 1024-slot, 16 KiB table. Starting at 16-64 slots costs nothing.
- **fst-N3.** `intersect` is unchanged code and measures 1.02x (arm64), 1.02x (x86 clang), 0.84x [0.77..0.90] (x86
  GCC 16, shared binary, A/A 0.99): a layout effect, but it is also the one walk still decoding a full `node` per
  transition.
- **fst-N4.** README's Performance table is the start's numbers (labelled `12657aa`); build is now 2.3-3.3x faster
  than it says. The CHANGELOG calls the `8058003` bug "heap-use-after-free"; it was an over-read past `out_`'s size.
- **fst-N5.** Pre-existing, not introduced: `range` with a non-empty `hi` compares the whole path against `hi` at
  every step, so walking an L-byte key costs O(L^2) (the 100k-byte-key probe case takes minutes under ASan, old and
  new alike). `get_le` assumes a little-endian host (unchanged).

### Evidence

- The fst probe (probe not kept), 136 key sets: 0 keys; the empty key alone with value 0 and 2^64-1; one key `\0`; one key
  `\xff`; one 100k-byte key; two 100k-byte keys diverging at the end; 256-way fan-out; all 65,536 two-byte keys; a
  5,002-byte shared binary prefix; 20k binary keys with random 64-bit values; decreasing values near 2^64 (output
  pushing); 160k keys sharing 40 suffixes; equal shapes differing only in outputs; 300k decimal strings (many
  `grow()` cycles); 120 random sets over 2/3/16/256-byte alphabets. Per set: bytes equal the reference; the
  validating constructor accepts them; `for_each` equals the `std::map`; 300 random `range(lo, hi, limit)`
  (members, members +/- 1 byte, prefixes, random binary, empty bounds, early stop after 0-6), `get`, `floor`,
  `floor_value`, prefix `intersect` and a never-pruning automaton all equal the reference and the oracle.
  Identical on arm64 (Apple clang 17), x86-64 Apple clang 17 and GCC 16.2; the 136 FNV digests match line by line
  across the three. Under GCC 11 ASan+UBSan+`_GLIBCXX_ASSERTIONS` (Linux VM): all 136 identical, no report (one
  earlier run died inside the ASan runtime while the Linux VM's temporary directory was full; the identical binary
  reran clean).
- Same probe with forced collisions (`& 0xfff`, `& 3`, `0`): identical on arm64; `& 0xfff` also on x86-64 and
  under ASan on the Linux VM.
- Repo `fst_diff` and `fst_test` pass under GCC 11 ASan+UBSan (Linux VM).
- Range mutants: R1 (chain-node `lo` skip removed) killed by `diff.cc`; R2 (path `>= hi` cut-off removed) survives
  and is equivalent (every subtree ends in a final node, which stops the walk).
- strata `93b5322` against fst head (`FETCHCONTENT_SOURCE_DIR_FST`, confirmed in `build.ninja`): `format14` (golden
  segment bytes, pinned by hash in `pre_freeze.txt`), `key_index`, `core_kv`, `scan`, `merge_stream`, `index`,
  `keys_fuse`, `fields`: 8/8 pass, as with its pinned fst `24da59a`.
- Compatibility: format, public `map`/`builder` API and `range` contract unchanged; `builder`'s private layout
  changed (header-only, no ABI promise). fst.hh dropped `#include <unordered_map>`; no consumer relied on it
  (termdict, strata, prospect checked). Both headers self-contained under libc++ and libstdc++ 16, C++20 as
  before. New code is endian-neutral (`exact_le`).

### Performance

Edge rows (build of 1 to 1024 keys, 200-byte keys, short `range`) came from an edge bench (probe not kept).

| row | arm64 M4 Pro, clang 17 | x86-64 i9, Apple clang 17 | x86-64 i9, GCC 16.2 | claim |
|---|---|---|---|---|
| build, dict 236k (`fst_cmp_bench`, 3 runs) | 274-299 -> 106-112 ns/key, 2.46-2.68x (A/A 1.03-1.09) | 555-579 -> 186-198, 2.89-3.08x (A/A 0.98-1.01) | 529-545 -> 176-191, 2.85-3.02x (A/A 1.00-1.01) | 2.4x: holds |
| `for_each`, same | 60.0-60.4 -> 38.4-39.4, 1.53-1.56x | 72.9-76.3 -> 61.8-62.5, **1.18-1.22x** | 73.6-74.6 -> 50.3-51.2, 1.45-1.48x | 1.5x: holds except x86 clang |
| `fst_bench` build, separate binaries | 3.49-3.59 -> 8.11-8.55 Mkeys/s | 1.44-1.57 -> 4.62-4.79 | | |
| build 1 / 4 / 16 / 256 / 1024 keys | 0.90 / 1.57 / 2.93 / 4.00 / 3.59x | 1.38 / 2.18 / 4.20 / 4.96 / 3.75x | 1.10 / 2.14 / 4.43 / 5.48 / 4.30x | |
| build 200-byte keys, 20k | 8.67x | 4.85x | 4.69x | |
| `range`, first 1 / 10 / 100 keys | 1.62 / 1.58 / 1.51x | 1.57 / 1.36 / 1.16x | 1.75 / 1.81 / 1.55x | |
| for_each decimal 300k / 200-byte keys | 1.54 / 1.74x | 1.05 / 1.19x | 2.04 / 2.19x | |
| `get` (unchanged) | 0.98x | 1.04x | 1.00x | |

All A/A rows 0.93-1.10 except where shown.

## bitpack

No campaign commit on `origin/main` (`cd13f36`, CI green); the unpack aliasing change sat uncommitted in a local
working tree (`bitpack.hh`, `CMakeLists.txt`, `test/bitpack_v0.hh`, `test/differential.cc`). Not audited.

## Bar

- fst: clearly better than the start on every ISA and compiler tried (build 2.5-3.1x, iteration 1.2-1.6x, short
  ranges 1.2-1.8x, identical bytes on every adversarial set, strata fixtures intact). Build at 106-112 ns/key now
  beats `std::map` sorted-hint insert (149 ns/key, [survey G](2026-10-30-survey-engine.md)); lookup is unchanged and
  at par with absl btree. To be clearly at the bar: give `intersect` the lean frames `range` got (fuzzy and regex
  expansion run there), and fix E3 so the build wins on memory as well as time.
- docset: better on arm64 and with GCC on x86-64, worse with clang on x86-64 on both rows it targeted (E5), and one
  untargeted arm64 row lost to code layout (E4). The single change: the 3-line codegen fix in E5 (`cmov` and an
  unguarded `bsf`), landed with the out-of-line conversion from E4 and gated by separate-binary start/head
  benches on arm64 and on x86-64 with both clang and GCC.

Not run: TSan (no concurrency changed; CI runs it), FreeBSD, MSVC, big-endian hosts, fuzzers, the full strata
suite (8 of 55 tests: the ones that touch the term dictionary and the golden segments).
