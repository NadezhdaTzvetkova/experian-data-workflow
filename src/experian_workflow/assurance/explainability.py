"""Governed presentation metadata; no KPI or risk calculations live here."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from experian_workflow.assurance.publication import TABLE_CONTRACTS
from experian_workflow.evidence import sha256_file

SOURCE_ROLES = {
    "enterprise_reference": ("SQLite", "Enterprise identity, risk/control context and mapping references", "Keyed reference tables"),
    "control_evidence": ("JSON", "Control testing and evidence populations", "One assurance test per reporting period"),
    "findings": ("CSV", "Finding status and recurrence history", "One finding per finding ID"),
    "management_actions": ("CSV", "Remediation ownership, target dates and closure", "One action per action ID"),
}
PIPELINE_STAGES = [
    "Source ingestion", "Structural validation", "Identity normalization",
    "Population reconciliation", "Governed analytics", "Independent metric validation",
    "Shared publication", "PowerPoint / HTML / Tableau",
]
VALIDATION_LEVELS = {
    "analytics": "Pandas, independent DuckDB and the governed metric contract must agree; persisted tables are read back and reconciled.",
    "html": "Programmatic structure/link checks. Browser interactions are separate executed evidence.",
    "tableau": "Programmatic Hyper content, TWB field/visual binding and TWBX package checks; Tableau Desktop is not executed by the pipeline.",
    "powerpoint": "Automated package, slide, identity and link checks. PowerPoint Desktop rendering/navigation is separate evidence; pipeline client_validation remains NOT_EXECUTED.",
}
RATIONALE = {
    "Python / Pandas": "Readable deterministic processing and typed analytical tables.",
    "DuckDB": "Independent SQL checks against the governed Python results.",
    "HTML / Plotly": "Portable interactive exploration with embedded chart code.",
    "Tableau": "A packaged BI workbook over the same governed tables.",
    "PowerPoint": "An executive narrative and navigation layer.",
}


def build_explainability(
    *, manifest: dict[str, Any], metric_contract: dict[str, Any],
    metrics: dict[str, int], rules: dict[str, Any],
) -> dict[str, Any]:
    populations = {
        "control_assurance": ("assurance_tests", "One assurance test per test ID and reporting period"),
        "findings": ("findings_summary", "One finding per finding ID"),
        "remediation_actions": ("remediation_summary", "One management action per action ID"),
    }
    definitions = {}
    for metric_id, contract in metric_contract["metrics"].items():
        table, grain = populations[contract["trusted_population"]]
        definitions[metric_id] = {
            "label": metric_id.replace("_", " ").capitalize(),
            "value": metrics[metric_id], "grain": grain,
            "calculation": contract["calculation"],
            "publication_table": f"publication/tables/{table}.csv",
            **{key: contract[key] for key in (
                "trusted_population", "numerator", "denominator", "units",
                "business_question", "limitation", "filter_semantics",
            )},
            "drill_target": "reports/data_trust.html#data-and-metrics",
        }
    freshness = rules["rules"]["evidence_freshness"]
    max_age = freshness["max_age_days"]
    age_comparison = "older than" if freshness["boundary_inclusive"] else "at least"
    states = {
        "SUFFICIENT": "Reconciliation passes, identity is mapped, evidence is current and tested population meets configured full coverage; evidence adequacy does not imply control effectiveness.",
        "PARTIAL": "Reconciliation passes, identity is mapped and evidence is current, with nonzero testing below full expected coverage; this is not automatically a failed control.",
        "INSUFFICIENT": "After reconciliation and mapping checks, stale evidence or zero tested population prevents a sufficient assurance basis.",
        "NOT_EVALUABLE": "The relevant evaluation lacks a valid basis: failed reconciliation, unresolved identity, future evidence or missing expected population can prevent evidence evaluation; insufficient assurance basis or missing inherent risk prevents residual-risk evaluation.",
        "STALE": f"Evidence is {age_comparison} {max_age} days old at the governed as-of date. Freshness overlaps evidence-sufficiency states; future evidence is NOT_EVALUABLE.",
        "UNMAPPED": "No resolved enterprise identity. Retain the test and its source records explicitly.",
        "NOT_TESTED": "Mapped source records were not evaluated; retain them in population reconciliation.",
        "NOT_APPLICABLE": "The relevant field does not apply; retain it distinctly from missing, untested or not-evaluable evidence.",
        "partial_coverage": "Partial coverage can coexist with an observed EFFECTIVE result. It does not establish full evidence sufficiency or permit a residual-risk conclusion under the configured prerequisites.",
        "residual_risk": "A residual-risk conclusion requires SUFFICIENT evidence and the configured inherent-risk/control-effectiveness matrix.",
    }
    sources = [
        {"id": name, "path": item["path"], "sha256": item["sha256"],
         "format": SOURCE_ROLES[name][0], "role": SOURCE_ROLES[name][1],
         "grain": SOURCE_ROLES[name][2]}
        for name, item in manifest["source_inventory"].items()
    ]
    return {
        "schema_version": "1.0", "run_id": manifest["run_id"],
        "as_of_date": manifest["reporting"]["as_of_date"],
        "reporting_period": str(manifest["reporting"]["as_of_date"])[:7],
        "code_identity": manifest["code_identity"],
        "disclaimer": "Illustrative synthetic enterprise-assurance data, controls, methodology and policy; not Experian internal data, controls, methodology or policy.",
        "sources": sources, "pipeline_stages": PIPELINE_STAGES,
        "claim_to_evidence": "Executive claim → published metric/table → independent validation → governed input → source/configuration",
        "traceability_limit": "Run identity and hashes establish traceability; metric-contract and scenario checks establish analytical correctness.",
        "reconciliation": manifest["controls"]["reconciliation"],
        "reconciliation_grain": "Source-record population counts within assurance tests; assurance-test KPIs count test rows.",
        "population_equations": ["Received = mapped + unmapped source records", "Mapped = evaluated + not tested source records"],
        "grain_distinction": (
            f"{manifest['controls']['reconciliation']['unmapped_population']} unmapped source records and "
            f"{metrics['unmapped_tests']} unmapped assurance test describe different grains in the current demonstration."
        ),
        "metrics": definitions, "states": states, "validation_levels": VALIDATION_LEVELS,
        "implementation_choices": RATIONALE,
        "implementation_choice_scope": "Implementation choices for this demonstration, not recruiter-mandated technologies.",
        "channels": {"PowerPoint": "Executive narrative and navigation", "HTML": "Interactive exploration", "Tableau": "BI exploration"},
    }


def write_explainability(
    *, run_dir: Path, manifest: dict[str, Any], metric_contract: dict[str, Any],
    metrics: dict[str, int], rules: dict[str, Any],
) -> Path:
    payload = build_explainability(
        manifest=manifest, metric_contract=metric_contract, metrics=metrics, rules=rules,
    )
    # Bind explanation to finalized canonical metric/table bytes, not a second calculation.
    payload["publication_inputs"] = {
        p.relative_to(run_dir).as_posix(): sha256_file(p)
        for p in sorted((run_dir / "publication").glob("tables/*.csv"))
    }
    for name in ("metrics.json", "metric_validation.json"):
        p = run_dir / "publication" / name
        payload["publication_inputs"][p.relative_to(run_dir).as_posix()] = sha256_file(p)
    payload["publication_input_identity"] = hashlib.sha256(
        json.dumps(payload["publication_inputs"], sort_keys=True).encode()
    ).hexdigest()
    path = run_dir / "publication" / "explainability.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    load_explainability(run_dir=run_dir, expected_run_id=str(manifest["run_id"]))
    return path


def load_explainability(*, run_dir: Path, expected_run_id: str) -> dict[str, Any]:
    path = run_dir / "publication" / "explainability.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Governed explainability metadata is missing or unreadable") from exc
    required = {
        "schema_version", "run_id", "as_of_date", "reporting_period", "code_identity",
        "disclaimer", "sources", "pipeline_stages", "reconciliation", "metrics",
        "states", "validation_levels", "implementation_choices", "channels",
        "publication_inputs", "publication_input_identity", "grain_distinction",
        "claim_to_evidence", "traceability_limit",
    }
    if not required.issubset(payload) or payload["schema_version"] != "1.0":
        raise RuntimeError("Unsupported or incomplete explainability metadata")
    if payload["run_id"] != expected_run_id:
        raise RuntimeError("Explainability run identity mismatch")
    metrics = json.loads((run_dir / "publication/metrics.json").read_text(encoding="utf-8"))
    for key, item in payload["metrics"].items():
        if not {"value", "grain", "numerator", "denominator", "limitation", "publication_table"}.issubset(item):
            raise RuntimeError(f"Incomplete explainability metric: {key}")
    if payload["as_of_date"] != metrics["as_of_date"] or {
        key: item["value"] for key, item in payload["metrics"].items()
    } != metrics["metrics"]:
        raise RuntimeError("Explainability metric/as-of parity mismatch")
    inputs = payload["publication_inputs"]
    expected_inputs = {
        f"publication/tables/{name}.csv" for name in TABLE_CONTRACTS
    } | {"publication/metrics.json", "publication/metric_validation.json"}
    if not isinstance(inputs, dict) or set(inputs) != expected_inputs:
        raise RuntimeError("Explainability publication-input binding is incomplete")
    if metrics["run_id"] != expected_run_id or metrics["validation_status"] != "PASS":
        raise RuntimeError("Explainability canonical metric identity/status mismatch")
    identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    if identity != payload["publication_input_identity"]:
        raise RuntimeError("Explainability publication-input identity mismatch")
    for relative, digest in inputs.items():
        target = (run_dir / relative).resolve()
        if not target.is_relative_to(run_dir.resolve()) or not target.is_file() or sha256_file(target) != digest:
            raise RuntimeError("Explainability publication-input bytes changed")
    return payload
