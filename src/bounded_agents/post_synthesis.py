"""V2-only compact synthesis, canonical numbers and bounded surgical edits.

No numerical validator relaxation; no model-derived arithmetic or source truth.
"""
from enum import Enum
from typing import Literal
import hashlib
import re

from pydantic import Field, model_validator

from src.orchestration.models import Claim, ClaimType, SynthesisDraft
from src.schemas.models import ProvenanceType
from .models import Contract, CriticFeedback, CriticDecision, CriticIssue
from .answer_contract import TypedDraft,AnswerComponent,ComponentRole,Authenticity,authenticity


class ContextKind(str, Enum):
    QUOTE = 'quote'
    INTERPRETATION = 'interpretation'
    LIMITATION = 'limitation'


class ContextStatement(Contract):
    kind: ContextKind
    # Resolved quotes are canonical application-owned passages, not model prose.
    text: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode='after')
    def bounded_semantic_text(self):
        if self.kind is not ContextKind.QUOTE and len(self.text) > 480:
            raise ValueError('Semantic claim needs bounded text')
        return self


class CompactSynthesis(Contract):
    # No model-owned number/value/unit/company/period/lineage fields.
    context: tuple[ContextStatement, ...] = Field(max_length=3)
    direct_answer: ContextStatement | None = Field(default=None,
        description='Substantive source-supported answer first for documentary requests; source caveats belong in context. Null only for numeric-only or unsupported content.')


class CorrectionOperation(str, Enum):
    ADD_MISSING_ANSWER_COMPONENT = 'add_missing_answer_component'
    DROP_CLAIM = 'drop_claim'
    RESTORE_NUMERIC = 'restore_numeric'
    REBIND_QUOTE = 'rebind_quote'
    ADD_LIMITATION = 'add_limitation'


PERMITTED_CORRECTIONS = {
    'incomplete_answer':{'add_missing_answer_component'},
    'causal_overclaim':{'drop_claim','restore_numeric'},
    'unsupported_interpretation':{'drop_claim'},
    'misleading_attribution':{'drop_claim','restore_numeric','rebind_quote'},
    'missing_limitation':{'add_limitation'},
}


class SurgicalCorrection(Contract):
    claim_id: str = Field(pattern=r'^claim_[0-9]{3}$')
    issue: CriticIssue
    operation: CorrectionOperation
    evidence_id: str | None = None
    missing_answer_component: Literal['direct_commentary','direct_definition','governed_result','requested_contributor'] | None = None

    @model_validator(mode='after')
    def operation_contract(self):
        if self.operation.value not in PERMITTED_CORRECTIONS[self.issue.value]:
            raise ValueError('Correction does not address a typed issue')
        if self.operation is CorrectionOperation.REBIND_QUOTE and self.evidence_id is None:
            raise ValueError('Quote rebinding requires selected evidence identity')
        if self.operation is CorrectionOperation.ADD_MISSING_ANSWER_COMPONENT and self.evidence_id is None:
            raise ValueError('Completion must bind selected evidence')
        if self.operation is CorrectionOperation.ADD_MISSING_ANSWER_COMPONENT and self.missing_answer_component is None:
            raise ValueError('Completion requires an exact missing component')
        if self.operation is not CorrectionOperation.ADD_MISSING_ANSWER_COMPONENT and self.missing_answer_component is not None:
            raise ValueError('Only completion names a missing component')
        if self.operation in {CorrectionOperation.RESTORE_NUMERIC, CorrectionOperation.ADD_LIMITATION} and self.evidence_id is not None:
            raise ValueError('Canonical restoration does not accept documentary evidence')
        return self


class ActionableCritic(CriticFeedback):
    corrections: tuple[SurgicalCorrection, ...] = Field(default=(), max_length=3)

    @model_validator(mode='after')
    def actionable(self):
        if self.decision is CriticDecision.REVISE:
            if not self.claim_ids or not self.corrections:
                raise ValueError('Revision requires exact claims and closed corrections')
            if set(self.claim_ids) != {x.claim_id for x in self.corrections}:
                raise ValueError('Every disputed claim needs an exact correction')
            if set(self.issues) != {x.issue for x in self.corrections}:
                raise ValueError('Every correction must bind its exact typed issue')
        elif self.corrections:
            raise ValueError('Only revision can contain corrections')
        if self.decision is CriticDecision.REJECT and not self.claim_ids:
            raise ValueError('Block requires exact unsupported claim identities')
        if len({x.claim_id for x in self.corrections}) != len(self.corrections):
            raise ValueError('Ambiguous duplicate edits')
        return self


