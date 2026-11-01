# The uinteger_t and base-x campaign

- Date: 2026-10-30 to 2026-11-01. Kind: record of the performance and correctness campaign on uinteger_t
  and base-x, run apart from the catalog's [October 2026 work](2026-10-31-system.md) and measured outside it.
- Repos: `uinteger_t:85316dd..681185e` (146 commits) and `base-x:54a9326..124424e` (54 commits), both on
  `master`. Start is the last commit before 2026-10-30; head is the last commit of the campaign. Two README
  edits followed on 2026-11-01 (`uinteger_t:a383e37`, `base-x:dce0547`).
- Machines: Apple M4 Pro (development, the research, the early timings), Apple M1 Pro and Intel Core
  i9-9980HK (the final tables and the later A/B runs), the shared Linux x86-64 VM (ASan, x86 correctness),
  GitHub Actions runners (CI). Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

The blocking findings of the 19 reviews. Every other condition was closed when its branch landed; the
follow-ups still open are under "Open" at the end.

| finding | status | repo:sha | test |
|---|---|---|---|
| digits SR1: the size arithmetic of `digits()` and `from_digits()` wraps a 32-bit `size_t` (a 512 MiB input writes past the buffer) | closed | `uinteger_t:819daa4`, `uinteger_t:bcd908b` | `uinteger_t_property` (the guards at narrow size types) |
| digits SR5: base-x sums its checksum in an `int`, which overflows at about 34 million characters | closed | `base-x:10a5f0b` | - (64-bit sums; no test reaches a sum past 2^31) |
| radix-tree SR1: the conversion tree's bit count wraps a 32-bit `size_t` (silently wrong digits) | closed | `uinteger_t:b012716`, `uinteger_t:9f826fc` | `uinteger_t_radix_tree` (a 16-bit size type) |
| sbo CR1: a failed allocation of the carry limb in `x += y` or `++x` leaves `x` invalid | closed | `uinteger_t:dabd824`, `uinteger_t:b94a1f5` | `uinteger_t_alloc` (fails each allocation of every growing operation) |
| bx-semantics SR1: the RFC 4648 digit count wraps a 32-bit `size_t` | closed | `base-x:b468653` | `base_x` (`block_digits` at 16- and 32-bit sizes) |
| divq CR1: the quotient-length guard is dead at 16-bit limbs (`~digit(0)` promotes to `int` -1) | closed | `uinteger_t:392c7f8` | `uinteger_t_divq_kernel16`, `uinteger_t_divq_kernel_guard` |
| newton CR1: a rebase dropped the Debug test arguments of 39 targets | closed | `uinteger_t:b51b099` | - (`ctest -N -V` per test name against master) |
| system A1: the base-256 parse leaves a zero top limb, so `==`, `<` and `bits()` are wrong and a division by a parsed zero divides by a zero limb | closed | `uinteger_t:eb588dc` | `uinteger_t_property` (0 to 17 leading zero bytes) |

The SR5 fix has no test because a sum past 2^31 takes about 40 million characters; base-x's
[OPEN-WORK.md](https://github.com/Kronuz/base-x/blob/master/docs/OPEN-WORK.md) lists it. The newton CR1
check compares the CTest command lines. A `rechecker` pass closed the digits findings; the lead reran
the sbo reviewer's failure probe on the fix: 0 invalid operands and 0 leaks over 205,000 runs at 8
inline limbs and 33,000 at 1.

## Verdict

**Done.** Both libraries are on `master` with CI green on every job, the README tables are measured on
two machines, and the open work is written down in each repository. uinteger_t takes 1.2 to 2.3 times
GMP 6.3.0's time on most operations and prints decimal faster than GMP up to 4,096 bits (GMP is faster
from 16,384 bits); base-x encodes
a 32-byte base58 key in 74 ns and decodes it in 72 on an Apple M1 Pro. Xapiand's `xapiand` branch pins
both heads (`Xapiand:c9c6fa77`); its `master` still pins the commits from before the campaign.

## Scope and method

