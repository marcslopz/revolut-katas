# Kata 005 — Mock Review

**Domain:** API Gateway Quota Tracker (register client with quota, record request against a rolling time window, concurrent access, distributed/Postgres design)
**Stages completed:** 4 (Stage 4 was discussion-only: Postgres schema, row locking vs isolation level, composite indexing, idempotency, canary rollout)

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 3 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 4 |
| 7 | Code quality | 3 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 3 |
| 10 | Ability to evolve the design | 4 |
| 11 | Concurrency reasoning | 3 |
| 12 | Performance awareness | 4 |
| 13 | Production/backend judgement | 3 |
| 14 | Time management | 4 |

## A. Assessment: BORDERLINE (leaning PASS)

## B. Three strongest things
- Correctly identified and fixed a real redundant-locking bug (service-level lock wrapping an already-present per-entity lock, serializing every client's requests through one global lock) the moment it was pointed at, and proposed the right scoped fix without needing the fix spelled out.
- Clean, rewrite-free evolution of the design: Stage 1's `current_requests: int` became Stage 2's `list[datetime]` sliding-window log, with `bisect` used correctly to trim expired entries — no premature abstraction anywhere in three stages of change.
- Derived O(quota) time/space complexity for the sliding-window log unprompted, and correctly reasoned through the fixed-window boundary burst problem (up to 2x quota near a window edge) once an initial "peak → blocked" mix-up was corrected via a concrete example.

## C. Three biggest risks for the real interview
- **Recurring pattern (kata-003, kata-004): DB isolation-level answers are initially imprecise under pressure.** Called a lost-update race (two transactions both reading "under quota" before either commits) a "dirty read" — which Read Committed already prevents by definition — and only landed on the correct term after being walked through a concrete counterexample. This is the third kata in a row where an isolation-level claim needed direct pushback to correct (kata-003 C, kata-004 C).
- **Composite index column ordering was wrong, twice.** For a query filtering by `client_id` (equality) and ranging on `timestamp`, first proposed `(timestamp, client_id)`, then split into two separate single-column indexes rather than converging on `(client_id, timestamp)` — the standard "equality columns before range columns" rule. Never self-corrected to the right answer; only got there when asked to compare against the composite-index alternative directly.
- **Invented a non-existent SQL construct** ("SELECT for INSERT") when first reasoning about the idempotency-key insert race, before landing on the correct answer (unique constraint) after a guiding question. Recovered well, but producing a fabricated construct under pressure is a pattern worth eliminating before answers that can't be walked back as gracefully.

## D. Bugs / correctness problems
- `AlreadyExistingClient(ServiceException)` is defined twice in `main.py` (once near the top, once again immediately before `ClientDto`). Harmless — the second silently shadows the first — but would be flagged in any real code review.
- `quota_window_seconds` is never validated (only `quota` goes through `validate_quota`). A zero, negative, or non-int window is silently accepted; a negative window would make `current_window_start` land *after* `current_window_end`, producing nonsensical trimming behavior.
- `Client.to_dto()` does not copy `current_requests` — `ClientDto.current_requests` holds a reference to the live list rather than a snapshot. Not exploited by any current test, but breaks the "DTO is immutable/point-in-time" property this candidate has correctly applied in earlier katas (kata-004 B).

## E. Unnecessary abstractions / overengineering
None. Fourth kata in a row with no premature abstraction layer — no repository/interface indirection for what is a single in-memory dict-backed service.

## F. Missing or low-value tests
- No test that a request is allowed again after its window actually elapses — explicitly and transparently deferred due to no injectable clock (reasonable time-management call, but see J).
- No test for invalid `quota_window_seconds` (ties directly to the unvalidated-input bug in D).
- No test for `AlreadyExistingClient` (duplicate `create_client` call).
- The concurrency test only covers `quota=1` (fully all-or-nothing). A `quota=5, threads=20` variant asserting exactly 5 `True` results would exercise the trim/count logic under contention more precisely than an all-or-nothing case can.

## G. Better concurrency approaches
None needed structurally — the eventual fix (drop the redundant global lock around `client.record_request()`, keep the dict lookup itself under the service lock) is the right call at this scale and was reached through sound reasoning, not luck.

## H. Performance issues
None at the given scale (O(quota) per call, bounded list). Correctly flagged during the Stage 4 discussion: a naive Postgres port (delete-old-rows + insert + count per request, under a row lock) would become a hot-row bottleneck at high RPS; the Redis sorted-set alternative (`ZADD`/`ZREMRANGEBYSCORE` + key TTL) was the right instinct and maps directly onto the in-memory algorithm already built.

## I. What a stronger candidate might have done differently
Would have used "lost update" precisely on the first pass rather than "dirty read," and would have named `(client_id, timestamp)` as the composite index without needing the two-separate-indexes detour. Would likely have proactively flagged the missing `quota_window_seconds` validation while reviewing their own diff, the same way `quota` validation was added unprompted.

## J. Practice priorities before next kata
- **Isolation-level vocabulary, precisely**: dirty read vs non-repeatable read vs phantom read vs lost update, and which specific mechanism (Read Committed, `SELECT FOR UPDATE`, Serializable) prevents each. Third kata running this needed direct pushback (kata-003, kata-004, kata-005) — worth deliberately drilling outside of a mock before it recurs a fourth time.
- **Composite index column ordering** (equality predicates before range predicates) — a very common backend-interview SQL topic, not yet solid.
- **Inject a testable clock** (`now: Callable[[], datetime]`, defaulted to `datetime.now`) into time-window-based katas from the start, so window-expiry becomes testable without `sleep()` or a real clock dependency — this is the second kata where a natural test was skipped for exactly this reason.

## K. A better implementation approach (post-mock)
Remove the duplicate `AlreadyExistingClient` definition. Add `validate_quota_window_seconds` (positive int, same shape as `validate_quota`) and call it in `create_client`. Make `Client.to_dto()` return a copy of `current_requests` (`list(self.current_requests)`) rather than the live list. Extract a `Clock` protocol/callable injected into `ClientQuotaService` and threaded into `Client.record_request()` — one small change that unlocks deterministic window-expiry tests without touching the sliding-window algorithm itself, mirroring the recommendation already made in kata-004 (K) for a different testability gap.
