# Experian Assurance Analytics and Data Workflow

A reproducible analytics and data workflow for the Experian technical exercise, covering corporate expenses and enterprise assurance. It validates source records, reconciles populations, checks governed calculations independently, and publishes one validated analytical truth to PowerPoint, offline HTML and Tableau. The committed reviewer package lets you inspect the results without running the pipeline.

All datasets, controls, methodology, and policy examples are synthetic and illustrative. They are not Experian internal data, controls, methodology, or policy. The observed results demonstrate workflow behaviour rather than conditions at Experian or any real organisation.

## Start here

Follow **PowerPoint → HTML → Tableau → implementation and tests**. The [reviewer guide](review/README.md) records the artifact producer, exact paths and executed validation levels.

| Review item | Open | Purpose |
| --- | --- | --- |
| PowerPoint | [Eight-slide executive presentation](review/presentation/assurance_executive_report.pptx) | Narrative, reconciliation, priorities and drill links |
| Slide previews | [Eight PNG previews](review/visuals/) | Inspect the deck directly on GitHub |
| HTML dashboard | [Offline dashboard](review/html/assurance_dashboard.html) | Explore results and Data & Metrics definitions |
| HTML detail | [Four reports](review/html/reports/) · [Six charts](review/html/charts/) | Supporting analysis linked from the dashboard |
| Tableau | [Packaged workbook](review/tableau/assurance_dashboard.twbx) | Explore the governed extract in compatible Tableau software |
| Implementation | [Python source](src/experian_workflow/) | Processing, calculation and publication logic |
| Tests | [Tests and independent fixtures](tests/) | Analytical and publication acceptance evidence |
| Configuration and contracts | [Assurance contracts](config/assurance/) · [Expense policy](config/expense_policy.yaml) | Governed rules, metrics and population semantics |

**GitHub displays HTML source; it does not execute the dashboard.** Download and extract the repository, then open `review/html/assurance_dashboard.html` locally. Keep the complete `review/` folder together so HTML and PowerPoint relative links work. Tableau requires compatible software; the PNG previews can be viewed without PowerPoint.

## Architecture

The expense workflow ingests CSV transactions, SQLite vendor reference data, and YAML policy. It validates structure and records, quarantines unusable rows, preserves valid audit exceptions, enriches trusted data, and reconciles DuckDB analytics against independent Pandas calculations.

The assurance workflow ingests enterprise reference data, control evidence, findings, and management actions. Governed configuration defines evidence freshness and sufficiency, residual-risk interpretation, overdue actions, and recurrence. Source populations are reconciled explicitly before analytical marts and publication artifacts are accepted.

Three presentation channels consume the same validated publication truth:

- **PowerPoint:** executive narrative, eight-slide navigation, and links to analytical detail.
- **HTML:** interactive browser analytics with supporting reports and charts.
- **Tableau:** packaged analytical workbook and genuine Hyper extract.

Renderers do not recreate KPI business logic. The PowerPoint reconciliation view distinguishes unmapped source records from unmapped assurance tests, which use different grains.

## Repository structure

| Path | Purpose |
| --- | --- |
| `src/experian_workflow/` | Expense pipeline and shared implementation |
| `src/experian_workflow/assurance/` | Governed assurance processing, validation, and publication |
| `config/` | Expense policy and assurance rules, metrics, reconciliation, and Tableau contracts |
| `data/source/` | Deterministic synthetic source files, including adversarial assurance examples |
| `tests/` | Runtime tests and independent scenario/expected-result fixtures |
| `scripts/` | Deterministic synthetic-source generators |
| `sql/` | Expense audit aggregation SQL |
| `docs/` | Design decisions and changed-requirement scenarios |
| `ai/` | Intentional project review contracts and methodology documentation |
| `sample_output/` | Versioned representative expense output for review without execution |
| `review/` | Curated reviewer snapshot with explicit producer provenance |
| `output/` | Ignored local runtime runs and submission packages |
| `pyproject.toml`, `uv.lock` | Runtime specification and locked dependency resolution |

The versioned expense sample is illustrative historical evidence with its own producer identity. It is separate from the final assurance submission. Generated assurance runs and submission packages remain local and are not version controlled.

The expense sample's original producer identifiers describe that historical sample and are not reproduction checkout targets. Use the current branch to run the expense workflow; use the reviewer guide's producer source commit to reproduce the assurance snapshot.

## Setup and execution

Use Python **3.12** and `uv`. `pyproject.toml` supports `>=3.12,<3.13`; `uv.lock` resolves Python `3.12.*`. Run the following commands from the repository root:

```powershell
uv sync
uv run python -m experian_workflow.assurance.pipeline
```

The supplied synthetic sources are sufficient for normal execution. The original expense workflow runs with:

```powershell
uv run python -m experian_workflow.pipeline
```

The deterministic source generators are `scripts/generate_synthetic_data.py` and `scripts/generate_assurance_sources.py`. Regeneration is optional and rewrites synthetic source files; it is not needed to review the supplied example.

## Run outputs and terminal publication

Each assurance execution writes to `output/assurance_runs/<run_id>/`:

```text
manifest.json
control_assurance.parquet
assurance_reporting_mart.parquet
findings.csv
remediation_actions.csv
evidence_summary.json
assurance_report.html
publication/
  metrics.json
  metric_validation.json
  explainability.json
  validation_summary.json
  tables/
  html/
    assurance_dashboard.html
    reports/
    charts/
  tableau/
    assurance_dashboard.hyper
    assurance_dashboard.twb
    assurance_dashboard.twbx
    tableau_data_dictionary.csv
    tableau_validation.json
  powerpoint/
    assurance_executive_report.pptx
    slide_data.json
    powerpoint_validation.json
```

