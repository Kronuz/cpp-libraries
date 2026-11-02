# Gate: flat-map

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/flat-map#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

Owner question (2026-11-01 08:41): is this library in a substantially better position than at the start, and is any part slower than it was?

| | commit | date | subject |
|---|---|---|---|
| START (last on `origin/main` before 2026-10-30) | `a9a52b0` | 2026-10-24 05:47:26 -0700 | Extract the corrected C++20 sorted-vector map |
| HEAD (`origin/main` when pinned, 2026-11-01) | `d43bfb5` | 2026-11-01 06:15:42 -0800 | Re-measure flat-map on the M4 Pro and name Boost 1.92.0 |

Library sources changed between them (docs, tests, benches, CI excluded): 2 files changed, 180 insertions(+), 22 deletions(-).

## Method (common to every machine)

- Two worktrees of one clone, at START and at HEAD. The bench source is HEAD's (or, where stated, a copy of it with the rows START cannot compile removed, or a micro-bench written for the gate, not kept); each is compiled twice, once with `-I <START tree>` (binary A) and once with `-I <HEAD tree>` (binary B), same compiler, flags and source path. A/A is a byte copy of A.
- Flags: `c++ -std=c++20 -O3 -DNDEBUG -pthread` (Apple clang 17.0.0: M4 Pro `clang-1700.3.19.1`, i9 `clang-1700.6.4.2`). Comparator libraries are not linked or fetched. Only `flat-map`'s bench finds them by itself (`__has_include`): `absl::btree_map` is on the default include path of both machines and `boost::container::flat_map` on the i9's only, so that bench has abseil rows on the M4 and boost and abseil rows on the i9 (controls: they run no code of this repo).
- Rounds: every round runs each bench entry with A, B and AA (order `a b aa` on odd rounds, `aa b a` on even ones), under one `quiet strict` hold per repo and machine (on macOS a strict hold is exclusive). `runab.sh` writes one file per run; `ab_compare.py compare --format unit` pairs run i of A with run i of B (and of AA) and reports the median ratio.
- **Ratio = START time / HEAD time, so above 1 means HEAD is faster.** Throughputs are converted to ns per item. `A/A max dev` is the largest |ratio - 1| of A against its own copy over the same rounds: the measurement's noise. Rows marked `(control)` run code the change cannot reach (a standard-library or baseline arm); they show the noise floor and are left out of the geomean.
- A row is listed as "<0.97 outside A/A" when its ratio is below 0.97 and also below 1/(1 + A/A max dev).

## What was measured

- `bench/bench.cc` (`flat_map_bench`), no arguments: `kronuz::flat_map` only (the boost and abseil comparators are not on the include path). Rows by key and mapped type and table size: `<u64,u64>` at 256, 4096, 65536 and 1,048,576 entries, `<u32,u32>` at 16, 64 and 4096, `<i8,u64>` at 100, `<string,u64>` at 32, `<u64,string>`, `<string,string>` and `<u64,u64[8]>` at 1024 (and 262,144 for the last). Per row: `insert` (fresh map filled with `try_emplace`, skipped above 65,536 entries), `find` (the same queries replayed in the same order, which a branch predictor can learn) and `find(stream)` (2^18 random queries). Best of 5, ns per operation.
- **Not run: `bench/crossover.cc`.** It times HEAD's internal search kernels (`kronuz::flat_map_detail::lower_bound_binary` and friends), which START does not have; it does not compile against START and has no START row to compare with.
- The bench drives only `try_emplace`, `find`, `end` and `size`, which START provides, so no row was dropped.
- Library change in scope (`flat_map.hh`, +201 lines): an integer-key search without branches (compare marked unpredictable), a prefetching search for tables of 512 KiB or more, `insert` that works on an index and shifts the tail with `memmove` (32 entries or more) or `vector::insert`, and a `memmove` byte shift gated on the types being implicit-lifetime.


### Apple M4 Pro

