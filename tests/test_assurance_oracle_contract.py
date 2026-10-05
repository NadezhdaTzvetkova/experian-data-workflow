from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
SCENARIOS = FIXTURES / "assurance_scenarios.yaml"
ORACLE = FIXTURES / "assurance_expected_results.json"

EXPECTED_SCENARIOS = {
    "SCN_ACQ_MAPPING_GAP",
    "SCN_INCOMPLETE_COVERAGE",
    "SCN_STALE_IAM_EVIDENCE",
    "SCN_THIRD_PARTY_OVERDUE",
    "SCN_SCHEMA_DRIFT",
    "SCN_REPEAT_FINDING",
}


def _load_scenarios() -> dict:
    with SCENARIOS.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_oracle() -> dict:
    with ORACLE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_scenario_and_oracle_inventory_is_complete_and_aligned() -> None:
    scenario_doc = _load_scenarios()
    oracle = _load_oracle()

    scenario_ids = {
        item["scenario_id"]
        for item in scenario_doc["scenarios"]
    }

    assert scenario_ids == EXPECTED_SCENARIOS
    assert set(oracle["scenarios"]) == EXPECTED_SCENARIOS
    assert oracle["oracle_role"] == "test_and_review_only"
    assert oracle["production_runtime_dependency_allowed"] is False
    assert oracle["methodology_version"] == scenario_doc["methodology_version"]
    assert oracle["as_of_date"] == scenario_doc["as_of_date"]


def test_iam_oracle_uses_real_evidence_identifiers() -> None:
    oracle = _load_oracle()
    scenario = oracle["scenarios"]["SCN_STALE_IAM_EVIDENCE"]

    assert set(scenario["expected_records"]["current_evidence_ids"]) == {
        "EVD_IAM_FRESH",
        "EVD_IAM_BOUNDARY",
        "EVD_IAM_NEGATIVE",
    }
    assert set(scenario["expected_records"]["stale_evidence_ids"]) == {
        "EVD_IAM_STALE",
    }


def test_schema_drift_oracle_uses_terminal_manifest_publication_semantics() -> None:
    scenario_doc = _load_scenarios()
    oracle = _load_oracle()

    scenario_fixture = next(
        item
        for item in scenario_doc["scenarios"]
        if item["scenario_id"] == "SCN_SCHEMA_DRIFT"
    )
    oracle_scenario = oracle["scenarios"]["SCN_SCHEMA_DRIFT"]

    fixture_text = json.dumps(scenario_fixture, sort_keys=True)
    oracle_text = json.dumps(oracle_scenario, sort_keys=True)

    forbidden_legacy_terms = (
        "candidate_publishable",
        "breaking_candidate_blocks_trusted_publication",
        "last_known_good",
    )

    for term in forbidden_legacy_terms:
        assert term not in fixture_text
        assert term not in oracle_text

    publication = oracle_scenario["expected_publication_effect"]
    assert publication["breaking_run_manifest_written"] is False
    assert publication["failed_run_is_published"] is False
    assert publication["default_successful_run_contaminated"] is False
