# Experian Data Workflow Technical Exercise

A small, reproducible data workflow demonstrating data ingestion, validation, trusted transformation, audit-oriented analytics, traceability, reconciliation, testing, and presentation.

The example domain is deterministic synthetic corporate-expense data. No real, confidential, proprietary, or personal data is used.

## Core question

> Can I prove that what came out is the correct, complete and consistent transformation of what went in, identify exactly where it stopped being true if it is not, and preserve enough evidence for another engineer or auditor to reproduce and verify the result?

## Workflow

```text
expenses.csv --------\
                     \
vendors.db -----------> ingest -> structural validation -> record validation
                     /                                      |
expense_policy.yaml -/                                       |
                                                            +--> invalid rows -> quarantine
                                                            |
                                                            +--> trusted rows -> enrichment
                                                                                   |
                                                                                   +--> curated Parquet
                                                                                   |
                                                                                   +--> DuckDB audit summary
                                                                                              |
                                                                                              +--> independent Pandas KPI reconciliation
                                                                                              |
                                                                                              +--> audit-facing HTML report
```

Each successful run also writes a manifest containing source identity, hashes, row counts, code identity, control results, reconciliation evidence, analytical definition identity, and output paths.

## Design decisions

### Failure semantics

The workflow deliberately distinguishes different kinds of problems:

- **Structural failure:** the pipeline stops because the source contract is not safe to process.
- **Invalid record:** the row is quarantined with a control identifier and reason.
- **Valid audit exception:** the row remains in the trusted dataset and is flagged for analysis.
- **Reconciliation failure:** the pipeline fails rather than publishing results that cannot be accounted for.

This prevents valid business-risk signals from being confused with unusable data.

### Data quality controls

The current controls focus on material risks rather than maximising the number of checks:

- required source columns and policy structure
- missing transaction identifier
- duplicate transaction identifier
- non-positive or invalid amount
- invalid or future transaction date
- unresolved vendor reference
- many-to-one vendor enrichment cardinality
- source-to-quarantine-to-trusted row reconciliation
- trusted-to-curated enrichment cardinality

### Money and time

Monetary values are stored as integer minor units to avoid floating-point ambiguity.

The policy uses an explicit deterministic `as_of_date`. Transaction dates are treated separately from execution timestamps so business meaning remains reproducible even though run timestamps change.

### Historical reference logic

Vendor activity is evaluated against the transaction date. A vendor that later became inactive is not automatically treated as inactive for earlier transactions. This preserves historical interpretation rather than applying only the current reference state.

## Analytics

The curated dataset is the only analytical source. `sql/audit_summary.sql` produces category-level audit metrics in DuckDB. The same headline metrics are independently recomputed in Pandas. The run fails if the two implementations disagree.

The analytical output includes:

- transaction and spend totals by category
- policy-limit exception counts
- high-risk vendor counts
- historically inactive vendor counts
- overall audit-exception counts

The report also surfaces vendor concentration and cost-centre exception exposure for audit prioritisation.

## Traceability and reproducibility

Every manifested run records:

- source paths and SHA-256 hashes
- source and trusted row counts
- policy version and policy hash
- Git commit and working-tree dirty state
- structural and record-control results
- row reconciliation results
- analytical SQL path and SHA-256 hash
- independent SQL/Pandas KPI reconciliation
- persisted output paths

A run is considered complete only when its `manifest.json` exists. Files produced before the manifest are intermediate execution artifacts.

## Synthetic defects and audit examples

The generator creates deterministic synthetic data and injects known examples for testing and review. The independent ground-truth file is used only by tests and review; production validation logic does not read it.

Injected invalid-record examples cover:

- duplicate transaction ID
- missing transaction ID
- invalid amount
- future transaction date
- unknown vendor

Separate valid audit examples cover policy-limit breaches, high-risk vendors, and historically inactive vendors. Valid audit examples remain in the curated dataset rather than being quarantined.

## Running the workflow

Requirements: Python 3.12 and `uv`.

```powershell
cd experian-data-workflow
uv sync
uv run python scripts/generate_synthetic_data.py
uv run python -m experian_workflow.pipeline
```

The pipeline writes each execution under:

```text
output/runs/<run_id>/
```

Typical outputs:

```text
manifest.json
quarantine.csv
curated_expenses.parquet
audit_summary.csv
audit_report.html
```

The pipeline also generates a self-contained audit-facing `audit_report.html` as part of the same manifested run. No separate report-generation step is required.

## Testing and code quality

```powershell
cd experian-data-workflow
uv run ruff check .
uv run pytest -q
```

The test suite covers structural contract failure, record quarantine semantics, valid audit exceptions, unsafe reference cardinality, persisted run evidence, analytical reconciliation including deliberate mismatch detection, and report generation.

## Important interpretation notes

Audit flags are not mutually exclusive. A transaction may simultaneously breach policy and involve a high-risk or historically inactive vendor. Therefore the overall audit-exception count represents transactions with at least one flag and should not be calculated by summing individual flag counts.

Categories without a configured policy limit are not treated as policy breaches solely because of transaction value.

The dataset is intentionally synthetic and seeded with examples. Observed exception prevalence and concentration are therefore demonstrations of workflow behaviour, not evidence about Experian or any real organisation.

## Scaling and operationalisation

For a production-scale implementation I would preserve the same contracts while replacing local components according to volume and operational needs, for example object storage for immutable source evidence, scheduled orchestration, managed compute, catalogued curated datasets, central monitoring, alerting, retained manifests and control history, and role-based access. The exercise intentionally avoids building that infrastructure because it would add complexity without improving the evidence required for this task.

## AI-assisted development

AI was used as a development assistant during the exercise. Design choices, implementation, validation, tests, reconciliation logic, analytical interpretation, and final responsibility for correctness remain human-owned. The solution includes independent checks specifically so generated or suggested implementation details are not accepted solely on trust.