#### main (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| <u64,u64> n=256 kronuz::flat_map insert | 32.15 | 26.15 | 1.218 | 1.19-1.24 | 3.5% | 3 |
| <u64,u64> n=256 kronuz::flat_map find | 5.990 | 3.890 | 1.540 | 1.52-1.60 | 4.8% | 3 |
| <u64,u64> n=256 kronuz::flat_map find(stream) | 6.100 | 3.860 | 1.567 | 1.56-1.64 | 2.4% | 3 |
| <u64,u64> n=256 absl::btree_map insert (control) | 14.21 | 14.07 | 1.007 | 0.99-1.03 | 4.8% | 3 |
| <u64,u64> n=256 absl::btree_map find (control) | 7.740 | 7.820 | 1.001 | 0.96-1.02 | 1.0% | 3 |
| <u64,u64> n=256 absl::btree_map find(stream) (control) | 19.09 | 19.28 | 0.990 | 0.95-1.04 | 4.1% | 3 |
| <u64,u64> n=4096 kronuz::flat_map insert | 299.6 | 171.4 | 1.742 | 1.73-1.77 | 2.4% | 3 |
| <u64,u64> n=4096 kronuz::flat_map find | 11.15 | 6.430 | 1.734 | 1.71-1.75 | 2.9% | 3 |
| <u64,u64> n=4096 kronuz::flat_map find(stream) | 11.08 | 6.440 | 1.726 | 1.71-1.74 | 2.0% | 3 |
| <u64,u64> n=4096 absl::btree_map insert (control) | 25.53 | 22.59 | 1.243 | 0.97-1.41 | 64.0% | 3 |
| <u64,u64> n=4096 absl::btree_map find (control) | 17.97 | 20.18 | 0.906 | 0.89-1.29 | 50.7% | 3 |
| <u64,u64> n=4096 absl::btree_map find(stream) (control) | 29.56 | 30.07 | 0.983 | 0.96-1.02 | 2.6% | 3 |
| <u64,u64> n=65536 kronuz::flat_map insert | 5409.7 | 3758.0 | 1.440 | 1.42-1.46 | 1.0% | 3 |
| <u64,u64> n=65536 kronuz::flat_map find | 40.53 | 27.74 | 1.451 | 1.44-1.47 | 5.6% | 3 |
| <u64,u64> n=65536 kronuz::flat_map find(stream) | 38.93 | 27.06 | 1.439 | 1.38-1.53 | 6.0% | 3 |
| <u64,u64> n=65536 absl::btree_map insert (control) | 67.20 | 66.70 | 0.997 | 0.99-1.03 | 3.7% | 3 |
| <u64,u64> n=65536 absl::btree_map find (control) | 50.20 | 51.45 | 0.984 | 0.94-0.99 | 2.3% | 3 |
| <u64,u64> n=65536 absl::btree_map find(stream) (control) | 50.68 | 50.21 | 1.012 | 0.99-1.03 | 2.4% | 3 |
| <u64,u64> n=1048576 kronuz::flat_map find | 138.7 | 71.64 | 1.842 | 1.66-1.96 | 29.9% | 3 |
| <u64,u64> n=1048576 kronuz::flat_map find(stream) | 125.5 | 75.96 | 1.773 | 1.36-2.02 | 30.3% | 3 |
| <u64,u64> n=1048576 absl::btree_map find (control) | 111.7 | 104.2 | 1.110 | 0.81-1.11 | 16.6% | 3 |
| <u64,u64> n=1048576 absl::btree_map find(stream) (control) | 109.7 | 111.6 | 0.952 | 0.82-0.98 | 8.6% | 3 |
| <u32,u32> n=16 kronuz::flat_map insert | 11.13 | 11.24 | 0.994 | 0.99-1.00 | 13.9% | 3 |
| <u32,u32> n=16 kronuz::flat_map find | 2.510 | 2.170 | 1.171 | 1.16-1.18 | 3.5% | 3 |
| <u32,u32> n=16 kronuz::flat_map find(stream) | 3.800 | 2.080 | 1.832 | 1.83-1.88 | 1.6% | 3 |
| <u32,u32> n=16 absl::btree_map insert (control) | 11.42 | 10.96 | 1.003 | 0.89-1.06 | 10.6% | 3 |
| <u32,u32> n=16 absl::btree_map find (control) | 3.310 | 3.690 | 0.932 | 0.86-0.95 | 11.4% | 3 |
| <u32,u32> n=16 absl::btree_map find(stream) (control) | 7.740 | 7.970 | 0.976 | 0.96-0.99 | 2.8% | 3 |
| <u32,u32> n=64 kronuz::flat_map insert | 13.84 | 14.26 | 0.966 (<0.97, inside A/A) | 0.96-0.98 | 4.5% | 3 |
| <u32,u32> n=64 kronuz::flat_map find | 4.440 | 2.810 | 1.580 | 1.55-1.60 | 3.5% | 3 |
| <u32,u32> n=64 kronuz::flat_map find(stream) | 4.450 | 2.720 | 1.636 | 1.60-1.65 | 2.0% | 3 |
| <u32,u32> n=64 absl::btree_map insert (control) | 11.09 | 11.82 | 0.938 | 0.89-0.96 | 4.9% | 3 |
| <u32,u32> n=64 absl::btree_map find (control) | 6.510 | 6.620 | 0.976 | 0.93-0.99 | 1.4% | 3 |
| <u32,u32> n=64 absl::btree_map find(stream) (control) | 14.87 | 14.98 | 0.997 | 0.99-1.00 | 1.1% | 3 |
| <u32,u32> n=4096 kronuz::flat_map insert | 301.6 | 102.5 | 2.938 | 2.91-2.97 | 1.2% | 3 |
| <u32,u32> n=4096 kronuz::flat_map find | 11.05 | 6.400 | 1.727 | 1.73-1.73 | 1.6% | 3 |
| <u32,u32> n=4096 kronuz::flat_map find(stream) | 11.08 | 6.410 | 1.734 | 1.73-1.74 | 1.4% | 3 |
| <u32,u32> n=4096 absl::btree_map insert (control) | 21.21 | 22.82 | 0.917 | 0.89-0.93 | 4.8% | 3 |
| <u32,u32> n=4096 absl::btree_map find (control) | 18.89 | 21.87 | 0.887 | 0.86-1.00 | 19.3% | 3 |
| <u32,u32> n=4096 absl::btree_map find(stream) (control) | 28.75 | 28.84 | 0.997 | 0.99-1.00 | 1.7% | 3 |
| <i8,u64> n=100 kronuz::flat_map insert | 18.11 | 17.58 | 1.030 | 1.01-1.05 | 3.4% | 3 |
| <i8,u64> n=100 kronuz::flat_map find | 4.800 | 3.240 | 1.481 | 1.43-1.50 | 1.3% | 3 |
| <i8,u64> n=100 kronuz::flat_map find(stream) | 8.160 | 3.240 | 2.528 | 2.50-2.53 | 2.5% | 3 |
| <i8,u64> n=100 absl::btree_map insert (control) | 11.49 | 11.88 | 0.956 | 0.95-1.00 | 1.5% | 3 |
| <i8,u64> n=100 absl::btree_map find (control) | 5.430 | 5.560 | 0.973 | 0.93-1.08 | 6.6% | 3 |
| <i8,u64> n=100 absl::btree_map find(stream) (control) | 15.28 | 15.11 | 1.008 | 0.99-1.01 | 2.3% | 3 |
| <string,u64> n=32 kronuz::flat_map insert | 19.72 | 20.56 | 0.959 **<0.97** | 0.92-0.97 | 1.7% | 3 |
| <string,u64> n=32 kronuz::flat_map find | 13.15 | 13.47 | 0.976 | 0.97-1.03 | 4.2% | 3 |
| <string,u64> n=32 kronuz::flat_map find(stream) | 34.77 | 35.08 | 0.997 | 0.97-1.00 | 1.0% | 3 |
| <string,u64> n=32 absl::btree_map insert (control) | 23.65 | 22.38 | 1.057 | 1.04-1.07 | 3.7% | 3 |
| <string,u64> n=32 absl::btree_map find (control) | 9.690 | 9.740 | 1.002 | 0.99-1.00 | 6.3% | 3 |
| <string,u64> n=32 absl::btree_map find(stream) (control) | 26.85 | 26.81 | 1.007 | 1.00-1.01 | 2.3% | 3 |
| <u64,string> n=1024 kronuz::flat_map insert | 227.4 | 223.6 | 1.009 | 1.00-1.02 | 1.6% | 3 |
| <u64,string> n=1024 kronuz::flat_map find | 8.460 | 5.080 | 1.662 | 1.66-1.69 | 2.1% | 3 |
| <u64,string> n=1024 kronuz::flat_map find(stream) | 8.480 | 5.100 | 1.675 | 1.66-1.68 | 1.6% | 3 |
| <u64,string> n=1024 absl::btree_map insert (control) | 37.93 | 37.11 | 0.995 | 0.99-1.04 | 5.2% | 3 |
| <u64,string> n=1024 absl::btree_map find (control) | 8.730 | 8.720 | 1.001 | 0.96-1.03 | 1.7% | 3 |
| <u64,string> n=1024 absl::btree_map find(stream) (control) | 27.04 | 27.08 | 1.005 | 0.99-1.02 | 3.2% | 3 |
| <string,string> n=1024 kronuz::flat_map insert | 395.9 | 398.0 | 0.998 | 0.99-1.00 | 1.5% | 3 |
| <string,string> n=1024 kronuz::flat_map find | 25.77 | 27.12 | 0.961 (<0.97, inside A/A) | 0.92-0.97 | 7.0% | 3 |
| <string,string> n=1024 kronuz::flat_map find(stream) | 78.62 | 78.60 | 1.000 | 1.00-1.01 | 1.6% | 3 |
| <string,string> n=1024 absl::btree_map insert (control) | 59.39 | 61.86 | 0.962 | 0.95-1.04 | 6.3% | 3 |
| <string,string> n=1024 absl::btree_map find (control) | 28.36 | 28.34 | 1.055 | 0.86-1.07 | 3.1% | 3 |
| <string,string> n=1024 absl::btree_map find(stream) (control) | 64.63 | 64.78 | 1.000 | 1.00-1.01 | 0.7% | 3 |
| <u64,u64[8]> n=1024 kronuz::flat_map insert | 278.0 | 202.5 | 1.373 | 1.32-1.39 | 1.5% | 3 |
| <u64,u64[8]> n=1024 kronuz::flat_map find | 10.26 | 5.240 | 1.972 | 1.96-1.99 | 1.8% | 3 |
| <u64,u64[8]> n=1024 kronuz::flat_map find(stream) | 10.32 | 5.490 | 1.880 | 1.86-1.91 | 1.4% | 3 |
| <u64,u64[8]> n=1024 absl::btree_map insert (control) | 23.65 | 23.24 | 1.009 | 1.01-1.04 | 3.0% | 3 |
| <u64,u64[8]> n=1024 absl::btree_map find (control) | 9.300 | 9.020 | 1.025 | 1.02-1.03 | 1.6% | 3 |
| <u64,u64[8]> n=1024 absl::btree_map find(stream) (control) | 31.37 | 32.14 | 0.987 | 0.94-1.02 | 4.3% | 3 |
| <u64,u64[8]> n=262144 kronuz::flat_map find | 133.6 | 57.98 | 2.102 | 1.92-2.30 | 39.7% | 3 |
| <u64,u64[8]> n=262144 kronuz::flat_map find(stream) | 83.37 | 54.02 | 1.575 | 1.54-1.91 | 7.3% | 3 |
| <u64,u64[8]> n=262144 absl::btree_map find (control) | 208.0 | 169.1 | 0.977 | 0.90-1.25 | 46.1% | 3 |
| <u64,u64[8]> n=262144 absl::btree_map find(stream) (control) | 196.2 | 161.3 | 0.953 | 0.90-1.27 | 46.2% | 3 |

