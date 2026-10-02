"""Deterministic Step 5 retrieval and chunking evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.retrieval.chunking import naive_fixed_chunks
from src.retrieval.models import EvidenceUnit, EvidenceUnitType, RetrievalQuery, RetrievalStatus
from src.retrieval.retrieve import GovernedRetriever


CORPUS = ROOT / "data/retrieval/local/evidence_units.jsonl"


def load_units() -> list[EvidenceUnit]:
    return [EvidenceUnit.model_validate_json(line) for line in CORPUS.read_text().splitlines() if line]


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _matches(result, case: dict) -> bool:
    return (
        result.source_id in case["expected_source_ids"]
        and result.page_number in case["expected_pages"]
        and result.evidence_unit_type.value in case["expected_evidence_types"]
    )


def evaluate(units: list[EvidenceUnit], cases: list[dict], method: str, *,
             retriever: GovernedRetriever | None = None) -> tuple[dict[str, float | int], list[dict]]:
    retriever = retriever or GovernedRetriever(units, root=ROOT)
    hits = {1: 0, 3: 0, 5: 0}
    reciprocal_ranks: list[float] = []
    source_correct = page_correct = scope_correct = period_correct = 0
    retrieval_cases = 0
    expected_no = predicted_no = correct_no = 0
    hard_total = hard_errors = 0
    citation_complete = citation_total = 0
    citation_relevant = citation_retrieved = 0
    failures: list[dict] = []
    for case in cases:
        query = RetrievalQuery(
            query_id=case["query_id"], raw_question=case["question"], company_id=case["company_id"],
            reporting_periods=tuple(case["reporting_periods"]), business_scopes=tuple(case["business_scopes"]),
            metric_ids=tuple(case["metric_ids"]),
            preferred_evidence_types=tuple(EvidenceUnitType(value) for value in case["expected_evidence_types"]), top_k=5,
        )
        response = retriever.retrieve(query, method=method)
        no_evidence = response.status is RetrievalStatus.NO_RELEVANT_EVIDENCE
        if not case["should_retrieve"]:
            expected_no += 1
            if no_evidence:
                correct_no += 1
        if no_evidence:
            predicted_no += 1
        if case["hard_negative"]:
            hard_total += 1
        if case["should_retrieve"]:
            retrieval_cases += 1
            matching_ranks = [index for index, result in enumerate(response.results, start=1) if _matches(result, case)]
            rank = min(matching_ranks) if matching_ranks else None
            for k in hits:
                hits[k] += int(rank is not None and rank <= k)
            reciprocal_ranks.append(1 / rank if rank else 0.0)
            if response.results:
                top = response.results[0]
                source_correct += int(top.source_id in case["expected_source_ids"])
                page_correct += int(top.page_number in case["expected_pages"])
                scope_correct += int(not case["business_scopes"] or bool(set(case["business_scopes"]) & set(top.business_scopes)))
                period_correct += int(not case["reporting_periods"] or set(case["reporting_periods"]).issubset(top.reporting_periods))
            if rank is None:
                failures.append({"query_id": case["query_id"], "query": case["question"], "expected_pages": case["expected_pages"], "retrieved": [(r.source_id, r.page_number, r.evidence_unit_type.value) for r in response.results]})
            if case["hard_negative"] and (rank is None or rank > 1):
                hard_errors += 1
        elif case["hard_negative"] and not no_evidence:
            hard_errors += 1
        for result in response.results:
            citation_total += 1
            citation_complete += int(all((result.source_title, result.official_url, result.printed_page_or_slide, result.section, result.content_hash, result.citation)))
            if case["should_retrieve"]:
                citation_retrieved += 1
                citation_relevant += int(_matches(result, case))
    denominator = max(1, retrieval_cases)
    metrics = {
        "query_count": len(cases),
        "retrieval_query_count": retrieval_cases,
        "hit_at_1": round(hits[1] / denominator, 4),
        "hit_at_3": round(hits[3] / denominator, 4),
        "hit_at_5": round(hits[5] / denominator, 4),
        "recall_at_5": round(hits[5] / denominator, 4),
        "mrr": round(sum(reciprocal_ranks) / denominator, 4),
        "source_accuracy": round(source_correct / denominator, 4),
        "page_accuracy": round(page_correct / denominator, 4),
        "scope_filter_accuracy": round(scope_correct / denominator, 4),
        "period_filter_accuracy": round(period_correct / denominator, 4),
        "no_evidence_precision": round(correct_no / max(1, predicted_no), 4),
        "no_evidence_recall": round(correct_no / max(1, expected_no), 4),
        "hard_negative_error_rate": round(hard_errors / max(1, hard_total), 4),
        "citation_completeness": round(citation_complete / max(1, citation_total), 4),
        "citation_precision": round(citation_relevant / max(1, citation_retrieved), 4),
    }
    return metrics, failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--output")
    args = parser.parse_args()
    cases = load_cases(ROOT / f"evals/step5_{args.split}.jsonl")
    units = load_units()
    report: dict[str, object] = {"split": args.split, "evaluation_version": "step5-eval-1.0.0", "methods": {}}
    if args.split == "dev":
        naive = naive_fixed_chunks(units)
        report["chunking"] = {
            "naive_fixed_180": evaluate(naive, cases, "hybrid")[0],
            "structure_aware": evaluate(units, cases, "hybrid")[0],
        }
        methods = ("lexical", "dense", "hybrid")
    else:
        methods = ("hybrid",)
    all_failures = {}
    for method in methods:
        metrics, failures = evaluate(units, cases, method)
        report["methods"][method] = metrics
        all_failures[method] = failures
    report["failures"] = all_failures
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
