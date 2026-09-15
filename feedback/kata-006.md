# Kata 006 — Mock Review

**Domain:** Payment Idempotency Service (create payment by idempotency key, conflict detection on mismatched retries, concurrent duplicate submissions, Postgres/multi-instance design, key expiry with testable time, retry safety, zero-downtime schema migration)
**Stages completed:** 4 (Stage 4 was discussion-only: Postgres schema, unique-constraint-as-mutex, isolation level, key expiry/testable clock, retry semantics, expand/contract migration)

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 3 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 3 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 4 |
| 10 | Ability to evolve the design | 4 |
| 11 | Concurrency reasoning | 3 |
| 12 | Performance awareness | 3 |
| 13 | Production/backend judgement | 4 |
| 14 | Time management | 4 |

## A. Assessment: BORDERLINE (leaning PASS)

## B. Three strongest things
- Precise, improved isolation-level and idempotency reasoning at the DB layer: correctly identified the unique constraint as the actual correctness mechanism (not the isolation level), and justified Read Committed as sufficient specifically because the insert itself serializes conflicting writers. This directly resolves the isolation-level vocabulary gap flagged after kata-005.
- Reached for a testable clock/interface boundary unprompted when asked how to test 24h key expiry without sleeping — also directly resolves a kata-005 gap (deferred that round for lack of injectable time).
- Well-constructed concurrency test: `threading.Barrier` + `ThreadPoolExecutor` to force 10 threads to race on the same idempotency key simultaneously, asserting exactly one payment_id wins — a real proof of thread safety, not just an assertion of it.

## C. Three biggest risks for the real interview
- **New pattern: avoided a direct answer when pressed on an unmet requirement.** Asked three times, with increasing specificity, whether `get_payment` still serialized behind the same global lock as `create_payment` (the exact thing Stage 3 asked to avoid) — first pivoted to a hypothetical future fix, then to "I prefer to be safe" without engaging the actual question, then answered "yes it's satisfied" when traced through concretely, which was incorrect (it still serializes). In a real interview this reads worse than admitting the gap directly.
- **Declared "stage complete" without closing the loop on a stated requirement.** Stage 3 had two explicit parts; part 1 (duplicate-key race) was solved and proven with a test, part 2 (no serialization for unrelated operations) was never actually addressed in code, only asserted as satisfied under questioning.
- **Premature, unused locking infrastructure resurfaced.** A per-payment `lock` field was added in Stage 1 "to be prepared for concurrency" and sat completely unused through all 3 coding stages — the same instinct that was a *strength* in kata-005 (correctly removing an over-broad redundant lock) shows up here as the opposite failure mode: adding lock infrastructure ahead of any stated need, then not using it when the real need arrived.

## D. Bugs or correctness problems
- `get_payment` acquires `self._lock`, the same lock used by `create_payment`'s check-and-insert — all reads and writes serialize through one lock regardless of which payment_id is involved. Not a crash bug, but an explicitly unmet requirement.
- No other correctness issues found. `create_payment`'s check-and-insert is correctly atomic under the lock, and the post-lock `check_amount_and_currency` call is safe because `Payment.amount`/`currency` are never mutated after construction — reading them outside the lock does not introduce a real race.

## E. Unnecessary abstractions / overengineering
- `Payment.lock` (added Stage 1, unused through Stage 3) — acknowledged as removable the moment it was asked about directly, but was never revisited unprompted across three stage transitions.

## F. Missing or low-value tests
- `get_payment` invalid-input tests: explicitly and transparently skipped as low marginal value given time — a reasonable call.
- No test demonstrating that unrelated `get_payment`/`create_payment` calls don't block each other. This is exactly the test that would have surfaced the Stage 3 gap during coding rather than in the technical conversation.

## G. Better concurrency approaches
- Since `Payment` is effectively immutable after construction, `get_payment` does not need `self._lock` at all — `self._payments_by_payment_id.get(payment_id)` is safe as a single dict read under the GIL. The lock is only structurally required around the check-and-insert in `create_payment`.

## H. Performance issues
- As implemented, every read funnels through the same lock as every write, even for completely unrelated payment IDs — under read-heavy traffic (e.g. clients polling payment status) this is an avoidable bottleneck, and it's the exact scenario Stage 3 was testing for.

## I. What a stronger candidate might have done differently
Would have said "no, not yet" the first time asked whether `get_payment` satisfied the Stage 3 requirement, then either fixed it live (dropping the lock, given `Payment`'s post-construction immutability) or explicitly scoped it as a named follow-up — rather than pivoting through two indirect answers before landing on an incorrect "yes."

## J. Practice priorities before next kata
- Per [[coaching-drill-vs-mock-evidence]]: isolation-level vocabulary and testable-clock injection (both flagged after kata-005, both drilled in the 2026-09-15 coaching session) were clean and unprompted this mock — real mock evidence, ready to move to RESOLVED in the next coaching session.
- **New — commit to a direct answer under pressure.** When asked whether an implementation meets a stated requirement, answer yes/no/not-yet first, then justify — practice sitting with "not yet, here's the gap" instead of pivoting to a hypothetical fix or restating intent.
- **Recurring in a new form — re-examine locks/abstractions at the end of each stage, not just when asked.** The unused per-payment lock would have been a good thing to flag unprompted while reviewing the diff, the same way `quota` validation was added unprompted in kata-005. See [[weak-areas-backend-concurrency]].

## K. A better implementation approach (post-mock)
Drop `self._lock` from around the body of `get_payment` — replace with a direct `self._payments_by_payment_id.get(payment_id)`, raising `PaymentNotFound` if `None`. This closes the Stage 3 gap with a one-line change, since correctness here comes from `Payment`'s post-construction immutability, not the lock. Remove the unused `Payment.lock` field. If write-side contention among concurrent creates for *different* idempotency keys ever became a real bottleneck at scale, striped/sharded locks over the two dicts would be the next step — not needed here, but worth naming if pushed on scaling further.
