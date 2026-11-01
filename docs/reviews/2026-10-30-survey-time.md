# Survey C: time (datetime, times, time-point, epoch)

- Date: 2026-10-30. Kind: performance survey of cluster C (time libraries), the starting point of the October 2026
  performance work.
- Repos (heads surveyed, the last commit before 2026-10-30): `datetime:fce3d4d`, `times:666dfdd`,
  `time-point:2f1f7f9`, `epoch:4f9e76a`.
- Machines: Apple M4 Pro (arm64). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| C-W1 datetime parse `YYYY-MM-DD` | landed | `datetime:5d4f2cb` | `datetime_diff` (frozen original in `test/old/`) |
| C-W2 datetime parse `...T00:00:00` | landed | `datetime:5d4f2cb` | `datetime_diff` |
| C-W3 datetime parse `...Z` | landed | `datetime:5d4f2cb` | `datetime_diff` |
| C-W4 datetime parse `.ffffffZ` | landed | `datetime:5d4f2cb` | `datetime_diff` |
| C-W5 datetime parse `...+hh:mm` | landed | `datetime:5d4f2cb` | `datetime_diff` |
| C-W6 datetime parse `.ffffff+hh:mm` | landed | `datetime:5d4f2cb` | `datetime_diff` |
| C-W7 datetime parse loose format (regex fallback) | landed | `datetime:5d4f2cb` | `datetime_diff` |
| C-W8 datetime date math `...\|\|+1d/d` | landed | `datetime:5d4f2cb` | `datetime_diff`, `datetime_datemath` |
| C-W9 datetime `isDatetime` | landed | `datetime:5d4f2cb`, `datetime:2359df3` | `datetime_diff` (both `Iso8601Parser` overloads against a reference verdict) |
| C-W10 datetime `iso8601(tm_t)` formatter | landed | `datetime:5d4f2cb` | `datetime_diff` |
| C-W11 datetime `to_tm_t(time_t)` | landed | `datetime:5d4f2cb` | `datetime_diff`, `datetime_datemath` |
| C-W12 datetime `TimeParser` | open | - | -: `datetime:datetime.cc:1312` still reads each field through `strict_stoul`; no commit or CHANGELOG entry references it |
| C-M1 datetime `timestamp(tm_t)` | landed | `datetime:773205b` | `datetime_datemath`, `datetime_diff` |
| C-M2 datetime `timegm(std::tm)` | landed | `datetime:773205b` | `datetime_datemath`, `datetime_diff` |
| C-M3 datetime `time_to_string(double)` | not pursued | - | -: `datetime:datetime.cc:1500` is still the `std::format` chain; no commit or CHANGELOG entry references it |

The datetime history, with the before and after numbers of each change, is in `datetime:CHANGELOG.md` (2026-10-30 and
2026-10-31). `5d4f2cb` kept results identical for every input; the fixes that followed (`fe618d8`, `03f36fa`, `773205b`)
changed the listed input classes on purpose. Not on `main` yet: the external comparator rows (hand ISO parser,
abseil, `strptime`+`timegm`) as `datetime:bench/compare.cc`; `datetime:bench/bench.cc` times the library against its
frozen original only.

Bench: a cluster harness (prototype not kept; the old-against-new rows are in `datetime:bench/bench.cc`), clang++ -O2,
C++20, arm64, brew abseil 20260817. 4096 random inputs per row, best of 7 (3 for slow rows), under an exclusive timing
hold. A/A = the same lib closure run twice (spread 0-7%).
Comparators: hand ISO parser/formatter and days_from_civil/civil_from_days written from the public algorithm
description (not copied), abseil `ParseTime/FormatTime/FromCivil`, `strptime+timegm`, `gmtime_r`, `clock_gettime`.
Every "identical=yes" row compared the full result (parsed seconds incl. fsec and TZ offset, or full string).

