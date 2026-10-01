# sd-3 — Card transaction authorization

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design the system that decides, in real time, whether to approve or decline a payment when a
customer uses their Revolut card at a merchant.

## Phase 1 — Requirements

### Candidate's first pass (functional, framed as checks before approval)
1. Sufficient funds/credit
2. Valid Revolut customer; asked how the payment/merchant is identified to Revolut
3. Merchant fraud check — internal DB or external provider?
4. Does merchant need to register with Revolut first?

### Stakeholder answers given
- Flow: merchant -> acquirer -> card network (Visa/Mastercard) -> Revolut as issuer. Revolut
  receives an authorization request and must reply approve/decline. Merchant does NOT register with
  Revolut.
- Request contains: card identifier (PAN/token), amount + currency, merchant ID, merchant category,
  country, network transaction ID.
- Customer identified by card -> card maps to customer + account. Card must be active (not
  frozen/cancelled/expired).
- Funds: debit cards only, authorized against the customer's Revolut account balance. No credit.
- Fraud: an internal fraud/risk scoring service owned by another team exists; integrate with it,
  don't design its model. Risk is about the transaction as a whole, not just the merchant.

### Not yet asked (watch)
- Non-functional: latency budget, scale, availability
- Implicit: compliance (PCI), multi-currency/FX, holds vs capture lifecycle, idempotency of network
  retries
- Q: must fraud be called synchronously? A (business req only): fraud verdict must be able to
  influence THIS transaction's decision (block before approval), not just post-hoc. Integration
  mechanism left to candidate.

### Candidate's API sketch (still in Phase 1)
`check_transaction(card_id, network_txn_id, amount, currency, merchant_id, merchant_category,
merchant_country)` — network_txn_id passed to fraud scorer synchronously.

### Non-functional — stakeholder answers
- ~10M daily active card users, ~3 card transactions/user/day on average.
- Peak ~5x average (lunchtime, Black Friday-type events). Candidate to derive QPS.
- Candidate estimate: 19.2k WPS avg, 96k peak -> concluded "shard DB to parallelize writes".
  !! Actual: 30M/day / 86,400 ≈ ~350/s avg, ~1.7k/s peak — candidate is off by ~55x. Challenged by
  asking for the derivation (not corrected directly). Also: jumped to a sharding decision during
  Phase 1, driven by the wrong number.
- Derivation given: 30M / 86,400 = 19.2k. Setup correct, division wrong. Asked to sanity-check the
  division (no correction stated).
- Self-corrected after one nudge: ~347 WPS avg, ~1.7k peak -> "single DB is enough, no sharding".
  Reversed the earlier sharding conclusion correctly. (Note for review: number-driven decision made
  and reversed within Phase 1; no read volume, latency budget, or availability asked yet.)

### Implicit — surfaced by candidate (unprompted) ✅
- Asked about legal audit + long-term log retention. First unprompted implicit requirement across
  sd-1..sd-3 (recurring weakness — positive data point).
- Stakeholder answer: every decision (approve/decline + reason + inputs) recorded immutably,
  retained 7 years; also used for disputes/chargebacks. Must not be lost even if the auth path is
  degraded.
- Asked interviewer for record size estimate -> reflected back: derive from own fields.
- Record fields: card_id, merchant_info, network_txn_id, amount, currency, fraud_score, decision,
  reason text. ~8 x 100B ≈ 800B -> rounded to 1KB/record.
- Storage: said "3M/day" (verbal slip — math actually uses 30M) x 365 x 7 x 1KB ≈ 76TB. Numbers
  check out.
- Tiering: hot = last 1 year ≈ 11TB in relational DB; cold = remaining 6 years in S3/Glacier
  (cost). Note: named concrete tech (S3/Glacier) already in Phase 1 — mild early-detail flag, not
  redirected.
- Still NOT asked: latency budget for auth response, availability target, behaviour when
  dependencies (fraud service, DB) are slow/down, network retries/duplicates, multi-currency.

