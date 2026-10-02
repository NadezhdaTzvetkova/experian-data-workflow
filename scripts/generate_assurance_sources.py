from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import closing
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "config" / "assurance" / "synthetic_source_spec.yaml"


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        spec = yaml.safe_load(handle)

    if spec.get("spec_role") != "synthetic_generator_input_only":
        raise ValueError("Unexpected assurance source specification role.")

    generation = spec.get("generation", {})
    if generation.get("deterministic") is not True:
        raise ValueError("Assurance source generation must be deterministic.")
    if generation.get("random_generation_allowed") is not False:
        raise ValueError("Random assurance source generation is not permitted.")

    return spec


def _path_from_spec(spec: dict[str, Any], key: str) -> Path:
    value = spec["generation"][key]
    return ROOT / value


def _as_sqlite_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    return value


def _execute_many(
    connection: sqlite3.Connection,
    sql: str,
    rows: list[tuple[Any, ...]],
) -> None:
    if rows:
        connection.executemany(sql, rows)


def create_enterprise_database(spec: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        output_path.unlink()

    with closing(sqlite3.connect(output_path)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")

        connection.executescript(
            """
            CREATE TABLE entities (
                entity_id TEXT PRIMARY KEY,
                entity_name TEXT NOT NULL,
                region TEXT NOT NULL,
                country TEXT NOT NULL,
                business_unit TEXT NOT NULL,
                acquired_status TEXT NOT NULL,
                acquisition_cohort TEXT,
                effective_from TEXT NOT NULL,
                effective_to TEXT
            );

            CREATE TABLE systems (
                system_id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                system_name TEXT NOT NULL,
                system_owner TEXT NOT NULL,
                criticality TEXT NOT NULL,
                data_classification TEXT NOT NULL,
                contains_sensitive_data INTEGER NOT NULL,
                core_acquired_status TEXT NOT NULL,
                acquisition_cohort TEXT,
                third_party_dependency_flag INTEGER NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
            );

            CREATE TABLE risk_taxonomy (
                risk_id TEXT PRIMARY KEY,
                risk_domain TEXT NOT NULL,
                risk_name TEXT NOT NULL,
                risk_description TEXT NOT NULL
            );

            CREATE TABLE risk_assignments (
                system_id TEXT NOT NULL,
                risk_id TEXT NOT NULL,
                reporting_period TEXT NOT NULL,
                inherent_risk TEXT NOT NULL,
                PRIMARY KEY (system_id, risk_id, reporting_period),
                FOREIGN KEY (system_id) REFERENCES systems(system_id),
                FOREIGN KEY (risk_id) REFERENCES risk_taxonomy(risk_id)
            );

            CREATE TABLE controls (
                control_id TEXT PRIMARY KEY,
                risk_id TEXT NOT NULL,
                control_name TEXT NOT NULL,
                control_objective TEXT NOT NULL,
                control_type TEXT NOT NULL,
                expected_frequency TEXT NOT NULL,
                expected_evidence_type TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                FOREIGN KEY (risk_id) REFERENCES risk_taxonomy(risk_id)
            );

            CREATE TABLE source_registry (
                source_id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_owner TEXT NOT NULL,
                expected_grain TEXT NOT NULL,
                expected_frequency TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                classification TEXT NOT NULL,
                known_limitation TEXT
            );

            CREATE TABLE source_expectations (
                source_id TEXT NOT NULL,
                reporting_period TEXT NOT NULL,
                expected_record_count INTEGER NOT NULL,
                PRIMARY KEY (source_id, reporting_period),
                FOREIGN KEY (source_id) REFERENCES source_registry(source_id)
            );

            CREATE TABLE system_mappings (
                source_system TEXT NOT NULL,
                raw_system_id TEXT NOT NULL,
                canonical_system_id TEXT,
                mapping_status TEXT NOT NULL,
                PRIMARY KEY (source_system, raw_system_id),
                FOREIGN KEY (source_system) REFERENCES source_registry(source_id),
                FOREIGN KEY (canonical_system_id) REFERENCES systems(system_id)
            );

            CREATE TABLE third_parties (
                third_party_id TEXT PRIMARY KEY,
                third_party_name TEXT NOT NULL,
                tier TEXT NOT NULL,
                sensitive_access_flag INTEGER NOT NULL,
                assurance_status TEXT NOT NULL,
                last_assurance_date TEXT NOT NULL
            );

            CREATE TABLE system_third_parties (
                system_id TEXT NOT NULL,
                third_party_id TEXT NOT NULL,
                PRIMARY KEY (system_id, third_party_id),
                FOREIGN KEY (system_id) REFERENCES systems(system_id),
                FOREIGN KEY (third_party_id) REFERENCES third_parties(third_party_id)
            );
            """
        )

        _execute_many(
            connection,
            """
            INSERT INTO entities (
                entity_id,
                entity_name,
                region,
                country,
                business_unit,
                acquired_status,
                acquisition_cohort,
                effective_from,
                effective_to
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["entity_id"],
                    row["entity_name"],
                    row["region"],
                    row["country"],
                    row["business_unit"],
                    row["acquired_status"],
                    row.get("acquisition_cohort"),
                    row["effective_from"],
                    row.get("effective_to"),
                )
                for row in spec["entities"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO systems (
                system_id,
                entity_id,
                system_name,
                system_owner,
                criticality,
                data_classification,
                contains_sensitive_data,
                core_acquired_status,
                acquisition_cohort,
                third_party_dependency_flag,
                effective_from,
                effective_to
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["system_id"],
                    row["entity_id"],
                    row["system_name"],
                    row["system_owner"],
                    row["criticality"],
                    row["data_classification"],
                    _as_sqlite_bool(row["contains_sensitive_data"]),
                    row["core_acquired_status"],
                    row.get("acquisition_cohort"),
                    _as_sqlite_bool(row["third_party_dependency_flag"]),
                    row["effective_from"],
                    row.get("effective_to"),
                )
                for row in spec["systems"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO risk_taxonomy (
                risk_id,
                risk_domain,
                risk_name,
                risk_description
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    row["risk_id"],
                    row["risk_domain"],
                    row["risk_name"],
                    row["risk_description"],
                )
                for row in spec["risk_taxonomy"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO risk_assignments (
                system_id,
                risk_id,
                reporting_period,
                inherent_risk
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    row["system_id"],
                    row["risk_id"],
                    row["reporting_period"],
                    row["inherent_risk"],
                )
                for row in spec["risk_assignments"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO controls (
                control_id,
                risk_id,
                control_name,
                control_objective,
                control_type,
                expected_frequency,
                expected_evidence_type,
                effective_from,
                effective_to
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["control_id"],
                    row["risk_id"],
                    row["control_name"],
                    row["control_objective"],
                    row["control_type"],
                    row["expected_frequency"],
                    row["expected_evidence_type"],
                    row["effective_from"],
                    row.get("effective_to"),
                )
                for row in spec["controls"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO source_registry (
                source_id,
                source_name,
                source_type,
                source_owner,
                expected_grain,
                expected_frequency,
                schema_version,
                classification,
                known_limitation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["source_id"],
                    row["source_name"],
                    row["source_type"],
                    row["source_owner"],
                    row["expected_grain"],
                    row["expected_frequency"],
                    row["schema_version"],
                    row["classification"],
                    row.get("known_limitation"),
                )
                for row in spec["source_registry"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO source_expectations (
                source_id,
                reporting_period,
                expected_record_count
            )
            VALUES (?, ?, ?)
            """,
            [
                (
                    row["source_id"],
                    row["reporting_period"],
                    row["expected_record_count"],
                )
                for row in spec["source_expectations"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO system_mappings (
                source_system,
                raw_system_id,
                canonical_system_id,
                mapping_status
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    row["source_system"],
                    row["raw_system_id"],
                    row.get("canonical_system_id"),
                    row["mapping_status"],
                )
                for row in spec["system_mappings"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO third_parties (
                third_party_id,
                third_party_name,
                tier,
                sensitive_access_flag,
                assurance_status,
                last_assurance_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["third_party_id"],
                    row["third_party_name"],
                    row["tier"],
                    _as_sqlite_bool(row["sensitive_access_flag"]),
                    row["assurance_status"],
                    row["last_assurance_date"],
                )
                for row in spec["third_parties"]
            ],
        )

        _execute_many(
            connection,
            """
            INSERT INTO system_third_parties (
                system_id,
                third_party_id
            )
            VALUES (?, ?)
            """,
            [
                (
                    row["system_id"],
                    row["third_party_id"],
                )
                for row in spec["system_third_parties"]
            ],
        )

        foreign_key_violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_violations:
            raise ValueError(
                "Generated assurance SQLite database has foreign-key "
                f"violations: {foreign_key_violations}"
            )


def write_control_evidence(spec: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": "1.0",
        "reporting_period": spec["reporting_period"],
        "records": spec["control_evidence_records"],
    }

    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(
    output_path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_findings(spec: dict[str, Any], output_path: Path) -> None:
    _write_csv(
        output_path,
        spec["findings"],
        [
            "finding_id",
            "scenario_id",
            "system_id",
            "control_id",
            "recurrence_key",
            "finding_theme",
            "severity",
            "identified_date",
            "status",
            "closed_date",
        ],
    )


def write_management_actions(spec: dict[str, Any], output_path: Path) -> None:
    _write_csv(
        output_path,
        spec["management_actions"],
        [
            "action_id",
            "scenario_id",
            "finding_id",
            "action_owner",
            "target_date",
            "status",
            "closed_date",
            "closure_validation_status",
        ],
    )


def _test_record_by_id(
    spec: dict[str, Any],
    test_id: str,
) -> dict[str, Any]:
    matches = [
        row
        for row in spec["control_evidence_records"]
        if row["test_id"] == test_id
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one control-evidence record for {test_id}; "
            f"found {len(matches)}."
        )

    return deepcopy(matches[0])


def write_adversarial_sources(spec: dict[str, Any]) -> None:
    adversarial = spec["adversarial_control_evidence"]

    breaking = adversarial["breaking_variant"]
    breaking_record = _test_record_by_id(spec, breaking["base_test_id"])
    removed_field = breaking["mutation"]["remove_required_field"]

    if removed_field not in breaking_record:
        raise ValueError(
            f"Breaking mutation field {removed_field!r} does not exist in base record."
        )

    breaking_record.pop(removed_field)

    breaking_payload = {
        "fixture_id": breaking["fixture_id"],
        "schema_version": breaking["schema_version"],
        "reporting_period": spec["reporting_period"],
        "records": [breaking_record],
    }

    breaking_path = _path_from_spec(spec, "breaking_schema_output")
    breaking_path.parent.mkdir(parents=True, exist_ok=True)
    breaking_path.write_text(
        json.dumps(breaking_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    additive = adversarial["additive_variant"]
    additive_record = _test_record_by_id(spec, additive["base_test_id"])
    additive_field = additive["mutation"]["add_optional_field"]
    additive_record[additive_field["name"]] = additive_field["value"]

    additive_payload = {
        "fixture_id": additive["fixture_id"],
        "schema_version": additive["schema_version"],
        "reporting_period": spec["reporting_period"],
        "records": [additive_record],
    }

    additive_path = _path_from_spec(spec, "additive_schema_output")
    additive_path.parent.mkdir(parents=True, exist_ok=True)
    additive_path.write_text(
        json.dumps(additive_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def generate_assurance_sources(spec_path: Path = SPEC_PATH) -> None:
    spec = load_spec(spec_path)

    create_enterprise_database(
        spec,
        _path_from_spec(spec, "sqlite_output"),
    )
    write_control_evidence(
        spec,
        _path_from_spec(spec, "control_evidence_output"),
    )
    write_findings(
        spec,
        _path_from_spec(spec, "findings_output"),
    )
    write_management_actions(
        spec,
        _path_from_spec(spec, "management_actions_output"),
    )
    write_adversarial_sources(spec)


if __name__ == "__main__":
    generate_assurance_sources()