The owner's goal: make both libraries as fast as they can be, uinteger_t's generic arithmetic
included, keep the benchmarks, and match or beat the comparable libraries (GMP and Boost.Multiprecision
for uinteger_t, the usual base58 codecs for base-x). A tier or mechanism that is measurably faster
stays (10% counts without argument); one whose gain is within about 3%, near the A/A spread, goes. The
code comes from the papers and first principles: uinteger_t is MIT, and no GMP (LGPL) source was copied.

- **One developer per branch.** Each workstream had its own branch, worktree, ledger and done criteria
  (the change, its tests and mutants, the measured gain, the comparator rows, the docs). Explorers took
  narrow questions (why multiplication is 1.6x GMP per limb product, why addition is 2x) on their own
  branches and handed a verified change to the lead.
- **Independent reviews.** A reviewer from a fresh context read each branch before it landed: a code
  review for the kernels, a security review wherever untrusted text reaches a decoder or a size
  computation, and an architect's review of the whole design halfway through. A REJECT went back to the
  developer; a rechecker or the lead confirmed each fix against the reviewer's own probe.
- **Oracles.** GMP through a differential fuzz (`uinteger_t:test/fuzz_gmp.cc`, conversions up to 64K
  limbs, not in CTest), byte identity against the original headers (105,000 conversions in bases 2 to 36
  and 5,200 base-x encodes), Python's `int` and an independent Python model of base-x's alphabet rules for
  the bug hunts, Python's `base64` module for the RFC 4648 presets, an independent base-4 model of the
  quotient-only division (`uinteger_t:test/divq_model.cc`), a naive DFT for the transform, and all 2^31
  normalized divisors at 16-bit limbs for the reciprocals (`uinteger_t:test/recip16.cc`).
