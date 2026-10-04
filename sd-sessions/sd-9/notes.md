# sd-9 — Transaction history feed

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design the transaction history in the Revolut app: users see all their transactions — card
payments, transfers, top-ups, withdrawals, and so on — in one list, and can search and filter it.

(Interviewer-private: calibration mock — normal difficulty, technical focus, quarter-point scale,
J + K sections. Deliberately a different shape from sd-5..sd-8 (external provider + money path):
a **read-heavy, event-driven projection** (CQRS). Core: building one per-user feed from many
producer services' events, exactly-once/idempotent projection under at-least-once delivery,
out-of-order events and late updates (card pending → settled / amount changes, transfer returned,
top-up reversed — the "late reversal" MEDIUM item in a new form), pagination on a mutable list,
search/filter at scale, backfill/rebuild of the projection, read-your-writes after a payment.
Also tests schema completeness (MEDIUM) and Phase 4 bottleneck + cost (hot users, search index
size, cell-local projections). Keep the domain simple: producers publish events to a broker.)

## Phase 1 — Requirements

### Stated by interviewer (stakeholder answers)
- Q: read-only service? A: for the user, yes — they don't create or edit transactions here.
  Transactions are owned by other teams' services (cards, transfers, top-ups, withdrawals, …). Each
  publishes an **event to a shared message broker** whenever one of its transactions is created or
  changes. The feed can consume those events; how it gets/stores data is the candidate's design.
- Q: how many transaction types? A: ~15 types today from ~10 producer services; new types added a few
  times a year. Every event shares common fields (transaction id, user, amount, currency, status,
  timestamp, counterparty/merchant name) plus type-specific details.
- Q: show type-specific details? A: the **list** shows only common fields (icon by type, counterparty
  name, amount, status, date). Tapping a transaction opens a **detail screen** with the type-specific
  details (e.g. card: merchant category + location; transfer: masked destination account + reference).
- Q: how many events on the shared broker? every status change? how many transitions? will they change?
  A: yes, an event on creation and on every change. ~30M transactions/day → ~3 events each on average
  → **~90M events/day**. Producers map their internal states to a **common status set**: `pending`,
  `completed`, `declined`/`failed`, `reversed` (refunds/returns arrive later as `reversed` or as a new
  linked transaction). Card payments can also change **amount** between pending and completed. New
  statuses are rare; new types more common.
  (Held back unless asked: at-least-once delivery, ordering only per transaction id.)
- Q: other types changing amount? A: no — in practice only card payments (tips, hotel/fuel holds,
  currency conversion at settlement). Other types keep their amount; they only change status.
- Q: convert to a user-selected currency? A: no conversion by this service. Each transaction is shown
  in the currency of the account it affected (as sent in the event); for card payments abroad the
  event also carries the original merchant amount/currency, shown as secondary info.

### Candidate's functional list
- API: get a user's transaction history, with filters.
- Queue consumers: take transaction updates and save them to our DB.
- Q: which filters? A: type, status, date range, account (currency), amount range; plus **free-text
  search** on counterparty/merchant name and reference. Default order newest first; infinite scroll.
Interviewer-private: detail screen (stated earlier) not in the list yet.
- Candidate maps requirements to tech already: filters → Postgres; free-text → Postgres full-text or
  Elasticsearch (undecided); infinite scroll → **cursor pagination** (+); "even websocket / full-duplex
  with our service" for scrolling.
  Interviewer-private: tech choices inside Phase 1 (early, mild; not redirected). WebSocket for
  pagination = over-engineering (scrolling is plain request/response; a push channel would only be
  for live updates of new transactions). Watch.

### Non-functional
- Candidate: 90M events/day → ~1k events/s average ✔. Q: peaks? A: busiest daytime hours ≈2.5x the
  average; plus a **nightly burst** — card settlement is processed in batch, ~20M "pending →
  completed" events arrive within ~1 hour around 02:00; seasonal days (Black Friday, Christmas) ≈2x a
  normal day.
- Candidate: daytime peak 2.5k msg/s → no broker partitioning yet (be ready). Night burst 20M/1 h →
  5.56k msg/s ✔, off-hours → **tolerate processing lag until 6–7 AM** (+ explicit trade-off; though
  a backlog of hours means "pending" shown stale overnight — acceptable). Special days ~5k msg/s →
  scale consumers; 1 row insert/update per event → ~5k WPS → "doable on a single Postgres primary",
  be ready to shard; same for Elasticsearch.
  Interviewer-private: arithmetic ✔. 5k WPS + several secondary indexes (filters) + ES indexing on one
  primary is the 🟡 edge, stated as fine without an anchor; the burst-lag decision softens it. Reads
  not estimated yet.
