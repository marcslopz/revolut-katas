# Current Coaching Priorities — System Design

_Last updated: 2026-09-29, after sd-2 (second full mock, global hotel booking, BORDERLINE)._

## Overall trend

Two data points, both BORDERLINE, but for different reasons — this itself is worth tracking:

- **sd-1**: pacing control was the dominant problem (4 interviewer redirects, one mechanism ate the
  session).
- **sd-2**: zero pacing redirects needed, and clear improvement on proactive trade-off narration —
  but the session ended inside Phase 3, having never reached Database Design in depth, Security
  beyond JWT, or Phase 4 (Scaling) at all, and closed with the candidate asking the interviewer
  "anything else?" instead of naming the remaining gaps themselves.

Read together: the *loud* form of the session-leadership problem (visible pacing failures) is
improving, but a *quieter* form (running out of self-generated structure before the session's
scope is actually complete) is still present and is arguably harder to self-detect, since nothing
felt obviously wrong in the moment. Two technical items flagged after sd-1 (distributed-transaction
vocabulary precision, and the "is there an invariant" pattern-selection habit) are now confirmed
resolved by sd-2 — see RESOLVED below.

## RECURRING WEAKNESSES (aggregated view)

- **Reactive rather than proactive self-catch / trade-off surfacing** — the chronic Build It
  weakness (12+ mocks, see `coaching/current-priorities.md`'s top RECURRING WEAKNESSES item and
  [[weak_areas_backend_concurrency]]), confirmed in System Design at sd-1 and **improving** at sd-2:
  communication score rose 3→4, with three unprompted trade-off statements in sd-2 versus zero in
  sd-1 (single-writer consistency rationale, cache eventual-consistency rationale, circuit-breaker
  addition). Not resolved — the EU-region SPOF trade-off in sd-2 still needed two interviewer
  follow-ups to surface fully — but a genuine, measurable improvement, not just noise.
- **Implicit requirements not proactively surfaced** — upgraded from a 1-data-point MEDIUM flag to a
  confirmed recurring weakness: sd-1 (AML/compliance, fintech prompt) and sd-2 (PCI/payment-data
  handling, a design that directly calls a payment provider) both show zero unprompted implicit
  requirements. Two fintech-adjacent prompts, same exact gap both times.

## RESOLVED (confirmed by a full mock)

Per [[coaching-drill-vs-mock-evidence]]: coaching-session/drill evidence alone never promotes an
item here — only a full mock under `modes/system-design/interviewer.md` does. sd-2 is that mock for
both items below.

- **Distributed-transaction vocabulary/mechanics precision** — sd-1 conflated 2PC with the
  outbox+queue pattern and called a post-commit reversal a "rollback" instead of a compensating
  transaction. The 2026-09-29 coaching pass taught the levels explicitly (outbox → Saga → 2PC →
  2PC+consensus) and drilled it once informally; sd-2 then showed correct terminology and correct
  pattern selection throughout a real mock with zero prompting needed on vocabulary — Saga chosen
  correctly over 2PC, idempotency-key handling correct, "rollback" used correctly (pre-commit, so
  it was actually the right word this time). Resolved as of sd-2 — watch for regression under
  pressure in a future mock rather than treating this as permanently closed.
- **"Is there an invariant, and how much tolerance does it have?" before picking a pattern** — first
  surfaced and drilled in the 2026-09-29 RAPID SD DRILL (recurred across 3 of 5 drill scenarios).
  sd-2 confirmed it generalizes under real mock pressure, unprompted, twice: the room-hold design
  (short atomic status-flip instead of holding a lock through an external payment call) and the
  cache design (accepted eventual consistency for search/availability because the real invariant —
  no double-booking — is enforced at booking time, not at read time). Resolved as of sd-2.

## CURRENT PRACTICE PRIORITIES (mock-derived)

