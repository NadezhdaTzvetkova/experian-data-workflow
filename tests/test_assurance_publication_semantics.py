import shutil
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

@pytest.mark.parametrize(
    "pipeline_stage",
    [
        "write_browser_publication",
        "build_tableau_hyper",
        "build_tableau_workbook",
        "build_powerpoint_publication",
    ],
)
def test_late_publication_failure_does_not_publish_terminal_manifest(
    monkeypatch,
    pipeline_stage: str,
) -> None:
    root = Path(__file__).resolve().parents[1]
    runs_dir = root / "output" / "assurance_runs"
    before = {
        path.name
        for path in runs_dir.iterdir()
        if path.is_dir()
    }

    def fail_stage(*args, **kwargs):
        raise RuntimeError(f"synthetic {pipeline_stage} failure")

    monkeypatch.setattr(pipeline, pipeline_stage, fail_stage)

    created: list[Path] = []
    try:
        with pytest.raises(
            RuntimeError,
            match=f"synthetic {pipeline_stage} failure",
        ):
            pipeline.run_assurance_pipeline(root)

        created = [
            path
            for path in runs_dir.iterdir()
            if path.is_dir() and path.name not in before
        ]
        assert len(created) == 1

        failed_run = created[0]
        manifest_path = failed_run / "manifest.json"
        assert not manifest_path.exists()

        validation_summary_path = (
            failed_run / "publication" / "validation_summary.json"
        )
        if validation_summary_path.exists():
            validation_text = validation_summary_path.read_text(
                encoding="utf-8"
            )
            assert "completed_at_utc" not in validation_text
    finally:
        for path in created:
            shutil.rmtree(path, ignore_errors=True)
