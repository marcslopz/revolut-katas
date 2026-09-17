# Kata 009 — Mock Review

**Domain:** Inventory Reservation Service (register products with stock, reserve/release stock, concurrent reservations against limited stock, PostgreSQL schema/locking/isolation discussion)
**Stages completed:** 4 coding stages (core register/reserve → releasable reservations → concurrency → PostgreSQL schema/locking design) + full technical discussion

## Scores (1–5)

| # | Category | Score |
|---|----------|-------|
| 1 | Requirements clarification | 5 |
| 2 | Communication / thinking aloud | 4 |
| 3 | Python fluency | 4 |
| 4 | Speed | 4 |
| 5 | Correctness | 3 |
| 6 | Simplicity | 4 |
| 7 | Code quality | 4 |
| 8 | Naming/readability | 4 |
| 9 | Test quality | 3 |
| 10 | Ability to evolve the design | 4 |
| 11 | Concurrency reasoning | 4 |
| 12 | Performance awareness | 4 |
| 13 | Production/backend judgement | 4 |
| 14 | Time management | 4 |

## A. Assessment: PASS

## B. Three strongest things
- **Requirements-scoping instinct.** Sharp, well-targeted clarifying questions at every stage (zero-stock validity, whether to track `caller_id`, whether idempotency was in scope) and consistently declined to build ahead of what was asked.
- **Sound, fully-wired concurrency design.** The per-product lock introduced in Stage 1 was actually used consistently through `reserve_quantity` and `release_reservation` after the Stage 2 refactor — no dead/unused locking infrastructure, a clean improvement over a past kata's premature-lock pattern.
- **Strong system-design breadth in the technical conversation** — correct idempotency-key write ordering, a committed DDD bounded-context stance once pushed to commit, event dedup via publisher-supplied keys, a well-reasoned fail-fast/circuit-breaker trade-off, and a textbook expand→backfill→contract migration.

## C. Three biggest risks for the real interview
- **Confidently asserted an incorrect synchronization claim before tracing lock identity.** `get_product_current_stock` read `stock` under the service-level dict lock, but all writes to `stock` happened under a separate per-product lock — genuinely unsynchronized. The first answer to "is this thread-safe end-to-end?" was an unqualified "yes... protected by global lock," which was false. Only corrected after a second, more pointed question naming the two lock objects directly. The bug survived silently through two stages of the candidate's own code.
- **Recurring str/UUID type mismatch (2nd occurrence).** `Reservation.product_id` is typed `uuid.UUID` but assigned the raw string parameter in `ProductService.reserve_product`, never converted — currently inert since nothing reads the field, but the same defect family as a same-account type-mismatch bug from kata-008. Two occurrences now suggests a systematic blind spot at str/UUID boundaries, not a one-off slip.
- **Live bug fixed with zero regression test, again.** After fixing the `get_stock()` race mid-interview, no test was added to lock in the fix — the exact pattern flagged as a risk in kata-008's review, now confirmed a second time.

## D. Bugs or correctness problems
- *(Found & fixed live)* `get_product_current_stock` originally read `product.stock` while holding only the service-level lock, not the per-product lock that guards writes to it — an unsynchronized read across two different lock scopes. Fixed by adding `Product.get_stock()`, which acquires `product.lock`.
- `Reservation.product_id` is typed `uuid.UUID` but is assigned the raw string `product_id` parameter in `ProductService.reserve_product` — never causes a visible failure currently since the field isn't read anywhere, but it's a latent inconsistency.

## E. Unnecessary abstractions / overengineering
- None significant — a clear improvement over past katas' premature/unused locking infrastructure. The one instance of over-design (proposing a composite `(reservation_id, product_id)` index that duplicated the PK) was minor and self-corrected within two prompts.

## F. Missing or low-value tests
- No regression test for the `get_stock()` synchronization bug found and fixed mid-interview.
- No test asserting the actual stored fields of a `Reservation` object (would likely have caught the str/UUID mismatch for free, e.g. via a type assertion).
- No dedicated happy-path test with a non-zero expected value for `get_product_current_stock` (covered only incidentally via other tests' assertions).

## G. Better concurrency/design approaches
- The final design (consistent per-product locking on every read and write of product-level state) is correct and appropriate for this scale — nothing more sophisticated is needed. The deadlock-ordering answer for a hypothetical multi-product transfer (lock by product-id order) was correct and unprompted.

## H. Performance issues
- Correctly self-identified the per-product lock as a serialization bottleneck for a single hot product under flash-sale load. No action needed within the kata's scope; correctly reasoned through as an accepted trade-off in the fail-fast/circuit-breaker discussion.

## I. What a strong candidate might have done differently
- Traced the actual lock object identity before answering "is this thread-safe?" confidently, rather than asserting first and correcting only under a second, more pointed challenge.
- Added a regression test immediately after fixing the `get_stock()` race, before moving on.
- Added a quick type/field assertion on `Reservation` right after the Stage 2 refactor, likely surfacing the str/UUID drift unprompted.

## J. Practice priorities before next kata
- **Verify "which lock guards this state" before asserting thread-safety**, whenever a design uses more than one lock — the direct fix for the risk-#1 pattern this session.
- **Add the regression test as the very next action after any live bug fix during a mock** — now a confirmed 2-for-2 pattern (kata-008, kata-009) and the strongest current candidate for a focused coaching drill.
- **Watch str/UUID boundaries specifically when a value crosses from a service-layer parameter into a stored/typed field** — now also 2-for-2 (kata-008, kata-009).
- The "evasion under pressure" item (recurring through kata-006/007, likely-resolved after kata-008) is now **fully resolved** — a second consecutive mock where, even though the *first* answer was factually wrong this time, it was a genuine (not evasive) mistake, and the correction on direct challenge was immediate and non-hedging. Retire from active tracking.

## K. A better implementation approach (post-mock)
- Convert `product_id` to a `uuid.UUID` before constructing `Reservation`, so the type hint is honored.
- Make `Product.get_stock()` the only path product stock is ever read through at the service layer, so it's structurally impossible for a future change to bypass the per-product lock the way the original code did.
- Add a regression test for the `get_stock()` fix and a field-level assertion test for `Reservation` to catch the str/UUID drift.
