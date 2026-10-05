from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from experian_workflow.assurance.ingestion import (
    CONTROL_EVIDENCE_COLUMNS,
    FINDING_COLUMNS,
    MANAGEMENT_ACTION_COLUMNS,
    SQLITE_TABLE_COLUMNS,
)


@dataclass(frozen=True)
class QualityResult:
    control_id: str
    dataset: str
    status: str
    blocking: bool
    reason_code: str | None
    message: str
    affected_ids: tuple[str, ...] = ()


class StructuralValidationError(ValueError):
    pass


def _missing_columns(
    frame: pd.DataFrame,
    required_columns: list[str],
) -> list[str]:
    return sorted(set(required_columns) - set(frame.columns))


def validate_required_columns(
    frame: pd.DataFrame,
    required_columns: list[str],
    *,
    dataset: str,
    control_id: str,
) -> QualityResult:
    missing = _missing_columns(frame, required_columns)

    if missing:
        return QualityResult(
            control_id=control_id,
            dataset=dataset,
            status="FAIL",
            blocking=True,
            reason_code="MISSING_REQUIRED_COLUMNS",
            message=f"Missing required columns: {', '.join(missing)}",
        )

    return QualityResult(
        control_id=control_id,
        dataset=dataset,
        status="PASS",
        blocking=False,
        reason_code=None,
        message="Required columns are present.",
    )


def validate_sqlite_contracts(
    tables: dict[str, pd.DataFrame],
) -> list[QualityResult]:
    results: list[QualityResult] = []

    for table, required_columns in SQLITE_TABLE_COLUMNS.items():
        if table not in tables:
            results.append(
                QualityResult(
                    control_id=f"DQ_SQLITE_{table.upper()}_SCHEMA",
                    dataset=table,
                    status="FAIL",
                    blocking=True,
                    reason_code="MISSING_REQUIRED_TABLE",
                    message=f"Required table is missing: {table}",
                )
            )
            continue

        results.append(
            validate_required_columns(
                tables[table],
                required_columns,
                dataset=table,
                control_id=f"DQ_SQLITE_{table.upper()}_SCHEMA",
            )
        )

    return results


def validate_control_evidence_contract(
    payload: dict[str, Any],
    frame: pd.DataFrame,
) -> list[QualityResult]:
    results: list[QualityResult] = []

    schema_version = payload.get("schema_version")
    if schema_version != "1.0":
        results.append(
            QualityResult(
                control_id="DQ_EVIDENCE_SCHEMA_VERSION",
                dataset="control_evidence",
                status="FAIL",
                blocking=True,
                reason_code="UNSUPPORTED_SCHEMA_VERSION",
                message=(
                    "Expected control-evidence schema version 1.0; "
                    f"observed {schema_version!r}."
                ),
            )
        )
    else:
        results.append(
            QualityResult(
                control_id="DQ_EVIDENCE_SCHEMA_VERSION",
                dataset="control_evidence",
                status="PASS",
                blocking=False,
                reason_code=None,
                message="Control-evidence schema version is supported.",
            )
        )

    results.append(
        validate_required_columns(
            frame,
            CONTROL_EVIDENCE_COLUMNS,
            dataset="control_evidence",
            control_id="DQ_EVIDENCE_REQUIRED_COLUMNS",
        )
    )

    return results


def validate_findings_contract(
    frame: pd.DataFrame,
) -> QualityResult:
    return validate_required_columns(
        frame,
        FINDING_COLUMNS,
        dataset="findings",
        control_id="DQ_FINDINGS_REQUIRED_COLUMNS",
    )


def validate_management_actions_contract(
    frame: pd.DataFrame,
) -> QualityResult:
    return validate_required_columns(
        frame,
        MANAGEMENT_ACTION_COLUMNS,
        dataset="management_actions",
        control_id="DQ_ACTIONS_REQUIRED_COLUMNS",
    )


