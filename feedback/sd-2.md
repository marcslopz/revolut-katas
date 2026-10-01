# sd-2 — Hotel room booking (global)

Date: 2026-09-29
Problem: Design a system for booking hotel rooms, globally (hotels and users worldwide, no single
dominant region).

## Scores (1-5)

1. Requirements clarification: **3** — solid non-functional coverage (global scope, DAU, search:
   booking ratio, conversion %, availability/latency SLAs), but never surfaced an implicit
   requirement unprompted (payment/PCI scope, cancellation windows, multi-currency pricing) —
   same specific gap as sd-1, now confirmed recurring across two mocks.
2. Session leadership: **3** — a real improvement over sd-1's 2: drove the high-level design and
   most of the write-path design unprompted, with proactive trade-off reasoning volunteered at
   several points without being asked (consistency-via-single-writer, cache eventual-consistency
   rationale, circuit-breaker addition). I never had to intervene on pacing once, versus sd-1's 4
   separate redirects. But the session ended with the exact behavior Karim's email calls out:
   twice explicitly handed control back to me near the end ("ask me any questions about edge cases
   or whatever", "anything else?") instead of proactively naming remaining gaps and steering there
   itself — and the session ended inside Phase 3, never reaching Phase 4 (scaling) at all.
3. Communication: **4** — clear improvement on proactive trade-off articulation specifically (the
   named sd-1 weakness): stated reasoning for the single-writer choice, the cache's eventual-
   consistency scope, and the circuit-breaker addition without being asked first, not just when
   pushed.
4. High-level design discipline: **4** — stayed at box/topology level (regional web tier, write/
   read DB split, auth service) without naming specific database or cache technologies until Phase
   3; no premature deep-dive.
5. Component design: **3** — the room-hold-before-payment sequencing was correctly established
   (good prerequisite/pre-flow discipline, matching Karim's explicit criterion), but component
   boundaries stayed vague — everything sat inside one undifferentiated "web service" rather than
   naming distinct search/inventory vs. booking-orchestration responsibilities.
6. Database design: **2** — never reached at all. No schema, no indexing, no sharding/partitioning
   key discussion, despite explicitly stated scale (tens of thousands of hotels, millions of
   users). A real regression versus sd-1, which at least reached a schema once prompted.
7. Scalability reasoning: **2** — some local→regional instinct appeared early (stateless services,
   horizontal scaling per region, adding AZs as load grows), but Phase 4 (explicit local→regional→
   global progression, pushed to a much larger scale, cost/performance trade-offs) never happened —
   the mock ended before it was reached.
8. Security awareness: **2** — narrower than sd-1: only JWT-based authz was named. No encryption
   at rest/in transit, no rate limiting, no PII/payment-data handling discussed at all, despite this
   design directly touching a payment provider.
9. Edge cases and failure-handling: **4** — the strongest area of the mock, and a genuine positive
   signal: self-corrected from a naive long-held-lock-during-synchronous-payment-call design into a
   short atomic status-flip + outbox + async retry pattern under challenge — the same
   entity-owned-short-lock pattern taught and drilled in the post-sd-1 coaching session (hotel
   booking scenario), now reproduced unprompted in a live mock context. Also correctly reasoned
   through outbox-consumer crash recovery (queue redelivery + TTL backstop) and an EU-region SPOF
   trade-off, though both needed one or two interviewer follow-ups to fully resolve rather than
   being self-driven end-to-end.
10. Simplicity: **4** — no over-engineered detour this time (unlike sd-1's 2PC digression); reused
    the existing TTL mechanism for circuit-breaker-open handling rather than inventing new
    machinery, and scoped the cache to eventual consistency rather than over-engineering strong
    read consistency.
11. Time management: **3** — better than sd-1 in that I never had to redirect on pacing mid-session,
    but the session still ended with entire evaluation categories (database design, security,
    scaling) essentially uncovered, and the candidate didn't visibly budget time to make sure every
    phase got reached.

## A. Assessment: BORDERLINE

Different failure mode than sd-1, and arguably a harder one to accept in a real 50-minute round.
sd-1's problem was pacing control on a session that otherwise covered good breadth. This session
had noticeably better proactive communication and self-managed structure through most of Phase 3,
plus a genuinely strong, well-generalized failure-handling deep-dive — but it never reached three
of the named evaluation categories (database design, security, scaling) in any real depth, and
ended with the candidate asking the interviewer what's missing rather than naming it themselves.
Depth where it happened was strong; breadth across the full evaluation rubric was not there.

## B. Three strongest things

1. Self-corrected, unprompted mid-mock, from a lock-held-during-synchronous-payment-call design
   into a short atomic status-flip + transactional outbox + async retry pattern — reproducing,
   under real interview pressure, the exact mechanic taught and drilled two mocks ago in coaching.
   This is the clearest evidence yet that a coaching lesson generalizes past the session it was
   taught in.
2. Proactive trade-off narration, volunteered before being asked, at multiple points (single-writer
   consistency rationale, cache staleness-is-fine-because-booking-enforces-it reasoning,
   circuit-breaker addition) — directly addresses sd-1's flagged "reactive not proactive" weakness.
3. Correct idempotency-key + retry reasoning for the external payment-provider call, again without
   confusing it with any heavier distributed-transaction machinery — consistent with the strong,
   now-repeated Build It/System Design pattern on this specific mechanic.

## C. Three biggest risks for the real interview

1. **Running out the clock before reaching Database Design and Scaling.** In this format those are
   separately evaluated categories. Spending most of the session on one deep, well-handled
   mechanism (the booking write path) at the cost of never reaching two other graded areas is a
   real risk even with strong depth on what did get covered.
2. **Relying on the interviewer to name what's missing.** "Ask me any questions" and "anything
   else?" both hand structural ownership back to the interviewer — exactly the behavior Karim's
   email singles out as separately graded, and it recurred here even in a session that was
   otherwise much better self-driven than sd-1.
3. **Security breadth.** For a system that talks to a real payment provider, reaching only JWT authz
   and nothing else (encryption, rate limiting, PII/payment-data handling) would likely draw a
   direct follow-up in the real interview that this mock never got to.

## D. Architectural gaps or inconsistencies

- No sharding/partitioning strategy was ever discussed for the single-EU-writer database, despite
  the stated global, multi-tens-of-thousands-of-hotels scale — an open question that Phase 4 would
  normally have forced.
- The EU-region-outage discussion surfaced a real, acknowledged single point of failure (the global
  single write leader) that was explicitly deferred rather than designed around — a legitimate
  choice if stated as a deliberate trade-off, but it was reached only after two interviewer
  follow-ups, not raised proactively when the single-writer decision was first made in Phase 2.

## E. Missing non-functional considerations

- Security: encryption at rest/in transit, rate limiting/abuse prevention, PII/payment-data
  handling — none discussed.
- Observability for the failure paths actually designed (e.g. detecting a growing backlog of
  `held`-but-unresolved rooms, outbox consumer lag, circuit-breaker trip rate) — not raised.
- Compliance/regulatory considerations for handling payment data (even lightweight PCI-scope
  awareness) — not raised, despite the design directly touching a payment provider.

## F. Over/under-engineering

- No over-engineering this time — the design stayed proportionate throughout, and the reuse of the
  existing TTL mechanism instead of adding new circuit-breaker-specific handling was a good
  simplicity instinct.
- Under-engineered by omission rather than by a wrong choice: database design and scaling were
  never reached, not because a poor choice was made there, but because they were never attempted.

## G. What a strong Revolut candidate might have covered that this session didn't

- Naming a sharding key for the bookings/inventory data (e.g. hotel_id) once global scale was
  established, rather than leaving the single-EU-writer topology unexamined at data-model level.
- Proactively raising the EU-region SPOF as a stated trade-off at the moment the single-writer
  decision was made in Phase 2, rather than only after two interviewer follow-ups near the end.
- Self-budgeting time to explicitly reach Phase 4, even briefly, rather than ending the session by
  asking the interviewer what else to cover.
- At least one explicit security/compliance consideration for a payment-adjacent flow, raised
  unprompted.

## H. Topics to practice before the next mock

- **Explicit time-boxing that guarantees all four phases get touched**, even lightly — the same
  practice priority flagged after sd-1 (self-imposed time-boxing), now showing a new symptom: not
  running out of time on one topic, but running out of new topics to self-generate near the end of
  Phase 3, before scaling was ever reached.
- **Ending the "ask me anything else" pattern** — rehearse explicitly naming your own remaining gaps
  ("I haven't covered database sharding or security in depth — let me do that now") instead of
  inviting the interviewer to point them out.
- **Security/compliance as a standing checklist item for fintech-adjacent prompts** — surface at
  least one item unprompted, the same open item from sd-1.
- Continue reinforcing the short-atomic-lock + outbox pattern — it's now confirmed twice (coaching
  drill, then this live mock) and is becoming a genuine strength; watch for it recurring correctly
  in a third, independent context to consider it fully resolved.

## I. A better architecture (post-mock only)

Keep the regional web tier and the room-hold + transactional-outbox + async-payment-retry pattern —
that part is sound and well-reasoned. Add a sharding key on the bookings/inventory tables (e.g.
`hotel_id`, since a hotel's rooms are always read/written together and never need cross-hotel
transactions) so the single-EU-writer topology can scale horizontally as hotel count grows, instead
of being a single unsharded primary. For the EU-region SPOF, either state explicitly as an accepted
trade-off with a documented RTO/RPO, or add asynchronous replica promotion (consensus-based leader
election, e.g. Raft-based coordination across regional replicas) if the 99.9% SLA is meant to
survive a full regional outage — the design as discussed cannot currently guarantee that. Add
field-level encryption for payment-adjacent PII, rate limiting at the API gateway layer per user/IP,
and metrics on `held`-room age and outbox consumer lag so degraded payment-provider health is
observable before it causes a backlog of stuck rooms.
