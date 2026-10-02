"""Vector storage contracts, local evaluator, and pgvector DDL."""

from __future__ import annotations

from dataclasses import dataclass

from .embeddings import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    EmbeddingProvider,
    LocalHashEmbeddingProvider,
    cosine_similarity,
)
from .models import EvidenceUnit


PGVECTOR_SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS retrieval_evidence_units (
  evidence_unit_id text PRIMARY KEY,
  source_id text NOT NULL,
  company_id text NOT NULL,
  reporting_periods text[] NOT NULL,
  business_scopes text[] NOT NULL,
  metric_ids text[] NOT NULL,
  content_hash text NOT NULL,
  parser_version text NOT NULL,
  chunking_version text NOT NULL,
  metadata jsonb NOT NULL
);
ALTER TABLE retrieval_evidence_units ADD COLUMN IF NOT EXISTS content_hash text;
ALTER TABLE retrieval_evidence_units ADD COLUMN IF NOT EXISTS parser_version text;
ALTER TABLE retrieval_evidence_units ADD COLUMN IF NOT EXISTS chunking_version text;
CREATE TABLE IF NOT EXISTS retrieval_embeddings (
  evidence_unit_id text NOT NULL REFERENCES retrieval_evidence_units(evidence_unit_id),
  embedding_model text NOT NULL,
  embedding vector({EMBEDDING_DIMENSION}) NOT NULL
  ,PRIMARY KEY (evidence_unit_id, embedding_model)
);
CREATE INDEX IF NOT EXISTS retrieval_evidence_metadata_idx
  ON retrieval_evidence_units (company_id, source_id);
CREATE INDEX IF NOT EXISTS retrieval_evidence_periods_idx
  ON retrieval_evidence_units USING gin (reporting_periods);
CREATE INDEX IF NOT EXISTS retrieval_evidence_scopes_idx
  ON retrieval_evidence_units USING gin (business_scopes);
CREATE INDEX IF NOT EXISTS retrieval_evidence_metrics_idx
  ON retrieval_evidence_units USING gin (metric_ids);
CREATE INDEX IF NOT EXISTS retrieval_evidence_embedding_hnsw_idx
  ON retrieval_embeddings USING hnsw (embedding vector_cosine_ops);
""".strip()

PGVECTOR_SEARCH_SQL = """
SELECT e.evidence_unit_id, e.metadata, 1 - (v.embedding <=> %(query_embedding)s::vector) AS cosine_similarity
FROM retrieval_evidence_units AS e
JOIN retrieval_embeddings AS v USING (evidence_unit_id)
WHERE e.company_id = %(company_id)s
  AND (cardinality(%(reporting_periods)s::text[]) = 0 OR e.reporting_periods @> %(reporting_periods)s::text[])
  AND (cardinality(%(business_scopes)s::text[]) = 0 OR e.business_scopes && %(business_scopes)s::text[])
  AND (cardinality(%(metric_ids)s::text[]) = 0 OR e.metric_ids && %(metric_ids)s::text[])
  AND v.embedding_model = %(embedding_model)s
ORDER BY
  CASE WHEN cardinality(%(preferred_evidence_types)s::text[]) > 0
         AND e.metadata->>'evidence_unit_type' = ANY(%(preferred_evidence_types)s::text[])
       THEN 0 ELSE 1 END,
  v.embedding <=> %(query_embedding)s::vector,
  e.evidence_unit_id
LIMIT %(top_k)s
""".strip()

PGVECTOR_COUNT_SQL = """
SELECT count(*)
FROM retrieval_evidence_units AS e
JOIN retrieval_embeddings AS v USING (evidence_unit_id)
WHERE e.company_id = %(company_id)s
  AND (cardinality(%(reporting_periods)s::text[]) = 0 OR e.reporting_periods @> %(reporting_periods)s::text[])
  AND (cardinality(%(business_scopes)s::text[]) = 0 OR e.business_scopes && %(business_scopes)s::text[])
  AND (cardinality(%(metric_ids)s::text[]) = 0 OR e.metric_ids && %(metric_ids)s::text[])
  AND v.embedding_model = %(embedding_model)s
