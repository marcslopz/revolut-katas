# sd-8 — Mobile phone top-ups

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design a feature that lets Revolut users buy mobile phone credit (a top-up) for any phone number,
in any country, from the Revolut app.

(Interviewer-private: calibration mock — normal difficulty, technical focus, quarter-point scale,
review sections J + K. Varies from sd-1..sd-7. Targets the new HIGH item: failure paths for an
external call without being asked — the top-up aggregator can succeed, reject (invalid number /
operator down), time out (unknown outcome), or reverse later (operator refund). Also tests the
MEDIUM money path (one more clean mock resolves it) and Phase 4 bottleneck + cost (operator /
aggregator rate limits, catalog of products per operator cached globally — non-personal reference
data). Keep domain simple: one external aggregator API that covers all operators; catalog of fixed
denominations per operator; results synchronous for most, async callback for some.)

## Phase 1 — Requirements

### Stated by interviewer (stakeholder answers)
- Candidate unfamiliar with top-ups; asked if it's like a bank transfer via a provider but with a
  phone number. Explained the domain (simple, no failure modes volunteered):
  - Very similar shape. User pays from their Revolut balance; Revolut calls ONE external **top-up
    aggregator** (covers all operators worldwide) with phone number + product; the aggregator tells
    the mobile operator; the credit appears on the phone.
  - Products are fixed amounts per operator (e.g. "Vodafone Spain €10", "Airtel India ₹500"),
    listed in a **catalog** from the aggregator. Price shown to the user in their account currency.
  - Revolut pays the aggregator in bulk from its own prepaid balance there — the user never deals
    with that.
  - Most top-ups confirm in a few seconds in the API response; some operators confirm later via a
    callback.
- Q: €5 when the minimum is €10? A: users can only pick catalog products; no custom amounts. If
  the operator's smallest product is €10, €5 isn't possible.
- Q: how does the aggregator say which amounts are possible from just a phone number? A: aggregator
  API has (1) **lookup(phone) → operator + country + products valid for that number**, and (2) a
  **full catalog** endpoint (all operators × products, changes a few times a day). Plus (3) the
  top-up call itself.
- Q: aggregator latency? A: lookup(phone) ~300 ms typical, p99 ~2 s. Full catalog ≈ 50k products,
  several seconds to download — meant to be pulled periodically, not per user request. Top-up call
  ~2–5 s typical, can take up to ~30 s before the aggregator answers.
  (Held back unless asked: aggregator rate limits.)
- Candidate: cache the catalog in Redis with a TTL (design detail in Phase 1 — fine, driven by the
  latency answer). Q: how long is the catalog valid / how often does it change? A: changes ~3–4
  times a day (mostly price updates, occasionally products added/removed); business accepts showing
  a catalog up to ~1 hour old.
- Candidate: TTL ~1 hour "to avoid hitting the provider on each phone lookup".
  Interviewer-private: conflation — the catalog cache answers "products per operator", but finding
  *which operator* a number belongs to still needs the per-number lookup (numbers move between
  operators), unless lookups are cached per number too. Not corrected; watch whether it surfaces.
- Q: top-up call sync or async? Partly a re-ask (said earlier: most confirm in the response, some via
  callback) — pointed out lightly. Added the contract: synchronous response with status
  `success` | `failed` | `pending`; `pending` → final result later via callback (usually minutes,
  rarely up to 24 h).

### Candidate's functional flow (spoken, combined F + core design)
1. GET options for a number: top-up API → aggregator lookup(phone) + operator catalog (catalog
   cached in Redis, TTL 1 h).
2. User picks catalog_id → POST top-up.
3. **TX1**: conditional hold (`available >= amount`, 0 rows → insufficient balance); create
   topup_payment (client idempotency key) status created; **outbox** row with user_id, account_id,
   amount, currency (catalog item has its own currency), phone, catalog_id, topup_payment_id.
4. Worker consumes from the queue; idempotency by payment id (if already sent/waiting → check status
   at the provider instead of re-sending). First time: call aggregator with
   **key = topup_payment_id**, wait for the sync response:
   - success → TX2: status succeeded, settle hold/balance/available, ledger 2 rows (user debit,
     credit "for the phone number");
   - failed → TX3: release hold, status failed;
   - pending → TX4: status waiting.
