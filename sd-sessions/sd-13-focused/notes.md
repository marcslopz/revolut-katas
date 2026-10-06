# sd-13-focused — Online store inventory (stock series 1/5)

Interviewer's running transcription — not candidate-authored. Format: **lite mock** (set by the
candidate 2026-10-06): full flow, candidate leads, but scope limited to F reqs → N estimates →
flow + blocks → states → ONE hard edge case. Security/deployment/monitoring boilerplate NOT expected.
Completeness not the goal. Short feedback at the end; coaching evidence only (not a mock).

## Problem statement
Design the inventory (stock) system for an online retailer that sells physical products shipped
from its own warehouses.

(Interviewer-private: core = **fungible quantity per SKU per warehouse**; checkout reserves units
while the customer pays (~15 min), then the reservation is committed (order placed) or released.
No overselling under concurrency. Restocks arrive from suppliers (warehouse staff increments stock).
3 warehouses (one country); ~50k SKUs; ~20k orders/day normal, sale days 10x with a few hot SKUs.
Payment = external, success/fail callback, out of scope beyond that. Out of scope: shipping/routing
optimisation, returns, pricing, catalogue management. Contrast with sd-12: counter vs per-unit rows.
Targets: most common action asked (product page "in stock?" reads ≫ reservations); conditional
decrement `WHERE available >= qty`; states of a reservation; hard edge case candidate's choice — if
none chosen, push: hot SKU on a sale day (row contention) OR multi-SKU cart partially available.)

## Phase 1 — Requirements

- Q: actors — customer; are there also retailers? A: no — **one retailer (us)**, not a marketplace.
  Actors: **customers** (buy on the website) and **warehouse staff** (record incoming stock).
- Q: what are the common actions? (+) dominant-action question asked second, unprompted.
  A, most common first: (1) customers **view a product page with its availability** ("in stock" /
  "only 3 left") — by far the most common; (2) **checkout**: units in the cart are **reserved for 15 min**
  while the customer pays (external provider, success/fail callback) → order placed, or released;
  (3) staff **record a delivery** (+N units of a SKU at a warehouse).
- Q: different warehouses? total per SKU or per warehouse? A: **3 warehouses, one country**. Stock must be
  tracked **per warehouse** (deliveries land at one warehouse; pickers ship from one). Customer sees
  only the **total** across warehouses. On reservation any warehouse with enough units is fine; items
  of one cart may ship from different warehouses; no routing optimisation needed.

## Phase 2 — Estimates

- (Late, self-initiated — candidate came back to it during the edge-case phase, before answering the hot-SKU
  push.) Q: what reads/writes do we have to cover? A: **~50k SKUs**; normal day **~2M product page views**
  (availability reads), **~25k checkouts** (→ ~20k confirmed orders), **~500 delivery records**; traffic
  mostly in daytime hours. **Sale days: 10x everything**, concentrated in the first hour, with a few hot
  SKUs (e.g. the 200 checkouts/s one).
- Candidate: 500 deliveries/day vs 25k checkouts → negligible, ignored. (+) explicit comparison sentence.
- Normal day: writes 25k checkouts → ~1k/h → **0.3 WPS**; reads 2M views → ~84k/h → **23 QPS** (24 h average,
  no daytime peak factor).
- Sale day writes: 250k checkouts in the first hour → **69.4 checkouts/s** × <10 writes each → **~700 write
  ops/s → no sharding**.
- Hot SKU: 200 checkouts/s × ~5 ms per checkout tx → **ρ = 1 (100%)** → saturated; idea: a **write cache** for
  hot SKUs to bring the per-checkout time under 1 ms (0.5 ms → ρ = 0.1).
  (Interviewer-private: (+) arithmetic right; (+) ρ = λ × S applied unprompted to the hot row — sd-12's
  model carried over; (+) "no sharding" decided from the number. Gaps: **sale-day reads never computed** —
  20M views mostly in the first hour ≈ 5–6k QPS on the same primary, the read-heavy side of a read-heavy
  prompt (LOW estimate item: "size reads first"); the 3 warehouse rows split the hot SKU's load (~0.33 each
  if SKIP LOCKED spreads it) — not noticed; "write cache" not yet defined — what's the source of truth?)

- (Interviewer-private) **skipped so far** — went from F reqs straight to the diagram; no NFRs asked
  (volumes, read/write ratio, sale-day peaks, freshness of "in stock"). Candidate's own plan was F → N →
  diagram. Not redirected (candidate leads).

## Phase 3 — Flow, blocks, states

- Screenshot `01-high-level.png`: Customer/Staff → Auth Service (creds → JWT); → **Retail Service API** → DB;
  API redirects the customer to the **External Payment Provider** (payment URL); provider → API callback
  (confirmed/failed). Skeleton-level, single service + single DB — proportionate. Not yet visible: where
  stock lives (per warehouse), reservation entity, expiry mechanism, the read path for availability.