- Q: latency/availability SLAs, retention? A:
  - Feed first page p99 < 300 ms; search p99 < 1 s.
  - **Freshness: a new transaction must appear in the feed within ~5 s of its event, at any time of
    day** (users open the app right after paying).
  - Availability (reads) 99.95%.
  - Retention: users can scroll back through their **whole history since account opening (up to ~10
    years)**; ~90% of views are within the last 3 months.
  Interviewer-private: the 5 s freshness "at any time of day" collides with the candidate's "let the
  02:00 burst lag until 6–7 AM" if new transactions share the same queue/consumers as settlement
  updates. Not pointed out — watch whether they reconcile it.
- Storage: common data ~8 cols × 50 B = 400 B/txn → 30M × 400 B × 365 = 4.38 TB/yr ✔ → 43.8 TB over
  10 years ✔. "4 TB OK for Postgres maintenance, 43 not" → keep 1 year in the DB, the rest in cold
  storage (cheaper, slower reads; fine since 90% of views are the last 3 months).
  Interviewer-private: (+) sizing + comparison. (−) Type-specific detail payloads not sized. (−) How a
  user scrolling to 2019 (or searching all history) is served from cold storage isn't defined —
  Glacier-class retrieval is minutes/hours; S3 needs a per-user, per-period layout to be readable.
  Watch.
- 5 s freshness: consumer throughput must keep up with queue depth; read recent transactions from the
  **primary** to avoid replica lag, or write-through to **Redis (TTL 60 s)**; Redis cache-aside (LRU)
  for reads in general.
  Interviewer-private: (+) replica lag recognised, read-your-writes reapplied. (−) Night-burst lag
  vs 5 s at any hour still unreconciled. Redis write-through *and* cache-aside on a paginated,
  filtered, mutable list → invalidation of cached pages on every status/amount change not addressed.

### Implicit requirements (candidate)
- No card numbers / payment processing here → AML, PCI, column encryption "not strictly needed".
  Only requirement: keep users' personal data in their region (GDPR).
  Interviewer-private: (+) residency again (4th mock running). (−) Security misjudgment at principle
  level: a full transaction history (counterparty names, merchants, amounts, references, masked
  accounts) is highly sensitive personal/financial data → at least encryption at rest + in transit,
  strict authZ (a user only ever reads their own feed — the key risk of this service), audit of
  internal access. "Not strictly needed" will cost in Security.
- Self-corrected unprompted: mask accounts in logs, **encrypt at rest**; authN via JWT from the auth
  service, verified in our service; **authZ: a user can only read their own transactions**. (+) fixes
  the previous statement within one turn, without a probe.
- Q: can events arrive out of order (completed before created)? A: **yes, it can happen**. Broker is
  at-least-once (duplicates possible). Producers key messages by transaction id, so events of one
  transaction are *usually* in order, but retries/rebalances can deliver an older event after a newer
  one. Every event carries the producer's per-transaction **sequence number** (monotonic) and an
  updated_at timestamp. (+) Candidate asked the key question themselves.
- Candidate: (transaction_id, sequence) as idempotency; keep the latest sequence per transaction;
  older sequence → drop (we already hold a newer state).
  Interviewer-private: (++) correct core mechanism (version-guarded upsert: `INSERT … ON CONFLICT
  (transaction_id) DO UPDATE … WHERE excluded.seq > feed.seq`) — handles duplicates AND reordering in
  one rule. Implicit assumption: each event carries the full current state (not a delta) — fine, not
  stated. Not yet said: is it one atomic conditional statement (vs read-compare-write race between two
  consumers)?

