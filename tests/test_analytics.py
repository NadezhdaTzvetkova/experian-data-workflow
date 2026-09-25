from pathlib import Path

import pandas as pd

from experian_workflow.analytics import verify_headline_kpis


def test_headline_kpi_reconciliation_detects_mismatch(tmp_path: Path):
    curated_path = tmp_path / "curated.parquet"
    curated = pd.DataFrame(
        {
            "amount_minor": [100, 200],
            "policy_exception": [True, False],
            "high_risk_vendor": [False, True],
            "inactive_vendor": [False, False],
            "audit_exception": [True, True],
        }
    )
    curated.to_parquet(curated_path, index=False)

    corrupted_mart = pd.DataFrame(
        {
            "transaction_count": [2],
            "spend_minor": [300],
            "policy_exception_count": [1],
            "high_risk_vendor_count": [1],
            "inactive_vendor_count": [0],
            "audit_exception_count": [1],
        }
    )

    result = verify_headline_kpis(curated_path, corrupted_mart)

    assert result["match"] is False
    assert result["python_totals"]["audit_exception_count"] == 2
    assert result["sql_totals"]["audit_exception_count"] == 1
