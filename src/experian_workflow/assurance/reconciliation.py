from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REQUIRED_COLUMNS = [
    "test_id",
    "reporting_period",
    "expected_population",
    "received_population",
    "mapped_population",
    "tested_population",
]


class ReconciliationError(ValueError):
    pass


def load_reconciliation_contract(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)
    if not isinstance(contract, dict):
        raise ReconciliationError(f"Invalid reconciliation contract: {path}")
    if contract.get("schema_version") != "1.0":
        raise ReconciliationError("Unsupported reconciliation schema version.")
    model = contract.get("reconciliation_model")
    if not isinstance(model, dict):
        raise ReconciliationError("Missing reconciliation_model mapping.")
    stages = model.get("stages")
    if not isinstance(stages, dict):
        raise ReconciliationError("Missing reconciliation stages.")
    expected = {
        "expected": ("source_field", "expected_population"),
        "received": ("source_field", "received_population"),
        "mapped": ("source_field", "mapped_population"),
        "testable": ("derivation", "mapped_population"),
        "evaluated": ("source_field", "tested_population"),
    }
    for stage, (field, value) in expected.items():
        config = stages.get(stage)
        if not isinstance(config, dict) or config.get(field) != value:
            raise ReconciliationError(
                f"Unsupported reconciliation semantics for stage: {stage}"
            )
    structurally_valid = stages.get("structurally_valid")
    if (
        not isinstance(structurally_valid, dict)
        or structurally_valid.get("derivation")
        != "received_population when the control-evidence dataset structural contract passes"
        or structurally_valid.get("structural_failure_behavior")
        != "NOT_EVALUABLE"
    ):
        raise ReconciliationError(
            "Unsupported reconciliation semantics for stage: structurally_valid"
        )
    equations = model.get("equations")
    if not isinstance(equations, list) or len(equations) != 5:
        raise ReconciliationError("Reconciliation contract must define five stage equations.")
    return contract


def reconcile_control_evidence(
    frame: pd.DataFrame,
    contract: dict[str, Any],
    *,
    structural_contract_status: str,
) -> pd.DataFrame:
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ReconciliationError(
            "Missing reconciliation prerequisites: " + ", ".join(missing)
        )
    model = contract.get("reconciliation_model")
    if not isinstance(model, dict):
        raise ReconciliationError("Invalid reconciliation contract.")
    stages = model.get("stages")
    if not isinstance(stages, dict):
        raise ReconciliationError("Invalid reconciliation stages.")

    result = frame.copy()
    derived = [
        "structurally_valid_population",
        "structurally_rejected_population",
        "unmapped_population",
        "testable_population",
        "not_testable_population",
        "evaluated_population",
        "not_tested_population",
        "not_received_population",
    ]

    if structural_contract_status != "PASS":
        for column in derived:
            result[column] = pd.NA
        result["reconciliation_status"] = "NOT_EVALUABLE"
        result["reconciliation_reason_code"] = "STRUCTURAL_CONTRACT_FAILURE"
        return result

    source_population = REQUIRED_COLUMNS[2:]
    numeric = result[source_population].apply(pd.to_numeric, errors="coerce")
    invalid_numeric = numeric.isna().any(axis=1)
    if invalid_numeric.any():
        ids = result.loc[invalid_numeric, "test_id"].astype(str).tolist()
        raise ReconciliationError(
            "Non-numeric population values for test IDs: " + ", ".join(ids)
        )
    result[source_population] = numeric

    result["structurally_valid_population"] = result["received_population"]
    result["structurally_rejected_population"] = 0
    result["testable_population"] = result["mapped_population"]
    result["not_testable_population"] = 0
    result["evaluated_population"] = result["tested_population"]

    result["not_received_population"] = (
        result["expected_population"] - result["received_population"]
    )
    result["unmapped_population"] = (
        result["structurally_valid_population"] - result["mapped_population"]
    )
    result["not_tested_population"] = (
        result["testable_population"] - result["evaluated_population"]
    )

    invalid_order = (
        (result["received_population"] > result["expected_population"])
        | (
            result["mapped_population"]
            > result["structurally_valid_population"]
        )
        | (
            result["testable_population"]
            > result["mapped_population"]
        )
        | (
            result["evaluated_population"]
            > result["testable_population"]
        )
    )

    population_columns = REQUIRED_COLUMNS[2:] + derived
    negative = (result[population_columns] < 0).any(axis=1)

    equation_balance = (
        result["expected_population"]
        == result["received_population"] + result["not_received_population"]
    ) & (
        result["received_population"]
        == result["structurally_valid_population"]
        + result["structurally_rejected_population"]
    ) & (
        result["structurally_valid_population"]
        == result["mapped_population"] + result["unmapped_population"]
    ) & (
        result["mapped_population"]
        == result["testable_population"] + result["not_testable_population"]
    ) & (
        result["testable_population"]
        == result["evaluated_population"] + result["not_tested_population"]
    )

    result["reconciliation_status"] = "PASS"
    result["reconciliation_reason_code"] = pd.NA

    invalid_stage = negative | invalid_order
    result.loc[invalid_stage, "reconciliation_status"] = "FAIL"
    result.loc[
        invalid_stage,
        "reconciliation_reason_code",
    ] = "INVALID_STAGE_ORDER"

    imbalance = ~equation_balance & ~invalid_stage
    result.loc[imbalance, "reconciliation_status"] = "FAIL"
    result.loc[
        imbalance,
        "reconciliation_reason_code",
    ] = "UNEXPLAINED_POPULATION_IMBALANCE"

    return result


def summarize_reconciliation(frame: pd.DataFrame) -> dict[str, int | str]:
    if frame["reconciliation_status"].eq("NOT_EVALUABLE").any():
        return {"status": "NOT_EVALUABLE", "record_count": len(frame)}
    status = "FAIL" if frame["reconciliation_status"].eq("FAIL").any() else "PASS"
    population_columns = [
        "expected_population",
        "received_population",
        "not_received_population",
        "structurally_valid_population",
        "structurally_rejected_population",
        "mapped_population",
        "unmapped_population",
        "testable_population",
        "not_testable_population",
        "evaluated_population",
        "not_tested_population",
    ]
    summary: dict[str, int | str] = {
        "status": status,
        "record_count": len(frame),
    }
    for column in population_columns:
        summary[column] = int(frame[column].sum())
    return summary
