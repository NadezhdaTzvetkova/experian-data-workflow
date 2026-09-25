# Ingestion and Modeling

## Purpose
Review source boundaries, data types, modelling choices and deterministic processing.

## Invoke when
- introducing or changing a source;
- changing schema or data types;
- adding transformations or enrichment.

## Review questions
- Are source roles clear?
- Are identifiers, dates and monetary values represented safely?
- Are transformations deterministic?
- Is the trusted analytical model understandable?

## Evidence expected
- explicit source inventory;
- stable schema expectations;
- deterministic configuration;
- modelling rationale.

## Failure signal
The same business input can produce ambiguous or materially different interpretation without an explicit reason.
