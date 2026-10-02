from pathlib import Path

import pytest

from src.planning import QuestionPlanner
from src.planning.models import ComparabilityStatus, PlanningStatus, QuestionType
from src.schemas.models import ConfidenceLevel, EvidenceType, PeriodGrain, ScopeType


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def planner():
    return QuestionPlanner(ROOT)


def test_reported_fact_is_resolved(planner):
    plan = planner.plan("What were Henkel H1 2026 sales?", question_id="fact")
    assert plan.question_type is QuestionType.REPORTED_FACT
    assert plan.status is PlanningStatus.READY
    assert plan.primary_target.metric_id == "henkel_sales"
    assert plan.primary_target.business_scope == "henkel_group"
    assert plan.primary_target.period.value == "H1_2026"
    assert plan.requires_documents is True
    assert EvidenceType.PRIMARY_NUMERIC in plan.required_evidence_types
    assert plan.evidence_expectation_ids


def test_variance_decomposition_routes_supporting_metrics(planner):
    plan = planner.plan("What contributed to Henkel organic growth in H1 2026?")
    assert plan.question_type is QuestionType.VARIANCE_DECOMPOSITION
    assert plan.requires_decomposition is True
    assert plan.primary_target.metric_id == "henkel_organic_sales_growth"
    assert EvidenceType.PRIMARY_NUMERIC in plan.required_evidence_types
    assert any("price" in item for item in plan.evidence_expectation_ids)
    assert any("volume" in item for item in plan.evidence_expectation_ids)


def test_calculation_has_current_and_comparison_period(planner):
    plan = planner.plan("How did Mercedes-Benz Group adjusted EBIT change from Q2 2025 to Q2 2026?")
    assert plan.question_type is QuestionType.CALCULATION
    assert plan.requires_calculation is True
    assert plan.primary_target.period.value == "Q2_2026"
    assert plan.primary_target.comparison_period.value == "Q2_2025"


def test_cross_company_revenue_comparison_is_limited(planner):
    plan = planner.plan("Compare Henkel sales with Mercedes-Benz Group revenue in H1 2026.")
    assert plan.status is PlanningStatus.READY
    assert plan.question_type is QuestionType.CROSS_COMPANY_COMPARISON
    assert plan.primary_target.metric_id == "henkel_sales"
    assert plan.comparison_target.metric_id == "mercedes_revenue"
    assert plan.comparability_status is ComparabilityStatus.LIMITED
    assert plan.resolution_confidence is ConfidenceLevel.MEDIUM


def test_metric_definition_does_not_require_period_or_documents(planner):
    plan = planner.plan("How does Henkel define organic sales growth?")
    assert plan.question_type is QuestionType.METRIC_DEFINITION
    assert plan.primary_target.period is None
    assert plan.requires_documents is False


def test_why_question_is_hybrid_analysis(planner):
    plan = planner.plan("Why did Mercedes-Benz Group adjusted EBIT decline in Q2 2026?")
    assert plan.question_type is QuestionType.HYBRID_ANALYSIS
    assert plan.requires_documents is True
    assert plan.requires_decomposition is True


def test_ambiguous_mercedes_sales_requests_clarification(planner):
    plan = planner.plan("What were Mercedes sales in Q2 2026?")
    assert plan.status is PlanningStatus.NEEDS_CLARIFICATION
    assert plan.question_type is QuestionType.AMBIGUOUS
    assert "revenue or vehicle unit sales" in plan.clarification_question


@pytest.mark.negative
def test_undisclosed_mercedes_price_split_is_unsupported(planner):
    plan = planner.plan(
        "How much of Mercedes-Benz Cars adjusted EBIT decline in Q2 2026 was due to lower unit sales versus reduced pricing?"
    )
    assert plan.status is PlanningStatus.UNSUPPORTED
    assert "Volume / structure / net pricing" in plan.unsupported_reason


