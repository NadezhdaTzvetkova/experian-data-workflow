# Requirement Acceptance Matrix

This is the completion and submission gate.

Allowed statuses:
- `NOT_STARTED`
- `PARTIAL`
- `PASS`
- `NOT_APPLICABLE_WITH_JUSTIFICATION`
- `FAIL`

A row may be marked `PASS` only when the stated evidence exists.

| ID | Source-of-truth requirement | Minimum evidence | Status |
|---|---|---|---|
| R1.1 | Ingest one or more sources | successful pipeline run + source inventory | NOT_STARTED |
| R1.2 | Use Python and/or SQL for processing/transformation | executed code/SQL + output | NOT_STARTED |
| R1.3 | Structured analytics-ready output | curated output + explicit schema/data dictionary | NOT_STARTED |
| R1.4 | Appropriate modelling/transformation choices | grain/keys/model rationale + verification | NOT_STARTED |
| R1.5 | Consistent reruns | deterministic rerun verification | NOT_STARTED |
| R1.6 | Explain decisions, assumptions, limitations | README/design notes | NOT_STARTED |
| R2.1 | Appropriate quality/validation controls | control catalogue + tests/evidence | NOT_STARTED |
| R2.2 | Explain why controls were selected | risk mapping | NOT_STARTED |
| R2.3 | Explain risks addressed | control catalogue | NOT_STARTED |
| R2.4 | Determine fitness for use | explicit fit-for-use gate/status | NOT_STARTED |
| R2.5 | Define response to validation failures | fail/quarantine/flag semantics + tests | NOT_STARTED |
| R3.1 | Trace source data | source IDs/inventory/hashes | NOT_STARTED |
| R3.2 | Trace transformations and processing | lineage + stage/code/SQL identity | NOT_STARTED |
| R3.3 | Trace execution information | run manifest/log evidence | NOT_STARTED |
| R3.4 | Historical results where appropriate | run-specific outputs + reference/config identity | NOT_STARTED |
| R3.5 | Another engineer can understand/maintain/reproduce | clean-run instructions + docs | NOT_STARTED |
| R4.1 | Small number of useful observations | analysis output | NOT_STARTED |
| R4.2 | Appropriate analytical/visual method | notebook/report/charts | NOT_STARTED |
| R4.3 | Clear communication of analysis/insights | stakeholder-readable output | NOT_STARTED |
| R4.4 | Well structured/easy to navigate | presentation review | NOT_STARTED |
| R4.5 | Appropriate visualisations | chart review | NOT_STARTED |
| R4.6 | Layout/readability/visual hierarchy | reviewer audit | NOT_STARTED |
| R4.7 | Professional standard for audit/senior stakeholders | final presentation audit | NOT_STARTED |
| R5.1 | Code quality and reusability | code review + lint/tests | NOT_STARTED |
| R5.2 | Organisation and documentation | repository audit | NOT_STARTED |
| R5.3 | Testing and validation | focused tests + E2E verification | NOT_STARTED |
| R5.4 | Version control | clean Git repository/history/status | NOT_STARTED |
| R5.5 | Error and exception handling | failure behavior tests/demo | NOT_STARTED |
| R5.6 | Performance and scalability considerations | README/interview defence | NOT_STARTED |
| R5.7 | Explain engineering approach/trade-offs | design decisions | NOT_STARTED |
| AI1 | Explain how AI was used | factual AI-assisted examples | NOT_STARTED |
| AI2 | Evaluate/challenge AI suggestions | accepted/modified/rejected examples | NOT_STARTED |
| AI3 | Demonstrate result correctness | multi-channel correctness evidence | NOT_STARTED |
| AI4 | Adapt when requirements change | change seams + interview drills | NOT_STARTED |
| I1 | Solution can be explained/demonstrated | demo script + successful run | NOT_STARTED |
| I2 | No confidential/proprietary/personal data | synthetic/public data statement + inspection | NOT_STARTED |
| I3 | Scope remains proportionate to ~2–3 hours | reviewer judgement | NOT_STARTED |
| I4 | Operationalise/monitor/scale discussion ready | interview defence notes | NOT_STARTED |

## Submission Gate

Submission is blocked if any mandatory source-of-truth row is:
- `FAIL`;
- `NOT_STARTED`;
- unresolved `PARTIAL`.

Optional role-aligned enhancements may remain incomplete and **must not block submission** once all source-of-truth requirements pass.
