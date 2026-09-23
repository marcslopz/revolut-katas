# Kata 024 — Mock Review

**Domain:** Support Ticket Dispatch Service (agent registration/capacity → manual + priority-based pull assignment → concurrent worker access) + technical discussion (locking granularity, PostgreSQL schema/locking, idempotency, transactional outbox, microservice decomposition/CQRS-style capacity caching)
**Stages completed:** 3 coding stages + optional Stage 4 (discussion: schema, distributed locking, isolation level) + full technical discussion

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 4 |
| 2 | Communication / thinking aloud | 3 |
| 3 | Python fluency | 5 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 4 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 3 |
| 10 | Ability to evolve the design | 4 |
| 11 | Concurrency reasoning | 5 |
| 12 | Performance awareness | 4 |
| 13 | Production/backend judgement | 5 |
| 14 | Time management | 4 |

## A. Assessment: PASS

## B. Three strongest things
- **Ownership check correct from the start and stable across extension.** `Ticket.resolve` compares `assignee_id` against the caller's `agent_id` directly (not just existence), and Stage 1 included a dedicated "valid but unrelated agent" test — the exact case flagged as missing after kata-007. Held up unchanged through two later stages.
- **Concurrency and transaction reasoning generalized cleanly to a new domain.** Correctly justified a single coarse lock by tracing the actual coupling (`assign_next_ticket` needs the heap, ticket map, and agent map together), reasoned correctly about deadlock (no nested locks), and — at the DB design level — correctly attributed the capacity-safety guarantee to the row lock/CHECK constraint rather than the isolation level, unprompted. This is the same distinction that fully resolved in kata-006/007; seeing it reapplied cleanly to a fresh schema is a good generalization signal. `SELECT ... FOR UPDATE SKIP LOCKED` was also recalled correctly and unprompted (previously a gap flagged in kata-012, drilled in kata-013-focused).
- **Strong, self-driven production judgement in the conversation phase.** Proposed a transactional outbox for assignment notifications unprompted (correct pattern, correctly justified), correctly self-diagnosed `assign_next_ticket` as non-idempotent under client retry with a concrete idempotency-key fix, and — when pushed on a hypothetical microservice split — recognized and proposed a compensating action for a genuine eventual-consistency overcommit window rather than hand-waving it away.

## C. Three biggest risks for the real interview
- **A real correctness bug shipped and was never caught or fixed.** `OrderedTicket`'s tie-break field is `ticket_id` (a random UUID4), not creation order — this violates the Stage 2 requirement stated explicitly ("ties broken by creation order, oldest first"). It survived Stage 2 and Stage 3 undetected because no test ever created two same-priority tickets. It only surfaced when the interviewer asked about it during the *Postgres schema* discussion in Stage 4 — and even then, only the DB design was corrected; the actual Python bug in `main.py` was never revisited or fixed. This is now a third-generation instance of a recurring family (kata-022: enum declaration order as implicit sort key; kata-023: dataclass field order in a heap comparator; kata-024: wrong field entirely used as a tie-break) — the first time this family has survived a full mock rather than being caught in a focused-kata drill.
- **An explicitly-stated requirement was skipped until directly challenged.** The interviewer asked by name for a test demonstrating concurrent-load correctness; "Stage 3 completed" was declared without it, and the test was only written after being called out directly. This isn't an inferred/nice-to-have miss — it was stated in plain language as part of the stage's requirements.
- **The concurrency test that was eventually added doesn't cover the stage's actual point.** It correctly stress-tests `assign_ticket`'s capacity race, but Stage 3 was motivated by concurrent workers pulling from the shared priority queue via `assign_next_ticket` — that heap-pop path (the more novel, more contested piece of shared state) was never exercised under concurrency at all.

