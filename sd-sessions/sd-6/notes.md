# sd-6 — Payment links

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design a feature that lets Revolut users create a payment link they can share, so that anyone —
whether they have Revolut or not — can pay them.

(Interviewer-private: normal interview difficulty, per post-sd-5 coaching request. Varies from
sd-1 P2P / sd-2 hotel / sd-3 card auth / sd-4 notifications / sd-5 scheduled payments, and from
the 2026-10-04 drill products (KYC, vault, cashback, trading, fraud). Core hard part: crediting the
link owner exactly once from at-least-once, possibly duplicated/out-of-order payment confirmations
(external card payer via a PSP/acquirer webhook; Revolut payer via internal transfer), with link
semantics (single-use vs multi-use, fixed vs open amount, expiry) under concurrent payers. Tests
HIGH items: exactly-once on the money path (natural idempotency key, webhook dedupe, outbox, no
check-then-act on "link already paid"), data residency (payer anywhere in the world, owner in home
cell; what payer data is stored where), plus core-first, canvas drift, legal-basis recall, PCI
scope (card data must stay with the PSP — hosted payment page). Implicit reqs available: PCI DSS
(external card payers), AML/fraud on inbound funds from unknown payers, chargebacks on card-funded
payments, payer PII (GDPR) for non-customers, link enumeration/phishing abuse, currency of the link
vs payer's card currency, refunds.)

## Phase 1 — Requirements

### Stated by interviewer (stakeholder answers)
- Q: how does the link work / payment mechanisms? A: link opens a Revolut-hosted web page.
  - Non-Revolut payer: pays by **card** (debit/credit) on that page. Card processing goes through
    an **external card processor (PSP/acquirer)** Revolut works with. Apple/Google Pay
    nice-to-have; pay-by-bank (open banking) out of scope.
  - Revolut payer: link opens the **Revolut app** → pays from their balance (internal transfer).
- Candidate's first question already went for the payer-side mechanism (good: actors/flows first,
  no schema).
- Q: link validity? A: creator chooses expiry; default 30 days, max 90 days; creator can also
  deactivate it manually at any time. (Link create = API call by the Revolut user — candidate.)
- Candidate: "we need a payment_links table with expiration_date (default now+30d, up to 90d)".
  Interviewer-private: first table mention while still in requirements (sd-5 pattern), but a
  single line — not redirected. Watch.
- Candidate's payer-side UX flow: link → Revolut web page → if mobile + app installed → redirect to
  app (deep link); else a form: enter card, or "authenticate via Google/Apple OAuth to use Google
  Pay / Apple Pay".
  Interviewer-private: Apple/Google Pay aren't OAuth logins — they're wallet payment tokens
  (browser Payment Request API / PSP SDK); imprecise but on a nice-to-have path, not probed.
  Still functional, still in Phase 1. Not yet asked: amount fixed vs open, single vs multi-use,
  currency, refunds, what the creator sees.

### Candidate's functional list
1. Create payment link: input user_id, account_id → "upserts" link in DB → returns URL containing
   payment_link_id.
2. Open link: fetch by payment_link_id → show web form (non-Revolut) or redirect to app.
Interviewer-private: no amount/currency/description in create; no "pay" operation listed as such
(the actual money movement); no deactivate (stated by me earlier), no list/view received payments,
no single- vs multi-use, no refunds. "upsert" on create — odd (create is an insert). Watch.

### Non-functional — stakeholder answers (asked req/s + p99 for create and payer paths)
Gave business numbers (candidate derives rates):
- Links created: ~150k/day.
- Link opens: ~600k/day.
- Payments made through links: ~100k/day; ~60% by card from non-Revolut payers, ~40% by
  Revolut users in-app.
- Traffic is fairly flat through the day; evenings ~3x the daily average.
- Latency: create link p99 < 500 ms; link page load p99 < 1 s; a card payment can take 1–3 s at
  the card processor — payer should see the final result within ~5 s.
