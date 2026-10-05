import shutil
from pathlib import Path

import pytest

from experian_workflow.assurance.pipeline import run_assurance_pipeline


@pytest.fixture(scope="module")
def dashboard_html() -> str:
    root = Path(__file__).resolve().parents[1]
    manifest = run_assurance_pipeline(root)
    run_dir = root / "output" / "assurance_runs" / str(manifest["run_id"])
    report_path = root / str(manifest["outputs"]["assurance_report"])

    try:
        yield report_path.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_assurance_report_has_interactive_dashboard_shell(
    dashboard_html: str,
) -> None:
    expected_elements = [
        'id="dashboard-shell"',
        'id="dashboard-filters"',
        'id="filter-risk-domain"',
        'id="filter-evidence"',
        'id="filter-freshness"',
        'id="filter-residual-risk"',
        'data-dashboard-tab="executive"',
        'data-dashboard-tab="risk-evidence"',
        'data-dashboard-tab="findings-actions"',
        'data-dashboard-tab="lineage"',
        'id="attention-table"',
        'id="priority-table"',
    ]

    for element in expected_elements:
        assert element in dashboard_html


def test_assurance_report_uses_stakeholder_friendly_labels(
    dashboard_html: str,
) -> None:
    assert "Not evaluable" in dashboard_html
    assert "Sufficient evidence" in dashboard_html
    assert "Evidence freshness" in dashboard_html
    assert "Findings & actions" in dashboard_html


def test_assurance_report_contains_client_side_filtering(
    dashboard_html: str,
) -> None:
    assert "applyDashboardFilters" in dashboard_html
    assert "setActiveDashboardTab" in dashboard_html
    assert "Plotly.react" in dashboard_html
