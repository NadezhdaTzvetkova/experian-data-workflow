from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pandas as pd

SQLITE_TABLE_COLUMNS: dict[str, list[str]] = {
    "entities": [
        "entity_id",
        "entity_name",
        "region",
        "country",
        "business_unit",
        "acquired_status",
        "acquisition_cohort",
        "effective_from",
        "effective_to",
    ],
    "systems": [
        "system_id",
        "entity_id",
        "system_name",
        "system_owner",
        "criticality",
        "data_classification",
        "contains_sensitive_data",
        "core_acquired_status",
        "acquisition_cohort",
        "third_party_dependency_flag",
        "effective_from",
        "effective_to",
    ],
    "risk_taxonomy": [
        "risk_id",
        "risk_domain",
        "risk_name",
        "risk_description",
    ],
    "risk_assignments": [
        "system_id",
        "risk_id",
        "reporting_period",
        "inherent_risk",
    ],
    "controls": [
        "control_id",
        "risk_id",
        "control_name",
        "control_objective",
        "control_type",
        "expected_frequency",
        "expected_evidence_type",
        "effective_from",
        "effective_to",
    ],
    "source_registry": [
        "source_id",
        "source_name",
        "source_type",
        "source_owner",
        "expected_grain",
        "expected_frequency",
        "schema_version",
        "classification",
        "known_limitation",
    ],
    "source_expectations": [
        "source_id",
        "reporting_period",
        "expected_record_count",
    ],
    "system_mappings": [
        "source_system",
        "raw_system_id",
        "canonical_system_id",
        "mapping_status",
    ],
    "third_parties": [
        "third_party_id",
        "third_party_name",
        "tier",
        "sensitive_access_flag",
        "assurance_status",
        "last_assurance_date",
    ],
    "system_third_parties": [
        "system_id",
        "third_party_id",
    ],
}

CONTROL_EVIDENCE_COLUMNS = [
    "test_id",
    "scenario_id",
    "raw_system_id",
    "control_id",
    "reporting_period",
    "expected_population",
    "received_population",
    "mapped_population",
    "tested_population",
    "exception_count",
    "source_result",
    "evidence_id",
    "evidence_date",
]

FINDING_COLUMNS = [
    "finding_id",
    "scenario_id",
    "system_id",
    "control_id",
    "recurrence_key",
    "finding_theme",
    "severity",
    "identified_date",
    "status",
    "closed_date",
]

MANAGEMENT_ACTION_COLUMNS = [
    "action_id",
    "scenario_id",
    "finding_id",
    "action_owner",
    "target_date",
    "status",
    "closed_date",
    "closure_validation_status",
]


def _ordered_select(table: str, columns: list[str]) -> str:
    selected = ", ".join(f'"{column}"' for column in columns)
    return f'SELECT {selected} FROM "{table}"'


def load_enterprise_reference(
    path: Path | str,
) -> dict[str, pd.DataFrame]:
    path = Path(path)
    tables: dict[str, pd.DataFrame] = {}

    with closing(sqlite3.connect(path)) as connection:
        for table, columns in SQLITE_TABLE_COLUMNS.items():
            tables[table] = pd.read_sql_query(
                _ordered_select(table, columns),
                connection,
            )

    return tables


def load_control_evidence(
    path: Path | str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    path = Path(path)

    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise TypeError(
            f"Control evidence must deserialize to a mapping: {path}"
        )

    records = payload.get("records")
    if not isinstance(records, list):
        raise TypeError(
            f"Control evidence records must deserialize to a list: {path}"
        )

    frame = pd.DataFrame.from_records(records)

    return payload, frame


def load_findings(path: Path | str) -> pd.DataFrame:
    path = Path(path)

    return pd.read_csv(
        path,
        dtype={
            "finding_id": "string",
            "scenario_id": "string",
            "system_id": "string",
            "control_id": "string",
            "recurrence_key": "string",
            "finding_theme": "string",
            "severity": "string",
            "identified_date": "string",
            "status": "string",
            "closed_date": "string",
        },
        keep_default_na=False,
    )


def load_management_actions(path: Path | str) -> pd.DataFrame:
    path = Path(path)

    return pd.read_csv(
        path,
        dtype={
            "action_id": "string",
            "scenario_id": "string",
            "finding_id": "string",
            "action_owner": "string",
            "target_date": "string",
            "status": "string",
            "closed_date": "string",
            "closure_validation_status": "string",
        },
        keep_default_na=False,
    )
