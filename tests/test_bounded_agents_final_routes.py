"""Local final-route regressions; no API client or held evaluation runner."""
from decimal import Decimal

import pytest

from scripts.compare_bounded_agents_dev import QUESTIONS
from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents.models import AnalyticsAction
from src.bounded_agents.planner import BoundedIntentPlanner
from src.bounded_agents.policy import analytics_menu, authorize_analytics
from src.bounded_agents.post_synthesis import governed_draft, needs_critic, compose, CompactSynthesis, ContextStatement
from src.orchestration.tools import ToolAuthorizationError
from tests.test_bounded_agents_spike import graph, FACT, BRIDGE, DOCUMENT, assert_closed
from tests.test_bounded_agents_call_budget import COMPARISON, HELPED, HURT, BIGGEST
from tests.test_bounded_agents_post_synthesis import context, feedback


@pytest.mark.parametrize('intent,value',[
    ('What had the biggest impact on', '-602'),
    ('What was the biggest contributor to', '-602'),
    ('Select the largest absolute contribution to', '-602'),
    ('Select the largest positive contributor to', '482'),
    ('Select the biggest positive contributor to', '482'),
    ('Select the largest negative contributor to', '-602'),
    ('Select the most negative contributor to', '-602'),
    ('What helped', '482'), ('What hurt', '-602'),
    ('What helped most', '482'), ('What hurt most', '-602'),
])
def test_ranked_intents_cannot_be_vetoed_by_model_insufficiency(intent,value):
    p=SpikeFixtureProvider({'analytics.choose':{'action':'insufficient'}})
    g=graph(p); b=g.run(f'{intent} Mercedes-Benz Cars adjusted EBIT in Q2 2026?')
    assert b.status.value=='COMPLETED' and b.verification.verdict.value=='PASS'
    assert b.claims[0].value==Decimal(value) and 'Largest' in b.answer
    assert 'analytics.choose' not in p.calls and 'critic' not in p.calls
    assert p.calls==['evidence.choose'] and g.budget.calls<=g.activation.max_calls
    assert any(e.action=='deterministic_contribution_selection' for e in g.agent_trace)
    combined=next(c for c in b.claims if c.value==Decimal('-602'))
    assert 'Volume / structure / net pricing' in combined.text
    assert 'Management attribution is not causal identification.' in b.limitations


@pytest.mark.parametrize('q',[FACT,COMPARISON,HELPED,HURT,BIGGEST,BRIDGE])
def test_route_specific_menus_exclude_premature_insufficient(q):
    g=graph();plan=g.planner.plan(q);executor=g.analytics_tool.executor
    menu=analytics_menu(plan,executor=executor)
    assert AnalyticsAction.INSUFFICIENT not in menu
    if q!=BRIDGE: assert menu==(AnalyticsAction.TASK,)
    else: assert set(menu)=={AnalyticsAction.TASK,AnalyticsAction.LOOKUP,
        AnalyticsAction.RANK_POSITIVE,AnalyticsAction.RANK_NEGATIVE,AnalyticsAction.RECONCILE}
    with pytest.raises(ToolAuthorizationError):authorize_analytics(plan,AnalyticsAction.INSUFFICIENT,executor=executor)


def test_truly_absent_contributions_cannot_release_or_invent_ranking():
    p=SpikeFixtureProvider();g=graph(p);executor=g.analytics_tool.executor
    executor._decomposition=lambda fact:()
    plan=g.planner.plan(BIGGEST)
    assert analytics_menu(plan,executor=executor)==(AnalyticsAction.INSUFFICIENT,)
    assert authorize_analytics(plan,AnalyticsAction.INSUFFICIENT,executor=executor)==AnalyticsAction.INSUFFICIENT
    assert_closed(g.run(BIGGEST));assert p.calls==[]


def test_missing_positive_candidates_are_not_declared_available():
    g=graph();executor=g.analytics_tool.executor;original=executor._decomposition
    executor._decomposition=lambda f:tuple(x for x in original(f) if x.value<0)
    assert analytics_menu(g.planner.plan(HELPED),executor=executor)==(AnalyticsAction.INSUFFICIENT,)
    assert_closed(g.run(HELPED))