### Security / compliance — surfaced by candidate (unprompted) ✅
- Raised PCI (2nd unprompted implicit requirement this session).
- Proposal: transparent on-disk encryption (TDE-style) so the app is unaware, "not accessible if
  they break our DB".
  !! Claim is inaccurate: transparent at-rest encryption protects against stolen disks/backups, not
  against someone with DB/query-level access (data is decrypted for any authenticated reader).
  Probed with one scenario question rather than corrected. Not yet addressed: whether PAN is stored
  at all vs tokenization, key management, in-transit encryption.
- Answer: "they only see info for their compromised account". Seems to read "service account" as a
  customer account / assume per-customer row isolation. Clarified scenario once: it's the auth
  service's own DB credential, which must read any card. Will not push further after this.
- Answer: "everything" (correct), then: credentials not reachable from outside; per-user creds for
  own data; admin/decrypt creds not reachable by a regular service account. Mitigation is about
  credential hygiene, not about limiting blast radius of data itself — no tokenization/vault for
  PAN, no app-level field encryption, no KMS/key separation mentioned. Per-user DB credentials is
  muddled for an issuer-side auth path (no end user is in the loop at auth time). Left it there —
  review item, not further probed.

### Phase 1 close (candidate-initiated transition)
Asked: functional checks, fraud integration timing, volume, audit retention (implicit), PCI
(implicit). Never asked: latency budget/network timeout, availability target, behaviour when
dependencies fail, duplicate/retried network messages, multi-currency (card in EUR acct, USD
merchant), hold/capture lifecycle (auth vs settlement), reversals/refunds.

## Phase 2 — High-level design
### Screenshot 01-mvp.png (copied from ~/Downloads/mock_revolut_payments.png)

Sticky notes on canvas:
- Functional: check_transaction(card_id, merchant, network_txn_id, amount, currency). Invariants:
  card active, balance sufficient.
- Non-functional: 10M DAU, 3 tx/AU, peak 5x; "347/s avg, 2K/s peak -> need sharding" (!! canvas
  still says sharding needed — contradicts the verbal "single DB, no sharding" conclusion);
  10.95TB/yr, 1y DB + 6y cold; p99 < 150ms; fraud p99 < 50ms, "sync but with hard stop at 1s
  because network hard limit 2s".
  !! 1s fraud timeout vs a 150ms p99 end-to-end budget — inconsistent. No fallback stated for what
  the decision is when fraud times out.
- Implicit: PCI, GDPR if EU users (3rd implicit, unprompted ✅), audit of decisions.

Three diagram iterations on the canvas:
1. Generic: Network -> LB/Gateway -> API Service -> Cache(read), DB, File Storage; Gateway -> Auth
   service.
2. "AUTH" flow: Network logs in via Gateway -> Auth service -> session token; API call with token ->
   API Service (check token). Treats network as a client that logs in.
3. Main flow: network -check_transaction-> LB/Gateway -> API Service (check JWT) ->
   - write approval/rejection -> DB
   - get fraud score -> Fraud scoring service -> result (sync)
   - Archiver (daily) reads DB -> moves archived txns -> File Storage
   - Cache (read) and Auth service drawn but unconnected.
   Response accept/reject flows back through gateway to network.

Observations (for later phases / review, not raised):
- Box-level, MVP-ish ✅ — no DB engines named in the diagram.
- No step that reads card status or account balance is drawn; the only DB arrow is "write
  approval/rejection". The two invariants on the sticky note have no component that enforces them.
- No hold/reservation of funds -> two concurrent auths on same account could both pass a balance
  check (double spend). Not drawn, not mentioned.
- Pre-flow ordering (card valid -> balance -> fraud -> decide -> persist -> respond) not explicit.
- Diagram still says "check JWT" after verbally deciding to drop JWT for server-to-server.
- Audit records and operational data share one DB; "must not lose an audit record" not addressed.
- Single API service / single DB — no stated redundancy yet (fine for MVP).
- (Late Phase 1 Q, asked after announcing the drawing) Latency + fraud SLA:
  - check_transaction: p99 ≤ 150ms internal target (receive -> respond). Card network hard timeout
    ~2s; past that the network times out / applies its own stand-in decision without us.
  - Fraud scoring: p50 ~10ms, p99 ~50ms, availability 99.9% — does degrade occasionally.
