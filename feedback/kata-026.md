# Kata 026 — Mock Review

**Domain:** Seat-Hold Service for event booking (hold/release specific seats, no partial holds → TTL-based automatic expiration → multi-threaded concurrency with a service-level lock → Postgres/multi-instance schema + locking discussion) + technical discussion (idempotency, scale/hot-row contention, safe schema-change rollout, CQRS, transactional outbox)
**Stages completed:** 4 coding/design stages (Stage 4 as discussion, not implementation) + full technical discussion

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 5 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 3 |
| 10 | Ability to evolve the design | 5 |
| 11 | Concurrency reasoning | 3 |
| 12 | Performance awareness | 3 |
| 13 | Production/backend judgement | 5 |
| 14 | Time management | 4 |

## A. Assessment: PASS

## B. Three strongest things
- **Rich domain entities carried their own invariants (`Seat.hold`/`free`, `Reservation.release`) instead of an anemic dict-manipulation service.** This is what let TTL, then locking, then the Postgres schema all bolt on cleanly across four stages with no restructuring — the strongest "ability to evolve" showing in the series so far.
- **Deterministic, non-flaky concurrency testing.** The Stage 3 concurrency test used a `threading.Barrier` to force all 10 threads to start simultaneously and asserted an exact, reproducible outcome (6 wins / 4 losses) — no `sleep`-based timing games, no flakiness risk.
- **Production judgement in the discussion phase was consistently strong and self-driven.** Idempotency-key design with a DB unique constraint (unprompted follow-through to the DB layer once asked), a transactional outbox for reliable event publishing (recalled and correctly reapplied from prior practice), and a clean expand/migrate/contract rollout plan (dual-write canary → backfill → read-cutover canary → cleanup) for a live schema change — all reasoned through concretely, not name-dropped.

## C. Three biggest risks for the real interview
- **Regression-test-after-live-fix gap is now confirmed 5-for-5 (kata-008, 009, 010, 012, 026), with the interview tomorrow.** The Stage 3 partial-hold rollback bug (no unwind of already-held seats when a later seat in the same request turns out to already be held) was found and fixed live, correctly — but no test was added to lock the fix in. This has never once broken across five separate mocks; it needs to become a hard habit before tomorrow, not another passive watch item.
- **A live, unresolved consistency bug shipped in the final code.** `Reservation.release()` checks the raw, eagerly-stored `status` field, but that field is only ever mutated by an explicit `release()` call — TTL expiry is only reflected lazily, in `get_status_with_ttl()`, a *different* code path. Net effect: a reservation's original owner can call `release_reservation` on it **after** it has expired and its seats have been legitimately re-held by someone else — silently freeing another customer's active hold. This was surfaced via a targeted interviewer question during the concurrency discussion but never revisited or fixed in code. It's the same *shape* of bug as the Stage 3 fix (an invariant enforced in one place but not everywhere it's needed), just not caught the second time it appeared.
- **Needed a prompt twice on concurrency-adjacent reasoning that should be closer to reflexive by now.** First, asked to trace whether a lock-free reader could observe a torn write, the first answer described an unrelated race (a lost update between two concurrent writers) before self-correcting precisely on a more specific follow-up. Second, asked how to handle a burst of 50,000 requests contending for the same physical seats, the first instinct was to "spread" the load via hashing — which doesn't apply, since the seats themselves (not an artificial key) are the scarce, genuinely contended resource; corrected quickly to `SELECT ... FOR UPDATE SKIP LOCKED` once redirected. Both corrections were fast and precise, but the first-response reflex on live concurrency reasoning is the thing this interview actually scores.

## D. Bugs or correctness problems
- `Reservation.release()` trusts the raw `status` field rather than TTL-aware state — an expired-but-unreleased reservation can still be released by its original owner even after its seats were legitimately re-held by a different customer, incorrectly freeing that customer's active hold. Unresolved at end of mock. Fix is small: check `is_expired(now, self.reserved_at)` (or reuse `get_status_with_ttl`) at the top of `release()` and raise a distinct exception if already expired, rather than proceeding.
- (Found and fixed live) Stage 3's original `hold_seats` held no rollback: if seat N of a multi-seat request failed with `SeatAlreadyHeld`, seats 1..N-1 were left held with no reservation ever created for them, violating the stated "no partial holds" requirement. Correctly fixed with a `try`/`except` unwind — but with no regression test (see C).
- Minor: the fix's `except SeatAlreadyHeld: ... raise SeatAlreadyHeld` re-raises a bare exception, discarding the `customer_id` argument the original raise carried.

