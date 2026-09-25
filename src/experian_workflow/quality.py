from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

from experian_workflow.ingestion import REQUIRED_EXPENSE_COLUMNS, REQUIRED_VENDOR_COLUMNS


class StructuralValidationError(ValueError):
    """Raised when required source/configuration structure is unsafe to process."""


def require_columns(frame: pd.DataFrame, required: Iterable[str], source_name: str) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise StructuralValidationError(f"{source_name} missing required columns: {missing}")


def validate_policy_structure(policy: dict[str, Any]) -> None:
    required_keys = ["as_of_date", "policy_version", "currency", "category_limits", "vendor_controls"]
    missing = [key for key in required_keys if key not in policy]
    if missing:
        raise StructuralValidationError(f"policy missing required keys: {missing}")
    if not isinstance(policy["category_limits"], dict) or not policy["category_limits"]:
        raise StructuralValidationError("policy category_limits must be a non-empty mapping")
    if not isinstance(policy["vendor_controls"], dict):
        raise StructuralValidationError("policy vendor_controls must be a mapping")


def validate_source_structure(expenses: pd.DataFrame, vendors: pd.DataFrame, policy: dict[str, Any]) -> None:
    require_columns(expenses, REQUIRED_EXPENSE_COLUMNS, "expenses")
    require_columns(vendors, REQUIRED_VENDOR_COLUMNS, "vendors")
    validate_policy_structure(policy)


def validate_records(expenses: pd.DataFrame, vendors: pd.DataFrame, policy: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = expenses.copy()
    reasons: list[list[str]] = [[] for _ in range(len(work))]
    control_ids: list[list[str]] = [[] for _ in range(len(work))]

    def fail(mask: pd.Series, control_id: str, reason: str) -> None:
        for position in mask[mask].index:
            row_position = work.index.get_loc(position)
            control_ids[row_position].append(control_id)
            reasons[row_position].append(reason)

    missing_id = work["transaction_id"].isna() | work["transaction_id"].fillna("").str.strip().eq("")
    fail(missing_id, "DQ002", "missing transaction_id")

    duplicate_id = work["transaction_id"].notna() & work["transaction_id"].duplicated(keep="first")
    fail(duplicate_id, "DQ003", "duplicate transaction_id")

    amount_numeric = pd.to_numeric(work["amount_minor"], errors="coerce")
    invalid_amount = amount_numeric.isna() | amount_numeric.le(0)
    fail(invalid_amount, "DQ004", "amount_minor must be a positive integer")

    parsed_dates = pd.to_datetime(work["transaction_date"], errors="coerce")
    as_of_date = pd.Timestamp(policy["as_of_date"])
    invalid_date = parsed_dates.isna() | parsed_dates.gt(as_of_date)
    fail(invalid_date, "DQ005", "transaction_date must be valid and not after as_of_date")

    known_vendors = set(vendors["vendor_id"].astype(str))
    unknown_vendor = ~work["vendor_id"].astype(str).isin(known_vendors)
    fail(unknown_vendor, "DQ006", "vendor_id must resolve to the vendor reference")

    quarantine_mask = pd.Series([bool(item) for item in reasons], index=work.index)
    quarantine = work.loc[quarantine_mask].copy()
    accepted = work.loc[~quarantine_mask].copy()

    quarantine["failed_control_ids"] = [";".join(control_ids[work.index.get_loc(index)]) for index in quarantine.index]
    quarantine["failure_reasons"] = [";".join(reasons[work.index.get_loc(index)]) for index in quarantine.index]

    return accepted.reset_index(drop=True), quarantine.reset_index(drop=True)
