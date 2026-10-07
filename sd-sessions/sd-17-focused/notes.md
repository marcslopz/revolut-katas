# sd-17-focused — Company card spending limits (lite mock 1/9, fintech)

Interviewer's running transcription — not candidate-authored. Format: **LITE SD MOCK** (`modes/system-design/coach.md`):
F → N → flow/blocks → states → one hard edge case; no boilerplate; live challenges pointing at the problem, answer
only if stuck. Targets: "unique within what?", counter walk on every transition, invariant table first, size to the
given number.

## Problem statement
Design spending limits for company cards: each employee's card has a monthly limit, and every card payment must be
approved or declined against it.

(Interviewer-private: core = **a counter per card per month with holds**. The card processor (external, already
integrated) calls us **synchronously to approve/decline each authorization** (must answer < 200 ms; if we don't answer
in time the processor **declines**). Later, asynchronously (minutes to days), the processor sends events for that
authorization: **capture** (final amount, may differ from the authorized one, e.g. tips; **can come in several partial
captures**), **reversal** (released, nothing charged), **refund** (money back after capture). Events at-least-once, each
with **`event_id` (unique per processor)** and the **`authorization_id`** it refers to. One processor. Limit counts in the
**month of the authorization**; refunds give limit back only if in the same month (else ignore — keep simple). Admins
set/change limits. ~5k companies, ~200k cards; ~1M authorizations/day; peak lunch ~3x; ~10% authorizations never captured
(expire after 7 days → hold released automatically by us).
Targets: invariant `spent + held + amount <= limit` via conditional update on the card-month row; counters on every
transition (auth → hold; capture → hold→spent with amount diff; partial captures; reversal; 7-day expiry; refund);
idempotency on **event_id**, not authorization_id (partial captures share the auth id); timeout = decline and the processor sends **nothing** more for that authorization → if we committed a hold but
answered late, the hold leaks until the 7-day expiry (blocks the employee's limit). Hard edge case if none chosen: capture
arrives after our 7-day expiry released the hold.)

## Phase 1 — Requirements

- Q: actors and actions? A: actors — **employees** (card holders), **company admins**, and the **card processor** (external
  system, already integrated). Actions, most common first: (1) **processor asks us to approve/decline each card payment**
  (authorization) in real time; (2) **processor tells us later what happened** to that authorization (final amount charged,
  cancelled, refunded); (3) employees **see their remaining limit**; (4) admins **set/change a card's monthly limit**.
- Q: employee/admin = sync API; processor approval sync; processor results — sync callback too? A: approval is a **sync call,
  we must answer in < 200 ms**; if we don't, the processor **declines and sends nothing more** for that authorization.
  Results are **async HTTP events (webhook)**, minutes to days later, **at-least-once**; each has an **`event_id` (unique per
  processor)**, the **`authorization_id`** and a type: **capture** (final amount, may differ from the authorized amount; a
  single authorization **can be captured in several parts**), **reversal** (cancelled, nothing charged), **refund** (money back
  after a capture). One processor.
- Q: how do we know the processor declined us by timeout? our own timer? can we query the processor for a payment's status?
  (+) spotted the timeout-leak risk unprompted. A: **we're not told**; the processor offers a **status API**: `GET
  /authorizations/{authorization_id}` → approved / declined / captured / reversed. Whether and when to call it = candidate's
  design.
- Q: meaning of the statuses; why no refunded? A: they're the processor's view of the **authorization**: approved = our
  approval reached it in time, waiting for capture; declined = we declined **or answered too late**; captured = at least one
  capture done; reversed = cancelled before any capture. **Refunds are separate transactions** after a capture (they arrive
  as refund events), not a state of the authorization.
- Q: refund event carries the same authorization_id? A: yes — it references the original authorization_id, with its own
  event_id and amount; there can be several refunds per authorization (partial refunds).
- Candidate: events can take days → can't wait forever → maybe a process that verifies status to shorten the window during
  which the limit is held. (Thinking aloud; no hold-duration rule asked yet.)

## Phase 2 — Estimates

- Numbers given: ~5k companies, **~200k cards**; **~1M authorizations/day**, mostly 8:00–22:00, lunch peak ~3x; ~1.1 events
  per authorization (captures, reversals, refunds); ~10% of authorizations never get any event; employees check remaining
  limit ~300k times/day; admins change limits ~2k/day; approval answer < 200 ms (p99), 99.95% availability for approvals
  (if we're down every card payment is declined).
- Writes: auths 1M / 14 h × 3 peak = 215k/h → **59.5 WPS**; events 1.1 × 59.5 × 90% → 58.9 WPS; "total 60 × 3 = 180 WPS".
- Reads: limit checks 300k / 14 h × 10 peak → 59.5 QPS; + auths and events 120 → **180 QPS**.
  (+) auth arithmetic right. Live challenges: (1) "1.1 per authorization" already averages over all authorizations, the 10%
  without events included → ×90% counts it twice (minor); (2) what is the ×3 in "60 × 3 = 180 WPS"?; (3) no conclusion drawn
  from the numbers yet. Peak ×10 for reads vs the stated ×3 (conservative, harmless).
- Fixed: events 1.1 × 60 = 66 → **126 WPS** requests; × ~3 DB writes each → **~380 write ops/s → no sharding**; "at ~1k writes/s
  we're close to sharding". Reads served by the primary, no replicas. (+) conclusion drawn, replica reflex gone.
  Live challenge (minor): where is one Postgres primary's write ceiling, roughly? (1k/s is well below it.)
- Answer: start sharding around **~10k writes/s**. (+) reasonable anchor (a few thousand to ~10k simple writes/s).

## Phase 3 — Flow, blocks, states

- Screenshot `01-high-level.png`: sticky notes (actors/actions, volumes, 126 WPS / 180 QPS, SLA, processor contract: event_id
  unique per processor, authorization_id, capture (amount may differ) / reversal / refund). Diagram: card processor →
  (auth/event) → **Card Limit API Service** → DB; employee (check limit) and admin (set limits) → API; **card event
  compensator** (worker) → DB and → processor ("verify authorization result").
  (+) proportionate: one service, one DB, one reconciliation worker. (Interviewer-private: the processor sticky omits
  "**one authorization can be captured in several parts**" and "several refunds per authorization" — relevant to the
  idempotency key. HA for 99.95% not on the canvas yet.)
- Q: cards per employee? A: **one card per employee**; the limit is per card (= per employee).
- Q: does the processor send card id or employee id? A: the authorization request carries **`card_id`** (our id for the card,
  registered with the processor), `authorization_id`, `amount`, `currency` (always EUR — single currency, keep simple),
  merchant name, timestamp. No employee id.
- Q: employees without a card? A: possible (card not issued yet), but irrelevant here — issuing is out of scope; we only
  track cards that exist, each belonging to exactly one employee.
- Q (re-ask, answered just before): currencies? A: noted it was covered — **everything in EUR**; the processor converts foreign
  payments before asking us.
- Candidate: currency column not added (all EUR); per-branch/per-employee currency later if needed. (+) scoped.
- Q (re-ask): event message + status API response? A (repeated): event = event_id (unique per processor), authorization_id,
  card_id, type capture|reversal|refund, amount, occurred_at; one authorization may have several captures and several refunds.
  Status API `GET /authorizations/{id}` → status approved|declined|captured|reversed, authorized_amount, captured_amount so far.
- Q: what does the status API show for a refunded / partially refunded authorization? A: status stays **captured**, captured_amount
  unchanged — **refunds only reach us as refund events** (second time asked about refunds vs status).
- Q: so we rely on at-least-once delivery for refunds? A: yes — the processor **retries each event until we answer 2xx** (for
  up to 3 days); duplicates possible.
- Q: p99 delay auth → capture/reversal? refunds? (to size the worker). A: most captures within **1–2 days**; **p99 ≈ 7 days**
  (hotels, car rentals). The processor **expires uncaptured authorizations after 7 days** — status becomes `reversed`, **but no
  event is sent** for that (that's the ~10% with no event). Refunds: any time up to ~90 days after capture, events only.
- Worker plan: day-centric → run once or twice a day, **first once at end of day** (off-peak); shorten the interval if we want
  limits freed faster.
  Live challenges: (1) which authorizations does each run pick, and how many status calls is that? (all pending ones vs only
  those past 7 days); (2) the timeout case raised earlier: we approved, answered late, the processor declined — the employee's
  limit stays held until tonight's run.
- Answers: (1) check only pending authorizations **older than 2 days** (most captures arrive before), and expire those **past 7
  days** (most will be reversed). (+) bounded set. (2) store our response time per authorization + another worker re-checking
  those near/over 200 ms — "but this is over-engineering". Live challenge: the request itself knows how long it has taken —
  what could it do **before committing** the hold?
- Answer: if the request is already too slow, mark it **declined ourselves** and don't take the hold (same tx) → answer
  decline. (+) deadline-aware commit — the leak can't happen except for a tiny window. Note given: compare against a budget
  with margin (e.g. ~150 ms), since the commit + network back also take time; the rare residual is covered by the worker.

- Screenshot `02-tables.png` (draft; indexes/constraints/columns to come):
  - `users(id, name, surname, type IN (admin, employee), card_id NULL)`
  - `employee_card_amounts(id, employee_id FK, card_id FK users.card_id, limit >= 0, available CHECK (>= 0 AND <= limit))`
  - `employee_payments(id = authorization_id, employee_amounts FK, amount > 0, status IN (held, captured, declined, reversed,
    refunded), held_at, last_captured_at, declined_at, reversed_at, last_refunded_at)`
  - `employee_payments_verifications(id generated by us, authorization_id, PK (id, authorization_id), result IN (error,
    approved, declined, captured, reversed), amount > 0)` — one row per status call.
  (+) invariant-holding row drawn first-class (limit + available per card); authorization as the payment row.
  Live challenges: (1) **the limit is monthly** — nothing in the counter row says which month, how does it reset?; (2) `CHECK
  available >= 0` vs a capture **larger** than the authorized amount (tips) — the capture already happened and can't be refused.
  Not raised yet (flows pending): where events are deduplicated (event_id), captured/refunded totals per payment for partial
  captures; the verifications table may be more than needed.
- Answers: (1) options: a month/year column (one row per card per month — "rows grow every month") **or a worker that resets
  available = limit on the 1st** — prefers the reset worker. (2) **remove CHECK >= 0**, available can go negative: 50 available →
  auth 50 accepted → capture 58 → −8. (+) (2) right (interviewer's €3 example meant "after the hold"; candidate's trace is the
  clean version).
  Live challenges on (1): 200k cards × 12 = 2.4M rows/yr — is that growth a problem for Postgres?; a payment authorized on
  31 March 23:59 and captured on 3 April — after the reset, which month's counter does the capture adjust?; an authorization
  committing at 00:00:00.3 while the reset runs — what does the reset's write do to it?
- Answer: 2.4M rows/yr is no problem for Postgres; **switches to one row per card per month**, so every event adjusts the counter
  of the month its authorization belongs to (payment row → FK to that card-month row). (+) revised on the cross-month case;
  the reset race disappears with it. Open: who creates the month row (first authorization of the month → upsert).
- Flow authorization (one tx): conditional `UPDATE employee_card_amounts SET available -= :amount WHERE card_id = ? AND month =
  :this_month AND available >= :amount` (row lock, index `(card_id, month)`); 0 rows → insert payment `declined` (held_at
  nullable); 1 row → insert payment `held`, answer approve.
  (+) conditional decrement on the invariant row; declined attempts recorded. Live challenges: (1) the **first authorization of
  a month** — that month's row doesn't exist yet → 0 rows → ?; (2) the deadline check designed earlier isn't in the flow; minor:
  `(card_id, month)` should be UNIQUE (one counter per card-month).
- Answers: (1) can't happen — **when an admin sets a limit, write one row per month from now to the card's expiry**. (Works;
  heavier than a lazy upsert in the auth tx — ~36–48 rows per card.) (2) **before commit, if ≥ 150 ms elapsed → give the
  amount back and mark the payment declined** (same tx). (+) deadline check placed right (a rollback of the decrement would
  be simpler but equivalent).
  Live challenge (counter on a secondary transition): admin **changes** the limit mid-month, 1,000 → 1,500 on the 15th, with
  `available` = 200 — what is `available` after the change?
- Answers: (1) set limit = 1,500 and **add the difference to available** — (+) right mechanism (relative, not reset); arithmetic
  slip: "difference 300 → 500" (should be +500 → 700) — pointed out. (2) keeps the update-back so the declined payment row
  survives (a rollback would lose the insert) — (+) fair point, accepted.
- Fixed: +500 → available 700.
- Flow capture event (one tx): (1) idempotency — `INSERT INTO events ... ON CONFLICT DO NOTHING` on **(event_id,
  authorization_id)**; conflict → drop. (+) dedupe on the event, not the authorization — partial captures safe (event_id is
  already unique per processor, the pair is fine). (2) conditional update of the payment (from held|captured → captured);
  assumption "capture = total amount, overwrite"; new `captured_amount` column; adjust available by the difference; update
  last_captured_at.
  Q: are sequential captures additions or the total? A: **each capture event carries the amount of that capture only
  (additive)**; the total so far is only in the status API's captured_amount.
- Trace (candidate): 200 available → auth 100 → (available 100, amount 100, captured 0) → capture 60: captured 60, "difference
  −40" → **releases 40 → available 140** → capture 45: captured 105, +45 over the... → available 95. (+) final number right
  (200 − 105) and additive captures handled.
  Live challenge: the remaining 40 is released at the **first partial** capture although more captures can follow — between the
  two captures the employee spends 140 → the 45 capture lands → −5, over the limit. When should the remaining hold be released?
- Answer: release the remainder only after 1–2 days (common capture time). Live challenge: captures have p99 ≈ 7 days (hotels) and
  the processor closes uncaptured authorizations at 7 days; there's already a component that looks at authorizations at 7 days.
- Fixed (3rd attempt, with the hint): keep the remaining hold until the authorization expires; the **7-day worker releases
  `amount − captured`** (captures above the authorized amount consume limit immediately). (+)

## Edge case

- Candidate stops states/workflows here; "the only missing hard one is the compensator"; asks for a hard edge case. Given:
  hotel authorization **€100**, available before 200. Day 1: capture €60 arrives (available 100, held remainder 40). Day 6: the
  processor makes a second capture **€45**, but our webhook endpoint fails and the processor keeps retrying. Day 7: the worker
  runs, calls the status API — it returns `captured, captured_amount 105`... **or** (variant) the worker called the status API a
  second **before** the second capture was made and saw `captured_amount 60`. Day 8: the €45 event finally arrives.
  Ask: counters and payment status after each step, for the variant where the worker's status read is stale; and what if the
  worker's release and the event's transaction run at the same moment.
  (Targets: worker must base the release on **our own** captured total, not the provider's snapshot, or reconcile using the
  provider's captured_amount as truth with an idempotent "set to" rather than "add"; conditional transition / row lock on the
  payment so release and capture serialize; final available must be 95.)
- Answer: Day 1 available 100, captured 60 (remainder kept for the worker). Day 6 nothing changes (our endpoint down). Day 7 the
  worker verifies with the processor, sees **captured_amount = 105** (not the stale 60 given), adjusts → "**available = −5**",
  captured 105. Day 8 not addressed. (2) concurrent: "the first winning action updates, the other does nothing".
  Live challenges: (a) the premise was a **stale** read (60) — redo with that; (b) 200 − 105 spent ⇒ available should be 95, not −5;
  (c) day 8: the €45 event arrives after the worker already used 105 — counted twice?; (d) if the losing transaction "does
  nothing", which effect is lost — the release or the €45?
- Answers: (a) "read-check-write atomically with a lock, committed reads → no stale reads from the worker" — confuses our DB
  isolation with the **external** status API's snapshot; (b) agreed final 95; (c) save event ids seen via the processor in the
  worker's tx (status API returns no event ids), or a `completed` status after the 7-day run so later events are **discarded** →
  would drop a real €45 charge; (d) not answered.
  (Interviewer-private: second round still off → answer given per the format rule.)
- **Answer given**: never apply the provider's total additively; the worker closes the authorization **once** (conditional
  `held → closed`) releasing `amount − captured_by_us` (our own event-applied total); every capture event is applied exactly once
  (event_id dedupe) and **also after closing** (it was charged — consumes limit, may go negative). Trace: 200 → auth 100 (100) →
  cap 60 (100, captured 60) → day 7 close, release 40 (140) → day 8 cap 45 (95). Concurrency: both lock the payment row; they
  serialize, both effects apply in either order (release computes from the captured total at that moment).

## Feedback

## Feedback (lite mock — coaching evidence only)

**Strong**
- Phase 1 integration questions found the risky parts unprompted: timeout = silent decline (→ a status API), refunds not in the
  status, delivery guarantees, p99 delays to size the worker.
- **Idempotency on the event** `(event_id, authorization_id)`, not the authorization — partial captures safe: the new MEDIUM item
  ("unique within what?") held on the first try.
- Invariant row drawn first (limit/available per card), conditional decrement on it; CHECK >= 0 removed for captures that can't
  be refused (case 2 lesson); deadline-aware commit (decline ourselves at ≥150 ms) after one pointer.
- Month row chosen over a reset worker once the cross-month capture and the midnight race were shown; limit change as a relative
  update (+ difference).
- Estimates driven to a conclusion; ~10k writes/s sharding anchor; no replica reflex.

**To improve**
1. **External reads vs our own state** (the edge case): treating the provider's `captured_amount` as an input to our counters, and
   "committed reads" as protection against a stale HTTP snapshot. Rule: apply each external event exactly once; never add the
   provider's totals; reconcile only to *close* something.
2. **Counters on secondary transitions** (cross-case pattern, still the main gap): releasing the remainder at the first partial
   capture (needed 3 attempts → release at 7-day close); discarding post-close captures (drops real charges); concurrency answered
   "the loser does nothing".
3. **Arithmetic slips under pressure**: +300 for 1,000 → 1,500; −5 instead of 95; events ×0.9 double-count. Trace with numbers
   *before* stating the result.
4. Minor: re-asks (currency, refund vs status twice, contract repeated) — capture the contract on the canvas, including "captures
   are additive and can be several".
