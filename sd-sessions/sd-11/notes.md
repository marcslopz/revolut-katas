# sd-11 — Meeting room booking

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design a system that lets employees of a company book meeting rooms.

(Interviewer-private: first mock under the **40-minute scope rule** (2026-10-05): minimal scope with one
core. Keep answers simple: one office building to start, rooms with capacity, book / cancel / see
availability. **Out of scope unless they insist:** recurring meetings, notifications/reminders,
calendar integrations, approvals, check-in/no-show release. Core: **no overlapping bookings for the
same room** under concurrency (interval overlap, not a single slot) + **"which rooms are free between
14:00 and 15:00 for 8 people?"** query → tests the HIGH data-layer item (query → index → table → lock)
directly. Phase 4: one office → many offices / regions; Monday 9:00 burst; prove the bottleneck with
numbers (HIGH item). Domain non-fintech.)

## Phase 1 — Requirements

### Stated by interviewer (stakeholder answers)
- Q: a role for adding rooms? A: yes — an **office admin** adds/edits/removes rooms (name, floor,
  capacity). Rare operation. Employees book, cancel, see availability.
- Candidate's actions: admin add/edit/remove rooms; employee reserve/cancel a room for a time range,
  view a room's availability. (+) concise F list.
- Q: limits beyond "no double booking"? A: bookings in **15-minute steps**, **max 4 hours** each, up to
  **30 days ahead**. Nothing else (no per-employee quota, no approvals).

### Non-functional — stakeholder answers
- One office building to start: **5,000 employees, 200 rooms**.
- ~**3,000 bookings/day**, ~500 cancellations/day, ~**50,000 availability views/day**.
- Peak: Monday 09:00–10:00 carries ~20% of the day's bookings and views.
- p99: availability view < 300 ms; book/cancel < 500 ms. Availability 99.9%.
- Audit: keep booking history **1 year** (who booked what, when, cancellations); nothing regulatory.
- Q: PII / sensitive data? A: minimal — employee id + name come from the company's existing identity
  provider (SSO); meeting title optional and visible to colleagues. Nothing sensitive beyond standard
  protection.
- Q: only invited members see meeting details? A: invitees are out of scope; any employee sees who
  booked a room and the title. Only the **person who booked it (or an admin) can cancel**.
  Candidate: minimal info shown + authorised access to objects. (+) authZ at principle level.

### Estimation (candidate)
- Avg: reads 0.58 QPS ✔, writes 3.5k/day → 0.04 WPS ✔. Peak Mon 9–10: reads 10k/h → 2.78 QPS ✔,
  writes 600/h → 0.167 WPS ✔ (cancellations left out of the peak, negligible). "Very low, no sharding."
  (+) Correct and proportionate — a single small DB; numbers sanity-checked implicitly.
- Storage: employees 5 MB, rooms 200 KB, **availability rows per room per 15-min slot**: 200 × 36 slots/day
  (9 office hours × 4) × 30 days × 1 KB = 216 MB; audit 3.5k/day × 364 × 1 KB ≈ 1.27 GB/yr → one
  Postgres. ✔
  Interviewer-private: reveals a **slot-based model** (one row per room per 15-min slot, pre-created
  for 30 days) — a valid way to make overlap prevention a uniqueness problem. Implication to watch:
  a 4-hour booking = 16 slot rows claimed atomically; rolling window needs a job to create day 31;
  office hours assumed (9 h) — not asked. 1 KB/slot is generous (fine).

## Phase 2 — High-level design (candidate-led transition)
### Workflows (spoken)
1. Auth: credentials → Auth service → JWT; API validates it.
2. Admin add/edit/remove rooms (admin role checked from the JWT first): client idempotency key;
   add = INSERT … ON CONFLICT with UNIQUE(name) and UNIQUE(idempotency_key) → duplicate key returns the
   existing room id, duplicate name fails; edit = UPDATE (row lock); remove = soft delete + cancel the
   room's bookings in the same TX (idempotent via the key).
3. Book: **lock the room row**, check availability for the requested slot(s), reject if taken, else
   insert the booking (user_id, idempotency key) and commit (releases the lock).
