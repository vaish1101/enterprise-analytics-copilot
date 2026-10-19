"""Shared P0 release/review/repair decisions; no model-owned authority."""
from .answer_contract import AnswerComponent,ComponentRole,TypedDraft,authenticity
from .completeness import assess,eligible_documents
from .causal_policy import assess_claim


def repair_component(draft,bundle,*,reserved_claim_ids=()):
    """One source-only completion. Caller owns attempt count and deadline."""
    missing=assess(draft,bundle).missing_components
    if not set(missing)&{'direct_definition','direct_commentary'}:
        return None
    docs=eligible_documents(bundle,fixture_mode=getattr(draft,'fixture_mode',False))
    if not docs:return None
    from .post_synthesis import compose,CompactSynthesis,ContextStatement,SAFE_LIMITATIONS
    from .source_ownership import excerpt
    item=next(iter(docs.values()))
    resolved=compose(bundle,CompactSynthesis(context=(),direct_answer=ContextStatement(
        kind='quote',text=excerpt(item.text),evidence_ids=(item.evidence_unit_id,))),
        fixture_mode=getattr(draft,'fixture_mode',False))
    # A fallback may have removed every original claim. Do not recycle an ID
    # already recorded as withheld for a different claim in this request.
    used_ids={c.claim_id for c in draft.claims}|set(reserved_claim_ids)
    next_id=max([int(claim_id.split('_')[1]) for claim_id in used_ids]+[0])+1
    if next_id>999:raise ValueError('Completion claim identity space exhausted')
    new=resolved.claims[-1].model_copy(update={'claim_id':f'claim_{next_id:03d}'})
    original=draft.model_dump()
    original.update(claims=(*draft.claims,new) if bundle.analytics else (new,*draft.claims),
        components=(*getattr(draft,'components',()),AnswerComponent(claim_id=new.claim_id,
            role=ComponentRole.DIRECT_ANSWER,authenticity=authenticity(item),evidence_ids=new.evidence_ids,
            source_quotation=True)),
        limitations=tuple(dict.fromkeys((*[x for x in draft.limitations if x!=SAFE_LIMITATIONS[2]],*resolved.limitations))),revision_number=1)
    original['answer']=' '.join(c.text for c in original['claims'])
    return TypedDraft(**original)


def review_required(draft,bundle):
    from .semantic_review import REVIEW_UNAVAILABLE_LIMITATION
    from .post_synthesis import governed_draft,evidence_map,SAFE_LIMITATIONS
    from .answer_contract import components,Authenticity,authenticity
    from .source_ownership import excerpt
    if not assess(draft,bundle).complete:return True
    canonical={c.claim_id:c for c in governed_draft(bundle).claims}
    typed=components(draft)
    quoted_sources=set()
    for claim in draft.claims:
        if claim==canonical.get(claim.claim_id):continue
        docs=evidence_map(bundle)
        component=typed.get(claim.claim_id)
        doc=docs.get(claim.evidence_ids[0]) if len(claim.evidence_ids)==1 else None
        exact_quote=(component and component.source_quotation and doc is not None
            and claim.text==excerpt(doc.text) and component.evidence_ids==claim.evidence_ids
            and component.authenticity==authenticity(doc) and claim.claim_type.value=='REPORTED'
            and claim.value is None and claim.unit is None and not claim.fact_ids and not claim.calculation_run_ids)
        if exact_quote and (getattr(draft,'fixture_mode',False) or component.authenticity is not Authenticity.SYNTHETIC_FIXTURE):
            quoted_sources.add(doc.source_id)
            if len(quoted_sources)>1:return True
            continue
        policy=assess_claim(claim,bundle)
        if policy.prohibited or policy.review_required:return True
        if len({docs[e].source_id for e in claim.evidence_ids if e in docs})>1:return True
        if component and component.authenticity is Authenticity.SYNTHETIC_FIXTURE and not getattr(draft,'fixture_mode',False):return True
    allowed=set(governed_draft(bundle).limitations)|set(SAFE_LIMITATIONS)|{'Documentary context uses labelled synthetic development evidence, not issuer statements.',REVIEW_UNAVAILABLE_LIMITATION}
    return not set(governed_draft(bundle).limitations).issubset(draft.limitations) or any(x not in allowed for x in draft.limitations)


def review_window(remaining,*,maximum=12.0,verification=.25,repair=.25,minimum=1.0):
    available=remaining-verification-repair
    return min(maximum,available) if available>=minimum else None


def review_payload(draft,bundle,*,candidate_available=False,revision_count=0):
    from .post_synthesis import governed_draft,evidence_map
    from .completeness import requirements
    canonical={c.claim_id:c for c in governed_draft(bundle).claims}
    claims=[c for c in draft.claims if c!=canonical.get(c.claim_id)]
    ids={e for c in claims for e in c.evidence_ids}
    if not assess(draft,bundle).complete:ids.update(eligible_documents(bundle,fixture_mode=getattr(draft,'fixture_mode',False)))
    from .passage_representation import representation
    documents = [{**representation(x,budget=8192),'authenticity':authenticity(x).value}
                 for e,x in evidence_map(bundle).items() if e in ids]
    # Review must not approve from a prefix with an unseen qualifier or negation.
    if any(x['shortened'] for x in documents):
        raise ValueError('Complete canonical review context exceeds review budget')
    return {'question':bundle.plan.raw_question,'operation':bundle.plan.operation.value,
        'answer_requirements':requirements(bundle),'completeness':assess(draft,bundle).model_dump(mode='json'),
        'completion_candidate_available':candidate_available,
        'components':[x.model_dump(mode='json') for x in getattr(draft,'components',())],
        'claims':[{'claim_id':c.claim_id,'text':c.text,'claim_type':c.claim_type.value,
            'evidence_ids':c.evidence_ids,'causal_policy':assess_claim(c,bundle).model_dump(mode='json')} for c in claims],
        'numeric_claims_are_canonical':all(c==canonical.get(c.claim_id) for c in draft.claims if c.value is not None),
        'numeric_handles':[{'claim_id':c.claim_id,'fact_ids':c.fact_ids,'calculation_run_ids':c.calculation_run_ids} for c in canonical.values()],
        'limitations':draft.limitations,
        'documents':documents,
        'revision_count':revision_count}
