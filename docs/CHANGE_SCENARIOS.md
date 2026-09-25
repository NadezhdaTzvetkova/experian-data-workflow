# Change Scenarios

This document shows how the current design would adapt if requirements changed. The intent is to preserve the core contracts—traceability, validation semantics, reconciliation and reproducibility—while changing implementation details only where the new requirement justifies it.

## 1. Data volume grows from hundreds of rows to hundreds of millions

**What changes**
- Replace in-memory Pandas processing with a scalable execution engine where required.
- Partition curated data appropriately.
- Avoid loading full datasets into memory.
- Move source and curated storage to scalable object or warehouse storage.

**What stays the same**
- structural validation semantics;
- quarantine vs trusted-data distinction;
- row-count reconciliation;
- provenance and run evidence;
- independent analytical validation.

**Likely implementation options**
Spark, distributed SQL, warehouse-native transformations or another engine appropriate to the platform and workload.

## 2. Multiple currencies are introduced

**What changes**
- Extend the data contract to require currency-aware policy configuration.
- Prevent aggregation of monetary values across currencies without explicit conversion.
- Introduce governed FX rates if cross-currency reporting is required.

**New risks**
- incorrect policy threshold comparison;
- stale FX rates;
- inconsistent conversion dates;
- accidental aggregation of unlike monetary units.

**Control response**
Fail or quarantine records where required currency context cannot be established.

## 3. Expense data arrives daily

**What changes**
- Introduce scheduled orchestration.
- Add explicit business-date or partition identity.
- Make ingestion and publication idempotent.
- Add freshness monitoring.

**What stays the same**
The pipeline remains a deterministic unit that an orchestrator invokes rather than embedding orchestration logic inside transformations.

## 4. Vendor reference data becomes SCD Type 2

**What changes**
- Replace the current effective-date logic with an explicit temporal interval join.
- Enforce non-overlapping effective periods per vendor.
- Validate that each transaction resolves to at most one historical vendor record.

**New reconciliation**
Accepted transaction count must still equal the enriched curated count unless the changed requirement explicitly permits one-to-many relationships.

## 5. Policy limits change over time

**What changes**
- Version policy thresholds with effective dates.
- Resolve the applicable policy according to transaction date rather than one run-level policy version.

**New evidence**
The manifest should record the policy versions or policy dataset identity used during the run.

## 6. Quarantine volume becomes operationally significant

**What changes**
- Introduce configurable fitness-for-use thresholds.
- Emit quarantine-rate metrics and alerts.
- Record control-level trends across runs.

**Example policy**
A small number of isolated row defects may produce `SUCCESS_WITH_QUARANTINE`, while a material quarantine rate could cause the run to fail publication.

**Important**
Thresholds should be based on business risk, not arbitrary percentages.

## 7. Duplicate handling requirement changes

**Current behaviour**
Later duplicate transaction identifiers are quarantined.

**Possible changed requirement**
The source system may define a trusted update timestamp and require latest-record-wins semantics.

**What changes**
- Define the authoritative ordering field.
- Validate that ordering is deterministic.
- Preserve discarded/replaced records as evidence.
- Reconcile pre- and post-deduplication counts explicitly.

## 8. A new source is delivered through an API

**What changes**
Add an ingestion adapter responsible for:
- authentication;
- pagination;
- retry/backoff;
- response schema validation;
- source extraction timestamp;
- preservation of raw response evidence where appropriate.

**What does not change**
Downstream trusted-data contracts should remain independent of transport mechanism.

## 9. Real-time events are introduced

**What changes**
Only if the business requirement genuinely becomes event-driven:
- define event identity and ordering semantics;
- define replay/idempotency behaviour;
- define late-event handling;
- introduce streaming infrastructure where justified.

**What does not happen automatically**
Kafka or another broker is not added simply because data volume increases. Streaming technology is justified by event and latency requirements, not by architecture preference.

## 10. Production monitoring is required

**Metrics to expose**
- run status;
- source freshness;
- source row count;
- quarantined row count and rate;
- failures by control;
- reconciliation status;
- runtime duration;
- output publication status.

**Alert examples**
- structural contract failure;
- reconciliation failure;
- missing source;
- stale source;
- quarantine threshold exceeded;
- analytical cross-check mismatch.

## 11. Cloud deployment is required

**Possible mapping**
- immutable source evidence → object storage;
- curated datasets → object storage, warehouse or lakehouse;
- scheduled execution → managed orchestration;
- runtime → managed compute;
- manifests/control history → durable metadata store;
- metrics/logs → central monitoring;
- access → role-based IAM.

**Design principle**
The cloud implementation should preserve the logical contracts rather than forcing the contracts to match a particular vendor service.

## 12. A reviewer asks for another analytical dimension

**Example**
Analyse exception exposure by employee or month.

**Response**
Do not modify upstream trusted-data logic unless the new analysis requires additional governed attributes. Extend the downstream analytical layer and independently validate new headline metrics.

## 13. A required category is missing from a future dataset

**Current report assumption**
The deterministic exercise dataset contains known `meals` and `travel` categories.

**Changed requirement**
The report must support arbitrary category populations.

**What changes**
Remove hard-coded narrative assumptions and derive observations dynamically from available categories and exception rates.

## 14. Docker execution is required

**What changes**
Add a minimal container definition around the existing Python 3.12 + `uv` environment.

**What stays the same**
The pipeline command, deterministic data contracts, tests and outputs remain unchanged.

**Why this is low-risk**
Docker changes the execution environment, not the business logic.

## Decision rule for changed requirements

For any new requirement:

1. identify the changed business or operational need;
2. determine which existing contract is affected;
3. preserve unaffected contracts;
4. implement the smallest coherent change;
5. add evidence that proves the changed behaviour;
6. rerun reconciliation and regression tests;
7. update documentation and limitations;
8. human-review the result before publication.
