# sd-16 — Click & collect for a retail chain (full mock, stock domain)

Interviewer's running transcription — not candidate-authored. Updated per phase and on new screenshots.
Full mock under `modes/system-design/interviewer.md` (quiet interviewer, candidate leads). Numbered 16, not 13,
to avoid colliding with the sd-13/14/15-focused lite mocks from the same day.

## Problem statement
Design a click-and-collect system for a retail chain: customers reserve products online and pick them up in
a store.

(Interviewer-private: 40-minute scope rule. Keep answers minimal. Core: **per-store stock shared between
online reservations and in-store till sales we can't block**. Simplest rules:
- ~200 stores, **one country**; ~20k SKUs, stock tracked **per store**.
- Customer picks a store, reserves items; **no online payment** — pays at pickup. Store staff **pick the items to
  a hold shelf**; customer has **48 h** to collect, else items go back to the shelf (released).
- In-store **till (POS) sales are never blocked**; each till sale is sent to us as an event **within a few
  seconds** (at-least-once). Stock count can therefore drop below what's been reserved online → at pick time
  staff may not find an item → that line is cancelled, customer notified (notification = out of scope, one line).
- Deliveries to stores recorded by staff (as before).
- Dominant action: **"which nearby stores have this product in stock?"** (product page + store picker).
- Numbers (only if asked): ~3M product/availability views/day; ~40k reservations/day (~3 lines each); ~1.5M till
  sales lines/day across all stores; ~2k delivery lines/day; traffic 8:00–22:00, evening peak ~3x; staff pick
  within 2 h of the reservation.
- Out of scope: payment, delivery to home, pricing, loyalty, notifications beyond "notify the customer".
Targets: dominant read designed first (per store per SKU availability, nearby stores — index (sku_id, store_id) or
per-store lookup); reservation as conditional decrement of `available`; POS events as unrejectable decrements that
may make `available` negative → shortfall at pick → cancel line; counters on every transition (pick, collect,
48 h expiry, POS event, cancel); timer races (customer arrives as the 48 h expiry fires); idempotent POS events
(till_id, sale_id); estimates incl. POS write rate (~1.5M/day ≫ reservations) — the real write load; Phase 4 opened
unprompted (more countries → per-country cell / data stays local; hot store/SKU; POS event burst at closing).)

## Phase 1 — Requirements

- Q: actors and actions? A: actors — **customers** (online), **store staff**, and the stores' **tills (POS)**, an
  existing system that sells the same stock in-store. Actions, most common first: (1) customers **view a product and
  see which stores have it in stock**; (2) customers **reserve items at one store**; (3) staff **pick reserved items
  to a hold shelf**; (4) customer **collects and pays in the store**; (5) **in-store till sales** of the same stock;
  (6) staff **record deliveries** to the store.
- Q: are tills the staff selling in the store? A: yes — cashiers ring up walk-in shoppers at the till; a shopper can
  take any item off the shelf, including ones we've reserved online if they haven't been picked yet. The till system
  is existing (not ours) and **reports each sale to us**.
- Q: more than one SKU per reservation? A: yes — several SKUs, each with a quantity, **all at the same store**.
- Q: deliveries with several SKUs? recorded once items are in the store? A: yes and yes — one delivery = several
  SKU lines; recorded when the goods are physically in the store (sellable from then on).
- (+) Moves to NFRs explicitly, asks volumes per actor. A: **~200 stores, one country, ~20k SKUs**; customers **~3M
  product/availability views/day**, **~40k reservations/day** (~3 lines each); tills **~1.5M sale lines/day** across all
  stores; staff **~2k delivery lines/day**, picks ≈ reservations; stores open **8:00–22:00**, evening peak **~3x**.
- Q: online reservations outside store hours? A: yes, online is 24/7, but online traffic follows roughly the same
  8:00–22:00 window; reservations made at night are picked when the store opens.
