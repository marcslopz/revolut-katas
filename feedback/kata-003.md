# Kata 003 — Mock Review

**Domain:** Coupon Redemption Service (create coupon, redeem by code, per-customer limits, redemption info)
**Stages completed:** 4 (Stage 4 was discussion-only: Postgres schema, locking, isolation level, idempotency, rollout sequencing, backpressure)

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 2 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 3 (unreliable — session had multiple real-life pauses, no clock tracked) |
| 5 | Correctness | 4 |
| 6 | Simplicity | 5 |
| 7 | Code quality | 4 |
| 8 | Naming / readability | 4 |
| 9 | Test quality | 4 |
| 10 | Ability to evolve the design | 5 |
| 11 | Concurrency reasoning | 5 |
| 12 | Performance awareness | 3 |
| 13 | Production/backend judgement | 4 |
| 14 | Time management | 3 (not meaningfully measurable this run) |

## A. Assessment: PASS

## B. Three strongest things
- Concurrency correctness was right from Stage 1 and needed zero changes through Stages 2–3: the per-coupon lock protected both the overall cap and, once added, the per-customer cap, and both were proven with real barrier-synchronized thread tests (not just "run it a few times and hope").
- Excellent verbal reasoning under pushback: framed the mutable-shared-object question in terms of DB isolation levels, correctly sequenced an expand-only zero-downtime migration, and explicitly recognized that historical idempotency keys could never be backfilled — a subtle, easy-to-miss point.
- Clean incremental design across three coding stages with no rewrites — the Stage 1 lock and model absorbed the Stage 2 per-customer rule and the Stage 3 concurrency proof without restructuring.

## C. Three biggest risks for the real interview
- Near-zero unprompted clarifying questions (only one was asked, about error signaling) — this is the same weakness flagged in kata-002. Ambiguous points (customer_id shape/type, case-sensitivity of coupon codes) were resolved by silent assumption rather than asked upfront.
- Real design gaps were only caught when the interviewer explicitly pushed: the customer table's primary key was wrong until challenged, and the DLQ/202 answer ignored that `redeem` is a synchronous, customer-facing call until challenged. In a real interview the interviewer will not always probe every answer.
- No validation on `customer_id` anywhere in the code — an unhashable value would raise a raw `TypeError` deep inside a dict operation instead of a controlled domain exception, unlike every other input in the module.

## D. Bugs / correctness problems
- `redeem_coupon` / `Coupon.redeem` never validate `customer_id`. Passing a non-hashable type (e.g. a list) raises an unhandled `TypeError: unhashable type` instead of a domain exception — inconsistent with `validate_coupon_code`/`validate_max_redemptions` being applied everywhere else.
- `raise MaxRedemptionsReached` and `raise MaxRedemptionsReachedByCustomer` are raised with no arguments, unlike every other exception in the file (`CouponCodeNotFound(coupon_code)`, `AlreadyExistingCouponCode(coupon_code)`, etc.) — makes the specific coupon/customer involved unavailable to logs/callers.
- `get_coupon()` returns the live, mutable `Coupon` object — including its internal `threading.Lock` — directly to the caller. Any caller can mutate `current_redemptions` or acquire/release the lock directly, bypassing the exact invariant Stage 3 exists to protect. Correctly diagnosed verbally (repeatable-read analogy) but never fixed in code.

## E. Unnecessary abstractions / overengineering
None — same clean minimalism as kata-002. No premature abstractions across any of the three coding stages.

## F. Missing or low-value tests
- No test for an invalid/non-hashable `customer_id` on `redeem_coupon`.
- No test for an invalid `max_redemptions_by_customer` value (the parametrized invalid-input test only covers `max_redemptions`).
- Nothing exercises the mutability leak from `get_coupon()` — a test mutating the returned object and observing state corruption would have surfaced the D-3 bug directly.
- No concurrent test for `create_coupon` (two threads racing to create the same code) — asymmetric with the thoroughness applied to `redeem_coupon`.

## G. Better concurrency approaches
None needed. The two-level lock (coarse lock on the coupon dict, fine-grained lock per `Coupon`) is the right shape at this scale, and the live reasoning about lock ordering, granularity, and deadlock-freedom held up under direct questioning.

## H. Performance issues
- `current_redemptions_by_customer` grows one entry per distinct customer for the coupon's entire lifetime and is never evicted — fine at kata scale, worth flagging for a long-lived, high-traffic coupon.
- A single `threading.Lock` per coupon fully serializes every redemption of that coupon — exactly the flash-sale scenario discussed in Stage 3 — and this scaling limit was never raised proactively, only implicitly touched via the CQRS discussion.

## I. What a stronger candidate might have done differently
- Asked several clarifying questions up front (shape/type of `customer_id`, case-sensitivity of coupon codes, whether the per-customer/overall caps should behave identically on rejection) instead of just one.
- Designed `get_coupon()` to return a read-only snapshot/DTO from the start, rather than leaking the mutable domain object with its lock.
- Caught the composite-PK schema flaw and the sync/async mismatch in the 202/DLQ answer unaided, rather than after being directly challenged on both.

## J. Practice priorities before next kata
- **Recurring (kata-002, kata-003):** ask more requirement-clarifying questions unprompted, even when a requirement feels self-evident.
- Validate every input a method accepts, not just the ones that already have a `validate_*` helper — `customer_id` was skipped entirely this run.
- Before proposing an async/queue-based reliability fix, check it against the actual call shape (synchronous vs. asynchronous) before presenting it as the answer.

## K. A better implementation approach (post-mock)
Add `validate_customer_id` mirroring `validate_coupon_code` and call it in `redeem_coupon`. Replace `get_coupon()`'s return value with a small read-only response object (or a `dataclasses.replace`-based snapshot) so no caller can reach the internal lock or mutate state directly. Pass context into the two bare exceptions (`MaxRedemptionsReached(coupon_code)`, `MaxRedemptionsReachedByCustomer(coupon_code, customer_id)`) for consistency with the rest of the module.
