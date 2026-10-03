import pandas as pd

from experian_workflow.assurance.reporting import build_assurance_kpis


def test_build_assurance_kpis_counts_trusted_states():
    assurance = pd.DataFrame(
        {
            "evidence_sufficiency": ["SUFFICIENT", "PARTIAL", "INSUFFICIENT", "NOT_EVALUABLE"],
            "freshness_state": ["CURRENT", "CURRENT", "STALE", "CURRENT"],
            "identity_status": ["MAPPED", "MAPPED", "MAPPED", "UNMAPPED"],
            "residual_risk": ["HIGH", "LOW", "NOT_EVALUABLE", "NOT_EVALUABLE"],
        }
    )
    remediation = pd.DataFrame({"overdue": [True, False]})
    findings = pd.DataFrame(
        {
            "repeat_finding": [True, False, False],
            "status": ["OPEN", "IN_PROGRESS", "CLOSED"],
        }
    )

    assert build_assurance_kpis(assurance, remediation, findings) == {
        "assurance_tests": 4,
        "sufficient_evidence": 1,
        "partial_evidence": 1,
        "insufficient_evidence": 1,
        "not_evaluable_evidence": 1,
        "stale_evidence": 1,
        "unmapped_tests": 1,
        "high_or_critical_residual_risk": 1,
        "not_evaluable_residual_risk": 2,
        "overdue_actions": 1,
        "repeat_findings": 1,
        "open_findings": 2,
    }



def test_build_assurance_reporting_mart_preserves_grain_and_unmapped_state():
    from experian_workflow.assurance.reporting import build_assurance_reporting_mart

    assurance = pd.DataFrame(
        {
            "test_id": ["T1", "T2"],
            "reporting_period": ["2026-09", "2026-09"],
            "canonical_system_id": ["SYS_1", pd.NA],
            "control_id": ["CTRL_1", "CTRL_1"],
            "risk_id": ["RSK_1", "RSK_1"],
        }
    )
    systems = pd.DataFrame(
        {
            "system_id": ["SYS_1"],
            "entity_id": ["ENT_1"],
            "system_name": ["System One"],
            "system_owner": ["Owner"],
            "criticality": ["HIGH"],
            "data_classification": ["CONFIDENTIAL"],
            "contains_sensitive_data": [1],
            "core_acquired_status": ["CORE"],
            "acquisition_cohort": [pd.NA],
            "third_party_dependency_flag": [0],
        }
    )
    entities = pd.DataFrame(
        {
            "entity_id": ["ENT_1"],
            "entity_name": ["Entity One"],
            "region": ["EU"],
            "country": ["BG"],
            "business_unit": ["BU"],
            "acquired_status": ["CORE"],
        }
    )
    controls = pd.DataFrame(
        {
            "control_id": ["CTRL_1"],
            "control_name": ["Control One"],
            "control_objective": ["Objective"],
            "control_type": ["DETECTIVE"],
            "expected_frequency": ["MONTHLY"],
        }
    )
    risk_taxonomy = pd.DataFrame(
        {
            "risk_id": ["RSK_1"],
            "risk_domain": ["ACCESS"],
            "risk_name": ["Access Risk"],
            "risk_description": ["Description"],
        }
    )

    mart = build_assurance_reporting_mart(
        assurance, systems, entities, controls, risk_taxonomy
    )

    assert len(mart) == 2
    assert mart[["test_id", "reporting_period"]].drop_duplicates().shape[0] == 2
    assert mart.loc[mart["test_id"].eq("T1"), "system_name"].item() == "System One"
    assert pd.isna(mart.loc[mart["test_id"].eq("T2"), "system_name"].item())



def test_cross_check_headline_kpis_matches_expected_counts():
    from experian_workflow.assurance.reporting import cross_check_headline_kpis

    assurance = pd.DataFrame(
        {
            "evidence_sufficiency": ["SUFFICIENT", "SUFFICIENT", "PARTIAL", "NOT_EVALUABLE"],
            "freshness_state": ["CURRENT", "STALE", "CURRENT", "STALE"],
            "identity_status": ["MAPPED", "MAPPED", "MAPPED", "UNMAPPED"],
            "residual_risk": ["HIGH", "LOW", "NOT_EVALUABLE", "NOT_EVALUABLE"],
        }
    )

    remediation = pd.DataFrame({"overdue": [True, False]})
    findings = pd.DataFrame(
        {
            "repeat_finding": [True, False, False],
            "status": ["OPEN", "IN_PROGRESS", "CLOSED"],
        }
    )

    assert cross_check_headline_kpis(assurance, remediation, findings) == {
        "assurance_tests": 4,
        "sufficient_evidence": 2,
        "partial_evidence": 1,
        "insufficient_evidence": 0,
        "not_evaluable_evidence": 1,
        "stale_evidence": 2,
        "unmapped_tests": 1,
        "high_or_critical_residual_risk": 1,
        "not_evaluable_residual_risk": 2,
        "overdue_actions": 1,
        "repeat_findings": 1,
        "open_findings": 2,
    }



def test_build_assurance_report_generates_self_contained_html(tmp_path):
    import json
    from pathlib import Path

    from experian_workflow.assurance.ingestion import load_enterprise_reference
    from experian_workflow.assurance.pipeline import build_trusted_assurance_outputs
    from experian_workflow.assurance.reporting import (
        build_assurance_report,
        build_assurance_reporting_mart,
    )

    root = Path(__file__).resolve().parents[1]
    assurance, remediation, findings, evidence = build_trusted_assurance_outputs(root)

    run_dir = root / "output" / "assurance_runs" / "_pytest_report_fixture"
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        assurance.to_parquet(run_dir / "control_assurance.parquet", index=False)
        remediation.to_csv(run_dir / "remediation_actions.csv", index=False, lineterminator="\n")
        findings.to_csv(run_dir / "findings.csv", index=False, lineterminator="\n")

        reference = load_enterprise_reference(
            root / "data" / "source" / "assurance" / "enterprise.db"
        )
        mart = build_assurance_reporting_mart(
            assurance,
            reference["systems"],
            reference["entities"],
            reference["controls"],
            reference["risk_taxonomy"],
        )
        mart.to_parquet(
            run_dir / "assurance_reporting_mart.parquet", index=False
        )

        manifest = {
            "run_id": "pytest-report",
            "status": "SUCCESS",
            "methodology": evidence["methodology"],
            "reporting": evidence["reporting"],
            "controls": {"reconciliation": evidence["reconciliation"]},
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        output = tmp_path / "assurance_report.html"
        result = build_assurance_report(run_dir, output, manifest)
        html = result.read_text(encoding="utf-8")

        assert result == output
        assert result.exists()
        assert html.startswith("<!DOCTYPE html>")
        assert "Enterprise Assurance Analytics Report" in html
        assert "Independent KPI reconciliation" in html
        assert "Synthetic demonstration methodology; not Experian internal methodology." in html
        assert "plotly.js" in html.lower()
        assert '<script src="https://cdn.plot.ly' not in html.lower()
        assert not result.read_bytes().startswith(b"\xef\xbb\xbf")
    finally:
        import shutil

        shutil.rmtree(run_dir, ignore_errors=True)
