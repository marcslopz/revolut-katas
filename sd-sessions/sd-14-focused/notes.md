# sd-14-focused — Multi-channel stock sync (stock series 2/5)

Interviewer's running transcription — not candidate-authored. Format: **lite mock** (see sd-13-focused):
F reqs → N → flow + blocks → states → ONE hard edge case. No security/deployment/monitoring boilerplate.
Coaching evidence only. Session target from case 1's feedback: order F → N → core flow first.

## Problem statement
A brand sells its products on its own web shop and on two external marketplaces (think Amazon-like and
eBay-like). Design the system that keeps stock correct across all sales channels.

(Interviewer-private: core = **one physical stock, several channels that sell it, two of which we don't
control**. Own web shop: we reserve synchronously (case 1). Marketplaces: they hold their own displayed
stock number, which we **push** via their API (rate-limited: ~10 requests/s per marketplace, batch up to
100 SKUs per request); they sell on their side and **notify us of orders via webhook, 0–2 min later** (can
be delayed/duplicated) — **a marketplace order is already sold, we can't reject it**, only cancel it
afterwards (penalised by the marketplace; cancel rate > 2% → seller account at risk). 1 warehouse.
~10k SKUs; ~30k orders/day total (40% web, 60% marketplaces); stock levels change on every order; restocks
as before. Out of scope: pricing, listings content, shipping, returns, marketplace onboarding.
Targets: source of truth = our DB; **oversell is a tolerance decision** (invariant can't be enforced
atomically across channels we don't control) → safety buffer / per-channel allocation for low-stock SKUs,
push updates prioritised for low stock; webhook orders as idempotent decrements that may go negative →
detect → cancel/backorder; push pipeline rate limit math (30k orders/day → stock changes/s vs 10 req/s ×
100 SKUs). Hard edge case if none chosen: last unit sold on the web shop and on a marketplace within the
sync delay.)

## Phase 1 — Requirements

- Q: actors? actions? (+) actions asked in the first question.
  A: actors — **web shop customers**, the **2 marketplaces** (external systems), **warehouse staff**.
  Actions, most common first: (1) web customers view products with availability; (2) **orders** — web
  checkout (reserve while paying, same as case 1) and **marketplace orders, which the marketplace notifies
  us about**; (3) we **keep each marketplace's displayed stock up to date via its API** (each marketplace
  shows its own stock number); (4) staff record deliveries (1 warehouse).
- Q: how do marketplaces talk to us — API calls? queues both ways? A: **HTTP only across the boundary**, no
  shared queue. Inbound: **webhook** to our endpoint per order, sent **0–2 min after the sale**, at-least-once
  (may be duplicated or late); the order is **already placed and paid on their side**. Outbound: their **REST
  API** to set the displayed stock, **~10 requests/s per marketplace, up to 100 SKUs per request**. Queues
  inside our system: candidate's choice.
- Candidate names the core: stock is effectively a distributed state across systems we don't control →
  **no strong consistency on availability** possible because of marketplace orders + eventually consistent
  displayed stock. (+) core identified unprompted within ~3 min, before any design. Not yet: what that means
  for the business (oversell tolerance) or how to bound it.
- Q: web checkout same as case 1? A: yes — reserve 15 min while paying at an external provider, then
  confirm/release; candidate may reuse case 1's design as-is.
- Candidate scopes out: web checkout not re-detailed (same as case 1); focus on the marketplace flows. (+)
  explicit scoping to the new part — proportionate.
- Q: when compensating a stock break, is there a priority between marketplace A, B and our web customers?
  (+) asks the business rule for oversell before designing it. A: **no preference between A and B**. Web
  orders are reserved synchronously against our DB, so they never oversell themselves. A marketplace order
  can't be rejected — it's already sold; cancelling it is **penalised: cancel rate above ~2% puts the seller
  account at risk**. Business prefers **avoiding oversell in the first place**; if it happens: **backorder**
  (ship late, customer told) when a delivery is expected within ~3 days, otherwise cancel.
- Q: can we keep a **stock buffer** — a % of each SKU not shown as available on the marketplaces? (+) safety
  buffer proposed unprompted — the target mitigation. A: yes, the business accepts it; the cost is units
  that don't sell on marketplaces (60% of our orders). Exact rule = candidate's design.
- Q (re-check): 10 req/s is for the stock update API? max SKUs per request? A: yes — outbound stock updates,
  ~10 req/s per marketplace, up to 100 SKUs per request.

## Phase 2 — Estimates

