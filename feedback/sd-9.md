# sd-9 — Transaction history feed

Date: 2026-10-04
Problem: Design the transaction history in the Revolut app. Users see all their transactions (card
payments, transfers, top-ups, withdrawals and so on) in one list, and they can search and filter it.

Session artifacts: `sd-sessions/sd-9/notes.md`, `sd-sessions/sd-9/01-high-level.png`.

Scored on the quarter-point scale (5 = the solution I would design; 1 minor improvement →
4.5–4.75; 2 minor → 4; each missed edge case −0.25/−0.5). Domain/legal items are in K and are not
scored. This prompt was a deliberately different shape from sd-5 to sd-8: a read-heavy,
event-driven projection (CQRS) instead of a money path with an external provider.

## Scores (1-5)

| # | Category | Score | Why |
|---|---|---|---|
| 1 | Requirements | **4** | Your best questioning so far: read-only?, number of types, detail vs list, event volume, statuses, which types change amount, currency, filters, peaks, SLAs, retention, and **"can events arrive out of order?"**. Peaks computed correctly. Deductions: the **read volume** of a read-heavy service was never asked or estimated (−0.5); the "lag the burst until 6–7 AM" decision was made before asking for the freshness SLA, which then contradicted it |
| 2 | Session leadership | **3.75** | You drove every phase and listed edge cases before answering them. But 5 interventions were needed on core points (first-insert upsert, sort timestamp, night burst ×2, scale push), and there was no closing summary |
| 3 | Communication | **4.25** | Clear, with fast and honest self-corrections ("you're right, I hadn't thought about that"; "it's going to be horrible UX"). You fixed the encryption statement on your own within one turn |
| 4 | HLD discipline | **4** | Readable CQRS diagram. Drift: consumers drawn writing directly to Elastic and NoSQL *and* through the outbox; cold storage (part of your NFR answer) missing |
| 5 | Component design | **3.75** | Good split: Postgres for the list and filters, Elastic for text, KV for details, the outbox to keep them consistent, version-guarded upserts, and two topics (after probes). Gaps: free-text search *combined with* filters (status/amount/date) needs those fields in Elastic, and you didn't address that (−0.5). The fan-out-to-producers idea was withdrawn after one challenge |
| 6 | Database design | **3.25** | Good: outbox `UNIQUE(transaction_id, type)`, thinking about new types vs the CHECK constraint, upsert + seq guard (after a probe). Gaps: **no transaction time**, so the feed sorted by `updated_at` (fixed after a probe) (−0.5); **single-column indexes** when every query is per user, which regresses sd-7's lesson (−0.5); an unnecessary seq index; no debit/credit direction (−0.25); first-event insert bug before the probe (−0.5) |
| 7 | Scalability | **3.75** | Cell per region, a federated broker (each region only gets its own events), failover in the jurisdiction with a sync replica. The bottleneck (Postgres primary → shard by user_id) came after a push, with no numbers and no cost. How a user reads data older than 1 year from cold storage was never defined |
| 8 | Security | **4.25** | Encryption at rest/in transit, masking in views and logs, JWT + **authZ: users only read their own feed**, the key risk here. Started with "encryption not strictly needed" and corrected it yourself. Minor: Redis/Elastic copies need the same protection |
| 9 | Edge cases | **3.75** | Six cases listed and answered correctly (duplicates/reordering, consumer crash, TX rollback, publisher crash, primary down, region down). Missing: the **night burst blocking real-time events** (−0.5, needed two prompts); Elastic/KV down → the list keeps working but search/details go stale (degradation not stated) (−0.25); a reversal arriving as a new linked transaction (−0.25) |
| 10 | Simplicity | **4.25** | The three-store CQRS split is justified by the access patterns. Minor: WebSocket for infinite scroll (pagination is plain request/response) (−0.25); Redis write-through *and* cache-aside on a paginated, mutable list without an invalidation story (−0.25) |
| 11 | Time management | **4** | Every phase reached, with depth on the core. No closing summary or open risks |

