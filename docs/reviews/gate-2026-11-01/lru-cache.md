# Gate: lru-cache

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/lru-cache#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `7dd23eb` | 2026-10-29 03:55:48 -0700 | Report successful key erasure when the final entry is removed |
| HEAD (`origin/main` when pinned, 2026-11-01) | `d170245` | 2026-11-01 03:55:30 -0800 | Shape the README to the family standard and drop the diagram [skip ci] |

Library sources changed between them (docs, tests, benches, CI excluded): none (the library sources are byte-identical).

## Method (common to every machine)

- Two worktrees of one clone, at START and at HEAD. The bench source is HEAD's (or, where stated, a copy of it with the rows START cannot compile removed, or a micro-bench written for the gate, not kept); each is compiled twice, once with `-I <START tree>` (binary A) and once with `-I <HEAD tree>` (binary B), same compiler, flags and source path. A/A is a byte copy of A.
- Flags: `c++ -std=c++20 -O3 -DNDEBUG -pthread` (Apple clang 17.0.0: M4 Pro `clang-1700.3.19.1`, i9 `clang-1700.6.4.2`). Comparator libraries are not linked or fetched. Only `flat-map`'s bench finds them by itself (`__has_include`): `absl::btree_map` is on the default include path of both machines and `boost::container::flat_map` on the i9's only, so that bench has abseil rows on the M4 and boost and abseil rows on the i9 (controls: they run no code of this repo).
- Rounds: every round runs each bench entry with A, B and AA (order `a b aa` on odd rounds, `aa b a` on even ones), under one `quiet strict` hold per repo and machine (on macOS a strict hold is exclusive). `runab.sh` writes one file per run; `ab_compare.py compare --format unit` pairs run i of A with run i of B (and of AA) and reports the median ratio.
- **Ratio = START time / HEAD time, so above 1 means HEAD is faster.** Throughputs are converted to ns per item. `A/A max dev` is the largest |ratio - 1| of A against its own copy over the same rounds: the measurement's noise. Rows marked `(control)` run code the change cannot reach (a standard-library or baseline arm); they show the noise floor and are left out of the geomean.
- A row is listed as "<0.97 outside A/A" when its ratio is below 0.97 and also below 1/(1 + A/A max dev).

## What was measured

- `bench/bench.cc` (`lru_cache_bench`): `lru::lru` (`find_and_renew`, `emplace` on a miss) against a textbook `std::list` + `std::unordered_map` LRU on skewed keys, ns per operation, best of 5. The `list+map` column is `std` only, so it is the control of every row.
- **The library did not change.** `lru.h` is byte-identical at START and at HEAD (`git diff --stat 7dd23eb d170245 -- lru.h` is empty; the 2 commits since START are a benchmark and README/CI edits). The two compiled binaries have identical machine code (`otool -tv` of A and B differs only in the file name on the first line; the other bytes that differ are the Mach-O UUID and signature). The measurement below is therefore an A/A: it shows what this benchmark reads when nothing changed, and every ratio away from 1 is noise or host state.


### Apple M4 Pro

#### main (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| u64 keys cap=1024 lru::lru | 23.70 | 23.40 | 1.013 | 1.00-1.02 | 2.1% | 3 |
| u64 keys cap=1024 list+map (control) | 27.30 | 28.10 | 0.979 | 0.95-1.05 | 3.0% | 3 |
| u64 keys cap=65536 lru::lru | 37.10 | 37.80 | 0.984 | 0.85-1.09 | 20.4% | 3 |
| u64 keys cap=65536 list+map (control) | 47.00 | 52.40 | 0.956 | 0.84-0.97 | 29.3% | 3 |
| u64 keys cap=1048576 lru::lru | 167.8 | 152.7 | 1.132 | 1.05-1.23 | 11.8% | 3 |
| u64 keys cap=1048576 list+map (control) | 192.5 | 158.4 | 1.228 | 0.89-1.27 | 13.8% | 3 |
| string keys cap=65536 lru::lru | 87.50 | 110.3 | 0.793 **<0.97** | 0.64-1.05 | 22.5% | 3 |
| string keys cap=65536 list+map (control) | 100.1 | 121.4 | 0.759 | 0.70-1.59 | 22.7% | 3 |

**Geomean START/HEAD (Apple M4 Pro): 0.973** over 4 library rows (controls, 4 rows: 0.966)

Rows >1.03: 1; within 0.97-1.03: 2; <0.97: 1 (1 outside the A/A spread, 0 inside it).

### Intel i9-9980HK

#### main (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| u64 keys cap=1024 lru::lru | 84.80 | 82.60 | 1.027 | 0.98-1.04 | 8.8% | 3 |
| u64 keys cap=1024 list+map (control) | 84.90 | 82.40 | 1.063 | 1.02-1.09 | 13.0% | 3 |
| u64 keys cap=65536 lru::lru | 288.3 | 229.1 | 1.386 | 0.89-1.44 | 47.9% | 3 |
| u64 keys cap=65536 list+map (control) | 315.5 | 260.3 | 1.273 | 0.96-1.33 | 29.6% | 3 |
| u64 keys cap=1048576 lru::lru | 383.7 | 360.9 | 1.063 | 0.99-1.16 | 14.4% | 3 |
| u64 keys cap=1048576 list+map (control) | 375.8 | 362.2 | 1.038 | 1.02-1.19 | 8.4% | 3 |
| string keys cap=65536 lru::lru | 297.7 | 259.3 | 1.130 | 0.99-1.37 | 9.2% | 3 |
| string keys cap=65536 list+map (control) | 435.2 | 411.4 | 1.050 | 0.89-1.34 | 24.9% | 3 |

**Geomean START/HEAD (Intel i9-9980HK): 1.143** over 4 library rows (controls, 4 rows: 1.102)

Rows >1.03: 3; within 0.97-1.03: 1; <0.97: 0 (0 outside the A/A spread, 0 inside it).

## Findings: lru-cache

- **No change, by construction.** Same `lru.h`, same machine code. Geomean 0.973 (M4) and 1.143 (i9) are the noise of 3 rounds of a benchmark whose rows have a 2-48% A/A spread, not a change in the library; the `list+map` control (pure `std`, never touches `lru.h`) has a geomean of 0.966 (M4) and 1.102 (i9) in the same runs.
- **Rows below 0.97 outside the A/A spread: 1**, `string keys cap=65536 lru::lru` on the M4 (0.793, A/A max dev 22.5%, range 0.64-1.05). The cause is not the library: the code is identical and the control arm in the same run moved the same way (`list+map` 0.759, range 0.70-1.59). Treat as "unexplained, host state": the A/A estimate comes from only 3 pairs and the row is a 65,536-entry string-key workload whose time depends on allocator and cache state.
- `lru-cache` has no correctness or behaviour change between START and HEAD that would make a row not comparable.

**Verdict: SAME** (nothing changed; the benchmark was added, see `bench/bench.cc` at HEAD).

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 string keys, capacity 65,536, `lru::lru` 0.793: placement. The code is identical and the
  `std::list` + `unordered_map` control moved the same way (0.759).
