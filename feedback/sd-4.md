# sd-4 — Notification platform

Date: 2026-10-01 (same day as sd-3, run right after the sd-3 review + Q&A)
Problem: Design a notification system that lets Revolut send messages to its users.

Session artifacts: `sd-sessions/sd-4/notes.md`, `sd-sessions/sd-4/01-hld.png`.

## Scores (1-5)

1. Requirements clarification: **4** — strong functional structuring. You modelled the problem as
   types × channels × user preferences yourself, asked who controls routing, and pinned down
   mandatory (non-opt-out) types. The traffic estimate was correct first time (868/s avg,
   4.3k/s peak, 5.5k/s campaign burst). **The implicit requirement came unprompted again**: PII in
   content plus legal audit. You also asked for per-type latency SLAs. Deductions: the storage
   estimate took three rounds:
   - a 500 KB "average" built from a 50/50 email/SMS guess;
   - forgetting to multiply by record size;
   - accepting 157 PB/year without a gut check until asked.

   You also re-asked the campaign frequency. You never asked about availability, delivery
   guarantees (are duplicates acceptable?), time zones/quiet hours, or marketing consent.
2. Session leadership: **4** — a clear step up. You drove every transition, **identified the core
   problem without prompting** (priority isolation, so marketing bursts can't delay OTPs), and
   raised failure handling, backpressure and security on your own. You also ended on your own
   summary rather than "anything else?". Held back from 5 by two things: the estimation loop made
   Phase 1 run long, and the local → regional → global step only started when I asked. The
   closing summary recapped what you'd built rather than naming open risks.
3. Communication: **4** — the active-passive justification was the best trade-off answer across
   all four mocks: consistency simplicity, cost (passive regions at minimum scale with autoscale),
   cross-region latency weighed against each SLA, and cross-region campaign targeting. Sharding by
   user_id came with its cost stated (campaign scatter-gather). Minor: you then said "since we
   don't need sharding," two turns after proposing sharding.
4. High-level design discipline: **4** — a clean box-level pipeline (API → broker → 4 priority
   queues → 4 consumer groups → providers) with no premature technology choices.
5. Component design: **3** — good:
   - priority queues with independently scaled consumers;
   - preference filtering *before* enqueue (correct pre-flow ordering);
   - campaigns as an async job table plus a worker, not a synchronous fan-out in the POST.

   Gaps:
   - every consumer group talks to every provider directly, so sending logic, provider
     credentials and rate limits are duplicated four times (no per-channel sender layer);
   - the in-app inbox channel was in scope but never drawn;
   - no component receives provider delivery callbacks, although your `delivered` status depends
     on them;
   - no path for users to manage preferences.
6. Database design: **3** — sensible relational model:
   - UNIQUE(user, type, channel) on preferences;
   - security deliberately removed from the preferences table so the legal invariant is enforced
     by the data model;
   - a status lifecycle (created → sent → delivered/failed) that maps to the audit requirement.

   Gaps:
   - `notifications` had no content reference (audit must prove *what* was sent);
   - no producer idempotency key;
   - no `campaign_id`, although your crash-recovery answer relied on it;
   - no contact or device-token table (multiple phones, emails, push devices per user);
   - "index every filterable column" on `users`;
   - 151 TB in one relational DB, with no partitioning or TTL for non-mandatory types;
   - writes per notification (insert + 2 status updates) never factored into the write estimate.
7. Scalability reasoning: **3** — you named the right two bottlenecks at 10x (DB writes and
   provider limits), chose a justified shard key, and acknowledged the scatter-gather cost.
   Multi-region reused the quorum-promotion pattern consistently, and cost reasoning appeared for
   the first time. But:
   - **replicating the whole `users` table (PII) to every region**, the same data-residency gap
     as sd-3, explained in the Q&A earlier the same day;
   - the "no sharding" contradiction;
   - a Redis cache for campaign targets adds little, since segments rarely repeat and the cache
     would hold hundreds of millions of IDs;
   - replication RPO at failover was never discussed.
8. Security awareness: **4** — masking PII in logs, mTLS internally, vault + tokens for sensitive
   data, and per-type RBAC for producers. JWT was used correctly this time, for human operators,
   with system producers kept separate. **Caveat:** most of this applies the post-sd-3
   explanation given an hour earlier, so it's same-day transfer, not independent recall (see
   [[coaching-drill-vs-mock-evidence]]). Not covered: OTP handling (stored? hashed? kept out of
   the notifications table and logs), PII sent to third-party providers, encryption at rest.
