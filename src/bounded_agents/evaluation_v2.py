"""Separate machine dimensions and human adjudication; no provider execution."""
from .completeness import assess
from .answer_contract import components,ComponentRole
from .causal_policy import assess_claim


def fault_precondition(draft,bundle,kind):
    complete=assess(draft,bundle).complete
    if kind=='omit_documentary_component':
        typed=components(draft)
        return complete and any(c.value is None and c.claim_id in typed
            and typed[c.claim_id].role is ComponentRole.DIRECT_ANSWER
            and c.claim_type.value!='LIMITATION' for c in draft.claims)
    if kind=='affirmative_causal_corruption':return complete and bool(draft.claims)
    raise ValueError('Unknown bounded fault')


def inject_fault(draft,bundle,kind):
    """Return an unchanged invalid setup, or one typed, controlled defect."""
    if not fault_precondition(draft,bundle,kind):return draft,False
    typed=components(draft)
    if kind=='omit_documentary_component':
        removed={c.claim_id for c in draft.claims if c.claim_id in typed and typed[c.claim_id].role is ComponentRole.DIRECT_ANSWER}
        claims=tuple(c for c in draft.claims if c.claim_id not in removed)
        updated=draft.model_copy(update={'claims':claims,'components':tuple(x for x in draft.components if x.claim_id not in removed),
            'answer':' '.join(c.text for c in claims)})
    else:
        from .post_synthesis import compose,CompactSynthesis,ContextStatement
        updated=compose(bundle,CompactSynthesis(context=(ContextStatement(kind='interpretation',
            text="Management's bridge proves an independently established causal effect.",
            evidence_ids=(bundle.selected_evidence_ids[0],)),)),fixture_mode=getattr(draft,'fixture_mode',False))
    return updated,True


def score(graph,brief,*,fault_setup_valid=None,fault_detected=None,fault_recovered=None):
    state=getattr(graph,'last_state',{})
    release=getattr(graph,'release_record',None)
    partial=(release is not None and release.release_mode.value=='PARTIAL') or brief.refusal_reason in {
        'review_timeout_supported_numeric_subset','semantic_review_unavailable_supported_subset',
        'surgical_supported_subset','supported_subset','supported_numeric_subset','supported_documentary_subset'}
    task=(brief.status.value=='COMPLETED' and not partial and 'draft' in state
        and assess(state['draft'],state['evidence']).complete) or brief.status.value=='NEEDS_CLARIFICATION'
    return {'version':'bounded-p0-development-2',
        'machine_result':{'task_completion':task,'supported_subset':partial,
            'safety':{'released_verified':not brief.claims or brief.verification is not None and brief.verification.verdict.value=='PASS',
                'unsupported_claim_released':any(assess_claim(c,state['evidence']).prohibited for c in brief.claims) if 'evidence' in state else bool(brief.claims)},
            'fault_detection':fault_detected if fault_setup_valid is True else None,
            'fault_recovery':fault_recovered if fault_setup_valid is True else None,
            'fault_setup':'VALID' if fault_setup_valid is True else 'INVALID' if fault_setup_valid is False else 'NOT_APPLIED',
            'efficiency':{'generation_calls':graph.budget.calls,'ceiling':graph.budget.max_total_calls},
            'system_reliability':{'review_timeout':graph.review_timeout,
                'request_failed':brief.status.value=='REFUSED' and (brief.refusal_reason or '').startswith('WORKFLOW_FAILURE')}},
        'human_adjudication':{'status':'NOT_REVIEWED','reviewer':None,'verdict':None,'notes':None}}
