"""Typed, plan-authorized adapters over the locked Step 4 and Step 5 layers."""

from __future__ import annotations

from pathlib import Path

from src.analytics.executor import AnalyticsExecutor
from src.analytics.models import AnalyticalResult
from src.planning.models import AnalyticalPlan, PlanOperation, PlanningStatus, QuestionType
from src.retrieval.models import RetrievalResponse
from src.retrieval.query import query_from_plan
from src.retrieval.retrieve import GovernedRetriever

from .models import ToolId


_ANALYTICS_TOOL = {
    PlanOperation.LOOKUP: ToolId.ANALYTICS_LOOKUP,
    PlanOperation.CALCULATE_CHANGE: ToolId.ANALYTICS_CHANGE,
    PlanOperation.DECOMPOSE_VARIANCE: ToolId.ANALYTICS_DECOMPOSE,
    PlanOperation.RANK_CONTRIBUTIONS: ToolId.ANALYTICS_RANK,
    PlanOperation.RECONCILE: ToolId.ANALYTICS_RECONCILE,
    PlanOperation.EXPLAIN_WITH_EVIDENCE: ToolId.ANALYTICS_DECOMPOSE,
}


class ToolAuthorizationError(PermissionError):
    pass


class ToolAuthorizer:
    @staticmethod
    def allowed(plan: AnalyticalPlan) -> frozenset[ToolId]:
        if plan.status is not PlanningStatus.READY:
            return frozenset()
        tools: set[ToolId] = set()
        if plan.operation in _ANALYTICS_TOOL:
            tools.add(_ANALYTICS_TOOL[plan.operation])
        if (
            plan.question_type in {QuestionType.DOCUMENT_CONTEXT, QuestionType.HYBRID_ANALYSIS}
            or plan.operation in {
                PlanOperation.DEFINE_METRIC, PlanOperation.RETRIEVE_CONTEXT,
                PlanOperation.EXPLAIN_WITH_EVIDENCE, PlanOperation.DECOMPOSE_VARIANCE,
                PlanOperation.RANK_CONTRIBUTIONS, PlanOperation.RECONCILE,
            }
        ):
            tools.add(ToolId.KNOWLEDGE_RETRIEVE)
        return frozenset(tools)

    @classmethod
    def require(cls, plan: AnalyticalPlan, tool_id: ToolId) -> None:
        if tool_id not in cls.allowed(plan):
            raise ToolAuthorizationError(f"{tool_id.value} is not authorized by plan operation {plan.operation.value}")


class GovernedAnalyticsTool:
    def __init__(self, root: Path):
        self.executor = AnalyticsExecutor(root)

    def invoke(self, plan: AnalyticalPlan, tool_id: ToolId) -> AnalyticalResult:
        ToolAuthorizer.require(plan, tool_id)
        expected = _ANALYTICS_TOOL.get(plan.operation)
        if tool_id is not expected:
            raise ToolAuthorizationError(f"plan authorizes {expected}, not {tool_id}")
        return self.executor.execute(plan)


class GovernedKnowledgeTool:
    def __init__(self, retriever: GovernedRetriever, *, method: str = "dense"):
        self.retriever = retriever
        self.method = method

    def invoke(self, plan: AnalyticalPlan, tool_id: ToolId) -> RetrievalResponse:
        ToolAuthorizer.require(plan, tool_id)
        query = query_from_plan(plan).model_copy(update={"top_k": 5})
        return self.retriever.retrieve(query, method=self.method)