**Geomean START/HEAD (Apple M4 Pro): 1.458** over 37 library rows (controls, 37 rows: 0.992)

Rows >1.03: 28; within 0.97-1.03: 6; <0.97: 3 (1 outside the A/A spread, 2 inside it).

### Intel i9-9980HK

#### main (`bench`)

| row | START | HEAD | START/HEAD | range | A/A max dev | n |
|---|---:|---:|---:|---:|---:|---:|
| <u64,u64> n=256 kronuz::flat_map insert | 61.13 | 35.14 | 1.740 | 1.30-1.76 | 15.4% | 3 |
| <u64,u64> n=256 kronuz::flat_map find | 9.770 | 8.850 | 1.104 | 0.88-1.14 | 23.2% | 3 |
| <u64,u64> n=256 kronuz::flat_map find(stream) | 33.43 | 8.800 | 3.791 | 2.98-4.02 | 5.1% | 3 |
| <u64,u64> n=256 boost flat_map insert (control) | 24.53 | 27.96 | 0.890 | 0.68-0.89 | 6.1% | 3 |
| <u64,u64> n=256 boost flat_map find (control) | 8.240 | 10.94 | 0.753 | 0.52-0.78 | 6.5% | 3 |
| <u64,u64> n=256 boost flat_map find(stream) (control) | 33.61 | 36.54 | 0.907 | 0.72-0.95 | 5.0% | 3 |
| <u64,u64> n=256 absl::btree_map insert (control) | 21.70 | 24.49 | 0.895 | 0.62-0.92 | 3.6% | 3 |
| <u64,u64> n=256 absl::btree_map find (control) | 11.93 | 14.84 | 0.804 | 0.58-0.83 | 7.8% | 3 |
| <u64,u64> n=256 absl::btree_map find(stream) (control) | 27.28 | 29.58 | 0.922 | 0.70-0.94 | 5.7% | 3 |
| <u64,u64> n=4096 kronuz::flat_map insert | 578.7 | 193.7 | 2.987 | 2.14-3.18 | 2.0% | 3 |
| <u64,u64> n=4096 kronuz::flat_map find | 52.85 | 14.53 | 3.583 | 2.49-3.66 | 2.7% | 3 |
| <u64,u64> n=4096 kronuz::flat_map find(stream) | 53.26 | 15.06 | 3.537 | 2.54-3.54 | 3.0% | 3 |
| <u64,u64> n=4096 boost flat_map insert (control) | 211.1 | 213.4 | 0.989 | 0.80-0.99 | 5.8% | 3 |
| <u64,u64> n=4096 boost flat_map find (control) | 54.44 | 57.18 | 0.959 | 0.68-0.97 | 4.9% | 3 |
| <u64,u64> n=4096 boost flat_map find(stream) (control) | 53.55 | 55.29 | 0.978 | 0.70-0.99 | 2.2% | 3 |
| <u64,u64> n=4096 absl::btree_map insert (control) | 75.68 | 76.90 | 1.002 | 0.83-1.04 | 4.6% | 3 |
| <u64,u64> n=4096 absl::btree_map find (control) | 44.29 | 46.72 | 0.960 | 0.80-1.09 | 17.1% | 3 |
| <u64,u64> n=4096 absl::btree_map find(stream) (control) | 50.20 | 47.62 | 1.026 | 1.00-1.05 | 24.4% | 3 |
| <u64,u64> n=65536 kronuz::flat_map insert | 10575.9 | 5467.0 | 1.954 | 1.93-1.96 | 9.0% | 3 |
| <u64,u64> n=65536 kronuz::flat_map find | 114.0 | 49.41 | 2.350 | 2.08-2.35 | 9.1% | 3 |
| <u64,u64> n=65536 kronuz::flat_map find(stream) | 117.3 | 47.47 | 2.357 | 2.21-2.48 | 1.5% | 3 |
| <u64,u64> n=65536 boost flat_map insert (control) | 5471.2 | 5540.5 | 0.987 | 0.97-1.00 | 1.9% | 3 |
| <u64,u64> n=65536 boost flat_map find (control) | 123.0 | 120.8 | 1.015 | 0.97-1.07 | 12.6% | 3 |
| <u64,u64> n=65536 boost flat_map find(stream) (control) | 118.5 | 121.1 | 0.971 | 0.94-1.08 | 13.1% | 3 |
| <u64,u64> n=65536 absl::btree_map insert (control) | 107.5 | 106.2 | 1.006 | 0.99-1.03 | 16.0% | 3 |
| <u64,u64> n=65536 absl::btree_map find (control) | 71.50 | 72.31 | 0.977 | 0.97-0.99 | 14.2% | 3 |
| <u64,u64> n=65536 absl::btree_map find(stream) (control) | 73.99 | 73.60 | 0.998 | 0.96-1.01 | 12.7% | 3 |
| <u64,u64> n=1048576 kronuz::flat_map find | 242.5 | 110.8 | 2.171 | 2.17-2.21 | 9.0% | 3 |
| <u64,u64> n=1048576 kronuz::flat_map find(stream) | 242.8 | 117.5 | 2.066 | 2.00-2.08 | 12.1% | 3 |
| <u64,u64> n=1048576 boost flat_map find (control) | 242.1 | 246.4 | 0.996 | 0.91-1.01 | 23.2% | 3 |
| <u64,u64> n=1048576 boost flat_map find(stream) (control) | 246.1 | 247.2 | 0.988 | 0.97-1.34 | 30.7% | 3 |
| <u64,u64> n=1048576 absl::btree_map find (control) | 163.0 | 168.7 | 0.975 | 0.94-1.00 | 4.9% | 3 |
| <u64,u64> n=1048576 absl::btree_map find(stream) (control) | 161.7 | 162.8 | 0.992 | 0.98-1.02 | 4.6% | 3 |
| <u32,u32> n=16 kronuz::flat_map insert | 28.29 | 26.09 | 1.084 | 1.03-1.19 | 7.2% | 3 |
| <u32,u32> n=16 kronuz::flat_map find | 5.590 | 4.280 | 1.306 | 1.31-1.37 | 5.0% | 3 |
| <u32,u32> n=16 kronuz::flat_map find(stream) | 7.150 | 3.950 | 1.815 | 1.78-1.85 | 5.1% | 3 |
| <u32,u32> n=16 boost flat_map insert (control) | 35.82 | 35.46 | 1.023 | 0.98-1.04 | 3.3% | 3 |
| <u32,u32> n=16 boost flat_map find (control) | 5.670 | 5.680 | 0.998 | 1.00-1.02 | 0.7% | 3 |
| <u32,u32> n=16 boost flat_map find(stream) (control) | 7.260 | 7.230 | 1.004 | 0.93-1.11 | 12.9% | 3 |
| <u32,u32> n=16 absl::btree_map insert (control) | 22.42 | 20.78 | 1.079 | 0.88-1.22 | 14.2% | 3 |
| <u32,u32> n=16 absl::btree_map find (control) | 4.830 | 4.730 | 1.009 | 0.90-1.16 | 36.3% | 3 |
| <u32,u32> n=16 absl::btree_map find(stream) (control) | 13.00 | 12.76 | 1.007 | 1.00-1.11 | 9.0% | 3 |
| <u32,u32> n=64 kronuz::flat_map insert | 23.50 | 20.84 | 1.162 | 1.11-1.24 | 11.2% | 3 |
| <u32,u32> n=64 kronuz::flat_map find | 7.540 | 5.010 | 1.505 | 1.50-1.58 | 9.4% | 3 |
| <u32,u32> n=64 kronuz::flat_map find(stream) | 7.460 | 4.920 | 1.551 | 1.48-1.57 | 5.5% | 3 |
| <u32,u32> n=64 boost flat_map insert (control) | 24.44 | 24.65 | 0.991 | 0.99-1.00 | 6.3% | 3 |
| <u32,u32> n=64 boost flat_map find (control) | 7.560 | 7.620 | 0.993 | 0.98-0.99 | 0.8% | 3 |
| <u32,u32> n=64 boost flat_map find(stream) (control) | 8.050 | 7.750 | 1.039 | 1.03-1.13 | 12.8% | 3 |
| <u32,u32> n=64 absl::btree_map insert (control) | 18.95 | 17.67 | 1.043 | 1.04-1.21 | 5.6% | 3 |
| <u32,u32> n=64 absl::btree_map find (control) | 8.570 | 9.780 | 0.873 | 0.85-1.04 | 24.6% | 3 |
| <u32,u32> n=64 absl::btree_map find(stream) (control) | 23.00 | 21.75 | 1.050 | 1.04-1.07 | 13.0% | 3 |
| <u32,u32> n=4096 kronuz::flat_map insert | 541.5 | 89.90 | 6.040 | 5.69-6.14 | 1.9% | 3 |
| <u32,u32> n=4096 kronuz::flat_map find | 18.19 | 10.71 | 1.717 | 1.63-1.74 | 12.5% | 3 |
| <u32,u32> n=4096 kronuz::flat_map find(stream) | 18.32 | 10.73 | 1.736 | 1.68-1.74 | 8.9% | 3 |
| <u32,u32> n=4096 boost flat_map insert (control) | 95.83 | 92.78 | 1.043 | 0.95-1.05 | 1.8% | 3 |
| <u32,u32> n=4096 boost flat_map find (control) | 17.28 | 17.43 | 0.983 | 0.94-1.06 | 4.6% | 3 |
| <u32,u32> n=4096 boost flat_map find(stream) (control) | 19.24 | 18.36 | 1.069 | 0.97-1.08 | 7.3% | 3 |
| <u32,u32> n=4096 absl::btree_map insert (control) | 71.27 | 68.00 | 1.066 | 0.97-1.10 | 6.4% | 3 |
| <u32,u32> n=4096 absl::btree_map find (control) | 41.93 | 44.11 | 0.947 | 0.93-0.96 | 6.9% | 3 |
| <u32,u32> n=4096 absl::btree_map find(stream) (control) | 45.75 | 43.51 | 1.047 | 1.04-1.12 | 10.9% | 3 |
| <i8,u64> n=100 kronuz::flat_map insert | 27.52 | 23.99 | 1.205 | 1.12-1.29 | 14.3% | 3 |
| <i8,u64> n=100 kronuz::flat_map find | 4.880 | 6.440 | 0.758 **<0.97** | 0.75-0.93 | 17.3% | 3 |
| <i8,u64> n=100 kronuz::flat_map find(stream) | 27.05 | 6.820 | 3.886 | 3.87-4.41 | 12.2% | 3 |
| <i8,u64> n=100 boost flat_map insert (control) | 21.46 | 21.25 | 1.010 | 0.96-1.16 | 10.2% | 3 |
| <i8,u64> n=100 boost flat_map find (control) | 5.070 | 5.180 | 0.977 | 0.95-1.21 | 17.3% | 3 |
| <i8,u64> n=100 boost flat_map find(stream) (control) | 26.56 | 25.53 | 1.040 | 1.00-1.14 | 14.1% | 3 |
| <i8,u64> n=100 absl::btree_map insert (control) | 20.04 | 19.50 | 1.028 | 0.95-1.26 | 18.4% | 3 |
| <i8,u64> n=100 absl::btree_map find (control) | 7.540 | 8.660 | 0.887 | 0.64-1.04 | 13.0% | 3 |
| <i8,u64> n=100 absl::btree_map find(stream) (control) | 23.18 | 23.30 | 0.992 | 0.99-1.12 | 15.4% | 3 |
| <string,u64> n=32 kronuz::flat_map insert | 52.48 | 59.19 | 0.914 (<0.97, inside A/A) | 0.83-0.95 | 16.5% | 3 |
| <string,u64> n=32 kronuz::flat_map find | 49.54 | 49.82 | 0.983 | 0.96-1.11 | 10.2% | 3 |
| <string,u64> n=32 kronuz::flat_map find(stream) | 54.41 | 54.22 | 0.989 | 0.99-1.00 | 1.1% | 3 |
| <string,u64> n=32 boost flat_map insert (control) | 57.72 | 57.46 | 0.972 | 0.95-1.01 | 6.5% | 3 |
| <string,u64> n=32 boost flat_map find (control) | 48.36 | 48.89 | 0.988 | 0.91-0.99 | 2.1% | 3 |
| <string,u64> n=32 boost flat_map find(stream) (control) | 59.05 | 57.68 | 1.022 | 1.01-1.02 | 3.2% | 3 |
| <string,u64> n=32 absl::btree_map insert (control) | 56.74 | 56.02 | 1.019 | 0.99-1.02 | 14.5% | 3 |
| <string,u64> n=32 absl::btree_map find (control) | 35.01 | 32.47 | 1.027 | 0.99-1.08 | 14.2% | 3 |
| <string,u64> n=32 absl::btree_map find(stream) (control) | 46.98 | 47.38 | 0.992 | 0.99-1.03 | 14.5% | 3 |
| <u64,string> n=1024 kronuz::flat_map insert | 532.9 | 321.9 | 1.657 | 1.63-1.74 | 14.2% | 3 |
| <u64,string> n=1024 kronuz::flat_map find | 38.11 | 9.370 | 4.067 | 4.07-4.20 | 16.7% | 3 |
| <u64,string> n=1024 kronuz::flat_map find(stream) | 46.02 | 9.610 | 4.799 | 4.44-5.32 | 15.3% | 3 |
| <u64,string> n=1024 boost flat_map insert (control) | 357.3 | 341.9 | 1.053 | 0.97-1.11 | 6.6% | 3 |
| <u64,string> n=1024 boost flat_map find (control) | 39.73 | 39.81 | 0.998 | 0.83-1.02 | 9.0% | 3 |
| <u64,string> n=1024 boost flat_map find(stream) (control) | 42.01 | 42.85 | 0.980 | 0.97-1.00 | 8.2% | 3 |
| <u64,string> n=1024 absl::btree_map insert (control) | 130.2 | 131.7 | 0.988 | 0.96-1.06 | 15.8% | 3 |
| <u64,string> n=1024 absl::btree_map find (control) | 29.66 | 31.46 | 0.939 | 0.90-0.94 | 17.7% | 3 |
| <u64,string> n=1024 absl::btree_map find(stream) (control) | 40.31 | 40.40 | 0.988 | 0.96-1.02 | 16.8% | 3 |
| <string,string> n=1024 kronuz::flat_map insert | 559.9 | 566.1 | 1.008 | 0.95-1.01 | 18.1% | 3 |
| <string,string> n=1024 kronuz::flat_map find | 135.7 | 129.3 | 1.050 | 0.99-1.10 | 17.9% | 3 |
| <string,string> n=1024 kronuz::flat_map find(stream) | 123.3 | 134.6 | 0.916 (<0.97, inside A/A) | 0.89-0.92 | 13.1% | 3 |
| <string,string> n=1024 boost flat_map insert (control) | 580.8 | 591.7 | 1.020 | 0.97-1.11 | 27.8% | 3 |
| <string,string> n=1024 boost flat_map find (control) | 130.2 | 125.7 | 1.051 | 0.98-1.18 | 20.0% | 3 |
| <string,string> n=1024 boost flat_map find(stream) (control) | 134.0 | 130.3 | 1.026 | 1.02-1.03 | 16.2% | 3 |
| <string,string> n=1024 absl::btree_map insert (control) | 234.9 | 233.9 | 0.998 | 0.99-1.04 | 20.3% | 3 |
| <string,string> n=1024 absl::btree_map find (control) | 108.8 | 108.9 | 0.998 | 0.99-1.00 | 16.9% | 3 |
| <string,string> n=1024 absl::btree_map find(stream) (control) | 115.3 | 112.6 | 1.024 | 1.02-1.02 | 11.9% | 3 |
| <u64,u64[8]> n=1024 kronuz::flat_map insert | 447.4 | 215.4 | 2.101 | 1.98-2.23 | 18.5% | 3 |
| <u64,u64[8]> n=1024 kronuz::flat_map find | 39.39 | 10.32 | 3.825 | 3.79-3.90 | 17.7% | 3 |
| <u64,u64[8]> n=1024 kronuz::flat_map find(stream) | 42.88 | 10.56 | 4.048 | 4.03-4.22 | 10.4% | 3 |
| <u64,u64[8]> n=1024 boost flat_map insert (control) | 292.4 | 288.2 | 1.015 | 0.88-1.33 | 14.5% | 3 |
| <u64,u64[8]> n=1024 boost flat_map find (control) | 44.23 | 43.21 | 1.011 | 0.97-1.08 | 9.5% | 3 |
| <u64,u64[8]> n=1024 boost flat_map find(stream) (control) | 43.26 | 42.21 | 1.014 | 1.00-1.07 | 8.2% | 3 |
| <u64,u64[8]> n=1024 absl::btree_map insert (control) | 110.8 | 109.5 | 1.011 | 1.00-1.06 | 5.9% | 3 |
| <u64,u64[8]> n=1024 absl::btree_map find (control) | 36.01 | 35.83 | 1.005 | 0.98-1.02 | 24.2% | 3 |
| <u64,u64[8]> n=1024 absl::btree_map find(stream) (control) | 46.66 | 45.79 | 1.010 | 1.00-1.02 | 11.6% | 3 |
| <u64,u64[8]> n=262144 kronuz::flat_map find | 207.3 | 97.11 | 2.143 | 2.14-2.19 | 5.1% | 3 |
| <u64,u64[8]> n=262144 kronuz::flat_map find(stream) | 208.8 | 99.38 | 2.080 | 1.96-2.10 | 16.0% | 3 |
| <u64,u64[8]> n=262144 boost flat_map find (control) | 205.7 | 219.8 | 0.936 | 0.90-0.97 | 10.0% | 3 |
| <u64,u64[8]> n=262144 boost flat_map find(stream) (control) | 207.8 | 205.0 | 1.021 | 0.98-1.03 | 20.0% | 3 |
| <u64,u64[8]> n=262144 absl::btree_map find (control) | 196.6 | 205.0 | 0.957 | 0.95-0.98 | 43.5% | 3 |
| <u64,u64[8]> n=262144 absl::btree_map find(stream) (control) | 199.8 | 196.1 | 1.027 | 1.01-1.05 | 42.6% | 3 |

