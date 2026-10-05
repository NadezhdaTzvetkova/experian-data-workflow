from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from experian_workflow.assurance.publication import TABLE_CONTRACTS
from experian_workflow.assurance.tableau import (
    BOOLEAN_COLUMNS,
    DATE_COLUMNS,
    DOUBLE_COLUMNS,
    INTEGER_COLUMNS,
    TABLEAU_METRICS_TABLE,
)


def _hyper_type_name(column: str) -> str:
    if column in DATE_COLUMNS:
        return "DATE"
    if column in BOOLEAN_COLUMNS:
        return "BOOLEAN"
    if column in INTEGER_COLUMNS:
        return "BIG_INT"
    if column in DOUBLE_COLUMNS:
        return "DOUBLE"
    return "TEXT"


def write_tableau_data_dictionary(
    *,
    run_dir: Path,
) -> dict[str, object]:
    publication_dir = run_dir / "publication"
    tables_dir = publication_dir / "tables"
    tableau_dir = publication_dir / "tableau"
    tableau_dir.mkdir(parents=True, exist_ok=True)
    output_path = tableau_dir / "tableau_data_dictionary.csv"

    rows: list[dict[str, object]] = []
    for name, contract in TABLE_CONTRACTS.items():
        source_path = tables_dir / f"{name}.csv"
        if not source_path.exists():
            raise RuntimeError(
                f"Missing governed publication table for Tableau dictionary: {source_path}"
            )
        frame = pd.read_csv(
            source_path,
            dtype=str,
            keep_default_na=False,
            nrows=0,
        )
        for column in frame.columns:
            rows.append(
                {
                    "dataset_id": contract.dataset_id,
                    "grain": contract.grain,
                    "source_artifact": source_path.relative_to(run_dir).as_posix(),
                    "field_name": column,
                    "hyper_type": _hyper_type_name(column),
                    "is_business_key": column in contract.key,
                    "nullable_key": column in contract.nullable_key_fields,
                }
            )

    metric_fields = [
        ("metric_id", "TEXT"),
        ("display_name", "TEXT"),
        ("value", "DOUBLE"),
        ("unit", "TEXT"),
        ("business_question", "TEXT"),
        ("limitation", "TEXT"),
        ("methodology_version", "TEXT"),
        ("publication_run_id", "TEXT"),
        ("publication_as_of_date", "DATE"),
        ("validation_status", "TEXT"),
    ]
    for field_name, hyper_type in metric_fields:
        rows.append(
            {
                "dataset_id": TABLEAU_METRICS_TABLE,
                "grain": "one governed published metric",
                "source_artifact": "publication/metrics.json",
                "field_name": field_name,
                "hyper_type": hyper_type,
                "is_business_key": field_name == "metric_id",
                "nullable_key": False,
            }
        )

    fieldnames = [
        "dataset_id",
        "grain",
        "source_artifact",
        "field_name",
        "hyper_type",
        "is_business_key",
        "nullable_key",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "status": "PASS",
        "path": output_path,
        "row_count": len(rows),
        "dataset_count": len(TABLE_CONTRACTS) + 1,
    }