def test_combined_mercedes_bridge_label_is_resolved_without_splitting(planner):
    plan = planner.plan("What was Mercedes-Benz Cars volume / structure / net pricing in Q2 2026?")
    assert plan.status is PlanningStatus.READY
    assert plan.primary_target.metric_id == "mercedes_bridge_volume_structure_net_pricing"
    assert plan.primary_target.period_grain is PeriodGrain.QUARTER_YOY
    assert plan.primary_target.comparison_period.value == "Q2_2025"


@pytest.mark.negative
def test_q1_request_is_unsupported(planner):
    plan = planner.plan("What was Henkel Adhesive Technologies price contribution in Q1 2026?")
    assert plan.status is PlanningStatus.UNSUPPORTED
    assert "Q1 2026" in plan.unsupported_reason


def test_unit_sales_requires_non_group_scope(planner):
    plan = planner.plan("What were Mercedes-Benz unit sales in H1 2026?")
    assert plan.status is PlanningStatus.NEEDS_CLARIFICATION
    assert "scope" in plan.ambiguity_reason.lower()


def test_unit_sales_with_segment_is_ready(planner):
    plan = planner.plan("What were Mercedes-Benz Cars unit sales in H1 2026?")
    assert plan.status is PlanningStatus.READY
    assert plan.primary_target.scope_type is ScopeType.SEGMENT
    assert plan.primary_target.metric_id == "mercedes_unit_sales"


@pytest.mark.negative
def test_scope_type_mismatch_is_unsupported(planner):
    plan = planner.plan("What was Henkel Hair price contribution in H1 2026?")
    assert plan.status is PlanningStatus.UNSUPPORTED
    assert "BUSINESS_AREA" in plan.unsupported_reason


@pytest.mark.negative
def test_cross_company_unlike_metrics_are_not_comparable(planner):
    plan = planner.plan("Compare Henkel organic sales growth with Mercedes adjusted EBIT in Q2 2026.")
    assert plan.status is PlanningStatus.UNSUPPORTED
    assert plan.question_type is QuestionType.CROSS_COMPANY_COMPARISON
    assert plan.comparability_status is ComparabilityStatus.NOT_COMPARABLE


@pytest.mark.negative
@pytest.mark.parametrize(
    "question,reason_fragment",
    [
        ("What was BMW revenue in Q2 2026?", "outside"),
        ("What was Henkel EBITDA in H1 2026?", "metric catalog"),
        ("What was revenue in H1 2026?", None),
    ],
)
def test_fail_closed_boundaries(planner, question, reason_fragment):
    plan = planner.plan(question)
    assert plan.status is not PlanningStatus.READY
    reason = plan.unsupported_reason or plan.ambiguity_reason
    if reason_fragment:
        assert reason_fragment in reason


def test_output_is_deterministic(planner):
    question = "What were Henkel Consumer Brands sales in H1 2026?"
    assert planner.plan(question).model_dump_json() == planner.plan(question).model_dump_json()


def test_ranking_operation_and_direction_are_structured(planner):
    plan = planner.plan(
        "Which Mercedes-Benz Cars EBIT bridge component had the largest negative contribution in Q2 2026?"
    )
    assert plan.operation.value == "RANK_CONTRIBUTIONS"
    assert plan.ranking_direction.value == "LARGEST_NEGATIVE"


def test_reconciliation_operation_does_not_require_comparison_period(planner):
    plan = planner.plan("Reconcile Henkel organic growth in H1 2026.")
    assert plan.status is PlanningStatus.READY
    assert plan.operation.value == "RECONCILE"
    assert plan.primary_target.comparison_period is None


@pytest.mark.negative
def test_ready_requires_normalized_runtime_fact(planner):
    plan = planner.plan("What were Henkel Hair sales in H1 2026?")
    assert plan.status is PlanningStatus.UNSUPPORTED
    assert "No normalized runtime fact" in plan.unsupported_reason
