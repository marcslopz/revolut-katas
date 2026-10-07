# sd-21 — Library network reservations (full mock, bookings, timed)

Interviewer's running transcription — not candidate-authored. Full mock under `modes/system-design/interviewer.md` (quiet interviewer,
candidate leads). **Timed** — budget requirements 5–10 / high level ~15 / deep dive ~20 → 40–45 min. Phase timestamps logged when the
candidate announces them. Target from sd-20: time.

## Problem statement
Design a reservation system for a city's network of public libraries: users reserve books, pick them up and return them, and library
staff add new copies.

(Interviewer-private: 40-minute scope. Simplest rules:
- **~300 libraries** in one city network; ~500k titles; **~10M copies**; each copy belongs to **one library forever** (no transfers).
- User reserves a **title at a library of their choice**. If a copy is on the shelf there → it's **held for pickup for 3 days**
  (staff take it to the hold shelf; keep simple: held = reserved for that user); else the user joins that library's **waitlist for the
  title (FIFO)**.
- Pickup at the counter → **loan of 21 days**. Return (at the **same** library) → if someone is waiting there for that title, the copy is
  **held for the next in line** (3 days), else back to the shelf.
- Hold not picked up in 3 days → expires → next in line, or shelf.
- **A user can have at most 5 active items** (holds + loans + waitlist entries) **across all libraries**.
- Screenshot `02-high-level.png`: Auth Service (JWT) → user/staff → **Library API** (search/reserve/cancel; add/remove/pickup/return) → DB;
  **Status checker** (worker) → DB and → **External notification service** (pickup expired / return overdue). (+) proportionate. (Interviewer-
  private: "copy set aside for you" notifications from the API path (return → next in line) not drawn — minor.)
- Staff add copies (new copy → serves the waitlist first) and remove damaged ones.
- Numbers (if asked): ~2M members; ~3M catalogue searches/day ("which libraries have title X available"); ~100k reservations/day;
  ~80k pickups and ~80k returns/day; 9:00–21:00, peak ~3x; search p99 < 300 ms (seconds stale OK), reserve < 1 s; 99.9%.
- Out of scope: fines, notifications beyond "notify the user", renewals, catalogue management, inter-library transfers.
Targets: dominant read (availability of a title across libraries — index (title_id, library_id) / per-library counter); hold as a
conditional claim on a copy (or a counter per (title, library)); waitlist FIFO + promotion on return/expiry/new copy; **per-user limit
across libraries** (counter on the user row, conditional, every transition walks it); timer race: hold expires as the user is at the
counter; states as a table; Phase 4: more cities / hot title (bestseller with 2k waiting).)

## Timing
- 16:48 — problem statement given
- 16:56 — candidate: requirements done
- 17:06 — candidate: → deep dive
- 17:32 — scaling (opened unprompted)
- 17:33 — END MOCK

## Phase 1 — Requirements

- Q: any other actions from staff or users? A: most common first: users (1) **search a title and see which libraries have it available**;
  (2) **reserve** a title at a library; (3) **cancel** a reservation; pickup and return happen **at the counter, registered by staff**.
  Staff: register **pickups** and **returns**, **add new copies**, **remove** damaged/lost copies.
- Q: what if a book isn't returned in time? A: loans last **21 days**; late = **overdue**, nothing automatic (fines/reminders out of scope);
  the loan stays active (and keeps counting for the user) until returned; people waiting for that title just keep waiting. (Interviewer slip: "counts toward the user's limits" hints a limit exists.)
- Q: non-functional requirements? A: ~300 libraries, one city; ~500k titles, ~10M copies (each belongs to one library); ~2M members; **~3M
  searches/day**; **~100k reservations/day**; ~80k pickups and ~80k returns/day; ~2k copies added/day; 9:00–21:00, peak ~3x. Search p99 < 300
  ms (seconds stale OK); reservation confirmed < 1 s; 99.9%.
- Screenshot `01-reqs.png`: actions (user: search title availability, reserve(title, library), cancel; staff: add copies, register pickup/return,
  remove copies); implicit: PII encrypted in transit (HTTPS + mTLS) and at rest (KMS); numbers all copied right; writes 262k/day → 18 WPS ×10 DB
  writes → **180 WPS, one DB, no sharding**; reads 3M → **208 QPS, no replicas**.
  (+) fast (≈5 min), numbers right, conclusions drawn. (Interviewer-private: **reservation rules never asked** — what if no copy is available
  (waitlist?), how long a reserved copy is held, the user limit (hinted), loan length not on the canvas. Implicit reqs generic only.)
- Q (after closing requirements): cancel any time before pickup? pickup time? no-show? A: **cancel any time before pickup**. Once a copy is
  **set aside for the user** they have **3 days** to pick it up; not picked up → the hold **expires** and the copy goes to the next user waiting
  for that title at that library, or back to the shelf.
- Q: no-show procedure — automated or staff? A: **automatic in our system** at the 3-day mark (the next user mustn't wait for staff); staff
  get a daily list of expired holds to move the physical books.
- Q: assume a push-notification provider? A: yes — an existing internal notification service; just "notify the user", details out of scope.

## Phase 2 — High-level design

- Flows (spoken, before a diagram): staff add/remove copies → DB. User searches title availability across libraries, closest libraries via a
  **geolocation index on libraries** (+, sd-18 lesson applied); picks an ISBN at one library and reserves; 3 days to pick up; staff mark
  pickup; staff mark return; user can cancel before pickup → reservation cancelled, copy free again. **Status checker** (worker): holds not
  picked up in 3 days → expired; loans > 21 days → overdue; notify (user for overdue, staff for expired) with an idempotency key.
  Q: "the pickup time is 3 days after the reservation, right?" A: **3 days from when a copy is set aside for the user** — at reservation time if
  one is on the shelf there; **if none is available, the user waits in line for that title at that library** and the 3 days start when a copy
  comes back for them.
  (Interviewer-private: availability assumed at reservation — the "no copy available" case never asked until this answer.)
- Q: so there's a waitlist per title? A: yes — **per title per library, first come first served**; a returned copy, an expired hold's copy, or a
  newly added copy goes to the first person in that library's line for that title. Also: **a user can have at most 5 active items** (waiting +
  held + on loan) **across all libraries**.