def validate_unique_key(
    frame: pd.DataFrame,
    *,
    dataset: str,
    key_columns: list[str],
    control_id: str,
) -> QualityResult:
    missing = _missing_columns(frame, key_columns)

    if missing:
        return QualityResult(
            control_id=control_id,
            dataset=dataset,
            status="NOT_EVALUABLE",
            blocking=True,
            reason_code="MISSING_KEY_PREREQUISITE",
            message=(
                "Uniqueness cannot be evaluated because key columns are "
                f"missing: {', '.join(missing)}"
            ),
        )

    null_or_blank_key_mask = frame[key_columns].apply(
        lambda column: (
            column.isna()
            | column.astype("string").str.strip().eq("")
        )
    ).any(axis=1)

    if null_or_blank_key_mask.any():
        affected = tuple(
            str(index)
            for index in frame.index[null_or_blank_key_mask].tolist()
        )
        return QualityResult(
            control_id=control_id,
            dataset=dataset,
            status="FAIL",
            blocking=True,
            reason_code="NULL_REQUIRED_KEY",
            message="Required key contains null or blank values.",
            affected_ids=affected,
        )

    duplicate_mask = frame.duplicated(
        subset=key_columns,
        keep=False,
    )
    if duplicate_mask.any():
        affected = tuple(
            str(index)
            for index in frame.index[duplicate_mask].tolist()
        )
        return QualityResult(
            control_id=control_id,
            dataset=dataset,
            status="FAIL",
            blocking=True,
            reason_code="DUPLICATE_KEY",
            message=(
                "Duplicate rows found for key "
                f"{', '.join(key_columns)}."
            ),
            affected_ids=affected,
        )

    return QualityResult(
        control_id=control_id,
        dataset=dataset,
        status="PASS",
        blocking=False,
        reason_code=None,
        message=(
            "Required key is complete and unique for "
            f"{', '.join(key_columns)}."
        ),
    )


def validate_control_evidence_population(
    frame: pd.DataFrame,
) -> QualityResult:
    required = [
        "test_id",
        "expected_population",
        "received_population",
        "mapped_population",
        "tested_population",
        "exception_count",
    ]
    missing = _missing_columns(frame, required)

    if missing:
        return QualityResult(
            control_id="DQ_EVIDENCE_POPULATION_ORDER",
            dataset="control_evidence",
            status="NOT_EVALUABLE",
            blocking=True,
            reason_code="MISSING_POPULATION_PREREQUISITE",
            message=(
                "Population relationships cannot be evaluated because "
                f"columns are missing: {', '.join(missing)}"
            ),
        )

    numeric = frame[required[1:]].apply(
        pd.to_numeric,
        errors="coerce",
    )

    invalid_numeric_mask = numeric.isna().any(axis=1)
    if invalid_numeric_mask.any():
        affected = tuple(
            frame.loc[
                invalid_numeric_mask,
                "test_id",
            ].astype(str)
        )
        return QualityResult(
            control_id="DQ_EVIDENCE_POPULATION_ORDER",
            dataset="control_evidence",
            status="FAIL",
            blocking=True,
            reason_code="INVALID_POPULATION_VALUE",
            message="Population fields must contain valid numeric values.",
            affected_ids=affected,
        )

    negative_mask = (numeric < 0).any(axis=1)
    impossible_order_mask = (
        (numeric["mapped_population"] > numeric["received_population"])
        | (numeric["tested_population"] > numeric["mapped_population"])
        | (numeric["exception_count"] > numeric["tested_population"])
    )

    invalid_mask = negative_mask | impossible_order_mask

    if invalid_mask.any():
        affected = tuple(
            frame.loc[
                invalid_mask,
                "test_id",
            ].astype(str)
        )
        return QualityResult(
            control_id="DQ_EVIDENCE_POPULATION_ORDER",
            dataset="control_evidence",
            status="FAIL",
            blocking=True,
            reason_code="IMPOSSIBLE_POPULATION_RELATIONSHIP",
            message=(
                "Population values violate required non-negative or "
                "ordering constraints."
            ),
            affected_ids=affected,
        )

    return QualityResult(
        control_id="DQ_EVIDENCE_POPULATION_ORDER",
        dataset="control_evidence",
        status="PASS",
        blocking=False,
        reason_code=None,
        message="Population relationships are locally plausible.",
    )


