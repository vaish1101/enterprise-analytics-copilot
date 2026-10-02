"""Network-free deterministic dense embeddings.

This provider is intentionally small and reproducible. It uses governed text
normalization and signed feature hashing over word and character n-grams. The
provider interface can be replaced by a locally hosted SentenceTransformer
without changing evidence or retrieval contracts.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol


EMBEDDING_MODEL = "governed-hashing-word-char-v1"
EMBEDDING_DIMENSION = 384
SEMANTIC_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    def embed(self, text: str) -> tuple[float, ...]: ...
    def embed_many(self, texts: Iterable[str]) -> tuple[tuple[float, ...], ...]: ...


def _features(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    features = [f"w:{word}" for word in words]
    features.extend(f"b:{a}_{b}" for a, b in zip(words, words[1:]))
    compact = " ".join(words)
    features.extend(f"c:{compact[i:i+4]}" for i in range(max(0, len(compact) - 3)))
    return features


class LocalHashEmbeddingProvider:
    model_name = EMBEDDING_MODEL
    dimension = EMBEDDING_DIMENSION

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimension
        for feature in _features(text):
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return tuple(vector)

    def embed_many(self, texts: Iterable[str]) -> tuple[tuple[float, ...], ...]:
        return tuple(self.embed(text) for text in texts)


class SentenceTransformerEmbeddingProvider:
    """Lazy optional provider backed by a real pretrained semantic encoder."""

    model_name = SEMANTIC_EMBEDDING_MODEL
    dimension = EMBEDDING_DIMENSION

    def __init__(self, *, cache_folder: Path | str | None = None, local_files_only: bool = True):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "SentenceTransformer support is optional; install requirements-step5-semantic.txt"
            ) from exc
        if cache_folder is None:
            project_cache = Path(__file__).resolve().parents[2] / "data/retrieval/local/model_cache"
            cache_folder = project_cache if project_cache.exists() else None
        self._model = SentenceTransformer(
            self.model_name,
            cache_folder=str(cache_folder) if cache_folder else None,
            local_files_only=local_files_only,
        )
        dimension = self._model.get_embedding_dimension()
        if dimension != self.dimension:
            raise ValueError(f"expected {self.dimension} dimensions, model returned {dimension}")

    def embed(self, text: str) -> tuple[float, ...]:
        return self.embed_many((text,))[0]

    def embed_many(self, texts: Iterable[str]) -> tuple[tuple[float, ...], ...]:
        values = self._model.encode(
            list(texts), batch_size=64, normalize_embeddings=True,
            show_progress_bar=False, convert_to_numpy=True,
        )
        return tuple(tuple(float(value) for value in row) for row in values)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions differ")
    return sum(a * b for a, b in zip(left, right))
