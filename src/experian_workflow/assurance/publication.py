from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from experian_workflow.assurance.reporting import (
    build_risk_domain_assurance_summary,
)
from experian_workflow.evidence import sha256_file

PUBLICATION_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class PublicationTableContract:
    dataset_id: str
    grain: str
    key: tuple[str, ...]
    nullable_key_fields: tuple[str, ...] = ()


TABLE_CONTRACTS: dict[str, PublicationTableContract] = {
    "assurance_tests": PublicationTableContract(
        dataset_id="assurance_tests",
        grain="one assurance test for one reporting period",
        key=("test_id", "reporting_period"),
    ),
    "risk_domain_summary": PublicationTableContract(
        dataset_id="risk_domain_summary",
        grain="one governed risk domain",
        key=("risk_domain",),
    ),
    "findings_summary": PublicationTableContract(
        dataset_id="findings_summary",
        grain="one governed finding",
        key=("finding_id",),
    ),
    "remediation_summary": PublicationTableContract(
        dataset_id="remediation_summary",
        grain="one governed management action",
        key=("action_id",),
    ),
    "findings_actions_detail": PublicationTableContract(
        dataset_id="findings_actions_detail",
        grain="one finding/action relationship, retaining findings without actions",
        key=("finding_id", "action_id"),
        nullable_key_fields=("action_id",),
    ),
    "attention_items": PublicationTableContract(
        dataset_id="attention_items",
        grain="one assurance test requiring review for one reporting period",
        key=("test_id", "reporting_period"),
    ),
    "lineage_summary": PublicationTableContract(
        dataset_id="lineage_summary",
        grain="one current-run lineage/configuration item",
        key=("lineage_type", "item_id"),
    ),
}


