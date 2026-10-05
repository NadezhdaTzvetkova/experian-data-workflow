import shutil
from pathlib import Path

import pandas as pd

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.tableau_dictionary import (
    write_tableau_data_dictionary,
)


def test_tableau_data_dictionary_is_generated_from_governed_contracts():
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = (
        root
        / "output"
        / "assurance_runs"
        / str(manifest["run_id"])
    )

    try:
        result = write_tableau_data_dictionary(run_dir=run_dir)
        path = Path(result["path"])
        frame = pd.read_csv(path)

        assert result["status"] == "PASS"
        assert result["dataset_count"] == 8
        assert path.exists()
        assert set(frame["dataset_id"]) == {
            "assurance_tests",
            "risk_domain_summary",
            "findings_summary",
            "remediation_summary",
            "findings_actions_detail",
            "attention_items",
            "lineage_summary",
            "governed_metrics",
        }
        assert (
            frame.loc[
                (frame["dataset_id"] == "assurance_tests")
                & (frame["field_name"] == "coverage_ratio"),
                "hyper_type",
            ].item()
            == "DOUBLE"
        )
        assert (
            frame.loc[
                (frame["dataset_id"] == "remediation_summary")
                & (frame["field_name"] == "overdue"),
                "hyper_type",
            ].item()
            == "BOOLEAN"
        )
        assert (
            frame.loc[
                (frame["dataset_id"] == "governed_metrics")
                & (frame["field_name"] == "metric_id"),
                "is_business_key",
            ].item()
            is True
        )
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
