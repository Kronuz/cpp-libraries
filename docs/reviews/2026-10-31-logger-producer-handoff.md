# Logger producer path review: the post() hand-off (scheduler) and the logger's producer path

- Date: 2026-10-31. Kind: architect review of the scheduler's `post()` hand-off and the logger's producer
  path, with a re-check, from the October 2026 performance and correctness work (read-only).
- Repos: scheduler `perf/scheduler-producer` at `4738a05` (base `main` `5fa44d1`), re-checked at `b0b1920`;
  logger `perf/logger-producer` at `6bff8fe` (base `main` `5299eb3`), re-checked at `e86cc5e`; stash `351ef2e`
  and threadpool `628679a` as the scheduler pinned them. The work landed as
  `scheduler:5ad60fc..2c7345f`, `logger:c7332d6..61a05f5`.
- Machines: Apple M4 Pro. Method: [PERFORMANCE.md](../PERFORMANCE.md).
- Resolution checked against each repo's default branch on GitHub on 2026-11-01.

## Resolution

| finding | status | repo:sha | test |
|---|---|---|---|
| LPH-R1 countdown exit and `finish(0)` strand and leak accepted tasks | closed | `scheduler:5ad60fc` | `scheduler_post` (`finish_exit_none`, `finish_exit_countdown`, `finish_exit_zero`) |
| LPH-R2 task destructors and refusal runs execute under `mtx` | closed | `scheduler:5ad60fc` | `scheduler_post` (`dtor_posts`) |
| LPH-R3 `post_ordered()` contract across posters | closed | `scheduler:5ad60fc..2c7345f`, `logger:61a05f5` | `scheduler_post` (`ordered_posters`) |
| LPH-R4 `pending_count()` can undercount | partly closed | `logger:c7332d6` | - (`completed_` is read first; no test fails with the order reverted) |
| LPH-R5 relaxed load of `atom_next_wakeup_time` in push() | partly closed | `scheduler:5ad60fc` | - (seq_cst load; `scheduler_handshake_model` models `add()` only) |
| LPH-R6 `bad_alloc` from `arrivals.push_back` kills the worker | partly closed | `scheduler:5ad60fc` | - (no test on origin; `scheduler_no_memory` covers `add()` and `debounce()` only) |
| LPH-R7 tests that cannot fail | closed | `scheduler:c01a9e3`, `scheduler:2c7345f`, `logger:c7332d6` | `scheduler_post` (`finish_exit_*`, `peep_sleep_stale`), `logger_clock`; `race_once` is unchanged |
| LPH-R8 derived wall-clock stamp within 2 us | no change | - | `logger_clock` keeps the bound |
| LPH-R9 smaller contract differences | no change | `logger:61a05f5` | - (accepted; filing-time refusals documented in logger AGENTS.md, README cost corrected) |
| LPH-R10 `producers` times out under TSan | closed | `stash:78a18f3`, `scheduler:f27febe` | `stash` (`test_claim_walk`), `scheduler_post` (`producers`, under TSan) |
| LPH-R11 test name, hook comment, API.md omission | closed | `scheduler:5ad60fc..2c7345f` | - (documentation) |
| L1 close and drain `posted` on every exit (LPH-R1) | closed | `scheduler:5ad60fc..2c7345f` | `scheduler_post` (`finish_exit_none`, `finish_exit_countdown`, `finish_exit_zero`) |
| L2 no task code under `mtx` (LPH-R2) | closed | `scheduler:5ad60fc` | `scheduler_post` (`dtor_posts`) |
| L3 `completed_` before the stripes (LPH-R4) | partly closed | `logger:c7332d6` | - (as LPH-R4) |
| L4 `post_ordered()` contract and concurrent test (LPH-R3) | closed | `scheduler:5ad60fc..2c7345f`, `logger:61a05f5` | `scheduler_post` (`ordered_posters`) |
| C1 seq_cst load in push() (LPH-R5) | partly closed | `scheduler:5ad60fc` | - (as LPH-R5) |
| C2 `bad_alloc` while filing (LPH-R6) | partly closed | `scheduler:5ad60fc` | - (as LPH-R6) |
| C3 logger repins the landed scheduler | closed | `logger:f429478` (pin `scheduler:34631ec`) | `logger_transcript`, `logger_order`, `logger_producer` |
| C4 sleep-race seam test and clock test (LPH-R7) | closed | `scheduler:c01a9e3`, `logger:c7332d6` | `scheduler_post` (`peep_sleep_stale`), `logger_clock` |
| C5 README performance section | closed | `logger:f95ff17`, `logger:8d309e0` | - (documentation) |

