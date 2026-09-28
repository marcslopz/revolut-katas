# System Design — Study Progress

Maintained by `modes/system-design/coach.md`'s STUDY TRACKING phase. The candidate never edits this
file directly — report progress out loud in a coaching session and the coach updates it.

Not a hard gate: mocks (`modes/system-design/interviewer.md`) can start whenever you decide you're
ready, checked or not. This just keeps the theory pass organized.

## Recommended order (2-3 day pass)

1. **Day 1** — System Design Primer (README + DB/caching/load-balancing sections), then the Revolut
   event-streaming article (highest signal of everything on this list — it's the actual engineering
   org's own system, read it like you're the interviewer reviewing the trade-offs).
2. **Day 1-2** — "Design Twitter" video, then 5-6 ByteByteGo videos on sharding/caching/queues/CAP.
3. **Day 2** — DDIA (2nd edition, confirmed 2026-09-27 — numbering differs from the 1st edition):
   read only the intro + Summary section of chapters **1, 4, 6, 7, 8**, in that order, via the
   Kindle ebook (~2h total, not the full chapters — see the book entry below for why). Chapters 9
   (The Trouble with Distributed Systems) / 10 (Consistency and Consensus) / 12 (Stream Processing)
   as stretch goals, same intro+summary treatment if time allows.
4. **Day 3** — DDD concepts via free articles (bounded context, aggregate, context mapping — see
   below, not Vernon's book) → Cloud Design Patterns (dip into failure/scaling patterns as a
   catalog, not cover to cover) → Abbott's AKF scale cube concept → Software Architecture Katas as
   a warm-up right before the first mock.
5. **Whenever** — the Andela "System Design in Software Development" article: short, low-depth
   filler, doesn't block anything above it.

## Articles

- [ ] System Design in Software Development (The Andela Way)
      Intro-level: defines architecture/modules/components/interfaces, a 4-step design process, 8
      trade-off factors (scale, timeline, cost, UX, maintainability...), ends on MVC as a concrete
      pattern. Low depth, mostly vocabulary. Low priority.
- [x] Recording more events… But where will we store them? (Revolut engineering blog) — **done
      2026-09-27**
      Revolut's own writeup of why they built a custom event-streaming platform instead of Kafka:
      synchronous domain-model update + event generated after (not pure event sourcing);
      consistency via same-transaction persistence + background reconciliation on publish failure;
      Postgres `LISTEN/NOTIFY` for real-time distribution; EventStore (Kotlin/Ktor) + EventStream
      (RSocket) as separate components; master-replica Postgres; Saga pattern across domain
      boundaries. High priority — this is the house style/vocabulary the interviewer likely shares.

## Videos

