from __future__ import annotations

import json
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio

from experian_workflow.assurance.explainability import load_explainability


def build_assurance_report(
    run_dir: Path | str,
    output_path: Path | str,
    manifest: dict[str, object] | None = None,
) -> Path:
    run_dir = Path(run_dir).resolve()
    output_path = Path(output_path)

    if manifest is None:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    publication_dir = run_dir / "publication"
    publication_metrics_path = publication_dir / "metrics.json"
    publication_metric_validation_path = publication_dir / "metric_validation.json"
    publication_tables_dir = publication_dir / "tables"

    required_publication_paths = [
        publication_metrics_path,
        publication_metric_validation_path,
        publication_tables_dir / "assurance_tests.csv",
        publication_tables_dir / "risk_domain_summary.csv",
        publication_tables_dir / "findings_actions_detail.csv",
    ]
    missing_publication_paths = [
        path for path in required_publication_paths if not path.exists()
    ]
    if missing_publication_paths:
        missing = ", ".join(
            path.relative_to(run_dir).as_posix()
            for path in missing_publication_paths
        )
        raise RuntimeError(
            f"Publication package is incomplete for HTML rendering: {missing}"
        )

    publication_metrics = json.loads(
        publication_metrics_path.read_text(encoding="utf-8")
    )
    if str(publication_metrics.get("run_id")) != str(manifest["run_id"]):
        raise RuntimeError(
            "Publication metrics run identity does not match report manifest"
        )
    if publication_metrics.get("validation_status") != "PASS":
        raise RuntimeError(
            "Publication metrics are not validated for HTML rendering"
        )

    raw_metrics = publication_metrics.get("metrics")
    if not isinstance(raw_metrics, dict):
        raise TypeError(
            "Publication metrics payload must contain a metrics mapping"
        )
    kpis = {str(name): int(value) for name, value in raw_metrics.items()}

    mart = pd.read_csv(publication_tables_dir / "assurance_tests.csv")
    risk_domain_view = pd.read_csv(
        publication_tables_dir / "risk_domain_summary.csv"
    )
    detail = pd.read_csv(
        publication_tables_dir / "findings_actions_detail.csv"
    )
    priority_view = detail.reset_index(drop=True)

    evidence_view = (
        mart["evidence_sufficiency"]
        .value_counts(dropna=False)
        .rename_axis("evidence_sufficiency")
        .reset_index(name="test_count")
    )

    bootstrap_fig = px.bar(
        evidence_view,
        x="evidence_sufficiency",
        y="test_count",
    )
    plotly_bootstrap = pio.to_html(
        bootstrap_fig,
        include_plotlyjs="inline",
        full_html=False,
        div_id="plotly-bootstrap",
    )

    methodology = manifest["methodology"]
    reporting = manifest["reporting"]
    reconciliation = manifest["controls"]["reconciliation"]

    source_inventory = manifest.get("source_inventory", {})
    configuration = manifest.get("configuration", {})

    def manifest_path(
        container: object,
        key: str,
    ) -> str:
        if not isinstance(container, dict):
            return "Not supplied in report manifest"

        entry = container.get(key)
        if not isinstance(entry, dict):
            return "Not supplied in report manifest"

        value = entry.get("path")
        if value in (None, ""):
            return "Not supplied in report manifest"

        return str(value)

    enterprise_reference_path = manifest_path(
        source_inventory,
        "enterprise_reference",
    )
    control_evidence_path = manifest_path(
        source_inventory,
        "control_evidence",
    )
    findings_source_path = manifest_path(
        source_inventory,
        "findings",
    )
    management_actions_path = manifest_path(
        source_inventory,
        "management_actions",
    )

    rules_config_path = manifest_path(configuration, "rules")
    reconciliation_config_path = manifest_path(
        configuration,
        "reconciliation",
    )
    metrics_config_path = manifest_path(configuration, "metrics")

    try:
        metric_validation = json.loads(
            publication_metric_validation_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Metric-validation evidence exists but cannot be read"
        ) from exc

    status = metric_validation.get("status")
    all_match = metric_validation.get("all_match")

    if status != "PASS" or all_match is not True:
        raise RuntimeError(
            "Metric-validation evidence is not PASS: "
            f"status={status!r}, all_match={all_match!r}"
        )

    published_values = metric_validation.get("published")
    if published_values != kpis:
        raise RuntimeError(
            "HTML renderer metrics do not match the validated "
            "publication metric package"
        )

    metric_validation_status = str(status)

    terminal_manifest_state = (
        "Present at render time"
        if (run_dir / "manifest.json").exists()
        else "Pending terminal publication"
    )

    validated_closures = int(
        priority_view["closure_validation_status"]
        .fillna("")
        .astype(str)
        .eq("VALIDATED")
        .sum()
    )

    mart_json = mart.to_json(orient="records", date_format="iso")
    priority_json = priority_view.to_json(orient="records", date_format="iso")
    risk_domain_json = risk_domain_view.to_json(orient="records", date_format="iso")

    explanation = load_explainability(run_dir=run_dir, expected_run_id=str(manifest["run_id"]))
    source_rows = "".join(
        "<tr>" + "".join(f"<td>{escape(str(source[key]))}</td>" for key in ("path", "format", "role", "grain")) + "</tr>"
        for source in explanation["sources"]
    )
    metric_rows = "".join(
        "<tr>" + "".join(f"<td>{escape(str(item[key]))}</td>" for key in ("label", "value", "grain", "numerator", "denominator", "limitation")) + "</tr>"
        for item in explanation["metrics"].values()
    )
    state_rows = "".join(f"<p><strong>{escape(key)}</strong>: {escape(value)}</p>" for key, value in explanation["states"].items())
    validation_rows = "".join(f"<p><strong>{escape(key)}</strong>: {escape(value)}</p>" for key, value in explanation["validation_levels"].items())
    rationale_rows = "".join(f"<p><strong>{escape(key)}</strong>: {escape(value)}</p>" for key, value in explanation["implementation_choices"].items())
    canonical_metrics_json = json.dumps(kpis)
    metric_definitions_json = json.dumps(explanation["metrics"])
    accessible_columns = [
        "test_id", "system_name", "entity_name", "control_name", "risk_domain",
        "expected_population", "received_population", "structurally_valid_population",
        "mapped_population", "testable_population", "evaluated_population",
        "not_tested_population", "coverage_ratio", "evidence_sufficiency",
        "freshness_state", "evidence_age_days", "control_effectiveness",
        "inherent_risk", "residual_risk", "identity_status", "reporting_period",
    ]
    accessible_rows = mart[accessible_columns].fillna("Not supplied").rename(
        columns=lambda name: name.replace("_", " ").capitalize(),
    ).to_html(
        index=False, classes="dashboard-table", border=0, escape=True,
    ).replace("<th>", '<th scope="col">')
    explanation_html = (
        '<details id="data-and-metrics" class="lineage-card" open><summary><strong>Methodology / Data &amp; Metrics</strong></summary>'
        + '<p>' + escape(explanation["disclaimer"]) + '</p>'
        + '<p>Reporting period: ' + escape(explanation["reporting_period"]) + '. As of: ' + escape(explanation["as_of_date"]) + '.</p>'
        + '<h3>Sources and roles</h3><div style="overflow-x:auto"><table><thead><tr><th>Source</th><th>Format</th><th>Role</th><th>Grain</th></tr></thead><tbody>' + source_rows + '</tbody></table></div>'
        + '<h3>Python-driven flow</h3><p>' + escape(' → '.join(explanation["pipeline_stages"])) + '</p>'
        + '<h3>Claim-to-evidence traceability</h3><p>' + escape(explanation["claim_to_evidence"]) + '</p><p>' + escape(explanation["traceability_limit"]) + '</p>'
        + '<p>' + escape(explanation["reconciliation_grain"]) + ' ' + escape(explanation["grain_distinction"]) + '</p>'
        + '<h3>Headline metric definitions (validated default scope)</h3><p>Counts are not percentages. Denominators below describe context; use the correct test, finding or action population when interpreting a rate. Filters change scope; this table records the validated full-run values.</p>'
        + '<div style="overflow-x:auto"><table><thead><tr><th>Metric</th><th>Count</th><th>Grain</th><th>Numerator</th><th>Denominator/context</th><th>Limitation</th></tr></thead><tbody>' + metric_rows + '</tbody></table></div>'
        + '<h3>State meanings</h3>' + state_rows + '<h3>What validation proves</h3>' + validation_rows
        + '<h3>Implementation choices</h3><p>' + escape(explanation["implementation_choice_scope"]) + '</p>' + rationale_rows + '</details>'
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Enterprise Assurance Analytics Report</title>
<style>
:root {{
    --navy: #102a43;
    --navy-2: #243b53;
    --blue: #2563eb;
    --blue-soft: #dbeafe;
    --green: #15803d;
    --green-soft: #dcfce7;
    --amber: #b45309;
    --amber-soft: #fef3c7;
    --red: #b91c1c;
    --red-soft: #fee2e2;
    --purple: #6d28d9;
    --gray-25: #fcfcfd;
    --gray-50: #f8fafc;
    --gray-100: #f1f5f9;
    --gray-200: #e2e8f0;
    --gray-300: #cbd5e1;
    --gray-500: #64748b;
    --gray-700: #334155;
    --gray-900: #0f172a;
    --shadow: 0 10px 28px rgba(15, 23, 42, 0.07);
}}

* {{ box-sizing: border-box; }}

body {{
    margin: 0;
    background: var(--gray-50);
    color: var(--gray-900);
    font-family: Inter, "Segoe UI", Arial, sans-serif;
}}

#plotly-bootstrap {{ display: none !important; }}

#dashboard-shell {{
    min-height: 100vh;
}}

