# sd-5 — Scheduled & recurring payments

Date: 2026-10-02
Problem: Design a system that lets Revolut users schedule payments, either one-off on a future date
or recurring (for example, paying rent every month).

Session artifacts: `sd-sessions/sd-5/notes.md`, `sd-sessions/sd-5/01-hld.png`,
`sd-sessions/sd-5/02-tables.png`, `sd-sessions/sd-5/03-tables2.png`.

## Scores (1-5)

1. Requirements clarification: **3**. What went well:
   - You asked the right scale questions and turned the numbers into rates correctly first time:
     11.57/s average, ~139/s on the 1st, ~58 QPS reads, <6 WPS management.
   - You sized storage (1 KB/row → 360 GB/year) and **compared it to something**: "fits one DB,
     even 3–5 years".
   - You raised audit, PII and GDPR unprompted. You also stated the key invariant yourself:
     sufficient balance *at execution time*.

   Deductions:
   - The functional scope stopped at "create": no edit, cancel, list or notify, even though the
     numbers included 200k edits/cancels a day and 5M views.
   - You never asked what happens when a payment fails.
   - You never asked *when* a payment executes: the user's local time, the scheme cut-off, or
     weekends and bank holidays.
   - You never asked what "monthly" means on the 29th–31st.
   - None of the implicit requirements were specific to this domain. Calendar and time-zone
     handling is *the* implicit requirement here.
   - PCI was mis-scoped to bank accounts. You corrected it after one question, but it's the same
     imprecision as in sd-3.
   - A large share of Phase 1 went on table design (1 → 2 → 4 tables) before any user action
     was listed.
2. Session leadership: **3**. You drove every phase transition, opened scaling with residency
   yourself, and closed on your own summary, which included deployment and monitoring. There was
   no "anything else?" hand-back.

   But the core of the prompt is executing each due occurrence exactly once, on time, under the
   1st-of-month spike. It was only walked through when I asked for it. I also had to redirect you
   once (schema in HLD). In total I asked 6 probing questions, and each one exposed something
   material.
3. Communication: **3**. You stated trade-offs consistently:
   - one table vs two (query count vs null columns);
   - relational vs not;
   - wait-for-Europe vs promote-and-compensate.

   But the reasoning flipped without being named as a reversal. The schema went
   1 → 2 → 4 → 2 tables using the same "avoid nulls" argument in opposite directions. Residency
   went "user data must stay in-region" → single EU primary → replicas worldwide within three
   turns. Dictation slips ("13 million", "230 days", "10,000 million") were harmless; the
   interviewer can follow them.
4. High-level design discipline: **3**. The diagram is a clean skeleton (API → DB ← scheduler →
   queue → consumers → providers), and you put destination validation before the write. But you
   designed tables in Phase 1 and again at the start of Phase 2, and you needed the one redirect.
5. Component design: **3**. Good split of synchronous management from the asynchronous execution
   pipeline, independently scalable consumers, a DLQ, and an optional throttling layer in front
   of the providers. Gaps:
   - The balance check lives in the consumer, separate from the debit (see D).
   - Nothing writes the provider result back to the payment row.
   - Nothing receives SEPA's asynchronous confirmations or returns, so `sent → confirmed` has no
     path.
   - The scheduler "can scale but isn't needed", with no coordination between instances, which
     leaves it as a single point of failure on the busiest day.
   - The user is never notified.
6. Database design: **3**. Good:
   - `next_execution_at` is the right hook for finding due schedules;
   - execution rows snapshot amount and destination, which is good for audit;
   - there is an explicit status lifecycle.

   Gaps:
   - **`period_in_days` can't express "monthly on the 1st"**, which is the dominant case. 30 days
     after 1 Feb is 3 Mar, so the schedule drifts within one cycle.
   - Execution rows have **no `definition_id` and no occurrence date**, and the idempotency key
     is a fresh UUID PK. Nothing in the schema stops the same occurrence being created twice.
   - BIC and SWIFT code are the same identifier.
   - There is no payee name, which SEPA needs.
   - There is no schedule status (active/cancelled).
   - `end_at NOT NULL` was changed verbally but the canvas wasn't updated.
7. Scalability reasoning: **2**. Locally the reasoning was strong: no sharding at these numbers,
   which is the right call and the opposite of sd-3. Regionally and globally it fell apart:
   - you stated data residency as the rule, then put a single EU write primary for the world;
   - you then added read replicas everywhere, which means EU PII leaves Europe;
   - "inform the user" was offered as the mitigation, but informing users is not a lawful basis
     for moving the data.

   There was no explicit local → regional → global sequence, no cost vs performance discussion,
   and no graceful-degradation statement. The quorum-ordered failover is a good instinct, but it
   contradicted your later (better) answer of "don't promote, wait for Europe".
