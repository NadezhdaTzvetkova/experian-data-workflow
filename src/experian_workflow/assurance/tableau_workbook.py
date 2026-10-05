from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

from experian_workflow.assurance.tableau_workbook_contract import (
    validate_tableau_workbook_contract,
)


def _tableau_datatype(hyper_type: str) -> str:
    return {
        "TEXT": "string",
        "DATE": "date",
        "BOOLEAN": "boolean",
        "BIG_INT": "integer",
        "DOUBLE": "real",
    }.get(hyper_type, "string")


def _field_role_and_type(hyper_type: str) -> tuple[str, str]:
    if hyper_type in {"BIG_INT", "DOUBLE"}:
        return "measure", "quantitative"
    if hyper_type == "DATE":
        return "dimension", "ordinal"
    return "dimension", "nominal"


def _visual_instance(
    reference: str,
    *,
    dataset_id: str,
    available: dict[str, str],
) -> tuple[str, str, str, str, str]:
    aggregate = re.fullmatch(r"COUNT\(([^)]+)\)", reference)
    field_name = aggregate.group(1) if aggregate else reference
    hyper_type = available[field_name]
    if aggregate:
        instance_name = f"[cnt:{field_name}:qk]"
        derivation = "Count"
        instance_type = "quantitative"
    elif hyper_type in {"BIG_INT", "DOUBLE"}:
        instance_name = f"[none:{field_name}:qk]"
        derivation = "None"
        instance_type = "quantitative"
    elif hyper_type == "DATE":
        instance_name = f"[none:{field_name}:ok]"
        derivation = "None"
        instance_type = "ordinal"
    else:
        instance_name = f"[none:{field_name}:nk]"
        derivation = "None"
        instance_type = "nominal"
    qualified = f"[ds_{dataset_id}].{instance_name}"
    return field_name, instance_name, derivation, instance_type, qualified


def _append_visual_contract(
    *,
    table: ET.Element,
    view: ET.Element,
    dependencies: ET.Element,
    dataset_id: str,
    available: dict[str, str],
    worksheet_fields: list[str],
    visual: dict[str, Any],
) -> None:
    references: list[str] = []
    for channel in ("rows", "columns", "label", "color", "filters"):
        references.extend(str(value) for value in visual[channel])

    instances: dict[str, str] = {}
    declared_fields = set(worksheet_fields)
    for reference in dict.fromkeys(references):
        field_name, instance_name, derivation, instance_type, qualified = (
            _visual_instance(
                reference,
                dataset_id=dataset_id,
                available=available,
            )
        )
        if field_name not in declared_fields:
            role, field_type = _field_role_and_type(available[field_name])
            ET.SubElement(
                dependencies,
                "column",
                {
                    "datatype": _tableau_datatype(available[field_name]),
                    "name": f"[{field_name}]",
                    "role": role,
                    "type": field_type,
                },
            )
            declared_fields.add(field_name)
        ET.SubElement(
            dependencies,
            "column-instance",
            {
                "column": f"[{field_name}]",
                "derivation": derivation,
                "name": instance_name,
                "pivot": "key",
                "type": instance_type,
            },
        )
        instances[reference] = qualified

    for reference in visual["filters"]:
        ET.SubElement(
            view,
            "filter",
            {
                "class": "categorical",
                "column": instances[str(reference)],
            },
        )

    panes = ET.SubElement(table, "panes")
    pane = ET.SubElement(panes, "pane")
    pane_view = ET.SubElement(pane, "view")
    ET.SubElement(pane_view, "breakdown", {"value": "auto"})
    ET.SubElement(
        pane,
        "mark",
        {"class": "Bar" if visual["mark"] == "bar" else "Text"},
    )
    encodings = ET.SubElement(pane, "encodings")
    for reference in visual["label"]:
        ET.SubElement(
            encodings,
            "text",
            {"column": instances[str(reference)]},
        )
    for reference in visual["color"]:
        ET.SubElement(
            encodings,
            "color",
            {"column": instances[str(reference)]},
        )

    rows = ET.SubElement(table, "rows")
    rows.text = " / ".join(instances[str(value)] for value in visual["rows"])
    cols = ET.SubElement(table, "cols")
    cols.text = " / ".join(instances[str(value)] for value in visual["columns"])


