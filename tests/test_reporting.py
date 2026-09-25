import json
from pathlib import Path

import pandas as pd

from experian_workflow.reporting import build_audit_report


def test_audit_report_is_self_contained_and_audit_facing(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    manifest = {
        "run_id": "test-run",
        "policy_version": "test-policy",
        "status": "SUCCESS_WITH_QUARANTINE",
        "counts": {"source": 4, "accepted": 4, "quarantined": 0, "curated": 4},
        "analytics_validation": {"match": True},
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8", newline="\n"
    )

    curated = pd.DataFrame(
        {
            "transaction_id": ["T1", "T2", "T3", "T4"],
            "vendor_id": ["V1", "V2", "V1", "V3"],
            "vendor_name": ["Vendor 1", "Vendor 2", "Vendor 1", "Vendor 3"],
            "cost_center": ["CC1", "CC1", "CC2", "CC2"],
            "amount_minor": [12000, 5000, 8000, 3000],
            "policy_exception": [True, False, False, False],
            "high_risk_vendor": [False, True, False, False],
            "inactive_vendor": [False, False, True, False],
            "audit_exception": [True, True, True, False],
        }
    )
    curated.to_parquet(run_dir / "curated_expenses.parquet", index=False)

    summary = pd.DataFrame(
        {
            "category": ["meals", "travel"],
            "transaction_count": [2, 2],
            "spend_minor": [17000, 11000],
            "policy_exception_count": [1, 0],
            "high_risk_vendor_count": [1, 0],
            "inactive_vendor_count": [0, 1],
            "audit_exception_count": [2, 1],
        }
    )
    summary.to_csv(run_dir / "audit_summary.csv", index=False, lineterminator="\n")

    output_path = tmp_path / "audit_report.html"
    build_audit_report(run_dir, output_path)

    raw = output_path.read_bytes()
    text = raw.decode("utf-8")

    assert not raw.startswith(b"\xef\xbb\xbf")
    assert "\r" not in text
    assert "Control evidence" in text
    assert "Key observations" in text
    assert "Exception profile by category" in text
    assert "Vendor concentration" in text
    assert "Cost-centre prioritisation" in text
    assert "Traceability and limitations" in text
    assert "deterministic synthetic data" in text
    assert 'src="https://cdn.plot.ly/' not in text
    assert "plotly.js" in text.lower()
