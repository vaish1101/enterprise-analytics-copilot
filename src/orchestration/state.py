"""LangGraph state schema and reducers."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from src.analytics.models import AnalyticalResult
from src.planning.models import AnalyticalPlan
from src.retrieval.models import RetrievalResponse

from .models import (
    DecisionBrief,
    EvidenceBundle,
    SynthesisDraft,
    TraceEvent,
    VerificationResult,
    WorkflowRoute,
    WorkflowStatus,
)


class GraphState(TypedDict, total=False):
    run_id: str
    question: str
    question_id: str
    status: WorkflowStatus
    route: WorkflowRoute
    plan: AnalyticalPlan
    analytics: AnalyticalResult | None
    retrieval: RetrievalResponse | None
    evidence: EvidenceBundle
    draft: SynthesisDraft
    verification: VerificationResult
    revision_count: int
    final: DecisionBrief
    traces: Annotated[list[TraceEvent], operator.add]
    prompt_versions: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]

