# sd-7 — Withdrawals to an external bank account

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design a feature that lets Revolut users withdraw money from their Revolut account to their own
account at another bank.

(Interviewer-private: first mock under the 2026-10-04 CALIBRATION — normal difficulty, technical
focus, domain kept simple via stakeholder rules, quarter-point scale, review sections J + K.
Varies from sd-1 P2P / sd-2 hotel / sd-3 card auth / sd-4 notifications / sd-5 scheduled payments /
sd-6 payment links. Targets the HIGH technical priority directly: a payment/withdrawal row with a
state machine persisted before the external call, reserve (hold) before the irreversible step,
idempotency end to end (client retry → API → provider), unknown outcome on provider timeout,
returns arriving days later, recovery worker. Also checks residency (2nd clean mock would resolve
it). Keep domain simple: an external "bank transfer provider" with an API + callbacks; it may take
seconds (instant) or up to 1–2 business days; transfers can be returned later (wrong account).)

## Phase 1 — Requirements

### Stated by interviewer (stakeholder answers)
- Q: does the withdrawal use a SEPA account? A: destination = user's own account at another bank,
  identified by IBAN (EU) or account number + sort code (UK). Revolut doesn't talk to SEPA/FPS
  directly: it uses an **external bank transfer provider** (API + status callbacks) that picks the
  scheme. Usually completes in seconds; sometimes up to 1–2 business days.
  (Held back unless asked: transfers can be returned days later, e.g. account closed.)
- Q: different providers per destination? A: one provider per region — one for EU withdrawals,
  one for UK — with very similar APIs. Not one per destination bank.
- Candidate (still Phase 1): central entity = **withdrawal**, its unique ID = idempotency key; user
  creates it; saga = **hold** balance → request provider → **debit** in ledger (happy path), via the
  region's provider.
  Interviewer-private: (++) **payment-entity-first + hold before the irreversible step**, unprompted,
  in the first minutes — exactly the HIGH priority habit. (−) Jumped to the core design before
  finishing requirements (no functional list beyond create, no NFR yet); not redirected. Where the
  withdrawal ID is generated (client vs server) not stated yet.
- Assumption stated: currency = the user's account currency. Confirmed: EUR (EU) / GBP (UK), no
  currency conversion in scope. (+) assumption made explicit and checked.

### Non-functional — stakeholder answers (asked users/requests/latency)
- Customers: ~50M (≈30M EU, ≈20M UK).
- Withdrawals: ~2M/day total; busiest hour ≈3x the daily hourly average; days around payday
  (25th–1st) ≈2x a normal day.
- Status/history views: ~10M/day.
- Latency: creating a withdrawal p99 < 500 ms (user sees "processing" right away); the final
  result for instant transfers should show within ~10 s; viewing status p99 < 300 ms.
- Availability target for creating withdrawals: 99.95%.

### Screenshot 01-fni.png (new file, differs from sd-6's)
- Functional: withdraw(user_id, account_id, amount, to_bank_info) → payment_id.
- NFR: 4M withdrawals on a peak day → ~167k/hour avg → ×3 = 500k in the peak hour → **139/s** ✔
  (combined payday 2x and hourly 3x correctly). p99 < 500 ms, ~10 s for instant results, view
  status p99 < 300 ms, availability 99.95%.
- Implicit: PII lives in the user's region (GDPR); secure in transit (HTTPS/mTLS) and at rest
  (encrypted disk, tokenised); balance check at the start of the withdrawal.
Interviewer-private: (+) estimation clean, both peak factors stacked. (−) Reads (10M/day ≈ 116/s
avg) not converted. (−) Functional list = create only: no get status / list history (despite the
10M views/day NFR); no cancel. (−) No comparison sentence (139/s vs one primary). Residency
stated in Phase 1 again (+).

## Phase 2/3 — Design (candidate merged HLD with the core LLD)

### Screenshot 02-high-level.png (new; differs from sd-6)
user → withdraw API service → DB ("check and hold balance", "debit user"); API → "execute" →
Region-based bank payment provider → "async callback" → API.

