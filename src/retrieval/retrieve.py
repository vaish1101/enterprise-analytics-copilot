"""Governed retrieval orchestration. No calculation or answer synthesis occurs here."""

from __future__ import annotations

import time
import json
from pathlib import Path

from .embeddings import EMBEDDING_MODEL, EmbeddingProvider, SentenceTransformerEmbeddingProvider
from .hybrid import reciprocal_rank_fusion
from .lexical import BM25Index
from .models import (
    EvidenceResult,
    EvidenceUnit,
    RetrievalQuery,
    RetrievalResponse,
    RetrievalStatus,
    RetrievalTrace,
)
from .query import GovernedVocabulary
from .vector_store import InMemoryVectorStore, PgVectorStore


RETRIEVAL_STRATEGY_VERSION = "governed-hybrid-1.0.0"
PGVECTOR_RETRIEVAL_STRATEGY_VERSION = "governed-semantic-dense-1.0.0"
FUSION_STRATEGY_VERSION = "rrf-k60-1.0.0"


def _citation(unit: EvidenceUnit) -> str:
    location = f"slide {unit.printed_page_or_slide}" if "presentation" in unit.source_id else f"page {unit.printed_page_or_slide} (PDF {unit.page_number})"
    detail = f", table: {unit.table_title}" if unit.table_title else ""
    return f"{unit.source_title}, {location}, section: {unit.section}{detail}"


