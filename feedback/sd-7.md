# sd-7 — Withdrawals to an external bank account

Date: 2026-10-04
Problem: Design a feature that lets Revolut users withdraw money from their Revolut account to their
own account at another bank.

Session artifacts: `sd-sessions/sd-7/notes.md`, `sd-sessions/sd-7/01-fni.png`,
`sd-sessions/sd-7/02-high-level.png`.

First mock under the 2026-10-04 calibration: technical design is scored, domain/legal is bonus
only, quarter-point scale (5 = the solution I would design; 1 minor improvement → 4.5–4.75;
2 minor → 4; each missed edge case −0.25/−0.5).

## Scores (1-5)

| # | Category | Score | Why |
|---|---|---|---|
| 1 | Requirements | **4** | Good provider/region questions; currency assumption stated and checked; both peak factors stacked correctly (139/s). Minor: functional list = create only (status/history came in later); 10M reads/day not converted |
| 2 | Session leadership | **4** | You drove every transition, held your structure, and closed with your own summary. The core gap (orphaned withdrawals) needed one probe. No questions at wrap-up |
| 3 | Communication | **4** | Trade-offs stated with reasons: status column vs queues, cold storage for maintenance + cost, eventual consistency for views. Minor drift: "publisher"/"queue HA" for a queue the design doesn't have; the summary said "mixed DB/outbox/queue" |
| 4 | HLD discipline | **4.5** | Lean, box-level skeleton. Minor: the recovery worker never appeared as a box |
| 5 | Component design | **4** | Pre-flow done right (hold before calling the provider). Two minors: no recovery worker until probed; callback handling not separated or authenticated |
| 6 | Database design | **4.25** | Payment row with status, client idempotency key, bank_payment_id, hold + row in one TX, double-entry ledger, rows-per-event estimate, cold-storage tiering. Minor: read indexes should be per user (composite) |
| 7 | Scalability | **3.75** | Residency right, cell per region, multi-AZ failover inside the region. Thin: no local → regional → global steps, no new bottleneck named at scale; "region down" answered with AZs (−0.25); read-your-writes on replicas not considered |
| 8 | Security | **3.5** | Encryption in transit/at rest, tokenisation, residency stated in Phase 1. Missing (technical): callback authentication (−0.5); authZ (a user can only see and withdraw from their own accounts) (−0.5); rate limiting (−0.25) |
| 9 | Edge cases | **3.75** | Client retry, crash mid-flow, failover + ledger-sums-to-zero + stuck detector, returns compensated correctly. Missing: provider **rejects** → release the hold (−0.5); newest rows lost on async-replica promotion after the provider was already called (−0.5); duplicate return callback (−0.25) |
| 10 | Simplicity | **4.75** | Best so far: status column as saga state instead of queues, Redis only "if it grows", cold storage justified by cost. Minor: HA for a queue that isn't in the design |
| 11 | Time management | **4.25** | Every phase reached with a self-driven close; Phase 4 was short |

## A. Assessment: PASS

A clear pass, and the strongest mock of the seven. The HIGH priority from sd-3/sd-5/sd-6 showed up
**unprompted in the first minutes**:

- the withdrawal entity first;
- a hold before the irreversible step;
- the row persisted before the external call;
- a client idempotency key, with the payment_id as the provider's key;
- the debit and hold release in one transaction on the callback.

The only core gap (who moves orphaned rows forward) was fixed after one question, with the right
reasoning about why duplicates between the API and the worker are harmless.

Data residency was right for the **second mock in a row**, which meets the bar to mark it resolved.

## B. Three strongest things

1. **Money path designed correctly from the start**: entity → hold → persisted state → idempotent
   provider call → atomic settle. This is exactly what was missing in sd-6.
2. **Simplicity with explicit trade-offs**: "status column instead of queues, queues later if the
   provider needs rate limiting" is the right call at 139/s, and you said why.
3. **Detection, not just recovery**: ledger entries must sum to zero, plus a stuck-operation
   detector that tells legitimately waiting withdrawals apart from stuck ones.

## C. Three biggest risks for the real interview

1. **Happy path first, failure paths only when asked.** Provider *reject* never came up, and
   returns came up only when I prompted. Make "for every external call: success, reject, timeout,
   late reversal" a reflex.
2. **The recovery worker should be part of the design, not an answer to a probe.** Whenever the
   state lives in a status column, say in the same breath who scans for stuck rows and on what
   criteria.
3. **Phase 4 depth.** Residency is solid now, but the scaling step needs one new bottleneck and its
   cost. Here that's the provider's rate limits on payday peaks (you had the queue/throttle idea;
   you just placed it in infra, not in scaling).

## D. Architectural gaps or inconsistencies

- The design chose status column + recovery worker. Later answers talked about a "publisher",
  "queue HA" and "a mixed DB/outbox/queue" pattern. Pick one and keep it.
