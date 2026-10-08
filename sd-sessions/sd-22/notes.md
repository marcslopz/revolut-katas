# sd-22 — Online shop stock (interviewer notes)

Prompt: Design the stock service for an online shop. Customers buy products (checkout/payment is
handled outside our service), and staff add stock.

## Phase 1 — Requirements
- Candidate opened by asking the interviewer to list actors and actions (instead of proposing them).
  Answered with the prompt's two actors/actions only, and handed the follow-up back.

- Candidate's customer flow: check availability → add to cart → checkout → payment (payment next step).
- Q: prices in our service? A: no — catalog/pricing is another service; we own stock quantities per product.
- Q: multiple warehouses? A: no — single warehouse, one stock count per product.
- Q: users from same country? A: yes — single country for now.
- Q: how long is stock held between checkout and payment? A: hold starts at checkout, lasts 15 min;
  no payment confirmation by then → released. Adding to cart does NOT hold stock.
- Q: how do we talk to the payment provider (our API vs redirect)? A: we don't — the checkout service
  (external) owns cart, payment and the provider. It tells us when checkout starts and later whether
  payment succeeded or failed; integration mechanism is the candidate's call.
- Candidate restated as "our service talks to checkout to check out, checkout calls back with result" —
  direction corrected: checkout service calls US when checkout starts; then reports the payment outcome.
- Q: can checkout → us be async via a queue? A: design call is theirs; business constraint given:
  customer must not be sent to pay unless the hold succeeded (checkout needs that answer before payment).
- Candidate's flow: checkout start → we hold units and answer "accepted" (sync, implied) → user pays via
  checkout service → checkout calls back us with success/failure. (Said "we tell the user" — the caller is
  the checkout service; not corrected.)
- NFRs asked (reads/writes at peak, latency, availability). Given: ~100k products; peak availability
  reads ~5,000/s; peak checkout holds ~200/s; staff stock additions a few hundred/day; latency p99 reads
  < 100 ms, holds < 300 ms; availability 99.95%. Consistency NOT asked (yet).
- Screenshot 01-reqs.png (was dropped in ~/Downloads, copied into the folder):
  - Functional: customer check stock, checkout (hold 15 min), payment; staff add_stock.
  - Implicit: login through an auth service + JWT; user info in home region; PII encrypted in transit/at rest.
  - NFR: 100k products; reads 5k/s at peak → read replicas, eventual consistency on replication lag;
    writes "200*2 + 500 = 900 WPS" → single Postgres writer, ready to shard later; p99 <100 ms reads,
    <300 ms hold; 99.95%.
  - Observation: the staff rate given was "a few hundred per DAY"; the sheet counts 500 per SECOND.
    Conclusion (one writer is enough) unchanged. Asked once as a numbers challenge.
  - Tech choices (Postgres, replicas) already appear in requirements — note for HL discipline.
  - Consistency for holds/overselling not stated explicitly.

## Phase 2 — High level
- The "where does the 500 come from" question went unanswered; candidate moved on to the flow.
- Auth: user/staff get a JWT from the auth service; it's sent to our stock API.
- Hold (checkout): one DB transaction: lock(?) ("logs") + check availability for every line; any line
  short → rollback + fail; otherwise decrement units in the same update and create the order /
  reservation + order lines. Return reservation_id; the user pays with it.
- Payment result: checkout calls us with (payment_result_id unique in their system, reservation_id). That
  pair = idempotency key. On success: reservation reserved → completed, and "update the stock,
  decrementing the amount of units".
  - OPEN: units are already decremented at hold — is this a second counter (on-hand vs available) or a
    double decrement? Not stated. Probe in the deep dive if the tables don't settle it.
- On failure: reservation → failed, release the available units per line.
- Expiry: an "automation service" scans the DB for checkouts older than 15 min; one tx marks the
  reservation expired and releases each line's units.
  - Potential race to probe: payment success arriving after/at expiry; expiry and success concurrent.
- Flows described verbally; no HL diagram yet (asked for one).
- Integration decision: checkout → stock API is synchronous, retryable HTTP. Future: queue
  (pub/sub) + circuit breaker / rate limit when the stock API is down. Same for the "order checker"
  (expiry job): decouple via a queue, e.g. push notifications to staff/user (notifications not in scope).
