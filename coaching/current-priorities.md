# Current Coaching Priorities

_Last updated: 2026-09-24 (INTERVIEW DAY), after kata-001 through kata-012 (see below), plus three more full
mocks on 2026-09-23 — kata-024 (PASS), kata-025 (PASS), kata-026 (PASS, last full mock before today's
interview) — and the kata-013-focused → kata-023-focused coaching-drill series in between (not mock evidence,
see PRACTICED IN COACHING)._

## 🎯 INTERVIEW-DAY QUICK REFERENCE (read this first)

No more coding practice time — this is recall/review only. Ranked by urgency:

1. **Regression test immediately after any live fix.** Confirmed **5-for-5** (kata-008, 009, 010, 012, 026),
   never once broken. Purely mechanical — the moment you fix a bug mid-interview, the very next line is a test
   that would have failed without the fix.
2. **Bloom filter — name it.** kata-025: described the concept perfectly, could not produce the name, guessed
   "dict/hash table" (wrong on both properties). Recruiter-flagged topic. One-line recall: **Bloom filter** =
   probabilistic set membership, no false negatives, tunable false positives, O(1) bounded memory regardless of
   set size — "cheap membership check at scale, false positives OK."
3. **Composite sort/comparator: is there a real tie in your test?** 3-for-3 across kata-022/023/024 — a
   secondary/tie-break field's order silently determined correctness and shipped untested every time. Before
   moving on from any sort/heap/`ORDER BY`, ask this once, out loud.
4. **`SELECT ... FOR UPDATE SKIP LOCKED`** (not `NOWAIT`) for concurrent pollers on a shared queue — solid now
   (kata-024, kata-026), keep it loaded.
5. **When fixing a bug shaped like "invariant enforced in path A, not path B"** (kata-026: TTL-expiry checked in
   the read path, not in `release()`), the fix in one place doesn't mean the sibling path is safe — a 30-second
   grep for other reads/writes of the same field is cheap insurance.

Resolved, don't spend energy here: evasion-under-pressure, existence-vs-ownership, composite index ordering,
isolation-level vocabulary, idempotency-key + unique-constraint pattern (3-for-3 clean: kata-024/025/026),
transactional outbox (3-for-3 clean), deadlock-avoidance lock ordering, simplicity/no-overengineering.

## Overall trend
Assessment: BORDERLINE → PASS → PASS → PASS → BORDERLINE (leaning PASS) → BORDERLINE (leaning PASS) → PASS →
PASS → PASS → PASS → PASS (strong) → **PASS**. Kata-010 was the third consecutive clean mock on "evasion under
pressure": the first response to a direct trace question was again factually wrong (this time claiming a broken
check verified ownership when it only verified existence), but the candidate self-corrected immediately and
precisely once walked through a concrete scenario, with no hedging — that pattern stays fully resolved, and
kata-012 reconfirms it a fourth time (two separate live-bug traces, both diagnosed correctly on the first
answer). Two mechanical gaps hardened further through kata-010: **regression-test-after-live-fix is 3-for-3**
(kata-008, 009, 010) and **existence-vs-ownership authorization checks are 2-for-2** (kata-007, kata-010) — this
time the bug wasn't present from the start but was introduced as a *regression* while adding an unrelated
feature (the one-active-subscription invariant), a new and slightly scarier variant of the same defect family.
Kata-011 (no live application bug this time, so neither of those two streaks got new evidence either way)
surfaced no new correctness gaps at all — the only defect was a **test-hygiene issue: a duplicate test function
name silently dropped real coverage, now 2-for-2 (kata-008, kata-011)**, the same shape as the earlier duplicate
`test_withdraw_amount`. Deadlock reasoning (consistent lock ordering) and a multi-instance/Postgres migration
plan (strangler-fig, dual-source reads, incremental backfill, traffic-based cutover) both landed unprompted and
were more advanced than prior katas' equivalents — the strongest production-judgement showing of the ten mocks
so far. Kata-012 pushed **regression-test-after-live-fix to 4-for-4** (kata-008, 009, 010, 012) — now fully
mechanical and the single most confirmed gap in the tracker — but also gave the **first clean counter-example on
existence-vs-ownership**: a fresh `_validate_owner` check compared the caller against the job's actual stored
owner (not just existence) from the start, and held unchanged through two later extension stages, with no
scaffolding. One clean data point doesn't resolve a 2-for-2 negative streak yet, but it's the first positive
signal on that item. Kata-012 also surfaced a new shape of gap — not a design/correctness miss but **exact
terminology recall under pressure** (couldn't name "heap/priority queue" for O(log N) due-job scheduling; reached
for `NOWAIT` instead of `SELECT ... FOR UPDATE SKIP LOCKED` for concurrent-poller row skipping) — on vocabulary
the interviewer noted "recurs across scheduler/queue/rate-limiter-style problems," so closing it once should
generalize.

