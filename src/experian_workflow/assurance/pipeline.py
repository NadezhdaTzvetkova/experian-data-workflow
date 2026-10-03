from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

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
    validate_findings_contract,
    validate_management_actions_contract,
    validate_sqlite_contracts,
    validate_unique_key,
)
from experian_workflow.assurance.reconciliation import (
    load_reconciliation_contract,
    reconcile_control_evidence,
    summarize_reconciliation,
)
from experian_workflow.assurance.reporting import (
    build_assurance_report,
    build_assurance_reporting_mart,
)
from experian_workflow.evidence import git_commit, git_is_dirty, sha256_file

MAPPING_SOURCE_SYSTEM = "enterprise_inventory"


def build_trusted_assurance_outputs(
    root: Path | str = ".",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    root = Path(root).resolve()
    source_dir = root / "data" / "source" / "assurance"

    reference = load_enterprise_reference(source_dir / "enterprise.db")
    payload, evidence = load_control_evidence(source_dir / "control_evidence.json")
    findings = load_findings(source_dir / "findings.csv")
    actions = load_management_actions(source_dir / "management_actions.csv")

    quality_results = validate_sqlite_contracts(reference)
    quality_results.extend(validate_control_evidence_contract(payload, evidence))
    quality_results.append(validate_findings_contract(findings))
    quality_results.append(validate_management_actions_contract(actions))
    quality_results.append(
        validate_unique_key(
            evidence,
            dataset="control_evidence",
            key_columns=["test_id", "reporting_period"],
            control_id="DQ_EVIDENCE_BUSINESS_KEY",
        )
    )
    quality_results.append(
        validate_unique_key(
            findings,
            dataset="findings",
            key_columns=["finding_id"],
            control_id="DQ_FINDINGS_BUSINESS_KEY",
        )
    )
    quality_results.append(
        validate_unique_key(
            actions,
            dataset="management_actions",
            key_columns=["action_id"],
            control_id="DQ_ACTIONS_BUSINESS_KEY",
        )
    )
    quality_results.append(validate_control_evidence_population(evidence))
    assert_structurally_usable(quality_results)

    normalized = normalize_control_evidence_identity(
        evidence,
        reference["system_mappings"],
        mapping_source_system=MAPPING_SOURCE_SYSTEM,
    )
    reconciliation_contract = load_reconciliation_contract(
        root / "config" / "assurance" / "reconciliation.yaml"
    )
    reconciled = reconcile_control_evidence(
        normalized,
        reconciliation_contract,
        structural_contract_status="PASS",
    )
    reconciliation_summary = summarize_reconciliation(reconciled)
    if reconciliation_summary["status"] != "PASS":
        raise RuntimeError("Assurance reconciliation failed; trusted outputs will not be published")

    rules = load_assurance_rules(root / "config" / "assurance" / "rules.yaml")
    assurance = enrich_control_assurance(
        reconciled,
        rules,
        reference["controls"],
        reference["risk_assignments"],
    )
    remediation = enrich_remediation_actions(actions, rules)
    repeat_findings = detect_repeat_findings(findings, rules)

    evidence_summary: dict[str, object] = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "structural_controls": [
            {
                "control_id": result.control_id,
                "dataset": result.dataset,
                "status": result.status,
                "blocking": result.blocking,
                "reason_code": result.reason_code,
                "affected_ids": list(result.affected_ids),
            }
            for result in quality_results
        ],
        "reconciliation": reconciliation_summary,
        "methodology": rules["methodology"],
        "reporting": rules["reporting"],
    }
    return assurance, remediation, repeat_findings, evidence_summary