- Re-asked "is the network or end user doing the request?" — already answered in first stakeholder
  reply. Pointed out lightly. (Review: note-capture discipline per Karim.)
- Candidate realises caller is server-to-server (network), revising a JWT (end-user auth) approach
  in the drawing. Suggests the diagram initially assumed an end-user-facing API.
- Candidate moved straight to DB after sharing screenshot — did not verbally walk through the
  end-to-end HLD flow.

## Phase 3 — Low-level design

### Database
- Single DB: 2k/s peak absorbable by one node; prefer ACID + strong consistency over distributed
  consistency ("more complex and slow"). Trade-off stated ✅ (justification: volume fits + invariant
  needs strong consistency). Not yet: what happens when that one DB node fails (SPOF), replicas.
- Postgres: schema stable, no document needs, well-known isolation levels. Justified ✅ (mostly
  "why not NoSQL"; not yet which isolation level/locking it actually relies on).
- Schema `transactions`: transaction_id UUID PK, network_id UUID, amount DECIMAL >0, currency
  VARCHAR(8), status IN (accepted, rejected, error), created_at, merchant_id/category/country,
  idempotency_key UUID UNIQUE.
- Indexes: unique on idempotency_key (fast idempotency check); index on created_at for archiver.
  No other index needed for insertion.
  !! Missing vs own earlier record definition: card_id, fraud_score, decline reason.
  !! No cards / accounts / balances tables — the two invariants (card active, balance sufficient)
     have no data to be checked against.
  ? idempotency_key separate from network_id — where it comes from is unstated (the network's txn
    id is the natural dedupe key on retries).
  ? 'error' status — what's returned to the network in that case?
- Probed (one question): where card-status / balance data lives in this schema.
- `cards`: card_id UUID PK, status IN (active, expired), balance DECIMAL >= 0.
  - No FK from transactions.card_id to cards on purpose: must log invalid card ids from the network
    for audit. Good, justified ✅ (implies transactions gets a card_id column, not yet restated).
  - balance >= 0 CHECK as DB-level backstop ✅.
  !! Balance on the card, not on an account — stakeholder said card -> customer + account; a customer
     with physical + virtual cards on one account would have split balances. Not probed.
  !! status missing frozen/cancelled (stakeholder named them).
  ? No concurrency approach stated yet for check-then-debit (and is it a debit or a hold?).
- Q: who decrements the balance? Stakeholder answer (business lifecycle): approval doesn't move
  money; once approved, that amount must be unavailable for any later authorization (reserved for
  the merchant). Final posting happens at settlement/clearing, ~1-3 days later, from a separate
  network message, owned by another system — out of scope. Reserving at auth time IS in scope;
  mechanism is the candidate's.
- Reservation: decrement cards.balance on accept so later auths can't use it; needs a release path
  if the approved txn is never settled (expired auth) ✅ (unprompted). Release trigger/timeout and
  concurrency control for the decrement not stated yet. Note: decrementing the balance itself
  conflates "available" vs "ledger" balance — settlement system would then need to know not to
  debit again.
- Read replicas: archiver reads from replica so it doesn't contend with the write path; eventual
  consistency OK for a daily job ✅. Also cited "availability" — unclear whether that means
  replica promotion on primary failure (failover not described).
- No cache: traffic doesn't justify it; Postgres ACID is fast enough even at peak. Explicit
  simplicity trade-off ✅ (Cache bubble remains on canvas, unconnected).