- Q: where are creators and payers? A: creators = Revolut customers of the **EU and UK** entities
  (launch in both at once). Payers = **anywhere**: card payers with cards issued in any country;
  Revolut payers from any Revolut entity (EU, UK, US, …). ~85% of payments are same-country as the
  creator, ~15% cross-border.
  Interviewer-private: (+) asked about geography in Phase 1 — residency-relevant question, unprompted.
  Note: two cells from day one — no "single-region MVP" this time.

### Screenshot 01-fni.png (copied from ~/Downloads/fni.png) — candidate's F-N-I stickies
- Functional: create_payment_link(user_id, account_id) → upserts link, returns URL to link id;
  payment_link_host/<link_id> → web / app redirection. (Still no amount/currency/pay/deactivate.)
- Non-functional: create 150k/day = 1.73 WPS ✔ p99 < 500 ms; page load 600k/day = 6.94 QPS ✔
  p99 < 1 s; payments 100k/day = 1.15/s ✔ (60k card = 0.69/s, 40k Revolut = 0.45/s ✔).
  Evening peak: "85% is sent at evening" → 100k/3h ×3 → ~3.47 payments/s peak.
  Interviewer-private: **misread** — 85% was *same-country* share, not "sent in the evening"; I said
  evenings ≈ 3x the average. The result (~3.5/s ≈ 3x of 1.16/s) happens to equal the stated 3x,
  but the reasoning mixed two facts. No explicit comparison sentence ("tiny vs one primary") —
  numbers obviously small, low stakes.
- Implicit (unprompted, sd-5 → sd-6 improvement in specificity):
  - payment can fail on payer's insufficient balance;
  - PCI: "if we need to store payer's card, always tokens" — (+) PCI correctly scoped to cards this
    time; (−) better answer is "we never see the card: PSP-hosted fields/page", watch in LLD;
  - **residency stated in Phase 1**: user info always in its cell (EU/UK), payer info in payer's
    cell; only minimal info travels (amount, currency, payment_id, idempotency key, masked name
    "Pete S."). (+) HIGH-priority item surfaced first, in requirements, with minimisation.
  - Not raised: AML/fraud on money from unknown payers, chargebacks on card-funded payments,
    phishing/link abuse, GDPR for non-customer payer data (where do card payers' data live? they
    have no cell).

## Phase 2 — High-level design

### Screenshot 02-high-level.png + spoken workflows
Diagram: Revolut link creator → LinkCreator API Service → DB; service → Card Payment Provider;
Payer → CDN (static page) → "form input" → LinkCreator API; CDN → redirect → Revolut app backend
service → LinkCreator API; CDN ↔ Google/Apple Pay Auth Service ("auth", "JWT token").
Workflows (spoken):
1. Creator calls LinkCreator for a chosen account_id; if an active link already exists for
   (user_id, account_id) it returns it, else creates one → URL with unique link_id.
   Interviewer-private: implies **one reusable link per account with no amount** — a "pay me"
   handle where the payer picks the amount. Product assumption never stated or checked with the
   stakeholder.
2. Payer opens URL → static page from CDN; script detects mobile + app → open app; else card form
   or Google/Apple Pay "auth".
3. Card payer: card data sent over TLS to the gateway, mTLS internally; tokenise in "our vault
   whenever we need to store card info"; asynchronously call card provider; provider webhook →
   API accept/reject → inform payer → audit log event (minimal payer info, amount, time, currency,
   settled/rejected). **"The ledger transaction / creator balance is not owned by this service —
   out of scope."**
4. Revolut payer: either (a) "we own the transfer": two ledger rows in our cell's ledger (debit
   cell X, credit our user), or (b) call a Revolut payment service and wait for a webhook like the
   external provider. Edge cases deferred to later.
Interviewer-private:
- (−−) **Core scoped out**: crediting the creator exactly once is the heart of the prompt. Corrected
  as a stakeholder (scope answer, not a design hint): crediting the creator is in scope.
