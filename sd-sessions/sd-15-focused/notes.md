# sd-15-focused — Perishable stock for online grocery (stock series 3/5, last before the full mock)

Interviewer's running transcription — not candidate-authored. Format: **lite mock** (see sd-13-focused):
F reqs → N → flow + blocks → states → ONE hard edge case. No security/deployment/monitoring boilerplate.
Coaching evidence only. Live challenges as mistakes appear (point at the problem, answer only if stuck).
Targets from cases 1–2: compare every number before deciding; re-read stakeholder facts before decisions that
depend on them; walk each flow against the tables before presenting them.

## Problem statement
Design the stock system for an online grocery that delivers from its own store, where many products are
perishable and have an expiry date.

(Interviewer-private: core = **stock as lots (sku, expiry date, quantity), not a counter**; sellability
depends on the **delivery date**: a unit can be sold for a delivery only if it still has **≥ 2 days of shelf
life on delivery day** (perishables). Customer picks a **delivery slot from today up to 3 days ahead**; order
paid at checkout with a saved card (synchronous, out of scope — **no hold timer** this time); stock reserved
when the order is placed; picked by staff on the delivery day. **FEFO** (first-expiry-first-out) — serve the
lot expiring soonest that is still valid for that date — to minimise waste. 1 store (dark store), 1 city.
~5k SKUs (~30% perishable); ~8k orders/day × ~25 lines = ~200k lines/day; evening peak; ~1–5 active lots per
perishable SKU. Staff: record deliveries (new lots), write off expired/damaged units, pick orders.
Out of scope: pricing/discounts on near-expiry, delivery routing, substitutions UI, payments.
Targets: availability is **per delivery date** (same SKU can be available Mon and not Thu) → the dominant
read changes shape; lot table + conditional decrement per lot; allocation across several lots for one line
(FEFO, deterministic lock order); states of an order line / allocation. Hard edge case if none chosen:
**at pick time the allocated lot is short/damaged** (staff find 3 of 5 units) → reallocate from another lot
valid for that delivery, else partial + refund — and a later order may already hold the next lot.)

## Phase 1 — Requirements

- Q: actors and actions? A: actors — **customers**, **store staff**. Actions, most common first:
  (1) customers **choose a delivery slot (today up to 3 days ahead) and browse products with availability**;
  (2) customers **place an order** for that slot — paid at checkout with a saved card (synchronous, out of scope,
  no payment hold this time); (3) staff **pick orders** on the delivery day; (4) staff **record supplier
  deliveries** — each delivery of a SKU comes with an **expiry date**; (5) staff **write off** expired or damaged
  units.
- Q: stock reserved when choosing the slot or when placing the order? A: **when the order is placed**. Choosing a
  slot reserves nothing (slot capacity itself out of scope); browsing only shows availability.
- Q: slot delivery capacity out of scope? A: yes; product availability *for the chosen slot* is in scope.
- Candidate: "actors/actions clear, let's go for N". Live challenge: nothing asked yet about the expiry date —
  the word in the prompt — and what it means for selling (rule not revealed).

## Phase 2 — Estimates

- Numbers given: ~5k SKUs (~30% perishable, 1–5 active lots each); ~8k orders/day × ~25 lines (~200k lines/day);
  ~400k product-list/page views/day; ~150 supplier delivery lines/day; ~300 write-off records/day; traffic
  7:00–23:00 with an evening peak (~3x average).
- Writes: 200k lines / 16 h → 12.5k/h → **3.47 WPS**; peak ×3 → "112.5k/h" → **10.41 WPS → single Postgres, no
  sharding**. (Intermediate 112.5k/h inconsistent with 10.41/s — 37.5k/h is right; final number right.)
- Reads: 400k / 16 h → 25k/h → **6.94 QPS**; peak 75k/h → **20.83 QPS** → "**a read replica is enough**, 2 for
  availability, or fall back to the primary". Staff traffic ignored (comparison stated).
  Live challenge: 21 QPS doesn't need a read replica at all — same reflex as case 2 (replicas without a number
  that needs them).
- Answer: replica is **for availability, not throughput** — one DB does 1k–10k QPS. (+) fair, and the capacity
  anchor is right. Follow-up challenge: if the primary is down, what can customers still do with a read replica
  (browse yes, order no) → HA = standby + failover, not read routing.
- Answer: **synchronously replicated standby** for availability of writes; read replicas only when read traffic
  needs them. (+) right. Expiry question (flagged earlier) still not asked.
