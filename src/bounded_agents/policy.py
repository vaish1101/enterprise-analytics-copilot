"""Separate narrow investigation capability space. v1 authorizer is unchanged."""
from src.orchestration.tools import ToolAuthorizationError
from src.planning.models import AnalyticalPlan, PlanOperation, RankingDirection
from src.retrieval.models import EvidenceUnitType
from src.retrieval.query import query_from_plan

from .models import AnalyticsAction, EvidenceSearchStrategy


def _candidates(plan: AnalyticalPlan) -> tuple[AnalyticsAction, ...]:
    # Ranking is the resolved governed task, not an invitation to change sign
    # or replace it with a lookup. Fact/comparison also need no diagnostics.
    if plan.operation in {PlanOperation.RANK_CONTRIBUTIONS, PlanOperation.LOOKUP,
            PlanOperation.CALCULATE_CHANGE}:
        return (AnalyticsAction.TASK,)
    actions = [AnalyticsAction.TASK, AnalyticsAction.INSUFFICIENT]
    # Only already resolved decomposition-capable tasks. No metric, scope,
    # period, cross-company or drill-down parameters are accepted from agents.
    if plan.requires_decomposition:
        actions += [AnalyticsAction.LOOKUP, AnalyticsAction.RANK_POSITIVE,
                    AnalyticsAction.RANK_NEGATIVE, AnalyticsAction.RECONCILE]
    elif plan.operation is PlanOperation.CALCULATE_CHANGE:
        actions += [AnalyticsAction.LOOKUP]
    return tuple(actions)


def _derive(plan: AnalyticalPlan, action: AnalyticsAction) -> AnalyticalPlan:
    if action not in _candidates(plan) or action is AnalyticsAction.INSUFFICIENT:
        raise ToolAuthorizationError("Unapproved investigation action")
    operation = {
        AnalyticsAction.TASK: PlanOperation.DECOMPOSE_VARIANCE if plan.operation is PlanOperation.EXPLAIN_WITH_EVIDENCE else plan.operation,
        AnalyticsAction.LOOKUP: PlanOperation.LOOKUP,
        AnalyticsAction.RANK_POSITIVE: PlanOperation.RANK_CONTRIBUTIONS,
        AnalyticsAction.RANK_NEGATIVE: PlanOperation.RANK_CONTRIBUTIONS,
        AnalyticsAction.RECONCILE: PlanOperation.RECONCILE,
    }[action]
    direction = RankingDirection.LARGEST_POSITIVE if action is AnalyticsAction.RANK_POSITIVE else RankingDirection.LARGEST_NEGATIVE if action is AnalyticsAction.RANK_NEGATIVE else plan.ranking_direction if operation is PlanOperation.RANK_CONTRIBUTIONS else None
    # Revalidate, not model_copy: IDs and original target never come from model.
    return AnalyticalPlan.model_validate({**plan.model_dump(), "operation": operation, "ranking_direction": direction})


def _identity(plan, action):
    derived = _derive(plan, action)
    return derived.operation, derived.ranking_direction


def analytics_menu(plan, *, previous=(), follow_up=False, remaining=1, executor=None):
    """The advertised menu IS the execution capability set for this phase."""
    controls = (AnalyticsAction.STOP,) if follow_up else ()
    if follow_up and remaining <= 0:
        return controls
    used = {_identity(plan, action) for action in previous}
    allowed = []
    for action in _candidates(plan):
        if action is AnalyticsAction.INSUFFICIENT:
            continue
        try:
            derived = _derive(plan, action)
            if _identity(plan, action) in used:
                continue
            if executor is not None:
                target = derived.primary_target
                if target is None or target.period is None or target.business_scope is None:
                    continue
                primary = executor.facts.get(target.company, target.metric_id, target.business_scope, target.period)
                if primary.period_grain is not target.period_grain:
                    continue
                if derived.operation is PlanOperation.CALCULATE_CHANGE:
                    comparison = executor.facts.get(target.company, target.metric_id, target.business_scope, target.comparison_period)
                    if comparison.period_grain is not primary.period_grain:
                        continue
                if derived.requires_decomposition and derived.operation is not PlanOperation.LOOKUP:
                    components = executor._decomposition(primary)
                    if not components or any(x.company != primary.company or x.business_scope != primary.business_scope or x.period != primary.period for x in components):
                        continue
                    if derived.operation is PlanOperation.RANK_CONTRIBUTIONS:
                        if derived.ranking_direction is RankingDirection.LARGEST_POSITIVE and not any(x.value > 0 for x in components):
                            continue
                        if derived.ranking_direction is RankingDirection.LARGEST_NEGATIVE and not any(x.value < 0 for x in components):
                            continue
            allowed.append(action)
        except (ValueError, LookupError, ToolAuthorizationError):
            continue
    if not allowed:
        return (*controls, AnalyticsAction.INSUFFICIENT) if not follow_up else controls
    return (*allowed, *controls)


def authorize_analytics(plan, action, **context):
    if action not in analytics_menu(plan, **context):
        raise ToolAuthorizationError("Action not offered by current capability set")
    return action


def action_plan(plan, action, **context):
    authorize_analytics(plan, action, **context)
    return _derive(plan, action)


def evidence_menu(*, previous=(), remaining=1):
    if remaining <= 0:
        return ()
    return tuple(x for x in EvidenceSearchStrategy if x not in previous)


def authorize_evidence(strategy, *, previous=(), remaining=1):
    if strategy not in evidence_menu(previous=previous, remaining=remaining):
        raise ToolAuthorizationError("Search not offered by current capability set")
    return strategy


def search_query(plan, strategy, allowed_strategies):
    if strategy not in allowed_strategies:
        raise ToolAuthorizationError("Unapproved search strategy")
    query = query_from_plan(plan)
    if strategy is EvidenceSearchStrategy.DEFINITION:
        query = query.model_copy(update={"preferred_evidence_types": (EvidenceUnitType.METRIC_DEFINITION,)})
    return query.model_copy(update={"top_k": 5})


def check_results(query, response, source_ids):
    for item in response.results:
        if (item.source_id not in source_ids or item.company_id != query.company_id
            or not set(query.reporting_periods).issubset(item.reporting_periods)
            or query.business_scopes and not set(query.business_scopes).intersection(item.business_scopes)
            or not set(query.metric_ids).intersection(item.metric_ids)):
            raise ToolAuthorizationError("Evidence escaped pinned scope/source policy")
