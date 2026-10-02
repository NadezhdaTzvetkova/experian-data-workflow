from pathlib import Path

import pytest
import yaml

from experian_workflow.assurance.ingestion import load_control_evidence
from experian_workflow.assurance.reconciliation import (
    ReconciliationError,
    load_reconciliation_contract,
    reconcile_control_evidence,
    summarize_reconciliation,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'assurance' / 'reconciliation.yaml'
EVIDENCE = ROOT / 'data' / 'source' / 'assurance' / 'control_evidence.json'


def _inputs():
    contract = load_reconciliation_contract(CONFIG)
    _, evidence = load_control_evidence(EVIDENCE)
    return contract, evidence


def test_reconciliation_preserves_exact_stage_accounting():
    contract, evidence = _inputs()
    result = reconcile_control_evidence(
        evidence,
        contract,
        structural_contract_status='PASS',
    )
    summary = summarize_reconciliation(result)
    assert summary == {
        'status': 'PASS',
        'record_count': 9,
        'expected_population': 291,
        'received_population': 291,
        'not_received_population': 0,
        'structurally_valid_population': 291,
        'structurally_rejected_population': 0,
        'mapped_population': 281,
        'unmapped_population': 10,
        'testable_population': 281,
        'not_testable_population': 0,
        'evaluated_population': 253,
        'not_tested_population': 28,
    }
    by_test = result.set_index('test_id')
    assert by_test.loc['TEST_MAP_001', 'unmapped_population'] == 10
    assert by_test.loc['TEST_MAP_001', 'evaluated_population'] == 0
    assert by_test.loc['TEST_COV_001', 'not_tested_population'] == 28
    assert by_test.loc['TEST_COV_002', 'not_tested_population'] == 0
    assert set(result.loc[result['unmapped_population'] > 0, 'test_id']) == {'TEST_MAP_001'}
    assert set(result.loc[result['not_tested_population'] > 0, 'test_id']) == {'TEST_COV_001'}


def test_structural_failure_makes_reconciliation_not_evaluable():
    contract, evidence = _inputs()
    result = reconcile_control_evidence(
        evidence,
        contract,
        structural_contract_status='FAIL',
    )
    assert (result['reconciliation_status'] == 'NOT_EVALUABLE').all()
    assert (result['reconciliation_reason_code'] == 'STRUCTURAL_CONTRACT_FAILURE').all()
    assert result['evaluated_population'].isna().all()
    assert summarize_reconciliation(result) == {
        'status': 'NOT_EVALUABLE',
        'record_count': 9,
    }


@pytest.mark.parametrize(
    ('column', 'value'),
    [
        ('received_population', 101),
        ('mapped_population', 101),
        ('tested_population', 101),
    ],
)
def test_downstream_population_cannot_exceed_upstream(column, value):
    contract, evidence = _inputs()
    broken = evidence.iloc[[0]].copy()
    broken.loc[broken.index[0], column] = value
    result = reconcile_control_evidence(
        broken,
        contract,
        structural_contract_status='PASS',
    )
    assert result.iloc[0]['reconciliation_status'] == 'FAIL'
    assert result.iloc[0]['reconciliation_reason_code'] == 'INVALID_STAGE_ORDER'


def test_non_numeric_population_is_rejected():
    contract, evidence = _inputs()
    broken = evidence.iloc[[0]].copy()
    broken['tested_population'] = broken['tested_population'].astype('object')
    broken.loc[broken.index[0], 'tested_population'] = 'not-a-number'
    with pytest.raises(ReconciliationError, match='Non-numeric population values'):
        reconcile_control_evidence(
            broken,
            contract,
            structural_contract_status='PASS',
        )


def test_contract_drift_is_rejected_by_real_loader(tmp_path):
    raw = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))
    raw['reconciliation_model']['stages']['testable']['derivation'] = 'tested_population'
    broken_path = tmp_path / 'reconciliation.yaml'
    broken_path.write_text(
        yaml.safe_dump(raw, sort_keys=False),
        encoding='utf-8',
    )
    with pytest.raises(
        ReconciliationError,
        match='Unsupported reconciliation semantics for stage: testable',
    ):
        load_reconciliation_contract(broken_path)


def test_negative_population_is_rejected():
    contract, evidence = _inputs()
    broken = evidence.iloc[[0]].copy()
    broken.loc[broken.index[0], 'received_population'] = -1
    result = reconcile_control_evidence(
        broken,
        contract,
        structural_contract_status='PASS',
    )
    assert result.iloc[0]['reconciliation_status'] == 'FAIL'
    assert result.iloc[0]['reconciliation_reason_code'] == 'INVALID_STAGE_ORDER'
