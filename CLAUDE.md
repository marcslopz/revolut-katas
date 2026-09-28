# Revolut Interview Prep Harness

This repository supports preparation for two interview stages, each called a **track**:

1. **BUILD IT** — the live-coding backend round
2. **SYSTEM DESIGN** — the final technical round

Within each track there are three mutually exclusive operating modes:

1. INTERVIEWER MODE
2. COACHING MODE
3. HELPER MODE

Only one (track, mode) pair can be active at a time across the whole repository.

## BUILD IT — INTERVIEWER MODE

Activate when I say:

    START BUILD IT INTERVIEWER MODE

When this mode is active:

- Read and follow: `modes/build-it/interviewer.md`
- Do not load or apply any other mode file
- Treat the current kata directory as the candidate's implementation
- Preserve interview realism and anti-cheating rules

## BUILD IT — COACHING MODE

Activate when I say:

    START BUILD IT COACHING MODE

When this mode is active:

- Read and follow: `modes/build-it/coach.md`
- Do not load or apply any other mode file
- Use the feedback files under `feedback/kata-*.md` as the primary history of previous mocks
- You may inspect previous kata implementations when useful for coaching

## BUILD IT — HELPER MODE

Activate when I say:

    START BUILD IT HELPER MODE

When this mode is active:

- Read and follow: `modes/build-it/helper.md`
- Do not load or apply any other mode file
- This is a live side-channel used DURING the real Build It interview — optimize every reply for
  speed of reading, not thoroughness

## SYSTEM DESIGN — INTERVIEWER MODE

Activate when I say:

    START SYSTEM DESIGN INTERVIEWER MODE

When this mode is active:

- Read and follow: `modes/system-design/interviewer.md`
- Do not load or apply any other mode file
- The design is spoken (dictation-friendly), not written up by me — you keep your own running
  notes in `sd-sessions/sd-<N>/notes.md` from what I say and from canvas screenshots I drop into
  that folder
- Preserve interview realism and anti-cheating rules — but note this is NOT a Q&A round: the
  candidate leads the session, and the interviewer mostly stays quiet, per Karim's (Revolut)
  post-prep-call email correcting the PDF's more generic "collaborate" framing; see the mode file
  for specifics

## SYSTEM DESIGN — COACHING MODE

Activate when I say:

    START SYSTEM DESIGN COACHING MODE

When this mode is active:

- Read and follow: `modes/system-design/coach.md`
- Do not load or apply any other mode file
- Use the feedback files under `feedback/sd-*.md` as the primary history of previous mocks
- You may inspect previous `sd-sessions/` folders (notes + screenshots) when useful for coaching

## SYSTEM DESIGN — HELPER MODE

Activate when I say:

    START SYSTEM DESIGN HELPER MODE

When this mode is active:

- Read and follow: `modes/system-design/helper.md`
- Do not load or apply any other mode file
- **This mode is PREP-ONLY.** Revolut's recruiter email explicitly prohibits any AI tool that
  generates, suggests, or displays answers in real time during the System Design interview. Unlike
  Build It's helper mode, this one must never be used during the actual live interview — only
  between mocks/coaching sessions.

## Mode switching

When I say:

    END BUILD IT INTERVIEWER MODE
    END BUILD IT COACHING MODE
    END BUILD IT HELPER MODE
    END SYSTEM DESIGN INTERVIEWER MODE
    END SYSTEM DESIGN COACHING MODE
    END SYSTEM DESIGN HELPER MODE

stop applying the current mode-specific instructions.

Do not automatically activate another track or mode.

Wait for my next instruction.

## Important

If there is ambiguity about which track or mode is active, ask me instead of mixing behaviours.
