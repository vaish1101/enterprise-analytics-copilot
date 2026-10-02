"""V2-only activation/admission policy. No numerical or retrieval authority."""
from dataclasses import dataclass
import re

from src.orchestration.models import ClaimType, WorkflowRoute
from src.planning.models import PlanOperation


@dataclass(frozen=True)
class RouteActivation:
    family: str
    analytics: bool
    evidence: bool
    semantic_review: bool
    max_calls: int


@dataclass(frozen=True)
class DeadlineReserves:
    # Compact context-only output has a 12 s hard window, not a latency SLA.
    # Third-run completed critics reached 6.366 s; allow 7 s with margin.
    # These are conservative admission estimates, NOT provider latency promises.
    synthesis: float = 12.0
    critic: float = 7.0
    revision: float = .25
    verification: float = .25
    investigation_call: float = 3.0


def activation(plan, route):
    if route in {WorkflowRoute.NEEDS_CLARIFICATION, WorkflowRoute.UNSUPPORTED}:
        return RouteActivation("short_circuit", False, False, False, 0)
    if route is WorkflowRoute.ANALYTICS_ONLY:
        comparison = plan.operation is PlanOperation.CALCULATE_CHANGE
        return RouteActivation("comparison" if comparison else "fact", False, False,
            False, 3 if comparison else 2)
    if route is WorkflowRoute.KNOWLEDGE_ONLY:
        return RouteActivation("definition" if plan.operation is PlanOperation.DEFINE_METRIC
            else "documentary", False, True, True, 3)
    return RouteActivation("driver" if plan.requires_decomposition else "hybrid",
        plan.requires_decomposition, True, True, 4)


def critic_required(policy, draft, bundle):
    from .post_synthesis import needs_critic
    return needs_critic(draft, bundle)
