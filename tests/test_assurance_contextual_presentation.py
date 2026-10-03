from pathlib import Path

from experian_workflow.assurance.pipeline import run_assurance_pipeline


def test_assurance_report_includes_contextual_analytical_views(tmp_path):
    root = Path(__file__).resolve().parents[1]

    manifest = run_assurance_pipeline(root)
    report_path = root / str(manifest["outputs"]["assurance_report"])
    html = report_path.read_text(encoding="utf-8")

    assert "Assurance by risk domain" in html
    assert "Finding and remediation priorities" in html
    assert "Access Management" in html
    assert "Third Party" in html
    assert "FND_IAM_006" in html
    assert "FND_TP_001" in html
