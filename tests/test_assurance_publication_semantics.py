from pathlib import Path

import pytest

from experian_workflow.assurance import pipeline


def test_failed_final_report_does_not_publish_manifest(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    before = {
        path.name
        for path in (root / "output" / "assurance_runs").iterdir()
        if path.is_dir()
    }

    def fail_report(*args, **kwargs):
        raise RuntimeError("synthetic report failure")

    monkeypatch.setattr(pipeline, "build_assurance_report", fail_report)

    with pytest.raises(RuntimeError, match="synthetic report failure"):
        pipeline.run_assurance_pipeline(root)

    after_dirs = [
        path
        for path in (root / "output" / "assurance_runs").iterdir()
        if path.is_dir() and path.name not in before
    ]

    assert len(after_dirs) == 1
    assert not (after_dirs[0] / "manifest.json").exists()
