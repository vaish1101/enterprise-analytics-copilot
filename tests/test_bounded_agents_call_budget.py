"""Route call ceilings, judgment activation and simulated-clock admission."""
from decimal import Decimal
from pathlib import Path
import time

import pytest

from src.bounded_agents.activation import DeadlineReserves
from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents.models import (AgentBudgetState, AnalyticsInvestigationRequest,
    CriticFeedback, EvidenceSingleTurnRequest)
from src.orchestration.models import ClaimType
from tests.test_bounded_agents_spike import graph, FACT, BRIDGE, DOCUMENT, assert_closed
from tests.test_bounded_agents_hardening import provider, SDKStub

COMPARISON = "Calculate the change in Henkel group sales from H1 2025 to H1 2026."
HELPED = "What helped Mercedes-Benz Cars adjusted EBIT in Q2 2026?"
HURT = "What hurt Mercedes-Benz Cars adjusted EBIT in Q2 2026?"
BIGGEST = "What had the biggest impact on Mercedes-Benz Cars adjusted EBIT in Q2 2026?"
HYBRID = "What was Henkel H1 2026 sales according to management?"


class VirtualClock:
    def __init__(self): self.value = time.monotonic()
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds


class TimedFixture(SpikeFixtureProvider):
    def __init__(self, clock, durations=None, fixtures=None):
        super().__init__(fixtures); self.clock = clock; self.durations = durations or {}
        self.counts = {}
    def generate_structured(self, **kwargs):
        role = kwargs["role"]
        self.counts[role] = self.counts.get(role, 0) + 1
        duration = self.durations.get(role, 0)
        if isinstance(duration, tuple): duration = duration[self.counts[role]-1]
        self.clock.advance(duration)
        return super().generate_structured(**kwargs)


def timed_graph(durations=None, fixtures=None, budgets=None):
    clock = VirtualClock(); p = TimedFixture(clock, durations, fixtures)
    g = graph(p, budgets); g.clock = clock
    return g, p, clock


@pytest.mark.parametrize("question,expected,ceiling", [
    (FACT, 0, 2), (COMPARISON, 0, 3), (DOCUMENT, 3, 3),
    ("What did management report about Henkel H1 2026 sales?", 3, 3),
    (BRIDGE, 3, 4), (HELPED, 1, 4), (HURT, 1, 4), (BIGGEST, 1, 4),
    (HYBRID, 2, 4), ("Investigate adjusted EBIT.", 0, 0),
    ("Isolate solely the price contribution to Mercedes-Benz Cars adjusted EBIT in Q2 2026.", 0, 0),
])
def test_exact_normal_calls_and_hard_route_ceiling(question, expected, ceiling):
    g = graph(); g.run(question)
    assert len(g.provider.calls) == expected
    assert g.budget.calls == expected
    assert g.activation.max_calls == ceiling
    assert expected <= ceiling
    assert "analytics.follow_up" not in g.provider.calls
    assert "evidence.coverage" not in g.provider.calls


def test_protected_headroom_skips_optional_analytics_not_canonical_anchor():
    g,p,c = timed_graph()
    # Delay the virtual clock immediately before optional admission.
    original_admit = g._admit
    first = True
    def admit(*args, **kwargs):
        nonlocal first
        if first: c.advance(8); first = False
        return original_admit(*args, **kwargs)
    g._admit = admit
    result = g.run(BRIDGE)
    assert result.status.value == "COMPLETED"
    assert "analytics.choose" not in p.calls
    assert g.last_state["evidence"].analytics.decomposition_components
    assert any(x.role == "analytics.choose" and x.action == "deadline_reserved" for x in g.agent_trace)


def test_low_call_budget_skips_optional_agents_and_never_waives_needed_critic():
    g = graph(budget=AgentBudgetState(max_total_calls=2))
    result = g.run(BRIDGE)
    assert result.status.value == "COMPLETED"
    assert g.provider.calls == ["synthesis"]  # Canonical numeric answer has no semantic risk.
    assert not g.observations
    g = graph(budget=AgentBudgetState(max_total_calls=1))
    assert_closed(g.run(BRIDGE))
    assert g.provider.calls == []
    assert any(x.role == "synthesis" and x.action == "call_budget_reserved" for x in g.agent_trace)


