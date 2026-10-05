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
  handling, multi-currency/timezone, business constraints. (Missed in sd-1/sd-2, surfaced
  unprompted in sd-3/sd-4 — keep the habit.)

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
  | **Anything scheduled / time-based** (added after sd-5) | User time zone (store IANA name, e.g. `Europe/Lisbon`, never an offset — DST), calendar rule vs fixed interval ("monthly" ≠ 30 days; derive occurrence *n* from the start date, clamp 29–31 to month end), business days + scheme cut-offs (batch schemes only), "executed by when?" SLA, push (standing order) vs pull (direct debit) |
  | **Baseline, applies almost everywhere with EU users** | GDPR (deletion, export, consent), encryption of PII at rest and in transit |

### Anchor numbers for N (order of magnitude, not precision)

The point of asking non-functional questions is to find out which side of a known threshold you're
on — if a number doesn't move you across one of these, it wasn't the question that mattered. Per
Karim's email, precision matters less than showing the method and sanity-checking the result.

| Component | Anchor | Decision it triggers |
|---|---|---|
| Relational DB, single primary | 🟢 < ~2K writes/s · 🟡 ~2-10K · 🔴 > ~10K sustained | 🟢 one primary, no discussion. 🟡 big instance + time partitioning/archiving, sharding plan ready. 🔴 shard or a store built for it. Write-heavy → first ask if you can write less (batch/aggregate). Cloud IOPS/storage maxima are ceilings, not design points. |
| Same primary, storage | 🟢 < ~5 TB · 🟡 ~5-30 TB · 🔴 > ~30-50 TB (backups/restore time, vacuum, reindex) | Storage-only growth → partition by time + archive to cold storage, usually NOT sharding. |
| Read replicas | Scale ~linearly per node; limit is replication lag (ms-seconds), not throughput | Decides if "read from replica" is safe for a given use case. |
| Cache (single Redis node) | ~100K-200K ops/sec, sub-ms | Capacity is effectively free — the real question is invalidation/staleness. Note: capacity and HA are separate axes — a single node may have throughput to spare and still need a replica (Sentinel/Cluster) purely for failover, not for load. |
| Network bandwidth | 1 Gbps ≈ 125 MB/s; a normal server NIC is 10-25 Gbps (1-3 GB/s) | Tens of MB/s is trivial (one link). Only hundreds of MB/s+ sustained, or video/egress at scale, makes bandwidth a design topic (→ CDN). |
| Websocket / push server | ~0.5-1M concurrent connections; ~1M small messages/s per server | Size EVERY resource (network, connections, messages/s) with total ÷ per-server capacity — the largest wins. Batch per user per tick before adding servers (FX drill: 150 → ~10 servers). |
| Cloud egress cost | ≈ $0.05/GB out | 15 GB/s ≈ $2,700/hour. Reducing what you send is a cost argument, not just a performance one. |
| Object storage cost | S3 Standard ≈ $23/TB-month; Glacier Deep Archive ≈ $1/TB-month (≈12h retrieval) | Capacity is never the problem in object storage — cost is. Justify tiering in $/month, and use lifecycle policies instead of custom archivers. |
| Writes per business event | Fintech: one money movement ≈ 2 ledger entries + 1 transfer row + 2 balance updates | Count rows per event before multiplying — it moved round-ups from 🟢 to 🟡 in the 2026-10-02 drill. |
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

- **Money path — per-hop duplicate hunt** (added after sd-5): walk producer → DB → outbox → queue →
  consumer → ledger/provider → callback and, at each hop, say "if it crashes here: duplicated /
  lost / fine — and what stops it". Mandatory checks:
  1. **Natural idempotency key** from the business event with a UNIQUE constraint (e.g.
     `UNIQUE(schedule_id, occurrence_date)`), plus a **deterministic** `payment_id` derived from it
     (UUIDv5) that flows through ledger, outbox, other cell, external provider. Never a fresh random
     UUID per attempt; retries keep the same id (`attempt` column if you need to count).
  2. **Never "atomic" across two systems** (DB + queue, DB + another cell's DB) → transactional
     outbox; each transaction touches one DB only.
  3. **No check-then-act on a balance** → one conditional statement
     (`UPDATE … SET balance = balance − x WHERE id = ? AND balance >= x`; 0 rows = insufficient).
  4. **Double-entry ledger**: every payment's entries sum to zero; reconciliation checks it.
  5. **Saga compensation only on a definitive answer from the side that commits, never on a
     timeout.** A timeout means "I don't know". Make "too late" a shared rule: the message carries
     `expires_at`; the receiver rejects after it and stores a tombstone (`inbound_payments(P1,
     'rejected')`); the sender asks for the status and compensates only on `rejected`.
  6. Retries: exponential backoff **until a business deadline**, not a retry count; tell the user.

For every choice here: name it AND justify it (user angle + business angle) before moving on —
don't wait to be asked why.

## Phase 4 — Scaling (~10 min): **L-R-G**

- **L**ocal → **R**egional → **G**lobal, explicitly, as three separate steps
- At each step: what's the new bottleneck (not just "more of the same"), what does the fix cost,
  what would you deliberately let degrade rather than fail outright

### Multi-region for fintech = cells per legal entity (added after sd-5; residency failed sd-3/4/5)

**Open Phase 4 with this, before any word about replication:**

> "Locally, one cell handles our numbers. Regionally, I add **one cell per legal entity** (EU, UK,
> US…): each user's data lives only in their home cell, writes go only there, failover stays inside
> the jurisdiction. Globally, only a pseudonymous `user_id → cell` directory is shared, and
> cross-cell payments send only the instruction needed."

