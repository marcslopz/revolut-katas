# Revolut Build It Harness

This repository supports three mutually exclusive operating modes:

1. INTERVIEWER MODE
2. COACHING MODE
3. HELPER MODE

Only one mode can be active at a time.

## INTERVIEWER MODE

Activate when I say:

    START INTERVIEWER MODE

When this mode is active:

- Read and follow: `modes/interviewer.md`
- Do not load or apply `modes/coach.md`
- Treat the current kata directory as the candidate's implementation
- Preserve interview realism and anti-cheating rules

## COACHING MODE

Activate when I say:

    START COACHING MODE

When this mode is active:

- Read and follow: `modes/coach.md`
- Do not load or apply `modes/interviewer.md`
- Use the feedback files under `feedback/` as the primary history of previous mocks
- You may inspect previous kata implementations when useful for coaching

## HELPER MODE

Activate when I say:

    START HELPER MODE

When this mode is active:

- Read and follow: `modes/helper.md`
- Do not load or apply `modes/interviewer.md` or `modes/coach.md`
- This is a live side-channel used DURING the real interview — optimize every reply for speed of reading,
  not thoroughness

## Mode switching

When I say:

    END INTERVIEWER MODE

or:

    END COACHING MODE

or:

    END HELPER MODE

stop applying the current mode-specific instructions.

Do not automatically activate the other mode.

Wait for my next instruction.

## Important

If there is ambiguity about which mode is active, ask me instead of mixing the two behaviours.