import pandas as pd

from experian_workflow.assurance.reporting import cross_check_headline_kpis


def test_cross_check_headline_kpis_covers_all_published_assurance_metrics():
    assurance = pd.DataFrame(
        {
            "evidence_sufficiency": [
                "SUFFICIENT",
                "PARTIAL",
                "INSUFFICIENT",
                "NOT_EVALUABLE",
            ],
            "freshness_state": ["CURRENT", "STALE", "CURRENT", "STALE"],
            "identity_status": ["MAPPED", "MAPPED", "UNMAPPED", "MAPPED"],
            "residual_risk": ["LOW", "HIGH", "CRITICAL", "NOT_EVALUABLE"],
        }
    )
    remediation = pd.DataFrame({"overdue": [True, False, True]})
    findings = pd.DataFrame(
        {
            "repeat_finding": [True, False, False],
            "status": ["OPEN", "IN_PROGRESS", "CLOSED"],
        }
    )

    assert cross_check_headline_kpis(assurance, remediation, findings) == {
        "assurance_tests": 4,
        "sufficient_evidence": 1,
        "partial_evidence": 1,
        "insufficient_evidence": 1,
        "not_evaluable_evidence": 1,
        "stale_evidence": 2,
        "unmapped_tests": 1,
        "high_or_critical_residual_risk": 2,
        "not_evaluable_residual_risk": 1,
        "overdue_actions": 2,
        "repeat_findings": 1,
        "open_findings": 2,
    }
