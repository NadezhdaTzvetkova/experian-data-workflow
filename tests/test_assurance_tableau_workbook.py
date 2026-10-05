import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.tableau_workbook import (
    build_tableau_workbook,
    validate_tableau_workbook_artifacts,
)


def test_programmatic_tableau_workbook_and_package_match_contract():
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = root / "output" / "assurance_runs" / str(manifest["run_id"])

    try:
        publication_outputs = manifest["outputs"]["publication"]
        assert "tableau_twb" in publication_outputs
        assert "tableau_twbx" in publication_outputs
        assert (root / publication_outputs["tableau_twb"]).exists()
        assert (root / publication_outputs["tableau_twbx"]).exists()

        summary = json.loads(
            (run_dir / "publication" / "validation_summary.json").read_text(
                encoding="utf-8"
            )
        )
        assert summary["scope"] == "publication_foundation_html_tableau_and_powerpoint"
        assert summary["tableau_workbook"]["status"] == "PASS"
        assert summary["tableau_workbook"]["acceptance_model"] == (
            "PROGRAMMATIC_TABLEAU"
        )
        assert summary["tableau_workbook"]["dashboard_count"] == 4
        assert summary["tableau_workbook"]["worksheet_count"] == 11
        assert summary["tableau_workbook"]["dataset_count"] == 8
        assert summary["tableau_workbook"]["twb_structure"] == "PASS"
        assert summary["tableau_workbook"]["visual_contract"] == "PASS"
        assert summary["tableau_workbook"]["twbx_package"] == "PASS"

        tableau_dir = run_dir / "publication" / "tableau"
        twb_path = tableau_dir / "assurance_dashboard.twb"
        twbx_path = tableau_dir / "assurance_dashboard.twbx"
        contract_path = (
            root / "config" / "assurance" / "tableau_workbook_contract.json"
        )
        dictionary_path = tableau_dir / "tableau_data_dictionary.csv"
        hyper_path = tableau_dir / "assurance_dashboard.hyper"
        result = validate_tableau_workbook_artifacts(
            twb_path=twb_path,
            twbx_path=twbx_path,
            contract_path=contract_path,
            dictionary_path=dictionary_path,
            hyper_path=hyper_path,
        )

        assert result["status"] == "PASS"
        assert result["acceptance_model"] == "PROGRAMMATIC_TABLEAU"
        assert result["dashboard_count"] == 4
        assert result["worksheet_count"] == 11
        assert result["dataset_count"] == 8
        assert result["twb_structure"] == "PASS"
        assert result["visual_contract"] == "PASS"
        assert result["twbx_package"] == "PASS"
        assert result["hyper_identity_match"] is True
        assert result["package_members"] == [
            "Data/Extracts/assurance_dashboard.hyper",
            "assurance_dashboard.twb",
        ]
        assert twb_path.exists()
        assert twbx_path.exists()

        workbook_root = ET.parse(twb_path).getroot()
        worksheets = workbook_root.findall("./worksheets/worksheet")
        assert len(worksheets) == 11
        for worksheet in worksheets:
            panes = worksheet.findall("./table/panes/pane")
            marks = worksheet.findall("./table/panes/pane/mark")
            rows = worksheet.find("./table/rows")
            cols = worksheet.find("./table/cols")
            encodings = worksheet.findall("./table/panes/pane/encodings/*")
            assert panes, worksheet.attrib["name"]
            assert marks, worksheet.attrib["name"]
            assert (
                (rows is not None and bool((rows.text or "").strip()))
                or (cols is not None and bool((cols.text or "").strip()))
                or bool(encodings)
            ), worksheet.attrib["name"]

        with pytest.raises(
            RuntimeError,
            match="Tableau workbook output already exists",
        ):
            build_tableau_workbook(
                run_dir=run_dir,
                contract_path=contract_path,
                dictionary_path=dictionary_path,
                hyper_path=hyper_path,
            )
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

def test_tableau_workbook_validator_rejects_visual_contract_drift(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = root / "output" / "assurance_runs" / str(manifest["run_id"])

    try:
        tableau_dir = run_dir / "publication" / "tableau"
        source_twb = tableau_dir / "assurance_dashboard.twb"
        mutated_twb = tmp_path / "assurance_dashboard.twb"

        tree = ET.parse(source_twb)
        worksheet = tree.getroot().find(
            './worksheets/worksheet[@name="risk_domain_overview"]'
        )
        assert worksheet is not None
        mark = worksheet.find("./table/panes/pane/mark")
        assert mark is not None
        mark.set("class", "Text")
        tree.write(
            mutated_twb,
            encoding="utf-8",
            xml_declaration=True,
        )

        with pytest.raises(
            RuntimeError,
            match=("Worksheet mark differs from contract for "
                   "risk_domain_overview"),
        ):
            validate_tableau_workbook_artifacts(
                twb_path=mutated_twb,
                twbx_path=tableau_dir / "assurance_dashboard.twbx",
                contract_path=(
                    root
                    / "config"
                    / "assurance"
                    / "tableau_workbook_contract.json"
                ),
                dictionary_path=tableau_dir / "tableau_data_dictionary.csv",
                hyper_path=tableau_dir / "assurance_dashboard.hyper",
            )
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
