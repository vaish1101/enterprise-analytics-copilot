from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.build_normalized_facts import build_rows
from src.analytics import AnalyticsExecutor, ExecutionRejectedError, FactStore
from src.analytics.calculations import CalculationError, RuleRegistry, calculate_period_change
from src.analytics.models import (
    CalculationOutputField,
    CalculationRuleId,
    CalculationRunRecord,
    ExecutionOperation,
    FactValue,
    LimitationCode,
    WarningCode,
)
from src.planning import QuestionPlanner
from src.planning.models import CompanyId, MetricId, PlanningStatus
from src.schemas.models import CalculationRunStatus, ProvenanceType, Unit


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def planner():
    return QuestionPlanner(ROOT)


@pytest.fixture(scope="module")
def executor():
    return AnalyticsExecutor(ROOT, clock=lambda: FIXED_TIME)


def test_normalized_fact_store_loads_reviewed_contract():
    store = FactStore(ROOT)
    assert len(store.records) == 195
    assert len(build_rows()) == 163
    assert all(record.fact.evidence_ids for record in store.records)
    assert all(record.fact.source_ids for record in store.records)


def test_ready_plan_retrieves_exact_fact_with_provenance_and_evidence(planner, executor):
    result = executor.execute(planner.plan("What were Henkel H1 2026 sales?"))
    assert result.operation is ExecutionOperation.RETRIEVE
    assert result.primary_result.value == Decimal("10348")
    assert result.primary_result.unit is Unit.EUR_MILLION
    assert result.primary_result.provenance_type is ProvenanceType.REPORTED
    assert result.evidence_ids == result.primary_result.evidence_ids


@pytest.mark.negative
def test_needs_clarification_plan_is_rejected(planner, executor):
    plan = planner.plan("What were Mercedes sales in Q2 2026?")
    assert plan.status is PlanningStatus.NEEDS_CLARIFICATION
    with pytest.raises(ExecutionRejectedError, match="READY"):
        executor.execute(plan)


@pytest.mark.negative
def test_unsupported_plan_is_rejected(planner, executor):
    plan = planner.plan("What was Mercedes-Benz Cars pricing contribution in Q2 2026?")
    assert plan.status is PlanningStatus.UNSUPPORTED
    with pytest.raises(ExecutionRejectedError, match="READY"):
        executor.execute(plan)


@pytest.mark.negative
def test_malformed_input_is_rejected(executor):
    with pytest.raises(ExecutionRejectedError, match="AnalyticalPlan"):
        executor.execute({"status": "READY"})


@pytest.mark.negative
def test_missing_normalized_fact_is_rejected_by_planner(planner, executor):
    plan = planner.plan("What was Henkel Hair organic growth in H1 2026?")
    assert plan.status is PlanningStatus.UNSUPPORTED
    assert "No normalized runtime fact" in plan.unsupported_reason
    with pytest.raises(ExecutionRejectedError, match="READY"):
        executor.execute(plan)


def test_absolute_and_percentage_change(planner, executor):
    plan = planner.plan("How did Mercedes-Benz Cars adjusted EBIT change from Q2 2025 to Q2 2026?")
    result = executor.execute(plan)
    assert result.absolute_change == Decimal("-319")
    assert result.percentage_change is None
    assert WarningCode.PERCENT_CHANGE_DISALLOWED_FOR_METRIC in result.warnings
    assert LimitationCode.PERCENT_CHANGE_UNAVAILABLE in result.limitations
    assert [run.rule_id for run in result.calculation_runs] == [
        CalculationRuleId.ABSOLUTE_CHANGE_V1, CalculationRuleId.PERCENT_CHANGE_V1,
    ]


def test_percentage_point_change_for_rate(planner, executor):
    plan = planner.plan("How much did Henkel organic sales growth change from H1 2025 to H1 2026?")
    result = executor.execute(plan)
    assert result.absolute_change is None
    assert result.percentage_change is None
    assert result.percentage_point_change == Decimal("3.3")
    assert result.calculation_runs[0].rule_id is CalculationRuleId.PERCENTAGE_POINT_CHANGE_V1


@pytest.mark.negative
def test_invalid_unit_combination_is_rejected(executor):
    store = executor.facts
    current = store.records[0].fact
    data = current.model_dump()
    data.update(fact_id=9999, period=current.period, unit=Unit.VEHICLE)
    incompatible = FactValue(**data)
    with pytest.raises(CalculationError, match="identical units"):
        calculate_period_change(executor.rules, current, incompatible, FIXED_TIME, "unit")


def test_zero_denominator_records_failed_percentage_run(executor):
    base = executor.facts.records[0].fact
    prior_data = base.model_dump()
    prior_data.update(fact_id=9001, value=Decimal("0"))
    current_data = base.model_dump()
    current_data.update(fact_id=9002, value=Decimal("5"))
    outcome = calculate_period_change(
        executor.rules, FactValue(**current_data), FactValue(**prior_data), FIXED_TIME, "zero"
    )
    assert outcome.absolute_change == Decimal("5")
    assert outcome.percentage_change is None
    assert WarningCode.ZERO_DENOMINATOR in outcome.warnings
    assert outcome.runs[-1].status is CalculationRunStatus.FAILED


def test_negative_denominator_makes_percentage_unavailable(executor):
    base = executor.facts.records[0].fact
    prior_data = base.model_dump()
    prior_data.update(fact_id=9011, value=Decimal("-10"))
    current_data = base.model_dump()
    current_data.update(fact_id=9012, value=Decimal("-5"))
    outcome = calculate_period_change(
        executor.rules, FactValue(**current_data), FactValue(**prior_data), FIXED_TIME, "negative"
    )
    assert outcome.percentage_change is None
    assert WarningCode.NON_POSITIVE_BASELINE_PERCENT_CHANGE_UNAVAILABLE in outcome.warnings


