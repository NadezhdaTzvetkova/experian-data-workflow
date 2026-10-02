from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


class AssuranceCalculationError(ValueError):
    pass


def load_assurance_rules(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise AssuranceCalculationError(f"Invalid assurance rules: {path}")
    if config.get("schema_version") != "1.0":
        raise AssuranceCalculationError("Unsupported assurance rules schema version.")
    methodology = config.get("methodology")
    reporting = config.get("reporting")
    rules = config.get("rules")
    if not isinstance(methodology, dict) or not isinstance(reporting, dict):
        raise AssuranceCalculationError("Missing assurance methodology/reporting config.")
    if not isinstance(rules, dict):
        raise AssuranceCalculationError("Missing assurance rules mapping.")
    required_rules = {
        "coverage",
        "evidence_freshness",
        "evidence_sufficiency",
        "control_effectiveness",
        "residual_risk",
    }
    missing = sorted(required_rules - set(rules))
    if missing:
        raise AssuranceCalculationError(
            "Missing assurance rule definitions: " + ", ".join(missing)
        )
    residual = rules["residual_risk"]
    matrix = residual.get("matrix")
    if not isinstance(matrix, dict):
        raise AssuranceCalculationError("Missing residual-risk matrix.")
    inherent_states = {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    effectiveness_states = {"EFFECTIVE", "PARTIALLY_EFFECTIVE", "INEFFECTIVE"}
    if set(matrix) != inherent_states:
        raise AssuranceCalculationError("Residual-risk matrix has incomplete inherent-risk states.")
    for inherent in sorted(inherent_states):
        row = matrix[inherent]
        if not isinstance(row, dict) or set(row) != effectiveness_states:
            raise AssuranceCalculationError(
                f"Residual-risk matrix is incomplete for inherent risk: {inherent}"
            )
    date.fromisoformat(str(reporting.get("as_of_date")))
    return config


def calculate_coverage(
    expected_population: int,
    tested_population: int,
    rules: dict[str, Any],
) -> tuple[float | None, str, str | None]:
    rule = rules["rules"]["coverage"]
    if expected_population <= 0:
        return None, rule["zero_denominator_state"], "MISSING_EXPECTED_POPULATION"
    ratio = tested_population / expected_population
    if tested_population == 0:
        return ratio, "INSUFFICIENT", "NOT_TESTED"
    if ratio >= float(rule["sufficient_ratio"]):
        return ratio, "SUFFICIENT", None
    return ratio, "PARTIAL", "INCOMPLETE_COVERAGE"


def classify_freshness(
    evidence_date: str,
    rules: dict[str, Any],
) -> tuple[int, str, str | None]:
    as_of = date.fromisoformat(rules["reporting"]["as_of_date"])
    observed = date.fromisoformat(evidence_date)
    age_days = (as_of - observed).days
    if age_days < 0:
        return age_days, "NOT_EVALUABLE", "OUT_OF_PERIOD"
    rule = rules["rules"]["evidence_freshness"]
    max_age = int(rule["max_age_days"])
    inclusive = bool(rule["boundary_inclusive"])
    current = age_days <= max_age if inclusive else age_days < max_age
    if current:
        return age_days, "CURRENT", None
    return age_days, "STALE", str(rule["stale_reason_code"])


def classify_evidence_sufficiency(
    *,
    identity_status: str,
    reconciliation_status: str,
    freshness_status: str,
    coverage_state: str,
    tested_population: int,
    rules: dict[str, Any],
) -> tuple[str, str | None]:
    rule = rules["rules"]["evidence_sufficiency"]
    if reconciliation_status != "PASS":
        return "NOT_EVALUABLE", "RECONCILIATION_FAILURE"
    if identity_status != "MAPPED":
        return str(rule["unresolved_mapping_state"]), "UNRESOLVED_MAPPING"
    if freshness_status == "NOT_EVALUABLE":
        return "NOT_EVALUABLE", "OUT_OF_PERIOD"

    if freshness_status != "CURRENT":
        return "INSUFFICIENT", "STALE_EVIDENCE"
    if coverage_state == "NOT_EVALUABLE":
        return "NOT_EVALUABLE", "MISSING_EXPECTED_POPULATION"
    if tested_population == 0:
        return str(rule["zero_tested_state"]), "NOT_TESTED"
    if coverage_state == "PARTIAL":
        return str(rule["partial_coverage_state"]), "INCOMPLETE_COVERAGE"
    return "SUFFICIENT", None


def classify_control_effectiveness(
    *,
    source_result: str,
    tested_population: int,
    evidence_sufficiency: str,
    evidence_reason_code: str | None,
    rules: dict[str, Any],
) -> tuple[str, str | None]:
    rule = rules["rules"]["control_effectiveness"]
    if evidence_sufficiency in {"INSUFFICIENT", "NOT_EVALUABLE"}:
        return str(rule["insufficient_evidence_state"]), evidence_reason_code
    if bool(rule["requires_test_performed"]) and tested_population == 0:
        return str(rule["insufficient_evidence_state"]), "NOT_TESTED"
    mapping = rule["source_result_mapping"]
    if source_result not in mapping:
        raise AssuranceCalculationError(
            f"Unsupported source_result for control effectiveness: {source_result}"
        )
    return str(mapping[source_result]), None


def derive_residual_risk(
    *,
    inherent_risk: str | None,
    control_effectiveness: str,
    evidence_sufficiency: str,
    rules: dict[str, Any],
) -> tuple[str, str | None]:
    rule = rules["rules"]["residual_risk"]
    required_sufficiency = str(rule["requires_evidence_sufficiency"])
    if evidence_sufficiency != required_sufficiency:
        return str(rule["non_evaluable_input_state"]), "INSUFFICIENT_ASSURANCE_BASIS"
    if not inherent_risk:
        return str(rule["non_evaluable_input_state"]), "MISSING_INHERENT_RISK"
    matrix = rule["matrix"]
    if inherent_risk not in matrix:
        raise AssuranceCalculationError(
            f"Unsupported inherent risk state: {inherent_risk}"
        )
    row = matrix[inherent_risk]
    if control_effectiveness not in row:
        raise AssuranceCalculationError(
            "Residual-risk matrix has no outcome for "
            f"{inherent_risk} x {control_effectiveness}"
        )
    return str(row[control_effectiveness]), None


def enrich_control_assurance(
    frame: pd.DataFrame,
    rules: dict[str, Any],
    controls: pd.DataFrame,
    risk_assignments: pd.DataFrame,
) -> pd.DataFrame:
    required = {
        "test_id",
        "control_id",
        "reporting_period",
        "expected_population",
        "tested_population",
        "source_result",
        "evidence_date",
        "canonical_system_id",
        "identity_status",
        "reconciliation_status",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise AssuranceCalculationError(
            "Missing assurance calculation prerequisites: " + ", ".join(missing)
        )

    control_required = {"control_id", "risk_id"}
    risk_required = {"system_id", "risk_id", "reporting_period", "inherent_risk"}
    if not control_required.issubset(controls.columns):
        raise AssuranceCalculationError("Controls are missing required columns.")
    if not risk_required.issubset(risk_assignments.columns):
        raise AssuranceCalculationError("Risk assignments are missing required columns.")
    if controls["control_id"].duplicated().any():
        raise AssuranceCalculationError("Duplicate control_id in controls.")
    risk_key = ["system_id", "risk_id", "reporting_period"]
    if risk_assignments.duplicated(risk_key).any():
        raise AssuranceCalculationError("Duplicate risk-assignment business key.")

    result = frame.copy()
    before = len(result)
    result = result.merge(
        controls[["control_id", "risk_id"]],
        on="control_id",
        how="left",
        validate="many_to_one",
     )
    if len(result) != before:
        raise AssuranceCalculationError("Control join changed evidence row count.")
    if result["risk_id"].isna().any():
        ids = result.loc[result["risk_id"].isna(), "test_id"].astype(str).tolist()
        raise AssuranceCalculationError(
            "Missing control-to-risk mapping for test IDs: " + ", ".join(ids)
        )

    result = result.merge(
        risk_assignments[list(risk_key) + ["inherent_risk"]],
        left_on=["canonical_system_id", "risk_id", "reporting_period"],
        right_on=risk_key,
        how="left",
        validate="many_to_one",
        suffixes=("", "_assignment"),
     )
    if len(result) != before:
        raise AssuranceCalculationError("Risk-assignment join changed evidence row count.")
    result = result.drop(columns=["system_id"])

    coverage = [
        calculate_coverage(int(expected), int(tested), rules)
        for expected, tested in zip(
            result["expected_population"],
            result["tested_population"],
            strict=True,
        )
    ]
    result["coverage_ratio"] = [item[0] for item in coverage]
    result["coverage_state"] = [item[1] for item in coverage]
    result["coverage_reason_code"] = [item[2] for item in coverage]

    freshness = [
        classify_freshness(str(value), rules) for value in result["evidence_date"]
    ]
    result["evidence_age_days"] = [item[0] for item in freshness]
    result["freshness_state"] = [item[1] for item in freshness]
    result["freshness_reason_code"] = [item[2] for item in freshness]

    sufficiency = [
        classify_evidence_sufficiency(
            identity_status=str(identity),
            reconciliation_status=str(reconciliation),
            freshness_status=str(freshness_state),
            coverage_state=str(coverage_state),
            tested_population=int(tested),
            rules=rules,
        )
        for identity, reconciliation, freshness_state, coverage_state, tested in zip(
            result["identity_status"],
            result["reconciliation_status"],
            result["freshness_state"],
            result["coverage_state"],
            result["tested_population"],
            strict=True,
        )
    ]
    result["evidence_sufficiency"] = [item[0] for item in sufficiency]
    result["evidence_sufficiency_reason_code"] = [item[1] for item in sufficiency]

    effectiveness = [
        classify_control_effectiveness(
            source_result=str(source_result),
            tested_population=int(tested),
            evidence_sufficiency=str(sufficiency_state),
            evidence_reason_code=reason,
            rules=rules,
        )
        for source_result, tested, sufficiency_state, reason in zip(
            result["source_result"],
            result["tested_population"],
            result["evidence_sufficiency"],
            result["evidence_sufficiency_reason_code"],
            strict=True,
        )
    ]
    result["control_effectiveness"] = [item[0] for item in effectiveness]
    result["control_effectiveness_reason_code"] = [item[1] for item in effectiveness]

    residual = [
        derive_residual_risk(
            inherent_risk=None if pd.isna(inherent) else str(inherent),
            control_effectiveness=str(effectiveness_state),
            evidence_sufficiency=str(sufficiency_state),
            rules=rules,
        )
        for inherent, effectiveness_state, sufficiency_state in zip(
            result["inherent_risk"],
            result["control_effectiveness"],
            result["evidence_sufficiency"],
            strict=True,
        )
    ]
    result["residual_risk"] = [item[0] for item in residual]
    result["residual_risk_reason_code"] = [item[1] for item in residual]
    return result


def classify_remediation_overdue(
    *,
    target_date: str,
    status: str,
    rules: dict[str, Any],
) -> tuple[bool, int]:
    rule = rules["rules"]["remediation_overdue"]
    open_statuses = set(rule["open_statuses"])
    closed_statuses = set(rule["closed_statuses"])
    allowed_statuses = open_statuses | closed_statuses
    if status not in allowed_statuses:
        raise AssuranceCalculationError(
            f"Unsupported remediation status: {status}"
        )
    as_of = date.fromisoformat(rules["reporting"]["as_of_date"])
    target = date.fromisoformat(target_date)
    if status in closed_statuses:
        return False, 0
    overdue = target < as_of
    if not overdue:
        return False, 0
    return True, (as_of - target).days


def enrich_remediation_actions(
    actions: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    required = {"action_id", "target_date", "status"}
    missing = sorted(required - set(actions.columns))
    if missing:
        raise AssuranceCalculationError(
            "Missing remediation calculation prerequisites: " + ", ".join(missing)
        )
    if actions["action_id"].isna().any() or actions["action_id"].astype(str).str.strip().eq("").any():
        raise AssuranceCalculationError("Missing action_id in remediation actions.")
    if actions["action_id"].duplicated().any():
        raise AssuranceCalculationError("Duplicate action_id in remediation actions.")
    result = actions.copy()
    classifications = [
        classify_remediation_overdue(
            target_date=str(target_date),
            status=str(status),
            rules=rules,
        )
        for target_date, status in zip(
            result["target_date"],
            result["status"],
            strict=True,
        )
    ]
    result["overdue"] = [item[0] for item in classifications]
    result["days_overdue"] = [item[1] for item in classifications]
    return result


def detect_repeat_findings(
    findings: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    required = {
        "finding_id",
        "recurrence_key",
        "identified_date",
        "status",
        "closed_date",
    }
    missing = sorted(required - set(findings.columns))
    if missing:
        raise AssuranceCalculationError(
            "Missing repeat-finding prerequisites: " + ", ".join(missing)
        )
    if findings["finding_id"].isna().any() or findings["finding_id"].astype(str).str.strip().eq("").any():
        raise AssuranceCalculationError("Missing finding_id in findings.")
    if findings["finding_id"].duplicated().any():
        raise AssuranceCalculationError("Duplicate finding_id in findings.")
    rule = rules["rules"]["repeat_finding"]
    if not bool(rule["recurrence_key_required"]):
        raise AssuranceCalculationError(
            "Unsupported repeat-finding semantics: recurrence_key must be required."
        )
    if bool(rule["fuzzy_title_matching"]):
        raise AssuranceCalculationError(
            "Unsupported repeat-finding semantics: fuzzy title matching is not allowed."
        )
    result = findings.copy()
    identified = pd.to_datetime(result["identified_date"], errors="raise")
    closed = pd.to_datetime(result["closed_date"].replace("", pd.NA), errors="coerce")
    result["repeat_finding"] = False
    result["prior_finding_id"] = pd.NA
    for index in result.index:
        key = str(result.at[index, "recurrence_key"]).strip()
        if not key:
            raise AssuranceCalculationError(
                f"Missing recurrence_key for finding: {result.at[index, 'finding_id']}"
            )
        current_identified = identified.loc[index]
        candidates = result.index[
            (result["recurrence_key"].astype(str).str.strip() == key)
            & (result["status"] == "CLOSED")
            & closed.notna()
            & (closed < current_identified)
        ]
        candidates = candidates[candidates != index]
        if len(candidates) > 1:
            ids = result.loc[candidates, "finding_id"].astype(str).tolist()
            raise AssuranceCalculationError(
                "Ambiguous repeat-finding prior candidates for "
                f"{result.at[index, 'finding_id']}: " + ", ".join(ids)
            )
        if len(candidates) == 1:
            prior_index = candidates[0]
            result.at[index, "repeat_finding"] = True
            result.at[index, "prior_finding_id"] = result.at[prior_index, "finding_id"]
    return result