Rows closed with `-` in the test column are documentation fixes, where no test applies. LPH-R4 and LPH-R5 are
memory-order fixes that no hardware run tells apart from the old order, and no model test covers them;
`peep_sleep_stale` fails with the pre-sleep read of `posted` removed (`scheduler:62a4fe8` records the check).

## Scope

- Reviewed: scheduler `perf/scheduler-producer` at 4738a05 (base main 5fa44d1; `scheduler.h`,
  `test/post.cc`, ARCHITECTURE.md "post()" and "The arrival queue", AGENTS.md invariants, docs/API.md,
  CHANGELOG.md); logger `perf/logger-producer` at 6bff8fe (base main 5299eb3; `logger.h`, `logger.cc`,
  `test/order.cc`, `test/producer.cc`, `test/format.cc`, `test/transcript.cc` with `test/frozen`,
  AGENTS.md "Load-bearing invariants", ARCHITECTURE.md "What one call costs", README.md,
  docs/status/producer-path.md). Dependencies as pinned: stash 351ef2e, threadpool 628679a (scheduler's
  CMakeLists.txt); logger fetches the scheduler at 4738a05 (confirmed in `_deps/scheduler-src`).
- Checked against: the done criteria in docs/status/producer-path.md (K2: output bytes, ordering,
  `finish()` drain and the inline path for severe lines unchanged); the scheduler's documented
  guarantees for `post()` (scheduler.h:587-618, ARCHITECTURE.md:124-170, AGENTS.md:105-128); the logger's
  invariants (AGENTS.md:111-139); stash's insert floor (stash.h:258-283, 316-325 at 351ef2e).
- Checked by: Homebrew clang 23.1.4 on an Apple M4 Pro, every build under a light hold:
  - scheduler `test/post.cc`, plain -O2 (2.5 s) and TSan -O1 (9.8 s): all pass, no TSan report;
  - logger, TSan Debug -O1 (top-level build of the branch): `logger_test`, `logger_order_test`
    (40 rounds, half with a stalled LOG thread, 2 793 974 ordered pairs), `logger_producer_test 6`
    (320 000 lines from 8 threads exactly once in thread order, 2 715 638 ordered pairs across 4 threads,
    counters, 6 finish races), `logger_format_test` (310 326 fast-path messages equal to `std::vformat`):
    all pass, no TSan report;
  - logger Release: `logger_transcript` (new against `test/frozen`): identical bytes;
  - mutants of scheduler.h at 4738a05 against `test/post.cc`: `no_filing_tick` (ingest_tick from the
    due time, :346) dies in `mixed_order(true)` round 0; `no_close` (no `ingest(true)`, :498) survives
    3 of 3 runs; `no_presleep_ingest` (:521 removed) survives 2 of 2;
  - probes P1-P5, built against the pinned stash and threadpool:
    - P1: a task accepted before `finish(0)` stays in the stack, never runs, is never freed (probe not
      kept; covered by `scheduler:test/post.cc` `finish_exit_zero`);
    - P2 (with a hook in push() after the `stopping` check): the countdown exit leaves the stack open
      (probe not kept; covered by `scheduler:test/post.cc` `finish_exit_countdown`);
    - P3: a cancelled task's destructor that posts deadlocks the worker (probe not kept; covered by
      `scheduler:test/post.cc` `dtor_posts`);
    - P4: what `post_ordered()` does with decreasing wakeups (probe not kept; covered by
      `scheduler:test/post.cc` `ordered_posters`);
    - P5: `steady_now()` and `system_at()` against the standard clocks (probe not kept; covered by
      `logger:test/clock.cc`, CTest `logger_clock`).
  - Not run: benchmarks (out of scope for this review); ASan (hangs on the M4 Pro); Linux, FreeBSD and
    the Intel Core i9-9980HK; the logger's full 40 finish-race rounds (6 under TSan); fuzzing. The memory-order
    findings LPH-R4 and LPH-R5 are by reading only.

## Verdict

**APPROVE WITH CONDITIONS: the hand-off, the ordered queue and the producer path hold their
ordering and exactly-once claims under TSan and a live oracle, but `finish()`'s "never stranded"
guarantee covers one of the worker's exits, and the worker runs task code while it holds its own
mutex. Both need small fixes before the scheduler lands and the logger repins.**

What holds, and reproduces:

