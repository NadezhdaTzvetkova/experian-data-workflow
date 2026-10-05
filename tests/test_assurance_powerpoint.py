import json
import shutil
from pathlib import Path

import pytest

from experian_workflow.assurance import pipeline
from experian_workflow.assurance.powerpoint import (
    build_powerpoint_publication,
    validate_powerpoint_publication,
)


def test_powerpoint_publication_uses_governed_current_run_package():
    root = Path(__file__).resolve().parents[1]
    manifest = pipeline.run_assurance_pipeline(root)
    run_dir = root / "output" / "assurance_runs" / str(manifest["run_id"])

    try:
        publication_outputs = manifest["outputs"]["publication"]
        assert "powerpoint_pptx" in publication_outputs
        assert "powerpoint_slide_data" in publication_outputs
        assert "powerpoint_validation" in publication_outputs
        assert (root / publication_outputs["powerpoint_pptx"]).exists()
        assert (root / publication_outputs["powerpoint_slide_data"]).exists()
        assert (root / publication_outputs["powerpoint_validation"]).exists()

        summary = json.loads(
            (run_dir / "publication" / "validation_summary.json").read_text(
                encoding="utf-8"
            )
        )
        assert summary["scope"] == (
            "publication_foundation_html_tableau_and_powerpoint"
        )
        assert summary["powerpoint"]["status"] == "PASS"
        assert summary["powerpoint"]["slide_count"] == 8
        assert summary["powerpoint"]["internal_navigation_links"] == 114
        assert summary["powerpoint"]["run_identity_match"] is True
        assert summary["powerpoint"]["package_structure"] == "PASS"
        assert summary["powerpoint"]["client_validation"] == {
            "status": "NOT_EXECUTED",
            "validation_scope": "microsoft_powerpoint_desktop_client",
            "required_for_pipeline_success": False,
        }

        pptx_path = root / publication_outputs["powerpoint_pptx"]
        slide_data_path = root / publication_outputs["powerpoint_slide_data"]
        result = validate_powerpoint_publication(
            pptx_path=pptx_path,
            slide_data_path=slide_data_path,
            expected_run_id=str(manifest["run_id"]),
        )

        assert result["status"] == "PASS"
        assert result["slide_count"] == 8
        assert result["internal_navigation_links"] == 114
        assert len(result["external_publication_links"]) == 17
        assert result["run_identity_match"] is True
        assert result["package_structure"] == "PASS"
        assert pptx_path.exists()
        assert slide_data_path.exists()

        slide_data = json.loads(slide_data_path.read_text(encoding="utf-8"))
        metrics = json.loads(
            (run_dir / "publication" / "metrics.json").read_text(
                encoding="utf-8"
            )
        )
        assert slide_data["run_id"] == str(manifest["run_id"])
        assert slide_data["as_of_date"] == metrics["as_of_date"]
        assert slide_data["methodology_version"] == metrics["methodology_version"]
        assert slide_data["metrics"] == metrics["metrics"]
        from pptx import Presentation
        presentation = Presentation(pptx_path)
        slide5_text = " ".join(
            shape.text
            for shape in presentation.slides[4].shapes
            if hasattr(shape, "text")
        )
        for label in (
            "291 expected", "291 received", "281 mapped", "253 evaluated",
            "10 unmapped source records", "28 not tested (mapped source records)",
            "1 unmapped assurance test", "different grain", "Trust boundary",
        ):
            assert label in slide5_text
        assert "Unmapped assurance population" not in slide5_text
        assert slide_data["reconciliation"] == manifest["controls"]["reconciliation"]
        slide4_table_text = " ".join(
            cell.text
            for shape in presentation.slides[3].shapes
            if getattr(shape, "has_table", False)
            for row in shape.table.rows
            for cell in row.cells
        )
        assert len(slide_data["remediation_summary"]) == 6
        for action in slide_data["remediation_summary"]:
            assert action["action_id"] in slide4_table_text
        slide8_text = " ".join(
            shape.text
            for shape in presentation.slides[7].shapes
            if hasattr(shape, "text")
        )
        for label in (
            "Priority 1 — Restore decision confidence", "2 stale-evidence",
            "1 evidence-not-evaluable", "Priority 2 — Close risk uncertainty",
            "4 residual-risk conclusions that remain not evaluable",
            "high/critical risk", "Priority 3 — Close operational exceptions",
            "1 overdue management action", "1 unmapped assurance test",
            "Illustrative synthetic enterprise-assurance dataset and methodology",
            "not Experian internal data or methodology",
        ):
            assert label in slide8_text
        assert "Resolve the remaining evidence and remediation exceptions" not in slide8_text
        assert "Close the remaining presentation acceptance gate" not in slide8_text
        assert slide_data["attention_items"]
        assert all("D:\\" not in link for link in result["external_publication_links"])

        with pytest.raises(
            RuntimeError,
            match="PowerPoint publication directory already exists",
        ):
            build_powerpoint_publication(run_dir=run_dir)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
