# char-classify: START vs HEAD (final gate, 2026-11-01)

> Part of the [gate of 2026-11-01](../gate-2026-11-01.md). Rerun the repository's own benchmark with the command in its [README](https://github.com/Kronuz/char-classify#-performance). `$GATE` below stands for the gate's working directory (rigs, scripts, micro-benches and raw outputs), which was not kept.

- START: `a890496 2026-10-28 04:27:23 -0700 Credit Germán Méndez Bravo and bound Dubalu's years`
- HEAD: `65c1ff5 2026-11-01 07:47:54 -0800 Shape the README to the family standard and drop the demo screenshot [skip ci]` (origin/main at 09:00 on 2026-11-01)
- Library under test: `chars.hh` (the START library is `chars.hh` only; HEAD adds `chars_escape.hh`, `chars_simd.hh`, the `hex_value` table)
- Bench source: bench/compare.cc, trimmed to the rows whose API exists at START (derived copy `compare_gate.cc`, the same file for both builds)
- Rows dropped because the API is new since START: the `fold`, `scan` and `kernel` groups and the `hex_value` decode row (they need `chars_simd.hh`, `chars_escape.hh` and `hex_value`, which START does not have: 100% new API)
- Metric: column `ours` (the library) against the comparator column as anchor
- Machines: Apple M4 Pro, 14 cores, macOS 26.7.2, arm64; Intel Core i9-9980HK, 8C/16T, macOS 15.8.1, x86_64. Compiler: Apple clang 17 (`c++`), `-std=gnu++20 -O3 -DNDEBUG -w`, no `-march` flags, same on both builds.
- Method: HEAD's bench built twice, A = START library sources, B = HEAD library sources, each with the dependency pins its own CMakeLists names (see the command); per round A, B, A again (the A/A control), interleaved, inside a `quiet strict` hold on the host; rounds per row set are in the table below; `tools/ab_compare.py compare` for the paired ratios, the range over rounds, the A/A deviation and the geomean. `ab_compare` calls a row slower or faster when its median ratio is outside the A/A deviation; a row is listed below when the ratio is also under 0.97.
- Build command (`w/` = the scratch worktrees; A with `start`/first pin, B with `head`/second pin):
  `c++ -std=gnu++20 -O3 -DNDEBUG -w -I w/char-classify-{start|head} w/char-classify-head/bench/compare_gate.cc`
- Raw per-round outputs: `$GATE/raw/char-classify/<host>/` (`a-NN` START, `b-NN` HEAD, `aa-NN` START again).
- Run: `./<repo>_A > a-NN.txt; ./<repo>_B > b-NN.txt; ./<repo>_A > aa-NN.txt` for NN = 01..05 (`measure.sh` / `hold.sh`, scratch only), then `ab_compare.py compare --regex ... --a a-* --b b-* --aa aa-*`.

## Summary

| machine | rows | geomean START/HEAD | per-run geomean (min-max) | A/A geomean | rows < 0.97 outside A/A | worst row |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Apple M4 Pro | 7 | 1.005 | 1.001-1.007 | 1.010 | 0 | 0.992 hex char_repr hex-encode, 65536 B nibble string lookup |
| Intel i9-9980HK | 7 | 0.999 | 0.985-1.016 | 1.002 | 0 | 0.978 classify is_hexdigit count, 64 KB arithmetic ranges |

**Verdict: SAME**; geomean 1.005 / 0.999 (Apple M4 Pro / Intel i9-9980HK).

Ratio = START time / HEAD time (above 1: HEAD is faster); median of the paired per-round ratios.

## Rows below 0.97 outside the A/A spread

- Apple M4 Pro: none.
- Intel i9-9980HK: none.

## Notes

