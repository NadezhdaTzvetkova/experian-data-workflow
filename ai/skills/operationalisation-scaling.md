# Operationalisation and Scaling

## Purpose
Identify how the same logical contracts would extend to larger or scheduled workloads.

## Invoke when
- discussing productionisation;
- considering volume, frequency or availability changes;
- evaluating infrastructure choices.

## Review questions
- Which contracts should remain unchanged?
- Where would orchestration become useful?
- What requires monitoring or alerting?
- Which local component becomes the first scaling constraint?

## Evidence expected
- explicit scaling seams;
- idempotency strategy;
- monitoring concepts;
- proportionate production alternatives.

## Failure signal
Infrastructure is added without solving a demonstrated scale, reliability or operational requirement.