**Geomean START/HEAD (Intel i9-9980HK): 1.908** over 37 library rows (controls, 74 rows: 0.989)

Rows >1.03: 31; within 0.97-1.03: 3; <0.97: 3 (1 outside the A/A spread, 2 inside it).

## Findings: flat-map

- **i9 (3 rounds, 37 library rows): geomean 1.908.** Random-order `find` is 2.1-4.8x faster (`<u64,u64>` 4096: 3.58x, 65536: 2.35x, 1,048,576: 2.17x; `<u64,string>` 1024: 4.07x; `<u64,u64[8]>` 1024: 3.83x and 262,144: 2.14x; `<i8,u64>` 100 `find(stream)`: 3.89x), replayed `find` 1.3-3.6x faster on every table of 16 or more entries except the one row below. `insert` is 1.2-6.0x faster (`<u32,u32>` 4096 6.04x, `<u64,u64>` 4096 2.99x, 65536 1.95x, `<u64,u64[8]>` 2.10x, `<u64,string>` 1.66x, `<i8,u64>` 100 1.21x, `<u32,u32>` 16 / 64 1.08x / 1.16x). String-key rows are unchanged (they still use `std::lower_bound`): `find` 0.98-1.05, `insert` 0.91 and 1.01.
- **Rows below 0.97 outside the A/A spread: 1.** `<i8,u64>` n=100, `find` (the replayed row): START 4.88 ns, HEAD 6.44 ns, ratio 0.758 (A/A max dev 17.3%, range 0.75-0.93). This is the documented trade-off in HEAD's CHANGELOG ("A branch predictor learns `std::lower_bound` on a short table queried in the same order again and again", 5.0 ns against 6.4 ns on the i9; the same table queried at random is 26.3 -> 6.8 ns here, 3.89x). `flat_map_detail::search_for` is the one place to change it. Two more rows are below 0.97 inside their A/A spread and are on unchanged paths (`std::lower_bound` for string keys): `<string,u64>` 32 `insert` 0.914 (A/A 16.5%) and `<string,string>` 1024 `find(stream)` 0.916 (A/A 13.1%): noise.
- **Comparator rows (controls).** On the i9 the bench finds `boost::container::flat_map` and `absl::btree_map` through `__has_include`, so it has 74 comparator rows, which run no code of this repo: their geomean is 0.989. The `n=256` group, the first rows of a run, shows the host-state bias the CHANGELOG describes ("the first row of a run, up to 86% between runs"): its boost and abseil controls read 0.75-0.92 in this run, so the `<u64,u64>` n=256 library rows (insert 1.74x, find 1.10x, `find(stream)` 3.79x) are the least reliable numbers here.
- **Not comparable:** `bench/crossover.cc` times HEAD's internal search kernels and does not compile against START (see "What was measured"). HEAD's tests add the strategy checks; the START `insert` and `find` results are the same (the search and shift are an optimisation, not a behaviour change).

