# Design Decisions

This document records the main implementation decisions, why they were made, their trade-offs and how they could evolve in a production environment.

## 1. Synthetic corporate-expense data

**Decision**
Use deterministic synthetic expense data rather than public business data.

**Why**
The exercise requires a workflow that can demonstrate ingestion, validation, audit exceptions, reconciliation and presentation without introducing confidential, proprietary or personal information. Synthetic data also allows known defects and audit examples to be injected deliberately.

**Trade-off**
Observed exception prevalence is not representative of a real organisation.

**Production alternative**
Use governed enterprise source systems with the same validation and reconciliation contracts.

## 2. CSV + SQLite + YAML as source types

**Decision**
Use CSV for expense facts, SQLite for vendor reference data and YAML for governed policy configuration.

**Why**
The three sources represent distinct real-world responsibilities: transaction facts, reference/master data and business configuration.

**Trade-off**
The sources are local and small-scale.

**Production alternative**
Replace storage and connectivity while preserving the same source contracts and semantic roles.

## 3. Integer minor units for money

**Decision**
Store monetary values as integer minor units.

**Why**
This avoids floating-point ambiguity in thresholds, reconciliation and aggregation.

**Trade-off**
Human-readable currency amounts require formatting at presentation boundaries.

**Production alternative**
Use integer minor units or an appropriate fixed-precision decimal type depending on platform and currency requirements.

## 4. Structural failure vs quarantine vs audit exception

**Decision**
Separate failures into structural pipeline failure, invalid-record quarantine and valid audit/business exception.

**Why**
Invalid data should not enter the trusted dataset, while valid transactions that breach policy or involve risky vendors are precisely the records an auditor needs to analyse.

**Trade-off**
Each control needs an explicit failure classification.

## 5. Historical vendor interpretation

**Decision**
Evaluate vendor activity relative to transaction date and effective dates, not only current `active_flag`.

**Why**
Audit analysis requires historical truth.

**Production alternative**
Use effective-dated reference data or SCD2-style temporal joins where required.

## 6. Parquet as the curated analytical layer

**Decision**
Persist trusted curated output as Parquet.

**Why**
Parquet is typed, compact and directly consumable by DuckDB and Pandas.

**Trade-off**
It is not intended for manual inspection in a text editor.

## 7. DuckDB analytics with independent Pandas reconciliation

**Decision**
Produce analytical summaries in DuckDB and independently recompute headline KPIs in Pandas.

**Why**
A single implementation can be internally consistent while still being wrong. Independent calculation provides additional evidence of correctness.

**Trade-off**
Some analytical logic is intentionally duplicated for verification.

## 8. Run manifest and hash-based provenance

**Decision**
Record source identities, hashes, counts, policy version, analytical SQL identity, Git state, control results and output paths in a run manifest.

**Why**
Another engineer or auditor should be able to identify what inputs, configuration and code state produced a result.

## 9. Manifest written last

**Decision**
Generate all run outputs before writing `manifest.json`.

**Why**
The manifest acts as the publication marker for a complete run.

**Trade-off**
Intermediate files can exist before publication.

**Production alternative**
Use staging and atomic promotion or equivalent commit semantics.

## 10. Minimal infrastructure

**Decision**
Keep the implementation local and dependency-light rather than adding cloud services or distributed processing.

**Why**
The exercise prioritises engineering judgement, analysis and presentation within a short preparation window, and the current data volume does not justify distributed infrastructure.

**Production alternative**
Map the same logical contracts to managed storage, orchestration, compute, monitoring and access-control services when requirements justify them.

## 11. Curated public AI methodology

**Decision**
Publish both the reviewer-facing AI methodology and the task-specific canonical AI framework, while excluding raw conversations and unrelated personal context.

**Why**
The exercise asks how AI was used, evaluated and challenged, but explicitly does not require prompt transcripts.

**Trade-off**
The private working framework is richer than the public documentation.