.hero {{
    background:
        radial-gradient(circle at 85% 20%, rgba(37,99,235,.22), transparent 28%),
        linear-gradient(135deg, #102a43 0%, #173f67 58%, #1f5d8f 100%);
    color: white;
    padding: 34px 42px 30px;
}}

.hero-inner {{
    max-width: 1480px;
    margin: 0 auto;
}}

.hero-top {{
    display: flex;
    justify-content: space-between;
    gap: 24px;
    align-items: flex-start;
}}

.eyebrow {{
    text-transform: uppercase;
    letter-spacing: .12em;
    font-size: 11px;
    font-weight: 700;
    opacity: .78;
    margin-bottom: 8px;
}}

.hero h1 {{
    margin: 0;
    font-size: 32px;
    line-height: 1.15;
    letter-spacing: -.02em;
}}

.hero-meta {{
    margin-top: 10px;
    color: rgba(255,255,255,.78);
    font-size: 14px;
}}

.status-pill {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255,255,255,.13);
    border: 1px solid rgba(255,255,255,.24);
    border-radius: 999px;
    padding: 8px 13px;
    font-size: 13px;
    font-weight: 700;
    white-space: nowrap;
}}

.status-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #4ade80;
    box-shadow: 0 0 0 4px rgba(74,222,128,.14);
}}

.dashboard-main {{
    max-width: 1480px;
    margin: 0 auto;
    padding: 0 30px 44px;
}}

.nav-strip {{
    margin-top: -1px;
    background: white;
    border-bottom: 1px solid var(--gray-200);
    position: sticky;
    top: 0;
    z-index: 30;
}}

.nav-inner {{
    max-width: 1480px;
    margin: 0 auto;
    display: flex;
    gap: 4px;
    padding: 0 30px;
    overflow-x: auto;
}}

.tab-button {{
    border: 0;
    background: transparent;
    color: var(--gray-500);
    font-weight: 650;
    font-size: 14px;
    padding: 16px 18px 14px;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    white-space: nowrap;
}}

.tab-button:hover {{
    color: var(--navy);
}}

.tab-button.active {{
    color: var(--blue);
    border-bottom-color: var(--blue);
}}

.open-artifact-link {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--blue);
    font-size: 12px;
    font-weight: 700;
    text-decoration: none;
    white-space: nowrap;
}}
.open-artifact-link:hover {{
    text-decoration: underline;
}}

.filter-panel {{
    margin-top: 24px;
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 14px;
    box-shadow: var(--shadow);
    padding: 17px 18px;
}}

.filter-header {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: center;
    margin-bottom: 12px;
}}

.filter-title {{
    font-weight: 750;
    color: var(--navy);
    font-size: 14px;
}}

.filter-caption {{
    color: var(--gray-500);
    font-size: 12px;
}}

.filter-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(150px, 1fr)) auto;
    gap: 12px;
    align-items: end;
}}

.filter-field label {{
    display: block;
    color: var(--gray-500);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .05em;
    margin-bottom: 6px;
}}

.filter-field select {{
    width: 100%;
    min-height: 39px;
    border: 1px solid var(--gray-300);
    border-radius: 8px;
    background: white;
    color: var(--gray-900);
    padding: 8px 10px;
    font-size: 13px;
}}

.reset-button {{
    min-height: 39px;
    border: 1px solid var(--gray-300);
    background: white;
    color: var(--gray-700);
    border-radius: 8px;
    padding: 8px 14px;
    cursor: pointer;
    font-weight: 650;
}}

.reset-button:hover {{
    background: var(--gray-100);
}}

.active-filter-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    margin-top: 12px;
    flex-wrap: wrap;
}}

.active-filter-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    min-height: 30px;
    align-items: center;
}}

.filter-chip {{
    border: 1px solid var(--blue-soft);
    background: #eff6ff;
    color: var(--blue);
    border-radius: 999px;
    padding: 5px 9px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
}}

.metric-mode-toggle {{
    border: 1px solid var(--gray-300);
    background: white;
    color: var(--navy);
    border-radius: 999px;
    padding: 7px 11px;
    font-size: 11px;
    font-weight: 750;
    cursor: pointer;
}}

.finding-filter-panel {{
    display: grid;
    grid-template-columns: repeat(5, minmax(125px, 1fr)) minmax(190px, 1.5fr);
    gap: 10px;
    margin-bottom: 18px;
}}

.finding-filter-panel select,
.finding-filter-panel input {{
    width: 100%;
    min-height: 38px;
    border: 1px solid var(--gray-300);
    border-radius: 8px;
    background: white;
    color: var(--gray-900);
    padding: 8px 10px;
    font-size: 12px;
}}

.summary-chart-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 18px;
}}

.drawer-backdrop {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, .36);
    z-index: 80;
}}

.drawer-backdrop.open {{
    display: block;
}}

.detail-drawer {{
    position: fixed;
    top: 0;
    right: -560px;
    width: min(520px, 94vw);
    height: 100vh;
    background: white;
    box-shadow: -18px 0 42px rgba(15, 23, 42, .18);
    z-index: 90;
    transition: right .22s ease;
    overflow-y: auto;
    padding: 24px;
}}

.detail-drawer.open {{
    right: 0;
}}

.drawer-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 18px;
    margin-bottom: 18px;
}}

.drawer-close {{
    border: 1px solid var(--gray-300);
    background: white;
    border-radius: 8px;
    cursor: pointer;
    padding: 6px 10px;
    font-weight: 700;
}}

.detail-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}}

.detail-item {{
    border: 1px solid var(--gray-200);
    border-radius: 9px;
    padding: 10px;
}}

.detail-label {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: .05em;
    color: var(--gray-500);
    font-weight: 750;
}}

.detail-value {{
    margin-top: 5px;
    font-size: 12px;
    color: var(--gray-900);
    word-break: break-word;
}}

.lineage-accordion {{
    margin-bottom: 12px;
    border: 1px solid var(--gray-200);
    border-radius: 12px;
    background: white;
    overflow: hidden;
}}

.lineage-toggle {{
    width: 100%;
    border: 0;
    background: white;
    padding: 14px 16px;
    display: flex;
    justify-content: space-between;
    cursor: pointer;
    color: var(--navy);
    font-weight: 750;
    text-align: left;
}}

.lineage-content {{
    display: none;
    padding: 0 16px 15px;
}}

.lineage-content.open {{
    display: block;
}}

.clickable-row {{
    cursor: pointer;
}}

.clickable-row:hover {{
    background: #eef6ff !important;
}}

.dashboard-tab {{
    display: none;
    padding-top: 22px;
}}

.dashboard-tab.active {{
    display: block;
}}

.section-title {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-end;
    margin: 6px 0 14px;
}}

.section-title h2 {{
    margin: 0;
    font-size: 22px;
    color: var(--navy);
    letter-spacing: -.01em;
}}

.section-title p {{
    margin: 5px 0 0;
    color: var(--gray-500);
    font-size: 13px;
    max-width: 900px;
}}

.section-kicker {{
    font-size: 11px;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: var(--blue);
    margin-bottom: 5px;
}}

.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(170px, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}}

.kpi-card {{
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 14px;
    box-shadow: var(--shadow);
    padding: 17px 18px 16px;
    position: relative;
    overflow: hidden;
}}

.kpi-card::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--blue);
}}

.kpi-card.good::before {{ background: var(--green); }}
.kpi-card.warn::before {{ background: var(--amber); }}
.kpi-card.risk::before {{ background: var(--red); }}
.kpi-card.neutral::before {{ background: var(--gray-500); }}

.kpi-label {{
    color: var(--gray-500);
    font-size: 12px;
    font-weight: 650;
}}

.kpi-value {{
    margin-top: 7px;
    font-size: 30px;
    line-height: 1;
    font-weight: 780;
    color: var(--navy);
    letter-spacing: -.03em;
}}

.kpi-sub {{
    margin-top: 8px;
    color: var(--gray-500);
    font-size: 11px;
}}

.content-grid {{
    display: grid;
    grid-template-columns: 1.15fr .85fr;
    gap: 16px;
    margin-bottom: 18px;
}}

.panel {{
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 14px;
    box-shadow: var(--shadow);
    overflow: hidden;
}}

.panel-head {{
    padding: 16px 18px 10px;
}}

.panel-title {{
    margin: 0;
    color: var(--navy);
    font-size: 16px;
    font-weight: 750;
}}

.panel-subtitle {{
    margin-top: 4px;
    color: var(--gray-500);
    font-size: 12px;
}}

.chart {{
    min-height: 330px;
    width: 100%;
}}

.wide-chart {{
    min-height: 380px;
    width: 100%;
}}

.observation-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}}

.observation {{
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 12px;
    padding: 14px 15px;
}}

