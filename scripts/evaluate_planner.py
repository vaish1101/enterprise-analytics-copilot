"""Evaluate the deterministic Step 3 planner against a frozen JSONL dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.planning import QuestionPlanner  # noqa: E402


METRIC_FIELDS = {
    "classification_accuracy": ("question_type",),
    "company_resolution_accuracy": ("company", "comparison_company"),
    "metric_resolution_accuracy": ("metric_id", "comparison_metric_id"),
    "scope_resolution_accuracy": ("business_scope",),
    "period_resolution_accuracy": ("period", "comparison_period"),
    "status_accuracy": ("status",),
    "clarification_accuracy": ("clarification_required",),
    "unsupported_detection_accuracy": ("unsupported_required",),
    "comparability_gate_accuracy": ("comparability_status",),
}


def _flatten(plan) -> dict[str, object]:
    primary = plan.primary_target
    comparison = plan.comparison_target
    return {
        "question_type": plan.question_type.value,
        "status": plan.status.value,
        "company": primary.company.value if primary else None,
        "metric_id": primary.metric_id.value if primary else None,
        "business_scope": primary.business_scope if primary else None,
        "period": primary.period.value if primary and primary.period else None,
        "comparison_period": primary.comparison_period.value if primary and primary.comparison_period else None,
        "comparison_company": comparison.company.value if comparison else None,
        "comparison_metric_id": comparison.metric_id.value if comparison else None,
        "clarification_required": plan.clarification_question is not None,
        "unsupported_required": plan.unsupported_reason is not None,
        "comparability_status": plan.comparability_status.value,
    }


def evaluate(dataset: Path, root: Path) -> dict[str, object]:
    planner = QuestionPlanner(root)
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    failures: list[dict[str, object]] = []
    score_counts = {name: {"correct": 0, "total": 0} for name in METRIC_FIELDS}
    for case in cases:
        actual = _flatten(planner.plan(case["question"], question_id=case["question_id"]))
        mismatches = {
            key: {"expected": expected, "actual": actual.get(key)}
            for key, expected in case["expected"].items()
            if actual.get(key) != expected
        }
        if mismatches:
            failures.append({"question_id": case["question_id"], "mismatches": mismatches})
        for name, fields in METRIC_FIELDS.items():
            applicable = [field for field in fields if field in case["expected"]]
            if applicable:
                score_counts[name]["total"] += 1
                if all(actual.get(field) == case["expected"][field] for field in applicable):
                    score_counts[name]["correct"] += 1
    passed = len(cases) - len(failures)
    metrics = {
        name: {
            **counts,
            "accuracy": counts["correct"] / counts["total"] if counts["total"] else None,
        }
        for name, counts in score_counts.items()
    }
    metrics["full_plan_exact_match"] = {
        "correct": passed,
        "total": len(cases),
        "accuracy": passed / len(cases) if cases else None,
    }
    return {
        "dataset": str(dataset), "total": len(cases), "passed": passed,
        "failed": len(failures), "accuracy": passed / len(cases) if cases else 0.0,
        "metrics": metrics,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.dataset, ROOT)
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