## A. Assessment: PASS (moderate margin)

A harder, different-shaped prompt, and the core mechanisms ended up right:

- version-guarded upserts so duplicates and reordering are harmless;
- the outbox written only on first insert;
- the amount served from the source-of-truth table;
- separate topics so the batch can't starve real-time events;
- sharding by user_id at 10x.

The margin is lower than sd-7/sd-8 because several of those needed a probe. In particular, the first
event of a new transaction being dropped, and sorting by `updated_at`, would both have been visible
bugs in production. The **reasoning quality after each probe was high**: you diagnosed, rejected
your own weaker idea (fanning out to the producers), and landed on the right fix quickly.

## B. Three strongest things

1. **Asking the questions that shape the design**: out-of-order delivery, which types change amount,
   peaks including the nightly batch, and the freshness SLA.
2. **Idempotent projection**: `(transaction_id, seq)` with a conditional upsert, with the outbox
   triggered by the insert branch, so it works for any arrival order. That's exactly the mechanism a
   senior engineer would use.
3. **Honest, fast self-correction**: encryption, the fan-out, and the sort key, each fixed in one
   turn with the reason stated.

## C. Three biggest risks for the real interview

1. **Check decisions against SLAs you haven't asked about yet.** You decided "the burst can lag
   until 7 AM" before learning about "5 s at any time". Either ask the SLA first, or revisit earlier
   decisions when a new requirement arrives. That's the same "decisions don't follow new facts"
   pattern as the old model-drift item.
2. **Schema completeness and per-user indexes** (third mock running for schema gaps: sd-6 amount,
   sd-8 phone number, sd-9 transaction time). Before showing a table, ask "what does my main query
   sort and filter by?" and index for **that** query, user first.
3. **Phase 4 still needs a push** (sd-8, sd-9). Say the bottleneck *with a number* and *its cost*
   before being asked.

## D. Architectural gaps or inconsistencies

- The diagram shows consumers writing to Elastic/NoSQL directly; the spoken design says only via
  the outbox.
- Free-text search lives in Elastic, filters in Postgres, but a combined "uber + completed + last
  month" query needs one store that holds both.
- The 1-year Postgres / cold-storage split was never connected to the read path (a user scrolling to
  2019).
- The night-burst lag decision contradicted the 5 s freshness SLA until probed.

## E. Missing non-functional considerations

- A freshness SLI: event-to-visible lag per topic, alerting above 5 s for the real-time topic.
- Read volume and read peak (app opens), which drive the replica, cache and Elastic sizing.
- Degraded mode when Elastic or the KV store is down (list still served; search/details temporarily
  unavailable).

## F. Over/under-engineering

- **Right-sized**: CQRS with three stores for three access patterns; outbox for cross-store
  consistency; no sharding at 5k WPS.
- **Over**: WebSocket for pagination; Redis write-through + cache-aside on a mutable list.
- **Under**: indexes (single-column), and the combined search + filter path.

## G. What a strong Revolut candidate might have covered

- Asking the read volume early ("how many feed opens per day / at peak?") and sizing reads first,
  since this is a read-heavy service.
- Feed key = `(user_id, occurred_at DESC, transaction_id)`, cursor = `(occurred_at,
  transaction_id)`, so pagination stays stable while statuses change.
- Putting the filterable fields in Elastic too (status/amount updates flow through the outbox), with
  routing by user_id so each user's search hits one shard. Or Postgres full-text if the volume per
  user is small enough.
- Separate topics/consumer groups from the start, plus pre-scaling consumers before the scheduled
  02:00 burst.

## H. Topics to practise before the next mock

1. **Index from the query**: write the main query (`WHERE user_id = ? ORDER BY occurred_at DESC
   LIMIT 50`), then derive the index. 3 quick reps on different features.