class GovernedRetriever:
    def __init__(self, units: list[EvidenceUnit], *, root: Path | None = None,
                 embedding_provider: EmbeddingProvider | None = None,
                 lexical_weight: float = 1.0, dense_weight: float = 1.0):
        self.units = sorted(units, key=lambda unit: unit.evidence_unit_id)
        self.unit_by_id = {unit.evidence_unit_id: unit for unit in self.units}
        self.lexical = BM25Index(self.units)
        self.vector = InMemoryVectorStore(self.units, embedding_provider)
        self.vocabulary = GovernedVocabulary(root or Path(__file__).resolve().parents[2])
        if lexical_weight <= 0 or dense_weight <= 0:
            raise ValueError("fusion weights must be positive")
        self.fusion_weights = {"lexical": lexical_weight, "dense": dense_weight}

    @staticmethod
    def _is_unsupported_split(query: RetrievalQuery) -> bool:
        question = query.raw_question.lower()
        if query.company_id != "mercedes_benz_group":
            return False
        asks_price = "price" in question or "pricing" in question
        asks_split = any(term in question for term in (
            "separate", "separately", "due to", "contribution", "isolate", "isolation", "solely", "alone"
        ))
        preserves_combined = "volume / structure / net pricing" in question or "combined volume structure" in question
        return asks_price and asks_split and not preserves_combined

    def _filter(self, query: RetrievalQuery) -> list[EvidenceUnit]:
        candidates: list[EvidenceUnit] = []
        for unit in self.units:
            if unit.company_id != query.company_id:
                continue
            if query.reporting_periods and not set(query.reporting_periods).issubset(unit.reporting_periods):
                continue
            if query.business_scopes and not set(query.business_scopes).intersection(unit.business_scopes):
                continue
            if query.metric_ids and not set(query.metric_ids).intersection(unit.metric_ids):
                continue
            candidates.append(unit)
        return candidates

    def retrieve(self, query: RetrievalQuery, *, method: str = "hybrid") -> RetrievalResponse:
        started = time.perf_counter()
        if method not in {"lexical", "dense", "hybrid"}:
            raise ValueError("method must be lexical, dense, or hybrid")
        expanded_terms = self.vocabulary.expand(query.company_id, query.metric_ids)
        search_text = " ".join((query.raw_question, *expanded_terms))
        candidates = [] if self._is_unsupported_split(query) else self._filter(query)
        allowed = {unit.evidence_unit_id for unit in candidates}

        lexical_all = self.lexical.rank(search_text)
        lexical_ranked = [(self.units[index], score) for index, score in lexical_all if self.units[index].evidence_unit_id in allowed]
        dense_ranked = self.vector.rank(search_text, allowed)
        lexical_ids = [unit.evidence_unit_id for unit, _ in lexical_ranked]
        dense_ids = [unit.evidence_unit_id for unit, _ in dense_ranked]
        lexical_rank = {eid: rank for rank, eid in enumerate(lexical_ids, start=1)}
        dense_rank = {eid: rank for rank, eid in enumerate(dense_ids, start=1)}
        lexical_score = {unit.evidence_unit_id: score for unit, score in lexical_ranked}
        dense_score = {unit.evidence_unit_id: score for unit, score in dense_ranked}

        if method == "lexical":
            fused = [(eid, lexical_score[eid]) for eid in lexical_ids]
        elif method == "dense":
            fused = [(eid, dense_score[eid]) for eid in dense_ids]
        else:
            fused = reciprocal_rank_fusion(
                {"lexical": lexical_ids, "dense": dense_ids}, weights=self.fusion_weights
            )

        # Preferred evidence types are a deterministic tie-break boost, never a bypass
        # of company/period/scope/metric filters.
        if query.preferred_evidence_types:
            preferred = set(query.preferred_evidence_types)
            fused = sorted(fused, key=lambda item: (self.unit_by_id[item[0]].evidence_unit_type not in preferred, -item[1], item[0]))

        top = fused[:query.top_k]
        results = tuple(
            EvidenceResult(
                evidence_unit_id=eid,
                source_id=(unit := self.unit_by_id[eid]).source_id,
                company_id=unit.company_id,
                source_title=unit.source_title,
                official_url=unit.official_url,
                page_number=unit.page_number,
                printed_page_or_slide=unit.printed_page_or_slide,
                section=unit.section,
                subsection=unit.subsection,
                table_title=unit.table_title,
                table_headers=unit.table_headers,
                business_scopes=unit.business_scopes,
                reporting_periods=unit.reporting_periods,
                evidence_unit_type=unit.evidence_unit_type,
                evidence_relevance=unit.evidence_relevance,
                source_hierarchy=unit.source_hierarchy,
                evidence_method=unit.evidence_method,
                text=unit.text,
                metric_ids=unit.metric_ids,
                metric_families=unit.metric_families,
                lexical_rank=lexical_rank.get(eid), dense_rank=dense_rank.get(eid),
                fused_rank=rank,
                lexical_score=lexical_score.get(eid), dense_score=dense_score.get(eid),
                fused_score=score, content_hash=unit.content_hash,
                citation=_citation(unit),
            )
            for rank, (eid, score) in enumerate(top, start=1)
        )
        elapsed = (time.perf_counter() - started) * 1000
        trace = RetrievalTrace(
            query=query.raw_question,
            plan_derived_filters={
                "company_id": query.company_id,
                "reporting_periods": query.reporting_periods,
                "business_scopes": query.business_scopes,
                "metric_ids": query.metric_ids,
            },
            expanded_terms=expanded_terms,
            retrieval_methods=(method,),
            candidates_before_filtering=len(self.units),
            candidates_after_filtering=len(candidates),
            top_k=query.top_k,
            final_evidence_ids=tuple(result.evidence_unit_id for result in results),
            latency_ms=elapsed,
            parser_version=self.units[0].parser_version if self.units else "unknown",
            chunking_version=self.units[0].chunking_version if self.units else "unknown",
            embedding_model=self.vector.provider.model_name,
            embedding_index_version=self.vector.index_version,
            retrieval_strategy_version=RETRIEVAL_STRATEGY_VERSION,
            fusion_strategy_version=(
                FUSION_STRATEGY_VERSION
                if self.fusion_weights == {"lexical": 1.0, "dense": 1.0}
                else f"weighted-rrf-k60-l{self.fusion_weights['lexical']:g}-d{self.fusion_weights['dense']:g}-1.0.0"
            ),
        )
        if not results:
            reason = "Unsupported separate Mercedes price evidence." if self._is_unsupported_split(query) else "No evidence satisfies all governed metadata filters."
            return RetrievalResponse(status=RetrievalStatus.NO_RELEVANT_EVIDENCE, results=(), trace=trace, reason=reason)
        return RetrievalResponse(status=RetrievalStatus.SUCCESS, results=results, trace=trace)


