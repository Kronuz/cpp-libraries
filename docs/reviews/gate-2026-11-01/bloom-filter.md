# Gate: bloom-filter

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/bloom-filter#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `0410185` | 2026-10-28 04:27:13 -0700 | Credit Germán Méndez Bravo and bound Dubalu's years |
| HEAD (`origin/main` when pinned, 2026-11-01) | `638fcad` | 2026-11-01 06:06:12 -0800 | Re-measure the bloom benchmark and name Boost 1.92.0 |

Library sources changed between them (docs, tests, benches, CI excluded): 1 file changed, 137 insertions(+).

## Method (common to every machine)

- Two worktrees of one clone, at START and at HEAD. The bench source is HEAD's (or, where stated, a copy of it with the rows START cannot compile removed, or a micro-bench written for the gate, not kept); each is compiled twice, once with `-I <START tree>` (binary A) and once with `-I <HEAD tree>` (binary B), same compiler, flags and source path. A/A is a byte copy of A.
- Flags: `c++ -std=c++20 -O3 -DNDEBUG -pthread` (Apple clang 17.0.0: M4 Pro `clang-1700.3.19.1`, i9 `clang-1700.6.4.2`). Comparator libraries are not linked or fetched. Only `flat-map`'s bench finds them by itself (`__has_include`): `absl::btree_map` is on the default include path of both machines and `boost::container::flat_map` on the i9's only, so that bench has abseil rows on the M4 and boost and abseil rows on the i9 (controls: they run no code of this repo).
- Rounds: every round runs each bench entry with A, B and AA (order `a b aa` on odd rounds, `aa b a` on even ones), under one `quiet strict` hold per repo and machine (on macOS a strict hold is exclusive). `runab.sh` writes one file per run; `ab_compare.py compare --format unit` pairs run i of A with run i of B (and of AA) and reports the median ratio.
- **Ratio = START time / HEAD time, so above 1 means HEAD is faster.** Throughputs are converted to ns per item. `A/A max dev` is the largest |ratio - 1| of A against its own copy over the same rounds: the measurement's noise. Rows marked `(control)` run code the change cannot reach (a standard-library or baseline arm); they show the noise floor and are left out of the geomean.
- A row is listed as "<0.97 outside A/A" when its ratio is below 0.97 and also below 1/(1 + A/A max dev).

## What was measured

- `bench/bloom_bench.cc` (`bloom_bench`): add, hit and miss, ns per operation, best of 7, for `N` = 8192 and 131072 with 16-byte keys and 131072 with 64-byte keys; the false-positive and false-negative counts are printed too (both are 0 and unchanged: the legacy filter sets the same bits).
- **Rows dropped because START cannot compile them:** HEAD's bench also times `FastBloomFilter` and `BlockedBloomFilter`. They are new opt-in types (2026-10-31); START has no counterpart, so their two lines are removed from a copy of the bench (`gate/patched/bloom-filter/bloom_bench.cc`). What remains is the START API, `BloomFilter<N>` (the "legacy" row).
- `hashes` (`xxh64::hash`, `fnv1ah64::hash`) is not part of this repo: both binaries include the same checkout (`Kronuz/hashes` `169d1d1`, `static-string` `cfa8127`, `char-classify` `65c1ff5`), so a `hashes` change cannot move a row.
- **The legacy class did not change.** `bloom_filter.hh` between START and HEAD is pure addition (the `<array>`/`<cstdint>` includes and the two new classes below the old class); the `BloomFilter<N>` text is untouched, and so is its bit layout. Any ratio away from 1 is layout or host state.


### Apple M4 Pro

#### main (`bloom_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| N=8192 keylen=16 BloomFilter (legacy) add | 17.78 | 17.97 | 0.986 | 0.98-1.01 | 3.7% | 3 |
| N=8192 keylen=16 BloomFilter (legacy) hit | 17.23 | 17.21 | 1.001 | 0.98-1.02 | 4.1% | 3 |
| N=8192 keylen=16 BloomFilter (legacy) miss | 23.13 | 23.17 | 0.998 | 0.98-1.01 | 3.7% | 3 |
| N=131072 keylen=16 BloomFilter (legacy) add | 21.05 | 21.21 | 0.992 | 0.97-1.00 | 5.5% | 3 |
| N=131072 keylen=16 BloomFilter (legacy) hit | 19.12 | 18.87 | 1.013 | 1.00-1.01 | 1.8% | 3 |
| N=131072 keylen=16 BloomFilter (legacy) miss | 27.83 | 27.99 | 0.994 | 0.98-1.00 | 2.7% | 3 |
| N=131072 keylen=64 BloomFilter (legacy) add | 61.13 | 61.79 | 0.989 | 0.98-0.99 | 1.4% | 3 |
| N=131072 keylen=64 BloomFilter (legacy) hit | 61.51 | 61.43 | 1.011 | 0.98-1.02 | 1.8% | 3 |
| N=131072 keylen=64 BloomFilter (legacy) miss | 73.35 | 72.87 | 1.007 | 0.98-1.02 | 2.4% | 3 |

