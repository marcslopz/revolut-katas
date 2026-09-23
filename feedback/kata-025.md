# Kata 025 — Mock Review

**Domain:** Promo Code Redemption Service (create/redeem with max-redemption cap and per-user uniqueness → expiration/testable clock → concurrent redemption race + lock-creation race discussion) + technical discussion (check-priority bug, idempotency, Postgres unique constraint, scale/data-structure trade-offs, monitoring)
**Stages completed:** 3 coding stages + Stage 4 (discussion: scale/data-structure trade-offs at 10M redemptions) + full technical discussion

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 3 |
| 3 | Python fluency | 5 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 5 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 4 |
| 10 | Ability to evolve the design | 4 |
| 11 | Concurrency reasoning | 5 |
| 12 | Performance awareness | 3 |
| 13 | Production/backend judgement | 5 |
| 14 | Time management | 4 |

## A. Assessment: PASS

## B. Three strongest things
- **The kata-024 "explicit requirement skipped until challenged" gap did not recur — resolved in exactly one kata.** The concurrency test was delivered proactively this time, without being asked, and correctly targeted the actual hot path (`redeem_promo_code` racing near the cap), not a secondary path.
- **Clean, unprompted handling of a new concurrency subtlety on the first attempt.** When asked how a per-promo-code lock would work, immediately identified the classic "lazy lock creation" race and avoided it by creating the lock inside `Promo` at construction time (itself guarded by the existing dict lock) — no hints needed, no probing required.
- **Consistently strong production/backend instincts, now a demonstrated pattern rather than a one-off.** Correct unique-constraint schema (`(promo_code, user_id)`) for the Postgres design, a second consecutive correct idempotency-key self-diagnosis (first seen in kata-024's `assign_next_ticket`, now here for `redeem_promo_code`), and concrete, non-generic monitoring ideas (brute-force redemption-rate alerting, "expired with zero redemptions" as an anomaly signal).

## C. Three biggest risks for the real interview
- **Bloom filter recall/application failure — time-critical given the interview is tomorrow (2026-09-24).** When asked for a structure that keeps a membership check cheap in memory without storing every ID exactly, correctly *described* the concept (probabilistic check, memory savings, false positives) but could not name it, and after a push, mischaracterized it as a "dict or hash table" — which has neither property. This is the first real-scenario test of the kata-020-bloomfilter drill from 2026-09-21 (added specifically because a Revolut recruiter flagged this topic), and the drill has not generalized to a novel application. This needs a fast, targeted recall pass before the interview, not another full applied kata.
- **A real bug in check ordering shipped through all three implementation stages, undetected.** `Promo.redeem` checks `max_redemptions` and "already redeemed" before checking expiration — so a promo that is both expired and at capacity reports the wrong reason. No test ever exercised both conditions at once; it only surfaced when asked directly in the technical conversation, and (appropriately, since this was post-`CODING COMPLETE`) was diagnosed correctly but not fixed in code.
- **A data-structure complexity claim was initially wrong and took two direct pushes to fully correct.** First said set insertion is "slower" for a huge set with no complexity given: pushed once, answered "O(n)"; pushed again, landed on the fully correct answer (amortized O(1), occasional O(n) rehash, plus a correct added point about cache locality at scale). Same shape as the kata-005 isolation-vocabulary-under-pressure gap that later fully resolved — one data point, worth a light watch rather than urgent drilling.

## D. Bugs or correctness problems
- `Promo.redeem` check ordering: `max_redemptions` → already-redeemed → expiration. Should be expiration-first (or at least before the other two), since an expired code should never be redeemable regardless of remaining capacity or redemption history. Self-diagnosed correctly and immediately when asked directly; not fixed in code (raised post-`CODING COMPLETE`).
- No other functional bugs found — redemption-cap enforcement, per-user uniqueness, expiration logic, and the concurrent-redemption race were all correctly implemented and verified by tests.

## E. Unnecessary abstractions / overengineering
- None. The design stayed minimal throughout — notably, using a single `set[uuid.UUID]` to serve double duty as both the redemption count and the per-user uniqueness check is an elegant, non-redundant choice given the stated invariants.

## F. Missing or low-value tests
- No test exercises a promo that is simultaneously expired and at `max_redemptions` — would have caught the check-ordering bug in D directly.
- Self-disclosed and accepted trade-off: input-validation tests (type/range checks) were skipped in favor of `ServiceException` coverage, called out proactively rather than hidden.

## G. Better concurrency/design approaches
- The single service-wide lock is defensible for simplicity, but — per the candidate's own correct reasoning in the discussion — a per-promo-code lock (created at `Promo.__post_init__`, guarded during creation by the existing dict lock) would reduce contention across unrelated promo codes with no cross-structure coupling to worry about (unlike kata-024's priority-queue case). The reasoning was already right; worth actually implementing it next time a similar shape comes up.

## H. Performance issues
- Storing every redeemed `user_id` in a set costs O(n) memory for high-volume promo codes (correctly self-diagnosed for a 10M-redemption scenario). A Bloom filter (or another bounded/probabilistic structure) trades a small false-positive rate for bounded memory — exactly the mitigation the candidate could describe but not name (see C).

## I. What a strong candidate might have done differently
- Added a test combining "expired" and "at max redemptions" to catch the check-ordering bug before it shipped.
- Named "Bloom filter" directly and unprompted, given the concept was described correctly and the topic was specifically and recently drilled for this exact interview.
- Actually implemented the per-promo lock, since the reasoning for preferring it over a single service lock was already correct and clearly articulated.

## J. Practice priorities before the interview (2026-09-24)
- **Highest priority, time-boxed: a fast Bloom filter recall drill** — name, one-line definition (probabilistic set membership, no false negatives, tunable false positives, O(1) bounded memory per element regardless of set size), and the "when to use it" trigger phrase ("cheap membership check at scale, false positives acceptable"). Given time is short before the interview, a flashcard-style recall pass is likely higher-value right now than another applied kata.
- **Standing reflex, reconfirmed from kata-024:** before finishing a stage, check for boundary/interaction cases between the invariants just implemented (here: two rejection conditions overlapping) and add one test for it.
- Concurrency reasoning, idempotency design, and production judgement are all consistently strong across the last two katas — no further drilling needed there before tomorrow.

## K. A better implementation approach (post-mock)
- Reorder `Promo.redeem`'s checks to test expiration first.
- Replace the single `PromoRedemptionService._lock` with a per-`Promo` lock created in `__post_init__`, using the service-level dict lock only to guard dict insert/lookup — exactly as reasoned through in the discussion.
- For the viral-promo scale problem: back the "already redeemed" check with a Bloom filter for a fast, memory-bounded pre-check, falling back to (or backed by) an exact source of truth (e.g. the Postgres unique constraint) as the final authority — bounding memory while keeping the invariant enforced exactly where it matters.
