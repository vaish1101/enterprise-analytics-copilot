"""Menu-to-policy equivalence and sanitized critic diagnostics, no paid calls."""
import json
from types import SimpleNamespace

import pytest

from src.analytics.executor import AnalyticsExecutor
from src.bounded_agents.diagnostics import failure_category
from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents.models import (AnalyticsAction, CriticFeedback, CriticDecision,
    CriticIssue, EvidenceSearchStrategy, EvidenceFollowUpDecision,
    EvidenceCoverageAssessment, AgentBudgetState)
from src.bounded_agents.planner import BoundedIntentPlanner
from src.bounded_agents.policy import (analytics_menu, action_plan, authorize_analytics,
    evidence_menu, authorize_evidence, search_query)
from src.bounded_agents.provider import BudgetedOpenAIProvider, SpendLedger
from src.llm.base import ProviderMalformedOutputError
from src.orchestration.tools import ToolAuthorizationError
from src.planning.models import PlanOperation
from tests.test_bounded_agents_hardening import SDKStub
from tests.test_bounded_agents_spike import graph, FACT, BRIDGE, DOCUMENT, assert_closed


@pytest.mark.parametrize("question", [FACT, BRIDGE,
    "Calculate Henkel sales change from H1 2025 to H1 2026.",
    "What helped Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
    "What hurt Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
    "What had the biggest impact on Mercedes-Benz Cars adjusted EBIT in Q2 2026?"])
def test_every_advertised_analytics_action_executes_under_same_policy(question):
    plan = BoundedIntentPlanner().plan(question); executor = AnalyticsExecutor()
    initial = analytics_menu(plan, executor=executor)
    assert AnalyticsAction.STOP not in initial
    for first in initial:
        if first is AnalyticsAction.INSUFFICIENT:
            assert authorize_analytics(plan, first, executor=executor) is first
            continue
        first_plan = action_plan(plan, first, executor=executor)
        executor.execute(first_plan)
        context = dict(previous=(first,), follow_up=True, remaining=1, executor=executor)
        for action in analytics_menu(plan, **context):
            authorize_analytics(plan, action, **context)
            if action in {AnalyticsAction.STOP, AnalyticsAction.INSUFFICIENT}: continue
            derived = action_plan(plan, action, **context)
            assert (derived.operation, derived.ranking_direction) != (first_plan.operation, first_plan.ranking_direction)
            executor.execute(derived)
        with pytest.raises(ToolAuthorizationError): authorize_analytics(plan, first, **context)


def test_exhausted_followup_menu_has_only_terminal_choices():
    plan = BoundedIntentPlanner().plan(BRIDGE)
    assert set(analytics_menu(plan, follow_up=True, remaining=0)) == {AnalyticsAction.STOP}
    assert evidence_menu(remaining=0) == ()


def test_unexecutable_task_is_not_advertised():
    # A deliberately mis-specified decomposition of a real non-bridge fact.
    plan = BoundedIntentPlanner().plan(FACT).model_copy(update={
        "operation":PlanOperation.DECOMPOSE_VARIANCE, "requires_decomposition":True})
    assert analytics_menu(plan, executor=AnalyticsExecutor()) == (AnalyticsAction.LOOKUP,)
    # The lookup is available, but cannot replace the unavailable bridge anchor.
    with pytest.raises(ToolAuthorizationError): action_plan(plan, AnalyticsAction.TASK, executor=AnalyticsExecutor())


@pytest.mark.parametrize("previous", tuple(EvidenceSearchStrategy))
def test_every_advertised_search_has_the_same_authorization(previous):
    plan = BoundedIntentPlanner().plan(DOCUMENT)
    menu = evidence_menu(previous=(previous,))
    assert previous not in menu
    for strategy in menu:
        assert authorize_evidence(strategy, previous=(previous,)) is strategy
        query = search_query(plan, strategy, menu)
        assert query.company_id == plan.primary_target.company.value
        assert query.metric_ids == (plan.primary_target.metric_id.value,)
    with pytest.raises(ToolAuthorizationError): authorize_evidence(previous, previous=(previous,))


def test_sufficient_coverage_cannot_request_a_search():
    with pytest.raises(ValueError):
        EvidenceFollowUpDecision(coverage=EvidenceCoverageAssessment(sufficient=True,
            selected_evidence_ids=("existing",)), follow_up=EvidenceSearchStrategy.HYBRID)


@pytest.mark.parametrize("error,expected", [
    (ProviderMalformedOutputError("sensitive body"), "malformed_output"),
    (TimeoutError("sensitive body"), "timeout"),
    (ToolAuthorizationError("sensitive body"), "policy_rejection"),
    (RuntimeError("sensitive body"), "provider_failure"),
])
def test_critic_failure_categories_are_captured_without_exception_text(error, expected):
    class Fault(SpikeFixtureProvider):
        def generate_structured(self, **kwargs):
            if kwargs["role"] == "critic": raise error
            return super().generate_structured(**kwargs)
    g = graph(Fault(), AgentBudgetState(max_retries=0)); assert_closed(g.run(DOCUMENT))
    events = [x for x in g.agent_trace if x.role == "critic" and x.error_category]
    assert events and events[-1].error_category.value == expected
    assert "sensitive body" not in json.dumps([x.model_dump(mode="json") for x in g.agent_trace])


def test_critic_schema_and_policy_failures_distinct():
    invalid = CriticFeedback.model_construct(decision=CriticDecision.APPROVE,
        issues=(CriticIssue.MISSING_LIMITATION,), claim_ids=(), evidence_sufficient=True)
    g = graph(SpikeFixtureProvider({"critic":invalid})); assert_closed(g.run(BRIDGE))
    assert any(x.error_category and x.error_category.value == "schema_failure" for x in g.agent_trace)
    invented = CriticFeedback(decision=CriticDecision.REJECT, issues=(CriticIssue.MISSING_LIMITATION,),
        claim_ids=("not_existing",), evidence_sufficient=True)
    g = graph(SpikeFixtureProvider({"critic":invented})); assert_closed(g.run(BRIDGE))
    assert any(x.role == "critic" and x.error_category and x.error_category.value == "policy_rejection" for x in g.agent_trace)


@pytest.mark.parametrize("output,expected", [
    ("not JSON", "malformed_output"),
    ('{"decision":"approve","issues":["missing_limitation"],"claim_ids":[],"evidence_sufficient":true}', "schema_failure"),
])
def test_critic_validation_failure_preserves_known_paid_usage(output, expected):
    stub = SDKStub()
    stub.responses.create = lambda **kwargs: SimpleNamespace(status="completed", output_text=output,
        usage=SimpleNamespace(input_tokens=20, output_tokens=10))
    p = BudgetedOpenAIProvider(model="test", input_rate=1, output_rate=2,
        ledger=SpendLedger(1), client=stub)
    with pytest.raises(Exception) as raised:
        p.generate_structured(role="critic", prompt="test", payload={},
            output_model=CriticFeedback, prompt_version="test")
    assert failure_category(raised.value).value == expected
    assert p.records[0]["status"] == "completed"
    assert p.records[0]["actual_usd"] == "0.00004"
    assert p.failures[0]["error_category"] == expected
