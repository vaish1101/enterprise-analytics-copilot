from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=1000)
    session_id: str | None = Field(default=None, min_length=8, max_length=100)


class ClaimResponse(BaseModel):
    claim_id: str
    provenance: str
    text: str
    company_id: str | None = None
    metric_id: str | None = None
    business_scope: str | None = None
    periods: list[str] = Field(default_factory=list)
    value: str | None = None
    unit: str | None = None
    fact_ids: list[int] = Field(default_factory=list)
    calculation_run_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class CitationResponse(BaseModel):
    evidence_unit_id: str
    source_id: str
    source_title: str
    official_url: str
    page_number: int
    citation: str
    company_id: str | None = None
    evidence_type: str | None = None
    section: str | None = None


class VerificationResponse(BaseModel):
    verdict: str
    label: str
    supported_claims: int
    total_claims: int
    errors: list[str] = Field(default_factory=list)


class ProvenanceCount(BaseModel):
    provenance: str
    count: int


class ExecutionStage(BaseModel):
    order: int
    label: str
    status: Literal["completed", "skipped", "failed"]
    duration_ms: float | None = None


class ExecutionSummary(BaseModel):
    analytics_used: bool
    retrieval_used: bool
    revision_used: bool
    provider_calls: int
    verifier_interventions: int
    input_tokens: int
    output_tokens: int
    cost_usd: str
    stages: list[ExecutionStage]


class AnalyticsFact(BaseModel):
    """One governed normalized fact, exactly as the deterministic executor used it."""

    fact_id: int
    company_id: str
    metric_id: str
    label: str
    business_scope: str
    period: str
    period_grain: str
    value: str
    unit: str
    provenance: str
    bridge_role: str | None = None
    component_order: int | None = None


class AnalyticsChange(BaseModel):
    kind: Literal["absolute", "percent", "percentage_point"]
    value: str
    unit: str
    calculation_run_id: str | None = None


class RankedComponentResponse(BaseModel):
    rank: int
    fact_id: int
    metric_id: str
    label: str
    value: str
    unit: str
    provenance: str


class ReconciliationResponse(BaseModel):
    rule_id: str
    expected_value: str
    calculated_value: str
    absolute_difference: str
    tolerance: str
    passed: bool
    source_fact_ids: list[int]
    calculation_run_id: str


class AnalyticsResponse(BaseModel):
    """Serialized governed AnalyticalResult. Released only with a COMPLETED answer."""

    operation: str
    primary: AnalyticsFact
    comparison: AnalyticsFact | None = None
    changes: list[AnalyticsChange] = Field(default_factory=list)
    components: list[AnalyticsFact] = Field(default_factory=list)
    supporting: list[AnalyticsFact] = Field(default_factory=list)
    ranked: list[RankedComponentResponse] = Field(default_factory=list)
    reconciliations: list[ReconciliationResponse] = Field(default_factory=list)
    calculation_run_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class FactSourceResponse(BaseModel):
    """Public-safe provenance of a governed numeric fact (never an excerpt)."""

    fact_id: int
    source_id: str
    source_title: str
    official_url: str
    source_type: str
    location: str
    page_or_sheet: str
    cell_or_range: str | None = None
    evidence_type: str


class ClarificationOption(BaseModel):
    """A planner-accepted rewrite of the question that resolves the missing detail."""

    label: str
    detail: str
    question: str


class GovernedAlternative(BaseModel):
    label: str
    question: str


class QueryResponse(BaseModel):
    request_id: str
    session_id: str
    status: str
    route: str
    answer: str
    claims: list[ClaimResponse]
    citations: list[CitationResponse]
    limitations: list[str]
    verification: VerificationResponse | None
    provenance_summary: list[ProvenanceCount]
    execution: ExecutionSummary
    latency_ms: float
    provider: str
    model: str
    clarification_question: str | None = None
    refusal_reason: str | None = None
    analytics: AnalyticsResponse | None = None
    fact_sources: list[FactSourceResponse] = Field(default_factory=list)
    clarification_options: list[ClarificationOption] = Field(default_factory=list)
    alternatives: list[GovernedAlternative] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadinessCheck(BaseModel):
    name: str
    ready: bool
    detail: str


class ReadinessResponse(BaseModel):
    status: str
    checks: list[ReadinessCheck]


class CompanyMetadata(BaseModel):
    id: str
    name: str
    periods: list[str]
    scopes: list[str]


class ExampleGroup(BaseModel):
    category: str
    questions: list[str]


class MetricLabel(BaseModel):
    label: str
    reported_name: str
    unit: str
    company_id: str


class ScopeLabel(BaseModel):
    label: str
    company_id: str
    scope_type: str | None = None


class PeriodLabel(BaseModel):
    company_id: str
    period_id: str
    period_grain: str
    label: str
    fiscal: bool


class CatalogLabels(BaseModel):
    metrics: dict[str, MetricLabel]
    scopes: dict[str, ScopeLabel]
    periods: list[PeriodLabel]


class MetadataResponse(BaseModel):
    system_version: str
    headline: str
    companies: list[CompanyMetadata]
    examples: list[ExampleGroup]
    retrieval_model: str
    retrieval_method: str
    retrieval_version: str
    top_k: int
    graph_version: str
    verifier_version: str
    demo_mode: bool
    rights_notice: str
    labels: CatalogLabels | None = None
    provider_mode: str = "live"


class SessionSummary(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    interaction_count: int
    interactions: list[dict]


class MetricsResponse(BaseModel):
    requests: int
    completed: int
    refused: int
    clarification: int
    errors: int
    revisions: int
    provider_calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: str
    average_latency_ms: float
    route_distribution: dict[str, int]
    verifier_distribution: dict[str, int]
