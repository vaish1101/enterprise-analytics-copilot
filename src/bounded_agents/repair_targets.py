"""Opt-in semantic-review target contract. No model-owned remediation content."""
from copy import deepcopy
from enum import Enum
import hashlib
import json
import re
from pydantic import Field, create_model, model_validator
from .models import Contract
from .semantic_review import ReviewStatus, ReviewIssue, ReviewAction, ReviewReason
from .post_synthesis import ActionableCritic

VERSION = 'semantic-review-repair-options-2'
LEGACY_VERSION = 'semantic-review-1'
PROMPT_SUFFIX = '''
This request uses versioned repair options. For REQUEST_MISSING_COMPONENT,
select one supplied repair_option_id and return claim_id=null. The option binds
the exact missing component, supported candidate and permitted action; its
anchor_claim_id is application execution bookkeeping, not your claim target.
For DROP_CLAIM, select the disputed claim_id and return repair_option_id=null.
Never invent repair options or supply repair text. If no compatible completion
option exists, BLOCK the incompleteness with both targets null. PASS has both
targets null. Missing-limitation addition is not offered by this contract;
BLOCK that answer-level risk rather than selecting a claim anchor.'''


class TargetFeedback(ActionableCritic):
    """Opt-in internal feedback permits explicit answer-level rejection only."""
    @model_validator(mode='after')
    def actionable(self):
        if (self.decision.value == 'reject' and not self.claim_ids
            and len(self.issues) == 1
            and self.issues[0].value in {'incomplete_answer', 'missing_limitation'}
            and not self.corrections):
            return self
        return super().actionable()


def version(payload):
    value = payload.get('semantic_review_contract_version', LEGACY_VERSION)
    if value not in (LEGACY_VERSION, VERSION):
        raise ValueError('Unknown semantic review contract version')
    return value


def options(payload):
    """Derive one unambiguous documentary completion from trusted app context.

    Current surgery accepts a single retained quote candidate. Do not invent
    component/source pairings when multiple missing components or candidates exist.
    The anchor is execution bookkeeping, not a reviewer-selected disputed claim.
    """
    validate_identities(payload)
    missing = payload.get('completeness', {}).get('missing_components', ())
    candidates = payload.get('completion_candidate_evidence_ids', ())
    expected = ('direct_definition' if payload.get('operation') == 'DEFINE_METRIC'
                else 'direct_commentary')
    if (list(missing) != [expected] or len(candidates) != 1
        or not payload.get('completion_candidate_available')
        or payload.get('completion_candidate_kind', 'quote') != 'quote'
        or not payload.get('completeness', {}).get('eligible_documentary_evidence')
        or payload.get('completeness', {}).get('complete') is not False):
        return []
    docs = [d for d in payload.get('documents', ()) if d['id'] == candidates[0]]
    if len(docs) != 1 or docs[0].get('shortened') or not docs[0].get('text'):
        return []
    from .completeness import substantive
    if not substantive(docs[0]['text']):
        return []
    anchors = sorted(c['claim_id'] for c in payload.get('claims', ())
                     if candidates[0] in c.get('evidence_ids', ()))
    if not anchors:
        return []
    # Bind a response choice to the exact application-owned context. A constant
    # request-local ordinal would accept an old response against a changed request.
    context = {k:v for k,v in payload.items()
               if k not in {'repair_options', 'semantic_review_contract_version'}}
    context = deepcopy(context)
    for field, identity in (('claims','claim_id'), ('numeric_handles','claim_id'),
                            ('components','claim_id'), ('documents','id')):
        if field in context:
            context[field] = sorted(context[field], key=lambda x:x[identity])
    digest = hashlib.sha256(json.dumps(context, sort_keys=True, separators=(',',':')).encode()).hexdigest()[:16]
    return [{'repair_option_id':'repair_'+digest, 'missing_component':expected,
             'supported_candidate':candidates[0],
             'permitted_action':'REQUEST_MISSING_COMPONENT',
             'anchor_claim_id':anchors[0]}]


