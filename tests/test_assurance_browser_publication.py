import shutil
from pathlib import Path

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.browser_publication import (
    CHART_PAGES,
    REPORT_PAGES,
    write_browser_publication,
)


def test_browser_publication_generates_current_run_reports_and_charts():
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = root / "output" / "assurance_runs" / str(manifest["run_id"])

    try:
        html_dir = run_dir / "publication" / "html"
        dashboard_path = html_dir / "assurance_dashboard.html"
        result = write_browser_publication(
            dashboard_path=dashboard_path,
            html_dir=html_dir,
        )

        assert result["status"] == "PASS"
        assert result["report_count"] == 4
        assert result["chart_count"] == 6

        dashboard_text = dashboard_path.read_text(encoding="utf-8")
        assert 'id="assurance-data"' in dashboard_text
        dashboard_lower = dashboard_text.lower()
        assert '<script src="http' not in dashboard_lower
        assert "<script src='http" not in dashboard_lower
        assert '<link href="http' not in dashboard_lower
        assert "<link href='http" not in dashboard_lower

        for filename, tab_name in REPORT_PAGES.items():
            path = Path(result["reports"][filename])
            text = path.read_text(encoding="utf-8")
            assert path.exists()
            assert 'data-browser-publication="focus"' in text
            assert f'setActiveDashboardTab("{tab_name}")' in text
            assert 'id="assurance-data"' in text
            assert '<base href="../">' in text

        for filename, (tab_name, target_id) in CHART_PAGES.items():
            path = Path(result["charts"][filename])
            text = path.read_text(encoding="utf-8")
            assert path.exists()
            assert f'setActiveDashboardTab("{tab_name}")' in text
            assert f'document.getElementById("{target_id}")' in text
            assert 'id="assurance-data"' in text
            assert '<base href="../">' in text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