- The stack is sound. Pushes are compare-exchanges on `posted` (scheduler.h:645) and the take is one
  exchange (:322). Every successful push is a release RMW, so the exchange acquires every poster's
  `post_next`, `post_hold`, `wakeup_time` and `post_ordered`. The stack only grows by push and is only
  emptied whole, so there is no ABA: a recycled address at the head is the head. Until the take, the
  task owns itself through `post_hold`; after it, the worker's local `task` owns it (:337). A task
  cancelled before filing is dropped with no entry (:340). TSan finds no race in `test/post.cc` or in
  the logger's tests.
- The Dekker pair holds as written (all four accesses seq_cst, :511/:520/:521 against :645/:655), and
  so does the `wake_requested` coalescing. I checked each interleaving of a poster against the clear at
  :512 and the pre-sleep ingest; the one weak spot is the relaxed load at :650 (LPH-R5).
- The merge reproduces the wheel's order. `filing_tick()` (:183-187) is exactly stash's rule
  (`key < floor ? floor : key`, stash.h:282-283), read by the only thread that moves the floor.
  Filing ticks are monotone in filing order for tasks whose due times are, so pairs ordered by
  happens-before keep due order (proof under LPH-R3). The oracle is live: the `no_filing_tick` mutant
  fails `mixed_order(true)` ("round 0 (stalled): task 9 fired after task 55 although due first"),
  which reproduces the revert check the change records.
- K2 holds in the runs: identical transcript bytes; due order per thread and across threads ordered
  by turns, with and without a stalled LOG thread; exactly once from 8 producers; every line written
  once in 6 finish races under TSan. The refused-line policy (logger.cc:926-941) and the `clears`
  cancel/swap path are unchanged, apart from the new refusal reasons noted in LPH-R9.
- `steady_now()` reads the same clock as `steady_clock` on the M4 Pro. P5: 0 of 1 000 000 readings
  fell outside a `steady_clock` bracket. The host has slept 34 904 s since boot, and `steady_clock`
  sits 42 ns from `mach_continuous_time` and 34 904 s from `mach_absolute_time`, so the start-up check
  is not just passing on a host that never slept.

What blocks landing: LPH-R1 (the countdown exit and `finish(0)` strand and leak accepted tasks; the
test that claims to guard the close cannot fail) and LPH-R2 (task destructors and refusal runs execute
under `mtx`; a destructor that posts deadlocks the LOG thread). The fixes are local; see L1-L4.

## Findings