`manifest.json` is terminal publication evidence. It is written only after the required analytical and publication steps succeed. Earlier files are intermediate artifacts until that manifest exists. It records source/configuration hashes, population controls, reporting date, code commit, dirty state, and output paths. `publication/validation_summary.json` records the same-run validation evidence across channels.

The original expense pipeline uses `output/runs/<run_id>/` and produces quarantine, curated Parquet, audit summary, HTML report, and a terminal manifest.

## Current synthetic demonstration results

These are the governed example results for the supplied assurance sources and **2026-09-30** reporting date. They are demonstration results, not universal constants.

| Measure | Value |
| --- | ---: |
| Assurance tests | 9 |
| Sufficient evidence | 5 |
| Partial evidence | 1 |
| Insufficient evidence | 2 |
| Evidence not evaluable | 1 |
| Stale evidence | 2 |
| Unmapped assurance tests | 1 |
| High/critical residual risk | 2 |
| Residual risk not evaluable | 4 |
| Overdue management actions | 1 |
| Repeat findings | 1 |
| Open findings | 4 |

The source-record population flow is **291 expected → 291 received → 281 mapped → 253 evaluated**. The remaining populations are **10 unmapped source records** and **28 mapped records not tested**: `291 = 281 + 10` and `281 = 253 + 28`. The example also retains all **6 management actions**, **5 findings**, **9 control-assurance rows**, and **9 reporting-mart rows**.

## Validation model and testing

`publication/explainability.json` binds source roles, metric definitions, state meanings and validation boundaries to the same-run published metric/table hashes. PowerPoint Notes, HTML Data & Metrics, and Tableau About / Data & Metrics consume this metadata without recalculating business rules.

Metric acceptance compares Pandas, DuckDB, and an executable metric contract, then checks persisted publication readback. Independent scenario fixtures provide additional correctness checks. Reconciliation preserves explicit populations rather than silently dropping unmapped or non-evaluable cases.

HTML/browser publication checks verify structure, report/chart generation, expected links, and current-run content. These are programmatic publication checks, not a claim of live browser interaction testing. Tableau checks validate Hyper data parity, workbook bindings, packaged extract identity, and worksheet/dashboard visual contracts. Tableau Desktop execution is not part of this validation model and was not executed for finalization.

PowerPoint automated checks validate eight slides, package structure, run identity, and the navigation/artifact-link contract. Content tests also verify the reconciliation narrative, priorities, disclaimer, and all six management-action IDs. PowerPoint Desktop rendering QA may be performed separately from the pipeline; the pipeline can therefore truthfully retain `client_validation = NOT_EXECUTED` even when separate desktop-render evidence exists.

The presentation consistency gate compares all twelve embedded HTML metrics, complete assurance/finding/action/risk-domain records, actual bound PowerPoint headline values and every slide's metric Notes with the same-run publication. Material mismatches stop terminal publication. HTML accessibility checks cover structure and keyboard-control wiring; they do not establish browser rendering or assistive-technology conformance.

```powershell
uv run pytest tests/test_assurance_powerpoint.py -q
uv run pytest -q
uv run ruff check .
git diff --check
```

## Reproducibility and provenance

The published reviewer handoff lives under `review/`. Its guide records the clean producer run, source commit, and validation levels. The complete HTML subtree preserves relative links, and the eight slide previews come from the exact published deck. Local packages under ignored `output/submission/` are historical execution material; use `review/` for the current handoff.

The reviewer guide records the exact clean producer run and source commit; the corresponding ignored run directory retains the terminal manifest and validation summary. Later documentation commits do not change the producer identity of these artifacts.

Standalone assurance CSVs, field dictionaries, metrics and machine-readable manifests are intentionally omitted from the curated snapshot to avoid duplicate analytical copies. The TWBX contains its validated data extract, and HTML includes the data and definitions needed for offline review. To inspect all supporting files, reproduce the reviewer guide's producer source commit in a separate checkout and run the assurance command above. Its new run directory contains `publication/tables/`, `publication/metrics.json`, `publication/explainability.json`, Tableau metadata under `publication/tableau/`, `publication/validation_summary.json` and `manifest.json`. A new execution has a new run identity; the guide's producer run remains the identity of the committed snapshot.

## Design principles and limitations

One governed truth supplies every channel. Explicit `NOT_EVALUABLE` and unmapped states preserve uncertainty. Run-scoped provenance supports reproduction, while fail-closed terminal publication prevents a partially completed run from being represented as successful.

The exercise is a small local synthetic demonstration. Browser-rendered HTML and live interactions are **NOT_EXECUTED**; Tableau Desktop is **NOT_EXECUTED**. HTML structural and accessibility-wiring checks do not establish runtime or assistive-technology conformance. Local/offline artifact links assume the package folder structure remains intact. PowerPoint supports navigation and drill links; filtering belongs to the HTML and Tableau channels. Hashes and run identity establish provenance, while analytical contracts and reconciliation establish correctness.

Further implementation context is available in [design decisions](docs/DESIGN_DECISIONS.md) and [changed-requirement scenarios](docs/CHANGE_SCENARIOS.md).
