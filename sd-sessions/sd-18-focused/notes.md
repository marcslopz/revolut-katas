# sd-18-focused — Restaurant table reservations (lite mock 2/9, bookings)

Interviewer's running transcription — not candidate-authored. Format: **LITE SD MOCK** (`modes/system-design/coach.md`):
F → N → flow/blocks → states → one hard edge case; no boilerplate; live challenges pointing at the problem, answer only
if stuck. Targets: "unique within what?", counter walk on every transition, invariant table first, size to the given
number; from case 1: external snapshots never added to our counters; arithmetic traced before stating.

## Problem statement
Design a reservation platform where diners book tables at restaurants.

(Interviewer-private: core = **no two reservations on the same table with overlapping time ranges** (interval overlap, not a
counter). Simplest rules:
- ~20k restaurants (one country), ~20 tables each, table sizes 2/4/6; a reservation = party size + start time (15-min
  grid); **every reservation lasts 2 h**; we assign **one table** with capacity ≥ party (no combining tables).
- Booking confirmed instantly (no payment, no hold timer).
- Channels: our app/web, **restaurant staff** (phone/walk-in bookings via the same API), and **partner apps** (map/search
  apps) that call our API with **their own `request_id`, unique per partner**, and retry on timeout.
- Diner can cancel until 2 h before; staff mark **seated / no-show**; a no-show frees the table from 15 min after start.
- Dominant action: **search "restaurants near X with a table for N at T"** (≈2M searches/day) vs ~150k bookings/day; peak
  Fri/Sat 19:00–21:00 ≈ 5x; most bookings same day or next 7 days; booking window up to 30 days.
- Out of scope: payments/deposits, reviews, menus, notifications beyond one line, table combining, waitlists.
Targets: model (slot rows per table per 15 min with UNIQUE, or exclusion constraint on tstzrange, or per-table lock + overlap
check) with the trade-off; search read path (precomputed availability per restaurant/party-size/slot vs live query) and its
staleness; idempotency key `(partner_id, request_id)`; counters/slots on secondary transitions (cancel, no-show early release,
staff move to another table); hard edge case if none chosen: a party of 4 asks for 20:00, the only 4-table is free 20:00–21:45
but booked at 21:45 (overlap by 15 min) — and the staff extend a seated table's stay beyond 2 h.)

## Phase 1 — Requirements

- Q: actors and actions? A: actors — **diners** (our app/web), **restaurant staff**, **partner apps** (external map/search apps
  that book through our API). Actions, most common first: (1) diners **search restaurants with a free table** for a party size at
  a time near a place; (2) **book** a table (diners, partner apps, or staff for phone/walk-in bookings); (3) diners **cancel**;
  (4) staff mark a reservation **seated / no-show**; (5) staff manage their restaurant's tables (rare).
- Q: table capacity per restaurant in our system? A: yes — each restaurant has its **tables**, each with a **capacity (2, 4 or
  6)**, ~20 tables per restaurant. A booking gets **one table with capacity ≥ party size**; no combining tables.
- Q: how is a partner app's diner registered? A: **no account on our side** — the partner sends the diner's **name + phone**;
  the partner itself is identified by its API credentials (**partner_id**). Each booking request carries the partner's
  **`request_id`, unique within that partner**; partners **retry on timeout** with the same request_id.
- Q: walk-in customers? A: staff create a booking for them through our API (name optional), **starting now**, marked seated
  straight away; phone bookings are staff-created bookings for a future time. Same tables, same rules (2 h).
- Q: how many slots — lunch and dinner? A: not fixed sittings: a booking can **start on any 15-minute mark** within the
  restaurant's opening hours (typically lunch 12:00–16:00, dinner 19:00–23:30, per restaurant), and **always lasts 2 h**.
- **Scope cut (candidate, meta):** slots too much for a lite mock → new rule: **two fixed services per day, lunch and dinner;
  one booking per table per service** (a table booked for dinner is taken for the whole dinner service). No time ranges, no
  overlaps. Walk-ins take a table for the current service.
- Candidate summary: diners via our web; walk-ins/phone via staff; "**one** partner app" booking with the partner id. Corrected:
  **several partner apps** (~10).

## Phase 2 — Estimates

- Numbers given: ~20k restaurants (one country), ~20 tables each; **~2M searches/day**; **~150k bookings/day** (60% our app/web,
  25% partners, 15% staff); ~10% cancelled; ~5% no-show; bookings up to 30 days ahead, most same day or next 7; traffic
  10:00–22:00, peak Fri/Sat 18:00–20:00 ≈ 5x average. Search p99 < 300 ms (a few seconds stale OK); booking confirmed < 1 s;
  99.9%.
- Q: how long before staff can mark a no-show? A: **30 min after the service starts** (manual, staff decide); from then the
  table is **free again for the rest of that service** (walk-ins or new bookings).
- Q: cancellation window? A: diners (and partners on their behalf) can cancel **until 2 h before the service starts**; after that,
  only staff can cancel. No fees (no payments in scope).
- Screenshot `01-reqs.png`: stickies for diners / staff / partner_app (booking with name, phone, partner_id, reservation_id) /
  tables (capacity 2/4/6, ~20 per restaurant, lunch/dinner) / numbers / SLA. Writes: 150k × 1.15 / 12 h → **4 WPS avg → ×5 ≈ 20
  WPS → no sharding** (+). Reads: "**20M** searches/day" → 20M / 12 h × 5 → **2.3k QPS → read replicas**, seconds-stale OK.
  Live challenge: the number given was **2M** searches/day, not 20M → recompute and re-check the replica decision.
- Fixed: 2M → **~230 QPS** peak → **no read replicas**, one primary for everything. (+) decision revisited with the number.

## Phase 3 — Flow, blocks, states

- Screenshot `02-high-level.png`: partner_user → **partner service** (external) → search/book/cancel → **booking service API**;
  diner (search/book/cancel) and staff (manage_table, all staff actions) → API → DB. (+) proportionate: one service, one DB.
- Q: do staff complete the booking after seated? A: **no** — seated is final; the table is taken for that service anyway.
- Screenshot `03-tables.png` (draft; more to come): `restaurants(id, ...)`; `restaurant_tables(id, restaurant_id, capacity IN
  (2,4,6))`; `actors(id, name, phonenumber, type IN (partner, staff, diner))`; `bookings(id, restaurant_id, table FK, reserved_by FK
  actors, party_size > 0, status IN (booked, seated, no-show, canceled), service IN (lunch, dinner), service_start_at CHECK
  13h/19h)`.
  (+) booking row = the invariant entity (table + service). Not raised yet (constraints pending): the invariant constraint and
  how it treats canceled/no-show rows; partner request_id column.
- Flow search (no tx, eventual consistency OK): select a restaurant's tables by restaurant_id → index `(restaurant_id, capacity)`
  with `capacity >= party_size`. (Interviewer-private: per single restaurant so far; the stated search is "restaurants **near a
  place**" — many restaurants per search.)
- … then exclude tables with a booking for that `service_start_at` in status booked|seated. (+) canceled/no-show correctly don't
  block. Live challenge: the search is "restaurants **near a place** with a free table" — how many restaurants does one search
  touch, and how do you get them?
- Answer: (1) restaurant ids near the diner; (2) their tables with capacity ≥ party; (3) remove tables with booked|seated bookings
  at that service_start_at. (+) right shape. Live challenge (minor): how is "near" computed — which column/index?
- Answer: a **precomputed user × restaurant distance table** for our diners; real-time for partner users with the partner user's
  location. (Same idea as sd-16's user_distances.) Live challenge: size it — users × 20k restaurants rows; and the diner searches
  "near a place", which can be anywhere (not their home).
- Fixed: the searched location can be anywhere → **real-time distance for all users** (no precomputed table). (+) Index for "near"
  still not named (asked once more).
- Answer: `LIMIT 10` nearest. (Interviewer-private: LIMIT doesn't avoid computing/sorting all 20k without a spatial index.)
  **Answer given** (2nd attempt): a **geospatial index** on `restaurants.location` (PostGIS GiST; KNN `ORDER BY location <-> :point
  LIMIT N`) or a geohash/city column with a B-tree; at 20k rows a scan is still only a few ms — the index matters as it grows.
- Bookings filter: a key on **(restaurant_id, table_id, service_start_at) with WHERE status IN (booked, seated)** — partial index.
  (+) partial on active statuses. Live challenge: just an index for the search, or also **UNIQUE** — what does it guarantee?
- Answer: **partial UNIQUE** → the DB itself guarantees the same table isn't booked twice for a service. (+) invariant enforced by a
  constraint; cancel/no-show rows drop out of it automatically (secondary transitions free the table with no extra write).
- Flow book (tx): booking for a party size at a restaurant; **`SELECT ... FOR UPDATE` on the restaurant row** first (20 tables per
  restaurant). Live challenge: the partial UNIQUE already guarantees no double booking — what does locking the whole restaurant
  add, and what does it serialize (every booking of that restaurant, any date/service)?
- Revised: (1) non-blocking read of the restaurant's tables with capacity ≥ party; (2) **try INSERT into bookings table by table**
  (lexicographic order); a conflict on the partial UNIQUE = table taken → next table; first insert that succeeds → status booked,
  commit. (+) no explicit lock — the constraint is the arbiter; contention only on the same table+service.
  Live challenge (minor, product): order — a party of 2 with a 2-table and a 6-table free.
- Fixed: order by **capacity ASC, then id**. (+)
- Flow cancel (tx): `UPDATE bookings SET status = 'canceled' WHERE id = ? AND status = 'booked' AND service_start_at > now() + 2 h`;
  rows updated tells success. (+) conditional transition with the time rule inside the WHERE; the partial UNIQUE frees the table.
  Minor, not raised: 0 rows = not found / too late / already canceled (a repeated cancel could answer OK — idempotent).
- Cancel uses the PK, no extra index (+).
- Flow seated (staff, existing booking): conditional `UPDATE ... SET status = 'seated' WHERE id = ? AND status = 'booked'`. (+)
- Flow walk-in: INSERT a booking (generated id, table, restaurant, party size) directly as **seated**; unique violation = that
  table is already booked/seated for this service. (+) same constraint arbitrates walk-ins vs online bookings.
- Staff cancel = diner cancel without the 2 h check. (+)
- No-show = same as seated but status → no-show (from booked). Live challenge: the 30-min rule isn't in the condition.
- Answer: `status = 'booked' AND service_start_at < now() + 30 min`. Live challenge: direction — dinner at 19:00, staff click at
  18:45: does the condition let it through? (should be `service_start_at <= now() − 30 min`).
- Fixed: `service_start_at <= now() − 30 min`. (+)
- Flow partner booking: same as diner booking + duplicates: idempotency key **(partner_id, request_id)** — new `reservation_id`
  column; **UNIQUE (reserved_by, reservation_id) WHERE reservation_id IS NOT NULL** (or without the WHERE, NULLs don't collide).
  (+) **"unique within what?" right first time** — scoped to the partner. Live challenge (minor): on a retry, what does the
  partner get back, and is the idempotency check done before trying tables?
- Answer: on the idempotency conflict return the existing booking's table → the retry always gets the same table. (+) idea right.
  Detail noted: `ON CONFLICT DO NOTHING` returns no row, and two different unique constraints can fire in the table loop —
  simplest is to look up `(partner_id, request_id)` first and return the existing booking; spoken-design level is fine.
- Partner cancel = diner cancel + idempotency (a repeated cancel answers OK). (+)

## Edge case

- (States not presented separately — status list + conditional transitions given per flow.) Given: dinner 19:00, Ana's booking on
  table 7 (4-seat). **19:31** staff mark Ana **no-show**. **19:32** a walk-in party of 4 is seated at table 7. **19:40** Ana arrives.
  Variant: no walk-in — Ana arrives 19:33. What happens in each, which transitions are allowed (no-show → seated?), and what does
  the partial UNIQUE do? Also: staff want to move Ana to free table 9.
- Answer: (1) **no-show → seated not allowed**; staff look for a free table and create a **new booking** for Ana (walk-in flow);
  none free → Ana loses it. (2) variant: new booking on table 7 (the no-show row doesn't block the partial UNIQUE), reserved_by =
  staff. (3) move to table 9: cancel the existing booking on 7 and book 9.
  (+) reuses existing flows; no new transition needed; the constraint behaves correctly in both variants. Live challenge: (3) as two
  separate steps — between "cancel 7" and "book 9", another walk-in takes 9 → Ana has neither; atomic options?
  Minor: the new booking loses the link to Ana's original one (reserved_by = staff).
- Answer: new **move booking** action — in one tx, cancel the old booking and insert the new one as seated on table 9; (if 9 is taken
  the insert fails → rollback → Ana keeps 7). (+) atomic. Simpler alternative noted: a single `UPDATE bookings SET table_id = 9 WHERE
  id = ?` — the partial UNIQUE guards table 9 and the booking keeps its identity.

## Feedback

## Feedback (lite mock — coaching evidence only)

**Strong**
- **Invariant as a constraint**: partial UNIQUE on (table, service) WHERE status IN (booked, seated) — no explicit locks; walk-ins,
  online bookings and partner bookings all arbitrated by it; cancel/no-show free the table with no compensation write.
- Dropped the restaurant-wide lock on one challenge (insert-try per table, ordered by capacity then id).
- **Idempotency scoped to the partner** `(partner_id, request_id)` first time — the new MEDIUM item held for the 2nd case running.
- Conditional transitions with the business rule inside the WHERE (2 h cancel, 30-min no-show); edge case solved reusing flows, then
  made atomic.
- Replica decision revisited as soon as the number was corrected.

**To improve**
1. **Numbers recalled wrong on the canvas** (20M vs 2M searches) — decision followed the wrong number until challenged. Read the
   sticky against the stakeholder's answer before deriving.
2. **"Near" search**: precomputed user × restaurant distances again (sd-16 pattern), then `LIMIT` as the index answer — geo index
   given after two attempts. When a read is spatial, say "geo index, nearest-N".
3. **Time conditions**: direction slip on the no-show rule (`now + 30` vs `now − 30`) — trace one concrete time before writing it.
4. Minor: states not presented as a list/diagram (implicit per flow); move = cancel + insert where a single update suffices.
