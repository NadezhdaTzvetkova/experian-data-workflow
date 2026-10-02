from pathlib import Path

import pandas as pd
import pytest

from experian_workflow.assurance.ingestion import load_control_evidence
from experian_workflow.assurance.quality import (
    StructuralValidationError,
    assert_structurally_usable,
    validate_control_evidence_contract,
    validate_control_evidence_population,
    validate_unique_key,
)

ROOT = Path(__file__).resolve().parents[1]
ASSURANCE_SOURCE = ROOT / "data" / "source" / "assurance"
ADVERSARIAL_SOURCE = ASSURANCE_SOURCE / "adversarial"


def test_additive_control_evidence_schema_is_compatible() -> None:
    payload, frame = load_control_evidence(
        ADVERSARIAL_SOURCE / "control_evidence_additive.json"
    )

    results = validate_control_evidence_contract(payload, frame)
    population = validate_control_evidence_population(frame)

    assert [result.status for result in results] == ["PASS", "PASS"]
    assert population.status == "PASS"
    assert "review_note" in frame.columns

    assert_structurally_usable([*results, population])


def test_breaking_control_evidence_schema_blocks_trusted_use() -> None:
    payload, frame = load_control_evidence(
        ADVERSARIAL_SOURCE / "control_evidence_breaking.json"
    )

    contract_results = validate_control_evidence_contract(payload, frame)
    population = validate_control_evidence_population(frame)

    assert contract_results[0].status == "FAIL"
    assert contract_results[0].reason_code == "UNSUPPORTED_SCHEMA_VERSION"

    assert contract_results[1].status == "FAIL"
    assert contract_results[1].reason_code == "MISSING_REQUIRED_COLUMNS"

    assert population.status == "NOT_EVALUABLE"
    assert population.reason_code == "MISSING_POPULATION_PREREQUISITE"

    with pytest.raises(
        StructuralValidationError,
        match="Assurance structural validation blocked",
    ):
        assert_structurally_usable([*contract_results, population])


def test_unique_key_is_not_evaluable_when_key_column_is_missing() -> None:
    frame = pd.DataFrame(
        {
            "control_id": ["CTRL_ACCESS_01"],
        }
    )

    result = validate_unique_key(
        frame,
        dataset="control_evidence",
        key_columns=["test_id"],
        control_id="DQ_EVIDENCE_TEST_KEY",
    )

    assert result.status == "NOT_EVALUABLE"
    assert result.blocking is True
    assert result.reason_code == "MISSING_KEY_PREREQUISITE"


def test_duplicate_key_fails_without_silent_deduplication() -> None:
    frame = pd.DataFrame(
        {
            "test_id": ["TEST_001", "TEST_001"],
        }
    )

    result = validate_unique_key(
        frame,
        dataset="control_evidence",
        key_columns=["test_id"],
        control_id="DQ_EVIDENCE_TEST_KEY",
    )

    assert result.status == "FAIL"
    assert result.blocking is True
    assert result.reason_code == "DUPLICATE_KEY"
    assert result.affected_ids == ("0", "1")
