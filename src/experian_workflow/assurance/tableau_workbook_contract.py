from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


def validate_tableau_workbook_contract(
    *,
    contract_path: Path,
    dictionary_path: Path,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    dictionary = pd.read_csv(
        dictionary_path,
        dtype=str,
        keep_default_na=False,
    )

    if contract.get("schema_version") != "1.0":
        raise RuntimeError("Unsupported Tableau workbook contract schema_version")
    if contract.get("workbook_id") != "assurance_dashboard":
        raise RuntimeError("Unexpected Tableau workbook_id")

    dashboards = contract.get("dashboards")
    if not isinstance(dashboards, list) or not dashboards:
        raise RuntimeError("Tableau workbook contract must define dashboards")

    available: dict[str, set[str]] = {}
    for dataset_id, group in dictionary.groupby("dataset_id", sort=False):
        available[str(dataset_id)] = set(group["field_name"].astype(str))

    dashboard_ids: set[str] = set()
    worksheet_ids: set[str] = set()
    referenced_datasets: set[str] = set()

    for dashboard in dashboards:
        dashboard_id = str(dashboard.get("id", "")).strip()
        if not dashboard_id:
            raise RuntimeError("Dashboard id must not be empty")
        if dashboard_id in dashboard_ids:
            raise RuntimeError(f"Duplicate dashboard id: {dashboard_id}")
        dashboard_ids.add(dashboard_id)

        worksheets = dashboard.get("worksheets")
        if not isinstance(worksheets, list) or not worksheets:
            raise RuntimeError(f"Dashboard {dashboard_id} has no worksheets")

        for worksheet in worksheets:
            worksheet_id = str(worksheet.get("id", "")).strip()
            dataset_id = str(worksheet.get("dataset", "")).strip()
            fields = worksheet.get("fields")

            if not worksheet_id:
                raise RuntimeError(f"Worksheet id missing in {dashboard_id}")
            if worksheet_id in worksheet_ids:
                raise RuntimeError(f"Duplicate worksheet id: {worksheet_id}")
            worksheet_ids.add(worksheet_id)

            if dataset_id not in available:
                raise RuntimeError(
                    f"Unknown governed dataset: {dataset_id}"
                )
            referenced_datasets.add(dataset_id)

            if not isinstance(fields, list) or not fields:
                raise RuntimeError(f"Worksheet {worksheet_id} has no fields")
            if len(fields) != len(set(fields)):
                raise RuntimeError(
                    f"Worksheet {worksheet_id} contains duplicate fields"
                )

            missing = sorted(set(fields) - available[dataset_id])
            if missing:
                raise RuntimeError(
                    f"Worksheet {worksheet_id} references missing fields: {missing}"
                )

            visual = worksheet.get("visual")
            if not isinstance(visual, dict):
                raise TypeError(f"Worksheet {worksheet_id} has no visual contract")
            if visual.get("view_type") not in {"kpi_text", "bar", "table"}:
                raise RuntimeError(f"Worksheet {worksheet_id} has unsupported view_type")
            if visual.get("mark") not in {"text", "bar"}:
                raise RuntimeError(f"Worksheet {worksheet_id} has unsupported mark")
            for channel in ("rows", "columns", "label", "color", "filters"):
                references = visual.get(channel)
                if not isinstance(references, list):
                    raise TypeError(
                        f"Worksheet {worksheet_id} visual channel {channel} must be a list"
                    )
                for reference in references:
                    reference_text = str(reference)
                    aggregate = re.fullmatch(r"COUNT\(([^)]+)\)", reference_text)
                    field_name = aggregate.group(1) if aggregate else reference_text
                    if field_name not in available[dataset_id]:
                        raise RuntimeError(
                            f"Worksheet {worksheet_id} visual channel {channel} "
                            f"references missing field: {field_name}"
                        )

    return {
        "status": "PASS",
        "schema_version": str(contract["schema_version"]),
        "workbook_id": str(contract["workbook_id"]),
        "dashboard_count": len(dashboard_ids),
        "worksheet_count": len(worksheet_ids),
        "referenced_dataset_count": len(referenced_datasets),
        "dashboard_ids": sorted(dashboard_ids),
        "worksheet_ids": sorted(worksheet_ids),
        "referenced_datasets": sorted(referenced_datasets),
    }