def validate_identities(payload):
    """Reject ambiguous application state before enums or edits can hide it."""
    seen = set()
    for field in ('claims', 'numeric_handles'):
        for item in payload.get(field, ()):
            identity = item.get('claim_id')
            if not isinstance(identity, str) or not re.fullmatch(r'claim_[0-9]{3}', identity):
                raise ValueError('Malformed application claim identity')
            if identity in seen:
                raise ValueError('Duplicate or numeric-aliased application claim identity')
            seen.add(identity)
    for field, key in (('documents','id'), ('components','claim_id')):
        ids = [item.get(key) for item in payload.get(field, ())]
        if any(not isinstance(i,str) or not i for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('Missing or duplicate application identity')


def prepare_payload(payload):
    """New derived input; never modify a frozen payload or accept supplied options."""
    value = deepcopy(payload)
    value['semantic_review_contract_version'] = VERSION
    value['repair_options'] = options(value)
    return value


def checked_options(payload):
    if version(payload) != VERSION or payload.get('repair_options') != options(payload):
        raise ValueError('Repair options do not match application-owned context')
    return payload['repair_options']


class TargetReview(Contract):
    status: ReviewStatus
    issue_type: ReviewIssue
    claim_id: str | None = Field(description='Existing disputed claim for claim corrections; null for answer completion or PASS.')
    repair_option_id: str | None = Field(description='Select a supplied repair option for REQUEST_MISSING_COMPONENT; null otherwise.')
    correction_action: ReviewAction
    reason_code: ReviewReason

    @model_validator(mode='after')
    def coherent(self):
        if self.claim_id is not None and self.repair_option_id is not None:
            raise ValueError('Claim and repair targets are mutually exclusive')
        if self.status is ReviewStatus.PASS:
            if (self.issue_type is not ReviewIssue.NONE or self.claim_id is not None
                or self.repair_option_id is not None or self.correction_action is not ReviewAction.NONE
                or self.reason_code is not ReviewReason.SUPPORT_OK):
                raise ValueError('PASS cannot contain objections or targets')
            return self
        if self.issue_type is ReviewIssue.NONE or self.reason_code is ReviewReason.SUPPORT_OK:
            raise ValueError('Intervention needs a typed issue and reason')
        incomplete = self.issue_type is ReviewIssue.INCOMPLETE_ANSWER
        if incomplete != (self.reason_code is ReviewReason.MISSING_COMPONENT):
            raise ValueError('Reason must match the issue')
        if self.status is ReviewStatus.BLOCK:
            if self.correction_action is not ReviewAction.NONE or self.repair_option_id is not None:
                raise ValueError('BLOCK cannot select a repair')
            if incomplete or self.issue_type is ReviewIssue.MISSING_LIMITATION:
                if self.claim_id is not None:
                    raise ValueError('Answer-level BLOCK has no disputed claim')
            elif self.claim_id is None:
                raise ValueError('Claim-level BLOCK needs a disputed claim')
            return self
        if incomplete:
            if (self.correction_action is not ReviewAction.REQUEST_MISSING_COMPONENT
                or self.repair_option_id is None or self.claim_id is not None):
                raise ValueError('Completion requires a repair option, not a claim target')
        elif (self.issue_type is ReviewIssue.MISSING_LIMITATION
              or self.correction_action is not ReviewAction.DROP_CLAIM
              or self.claim_id is None or self.repair_option_id is not None):
            # Limitation addition remains legacy-only until its own answer-target
            # options are defined; never reuse a claim anchor in this contract.
            raise ValueError('Claim correction requires DROP_CLAIM and a claim target')
        return self


def wire_contract(payload):
    repairs = checked_options(payload)
    ids = tuple(dict.fromkeys(c['claim_id'] for c in payload.get('claims', ())))
    claims = Enum('DisputedClaimIdentity', {f'C{i}':v for i,v in enumerate(ids)}, type=str) if ids else type(None)
    repair_ids = [r['repair_option_id'] for r in repairs]
    choices = Enum('RepairOptionIdentity', {f'R{i}':v for i,v in enumerate(repair_ids)}, type=str) if repair_ids else type(None)
    return create_model('BoundedSemanticReviewRepairOptionsV2', __base__=TargetReview,
        claim_id=(claims | None if ids else type(None), Field(..., description=TargetReview.model_fields['claim_id'].description)),
        repair_option_id=(choices | None if repair_ids else type(None), Field(..., description=TargetReview.model_fields['repair_option_id'].description)))


def to_feedback(review, payload):
    from .post_synthesis import SurgicalCorrection
    # Revalidate even direct/internal callers or model_construct cannot bypass
    # coherence, option membership, or application-owned option/action bindings.
    review = wire_contract(payload).model_validate(review.model_dump(mode='json'))
    if review.status is ReviewStatus.PASS:
        return TargetFeedback(decision='approve', issues=(), claim_ids=(), evidence_sufficient=True, corrections=())
    issue = {ReviewIssue.UNSUPPORTED_CLAIM:'unsupported_interpretation',
             ReviewIssue.CAUSAL_OVERSTATEMENT:'causal_overclaim', ReviewIssue.ATTRIBUTION_ERROR:'misleading_attribution',
             ReviewIssue.EVIDENCE_MISMATCH:'unsupported_interpretation', ReviewIssue.INCOMPLETE_ANSWER:'incomplete_answer',
             ReviewIssue.MISSING_LIMITATION:'missing_limitation'}[review.issue_type]
    if review.status is ReviewStatus.BLOCK:
        return TargetFeedback(decision='reject', issues=(issue,),
            claim_ids=(review.claim_id,) if review.claim_id else (), evidence_sufficient=True, corrections=())
    if review.correction_action is ReviewAction.REQUEST_MISSING_COMPONENT:
        selected = next(r for r in checked_options(payload) if r['repair_option_id'] == review.repair_option_id)
        if selected['permitted_action'] != review.correction_action.value:
            raise ValueError('Repair option/action mismatch')
        edit = SurgicalCorrection(claim_id=selected['anchor_claim_id'], issue=issue,
            operation='add_missing_answer_component', evidence_id=selected['supported_candidate'],
            missing_answer_component=selected['missing_component'])
    else:
        edit = SurgicalCorrection(claim_id=review.claim_id, issue=issue, operation='drop_claim')
    return TargetFeedback(decision='revise', issues=(issue,), claim_ids=(edit.claim_id,),
                           evidence_sufficient=True, corrections=(edit,))
