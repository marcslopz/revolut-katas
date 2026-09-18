# Kata 010 — Mock Review

**Domain:** Subscription Service (create/cancel subscription, one-active-subscription-per-user invariant, concurrent creates/cancels, PostgreSQL schema/locking/idempotency/migration discussion)
**Stages completed:** 3 coding stages (core lifecycle → one-active-subscription invariant → concurrency) + a live bug found and fixed + full technical discussion

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 5 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 4 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 3 |
| 10 | Ability to evolve the design | 4 |
| 11 | Concurrency reasoning | 4 |
| 12 | Performance awareness | 4 |
| 13 | Production/backend judgement | 5 |
| 14 | Time management | 4 |

## A. Assessment: PASS

## B. Three strongest things
- **Unprompted, precise production/distributed-systems judgment.** A partial unique index (`UNIQUE(user_id, status) WHERE status = 'active'`) for the invariant, the correct idempotency-key + `INSERT ... ON CONFLICT DO NOTHING` + re-read pattern for safe retries, an unprompted transactional-outbox answer for a downstream billing failure, and a textbook add-column → canary → backfill → add-constraint migration — all landed correctly on the first pass.
- **Direct, non-evasive tracing under pressure.** When walked through `cancel_subscription` line by line, correctly identified — unaided, without hedging or pivoting to hypotheticals — that any user with their own active subscription could cancel an unrelated user's subscription, and traced the full blast radius (the victim's subscription gets wrongly cancelled; the victim's bookkeeping entry is left stale, blocking them from creating a new one; the attacker's own entry is wrongly cleared).
- **Concurrency test design uses real proof, not approximation.** `threading.Barrier` + `ThreadPoolExecutor` to force genuine races for both the duplicate-create and create/cancel scenarios, plus correct, unprompted reasoning about lock granularity (service-level lock for index mutations vs. per-subscription lock for status/DTO reads, to avoid serializing unrelated subscriptions).

## C. Three biggest risks for the real interview
- **A real authorization bug reached "stage completed" and passed the full test suite.** The Stage 2 rewrite of `cancel_subscription` replaced an actual ownership comparison with an existence check against `_user_active_subscriptions`, letting any user with an active subscription cancel anyone else's. It was never self-caught — only surfaced because the interviewer asked for a line-by-line trace. In a real 35-minute interview, if that exact question isn't asked, this ships.
- **No regression test was added after the fix.** Same gap as kata-008 and kata-009 — now a 3-for-3 pattern across consecutive mocks. The pre-existing `test_cancel_subscription_different_user_id` still only exercises a subscription_id/user_id pair where the user never created any subscription (existence check passes by accident), not a valid-but-unrelated user with their own active subscription — the exact shape of bug that just occurred, still not covered.
- **A subtle status-visibility race was initially downplayed rather than precisely reasoned through.** Asked whether two subscriptions for the same user could both report `status == active` via `get_subscription` at the same time, the first answer leaned on "eventual consistency" framing before conceding, under a further direct question, that nothing actually synchronizes `subscription.cancel()` (called outside the lock) against a concurrent `create_subscription` completing for the same user. The invariant is correctly enforced in the index, but the public status field can briefly disagree with it — a real risk if any caller (e.g. a billing check) treats `status` as ground truth.

## D. Bugs or correctness problems
- *(Found & fixed live)* `cancel_subscription`'s ownership check compared "does this user_id have any active subscription" instead of "does this user_id own this specific subscription" — fixed by looking up the caller's actual active subscription and comparing owners directly.
- *(Not raised, not fixed)* `self._lock` is released before `subscription.cancel()` runs, so a concurrent `get_subscription` (on the old or the newly-created subscription) can observe both as `active` simultaneously for a brief window.

## E. Unnecessary abstractions / overengineering
- None significant. Both locks (service-level and per-subscription) are actually used and serve distinct, justified purposes — no dead locking infrastructure this time.

## F. Missing or low-value tests
- No regression test for the fixed cross-user cancellation bug.
- `test_cancel_subscription_different_user_id` still doesn't cover a valid-but-unrelated user (a user who has their own active subscription) — only a nonexistent one.
- Minor/cosmetic: `class CancellationDenied(ServiceException): pass` and the next class definition run together with no blank line — not worth drilling, purely a style nit.

## G. Better concurrency/design approaches
- Current design is appropriate for the scope. To close the status-visibility window in D: mutate `subscription.status` to cancelled while still holding `self._lock` (or otherwise tie the two updates together), so the index and the status field can never disagree even briefly.

## H. Performance issues
- None. The per-subscription lock was a deliberate, correctly-reasoned choice over a single global lock to keep unrelated subscriptions' reads/writes concurrent.

## I. What a strong candidate might have done differently
- Added a "cancel by a different, valid user who has their own active subscription" test the moment the ownership check was introduced in Stage 2 — this existence-vs-ownership bug shape is common enough to warrant a reflexive test case, not just a "user doesn't exist" case.
- Given a direct, precise answer to the status-visibility question on the first pass instead of framing it as acceptable eventual consistency before being pushed further.

## J. Practice priorities before next kata
- **Add a regression test as the very next action after any live bug fix during a mock** — now confirmed 3-for-3 (kata-008, kata-009, kata-010). This should move from passive tracking to an active, direct coaching drill.
- **Write a "valid-but-unrelated-party" test case as a reflex whenever an ownership/authorization check is introduced** — recurrence of the kata-007 pattern, now 2-for-2 (kata-007, kata-010).
- Keep a light watch on precision when reasoning about cross-structure consistency windows (status field vs. index) under direct pressure — only one data point so far.

## K. A better implementation approach (post-mock)
- Simplify the ownership check to compare `subscription.user_id != user_uuid` directly instead of round-tripping through `_user_active_subscriptions` twice — same correctness, fewer moving parts.
- Move the `subscription.status = cancelled` mutation inside the same critical section as the `_user_active_subscriptions` update (or otherwise synchronize them) to eliminate the brief active/active visibility window.
- Add a regression test for the cross-user cancellation fix and a "valid-but-unrelated-user" case alongside the existing "nonexistent user" test.