| library | workload | ours | best comparator | ratio (A/A) | diagnosis | est. win | effort | verdict | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| datetime | parse `YYYY-MM-DD` | 49.4 ns | hand ISO 5.9 ns | 8.4x (2%) | each field via `strict_stoul(substr)` (errno save, strtoul-style generality) for 2-4 digits | 8x | S | CLEAR WIN | C-W1 |
| datetime | parse `…T00:00:00` | 94 ns | hand 7.4 ns; absl 87 ns | 12.7x (1%) | same; abseil is no better | 12x | S | CLEAR WIN | C-W2 |
| datetime | parse `…Z` | 89 ns | hand 7.4 ns | 12.0x (7%) | same | 12x | S | CLEAR WIN | C-W3 |
| datetime | parse `.ffffffZ` | 116 ns | hand 10.0 ns | 11.6x (0%) | fraction via `strict_stod` + `normalize_fsec` (double round) | 11x | S | CLEAR WIN | C-W4 |
| datetime | parse `…+hh:mm` | 239 ns | hand 9.1 ns | 26x (5%) | `computeTimeZone` builds two std::strings and runs `computeDateMath` twice (strict_stoi, normalizeMonths, toordinal round trip) to add an offset | 25x | S | CLEAR WIN | C-W5 |
| datetime | parse `.ffffff+hh:mm` | 276 ns | hand 11.9 ns | 23x (0%) | same | 23x | S | CLEAR WIN | C-W6 |
| datetime | parse `2020/01/02 03:04:05` (non-fast format, regex) | 1390 ns | hand 9.7 ns; strptime+timegm 2112 ns | 144x (2%) | falls to `std::regex_match` (backtracking, `\2` backreference), then `m.str()` string temporaries and strict_stoi/stod on each | 100x+ | M | CLEAR WIN | C-W7 |
| datetime | parse `…\|\|+1d/d` (date math) | 764 ns | no equal comparator (strptime ignores math) | n/a | `processDateMath` uses `std::regex_search` iteration (date_math_re) | est. 10x+ | M | CLEAR WIN (same fix family; not measured against a comparator) | C-W8 |
| datetime | `isDatetime` (.ffffffZ) | 93 ns | hand 10.3 ns | 9x | calls Iso8601Parser; regex only on INVALID (so invalid-but-regex-valid inputs cost ~1.3 us) | 9x | S | CLEAR WIN (falls out of the parser fix) | C-W9 |
| datetime | `iso8601(tm_t)` trimmed, mixed fsec, UTC | 267 ns | hand formatter 8.9 ns | 30x (1.5%) | 3-5 `std::format` calls, `format("{:.6f}")` + erase(0,1) + trailing-zero strip, string reallocs | 25-30x | S | CLEAR WIN | C-W10 |
| datetime | `iso8601` vs absl FormatTime | 267 ns | absl 1100 ns | 0.24x | abseil slower (cctz); void identity (different offset style) | - | - | already beats absl | - |
| datetime | `to_tm_t(time_t)` | 34.4 ns | civil_from_days 5.7 ns | 6.0x (1%) | `gmtime_r` (tz-aware libc, locks tz state) for a pure UTC conversion | 6x | S | CLEAR WIN | C-W11 |
| datetime | `timestamp(tm_t)` | 4.2 ns | days_from_civil 1.8 ns | 2.4x (2%) | `toordinal` throws-checking (getDays_month), cumdays table, normalizeMonths | 2x (ns level) | S | maybe (tiny absolute) | C-M1 |
| datetime | `timegm(std::tm)` | 5.0 ns | days_from_civil 1.8 ns | 2.8x | same | 2.8x | S | maybe | C-M2 |
| datetime | `timestamp(tm_t)` vs absl FromCivil | 4.2 ns | absl 26.9 ns | 0.16x | n/a | - | - | already good | - |
| datetime | `TimeParser` hh:mm:ss.f+hh:mm + to_double | 86 ns | not benched separately | est. ~8x | same strict_stoul/strict_stod pattern as the date parser | est. 8x | S | CLEAR WIN (same fix) | C-W12 |
| datetime | `time_to_string(double)` | 145 ns | not benched separately | est. ~15x | std::format chain | est. 10x | S | maybe (same fix family as iso8601) | C-M3 |
| epoch | `now<ns>()` | 14.4 ns | raw clock_gettime 12.9 ns | 1.1x | one clock call; duration_cast is free | none | - | already good | - |
| time-point | `time_point_to_ullong(now)` | 12.8 ns | clock_gettime 12.9 | 1.0x | pure cast | none | - | already good | - |
| times | `now()` (timespec_t) | 12.0 ns | clock_gettime 12.9 | 0.9x | thin | none | - | already good | - |
| times | `timespec_t +=/-=` pair | 0.93 ns | int64 ns 0.40 ns | 2.3x | `_adjust()` while loops and `1e9L` (long double; on x86 an x87 op, on arm64 the same as double) | <1 ns | S | not worth it | - |

## CLEAR WINS