- Screenshot 02-high-level.png (copied from ~/Downloads/high.png):
  - Auth Service: user/staff send creds, get a JWT.
  - staff --add stock--> stock API service; user --checkout--> stock API service (direct).
  - Checkout Service --payment_result--> stock API service.
  - stock API service → DB; order checker → DB.
  - Observations: user calls the stock API directly for checkout, which contradicts the agreed boundary
    (checkout service owns checkout and calls us). No arrow from the checkout service for the
    hold, and no user ↔ checkout service (payment) edge. The "check stock" read path isn't drawn,
    and no read replicas appear despite the requirements sheet. Asked about the checkout inconsistency
    once.
- Correction (spoken): the user doesn't log into our service. The checkout service calls our
  checkout/hold on the user's behalf. Open: how the checkout service authenticates to us
  (service-to-service), and who serves "check stock" reads now.
- Candidate: our system has only two callers, the checkout service (holds + payment results) and staff
  (add stock). The customer "check stock" read (5k/s, in the requirements) has no caller now and
  hasn't been placed. Let it surface in the deep dive.
- Q: does the user check stock via us or via checkout? A: via us — the storefront's product pages call
  our service directly for availability (the 5k/s reads); no login needed to browse.
- Candidate: "user needs credentials to check stock". Contradicts the answer just given (no login to
  browse); pointed that out once.

## Phase 3 — Deep dive
- Tables (spoken): users(id PK, type text NOT NULL CHECK in ('user','staff')).
  - Observation: users authenticate with the auth service, and customers don't call us for writes
    (checkout does, and browsing is anonymous). Unclear what this table guards in our service; maybe
    staff authorization for add_stock?
- products/skus(id PK, title text, description text, quantity int >= 0, available int NOT NULL >= 0).
  quantity = units physically in the warehouse; available = units free to hold. Checkout (hold) decrements
  available.
  - This settles the HL "double decrement" question: hold → available−n; payment success →
    quantity−n (on-hand leaves). Two counters.
  - Observations: title/description are catalog data, which another service owns (said in requirements).
    No available <= quantity check stated.
- orders(id PK, user_id UUID FK → users, created_at NOT NULL, status in reserved|completed|failed|expired,
  per-transition timestamps, e.g. expired_at nullable).
  - Observations to probe:
    - The checkout → us hold call is "retryable HTTP", but no idempotency key on the hold/order has
      been named yet. A retried hold could create a duplicate reservation and double-decrement
      available.
    - user_id FK → local users table: who populates users if login is in the auth service and the
      caller is the checkout service?
    - Index for the expiry scan (status, created_at) not stated yet.
- order_lines(id PK, sku_id FK, amount int NOT NULL > 0). Candidate: "that's it for now; indexes,
  constraints and extra columns when we go deep".
  - Observation: no order_id FK on order_lines as spoken. Check the screenshot.
