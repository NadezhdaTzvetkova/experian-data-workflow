# Source-of-Truth Validation

## Purpose
Validate every design, code change, test, document, scope decision, and completion claim strictly against the written Experian exercise and REQUIREMENT_ACCEPTANCE_MATRIX.md.

## Workflow
1. Read SOURCE_OF_TRUTH_SPEC.md.
2. Read REQUIREMENT_ACCEPTANCE_MATRIX.md.
3. Identify the exact requirement IDs affected.
4. Inspect implementation and evidence.
5. Classify proposed work as REQUIRED_BY_SPEC, SUPPORTS_SPEC, ROLE_ALIGNED_OPTIONAL, or OVERENGINEERING.
6. Defer optional work that threatens mandatory completion.
7. Mark PASS only when concrete evidence exists.

## Required Output
For each reviewed requirement provide:
- requirement ID;
- implementation;
- verification;
- evidence;
- current status;
- smallest action needed to reach PASS.

## Guardrail
A library, framework, service, or technology merely existing in the repository never proves that a requirement is satisfied.
Role-description alignment is useful only after the written exercise remains fully satisfied.
