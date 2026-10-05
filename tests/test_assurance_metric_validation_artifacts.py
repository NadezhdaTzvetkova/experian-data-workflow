import json
import shutil
from pathlib import Path

from experian_workflow.assurance.pipeline import run_assurance_pipeline


def test_successful_run_publishes_machine_readable_metric_validation():
    root = Path(__file__).resolve().parents[1]
    manifest = run_assurance_pipeline(root)
    run_dir = root / "output" / "assurance_runs" / str(manifest["run_id"])

    try:
        assert "metrics" in manifest["outputs"]
        assert "metric_validation" in manifest["outputs"]

        metrics_path = root / str(manifest["outputs"]["metrics"])
        validation_path = root / str(
            manifest["outputs"]["metric_validation"]
        )

        assert metrics_path.exists()
        assert validation_path.exists()

        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        validation = json.loads(
            validation_path.read_text(encoding="utf-8")
        )

        assert metrics == {
            "assurance_tests": 9,
            "sufficient_evidence": 5,
            "partial_evidence": 1,
            "insufficient_evidence": 2,
            "not_evaluable_evidence": 1,
            "stale_evidence": 2,
            "unmapped_tests": 1,
            "high_or_critical_residual_risk": 2,
            "not_evaluable_residual_risk": 4,
            "overdue_actions": 1,
            "repeat_findings": 1,
            "open_findings": 4,
        }

        assert validation["status"] == "PASS"
        assert validation["pandas"] == metrics
        assert validation["duckdb"] == metrics
        assert validation["metric_contract"] == metrics
        assert validation["all_match"] is True
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

def test_metric_contract_drift_blocks_terminal_publication(
    tmp_path: Path,
) -> None:
    import shutil

    import pytest
    import yaml

    root = Path(__file__).resolve().parents[1]
    work = tmp_path / "repo"
    shutil.copytree(
        root,
        work,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "output",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
        ),
    )

    metrics_path = work / "config" / "assurance" / "metrics.yaml"
    contract = yaml.safe_load(metrics_path.read_text(encoding="utf-8"))

    contract["metrics"]["sufficient_evidence"]["calculation"] = {
        "population": "control_assurance",
        "aggregation": "count",
        "operator": "eq",
        "field": "evidence_sufficiency",
        "value": "NOT_EVALUABLE",
    }

    metrics_path.write_text(
        yaml.safe_dump(contract, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )

    runs_dir = work / "output" / "assurance_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    before = set(runs_dir.iterdir())

    with pytest.raises(
        RuntimeError,
        match="Assurance metric validation failed",
    ):
        run_assurance_pipeline(work)

    after = set(runs_dir.iterdir())
    created = after - before

    assert created == set()
