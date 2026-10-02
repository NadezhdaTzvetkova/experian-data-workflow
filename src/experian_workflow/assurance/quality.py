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

    null_key_mask = frame[key_columns].isna().any(axis=1)
    if null_key_mask.any():
        affected = tuple(
            str(index)
            for index in frame.index[null_key_mask].tolist()
        )
        return QualityResult(
            control_id=control_id,
            dataset=dataset,
            status="FAIL",
            blocking=True,
            reason_code="NULL_REQUIRED_KEY",
            message="Required key contains null values.",
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
