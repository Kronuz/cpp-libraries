> Moved here on 2026-11-08 from the unversioned `~/code/Kronuz/KRONUZ_REFACTORING_DIRECTIVES.md` (last edited 2026-07-02), which strata `docs/PLAN.md` (Phase 7, "Throughout") and Xapiand `docs/dev/extraction-ledger.md` cite. The text below is unchanged.

# Kronuz Refactoring Directives

A methodology for **disassembling a monolith into many small, generic, reusable libraries**
without losing anything. Project-agnostic: "the app" below is whatever monolith you are
refactoring, "the library namespace" is wherever your extracted libs live, and "the app's
regression net" is whatever end-to-end suite proves the app still works.

---

## 1. The north star

Break the app into **many small/medium, generic, reusable libraries**, and make the app itself
**as few lines as is feasible and technically possible**. The end state is a thin application
that is mostly composition — it wires together clean, independently useful components and keeps
only the irreducible domain glue (its own types' domain fields, its domain-specific handlers, its
policy). Everything that is not intrinsically about the app's problem domain is a candidate for
extraction.

A good extraction is one another project could adopt without ever knowing your app exists.

## 2. The prime directive (non-negotiable)

**Never lose performance, functionality, or reliability.**

Extraction is a **behavior-preserving move, not a rewrite.** You are relocating proven code into
a reusable shape, not reimplementing it. The refactor is done right only if the app behaves
*identically* afterward — same outputs, same performance, same failure behavior — with the sole
exception of a deliberate, separately-validated improvement.

When in doubt, preserve. Cleverness that changes behavior is a regression wearing a nice hat.

## 3. Extraction principles

- **Faithful / verbatim port.** Move the logic as-is. Keep the algorithm line-identical and any
  wire/file/binary format byte-identical, so a not-yet-migrated peer or an on-disk artifact still
  interoperates. Translate *only* the couplings (see below) into injected seams; leave the actual
  logic untouched.
- **Separate "extract" from "improve."** Do the extraction first, prove it is behavior-identical,
  *then* improve in a follow-up change with its own validation. Never smuggle an optimization or a
  cleanup into an extraction — you lose the ability to tell which change caused a regression. This
  is doubly true for safety-critical code (consensus, replication, crypto, allocation): a subtly
  "improved" algorithm is a latent disaster, and happy-path tests will not catch it.
- **Inject the couplings; keep the domain out.** A generic lib must not know the app's domain. The
  places the original code reached into the app — transport, the app's object model, global state,
  lifecycle callbacks, "apply this effect" — become **injected seams**: template parameters,
  small interfaces, or callbacks the app implements. The lib provides the mechanism; the app
  provides the policy and the domain.
- **Try clean-generic; fall back honestly.** Prefer a clean, generic, extensible lib. But if a
  piece is so fused with the app that its seams would be *nothing but* app-specific hooks, it is
  not really generic — **keep it in the app** rather than ship a fake-generic lib with a misleading
  interface. Say so explicitly and record why. A lib that is generic in name only is worse than an
  honest app-side module.
- **Compose, don't over-fragment.** Two pieces that share state, a transport, and a lifecycle can
  live in one lib as separate modules (separate headers), not two repos with a chatty interface
  between them. Split further later, once the seams have proven clean and stable — the way a router
  can be spun out of a web framework after it has settled.

## 4. The couplings (what becomes a seam)

When you read the original code, categorize every reference to the outside world:

| Coupling | Becomes |
| --- | --- |
| I/O, sockets, the event loop, threads | the runtime the lib rides on (injected or a dependency) |
| The app's object/record model | a template parameter or a serialization/identity concept |
| Global registries / singletons | an injected provider interface |
| App lifecycle / state machine | injected policy gates + hooks ("may I act now?", "I did X, react") |
| "Apply this effect to the app" | an injected callback |
| Logging / metrics | a no-op-by-default hook, or dropped from the lib |
| Config / feature flags | constructor options with sane defaults |

The pure logic — the algorithm, the state machine, the framing, the data structure — stays in the
lib untouched. Everything in the table above is the seam.

## 5. The "complete" criterion

**An extraction must let the app lose nothing — every function, every feature, and every
performance optimization of the original, preserved line by line.** The only acceptable deviation
is an improvement.

If the original had a dual buffered/streaming mode, a fast path, a specific socket-buffer sizing, a
back-pressure knob, an EINTR-safe retry, a graceful-shutdown dance — the lib carries **all of it**.
A simplified subset that "covers the common case" is not an extraction; it is a regression that
will surface later as a lost feature or a perf cliff. Diff the original against your port and
account for every line: it either moved into the lib, moved into an injected seam, or is dead (and
you can prove it).

## 6. The deliverables standard

A library is **genuinely reusable** — and only then "done" — when it is **documented, demonstrated,
measured, tested, and complete**:

1. **README** — what it is, the shape/mental model, a usage snippet, how to build/depend on it.
   *(documented)*
2. **ARCHITECTURE** — how the pieces fit, the data/control flow, and the extension seams. *(documented)*
3. **AGENTS / working notes** — orientation for whoever (human or agent) works on it next: the file
   map, the **invariants** ("do not regress these"), the gotchas, and how to build/test. *(documented)*
4. **examples / demos** — at least one runnable program showing real use, distinct from the tests.
   *(demonstrated)*
5. **benchmarks** — when perf is relevant to the lib: a throughput/latency harness or a before/after
   comparison, so a consumer can reason about cost. Skip only where perf is irrelevant, and say so.
   *(measured)*