**Three more full mocks, all on 2026-09-23, all PASS**: kata-024 (support ticket dispatch), kata-025 (promo code
redemption), kata-026 (seat-hold service, last mock before today's 2026-09-24 interview). The scheduler
vocabulary gap closed cleanly (`SKIP LOCKED` recalled unprompted in kata-024, again — with one redirect — in
kata-026). Existence-vs-ownership is now fully resolved (clean in all three). A genuinely new, mock-confirmed
gap emerged and repeated: a composite comparator/sort tie-break field's order silently determining correctness,
3-for-3 across kata-022-focused/023-focused/024, the last one surviving a full mock completely uncaught. A
time-critical recall gap surfaced in kata-025 (Bloom filter: concept understood, name and properties not
recalled). Regression-test-after-live-fix extended its unbroken streak to 5-for-5 in kata-026. See the Quick
Reference at the top of this file for the condensed, interview-day version of all of this.

## RECURRING WEAKNESSES (aggregated view)
- Reactive self-catch instinct (fix what's pointed at, not proactively re-checked) — the chronic core weakness,
  12 mocks running, now including two cases where the first response under challenge was confidently wrong.
  Kata-011 continues it in a narrower form: the duplicate test name was self-fixed correctly once raised, but
  not self-caught before declaring the stage complete. Kata-012 continues it again: both live bugs (a lock
  wrapped around a lazily-evaluated generator; an unsynchronized cancel/execute race) shipped at "stage
  completed" and were only caught by pointed interviewer questions, not self-review.
- Live bugs get fixed but not locked in with a regression test — confirmed 4/4 (kata-008, kata-009, kata-010,
  kata-012). No new data point in kata-011 (no live application bug was found to fix). This is now the single
  most mechanically confirmed gap in the tracker.
- ~~Existence check confused with ownership/authorization check~~ — **RESOLVED**, see RESOLVED section (clean
  since kata-012, reconfirmed kata-024 and kata-026).
- Boundary type mismatches (str vs UUID) when a value crosses from a parameter into a typed/stored field —
  confirmed 2/2 (kata-008, kata-009), different concrete bug each time, same defect family. No new evidence
  either way in kata-010, kata-011, or kata-012 (kata-012's domain had no str/UUID boundary to test).
- Edge-case/validation test coverage as a standing gap shape vs. strong happy-path/concurrency tests —
  12 mocks. Kata-012 adds a specific variant: tests asserted only the returned DTO after job execution, not the
  underlying `job.status`, which is exactly how the missing-status-transition bug shipped unnoticed further than
  it should have.
- Test-suite hygiene (duplicate test names silently dropping coverage) — confirmed 2/2 (kata-008, kata-011),
  same defect shape both times (copy-paste rename missed). Elevated from a self-identified concept gap to a
  tracked recurring weakness now that it has recurred across mocks, per the user's own calibration in
  [[coaching-calibration-minor-findings]]. No new instance in kata-012 (no evidence either way).

## CURRENT PRACTICE PRIORITIES (mock-derived)

**HIGH — Add a regression test immediately after fixing any live bug found mid-mock**
Recurring: yes (kata-008, kata-009, kata-010, kata-012, kata-026) — now confirmed **5-for-5**, unbroken across
the entire series; per [[coaching-drill-vs-mock-evidence]] this should be an active, direct coaching drill, not
passive tracking.
Evidence: kata-008 — two live bugs fixed (same-account type mismatch; idempotency-ordering bug), zero
regression tests added. Kata-009 — the `get_stock()` unsynchronized-read bug was fixed live, again with no
regression test added afterward. Kata-010 — the cross-user cancellation authorization bug was fixed live, and
again no regression test followed; the pre-existing "different user" test still only covers a nonexistent user.
Kata-012 — two live concurrency bugs fixed (generator-laziness defeating a lock; unsynchronized cancel/execute
race), and again no regression test followed either fix. Kata-026 — a partial-hold rollback bug (no unwind of
already-held seats when a later seat in the same request was already held) was found and fixed live, correctly,
with zero regression test — a fifth consecutive clean miss.
Problem: Fixing a bug without a test protecting the fix means the same class of regression is invisible next
time the code is touched. This is the single most concrete, mechanical, repeated gap in the whole tracker — 5
consecutive mocks with a live bug, 5 consecutive mocks with no regression test for the fix.
Drill: Standing habit — the moment a bug is fixed mid-mock (self-caught or interviewer-surfaced), the very next
action is a test that reproduces it, before moving to the next task. Practice by intentionally seeding a bug in
a small snippet, fixing it, and only then being "allowed" to move on once a red-then-green test exists.

**HIGH — Composite comparator/sort tie-break correctness (new, elevated from coaching to mock-confirmed)**
Recurring: yes (kata-022-focused, kata-023-focused, kata-024 full mock) — 3-for-3, and kata-024 is the first
time this survived a full mock uncaught, not just a focused-kata drill.
Evidence: kata-022-focused — `EventStatus(enum.IntEnum)` declaration order silently became the tie-break field
in a heap comparator. kata-023-focused — a `@dataclass(order=True)` field order put `status` before `priority`,
accepted as a known trade-off after being shown a counter-scenario rather than fixed. kata-024 — `OrderedTicket`
used a random UUID4 as the tie-break instead of the stage's own stated requirement (creation order); no test
ever created two same-priority tickets, so it shipped silently through two stages and was only caught via a
Stage 4 discussion question — the underlying code bug was never actually fixed.
Problem: whenever sorting/comparing on multiple fields (dataclass `order=True`, a manual `__lt__`, a heap
tuple, `ORDER BY`), the field order itself determines correctness, not just aesthetics — and it has now shipped
uncaught in a full mock.
Drill: standing reflex — whenever writing or reviewing a multi-field comparator, ask "do I have a test with a
genuine tie on the leading field(s)?" before declaring it done.

**HIGH — Bloom filter recall under pressure (new, time-critical)**
Recurring: no (one full-mock data point, kata-025) — flagged HIGH given it is a recruiter-named topic and the
interview is today.
Evidence: kata-025 — asked for a memory-bounded probabilistic membership structure for a large "already
redeemed" check, correctly described the properties (probabilistic, bounded memory, false positives) but could
not produce the name "Bloom filter," and after a push, mischaracterized it as a dict/hash table (which has
neither property). This is the first applied test of the kata-020-bloomfilter drill from 2026-09-21, and it did
not generalize.
Drill: flashcard recall — name + one-line definition + trigger phrase (see Quick Reference above). No further
applied practice needed, just recall speed.

**HIGH — Watch str/UUID boundaries specifically when a value crosses into a stored/typed field**
Recurring: yes (kata-008, kata-009) — new tracked priority, promoted directly to HIGH given two independent
occurrences in the same defect family
Evidence: kata-008 — a same-account transfer check compared a string to a UUID, so the check silently never
fired. Kata-009 — `Reservation.product_id` typed `uuid.UUID` but assigned the raw string parameter, never
converted (currently inert only because nothing reads the field yet).
Problem: Two different bugs, same root shape — a value crosses a service-layer boundary and its type isn't
normalized at the crossing point. Currently invisible because tests don't assert on field types/values.
Drill: When reviewing any kata involving both UUID and string identifiers, explicitly check every point where a
raw parameter is stored into a typed field or compared against one, and write a quick field-level assertion
test right after — this would likely have caught both occurrences for free.
**Update (kata-026, 2026-09-23): no new str/UUID evidence either way** — the seat-hold domain used only `str`
seat IDs and `uuid.UUID` reservation IDs generated internally (`uuid4()`), no service-boundary crossing of a
raw string into a typed UUID field. Streak stays at kata-008/009 evidence only.

Concrete plan (from 2026-09-17 coaching session — full session log):
- Candidate initially proposed two fixes: (a) never type fields as `uuid.UUID`, always use validated `str`, or
  (b) rely on ruff to catch the mismatch. Self-corrected on (b) unprompted: ruff is a linter, not a type
  checker (confused it with `ty`/mypy). Confirmed environment: mock/real interview both run on the candidate's
  own PyCharm, so a locally-configured type checker is a genuine safety net in the interview itself, not just
  in practice.
- Core insight reached (after one Socratic nudge on the exact kata-009 case, where `product_id` was *already*
  typed `uuid.UUID` and still broke): **a type annotation with nothing checking it is documentation, not
  protection.** Python doesn't enforce annotations at runtime; kata-009's bug proves the annotation alone did
  nothing. This settled the decision to keep `uuid.UUID` typing (candidate's preference, and the objectively
  better domain model) rather than retreating to plain `str`, on the condition that enforcement is added.
- Root cause of "PyCharm already flags this but I miss it": the existing inspection is named **"Type
  checker"** in `Settings → Editor → Inspections → Python` (candidate was searching for "type hints", wrong
  name — worth remembering for next time this menu is needed) and renders at "Weak Warning" severity, styled
  faint gray via `Settings → Editor → Color Scheme → General → Weak Warning` — two separate settings
  (severity vs. visual style), both need checking.
- Agreed plan: (1) raise "Type checker" inspection severity to Warning/Error; (2) if still visually weak,
  brighten the "Weak Warning" color scheme entry directly; (3) fold a glance at the aggregated Problems panel
  into the existing end-of-stage self-catch checklist, instead of relying on catching the inline underline
  while typing under pressure.
- Also covered: for tests that *deliberately* pass a wrong type (e.g. asserting invalid-input handling), don't
  lower the global severity to silence the false positive — suppress locally instead, via `⌥+Enter → Suppress
  for statement` (PyCharm inserts `# noinspection PyTypeChecker`) or a manual `# noinspection PyTypeChecker` /
  `# type: ignore[arg-type]` comment on that exact line. Keeps the tool loud everywhere else.
- Status: this is a coaching-session plan, not yet verified — per [[coaching-drill-vs-mock-evidence]], only a
  future kata's mock feedback showing no str/UUID recurrence (or a recurrence despite the settings change)
  confirms whether it worked.
- Environment confirmed (kata-014-focused, 2026-09-20): the inspection now shows at Warning severity and is
  visible inline in the editor without needing to open the Problems panel — the 2026-09-17 setup plan is
  actually in effect. Still awaiting a future kata to confirm this translates into catching a real str/UUID
  boundary bug before it ships.
- New sub-shape, kata-022-focused (2026-09-21): the type-checker plan above covers Python type annotations, but
  this instance was a **schema-level** FK type mismatch — `events.card_id UUID REFERENCES cards(card_id)` where
  `cards.card_id` was `TEXT` — caught only when Postgres refused to apply the schema
  (`DatatypeMismatch: ... are of incompatible types: uuid and text`), not by any static check. Broadens the
  family from "a value crossing a service-layer boundary" to "two related table definitions disagreeing on a
  shared key's type" — worth a quick glance at FK column types matching their referenced PK type as part of any
  schema self-review, since PyCharm's type-checker inspection has no equivalent for this at the SQL-DDL level.

**HIGH — Follow through on verbally-agreed requirements**
Recurring: no (one occurrence, kata-008) — kept HIGH: distinct failure mode from general self-catch, no
counter-evidence yet since kata-009's domain didn't create an equivalent situation
Evidence: kata-008 — confirmed early (Stage 1) that deposit amounts must be positive, but `validate_amount`
stayed a no-op through all four stages. Never self-caught; not even raised by the interviewer.
Problem: A spoken agreement needs to become a checklist item, not just a talking point that gets lost once the
conversation moves on.
Drill: After any requirement is verbally confirmed with the interviewer, immediately write (or stub with a
`# TODO` revisited before the stage is declared done) the check.

**MEDIUM — Verify which lock guards a given piece of state before asserting thread-safety**
Recurring: no (new, kata-009, one data point) — but flagged distinct from the now-resolved evasion pattern:
this is a confidence/verification gap, not hedging
Evidence: kata-009 — `get_product_current_stock` read `stock` under the service-level lock, but all writes
happened under a separate per-product lock (genuinely unsynchronized). First answer to "is this thread-safe
end-to-end?" was an unqualified, incorrect "yes." Corrected immediately once a second, more pointed question
named the two lock objects directly. Bug survived silently through 2 stages of the candidate's own code.
Problem: In any design with more than one lock, "there's a lock around this" isn't sufficient — the specific
lock object guarding the specific state must be traced before asserting safety.
Drill: Whenever a design has more than one lock, before answering "is X thread-safe," trace and name out loud
which exact lock object guards every read and write of X.

**MEDIUM — Self-catch bugs and design gaps before being challenged (general correctness)**
Recurring: yes (kata-001–003, regressed kata-006/007/008/009/010, different concrete form each time)
Evidence: kata-010 continues the pattern — the cross-user cancellation bug above was found only via interviewer
line-by-line trace, not the candidate's own review.
Problem: The instinct is still reactive rather than proactive. This is the structural weakness underneath
several of the more specific items above.
Drill: At the end of every stage: (1) re-read requirements line by line, confirm each has code and a test; (2)
for any check whose name implies a comparison, verify it compares values not just existence; (3) for any state
guarded by more than one lock, name which lock guards which read/write.

**MEDIUM — Edge-case & validation test coverage**
Recurring: yes (kata-001 through kata-010)
Evidence: kata-010 — no regression test for the cross-user cancellation fix; the pre-existing
"different user" test still only covers a nonexistent user, not a valid-but-unrelated one.
Problem: Happy-path and concurrency tests are consistently strong; validation/edge-case and field-level
assertion tests are the consistent gap shape, now nine mocks running.
Drill: For every new check or field added, write the case where it should *fire*/be asserted as a standing pair
with the happy path.

**MEDIUM — Recall exact terminology for "many workers polling a shared due/ready set" (new, kata-012)**
Recurring: no (new, one data point) — flagged MEDIUM rather than LOW because the interviewer explicitly noted
this vocabulary "recurs across scheduler/queue/rate-limiter-style problems," so it's a generalizable gap, not a
one-off fact.
Evidence: kata-012 — could not name `heapq`/priority queue as the structure for O(log N) due-job scheduling
(the design shipped as an O(N) full scan instead, correctly self-diagnosed as a complexity problem but without
the standard fix). Separately, reached for `SELECT ... FOR UPDATE ... NOWAIT` to avoid concurrent pollers
blocking on the same row, which is wrong for that use case (`NOWAIT` aborts the whole statement instead of
skipping locked rows) — the correct answer, `SELECT ... FOR UPDATE SKIP LOCKED`, wasn't recalled even after a
follow-up prompt.
Problem: Both are close to boilerplate vocabulary for exactly this problem shape (a shared work queue polled by
multiple workers), which is common in backend interviews (schedulers, job queues, rate limiters, outboxes).
Missing them costs points on a question that's likely to reappear in different domain dressing.
Drill: Flashcard-style recall drill on "shared due/ready set polled by N workers" → `heapq`/priority queue
(with lazy-deletion for cancellation) for the in-memory version, `SELECT ... FOR UPDATE SKIP LOCKED ORDER BY
<due_column> LIMIT batch_size` for the Postgres version. Practice stating both unprompted the next time any
kata involves polling, scheduling, or a work queue.

**LOW — Skim the test file for duplicate function names before declaring a stage complete**
Recurring: yes (kata-008, kata-011) — 2-for-2, kept LOW per the user's calibration ([[coaching-calibration-minor-findings]]):
a hygiene finding, not a design/correctness judgment gap, and both mocks still scored PASS overall.
Evidence: kata-008 — a duplicate `test_withdraw_amount` silently shadowed the first definition. Kata-011 —
`test_earn_points_invalid_input` was copy-pasted for the `redeem_points` case without renaming; Python module
semantics mean the second definition silently discarded the first, so `earn_points`'s invalid-input parametrized
cases never actually ran despite a green suite. Both times only surfaced via a direct interviewer question about
pytest collection semantics, self-fixed correctly once raised, not self-caught before "stage completed."
Problem: This specific hygiene slip is the one that actively masks real coverage (unlike a typo or unused
parametrize arg) — a green suite silently means less than it appears to.
Drill: Before saying a stage is done, a 5-second skim of test function names in the file for exact duplicates.
Also default to a pytest-discoverable filename (`test_*.py`/`*_test.py`) — kata-011's `test.py` wasn't collected
by a bare `pytest` invocation.

## PRACTICED IN COACHING (2026-09-18) — AWAITING NEXT KATA VERIFICATION
Per [[coaching-drill-vs-mock-evidence]]: drilled with scaffolding in a coaching session, not yet confirmed
unprompted under mock pressure. Only promote to RESOLVED once a future kata's `feedback/kata-XXX.md` shows the
behavior on its own; if it recurs, move back to CURRENT PRACTICE PRIORITIES with the added evidence.

- **kata-023-focused (2026-09-22)** — mechanic drilled: priority-ranked claim queue with a TTL-based lease (many
  workers reclaiming a shared pool via explicit lease expiry, distinct from the immediate claim/dequeue of
  013–018/022), new domain (fraud-review case queue), full in-memory → SQL port; `mark_case_completed`'s SQL port
  and a concurrent-complete race were dropped for time — in-memory Stage 2 fully done, SQL Stage 2 covered only
  `claim_next_case`.
  - **New sub-shape of the composite-sort-key-ordering bug family (3rd instance across 2 sessions, after
    kata-022's two)**: `Case`'s `@dataclass(order=True)` field order put `status` before `priority` in the heap
    comparator, so any UNCLAIMED case — regardless of priority — always outranked a CLAIMED-but-lease-expired
    case, even a HIGH-priority one. Confirmed live (a LOW-priority fresh case beat a HIGH-priority reclaimable
    one). Proposed reordering fields to lead with `priority`; when shown a concrete counter-scenario (an active,
    not-yet-expired HIGH claim would then short-circuit the `while` loop's `return None` and starve a
    genuinely-available LOW-unclaimed case), chose not to trace it through and reverted to the original field
    order, explicitly accepting the original bug as a trade-off rather than resolving it. A defensible
    time-boxed call, but the underlying mechanism (a static heap comparator can't correctly rank
    "unclaimed-or-expired" together when availability depends on `now`, which changes without any heap
    operation) was not derived unprompted.
  - **SQL side of the same family, new mechanism**: `ORDER BY (priority, claimed_at) NULLS FIRST` — the
    parenthesized pair is a row constructor, not multi-column ordering; `NULLS FIRST` only affects whole-row
    nullness (never true here) and silently left NULL (`claimed_at`, i.e. unclaimed) sorting *last* within a
    priority tier. Not self-caught; surfaced only by the coach running a raw `ORDER BY` against real Postgres.
    Could not derive the correct multi-column form unprompted when asked directly — given the fix per the
    focused-kata "if you give up, teach it" rule (`ORDER BY priority, claimed_at ASC NULLS FIRST`, no parens).
    Fixed and verified. Worth noting: the SQL version, once fixed, achieves the fuller-correct "priority governs
    regardless of claim status" semantics that the in-memory heap couldn't without restructuring — the same
    mechanic has a different achievable correctness trade-off depending on data structure, a good point to be
    able to articulate in an interview.
  - **SQL transaction hygiene recurs a 2nd time (after kata-014-focused)**: `claim_next_case`'s SQL port had no
    `conn.commit()` on either return path, leaving the `FOR UPDATE`-acquired row lock in a dangling open
    transaction. Not self-caught; fixed correctly and completely once asked to trace the connection's state
    after return. Two data points now on commit/rollback discipline after a SQL state transition.
  - **`SELECT ... FOR UPDATE SKIP LOCKED` recalled and written correctly unprompted this time** (in the query
    itself, no nudge needed) — continues the positive trend from kata-018 for the in-memory `heapq` half; the
    *why* vs. plain `FOR UPDATE` needed one round of sharpening — first answer ("both block, one does nothing")
    was directionally right but missed the precise mechanism (the blocked transaction doesn't get the
    next-best candidate after unblocking; `LIMIT 1` already fixed the plan on one specific row, re-checked via
    EvalPlanQual and simply dropped, returning zero rows even if other cases are available).
  - **Existence-vs-ownership-shaped gap, in-memory, self-corrected under pushback**: `mark_case_completed` on a
    never-claimed case succeeded if the caller passed `worker_id=None` (matches the `Case` default sentinel).
    Correctly flagged as a bug on first read, then briefly walked back ("worker_id es None, no es un bug real"),
    reasoning a real caller wouldn't pass `None` — reversed again once pushed on trusting an
    unvalidated/runtime-unenforced boundary assumption, fixed (reject completing an `UNCLAIMED` case) and
    verified. The wobble-then-correct-under-pushback shape is new — distinct from the already-RESOLVED
    hedge-on-a-hypothetical pattern, since the first instinct here was already correct; light watch for
    recurrence.
  - **Concurrency (in-memory), clean**: single service-wide lock, correctly justified (the shared heap array is
    mutated by every method, so per-case locks wouldn't protect it) — verified for real, 20 threads / 4000 claim
    attempts, zero double-claims. Correctly caught and corrected a "the GIL protects `get_claim_pool_size`"
    over-generalization with one nudge, landing precisely on the real boundary (GIL makes a single bytecode op
    atomic, not a compound one like list iteration), then made a sound, explicit trade-off call to keep the
    lock anyway given the negligible cost.
  - **Verified for real, SQL**: 10 concurrent connections racing 30 cases, all 30 claimed exactly once, zero
    duplicates, after the ORDER BY and commit fixes above.
  - Verification needed: none of this is mock evidence. `mark_case_completed`'s SQL port and a
    concurrent-complete race were not reached this session — candidate for a follow-up if this mechanic
    (priority + TTL-lease queue) comes up again before Thursday.

- **kata-022-focused (2026-09-21)** — mechanic drilled: transactional outbox pattern (Databases example listed
  in `modes/coach.md`, never drilled in focused-kata format before), tied to the still-open kata-018 watch item
  ("a claim/dequeue operation ported to SQL needs an explicit interim state") and to Revolut priority #9
  (distributed systems/reliability). New domain (card freeze/unfreeze → push-notification outbox), full
  in-memory → SQL port.
  - **New, sharper instance of an already-tracked bug shape, found twice in one session in two different forms**:
    a composite sort key's *declared/default order* silently determining correctness, not just aesthetics.
    In-memory: `EventStatus(enum.IntEnum)` declared `CLAIMED` before `NOT_DELIVERED`, so any single validly-claimed
    event (not even expired) sorted ahead of every fresh event in the heap and made `claim_next_event()` return
    `None` for the **entire service** — one in-flight claim silently starved every other worker. Found unprompted
    by the candidate while tracing a two-worker scenario the coach set up, without being told where to look.
    SQL: Postgres's default `NULLS LAST` on `ORDER BY claimed_at ASC` meant expired-and-reclaimable events were
    served ahead of never-touched fresh events — same conceptual mistake (assumed ordering matched intended
    priority without checking), different mechanism (enum declaration order vs. SQL NULL-ordering default,
    genuine new library-knowledge gap, fixed correctly once told `NULLS FIRST` exists).
  - **New, more severe bug: TTL/lease expiry condition had an inverted sign.** `claimed_at > now_minus_ttl`
    (reads as "still valid") was used where `claimed_at < now_minus_ttl` ("expired") was needed — the poller
    could re-claim an event **before** its lease expired, letting two workers hold the same event simultaneously
    well within a 60s TTL. This is a genuine concurrency-safety violation, not a priority/fairness nit like the
    two bugs above — found only by the coach constructing and running a concrete two-worker-one-second-apart
    scenario against real Postgres; not self-caught before declaring the stage done.
  - **Third instance of the str/UUID-family boundary mismatch, new sub-shape**: `events.card_id UUID
    REFERENCES cards(card_id)` where `cards.card_id` was `TEXT` — a schema-definition-level FK type mismatch,
    caught only by Postgres refusing to apply the DDL (`DatatypeMismatch`). See the updated note on the HIGH
    str/UUID item above.
  - **Design gap, kept out of scope deliberately**: neither the in-memory `Event` nor the initial Postgres
    `events` table carried any business payload (which card, what new status) — an outbox event with an empty
    envelope. Raised directly by the coach; the candidate explicitly chose to leave Stage 1 as-is and add the
    payload (`card_id`, `card_action`) only in the Postgres schema, accepting the inconsistency between tracks
    as a deliberate scope call rather than fixing both — a legitimate call for a time-boxed exercise, noted for
    completeness rather than as a gap to redrill.
  - **Positive, unprompted**: reached for the `now: datetime | None = None` injectable-clock parameter (same
    family as the already-RESOLVED testable-clock item) without being asked, in both the in-memory and SQL
    services. Correctly reasoned through the `None`-vs-`datetime` heap-comparison trap from `kata-019` and
    proactively asked how to avoid it *before* writing the buggy version, rather than after.
  - **Verified for real, both tracks**: in-memory two-worker starvation scenario, Postgres TTL sign fix, Postgres
    NULLS FIRST fix, and 50 events claimed exactly once with zero duplicates across 10 concurrent Postgres
    connections.
  - Verification needed: none of this is mock evidence. The "run your own code before declaring done" theme
    continues unbroken (7th session: 013–018, 022) — none of the four bugs above were self-caught before saying
    a stage was complete, all found by the coach actually executing the code. The composite-sort-key-ordering bug
    shape (now 2 instances in one session, one in-memory/one SQL) and the TTL-sign-inversion bug are both new,
    worth a light watch if either recurs in a future kata.

- **kata-019-algorithms / kata-020-bloomfilter / kata-021-grafos (2026-09-21)** — a new, separate supplementary
  track, outside the Revolut concurrency/SQL weighting: after the user reviewed two external kata sites
  (codekata.com, kata-log.rocks/tdd) a recruiter pointed them to ahead of Thursday's interview, we jointly
  concluded almost all of both sites' katas were redundant with this repo's existing TDD/OOP practice, except
  three gaps: (1) sorted-structure/heap trade-offs beyond what scheduler katas already drilled, (2) Bloom
  filters (never covered), (3) basic weighted-graph shortest path (never covered, first time doing graphs in
  Python at all). One session per topic, numbered like focused katas but with a topic suffix instead of
  `-focused`, no SQL-port requirement (doesn't apply to these mechanics).
  - **kata-019-algorithms** (support-ticket queue): correctly derived the negate-priority-for-max-heap trick and
    the tuple/dataclass-comparator tie-break reasoning with light scaffolding; caught unprompted that a heap's
    internal array is only heap-ordered, not fully sorted, once asked the right question, and derived the
    copy-and-drain pattern for a non-destructive sorted view. Needed two passes to fully fix a
    negate-before-validating-type bug (first fix moved the negation but left a value that could crash the error
    message itself for non-negatable types). `resolve()` shipped as a no-op `pass` under a declared-done Stage 2
    — caught only because the coach traced it, not self-caught.
  - **kata-020-bloomfilter** (card blocklist pre-check): genuinely new material (first Bloom filter). Needed
    the concept, and separately the `m`/`k` sizing formulas, taught with concrete worked numeric examples
    (abstract explanation alone didn't land — see [[teaching-new-material-calibration]]) — once grounded in
    real numbers, applied the formulas and the double-hashing index derivation correctly and finished a
    verified-correct implementation (0 false negatives over 50k checks, 0.504% measured false-positive rate
    against a 0.5% target). One bug: `-> iter[int]` as a return type hint (confusing the builtin function `iter`
    with a generic type) crashed the module on import — not caught until asked directly whether the code had
    ever been run. Same "run your own code before declaring done" shape as the SQL-track focused katas
    (013–018), now confirmed to recur outside that track too.
  - **kata-021-grafos** (cheapest currency-conversion path): first-ever graph/Dijkstra implementation in Python.
    Initial theory pass assumed too much background (BFS, Big-O, NP-hard, DAG terms) and had to be restarted
    from real zero once the user said so directly — see [[teaching-new-material-calibration]]. Once re-taught
    with a fully concrete step-by-step trace on the user's own EUR/USD/GBP example, implemented Dijkstra +
    path-reconstruction (`came_from`-equivalent dict) correctly on the first pass, including understanding
    unprompted why an early break on popping the target node is still correct (heap-minimum property). Found the
    "unreachable target" edge case unprompted (no coaching nudge), then caught on their own that their first
    regression test for it didn't actually reproduce the disconnected case (the test graph was accidentally
    still connected) — a clean, real-time self-catch instance.
  - Verification needed: none of this is mock evidence, and none of it maps to the Revolut concurrency/SQL
    priorities above — this is a separate, lower-priority supplementary track done as a hedge against a
    non-concurrency coding-stage question. No further sessions planned unless a specific topic needs a repeat.

- **kata-018-focused (2026-09-20)** — mechanic drilled: "many workers polling a shared due-item set" again
  (Revolut priority weighting, first flagged kata-012, previously drilled once in kata-013-focused), new domain
  (webhook delivery retry queue), full in-memory → SQL port.
  - **In-memory: `heapq` recalled unprompted, correct on the first pass** — a cleaner data point than
    kata-013-focused, which needed the module name prompted directly.
  - **SQL: `SELECT ... FOR UPDATE SKIP LOCKED` was NOT recalled unprompted a second time.** `poll_due` shipped
    with plain `FOR UPDATE` (no `SKIP LOCKED`) and was only caught by running two real concurrent connections and
    showing one blocking ~1.2s on an unrelated row that was free the entire time. Fixed correctly and instantly
    once shown. Now 2-for-2 needing the SQL half surfaced by the coach rather than reached for independently,
    while the in-memory half (`heapq`) looks to have generalized cleanly — split verdict on this item.
  - **New, generalizable gap: porting a "claim" operation to SQL needs an explicit interim state.** Popping an
    entry from the in-memory heap naturally removes it from consideration until `schedule()` re-inserts it; the
    first SQL `poll_due` had no equivalent — a claimed row stayed `status = 'pending'` with an unchanged
    `next_attempt_at`, so the *same* row was returned again by a second `poll_due` call on the *same connection*,
    zero concurrency involved. Deterministic double-claim, not a race. Diagnosed correctly and completely on the
    first attempt once demonstrated concretely ("I need to change the status to running") — added the
    already-defined-but-previously-unused `Status.RUNNING` transition inside the same claiming transaction,
    verified clean under 20 real concurrent Postgres connections against 200 deliveries afterward (200
    delivered, 0 duplicates). Watch for recurrence in any future kata porting a queue/dequeue-shaped mechanic to
    SQL — this is the actual "no double processing" requirement, not a side detail.
  - **"Run your own code before declaring done" — 6th focused-kata session running the same shape, heaviest
    diagnostic value yet.** Found only by the coach actually executing the code: two ambiguous-column errors
    (`ON CONFLICT DO UPDATE SET attempts = attempts + 1`, ambiguous between the target table and `excluded`; the
    identical fix needed a second time on an unrelated `WHERE id = ...` in the same statement, suggesting the
    *principle* didn't fully generalize the first time it was explained), the missing `SKIP LOCKED` above, an
    `attempts` off-by-one in the returned DTO (read before the increment instead of after), a `<` vs `<=`
    boundary mismatch against the in-memory version, a stale `status='pending'` hardcoded into the DTO after the
    row had already moved to `'running'`, and the deterministic double-claim bug. None were self-caught before
    declaring a stage "done." Given six sessions running (013 lightly, 014–018), recommend promoting this to its
    own named watch item distinct from the general reactive-self-catch weakness.
  - **Testable-clock discipline (from kata-017-focused) recurred as a fast, but still prompted, catch.** The
    schema's `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` (checked via `next_attempt_at >= updated_at`)
    reintroduced a real-wall-clock dependency, same shape as kata-017's `DEFAULT now()` bug — fixed correctly and
    instantly once asked, but not self-caught during initial schema design. Second coaching-session data point on
    the same lesson; still awaiting an unprompted catch.
  - **Composite index ordering**: initially just `(next_attempt_at ASC)`; corrected to `(status, next_attempt_at
    ASC)` — equality-before-range — immediately and correctly once asked to reconcile it with the template's own
    stated advice directly above it. Needed the nudge to reconsider, but the fix itself was exactly right.
  - **Lock-granularity reasoning (in-memory) was a genuine strength this session**: correctly proved, via a
    concrete two-critical-section thought experiment, that splitting the heap-pop and the status-check/increment
    into separate locks reintroduces the exact race a single lock prevents — then correctly identified (after an
    initial wrong "no") that even two threads interested in *unrelated* deliveries must still serialize on the
    shared heap, making a single service-level lock the structurally correct choice, not a shortcut.
  - Verification needed: none of this is mock evidence. The SQL-side `SKIP LOCKED` recall and the SQL
    claim/state-transition gap are the two most important open threads for a future kata/mock to test
    unprompted.

- **LOW — Hand-waving a cross-structure consistency question before getting precise** (from kata-010: asked
  whether two subscriptions for the same user could momentarily both report `status == active`, first answer
  framed it as acceptable "eventual consistency" instead of tracing that `subscription.cancel()` runs outside
  `self._lock`).
  - Drilled via guided Socratic questions (multiple-choice framing, then open trace): candidate correctly
    identified, with scaffolding, that "eventual consistency" alone doesn't settle it — you need both (a) an
    actual bound on how long the window can stay open (none exists here; the thread could be preempted
    indefinitely after releasing the lock) and (b) whether any consumer treats `status` as ground truth during
    that window (e.g. a billing check, which would be a real risk).
  - Correctly proposed the fix unprompted once asked directly: move the `subscription.cancel()` status mutation
    inside the same `self._lock` critical section as the index removal, serializing it against
    `create_subscription`'s own lock-protected insert. Also named the trade-off unprompted (slightly longer
    lock hold, negligible cost since the added work is one attribute assignment).
  - Scaffolding needed: a guided multiple-choice question to get from "it's fine" to "both factors matter";
    everything after that (the fix, the trade-off) was reached independently.
  - Verification needed: a future kata where a similar dual-structure consistency question comes up in the
    technical discussion, with no coaching scaffolding, first response precise rather than reaching for a
    generic term.

- **MEDIUM — Recall exact terminology for "many workers polling a shared due-item set"** (from kata-012: couldn't
  name `heapq`/priority queue, reached for `NOWAIT` instead of `SKIP LOCKED`). Drilled directly in
  `kata-013-focused` (2026-09-19), a focused-kata coaching session (Python in-memory implementation, then a real
  PostgreSQL port via `psycopg` against a local Docker instance — see [[revolut-interview-prep]] for the new
  focused-kata format).
  - In-memory track: correctly used `heapq` once the module name was recalled (needed one direct answer, not
    self-recalled), including a correct indexed-lookup + lazy-deletion pattern (dict for O(1) lookup/cancellation,
    heap purely for ordering) reached through guided questions, not handed over.
  - SQL track: correctly wrote `SELECT ... FOR UPDATE SKIP LOCKED ... LIMIT 1` once prompted on the specific
    clause names — confirmed recall of the *concept* (why `SKIP LOCKED` beats blocking or `NOWAIT` for concurrent
    pollers) but needed the clause syntax and ordering rules (`FOR UPDATE`/`SKIP LOCKED` must follow `ORDER BY`/
    `LIMIT`, not precede them) corrected via a real Postgres syntax error — expected, since this was the
    candidate's first hands-on SQL session of the whole series.
  - Verification needed: unprompted, correct recall of both `heapq` and `SKIP LOCKED` (name and clause order) in
    a future kata or focused session, without a nudge.

- **NEW — Building a SQL query via raw string interpolation of values (SQL injection anti-pattern)**, found in
  `kata-013-focused` (2026-09-19): the first `INSERT` attempt used an f-string to embed `notification_id`,
  `payload`, and `due_at` directly into the SQL text, instead of parameterized placeholders. Not self-caught;
  flagged directly as a security issue (not just a syntax bug) since `payload` is caller-controlled input in this
  domain. Corrected immediately and completely once flagged — every subsequent query in the session used
  `%(name)s` placeholders with a parameters dict correctly. One occurrence, first-ever SQL-writing session, so
  not yet a tracked pattern — but given the severity class (OWASP-top-10, not a style nit), watch closely in the
  next SQL-focused session for any recurrence, which would elevate this to a real priority regardless of how
  early in the prep series it is.

- **kata-017-focused (2026-09-20)** — mechanic drilled: rate limiting with **time** as a first-class correctness
  factor (token bucket), full in-memory → SQL port. By far the most bug-dense of the four focused-kata sessions
  so far — worth treating as the strongest evidence yet on two existing coaching threads:
  - **"Run your own code before declaring done" (from kata-015/016) is now confirmed a 4th and much heavier
    time**: roughly 8 distinct bugs across both tracks this session, several complete-mechanism-failures (a
    version that dropped token consumption entirely, always allowing every request; a control-flow indentation
    bug — `return_value = True` unconditionally following an `if` block — that made the SQL version always
    return `True` regardless of actual availability). None were self-caught before declaring a stage/fix "done"
    — every one surfaced only because the coach actually ran the code. This is coaching evidence only (per
    [[coaching-drill-vs-mock-evidence]]), but four sessions running (014 light, 015 heavy, 016 heavy, 017
    heaviest) is enough to treat "run it before you say it's done" as the single most important standing habit
    to carry into the next real mock.
  - **`fetchone()` after a non-`RETURNING` `UPDATE`/`INSERT` recurred a third straight session** (015, 016, 017)
    — same exact crash shape each time. Worth a mechanical habit: when writing an `UPDATE`/`INSERT` you plan to
    `fetchone()` after, add `RETURNING` in the same edit, never as a separate afterthought.
  - **New, real gap — fractional-state rounding instinct**: when moving from integer to float token counts,
    proposed rounding the refill amount (to "keep it an int") not once but twice after being shown why a
    truncated/rounded fraction is lost forever, call after call, and never reached "just keep it a float, only
    the final `< 1` check needs an integer-ish threshold" independently — had to be told directly. Distinct from
    the general self-catch pattern; this is a specific conceptual gap in the fractional-accumulation model worth
    a light watch in a future time-based mechanic.
  - **New instance of the tracked str/UUID boundary-crossing shape**: Postgres `NUMERIC` round-trips as Python
    `decimal.Decimal`, not `float` — mixing it with `timedelta.total_seconds()` (always `float`) raised a
    `TypeError`. Same defect family as the HIGH str/UUID item — a value crossing a boundary (DB → Python)
    without being normalized at the crossing point — logged there for cross-reference.
  - **Positive, continuing**: pre-apply schema review caught a real bug before it ever touched the database —
    `CHECK (available_tokens > 0)` would have rejected the fully-normal "bucket is empty" state, and had no
    upper bound at all. Same "catch it before applying" pattern as kata-014's status-value bug — now 2-for-2.
  - **Positive, instructive**: correctly diagnosed, once traced, that `last_computed_at TIMESTAMPTZ NOT NULL
    DEFAULT now()` silently reintroduced a dependency on *real* wall-clock time for a brand-new bucket's initial
    state — directly undermining the testable-clock principle the whole kata was built around. Fixed correctly
    by having the `INSERT` set `last_computed_at` explicitly from the caller's `now`.
  - Verified for real, both tracks: exactly 5-of-20 concurrent requests allowed for the same client, in-memory
    and against real Postgres, matching the cap precisely each time.

- **kata-016-focused (2026-09-20)** — mechanic drilled: deadlock avoidance via consistent lock ordering across
  two related resources (Revolut priority #5) — previously only confirmed in full mocks, first time drilled in
  focused-kata format. Domain: account-to-account transfers, full in-memory → SQL port.
  - In-memory: implemented consistent account-id-based lock ordering **unprompted, first pass**, with no trap
    needed to surface it — reconfirms the already-RESOLVED "deadlock fix via lock ordering" mock item, now also
    holding in this format. When pushed to explain *why* (not just "to avoid deadlocks"), gave a precise,
    correct circular-wait trace unprompted-mechanism-level, not a hand-wave. Verified for real: 400 concurrent
    crossed in-memory transfers (200 each direction), no deadlock, balances conserved exactly.
  - SQL: correctly recalled, once told directly (this is a genuinely non-obvious Postgres internal, not
    something reasoning alone would derive), that `SELECT ... FOR UPDATE ORDER BY x` does **not** guarantee lock
    acquisition order — `LockRows` runs before `Sort` in the plan. Correctly implemented the safe alternative
    (two separate single-row `FOR UPDATE` statements issued in sorted order) and it held under 400 real
    concurrent crossed transfers against actual Postgres — no deadlock, balances conserved exactly.
  - Gap: the SQL `transfer` initially had no application-level insufficient-funds check at all, relying solely
    on the table's `CHECK (balance >= 0)` — correctly self-diagnosed the failure mechanism when asked to trace
    it (`CheckViolation` on the `UPDATE`), but didn't know `psycopg.errors.IntegrityError` existed as the
    general constraint-violation parent class (asked directly, genuine library-knowledge gap, not a design
    miss). Fixed correctly once told: catch, rollback, raise a clean domain `ValueError` — verified for real
    that the connection is fully reusable immediately after the failed transfer, not left aborted.
  - Two small copy-paste-shaped bugs (wrong variable in an f-string error message; a `-> None` signature that
    still `return`ed a value) — both self-fixed without further discussion once flagged, same "typo self-fix
    once pointed at" shape as kata-014/015, still not self-caught before declaring stages done.
  - Verification needed: none of this is mock evidence. The deadlock-ordering result is a positive confirmation
    in a new format of an already-resolved item — no action needed unless it regresses. The `IntegrityError`
    gap and the "run your own code" theme continuing across three straight focused-kata sessions (013 lightly,
    014, 015 heavily, 016) are the two things worth watching in a future mock.

- **kata-015-focused (2026-09-20)** — mechanic drilled: pessimistic vs. optimistic concurrency control on the
  same operation (Revolut priority #6), domain: flash-sale stock counter, full in-memory → SQL port.
  - **New, sharper instance of the chronic reactive-self-catch weakness**: across the whole session, every
    single bug below was found by the coach actually running the candidate's code (in-memory traces, and for
    SQL, literally executing it against real Postgres) — none were self-caught before declaring a stage
    "done," and several were basic crashes that running the code once would have surfaced immediately. This is
    a concrete, mechanical framing worth drilling directly: **run your own code before declaring a stage
    complete**, not just for SQL but everywhere. Tally this session: `row = cur.fetchone() is not None` (a
    boolean-not-subscriptable crash on the very next line), `cur.fetchone()` called after an `UPDATE`/`INSERT`
    with no `RETURNING` clause (twice), and a missing `f` prefix on an interpolated error string (twice, same
    exact shape both times — not caught by the first instance).
  - In-memory optimistic implementation, first pass, was **not actually optimistic**: `get_version()` took a
    lock and *mutated* the version counter on every call (including reads), so every concurrent caller
    conflicted with every other one before even reaching the real check — functionally closer to pessimistic
    locking but with added retry/backoff overhead, i.e. worse than Stage 1's simple lock for no benefit.
    Self-corrected precisely once walked through a concrete two-thread trace and asked whether reads should
    mutate state: moved to reading `version` unlocked and only writing (version bump + decrement) inside the
    single atomic critical section — the correct textbook pattern, and one they then reproduced faithfully and
    correctly in the SQL track's conditional `UPDATE ... WHERE version = ...` unprompted.
  - Separately, dropping the Stage 1 service-wide lock for Stage 2 silently removed protection from
    `_purchases_by_sku_id` (a dict-of-lists, not related to the stock/version CAS at all) — a real check-then-act
    race on first-ever-purchase-per-SKU that could silently drop a buyer's purchase record. Self-fixed well once
    pointed at: added one small, correctly-scoped lock just for that dict, without reintroducing contention on
    the actual purchase path.
  - **PostgreSQL FK-index question recurs** (asked directly this time rather than asserting the MySQL-style
    auto-index misconception, unlike kata-009) — still evidence the fact hasn't stuck; watch for a third
    occurrence.
  - Strength, unprompted: correct, precise trace and real-concurrency verification of `SELECT ... FOR UPDATE`
    blocking semantics (predicted then confirmed 1-success/4-fail under 5 real concurrent connections). Closing
    trade-off answer (optimistic vs. pessimistic) was precise and included a genuinely advanced point not
    prompted for: prefer optimistic when the check step includes a slow external call, since pessimistic would
    hold a lock across it.
  - Verification needed: none of this is mock evidence. The "run your own code before declaring done" framing
    is new this session — watch for whether it recurs in a future mock/focused kata before promoting it to a
    tracked priority in its own right, distinct from the general self-catch item it's currently filed under.

- **kata-014-focused (2026-09-20)** — mechanic drilled: an ownership check touched mid-session by an unrelated
  feature (see the HIGH ownership-check item above for the main result), plus a full in-memory → SQL port.
  Domain: a document service with owner-only soft-delete.
  - Concurrency (in-memory): `get_document` read the mutable `status` field *outside* the lock's critical
    section while `delete()` mutated it *inside* the lock — a genuine unsynchronized read, same shape as the
    kata-009 lock-identity gap. Self-corrected precisely and completely once pointed at (moved the DTO
    construction inside the `with self._lock:` block), with none of the "eventual consistency" hand-waving
    flagged after kata-010 — a clean counter-signal on that specific evasion pattern.
  - New finding — SQL transaction hygiene: `delete_document`'s two failure paths (`DocumentNotFound`,
    `DeletionDenied`) raised without calling `conn.commit()` or `conn.rollback()` first, leaving the connection
    in a dangling open transaction. Not self-caught before declaring the stage complete (same reactive-self-catch
    shape as ever); fixed correctly and completely (rollback added to both paths) once asked to trace the
    connection's state after the raise. One data point — watch for recurrence in a future SQL-track session
    before treating it as a tracked pattern.
  - Schema bug (self-inflicted, caught pre-apply): the `status` CHECK constraint listed `'completed'` instead of
    `'deleted'`, not matching the actual `DocumentStatus` values — caught in review before the schema was ever
    applied to the database, fixed correctly.
  - Isolation-level precision: correctly explained that Postgres re-evaluates (`EvalPlanQual`) a blocked
    `UPDATE`'s `WHERE` clause against the post-commit row version once unblocked, and correctly identified that
    Read Committed "being enough" here is specific to the single-statement atomic `UPDATE ... RETURNING`
    pattern — a separate SELECT-then-UPDATE would reintroduce the race and need `SELECT ... FOR UPDATE` or
    Serializable instead. Reinforces the already-RESOLVED isolation-level item, no action needed.
  - Verification needed: none of this is mock evidence — the ownership-check result feeds the HIGH item above;
    the transaction-hygiene finding is new and just a light watch for now.

- **Counter-signal (positive) on the chronic reactive-self-catch weakness**: in the same session, unprompted and
  before being asked to fix anything, the candidate identified that a single `UPDATE ... RETURNING status` for
  `cancel_notification` couldn't distinguish "id doesn't exist" from "id exists but isn't cancellable" from a
  bare empty-`RETURNING` result — and proposed a correct, safe follow-up diagnostic read to disambiguate without
  reintroducing a check-then-act race. Narrow in scope (one specific ambiguity, not a full self-review), but a
  genuine, real-time instance of the self-catch instinct the tracker has flagged as chronically reactive rather
  than proactive across 12 mocks. Not mock evidence (per [[coaching-drill-vs-mock-evidence]]), but worth noting
  as a positive data point to watch for recurrence.

## RESOLVED / IMPROVED (do not re-drill unless it regresses)
- **Commit to a direct, unhedged answer about current code behavior before offering a hypothetical fix** (was
  HIGH, 2-for-2 evasive in kata-006/007): kata-008 was the first mock where every first response was direct.
  Kata-009 and kata-010 each confirm it again — in both, the first factual answer was *wrong* rather than
  evasive (kata-009: a confidently wrong thread-safety claim; kata-010: a confidently wrong description of what
  a check verified), but neither hedged or pivoted to a hypothetical, and both corrected immediately and
  precisely once pushed. **Fully resolved, three mocks running** — retire from active tracking. (The residual
  issues, tracked separately above, are about verification/precision under confidence, not evasion.)
- **Lock granularity applied by habit** (was MEDIUM, downgraded to LOW after kata-005/007/008): kata-009 adds a
  fourth consecutive good showing — the per-product lock was introduced with reason and used consistently
  through every read/write after the Stage 2 refactor, with no dead/unused locking code (a direct contrast with
  kata-006, the sole outlier). **Resolved** — retire from active tracking.
- **Composite index column ordering** (open since kata-005): kata-007 converged unprompted on
  `(room_id, start, end)`. RESOLVED per real mock evidence.
- **Isolation-level vocabulary under pressure** (resolved after kata-006, reconfirmed kata-007): durable across
  multiple scenario shapes.
- **Testable clock injection** (resolved after kata-006): no regression signal since.
- **Idempotent-retry pattern (key + unique constraint + return-prior-result)**: kata-007, kata-008 both gave
  this precisely and unprompted. Durable across three mocks; reconfirmed a further 3-for-3 in kata-024
  (`assign_next_ticket`), kata-025 (`redeem_promo_code`), and kata-026 (`hold_seats`) — now six mocks total.
- **Authorization/ownership check vs. existence check** (was HIGH, 2-for-2 negative through kata-007/kata-010):
  kata-012 gave the first clean from-scratch instance (`_validate_owner`, held through two extension stages);
  kata-024 (`Ticket.resolve`, correct from Stage 1 through two later stages) and kata-026
  (`release_reservation`'s customer-id comparison, correct from the start) each add a further clean instance.
  **Resolved — three consecutive clean mocks (kata-012, kata-024, kata-026)** with no new negative evidence
  since kata-010; retire from active tracking. The specific "check touched mid-refactor for an unrelated
  reason" shape (the variant that actually failed twice) was also drilled clean in kata-014-focused coaching,
  reinforcing this further.
- **Transactional outbox pattern for reliable event publishing**: reapplied correctly and unprompted across
  three different domains (kata-022-focused, kata-024, kata-026) — treat as a solid, generalized strength.
- **Unprompted clarifying questions** (resolved, holding since kata-004): kata-009 scored 5/5 — six mocks
  running at a healthy level.
- **Encapsulation: don't return live internal state** (resolved after kata-003): no recurrence since.
- **Deadlock fix via lock ordering** (kata-001 risk): correct and unprompted since kata-002; kata-009
  reconfirms on a hypothetical multi-product-transfer question (lock by product-id order), unprompted.
- **Public API completeness** (resolved after kata-002): no recurrence since.

## SELF-IDENTIFIED CONCEPT GAPS (self-reported or narrow, no urgent drill needed)
- **MEDIUM — Optimistic vs pessimistic locking**: kata-008 gave the first direct mock evidence (needed one
  nudge to sharpen "throughput" into "contention on the same row"). No new evidence in kata-009 either
  direction.
- **LOW — Edge-case tests slow to write / parametrize correctness**: one full test function per case under time
  pressure in earlier katas; kata-008 also showed a parametrize test whose body ignored its own parameters. No
  new hygiene instance in kata-009 — keep as a light watch per the user's calibration (don't over-index on
  cosmetic test-hygiene findings unless they recur or mask real coverage gaps).
- **LOW — Concurrency test pattern strong on "one hot key," thin on cross-entity independence**: no new
  evidence in kata-007/008/009 either direction (no domain has created the opportunity yet).
- **LOW — PostgreSQL FK-index misconception** (new, kata-009, one data point): claimed a foreign-key column is
  automatically indexed in Postgres (true in MySQL/InnoDB, false in Postgres). Self-corrected after two direct
  pushes. Narrow factual gap, not a design/judgment issue — note if it recurs, no drill needed yet.
- **LOW — Restate a precise interviewer question before answering** (new, kata-011, one data point): when asked
  what the in-memory lock protects during a multi-instance rollout, the first response conflated the in-process
  lock with a hypothetical DB-level lock, requiring the interviewer to restate the scenario; recovery was
  immediate and the follow-up answer was correct. Note if it recurs, no drill needed yet.
- **LOW — Defining a term precisely under a direct push** (new, kata-012, one data point): asked to define
  "idempotent," the first pass circled ("idempotent... it's idempotent") before landing on "same end result
  whether run once or more times." Same shape as the kata-005 isolation-level vocabulary gap that was later
  resolved via drilling — one data point, not yet worth heavy drilling on its own (distinct from the MEDIUM
  scheduler-vocabulary item above, which has an explicit generalization signal from the interviewer).

## RECURRING STRENGTHS (do not over-drill these)
- Simplicity / avoiding overengineering: 11/11 last eleven mocks (kata-002–kata-012) — kata-010 had no dead
  locking infrastructure at all (both service-level and per-subscription locks were genuinely used); kata-011
  continued it, no unused scaffolding in the `Operation`/`OperationDto` split; kata-012 declined two separate
  invitations to over-build (speculative status-overwrite guards before any execution path existed, and a
  service-level lock before concurrency was a stated requirement), dropping the latter unprompted once asked to
  justify it.
- Ability to evolve the design without rewrites: 12/12 mocks running — kata-011's three stages (history →
  transfer → DB port) each layered cleanly onto the existing `Account`/`AccountService` split; kata-012's
  per-job-lock + manager-lock design absorbed two extension stages without restructuring.
- Concurrency-first instinct, once asked: kata-010 used `threading.Barrier` + `ThreadPoolExecutor` for genuine
  (not approximated) races on both the duplicate-create and create/cancel scenarios, plus correct, unprompted
  lock-granularity reasoning (service-level lock for index mutations vs. per-subscription lock for status/DTO
  reads). Kata-011 added unprompted, correct deadlock reasoning for a two-account transfer (consistent lock
  ordering by `account_id`) with no scaffolding. Kata-012 reused the existing barrier-based concurrency test
  pattern correctly and articulated the per-job-lock-vs-single-lock trade-off unprompted.
- Applying feedback from a previous mock unprompted: continues on DB fundamentals and on the
  evasion-under-pressure item, clean across five consecutive mocks now (kata-008–kata-012) — kata-012 traced two
  separate live bugs with a direct, correct first answer each time, no hedging.
- Production/backend judgement: kata-010 scored 5/5 — a partial unique index for the invariant, correct
  idempotency-key retry pattern, an unprompted transactional-outbox answer, and a textbook zero-downtime
  migration sequence all landed correctly on the first pass. Kata-011 matched it — a detailed strangler-fig
  migration plan (dual-source reads, incremental backfill, traffic-based cutover, then removing the now-useless
  in-process lock) for moving the in-memory service to multi-instance + Postgres, more advanced than prior
  katas' rollout answers. Kata-012 produced a correct Postgres schema with composite index `(status, run_at)`
  and correct deadlock-avoidance (consistent row-lock ordering) unprompted, though it did lose points on two
  vocabulary specifics (see the MEDIUM scheduler-terminology item).
- Requirements-scoping instinct: kata-010 scored 4/5 on clarifying questions; kata-011 scored 4/5 too; kata-012
  scored 4/5 as well.
- Composite index column ordering (equality-before-range): clean and unprompted again in kata-012
  (`(status, run_at)`) — holding since kata-007, no recurrence of the kata-005 gap in five mocks running.

## TECHNICAL ENGLISH PRACTICE LOG
- 2026-09-18: vocabulary drill on "contention" (noun), "contend (for)" (verb), "contended"/"uncontended"
  (adjective) — lock/resource-competition vocabulary, with backend examples (lock contention, connection-pool
  contention, CPU contention). Not a mock-evidenced gap; log only, no active-priority tracking needed unless a
  future mock surfaces a related communication issue.

## NEXT MOCK FOCUS (historical — superseded by the Quick Reference at the top; no further mock is planned before
today's 2026-09-24 interview)
1. **Add the regression test as the very next action after any live bug fix**, before moving to the next task —
   confirmed 4-for-4 (kata-008, kata-009, kata-010, kata-012), still the top priority for an active direct drill
   and the most mechanical/drillable item on the board.
2. **Write a "valid-but-unrelated-party" test the moment an ownership/authorization check is written OR
   touched** (including during an unrelated refactor) — confirmed 2-for-2 (kata-007, kata-010); kata-012 was the
   first clean instance writing one from scratch, watch specifically for the "touched during an unrelated
   change" shape next, since that's the variant that has actually failed.
3. **Recall exact terminology for shared-work-queue/scheduler problems** — new from kata-012:
   `heapq`/priority queue for O(log N) due-item access, `SELECT ... FOR UPDATE SKIP LOCKED` (not `NOWAIT`) for
   concurrent pollers. One data point, but flagged by the interviewer as a generalizable vocabulary gap.
4. **Watch str/UUID boundaries** whenever a value crosses from a service-layer parameter into a stored/typed
   field — confirmed 2-for-2 (kata-008, kata-009); no new evidence either way in kata-010, kata-011, or kata-012.
5. **Trace which exact lock guards a piece of state before asserting thread-safety/consistency**, in any design
   with more than one lock or more than one derived structure — kata-009 (lock identity) is a still-light mock
   data point; kata-010's variant (status-field-vs-index consistency) was drilled in coaching on 2026-09-18
   (see PRACTICED IN COACHING) and needs unprompted mock verification next.
6. **Implement verbally-agreed requirements as they're agreed**, not just discussed — still only one data
   point (kata-008); no new evidence either way in kata-009 through kata-012.
7. **Skim the test file for duplicate function names before declaring a stage complete** — confirmed 2-for-2
   (kata-008, kata-011); low severity per the user's calibration, but cheap and mechanical enough to make a
   standing habit. Default to a `test_*.py` filename too. No new evidence either way in kata-012.
8. Quiet, low-pressure watch only: general self-catch instinct — end-of-stage checklist habit — this is the
   chronic structural weakness underneath several of the above, not a new drill in itself.
9. **New watch, coaching evidence only (kata-018-focused)**: whether a claim/dequeue-shaped operation ported to
   SQL gets an explicit interim state (e.g. `RUNNING`) — without it, a claimed row stays immediately re-pollable
   and the "no double processing" requirement fails deterministically, not just under a race. No mock data point
   yet.
10. **"Run your own code before declaring a stage done" is now the single most consistent coaching-evidence
    theme (7 focused-kata sessions running: 013–018, 022, plus kata-020-bloomfilter's `iter[int]` import crash on
    2026-09-21 — now confirmed outside the SQL/concurrency track too)** — still zero mock data points either
    way. Worth listening for during a full mock whether self-testing happens unprompted before declaring
    correctness.