- **Cell** = full copy of the system (API, DB, scheduler, outbox, queue, ledger, local scheme
  connector). Home cell = legal entity that holds the account, not where the user connects from.
- **Writes**: many primaries, but each row has exactly one — no multi-master conflicts. Never a
  single global primary; never global read replicas of PII.
- **Failover** inside the jurisdiction (Frankfurt ↔ Dublin), never to another continent.
- **External payment** (to another bank's IBAN): stays entirely in the payer's cell → local scheme
  connector. Other Revolut cells are not involved.
- **Internal cross-cell payment** (UK Ana → EU Luis), each step one local transaction:
  1. UK: conditional debit Ana + credit "owed to EU entity" + ledger entries + `P1 =
     sent_to_EU` + outbox `{payment_id, to_account_ref, amount, currency, payer_name, reference,
     expires_at}`
  2. UK relay → **inter-cell payment API** (internal, mTLS)
  3. EU: insert `inbound_payments(P1)` (PK = dedupe) + credit Luis + "owed by UK entity" + ledger
     + outbox ack
  4. EU relay → ack → 5. UK: `P1 = confirmed` (idempotent update)
  Inter-entity accounts are settled **net daily** with a real transfer — each entity is a separate
  regulated balance sheet (safeguarding).
- **Legal basis when data crosses** — never "consent", never "inform the user":

  | Crossing | Basis |
  |---|---|
  | Payment instruction the user ordered | Contract necessity (+ adequacy EU↔UK) |
  | Analytics/fraud features | Pseudonymise/aggregate + SCCs + TIA, or keep regional |
  | Remote support access | Counts as a transfer → SCCs + VDI, logged, just-in-time access |
  | UK → US | UK–US Data Bridge / SCCs, or contract necessity for the user's own payment |

- **Payment schemes** (one connector per cell): SEPA (EUR; SCT batch ~D+1 business days with
  cut-off, SCT Inst 24/7), FPS (UK, GBP, near-instant 24/7), ACH (US, batch 1–3 days, returns
  arrive days later), SWIFT (global messaging via correspondents). Batch schemes → store requested
  date vs expected settlement date separately, and have a returns/reconciliation path
  (`sent → confirmed/returned`). A non-business-day order is deemed received the next business day
  (PSD2).

## Postgres concurrency cheat sheet (added 2026-10-05, after sd-12 Q&A)

- **Index vs WHERE**: the index holds the columns that *find* the rows (equalities first, then the
  range/order); the WHERE holds *every* condition correctness needs, indexed or not. A hold by
  `(screening_id, seat_id = ANY(:ids))` needs only the PK; `status`/`held_until` stay in the WHERE.
- **Status in an index** only when the query searches by state without a more selective key (the expiry
  worker) — and make it **partial**: `CREATE INDEX … (held_until) WHERE status IN ('held','paying')`.
- **All-or-nothing multi-row claim**: one `UPDATE … WHERE … seat_id = ANY(:ids) AND <free or expired>
  RETURNING seat_id`; commit only if N rows came back, else ROLLBACK. Under READ COMMITTED Postgres
  re-evaluates the WHERE on the new row version after waiting → no double-sell.
- **Deadlocks** need waiting + different lock order. Prevent with `SELECT … ORDER BY key FOR UPDATE`
  (fixed order), or don't wait: `FOR UPDATE NOWAIT` (fail fast — good at premieres) / `SKIP LOCKED`
  (treat locked as unavailable; workers always use it, so they never deadlock with users).
- **If a deadlock happens**, Postgres detects it (`deadlock_timeout`, 1 s) and aborts one TX with
  SQLSTATE 40P01 → the app retries. Never "force unlock".
- **Long lock waits** (no cycle) are NOT auto-resolved: keep transactions short, **no external calls
  inside a TX**, set `lock_timeout`, `statement_timeout`, `idle_in_transaction_session_timeout`. Emergency
  only: `pg_cancel_backend(pid)` (cancel query) / `pg_terminate_backend(pid)` (kill session → rollback);
  find the blocker with `pg_stat_activity` + `pg_blocking_pids(pid)`.
- **Occupancy of a serialized resource**: ρ = λ (requests/s on *that* row/worker/partition) × S (seconds
  each holds it). < 50% fine, > 70% risky (wait ≈ S/(1−ρ)), ≥ 100% the queue grows without bound. Name
  the serialized unit first.

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
