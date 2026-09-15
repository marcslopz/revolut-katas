# Kata 007 — Mock Review

**Domain:** Room Booking Service (create booking with per-room overlap conflict detection, cancellation with ownership check, list bookings by room/by user, concurrent creates and concurrent cancels, Postgres schema/index design, isolation level for the overlap-insert race, idempotent retries)
**Stages completed:** 3 coding stages + discussion-only Postgres/distributed-systems conversation (candidate declined optional Stage 4 coding, moved straight to CODING COMPLETE)

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 5 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 4 |
| 7 | Code quality | 3 |
| 8 | Naming/readability | 3 |
| 9 | Test quality | 4 |
| 10 | Ability to evolve the design | 4 |
| 11 | Concurrency reasoning | 4 |
| 12 | Performance awareness | 3 |
| 13 | Production/backend judgement | 5 |
| 14 | Time management | 4 |

## A. Assessment: PASS

## B. Three strongest things
- Excellent requirements clarification, including correctly pushing back once when an answer ("that's your design decision") was actually a product/requirements question mis-categorized by the interviewer — recognized the distinction unprompted and got a real requirements answer instead of accepting a hand-wave.
- Strong concurrency reasoning under direct pressure: traced two distinct, non-obvious races (check-then-act on the shared `_bookings_by_id` dict; `ValueError` vs `KeyError` propagating differently across two code layers) accurately once pushed to the specific line — first pass was occasionally imprecise ("KeyError" when it was actually `ValueError`) but self-corrected immediately on a follow-up, without needing the answer handed over.
- Precise, unprompted database/production judgment: converged on the correct composite index column ordering `(room_id, start, end)` for an equality+range query without prompting (a gap flagged after kata-005), named SERIALIZABLE isolation / phantom reads / write skew and row-level locking correctly as alternatives for the concurrent overlap-insert race, and gave the exact idempotency-key + unique-constraint + return-prior-result pattern for safe retries.

## C. Three biggest risks for the real interview
- **A real authorization bug shipped and was never fixed.** `cancel_booking` looks up the booking's true `room_id`/`user_id` from `_bookings_by_id` but never compares them to the caller-supplied `room_id`/`user_id` — it only checks that those IDs exist *somewhere* in the system. Any existing room+user pair can cancel someone else's booking. This was only surfaced because the interviewer asked a targeted question in the technical-conversation phase; it was not caught by the candidate's own review or tests, and was still unfixed when the mock ended.
- **Recurring evasion pattern under pressure (also seen in kata-006).** Asked directly whether the *current* code (not a future one) correctly rejected the losing side of a concurrent-cancel race, the first response pivoted to "imagine in the future we're doing other actions there... we should circuit break everything" instead of answering for the code as it stood. Self-corrected cleanly on the next direct prompt, tracing the actual lines precisely — but the instinct to reach for a hypothetical fix before committing to a yes/no about current behavior repeated across two consecutive mocks.
- **Test gap directly tied to the missed bug.** The only "wrong owner" cancellation test uses a `user_id` that doesn't exist anywhere in the system, so the `except KeyError` fallback happens to catch it — masking that the real ownership comparison is missing. No test exercises a `room_id`/`user_id` pair that exists elsewhere but doesn't own this booking, which is exactly the case that fails.

## D. Bugs or correctness problems
- `cancel_booking` authorization: compares existence of `room_id`/`user_id` in the top-level dicts, not equality against the booking's actual `room_id`/`user_id` (unfixed at end of session — see C).
- Race #1 (found and fixed live): concurrent cancels of the same `booking_id` could raise an unhandled `ValueError` from `list.remove` on the losing thread.
- Race #2 (found and fixed live): after fixing race #1 by swallowing the `ValueError`, the final `del self._bookings_by_id[...]` could raise an unhandled `KeyError` on the losing thread instead — also fixed.
- Discussed-but-not-implemented: even after both crash fixes, two threads racing to cancel the same booking can both currently return success (`True`) rather than exactly one winner. Candidate correctly diagnosed this live and proposed a one-line fix (raise `RoomBookingCancelConflict` on the final `KeyError` instead of passing), but it was not applied to the code before the mock ended.

