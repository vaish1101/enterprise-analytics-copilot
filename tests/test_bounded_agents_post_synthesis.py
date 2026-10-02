"""Offline release, numerical authority, semantic gating and surgical edits."""
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from src.bounded_agents.models import AgentBudgetState
from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents.post_synthesis import (ActionableCritic, CompactSynthesis,
    ContextStatement, governed_draft, compose, needs_critic, surgical_patch, compact_payload, SAFE_LIMITATIONS)
from src.orchestration.numerical_prose import numerical_prose_matches
from src.orchestration.verifier import DeterministicVerifier
from scripts.evaluate_bounded_agents_dev import synthetic_units
from tests.test_bounded_agents_spike import graph,FACT,BRIDGE,DOCUMENT,assert_closed
from tests.test_bounded_agents_call_budget import HELPED,HURT,BIGGEST,COMPARISON,timed_graph


def context(kind='interpretation',text='Reporting context is limited.'):
    return CompactSynthesis(context=(ContextStatement(kind=kind,text=text,
        evidence_ids=(synthetic_units()[2].evidence_unit_id,)),))


def feedback(claim_id,issue='unsupported_interpretation',operation='drop_claim',evidence_id=None):
    return ActionableCritic(decision='revise',issues=(issue,),claim_ids=(claim_id,),
        evidence_sufficient=True,corrections=({'claim_id':claim_id,'issue':issue,
            'operation':operation,'evidence_id':evidence_id},))


@pytest.mark.parametrize('q,first',[(HELPED,Decimal(482)),(HURT,Decimal(-602)),(BIGGEST,Decimal(-602))])
def test_realistic_driver_releases_ranked_canonical_result(q,first):
    g=graph();b=g.run(q)
    assert b.status.value=='COMPLETED' and b.verification.verdict.value=='PASS'
    assert b.claims[0].value==first and 'Largest' in b.answer
    combined=next(c for c in b.claims if c.value==Decimal(-602))
    assert 'Volume / structure / net pricing' in combined.text
    assert all(c.claim_type.value=='MANAGEMENT_ATTRIBUTED' for c in b.claims if c.metric_id.startswith('mercedes_bridge_'))
    assert 'Management attribution is not causal identification.' in b.limitations
    assert g.provider.calls==['evidence.choose']
    assert any(e.role=='critic' and e.status.value=='Skipped' for e in g.agent_trace)


@pytest.mark.parametrize('q',[BRIDGE])
def test_compact_wire_has_no_numeric_authority_and_verifier_always_runs(q):
    class Capture(SpikeFixtureProvider):
        def generate_structured(self,**kw):
            if kw['role']=='synthesis':self.payload=kw['payload'];self.output=kw['output_model']
            return super().generate_structured(**kw)
    p=Capture();g=graph(p);b=g.run(q)
    assert p.output is CompactSynthesis
    assert set(p.output.model_fields)=={'context'}
    assert not {'trace','evidence_bundle','investigation_observations'}&set(p.payload)
    assert b.verification.verdict.value=='PASS'
    assert not g.critic_needed


def test_signed_change_exact_percent_and_lineage_are_governed():
    g=graph();b=g.run(COMPARISON)
    change=next(c for c in b.claims if c.unit=='EUR_million' and c.claim_type.value=='CALCULATED')
    percent=next(c for c in b.claims if c.unit=='percent')
    assert change.value==Decimal(-54) and percent.value==Decimal('-0.5191309363583926168044606806')
    assert change.calculation_run_ids and set(change.fact_ids)=={3,4}
    assert str(percent.value) in percent.text and 'approximately' not in percent.text
    assert b.verification.verdict.value=='PASS'


@pytest.mark.parametrize('text,values,units,expected',[
    ('Reported 482 EUR_million.',{Decimal(482)},{'EUR_million'},True),
    ('Reported -602 EUR_million.',{Decimal(-602)},{'EUR_million'},True),
    ('Volume / structure / net pricing: -602 EUR_million.',{Decimal(-602)},{'EUR_million'},True),
    ('Absolute change -54 EUR_million.',{Decimal(-54)},{'EUR_million'},True),
    ('Sales decreased by EUR 54 million.',{Decimal(-54)},{'EUR_million'},False),
    ('Change -0.5191309363583926168044606806 percent.',{Decimal('-0.5191309363583926168044606806')},{'percent'},True),
    ('Change approximately -0.52%.',{Decimal('-0.5191309363583926168044606806')},{'percent'},False),
    ('Sales were 999 EUR million.',{Decimal(10348)},{'EUR_million'},False),
])
def test_shared_numerical_validator_not_relaxed(text,values,units,expected):
    assert numerical_prose_matches(text,values,units) is expected


