# AI Oversight

## Purpose
Prevent AI-generated work from being accepted without independent verification.

## Invoke when
- AI proposes code, tests, architecture or interpretation;
- a suggestion appears plausible but is not independently proven.

## Review questions
- What assumption is the AI making?
- What independent evidence supports the change?
- Could the implementation pass while still being wrong?
- Has AI silently changed the requirement?

## Evidence expected
- tests;
- direct source inspection;
- reconciliation;
- independent calculation;
- human review.

## Failure signal
The justification for correctness is effectively “the AI said so.”