## E. Unnecessary abstractions / overengineering
- None. Scope stayed tight throughout — correctly declined to add a confirm/purchase endpoint, per-hold configurable TTL, or multi-event support when those weren't required, and explicitly named the service-lock choice as a deliberate simplicity trade-off rather than a default.

## F. Missing or low-value tests
- No regression test for the Stage 3 partial-hold rollback fix (see C).
- No test for `UnknownSeatId`.
- No test exercises "release a reservation after its TTL has expired and the seat has been re-held by someone else" — would have caught the D1 bug directly, and is a natural extension of the TTL tests that already exist.
- Concurrency tests cover `hold_seats` only; `release_reservation` under concurrency was explicitly and reasonably skipped to save time ("would be the same").

## G. Better concurrency/design approaches
- The single service-wide lock, applied to both reads and writes, was a deliberate and well-justified simplicity choice for this scope — correctly identified by the candidate as a performance/simplicity trade-off before writing any code.
- For Stage 4's Postgres design: `SELECT ... FOR UPDATE` with rows locked in `seat_id` order (deadlock avoidance) and pessimistic locking justified by expected high contention were both solid, unprompted choices. `SKIP LOCKED` for fail-fast under hot-row contention was correct once reached, though it took a redirect to get there (see C).

## H. Performance issues
- The single lock serializes all reads and writes, including read-only status queries — reasonable at kata scale; flagged correctly by the candidate as something that would need finer granularity in production.
- For the 50k-request burst scenario, the candidate didn't proactively raise connection pooling, a request-level rate limiter/waiting-room pattern, or read replicas for status queries — only `SKIP LOCKED` was reached, and only after correction on the hot-row point.

## I. What a strong candidate might have done differently
- Applied the same "does this check reflect TTL-expiry, not just the stored flag" scrutiny to `release()` that was just applied to fixing the rollback bug — the two are the same defect family, one path apart.
- Written the regression test for the rollback fix as part of the same edit, not skipped — especially valuable here since the fix touches exception-safety/rollback logic, exactly the kind of thing that regresses silently.
- On the scale question, named the actual scarce resource (the seat) before reaching for a generic scaling technique (hashing/sharding).

## J. Practice priorities before the interview (2026-09-24)
- **Highest priority: make "write the regression test in the same breath as the fix" an unconditional reflex, not a judgment call.** This is the single most repeated, most mechanical gap across the entire series (5-for-5, unbroken since kata-008) and is the cheapest one to close — there is no conceptual gap here, only a habit gap.
- **Standing reflex for any TTL/lazy-expiry design: audit every code path that reads or mutates the "real" state field, not just the one path (`get_status_with_ttl`) that already handles staleness correctly.** This exact shape has now cost a live bug once (kata-026) after already being fixed once elsewhere in the same file.
- Before proposing a scaling fix, first identify whether the bottleneck is a genuinely scarce, contended resource (irreducible) or an artificial hotspot (fixable by resharding/hashing) — one data point so far, worth a light watch.

## K. A better implementation approach (post-mock)
- `Reservation.release()`: check expiry first (`if is_expired(now, self.reserved_at): raise ReservationExpired(...)`, reusing the existing `is_expired` helper) before checking `status == LOCKED`, so an expired reservation can never be used to free seats it no longer legitimately owns.
- Add a test that holds a seat, advances time past TTL, lets a second customer re-hold the same seat, then asserts the first customer's `release_reservation` call raises rather than silently freeing the second customer's hold.
- Add a `test_hold_seats_rolls_back_on_partial_failure` asserting that after a failed multi-seat `hold_seats` call, every seat in the request (including the ones that succeeded before the failure) is back to `FREE`.
