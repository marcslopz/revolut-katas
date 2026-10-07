# sd-17-focused — Company card spending limits (lite mock 1/9, fintech)

Interviewer's running transcription — not candidate-authored. Format: **LITE SD MOCK** (`modes/system-design/coach.md`):
F → N → flow/blocks → states → one hard edge case; no boilerplate; live challenges pointing at the problem, answer
only if stuck. Targets: "unique within what?", counter walk on every transition, invariant table first, size to the
given number.

## Problem statement
Design spending limits for company cards: each employee's card has a monthly limit, and every card payment must be
approved or declined against it.

(Interviewer-private: core = **a counter per card per month with holds**. The card processor (external, already
integrated) calls us **synchronously to approve/decline each authorization** (must answer < 200 ms; if we don't answer
in time the processor **declines**). Later, asynchronously (minutes to days), the processor sends events for that
authorization: **capture** (final amount, may differ from the authorized one, e.g. tips; **can come in several partial
captures**), **reversal** (released, nothing charged), **refund** (money back after capture). Events at-least-once, each
with **`event_id` (unique per processor)** and the **`authorization_id`** it refers to. One processor. Limit counts in the
**month of the authorization**; refunds give limit back only if in the same month (else ignore — keep simple). Admins
set/change limits. ~5k companies, ~200k cards; ~1M authorizations/day; peak lunch ~3x; ~10% authorizations never captured
(expire after 7 days → hold released automatically by us).
Targets: invariant `spent + held + amount <= limit` via conditional update on the card-month row; counters on every
transition (auth → hold; capture → hold→spent with amount diff; partial captures; reversal; 7-day expiry; refund);
idempotency on **event_id**, not authorization_id (partial captures share the auth id); timeout = decline and the processor sends **nothing** more for that authorization → if we committed a hold but
answered late, the hold leaks until the 7-day expiry (blocks the employee's limit). Hard edge case if none chosen: capture
arrives after our 7-day expiry released the hold.)

## Phase 1 — Requirements

## Phase 2 — Estimates

## Phase 3 — Flow, blocks, states

## Edge case

## Feedback
