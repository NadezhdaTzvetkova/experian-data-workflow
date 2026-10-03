from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.io as pio


def build_assurance_kpis(
    assurance: pd.DataFrame,
    remediation: pd.DataFrame,
    findings: pd.DataFrame,
) -> dict[str, int]:
    return {
        "assurance_tests": len(assurance),
        "sufficient_evidence": int(assurance["evidence_sufficiency"].eq("SUFFICIENT").sum()),
        "partial_evidence": int(assurance["evidence_sufficiency"].eq("PARTIAL").sum()),
        "insufficient_evidence": int(assurance["evidence_sufficiency"].eq("INSUFFICIENT").sum()),
        "not_evaluable_evidence": int(assurance["evidence_sufficiency"].eq("NOT_EVALUABLE").sum()),
        "stale_evidence": int(assurance["freshness_state"].eq("STALE").sum()),
        "unmapped_tests": int(assurance["identity_status"].eq("UNMAPPED").sum()),
        "high_or_critical_residual_risk": int(assurance["residual_risk"].isin(["HIGH", "CRITICAL"]).sum()),
        "not_evaluable_residual_risk": int(assurance["residual_risk"].eq("NOT_EVALUABLE").sum()),
        "overdue_actions": int(remediation["overdue"].eq(True).sum()),
        "repeat_findings": int(findings["repeat_finding"].eq(True).sum()),
        "open_findings": int(findings["status"].isin(["OPEN", "IN_PROGRESS"]).sum()),
    }



def build_assurance_reporting_mart(
    assurance: pd.DataFrame,
    systems: pd.DataFrame,
    entities: pd.DataFrame,
    controls: pd.DataFrame,
    risk_taxonomy: pd.DataFrame,
) -> pd.DataFrame:
    system_context = systems[[
        "system_id",
        "entity_id",
        "system_name",
        "system_owner",
        "criticality",
        "data_classification",
        "contains_sensitive_data",
        "core_acquired_status",
        "acquisition_cohort",
        "third_party_dependency_flag",
    ]]
    entity_context = entities[[
        "entity_id",
        "entity_name",
        "region",
        "country",
        "business_unit",
        "acquired_status",
    ]]
    control_context = controls[[
        "control_id",
        "control_name",
        "control_objective",
        "control_type",
        "expected_frequency",
    ]]
    risk_context = risk_taxonomy[[
        "risk_id",
        "risk_domain",
        "risk_name",
        "risk_description",
    ]]

    mart = assurance.merge(
        system_context,
        how="left",
        left_on="canonical_system_id",
        right_on="system_id",
        validate="many_to_one",
    )
    mart = mart.merge(
        entity_context,
        how="left",
        on="entity_id",
        validate="many_to_one",
    )
    mart = mart.merge(
        control_context,
        how="left",
        on="control_id",
        validate="many_to_one",
    )
    mart = mart.merge(
        risk_context,
        how="left",
        on="risk_id",
        validate="many_to_one",
    )
    return mart



