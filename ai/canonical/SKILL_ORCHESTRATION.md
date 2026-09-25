# Skill Orchestration Map

`MASTER_SKILL.md` is the only entry point.

| Current problem | Specialist skill |
|---|---|
| What exactly does Experian require / is this complete? | `source-of-truth-validation` |
| How should sources, grain, keys and transformations work? | `ingestion-and-modeling` |
| What quality controls and failure semantics should exist? | `data-contract-quality` |
| How do we prove completeness, provenance and history? | `audit-lineage-reconciliation` |
| How should KPIs, SQL marts, charts and presentation work? | `analytics-presentation` |
| Is code/test/Git/repository quality strong? | `engineering-quality` |
| How would this be monitored, secured, recovered and scaled? | `operationalisation-scaling` |
| How do we prove responsible AI use and human ownership? | `ai-oversight` |
| What can still break or mislead the reviewer? | `red-team-review` |
| How do I defend it and adapt live? | `interview-defense` |

## Orchestration Rules

1. Read source-of-truth and acceptance matrix first.
2. Load only the specialist skill relevant to the current phase.
3. One implementation orchestrator owns repository changes.
4. Specialist skills guide/review; they do not independently redesign the whole system.
5. Do not run parallel coding agents on the same files.
6. After each coherent slice, verify before moving on.
7. Before submission: source-of-truth audit -> engineering review -> red-team -> human ownership -> final gate -> interview defence.