- **Timing.** An A/A run first, then A/B interleaved against `master` on a quiet machine under an
  exclusive hold, at the sizes users hit (base-x's 32- and 64-byte keys). The final tables take the best
  of two runs per machine for uinteger_t and of seven rounds for base-x, with the raw output committed
  under each repository's `bench/results/`.
- **Sanitizers and mutants.** UBSan and libc++ hardening on the Apple M4 Pro (ASan and TSan do not run
  there), ASan on the Linux VM and in CI, TSan in CI. Each review ran its own mutants; the mutants that
  mattered became `tools/mutate.py` sets in both repositories: 353 in uinteger_t (336 killed, 17 argued
  equivalent) and 48 in base-x (47 killed, 1 equivalent).

## The reviews

| review | subject | kind | verdict | key findings |
|---|---|---|---|---|
| kernels-code | raw limb kernels, `uinteger_t:5bb58c1` | code | APPROVE WITH CONDITIONS | 30 mutants, 24 killed; two survivors were test gaps (an odd-split product into a dirty buffer, a reciprocal branch of probability 3e-7); pre-existing wrong products without `__int128` and on MSVC (fixed `a39ede0`) |
| digits-security | the digit API, `uinteger_t:0a131e1`, `base-x:e097576` | security and code | **REJECT** | SR1 and SR5 above; the conversion itself 0 wrong in 10.5 million checks |
| divdc-code | recursive division, `e1e1626` | code | APPROVE WITH CONDITIONS | two doc fixes; nothing pins the balance of the split |
| toom-code | Toom-3 and squaring, `a183149` | code | APPROVE WITH CONDITIONS | docs; 890,000 raw-kernel cases against GMP, 0 wrong; no test pins that `a * a` takes the squaring kernel |
| kernel-security | division-free kernels, `uinteger_t:a1d5b48`, `base-x:2c21ec4` | security and code | APPROVE WITH CONDITIONS | no CTest target for unroll 0 and 8; the tables are never freed; TSan evidence only from CI |
| repr-code | the representation, `8bafde5` | code | APPROVE WITH CONDITIONS | a shift count past one limb read as huge at narrow limbs; unpinned early exits |
| sbo-code | inline buffer, `fac478f` | code | **REJECT** | CR1 above; 850,000 operation runs against GMP, 0 wrong |
| ntt-code | the transform, `bf26b36` | code | APPROVE WITH CONDITIONS | CTest cost; a weakened scratch check; a stale diagram |
| radix-tree-security | the conversion tree, `6a9fc0b` | security and code | **REJECT** | SR1 above, the defect class of digits SR1 on a new path; 1.9 million checks, 0 wrong |
| hunt-bx-security | base-x decode, `is_valid` and encode fixes, `1c9ff93` | security | APPROVE WITH CONDITIONS | text after the padding decoded but failed `is_valid` (pre-existing; `decode` rejects it since `d3d9f23`) |
| system-2026-10-31 | the whole design, `uinteger_t:c0d67fc`, `base-x:979180c` | architect | SOUND WITH CONDITIONS | A1 above; duplicate and dead mechanisms; cutoffs tuned one workstream at a time; memory and compile cost undocumented; `compare` documented as public but private; a slow sanitizer job |
| codec-security | base-x codec, `base-x:dd2124e`, and the byte path, `uinteger_t:e0160ad` | security | APPROVE | no finding; the fuzz target cannot see a one-byte over-read |
| cleanup-divbase-code | system-review cleanup, `89457a1`, and the division basecase, `10e4f54` | code | APPROVE WITH CONDITIONS (both) | docs; the explorer's harnesses kept out of the repository; stack bounds restated |
| newton-code | Newton division, `5630a78` | code | APPROVE WITH CONDITIONS | CR1 above; the numeric argument holds from the code |
| toom4-code | Toom-4, `dad60e2` | code | APPROVE WITH CONDITIONS | four stale comments; the 400-limb cutoff does not pay on the M1 Pro |
| bx-semantics-security | RFC 4648 byte-exact presets, stricter decode, `base-x:735f430` | security | APPROVE WITH CONDITIONS | SR1 above, the same defect class a third time; every non-RFC preset byte-identical |
| divq-code | quotient-only division, `32c1c57` | code | APPROVE WITH CONDITIONS | CR1 above; CR2: the 16-bit test cannot fail on a dead guard (random dividends never flag) |
| divq-repair | the repair, the cutoff, the rebase, `c9bd611` | code | APPROVE WITH CONDITIONS | 2.67 billion exhaustive and 165 million adversarial model cases, 26.3 million GMP-checked, 0 wrong; no hook forces the redo branch |
| bx-lz-code | base-x `leading_zeros`, `3cb9ecc` | code | APPROVE WITH CONDITIONS | docs that did not match the code; 13 of Bitcoin Core's 21 vectors pinned |

Three of the 19 rejected, each on a small local fix. The REJECTs and the blocking conditions found two
classes again and again: size arithmetic that wraps a 32-bit `size_t` (three times, on three new paths),
and a failure path that no test reached (a half-written sum after a failed allocation, a guard that never
fires). Each review's probes lived in the campaign's working folder, which is not kept; the probes that
mattered are tests now (the table above).

## Results

uinteger_t at `ac3388f` (every conversion change in, before the eight-limb addition and the
quotient-only division) against the original header (`85316dd`), Apple M1 Pro, Apple clang 21, `-O2`,
`bench/bench.cc`, best of two runs, 2 to 4,096 limbs:

| operation | speedup |
|---|---|
| `a.str(10)` | 43x (2 limbs) to 530x (4,096) |
| `uinteger_t(s, 10)` | 57x to 121x |
| `a.str(16)` | 1.9x to 2.6x |
| `a * b` | 1.8x to 8.0x |
| `a / b`, b half of a | 1.3x to 24.5x |
| `a + b` | 1.1x to 7.8x |

Against GMP 6.3.0 and Boost.Multiprecision 1.92's `cpp_int` (Apple M1 Pro; the README's table at
`6ba8ffa`, its division rows at `afdded1`): uinteger_t takes 1.2 to 2.3 times GMP's time on most rows,
prints decimal faster than GMP up to 4,096 bits (2.83 against 4.05 us at 4,096; GMP is faster from 16,384
bits, 291 against 207 us at 65,536; nothing between was measured), and takes 3.4 times
GMP's time for a new 4,096-bit sum, where allocating the result costs more than the addition. Boost takes
2 to 4 times uinteger_t's time at 256 bits and 3 (sums) to 118 (decimal printing) times at a million bits,
but parses decimal faster up to 4,096 bits (uinteger_t is faster from 16,384). The Intel Core i9-9980HK (Apple clang 17) shows the same
pattern.

base-x, base58 in ns per call (Apple M1 Pro, Apple clang 21; Intel Core i9-9980HK, Apple clang 17; best
of seven rounds of `bench/bench.cc`; Firedancer on its portable path):