## D. Bugs or correctness problems
- `OrderedTicket(priority, status, ticket_id)` tie-breaks same-priority tickets by a random UUID instead of creation order — never fixed in code (see C).
- `assign_next_ticket` raises `TicketNotFound` both for "ticket ID doesn't exist" (used elsewhere in the API) and "no eligible ticket to assign" — a different condition reusing the same exception. Self-diagnosed correctly in the technical conversation ("we should use a different exception... risk is not being able to distinguish the source"), not fixed (acceptable — raised post-`CODING COMPLETE`).
- `assign_next_ticket` is not idempotent under client retry-after-timeout — a retried call after a successful-but-unacknowledged assignment will hand the agent a second ticket. Self-diagnosed correctly and unprompted with a concrete idempotency-key fix (acceptable — discussion phase only).

## E. Unnecessary abstractions / overengineering
- None of note. `OrderedTicket` as a separate frozen/orderable dataclass to keep heap-comparison semantics out of the core `Ticket` entity is a clean, appropriately minimal abstraction. Minor: it carries a `status` field that is always `UNASSIGNED` at push-time (entries aren't re-pushed after status changes), so that field never actually varies within the heap — harmless dead weight, not worth more than a mention.

## F. Missing or low-value tests
- No test creates two same-priority tickets to assert FIFO ordering — would have caught the bug in D immediately, since the current test suite only ever has one ticket per priority level.
- The concurrency test covers only `assign_ticket`'s capacity race; nothing exercises multiple threads calling `assign_next_ticket` concurrently against the same shared heap/agent set, which is the path Stage 3 was actually designed to stress.
- Self-disclosed and accepted trade-off: not all validation-error paths have dedicated tests (reasonable, time-boxed call, called out proactively rather than hidden).

## G. Better concurrency/design approaches
- The single coarse lock is a reasonable, well-justified choice given `assign_next_ticket`'s need to touch the heap, ticket map, and agent map together — correctly identified that finer-grained locks would need to change if that method didn't exist. No change recommended here; this was handled well.

## H. Performance issues
- The coarse lock serializes all operations across the whole service — correctly self-diagnosed as a throughput bottleneck under high concurrency (100 workers), with no proposed mitigation requested or offered (reasonable for this stage's scope).

## I. What a strong candidate might have done differently
- Written a same-priority, multi-ticket test as part of Stage 2 itself (not just Stage 3's concurrency pass) — this is a natural boundary case for "ties broken by creation order" and would have caught the bug before it ever shipped.
- Delivered the explicitly-requested concurrency test on the first pass, before declaring the stage complete, rather than after being asked about it directly.
- Extended the concurrency test to also exercise `assign_next_ticket` under multiple threads, since that was the path motivating the requirement in the first place.

## J. Practice priorities before the interview (2026-09-24)
- **Composite-comparator tie-break correctness is now a 3rd-generation recurring gap, and the first instance to survive a full mock.** Before tomorrow: adopt a standing reflex — any time you sort/compare on multiple fields, ask "do I have a test with a real tie on the leading field(s)?" and write it before moving on.
- **Re-read the stage's literal requirement text before declaring it complete**, checking every explicit ask (not just the one that feels like the "main" deliverable) — this is what let the concurrency test get skipped this time.
- Everything else (concurrency/locking reasoning, DB design, ownership checks, production judgement) is consistently strong across recent katas and doesn't need further drilling before tomorrow — spend remaining time on the two items above rather than broadening further.

## K. A better implementation approach (post-mock)
- Add `created_at: datetime` to `Ticket`, include it in `OrderedTicket` as `(priority, created_at, ticket_id)` with `ticket_id` only as the final fully-deterministic tiebreak (never the primary tie-break).
- Split `assign_next_ticket`'s "no eligible ticket" case into its own exception (e.g. `NoEligibleTicket`), distinct from `TicketNotFound`.
- Add an idempotency-key parameter (checked before assignment, short-circuiting to a no-op returning the prior result) to make `assign_next_ticket` safe under client retries.
