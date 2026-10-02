"""V2-only compact synthesis, canonical numbers and bounded surgical edits.

No numerical validator relaxation; no model-derived arithmetic or source truth.
"""
from enum import Enum
import hashlib
import re

from pydantic import Field, model_validator

from src.orchestration.models import Claim, ClaimType, SynthesisDraft
from src.schemas.models import ProvenanceType
from .models import Contract, CriticFeedback, CriticDecision, CriticIssue


class ContextKind(str, Enum):
    QUOTE = 'quote'
    INTERPRETATION = 'interpretation'
    LIMITATION = 'limitation'


class ContextStatement(Contract):
    kind: ContextKind
    text: str = Field(min_length=1, max_length=480)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=2)


class CompactSynthesis(Contract):
    # No model-owned number/value/unit/company/period/lineage fields.
    context: tuple[ContextStatement, ...] = Field(max_length=3)


class CorrectionOperation(str, Enum):
    DROP_CLAIM = 'drop_claim'
    RESTORE_NUMERIC = 'restore_numeric'
    REBIND_QUOTE = 'rebind_quote'
    ADD_LIMITATION = 'add_limitation'


class SurgicalCorrection(Contract):
    claim_id: str = Field(pattern=r'^claim_[0-9]{3}$')
    issue: CriticIssue
    operation: CorrectionOperation
    evidence_id: str | None = None


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
        if any(x.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED for x in claims):
            limitations.extend(SAFE_LIMITATIONS[:2])
    return SynthesisDraft(draft_id='v2_governed_'+hashlib.sha256(bundle.question_id.encode()).hexdigest()[:16],
        question_id=bundle.question_id, answer=' '.join(x.text for x in claims),
        claims=tuple(claims), limitations=tuple(dict.fromkeys(limitations)))


def evidence_map(bundle):
    return {x.evidence_unit_id:x for x in bundle.retrieval.results
        if x.evidence_unit_id in bundle.selected_evidence_ids} if bundle.retrieval else {}


def compact_payload(bundle, observations=()):
    seed = governed_draft(bundle)
    a=bundle.analytics
    facts={f.fact_id:f for f in (a.primary_result,a.comparison_result,*a.decomposition_components) if f is not None} if a else {}
    return {'question':bundle.plan.raw_question,
        'target':bundle.plan.model_dump(mode='json')['primary_target'],
        'operation':bundle.plan.operation.value,
        'numeric_claims':[{'id':x.claim_id,'label':facts[x.fact_ids[0]].reported_name,
            'metric':x.metric_id,'periods':x.periods,'value':str(x.value),'unit':x.unit,
            'provenance':x.claim_type.value,'fact_ids':x.fact_ids,
            'calculation_run_ids':x.calculation_run_ids,'evidence_ids':x.evidence_ids} for x in seed.claims],
        'limitations':seed.limitations,
        'documents':[{'id':x.evidence_unit_id,'text':x.text,'source_id':x.source_id,
            'type':x.evidence_unit_type.value,'relevance':x.evidence_relevance.value,
            'company':x.company_id,'scope':x.business_scopes,'metric':x.metric_ids,
            'periods':x.reporting_periods,'hash':x.content_hash} for x in evidence_map(bundle).values()],
        'diagnostics':[{'action':x.action.value,'ranked_fact_ids':[f.fact_id for f in x.result.ranked_components],
            'reconciliation':[r.model_dump(mode='json') for r in x.result.reconciliation_results]} for x in observations],
        'conflicts':bundle.conflict_notes}


def compose(bundle, output):
    seed = governed_draft(bundle)
    claims = list(seed.claims)
    documents = evidence_map(bundle)
    for c in output.context:
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
    limitations = seed.limitations
    if seed.claims and not output.context:
        limitations += (SAFE_LIMITATIONS[2],) if bundle.retrieval is not None else ()
    if not claims:
        raise ValueError('No supported content on documentary-only route')
    return seed.model_copy(update={'claims':tuple(claims),'answer':' '.join(x.text for x in claims),'limitations':limitations})


def needs_critic(draft, bundle):
    """Semantic review only; canonical arithmetic is owned by the verifier.

    Canonical management-attributed labels with closed caveats are not an
    explanation. Additional narrative or cross-source synthesis is reviewable.
    """
    canonical = {x.claim_id:x for x in governed_draft(bundle).claims}
    docs = evidence_map(bundle)
    for c in draft.claims:
        if c == canonical.get(c.claim_id):
            continue
        # Only exact non-risky metric definition quotes may skip semantic review.
        if (c.claim_type is ClaimType.REPORTED and c.value is None and c.evidence_ids
            and all(e in docs and docs[e].evidence_unit_type.value=='METRIC_DEFINITION'
                and not docs[e].source_id.startswith('synthetic_') and 'synthetic' not in docs[e].text.lower()
                and c.text in docs[e].text for e in c.evidence_ids)
            and len({docs[e].source_id for e in c.evidence_ids}) == 1
            and not CAUSAL_RISK.search(c.text)):
            continue
        return True
    allowed = set(governed_draft(bundle).limitations) | set(SAFE_LIMITATIONS)
    required = set(governed_draft(bundle).limitations)
    return not draft.claims or not required.issubset(draft.limitations) or any(x not in allowed for x in draft.limitations)


def surgical_patch(draft, bundle, feedback):
    """Closed edits only; no full regeneration, novel numbers or new prose."""
    originals = {c.claim_id:c for c in draft.claims}
    canonical = {c.claim_id:c for c in governed_draft(bundle).claims}
    docs = evidence_map(bundle)
    replacements = dict(originals)
    limitations = list(draft.limitations)
    for edit in feedback.corrections:
        if edit.claim_id not in originals:
            raise ValueError('Unknown disputed claim')
        c = originals[edit.claim_id]
        permitted = {
            'causal_overclaim':{'drop_claim','restore_numeric'},
            'unsupported_interpretation':{'drop_claim'},
            'misleading_attribution':{'drop_claim','restore_numeric','rebind_quote'},
            'missing_limitation':{'add_limitation'},
        }
        if edit.operation.value not in permitted[edit.issue.value]:
            raise ValueError('Correction does not address a typed issue')
        if edit.operation is CorrectionOperation.RESTORE_NUMERIC:
            if edit.claim_id not in canonical or edit.evidence_id is not None:
                raise ValueError('No canonical numeric restoration')
            replacements[edit.claim_id] = canonical[edit.claim_id]
        elif edit.operation is CorrectionOperation.DROP_CLAIM:
            if c.value is not None or edit.evidence_id is not None:
                raise ValueError('Required governed numeric claims cannot be dropped')
            del replacements[edit.claim_id]
        elif edit.operation is CorrectionOperation.REBIND_QUOTE:
            item = docs.get(edit.evidence_id)
            if c.value is not None or item is None or c.text not in item.text:
                raise ValueError('Citation correction must bind an exact existing quote')
            replacements[edit.claim_id] = c.model_copy(update={'evidence_ids':(edit.evidence_id,)})
        else:
            if edit.evidence_id is not None:
                raise ValueError('Limitation is a closed governance template')
            required = governed_draft(bundle).limitations
            if not set(required)-set(limitations):
                raise ValueError('Requested governance limitation is already present')
            limitations.extend(required)
    return draft.model_copy(update={'claims':tuple(replacements.values()),
        'answer':' '.join(c.text for c in replacements.values()),
        'limitations':tuple(dict.fromkeys(limitations)), 'revision_number':1})
