# Audit Lineage and Reconciliation

## Purpose
Prove that source data and resulting outputs can be traced and accounted for.

## Invoke when
- adding transformations;
- enriching with reference data;
- publishing outputs;
- changing run evidence.

## Review questions
- Can every source row be accounted for?
- Was expected cardinality preserved?
- Can sources, configuration and analytical definitions be identified?
- Can another engineer reproduce the run?

## Evidence expected
- row-count reconciliation;
- source/configuration hashes;
- code identity;
- manifest;
- output paths.

## Failure signal
A result looks plausible but its source-to-output path cannot be demonstrated.
