"""Deterministic Step 4 evaluation for development and frozen test datasets."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics import AnalyticsExecutor, ExecutionRejectedError  # noqa: E402
from src.planning import QuestionPlanner  # noqa: E402
from src.planning.models import PlanningStatus  # noqa: E402


METRIC_FIELDS = {
    "fact_retrieval_accuracy": ("primary_value",),
    "numeric_accuracy": (
        "primary_value", "absolute_change", "percentage_change", "percentage_point_change",
        "component_values", "ranked_top_value",
    ),
    "unit_correctness": ("unit",),
    "provenance_correctness": ("primary_provenance", "provenance_types"),
    "evidence_linkage_correctness": ("evidence_linked",),
    "calculation_rule_selection_accuracy": ("rule_ids",),
    "reconciliation_accuracy": ("reconciliation_pass", "reconciliation_count"),
    "decomposition_completeness": ("component_count", "component_values"),
    "ranking_correctness": ("ranked_top_label", "ranked_top_value"),
    "invalid_operation_rejection": ("outcome", "rejection_stage"),
}


def _decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _flatten_success(result) -> dict[str, object]:
    components = {item.reported_name: _decimal(item.value) for item in result.decomposition_components}
    return {
        "outcome": "SUCCESS",
        "operation": result.operation.value,
        "primary_fact_id": result.primary_result.fact_id,
        "primary_value": _decimal(result.primary_result.value),
        "unit": result.primary_result.unit.value,
        "primary_provenance": result.primary_result.provenance_type.value,
        "provenance_types": sorted(item.provenance_type.value for item in result.provenance_summary),
        "evidence_linked": bool(result.evidence_ids),
        "absolute_change": _decimal(result.absolute_change),
        "percentage_change": _decimal(result.percentage_change),
        "percentage_point_change": _decimal(result.percentage_point_change),
        "component_count": len(result.decomposition_components),
        "component_values": components,
        "ranked_top_label": result.ranked_components[0].component_label if result.ranked_components else None,
        "ranked_top_value": _decimal(result.ranked_components[0].value) if result.ranked_components else None,
        "reconciliation_pass": all(item.passed for item in result.reconciliation_results) if result.reconciliation_results else None,
        "reconciliation_count": len(result.reconciliation_results),
        "rule_ids": [run.rule_id.value for run in result.calculation_runs],
    }


def evaluate(dataset: Path, root: Path = ROOT) -> dict[str, object]:
    planner = QuestionPlanner(root)
    fixed_time = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    executor = AnalyticsExecutor(root, clock=lambda: fixed_time)
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    failures: list[dict[str, object]] = []
    score_counts = {name: {"correct": 0, "total": 0} for name in METRIC_FIELDS}
    for case in cases:
        plan = planner.plan(case["question"], question_id=case["case_id"])
        if plan.status is not PlanningStatus.READY:
            actual = {"outcome": "REJECTED", "rejection_stage": "PLANNER"}
        else:
            try:
                actual = _flatten_success(executor.execute(plan))
            except ExecutionRejectedError:
                actual = {"outcome": "REJECTED", "rejection_stage": "EXECUTOR"}
        mismatches = {
            key: {"expected": expected, "actual": actual.get(key)}
            for key, expected in case["expected"].items()
            if actual.get(key) != expected
        }
        if mismatches:
            failures.append({"case_id": case["case_id"], "mismatches": mismatches})
        for name, fields in METRIC_FIELDS.items():
            if name == "invalid_operation_rejection" and case["expected"].get("outcome") != "REJECTED":
                continue
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
    metrics["full_structured_result_match"] = {
        "correct": passed, "total": len(cases),
        "accuracy": passed / len(cases) if cases else None,
    }
    return {
        "dataset": str(dataset), "total": len(cases), "passed": passed,
        "failed": len(failures), "accuracy": passed / len(cases) if cases else 0.0,
        "metrics": metrics, "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, default=ROOT / "evals/step4_dev.jsonl")
    parser.add_argument("--test", type=Path)
    args = parser.parse_args()
    output = {"development": evaluate(args.development)}
    if args.test:
        output["test"] = evaluate(args.test)
    print(json.dumps(output, indent=2))
    return 1 if any(item["failed"] for item in output.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
