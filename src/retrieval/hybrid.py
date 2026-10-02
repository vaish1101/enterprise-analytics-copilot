"""Reciprocal-rank fusion for lexical and dense rankings."""

from __future__ import annotations


def reciprocal_rank_fusion(
    rankings: dict[str, list[str]], *, k: int = 60, weights: dict[str, float] | None = None
) -> list[tuple[str, float]]:
    if k <= 0:
        raise ValueError("RRF k must be positive")
    scores: dict[str, float] = {}
    weights = weights or {}
    for method, ranked_ids in rankings.items():
        weight = weights.get(method, 1.0)
        if weight <= 0:
            raise ValueError("RRF weights must be positive")
        for rank, evidence_id in enumerate(ranked_ids, start=1):
            scores[evidence_id] = scores.get(evidence_id, 0.0) + weight / (k + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
