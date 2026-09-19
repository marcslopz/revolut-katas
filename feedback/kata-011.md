# Kata 011 — Mock Review

**Domain:** Loyalty Points Ledger (create account, earn/redeem points, chronological operation history, transfer between accounts, concurrency, PostgreSQL schema/locking/migration discussion)
**Stages completed:** 3 coding stages (core earn/redeem → operation history → transfer + concurrency) + optional Stage 4 (PostgreSQL schema/locking design, no code) + full technical discussion

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 5 |
| 4 | Speed | 4 |
| 5 | Correctness | 5 |
| 6 | Simplicity | 5 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 4 |
| 10 | Ability to evolve the design | 5 |
| 11 | Concurrency reasoning | 5 |
| 12 | Performance awareness | 4 |
| 13 | Production/backend judgement | 5 |
| 14 | Time management | 4 |

## A. Assessment: PASS (strong)

## B. Three strongest things
- **Unprompted, correct deadlock reasoning.** Asked what would happen with per-account locks on `transfer_points`, immediately named the deadlock risk and the standard fix (lock accounts in a consistent order, e.g. sorted by `account_id`) without any scaffolding from the interviewer.
- **Production-grade migration plan.** When asked how to roll a single-process, in-memory-locked service into multiple instances backed by Postgres, produced a genuine strangler-fig plan: dual-source reads against the old in-memory service while incrementally populating Postgres, a migration script for existing accounts, a cutover once traffic to the old source hits zero, and only then removing the now-meaningless in-process lock — materially more detailed than a typical "just add row locks" answer.
- **Clean incremental design evolution.** Each stage (ledger history, transfer, DB port) was layered onto the existing `Account`/`AccountService` split without rewrites or premature abstractions — business logic stayed on the domain object, orchestration/locking stayed on the service.

## C. Three biggest risks for the real interview
- **Recurring test-hygiene defect: duplicate test function name silently dropped real coverage.** `test_earn_points_invalid_input` was defined twice (once for `earn_points`, copy-pasted for `redeem_points`) — Python module semantics mean the second definition silently overwrote the first, so the `earn_points` invalid-input cases were never actually executed despite the suite showing green. This is the same defect shape as kata-008's duplicate `test_withdraw_amount` — now a 2nd occurrence across mocks. Only surfaced because the interviewer asked what happens when pytest collects a module with two same-named functions; self-fixed correctly once asked, but was not noticed before saying "stage completed."
- **Test file isn't discoverable by plain `pytest`.** The file is named `test.py`, which doesn't match pytest's default `test_*.py`/`*_test.py` collection patterns — running bare `pytest` in the directory reports "no tests ran," and only `pytest test.py` works. In a real interview environment where an interviewer (or their harness) runs the test suite themselves, this would look like zero tests exist.
- **Initial scope confusion under a precise technical question.** When pushed on what the in-memory lock protects during a multi-instance rollout, the first response conflated the in-process lock with a hypothetical DB-level lock, requiring the interviewer to restate the scenario. Recovery was immediate and the follow-up answer was precise and correct — but worth practicing restating an interviewer's question back exactly before answering, to catch this kind of mismatch without needing a prompt.

## D. Bugs or correctness problems
- None in application logic. The only defect found was the duplicate test function name (test-file hygiene, not business logic) — found via interviewer question, self-fixed correctly in-session.

## E. Unnecessary abstractions / overengineering
- None observed. `Operation`/`OperationDto` split (domain object vs. immutable transport shape) is justified and not over-built; no dead code or unused scaffolding.

## F. Missing or low-value tests
- No test covers the `pytest` bare-invocation discovery gap (expected — that's a project-config issue, not a unit test).
- No test/field correlates the two ledger rows of a single transfer (`TRANSFER_TO`/`TRANSFER_FROM`) via a shared identifier — reasonable to defer, since this was only designed at the Stage 4 schema-sketch level (`transfer_id` proposed for the DB schema, not yet in the in-memory model).
- Growth of `operations` under sustained load isn't tested (correctly identified as a real cost in discussion, not covered — reasonable given time).

## G. Better concurrency/design approaches
- Current design (single service-level lock) is appropriate for the in-memory scope and was explicitly, correctly named as the main scalability limitation without prompting. The Postgres design (`SELECT ... FOR UPDATE` + consistent lock ordering for transfers + Read Committed) is sound.

## H. Performance issues
- `get_account_operations` returns the full unbounded history in one call — fine for a kata, would need pagination/date-range filtering for a genuinely active account in production. Correctly flagged as a concern when asked, not something to drill further.

## I. What a strong candidate might have done differently
- Named the test file `test_main.py` (or similar) from the start — avoids the discovery gap entirely and is the kind of detail that separates "looks complete" from "verified by the tooling a reviewer would actually run."
- Skimmed the test file for copy-paste duplicate names before declaring a stage complete, the same habit flagged after kata-008.

## J. Practice priorities before next kata
- **Test-file hygiene as an active pre-"stage completed" habit**: skim for duplicate test names before moving on. Now 2-for-2 across mocks (kata-008, kata-011) — cheap to self-check, worth turning into a reflex rather than something the interviewer has to catch.
- Default to a pytest-discoverable test filename (`test_*.py`) as muscle memory.
- No action needed on authorization/ownership or regression-after-live-fix this kata — neither pattern was exercised (no ownership concept in this domain; no live application bug was found to require a regression test).

## K. A better implementation approach (post-mock)
- Add a `transfer_id` (or reuse one `operation_id` pair with a shared correlation field) to the in-memory `Operation` model now, not just at the Postgres-schema-sketch stage, so both ledger rows of a transfer can be reconciled directly.
- Otherwise the current design is solid as-is; no rewrite warranted.
