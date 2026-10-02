"""Idempotently synchronize governed evidence and MiniLM embeddings to pgvector."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg  # type: ignore[import-not-found]  # noqa: E402
from pgvector.psycopg import register_vector  # type: ignore[import-not-found]  # noqa: E402
from psycopg.types.json import Jsonb  # type: ignore[import-not-found]  # noqa: E402

from src.retrieval.embeddings import SentenceTransformerEmbeddingProvider  # noqa: E402
from src.retrieval.models import EvidenceUnit  # noqa: E402
from src.retrieval.vector_store import PGVECTOR_SCHEMA_SQL  # noqa: E402
from src.persistence.checkpoint_store import CheckpointStore  # noqa: E402


CORPUS = ROOT / "data/retrieval/local/evidence_units.jsonl"


def _units() -> list[EvidenceUnit]:
    units = [
        EvidenceUnit.model_validate_json(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines() if line
    ]
    if len({unit.evidence_unit_id for unit in units}) != len(units):
        raise RuntimeError("governed corpus contains duplicate evidence IDs")
    return sorted(units, key=lambda unit: unit.evidence_unit_id)


def load(dsn: str) -> dict[str, int | str | float | bool]:
    started = time.perf_counter()
    units = _units()
    provider = SentenceTransformerEmbeddingProvider(
        cache_folder=ROOT / "data/retrieval/local/model_cache", local_files_only=True,
    )
    with psycopg.connect(dsn) as connection:
        connection.execute(PGVECTOR_SCHEMA_SQL)
        register_vector(connection)
        existing = {
            row[0]: (row[1], row[2], row[3], bool(row[4]))
            for row in connection.execute(
                """SELECT e.evidence_unit_id, e.content_hash, e.parser_version, e.chunking_version,
                          EXISTS (SELECT 1 FROM retrieval_embeddings v
                                  WHERE v.evidence_unit_id=e.evidence_unit_id AND v.embedding_model=%s)
                   FROM retrieval_evidence_units e""",
                (provider.model_name,),
            ).fetchall()
        }
        changed = [
            unit for unit in units
            if existing.get(unit.evidence_unit_id) != (
                unit.content_hash, unit.parser_version, unit.chunking_version, True,
            )
        ]
        vectors = provider.embed_many(unit.text for unit in changed) if changed else ()
        with connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO retrieval_evidence_units
                   (evidence_unit_id, source_id, company_id, reporting_periods, business_scopes,
                    metric_ids, content_hash, parser_version, chunking_version, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (evidence_unit_id) DO UPDATE SET
                     source_id=EXCLUDED.source_id, company_id=EXCLUDED.company_id,
                     reporting_periods=EXCLUDED.reporting_periods,
                     business_scopes=EXCLUDED.business_scopes, metric_ids=EXCLUDED.metric_ids,
                     content_hash=EXCLUDED.content_hash, parser_version=EXCLUDED.parser_version,
                     chunking_version=EXCLUDED.chunking_version, metadata=EXCLUDED.metadata""",
                [(
                    unit.evidence_unit_id, unit.source_id, unit.company_id,
                    list(unit.reporting_periods), list(unit.business_scopes), list(unit.metric_ids),
                    unit.content_hash, unit.parser_version, unit.chunking_version,
                    Jsonb(unit.model_dump(mode="json")),
                ) for unit in units],
            )
            cursor.executemany(
                """INSERT INTO retrieval_embeddings (evidence_unit_id, embedding_model, embedding)
                   VALUES (%s,%s,%s)
                   ON CONFLICT (evidence_unit_id, embedding_model) DO UPDATE
                   SET embedding=EXCLUDED.embedding""",
                [
                    (unit.evidence_unit_id, provider.model_name, list(vector))
                    for unit, vector in zip(changed, vectors, strict=True)
                ],
            )
            ids = [unit.evidence_unit_id for unit in units]
            cursor.execute("DELETE FROM retrieval_embeddings WHERE NOT (evidence_unit_id = ANY(%s))", (ids,))
            cursor.execute("DELETE FROM retrieval_evidence_units WHERE NOT (evidence_unit_id = ANY(%s))", (ids,))
        connection.commit()
        evidence_count = int(connection.execute("SELECT count(*) FROM retrieval_evidence_units").fetchone()[0])
        embedding_count = int(connection.execute(
            "SELECT count(*) FROM retrieval_embeddings WHERE embedding_model=%s", (provider.model_name,),
        ).fetchone()[0])
        duplicate_count = int(connection.execute(
            "SELECT count(*) FROM (SELECT evidence_unit_id FROM retrieval_evidence_units GROUP BY 1 HAVING count(*)>1) d"
        ).fetchone()[0])
    checkpoint = CheckpointStore(mode="postgres", uri=dsn)
    checkpoint.close()
    return {
        "success": evidence_count == len(units) == embedding_count and duplicate_count == 0,
        "embedding_model": provider.model_name, "source_count": len(units),
        "changed_or_missing_count": len(changed), "evidence_count": evidence_count,
        "embedding_count": embedding_count, "duplicate_count": duplicate_count,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required")
    report = load(args.database_url)
    print(json.dumps(report, sort_keys=True))
    if not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