9. Edge cases and failure-handling: **4** — the strongest area:
   - crash mid-campaign → checkpoint + idempotent consumer (two layers, the second unprompted);
   - replicated, persistent broker;
   - DLQ for poison messages;
   - per-provider rate limiters and circuit breakers;
   - **load shedding by priority** (block campaign launches, throttle "others"), unprompted;
   - fallback channel for OTP when SMS is down.

   Precision gaps:
   - dedupe on "already *delivered*" misses in-flight messages; it should be "already exists";
   - an offset/count checkpoint is unstable while users change, so a keyset cursor is needed;
   - no secondary SMS provider for the critical channel;
   - OTPs queued during an outage should expire with the code's 5-minute TTL, not be sent late.
10. Simplicity: **3** — the core pipeline is lean. But the session reached for extra components
    without a stated need: a Redis cache for campaign targeting, a cache to avoid re-reading the
    ID file on restart, and a CDN for internal user-ID files. That last one is internal batch
    input, read once, and puts personal data on edge infrastructure. The 157 PB detour came from
    assumptions you hadn't sanity-checked.
11. Time management: **3** — every phase was reached, and Phases 2–4 were well proportioned
    around the core. The estimation loop in Phase 1 cost several exchanges that a single
    sanity check would have avoided.

## A. Assessment: PASS (low margin)

This is the first mock where the candidate **found the prompt's core and designed it first**
(priority isolation, then backpressure/shedding by priority). That directly addresses sd-3's #1
risk. Failure handling was layered and mostly self-driven, and the trade-off reasoning was the best
so far. What keeps the margin low: estimation sanity, a recurring data-residency blind spot, and
schema/consistency slips over the course of the session (fields used later but never modelled,
"no sharding" after sharding).

## B. Three strongest things

1. **Core first.** Priority queues isolating OTP/security from marketing bursts came in the first
   HLD sentence. Later you added load shedding by priority under degradation without prompting.
2. **Layered failure handling:** checkpoint + idempotent consumer, DLQ, a replicated broker,
   per-provider rate limits and breakers, and a channel fallback for OTP.
3. **Trade-off justification with cost and SLA:** active-passive defended on consistency, cost,
   latency-vs-SLA and cross-region targeting. Sharding by user_id came with its scatter-gather cost
   stated up front.

## C. Three biggest risks for the real interview

1. **Estimation without a gut check.** sd-3 was off 55x on a division; sd-4 had a missing factor,
   a naive average, and 157 PB accepted until asked. An interviewer sees an unsanity-checked number
   as a judgement signal, not an arithmetic one. Habit: after every number, ask "does this compare
   sensibly to something I know?"
2. **Data residency when going multi-region.** In two mocks running you replicated all user
   personal data globally, even after raising GDPR/PII yourself and after it was explained
   today. For Revolut (an EU/UK-regulated bank) this is a likely probe.
3. **Model drift over the session.** You introduced concepts (`campaign_id`, content URL,
   idempotency, inbox, device tokens) or reversed decisions (sharding) without going back to the
   schema or diagram. Re-sync the canvas when something changes.

## D. Architectural gaps or inconsistencies

- "Since we don't need sharding" in the multi-region answer vs. sharding by user_id at 10x two
  turns earlier.
- The crash-recovery dedupe key uses `campaign_id`, which isn't in the `notifications` schema.
- A `delivered` status with no component receiving provider delivery callbacks/webhooks.
- The in-app inbox was in scope (stakeholder answer) but missing from diagram and schema; the
  channel enum has `app`, but that's push.
- Phase 1 plan: "1 month hot in DB, rest cold." Later: "151 TB for 5 years can live in one DB."
  The tiering was dropped without a reason.