| bytes | operation | base-x M1 Pro | Firedancer M1 Pro | libbase58 M1 Pro | base-x i9 | Firedancer i9 |
|---:|---|---:|---:|---:|---:|---:|
| 32 | encode | 74.3 | 48.5 | 2,086 | 143.5 | 69.6 |
| 32 | decode | 71.6 | 63.3 | 496 | 186.7 | 88.5 |
| 64 | encode | 134 | 112 | 9,300 | 258.5 | 154.1 |
| 64 | decode | 98.2 | 198 | 1,749 | 277.2 | 287.1 |

base-x returns a new `std::string`; into a string that keeps its capacity it takes 52.0 and 51.6 ns at
32 bytes on the M1 Pro. Firedancer's AVX2 path on the i9 does not change the picture (74.8 ns to encode
32 bytes).

The workstreams, with the number each landed on:

| workstream | landed | number (machine) |
|---|---|---|
| chunked conversion: a limb of digits per pass on raw limbs | `uinteger_t:aeeeb67`, `base-x:8572a00` | decimal `str()` 15-39x, parsing 76x at 4 to 1,024 limbs; base58 32-byte encode 10x (M4 Pro) |
| raw limb kernels: two-row basecase, Karatsuba, Algorithm D with a 3-by-2 estimate | `uinteger_t:5bb58c1`, `a39ede0` | multiplication at 1,024 limbs 383 to 127 us (M4 Pro) |
| the digit API, `digits()` and `from_digits()`; base-x on it | `uinteger_t:bd7bab1`, `base-x:8935fe6` | hex parse at 1,024 limbs 5.0 ms to 32 us; base64 decode of 2 KiB 500 to 7.6 us (M4 Pro) |
| recursive division (Burnikel-Ziegler) | `uinteger_t:441a250` | 1,024 by 513 limbs 162 to 75 us, GMP 39 (M4 Pro) |
| Toom-3 and squaring kernels | `uinteger_t:2b2199e` | multiplication at 1,024 limbs 125 to 106 us, GMP 57; squaring 125 to 74, GMP 45 (M4 Pro) |
| conversion tree above 8,192 bits | `uinteger_t:6e74834` | decimal `str()` at 65,536 limbs 9.2 s to 145 ms, GMP 48 ms (M4 Pro) |
| representation: the limb vector alone | `uinteger_t:6ff439f` | `sizeof` 56 to 24 bytes; `a << 3` 74 to 17 ns (M4 Pro) |
| RFC 4648 presets: the mask and the leading digit | `base-x:c3965ec` | 240 of 240 random inputs match Python's `base64` (148 differed) |
| division-free conversion kernels | `uinteger_t:8486c75`, `a1d5b48`, `base-x:2c21ec4` | base58 32 bytes 156 to 34 ns, 1 KiB 37.4 to 6.2 us; base-x 32-byte encode 203 to 73 ns (M4 Pro) |
| base-x fixes from the first hunt | `base-x:d1fda10..ecbfb44` | about 1.4 million cases per run against an independent model |
| inline buffer of 8 limbs | `uinteger_t:8f1345e`, `dabd824` | 1 to 8 limbs: copy 10-13 to 2-3 ns, `a + b` 16-19 to 2-5, `a * b` 19-27 to 6-14 (M4 Pro) |
| carry last in the multiply-add (explorer) | `uinteger_t:5ee8586` | multiplication 8 to 11% faster from 16 to 1,024 limbs (M4 Pro) |
| three-prime transform multiplication | `uinteger_t:ee0a379` | 256K limbs 372 to 52.7 ms, GMP 48.1 (M4 Pro) |
| base-x codec and the byte path | `uinteger_t:007f08a`, `eb588dc`, `base-x:6bad890` | 32-byte base58 encode 74 to 57 ns, decode 88 to 53 (M4 Pro) |
| Newton division | `uinteger_t:0c99f86`, `32de4fc` | `div n/2`: a 32,768-limb dividend 27% faster, a 131,072-limb one 38% (M1 Pro) |
| Toom-4 products | `uinteger_t:af9c690`, `aa20669` | 1,024 limbs 5.9% faster, 768 limbs 2.2% (M1 Pro) |
| sanitizer CI in a light mode | `uinteger_t:4c094ad` | the ASan job 1,330 to 329 s |
| base-x RFC 4648 byte-exact, decode rejects text after padding | `base-x:2507a82..9adf6bd` | 0 mismatches against Python's `base64`; the 35 non-RFC presets byte-identical |
| public `compare`, `mul(r, a, b)`, `divmod(q, r, a, b)` | `uinteger_t:d1be6ed` | reused outputs within the buffer allocate nothing |
| division basecase: one carry chain in the multiply-subtract (explorer) | `uinteger_t:1c07a32` | `div n/2` at 16 to 64 limbs 16 to 18% faster (i9) |
| quotient-only division with a repair | `uinteger_t:b7a06cd..afdded1` | random operands 8 to 36% faster at 16 to 128 limbs, exact multiples 0 to 15% slower (i9) |
| digit splitters fixed to the base's chunk shape | `uinteger_t:03b2fa0` | base58 32-byte encode 163.7 to 142.5 ns (i9), 8% (M4 Pro) |
| eight-limb addition (explorer) | `uinteger_t:bd83419` | `a + b` 30% faster from 256 limbs (M1 Pro); 0.59 to 0.92 of master's time on both machines |
| `leading_zeros` for Bitcoin and Ripple base58 | `base-x:27be05e..7735f77` | 1 to 3 ns on the two flagged presets only (M1 Pro) |
| golden output of every preset | `base-x:74d6855` | 41 presets, one line per case |

