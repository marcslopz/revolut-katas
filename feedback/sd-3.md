# sd-3 — Card transaction authorization (issuer side)

Date: 2026-10-01
Problem: Design the system that decides, in real time, whether to approve or decline a payment when
a customer uses their Revolut card at a merchant.

Session artifacts: `sd-sessions/sd-3/notes.md`, `sd-sessions/sd-3/01-mvp.png`.

## Scores (1-5)

1. Requirements clarification: **4** — the best requirements phase so far. Clean functional pass
   (card valid, funds, fraud, merchant identity), asked about volume, and **surfaced three implicit
   requirements unprompted**: audit/long-term retention, PCI, and GDPR (on the canvas). That breaks
   the recurring sd-1/sd-2 pattern of zero implicit requirements. Deductions: the QPS division was
   off by ~55x (30M/86,400 → "19.2k") and drove an immediate "we need sharding" conclusion before
   one nudge fixed it. The latency budget was asked only after announcing the drawing. The
   availability target, network retries/duplicates, multi-currency and reversals were never asked.
   One already-answered question was asked again ("is it the network or the end user?").
2. Session leadership: **3** — clear progress. You drove every transition yourself: requirements →
   drawing → DB → replicas/cache → archiver → deployment → security → edge cases/monitoring →
   multi-region. This is the first mock to reach Phase 4, and you covered Karim's full list
   (deployment, observability, maintenance) without being asked. Two things hold the score at 3:
   (a) you closed the same way as sd-2, handing control back with "any questions or extra
   improvements you want to make?" instead of naming your own open items, and (b) you deferred the
   fraud fallback with "it's a business decision, not a technical question." A lead engineer is
   expected to recommend there.
