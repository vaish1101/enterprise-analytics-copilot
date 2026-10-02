"""Build a deterministic ignored local vector index and emit pgvector DDL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.retrieval.embeddings import (  # noqa: E402
    EMBEDDING_DIMENSION,
    LocalHashEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
)
from src.retrieval.models import EvidenceUnit
from src.retrieval.vector_store import PGVECTOR_SCHEMA_SQL


CORPUS = ROOT / "data/retrieval/local/evidence_units.jsonl"
DDL = ROOT / "data/retrieval/local/pgvector_schema.sql"


def build(provider_name: str = "semantic") -> dict[str, object]:
    units = [EvidenceUnit.model_validate_json(line) for line in CORPUS.read_text().splitlines() if line]
    provider = (
        SentenceTransformerEmbeddingProvider(local_files_only=True)
        if provider_name == "semantic" else LocalHashEmbeddingProvider()
    )
    index_path = ROOT / f"data/retrieval/local/{provider_name}_vector_index.jsonl"
    ordered = sorted(units, key=lambda unit: unit.evidence_unit_id)
    embeddings = provider.embed_many(unit.text for unit in ordered)
    with index_path.open("w", encoding="utf-8") as handle:
        for unit, embedding in zip(ordered, embeddings, strict=True):
            handle.write(json.dumps({
                "evidence_unit_id": unit.evidence_unit_id,
                "embedding_model": provider.model_name,
                "content_hash": unit.content_hash,
                "embedding": embedding,
                "metadata": {
                    "company_id": unit.company_id,
                    "source_id": unit.source_id,
                    "reporting_periods": unit.reporting_periods,
                    "business_scopes": unit.business_scopes,
                    "metric_ids": unit.metric_ids,
                },
            }, separators=(",", ":")) + "\n")
    DDL.write_text(PGVECTOR_SCHEMA_SQL + "\n", encoding="utf-8")
    return {
        "model": provider.model_name, "dimension": EMBEDDING_DIMENSION,
        "indexed_count": len(ordered), "index_path": str(index_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("semantic", "hashing"), default="semantic")
    args = parser.parse_args()
    print(json.dumps(build(args.provider), indent=2, sort_keys=True))