- No tables screenshot (candidate declined, "extract from my statements"). Tables recorded from speech only.
- Probe 1: hold call is retryable HTTP. Hold commits, response lost, checkout retries. What happens?
  - A: idempotency key = order id generated by the checkout service, used as orders PK → unique
    constraint blocks the duplicate. Works (single caller, so unique-within-checkout is enough).
    Not said yet: what the retry gets back (the original reservation vs an error). Asked as a follow-up.
  - A: first statement in the tx is INSERT order (id = checkout's order id); on conflict, read the
    existing row and return the same response as the original. Solid.
    (Note: a failed hold rolls back the insert, so a retry after "out of stock" re-evaluates. Acceptable.)
- Candidate declares "high level ended, let's go deep" (the tables and idempotency already came during HL).
- Hold mechanics: stock lives in skus (quantity / available), order transitions in orders. Per order line,
  a conditional update on skus.available (>= amount), done in sku_id order across lines to avoid
  deadlocks between concurrent orders. All in one tx with the order insert.
- Counter walk (spoken):
  - reserve: available −= amount per line if enough
  - payment succeeded: quantity −= amount per line (order → completed, said earlier)
  - payment failed: available += amount per line, order → failed
  - expiry (order checker): same as failed; available += amount per line, order → expired
  - staff add stock: quantity += n and available += n
  - Complete and consistent; invariant available <= quantity holds on every path.
  - Not said: are the transitions guarded by status = 'reserved' (conditional update on orders)?
- Probe 2: payment succeeds at ~14:59; the result reaches us at 15:02, after the checker already expired the order.
  - A: if the order is already expired, re-check availability. If enough, decrement available and
    quantity and mark it succeeded/completed; if not, compensate the user with a refund. Good.
    Open: who triggers the refund (we don't own payments, so presumably we tell checkout)?
- Probe 3: the checker and the success result hit the same order at the same instant. What stops both
  from applying?
  - A: both lock the order's SKU rows in sku_id order, so one wins and moves the order reserved →
    expired/completed; the loser sees the new status and does nothing.
  - Concern: this serializes on SKU rows, not the order row. It's correct only if the status is
    read AFTER the SKU locks are held; a status read before locking acts on stale data. The
    simpler guard is a conditional update on orders (WHERE status='reserved') or SELECT … FOR UPDATE
    on the order row. Asked when the status is read.
  - A: status is read after the SKU locks. Better: lock the reservation/order row first (PK lookup,
    fast), then change the status once the lock is held. Correct; reached the cleaner option on the
    follow-up.

## Phase 4 — Scaling
- Infra / security (spoken): API service and order checker scale horizontally; API behind an LB with TLS
  termination; mTLS inside the private network; sensitive data encrypted with a key held in a KMS.
  - Not said: service-to-service auth for the checkout service (mTLS could cover it, but it wasn't tied
    to it); staff authZ for add_stock; several checker instances picking the same expired rows (no
    SKIP LOCKED / partitioning mentioned; row locks keep it correct, though instances block each other).
- Availability: second cell in another region as failover, or an LB across APIs in two regions; a
  single writer, with a synchronous replica in the other region promoted on failure.
  - Not discussed: cross-region sync-replication latency vs the 300 ms hold budget.
- Bottleneck: the DB. More writes → shard by user or by SKU id.
  - Concern: stock lives per SKU, so sharding by user doesn't partition skus. Sharding by SKU makes a
    multi-line hold cross-shard and breaks the single-transaction hold. Probed.
- Read path (5k/s availability): read replicas appeared only on the requirements sheet. No cache, no
  drawing, not revisited.
  - A: "Then I will start with user id". No reasoning given. Follow-up: where does a SKU's available
    counter live under user sharding?
  - A: SKU sharding is better, with the limitation that multi-SKU orders need distributed
    transactions across shards. Limitation named, no resolution yet (saga / per-shard reservation with
    compensation, or "don't shard: ~200 holds/s fits one writer"). Asked how they'd handle it.
  - A: "saga pattern". Named only. Asked for a walk-through of the 3-line order where line 2 fails.
  - A: reserve the lines one by one; when line 2 fails, compensate (release) the lines already reserved.
    Basic shape is right. Not covered: where saga state lives, a crash mid-saga (line 1 reserved, no
    compensation), idempotent compensations, or the ~200 holds/s fitting one writer, so sharding may
    not be needed. Not probed further.
- Ops (spoken): canary deployments. Monitor CPU/memory/disk usage and IO on the API, checker and DB;
  latency, throughput and errors on all three; payment success/fail ratio; most expensive DB/API
  operations; low-stock products → notify staff.
  - Domain-specific signals not named: expired-hold rate, late-success-after-expiry / refund count,
    checker lag (oldest overdue reservation), oversell guard (available < 0 attempts).
- Global: replicate the cell per region for other countries. (Single warehouse; stock ownership per region
  not discussed.)
- Candidate closes: "I spoke about edge cases already. That's it."
- Never covered: the 5k/s read path for availability (caching / replicas / staleness on the product page).

## Timing
- Approx from file timestamps: start 18:08, reqs screenshot 18:18, HL screenshot 18:25, end ~18:47 → ~39 min.

