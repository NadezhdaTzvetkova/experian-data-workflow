from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REQUIRED_EXPENSE_COLUMNS = [
    "transaction_id",
    "employee_id",
    "vendor_id",
    "transaction_date",
    "category",
    "currency",
    "amount_minor",
    "cost_center",
    "receipt_present",
]

REQUIRED_VENDOR_COLUMNS = [
    "vendor_id",
    "vendor_name",
    "risk_rating",
    "active_flag",
    "effective_from",
    "effective_to",
]


def load_policy(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    if not isinstance(policy, dict):
        raise ValueError(f"Policy must deserialize to a mapping: {path}")
    return policy


def load_expenses(path: Path | str) -> pd.DataFrame:
    path = Path(path)
    return pd.read_csv(path, dtype={"transaction_id": "string", "employee_id": "string", "vendor_id": "string", "category": "string", "currency": "string", "cost_center": "string"})


def load_vendors(path: Path | str) -> pd.DataFrame:
    path = Path(path)
    with sqlite3.connect(path) as connection:
        return pd.read_sql_query("SELECT vendor_id, vendor_name, risk_rating, active_flag, effective_from, effective_to FROM vendors ORDER BY vendor_id", connection)
