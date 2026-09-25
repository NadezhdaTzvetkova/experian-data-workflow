---
name: experian-senior-data-analytics-master
description: Orchestrate the Experian Senior Data Analytics Engineer take-home strictly against the written exercise, using progressive specialist skills for ingestion, modelling, data quality, audit evidence, analytics, engineering quality, operationalisation, AI oversight, red-team review and interview defence.
---

# Experian Senior Data Analytics Master Skill

This is the **single active entry point** for the Experian agentic-control system.

## Absolute Authority

Before planning, coding, reviewing, documenting, or claiming completion:

1. Read `SOURCE_OF_TRUTH_SPEC.md`.
2. Read `REQUIREMENT_ACCEPTANCE_MATRIX.md`.
3. Apply later explicit Experian clarifications if any.
4. Treat role-description alignment and external research as secondary.
5. Never allow an AI suggestion, framework, role keyword, or earlier preference to override or expand the written exercise.

Every proposed change must be classified as:

- `REQUIRED_BY_SPEC`
- `SUPPORTS_SPEC`
- `ROLE_ALIGNED_OPTIONAL`
- `OVERENGINEERING`

Only `REQUIRED_BY_SPEC` and `SUPPORTS_SPEC` may block completion.

## Master Objective

Deliver the smallest complete, reliable, reproducible, audit-friendly, analytically useful, professional, and interview-defensible solution that satisfies every written Experian requirement.

Central question:

> Can I prove that the output is the correct, complete, and consistent transformation of the inputs, identify exactly where trust was lost if it is not, and preserve enough evidence for another engineer or auditor to reproduce and verify the result?

## Non-Negotiable Invariants

- Use no confidential, proprietary, or personal data.
- Preserve source/raw evidence.
- Never silently lose source records.
- Keep invalid data separate from valid audit/business exceptions.
- Reconcile source records to accepted/quarantined outcomes.
- Preserve every result-affecting source/config/reference identity.
- Equivalent inputs + configuration + code must produce equivalent business results.
- Do not let uncontrolled wall-clock time determine business-rule outcomes.
- Use deterministic numeric semantics for financial reconciliation.
- Keep Jupyter out of the core ETL; notebooks consume trusted outputs.
- Do not add frameworks/infrastructure without a source-of-truth requirement or concrete risk.
- Never mark a requirement `PASS` without evidence.
- Never weaken a valid test merely to make AI-generated code pass.
- Never claim hosted CI/cloud behavior that was not actually verified.
- Stop adding scope when mandatory requirements pass and material risks are closed.
- Keep the public submission framed as data analytics engineering, data quality, controls, reconciliation, provenance and audit evidence rather than as a QA automation framework.

## Reviewer Value Test

Before adding any dependency, framework, abstraction, service, document, test category, source type, or infrastructure component, ask:

> What would the Experian panel learn from this addition that they could not already learn from something simpler?

If the answer is weak, do not add it. Prefer the simpler implementation or keep the topic as an interview/production-evolution discussion.

This test may reduce optional scope, but it may never be used to remove evidence required by the written exercise.

## Orchestration

Use one implementation orchestrator. Specialist skills are loaded **sequentially and on demand**, not as competing agents.

### Skill Routing

- requirement interpretation / status / completion gate -> `source-of-truth-validation`
- ingestion / trust boundaries / grain / keys / modelling -> `ingestion-and-modeling`
- data contract / validation / quarantine / fit-for-use -> `data-contract-quality`
- provenance / manifests / reconciliation / history / idempotency -> `audit-lineage-reconciliation`
- KPI / SQL mart / visuals / notebook / stakeholder communication -> `analytics-presentation`
- code quality / tests / errors / Git / maintainability -> `engineering-quality`
- monitoring / security / recovery / scaling / AWS evolution -> `operationalisation-scaling`
- AI review / human oversight / factual AI examples -> `ai-oversight`
- adversarial final audit -> `red-team-review`
- panel rehearsal / changed requirements -> `interview-defense`

Do not preload every skill.

## Canonical Execution Loop

For every meaningful change:

1. Identify the exact requirement ID(s) or concrete risk.
2. Inspect current repository state and relevant outputs.
3. State the expected observable behavior.
4. Make the smallest coherent change.
5. Run the narrowest relevant proof.
6. Inspect output, logs, and diff.
7. Broaden verification only after the narrow proof succeeds.
8. Update the acceptance matrix only when evidence exists.
9. Continue automatically unless a genuinely consequential decision requires human input.

## Candidate + PowerShell Working Style

Default submission root:

`repository root`

Canonical AI control root:

`ai/canonical`

When the candidate pastes terminal output:

1. inspect it;
2. explain what it proves;
3. identify anything wrong;
4. give the next exact action;
5. use one physical PowerShell command line at a time;
6. always `cd` explicitly to the intended directory first;
7. fail fast and validate immediately.

Do not introduce WSL/Docker unless the specification or a concrete risk justifies them.

## Correctness Evidence Hierarchy

Prefer multiple independent evidence channels:

1. deterministic synthetic source generation with known injected defects;
2. explicit contracts;
3. risk-linked controls;
4. quarantine evidence;
5. record reconciliation;
6. financial reconciliation when valid;
7. schema/key/join-cardinality tests;
8. independent Python/SQL KPI cross-check;
9. deterministic rerun comparison;
10. end-to-end pipeline test;
11. source/config/reference/code provenance;
12. manual trace from stakeholder result to source.

A synthetic ground-truth defect manifest may be used as an independent test oracle, but production validation must not depend on it.

Do not rely on a single test channel.

## Final Gate

Implementation is complete only when:

- every source-of-truth requirement is `PASS`;
- clean-environment reproduction succeeds;
- canonical verification command succeeds;
- end-to-end pipeline succeeds;
- reconciliation succeeds;
- trusted analytics reconcile to curated data;
- presentation is professional;
- documentation matches reality;
- repository/package is clean;
- AI-use examples are factual and defendable;
- candidate can explain all meaningful code/design decisions;
- red-team review has no unresolved material finding.

Role-aligned optional enhancements must never delay this state.
