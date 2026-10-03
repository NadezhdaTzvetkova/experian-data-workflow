import pandas as pd

from experian_workflow.assurance.reporting import (
    build_finding_remediation_priority_view,
    build_risk_domain_assurance_summary,
)


def test_build_risk_domain_assurance_summary_uses_trusted_assurance_population():
    mart = pd.DataFrame(
        {
            "test_id": ["T1", "T2", "T3", "T4"],
            "risk_domain": ["Access", "Access", "Third Party", "Third Party"],
            "evidence_sufficiency": [
                "SUFFICIENT",
                "INSUFFICIENT",
                "PARTIAL",
                "SUFFICIENT",
            ],
            "freshness_state": ["CURRENT", "STALE", "STALE", "CURRENT"],
            "residual_risk": ["LOW", "HIGH", "NOT_EVALUABLE", "CRITICAL"],
        }
    )

    result = build_risk_domain_assurance_summary(mart).set_index("risk_domain")

    assert result.loc["Access"].to_dict() == {
        "assurance_tests": 2,
        "sufficient_evidence": 1,
        "weak_evidence": 1,
        "stale_evidence": 1,
        "high_or_critical_residual_risk": 1,
        "not_evaluable_residual_risk": 0,
    }
    assert result.loc["Third Party"].to_dict() == {
        "assurance_tests": 2,
        "sufficient_evidence": 1,
        "weak_evidence": 1,
        "stale_evidence": 1,
        "high_or_critical_residual_risk": 1,
        "not_evaluable_residual_risk": 1,
    }


def test_build_finding_remediation_priority_view_preserves_action_grain():
    findings = pd.DataFrame(
        {
            "finding_id": ["F1", "F2", "F3"],
            "system_id": ["S1", "S2", "S3"],
            "finding_theme": ["Theme A", "Theme B", "Theme C"],
            "severity": ["HIGH", "LOW", "MODERATE"],
            "status": ["OPEN", "CLOSED", "OPEN"],
            "repeat_finding": [True, False, False],
            "prior_finding_id": ["F0", pd.NA, pd.NA],
        }
    )
    remediation = pd.DataFrame(
        {
            "finding_id": ["F1", "F1", "F2"],
            "action_id": ["A1", "A2", "A3"],
            "action_owner": ["Owner 1", "Owner 2", "Owner 3"],
            "target_date": ["2026-09-29", "2026-10-01", "2026-09-20"],
            "status": ["OPEN", "IN_PROGRESS", "CLOSED"],
            "overdue": [True, False, False],
            "days_overdue": [1, 0, 0],
            "closure_validation_status": [
                "NOT_APPLICABLE",
                "NOT_APPLICABLE",
                "VALIDATED",
            ],
        }
    )

    result = build_finding_remediation_priority_view(findings, remediation)

    assert result["finding_id"].tolist() == ["F1", "F1", "F3"]
    assert result["action_id"].tolist()[:2] == ["A1", "A2"]
    assert pd.isna(result["action_id"].iloc[2])
    assert result["overdue"].fillna(False).sum() == 1
    assert result["repeat_finding"].sum() == 2
