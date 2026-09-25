# AI-Assisted Engineering

This exercise was developed with AI assistance, but AI was not treated as an authority for correctness. The workflow used a small set of specialist review roles to challenge requirements, implementation choices, data-quality controls, reconciliation, analytics, engineering quality and operationalisation.

The purpose of the agentic layer was not to generate more code. Its purpose was to create structured challenge around the places where a data workflow can appear correct while still being wrong.

## Operating principle

> AI proposes and challenges; independent evidence validates; the human accepts or rejects.

The final implementation remained human-owned. AI suggestions were evaluated against the exercise requirements, deterministic tests, reconciliation evidence, source and transformation traceability, independent analytical calculations and code review.

## Public agentic model

The repository contains two complementary AI layers: a concise reviewer-facing methodology and the task-specific canonical framework actually used during development. Raw conversation transcripts and unrelated personal context are not included.

The review roles are:

- **Source-of-Truth Validator** — protects requirement fidelity and prevents implementation choices from silently redefining the task.
- **Ingestion & Modeling Reviewer** — challenges source selection, data types, transformation boundaries, determinism and modelling choices.
- **Data Contract & Quality Reviewer** — reviews structural contracts, record validation, quarantine semantics and fitness-for-use rules.
- **Audit Lineage & Reconciliation Reviewer** — verifies provenance, row accounting, enrichment cardinality, hashes and reproducibility evidence.
- **Analytics & Presentation Reviewer** — checks whether analytical outputs are decision-useful, correctly interpreted and professionally communicated.
- **Engineering Quality Reviewer** — challenges maintainability, testing, failure handling, packaging and reproducibility.
- **Operationalisation & Scaling Reviewer** — evaluates how the same contracts would extend to scheduled, larger-scale or production workloads without forcing unnecessary infrastructure into the exercise.
- **AI Oversight Reviewer** — checks whether AI-generated suggestions are being accepted without independent evidence.
- **Red-Team Reviewer** — actively searches for brittle assumptions, false confidence, hidden coupling, misleading tests and cases where the workflow can appear correct while being wrong.

## What the agentic layer did

The AI-assisted process was used to:

1. restate and protect the exercise requirements before implementation;
2. challenge architecture and scope choices;
3. review data contracts and validation semantics;
4. distinguish invalid data from valid audit exceptions;
5. challenge reconciliation and lineage evidence;
6. independently review analytical logic and presentation;
7. red-team tests and reproducibility assumptions;
8. identify where the solution should remain deliberately simple; and
9. prepare for changed requirements and production-scaling discussion.

## Human acceptance gates

AI-generated changes were not accepted solely because they looked plausible. Acceptance relied on evidence including:

- deterministic synthetic data generation;
- independent ground-truth examples used only by tests and review;
- structural contract tests;
- record-level quarantine tests;
- source-to-trusted-to-quarantine reconciliation;
- many-to-one reference cardinality protection;
- trusted-to-curated cardinality reconciliation;
- SHA-256 provenance for sources, configuration and analytical SQL;
- independent DuckDB and Pandas KPI reconciliation;
- Ruff static analysis;
- pytest;
- Git diff review;
- repository encoding and line-ending checks; and
- human review of assumptions, limitations and trade-offs.

## What is included

The repository includes the task-specific canonical AI system under `ai/canonical/`, including the master role, orchestration, source-of-truth specification, acceptance matrix and specialist skills. The exercise explicitly does not require prompt transcripts, so raw conversations are not included.

This keeps the submission focused on the question that matters: **how AI-assisted work was made trustworthy and explainable.**

## Further documentation

- [Orchestration model](ORCHESTRATION.md)
- [Role catalog](ROLE_CATALOG.md)
- [Human oversight and challenged suggestions](HUMAN_OVERSIGHT.md)
- [Public skill cards](skills/)
