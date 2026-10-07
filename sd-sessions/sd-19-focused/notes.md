# sd-19-focused — Stock transfers between shops (lite mock 3/9, stock)

Interviewer's running transcription — not candidate-authored. Format: **LITE SD MOCK** (`modes/system-design/coach.md`):
F → N → flow/blocks → **states (as an explicit list)** → one hard edge case; no boilerplate; live challenges pointing at the
problem, answer only if stuck. Targets: "unique within what?", counter walk on every transition, invariant table first, size to
the given number, numbers copied right onto the canvas, time conditions traced.

## Problem statement
Design the stock system for a fashion retailer with a central warehouse and 50 shops, which moves stock between its locations.

(Interviewer-private: core = **stock moves between locations through a transfer with an in-transit phase** — counters on both
sides across every transition. Simplest rules:
- Locations: 1 central warehouse + 50 shops, one country; ~10k SKUs; stock per (location, SKU).
- Transfer = from location → to location, several lines (SKU, qty). States: **requested → shipped → received** (or **cancelled**
  before shipping). Source stock leaves at **ship** time; destination stock arrives at **receive** time; between them it's
  **in transit** (belongs to nobody's shelf, but must not vanish from totals).
- Receiving is done with **handheld scanners** that work offline and sync later: each scan event = `device_id`, **`scan_id`
  (unique per device)**, transfer_id, sku, qty; at-least-once on sync. Received quantity can be **less than shipped** (lost/
  damaged) → discrepancy recorded, the missing units written off after review (out of scope beyond recording).
- Shops also sell (our own tills, simple decrement events) and the warehouse receives supplier deliveries — both simple.
- Shops request transfers; warehouse/shop staff ship; dominant read = **"stock of SKU X across all locations"** (staff app, ~500k
  views/day) and per-location stock.
- Numbers (if asked): ~300k sale lines/day; ~3k transfers/day × ~20 lines; ~60k scan events/day; staff stock views ~500k/day;
  hours 9:00–21:00, peak ~3x; transfers take 1–3 days in transit.
- Out of scope: routing/trucks, replenishment algorithms, pricing, customer-facing app.
Targets: stock per (location, sku) with on_hand (+ maybe reserved for requested transfers); in-transit counted on the transfer lines
(shipped_qty, received_qty); idempotency on **(device_id, scan_id)**; counters on: request (reserve at source?), cancel, ship,
partial/over receive, close with discrepancy; states as an explicit list; hard edge case if none chosen: offline scanner syncs a
receive scan **after** staff already closed the transfer with a discrepancy (late scan → units found).)

## Phase 1 — Requirements

- Q: actors and actions? A: actors — **shop staff**, **warehouse staff**, the shops' **tills** (ours) and **handheld scanners** used
  to receive goods. Actions, most common first: (1) staff **view stock of a SKU** — at their location and across all locations;
  (2) **till sales** decrement shop stock; (3) a shop **requests a transfer** (from the warehouse or another shop); (4) the source
  **ships** it; (5) the destination **receives** it by scanning items; (6) warehouse records **supplier deliveries**.
- Q: customer returns/refunded SKUs? A: **ignore** — out of scope.
- Candidate assumption: "all transfers arrive right, no damaged or lost products". A: **not quite** — sometimes **fewer units arrive
  than were shipped** (lost or damaged in transit, ~2% of transfers); the destination records what it actually received; the
  difference is recorded as a discrepancy (what happens to it afterwards is out of scope).
- Q: so lost/damaged units are removed from stock? A: yes — they never enter the destination's stock and are gone from the
  company's total.

## Phase 2 — Estimates

- Numbers given: 1 warehouse + 50 shops, one country, ~10k SKUs; **~300k sale lines/day**; **~3k transfers/day × ~20 lines**; **~60k
  scan events/day**; ~1k supplier delivery lines/day; **staff stock views ~500k/day**; hours 9:00–21:00, peak ~3x; transfers spend
  **1–3 days in transit**. SLA: stock views p99 < 300 ms (a few seconds stale OK); 99.9%.
- Screenshot `01-reqs.png`: actors/actions stickies; numbers; writes = 200k sale lines + 60k transfer lines × 3 (requested, shipped,
  received) + 1k → 381k/day → ×3 / 12 h → **26 WPS, no sharding**; reads = 60k scans + 500k views = 560k → **"30 QPS"**, same DB, no
  replicas. (+) transfer lines ×3 for the three transitions — counter-per-transition thinking.
  Live challenges: (1) **till sales copied as 200k — the number given was 300k** (same pattern as case 2's 20M); (2) **scans counted
  as reads** — what does a scan do to the data?; minor: 560k × 3 / 43,200 ≈ 39, not 30. Conclusions unchanged either way.
- Fixed: 300k → **~34 WPS** peak. Scans: assumed the scanner only looks up the SKU locally and "received" writes all lines once staff
  finish. Stakeholder correction (fact about the device): **scanners work offline; each scan is stored on the device and synced to us
  later as an event** — `device_id`, `scan_id` (unique per device), transfer_id, sku, qty — **at-least-once**; ~60k/day; staff then
  close the transfer as received. So scans are writes.
- Q: can scanners send one batch per transfer instead of one event per scan? A: **no** — a device syncs whatever it has when it gets
  connectivity (one HTTP call may carry many scan events, but each is a separate scan); **one transfer's scans can come from several
  devices and in several syncs**.
- Q (re-ask; transfer_id was in the event fields): how does the scanner get the transfer_id? A: staff **scan the transfer's
  label/box first**, then the items; every scan event carries that transfer_id.
- Q: so "transfer received" can arrive and later scan events, unordered? (+) found the planted edge case's premise himself. A: **yes** —
  scans from different devices arrive in any order, and a device that was offline can sync scans **after** staff closed the transfer.
- Q: how do we get the discrepancy / know scans have finished arriving? A: design is the candidate's; facts: **devices send no "done"
  signal**; staff close the transfer when they believe everything is scanned; a device usually syncs within minutes, **rarely up to
  24 h later**.
- Decision: **apply stock as each scan event arrives** (destination +qty); transfer status changes when staff close it; a process
  computes the **discrepancy 24 h after the close** (shipped − received). (+) decouples stock from the close and waits out the sync
  window — fits the stated p-max. Open: scans after the 24 h computation.
- Q: supplier receiving also with scanners? A: **no** — warehouse staff record a supplier delivery in one API call (delivery note with
  lines), online.

## Phase 3 — Flow, blocks, states

- Screenshot `02-high-level.png`: scanner (scan events), staff (transfer actions / supplier received), till (sale_action) → **stock manager
  API** → DB; **discrepancy checker** (worker) → DB. (+) proportionate: one API, one DB, one worker.
- Screenshot `03-tables.png` (draft; supplier deliveries, sales, staff users still missing; state machine next): `buildings(id, type IN
  (warehouse, store), UNIQUE type WHERE warehouse)`; `skus(id, name, description)`; **`sku_stocks(id, sku_id, building_id, quantity
  >= 0, available)`**; `sku_transfer_lines(id, sku_stock_id FK, quantity > 0)`.
  (+) invariant table drawn first, two counters; one-warehouse rule as a partial UNIQUE. Live challenges: no **transfers** table (from,
  to, status) and lines without transfer_id; a line points at **one** `sku_stock_id` but a transfer touches **two** locations — which
  one?; where do shipped vs received quantities live (needed for the 24 h discrepancy)? Minor: UNIQUE (sku_id, building_id).
- Answers: (1) `sku_transfers` exists; lines now have transfer_id; (2) `from_building_id`, `to_building_id` on sku_transfers; (3) "a
  discrepancies table or something like that". Live challenge: a discrepancy table stores the **result**; to compute it you need, per
  line, what was shipped and what has been received so far — where do the scan events add up? (and lines can reference `sku_id`, the
  locations come from the transfer).
- Answer: a **scan_events** table (each scan stored) + the checker compares the transfer's lines to the summed scans per SKU and inserts
  into the discrepancies table. (+) works (sum at +24 h); a `received_qty` counter on the line is the alternative. Idempotency of scan
  events not discussed yet.
- State machine / transitions (candidate): **requested** — insert transfer + lines, hold `available −= q` at the source (one tx);
  **requested → shipped** — conditional on requested, status only; **→ received** — staff scan and mark received: atomically
  **source quantity −= q, destination quantity += q**; **→ lost** after n days by staff: source quantity −= q.
  (+) hold at request; conditional transition; lost path has a counter. Live challenges: (1) **contradiction** with the earlier decision
  "apply stock as each scan arrives" — now the destination gets stock at the close, and with which quantity: shipped or scanned?;
  (2) between ship and receive (1–3 days) the source's `quantity` still counts units that left on the truck; (3) destination
  `available` not mentioned.
- Answers: (1) scans go to their own table, not sku_stocks; at the close the destination gets the **shipped** quantities (may be more
  than really arrived) and the discrepancy is handled afterwards on another path; (2) the source's `available` already excludes the
  shipped units — `quantity` keeps them until received (units belong to the source while in transit — coherent with lost → source
  −= q); (3) destination: **quantity and available += q**.
  (+) consistent ownership model (in-transit stays with the source). Live challenge: the destination got the **shipped** quantity;
  the checker finds 2 units missing at +24 h — what happens to the destination's counters then?
- Answer: on a discrepancy, **destination quantity and available −= missing** (20 → 18). (+) Candidate notes "the discrepancy flow was out
  of scope" — clarified: the follow-up (investigation/write-off) is; correcting the counters is needed because the design added the
  shipped quantity.
- Check stock: `sku_stocks WHERE building_id = ? AND sku_id = ?` → **UNIQUE (sku_id, building_id)** (no duplicate SKU per building). (+)
  sku_id first also serves the "across all locations" view (`WHERE sku_id = ?`).
- Flow request transfer (one tx): per line conditional `UPDATE sku_stocks SET available −= q WHERE sku_id AND building_id AND available >=
  q`; any 0 rows → rollback; then insert transfer (from, to, staff, requested) + lines. (+) all-or-nothing hold. Live challenge: several
  SKU rows locked per transfer — two transfers from the same building with the same SKUs in different order? (lock order not stated).
- Fixed: deadlock → always update in **sku_id order**. (+) first challenge.
- Flow ship: `UPDATE sku_transfers SET status = 'shipped' WHERE id = ? AND status = 'requested'`; PK, no extra index. (+)
- Flow receive (one tx; scans arrive async separately): lock the lines' sku_stocks rows ordered by sku_id; destination quantity and
  available += line qty; source quantity −= line qty; status → received WHERE status = 'shipped'. (+) both sides in one tx, conditional
  transition, lock order. Live challenge: a shop receiving a SKU it has **never stocked** — there's no destination row. Minor: same SKU
  has two rows (source, destination) → order by (sku_id, building_id).
- Fixed: **upsert** (INSERT … ON CONFLICT DO UPDATE) for the destination row. (+) first challenge.

## Edge case

- Given: transfer of **20 units of SKU A**. Two scanners: device 1 scans 12 and syncs at once; device 2 scans 8 but is offline. Monday
  10:00 staff close as received (destination +20). Tuesday 10:00 the checker sees 12 scanned → discrepancy 8 → destination −8. **Tuesday
  16:00 device 2 comes online and syncs its 8 scans — and, on a flaky connection, sends the same batch twice.** Ask: counters, scan
  storage, idempotency key, final state.
- Q (re-ask of fields, repeated). Answer: idempotency key = **(scan_id, transfer_id)**; duplicate → ignore. (Interviewer-private: scan_id is
  unique **per device** → two devices on the same transfer both have scan #1 → device 2's real scan dropped. "Unique within what?" missed
  here — the key must be **(device_id, scan_id)**.) Live challenge with that scenario.
- Fixed: key = **(device_id, scan_id, transfer_id)** (device_id + scan_id suffice; transfer_id harmless). (+) one challenge.

## Feedback
- Answer: on the late scans, update the transfer's scanned total; the discrepancy becomes 0 → **compensate +8** at the destination
  (quantity and available) → final 20. (+) late events after the close handled as a correction (case 1's lesson applied). Not discussed:
  serializing the checker and a late scan (lock the transfer row) — minor.

## Feedback (lite mock — coaching evidence only)

**Strong**
- Found the edge case's premise himself in Phase 1 ("received can arrive before the scans, unordered?") and designed around it: stock on
  close + discrepancy check 24 h later, waiting out the stated sync window.
- Invariant table first (`sku_stocks` with quantity/available), coherent ownership model (in-transit units stay with the source),
  transitions conditional, hold at request, lock order, upsert — each gap fixed on the first challenge.
- Late scans after the discrepancy handled as a compensation (+8), the opposite of discarding them.
- Counted writes per transition (×3) in the estimates.

**To improve**
1. **"Unique within what?" missed** with scanners: `(scan_id, transfer_id)` when scan_id is unique per device — fixed on one challenge.
   Two of three cases today held it; the miss came when the id was a device's, not a company's. Ask it for every external id.
2. **Numbers copied wrong again** (300k → 200k) and scans counted as reads — read stickies back against the stakeholder.
3. **A decision reversed without saying so** ("apply stock per scan" → "stock at close"); when you change a decision, say it.
4. **States list**: given in prose this time — better than case 2, still not a table of transitions.
