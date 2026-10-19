"""V2 route-specific structural completeness, independent of support checks.

This is not a semantic similarity oracle. The Semantic Review Agent also reviews
question fulfillment. A source disclaimer is never documentary substance.
"""
import re
from .models import Contract
from pydantic import Field


class CompletenessAssessment(Contract):
    complete: bool
    missing_components: tuple[str, ...]
    documentary_required: bool
    eligible_documentary_evidence: bool


def substantive(text):
    # Remove source qualifications only, never rewrite reporting content.
    remaining=re.sub(r'(?i)synthetic development (?:commentary|definition), not an issuer (?:quotation|definition)\.?','',text)
    remaining=remaining.strip(' \t\n\u201c\u201d\"\' .')
    if re.fullmatch(r'(?i)(?:the )?[\w /-]+(?:commentary|definition|explanation|evidence) (?:is |was )?(?:unavailable|absent|not provided|missing)\.?',remaining):
        return False
    return bool(remaining) and not re.fullmatch(
        r'(?i)(?:the )?(?:selected )?(?:source|evidence|citation|report|document)(?: evidence)? (?:is limited|is unavailable|was cited|is provided|contains commentary)\.?',remaining)


def documentary_required(p):
    """Business explanation intent is independent of numerical tool routing.

    A reported bridge can answer a decomposition, but not an explicitly requested
    documentary explanation. This policy is v2-only; the validated v1 is unchanged.
    """
    op=p.operation.value
    return op in {'DEFINE_METRIC','RETRIEVE_CONTEXT','EXPLAIN_WITH_EVIDENCE'} or p.question_type.value=='HYBRID_ANALYSIS' or bool(
        re.search(r'\b(?:why|what\s+drove|management commentary|documentary explanation)\b',p.raw_question,re.I))


def requirements(bundle):
    p=bundle.plan
    op=p.operation.value
    documentary=documentary_required(p)
    return {'operation':op,'documentary_required':documentary,
        'required_components':(('direct_definition','source_attribution') if op=='DEFINE_METRIC' else
            ('direct_commentary','source_attribution') if documentary else ('governed_result',)),
        'boundary_is_not_direct_answer':True}


def relevant_substance(text, bundle):
    """Conservative lexical shape check; not a substitute for semantic review."""
    target=bundle.plan.primary_target
    if not target or not target.metric_id:
        return substantive(text)
    terms=set(target.metric_id.value.split('_'))-{'henkel','mercedes','benz','group','adjusted','organic'}
    if 'ebit' in terms:
        terms |= {'bridge','contributions','attribution'}
    return substantive(text) and any(re.search(r'\b'+re.escape(x)+r'\b',text,re.I) for x in terms)


def eligible_documents(bundle, *, fixture_mode=False):
    from .post_synthesis import evidence_map
    from .answer_contract import authenticity,Authenticity
    op=bundle.plan.operation.value
    return {k:v for k,v in evidence_map(bundle).items() if relevant_substance(v.text,bundle)
        and (op!='DEFINE_METRIC' or v.evidence_unit_type.value=='METRIC_DEFINITION')
        and (fixture_mode or authenticity(v) is not Authenticity.SYNTHETIC_FIXTURE)}


def assess(draft,bundle):
    from .post_synthesis import governed_draft,evidence_map,SAFE_LIMITATIONS
    needs=requirements(bundle);missing=[]
    canonical=governed_draft(bundle)
    required_numeric={c.claim_id:c for c in canonical.claims if c.value is not None}
    actual={c.claim_id:c for c in draft.claims}
    if any(k not in actual or actual[k].value!=v.value for k,v in required_numeric.items()):
        missing.append('governed_result')
    if bundle.analytics and bundle.analytics.ranked_components:
        first=bundle.analytics.ranked_components[0]
        if not draft.claims or first.fact_id not in draft.claims[0].fact_ids or not draft.claims[0].text.startswith('Largest '):
            missing.append('requested_contributor')
    docs=evidence_map(bundle)
    op=bundle.plan.operation.value
    eligible=eligible_documents(bundle,fixture_mode=getattr(draft,'fixture_mode',False))
    if needs['documentary_required']:
        from .answer_contract import components,ComponentRole
        typed=components(draft)
        supported_context=any(c.value is None and c.claim_type.value not in {'LIMITATION'}
            and c.claim_id in typed and typed[c.claim_id].role is ComponentRole.DIRECT_ANSWER
            and relevant_substance(c.text,bundle) and c.evidence_ids
            and set(c.evidence_ids).issubset(eligible) for c in draft.claims)
        if not supported_context:
            # Numeric subsets may explicitly withhold absent documentary content.
            missing.append('direct_definition' if op=='DEFINE_METRIC' else 'direct_commentary')
    return CompletenessAssessment(complete=not missing,missing_components=tuple(missing),
        documentary_required=needs['documentary_required'],eligible_documentary_evidence=bool(eligible))