def _build_workbook_xml(
    *,
    contract: dict[str, Any],
    dictionary: pd.DataFrame,
) -> bytes:
    root = ET.Element(
        "workbook",
        {
            "original-version": "18.1",
            "source-platform": "win",
            "version": "18.1",
        },
    )

    datasources = ET.SubElement(root, "datasources")
    dataset_fields: dict[str, list[tuple[str, str]]] = {}
    for dataset_id, group in dictionary.groupby("dataset_id", sort=False):
        dataset_fields[str(dataset_id)] = [
            (str(row.field_name), str(row.hyper_type))
            for row in group.itertuples(index=False)
        ]

    for dataset_id in sorted(dataset_fields):
        datasource_name = f"ds_{dataset_id}"
        datasource = ET.SubElement(
            datasources,
            "datasource",
            {
                "caption": dataset_id,
                "inline": "true",
                "name": datasource_name,
                "version": "18.1",
            },
        )
        connection = ET.SubElement(
            datasource,
            "connection",
            {
                "class": "hyper",
                "dbname": "Data/Extracts/assurance_dashboard.hyper",
                "schema": "Extract",
            },
        )
        ET.SubElement(
            connection,
            "relation",
            {
                "name": dataset_id,
                "table": f"[Extract].[{dataset_id}]",
                "type": "table",
            },
        )
        for field_name, hyper_type in dataset_fields[dataset_id]:
            ET.SubElement(
                datasource,
                "column",
                {
                    "datatype": _tableau_datatype(hyper_type),
                    "name": f"[{field_name}]",
                    "role": "dimension",
                    "type": "nominal",
                },
            )

    worksheets = ET.SubElement(root, "worksheets")
    for dashboard in contract["dashboards"]:
        for worksheet_spec in dashboard["worksheets"]:
            worksheet_id = str(worksheet_spec["id"])
            dataset_id = str(worksheet_spec["dataset"])
            worksheet = ET.SubElement(
                worksheets,
                "worksheet",
                {"name": worksheet_id},
            )
            table = ET.SubElement(worksheet, "table")
            view = ET.SubElement(table, "view")
            view_datasources = ET.SubElement(view, "datasources")
            ET.SubElement(
                view_datasources,
                "datasource",
                {
                    "caption": dataset_id,
                    "name": f"ds_{dataset_id}",
                },
            )
            dependencies = ET.SubElement(
                view,
                "datasource-dependencies",
                {"datasource": f"ds_{dataset_id}"},
            )
            available = dict(dataset_fields[dataset_id])
            for field_name in worksheet_spec["fields"]:
                ET.SubElement(
                    dependencies,
                    "column",
                    {
                        "datatype": _tableau_datatype(available[field_name]),
                        "name": f"[{field_name}]",
                        "role": "dimension",
                        "type": "nominal",
                    },
                )

            _append_visual_contract(
                table=table,
                view=view,
                dependencies=dependencies,
                dataset_id=dataset_id,
                available=available,
                worksheet_fields=list(worksheet_spec["fields"]),
                visual=worksheet_spec["visual"],
            )

    dashboards = ET.SubElement(root, "dashboards")
    for dashboard_spec in contract["dashboards"]:
        dashboard = ET.SubElement(
            dashboards,
            "dashboard",
            {"name": str(dashboard_spec["id"])},
        )
        zones = ET.SubElement(dashboard, "zones")
        for index, worksheet_spec in enumerate(
            dashboard_spec["worksheets"],
            start=1,
        ):
            ET.SubElement(
                zones,
                "zone",
                {
                    "id": str(index),
                    "name": str(worksheet_spec["id"]),
                    "type-v2": "sheet",
                },
            )

    ET.indent(root, space="  ")
    return ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
    )