- Q: how does the saved-card payment work? A: black box — an internal **Payments service, called synchronously**
  with the customer's saved card token and the amount; answers **paid / declined in ~1 s** (rarely times out). No
  redirect, no callback, no hold timer. Order of steps vs the stock reservation = candidate's design.
- Candidate: place order → call Payments with customer_id + order_id; may time out → **must be able to retry**.
  (Stakeholder fact given so retries are safe: Payments **deduplicates by order_id**.) Light scope — not probed.

## Phase 3 — Flow, blocks, states

- Screenshot `01-high-level.png`: customers (view/order) and staff (pick-up order, record supplier delivery, write
  off expired/damaged) → **groceries stock API service** → DB; **payment publisher (outbox)** → order payments
  queue → **order payment consumer** ↔ Internal Payment Provider, writing back to DB; **Expiration worker ("missed
  expired stocks")** → DB.
  Live challenges: (1) payment made **async** (outbox + queue + consumer) although Payments answers synchronously
  in ~1 s — what does the queue buy, and what does the customer see at checkout meanwhile? (2) expiry handled only
  as "remove expired stock" by a worker — a customer orders yogurt for **Thursday** and the only lot expires
  **Wednesday**: does anything stop that sale? (the sellability rule still not asked).
- Answers: (1) async payment = decoupling, retries without losing the flow, at-least-once consistency; order gets
  an intermediate "processing payment" status, customer sees it via polling/websocket. (Defensible; heavier than
  needed for a 1 s sync call — trade-off noted, not pushed.) (2) **`expired_at` per batch**; ordering **filters out
  batches expiring before the delivery date**; the expiry worker only cleans up. (+) per-delivery-date sellability
  found. Live challenge: a batch expiring **on** delivery day passes the filter — would a customer accept it?
  (shelf-life margin still not asked.)
- Candidate: business must define the margin (e.g. sell only batches expiring after the delivery day). A: **a batch
  is sellable for a delivery only if it has ≥ 2 days of shelf life on delivery day** (`expires_at >= delivery_date
  + 2 days`), same rule for all perishables. (+) turned it into a stakeholder question.
- Screenshot `02-tables.png` (draft; constraints/indexes to come):
  - `skus(id, price > 0, name, description)`
  - `sku_batches(id, sku_id, quantity >= 0, available_quantity CHECK (>= 0 AND <= quantity), expired_at NULL — only
    perishables)` (+) stock as batches with their own counter.
  - `orders(id, customer_id, created_at, status IN (created, paying, completed, failed), paying_at, completed_at,
    failed_at)`
  - `order_lines(id, order_id, batch_id, quantity > 0, price > 0)` (+) line points at a batch → FEFO allocation
    recorded.
  - `outbox(id, order_id, total_price_with_tax, customer_id, status IN (created, sent), created_at)`
  Live challenge: **`orders` has no delivery date / slot** — the field the sellability rule and picking depend on.
- Answer: add `delivered_at` to orders. Live challenge (semantics): `delivered_at` reads as "when it was delivered"
  (unknown at order time) vs the **chosen slot** (known at order time) — which one does the rule need?
- Fixed: **`orders.delivery_at`** — an input of the order transaction (the chosen slot), used for the availability
  check. (+)
- States/transitions — orders: no stock for some line → fail, no order created, ask the customer to remove those
  SKUs; all lines in stock → order `created` + outbox `created` (same tx) → publisher sends, on queue ack → order
  `paying` (only from `created`) + outbox `sent` → consumer: provider accepts → `completed`; declines → `failed`;
  timeout → redeliver idempotently by order_id until success/fail.
  (+) conditional transition `paying` only from `created` (consumer may finish first); idempotent retry key.
  Live challenge: **`failed` doesn't give the batch units back** — the stock reserved at `created` stays taken
  (same miss as case 2's cancellation). Not yet: states after `completed` (picking/delivery).
- Fixed: on `failed`, give back `available_quantity` of every order line's batch (same tx as the status change
  implied). (+)
- Customer order tx: per SKU, `SELECT ... FOR UPDATE SKIP LOCKED` on `sku_batches` `WHERE sku_id = ? AND
  available_quantity > 0 AND expired_at > :delivery_at + 2 days ORDER BY expired_at` (FEFO), locking batches until the
  quantity is covered; N retries then without SKIP LOCKED; decrement `available_quantity` per batch by PK; insert
  order + order_lines + outbox; UNIQUE `order_lines(order_id, batch_id)`, UNIQUE `outbox(order_id)`. Index
  `sku_batches(sku_id, available_quantity, expired_at)`.
  (+) FEFO + delivery-date rule in the WHERE, multi-batch per line, retry → blocking fallback carried from case 1,
  one tx with the outbox. Live challenges: (1) `expired_at` is NULL for non-perishables → `NULL > date` is not true →
  **non-perishables never sellable**; (2) several SKUs locked in one tx — in the blocking fallback, two orders
  locking A then B and B then A → **deadlock** (lock order). Minor, not raised (spoken-design calibration): index
  with two range columns — `(sku_id, expired_at)` serves the ORDER BY; with 1–5 batches per SKU `sku_id` alone is
  enough.
- Fixed, both on the first challenge: (1) `(expired_at IS NULL OR expired_at > :delivery_at + 2 days)`; (2) **acquire
  locks ordered by sku_id** → same order everywhere → no deadlock. (+)
- Staff pick-up flow: per order line, lock batches (ordered by sku_id) `FOR UPDATE`, decrement **both `quantity` and
  `available_quantity`** by the line's amount.
  Live challenge: `available_quantity` was already decremented when the order was placed → decrementing it again at
  pick counts the order twice. (Order state for picking not mentioned yet.)
- Fixed by tracing the numbers: placed → (10, 5); picked → (5, 5); **pick decrements only `quantity`**. (+)
- State: `completed → delivered` at pick time (conditional from `completed`). Minor naming: at pick time it's
  `picked` (delivery out of scope) — told directly, low severity.

## Edge case

- Candidate asks for a hard one. Given: **batch A** (yogurt, expires in 3 days): `quantity 10, available 0` — reserved
  by order X (5, delivery **today**) and order Y (5, delivery **tomorrow**). **Batch B** (expires in 8 days):
  `quantity 6, available 4`. Picking order X today, staff find only **8 units of A on the shelf — 2 damaged**.
  (Targets: write-off makes A's physical < reserved → the shortfall belongs to someone; reallocate X (or Y) to B if
  B is valid for that date and available; Y's delivery tomorrow + 2 = 3 days → A is still valid for Y; counters
  stay consistent (quantity −2, a reservation moves A→B: A available +k, B available −k, order_lines updated);
  if B isn't enough → partial + refund via Payments; decide who gets shorted (FEFO / earliest delivery first).)
- Answer: staff mark 2 of A as damaged; if A's `available >= 2` → just `quantity −2, available −2`. Here available = 0 →
  look for other batches (by expired_at) with `available >= 2` → B `available −= 2`, and **move 2 units of the order
  with the latest `delivery_at` (Y) from A to B**. Result: **A (8, 0), B (6, 2); X 5 from A; Y 3 from A + 2 from B**.
  (+) counters right — A's 8 physical = X 5 + Y 3; the shortfall is moved off the order being picked now onto the one
  with the most slack. Live challenges: (1) B must also pass Y's sellability rule (`expires >= Y.delivery_at + 2`) —
  not stated; (2) no batch can compensate → ?
- Answers: (1) "the check is `available >= 2`" — sellability for Y's date still missing → re-pointed with a concrete
  case (B expiring tomorrow). (2) **reduce Y's line by 2 and refund the 2 yogurts** (+) partial + refund.

## Feedback
- Fixed on the 2nd pointer: compensation batch must pass `available >= k` **and** `expired_at >= Y.delivery_at + 2 days`.

Closed after the edge case. Lite-mock feedback (coaching evidence only):

**Strong**
- F → N → flows kept in order; estimates right (one intermediate typo), capacity anchor 1k–10k QPS stated; replica
  question → hot standby with sync replication.
- Core modelled right: stock as batches with their own counter, FEFO, the per-delivery-date rule in the WHERE, a line
  split across batches, `order_lines.batch_id`.
- Conditional transitions habitual (`paying` only from `created`, picking only from `completed`); lock order by
  sku_id on the first challenge; retry → blocking fallback carried over from case 1.
- Edge case: counters right (A 8/0, B 6/2), shortfall moved to the order with the most slack, partial + refund.
- Caught the double decrement by tracing numbers.

**To improve**
1. **The prompt's key word asked late**: expiry rule only after two pointers (`expires >= delivery + 2`).
2. **Invariants/counters dropped on secondary paths** — stock release on `failed` (same miss as case 2's cancel),
   double decrement at pick, sellability forgotten on reallocation, NULL expiry for non-perishables. The main path
   was right each time; the other paths that touch stock weren't walked against the same rules.
3. Fields the flow depends on: `delivery_at` missing from orders (fixed on one challenge).
4. Simplicity: async payment for a 1 s sync call (defended with a trade-off); replica reflex again at 21 QPS.