- A CDN for internal user-ID target files.

## E. Missing non-functional considerations

- Delivery semantics: at-least-once plus dedupe is the right default, but it was never stated
  explicitly at the requirements level.
- Time zones / quiet hours for marketing; marketing consent (GDPR/ePrivacy) as distinct from
  "enabled".
- OTP secrecy: codes shouldn't be persisted in clear in `notifications` or logs, and expire after
  the TTL.
- PII shared with third-party providers (processor agreements, minimising what's in the message).
- Business-level observability: per-type end-to-end latency vs SLA, queue age per priority,
  provider acceptance/delivery rates, DLQ growth. Monitoring wasn't covered in this mock.
- Retention/TTL: 5 years only for mandatory types; everything else can expire.

## F. Over/under-engineering

- **Over:** caches for campaign targeting and file re-reads, a CDN for internal files, and an
  index per filterable column.
- **Under:** a per-channel sender layer (where provider rate limits, breakers and failover belong,
  once rather than four times), a delivery-callback ingestion path, and a contact/device registry.
- **Right-sized:** 4 priority queues, campaign jobs as a table + worker, a single DB at today's
  scale.

## G. What a strong Revolut candidate might have covered

- Architecture as **ingest → route/expand → per-channel senders**: priority queues feed routing
  workers (preferences, contact lookup, rendering), which feed per-channel queues and senders.
  Each sender owns its provider's credentials, rate limit, breaker, and **multi-provider failover**
  (SMS primary/secondary transparent to the user, with channel fallback as a second line).
- A **delivery status pipeline:** provider webhooks → status-update queue → notifications store.
  This is also what proves the regulatory "delivered."
- **Notifications log in an append-friendly store**, separate from users/preferences:
  time-partitioned, TTL for non-mandatory types, and a 5-year immutable archive (Object Lock) only
  for mandatory types.
- **Campaign expansion against a replica or analytics store, not the OLTP primary**, with a
  keyset-paginated cursor checkpoint and a unique (campaign_id, user_id, channel) constraint for
  idempotency.
- **Per-region user homing** (users served in their home region, data stays there), with
  campaigns fanned out per region. This is the data-residency-friendly alternative to
  active-passive.
- Quiet hours/time-zone-aware scheduling for marketing.

## H. Topics to practice before the next mock

1. **Estimation sanity drill:** 5 quick estimates (QPS, storage, bandwidth), each followed by an
   explicit comparison ("is X PB plausible? What's Revolut's whole data footprint?"). Use realistic
   mixes (weighted averages), not midpoints.
2. **Data residency by default:** for every multi-region answer, state which data stays in its
   home region and what (if anything) is replicated, minimised or pseudonymised. One sentence is
   enough, but it must come unprompted.
3. **Canvas re-sync habit:** at each phase boundary, re-read your schema and sticky notes against
   what you've said since, and fix drift aloud ("I introduced campaign_id, adding it to the
   schema").
4. **Close with risks, not a recap:** "With more time: (1) …, (2) …, (3) …."
5. Keep the core-first habit. It worked; make it the default opener after requirements.

## I. A better architecture (post-mock only, brief)

Producers (mTLS service identity / JWT for human operators, per-type RBAC) → Notification API
(validate, idempotency key, mandatory-type rules) → **priority ingest queues** (security/OTP,
transactional, marketing, others) → **router workers** (preferences + contact/device registry +
template rendering; drop or expand) → **per-channel queues** → **channel senders** (one per channel:
provider rate limits, breakers, primary/secondary provider failover, OTP TTL expiry) → providers.
Provider webhooks → status queue → notifications store (time-partitioned; TTL for non-mandatory;
immutable 5-year archive for mandatory). Campaigns: job table → expander reading from a
replica/analytics store with a keyset cursor checkpoint → marketing ingest queue, with
UNIQUE(campaign_id, user_id, channel). The in-app inbox is a per-user, read-optimised store written
by the router. Multi-region: users homed per region, notifications processed in the home region,
campaigns fanned out per region, nothing personal replicated globally.