## E. Unnecessary abstractions / overengineering
- None significant. Good instinct declining to split the single service lock into two (rooms/users) "as an optimization" without a measured need — explicitly deferred until performance data justified it. This is a real strength, and the inverse of the premature-locking pattern flagged in kata-006.
- `Booking.__eq__` doing double duty — comparing to another `Booking` by id, or to a raw string — exists purely to make `list.remove(booking_id)` work. It's a workaround more than an abstraction, but it's a design smell (see G).

## F. Missing or low-value tests
- No test where the passed `room_id`/`user_id` exist elsewhere in the system but aren't the booking's actual owner (would have caught bug D1 directly).
- No test for cancelling a booking that leaves a room/user with zero remaining bookings, or for the conflict-scan's behavior as a room's booking history grows large.
- Input validation tests were explicitly and transparently deprioritized as low marginal value / repetitive with prior katas — a reasonable, well-communicated time-management call.

## G. Better concurrency/design approaches
- Storing bookings keyed by `booking_id` in a dict (per room and per user) instead of a list matched via a custom dual-mode `__eq__` would make cancellation O(1), remove the string/`Booking` equality hack, and make "does this booking belong to this room/user" a direct dict lookup rather than an indirect existence check on unrelated dicts — which is also what let bug D1 slip in.
- To close the remaining "double success" race cleanly: treat popping from `_bookings_by_id` (under `self._lock`) as the single source of truth for who wins the race, verify ownership there, and only then clean up the room/user side structures — collapsing the current two-phase, three-exception-type flow into one atomic decision point.

## H. Performance issues
- `add_booking`'s conflict check is a linear scan over all existing bookings for a room. Fine at kata scale; would need a sorted-by-start-time structure (or interval tree) for a room with a large booking history. Not raised or tested this session — no positive or negative signal either way, just untested.

## I. What a strong candidate might have done differently
- Added the room/user ownership comparison in `cancel_booking` proactively the moment `booking_id`-based lookup was introduced in Stage 2, rather than relying on incidental existence checks.
- After finding the crash-race in Stage 3, audited the *sibling* exception-catching branch (the other `except` added in the same fix) for the same class of problem, instead of needing a second nudge to find it.

## J. Practice priorities before next kata
- **Recurring — commit to a direct, unhedged answer about current code behavior before offering a hypothetical fix.** This is the second consecutive mock (see kata-006) where the first response to "does the current code satisfy X?" pivoted to a future/hypothetical fix rather than a plain yes/no/not-yet. Worth deliberately drilling in coaching per [[coaching-drill-vs-mock-evidence]] — this mock's evidence should NOT yet promote it to resolved even after self-correction, since the initial evasive instinct still fired first both times.
- **New — treat "does X exist" and "does X own/match Y" as two different checks when writing authorization/ownership logic**, and specifically test the case where the other party is valid-but-unrelated, not just nonexistent.
- Composite index ordering and isolation-level vocabulary were clean and unprompted again this mock (both previously flagged after kata-005, resolved per kata-006, and holding here) — no further drilling needed on these specifically.

## K. A better implementation approach (post-mock)
- Key bookings by `booking_id` directly (`dict[str, Booking]` per room and per user) instead of a list + custom `__eq__`, giving O(1) cancellation and removing the `list.remove(str)` hack entirely.
- In `cancel_booking`: pop the entry from `_bookings_by_id` first under `self._lock` (this atomically decides the single winner and gives a clean `KeyError`-not-found signal for a genuine double-cancel), compare the popped record's `room_id`/`user_id` to the arguments and raise `RoomBookingCancelConflict` on mismatch, and only then remove the booking from the room/user views — one clear operation instead of the current two-phase dance across three exception types.