- Estimates (candidate):
  - Online writes: 40k × 3 lines × 2 (reserve + pick) + 2k deliveries → ~10k/h → **~3 WPS**, negligible vs stores.
  - Till writes: 1.5M / 14 h → ~100k/h → **~30 WPS** → peak ×10 → **~300 WPS** → single writer, "prepared to shard by
    user_id or sku_id".
  - Reads: 3M/day → **34.7 QPS** → peak ×10 → **~350 QPS** → same primary, no read replicas; **sync-replicated HA
    standby with failover**; read replicas + eventual consistency only if it grows.
  (Interviewer-private: (+) **identified the till writes as the real write load** (1.5M ≫ reservations) — the key number;
  comparison sentences; replica reflex gone, HA standby named. Minor: peak ×10 vs the stated ~3x (conservative, harmless);
  online and reads divided by 24 h instead of 14 h (×1.7, harmless). Watch: "shard by user_id" makes no sense for
  per-store stock — natural key would be store_id; not probed now.)
- Implicit reqs (candidate): customer data stored → encryption in transit (HTTPS/mTLS) and at rest (keys in KMS); EU
  residency — one country, so no cross-jurisdiction move at this scope. (+) principle-level, unprompted. (Interviewer-
  private: all generic; domain-specific ones not asked yet — how long a reservation is held, what happens if a till
  sells a reserved item, how fast till sales reach us, can a till sale be refused.)
- Q: SLAs latency/availability? A: availability views **p99 < 300 ms**, may be **a few seconds stale**; reservation
  confirmed to the customer **< 1 s**; **99.9%** for customer-facing. **Tills never depend on us** — they keep selling if
  we're down; their sales reach us normally **within a few seconds**, delivered at-least-once.

## Phase 2 — High-level design

- Screenshot `01-requirements-mvp.png`:
  - Canvas notes: Customers (view_product_stock, reserve_product); Staff (pickup_reserved_items, record_delivery); Till
    (sell_item); volumes; "writes 300 WPS, reads 340 QPS, no need for sharding or read replicas yet"; SLA note incl.
    "tills can sell with our system down (offline service with DB and queues to decouple)". (+) captures everything on
    the canvas as Karim asked.
  - Diagram: user/staff → Auth service (creds → JWT) → **store stock service API** → DB. Inside a dashed **store private
    network**: till ↔ store auth; till → **sell service** → **sell DB** → **sell events publisher (outbox)** → sell events
    queue → **sell events consumer** → store stock service API.
  (Interviewer-private: skeleton-level, prerequisite auth before the main action. The till side is drawn as our own
  system (sell service + DB + outbox + queue) although it was stated as **existing, not ours, and it reports each sale**
  — extra boxes beyond scope; what matters is the inbound event (at-least-once). Customer **collect/pay at pickup**
  action missing from the sticky; hold duration / uncollected reservations not asked yet.)
- Candidate: the store system is **out of scope**, drawn only to illustrate that tills record sales offline and sales
  reach us as messages via a consumer → tills decoupled, keep selling if we're down. (+) clarified unprompted — the
  boundary is the inbound sale message.

## Phase 3 — Low-level design

- Moves to low-level design starting with tables (no end-to-end flow walked at box level first). **Postgres** —
  transactions, joins, relational preference. (Justification brief; no alternative weighed.)
- Q: till ids live outside our system — only store_id matters for sell_items, we don't care who sold? A: right, we
  don't track the cashier. Message format (fact about the external system): **store_id, till_id, sale_id (unique per
  till), lines (sku_id, quantity), sold_at**.
- Screenshot `02-tables-draft.png` (draft; indexes/constraints/statuses/idempotency keys still to add):
  - `stores(id, ...)`; `users(id, type IN (customer, staff, store), ...)`; `skus(id, name, description, price > 0)`
  - `orders(id, ordered_by FK — "store or customer", status IN (created, reserved, completed, failed), created_at,
    reserved_at — "staff picks to the shelf", completed_at — "customer pays and collects", failed_at — "customer comes
    and we don't have stock")`
  - `order_lines(id, sku_id, quantity > 0, price > 0)`
  (Interviewer-private, not raised — candidate said it's a draft: **no stock table at all** (per store × SKU counts) —
  the core of the prompt; `orders` has **no store_id**; `order_lines` has **no order_id**; till sales modelled as orders
  ("ordered_by = store"); "failed" discovered when the customer arrives rather than at pick; no state for uncollected
  reservations.)
