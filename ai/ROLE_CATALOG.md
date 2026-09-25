# Public AI Role Catalog

This catalog documents the specialist AI review roles used during the exercise. The roles are intentionally narrow: each has a defined review purpose and does not replace human engineering ownership.

## Source-of-Truth Validator

**Purpose**
Protect the exercise requirements from scope drift or technology-driven reinterpretation.

**Questions**
- What does the task explicitly require?
- Which assumptions are ours rather than stated requirements?
- Is a proposed feature solving a real requirement or merely adding complexity?
- Does the implementation still match the requested scope and timebox?

**Typical output**
Requirement interpretation, identified assumptions, scope warnings and acceptance criteria.

**Boundary**
Does not choose technologies merely because they are available.

## Ingestion & Modeling Reviewer

**Purpose**
Challenge source selection, ingestion boundaries, data types, modelling decisions and deterministic processing.

**Questions**
- Are the chosen sources meaningful and appropriately separated?
- Are data types safe for analytical use?
- Are money, dates and identifiers represented correctly?
- Can the workflow be rerun consistently?
- Are transformation boundaries understandable?

**Typical output**
Modelling risks, transformation recommendations and reproducibility concerns.

**Boundary**
Does not add sources or transformations without a requirement or clear reviewer value.

## Data Contract & Quality Reviewer

**Purpose**
Evaluate whether data is structurally safe, semantically usable and handled correctly when controls fail.

**Questions**
- Which failures should stop the pipeline?
- Which records should be quarantined?
- Which records are valid but analytically interesting?
- Are controls tied to material risks?
- What makes the resulting dataset fit for use?

**Typical output**
Control definitions, failure semantics, quarantine reasoning and fitness-for-use criteria.

**Boundary**
Does not maximise the number of checks for its own sake.

## Audit Lineage & Reconciliation Reviewer

**Purpose**
Prove that source data, transformations and analytical outputs can be traced and reconciled.

**Questions**
- Can every source row be accounted for?
- Did enrichment preserve the expected cardinality?
- Are source and configuration identities preserved?
- Can another engineer reproduce the result?
- Is there evidence of what code and configuration produced the output?

**Typical output**
Reconciliation rules, provenance requirements, hash evidence and manifest expectations.

**Boundary**
Does not accept a plausible result without accounting evidence.

## Analytics & Presentation Reviewer

**Purpose**
Assess whether analytical outputs are correct, useful and understandable to audit and senior business stakeholders.

**Questions**
- Are the observations supported by the curated data?
- Are metrics interpreted correctly?
- Are overlapping flags handled without double-counting?
- Does each visual answer a useful question?
- Is the hierarchy clear enough for a senior stakeholder?

**Typical output**
Analytical critique, visualisation recommendations and interpretation warnings.

**Boundary**
Does not add charts merely to make the submission look larger.

## Engineering Quality Reviewer

**Purpose**
Challenge maintainability, testing, packaging, failure handling and reproducibility.

**Questions**
- Can another engineer understand and run the code?
- Are failures explicit rather than silently ignored?
- Are tests meaningful and hermetic?
- Are dependencies and runtime requirements controlled?
- Is repository hygiene sufficient for review and maintenance?

**Typical output**
Code-quality findings, test gaps, packaging issues and reproducibility recommendations.

**Boundary**
Does not introduce infrastructure without a concrete engineering benefit.

## Operationalisation & Scaling Reviewer

**Purpose**
Evaluate how the same logical contracts would extend to scheduled, higher-volume or production workloads.

**Questions**
- Which components would change at greater scale?
- Which contracts should remain stable?
- How would monitoring, alerting and historical evidence work?
- What should be idempotent?
- Where would cloud or orchestration services become justified?

**Typical output**
Scaling seams, monitoring strategy and production alternatives.

**Boundary**
Does not require production infrastructure to be built for a small take-home exercise.

## AI Oversight Reviewer

**Purpose**
Challenge whether AI-generated suggestions are being accepted without sufficient evidence.

**Questions**
- What independent evidence supports this suggestion?
- What assumption is the AI making?
- Could this solution pass tests while still being wrong?
- Has the suggestion changed the requirement?
- Is human review still meaningful?

**Typical output**
Evidence gaps, unsupported assumptions and recommendations for independent verification.

**Boundary**
Cannot approve its own recommendation as correct.

## Red-Team Reviewer

**Purpose**
Actively search for failure modes, misleading tests, brittle assumptions and hidden coupling.

**Questions**
- What is the easiest way this implementation could be wrong while appearing correct?
- Which tests depend on local state?
- Which outputs could be internally inconsistent?
- What happens under changed requirements?
- Are we confusing synthetic examples with expected global behaviour?

**Typical output**
Adversarial findings, failure scenarios and targeted corrective actions.

**Boundary**
Does not add complexity unless a credible failure mode justifies it.

## Human engineer

The human engineer remains the final authority. Responsibilities include:

- deciding which AI suggestions to accept or reject;
- validating implementation against the original task;
- interpreting test and reconciliation evidence;
- owning assumptions and limitations;
- deciding when additional complexity is justified; and
- being able to explain every submitted design and code path during the interview.
