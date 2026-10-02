from __future__ import annotations

import math

import pytest


sentence_transformers = pytest.importorskip("sentence_transformers")

from src.retrieval.embeddings import (  # noqa: E402
    EMBEDDING_DIMENSION,
    SEMANTIC_EMBEDDING_MODEL,
    SentenceTransformerEmbeddingProvider,
    cosine_similarity,
)


@pytest.fixture(scope="module")
def provider():
    return SentenceTransformerEmbeddingProvider(local_files_only=True)


def test_minilm_is_a_real_384_dimension_normalized_embedding(provider):
    vector = provider.embed("underlying sales momentum")
    assert provider.model_name == SEMANTIC_EMBEDDING_MODEL
    assert len(vector) == EMBEDDING_DIMENSION
    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0, abs=1e-5)


def test_minilm_semantics_beat_unrelated_text(provider):
    query = provider.embed("underlying sales momentum excluding currency effects")
    related = provider.embed("organic sales growth adjusted for foreign exchange")
    unrelated = provider.embed("database connection pooling and server sockets")
    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)