5. Callback (webhook) with topup_payment_id + success/fail → same TX2/TX3; dedupe if already
   terminal (drop duplicate).
6. **Checker**: rows `waiting` with last_checked_at < now − N hours → query aggregator status →
   settle or bump last_checked_at.
Interviewer-private:
- (++) **HIGH item fired unprompted**: all three provider outcomes handled with their effect on
  status + hold, callback dedupe, and a checker/recovery worker with explicit selection criteria —
  all before any probe. Money path entity-first again (hold → row → outbox → idempotent provider
  key → atomic settle).
- (−) Timeout / no response within ~30 s (unknown outcome) not named explicitly — partly covered by
  "if already sent, check status" on redelivery; but rows stuck in `created`/`sent` (worker crashed
  mid-call) — the checker only scans `waiting`.
- (−) Late reversal (operator refunds a delivered top-up) not covered (not asked by me).
- (−) Ledger counterpart "credit for the phone number" — should be an internal account (aggregator
  payable / prepaid float), not a phone number.
- (−) Dedupe phrased as "check if already terminal, drop" — conditional UPDATE is the race-free form.
- Phase discipline: functional reqs and core LLD merged (same as sd-7) — not redirected; content
  strong.

### Screenshot 01-high-level.png (new)
user → top-up API service → {catalog cache → top-up external provider ("lookup phone number / get
catalog"), DB, message queue}; message queue → top-up worker → provider ("top-up");
provider → worker ("success/failed/pending"); checker worker → DB and → provider ("check payment").
Drift vs spoken: API → queue directly (spoken: outbox in TX1; no outbox relay box); no worker → DB
edge (worker writes TX2–TX4); no webhook/callback receiver drawn.

### Non-functional — stakeholder answers (asked throughput, latency, availability, retention)
- Top-ups: ~600k/day; evening peak hour ≈3x the hourly average.
- Phone lookups / options screens: ~3M/day.
- Latency: options screen p99 < 2 s (bounded by the aggregator); POST top-up responds p99 < 500 ms
  with "processing"; most users should see the final result within ~10 s.
- Availability: 99.9%.
- Retention: top-up records 5 years.

### Estimation (candidate)
- 600k/day → 25k/h → ×3 = 75k in the peak hour → 20.83 top-ups/s ✔ "very low"; ×~10 row writes per
  top-up → "200.83" writes/s (slip: 208) → no sharding. (+) rows-per-event + explicit judgement.
  Lookups (3M/day) not converted yet.
- Reads: 3M/day → 34.7/s ✔ (average; peak ≈ ×3 not applied) "not much". Provider p99 < 2 s, but
  when cached → ms (Redis in memory). HA Redis cluster to avoid a SPOF.
  Interviewer-private: same conflation as before — the catalog is cached, but the per-number lookup
  (which operator?) still goes to the aggregator unless numbers are cached too. **Probe asked.**
- Answer: two cache layers — phone number → operator (numbers rarely change operator) and catalog per
  operator (LRU for recently used operators). New number → miss → aggregator lookup → operator_id →
  catalog from Redis (hit) or from the aggregator, then cached.
  Interviewer-private: (+) resolved cleanly after one probe; two-level cache-aside is right.
  (−) No TTL stated for the number cache (portability → days, not forever); phone numbers are
  personal data of the recipient (often not a Revolut user) → the cache lives in the user's cell,
  with a TTL; not mentioned (bonus-level for this calibration, but the TTL is technical).
- Latency budget for POST top-up (p99 < 500 ms "processing"): one Postgres primary, <1k writes/s;
  TX1 (hold + row + outbox) ~10–50 ms intra-region; ~10 ms network round trip → <100 ms, >400 ms
  headroom. (+) Explicit budget breakdown (lesson from the 2026-10-04 drill case 5). Minor: write
  latency is dominated by the WAL commit/fsync, not disk reads.
- ~10 s final-result budget: worker pickup 0.5–1 s + call 50 ms + provider 2–5 s (up to 30 s) →
  the **provider is the bottleneck**; scaling producers/consumers doesn't reduce its latency.
  Interviewer-private: (+) bottleneck named. (−) Latency ≠ throughput: at 21/s × 5 s ≈ 100 calls in
  flight (×30 s worst case ≈ 600) → workers need enough concurrency (Little's law) or the queue backs
  up; the real throughput limit would be the aggregator's rate limit (not asked). How the app learns
  the final result (push vs polling) not stated.

### Implicit requirements (candidate)
- Top-up can't exceed the user's balance (invariant; already enforced by the conditional hold).
- Phone numbers are PII → encrypt at rest with a key held in a KMS/vault (field-level, symmetric —
  "shared secret"), HTTPS externally, mTLS internally. (+) principle-level, sufficient per
  calibration; field-level encryption > disk-only.
- Not mentioned this time: where data lives (residency) — expected to come in Phase 4; abuse/fraud
  (stolen accounts draining balance via top-ups) — bonus.
- Residency: user data lives in the user's region cell → no cross-region GDPR concern. (+) third
  mock running. Bonus-level gap: the phone number does leave the cell — to the external aggregator
  (possibly another country) — minimal data to a processor; not mentioned.
- Storage: ~8 columns × ~50 B ≈ 400 B/record; 600k × 365 × 400 B = 87.6 GB/yr ✔, 438 GB over 5 years ✔
  → fine for one Postgres ("without any problems") — comparison stated. Optionally archive >1 year to
  S3/Glacier for faster updates/queries if rarely read. (Re-asked the 600k/day figure — had it right.)
  Interviewer-private: excluded ledger rows/outbox from sizing (outbox can be purged) — fine.

## Phase 3 — Low-level design
- DB: Postgres, no sharding → no distributed transactions, strongly consistent writes (ACID — the
  design-specific justification, finally stated up front). Read replicas with eventual consistency
  for views; **read-after-write from the primary** for recently created top-ups. (+) sd-7 J-section
  lesson (read-your-writes) applied unprompted.

### Schema (spoken)
accounts(account_id PK, user_id FK, balance ≥0, hold ≥0, available ≥0, CHECK hold + available ≤
balance, updated_at).
ledger(payment_id FK, amount signed, currency, debitor_id NULL FK, creditor_id NULL FK).
topup_payments(payment_id PK, user_id, account_id, catalog_id, currency, amount >0, status IN
(created, waiting, succeeded, failed), checked_at, created_at).
Indexes: publisher `WHERE status='created' ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED` →
(status, created_at); checker `status='waiting' AND checked_at < now − N` → (status, checked_at);
user view `user_id = X ORDER BY created_at DESC` → (user_id, created_at); everything else by PK.
Interviewer-private:
- (+) Indexes derived from the actual queries, composite and correctly ordered, SKIP LOCKED for the
  publisher — sd-7 J-section lesson (per-user composite index) applied.
- (−) topup_payments is missing: **destination phone number** (encrypted — the key field of the
  feature), the **client idempotency key + UNIQUE**, the **aggregator reference**, updated_at.
- (−) No `sent` state between created and the provider's answer: a worker that crashes mid-call
  leaves the row `created` (re-published → same key → safe) — fine, but the checker only scans
  `waiting`. 
- (−) Drift: TX1 wrote an **outbox** row; here the publisher polls `topup_payments` status =
  created (status-as-outbox). Either works; pick one.
- (−) accounts CHECK should be hold + available = balance; ledger mixes a signed amount with
  debitor/creditor columns (single-row transfer model) while the spoken flow said two rows; no entry
  PK / account_id per entry. Minor.
- Partial indexes (`WHERE status IN ('created','waiting')`) would stay tiny — optional.

### Infra (candidate)
- Broker: at-least-once, durable messages, passive broker fallback (HA) → no lost messages;
  duplicates deduped by payment_id. Outbox gets a status (sent/published) set when the broker acks
  the publish. Broker keeps the message until the worker acks.
  Interviewer-private: (+) correct mechanics. Confirms the outbox approach → the schema's publisher
  query on topup_payments(status='created') is the drifting piece.
- Deploy/observability: canary per service, independent scaling; per-block CPU/mem/disk, latency,
  throughput, errors; queue age + unacked count; DLQ (poison after N retries) with alerts for root
  cause; aggregator error % and latency; **error % per operator, per country, per catalog entry**.
  Interviewer-private: (+) business-level breakdown (per operator/country) — the sd-5 gap closed.
  Minor: no SLI for "% of top-ups final within 10 s" or count of rows stuck in waiting.

### Edge cases (candidate-led, listed then answered)
1. API crashes mid TX1 → TX rolls back; client retries with its idempotency key → insert payment +
   outbox if not there. ✔
2. Publisher crashes before publish / before broker ack → republish; duplicates collapse on
   payment_id at the consumer. ✔
3. Aggregator 5xx on lookup/catalog → circuit breaker, fail fast, tell the user. On top-ups → circuit
   breaker pauses publisher + consumer, and **disable new top-ups in the UI** until resolved
   (don't accumulate holds/backlog). ✔ (+) graceful degradation stated unprompted.
4. Slow/timeouts → consumer retries with the same key (idempotent); sustained → same breaker, stop
   accepting new top-ups. ✔ (unknown outcome handled via idempotent retry.)
5. Worker crashes before calling the provider / before acking → broker redelivers → worker re-sends
   unless already waiting (same key makes a re-send after an accepted call safe). ✔
6. Region down → fail over to a **synchronous** standby / second region **in the same legal region**
   (Frankfurt + Paris for EU). ✔ (+) both sd-7 J-section corrections (sync standby, second region in
   the jurisdiction) applied unprompted.
Interviewer-private:
- (++) **HIGH item: success / failed / pending / 5xx / timeout all covered without being asked**,
  plus detection (monitoring) and recovery (checker). Only the 4th outcome — **late reversal** — is
  missing. **Probe asked.**
- Minor: during a long breaker-open period, top-ups already held stay held — when to give up and
  release (deadline) not stated.
- Answer: compensation — callback handler writes a "reverse top-up" outbox message; the worker
  consumes it, sets status `reversed`, credits balance/available, adds the two reversing ledger rows.
  Interviewer-private: ✔ correct outcome. (−) Extra hop: the reversal touches only our own DB, so the
  callback handler can do it in **one TX** (`UPDATE … WHERE status='succeeded'` → reversed + ledger +
  balance); outbox is for side effects on *other* systems. Minor over-engineering. Dedupe of a
  duplicate reversal callback and notifying the user not mentioned.

## Phase 4 — L → R → G (candidate-led)
- Today a cell in the EU; tomorrow US → replicate the cell across two US regions, same or a different
  aggregator depending on its availability there. Traffic always local; phone numbers and the
  aggregator catalogs are global. Global = same pattern per region.
  Interviewer-private: (+) cell topology + two regions per jurisdiction consistent; residency 3rd
  mock running. (−) Still no new bottleneck or cost named at scale (MEDIUM item). **Probe asked**
  (Phase 4 guidance: push scale, ask for the new bottleneck and its cost).
- Answer: 6M/day → 69.44/s → ~694 writes/s → DB still fine; storage "below 1 TB" so 10x doesn't break
  (archive earlier); API/publisher/worker scale out → **bottleneck = the aggregator**; queue grows.
  Mitigations: per-user rate limit (if business allows), **multiple aggregator contracts with traffic
  split**, or **pay more** for better SLAs/latency.
  Interviewer-private: (+) bottleneck named + options with cost (money, contracts) — MEDIUM Phase 4
  item addressed after one push. (−) Estimation slips: used the **daily average** (69/s) instead of the
  peak (×3 ≈ 208/s → ~2k writes/s); storage 10x of 438 GB ≈ 4.4 TB over 5 years, not "<1 TB" (still
  fine split across 5 cells ~0.9 TB each — conclusion holds, reasoning off). (−) Cost of the
  multi-provider option not spelled out (routing layer, per-provider reconciliation, failover between
  providers needs a provider-agnostic status model).
