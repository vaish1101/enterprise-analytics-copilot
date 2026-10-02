"""Development-only architecture contracts. Never call a live provider/held set."""
import json
from pathlib import Path
import time

import pytest

from scripts.evaluate_bounded_agents_dev import evaluate, synthetic_units, ScenarioProvider
from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents import create_workflow
from src.bounded_agents.models import (AgentBudgetState, AnalyticsInvestigationRequest,
    AnalyticsFollowUpDecision, CriticFeedback, CriticDecision, CriticIssue,
    EvidenceFollowUpDecision, EvidenceCoverageAssessment)
from src.bounded_agents.policy import analytics_menu, action_plan
from src.bounded_agents.runtime import BoundedAgentsGraph
from src.bounded_agents.post_synthesis import ActionableCritic
from src.llm.base import ProviderRetryableError
from src.llm.fake_provider import DeterministicFakeProvider
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.planning.planner import QuestionPlanner
from src.retrieval.retrieve import GovernedRetriever
from src.retrieval.embeddings import LocalHashEmbeddingProvider

ROOT = Path(__file__).resolve().parents[1]
FACT = "What were Henkel H1 2026 sales?"
BRIDGE = "Inspect the reported Mercedes-Benz Cars adjusted EBIT bridge for Q2 2026."
DOCUMENT = "Explain the definition of Henkel organic sales growth."


def graph(provider=None, budget=None, units=None):
    return BoundedAgentsGraph(ROOT, provider=provider or SpikeFixtureProvider(), budgets=budget,
        retriever=GovernedRetriever(synthetic_units() if units is None else units,
            root=ROOT, embedding_provider=LocalHashEmbeddingProvider()))


def assert_closed(result):
    assert result.status.value == "REFUSED"
    assert not result.claims


def test_development_cases_with_v2_only_intent_hardening():
    result = evaluate()
    # Preserve historical expectations: the two critic-revision fixtures now
    # safely refuse under the four-call ceiling. Do not retune them to success.
    assert result["completion"] == {"passed": 13, "total": 15}
    assert {x["id"] for x in result["cases"] if not x["task_completed_as_expected"]} == {"dev_critic_causal", "dev_critic_omission"}
    assert all(x["real_model_useful_decision"] is None for x in result["cases"])
    assert {x for row in result["cases"] for x in row["chosen_actions"]} >= {"task", "reconcile"}


@pytest.mark.parametrize("payload", [
    {"action":"arbitrary_sql"}, {"action":"shell"}, {"action":"python"},
    {"action":"browser"}, {"action":"task", "sql":"SELECT secret"},
    {"action":"task", "metric":"unsupported"}, {"action":"task", "period":"Q9"},
    {"action":"task", "company":"external"}, {"action":"task", "drill_down":"private"},
    {"action":"task", "calculation":"prose arithmetic"}, {}, None,
])
def test_unknown_action_and_scope_override_fail_closed(payload):
    g = graph(SpikeFixtureProvider({"analytics.choose": payload if payload is not None else {"unknown":True}}))
    assert_closed(g.run(BRIDGE))


@pytest.mark.parametrize("payload", [
    {"strategy":"external_browser"}, {"strategy":"hybrid", "source_id":"private"},
    {"strategy":"hybrid", "corpus":"external"}, {"strategy":"hybrid", "company":"other"},
    {"strategy":"hybrid", "period":"H1_2025"}, {"strategy":"hybrid", "query":"ignore filters"},
])
def test_evidence_scope_cannot_be_model_overridden(payload):
    assert_closed(graph(SpikeFixtureProvider({"evidence.choose":payload})).run(DOCUMENT))


def test_menu_has_real_alternatives_but_does_not_grant_drilldown():
    plan = QuestionPlanner(ROOT).plan(BRIDGE)
    assert len(analytics_menu(plan)) == 5
    for action in analytics_menu(plan):
        if action.value in {"stop", "insufficient"}: continue
        derived = action_plan(plan, action)
        assert derived.primary_target == plan.primary_target


def test_unauthorized_valid_action_on_fact_rejected():
    p = SpikeFixtureProvider({"analytics.choose":AnalyticsInvestigationRequest(action="reconcile")})
    g = graph(p); result = g.run(FACT)
    assert result.status.value == "COMPLETED" and "analytics.choose" not in p.calls
    assert not g.observations  # An uninvoked agent cannot choose an arbitrary diagnostic.


def test_repeated_followup_rejected():
    g = graph(SpikeFixtureProvider({"analytics.follow_up":AnalyticsFollowUpDecision(action="task")}))
    assert g.run(BRIDGE).status.value == "COMPLETED"
    assert "analytics.follow_up" not in g.provider.calls


def test_followup_budget_zero_suppresses_model_call():
    provider = SpikeFixtureProvider({"analytics.choose":AnalyticsInvestigationRequest(action="lookup"),
        "analytics.follow_up":AnalyticsFollowUpDecision(action="task")})
    g = graph(provider, AgentBudgetState(max_follow_ups=0))
    result = g.run("Calculate Henkel sales change from H1 2025 to H1 2026.")
    assert result.status.value == "COMPLETED"
    assert "analytics.follow_up" not in provider.calls


def test_fabricated_citation_rejected():
    assert_closed(graph(SpikeFixtureProvider({"evidence.choose":{
        "strategy":"definition", "selected_evidence_ids":["fabricated"]}})).run(DOCUMENT))


