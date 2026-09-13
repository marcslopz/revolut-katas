# Kata 001 — Mock Review

**Domain:** Merchant Quota Service (register merchant, charge merchant against a cap, query usage)
**Stages completed:** 4 (Stage 4 included both an implementation change — splitting the global lock into repo + per-merchant locks — and discussion: DB schema, isolation level, deadlocks, distributed locking, deployment)

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 5 |
| 7 | Code quality | 3 |
| 8 | Naming / readability | 3 |
| 9 | Test quality | 3 |
| 10 | Ability to evolve the design | 5 |
| 11 | Concurrency reasoning | 4 |
| 12 | Performance awareness | 4 |
| 13 | Production/backend judgement | 4 |
| 14 | Time management | 4 |

## A. Assessment: BORDERLINE

## B. Three strongest things
- Evolving the design without breaking it: refactored tests to use the public API instead of hand-built dicts, and — when challenged — correctly diagnosed that holding `_repo_lock` for the whole `charge_merchant` call defeated the point of the lock split just designed, then fixed it live.
- Recognized premature optimization: when pushed toward "lock inside a lock" for a delete operation that doesn't exist, self-corrected with "if there's no deletion... it's a pre-optimization" instead of building speculative machinery.
- Strong system-design conversation: idempotency and concurrency combined correctly (dedupe check inside the merchant lock), reasonable DB schema, defensible isolation-level choice with justification, and a concrete canary/rollback deployment plan.

## C. Three biggest risks for the real interview
- The first concurrency implementation was not thread-safe at all, and it shipped past two stages unnoticed: `with threading.Lock():` inside the method body creates a *new* lock object on every call, so every thread got its own lock — zero mutual exclusion from Stage 1 through Stage 2, only caught once Stage 3 explicitly demanded a concurrency test.
- A real correctness bug slipped through uncaught: `_is_amount_exceeded` uses `>=` instead of `>`, so a charge that brings the total to *exactly* the cap is rejected — contradicting the candidate's own stated rule ("does not exceed the quota" should allow equality). No test exercised this boundary.
- The deadlock-prevention answer didn't converge on the standard fix: reached for "lock the whole table" (which reintroduces the serialization problem just eliminated) rather than lock ordering (e.g., always lock merchant IDs in a fixed order), even after two follow-up nudges.

## D. Bugs / correctness problems
- `_is_amount_exceeded`: `>=` should be `>`. A charge equal to the remaining quota is currently rejected.
- Stage 1–2 locking (`with threading.Lock():` inside the method body) provided no actual synchronization — a new lock per call is a no-op for mutual exclusion across threads. Fixed once Stage 3 made it an explicit requirement.

## E. Unnecessary abstractions / overengineering
None of note. One structural smell rather than overengineering: `_merchant_locks` is a second dict kept in sync with `merchants_repository` by convention rather than by construction — nothing guarantees a merchant entry and its lock always exist together except careful method-by-method discipline.

## F. Missing or low-value tests
- No boundary test for a charge that lands exactly on the cap (would have caught the `>=` bug).
- `from unittest import mock` imported in `test.py` but never used.
- `test_register_already_existing_merchant` still hand-builds `{"merchant_1": {}}` instead of using `register_merchant`, inconsistent with how the other tests were cleaned up.
- No test for the race between `register_merchant` and `charge_merchant` on the same ID (not currently possible since `register_merchant` holds `_repo_lock` for its whole body, but untested).

## G. Better concurrency approaches
The coarse repo lock + fine-grained per-merchant lock split is the right shape once corrected. Next step: move the lock onto the merchant entity itself (e.g., a `Merchant` object owning its own `threading.Lock()`) instead of a parallel `_merchant_locks` dict, so "a merchant and its lock always exist together" is a structural guarantee rather than a convention maintained by hand across three methods. For the transfer/deadlock scenario, lock acquisition should follow a total order over merchant IDs (e.g., always lock the lexicographically smaller ID first), not a table-wide lock.

## H. Performance issues
Nothing outstanding at this scale. The cumulative-counter-over-recompute decision was reasoned and justified well upfront (avoids scanning all charges on every check). The final repo-lock/merchant-lock split is the correct scalability move once the "holding both for the whole operation" issue was fixed.

## I. What a stronger candidate might have done differently
Treated thread-safety as a default concern for shared mutable state from Stage 1, rather than only after an explicit concurrency prompt — a merchant-charging domain should trigger that instinct unaided. Would have written the exact-boundary test as soon as the requirement said "does not exceed," since that phrasing is a direct signal for an off-by-one risk. Would have converged faster on lock-ordering as the deadlock fix rather than table-locking.

## J. Practice priorities before next kata
- Concurrency-first instincts: whenever shared mutable state (a dict, a counter, a running total) is introduced, ask immediately whether concurrent callers can corrupt it — don't wait for the interviewer to say "now make it thread-safe."
- Deadlock prevention patterns: lock ordering, try-lock-with-timeout-and-retry, and locking-granularity trade-offs — the standard answer wasn't ready when probed.
- Boundary-condition test discipline: for any comparison involving a cap/limit/threshold, write the exact-boundary test as a reflex.

## K. A better implementation approach (post-mock)
Encapsulate each merchant's lock on the merchant entity itself (e.g., a `Merchant` dataclass with its own `lock`, `cap`, `accumulated_charges`, `charges`), so `ChargeMerchantService` only needs one coarse `_repo_lock` for registration/lookup and never has to keep a second locks-dict in sync. Extract the repeated merchant_id/amount/cap validation guard clauses (currently duplicated across `charge_merchant`, `register_merchant`, and `get_cap_amount`) into shared helpers. Fix the cap comparison to `>` per the stated requirement.