**LPH-R1 (medium; low for the logger's line loss). The closed mark covers the `break` exit only; the
countdown exit and `finish(0)` leave `posted` open, and an accepted task left there never runs and is
never freed.** The worker closes the stack only on the nothing-pending exit (scheduler.h:494-501). When
`ending` reaches 0 with something due inside the 100 ms peep window, the loop ends at `while (ending
!= 0)` (:452) and nothing closes or drains the stack. `finish(0)` exits the same way after the current
pass. The worker has no destructor that drains `posted`. A task left there holds itself through
`post_hold` (:113-114), so it is never destroyed.
- P1 is deterministic, with no mutant. The worker is held inside a task after the pass's ingest; a task
  is posted (accepted, `finish()` has not begun), then `finish(0)` is called and the worker released.
  Output: `finish(0): post()=scheduled, fired=0, task freed=NO`. Control: `finish(1): post()=scheduled,
  fired=1, task freed=yes`.
- P2 uses a copy of scheduler.h with one hook after push()'s `stopping` check (:631). It holds a
  poster where a preempted thread would stand, past its check and before its push. Results:
  - nothing pending at `finish(1)`: the worker closes, and the held poster is refused (`stopping`), as
    documented;
  - a task due 60 ms out (inside the peep window): the worker leaves by the countdown and the held
    poster's push succeeds. Output: `far task pending: finish(1) joined=yes, post()=scheduled,
    fired=0, task freed=NO`, 3 of 3 plain runs and under TSan;
  - a first version used a task due 400 ms out, and the poster was refused there too: `peep()` looks
    only 100 ms ahead while ending (:464, :470), so that task did not count as pending and the loop
    closed. The countdown exit needs work due within 100 ms at each of `wait` passes.
- By reading: a racer that `ingest(true)` files in the pass where the countdown reached 0 is filed and
  then abandoned, because `continue` (:499) re-tests `ending != 0` and leaves.

Why it matters. ARCHITECTURE.md:164-169, AGENTS.md:113-117, CHANGELOG.md:19 and the `post()` comment
(scheduler.h:597-598) all promise "a task that raced it is refused, never stranded", and name
`test_finish_race` as the check. It is not one: the `no_close` mutant passes it 3 of 3 times (about
1.9 million accepted tasks per run, "none stranded"). The test only reaches the `break` exit (it uses
`finish(10)` and tasks due now), and its race window is the few nanoseconds between push()'s load of
`ending` and its compare-exchange.

For the logger: `Logging::finish(wait)` is `scheduler().finish(wait)` (logger.cc:766-768), and
`~Scheduler` is `finish(1)`. A line from a thread descheduled in that window, during a drain whose
passes keep finding lines due (deferred lines with distinct due times), is accepted and never written.
The same race existed with `add()`, which filed the line on a wheel nobody walked again, so line loss
is not new. What is new: the record leaks, `completed_` never counts it, and `pending_count()` stays
at 1 or more for the rest of the process.

Fix:
1. On every exit from the loop (after it), close and drain: `ingest(true)`, then run the filed tasks
   that are due and release the rest. Nothing may stay in `posted`, where a task owns itself.
2. When `ingest(true)` files tasks, do not let the countdown end the loop before they run, for example
   `if (ingest(true)) { if (ending == 0) ending = 1; continue; }`.
3. Add a `SCHEDULER_TEST_HOOK` site in push() after the `stopping` check, and a deterministic test for
   both exits (P2's shape) plus `finish(0)` (P1's shape) that fails on the `no_close` mutant and on
   4738a05.

**LPH-R2 (medium). The worker runs task code under its own mutex; a destructor or task that posts
deadlocks it.** The pre-sleep ingest runs between `lk.lock()` (:510) and the wait (:518-521). Inside
it, `ingest()`:
- drops a task cancelled before filing (:340), which may release the last reference and run its
  destructor;
- runs a due task the wheel refused (:357), calling the task itself.

If either posts (or adds), push() finds `sleeping` set and `wake_requested` just cleared (:512), and
locks `mtx` (:657-659), which this thread already holds.

P3 is deterministic through the existing `after_peep` seam. The hook posts a cancelled task whose
destructor posts. Output, plain and TSan builds alike: `worker stuck: destructor entered post()=yes,
returned=no, fired=1  <-- self-deadlock on mtx`.

The LOG thread then stops for good. Later posters find `wake_requested` already set, so they do not
block, but nothing is written, the stack grows without bound, and `finish()`'s join times out.

Logger exposure is narrow but real:
- `~Logging` runs `clean()`, which posts a pending swap line (logger.cc:1062-1067) when the record was
  never cleaned on the producer. That happens with a `Log::release()`d record that is cancelled and
  then given an `unlog` line.
- The refusal run at :357 calls the sinks under `mtx`, so a sink that logs deadlocks, and a slow sink
  holds the mutex that posters take to signal.

For the scheduler API, it applies to any task type whose destructor or body touches the scheduler.
Before this change, the worker ran task code only after `lk.unlock()`.

Fix: under the lock, only test whether `posted` is non-null (that read is the Dekker half; keep it
seq_cst). If it is, skip the wait: unlock, ingest, and go round. Alternatively, have `ingest()` collect
the cancelled and refused tasks in a local list that is run and released after `lk.unlock()`. Add P3
as a test.

**LPH-R3 (low; documentation and a missing test). The logger breaks `post_ordered()`'s precondition
across threads. The effect is bounded and keeps the logger's guarantee, but both repositories document
it wrongly.**

The logger's AGENTS.md:122-127 says "wakeups never decrease in posting order", and ARCHITECTURE.md:139
says "its wakeup times never decrease". That holds per thread only. The wakeup is `now + 1 ms`, with
`now` read at logger.cc:812, and the push comes later at scheduler.h:645, after `system_at`, an
allocation, a copy and possibly a preemption. Two threads whose reads and pushes interleave post
decreasing wakeups.

At the scheduler level, `fire_due()` compares only the queue's head (:380-408). A task behind a
later-due head waits for that head, and wheel tasks due between the two pass it. P4 posts Y ordered at
+6 ms, then X ordered at +1 ms, then W through `post()` at +3 ms. Output: `due order: X(+1ms) W(+3ms)
Y(+6ms); fired: W(+3.77ms) Y(+6.48ms) X(+6.48ms)` (3 of 3 runs, and under TSan).

For the logger the effect is bounded. Everything ahead of line L in the queue was pushed before L, so
it read its clock before L's push and is due by L's push time + 1 ms. Hence:
1. L is written at most about 1 ms after its push.
2. If L happens-before a later line M (same thread, or any synchronization), every entry ahead of L is
   due no later than M. Filing ticks are monotone in filing order (the floor only rises), so L and
   everything ahead of it fire before M, at an equal tick by filing order. The documented guarantee
   (lines of one thread, the due-time oracle of `test/order.cc` and of `test_order_across_threads`)
   holds. The runs agree.
3. Lines of different threads with no ordering between them can leave due order by up to the gap
   between a poster's clock read and its push.

Decision: the logger may keep `post_ordered()`, but the contract must say what it is.

Fix:
- The scheduler's `post_ordered()` comment (scheduler.h:611-618), ARCHITECTURE.md:145-147, AGENTS.md:125-126
  and docs/API.md:29-32 should state: nondecreasing per poster; across posters a late arrival waits for
  the head and is passed by wheel tasks due before it; tasks whose posts are ordered by happens-before
  and whose wakeups are the post's clock plus a fixed delay keep due order.
- The logger's AGENTS.md:122-127 and ARCHITECTURE.md:139 should say the same.
- Add a scheduler test with several `post_ordered()` posters that read the clock, wait a random time,
  then post (the logger's shape), checking pairs ordered through a shared turn. `test_producers` uses
  `post()` only, and the logger's producer test never stalls between the clock read and the push.

**LPH-R4 (low; by reading). `pending_count()` can undercount and report 0 while lines are pending.**
logger.h:583-590 loads the stripes (relaxed) first and `completed_` (acquire) second. A reader can
acquire the completion of line L while its earlier relaxed stripe loads miss L's increment; on arm64
nothing orders them. The count then comes out low, and the clamp `n > 0 ? n : 0` hides the negative
case. So the promise at logger.cc:750 and AGENTS.md:128-132 ("a reader that sees the count drained
sees the writes") does not hold as coded. Users: backpressure (logger.cc:897), and the tests' `drain()`
and `settle()`, which then sleep or count lines, so no test shows it. Fix: load `completed_` with
acquire first, then the stripes. A line's stripe increment (logger.cc:922) is sequenced before its
push, which the LOG thread acquires before the line can complete, so with `completed_` read first
every completed line's increment is visible. The count can then no longer go negative, and the clamp
can become an assertion.

**LPH-R5 (low; formal; by reading). push() decides whether to signal from a relaxed load of
`atom_next_wakeup_time` (scheduler.h:650).** In the C++ model that load can return the target from
before the worker's raise at the top of its pass (:493), even though the poster then reads `sleeping
== true`. The poster then sees a target at or before its task, does not signal, and the worker sleeps
to the raised target (up to 30 s). On arm64 and x86 the preceding seq_cst compare-exchange forbids it
(the cycle raise -> DMB -> worker's load of `posted` -> fr -> CASAL -> poster's load -> fr -> raise is
not allowed), so it is not reproducible. `add()` loads seq_cst and fences (:565-569). Fix: load seq_cst.
It costs nothing after the RMW.

**LPH-R6 (low; by reading). An allocation failure in `arrivals.push_back` (scheduler.h:348) kills the
worker silently.** The exception leaves `operator()`, and `Thread::_runner` stores it in the promise
(threadpool thread.hh:91-97). The thread exits, every later `post()` returns `scheduled` and never
runs, and the rest of the taken list leaks. The `post()` comment (:599-601) promises that allocation
failures while filing run the task if due and drop it otherwise. Fix: catch around the push and apply
that policy.

**LPH-R7 (low). Tests that cannot fail, or that test something nearby.**
- `test_finish_race` (`no_close` survives; LPH-R1).
- No test pins post()'s side of the sleep race the way `test_add_between_peep_and_sleep` pins
  `add()`'s: the `no_presleep_ingest` mutant passes 2 of 2. The lowering of `atom_next_wakeup_time` in
  push() (:651) already carries most of that handshake. So either the pre-sleep ingest is mostly
  redundant, and AGENTS.md:110-111 and ARCHITECTURE.md:137-143 overstate it as "the Dekker pair", or
  it needs a seam test. Write one with the `after_peep` seam: post from the hook with a time at or
  after the published target, and check the task is not slept through.
- `logger_producer`'s `race_once` has the same nanosecond window as `test_finish_race`.
- No test compares `system_at()` with `system_clock`: the transcript hooks the stamp to "TS "
  (transcript.cc:111). `test/order.cc` logs through `do_log` (`steady_clock`), not through the macros
  (`steady_now()`). P5 covers both on the M4 Pro; a small test should keep it so on others.

**LPH-R8 (informational). The derived wall-clock stamp is within 2 us of `system_clock`.** P5, 4
threads over 3 s across 20 ms re-measurements: 184 105 of 370 828 stamps fell outside a
`system_clock` bracket, worst 2 000 ns. That is the wall clock's microsecond resolution carried into
the offset, inside the documented bound (logger.h:207-211). At the default microsecond precision, a
thread's stamps can step back by up to that across a re-measurement. No change required.

**LPH-R9 (informational). Smaller contract differences.**
- Wheel refusals now happen at filing, not at the call:
  - `no_memory` at filing, and `past_horizon` at filing (a wakeup under an hour ahead, which post()
    does not check, on a wheel whose low-water mark lags by most of a day), drop a future line
    silently (scheduler.h:353-359);
  - the logger's policy for refused lines (logger.cc:926-941) sees only refusals at the call, so a
    severe future line refused there is no longer written inline.
- `before()` (:368-373) gives `add()`ed tasks sequence 0 and their due tick, not the floor tick. So
  within a tick they precede arrivals (documented, AGENTS.md:127-128), and an overdue `add()`ed task
  also sorts ahead of arrivals filed between its due tick and the floor (not documented).
- A walk parked on another producer's in-flight `add()` lets queued tasks pass wheel tasks behind it.
- The logger uses no `add()`, so none of this reaches it.
- The README still says 235 ns per call and "reads the steady clock once and the system clock once"
  (README.md:88, :106). The status file lists this as next.

## Blocking items / Required changes

- L1 (LPH-R1): close and drain `posted` on every exit of the worker loop, and keep tasks that
  `ingest(true)` files from being abandoned by the countdown. Nothing posted may outlive the scheduler
  holding itself. Add a deterministic test for the countdown exit and for `finish(0)`, through a new
  `SCHEDULER_TEST_HOOK` site in push(). It must fail on 4738a05 and on the `no_close` mutant. Correct
  ARCHITECTURE.md:164-169, AGENTS.md:113-117 and CHANGELOG.md:19 to what the test proves.
- L2 (LPH-R2): run no task body or destructor while holding `mtx`. Add P3 as a test; it must hang or
  fail on 4738a05 and pass after the fix.
- L3 (LPH-R4): read `completed_` before the stripes in `pending_count()`.
- L4 (LPH-R3): state `post_ordered()`'s contract across posters in the scheduler, and correct the
  logger's "wakeups never decrease" claims (logger AGENTS.md:122-127, ARCHITECTURE.md:139). Add the
  concurrent `post_ordered()` test with a delay between clock read and push.

## Conditions

- C1 (LPH-R5): make the load at scheduler.h:650 seq_cst.
- C2 (LPH-R6): handle `std::bad_alloc` from `arrivals.push_back` by the documented policy.
- C3: the logger repins the scheduler to the commit that lands on scheduler main with L1, L2 and C1.
  4738a05 is on the branch only. Rerun the logger's TSan job and the transcript at that pin.
- C4 (LPH-R7): add the post() sleep-race seam test, or reword the pre-sleep ingest's role in the docs.
  Add a test that `system_at(steady_now())` stays within a few microseconds of `system_clock` and that
  `steady_now()` stays within a `steady_clock` bracket.
- C5: the README's performance section and K1's numbers are to be updated and measured
  under an exclusive timing hold. This review ran no benchmark and checks none of the cost claims (76 ns, 57 ns).
- Re-check: rerun P1, P2 and P3 and the three mutants against the fix commits, citing
  file:line.

## Re-check

- Date: 2026-10-31. Scheduler `perf/scheduler-producer` at b0b1920, logger
  `perf/logger-producer` at e86cc5e (pin b0b1920, CMakeLists.txt:16; an uncommitted edit to
  ARCHITECTURE.md's cost numbers was not read as part of this). Homebrew clang 23.1.4 on the Apple M4 Pro,
  every build and run under a light hold. Probes P1-P3 unchanged (P2 already
  defined `SCHEDULER_PUSH_HOOK()`, which is now the header's own seam, scheduler.h:59-63, :668); new
  probes P6 (now `scheduler:test/post.cc` `peep_sleep_stale`) and P7 (probe not kept); the mutants are
  named where they are used.
- Not run: benchmarks; ASan; Linux, FreeBSD, x86-64; the logger under TSan and its transcript test at the pin
  (the logger's clock, producer and order tests ran in a Release -O2 build); `race_once`; anything of
  C3 beyond confirming the fetch resolves to b0b1920 (`_deps/scheduler-src` at b0b1920 in the logger build).

**LPH-R1: CLOSED.** The worker ends with `ingest(true); fire_due();` after the loop (scheduler.h:578-579),
which every exit reaches; the nothing-pending exit still closes first (:517). A held poster is refused
(`stopping`) or its task is filed and run if due; nothing stays on the stack.
- P1: `finish(1)` and `finish(0)` both print `post()=scheduled, fired=1, task freed=yes` (was `fired=0, task
  freed=NO` for `finish(0)`), plain and TSan.
- P2: `far task pending: finish(1) joined=yes, post()=stopping, fired=0, task freed=yes` in 3 of 3 plain runs and
  under TSan (was `scheduled ... freed=NO`). The same probe on 4738a05 plus the hook still prints the stranded
  line 3 of 3, so the probe is live.
- Tests (post.cc:443-526). Mutants of b0b1920 by pattern: `no_close` (both `ingest(true)` deleted) fails
  `finish_exit_none` ("a task post() accepted never ran (and is still held)"), `finish_exit_countdown` (same) and
  `finish_exit_zero` (CHECK at :471), 3 of 3; deleting only the post-loop call fails countdown and zero and passes
  none (the nothing-pending close covers it); deleting only the nothing-pending call passes all three (the
  post-loop close covers it). `finish_race` passes `no_close` 3 of 3 (about 2 million accepted tasks per run), as
  the docs now say. (The first batch built `no_close` from a pattern that missed the post-loop line; the table
  above is from the rebuilt mutant.)
- The old-logic claim holds: 4738a05 plus `SCHEDULER_PUSH_HOOK()` after the `stopping` check passes
  `finish_exit_none` and fails `finish_exit_countdown` (abort), `finish_exit_zero` (abort) and `dtor_posts` (exit
  1, "a cancelled task's destructor that posts hung it").
- A task the last `ingest(true)` files that is not due is released with the wheel, not run; ARCHITECTURE.md:173-179
  and the `post()` comment (scheduler.h:623-632) say so.

**LPH-R2: CLOSED.** By reading, between `lk.lock()` (:529) and `lk.unlock()` (:563) the worker runs only atomic
stores and loads, `has_posted()` (:544), `peep()`, a read of `arrivals.front()->wakeup_time`, CAS loops and
`wait_until`. `peep()` is `noexcept` and returns a copy of a reference the wheel also holds, so dropping `late`
cannot run a task destructor. `ingest()` runs at :479 (top, lock released at :469), :517 (lock not held), :568
(after :563) and :578; the new `bad_alloc` handling (:359-371) is inside `ingest()`. P3: `no deadlock: fired=2`,
plain and TSan (4738a05: `worker stuck ... self-deadlock on mtx`). `dtor_posts` passes, and
fails (exit 1) on a mutant that puts `ingest()` back under the lock.

**LPH-R3: CLOSED** (nits below). The wording is true. P4 on b0b1920, 3 of 3 plain and TSan: `fired: W(+3.7ms)
Y(+7.1ms) X(+7.1ms)`: the late X waits for the head Y and the wheel task W due between them passes it, which is
what scheduler.h:643-654, ARCHITECTURE.md:152-157, AGENTS.md:133-136 and the logger's AGENTS.md (the "Across
threads" sentences of the ordered-post invariant) and ARCHITECTURE.md (step 5) now say. Their guarantee (lines
whose logging is ordered, one push before the other's clock read, and due in that order, are written in that
order) is the one the review's proof gives, and so is "by up to that gap". `ordered_posters` (post.cc:586) is live
for the contract it pins: it fails on a mutant that files the stack newest first (`task 1 (pushed before task 2
read its clock, due no later) fired after it`, 2 of 2) and passes the `no_filing_tick` mutant, which `mixed`
catches (2 of 2).

**LPH-R4: CLOSED.** logger.h:583-593 loads `completed_` (acquire) first. A line's stripe increment (logger.cc:922)
is sequenced before its push (:925), the LOG thread's take acquires every push, and the release add of
`completed_` (:751) follows the take, so every line counted in `done` has its increment visible to the relaxed
stripe loads that follow, and a refusal's decrement (:930) cannot be seen without its increment. The sum cannot
fall below `done`; the clamp is unreachable (it may stay). `logger_producer_test 3` (Release): counters and exactly
once pass.

**LPH-R5: CLOSED** by reading: scheduler.h:687 loads `atom_next_wakeup_time` seq_cst.

**LPH-R6: CLOSED.** scheduler.h:359-371: the `push_back` is in a `try`, and a failure takes the refused-insert
policy (a due task runs, any other is dropped) and goes on; a failed `deque::push_back` leaves `task` intact. P7
makes the global `operator new` throw once for the deque's first 4096-byte block, which the worker requests
(`injected on worker=1`): due task `a ran=yes, worker alive=yes`; task due 100 ms out `a ran=no, worker
alive=yes`. On 4738a05 the same probe prints `worker died` for both.

**LPH-R7: PARTIAL.**
- Finish tests: they fail on the mutants now (R1). `test/clock.cc` (registered, CMakeLists.txt:73-75) passes in
  the logger build at the pin, twice: 91.8 million readings from 4 threads, `steady_now()` always inside its
  `steady_clock` bracket, `system_at()` at most 3000 ns outside its `system_clock` bracket (slack 100 us).
- `peep_sleep` (post.cc:560) exists and passes, but it cannot fail on what the review doubted. The pre-sleep read
  of `posted` (`if (!has_posted())`, scheduler.h:544) is not only an optimisation. P6: the worker has woken by
  timeout (its local copy of the published target equals the published one, now in the past), a task due now is
  posted from the `after_peep` hook, push() has nothing to lower and sees `sleeping == false`, so it does not
  signal; the worker's CAS then raises the target to now + 30 s and goes to sleep. With the read, the task runs
  `1 us` later (3 of 3 plain, 1 under TSan; once on 4738a05). With the read deleted (`no_has_posted`): `Y ... did NOT run
  within 5 s <-- slept past it`, 2 of 2. `peep_sleep` and the whole of post.cc pass that mutant (3 of 3 and 1 of
  1): in `peep_sleep` the preceding "wake" post lowers the published target, the worker's CAS fails and never
  raises it, so push()'s lowering alone carries the test. ARCHITECTURE.md:139-146 states the Dekker pair
  correctly, but :145 ("a worker not yet asleep sees the task due even without the pair") is true only when the
  poster has something to lower.
- To close: add P6's shape as a test (wake the worker by timeout, post from the hook on the next pass, expect the
  task within a second; it must fail on `no_has_posted`), and reword :145.

**LPH-R10 (new; medium for the test suite, low for the product). `producers` fails under TSan on b0b1920 and
passes on 4738a05.** `post_tsan producers` (macOS arm64, TSan -O1, host load about 7): b0b1920 hit the test's 30 s
wait (post.cc:370) in 6 of 7 runs, always with one core busy (user time 30 s); 4738a05 plus the hook passed 7 of
7 (1.4-3.4 s in the three timed runs, under 8 s in the other four); plain -O2 passes in 0.1-0.4 s. Stack samples
of three slow runs (b0b1920 twice, the no-pre-sleep-read mutant once) put all but two of about 1 500-1 700 worker
samples in `ingest()` -> `scheduler_queue.add` (scheduler.h:372) -> `StashValues::put` -> the chain walk in
`Stash::Data::get` (stash.h:500): the worker files a backlog of overdue `post()` tasks into the wheel's floor
slot, a chain an insert walks from its head, which is quadratic. That cost is the one ARCHITECTURE.md describes for
a slot with thousands of tasks. The new code does not add it; it makes the backlog reachable, because filing no
longer happens under `mtx` (the fixed header with `ingest()` put back under the lock passes 4 of 4; with only
the pre-sleep read removed it fails 3 of 4). The test posts 200 000 tasks due within 2 ms from four threads in
about 0.2 s. CI is reported green, so this is host and timing dependent. Either shrink the test under TSan or
spread its due times (that is a test change), or decide that `post()` of overdue tasks must not walk a chain
(an owner decision). The review's own TSan run of post.cc passed (9.8 s) on 4738a05.

**LPH-R11 (new; low; documentation).** `test_finish_exits` (AGENTS.md:120, ARCHITECTURE.md:179) is not a test
name: the tests are `test_finish_exit_nothing_pending`, `_countdown` and `_zero` (`finish_exit_none`,
`finish_exit_countdown`, `finish_exit_zero`). The comment about `SCHEDULER_TEST_HOOK` (scheduler.h:55-58) now sits
above `SCHEDULER_PUSH_HOOK`. docs/API.md:32-36 omits that wheel tasks due between the two pass a late arrival (the
header, ARCHITECTURE.md and AGENTS.md say it).

Verdict of the re-check: R1, R2, R3, R4, R5 and R6 are closed; R7 is partial (the P6 test and the one-line
doc fix remain); R10 should be decided before the scheduler lands.
