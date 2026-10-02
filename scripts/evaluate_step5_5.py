"""Step 5.5 semantic hardening benchmark; development data only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_step5 import evaluate, load_cases, load_units  # noqa: E402
from src.retrieval.embeddings import (  # noqa: E402
    LocalHashEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
)
from src.retrieval.retrieve import GovernedRetriever  # noqa: E402


OUTPUT = ROOT / "data/retrieval/local/step5_5_dev_results.json"
SEMANTIC_INDEX = ROOT / "data/retrieval/local/semantic_vector_index.jsonl"


def _evaluate_suite(units, cases, hash_retriever, semantic_retriever, weighted_semantic_retriever):
    specifications = (
        ("bm25_lexical", hash_retriever, "lexical"),
        ("hashing_dense", hash_retriever, "dense"),
        ("semantic_minilm_dense", semantic_retriever, "dense"),
        ("hybrid_hashing", hash_retriever, "hybrid"),
        ("hybrid_minilm", semantic_retriever, "hybrid"),
        ("hybrid_minilm_weighted_1_2", weighted_semantic_retriever, "hybrid"),
    )
    report = {}
    failures = {}
    for label, retriever, method in specifications:
        metrics, method_failures = evaluate(units, cases, method, retriever=retriever)
        report[label] = metrics
        failures[label] = method_failures
    return report, failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--held", action="store_true")
    args = parser.parse_args()
    units = load_units()
    semantic_provider = SentenceTransformerEmbeddingProvider(local_files_only=True)
    semantic_retriever = GovernedRetriever(units, root=ROOT, embedding_provider=semantic_provider)

    if args.held:
        held_cases = load_cases(ROOT / "evals/step5_5_semantic_test.jsonl")
        metrics, failures = evaluate(units, held_cases, "dense", retriever=semantic_retriever)
        result = {
            "evaluation_version": "step5.5-semantic-held-1.0.0",
            "model": semantic_provider.model_name,
            "dimension": semantic_provider.dimension,
            "query_count": len(held_cases),
            "metrics": metrics,
            "failures": failures,
        }
        output = ROOT / "data/retrieval/local/step5_5_test_results.json"
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    base_cases = load_cases(ROOT / "evals/step5_dev.jsonl")
    stress_cases = load_cases(ROOT / "evals/step5_5_semantic_dev.jsonl")
    hash_retriever = GovernedRetriever(units, root=ROOT, embedding_provider=LocalHashEmbeddingProvider())
    weighted_semantic_retriever = GovernedRetriever(
        units, root=ROOT, embedding_provider=semantic_provider,
        lexical_weight=1.0, dense_weight=2.0,
    )

    with SEMANTIC_INDEX.open("w", encoding="utf-8") as handle:
        for record in semantic_retriever.vector.records:
            handle.write(json.dumps({
                "evidence_unit_id": record.unit.evidence_unit_id,
                "embedding_model": semantic_provider.model_name,
                "embedding": record.embedding,
            }, separators=(",", ":")) + "\n")

    result = {
        "evaluation_version": "step5.5-semantic-dev-1.0.0",
        "model": semantic_provider.model_name,
        "dimension": semantic_provider.dimension,
        "base_development": {},
        "semantic_stress_development": {},
        "combined_development": {},
        "failures": {},
        "held_set_executed": False,
    }
    for key, cases in (
        ("base_development", base_cases),
        ("semantic_stress_development", stress_cases),
        ("combined_development", base_cases + stress_cases),
    ):
        metrics, failures = _evaluate_suite(
            units, cases, hash_retriever, semantic_retriever, weighted_semantic_retriever
        )
        result[key] = metrics
        result["failures"][key] = failures
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
