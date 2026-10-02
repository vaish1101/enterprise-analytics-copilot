"""Closed v2 contracts: decisions are enums/IDs, never executable model prose."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.analytics.models import AnalyticalResult
from src.orchestration.models import TokenUsage


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AnalyticsAction(str, Enum):
    TASK = "task"
    LOOKUP = "lookup"
    RANK_POSITIVE = "rank_positive"
    RANK_NEGATIVE = "rank_negative"
    RECONCILE = "reconcile"
    STOP = "stop"
    INSUFFICIENT = "insufficient"


class AnalyticsInvestigationRequest(Contract):
    action: AnalyticsAction


class AnalyticsObservation(Contract):
    action: AnalyticsAction
    result: AnalyticalResult


class AnalyticsFollowUpDecision(Contract):
    action: AnalyticsAction


class EvidenceSearchStrategy(str, Enum):
    LEXICAL = "lexical"
    DENSE = "dense"
    HYBRID = "hybrid"
    DEFINITION = "definition"


class EvidenceSearchRequest(Contract):
    strategy: EvidenceSearchStrategy


class EvidenceSingleTurnRequest(EvidenceSearchRequest):
    follow_up: EvidenceSearchStrategy | None = Field(default=None,
        description="Optional precommitted different search, only if an unmet coverage gap and unseen in-scope evidence justify it")

    @model_validator(mode="after")
    def distinct_search(self):
        if self.follow_up == self.strategy:
            raise ValueError("Fallback search must be different")
        return self


class EvidenceCoverageAssessment(Contract):
    sufficient: bool
    selected_evidence_ids: tuple[str, ...] = Field(max_length=5)


class EvidenceFollowUpDecision(Contract):
    coverage: EvidenceCoverageAssessment
    follow_up: EvidenceSearchStrategy | None = Field(description="null if coverage is sufficient; otherwise one advertised different strategy or null to stop")

    @model_validator(mode="after")
    def consistent_coverage(self):
        if self.coverage.sufficient and self.follow_up is not None:
            raise ValueError("Sufficient coverage must stop searching")
        return self


class CriticDecision(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"


class CriticIssue(str, Enum):
    CAUSAL_OVERCLAIM = "causal_overclaim"
    MISSING_LIMITATION = "missing_limitation"
    UNSUPPORTED_INTERPRETATION = "unsupported_interpretation"
    MISLEADING_ATTRIBUTION = "misleading_attribution"


class CriticFeedback(Contract):
    decision: CriticDecision
    issues: tuple[CriticIssue, ...] = Field(description="Empty when approving; typed semantic objections otherwise")
    claim_ids: tuple[str, ...] = Field(description="Only disputed existing claims; empty when approving")
    evidence_sufficient: bool

    @model_validator(mode="after")
    def outcome(self):
        if self.decision is CriticDecision.APPROVE and (self.issues or self.claim_ids):
            raise ValueError("approval cannot contain objections")
        if self.decision is not CriticDecision.APPROVE and not self.issues:
            raise ValueError("intervention requires a typed issue")
        return self


class AgentStatus(str, Enum):
    PLANNED = "Planned"
    RUNNING = "Running"
    COMPLETED = "Completed"
    SKIPPED = "Skipped"
    BLOCKED = "Blocked"
    UNKNOWN = "Unknown"


class AgentFailureCategory(str, Enum):
    MALFORMED_OUTPUT = "malformed_output"
    TIMEOUT = "timeout"
    SCHEMA_FAILURE = "schema_failure"
    POLICY_REJECTION = "policy_rejection"
    PROVIDER_FAILURE = "provider_failure"
    BUDGET_EXCEEDED = "budget_exceeded"


class AgentBudgetState(Contract):
    max_calls_per_role: int = Field(default=3, ge=1, le=6)
    max_total_calls: int = Field(default=12, ge=1, le=24)
    max_follow_ups: int = Field(default=1, ge=0, le=1)
    max_retries: int = Field(default=1, ge=0, le=1)
    max_tokens: int = Field(default=24000, ge=1)
    max_input_tokens_per_call: int = Field(default=16000, ge=1)
    max_output_tokens_per_call: int = Field(default=4096, ge=1)
    max_seconds: float = Field(default=30, gt=0, le=120)
    calls: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)


class AgentTraceEvent(Contract):
    version: str = "bounded-agents-trace-0.4"
    role: str
    status: AgentStatus
    action: str | None = None
    tool_requested: str | None = None
    tool_returned: str | None = None
    follow_up_requested: bool = False
    follow_up_denied: bool = False
    critic_outcome: CriticDecision | None = None
    verifier_outcome: str | None = None
    timestamp: datetime
    duration_ms: float = Field(default=0, ge=0)
    elapsed_ms: float = Field(default=0, ge=0)
    remaining_ms: float = Field(default=0, ge=0)
    phase: str | None = None
    model_calls: int = Field(ge=0)
    token_usage: int = Field(ge=0)
    usage: TokenUsage | None = None
    error_category: AgentFailureCategory | None = None
    error_type: str | None = None
    approved_choices: tuple[str, ...] = ()
    decision: dict | None = None