**HIGH — Session leadership / self-managed session completeness (evolved from sd-1's pacing framing)**
Recurring: yes (2/2 mocks), but the *shape* of the gap changed between mocks — track both forms.
Evidence: sd-1 — 4 interviewer redirects on pacing, one mechanism consumed the session. sd-2 — zero
pacing redirects, but the session ended inside Phase 3 (Database Design left shallow, Security
narrowed to JWT-only, Phase 4/Scaling never reached), and closed with the candidate twice handing
structuring back to the interviewer ("ask me any questions about edge cases or whatever", "anything
else?") rather than naming and closing remaining gaps itself.
Problem: per Karim's email this is a first-class, separately graded criterion. sd-2 shows real
progress on the loud symptom (visible pacing chaos) but a quieter, still-unresolved symptom
(session ending before its scope is actually complete, with structure handed back to the
interviewer) — arguably harder to self-catch because nothing felt obviously wrong in the moment.
Drill: two standing habits — (1) at roughly the session's midpoint, explicitly name out loud which
of the 4 phases are still untouched and budget remaining time across them; (2) ban the phrase
"anything else?" — replace with self-naming the specific remaining gaps ("I haven't covered
sharding or security — let me do both now") before the interviewer ever has to ask.

**HIGH — Implicit requirements not proactively surfaced (upgraded from MEDIUM, now recurring)**
Recurring: yes (2/2 mocks — sd-1: AML/compliance/audit-trail; sd-2: PCI/payment-data handling).
Evidence: two different fintech-adjacent prompts, same exact requirements-phase gap both times,
zero improvement between mocks. **Update 2026-09-30**: dedicated coaching drilling now done — a
domain-family reference table added to `coaching/sd-interview-checklist.md`, plus 4 scenarios
practicing unprompted implicit-requirement naming (personal lending, P2P car rental, teen social
app, telemedicine) and 6 scenarios practicing the adjacent actor-identification skill (F of F-N-I).
Domain-family filtering discipline (use the *right* family's items, don't cross-contaminate) landed
within the session — two misapplications early on, both self-corrected in one challenge, clean from
scenario 3 onward. Still coaching evidence only, not mock evidence — per
[[coaching-drill-vs-mock-evidence]] this does not resolve the item.
Problem: requirements-phase completeness gap specific to the "implicit requirements" bucket Karim
named directly — reasoning/discipline now practiced, but real-interview-pressure generalization
unconfirmed.
Drill going forward: the standing habit (name one compliance/regulatory/PII implicit requirement
unprompted, for any fintech- or domain-sensitive prompt) is now backed by reference material — the
next signal to watch for is whether it surfaces unprompted in sd-3's actual Phase 1, with none of
today's scaffolding present.

**MEDIUM — Reactive rather than proactive self-catch (recurring, cross-track, improving)**
Recurring: yes, cross-track (Build It: 12+ mocks; System Design: 2/2, but trending better).
Evidence: sd-1 — quietly relaxed the p99 SLA without flagging it; needed several follow-ups to reach
the 2PC-blocking conclusion. sd-2 — three proactive trade-off statements unprompted (up from zero),
but the EU-region SPOF was only fully reasoned through after two interviewer follow-ups.
Problem: same chronic structural weakness underneath several Build It items, now showing genuine,
measurable improvement in System Design specifically — downgraded from HIGH to MEDIUM to reflect
that trend, not because it's resolved.
Drill: at natural checkpoints, explicitly ask "what did I just change that contradicts something I
said earlier?" out loud, before the interviewer has to ask it — keep going, this is working.

## Positive signals worth reinforcing (not gaps)

- **Cross-mock generalization, confirmed**: the short-atomic-lock + transactional-outbox pattern was
  taught explicitly, drilled once informally (2026-09-29), then reproduced correctly and unprompted
  under real sd-2 mock pressure — the clearest evidence so far that a coaching lesson survives past
  the session it was taught in and into live interview conditions.
- Idempotency-key + duplicate-check handling — now confirmed 2-for-2 in System Design (sd-1, sd-2)
  on top of an already-strong Build It record.
- Quick, non-defensive self-correction whenever challenged directly, across both mocks.
- sd-2 specifically: unprompted circuit-breaker proposal when asked what was still missing — a
  correct, well-targeted answer even if the follow-up on its exact behavior was thin.

## PRACTICED IN COACHING — AWAITING NEXT MOCK VERIFICATION

Per [[coaching-drill-vs-mock-evidence]]: this is coaching-session evidence, not mock evidence — it
can surface or reinforce a gap, but doesn't promote anything to RESOLVED. Only a future full mock
does that. (Two prior entries here — the RAPID SD DRILL and the strong-consistency teaching pass —
are now confirmed by sd-2 and have moved to RESOLVED above.)

Next candidates for a coaching drill, per the CURRENT PRACTICE PRIORITIES above: requirements-phase
implicit-requirements habit (zero improvement so far, may need dedicated drilling rather than a
standing reminder), and session-completeness time-boxing (new instantiation of the session-
leadership gap).

- **2026-09-30 — back-of-envelope numeracy + storage-selection drill (2 scenarios), building the
  new `coaching/sd-interview-checklist.md` script.** Grew out of the candidate flagging that they
  find it hard to remember every point to cover per phase ("me resulta dificil acordarme de todos
  los puntos"), and separately that they didn't see the point of asking for NFR numbers if the
  numbers "don't change the design." Built a memorization script (F-N-I / skeleton / D-I-S-E / L-R-G
  mnemonics + mid-session checkpoint + a "never say anything else?" rule) directly targeting sd-2's
  session-completeness gap, plus reference tables (5 anchor capacity numbers, storage-technology
  decision table) now persisted in that file for standing use.
  - Scenario 1 (photo-sharing app): first attempt had a real conceptual unit error — multiplied DAU
    by 7 to "get a week's worth of users" (140M) instead of recognizing DAU already represents the
    recurring daily user base the weekly per-user rate should apply to directly. This inflated WPS
    7x (462 vs. correct 66) and drove an incorrect sharding-from-day-1 conclusion. Self-corrected
    within one challenge once the conceptual error (not just the arithmetic) was named, and
    correctly reversed the sharding conclusion using the corrected number — a clean demonstration of
    why the NFR math matters (it can flip a real architectural decision), which is the candidate's
    own original question, now closed with a concrete example.
  - Scenario 2 (ride-hailing GPS pings): math was correct on the first attempt this time (no repeat
    of the DAU-conflation error) — 312.5K writes/sec average, 3.12M peak. But then reached by reflex
    for "shard a relational DB into 10,000 pieces" rather than questioning whether the access pattern
    (overwrite a driver's current position) needed a relational store at all. This is the same
    reach-for-the-familiar-tool instinct as the RESOLVED "is there an invariant" item, but applied to
    a different axis — storage *category* fit, not invariant strength. Self-corrected in one
    challenge to Redis (pure key lookup, no relational need), then correctly recognized unprompted
    that a single Redis node's throughput ceiling (per the anchor-numbers table, hundreds of
    thousands of ops/sec) is still below the 3.12M peak, landing on Redis Cluster.

  Coaching evidence only, not mock evidence — worth watching in a future mock whether "match the
  access pattern to the storage category, don't default to sharding what you already know" holds up
  under live pressure, the same way the original invariant-check habit did.

  - Scenario 3 (banking audit log): storage growth over 3 years + sharding decision + hot/cold
    tiering (recent data in the operational store, older data archived to S3/Glacier) — the
    strongest, most complete answer of the whole session, correct on the first pass.
  - Scenario 4 (video streaming bandwidth + CDN offload + origin node count): correct instinct on
    CDN as the standard fix for massive aggregate bandwidth (connected unprompted to the "celebrity
    problem" from the earlier Design Twitter study video), then correctly generalized the
    node-count formula (total demand ÷ per-node capacity + redundancy margin) from the earlier
    Redis Cluster reasoning in scenario 2 to a completely different resource type (network
    bandwidth) — a second instance of a lesson transferring across contexts within one session.
  - Scenario 5 (SLA/availability budget: 99.9% vs 99.99% downtime-per-year, then whether a 30-40 min
    failover fits the annual budget): recurring error type surfaced 3 times today — forgetting to
    convert a percentage to a decimal fraction (dividing by 100) before using it in a calculation,
    each time producing an answer off by a clean power of 10. Self-corrected each time once
    challenged. Also caught, live, a good general debugging technique worth reinforcing: comparing
    the *relationship* between two related computed values (more nines should mean less downtime,
    not more) to sanity-check a result without redoing the full calculation.
  - Process note, not a candidate gap: I (the coach) misread the candidate's Spanish-locale decimal
    comma as an English thousands separator twice in this session, wrongly "correcting" one answer
    that was actually right. Logged to personal memory
    (`feedback_spanish_decimal_notation`) so it doesn't recur in future sessions.

  Overall pattern for today's numeracy drilling: the recurring failure mode isn't conceptual
  (storage-category choice, sharding-vs-not judgment, CDN/tiering instincts were all sound or
  quickly self-corrected) — it's mechanical: percent-to-decimal and unit-magnitude (Mega/Giga/Tera)
  conversion slips, consistently self-caught in one challenge once flagged. Worth a lighter-weight,
  higher-repetition drill (many quick unit-conversion reps) rather than another full scenario cycle,
  if this resurfaces.

  - Scenario 6 (push-notification flash sale: audience %, QPS to hit a time window, delivery
    success %): first scenario of the session with a clean pass on percent math, no conversion
    error — the mechanical slip from scenarios 1/3/5 may already be settling with repetition.
    Third independent application of the "total demand ÷ per-node capacity" formula (after Redis
    Cluster in scenario 2 and origin bandwidth nodes in scenario 4), this time to queue consumers —
    the generalization is holding up cleanly across a third, unrelated resource type.
  - Scenario 7 (search autocomplete: QPS math clean again, then storage-type choice) — QPS math
    correct with no conversion error. But the storage pick was a genuinely new failure mode, and the
    most over-engineered instinct of the session: proposed using an LLM for prefix completion,
    reasoning "it's a perfect text predictor." This is the *opposite* direction from the earlier
    "reach for the familiar heavy tool" pattern (that was about defaulting to known distributed-
    systems machinery like sharding/2PC) — this is reaching for a trendy ML solution that is both
    far too slow/expensive for the latency+QPS budget AND solves the wrong problem (generates
    plausible text instead of surfacing what other users actually searched). Corrected directly
    (not self-corrected — this was a genuine knowledge gap, not a pressure slip) to the standard
    pattern: a precomputed Trie or Redis sorted set (`ZRANGEBYLEX`) built offline from real query
    logs. Worth watching for in a future mock — an LLM-shaped answer to a component that should be a
    simple precomputed lookup.
  - Scenarios 8-14 (URL-shortener keyspace sizing, celebrity fanout, latency-budget decomposition,
    Little's Law concurrency, infra cost estimation, cache working-set sizing, hot-shard/skew):
    broadest single-session coverage of calculation *types* yet — combinatorial keyspace sizing,
    burst/instantaneous load, additive latency budgets across a sync call chain, queueing-theory
    concurrency, $ cost trade-offs, memory-capacity sizing, and skewed-key hot-shard risk, on top of
    the throughput/storage/percent/bandwidth types from scenarios 1-7. Notable moments:
    - Scenario 8: a genuine input-transcription slip (read "500M" as "50M"), different in kind from
      the percent/unit-conversion errors earlier — correctly self-corrected, and correctly explained
      *why* it didn't change the final answer (base62's exponential growth absorbs a 10x input
      error in this range), a useful nuance rather than just a lucky pass.
    - Scenario 9 (celebrity fanout): initially proposed a heavier fanout-on-write-via-sharded-Redis
      alternative alongside the correct fanout-on-read answer; the real gap surfaced was a common
      misconception that fanout-on-read implies slow reads from a DB — didn't initially realize
      celebrity content is itself highly cacheable regardless of fanout direction. Self-corrected
      cleanly once challenged, landing on the standard hybrid (push for normal users, pull+cache for
      high-follower accounts) with a well-reasoned threshold-by-ops/sec framing.
    - Scenario 10 (latency budget): small arithmetic slip (dropped one line item summing the
      synchronous call chain, 130ms vs. correct 125ms remaining budget) — same "don't drop a term"
      discipline theme as the rest of the session. Design reasoning itself was strong: correctly
      distinguished a precomputed/independent risk signal (fine to run "before" authorization) from
      a transaction-dependent fraud check (needs async + compensation, correctly named unprompted).
    - Scenarios 11-14: clean passes throughout — Little's Law applied correctly for WebSocket
      concurrency sizing, cost trade-off math correctly used to justify the earlier hot/cold storage
      tiering decision in dollar terms, cache memory sizing correctly checked against a node-RAM
      threshold instead of assuming sharding was needed, and — the strongest moment of this back
      half — correctly identified a hot-shard risk hiding behind a healthy system-wide average, then
      unprompted named the real cost of the fix (subsharding one outlier hotel sacrifices the
      single-shard read locality every other hotel still has).

- **2026-09-30 — F (functional requirements) practice: actor identification.** First time this
  specific sub-skill was drilled (F itself hasn't shown up as a gap in either mock, unlike N and I,
  but "for whom" — identifying every actor type, not just the obvious one — was untested). Prompt:
  food-delivery platform. First pass named only 2 of 3 actors (consumer, restaurant owner), missing
  the delivery driver entirely — the role that makes "delivery" the point of the whole system.
  Self-corrected in one challenge once pointed at the verb "reparto" in the prompt itself, then
  correctly built out the driver's full lifecycle (pickup → in-transit status → deliver) unprompted.
  Closing heuristic given: parse the verbs/nouns in the problem statement itself for implied actors
  before closing the requirements phase. One data point — watch whether actor-completeness holds up
  in a future mock's Phase 1.

  Continued across 6 total F scenarios (food delivery, medical appointments, event ticketing,
  crowdfunding, insurance claims, bank account/KYC onboarding) — three distinct sub-skills drilled:
  (1) finding a hidden actor via noun/verb parsing (food delivery, ticketing) or via business-risk
  reasoning when no noun points to it (crowdfunding's moderator — explicitly connected in-session to
  the I skill: "who gates this for implicit-risk reasons" is the same muscle as implicit
  requirements, just applied to actors instead of requirements); (2) operation symmetry — every
  create/accept also needs its cancel/reject counterpart (medical appointments); (3) not correctly
  identifying an actor when there isn't a third one, and instead catching domain-genericity —
  insurance claims was modeled as a generic support-ticket system at first, missing
  claims-specific operations (evidence submission, an actual accept/reject decision vs. a generic
  status change) until pushed. Bank account/KYC onboarding (F-6, the closest domain to Revolut's
  actual business) was solved correctly on the first pass with no missing actor — good sign this is
  becoming reliable.

  Then pivoted to 4 dedicated I scenarios (personal lending, P2P car rental, teen photo-sharing
  social app, telemedicine), each testing the same discipline from a different angle:
  - Personal lending: first pass wrongly imported booking-family items (double-booking invariant,
    cancellation policy) into a non-booking domain — a direct violation of the "identify the domain
    family first" instruction given minutes earlier. Self-corrected when challenged, and the
    lending-specific items taught (responsible lending/affordability check, interest rate caps,
    credit bureau reporting) were then applied correctly.
  - P2P car rental: the mirror-image error — over-applied a fintech item (AML) to a non-financial
    marketplace, while under-applying genuine booking-family items (no-double-booking, cancellation)
    that *do* belong here. Self-corrected both directions when challenged on each specifically.
    Domain-specific check (driver's license) was named correctly unprompted; a second, non-standard
    guess (criminal background check) was gently downgraded; insurance/liability (arguably the
    single most important implicit requirement for this domain) had to be taught directly.
  - Teen photo-sharing app: correctly named GDPR, content moderation, and age verification
    unprompted — but stopped at "verify age" without the follow-on regulatory step (COPPA/GDPR
    Art. 8 parental consent) that age verification exists to trigger. Genuine knowledge gap, taught
    directly.
  - Telemedicine: correctly named GDPR, health-data protection/consent, and mandatory record
    retention unprompted, cleanly scoped to the healthcare family with no cross-contamination from
    other families — the best-scoped first pass of the four. Missed the telemedicine-specific
    cross-jurisdiction medical licensing issue (a doctor needs to be licensed where the *patient* is,
    not just be "a licensed doctor") — genuine knowledge gap, taught directly.

  **Overall read on the I item**: the domain-family filtering discipline (don't drag items across
  families) is landing — both misapplications today were caught and corrected in one challenge each,
  and by scenario 4 the family-scoping was clean from the first pass. What's still genuinely missing
  is domain-specific knowledge beyond the taught framework (lending affordability rules, car-rental
  insurance, COPPA/GDPR Art. 8 parental consent, cross-border medical licensing) — these are facts
  to accumulate, not a reasoning gap, and each was absorbed in one pass once taught. This is
  coaching evidence only; the real test is whether unprompted implicit-requirement-naming shows up
  in sd-3's Phase 1 without any of this scaffolding present.

- **2026-10-01 — Skeleton (Phase 2) practice, 3 scenarios drawn in Excalidraw (QR payment, insurance
  claims, doctor appointments), then one full D-I-S-E (Phase 3) deep-dive on a subscription billing
  system.** Context: skeleton was never a weak area (4/5 both mocks) — practiced anyway to build
  habit; D-I-S-E was the real target, since sd-2 scored DB design 2/5 (never reached) and Security
  2/5 (JWT only).

  **Skeleton (3 diagrams)**:
  - QR payment service: missed the auth/pre-flow step entirely on first pass (self-corrected to an
    Auth Service box when challenged); initially defended a single monolithic "API Service" doing
    everything, then correctly distinguished that as a deployment choice, not an excuse to skip
    naming distinct logical responsibilities (echoing sd-2's "not a monolith-in-boxes" finding
    directly — same critique, same self-correction once reconnected to its source).
  - Insurance claims: auth correctly gated both actors unprompted this time (direct improvement).
    Unprompted, correct generalization of the hot/cold storage-tiering pattern (from an earlier
    numeracy scenario) into an "archive worker" component — a coaching lesson surfacing correctly in
    a completely different exercise type. But two explicitly-given F operations ("revisar
    reclamación", "consultar estado") were dropped from the diagram — candidate's own explanation:
    preferred a cleaner base-skeleton-plus-per-action-diagram technique and deferred fixing it to the
    next scenario (a reasonable diagramming practice, validated as such, but completeness doesn't
    automatically follow from better diagram hygiene — flagged as a distinct axis).
  - Doctor appointments: applied the previous scenario's feedback immediately — explicitly listed
    read actions separately from write actions for both actors, closing exactly the gap just
    flagged. Correct scale math (20k/day → 0.23 writes/sec → no sharding) and detailed, well
    thought-out AUTH flow — which surfaced a genuine design flaw (JWT validated via a network
    round-trip to Auth Service on every request, defeating JWT's main advantage over opaque session
    tokens). Self-corrected immediately to local signature verification once challenged, then
    correctly extended to asymmetric (RS256) vs symmetric signing and why distributed verifiers
    need asymmetric. Follow-on Q&A (not evaluated, pure teaching) covered OAuth/OIDC federated login
    end-to-end (authorization code exchange, ID token vs access token, scope-based authorization,
    refresh tokens) and a sharp, candidate-initiated security question: if auth is federated via
    Google, where does a domain-specific role (doctor vs. patient) come from, and can the frontend be
    trusted to assert it? Correctly intuited the answer should not be "trust the client" before being
    told; the resolved pattern (never trust client/IdP for role claims, resolve against your own DB,
    mint your own signed JWT) is now in the checklist's Security section.

  **D-I-S-E deep dive (subscription billing system)** — the strongest single Phase-3 walkthrough of
  the whole prep:
  - *D*: correct scale math (0.77 writes/sec, no sharding), SQL choice justified with a concrete
    example (not generic "transactions are good for payments") once pushed once. First schema draft
    had four real gaps — missing idempotency_key on `payments` (despite having just described a
    retry flow that needs it), missing subscription status/next-billing-date entirely (making the
    stated cancel-subscription requirement and the scheduler mechanism both unimplementable against
    the schema as drafted), a `CHECK` constraint typo, and a `NOT NULL` column (`invoice_url`)
    directly contradicted by the status enum including `'creating'`. All four corrected in one pass,
    including a technically correct idiomatic SQL fix (`CHECK (status != 'completed' OR url IS NOT
    NULL)`). Indexing: correctly ordered a composite index (equality column before range column, a
    common error point) unprompted, then needed one nudge to recall that Postgres does not
    auto-index foreign keys (unlike MySQL/InnoDB) — once reminded of the actual F operations list,
    correctly derived exactly one missing index (`invoices.user_id`) and correctly ruled out the
    others as PK-based.
  - *I*: full outbox-driven saga (payment leg → invoice leg) with correct transactional precision —
    when pushed on whether the payment-completion transaction also atomically writes the
    invoice-trigger outbox message (not a separate, riskier step), confirmed yes correctly. Caught
    and resolved an internally ambiguous description (sounded like two different invoice-creation
    trigger mechanisms, a DB poller and an outbox consumer) when asked to state the single trigger
    path explicitly — confirmed only one, and correctly named it as a two-step saga unprompted.
    Deliberately minimal caching (no cache unless read replicas can't meet the SLA) — good restraint,
    not reflexive over-engineering.
  - *S*: PCI/tokenization and encryption-in-transit (TLS termination at LB) correct by default.
    Initially proposed CDN-served invoices with no access control until prompted — correctly reached
    for signed URLs, justified the choice over a password-protected-PDF alternative on a genuine
    user-experience trade-off once asked to commit to one. Encryption **at rest** was dropped
    entirely on the first pass (only "in transit" was covered despite the topic naming both) —
    corrected cleanly once flagged (column-level encryption via a Postgres extension, or
    volume-level). Rate limiting's first answer ("the cloud provider handles it") was a real gap —
    too vague to count as a design decision; second attempt (per-user, per-endpoint, calibrated to
    real read/write ratio) was adequate.
  - *E*: correctly reasoned through worker-crash durability, duplicate-payment idempotency, and
    short vs. long payment-provider outages (circuit breaker). Two follow-ups needed: the "abandoned
    message" detect/recover mechanism (resolved correctly and precisely — ack/visibility-timeout
    redelivery, DLQ as backstop) and, strongest moment of the whole session, the **post-outage
    backlog recovery** question — unprompted connected it to the earlier celebrity-fanout numeracy
    lesson about bursts, and proposed a half-open circuit breaker with a rate-limited, gradually
    increasing throughput ramp — structurally the same pattern as their own canary-deployment design
    from the Infra section, applied to traffic instead of code, without being told to make that
    connection.

  **Net effect on tracked priorities**: this is the single most convincing coaching-session evidence
  yet that the two weakest sd-2 scores (Database design 2/5, Security 2/5) reflect a *coverage* gap
  from running out of session time, not a *reasoning* gap — once given the time and prompting to go
  deep, both were handled with real precision, including catching self-made schema inconsistencies
  unprompted-adjacent (quick once flagged) and generalizing patterns across completely different
  problem types (storage tiering, canary rollout, burst handling) without being told to. Per
  [[coaching-drill-vs-mock-evidence]], still coaching evidence, not mock evidence — the real test is
  whether this depth survives under sd-3's actual time pressure, where Database/Security/Scaling
  have to compete for the same clock as everything else, which is precisely the sd-2 failure mode
  this needs to overcome.

  **Same session, continued — L-R-G (Phase 4) on the same subscription billing system, pushed to
  200M subscriptions across EU/US/APAC.** Correct scale math (200M/month → 77 writes/sec, still
  below the sharding threshold). First pass gave a complete, well-reasoned global end-state directly
  — including, unprompted, a replica-promotion failover mechanism for the single-write-region SPOF,
  a direct, concrete improvement over sd-2's real mock (where that same SPOF was accepted with zero
  mitigation). But skipped the explicit local→regional→global staged narrative Karim's framing asks
  for — same "jump to the answer" pattern as elsewhere today, applied to narrative structure rather
  than technical content; redirected and corrected immediately when asked to re-narrate in stages.

  The standout moment of the whole two-day session: asked to identify what's genuinely new at 3+
  regions vs. 2, candidate initially said "nothing, same problem" — then, under challenge, surfaced
  the real split-brain risk in their own proposed priority-ordered failover list (a static list
  doesn't verify the old leader actually stopped, so an isolated-but-alive EU plus a promoted US
  produces two simultaneous write-leaders). First correction attempt (decide master by comparing
  "majority of traffic" between regions) was reasonable-sounding but logically circular — correctly
  diagnosed in the teaching pass as impossible to measure *during* the very partition it's meant to
  resolve. Second attempt, after being taught the quorum-of-replica-nodes mechanism (not traffic, not
  external visibility — each node unilaterally counts how many of the known node set it can currently
  reach), correctly synthesized a working mechanism: self-demotion on loss of quorum, priority-list
  as tiebreaker among the majority side only. This is genuinely advanced material (the core mechanism
  behind Raft/Paxos, explicitly flagged as a "stretch" DDIA chapter never completed in the theory
  pass) — worked through to a correct answer via teaching plus two iterations, not recalled from
  prior study.

  Degraded-mode question (what to deliberately let degrade under stress): correctly identified
  billing/invoice processing as the right thing to deprioritize (already async, wide tolerance
  window, vs. tight-SLA interactive user requests) and, once pushed for the concrete mechanism,
  named pausing/rate-limiting the scheduler — the same mechanism already designed for payment-
  provider-outage recovery, now correctly reapplied symmetrically for self-protection under load.

  **Overall**: this is the strongest technical session of the whole prep arc. The real open question
  is unchanged from the D-I-S-E entry above — everything demonstrated today required coaching time
  and, in the quorum case, direct teaching of genuinely new material; sd-3 is what tests whether any
  of it holds up unprompted, under the clock, without a coach available to redirect when the
  narrative jumps ahead of itself.
