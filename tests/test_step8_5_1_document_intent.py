from pathlib import Path

import pytest

from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.orchestration.models import WorkflowRoute, WorkflowStatus
from src.planning import QuestionPlanner
from src.planning.models import PlanOperation, PlanningStatus, QuestionType
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import GovernedRetriever
from src.schemas.models import EvidenceType


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def planner() -> QuestionPlanner:
    return QuestionPlanner(ROOT)


@pytest.fixture(scope="module")
def graph() -> EnterpriseAnalyticsGraph:
    return EnterpriseAnalyticsGraph(ROOT)


DOCUMENT_CASES = (
    (
        "What did management say about Mercedes-Benz Mobility EBIT in Q2 2026?",
        QuestionType.DOCUMENT_CONTEXT, WorkflowRoute.KNOWLEDGE_ONLY, False,
    ),
    (
        "What did management report about Mercedes-Benz Mobility EBIT in Q2 2026?",
        QuestionType.DOCUMENT_CONTEXT, WorkflowRoute.KNOWLEDGE_ONLY, False,
    ),
    (
        "How did management explain the change in Mercedes-Benz Group adjusted EBIT from Q2 2025 to Q2 2026?",
        QuestionType.DOCUMENT_CONTEXT, WorkflowRoute.KNOWLEDGE_ONLY, False,
    ),
    (
        "What is management's outlook for Henkel organic sales growth in H1 2026?",
        QuestionType.DOCUMENT_CONTEXT, WorkflowRoute.KNOWLEDGE_ONLY, False,
    ),
    (
        "What is the outlook for Henkel organic sales growth in H1 2026?",
        QuestionType.DOCUMENT_CONTEXT, WorkflowRoute.KNOWLEDGE_ONLY, False,
    ),
    (
        "According to the report, what does management say about Henkel organic sales growth in H1 2026?",
        QuestionType.DOCUMENT_CONTEXT, WorkflowRoute.KNOWLEDGE_ONLY, False,
    ),
    (
        "What commentary did management provide about Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
        QuestionType.DOCUMENT_CONTEXT, WorkflowRoute.KNOWLEDGE_ONLY, False,
    ),
    (
        "What guidance was reported for Henkel organic sales growth in H1 2026?",
        QuestionType.DOCUMENT_CONTEXT, WorkflowRoute.KNOWLEDGE_ONLY, False,
    ),
    (
        "According to management, what was Mercedes-Benz Mobility EBIT in Q2 2026?",
        QuestionType.HYBRID_ANALYSIS, WorkflowRoute.HYBRID, True,
    ),
)


@pytest.mark.parametrize("question,question_type,route,analytics_required", DOCUMENT_CASES)
def test_document_intent_routes_with_required_evidence(
    planner: QuestionPlanner,
    graph: EnterpriseAnalyticsGraph,
    question: str,
    question_type: QuestionType,
    route: WorkflowRoute,
    analytics_required: bool,
):
    plan = planner.plan(question)
    assert plan.planner_version == "3.0.1"
    assert plan.status is PlanningStatus.READY
    assert plan.question_type is question_type
    assert EnterpriseAnalyticsGraph._route(plan) is route
    assert plan.requires_documents is True
    assert EvidenceType.PRIMARY_NUMERIC in plan.required_evidence_types

    result = graph.run(question)
    nodes = {event.node for event in result.trace}
    assert result.status is WorkflowStatus.COMPLETED
    assert result.route is route
    assert ("analytics_agent" in nodes) is analytics_required
    assert "knowledge_agent" in nodes
    assert result.citations


def test_numeric_document_question_keeps_analytics_as_numeric_authority(graph: EnterpriseAnalyticsGraph):
    result = graph.run("According to management, what was Mercedes-Benz Mobility EBIT in Q2 2026?")
    numeric = [claim for claim in result.claims if claim.value is not None]
    assert result.route is WorkflowRoute.HYBRID
    assert numeric
    assert all(claim.fact_ids for claim in numeric)
    assert all(not claim.calculation_run_ids for claim in numeric)
    assert any(claim.value == 475 for claim in numeric)


def test_document_intent_without_required_period_clarifies(planner: QuestionPlanner):
    plan = planner.plan("What did management report about Mercedes-Benz Mobility EBIT?")
    assert plan.status is PlanningStatus.NEEDS_CLARIFICATION
    assert "period" in plan.ambiguity_reason.lower()


@pytest.mark.parametrize(
    "question,question_type,operation,route",
    (
        (
            "What was Mercedes-Benz Mobility EBIT in Q2 2026?",
            QuestionType.REPORTED_FACT, PlanOperation.LOOKUP, WorkflowRoute.ANALYTICS_ONLY,
        ),
        (
            "Calculate the change in Henkel sales from H1 2025 to H1 2026.",
            QuestionType.CALCULATION, PlanOperation.CALCULATE_CHANGE, WorkflowRoute.ANALYTICS_ONLY,
        ),
        (
            "Reconcile Henkel organic growth in H1 2026.",
            QuestionType.CALCULATION, PlanOperation.RECONCILE, WorkflowRoute.DECOMPOSITION_EXPLANATION,
        ),
        (
            "Rank the Mercedes-Benz Cars EBIT bridge components in Q2 2026.",
            QuestionType.VARIANCE_DECOMPOSITION, PlanOperation.DECOMPOSE_VARIANCE,
            WorkflowRoute.DECOMPOSITION_EXPLANATION,
        ),
    ),
)
def test_negative_controls_do_not_become_document_intent(
    planner: QuestionPlanner,
    question: str,
    question_type: QuestionType,
    operation: PlanOperation,
    route: WorkflowRoute,
):
    plan = planner.plan(question)
    assert plan.status is PlanningStatus.READY
    assert plan.question_type is question_type
    assert plan.operation is operation
    assert EnterpriseAnalyticsGraph._route(plan) is route


def test_required_document_evidence_fails_closed_when_retrieval_is_empty():
    units = [
        EvidenceUnit.model_validate_json(line)
        for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    henkel_only = next(unit for unit in units if unit.company_id == "henkel")
    graph = EnterpriseAnalyticsGraph(ROOT, retriever=GovernedRetriever([henkel_only], root=ROOT))
    cases = (
        ("What did management report about Mercedes-Benz Mobility EBIT in Q2 2026?", WorkflowRoute.KNOWLEDGE_ONLY),
        ("According to management, what was Mercedes-Benz Mobility EBIT in Q2 2026?", WorkflowRoute.HYBRID),
    )
    for question, route in cases:
        result = graph.run(question)
        assert result.route is route
        assert result.status is WorkflowStatus.REFUSED
        assert result.refusal_reason == "REQUIRED_DOCUMENT_EVIDENCE_UNAVAILABLE"
        assert not result.claims
        assert not result.citations


def test_predictive_request_is_generically_unsupported(planner: QuestionPlanner, graph: EnterpriseAnalyticsGraph):
    question = "Predict Siemens margin next year."
    plan = planner.plan(question)
    assert plan.status is PlanningStatus.UNSUPPORTED
    assert "Predictive forecasts" in plan.unsupported_reason
    result = graph.run(question)
    assert result.route is WorkflowRoute.UNSUPPORTED
    assert result.status is WorkflowStatus.REFUSED
    assert not result.claims
