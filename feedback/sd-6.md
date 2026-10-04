# sd-6 — Payment links

Date: 2026-10-04
Problem: Design a feature that lets Revolut users create a payment link they can share, so that
anyone, whether they have Revolut or not, can pay them.

Session artifacts: `sd-sessions/sd-6/notes.md`, `sd-sessions/sd-6/01-fni.png`,
`sd-sessions/sd-6/02-high-level.png`, `sd-sessions/sd-6/03-db-tables.png`.

Context: first mock after the post-sd-5 coaching (cells, cross-cell sagas, 5-product rapid drill).
Requested at "normal interview difficulty".

## Recalibrated assessment (2026-10-04): PASS, with one technical gap

The candidate asked to recalibrate after the review: the real round grades technical design, not
fintech domain depth or legal detail (see CALIBRATION in `modes/system-design/interviewer.md`).
Below, the scores and verdict are revised on that basis. **These revised scores replace the
originals.** The original review is kept further down for the record.

| # | Category | Original | Revised | Why |
|---|---|---|---|---|
| 1 | Requirements | 3 | **4** | Good questions incl. geography, correct rates, implicit reqs raised; missing amount/single-use questions is the only real deduction |
| 2 | Session leadership | 3 | 3 | Unchanged: core probe never picked up again, no closing summary |
| 3 | Communication | 3 | 3 | Unchanged |
| 4 | HLD discipline | 3 | 3 | Unchanged |
| 5 | Component design | 2 | **3** | PCI-scope point moves to bonus; the one-service-does-everything shape still counts |
| 6 | Database design | 2 | 2 | Unchanged: no payment row, no amount — technical, not domain |
| 7 | Scalability | 4 | 4 | Unchanged (legal-basis deduction removed, scheme detail never counted) |
| 8 | Security | 2 | **3** | Principle-level answer accepted; webhook signature and authZ still missing (technical) |
| 9 | Edge cases | 3 | 3 | Chargebacks move to bonus; crash mid-flow still the gap |
| 10 | Simplicity | 3 | 3 | Unchanged |
| 11 | Time management | 3 | 3 | Unchanged |

**Verdict: PASS, with one technical point to fix.** Consistency (conditional writes, row locks,
partial unique), availability (in-region multi-AZ failover, a cell per region), data placement,
and a reasoned sync choice were all there. The single thing that matters for the real round:
**persist the payment row and its status before each external call**, so a crash mid-flow can be
resumed by a recovery worker. That's a technical durability gap, and it's the HIGH priority to
carry into the next mock.

**Bonus (not scored):** PSP-hosted card fields to stay out of PCI scope, chargebacks after
crediting, fraud/AML on card money from strangers, naming the legal basis for what crosses cells.

---

# Original review (superseded scores and verdict)

## Scores (1-5)

1. Requirements clarification: **3**. Good questions, asked in a sensible order:
   - how payment works for each kind of payer;
   - link validity;
   - rates and latency per path;
   - **where creators and payers are**, a residency question asked in Phase 1 without prompting.

   The rates were right first time (1.73 / 6.94 / 1.15 per second). The implicit requirements
   were more specific than in sd-5: PCI correctly scoped to cards, and residency with
   minimisation, down to the masked name "Pete S.".

   Deductions:
   - You never asked about **amount** (fixed or chosen by the payer), **currency**, **single-
     vs multi-use** links, refunds, or **chargebacks**. One reusable link per account with no
     amount was assumed silently.
   - AML/fraud on money arriving from unknown card payers never came up, and that is the classic
     abuse vector of this exact product.
   - You misread "85% same-country" as "85% sent in the evening". The peak figure came out right
     by coincidence.
2. Session leadership: **3**. You drove every transition. You also held your own structure when I
   probed ("let me cover edge cases my way"), which is a legitimate senior move. But:
   - the core was **scoped out** ("the ledger is outside this service's scope"), and I had to
     correct that as the stakeholder;
   - the deferred probe (crash mid-saga) was **never picked up again**;
   - the session ended without a summary or open risks.
3. Communication: **3**. You named your choices with reasons: sync for simplicity, relational
   for low traffic and joins, ACID and row locks for correctness. But you described the app
   holding the payer's balance right after I said it doesn't touch balances. Relational was
   again justified generically before ACID came up later.
4. High-level design discipline: **3**. Box-level and readable, with app detection placed before
   the form. TLS/mTLS/vault details were spoken during HLD (minor). The main issue is that the
   money movement, the core, wasn't part of the skeleton.
5. Component design: **2**.
   - One "LinkCreator API Service" does everything: link CRUD, page data, card payments,
     webhooks, Revolut payments.
   - There's no payment orchestrator, no webhook receiver, and no saga state.
   - The **card number goes through Revolut's own API** ("form input" → service, "tokenise in
     our vault"), which puts the whole service in PCI scope. The standard approach is PSP-hosted
     card fields, so Revolut only ever sees a token.
   - Revolut payer: credit the payee, then debit the payer, which is the order that needs
     reversing a credit the creator may already have spent.
