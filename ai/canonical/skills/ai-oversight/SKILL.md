# AI Oversight

## Purpose
Ensure AI-assisted work remains technically owned, independently verified, explainable, and truthful for the Experian exercise and interview.

## Core Principle
AI is an accelerator, not an authority. The candidate remains responsible for design, correctness, quality, trade-offs, and every submitted artifact.

## Workflow
For significant AI-assisted work:
1. Identify what AI proposed or generated.
2. Understand the intent and assumptions.
3. Inspect the code/design before accepting it.
4. Run the narrowest relevant proof.
5. Cross-check important results through an independent channel.
6. Modify or reject the suggestion when it weakens correctness, clarity, proportionality, or explainability.
7. Preserve only factual, defensible examples of AI use for interview discussion.

## Required AI Oversight Examples
Prepare at least:
- one AI suggestion accepted after verification;
- one AI suggestion modified because the original design was incomplete or disproportionate;
- one AI suggestion rejected because it added risk, overengineering, or incorrect semantics.

Use only examples that actually occurred. Never invent an AI-use story for interview effect.

## Independent Validation
AI-generated or AI-modified work should be validated by appropriate combinations of:
- focused unit tests;
- end-to-end tests;
- deterministic synthetic ground truth;
- reconciliation;
- independent Python/SQL KPI comparison;
- schema/key/cardinality checks;
- manual trace from result to source;
- code review and diff inspection.

## Human Ownership Gate
The candidate must be able to explain:
- why every meaningful file exists;
- important inputs and outputs;
- transformation semantics;
- each major control and its risk;
- failure behavior;
- reconciliation;
- important tests;
- key trade-offs;
- assumptions and limitations;
- how the design would change under new requirements.

If a meaningful part cannot be explained, simplify it or learn it before submission.

## Guardrails
Do not conceal legitimate AI use.
Do not submit AI conversation transcripts unless explicitly requested.
Do not treat AI confidence as evidence.
Do not weaken tests to make generated code pass.
Do not claim AI-generated architectural sophistication that was not independently evaluated.
Do not invent accepted/modified/rejected examples.