def test_critic_cannot_be_waived_for_deadline():
    g,p,c = timed_graph({"synthesis":25.3})
    # Synthesis is bounded to 25.25 s: an overrun refuses before downstream work.
    assert_closed(g.run(DOCUMENT))
    assert "critic" not in p.calls


def test_critic_admission_skips_then_refuses_if_remaining_time_is_insufficient():
    g,p,c = timed_graph()
    original = g._admit
    def admit(role, **kwargs):
        if role == "critic": c.advance(26)
        return original(role, **kwargs)
    g._admit = admit
    assert_closed(g.run(DOCUMENT))
    assert p.calls == ["evidence.choose","synthesis"]
    assert any(x.role == "critic" and x.action == "deadline_reserved" for x in g.agent_trace)


def test_revision_not_started_when_remaining_time_inadequate():
    g,p,c = timed_graph({"synthesis":13})
    assert_closed(g.run(DOCUMENT))
    assert p.calls.count("synthesis") == 1
    assert 'critic' not in p.calls  # Hard synthesis window prevents unusable downstream work.


def test_unexpected_interpretation_on_fact_requires_critic():
    p = SpikeFixtureProvider({'synthesis':{'context':[{'kind':'interpretation',
        'text':'This proves a causal effect.','evidence_ids':['invented']}]}})
    g=graph(p); assert_closed(g.run(HYBRID))
    assert p.calls==['evidence.choose','synthesis']  # Invented source fails before Critic.


def test_free_text_limitations_on_fact_require_critic_and_budget_fail_closes():
    p=SpikeFixtureProvider({'synthesis':{'context':[], 'limitations':['Causal proof of future returns.']}})
    g=graph(p,AgentBudgetState(max_total_calls=1));assert_closed(g.run(HYBRID))


def test_causal_numeric_prose_requires_critic_and_is_not_released_verbatim():
    p=SpikeFixtureProvider({'synthesis':{'context':[], 'answer':'Sales 10348 prove a causal effect.'}})
    g=graph(p); result=g.run(HYBRID)
    assert "causal" not in result.answer.lower()
    assert_closed(result)  # Arbitrary numeric prose is outside the compact schema.
    assert p.calls == ["evidence.choose", "synthesis"]


@pytest.mark.parametrize("action", ["task","lookup","rank_positive","rank_negative","reconcile"])
def test_single_turn_analytics_has_real_choices_preserving_target(action):
    g = graph(SpikeFixtureProvider({"analytics.choose":AnalyticsInvestigationRequest(action=action)}))
    result = g.run(BRIDGE)
    assert result.status.value == "COMPLETED"
    assert g.observations[0].action.value == action
    assert g.roles["analytics"] == 1 and g.budget.calls == 3
    assert g.observations[0].result.primary_result == g.last_state["evidence"].analytics.primary_result


@pytest.mark.parametrize("strategy", ["definition","hybrid","lexical","dense"])
def test_single_turn_evidence_has_real_governed_choices(strategy):
    g = graph(SpikeFixtureProvider({"evidence.choose":EvidenceSingleTurnRequest(strategy=strategy)}))
    g.run(DOCUMENT)
    assert g.roles["evidence"] == 1 and g.budget.calls == 3
    assert any(x.role == "evidence" and x.action == strategy for x in g.agent_trace)


def test_helped_alias_reuses_equivalent_anchor_biggest_keeps_distinct_anchor():
    g = graph(SpikeFixtureProvider({"analytics.choose":AnalyticsInvestigationRequest(action="rank_positive")}))
    g.run(HELPED)
    assert g.last_state['evidence'].analytics.ranked_components[0].value == Decimal('482')
    assert not g.observations and 'analytics.choose' not in g.provider.calls
    assert g._distinct_observations(g.last_state) == ()
    g = graph(SpikeFixtureProvider({"analytics.choose":AnalyticsInvestigationRequest(action="rank_positive")}))
    g.run(BIGGEST)
    assert g.last_state["evidence"].analytics.ranked_components[0].value == Decimal('-602')
    assert not g.observations and 'analytics.choose' not in g.provider.calls


def test_followup_no_unseen_evidence_suppressed():
    g = graph(SpikeFixtureProvider({"evidence.choose":EvidenceSingleTurnRequest(strategy="definition",follow_up="lexical")}))
    g.run(DOCUMENT)
    assert g.budget.calls == 3
    assert not any(x.follow_up_requested for x in g.agent_trace)


