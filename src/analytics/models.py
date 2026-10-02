"""Strict result and lineage contracts for the Step 4 execution layer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator

from src.planning.models import CompanyId, MetricId, PeriodId, PlanOperation
from src.schemas.models import (
    CalculationRunStatus,
    ClaimSemantics,
    PeriodGrain,
    ProvenanceType,
    Unit,
    VerificationStatus,
)


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    SUCCESS_WITH_LIMITATIONS = "SUCCESS_WITH_LIMITATIONS"


class ExecutionOperation(str, Enum):
    RETRIEVE = "RETRIEVE"
    PERIOD_COMPARISON = "PERIOD_COMPARISON"
    DECOMPOSITION = "DECOMPOSITION"
    RANKING = "RANKING"
    RECONCILIATION = "RECONCILIATION"


class CalculationRuleId(str, Enum):
    ABSOLUTE_CHANGE_V1 = "ABSOLUTE_CHANGE_V1"
    PERCENT_CHANGE_V1 = "PERCENT_CHANGE_V1"
    PERCENTAGE_POINT_CHANGE_V1 = "PERCENTAGE_POINT_CHANGE_V1"
    HENKEL_ORGANIC_RECONCILIATION_V1 = "HENKEL_ORGANIC_RECONCILIATION_V1"
    HENKEL_NOMINAL_BRIDGE_V1 = "HENKEL_NOMINAL_BRIDGE_V1"
    MERCEDES_EBIT_BRIDGE_V1 = "MERCEDES_EBIT_BRIDGE_V1"
    MERCEDES_ADJUSTED_TO_REPORTED_EBIT_V1 = "MERCEDES_ADJUSTED_TO_REPORTED_EBIT_V1"
    RANK_CONTRIBUTIONS_V1 = "RANK_CONTRIBUTIONS_V1"


class CalculationOutputField(str, Enum):
    ABSOLUTE_CHANGE = "ABSOLUTE_CHANGE"
    PERCENT_CHANGE = "PERCENT_CHANGE"
    PERCENTAGE_POINT_CHANGE = "PERCENTAGE_POINT_CHANGE"
    RECONCILIATION_CALCULATED_VALUE = "RECONCILIATION_CALCULATED_VALUE"
    RANKING = "RANKING"


class WarningCode(str, Enum):
    ZERO_DENOMINATOR = "ZERO_DENOMINATOR"
    NON_POSITIVE_BASELINE_PERCENT_CHANGE_UNAVAILABLE = "NON_POSITIVE_BASELINE_PERCENT_CHANGE_UNAVAILABLE"
    NEAR_ZERO_BASELINE_PERCENT_CHANGE_UNAVAILABLE = "NEAR_ZERO_BASELINE_PERCENT_CHANGE_UNAVAILABLE"
    PERCENT_CHANGE_DISALLOWED_FOR_METRIC = "PERCENT_CHANGE_DISALLOWED_FOR_METRIC"
    ROUNDING_TOLERANCE_APPLIED = "ROUNDING_TOLERANCE_APPLIED"


class LimitationCode(str, Enum):
    MANAGEMENT_ATTRIBUTION_NOT_CAUSAL = "MANAGEMENT_ATTRIBUTION_NOT_CAUSAL"
    COMBINED_COMPONENT_NOT_SPLIT = "COMBINED_COMPONENT_NOT_SPLIT"
    PERCENT_CHANGE_UNAVAILABLE = "PERCENT_CHANGE_UNAVAILABLE"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"


class FactValue(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    fact_id: int
    company: CompanyId
    metric_id: MetricId
    reported_name: str
    business_scope: str
    period: PeriodId
    period_grain: PeriodGrain
    value: Decimal
    unit: Unit
    provenance_type: ProvenanceType
    claim_semantics: ClaimSemantics
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    verification_status: VerificationStatus
    rounding_tolerance: Decimal


class RankedComponent(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    rank: int
    fact_id: int
    metric_id: MetricId
    component_label: str
    value: Decimal
    unit: Unit
    provenance_type: ProvenanceType


class CalculationRunRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    run_id: str
    rule_id: CalculationRuleId
    rule_version: str
    company: CompanyId
    metric_id: MetricId
    output_field: CalculationOutputField
    input_fact_ids: tuple[int, ...]
    input_digest: str
    result_value: Decimal | None
    executed_at: datetime
    status: CalculationRunStatus
    tolerance_applied: Decimal

    @model_validator(mode="after")
    def successful_run_has_result_and_inputs(self) -> "CalculationRunRecord":
        if not self.input_fact_ids:
            raise ValueError("calculation lineage requires input facts")
        if self.status is CalculationRunStatus.SUCCESS and self.result_value is None:
            raise ValueError("successful calculation run requires result_value")
        return self


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    rule_id: CalculationRuleId
    expected_value: Decimal
    calculated_value: Decimal
    absolute_difference: Decimal
    tolerance: Decimal
    passed: bool
    source_fact_ids: tuple[int, ...]
    calculation_run_id: str


class ProvenanceCount(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    provenance_type: ProvenanceType
    fact_count: int


class AnalyticalResult(BaseModel):
    """Machine-readable analytical evidence; intentionally not a prose answer."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    execution_version: str = "4.0.0"
    execution_id: str
    question_id: str
    source_plan_operation: PlanOperation
    operation: ExecutionOperation
    status: ExecutionStatus
    primary_result: FactValue
    comparison_result: FactValue | None = None
    supporting_results: tuple[FactValue, ...] = ()
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    percentage_point_change: Decimal | None = None
    decomposition_components: tuple[FactValue, ...] = ()
    ranked_components: tuple[RankedComponent, ...] = ()
    reconciliation_results: tuple[ReconciliationResult, ...] = ()
    provenance_summary: tuple[ProvenanceCount, ...]
    evidence_ids: tuple[str, ...]
    calculation_runs: tuple[CalculationRunRecord, ...] = ()
    calculation_run_ids: tuple[str, ...] = ()
    warnings: tuple[WarningCode, ...] = ()
    limitations: tuple[LimitationCode, ...] = ()

    @model_validator(mode="after")
    def lineage_and_operation_are_consistent(self) -> "AnalyticalResult":
        if self.calculation_run_ids != tuple(run.run_id for run in self.calculation_runs):
            raise ValueError("calculation_run_ids must match calculation_runs")
        if self.operation is ExecutionOperation.PERIOD_COMPARISON and self.comparison_result is None:
            raise ValueError("period comparison requires comparison_result")
        if self.ranked_components and self.operation is not ExecutionOperation.RANKING:
            raise ValueError("ranked_components require RANKING operation")
        return self
