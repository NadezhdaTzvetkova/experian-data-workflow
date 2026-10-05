from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


class MetricContractError(ValueError):
    pass


def load_metric_contract(path: Path | str) -> dict[str, Any]:
    path = Path(path)

    with path.open(encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)

    if not isinstance(contract, dict):
        raise MetricContractError(f"Invalid metric contract: {path}")

    if contract.get("schema_version") != "1.0":
        raise MetricContractError("Unsupported metric-contract schema version.")

    methodology = contract.get("methodology")
    metrics = contract.get("metrics")

    if not isinstance(methodology, dict):
        raise MetricContractError("Missing metric-contract methodology.")

    if not isinstance(metrics, dict) or not metrics:
        raise MetricContractError("Missing governed metric definitions.")

    return contract


def evaluate_metric_contract(
    contract: dict[str, Any],
    populations: dict[str, pd.DataFrame],
) -> dict[str, int]:
    metrics = contract.get("metrics")

    if not isinstance(metrics, dict):
        raise MetricContractError("Missing governed metric definitions.")

    results: dict[str, int] = {}

    for metric_name, definition in metrics.items():
        if not isinstance(definition, dict):
            raise MetricContractError(
                f"Invalid metric definition: {metric_name}"
            )

        calculation = definition.get("calculation")
        if not isinstance(calculation, dict):
            raise MetricContractError(
                f"Missing calculation specification: {metric_name}"
            )

        population_name = calculation.get("population")
        if population_name not in populations:
            raise MetricContractError(
                f"Unknown metric population for {metric_name}: "
                f"{population_name}"
            )

        if calculation.get("aggregation") != "count":
            raise MetricContractError(
                f"Unsupported aggregation for {metric_name}: "
                f"{calculation.get('aggregation')}"
            )

        frame = populations[str(population_name)]
        operator = calculation.get("operator")

        if operator == "all":
            results[str(metric_name)] = len(frame)
            continue

        field = calculation.get("field")
        if not isinstance(field, str) or field not in frame.columns:
            raise MetricContractError(
                f"Missing metric field for {metric_name}: {field}"
            )

        if operator == "eq":
            if "value" not in calculation:
                raise MetricContractError(
                    f"Missing comparison value for {metric_name}"
                )
            mask = frame[field].eq(calculation["value"])

        elif operator == "in":
            values = calculation.get("values")
            if not isinstance(values, list) or not values:
                raise MetricContractError(
                    f"Missing comparison values for {metric_name}"
                )
            mask = frame[field].isin(values)

        else:
            raise MetricContractError(
                f"Unsupported metric operator for {metric_name}: "
                f"{operator}"
            )

        results[str(metric_name)] = int(mask.fillna(False).sum())

    return results