## Phase 3 — Core flow (candidate)
1. Consumer takes an event.
2. TX: `UPDATE transactions SET … WHERE transaction_id = :id AND seq < :seq`. 0 rows → we already have
   this or newer → ack & drop. 1 row → update status, updated_at (+ seq). Also update the Redis entry
   (if that's lost, readers fall back to the primary and re-cache). Same TX: **outbox** rows to index
   free text in **Elasticsearch** and write a detail document to a **NoSQL** store. Assumes detail and
   free text never change → outbox only on the `pending` event.
3. Outbox worker → ES insert / NoSQL write → mark outbox row sent.
Interviewer-private:
- (+) Version-guarded conditional update, CQRS split (Postgres list/filters, ES text, NoSQL detail),
  outbox to keep the three stores consistent with the source row.
- (−−) **Bug: a brand-new transaction never gets inserted** — the first event finds no row, UPDATE
  returns 0 → treated as "already have newer" → dropped. Needs an upsert (INSERT … ON CONFLICT DO
  UPDATE … WHERE excluded.seq > seq). Same for out-of-order "completed before created". **Probe asked.**
- (−) "Outbox only on pending": not every type starts pending (stakeholder: internal transfers are
  created directly as completed) and an out-of-order first event may be `completed`; card amounts
  change. Answered as stakeholder.
- (−) Free-text search combined with filters (status, amount, date) — if ES only has text and
  Postgres the mutable fields, a "uber + completed + last month" query needs both → ES needs the
  filterable fields too (and then status/amount changes must reach ES). Not yet visible to candidate.
- Redis update outside the TX (best effort) acknowledged — fine.
- Fix after probe: `INSERT … ON CONFLICT DO UPDATE` (upsert). ✔ Implicitly the seq guard goes on the
  DO UPDATE (`WHERE excluded.seq > seq`) — not spelled out. "Outbox only on pending" not revisited
  yet given the stakeholder answer.
- Q: is the first event's sequence always 0? A: yes — the creation event of every transaction has
  sequence 0, whatever its status (pending or completed). (It can still arrive after seq 1.)
- Refined: upsert; on conflict update only if incoming seq is newer; create the ES/NoSQL outbox rows
  **only when the INSERT branch happened** (first time we see the transaction, whatever its seq/status)
  → free text and details written once. Amount is never trusted from NoSQL — always served from the
  common table (card amounts change).
  Interviewer-private: (++) clean, handles out-of-order first events and the amount-change case.
  Remaining: ES holds only text → search + filters (status/amount/date) needs a join across stores or
  ES also holding the mutable filter fields (then status/amount updates must flow to ES too).

### Screenshot 01-high-level.png (new)
user → Reader API → {Redis cache-aside, Common info DB (Postgres), Freetext DB (Elastic), Detailed
info DB (NoSQL/KV)}; Redis → Postgres / Elastic / NoSQL; common shared queue → consumers →
{Postgres, Redis, Elastic, NoSQL}; outbox publisher (reads Postgres) → Elastic, NoSQL.
Interviewer-private: (−) **drift**: consumers drawn writing directly to Elastic and NoSQL *and* the
outbox publisher writing to them — spoken design says only via outbox. (−) Cold storage (>1 year,
stated in NFR) absent. (−) Reader query path for "text search + filters" (ES vs Postgres) not shown.
Overall box-level and readable.

### LLD — relational DB (candidate)
- 1 primary, no sharding; read replicas (lag accepted); read cache first, primary for recent
  transactions (read-your-writes for the common "just paid" case).
- transactions(transaction_id PK, user_id, account_id, type (CHECK on current types, or relax and
  filter unknown in SELECT), amount >0, currency CHAR(3), status IN (pending, completed, declined,
  failed, reversed), counterparty, seq_number BIGINT, updated_at).
- outbox(transaction_id, status created/sent, type freetext/detailed, body, created_at),
  UNIQUE(transaction_id, type).
- Indexes: reads → (type), (status), (updated_at), (account_id), (amount); publisher → (status,
  created_at); consumer → PK + "seq_number must be indexed".
Interviewer-private:
- (+) UNIQUE(transaction_id, type) on outbox; thought about new types vs the CHECK constraint.
- (−−) **No transaction time** (occurred_at). The only timestamp is updated_at → sorting the feed by it
  makes a payment jump to the top whenever its status changes (02:00 settlement burst reorders
  everyone's history) and breaks cursor pagination. **Probe asked.**
- (−) **Indexes regress to single-column**: every read is per user → (user_id, occurred_at DESC) and
  per-user composites for filters; single-column (type)/(status)/(amount) are near-useless at 10B rows
  and add write cost at 5k WPS. sd-7 J lesson (per-user composite) not applied here.
- (−) seq_number index unnecessary (row fetched by PK, seq compared in place).
- (−) No direction (incoming vs outgoing) with amount > 0 — minor.
- Fix after probe: order by the user's action time (created_at of the transaction), not the event's
  updated_at; updates would otherwise reorder and corrupt scrolling. ✔
  Interviewer-private: cursor needs a tie-breaker (created_at, transaction_id) — not said; indexes not
  revisited to (user_id, created_at DESC).
- NoSQL detail store keyed/indexed by transaction_id for fast detail reads. ✔ (It's simply the
  partition/primary key of a KV/document store.) Ownership check on detail reads (user_id in the doc
  or verified via Postgres) not mentioned.

### Infra / ops (candidate)
- Consumers, outbox publisher, reader API scale horizontally; Postgres 1 primary + N replicas; Redis HA
  cluster; canary, independent deploys; resource monitoring everywhere; throughput/latency/errors at
  every hop; average message processing time.
  Interviewer-private: (+) complete baseline. (−) The SLI that matters here — **event-to-visible lag**
  (consumer lag in seconds vs the 5 s freshness target) and outbox backlog age — not named explicitly
  ("average processing time" is close). ES/NoSQL HA not mentioned.
- Security restated: encrypted at rest, HTTPS to termination, mTLS internally, redaction in views and
  logs (+ authN JWT / authZ own-transactions said earlier). ✔ principle level, complete for this
  calibration. ES and Redis copies of the data also need the same protection — not said (minor).

### Edge cases (candidate-led, listed then answered)
1. Duplicates / out-of-order → (transaction_id, seq) guard; outbox only on insert; older events don't
   overwrite. ✔
2. Consumer crashes before writing → no ack → broker redelivers to another consumer; idempotent. ✔
3. Consumer fails before the outbox insert → same TX as the row → rollback; retry or let the broker
   redeliver. ✔
4. Outbox publisher crashes after reading, before writing to the target → status stays `created` →
   picked again; only marked sent after a successful write. ✔ (Implicit: ES/NoSQL writes keyed by
   transaction_id are idempotent upserts — not said.)
5. Postgres primary down → synchronous replica in another region in the same jurisdiction. ✔
6. Region down → whole cell fails over to the fallback region in the jurisdiction. ✔
Interviewer-private:
- (+) Six cases, each with the right mechanism, unprompted; detect side partly via monitoring.
- (−) The design tension stated in Phase 1 is still open: **night-burst lag "until 6–7 AM" vs "new
  transactions visible within 5 s at any time"** — they share the queue/consumers. **Probe asked.**
- Not covered: Elasticsearch/NoSQL down → outbox backlog grows (search/details stale; list still
  works — graceful degradation could be stated); late reversal shown as a *new linked transaction*.
- Answer: "hadn't thought about it" → on each feed read, also query the source-of-truth producer services
  for the user's last 5–10 minutes (by created_at) and merge.
  Interviewer-private: (−) works functionally but couples every feed read to ~10 producer services
  (fan-out per request, p99 = slowest producer, availability = product of all, extra load on
  payment-critical systems), and contradicts the CQRS split the design is built on. Simpler: separate
  the predictable batch traffic — **its own topic/consumer group (or priority lane)** for settlement
  updates vs new transactions, and/or **pre-scale consumers before 02:00** (the burst is scheduled).
  Challenged once on cost (latency/availability), no alternative given.
- Candidate rejects own fan-out ("horrible UX") and asks: can the shared broker have priority queues?
  A (stakeholder/infra): yes — the broker supports multiple topics, and producer teams can publish
  real-time events and the nightly batch settlement updates to separate topics if this feature asks
  them to.
- Fix: two topics with **separate consumer groups** (the 15M batch can't delay real-time events), or one
  consumer that always drains real-time first. ✔ Good resolution after two pushes. (Cross-topic
  reordering is already safe thanks to the seq guard — not said, but holds.) Pre-scaling consumers
  for the scheduled burst not mentioned.

## Phase 4 — L → R → G (candidate-led)
- Cell replicated per region; users hit their own cell; the shared broker is federated so each region
  only receives its own events; global = same; each legal region deployed to 2 regions in the same
  jurisdiction for failover.
  Interviewer-private: (+) residency 4th mock running, consistent. (−) Again no new bottleneck / cost
  at scale → **pushed once** (as in sd-8).
- Answer: consumers scale out; the ceiling is the **Postgres primary** (too many writes/s, too much data
  to query) → **shard by user_id**.
  Interviewer-private: (+) right bottleneck and right key (every read is per user → single-shard reads).
  (−) No numbers (900M/day → ~10k/s avg, ~25k/s daytime peak, ~55k/s in the burst), and the cost of
  sharding not spelled out (resharding/rebalancing, cross-user queries become scatter-gather, ops
  burden, hot users). ES/Redis scaling (routing by user_id) not mentioned. Needed the push (MEDIUM
  item: still not unprompted).
