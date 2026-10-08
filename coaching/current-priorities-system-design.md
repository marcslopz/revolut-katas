# Current Coaching Priorities — System Design

_Last updated: 2026-10-08, after sd-20/21/22 (timed afternoon mocks, all PASS). Previously: 2026-10-06, after sd-16 (click & collect, PASS moderate) and the lite-mock stock series (sd-13/14/15-focused) logged under PRACTICED IN COACHING. Before that: 2026-10-05, after sd-12 (cinema seats, strong PASS — best overall) + post-review
Postgres concurrency Q&A. Previous update: after sd-11._

**Calibration (2026-10-04, set by the candidate):** priorities here track **technical design**
(consistency, availability, durable state across failures, idempotency, sync vs async, data
placement, secure storage). Fintech domain depth and legal detail are a bonus: not tracked as
priorities, never counted against a mock. See CALIBRATION in `modes/system-design/interviewer.md`.

## Overall trend

Seven mocks: BORDERLINE → BORDERLINE → BORDERLINE (trending up) → PASS (low margin) → BORDERLINE →
PASS (sd-6, after recalibration) → PASS (sd-7) → PASS, strong (sd-8) → PASS, moderate (sd-9) →
PASS, strong (sd-10, first non-fintech) → PASS, strong (sd-11, 40-minute scope) → **PASS, strong — best
overall** (sd-12) → PASS, moderate (sd-16, click & collect, after the lite-mock stock series sd-13/14/15-focused).

- **sd-1**: pacing chaos (4 redirects).
- **sd-2**: no redirects, but ended inside Phase 3 and handed structure back ("anything else?").
- **sd-3**: every phase reached, implicit requirements surfaced unprompted (3 of them) — but depth
  went to a peripheral component (daily archiver) while the prompt's core (reserving money safely
  under concurrency) was never designed. Closed with the sd-2 hand-back again.
- **sd-4**: found the core first (priority isolation of OTP vs marketing), layered failure handling,
  best trade-off justification so far, no hand-back at the close.
- **sd-5**: process skills held (all phases, own transitions, own summary incl. deployment +
  monitoring, simplicity 4, estimates right first time with a storage comparison). Failed on
  **money-path correctness** (dual-write claim, random-UUID idempotency key with no per-occurrence
  uniqueness, balance check-then-act — exactly-once path only walked through when probed),
  **data residency for the 3rd time** (stated the rule, then single EU primary + global replicas),
  and **domain modelling** ("monthly" as `period_in_days = 30`; no time-zone/month-end/business-day
  questions).