def run_assurance_pipeline(root: Path | str = ".") -> dict[str, object]:
    root = Path(root).resolve()
    assurance, remediation, findings, evidence_summary = (
        build_trusted_assurance_outputs(root)
    )

    reference = load_enterprise_reference(
        root / "data" / "source" / "assurance" / "enterprise.db"
    )
    reporting_mart = build_assurance_reporting_mart(
        assurance,
        reference["systems"],
        reference["entities"],
        reference["controls"],
        reference["risk_taxonomy"],
    )
    key_columns = ["test_id", "reporting_period"]
    assurance_keys = set(assurance[key_columns].itertuples(index=False, name=None))
    mart_keys = set(reporting_mart[key_columns].itertuples(index=False, name=None))
    if (
        len(reporting_mart) != len(assurance)
        or reporting_mart.duplicated(key_columns).any()
        or mart_keys != assurance_keys
    ):
        raise RuntimeError(
            "Assurance reporting mart grain or membership changed during enrichment"
        )

    started_at = datetime.fromisoformat(str(evidence_summary["started_at_utc"]))
    run_id = started_at.strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = root / "output" / "assurance_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    assurance_path = run_dir / "control_assurance.parquet"
    reporting_mart_path = run_dir / "assurance_reporting_mart.parquet"
    remediation_path = run_dir / "remediation_actions.csv"
    findings_path = run_dir / "findings.csv"
    evidence_path = run_dir / "evidence_summary.json"
    report_path = run_dir / "assurance_report.html"
    manifest_path = run_dir / "manifest.json"

    assurance.to_parquet(assurance_path, index=False)
    reporting_mart.to_parquet(reporting_mart_path, index=False)
    remediation.to_csv(remediation_path, index=False, lineterminator="\n")
    findings.to_csv(findings_path, index=False, lineterminator="\n")
    evidence_path.write_text(
        json.dumps(evidence_summary, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    source_dir = root / "data" / "source" / "assurance"
    rules_path = root / "config" / "assurance" / "rules.yaml"
    reconciliation_path = root / "config" / "assurance" / "reconciliation.yaml"
    metrics_path = root / "config" / "assurance" / "metrics.yaml"
    completed_at = datetime.now(UTC)

    manifest: dict[str, object] = {
        "run_id": run_id,
        "status": "SUCCESS",
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": completed_at.isoformat(),
        "methodology": evidence_summary["methodology"],
        "reporting": evidence_summary["reporting"],
        "source_inventory": {
            "enterprise_reference": {
                "path": (source_dir / "enterprise.db").relative_to(root).as_posix(),
                "sha256": sha256_file(source_dir / "enterprise.db"),
            },
            "control_evidence": {
                "path": (source_dir / "control_evidence.json").relative_to(root).as_posix(),
                "sha256": sha256_file(source_dir / "control_evidence.json"),
                "row_count": len(assurance),
            },
            "findings": {
                "path": (source_dir / "findings.csv").relative_to(root).as_posix(),
                "sha256": sha256_file(source_dir / "findings.csv"),
                "row_count": len(findings),
            },
            "management_actions": {
                "path": (source_dir / "management_actions.csv").relative_to(root).as_posix(),
                "sha256": sha256_file(source_dir / "management_actions.csv"),
                "row_count": len(remediation),
            },
        },
        "configuration": {
            "rules": {
                "path": rules_path.relative_to(root).as_posix(),
                "sha256": sha256_file(rules_path),
            },
            "reconciliation": {
                "path": reconciliation_path.relative_to(root).as_posix(),
                "sha256": sha256_file(reconciliation_path),
            },
            "metrics": {
                "path": metrics_path.relative_to(root).as_posix(),
                "sha256": sha256_file(metrics_path),
            },
        },
        "code_identity": {
            "git_commit": git_commit(root),
            "git_dirty": git_is_dirty(root),
        },
        "controls": {
            "structural": evidence_summary["structural_controls"],
            "reconciliation": evidence_summary["reconciliation"],
        },
        "counts": {
            "control_assurance": len(assurance),
            "assurance_reporting_mart": len(reporting_mart),
            "remediation_actions": len(remediation),
            "findings": len(findings),
        },
        "outputs": {
            "control_assurance": assurance_path.relative_to(root).as_posix(),
            "assurance_reporting_mart": reporting_mart_path.relative_to(root).as_posix(),
            "remediation_actions": remediation_path.relative_to(root).as_posix(),
            "findings": findings_path.relative_to(root).as_posix(),
            "evidence_summary": evidence_path.relative_to(root).as_posix(),
            "assurance_report": report_path.relative_to(root).as_posix(),
            "manifest": manifest_path.relative_to(root).as_posix(),
        },
    }

    build_assurance_report(run_dir, report_path, manifest)
    manifest["completed_at_utc"] = datetime.now(UTC).isoformat()

    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> None:
    manifest = run_assurance_pipeline()
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
