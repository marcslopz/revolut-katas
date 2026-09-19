# Kata 012 — Mock Review

**Domain:** Job Scheduler (schedule/cancel/fetch-status → execute due jobs → concurrent worker polling with per-job and manager-level locking) + technical discussion (locking trade-offs, Big-O of polling, PostgreSQL schema/locking, retry idempotency, observability)
**Stages completed:** 3 coding stages (no optional Stage 4 — went straight to CODING COMPLETE) + full technical discussion

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 4 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 3 |
| 10 | Ability to evolve the design | 4 |
| 11 | Concurrency reasoning | 3 |
| 12 | Performance awareness | 3 |
| 13 | Production/backend judgement | 4 |
| 14 | Time management | 4 |

## A. Assessment: PASS

## B. Three strongest things
- **Ownership check done correctly from the start.** `_validate_owner` compares the caller's `owner_id` against the job's actual stored owner (not just existence), and it held up unchanged through two later stages of extension — no regression of the kata-007/kata-010 existence-vs-ownership pattern.
- **Non-evasive concurrency tracing.** When asked to trace two separate real bugs (a lock wrapped around a lazily-evaluated generator; an unsynchronized `cancel` racing `execute`), the first response in both cases was a direct, correct diagnosis followed by a correct fix — no hedging, no pivoting to hypotheticals. Consistent with the evasion-under-pressure pattern staying resolved (last seen kata-006/007).
- **Clear trade-off articulation.** Explained the per-job-lock-vs-single-service-lock choice in terms of concurrency/complexity trade-offs unprompted, and produced a correct PostgreSQL schema with the right composite index `(status, run_at)` and correct deadlock-avoidance reasoning (consistent row lock ordering) — the composite-index gap from kata-005 continues to show no signs of recurring.

## C. Three biggest risks for the real interview
- **Regression-test-after-live-fix gap, now 4-for-4 (kata-008, kata-009, kata-010, kata-012).** Two real concurrency bugs were found and fixed live this session (see D) and neither got a regression test — this is now a fully confirmed, mechanical habit gap rather than a one-off.
- **Both bugs were present when "stage completed" was declared.** The lock-that-doesn't-lock (generator laziness) and the cancel/execute race both shipped silently at the end of Stage 3; both were only caught because the interviewer asked pointed, code-specific follow-up questions. A less probing interviewer would not have caught either.
- **Terminology recall gaps under time pressure, two separate instances in one session.** Could not name "heap / priority queue" as the structure for O(log N) due-job scheduling, and did not know `SELECT ... FOR UPDATE SKIP LOCKED` for avoiding wasted blocking across concurrent pollers (reached for `NOWAIT` instead, which aborts the whole statement rather than skipping locked rows — incorrect for this use case even after a follow-up prompt).

## D. Bugs or correctness problems
- `Job.execute()` originally computed the outcome but never wrote `self.status` at all (Stage 2) — a due job would never leave `PENDING` and would be re-executed on every subsequent poll. Only caught when asked to trace whether a job ever becomes `RUNNING`; fixed correctly and completely (including adding the `RUNNING` transition) once raised.
- `JobManager._get_job_values` wrapped `self._jobs.values()` in a `with self._jobs_lock:` block but returned a **generator expression** — the lock was released before the generator body ever executed (generators are lazy), so the lock provided zero protection against a concurrent `schedule_job` mutating `self._jobs` mid-iteration. Fixed by returning a materialized list inside the lock.
- `cancel_job` mutated `self.status` directly with no lock, racing unsynchronized against `execute()`'s lock-protected check-then-act — a job could be canceled and executed concurrently with no serialization between the two paths. Fixed by moving the check+mutation into the same `execute_lock` used by `execute()`.

## E. Unnecessary abstractions / overengineering
- None. Notably avoided two invitations to over-build: declined to add speculative "don't overwrite a completed status" guard logic in Stage 1 before any execution path existed, and initially proposed but then dropped a service-level lock before concurrency was a stated requirement, once asked to justify it. Good instinct, consistent with kata-005's similar self-correction.

## F. Missing or low-value tests
- No test asserts `job.status` actually becomes `SUCCEEDED`/`FAILED` after `process_due_jobs` — existing tests only check the returned `ExecutedJobDto`, which is exactly how the missing-status-transition bug in D could have shipped unnoticed even further.
- No regression test for either live fix in D: nothing exercises `schedule_job` running concurrently with `process_due_jobs` (the generator-laziness scenario), and nothing exercises `cancel_job` running concurrently with `process_due_jobs` on the same job (the cancel/execute race).
- The existing `test_process_due_jobs_concurrently` (barrier-synchronized threads asserting `execute_body` called exactly once) is a good, reusable pattern for exactly this kind of test — it just wasn't extended to cover the two bugs found later in the same stage.

## G. Better concurrency/design approaches
- Current per-job-lock + manager-level dict-lock split is a reasonable, correctly-reasoned design once the two bugs were fixed. For the Postgres version, `SELECT ... FOR UPDATE SKIP LOCKED ORDER BY run_at LIMIT batch_size` per worker would let idle workers pick up different due jobs instead of blocking (or erroring, with `NOWAIT`) on rows another worker already claimed.

## H. Performance issues
- `process_due_jobs` scans the entire job set every poll — correctly self-diagnosed as O(N) and degrading with scale. A `heapq`-based priority queue keyed by `run_at` (or a Postgres index scan bounded by `run_at`) would get this to O(log N) per operation; cancellation is the awkward part with a plain heap (no O(log N) arbitrary delete) — the standard answer is lazy deletion (mark canceled, skip stale entries on pop).

## I. What a strong candidate might have done differently
- Added a regression test immediately after each of the two live concurrency fixes, before moving on.
- Named `heapq`/priority queue and `SELECT ... FOR UPDATE SKIP LOCKED` unprompted — both are close to boilerplate vocabulary for "poll a shared due-item set from multiple workers," which is precisely the shape of this exercise.
- Asserted `job.status` post-execution in the existing due-jobs tests rather than only the returned DTO, which would have caught the missing-status-transition bug without needing an interviewer question.

## J. Practice priorities before next kata
- **Add a regression test as the very next action after any live bug fix during a mock** — now confirmed 4-for-4 (kata-008, kata-009, kata-010, kata-012). This is the single most concrete, mechanical, and persistent gap across the whole series and warrants a direct coaching drill rather than passive tracking.
- **Recall drill: `SELECT ... FOR UPDATE SKIP LOCKED` and heap/priority-queue as the default answer to "many workers polling a shared due/ready set."** This exact framing recurs across scheduler/queue/rate-limiter-style problems, so closing the vocabulary gap once should generalize.
- Light watch: defining a term precisely under a direct push (this session's "idempotent... it's idempotent" circularity before landing on "same end result whether run once or more times") — similar shape to the kata-005 isolation-level vocabulary gap that was later resolved; only one data point here, not yet worth heavy drilling.

## K. A better implementation approach (post-mock)
- Back pending jobs with a heap of `(run_at, job_id)` tuples for O(log N) "next due" access instead of scanning `self._jobs`; on `cancel`, leave the heap entry in place and skip it lazily at pop time if the job's status is no longer `PENDING`.
- For the Postgres design, use `SELECT ... FOR UPDATE SKIP LOCKED ORDER BY run_at LIMIT :batch_size` per polling worker instead of plain `FOR UPDATE`, so concurrent workers partition the due-job set instead of blocking on each other.
- Add the two missing regression tests from F (concurrent schedule during poll; concurrent cancel during poll) and a post-execution `job.status` assertion to the existing due-jobs tests.
