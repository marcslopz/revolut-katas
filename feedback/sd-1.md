# sd-1 — P2P instant money transfer (cross-currency)

Date: 2026-09-29
Problem: Design a service that lets users send money to each other instantly, including across
different currencies.

## Scores (1-5)

1. Requirements clarification: **3** — solid functional/non-functional questions (scope, scale,
   SLA), but never surfaced an implicit requirement (compliance/AML/audit trail) unprompted — an
   explicit Karim-email category, missed entirely this session.
2. Session leadership: **2** — the single biggest new evaluation axis per Karim's post-prep-call
   email, and the clearest weak spot this mock. Needed repeated interviewer-driven time/structure
   redirects (at least 4 separate points) rather than self-managing the pacing.
3. Communication: **3** — good self-correction under challenge, honest ("you are right, I totally
   forgot"), but trade-off articulation was mostly reactive (given when pushed) rather than
   volunteered proactively.
4. High-level design discipline: **4** — initial pass stayed appropriately skeleton-level; the
   depth that followed was interviewer-driven, not self-inflicted premature detail.
5. Component design: **3** — clear component boundaries (LB/web/DB/queue/consumer), but pre-flow/
   prerequisite sequencing (e.g. balance check before debit) was never made explicit.
6. Database design: **3** — reasonable schema reached, but only after a direct prompt (amount/
   currency were forgotten initially); no indexing/sharding-key discussion on the schema itself.
7. Scalability reasoning: **3** — good unprompted instinct to reuse the outbox mechanism for
   cross-shard as well as cross-region; missed the sharding-key question and proposed an O(N²)
   pairwise-queue topology for N regions without flagging the scaling risk in that choice.
8. Security awareness: **3** — solid on what was covered (JWT auth, TLS-at-edge, VPC isolation
   including the cross-region link), but breadth was narrow (no rate limiting, PII/compliance, or
   at-rest encryption reached) — partly a time-budget symptom of item #2.
9. Edge cases and failure-handling: **3** — the deepest, most rigorously interrogated area of the
   whole mock (circuit breaker → partial-commit state → coordinator crash → in-doubt blocking), and
   eventually landed correctly ("they would be stuck waiting") — but needed several interviewer
   follow-ups to get there, and along the way conflated 2PC with the outbox/queue pattern, and
   called an already-committed transaction's reversal a "rollback" instead of a compensating
   transaction.
10. Simplicity: **4** — the 2PC detour was arguably over-engineered relative to what the
    requirements actually needed, but was self-corrected into the simpler, correct async outbox
    model once its problems surfaced.
11. Time management: **2** — a hugely disproportionate share of the session went to one mechanism
    (cross-region consistency), leaving data model, security, and scaling all visibly rushed at the
    end; the interviewer had to intervene on pacing multiple times.

## A. Assessment: BORDERLINE

Technical depth and correctness, once probed, were good-to-strong — this reads as a candidate with
real distributed-systems instincts. The reason this isn't a clean PASS is squarely the newly
sharpened evaluation axis from Karim's email: **session leadership**. This mock needed the
interviewer to redirect on time/structure repeatedly, which is exactly the behavior Karim's email
says is separately and explicitly graded now, distinct from technical correctness.

## B. Three strongest things

1. Landed on the transactional outbox pattern unprompted, at the exact point it mattered, replacing
   an earlier flawed two-phase-commit idea — a direct, correct application of material studied only
   1-2 days earlier (Cloud Design Patterns).
2. Idempotency-key handling for duplicate message delivery — correct, textbook, and the first System
   Design data point confirming an already-strong Build It pattern (3-for-3 there) generalizes to
   this track too.
3. Never got defensive or dug in when challenged — self-corrected quickly and openly on the missing
   currency/amount fields, the 2PC-vs-outbox conflation, and the coordinator-blocking question.

## C. Three biggest risks for the real interview

1. **Time/session ownership.** The interviewer will not redirect you as generously as this mock did.
   Left unmanaged, one meaty sub-problem can eat the whole session and leave scaling/security as an
   afterthought — which is what happened here.
2. **Reactive rather than proactive trade-off surfacing.** The p99 < 500ms "instant" requirement was
   quietly relaxed for cross-region transfers without ever being called out and reconciled — a
   strong candidate flags that tension unprompted ("this means cross-region transfers won't hit our
   500ms target — here's why I think that's an acceptable trade-off").
3. **Precision under pressure on recently-studied vocabulary.** 2PC vs. outbox-with-queue, and
   rollback vs. compensating transaction, were both conflated live despite being covered in the
   theory pass 1-2 days earlier — the concepts aren't yet fully internalized, just recognized.

## D. Architectural gaps or inconsistencies

- The regional-DB architecture changed three times (separate-DB-per-region → single-global-primary
  in Europe → master-master with eventual consistency → per-region DB with an outbox+queue for
  cross-region) without ever being explicitly restated as a single, final, settled design.
- "Roll back the transfer in the European [side]" after that side had already committed — the
  correct mechanism is a compensating transaction (Saga), not a rollback.
- The idempotency key described verbally for duplicate-message handling was never placed on the
  Transfers table itself in the data model.

## E. Missing non-functional considerations

- Compliance/regulatory (AML, transaction limits, audit trail) — never surfaced, despite being
  named as an implicit-requirement category to watch for in a fintech prompt.
- Rate limiting / abuse prevention — not discussed.
- Data-at-rest encryption — only in-transit (TLS at the edge, VPC internally) was covered.
- Observability for the failure scenarios discussed (e.g. detecting outbox-consumer lag or a
  growing cross-region queue backlog) — not raised.

## F. Over/under-engineering

- The initial two-phase-commit design was arguably over-engineered relative to the actual
  requirement — the simpler async outbox model (which the candidate arrived at anyway) would have
  gotten there directly, and the 2PC detour cost real session time without surviving into the final
  design.
- Otherwise the design was reasonably proportionate to the stated 50M-user, cross-currency,
  strongly-consistent-balance requirements — no other over- or under-engineering flagged.

## G. What a strong Revolut candidate might have covered that this session didn't

- Proactively raising AML/compliance and an audit trail as an implicit requirement during Phase 1.
- Naming the Saga pattern and compensating transactions precisely, rather than reaching for
  "rollback," given it was studied within the last two days.
- A hub/central-broker topology for N-region messaging instead of pairwise per-region-pair queues.
- Explicitly self-managing the clock: "let me summarize this consistency approach and move on so we
  have time for scaling and security" — said by the candidate, not the interviewer.

## H. Topics to practice before the next mock

- **Saga pattern / compensating transactions vs. rollback** — precise vocabulary and mechanics.
  Direct callback to yesterday's Cloud Design Patterns reading; this is exactly where it should have
  been reached for.
- **2PC's blocking/in-doubt-transaction weakness** — recognize and name it in one pass rather than
  needing several follow-up questions to land on it.
- **Self-imposed time-boxing** — a personal rule like "no more than N minutes on any single
  sub-mechanism before summarizing and consciously moving on," rehearsed explicitly next time.
- **Proactively naming implicit requirements** (compliance/regulatory) during requirements
  gathering, without being asked.

## I. A better architecture (post-mock only)

Keep the regional split (EU/US primary DBs, each with local read replicas) — that part was sound.
Use the transactional outbox pattern consistently for every cross-boundary transfer (cross-region
*and* cross-shard, once sharding is introduced) — never 2PC. Model each cross-boundary transfer as a
two-leg saga: the debit leg commits locally and emits an event; the credit leg is a separate,
independently-retriable step; if the credit leg fails, emit a compensating *credit-back* event
rather than attempting a "rollback" of an already-committed transaction. Add `status` (pending /
completed / failed / compensated) and an explicit `idempotency_key` column to the Transfers table
alongside amount/currency/fx_rate. For growth beyond two regions, replace the pairwise-queue idea
with a hub/central-broker model (e.g. one globally-replicated event bus, or per-region brokers
bridged through a single relay) so the cross-region messaging topology scales linearly, not
quadratically, with the number of regions.
