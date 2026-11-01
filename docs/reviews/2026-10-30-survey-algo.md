# Survey F: text algorithms and geo

- Date: 2026-10-30. Kind: performance survey of the text-algorithm and geo cluster (string-similarity, soundex,
  double-metaphone, snowball, htm, cartesian) against the best comparator (read-only).
- Repos: `string-similarity:ddfb8d1`, `soundex:89f9d51`, `double-metaphone:91c17a2`, `snowball:51582e3`,
  `htm:a0321ab`, `cartesian:6eab8ed` (the heads before the campaign commits).
- Machines: Apple M4 Pro. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| F-W1 Levenshtein, near word pairs | landed | `string-similarity:0a05bbd` | `string_similarity_differential` |
| F-W2 Levenshtein, 300 chars | landed | `string-similarity:0a05bbd`, `string-similarity:b987cf8` | `string_similarity_levenshtein` |
| F-W3 Levenshtein, 3000 chars | landed | `string-similarity:0a05bbd`, `string-similarity:b987cf8` | `string_similarity_levenshtein` |
| F-W4 Jaro, 300 chars | landed (after the semantics decision: standard Jaro, owner-authorized) | `string-similarity:0a05bbd`, `string-similarity:efba168`, `string-similarity:206f76b` | `string_similarity_correctness` |
| F-W5 Jaro, 3000 chars | landed (same) | `string-similarity:0a05bbd`, `string-similarity:efba168`, `string-similarity:206f76b` | `string_similarity_correctness` |
| F-W6 HTM `getId(Cartesian)` | landed | `htm:46094e9` | `htm_diff` |
| F-W7 HTM `getTrixelName(Cartesian)` | landed (through the id) | `htm:46094e9` | `htm_diff` |
| F-W8 HTM `getTrixelName(id)` | rejected: `std::bit_width` was no faster (52 vs 60 ns, the string allocation dominates), recorded in [LESSONS](../LESSONS.md#htm); `htm.cc:827` still uses `ceil(log2(id))` | - | - |
| F-M1 Levenshtein, random word pairs | landed | `string-similarity:0a05bbd` | `string_similarity_differential` |
| F-M2 Levenshtein, `icase=true` | landed (fold into a stack buffer in the kernel) | `string-similarity:0a05bbd` | `string_similarity_differential` |
| F-M3 Jaro, random word pairs | landed | `string-similarity:0a05bbd`, `string-similarity:efba168` | `string_similarity_correctness` |
| F-M4 Jaro_Winkler, word pairs (CRTP bug) | landed (bug fixed first) | `string-similarity:efba168`, `string-similarity:0a05bbd` | `string_similarity_correctness` |
| F-M5 Jaro_Winkler, `icase=true` | landed | `string-similarity:0a05bbd`, `string-similarity:efba168` | `string_similarity_correctness` |
| F-M6 Soundex English | landed | `soundex:dd429fd` | `soundex_diff` |
| F-M7 Cartesian `toLatLon` | not pursued: sqrt/atan2/Newton bound, only the datum lookup is avoidable ([LESSONS](../LESSONS.md#cartesian)); `cartesian.cc` unchanged since `6eab8ed` | - | - |
| F-M8 `hash<Cartesian>` | landed (then the equality fix of the [audit](2026-10-31-audit-algo.md), C1) | `cartesian:79ed663`, `cartesian:7066e9e` | `cartesian` (`test_hash`, `test_hash_scale`, `test_hash_domain`) |

The Double Metaphone row, rated not worth it here, was rewritten later anyway: `double-metaphone:82ee696` builds one
key per call and cleans the word in one pass (the glue, not the rule table, was the cost; see
[LESSONS](../LESSONS.md#double-metaphone)).

Bench: a survey harness (probe not kept; the rows are covered by `string-similarity:bench/bench.cc`,
`soundex:bench/bench.cc`, `double-metaphone:bench/bench.cc`, `htm:bench/bench.cc` and `cartesian:bench/bench.cc`;
clang++ -O3, C++20). Dictionary words (29.5k, 1 in 8 of /usr/share/dict/words), random and near (1-2 edit) pairs,
plus 300 and 3000 char strings over a 4 letter alphabet. Best of 5 per row, timed on the Apple M4 Pro under an
exclusive timing hold. Ratio = ours / comparator (above 1 means we are slower). A/A spread measured on the first
Levenshtein row and the soundex/HTM rows: 1.65x to 1.85x for rapidfuzz word pairs, about 2% for the others (HTM 1.84
vs 1.86, soundex 1.62 vs 1.57). Small rapidfuzz word-pair rows are noisy, about +/-10%. Not built or timed under any
sanitizer; the sources of every library were not modified.

## Identity checks (void rows are marked)

- Levenshtein (icase=false): 0 mismatches in 59k pairs against rapidfuzz normalized distance. Row valid.
- **Jaro: 6372 of 59k pairs differ from rapidfuzz (max diff 0.056).** The library matches characters in each
  direction independently (two greedy passes), not with one shared match-flag set, so it is a non-standard Jaro. Jaro
  rows below are speed-only, not identical results.
- **Jaro_Winkler is not Jaro-Winkler: it returns plain Jaro.** `StringMetric<Jaro>` is the CRTP base, so
  `similarity()` statically casts to `Jaro` and never reaches `Jaro_Winkler::_similarity`. MARTHA/MARHTA gives 0.9444
  (Jaro) and `name()` returns "Jaro". 52400 of 59k pairs differ from rapidfuzz JW. Rows are speed-only.
- Soundex English vs a table loop: 0 mismatches. HTM getId vs plain scalar: 0 mismatches in 20k points. Valid.
- Double Metaphone and Snowball: no independent comparator in the tree. Snowball is the generated reference C.

## Table

| library | workload | ours | best comparator | ratio (A/A) | diagnosis | win | effort | verdict | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| string-similarity Levenshtein | random word pairs | 134 ns | rapidfuzz 73-80 ns | 1.65-1.85x | `std::vector<size_t>` x2 allocated per call, O(nm) scalar DP with `min({...})` initializer list | 2x | low | maybe | F-M1 |
| Levenshtein | near word pairs | 148 ns | rapidfuzz 52 ns | 2.8x | same; rapidfuzz strips common prefix/suffix and uses bit-parallel Myers | 2.8x | low-med | CLEAR WIN | F-W1 |
| Levenshtein | 300 chars | 108 us | rapidfuzz 3.2 us | 33.6x | O(nm) scalar vs bit-parallel Hyyro/Myers (64 cells per word op) | 30x | med | CLEAR WIN | F-W2 |
| Levenshtein | 3000 chars | 11.2 ms | rapidfuzz 244 us | 45.8x | same, algorithmic | 45x | med | CLEAR WIN | F-W3 |
| Levenshtein | icase=true (default) | 176 ns | rapidfuzz, no fold, 84 ns | 2.1x | `strings::upper` copies both strings (allocation) on every call; the default is icase | 2x | low | maybe (part of the same fix) | F-M2 |
| Jaro | random word pairs | 169 ns | rapidfuzz 73 ns | 2.3x | two passes, `vector<bool>` + `vector<char>` allocations; result is non-standard | 2x | low | maybe | F-M3 |
| Jaro | 300 chars | 29.5 us | rapidfuzz 1.37 us | 21.5x | O(n*window) scalar match search vs bit-parallel | 20x | med | CLEAR WIN (after the semantics decision) | F-W4 |
| Jaro | 3000 chars | 3.54 ms | rapidfuzz 19.1 us | 185x | same | 180x | med | CLEAR WIN (same) | F-W5 |
| Jaro_Winkler | word pairs, random/near | 147-169 ns | rapidfuzz 62-74 ns | 2.3-2.4x | same as Jaro, plus the CRTP bug (computes Jaro only) | 2x | low | maybe; fix the bug first | F-M4 |
| Jaro_Winkler | icase=true | 184 ns | rapidfuzz 63 ns | 2.9x | upper() allocations | 2.9x | low | maybe | F-M5 |
| Soundex English | dict words | 50 ns | table loop 31 ns | 1.6x | `std::string` by value, then `erase`/`insert` shifts in place (O(n^2)), per-char switch | 1.6x | low | maybe; short words, small absolute cost | F-M6 |
| Double Metaphone | primary key, dict words | 137 ns | none (encode_both same cost) | 1.0x | `encode()` computes both keys, then discards the alternate; `Word` copy + `Keys` strings, each a heap allocation past SSO | 1.3x est. | med | not worth it | - |
| HTM | getId(Cartesian) level 25 | 900 ns | plain scalar 489 ns | 1.84-1.86x | `Cartesian` carries `SRID`+`scale` (48 B), each midpoint/cross builds a `Cartesian` through a non-inline ctor (cartesian.cc), 3 midPoints (3 sqrt) per level, 3 insideVertex tests each recomputing cross products | 1.85x | low | CLEAR WIN | F-W6 |
| HTM | getTrixelName(Cartesian) | 1.62 us | getId + name(id) 0.98 us | 1.66x | copies `std::string name` per call and push_back per level; same Cartesian overhead | 1.7x | low | CLEAR WIN (rides on getId) | F-W7 |
| HTM | getTrixelName(id) | 62 ns | bit loop 7.8 ns | 7.9x | `ceil(log2(id))` in floating point, per char mask arithmetic | 7x | trivial | CLEAR WIN (small absolute) | F-W8 |
| Cartesian | ctor lat/lon WGS84 | 17.5 ns | plain 14.8 ns | 1.18x | `unordered_map` lookup of the datum on each call, try/catch | 1.2x | low | already good | - |
| Cartesian | ctor OSGB36 | 20.3 ns | WGS84 ctor 17.7 ns | 1.15x | Helmert via one map lookup | 1.1x | n/a | already good | - |
| Cartesian | toLatLon | 122 ns | Bowring closed form 49.5 ns (not identical) | 2.5x | `unordered_map::at` and a Newton loop to 1e-15 (Lin-Wang) | up to 2x | med | maybe (changes last digits if the method changes) | F-M7 |
| Cartesian | distance | 8.8 ns | inline acos 8.6 ns | 1.02x | acos dominates | none | n/a | already good | - |
| Cartesian | hash<Cartesian> | 253 ns | hash<double> 0.6 ns (not same) | n/a | formats to a string and hashes it: `std::format` + `std::hash<string>` | 100x+ | low | maybe; changes hash values (hash is not persisted, check callers) | F-M8 |
| Cartesian | to_string | 251 ns | snprintf 271 ns | 0.93x | `std::format` | none | n/a | already good | - |
| Snowball | english/german/russian stem | 121/183/80 ns per word | libstemmer-style reference is the same generated C code | 1.0x (n/a) | thin wrapper (`string_view` in, `string_view` out, no allocation); name lookup done once at construction | none | n/a | already good | - |

## CLEAR WINs

### 1. Levenshtein (and the Jaro family) bit-parallel
- Start files: `string-similarity:levenshtein.h`, `jaro.h`, `jaro_winkler.h`, `basic_string_metric.h`.
- Biggest change: when `_subst_cost == _ins_del_cost == 1`, use Myers/Hyyro bit-vector Levenshtein (single word for
  length up to 64, blocked above), after trimming the common prefix and suffix. Weighted costs keep the existing DP,
  but with stack/reused rows rather than two `vector`s. For Jaro, a bit-parallel match search over 64-bit words.
  Implement from the Myers 1999 / Hyyro 2003 papers, not from rapidfuzz source (rapidfuzz is MIT, but write it fresh).
- Stay identical: `distance()`/`similarity()` doubles for Levenshtein (the check above shows 0 diff), the
  empty-string (1.0 / 0.0) and equal-string short circuits, `icase` folding semantics, the `_maxCost * max(len)`
  normalization. For Jaro the result is non-standard (see below); keep it bit-identical or decide with the owner first.
- Also drop the per-call `strings::upper` allocation by folding into a small stack buffer or comparing through a
  fold table.

### 2. HTM getId / getTrixelName
- Start files: `htm:htm.cc` (`getId`, `getTrixelName`, `insideVertex_Trixel`, `midPoint`), `cartesian:cartesian.h`.
- Biggest change: run the descent on plain 3-double vectors with the cross products hoisted (the edge normals
  v0^v1 etc. are shared), inline the midpoint, and make `getTrixelName(Cartesian)` build the name from the id.
- Stay identical: the id for every input (verified identical: 0 mismatches in 20k points; keep the exact `> 0`
  comparisons and the child order, since boundary points decide ties), the name format, the public signatures. Avoid
  changing the floating-point operation order for midpoint/normalize, or the tie-break on boundaries can move.
- `getTrixelName(id)`: replace `ceil(log2(id))` with `std::bit_width`; trivial.

## Notes and API-compat hazards

- **Jaro_Winkler returns Jaro** (CRTP base is `Jaro`). Fixing it changes every result; this is an observable behavior
  change for callers, so it needs an owner decision. Same for the non-standard two-pass Jaro match.
- `StringMetric::distance(T&&, T&&)` needs both arguments the same type; `string_view` lvalues work with any `icase`.
- Levenshtein constructors take `size_t` costs with a `1.0` default (silent conversion). Cost weights above 1 must keep
  working through the weighted DP.
- Soundex keeps no first-letter plain rule: it is the "refined" variant, not 4-char Soundex; any rewrite must keep
  R901096 output (the table loop reproduces it, 0 mismatches).
- `hash<Cartesian>` hashes the printed string (6 significant digits), so nearby points collide and equal hashes do not
  imply `operator==`; do not change the equality behavior when speeding it up.
- HTM `getId(Cartesian)` expects a normalized vector; the bench normalizes inputs.
- Cartesian toLatLon with different SRIDs relies on the datum map; precision depends on the 1e-15 Newton stop.

## LESSONS

The lessons of this survey are in [LESSONS](../LESSONS.md): [string-similarity](../LESSONS.md#string-similarity),
[htm](../LESSONS.md#htm), [cartesian](../LESSONS.md#cartesian), [soundex](../LESSONS.md#soundex),
[double-metaphone](../LESSONS.md#double-metaphone). One is not recorded there:

- When a library wraps a reference implementation (Snowball) and returns views with no allocation, there is nothing to
  gain; check for that before spending time.