def _require_mapping(
    value: object,
    *,
    name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _with_publication_identity(
    frame: pd.DataFrame,
    *,
    run_id: str,
    as_of_date: str,
) -> pd.DataFrame:
    result = frame.copy()
    result["publication_run_id"] = run_id
    result["publication_as_of_date"] = as_of_date
    return result


def build_findings_actions_detail(
    findings: pd.DataFrame,
    remediation: pd.DataFrame,
) -> pd.DataFrame:
    action_columns = [
        "finding_id",
        "action_id",
        "action_owner",
        "target_date",
        "status",
        "closed_date",
        "closure_validation_status",
        "overdue",
        "days_overdue",
    ]
    actions = remediation[action_columns].rename(
        columns={"status": "action_status"}
    )

    return findings.merge(
        actions,
        how="left",
        on="finding_id",
        validate="one_to_many",
    )


def build_attention_items(
    assurance_reporting_mart: pd.DataFrame,
) -> pd.DataFrame:
    mask = (
        assurance_reporting_mart["evidence_sufficiency"].ne("SUFFICIENT")
        | assurance_reporting_mart["identity_status"].eq("UNMAPPED")
        | assurance_reporting_mart["residual_risk"].isin(
            ["HIGH", "CRITICAL"]
        )
    )
    return assurance_reporting_mart.loc[mask].copy()


def build_lineage_summary(
    manifest: Mapping[str, object],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for lineage_type, manifest_key in (
        ("source", "source_inventory"),
        ("configuration", "configuration"),
    ):
        container = _require_mapping(
            manifest.get(manifest_key, {}),
            name=manifest_key,
        )
        for item_id, raw_entry in container.items():
            entry = _require_mapping(
                raw_entry,
                name=f"{manifest_key}.{item_id}",
            )
            rows.append(
                {
                    "lineage_type": lineage_type,
                    "item_id": str(item_id),
                    "path": entry.get("path"),
                    "sha256": entry.get("sha256"),
                    "row_count": entry.get("row_count"),
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "lineage_type",
            "item_id",
            "path",
            "sha256",
            "row_count",
        ],
    )


def build_publication_tables(
    *,
    assurance_reporting_mart: pd.DataFrame,
    findings: pd.DataFrame,
    remediation: pd.DataFrame,
    manifest: Mapping[str, object],
) -> dict[str, pd.DataFrame]:
    run_id = str(manifest["run_id"])
    reporting = _require_mapping(
        manifest["reporting"],
        name="reporting",
    )
    as_of_date = str(reporting["as_of_date"])

    tables = {
        "assurance_tests": assurance_reporting_mart.copy(),
        "risk_domain_summary": build_risk_domain_assurance_summary(
            assurance_reporting_mart
        ),
        "findings_summary": findings.copy(),
        "remediation_summary": remediation.copy(),
        "findings_actions_detail": build_findings_actions_detail(
            findings,
            remediation,
        ),
        "attention_items": build_attention_items(
            assurance_reporting_mart
        ),
        "lineage_summary": build_lineage_summary(manifest),
    }

    return {
        name: _with_publication_identity(
            frame,
            run_id=run_id,
            as_of_date=as_of_date,
        )
        for name, frame in tables.items()
    }


def _validate_key(
    name: str,
    frame: pd.DataFrame,
    contract: PublicationTableContract,
) -> None:
    missing = [column for column in contract.key if column not in frame]
    if missing:
        raise RuntimeError(
            f"Publication table {name} is missing key columns: {missing}"
        )

    required_non_null = [
        column
        for column in contract.key
        if column not in contract.nullable_key_fields
    ]
    if required_non_null and frame[required_non_null].isna().any().any():
        raise RuntimeError(
            f"Publication table {name} contains null required key values"
        )

    if frame.duplicated(list(contract.key), keep=False).any():
        duplicates = (
            frame.loc[
                frame.duplicated(list(contract.key), keep=False),
                list(contract.key),
            ]
            .astype("string")
            .to_dict(orient="records")
        )
        raise RuntimeError(
            f"Publication table {name} violates key uniqueness: "
            f"{duplicates}"
        )


def validate_publication_tables(
    *,
    tables: Mapping[str, pd.DataFrame],
    assurance_reporting_mart: pd.DataFrame,
    findings: pd.DataFrame,
    remediation: pd.DataFrame,
    run_id: str,
    as_of_date: str,
) -> dict[str, dict[str, object]]:
    if set(tables) != set(TABLE_CONTRACTS):
        raise RuntimeError(
            "Publication table set does not match the governed contract"
        )

    validation: dict[str, dict[str, object]] = {}

    for name, contract in TABLE_CONTRACTS.items():
        frame = tables[name]
        _validate_key(name, frame, contract)

        if "publication_run_id" not in frame:
            raise RuntimeError(
                f"Publication table {name} has no run identity"
            )
        if "publication_as_of_date" not in frame:
            raise RuntimeError(
                f"Publication table {name} has no as-of identity"
            )
        if set(frame["publication_run_id"].astype(str)) != {run_id}:
            raise RuntimeError(
                f"Publication table {name} contains wrong run identity"
            )
        if set(frame["publication_as_of_date"].astype(str)) != {
            as_of_date
        }:
            raise RuntimeError(
                f"Publication table {name} contains wrong as-of identity"
            )

        validation[name] = {
            "status": "PASS",
            "grain": contract.grain,
            "key": list(contract.key),
            "row_count": len(frame),
        }

    assurance_keys = set(
        zip(
            assurance_reporting_mart["test_id"].astype(str),
            assurance_reporting_mart["reporting_period"].astype(str),
            strict=True,
        )
    )
    published_assurance_keys = set(
        zip(
            tables["assurance_tests"]["test_id"].astype(str),
            tables["assurance_tests"]["reporting_period"].astype(str),
            strict=True,
        )
    )
    if published_assurance_keys != assurance_keys:
        raise RuntimeError(
            "assurance_tests publication membership differs from "
            "assurance_reporting_mart"
        )

    finding_ids = set(findings["finding_id"].astype(str))
    published_finding_ids = set(
        tables["findings_summary"]["finding_id"].astype(str)
    )
    if published_finding_ids != finding_ids:
        raise RuntimeError(
            "findings_summary publication membership differs from findings"
        )

    action_ids = set(remediation["action_id"].astype(str))
    published_action_ids = set(
        tables["remediation_summary"]["action_id"].astype(str)
    )
    if published_action_ids != action_ids:
        raise RuntimeError(
            "remediation_summary publication membership differs from "
            "remediation_actions"
        )

    detail = tables["findings_actions_detail"]
    detail_finding_ids = set(detail["finding_id"].astype(str))
    if detail_finding_ids != finding_ids:
        raise RuntimeError(
            "findings_actions_detail does not retain every finding"
        )

    detail_action_ids = set(
        detail.loc[detail["action_id"].notna(), "action_id"].astype(str)
    )
    if detail_action_ids != action_ids:
        raise RuntimeError(
            "findings_actions_detail action membership differs from "
            "remediation_actions"
        )

    expected_attention = build_attention_items(
        assurance_reporting_mart
    )
    expected_attention_keys = set(
        zip(
            expected_attention["test_id"].astype(str),
            expected_attention["reporting_period"].astype(str),
            strict=True,
        )
    )
    published_attention = tables["attention_items"]
    published_attention_keys = set(
        zip(
            published_attention["test_id"].astype(str),
            published_attention["reporting_period"].astype(str),
            strict=True,
        )
    )
    if published_attention_keys != expected_attention_keys:
        raise RuntimeError(
            "attention_items publication membership differs from the "
            "governed attention rule"
        )

    risk_summary = tables["risk_domain_summary"]
    if int(risk_summary["assurance_tests"].sum()) != len(
        assurance_reporting_mart
    ):
        raise RuntimeError(
            "risk_domain_summary does not conserve assurance-test count"
        )

    return validation


def _write_json(
    path: Path,
    payload: Mapping[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_publication_package(
    *,
    run_dir: Path,
    manifest: Mapping[str, object],
    metrics: Mapping[str, int],
    metric_validation: Mapping[str, object],
    assurance_reporting_mart: pd.DataFrame,
    findings: pd.DataFrame,
    remediation: pd.DataFrame,
) -> dict[str, Path]:
    publication_dir = run_dir / "publication"
    tables_dir = publication_dir / "tables"
    publication_dir.mkdir(parents=True, exist_ok=False)
    tables_dir.mkdir(parents=True, exist_ok=False)

    run_id = str(manifest["run_id"])
    reporting = _require_mapping(
        manifest["reporting"],
        name="reporting",
    )
    methodology = _require_mapping(
        manifest["methodology"],
        name="methodology",
    )
    as_of_date = str(reporting["as_of_date"])

    pandas_values = _require_mapping(
        metric_validation.get("pandas"),
        name="metric_validation.pandas",
    )
    duckdb_values = _require_mapping(
        metric_validation.get("duckdb"),
        name="metric_validation.duckdb",
    )
    contract_values = _require_mapping(
        metric_validation.get("metric_contract"),
        name="metric_validation.metric_contract",
    )

    if (
        metric_validation.get("status") != "PASS"
        or metric_validation.get("all_match") is not True
        or dict(pandas_values) != dict(metrics)
        or dict(duckdb_values) != dict(metrics)
        or dict(contract_values) != dict(metrics)
    ):
        raise RuntimeError(
            "Publication metric package is not backed by matching "
            "Pandas, DuckDB, and metric-contract evidence"
        )

    published_metrics: dict[str, object] = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "run_id": run_id,
        "as_of_date": as_of_date,
        "methodology_version": methodology.get("version"),
        "validation_status": "PASS",
        "metrics": dict(metrics),
    }

    published_metric_validation: dict[str, object] = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "PASS",
        "all_match": True,
        "pandas": dict(pandas_values),
        "duckdb": dict(duckdb_values),
        "metric_contract": dict(contract_values),
        "published": dict(metrics),
    }

    metrics_path = publication_dir / "metrics.json"
    metric_validation_path = publication_dir / "metric_validation.json"

    _write_json(metrics_path, published_metrics)
    _write_json(
        metric_validation_path,
        published_metric_validation,
    )

    tables = build_publication_tables(
        assurance_reporting_mart=assurance_reporting_mart,
        findings=findings,
        remediation=remediation,
        manifest=manifest,
    )

    table_validation = validate_publication_tables(
        tables=tables,
        assurance_reporting_mart=assurance_reporting_mart,
        findings=findings,
        remediation=remediation,
        run_id=run_id,
        as_of_date=as_of_date,
    )

    paths: dict[str, Path] = {
        "metrics": metrics_path,
        "metric_validation": metric_validation_path,
    }

    for name, frame in tables.items():
        contract = TABLE_CONTRACTS[name]
        ordered = frame.sort_values(
            list(contract.key),
            kind="stable",
            na_position="last",
        ).reset_index(drop=True)
        path = tables_dir / f"{name}.csv"
        ordered.to_csv(
            path,
            index=False,
            lineterminator="\n",
        )
        paths[name] = path

    persisted_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    persisted_metric_validation = json.loads(
        metric_validation_path.read_text(encoding="utf-8")
    )
    if persisted_metrics != published_metrics:
        raise RuntimeError(
            "Persisted publication metrics differ from the validated in-memory payload"
        )
    if persisted_metric_validation != published_metric_validation:
        raise RuntimeError(
            "Persisted metric-validation evidence differs from the validated in-memory payload"
        )

    persisted_table_validation: dict[str, dict[str, object]] = {}
    for name, frame in tables.items():
        contract = TABLE_CONTRACTS[name]
        expected = frame.sort_values(
            list(contract.key),
            kind="stable",
            na_position="last",
        ).reset_index(drop=True)
        persisted = pd.read_csv(
            paths[name],
            dtype=str,
            keep_default_na=False,
        )
        expected_serialized = (
            expected.where(expected.notna(), "")
            .astype(str)
            .reset_index(drop=True)
        )
        if list(persisted.columns) != list(expected_serialized.columns):
            raise RuntimeError(
                f"Persisted publication table {name} changed column order or membership"
            )
        if not persisted.equals(expected_serialized):
            raise RuntimeError(
                f"Persisted publication table {name} differs from its validated in-memory table"
            )
        _validate_key(name, persisted, contract)
        if set(persisted["publication_run_id"].astype(str)) != {run_id}:
            raise RuntimeError(
                f"Persisted publication table {name} contains wrong run identity"
            )
        if set(persisted["publication_as_of_date"].astype(str)) != {
            as_of_date
        }:
            raise RuntimeError(
                f"Persisted publication table {name} contains wrong as-of identity"
            )
        persisted_table_validation[name] = {
            "status": "PASS",
            "row_count": len(persisted),
            "key": list(contract.key),
            "full_content_match": True,
        }
        table_validation[name]["persisted_readback_status"] = "PASS"
        table_validation[name]["persisted_full_content_match"] = True

    artifact_validation: dict[str, dict[str, object]] = {
        "metrics": {
            "path": metrics_path.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(metrics_path),
            "persisted_readback_status": "PASS",
        },
        "metric_validation": {
            "path": metric_validation_path.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(metric_validation_path),
            "persisted_readback_status": "PASS",
        },
    }

    for name in TABLE_CONTRACTS:
        path = paths[name]
        artifact_validation[name] = {
            "path": path.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(path),
        }
        table_validation[name]["sha256"] = sha256_file(path)

    validation_summary: dict[str, object] = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "status": "PASS",
        "scope": "publication_foundation",
        "run_id": run_id,
        "as_of_date": as_of_date,
        "methodology_version": methodology.get("version"),
        "metric_validation": {
            "status": "PASS",
            "all_match": True,
            "published_matches_validated": True,
        },
        "tables": table_validation,
        "persisted_readback": {
            "status": "PASS",
            "metrics": "PASS",
            "metric_validation": "PASS",
            "tables": persisted_table_validation,
        },
        "artifacts": artifact_validation,
    }

    validation_summary_path = publication_dir / "validation_summary.json"
    _write_json(
        validation_summary_path,
        validation_summary,
    )
    paths["validation_summary"] = validation_summary_path

    return paths
