"""Compare the validated local dense retriever with production pgvector on dev data."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.retrieval.models import EvidenceUnit, EvidenceUnitType, RetrievalQuery, RetrievalStatus  # noqa: E402
from src.retrieval.retrieve import build_default_retriever, build_pgvector_retriever  # noqa: E402


def _expected(row: dict, response) -> bool:
    if not row["should_retrieve"]:
        return response.status is not RetrievalStatus.SUCCESS
    return bool(response.results) and any(
        result.source_id in row["expected_source_ids"]
        and result.page_number in row["expected_pages"]
        and result.evidence_unit_type.value in row["expected_evidence_types"]
        for result in response.results
    )


def _filters_hold(query: RetrievalQuery, response) -> bool:
    return all(
        result.company_id == query.company_id
        and (not query.reporting_periods or set(query.reporting_periods).issubset(result.reporting_periods))
        and (not query.business_scopes or bool(set(query.business_scopes) & set(result.business_scopes)))
        and (not query.metric_ids or bool(set(query.metric_ids) & set(result.metric_ids)))
        for result in response.results
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required")
    units = [
        EvidenceUnit.model_validate_json(line)
        for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text().splitlines() if line
    ]
    local = build_default_retriever(units, root=ROOT)
    postgres = build_pgvector_retriever(units, dsn=args.database_url, root=ROOT)
    cases = [json.loads(line) for line in (ROOT / "evals/step5_5_semantic_dev.jsonl").read_text().splitlines() if line]
    results = []
    for row in cases:
        query = RetrievalQuery(
            query_id=row["query_id"], raw_question=row["question"], company_id=row["company_id"],
            reporting_periods=tuple(row["reporting_periods"]), business_scopes=tuple(row["business_scopes"]),
            metric_ids=tuple(row["metric_ids"]),
            preferred_evidence_types=tuple(EvidenceUnitType(item) for item in row["expected_evidence_types"]),
            top_k=5,
        )
        left = local.retrieve(query, method="dense")
        right = postgres.retrieve(query, method="dense")
        local_ids = [item.evidence_unit_id for item in left.results]
        pg_ids = [item.evidence_unit_id for item in right.results]
        expected_local = _expected(row, left)
        expected_pg = _expected(row, right)
        filter_equal = _filters_hold(query, left) and _filters_hold(query, right)
        no_duplicates = len(pg_ids) == len(set(pg_ids))
        results.append({
            "query_id": row["query_id"], "question": row["question"],
            "local_ids": local_ids, "pgvector_ids": pg_ids,
            "top1_equal": local_ids[:1] == pg_ids[:1],
            "top3_set_equal": set(local_ids[:3]) == set(pg_ids[:3]),
            "top5_set_equal": set(local_ids[:5]) == set(pg_ids[:5]),
            "expected_local": expected_local, "expected_pgvector": expected_pg,
            "filter_compliance": filter_equal, "no_duplicate_pgvector_ids": no_duplicates,
            "material_regression": expected_local and not expected_pg or not filter_equal or not no_duplicates,
        })
    report = {
        "dataset": "evals/step5_5_semantic_dev.jsonl", "held_dataset_used": False,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "top_k": 5,
        "query_count": len(results),
        "top1_exact_count": sum(item["top1_equal"] for item in results),
        "top3_set_exact_count": sum(item["top3_set_equal"] for item in results),
        "top5_set_exact_count": sum(item["top5_set_equal"] for item in results),
        "expected_local_pass_count": sum(item["expected_local"] for item in results),
        "expected_pgvector_pass_count": sum(item["expected_pgvector"] for item in results),
        "filter_compliance_count": sum(item["filter_compliance"] for item in results),
        "material_regression_count": sum(item["material_regression"] for item in results),
        "passed": not any(item["material_regression"] for item in results),
        "results": results,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
