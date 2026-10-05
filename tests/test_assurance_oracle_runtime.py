from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.calculations import (
    detect_repeat_findings,
    enrich_control_assurance,
    enrich_remediation_actions,
    load_assurance_rules,
)
from experian_workflow.assurance.ingestion import (
    load_control_evidence,
    load_enterprise_reference,
    load_findings,
    load_management_actions,
)
from experian_workflow.assurance.normalization import (
    normalize_control_evidence_identity,
)
from experian_workflow.assurance.quality import (
    assert_structurally_usable,
    validate_control_evidence_contract,
    validate_control_evidence_population,
)
from experian_workflow.assurance.reconciliation import (
    load_reconciliation_contract,
    reconcile_control_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source" / "assurance"
ADVERSARIAL = SOURCE / "adversarial"
RULES = ROOT / "config" / "assurance" / "rules.yaml"
RECONCILIATION = ROOT / "config" / "assurance" / "reconciliation.yaml"
ORACLE_PATH = ROOT / "tests" / "fixtures" / "assurance_expected_results.json"


def _oracle() -> dict:
    return json.loads(ORACLE_PATH.read_text(encoding="utf-8"))


def _runtime_assurance():
    tables = load_enterprise_reference(SOURCE / "enterprise.db")
    _, evidence = load_control_evidence(SOURCE / "control_evidence.json")

    normalized = normalize_control_evidence_identity(
        evidence,
        tables["system_mappings"],
        mapping_source_system="enterprise_inventory",
    )

    contract = load_reconciliation_contract(RECONCILIATION)
    reconciled = reconcile_control_evidence(
        normalized,
        contract,
        structural_contract_status="PASS",
    )

    rules = load_assurance_rules(RULES)
    assurance = enrich_control_assurance(
        reconciled,
        rules,
        tables["controls"],
        tables["risk_assignments"],
    )

    return tables, evidence, normalized, assurance, rules


def test_oracle_acquisition_mapping_truth_matches_runtime() -> None:
    oracle = _oracle()["scenarios"]["SCN_ACQ_MAPPING_GAP"]
    _, _, normalized, assurance, _ = _runtime_assurance()

    scenario_rows = normalized.loc[
        normalized["scenario_id"] == "SCN_ACQ_MAPPING_GAP"
    ]

    expected = oracle["expected_records"]

    actual_unmapped = set(
        scenario_rows.loc[
            scenario_rows["identity_status"] == "UNMAPPED",
            "raw_system_id",
        ]
    )
    actual_mapped = set(
        scenario_rows.loc[
            scenario_rows["identity_status"] == "MAPPED",
            "raw_system_id",
        ]
    )
    actual_canonical = set(
        scenario_rows.loc[
            scenario_rows["identity_status"] == "MAPPED",
            "canonical_system_id",
        ].dropna()
    )

    assert actual_unmapped == set(expected["unmapped_raw_system_ids"])
    assert actual_mapped == set(expected["mapped_raw_system_ids"])
    assert actual_canonical == set(expected["mapped_canonical_system_ids"])

    by_raw = scenario_rows.set_index("raw_system_id")
    expected_states = oracle["expected_states"]

    for raw_system_id, state in expected_states.items():
        row = by_raw.loc[raw_system_id]
        assert row["identity_status"] == state["mapping_status"]

        if "canonical_system_id" in state:
            assert row["canonical_system_id"] == state["canonical_system_id"]

    assurance_by_raw = assurance.set_index("raw_system_id")
    unmapped_state = expected_states["ACQ_SYS_LEGACY_77"]

    assert (
        assurance_by_raw.loc[
            "ACQ_SYS_LEGACY_77",
            "evidence_sufficiency",
        ]
        == unmapped_state["downstream_assurance_state"]
    )
    assert (
        assurance_by_raw.loc[
            "ACQ_SYS_LEGACY_77",
            "evidence_sufficiency_reason_code",
        ]
        == unmapped_state["reason_code"]
    )


def test_oracle_incomplete_coverage_truth_matches_runtime() -> None:
    oracle = _oracle()["scenarios"]["SCN_INCOMPLETE_COVERAGE"]
    _, _, _, assurance, _ = _runtime_assurance()

    scenario_rows = assurance.loc[
        assurance["scenario_id"] == "SCN_INCOMPLETE_COVERAGE"
    ].set_index("test_id")

    expected_records = oracle["expected_records"]

    actual_partial = set(
        scenario_rows.loc[
            scenario_rows["coverage_state"] == "PARTIAL"
        ].index
    )
    actual_sufficient = set(
        scenario_rows.loc[
            scenario_rows["coverage_state"] == "SUFFICIENT"
        ].index
    )

    assert actual_partial == set(expected_records["partial_coverage_test_ids"])
    assert actual_sufficient == set(expected_records["full_coverage_test_ids"])

    for test_id, expected in oracle["expected_states"].items():
        row = scenario_rows.loc[test_id]

        for field in (
            "expected_population",
            "tested_population",
            "coverage_ratio",
            "coverage_state",
            "evidence_sufficiency",
            "control_effectiveness",
        ):
            if field in expected:
                assert row[field] == expected[field]

        if "residual_risk" in expected:
            assert row["residual_risk"] == expected["residual_risk"]

        if "residual_risk_reason" in expected:
            assert (
                row["residual_risk_reason_code"]
                == expected["residual_risk_reason"]
            )


def test_oracle_stale_iam_truth_matches_runtime() -> None:
    oracle = _oracle()["scenarios"]["SCN_STALE_IAM_EVIDENCE"]
    _, _, _, assurance, _ = _runtime_assurance()

    scenario_runtime = assurance.loc[
        assurance["scenario_id"] == "SCN_STALE_IAM_EVIDENCE"
    ].copy()

    assert "evidence_id" in scenario_runtime.columns
    assert scenario_runtime["evidence_id"].notna().all()
    assert scenario_runtime["evidence_id"].is_unique

    by_evidence = scenario_runtime.set_index("evidence_id")
    expected_records = oracle["expected_records"]

    actual_current = set(
        by_evidence.loc[
            by_evidence["freshness_state"] == "CURRENT"
        ].index
    )
    actual_stale = set(
        by_evidence.loc[
            by_evidence["freshness_state"] == "STALE"
        ].index
    )

    assert actual_current == set(expected_records["current_evidence_ids"])
    assert actual_stale == set(expected_records["stale_evidence_ids"])

    for evidence_id, expected in oracle["expected_states"].items():
        row = by_evidence.loc[evidence_id]

        if "age_days" in expected:
            assert row["evidence_age_days"] == expected["age_days"]

        assert row["freshness_state"] == expected["freshness"]

        if "evidence_sufficiency" in expected:
            assert (
                row["evidence_sufficiency"]
                == expected["evidence_sufficiency"]
            )

        if "control_effectiveness" in expected:
            assert (
                row["control_effectiveness"]
                == expected["control_effectiveness"]
            )

        if "reason_code" in expected:
            assert (
                row["control_effectiveness_reason_code"]
                == expected["reason_code"]
            )


def test_oracle_third_party_overdue_truth_matches_runtime() -> None:
    oracle = _oracle()["scenarios"]["SCN_THIRD_PARTY_OVERDUE"]
    _, _, _, _, rules = _runtime_assurance()

    actions = load_management_actions(SOURCE / "management_actions.csv")
    scenario_actions = actions.loc[
        actions["scenario_id"] == "SCN_THIRD_PARTY_OVERDUE"
    ]
    runtime = enrich_remediation_actions(scenario_actions, rules)

    expected_records = oracle["expected_records"]

    actual_overdue = set(
        runtime.loc[runtime["overdue"], "action_id"]
    )
    actual_not_overdue = set(
        runtime.loc[~runtime["overdue"], "action_id"]
    )

    assert actual_overdue == set(expected_records["overdue_action_ids"])
    assert actual_not_overdue == set(expected_records["not_overdue_action_ids"])

    by_action = runtime.set_index("action_id")

    for action_id, expected in oracle["expected_states"].items():
        row = by_action.loc[action_id]
        assert bool(row["overdue"]) is expected["overdue"]
        assert row["days_overdue"] == expected["days_overdue"]


def test_oracle_repeat_finding_truth_matches_runtime() -> None:
    oracle = _oracle()["scenarios"]["SCN_REPEAT_FINDING"]
    _, _, _, _, rules = _runtime_assurance()

    findings = load_findings(SOURCE / "findings.csv")
    runtime = detect_repeat_findings(findings, rules)

    expected_records = oracle["expected_records"]

    actual_repeat = set(
        runtime.loc[runtime["repeat_finding"], "finding_id"]
    )

    assert actual_repeat == set(expected_records["repeat_finding_ids"])

    expected_non_repeat = set(expected_records["non_repeat_finding_ids"])
    actual_non_repeat = set(
        runtime.loc[
            runtime["finding_id"].isin(expected_non_repeat)
            & ~runtime["repeat_finding"],
            "finding_id",
        ]
    )
    assert actual_non_repeat == expected_non_repeat

    by_finding = runtime.set_index("finding_id")

    for finding_id, expected in oracle["expected_states"].items():
        row = by_finding.loc[finding_id]
        assert bool(row["repeat_finding"]) is expected["repeat"]
        assert row["recurrence_key"] == expected["recurrence_key"]

        if "prior_finding_id" in expected:
            assert row["prior_finding_id"] == expected["prior_finding_id"]


def test_oracle_schema_drift_truth_matches_runtime() -> None:
    oracle = _oracle()["scenarios"]["SCN_SCHEMA_DRIFT"]
    expected_states = oracle["expected_states"]

    breaking_payload, breaking_frame = load_control_evidence(
        ADVERSARIAL / "control_evidence_breaking.json"
    )
    breaking_contract = validate_control_evidence_contract(
        breaking_payload,
        breaking_frame,
    )
    breaking_population = validate_control_evidence_population(
        breaking_frame
    )

    breaking_expected = expected_states["CONTROL_EVIDENCE_BREAKING_V2"]

    assert breaking_contract[0].status == breaking_expected["structural_status"]
    assert breaking_contract[1].status == breaking_expected["structural_status"]
    assert (
        breaking_contract[1].reason_code
        == "MISSING_REQUIRED_COLUMNS"
    )
    assert (
        breaking_expected["missing_required_field"]
        not in breaking_frame.columns
    )
    assert breaking_population.status == breaking_expected["downstream_state"]
    assert breaking_expected["terminal_manifest_eligible"] is False

    additive_payload, additive_frame = load_control_evidence(
        ADVERSARIAL / "control_evidence_additive.json"
    )
    additive_contract = validate_control_evidence_contract(
        additive_payload,
        additive_frame,
    )
    additive_population = validate_control_evidence_population(
        additive_frame
    )

    additive_expected = expected_states["CONTROL_EVIDENCE_ADDITIVE_V1"]

    assert [result.status for result in additive_contract] == [
        additive_expected["structural_status"],
        additive_expected["structural_status"],
    ]
    assert additive_population.status == additive_expected["structural_status"]
    assert additive_expected["added_optional_field"] in additive_frame.columns
    assert (
        additive_expected["terminal_manifest_eligible_if_other_gates_pass"]
        is True
    )

    assert_structurally_usable(
        [*additive_contract, additive_population]
    )


def test_oracle_terminal_manifest_failure_semantics_match_runtime(
    monkeypatch,
) -> None:
    publication = _oracle()["scenarios"]["SCN_SCHEMA_DRIFT"][
        "expected_publication_effect"
    ]

    runs_dir = ROOT / "output" / "assurance_runs"
    before = {
        path.name
        for path in runs_dir.iterdir()
        if path.is_dir()
    }

    def fail_report(*args, **kwargs):
        raise RuntimeError("oracle publication failure")

    monkeypatch.setattr(
        pipeline,
        "build_assurance_report",
        fail_report,
    )

    created: list[Path] = []
    try:
        with pytest.raises(RuntimeError, match="oracle publication failure"):
            pipeline.run_assurance_pipeline(ROOT)

        created = [
            path
            for path in runs_dir.iterdir()
            if path.is_dir() and path.name not in before
        ]

        assert len(created) == 1
        failed_run = created[0]

        assert (
            (failed_run / "manifest.json").exists()
            is publication["breaking_run_manifest_written"]
        )
        assert not (failed_run / "assurance_report.html").exists()
        assert not (failed_run / "publication" / "html").exists()
        assert not (failed_run / "publication" / "tableau").exists()
        assert not (failed_run / "publication" / "powerpoint").exists()
        assert publication["failed_run_is_published"] is False
    finally:
        for path in created:
            shutil.rmtree(path, ignore_errors=True)

def test_production_runtime_does_not_depend_on_test_oracle() -> None:
    production_root = ROOT / "src" / "experian_workflow" / "assurance"

    forbidden = (
        "assurance_expected_results.json",
        "assurance_scenarios.yaml",
        "SCN_ACQ_MAPPING_GAP",
        "SCN_INCOMPLETE_COVERAGE",
        "SCN_STALE_IAM_EVIDENCE",
        "SCN_THIRD_PARTY_OVERDUE",
        "SCN_SCHEMA_DRIFT",
        "SCN_REPEAT_FINDING",
    )

    for path in production_root.glob("*.py"):
        text = path.read_text(encoding="utf-8")

        for token in forbidden:
            assert token not in text, (
                f"Production runtime unexpectedly depends on test/scenario "
                f"truth: {token!r} found in {path.name}"
            )