def _validate_reference(
    child: pd.DataFrame,
    parent: pd.DataFrame,
    *,
    child_dataset: str,
    child_key: str,
    parent_key: str,
    control_id: str,
    nullable: bool = False,
    row_identifier: str | None = None,
) -> QualityResult:
    required_child = {child_key}
    if row_identifier is not None:
        required_child.add(row_identifier)

    missing_child = sorted(required_child - set(child.columns))
    missing_parent = sorted({parent_key} - set(parent.columns))

    if missing_child or missing_parent:
        missing = [
            *(f"{child_dataset}.{column}" for column in missing_child),
            *(f"parent.{column}" for column in missing_parent),
        ]
        return QualityResult(
            control_id=control_id,
            dataset=child_dataset,
            status="NOT_EVALUABLE",
            blocking=True,
            reason_code="MISSING_REFERENCE_PREREQUISITE",
            message=(
                "Reference integrity cannot be evaluated because required "
                "columns are missing: "
                + ", ".join(missing)
            ),
        )

    parent_values = set(
        parent[parent_key]
        .dropna()
        .astype("string")
        .str.strip()
        .loc[lambda series: series.ne("")]
        .tolist()
    )

    child_values = child[child_key].astype("string")
    null_or_blank = child_values.isna() | child_values.str.strip().eq("")

    if nullable:
        eligible = ~null_or_blank
    else:
        if null_or_blank.any():
            if row_identifier is not None:
                affected = tuple(
                    child.loc[null_or_blank, row_identifier]
                    .astype(str)
                    .tolist()
                )
            else:
                affected = tuple(
                    str(index)
                    for index in child.index[null_or_blank].tolist()
                )

            return QualityResult(
                control_id=control_id,
                dataset=child_dataset,
                status="FAIL",
                blocking=True,
                reason_code="NULL_REQUIRED_REFERENCE",
                message=(
                    f"Required reference {child_key} contains null or blank values."
                ),
                affected_ids=affected,
            )
        eligible = pd.Series(True, index=child.index)

    normalized_child = child_values.str.strip()
    missing_reference = eligible & ~normalized_child.isin(parent_values)

    if missing_reference.any():
        if row_identifier is not None:
            affected = tuple(
                child.loc[missing_reference, row_identifier]
                .astype(str)
                .tolist()
            )
        else:
            affected = tuple(
                str(value)
                for value in normalized_child.loc[missing_reference].tolist()
            )

        return QualityResult(
            control_id=control_id,
            dataset=child_dataset,
            status="FAIL",
            blocking=True,
            reason_code="MISSING_REFERENCE",
            message=(
                f"Values in {child_dataset}.{child_key} do not resolve to "
                f"{parent_key}."
            ),
            affected_ids=affected,
        )

    return QualityResult(
        control_id=control_id,
        dataset=child_dataset,
        status="PASS",
        blocking=False,
        reason_code=None,
        message=(
            f"Reference {child_dataset}.{child_key} resolves to {parent_key}."
        ),
    )