Two hunts read the code around the landings, where the reviews had not looked. The first (83,000
operator checks at 64-bit limbs against Python's `int`, 62,000 each at 32-bit limbs and on the portable
primitives, 72,000 base-x cases against the model) found five bugs that reproduce on the original
headers: `x *= 1` after `x >>= 64` gave the shifted-out limbs back, a moved-from value after a right shift
had `size()` 2^64 - 1, `encode` into a non-empty result padded and summed over the whole buffer,
`is_valid` rejected every padded RFC 4648 text, and `decode` stopped at a NUL byte in an alphabet without
padding. The second widened the system review's A1 (an all-zero buffer parsed to a zero that is not 0,
and dividing by it raised `SIGFPE` on x86-64) and found that `5 << big` did not compile.

## Dropped, and why

- **Toom-4 squaring.** On a quiet M1 Pro it measured 0.6% faster than Toom-3 at 1,024 limbs against an
  A/A spread of 0.2%, short of the 3% a tier must earn, while Toom-4 products gained 5.9%. Squares take
  Toom-3 up to the transform; the kernel, its cutoff and `UINTEGER_T_SQR_TOOM4_THRESHOLD` went
  (`uinteger_t:2bde294`).
- **An inlined loop for sums under 8 limbs.** On the quiet M1 Pro 2 and 4 limbs went from 5 to 4 and 7 to 5
  ns; on the i9, 4 to 16 limbs lost 1 to 2 ns. A result that wins on one instruction set and loses on the
  other is not landed.
- **A quotient-only cutoff of 512 limbs.** It would win more on random operands, but an exact multiple
  always takes the repair, and at 1,024 limbs it cost 86% more. The cutoff is 64 limbs (dividends up to
  about 130), where exact multiples cost at most 15% more.
- **Redoing a flagged division.** The first version of the quotient-only kernel handed a flagged digit to
  the recursive division and started over; the repair subtracts the products it skipped and finishes
  exactly (`uinteger_t:a9af8cf`). It took a second review scoped to the new commits.
- **The window view and the carry member.** Nothing built a view once Karatsuba ran on raw pointers, and
  nothing read `_carry`; the offset the view kept was the cause of two of the hunt's bugs.
- **Public conversion primitives.** `divmod_small`, `mul_add_small` and `base_chunk` were public from
  `aeeeb67` to `bd7bab1` so that base-x could call them; `digits()` and `from_digits()` replaced them and
  they are private again.
- **A scaled remainder tree.** With only full products a middle product costs about what the division it
  replaces does (2.1 M(n/2) measured); it pays only with a middle-product kernel.
