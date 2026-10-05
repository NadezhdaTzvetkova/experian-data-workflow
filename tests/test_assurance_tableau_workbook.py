import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.tableau_workbook import build_tableau_workbook


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
        assert summary["tableau_workbook"]["twbx_package"] == "PASS"

        result = build_tableau_workbook(
            run_dir=run_dir,
            contract_path=root / "config" / "assurance" / "tableau_workbook_contract.json",
            dictionary_path=run_dir / "publication" / "tableau" / "tableau_data_dictionary.csv",
            hyper_path=run_dir / "publication" / "tableau" / "assurance_dashboard.hyper",
        )

        assert result["status"] == "PASS"
        assert result["acceptance_model"] == "PROGRAMMATIC_TABLEAU"
        assert result["dashboard_count"] == 4
        assert result["worksheet_count"] == 11
        assert result["dataset_count"] == 8
        assert result["twb_structure"] == "PASS"
        assert result["twbx_package"] == "PASS"
        assert result["hyper_identity_match"] is True
        assert result["package_members"] == [
            "Data/Extracts/assurance_dashboard.hyper",
            "assurance_dashboard.twb",
        ]
        assert Path(result["twb_path"]).exists()
        assert Path(result["twbx_path"]).exists()

        workbook_root = ET.parse(result["twb_path"]).getroot()
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
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
