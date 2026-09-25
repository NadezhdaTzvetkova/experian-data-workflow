import json
import shutil
from pathlib import Path

import pandas as pd

from experian_workflow.evidence import sha256_file
from experian_workflow.pipeline import run_pipeline


def test_pipeline_persists_reconciled_audit_evidence(tmp_path: Path):
    project = tmp_path / "project"
    (project / "config").mkdir(parents=True)
    (project / "data" / "source").mkdir(parents=True)
    (project / "output" / "runs").mkdir(parents=True)

    shutil.copy2("config/expense_policy.yaml", project / "config" / "expense_policy.yaml")
    shutil.copy2("data/source/expenses.csv", project / "data" / "source" / "expenses.csv")
    shutil.copy2("data/source/vendors.db", project / "data" / "source" / "vendors.db")

    manifest = run_pipeline(project)

    assert manifest["status"] == "SUCCESS_WITH_QUARANTINE"
    assert manifest["counts"] == {
        "source": 120,
        "accepted": 115,
        "quarantined": 5,
        "curated": 115,
    }
    assert manifest["reconciliation"]["source_equals_accepted_plus_quarantined"] is True
    assert manifest["reconciliation"]["accepted_equals_curated_after_enrichment"] is True

    quarantine_path = project / manifest["outputs"]["quarantine"]
    curated_path = project / manifest["outputs"]["curated"]
    manifest_path = project / manifest["outputs"]["manifest"]

    assert quarantine_path.exists()
    assert curated_path.exists()
    assert manifest_path.exists()

    quarantine = pd.read_csv(quarantine_path)
    curated = pd.read_parquet(curated_path)
    persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert len(quarantine) == 5
    assert len(curated) == 115
    assert persisted_manifest == manifest

    assert manifest["source_inventory"]["expenses"]["sha256"] == sha256_file(project / "data/source/expenses.csv")
    assert manifest["source_inventory"]["vendors"]["sha256"] == sha256_file(project / "data/source/vendors.db")
    assert manifest["source_inventory"]["policy"]["sha256"] == sha256_file(project / "config/expense_policy.yaml")

    assert "\\" not in manifest["outputs"]["quarantine"]
    assert "\\" not in manifest["outputs"]["curated"]
    assert "\\" not in manifest["outputs"]["manifest"]
