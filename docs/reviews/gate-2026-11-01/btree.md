# Gate: btree

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/btree#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/master` before 2026-10-30) | `25f9494` | 2026-10-22 16:47:28 -0700 | Transfer container ownership through genuine moves |
| HEAD (`origin/master` when pinned, 2026-11-01) | `21233e5` | 2026-11-01 06:15:43 -0800 | Measure btree::map against abseil on both machines |

Library sources changed between them (docs, tests, benches, CI excluded): 1 file changed, 211 insertions(+), 161 deletions(-).

## Method (common to every machine)

- Two worktrees of one clone, at START and at HEAD. The bench source is HEAD's (or, where stated, a copy of it with the rows START cannot compile removed, or a micro-bench written for the gate, not kept); each is compiled twice, once with `-I <START tree>` (binary A) and once with `-I <HEAD tree>` (binary B), same compiler, flags and source path. A/A is a byte copy of A.
- Flags: `c++ -std=c++20 -O3 -DNDEBUG -pthread` (Apple clang 17.0.0: M4 Pro `clang-1700.3.19.1`, i9 `clang-1700.6.4.2`). Comparator libraries are not linked or fetched. Only `flat-map`'s bench finds them by itself (`__has_include`): `absl::btree_map` is on the default include path of both machines and `boost::container::flat_map` on the i9's only, so that bench has abseil rows on the M4 and boost and abseil rows on the i9 (controls: they run no code of this repo).
- Rounds: every round runs each bench entry with A, B and AA (order `a b aa` on odd rounds, `aa b a` on even ones), under one `quiet strict` hold per repo and machine (on macOS a strict hold is exclusive). `runab.sh` writes one file per run; `ab_compare.py compare --format unit` pairs run i of A with run i of B (and of AA) and reports the median ratio.
- **Ratio = START time / HEAD time, so above 1 means HEAD is faster.** Throughputs are converted to ns per item. `A/A max dev` is the largest |ratio - 1| of A against its own copy over the same rounds: the measurement's noise. Rows marked `(control)` run code the change cannot reach (a standard-library or baseline arm); they show the noise floor and are left out of the geomean.
- A row is listed as "<0.97 outside A/A" when its ratio is below 0.97 and also below 1/(1 + A/A max dev).

## What was measured

- `benchmarks/mutation_bench.cc`: 65,536 random `emplace` then `erase` of string keys (80-byte mapped strings), 4 cycles, process CPU ms, at key width 12 (default), 16, 32 and 200 bytes (`--keys=N`), plus `--copy`, `--copy-pruned` and `--move-nested`.
- `benchmarks/ownership_bench.cc`: moving 128 containers of 512 entries each (move construction, move assignment into an empty and into a populated destination), process CPU ms.
- `benchmarks/string_insert_bench.cc`: string-key `emplace` (random and sorted order), `operator[]` and `find`, n = 20,000 and 200,000, ns per operation, best of 5. **Rows dropped:** its `absl::btree_map` comparator rows (abseil is not on the include path); the btree rows are HEAD's source unchanged.
- `$GATE/own/btree_int.cc` (a micro-bench written for the gate, 40 lines, not kept): the integer-key entry points the repo's benchmarks do not time, `btree::map<u64,u64>` insert, find, iterate, copy and copy+erase and `btree::set<u64>` insert, find, iterate and copy+erase at n = 1,000, 100,000 and 1,000,000, ns per element, best of 5.
- `benchmarks/relocation_alloc_bench.cc` counts `operator new` calls and bytes (deterministic, not timed); results below.
- Not run: `benchmarks/node_footprint.cc` and `mutation_allocation_bench.cc` (footprint and allocation meters, not timings).
- Library change in scope (`btree/btree.h`, 372 lines changed): map slots hold `std::pair<Key, T>` and are relocated by moving keys (START copied the const key of a `std::pair<const Key, T>` on every split, rebalance, merge, erase and root replacement), every allocation of an insertion precedes its first value move, erase allocates nothing, and the middle-insert shift is a move instead of a prepared copy. Node layout and node sizes are unchanged.

