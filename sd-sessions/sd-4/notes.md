# sd-4 — Notification platform

Interviewer's running transcription — not candidate-authored. Updated per phase and on new
screenshots.

## Problem statement
Design a notification system that lets Revolut send messages to its users.

(Interviewer-private: domain chosen to vary from sd-1 P2P / sd-2 hotel / sd-3 card auth; tests
whether the candidate names the core hard part first — per sd-3 feedback — e.g. priority isolation
of critical vs bulk traffic, delivery guarantees/dedupe, third-party provider failure. Implicit
reqs available: marketing consent/GDPR, quiet hours/time zones, mandatory regulatory notices, PII
in message content.)

## Phase 1 — Requirements

### Stakeholder answers
- Channels (candidate listed push, websocket, HTTP polling, SMS, email): in scope = mobile push
  (iOS + Android, via Apple/Google push services), SMS (third-party SMS providers), email
  (third-party email provider), and an in-app notification inbox (history the user sees when
  opening the app or web). Real-time websocket delivery to web: not required — inbox read on open
  is enough.
- Q: does Revolut choose the channel? A: internal producer teams (cards, security, marketing,
  etc.) send by notification TYPE; each type has configured default channel(s). Users can turn
  some types/channels off in settings; some types can't be turned off. (Did not say which, or why.)
- Candidate modelled it as types x channels (good structuring ✅). Answers:
  - Preferences are per (type, channel) — e.g. payments only via push is allowed.
  - Mandatory (can't be disabled by user): security alerts (new device login, OTP/verification
    codes), legally required notices (T&C changes, regulatory notices). User can't opt out.
  - Revolut ops/product can enable/disable a type globally and change its default channels
    without a deploy (e.g. stop a broken campaign).

### Non-functional — stakeholder answers
- 50M registered users, 15M DAU.
- Transactional/event notifications (payments, security, etc.): ~5 per DAU per day avg; peak ~5x
  avg.
- Marketing campaigns: a few per week, a single campaign can target up to ~20M users at once;
  marketing wants it delivered within ~1 hour.
- Candidate to derive per-second numbers. (Expected: ~75M/day ≈ ~870/s avg, ~4.3k/s peak
  transactional; campaign 20M/3,600s ≈ ~5.5k/s sustained for an hour, on top.)
- Candidate: 868/s avg, 4.34k/s peak (correct ✅, arithmetic clean this time); "no write sharding
  needed for now". Campaign burst (20M/hour) not yet included in the estimate.
- Campaign: ~5.5k/s (correct ✅); worst case combined < 10k/s -> "no write sharding yet".
  ? ~10k writes/s on one primary is borderline, and each notification may fan out into several
    writes (inbox row + per-channel delivery status) — watch whether this is revisited in DB design.

### Implicit — surfaced by candidate (unprompted) ✅
- Asked about PII in content + legal audit (implicit req, unprompted, 2nd mock in a row).
- Answers: content can include name, amounts, merchant names, last 4 card digits; one-time codes
  are sensitive (secret). Never full card numbers/passwords. For mandatory/regulatory notices we
  must be able to PROVE we sent them (what, when, which channel, delivery outcome) — retain 5 years.
  Other notification types: no legal retention requirement.
- Asked notification size (1KB?). Reflected back as candidate's assumption; only stated content
  nature: push/SMS short text, emails rendered from templates (HTML) and can be larger.
- Size: SMS < 1KB, campaign emails with images ~1MB -> "average 500KB/notification".
  Storage: 10k/s x 86,400 x 365 x 5 = "1.576 TB".
  !! 10k x 86,400 x 365 x 5 ≈ 1.58 x 10^12 — that's the notification COUNT; the 500KB was never
     multiplied in (would be ~790 PB). Also: uses the 10k/s worst-case peak as a 24/7 average
     (real avg ≈ 870/s + a few campaigns/week); 500KB "average" of 1KB and 1MB ignores the mix
     (almost all are small); images would normally be stored once per template, not per
     notification; 5-year retention applies only to mandatory types.
  Probed: asked where the 500KB enters the calculation (not corrected).
- Explained 500KB as 50/50 split email vs text (the 50% email assumption itself is unasked and
  unlikely). Didn't notice the missing multiplication — asked once more whether 500KB is in the
  1.576 figure.
- Recomputed: ~157 PB/year (arithmetic now consistent with own assumptions). Reaction: "a lot",
  go to tiering (1 month in DB, rest cold) instead of questioning the assumptions that produced
  it. Asked one sanity-check question on plausibility.