2. **Re-check earlier decisions when a new SLA arrives**: practise saying "that changes my earlier
   decision about X".
3. **Phase 4 opener with numbers**: "at 10x: N writes/s → the primary is the bottleneck → shard by
   user_id, which costs resharding + scatter-gather for cross-user queries".

## I. A better architecture (post-mock, brief)

```
Producers ─► topic: realtime  ─► consumer group A (priority) ─┐
          └► topic: batch     ─► consumer group B (pre-scaled) ─┤
                                                               ▼
  TX: INSERT … ON CONFLICT (transaction_id) DO UPDATE … WHERE excluded.seq > seq
      + outbox(index_doc) on insert AND on status/amount change (ES holds filter fields too)
  feed(user_id, occurred_at, transaction_id, type, status, amount, direction, currency, counterparty, seq)
      PK (transaction_id); INDEX (user_id, occurred_at DESC, transaction_id)
Reader API: list → Postgres replica (recent → primary) · search+filters → Elastic (routed by user_id)
            · detail → KV by transaction_id (ownership checked) · >1 year → per-user monthly archive
At 10x: shard Postgres + Elastic by user_id.
```

## J. Better options, decision by decision

| Your decision | Works? | Better option (if any) and why |
|---|---|---|
| CQRS: Postgres list + Elastic text + KV details | ✅ | — Right split for three access patterns |
| `(transaction_id, seq)` guard | ✅ Optimal | — |
| `UPDATE … WHERE seq <` (first version) | ❌ Drops new transactions | `INSERT … ON CONFLICT DO UPDATE … WHERE excluded.seq > seq` (you got there after the probe) |
| Outbox only when the insert branch runs | ✅ For immutable fields | If Elastic also holds status/amount for filtering, emit an outbox row on those changes too |
| Amount always served from Postgres | ✅ Optimal | — |
| Sort by `updated_at` → `created_at` | ✅ After probe | Use the transaction's occurrence time (`occurred_at` from the producer), plus `transaction_id` as the cursor tie-breaker |
| Single-column indexes on type/status/amount/account | ❌ | `(user_id, occurred_at DESC, transaction_id)`; filter within the user's rows; drop the seq index |
| Redis write-through 60 s + cache-aside LRU | ⚠️ Over | Primary for the user's recent rows is enough; cache only the first page per user, invalidated on that user's events |
| WebSocket for infinite scroll | ⚠️ Over | Plain cursor pagination over HTTP; a push channel only for "new transaction" notifications |
| Lag the burst until morning | ❌ vs the 5 s SLA | Separate topics (you got there), plus pre-scale for the predictable burst |
| Fan-out to producers for recent transactions | ❌ | You withdrew it: per-request coupling to ~10 services kills p99 and availability |
| 1 year in Postgres, rest in cold storage | ⚠️ | Define the read path: per-user monthly archives (e.g. compressed files keyed by user/month) fetched on demand, slower but acceptable for rare deep scrolls |
| Shard by user_id at 10x | ✅ | Add the numbers and the cost (resharding, scatter-gather for cross-user analytics, hot users) |

## K. Real-world bonus (not scored)

- **Wide-column stores** (Cassandra/ScyllaDB, DynamoDB) are the classic choice for activity feeds at
  very large scale: partition by user (+ month), cluster by time. Writes scale horizontally without
  manual sharding.
- **CDC instead of outbox polling** (Debezium reading Postgres' WAL) is common when the outbox
  volume is high.
- **Schema registry** (Avro/Protobuf) for producer events, so new transaction types don't break
  consumers. It also answers your "relax the CHECK constraint" question cleanly.
- **Merchant enrichment**: real feeds clean raw card descriptors ("UBER *TRIP 8823") into names and
  logos, an async enrichment step that updates the projection.
- **Statements** (monthly PDFs) are regulatory artefacts, separate from the app feed but built from
  the same data.
