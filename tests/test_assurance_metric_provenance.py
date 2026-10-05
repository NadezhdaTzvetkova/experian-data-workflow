from pathlib import Path

from experian_workflow.assurance.pipeline import run_assurance_pipeline


def test_assurance_manifest_records_metric_dictionary_identity():
    root = Path(__file__).resolve().parents[1]
    manifest = run_assurance_pipeline(root)

    metrics = manifest["configuration"]["metrics"]

    assert metrics["path"] == "config/assurance/metrics.yaml"
    assert len(metrics["sha256"]) == 64
