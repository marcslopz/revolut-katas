# Kata 008 — Mock Review

**Domain:** Digital Wallet Service (accounts with deposit/withdraw, transfers between accounts, concurrent transfer safety, idempotent transfers, PostgreSQL schema/locking/scaling discussion)
**Stages completed:** 4 coding stages (core ops → transfers → concurrency → idempotency) + an extra round exploring per-account locking, plus full technical discussion

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 5 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 5 |
| 7 | Code quality | 3 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 2 |
| 10 | Ability to evolve the design | 5 |
| 11 | Concurrency reasoning | 5 |
| 12 | Performance awareness | 4 |
| 13 | Production/backend judgement | 4 |
| 14 | Time management | 5 |

## A. Assessment: PASS

## B. Three strongest things
- **Direct, unhedged answers under repeated cross-examination.** This is the first mock where the previously recurring "evasion under pressure" pattern (2-for-2 in kata-006/007) didn't fire at all — every time asked to trace actual code behavior (the same-account type-mismatch bug, the idempotency-ordering bug, the DB schema critique, the locking-tradeoff critique), the *first* response was a correct, direct diagnosis, not a hedge or hypothetical pivot.
- **Excellent concurrency design judgment.** Proposed account-id lock ordering unprompted to avoid deadlock when moving to per-account locks. Then, when that finer-grained locking was shown to break idempotency correctness (a failed transfer could get silently marked as succeeded on retry), recognized the conflict immediately and chose a well-justified, simpler trade-off (full serialization under the service lock for `transfer_amount`) instead of chasing a more complex fix under time pressure.
- **Strong, largely self-corrected production/DB reasoning.** Converged on unique-constraint-based idempotency for distributed insert races unprompted at the end. Needed only one nudge each to fix a real schema modeling issue (idempotency key misplaced on the `Accounts` table) and to sharpen optimistic-vs-pessimistic reasoning from "throughput" to "contention on the same row" — a gap self-identified as unresolved going into this kata.

## C. Three biggest risks for the real interview
- **A stated, agreed-upon validation requirement was never implemented.** In Stage 1 the candidate confirmed deposit amounts should be positive, but `validate_amount` was left as a no-op (`pass`) through all four stages. Deposits/withdrawals/transfers with negative or zero amounts are silently accepted — a "deposit" of -10 is actually an unvalidated withdrawal. Never caught or flagged at any point in the session.
- **Two real correctness bugs this session were only caught because the interviewer asked a targeted trace question** — neither was self-caught during implementation or by the candidate's own tests, and neither has a regression test protecting the fix now that it's in place.
- **Test suite hygiene issues went unnoticed across all four stages.** A duplicated `test_withdraw_amount` function silently shadows the first definition (the "successful withdraw to zero" case hasn't actually run since Stage 1), and the parametrized invalid-input test's body ignores its own `user_id`/`balance` parameters, so all four "different" cases test the identical scenario. Coverage looks broader than it is.

## D. Bugs or correctness problems
- `validate_amount` never implemented — negative/zero amounts silently accepted everywhere despite the agreed requirement.
- *(Found & fixed live)* Same-account transfer check originally compared a string to a UUID (`account_id_dst == account_uuid_src`), so `SameAccountForTransfer` never fired. Fixed to compare like types.
- *(Found & fixed live, then design reverted)* The per-account-locking refactor recorded the idempotency key **before** the transfer executed. A retry after a genuine failure (e.g. insufficient balance) would hit the idempotency-match branch and silently return success without moving any money. Fixed by moving the transfer execution before the idempotency-key write, both back under the single service lock.
- `test_withdraw_amount` defined twice — pytest only collects the second; the first (successful withdrawal to zero) never runs.
- `test_create_account_with_invalid_input` hardcodes `("user_1", -1)` in its body instead of using the parametrized `user_id`/`balance` — all 4 parametrize cases test the same input.

## E. Unnecessary abstractions / overengineering
- None. Declined to add authorization checks out of scope, declined to prematurely split locks, and cleanly reverted a completed-but-riskier locking optimization once it conflicted with correctness. Consistently good scope judgment throughout.

## F. Missing or low-value tests
- No test for the (fixed) same-account transfer rejection.
- No test asserting a failed transfer doesn't consume/record its idempotency key — exactly the second bug found live this session.
- No test for negative/zero amounts anywhere (ties directly to the unimplemented `validate_amount`).
- The two hygiene bugs above reduce actual coverage well below what the file appears to provide.

## G. Better concurrency/design approaches
- The final design (whole `transfer_amount` under the single service lock) is correct but gives up the per-account granularity built earlier. A cleaner alternative: make the idempotency store an explicit state machine (reserve the key as `PENDING` under the service lock, release it, do the per-account-locked transfer, then flip the entry to `SUCCEEDED`/remove it on failure) — this would preserve fine-grained locking without the ordering hazard.

## H. Performance issues
- Reverting to the coarse lock for `transfer_amount` fully serializes all transfers again, even between unrelated account pairs — the concurrency benefit built earlier only applies to standalone `deposit_amount`/`withdraw_amount` now. Correctly identified and consciously accepted as a trade-off by the candidate, not a miss — but worth remembering as the current bottleneck.

## I. What a strong candidate might have done differently
- Implemented `validate_amount` at the point it was first agreed to be a requirement, rather than leaving the stub for the entire session.
- Added a regression test immediately after fixing each of the two live bugs, before moving on.
- Given a quiet moment, skimmed the test file once for copy-paste mistakes across four stages of scaffolding.

## J. Practice priorities before next kata
- **Follow through on verbally-agreed validation.** A confirmed requirement ("amount should be positive") was stated out loud but never implemented — treat a verbal agreement as a checklist item, not just a talking point.
- **Add a regression test the moment a live bug is fixed**, before moving to the next task — two real bugs were found and fixed this session with zero test coverage protecting either fix.
- **Periodically skim your own test file** for duplicate names and parametrize bodies that don't reference their parameters — cheap to check, expensive to miss (false confidence in coverage).
- The "evasion under pressure" item (recurring since kata-006) can now be considered resolved pending one more confirmation — this is the first session where the *first* response was consistently direct across multiple separate challenges (same-account bug, idempotency-ordering bug, schema critique, locking critique).

## K. A better implementation approach (post-mock)
- Fill in `validate_amount(amount)` to reject `amount <= 0`.
- Deduplicate `test_withdraw_amount` (rename one) and fix the parametrized test to actually use its arguments.
- Add tests for same-account rejection and for "a failed transfer doesn't record its idempotency key."
- If per-account locking for `transfer_amount` is worth revisiting, use the `PENDING`/`SUCCEEDED`/`FAILED` state-machine approach from (G) instead of choosing between "safe but coarse" and "fast but unsafe."
