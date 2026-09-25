# Human Oversight and Challenged AI Suggestions

AI assistance was used throughout the exercise, but suggestions were not accepted solely because they were plausible. This document records concrete cases where evidence, tests or requirement review changed the implementation.

## 1. Ground-truth assumptions were corrected instead of forcing the data

### Initial risk

The synthetic generator included deliberately injected audit examples. An early interpretation treated those examples too much like expected global totals.

### What the evidence showed

The deterministic random population naturally produced additional valid policy and vendor-risk exceptions beyond the deliberately injected examples.

### Human decision

The dataset was not manipulated to make the earlier assumption true. Instead, the ground-truth file was corrected to identify the intentionally injected examples while allowing naturally occurring valid exceptions to remain part of the analytical population.

### Why this matters

Ground truth should describe what is actually controlled and known. It should not be used to force real output to match an incorrect expectation.

## 2. Inactive-vendor logic was changed from current-state thinking to historical interpretation

### Initial risk

A simplistic implementation could treat `active_flag = 0` as meaning every transaction for that vendor was historically invalid or inactive.

### What the evidence showed

Vendor status has temporal meaning. A transaction may have occurred while the vendor was still valid even if the vendor is inactive today.

### Human decision

The control evaluates vendor validity relative to the transaction date and effective-date information rather than relying only on current state.

### Why this matters

Audit analysis frequently depends on historical truth, not merely the latest master-data state.

## 3. Analytical results were not accepted from a single implementation

### Initial risk

A SQL query can look correct while still containing an aggregation or interpretation error.

### Human decision

Headline KPIs produced in DuckDB are independently recalculated in Pandas. The pipeline fails if the two implementations disagree.

### Evidence

The reconciliation covers transaction count, spend in minor units, policy exceptions, high-risk vendor exceptions, inactive-vendor exceptions and overall audit exceptions.

### Why this matters

Independent calculation reduces the risk of accepting a plausible but incorrect analytical result.

## 4. A misleading report test was replaced with a test of the actual requirement

### Initial test

The report test initially asserted that the generated HTML must not contain the literal text `cdn.plot.ly`.

### What failed

Inline Plotly JavaScript itself can contain that string even when the report has no external CDN dependency.

### Human decision

The test was changed to check the real requirement: that the HTML does not include an external `<script src="https://cdn.plot.ly/...">` dependency.

### Why this matters

Tests should verify behaviour and risk, not implementation trivia or misleading string matches.

## 5. A local-state-dependent test was made hermetic

### Initial risk

The reporting test originally selected the latest folder under local `output/runs`. It passed on the development machine because historical runs already existed.

### What the review showed

A fresh clone or CI environment might have no run history, making the test fail for reasons unrelated to report correctness.

### Human decision

The test now creates its own temporary manifest, curated Parquet and audit summary. It no longer depends on prior local execution history.

### Why this matters

A reproducibility claim is weak if the tests themselves depend on hidden local state.

## 6. Manifest publication order was corrected

### Initial implementation

The pipeline initially wrote `manifest.json` before generating the final HTML report.

### Conflict

The documented contract defined the presence of the manifest as evidence that a run was complete. Writing it before all outputs existed violated that contract.

### Human decision

Report generation now completes first and `manifest.json` is written last. The manifest therefore acts as the publication marker for a completed run.

### Why this matters

Traceability documentation must match actual execution semantics.

## 7. Brittle file-editing commands were rejected or corrected

### Initial risk

Some AI-generated PowerShell edits depended on relative-path behaviour, fragile multiline replacements or assumptions about current file content.

### What happened

Commands failed safely or were stopped when expected anchors were not found. Changes were then applied against inspected file content using absolute paths, explicit guards and UTF-8-without-BOM/LF-safe writes.

### Human decision

Automation convenience was not prioritised over repository integrity.

## 8. Scope inflation was deliberately rejected

### Considered additions

Docker, cloud services, Terraform, Airflow, Spark, Kafka, APIs and additional visualisations were considered during design review.

### Human decision

Technologies were evaluated using four questions:
1. Does this improve requirement coverage?
2. Does it reduce a credible failure risk?
3. Does it materially increase reviewer information?
4. Is the complexity cost justified?

Most infrastructure additions were rejected because they would not improve the evidence required by the exercise. A minimal Dockerfile remained a defensible reproducibility enhancement and was treated separately from unnecessary production infrastructure.

### Why this matters

Senior engineering judgement includes knowing what not to build.

## Human acceptance rule

The final acceptance question for an AI-assisted change was:

> What independent evidence shows that this change is correct, proportionate and still aligned with the original requirement?

If that question could not be answered, the change was revised, rejected or left out.