- (+) Moved to N right after F, in order (case 1 feedback applied). Numbers given: **~10k SKUs**; **~30k
  orders/day** — 40% web (~12k), 60% marketplaces (~9k each); ~500k web product views/day; ~200 deliveries/day;
  traffic mostly 8:00–22:00; no special sale days in this case.
- Q: no peaks or hot products? A: no sale events. A few **bestsellers sell a few hundred units/day**; at any
  time **~10% of SKUs are low stock (< 10 units)** — that's where oversell risk lives.
- Writes: 30k/day over 14 h (deliveries ignored, negligible) → **~0.6 req/s** → ×10 DB ops × 10 peak → **60 WPS
  → no sharding, one Postgres primary**. (+) correct, comparison sentence, peak factor applied.
- Reads: 500k/day over 14 h → "**~10k QPS**" → ×10 peak → "**~100k QPS, low, read replicas with eventual
  consistency**".
  (Interviewer-private: **magnitude slip ×1000** — 500k / 50,400 s ≈ **10 QPS** → ~100 QPS at peak. Not caught
  by a sanity check: "100k QPS" was called "low", which should have triggered one (100k QPS is not low for
  Postgres). The decision drawn from it (read replicas) is unnecessary at the real number — one primary is
  plenty. Same mechanical unit slip as the 2026-09-30 numeracy drill. Also not estimated: the number this
  prompt is about — **stock changes/s to push vs the marketplace limit** (10 req/s × 100 SKUs = 1,000 SKU
  updates/s per marketplace).)
- Self-corrected (unprompted, ~1 min later): 500k / 14 h → **10 QPS** → ×10 → **100 QPS**. (+) caught without a
  probe. Replica decision not yet revisited against the new number.
- **Format change (candidate):** challenge mistakes live, as they happen — don't hold them for the review.
- Live corrections given: (1) read replicas unnecessary at ~100 QPS; (2) marketplace push rate not sized.
- Push capacity: 10 req/s × 100 SKUs = **1,000 SKUs/s** per marketplace → all 10k SKUs in ~10 s. (+) right.
  Live note: capacity without demand — compare with stock changes/s (~0.6 avg, ~6 peak).

## Phase 3 — Flow, blocks, states

- Screenshot `01-high-level.png`: Marketplace A/B → **Stock API** (order); Stock API → A/B (update stock);
  staff (record delivery) and customer (view/checkout) → Stock API → DB; payment redirect/callback with the
  External Payment Provider; **expired payment worker** (check provider, check/expire in DB). Single
  service + single DB — proportionate (no replicas, per the corrected read number).
  Live challenge: "update stock" drawn as a direct call from the Stock API — what happens to a web checkout
  or a marketplace order when a marketplace's API is down / rate-limiting at that moment? (No push worker /
  queue / outbox between the DB change and the push.)
- Screenshot `02-high-level-outbox.png` (fix after the challenge): DB → **stock marketplace outbox publisher** →
  **stock update queue** → **stock marketplace consumer** → update stock on A and B. (+) outbox decouples the
  stock change from the push in one step. To watch when the consumer is described: one consumer/queue for
  both marketplaces (A down → B blocked?); message = absolute value or delta, and ordering.
- Screenshot `03-tables.png` (draft):
  - `orders(id, market_place_id NULL FK, market_place_order_id NULL, sku_id, quantity > 0, created_at,
    status IN (reserved, confirmed, failed, refunded, expired), reserved_at, confirmed_at, failed_at,
    refunded_at, expired_at)` — web + marketplace orders in one table (NULL marketplace = web).
  - `sku_stock(id, sku_id, quantity >= 0, available_quantity CHECK (>= 0 AND <= quantity), created_at)`.
  Live challenges: (1) `CHECK available_quantity >= 0` vs a marketplace order that can't be rejected when the
  stock is already 0 — what happens to the webhook? (2) one `sku_id` per order row vs webhooks with several
  lines; (3) the `(marketplace_id, order_id)` idempotency key isn't enforced anywhere in the table; (4) the
  status list is the web flow's — what states does a marketplace order go through (oversell outcomes)?
  (5) outbox publisher drawn, no outbox table. Buffer not represented yet.
