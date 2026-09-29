# sd-1 — P2P instant money transfer (cross-currency)

Interviewer's own running notes. Candidate never writes here.

## Problem statement
Design a service that lets users send money to each other instantly, including across different
currencies.

## Phase 1 — Requirements gathering (in progress)

### Stated by interviewer (stakeholder answers)
- Scale: 50M registered users, 10M MAU, ~2M DAU.
- Transfer traffic: ~100 transfers/sec average, ~500/sec peak (5x peak/average).
- Read/write ratio: ~20:1 (balance/history checks dominate transfer-initiation writes).
- FX rates: sourced from an external third-party market-data provider (no in-house rate
  generation). Provider SLA: 99.9% availability, historically only brief (minutes-scale) outages,
  no prolonged failures.
- Non-functional: p99 < 500ms end-to-end transfer confirmation, p99 < 200ms balance/history reads,
  99.95% service availability, balance strongly consistent (no double-spend/lost updates, stated as
  non-negotiable).
- All 3 core actions confirmed synchronous from the user's perspective (matches the "instant"/
  latency requirement); anything after the response is the candidate's design choice.
- Users are global: ~60% Europe, ~40% North America + Asia-Pacific combined, growing. Whether/how
  to allocate across regions (servers/DBs) is the candidate's design decision, not yet answered.

### Candidate's questions so far
- Users / requests-per-second — asked
- How FX rate info is obtained — asked (third party vs internal)
- FX provider reliability / need for failover — asked (redirected back: their design decision)
- Functional scope confirmation (get balance, get transfer history, transfer money) — asked and
  confirmed as the core 3 actions
- Latency/availability SLA — asked

### Not yet covered by candidate
- Explicit non-functional ask on consistency (answered proactively above since it's non-negotiable
  regardless)
- Implicit requirements: compliance/regulatory (AML, transaction limits, audit trail),
  multi-currency/timezone realities — not surfaced by candidate yet
- No FX-quote/preview step raised as a separate concern yet (may fold into "transfer" internally,
  not necessarily a scope gap)

## Phase 2 — High-level design (in progress)

Candidate's design so far (verbal, no screenshot yet):
- Global load balancer, routes each user to a region based on user info (geo-routing)
- Web servers replicated per region: Europe and North America regions so far
- Separate databases per region: one for Europe, one for US
- Each regional DB: single master for writes, read replicas for reads (justified by the earlier
  20:1 read/write ratio)

Open question raised by interviewer: how does a transfer between a user in Europe and a user in the
US work, given they're in separate regional databases? Candidate's answer (trade-off enumerated,
no commitment yet):
- Option A: keep separate regional DBs, cross-region transfer via an async feed / distributed
  transaction (mentioned two-phase commit explicitly) — more complex.
- Option B: single global DB, simpler atomic transactions, but latency penalty for whichever
  region is remote from the DB.
Candidate did not commit to one or justify a final choice yet — pushed to decide.

Candidate's decision: single global write-primary in Europe (majority of users), with replicas in
America; American users accept extra write latency (cross-Atlantic write to the EU primary) in
exchange for a simpler consistency model. Justification given: majority-user region hosts the
primary.

Potential inconsistency to probe: this seems to replace the earlier "separate DB per region, each
with its own master+read-replicas" statement with a single global primary — unclear if that's
intentional (all writes now go through the EU primary regardless of same-region-only transfers) or
only meant for cross-region transfers specifically. Flagged to candidate for reconciliation.

Candidate's revision: master-master replication between EU and US regional DBs, eventual
consistency across regions, same-region writes stay local.

**Real inconsistency flagged (2026-09-29)**: this directly contradicts the non-negotiable
requirement stated in Phase 1 — "balance must be strongly consistent, no double-spend, no lost
updates, ever." Master-master + eventual consistency is exactly the setup that risks a double-spend
or lost update on a cross-region transfer touching both users' balances (conflicting concurrent
writes on two masters, needing conflict resolution). Pushed candidate on this directly rather than
stating the conclusion.

Candidate's clarification (good self-correction): eventual consistency only applies to read
replicas catching up from their local master (normal replication lag) — the actual cross-region
transfer itself would use two-phase commit across the two masters for atomicity. This resolves the
strong-consistency contradiction above.

