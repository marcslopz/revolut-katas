# sd-5 — Scheduled & recurring payments

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design a system that lets Revolut users schedule payments — one-off on a future date, or
recurring (e.g. rent every month).

(Interviewer-private: domain chosen to vary from sd-1 P2P / sd-2 hotel / sd-3 card auth / sd-4
notifications. Core hard part: executing each due payment exactly once, on time, under a massive
synchronized spike (1st of the month / payday), with retries for insufficient funds that never
double-pay. Tests current priorities: estimation sanity-check (spike vs average), data residency
on multi-region, core-first depth, canvas/schema drift. Implicit reqs available: user time zones
& DST, bank holidays/weekends and month-end edge cases (31st), payment-scheme cut-off times,
audit/regulatory trail, PSD2/SCA for mandate setup, notifying the user before/after, GDPR/home
region.)

## Phase 1 — Requirements

### Candidate's first pass (functional)
- Actor: one — the user.
- Framed one-off vs recurring as a modelling choice: (a) two separate actions/models, or (b) a
  single "scheduled payment" model with nullable recurrence fields. Chose (b): simpler, one
  table; justified by "less information, not two tables" and a possible business need to show
  all scheduled payments in one view.
- Interviewer-private: went into table/data-model shape while still in functional requirements,
  before listing what the user can actually do (create/edit/cancel/list? who's the payee? what
  happens when it executes?). No redirect given (first minute, light). Watch whether the actions
  list follows.

### Stated by interviewer (stakeholder answers)
- Source: always the user's own Revolut account balance (one of their currency balances). No
  card-funded scheduled payments.
- Destination: either another Revolut user (internal transfer) or an external bank account.
- External: via local payment schemes (e.g. SEPA in EU, Faster Payments in UK). International
  (cross-border external) exists but is nice-to-have, not MVP; domestic external + internal are
  core.
