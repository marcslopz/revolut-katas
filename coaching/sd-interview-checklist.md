# System Design Interview — Session Script

Purpose: a mental script to rehearse before mocks and before the real interview — memorize it, do
not plan to consult it live (you won't have it, and per Revolut's rules you shouldn't). The goal is
that covering every area becomes automatic, closing the sd-2 gap of running out of self-generated
structure before the session's scope was actually complete.

Three mnemonics, one per stage. Say each phase's letters to yourself at the start of that phase.

## Phase 1 — Requirements (5-7 min): **F-N-I**

- **F**unctional — what operations, for whom
- **N**on-functional — scale, SLA, latency, availability
- **I**mplicit — say ONE out loud even if not asked: compliance/regulatory, PII/payment-data
  handling, multi-currency/timezone, business constraints. **This is the current weakest link —
  2/2 mocks missed it entirely. Force it even if it feels unnatural.**

  ### Implicit requirements by domain family

  Identify the prompt's domain family first, then fire the 2-3 items for that family — don't try to
  recall a generic master list.

  | Domain | Typical implicit requirements |
  |---|---|
  | **Fintech/payments/banking** (most relevant for you) | KYC (identity at onboarding), AML (ongoing transaction monitoring — sanctions/PEP lists), PCI DSS (tokenize cards, never store them), audit trail with legally-required retention, transaction/fraud limits, strong balance consistency |
  | **Booking/reservations** (the other family Karim named) | Cancellation/refund window, no-double-booking invariant, multi-currency/timezone if global, identity verification for high-value bookings |
  | **E-commerce/marketplace** | PCI if cards touched directly, returns/refunds policy, tax (VAT/sales tax varies by region), seller verification |
  | **Healthcare** | HIPAA/health-data GDPR rules, mandatory record retention, explicit consent for data sharing |
  | **Social/UGC** | Content moderation, age verification/minor protection, GDPR right-to-be-forgotten |
  | **Baseline, applies almost everywhere with EU users** | GDPR (deletion, export, consent), encryption of PII at rest and in transit |

### Anchor numbers for N (order of magnitude, not precision)

The point of asking non-functional questions is to find out which side of a known threshold you're
on — if a number doesn't move you across one of these, it wasn't the question that mattered. Per
Karim's email, precision matters less than showing the method and sanity-checking the result.

| Component | Anchor | Decision it triggers |
|---|---|---|
| Relational DB, single primary | ~1,000-5,000 writes/sec comfortable | Below → don't shard yet. Above → sharding is a real conversation, not optional. |
| Same primary, storage | Low single-digit TBs fine, tens of TBs hurts (backups, vacuum, reindex) | Second, independent trigger for sharding. |
| Read replicas | Scale ~linearly per node; limit is replication lag (ms-seconds), not throughput | Decides if "read from replica" is safe for a given use case. |
| Cache (single Redis node) | ~100K-200K ops/sec, sub-ms | Capacity is effectively free — the real question is invalidation/staleness. Note: capacity and HA are separate axes — a single node may have throughput to spare and still need a replica (Sentinel/Cluster) purely for failover, not for load. |
| Cross-region latency | Same-region <5ms. Cross-continent one-way ~70-150ms (US-EU ~70-100ms, US-Asia ~150-200ms) | This, not raw QPS, is usually what kills a synchronous cross-region call — this was the exact number missing from the sd-2 EU-write-leader discussion. |

**Prefix lookups (autocomplete/typeahead)**: not a full-text search engine (Elasticsearch is built
for relevance scoring, not raw prefix speed) and *definitely* not an LLM (far too slow/expensive per
keystroke, and it answers the wrong question — "plausible text" instead of "what other users
actually searched"). Standard pattern: a **Trie** (prefix tree, pronounced "try", from "retrieval")
or a Redis sorted set (`ZRANGEBYLEX` for lexicographic prefix ranges), precomputed **offline** from
real query logs, top-N completions per prefix, refreshed periodically. Lookup at request time is an
in-memory, sub-ms operation — no inference, no live ranking.

## Phase 2 — High-Level Design (~10 min): skeleton only

- Boxes and connections, end-to-end happy path. No DB tech, no cache strategy, no index types yet.
- Sequence prerequisite/pre-flow steps (validation, auth, availability check) before the main
  action — don't jump straight to it.

## Phase 3 — Low-Level Design (~15-20 min): **D-I-S-E**

- **D**atabase — schema, SQL vs NoSQL, indexing, sharding/partitioning key, read replicas

  | Option | Good for | Reach for it when | Example |
  |---|---|---|---|
  | Relational (SQL) | Structured data, ACID transactions | Strong invariant/joins needed (the hotel/booking pattern) | Users, Bookings, Ledger |
  | Key-Value / NoSQL | Pure key lookups, native horizontal scale | Always accessed by ID, no relational queries, write volume crosses a single-primary threshold | User profile by id, counters, sessions |
  | Document store | Semi-structured data, schema varies a lot | Record "shape" changes often, avoid constant migrations | Product catalog with variable attributes |
  | Cache (in-memory) | Sub-ms hot reads, atomic counters | Reads dominate and tolerate staleness (checkout/hotel pattern) | Search results, rate limiting |
  | Object storage + CDN | Large blobs, cheap, not queryable | Any big binary — never put the blob inside the relational DB | Photos, backups, KYC docs |
  | Search index | Full-text, faceted/geo search | Free-text or combined-filter search a normal SQL index can't do well | Hotel search by location + text |
  | Message queue/log | Durable event transport, not queryable storage | Backing an outbox pattern or async decoupling | sd-2's outbox consumer |
  | Data warehouse (OLAP) | Analytics over large historical data | Reporting/BI, never to serve a live user request | Internal dashboards |

  Deciding question: what's the access pattern — transactions/relations (SQL), pure key lookup at
  scale (KV), text/geo search (search index), or a blob that shouldn't be in a queryable DB at all
  (object storage)? Justify by access pattern, not by "what's modern."
- **I**nfra — caching (what + invalidation), queues/async, load balancing, CDN, deployment,
  observability
- **S**ecurity — authN/authZ, encryption at rest/in transit, rate limiting, PII handling

  **AuthN vs authZ, and federated login (OAuth/OIDC, e.g. "Sign in with Google")**: Google (or any
  external identity provider) only resolves *authentication* — proves who the user is (email, a
  provider-specific user ID), via a verified ID token (a JWT, same signature-verification mechanism
  as your own tokens). It has no concept of your domain's roles. **Never trust the frontend, or the
  external provider's token, for role/permission claims** — a compromised or modified client could
  assert any role. The correct pattern: your backend resolves the external identity against **your
  own database** (which email is a doctor vs. a patient — established through your own onboarding
  process), then mints **your own signed JWT** with the role your system determined. AuthZ itself
  then splits into two distinct checks: role-based (can this type of actor do this type of action —
  readable straight off the JWT claim) and resource-ownership (can *this specific user* act on
  *this specific resource* — requires a DB lookup, the JWT alone can't answer it, e.g. a patient
  cancelling only their own appointment, not someone else's).
- **E**dge cases — pick 2-3 concrete failure scenarios, walk each through **detect → prevent →
  recover**, not just "here's what could go wrong"

For every choice here: name it AND justify it (user angle + business angle) before moving on —
don't wait to be asked why.

## Phase 4 — Scaling (~10 min): **L-R-G**

- **L**ocal → **R**egional → **G**lobal, explicitly, as three separate steps
- At each step: what's the new bottleneck (not just "more of the same"), what does the fix cost,
  what would you deliberately let degrade rather than fail outright

## Mid-session checkpoint (self-imposed, ~25 min in)

Say to yourself, out loud if the format allows it: **"Which of F-N-I / skeleton / D-I-S-E / L-R-G
have I not touched yet, and how am I splitting the remaining time across them?"**

This is the direct fix for sd-2: the session ended inside Phase 3 having never reached Database
depth, Security beyond auth, or Phase 4 at all — not because time ran out on one topic, but because
there was no checkpoint forcing an explicit look at what was still missing.

## Never say

**"Anything else?" / "What should I cover next?"** — if you reach a point where you don't know
what's left, that's the checkpoint above firing late. Instead, name the specific gap yourself:
*"I haven't covered sharding or security in depth — let me do both now."* Ending a phase by handing
structure back to the interviewer is graded as a leadership gap even when everything covered up to
that point was strong.
