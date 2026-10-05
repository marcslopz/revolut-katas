# sd-10 — Library book reservations

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design a system for a network of public libraries that lets members reserve books online and pick
them up at a branch of their choice.

(Interviewer-private: first non-fintech mock, per the candidate's request (2026-10-05). Calibration:
normal difficulty, technical focus, quarter-point scale, J + K sections. Core: per-copy inventory
across branches; reserving the last available copy under concurrency (no double allocation); a
**waitlist/queue** when nothing is available (fairness, FIFO position); **hold expiry** (pick up within
N days or the copy goes to the next in line) — timers/state machine; copy transfer between branches
(in-transit state). Targets: HIGH schema completeness + query-derived indexes (availability search
by title + branch; waitlist position), MEDIUM "decisions follow new facts" (introduce waitlist /
expiry / transfer requirements as answers), MEDIUM Phase 4 bottleneck + cost (city → country →
international; popular-release hotspots: thousands waiting on one title), failure paths with
notifications (an external email/push provider). Little to no residency pressure — check they don't
over-apply fintech patterns.)

## Phase 1 — Requirements

### Stated by interviewer (stakeholder answers)
- Q: two actors — members who reserve, branches that register copies? A: yes, with branch **staff** as
  the second actor: they add/remove copies, **prepare** reserved books (take them off the shelf, or send
  them to another branch), mark a book as **picked up** when the member collects it, and check in
  **returns**. Members search, reserve, cancel, and see the status of their reservations.
  (+) Actor-first opening.
- Q: fixed return time? can the user extend? A: two stages. **Reservation (hold)**: once the copy is
  ready at the chosen branch, the member has **3 days to pick it up**, otherwise it's released.
  **Loan**: after pickup, **21 days** to return; **one renewal of 21 days**, only if no other member is
  waiting for that title.
  (Note: "other members waiting" hints a queue exists — given as part of the renewal rule.)
- Q: per-user limits? overdue? block the user? A: **max 10 items at once** (active reservations + loans
  combined). Overdue: reminder notifications; while a member has **any overdue loan, they can't place
  new reservations** (existing ones stay). Fines out of scope.

### Non-functional — stakeholder answers (asked reads/writes per second, staff + users)
Business numbers given (candidate derives rates):
- Network: **200 branches** in one country; **5M members**, ~2M active per month.
- Catalog: **3M titles**, **25M physical copies**.
- Members: **~2M searches/day**; **~150k reservations/day**; ~15k cancellations/day; status checks
  ~1M/day.
- Staff: ~120k pickups/day, ~140k returns/day, ~40k branch-to-branch transfers/day, ~5k copies
  added/day.
- Daily pattern: activity mostly 09:00–21:00; busiest hour ≈3x the average hour.
- **Hotspot**: when a bestseller is released, up to **~50k members try to reserve the same title in
  the first hour**.
- Q: audit trail for years? availability, p99? A:
  - Retention: reservation/loan history kept **2 years**, then anonymised (privacy policy — libraries
    keep as little reading history as possible). Catalog/copies kept as long as they exist.
  - Availability: member site/app 99.9%; **staff desk operations (pickup/return scanning) 99.95%**.
  - Latency p99: search < 500 ms; place a reservation < 1 s; staff scan (pickup/return) < 300 ms.
- Q: PII / legal encryption requirements? A: yes — members' name, email, phone, address, library card
  number are PII (EU country, GDPR: protect it, members can ask for export/deletion). **Reading history
  is treated as sensitive** (it can reveal beliefs/health) → hence the 2-year anonymisation; staff
  should only see what they need. Branch data isn't sensitive. Standard expectations: encrypted in
  transit and at rest; no specific extra regulation.
  (+) Candidate asked the implicit question themselves (principle level).