- Flow 1 — Authentication: login with creds → JWT → JWT on API calls. (Interviewer-private: first flow
  walked is the generic one the candidate said to skip; the core flows — availability read, reserve at
  checkout — not yet.)
- Flow 2 — record_delivery (staff): API(sku, qty, warehouse) → validate → save in DB ("transactions and
  tables later") → sync response. (Interviewer-private: second-least-frequent action designed before
  the dominant one; the write is an increment — how it combines with concurrent reservations deferred.)
- Flow 3 — view product(s) (customer): API → DB → return product data. (Interviewer-private: the
  dominant action, walked as a plain read; availability = total across 3 warehouses minus reservations
  not mentioned; no read volume known since estimates skipped — whether one DB suffices is open.)
- Flow 4 — checkout (customer): (1) checkout qty of SKU X → (2) API **reserves the stock or fails if not
  enough**, stores a timestamp (for the 15 min) → (3) generates `reservation_id`, redirects to the payment
  provider with a callback_url (reservation_id + payment expiry timestamp) → (4) customer pays at the
  provider → (5) provider callback (payment_id, reservation_id, result) → (6) customer redirected to our
  checkout-completed page.
  (Interviewer-private: (+) reserve-before-redirect order right, durable reservation before the external
  step; expiry passed to the provider. Open: one SKU only — multi-SKU cart not addressed; which warehouse
  the units come from; how "reserve or fail" is made atomic; who releases at 15 min; callback arriving
  after expiry; reservation_id created after the reserve rather than with it.)
- New block — **Checkout releaser** (worker): (1) picks reservations expired (>15 min) without a provider
  confirmation → (2) **asks the provider synchronously** for the payment status → (3) paid → complete
  the reservation; failed **or pending** → free the reserved SKU units and update the reservation.
  (Interviewer-private: (+) reconciles with the provider before releasing — doesn't trust the timer
  alone; unprompted. Open: "pending → release" then the payment succeeds later (late success on
  released stock); callback and releaser acting on the same reservation at the same moment — no
  conditional transition stated yet. Both = the sd-12 timer-race item.)

- Q (moving to tables): can the customer cancel the checkout? A: no cancel feature of our own. If they
  cancel on the provider's page the provider calls back with **failed**; if they just close the tab the
  reservation **expires** after 15 min.

