from pathlib import Path

import pandas as pd
import pytest

from experian_workflow.assurance.ingestion import (
    load_control_evidence,
    load_enterprise_reference,
)
from experian_workflow.assurance.normalization import (
    CanonicalMappingError,
    normalize_control_evidence_identity,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'source' / 'assurance'


def _load_inputs():
    tables = load_enterprise_reference(SOURCE / 'enterprise.db')
    _, evidence = load_control_evidence(SOURCE / 'control_evidence.json')
    return tables, evidence


def test_identity_normalization_preserves_exact_membership():
    tables, evidence = _load_inputs()
    normalized = normalize_control_evidence_identity(
        evidence,
        tables['system_mappings'],
        mapping_source_system='enterprise_inventory',
    )
    assert len(normalized) == len(evidence) == 9
    assert normalized['test_id'].is_unique
    by_test = normalized.set_index('test_id')
    assert by_test.loc['TEST_MAP_001', 'raw_system_id'] == 'ACQ_SYS_LEGACY_77'
    assert by_test.loc['TEST_MAP_001', 'identity_status'] == 'UNMAPPED'
    assert by_test.loc['TEST_MAP_001', 'identity_reason_code'] == 'UNRESOLVED_MAPPING'
    assert pd.isna(by_test.loc['TEST_MAP_001', 'canonical_system_id'])
    assert by_test.loc['TEST_MAP_002', 'raw_system_id'] == 'ACQ_SYS_LEGACY_42'
    assert by_test.loc['TEST_MAP_002', 'identity_status'] == 'MAPPED'
    assert by_test.loc['TEST_MAP_002', 'canonical_system_id'] == 'SYS_ACQ_01'
    unmapped = set(normalized.loc[normalized['identity_status'] == 'UNMAPPED', 'test_id'])
    assert unmapped == {'TEST_MAP_001'}


def test_null_raw_system_id_is_rejected():
    tables, evidence = _load_inputs()
    broken = evidence.iloc[[0]].copy()
    broken.loc[broken.index[0], 'raw_system_id'] = pd.NA
    with pytest.raises(CanonicalMappingError, match='missing or blank raw_system_id'):
        normalize_control_evidence_identity(
            broken,
            tables['system_mappings'],
            mapping_source_system='enterprise_inventory',
        )


def test_blank_raw_system_id_is_rejected():
    tables, evidence = _load_inputs()
    broken = evidence.iloc[[0]].copy()
    broken.loc[broken.index[0], 'raw_system_id'] = '   '
    with pytest.raises(CanonicalMappingError, match='missing or blank raw_system_id'):
        normalize_control_evidence_identity(
            broken,
            tables['system_mappings'],
            mapping_source_system='enterprise_inventory',
        )


def test_missing_mapping_namespace_is_rejected():
    tables, evidence = _load_inputs()
    with pytest.raises(CanonicalMappingError, match='No system mappings found'):
        normalize_control_evidence_identity(
            evidence,
            tables['system_mappings'],
            mapping_source_system='DOES_NOT_EXIST',
        )


def test_duplicate_mapping_reference_is_rejected_before_fanout():
    tables, evidence = _load_inputs()
    duplicate_mappings = pd.concat(
        [
            tables['system_mappings'],
            tables['system_mappings'].loc[
                tables['system_mappings']['raw_system_id'] == 'CORE_PAY_01'
            ],
        ],
        ignore_index=True,
    )
    with pytest.raises(CanonicalMappingError, match='not many-to-one'):
        normalize_control_evidence_identity(
            evidence,
            duplicate_mappings,
            mapping_source_system='enterprise_inventory',
        )