### Withdraw workflow (spoken)
1. User → withdraw API (destination bank info, amount; currency implicit per cell).
2. **TX1**: check balance + **hold** (available goes down) if enough, else "not enough balance";
   in the same TX create the payment row (new payment_id, **client idempotency_key** to dedupe
   client retries), status = created.
3. API calls the regional provider → 201 + bank_payment_id. **Provider idempotency key =
   payment_id**, so after a crash the transfer request can be repeated safely.
4. Store bank_payment_id, status = waiting_for_bank_provider.
5. Provider callback (payment_id / bank_payment_id), possibly much later → **TX**: if not already
   completed (dedupe), status = completed + ledger double entry (user −amount, "bank withdrawal"
   +amount, same payment_id) + release the hold (available == balance, both without the amount).
Read path: paginated withdrawal list with status, filters by status / created / updated → indexes
on those columns.
Interviewer-private:
- (++) Textbook skeleton of the HIGH item: entity first, **state persisted before the external
  call**, hold before the irreversible step, client idempotency key + payment_id as the provider's
  key, debit + hold release in one TX on the callback. Big step up from sd-6.
- (−) No recovery worker named: crash after TX1 before/while calling the provider leaves the row in
  `created` — "we can repeat" but who/when? Rows stuck in `waiting` if the callback never arrives?
- (−) Only the happy path: provider rejects (bad IBAN) → release hold; returns after completion
  (days later) → credit back — not covered (returns held back unless asked).
- (−) Callback dedupe phrased as "check not already completed" (check-then-act) — robust form is a
  conditional UPDATE … WHERE status = 'waiting'. Callback authentication not mentioned.
- (−) Read indexes: single-column on status/created/updated; the real access pattern is per user →
  composite (user_id, created_at) etc.
- Simplification: hold + ledger in "DB" alongside payments — treats the ledger as same-DB (one TX).
  Reasonable for this mock; not challenged.
- HLD at box level, very lean (one service) — fine at this scale.

### LLD — database (candidate)
- Relational. 139 withdrawals/s × <10 row writes per transaction ≈ 1k writes/s → no sharding.
  (+) rows-per-business-event applied unprompted (lesson from the 2026-10-02 drill); conclusion
  sensible (comparison implicit, not stated against an anchor).
- Storage not high; asks how many years audit records must be kept → move older records to cold
  storage (keeps VACUUM/snapshots/maintenance efficient, reads fast, cheaper per TB-month).
  Stakeholder answer: keep withdrawal records **5 years**; older than ~1 year rarely read.
- Interviewer-private: relational justification still not explicit (ACID for hold + payment row +
  ledger in one TX is the real reason — implied by the design, not said).

### LLD — infra (candidate)
- Could use queues + outbox for the saga, but simpler: **saga state = the status column in the DB**,
  no extra infra. Queues would add flexibility if the provider struggles (rate limiting, circuit
  breaker, half-open ramp) — listed as a future improvement.
  Interviewer-private: (+) explicit simplicity trade-off, status row as saga state = right call at
  this scale. (−) Still nothing that *drives* stuck rows forward (no worker named).
- **Probe asked (core, scenario):** TX1 committed (hold + created), API crashes before calling the
  provider, client doesn't retry — what moves the withdrawal forward?
- Answer: a **processor/recovery worker** picks up orphaned withdrawals: reads the DB status and
  continues the saga; duplicates (user retry vs worker) are harmless because every step is
  idempotent. Notes that with outbox + queue this is solved by the producer driving the saga.
  Interviewer-private: (+) correct fix after one probe, and the idempotency argument for the
  API-vs-worker race is right (provider key = payment_id). (−) Selection criteria not stated
  (non-terminal status AND updated_at < now − N, SKIP LOCKED); also applies to rows stuck in
  `waiting` when the callback never arrives (→ query provider status) — not said.

### Scalability / deployment (candidate, local)
- API scales horizontally behind a load balancer; canary deploys watching latency/errors/throughput,
  rollback with small blast radius.