- Answers: (1) **buffer = constant 10 units**: push `max(available - 10, 0)` to marketplaces (API logic);
  (2) new **`order_skus`** table (lines per order) — "didn't know an order could have several SKUs" (it was in
  the webhook answer); (3) **UNIQUE `orders(market_place_id, market_place_order_id)`** (+; NULLs for web orders
  don't collide in Postgres); (4) explicit statuses **`marketplace_confirmed`, `marketplace_oversold`** (was
  going to reuse `refunded`); (5) outbox table added.
  Live challenges: (1) not answered — the buffer lowers the odds, but the order that still arrives at 0 hits
  the CHECK → what does the webhook handler do? Also: why 10 for every SKU, when ~10% of SKUs have < 10 units
  (→ always 0 on marketplaces) and stock is sold at very different speeds? (4) `oversold` is a detection
  state — per the business rule what comes after it?
- Answer (1): webhook tries to reserve if stock is available → 200 OK; if oversold → **respond with an "out of
  stock" error so the marketplace refunds**. Buffer changed to **10% of quantity (rounded)**.
  Live challenges: (a) contradicts the stated rule — the order is already sold, can't be rejected; an error on
  an at-least-once webhook means the marketplace **retries**, not refunds; cancelling is our own (penalised)
  action, and the rule is backorder ≤ 3 days else cancel. (b) 10% of quantity puts the buffer where the risk
  isn't: < 10 units → 0–1 buffer; 1,000 units → 100 hidden. Risk = units sold during the sync window.
- Answers: (a) **respond 200 OK**, mark the stock break, **extend the delivery period** so staff ship when stock
  arrives (= backorder); duplicates handled by the UNIQUE `(market_place_id, market_place_order_id)`. (+)
  right direction; open: how the decrement coexists with `CHECK available >= 0`, and the cancel branch (no
  delivery within 3 days). (b) "both constraints: available always > 10, 10% for big stocks and hot sales".
  (Interviewer-private: 3rd attempt, still sized by stock level, not by sales speed × sync window; low-stock
  SKUs would still show 0 on marketplaces. Answer given — candidate stuck per the format rule.)
- Answers: **remove the `>= 0` CHECK**; **alert staff** on an oversell so they react fast and record the delivery;
  if 3 days isn't enough → "ask business: notify the marketplace of a delay with a new date, or refund via the
  marketplace".
  Live challenges: removing the CHECK — what still stops the **web** checkout from overselling? (a conditional
  `WHERE available >= q` would, but not said). The > 3 days branch was already answered by the stakeholder:
  **cancel** (marketplace refunds; counts toward the 2% rate) → a state and who triggers it are missing.
- Answer: new **cancellation worker**; state **`marketplace_canceled` added "to `sku_stock`"**.
  Live challenges: the state belongs to the **order**, not the stock row; what makes the worker pick an order
  (which fields/condition)?; challenge 1 (web oversell without the CHECK) still unanswered.
- Answers: state on **orders** (+). Worker picks orders with `marketplace_ordered_at` older than 3 days and still
  no stock to deliver. Web checkout keeps a **conditional update** (`WHERE available >= q`) once the CHECK is
  gone (+).
  Live challenge: the rule was "backorder **if a delivery is expected** within 3 days, otherwise cancel" — the
  worker waits 3 days even when nothing is coming; and the condition has no status filter (only oversold
  orders).
- Answer: **staff action to accept (backorder) / reject (cancel) the oversell** themselves — they know what
  deliveries are coming. (+) valid simplification: we don't track purchase orders, a human decides. Live
  challenge: what if staff never act? (status filter still not stated.)
- Answer: the **worker auto-cancels the oversold order after 3 days** if staff haven't acted. (+) human decision
  with a timer fallback. (Interviewer-private: staff accept vs worker cancel at the same moment = the timer race;
  not raised yet — left for the edge-case phase.) ~45 min elapsed.

- Workflow marketplace order — Q: one webhook = batch of orders or one? A: **one order per webhook**, with the
  marketplace's `order_id` and one or more lines (sku, quantity).
- Idempotency key = marketplace `order_id`. Live correction: ids are only unique **within** one marketplace →
  key must be `(marketplace_id, order_id)`.
- **Format refined (candidate):** live flags as a challenge pointing at the problem, not the answer.

