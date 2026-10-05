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


def test_dashboard_v3_has_cross_filter_controls(dashboard_html: str) -> None:
    expected = [
        'id="active-filter-chips"',
        'id="metric-mode-toggle"',
        "handleRiskDomainClick",
        "handleEvidenceClick",
        "handleResidualRiskClick",
        "clearDashboardSelection",
        "renderActiveFilterChips",
    ]

    for value in expected:
        assert value in dashboard_html


def test_dashboard_v3_has_dynamic_observations(dashboard_html: str) -> None:
    assert 'id="dynamic-observations"' in dashboard_html
    assert "renderDynamicObservations" in dashboard_html


def test_dashboard_v3_has_assurance_test_drilldown(dashboard_html: str) -> None:
    expected = [
        'id="test-detail-drawer"',
        'id="test-detail-content"',
        "openTestDetail",
        "closeTestDetail",
    ]

    for value in expected:
        assert value in dashboard_html


def test_dashboard_v3_has_findings_action_filters_and_search(
    dashboard_html: str,
) -> None:
    expected = [
        'id="filter-finding-severity"',
        'id="filter-finding-status"',
        'id="filter-action-status"',
        'id="filter-overdue"',
        'id="filter-repeat"',
        'id="finding-search"',
        "applyFindingFilters",
        "renderFindingSummary",
    ]

    for value in expected:
        assert value in dashboard_html


def test_dashboard_v3_has_findings_interaction(dashboard_html: str) -> None:
    expected = [
        'id="finding-summary-chart"',
        'id="action-summary-chart"',
        "openFindingDetail",
        'id="finding-detail-drawer"',
    ]

    for value in expected:
        assert value in dashboard_html


def test_dashboard_v3_has_expandable_lineage(dashboard_html: str) -> None:
    expected = [
        'id="lineage-sources"',
        'id="lineage-config"',
        'id="lineage-publication"',
        "toggleLineageSection",
    ]

    for value in expected:
        assert value in dashboard_html


def test_dashboard_v3_updates_all_connected_views(dashboard_html: str) -> None:
    required_calls = [
        "renderExecutiveKpis(rows)",
        "renderEvidenceChart(rows)",
        "renderResidualChart(rows)",
        "renderRiskDomainChart(rows)",
        "renderFreshnessChart(rows)",
        "renderAttentionTable(rows)",
        "renderDynamicObservations(rows)",
        "renderActiveFilterChips()",
    ]

    for call in required_calls:
        assert call in dashboard_html
