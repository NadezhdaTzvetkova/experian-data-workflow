from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from tableauhyperapi import (
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
)

from experian_workflow.assurance.publication import TABLE_CONTRACTS

TABLEAU_SCHEMA = "Extract"
TABLEAU_METRICS_TABLE = "governed_metrics"

DATE_COLUMNS = {
    "evidence_date",
    "identified_date",
    "closed_date",
    "closed_date_x",
    "closed_date_y",
    "target_date",
    "publication_as_of_date",
}
BOOLEAN_COLUMNS = {
    "contains_sensitive_data",
    "third_party_dependency_flag",
    "repeat_finding",
    "overdue",
}
INTEGER_COLUMNS = {
    "expected_population",
    "received_population",
    "mapped_population",
    "tested_population",
    "exception_count",
    "structurally_valid_population",
    "structurally_rejected_population",
    "testable_population",
    "not_testable_population",
    "evaluated_population",
    "not_received_population",
    "unmapped_population",
    "not_tested_population",
    "evidence_age_days",
    "assurance_tests",
    "sufficient_evidence",
    "weak_evidence",
    "stale_evidence",
    "high_or_critical_residual_risk",
    "not_evaluable_residual_risk",
    "row_count",
    "days_overdue",
}
DOUBLE_COLUMNS = {"coverage_ratio"}


def _sql_type(column: str) -> SqlType:
    if column in DATE_COLUMNS:
        return SqlType.date()
    if column in BOOLEAN_COLUMNS:
        return SqlType.bool()
    if column in INTEGER_COLUMNS:
        return SqlType.big_int()
    if column in DOUBLE_COLUMNS:
        return SqlType.double()
    return SqlType.text()


def _parse_bool(value: str) -> bool | None:
    if value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "1.0"}:
        return True
    if normalized in {"false", "0", "0.0"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _convert_value(column: str, value: str) -> Any:
    if value == "":
        return None
    if column in DATE_COLUMNS:
        return date.fromisoformat(value)
    if column in BOOLEAN_COLUMNS:
        return _parse_bool(value)
    if column in INTEGER_COLUMNS:
        return int(float(value))
    if column in DOUBLE_COLUMNS:
        return float(value)
    return value


def _normalize_hyper_value(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column in DATE_COLUMNS:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))
    return value


def _load_publication_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _table_definition(name: str, columns: list[str]) -> TableDefinition:
    return TableDefinition(
        table_name=TableName(TABLEAU_SCHEMA, name),
        columns=[
            TableDefinition.Column(column, _sql_type(column))
            for column in columns
        ],
    )


def _metric_rows(
    *,
    metrics_path: Path,
    metrics_config_path: Path,
) -> list[dict[str, Any]]:
    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    config = yaml.safe_load(metrics_config_path.read_text(encoding="utf-8"))
    metric_contracts = config["metrics"]

    published_metrics = metrics_payload["metrics"]
    if set(published_metrics) != set(metric_contracts):
        raise RuntimeError(
            "Published metric keys do not match the governed metric contract"
        )

    rows: list[dict[str, Any]] = []
    for metric_id in sorted(published_metrics):
        contract = metric_contracts[metric_id]
        rows.append(
            {
                "metric_id": metric_id,
                "display_name": metric_id,
                "value": float(published_metrics[metric_id]),
                "unit": str(contract["units"]),
                "business_question": str(contract["business_question"]),
                "limitation": str(contract["limitation"]),
                "methodology_version": str(
                    metrics_payload["methodology_version"]
                ),
                "publication_run_id": str(metrics_payload["run_id"]),
                "publication_as_of_date": date.fromisoformat(
                    str(metrics_payload["as_of_date"])
                ),
                "validation_status": str(
                    metrics_payload["validation_status"]
                ),
            }
        )
    return rows