def validate_reference_integrity(
    reference: dict[str, pd.DataFrame],
    findings: pd.DataFrame,
    actions: pd.DataFrame,
) -> list[QualityResult]:
    required_tables = {
        "entities",
        "systems",
        "risk_taxonomy",
        "risk_assignments",
        "controls",
        "system_mappings",
        "third_parties",
        "system_third_parties",
    }
    missing_tables = sorted(required_tables - set(reference))

    if missing_tables:
        return [
            QualityResult(
                control_id="DQ_ASSURANCE_REFERENCE_MODEL",
                dataset="enterprise_reference",
                status="NOT_EVALUABLE",
                blocking=True,
                reason_code="MISSING_REFERENCE_PREREQUISITE",
                message=(
                    "Reference integrity cannot be evaluated because "
                    "required tables are missing: "
                    + ", ".join(missing_tables)
                ),
            )
        ]

    entities = reference["entities"]
    systems = reference["systems"]
    risk_taxonomy = reference["risk_taxonomy"]
    risk_assignments = reference["risk_assignments"]
    controls = reference["controls"]
    system_mappings = reference["system_mappings"]
    third_parties = reference["third_parties"]
    system_third_parties = reference["system_third_parties"]

    results = [
        _validate_reference(
            systems,
            entities,
            child_dataset="systems",
            child_key="entity_id",
            parent_key="entity_id",
            control_id="DQ_SYSTEM_ENTITY_REFERENCE",
            row_identifier="system_id",
        ),
        _validate_reference(
            risk_assignments,
            systems,
            child_dataset="risk_assignments",
            child_key="system_id",
            parent_key="system_id",
            control_id="DQ_RISK_ASSIGNMENT_SYSTEM_REFERENCE",
        ),
        _validate_reference(
            risk_assignments,
            risk_taxonomy,
            child_dataset="risk_assignments",
            child_key="risk_id",
            parent_key="risk_id",
            control_id="DQ_RISK_ASSIGNMENT_RISK_REFERENCE",
        ),
        _validate_reference(
            controls,
            risk_taxonomy,
            child_dataset="controls",
            child_key="risk_id",
            parent_key="risk_id",
            control_id="DQ_CONTROL_RISK_REFERENCE",
            row_identifier="control_id",
        ),
        _validate_reference(
            system_third_parties,
            systems,
            child_dataset="system_third_parties",
            child_key="system_id",
            parent_key="system_id",
            control_id="DQ_SYSTEM_THIRD_PARTY_SYSTEM_REFERENCE",
        ),
        _validate_reference(
            system_third_parties,
            third_parties,
            child_dataset="system_third_parties",
            child_key="third_party_id",
            parent_key="third_party_id",
            control_id="DQ_SYSTEM_THIRD_PARTY_REFERENCE",
        ),
        _validate_reference(
            findings,
            systems,
            child_dataset="findings",
            child_key="system_id",
            parent_key="system_id",
            control_id="DQ_FINDING_SYSTEM_REFERENCE",
            row_identifier="finding_id",
        ),
        _validate_reference(
            findings,
            controls,
            child_dataset="findings",
            child_key="control_id",
            parent_key="control_id",
            control_id="DQ_FINDING_CONTROL_REFERENCE",
            nullable=True,
            row_identifier="finding_id",
        ),
        _validate_reference(
            actions,
            findings,
            child_dataset="management_actions",
            child_key="finding_id",
            parent_key="finding_id",
            control_id="DQ_ACTION_FINDING_REFERENCE",
            row_identifier="action_id",
        ),
    ]

    mapping_required = {
        "raw_system_id",
        "canonical_system_id",
        "mapping_status",
    }
    missing_mapping_columns = sorted(
        mapping_required - set(system_mappings.columns)
    )

    if missing_mapping_columns:
        results.append(
            QualityResult(
                control_id="DQ_SYSTEM_MAPPING_CANONICAL_REFERENCE",
                dataset="system_mappings",
                status="NOT_EVALUABLE",
                blocking=True,
                reason_code="MISSING_REFERENCE_PREREQUISITE",
                message=(
                    "Canonical mapping integrity cannot be evaluated because "
                    "columns are missing: "
                    + ", ".join(missing_mapping_columns)
                ),
            )
        )
    else:
        mapped = system_mappings.loc[
            system_mappings["mapping_status"].eq("MAPPED")
        ].copy()

        results.append(
            _validate_reference(
                mapped,
                systems,
                child_dataset="system_mappings",
                child_key="canonical_system_id",
                parent_key="system_id",
                control_id="DQ_SYSTEM_MAPPING_CANONICAL_REFERENCE",
                row_identifier="raw_system_id",
            )
        )

    return results


