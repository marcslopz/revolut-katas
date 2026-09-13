# Kata 002 — Mock Review

**Domain:** Warehouse Inventory Service (register product, reserve/release/confirm stock)
**Stages completed:** 4 (Stage 4 was discussion-only: DB schema, locking, isolation level, outbox)

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 3 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 5 |
| 7 | Code quality | 4 |
| 8 | Naming / readability | 4 |
| 9 | Test quality | 4 |
| 10 | Ability to evolve the design | 5 |
| 11 | Concurrency reasoning | 5 |
| 12 | Performance awareness | 3 |
| 13 | Production/backend judgement | 4 |
| 14 | Time management | 5 |

## A. Assessment: PASS

## B. Three strongest things
- Concurrency was treated as a first-class concern from Stage 1, unprompted: per-entity locks, a separate coarse lock for the registry, and matching thread-safety tests for every mutating operation added.
- Strong distributed-systems reasoning once probed: pessimistic row locking, correct isolation-level pick, spotted the deadlock risk from inconsistent lock ordering and fixed it immediately, and landed on the outbox pattern unaided for the dual-write problem.
- No over-engineering. The `Product`/`Reservation` model evolved cleanly across three stages without a rewrite — no premature abstractions, no speculative flexibility.

## C. Three biggest risks for the real interview
- Rarely initiated clarifying questions — most ambiguous calls (zero-quantity registration, negative quantities, double-release/confirm semantics) were resolved by silent assumption rather than asked upfront.
- Tests reach directly into private state (`product_service._products["x"].reservations[id].status`) instead of exercising a public API. Symptom of a real gap: Stage 1 asked for a way to query available stock, and `ProductService` never got a public method for it.
- Built idempotency into `confirm` proactively, but the identical problem on `reserve` only surfaced when walked through the retry scenario explicitly — pattern-matching on a solved case rather than systematically asking "is this endpoint retry-safe?" for every new mutating method.

## D. Bugs / correctness problems
- `ProductService.__init__`: `self._products` is only assigned inside the `if products is None` branch — pass a non-`None` dict and every subsequent call raises `AttributeError`. Found only when prompted.
- `reserve_product_quantity` isn't retry-safe: a timed-out client retry creates a second reservation and double-deducts stock. Diagnosed correctly in discussion, not fixed in code.
- Because `release_quantity` deletes the dict entry, confirming an already-released reservation raises the same `ReservationNotFoundException` as confirming one that never existed — a caller (e.g. a payment processor) can't tell "already handled" from "this is broken."

## E. Unnecessary abstractions / overengineering
None — genuine strength this run.

## F. Missing or low-value tests
- Confirming a nonexistent reservation.
- Confirming a reservation that was already released (the ambiguous-exception case above).
- Concurrent double-confirm (only sequential idempotency was tested, unlike every other operation which got a thread-safety test).
- Nothing exercises a genuine public "get available stock" query — that Stage 1 requirement was never built as a service-level method.

## G. Better concurrency approaches
Nothing structurally wrong — coarse-plus-fine locking is a sound choice at this scale, and the DB-locking answers held up under pushback.

## H. Performance issues
Confirmed reservations are never removed from `Product.reservations` — unbounded growth over a product's lifetime (released ones get cleaned up, confirmed ones don't). Worth noting for a long-lived, high-volume service.

## I. What a stronger candidate might have done differently
Applied the "is this retry-safe?" question to every mutating endpoint the moment idempotency was introduced for `confirm`, instead of only when directed at `reserve`. Also would have closed out Stage 1 with a real `get_available_stock` method rather than letting tests peek at internals.

## J. Practice priorities before next kata
- Ask more clarifying questions unprompted, even when a requirement feels self-evident.
- After adding any new state-changing method, systematically ask whether it needs to be idempotent under retries — don't rely on the interviewer to point at it.
- Keep public API surface complete per stage (don't let tests substitute for a missing query method).

## K. A better implementation approach (post-mock)
Keep released reservations as `RELEASED` status instead of deleting them — gives an audit trail and disambiguates "already released" vs "never existed" for free. Add a client-supplied idempotency key on `reserve`, stored with the reservation, so retries return the existing reservation id instead of creating a new one. Add `get_available_stock(product_id)` on `ProductService` so tests and callers never touch `_products` directly.