- **A larger quadratic range.** Raising `UINTEGER_T_RADIX_MAX_BITS` is up to 15% faster between 129 and 320
  limbs, but each new size builds its table with a quadratic first use.
- **Inline assembly for the basecase.** GMP's basecase sits at the carry flag's throughput bound and the
  carry-last kernel is 10 to 15% from it (M4 Pro); assembly could at best match GMP.
- **Leading zeros in every base58 preset.** Writing Bitcoin's leading zero bytes changes stored text, so
  the lead left it to the owner and built it as a flag on `bitcoin()` and `ripple()` alone, which the owner
  landed; every other preset kept its text.

## Where it lives now

The campaign's working folder (plans, ledgers, probes, the research note) is not kept. What it learned is
in the repositories:

- **uinteger_t:** [README](https://github.com/Kronuz/uinteger_t/blob/master/README.md) (the Performance
  table against GMP and Boost), [ARCHITECTURE.md](https://github.com/Kronuz/uinteger_t/blob/master/ARCHITECTURE.md),
  [docs/API.md](https://github.com/Kronuz/uinteger_t/blob/master/docs/API.md),
  [docs/design/](https://github.com/Kronuz/uinteger_t/tree/master/docs/design) (the proof of the
  quotient-only division, the bounds of every kernel, the sweeps behind the cutoffs, the designs that
  measured slower), [docs/OPEN-WORK.md](https://github.com/Kronuz/uinteger_t/blob/master/docs/OPEN-WORK.md),
  [docs/BENCHMARKING.md](https://github.com/Kronuz/uinteger_t/blob/master/docs/BENCHMARKING.md),
  [docs/MUTATION.md](https://github.com/Kronuz/uinteger_t/blob/master/docs/MUTATION.md),
  [CHANGELOG.md](https://github.com/Kronuz/uinteger_t/blob/master/CHANGELOG.md),
  [AGENTS.md](https://github.com/Kronuz/uinteger_t/blob/master/AGENTS.md) (traps and rules of thumb), and
  `bench/results/` (the raw runs behind the README).
- **base-x:** [README](https://github.com/Kronuz/base-x/blob/master/README.md) (base58 against Firedancer
  and libbase58), [ARCHITECTURE.md](https://github.com/Kronuz/base-x/blob/master/ARCHITECTURE.md),
  [docs/API.md](https://github.com/Kronuz/base-x/blob/master/docs/API.md),
  [docs/OPEN-WORK.md](https://github.com/Kronuz/base-x/blob/master/docs/OPEN-WORK.md),
  [docs/BENCHMARKING.md](https://github.com/Kronuz/base-x/blob/master/docs/BENCHMARKING.md),
  [docs/MUTATION.md](https://github.com/Kronuz/base-x/blob/master/docs/MUTATION.md),
  [CHANGELOG.md](https://github.com/Kronuz/base-x/blob/master/CHANGELOG.md),
  [AGENTS.md](https://github.com/Kronuz/base-x/blob/master/AGENTS.md), `test/golden/encode.txt` (the
  text of every preset) and `bench/results/`.
- **This catalog:** the two entries in [AGENTS.md](../../AGENTS.md), their sections of
  [LESSONS.md](../LESSONS.md#uinteger_t), and their rows in [PERFORMANCE.md](../PERFORMANCE.md).

## Open

The follow-ups of the reviews that are still open, each listed with its measurement in the repository's
OPEN-WORK.md:

- uinteger_t: no test forces the quotient-only kernel's fallback (divq-repair RC2); modular arithmetic and
  a constant-time type for secrets; decimal parsing up to 4,096 bits takes 1.1 to 1.5 times Boost's time
  (M1 Pro); a short quotient by a long divisor (4 by 2,048 limbs: 1.3 us against GMP's 0.09 on the i9);
  addition at 0.43 against GMP's 0.31 ns per limb (M1 Pro) needs assembly; the Toom-4 cutoff is the M4
  Pro's.
- base-x: 13 of Bitcoin Core's 21 base58 vectors pinned (bx-lz RC1); the `leading_zeros` and
  `block_padding` conflict is only an assert (RC4); a Release CTest build compiles out `test/test.cc`'s
  asserts (RC5); `encode` into a `std::vector` does not compile (RC7); the table paths are AArch64 only.