**Geomean START/HEAD (Apple M4 Pro): 0.999** over 9 library rows (controls, 0 rows: -)

Rows >1.03: 0; within 0.97-1.03: 9; <0.97: 0 (0 outside the A/A spread, 0 inside it).

### Intel i9-9980HK

#### main (`bloom_bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| N=8192 keylen=16 BloomFilter (legacy) add | 33.58 | 37.32 | 0.900 **<0.97** | 0.84-1.00 | 0.1% | 3 |
| N=8192 keylen=16 BloomFilter (legacy) hit | 28.74 | 30.53 | 0.940 **<0.97** | 0.84-1.00 | 0.2% | 3 |
| N=8192 keylen=16 BloomFilter (legacy) miss | 27.34 | 27.46 | 0.994 | 0.85-1.00 | 0.6% | 3 |
| N=131072 keylen=16 BloomFilter (legacy) add | 47.48 | 46.71 | 1.013 | 0.99-1.02 | 2.2% | 3 |
| N=131072 keylen=16 BloomFilter (legacy) hit | 38.59 | 37.28 | 1.032 | 1.00-1.06 | 3.7% | 3 |
| N=131072 keylen=16 BloomFilter (legacy) miss | 35.88 | 36.02 | 0.985 | 0.97-1.06 | 7.0% | 3 |
| N=131072 keylen=64 BloomFilter (legacy) add | 100.1 | 102.4 | 0.996 | 0.97-1.03 | 7.3% | 3 |
| N=131072 keylen=64 BloomFilter (legacy) hit | 94.17 | 95.10 | 1.005 | 0.98-1.01 | 13.4% | 3 |
| N=131072 keylen=64 BloomFilter (legacy) miss | 88.36 | 88.64 | 0.997 | 0.99-1.01 | 2.3% | 3 |

**Geomean START/HEAD (Intel i9-9980HK): 0.984** over 9 library rows (controls, 0 rows: -)

Rows >1.03: 1; within 0.97-1.03: 6; <0.97: 2 (2 outside the A/A spread, 0 inside it).

## Findings: bloom-filter

- **M4 Pro: all 9 rows within 0.986-1.013** (geomean 0.999, A/A max dev 1.4-5.5%).
- **i9: two rows below 0.97 outside the A/A spread**, `N=8192 keylen=16` `add` (0.900) and `hit` (0.940). They are not a regression of the legacy filter: the source is unchanged and the per-round values show B settling onto A. START's `add` ns per run: 33.60, 33.58, 33.57; HEAD's: 39.93, 37.32, 33.58; the A/A copy: 33.59, 33.62, 33.61. HEAD's binary was slow in rounds 1 and 2 and equal to START in round 3 (33.58 against 33.57, `hit` 28.74 against 28.74), while A and AA stayed within 0.2% of each other, so the A/A spread (0.1%) is a poor bound on a transient that hit only B. HEAD's own CHANGELOG records the same effect: "the spread between builds of the unchanged `BloomFilter` is up to 12% on the i9". Cause: a start-up/host-state transient of the B runs plus that known build-to-build spread, unexplained beyond that; a longer run (15 rounds, about 1 minute) would settle it and was not obtained in this pass (see Status).
- The other 7 i9 rows are within 0.985-1.032 (geomean over the 9 rows 0.984).
- **Not comparable / added:** `FastBloomFilter` and `BlockedBloomFilter` have no START counterpart. HEAD's CHANGELOG measures them against the legacy filter (`N = 131072`, 16-byte keys, miss, ns: M4 8.0 and 8.5 against 27.7; i9 20.6 and 18.4 against 36.0; 64-byte keys M4 11.9 / 12.1 against 73.4, i9 31.7 / 31.1 against 96.1); this gate did not time them, since START has no row to compare with. `BloomFilter<N>` keeps its layout, so a persisted bitset still loads.

**Verdict: SAME** for the START API (identical source), plus new opt-in types.

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 19:15 PST, after the last fixes of the day; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- i9 `N=8192 keylen=16` `add` 0.900 and `hit` 0.940: placement. The source of `BloomFilter` is
  unchanged; the i9 shows up to 12% between builds of the same code.