6. Database design: **2**. Good:
   - a partial uniqueness rule, one active link per (user, account), which should be a partial
     UNIQUE index rather than a CHECK;
   - the 90-day CHECK;
   - lazy expiry;
   - an append-only audit table.

   But:
   - **there's no payments table and no per-payment id.** `payment_events.payment_id` is an FK to
     the link, whose PK is itself named `payment_id`;
   - **there's no amount or currency anywhere**;
   - there's no `deactivated` status, though manual deactivation was a stated requirement;
   - the index on `expired_at` doesn't serve the lookup it was meant for;
   - the event types cover only the Revolut-payer path (no card authorised / captured / failed /
     refunded / chargeback).
7. Scalability reasoning: **4**. **The best Phase 4 so far.**
   - **One cell per region, each creator's links in their own cell, failover across availability
     zones inside the region, no global primary and no global replicas**, all unprompted. This is
     the topology that failed in sd-3, sd-4 and sd-5.
   - A global `link_id → cell` directory for routing (valid; encoding the cell in the link id is
     simpler).
   - Local scaling was covered separately (CDN, horizontal API, a single writer with ACID).

   Deductions:
   - You said "GDPR and legal implications covered" without naming the basis for what does
     cross: the cross-cell payment instruction and the masked name.
   - You didn't say where card payers' data lives, since they have no cell.
   - There was no explicit local → regional → global sequence.
8. Security awareness: **2**. You covered TLS, mTLS and vault tokenisation. You did not cover:
   - PCI scope (see 5);
   - webhook authentication: a signature plus deduplication;
   - authorization: who can see or deactivate which link;
   - link abuse (phishing pages that look like Revolut, guessing link ids);
   - fraud/AML on inbound card money (stolen cards paying a link is the textbook case).
9. Edge cases and failure handling: **3**. The **lost webhook → status query → continue only on
   a definitive answer** pattern is exactly right, and it applies the saga lesson. The in-region
   failover was right too. Missing:
   - the crash mid-saga (asked, deferred, never answered);
   - async replication losing the in-flight rows on promotion;
   - duplicate or out-of-order webhooks;
   - two payers paying a single-use link at once;
   - the link expiring mid-payment;
   - **a chargeback after the creator has been credited**.
10. Simplicity: **3**. You stayed right-sized on infrastructure: no sharding, no cache, no queues
    without a reason. But the "no queues, all sync" choice removed the durable saga state the
    core needs. Here simplicity became under-engineering of the money path.
11. Time management: **3**. You reached every phase, with Phase 1 well paced. The session ended
    without a closing summary or wrap-up, and the core probe was left open.

## A. Assessment: BORDERLINE

This mock **fixes the biggest recurring failure**: data residency was right from Phase 1 to
Phase 4, unprompted, three mocks after it first failed. That's a real change, not a coincidence.

But the prompt's core, **moving money into the creator's account exactly once**, was again not
designed:

- no payment entity;
- a synchronous saga with no durable state;
- credit before debit;
- the crash question left unanswered.

That's the third mock where the money path is the gap (sd-3, sd-5, sd-6). It's now the single
biggest risk.

## B. Three strongest things

1. **Residency by default.** A cell per region, home-cell ownership, failover inside the region,
   only minimal data crossing (masked name), and it was stated in Phase 1 requirements as well as
   in Phase 4. Combined with the directory for routing, this is the answer the last three
   reviews asked for.
2. **Phase 1 discipline.** Good stakeholder questions, including geography. Rates right first
   time. Implicit requirements that were specific to the domain, with PCI correctly limited to
   cards this time.
3. **Reconciliation and concurrency vocabulary used correctly.** Status query on a lost webhook,
   acting only on definitive answers, conditional INSERT/UPDATE with SELECT FOR UPDATE, and a
   partial uniqueness rule for one active link.

## C. Three biggest risks for the real interview

1. **The money path is still undesigned** (sd-3, sd-5, sd-6). There's no row that represents
   *a payment*, so there's nothing to deduplicate, resume or reconcile against. The synchronous
   saga keeps its state only in memory. Fix the habit, not the instance: **every money-moving
   design starts with the payment entity and its state machine**, and asks "where is the saga
   state durable?" before choosing sync or async.
2. **Card-domain risk was invisible.** PAN flowing through your own service (PCI scope);
   **chargebacks** up to ~120 days after the creator was credited (and may have withdrawn the
   money); **fraud/AML** on card money from strangers. For a product that takes money from anyone
   on the internet, these are the first questions a Revolut interviewer asks.
