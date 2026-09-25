# Operationalisation and Scaling

## Purpose
Prepare and review how the local Experian workflow would be operationalised, monitored, secured, recovered, and scaled in production without bloating the take-home implementation.

## Core Principle
The written exercise explicitly asks the candidate to discuss operationalisation, monitoring, and scaling, but does not require production infrastructure. Implement locally only what strengthens correctness and reproducibility; discuss production architecture rather than pretending to deploy it.

## Implement Locally
- explicit run status;
- deterministic rerun behavior;
- run manifest and execution evidence;
- stage-level logging sufficient to diagnose a run;
- trusted-output publication semantics;
- source/config/reference identity;
- no secrets, credentials, confidential data, proprietary data, or personal data;
- recoverability through preserved source + code + configuration/reference identity.

## Discuss Rather Than Build Unless a Requirement Changes
- S3 raw/landing and curated zones;
- AWS Glue, Lambda, or ECS depending workload characteristics;
- Athena, Redshift, or another distributed analytical engine;
- partitioning and incremental processing;
- EventBridge, Step Functions, or enterprise scheduling/orchestration;
- CloudWatch logs, metrics, dashboards, and alarms;
- IAM least privilege;
- encryption at rest and in transit;
- Secrets Manager or equivalent;
- data classification and retention;
- dependency patching and vulnerability management;
- source/code/configuration backup;
- disaster recovery;
- Terraform or other infrastructure-as-code.

## Monitoring Signals
Prepare concrete monitoring for:
- source arrival;
- source freshness;
- unexpected row-volume change;
- schema/contract failure;
- quarantine count and rate;
- validation/control failures;
- reconciliation status;
- pipeline runtime;
- output freshness;
- final run status;
- repeated/replayed source detection where relevant.

## Failure and Recovery Semantics
Structural failure -> run FAILED and no trusted publication.
Record-level defect -> quarantine when safe to continue.
Audit/business exception -> retain and flag.
Reconciliation failure -> run FAILED.
Retry must not duplicate or silently alter business output.
Preserved source + versioned code/config/reference inputs should allow regeneration of trusted outputs.

## Scaling Scenarios
Be prepared to explain what changes if:
- files arrive daily rather than once;
- data reaches 100M+ rows;
- late-arriving data appears;
- source schema drifts;
- the same source is replayed;
- a vendor/reference record is corrected historically;
- policy thresholds become effective-dated;
- one required source is unavailable;
- PII is introduced;
- a daily SLA and alerting requirement is added.

## Production Mapping
Local source files -> S3 raw/landing.
Curated Parquet -> S3 curated.
SQLite/reference source -> governed SQL/RDS/external source.
SQLAlchemy -> governed source connector.
Local Python batch -> Glue/Lambda/ECS depending workload.
DuckDB -> Athena/Redshift/distributed SQL where scale requires it.
Run manifest -> durable audit/control metadata store.
Local logging -> CloudWatch.
YAML configuration -> governed/versioned configuration store.
Manual execution -> scheduler/EventBridge/Step Functions.
Local permissions -> IAM/RBAC.
Git -> enterprise source control and CI/CD.
Infrastructure discussion -> Terraform/IaC.

## Performance Reasoning
For the small take-home, prefer transparent Pandas/Parquet processing.
At larger scale, avoid full in-memory Pandas loads; use partitioning, predicate pushdown, incremental processing, distributed execution, or warehouse-native transformations as appropriate.
Do not prematurely implement distributed infrastructure merely to demonstrate awareness of it.

## Security and Privacy
Use least privilege.
Keep secrets outside code and configuration committed to Git.
Encrypt sensitive production data at rest and in transit.
Classify data and apply retention/access controls.
Avoid logging sensitive field values.
The take-home itself must contain no confidential, proprietary, or personal data.

## Reviewer Value Test
Before adding any operational technology ask:
"What would the Experian panel learn from implementing this that they could not learn from a simpler local solution plus a clear production-evolution explanation?"

If the answer is weak, discuss it instead of building it.

## Guardrail
Do not build AWS, Terraform, orchestration platforms, containers, distributed processing, or monitoring infrastructure merely because they are relevant to the real role. The exercise explicitly prioritises judgement and proportionality over production-scale implementation.
