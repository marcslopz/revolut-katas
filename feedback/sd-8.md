# sd-8 — Mobile phone top-ups

Date: 2026-10-04
Problem: Design a feature that lets Revolut users buy mobile phone credit (a top-up) for any phone
number, in any country, from the Revolut app.

Session artifacts: `sd-sessions/sd-8/notes.md`, `sd-sessions/sd-8/01-high-level.png`.

Scored on the quarter-point scale (5 = the solution I would design; 1 minor improvement →
4.5–4.75; 2 minor → 4; each missed edge case −0.25/−0.5). Domain/legal items are in K and are not
scored.

## Scores (1-5)

| # | Category | Score | Why |
|---|---|---|---|
| 1 | Requirements | **4** | You asked the right questions about an unfamiliar domain (how a top-up works, the catalog, latency per call, freshness, sync/async) plus throughput, latency, availability and retention. Rates right. Minor: functional requirements merged into the design; two settled answers re-asked (sync/async, 600k/day); peak factor not applied to reads |
| 2 | Session leadership | **4** | You drove every phase: listed 6 edge cases *before* answering them, and started Phase 4 yourself. Needed two probes (cache conflation, late reversal) and one scale push. No closing summary |
| 3 | Communication | **4.25** | Clear and quantified, including an explicit latency budget (TX ~50 ms + RTT ~10 ms → >400 ms headroom). Minor drift: outbox in TX1, but the schema's publisher polls `topup_payments` |
| 4 | HLD discipline | **4.25** | Clean diagram with the catalog cache, queue, worker and checker. Minor: API → queue drawn directly (no outbox relay), no worker → DB edge, no callback receiver |
| 5 | Component design | **4.25** | Hold before calling the provider, outbox, worker, checker with explicit criteria, circuit breaker that also disables the UI. Minor: the checker only scans `waiting`; reversal routed through outbox + worker instead of one TX |
| 6 | Database design | **3.75** | Indexes derived from the actual queries (composite, correctly ordered, `SKIP LOCKED`). Missing from `topup_payments`: **destination phone number**, **client idempotency key + UNIQUE**, aggregator reference (−0.5 together). Minor: ledger mixes a signed amount with debtor/creditor columns; `hold + available = balance`, not `≤` |
| 7 | Scalability | **4** | Cell per region, two regions per jurisdiction, synchronous standby. The bottleneck (the aggregator) and its cost options came after one push. Estimation slips at 10x: daily average used instead of peak (69/s vs ~208/s); storage "<1 TB" vs ~4.4 TB in total (the conclusion still holds per cell) |
| 8 | Security | **3.75** | Field-level encryption of phone numbers with a KMS key, TLS/mTLS, residency. Missing: callback authentication (−0.5); authZ (users only see their own top-ups) (−0.25) |
| 9 | Edge cases | **4.25** | **Excellent**: API crash, publisher crash, 5xx, timeout, worker crash, region outage, each with the right mechanism, plus graceful degradation. Missing: late reversal until asked (−0.25); rows stuck in `created` if the publisher dies for good (the checker only scans `waiting`) (−0.25); how long held top-ups wait during a long outage before being released (−0.25) |
| 10 | Simplicity | **4.5** | Right-sized throughout. Minor: the reversal only touches your own DB, so outbox + worker is an extra hop |
| 11 | Time management | **4.25** | Every phase reached, with depth where it mattered. Ended without a closing summary or wrap-up |

## A. Assessment: PASS, strong

On par with sd-7, and it **closes this week's HIGH item**: the failure paths of the external call
(success / failed / pending / 5xx / timeout) were covered **without being asked**, including a
checker with explicit selection criteria, circuit breakers, and graceful degradation (disabling the
UI). Only the fourth outcome, the **late reversal**, needed a prompt, and you answered it correctly.

The money path was entity-first again (hold → row + outbox → idempotent provider key → atomic
settle) — a second clean mock for that item. You also applied every J-section correction from sd-7
on your own: read-your-writes from the primary, per-user composite index, a synchronous standby,
and a second region inside the jurisdiction.

## B. Three strongest things

1. **Failure-first thinking without prompts**: 6 named edge cases, each with a concrete mechanism,
   plus "stop accepting top-ups in the UI" as deliberate degradation.
2. **Quantified reasoning**: a latency budget broken into milliseconds, rows per event, storage with
   a sanity check, and the provider named as the bottleneck for the 10 s target.
3. **Learning transfer**: everything from sd-7's J section showed up here without being asked.

## C. Three biggest risks for the real interview

1. **Schema completeness**: the field the whole feature revolves around (the phone number) and the
   client idempotency key were missing from the table. Before showing a schema, check it against
   your own flow: every field you said you use.