- Candidate asked to scope down to user-to-user only ("otherwise I'll separate the two actions
  because the destination format differs"). Declined: rent-style payees are mostly NOT Revolut
  users, so external domestic is the main use case and must be in scope. Candidate may still
  sequence internal first.
- Candidate's response: splits into two tables — scheduled payment to user vs to external
  account. Trade-off stated: one table = one query (faster) but many nullable columns; two tables
  = no nulls, "cleaner", but two queries.
- Interviewer-private: (1) second table/schema decision made inside Phase 1, still no list of user
  actions (create / edit / cancel / list / what happens on execution / failure) and no
  non-functional questions yet. (2) Reasoning tension: one-off vs recurring was kept in ONE table
  despite nullable recurrence fields, while internal vs external was split to AVOID nullable
  fields; same criterion, opposite outcomes, not reconciled. Not raised — watch whether it
  surfaces in LLD. No redirect yet.
- Candidate: "for the same reason" also splits recurring vs one-off → reverses the first decision
  (single model with nullable recurrence). Self-reconciled the inconsistency noted above (credit).
  Implied model now: up to 4 tables (one-off/recurring × internal/external) — not stated
  explicitly. Still no functional actions list, no NFR questions; ~3 schema decisions made in
  Phase 1.
- Candidate summary: two operations (external, internal). Recurrence is decided by the input:
  if recurring → start date, end date, period.
- Interviewer-private: unclear whether the model is now 2 tables (internal/external, recurrence
  as optional fields) or 4 (the split announced one turn earlier). Possible drift; watch the
  canvas/schema. Functional scope captured so far = create only. Not yet mentioned: edit/cancel,
  list/view, execution outcome, failure (insufficient funds), notifications.

### Non-functional — stakeholder answers (candidate asked for reads/writes per second)
Gave business numbers only, candidate to derive rates:
- ~50M retail customers; ~10M have at least one active scheduled payment; avg ~3 active
  schedules each (→ ~30M active schedules). Mostly monthly.
- Schedule management (create/edit/cancel): ~500k per day.
- Viewing scheduled payments list/detail: ~5M views per day.
- Executions are NOT uniform: ~40% of a month's executions land on the 1st, plus a smaller
  bump around payday (25th–28th).
- Interviewer-private: the spike is the estimation trap: monthly average vs a 1st-of-month
  peak. Also whether execution happens at a specific time of day (all at 00:00?) not yet asked.
- Q: are the 5M views/day from the 10M active users or all 50M? A: overwhelmingly from the ~10M
  with active schedules; 5M is already the total daily figure.
- Q: creation rate? Already given (500k/day create+edit+cancel) — pointed out lightly that it was
  covered (re-ask of settled info, per canvas-discipline note). Added split: ~300k creations,
  ~200k edits/cancels per day.
- Q: % executed in the payday window? A: ~20% across 25th–28th (four days, candidate said
  "three"). Remaining ~40% spread over the rest of the month.
  → Full distribution: 1st ≈ 40%, 25th–28th ≈ 20% (~5%/day), other ~25 days ≈ 40% (~1.6%/day).

### Candidate's estimation
- "10,000 million" active users (verbal slip / dictation — clearly meant 10M given the follow-up)
  × 3 monthly schedules = 30M executions/month → 11.57/s average. ✔ (30M / 2.592M s)
- Peak: 40% on the 1st → 12M in a day → ~139/s. ✔ arithmetic.
- Interviewer-private: (1) the peak figure silently assumes the 1st-of-month executions are
  spread evenly over 24h; whether execution time-of-day is fixed (e.g. all at 00:00 or a scheme
  cut-off) hasn't been asked. Not challenged — let it surface in LLD. (2) No sanity comparison
  stated ("139/s is small/large relative to ...") — current HIGH priority item; watch whether it
  shows up. (3) Read/management rates (5M views/day, 500k changes/day) not converted yet.
- Q: MVP single region? A: Yes — MVP launches in one region (say the EU, SEPA). Longer term the
  product must serve other regions Revolut operates in (UK, etc.), each with its own scheme and
  regulator — relevant for Phase 4 (and data residency).
- Reads: 5M/day → ~58 QPS ✔. Management writes: 500k/day → <6/s ✔. Executions peak ~139/s.
  All averages over 24h (no intra-day peak factor applied to reads/writes). Still no sanity
  comparison stated for any of the numbers.
- Conclusion: no sharding needed ("share" = shard, dictation) — writes and reads low; single
  writer/primary + read replicas covers availability, consistency and throughput.
- Interviewer-private: (+) used the numbers to drive a decision and landed on "don't shard" —
  the opposite of sd-3's premature sharding; implicit sanity check, though no explicit anchor
  ("one Postgres primary handles thousands of writes/s"). (−) DB topology chosen inside Phase 1,
  before any HLD. Not asked so far: storage size (30M schedules + years of execution history),
  latency/availability SLA, consistency needs, execution time-of-day / timeliness guarantee.
  No implicit requirement surfaced yet (time zones, weekends/bank holidays, month-end 29–31,
  audit, SCA, notifications).

### Storage (candidate-raised)
- Implicit requirement surfaced unprompted: **audit** — transfers must be kept for some years.
- ~10 columns × ~100 B → ~1 KB per execution row. Said "13 million executions a month" (likely
  dictation of "30"; result is consistent with 30M) → 30M × 1 KB × 12 ≈ 360 GB/year ✔.
- Sanity conclusion stated: fits a single database without maintenance problems, even 3–5 years
  (~1–1.8 TB). If cost matters → tier older data to cold storage, keep months/1 year hot.
- Interviewer-private: (+) explicit "does this fit?" comparison — the HIGH-priority sanity-check
  habit fired here. (+) first implicit requirement (audit retention). Schedule table itself
  (30M active rows) not sized, small anyway.

### Implicit requirements (candidate-raised)
- Audit trail (already above).
- Sensitive data: PII, and "PCI if we have any bank account information" → handle sensitive data
  properly.
- GDPR compliance (EU, personal data).
- Interviewer-private: PCI DSS scopes payment-CARD data (PAN etc.), not bank account details
  (IBAN/sort code) — and the source here is never a card (stated earlier). Same PCI imprecision as
  sd-3. Probed with one question (factual claim → legitimate interjection). Still no
  domain-specific implicit reqs: time zones/DST, weekends & bank holidays / SEPA business days,
  29th–31st in short months, insufficient-funds behaviour, notifying the user, SCA/consent for
  setting up a payment.
- After one probe: candidate self-corrected — PCI is card-only; bank account details are
  sensitive (PII/GDPR) but not PCI. Corrected quickly, needed the prompt.

### Phase 1 close — interviewer summary
- Candidate-led transition to design (no prompt needed).
- Covered: actor, source/destination types, one-off vs recurring, scale (derived rates ✔),
  storage (✔ with sanity check), single-region MVP, audit, PII/GDPR (PCI corrected after probe).
- Not covered: functional actions beyond "create" (edit/cancel/list/notify), what happens when
  a payment fails (insufficient funds → retry? skip? notify?), timeliness SLA (on the date? by a
  time? at 00:00 user-local?), availability target, consistency needs, time zones, non-business
  days, month-end dates, SCA/consent. Domain-specific implicit reqs = 0; generic ones = 3.
- Spent a noticeable share of Phase 1 on table design (2 vs 4 tables) and DB topology.

## Phase 2 — High-level design
- (Back in requirements briefly) Invariant stated: payer must have sufficient balance at
  EXECUTION time (not creation time). Behaviour when it doesn't (fail / retry / notify) not yet
  stated.

### HLD — management path (candidate)
- User → API gateway → load balancer → Scheduled Payment API (horizontally scaled).
- API validates the scheduled-payment data and the destination (exists / valid); invalid →
  error response to UI. Valid → Scheduled Payment service writes to DB.
- (+) Pre-flow validation sequenced before the write.
- Q: latency SLA for management? A: interactive user-facing; p99 under ~1s acceptable, typical
  a few hundred ms. Not a hot path.
- Interviewer-private: "validates destination exists" — for internal it's a Revolut lookup; for
  external IBANs, how existence/ownership is validated not explained (box level is fine for now).
- Candidate: with ~1s budget, cross-region latency likely not a problem. (MVP is single-region,
  so forward-looking remark; not engaged.)
- Candidate revisits the table split: maybe just 2 tables (internal / external); one-off =
  recurring with end_date = start_date, or start_date with null period.
- Interviewer-private: third change of the schema shape (1 → 2 → 4 → 2), all verbal, all before
  the execution path exists. Ends up close to the very first decision (one model, nullable
  recurrence) but without acknowledging the reversal. Model-drift risk for the canvas.
- **Redirect #1 (light, one-time, HLD discipline):** asked to keep it at box level and save the
  schema for the deep dive. Trigger: sustained table-level design across Phase 1 + Phase 2 while
  the execution flow (the prompt's core) hasn't been sketched.

### HLD — execution path (candidate)
- Fully async (user not waiting) → producer/consumer.
- **Schedule producer**: queries the scheduled-payments tables; for each due one, "transactionally,
  atomically" creates a row in a **payments** table AND publishes a message to a **queue broker**.
- **Workers/consumers** behind the broker: multiple, autoscaled on throughput.
- Broker configured **at-least-once**; duplicates (e.g. timeouts) handled by an **idempotency
  key** carried in the message and stored in the payments table → payments idempotent.
- Actual money movement via a provider: SEPA provider for external, internal provider/ledger for
  user-to-user.
- Interviewer-private: (+) core flow now on the board; at-least-once + idempotency named
  together. Probe candidates for LLD: (1) "atomically" write DB row + publish to broker — how
  (outbox? or dual write)? (2) how the producer finds due schedules among 30M without
  double-producing (multiple producer instances? cursor/next_run_at? locking?), and advances
  the schedule to the next occurrence; (3) idempotency key derivation (per schedule+occurrence?);
  (4) insufficient funds at execution (invariant stated earlier, behaviour undefined);
  (5) the 1st-of-month spike: when does the producer run — all at 00:00?; (6) provider
  failure/timeouts — SEPA is async with its own status.

### Screenshot 01-hld.png (copied from ~/Downloads/mock_revolut_scheduled_payments.png)
- Stickies: Functional = schedule_external_payment(to_external, amount, currency, period,
  start_date, end_date), schedule_internal_payment(user_id, ...same...); invariant "source user
  must have enough balance at execution time". NFR sticky = matches spoken numbers (10M users,
  3 schedules, 30M exec/month, 11.57/s avg, 139/s peak, 57.87 QPS reads, 5.78 WPS, 1 KB/row,
  360 GB/yr single DB OK, p99 < 1s). Implicit sticky = audit trails, PII (bank accounts, personal
  data), GDPR — PCI correctly dropped.
- Diagram: user → Gateway → Load Balancer → Schedule Payment API → DB ← Scheduler → payments
  queue (+ DLQ box, unconnected) → Consumer → {Bank account payment provider, Revolut internal
  payment provider}.
- Canvas vs spoken: consistent overall (canvas discipline good). Differences/gaps:
  - DLQ on canvas but never mentioned verbally; no edge to/from it.
  - Single "DB" box — the separate payments table and the "atomic" row+publish aren't visible.
  - No edge from Consumer back to DB → payment status/result never recorded; the next
    occurrence of a recurring schedule is not shown being advanced.
  - Functional API = create only (no edit/cancel/list, though 5M views/day and 200k
    edits/cancels/day were in the numbers).
  - Balance check (stated invariant) has no home on the diagram — implicitly inside the
    providers?

## Phase 3 — Low-level design
- Candidate-led transition: "let's focus on the internals", starting with the database.
- DB topology restated: single write primary + read replicas, no sharding (low traffic).
- Relational DB chosen: "want to do joins", schema well defined.
- Interviewer-private: justification is generic. The stronger, design-specific reason —
  transactions (the "atomic" payment-row + publish from HLD, idempotency-key uniqueness,
  advancing next run in the same txn) — not given. Which joins are needed not stated.

### Screenshot 02-tables.png (copied from ~/Downloads/table.png)
Two tables — settles the model at 2 (internal/external), recurrence as fields:
- schedule_payment_definitions_internal: id UUID PK, user_id UUID NN (FK users), amount Decimal
  NN (>0), currency varchar(8) NN, period_in_days int (null or >0), start_at timestamptz NN,
  end_at timestamptz NN, next_execution_at timestamptz NN, to_user_id UUID NN (FK users).
- schedule_payment_definitions_external: same core + to_iban TEXT NN, to_bic TEXT NN,
  to_swift_code TEXT NN.
Interviewer-private observations:
- (+) next_execution_at — the right hook for "find due schedules".
- (−) **period_in_days** cannot express "monthly on the 1st" (28–31-day months) — the dominant
  case per Phase 1 ("mostly monthly", 40% on the 1st). Strongest domain gap so far; ties to the
  missed implicit reqs (month-end, time zones, non-business days).
- end_at NOT NULL → open-ended recurring (rent with no end) not representable.
- No status (active/paused/cancelled) despite 200k edits/cancels/day; no created_at/updated_at /
  version.
- No source balance/account reference (currency only).
- External: BIC and SWIFT code are the same identifier (redundant); SEPA needs IBAN (+ payee
  name for SEPA/Verification of Payee) — no beneficiary name column. IBAN stored plain (PII
  flagged in Phase 1 — encryption not yet mentioned).
- No index stated on next_execution_at; payments/executions table (with idempotency key) not on
  canvas yet.
- No user time zone → "start_at timestamptz" is an instant, not "the 1st in the user's local
  calendar".

### Screenshot 03-tables2.png (copied from ~/Downloads/tables2.png) — execution tables
- schedule_payments_internal: id UUID PK "(idempotency key)", user_id NN FK, amount Decimal NN
  (>0), currency varchar(8) NN, created_at timestamptz NN, status NN IN ('created','sent',
  'confirmed','failed'), to_user_id UUID NN FK.
- schedule_payments_external: same + to_iban, to_bic, to_swift_code NN.
Interviewer-private observations:
- (+) Execution rows snapshot amount/destination — good for audit (definition edits don't
  rewrite history). (+) Explicit status lifecycle.
- (−) **No link to the definition** (no definition_id) and **no occurrence/scheduled date**.
  The idempotency key is the row's own PK UUID → if generated fresh per insert, it does NOT stop
  the scheduler from producing the same occurrence twice (crash before advancing
  next_execution_at, two scheduler instances, retry). Idempotency only protects the
  queue→consumer leg, not the producer leg. This is the prompt's core ("each due payment exactly
  once"). Prime LLD probe.
- No retry/attempt fields; 'failed' is terminal → insufficient-funds behaviour still undefined.
- No provider reference (SEPA end-to-end id) for reconciliation; no updated_at.
- Same BIC/SWIFT redundancy and plain IBAN as definitions.

### LLD — infrastructure & execution internals (candidate)
- Gateway routes by path; LB with TLS termination; REST over HTTP to Schedule Payment API
  (horizontal).
- DB: single primary + read replicas; scale replicas out; primary down → promote a replica.
- Scheduler: "can scale up but not needed"; if it goes down "we don't lose anything".
- Publishing: for each payment row in 'created' → send to queue → update status to **'pending'**
  (new status, not on canvas) ⇒ "pending means it's in the queue". (= polling publisher /
  outbox-like; crash between publish and update → re-publish → relies on consumer dedupe.)
- Queue at-least-once; consumer acks only after provider responds 'accepted'.
- Consumer idempotency: check if the idempotency key was "already sent", drop if so.
- Poison messages → after N (~5) retries → DLQ → engineering investigates. (DLQ box now
  explained.)
- Consumers scale horizontally. Optional extra queue between consumer and providers for provider
  throttling / circuit breaker / rate limiting (degradation, cost, errors).
Interviewer-private:
- (+) Good failure vocabulary: outbox-ish status flip, ack-after-success, DLQ, provider
  throttling/circuit breaker, replica promotion.
- (−) Still undescribed: **who creates the 'created' payment rows from the definitions and how
  next_execution_at is advanced** — the exactly-once-per-occurrence step. Payment table has no
  definition_id/occurrence date, so nothing structural prevents a duplicate occurrence.
- "Scale but not needed": a second scheduler instance would double-publish/double-create
  without row locking/leader election — not addressed; single instance = SPOF + 1st-of-month
  backlog.
- Consumer dedupe "check if already sent" = check-then-act race across consumers; and the
  crash-after-provider-accepted-before-ack case → redelivery → is the provider call idempotent
  (key passed to provider)?
- Balance check (stated invariant) still has no place in the flow; insufficient funds →
  'failed'? retry? notify?
- Replica promotion with async replication → possible loss of last committed writes (not
  discussed).
- Schema drift: 'pending' status not on the canvas.
- **Probe asked (core, scenario-based):** walk through one monthly rent definition on the 1st,
  from definition to message in queue, and a crash halfway.

### Core walkthrough — one monthly rent schedule (candidate, answering probe)
- API creates the definition: monthly → period_in_days = "230" (dictation; meant 30),
  start_at = 1st of next month, end_at may be NULL (**constraint changed verbally** → canvas now
  stale), next_execution_at = start_at.
- Scheduler (after the 1st): queries definitions with now > next_execution_at; in ONE
  transaction: reads the definition, inserts the new 'created' payment, computes next
  next_execution_at — (+) advance + insert in the same txn, the key exactly-once step, now stated.
- NEW: "we can also do the message insert into the queue in the same transaction, so we don't
  need the pending status." Crash between payment write and queue insert → txn rolls back both
  tables → scheduler restarts and redoes everything.
Interviewer-private:
- (−−) **Dual-write error.** The broker is a separate system; publishing can't be part of the DB
  transaction. Failure: publish succeeds → crash/commit fails → DB rolls back, message already in
  queue with payment id X → restart creates a NEW payment row with a NEW UUID Y + new message →
  two messages, two different idempotency keys → **double payment**. The earlier 'pending'
  polling-publisher was the safer design; it was dropped in favour of this. Distributed-txn
  vocabulary was "resolved" as of sd-2 — this is a regression under pressure, watch.
- (−) period_in_days = 30 for "monthly on the 1st": 1 Feb + 30d = 3 Mar → drifts off the 1st
  within one cycle. Not yet probed.
- Probe asked: the queue isn't in the DB — what if the publish succeeds and the commit fails?
- After probe: switched to **transactional outbox** — outbox row written in the same txn as the
  payment insert + next_execution_at advance; on restart, relay re-reads the outbox and
  (re)publishes. Correct fix, needed the prompt. Outbox table not on canvas yet. Implicit:
  re-publish → duplicate messages share the same payment id → consumer dedupe works (not said).

### Security (candidate)
- AuthN: auth service issues JWT on credentials; API/internal services validate JWT.
- In transit: TLS at LB, mTLS internally.
- At rest: Postgres disk encryption (first time "Postgres" named). Logs: mask/obfuscate private
  data.
Interviewer-private:
- (−) AuthZ not mentioned — ownership check (definition.user_id == token subject) for view/edit;
  matters more once edit/cancel exist (still not in functional scope).
- (−) No SCA / step-up (PSD2) when creating a payment to a new payee — a Revolut-specific
  expectation; creating a standing order is effectively authorising future debits.
- Execution happens with no user present → which identity/permission does the scheduler/consumer
  act under? Not discussed.
- No rate limiting/abuse (mass schedule creation, payee-validation enumeration).
- Disk encryption only; no field-level encryption/tokenisation of IBAN despite PII flagged.

### Edge cases (candidate)
- Scheduler crash mid-way → covered (outbox).
- Consumer crash with a message → ack + idempotent ops.
- Provider degradation → circuit break; stop the scheduler generating messages; when provider
  recovers, add schedulers/consumers to drain the backlog while staying under provider rate
  limits. (+) backpressure + recovery-drain thinking.
Interviewer-private:
- (−) Detection absent: no monitoring/metrics/alerting named (queue lag, DLQ depth, % due
  payments not executed by X, provider error rate) — Karim's detect/prevent/recover triad,
  only prevent/recover covered.
- (−) Own stated invariant (sufficient balance at execution) still has no handling and no
  component doing the check.
- Not covered: consumer crash AFTER provider accepted but BEFORE recording/ack (is the key passed
  to the provider?); SEPA is async (sent → confirmed/returned later) — how does status reach
  'confirmed'?; 1st-of-month backlog timing.
- **Probe asked:** rent executes on the 1st, balance is 50 EUR short — what happens?
- Answer: consumer checks balance before calling the provider; insufficient → payment status
  'failed' + a reason, so the user can see why.
Interviewer-private:
- (+) Balance check finally placed (consumer, before provider call).
- (−) Business decision taken with no trade-off articulated: no retry (e.g. later that day /
  next morning when salary lands), no notification to the user (only visible if they open the
  app), no "notify the day before if balance looks low". For rent, silent failure is the
  costliest UX outcome.
- (−) Check-then-act: balance checked in consumer, debit happens later in the provider/ledger —
  a concurrent card payment can spend the money in between. Needs atomic reserve/debit in the
  ledger (sd-3 core-invariant theme again). Not raised.
- Schema drift: no 'reason' column on the canvas.

### Phase 3 close — interviewer summary
- Candidate-led transition to scaling. LLD covered DB choice/topology, schemas, infra, outbox
  (after probe), consumer ack/idempotency, DLQ, provider circuit breaking, security basics,
  insufficient funds (after probe).
- Canvas not updated since 03-tables2.png: outbox table, 'pending' status (later dropped?),
  'reason' column, nullable end_at all verbal-only → drift.
- Not touched: monitoring/observability, period_in_days vs calendar months, time zones,
  SEPA async confirmation/returns, 1st-of-month spike timing, multiple scheduler instances.

## Phase 4 — Scaling
- Candidate opens multi-region with **data residency first**: GDPR → user data must stay in the
  user's region. (+) HIGH-priority item fired unprompted, at the very start of the phase.
- Next: management traffic low + p99 budget generous → keep a single write primary in Europe and
  accept ~100 ms cross-region latency for other regions' writes.
- Interviewer-private: **internal inconsistency** with the sentence just before (user data must
  stay in-region) — single EU primary means non-EU users' PII/bank data written to and stored in
  the EU. Same residency-by-default pattern as sd-3/sd-4, this time after stating the rule.
  Latency argument is sound on its own; residency is the binding constraint, not latency.
- **Probe asked:** a UK user creates a schedule — where does that row live?
- Answer: "the information about the user is in Europe for this UK user"; what can be outside is
  shared info, e.g. a UK user scheduling a payment to a user in another region.
- Interviewer-private: did not resolve the inconsistency — confirmed UK user data stored in the
  EU, then pivoted to cross-region payees. Unclear whether "region" means the user's home region
  or "where our single primary is". One neutral clarifying follow-up asked to let them confront
  it (no hint of the answer).
- Answer: yes, UK user data in Europe; sensitive/private fields (e.g. IBAN) stored as **tokens
  from a vault**.
Interviewer-private:
- Held the position; added tokenisation/vault as mitigation (+ for the idea). Vault location not
  stated: if the vault sits in the user's home region and only tokens cross, that is close to a
  defensible "minimised/pseudonymised cross-region" answer — but it wasn't framed that way.
- Nuance for review (keep it fair): UK GDPR has an adequacy decision for the EEA, so UK→EU
  storage isn't automatically unlawful; the problem is (1) contradicting their own opening
  premise "user data must stay in-region" without reconciling it, and (2) the design doesn't
  generalise to jurisdictions with real localisation rules, nor to regulator expectations
  (FCA/local entity) — a single EU primary is also a global SPOF/blast radius.
- No explicit local → regional → global progression yet; went straight to "another region".

### Multi-region / global (candidate)
- Single write primary in Europe; all users worldwide write to it. Read replicas in every region.
- Europe down → a replica in another region is promoted.
- Queues/scheduler/consumers deployed in all regions, but only one active ("app tick" ≈ active
  instance) in the primary's region (active/passive).
- Acknowledges this puts GDPR data outside Europe → "inform the user in which situations and how
  we store it securely".
- 2 regions → global: same pattern + **ordered priority list** for primary; first in the list
  keeps/takes primary only if it can reach a **majority** of the other regions, else steps down;
  next in the list checks majority and takes over. (≈ quorum-based leader election.)
Interviewer-private:
- (+) Quorum/majority idea to avoid split-brain; active/passive workers to avoid double
  scheduling across regions — consistent with the single-primary choice.
- (−−) **Data residency now violated in both directions**: EU users' PII replicated to read
  replicas worldwide; "inform the user" isn't a GDPR transfer mechanism. Reverses the phase's
  opening statement. Third mock in a row (sd-3, sd-4, sd-5) — HIGH priority item NOT resolved,
  despite being the first thing said in Phase 4.
- (−) Promotion with async replicas → lost last writes: an un-replicated next_execution_at
  advance + outbox row → newly promoted region re-executes occurrences → double payment. Not
  considered (core invariant again).
- (−) Every write from APAC/US crosses to the EU; global SPOF/blast radius in one region.
- (−) No explicit local → regional → global steps (local scaling skipped); no cost vs performance
  trade-off; no graceful-degradation statement; 1st-of-month global spike (time zones!) not
  discussed.
- **Probe asked:** EU primary dies on the 1st; last seconds of writes didn't replicate to the
  promoted replica — what happens to those payments?
- Answer: traffic isn't real-time → option A: don't promote, tolerate the delay until Europe is
  back (no lost writes). Option B: promote another region and **compensate** later when Europe
  returns.
Interviewer-private:
- (+) Option A is a genuinely good trade-off for this domain (payments due "today" tolerate
  minutes/hours of delay; consistency > availability for money) — but it wasn't stated as a
  decision, and it contradicts the automatic quorum promotion described one turn earlier.
- (−) Never named the concrete failure (re-executed occurrence → double payment) nor how
  compensation works (detect via a deterministic per-occurrence key, reconcile against provider/
  ledger, reverse/refund). No RPO/RTO vocabulary; sync vs async replication not considered as
  the knob.

### Candidate's closing summary
- API for creating scheduled payments; internal/external; one-off or recurring via columns.
- Scheduler/producer queries DB, writes via outbox ("notebook's pattern" = outbox, dictation) →
  queue; consumers read, check balance (insufficient → fail without calling provider), call the
  bank-account or internal provider.
- NEW — deployment: services deploy independently; canary per service watching latency,
  throughput, errors.
- NEW — monitoring: per-component resources, DB, queues (depth, average time in queue), DLQ for
  poison messages, downstream provider error rate → drives circuit breaking / rate limiting.
Interviewer-private:
- (+) Observability finally covered, with queue age + DLQ + provider error rate — good technical
  signals. (−) No business-level SLI ("% of payments due today executed by HH:MM", failed-for-
  insufficient-funds rate) — the metric that actually tells you the product is broken.
- (+) Closed with a self-driven summary, no hand-back ("anything else?") — sd-2/sd-3 habit stays
  fixed.
- Summary didn't mention multi-region/residency or the failover decision.

## Phase 5 — Wrap-up
- Candidate had no questions for the interviewer. (Minor: in the real final round, 1–2 questions
  about the team/domain are expected and a cheap positive signal.)
- Mock ended. Awaiting "END MOCK - START REVIEW MODE".
