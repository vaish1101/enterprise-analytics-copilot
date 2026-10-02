"""Dependency-free governed contracts shared by catalog validation and loaders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping, Sequence


class ProvenanceType(str, Enum):
    REPORTED = "REPORTED"
    CALCULATED = "CALCULATED"
    MANAGEMENT_ATTRIBUTED = "MANAGEMENT_ATTRIBUTED"
    INTERPRETATION = "INTERPRETATION"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"


class ClaimSemantics(str, Enum):
    REPORTED_FACT = "REPORTED_FACT"
    DERIVED_CALCULATION = "DERIVED_CALCULATION"
    MANAGEMENT_ATTRIBUTION = "MANAGEMENT_ATTRIBUTION"
    INTERPRETATION = "INTERPRETATION"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"


class PeriodGrain(str, Enum):
    QUARTER = "QUARTER"
    HALF_YEAR = "HALF_YEAR"
    YEAR = "YEAR"
    POINT_IN_TIME = "POINT_IN_TIME"
    QUARTER_YOY = "QUARTER_YOY"
    HALF_YEAR_YOY = "HALF_YEAR_YOY"


class ScopeType(str, Enum):
    GROUP = "GROUP"
    BUSINESS_UNIT = "BUSINESS_UNIT"
    BUSINESS_AREA = "BUSINESS_AREA"
    SEGMENT = "SEGMENT"
    REGION = "REGION"
    PRODUCT_CATEGORY = "PRODUCT_CATEGORY"


class ValueType(str, Enum):
    DECIMAL = "DECIMAL"
    INTEGER = "INTEGER"


class Unit(str, Enum):
    EUR_MILLION = "EUR_million"
    PERCENTAGE_POINT = "percentage_point"
    VEHICLE = "vehicle"


class CalculationType(str, Enum):
    REPORTED = "REPORTED"
    REPORTED_MANAGEMENT_DECOMPOSITION = "REPORTED_MANAGEMENT_DECOMPOSITION"
    REPORTED_RECONCILIATION = "REPORTED_RECONCILIATION"
    DETERMINISTIC_CALCULATION = "DETERMINISTIC_CALCULATION"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceType(str, Enum):
    PRIMARY_NUMERIC = "PRIMARY_NUMERIC"
    CORROBORATING_NUMERIC = "CORROBORATING_NUMERIC"
    MANAGEMENT_BRIDGE = "MANAGEMENT_BRIDGE"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class CalculationRunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BridgeComponentRole(str, Enum):
    START = "START"
    COMPONENT = "COMPONENT"
    ADJUSTED_ENDPOINT = "ADJUSTED_ENDPOINT"
    ADJUSTMENT = "ADJUSTMENT"
    REPORTED_ENDPOINT = "REPORTED_ENDPOINT"


def _required(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value


def parse_bool(value: str, field_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{field_name} must be 'true' or 'false'")


def deterministic_confidence(
    provenance_types: Iterable[ProvenanceType],
    *,
    numeric_evidence_verified: bool = True,
    evidence_complete: bool = True,
    evidence_gap: bool = False,
) -> ConfidenceLevel | None:
    """Classify evidence completeness independently from claim semantics."""

    values = tuple(provenance_types)
    if ProvenanceType.UNSUPPORTED in values:
        return None
    if evidence_gap or not evidence_complete or not numeric_evidence_verified or not values:
        return ConfidenceLevel.LOW
    if any(value in {ProvenanceType.INTERPRETATION, ProvenanceType.AMBIGUOUS} for value in values):
        return ConfidenceLevel.LOW
    if any(value in {ProvenanceType.CALCULATED, ProvenanceType.MANAGEMENT_ATTRIBUTED} for value in values):
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.HIGH


@dataclass(frozen=True)
class Company:
    company_id: str
    legal_name: str

    def __post_init__(self) -> None:
        _required(self.company_id, "company_id")
        _required(self.legal_name, "legal_name")


@dataclass(frozen=True)
class ReportingPeriod:
    period_id: str
    label: str
    grain: PeriodGrain
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if not isinstance(self.grain, PeriodGrain):
            raise TypeError("grain must be a PeriodGrain")
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")


@dataclass(frozen=True)
class BusinessScope:
    scope_id: str
    company_id: str
    scope_type: ScopeType
    scope_name: str
    parent_scope_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope_type, ScopeType):
            raise TypeError("scope_type must be a ScopeType")


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    company_id: str
    official_url: str
    expected_filename: str
    sha256: str | None = None


@dataclass(frozen=True)
class EvidenceExpectation:
    expectation_id: str
    metric_id: str
    company_id: str
    source_id: str
    source_location: str
    source_page_or_sheet: str
    source_cell_or_range: str
    evidence_type: EvidenceType
    verification_status: VerificationStatus
    note: str = ""

    def __post_init__(self) -> None:
        for name in ("expectation_id", "metric_id", "company_id", "source_id", "source_location", "source_page_or_sheet"):
            _required(getattr(self, name), name)
        if not isinstance(self.evidence_type, EvidenceType):
            raise TypeError("evidence_type must be an EvidenceType")
        if not isinstance(self.verification_status, VerificationStatus):
            raise TypeError("verification_status must be a VerificationStatus")


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    company_id: str
    reported_name: str
    canonical_family: str
    description: str
    definition: str
    unit: Unit
    value_type: ValueType
    allowed_period_grains: frozenset[PeriodGrain]
    allowed_scope_types: frozenset[ScopeType]
    allowed_provenance_types: frozenset[ProvenanceType]
    claim_semantics: ClaimSemantics
    calculation_type: CalculationType
    comparability_group: str
    comparable_across_companies: bool
    comparability_notes: str
    rounding_tolerance: Decimal
    evidence_required: bool
    causal_claim_allowed: bool
    evidence_expectations: tuple[EvidenceExpectation, ...] = field(default_factory=tuple)
    notes: str = ""

    def __post_init__(self) -> None:
        for name in (
            "metric_id", "company_id", "reported_name", "canonical_family",
            "description", "definition", "comparability_group", "comparability_notes",
        ):
            _required(getattr(self, name), name)
        if not self.allowed_period_grains or not self.allowed_scope_types or not self.allowed_provenance_types:
            raise ValueError("metric period, scope, and provenance allow-lists must not be empty")
        if self.rounding_tolerance < 0:
            raise ValueError("rounding_tolerance must be non-negative")
        if self.causal_claim_allowed:
            raise ValueError("no current metric permits a causal claim")
        if ProvenanceType.MANAGEMENT_ATTRIBUTED in self.allowed_provenance_types:
            if self.claim_semantics is not ClaimSemantics.MANAGEMENT_ATTRIBUTION:
                raise ValueError("management-attributed metrics require MANAGEMENT_ATTRIBUTION semantics")
        if ProvenanceType.CALCULATED in self.allowed_provenance_types:
            if self.claim_semantics is not ClaimSemantics.DERIVED_CALCULATION:
                raise ValueError("calculated metrics require DERIVED_CALCULATION semantics")
            if self.calculation_type is not CalculationType.DETERMINISTIC_CALCULATION:
                raise ValueError("calculated metrics require DETERMINISTIC_CALCULATION")
        if self.evidence_required and not self.evidence_expectations:
            raise ValueError("evidence_required metrics need at least one evidence expectation")
        for expectation in self.evidence_expectations:
            if expectation.metric_id != self.metric_id or expectation.company_id != self.company_id:
                raise ValueError("evidence expectation metric/company must match the metric")

    @classmethod
    def from_catalog_row(
        cls,
        row: Mapping[str, str],
        *,
        allowed_period_grains: Iterable[str | PeriodGrain],
        allowed_scope_types: Iterable[str | ScopeType],
        evidence_expectations: Sequence[EvidenceExpectation],
    ) -> "MetricDefinition":
        periods = frozenset(
            value if isinstance(value, PeriodGrain) else PeriodGrain(value)
            for value in allowed_period_grains
        )
        scopes = frozenset(
            value if isinstance(value, ScopeType) else ScopeType(value)
            for value in allowed_scope_types
        )
        provenance = ProvenanceType(row["allowed_provenance_type"])
        return cls(
            metric_id=row["metric_id"], company_id=row["company"],
            reported_name=row["reported_name"], canonical_family=row["canonical_family"],
            description=row["description"], definition=row["definition"],
            unit=Unit(row["unit"]), value_type=ValueType(row["value_type"]),
            allowed_period_grains=periods, allowed_scope_types=scopes,
            allowed_provenance_types=frozenset({provenance}),
            claim_semantics=ClaimSemantics(row["claim_semantics"]),
            calculation_type=CalculationType(row["calculation_type"]),
            comparability_group=row["comparability_group"],
            comparable_across_companies=parse_bool(row["comparable_across_companies"], "comparable_across_companies"),
            comparability_notes=row["comparability_notes"],
            rounding_tolerance=Decimal(row["rounding_tolerance"]),
            evidence_required=parse_bool(row["evidence_required"], "evidence_required"),
            causal_claim_allowed=parse_bool(row["causal_claim_allowed"], "causal_claim_allowed"),
            evidence_expectations=tuple(evidence_expectations), notes=row.get("notes", ""),
        )


@dataclass(frozen=True)
class CalculationRule:
    rule_id: str
    rule_name: str
    rule_version: str
    formula_or_executable_id: str
    output_metric_id: str
    company_id: str
    deterministic: bool
    description: str

    def __post_init__(self) -> None:
        if not self.deterministic:
            raise ValueError("calculation rules must be deterministic")


@dataclass(frozen=True)
class CalculationInput:
    input_fact_id: int
    input_role: str
    input_position: int

    def __post_init__(self) -> None:
        if self.input_position < 0:
            raise ValueError("input_position must be non-negative")
        _required(self.input_role, "input_role")


@dataclass(frozen=True)
class CalculationRun:
    run_id: str
    rule_id: str
    rule_version: str
    output_metric_id: str
    company_id: str
    executed_at: datetime
    execution_engine: str
    execution_version: str
    input_digest: str
    result_value: Decimal
    status: CalculationRunStatus
    inputs: tuple[CalculationInput, ...]

    def __post_init__(self) -> None:
        if self.status is CalculationRunStatus.SUCCESS and not self.inputs:
            raise ValueError("successful calculation runs require at least one input")
        for name in ("execution_engine", "execution_version", "input_digest"):
            _required(getattr(self, name), name)


@dataclass(frozen=True)
class MetricFact:
    fact_id: int
    metric_id: str
    company_id: str
    period_id: str
    scope_id: str
    value: Decimal
    unit: Unit
    value_type: ValueType
    provenance_type: ProvenanceType
    claim_semantics: ClaimSemantics
    causal_claim: bool = False
    source_id: str | None = None
    calculation_run_id: str | None = None

    def validate_against(
        self, metric: MetricDefinition, period: ReportingPeriod,
        scope: BusinessScope, source: SourceDocument | None,
        calculation_run: CalculationRun | None = None,
    ) -> None:
        if self.metric_id != metric.metric_id or self.company_id != metric.company_id:
            raise ValueError("fact metric/company does not match metric definition")
        if scope.company_id != self.company_id or self.scope_id != scope.scope_id:
            raise ValueError("fact scope is incompatible with company")
        if scope.scope_type not in metric.allowed_scope_types:
            raise ValueError("scope type is not allowed for metric")
        if period.period_id != self.period_id or period.grain not in metric.allowed_period_grains:
            raise ValueError("period grain is not allowed for metric")
        if self.unit is not metric.unit or self.value_type is not metric.value_type:
            raise ValueError("fact unit/value type does not match metric")
        if self.provenance_type not in metric.allowed_provenance_types:
            raise ValueError("fact provenance is not allowed for metric")
        if self.claim_semantics is not metric.claim_semantics:
            raise ValueError("fact claim semantics does not match metric")
        if self.causal_claim or metric.causal_claim_allowed:
            raise ValueError("current governed metrics do not permit causal claims")
        if self.provenance_type is ProvenanceType.CALCULATED:
            if calculation_run is None or self.calculation_run_id != calculation_run.run_id:
                raise ValueError("calculated fact requires calculation lineage")
            if calculation_run.status is not CalculationRunStatus.SUCCESS:
                raise ValueError("calculated fact requires a successful calculation run")
            if (calculation_run.output_metric_id != self.metric_id
                    or calculation_run.company_id != self.company_id
                    or calculation_run.result_value != self.value
                    or not calculation_run.inputs):
                raise ValueError("calculation run does not reproduce this fact")
            if source is not None or self.source_id is not None:
                raise ValueError("calculated fact uses calculation lineage rather than a primary source")
        else:
            if calculation_run is not None or self.calculation_run_id is not None:
                raise ValueError("non-calculated fact must not reference a calculation run")
            if source is None or self.source_id != source.source_id:
                raise ValueError("reported or management-attributed fact requires a source")
            if source.company_id != self.company_id:
                raise ValueError("fact source is incompatible with company")
            if source.source_id not in {item.source_id for item in metric.evidence_expectations}:
                raise ValueError("source is not an allowed evidence source for metric")


ReportedMetricFact = MetricFact


@dataclass(frozen=True)
class FactEvidence:
    evidence_id: str
    fact_id: int
    metric_id: str
    company_id: str
    expectation_id: str
    source_id: str
    source_location: str
    source_page_or_sheet: str
    source_cell_or_range: str
    evidence_type: EvidenceType
    verification_status: VerificationStatus
    note: str = ""

    def validate_against(self, fact: MetricFact, source: SourceDocument, expectation: EvidenceExpectation) -> None:
        if (self.fact_id, self.metric_id, self.company_id) != (fact.fact_id, fact.metric_id, fact.company_id):
            raise ValueError("evidence fact/metric/company mismatch")
        if source.source_id != self.source_id or source.company_id != self.company_id:
            raise ValueError("evidence source/company mismatch")
        expected = (expectation.expectation_id, expectation.metric_id, expectation.company_id,
                    expectation.source_id, expectation.source_location,
                    expectation.source_page_or_sheet, expectation.source_cell_or_range)
        actual = (self.expectation_id, self.metric_id, self.company_id, self.source_id,
                  self.source_location, self.source_page_or_sheet, self.source_cell_or_range)
        if actual != expected:
            raise ValueError("evidence must match one document-specific expectation")


@dataclass(frozen=True)
class BridgeComponentFact:
    fact: MetricFact
    bridge_id: str
    component_label: str
    component_order: int
    role: BridgeComponentRole

    def __post_init__(self) -> None:
        if self.component_order < 0:
            raise ValueError("component_order must be non-negative")
        _required(self.component_label, "component_label")
        if not isinstance(self.role, BridgeComponentRole):
            raise TypeError("role must be a BridgeComponentRole")
