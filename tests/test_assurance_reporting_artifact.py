import shutil
from pathlib import Path

import pandas as pd

from experian_workflow.assurance.pipeline import run_assurance_pipeline


def test_pipeline_persists_governed_reporting_mart():
    root = Path(__file__).resolve().parents[1]
    manifest = run_assurance_pipeline(root)
    run_dir = root / "output" / "assurance_runs" / str(manifest["run_id"])
    try:
        assert "assurance_reporting_mart" in manifest["outputs"]
        mart_path = root / str(manifest["outputs"]["assurance_reporting_mart"])
        assurance_path = root / str(manifest["outputs"]["control_assurance"])
        assert mart_path.exists()
        assert mart_path.is_file()
        mart = pd.read_parquet(mart_path)
        assurance = pd.read_parquet(assurance_path)
        key = ["test_id", "reporting_period"]
        assert len(mart) == len(assurance)
        assert not mart.duplicated(key).any()
        assert set(map(tuple, mart[key].itertuples(index=False, name=None))) == set(map(tuple, assurance[key].itertuples(index=False, name=None)))
        assert len(mart.columns) > len(assurance.columns)
        assert {"system_name", "entity_name", "control_name", "risk_name", "region", "business_unit"}.issubset(mart.columns)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