### Estimation (candidate)
- Reads: 3M/day → 34.72 QPS avg ✔; 12-hour window → 250k/h ×3 → 750k/h → 208 QPS peak ✔.
- Writes: 470k/day → 5.43 WPS avg ✔; 39.17k/h ×3 → 117.5k/h → 32.64 WPS peak ✔.
- Hotspot: 50k in 1 h → 13.89 WPS ✔.
- ×<10 DB ops per action → ~320 WPS and "2k QPS" → single Postgres primary + read replicas, no sharding.
Interviewer-private: (+) clean, both windows (12 h active day + 3x hour) applied, explicit verdict.
(−) Reads ×10 inflated (a read isn't 10 DB ops; harmless overestimate). (−) **Hotspot treated as
throughput (13.9/s, tiny) instead of contention**: 50k requests competing for the *same title's*
handful of copies / one waitlist — the real issue is row-level lock contention and fairness, not
WPS. Not raised; watch in LLD.
- Candidate (self-raised, right after): hotspot risk = **row lock contention**, latency across the 50k:
  read-check-write ~5 ms → 50k × 5 ms = 250 s serialized "is a lot" → for bestsellers, an in-memory
  **Redis** reserve/fail-fast path, then persist the result to the DB.
  Interviewer-private: (+) recognised contention unprompted (revisited own estimate). (−) Sanity: 250 s
  of lock time spread over the hour is ~7% utilisation — only a real problem if the 50k arrive within
  the first seconds/minute (not established). (−) Redis as the reservation authority + "persist later"
  = durability/dual-write risk (Redis failover loses accepted reservations; Redis and DB can disagree).
  (−) **Not yet asked: what happens when no copy is available** — with ~hundreds of copies and 50k
  requests, almost everyone joins a **waitlist** (queue), they don't "fail". Waitlist not discovered
  yet (only hinted in the renewal rule). Watch.
- Candidate: members join a **waitlist queue**, consumed FIFO to allocate the available copies; the rest
  "fail"; users see their position and get an async result once all copies are reserved.
  Interviewer-private: (+) waitlist + FIFO + async result + visible position, self-discovered.
  (−) Product assumption "the rest fail" — stakeholder correction given: members who don't get a copy
  **stay in line**; as copies are returned they go to the next person (weeks/months for a bestseller).
  This turns the waitlist from a burst buffer into a **long-lived, persistent queue per title** —
  checks whether earlier decisions (Redis fail-fast, queue broker) get revisited.
- Stakeholder answer added: waitlist persists; returned copies go to the next member in line; members
  can leave the line; position visible.
- Revisited immediately: waitlist as a **DB table with a sequence number** instead of one broker queue
  per bestseller (less infra). (++) "Decisions follow new facts" item fired right away — the queue
  design changed as soon as the long-lived requirement arrived. Position = rows ahead in the same
  title (index (title_id, seq) implied, not said). Redis fail-fast path not explicitly dropped yet.
- Storage: members 5M × ~1 KB = 5 GB; titles 3M × 1 KB = 3 GB; loan actions 465k/day × 1 KB × 365 =
  169 GB/yr ✔, 339 GB in 2 years → Postgres fine under 1 TB; archive anonymised loan data to cold
  storage after that. (+) sizing + verdict. Minor: the 25M **copies** table not sized (~25M rows — still
  small).

### Phase 1 close — interviewer summary
- Candidate-led: actors, hold vs loan rules, limits/overdue, NFR numbers, SLAs, PII question,
  estimation (clean), hotspot contention self-raised, waitlist self-discovered and moved to a DB table
  once it became long-lived, storage. Strong Phase 1.
- Not asked: what "ready at the chosen branch" involves (copy at another branch → transfer, in-transit
  state); how members get notified (hold ready, expiring, overdue).

## Phase 2 — High-level design
- Q: how are reminders sent — DB table shown in-app, or external providers? A: via an **external
  provider** for **email and push** (API, async, can fail/time out — standard). An in-app list is
  nice-to-have. Notifications needed: book ready for pickup, pickup window ending tomorrow, loan due in
  2 days, overdue reminders.
- Q: overdue reminders — how many, how long? A: on days 1, 7 and 14 after the due date; after 30 days
  the copy is marked **lost** and staff follow up offline (no more automatic reminders).

### HLD — API actions + automation worker (spoken, no diagram yet)
API:
1. Staff add/remove copies → TX: title total_copies ±, insert/remove BookCopies rows (monotonic seq,
   branch_id).
2. Prepare reserved book → other branch: status in_transit, move copy to the new branch_id, audit
   action. Same branch: status prepared, pickup_due_at = +3 days, reserved_by = user, audit.
3. Picked up → status picked_up, return_due_at, audit.
4. Return → status available, clear reserved_by; if the title has a waitlist → prepare for the next
   member, update the waitlist.
5. Reserve → if a copy is available at the selected branch: hold it (destination branch, reserved_by,
   status reserved); else the member can join the title's waitlist.
6. Loan: staff own picked_up + return_due_at; member can renew +21 days if nobody waits.
Automation worker: notify staff of new reservations to prepare/send; notify member when ready (+
pickup due date); notify staff when pickup expired (unhold or prepare for the next in line); member
reminders (pickup ends tomorrow, due in 2 days, overdue 1/7/14); notify staff when a copy is marked
lost at 30 days.
Interviewer-private:
- (+) Complete action inventory for both actors + a scheduled worker covering every timer; copy-level
  state machine (available → reserved → in_transit → prepared → picked_up → available/lost) emerging.
- (−) Pre-flow checks missing from reserve: the **10-item limit** and the **overdue block** (stated
  requirements).
- (−) In-transit **arrival** isn't an action: when does the copy become `prepared` and the 3-day window
  start? (Receiving staff scan.)
- (−) Reserve only looks at the *selected* branch; copies available at *other* branches (→ transfer)
  aren't considered at reserve time, though step 2 handles transfers.
- (−) Pickup expiry handled by "notify staff to unhold" — releasing the hold and promoting the next
  waitlisted member should be automatic (system-owned), staff only re-shelve. Member cancellation and
  leaving the waitlist not covered.
- Level of detail: statuses/columns at HLD (mild), but organised by actions — acceptable.

### Screenshot 01-high-level.png (new)
user/staff → Auth Service (creds → JWT); user/staff → Library API Service → DB; Automation worker
("check/change book status, outbox notifications") → DB and → notifications queue → notification
consumer → Email provider / Push provider.
Interviewer-private: (+) clean MVP skeleton; auth for both actors; notifications decoupled through a
queue with external providers. (−) Worker drawn publishing to the queue directly while labelled
"outbox" (relay not shown — same minor drift as sd-8). No search component (2M searches/day over 3M
titles — fine in Postgres full-text, but undecided). Redis hotspot path silently gone (simplification,
not stated). Read replicas not drawn (minor at HLD).

## Phase 3 — Low-level design
- DB: Postgres, 1 primary + read replicas; primary for recently changed reads (read-your-writes),
  eventual consistency elsewhere. ✔ (same pattern as sd-8/sd-9). Availability search ("is a copy free?")
  would need the primary at reserve time — the decision itself is a write (conditional update), so fine.

### Schema (spoken)
users(user_id PK, type user/staff, branch_id FK — staff's branch or member's favourite).
branches(branch_id PK, address, …). titles(isbn PK, title, author, number_of_copies ≥0).
book_copies(isbn FK, seq_number autoinc from 1, branch_id FK, status IN (available, reserved,
in_transit, ready_for_pickup, picked_up, lost), picked_due_at NULL, return_due_at NULL, reserved_by
FK users) PK (isbn, seq_number); indexes (isbn, status), (status, picked_due_at), (status,
return_due_at).
waitlist(isbn FK, wait_list_position autoinc from 1, user_id FK) PK (isbn, wait_list_position).
actions(action_id PK, isbn, seq_number NULL, user_id NN, type IN (…), created_at, metadata JSONB).
outbox(outbox_id PK, type IN (pickup, loan, overdue, lost, prepare, reservation), isbn, seq_number).
Interviewer-private (HIGH item check — query-first + own-flow fields):
- (+) Copy-level state machine in one column; timer indexes (status, picked_due_at) and (status,
  return_due_at) derived from the worker's queries ✔; audit table with JSONB metadata; isbn as natural
  key.
- (−) **Fields the own flow uses but the schema lacks**:
  - book_copies: **pickup/destination branch** (reserve sets "destination branch"; in_transit needs a
    target); updated_at/version.
  - waitlist: **the member's chosen pickup branch**, created_at, status (waiting/left/fulfilled), and a
    UNIQUE(isbn, user_id) so one member can't join twice.
  - users: **email/phone/push token** — the notification consumer needs a recipient; name.
  - outbox: **recipient user_id, payload, status/published_at, created_at**; no dedupe key for
    reminders (e.g. UNIQUE(isbn, seq, type, due_date) so the day-7 reminder isn't sent twice).
- (−) **Indexes vs main queries**: reserve looks up "available copy of isbn **at the selected branch**"
  → (isbn, branch_id, status) — branch missing; member's own loans/reservations (status view, 10-item
  limit, overdue block) → (reserved_by, status) missing; "my waitlists" → (user_id).
- actions.user_id NOT NULL but the automation worker also acts (system user needed).

### Infra / security (candidate)
- Auth service issues JWT (staff/user); LB with TLS termination, API scales horizontally; mTLS
  internally for PII; encryption at rest with a KMS-held key; automation worker + notification consumer
  scale horizontally; notification queue HA + durable + DLQ; circuit breakers on the providers —
  **stop both the consumer and the automation worker** when providers are down; half-open with rate
  limiting; close when healthy.
  Interviewer-private: (+) solid baseline; failure path of the external provider covered unprompted
  (breaker, half-open, DLQ). (−) **Coupling**: the automation worker also runs the *state machine*
  (expire holds after 3 days, promote the next waitlisted member, mark lost at 30 days). Stopping it
  because email/push is down freezes those business transitions. **Probe asked.**
- Answer: state transitions keep running (worker checks/changes statuses); only the outbox → queue
  publishing pauses; members already knew the pickup deadline, so no release notice is needed.
  ✔ Correct decoupling after one probe (the outbox naturally buffers notifications).
  Interviewer-private: (−) remaining edge: the *next* waitlisted member gets a hold whose 3-day window
  starts while their "ready" notification is stuck → they may lose it without knowing. Fix: start the
  pickup window when the notification is actually sent (or extend windows by the outage). Review item.
- Ops: canary, independent autoscaling; resource monitoring on API, workers, broker, DB; queue depth,
  message age, DLQ alerts; broker acks both ways (at-least-once); idempotency by outbox_id. ✔
  Interviewer-private: (−) no business SLI (e.g. "ready" notifications delivered within X min; holds
  expiring without a delivered notification; waitlist promotions per hour). outbox_id dedupe needs a
  "sent" record on the consumer side to avoid double emails — implied.
- Business metrics: titles with no available copies (hot titles → order more), longest waitlists
  (order more), titles with all copies available (reduce copies). (+) product-level metrics,
  unprompted — beyond the sd-5..9 pattern. (These are analytics queries → run on a replica/warehouse,
  not the primary — not said; minor.)

### Edge cases (candidate-led)
1. API crashes mid-TX → rollback; client retries with a client-generated idempotency key. ✔
2. Worker crashes mid-action → status change + outbox in one TX; retried. ✔
3. Worker dies before publishing → republish. ✔ 4. Dies before broker ack → duplicate, idempotent. ✔
5. Consumer dies before calling the provider → no ack → redelivered. ✔
6. Consumer dies after sending, before the response → redelivered (idempotent). ✔ (provider-side
   duplicate email possible unless the provider takes an idempotency key — minor)
7. Provider rejects → transient: retry N; invalid message: DLQ. ✔
8. Provider timeout → retry N, then breaker (stop consumers and "stop producing outbox messages").
Interviewer-private:
- (++) Every outcome of the external call covered **unprompted**: success / reject (transient vs
  invalid) / timeout / crash before-after send — the MEDIUM failure-path item, clean this time (late
  reversal doesn't apply to notifications).
- (−) Drift in 8: "stop producing outbox messages" contradicts the fix two turns ago (keep writing the
  outbox, only pause publishing) — if taken literally, notifications are lost.
- (−) **Core concurrency not covered**: two members reserving the last copy at once, and fairness at
  return time (a non-waitlisted member grabbing a just-returned copy before the first in line).
  **Probe asked.**
- Answer: reserve must first check whether the title has a waitlist; if so, Carla joins it at the end;
  the worker reserves the copy for Dan first; Carla only if copies remain. Framed as an "eventual
  consistency problem".
  Interviewer-private: (+) right business rule (waitlist has priority over direct reservations).
  (−) Mechanism not atomic: with the worker promoting Dan *asynchronously*, the returned copy sits
  `available` between the check-in TX and the worker run; correctness then depends on every reserve
  path checking the waitlist. Cleaner: **promote the next waiter inside the check-in TX**, so a copy is
  never `available` while someone waits. Not "eventual consistency" — it's an atomicity/race problem on
  the primary. No locking mentioned. **Follow-up probe (classic last-copy race).**
- Answer: every reserve TX starts with `UPDATE titles SET available_copies = available_copies − 1 WHERE
  isbn = ? AND available_copies > 0` → the title row lock serializes reservations per title; the winner
  continues (copy reserved, action, outbox); the loser blocks on the row, then sees 0 → **joins the
  waitlist in the same TX**. ✔ Correct, atomic, serialised per title — and it doubles as the hotspot
  mechanism (no Redis needed).
  Interviewer-private: (−) schema drift: the table had `number_of_copies` (total), not `available_copies`.
  (−) The counter is per title, but reserve was "available at the **selected branch**" — per-branch
  availability vs a global counter not reconciled. (−) Check-in path should do the inverse in one TX
  (increment, or hand straight to the first waiter). Not said.

## Phase 4 — Scaling / availability (candidate-led)
- Single country → two regions in the same country; primary in one, **synchronous** standby in the
  other for failover. ✔ (consistent with sd-7–sd-9 learning; no fintech residency over-applied — good
  calibration to the domain).
- More countries → replicate the cell per country/region; transfers only within a country → no
  cross-region data. (+) clean, assumption stated.
  Interviewer-private: (−) no new bottleneck / cost named unprompted (3rd mock running) → **pushed once**.
- Answer: workers scale; DB sharding only if writes reach ~10k/s (10x isn't enough — think 100x/1000x);
  cold storage sooner. **Bottleneck: the external notification providers** → options with costs:
  (1) provider adapter + routing across several providers (complexity + more providers to pay),
  (2) pay the current providers for more throughput/latency, (3) relax the number of notifications —
  prefers 1 or 2 because the business depends on notifications.
  Interviewer-private: (+) **bottleneck + options + explicit costs + a preference** — the most complete
  Phase 4 answer so far (after one push). (+) correctly judged that 10x (~3k WPS) doesn't force sharding.
  (−) No numbers for the provider claim: 10x of today's notifications is roughly tens per second —
  well within typical email/push providers; the real first pressure at 10x is likely the per-title row
  lock on a bestseller (≈10x the 50k/h hotspot) or nothing at all. Sanity check missing on the
  bottleneck itself.
