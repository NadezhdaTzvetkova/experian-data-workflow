import shutil
from pathlib import Path

from experian_workflow.assurance import pipeline, reporting


def test_html_renderer_uses_validated_publication_package(monkeypatch):
    root = Path(__file__).resolve().parents[1]

    def fail_recalculation(*args, **kwargs):
        raise AssertionError(
            "HTML renderer must not independently recalculate headline KPIs "
            "when the validated publication package exists"
        )

    monkeypatch.setattr(reporting, "build_assurance_kpis", fail_recalculation)
    monkeypatch.setattr(
        reporting,
        "cross_check_headline_kpis",
        fail_recalculation,
    )

    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = (
        root
        / "output"
        / "assurance_runs"
        / str(manifest["run_id"])
    )

    try:
        report_path = root / str(manifest["outputs"]["assurance_report"])
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert 'id="kpi-tests" class="kpi-value">9</div>' in html
        assert 'id="kpi-sufficient" class="kpi-value">5</div>' in html
        assert "Metric validation</span><span>PASS" in html
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