- (−) PAN flows through Revolut's own API ("form input" → LinkCreator) → Revolut's whole service in
  PCI scope; alternative (PSP-hosted fields / page, Revolut only sees a token) not considered.
- (−) One "LinkCreator API Service" does link CRUD, page data, card payments, webhooks, Revolut
  payments → monolith-in-boxes; no webhook receiver, no queue/outbox (fine for skeleton level).
- (−) Revolut payer option (a) "debit from cell X" in "our cell's ledger" — payer may be in another
  cell; cross-cell mechanics not addressed yet. Two options left open, no choice made.
- HLD level: boxes mostly fine; TLS/mTLS/vault details spoken early (minor; no redirect).
- (+) Pre-flow: app detection before form; async card call with webhook.
- Google/Apple Pay still modelled as OAuth/JWT auth (imprecise, nice-to-have path).
- Q (x2): who owns the payer's ledger write / does the app hold the payer's ledger? A: each
  entity's core ledger service (in its cell) owns its customers' balances, internal API for
  debits/credits in that entity; the app is only a client and writes nothing; which component asks
  the payer's ledger to debit, and when, is the candidate's design.
- Candidate's Revolut-payer saga: "the Revolut app holds the payer's balance when they accept";
  our API calls the **payee's ledger** to credit, then responds to the payer's app "to write their
  ledger there too"; any failing step → compensate holds/entries.
  Interviewer-private: (1) contradicts the stakeholder fact just given (app doesn't touch
  balances) — restated the fact once. (2) Order = credit payee BEFORE the payer's debit is final →
  if the debit fails, compensation means reversing a credit the creator may already have spent
  (exactly the 2026-10-03 coaching lesson: compensate a credit = bad; debit/reserve first).
  Not raised — leave for LLD. (+) Saga + hold + compensation vocabulary present.
- Corrected: "our service will call both ledgers" (payer's entity ledger + creator's entity
  ledger). Orchestrated saga owned by the payment-link service. Order/compensation not yet stated.

## Phase 3 — Low-level design

- Relational DB: traffic low (no sharding), fixed schema, wants JOINs. (Same generic justification
  as sd-5; transactions/constraints — the design-specific reason — not given.)

### Screenshot 03-db-tables.png (copied from ~/Downloads/db_tables.png)
payment_links: payment_id UUID PK, user_id FK, account_id FK, created_at, expired_at NN,
CHECK(expired_at − created_at ≤ 90 days), status IN (active, expired); "index expired_at to check
the upsert quickly"; "CHECK (UNIQUE account_id, user_id WHEN status = active)"; links expired lazily
on upsert and when a payer uses one after expiry.
payment_events (append-only audit): payment_id UUID FK, user_id FK, account_id FK, from_cell_id FK,
pseudonised_name TEXT NN, created_at, event_type IN (payer_accepted, payer_ledger_confirmed,
payee_ledger_confirmed, payer_ledger_rejected, payee_ledger_rejected).
Interviewer-private:
- (+) Partial uniqueness "one active link per (user, account)" — right instinct (should be a partial
  UNIQUE index, not a CHECK). (+) 90-day CHECK. (+) Lazy expiry. (+) Append-only audit table.
- (−−) **No payments table / no per-payment id.** payment_events.payment_id is an FK to the link
  PK (which is itself named payment_id) → every payment through a multi-payment link shares one id;
  there's no row per payment attempt, no idempotency key, no status per payment. The core (credit
  exactly once per payment) has no structural home.
- (−) **No amount or currency anywhere** (spoken audit log included them).
- (−) No 'deactivated' status despite manual deactivation being a stated requirement.
- (−) Index on expired_at doesn't serve the upsert lookup (by user/account); the partial unique
  index does.
- (−) Event types cover only the Revolut-payer saga; nothing for card payments (PSP authorised /
  captured / failed / refunded / chargeback). from_cell_id FK — card payers have no cell.
