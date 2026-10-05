import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.publication import TABLE_CONTRACTS


def test_successful_run_publishes_governed_publication_foundation():
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = (
        root
        / "output"
        / "assurance_runs"
        / str(manifest["run_id"])
    )

    try:
        publication = run_dir / "publication"
        tables_dir = publication / "tables"

        assert publication.is_dir()
        assert tables_dir.is_dir()

        metrics = json.loads(
            (publication / "metrics.json").read_text(
                encoding="utf-8"
            )
        )
        validation = json.loads(
            (publication / "metric_validation.json").read_text(
                encoding="utf-8"
            )
        )
        summary = json.loads(
            (publication / "validation_summary.json").read_text(
                encoding="utf-8"
            )
        )

        assert metrics["run_id"] == manifest["run_id"]
        assert metrics["validation_status"] == "PASS"
        assert metrics["metrics"] == validation["published"]
        assert validation["pandas"] == validation["published"]
        assert validation["duckdb"] == validation["published"]
        assert validation["metric_contract"] == validation["published"]
        assert validation["status"] == "PASS"
        assert summary["status"] == "PASS"
        assert summary["scope"] == "publication_foundation_html_tableau_and_powerpoint"
        assert summary["html"]["status"] == "PASS"
        assert summary["html"]["structural_markers_validated"] is True
        assert summary["run_id"] == manifest["run_id"]
        assert summary["persisted_readback"]["status"] == "PASS"
        assert summary["persisted_readback"]["metrics"] == "PASS"
        assert summary["persisted_readback"]["metric_validation"] == "PASS"

        for name, contract in TABLE_CONTRACTS.items():
            path = tables_dir / f"{name}.csv"
            assert path.exists()

            frame = pd.read_csv(path)
            assert summary["tables"][name]["status"] == "PASS"
            assert summary["tables"][name]["row_count"] == len(frame)
            assert summary["tables"][name]["key"] == list(
                contract.key
            )
            assert set(frame["publication_run_id"].astype(str)) == {
                str(manifest["run_id"])
            }
            assert summary["tables"][name]["persisted_readback_status"] == "PASS"
            assert summary["tables"][name]["persisted_full_content_match"] is True
            assert (
                summary["persisted_readback"]["tables"][name]["status"]
                == "PASS"
            )
            assert (
                summary["persisted_readback"]["tables"][name][
                    "full_content_match"
                ]
                is True
            )

        assurance = pd.read_csv(
            tables_dir / "assurance_tests.csv"
        )
        assert len(assurance) == 9

        attention = pd.read_csv(
            tables_dir / "attention_items.csv"
        )
        assert set(attention["test_id"]) == {
            "TEST_COV_001",
            "TEST_IAM_BOUNDARY",
            "TEST_IAM_FRESH",
            "TEST_IAM_STALE",
            "TEST_MAP_001",
            "TEST_TP_001",
        }
        assert len(attention) == 6
        findings = pd.read_csv(
            tables_dir / "findings_summary.csv"
        )
        assert len(findings) == 5

        remediation = pd.read_csv(
            tables_dir / "remediation_summary.csv"
        )
        assert len(remediation) == 6

        detail = pd.read_csv(
            tables_dir / "findings_actions_detail.csv"
        )
        assert set(detail["finding_id"]) == set(findings["finding_id"])
        assert set(detail["action_id"].dropna()) == set(
            remediation["action_id"]
        )

        assert "publication" in manifest["outputs"]
        assert (
            root / manifest["outputs"]["publication"]["validation_summary"]
        ).exists()
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_publication_failure_blocks_terminal_manifest(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    runs_dir = root / "output" / "assurance_runs"
    before = {
        path.name
        for path in runs_dir.iterdir()
        if path.is_dir()
    }

    def fail_publication(*args, **kwargs):
        raise RuntimeError("synthetic publication failure")

    monkeypatch.setattr(
        pipeline,
        "write_publication_package",
        fail_publication,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic publication failure",
    ):
        pipeline.run_assurance_pipeline(root)

    created = [
        path
        for path in runs_dir.iterdir()
        if path.is_dir() and path.name not in before
    ]

    assert len(created) == 1
    assert not (created[0] / "manifest.json").exists()

    shutil.rmtree(created[0], ignore_errors=True)
