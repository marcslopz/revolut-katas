# sd-2 — notes

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Phase 1 — Requirements

Functional (candidate-proposed): search hotels by location + capacity, view pricing, book a room.
Did not ask about / I did not volunteer: cancellation, modification, viewing booking history —
watch whether these surface later or stay a gap.

Non-functional (stakeholder answers given):
- Global: hotels + users worldwide, no single dominant region (NA/EU/APAC spread)
- 5M DAU, searches:bookings ~100-200:1, ~2% of DAU book per day
- Availability target 99.9%
- Latency: search p99 <300ms, booking (write) p99 <1s
- Candidate did not ask for QPS/storage numbers themselves — computed nothing yet, just used the
  raw inputs qualitatively so far.

Implicit requirements (compliance/regulatory, multi-currency, cancellation windows): not raised by
candidate yet — watch for this, per sd-1's flagged gap on implicit requirements.

## Phase 2 — High-Level Design

- Regional web-server tier (NA/EU/APAC), stateless, horizontally scalable per region independently.
- Single write leader in Europe for the DB; async read replicas in every region — every web server
  writes to EU, reads locally. Candidate's stated rationale: prioritizes consistency, simplifies
  atomic transactions for booking. (Cost/trade-off of this — cross-region write latency from
  NA/APAC — not yet self-identified.)
- Global auth/authz service, JWT-based, used by every backend to authorize bookings.
- Geo-routing: requests directed to nearest regional web-server pool; more AZs can be added per
  region as load grows, replicating the same per-region pattern.
- Not yet covered at HLD level: search/inventory component boundary, booking write path detail,
  caching, how availability is queried before booking (single global write DB implies read
  replicas could serve stale availability — not yet flagged as a risk by candidate).

## Phase 3 — Low-Level Design

Booking write path (evolved through several iterations, ending state below):
- Initial proposal: single transaction holds the room row lock, calls payment provider
  synchronously, rolls back on failure. I challenged what happens on a provider timeout
  (ambiguous outcome, lock held for the whole retry duration).
- Candidate confirmed payment provider supports idempotency keys, proposed retrying 3-5x.
- I pushed again on whether retries happen inside the same open transaction/lock — candidate
  self-corrected to a much better design:
  - Short atomic transaction: flip room status to `held` + write to an outbox table, same
    transaction, lock released immediately after (matches the entity-owned-short-lock pattern
    from the earlier coaching RAPID SD DRILL — good sign it generalized into a live mock).
  - Outbox consumer retries payment async with the idempotency key.
  - On failure, status reverts to `free`.
- SLA reconciliation: I flagged that the stated "booking p99 <1s" SLA no longer maps cleanly to a
  single operation once payment is async. Candidate's first answer was UX hand-waving (spinner);
  pushed once more, then explicitly and correctly re-scoped: the 1s SLA applies to the room being
  marked `held`, not to final payment confirmation. Took one interviewer nudge to reconcile
  explicitly rather than self-catching it — same "reactive not proactive" pattern flagged as a
  recurring weakness after sd-1, though the resolution itself, once pushed, was clean and correct.

Not yet covered: what happens if the outbox consumer itself crashes/never processes the message
(no TTL/expiry on `held` status mentioned yet — same open question as the earlier coaching drill
on this exact pattern), database schema, indexing/sharding, caching, security depth beyond
JWT-based authz, observability.

Caching: Redis, caches "all of it" (search results, availability, pricing) — reads eventually
consistent, correctness enforced at actual booking time by the held-status write path, not by the
cache. Good, well-reasoned answer, connected back to their own earlier write-path design
unprompted.

Deployment: one-box/canary per region, starting in an off-peak region, promoting to full fleet
after validation.

Edge case — outbox consumer crash: room stays `held`; recovery via message-queue-level max-retries/
redelivery (not a bespoke mechanism), plus a TTL on the held timestamp as the backstop to unblock
the room if everything else fails. Reasonable, resolved after two interviewer follow-ups (initial
answer didn't address the redelivery/TTL mechanics until pushed).

Edge case — EU write-region full outage: candidate initially downplayed this as "very difficult"
citing multi-AZ redundancy within Europe — conflated AZ-level HA with region-level DR when
challenged on the distinction. When pressed again, explicitly said "I'm not preparing for that
scenario" — a consciously deferred SPOF, not a design gap they were unaware of, but also not a
trade-off they raised or justified on their own before being asked.

Payment-provider circuit breaker: proposed unprompted when asked what's still missing (good, self-
identified fair gap). Follow-up on breaker-open behavior for an in-flight `held` room got a thin
answer — falls back on the existing TTL mechanism rather than any breaker-specific handling
(reasonable minimalism, but was not a fully worked-through answer).

## Session-leadership observations (for review)

- Drove the HLD and most of the write-path design unprompted, with real trade-off reasoning stated
  proactively at several points (consistency-via-single-writer, cache eventual-consistency
  rationale, circuit-breaker addition) — better than sd-1 on this specific dimension.
- BUT: twice explicitly handed control back to the interviewer near the end of Phase 3 ("ask me any
  questions about edge cases or whatever", "anything else?") instead of proactively raising
  remaining gaps (DB schema/indexing, security depth beyond JWT, Phase 4 scaling
  local→regional→global, compliance/PII) themselves. Never reached Phase 4 (scaling) at all —
  session effectively ended inside Phase 3.
- Interviewer note: I did not prompt for a canvas screenshot at any point (my own process gap, not
  the candidate's — rule 6 in interviewer.md says to ask if several minutes pass with none; I let
  the whole mock run without one).

## Phase 4 — Scaling

(pending)

## Open questions / inconsistencies to watch

(none yet)
