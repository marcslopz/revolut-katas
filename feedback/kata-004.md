# Kata 004 — Mock Review

**Domain:** Wallet Service (create wallet, deposit, withdraw, idempotent transfer between wallets)
**Stages completed:** 4 (Stage 4 was discussion-only: Postgres schema, locking, isolation level, ACID/crash atomicity, horizontal scaling, outbox pattern)

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 4 |
| 6 | Simplicity | 5 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 4 |
| 10 | Ability to evolve the design | 5 |
| 11 | Concurrency reasoning | 5 |
| 12 | Performance awareness | 4 |
| 13 | Production/backend judgement | 4 |
| 14 | Time management | 4 |

## A. Assessment: PASS

## B. Three strongest things
- **Deadlock prevention was unprompted and correct from the moment it was needed** — locking wallets in a fixed order (`self.wallet_id < wallet_dst.wallet_id`) and explicitly guarding against self-transfer (which would deadlock a non-reentrant `Lock`). This is a direct improvement over kata-001, where the same lock-ordering fix only landed after two follow-up nudges.
- **Applied a lesson from a previous kata unprompted**: `get_wallet` returns an immutable `WalletDto` rather than the internal mutable `Wallet` (with its lock), exactly the fix recommended in kata-003's review (K) for the mutable-object leak. Good sign of retained feedback.
- **Idempotency correctness under real concurrency**, not just sequential idempotency: the check-then-act on the idempotency key happens inside the same locked section that mutates balances, verified with a genuine barrier-synchronized 10-thread test — reasoning matched implementation matched test.

## C. Three biggest risks for the real interview
- Two DB-discussion answers were initially incomplete and only became correct after direct pushback: claimed Read Committed alone made the double-insert race safe (had to be walked through why the row lock, not the isolation level, is what actually serializes it), and claimed a DB crash mid-transaction has "the same problem" as the in-memory version (missed that ACID atomicity/durability is precisely the guarantee that removes that risk). Both were correctly reasoned once challenged, but a real interviewer won't always probe every answer — this is the same pattern flagged in kata-003 (C).
- The idempotency pattern, once built for `transfer_funds`, was not proactively questioned for `deposit_funds`/`withdraw_funds` — a client retrying a timed-out deposit would double-credit a wallet today. This is the same "idempotency applied only to the operation directly named, not asked systematically per mutating endpoint" gap flagged in kata-002 (C).
- Minor but real data-consistency bug: in `transfer_to`, the two `Transfer` records written for one logical transfer store `wallet_src_id` inconsistently — as a `uuid.UUID` object in both cases, while `wallet_dst_id` is stored as `str(...)` in both cases. Nothing currently asserts on these fields, so it went uncaught.

## D. Bugs / correctness problems
- `Wallet.transfer_to`: `Transfer(wallet_src_id=self.wallet_id, wallet_dst_id=str(wallet_dst.wallet_id), ...)` — `wallet_src_id` is a `UUID` object, `wallet_dst_id` is a `str`. Inconsistent types for what should be symmetric fields, in both the source's and destination's transfer log entry.
- `deposit_funds` / `withdraw_funds` have no idempotency key — a retried request (the exact scenario Stage 3 was built to prevent for transfers) will double-apply.

## E. Unnecessary abstractions / overengineering
None. Third kata in a row with no premature abstraction — the `Wallet`/`WalletService`/`WalletDto` shape absorbed transfer and idempotency across two stages with zero rewrites.

## F. Missing or low-value tests
- No test for an invalid `idempotency_key` on `transfer_funds` (explicitly and transparently skipped due to time — reasonable call, but worth circling back to since it's a new validator).
- No test that a *repeated* call with the same idempotency key is still a correct no-op even after the wallets' state has changed since the original call (would exercise the check-before-balance-check ordering more precisely than the concurrent test does).
- No test asserting on the contents of a `Transfer` log entry — would have caught the `wallet_src_id`/`wallet_dst_id` type inconsistency directly.
- No test for two *different* idempotency keys transferring between the same wallet pair concurrently — the existing concurrency test only proves dedup, not that unrelated transfers between the same pair still both apply correctly.

## G. Better concurrency approaches
None needed structurally. Lock ordering, critical-section placement of the idempotency check, and the self-transfer guard are all the right calls at this scale, and held up under direct questioning.

## H. Performance issues
Every operation on a wallet (deposit, withdraw, and every transfer it's a party to) serializes through that wallet's single `threading.Lock`. Not wrong at this scale, but a high-traffic "hub" wallet (e.g., a merchant receiving many concurrent transfers) would become a serialization bottleneck — this scaling limit wasn't raised proactively during the Stage 4 discussion, similar to the un-raised single-lock bottleneck noted in kata-003 (H).

## I. What a stronger candidate might have done differently
Would have asked "does this need to be idempotent too?" for `deposit_funds`/`withdraw_funds` the moment the idempotency pattern was built for `transfer_funds`, rather than only applying it to the one operation the interviewer named. Would have caught the Read-Committed and crash-atomicity gaps unaided rather than after direct challenge — both are core ACID fundamentals a "production/backend judgement"-focused interview will probe hard.

## J. Practice priorities before next kata
- **Recurring (kata-002):** treat "does this new mutating endpoint need idempotency?" as a checklist item applied to every operation, not just the one the interviewer explicitly calls out.
- Core ACID fundamentals: what atomicity/durability actually guarantee across a crash, and why row-level locking (not isolation level) is what serializes a check-then-insert race — both needed a nudge here.
- Keep an eye on field-type consistency in log/record objects; a quick assertion on log contents in a test would have caught it for free.

## K. A better implementation approach (post-mock)
Fix `Transfer` construction to store `wallet_src_id`/`wallet_dst_id` consistently (both `str`, matching `WalletDto`). Add an idempotency key to `deposit_funds` and `withdraw_funds`, mirroring the `transfers` dict pattern already built for transfers — likely worth a small shared `_check_and_record_idempotency_key`-style helper at that point, since it would now be duplicated three times. For the hub-wallet bottleneck, the next natural evolution (not needed yet) would be moving from a single lock per wallet to a lock-free/CAS-based balance update (e.g. `compare_and_swap` retry loop) for the deposit/withdraw path, keeping the two-phase lock only for the true two-wallet transfer case.