def validate_tableau_workbook_artifacts(
    *,
    twb_path: Path,
    twbx_path: Path,
    contract_path: Path,
    dictionary_path: Path,
    hyper_path: Path,
) -> dict[str, Any]:
    contract_result = validate_tableau_workbook_contract(
        contract_path=contract_path,
        dictionary_path=dictionary_path,
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    dictionary = pd.read_csv(
        dictionary_path,
        dtype=str,
        keep_default_na=False,
    )

    if not twb_path.exists() or twb_path.stat().st_size == 0:
        raise RuntimeError("Generated Tableau TWB is missing or empty")
    if not twbx_path.exists() or twbx_path.stat().st_size == 0:
        raise RuntimeError("Generated Tableau TWBX is missing or empty")

    twb_bytes = twb_path.read_bytes()
    text = twb_bytes.decode("utf-8")
    if re.search(r"[A-Za-z]:\\\\", text):
        raise RuntimeError("Tableau workbook contains an absolute Windows path")

    root = ET.fromstring(twb_bytes)
    if root.tag != "workbook":
        raise RuntimeError("Generated Tableau TWB root is not workbook")

    worksheet_names = {
        element.attrib["name"]
        for element in root.findall("./worksheets/worksheet")
    }
    expected_worksheets = {
        str(worksheet["id"])
        for dashboard in contract["dashboards"]
        for worksheet in dashboard["worksheets"]
    }
    if worksheet_names != expected_worksheets:
        raise RuntimeError("Generated TWB worksheet set differs from contract")

    dashboard_names = {
        element.attrib["name"]
        for element in root.findall("./dashboards/dashboard")
    }
    expected_dashboards = {
        str(dashboard["id"]) for dashboard in contract["dashboards"]
    }
    if dashboard_names != expected_dashboards:
        raise RuntimeError("Generated TWB dashboard set differs from contract")

    datasource_names = {
        element.attrib["name"]
        for element in root.findall("./datasources/datasource")
    }
    expected_datasets = set(dictionary["dataset_id"].astype(str))
    if datasource_names != {f"ds_{name}" for name in expected_datasets}:
        raise RuntimeError("Generated TWB datasource set differs from dictionary")

    expected_members = {
        "assurance_dashboard.twb",
        "Data/Extracts/assurance_dashboard.hyper",
    }
    with zipfile.ZipFile(twbx_path, "r") as package:
        members = set(package.namelist())
        if members != expected_members:
            raise RuntimeError(
                f"Unexpected TWBX package members: {sorted(members)}"
            )
        packaged_twb = package.read("assurance_dashboard.twb")
        packaged_hyper = package.read(
            "Data/Extracts/assurance_dashboard.hyper"
        )

    if packaged_twb != twb_bytes:
        raise RuntimeError("Packaged TWB differs from standalone TWB")
    if packaged_hyper != hyper_path.read_bytes():
        raise RuntimeError("Packaged Hyper differs from validated Hyper")

    return {
        "status": "PASS",
        "acceptance_model": "PROGRAMMATIC_TABLEAU",
        "dashboard_count": contract_result["dashboard_count"],
        "worksheet_count": contract_result["worksheet_count"],
        "dataset_count": len(expected_datasets),
        "twb_structure": "PASS",
        "twbx_package": "PASS",
        "hyper_identity_match": True,
        "package_members": sorted(expected_members),
    }


def build_tableau_workbook(
    *,
    run_dir: Path,
    contract_path: Path,
    dictionary_path: Path,
    hyper_path: Path,
) -> dict[str, Any]:
    tableau_dir = run_dir / "publication" / "tableau"
    tableau_dir.mkdir(parents=True, exist_ok=True)
    twb_path = tableau_dir / "assurance_dashboard.twb"
    twbx_path = tableau_dir / "assurance_dashboard.twbx"

    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    dictionary = pd.read_csv(
        dictionary_path,
        dtype=str,
        keep_default_na=False,
    )

    validate_tableau_workbook_contract(
        contract_path=contract_path,
        dictionary_path=dictionary_path,
    )

    twb_bytes = _build_workbook_xml(
        contract=contract,
        dictionary=dictionary,
    )
    twb_path.write_bytes(twb_bytes)

    with zipfile.ZipFile(
        twbx_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as package:
        package.writestr("assurance_dashboard.twb", twb_bytes)
        package.write(
            hyper_path,
            arcname="Data/Extracts/assurance_dashboard.hyper",
        )

    result = validate_tableau_workbook_artifacts(
        twb_path=twb_path,
        twbx_path=twbx_path,
        contract_path=contract_path,
        dictionary_path=dictionary_path,
        hyper_path=hyper_path,
    )
    result["twb_path"] = twb_path
    result["twbx_path"] = twbx_path
    return result