- If moved to producer/consumer: scale both horizontally, broker with at-least-once delivery +
  idempotent ops, DLQ for poison messages after N retries or clearly unfixable errors.
  Interviewer-private: (+) solid but mostly hypothetical (describes the alternative topology rather
  than the chosen one). Recovery worker scaling/coordination (multiple instances → SKIP LOCKED)
  not mentioned. No regional/global step yet; monitoring is deploy-centric (no stuck-withdrawal /
  provider error-rate signals).
- Reads: DB read replicas enough at this load; eventual consistency accepted for views. If growth /
  hot users / hot days → Redis cache (LRU) for hot data.
  Interviewer-private: (−) read-your-writes: user creates a withdrawal and the list (replica) may not
  show it yet — not mentioned; easy fix (read own recent writes from the primary / return the row
  from the create call).
- HA: "message queue with HA and durable messages" so a broker replica takes over.
  Interviewer-private: **drift** — the chosen design has no queue (status column + worker); HA for a
  queue that isn't in the design.
- DB primary down → promote a replica; a worker checks operations and compensates if needed.
  Interviewer-private: (−) with async replication the newest rows can be lost on promotion: if the
  provider was already called with payment_id X but row X didn't replicate, the money leaves and
  nothing in our DB says so (no hold, no debit). Detection = reconcile against the provider's
  records / callback for an unknown payment_id. Not raised; not probed (review item).

### Edge cases (candidate-led)
1. Create response lost, user retries → client idempotency key matched → return 201 with the same
   payment_id. ✔
2. "Publisher" crashes mid-operation → status not yet updated → next run repeats; duplicate message
   or duplicate provider call collapses because payment_id is the key. ✔ (terminology still from the
   queue variant — design chose status column + worker; minor drift)
3. Primary down → promote replica, resume new withdrawals when ready; in-flight ones picked up by the
   worker (maybe duplicated, idempotent). Add checkers: **ledger sums to zero** and **stuck
   operations** in DB — distinguishing legitimately waiting-for-provider ones.
   (+) detection named (ledger invariant + stuck detector) — Karim's detect→prevent→recover covered.
   (−) async-replication loss on promotion (provider called, row lost) still not seen.
Not covered: provider **rejects** (bad IBAN) → release hold; provider **returns** a completed
transfer days later; callback authentication; provider timeouts / unknown outcome (partly covered by
idempotent retry).
- **Probe asked:** completed withdrawal, 2 days later the provider sends "returned — destination
  account closed".
- Answer: callback for an already-debited payment → compensation: one TX updates payment to
  `returned`, inserts the two reversing ledger rows (credit user, debit "bank withdrawal"), updates
  balance. ✔ Correct.
  Interviewer-private: (−) not said: dedupe of the return callback (conditional UPDATE WHERE
  status = 'completed' makes a duplicate return a no-op); notify the user. Minor.

## Phase 4 — Multi-region (candidate)
- The cell serves UK or EU users locally; to add US users → replicate the cell with a US bank
  provider. User data never crosses regions; any cross-border movement is done by the bank
  provider, outside our system.
  Interviewer-private: (+) **residency right again, unprompted — 2nd consecutive clean mock**
  (sd-6, sd-7) → meets the RESOLVED bar. (−) Thin Phase 4: no explicit local → regional → global
  steps, in-region multi-AZ not restated here (replica promotion said earlier), no new bottleneck at
  scale (provider rate limits, payday peaks), no cost or graceful-degradation statement.
- Failover: every region deployed across ≥2 availability zones; promote a replica in the other AZ;
  data stays in the region.
  Interviewer-private: (+) in-jurisdiction failover. (−) Wording: "if a region goes down" → AZs
  don't help when the whole region is out; for that you need a second region inside the same
  jurisdiction (e.g. Frankfurt + Dublin for EU). Precision note for review.

### Closing summary (candidate)
- "An API, a mixed DB/outbox/queue producer/consumer pattern for the saga, and an external
  provider for the bank transfers."
  Interviewer-private: (+) self-driven close, no hand-back. (−) Summary blurs the choice: the design
  chose status column + recovery worker (no queue); "mixed DB/outbox/queue" re-introduces the
  alternative → drift. Recap only, no open risks named.

## Phase 5 — Wrap-up