@pytest.mark.parametrize('field',['value','unit','fact_ids','calculation_run_ids','company','periods','answer','limitations'])
def test_model_cannot_supply_or_override_numeric_or_governance_fields(field):
    p=SpikeFixtureProvider({'synthesis':{'context':[],field:'override'}})
    assert_closed(graph(p).run(BRIDGE))


@pytest.mark.parametrize('text',['This proves a causal effect.','This caused profit.','Future EBIT will grow.'])
def test_semantic_risk_invokes_critic_and_nominal_approval_does_not_release(text):
    p=SpikeFixtureProvider({'synthesis':context(text=text)})
    g=graph(p);assert_closed(g.run(BRIDGE));assert 'critic' in p.calls


def test_exact_definition_quote_can_skip_critic_but_not_verifier():
    unit=synthetic_units()[0].model_copy(update={'source_type':'mock_document','source_id':'mock_definition',
        'text':'Organic sales growth excludes currency and acquisition effects.'})
    p=SpikeFixtureProvider({'synthesis':CompactSynthesis(context=(ContextStatement(kind='quote',
        text=unit.text,evidence_ids=(unit.evidence_unit_id,)),))})
    g=graph(p,units=[unit]);b=g.run(DOCUMENT)
    assert b.status.value=='COMPLETED' and b.verification.verdict.value=='PASS'
    assert p.calls==['evidence.choose','synthesis']


def test_synthetic_definition_tag_is_not_enough_to_skip_critic():
    g=graph();g.run(DOCUMENT)
    assert 'critic' in g.provider.calls


@pytest.mark.parametrize('bad',[{'decision':'revise','issues':['missing_limitation'],'claim_ids':[],'evidence_sufficient':True},
    {'decision':'reject','issues':['unsupported_interpretation'],'claim_ids':[],'evidence_sufficient':False},
    {'decision':'approve','issues':[],'claim_ids':[],'evidence_sufficient':True,'corrections':[{'claim_id':'claim_009','issue':'unsupported_interpretation','operation':'drop_claim','evidence_id':None}]}])
def test_critic_vague_or_inconsistent_correction_fails_closed(bad):
    with pytest.raises(ValueError):ActionableCritic.model_validate(bad)


def test_surgical_numeric_restoration_changes_only_flagged_claim():
    g=graph();g.run(BRIDGE);bundle=g.last_state['evidence'];d=governed_draft(bundle)
    bad=d.claims[0].model_copy(update={'value':Decimal(999),'text':'Reported 999 EUR_million.'})
    faulty=d.model_copy(update={'claims':(bad,*d.claims[1:]),'answer':' '.join(c.text for c in (bad,*d.claims[1:]))})
    assert DeterministicVerifier().verify(faulty,bundle).verdict.value!='PASS'
    fixed=surgical_patch(faulty,bundle,feedback(bad.claim_id,'misleading_attribution','restore_numeric'))
    assert fixed.claims==d.claims and fixed.claims[1:]==faulty.claims[1:]
    assert DeterministicVerifier().verify(fixed,bundle).verdict.value=='PASS'


def test_runtime_internal_numeric_fault_gets_one_exact_correction():
    p=SpikeFixtureProvider({'critic':feedback('claim_001','misleading_attribution','restore_numeric')})
    g=graph(p);original=g._generate
    def fault(state,*,revision):
        update=original(state,revision=revision)
        d=update['draft'];c=d.claims[0].model_copy(update={'value':Decimal(999),'text':'Reported 999 EUR_million.'})
        update['draft']=d.model_copy(update={'claims':(c,*d.claims[1:]),'answer':' '.join(x.text for x in (c,*d.claims[1:]))})
        return update
    g._generate=fault;b=g.run(FACT)
    assert b.verification.verdict.value=='PASS' and b.claims[0].value==Decimal(10348)
    assert p.calls==['critic']
    assert g.last_state['revision_count']==1


def test_runtime_missing_limitation_gets_surgical_restoration():
    p=SpikeFixtureProvider({'synthesis':CompactSynthesis(context=()),
        'critic':feedback('claim_001','missing_limitation','add_limitation')})
    g=graph(p);original=g._generate
    def fault(state,*,revision):
        update=original(state,revision=revision)
        update['draft']=update['draft'].model_copy(update={'limitations':()})
        return update
    g._generate=fault;b=g.run(BRIDGE)
    assert b.verification.verdict.value=='PASS' and SAFE_LIMITATIONS[0] in b.limitations
    assert p.calls==['analytics.choose','evidence.choose','synthesis','critic']


def test_surgical_attribution_drop_only_removes_flagged_context_no_model_revision():
    p=SpikeFixtureProvider({'synthesis':context(text='This caused the outcome.'),
        'critic':feedback('claim_009','causal_overclaim')})
    g=graph(p);b=g.run(BRIDGE)
    assert b.status.value=='COMPLETED' and b.verification.verdict.value=='PASS'
    assert 'caused' not in b.answer
    assert p.calls.count('synthesis')==p.calls.count('critic')==1
    assert len(b.claims)==8 and any(e.role=='surgical_revision' for e in g.agent_trace)


