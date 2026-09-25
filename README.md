# Revolut Katas

Practice harness for Revolut's interview process (Backend Engineer, Python). Driven by Claude Code
and the instructions defined in `CLAUDE.md` and `modes/`.

Two tracks, one for each remaining/completed technical stage. Only one (track, mode) pair can be
active at a time.

## Tracks

### 🧩 Build It (live-coding backend round)

**Start interviewer:** `START BUILD IT INTERVIEWER MODE` · **End:** `END BUILD IT INTERVIEWER MODE`
**Start coaching:** `START BUILD IT COACHING MODE` · **End:** `END BUILD IT COACHING MODE`
**Start helper:** `START BUILD IT HELPER MODE` · **End:** `END BUILD IT HELPER MODE`

- **Interviewer mode** simulates the real interview: Claude acts as the interviewer, invents a new
  realistic backend exercise each time (never a LeetCode-style puzzle), evolves it over 3–4 stages
  (core functionality → business invariants → concurrency → production/DB), and applies strict
  anti-cheating rules (no hints, no fixing code, no revealing upcoming requirements). Ending with
  `END MOCK - START REVIEW MODE` produces a full review with 1–5 scores and detailed feedback,
  saved to `feedback/kata-NNN.md`. Full instructions: `modes/build-it/interviewer.md`.
- **Coaching mode**: Claude acts as a coach — aggregates historical feedback from
  `feedback/kata-*.md`, distinguishes recurring weaknesses from one-off mistakes, proposes concrete
  drills, and keeps a living summary in `coaching/current-priorities.md`. Includes **FOCUSED KATA
  MODE** (`START FOCUSED KATA`) for drilling a single mechanic without a full mock. Full
  instructions: `modes/build-it/coach.md`.
- **Helper mode**: a live side-channel for use **during the actual interview**. Replies are always
  short and to the point; code requests default to skeletons unless a full implementation is
  explicitly requested. Any file change requires confirmation first. Full instructions:
  `modes/build-it/helper.md`.

### 🏗️ System Design (final technical round)

**Start interviewer:** `START SYSTEM DESIGN INTERVIEWER MODE` · **End:** `END SYSTEM DESIGN INTERVIEWER MODE`
**Start coaching:** `START SYSTEM DESIGN COACHING MODE` · **End:** `END SYSTEM DESIGN COACHING MODE`
**Start helper:** `START SYSTEM DESIGN HELPER MODE` · **End:** `END SYSTEM DESIGN HELPER MODE`

- **Interviewer mode** simulates Revolut's ~55-minute, 6-phase system design interview (intro →
  requirements → high-level architecture → deep dive on DB/scalability/security/failure handling →
  scaling considerations → wrap-up), per Revolut's own "System Design Preparation Guide". Claude
  poses a new realistic design problem each time, gathers requirements like a real stakeholder, and
  pushes back on trade-offs — this round is explicitly more collaborative than Build It's, per
  Revolut's own guidance. The evolving design is tracked in `sd-sessions/sd-<N>.md` in lieu of a
  real whiteboard. Ending with `END MOCK - START REVIEW MODE` produces a full review saved to
  `feedback/sd-N.md`. Full instructions: `modes/system-design/interviewer.md`.
- **Coaching mode**: aggregates feedback from `feedback/sd-*.md`, tracks recurring weaknesses in
  `coaching/current-priorities-system-design.md`, and can teach concepts (CAP theorem, caching,
  sharding, DDD, failure handling, etc.), grounded in the resources from Revolut's own prep guide.
  Includes **FOCUSED SD DRILL** (`START FOCUSED SD DRILL`) for drilling one mechanic without a full
  mock. Full instructions: `modes/system-design/coach.md`.
- **Helper mode**: a fast-reference tool for **prep sessions only**. ⚠️ Revolut's recruiter email
  explicitly bans any AI tool that generates/suggests/displays answers in real time during the
  System Design interview — unlike Build It's helper mode, this one must **never** be opened during
  the actual live interview. Full instructions: `modes/system-design/helper.md`.

## Repo structure

- `kata-NNN/` — Build It implementation for each mock (or `kata-NNN-focused` for focused coaching
  sessions).
- `sd-sessions/` — System Design design docs for each mock (`sd-N.md`) or focused drill
  (`sd-N-focused.md`) — the written analog of a whiteboard session.
- `feedback/` — full review for each mock: `kata-NNN.md` (Build It) or `sd-N.md` (System Design).
  Source of truth for each track's coaching mode.
- `coaching/` — consolidated summary of practice priorities: `current-priorities.md` (Build It) and
  `current-priorities-system-design.md` (System Design).
- `modes/build-it/` and `modes/system-design/` — detailed instructions for each mode, per track.
- `docker-compose.yml` — local PostgreSQL (`kata`/`kata`/`kata` on `localhost:5432`) for Build It
  sessions that include the SQL track.
