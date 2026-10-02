"""Strict output contract for Step 3 question understanding and planning."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas.models import ConfidenceLevel, EvidenceType, PeriodGrain, ScopeType


class QuestionType(str, Enum):
    REPORTED_FACT = "REPORTED_FACT"
    CALCULATION = "CALCULATION"
    VARIANCE_DECOMPOSITION = "VARIANCE_DECOMPOSITION"
    METRIC_DEFINITION = "METRIC_DEFINITION"
    CROSS_COMPANY_COMPARISON = "CROSS_COMPANY_COMPARISON"
    DOCUMENT_CONTEXT = "DOCUMENT_CONTEXT"
    HYBRID_ANALYSIS = "HYBRID_ANALYSIS"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"


class PlanningStatus(str, Enum):
    READY = "READY"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED = "UNSUPPORTED"


class ExtensibleStrEnum(str, Enum):
    """Governed string enum whose additional values come from validated catalogs."""

    @classmethod
    def _missing_(cls, value):
        if not isinstance(value, str) or not value or not value.replace("_", "").isalnum():
            return None
        member = str.__new__(cls, value)
        member._name_ = f"CATALOG_{value.upper()}"
        member._value_ = value
        cls._value2member_map_[value] = member
        return member


class CompanyId(ExtensibleStrEnum):
    HENKEL = "henkel"
    MERCEDES_BENZ_GROUP = "mercedes_benz_group"


class MetricId(ExtensibleStrEnum):
    HENKEL_SALES = "henkel_sales"
    HENKEL_NOMINAL_SALES_CHANGE = "henkel_nominal_sales_change"
    HENKEL_ORGANIC_SALES_GROWTH = "henkel_organic_sales_growth"
    HENKEL_FX_EFFECT = "henkel_fx_effect"
    HENKEL_ACQUISITIONS_DIVESTMENTS_EFFECT = "henkel_acquisitions_divestments_effect"
    HENKEL_PRICE_CONTRIBUTION = "henkel_price_contribution"
    HENKEL_VOLUME_CONTRIBUTION = "henkel_volume_contribution"
    MERCEDES_REVENUE = "mercedes_revenue"
    MERCEDES_EBIT = "mercedes_ebit"
    MERCEDES_ADJUSTED_EBIT = "mercedes_adjusted_ebit"
    MERCEDES_UNIT_SALES = "mercedes_unit_sales"
    MERCEDES_BRIDGE_VOLUME_STRUCTURE_NET_PRICING = "mercedes_bridge_volume_structure_net_pricing"
    MERCEDES_BRIDGE_FOREIGN_EXCHANGE_RATES = "mercedes_bridge_foreign_exchange_rates"
    MERCEDES_BRIDGE_INDUSTRIAL_PERFORMANCE = "mercedes_bridge_industrial_performance"
    MERCEDES_BRIDGE_SELLING_EXPENSES = "mercedes_bridge_selling_expenses"
    MERCEDES_BRIDGE_GENERAL_ADMINISTRATIVE_EXPENSES = "mercedes_bridge_general_administrative_expenses"
    MERCEDES_BRIDGE_RESEARCH_NONCAPITALIZED_DEVELOPMENT = "mercedes_bridge_research_noncapitalized_development"
    MERCEDES_BRIDGE_OTHERS = "mercedes_bridge_others"
    MERCEDES_BRIDGE_ADJUSTMENTS = "mercedes_bridge_adjustments"
    MERCEDES_BRIDGE_COST_OF_CREDIT_RISK = "mercedes_bridge_cost_of_credit_risk"
    MERCEDES_BRIDGE_VOLUME_MARGIN = "mercedes_bridge_volume_margin"


class PeriodId(ExtensibleStrEnum):
    Q2_2026 = "Q2_2026"
    H1_2026 = "H1_2026"
    Q2_2025 = "Q2_2025"
    H1_2025 = "H1_2025"


class PlanOperation(str, Enum):
    LOOKUP = "LOOKUP"
    CALCULATE_CHANGE = "CALCULATE_CHANGE"
    DECOMPOSE_VARIANCE = "DECOMPOSE_VARIANCE"
    DEFINE_METRIC = "DEFINE_METRIC"
    COMPARE = "COMPARE"
    RETRIEVE_CONTEXT = "RETRIEVE_CONTEXT"
    EXPLAIN_WITH_EVIDENCE = "EXPLAIN_WITH_EVIDENCE"
    RANK_CONTRIBUTIONS = "RANK_CONTRIBUTIONS"
    RECONCILE = "RECONCILE"
    NONE = "NONE"


class RankingDirection(str, Enum):
    LARGEST_POSITIVE = "LARGEST_POSITIVE"
    LARGEST_NEGATIVE = "LARGEST_NEGATIVE"
    ABSOLUTE_MAGNITUDE = "ABSOLUTE_MAGNITUDE"


class AnalyticalDimension(str, Enum):
    COMPANY = "COMPANY"
    METRIC = "METRIC"
    BUSINESS_SCOPE = "BUSINESS_SCOPE"
    PERIOD = "PERIOD"
    COMPARISON_PERIOD = "COMPARISON_PERIOD"


class MissingField(str, Enum):
    COMPANY = "COMPANY"
    METRIC = "METRIC"
    BUSINESS_SCOPE = "BUSINESS_SCOPE"
    PERIOD = "PERIOD"
    COMPARISON_PERIOD = "COMPARISON_PERIOD"
    COMPARISON_COMPANY = "COMPARISON_COMPANY"
    COMPARISON_METRIC = "COMPARISON_METRIC"


class ComparabilityStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ALLOWED = "ALLOWED"
    LIMITED = "LIMITED"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class PlanTarget(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    company: CompanyId
    metric_id: MetricId
    business_scope: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]+$")
    scope_type: ScopeType | None = None
    period: PeriodId | None = None
    period_grain: PeriodGrain | None = None
    comparison_period: PeriodId | None = None

    @model_validator(mode="after")
    def period_fields_are_consistent(self) -> "PlanTarget":
        if (self.period is None) != (self.period_grain is None):
            raise ValueError("period and period_grain must be supplied together")
        if self.comparison_period is not None and self.period is None:
            raise ValueError("comparison_period requires period")
        known_owner = (
            CompanyId.HENKEL if self.metric_id.value.startswith("henkel_")
            else CompanyId.MERCEDES_BENZ_GROUP if self.metric_id.value.startswith("mercedes_")
            else None
        )
        if known_owner is not None and self.company is not known_owner:
            raise ValueError("metric_id does not belong to company")
        if known_owner is None and not self.metric_id.value.startswith(f"{self.company.value}_"):
            raise ValueError("metric_id does not belong to company")
        return self


class AnalyticalPlan(BaseModel):
    """Closed, machine-checkable plan. It never contains an analytical answer."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    planner_version: str = "3.0.1"
    question_id: str = Field(min_length=1)
    raw_question: str = Field(min_length=1)
    question_type: QuestionType
    status: PlanningStatus
    operation: PlanOperation
    ranking_direction: RankingDirection | None = None
    primary_target: PlanTarget | None = None
    comparison_target: PlanTarget | None = None
    dimensions: tuple[AnalyticalDimension, ...] = ()
    required_evidence_types: tuple[EvidenceType, ...] = ()
    evidence_expectation_ids: tuple[str, ...] = ()
    requires_documents: bool
    requires_calculation: bool
    requires_decomposition: bool
    requires_cross_company_comparison: bool
    comparability_status: ComparabilityStatus = ComparabilityStatus.NOT_APPLICABLE
    comparability_note: str | None = None
    ambiguity_reason: str | None = None
    missing_fields: tuple[MissingField, ...] = ()
    unsupported_reason: str | None = None
    clarification_question: str | None = None
    resolution_confidence: ConfidenceLevel

    @model_validator(mode="after")
    def validate_status_contract(self) -> "AnalyticalPlan":
        if self.status is PlanningStatus.READY:
            if self.ambiguity_reason or self.missing_fields or self.unsupported_reason or self.clarification_question:
                raise ValueError("READY plans cannot contain clarification or unsupported fields")
            if self.primary_target is None:
                raise ValueError("READY plans require a primary_target")
        elif self.status is PlanningStatus.NEEDS_CLARIFICATION:
            if not self.ambiguity_reason or not self.clarification_question or not self.missing_fields:
                raise ValueError("NEEDS_CLARIFICATION requires a reason, question, and missing_fields")
            if self.unsupported_reason is not None:
                raise ValueError("clarification plans cannot contain unsupported_reason")
        elif self.status is PlanningStatus.UNSUPPORTED:
            if not self.unsupported_reason:
                raise ValueError("UNSUPPORTED plans require unsupported_reason")
            if self.clarification_question is not None or self.missing_fields:
                raise ValueError("unsupported plans cannot request clarification")
        if self.requires_cross_company_comparison != (self.question_type is QuestionType.CROSS_COMPANY_COMPARISON):
            raise ValueError("cross-company flag must match question_type")
        if self.comparison_target and not self.requires_cross_company_comparison:
            raise ValueError("comparison_target is reserved for cross-company plans")
        if (self.operation is PlanOperation.RANK_CONTRIBUTIONS) != (self.ranking_direction is not None):
            raise ValueError("ranking_direction is required only for ranking operations")
        return self
