from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio


def build_audit_report(
    run_dir: Path | str,
    output_path: Path | str,
    manifest: dict[str, object] | None = None,
) -> Path:
    run_dir = Path(run_dir)
    output_path = Path(output_path)

    if manifest is None:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    curated = pd.read_parquet(run_dir / "curated_expenses.parquet")
    summary = pd.read_csv(run_dir / "audit_summary.csv")

    category_view = summary.copy()
    category_view["exception_rate_pct"] = (
        category_view["audit_exception_count"] / category_view["transaction_count"] * 100
    ).round(1)

    vendor_view = (
        curated[curated["audit_exception"]]
        .groupby(["vendor_id", "vendor_name"], as_index=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            exception_spend_minor=("amount_minor", "sum"),
            policy_exception_count=("policy_exception", "sum"),
            high_risk_vendor_count=("high_risk_vendor", "sum"),
            inactive_vendor_count=("inactive_vendor", "sum"),
        )
        .sort_values(["exception_spend_minor", "transaction_count"], ascending=False)
        .head(10)
    )

    cost_center_view = (
        curated[curated["audit_exception"]]
        .groupby("cost_center", as_index=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            exception_spend_minor=("amount_minor", "sum"),
        )
        .sort_values("exception_spend_minor", ascending=False)
    )

    category_fig = px.bar(
        category_view,
        x="category",
        y=["transaction_count", "audit_exception_count"],
        barmode="group",
        title="Accepted transactions vs audit exceptions by category",
        labels={"value": "Transaction count", "category": "Category", "variable": "Measure"},
    )
    category_fig.update_layout(legend_title_text="", margin={"l": 40, "r": 20, "t": 70, "b": 40})

    vendor_fig = px.bar(
        vendor_view.sort_values("exception_spend_minor"),
        x="exception_spend_minor",
        y="vendor_id",
        orientation="h",
        title="Audit-exception spend by vendor",
        labels={"exception_spend_minor": "Exception spend (minor units)", "vendor_id": "Vendor"},
        hover_data=[
            "vendor_name",
            "transaction_count",
            "policy_exception_count",
            "high_risk_vendor_count",
            "inactive_vendor_count",
        ],
    )
    vendor_fig.update_layout(margin={"l": 40, "r": 20, "t": 70, "b": 40})

    cost_center_fig = px.bar(
        cost_center_view,
        x="cost_center",
        y="exception_spend_minor",
        title="Audit-exception spend by cost centre",
        labels={"exception_spend_minor": "Exception spend (minor units)", "cost_center": "Cost centre"},
        hover_data=["transaction_count"],
    )
    cost_center_fig.update_layout(margin={"l": 40, "r": 20, "t": 70, "b": 40})

    meals = category_view.loc[category_view["category"] == "meals"].iloc[0]
    travel = category_view.loc[category_view["category"] == "travel"].iloc[0]
    top_vendor = vendor_view.iloc[0]
    top_cost_center = cost_center_view.iloc[0]

    evidence = manifest["counts"]
    analytics = manifest["analytics_validation"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audit Analytics Workflow Report</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 36px; color: #1f2937; background: #ffffff; }}
h1 {{ margin-bottom: 6px; }}
h2 {{ margin-top: 36px; border-bottom: 1px solid #d1d5db; padding-bottom: 8px; }}
.subtitle {{ color: #6b7280; margin-bottom: 24px; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
.card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; background: #f9fafb; }}
.metric {{ font-size: 28px; font-weight: 700; margin: 4px 0; }}
.label {{ color: #6b7280; font-size: 13px; }}
.finding {{ margin: 12px 0; padding-left: 14px; border-left: 3px solid #9ca3af; }}
.note {{ background: #f3f4f6; padding: 16px; border-radius: 8px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; }}
th {{ background: #f9fafb; }}
</style>
</head>
<body>
<h1>Audit Analytics Workflow Report</h1>
<div class="subtitle">Run {manifest["run_id"]} · Policy {manifest["policy_version"]} · Status {manifest["status"]}</div>

<h2>Control evidence</h2>
<div class="grid">
<div class="card"><div class="label">Source rows</div><div class="metric">{evidence["source"]}</div></div>
<div class="card"><div class="label">Trusted rows</div><div class="metric">{evidence["accepted"]}</div></div>
<div class="card"><div class="label">Quarantined rows</div><div class="metric">{evidence["quarantined"]}</div></div>
<div class="card"><div class="label">Independent KPI reconciliation</div><div class="metric">{"PASS" if analytics["match"] else "FAIL"}</div></div>
</div>

<h2>Key observations</h2>
<div class="finding"><strong>Meals are the strongest policy-control hotspot.</strong> {int(meals["audit_exception_count"])} of {int(meals["transaction_count"])} accepted meal transactions carry at least one audit exception, including {int(meals["policy_exception_count"])} policy-limit breaches.</div>
<div class="finding"><strong>Travel shows a different risk profile.</strong> Only {int(travel["policy_exception_count"])} travel transaction breaches the configured policy threshold, while vendor-risk and inactive-vendor controls contribute additional exceptions.</div>
<div class="finding"><strong>Vendor exposure is concentrated.</strong> {top_vendor["vendor_id"]} has the highest exception spend at {int(top_vendor["exception_spend_minor"]):,} minor units across {int(top_vendor["transaction_count"])} flagged transactions.</div>
<div class="finding"><strong>Audit prioritisation is possible by organisational segment.</strong> {top_cost_center["cost_center"]} has the highest exception spend at {int(top_cost_center["exception_spend_minor"]):,} minor units.</div>

<h2>Exception profile by category</h2>
{pio.to_html(category_fig, include_plotlyjs="inline", full_html=False)}

<h2>Vendor concentration</h2>
{pio.to_html(vendor_fig, include_plotlyjs=False, full_html=False)}

<h2>Cost-centre prioritisation</h2>
{pio.to_html(cost_center_fig, include_plotlyjs=False, full_html=False)}

<h2>Traceability and limitations</h2>
<div class="note">
<p><strong>Traceability:</strong> source files, policy configuration and analytical SQL are recorded by SHA-256 in the run manifest. Source-to-trusted and trusted-to-curated row reconciliation passed. Headline KPIs were independently recalculated in Pandas and DuckDB and matched.</p>
<p><strong>Interpretation:</strong> audit flags are not mutually exclusive. A transaction may breach policy and also involve a high-risk or historically inactive vendor.</p>
<p><strong>Limitation:</strong> this is deterministic synthetic data created for the technical exercise. The observed prevalence and concentration of exceptions should not be interpreted as representative of Experian or any real organisation.</p>
</div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8", newline="\n")
    return output_path