CAUSAL_RISK = re.compile(r'\b(?:caus\w*|because|due to|led to|resulted in|proves?|forecast\w*|predict\w*|future|will|suggest\w*|indicat\w*|implies?)\b', re.I)
SAFE_LIMITATIONS = ('Management attribution is not causal identification.',
    'The combined volume / structure / net pricing category remains unsplit.',
    'Documentary context was not included; numeric results use governed facts only.',
    'Unsupported model context was removed; this is a governed numeric subset, not a complete semantic answer.')


def governed_draft(bundle):
    """Public claims generated solely from deterministic results/lineage."""
    a = bundle.analytics
    claims = []
    limitations = []
    if a:
        # Ranking order is authoritative and must lead the answer.
        by_id = {f.fact_id:f for f in a.decomposition_components}
        ranked = [by_id[r.fact_id] for r in a.ranked_components]
        facts = ranked + [a.primary_result, a.comparison_result, *a.decomposition_components]
        seen = set()
        for f in facts:
            if f is None or f.fact_id in seen:
                continue
            seen.add(f.fact_id)
            attributed = f.provenance_type is ProvenanceType.MANAGEMENT_ATTRIBUTED
            typ = ClaimType.MANAGEMENT_ATTRIBUTED if attributed else ClaimType.REPORTED
            prefix = 'Management reported' if attributed else 'Reported'
            if ranked and f.fact_id==ranked[0].fact_id:
                direction=bundle.plan.ranking_direction.value if bundle.plan.ranking_direction else ''
                selection='positive' if direction=='LARGEST_POSITIVE' else 'negative' if direction=='LARGEST_NEGATIVE' else 'absolute-magnitude'
                prefix=f'Largest {selection} management-reported contribution'
            claims.append(Claim(claim_id=f'claim_{len(claims)+1:03d}', claim_type=typ,
                text=f'{prefix}: {f.reported_name}, {f.business_scope}, {f.period.value}: {format(f.value,"f")} {f.unit.value}.',
                company_id=f.company.value, metric_id=f.metric_id.value,
                business_scope=f.business_scope, periods=(f.period.value,), value=f.value,
                unit=f.unit.value, fact_ids=(f.fact_id,), evidence_ids=f.evidence_ids))
        for run in a.calculation_runs:
            if run.result_value is None or run.output_field.value not in {'ABSOLUTE_CHANGE','PERCENT_CHANGE','PERCENTAGE_POINT_CHANGE'}:
                continue
            unit = 'percent' if run.output_field.value=='PERCENT_CHANGE' else 'percentage_point' if run.output_field.value=='PERCENTAGE_POINT_CHANGE' else a.primary_result.unit.value
            f = a.primary_result
            inputs = tuple(x for x in (a.primary_result,a.comparison_result) if x is not None)
            claims.append(Claim(claim_id=f'claim_{len(claims)+1:03d}', claim_type=ClaimType.CALCULATED,
                text=f'Calculated {run.output_field.value.lower()}: {format(run.result_value,"f")} {unit}.',
                company_id=f.company.value, metric_id=f.metric_id.value, business_scope=f.business_scope,
                periods=tuple(x.period.value for x in inputs), value=run.result_value, unit=unit,
                fact_ids=tuple(x.fact_id for x in inputs), calculation_run_ids=(run.run_id,), evidence_ids=a.evidence_ids))
        limitations.extend(x.value for x in (*a.limitations,*a.warnings))
        if a.source_plan_operation.value == 'RECONCILE' and a.reconciliation_results:
            limitations.append('The governed reported bridge reconciles within its approved source tolerance.'
                if all(r.passed for r in a.reconciliation_results) else
                'The reported bridge does not reconcile; a stronger conclusion is withheld.')
        if any(x.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED for x in claims):
            limitations.append(SAFE_LIMITATIONS[0])
        # Scope this notice to the governed restriction, not all management
        # attribution (e.g. standalone price/volume growth contributions).
        if any(x.value == 'COMBINED_COMPONENT_NOT_SPLIT' for x in a.limitations):
            limitations.append(SAFE_LIMITATIONS[1])
    return SynthesisDraft(draft_id='v2_governed_'+hashlib.sha256(bundle.question_id.encode()).hexdigest()[:16],
        question_id=bundle.question_id, answer=' '.join(x.text for x in claims),
        claims=tuple(claims), limitations=tuple(dict.fromkeys(limitations)))