4. Cancel: conditional UPDATE on booking_id WHERE booker = caller OR caller is admin → cancelled, else
   denied.
   Fail-fast checks: > 4 h, in the past or > 30 days ahead, outside working hours (9–18).
5. Room availability: bookings (status reserved) for a room in a time range (≤ 30 days), with owner name
   + title, paginated per day.
Interviewer-private:
- (++) **Lock stated while designing** (room row → check → insert → commit) — the HIGH item's "say the
  lock" part, unprompted. Fail-fast pre-flow validation before the TX; authZ in the WHERE clause of the
  cancel; idempotency keys everywhere; soft delete cascading to bookings in one TX.
- (−) "INSERT … ON CONFLICT blocks the table" — inaccurate (it locks the conflicting index entry, not
  the table). Minor.
- (−) Working hours 9–18 assumed, not asked (fine as a stated assumption).
- (−) Overlap check described as "the input slot" — a booking spans up to 16 slots; the check is a
  range overlap (`start < :end AND end > :start`). Also earlier storage implied pre-created slot rows,
  now a bookings table + room lock — model not fixed yet.
- (−) **Missing the main employee query**: "which rooms are free between 14:00 and 15:00 for 8
  people?" (search across rooms by time + capacity). Only per-room availability designed.

### Screenshot 01-high-level.png (new)
employee/admin → Auth Service (creds → JWT); employee/admin → Room Booking API Service (JWT) → DB.
Interviewer-private: (++) **right-sized**: three boxes for ~3 QPS peak, no queues/caches/workers
invented. (Auth service "creds" vs the stakeholder's existing SSO — fine at box level.)

## Phase 3 — Low-level design
### API (candidate)
GET /rooms/{id}?from&to&limit&offset (room's slots, paginated); POST /rooms/{id}/booking (slot in body,
user from JWT); DELETE /rooms/{id}/booking/{id}; POST /room; DELETE /room; PATCH /room/{id}.
Interviewer-private: (+) REST shape clean, identity from the JWT. (−) Still no endpoint for the main
employee need — **find free rooms for a time range + capacity** (`GET /rooms?from&to&min_capacity`).
(−) offset pagination (the earlier "per day" paging is simpler/stabler); DELETE /room lacks the id;
idempotency key header not shown in the API (mentioned in flows). Minor.
- DB: one primary (<10 row writes/s); **read replicas** with eventual consistency for views; recent
  bookings read from the primary to avoid stale data.
  Interviewer-private: (−) habit carried over from the high-volume mocks: at ~3 QPS the primary serves
  every read trivially; replicas + read-your-writes routing add complexity with no load reason. A
  standby for availability is the only replica this needs. Minor over-engineering (J item).

### Schema (spoken)
users(user_id PK, user_type admin|employee, name). rooms(room_id PK, name UNIQUE, capacity >0, floor).
bookings(booking_id PK, idempotency_key UNIQUE, owner_id FK, slot TZRANGE ("or timerange"), status
reserved|cancelled, meeting_title NULL, owner_name). audit_actions(action_id PK, user_id, type, room_id,
booking_id NULL, idempotency_key UNIQUE).
Interviewer-private (HIGH item check):
- (+) **Range type for the slot** (Postgres `tstzrange`) — the right primitive for interval overlap.
- (−−) **bookings has no room_id** — the field the whole flow ("book room X", "availability of room X")
  depends on. Same pattern as sd-6/8/9/10 (the core field of the feature missing).
- (−) rooms: no soft-delete column (deleted_at/status) and no idempotency_key, though both were stated
  in the workflow; audit_actions: no created_at.
- Candidate moving to indexes next — watch whether deriving the index from the availability query
  surfaces room_id.

### Indexes, walked query by query (candidate)
- create_room: insert the action with the idempotency key; ON CONFLICT → duplicate → return the room;
  the UNIQUE constraint already is the index.
- delete_room: by room_id (PK); insert action first (dedupe), then mark the room deleted.
  **Self-caught**: rooms needs `status TEXT NOT NULL (created|deleted)`, audit needs `executed_at
  timestamptz`. (+) The walk-each-query habit surfaced missing columns on its own — the HIGH drill
  working live. Cancelling the room's bookings on delete not restated here (needs bookings.room_id).
- edit_room: by PK; idempotency via actions.
- new booking: lookup by room_id, ordered by slot, status = reserved ("<>" — slip) → index (room_id,
  status, slot); plus a **table constraint so one room can't have two rows with overlapping ranges**;
  idempotency moved to actions (drop it from bookings).
  Interviewer-private: (+) room_id now used in the bookings index → the missing column is implicitly
  restored (not stated as "adding room_id", but consistent). (+) Asked for a DB-level overlap guarantee
  — that's Postgres' **exclusion constraint** (`EXCLUDE USING gist (room_id WITH =, slot WITH &&) WHERE
  (status = 'reserved')`, btree_gist), not named. With it, the room-row lock from the workflow becomes
  unnecessary (the DB rejects the overlap) — not reconciled. (−) A B-tree on (room_id, status, slot)
  can't answer range overlap well; the GiST index of the exclusion constraint does both.
- cancel: by booking_id (PK); idempotency via actions. ✔

### Infra / ops (candidate)
- Auth service; API behind an LB with TLS termination, horizontal; mTLS to the DB if needed; canary
  deploys; resource + throughput/latency/errors monitoring; **business metric: % usage per room** (add
  or remove rooms). ✔ proportionate.

### Edge cases (candidate)
1. Concurrent reservations → room-row lock → atomic read-check-write. ✔
2. DB degrading → alerts on resources; reads: inspect replicas/locks, replace an unhealthy replica;
   writes: promote a replica or fail over to a **passive synchronous standby** (no lost writes). ✔
3. Cancel/booking contention → same room-row lock. ✔
Interviewer-private: (+) correct for this scope. (−) Thin vs the scope's own interesting cases:
booking racing with the admin **deleting that room** (booking must re-check room status under the same
lock — holds if the lock is on the room row, not stated); client retry of a booking (idempotency
covered earlier). "Force the unlock" of DB locks is an ops anti-pattern (kill the blocking session
deliberately, not as a recovery strategy) — minor.

## Phase 4 — L → R → G (candidate-led)
- This diagram = one cell per building per region. Several buildings in a region: if employees can book
  other buildings' rooms → add building_id to rooms (filter by building); if not → isolated cells per
  building, no schema change. Global = same. Availability: cell in ≥2 regions near the building, sync
  standby promotion.
  Interviewer-private: (+) explicit options depending on a product question (cross-building booking).
  (−) **No numbers**: a cell per building is heavy operational cost for tiny load — even 100 offices /
  200k employees ≈ 100 QPS peak, one Postgres; the honest answer is "nothing breaks on load; I'd keep
  one deployment (maybe one per continent for latency) and add building_id". Bottleneck not proven —
  HIGH item. **Pushed once.**
- Q: assume isolated buildings (employees only book their own building)? A: mostly — but employees
  travel: ~5% of bookings are for a room in another office.
- Candidate: any employee can book any building; requests are routed to **the building's cell/region**
  (route by building, not by user). ✔ Consistent with cells per building. Still no numbers.
- Scale-up with numbers: worst case = everyone booking in one region; 200k employees = 40x → peak
  writes 0.167 × 40 = 6.67/s → ×10 row writes ≈ 67 row writes/s → **Postgres writes are not the
  bottleneck**. ✔ (+) proved with a number — HIGH Phase 4 item, after the push.
- Reads: 2.78 × 40 = 111 QPS → not the bottleneck. ✔
- Contention: employees per room stays 25 (200k / 8k) → no worse per-room contention than today. (+)
  **sd-10 lesson applied: contention reasoned per row/key, not as global throughput.**
- Not yet answered: the **cost** of running ~100 cells (one per building).
- Conclusion: **no bottleneck**; ~100 cells → higher infra cost; improvement: **cells per continent**
  (3 cells, each replicated ×2 regions on the continent) → needs office_id on rooms, indexed for
  availability. ✔✔ Right answer: proved "nothing breaks" with numbers, named the real cost (operating
  100 cells) and consolidated with the schema change it implies. (HIGH Phase 4 item: complete after one
  push.)