class PgVectorRetriever:
    """Production dense retriever with governed filters executed inside PostgreSQL."""

    def __init__(self, *, dsn: str, root: Path, embedding_provider: EmbeddingProvider,
                 total_units: int):
        self.embedding_provider = embedding_provider
        self.vocabulary = GovernedVocabulary(root)
        self.store = PgVectorStore(dsn, embedding_model=embedding_provider.model_name)
        self.total_units = total_units

    def retrieve(self, query: RetrievalQuery, *, method: str = "dense") -> RetrievalResponse:
        if method != "dense":
            raise ValueError("pgvector production retriever supports governed dense retrieval only")
        started = time.perf_counter()
        expanded_terms = self.vocabulary.expand(query.company_id, query.metric_ids)
        search_text = " ".join((query.raw_question, *expanded_terms))
        unsupported = GovernedRetriever._is_unsupported_split(query)
        rows = [] if unsupported else self.store.search(
            query_embedding=self.embedding_provider.embed(search_text),
            company_id=query.company_id,
            reporting_periods=query.reporting_periods,
            business_scopes=query.business_scopes,
            metric_ids=query.metric_ids,
            preferred_evidence_types=tuple(item.value for item in query.preferred_evidence_types),
            top_k=query.top_k,
        )
        candidate_count = 0 if unsupported else self.store.candidate_count(
            company_id=query.company_id,
            reporting_periods=query.reporting_periods,
            business_scopes=query.business_scopes,
            metric_ids=query.metric_ids,
        )
        results: list[EvidenceResult] = []
        parser_versions: set[str] = set()
        chunking_versions: set[str] = set()
        for rank, (evidence_id, metadata, score) in enumerate(rows, start=1):
            unit = EvidenceUnit.model_validate_json(json.dumps(metadata))
            if unit.evidence_unit_id != evidence_id:
                raise RuntimeError("pgvector evidence identity mismatch")
            parser_versions.add(unit.parser_version)
            chunking_versions.add(unit.chunking_version)
            results.append(EvidenceResult(
                evidence_unit_id=evidence_id, source_id=unit.source_id, company_id=unit.company_id,
                source_title=unit.source_title, official_url=unit.official_url,
                page_number=unit.page_number, printed_page_or_slide=unit.printed_page_or_slide,
                section=unit.section, subsection=unit.subsection, table_title=unit.table_title,
                table_headers=unit.table_headers, business_scopes=unit.business_scopes,
                reporting_periods=unit.reporting_periods, evidence_unit_type=unit.evidence_unit_type,
                evidence_relevance=unit.evidence_relevance, source_hierarchy=unit.source_hierarchy,
                evidence_method=unit.evidence_method, text=unit.text, metric_ids=unit.metric_ids,
                metric_families=unit.metric_families, lexical_rank=None, dense_rank=rank,
                fused_rank=rank, lexical_score=None, dense_score=score, fused_score=score,
                content_hash=unit.content_hash, citation=_citation(unit),
            ))
        elapsed = (time.perf_counter() - started) * 1000
        trace = RetrievalTrace(
            query=query.raw_question,
            plan_derived_filters={
                "company_id": query.company_id, "reporting_periods": query.reporting_periods,
                "business_scopes": query.business_scopes, "metric_ids": query.metric_ids,
            },
            expanded_terms=expanded_terms, retrieval_methods=("dense",),
            candidates_before_filtering=self.total_units, candidates_after_filtering=candidate_count,
            top_k=query.top_k, final_evidence_ids=tuple(item.evidence_unit_id for item in results),
            latency_ms=elapsed,
            parser_version=",".join(sorted(parser_versions)) or "unknown",
            chunking_version=",".join(sorted(chunking_versions)) or "unknown",
            embedding_model=self.embedding_provider.model_name,
            embedding_index_version=self.store.index_version,
            retrieval_strategy_version=PGVECTOR_RETRIEVAL_STRATEGY_VERSION,
            fusion_strategy_version="none",
        )
        if not results:
            reason = "Unsupported separate Mercedes price evidence." if unsupported else "No evidence satisfies all governed metadata filters."
            return RetrievalResponse(status=RetrievalStatus.NO_RELEVANT_EVIDENCE, results=(), trace=trace, reason=reason)
        return RetrievalResponse(status=RetrievalStatus.SUCCESS, results=tuple(results), trace=trace)


def build_default_retriever(
    units: list[EvidenceUnit], *, root: Path | None = None
) -> GovernedRetriever:
    """Build the Step 5.5 development-selected MiniLM dense retriever.

    Model loading is strictly local. Run the documented one-time download before
    using this factory; retrieval itself never reaches the network.
    """
    project_root = root or Path(__file__).resolve().parents[2]
    provider = SentenceTransformerEmbeddingProvider(
        cache_folder=project_root / "data/retrieval/local/model_cache",
        local_files_only=True,
    )
    return GovernedRetriever(units, root=project_root, embedding_provider=provider)


def build_pgvector_retriever(
    units: list[EvidenceUnit], *, dsn: str, root: Path | None = None
) -> PgVectorRetriever:
    project_root = root or Path(__file__).resolve().parents[2]
    provider = SentenceTransformerEmbeddingProvider(
        cache_folder=project_root / "data/retrieval/local/model_cache",
        local_files_only=True,
    )
    return PgVectorRetriever(
        dsn=dsn, root=project_root, embedding_provider=provider, total_units=len(units),
    )