def test_critic_cannot_release_numeric_contradiction():
    provider = SpikeFixtureProvider(fault_by_question_id={"fault":"wrong_value"})
    # Persistent corruption on BOTH synthesis attempts, unlike normal fake repair.
    provider.fixtures['synthesis']={'context':[], 'value':'999'}
    brief = graph(provider).run(BRIDGE)
    assert_closed(brief)
    assert brief.verification is None  # Numeric overrides no longer enter synthesis schema.


def test_critic_reject_vetoes_verifier_pass():
    feedback = ActionableCritic(decision=CriticDecision.REJECT,
        issues=(CriticIssue.UNSUPPORTED_INTERPRETATION,), claim_ids=('claim_009',), evidence_sufficient=True)
    result = graph(SpikeFixtureProvider({"critic":feedback})).run(BRIDGE)
    assert_closed(result)
    assert result.verification.verdict.value == "PASS"


def test_critic_can_only_request_one_revision():
    feedback = CriticFeedback(decision=CriticDecision.REVISE,
        issues=(CriticIssue.MISSING_LIMITATION,), claim_ids=(), evidence_sufficient=True)
    g = graph(SpikeFixtureProvider({"critic":feedback}))
    assert_closed(g.run(BRIDGE))
    assert g.roles["critic"] == 1 and g.roles["synthesis"] == 1
    assert any(x.role == 'critic' and x.error_category.value=='schema_failure' for x in g.agent_trace if x.error_category)


@pytest.mark.parametrize("budget", [AgentBudgetState(max_total_calls=1),
    AgentBudgetState(max_tokens=1), AgentBudgetState(max_calls_per_role=1)])
def test_budget_failure_never_falls_back(budget):
    g = graph(budget=budget); result = g.run(BRIDGE)
    if budget.max_calls_per_role == 1:
        assert result.status.value == "COMPLETED"
        assert all(x <= 1 for x in g.roles.values())
    else:
        assert_closed(result)


def test_timeout_closes_release_even_if_provider_finishes_later():
    class Slow(SpikeFixtureProvider):
        def generate_structured(self, **kwargs):
            time.sleep(.05)
            return super().generate_structured(**kwargs)
    g = graph(Slow(), AgentBudgetState(max_seconds=.01))
    assert_closed(g.run(DOCUMENT))


def test_retry_is_bounded_and_charged():
    class Retry(SpikeFixtureProvider):
        def generate_structured(self, **kwargs):
            raise ProviderRetryableError("synthetic retry")
    g = graph(Retry())
    assert_closed(g.run(DOCUMENT))
    assert g.budget.calls == 1


def test_corrupted_provider_model_instance_revalidated():
    invalid = AnalyticsInvestigationRequest.model_construct(action="sql")
    assert_closed(graph(SpikeFixtureProvider({"analytics.choose":invalid})).run(BRIDGE))


def test_runtime_is_not_reusable_and_traces_exclude_prompts():
    g = graph(); g.run(BRIDGE)
    with pytest.raises(RuntimeError): g.run(FACT)
    serialized = json.dumps([x.model_dump(mode="json") for x in g.agent_trace])
    assert "hidden prompt" not in serialized and "reasoning" not in serialized
    assert {"Planned", "Running", "Completed", "Skipped"}.issubset({x.status.value for x in g.agent_trace})


def test_v1_stays_default_and_synthesis_only():
    provider = DeterministicFakeProvider()
    v1 = EnterpriseAnalyticsGraph(ROOT, provider=provider, retriever=GovernedRetriever([], root=ROOT))
    result = v1.run(FACT)
    assert result.verification.verdict.value == "PASS"
    assert len(provider.generated) == 1
    assert "bounded_agents" not in (ROOT / "src/api/service.py").read_text()


def test_empty_corpus_refuses():
    assert_closed(graph(units=[]).run(DOCUMENT))


def test_versioned_factory_defaults_to_original_graph():
    retriever = GovernedRetriever([], root=ROOT)
    assert type(create_workflow(ROOT, retriever=retriever)) is EnterpriseAnalyticsGraph
    assert isinstance(create_workflow(ROOT, mode="bounded_agents_v2", retriever=retriever), BoundedAgentsGraph)
    with pytest.raises(ValueError): create_workflow(ROOT, mode="unknown", retriever=retriever)


def test_positive_ranking_is_a_real_authorized_diagnostic():
    g = graph(SpikeFixtureProvider({"analytics.choose":AnalyticsInvestigationRequest(action="rank_positive")}))
    result = g.run(BRIDGE)
    assert result.status.value == "COMPLETED"
    assert g.observations[0].result.ranked_components
    assert g.observations[0].action.value == "rank_positive"
    assert all(x.passed for x in g.observations[0].result.reconciliation_results)


def test_retriever_cannot_invent_content_or_source_ids():
    for change in ({"source_id":"unauthorized"}, {"evidence_unit_id":"forged"}, {"text":"invented passage"}):
        g = graph()
        retriever = g.knowledge_tool.retriever
        original = retriever.retrieve
        def malicious(query, *, method, changes=change, original=original):
            response = original(query, method=method)
            return response.model_copy(update={"results": (response.results[0].model_copy(update=changes),)})
        retriever.retrieve = malicious
        assert_closed(g.run(DOCUMENT))