def test_percentage_change_remains_available_for_positive_revenue_baseline(planner, executor):
    plan = planner.plan(
        "Calculate the difference between Mercedes-Benz Group Q2 2025 revenue and Q2 2026 revenue."
    )
    result = executor.execute(plan)
    assert result.absolute_change == Decimal("-1092")
    assert result.percentage_change == Decimal("-1092") / Decimal("33153") * Decimal("100")


@pytest.mark.negative
def test_calculation_lineage_requires_input_facts():
    with pytest.raises(ValidationError, match="input facts"):
        CalculationRunRecord(
            run_id="run", rule_id=CalculationRuleId.ABSOLUTE_CHANGE_V1,
            rule_version="1.0.0", company=CompanyId.HENKEL, metric_id=MetricId.HENKEL_SALES,
            output_field=CalculationOutputField.ABSOLUTE_CHANGE,
            input_fact_ids=(), input_digest="digest", result_value=Decimal("1"),
            executed_at=FIXED_TIME, status=CalculationRunStatus.SUCCESS,
            tolerance_applied=Decimal("0"),
        )


def test_henkel_exact_reconciliation(planner, executor):
    result = executor.execute(planner.plan("Reconcile Henkel organic growth in H1 2026."))
    reconciliation = result.reconciliation_results[0]
    assert reconciliation.passed is True
    assert reconciliation.absolute_difference == Decimal("0.0")


def test_henkel_rounding_tolerance_is_retained(planner, executor):
    result = executor.execute(
        planner.plan("Reconcile Henkel Adhesive Technologies organic growth in H1 2026.")
    )
    reconciliation = result.reconciliation_results[0]
    assert reconciliation.passed is True
    assert reconciliation.absolute_difference == Decimal("0.1")
    assert reconciliation.tolerance == Decimal("0.1")
    assert WarningCode.ROUNDING_TOLERANCE_APPLIED in result.warnings


@pytest.mark.parametrize("scope", ["Cars", "Vans", "Financial Services"])
def test_mercedes_bridges_and_reported_endpoints_reconcile(scope, planner, executor):
    result = executor.execute(
        planner.plan(f"Reconcile Mercedes-Benz {scope} adjusted EBIT bridge in Q2 2026.")
    )
    assert len(result.reconciliation_results) == 2
    assert all(item.passed for item in result.reconciliation_results)
    assert {item.rule_id for item in result.reconciliation_results} == {
        CalculationRuleId.MERCEDES_EBIT_BRIDGE_V1,
        CalculationRuleId.MERCEDES_ADJUSTED_TO_REPORTED_EBIT_V1,
    }
    available_fact_ids = {
        result.primary_result.fact_id,
        *(item.fact_id for item in result.decomposition_components),
        *(item.fact_id for item in result.supporting_results),
    }
    assert all(set(item.source_fact_ids) <= available_fact_ids for item in result.reconciliation_results)
    assert all(item.evidence_ids for item in result.supporting_results)


def test_combined_mercedes_label_is_preserved(planner, executor):
    result = executor.execute(
        planner.plan("What were the drivers of Mercedes-Benz Cars adjusted EBIT bridge in Q2 2026?")
    )
    assert result.decomposition_components[0].reported_name == "Volume / structure / net pricing"
    assert LimitationCode.COMBINED_COMPONENT_NOT_SPLIT in result.limitations


def test_ranking_largest_negative_and_positive(planner, executor):
    negative = executor.execute(planner.plan(
        "Which Mercedes-Benz Cars EBIT bridge component had the largest negative contribution in Q2 2026?"
    ))
    positive = executor.execute(planner.plan(
        "Which Mercedes-Benz Cars EBIT bridge component had the largest positive contribution in Q2 2026?"
    ))
    assert negative.ranked_components[0].component_label == "Volume / structure / net pricing"
    assert negative.ranked_components[0].value == Decimal("-602")
    assert positive.ranked_components[0].component_label == "Industrial performance"
    assert positive.ranked_components[0].value == Decimal("482")


@pytest.mark.negative
def test_cross_company_arithmetic_is_rejected(planner, executor):
    plan = planner.plan("Compare Henkel sales with Mercedes-Benz Group revenue in H1 2026.")
    assert plan.status is PlanningStatus.READY
    with pytest.raises(ExecutionRejectedError, match="cross-company"):
        executor.execute(plan)


@pytest.mark.negative
def test_definition_operation_is_not_executable(planner, executor):
    plan = planner.plan("How does Henkel define organic sales growth?")
    with pytest.raises(ExecutionRejectedError):
        executor.execute(plan)


def test_deterministic_rerun_is_identical(planner, executor):
    plan = planner.plan("How did Mercedes-Benz Cars adjusted EBIT change from Q2 2025 to Q2 2026?")
    assert executor.execute(plan).model_dump_json() == executor.execute(plan).model_dump_json()


def test_no_narrative_or_causal_output_fields(planner, executor):
    result = executor.execute(planner.plan("What contributed to Henkel organic growth in H1 2026?"))
    assert "narrative" not in type(result).model_fields
    assert "answer" not in type(result).model_fields
    assert all(component.claim_semantics.value != "INTERPRETATION" for component in result.decomposition_components)


def test_rule_registry_is_closed():
    registry = RuleRegistry(ROOT)
    assert set(registry.rows) == set(CalculationRuleId)
    assert len(registry.policies) == 27