### Allocation counts (deterministic, `relocation_alloc_bench`, 65,536 insertions then erasures)

| key bytes | START insert calls / bytes | HEAD insert calls / bytes | START erase calls / bytes | HEAD erase calls |
|---:|---:|---:|---:|---:|
| 12 and 16 (inline in libc++'s 22-byte SSO) | 82,130 / 10,173,672 | 82,123 / 10,173,056 | 0 / 0 | 0 |
| 32 (heap) | 420,230 / 23,697,672 | 147,659 / 12,794,496 | 72,692 / 2,907,680 | 0 |
| 200 (heap) | 420,230 / 80,498,472 | 147,659 / 23,804,544 | 72,692 / 15,119,936 | 0 |


### Apple M4 Pro

#### insert-erase-12 (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| insert+erase key_bytes=12 [ms] | 127.3 | 120.4 | 1.011 | 0.92-1.18 | 22.7% | 3 |

#### insert-erase-16 (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| insert+erase key_bytes=16 [ms] | 118.8 | 121.3 | 0.968 **<0.97** | 0.94-1.03 | 2.6% | 3 |

#### insert-erase-32 (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| insert+erase key_bytes=32 [ms] | 226.6 | 166.1 | 1.313 | 1.30-1.36 | 3.9% | 3 |

#### insert-erase-200 (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| insert+erase key_bytes=200 [ms] | 345.8 | 268.6 | 1.296 | 1.29-1.31 | 5.1% | 3 |

#### copy (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| copy [ms] | 22.60 | 18.26 | 1.170 | 0.97-1.51 | 54.7% | 3 |

#### copy-pruned (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| copy-pruned [ms] | 3.778 | 3.329 | 1.143 | 0.92-1.17 | 14.5% | 3 |

#### move-nested (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| move-nested [ms] | 0.002 | 0.002 | 1.000 | 0.50-3.00 | 200.0% | 3 |

#### ownership (`ownership_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| move-construct [ms] | 0.002 | 0.004 | 0.500 **<0.97** | 0.40-1.00 | 60.0% | 3 |
| move-assign-empty [ms] | 0.003 | 0.003 | 1.000 | 0.67-1.00 | 0.0% | 3 |
| move-assign-populated [ms] | 7.954 | 7.605 | 1.046 | 0.83-1.13 | 15.0% | 3 |

#### string-insert (`string_insert_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| n=20000 btree::map emplace random | 345.9 | 185.3 | 1.867 | 1.76-1.91 | 2.3% | 3 |
| n=20000 btree::map emplace sorted | 77.10 | 52.10 | 1.480 | 1.42-1.51 | 2.0% | 3 |
| n=20000 btree::map operator[] | 354.6 | 191.7 | 1.854 | 1.82-1.88 | 3.3% | 3 |
| n=20000 btree::map find | 142.5 | 140.3 | 1.016 | 0.95-1.04 | 3.3% | 3 |
| n=200000 btree::map emplace random | 512.4 | 305.8 | 1.626 | 1.51-1.83 | 8.6% | 3 |
| n=200000 btree::map emplace sorted | 102.9 | 72.60 | 1.373 | 1.30-1.42 | 21.5% | 3 |
| n=200000 btree::map operator[] | 527.0 | 306.7 | 1.692 | 1.68-1.77 | 6.4% | 3 |
| n=200000 btree::map find | 331.5 | 281.2 | 1.224 | 0.84-1.23 | 14.1% | 3 |

#### int-keys (`btree_int`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| map<u64,u64> n=1000 insert | 16.61 | 17.16 | 0.967 **<0.97** | 0.97-0.98 | 1.9% | 3 |
| map<u64,u64> n=1000 find | 9.240 | 9.162 | 1.009 | 0.99-1.01 | 4.0% | 3 |
| map<u64,u64> n=1000 iterate | 0.455 | 0.465 | 0.981 | 0.98-0.99 | 2.6% | 3 |
| map<u64,u64> n=1000 copy | 2.151 | 2.201 | 0.978 | 0.97-1.00 | 6.0% | 3 |
| map<u64,u64> n=1000 copy+erase | 15.49 | 15.42 | 1.009 | 1.00-1.02 | 0.8% | 3 |
| set<u64> n=1000 insert | 16.64 | 16.86 | 1.002 | 0.98-1.00 | 2.5% | 3 |
| set<u64> n=1000 find | 11.38 | 11.36 | 1.002 | 0.99-1.02 | 3.2% | 3 |
| set<u64> n=1000 iterate | 0.425 | 0.421 | 0.995 | 0.98-1.01 | 1.4% | 3 |
| set<u64> n=1000 copy+erase | 17.13 | 16.95 | 1.010 | 0.98-1.01 | 1.2% | 3 |
| map<u64,u64> n=100000 insert | 70.08 | 71.58 | 0.986 | 0.98-1.00 | 1.4% | 3 |
| map<u64,u64> n=100000 find | 55.48 | 56.91 | 0.966 **<0.97** | 0.96-1.01 | 1.1% | 3 |
| map<u64,u64> n=100000 iterate | 1.162 | 1.176 | 0.988 | 0.92-1.01 | 4.6% | 3 |
| map<u64,u64> n=100000 copy | 2.920 | 2.942 | 0.993 | 0.99-1.00 | 2.0% | 3 |
| map<u64,u64> n=100000 copy+erase | 63.09 | 63.52 | 1.010 | 0.97-1.01 | 1.7% | 3 |
| set<u64> n=100000 insert | 61.82 | 60.10 | 1.029 | 1.02-1.03 | 2.1% | 3 |
| set<u64> n=100000 find | 49.50 | 49.73 | 0.993 | 0.99-1.00 | 1.5% | 3 |
| set<u64> n=100000 iterate | 0.776 | 0.777 | 1.013 | 0.99-1.03 | 1.3% | 3 |
| set<u64> n=100000 copy+erase | 55.68 | 57.51 | 0.966 **<0.97** | 0.96-0.99 | 1.1% | 3 |
| map<u64,u64> n=1000000 insert | 112.1 | 104.4 | 1.074 | 1.01-1.17 | 14.4% | 3 |
| map<u64,u64> n=1000000 find | 125.2 | 126.6 | 0.989 | 0.96-1.06 | 8.5% | 3 |
| map<u64,u64> n=1000000 iterate | 2.381 | 2.983 | 0.727 (<0.97, inside A/A) | 0.52-0.97 | 40.4% | 3 |
| map<u64,u64> n=1000000 copy | 6.498 | 6.480 | 1.003 | 0.77-1.23 | 17.1% | 3 |
| map<u64,u64> n=1000000 copy+erase | 99.51 | 104.0 | 0.971 | 0.92-1.14 | 9.5% | 3 |
| set<u64> n=1000000 insert | 84.33 | 83.61 | 1.017 | 0.98-1.05 | 5.9% | 3 |
| set<u64> n=1000000 find | 88.84 | 86.29 | 1.097 | 0.88-1.10 | 10.1% | 3 |
| set<u64> n=1000000 iterate | 1.015 | 1.066 | 0.970 (<0.97, inside A/A) | 0.95-1.09 | 13.5% | 3 |
| set<u64> n=1000000 copy+erase | 85.87 | 85.53 | 0.992 | 0.95-1.05 | 8.5% | 3 |

**Geomean START/HEAD (Apple M4 Pro): 1.069** over 45 library rows (controls, 0 rows: -)

Rows >1.03: 14; within 0.97-1.03: 24; <0.97: 7 (5 outside the A/A spread, 2 inside it).

### Intel i9-9980HK

#### insert-erase-12 (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| insert+erase key_bytes=12 [ms] | 268.9 | 269.6 | 1.030 | 0.96-1.04 | 6.8% | 3 |

#### insert-erase-16 (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| insert+erase key_bytes=16 [ms] | 254.4 | 259.5 | 0.993 | 0.90-1.00 | 9.0% | 3 |

#### insert-erase-32 (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| insert+erase key_bytes=32 [ms] | 693.4 | 344.2 | 2.015 | 1.93-2.08 | 4.6% | 3 |

#### insert-erase-200 (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| insert+erase key_bytes=200 [ms] | 782.6 | 545.1 | 1.441 | 1.41-1.46 | 1.8% | 3 |

#### copy (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| copy [ms] | 86.40 | 84.02 | 1.028 | 0.94-1.08 | 6.4% | 3 |

#### copy-pruned (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| copy-pruned [ms] | 13.82 | 12.55 | 0.964 (<0.97, inside A/A) | 0.88-1.12 | 13.2% | 3 |

#### move-nested (`mutation_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| move-nested [ms] | 0.002 | 0.002 | 1.000 | 1.00-1.50 | 50.0% | 3 |

#### ownership (`ownership_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| move-construct [ms] | 0.004 | 0.003 | 1.250 | 1.00-1.33 | 25.0% | 3 |
| move-assign-empty [ms] | 0.004 | 0.005 | 0.800 (<0.97, inside A/A) | 0.80-1.00 | 33.3% | 3 |
| move-assign-populated [ms] | 24.72 | 25.41 | 0.970 | 0.95-0.98 | 5.4% | 3 |

#### string-insert (`string_insert_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| n=20000 btree::map emplace random | 923.1 | 412.4 | 2.204 | 2.18-2.24 | 8.9% | 3 |
| n=20000 btree::map emplace sorted | 222.9 | 163.3 | 1.365 | 1.33-1.44 | 4.4% | 3 |
| n=20000 btree::map operator[] | 902.9 | 421.1 | 2.154 | 2.11-2.21 | 16.9% | 3 |
| n=20000 btree::map find | 315.5 | 318.5 | 0.992 | 0.91-1.01 | 6.1% | 3 |
| n=200000 btree::map emplace random | 1407.3 | 688.2 | 1.936 | 1.92-2.08 | 7.6% | 3 |
| n=200000 btree::map emplace sorted | 301.2 | 234.5 | 1.273 | 1.27-1.36 | 3.4% | 3 |
| n=200000 btree::map operator[] | 1461.9 | 693.4 | 2.158 | 1.77-2.16 | 10.8% | 3 |
| n=200000 btree::map find | 624.1 | 621.6 | 1.004 | 0.99-1.02 | 3.5% | 3 |

#### int-keys (`btree_int`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| map<u64,u64> n=1000 insert | 61.07 | 59.41 | 1.027 | 1.01-1.04 | 1.4% | 3 |
| map<u64,u64> n=1000 find | 30.52 | 30.36 | 1.008 | 1.01-1.01 | 1.9% | 3 |
| map<u64,u64> n=1000 iterate | 1.040 | 1.125 | 0.922 **<0.97** | 0.91-0.94 | 1.9% | 3 |
| map<u64,u64> n=1000 copy | 6.038 | 5.817 | 1.049 | 1.03-1.05 | 3.3% | 3 |
| map<u64,u64> n=1000 copy+erase | 52.73 | 53.28 | 0.990 | 0.98-1.01 | 2.7% | 3 |
| set<u64> n=1000 insert | 53.85 | 53.42 | 0.984 | 0.98-1.01 | 1.8% | 3 |
| set<u64> n=1000 find | 32.59 | 32.52 | 1.002 | 0.98-1.02 | 1.7% | 3 |
| set<u64> n=1000 iterate | 1.136 | 0.956 | 1.124 | 1.12-1.23 | 3.7% | 3 |
| set<u64> n=1000 copy+erase | 53.57 | 53.90 | 0.980 | 0.97-1.04 | 5.7% | 3 |
| map<u64,u64> n=100000 insert | 116.4 | 113.5 | 1.025 | 1.01-1.03 | 1.1% | 3 |
| map<u64,u64> n=100000 find | 80.66 | 80.38 | 1.004 | 0.98-1.03 | 1.6% | 3 |
| map<u64,u64> n=100000 iterate | 1.964 | 1.993 | 1.001 | 0.98-1.01 | 7.3% | 3 |
| map<u64,u64> n=100000 copy | 9.768 | 9.646 | 1.012 | 1.00-1.01 | 4.1% | 3 |
| map<u64,u64> n=100000 copy+erase | 105.7 | 104.9 | 1.024 | 0.98-1.03 | 0.9% | 3 |
| set<u64> n=100000 insert | 101.3 | 101.1 | 0.993 | 0.99-1.00 | 1.5% | 3 |
| set<u64> n=100000 find | 74.93 | 74.85 | 1.002 | 0.96-1.01 | 2.8% | 3 |
| set<u64> n=100000 iterate | 1.432 | 1.268 | 1.129 | 1.12-1.18 | 6.5% | 3 |
| set<u64> n=100000 copy+erase | 97.24 | 97.94 | 0.993 | 0.99-0.99 | 0.9% | 3 |
| map<u64,u64> n=1000000 insert | 188.3 | 187.5 | 1.007 | 1.00-1.02 | 2.6% | 3 |
| map<u64,u64> n=1000000 find | 175.4 | 177.2 | 0.984 | 0.97-1.01 | 2.1% | 3 |
| map<u64,u64> n=1000000 iterate | 7.140 | 7.139 | 1.035 | 0.90-1.09 | 8.5% | 3 |
| map<u64,u64> n=1000000 copy | 20.42 | 19.53 | 1.044 | 1.03-1.12 | 11.4% | 3 |
| map<u64,u64> n=1000000 copy+erase | 187.4 | 189.7 | 0.988 | 0.98-0.99 | 1.8% | 3 |
| set<u64> n=1000000 insert | 129.5 | 131.4 | 0.986 | 0.94-1.02 | 2.4% | 3 |
| set<u64> n=1000000 find | 120.3 | 118.3 | 1.025 | 0.87-1.03 | 10.7% | 3 |
| set<u64> n=1000000 iterate | 2.067 | 1.816 | 1.143 | 0.90-1.19 | 16.2% | 3 |
| set<u64> n=1000000 copy+erase | 134.6 | 135.4 | 0.996 | 0.99-1.00 | 1.4% | 3 |

**Geomean START/HEAD (Intel i9-9980HK): 1.118** over 45 library rows (controls, 0 rows: -)

Rows >1.03: 15; within 0.97-1.03: 27; <0.97: 3 (1 outside the A/A spread, 2 inside it).

## Findings: btree

- **M4 Pro (3 rounds, 45 library rows): geomean 1.069** (14 rows above 1.03, 24 within 0.97-1.03, 7 below 0.97 of which 5 outside the A/A spread and 2 inside it).
  - **Heap-allocated string keys are faster**: `mutation_bench` insert+erase of 65,536 entries is 1.31x faster with 32-byte keys (226.6 -> 166.1 ms CPU) and 1.30x with 200-byte keys (345.8 -> 268.6 ms); `string_insert_bench` `emplace` random 1.87x (n=20,000) and 1.63x (n=200,000), sorted 1.48x and 1.37x, `operator[]` 1.85x and 1.69x; copy 1.17x and pruned copy 1.14x (A/A max dev 54.7% and 14.5%, so only the direction is established). `find` is level: 1.016 at n=20,000 and 1.224 at 200,000 (A/A 14.1%, range 0.84-1.23).
  - **Short keys (inline in libc++'s small-string buffer) are level**: insert+erase with 12-byte keys 1.011 (A/A 22.7%, range 0.92-1.18).
  - **Integer keys are level**: the 27 `btree_int` rows have a geomean of 0.988 (A/A max dev 0.8-6.0% below 1M entries, up to 40% at 1M).
- **M4 rows below 0.97 outside the A/A spread: 5.** Four of them are 3.2-3.4% slower with an A/A spread of 1.1-2.6%, i.e. at the edge of the measurement: `map<u64,u64>` n=100,000 `find` 0.966, `set<u64>` n=100,000 copy+erase 0.966, `map<u64,u64>` n=1,000 `insert` 0.967, and `insert-erase` with 16-byte keys 0.968. HEAD's CHANGELOG states the same bound ("the `u64` rows ... stay within 3.5% of master in both compilers, inside their A/A spread") and its 16-byte-key row reads 265 -> 256 ms in the other direction on the i9; the changes touch map slot construction and relocation, not the search or the set. Cause: unexplained, at most 3.4% in 3 rounds; more rounds (the 3-round batch took 1 minute 42 seconds, so 15 rounds fit one hold) would settle it. The fifth is `ownership_bench` `move-construct`, 0.002 ms against 0.004 ms for 128 whole-container moves (A/A max dev 60%): each is a root-pointer transfer of microseconds, the three per-round values (START 2, 2, 2 µs; HEAD 2, 5, 4 µs; A/A 5, 2, 3 µs) are inside the clock's noise, and the row cannot show a speed difference at this scale.
- **i9 (3 rounds, 45 library rows): geomean 1.118** (15 rows above 1.03, 27 within 0.97-1.03, 3 below 0.97, 1 outside the A/A spread). Heap-allocated string keys: insert+erase 2.02x with 32-byte keys (693.4 -> 344.2 ms) and 1.44x with 200-byte keys (782.6 -> 545.1), `emplace` random 2.20x (n=20,000) and 1.94x (n=200,000), sorted 1.37x and 1.27x, `operator[]` 2.15x and 2.16x; `find` level (0.992 and 1.004). Short keys level (12 bytes 1.030, 16 bytes 0.993); copy 1.03x; 27 integer-key rows geomean 1.017 (A/A max dev 0.9-16%). The CHANGELOG's own i9 numbers agree (`emplace` 1658 -> 679 ns, `mutation_bench` 32-byte keys 689 -> 350 ms, 200-byte 799 -> 546).
- **i9 rows below 0.97: 1 outside the A/A spread**, `map<u64,u64>` n=1,000 `iterate` 0.922 (1.040 -> 1.125 ns per element; A/A max dev 1.9%). The iterator code did not change, the same loop over `set<u64>` at the same size is 1.124x faster (1.136 -> 0.956), and the n=100,000 and n=1,000,000 `map` rows are 1.001 and 1.035: a code-layout effect of a loop that takes about 1 ns per element, unexplained beyond that. Two more rows are below 0.97 inside their A/A spread (`ownership` `move-assign-empty` 0.004 -> 0.005 ms, 128 pointer transfers, A/A 33%; `copy-pruned` 0.964, A/A 13%).
- **Deterministic evidence (both machines the same, measured here):** with 32- and 200-byte keys HEAD makes 2.8x fewer allocation calls on insertion (420,230 -> 147,659), 3.4x fewer requested bytes at 200 bytes, and no allocation on erase (START 72,692 calls); 12- and 16-byte keys are level (82,130 -> 82,123 calls).
- **Not comparable / behaviour changes:** START fails `tests/relocation_failure.cc` (live allocations change after a refused insertion) and `tests/key_relocation.cc` (107,280 key copies while building), and crashes (rc 134) in Detent's allocation-refusal sweep with long names; HEAD passes. Those fixes are why the string-key rows are faster: START copied the const key at every reshape.

**Verdict: FASTER** for heap-allocated keys (1.3-1.9x on the M4, 1.4-2.2x on the i9), **SAME** for integer and short keys, with the borderline rows listed above (largest: i9 `map` n=1,000 `iterate` 0.92; M4 four rows at 0.966-0.968).

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- M4 `map<u64,u64>` `find` n=100,000 0.966, `set<u64>` copy and erase n=100,000 0.966,
  `map<u64,u64>` `insert` n=1,000 0.967, `insert-erase` with 16-byte keys 0.968: open, within 3.4%;
  the change touches slot construction and relocation, not search. No issue filed.
- M4 `ownership_bench` `move-construct` 0.500: noise. A root-pointer transfer of microseconds,
  with an A/A deviation of 60%.
- i9 `map<u64,u64>` `iterate` n=1,000 0.922: placement. The iterator is unchanged, and the same loop
  over `set<u64>` reads 1.124.