""".strip()


@dataclass(frozen=True)
class VectorRecord:
    unit: EvidenceUnit
    embedding: tuple[float, ...]


class InMemoryVectorStore:
    """Deterministic test/evaluation store with pgvector-equivalent cosine ranking."""

    index_version = "local-cosine-flat-1.0.0"

    def __init__(self, units: list[EvidenceUnit], provider: EmbeddingProvider | None = None):
        self.provider = provider or LocalHashEmbeddingProvider()
        ordered = sorted(units, key=lambda unit: unit.evidence_unit_id)
        embeddings = self.provider.embed_many(unit.text for unit in ordered)
        self.records = tuple(VectorRecord(unit, embedding) for unit, embedding in zip(ordered, embeddings, strict=True))

    def rank(self, query: str, allowed_ids: set[str] | None = None) -> list[tuple[EvidenceUnit, float]]:
        query_embedding = self.provider.embed(query)
        records = self.records if allowed_ids is None else tuple(record for record in self.records if record.unit.evidence_unit_id in allowed_ids)
        return sorted(
            ((record.unit, cosine_similarity(query_embedding, record.embedding)) for record in records),
            key=lambda item: (-item[1], item[0].evidence_unit_id),
        )


class PgVectorStore:
    """Production adapter; psycopg is optional and imported only on connection."""

    index_version = "pgvector-hnsw-cosine-1.0.0"

    def __init__(self, dsn: str, *, embedding_model: str = EMBEDDING_MODEL):
        self.dsn = dsn
        self.embedding_model = embedding_model

    def search(self, *, query_embedding: tuple[float, ...], company_id: str,
               reporting_periods: tuple[str, ...], business_scopes: tuple[str, ...],
               metric_ids: tuple[str, ...], preferred_evidence_types: tuple[str, ...] = (),
               top_k: int = 5) -> list[tuple[str, dict, float]]:
        try:
            import psycopg  # type: ignore[import-not-found]
            from pgvector.psycopg import register_vector  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("Install the optional psycopg and pgvector packages to use PostgreSQL") from exc
        params = {
            "query_embedding": list(query_embedding), "company_id": company_id,
            "reporting_periods": list(reporting_periods), "business_scopes": list(business_scopes),
            "metric_ids": list(metric_ids), "preferred_evidence_types": list(preferred_evidence_types),
            "embedding_model": self.embedding_model, "top_k": top_k,
        }
        with psycopg.connect(self.dsn) as connection:
            register_vector(connection)
            with connection.cursor() as cursor:
                cursor.execute(PGVECTOR_SEARCH_SQL, params)
                return [(row[0], row[1], float(row[2])) for row in cursor.fetchall()]

    def candidate_count(self, *, company_id: str, reporting_periods: tuple[str, ...],
                        business_scopes: tuple[str, ...], metric_ids: tuple[str, ...]) -> int:
        import psycopg  # type: ignore[import-not-found]
        params = {
            "company_id": company_id, "reporting_periods": list(reporting_periods),
            "business_scopes": list(business_scopes), "metric_ids": list(metric_ids),
            "embedding_model": self.embedding_model,
        }
        with psycopg.connect(self.dsn) as connection:
            return int(connection.execute(PGVECTOR_COUNT_SQL, params).fetchone()[0])

    def readiness(self) -> dict[str, int | str | bool]:
        import psycopg  # type: ignore[import-not-found]
        with psycopg.connect(self.dsn, connect_timeout=2) as connection:
            row = connection.execute(
                """SELECT current_setting('server_version'),
                          (SELECT extversion FROM pg_extension WHERE extname='vector'),
                          (SELECT count(*) FROM retrieval_evidence_units),
                          (SELECT count(*) FROM retrieval_embeddings WHERE embedding_model=%s),
                          EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='retrieval_evidence_embedding_hnsw_idx')""",
                (self.embedding_model,),
            ).fetchone()
        return {
            "postgres_version": str(row[0]), "pgvector_version": str(row[1] or ""),
            "evidence_count": int(row[2]), "embedding_count": int(row[3]),
            "hnsw_present": bool(row[4]),
        }