def validate_effective_dated_reference_state(
    reference: dict[str, pd.DataFrame],
    *,
    as_of_date: str,
) -> list[QualityResult]:
    try:
        as_of = pd.Timestamp(as_of_date)
        if pd.isna(as_of):
            raise ValueError("Reporting as-of date is null.")
        as_of = as_of.normalize()
    except (TypeError, ValueError):
        return [
            QualityResult(
                control_id="DQ_REFERENCE_EFFECTIVE_DATE",
                dataset="enterprise_reference",
                status="NOT_EVALUABLE",
                blocking=True,
                reason_code="INVALID_AS_OF_DATE",
                message=f"Invalid reporting as-of date: {as_of_date}",
            )
        ]

    specs = {
        "entities": "entity_id",
        "systems": "system_id",
        "controls": "control_id",
    }

    results: list[QualityResult] = []

    for dataset, id_column in specs.items():
        if dataset not in reference:
            results.append(
                QualityResult(
                    control_id=f"DQ_{dataset.upper()}_EFFECTIVE_DATE",
                    dataset=dataset,
                    status="NOT_EVALUABLE",
                    blocking=True,
                    reason_code="MISSING_REFERENCE_PREREQUISITE",
                    message=f"Required effective-dated table is missing: {dataset}.",
                )
            )
            continue

        frame = reference[dataset]
        required = {id_column, "effective_from", "effective_to"}
        missing = sorted(required - set(frame.columns))

        if missing:
            results.append(
                QualityResult(
                    control_id=f"DQ_{dataset.upper()}_EFFECTIVE_DATE",
                    dataset=dataset,
                    status="NOT_EVALUABLE",
                    blocking=True,
                    reason_code="MISSING_REFERENCE_PREREQUISITE",
                    message=(
                        "Effective-date validation cannot be evaluated because "
                        "columns are missing: "
                        + ", ".join(missing)
                    ),
                )
            )
            continue

        effective_from = pd.to_datetime(
            frame["effective_from"],
            errors="coerce",
        ).dt.normalize()

        effective_to = pd.to_datetime(
            frame["effective_to"],
            errors="coerce",
        ).dt.normalize()

        invalid_from = effective_from.isna()
        invalid_to = (
            frame["effective_to"].notna()
            & frame["effective_to"].astype("string").str.strip().ne("")
            & effective_to.isna()
        )
        reversed_range = (
            effective_to.notna()
            & effective_from.notna()
            & effective_to.lt(effective_from)
        )

        invalid_date = invalid_from | invalid_to | reversed_range

        if invalid_date.any():
            affected = tuple(
                frame.loc[invalid_date, id_column]
                .astype(str)
                .tolist()
            )
            results.append(
                QualityResult(
                    control_id=f"DQ_{dataset.upper()}_EFFECTIVE_DATE",
                    dataset=dataset,
                    status="FAIL",
                    blocking=True,
                    reason_code="INVALID_EFFECTIVE_DATE",
                    message=(
                        "Reference rows contain invalid or reversed "
                        "effective-date ranges."
                    ),
                    affected_ids=affected,
                )
            )
            continue

        not_effective = effective_from.gt(as_of) | (
            effective_to.notna() & effective_to.lt(as_of)
        )

        if not_effective.any():
            affected = tuple(
                frame.loc[not_effective, id_column]
                .astype(str)
                .tolist()
            )
            results.append(
                QualityResult(
                    control_id=f"DQ_{dataset.upper()}_EFFECTIVE_DATE",
                    dataset=dataset,
                    status="FAIL",
                    blocking=True,
                    reason_code="REFERENCE_NOT_EFFECTIVE",
                    message=(
                        f"Reference rows are not effective on {as_of.date()}."
                    ),
                    affected_ids=affected,
                )
            )
            continue

        results.append(
            QualityResult(
                control_id=f"DQ_{dataset.upper()}_EFFECTIVE_DATE",
                dataset=dataset,
                status="PASS",
                blocking=False,
                reason_code=None,
                message=(
                    f"Reference rows are effective on {as_of.date()} "
                    "using inclusive effective_to semantics."
                ),
            )
        )

    return results


def assert_structurally_usable(
    results: list[QualityResult],
) -> None:
    blocking = [
        result
        for result in results
        if result.blocking and result.status in {"FAIL", "NOT_EVALUABLE"}
    ]

    if blocking:
        details = "; ".join(
            f"{result.control_id}={result.status}"
            for result in blocking
        )
        raise StructuralValidationError(
            f"Assurance structural validation blocked: {details}"
        )
