"""Small model wire contract; application-owned translation and risk policy."""
from enum import Enum
from itertools import product
from pydantic import Field, create_model, model_validator
from .models import Contract


class ReviewStatus(str, Enum):
    PASS = 'PASS'
    REVISE = 'REVISE'
    BLOCK = 'BLOCK'


class ReviewIssue(str, Enum):
    NONE = 'NONE'
    UNSUPPORTED_CLAIM = 'UNSUPPORTED_CLAIM'
    CAUSAL_OVERSTATEMENT = 'CAUSAL_OVERSTATEMENT'
    ATTRIBUTION_ERROR = 'ATTRIBUTION_ERROR'
    EVIDENCE_MISMATCH = 'EVIDENCE_MISMATCH'
    INCOMPLETE_ANSWER = 'INCOMPLETE_ANSWER'
    MISSING_LIMITATION = 'MISSING_LIMITATION'


class ReviewAction(str, Enum):
    NONE = 'NONE'
    DROP_CLAIM = 'DROP_CLAIM'
    ADD_LIMITATION = 'ADD_LIMITATION'
    REQUEST_MISSING_COMPONENT = 'REQUEST_MISSING_COMPONENT'


class ReviewReason(str, Enum):
    SUPPORT_OK = 'SUPPORT_OK'
    SEMANTIC_RISK = 'SEMANTIC_RISK'
    MISSING_COMPONENT = 'MISSING_COMPONENT'


class CompactReview(Contract):
    status: ReviewStatus
    issue_type: ReviewIssue
    claim_id: str | None = Field(pattern=r'^claim_[0-9]{3}$')
    correction_action: ReviewAction
    reason_code: ReviewReason

    @model_validator(mode='after')
    def coherent(self):
        if self.status is ReviewStatus.PASS:
            if (self.issue_type is not ReviewIssue.NONE or self.claim_id is not None
                or self.correction_action is not ReviewAction.NONE or self.reason_code is not ReviewReason.SUPPORT_OK):
                raise ValueError('PASS cannot contain objections or edits')
        else:
            if self.issue_type is ReviewIssue.NONE or self.claim_id is None or self.reason_code is ReviewReason.SUPPORT_OK:
                raise ValueError('Intervention needs an existing claim and typed reason')
            if self.status is ReviewStatus.BLOCK and self.correction_action is not ReviewAction.NONE:
                raise ValueError('BLOCK cannot request edits')
            if self.status is ReviewStatus.REVISE:
                allowed = {ReviewIssue.INCOMPLETE_ANSWER: ReviewAction.REQUEST_MISSING_COMPONENT,
                    ReviewIssue.MISSING_LIMITATION: ReviewAction.ADD_LIMITATION}
                expected = allowed.get(self.issue_type, ReviewAction.DROP_CLAIM)
                if self.correction_action is not expected:
                    raise ValueError('Correction must address the issue')
            if (self.issue_type is ReviewIssue.INCOMPLETE_ANSWER) != (self.reason_code is ReviewReason.MISSING_COMPONENT):
                raise ValueError('Reason must match the issue')
        return self


def valid_examples():
    """Exhaustive bounded shape enumeration; no provider/tokenizer network."""
    for status, issue, action, reason in product(ReviewStatus, ReviewIssue, ReviewAction, ReviewReason):
        try:
            yield CompactReview(status=status, issue_type=issue,
                claim_id=None if status is ReviewStatus.PASS else 'claim_999',
                correction_action=action, reason_code=reason)
        except ValueError:
            pass


# UTF-8 bytes conservatively bound visible JSON tokens for byte-level encodings.
# 64 tokens of explicit formatting headroom, rounded up to a 32-token boundary.
# Not a measured live-model guarantee: required failure still withholds semantics.
MAX_REVIEW_JSON_BYTES = max(len(x.model_dump_json().encode()) for x in valid_examples())
REVIEW_OUTPUT_TOKEN_CAP = ((MAX_REVIEW_JSON_BYTES + 64 + 31) // 32) * 32
REVIEW_UNAVAILABLE_LIMITATION = 'Unreviewed semantic interpretation was withheld; only independently verified canonical content is retained.'


def wire_contract(payload):
    from .repair_targets import version, VERSION, wire_contract as repair_contract
    if version(payload) == VERSION:
        return repair_contract(payload)
    ids = tuple(dict.fromkeys(x['claim_id'] for x in (*payload.get('claims',()), *payload.get('numeric_handles',()))))
    choices = Enum('ReviewClaimIdentity', {f'C{i}':x for i,x in enumerate(ids)}, type=str) if ids else type(None)
    return create_model('BoundedSemanticReview', __base__=CompactReview,
        claim_id=(choices | None if ids else type(None), ...))


def to_feedback(review, payload):
    """Translate one compact decision into existing closed application edits."""
    from .repair_targets import version, VERSION, to_feedback as repair_feedback
    if version(payload) == VERSION:
        return repair_feedback(review, payload)
    from src.orchestration.tools import ToolAuthorizationError
    from .post_synthesis import ActionableCritic, SurgicalCorrection
    ids = {x['claim_id'] for x in (*payload.get('claims',()), *payload.get('numeric_handles',()))}
    if review.claim_id is not None and review.claim_id not in ids:
        raise ToolAuthorizationError('Semantic Review Agent invented claim identity')
    if review.status is ReviewStatus.PASS:
        return ActionableCritic(decision='approve', issues=(), claim_ids=(), evidence_sufficient=True, corrections=())
    issue = {ReviewIssue.UNSUPPORTED_CLAIM:'unsupported_interpretation',
        ReviewIssue.CAUSAL_OVERSTATEMENT:'causal_overclaim', ReviewIssue.ATTRIBUTION_ERROR:'misleading_attribution',
        ReviewIssue.EVIDENCE_MISMATCH:'unsupported_interpretation', ReviewIssue.INCOMPLETE_ANSWER:'incomplete_answer',
        ReviewIssue.MISSING_LIMITATION:'missing_limitation'}[review.issue_type]
    edits=()
    if review.status is ReviewStatus.REVISE:
        operation={ReviewAction.DROP_CLAIM:'drop_claim', ReviewAction.ADD_LIMITATION:'add_limitation',
            ReviewAction.REQUEST_MISSING_COMPONENT:'add_missing_answer_component'}[review.correction_action]
        extra={}
        if review.correction_action is ReviewAction.REQUEST_MISSING_COMPONENT:
            candidates=payload.get('completion_candidate_evidence_ids',())
            missing=payload.get('completeness',{}).get('missing_components',())
            if not candidates or not missing:
                raise ValueError('No application-owned completion candidate')
            extra={'evidence_id':candidates[0], 'missing_answer_component':missing[0]}
        edits=(SurgicalCorrection(claim_id=review.claim_id, issue=issue, operation=operation, **extra),)
    return ActionableCritic(decision='revise' if edits else 'reject', issues=(issue,),
        claim_ids=(review.claim_id,), evidence_sufficient=True, corrections=edits)


class ReviewRequirement(str, Enum):
    SKIP = 'SKIP'
    OPTIONAL = 'OPTIONAL'
    REQUIRED = 'REQUIRED'


def requirement(draft, bundle, *, optional=False):
    from .release_policy import review_required
    return ReviewRequirement.REQUIRED if review_required(draft,bundle) else ReviewRequirement.OPTIONAL if optional else ReviewRequirement.SKIP
