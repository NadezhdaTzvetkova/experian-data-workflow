from pathlib import Path

import yaml

from experian_workflow.assurance.reporting import build_assurance_kpis


def test_assurance_metric_dictionary_covers_all_published_kpis():
    root = Path(__file__).resolve().parents[1]
    path = root / "config" / "assurance" / "metrics.yaml"

    assert path.exists(), "Missing governed assurance metric dictionary"

    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert contract["schema_version"] == "1.0"
    assert contract["methodology"]["name"] == "synthetic_enterprise_assurance_demo"
    assert contract["methodology"]["version"] == "2026-09-v1"

    metrics = contract["metrics"]
    required_fields = {
        "trusted_population",
        "numerator",
        "denominator",
        "units",
        "filter_semantics",
        "business_question",
        "limitation",
        "empty_scope_state",
        "aggregation",
    }

    for metric_name, definition in metrics.items():
        assert required_fields.issubset(definition), metric_name

    import pandas as pd

    assurance = pd.DataFrame(
        {
            "evidence_sufficiency": ["SUFFICIENT"],
            "freshness_state": ["CURRENT"],
            "identity_status": ["MAPPED"],
            "residual_risk": ["LOW"],
        }
    )
    remediation = pd.DataFrame({"overdue": [False]})
    findings = pd.DataFrame(
        {
            "repeat_finding": [False],
            "status": ["OPEN"],
        }
    )

    published = build_assurance_kpis(assurance, remediation, findings)
    assert set(metrics) == set(published)

def test_metric_dictionary_has_machine_executable_calculation_specs():
    root = Path(__file__).resolve().parents[1]
    path = root / "config" / "assurance" / "metrics.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))

    metrics = contract["metrics"]

    allowed_populations = {
        "control_assurance",
        "remediation_actions",
        "findings",
    }
    allowed_operators = {
        "all",
        "eq",
        "in",
    }

    for metric_name, definition in metrics.items():
        calculation = definition.get("calculation")

        assert isinstance(calculation, dict), metric_name
        assert calculation.get("population") in allowed_populations, metric_name
        assert calculation.get("aggregation") == "count", metric_name
        assert calculation.get("operator") in allowed_operators, metric_name

        operator = calculation["operator"]

        if operator == "all":
            assert "field" not in calculation, metric_name
            assert "value" not in calculation, metric_name
            assert "values" not in calculation, metric_name

        elif operator == "eq":
            assert isinstance(calculation.get("field"), str), metric_name
            assert "value" in calculation, metric_name
            assert "values" not in calculation, metric_name

        elif operator == "in":
            assert isinstance(calculation.get("field"), str), metric_name
            assert isinstance(calculation.get("values"), list), metric_name
            assert calculation["values"], metric_name
            assert "value" not in calculation, metric_name


def test_metric_dictionary_structured_specs_match_governed_population_names():
    root = Path(__file__).resolve().parents[1]
    path = root / "config" / "assurance" / "metrics.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))

    for metric_name, definition in contract["metrics"].items():
        calculation = definition["calculation"]
        assert (
            calculation["population"]
            == definition["trusted_population"]
        ), metric_name
