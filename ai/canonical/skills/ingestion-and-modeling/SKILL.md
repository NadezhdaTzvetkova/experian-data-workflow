# Ingestion and Modeling

## Purpose
Design and review source trust boundaries, ingestion, raw preservation, output grain, keys, joins, modeling, and deterministic transformations for the Experian exercise.

## Workflow
1. Identify each source type and trust boundary.
2. Define source identity and raw/source preservation.
3. Define target grain explicitly.
4. Define business keys, reference keys, types, units, and nullability.
5. Separate original source values from derived fields.
6. Keep transformations deterministic and reproducible.
7. Avoid duplicating the same business rule in Python and SQL merely to demonstrate both technologies.
8. Validate reference-key uniqueness before enrichment.
9. Verify join cardinality after enrichment.
10. Define the curated output as genuinely analytics-ready, with clear semantics and provenance.
11. Document material field definitions, derivations, and limitations.
12. When using deterministic synthetic data, preserve a separate ground-truth defect manifest for test verification only. The production pipeline must not use that manifest to decide which records are invalid.

## Proportional Default
Prefer:
- deterministic transactions CSV;
- optional SQLite vendor/reference source through SQLAlchemy when it adds real value;
- YAML or JSON policy/configuration;
- curated Parquet;
- a small analytical mart.

A full dimensional warehouse or star schema is normally unnecessary for this scope.

## Failure Cases to Review
- missing required source;
- unreadable or empty source;
- malformed schema;
- duplicate source key;
- replayed source;
- missing reference key;
- unexpected join multiplication;
- changed reference or configuration input;
- silent row loss;
- non-deterministic transformation behavior.

## Independent Synthetic-Data Oracle
If known defects are injected by the synthetic generator:
- record the expected defect types/counts separately from production validation logic;
- use that manifest only in tests or review evidence;
- never let production validation read the oracle;
- compare expected versus detected defects as independent correctness evidence.

## Guardrail
Multiple sources are not inherently better. Keep additional source types only when they improve explicit requirement coverage without adding disproportionate fragility.
