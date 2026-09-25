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
3. **Day 2** — DDIA: read only the intro + Summary section of chapters 1, 3, 5, 6, 7, in that
   order, via the Kindle ebook (~2h total, not the full chapters — see the book entry below for
   why). 8/9/11 as stretch goals, same intro+summary treatment if time allows.
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
- [ ] Recording more events… But where will we store them? (Revolut engineering blog)
      Revolut's own writeup of why they built a custom event-streaming platform instead of Kafka:
      synchronous domain-model update + event generated after (not pure event sourcing);
      consistency via same-transaction persistence + background reconciliation on publish failure;
      Postgres `LISTEN/NOTIFY` for real-time distribution; EventStore (Kotlin/Ktor) + EventStream
      (RSocket) as separate components; master-replica Postgres; Saga pattern across domain
      boundaries. High priority — this is the house style/vocabulary the interviewer likely shares.

## Videos

- [ ] ByteByteGo — System Design (channel; note which specific videos were watched below, a
      channel-wide checkbox isn't meaningful on its own)
      Short (8-15 min), highly visual walkthroughs of real-system patterns (Discord, Netflix),
      sharding, caching, queues, CAP theorem. Good for fast pattern recognition, light on "why".
- [ ] Designing Scalable Systems — likely "Design Twitter - System Design Interview" (title
      confirmed via the video page; description/channel couldn't be fetched, so treat the exact
      source with some margin of doubt)
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
- [ ] Designing Data-Intensive Applications — Martin Kleppmann
      Highest-signal book for this interview. Priority chapters: 1 (reliability/scalability/
      maintainability vocabulary), 3 (storage engines/indexes), 5 (replication), 6 (partitioning/
      sharding), 7 (transactions/isolation levels — already strong from Build It prep). 8/9/11
      (distributed consistency, stream processing) as stretch.
      **Format decision (2026-09-25)**: full chapters would run ~6-8h (≈150 pages across the 5
      priority chapters) — too much alongside everything else in the 2-3 day pass. Owns the Kindle
      ebook (chosen over physical for delivery time, and over audio-only for being able to actually
      see the diagrams — B-trees, replication topologies, partition rebalancing). Primary pass:
      intro + Summary section of each priority chapter only, in the ebook (~2h total). Has the
      Audible audiobook too (confirmed section-level navigation, not just chapter-level) — used
      passively during commutes to re-listen to or extend what was already read, not as the primary
      pass. Full-chapter detail is on-demand only: revisit a specific subsection later if a mock
      surfaces a real gap there, per [[coaching-drill-vs-mock-evidence]]-style targeted follow-up.
- [ ] Cloud Design Patterns — Microsoft
      A pattern catalog, not a linear read: Circuit Breaker, Retry, Bulkhead, Saga, CQRS, Sharding,
      Competing Consumers. Dip in for exact pattern names when prepping failure-handling/scaling
      answers.
- [ ] The Art of Scalability — Martin L. Abbott
      The one idea worth extracting: the AKF scale cube (X = replicate, Y = split by function/
      service, Z = split by data partition). Rest is more organizational/business, lower priority.

## DDD concepts (free resources, replacing Vernon/Evans for this pass)

- [ ] Bounded Context — [Martin Fowler's bliki](https://martinfowler.com/bliki/BoundedContext.html)
      (~5 min)
- [ ] Aggregate — [Martin Fowler's bliki: DDD_Aggregate](https://martinfowler.com/bliki/DDD_Aggregate.html)
      (~5 min)
- [ ] Context mapping (Shared Kernel, Customer-Supplier, Anti-Corruption Layer, Conformist) —
      [Context Mapping in DDD: Patterns and Team Relationships (Milan Jovanovic)](https://milanjovanovic.tech/blog/context-mapping-ddd)
      (~15 min) — covers all four patterns in one article instead of reading them separately.
      Optional per-pattern reference if a crisper definition is needed later:
      [ContextMapper.org](https://contextmapper.org/docs/anticorruption-layer/) has one page per
      pattern (shared-kernel, customer-supplier, anticorruption-layer).

Total ≈ 30-45 min for all three concepts — the replacement for the Vernon/Evans checklist items
above.

## Hands-on

- [ ] System Design Primer
      Best ROI on this whole list: a README with core vocabulary (load balancers, caching, CDN,
      replication, sharding, queues) plus short topic sections each linking further reading. Built
      for interview prep, not meant to be read cover to cover.
- [ ] Software Architecture Katas
      Practice exercises, best used as a warm-up right before the first full mock rather than at
      the start of the theory pass.

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