- Naming: link PK called payment_id → confusion between link and payment (model-drift risk).
- Infra choice: all sync; async parts (card provider) via webhooks → "no queues, to keep it
  simple". Alternative named: producer/consumer + outbox, callbacks as messages back. Chose sync.
  Interviewer-private: simplicity instinct (+), but a sync orchestrated saga over two ledgers with
  no durable saga state = crash mid-saga loses track of money. Combined with no payments table →
  nothing records "payer debited, payee not yet credited".
- **Probe asked (core, scenario):** service debited the payer's ledger, crashes before calling the
  creator's ledger, restarts — what does it know, what state is the money in?
- Candidate deferred the probe: "haven't covered edge cases yet, let me anticipate them" — chose
  not to read it. (Session-leadership move; legitimate. Probe still open — check whether their own
  edge-case pass covers crash mid-saga.)

### Infra / deployment / local scaling (candidate)
- Two deployables: API service + static files (CDN), independent.
- Scaling: CDN config for reads; API horizontal — correctness via DB ACID with a single writer,
  READ COMMITTED + row locking: conditional INSERT/UPDATE in one txn, SELECT FOR UPDATE for
  read-check-write. (+) concurrency mechanism named precisely; first time ACID is used as the
  relational justification (late, but there).
- Canary deploys watching latency/errors/throughput; DB monitoring for read replicas; autoscale API
  on throughput + latency.
- Interviewer-private: all local scaling; ACID only covers writes inside OUR DB — the two ledgers
  are separate systems (other cells), so the saga problem is untouched by this. "escalation" =
  scaling (dictation/false friend).

### Edge cases (candidate-led)
1. Card payment succeeded at the provider but the webhook is lost → a checker worker finds payments
   without a confirmed (accepted/rejected) webhook after the usual time → queries the provider by
   payment_id → on a definitive answer, continues the saga.
   (+) Correct pattern (status query / reconciliation on missing callback, act only on definitive
   answer). (−) Needs a per-payment row with a pending status to find "unconfirmed payments" — the
   schema has no payments table (events keyed by link id).
2. Cell's write DB down → can't check link status, create links, write payment_events → ≥2
   availability zones in the same cell's region, promote a replica. The checker worker must also
   compensate/complete sagas that were mid-execution on the old primary after recovery.
   (+) Failover kept **inside the cell/region** (AZs) — residency-compatible by default, unlike
   sd-3/4/5. (−) Async replication can lose the last writes on promotion → the in-flight saga rows
   the checker relies on may not exist on the new primary; and with sync saga + no saga-state row
   written *before* calling the ledgers, there's nothing to resume from. Ties back to the open probe.

## Phase 4 — Scaling / multi-region (candidate-led transition)
- Growth to US: a new **US cell** (≥2 AZs) with the full stack (API, DB, US card provider
  connection, checker worker). Each creator's links live **in their own cell**. Ledger calls may
  cross regions as before (payer already global). Region/AZ down → fail over to the other AZ **in
  the same region**. ⇒ "we don't move user data cross-region (GDPR and other legal implications
  covered)".
Interviewer-private:
- (++) **Residency topology correct and unprompted**: cell per region, home-cell ownership, in-region
  failover, no global replicas/primary. Reverses the sd-3/4/5 pattern. Consistent with the Phase 1
  sticky (residency stated in requirements too).
- (−) Legal basis for what *does* cross (cross-cell payment instruction, masked name) not named —
  "covered" asserted, not justified (adequacy EU↔UK, contract necessity, UK/EU→US).
- (−) No explicit local → regional → global staging (local scaling was covered earlier, separately).
- (−) Card payers have no cell — where their (minimal) data lives isn't stated.
- (−) Request routing not addressed: a static page on a global CDN must know which cell owns
  link_id. **Probe asked.**
- Answer: global directory payment_link_id → cell_id. Valid (link ids aren't PII).
  Interviewer-private: simpler alternative not considered — encode the cell in the link id / URL
  (e.g. prefix or subdomain), which removes a global lookup dependency on the payer path. The
  directory's availability/consistency at link creation (written before the URL is shared?) not
  discussed.
