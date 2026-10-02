from pathlib import Path

import pytest
from pydantic import ValidationError

from src.planning.models import (
    AnalyticalPlan,
    CompanyId,
    MetricId,
    PeriodId,
    PlanOperation,
    PlanningStatus,
    PlanTarget,
    QuestionType,
)
from src.planning.registry import PlanningRegistry
from src.schemas.models import ConfidenceLevel, PeriodGrain


ROOT = Path(__file__).resolve().parents[1]


def test_planning_registry_loads_only_catalog_metrics():
    registry = PlanningRegistry(ROOT)
    assert len(registry.metrics) == 27
    assert len(registry.metric_aliases) == 58
    assert {metric_id for _, _, metric_id in registry.metric_aliases} <= set(registry.metrics)


def test_plan_target_requires_period_and_grain_together():
    with pytest.raises(ValidationError, match="period and period_grain"):
        PlanTarget(company=CompanyId.HENKEL, metric_id=MetricId.HENKEL_SALES, period=PeriodId.H1_2026)


@pytest.mark.negative
def test_strict_model_rejects_string_for_enum():
    with pytest.raises(ValidationError):
        PlanTarget(
            company="henkel",
            metric_id="henkel_sales",
            period=PeriodId.H1_2026,
            period_grain=PeriodGrain.HALF_YEAR,
        )


@pytest.mark.negative
def test_model_forbids_unknown_fields():
    with pytest.raises(ValidationError, match="Extra inputs"):
        PlanTarget(company=CompanyId.HENKEL, metric_id=MetricId.HENKEL_SALES, invented=True)


@pytest.mark.negative
def test_model_rejects_invented_metric_id():
    with pytest.raises(ValidationError):
        PlanTarget(company=CompanyId.HENKEL, metric_id="henkel_invented_metric")


@pytest.mark.negative
def test_model_rejects_company_metric_mismatch():
    with pytest.raises(ValidationError, match="does not belong to company"):
        PlanTarget(company=CompanyId.HENKEL, metric_id=MetricId.MERCEDES_REVENUE)


def test_taxonomy_and_status_values_are_closed():
    assert {item.value for item in QuestionType} == {
        "REPORTED_FACT", "CALCULATION", "VARIANCE_DECOMPOSITION", "METRIC_DEFINITION",
        "CROSS_COMPANY_COMPARISON", "DOCUMENT_CONTEXT", "HYBRID_ANALYSIS", "AMBIGUOUS", "UNSUPPORTED",
    }
    assert {item.value for item in PlanningStatus} == {"READY", "NEEDS_CLARIFICATION", "UNSUPPORTED"}


@pytest.mark.negative
def test_ready_plan_requires_target():
    with pytest.raises(ValidationError, match="primary_target"):
        AnalyticalPlan(
            question_id="q1", raw_question="question", question_type=QuestionType.REPORTED_FACT,
            status=PlanningStatus.READY, operation=PlanOperation.LOOKUP,
            requires_documents=True, requires_calculation=False,
            requires_decomposition=False, requires_cross_company_comparison=False,
            resolution_confidence=ConfidenceLevel.HIGH,
        )


@pytest.mark.negative
def test_clarification_requires_reason_question_and_missing_fields():
    with pytest.raises(ValidationError, match="NEEDS_CLARIFICATION"):
        AnalyticalPlan(
            question_id="q1", raw_question="question", question_type=QuestionType.AMBIGUOUS,
            status=PlanningStatus.NEEDS_CLARIFICATION, operation=PlanOperation.NONE,
            requires_documents=False, requires_calculation=False,
            requires_decomposition=False, requires_cross_company_comparison=False,
            resolution_confidence=ConfidenceLevel.LOW,
        )


@pytest.mark.negative
def test_unsupported_plan_requires_reason():
    with pytest.raises(ValidationError, match="unsupported_reason"):
        AnalyticalPlan(
            question_id="q1", raw_question="question", question_type=QuestionType.UNSUPPORTED,
            status=PlanningStatus.UNSUPPORTED, operation=PlanOperation.NONE,
            requires_documents=False, requires_calculation=False,
            requires_decomposition=False, requires_cross_company_comparison=False,
            resolution_confidence=ConfidenceLevel.HIGH,
        )
