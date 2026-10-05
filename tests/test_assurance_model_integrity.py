from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from experian_workflow.assurance.ingestion import (
    load_enterprise_reference,
    load_findings,
    load_management_actions,
)
from experian_workflow.assurance.quality import (
    validate_effective_dated_reference_state,
    validate_reference_integrity,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "source" / "assurance"


def _reference() -> dict[str, pd.DataFrame]:
    return load_enterprise_reference(SOURCE_DIR / "enterprise.db")


def _findings() -> pd.DataFrame:
    return load_findings(SOURCE_DIR / "findings.csv")


def _actions() -> pd.DataFrame:
    return load_management_actions(SOURCE_DIR / "management_actions.csv")


def test_reference_integrity_passes_for_canonical_synthetic_model() -> None:
    results = validate_reference_integrity(
        _reference(),
        _findings(),
        _actions(),
    )

    assert results
    assert all(result.status == "PASS" for result in results)
    assert all(result.blocking is False for result in results)


def test_dangling_system_entity_reference_is_blocking() -> None:
    reference = deepcopy(_reference())
    reference["systems"] = reference["systems"].copy()
    reference["systems"].loc[
        reference["systems"].index[0],
        "entity_id",
    ] = "ENT_DOES_NOT_EXIST"

    results = validate_reference_integrity(
        reference,
        _findings(),
        _actions(),
    )

    failure = next(
        result
        for result in results
        if result.control_id == "DQ_SYSTEM_ENTITY_REFERENCE"
    )
    assert failure.status == "FAIL"
    assert failure.blocking is True
    assert failure.reason_code == "MISSING_REFERENCE"


def test_mapped_canonical_system_must_exist() -> None:
    reference = deepcopy(_reference())
    reference["system_mappings"] = reference["system_mappings"].copy()

    mapped_index = reference["system_mappings"].index[
        reference["system_mappings"]["mapping_status"].eq("MAPPED")
    ][0]

    reference["system_mappings"].loc[
        mapped_index,
        "canonical_system_id",
    ] = "SYS_DOES_NOT_EXIST"

    results = validate_reference_integrity(
        reference,
        _findings(),
        _actions(),
    )

    failure = next(
        result
        for result in results
        if result.control_id == "DQ_SYSTEM_MAPPING_CANONICAL_REFERENCE"
    )
    assert failure.status == "FAIL"
    assert failure.blocking is True
    assert failure.reason_code == "MISSING_REFERENCE"


def test_nullable_finding_control_is_allowed() -> None:
    findings = _findings()

    missing_control = (
        findings["control_id"].isna()
        | findings["control_id"].astype("string").str.strip().eq("")
    )
    assert missing_control.any()

    results = validate_reference_integrity(
        _reference(),
        findings,
        _actions(),
    )

    result = next(
        result
        for result in results
        if result.control_id == "DQ_FINDING_CONTROL_REFERENCE"
    )
    assert result.status == "PASS"


def test_dangling_action_finding_reference_is_blocking() -> None:
    actions = _actions().copy()
    actions.loc[actions.index[0], "finding_id"] = "FND_DOES_NOT_EXIST"

    results = validate_reference_integrity(
        _reference(),
        _findings(),
        actions,
    )

    failure = next(
        result
        for result in results
        if result.control_id == "DQ_ACTION_FINDING_REFERENCE"
    )
    assert failure.status == "FAIL"
    assert failure.blocking is True
    assert failure.reason_code == "MISSING_REFERENCE"


def test_effective_dated_reference_state_passes_for_current_model() -> None:
    results = validate_effective_dated_reference_state(
        _reference(),
        as_of_date="2026-09-30",
    )

    assert results
    assert all(result.status == "PASS" for result in results)


@pytest.mark.parametrize(
    ("dataset", "id_column"),
    [
        ("entities", "entity_id"),
        ("systems", "system_id"),
        ("controls", "control_id"),
    ],
)
def test_reference_inactive_before_as_of_date_is_blocking(
    dataset: str,
    id_column: str,
) -> None:
    reference = deepcopy(_reference())
    reference[dataset] = reference[dataset].copy()

    row_index = reference[dataset].index[0]
    reference[dataset].loc[row_index, "effective_to"] = "2026-09-29"
    affected_id = str(reference[dataset].loc[row_index, id_column])

    results = validate_effective_dated_reference_state(
        reference,
        as_of_date="2026-09-30",
    )

    failure = next(
        result
        for result in results
        if result.dataset == dataset and result.status == "FAIL"
    )
    assert failure.blocking is True
    assert failure.reason_code == "REFERENCE_NOT_EFFECTIVE"
    assert affected_id in failure.affected_ids


def test_effective_to_is_inclusive_for_reporting_date() -> None:
    reference = deepcopy(_reference())
    reference["systems"] = reference["systems"].copy()

    reference["systems"].loc[
        reference["systems"].index[0],
        "effective_to",
    ] = "2026-09-30"

    results = validate_effective_dated_reference_state(
        reference,
        as_of_date="2026-09-30",
    )

    system_result = next(
        result
        for result in results
        if result.dataset == "systems"
    )
    assert system_result.status == "PASS"


def test_future_effective_reference_is_blocking() -> None:
    reference = deepcopy(_reference())
    reference["controls"] = reference["controls"].copy()

    reference["controls"].loc[
        reference["controls"].index[0],
        "effective_from",
    ] = "2026-10-01"

    results = validate_effective_dated_reference_state(
        reference,
        as_of_date="2026-09-30",
    )

    control_result = next(
        result
        for result in results
        if result.dataset == "controls"
    )
    assert control_result.status == "FAIL"
    assert control_result.blocking is True
    assert control_result.reason_code == "REFERENCE_NOT_EFFECTIVE"

@pytest.mark.parametrize("as_of_date", ["not-a-date", "NaT"])
def test_invalid_as_of_date_fails_closed(as_of_date: str) -> None:
    results = validate_effective_dated_reference_state(
        _reference(),
        as_of_date=as_of_date,
    )

    assert len(results) == 1
    result = results[0]
    assert result.status == "NOT_EVALUABLE"
    assert result.blocking is True
    assert result.reason_code == "INVALID_AS_OF_DATE"
