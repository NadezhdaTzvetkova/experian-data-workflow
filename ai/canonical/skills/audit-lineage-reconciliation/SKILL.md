# Audit Lineage and Reconciliation

## Purpose
Build and review provenance, hashes, run manifests, reconciliation, idempotency, historical reproducibility, and audit evidence.

## Workflow
1. Separate execution identity from business identity.
2. Inventory every result-affecting source, configuration, and reference input.
3. Hash file/configuration inputs where meaningful.
4. Preserve source and business identifiers into trusted outputs.
5. Record input, accepted, and quarantined counts.
6. Enforce source_count = accepted_count + quarantined_count.
7. Reconcile financial totals only where values are safely parseable and semantically comparable.
8. Preserve control-result summaries and failure evidence.
9. Store run-specific outputs and evidence.
10. Record code/Git identity when available.
11. Verify equivalent inputs, configuration, reference state, and code produce equivalent business results.
12. Preserve policy/reference version identity or effective-date semantics where historical accuracy matters.
13. Do not mark a run successful when reconciliation fails.

## Manifest Minimum
- run_id;
- final run status;
- started_at_utc;
- completed_at_utc;
- source inventory;
- source/config/reference hashes or version IDs;
- source row count;
- accepted row count;
- quarantined row count;
- control summary;
- reconciliation result;
- code/Git identity where available;
- output locations.

## Reconciliation Rules
Mandatory row conservation:
source_count = accepted_count + quarantined_count

Additional enrichment invariant:
accepted_count = curated_count after one-to-one reference enrichment unless a documented relationship intentionally changes cardinality.

Financial conservation is required only for values that can be parsed and compared meaningfully. Never manufacture a numeric reconciliation for malformed source values.

## Historical Accuracy
Run-specific folders alone are not sufficient if reference or policy data can change. Preserve the applied policy version, reference snapshot identity, or effective dates so historical results cannot be silently reinterpreted.

## Publication Semantics
Use the conceptual pattern:
WRITE -> AUDIT -> PUBLISH

Only results that pass required validation and reconciliation may be marked trusted or successful.

## Guardrail
A checksum proves identity, not semantic correctness. Hashes must be combined with contracts, validation, reconciliation, and tests.
