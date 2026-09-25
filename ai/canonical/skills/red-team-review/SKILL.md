# Red-Team Review

## Purpose
Perform an adversarial final review of the Experian submission to find correctness gaps, silent data loss, misleading evidence, overengineering, stale documentation, and interview-defence weaknesses before completion is claimed.

## Review Order
1. Read SOURCE_OF_TRUTH_SPEC.md.
2. Read REQUIREMENT_ACCEPTANCE_MATRIX.md.
3. Inspect the actual repository and generated evidence.
4. Re-run the canonical verification path.
5. Challenge every PASS claim.
6. Report material findings before optional polish.

## Adversarial Questions
### Source and Transformation
- Can any source row disappear silently?
- Can any row duplicate unexpectedly?
- Can malformed data be coerced into something that looks valid?
- Can a join multiply records?
- Can current reference state silently reinterpret a historical run?
- Can local time change a business result?

### Quality
- Are controls tied to concrete risks?
- Are invalid records distinguished from valid audit exceptions?
- Can prerequisite failures create false downstream failures?
- Is fitness-for-use explicit?
- Does quarantine preserve enough evidence?

### Reconciliation and Evidence
- Does source_count equal accepted_count + quarantined_count?
- Does accepted count remain stable across one-to-one enrichment?
- Are financial reconciliations semantically valid?
- Do hashes prove only identity, or are they being overstated as correctness?
- Can a stakeholder number be traced back to trusted source evidence?

### Analytics
- Are populations, denominators, filters, and units explicit?
- Can a KPI be independently reproduced?
- Are any observations written as causal conclusions without evidence?
- Does the notebook/dashboard consume trusted data only?

### Engineering
- Does a clean environment reproduce the project?
- Are commands in documentation accurate?
- Are there unused dependencies or dead files?
- Are failure paths tested?
- Is Git clean?
- Does the public repository accidentally expose unrelated internal or sensitive material?

### Scope and Reviewer Perception
- Does this look larger than a proportionate 2–3 hour exercise?
- Does any artifact exist mainly to demonstrate technology?
- Does the public repository look like an AI-generated compliance framework instead of a clear data analytics engineering solution?
- Could a simpler design communicate the same competence more clearly?
- Has optional role alignment delayed mandatory evidence?

### Human Ownership
- Can the candidate explain every meaningful component?
- Can she adapt a policy threshold, source adapter, reference rule, or control action live?
- Can she state what AI suggested and why she accepted, modified, or rejected it?
- Can she explain what would change in production without pretending it was implemented?

## Severity
Classify findings as:
- BLOCKER — violates a mandatory requirement or invalidates correctness;
- MATERIAL — creates meaningful reliability, maintainability, presentation, or interview risk;
- MINOR — polish or low-risk improvement;
- OPTIONAL — useful only if mandatory work is already complete.

Only BLOCKER and unresolved MATERIAL findings should prevent the final completion claim.

## Output
For each finding provide:
- severity;
- affected requirement/risk;
- evidence;
- why it matters;
- smallest corrective action;
- verification required after the fix.

## Guardrail
Do not redesign a correct solution merely to make the red-team review look productive. A clean review with no material findings is a valid outcome.