### 1. datetime parse path (Iso8601Parser / process_date_datetime / TimeParser)
- Start files: `datetime:datetime.cc` lines 57-345 (parsers), 530-555 (`computeTimeZone`), `isDatetime` ~1041.
- Biggest change: replace per-field `strict_stoul(substr)` with a fixed-width two/four-digit reader
  (`(c-'0')` with range check) and parse fractions as integer digits scaled to microseconds (keep the >6-digit
  rounding rule of `normalize_fsec`); apply the TZ offset as arithmetic on a seconds count (or directly into
  tm_t with one day-carry pass) instead of two `computeDateMath` string round trips. Measured prototype of the
  fixed-shape path: 6-12 ns for every shape.
- Second change: give the "other formats" fallback (`date_re`: `/`, space, `-`-less, 1-digit hours,
  separator-optional) a hand scanner that implements the same grammar (the regex is small and regular; `\2` just
  means "same separator twice"), and a hand scanner for the `||` date-math grammar `([+-]\d+|/{1,2})([dyMwhms])`.
  Keep `date_re`/`date_math_re` as exported symbols (they are public `extern const std::regex`) so ABI/API stays.
- Must stay identical: result tm_t fields incl. `is_utc` (set by Z and by +/-offset), `fsec` rounding via
  `normalize_fsec` (clamp 0.999999, round to microsecond), Format::{VALID,INVALID,OUT_OF_RANGE,ERROR} return
  codes per input class, exception messages (`Error format in _datetime`, `is out of range`), the quirks
  (size-19 path leaves `is_utc` untouched; offset arithmetic goes through date math, so day/month/year borrow
  exactly like computeDateMath). Differential-fuzz old vs new on strings including invalid ones.
- Note the bench proved identity of the hand parser only on valid in-range inputs, 1971-2099, days 1-28,
  fractions <= 6 digits; invalid/edge inputs need the fuzz above.

### 2. iso8601 / time_to_string / timedelta_to_string formatters
- Start: `datetime.cc` lines 933-1010, 1246-1290, 1455-1490.
- Change: write digits straight into a stack buffer (2-digit LUT or `/10`, `%10`), micros as integer
  digits with trailing-zero trim, one `std::string` construct. Measured 8.9 ns vs 267 ns.
- Must stay identical: the trim and non-trim modes, `sep`, `Z` suffix placement relative to the fraction,
  `{:04}` year padding behaviour for years > 9999 or < 1 (std::format widens; the hand writer must too),
  fsec printed as `{:.6f}` (round-half-even on the binary double; use the same rounding to micro as
  `llround(fsec*1e6)`; check ties on the full 0..999999 range, the bench did 2048 random values: identical).

### 3. to_tm_t(time_t / double)
- Start: `datetime.cc` 855-890. Replace `gmtime_r` with civil_from_days (5.7 ns vs 34 ns, identical on
  random 1970-2100). Also removes the dependency on libc tz state. Keep floor semantics for negative inputs
  (gmtime_r floors; `/` and `%` truncate, so do Euclidean division) and the `to_tm_t(double)` fsec rule
  (`timestamp - (time_t)timestamp`, truncation toward zero as today).

## Other notes
- Small, absolute-cost items: `toordinal`/`timegm`/`timestamp` are 2-3x off days_from_civil but only 2-3 ns;
  worth doing only as a by-product of using days_from_civil inside the new parser. Keep `toordinal` (python-style
  ordinal, year >= 1, throws) as is for API.
- epoch, time-point and times are thin wrappers over the OS clock; nothing to win.

## API-compat hazards
- `Datetime::date_re` and `date_math_re` are `extern const std::regex` in the public header: removing them is an
  ABI/API break. Keep them (unused internally) or leave a note.
- `time_point_from_ullong<system_clock>` does not compile on libc++/macOS (system_clock is microsecond-resolution,
  the nanosecond duration does not convert implicitly), contrary to the README's "any standard clock". Works for
  `steady_clock` (default). Also `time_point_to_ullong` only deduces `time_point<Clock, default duration>`.
  (A fix, `duration_cast`, is trivial; behaviour change none on Linux.)
- `computeTimeZone` is a public function, called by the parsers; its string_view signature must stay.
- The Iso8601Parser overloaded versions (with and without `tm_t&`) have a second copy of the logic (line ~348);
  both must be changed together (or the second made to delegate).
- `timespec_t` uses `long double 1e9L` constants: on x86-64 Linux that forces x87; not measured here (arm64 host).

## LESSONS

The lessons of this cluster are in [LESSONS.md](../LESSONS.md#datetime). One is recorded only here:

- Three-line wrappers over the OS clock (epoch, time-point, times) are already at the floor: no win there; do not
  spend effort on them.