8. Security awareness: **3**. You covered JWT authentication, TLS/mTLS, encryption at rest, log
   masking, and vault tokenisation for sensitive fields. You did not cover:
   - authorization: who can view or modify which schedule;
   - SCA / step-up when creating a standing payment to a new payee, which a Revolut interviewer
     will expect;
   - the identity the consumer acts under when no user is present;
   - rate limiting.
9. Edge cases and failure handling: **3**. Strong recovery vocabulary:
   - ack-after-success;
   - DLQ for poison messages;
   - provider circuit breaker, with backlog drain under the provider's rate limit;
   - monitoring of queue depth and age, DLQ and provider error rate.

   But:
   - the dual-write error (see D);
   - the crash after the provider accepted but before the ack was never covered;
   - you never named the double payment that async failover causes;
   - there is no business-level SLI ("% of today's due payments executed by 10:00");
   - insufficient funds → silent `failed`, with no retry and no notification.
10. Simplicity: **4**. Your best area this session. No premature sharding, no caches without a
    stated need, and the extra provider queue was explicitly conditional. This item has improved
    since sd-3 and sd-4, where it scored 3.
11. Time management: **4**. Every phase was reached, including monitoring, deployment and the
    summary, with no time-keeping from me. Phase 1 ran heavy on schema, which cost depth in the
    execution core.

## A. Assessment: BORDERLINE

The process skills are now consistently there: leadership, estimation, simplicity, closing. The
fail risk has moved to **technical correctness in the prompt's core**:

- the exactly-once-per-occurrence path had a dual-write error and no structural idempotency;
- "monthly" was modelled as 30 days;
- data residency was broken for the third mock in a row, this time right after you stated the
  rule yourself.

A Revolut interviewer would likely score this as a capable generalist who hasn't fully closed the
money-correctness and regulatory-topology gaps. That is a coin flip at the final round.

## B. Three strongest things

1. **Estimation drove decisions, with a sanity check.** The rates were right first time, the
   storage was compared to a single DB's comfort zone, and the result was "don't shard". The HIGH
   priority from sd-3/sd-4 fired here, at least for storage.
2. **You owned the session end to end.** You made every transition, closed with your own summary,
   and covered deployment (canaries) and monitoring (queue depth/age, DLQ, provider error rate)
   without being asked.
3. **The execution pipeline is the right shape and stays simple.** It is asynchronous, uses
   at-least-once delivery with idempotency, acks only after success, and has a DLQ. Provider
   degradation is handled with a circuit breaker and a rate-limited backlog drain. Execution rows
   are snapshotted for audit.

## C. Three biggest risks for the real interview

1. **Data residency (third consecutive mock: sd-3, sd-4, sd-5).** This time the rule came first,
   and then the design broke it twice. Drilling the rule isn't enough; the topology has to come
   out of your mouth *as* the residency answer: home-region cells, minimised cross-region data,
   failover inside the jurisdiction.
2. **Exactly-once on the money path.** You claimed that a queue publish can sit inside a DB
   transaction. The idempotency key was a random UUID with no `(definition, occurrence)`
   uniqueness. The balance check was separate from the debit. Any one of these is a double
   payment or an overdraft, which is the first thing a fintech interviewer probes. Distributed-
   transaction mechanics were marked resolved after sd-2; this is a regression under pressure.
3. **Domain modelling of the central business concept.** "Monthly rent on the 1st" is the example
   in the prompt, and `period_in_days` can't represent it. You didn't ask about time zones, month
   ends or non-business days. The interviewer reads this as not thinking about the product's
   users.

## D. Architectural gaps or inconsistencies

- **Dual write.** The DB insert and the queue publish were described as "in the same
  transaction". If the publish succeeds and the commit fails, a new UUID is created on retry and
  the payment goes out twice. You fixed it with an outbox after a probe. You had actually
  proposed the safer `pending` polling publisher a few minutes earlier, then dropped it.
- **Idempotency only protects queue → consumer, not scheduler → payment row.** There is no
  `UNIQUE(definition_id, occurrence_date)`.
- **Balance check is check-then-act.** The consumer checks the balance, then the provider debits
  later, so a card payment in between can overdraw the account. The check and the debit need to
  be one atomic ledger operation (reserve or conditional debit).
- **Residency was stated, then contradicted** by the single EU primary and the global read
  replicas.
- **Two failover answers**: automatic quorum promotion, then "don't promote, wait for Europe".
  You never picked one.
- **The canvas drifted from what you said**:
  - `pending` status was added and then dropped;
  - the `reason` column was never added;
  - `end_at` became nullable verbally only;
  - the outbox table never appeared;
  - there was no Consumer → DB edge for results.

  The model-drift item from sd-3/sd-4 is still active.
