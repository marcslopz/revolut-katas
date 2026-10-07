# sd-20 — Cross-cell transfers + deposits/withdrawals (full mock, fintech)

Interviewer's running transcription — not candidate-authored. Full mock under `modes/system-design/interviewer.md` (quiet
interviewer, candidate leads). Numbered 20 (after sd-17/18/19-focused). **Goal set by the candidate: measure times** — budget
requirements 5–10 min, high level ~15, deep dive ~20, total ~40–45. Phase timestamps logged when the candidate announces them.

## Problem statement
Design a money transfer service for a digital bank that runs in several cells: users can send money to each other — including to
users whose account lives in another cell — and deposit or withdraw money from their external bank account.

(Interviewer-private: 40-minute scope. Simplest rules:
- **2 cells** (EU-West, EU-East), **all EUR** (no FX). Each user's account + balance live **only in their home cell** (residency).
- Transfer: sender → receiver identified by phone/username; a directory says which cell a user lives in (exists, global, minimal
  data: user id → cell). **Same-cell transfer: instant. Cross-cell: within a few seconds is fine**, sender sees "pending" → done.
  **Balance can never go negative.** Receiver's account may be **closed/blocked** → transfer rejected → money back to sender.
- Deposit: user sends money from their external bank to their IBAN at our bank; the **payment provider** (one, external) notifies us
  by **webhook** (at-least-once, `provider_transaction_id` unique within the provider) → credit.
- Withdrawal: user asks to send money to their external IBAN; we call the provider; result comes by webhook (success/failure,
  **failure can arrive up to 2 days later**, e.g. wrong IBAN) → refund.
- Numbers (if asked): ~10M users (60% West, 40% East); ~5M transfers/day, **~10% cross-cell**; ~500k deposits/day; ~300k
  withdrawals/day; traffic 7:00–23:00, peak ~3x (salary day ~5x for deposits); balance reads ~20M/day.
- SLA: transfer API < 1 s for same-cell; cross-cell completes < 10 s p99; 99.95%; money never lost or duplicated.
- Out of scope: FX, fraud/limits (one line), KYC, cards, notifications beyond one line, statements.
Targets: ledger per cell (append-only entries + balance with conditional decrement); cross-cell = no distributed tx → saga with
outbox: debit (hold) in A → message → credit in B (idempotent by transfer_id) → ack → finalize in A; rejection → compensation
(refund) in A; idempotency keys: client request id (per user), transfer_id across cells, provider_transaction_id; withdrawal = hold
before calling the provider, failure webhook days later → refund; states as a transition table; Phase 4: more cells / hot account
(merchant receiving many transfers) / a cell down → cross-cell transfers queue (outbox) and drain.)

## Timing
- 15:17 — problem statement given (local clock)
- 15:36 — candidate: requirements done → high level
- 15:44 — **paused** by the candidate (clock stopped; high-level diagram presented, walk-through pending)
- 15:50 — **resumed** (high level, walk-through)
- 15:51 — candidate: → deep dive
- 16:25 — infra + scaling monologue (Phase 4 opened unprompted); candidate: "running out of time"

## Phase 1 — Requirements

- Q: actors and actions? A: actors — **users** (bank customers, mobile app) and the **payment provider** (external; connects us to
  other banks). Actions, most common first: (1) users **check their balance**; (2) users **send money to another user** (same or
  other cell); (3) users **deposit** — money arrives from their external bank, the provider notifies us; (4) users **withdraw** to
  their external bank account through the provider.
- Q: how does the provider identify the user's account? A: by the user's **IBAN at our bank** (each account has one); the deposit
  webhook carries **iban, amount, provider_transaction_id (unique within the provider), sender details**. Our IBAN → user/cell lookup is
  ours to design.
- Q: more than one provider? A: **one provider** for both deposits and withdrawals.
- Q: deposit = provider calls us by HTTP? withdrawal = we call it sync or async? A: deposit: provider sends an **HTTP webhook** to us,
  **at-least-once** (retries until 2xx). Withdrawal: we call the provider's **HTTP API**, which answers immediately "**accepted**"
  (with our idempotency key, `withdrawal_id`) — the **final result (completed / failed) comes later by webhook**; a failure can arrive
  **up to 2 days later** (e.g. wrong IBAN at the receiving bank). The API call itself can time out.
