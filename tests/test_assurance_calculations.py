from pathlib import Path

import pandas as pd
import pytest

from experian_workflow.assurance.calculations import (
    AssuranceCalculationError,
    calculate_coverage,
    classify_control_effectiveness,
    classify_evidence_sufficiency,
    classify_freshness,
    classify_remediation_overdue,
    derive_residual_risk,
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
from experian_workflow.assurance.reconciliation import (
    load_reconciliation_contract,
    reconcile_control_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'source' / 'assurance'
RULES = ROOT / 'config' / 'assurance' / 'rules.yaml'
RECONCILIATION = ROOT / 'config' / 'assurance' / 'reconciliation.yaml'


def _assurance_inputs():
    tables = load_enterprise_reference(SOURCE / 'enterprise.db')
    _, evidence = load_control_evidence(SOURCE / 'control_evidence.json')
    normalized = normalize_control_evidence_identity(
        evidence,
        tables['system_mappings'],
        mapping_source_system='enterprise_inventory',
    )
    contract = load_reconciliation_contract(RECONCILIATION)
    reconciled = reconcile_control_evidence(
        normalized,
        contract,
        structural_contract_status='PASS',
    )
    rules = load_assurance_rules(RULES)
    return reconciled, rules, tables


def test_deterministic_scenario_states_match_expected_semantics():
    reconciled, rules, tables = _assurance_inputs()
    result = enrich_control_assurance(
        reconciled,
        rules,
        tables['controls'],
        tables['risk_assignments'],
    )
    by_test = result.set_index('test_id')
    assert by_test.loc['TEST_COV_001', 'coverage_ratio'] == 0.72
    assert by_test.loc['TEST_COV_001', 'coverage_state'] == 'PARTIAL'
    assert by_test.loc['TEST_COV_001', 'evidence_sufficiency'] == 'PARTIAL'
    assert by_test.loc['TEST_COV_001', 'control_effectiveness'] == 'EFFECTIVE'
    assert by_test.loc['TEST_COV_001', 'residual_risk'] == 'NOT_EVALUABLE'
    assert by_test.loc['TEST_COV_001', 'residual_risk_reason_code'] == 'INSUFFICIENT_ASSURANCE_BASIS'
    assert by_test.loc['TEST_COV_002', 'coverage_ratio'] == 1.0
    assert by_test.loc['TEST_COV_002', 'evidence_sufficiency'] == 'SUFFICIENT'
    assert by_test.loc['TEST_COV_002', 'control_effectiveness'] == 'EFFECTIVE'
    assert by_test.loc['TEST_COV_002', 'inherent_risk'] == 'MODERATE'
    assert by_test.loc['TEST_COV_002', 'residual_risk'] == 'LOW'
    assert by_test.loc['TEST_MAP_001', 'evidence_sufficiency'] == 'NOT_EVALUABLE'
    assert by_test.loc['TEST_MAP_001', 'evidence_sufficiency_reason_code'] == 'UNRESOLVED_MAPPING'
    assert by_test.loc['TEST_MAP_001', 'control_effectiveness'] == 'NOT_EVALUABLE'


def test_freshness_boundary_is_89_current_90_current_91_stale():
    rules = load_assurance_rules(RULES)
    assert classify_freshness('2026-07-03', rules) == (89, 'CURRENT', None)
    assert classify_freshness('2026-07-02', rules) == (90, 'CURRENT', None)
    assert classify_freshness('2026-07-01', rules) == (91, 'STALE', 'STALE_EVIDENCE')


def test_future_evidence_is_not_evaluable():
    rules = load_assurance_rules(RULES)
    age, state, reason = classify_freshness('2026-10-01', rules)
    assert age == -1
    assert state == 'NOT_EVALUABLE'
    assert reason == 'OUT_OF_PERIOD'


def test_zero_tested_population_remains_not_tested_not_failed():
    rules = load_assurance_rules(RULES)
    ratio, coverage, coverage_reason = calculate_coverage(10, 0, rules)
    assert (ratio, coverage, coverage_reason) == (0.0, 'INSUFFICIENT', 'NOT_TESTED')
    sufficiency, sufficiency_reason = classify_evidence_sufficiency(
        identity_status='MAPPED',
        reconciliation_status='PASS',
        freshness_status='CURRENT',
        coverage_state=coverage,
        tested_population=0,
        rules=rules,
    )
    assert (sufficiency, sufficiency_reason) == ('INSUFFICIENT', 'NOT_TESTED')
    effectiveness, effectiveness_reason = classify_control_effectiveness(
        source_result='PASS',
        tested_population=0,
        evidence_sufficiency=sufficiency,
        evidence_reason_code=sufficiency_reason,
        rules=rules,
    )
    assert (effectiveness, effectiveness_reason) == ('NOT_EVALUABLE', 'NOT_TESTED')


def test_stale_evidence_does_not_fabricate_control_failure():
    reconciled, rules, tables = _assurance_inputs()
    result = enrich_control_assurance(
        reconciled,
        rules,
        tables['controls'],
        tables['risk_assignments'],
    ).set_index('test_id')
    stale = result.loc['TEST_IAM_STALE']
    assert stale['freshness_state'] == 'STALE'
    assert stale['evidence_sufficiency'] == 'INSUFFICIENT'
    assert stale['control_effectiveness'] == 'NOT_EVALUABLE'
    assert stale['control_effectiveness_reason_code'] == 'STALE_EVIDENCE'
    assert stale['control_effectiveness'] != 'INEFFECTIVE'


def test_residual_risk_matrix_is_exhaustive_and_monotonic():
    rules = load_assurance_rules(RULES)
    risk_rank = {'LOW': 0, 'MODERATE': 1, 'HIGH': 2, 'CRITICAL': 3}
    effectiveness_order = ['EFFECTIVE', 'PARTIALLY_EFFECTIVE', 'INEFFECTIVE']
    for inherent in ['LOW', 'MODERATE', 'HIGH', 'CRITICAL']:
        outcomes = [
            derive_residual_risk(
                inherent_risk=inherent,
                control_effectiveness=effectiveness,
                evidence_sufficiency='SUFFICIENT',
                rules=rules,
            )[0]
            for effectiveness in effectiveness_order
        ]
        assert all(state in risk_rank for state in outcomes)
        assert risk_rank[outcomes[0]] <= risk_rank[outcomes[1]] <= risk_rank[outcomes[2]]
    for effectiveness in effectiveness_order:
        outcomes = [
            derive_residual_risk(
                inherent_risk=inherent,
                control_effectiveness=effectiveness,
                evidence_sufficiency='SUFFICIENT',
                rules=rules,
            )[0]
            for inherent in ['LOW', 'MODERATE', 'HIGH', 'CRITICAL']
        ]
        ranks = [risk_rank[state] for state in outcomes]
        assert ranks == sorted(ranks)


def test_insufficient_assurance_basis_blocks_residual_risk():
    rules = load_assurance_rules(RULES)
    state, reason = derive_residual_risk(
        inherent_risk='HIGH',
        control_effectiveness='EFFECTIVE',
        evidence_sufficiency='PARTIAL',
        rules=rules,
    )
    assert state == 'NOT_EVALUABLE'
    assert reason == 'INSUFFICIENT_ASSURANCE_BASIS'


def test_duplicate_control_identity_is_rejected():
    reconciled, rules, tables = _assurance_inputs()
    controls = pd.concat([tables['controls'], tables['controls'].iloc[[0]]], ignore_index=True)
    with pytest.raises(AssuranceCalculationError, match='Duplicate control_id'):
        enrich_control_assurance(
            reconciled,
            rules,
            controls,
            tables['risk_assignments'],
        )


def test_duplicate_risk_assignment_key_is_rejected():
    reconciled, rules, tables = _assurance_inputs()
    assignments = pd.concat(
        [tables['risk_assignments'], tables['risk_assignments'].iloc[[0]]],
        ignore_index=True,
    )
    with pytest.raises(AssuranceCalculationError, match='Duplicate risk-assignment business key'):
        enrich_control_assurance(
            reconciled,
            rules,
            tables['controls'],
            assignments,
        )


def test_unsupported_source_result_is_rejected_when_evaluable():
    rules = load_assurance_rules(RULES)
    with pytest.raises(AssuranceCalculationError, match='Unsupported source_result'):
        classify_control_effectiveness(
            source_result='UNKNOWN',
            tested_population=10,
            evidence_sufficiency='SUFFICIENT',
            evidence_reason_code=None,
            rules=rules,
        )


def test_remediation_overdue_boundary_and_closed_semantics():
    _, rules, _ = _assurance_inputs()
    assert classify_remediation_overdue(
        target_date="2026-09-29", status="OPEN", rules=rules
    ) == (True, 1)
    assert classify_remediation_overdue(
        target_date="2026-09-30", status="OPEN", rules=rules
    ) == (False, 0)
    assert classify_remediation_overdue(
        target_date="2026-10-01", status="IN_PROGRESS", rules=rules
    ) == (False, 0)
    assert classify_remediation_overdue(
        target_date="2026-09-20", status="CLOSED", rules=rules
    ) == (False, 0)


def test_remediation_fixture_membership_matches_expected_truth():
    _, rules, _ = _assurance_inputs()
    actions = load_management_actions(SOURCE / "management_actions.csv")
    result = enrich_remediation_actions(actions, rules)
    overdue_ids = set(result.loc[result["overdue"], "action_id"])
    assert overdue_ids == {"ACT_TP_OVERDUE"}
    by_action = result.set_index("action_id")
    assert by_action.loc["ACT_TP_OVERDUE", "days_overdue"] == 1
    assert by_action.loc["ACT_TP_DUE_TODAY", "days_overdue"] == 0
    assert by_action.loc["ACT_TP_FUTURE", "days_overdue"] == 0
    assert by_action.loc["ACT_TP_CLOSED", "days_overdue"] == 0


def test_unsupported_remediation_status_is_rejected():
    _, rules, _ = _assurance_inputs()
    with pytest.raises(AssuranceCalculationError, match="Unsupported remediation status"):
        classify_remediation_overdue(
            target_date="2026-09-29",
            status="UNKNOWN",
            rules=rules,
        )


def test_duplicate_action_identity_is_rejected():
    _, rules, _ = _assurance_inputs()
    actions = load_management_actions(SOURCE / "management_actions.csv")
    broken = pd.concat([actions, actions.iloc[[0]]], ignore_index=True)
    with pytest.raises(AssuranceCalculationError, match="Duplicate action_id"):
        enrich_remediation_actions(broken, rules)


def test_repeat_finding_membership_uses_stable_key_and_chronology():
    _, rules, _ = _assurance_inputs()
    findings = load_findings(SOURCE / "findings.csv")
    result = detect_repeat_findings(findings, rules)
    repeat_ids = set(result.loc[result["repeat_finding"], "finding_id"])
    assert repeat_ids == {"FND_IAM_006"}
    by_finding = result.set_index("finding_id")
    assert by_finding.loc["FND_IAM_006", "prior_finding_id"] == "FND_IAM_001"
    assert not bool(by_finding.loc["FND_IAM_007", "repeat_finding"])


def test_similar_title_does_not_create_repeat_without_matching_key():
    _, rules, _ = _assurance_inputs()
    findings = load_findings(SOURCE / "findings.csv")
    result = detect_repeat_findings(findings, rules).set_index("finding_id")
    assert findings.loc[findings["finding_id"] == "FND_IAM_007", "finding_theme"].iloc[0].startswith("Privileged access review")
    assert not bool(result.loc["FND_IAM_007", "repeat_finding"])


def test_repeat_requires_prior_closed_before_current_identified_date():
    _, rules, _ = _assurance_inputs()
    findings = load_findings(SOURCE / "findings.csv")
    broken = findings.copy()
    broken.loc[broken["finding_id"] == "FND_IAM_001", "closed_date"] = "2026-09-01"
    result = detect_repeat_findings(broken, rules).set_index("finding_id")
    assert not bool(result.loc["FND_IAM_006", "repeat_finding"])


def test_ambiguous_repeat_priors_are_rejected():
    _, rules, _ = _assurance_inputs()
    findings = load_findings(SOURCE / "findings.csv")
    duplicate_prior = findings.loc[findings["finding_id"] == "FND_IAM_001"].copy()
    duplicate_prior.loc[:, "finding_id"] = "FND_IAM_002"
    duplicate_prior.loc[:, "identified_date"] = "2026-01-10"
    duplicate_prior.loc[:, "closed_date"] = "2026-02-28"
    broken = pd.concat([findings, duplicate_prior], ignore_index=True)
    with pytest.raises(AssuranceCalculationError, match="Ambiguous repeat-finding prior candidates"):
        detect_repeat_findings(broken, rules)


def test_missing_recurrence_key_is_rejected():
    _, rules, _ = _assurance_inputs()
    findings = load_findings(SOURCE / "findings.csv")
    broken = findings.copy()
    broken.loc[broken["finding_id"] == "FND_IAM_006", "recurrence_key"] = ""
    with pytest.raises(AssuranceCalculationError, match="Missing recurrence_key"):
        detect_repeat_findings(broken, rules)