3. Communication: **3** — most decisions came with a reason attached: single Postgres (volume fits,
   ACID over distributed consistency), no cache (traffic doesn't justify it), read replica for the
   archiver, no FK so invalid card ids can still be audited, and TLS termination at the LB for
   certificate management. That's strong. The weak spot was the fraud fallback. You first deferred
   it, then said "decline everything," then flipped to "approve everything" after one pushback,
   and opened that answer with "that's why I'm not a business person." Lay out both sides before
   picking, rather than swinging.
4. High-level design discipline: **4** — box-level and MVP-shaped, with no engines named on the
   diagram. Minor: S3/Glacier and hot/cold tiering came up in Phase 1, and you jumped from the
   screenshot to the DB without walking the end-to-end flow once.
5. Component design: **2** — the biggest weakness of the mock. The HLD had **no component and no
   data that enforced the two invariants written on your own sticky note** (card active, sufficient
   balance). The only DB arrow was "write approval/rejection." A cards table appeared only after
   I asked where that data lived. The order of steps (dedupe → card check → balance → fraud →
   decide → persist → respond) was never made explicit. The auth flow was first modelled as an
   end-user login with a JWT, which you caught yourself. Audit records and operational data share
   one DB.
6. Database design: **3** — real schema, indexes justified by access pattern (unique idempotency
   key, created_at for the archiver), Postgres justified, read replica justified. The deliberate
   no-FK decision for auditing invalid cards was a nice touch. Gaps: `transactions` lacked
   card_id, fraud_score and decline reason, all of which you had listed as audit fields minutes
   earlier. The balance sat on the card rather than the account. Card status omitted
   frozen/cancelled. **No concurrency control for the reservation (balance decrement) was ever
   stated.** There was no partitioning, and archiving meant row-by-row DELETEs of ~30M rows/day on
   the primary. The source of the idempotency key was never stated.
7. Scalability reasoning: **3** — you reached the phase and justified per-region stacks by
   latency, with cross-region RTT eating the 150 ms budget. After learning that networks route by
   BIN, you moved to "each region owns its BINs," and region failover used a priority list plus
   majority quorum to avoid split-brain, which was a genuinely good instinct. Gaps: you skipped the
   "local" step (what breaks first in one region). Cost was never discussed. Async replication lag
   at failover means recent reservations can be lost, giving a double-spend window. Replicating
   every EU cardholder's balance to every region contradicts the GDPR point you raised yourself.
8. Security awareness: **3** — much broader than sd-2's JWT-only answer: PCI, encryption at rest,
   TLS, credential rotation, and encrypting internal traffic. But there were several factual
   imprecisions a fintech interviewer will notice:
   - You claimed transparent disk encryption keeps data safe "if they break our DB." It doesn't
     protect against anyone with query access.
   - You initially accepted plaintext card data on the internal network.
   - Your fix was internal TLS *without certificate validation*, which gives no protection against
     an active MITM.
   - No PAN tokenization or vault, no key management, and username/password auth for the card
     network instead of mTLS or dedicated links.
9. Edge cases and failure-handling: **3** — strong on the archiver: after one crash-scenario probe
   you moved to atomic delete+outbox. The circuit breaker had half-open gradual recovery, and the
   region failover was quorum-aware. But the **critical auth path's failure modes were never raised
   by you**:
   - two concurrent authorizations on the same card
   - the Postgres primary dying in-region
   - the network retrying a request we already approved
   - a crash after decrementing the balance but before responding to the network

   The 1 s fraud timeout against a 150 ms p99 was on your sticky note, in the edge-case answer, and
   in the breaker answer, and was never reconciled. Monitoring covered infrastructure only, with no
   business metrics (approval rate, fallback rate, responses near the network's 2 s limit).
10. Simplicity: **3** — good restraint on cache and sharding once the numbers were right. But the
    most elaborate mechanism of the session was a 4-stage outbox → relay → queue → worker → DLQ
    pipeline for a **daily, off-critical-path archival job**. Daily partitions plus detach/export
    would do it with almost no moving parts. Meanwhile the real-time reservation, the actual hard
    part of this prompt, got no mechanism at all.
11. Time management: **3** — the first mock to reach every phase with zero pacing redirects, which
    is real progress on the sd-2 issue (ending inside Phase 3). The time was badly *proportioned*,
    though: the archiver got more depth than the authorization decision itself.

## A. Assessment: BORDERLINE (trending up)

Breadth is now there: every phase was reached, implicit requirements were surfaced, and Karim's
checklist was covered unprompted. That fixes the two loudest sd-2 problems. What keeps this
BORDERLINE rather than PASS is depth on the core: for a card-authorization prompt, the interviewer's
central question is "how do you safely approve-and-reserve money in under 150 ms when two payments
on the same card arrive at once and dependencies are flaky?" That was never designed. A Revolut
senior engineer would probably mark component design and failure handling on the hot path as the
deciding gap.

## B. Three strongest things

1. **Three unprompted implicit requirements** (audit/7-year retention, PCI, GDPR). This is the
   first mock-confirmed break of a weakness that recurred in sd-1 and sd-2. One mock isn't
   RESOLVED yet (see [[coaching-drill-vs-mock-evidence]]), but it's a strong signal.
2. **End-to-end ownership of the session.** You set every phase transition yourself, reached
   scaling, and covered deployment (independent canaries), observability, maintenance and
   security on your own initiative.
3. **Fast, clean self-correction under a single probe:** the QPS arithmetic, the archiver crash
   window (delete-then-write → atomic delete+outbox), the region-routing model once BIN routing
   was known, and the fallback-region data ownership (→ replicated cards + quorum promotion). Each
   needed exactly one question.

## C. Three biggest risks for the real interview

1. **Not finding and designing the prompt's core first.** You spread depth evenly across a checklist
   (DB, deployment, security, monitoring) instead of asking "what's the one hard thing here?" and
   designing it fully before peripheral components. For a fintech prompt, the core is almost always
   a money invariant under concurrency and partial failure. Ironically, that's your strongest Build
   It area (see [[weak_areas_backend_concurrency]]), and it never got airtime.
2. **Closing by handing the session back, and deferring judgment calls.** "Any questions or extra
   improvements you want to make?" (the sd-2 pattern again) and "it's a business decision, not
   technical." Karim's email grades exactly this. Close by listing your own remaining gaps and
   recommend with trade-offs when the business side is unclear.
3. **Security imprecision on a fintech prompt.** TDE ≠ protection against DB access; TLS without
   validation ≠ secure; no tokenization of card data. These are the topics a Revolut interviewer
   knows cold, and a confident wrong statement costs more than a gap.

## D. Architectural gaps or inconsistencies

- Canvas sticky note still says "347/s avg, 2K/s peak → **need sharding**" after you verbally
  concluded single DB, no sharding.
- Diagram still says "API Service (check JWT)" after you dropped JWT for server-to-server.
- Fraud timeout of 1 s against a 150 ms p99 end-to-end budget, never reconciled. Even with the
  breaker, every call before it trips costs up to 1 s.
- Balance lives on `cards`, but the stakeholder said card → customer + account. Physical + virtual
  cards on one account would have separate balances.
- `transactions` schema dropped card_id, fraud_score and reason, all of which you'd defined as
  required audit fields.
- "The archiver reads from the replica," but marking/deleting rows happens on the primary, in
  contention with the auth path.
- During failover: "transactions are independent, it doesn't matter which server decides." They
  aren't independent, because they share the card's balance (resolved after a probe).
- Replicating cards/balances to all regions vs. your own GDPR/data-residency point.
- Decrementing `balance` directly at auth time conflates *available* vs *ledger* balance. The
  settlement system would then need to know not to debit again, and expired-hold release has no
  stated trigger.

## E. Missing non-functional considerations

- Concurrency control on the reservation (conditional `UPDATE … SET balance = balance - :amt WHERE
  balance >= :amt`, or row lock) — never stated.
- Idempotency source: the network's transaction ID is the natural dedupe key for network retries,
  but a separate `idempotency_key` was introduced without saying who generates it.
- In-region DB failover (synchronous standby) and the availability target were never discussed.
- Recovery point (RPO) on cross-region promotion was not addressed: lost reservations mean
  double-spend.
- Business-level monitoring and alerting: approval/decline rate, fraud-fallback rate, p99 vs the
  network's 2 s limit, and hold-release backlog.
- Key management / KMS, PAN tokenization, mTLS with the network.

## F. Over/under-engineering

- **Over:** the archival pipeline (outbox + relay + queue + workers + DLQ) for a daily batch.
  Time-partitioned tables (daily/monthly) with detach → export to object storage → drop cover the
  same need with no message infrastructure, and avoid 30M DELETEs/day on the primary.
- **Under:** the authorization hot path. You had no explicit sequence, no reservation mechanism,
  no concurrency control and no latency budget breakdown.
- **Right-sized:** no cache, no sharding (once the arithmetic was fixed), single Postgres.

## G. What a strong Revolut candidate might have covered

- A **latency budget breakdown** inside 150 ms: dedupe lookup + card/account read + fraud call (run
  in parallel with the card lookup, with a ~60-80 ms timeout, not 1 s) + reservation write. The
  timeout is derived from the budget.
- **Holds as first-class records:** an `authorizations` (holds) row with expiry, where available
  balance = ledger balance − active holds. Settlement then *captures* the hold instead of debiting
  again, and an expiry sweeper releases unused holds.
- **Network-level idempotency:** dedupe on the network transaction ID. A retry returns the original
  decision without re-reserving.
- **Response-before-or-after-commit reasoning:** commit the hold and decision, then respond. If we
  crash after commit but before responding, the network retry hits the dedupe and gets the same
  answer.
- **Stand-in rules when fraud is down:** approve under an amount cap, decline high-risk MCC/country
  combinations, and cap total exposure while the breaker is open. This is a recommendation with
  trade-offs, not "business decides."
- **Audit as an append-only stream:** CDC or outbox into an immutable store, decoupled from the
  operational DB so that "never lose an audit record" doesn't depend on archival jobs.
- **Local → regional → global:** first an in-region HA primary with a synchronous standby across
  AZs. Then per-region BIN ownership. Then cross-region failover with explicit RPO and cost
  trade-offs.
- Questions for the interviewer at the end. "Nothing" is a missed opportunity in the real thing.

## H. Topics to practice before the next mock

1. **"Find the core first" opener:** after requirements, say out loud "the hardest part of this
   system is X," and design X end-to-end before any peripheral component. Drill on 3-4 fintech
   prompts in 2-minute bursts.
2. **Hot-path sequencing + latency budget:** write the numbered pre-flow and a millisecond budget
   for each step, and derive timeouts from it.
3. **Security fundamentals for card data:** TDE vs app-level/field encryption vs tokenization;
   mTLS; what PCI DSS actually requires in transit and at rest.
4. **Degraded-mode decisions as recommendations:** for any "dependency is down" question, give
   both sides, then a middle ground, then a recommendation. Never "that's business."
5. **Close-out script:** "Here's what I'd do with more time: A, B, C." Also have 2 questions ready
   for the interviewer.
6. Mental arithmetic anchor: 1 day ≈ 86,400 s ≈ 10^5 s, so 1M/day ≈ 12/s.

## I. A better architecture (post-mock only)

Hot path (single region, HA Postgres primary + sync standby across AZs):

1. Network → (mTLS / dedicated link) → gateway → Auth API.
2. Dedupe: look up `authorizations` by `network_txn_id` (UNIQUE). If it exists, return the stored
   decision.
3. In parallel: load card + account (status, available balance) **and** call fraud scoring with a
   ~60-80 ms timeout behind a circuit breaker.
4. Decide. If fraud is unavailable, apply stand-in rules (amount cap, MCC/country blocklist,
   exposure cap).
5. One DB transaction: conditional reservation
   `UPDATE accounts SET available = available - :amt WHERE id = :acct AND available >= :amt`
   (zero rows → decline insufficient funds) + insert the `authorizations` row (decision, reason,
   score, hold expiry) + insert an outbox row for audit.
6. Commit → respond to the network.

Off the hot path:

- The outbox/CDC feeds an append-only audit store (immutable, 7-year retention, tiered to cold
  storage by the store's own lifecycle).
- A hold-expiry sweeper releases unused holds.
- The settlement system captures holds by `network_txn_id`.
- The operational table is partitioned by day; old partitions are detached and dropped once
  they're confirmed in the audit store.
- Multi-region: BIN ranges → home region. Cross-region failover by quorum promotion, with an
  explicit RPO trade-off (async = possible double-spend window, bounded by stand-in exposure caps)
  and the data-residency constraint on where EU card data may be replicated.
