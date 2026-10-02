import json
from pathlib import Path

from scripts.evaluate_step4 import METRIC_FIELDS, evaluate


ROOT = Path(__file__).resolve().parents[1]


def test_step4_development_evaluator_reports_requested_metrics():
    result = evaluate(ROOT / "evals/step4_dev.jsonl", ROOT)
    assert result["total"] == 20
    assert result["failed"] == 0
    assert set(result["metrics"]) == set(METRIC_FIELDS) | {"full_structured_result_match"}
    assert all(metric["accuracy"] == 1.0 for metric in result["metrics"].values())


def test_step4_evaluator_reports_numeric_mismatch(tmp_path):
    dataset = tmp_path / "failure.jsonl"
    dataset.write_text(json.dumps({
        "case_id": "failure",
        "question": "What were Henkel H1 2026 sales?",
        "expected": {"outcome": "SUCCESS", "primary_value": "0", "unit": "EUR_million"},
    }) + "\n", encoding="utf-8")
    result = evaluate(dataset, ROOT)
    assert result["failed"] == 1
    assert result["metrics"]["numeric_accuracy"]["accuracy"] == 0.0
    assert result["metrics"]["unit_correctness"]["accuracy"] == 1.0
    assert result["failures"][0]["mismatches"]["primary_value"]["actual"] == "10348"
