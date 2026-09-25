from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from experian_workflow.analytics import build_audit_summary, verify_headline_kpis
from experian_workflow.evidence import git_commit, git_is_dirty, sha256_file
from experian_workflow.ingestion import load_expenses, load_policy, load_vendors
from experian_workflow.quality import validate_records, validate_source_structure
from experian_workflow.transformation import enrich_audit_flags


def run_pipeline(root: Path | str = ".") -> dict[str, object]:
    root = Path(root).resolve()
    policy_path = root / "config" / "expense_policy.yaml"
    expenses_path = root / "data" / "source" / "expenses.csv"
    vendors_path = root / "data" / "source" / "vendors.db"

    started_at = datetime.now(UTC)
    run_id = started_at.strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = root / "output" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    policy = load_policy(policy_path)
    expenses = load_expenses(expenses_path)
    vendors = load_vendors(vendors_path)
    validate_source_structure(expenses, vendors, policy)

    accepted, quarantine = validate_records(expenses, vendors, policy)
    curated = enrich_audit_flags(accepted, vendors, policy)

    source_count = len(expenses)
    accepted_count = len(accepted)
    quarantined_count = len(quarantine)
    curated_count = len(curated)

    row_reconciliation_passed = source_count == accepted_count + quarantined_count
    enrichment_cardinality_passed = accepted_count == curated_count
    if not row_reconciliation_passed or not enrichment_cardinality_passed:
        raise RuntimeError("Reconciliation failed; trusted outputs will not be published")

    quarantine_path = run_dir / "quarantine.csv"
    curated_path = run_dir / "curated_expenses.parquet"
    audit_summary_path = run_dir / "audit_summary.csv"
    manifest_path = run_dir / "manifest.json"
    audit_sql_path = root / "sql" / "audit_summary.sql"

    quarantine.to_csv(quarantine_path, index=False, lineterminator="\n")
    curated.to_parquet(curated_path, index=False)

    audit_summary = build_audit_summary(curated_path, audit_sql_path)
    analytics_check = verify_headline_kpis(curated_path, audit_summary)
    if not analytics_check["match"]:
        raise RuntimeError("Independent SQL/Python KPI reconciliation failed")
    audit_summary.to_csv(audit_summary_path, index=False, lineterminator="\n")

    completed_at = datetime.now(UTC)
    final_status = "SUCCESS_WITH_QUARANTINE" if quarantined_count else "SUCCESS"

    manifest: dict[str, object] = {
        "run_id": run_id,
        "status": final_status,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": completed_at.isoformat(),
        "policy_version": policy["policy_version"],
        "source_inventory": {
            "expenses": {
                "path": expenses_path.relative_to(root).as_posix(),
                "sha256": sha256_file(expenses_path),
                "row_count": source_count,
            },
            "vendors": {
                "path": vendors_path.relative_to(root).as_posix(),
                "sha256": sha256_file(vendors_path),
                "row_count": len(vendors),
            },
            "policy": {
                "path": policy_path.relative_to(root).as_posix(),
                "sha256": sha256_file(policy_path),
            },
        },
        "analytics_definition": {
            "sql_path": audit_sql_path.relative_to(root).as_posix(),
            "sql_sha256": sha256_file(audit_sql_path),
        },
        "analytics_validation": analytics_check,
        "code_identity": {
            "git_commit": git_commit(root),
            "git_dirty": git_is_dirty(root),
        },
        "counts": {
            "source": source_count,
            "accepted": accepted_count,
            "quarantined": quarantined_count,
            "curated": curated_count,
        },
        "controls": {
            "structural_contract": "PASS",
            "record_validation": {
                "DQ002_missing_transaction_id": int((quarantine["failed_control_ids"] == "DQ002").sum()),
                "DQ003_duplicate_transaction_id": int((quarantine["failed_control_ids"] == "DQ003").sum()),
                "DQ004_invalid_amount": int((quarantine["failed_control_ids"] == "DQ004").sum()),
                "DQ005_invalid_or_future_date": int((quarantine["failed_control_ids"] == "DQ005").sum()),
                "DQ006_unknown_vendor": int((quarantine["failed_control_ids"] == "DQ006").sum()),
            },
        },
        "reconciliation": {
            "source_equals_accepted_plus_quarantined": row_reconciliation_passed,
            "accepted_equals_curated_after_enrichment": enrichment_cardinality_passed,
        },
        "audit_flags": {
            "policy_exception_count": int(curated["policy_exception"].sum()),
            "high_risk_vendor_count": int(curated["high_risk_vendor"].sum()),
            "inactive_vendor_count": int(curated["inactive_vendor"].sum()),
            "any_audit_exception_count": int(curated["audit_exception"].sum()),
        },
        "outputs": {
            "quarantine": quarantine_path.relative_to(root).as_posix(),
            "curated": curated_path.relative_to(root).as_posix(),
            "manifest": manifest_path.relative_to(root).as_posix(),
            "audit_summary": audit_summary_path.relative_to(root).as_posix(),
        },
    }

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    manifest = run_pipeline()
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
