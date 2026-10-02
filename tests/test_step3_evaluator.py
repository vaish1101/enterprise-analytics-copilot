import json
from pathlib import Path

from scripts.evaluate_planner import METRIC_FIELDS, evaluate


ROOT = Path(__file__).resolve().parents[1]


def test_development_evaluator_reports_all_requested_metrics():
    result = evaluate(ROOT / "evals/dev.jsonl", ROOT)
    assert result["total"] == 20
    assert result["failed"] == 0
    assert set(result["metrics"]) == set(METRIC_FIELDS) | {"full_plan_exact_match"}
    assert all(metric["accuracy"] == 1.0 for metric in result["metrics"].values())


def test_evaluator_reports_field_level_failure(tmp_path):
    dataset = tmp_path / "failure.jsonl"
    dataset.write_text(json.dumps({
        "question_id": "failure",
        "question": "What were Henkel H1 2026 sales?",
        "expected": {"question_type": "CALCULATION", "status": "READY"},
    }) + "\n", encoding="utf-8")
    result = evaluate(dataset, ROOT)
    assert result["failed"] == 1
    assert result["metrics"]["classification_accuracy"]["accuracy"] == 0.0
    assert result["metrics"]["status_accuracy"]["accuracy"] == 1.0
    assert result["failures"][0]["mismatches"]["question_type"]["actual"] == "REPORTED_FACT"
