# Data Contract and Quality

## Purpose
Design and review schemas, risk-linked controls, validation dependencies, quarantine behavior, fit-for-use logic, and failure semantics.

## Workflow
1. Define the structural data contract.
2. Select only high-value controls justified by concrete risk.
3. For every control define:
   - control ID;
   - category;
   - risk addressed;
   - rule;
   - prerequisite;
   - severity;
   - failure action;
   - evidence emitted.
4. Separate invalid data from valid audit/business exceptions.
5. Use PASS, FAIL, NOT_APPLICABLE, and NOT_EVALUABLE where dependency semantics matter.
6. Preserve quarantined records with original identity/value, control ID, failure reason, run ID, and timestamp.
7. Prevent cascading false failures when prerequisites are missing.
8. Verify known injected defects independently from production validation logic.
9. Define the final fitness-for-use decision.

## Core Candidate Controls
- required source schema;
- required key completeness;
- transaction-key uniqueness;
- amount validity;
- temporal validity;
- reference integrity;
- reference-key uniqueness before joins;
- join-cardinality integrity;
- record reconciliation.

## Failure Semantics
Structural source/configuration failure -> FAIL RUN.
Record-level data-quality defect -> QUARANTINE when safe.
Valid audit/business exception -> KEEP + FLAG.
Missing prerequisite -> NOT_EVALUABLE.
Reconciliation failure -> FAIL RUN.

## Fitness-for-Use Gate
Trusted analytical use requires:
- structural contract passes;
- blocking controls pass;
- every source row is accounted for;
- trusted output satisfies key/schema rules;
- invalid records are isolated with evidence;
- no unexplained loss or duplication exists;
- downstream analytics use only trusted accepted records.

Run statuses:
- SUCCESS;
- SUCCESS_WITH_QUARANTINE;
- FAILED.

## Guardrails
Do not add controls merely to increase count.
Do not infer authoritative business domains or thresholds from observed dataset frequency.
Do not quarantine valid business exceptions merely because they are interesting or risky.
