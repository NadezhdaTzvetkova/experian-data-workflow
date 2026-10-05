from __future__ import annotations

from pathlib import Path
from typing import Any

REPORT_PAGES = {
    "executive_assurance.html": "executive",
    "risk_and_evidence.html": "risk-evidence",
    "findings_and_actions.html": "findings-actions",
    "data_trust.html": "lineage",
}

CHART_PAGES = {
    "evidence_sufficiency.html": ("executive", "evidence-chart"),
    "residual_risk.html": ("executive", "residual-chart"),
    "risk_domain.html": ("risk-evidence", "risk-domain-chart"),
    "freshness.html": ("risk-evidence", "freshness-chart"),
    "findings.html": ("findings-actions", "finding-summary-chart"),
    "remediation_actions.html": ("findings-actions", "action-summary-chart"),
}


def _focused_html(
    dashboard_html: str,
    *,
    tab_name: str,
    target_id: str | None = None,
) -> str:
    if "</body>" not in dashboard_html:
        raise RuntimeError("Canonical dashboard HTML has no closing body tag")

    target_js = ""
    if target_id is not None:
        target_js = (
            f'setTimeout(() => document.getElementById("{target_id}")'
            '?.scrollIntoView({behavior: "auto", block: "center"}), 80);'
        )

    if "</head>" not in dashboard_html:
        raise RuntimeError("Canonical dashboard HTML has no closing head tag")

    dashboard_html = dashboard_html.replace(
        "</head>",
        '<base href="../">' + "</head>",
        1,
    )

    script = f"""
<script data-browser-publication="focus">
window.addEventListener("DOMContentLoaded", () => {{
    setActiveDashboardTab("{tab_name}");
    {target_js}
}});
</script>
"""
    return dashboard_html.replace("</body>", f"{script}</body>", 1)


def write_browser_publication(
    *,
    dashboard_path: Path,
    html_dir: Path,
) -> dict[str, Any]:
    dashboard_html = dashboard_path.read_text(encoding="utf-8")

    required_markers = (
        'id="dashboard-shell"',
        'id="assurance-data"',
        "function setActiveDashboardTab",
    )
    missing = [marker for marker in required_markers if marker not in dashboard_html]
    if missing:
        raise RuntimeError(
            f"Canonical dashboard is missing browser-publication markers: {missing}"
        )

    expected_link_targets = [
        *(f"reports/{filename}" for filename in REPORT_PAGES),
        *(f"charts/{filename}" for filename in CHART_PAGES),
    ]
    missing_links = [
        target
        for target in expected_link_targets
        if f'data-browser-path="{target}"' not in dashboard_html
    ]
    if missing_links:
        raise RuntimeError(
            f"Canonical dashboard is missing browser links: {missing_links}"
        )
    if dashboard_html.count('target="_blank"') < len(expected_link_targets):
        raise RuntimeError("Canonical dashboard is missing required new-tab targets")

    reports_dir = html_dir / "reports"
    charts_dir = html_dir / "charts"
    existing_dirs = [path for path in (reports_dir, charts_dir) if path.exists()]
    if existing_dirs:
        raise RuntimeError(
            "Browser publication directories already exist: "
            + ", ".join(str(path) for path in existing_dirs)
        )
    reports_dir.mkdir(parents=False, exist_ok=False)
    charts_dir.mkdir(parents=False, exist_ok=False)

    report_paths: dict[str, Path] = {}
    for filename, tab_name in REPORT_PAGES.items():
        path = reports_dir / filename
        path.write_text(
            _focused_html(dashboard_html, tab_name=tab_name),
            encoding="utf-8",
            newline="\n",
        )
        report_paths[filename] = path

    chart_paths: dict[str, Path] = {}
    for filename, (tab_name, target_id) in CHART_PAGES.items():
        path = charts_dir / filename
        path.write_text(
            _focused_html(
                dashboard_html,
                tab_name=tab_name,
                target_id=target_id,
            ),
            encoding="utf-8",
            newline="\n",
        )
        chart_paths[filename] = path

    generated_paths = [*report_paths.values(), *chart_paths.values()]
    invalid_paths = [
        path for path in generated_paths if not path.exists() or path.stat().st_size == 0
    ]
    if invalid_paths:
        raise RuntimeError(f"Browser publication contains invalid files: {invalid_paths}")

    return {
        "status": "PASS",
        "new_tab_links_validated": True,
        "report_count": len(report_paths),
        "chart_count": len(chart_paths),
        "reports": report_paths,
        "charts": chart_paths,
    }
