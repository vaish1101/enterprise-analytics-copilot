from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.planning import QuestionPlanner
from src.retrieval.embeddings import EMBEDDING_DIMENSION, LocalHashEmbeddingProvider
from src.retrieval.hybrid import reciprocal_rank_fusion
from src.retrieval.models import EvidenceUnitType, RetrievalQuery, RetrievalStatus
from src.retrieval.parser import parse_corpus
from src.retrieval.query import GovernedVocabulary, query_from_plan
from src.retrieval.retrieve import GovernedRetriever
from src.retrieval.vector_store import InMemoryVectorStore, PGVECTOR_SCHEMA_SQL


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def units():
    return parse_corpus(ROOT)


@pytest.fixture(scope="module")
def retriever(units):
    return GovernedRetriever(units, root=ROOT)


def query(question, company, periods, scopes, metrics, types=()):
    return RetrievalQuery(query_id="test", raw_question=question, company_id=company, reporting_periods=tuple(periods), business_scopes=tuple(scopes), metric_ids=tuple(metrics), preferred_evidence_types=tuple(types), top_k=5)


def test_cars_filter_cannot_return_vans(retriever):
    response = retriever.retrieve(query("Mercedes Cars revenue Q2 2026", "mercedes_benz_group", ["Q2_2026"], ["mercedes_cars"], ["mercedes_revenue"]))
    assert response.status is RetrievalStatus.SUCCESS
    assert "mercedes_cars" in response.results[0].business_scopes
    assert not (response.results[0].business_scopes == ("mercedes_vans",))


def test_h1_filter_excludes_q2_only_bridge(retriever):
    response = retriever.retrieve(query("Mercedes Cars bridge H1 2026", "mercedes_benz_group", ["H1_2026"], ["mercedes_cars"], ["mercedes_bridge_volume_structure_net_pricing"]))
    assert response.status is RetrievalStatus.NO_RELEVANT_EVIDENCE


def test_henkel_filter_excludes_mercedes(retriever):
    response = retriever.retrieve(query("Henkel organic growth H1 2026", "henkel", ["H1_2026"], ["henkel_group"], ["henkel_organic_sales_growth"]))
    assert response.results and all(result.company_id == "henkel" for result in response.results)


def test_metric_expansion_is_governed_only():
    vocabulary = GovernedVocabulary(ROOT)
    terms = vocabulary.expand("henkel", ("henkel_organic_sales_growth",))
    assert "organic sales growth" in terms
    assert "invented synonym" not in terms


def test_vector_metadata_and_dimension_are_preserved(units):
    store = InMemoryVectorStore(units[:3])
    assert all(len(record.embedding) == EMBEDDING_DIMENSION for record in store.records)
    assert {record.unit.evidence_unit_id for record in store.records} == {unit.evidence_unit_id for unit in units[:3]}


@pytest.mark.parametrize("method", ["lexical", "dense", "hybrid"])
def test_each_retrieval_method_returns_governed_evidence(retriever, method):
    response = retriever.retrieve(query("Henkel Group price contribution H1 2026", "henkel", ["H1_2026"], ["henkel_group"], ["henkel_price_contribution"]), method=method)
    assert response.status is RetrievalStatus.SUCCESS
    assert response.results[0].page_number == 7


def test_rrf_is_correct_and_deterministic():
    fused = reciprocal_rank_fusion({"a": ["x", "y"], "b": ["y", "x"]}, k=60)
    assert fused == sorted(fused, key=lambda item: (-item[1], item[0]))
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)


def test_weighted_rrf_applies_declared_method_weight():
    fused = dict(reciprocal_rank_fusion(
        {"lexical": ["x"], "dense": ["y"]}, k=60,
        weights={"lexical": 1.0, "dense": 2.0},
    ))
    assert fused["y"] == pytest.approx(2 / 61)
    assert fused["x"] == pytest.approx(1 / 61)


def test_no_evidence_behavior(retriever):
    response = retriever.retrieve(query("Mercedes Trucks revenue", "mercedes_benz_group", ["Q2_2026"], ["mercedes_trucks"], ["mercedes_revenue"]))
    assert response.status is RetrievalStatus.NO_RELEVANT_EVIDENCE
    assert response.results == ()


def test_unsupported_mercedes_price_split_fails_closed(retriever):
    response = retriever.retrieve(query("Give a separate Mercedes Cars price contribution", "mercedes_benz_group", ["Q2_2025", "Q2_2026"], ["mercedes_cars"], ["mercedes_bridge_volume_structure_net_pricing"]))
    assert response.status is RetrievalStatus.NO_RELEVANT_EVIDENCE
    assert "price" in response.reason.lower()


def test_combined_source_label_is_preserved(units):
    bridge = next(unit for unit in units if unit.source_id == "mercedes_q2_2026_capital_market_presentation" and unit.page_number == 8 and unit.evidence_unit_type is EvidenceUnitType.BRIDGE_DECOMPOSITION)
    assert "Volume / structure / net pricing" in bridge.text


def test_citation_contract_is_complete_and_not_filename_only(retriever):
    response = retriever.retrieve(query("Mercedes Vans revenue Q2 2026", "mercedes_benz_group", ["Q2_2026"], ["mercedes_vans"], ["mercedes_revenue"]))
    result = response.results[0]
    assert result.source_title in result.citation
    assert result.section in result.citation
    assert ".pdf" not in result.citation.lower()


def test_similarity_is_not_exposed_as_confidence(retriever):
    result = retriever.retrieve(query("Henkel sales H1 2026", "henkel", ["H1_2026"], ["henkel_group"], ["henkel_sales"])).results[0]
    assert "confidence" not in type(result).model_fields


def test_retrieval_performs_no_arithmetic():
    import src.retrieval.retrieve as module
    source = inspect.getsource(module)
    assert "src.analytics" not in source
    assert "percentage_change" not in source


def test_structured_facts_remain_numerical_authority():
    from src.analytics.executor import AnalyticsExecutor
    assert AnalyticsExecutor is not None
    assert not hasattr(GovernedRetriever, "calculate")


def test_plan_derived_query_uses_scope_period_and_metric():
    plan = QuestionPlanner(ROOT).plan("What was Henkel Group organic sales growth in H1 2026?")
    retrieval_query = query_from_plan(plan)
    assert retrieval_query.business_scopes == ("henkel_group",)
    assert retrieval_query.reporting_periods == ("H1_2026",)
    assert retrieval_query.metric_ids == ("henkel_organic_sales_growth",)


def test_pgvector_schema_supports_cosine_and_metadata_filters():
    assert "vector(384)" in PGVECTOR_SCHEMA_SQL
    assert "vector_cosine_ops" in PGVECTOR_SCHEMA_SQL
    assert "company_id" in PGVECTOR_SCHEMA_SQL and "reporting_periods" in PGVECTOR_SCHEMA_SQL


def test_index_rebuild_is_deterministic(units):
    provider = LocalHashEmbeddingProvider()
    first = provider.embed(units[0].text)
    second = provider.embed(units[0].text)
    assert first == second


def test_management_bridge_stays_non_causal(units):
    bridges = [unit for unit in units if unit.evidence_unit_type is EvidenceUnitType.BRIDGE_DECOMPOSITION]
    assert bridges
    assert {unit.evidence_relevance.value for unit in bridges} == {"MANAGEMENT_ATTRIBUTED"}


def test_retrieval_module_has_no_network_dependency():
    import src.retrieval.embeddings as embeddings
    source = inspect.getsource(embeddings)
    assert "requests" not in source and "openai" not in source
