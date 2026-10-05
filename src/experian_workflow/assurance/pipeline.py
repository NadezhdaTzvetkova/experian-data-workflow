from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from experian_workflow.assurance.browser_publication import write_browser_publication
from experian_workflow.assurance.calculations import (
    detect_repeat_findings,
    enrich_control_assurance,
    enrich_remediation_actions,
    load_assurance_rules,
)
from experian_workflow.assurance.explainability import write_explainability
from experian_workflow.assurance.html_dashboard import build_assurance_report
from experian_workflow.assurance.ingestion import (
    load_control_evidence,
    load_enterprise_reference,
    load_findings,
    load_management_actions,
)
from experian_workflow.assurance.metrics import (
    evaluate_metric_contract,
    load_metric_contract,
)
from experian_workflow.assurance.normalization import (
    normalize_control_evidence_identity,
)
from experian_workflow.assurance.powerpoint import build_powerpoint_publication
from experian_workflow.assurance.publication import (
    write_publication_package,
)
from experian_workflow.assurance.quality import (
    assert_structurally_usable,
    validate_control_evidence_contract,
    validate_control_evidence_population,
    validate_effective_dated_reference_state,
    validate_findings_contract,
    validate_management_actions_contract,
    validate_reference_integrity,
    validate_sqlite_contracts,
    validate_unique_key,
)
from experian_workflow.assurance.reconciliation import (
    load_reconciliation_contract,
    reconcile_control_evidence,
    summarize_reconciliation,
)
from experian_workflow.assurance.reporting import (
    build_assurance_kpis,
    build_assurance_reporting_mart,
    cross_check_headline_kpis,
)
from experian_workflow.assurance.tableau import build_tableau_hyper
from experian_workflow.assurance.tableau_dictionary import write_tableau_data_dictionary
from experian_workflow.assurance.tableau_workbook import build_tableau_workbook
from experian_workflow.assurance.tableau_workbook_contract import (
    validate_tableau_workbook_contract,
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

    rules = load_assurance_rules(
        root / "config" / "assurance" / "rules.yaml"
    )

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
    quality_results.extend(
        validate_reference_integrity(
            reference,
            findings,
            actions,
        )
    )
    quality_results.extend(
        validate_effective_dated_reference_state(
            reference,
            as_of_date=str(rules["reporting"]["as_of_date"]),
        )
    )
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

    metrics_config_path = root / "config" / "assurance" / "metrics.yaml"
    metric_contract = load_metric_contract(metrics_config_path)

    pandas_metrics = build_assurance_kpis(
        assurance,
        remediation,
        findings,
    )
    duckdb_metrics = cross_check_headline_kpis(
        assurance,
        remediation,
        findings,
    )
    contract_metrics = evaluate_metric_contract(
        metric_contract,
        {
            "control_assurance": assurance,
            "remediation_actions": remediation,
            "findings": findings,
        },
    )

    metric_names = set(pandas_metrics)
    if (
        set(duckdb_metrics) != metric_names
        or set(contract_metrics) != metric_names
        or pandas_metrics != duckdb_metrics
        or pandas_metrics != contract_metrics
    ):
        raise RuntimeError(
            "Assurance metric validation failed: "
            "Pandas, DuckDB, and governed metric contract do not match"
        )

    metric_validation = {
        "status": "PASS",
        "all_match": True,
        "pandas": pandas_metrics,
        "duckdb": duckdb_metrics,
        "metric_contract": contract_metrics,
    }

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
                "path": metrics_config_path.relative_to(root).as_posix(),
                "sha256": sha256_file(metrics_config_path),
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

    publication_paths = write_publication_package(
        run_dir=run_dir,
        manifest=manifest,
        metrics=pandas_metrics,
        metric_validation=metric_validation,
        assurance_reporting_mart=reporting_mart,
        findings=findings,
        remediation=remediation,
    )
    publication_paths["explainability"] = write_explainability(
        run_dir=run_dir, manifest=manifest, metric_contract=metric_contract,
        metrics=pandas_metrics, rules=load_assurance_rules(root / "config/assurance/rules.yaml"),
    )
    manifest["outputs"]["publication"] = {
        name: path.relative_to(root).as_posix()
        for name, path in publication_paths.items()
    }

    build_assurance_report(run_dir, report_path, manifest)

    publication_html_dir = run_dir / "publication" / "html"
    publication_html_dir.mkdir(parents=True, exist_ok=False)
    html_dashboard_path = publication_html_dir / "assurance_dashboard.html"
    html_bytes = report_path.read_bytes()
    if not html_bytes:
        raise RuntimeError("Generated assurance HTML is empty")

    html_text = html_bytes.decode("utf-8")
    required_html_markers = (
        "<title>Enterprise Assurance Analytics Report</title>",
        'id="dashboard-shell"',
        'id="assurance-data"',
        'id="metric-mode-toggle"',
        "Metric validation",
    )
    missing_html_markers = [
        marker for marker in required_html_markers if marker not in html_text
    ]
    if missing_html_markers:
        raise RuntimeError(
            f"HTML structural validation failed: {missing_html_markers}"
        )

    html_dashboard_path.write_bytes(html_bytes)
    if html_dashboard_path.read_bytes() != report_path.read_bytes():
        raise RuntimeError(
            "Canonical HTML publication differs from compatibility report"
        )

    manifest["outputs"]["publication"]["html_dashboard"] = (
        html_dashboard_path.relative_to(root).as_posix()
    )

    browser_result = write_browser_publication(
        dashboard_path=html_dashboard_path,
        html_dir=publication_html_dir,
    )
    browser_artifacts: dict[str, dict[str, str]] = {}
    for category in ("reports", "charts"):
        category_paths = browser_result[category]
        if not isinstance(category_paths, dict):
            raise TypeError(f"Browser publication {category} result must be a mapping")
        for filename, artifact_path_value in category_paths.items():
            artifact_path = Path(str(artifact_path_value))
            artifact_key = f"html_{category[:-1]}_{Path(filename).stem}"
            manifest["outputs"]["publication"][artifact_key] = (
                artifact_path.relative_to(root).as_posix()
            )
            browser_artifacts[f"{category}/{filename}"] = {
                "path": artifact_path.relative_to(run_dir).as_posix(),
                "sha256": sha256_file(artifact_path),
            }

    validation_summary_path = publication_paths["validation_summary"]
    validation_summary = json.loads(
        validation_summary_path.read_text(encoding="utf-8")
    )
    validation_summary["scope"] = "publication_foundation_and_html"
    validation_summary["html"] = {
        "status": "PASS",
        "path": html_dashboard_path.relative_to(run_dir).as_posix(),
        "sha256": sha256_file(html_dashboard_path),
        "compatibility_alias": report_path.relative_to(run_dir).as_posix(),
        "compatibility_alias_sha256": sha256_file(report_path),
        "structural_markers_validated": True,
        "browser_publication_status": browser_result["status"],
        "standalone_report_count": browser_result["report_count"],
        "standalone_chart_count": browser_result["chart_count"],
        "new_tab_links_validated": browser_result["new_tab_links_validated"],
        "standalone_artifacts": browser_artifacts,
    }
    validation_summary_path.write_text(
        json.dumps(validation_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tableau_result = build_tableau_hyper(run_dir=run_dir, project_root=root)
    tableau_hyper_path = Path(str(tableau_result["hyper_path"]))
    tableau_validation_path = run_dir / "publication" / "tableau" / "tableau_validation.json"
    manifest["outputs"]["publication"]["tableau_hyper"] = (
        tableau_hyper_path.relative_to(root).as_posix()
    )
    manifest["outputs"]["publication"]["tableau_validation"] = (
        tableau_validation_path.relative_to(root).as_posix()
    )

    tableau_dictionary_result = write_tableau_data_dictionary(run_dir=run_dir)
    tableau_dictionary_path = Path(str(tableau_dictionary_result["path"]))
    manifest["outputs"]["publication"]["tableau_data_dictionary"] = (
        tableau_dictionary_path.relative_to(root).as_posix()
    )

    tableau_workbook_contract_result = validate_tableau_workbook_contract(
        contract_path=root / "config" / "assurance" / "tableau_workbook_contract.json",
        dictionary_path=tableau_dictionary_path,
    )

    tableau_workbook_result = build_tableau_workbook(
        run_dir=run_dir,
        contract_path=root / "config" / "assurance" / "tableau_workbook_contract.json",
        dictionary_path=tableau_dictionary_path,
        hyper_path=tableau_hyper_path,
    )
    tableau_twb_path = Path(str(tableau_workbook_result["twb_path"]))
    tableau_twbx_path = Path(str(tableau_workbook_result["twbx_path"]))
    manifest["outputs"]["publication"]["tableau_twb"] = (
        tableau_twb_path.relative_to(root).as_posix()
    )
    manifest["outputs"]["publication"]["tableau_twbx"] = (
        tableau_twbx_path.relative_to(root).as_posix()
    )

    tableau_hyper_evidence = dict(tableau_result)
    tableau_hyper_evidence["hyper_path"] = (
        tableau_hyper_path.relative_to(run_dir).as_posix()
    )
    tableau_workbook_evidence = {
        key: value
        for key, value in tableau_workbook_result.items()
        if key not in {"twb_path", "twbx_path"}
    }
    tableau_validation_payload = {
        "status": "PASS",
        "acceptance_model": "PROGRAMMATIC_TABLEAU",
        "hyper": tableau_hyper_evidence,
        "workbook_contract": tableau_workbook_contract_result,
        "workbook": tableau_workbook_evidence,
        "artifacts": {
            "hyper": {
                "path": tableau_hyper_path.relative_to(run_dir).as_posix(),
                "sha256": sha256_file(tableau_hyper_path),
            },
            "twb": {
                "path": tableau_twb_path.relative_to(run_dir).as_posix(),
                "sha256": sha256_file(tableau_twb_path),
            },
            "twbx": {
                "path": tableau_twbx_path.relative_to(run_dir).as_posix(),
                "sha256": sha256_file(tableau_twbx_path),
            },
            "data_dictionary": {
                "path": tableau_dictionary_path.relative_to(run_dir).as_posix(),
                "sha256": sha256_file(tableau_dictionary_path),
            },
        },
    }
    tableau_validation_path.write_text(
        json.dumps(tableau_validation_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    validation_summary["scope"] = "publication_foundation_html_and_tableau"
    validation_summary["tableau_extract"] = {
        "status": "PASS",
        "validation_scope": (
            "hyper_extract_structural_and_data_parity"
        ),
        "hyper_path": tableau_hyper_path.relative_to(run_dir).as_posix(),
        "hyper_sha256": sha256_file(tableau_hyper_path),
        "validation_path": (
            tableau_validation_path.relative_to(run_dir).as_posix()
        ),
        "validation_sha256": sha256_file(tableau_validation_path),
        "governed_metrics_exact_match": tableau_result["governed_metrics"][
            "exact_match"
        ],
        "data_dictionary_path": (
            tableau_dictionary_path.relative_to(run_dir).as_posix()
        ),
        "data_dictionary_sha256": sha256_file(tableau_dictionary_path),
        "data_dictionary_row_count": tableau_dictionary_result["row_count"],
        "data_dictionary_dataset_count": tableau_dictionary_result[
            "dataset_count"
        ],
        "workbook_contract_path": (
            root / "config" / "assurance" / "tableau_workbook_contract.json"
        ).relative_to(root).as_posix(),
        "workbook_contract_sha256": sha256_file(
            root / "config" / "assurance" / "tableau_workbook_contract.json"
        ),
        "workbook_contract_status": tableau_workbook_contract_result["status"],
        "workbook_contract_dashboard_count": tableau_workbook_contract_result[
            "dashboard_count"
        ],
        "workbook_contract_worksheet_count": tableau_workbook_contract_result[
            "worksheet_count"
        ],
        "workbook_contract_referenced_dataset_count": (
            tableau_workbook_contract_result["referenced_dataset_count"]
        ),
        "acceptance_model": tableau_result["acceptance_model"],
    }
    validation_summary["tableau_workbook"] = {
        "status": "PASS",
        "acceptance_model": tableau_workbook_result["acceptance_model"],
        "twb_path": tableau_twb_path.relative_to(run_dir).as_posix(),
        "twb_sha256": sha256_file(tableau_twb_path),
        "twbx_path": tableau_twbx_path.relative_to(run_dir).as_posix(),
        "twbx_sha256": sha256_file(tableau_twbx_path),
        "dashboard_count": tableau_workbook_result["dashboard_count"],
        "worksheet_count": tableau_workbook_result["worksheet_count"],
        "dataset_count": tableau_workbook_result["dataset_count"],
        "twb_structure": tableau_workbook_result["twb_structure"],
        "visual_contract": tableau_workbook_result["visual_contract"],
        "twbx_package": tableau_workbook_result["twbx_package"],
        "hyper_identity_match": tableau_workbook_result["hyper_identity_match"],
        "package_members": tableau_workbook_result["package_members"],
    }

    powerpoint_result = build_powerpoint_publication(run_dir=run_dir)
    powerpoint_pptx_path = Path(str(powerpoint_result["pptx_path"]))
    powerpoint_slide_data_path = Path(str(powerpoint_result["slide_data_path"]))
    powerpoint_validation_path = (
        run_dir / "publication" / "powerpoint" / "powerpoint_validation.json"
    )
    powerpoint_validation_payload = {
        key: value
        for key, value in powerpoint_result.items()
        if key not in {"pptx_path", "slide_data_path"}
    }
    powerpoint_validation_path.write_text(
        json.dumps(powerpoint_validation_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest["outputs"]["publication"]["powerpoint_pptx"] = (
        powerpoint_pptx_path.relative_to(root).as_posix()
    )
    manifest["outputs"]["publication"]["powerpoint_slide_data"] = (
        powerpoint_slide_data_path.relative_to(root).as_posix()
    )
    manifest["outputs"]["publication"]["powerpoint_validation"] = (
        powerpoint_validation_path.relative_to(root).as_posix()
    )
    validation_summary["scope"] = (
        "publication_foundation_html_tableau_and_powerpoint"
    )
    validation_summary["powerpoint"] = {
        "status": "PASS",
        "validation_scope": "package_navigation_links_and_run_identity",
        "pptx_path": powerpoint_pptx_path.relative_to(run_dir).as_posix(),
        "pptx_sha256": sha256_file(powerpoint_pptx_path),
        "slide_data_path": (
            powerpoint_slide_data_path.relative_to(run_dir).as_posix()
        ),
        "slide_data_sha256": sha256_file(powerpoint_slide_data_path),
        "validation_path": (
            powerpoint_validation_path.relative_to(run_dir).as_posix()
        ),
        "validation_sha256": sha256_file(powerpoint_validation_path),
        "slide_count": powerpoint_result["slide_count"],
        "internal_navigation_links": (
            powerpoint_result["internal_navigation_links"]
        ),
        "external_publication_links": (
            powerpoint_result["external_publication_links"]
        ),
        "run_identity_match": powerpoint_result["run_identity_match"],
        "package_structure": powerpoint_result["package_structure"],
        "client_validation": {
            "status": "NOT_EXECUTED",
            "validation_scope": "microsoft_powerpoint_desktop_client",
            "required_for_pipeline_success": False,
        },
    }

    validation_summary["artifacts"]["explainability"] = {
        "path": "publication/explainability.json",
        "sha256": sha256_file(publication_paths["explainability"]),
        "status": "PASS",
    }

    validation_summary_path.write_text(
        json.dumps(validation_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

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