def evidence_map(bundle):
    return {x.evidence_unit_id:x for x in bundle.retrieval.results
        if x.evidence_unit_id in bundle.selected_evidence_ids} if bundle.retrieval else {}


def compact_payload(bundle, observations=()):
    from .passage_representation import representation
    seed = governed_draft(bundle)
    a=bundle.analytics
    facts={f.fact_id:f for f in (a.primary_result,a.comparison_result,*a.decomposition_components) if f is not None} if a else {}
    from .completeness import requirements
    return {'question':bundle.plan.raw_question,'answer_requirements':requirements(bundle),
        'target':bundle.plan.model_dump(mode='json')['primary_target'],
        'operation':bundle.plan.operation.value,
        'numeric_claims':[{'id':x.claim_id,'label':facts[x.fact_ids[0]].reported_name,
            'metric':x.metric_id,'periods':x.periods,'value':str(x.value),'unit':x.unit,
            'provenance':x.claim_type.value,'fact_ids':x.fact_ids,
            'calculation_run_ids':x.calculation_run_ids,'evidence_ids':x.evidence_ids} for x in seed.claims],
        'limitations':seed.limitations,
        'documents':[{**representation(x,budget=4096),
            'type':x.evidence_unit_type.value,'relevance':x.evidence_relevance.value,
            'authenticity':authenticity(x).value,
            'company':x.company_id,'scope':x.business_scopes,'metric':x.metric_ids,
            'periods':x.reporting_periods,'hash':x.content_hash} for x in evidence_map(bundle).values()],
        'diagnostics':[{'action':x.action.value,'ranked_fact_ids':[f.fact_id for f in x.result.ranked_components],
            'reconciliation':[r.model_dump(mode='json') for r in x.result.reconciliation_results]} for x in observations],
        'conflicts':bundle.conflict_notes}


def compose(bundle, output, *, fixture_mode=False):
    seed = governed_draft(bundle)
    claims = list(seed.claims)
    documents = evidence_map(bundle)
    typed=[]
    for c in ((output.direct_answer,) if output.direct_answer is not None else ()) + output.context:
        if not set(c.evidence_ids).issubset(documents):
            raise ValueError('Context citation outside selected governed evidence')
        if c.kind is ContextKind.QUOTE and not all(c.text in documents[e].text for e in c.evidence_ids):
            raise ValueError('Quote must be an exact supported passage')
        target = bundle.plan.primary_target
        claims.append(Claim(claim_id=f'claim_{len(claims)+1:03d}',
            claim_type=ClaimType.REPORTED if c.kind is ContextKind.QUOTE else ClaimType.LIMITATION if c.kind is ContextKind.LIMITATION else ClaimType.INTERPRETATION,
            text=c.text, company_id=target.company.value if target else None,
            metric_id=target.metric_id.value if target and target.metric_id else None,
            business_scope=target.business_scope if target else None,
            periods=(target.period.value,) if target and target.period else (), evidence_ids=c.evidence_ids))
        role=ComponentRole.LIMITATION if c.kind is ContextKind.LIMITATION else ComponentRole.DIRECT_ANSWER if c is output.direct_answer else ComponentRole.SUPPORTING_CONTEXT
        auth=Authenticity.SYNTHETIC_FIXTURE if any(authenticity(documents[e]) is Authenticity.SYNTHETIC_FIXTURE for e in c.evidence_ids) else Authenticity.PUBLIC_REPORT
        typed.append(AnswerComponent(claim_id=claims[-1].claim_id,role=role,authenticity=auth,
            evidence_ids=c.evidence_ids,source_quotation=c.kind is ContextKind.QUOTE))
    limitations = seed.limitations
    from .completeness import requirements
    if requirements(bundle)['documentary_required'] and any(x.source_id.startswith('synthetic_') for x in documents.values()):
        limitations += ('Documentary context uses labelled synthetic development evidence, not issuer statements.',)
    if seed.claims and output.direct_answer is None and not output.context:
        limitations += (SAFE_LIMITATIONS[2],) if bundle.retrieval is not None else ()
    if not claims:
        raise ValueError('No supported content on documentary-only route')
    return TypedDraft(**{**seed.model_dump(),'claims':tuple(claims),'answer':' '.join(x.text for x in claims),
        'limitations':limitations,'components':tuple(typed),'fixture_mode':fixture_mode})