### Archiver pipeline (candidate-designed in detail)
- Archiver wakes daily, marks rows to archive (new column) + writes job_id to an outbox in the same
  txn. Outbox relay worker publishes to a queue. Archive workers consume: "remove the row from DB
  and write on file storage". Ack-based, retry on visibility timeout, DLQ after N retries for audit.
  ✅ Correct outbox/at-least-once/DLQ vocabulary.
  !! Ordering stated as delete-then-write — crash between them loses an audit record, violating the
     explicit "never lose an audit record" requirement. Probed with a crash scenario.
  !! Proportionality: most detailed mechanism so far is on a daily, off-critical-path batch job,
     while the real-time auth path's hard parts (concurrent reservation, fraud timeout fallback,
     DB failover, latency budget, network retries) are still unaddressed. Not redirected (yet) —
     review item for session leadership/simplicity.
  ? Marking rows happens on the primary — interacts with "archiver reads from replica" claim.
- Revised after probe: archiver deletes the row AND writes an outbox entry (record payload) in one
  DB txn; relay publishes; worker writes to file storage with retries; DLQ after many failures.
  Fixes the crash window ✅ (atomic delete+outbox). Residual: once published, the record only
  exists in the queue/DLQ until written — durability now depends on queue retention; DLQ framed as
  "investigate", not as a guaranteed-durable holding area. Not probed further.
  Review: row-by-row DELETE of ~30M rows/day on the primary (bloat/vacuum, write contention with the
  auth path) — time-partitioned table + detach/drop partition never considered.

