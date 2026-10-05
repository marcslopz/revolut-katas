# sd-12 — Cinema seat booking

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design a system that lets people book seats for movie screenings at a cinema chain.

(Interviewer-private: 40-minute scope rule. Keep answers minimal. Core: **choose specific seats for a
screening; seats are held for ~10 minutes while the user pays; then confirmed or released** — no
double-selling a seat under concurrency, hold expiry. Payment = an external provider with a
redirect + callback; keep it simple (success/fail), out of scope beyond that. Out of scope unless they
insist: food, discounts, loyalty, refunds, notifications. Targets: dominant action (view the seat map
of a screening) asked/designed first; main query → index → table (seats per screening); lock/condition
stated while designing; Phase 4 opened unprompted with numbers — premiere hotspot = many users on the
same screening's seats → per-row contention (ρ = λ × S) vs throughput.)

## Phase 1 — Requirements

### Stated by interviewer (stakeholder answers)
- Q: different rooms/cinemas? most common user actions? (+) **asked for the most common action
  unprompted in the first question** — MEDIUM item fired.
  A: chain of **100 cinemas**, ~**10 rooms** each, **150–300 seats** per room. A **screening** = a movie in a
  room at a time; screenings and seat layouts come from an existing internal scheduling system (out of
  scope to manage). User actions, most common first: (1) browse showtimes, (2) **open a screening's seat
  map** (by far the most common), (3) choose seats → seats held while paying → confirmed.
- Q: are we in charge of payment? what if the user doesn't pay? A: no — an **external payment
  provider**: we redirect the user with an amount + our booking reference; the provider calls us back
  with paid/failed. Seats are **held for 10 minutes**; if no successful payment within 10 minutes the hold
  expires and the seats are released.
- Q: global users/cinemas? A: **one country** for now (all 100 cinemas); expansion to other countries may
  come later.

### Non-functional — stakeholder answers (business numbers; candidate derives rates)
- ~**5,000 screenings/day** (100 cinemas × 10 rooms × ~5), avg ~200 seats → ~1M seats/day on offer;
  ~**120k bookings/day** (~2.5 seats each ≈ 300k tickets).
- ~**3M seat-map views/day**; ~5M showtime-browse requests/day.
- Peak: Fri/Sat 18:00–21:00, busiest hour ≈3x the average hour.
- **Premiere hotspot**: blockbuster tickets go on sale at a set time — ~**100k users open the seat maps of
  the opening-night screenings in the first 10 minutes** (a few dozen screenings).
- Audit: keep bookings **2 years** (accounting). No other regulation.
- Price: fixed per screening (from the scheduling system), **single currency (EUR)**.

### Estimation (candidate)
- Avg reads: (3M + 5M)/day → 333k/h → 93 QPS ✔. Avg writes: 120k/day → 5k/h → "2 WPS" (1.4, rounded) ✔.
- Peak ×3: 279 QPS, 6 WPS ✔.
- Premiere: few dozen screenings (36–72) × 200 seats = 7.2k–14.4k seats; first holders keep them 10 min;
  100k in 10 min → **166 WPS** → still one Postgres primary, no sharding.
Interviewer-private: (+) seat supply vs demand computed (7–14k seats for 100k users → most won't get
seats). (−) The 100k are **seat-map opens (reads)**, not all writes; hold attempts ≤ seats available.
(−) Throughput framed globally again; **per-key contention not computed** (≈2k users per screening,
fighting over the same best seats) — the sd-10 ρ = λ × S lesson not applied here yet. Watch in LLD.
- Candidate applies occupancy: hold write ~50 ms; 100k / 600 s × 0.05 s = **8.33 → 833%** → "we're going to
  queue in the premiere, other users affected".
  Interviewer-private: (+) used ρ = λ × S unprompted (sd-10 coaching lesson). (−−) **Misapplied**: ρ = λ × S
  holds for *one serialized resource*. 166 writes/s spread over many rows/connections aren't serialized
  — Postgres runs them in parallel. The serialized unit is a screening (if locked per screening) or a
  seat: ~2k users per screening in 10 min ≈ 3.3/s × ~5 ms ≈ 2% occupancy. Also 50 ms per write is ~10x
  a typical single-row write. Factual/technical error → **probe asked** ("which resource is
  serialized?").
- Corrected after one probe: the serialized unit is the **screening** → 50 screenings → 2k users per
  screening / 600 s × 5 ms ≈ **1.67%** → fine. ✔ Also corrected the per-write time to 5 ms.
  (+) Quick, precise fix; the per-key contention method is now in place.
- Storage: 120k bookings × 2.5 seats × 1 KB × 365 = 109.5 GB/yr ✔ → 219 GB in 2 years → one Postgres. ✔
  Interviewer-private: per-screening seat inventory (~1M seat rows/day if one row per seat per screening)
  not sized — small anyway (~tens of GB/yr), and depends on the model still to be chosen.
- Q: is screening data filled by others? Re-ask (covered: existing scheduling system, out of scope) —
  pointed out lightly; added: it publishes each new/changed screening (movie, room, time, price, seat
  layout) as an event/API you can consume.
- Implicit (candidate): no payment data stored (provider handles it; we keep booking ref + provider ref +
  result — confirmed); only user PII → encrypted in transit and at rest (key in KMS). ✔ principle level.

## Phase 2 — High-level design (spoken)
API: (1) Auth → JWT, checked by the API. (2) Browse screenings by day + cinema (read). (3) **Open seat
map** by screening_id — "here we update (skip locked) the seats held more than 10 minutes ago".
(4) **Hold N seats**: write with locking — update the seat rows only if all are free; **locks taken in
lexicographic seat order**; under the lock, check each is free or held > 10 min ago; else fail; if OK set
held, held_at, held_by. Client idempotency key on hold.
Seat-free worker: cron every second, conditional update + SKIP LOCKED for holds older than 10 min, unpaid.
Screening consumer: reads scheduling events → inserts screening (cinema, room, time, seat map); acks
after; idempotent by screening_id.
Interviewer-private:
- (++) **Lock stated while designing**, with **deadlock avoidance** (lock seats in a fixed order) and a
  conditional all-or-nothing hold; expired holds treated as free at hold time (lazy expiry) — so
  correctness doesn't depend on the worker. HIGH data-layer "say the lock" part fully unprompted.
- (−) **Seat-map read path writes** (releases expired holds on every open): turns the most common read
  (3M/day, 100k in 10 min at premieres) into writes/locks. The map can simply *display* `held_at < now −
  10 min` as free; release stays in the hold TX + worker.
- (−) **Payment flow not described yet**: redirect, callback → confirm, and the key race (callback
  arrives after the hold expired and someone else holds the seat). No booking entity yet (booking ref,
  provider ref, status).
- **Self-revised**: drop the update from the seat-map read (premiere would lock for no reason); release
  only in the seat-free worker. (++) "decisions follow new facts" — caught by the candidate, no probe.
- Payment flow: API answers 3xx redirect to the provider with a booking_id; user pays; provider callback
  accept/reject. Accept → atomically set the seats confirmed (confirmed_at, status) with row locks.
  Reject → user back to the seat map, seats still held, can retry. payment_reference stored as the
  idempotency key on the seat booking.
  Interviewer-private: (+) redirect + callback + idempotency on the provider reference. (−) **Key race not
  covered**: payment succeeds at minute 11 — the hold already expired and another user now holds those
  seats. The confirm must be conditional (`WHERE held_by = :user AND booking_id = :b AND status = 'held'`)
  and the 0-rows case needs a compensation (refund). **Probe asked.** Also "retry after reject" while the
  10-minute clock keeps running (fine, but not said).
- Answer: reverting a payment is costly → **take the seats back from Bruno** and confirm Ana.
  Interviewer-private: (−) moves the problem instead of removing it: if Bruno is already on the payment
  page, his payment can succeed too → now Bruno is charged with no seat (refund anyway) — and holds become
  unreliable for everyone. Real fixes: don't let the worker release a hold whose payment is **in flight**
  (status payment_pending with its own, longer timeout, or extend the hold at redirect), and/or
  **refund Ana** as the compensation when the conditional confirm finds 0 rows. **Challenged once.**
- Fix: at redirect, status held → **paying**; the worker never frees `paying` seats. ✔ Removes the race
  at its source. (−) Opens the next failure path: `paying` forever if the user abandons the payment page
  or the callback is lost → needs a paying timeout + status query to the provider. **Follow-up probe.**
- Answer: give the provider an **expiry for the payment session** (held_at + 10 min) so the user can't pay
  later; a longer safety window (e.g. 30 min) for `paying`; after that, free the seats.
  ✔ Good: makes "too late" a rule both sides share (the expires_at pattern from the cross-cell saga
  coaching). (−) Before releasing a `paying` hold, **query the provider's status** — a successful payment
  whose callback was lost would otherwise lose its seats ("unknown ≠ failed"). Minor, not said.
- **Self-added**: before freeing a `paying` hold whose outcome is unknown, query the provider's status
  (it may already be paid). ✔ Closed the gap without a probe.

### Screenshot 01-high-level.png (copied from ~/Downloads/highj.png — newest "high*" file)
user ↔ Auth (creds → JWT); user → Cinema Booking API (JWT) → DB; API → user "url redirect external with
booking_id" → user → External Payment Provider; provider → API "callback completed/rejected"; new
screening events queue → Screening event consumer → DB; Seat free worker → DB.
Interviewer-private: (+) right-sized, matches the spoken design. (−) No worker → provider edge for the
status query added a minute ago (minor drift).

## Phase 3 — Low-level design
- Postgres, one primary (writes), read replicas with eventual consistency for reads. ✔ Proportionate
  here (~280 QPS peak + premiere bursts; the seat map tolerates a slightly stale view because the hold
  re-checks on the primary — not said, but consistent).

### Schema + queries → indexes (spoken)
users, cinemas, rooms(cinema_id); screening(screening_id PK, room_id, cinema_id, start_time, date_range
DATERANGE "days the screening is available", info); screening_seats(seat_id, screening_id, PK
(screening_id, seat_id), status free|held|confirmed, booking_id NULL, held_at, confirmed_at);
bookings(booking_id PK, user_id, idempotency_key UNIQUE, status held|confirmed|canceled,
payment_reference UNIQUE NULL); booking_seats(booking_id, seat_id) PK; actions(action_id, type, user_id,
booking_id, screening_id).
Queries:
- add screening: INSERT … ON CONFLICT DO NOTHING (idempotent by PK).
- browse: WHERE cinema_id AND room_id AND date ∈ date_range ORDER BY start_time → index (cinema_id,
  room_id, date, start_time).
- seat map: WHERE screening_id → index screening_id.
- hold: UPDATE screening_seats SET held WHERE screening_id AND seat_id IN (…) AND (free OR held_at < now −
  10 min) → index (screening_id, seat_id, status, held_at).
Interviewer-private:
- (++) **Query → index walk for every path, unprompted**, and the dominant read (seat map) designed
  first. HIGH data-layer item: clearly improving.
- (−) **Drift / missing own-flow fields**: `paying` status (added 10 minutes earlier) absent from
  screening_seats and bookings; bookings lacks **screening_id**, amount, payment-session expires_at,
  updated_at; actions lacks created_at.
- (−) Screening modelled with start_time **and** a date_range of days — contradicts "a screening = a
  movie in a room at one time"; browse filters by room although users browse by cinema + day → index
  (cinema_id, start_time) is enough.
- (−) Redundant indexes: the PK (screening_id, seat_id) already serves the seat map and the hold.
- (−) Hold all-or-nothing: the UPDATE may match only some seats → must check rows-updated = N and roll
  back otherwise (not said); a single UPDATE … IN (…) doesn't guarantee the lexicographic lock order
  stated earlier → `SELECT … ORDER BY seat_id FOR UPDATE` first.

### Infra / security (candidate)
- Independent deploys for API + seat-free worker, horizontal scaling (worker already uses SKIP LOCKED);
  LB with TLS termination; mTLS internally for sensitive data; encryption at rest with a KMS key. ✔
  Callback authentication (provider signature) not mentioned.
- Ops: recent reads from the primary; idempotent ops everywhere; resource monitoring on all components;
  queue depth for the screening consumer; latency/throughput/errors per component; **business metrics**
  (room/screening occupancy %, hottest screenings) and **payment provider error % + latency**. ✔
  Missing business SLI for the core: holds expired unpaid, payments confirmed after expiry (refunds) —
  minor.

### Edge cases (candidate-led)
1. Screening consumer crashes before writing → no ack → redelivered; screening_id makes duplicates
   harmless. ✔ (−) The scheduler also sends **changed** screenings (time/room changes — stated earlier);
   `ON CONFLICT DO NOTHING` silently drops those updates → needs DO UPDATE with a version guard.
2. Seat-free worker crashes mid-release → TX rolls back → safe retry. ✔
3. DB degradation: deadlocks → "try to unlock", investigate root cause; primary out of resources/hardware →
   fail over to the sync standby; broken read replica → replace.
   Interviewer-private: (−) deadlocks: Postgres detects and aborts one TX automatically → retry it; the
   design already *prevents* them by locking seats in a fixed order — that's the answer to give, not
   manual unlocking (same "force unlock" pattern as sd-11). Failover ✔.
4. Provider edge cases (self-identified as "the most difficult part"):
   a. User reaches the provider but never pays → after 10 min the worker queries the provider; not paid →
      free the seats; the provider denies any later payment (session expired). ✔ (recap of the agreed
      design)
   b. Callback lost/timed out → the worker, before freeing, queries the provider → final accepted/rejected
      → update the booking accordingly. ✔ ("unknown ≠ failed" applied.)
   Not covered: provider fully down (users can't pay — holds just expire; maybe pause new holds /
   circuit breaker), callback authentication, duplicate callbacks (payment_reference UNIQUE covers it —
   said earlier).
   c. Duplicate callbacks → payment_reference makes it write once. ✔
   d. Double hold from the client → idempotency key → held once. ✔

## Phase 4 — Scaling (candidate-led, **unprompted**)
- Countries/regions: two regions per continent, sync standby promotion when a region goes down. ✔
- 10x users: peak writes still < 1k ops/s → no sharding; storage ~1 TB (10x of 219 GB/2 yr ≈ 2.2 TB — slip,
  conclusion holds); bottleneck candidate = **premiere hotspot** (1M users in 10 min) → **per-screening
  occupancy** ≈ 10% at 10x (exact: ~17%) → below 50% → OK.
- Keep growing → 10k–50k writes/s → **shard by screening_id**; hot screening = hot shard ("not that much");
  beyond a limit → an in-memory **waitlist / waiting room** for premieres.
Interviewer-private:
- (++) **HIGH Phase 4 item fired unprompted for the first time**: numbers, the occupancy method applied
  to the right resource, the next threshold, the shard key, the hot-shard consequence, and a mitigation.
- (−) Small numeric slips (storage 1 vs 2.2 TB; 10% vs 17%) — conclusions unchanged. Cost of sharding /
  of a waiting room not spelled out (minor).