def needs_critic(draft, bundle):
    """Semantic review only; canonical arithmetic is owned by the verifier.

    Canonical management-attributed labels with closed caveats are not an
    explanation. Additional narrative or cross-source synthesis is reviewable.
    """
    from .release_policy import review_required
    return review_required(draft,bundle)


def surgical_patch(draft, bundle, feedback, *, completion_candidate=None):
    """Closed edits only; no full regeneration, novel numbers or new prose."""
    originals = {c.claim_id:c for c in draft.claims}
    canonical = {c.claim_id:c for c in governed_draft(bundle).claims}
    docs = evidence_map(bundle)
    replacements = dict(originals)
    typed = {c.claim_id:c for c in getattr(draft,'components',())}
    limitations = list(draft.limitations)
    for edit in feedback.corrections:
        if edit.claim_id not in originals:
            raise ValueError('Unknown disputed claim')
        c = originals[edit.claim_id]
        if edit.operation.value not in PERMITTED_CORRECTIONS[edit.issue.value]:
            raise ValueError('Correction does not address a typed issue')
        if edit.operation is CorrectionOperation.ADD_MISSING_ANSWER_COMPONENT:
            # Semantic Review Agent identifies the component/source, not prose.
            # Restore only an already model-constructed exact-source answer.
            from .completeness import substantive
            candidate=completion_candidate
            if candidate is None or candidate.kind is not ContextKind.QUOTE or not substantive(candidate.text):
                raise ValueError('No supported Synthesis component available for surgical completion')
            if edit.evidence_id not in candidate.evidence_ids or any(e not in docs or candidate.text not in docs[e].text for e in candidate.evidence_ids):
                raise ValueError('Completion candidate outside exact selected source')
            constructed=compose(bundle,CompactSynthesis(context=(),direct_answer=candidate),fixture_mode=getattr(draft,'fixture_mode',False))
            new=constructed.claims[-1]
            new=new.model_copy(update={'claim_id':f'claim_{max(int(x.split("_")[1]) for x in replacements)+1:03d}'})
            replacements={new.claim_id:new,**replacements} if not bundle.analytics else {**replacements,new.claim_id:new}
            typed[new.claim_id]=constructed.components[-1].model_copy(update={'claim_id':new.claim_id})
        elif edit.operation is CorrectionOperation.RESTORE_NUMERIC:
            if edit.claim_id not in canonical or canonical[edit.claim_id].value is None or edit.evidence_id is not None:
                raise ValueError('No canonical numeric restoration')
            replacements[edit.claim_id] = canonical[edit.claim_id]
        elif edit.operation is CorrectionOperation.DROP_CLAIM:
            if c.value is not None:
                raise ValueError('Required governed numeric claims cannot be dropped')
            if edit.evidence_id is not None and (edit.evidence_id not in docs
                    or edit.evidence_id not in c.evidence_ids):
                raise ValueError('Drop evidence must bind the disputed selected claim')
            del replacements[edit.claim_id]
            typed.pop(edit.claim_id,None)
        elif edit.operation is CorrectionOperation.REBIND_QUOTE:
            item = docs.get(edit.evidence_id)
            if c.value is not None or item is None or c.text not in item.text:
                raise ValueError('Citation correction must bind an exact existing quote')
            replacements[edit.claim_id] = c.model_copy(update={'evidence_ids':(edit.evidence_id,)})
            if edit.claim_id in typed:
                typed[edit.claim_id]=typed[edit.claim_id].model_copy(update={'evidence_ids':(edit.evidence_id,)})
        else:
            if edit.evidence_id is not None:
                raise ValueError('Limitation is a closed governance template')
            required = governed_draft(bundle).limitations
            if not set(required)-set(limitations):
                raise ValueError('Requested governance limitation is already present')
            limitations.extend(required)
    update={'claims':tuple(replacements.values()),
        'answer':' '.join(c.text for c in replacements.values()),
        'limitations':tuple(dict.fromkeys(limitations)), 'revision_number':1}
    if hasattr(draft,'components'):update['components']=tuple(typed.values())
    return draft.model_copy(update=update)


def safe_reviewed_subset(draft, bundle):
    """After targeted review/patch, retain untouched exact non-risky quotations.

    No approval of free-form residual interpretation, missing governance caveats
    or altered canonical numbers. The final deterministic verifier still runs.
    """
    from .release_policy import review_required
    return bool(draft.claims) and not review_required(draft,bundle)