- **Scheduler scaling** was stated as possible with no coordination. Two instances would both pick
  the same due rows without `FOR UPDATE SKIP LOCKED`, partitioning or a lease.

## E. Missing non-functional considerations

- Availability target and execution timeliness SLA: you never asked either ("executed on the due
  date by when?").
- A business SLI and alerting: on-time execution %, insufficient-funds rate, and DLQ growth on
  the 1st.
- RPO/RTO, and sync vs async replication as the knob that sets them.
- AuthZ, SCA for new payees, rate limiting, and the service identity used for executions with no
  user present.
- User notification: before execution if the balance looks low, and on failure.

## F. Over/under-engineering

- **Under**:
  - the scheduler (single instance, no coordination) on a day with 40% of the monthly load;
  - the ledger interaction (no atomic reserve/debit);
  - no SEPA status/returns path;
  - no notification.
- **Over (mild)**: four, then two, physically separate tables for internal/external ×
  one-off/recurring. One `scheduled_payments` table with a typed destination (or a destination
  table) would have been simpler and avoided the churn.
- **Right-sized**: no sharding, no cache, and the conditional provider queue.

## G. What a strong Revolut candidate might have covered

- Ask early: "When exactly does a payment run: the user's local midnight, a fixed time, the
  scheme cut-off? What about weekends, bank holidays and the 31st?" Then model recurrence as a
  calendar rule (`frequency=MONTHLY, day_of_month=31` clamped to the month end), not as days.
- **Materialise occurrences ahead of time**: the day before, generate tomorrow's executions with
  `UNIQUE(schedule_id, occurrence_date)` as the natural idempotency key. This spreads the 1st-of-
  month spike over the previous day and makes duplicates structurally impossible.
- Run several scheduler workers using `SELECT … FOR UPDATE SKIP LOCKED` (or hash-partitioned
  ownership), with an outbox from the start.
- Debit through the ledger with a conditional or atomic reserve, passing the occurrence key to
  the provider as its idempotency key so that a crash after the provider accepted is safe.
- Insufficient funds: retry later the same day (salary often lands in the morning), notify the
  user, and possibly send a "low balance before tomorrow's rent" alert. Name these as business
  trade-offs.
- Multi-region: **one cell per jurisdiction** (EU, UK, …), each with its own primary, schedulers,
  queues and scheme connector. Users are pinned to their home cell. Failover goes to a standby
  inside the same jurisdiction. Only a routing directory (user → cell, pseudonymous) is global.
  Time-zone-aware execution naturally spreads the global "1st".

## H. Topics to practise before the next mock

1. **Residency topology, said aloud as the first scaling sentence** (third time, so change the
   drill format): for 3 domains, say the cell layout in under 60 seconds *before* any replication
   word, and finish with "what crosses regions, and in what form".
2. **Duplicate-hunting on a pipeline**: for every hop (scheduler → DB → outbox → queue → consumer →
   provider → callback), state "if it crashes here, what duplicates or gets lost, and what key
   stops it". Include the dual-write trap explicitly.
3. **Domain-time implicit requirements**: time zones, DST, month-end, business days, cut-offs.
   Add them to the implicit-requirements checklist next to audit, PII and GDPR.
4. **Schema checklist before showing a table**: parent link, natural/idempotency key, status,
   timestamps, the audit fields your own flow uses (e.g. `reason`), and nullability that matches
   what you said aloud.

## I. A better architecture (post-mock only, brief)

- **Management**: Gateway → Schedule API (authZ by owner, SCA on a new payee, payee validation) →
  a `scheduled_payments` table (`id`, `user_id`, `source_balance_id`, `amount`, `currency`,
  `destination_type` + `destination_ref` → `payees` table holding the tokenised IBAN and name,
  `rrule`/`day_of_month`, `timezone`, `start_date`, `end_date NULL`, `status`, `next_run_date`,
  `version`).
- **Planner** (daily, plus catch-up): picks due schedules with `SKIP LOCKED`, inserts
  `executions(schedule_id, occurrence_date UNIQUE, amount/destination snapshot, status,
  attempt, reason, provider_ref)`, advances `next_run_date` and writes an outbox row, all in one
  transaction.
- **Outbox relay** → queue → **executors**: an atomic ledger reserve/debit keyed on the
  execution id, then the internal transfer or the SEPA connector with the same key. Results and
  SEPA callbacks update `executions`. Insufficient funds → retry window + notify. Notification
  service on success and failure.
- **Observability**: on-time execution SLI per day, DLQ depth, queue age, provider error rate and
  reconciliation mismatches.
- **Scale**: one primary at these numbers → per-jurisdiction cells with in-jurisdiction standby
  (RPO ≈ 0 via sync standby for the ledger path) → time-zone-spread execution → a global routing
  directory only.
