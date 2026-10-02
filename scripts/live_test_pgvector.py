"""Load the local semantic index into real pgvector and verify governed search."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg  # type: ignore[import-not-found]  # noqa: E402
from pgvector.psycopg import register_vector  # type: ignore[import-not-found]  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

from src.retrieval.embeddings import SentenceTransformerEmbeddingProvider  # noqa: E402
from src.retrieval.models import EvidenceUnit  # noqa: E402
from src.retrieval.vector_store import PGVECTOR_SCHEMA_SQL, PgVectorStore  # noqa: E402


CORPUS = ROOT / "data/retrieval/local/evidence_units.jsonl"
INDEX = ROOT / "data/retrieval/local/semantic_vector_index.jsonl"
OUTPUT = ROOT / "data/retrieval/local/pgvector_live_test.json"


def main() -> None:
    dsn = os.environ.get("STEP5_PGVECTOR_DSN", "postgresql://localhost:55432/postgres")
    units = {unit.evidence_unit_id: unit for unit in (
        EvidenceUnit.model_validate_json(line) for line in CORPUS.read_text().splitlines() if line
    )}
    vectors = [json.loads(line) for line in INDEX.read_text().splitlines() if line]
    with psycopg.connect(dsn) as connection:
        connection.execute("DROP TABLE IF EXISTS retrieval_embeddings")
        connection.execute("DROP TABLE IF EXISTS retrieval_evidence_units")
        connection.execute(PGVECTOR_SCHEMA_SQL)
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO retrieval_evidence_units
                (evidence_unit_id, source_id, company_id, reporting_periods, business_scopes, metric_ids, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [(
                    unit.evidence_unit_id, unit.source_id, unit.company_id,
                    list(unit.reporting_periods), list(unit.business_scopes), list(unit.metric_ids),
                    Jsonb({"page_number": unit.page_number, "type": unit.evidence_unit_type.value,
                           "source_title": unit.source_title, "section": unit.section}),
                ) for unit in units.values()],
            )
            cursor.executemany(
                "INSERT INTO retrieval_embeddings (evidence_unit_id, embedding_model, embedding) VALUES (%s, %s, %s)",
                [(row["evidence_unit_id"], row["embedding_model"], row["embedding"]) for row in vectors],
            )
        connection.commit()

    provider = SentenceTransformerEmbeddingProvider(local_files_only=True)
    store = PgVectorStore(dsn, embedding_model=provider.model_name)
    checks = (
        ("underlying growth after currency and acquisitions", "henkel", ("H1_2026",), ("henkel_group",), ("henkel_organic_sales_growth",), 7),
        ("passenger car net pricing and product mix earnings walk", "mercedes_benz_group", ("Q2_2025", "Q2_2026"), ("mercedes_cars",), ("mercedes_bridge_volume_structure_net_pricing",), 8),
        ("finance arm credit quality earnings walk", "mercedes_benz_group", ("Q2_2025", "Q2_2026"), ("mercedes_financial_services",), ("mercedes_bridge_cost_of_credit_risk",), 21),
    )
    results = []
    for question, company, periods, scopes, metrics, expected_page in checks:
        rows = store.search(
            query_embedding=provider.embed(question), company_id=company,
            reporting_periods=periods, business_scopes=scopes, metric_ids=metrics, top_k=3,
        )
        observed_page = rows[0][1]["page_number"] if rows else None
        results.append({
            "query": question, "expected_page": expected_page, "observed_page": observed_page,
            "passed": observed_page == expected_page, "top_similarity": rows[0][2] if rows else None,
        })
    with psycopg.connect(dsn) as connection:
        extension = connection.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
        index_count = connection.execute("SELECT count(*) FROM retrieval_embeddings").fetchone()[0]
        hnsw = connection.execute("SELECT indexname FROM pg_indexes WHERE indexname='retrieval_evidence_embedding_hnsw_idx'").fetchone()
    report = {
        "postgresql_live": True, "pgvector_version": extension,
        "embedding_model": provider.model_name, "indexed_count": index_count,
        "hnsw_index_present": bool(hnsw), "checks": results,
        "all_checks_passed": all(item["passed"] for item in results),
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