- Candidate: audit of all actions (user / till-store / staff) — explicitly **parked as a later improvement** for time.
  (+) conscious scoping.
- Workflows. Q (re-ask, answered in the first answer): view_product_stock — total or per store? A (noted lightly it was
  covered): **per store** — the customer sees **which nearby stores** have it (e.g. the ~10 closest to their location;
  store locations are static), each with in stock / low / out.
- Candidate: store location in `stores`, user location in `users`, sort by distance; "even better" **pre-compute each
  user's distance to every store** in another table and search by distance ASC.
  (Interviewer-private: over-engineered — users × 200 stores rows, recomputed when a user moves; with 200 static stores
  the distance from the request's location to all 200 can be computed on the fly in memory (or PostGIS). Customer
  location also usually comes from the request, not a stored column. Not raised.)
- Workflow view_product_stock (reads eventually consistent — stock may change before reserving):
  (1) `SELECT ... FROM user_distances WHERE user_id = ? ORDER BY distance LIMIT 10` — index `(user_id, distance)`;
  optional **Redis cache, long TTL** (locations rarely change).
  (2) `SELECT available_quantity FROM sku_stores WHERE sku_id = ? AND store_id IN (...)` — 10 rows, no pagination,
  index `(sku_id, store_id)`.
  (Interviewer-private: (+) dominant read designed first, query → index stated; **`sku_stores` (stock per store × SKU)
  appears here for the first time** — not in the drawn tables yet. Redis on top of a precomputed table for ~200 static
  stores = two extra pieces for a trivially small computation.)
- Q (re-ask, answered in Phase 1): reserve = several SKU lines, different quantities, same store? A: yes, as said.
- Workflow reserve_products (one tx): `SELECT ... FOR UPDATE` the `sku_stores` rows of all requested SKUs at that store,
  **ordered by sku_id (no deadlocks)**; per line **conditional update** of `available_quantity` if enough; any 0-rows →
  rollback, "no stock"; insert `orders` ('created') + `order_lines`; commit.
  (+) all-or-nothing reservation, lock ordering and conditional decrement stated while designing. (Explicit lock +
  conditional update is belt-and-braces; fine.) Not mentioned: client retry / double submit (idempotency key);
  `orders.store_id` still absent from the drawn table.
- Workflow pickup (staff): conditional `UPDATE orders SET status = 'reserved', reserved_at = now() WHERE id = ? AND status =
  'created'`; commit. (+) conditional transition. (Interviewer-private: no stock counter touched — only `available` exists
  so far, no physical `quantity`; and what if staff **can't find** the item on the shelf (sold at a till first) — not
  covered; the "reserved" name for "picked to the hold shelf" is confusing given the online reservation already happened.)
- Q (re-ask): till message format? A (repeated): store_id, till_id, sale_id (unique per till), lines (sku_id, quantity),
  sold_at.
