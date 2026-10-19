"""Synthetic target examples; not corporate evidence, private cases or live results."""
from copy import deepcopy
import pytest
from src.bounded_agents.repair_targets import prepare_payload,LEGACY_VERSION
from src.bounded_agents.semantic_review import wire_contract,to_feedback


def payload():
    return {'question':'What did this synthetic example report?', 'operation':'RETRIEVE_CONTEXT',
        'claims':[{'claim_id':'claim_027','text':'Synthetic supporting statement.','evidence_ids':['eu_synthetic']}],
        'documents':[{'id':'eu_synthetic','text':'Synthetic reporting example: sales increased.',
                      'authenticity':'SYNTHETIC_FIXTURE','shortened':False}],
        'completeness':{'complete':False,'missing_components':['direct_commentary'],
                        'eligible_documentary_evidence':True},
        'completion_candidate_available':True,'completion_candidate_kind':'quote',
        'completion_candidate_evidence_ids':['eu_synthetic']}


def decision(p):
    return {'status':'REVISE','issue_type':'INCOMPLETE_ANSWER','claim_id':None,
        'repair_option_id':p['repair_options'][0]['repair_option_id'],
        'correction_action':'REQUEST_MISSING_COMPONENT','reason_code':'MISSING_COMPONENT'}


def test_completion_uses_owned_option():
    p=prepare_payload(payload());f=to_feedback(wire_contract(p).model_validate(decision(p)),p)
    assert f.corrections[0].claim_id=='claim_027'
    assert f.corrections[0].missing_answer_component=='direct_commentary'
    assert f.corrections[0].evidence_id=='eu_synthetic'


@pytest.mark.parametrize('change',[{'repair_option_id':None},{'repair_option_id':'invented'},
    {'claim_id':'claim_027'},{'correction_action':'DROP_CLAIM'},{'replacement_text':'arbitrary prose'}])
def test_invalid_target_or_instruction_rejected(change):
    p=prepare_payload(payload())
    with pytest.raises(ValueError):wire_contract(p).model_validate({**decision(p),**change})


def test_stale_and_tampered_targets_rejected():
    p=prepare_payload(payload());changed=payload();changed['question']='Another synthetic question.'
    new=prepare_payload(changed)
    with pytest.raises(ValueError):wire_contract(new).model_validate(decision(p))
    p['repair_options'][0]['supported_candidate']='eu_invented'
    with pytest.raises(ValueError):wire_contract(p)


def test_duplicate_and_malformed_ids_rejected():
    p=payload();p['claims'].append(deepcopy(p['claims'][0]))
    with pytest.raises(ValueError):wire_contract(prepare_payload(p))
    p=payload();p['claims'][0]['claim_id']='malformed'
    with pytest.raises(ValueError):wire_contract(prepare_payload(p))


def test_legacy_remains_five_fields():
    p=payload()
    assert len(wire_contract(p).model_fields)==5
    assert len(wire_contract({**p,'semantic_review_contract_version':LEGACY_VERSION}).model_fields)==5


@pytest.mark.parametrize('supported',[True,False])
def test_synthetic_completion_release_preserves_only_permitted_interpretation(supported):
    """Self-contained model fixtures, not a held or corporate evidence case."""
    import hashlib
    import json
    from pathlib import Path
    from src.bounded_agents.runtime import BoundedAgentsGraph
    from src.bounded_agents.fixtures import SpikeFixtureProvider
    from src.bounded_agents.post_synthesis import compose,CompactSynthesis,ContextStatement,ActionableCritic
    from src.bounded_agents.evaluation_v2 import score
    from src.retrieval.models import EvidenceUnit
    from src.retrieval.retrieve import GovernedRetriever
    from src.retrieval.embeddings import LocalHashEmbeddingProvider
    root=Path(__file__).resolve().parents[1]
    text='Management reported sales growth. Currency movements affected reported sales.'
    eid='eu_'+'a'*24
    unit=EvidenceUnit.model_validate_json(json.dumps({
        'evidence_unit_id':eid,'source_id':'synthetic_public_release_example',
        'company_id':'henkel','source_title':'Synthetic release example','source_type':'fixture',
        'reporting_periods':['H1_2026'],'publication_date':'2026-01-01','page_number':1,
        'printed_page_or_slide':'1','section':'Synthetic sales example',
        'business_scopes':['henkel_group'],'metric_ids':['henkel_sales'],
        'evidence_unit_type':'NARRATIVE_SECTION','evidence_relevance':'COMMENTARY',
        'source_hierarchy':'PRIMARY','evidence_method':'DOCUMENT_TEXT','text':text,
        'official_url':'https://example.invalid/synthetic','content_hash':hashlib.sha256(text.encode()).hexdigest(),
        'parser_version':'synthetic-test','chunking_version':'synthetic-test'}))
    g=BoundedAgentsGraph(root,provider=SpikeFixtureProvider(),fixture_mode=True,
        retriever=GovernedRetriever([unit],root=root,embedding_provider=LocalHashEmbeddingProvider()))
    g.run('What did Henkel management report about sales in H1 2026?')
    s=dict(g.last_state);bundle=s['evidence']
    context='Management reported sales growth.' if supported else 'Reported sales commentary has limited explanatory scope.'
    draft=compose(bundle,CompactSynthesis(context=(ContextStatement(kind='interpretation',text=context,
        evidence_ids=(eid,)),)),fixture_mode=True)
    old=draft.claims[0]
    g.completion_candidate=ContextStatement(kind='quote',text=text,evidence_ids=(eid,))
    s.update(draft=draft,revision_count=0,critic=ActionableCritic.model_validate({
        'decision':'revise','issues':['incomplete_answer'],'claim_ids':[old.claim_id],
        'evidence_sufficient':True,'corrections':[{'claim_id':old.claim_id,'issue':'incomplete_answer',
            'operation':'add_missing_answer_component','evidence_id':eid,'missing_answer_component':'direct_commentary'}]}))
    s={**s,**g._revise(s)};s={**s,**g._critic(s)};s={**s,**g._verify(s)}
    assert g._after_verify(s)=='pass'
    out=g._finalize(s);g.last_state={**s,**out};brief=out['final']
    assert brief.verification.verdict.value=='PASS'
    assert (old in brief.claims) is supported
    assert g.release_record.release_mode.value==('FULL' if supported else 'PARTIAL')
    if not supported:
        assert old.claim_id in g.release_record.withheld_claim_ids
        assert not set(g.release_record.released_claim_ids)&set(g.release_record.withheld_claim_ids)
        assert brief.refusal_reason=='supported_documentary_subset' and brief.answer==text
        assert score(g,brief)['machine_result']['task_completion'] is False


@pytest.mark.parametrize('reason',['supported_numeric_subset','supported_documentary_subset'])
def test_partial_reasons_never_count_as_full_task_completion(reason):
    from types import SimpleNamespace
    from src.bounded_agents.evaluation_v2 import score
    graph=SimpleNamespace(last_state={},release_record=None,budget=SimpleNamespace(calls=0,max_total_calls=1),
        review_timeout=False)
    brief=SimpleNamespace(refusal_reason=reason,status=SimpleNamespace(value='COMPLETED'),claims=())
    result=score(graph,brief)['machine_result']
    assert result['supported_subset'] is True and result['task_completion'] is False