- **sd-6**: data residency right from Phase 1 to Phase 4, unprompted (cell per region, in-region
  multi-AZ failover, only minimal data crosses, link→cell directory). Consistency mechanics precise
  (conditional writes, SELECT FOR UPDATE, partial unique), reasoned sync choice, lost-webhook
  reconciliation. Remaining technical gap: no payment row / no durable state before the external
  calls (crash mid-flow can't be resumed); credit-before-debit order.

- **sd-7**: money path designed entity-first **unprompted** (withdrawal row → hold → state persisted
  before the provider call → idempotent provider key → debit + release in one TX); only the
  recovery worker needed a probe. Residency clean for the 2nd mock running. Simplicity 4.75.
  Remaining: failure paths (provider reject) only when asked; thin Phase 4; callback auth/authZ.

- **sd-8**: failure paths of the external call covered **unprompted** (success/failed/pending/5xx/
  timeout, checker with explicit criteria, breaker + disabling the UI); only late reversal needed a
  probe. Money path entity-first again. Every sd-7 J-section fix applied unprompted. Remaining:
  schema missing the phone number + client idempotency key; peak factor dropped at 10x.

- **sd-9** (different shape: read-heavy, event-driven CQRS projection): best questioning so far
  (asked about out-of-order events herself), idempotent projection `(transaction_id, seq)` +
  outbox-on-insert, residency 4th mock running. But 5 interventions on core points: first-insert
  upsert bug, feed sorted by `updated_at` (no transaction time), night-burst lag vs the 5 s SLA (two
  prompts), Phase 4 bottleneck pushed. Single-column indexes again; read volume of a read-heavy
  service never asked.

- **sd-10** (library reservations): best Phase 1 of all ten — hotspot recognised as lock contention
  unprompted, waitlist discovered, queue → table the moment it became long-lived. Title-row conditional
  update with the loser joining the waitlist in the same TX (after a probe it was "implied"). Every
  external-call outcome unprompted. No fintech patterns over-applied. Gaps: schema missing own-flow
  fields (pickup branch, email, outbox recipient, `available_copies`), per-branch index, waitlist
  promotion async instead of in the check-in TX, Phase 4 pushed again.

- **sd-11** (meeting rooms, minimal scope): most proportionate design of all eleven — three boxes,
  `tstzrange`, DB-level non-overlap, authZ in the WHERE, fail-fast validation. Lock stated while
  designing; index walk per query self-caught `rooms.status` + `executed_at`. But `bookings` first shown
  without `room_id`; the main user action (find a free room by time + capacity) never designed; Phase 4
  pushed again — then the model answer (numbers, contention per room, cost of 100 cells, per-continent
  consolidation).

- **sd-12** (cinema seats): most common action asked in the first question; query → index for every
  path; lock order stated (deadlock avoidance); **Phase 4 opened unprompted for the first time**
  (per-screening occupancy, shard key, hot shard, waiting room). Gaps: `paying` status designed then
  missing from the table, `booking_seats` without screening; the late-payment race needed two probes;
  ρ first applied to the whole DB (fixed in one turn); "try to unlock" deadlocks again.

Session leadership, implicit requirements (generic ones) and simplicity are now stable. The fail
risk is technical correctness in the prompt's core and the regulatory topology — both are things a
fintech interviewer probes first.

## RECURRING WEAKNESSES (aggregated view)

- **Data residency on multi-region** — sd-3 (card balances replicated everywhere), sd-4 (users
  table + PII global), **sd-5** (opened Phase 4 with "user data must stay in the region", then single
  EU write primary for all users + read replicas in every region; "inform the user" as mitigation).
  The 2026-10-02 RAPID drill had it correct 3/3 → **drill-to-mock transfer failure**: the rule is
  known, but under the clock the latency/simplicity argument for one primary wins and the rule is
  dropped.
- **Exactly-once / duplicate safety on the money path** (new aggregate; sd-3 + sd-5) — sd-3 never
  designed the reserve-funds core; sd-5: "publish to the queue inside the DB transaction" (dual
  write → double payment), idempotency key = fresh UUID (no `UNIQUE(schedule_id, occurrence)`),
  balance checked in the consumer, debited later by the provider (check-then-act). Fixed with an
  outbox after one probe. Regression of the "distributed-transaction mechanics" item resolved at
  sd-2 — the vocabulary is there, the per-hop duplicate analysis isn't done unprompted.
- **Model drift / late self-catch** — sd-3, sd-4, **sd-5** (tables 1 → 2 → 4 → 2; `pending` added then
  dropped; `reason`, outbox, nullable `end_at` never reached the canvas; automatic quorum promotion
  vs "wait for Europe" never reconciled). Three mocks running.
- **Failure paths for every external call, without being asked** — sd-6/sd-7 needed probes; **sd-8**
  (only late reversal probed) and **sd-10** (every outcome unprompted: success, transient vs invalid
  reject, timeout, crash before/after send, breaker + half-open). Resolved as of sd-10.
- **Core-first and proportion of depth** — sd-3 fail, sd-4 success, **sd-5 fail** (Phase 1 + start of
  Phase 2 spent on table layout — needed a redirect; the scheduler → occurrence → exactly-once path
  only described when asked).

## RESOLVED (confirmed by a full mock)

Per [[coaching-drill-vs-mock-evidence]]: coaching-session/drill evidence alone never promotes an
item here — only a full mock under `modes/system-design/interviewer.md` does.

- **Implicit requirements not proactively surfaced** — 0/2 in sd-1/sd-2; after the 2026-09-30
  domain-family drilling, **unprompted in sd-3** (audit retention, PCI, GDPR) **and sd-4** (PII in
  content + legal proof of delivery). Two consecutive mocks → resolved as of sd-4. sd-5 kept the
  habit (audit, PII, GDPR unprompted) **but all generic**: zero domain-specific items (time zones,
  month-end, business days, cut-offs, SCA) — tracked as the new domain-modelling item below.
- **Distributed-transaction vocabulary/mechanics precision** — resolved as of sd-2; held in
  sd-3/sd-4. **sd-5 regression** (dual-write claim, fixed after a probe) — now tracked under the
  HIGH exactly-once item below; if it recurs in sd-6, move it back out of RESOLVED.
- **"Is there an invariant, and how much tolerance does it have?"** — resolved as of sd-2. sd-5:
  invariant stated unprompted ("sufficient balance *at execution time*") — but not enforced
  atomically (see exactly-once item).

- **Data residency by default in multi-region designs** — failed sd-3, sd-4, sd-5; **correct and
  unprompted in sd-6 and sd-7** (cell per region, home-region ownership, in-region failover, only
  minimal data crosses). Two consecutive mocks → resolved as of sd-7. Watch: "region down" answered
  with AZs in sd-7 (a full-region outage needs a second region inside the jurisdiction).

- **Exactly-once on the money path (payment row first, durable state, hold before the irreversible
  step, idempotent provider key)** — failed sd-3, sd-5, sd-6; **designed unprompted in sd-7** (one
  probe for the recovery worker) **and sd-8** (clean). Resolved as of sd-8.
- **Phase 4 opened unprompted** — pushed in sd-8/9/10/11; **opened unprompted in sd-12 and sd-16** (sd-16: cells per
  region with residency, ~3k WPS till writes named as the 10x bottleneck). Resolved as of sd-16. Residual: the first
  shard key was chosen for the read while the bottleneck was writes (fixed on one probe) — say which operation the key
  must keep single-shard.
- **Design the dominant user action first** — missed sd-11 (free-room search); **asked and designed first in sd-12 and
  sd-16** (per-store availability view, query → index). Resolved as of sd-16.
- **Time management (~40–45 min end to end)** — sd-20 62 min; **sd-21 45 and sd-22 ~39, both on budget**. Resolved as of sd-22.
  Residual: with a short deep dive, announce the edge-case sweep so it isn't pre-empted.
- **Core-first and proportion of depth** — sd-3/sd-5/sd-6 failures; **sd-7 and sd-8 went to the
  core (the money entity and its flow) within the first minutes**. Resolved as of sd-8.

## CURRENT PRACTICE PRIORITIES (mock-derived)

**sd-22 summary (2026-10-07, third timed mock — online shop stock)**: PASS (moderate, low margin), **~39 min**. Time on budget for the
2nd mock running → **time management moved to RESOLVED**. Improving:
- **counter walk on every transition, unprompted** (quantity / available, five transitions, all correct) — first clean mock after
  sd-16 / sd-21 misses; one more → RESOLVED
- "unique within what?" held (checkout's order id as `orders` PK, `ON CONFLICT` → same response)
- **late payment after expiry** answered on the first probe (re-check, else refund)

New / reinforced:
- **MEDIUM — Read path for read-heavy NFRs (new, related to sd-9 / sd-11)**: 5k/s availability reads (p99 < 100 ms) listed with
  replicas in requirements, then never drawn, designed or scaled. The dominant action *by volume* was dropped, while the dominant
  *write* got all the depth. Drill: when reads ≫ writes, put the read path in the high level (cache or replica, staleness SLA, which path
  is authoritative).
- **MEDIUM — Shard key from the invariant, and only when a number forces it (recurring: sd-16, sd-21, sd-22)**: sd-16 key chosen for
  the read; sd-21 shard by user splits per-library counters; sd-22 shard by user for per-SKU stock, then by SKU + saga at ~200 WPS
  (one writer). Drill: open Phase 4 with "N writes/s → still one writer? → first real bottleneck is X"; when sharding, say which
  transaction the key must keep single-shard.
- **Timer races (below)**: the concurrent expiry/success race first locked the SKU rows, not the order row (fixed on a follow-up).
  Improving: the late-event case is now answered on the first probe.
- Process: edge cases come last in the candidate's DISE flow. Announce the sweep at the start of the deep dive so a real interviewer
  waits. Asked the interviewer to list actors in Phase 1 (one-off; propose them, then confirm).

**sd-21 summary (2026-10-07, second timed mock)**: PASS (moderate), **45 min — on budget** (req 8 / HL 10 / deep 26). Time item improving
(one mock). Trade-off of the faster Phase 1: **core business rules not asked** (unavailable → waitlist, when each timer starts, per-user limit)
— add 2 min of "unavailable / timers / limits" questions to every reservation/stock prompt. Secondary transitions skipped the shared
structures again (new copies bypass the waitlist; the 5-item limit never designed; `reservations` without library_id). Timer race (user at the
counter as the hold expires) not addressed unprompted — still open.

**sd-20 summary (2026-10-07, first timed mock)**: PASS, technically strong; **62 min vs 40–45 budget** (requirements 19, deep dive 34).
New HIGH item for the real round: **time management** — requirements ≤ 8–10 min (estimates on the canvas in 2 min), high level with a
2-min walk of every flow, deep dive one flow per ~4 min riskiest first, move to scaling by ~35 min. Positives: numbers copied right all
through; "unique within what?" held twice (`(cell, transfer_id)`, provider ids); Phase 4 unprompted 3rd mock running; saga with retry-not-
compensate on timeout. Gap: outbox for the crash between commit and external call deferred as "improvement" (money path minimum).

**sd-16 summary (2026-10-06)**: Phase 4 and dominant-action items moved to RESOLVED. New / reinforced:
- **MEDIUM — Idempotency key scope: "unique within what?"** (new, recurring: case 2 lite mock `order_id` per marketplace
  + **sd-16 `sale_id` per till** used as a global key → real sales dropped as duplicates). Drill: for every external id,
  ask "unique within what?" and make the key the full natural identity (`(store_id, till_id, sale_id)`).
- **Timer races (below) — still open**: sd-16 no-show → late collection sale needed three turns and ended with a counter
  error (sale marked completed with no decrement → phantom stock). Same cross-case pattern as the lite mocks: counters on
  secondary transitions.
- **Data layer (below)**: sd-16's drawn schema had no stock table (`sku_stores` only in the queries), `orders` without
  `store_id`. Draw the invariant-holding entity first.
- **Simplicity (below, LOW → watch)**: sd-16 precomputed users × stores distances + Redis for 200 static stores;
  two-region sync replication kept after correcting 99.99% → 99.9%. Re-read the requirement number before adding a box.


**MEDIUM — Data layer from the queries: every field the flow uses, indexes from the main query, and the
locking statement said while designing** (raised after sd-9; **sd-10 = 4th mock running**: waitlist
without pickup branch, users without email, outbox without recipient/status, `available_copies` used
in the SQL but absent from the table, `(isbn, status)` without branch, no `(reserved_by, status)`; the
title-row lock only stated when probed. The "query first, then table" drill is still pending.)
**sd-11: improving** — lock stated while designing, and walking each query to its index self-caught
two missing columns; but the core field (`bookings.room_id`) was still missing on the first pass (5th
mock). Next step: read the main query's WHERE against the table *before* presenting it.
**sd-12: the query → index walk and the lock are now habitual** (every path, unprompted, with lock
order). What remains is narrower: **the state machine ↔ table check** — `paying` designed 10 minutes
earlier but absent from the table; `booking_seats` without `screening_id`.
**Re-scoped 2026-10-05 (candidate):** the real round is spoken design — nobody checks exact SQL, every
timestamp or NULL-ability. Downgraded to MEDIUM and narrowed to what a whiteboard conversation reaches:
key entities + the field the core flow depends on, the state list, the mechanism that guarantees the
invariant, and roughly which index serves the main query. SQL-level slips from the drills are bonus
polish, not interview risk.
Recurring: sd-6 (no amount/currency, no payment row), sd-8 (no phone number, no client idempotency
key), **sd-9** (no transaction time → feed sorted by `updated_at`; single-column indexes when every
query is per user — a regression of the sd-7 lesson; unnecessary seq index). Now the most persistent
technical gap. Each time it's a field or index the candidate's *own flow* depends on.
Drill (two steps, 30 seconds, before presenting any table):
1. Write the main query out loud (`WHERE user_id = ? ORDER BY occurred_at DESC LIMIT 50`) and derive
   the index from it, **user first**.
2. Walk your own flow and tick every field it uses and every key you said you dedupe on.

**~~MEDIUM~~ RESOLVED as of sd-16 (see RESOLVED) — Phase 4: one new bottleneck and its cost per step, unprompted** (downgraded after sd-12:
**opened unprompted for the first time** with numbers, per-screening occupancy, shard key, hot shard and
a mitigation. One more unprompted mock → RESOLVED. sd-11: pushed a 4th time; the
answer after the push was the model one — numbers proving nothing breaks, contention per key, the
operating cost of 100 cells, consolidation. Only the *opening* is missing. Raised after sd-10: pushed
in sd-8, sd-9 and sd-10 — every time. After the push the answers are good (sd-10: three options with
costs and a preference), so the gap is purely *starting it yourself* + *proving the bottleneck with a
number* (sd-10's "notification providers" was tens/s — not a bottleneck). Previously: sd-8 and sd-9: named the right
bottleneck — aggregator, Postgres primary → shard by user_id — but only after a push, and sd-9 without
numbers or cost. Opener to practise: "at 10x: N writes/s → X is the bottleneck → fix Y, which costs Z".)
Recurring: sd-4, sd-5, sd-6, sd-7 (no explicit local → regional → global staging; sd-7 named no
bottleneck at scale). Residency is now solid; what's missing is "what breaks next and what does the
fix cost" (e.g. provider rate limits on payday → throttle/queue; replica lag → read-your-writes).

**LOW (bonus) — Domain modelling of the core business concept (time/calendar)**
Recurring: no (sd-5 only). Per Calibration, domain depth is a bonus; kept only because "monthly ≠
30 days" is a modelling correctness issue, not legal/domain trivia.
Problem: "monthly rent on the 1st" was modelled as `period_in_days = 30`; no questions about user
time zone, month-end (29th–31st), weekends/bank holidays, scheme cut-off — the implicit
requirements specific to this domain. Generic implicit reqs (audit/PII/GDPR) are habitual;
domain-specific ones aren't.
Drill: add a **"time" family** to the implicit-requirements checklist (time zone / DST, calendar
vs fixed interval, month-end clamping, business days, cut-off times, "executed by when?") and in
Phase 1 always ask "what does a domain expert worry about that a generic CRUD app wouldn't?"

**~~MEDIUM~~ RESOLVED as of sd-16 (see RESOLVED) — Design the dominant user action first** (new, sd-11; related sd-9; **sd-12: asked in the
first question and designed first** — one clean mock, one more → RESOLVED)
sd-11: "find a free room for this time and size" — what employees do most — never asked or designed
(only per-room availability). sd-9: the read volume of a read-heavy service never asked. Drill: in
Phase 1 ask "what's the most common user action?", then design that query first (query → index →
table).

**MEDIUM — Races at timer/lifecycle boundaries** (new, sd-12; related sd-10)
sd-12: payment completes right after the hold expired and someone else held the seats — needed two
probes (first answer "take Bruno's seats" moved the problem). sd-10: the next waiter's pickup window
ticking while their notification was stuck. Drill: for every timer in the design, say "what if the other
event arrives one second after the timer fires?" and make the transition conditional on the expected
state (`WHERE status = 'held'`), with a compensation for the 0-rows case.

**MEDIUM — Decisions follow new facts (model drift + re-checking earlier decisions)** (sd-10 improving:
Redis → waitlist table revised immediately; residual drift: "stop producing outbox messages" vs the
earlier fix, Redis dropped silently)
Recurring: sd-3, sd-4, sd-5 (canvas drift), sd-8 (outbox vs status publisher), **sd-9** (consumers drawn
writing to Elastic/NoSQL directly *and* via the outbox; "lag the burst until 7 AM" decided before
asking the freshness SLA and not revisited when "5 s at any time" arrived).
Drill: when a new requirement or answer arrives, say "does this change anything I already decided?"
out loud; at each phase boundary, re-read the canvas against what's been said.

**LOW — Security precision for payments/PII data** (downgraded per Calibration: principle level
is enough; legal bases, PCI scoping detail and regulatory names are bonus. Still worth saying the
technical basics unprompted: authZ/ownership, webhook signature + dedupe, encryption at rest and in
transit, rate limiting.)
Recurring: sd-3 imprecise; sd-4 correct (same-day priming); sd-5 solid baseline (JWT, mTLS,
encryption at rest, log masking, vault tokens) **but PCI mis-scoped to bank accounts again**
(sd-3 + sd-5, corrected on one probe), **no authZ/ownership check**, **no SCA** for setting up a
payment to a new payee, no rate limiting, no service identity for executions with no user present.
Drill: Security checklist must open with "who may do what to which object" (authZ) and, for any
money-moving setup flow, "SCA/step-up?". PCI = card data (PAN) only.

**LOW — Sanity-check every estimate before using it** (downgraded from HIGH; sd-8: peak factor
dropped when recomputing at 10x, storage 10x misstated — conclusions held; sd-9: write-side peaks
all right, but the **read volume of a read-heavy service was never asked** — for read-heavy prompts,
size reads first)
Recurring: sd-3/sd-4 failures → 2026-10-02 drill → **sd-5 clean**: every rate right first time,
storage explicitly compared ("360 GB/yr fits one DB, even 3–5 years") and used to decide no
sharding. One clean mock; a second one moves it to RESOLVED (same bar as implicit requirements).
Residual watch: peak *within* the day (assumed the 1st's load spread over 24h — ask "do these all
fire at the same time?") and a comparison sentence for QPS, not just storage.

**LOW — Justify each component by need (simplicity)** (sd-11: read replicas + read-your-writes routing
at ~3 QPS — a habit carried over from high-volume mocks; size infra to *this* prompt's numbers)
Downgraded from MEDIUM: sd-3/sd-4 scored 3, **sd-5 scored 4** (no sharding, no cache, conditional
provider queue). Watch for one more mock.

**LOW — Session leadership: close with risks, and self-start L-R-G**
Recurring: improving strongly; sd-5 again no hand-back, closing summary self-driven (added
deployment + monitoring). Remaining: no explicit local → regional → global staging in sd-4 or sd-5;
the summary recaps instead of naming open risks; no questions for the interviewer at wrap-up
(have 1–2 ready).
Drill: closing script "With more time: (1) … (2) … (3) …" ranked by risk; open Phase 4 with "first,
what breaks within one region" — **after** the residency cell opener above.

## Positive signals worth reinforcing (not gaps)

- **Failure handling vocabulary is a strength** (sd-4: 4/5, sd-5: DLQ, ack-after-success, provider
  circuit breaker + rate-limited backlog drain, canary per service, queue depth/age + provider error
  rate monitoring — all unprompted).
- **Idempotency** named in every SD mock — but sd-5 shows *naming* ≠ a structurally sound key (see
  HIGH exactly-once item).
- **Quorum-based regional failover** — reproduced again in sd-5 (majority-connectivity + priority
  list), plus a sensible domain-specific alternative ("don't promote, wait for Europe — payments
  tolerate delay"), though the two weren't reconciled.
- **Estimation drives decisions** — sd-5's "no sharding" came straight from the numbers.
- **Trade-off justification with cost** — sd-4 best; sd-5 kept stating trade-offs (one vs two
  tables, wait vs promote), though some flipped without naming the reversal.
- Fast, non-defensive self-correction on a single probe (every mock — sd-5: PCI, outbox).

## PRACTICED IN COACHING — AWAITING NEXT MOCK VERIFICATION

Per [[coaching-drill-vs-mock-evidence]]: this is coaching-session evidence, not mock evidence — it
can surface or reinforce a gap, but doesn't promote anything to RESOLVED. Only a future full mock
does that. (Two prior entries here — the RAPID SD DRILL and the strong-consistency teaching pass —
are now confirmed by sd-2 and have moved to RESOLVED above.)

- **2026-10-07 — lite mocks sd-17/18/19-focused** (card spending limits, restaurant tables, stock transfers with offline scanners;
  planned 9, stopped at 3).
  - **"Unique within what?" 2 of 3**: right for the processor event and the partner request id; **missed for a per-device scan_id**
    (fixed on one challenge). Keep asking it for every external id.
  - **Numbers copied wrong onto the canvas, 3 cases running** (20M vs 2M, 200k vs 300k, events ×0.9) — the decision followed the wrong
    number until challenged. Habit: read each sticky back against the stakeholder's answer before deriving.
  - **External snapshot vs own state** (sd-17 edge case): provider's captured total treated as input to our counters; "committed reads"
    as protection against a stale HTTP read. Rule: apply each external event once; reconcile only to close.
  - Counters on secondary transitions: improving — sd-19 late scans compensated (+8) unprompted in shape; sd-17 partial capture release
    needed 3 attempts.
  - Positive: invariant enforced by a **partial UNIQUE** (sd-18), invariant table drawn first in all three, conditional transitions and
    lock order habitual, upsert on first challenge, edge-case premises found in Phase 1 (sd-17 timeout leak, sd-19 unordered scans).
  - Recurring minor: precomputed user × place distances (sd-16, sd-18) → "geo index, nearest-N"; time-condition direction slip; states
    not presented as a transition table.

- **2026-10-06 — "lite mock" stock series (sd-13/14/15-focused), 3 cases before the next full mock.** New format set
  by the candidate: full flow led by the candidate but scoped to F → N → flow/blocks → states → one hard edge case, no
  security/deployment/monitoring boilerplate; from case 2, live challenges that point at the problem (answer only if
  stuck). Cases: online store inventory (counter + 15-min hold, hot SKU), multi-channel sync with marketplaces we don't
  control (oversell tolerance, buffer, negative counter + backorders), perishable grocery stock (batches, FEFO,
  sellability per delivery date).
  - **Timer races: held unprompted** in case 1 (conditional transition, 0-rows branch, late success → re-reserve or
    `refunded`) and in case 2's edge case (durable `canceled` + outbox before the external call). Drill evidence only —
    the sd-12 MEDIUM item still needs a mock.
  - **Recurring across the 3 cases — invariants/counters dropped on secondary paths**: the main reserve path was right
    every time, but releases and re-checks on other paths needed challenges (case 1 failed callback — self-caught;
    case 2 cancel release + `CHECK >= 0` vs unrejectable orders; case 3 release on `failed`, double decrement at pick,
    sellability forgotten on reallocation). Habit to carry into the mock: **for every state transition, say what
    happens to the counters and which invariant it re-checks.**
  - **Replica reflex** (cases 2 and 3): read replicas at ~100 / ~21 QPS; case 2 from a ×1000 slip ("100k QPS is low").
    Defended in case 3 as availability → corrected to hot standby. Estimate item: compare before deciding.
  - **Stakeholder facts / the prompt's key concept applied late**: case 2 "reply with an error so the marketplace
    refunds" vs "already sold"; case 3 expiry rule asked only after two pointers.
  - Positive: F → N → core flow order fixed after case 1 and held; conditional transitions and lock ordering habitual;
    outbox reused unprompted; flow-by-flow table walk worked in case 1 (dropped in case 2 → table drift returned).
  - Concept taught: buffer sizing = sales velocity × sync window (not stock level); short lock window + SKIP LOCKED
    false "out of stock" (MAX vs SUM check, API-side retries, code in the case 1 discussion).

(The entries below predate sd-3/sd-4. Their open questions — implicit requirements unprompted,
D-I-S-E depth under the clock, quorum failover recall — were answered by those mocks; see RESOLVED
and Positive signals above.)

- **2026-09-30 — back-of-envelope numeracy + storage-selection drill (2 scenarios), building the
  new `coaching/sd-interview-checklist.md` script.** Grew out of the candidate flagging that they
  find it hard to remember every point to cover per phase ("me resulta dificil acordarme de todos
  los puntos"), and separately that they didn't see the point of asking for NFR numbers if the
  numbers "don't change the design." Built a memorization script (F-N-I / skeleton / D-I-S-E / L-R-G
  mnemonics + mid-session checkpoint + a "never say anything else?" rule) directly targeting sd-2's
  session-completeness gap, plus reference tables (5 anchor capacity numbers, storage-technology
  decision table) now persisted in that file for standing use.
  - Scenario 1 (photo-sharing app): first attempt had a real conceptual unit error — multiplied DAU
    by 7 to "get a week's worth of users" (140M) instead of recognizing DAU already represents the
    recurring daily user base the weekly per-user rate should apply to directly. This inflated WPS
    7x (462 vs. correct 66) and drove an incorrect sharding-from-day-1 conclusion. Self-corrected
    within one challenge once the conceptual error (not just the arithmetic) was named, and
    correctly reversed the sharding conclusion using the corrected number — a clean demonstration of
    why the NFR math matters (it can flip a real architectural decision), which is the candidate's
    own original question, now closed with a concrete example.
  - Scenario 2 (ride-hailing GPS pings): math was correct on the first attempt this time (no repeat
    of the DAU-conflation error) — 312.5K writes/sec average, 3.12M peak. But then reached by reflex
    for "shard a relational DB into 10,000 pieces" rather than questioning whether the access pattern
    (overwrite a driver's current position) needed a relational store at all. This is the same
    reach-for-the-familiar-tool instinct as the RESOLVED "is there an invariant" item, but applied to
    a different axis — storage *category* fit, not invariant strength. Self-corrected in one
    challenge to Redis (pure key lookup, no relational need), then correctly recognized unprompted
    that a single Redis node's throughput ceiling (per the anchor-numbers table, hundreds of
    thousands of ops/sec) is still below the 3.12M peak, landing on Redis Cluster.

  Coaching evidence only, not mock evidence — worth watching in a future mock whether "match the
  access pattern to the storage category, don't default to sharding what you already know" holds up
  under live pressure, the same way the original invariant-check habit did.

  - Scenario 3 (banking audit log): storage growth over 3 years + sharding decision + hot/cold
    tiering (recent data in the operational store, older data archived to S3/Glacier) — the
    strongest, most complete answer of the whole session, correct on the first pass.
  - Scenario 4 (video streaming bandwidth + CDN offload + origin node count): correct instinct on
    CDN as the standard fix for massive aggregate bandwidth (connected unprompted to the "celebrity
    problem" from the earlier Design Twitter study video), then correctly generalized the
    node-count formula (total demand ÷ per-node capacity + redundancy margin) from the earlier
    Redis Cluster reasoning in scenario 2 to a completely different resource type (network
    bandwidth) — a second instance of a lesson transferring across contexts within one session.
  - Scenario 5 (SLA/availability budget: 99.9% vs 99.99% downtime-per-year, then whether a 30-40 min
    failover fits the annual budget): recurring error type surfaced 3 times today — forgetting to
    convert a percentage to a decimal fraction (dividing by 100) before using it in a calculation,
    each time producing an answer off by a clean power of 10. Self-corrected each time once
    challenged. Also caught, live, a good general debugging technique worth reinforcing: comparing
    the *relationship* between two related computed values (more nines should mean less downtime,
    not more) to sanity-check a result without redoing the full calculation.
  - Process note, not a candidate gap: I (the coach) misread the candidate's Spanish-locale decimal
    comma as an English thousands separator twice in this session, wrongly "correcting" one answer
    that was actually right. Logged to personal memory
    (`feedback_spanish_decimal_notation`) so it doesn't recur in future sessions.

  Overall pattern for today's numeracy drilling: the recurring failure mode isn't conceptual
  (storage-category choice, sharding-vs-not judgment, CDN/tiering instincts were all sound or
  quickly self-corrected) — it's mechanical: percent-to-decimal and unit-magnitude (Mega/Giga/Tera)
  conversion slips, consistently self-caught in one challenge once flagged. Worth a lighter-weight,
  higher-repetition drill (many quick unit-conversion reps) rather than another full scenario cycle,
  if this resurfaces.

  - Scenario 6 (push-notification flash sale: audience %, QPS to hit a time window, delivery
    success %): first scenario of the session with a clean pass on percent math, no conversion
    error — the mechanical slip from scenarios 1/3/5 may already be settling with repetition.
    Third independent application of the "total demand ÷ per-node capacity" formula (after Redis
    Cluster in scenario 2 and origin bandwidth nodes in scenario 4), this time to queue consumers —
    the generalization is holding up cleanly across a third, unrelated resource type.
  - Scenario 7 (search autocomplete: QPS math clean again, then storage-type choice) — QPS math
    correct with no conversion error. But the storage pick was a genuinely new failure mode, and the
    most over-engineered instinct of the session: proposed using an LLM for prefix completion,
    reasoning "it's a perfect text predictor." This is the *opposite* direction from the earlier
    "reach for the familiar heavy tool" pattern (that was about defaulting to known distributed-
    systems machinery like sharding/2PC) — this is reaching for a trendy ML solution that is both
    far too slow/expensive for the latency+QPS budget AND solves the wrong problem (generates
    plausible text instead of surfacing what other users actually searched). Corrected directly
    (not self-corrected — this was a genuine knowledge gap, not a pressure slip) to the standard
    pattern: a precomputed Trie or Redis sorted set (`ZRANGEBYLEX`) built offline from real query
    logs. Worth watching for in a future mock — an LLM-shaped answer to a component that should be a
    simple precomputed lookup.
  - Scenarios 8-14 (URL-shortener keyspace sizing, celebrity fanout, latency-budget decomposition,
    Little's Law concurrency, infra cost estimation, cache working-set sizing, hot-shard/skew):
    broadest single-session coverage of calculation *types* yet — combinatorial keyspace sizing,
    burst/instantaneous load, additive latency budgets across a sync call chain, queueing-theory
    concurrency, $ cost trade-offs, memory-capacity sizing, and skewed-key hot-shard risk, on top of
    the throughput/storage/percent/bandwidth types from scenarios 1-7. Notable moments:
    - Scenario 8: a genuine input-transcription slip (read "500M" as "50M"), different in kind from
      the percent/unit-conversion errors earlier — correctly self-corrected, and correctly explained
      *why* it didn't change the final answer (base62's exponential growth absorbs a 10x input
      error in this range), a useful nuance rather than just a lucky pass.
    - Scenario 9 (celebrity fanout): initially proposed a heavier fanout-on-write-via-sharded-Redis
      alternative alongside the correct fanout-on-read answer; the real gap surfaced was a common
      misconception that fanout-on-read implies slow reads from a DB — didn't initially realize
      celebrity content is itself highly cacheable regardless of fanout direction. Self-corrected
      cleanly once challenged, landing on the standard hybrid (push for normal users, pull+cache for
      high-follower accounts) with a well-reasoned threshold-by-ops/sec framing.
    - Scenario 10 (latency budget): small arithmetic slip (dropped one line item summing the
      synchronous call chain, 130ms vs. correct 125ms remaining budget) — same "don't drop a term"
      discipline theme as the rest of the session. Design reasoning itself was strong: correctly
      distinguished a precomputed/independent risk signal (fine to run "before" authorization) from
      a transaction-dependent fraud check (needs async + compensation, correctly named unprompted).
    - Scenarios 11-14: clean passes throughout — Little's Law applied correctly for WebSocket
      concurrency sizing, cost trade-off math correctly used to justify the earlier hot/cold storage
      tiering decision in dollar terms, cache memory sizing correctly checked against a node-RAM
      threshold instead of assuming sharding was needed, and — the strongest moment of this back
      half — correctly identified a hot-shard risk hiding behind a healthy system-wide average, then
      unprompted named the real cost of the fix (subsharding one outlier hotel sacrifices the
      single-shard read locality every other hotel still has).

- **2026-09-30 — F (functional requirements) practice: actor identification.** First time this
  specific sub-skill was drilled (F itself hasn't shown up as a gap in either mock, unlike N and I,
  but "for whom" — identifying every actor type, not just the obvious one — was untested). Prompt:
  food-delivery platform. First pass named only 2 of 3 actors (consumer, restaurant owner), missing
  the delivery driver entirely — the role that makes "delivery" the point of the whole system.
  Self-corrected in one challenge once pointed at the verb "reparto" in the prompt itself, then
  correctly built out the driver's full lifecycle (pickup → in-transit status → deliver) unprompted.
  Closing heuristic given: parse the verbs/nouns in the problem statement itself for implied actors
  before closing the requirements phase. One data point — watch whether actor-completeness holds up
  in a future mock's Phase 1.

  Continued across 6 total F scenarios (food delivery, medical appointments, event ticketing,
  crowdfunding, insurance claims, bank account/KYC onboarding) — three distinct sub-skills drilled:
  (1) finding a hidden actor via noun/verb parsing (food delivery, ticketing) or via business-risk
  reasoning when no noun points to it (crowdfunding's moderator — explicitly connected in-session to
  the I skill: "who gates this for implicit-risk reasons" is the same muscle as implicit
  requirements, just applied to actors instead of requirements); (2) operation symmetry — every
  create/accept also needs its cancel/reject counterpart (medical appointments); (3) not correctly
  identifying an actor when there isn't a third one, and instead catching domain-genericity —
  insurance claims was modeled as a generic support-ticket system at first, missing
  claims-specific operations (evidence submission, an actual accept/reject decision vs. a generic
  status change) until pushed. Bank account/KYC onboarding (F-6, the closest domain to Revolut's
  actual business) was solved correctly on the first pass with no missing actor — good sign this is
  becoming reliable.

  Then pivoted to 4 dedicated I scenarios (personal lending, P2P car rental, teen photo-sharing
  social app, telemedicine), each testing the same discipline from a different angle:
  - Personal lending: first pass wrongly imported booking-family items (double-booking invariant,
    cancellation policy) into a non-booking domain — a direct violation of the "identify the domain
    family first" instruction given minutes earlier. Self-corrected when challenged, and the
    lending-specific items taught (responsible lending/affordability check, interest rate caps,
    credit bureau reporting) were then applied correctly.
  - P2P car rental: the mirror-image error — over-applied a fintech item (AML) to a non-financial
    marketplace, while under-applying genuine booking-family items (no-double-booking, cancellation)
    that *do* belong here. Self-corrected both directions when challenged on each specifically.
    Domain-specific check (driver's license) was named correctly unprompted; a second, non-standard
    guess (criminal background check) was gently downgraded; insurance/liability (arguably the
    single most important implicit requirement for this domain) had to be taught directly.
  - Teen photo-sharing app: correctly named GDPR, content moderation, and age verification
    unprompted — but stopped at "verify age" without the follow-on regulatory step (COPPA/GDPR
    Art. 8 parental consent) that age verification exists to trigger. Genuine knowledge gap, taught
    directly.
  - Telemedicine: correctly named GDPR, health-data protection/consent, and mandatory record
    retention unprompted, cleanly scoped to the healthcare family with no cross-contamination from
    other families — the best-scoped first pass of the four. Missed the telemedicine-specific
    cross-jurisdiction medical licensing issue (a doctor needs to be licensed where the *patient* is,
    not just be "a licensed doctor") — genuine knowledge gap, taught directly.

  **Overall read on the I item**: the domain-family filtering discipline (don't drag items across
  families) is landing — both misapplications today were caught and corrected in one challenge each,
  and by scenario 4 the family-scoping was clean from the first pass. What's still genuinely missing
  is domain-specific knowledge beyond the taught framework (lending affordability rules, car-rental
  insurance, COPPA/GDPR Art. 8 parental consent, cross-border medical licensing) — these are facts
  to accumulate, not a reasoning gap, and each was absorbed in one pass once taught. This is
  coaching evidence only; the real test is whether unprompted implicit-requirement-naming shows up
  in sd-3's Phase 1 without any of this scaffolding present.

- **2026-10-01 — Skeleton (Phase 2) practice, 3 scenarios drawn in Excalidraw (QR payment, insurance
  claims, doctor appointments), then one full D-I-S-E (Phase 3) deep-dive on a subscription billing
  system.** Context: skeleton was never a weak area (4/5 both mocks) — practiced anyway to build
  habit; D-I-S-E was the real target, since sd-2 scored DB design 2/5 (never reached) and Security
  2/5 (JWT only).

  **Skeleton (3 diagrams)**:
  - QR payment service: missed the auth/pre-flow step entirely on first pass (self-corrected to an
    Auth Service box when challenged); initially defended a single monolithic "API Service" doing
    everything, then correctly distinguished that as a deployment choice, not an excuse to skip
    naming distinct logical responsibilities (echoing sd-2's "not a monolith-in-boxes" finding
    directly — same critique, same self-correction once reconnected to its source).
  - Insurance claims: auth correctly gated both actors unprompted this time (direct improvement).
    Unprompted, correct generalization of the hot/cold storage-tiering pattern (from an earlier
    numeracy scenario) into an "archive worker" component — a coaching lesson surfacing correctly in
    a completely different exercise type. But two explicitly-given F operations ("revisar
    reclamación", "consultar estado") were dropped from the diagram — candidate's own explanation:
    preferred a cleaner base-skeleton-plus-per-action-diagram technique and deferred fixing it to the
    next scenario (a reasonable diagramming practice, validated as such, but completeness doesn't
    automatically follow from better diagram hygiene — flagged as a distinct axis).
  - Doctor appointments: applied the previous scenario's feedback immediately — explicitly listed
    read actions separately from write actions for both actors, closing exactly the gap just
    flagged. Correct scale math (20k/day → 0.23 writes/sec → no sharding) and detailed, well
    thought-out AUTH flow — which surfaced a genuine design flaw (JWT validated via a network
    round-trip to Auth Service on every request, defeating JWT's main advantage over opaque session
    tokens). Self-corrected immediately to local signature verification once challenged, then
    correctly extended to asymmetric (RS256) vs symmetric signing and why distributed verifiers
    need asymmetric. Follow-on Q&A (not evaluated, pure teaching) covered OAuth/OIDC federated login
    end-to-end (authorization code exchange, ID token vs access token, scope-based authorization,
    refresh tokens) and a sharp, candidate-initiated security question: if auth is federated via
    Google, where does a domain-specific role (doctor vs. patient) come from, and can the frontend be
    trusted to assert it? Correctly intuited the answer should not be "trust the client" before being
    told; the resolved pattern (never trust client/IdP for role claims, resolve against your own DB,
    mint your own signed JWT) is now in the checklist's Security section.

  **D-I-S-E deep dive (subscription billing system)** — the strongest single Phase-3 walkthrough of
  the whole prep:
  - *D*: correct scale math (0.77 writes/sec, no sharding), SQL choice justified with a concrete
    example (not generic "transactions are good for payments") once pushed once. First schema draft
    had four real gaps — missing idempotency_key on `payments` (despite having just described a
    retry flow that needs it), missing subscription status/next-billing-date entirely (making the
    stated cancel-subscription requirement and the scheduler mechanism both unimplementable against
    the schema as drafted), a `CHECK` constraint typo, and a `NOT NULL` column (`invoice_url`)
    directly contradicted by the status enum including `'creating'`. All four corrected in one pass,
    including a technically correct idiomatic SQL fix (`CHECK (status != 'completed' OR url IS NOT
    NULL)`). Indexing: correctly ordered a composite index (equality column before range column, a
    common error point) unprompted, then needed one nudge to recall that Postgres does not
    auto-index foreign keys (unlike MySQL/InnoDB) — once reminded of the actual F operations list,
    correctly derived exactly one missing index (`invoices.user_id`) and correctly ruled out the
    others as PK-based.
  - *I*: full outbox-driven saga (payment leg → invoice leg) with correct transactional precision —
    when pushed on whether the payment-completion transaction also atomically writes the
    invoice-trigger outbox message (not a separate, riskier step), confirmed yes correctly. Caught
    and resolved an internally ambiguous description (sounded like two different invoice-creation
    trigger mechanisms, a DB poller and an outbox consumer) when asked to state the single trigger
    path explicitly — confirmed only one, and correctly named it as a two-step saga unprompted.
    Deliberately minimal caching (no cache unless read replicas can't meet the SLA) — good restraint,
    not reflexive over-engineering.
  - *S*: PCI/tokenization and encryption-in-transit (TLS termination at LB) correct by default.
    Initially proposed CDN-served invoices with no access control until prompted — correctly reached
    for signed URLs, justified the choice over a password-protected-PDF alternative on a genuine
    user-experience trade-off once asked to commit to one. Encryption **at rest** was dropped
    entirely on the first pass (only "in transit" was covered despite the topic naming both) —
    corrected cleanly once flagged (column-level encryption via a Postgres extension, or
    volume-level). Rate limiting's first answer ("the cloud provider handles it") was a real gap —
    too vague to count as a design decision; second attempt (per-user, per-endpoint, calibrated to
    real read/write ratio) was adequate.
  - *E*: correctly reasoned through worker-crash durability, duplicate-payment idempotency, and
    short vs. long payment-provider outages (circuit breaker). Two follow-ups needed: the "abandoned
    message" detect/recover mechanism (resolved correctly and precisely — ack/visibility-timeout
    redelivery, DLQ as backstop) and, strongest moment of the whole session, the **post-outage
    backlog recovery** question — unprompted connected it to the earlier celebrity-fanout numeracy
    lesson about bursts, and proposed a half-open circuit breaker with a rate-limited, gradually
    increasing throughput ramp — structurally the same pattern as their own canary-deployment design
    from the Infra section, applied to traffic instead of code, without being told to make that
    connection.

  **Net effect on tracked priorities**: this is the single most convincing coaching-session evidence
  yet that the two weakest sd-2 scores (Database design 2/5, Security 2/5) reflect a *coverage* gap
  from running out of session time, not a *reasoning* gap — once given the time and prompting to go
  deep, both were handled with real precision, including catching self-made schema inconsistencies
  unprompted-adjacent (quick once flagged) and generalizing patterns across completely different
  problem types (storage tiering, canary rollout, burst handling) without being told to. Per
  [[coaching-drill-vs-mock-evidence]], still coaching evidence, not mock evidence — the real test is
  whether this depth survives under sd-3's actual time pressure, where Database/Security/Scaling
  have to compete for the same clock as everything else, which is precisely the sd-2 failure mode
  this needs to overcome.

  **Same session, continued — L-R-G (Phase 4) on the same subscription billing system, pushed to
  200M subscriptions across EU/US/APAC.** Correct scale math (200M/month → 77 writes/sec, still
  below the sharding threshold). First pass gave a complete, well-reasoned global end-state directly
  — including, unprompted, a replica-promotion failover mechanism for the single-write-region SPOF,
  a direct, concrete improvement over sd-2's real mock (where that same SPOF was accepted with zero
  mitigation). But skipped the explicit local→regional→global staged narrative Karim's framing asks
  for — same "jump to the answer" pattern as elsewhere today, applied to narrative structure rather
  than technical content; redirected and corrected immediately when asked to re-narrate in stages.

  The standout moment of the whole two-day session: asked to identify what's genuinely new at 3+
  regions vs. 2, candidate initially said "nothing, same problem" — then, under challenge, surfaced
  the real split-brain risk in their own proposed priority-ordered failover list (a static list
  doesn't verify the old leader actually stopped, so an isolated-but-alive EU plus a promoted US
  produces two simultaneous write-leaders). First correction attempt (decide master by comparing
  "majority of traffic" between regions) was reasonable-sounding but logically circular — correctly
  diagnosed in the teaching pass as impossible to measure *during* the very partition it's meant to
  resolve. Second attempt, after being taught the quorum-of-replica-nodes mechanism (not traffic, not
  external visibility — each node unilaterally counts how many of the known node set it can currently
  reach), correctly synthesized a working mechanism: self-demotion on loss of quorum, priority-list
  as tiebreaker among the majority side only. This is genuinely advanced material (the core mechanism
  behind Raft/Paxos, explicitly flagged as a "stretch" DDIA chapter never completed in the theory
  pass) — worked through to a correct answer via teaching plus two iterations, not recalled from
  prior study.

  Degraded-mode question (what to deliberately let degrade under stress): correctly identified
  billing/invoice processing as the right thing to deprioritize (already async, wide tolerance
  window, vs. tight-SLA interactive user requests) and, once pushed for the concrete mechanism,
  named pausing/rate-limiting the scheduler — the same mechanism already designed for payment-
  provider-outage recovery, now correctly reapplied symmetrically for self-protection under load.

  **Overall**: this is the strongest technical session of the whole prep arc. The real open question
  is unchanged from the D-I-S-E entry above — everything demonstrated today required coaching time
  and, in the quorum case, direct teaching of genuinely new material; sd-3 is what tests whether any
  of it holds up unprompted, under the clock, without a coach available to redirect when the
  narrative jumps ahead of itself.

- **2026-10-02 — RAPID SD DRILL on the two HIGH items (estimate sanity + data residency), 7
  scenarios.** Coaching evidence only — does not resolve either item.

  Estimation (S1 round-ups, S3 KYC uploads, S5 FX websocket push, S7 fraud feature cache):
  - **Comparison-sentence habit landed mid-session**: absent in S3 (went straight from number to
    design), present unprompted in S1 (thin) and S5 (vs server NIC, correct), partial in S7.
  - **Wrong anchor selected for the resource — 2x, the most diagnostic pattern**: S1 used cloud
    ceilings (RDS max IOPS/storage) as design thresholds; S7 applied on-disk DB storage anchors
    (TB, vacuum) to an in-memory cache. Comparing is now habitual; *choosing the right yardstick*
    isn't yet. Replaced the old 1-5K rule with 🟢🟡🔴 zones + memory/bandwidth/websocket/egress/
    object-storage anchors in `coaching/sd-interview-checklist.md`.
  - **Dropped term / unit slip — 2x** (S3: 20% retries applied to photos not video; S7: 60 GB vs
    15 TB/partition). Mechanical, self-caught on challenge, consistent with 2026-09-30.
  - New concepts taught: rows-per-business-event in fintech (double-entry: 1 money movement ≈ 5
    row writes — moved S1 from 🟢 to 🟡); the binding resource (S5: messages/s needed ~150 servers
    vs ~10 for bandwidth or connections); "write/send less before scaling" (batching, subscribed
    pairs only, delta encoding = 100x); cost per month as the object-storage comparison.
  - Good scoping questions before computing (S3 retention of failed attempts, S7 total vs per-
    window size, S7 memory-only scope).
  - S7 skipped failure/recovery of the cache until told (HA replica per shard, rebuild derived
    data from the event log).

  Data residency (S2 shared account EU+US, S4 global fraud model, S6 offshore support centre):
  - **Instinct is now correct first time in all three** — home-region data, minimisation at
    source, only what's needed crosses, remote access recognised as a transfer (S6, a point many
    miss). Clear improvement over sd-3/sd-4.
  - **Recurring mistake-selection: reaching for user consent as the legal basis — 2x** (S2, S6).
    Taught: contract necessity / SCCs (+ TIA) / adequacy / DPF; consent is a last resort; AML
    retention overrides erasure.
  - Knowledge gaps taught directly: pseudonymised ≠ anonymous (S4); the legal entity holding the
    account decides its home region, not traffic/cost (S2); federated learning by name (S4); VDI
    / remote browser isolation, DLP, break-glass, just-in-time case-scoped access (S6).
  - Proposing a same-region-only MVP (S2) is the simplicity move to reach for.

  Watch in sd-5: right-yardstick comparison sentences; residency stated unprompted in Phase 4
  without saying "consent".

- **2026-10-03 — post-sd-5 coaching: calendar modelling, peak re-estimate, and a teaching pass on
  cells / cross-cell sagas.** Coaching evidence only — resolves nothing.
  - Self-diagnosis of sd-5 named calendar/time-zone and residency, but **not** the exactly-once
    failures (dual write, random idempotency key, check-then-act) — had to be pointed out.
  - Calendar fixes landed quickly: start as a date, period as a calendar choice, 09:00 in the
    user's time zone; month-end clamping and "derive occurrence n from start_date, not from the
    previous execution" correct on first ask. Taught: IANA zone names (DST), weekend/holiday rule is
    a business trade-off and only applies to batch schemes, PSD2 "deemed received next business
    day", requested vs settlement date, push (standing order) vs pull (direct debit).
  - Peak re-estimate with time-zone execution: 1,111 executions/s right; then executions × 9 row
    writes computed with an **unclear unit** ("3,333 on each instant" — correct per-hour figure is
    ~10k writes/s, burst 36M) — same instant-vs-rate slip family as earlier drills. Conclusion
    (spread/throttle, only the day matters) right; taught overnight materialisation + throttled
    executor.
  - **Cells were genuinely new material, not a recall gap** — asked for a worked example twice
    ("no me ha quedado claro"), then for table-by-table writes per cell. Needed concepts taught
    from scratch: cell = full stack per legal entity; external payment never touches another
    Revolut cell; inter-cell payment API; double-entry and why each cell needs an inter-entity
    account (separate regulated balance sheets, net daily settlement); deterministic payment_id
    vs natural key; payment schemes (SEPA SCT/Inst, FPS, ACH, SWIFT) — had only heard of SEPA/SWIFT.
  - First attempt at the cross-cell flow put a separate "transfer service" call **after** writing
    both ledgers (ledger treated as a log, not as the money movement) and sent the payer id but
    not the payee ref or payment_id. Retry/compensation answer: idempotent retries + compensate
    after N retries — then, on the partition scenario, proposed "UK compensates and tells EU to
    compensate too" (temporary double money + reversing a credit the payee may have spent).
    Taught: compensate only on a definitive answer from the committing side; `expires_at` +
    receiver-side tombstone; deadline-based retries.
  - All of the above added to `coaching/sd-interview-checklist.md` (time row in implicit table,
    money-path per-hop checks, Phase 4 cells section with opener, cross-cell flow, legal-basis table,
    schemes).
  - Candidate explicitly asked for **many more cases** of this kind: transfers, multi-cell /
    multi-region, legal placement of data ("qué va en cada sitio"), sagas, edge cases,
    compensations. Next sessions: RAPID SD DRILL scenarios built around those, then sd-6 to verify.

- **2026-10-04 — RAPID SD DRILL: 5 different fintech products, increasing difficulty** (format
  requested by the candidate: blocks / flow + transactions / async / where it lives / one failure,
  no full mock). Earlier the same session (2026-10-03) a case-1 cross-cell FX variant was done and
  a cross-cell "user relocates" case was rejected by the candidate as too convoluted — they want
  breadth across product types, not deeper variants of transfers. Coaching evidence only.
  - Cases: (1) KYC onboarding, (2) savings vault with daily interest, (3) cashback engine,
    (4) share trading via external US broker, (5) real-time card fraud scoring (<50 ms, global
    model).
  - **Recurring strengths (5/5)**: outbox + relay, conditional UPDATE for caps/limits,
    idempotency keys sent to providers, circuit breaker with half-open + rate-limited recovery,
    DLQ + status-query reconciliation, "unknown ≠ failed" (case 4, applying the saga lesson from the
    day before). Asked good clarifying questions before designing (cases 2–4) — one re-ask of a
    settled answer (vault withdrawals).
  - **Recurring mistake-selection — "fix values at event time" missed 2x**: FX rate looked up on
    retry (cross-cell FX case) and partner cashback % looked up on day 8 instead of at clearing
    (case 3). Same root: re-evaluating a mutable input downstream instead of carrying it in the
    message/row. Taught as one rule ("retries/delayed jobs must be deterministic").
  - **Domain mechanics were the main knowledge gap, not reasoning** — each needed teaching:
    vendor `refer` outcome + sanctions/PEP screening (KYC); one ledger per cell with many accounts
    (vault); card lifecycle auth → clearing → refund/chargeback (cashback); partial fills = many
    execution reports for ONE order, not a new order — candidate defended the new-order model once
    (would double-buy) (trading); available vs booked balance + holds table, price collar (trading).
    Fraud: no model-serving block, no latency budget breakdown, read-replica lag on velocity
    features.
  - **Data classification / precision**: HMAC proposed for a non-personal partner-merchant list
    (over-protection); "HMAC encryption" (HMAC is keyed hashing); random token for a phone lookup
    (needs a deterministic keyed hash); signed URL for passport images valid 1 week.
  - **Legal basis still not recalled**: KYC → SCCs before DPA/in-region vendor; fraud training →
    "no idea" (fraud prevention is the GDPR-named legitimate interest, Recital 47). Same gap as the
    2026-10-02 drill ("consent" 2x). Facts-to-accumulate, but they're exactly what a Revolut
    interviewer asks.
  - Idempotency by constraint (vault accrual `UNIQUE(account_id, accrual_date)`) had to be pointed
    out again — batch cursors were offered as the safety mechanism.

- **2026-10-05 — "State machine → table" drill, 3½ booking cases** (gym classes, restaurant tables, car
  rental, doctor appointments — stopped during the tables of the last one, candidate tired but "sees the
  concept"). Staged format (states → tables → queries) with direct corrections, no challenge questions.
  Coaching evidence only.
  - **Landed**: one table + status vs separate tables ("does the waiting thing become the same entity?");
    entity separation (reservation lifecycle vs table/car availability derived from active rows);
    partial unique index for "one active per slot"; walk-in as `checked_in` with an explicit `source`;
    `car_id` NULL until pickup; capacity per category *per day*; index-only reasoning (own index choice
    beat the coach's in case 3).
  - **Recurring slips (same family as the HIGH item)**: states used in transitions but missing from the
    CHECK (`no_show`, `checked_in`), missing date in a uniqueness key, transition timestamps declared
    NOT NULL, duplicated slot data that a reschedule must keep in sync; condition-of-origin forgotten in
    the "easy" UPDATEs (check-in, overdue return), off-by-one / arithmetic on the indexed column in a
    timer, `FOR UPDATE` without `LIMIT … SKIP LOCKED`.
  - Coach process note: twice gave more than asked (full solution in case 1; a new capacity table in
    case 3 that confused the candidate) — stay inside the candidate's model and stage.
  - Pending: the "Timer races" block.