New angle to probe (partial failure, normally a Phase 3 topic but the conversation naturally
reached it): 2PC across an EU-US link is blocking and holds locks on both sides for the round trip
— asked candidate what happens if the cross-region link is down/slow mid-commit. Not yet answered.
Relevant background: candidate studied the Saga pattern and transactional outbox very recently
(Cloud Design Patterns / DDIA prep, 2026-09-27/28) as the standard alternative to 2PC for exactly
this shape of problem — not hinted at during the mock, but worth checking in the review whether it
gets reached for unprompted.

Failure-scenario follow-up: circuit breaker for user-facing timeout (reasonable) → asked about
partial-commit state (debited but not credited) → candidate correctly named atomicity as the
guarantee 2PC is meant to provide (roll back the first action if not both succeed) → asked
specifically about coordinator crash between "prepare" (both voted yes) and the final decision
being sent. Candidate's answer: put the coordinator behind a queue, a replacement coordinator picks
up the unacknowledged message. Doesn't fully resolve the classic 2PC "in-doubt/blocking" problem —
while waiting for a replacement coordinator, the participants that already voted yes are stuck
holding their locks (can't unilaterally decide), which is the actual availability risk of 2PC, not
addressed yet. Gave one more pointed follow-up on this; after that, moving on regardless of the
answer — this single mechanism has consumed a disproportionate share of the mock's time budget,
worth noting for the review (time management).

Candidate correctly identified the blocking problem on the final push ("they would be stuck
waiting") — good recovery, lands on the real 2PC availability risk by the end of the thread even
though it took several follow-ups to get there (not self-caught, interviewer-driven).

## Phase 3 — Low-level design (starting)

Candidate asked "do you want me to say about it?" before starting — a mild structure-ownership
check per CANDIDATE LEADS; reflected it back rather than listing topics for them, to avoid handing
over session structure.

Screenshot confirms Phase 2 topology (2026-09-29, 12:30): User → Load Balancer → regional API
webservers (Europe / North America) → each region's own DB, with a link between the two DBs for
cross-region transfers.

API/data-flow detail given: 3 endpoints (get balance, get history, transfer), routed to the user's
home region. Reads served from local read replica. Writes (transfer): debit written to local
write-master, and in the SAME transaction a message is inserted into a queue for a consumer to
apply the credit on the other region's DB if cross-region; same-region transfers stay local.

**Positive, unprompted**: this is the transactional outbox pattern (studied 2026-09-28 via Cloud
Design Patterns), applied correctly and without being pointed at it — replaces the earlier
2PC-across-masters idea with a safer async pattern. Worth flagging as a strength in the review; not
praised mid-mock per style rules.

Follow-up asked: idempotency — if that queue message is delivered twice to the consumer (e.g. a
retry after a timeout), what stops the recipient's balance from being credited twice? Not yet
answered.

Candidate's answer: client-generated idempotency key, checked before processing; duplicate returns
the same response as the original without reapplying. Correct, textbook answer.

**Positive, mock-confirmed generalization**: this is the exact idempotency-key + duplicate-check
pattern already confirmed solid 3-for-3 in Build It prep
([[weak_areas_backend_concurrency]]/`coaching/current-priorities.md`) — first System Design mock
data point that it generalizes to this track too, unprompted.

**New gap surfaced**: candidate described "replication" of cross-region transfers, asked to clarify
whether that meant the earlier queue/consumer (outbox) mechanism or actual DB-level replication.
Answer: "two-phase commit with the message queued in RabbitMQ" — conflates two competing,
architecturally incompatible approaches to the same problem (2PC = synchronous/blocking/strong
consistency via a coordinator talking directly to both DBs; outbox+queue = asynchronous/
non-blocking/eventual consistency, no coordinator). Not just terminology — these represent
different consistency models and trade-offs. Pushed candidate to reconcile which one is actually
being proposed rather than stating the conflation directly.

Candidate's end-to-end walkthrough: EU side commits debit + outbox message in one local
transaction → queue → US consumer attempts the credit → on success, sends confirmation back → on
failure, "roll back the transfer in the European [side]" and return an error to the user. This
resolves the 2PC-vs-outbox conflation (it IS the outbox pattern), but surfaces two new issues:
1. **Timing contradiction**: if the user's response depends on hearing back from the US consumer
   before deciding success/failure, that reintroduces the full cross-region round-trip latency into
   the synchronous response path — in tension with the earlier established p99 < 500ms requirement
   and with "the EU side already committed" implying the user could have been told "sent" right
   after the local commit.
2. **"Rollback" after commit is the wrong term/mechanism**: the EU debit was already COMMITTED
   locally before the outbox message was even sent — you cannot roll back a committed transaction.
   Reversing it requires a compensating transaction (a new, separate credit-back), which is exactly
   the Saga pattern's core mechanic — studied 2026-09-28 via Cloud Design Patterns, not yet applied
   correctly here despite being fresh knowledge.
Asked ONE consolidated question surfacing both threads, then moving the mock forward regardless of
the answer — this single cross-region-consistency mechanism has now consumed a large share of the
~50 min budget; noting for the review as a time-management concern, not drilling further live.

Candidate's answer: resolves the timing tension by not giving an immediate synchronous success —
shows a pending/loading state to the sender, async-resolves to success/failure once the cross-region
step completes. Reasonable, realistic mechanism (real fintechs do show "pending" for cross-border
transfers). **But**: this quietly relaxes the p99 < 500ms "instant" target established in Phase 1
for the cross-region case, and the candidate did not proactively call that out or reconcile it
against the stated SLA — only described the new mechanism when pushed, didn't connect it back to
the constraint unprompted. Same shape as the chronic Build It weakness "reactive rather than
proactive self-catch" ([[weak_areas_backend_concurrency]]) — first System Design data point that it
recurs in this track too. Also: the "rollback after commit" terminology/compensating-transaction gap
from the previous question was not addressed in this answer — left as an open item, not re-pushed
live given the time already spent; noting for the review.
Cutting this thread here per the time-management call above — moving forward now.


## Phase 3 — Data model

Candidate's first pass: Users table; Transfers/Operations table with source user, destination user,
timestamp. Notably missing for a money-transfer system: amount, currency (both sides, given
cross-currency is core to the prompt), status, and the idempotency key mentioned earlier as part of
the mechanism, and the FX rate applied at transfer time (audit/reconciliation). Asked about
amount/currency + status only (2 most load-bearing gaps), bundled into one question given time.

Candidate self-corrected on currency ("you are right, I totally forgot") — added amount, currency,
and the FX rate applied at transfer time (good instinct, unprompted on the rate specifically).
Confirmed status field: pending / completed / failed. Data model now reasonably complete for this
depth level: Users; Transfers(source_user, dest_user, amount, currency, fx_rate, status,
timestamp) — idempotency key still not explicitly placed on the record, not re-probed given time.

## Phase 3 — Security

Candidate's design: third-party auth issuing JWTs (contains user ID, periodically refreshed/
regenerated), token validity checked per request. TLS/HTTPS terminated at the load balancer only;
internal traffic (LB → app servers) is plain HTTP.

Asked: is the cross-region queue traffic (EU→US outbox messages, carrying transfer details) also
encrypted in transit, or only the user-facing edge? Not yet answered — connects their own mechanism
to the security topic rather than opening a fresh generic checklist, given time already spent.

## Phase 4 — Scaling

Candidate: if a region's bandwidth/load grows too much, shard by user within the region, and reuse
the same queue/outbox mechanism for cross-shard transfers as for cross-region ones. Good instinct —
reusing an established pattern for a structurally similar new boundary, rather than inventing a new
mechanism per problem.

Asked (local→regional→global framing per Karim's email): what would the sharding key be, and does
the queue-based cross-boundary mechanism still hold up if Revolut expands to a third region
(Asia-Pacific), or does something change/break at that point? This is likely the last deep-dive
question given the time already spent — moving toward wrap-up after this.

Candidate's answer: pairwise queues + replicated workers/consumers between every pair of regions.
Didn't address the sharding-key half of the question. Worth flagging in the review, not pressed live
given time: a naive all-pairs queue topology is O(N²) in region-pairs as N grows (3 regions = 3
pairs, but growth is quadratic) — a hub/central-broker model would scale linearly instead. Good
enough signal on scaling reasoning overall (correctly identified that the mechanism needs to extend,
even if the topology itself wasn't optimized) — moving to wrap-up now.

## Phase 5 — Wrap-up
(not started)