- States — web orders: reserved → confirmed (paid in time, or paid late with stock still there, or the expiry
  worker finds it paid); reserved → failed (payment failed / cancelled); reserved → refunded (paid late, no
  stock); reserved → expired (no payment, no further action).
  Live challenge: a late payment arrives after the expiry worker has already run — the order is `expired`, not
  `reserved`; late confirm/refund transitions start from `expired` (as in case 1's own design).
- Fixed: **reserved → expired → confirmed** and **reserved → expired → refunded**. (+) (If the callback beats the
  worker the stock is still held → reserved → confirmed directly; reserved → refunded can't happen.)

- States — marketplace orders: created → confirmed (stock available); created → oversold → oversold_accepted →
  confirmed (staff accept, add stock, confirm); created → oversold → canceled (staff reject); created → oversold
  → oversold_accepted → canceled (staff cancel later, or the worker after 3 days).
  (+) states grown with the flow; states and table now match (statuses on orders). Live challenge: the "staff
  never act" path — worker from `oversold` (not `accepted`) — isn't on the list. Minor: `created` is transient if
  the webhook decides confirmed/oversold in the same tx. Not raised: delivery → backorders vs web, who gets the
  units first.
- Fixed: created → oversold → canceled (by the worker, staff never answered). (+)

- Q: how do we notify the marketplace of a cancellation (outside the webhook)? A: their REST API has a **cancel
  endpoint by their order_id** (POST .../orders/{order_id}/cancel); the marketplace refunds the customer.
  Separate limit from stock updates, plenty of capacity. Can fail/time out like any external call.

## Edge case

- Candidate asks for one. Given: **3 days after an oversold order, 10:00:00 — the worker picks it to auto-cancel
  and calls the marketplace's cancel endpoint. 10:00:01 — the delivery arrives, staff record it and click
  "accept" on that same order.** (Targets: conditional transitions on the expected state; durable `canceling`
  state before the external call; cancel call timeout; units from the delivery and who gets them.)
- Candidate: in the current flow staff can accept an order that's already canceled. (+) bug identified.
- Fix: DB refuses the transition canceled → oversold_accepted (conditional transition). Asks whether to allow a
  best-effort "undo" of the marketplace cancellation. A (stakeholder): **a cancellation can't be undone** on the
  marketplace. Live challenge (repeated): the in-flight moment — if the worker writes `canceled` only after the
  call returns, the DB still says `oversold` at 10:00:01.
- Answer: "not a bug — I'd treat it atomically": **outbox** — worker sets `canceled` + inserts a cancellation outbox
  message in one tx; a queue consumer calls the marketplace cancel endpoint. → staff's accept at 10:00:01 hits
  `canceled` and is refused by the conditional transition. (+) correct: durable state before the external call,
  reusing the outbox already in the design. (Fair point: the order of operations hadn't been stated, the
  challenge assumed call-then-write.)
  Remaining part of the question: the delivery's units and the oversold order's negative stock.
- Self-admitted miss: the cancellation tx must also **release the stock** (`available += q`). Fixed. Part 2 (who
  gets the delivery's units first) not answered yet — re-pointed with a concrete number.
- Q: total units in oversold_accepted? A: 3 (e.g. 2 + 1), hence available = -3.
- Answer: delivery +10 → **available = 7**; in the **same tx** the system auto-confirms the waiting
  `oversold_accepted` orders (3 units) → `marketplace_confirmed`; the 7 are free for the web, and for the
  marketplaces subject to the buffer. (+) correct: the negative counter already protects the backordered units —
  the web can only sell what's above 0; auto-confirm atomic with the delivery. Not covered (fine): partial
  delivery smaller than the backlog → which order first (FIFO by marketplace_ordered_at).

## Feedback

Closed after the edge case (~60 min; target was ~25). Lite-mock feedback (coaching evidence only):

**Strong**
- Core named in ~3 min, before any design: no strong consistency across channels we don't control. Then asked for
  the oversell business rule and proposed a buffer unprompted.
- Case 1 fix applied: F → N → flows in order; web checkout explicitly scoped out as "same as case 1".
- Outbox for marketplace pushes after one challenge; **reused unprompted for cancellations** in the edge case
  (durable `canceled` + outbox message in one tx → staff accept refused by the conditional transition).
- Negative counter + atomic auto-confirm of backorders on delivery — the backordered units are protected by design.
- Complete state machines for both order types, kept on `orders`.

**To improve**
1. **Estimates sanity**: reads ×1000 (10k QPS instead of 10) → "100k QPS is low" → read replicas. Self-corrected
   the number, but the replica decision needed a challenge. The prompt's key number (push demand vs capacity) only
   after a challenge.
2. **Buffer sized by stock level, three attempts** — risk = sales velocity × sync window. Concept gap, taught.
3. **Stakeholder facts not applied**: "reply with an error so the marketplace refunds" (stated: already sold,
   can't reject; at-least-once → retries); "ask business" about a rule already given (cancel after 3 days).
4. Table ↔ flow drift came back in a new domain, each fixed on one challenge: CHECK vs an order that can't be
   rejected, multi-line webhook, idempotency key not on the table, state on `sku_stock`, stock release on cancel.