- The recovery worker isn't on the diagram.
- "If a region goes down" was answered with availability zones, which only cover an AZ outage.

## E. Missing non-functional considerations

- Callback authentication (signature) and authorization (ownership of the account; the destination
  must be the user's own account).
- Business-level monitoring: withdrawals stuck in `waiting` beyond the provider's SLA, provider
  error rate, return rate.
- Read-your-writes after creating a withdrawal while reading the list from replicas.

## F. Over/under-engineering

- **Right-sized**: one service, no queue, no cache until needed, cold storage after one year, no
  sharding at ~1k row writes/s.
- **Slightly under**: the recovery worker (missing until probed) and the reject path.

## G. What a strong Revolut candidate might have covered

- Recovery worker spelled out: `WHERE status IN ('created','waiting') AND updated_at < now() − N
  … FOR UPDATE SKIP LOCKED`. For `created`, call the provider again (same key). For `waiting`,
  query the provider's status instead of waiting forever for a callback.
- An explicit state machine: `created → sent → completed | rejected → (returned)`, each transition a
  conditional UPDATE, with every terminal path releasing or settling the hold.
- Scaling: payday peak → provider rate limits → throttle (token bucket) in front of the provider,
  with the backlog visible to users as "processing".

## H. Topics to practise before the next mock

1. For every external call, the four outcomes: success / reject / timeout (unknown) / late reversal.
   Quick reps on 3–4 providers (card, bank transfer, KYC vendor, broker).
2. "Status column ⇒ recovery worker": practise saying the worker's selection query and its
   concurrency guard in one sentence.
3. Phase 4: name one new bottleneck and its cost at each step (local → regional → global).

## I. A better architecture (post-mock, brief)

Same shape as yours, with three additions:

```
API ── TX1: hold + withdrawals(created, client_key UNIQUE) ── call provider(key=payment_id) → sent
Callback (signed) ── TX: UPDATE … WHERE status='sent' → completed + ledger + release hold
                     reject  → rejected + release hold
                     return  → UPDATE … WHERE status='completed' → returned + reverse ledger
Recovery worker ── stuck rows (SKIP LOCKED): created → resend · sent → query provider status
Primary with a synchronous standby in another AZ (no lost rows on failover) · second region in
the same jurisdiction for a full-region outage · throttle in front of the provider for payday.
```

## J. Better options, decision by decision

| Your decision | Works? | Better option (if any) and why |
|---|---|---|
| Saga state in a status column, no queue | ✅ Optimal | — The simplest correct choice at 139/s |
| Hold + payment row + client idempotency key in TX1 | ✅ Optimal | — |
| payment_id as the provider's idempotency key | ✅ Optimal | — |
| Debit + release hold on the completion callback | ✅ Works | Debiting at send time is the other valid model; yours keeps the money "reserved" while pending, which is cleaner for the user |
| Callback dedupe "check it's not already completed" | ⚠️ Works if serialized | A **conditional UPDATE** (`WHERE status = 'sent'`, 0 rows = duplicate) makes it race-free with two callback deliveries at once |
| Recovery worker (after the probe) | ✅ | Add the selection criteria + `SKIP LOCKED`, and **query the provider** for `sent` rows instead of only re-sending |
| Indexes on status / created / updated | ⚠️ | The access pattern is per user: `(user_id, created_at DESC)` with **keyset pagination** (`WHERE created_at < :cursor`), not single-column indexes or OFFSET |
| Read replicas with eventual consistency for views | ✅ | Plus read-your-writes: return the new row from the create call, or read a user's last few minutes from the primary |
| Replica promotion on primary failure | ⚠️ | With async replication the newest rows can be lost after the provider was called. A **synchronous standby** in another AZ for this DB gives zero data loss (RPO 0) at a small latency cost, or reconcile daily against the provider's records |
| Multi-AZ for "region down" | ⚠️ | AZs cover an AZ outage; a full-region outage needs a second region **in the same jurisdiction** (EU: e.g. Frankfurt + Dublin) |
| Cold storage after 1 year | ✅ Optimal | Partition by month so moving old data means detaching whole partitions |

## K. Real-world bonus (not scored)

- **Confirmation / Verification of Payee**: before sending, banks check that the account name
  matches the IBAN or sort code (UK CoP; EU VoP since October 2025). It's a sync call before
  `sent`, and a mismatch warning shown to the user.
- **Account-takeover pattern**: "password reset, then a withdrawal to a new account" is the classic
  fraud. Real systems add step-up authentication or a cooling-off period for new destinations.
- **Instant vs standard schemes**: SEPA Instant / Faster Payments settle in seconds; standard SEPA
  takes about a business day. The provider usually tries instant first and falls back.
- **Daily reconciliation files** from the provider are the safety net for every missed callback.
- **AML monitoring** also applies to outgoing money: unusual withdrawal patterns get flagged.