def _metric_definition() -> TableDefinition:
    return TableDefinition(
        table_name=TableName(TABLEAU_SCHEMA, TABLEAU_METRICS_TABLE),
        columns=[
            TableDefinition.Column("metric_id", SqlType.text()),
            TableDefinition.Column("display_name", SqlType.text()),
            TableDefinition.Column("value", SqlType.double()),
            TableDefinition.Column("unit", SqlType.text()),
            TableDefinition.Column("business_question", SqlType.text()),
            TableDefinition.Column("limitation", SqlType.text()),
            TableDefinition.Column(
                "methodology_version",
                SqlType.text(),
            ),
            TableDefinition.Column("publication_run_id", SqlType.text()),
            TableDefinition.Column(
                "publication_as_of_date",
                SqlType.date(),
            ),
            TableDefinition.Column("validation_status", SqlType.text()),
        ],
    )


def build_tableau_hyper(
    *,
    run_dir: Path,
    project_root: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    publication_dir = run_dir / "publication"
    tables_dir = publication_dir / "tables"
    metrics_path = publication_dir / "metrics.json"
    metrics_config_path = project_root / "config" / "assurance" / "metrics.yaml"

    if output_path is None:
        output_path = publication_dir / "tableau" / "assurance_dashboard.hyper"
    if output_path.exists():
        raise RuntimeError(f"Tableau Hyper output already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tables: dict[str, pd.DataFrame] = {}
    for name in TABLE_CONTRACTS:
        path = tables_dir / f"{name}.csv"
        if not path.exists():
            raise RuntimeError(f"Missing governed publication table: {path}")
        tables[name] = _load_publication_table(path)

    metric_rows = _metric_rows(
        metrics_path=metrics_path,
        metrics_config_path=metrics_config_path,
    )

    with HyperProcess(
        Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU
    ) as hyper, Connection(
        endpoint=hyper.endpoint,
        database=output_path,
        create_mode=CreateMode.CREATE_AND_REPLACE,
    ) as connection:
        connection.catalog.create_schema(TABLEAU_SCHEMA)

        for name, frame in tables.items():
            definition = _table_definition(
                name,
                list(frame.columns),
            )
            connection.catalog.create_table(definition)
            rows = [
                [
                    _convert_value(column, value)
                    for column, value in zip(
                        frame.columns,
                        row,
                        strict=True,
                    )
                ]
                for row in frame.itertuples(index=False, name=None)
            ]
            with Inserter(connection, definition) as inserter:
                inserter.add_rows(rows)
                inserter.execute()

        metric_definition = _metric_definition()
        connection.catalog.create_table(metric_definition)
        metric_columns = [
            "metric_id",
            "display_name",
            "value",
            "unit",
            "business_question",
            "limitation",
            "methodology_version",
            "publication_run_id",
            "publication_as_of_date",
            "validation_status",
        ]
        with Inserter(connection, metric_definition) as inserter:
            inserter.add_rows(
                [
                    [row[column] for column in metric_columns]
                    for row in metric_rows
                ]
            )
            inserter.execute()

    return validate_tableau_hyper(
        hyper_path=output_path,
        source_tables=tables,
        metric_rows=metric_rows,
    )


def validate_tableau_hyper(
    *,
    hyper_path: Path,
    source_tables: dict[str, pd.DataFrame],
    metric_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_tables = set(TABLE_CONTRACTS) | {TABLEAU_METRICS_TABLE}
    table_results: dict[str, dict[str, Any]] = {}

    with HyperProcess(
        Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU
    ) as hyper, Connection(
        endpoint=hyper.endpoint,
        database=hyper_path,
        create_mode=CreateMode.NONE,
    ) as connection:
        for table_name in expected_tables:
            if not connection.catalog.has_table(
                TableName(TABLEAU_SCHEMA, table_name)
            ):
                raise RuntimeError(f"Missing Hyper table: {table_name}")

        for name, frame in source_tables.items():
            table_ref = f'"{TABLEAU_SCHEMA}"."{name}"'
            row_count = int(
                connection.execute_scalar_query(
                    f"SELECT COUNT(*) FROM {table_ref}"
                )
            )
            if row_count != len(frame):
                raise RuntimeError(
                    f"Hyper row count mismatch for {name}: "
                    f"{row_count} != {len(frame)}"
                )

            contract = TABLE_CONTRACTS[name]
            key_expr = ", ".join(
                f'"{column}"' for column in contract.key
            )
            duplicate_count = int(
                connection.execute_scalar_query(
                    "SELECT COUNT(*) FROM ("
                    f"SELECT {key_expr}, COUNT(*) AS n "
                    f"FROM {table_ref} "
                    f"GROUP BY {key_expr} HAVING COUNT(*) > 1"
                    ") duplicates"
                )
            )
            if duplicate_count:
                raise RuntimeError(
                    f"Hyper key uniqueness failed for {name}"
                )

            source_run_ids = set(
                frame["publication_run_id"].astype(str)
            )
            hyper_run_ids = {
                str(row[0])
                for row in connection.execute_list_query(
                    "SELECT DISTINCT publication_run_id "
                    f"FROM {table_ref}"
                )
            }
            if hyper_run_ids != source_run_ids:
                raise RuntimeError(
                    f"Hyper run identity mismatch for {name}"
                )

            column_names = list(frame.columns)
            select_columns = ", ".join(f'"{column}"' for column in column_names)
            actual_rows = [
                tuple(
                    _normalize_hyper_value(column, value)
                    for column, value in zip(column_names, row, strict=True)
                )
                for row in connection.execute_list_query(
                    f"SELECT {select_columns} FROM {table_ref}"
                )
            ]
            expected_rows = [
                tuple(
                    _convert_value(column, value)
                    for column, value in zip(column_names, row, strict=True)
                )
                for row in frame.itertuples(index=False, name=None)
            ]
            key_positions = [column_names.index(column) for column in contract.key]
            actual_by_key = {
                tuple(row[index] for index in key_positions): row for row in actual_rows
            }
            expected_by_key = {
                tuple(row[index] for index in key_positions): row for row in expected_rows
            }
            if actual_by_key != expected_by_key:
                actual_keys = set(actual_by_key)
                expected_keys = set(expected_by_key)
                missing_keys = sorted(
                    repr(value) for value in expected_keys - actual_keys
                )
                unexpected_keys = sorted(
                    repr(value) for value in actual_keys - expected_keys
                )
                changed_keys = sorted(
                    repr(value)
                    for value in actual_keys & expected_keys
                    if actual_by_key[value] != expected_by_key[value]
                )
                raise RuntimeError(
                    f"Hyper full-content mismatch for {name}; "
                    f"missing_keys={missing_keys}, "
                    f"unexpected_keys={unexpected_keys}, "
                    f"changed_keys={changed_keys}"
                )

            table_results[name] = {
                "status": "PASS",
                "row_count": row_count,
                "key": list(contract.key),
                "run_identity_match": True,
                "full_content_match": True,
            }

        metric_ref = (
            f'"{TABLEAU_SCHEMA}"."{TABLEAU_METRICS_TABLE}"'
        )
        hyper_metrics = connection.execute_list_query(
            "SELECT metric_id, value, unit, methodology_version, "
            "publication_run_id, validation_status "
            f"FROM {metric_ref} ORDER BY metric_id"
        )
        expected_metrics = [
            [
                row["metric_id"],
                row["value"],
                row["unit"],
                row["methodology_version"],
                row["publication_run_id"],
                row["validation_status"],
            ]
            for row in metric_rows
        ]
        if [list(row) for row in hyper_metrics] != expected_metrics:
            raise RuntimeError(
                "Hyper governed metric rows differ from metrics.json"
            )

    return {
        "status": "PASS",
        "hyper_path": str(hyper_path),
        "tables": table_results,
        "governed_metrics": {
            "status": "PASS",
            "row_count": len(metric_rows),
            "exact_match": True,
        },
        "acceptance_model": "PROGRAMMATIC_TABLEAU",
    }
