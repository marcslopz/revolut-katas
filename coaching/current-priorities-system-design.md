# Current Coaching Priorities — System Design

_Last updated: 2026-09-29, after sd-1 (first full mock, P2P instant cross-currency transfer,
BORDERLINE)._

## Overall trend

One data point so far: BORDERLINE. Technical depth was good-to-strong once probed (correctly
reached the transactional outbox pattern, correctly diagnosed 2PC's blocking/in-doubt problem by
the end of the thread, clean idempotency-key handling), but the session showed a clear, repeated
gap on **session leadership** — the newly sharpened evaluation axis from Karim's post-prep-call
email (2026-09-28) — with the interviewer needing to redirect on time/structure at least 4 times.

## RECURRING WEAKNESSES (aggregated view)

- **Reactive rather than proactive self-catch / trade-off surfacing** — this is the chronic Build It
  weakness (12+ mocks, see `coaching/current-priorities.md`'s top RECURRING WEAKNESSES item and
  [[weak_areas_backend_concurrency]]), now confirmed to recur in System Design too (sd-1): quietly
  relaxed the p99 < 500ms SLA for cross-region transfers without flagging the trade-off unprompted;
  needed several interviewer follow-ups to reach the correct 2PC-blocking conclusion rather than
  self-catching it. Same structural weakness, new format.

## CURRENT PRACTICE PRIORITIES (mock-derived)

**HIGH — Session leadership / self-managed pacing (new, System Design-specific)**
Recurring: no (1 data point, sd-1) — flagged HIGH anyway since Karim's email names this the primary
new evaluation axis for this round, distinct from technical correctness.
Evidence: sd-1 — interviewer had to redirect on time/structure at least 4 separate times; one
mechanism (cross-region consistency) consumed a hugely disproportionate share of the session,
leaving data model, security, and scaling all visibly rushed at the end.
Problem: the real interviewer will not redirect this generously — per Karim, structuring and pacing
the whole session end-to-end is graded as a first-class criterion.
Drill: practice self-imposed time-boxing per sub-mechanism; rehearse explicitly narrating a summary
+ transition out loud ("let's lock that in and move to X") without waiting to be prompted.

**HIGH — Reactive rather than proactive self-catch (recurring, cross-track — see above)**
Recurring: yes, cross-track (Build It: 12+ mocks; System Design: 1/1 so far).
Evidence: sd-1, see RECURRING WEAKNESSES above.
Problem: same chronic structural weakness underneath several Build It items, now generalized to a
new interview format.
Drill: at natural checkpoints, explicitly ask "what did I just change that contradicts something I
said earlier?" out loud, before the interviewer has to ask it.

**MEDIUM — Distributed-transaction vocabulary/mechanics precision (new)**
Recurring: no (1 data point).
Evidence: sd-1 — conflated 2PC with the outbox+queue pattern; called a post-commit reversal a
"rollback" instead of a compensating transaction/Saga — both concepts studied only 1-2 days earlier
via Cloud Design Patterns, not yet fully internalized under live pressure.
Problem: recently-studied material available on recall but not precise enough under pressure.
Drill: a `START FOCUSED SD DRILL` specifically on Saga/compensating-transaction vs. rollback vs.
2PC, tracing one concrete cross-region failure scenario end to end.

**HIGH — "Is there an invariant, and how much tolerance does it have?" before picking a pattern (new, sharper than the general reactive item)**
Recurring: no (1 coaching session, 2026-09-29, but recurred within-session across 3 of 5 drills —
see PRACTICED IN COACHING below), not yet mock-confirmed.
Evidence: reached for outbox+hub+idempotency for a like-counter with no invariant at all; reached
for synchronous cross-region coordination for a rate limiter before checking if a fast atomic
counter (Redis `INCR`) would do; reached for globally-synchronous replica writes to fix a narrow
read-your-own-writes issue.
Problem: pattern-matches to the heaviest or most recently-used tool by default, rather than
checking what the actual invariant (if any) and its tolerance actually require first.
Drill: standing habit — before proposing a mechanism, say out loud "is there an invariant here, and
how much tolerance does it have?" and let the answer drive the choice (none → simplest local
option; loose tolerance → fast shared counter/cache; zero tolerance → the heavier coordination
patterns). Needs a future mock to confirm whether this generalizes under real interview pressure,
not just in a taught coaching session.