def test_full_bridge_keeps_bounded_diagnostic_choice_and_release():
    p=SpikeFixtureProvider({'analytics.choose':{'action':'reconcile'}})
    g=graph(p);b=g.run(BRIDGE)
    assert b.status.value=='COMPLETED' and b.verification.verdict.value=='PASS'
    assert g.observations[0].action.value=='reconcile'
    assert p.calls==['analytics.choose','evidence.choose','synthesis']


@pytest.mark.parametrize('q',[FACT,COMPARISON,HELPED,HURT,BIGGEST])
def test_critic_skips_governed_numbers_without_skipping_verification(q):
    g=graph();b=g.run(q)
    assert b.verification.verdict.value=='PASS'
    assert any(e.role=='critic' and e.status.value=='Skipped' for e in g.agent_trace)
    assert any(e.role=='verifier' and e.verifier_outcome=='PASS' for e in g.agent_trace)


@pytest.mark.parametrize('text',[
    'Management attributes the result to operational execution.',
    'The document contextualizes the reported bridge.',
    'This caused the reported outcome.',
    'This proves future profit growth.',
])
def test_semantic_explanations_require_critic(text):
    p=SpikeFixtureProvider({'synthesis':context(text=text),
        'critic':{'decision':'reject','issues':['unsupported_interpretation'],
            'claim_ids':['claim_009'],'evidence_sufficient':True,'corrections':[]}})
    assert_closed(graph(p).run(BRIDGE));assert 'critic' in p.calls


def test_one_semantic_issue_is_removed_surgically_preserving_all_numbers():
    p=SpikeFixtureProvider({'synthesis':context(text='This caused the outcome.'),
        'critic':feedback('claim_009','causal_overclaim')})
    g=graph(p);b=g.run(BRIDGE);seed=governed_draft(g.last_state['evidence'])
    assert b.status.value=='COMPLETED' and b.verification.verdict.value=='PASS'
    assert b.claims==seed.claims and 'caused' not in b.answer
    assert p.calls.count('synthesis')==p.calls.count('critic')==1
    assert g.release_mode=='surgical_supported_subset'
    assert any(e.role=='surgical_revision' for e in g.agent_trace)


def test_six_original_cases_have_release_capable_local_routes():
    rows=[]
    for q in QUESTIONS:
        p=SpikeFixtureProvider({'analytics.choose':{'action':'insufficient'}})
        g=graph(p);b=g.run(q)
        rows.append((b.status.value,b.verification.verdict.value,g.budget.calls))
        assert g.budget.calls<=g.activation.max_calls
    assert [(s,v) for s,v,c in rows]==[('COMPLETED','PASS')]*6
    assert [c for s,v,c in rows]==[0,0,1,1,1,3]
    # Definition fixture is a truthful limitation, not issuer-definition success.


def test_short_unresolved_biggest_question_does_not_invent_target():
    g=graph();b=g.run('What had the biggest impact?')
    assert b.status.value=='NEEDS_CLARIFICATION' and g.provider.calls==[]


def test_cross_source_definition_quote_requires_semantic_review():
    from scripts.evaluate_bounded_agents_dev import synthetic_units
    text='Organic sales growth excludes currency effects.'
    one=synthetic_units()[0].model_copy(update={'source_id':'mock_one','text':text})
    two=one.model_copy(update={'source_id':'mock_two','evidence_unit_id':'eu_111111111111111111111111'})
    g=graph(units=[one,two]);g.run(DOCUMENT);bundle=g.last_state['evidence']
    bundle=bundle.model_copy(update={'selected_evidence_ids':(one.evidence_unit_id,two.evidence_unit_id)})
    quote=CompactSynthesis(context=(ContextStatement(kind='quote',text=text,
        evidence_ids=(one.evidence_unit_id,two.evidence_unit_id)),))
    assert needs_critic(compose(bundle,quote),bundle)