.observation strong {{
    color: var(--navy);
    display: block;
    margin-bottom: 4px;
    font-size: 13px;
}}

.observation span {{
    color: var(--gray-700);
    font-size: 12px;
    line-height: 1.5;
}}

.table-panel {{
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 14px;
    box-shadow: var(--shadow);
    overflow: hidden;
    margin-bottom: 18px;
}}

.table-scroll {{
    overflow-x: auto;
    max-width: 100%;
}}

.dashboard-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    min-width: 880px;
}}

.dashboard-table th {{
    background: var(--gray-50);
    color: var(--gray-500);
    text-align: left;
    text-transform: uppercase;
    letter-spacing: .045em;
    font-size: 10px;
    font-weight: 750;
    padding: 10px 12px;
    border-bottom: 1px solid var(--gray-200);
    position: sticky;
    top: 0;
}}

.dashboard-table td {{
    padding: 11px 12px;
    border-bottom: 1px solid var(--gray-100);
    vertical-align: top;
    color: var(--gray-700);
}}

.dashboard-table tbody tr:hover {{
    background: #f8fbff;
}}

.badge {{
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 750;
    white-space: nowrap;
}}

.badge-green {{ background: var(--green-soft); color: var(--green); }}
.badge-amber {{ background: var(--amber-soft); color: var(--amber); }}
.badge-red {{ background: var(--red-soft); color: var(--red); }}
.badge-blue {{ background: var(--blue-soft); color: var(--blue); }}
.badge-gray {{ background: var(--gray-100); color: var(--gray-700); }}

.empty-state {{
    padding: 28px;
    text-align: center;
    color: var(--gray-500);
}}

.lineage-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
}}

.lineage-card {{
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 14px;
    padding: 18px;
    box-shadow: var(--shadow);
}}

.lineage-card h3 {{
    margin: 0 0 12px;
    color: var(--navy);
    font-size: 15px;
}}

.lineage-row {{
    display: flex;
    justify-content: space-between;
    gap: 18px;
    padding: 8px 0;
    border-bottom: 1px solid var(--gray-100);
    font-size: 12px;
}}

.lineage-row:last-child {{ border-bottom: 0; }}

.lineage-row span:first-child {{ color: var(--gray-500); }}
.lineage-row span:last-child {{
    font-weight: 650;
    color: var(--gray-900);
    text-align: right;
}}

.methodology-note {{
    margin-top: 16px;
    border-left: 4px solid var(--amber);
    background: #fffbeb;
    color: #78350f;
    border-radius: 8px;
    padding: 14px 16px;
    font-size: 12px;
    line-height: 1.55;
}}

.footer {{
    color: var(--gray-500);
    text-align: center;
    padding: 30px 10px 0;
    font-size: 11px;
}}

@media (max-width: 1050px) {{
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .content-grid {{ grid-template-columns: 1fr; }}
    .filter-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .lineage-grid {{ grid-template-columns: 1fr; }}
}}