def test_surgical_citation_rebind_requires_exact_selected_quote():
    unit=synthetic_units()[0];g=graph();g.run(DOCUMENT);bundle=g.last_state['evidence']
    d=compose(bundle,CompactSynthesis(context=(ContextStatement(kind='quote',text=unit.text,evidence_ids=(unit.evidence_unit_id,)),)))
    c=d.claims[0].model_copy(update={'evidence_ids':('eu_invented',)})
    faulty=d.model_copy(update={'claims':(c,)})
    fixed=surgical_patch(faulty,bundle,feedback(c.claim_id,'misleading_attribution','rebind_quote',unit.evidence_unit_id))
    assert fixed.claims[0].text==c.text and fixed.claims[0].evidence_ids==(unit.evidence_unit_id,)
    assert DeterministicVerifier().verify(fixed,bundle).verdict.value=='PASS'
    with pytest.raises(ValueError):surgical_patch(faulty,bundle,feedback(c.claim_id,'misleading_attribution','rebind_quote','eu_invented'))


def test_missing_limitation_is_restored_without_touching_claims():
    g=graph();g.run(BRIDGE);bundle=g.last_state['evidence'];seed=governed_draft(bundle)
    faulty=seed.model_copy(update={'limitations':()})
    assert needs_critic(faulty,bundle)
    fixed=surgical_patch(faulty,bundle,feedback(seed.claims[0].claim_id,'missing_limitation','add_limitation'))
    assert fixed.claims==seed.claims and fixed.limitations==seed.limitations
    assert not needs_critic(fixed,bundle)
    with pytest.raises(ValueError):surgical_patch(seed,bundle,feedback(seed.claims[0].claim_id,'missing_limitation','add_limitation'))


def test_partial_semantic_repair_exposes_numeric_subset_not_full_agent_success():
    extra=CompactSynthesis(context=(context(text='First unsupported context.').context[0],
        context(text='Other interpretation remains.').context[0]))
    p=SpikeFixtureProvider({'synthesis':extra,'critic':feedback('claim_009')})
    g=graph(p);b=g.run(BRIDGE)
    assert b.verification.verdict.value=='PASS' and b.status.value=='COMPLETED'
    assert b.refusal_reason=='supported_numeric_subset' and g.release_mode=='supported_numeric_subset'
    assert len(b.claims)==8 and 'Other interpretation' not in b.answer
    assert any(e.role=='release.subset' for e in g.agent_trace)


def test_wrong_citation_and_nonexact_quote_fail_before_semantic_review():
    for out in [CompactSynthesis(context=(ContextStatement(kind='quote',text='Invented definition.',evidence_ids=(synthetic_units()[0].evidence_unit_id,)),)),
        CompactSynthesis(context=(ContextStatement(kind='interpretation',text='Unknown source.',evidence_ids=('eu_unknown',)),))]:
        g=graph(SpikeFixtureProvider({'synthesis':out}));assert_closed(g.run(DOCUMENT))
        assert 'critic' not in g.provider.calls


def test_required_critic_budget_is_not_waived():
    p=SpikeFixtureProvider({'synthesis':context()});g=graph(p,AgentBudgetState(max_total_calls=1))
    assert_closed(g.run(BRIDGE));assert 'critic' not in p.calls


def test_synthesis_and_critic_have_smaller_output_caps_and_fixed_windows():
    class Capture(SpikeFixtureProvider):
        def __init__(self):super().__init__({'synthesis':context()});self.options=[]
        def generate_bounded(self,limits,deadline,**kw):
            self.options.append((kw['role'],limits.max_output_tokens_per_call,deadline))
            return self.generate_structured(**kw)
    p=Capture();g=graph(p);b=g.run(BRIDGE)
    assert b.verification.verdict.value=='PASS'
    assert [(role,cap) for role,cap,_ in p.options if role in ('synthesis','critic')]==[('synthesis',1024),('critic',768)]
    assert g.budget.max_seconds==30 and all(d<=g.started+30 for _,_,d in p.options)


def test_surgical_revision_reserve_not_spent_on_provider_regeneration():
    p=SpikeFixtureProvider({'synthesis':context(),'critic':feedback('claim_009')})
    g=graph(p);g.run(BRIDGE)
    assert p.calls==['analytics.choose','evidence.choose','synthesis','critic']
    assert g.roles['synthesis']==1 and g.roles['critic']==1
    assert g.last_state['revision_count']==1