- Re-asked campaign frequency ("1 per week, right?") — already answered: a few per week. Restated.
  Now recalculating from scratch.
- Clarified: "a few" = ~3 campaigns/week; not all target 20M (that's the max) — assume up to 20M.
- Self-correction ✅: store HTML/email bodies in object storage, keep only a URL reference in the DB
  -> ~1KB per notification record. (Whether a per-user rendered copy or a per-template copy is
  stored is not yet stated — matters for "prove what we sent" audit.) Recalculating.
- Recomputed: campaigns 20M x 3 x 52 x 1KB ≈ 3TB/yr; regular 15M x 5 x 365 x 1KB ≈ 27.4TB/yr;
  ≈ 30.4TB/yr; 5 years ≈ 151TB -> "can live in a DB". Arithmetic correct ✅.
  ? 151TB in a single relational DB is a big claim (vs earlier plan of 1 month hot + cold tier,
    now dropped); 5-year retention applies only to mandatory types, rest could be expired. Not
    probed.
  Phase 1 time: long (estimation took several rounds, three nudges total). Not yet asked: latency
  expectations per type (OTP vs marketing), delivery guarantees, availability.
- Latency SLA (by type, measured event -> handed to the channel provider):
  - Security / OTP codes: p99 ≤ 2s (codes expire after ~5 min; user is waiting on screen).
  - Transactional (payment, card events): p99 ≤ 10s.
  - Marketing: whole campaign within ~1 hour; individual latency doesn't matter.
  Deliberately NOT said: that campaigns must not delay OTPs — left implied by the numbers (core
  priority-isolation problem for the candidate to find).

### Phase 1 close (candidate-initiated)
Covered: channels, types x channels x preferences, mandatory types, volume (correct), PII + audit
(implicit, unprompted), storage (3 iterations), latency per type. Not asked: availability target,
delivery guarantee (at-least-once vs exactly-once / duplicates acceptable?), provider failures,
user time zones / quiet hours, marketing consent, template/localisation, producers' integration
(API vs events). Requirements phase ran long (estimation loop).

## Phase 2 — High-level design
### Verbal description (before screenshot)
- Queue system with priority queues: consumers scale independently per queue, and the shortest-p99
  types get prioritised ✅ — identified the core priority-isolation problem unprompted (sd-3 risk #1
  "find the core first" — positive signal).
- Mandatory notifications: consumer reads user contact info (phone, email, push device tokens) from
  DB, with a cache for read latency.
- Other notifications: consumer checks which users have this type enabled and on which channels.
- Preference/routing logic lives in the per-topic consumers.
  ? Same lookup logic duplicated in each consumer vs a shared component — watch.
  ? Fan-out for campaigns (20M users) — where the recipient list is expanded is unstated.

### Screenshot 01-hld.png (copied from ~/Downloads/mock_revolut_notifications.png)
Sticky notes: Functional — actor user: enable/disable notifications; actor Revolut: enable/disable;
invariants: some can't be switched off legally, enforced in backend (not just hidden in UI) ✅.
Non-functional: all numbers as stated verbally (868/4.3k, 5.5k campaign, <10k, 151TB/5y in one DB,
latency SLAs). Implicit: audit all sendings, treat PII.

Diagram: revolut (producers) -> LB -> API -> Queue Broker -> 4 queues {security & OTP,
transactional, marketing, others} -> 4 consumer groups (one per queue) -> each consumer group
fans out to SMS provider, Email provider, Android/iOS push providers, plus Read Cache and DB.

Observations (not raised):
- Box-level MVP ✅, priority isolation by queue + consumer group visible ✅.
- In-app inbox channel (stated in scope) not drawn.
- User preference management (sticky's "actor user enable/disable") has no path/component.
- Campaign fan-out: where a "send to 20M users" request is expanded into per-user messages
  is not shown (API? marketing consumers?).
- No delivery-status feedback from providers (needed for "prove delivery outcome" audit).
- No retries/DLQ/provider-failure handling (fine for MVP; watch Phase 3).
- Every consumer group talks to every provider directly — channel-sending logic (and provider
  rate limits/credentials) duplicated 4x; no per-channel sender layer.

## Phase 3 — Low-level design

### API flow
- POST /notifications, two shapes: (a) single-user notification; (b) campaign = targeting filter
  over users table columns (age, user type, products...) — "any indexed column".
- Single-user: API reads user_notifications (preference) -> enabled: enqueue to the type's queue;
  disabled: drop. Consumers read messages and send to the channels listed in the message body.
  ✅ Preference filtering before enqueue (pre-flow step sequenced before the main action).
- Campaign fan-out mechanics (who runs the 20M-row query, how 20M messages get enqueued, sync vs
  async, resumability) — not described. Probed.

### DB — SQL (relations), write primary + read replicas
- users(user_id PK, profile columns used for campaign targeting).
- user_notifications(id PK, user_id FK, notification_type IN (security, transaction, campaign,
  others), channel IN (app, email, sms), enabled bool, UNIQUE(user_id, type, channel)). Note that
  types could become a lookup table later (scoped simplification, stated ✅). Security removed from
  this table since it can't be overridden ✅ (invariant enforced by data model).
- notifications(id PK, user_id FK, notification_type (incl. security), channel, status IN
  (created, sent, delivered, failed), sent_at, delivered_at, created_at). sent = provider accepted;
  delivered = provider confirmed ✅ — maps to the "prove delivery outcome" audit requirement.
  Gaps: no content/content_url (audit "what was sent"), no producer idempotency key / event id
  (duplicate sends on retries), no campaign_id, no contact info / device tokens table (phone,
  email, multiple push devices), no default-preference semantics (missing row = ?). No indexes
  discussed yet. ~10k inserts/s + status updates on one primary not revisited.
- Campaign: API inserts a campaign_job row into campaign_jobs (async job ✅ — POST doesn't fan out
  synchronously). Paused to ask what targeting looks like.
- Stakeholder answer: a segment = combination (AND/OR) of user attributes — country, plan
  (Standard/Premium/Metal...), age range, holds product X, last active within N days. Sometimes the
  data team instead provides a precomputed list of user IDs (file upload).
- campaign_jobs: `query` column holding the AND/OR filter (nullable) OR `users_file_url` pointing
  to the ID file in file storage; consumed by a CampaignJobWorker.
  ? Storing a "query" — raw SQL (injection/arbitrary heavy query on prod DB) vs structured filter
    spec — unspecified. Where the 20M-row scan runs (primary vs replica) not stated yet.
- CampaignJobWorker: takes oldest job (FIFO), pages through selected users (users table via
  indexed filters, or file chunks), filters by campaign preference, builds batched messages with
  user+channels -> marketing queue -> CampaignQueueWorker sends. Job marked done once fully
  enqueued. ✅ Paginated, batched, async.
  ? "Index every filterable column" — write amplification on users, low-cardinality columns (plan,
    country) barely helped by B-tree; scan on primary vs replica unstated.
  ? Single worker taking jobs FIFO — concurrency of workers claiming jobs (SKIP LOCKED?) unstated.
  !! No progress checkpoint: crash after N of 20M enqueued -> restart from scratch -> duplicate
     marketing messages to N users (no idempotency key in schema). Probed with crash scenario.
- Crash answer: (1) idempotency — drop if a notification with (user_id, type, campaign_id) is
  "already delivered"; (2) better: checkpoint the number of messages already queued, resume from
  the last processed batch; (3) cache to avoid re-reading file / re-querying DB.
  ✅ Both layers (checkpoint + idempotent consumer) named, unprompted second layer.
  Nuances for review: dedupe on "already delivered" misses in-flight/sent ones — should be
  "already exists/created" (unique constraint on (campaign_id, user_id, channel)); a count/offset
  checkpoint is unstable if the users table changes mid-campaign — keyset cursor (last user_id,
  ordered) is stable; checkpoint written after enqueue still leaves a last-batch duplicate window
  that dedupe must cover; the cache adds little.

### Infra / failure handling (candidate-led)
- Recap: DB covered; cache for users-to-notify and user_notifications config.
- Queue: replicated broker, messages persisted to disk, replica takes over on failure ✅.
- DLQ for poison messages (always-failing) for investigation ✅.
- Per-provider rate limiters (respect provider throttling) + circuit breakers (cut a degraded
  provider) ✅.
- Backpressure: on degradation, throttle producers — block campaign launches, rate-limit the
  low-priority "others" group ✅ (graceful degradation by priority, unprompted — strong).
- Not said: what happens to messages while a provider's breaker is open (held in queue? rerouted?),
  especially OTP via SMS with a 2s SLA. Probed with a scenario.
- Answer: fallback channel — send OTP via email or app push instead; let the user choose the
  channel. Reasonable user-facing degradation ✅. Not considered: a secondary SMS provider (the
  standard redundancy for a critical channel — failover within the same channel, transparent to
  the user), security trade-off of moving OTP to email, what happens to messages already queued
  for SMS while open (expire after the code's 5-min TTL rather than send late).

### Security
- Mask/obfuscate PII in logs; mTLS for internal service-to-service; sensitive data in a vault,
  referenced by token in DB and traffic ✅. (Direct application of the sd-3 post-review explanation
  given earlier today — same-day transfer, weaker evidence than independent recall.)
- Not covered: authN/authZ of producers on POST /notifications — which team may send which type
  (a producer tagging marketing as "security" would bypass opt-outs and the legal invariant);
  OTP code handling (stored? hashed? kept out of logs/notifications table); encryption at rest;
  third-party providers receiving PII (DPAs). Probed the producer-authz scenario.
- Answer: per-type authorization — security/OTP only from automated system producers; campaign
  team role can only create campaign notifications; humans authenticate via auth service -> JWT
  with role; API denies type outside the role ✅. JWT correctly applied here (human operators),
  distinct from system producers. (Service producers' auth — mTLS identity — implied, not stated.)

## Phase 4 — Scaling (candidate-initiated)
- Horizontal scaling of API and each worker group independently (per notification type); more read
  replicas; more queue partitions. Generic — no bottleneck identified, no local->regional->global
  framing yet. Pushed: 10x scale, what's the first thing that doesn't scale horizontally?
  (Interviewer expectation: single write primary — each notification = insert + sent update +
  delivered update ≈ 3 writes -> ~30k/s at today's peak, ~300k/s at 10x; provider rate limits.)
- Bottlenecks named: DB writes and channel providers ✅ (both correct).
  - Providers: multiple providers or pay for higher limits (multi-provider now raised — as capacity,
    not as redundancy for OTP earlier).
  - DB: at 50-100k writes/s shard; key = user_id ✅; trade-off stated: campaign targeting becomes
    scatter-gather across all shards ✅; mitigate with a Redis cache-aside for similar targets
    (weak — segments rarely repeat exactly, and cache of 200M IDs is large).
  - Not stated: writes per notification (status updates multiply it), separating the append-heavy
    notifications log from users/preferences (different stores), archive/TTL of non-mandatory rows.
- Asked local -> regional -> global step (not raised by candidate).
- Multi-region plan (table by table):
  - users: read-mostly -> replicate globally ("cheap and faster").
  - user_notifications: replicate, master in first region (Europe).
  - campaign_jobs, notifications: master writes in Europe, replicas elsewhere as fallback.
  - CampaignJobWorker, queues, queue workers: active in Europe, passive elsewhere.
  - Failure: Europe loses connectivity -> stops writing; US promotes DB replicas + queues (disk
    replicated) + workers. Global: priority list, first region with majority connectivity takes
    master (same quorum pattern as sd-3 ✅ consistent).
  !! Replicating ALL users' PII (users table) to every region — same GDPR/data-residency gap flagged
     in sd-3 and explained in the post-sd-3 Q&A today; recurred unprompted. Not probed.
  !! Active-passive: every non-EU notification crosses to Europe and back (fine vs 2s SLA, but
     unstated), passive stacks idle (cost not discussed), all writes still to one region despite
     the sharding just proposed. Choice stated without justification — asked why active-passive
     over per-region active.
  Async replication RPO at failover (lost/duplicated notifications, queue replication lag) not
  discussed.
- Trade-off answer: single write location = simple strong consistency, no distributed txns;
  passive regions kept at minimum scale and autoscaled on failover (cost ✅, first time cost
  reasoning appears in an SD mock); cross-region 100-150ms is fine against 2s/10s/1h SLAs (latency
  vs SLA justified ✅); campaigns can target users across regions anyway. Well-structured,
  multi-point justification ✅.
  !! Internal inconsistency: "since we don't need sharding" — two turns earlier proposed sharding by
     user_id at 10x. Also: what invariant needs strong cross-region consistency here? Per-user
     sharding has no cross-shard transactions; notifications are per-user and idempotent, so
     per-region active (users homed by region) was viable — not explored. Not probed.

### Candidate's summary
- API + workers + prioritised queues (absorb peaks, latency for top-priority types); Redis cache
  for campaign targeting; DB indexes for targeting queries; NEW: CDN to cache user-ID files and to
  serve HTML/static assets for campaign emails.
  CDN for email images ✅ (right use: emails reference hosted images). CDN for internal user-ID
  target files ✗ — internal batch input read once by a worker, gains nothing from edge caching,
  and puts a list of user IDs (personal data) on public edge infra.
  Summary is a recap, not a list of open risks/next steps (yet).