- **M4 Pro (3 rounds, 37 library rows): geomean 1.458** (28 rows above 1.03, 6 within 0.97-1.03, 3 below 0.97). `find` is 1.17-2.1x faster on every integer-key table (`<u64,u64>` 4096 1.73x, 65536 1.45x, 1,048,576 1.84x; `<u32,u32>` 64 1.58x; `<i8,u64>` 100 1.48x replayed and 2.53x random; `<u64,u64[8]>` 1024 1.97x and 262,144 2.10x); `insert` is 1.2-2.9x faster on tables of 256 or more (`<u32,u32>` 4096 2.94x, `<u64,u64>` 4096 1.74x, 65536 1.44x, `<u64,u64[8]>` 1.37x) and level on the small ones (`<u32,u32>` 16 0.994, `<i8,u64>` 100 1.030, `<u64,string>` 1.009). On the M4 the 100-entry `<i8,u64>` replayed `find` is 1.48x faster, not slower: the branch predictor trade-off is x86-only. The 37 `absl::btree_map` control rows (found on the M4's include path; no boost there) read 0.89-1.24 (geomean 0.992), with A/A max dev up to 64% on the n=4096 ones.
- **M4 rows below 0.97 outside the A/A spread: 1.** `<string,u64>` n=32 `insert`: 19.72 -> 20.56 ns, ratio 0.959 (A/A max dev 1.7%). It is a string-key path (still `std::lower_bound`); the change that reaches it is the rewritten `insert` (index-based, `vector::insert` for tails shorter than 32 entries), which HEAD's CHANGELOG does not list for this row. Cause: probably that insert rewrite; not isolated. Two more rows are below 0.97 inside their A/A spread: `<string,string>` 1024 `find` 0.961 (A/A 7.0%, an unchanged path) and `<u32,u32>` 64 `insert` 0.966 (A/A 4.5%; HEAD's CHANGELOG measured 13.9 -> 13.7 ns for the same row on the M4 Pro).

**Verdict: FASTER** on both machines (geomean 1.46 on the M4 and 1.91 on the i9) with two slower rows: the replayed `find` of a 100-entry `<i8,u64>` table on the i9 (0.76, documented trade-off) and `<string,u64>` n=32 `insert` on the M4 (0.96, unexplained).

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- i9 `<i8,u64>` n=100 `find`, keys replayed in one order, 0.758: accepted (CHANGELOG). The branch
  predictor learns start's `std::lower_bound` on a short table queried in the same order; head's
  compare is marked unpredictable, so it has no branch to learn.
- M4 `<string,u64>` n=32 `insert` 0.959: open, probably the index-based `insert`; not isolated. No
  issue filed.
