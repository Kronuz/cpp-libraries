# stringified: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). The repository's README has no benchmark command; the gate timed a micro-bench written for it, not kept. `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `c8c9033 2026-10-28 04:53:07 -0700 Credit Germán Méndez Bravo and bound Dubalu's years`
- HEAD: `dea1ceb 2026-11-01 03:55:09 -0800 Shape the README to the family standard; drop the diagram the pitch already says [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `stringified.hh`
- Bench source: none ships; a 12-row micro-bench written for the gate (`stringified_bench.cc`, scratch only) that uses only the API both revisions have
- Rows dropped because the API is new since START: n/a
- Metric: ns per call, best of 7 samples of at least 8 ms
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -I w/stringified-{start|head} stringified_bench.cc`
- Raw per-round outputs: `$GATE/raw/stringified/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 11 | 0.797 | 0.786-0.811 | 0.995 | 4 | 0.051 string_view of a std::string: ctor + c_str * |
| Intel i9-9980HK | 11 | 0.849 | 0.830-0.861 | 0.992 | 4 | 0.035 string_view of a std::string: ctor + c_str * |

**Verdict: SLOWER-ROWS (4 on the Apple M4 Pro, 4 on the Intel i9-9980HK)**; geomean 0.797 / 0.849 (Apple M4 Pro / Intel i9-9980HK).

Geomean without the rows that are not comparable or are algorithmic changes (`\*`): Apple M4 Pro 1.054; Intel i9-9980HK 1.197. Rows marked `*` change behaviour at HEAD (START aliased or shared storage where HEAD copies) and are not comparable.

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: 4
  - `string_view of a std::string: ctor + c_str *`: 0.051 (round range 0.05-0.05, A/A deviation 0.041). not comparable (correctness change): START's `c_str()` returned the view's own pointer when the byte after the view was NUL, so a `string_view` of a `std::string` aliased it (and a view of a non-terminated buffer read one byte past its end); HEAD copies a bare `string_view` once to terminate it. CHANGELOG 2026-10-31: 'Keep the view on the object's own storage; never read past a view'.
  - `owned 200B: move-assign x2`: 0.337 (round range 0.33-0.35, A/A deviation 0.019). the move assignment now tests `o.owns()`, rebinds the view on this object's string, clears the source and rebinds it (CHANGELOG 2026-10-31); START moved the string and the view without rebinding, which was wrong for short (SSO) strings, where the view dangles into the moved-from object. The row uses a 200 B (heap) string, where START's shortcut happened to be valid: about 1 ns per assignment.
  - `string_view-backed: move ctor`: 0.611 (round range 0.58-0.61, A/A deviation 0.048). the move constructor now tests `owns()` and carries the `_terminated` flag (CHANGELOG 2026-10-31: copies and moves always leave the view on the new object's own storage); about 0.14 ns, one compare and one byte.
  - `string&& 10B: copy of source + ctor + c_str`: 0.825 (round range 0.81-0.83, A/A deviation 0.012). correctness fix that costs a rebind: START's rvalue constructor copied the string (`_str(str)`) and aimed the view at the copy; HEAD moves it and calls `bind_own()`. For a 10-byte (SSO) string the copy is cheaper than the move plus rebind: 0.3 to 0.4 ns. The 200 B row is the opposite (2.1x faster: no heap copy).
- Intel i9-9980HK: 4
  - `string_view of a std::string: ctor + c_str *`: 0.035 (round range 0.03-0.04, A/A deviation 0.110). not comparable (correctness change): START's `c_str()` returned the view's own pointer when the byte after the view was NUL, so a `string_view` of a `std::string` aliased it (and a view of a non-terminated buffer read one byte past its end); HEAD copies a bare `string_view` once to terminate it. CHANGELOG 2026-10-31: 'Keep the view on the object's own storage; never read past a view'.
  - `owned 200B: move-assign x2`: 0.663 (round range 0.63-0.68, A/A deviation 0.123). the move assignment now tests `o.owns()`, rebinds the view on this object's string, clears the source and rebinds it (CHANGELOG 2026-10-31); START moved the string and the view without rebinding, which was wrong for short (SSO) strings, where the view dangles into the moved-from object. The row uses a 200 B (heap) string, where START's shortcut happened to be valid: about 1 ns per assignment.
  - `string&& 10B: copy of source + ctor + c_str`: 0.901 (round range 0.86-0.92, A/A deviation 0.075). correctness fix that costs a rebind: START's rvalue constructor copied the string (`_str(str)`) and aimed the view at the copy; HEAD moves it and calls `bind_own()`. For a 10-byte (SSO) string the copy is cheaper than the move plus rebind: 0.3 to 0.4 ns. The 200 B row is the opposite (2.1x faster: no heap copy).
  - `owned 200B: copy ctor *`: 0.933 (round range 0.89-0.97, A/A deviation 0.043). not comparable (correctness fix): START's copy constructor copied only the view, so a copy of an owning object pointed into the source; HEAD copies the string.

## Notes

- No benchmark ships with the repo. The hot entry points are the constructors from `const std::string&`, `std::string&&` and `std::string_view`, and `c_str()`; the gate uses a 12-row micro-bench (`stringified_bench.cc` in the scratch directory `$GATE`) that uses only the API both revisions have (`stringified(const char*)` is ambiguous at START and is not used).
- Correctness changes that make rows not comparable (marked `*` in the row names): START's `c_str()` read the byte after the view and returned the view's own pointer when it was a NUL (so a `string_view` of a larger non-terminated buffer could come back unterminated, and one of a `std::string` aliased it); HEAD tracks termination in a flag and copies a bare `string_view` once. START's copy constructor copied only the view, so a copy of an owning object pointed into the source; HEAD copies the string (a fixed bug that now does more work). START's rvalue-`std::string` constructor copied (`_str(str)` of a named reference); HEAD moves it, which is a speed gain, not a trade-off.
- The object is one `bool` larger at HEAD (`_terminated`), and the move constructor and assignments test `owns()`; the sub-nanosecond rows (`string_view`-backed move constructor, 10-byte rvalue) show that as 0.15 to 0.4 ns.

A first version of the micro-bench (its owned-string rows built the object inside the timed loop) ran earlier in the hold that measured the other repos; it is superseded by the rows above. Its i9 raw files are in `$GATE/raw/stringified-v1/i9/`; the conclusions agree (the rvalue-string constructor 1.9x to 2.1x faster for 200 B, the `const std::string&` constructor 2.1x to 2.5x faster, `c_str()` of a view of a `std::string` now copies, the 10-byte rvalue constructor 0.83x on the M4).

## Apple M4 Pro: per-row results (library column)

| row                                          | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| const string& 200B: ctor + c_str             | 0.770 | 0.360 |     2.111x | 2.11-2.33 | 0.987 | 5 |  faster |
| const string& 10B: ctor + c_str              | 0.770 | 0.360 |     2.139x | 2.08-2.33 | 0.987 | 5 |  faster |
| string&& 200B: copy of source + ctor + c_str |  32.5 |  15.3 |     2.150x | 2.08-2.23 | 1.016 | 5 |  faster |
| string&& 10B: copy of source + ctor + c_str  |  1.59 |  1.93 |     0.825x | 0.81-0.83 | 0.994 | 5 |  slower |
| string_view mid-buffer 100B: ctor + c_str    |  13.9 |  14.3 |     0.970x | 0.96-1.01 | 0.989 | 5 |   noise |
| string_view of a std::string: ctor + c_str * | 0.750 |  14.9 |     0.051x | 0.05-0.05 | 1.014 | 5 |  slower |
| string_view: ctor + size + data              | 0.360 | 0.360 |     1.000x | 0.97-1.03 | 0.973 | 5 |   noise |
| string_view-backed: copy ctor                | 0.220 | 0.220 |     1.000x | 0.95-1.00 | 1.000 | 5 |   noise |
| string_view-backed: move ctor                | 0.220 | 0.360 |     0.611x | 0.58-0.61 | 1.000 | 5 |  slower |
| owned 200B: move-assign x2                   |  1.09 |  3.24 |     0.337x | 0.33-0.35 | 1.000 | 5 |  slower |
| owned 200B: copy ctor *                      |  30.0 |  29.5 |     1.019x | 0.96-1.05 | 0.981 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.797 over 11 rows (min 0.051 string_view of a std::string: ctor + c_str *; max 2.150 string&& 200B: copy of source + ctor + c_str)
per-run geomean: min 0.786, median 0.797, max 0.811 over 5 runs
A/A geomean 0.995

## Intel i9-9980HK: per-row results (library column)

| row                                          | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| -------------------------------------------- | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| const string& 200B: ctor + c_str             |  2.61 |  1.25 |     2.103x | 2.06-2.12 | 1.000 | 5 |  faster |
| const string& 10B: ctor + c_str              |  1.83 | 0.880 |     2.092x | 1.97-2.14 | 1.000 | 5 |  faster |
| string&& 200B: copy of source + ctor + c_str |  95.1 |  50.1 |     1.915x | 1.74-1.93 | 1.011 | 5 |  faster |
| string&& 10B: copy of source + ctor + c_str  |  2.74 |  3.04 |     0.901x | 0.86-0.92 | 1.004 | 5 |  slower |
| string_view mid-buffer 100B: ctor + c_str    |  50.5 |  49.7 |     1.014x | 0.98-1.06 | 1.009 | 5 |   noise |
| string_view of a std::string: ctor + c_str * |  1.78 |  50.8 |     0.035x | 0.03-0.04 | 0.957 | 5 |  slower |
| string_view: ctor + size + data              | 0.800 | 0.810 |     0.988x | 0.96-1.01 | 0.988 | 5 |   noise |
| string_view-backed: copy ctor                | 0.580 | 0.570 |     1.000x | 0.97-1.02 | 0.966 | 5 |   noise |
| string_view-backed: move ctor                | 0.580 | 0.580 |     1.000x | 0.98-1.04 | 1.000 | 5 |   noise |
| owned 200B: move-assign x2                   |  2.96 |  4.46 |     0.663x | 0.63-0.68 | 0.993 | 5 |  slower |
| owned 200B: copy ctor *                      |  95.6 | 101.5 |     0.933x | 0.89-0.97 | 0.987 | 5 |  slower |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.849 over 11 rows (min 0.035 string_view of a std::string: ctor + c_str *; max 2.103 const string& 200B: ctor + c_str)
per-run geomean: min 0.830, median 0.850, max 0.861 over 5 runs
A/A geomean 0.992

## Status since the gate

Checked against the default branch on GitHub on 2026-11-01 at 16:40 PST; the [summary](../gate-2026-11-01.md#slower-rows) uses the same words.

- Construction from a `std::string_view` plus `c_str()` (M4 0.051, i9 0.035) and the i9 copy of
  an owned 200-byte string (0.933): not comparable. Start's `c_str()` aliased the view, and its copy
  kept a view of the source.
- Move assignment of an owned 200-byte string, twice (M4 0.337, i9 0.663), move construction from
  a view (M4 0.611), and construction from a `std::string&&` of 10 bytes (M4 0.825, i9 0.901):
  accepted. Moves test whether the source owns its text and rebind, where start's shortcut
  dangled for small strings: 0.14 to 1 ns a call.