- [x] ByteByteGo — System Design (channel) — **video phase done 2026-09-27**, all 4 target topics
      (sharding/caching/CAP/queues) covered
      Short (8-15 min), highly visual walkthroughs of real-system patterns (Discord, Netflix),
      sharding, caching, queues, CAP theorem. Good for fast pattern recognition, light on "why".
      Watched so far (1/5-6 target — plan was sharding/caching/queues/CAP specifically, this one is
      extra/complementary, doesn't count toward that target):
      - "How to Crack a System Design Interview" — 2026-09-27, general interview framework/approach,
        not one of the sharding/caching/queues/CAP topics. Still count 5-6 topic-specific ones next.
      - "System Design Interview: A Step-by-Step Guide" — 2026-09-27, another general
        framework/approach video, same as above — not a sharding/caching/queues/CAP topic.
      - "Back-of-the-Envelope Estimation" — 2026-09-27, not one of the 4 target topics either, but
        genuinely high-value on its own: directly the skill needed for Revolut's "Scaling
        Considerations" phase, and pairs with the Primer's Latency-numbers/Powers-of-two appendix
        tables. Unlike the two framework videos, this one earns its slot even off-list.

      - "Top 5 Most Used Architecture Patterns" — 2026-09-27, off-target for this checklist
        (caching/queues/CAP still needed) but overlaps with the Cloud Design Patterns catalog
        planned for Day 3 if it covers CQRS/event-driven/saga-style patterns.

      **On-target topic videos (counts toward the 5-6):**
      - [x] Sharding — "Consistent Hashing" — 2026-09-27 (the standard mechanism for distributing/
        rebalancing shards without a full reshuffle when nodes are added/removed) — 1/5-6
      - [x] Caching — "How Key-Value Stores Work (Redis, DynamoDB, Memcached)" — 2026-09-27 (Redis/
        Memcached are the standard caching-layer technologies; DynamoDB doubles as a NoSQL/session-
        store example) — 2/5-6
      - [x] CAP theorem — same video, also covered CAP theorem (per candidate) — 3/5-6. Only
        message queues left on the target list.
      - [x] Message queues — "Kafka vs. RabbitMQ vs. Messaging Middleware vs. Pulsar" — 2026-09-27
        — 4/4 target topics now covered (all of sharding/caching/CAP/queues hit), across only 3
        on-target videos since one covered two topics at once. The "5-6 videos" figure was a rough
        breadth proxy, not a hard count — treating the video phase as DONE now that every target
        topic has real coverage, rather than padding to hit the number.

      **Extra bonus, post-video-phase:**
      - "Bloom Filters" — 2026-09-27, not on any list, but directly ties back to a tracked Build It
        weak area ([[weak_areas_backend_concurrency]]/`coaching/current-priorities.md`): kata-025
        could describe Bloom filter properties but couldn't produce the name under pressure. Also a
        legitimate System Design topic (space-efficient membership checks at scale — CDN/dedup use
        cases). Quick recall check offered in-session; not yet confirmed resolved.
- [x] Designing Scalable Systems — "Design Twitter - System Design Interview" — **done 2026-09-27**
      The classic Twitter timeline/feed design exercise: fanout-on-write vs fanout-on-read, the
      "celebrity problem" (fanout-on-write breaking down for huge follower counts), timeline
      sharding, caching. Good practical pairing with the Primer's scaling section.

## Books

_Track qualitatively — which chapters/topics were covered, not a binary done/not-done. Finishing an
entire book in a 2-3 day pass isn't the goal._

- [ ] Domain-Driven Design: Tackling Complexity in the Heart of Software — Eric Evans
      **Superseded for this pass (2026-09-25)** — see "DDD concepts (free resources)" below. Only
      worth buying/reading later as a long-term reference, not for this prep window.
- [ ] Implementing Domain-Driven Design — Vaughn Vernon
      **Superseded for this pass (2026-09-25)** — swapped for free articles covering the same
      interview-relevant concepts (bounded context, aggregate, context mapping) in ~30-45 min
      instead of ~1-1.5h even for the reduced intro+summary treatment. See "DDD concepts (free
      resources)" below.
- [x] Designing Data-Intensive Applications — Martin Kleppmann (& Riccomini, 2nd edition) — **all 5
      priority chapters done 2026-09-27** (9/10/12 stretch chapters still optional/open)
      Highest-signal book for this interview.
      **Edition correction (2026-09-27)**: candidate has the 2nd edition (Kleppmann + Riccomini),
      whose numbering doesn't match the 1st edition this list was originally written against.
      Confirmed real TOC: 1 Trade-Offs in Data Systems Architecture, 2 Defining Nonfunctional
      Requirements, 3 Data Models and Query Languages, 4 Storage and Retrieval, 5 Encoding and
      Evolution, 6 Replication, 7 Sharding (was "Partitioning"), 8 Transactions, 9 The Trouble with
      Distributed Systems, 10 Consistency and Consensus, 11 Batch Processing, 12 Stream Processing,
      13 A Philosophy of Streaming Systems, 14 Doing the Right Thing.
      Priority chapters (corrected numbering): **1** (foundational trade-offs vocabulary), **4**
      (storage engines/indexes), **6** (replication), **7** (sharding), **8** (transactions/
      isolation levels — already strong from Build It prep). 9/10/12 as stretch.
      Progress (intro+Summary pass, per chapter):
      - [x] Ch. 1 — Trade-Offs in Data Systems Architecture — done 2026-09-27
      - [x] Ch. 4 — Storage and Retrieval — done 2026-09-27
      - [x] Ch. 6 — Replication — done 2026-09-27
      - [x] Ch. 7 — Sharding — done 2026-09-27
      - [x] Ch. 8 — Transactions — done 2026-09-27
      **Format decision (2026-09-25)**: full chapters would run ~6-8h (≈150 pages across the 5
      priority chapters) — too much alongside everything else in the 2-3 day pass. Owns the Kindle
      ebook (chosen over physical for delivery time, and over audio-only for being able to actually
      see the diagrams — B-trees, replication topologies, partition rebalancing). Primary pass:
      intro + Summary section of each priority chapter only, in the ebook (~2h total). Has the
      Audible audiobook too (confirmed section-level navigation, not just chapter-level) — used
      passively during commutes to re-listen to or extend what was already read, not as the primary
      pass. Full-chapter detail is on-demand only: revisit a specific subsection later if a mock
      surfaces a real gap there, per [[coaching-drill-vs-mock-evidence]]-style targeted follow-up.
