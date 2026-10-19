"""Central conservative assertion/provenance policy. Lexical risk is review only.

Recognized negative causal boundaries are removed at phrase level, not by an
unsafe sentence-wide 'not' exemption. Any remaining affirmative assertion is
still blocked. This is bounded policy, not general natural-language entailment.
"""
from enum import Enum
import re
from .models import Contract


class AssertionType(str, Enum):
    MANAGEMENT_ATTRIBUTED = 'MANAGEMENT_ATTRIBUTED'
    REPORTED_CONTRIBUTION = 'REPORTED_CONTRIBUTION'
    DESCRIPTIVE_ASSOCIATION = 'DESCRIPTIVE_ASSOCIATION'
    INTERPRETATION = 'INTERPRETATION'
    INDEPENDENT_CAUSAL_ASSERTION = 'INDEPENDENT_CAUSAL_ASSERTION'
    LIMITATION = 'LIMITATION'


class CausalAssessment(Contract):
    assertion_type: AssertionType
    polarity: str
    source_bound: bool
    review_required: bool
    prohibited: bool
    reason: str | None


BOUNDARIES = re.compile(r'\b(?:not|no) (?:an? )?(?:independently (?:established|identified) )?(?:causal (?:identifications?|effects?|proof|evidence)|causality)\b|\brather than independently established causality\b',re.I)
AFFIRMATIVE = re.compile(r'\b(?:caused?|causes|causing|led to|leads to|because(?: of)?|due to|resulted in|results in|causal(?:ly)?|causality|forecast\w*|predict\w*|future|will)\b',re.I)


def assess_claim(claim,bundle):
    from .post_synthesis import evidence_map,governed_draft
    docs=evidence_map(bundle)
    canonical={c.claim_id:c for c in governed_draft(bundle).claims}
    anchored=claim==canonical.get(claim.claim_id)
    bound=bool(claim.evidence_ids) and all(e in docs and claim.text in docs[e].text for e in claim.evidence_ids)
    residual=BOUNDARIES.sub('',claim.text)
    positive=bool(AFFIRMATIVE.search(residual))
    negated=bool(BOUNDARIES.search(claim.text))
    if anchored:
        kind=AssertionType.MANAGEMENT_ATTRIBUTED if claim.claim_type.value=='MANAGEMENT_ATTRIBUTED' else AssertionType.REPORTED_CONTRIBUTION
        return CausalAssessment(assertion_type=kind,polarity='reported',source_bound=True,
            review_required=False,prohibited=False,reason=None)
    if claim.value is not None:
        return CausalAssessment(assertion_type=AssertionType.INTERPRETATION,polarity='unknown',source_bound=False,
            review_required=True,prohibited=True,reason='CANONICAL_PROVENANCE_MISMATCH')
    # Exact source content reports what a source says, never independently
    # establishes its assertion as the application's own causal conclusion.
    if bound and claim.claim_type.value=='REPORTED':
        return CausalAssessment(assertion_type=AssertionType.REPORTED_CONTRIBUTION,polarity='reported',
            source_bound=True,review_required=positive,prohibited=False,reason=None)
    if positive:
        return CausalAssessment(assertion_type=AssertionType.INDEPENDENT_CAUSAL_ASSERTION,polarity='affirmative',
            source_bound=bound,review_required=True,prohibited=True,reason='UNSUPPORTED_CAUSAL_ASSERTION')
    kind=AssertionType.LIMITATION if claim.claim_type.value=='LIMITATION' or negated else AssertionType.MANAGEMENT_ATTRIBUTED if re.search(r'\b(?:report|management) (?:reports?|attributes?|attributed)\b',claim.text,re.I) else AssertionType.DESCRIPTIVE_ASSOCIATION if re.search(r'\b(?:associated|association|correlat\w*)\b',claim.text,re.I) else AssertionType.INTERPRETATION
    return CausalAssessment(assertion_type=kind,polarity='negative' if negated else 'descriptive',
        source_bound=bound,review_required=not bound,prohibited=False,reason=None)


def prohibited(draft,bundle):
    return tuple(c.claim_id for c in draft.claims if assess_claim(c,bundle).prohibited)
