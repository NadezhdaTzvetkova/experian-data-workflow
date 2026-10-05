from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


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
):
    from experian_workflow.assurance.html_dashboard import (
        build_assurance_report as _build_assurance_report,
    )

    return _build_assurance_report(run_dir, output_path, manifest)