### Deployment
- Three independently deployable units: API, archiver, archive worker (+ implicitly outbox relay) —
  canary deployments. ✅ Covered unprompted (Karim's list). Not discussed: schema migrations on a
  single Postgres shared by all three, canary rollback signal/metric.

### Security
- Network authenticates with client credentials (id/password) via auth service, rotated every N
  months "per market standards". (No mTLS / network-signed messages; login/token round trip on a
  150ms hot path not considered.)
- Sensitive data: encrypted on disk (same TDE answer as Phase 1; tokenization/PAN handling still
  absent).
- HTTPS to the LB, TLS terminated at LB — certificates centralised for easy renew/revoke
  (justified ✅). Probed: traffic between LB and API carries card data — what's it like in clear?
- Answer: plaintext inside the internal network; cross-region later via private networks/VPN.
  !! Perimeter-trust model for cardholder data — PCI DSS / zero-trust expectation is encryption in
     transit internally too (mTLS / service mesh), and a breach of any internal host exposes card
     data. Not probed further — review item.
- Self-revised (unprompted follow-up): encrypt internal traffic with TLS too, but skip certificate
  validation internally "for simplicity". Partial improvement; TLS without validation gives no
  protection against an active MITM inside the network — mTLS is the standard answer. Review item.

### Edge cases / failure / observability (candidate-led)
- Fraud degraded: 1s timeout in API, then decide without fraud info. !! 1s vs 150ms p99 budget
  (same inconsistency as sticky note); default decision (approve? decline? rules-based?) unstated;
  no circuit breaker (had one in sd-2). Probed with a scenario.
- Archiver/worker crash mid-op: outbox + acked queue handles it ✅.
- Monitoring: host CPU/mem/disk/BW for all components; queue depth, DLQ size, message age;
  latency/throughput/errors on API, DB, archiver, worker. Broad infra coverage ✅, but no
  business-level metrics (approval/decline rate, fraud-fallback rate, timeouts vs network 2s
  limit, reservation releases) and no alerting thresholds.
- Still NOT covered on the critical path: concurrent reservations on the same card (race on
  balance), single Postgres primary failure / failover, duplicate network requests (retries ->
  idempotency key source), crash between decrement and responding to the network.
- Answer: p99 is compromised; add circuit breaker — skip fraud scoring while open; on recovery
  ramp a small % (half-open) and watch p99 before returning to full. ✅ breaker + gradual recovery.
  Didn't revisit the 1s timeout itself (still blows the budget before the breaker trips).
  Second half of question (what decision while fraud unavailable) unanswered — re-asked once.
- Answer: "business decision, not technical" — deferred. Pushed back as stakeholder: asked for a
  recommendation with reasoning (Karim: trade-offs from user AND business perspective).
- Recommendation: decline all while fraud is down — "fail fast, no fraud compensation later".
  Considered only fraud-loss side; no user-impact side (every customer's card declined during a
  fraud-service outage — 99.9% ≈ ~8.7h/yr), no middle ground (amount/MCC/risk-tier thresholds,
  local rules, approve small known-merchant txns). Pushed once from the user-impact angle.
- Revised: approve without fraud score, or fallback "business logic" without the score; fraud rate
  is low so blocking the majority is worse. Reached a defensible answer, but by flipping 180° under
  one pushback rather than laying out both sides first; middle-ground rules mentioned only in
  passing, not specified (e.g. amount caps, MCC/country rules, cap on exposure while breaker open).
  Opened with "that's why I'm not a business person" — framing to avoid in the real thing.
  Not pushed further.

## Phase 4 — Scaling (candidate-initiated)
- Jumped straight to multi-region (no "local" step: what breaks first on a single region — e.g.
  primary DB failover, hot cards, write IOPS — not discussed).
- Proposal: replicate the whole stack per region incl. write DB; cross-region RTT 100-150ms leaves no
  room in the 150ms p99 budget (latency-justified ✅). Geo-routing: requests go to the local region
  (Americas -> NA, Europe -> EU...). Background ETL backfills a central DB/file store for audit.
  !! Routing by where the transaction originates vs where the card's balance lives: an EU customer
     paying in the US hits the NA region, whose write DB doesn't own that card's balance. Probed
     with a traveller scenario.
- Candidate: doesn't know how networks route; asked whether merchant's or customer's side decides.
  Stakeholder answer (domain fact): network routes by the card's number range (BIN) to the
  issuer's configured connection endpoint(s); issuer chooses where requests for its card ranges are
  delivered; network backbone carries it from the merchant's country. So it's the card, not the
  merchant location. Implication left for candidate: "geo-routing by where the txn happens" as
  proposed doesn't hold.
- Revised: register BIN ranges per home region so each card's auths land in the region that owns
  its balance. Resolves the ownership problem ✅ (justified as "lowest latency" — real gain is
  single-writer ownership of the balance; the transatlantic hop is on the network's side anyway).
  Not yet: what happens when a home region is down (cards in that region can't authorize at all),
  cost of full per-region stacks, local -> regional step.
- Candidate closed with "I have finished all the design in my mind, any questions or extra
  improvements you want to make?" — same hand-back pattern as sd-2's close ("anything else?").
  Remaining gaps not self-named: concurrent reservation race, Postgres primary failover, network
  retry/idempotency source, region failure, cost, local -> regional step.
  Interviewer asked the Phase 4 degraded-mode/region-failure question (per mode file), not a list.
- Region failure: fail over to the next-nearest region via a region-to-region latency lookup;
  "transactions are independent, doesn't matter which API server decides"; prefer higher latency
  over declining all of Europe (user-impact reasoning ✅, applied unprompted this time).
  !! Contradiction: balances/card status live only in the dead EU write DB; fallback region has no
     data to check invariants against (and no reservation ownership). "Transactions are
     independent" is false — they share the card's balance. Probed: where does the fallback read
     balance/status from?
- Revised: transactions table stays region-local; cards table (status+balance) replicated to all
  regions as read replicas, each region authoritative for its own BINs. On isolation, the old
  region stops writing; next region on a priority list promotes itself to writer only if it sees
  a majority of other regions (quorum, avoids split-brain) ✅ — solid instinct.
  Gaps (not probed): async replication lag at failover -> reservations made just before the outage
  lost -> double-spend window (RPO); failback / reconciliation when EU returns; replicating EU
  cardholder balances to every region vs the GDPR/data-residency point the candidate raised
  themselves in Phase 1; cost of N full stacks + cross-region replication never discussed.

## Phase 5 — Wrap-up
- No questions for the interviewer. (Real interview: a missed chance to show interest in the team
  and the domain; prepare 1-2 questions.)
