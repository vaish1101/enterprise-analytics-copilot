"""Dependency-free BM25 lexical retrieval."""

from __future__ import annotations

import math
import re
from collections import Counter

from .models import EvidenceUnit


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", text.lower()))


class BM25Index:
    def __init__(self, units: list[EvidenceUnit], *, k1: float = 1.5, b: float = 0.75):
        self.units = units
        self.k1 = k1
        self.b = b
        self.documents = [tokenize(unit.text) for unit in units]
        self.lengths = [len(document) for document in self.documents]
        self.avg_length = sum(self.lengths) / max(1, len(self.lengths))
        self.term_frequencies = [Counter(document) for document in self.documents]
        self.document_frequency: Counter[str] = Counter()
        for document in self.documents:
            self.document_frequency.update(set(document))

    def score(self, query: str) -> list[float]:
        query_terms = tokenize(query)
        count = len(self.documents)
        scores: list[float] = []
        for index, frequencies in enumerate(self.term_frequencies):
            score = 0.0
            for term in query_terms:
                frequency = frequencies[term]
                if not frequency:
                    continue
                document_frequency = self.document_frequency[term]
                inverse_frequency = math.log(1 + (count - document_frequency + 0.5) / (document_frequency + 0.5))
                denominator = frequency + self.k1 * (1 - self.b + self.b * self.lengths[index] / max(1, self.avg_length))
                score += inverse_frequency * frequency * (self.k1 + 1) / denominator
            scores.append(score)
        return scores

    def rank(self, query: str) -> list[tuple[int, float]]:
        return sorted(enumerate(self.score(query)), key=lambda item: (-item[1], self.units[item[0]].evidence_unit_id))