def test_patch_unknown_claim_operation_and_unsafe_drop_fail_closed():
    g=graph();g.run(BRIDGE);bundle=g.last_state['evidence'];d=governed_draft(bundle)
    for f in [feedback('claim_999'),feedback('claim_001')]:
        with pytest.raises(ValueError):surgical_patch(d,bundle,f)


def test_context_size_cap_is_enforced():
    with pytest.raises(ValueError):context(text='x'*481)
    with pytest.raises(ValueError):CompactSynthesis(context=(context().context[0],)*4)


def test_late_compact_synthesis_cannot_release_or_trigger_critic():
    g,p,_=timed_graph({'synthesis':12.1})
    assert_closed(g.run(BRIDGE));assert 'critic' not in p.calls


def test_compact_payload_preserves_required_source_text_and_lineage():
    g=graph();g.run(BRIDGE);bundle=g.last_state['evidence'];p=compact_payload(bundle)
    assert p['documents'][0]['text']==synthetic_units()[2].text
    assert p['documents'][0]['hash']==synthetic_units()[2].content_hash
    assert all(c['fact_ids'] and c['evidence_ids'] for c in p['numeric_claims'])
    assert 'trace' not in json.dumps(p)


def test_actual_budget_adapter_sends_caps_strict_compact_schema_and_no_reasoning_change():
    from tests.test_bounded_agents_hardening import SDKStub,provider
    from src.bounded_agents.models import EvidenceSingleTurnRequest,AnalyticsInvestigationRequest
    stub=SDKStub()
    def parse(**kw):
        stub.requests.append(kw)
        model=kw['text_format']
        parsed=context() if model is CompactSynthesis else EvidenceSingleTurnRequest(strategy='hybrid') if issubclass(model,EvidenceSingleTurnRequest) else AnalyticsInvestigationRequest(action='task')
        return SimpleNamespace(status='completed',output_parsed=parsed,usage=SimpleNamespace(input_tokens=20,output_tokens=10))
    def create(**kw):
        stub.requests.append(kw)
        return SimpleNamespace(status='completed',output_text=ActionableCritic(decision='approve',issues=(),claim_ids=(),evidence_sufficient=True).model_dump_json(),usage=SimpleNamespace(input_tokens=20,output_tokens=10))
    stub.responses.parse=parse;stub.responses.create=create
    p=provider(stub);g=graph(p);b=g.run(BRIDGE)
    assert b.verification.verdict.value=='PASS'
    assert [x['max_output_tokens'] for x in stub.requests]==[4096,4096,1024,768]
    assert all(x['store'] is False and x['service_tier']=='default' and 'reasoning' not in x for x in stub.requests)
    assert all(x['max_retries']==0 for x in stub.options)
    assert 'context' in stub.count_requests[2]['text']['format']['schema']['properties']


def test_incomplete_compact_response_is_not_released_and_known_usage_is_accounted():
    from tests.test_bounded_agents_hardening import SDKStub,provider
    stub=SDKStub()
    stub.responses.parse=lambda **kw:SimpleNamespace(status='incomplete',output_parsed=CompactSynthesis(context=()),
        usage=SimpleNamespace(input_tokens=20,output_tokens=10))
    p=provider(stub)
    with pytest.raises(Exception):
        p.generate_bounded(role='synthesis',prompt='test',payload={},output_model=CompactSynthesis,
            prompt_version='post-synthesis',limits=AgentBudgetState(max_output_tokens_per_call=1024),deadline=None)
    assert p.records[0]['status']=='completed' and p.records[0]['actual_usd']=='0.00004'


def test_third_run_timing_scenarios_are_conditional_and_stress_fails_closed():
    from scripts.simulate_post_synthesis_dev import simulate
    normal=simulate();semantic=simulate('semantic');surgical=simulate('surgical');stress=simulate('old_slow_stress')
    assert all(r['verdict']=='PASS' for r in normal['rows'])
    assert [r['calls'] for r in normal['rows']]==[0,0,1,1,1,3]
    assert all(r['total_s']<30 for r in semantic['rows']+surgical['rows'])
    assert all(not r['synthesis_provider_invoked'] for r in normal['rows'][:5])
    assert stress['rows'][2]['status']==stress['rows'][4]['status']=='COMPLETED'
    assert all(x['paid_calls']==0 for x in (normal,semantic,surgical,stress))


def test_full_bridge_timing_probe_exercises_semantic_surgical_and_timeout_paths():
    from scripts.simulate_post_synthesis_dev import simulate
    rows=[simulate(s,bridge_probe=True)['rows'][2] for s in ('canonical','semantic','surgical','old_slow_stress')]
    assert all(r['status']=='COMPLETED' and r['total_s']<30 for r in rows[:3])
    assert rows[2]['surgical_revision'] and rows[2]['release_mode']=='surgical_supported_subset'
    assert rows[3]['status']=='REFUSED' and rows[3]['total_s']<30
