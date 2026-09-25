import json

import pandas as pd
import pytest

from experian_workflow.ingestion import load_expenses, load_policy, load_vendors
from experian_workflow.quality import StructuralValidationError, validate_records, validate_source_structure
from experian_workflow.transformation import enrich_audit_flags


def load_inputs():
    policy = load_policy("config/expense_policy.yaml")
    expenses = load_expenses("data/source/expenses.csv")
    vendors = load_vendors("data/source/vendors.db")
    return policy, expenses, vendors


def test_missing_required_column_fails_structural_contract():
    policy, expenses, vendors = load_inputs()
    broken = expenses.drop(columns=["transaction_id"])
    with pytest.raises(StructuralValidationError, match="transaction_id"):
        validate_source_structure(broken, vendors, policy)


def test_injected_defects_are_quarantined_and_rows_reconcile():
    policy, expenses, vendors = load_inputs()
    validate_source_structure(expenses, vendors, policy)
    accepted, quarantine = validate_records(expenses, vendors, policy)
    oracle = json.loads(open("data/source/ground_truth.json", encoding="utf-8").read())["injected_data_defects"]
    actual = {
        "duplicate_transaction_id": int((quarantine["failed_control_ids"] == "DQ003").sum()),
        "missing_transaction_id": int((quarantine["failed_control_ids"] == "DQ002").sum()),
        "invalid_amount": int((quarantine["failed_control_ids"] == "DQ004").sum()),
        "future_transaction_date": int((quarantine["failed_control_ids"] == "DQ005").sum()),
        "unknown_vendor": int((quarantine["failed_control_ids"] == "DQ006").sum()),
    }
    assert actual == oracle
    assert len(expenses) == len(accepted) + len(quarantine)
    assert len(quarantine) == 5


def test_valid_audit_examples_remain_trusted_and_are_flagged():
    policy, expenses, vendors = load_inputs()
    validate_source_structure(expenses, vendors, policy)
    accepted, quarantine = validate_records(expenses, vendors, policy)
    curated = enrich_audit_flags(accepted, vendors, policy)
    oracle = json.loads(open("data/source/ground_truth.json", encoding="utf-8").read())["injected_valid_audit_examples"]
    assert len(curated) == len(accepted)
    assert not set(oracle["policy_limit_breach_transaction_ids"]).intersection(set(quarantine["transaction_id"].dropna()))
    assert not set(oracle["high_risk_vendor_transaction_ids"]).intersection(set(quarantine["transaction_id"].dropna()))
    assert not set(oracle["inactive_vendor_transaction_ids"]).intersection(set(quarantine["transaction_id"].dropna()))
    indexed = curated.set_index("transaction_id")
    assert indexed.loc[oracle["policy_limit_breach_transaction_ids"], "policy_exception"].all()
    assert indexed.loc[oracle["high_risk_vendor_transaction_ids"], "high_risk_vendor"].all()
    assert indexed.loc[oracle["inactive_vendor_transaction_ids"], "inactive_vendor"].all()


def test_duplicate_vendor_reference_blocks_unsafe_enrichment():
    policy, expenses, vendors = load_inputs()
    validate_source_structure(expenses, vendors, policy)
    accepted, _ = validate_records(expenses, vendors, policy)
    duplicated_vendors = pd.concat([vendors, vendors.iloc[[0]]], ignore_index=True)
    with pytest.raises(pd.errors.MergeError):
        enrich_audit_flags(accepted, duplicated_vendors, policy)