def test_precommitted_followup_executes_only_for_gap_and_unseen_evidence():
    from src.retrieval.models import RetrievalStatus
    g = graph(SpikeFixtureProvider({"evidence.choose":EvidenceSingleTurnRequest(
        strategy="hybrid",follow_up="definition")}))
    retriever = g.knowledge_tool.retriever; original = retriever.retrieve; searches = []
    def search(query, *, method):
        searches.append(method); result = original(query,method=method)
        if len(searches)==1:
            return result.model_copy(update={"results":(),"status":RetrievalStatus.NO_RELEVANT_EVIDENCE})
        return result
    retriever.retrieve = search
    g.run(DOCUMENT)
    assert len(searches)==2 and g.budget.calls==3
    assert any(x.role=="evidence" and x.follow_up_requested for x in g.agent_trace)


def test_precommitted_followup_cannot_spend_protected_completion_time():
    from src.retrieval.models import RetrievalStatus
    g,p,c = timed_graph(fixtures={"evidence.choose":EvidenceSingleTurnRequest(strategy="hybrid",follow_up="definition")})
    retriever=g.knowledge_tool.retriever; original=retriever.retrieve; searches=[]
    def search(query, *, method):
        searches.append(method); result=original(query,method=method)
        c.advance(11.251)
        return result.model_copy(update={"results":(),"status":RetrievalStatus.NO_RELEVANT_EVIDENCE})
    retriever.retrieve=search
    assert_closed(g.run(DOCUMENT))
    assert len(searches)==1
    assert any(x.role=="evidence.follow_up" and x.action=="deadline_reserved" for x in g.agent_trace)


def test_comparison_can_use_one_correctable_critic_revision_within_ceiling():
    p=SpikeFixtureProvider();g=graph(p);result=g.run(COMPARISON)
    assert result.status.value=="COMPLETED"
    assert p.calls==[] and g.budget.calls==0
    assert result.verification.verdict.value=="PASS" and not g.critic_needed


def test_role_subdeadline_overrun_refuses_even_before_global_deadline():
    g,p,c=timed_graph({"analytics.choose":12})
    assert_closed(g.run(BRIDGE))
    assert p.calls==["analytics.choose"] and c()-g.started<30


def test_followup_zero_budget_not_advertised_in_schema():
    g = graph(SpikeFixtureProvider({"evidence.choose":EvidenceSingleTurnRequest(strategy="definition",follow_up="lexical")}),
        AgentBudgetState(max_follow_ups=0))
    assert_closed(g.run(DOCUMENT))
    assert any(x.error_category and x.error_category.value == "schema_failure" for x in g.agent_trace)


def test_conservative_spend_admission_counts_downstream_calls():
    p = provider(SDKStub()); limits = AgentBudgetState()
    worst = (16000*Decimal(1)+4096*Decimal(2))/1000000
    p.ledger.committed_usd = p.ledger.max_usd-2*worst
    assert p.can_reserve_calls(2,limits) and not p.can_reserve_calls(3,limits)
    p.cancel_pending(); assert not p.can_reserve_calls(1,limits)


def test_provider_subdeadline_never_changes_request_deadline():
    p = provider(SDKStub()); limits = AgentBudgetState()
    now = time.monotonic()
    p.generate_bounded(role="analytics.choose",prompt="test",payload={},
        output_model=AnalyticsInvestigationRequest,prompt_version="test",limits=limits,deadline=now+2)
    assert all(x['timeout'] <= 2 for x in p.client.options)
    assert p.deadline > now+2  # Role deadline did not reset/replace whole request.


def test_six_case_forecast_and_slow_synthesis_are_not_live_evaluation():
    from scripts.simulate_bounded_agents_call_budget import simulate
    normal=simulate(); slow=simulate(stress=True)
    assert normal['paid_calls']==slow['paid_calls']==0
    assert [x['call_count'] for x in normal['rows']]==[0,0,1,1,1,3]
    assert all(x['elapsed_s']<30 for x in normal['rows'])
    assert normal['rows'][5]['status']=='REFUSED'
    assert all(x['status']=='COMPLETED' and x['verification']=='PASS' for x in slow['rows'][2:5])
    assert all(x['elapsed_s']<=30 for x in slow['rows'])
    assert not any(x['fallback'] for x in normal['rows']+slow['rows'])
