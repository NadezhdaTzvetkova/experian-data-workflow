# Analytics and Presentation

## Purpose
Build and review trusted analytical marts, KPI definitions, independent SQL checks, visualisations, and stakeholder-ready presentation for the Experian exercise.

## Workflow
1. Consume only trusted curated data.
2. Define every KPI explicitly:
   - population;
   - numerator;
   - denominator;
   - units;
   - filters;
   - business meaning.
3. Use DuckDB SQL for at least one meaningful analytical aggregation when it adds value.
4. Independently cross-check at least one headline KPI through a second implementation path, such as Pandas versus DuckDB SQL.
5. Limit analysis to a small number of useful observations.
6. Make every visual answer one clear stakeholder question.
7. State assumptions and limitations close to the affected analysis.
8. Avoid unsupported causal claims.
9. Prefer reliable static output over fragile interactivity when necessary.
10. Verify every displayed number against trusted curated or mart data.

## Suggested Audit Questions
- Where is spend concentrated?
- Where are policy exceptions concentrated?
- What exposure exists to high-risk or inactive vendors?
- Is there a meaningful category or time pattern worth further investigation?

## Presentation Priority
1. Correct number.
2. Correct population and denominator.
3. Clear message.
4. Readable layout and visual hierarchy.
5. Appropriate visual type.
6. Restrained professional styling.

## Professional Standard
The output should be suitable for audit and senior business stakeholders. Use clear titles, units, labels, concise annotations, and consistent formatting.
Experian-aligned visual treatment may be used subtly when it improves professional presentation, but branding must never override clarity, correctness, or proportionality.

## Public Framing
Describe the solution primarily in terms of data analytics engineering, data quality, controls, reconciliation, provenance, curated data, analytical marts, and audit evidence. Do not make the submission read like a QA automation framework.

## Guardrails
Do not make a dashboard the source of truth.
Do not calculate business logic only inside a notebook.
Do not report figures that cannot be traced to trusted data.
Do not imply causation from synthetic observations unless the data and design actually support it.