- Candidate: **`sale_id` is the idempotency key**, UNIQUE on orders → till sales idempotent (duplicates possible).
  (Interviewer-private: `sale_id` is unique **per till** (stated twice) → two tills (or two stores) with the same sale_id
  would be dropped as duplicates → stock never decremented for real sales. Key must be `(store_id, till_id, sale_id)` —
  same miss as case 2's `(marketplace_id, order_id)`. Not raised — review.)
- Workflow sell (till message, one tx): `SELECT ... FOR UPDATE sku_stores WHERE store_id = ? AND sku_id IN (...) ORDER BY
  sku_id`; **unconditional** `available_quantity -= q` — **CHECK >= 0 removed, can go negative** (selling already-reserved
  items, edge case later); insert order + lines as **'completed'** (created_at/completed_at = now() or sold_at); commit.
  (+) till sale can't be refused → unconditional decrement allowed below zero while online reservations stay conditional —
  case 2's lesson applied unprompted. A duplicate hits the UNIQUE and rolls back the whole tx, decrement included — works.
- Workflow record delivery (one tx): `SELECT ... FOR UPDATE` the store's rows for the delivered SKUs ordered by sku_id;
  increment each; commit. (Interviewer-private: first delivery of a SKU to a store → no row → upsert needed (case 1
  lesson) — not said; "UPDATE quantity" — only `available_quantity` exists so far.)
- Q: how to tell a regular till sale from a click-and-collect sale in the message? (+) **spotted unprompted that
  collection is paid at the till → the same message stream** (double-decrement risk). A: at collection the cashier scans
  the reservation code; that sale message carries an extra **`reservation_id`** (our order id); regular sales have none.
- Candidate: sell tx branches — no reservation_id → flow as before (subtract from the SKU); with reservation_id "I think it's
  the same for the quantity in the reservation", both end `completed`. Ambiguous → interviewer asks what happens to
  `available_quantity` on the reservation branch.
- Answer: collection sale → **`quantity −= sold`, `available` unchanged**. Traced: 10 units (10,10) → reserve 2 → (10,8) →
  collect 2 → (8,8). (+) two counters (physical vs available) introduced and traced with numbers — no double decrement.
  (Interviewer-private: implies a regular sale decrements both counters — not restated; `sku_stores(quantity,
  available_quantity)` still not on the drawn tables.)
- Edge case (candidate-chosen, unprompted): 5 units, reserve 3 → (5,2); before pick a walk-in buys 4.
  (1) sale first → (1,−2); staff find 1 → cancel reservation → (1,1). (2) staff first → cancel → (5,5); sale → (1,1). "Same
  result, different intermediates"; compensation always at pickup → order `failed`.
  (+) **traced both interleavings with numbers, counters commute** — the negative counter absorbs the till sale and the
  cancel restores it; the cross-case lesson ("what happens to the counters on every transition") applied unprompted.
  Business choice not discussed: partial pick (1 of 3) vs cancel all. Still open: customer never collects (hold time
  never asked); sale_id idempotency key.
- Interviewer probe (Phase 3 scenario): customer reserves, staff pick to the hold shelf, customer never comes.
- Q: business no-show policy, how long? A: not discussed before; **48 h from the moment items are on the hold shelf**; then
  staff put the items back on the shelf and the reservation is released (customer notified — out of scope).
- Answer: **staff-driven, no worker** — staff call the API to release the order (and physically return the units):
  `available += reserved` for all lines, order → new status **`no_show`** + `no_show_at`. (+) proportionate: a physical
  action is needed anyway. Not stated: conditional on the expected state; how staff find orders past 48 h (query/index).
- Interviewer probe (timer race): staff release an order as no-show; a minute later that customer arrives and the
  cashier scans the reservation code — the sale message arrives with that reservation_id.
- Answer: "the system tells the cashier the reservation was marked no_show"; cashier checks with staff, a new sale without
  reservation is made → new sale_id flows to the API. (Interviewer-private: **inconsistent with the candidate's own
  architecture and the stated fact** — tills don't depend on us; they sell offline and the message arrives seconds later,
  so nothing can tell the cashier anything synchronously; the message with a no_show reservation_id still arrives.)
  Interviewer follow-up (genuine inconsistency): the till doesn't call us — what does the consumer do with that message?
- Answer: stays on the store's physical process — cashier has no access to our system; reservation box on the hold shelf /
  a log of no-show reservations and their lines / or the till queries our API; staff look up availability and ring a
  walk-in sale with a new sale_id. (Interviewer-private: **doesn't answer the consumer question** — the scenario's sale
  already happened with the reservation_id scanned; proposes the till querying our API, contradicting "tills never depend
  on us". Asked once more, narrowly.)
- Candidate pushes back: can't happen — physically the items are back on the shelf, so the reservation_id can't be used.
  Stakeholder fact given: the till scans whatever code the customer shows on their phone and **doesn't know the order's
  status**; customers do pick the same items from the shelf and show their code — it happens. (Last push on this.)
- Answer: if the sale has the same lines, handle like a reserved order → mark **completed**, "**without updating the
  quantities, because they were updated by the staff on the no-show**".
  (Interviewer-private: **counter error** — no_show restored `available` (+3) and the units are now sold, so the sale must
  decrement **both** `quantity` and `available` (treat as a regular sale): (10,10) → reserve 3 → (10,7) → no_show → (10,10)
  → sale → must be (7,7); as stated it stays (10,10) → 3 phantom units that the next online reservation can take. Also no
  conditional transition from `no_show` stated; partial/mismatched lines not covered. Not raised — review.)
- Candidate: if the sold items differ from the order lines → "a mechanism for stock compensation of mismatching lines"
  (not specified).
- Infra (candidate): single Postgres primary + **sync HA standby with failover**; read replicas / Redis only if throughput
  or latency demand it later; stateless **store stock API scaled horizontally behind a LB** with TLS termination; internal
  **mTLS**; **canary deployments**; monitoring: host resources (CPU/mem/disk) on API + DB, **DB locks and slowest
  transactions**, API/DB latency/throughput/errors, **business metrics: stock breaks and their duration, stock statistics
  for hot SKUs to drive replenishment**.
  (+) proportionate infra, deferred replicas/cache with the trigger named; lock contention monitored; business metric tied
  to the domain. Missing: **till-event consumer lag / DLQ** — the one async path whose delay makes availability wrong.)
- Failure: system down (DB, region network) → "since we want **99.99%**" → deploy the cell to **two regions** near the
  country, fail over between them; DB sync replica across the 2 regions.
  (Interviewer-private: stated SLA was **99.9%** — mis-recalled (pointed out lightly, once). At 99.9% (~8.7 h/yr) a
  multi-AZ standby in one region is enough; cross-region *synchronous* replication adds WAN latency to every commit and
  blocks writes if the other region is unreachable (unless degraded to async) — cost not weighed. Regions must stay in the
  jurisdiction — "close to the country" said.)
- Candidate acknowledges 99.9%; **two-region decision not revisited** against the corrected number.

## Phase 4 — Scaling

- **Opened unprompted** (local → regional → global): stores in new countries outside the region → **replicate the cell**
  (two nearby regions each), independent, user data stays in its region (GDPR). (+) Phase 4 self-started (2nd mock
  running); residency correct by default. Missing: a number and the next bottleneck inside one cell.
- Interviewer probe: within one country the chain grows 10x — 2,000 stores, till volume ×10. What breaks first?
- Answer: till writes ×10 → **~3k WPS** → near the limit of one Postgres primary → **shard**; key **sku_id** "because our
  queries are around it"; store_id or user_id would scatter the sku availability query across shards.
  (+) bottleneck identified with a number, the write side. (Interviewer-private: key chosen for the **read**, but the
  bottleneck is **writes**, and every write tx (reservation, till basket) locks several SKUs **of one store** → with sku_id
  sharding each becomes a cross-shard transaction. store_id (or geo-grouped stores) keeps every write single-shard; the
  read hits ≤10 nearby stores → 1–few shards if nearby stores are co-located. Cheaper steps before sharding not
  mentioned: batch till events per store, vertical scale.)
- Interviewer probe: a reservation of 3 SKUs at one store (or a till basket) with sku_id sharding — where do the rows live,
  and what does the transaction become?
- Revised after one probe: rows of one reservation would spread across shards → **shard by store_id**: every reservation
  and sale is single-shard; cost named — the availability view becomes up to **10 queries to 10 shards** (worst case).
  (+) fast, non-defensive revision with the cost stated. Not mentioned: co-locating nearby stores (geo-grouped shard key)
  to make the fan-out 1–2 shards; cheaper steps before sharding.

## Wrap-up
