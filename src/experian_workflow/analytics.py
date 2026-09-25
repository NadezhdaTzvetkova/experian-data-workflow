from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def build_audit_summary(curated_path: Path | str, sql_path: Path | str) -> pd.DataFrame:
    curated_path = Path(curated_path).resolve()
    sql_path = Path(sql_path)
    sql = sql_path.read_text(encoding="utf-8")
    with duckdb.connect() as connection:
        return connection.execute(sql, [str(curated_path)]).df()


def verify_headline_kpis(curated_path: Path | str, mart: pd.DataFrame) -> dict[str, object]:
    curated = pd.read_parquet(curated_path)
    python_totals = {
        "transaction_count": len(curated),
        "spend_minor": int(curated["amount_minor"].sum()),
        "policy_exception_count": int(curated["policy_exception"].sum()),
        "high_risk_vendor_count": int(curated["high_risk_vendor"].sum()),
        "inactive_vendor_count": int(curated["inactive_vendor"].sum()),
        "audit_exception_count": int(curated["audit_exception"].sum()),
    }
    sql_totals = {
        "transaction_count": int(mart["transaction_count"].sum()),
        "spend_minor": int(mart["spend_minor"].sum()),
        "policy_exception_count": int(mart["policy_exception_count"].sum()),
        "high_risk_vendor_count": int(mart["high_risk_vendor_count"].sum()),
        "inactive_vendor_count": int(mart["inactive_vendor_count"].sum()),
        "audit_exception_count": int(mart["audit_exception_count"].sum()),
    }
    return {
        "python_totals": python_totals,
        "sql_totals": sql_totals,
        "match": python_totals == sql_totals,
    }
