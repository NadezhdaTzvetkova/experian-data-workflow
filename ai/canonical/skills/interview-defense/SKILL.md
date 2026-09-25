# Interview Defense

## Purpose
Prepare the candidate to explain, demonstrate, challenge, and safely modify the Experian solution during the interview without relying on memorised syntax or AI-generated talking points.

## Core Narrative
Be able to explain:
1. what problem the workflow solves;
2. why the chosen data model and sources are appropriate;
3. how invalid data differs from valid audit/business exceptions;
4. how fitness for use is determined;
5. how completeness and correctness are proven;
6. how provenance and historical reproducibility work;
7. how trusted analytics are derived;
8. what trade-offs were deliberately made;
9. how the design would be operationalised and scaled;
10. how AI was used with human oversight.

## Demonstration Flow
A concise walkthrough should cover:
- source/config inputs;
- pipeline execution;
- validation/control results;
- accepted and quarantined populations;
- reconciliation;
- curated output;
- analytical mart or SQL result;
- one or two stakeholder observations;
- run manifest/provenance;
- tests/correctness evidence;
- assumptions and limitations.

## Changed-Requirement Drills
Be prepared to adapt the design live.

### Policy threshold changes
Example: travel limit becomes 750.
Expected seam: configuration change, not hard-coded Python.

### Reference source changes
Example: vendors now arrive from an API.
Expected seam: replace or add the source adapter while preserving downstream contracts where possible.

### Currency scope changes
Example: GBP is introduced.
Expected response: explain current monetary assumptions, conversion/reference-data needs, and which contracts/tests must change. Do not pretend multi-currency conversion already exists if it does not.

### Country-specific policy
Expected response: extend governed configuration/model semantics and add corresponding validation/tests.

### Historical reproducibility
Example: previous runs must remain reproducible after policy or vendor-reference changes.
Expected response: preserve applied config/reference identity, hashes/versions/effective dates, and run-specific evidence.

### Changed validation action
Example: an unresolved vendor should warn rather than quarantine.
Expected response: change the control severity/action deliberately and explain the fitness-for-use impact.

### Scale increase
Example: 100M records arrive daily.
Expected response: discuss partitioning, incremental processing, warehouse/distributed execution, orchestration and monitoring rather than forcing the local architecture unchanged.

## AI Discussion
Prepare truthful examples of:
- accepted AI suggestion;
- modified AI suggestion;
- rejected AI suggestion;
- how correctness was independently proven;
- where AI was not trusted;
- how the candidate would handle an AI suggestion during a live requirement change.

## High-Value Questions to Answer Cleanly
- Why this dataset?
- Why these controls and not more?
- Why quarantine some records but keep policy exceptions?
- How do you know no rows were lost?
- How do you know a join did not duplicate rows?
- Why integer minor units?
- Why a deterministic as_of_date?
- Why DuckDB?
- Why is Jupyter downstream rather than the pipeline itself?
- What breaks if reference data changes tomorrow?
- How would you monitor this in production?
- What would you change first at much larger scale?
- What did AI get wrong or overcomplicate?
- What limitation would you fix next if given more time?

## Guardrails
Do not memorise wording at the expense of understanding.
Do not claim implementation that does not exist.
Do not use production architecture as a substitute for explaining the actual local solution.
Do not defend unnecessary complexity merely because it has already been built.
If a live change exposes a genuine limitation, state it clearly and explain the smallest safe modification.