6. **tests** — unit/integration tests, green in CI, covering the invariants and the edge cases
   (not just the happy path). *(tested)*
7. **complete** — satisfies §5: nothing lost, line by line. *(complete)*

Miss any of these and the lib is a draft, not an extraction.

## 7. Performance discipline

- **No regressions, measured not assumed.** If you touch a hot path, benchmark before and after.
  The benchmark from the deliverables standard is what makes this checkable.
- **Seams cost, so place them well.** An injected interface (a virtual call, a `std::function`) is
  free on a control-plane path (timers, setup, gossip-rate messages) and must be avoided in a hot
  data path — use compile-time seams (templates, policies) there instead.
- **Preserve the micro-optimizations (§5).** Buffer reuse, `reserve`, zero-copy views, batching,
  fast paths — these are features. Carry them across verbatim.
- **Re-evaluate legacy algorithm/codec choices, measure the swap.** A dependency picked years ago
  was the best option *then*; extraction is the moment to check if a modern one is strictly better
  (e.g. a compression codec: better ratio at competitive speed is less bytes on the wire or disk —
  an efficiency win in bandwidth/storage cost, not just latency). Only swap when a benchmark says
  it wins on the axis that matters (ratio for a transfer/storage path, speed for a hot path). Treat
  a wire-format or on-disk-format codec change as a **compatibility event**: it needs both ends on
  the new codec plus a protocol/format version bump (fine when you own both ends and it is
  pre-production; flag it loudly otherwise, §10). Default the *new* code to the modern choice; do
  not rewrite already-shipped formats without the version discipline.

## 8. Reliability discipline

- **Prove behavior is identical.** Validate the extracted lib in isolation (unit tests: drive it
  exactly like the app did, assert identical results), *then* validate the app against its full
  regression net after wiring. Both, not either.
- **De-risk with sequencing.** Build and test the lib standalone first (zero app risk). Wire the
  app second, as its own step, validated against the net. Do not do "new lib + app rewire" as one
  untestable leap.
- **Atomic changes are focused efforts.** Some cutovers cannot be split into safe intermediate
  states (you cannot half-replace a running subsystem). Treat each as its own focused, fully-
  validated change — never leave a half-migrated essential subsystem, and never start one you
  cannot finish and verify.
- **Keep a fallback.** Work on a branch / in revertible commits, so a cutover that does not reach
  green can be rolled back to the last validated state without losing the extracted lib.

## 9. Library mechanics (conventions)

- **Header-only where practical** — the smallest possible consumption story.
- **A clean build target** — one importable target named for the lib (`<lib>::<lib>`), with its
  include path, standard, and transitive deps attached, so a consumer links one thing.
- **Dependencies fetched, not vendored** — pull deps by their published tip (or a pin), with a
  local-source override for parallel development across libs; never copy a dependency's source in.
- **Tests/examples/benchmarks build only when the repo is top-level** — a consumer that embeds the
  lib gets the header target and nothing else.
- **One identity, one namespace** — publish every lib under the same namespace and the same commit
  identity, so the family is coherent and its provenance is clean.

## 10. Flag what smells (but still port it faithfully)

Extraction is the closest reading a codebase ever gets. When the line-by-line port surfaces
something that looks like **a bug, a hard bad practice, or an anti-pattern**, do two things:

1. **Port it faithfully anyway.** Per §3, you preserve behavior — you do not silently "fix" it
   during extraction (that would smuggle an unvalidated change into a behavior-preserving move),
   and you do not silently carry it as if it were fine.
2. **Flag it loudly, clearly, and with fundamentals.** Call it out in your report, in the lib's
   ARCHITECTURE/AGENTS, and in the project log — with the *reasoning*: what it is, why it is
   suspect, the concrete scenario where it bites (or why it happens not to today), and the
   severity. Distinguish a **verifiable bug** (wrong result under a describable input) from a
   **latent foot-gun** (correct today only because of an implicit invariant) from a
   **scalability/design boundary** (works within an unstated limit) from a **cosmetic smell**.

The point is to let the owner make a *deliberate* decision: fix it as a separate, validated
improvement (§3's "separate extract from improve"), accept it with eyes open, or document the
invariant that keeps it safe. A silent bug carried into a shiny new "reusable" library is worse
than the original — now it is reused. Loud-flagging is how the reader-of-record (the extractor)
pays the codebase back for what it learned.

Do not overclaim: a flag must have fundamentals. "This looks weird" is not a flag; "this indexes
`v[i-1]` with an unsigned `i` that can be 0, guarded only by a short-circuit two lines up" is.

## 11. The extraction checklist

For each piece you extract:

- [ ] Read the original fully; categorize every outside-world coupling (§4).
- [ ] Decide clean-generic vs. app-side-fallback honestly (§3).
- [ ] Port the logic **verbatim**; route couplings through seams; keep formats byte-identical (§3, §5).
- [ ] Account for every original line: moved, seamed, or provably dead (§5).
- [ ] Flag any bug / bad practice / anti-pattern the reading surfaced — loudly, with fundamentals (§10).
- [ ] Ship README + ARCHITECTURE + AGENTS + examples + benchmarks + tests (§6).
- [ ] Prove it standalone (unit tests drive it like the app did) (§8).
- [ ] Wire the app as a separate step; validate against the full regression net (§8).
- [ ] Benchmark any touched hot path; confirm no perf loss (§7).
- [ ] The app is now thinner and lost nothing (§1, §5).

---

*The measure of a good refactor: the app got smaller, a new reusable library exists, and nobody
can tell the difference in what the app does or how fast it does it — unless it got better.*