def build_risk_domain_assurance_summary(
    mart: pd.DataFrame,
) -> pd.DataFrame:
    return (
        mart.groupby("risk_domain", dropna=False)
        .agg(
            assurance_tests=("test_id", "count"),
            sufficient_evidence=(
                "evidence_sufficiency",
                lambda series: int(series.eq("SUFFICIENT").sum()),
            ),
            weak_evidence=(
                "evidence_sufficiency",
                lambda series: int(series.ne("SUFFICIENT").sum()),
            ),
            stale_evidence=(
                "freshness_state",
                lambda series: int(series.eq("STALE").sum()),
            ),
            high_or_critical_residual_risk=(
                "residual_risk",
                lambda series: int(series.isin(["HIGH", "CRITICAL"]).sum()),
            ),
            not_evaluable_residual_risk=(
                "residual_risk",
                lambda series: int(series.eq("NOT_EVALUABLE").sum()),
            ),
        )
        .reset_index()
        .sort_values(
            ["weak_evidence", "assurance_tests", "risk_domain"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
    )


def build_finding_remediation_priority_view(
    findings: pd.DataFrame,
    remediation: pd.DataFrame,
) -> pd.DataFrame:
    action_columns = [
        "finding_id",
        "action_id",
        "action_owner",
        "target_date",
        "status",
        "overdue",
        "days_overdue",
        "closure_validation_status",
    ]
    actions = remediation[action_columns].rename(
        columns={"status": "action_status"}
    )

    priority = findings.merge(
        actions,
        how="left",
        on="finding_id",
        validate="one_to_many",
    )

    return priority.loc[
        priority["status"].isin(["OPEN", "IN_PROGRESS"])
        | priority["repeat_finding"].eq(True)
        | priority["overdue"].eq(True)
    ].reset_index(drop=True)


def cross_check_headline_kpis(
    assurance: pd.DataFrame,
    remediation: pd.DataFrame,
    findings: pd.DataFrame,
) -> dict[str, int]:
    connection = duckdb.connect(":memory:")
    try:
        connection.register("assurance", assurance)
        connection.register("remediation", remediation)
        connection.register("findings", findings)
        row = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM assurance) AS assurance_tests,
                (SELECT COUNT(*) FROM assurance WHERE evidence_sufficiency = 'SUFFICIENT') AS sufficient_evidence,
                (SELECT COUNT(*) FROM assurance WHERE evidence_sufficiency = 'PARTIAL') AS partial_evidence,
                (SELECT COUNT(*) FROM assurance WHERE evidence_sufficiency = 'INSUFFICIENT') AS insufficient_evidence,
                (SELECT COUNT(*) FROM assurance WHERE evidence_sufficiency = 'NOT_EVALUABLE') AS not_evaluable_evidence,
                (SELECT COUNT(*) FROM assurance WHERE freshness_state = 'STALE') AS stale_evidence,
                (SELECT COUNT(*) FROM assurance WHERE identity_status = 'UNMAPPED') AS unmapped_tests,
                (SELECT COUNT(*) FROM assurance WHERE residual_risk IN ('HIGH', 'CRITICAL')) AS high_or_critical_residual_risk,
                (SELECT COUNT(*) FROM assurance WHERE residual_risk = 'NOT_EVALUABLE') AS not_evaluable_residual_risk,
                (SELECT COUNT(*) FROM remediation WHERE overdue = TRUE) AS overdue_actions,
                (SELECT COUNT(*) FROM findings WHERE repeat_finding = TRUE) AS repeat_findings,
                (SELECT COUNT(*) FROM findings WHERE status IN ('OPEN', 'IN_PROGRESS')) AS open_findings
            """
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        raise RuntimeError("DuckDB assurance KPI cross-check returned no result")

    return {
        "assurance_tests": int(row[0]),
        "sufficient_evidence": int(row[1]),
        "partial_evidence": int(row[2]),
        "insufficient_evidence": int(row[3]),
        "not_evaluable_evidence": int(row[4]),
        "stale_evidence": int(row[5]),
        "unmapped_tests": int(row[6]),
        "high_or_critical_residual_risk": int(row[7]),
        "not_evaluable_residual_risk": int(row[8]),
        "overdue_actions": int(row[9]),
        "repeat_findings": int(row[10]),
        "open_findings": int(row[11]),
    }



def build_assurance_report(
    run_dir: Path | str,
    output_path: Path | str,
    manifest: dict[str, object] | None = None,
) -> Path:
    run_dir = Path(run_dir).resolve()
    output_path = Path(output_path)

    if manifest is None:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assurance = pd.read_parquet(run_dir / "control_assurance.parquet")
    remediation = pd.read_csv(run_dir / "remediation_actions.csv")
    findings = pd.read_csv(run_dir / "findings.csv")
    mart = pd.read_parquet(run_dir / "assurance_reporting_mart.parquet")
    kpis = build_assurance_kpis(assurance, remediation, findings)
    cross_check = cross_check_headline_kpis(assurance, remediation, findings)

    for name, value in cross_check.items():
        if kpis[name] != value:
            raise RuntimeError(
                f"Assurance KPI cross-check failed for {name}: "
                f"Pandas={kpis[name]} DuckDB={value}"
            )

    risk_domain_view = build_risk_domain_assurance_summary(mart)
    priority_view = build_finding_remediation_priority_view(findings, remediation)

    risk_domain_fig = px.bar(
        risk_domain_view,
        x="risk_domain",
        y=["sufficient_evidence", "weak_evidence"],
        barmode="group",
        title="Evidence sufficiency by risk domain",
        labels={
            "risk_domain": "Risk domain",
            "value": "Assurance tests",
            "variable": "Evidence classification",
        },
    )
    risk_domain_fig.update_layout(
        margin={"l": 40, "r": 20, "t": 70, "b": 40},
        legend_title_text="Evidence classification",
    )

    priority_columns = [
        "finding_id",
        "system_id",
        "finding_theme",
        "severity",
        "status",
        "repeat_finding",
        "prior_finding_id",
        "action_id",
        "action_owner",
        "target_date",
        "action_status",
        "overdue",
        "days_overdue",
        "closure_validation_status",
    ]
    priority_table = priority_view[priority_columns].to_html(
        index=False,
        border=0,
        classes="data-table",
        na_rep="",
    )

    evidence_view = (
        mart["evidence_sufficiency"]
        .value_counts(dropna=False)
        .rename_axis("evidence_sufficiency")
        .reset_index(name="test_count")
    )
    residual_view = (
        mart["residual_risk"]
        .value_counts(dropna=False)
        .rename_axis("residual_risk")
        .reset_index(name="test_count")
    )
    age_view = mart[[
        "test_id",
        "system_name",
        "evidence_age_days",
        "freshness_state",
    ]].copy()
    age_view["system_name"] = age_view["system_name"].fillna("Unmapped system")

    evidence_fig = px.bar(
        evidence_view,
        x="evidence_sufficiency",
        y="test_count",
        title="Evidence sufficiency across assurance tests",
        labels={
            "evidence_sufficiency": "Evidence sufficiency",
            "test_count": "Assurance tests",
        },
    )
    evidence_fig.update_layout(
        margin={"l": 40, "r": 20, "t": 70, "b": 40},
        showlegend=False,
    )

    residual_fig = px.bar(
        residual_view,
        x="residual_risk",
        y="test_count",
        title="Residual-risk conclusions supported by current evidence",
        labels={
            "residual_risk": "Residual risk",
            "test_count": "Assurance tests",
        },
    )
    residual_fig.update_layout(
        margin={"l": 40, "r": 20, "t": 70, "b": 40},
        showlegend=False,
    )

    age_fig = px.bar(
        age_view.sort_values("evidence_age_days"),
        x="test_id",
        y="evidence_age_days",
        color="freshness_state",
        title="Evidence age by assurance test",
        labels={
            "test_id": "Assurance test",
            "evidence_age_days": "Evidence age (days)",
            "freshness_state": "Freshness",
        },
        hover_data=["system_name"],
    )
    age_fig.update_layout(
        margin={"l": 40, "r": 20, "t": 70, "b": 40},
        xaxis_tickangle=-35,
    )

    attention = mart.loc[
        mart["evidence_sufficiency"].ne("SUFFICIENT")
        | mart["identity_status"].eq("UNMAPPED")
        | mart["residual_risk"].isin(["HIGH", "CRITICAL"]),
        [
            "test_id",
            "system_name",
            "entity_name",
            "control_name",
            "coverage_state",
            "freshness_state",
            "evidence_sufficiency",
            "control_effectiveness",
            "residual_risk",
        ],
    ].copy()
    attention["system_name"] = attention["system_name"].fillna("Unmapped system")
    attention["entity_name"] = attention["entity_name"].fillna("Unresolved entity")
    attention_table = attention.to_html(index=False, border=0, classes="data-table")

    methodology = manifest["methodology"]
    reporting = manifest["reporting"]
    reconciliation = manifest["controls"]["reconciliation"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Enterprise Assurance Analytics Report</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 1280px; margin: 0 auto; padding: 36px; color: #1f2937; background: #ffffff; }}
h1 {{ margin-bottom: 6px; }}
h2 {{ margin-top: 36px; border-bottom: 1px solid #d1d5db; padding-bottom: 8px; }}
.subtitle {{ color: #6b7280; margin-bottom: 24px; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
.card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; background: #f9fafb; }}
.metric {{ font-size: 28px; font-weight: 700; margin: 4px 0; }}
.label {{ color: #6b7280; font-size: 13px; }}
.finding {{ margin: 12px 0; padding-left: 14px; border-left: 3px solid #9ca3af; }}
.note {{ background: #f3f4f6; padding: 16px; border-radius: 8px; }}
.data-table {{ border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 13px; }}
.data-table th, .data-table td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; }}
.data-table th {{ background: #f9fafb; }}
</style>
</head>
<body>
<h1>Enterprise Assurance Analytics Report</h1>
<div class="subtitle">Run {manifest["run_id"]} · As of {reporting["as_of_date"]} · Status {manifest["status"]}</div>

<h2>Executive assurance view</h2>
<div class="grid">
<div class="card"><div class="label">Assurance tests</div><div class="metric">{kpis["assurance_tests"]}</div></div>
<div class="card"><div class="label">Sufficient evidence</div><div class="metric">{kpis["sufficient_evidence"]}</div></div>
<div class="card"><div class="label">Stale evidence</div><div class="metric">{kpis["stale_evidence"]}</div></div>
<div class="card"><div class="label">Unmapped tests</div><div class="metric">{kpis["unmapped_tests"]}</div></div>
<div class="card"><div class="label">Residual risk not evaluable</div><div class="metric">{kpis["not_evaluable_residual_risk"]}</div></div>
<div class="card"><div class="label">Overdue actions</div><div class="metric">{kpis["overdue_actions"]}</div></div>
<div class="card"><div class="label">Repeat findings</div><div class="metric">{kpis["repeat_findings"]}</div></div>
<div class="card"><div class="label">Independent KPI reconciliation</div><div class="metric">PASS</div></div>
</div>

<h2>Key observations</h2>
<div class="finding"><strong>Evidence sufficiency is mixed.</strong> {kpis["sufficient_evidence"]} of {kpis["assurance_tests"]} assurance tests have sufficient evidence; {kpis["partial_evidence"]} are partial, {kpis["insufficient_evidence"]} insufficient, and {kpis["not_evaluable_evidence"]} not evaluable.</div>
<div class="finding"><strong>Evidence freshness limits some conclusions.</strong> {kpis["stale_evidence"]} tests rely on stale evidence under the configured methodology.</div>
<div class="finding"><strong>Identity resolution remains an explicit data-trust issue.</strong> {kpis["unmapped_tests"]} assurance test remains unmapped rather than being assigned unsupported enterprise context.</div>
<div class="finding"><strong>Risk conclusions are evidence-dependent.</strong> {kpis["not_evaluable_residual_risk"]} tests do not support a residual-risk conclusion under the configured rules.</div>
<div class="finding"><strong>Remediation and recurrence are visible separately from control testing.</strong> There are {kpis["overdue_actions"]} overdue action(s), {kpis["repeat_findings"]} repeat finding(s), and {kpis["open_findings"]} open or in-progress finding(s).</div>

<h2>Assurance by risk domain</h2>
<p>This view compares sufficient and non-sufficient evidence across the governed risk-domain population. Counts remain at assurance-test grain and do not imply causal relationships between domain and assurance outcome.</p>
{pio.to_html(risk_domain_fig, include_plotlyjs="inline", full_html=False)}

<h2>Finding and remediation priorities</h2>
<p>This action-grain view highlights open or in-progress findings, repeat findings, and overdue remediation while preserving the distinction between a finding and its individual management actions.</p>
{priority_table}

<h2>Evidence sufficiency</h2>
{pio.to_html(evidence_fig, include_plotlyjs="inline", full_html=False)}

<h2>Residual-risk visibility</h2>
{pio.to_html(residual_fig, include_plotlyjs=False, full_html=False)}

<h2>Evidence freshness</h2>
{pio.to_html(age_fig, include_plotlyjs=False, full_html=False)}

<h2>Attention items</h2>
<p>This view highlights tests with incomplete evidence, unresolved identity, or high/critical residual risk. It does not reclassify the underlying assurance results.</p>
{attention_table}

<h2>Traceability and limitations</h2>
<div class="note">
<p><strong>Reconciliation:</strong> {reconciliation["status"]}. Expected population {reconciliation["expected_population"]}; received {reconciliation["received_population"]}; mapped {reconciliation["mapped_population"]}; unmapped {reconciliation["unmapped_population"]}; evaluated {reconciliation["evaluated_population"]}.</p>
<p><strong>Validation:</strong> headline assurance KPIs were calculated in Pandas and independently cross-checked in DuckDB before report generation.</p>
<p><strong>Interpretation:</strong> a source test result of PASS does not by itself establish sufficient assurance. Coverage, freshness, identity resolution and other configured evidence rules remain part of the assurance basis.</p>
<p><strong>Methodology:</strong> {methodology["name"]} {methodology["version"]}. {methodology["disclaimer"]}</p>
</div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8", newline="\n")
    return output_path
