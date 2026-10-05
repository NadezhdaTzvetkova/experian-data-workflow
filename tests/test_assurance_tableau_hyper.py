import shutil
from pathlib import Path

import pandas as pd
import pytest
from tableauhyperapi import Connection, CreateMode, HyperProcess, Telemetry

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.publication import TABLE_CONTRACTS
from experian_workflow.assurance.tableau import (
    TABLEAU_METRICS_TABLE,
    _metric_rows,
    build_tableau_hyper,
    validate_tableau_hyper,
)


def test_tableau_hyper_matches_governed_publication_package():
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = (
        root
        / "output"
        / "assurance_runs"
        / str(manifest["run_id"])
    )

    try:
        hyper_path = (
            run_dir
            / "publication"
            / "tableau"
            / "assurance_dashboard.hyper"
        )
        tables = {
            name: pd.read_csv(
                run_dir / "publication" / "tables" / f"{name}.csv",
                dtype=str,
                keep_default_na=False,
            )
            for name in TABLE_CONTRACTS
        }
        metric_rows = _metric_rows(
            metrics_path=run_dir / "publication" / "metrics.json",
            metrics_config_path=root / "config" / "assurance" / "metrics.yaml",
        )
        result = validate_tableau_hyper(
            hyper_path=hyper_path,
            source_tables=tables,
            metric_rows=metric_rows,
        )

        assert hyper_path.exists()
        assert result["status"] == "PASS"
        assert result["governed_metrics"]["status"] == "PASS"
        assert result["governed_metrics"]["row_count"] == 12
        assert result["governed_metrics"]["exact_match"] is True
        assert result["acceptance_model"] == "PROGRAMMATIC_TABLEAU"

        expected_rows = {
            "assurance_tests": 9,
            "risk_domain_summary": 3,
            "findings_summary": 5,
            "remediation_summary": 6,
            "findings_actions_detail": 8,
            "attention_items": 6,
            "lineage_summary": 7,
        }
        for name, expected_count in expected_rows.items():
            assert result["tables"][name]["status"] == "PASS"
            assert result["tables"][name]["row_count"] == expected_count
            assert result["tables"][name]["run_identity_match"] is True

        assert TABLEAU_METRICS_TABLE == "governed_metrics"

        with pytest.raises(
            RuntimeError,
            match="Tableau Hyper output already exists",
        ):
            build_tableau_hyper(
                run_dir=run_dir,
                project_root=root,
            )
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

def test_tableau_hyper_rejects_non_key_content_drift():
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = root / "output" / "assurance_runs" / str(manifest["run_id"])

    try:
        hyper_path = run_dir / "publication" / "tableau" / "assurance_dashboard.hyper"
        tables = {}
        for name in TABLE_CONTRACTS:
            tables[name] = pd.read_csv(
                run_dir / "publication" / "tables" / f"{name}.csv",
                dtype=str,
                keep_default_na=False,
            )
        metric_rows = _metric_rows(
            metrics_path=run_dir / "publication" / "metrics.json",
            metrics_config_path=root / "config" / "assurance" / "metrics.yaml",
        )

        with HyperProcess(
            Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU
        ) as hyper, Connection(
            endpoint=hyper.endpoint,
            database=hyper_path,
            create_mode=CreateMode.NONE,
        ) as connection:
            connection.execute_command(
                "UPDATE \"Extract\".\"assurance_tests\" "
                "SET \"system_name\" = 'CORRUPTED' "
                "WHERE \"test_id\" = 'TEST_COV_001' "
                "AND \"reporting_period\" = '2026-09'"
            )

        try:
            validate_tableau_hyper(
                hyper_path=hyper_path,
                source_tables=tables,
                metric_rows=metric_rows,
            )
        except RuntimeError as exc:
            assert "Hyper full-content mismatch for assurance_tests" in str(exc)
        else:
            raise AssertionError("Expected Hyper content drift to be rejected")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
