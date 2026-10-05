import shutil
from pathlib import Path

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.tableau_workbook_contract import (
    validate_tableau_workbook_contract,
)


def test_tableau_workbook_contract_matches_governed_dictionary():
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = (
        root
        / "output"
        / "assurance_runs"
        / str(manifest["run_id"])
    )

    try:
        result = validate_tableau_workbook_contract(
            contract_path=root / "config" / "assurance" / "tableau_workbook_contract.json",
            dictionary_path=run_dir
            / "publication"
            / "tableau"
            / "tableau_data_dictionary.csv",
        )

        assert result["status"] == "PASS"
        assert result["workbook_id"] == "assurance_dashboard"
        assert result["dashboard_count"] == 4
        assert result["worksheet_count"] == 11
        assert result["referenced_dataset_count"] == 8
        assert set(result["dashboard_ids"]) == {
            "executive_assurance",
            "risk_and_evidence",
            "findings_and_actions",
            "data_trust",
        }
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