- START's library is `chars.hh`; HEAD's `chars.hh` differs by an addition only (`NO_HEX_VALUE`, `hex_value_table`, `hex_value()`, 27 lines; `git diff a890496 65c1ff5 -- chars.hh`). `is_alpha`, `is_hexdigit`, `char_repr` and `hexdec` are the same code, so a ratio of 1.0 is expected, and is what the 7 rows show.
- Everything else the repo gained (`chars_simd.hh` block scanners and `ascii_lower`, `chars_escape.hh` escaping kernel, `hex_value`) does not exist at START: those rows (the bench's `fold`, `scan`, `kernel` groups and the `hex_value` decode) cannot be built against START and are not in this gate. Their comparators (arithmetic loops, `memchr`, `std::string_view::find_first_of`, a scalar table loop) are in HEAD's `bench/compare.cc`; the repo's own numbers for them are in its CHANGELOG, not re-measured here.
- Anchor column (the comparator in each row, same code in both builds) stays at 1.0 within its spread.

## Apple M4 Pro: per-row results (library column)

| row                                                    | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------------------------------------ | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| classify is_alpha count, 64 KB (c \| 32) - 'a' < 26     | 0.177 | 0.176 |     1.000x | 0.99-1.01 | 1.006 | 5 |   noise |
| classify is_alpha count, 64 KB std::isalpha            | 0.177 | 0.177 |     0.994x | 0.99-1.01 | 1.006 | 5 |   noise |
| classify is_hexdigit count, 64 KB arithmetic ranges    | 0.178 | 0.177 |     1.000x | 0.99-1.02 | 1.017 | 5 |   noise |
| hex char_repr hex-encode, 16 B nibble string lookup    | 0.336 | 0.326 |     1.031x | 0.97-1.05 | 1.018 | 5 |   noise |
| hex char_repr hex-encode, 256 B nibble string lookup   | 0.291 | 0.289 |     1.007x | 0.99-1.01 | 1.014 | 5 |   noise |
| hex char_repr hex-encode, 65536 B nibble string lookup | 0.256 | 0.258 |     0.992x | 0.98-1.00 | 1.004 | 5 |   noise |
| hex hexdec decode, 4096 B arithmetic nibbles           |  2.30 |  2.30 |     1.009x | 0.98-1.03 | 1.003 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.005 over 7 rows (min 0.992 hex char_repr hex-encode, 65536 B nibble string lookup; max 1.031 hex char_repr hex-encode, 16 B nibble string lookup)
per-run geomean: min 1.001, median 1.003, max 1.007 over 5 runs
A/A geomean 1.010

### Apple M4 Pro: anchor column (code that is the same in both builds; ratio should be 1)

| row                                                    | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------------------------------------ | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| classify is_alpha count, 64 KB (c \| 32) - 'a' < 26     | 0.143 | 0.143 |     1.007x | 0.99-1.01 | 1.000 | 5 |   noise |
| classify is_alpha count, 64 KB std::isalpha            | 0.427 | 0.426 |     1.007x | 1.00-1.03 | 1.022 | 5 |   noise |
| classify is_hexdigit count, 64 KB arithmetic ranges    | 0.358 | 0.356 |     1.008x | 0.98-1.02 | 1.011 | 5 |   noise |
| hex char_repr hex-encode, 16 B nibble string lookup    | 0.483 | 0.484 |     0.998x | 0.99-1.05 | 1.004 | 5 |   noise |
| hex char_repr hex-encode, 256 B nibble string lookup   | 0.344 | 0.341 |     1.003x | 0.99-1.03 | 1.000 | 5 |   noise |
| hex char_repr hex-encode, 65536 B nibble string lookup | 0.327 | 0.329 |     0.997x | 0.98-1.01 | 0.994 | 5 |   noise |
| hex hexdec decode, 4096 B arithmetic nibbles           | 0.682 | 0.682 |     1.000x | 0.98-1.02 | 1.006 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 1.003 over 7 rows (min 0.997 hex char_repr hex-encode, 65536 B nibble string lookup; max 1.008 classify is_hexdigit count, 64 KB arithmetic ranges)
per-run geomean: min 1.000, median 1.004, max 1.008 over 5 runs
A/A geomean 1.005

## Intel i9-9980HK: per-row results (library column)

| row                                                    | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------------------------------------ | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| classify is_alpha count, 64 KB (c \| 32) - 'a' < 26     | 0.267 | 0.271 |     0.996x | 0.98-1.03 | 0.978 | 5 |   noise |
| classify is_alpha count, 64 KB std::isalpha            | 0.273 | 0.269 |     1.026x | 0.99-1.04 | 1.014 | 5 |   noise |
| classify is_hexdigit count, 64 KB arithmetic ranges    | 0.273 | 0.275 |     0.978x | 0.97-1.01 | 1.008 | 5 |   noise |
| hex char_repr hex-encode, 16 B nibble string lookup    | 0.468 | 0.467 |     0.979x | 0.96-1.02 | 1.009 | 5 |   noise |
| hex char_repr hex-encode, 256 B nibble string lookup   | 0.413 | 0.409 |     0.998x | 0.98-1.03 | 1.002 | 5 |   noise |
| hex char_repr hex-encode, 65536 B nibble string lookup | 0.380 | 0.379 |     1.008x | 0.97-1.02 | 0.997 | 5 |   noise |
| hex hexdec decode, 4096 B arithmetic nibbles           |  4.26 |  4.22 |     1.011x | 0.99-1.03 | 1.009 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.999 over 7 rows (min 0.978 classify is_hexdigit count, 64 KB arithmetic ranges; max 1.026 classify is_alpha count, 64 KB std::isalpha)
per-run geomean: min 0.985, median 0.999, max 1.016 over 5 runs
A/A geomean 1.002

### Intel i9-9980HK: anchor column (code that is the same in both builds; ratio should be 1)

| row                                                    | START |  HEAD | START/HEAD |     range |   A/A | n | verdict |
| ------------------------------------------------------ | ----: | ----: | ---------: | --------: | ----: | : | ------: |
| classify is_alpha count, 64 KB (c \| 32) - 'a' < 26     | 0.206 | 0.202 |     1.000x | 0.98-1.08 | 0.995 | 5 |   noise |
| classify is_alpha count, 64 KB std::isalpha            |  1.14 |  1.16 |     0.986x | 0.91-1.16 | 0.990 | 5 |   noise |
| classify is_hexdigit count, 64 KB arithmetic ranges    | 0.558 | 0.577 |     0.950x | 0.91-1.00 | 1.009 | 5 |   noise |
| hex char_repr hex-encode, 16 B nibble string lookup    | 0.696 | 0.701 |     1.013x | 0.95-1.08 | 1.028 | 5 |   noise |
| hex char_repr hex-encode, 256 B nibble string lookup   | 0.654 | 0.637 |     1.027x | 0.96-1.05 | 0.991 | 5 |   noise |
| hex char_repr hex-encode, 65536 B nibble string lookup | 0.607 | 0.607 |     0.998x | 0.98-1.03 | 1.000 | 5 |   noise |
| hex hexdec decode, 4096 B arithmetic nibbles           |  2.19 |  2.17 |     1.003x | 0.98-1.09 | 1.013 | 5 |   noise |

runs: START 5, HEAD 5, A/A 5; a ratio above 1 means HEAD is faster
geomean 0.996 over 7 rows (min 0.950 classify is_hexdigit count, 64 KB arithmetic ranges; max 1.027 hex char_repr hex-encode, 256 B nibble string lookup)
per-run geomean: min 0.960, median 1.009, max 1.024 over 5 runs
A/A geomean 1.004