**MEDIUM — Implicit requirements not proactively surfaced (new)**
Recurring: no (1 data point), but flagged since it's an explicit named category in Karim's email.
Evidence: sd-1 — never raised AML/compliance/audit-trail despite the fintech-flavored prompt.
Problem: requirements-phase completeness gap specific to the "implicit requirements" bucket Karim
named directly.
Drill: standing habit — for any fintech-flavored prompt, name at least one compliance/regulatory
implicit requirement before moving into high-level design.

## Positive signals worth reinforcing (not gaps)

- Unprompted, correct application of the transactional outbox pattern at the moment it mattered —
  direct payoff from the 2026-09-28 Cloud Design Patterns reading.
- Idempotency-key + duplicate-check handling — first System Design confirmation that the
  already-strong Build It pattern (3-for-3 there) generalizes cleanly to this track.
- Quick, non-defensive self-correction whenever challenged directly (currency/amount fields, the
  2PC-vs-outbox conflation, the coordinator-blocking question).

## PRACTICED IN COACHING — AWAITING NEXT MOCK VERIFICATION

Per [[coaching-drill-vs-mock-evidence]]: this is coaching-session evidence, not mock evidence — it
can surface or reinforce a gap, but doesn't promote anything to RESOLVED. Only a future full mock
does that.

- **2026-09-29, post-sd-1 coaching session** — teaching pass covering the sd-1 review in depth
  (escrow/ledger pattern, CRDTs explained from scratch), then 5 rapid-fire `START FOCUSED SD DRILL`-
  style problems (candidate proposes a solution, coach challenges 2-3 times, coach closes with
  argued alternatives): (1) hotel booking, no double-booking, EU/US — correctly landed on
  entity-owned sharding (route to the room's home region) instead of Saga/2PC, plus a sharp
  correction on lock-duration (short atomic status-flip + TTL hold, not a long-held row lock across
  a payment flow); (2) global like-counter — initially over-applied the outbox+hub+idempotency
  pattern from sd-1 by reflex, self-corrected toward the CRDT/local-counter approach once challenged
  on whether there's an actual invariant to protect; (3) distributed rate limiter — correctly
  recognized eventual consistency risks up to 3x overshoot, converged on a Redis atomic-counter
  approach (with fail-open/fail-closed named as an explicit trade-off) after over-correcting first
  toward a synchronous queue+consumer (which reintroduced the same blocking problem being avoided);
  (4) read-your-own-writes after a transfer — correctly diagnosed replication lag, but first
  proposed making ALL writes synchronous with read replicas (a global, expensive fix for a narrow
  problem) before landing on sticky read-after-write routing / optimistic client update; (5) hot-key
  on a viral livestream — correctly proposed key-splitting and connected it back to the CRDT
  aggregation pattern from (2) unprompted, but only covers statically-known celebrities, not
  unpredictable virality (self-identified the gap, coach added cache-based defense as a
  complementary layer).

  **New, sharper pattern than the general "reactive" item above**: across nearly every drill
  (2, 3, 4), the first instinct was to reach for the heaviest or most recently-used mechanism
  (outbox+hub, synchronous coordination, full replica sync) before checking whether the actual
  invariant present — if any — actually required that much machinery. The self-correction, every
  time, came from being asked explicitly "is there an invariant here, and how much tolerance does
  it have?" — this question, asked out loud before picking a pattern, is the concrete habit to
  drill next, not just "be less reactive" in the abstract.

  Positive, unprompted: correctly reused the CRDT/local-aggregation pattern from drill (2) in drill
  (5) without being told to — a genuine sign that at least one lesson generalized within the same
  session, not just recalled when re-taught.