2. **Estimation at scale**: the peak factor dropped out at 10x. Carry the peak multiplier through
   every recalculation.
3. **The fourth outcome**: success, reject and timeout are now automatic. Add "late reversal" to the
   same reflex.

## D. Architectural gaps or inconsistencies

- Outbox written in TX1, but the publisher query polls `topup_payments WHERE status='created'`.
  Both are valid; pick one.
- The diagram has the API publishing to the queue directly, and no callback receiver.
- The ledger schema is a one-row-with-two-parties model, while the flow described two rows.
- The ledger counterpart was "credit for the phone number"; it should be an internal account (e.g.
  "aggregator payable").

## E. Missing non-functional considerations

- Callback authentication (signature + timestamp).
- A product SLI: % of top-ups final within 10 s, and the number of rows stuck in non-terminal states.
- A TTL on cached phone → operator entries (numbers move between operators).

## F. Over/under-engineering

- **Right-sized**: one Postgres, a two-level cache, outbox + queue + worker, no sharding at ~200
  writes/s.
- **Slightly over**: the reversal through outbox + worker.
- **Slightly under**: the checker's coverage (only `waiting`).

## G. What a strong Revolut candidate might have covered

- The checker scanning **every** non-terminal state with an age threshold: `created`/`sent` →
  re-publish or query; `waiting` → query the aggregator.
- Little's law for the worker pool: ~21/s × 5 s ≈ 100 calls in flight (×30 s worst case ≈ 600), so
  workers need concurrency, not just instances.
- A deadline for held top-ups during a long outage: after X hours, mark them failed and release the
  holds.

## H. Topics to practise before the next mock

1. A 30-second **schema check against your own flow** before presenting a table.
2. Carry the **peak factor** through every estimate, including "what if 10x".
3. Add **late reversal** to the outcomes reflex: success / reject / timeout / reversal.

## I. A better architecture (post-mock, brief)

Same as yours, with these deltas:

```
topup_payments(+ phone_number_enc, client_key UNIQUE, aggregator_ref, updated_at,
               status: created → sent → succeeded | failed | waiting → reversed)
Callback receiver (signed) ── one TX per outcome, conditional UPDATE on the expected status
Checker ── all non-terminal rows older than N (created/sent → republish/query, waiting → query)
Reversal ── one TX in the callback handler (no outbox: no external side effect)
```

## J. Better options, decision by decision

| Your decision | Works? | Better option (if any) and why |
|---|---|---|
| Hold + payment + outbox in TX1, client idempotency key | ✅ Optimal | — |
| payment_id as the aggregator's idempotency key | ✅ Optimal | — |
| Two-level cache (number → operator, operator → catalog) | ✅ After one probe | Give the number cache a TTL of days, because numbers move between operators |
| Catalog TTL 1 h | ✅ Optimal | It matches the business's tolerance |
| Publisher polls `topup_payments` while TX1 also writes an outbox row | ⚠️ Redundant | Use one: an outbox table (clean separation) **or** the status as the outbox (fewer tables) |
| Checker on `waiting` only | ⚠️ | Scan all non-terminal states with an age threshold |
| Callback dedupe by checking the terminal status | ⚠️ | Conditional `UPDATE … WHERE status = '<expected>'`; 0 rows = duplicate (race-free) |
| Reversal via outbox + worker | ⚠️ Over | One TX in the callback handler; the outbox is only for side effects on other systems |
| Circuit breaker + disabling the UI | ✅ Optimal | Add a deadline to release holds of top-ups stuck behind a long outage |
| Ledger: signed amount + debtor/creditor | ⚠️ | Double entry: one row per account (`entry_id, txn_id, account_id, amount`), entries summing to zero |
| Sync standby + second region in the jurisdiction | ✅ Optimal | — |
| 10x: multi-aggregator split / pay for a better SLA | ✅ | Name the cost: a routing layer, a provider-agnostic status model, reconciliation per provider |

## K. Real-world bonus (not scored)

- **Number portability**: a phone number's prefix doesn't reliably tell you the operator, which is
  why the lookup exists, and why the number cache needs a TTL.
- **Currency**: catalog prices are in the operator's currency; real systems lock an FX quote at
  purchase and carry it in the message (the same lesson as the cross-cell FX case).
- **Fraud**: top-ups are a classic way to cash out a compromised account (instant, irreversible,
  anonymous recipient). Real systems put velocity limits and step-up authentication on new numbers.
- **Prepaid float**: Revolut keeps a balance at the aggregator. Monitoring that float and topping it
  up is an operational dependency; if it runs dry, every top-up fails.
- **Daily reconciliation** of Revolut's records against the aggregator's report.
