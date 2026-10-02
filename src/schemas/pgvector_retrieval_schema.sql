-- Step 5 pgvector production schema. Tests use the network-free local store.
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
    embedding vector(384) NOT NULL,
    PRIMARY KEY (evidence_unit_id, embedding_model)
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

-- Filter metadata, join its vector, then rank:
-- SELECT e.*, 1 - (v.embedding <=> $5) AS cosine_similarity
-- FROM retrieval_evidence_units e JOIN retrieval_embeddings v USING (evidence_unit_id)
-- WHERE e.company_id = $1 AND e.reporting_periods @> $2
-- AND e.business_scopes && $3 AND e.metric_ids && $4
-- ORDER BY v.embedding <=> $5 LIMIT $6.