3. **Silent product assumptions, plus scoping out the core.** "One link per account, no amount"
   was never checked with the stakeholder, and "the ledger is out of scope" removed the hardest
   part. Check scope assumptions out loud before building on them.

## D. Architectural gaps or inconsistencies

- The link PK is named `payment_id`, and `payment_events.payment_id` points to the link, so link
  and payment are conflated.
- The audit log was described as storing amount and currency, but the schema has neither.
- Manual deactivation was required, but the status set is only `active`/`expired`.
- "The app holds the payer's balance" came right after the stakeholder said the app writes
  nothing. It was corrected to "our service calls both ledgers", but the order (credit the
  payee first) was never revisited.
- "No queues needed" vs the checker worker "compensating sagas in the middle of execution": the
  worker needs saga state that the sync design never writes.
- `from_cell_id` FK on events: card payers have no cell.

## E. Missing non-functional considerations

- Webhook security (HMAC signature + timestamp, dedupe by provider event id).
- Fraud/AML screening of inbound card payments; velocity limits per link.
- Chargeback/dispute handling and its effect on the creator's balance.
- Link abuse: unguessable ids, rate limiting on lookups, phishing awareness (a Revolut-branded
  pay page is an attractive clone target).
- AuthZ: only the owner lists or deactivates their links.
- Observability for the money path: stuck sagas, payments pending past N minutes, provider error
  rate.
- The legal basis for what crosses cells, and where non-customer payer data lives.

## F. Over/under-engineering

- **Under:** the money path (no payment entity, no durable saga state), PCI scope handling, and
  the fraud and chargeback model.
- **Right-sized:** no sharding, no cache, CDN for static assets, and the cell topology.
- **Minor over:** an "auth" service for Apple/Google Pay. They're wallet payment tokens handled by
  the browser or the PSP SDK, not OAuth logins.

## G. What a strong Revolut candidate might have covered

- Early stakeholder questions: "Fixed or open amount? One payment or many? Which currency? What
  about refunds and chargebacks?"
- Naming the core right after requirements: *"the hard part is crediting the creator exactly once
  from asynchronous, possibly duplicated confirmations, and dealing with money that can come back
  (chargebacks)"*.
- A `payments` entity: `payment_id` (from a server-side checkout session, which doubles as the
  idempotency key), `link_id`, amount, currency, method, `psp_reference UNIQUE`, and a status
  state machine (`created → authorised → captured → credited | failed | refunded | charged_back`).
- PSP-hosted card fields, so Revolut never sees the card number and its PCI scope stays minimal.
- Card path: webhook (signed, deduplicated) → payment captured → **one** idempotent credit to the
  creator, possibly with a short availability hold or fraud screening on first-time payers.
- Revolut-payer path: orchestrated saga with a **persisted saga row plus an outbox**: hold the
  payer's funds, credit the creator (cross-cell, idempotent by `payment_id`), then capture the
  hold. Compensation = **release the hold**, never reverse a credit.
- The link id encodes the cell (`eu_…`, `uk_…`), so routing needs no global lookup on the hot path.

## H. Topics to practise before the next mock

1. **"Payment entity first"**: for any money-moving prompt, sketch the payment row and its state
   machine *before* the HLD boxes. 5-minute reps across 4–5 products.
2. **Saga state durability**: for sync orchestration, say where the saga row is written before
   the first external call, and what the recovery worker scans. Always reserve or debit before
   crediting.
3. **The card-acceptance domain**: PSP-hosted fields / PCI scope, capture vs authorisation,
   chargebacks and their time window, fraud screening for card-not-present payments.
4. **The legal-basis sentence** for what crosses cells (still asserted, not named): adequacy
   EU↔UK, contract necessity for the payment instruction, legitimate interest for fraud.

## I. A better architecture (post-mock only, brief)

```
Payer browser ── CDN (static page) ── link id encodes cell → Payment-link API (creator's cell)
  card:    PSP hosted fields → token → API creates payments(row, status=created, payment_id)
           → PSP charge(idempotency=payment_id) → signed webhook → dedupe(psp_event_id)
           → tx: payments=captured + outbox(credit_creator) → ledger credit (idempotent by payment_id)
           → later: chargeback webhook → debit creator / reserve, notify
  Revolut: app → API: tx payments(created) + saga_state + outbox
           → payer's cell ledger: HOLD (idempotent) → creator's cell ledger: CREDIT (idempotent)
           → payer's cell: CAPTURE hold → payments=completed
           failure before credit → RELEASE hold (never reverse a credit)
  Recovery worker: scans payments/saga rows stuck in a state > N min → status query → continue.
Per cell: links, payments, saga state, events, minimal payer data (masked name, card brand/last4
from the PSP). Global: nothing with personal data; link ids carry the cell.
```