## Phase 3 — Low-level design

- **Postgres** (joins, ACID); "one replica is enough for our traffic" (= a single DB instance). (HA standby for 99.9% not mentioned.)
- Q: distinguish two copies of the same ISBN? A: yes — each physical copy has its **own barcode (copy id)**, belongs to one library; staff scan
  the copy's barcode at pickup and return.
- Screenshot `03-tables.png` (draft): `users(id, type staff|user)`; `libraries(id, geolocation)`; `book_titles(isbn PK, title indexed)`;
  `book_copies(isbn FK, barcode PK)`; `library_copies(id, isbn, library_id, PK (library_id, isbn))`; **`library_books(isbn, library_id, PK
  (library_id, isbn), copies >= 0, available >= 0)`**; `reservations(id, user_id, isbn, copy_id NULL until pickup, status IN (free, reserved,
  picked_up, no_show, returned, overdue), reserved_at — "3 days to no-show", picked_up — "21 days to overdue", returned_at)`.
  (+) counter per (library, title) with copies/available — the invariant row. (Interviewer-private: **`reservations` has no library_id** (reserve
  is per library); **no waiting vs held distinction** (the 3 days start when a copy is set aside, not at reserved_at); **no field/counter for the
  5-item limit**; `book_copies` has no library_id while `library_copies` duplicates `library_books`' key.)
- Happy path (one tx each): **reserve** — check library_books, `available −= 1`, insert reservation `reserved` + reserved_at, answer the id;
  **pickup** — staff scan a copy of that title on the shelf, reservation → `picked_up` + timestamp; **return** — staff find it by copy id →
  `returned`, `available += 1` in the same tx.
  (+) counter and status in one tx. (Interviewer-private: **available = 0 → waitlist** not handled; **return → next in line** not handled
  (available += 1 even when people wait); the **5-item limit** not enforced; conditional transitions not stated.)
- Cancel: reservation → **`canceled`** (new status) and `available += 1` in the same tx. (+) counter walked. (Same gap: if someone waits, the copy
  should go to the next in line.)
- Status checker: reservations `reserved` > 3 days → **no_show** + `available += 1` in the same tx. (+) counter. (Interviewer-private: no
  conditional on the state (user at the counter as the checker fires); next in line not served.)
- Interviewer probe (stated requirement not designed): a user reserves a title at a library where **available is 0** — 3 people already wait.
- Answer: **waitlist** (per title per library) with an **auto-increment position**; available = 0 → user appended. Whenever a copy is freed
  (returned, no-show, cancelled) the **first user in the waitlist is removed and a reservation (hold) is created** for them, and they're
  **notified** they have 3 days. (+) FIFO promotion on every freeing transition. (Interviewer-private: that `available` must **not** be
  incremented when the copy goes to the next in line — implied, not said; new copies added should also serve the waitlist; notification
  inside vs after the tx (outbox) not said; the **5-item limit** still not designed.)
- Overdue: checker sees pickup + 21 days without return → `overdue` + notify; availability unchanged (the book is with the user). (+)
- Add/remove copies: copies and available += n (or −= for damaged) + insert/delete barcodes in book_copies. (Interviewer-private: new copies
  should **serve the waitlist first** (stated rule) — added straight to available; second secondary-transition miss on the waitlist.)
- Idempotency: client-generated UUID as idempotency key; UNIQUE column on reservations; insert … on conflict → return the first result. (+)
  (Scoped per user `(user_id, key)` would be safer than a global UNIQUE on a client-generated value — minor.)

- Infra: stateless Library API horizontally scaled behind a LB (TLS termination), mTLS internally; **status checker scaled horizontally**; ACID in
  the single DB; canary deploys with rollback on latency/errors/throughput; monitoring: host resources incl. DB, slowest DB/API transactions,
  p99 read/write latency, checker operations, errors/throughput; notification error rate + **idempotency key on notifications**; business
  metrics: hot titles (reservations), idle titles → add/remove/move copies later.
  (+) business metric tied to a decision. (Interviewer-private: several checker instances on the same reservations → conditional transitions /
  SKIP LOCKED not stated; DB HA for 99.9% not mentioned.)

## Phase 4 — Scaling

- **Opened unprompted**: failover — deploy to different AZs or regions, route traffic to one, the other as failover (single writer, otherwise no
  transactions); or balance reads across two cells, write in one with the other a sync replica for failover; more countries/regions → replicate
  the cell. (Interviewer-private: no number or bottleneck (at 10x: ~1.8k write ops/s, ~2k QPS — still one DB); hot title (a bestseller with
  thousands waiting → one counter row + one waitlist) not discussed.)
- Growth: bottleneck = DB writes → **shard by user, or by country/city**. (Interviewer-private: no number; by user would split the per-library
  counter and waitlist (shared by many users) across shards → by city/library keeps reservations single-shard, with the cross-library 5-item
  limit as the cross-shard cost. Trade-off not weighed. Not probed — at the time budget.)

## Wrap-up
