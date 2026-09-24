# Revolut Katas

Practice harness for Revolut's *Build It* interview (Backend Engineer, Python). Driven by Claude Code and the
instructions defined in `CLAUDE.md` and `modes/`.

Only one mode can be active at a time.

## Modes

### 🎤 Interviewer mode

**Start:** `START INTERVIEWER MODE`
**End:** `END INTERVIEWER MODE`

Simulates the real interview: Claude acts as the interviewer, invents a new realistic backend exercise each
time (never a LeetCode-style puzzle), evolves it over 3–4 stages (core functionality → business invariants →
concurrency → production/DB), and applies strict anti-cheating rules (no hints, no fixing code, no revealing
upcoming requirements). Ending with `END MOCK - START REVIEW MODE` produces a full review with 1–5 scores and
detailed feedback, saved to `feedback/kata-NNN.md`.

Full instructions: `modes/interviewer.md`.

### 🧑‍🏫 Coaching mode

**Start:** `START COACHING MODE`
**End:** `END COACHING MODE`

Claude acts as a coach: aggregates historical feedback from `feedback/`, distinguishes recurring weaknesses
from one-off mistakes, proposes concrete drills, and keeps a living summary in
`coaching/current-priorities.md`. Unlike interviewer mode, this is where you can ask for explanations, code
examples, quizzes, etc.

Includes a lighter-weight sub-mode, **FOCUSED KATA MODE** (`START FOCUSED KATA`), for drilling a single
mechanic (locking, indexing, transactions...) without the overhead of a full mock, usually with both an
in-memory version and its PostgreSQL equivalent.

Full instructions: `modes/coach.md`.

### 🎧 Helper mode

**Start:** `START HELPER MODE`
**End:** `END HELPER MODE`

Support mode meant for use **during the actual interview** (not a mock). Replies are always short and to the
point (syntax, key ideas, no filler); if something isn't clear, ask `i need more` for a different explanation
or more examples while staying concise. Code requests default to skeletons only (signatures, structure), never
full implementations unless explicitly asked. Any file change requires confirmation first.

Full instructions: `modes/helper.md`.

## Repo structure

- `kata-NNN/` — implementation for each mock (or `kata-NNN-focused` for focused coaching sessions).
- `feedback/` — full review for each mock (source of truth for coaching mode).
- `coaching/` — consolidated summary of practice priorities.
- `modes/` — detailed instructions for each mode.
- `docker-compose.yml` — local PostgreSQL (`kata`/`kata`/`kata` on `localhost:5432`) for sessions that include
  the SQL track.