- Screenshot `02-draft-tables.png` (draft, "without idempotency keys"):
  - `warehouses(id, created_at)`; `skus(id, title, description, created_at)`
  - `sku_stocks(id, sku_id FK, warehouse_id FK, quantity CHECK >= 0, available_quantity CHECK >= 0)`
  - `reservations(id, sku_id FK, quantity CHECK > 0, status IN (reserved, failed, confirmed, expired),
    customer_id FK, reserved_at, failed_at, confirmed_at, expired_at)`
  - `audit_actions(id, actioned_by NULL=system, action_type IN (record_delivery, checkout,
    checkout_confirmed, checkout_failed, checkout_expired), created_at, metadata JSONB)`
  (Interviewer-private: (+) stock per (sku, warehouse) with total vs available split and `CHECK
  available_quantity >= 0` — the DB itself refuses overselling. (+) status list matches the flows.
  Gaps vs own flow: **`reservations` has no `warehouse_id`** → release/confirm can't know which
  `sku_stocks` row to touch (same shape as sd-12's `booking_seats` without `screening_id`); no
  `payment_id` though the callback brings one; no `UNIQUE(sku_id, warehouse_id)`; one SKU per
  reservation (multi-SKU cart still unaddressed). Atomic statement for reserve not yet said.)

- Candidate: columns/statuses will be added as each workflow is walked.
- Workflow record_delivery (tx): `UPDATE sku_stocks SET quantity += :q, available_quantity += :q WHERE
  sku_id = :sku AND warehouse_id = :wh` — "the update locks the row, so it's atomic". Index
  `(sku_id, warehouse_id)`.
  (Interviewer-private: (+) in-place relative increment, lock stated while designing, index derived from
  the WHERE. Minor: index should be UNIQUE (one stock row per pair); first delivery of a SKU to a
  warehouse → 0 rows updated → needs an upsert / row created with the SKU.)

- Self-revised (unprompted): record_delivery → **upsert** `INSERT INTO sku_stocks (...) VALUES (...) ON
  CONFLICT DO UPDATE (same increment)`; `(sku_id, warehouse_id)` made **UNIQUE**. (+) both minor gaps
  above self-caught within a minute.

- Workflow checkout (one tx):
  `SELECT warehouse_id FROM sku_stocks WHERE sku_id = :sku AND available_quantity >= :q FOR UPDATE SKIP
  LOCKED` → `UPDATE sku_stocks SET available_quantity -= :q WHERE sku_id AND warehouse_id` → `INSERT
  reservations (status 'reserved', reserved_at now(), **warehouse_id** — new column)` → `INSERT
  audit_actions (actioned_by = user from JWT, 'checkout', metadata {warehouse_id})`.
  (Interviewer-private: (+) `warehouse_id` added to reservations — the main table gap self-caught while
  walking the flow; reservation + audit in the same tx; condition `available >= q` under a row lock.
  Open: no `LIMIT 1` → locks every matching warehouse row, not one; **SKIP LOCKED + only 3 rows per SKU**
  → when 3 concurrent checkouts hold the 3 rows, the 4th sees 0 rows and gets "out of stock" although
  stock exists (false negative under contention — hot SKU on sale day). A plain wait (no SKIP LOCKED) or
  a single conditional UPDATE would avoid it.)

- Self-revised (unprompted): `LIMIT 1` added to the SELECT ... FOR UPDATE SKIP LOCKED.

- Workflow view stock (customer): `SELECT SUM(available_quantity) FROM sku_stocks WHERE sku_id = :sku`.
  (Interviewer-private: correct — total across warehouses, net of reservations; served by the UNIQUE
  `(sku_id, warehouse_id)` index's prefix (not said). Plain reads don't block on the checkout row locks in
  Postgres. Whether one primary handles the read volume is unknowable — still no estimates.)

- Workflow provider callback (confirmed/failed): `UPDATE reservations SET status = :result,
  confirmed_at|failed_at = now() WHERE id = :id AND status = 'reserved'`. 0 rows → either a duplicate
  (already confirmed/failed) or already expired: expired + failed → overwrite to failed + audit; **expired +
  confirmed → re-check availability, reserve the quantity from the same or another warehouse, overwrite to
  confirmed + audit**.
  (Interviewer-private: (+) **timer race handled unprompted**: conditional transition on the expected state,
  0-rows branch interpreted, late success compensated by re-reserving — the sd-12 MEDIUM item, here with no
  probe. Open: the **failed** branch doesn't return the units (`available_quantity += q`) — as written, a
  failed payment leaks stock until... never (the releaser only picks `reserved`); late-confirmed with **no
  stock left** → refund not said; `payment_id` still not stored; `quantity` (physical) never decremented
  on confirm — fine if that happens at shipping, not said.)

- Self-caught (unprompted): every transition out of `reserved` must also touch `sku_stocks` — failed/expired
  → release (`available_quantity += q`), confirmed → decrement (`quantity -= q`). (+) closes the stock leak
  above. Exact statements / same-tx not spelled out.

- Releaser/expired path left as "the easy one"; moved on to edge cases. (Interviewer-private: estimates
  phase never done — candidate's own planned N step skipped entirely.)

## Edge case

- Candidate's pick: customer closes the provider page without paying → releaser marks the reservation
  expired after 15 min and releases the stock. (Interviewer-private: correct, but it's the happy-path
  expiry already designed — not a hard case. Pushed the hard one per the lite-mock format.)
- Interviewer pushes: **sale day — one hot SKU, 5,000 units spread across the 3 warehouses, ~200
  checkouts/s for that SKU in the first minutes.** What happens with this design?
- Candidate first adds another case (own pick): **provider lets the user pay 20 min after checkout** (past
  expiry) → callback finds `expired` → re-reserve if stock is available → `confirmed`; if not → new status
  **`refunded`** + **synchronous refund call** to the provider.
  (Interviewer-private: (+) late-success compensation completed with the no-stock branch and a new state —
  state list grown with the flow. Open, not probed (out of the lite scope): sync refund call that times
  out / fails → needs a durable `refund_pending` (or `refunding`) state set before the call and a retry
  by the releaser, with an idempotent refund key; otherwise `refunded` may be written for a refund that
  never happened, or the refund may be lost.)

## Feedback

Ended by the candidate during the hot-SKU edge case (~35 min). Lite-mock feedback (coaching evidence only):

**Strong**
- Dominant action asked in the 2nd question; warehouse granularity clarified before designing.
- **Timer race handled unprompted** (sd-12 MEDIUM item): `WHERE status = 'reserved'`, 0-rows branch
  interpreted (duplicate vs expired), late success → re-reserve or `refunded`. No probe needed.
- Flow ↔ table kept in sync by walking each flow: `warehouse_id` on reservations, upsert, UNIQUE, LIMIT 1,
  stock release on every transition out of `reserved` — all self-caught. States grew with the flows.
- ρ = λ × S applied to the hot row unprompted; "no sharding" decided from the number.

**To improve**
1. **Order**: N skipped and done only after the edge cases; flows started with auth (the boilerplate the
   candidate chose to skip) and record_delivery before checkout. Target: F → N → core flow first.
2. **Sale-day reads not sized**: 20M views mostly in the first hour ≈ 5–6k QPS — bigger than the 700
   write ops/s. Display can be slightly stale (replica / short-TTL cache); correctness is enforced at
   checkout by the conditional decrement.
3. **Hot SKU unfinished** — model answer given (shorter lock hold via a single conditional UPDATE; stock
   buckets; Redis gatekeeper with reconciliation as the heavier option). SKIP LOCKED with 3 rows → false
   "out of stock" when all 3 are locked.
- Low (out of lite scope): sync refund call without a durable `refunding` state.
