"""Strict public contracts for the Step 6 agentic layer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.analytics.models import AnalyticalResult
from src.planning.models import AnalyticalPlan
from src.retrieval.models import EvidenceResult, RetrievalResponse


class WorkflowRoute(str, Enum):
    ANALYTICS_ONLY = "ANALYTICS_ONLY"
    KNOWLEDGE_ONLY = "KNOWLEDGE_ONLY"
    HYBRID = "HYBRID"
    DECOMPOSITION_EXPLANATION = "DECOMPOSITION_EXPLANATION"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED = "UNSUPPORTED"


class WorkflowStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    PLANNED = "PLANNED"
    ROUTED = "ROUTED"
    EVIDENCE_READY = "EVIDENCE_READY"
    DRAFTED = "DRAFTED"
    VERIFYING = "VERIFYING"
    REVISING = "REVISING"
    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    FAILED = "FAILED"


class ToolId(str, Enum):
    ANALYTICS_LOOKUP = "analytics.lookup"
    ANALYTICS_CHANGE = "analytics.calculate_change"
    ANALYTICS_DECOMPOSE = "analytics.decompose_variance"
    ANALYTICS_RANK = "analytics.rank_contributions"
    ANALYTICS_RECONCILE = "analytics.reconcile"
    KNOWLEDGE_RETRIEVE = "knowledge.retrieve_top5"


class ClaimType(str, Enum):
    REPORTED = "REPORTED"
    CALCULATED = "CALCULATED"
    MANAGEMENT_ATTRIBUTED = "MANAGEMENT_ATTRIBUTED"
    INTERPRETATION = "INTERPRETATION"
    LIMITATION = "LIMITATION"


class ClaimSupport(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONFLICTING = "CONFLICTING"


class VerificationVerdict(str, Enum):
    PASS = "PASS"
    NEEDS_REVISION = "NEEDS_REVISION"
    REFUSE = "REFUSE"


class TokenUsage(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: Decimal = Field(ge=0)


class TraceEvent(BaseModel):
    """Operational trace only. Reasoning and hidden chain-of-thought are excluded."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    sequence: int = Field(ge=1)
    node: str
    event: str
    started_at: datetime
    duration_ms: float = Field(ge=0)
    tool_id: ToolId | None = None
    input_ids: tuple[str, ...] = ()
    output_ids: tuple[str, ...] = ()
    usage: TokenUsage | None = None
    provider_call: bool = False
    provider_name: str | None = None
    provider_model: str | None = None
    prompt_version: str | None = None
    retry_number: int = Field(default=0, ge=0)
    fact_ids: tuple[int, ...] = ()
    calculation_run_ids: tuple[str, ...] = ()
    verifier_verdict: VerificationVerdict | None = None
    error_code: str | None = None


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    question_id: str
    plan: AnalyticalPlan
    analytics: AnalyticalResult | None = None
    retrieval: RetrievalResponse | None = None
    selected_evidence_ids: tuple[str, ...] = ()
    conflict_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence_ids_are_retrieved(self) -> "EvidenceBundle":
        available = {item.evidence_unit_id for item in self.retrieval.results} if self.retrieval else set()
        if not set(self.selected_evidence_ids).issubset(available):
            raise ValueError("selected evidence must be a subset of retrieved top-k evidence")
        if len(self.selected_evidence_ids) > 5:
            raise ValueError("at most five document evidence units may be selected")
        return self


class Claim(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    claim_id: str = Field(pattern=r"^claim_[0-9]{3}$")
    claim_type: ClaimType
    text: str = Field(min_length=1)
    company_id: str | None = None
    metric_id: str | None = None
    business_scope: str | None = None
    periods: tuple[str, ...] = ()
    value: Decimal | None = None
    unit: str | None = None
    fact_ids: tuple[int, ...] = ()
    calculation_run_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def lineage_contract(self) -> "Claim":
        if self.claim_type is ClaimType.CALCULATED and not self.calculation_run_ids:
            raise ValueError("CALCULATED claims require calculation lineage")
        if self.claim_type is ClaimType.REPORTED and self.value is not None and not self.fact_ids:
            raise ValueError("numeric REPORTED claims require fact lineage")
        if self.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED and not (self.fact_ids or self.evidence_ids):
            raise ValueError("management attribution requires source lineage")
        return self


class SynthesisDraft(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    draft_id: str
    question_id: str
    answer: str
    claims: tuple[Claim, ...]
    limitations: tuple[str, ...] = ()
    revision_number: int = Field(default=0, ge=0, le=1)


class ClaimCheck(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    claim_id: str
    support: ClaimSupport
    errors: tuple[str, ...] = ()


class VerificationResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    verification_id: str
    verdict: VerificationVerdict
    claim_checks: tuple[ClaimCheck, ...]
    errors: tuple[str, ...] = ()
    supported_claim_ids: tuple[str, ...] = ()


class CitationRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    evidence_unit_id: str
    source_id: str
    source_title: str
    official_url: str
    page_number: int
    citation: str


class DecisionBrief(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    run_id: str
    question_id: str
    status: WorkflowStatus
    route: WorkflowRoute
    answer: str
    claims: tuple[Claim, ...] = ()
    verification: VerificationResult | None = None
    clarification_question: str | None = None
    refusal_reason: str | None = None
    limitations: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    citations: tuple[CitationRecord, ...] = ()
    fact_ids: tuple[int, ...] = ()
    calculation_run_ids: tuple[str, ...] = ()
    trace: tuple[TraceEvent, ...]
    provider_name: str
    provider_model: str
    prompt_versions: tuple[str, ...]
    total_usage: TokenUsage


class ProviderResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    value: Any
    usage: TokenUsage
    provider_name: str
    provider_model: str
    prompt_version: str