- Q: "what would you do if the withdrawal result didn't come in two days?" — asked the interviewer to decide; reflected back ("your
  call"). Facts given: the provider **always** sends a final result within 2 days; it also has a **status API**
  `GET /withdrawals/{withdrawal_id}` → accepted | completed | failed | unknown (never received).
- Q: "always" even if the network is down — at-least-once? A: yes, the provider **retries every webhook until we answer 2xx, for up to 3
  days**; beyond that it gives up — the status API covers that case.
- Q: non-functional requirements? A: **2 cells** (EU-West, EU-East), **all EUR**; each user's account and balance live **only in their
  home cell**; ~**10M users** (60% West / 40% East); **~5M transfers/day, ~10% cross-cell**; ~500k deposits/day; ~300k withdrawals/day;
  ~20M balance reads/day; traffic 7:00–23:00, peak ~3x (salary day ~5x for deposits). SLA: same-cell transfer confirmed < 1 s;
  cross-cell transfer completed < 10 s p99 (sender sees pending meanwhile); **balance never negative; money never lost or duplicated**;
  99.95%.

## Phase 2 — High-level design

- (Interviewer-private, end of Phase 1: functional + NFR questions good — provider contract probed (sync/async, delivery guarantee,
  identification). **No estimates computed yet** and **no implicit requirements surfaced** (audit/ledger immutability, KYC/AML,
  residency reasons) — may come later.)
- Screenshot `01-reqs.png` (requirements canvas, presented at the start of high level): stickies for user actions, provider (incl. "check
  lost withdrawals after 2 days" + status API), numbers, SLAs, and:
  - **Writes**: transfers 5M / 16 h × 3 = **260 WPS**; deposits 500k × 5 = **43 WPS**; withdrawals 300k × 3 = **16 WPS**; biggest cell
    0.6 × (260 × 5 updates + 43 + 16) ≈ **840 write ops/s → one DB per cell, no sharding** (ceiling "a few dozen k writes/s").
  - **Reads**: 20M × 0.6 × 3 / 16 h = **625 QPS** → a read replica possible (with lag) "but at this level one write DB is enough".
  - **Implicit** (unprompted): GDPR → balances don't leave the cell; PII encrypted in transit (HTTPS/mTLS) and at rest (KMS); **KYC**; **AML**.
  (+) numbers copied right this time (all match), per-cell share applied, conclusions drawn; implicit requirements surfaced unprompted.
  Minor: "money never lost or duplicated" not on the SLA sticky; ceiling "a few dozen k writes/s" is optimistic for one Postgres
  primary (conclusion unaffected).
- Auth: provider authenticates to us with client credentials/token; users get a **JWT** from an auth service for their calls. (+) prerequisite
  step named.
- Q: same provider for both cells? A: yes, **one provider**; it **doesn't know about our cells** — it sends every webhook to the endpoint
  we configure and identifies accounts only by IBAN.
- Screenshot `02-high-level.png`: **two cells**, each = **Operations API Service + DB**; shared **Auth Service** (creds → JWT) for users West and
  East; **External Provider** (client/secret OAuth) ↔ the **West** Operations API only (deposit, withdraw, withdraw result); cross-cell
  **transfer West → East as an HTTPS call with retries** ("improvement: queue with outbox pattern").
  (+) cell-per-region skeleton, data stays in its cell, auth before actions, MVP-level. (Interviewer-private: provider wired only to
  West — deposits/withdrawals for **East** IBANs have no path, no IBAN/user → cell directory drawn; transfer arrow one direction only;
  cross-cell as a synchronous HTTPS call — what happens to the sender's money if East is down, deferred to "improvement".)

- Walk-through: user checks balance, withdraws or transfers. Withdraw: we call the provider, it accepts; if not, **retry with idempotency**;
  the provider sends the final result to our service. (Interviewer-private: hold/debit before calling the provider not mentioned yet.)

- (Interviewer-private, end of Phase 2: walk-through covered only the withdrawal; **deposit routing (provider → which cell?) and the
  cross-cell transfer path were not walked**.)

## Phase 3 — Low-level design

- **Postgres** — joins, schema stable, ACID transactions for strong consistency within a cell. Across cells: different DBs → "distributed
  transactions", no strong consistency across cells, but designed so neither region goes negative. (Mechanism not named yet — 2PC vs
  saga/compensation.)
- Tables (spoken): **accounts** (balance + available per user); **operations** (transfers, withdrawals, deposits — maybe separate tables);
  **ledger** with **two rows per payment** (double entry) → a checker verifies all operations sum to zero.
  (+) double-entry ledger + balance/available split + reconciliation, unprompted. (Interviewer-private: a cross-cell transfer has one
  leg in each cell → per-cell sum-to-zero needs an in-transit/clearing account per cell — not addressed.)
- Screenshot `03-tables.png` (per cell):
  - `accounts(id, user_id, balance >= 0, available >= 0)`
  - `transfers(id, from_account_id FK, to_account_id — "not FK since it's external", status IN (created, sent, confirmed, failed), amount > 0)`
  - `deposits(id, provider_deposit_id UNIQUE (idempotency), to_account_id FK, from_name, from_concept, amount > 0, status (received,
    succeeded, failed))`
  - `withdrawals(id, provider_withdrawal_id UNIQUE (idempotency), from_account_id FK, to_name, to_concept, amount > 0, status (created, sent,
    pending, succeeded, failed))`
  - `ledger(id, account_id — incl. **system accounts: one for provider deposits, one for withdrawals, one for transfers to/from the other
    cell**, amount ± , operation_id)`
  (+) double-entry with **system accounts incl. a cross-cell clearing account** — per-cell sum-to-zero holds; provider idempotency keys
  UNIQUE; balance/available split. (Interviewer-private: the **receiving** cell's record of an incoming transfer and its dedupe key
  (transfer_id from the other cell) isn't in the tables; no client request id for a user's double tap; `to_account_id` treated as always
  external although most transfers (90%) are same-cell; IBAN → cell routing for deposits still absent.)
- Flow deposit (one tx): webhook (provider deposit id, destination account id, amount) → `INSERT deposits ... ON CONFLICT DO NOTHING`
  (duplicate → return the first result) → `UPDATE accounts SET balance += amount, available += amount` (locks the account row) → ledger:
  credit user, debit provider system account → deposit `succeeded` → 2xx to the provider.
  (+) idempotency first, balance + double-entry in one tx, answer after commit. (Interviewer-private: the webhook carries an **IBAN**, not
  an account id, and arrives at one endpoint — an East user's deposit lands in West.)
- Interviewer probe (stated fact vs design): a deposit arrives for the IBAN of a user who lives in **East** — the provider only knows the
  endpoint you configured.
- Answer: not drawn — a **gateway in front with an IBAN → cell lookup table** routes each provider call to the right cell's service. (+)
  minimal global data (IBAN → cell), residency kept. (Not on the diagram.)
- Same global lookup used for transfers: account id → cell, to know whether the receiver is in another cell. (+)
- Flow withdrawal: tx 1 — conditional `UPDATE accounts SET available −= amount WHERE available >= amount` (row lock) + insert withdrawal
  `created` → commit; then call the provider and wait for "accepted"; timeout/failure → **retry with the same idempotency key**; webhook
  → dedupe on the withdrawal id → update status. States simplified to **created → pending → succeeded | failed**. On success: **balance
  −= amount** + two ledger rows.
  (+) hold before the external call, durable row first, idempotent retries, balance only moves on success — the money-path pattern.
  (Interviewer-private: **failed** branch — no counter given (available += amount); who retries if the process dies after the commit and
  before the call (a worker on `created` / the status API) not said.)
- Interviewer probe: two days later the webhook says **failed** (wrong IBAN).
- Answer: withdrawal → `failed` and **available += amount**. (+) right counter on the first probe (balance untouched since it only moves on
  success; no ledger rows to undo).
- Indexes: PKs, FKs, idempotency UNIQUEs; more per workload "as needed".
- Flow transfer: conditional `available −= amount WHERE available >= amount` on the sender + insert transfer. **Same cell**: lock receiver,
  balance/available += amount, ledger debit sender + credit receiver, commit. **Other cell** (global lookup): commit only the sender's hold;
  after commit **call the destination cell's API**; it locks the receiver, credits balance + available, inserts the transfer and both ledger
  rows, commits, answers success → the source adds its ledger rows and marks `confirmed`. **Saga**: if the second cell fails → compensation in
  the first (available back, transfer `failed`).
  (+) hold before the cross-cell step, saga with compensation named, per-cell ledgers via the clearing account. (Interviewer-private: same-cell
  — the **sender's balance** is never decremented (only available); lock order between two accounts (A→B and B→A at once) not stated;
  cross-cell — **dedupe key at the destination** (source retries) not stated; the source **crashing after commit, before the call** relies on
  the "improvement" outbox; and **a timeout is not a failure**.)
- Interviewer probe: West calls East, **the call times out — but East had committed the credit**. What does West do, and what are both
  balances afterwards?
- Answer: the West → East call carries an idempotency key **(source cell id, transfer_id)**; each service checks it and does nothing on
  duplicates. (+) **"unique within what?" right** — transfer ids are per cell. Follow-up: so on the timeout West… retries or compensates?
- Answer: **retry** (the dedupe at East makes it safe) → both balances right, no compensation on a timeout. (+) Compensation then only for a
  definitive rejection — not stated explicitly.

## Phase 4 — Scaling

- Infra (candidate, unprompted): auth service; **gateway + IBAN → cell lookup** for the provider; global account → cell lookup for transfers;
  cross-cell HTTP retries → **workers + outbox + message queue, at-least-once with the idempotency key**, per region; services behind LB with
  TLS termination, mTLS internal; monitoring of hosts, latency/throughput/errors; business metrics: provider error rate, error rate per
  operation, slowest operation, queue age; **DLQ for poison messages**.
- Edge cases: "already covered, could focus on one if asked — running out of time".
- Scaling (**opened unprompted**): bottleneck = writes above the ceiling → **shard by user_id** (within a cell). Availability: two AZs in one
  region now; for region outages, cells in two regions/AZs with a sync HA replica, fail over to the other. Regional growth: new countries (UK,
  US) → own cells for legal reasons, user data and balances stay in their cell. **External provider as a bottleneck** → decouple with a queue,
  **circuit breaker** (open on errors, half-open probe with rate limit, close), multiple providers / higher tier.
  (+) L → R → G progression with residency, provider degradation handled. (Interviewer-private: no number for when sharding is needed (10x →
  ~8.4k ops/s per cell); "sync HA replica across regions" again without weighing latency vs a 99.95% target; hot account not mentioned.)

## Wrap-up