@media (max-width: 680px) {{
    .hero {{ padding: 26px 20px; }}
    .hero-top {{ display: block; }}
    .status-pill {{ margin-top: 16px; }}
    .dashboard-main {{ padding: 0 14px 30px; }}
    .nav-inner {{ padding: 0 14px; }}
    .filter-grid {{ grid-template-columns: 1fr; }}
    .kpi-grid {{ grid-template-columns: 1fr; }}
    .observation-grid {{ grid-template-columns: 1fr; }}
}}
button:focus-visible, a:focus-visible, select:focus-visible, input:focus-visible,
summary:focus-visible, [tabindex]:focus-visible {{ outline: 3px solid #1e40af; outline-offset: 3px; }}
.skip-link {{ position: fixed; top: -80px; left: 12px; z-index: 1000; background: white; color: #102a43; padding: 12px; }}
.skip-link:focus {{ top: 12px; }}
.panel-title {{ margin: 0; }}
.dashboard-main, .panel, .content-grid > * {{ min-width: 0; }}
.badge {{ color: #102a43; }}
@media (max-width: 680px) {{
    .summary-chart-grid, .finding-filter-panel {{ grid-template-columns: 1fr; }}
    .detail-drawer {{ width: 100%; max-width: 100%; }}
    .nav-inner {{ flex-wrap: wrap; }}
}}
</style>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to analysis</a>
{plotly_bootstrap}

<div id="dashboard-shell">

<header class="hero">
<div class="hero-inner">
    <div class="hero-top">
        <div>
            <div class="eyebrow">Enterprise assurance - synthetic demonstration</div>
            <h1>Enterprise Assurance Analytics</h1>
            <div class="hero-meta">
                Run {manifest["run_id"]} - As of {reporting["as_of_date"]} -
                Methodology {methodology["version"]}
            </div>
        </div>
        <div class="status-pill">
            <span class="status-dot"></span>
            {manifest["status"]} - KPI reconciliation {metric_validation_status}
        </div>
    </div>
</div>
</header>

<nav class="nav-strip">
<div class="nav-inner">
    <button class="tab-button active" aria-pressed="true" data-dashboard-tab="executive"
        onclick="setActiveDashboardTab('executive')">Executive</button>
    <a class="open-artifact-link" href="reports/executive_assurance.html" target="_blank" rel="noopener" data-browser-path="reports/executive_assurance.html" onclick="openBrowserArtifact(event, 'reports/executive_assurance.html')">Open report ↗</a>
    <button class="tab-button" aria-pressed="false" data-dashboard-tab="risk-evidence"
        onclick="setActiveDashboardTab('risk-evidence')">Risk &amp; evidence</button>
    <a class="open-artifact-link" href="reports/risk_and_evidence.html" target="_blank" rel="noopener" data-browser-path="reports/risk_and_evidence.html" onclick="openBrowserArtifact(event, 'reports/risk_and_evidence.html')">Open report ↗</a>
    <button class="tab-button" aria-pressed="false" data-dashboard-tab="findings-actions"
        onclick="setActiveDashboardTab('findings-actions')">Findings & actions</button>
    <a class="open-artifact-link" href="reports/findings_and_actions.html" target="_blank" rel="noopener" data-browser-path="reports/findings_and_actions.html" onclick="openBrowserArtifact(event, 'reports/findings_and_actions.html')">Open report ↗</a>
    <button class="tab-button" aria-pressed="false" data-dashboard-tab="lineage"
        onclick="setActiveDashboardTab('lineage')">Data &amp; Metrics</button>
    <a class="open-artifact-link" href="reports/data_trust.html" target="_blank" rel="noopener" data-browser-path="reports/data_trust.html" onclick="openBrowserArtifact(event, 'reports/data_trust.html')">Open report ↗</a>
</div>
</nav>

<main id="main-content" class="dashboard-main" tabindex="-1">

<section id="dashboard-filters" class="filter-panel">
<div class="filter-header">
    <div>
        <div class="filter-title">Dashboard filters</div>
        <div class="filter-caption">Filters update assurance-test KPIs, charts and attention items.</div>
    </div>
    <div id="filtered-count" class="filter-caption"></div>
</div>
<div class="filter-grid">
    <div class="filter-field">
        <label for="filter-risk-domain">Risk domain</label>
        <select id="filter-risk-domain" onchange="applyDashboardFilters()"></select>
    </div>
    <div class="filter-field">
        <label for="filter-evidence">Evidence</label>
        <select id="filter-evidence" onchange="applyDashboardFilters()"></select>
    </div>
    <div class="filter-field">
        <label for="filter-freshness">Freshness</label>
        <select id="filter-freshness" onchange="applyDashboardFilters()"></select>
    </div>
    <div class="filter-field">
        <label for="filter-residual-risk">Residual risk</label>
        <select id="filter-residual-risk" onchange="applyDashboardFilters()"></select>
    </div>
    <button class="reset-button" onclick="resetDashboardFilters()">Reset</button>
</div>
<div class="active-filter-row">
    <div id="active-filter-chips" class="active-filter-chips"></div>
    <button
        id="metric-mode-toggle"
        class="metric-mode-toggle"
        onclick="toggleMetricMode()"
        type="button"
    >Metric mode: count</button>
</div>
</section>

<section id="tab-executive" class="dashboard-tab active">

<div class="section-title">
<div>
    <div class="section-kicker">Executive assurance view</div>
    <h2>Current assurance position</h2>
    <p>Headline indicators respond to the selected assurance-test population.</p>
</div>
</div>

<div class="kpi-grid">
    <div class="kpi-card">
        <div class="kpi-label">Assurance tests</div>
        <div id="kpi-tests" class="kpi-value">{kpis["assurance_tests"]}</div>
        <div class="kpi-sub">Selected test population</div>
    </div>
    <div class="kpi-card good">
        <div class="kpi-label">Sufficient evidence</div>
        <div id="kpi-sufficient" class="kpi-value">{kpis["sufficient_evidence"]}</div>
        <div id="kpi-sufficient-sub" class="kpi-sub">Evidence supports evaluation</div>
    </div>
    <div class="kpi-card warn">
        <div class="kpi-label">Stale evidence</div>
        <div id="kpi-stale" class="kpi-value">{kpis["stale_evidence"]}</div>
        <div class="kpi-sub">Evidence outside freshness policy</div>
    </div>
    <div class="kpi-card neutral">
        <div class="kpi-label">Unmapped tests</div>
        <div id="kpi-unmapped" class="kpi-value">{kpis["unmapped_tests"]}</div>
        <div class="kpi-sub">Identity intentionally unresolved</div>
    </div>
    <div class="kpi-card risk">
        <div class="kpi-label">High / critical residual risk</div>
        <div id="kpi-high-risk" class="kpi-value">{kpis["high_or_critical_residual_risk"]}</div>
        <div class="kpi-sub">Evaluable risk requiring attention</div>
    </div>
    <div class="kpi-card warn">
        <div class="kpi-label">Not evaluable residual risk</div>
        <div id="kpi-not-evaluable" class="kpi-value">{kpis["not_evaluable_residual_risk"]}</div>
        <div class="kpi-sub">Evidence does not support a conclusion</div>
    </div>
    <div class="kpi-card risk">
        <div class="kpi-label">Overdue actions</div>
        <div class="kpi-value">{kpis["overdue_actions"]}</div>
        <div class="kpi-sub">Across the full remediation population</div>
    </div>
    <div class="kpi-card good">
        <div class="kpi-label">Independent KPI reconciliation</div>
        <div class="kpi-value" style="font-size:24px">PASS</div>
        <div class="kpi-sub">Pandas results independently matched in DuckDB</div>
    </div>
</div>

<div class="content-grid">
    <div class="panel">
        <div class="panel-head">
            <h3 class="panel-title">Evidence position</h3>
            <div class="panel-subtitle">Composition of the selected assurance-test population</div>
            <a class="open-artifact-link" href="charts/evidence_sufficiency.html" target="_blank" rel="noopener" data-browser-path="charts/evidence_sufficiency.html" onclick="openBrowserArtifact(event, 'charts/evidence_sufficiency.html')">Open chart ↗</a>
        </div>
        <div id="evidence-chart" class="chart"></div>
    </div>
    <div class="panel">
        <div class="panel-head">
            <h3 class="panel-title">Residual-risk visibility</h3>
            <div class="panel-subtitle">Risk conclusions supported by current evidence</div>
            <a class="open-artifact-link" href="charts/residual_risk.html" target="_blank" rel="noopener" data-browser-path="charts/residual_risk.html" onclick="openBrowserArtifact(event, 'charts/residual_risk.html')">Open chart ↗</a>
        </div>
        <div id="residual-chart" class="chart"></div>
    </div>
</div>

<div class="section-title">
<div>
    <div class="section-kicker">Decision support</div>
    <h2>Key observations</h2>
</div>
</div>

<div id="dynamic-observations" class="observation-grid"></div>

</section>

<section id="tab-risk-evidence" class="dashboard-tab">

<div class="section-title">
<div>
    <div class="section-kicker">Assurance by risk domain</div>
    <h2>Risk &amp; evidence</h2>
    <p>Test counts are shown at assurance-test grain. Differences between domains are descriptive and do not imply causation.</p>
</div>
</div>

<div class="panel" style="margin-bottom:18px">
    <div class="panel-head">
        <h3 class="panel-title">Evidence sufficiency by risk domain</h3>
        <div class="panel-subtitle">Sufficient evidence versus tests requiring stronger evidence</div>
        <a class="open-artifact-link" href="charts/risk_domain.html" target="_blank" rel="noopener" data-browser-path="charts/risk_domain.html" onclick="openBrowserArtifact(event, 'charts/risk_domain.html')">Open chart ↗</a>
    </div>
    <div id="risk-domain-chart" class="wide-chart"></div>
</div>

<div class="panel" style="margin-bottom:18px">
    <div class="panel-head">
        <h3 class="panel-title">Evidence freshness</h3>
        <div class="panel-subtitle">Evidence age by assurance test; stale evidence is highlighted</div>
        <a class="open-artifact-link" href="charts/freshness.html" target="_blank" rel="noopener" data-browser-path="charts/freshness.html" onclick="openBrowserArtifact(event, 'charts/freshness.html')">Open chart ↗</a>
    </div>
    <div id="freshness-chart" class="wide-chart"></div>
</div>

<div class="section-title">
<div>
    <div class="section-kicker">Attention items</div>
    <h2>Tests requiring review</h2>
    <p>Incomplete evidence, unresolved identity, or high / critical residual risk.</p>
</div>
</div>

<div class="table-panel">
    <div id="attention-table" class="table-scroll"></div>
</div>

</section>

<section id="tab-findings-actions" class="dashboard-tab">

<div class="section-title">
<div>
    <div class="section-kicker">Finding and remediation priorities</div>
    <h2>Findings & actions</h2>
    <p>Action-grain operational view. Finding counts should continue to come from the governed finding population, not this one-to-many action view.</p>
</div>
</div>

<div class="kpi-grid">
    <div class="kpi-card risk">
        <div class="kpi-label">Open findings</div>
        <div class="kpi-value">{kpis["open_findings"]}</div>
        <div class="kpi-sub">Open or in progress</div>
    </div>
    <div class="kpi-card warn">
        <div class="kpi-label">Repeat findings</div>
        <div class="kpi-value">{kpis["repeat_findings"]}</div>
        <div class="kpi-sub">Exact governed recurrence logic</div>
    </div>
    <div class="kpi-card risk">
        <div class="kpi-label">Overdue actions</div>
        <div class="kpi-value">{kpis["overdue_actions"]}</div>
        <div class="kpi-sub">Strictly before the as-of date</div>
    </div>
    <div class="kpi-card good">
        <div class="kpi-label">Validated closure</div>
        <div id="validated-closures" class="kpi-value">{validated_closures}</div>
        <div class="kpi-sub">Closed actions with validated closure evidence</div>
    </div>
</div>

<div class="finding-filter-panel">
    <select aria-label="Finding severity" id="filter-finding-severity" onchange="applyFindingFilters()"></select>
    <select aria-label="Finding status" id="filter-finding-status" onchange="applyFindingFilters()"></select>
    <select aria-label="Action status" id="filter-action-status" onchange="applyFindingFilters()"></select>
    <select aria-label="Action schedule" id="filter-overdue" onchange="applyFindingFilters()">
        <option value="ALL">All schedules</option>
        <option value="true">Overdue</option>
        <option value="false">Not overdue</option>
    </select>
    <select aria-label="Finding recurrence" id="filter-repeat" onchange="applyFindingFilters()">
        <option value="ALL">All recurrence</option>
        <option value="true">Repeat</option>
        <option value="false">Not repeat</option>
    </select>
    <input
        aria-label="Search findings and actions" id="finding-search"
        type="search"
        placeholder="Search finding, theme, action or owner"
        oninput="applyFindingFilters()"
    >
</div>

<div class="summary-chart-grid">
    <div class="panel">
        <div class="panel-head">
            <h3 class="panel-title">Finding severity</h3>
            <div class="panel-subtitle">Distinct findings in the selected relationship scope; each finding counts once</div>
            <a class="open-artifact-link" href="charts/findings.html" target="_blank" rel="noopener" data-browser-path="charts/findings.html" onclick="openBrowserArtifact(event, 'charts/findings.html')">Open chart ↗</a>
        </div>
        <div id="finding-summary-chart" class="chart"></div>
    </div>
    <div class="panel">
        <div class="panel-head">
            <h3 class="panel-title">Action status</h3>
            <div class="panel-subtitle">Current filtered remediation population</div>
            <a class="open-artifact-link" href="charts/remediation_actions.html" target="_blank" rel="noopener" data-browser-path="charts/remediation_actions.html" onclick="openBrowserArtifact(event, 'charts/remediation_actions.html')">Open chart ↗</a>
        </div>
        <div id="action-summary-chart" class="chart"></div>
    </div>
</div>

<div class="table-panel">
    <div class="panel-head">
        <h3 class="panel-title">Finding and remediation priorities</h3>
        <div class="panel-subtitle">Compact operational view; repeated finding rows represent separate management actions.</div>
    </div>
    <div id="priority-table" class="table-scroll"></div>
</div>

</section>

<section id="tab-lineage" class="dashboard-tab">

<div class="section-title">
<div>
    <div class="section-kicker">Traceability and limitations</div>
    <h2>Data &amp; lineage</h2>
    <p>How to read this report: sources, methods and metric definitions.</p>
    <p>Publication, reconciliation and methodology evidence supporting the dashboard.</p>
</div>
</div>

{explanation_html}

<div class="lineage-accordion">
    <button class="lineage-toggle" aria-controls="lineage-sources" aria-expanded="false" onclick="toggleLineageSection('lineage-sources')" type="button">
        <span>Source lineage</span><span>+</span>
    </button>
    <div id="lineage-sources" class="lineage-content">
        <div class="lineage-row"><span>Enterprise reference</span><span>{enterprise_reference_path}</span></div>
        <div class="lineage-row"><span>Control evidence</span><span>{control_evidence_path}</span></div>
        <div class="lineage-row"><span>Findings</span><span>{findings_source_path}</span></div>
        <div class="lineage-row"><span>Management actions</span><span>{management_actions_path}</span></div>
    </div>
</div>

<div class="lineage-accordion">
    <button class="lineage-toggle" aria-controls="lineage-config" aria-expanded="false" onclick="toggleLineageSection('lineage-config')" type="button">
        <span>Configuration lineage</span><span>+</span>
    </button>
    <div id="lineage-config" class="lineage-content">
        <div class="lineage-row"><span>Rules</span><span>{rules_config_path}</span></div>
        <div class="lineage-row"><span>Reconciliation</span><span>{reconciliation_config_path}</span></div>
        <div class="lineage-row"><span>Metrics</span><span>{metrics_config_path}</span></div>
    </div>
</div>

<div class="lineage-accordion">
    <button class="lineage-toggle" aria-controls="lineage-publication" aria-expanded="false" onclick="toggleLineageSection('lineage-publication')" type="button">
        <span>Publication evidence</span><span>+</span>
    </button>
    <div id="lineage-publication" class="lineage-content">
        <div class="lineage-row"><span>Run</span><span>{manifest["run_id"]}</span></div>
        <div class="lineage-row"><span>Status</span><span>{manifest["status"]}</span></div>
        <div class="lineage-row"><span>Metric validation</span><span>{metric_validation_status}</span></div>
        <div class="lineage-row"><span>Terminal manifest</span><span>{terminal_manifest_state}</span></div>
    </div>
</div>

<div class="lineage-grid">
    <div class="lineage-card">
        <h3>Population reconciliation</h3>
        <div class="lineage-row"><span>Status</span><span>{reconciliation["status"]}</span></div>
        <div class="lineage-row"><span>Expected population</span><span>{reconciliation["expected_population"]}</span></div>
        <div class="lineage-row"><span>Received</span><span>{reconciliation["received_population"]}</span></div>
        <div class="lineage-row"><span>Mapped</span><span>{reconciliation["mapped_population"]}</span></div>
        <div class="lineage-row"><span>Unmapped</span><span>{reconciliation["unmapped_population"]}</span></div>
        <div class="lineage-row"><span>Evaluated</span><span>{reconciliation["evaluated_population"]}</span></div>
        <div class="lineage-row"><span>Mapped but not tested</span><span>{reconciliation["not_tested_population"]}</span></div>
    </div>

    <div class="lineage-card">
        <h3>Validation evidence</h3>
        <div class="lineage-row"><span>Published assurance tests</span><span>{kpis["assurance_tests"]}</span></div>
        <div class="lineage-row"><span>Pandas KPI calculation</span><span>PASS</span></div>
        <div class="lineage-row"><span>Independent DuckDB cross-check</span><span>PASS</span></div>
        <div class="lineage-row"><span>Run status</span><span>{manifest["status"]}</span></div>
        <div class="lineage-row"><span>As-of date</span><span>{reporting["as_of_date"]}</span></div>
        <div class="lineage-row"><span>Methodology version</span><span>{methodology["version"]}</span></div>
    </div>
</div>

<div class="methodology-note">
<strong>Methodology:</strong> {methodology["name"]} {methodology["version"]}.
{methodology["disclaimer"]}
A source test result of PASS does not by itself establish sufficient assurance.
Coverage, freshness, identity resolution and other configured evidence rules remain part of the assurance basis.
</div>

</section>

<div id="drawer-backdrop" class="drawer-backdrop" onclick="closeAllDrawers()"></div>

<aside id="test-detail-drawer" class="detail-drawer" role="dialog" aria-modal="true" aria-hidden="true" inert aria-label="Assurance test detail">
    <div class="drawer-head">
        <div>
            <div class="section-kicker">Assurance test</div>
            <h2 style="margin:0">Test detail</h2>
        </div>
        <button class="drawer-close" onclick="closeTestDetail()" type="button">Close</button>
    </div>
    <div id="test-detail-content"></div>
</aside>

<aside id="finding-detail-drawer" class="detail-drawer" role="dialog" aria-modal="true" aria-hidden="true" inert aria-label="Finding detail">
    <div class="drawer-head">
        <div>
            <div class="section-kicker">Finding &amp; remediation</div>
            <h2 style="margin:0">Finding detail</h2>
        </div>
        <button class="drawer-close" onclick="closeFindingDetail()" type="button">Close</button>
    </div>
    <div id="finding-detail-content"></div>
</aside>

<details class="panel" open><summary><strong>Assurance data table — selected scope</strong></summary>
<p>Coverage, effectiveness, inherent risk and residual risk are distinct. Partial coverage may coexist with an observed EFFECTIVE result while preventing a full residual-risk conclusion. Source-record populations differ from test counts.</p>
<div id="accessible-assurance-table" class="table-scroll" tabindex="0" aria-label="Assurance data table">{accessible_rows}</div>
</details>

<div class="footer">
Self-contained synthetic assurance dashboard - Run {manifest["run_id"]} - No external chart dependency
</div>

</main>
</div>

<script id="canonical-metrics" type="application/json">{canonical_metrics_json}</script>
<script id="metric-definitions" type="application/json">{metric_definitions_json}</script>
<script id="assurance-data" type="application/json">{mart_json}</script>
<script id="priority-data" type="application/json">{priority_json}</script>
<script id="risk-domain-data" type="application/json">{risk_domain_json}</script>

<script>
const assuranceData = JSON.parse(document.getElementById("assurance-data").textContent);
const priorityData = JSON.parse(document.getElementById("priority-data").textContent);
const canonicalMetrics = JSON.parse(document.getElementById("canonical-metrics").textContent);
const metricDefinitions = JSON.parse(document.getElementById("metric-definitions").textContent);

let dashboardSelection = {{
    risk_domain: null,
    evidence_sufficiency: null,
    residual_risk: null
}};

let metricMode = "count";

function escapeHtml(value) {{
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}}

const palette = {{
    navy: "#102a43",
    blue: "#2563eb",
    green: "#15803d",
    amber: "#d97706",
    red: "#dc2626",
    purple: "#7c3aed",
    gray: "#94a3b8",
    grid: "#e2e8f0"
}};

const plotConfig = {{
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
}};

function cleanValue(value) {{
    return value === null || value === undefined || value === "" ? "Unspecified" : String(value);
}}

function humanize(value) {{
    if (value === null || value === undefined) return "Unspecified";
    return String(value)
        .replaceAll("_", " ")
        .toLowerCase()
        .replace(/\\b\\w/g, c => c.toUpperCase());
}}

function uniqueValues(field) {{
    return [...new Set(
        assuranceData
            .map(row => cleanValue(row[field]))
            .filter(value => value !== "Unspecified")
    )].sort();
}}

function populateFilter(id, field) {{
    const select = document.getElementById(id);
    select.innerHTML = '<option value="ALL">All</option>';
    uniqueValues(field).forEach(value => {{
        const option = document.createElement("option");
        option.value = value;
        option.textContent = humanize(value);
        select.appendChild(option);
    }});
}}

function selectedValue(id) {{
    return document.getElementById(id).value;
}}

function filteredAssuranceData() {{
    const riskDomain = selectedValue("filter-risk-domain");
    const evidence = selectedValue("filter-evidence");
    const freshness = selectedValue("filter-freshness");
    const residualRisk = selectedValue("filter-residual-risk");

    return assuranceData.filter(row =>
        (riskDomain === "ALL" || cleanValue(row.risk_domain) === riskDomain) &&
        (evidence === "ALL" || cleanValue(row.evidence_sufficiency) === evidence) &&
        (freshness === "ALL" || cleanValue(row.freshness_state) === freshness) &&
        (residualRisk === "ALL" || cleanValue(row.residual_risk) === residualRisk) &&
        (!dashboardSelection.risk_domain ||
            cleanValue(row.risk_domain) === dashboardSelection.risk_domain) &&
        (!dashboardSelection.evidence_sufficiency ||
            cleanValue(row.evidence_sufficiency) === dashboardSelection.evidence_sufficiency) &&
        (!dashboardSelection.residual_risk ||
            cleanValue(row.residual_risk) === dashboardSelection.residual_risk)
    );
}}

function percentage(value, total) {{
    if (!total) return "0%";
    return `${{Math.round((value / total) * 100)}}%`;
}}

function scopedMetrics(rows) {{
    if (rows.length === assuranceData.length) return canonicalMetrics;
    const result = {{}};
    Object.entries(metricDefinitions).forEach(([id, definition]) => {{
        if (definition.trusted_population !== "control_assurance") return;
        const rule = definition.calculation;
        result[id] = rows.filter(row => {{
            if (rule.operator === "all") return true;
            if (rule.operator === "eq") return row[rule.field] === rule.value;
            if (rule.operator === "in") return rule.values.includes(row[rule.field]);
            throw new Error("Unsupported governed metric operator");
        }}).length;
    }});
    return result;
}}

function renderExecutiveKpis(rows) {{
    const metrics = scopedMetrics(rows);
    const total = metrics.assurance_tests;
    const sufficient = metrics.sufficient_evidence;
    const stale = metrics.stale_evidence;
    const unmapped = metrics.unmapped_tests;
    const highRisk = metrics.high_or_critical_residual_risk;
    const notEvaluable = metrics.not_evaluable_residual_risk;

    const metricValue = value =>
        metricMode === "percentage" ? percentage(value, total) : value;

    document.getElementById("kpi-tests").textContent =
        metricMode === "percentage" ? percentage(total, total) : total;
    document.getElementById("kpi-sufficient").textContent = metricValue(sufficient);
    document.getElementById("kpi-sufficient-sub").textContent =
        `${{percentage(sufficient, total)}} of selected assurance tests`;
    document.getElementById("kpi-stale").textContent = metricValue(stale);
    document.getElementById("kpi-unmapped").textContent = metricValue(unmapped);
    document.getElementById("kpi-high-risk").textContent = metricValue(highRisk);
    document.getElementById("kpi-not-evaluable").textContent = metricValue(notEvaluable);
    document.getElementById("filtered-count").textContent =
        `${{total}} of ${{assuranceData.length}} assurance tests selected`;
}}

function frequency(rows, field, orderedValues = []) {{
    const counts = {{}};
    rows.forEach(row => {{
        const key = cleanValue(row[field]);
        counts[key] = (counts[key] || 0) + 1;
    }});

    const keys = orderedValues.length
        ? orderedValues.filter(key => Object.prototype.hasOwnProperty.call(counts, key))
        : Object.keys(counts);

    Object.keys(counts).forEach(key => {{
        if (!keys.includes(key)) keys.push(key);
    }});

    return {{
        labels: keys,
        values: keys.map(key => counts[key])
    }};
}}

function commonLayout(title) {{
    return {{
        title: {{ text: title, font: {{ size: 14, color: palette.navy }} }},
        font: {{ family: 'Inter, Segoe UI, Arial, sans-serif', color: "#334155", size: 11 }},
        paper_bgcolor: "white",
        plot_bgcolor: "white",
        margin: {{ l: 54, r: 24, t: 56, b: 52 }},
        hoverlabel: {{ bgcolor: palette.navy, font: {{ color: "white" }} }}
    }};
}}

function renderEvidenceChart(rows) {{
    const result = frequency(
        rows,
        "evidence_sufficiency",
        ["SUFFICIENT", "PARTIAL", "INSUFFICIENT", "NOT_EVALUABLE"]
    );

    const colorMap = {{
        SUFFICIENT: palette.green,
        PARTIAL: palette.amber,
        INSUFFICIENT: palette.red,
        NOT_EVALUABLE: palette.gray
    }};

    Plotly.react(
        "evidence-chart",
        [{{
            type: "pie",
            labels: result.labels.map(humanize),
            values: result.values,
            hole: 0.62,
            marker: {{ colors: result.labels.map(label => colorMap[label] || palette.blue) }},
            textinfo: "label+value",
            hovertemplate: "%{{label}}: %{{value}} tests<extra></extra>",
            sort: false
        }}],
        {{
            ...commonLayout("Evidence sufficiency"),
            showlegend: false,
            margin: {{ l: 24, r: 24, t: 50, b: 30 }},
            annotations: [{{
                text: `<b>${{rows.length}}</b><br><span style="font-size:10px">tests</span>`,
                showarrow: false,
                font: {{ size: 18, color: palette.navy }}
            }}]
        }},
        plotConfig
    );

    const chart = document.getElementById("evidence-chart");
    chart.removeAllListeners?.("plotly_click");
    chart.on?.("plotly_click", event => {{
        const point = event.points?.[0];
        if (point) handleEvidenceClick(String(point.label).toUpperCase().replaceAll(" ", "_"));
    }});
}}

function renderResidualChart(rows) {{
    const result = frequency(
        rows,
        "residual_risk",
        ["CRITICAL", "HIGH", "MODERATE", "LOW", "NOT_EVALUABLE"]
    );

    const colorMap = {{
        CRITICAL: "#991b1b",
        HIGH: palette.red,
        MODERATE: palette.amber,
        LOW: palette.green,
        NOT_EVALUABLE: palette.gray
    }};

    Plotly.react(
        "residual-chart",
        [{{
            type: "bar",
            orientation: "h",
            y: result.labels.map(humanize),
            x: result.values,
            marker: {{ color: result.labels.map(label => colorMap[label] || palette.blue) }},
            text: result.values,
            textposition: "auto",
            hovertemplate: "%{{y}}: %{{x}} tests<extra></extra>"
        }}],
        {{
            ...commonLayout("Residual risk"),
            xaxis: {{
                title: "Assurance tests",
                gridcolor: palette.grid,
                dtick: 1,
                rangemode: "tozero"
            }},
            yaxis: {{ title: "" }},
            showlegend: false
        }},
        plotConfig
    );

    const chart = document.getElementById("residual-chart");
    chart.removeAllListeners?.("plotly_click");
    chart.on?.("plotly_click", event => {{
        const point = event.points?.[0];
        if (point) handleResidualRiskClick(String(point.y).toUpperCase().replaceAll(" ", "_"));
    }});
}}

function renderRiskDomainChart(rows) {{
    const grouped = {{}};

    rows.forEach(row => {{
        const domain = cleanValue(row.risk_domain);
        if (!grouped[domain]) grouped[domain] = {{ sufficient: 0, other: 0 }};
        if (cleanValue(row.evidence_sufficiency) === "SUFFICIENT") {{
            grouped[domain].sufficient += 1;
        }} else {{
            grouped[domain].other += 1;
        }}
    }});

    const domains = Object.keys(grouped).sort();

    Plotly.react(
        "risk-domain-chart",
        [
            {{
                type: "bar",
                orientation: "h",
                name: "Sufficient evidence",
                y: domains.map(humanize),
                x: domains.map(domain => grouped[domain].sufficient),
                marker: {{ color: palette.green }},
                text: domains.map(domain => grouped[domain].sufficient), textposition: "auto",
                hovertemplate: "%{{y}}<br>Sufficient: %{{x}}<extra></extra>"
            }},
            {{
                type: "bar",
                orientation: "h",
                name: "Needs stronger evidence",
                y: domains.map(humanize),
                x: domains.map(domain => grouped[domain].other),
                marker: {{ color: palette.amber }},
                text: domains.map(domain => grouped[domain].other), textposition: "auto",
                hovertemplate: "%{{y}}<br>Needs stronger evidence: %{{x}}<extra></extra>"
            }}
        ],
        {{
            ...commonLayout("Assurance by risk domain"),
            barmode: "stack",
            xaxis: {{
                title: "Assurance tests",
                gridcolor: palette.grid,
                dtick: 1
            }},
            yaxis: {{ title: "", automargin: true }},
            legend: {{
                orientation: "h",
                x: 0,
                y: 1.12,
                font: {{ size: 10 }}
            }}
        }},
        plotConfig
    );

    const chart = document.getElementById("risk-domain-chart");
    chart.removeAllListeners?.("plotly_click");
    chart.on?.("plotly_click", event => {{
        const point = event.points?.[0];
        if (point) handleRiskDomainClick(String(point.y));
    }});
}}

function renderFreshnessChart(rows) {{
    const sorted = [...rows].sort(
        (a, b) => Number(a.evidence_age_days || 0) - Number(b.evidence_age_days || 0)
    );

    Plotly.react(
        "freshness-chart",
        [{{
            type: "bar",
            x: sorted.map(row => row.test_id),
            y: sorted.map(row => Number(row.evidence_age_days || 0)),
            marker: {{
                color: sorted.map(row =>
                    cleanValue(row.freshness_state) === "STALE"
                        ? palette.red
                        : palette.blue
                )
            }},
            text: sorted.map(row => `${{row.evidence_age_days}} days / ${{humanize(row.freshness_state)}}`),
            textposition: "auto",
            customdata: sorted.map(row => [
                cleanValue(row.system_name),
                humanize(cleanValue(row.freshness_state))
            ]),
            hovertemplate:
                "<b>%{{x}}</b><br>" +
                "Evidence age: %{{y}} days<br>" +
                "System: %{{customdata[0]}}<br>" +
                "Freshness: %{{customdata[1]}}" +
                "<extra></extra>"
        }}],
        {{
            ...commonLayout("Evidence age by assurance test"),
            xaxis: {{
                title: "",
                tickangle: -25,
                automargin: true
            }},
            yaxis: {{
                title: "Evidence age (days)",
                gridcolor: palette.grid,
                rangemode: "tozero"
            }},
            showlegend: false
        }},
        plotConfig
    );
}}

function badge(value, kind) {{
    return `<span class="badge badge-${{kind}}">${{humanize(value)}}</span>`;
}}

function evidenceBadge(value) {{
    const normalized = cleanValue(value);
    if (normalized === "SUFFICIENT") return badge(normalized, "green");
    if (normalized === "PARTIAL") return badge(normalized, "amber");
    if (normalized === "INSUFFICIENT") return badge(normalized, "red");
    return badge(normalized, "gray");
}}

function riskBadge(value) {{
    const normalized = cleanValue(value);
    if (["CRITICAL", "HIGH"].includes(normalized)) return badge(normalized, "red");
    if (normalized === "MODERATE") return badge(normalized, "amber");
    if (normalized === "LOW") return badge(normalized, "green");
    return badge(normalized, "gray");
}}

function attentionRows(rows) {{
    return rows.filter(row =>
        cleanValue(row.evidence_sufficiency) !== "SUFFICIENT" ||
        cleanValue(row.identity_status) === "UNMAPPED" ||
        ["HIGH", "CRITICAL"].includes(cleanValue(row.residual_risk))
    );
}}

function renderAttentionTable(rows) {{
    const target = document.getElementById("attention-table");
    const items = attentionRows(rows);

    if (!items.length) {{
        target.innerHTML = '<div class="empty-state">No attention items in the selected population.</div>';
        return;
    }}

    const body = items.map(row => `
        <tr
            class="clickable-row" tabindex="0" onkeydown="activateDrillRow(event, this)"
            data-test-id="${{escapeHtml(cleanValue(row.test_id))}}"
            onclick="openTestDetail(this.dataset.testId)"
        >
            <td><strong>${{cleanValue(row.test_id)}}</strong></td>
            <td>${{cleanValue(row.system_name)}}</td>
            <td>${{cleanValue(row.risk_domain)}}</td>
            <td>${{evidenceBadge(row.evidence_sufficiency)}}</td>
            <td>${{badge(row.freshness_state, cleanValue(row.freshness_state) === "STALE" ? "red" : "blue")}}</td>
            <td>${{riskBadge(row.residual_risk)}}</td>
        </tr>
    `).join("");

    target.innerHTML = `
        <table class="dashboard-table">
            <thead>
                <tr>
                    <th>Test</th>
                    <th>System</th>
                    <th>Risk domain</th>
                    <th>Evidence</th>
                    <th>Freshness</th>
                    <th>Residual risk</th>
                </tr>
            </thead>
            <tbody>${{body}}</tbody>
        </table>
    `;
}}

function renderPriorityTable(rows = priorityData) {{
    const target = document.getElementById("priority-table");

    if (!rows.length) {{
        target.innerHTML = '<div class="empty-state">No finding or remediation priorities.</div>';
        return;
    }}

    const body = rows.map(row => {{
        const findingStatus = cleanValue(row.status);
        const actionStatus = cleanValue(row.action_status);
        const overdue = row.overdue === true || String(row.overdue).toLowerCase() === "true";
        const repeat = row.repeat_finding === true || String(row.repeat_finding).toLowerCase() === "true";

        return `
            <tr
                class="clickable-row" tabindex="0" onkeydown="activateDrillRow(event, this)"
                data-finding-id="${{escapeHtml(cleanValue(row.finding_id))}}"
                onclick="openFindingDetail(this.dataset.findingId)"
            >
                <td><strong>${{cleanValue(row.finding_id)}}</strong></td>
                <td>${{cleanValue(row.finding_theme)}}</td>
                <td>${{riskBadge(row.severity)}}</td>
                <td>${{badge(findingStatus, findingStatus === "OPEN" ? "amber" : "blue")}}</td>
                <td>${{repeat ? badge("Repeat", "red") : badge("No", "gray")}}</td>
                <td>${{cleanValue(row.action_id)}}</td>
                <td>${{cleanValue(row.action_owner)}}</td>
                <td>${{cleanValue(row.target_date)}}</td>
                <td>${{badge(actionStatus, actionStatus === "CLOSED" ? "green" : actionStatus === "IN_PROGRESS" ? "blue" : "amber")}}</td>
                <td>${{!row.action_id ? badge("No action", "gray") : overdue ? badge("Overdue", "red") : badge("Not overdue", "green")}}</td>
            </tr>
        `;
    }}).join("");

    target.innerHTML = `
        <table class="dashboard-table">
            <thead>
                <tr>
                    <th>Finding</th>
                    <th>Theme</th>
                    <th>Severity</th>
                    <th>Finding status</th>
                    <th>Repeat</th>
                    <th>Action</th>
                    <th>Owner</th>
                    <th>Target date</th>
                    <th>Action status</th>
                    <th>Schedule</th>
                </tr>
            </thead>
            <tbody>${{body}}</tbody>
        </table>
    `;

    const validated = uniqueRecords(rows, "action_id").filter(row =>
        cleanValue(row.closure_validation_status) === "VALIDATED"
    ).length;
    document.getElementById("validated-closures").textContent = validated;
}}

function handleRiskDomainClick(value) {{
    dashboardSelection.risk_domain =
        dashboardSelection.risk_domain === value ? null : value;
    applyDashboardFilters();
}}

function handleEvidenceClick(value) {{
    dashboardSelection.evidence_sufficiency =
        dashboardSelection.evidence_sufficiency === value ? null : value;
    applyDashboardFilters();
}}

function handleResidualRiskClick(value) {{
    dashboardSelection.residual_risk =
        dashboardSelection.residual_risk === value ? null : value;
    applyDashboardFilters();
}}

function clearDashboardSelection(field = null) {{
    if (field && Object.prototype.hasOwnProperty.call(dashboardSelection, field)) {{
        dashboardSelection[field] = null;
    }} else {{
        dashboardSelection = {{
            risk_domain: null,
            evidence_sufficiency: null,
            residual_risk: null
        }};
    }}
    applyDashboardFilters();
}}

function renderActiveFilterChips() {{
    const target = document.getElementById("active-filter-chips");
    const chips = [];

    Object.entries(dashboardSelection).forEach(([field, value]) => {{
        if (!value) return;
        chips.push(
            `<button class="filter-chip" onclick="clearDashboardSelection('${{field}}')" type="button">` +
            `${{humanize(field)}}: ${{humanize(value)}} [remove]</button>`
        );
    }});

    target.innerHTML = chips.length
        ? chips.join("")
        : '<span class="filter-caption">No chart selections active</span>';
}}

function toggleMetricMode() {{
    metricMode = metricMode === "count" ? "percentage" : "count";
    document.getElementById("metric-mode-toggle").textContent =
        `Metric mode: ${{metricMode}}`;
    applyDashboardFilters();
}}

function renderDynamicObservations(rows) {{
    const metrics = scopedMetrics(rows);
    const total = metrics.assurance_tests;
    const sufficient = metrics.sufficient_evidence;
    const stale = metrics.stale_evidence;
    const unmapped = metrics.unmapped_tests;
    const highRisk = metrics.high_or_critical_residual_risk;
    const notEvaluable = metrics.not_evaluable_residual_risk;

    const observations = [
        [
            "Evidence sufficiency",
            `${{sufficient}} of ${{total}} selected tests have sufficient evidence (${{percentage(sufficient, total)}}).`
        ],
        [
            "Evidence freshness",
            `${{stale}} selected tests rely on evidence outside the configured freshness threshold.`
        ],
        [
            "Identity resolution",
            `${{unmapped}} selected tests retain unresolved enterprise identity rather than inferred context.`
        ],
        [
            "Risk visibility",
            `${{highRisk}} selected tests carry high / critical residual risk; ${{notEvaluable}} do not support a residual-risk conclusion.`
        ]
    ];

    document.getElementById("dynamic-observations").innerHTML =
        observations.map(item => `
            <div class="observation">
                <strong>${{escapeHtml(item[0])}}</strong>
                <span>${{escapeHtml(item[1])}}</span>
            </div>
        `).join("");
}}

function activateDrillRow(event, row) {{
    if (event.key === "Enter" || event.key === " ") {{ event.preventDefault(); row.click(); }}
}}

let drawerReturnFocus = null;
function focusDrawer(id) {{
    drawerReturnFocus = document.activeElement;
    const drawer = document.getElementById(id);
    drawer.inert = false;
    drawer.setAttribute("aria-hidden", "false");
    drawer.querySelector("button").focus();
}}
function restoreDrawerFocus() {{
    document.querySelectorAll(".detail-drawer").forEach(drawer => {{ drawer.setAttribute("aria-hidden", "true"); drawer.inert = true; }});
    drawerReturnFocus?.focus();
}}
document.addEventListener("keydown", event => {{
    const drawer = document.querySelector(".detail-drawer.open");
    if (!drawer) return;
    if (event.key === "Escape") {{ closeAllDrawers(); event.preventDefault(); }}
    if (event.key === "Tab") {{
        const controls = [...drawer.querySelectorAll("button, a, input, select, [tabindex='0']")];
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {{ event.preventDefault(); last.focus(); }}
        else if (!event.shiftKey && document.activeElement === last) {{ event.preventDefault(); first.focus(); }}
    }}
}});

function detailItem(label, value) {{
    return `
        <div class="detail-item">
            <div class="detail-label">${{escapeHtml(label)}}</div>
            <div class="detail-value">${{escapeHtml(cleanValue(value))}}</div>
        </div>
    `;
}}

function openTestDetail(testId) {{
    const row = assuranceData.find(item => cleanValue(item.test_id) === String(testId));
    if (!row) return;

    const fields = [
        ["Test", row.test_id],
        ["System", row.system_name],
        ["Entity", row.entity_name],
        ["Risk domain", row.risk_domain],
        ["Control", row.control_name],
        ["Evidence sufficiency", row.evidence_sufficiency],
        ["Freshness", row.freshness_state],
        ["Evidence age", `${{row.evidence_age_days}} days`],
        ["Coverage", row.coverage_ratio],
        ["Control effectiveness", row.control_effectiveness],
        ["Inherent risk", row.inherent_risk],
        ["Residual risk", row.residual_risk],
        ["Identity", row.identity_status],
        ["Reporting period", row.reporting_period]
    ];

    document.getElementById("test-detail-content").innerHTML =
        `<div class="detail-grid">${{fields.map(item => detailItem(item[0], item[1])).join("")}}</div>`;

    document.getElementById("drawer-backdrop").classList.add("open");
    document.getElementById("test-detail-drawer").classList.add("open");
    focusDrawer("test-detail-drawer");
}}

function closeTestDetail() {{
    restoreDrawerFocus();
    document.getElementById("test-detail-drawer").classList.remove("open");
    if (!document.getElementById("finding-detail-drawer").classList.contains("open")) {{
        document.getElementById("drawer-backdrop").classList.remove("open");
    }}
}}

function populateFindingFilter(id, field, label) {{
    const select = document.getElementById(id);
    const values = [...new Set(
        priorityData
            .map(row => cleanValue(row[field]))
            .filter(value => value !== "Unspecified")
    )].sort();

    select.innerHTML = `<option value="ALL">All ${{label}}</option>`;
    values.forEach(value => {{
        const option = document.createElement("option");
        option.value = value;
        option.textContent = humanize(value);
        select.appendChild(option);
    }});
}}

function filteredFindingData() {{
    const severity = document.getElementById("filter-finding-severity").value;
    const findingStatus = document.getElementById("filter-finding-status").value;
    const actionStatus = document.getElementById("filter-action-status").value;
    const overdue = document.getElementById("filter-overdue").value;
    const repeat = document.getElementById("filter-repeat").value;
    const search = document.getElementById("finding-search").value.trim().toLowerCase();

    return priorityData.filter(row => {{
        const rowOverdue =
            row.overdue === true || String(row.overdue).toLowerCase() === "true";
        const rowRepeat =
            row.repeat_finding === true ||
            String(row.repeat_finding).toLowerCase() === "true";

        const searchable = [
            row.finding_id,
            row.finding_theme,
            row.action_id,
            row.action_owner
        ].map(cleanValue).join(" ").toLowerCase();

        return (
            (severity === "ALL" || cleanValue(row.severity) === severity) &&
            (findingStatus === "ALL" || cleanValue(row.status) === findingStatus) &&
            (actionStatus === "ALL" || cleanValue(row.action_status) === actionStatus) &&
            (overdue === "ALL" || String(rowOverdue) === overdue) &&
            (repeat === "ALL" || String(rowRepeat) === repeat) &&
            (!search || searchable.includes(search))
        );
    }});
}}

function uniqueRecords(rows, field) {{
    const seen = new Set();
    return rows.filter(row => {{
        const id = row[field];
        if (id === null || id === undefined || id === "" || seen.has(id)) return false;
        seen.add(id);
        return true;
    }});
}}

function renderFindingSummary(rows) {{
    const findings = uniqueRecords(rows, "finding_id");
    const severity = frequency(findings, "severity", ["CRITICAL", "HIGH", "MODERATE", "LOW"]);
    Plotly.react(
        "finding-summary-chart",
        [{{
            type: "bar",
            x: severity.labels.map(humanize),
            y: severity.values,
            marker: {{ color: palette.amber }},
            text: severity.values, textposition: "auto",
            hovertemplate: "%{{x}}: %{{y}} records<extra></extra>"
        }}],
        {{
            ...commonLayout("Finding severity"),
            xaxis: {{ title: "" }},
            yaxis: {{ title: "Distinct records", dtick: 1, rangemode: "tozero", gridcolor: palette.grid }},
            showlegend: false
        }},
        plotConfig
    );

    const actions = frequency(uniqueRecords(rows, "action_id"), "action_status", ["OPEN", "IN_PROGRESS", "CLOSED"]);
    Plotly.react(
        "action-summary-chart",
        [{{
            type: "bar",
            x: actions.labels.map(humanize),
            y: actions.values,
            marker: {{ color: palette.blue }},
            text: actions.values, textposition: "auto",
            hovertemplate: "%{{x}}: %{{y}} records<extra></extra>"
        }}],
        {{
            ...commonLayout("Action status"),
            xaxis: {{ title: "" }},
            yaxis: {{ title: "Distinct records", dtick: 1, rangemode: "tozero", gridcolor: palette.grid }},
            showlegend: false
        }},
        plotConfig
    );
}}

function applyFindingFilters() {{
    const rows = filteredFindingData();
    renderPriorityTable(rows);
    renderFindingSummary(rows);
}}

function openFindingDetail(findingId) {{
    const rows = priorityData.filter(
        item => cleanValue(item.finding_id) === String(findingId)
    );
    if (!rows.length) return;

    const first = rows[0];
    const summary = [
        ["Finding", first.finding_id],
        ["Theme", first.finding_theme],
        ["Severity", first.severity],
        ["Finding status", first.status],
        ["Repeat", first.repeat_finding],
        ["Prior finding", first.prior_finding_id]
    ];

    const actions = rows.map(row => `
        <div class="detail-item" style="margin-top:10px">
            <div class="detail-label">${{escapeHtml(cleanValue(row.action_id))}}</div>
            <div class="detail-value">
                Owner: ${{escapeHtml(cleanValue(row.action_owner))}}<br>
                Status: ${{escapeHtml(humanize(cleanValue(row.action_status)))}}<br>
                Target: ${{escapeHtml(cleanValue(row.target_date))}}<br>
                Days overdue: ${{escapeHtml(cleanValue(row.days_overdue))}}
            </div>
        </div>
    `).join("");

    document.getElementById("finding-detail-content").innerHTML =
        `<div class="detail-grid">${{summary.map(item => detailItem(item[0], item[1])).join("")}}</div>` +
        `<h3 style="margin-top:20px">Management actions</h3>${{actions}}`;

    document.getElementById("drawer-backdrop").classList.add("open");
    document.getElementById("finding-detail-drawer").classList.add("open");
    focusDrawer("finding-detail-drawer");
}}

function closeFindingDetail() {{
    restoreDrawerFocus();
    document.getElementById("finding-detail-drawer").classList.remove("open");
    if (!document.getElementById("test-detail-drawer").classList.contains("open")) {{
        document.getElementById("drawer-backdrop").classList.remove("open");
    }}
}}

function closeAllDrawers() {{
    restoreDrawerFocus();
    document.getElementById("test-detail-drawer").classList.remove("open");
    document.getElementById("finding-detail-drawer").classList.remove("open");
    document.getElementById("drawer-backdrop").classList.remove("open");
}}

function toggleLineageSection(id) {{
    const target = document.getElementById(id);
    if (target) {{
        const open = target.classList.toggle("open");
        document.querySelector(`[aria-controls="${{id}}"]`)?.setAttribute("aria-expanded", String(open));
    }}
}}

function renderAccessibleAssuranceTable(rows) {{
    const fields = {json.dumps(accessible_columns)};
    document.getElementById("accessible-assurance-table").innerHTML =
        '<table class="dashboard-table"><caption>Selected assurance tests; population counts are source records, coverage is a ratio</caption><thead><tr>' +
        fields.map(field => `<th scope="col">${{humanize(field)}}</th>`).join("") +
        '</tr></thead><tbody>' + rows.map(row => '<tr>' + fields.map(field => `<td>${{escapeHtml(cleanValue(row[field]))}}</td>`).join("") + '</tr>').join("") + '</tbody></table>';
}}

function applyDashboardFilters() {{
    const rows = filteredAssuranceData();
    renderExecutiveKpis(rows);
    renderEvidenceChart(rows);
    renderResidualChart(rows);
    renderRiskDomainChart(rows);
    renderFreshnessChart(rows);
    renderAttentionTable(rows);
    renderDynamicObservations(rows);
    renderActiveFilterChips();
    renderAccessibleAssuranceTable(rows);
}}

function resetDashboardFilters() {{
    [
        "filter-risk-domain",
        "filter-evidence",
        "filter-freshness",
        "filter-residual-risk"
    ].forEach(id => {{
        document.getElementById(id).value = "ALL";
    }});
    dashboardSelection = {{
        risk_domain: null,
        evidence_sufficiency: null,
        residual_risk: null
    }};
    applyDashboardFilters();
}}

function openBrowserArtifact(event, relativePath) {{
    event.preventDefault();
    const rootReport = window.location.pathname.endsWith("/assurance_report.html");
    const targetPath = rootReport ? `publication/html/${{relativePath}}` : relativePath;
    window.open(targetPath, "_blank", "noopener");
}}

function setActiveDashboardTab(tabName) {{
    document.querySelectorAll(".dashboard-tab").forEach(tab => {{
        tab.classList.toggle("active", tab.id === `tab-${{tabName}}`);
    }});

    document.querySelectorAll(".tab-button").forEach(button => {{
        button.classList.toggle(
            "active",
            button.dataset.dashboardTab === tabName
        );
        button.setAttribute("aria-pressed", String(button.dataset.dashboardTab === tabName));
    }});

    setTimeout(() => {{
        window.dispatchEvent(new Event("resize"));
    }}, 40);
}}

populateFilter("filter-risk-domain", "risk_domain");
populateFilter("filter-evidence", "evidence_sufficiency");
populateFilter("filter-freshness", "freshness_state");
populateFilter("filter-residual-risk", "residual_risk");

populateFindingFilter("filter-finding-severity", "severity", "severities");
populateFindingFilter("filter-finding-status", "status", "finding statuses");
populateFindingFilter("filter-action-status", "action_status", "action statuses");

applyFindingFilters();
applyDashboardFilters();
</script>

</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8", newline="\n")
    return output_path