- [x] Cloud Design Patterns — Microsoft — **all 7 target patterns done 2026-09-28**
      **Free, not a book to buy** — it's the live web catalog at
      [learn.microsoft.com/.../architecture/patterns](https://learn.microsoft.com/en-us/azure/architecture/patterns/).
      A pattern catalog, not a linear read: Circuit Breaker, Retry, Bulkhead, Saga, CQRS, Sharding,
      Competing Consumers. Dip in for exact pattern names when prepping failure-handling/scaling
      answers.
      Progress:
      - "Anti-Corruption Layer" — done 2026-09-28 (bonus, not on the original 7 — reinforces the
        Context Mapping article's ACL concept from a different angle)
      - [x] Retry — done 2026-09-28
      - [x] Circuit Breaker — done 2026-09-28
      - [x] Bulkhead — done 2026-09-28
      - [x] Saga — done 2026-09-28
      - [x] CQRS — done 2026-09-28
      - [x] Sharding — done 2026-09-28
      - [x] Competing Consumers — done 2026-09-28
- [x] The Art of Scalability — Martin L. Abbott — **superseded, done via free article 2026-09-28**
      The one idea worth extracting: the AKF scale cube (X = replicate, Y = split by function/
      service, Z = split by data partition). Rest is more organizational/business, lower priority.
      Read [The Scale Cube (AKF Partners' own blog)](https://akfpartners.com/growth-blog/scale-cube/)
      instead of the book — same substitution pattern as Vernon/DDD.

## DDD concepts (free resources, replacing Vernon/Evans for this pass)

- [x] Bounded Context — [Martin Fowler's bliki](https://martinfowler.com/bliki/BoundedContext.html)
      — done 2026-09-28
- [x] Aggregate — [Martin Fowler's bliki: DDD_Aggregate](https://martinfowler.com/bliki/DDD_Aggregate.html)
      — done 2026-09-28
- [x] Context mapping (Shared Kernel, Customer-Supplier, Anti-Corruption Layer, Conformist) —
      [Context Mapping in DDD: Patterns and Team Relationships (Milan Jovanovic)](https://milanjovanovic.tech/blog/context-mapping-ddd)
      — done 2026-09-28. Covers all four patterns in one article instead of reading them separately.
      Optional per-pattern reference if a crisper definition is needed later:
      [ContextMapper.org](https://contextmapper.org/docs/anticorruption-layer/) has one page per
      pattern (shared-kernel, customer-supplier, anticorruption-layer).

Total ≈ 30-45 min for all three concepts — the replacement for the Vernon/Evans checklist items
above.

## Hands-on

- [x] System Design Primer — **done 2026-09-27**
      Best ROI on this whole list: a README with core vocabulary (load balancers, caching, CDN,
      replication, sharding, queues) plus short topic sections each linking further reading. Built
      for interview prep, not meant to be read cover to cover.
      Read: How to approach a system design interview question, Performance vs scalability, Latency
      vs throughput, Availability vs consistency (CAP), Load balancer, Database, Cache — plus the
      Latency numbers / Powers of two appendix tables. Skipped: full worked-example solutions,
      flashcards, company-blog list (per plan, optional/reference only).
- [ ] Software Architecture Katas
      Practice exercises, best used as a warm-up right before the first full mock rather than at
      the start of the theory pass.
- [ ] Hello Interview — [hellointerview.com](https://www.hellointerview.com/), specifically the free
      ["System Design in a Hurry"](https://www.hellointerview.com/learn/system-design/in-a-hurry/introduction)
      guide (named by Karim, 2026-09-28 email)
- [ ] IGotAnOffer — [igotanoffer.com](https://igotanoffer.com/) (named by Karim; mostly
      company-specific guides + a paid mock-interview coaching marketplace, lower priority than
      Hello Interview's free guide)
- [ ] Exponent system design guide — [tryexponent.com/blog/system-design-interview-guide](https://www.tryexponent.com/blog/system-design-interview-guide)
      (named by Karim)

## Session log

- **2026-09-25**: Coach reviewed all 4 linked resources (2 Medium articles fetched in full, the
  video's title confirmed, the ByteByteGo channel page blocked by YouTube's consent wall — relied on
  general knowledge for it) and the 4 books/2 hands-on items from general knowledge, and produced the
  descriptions and recommended order above. No study time logged yet — candidate hasn't started the
  theory pass.
- **2026-09-25**: DDIA format decided — bought the Kindle ebook (physical was 1+ week out) as the
  primary read, keeping the free Audible audiobook for passive commute re-listening only. After
  estimating full chapters 1/3/5/6/7 at ~6-8h, settled on intro+Summary-only for the primary pass
  (~2h), with full-chapter depth deferred to on-demand lookups triggered by actual mock gaps. See the
  DDIA book entry above for the full reasoning.
- **2026-09-25**: Swapped Vernon's "Implementing DDD" (and Evans' original) out of this pass — after
  estimating even the reduced intro+summary treatment at ~1-1.5h, replaced with 3 free articles
  covering the same interview-relevant concepts (bounded context, aggregate, context mapping) in
  ~30-45 min total. See the new "DDD concepts (free resources)" section above.
- **2026-09-27**: System Design Primer done — the planned topic sections plus the two appendix
  tables, worked-examples/flashcards/company-blogs intentionally skipped. Day 1 continues with the
  Revolut event-streaming article next.
- **2026-09-27**: Revolut event-streaming article done. Day 1 complete — moving to Day 1-2 (videos)
  next.
- **2026-09-27**: "Design Twitter" video done. Next: 5-6 ByteByteGo videos on sharding/caching/
  queues/CAP to close out Day 1-2.
- **2026-09-27**: Watched "How to Crack a System Design Interview" (ByteByteGo) — a general
  framework video, not one of the planned sharding/caching/queues/CAP topics. Logged as a bonus,
  still need 5-6 topic-specific ones to close out Day 1-2.
- **2026-09-27**: Watched "System Design Interview: A Step-by-Step Guide" (ByteByteGo) — another
  general framework video, same bonus/non-counting status as the previous one. Two framework videos
  watched now, but zero on the actual target topics (sharding/caching/queues/CAP) — worth steering
  toward those specifically next.
- **2026-09-27**: Watched "Back-of-the-Envelope Estimation" (ByteByteGo) — off-list but genuinely
  valuable (directly useful for the Scaling Considerations phase). Still 0/5-6 on the actual target
  topics — three videos in and none on sharding/caching/queues/CAP yet.
- **2026-09-27**: Watched "Consistent Hashing" (ByteByteGo) — counts toward the sharding bucket,
  first on-target video (1/5-6). 3-4 more on caching/queues/CAP to go.
- **2026-09-27**: Watched "Top 5 Most Used Architecture Patterns" (ByteByteGo) — off-target again
  (4 of 5 videos so far haven't hit caching/queues/CAP specifically), though it may resurface useful
  ground for Day 3's Cloud Design Patterns catalog. Still 1/5-6 on the actual target list.
- **2026-09-27**: Watched "How Key-Value Stores Work (Redis, DynamoDB, Memcached)" (ByteByteGo) —
  on-target, covers caching (2/5-6). Queues and CAP theorem left.
- **2026-09-27**: Candidate confirmed the same Key-Value Stores video also covered CAP theorem —
  3/5-6, DynamoDB's tunable consistency likely the tie-in. Only message queues remain on the target
  list; Day 1-2 close to done.
- **2026-09-27**: Watched "Kafka vs. RabbitMQ vs. Messaging Middleware vs. Pulsar" (ByteByteGo) —
  message queues covered, all 4 target topics (sharding/caching/CAP/queues) now hit. Calling the
  video phase done — the "5-6 videos" figure was only ever a breadth proxy, not a real target once
  every topic has genuine coverage. Day 1-2 complete. Convention noted: candidate names a video only
  after watching it, never before — treat every named video as already watched.
- **2026-09-27**: Watched "Bloom Filters" (bonus, off-list) — ties back to the still-open Build It
  recall gap on this exact topic (kata-025). Offered a quick unprompted-recall check in this
  session; result not yet reported back.
- **2026-09-27**: Watched "What is a Load Balancer?" (bonus) — reinforces the Primer's Load Balancer
  section already read on Day 1, no new topic ground covered.
- **2026-09-27**: Videos closed out for now, moving to Day 2 (DDIA).
- **2026-09-27**: Candidate flagged their Chapter 1 as "Trade-Offs in Data Systems Architecture",
  not the 1st-edition title used in this tracker — confirmed via web search (two independent
  sources agreeing) that they have the 2nd edition (Kleppmann + Riccomini), with a different
  chapter numbering. Corrected the priority chapter list from 1/3/5/6/7 to **1/4/6/7/8**. See the
  DDIA book entry above for the full corrected TOC.
- **2026-09-27**: DDIA Day 2 complete — intro+Summary read for chapters 1, 4, 6, 7, 8 (corrected
  2nd-edition numbering). 9/10/12 left as optional stretch. Moving to Day 3 (DDD concepts / Cloud
  Design Patterns / AKF cube / Katas).
- **2026-09-28**: DDD concepts (free resources) done — Bounded Context, Aggregate, Context Mapping
  all read. Next: Cloud Design Patterns catalog (dip in on failure/scaling patterns), then Abbott's
  AKF scale cube, then Software Architecture Katas.
- **2026-09-28**: Cloud Design Patterns done — discovered it's the free Microsoft Learn catalog, not
  a book to buy (corrected from the original guide's "book" framing). Read Anti-Corruption Layer
  (bonus) plus all 7 target patterns: Retry, Circuit Breaker, Bulkhead, Saga, CQRS, Sharding,
  Competing Consumers. Next: Abbott's AKF scale cube, then Software Architecture Katas.
- **2026-09-28**: AKF scale cube done via AKF Partners' own free blog article (substitute for
  Abbott's book, same pattern as the DDD swap). Theory pass now effectively complete except the
  short Andela filler article; Software Architecture Katas remain as a pre-mock warm-up, not theory.
- **2026-09-28**: Had the prep call with Karim (Revolut). Follow-up email corrected/sharpened the
  PDF's framing significantly — biggest change: **this is not a Q&A round, the candidate leads the
  session**, not "more collaborative than Build It" as the PDF alone implied. Also: ~50 min counted
  from problem statement to drafted solution (not 55 min total), high-level design must stay
  MVP/skeleton-only, low-level design needs explicit trade-off justification, edge cases/failure
  scenarios framed as detect→prevent→recover, and scaling framed as local→regional→global.
  Propagated into `modes/system-design/interviewer.md` (INTERVIEW CONTEXT, new CANDIDATE LEADS
  section, all 4 phases, TIME MANAGEMENT, REVIEW MODE, IMPORTANT INTERVIEW STYLE) and
  `modes/system-design/coach.md` (evaluation weighting, session-leadership-is-mock-only-evidence
  note). Added 3 new practice resources Karim named (Hello Interview, IGotAnOffer, Exponent) to the
  Hands-on list above.
- **2026-09-28**: Candidate relayed that Karim also mentioned, verbally on the prep call,
  "booking.com-style designs" and fintech apps as likely example domains. Added a new
  booking/reservation-style domain category to `modes/system-design/interviewer.md`'s mock-generation
  list, explicitly steered toward the parts not already drilled via Build It's concurrency prep
  (availability search/indexing, geo-distribution) rather than re-testing lock-ordering. Moving to
  the first full mock next.
