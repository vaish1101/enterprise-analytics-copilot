"""Single request-local release authority; never a model-supplied record."""
from enum import Enum
from .models import Contract
from pydantic import model_validator


class ReleaseMode(str, Enum):
    FULL = 'FULL'
    PARTIAL = 'PARTIAL'
    WITHHELD = 'WITHHELD'
    CLARIFICATION = 'CLARIFICATION'


class ReleaseRecord(Contract):
    release_mode: ReleaseMode
    verification_status: str | None
    verification_id: str | None
    parent_verification_id: str | None = None
    released_claim_ids: tuple[str, ...] = ()
    withheld_claim_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    useful: bool = False

    @model_validator(mode='after')
    def release_requires_pass(self):
        if self.release_mode in {ReleaseMode.FULL,ReleaseMode.PARTIAL}:
            if self.verification_status!='PASS' or not self.verification_id or not self.released_claim_ids or not self.useful:
                raise ValueError('Released record requires its own passing verification and useful claims')
        elif self.released_claim_ids:
            raise ValueError('Withheld or clarification record cannot release claims')
        if set(self.released_claim_ids)&set(self.withheld_claim_ids):
            raise ValueError('Released and withheld identities must be disjoint')
        return self


def diagnostics(graph, brief):
    state = getattr(graph, 'last_state', {}) or getattr(graph,'last_observed_state',{})
    bundle = state.get('evidence')
    draft = graph.verified_draft or state.get('draft')
    retrieval = bundle.retrieval if bundle else None
    verification = graph.parent_verification or brief.verification
    checks = {c.claim_id:c for c in verification.claim_checks} if verification else {}
    def domain(numeric):
        claims = [c for c in draft.claims if (c.value is not None) == numeric] if draft else []
        released = [c.claim_id for c in brief.claims if (c.value is not None) == numeric]
        from .completeness import requirements
        applicable=bool(claims or (graph.observations if numeric else bundle and requirements(bundle)['documentary_required']))
        return {'claim_ids':[c.claim_id for c in claims],
            'checks':[checks[c.claim_id].model_dump(mode='json') for c in claims if c.claim_id in checks],
            'released_claim_ids':released,
            'release_status':'RELEASED' if released else 'WITHHELD_REVIEW_TIMEOUT' if not numeric and graph.review_timeout else 'WITHHELD',
            'status':'NOT_APPLICABLE' if not applicable else 'PASS' if claims and all(c.claim_id in checks and not checks[c.claim_id].errors for c in claims) else 'NOT_VERIFIED' if not checks else 'FAIL'}
    from .answer_contract import authenticity
    selected = list(bundle.selected_evidence_ids) if bundle else list(graph.selected or ())
    catalog = graph.knowledge_tool.retriever.unit_by_id
    observed_facts = list(dict.fromkeys(f.fact_id for o in graph.observations for f in
        (o.result.primary_result,o.result.comparison_result,*o.result.supporting_results,*o.result.decomposition_components) if f))
    return {'analytical':{**domain(True),'requested_operation':bundle.plan.operation.value if bundle else None,
        'actions':[o.action.value for o in graph.observations],
        'operations':[o.result.source_plan_operation.value for o in graph.observations],
        'fact_ids':observed_facts or list(dict.fromkeys(f for c in (draft.claims if draft else ()) for f in c.fact_ids)),
        'numeric_facts':list({f.fact_id:f.model_dump(mode='json') for o in graph.observations for f in
            (o.result.primary_result,o.result.comparison_result,*o.result.supporting_results,*o.result.decomposition_components) if f}.values()),
        'final_verification_status':brief.verification.verdict.value if brief.verification else None},
        'documentary':{**domain(False),'retrieval_strategy':list(retrieval.trace.retrieval_methods) if retrieval else [],
            'selected_evidence_ids':selected,
            'authenticity':{e:authenticity(catalog[e]).value for e in selected if e in catalog},
            'components':[c.model_dump(mode='json') for c in getattr(draft,'components',())],
            'review_required':graph.critic_needed,'review_timeout':graph.review_timeout,
            'synthesis_status':next((e.status.value for e in reversed(graph.agent_trace) if e.role=='stage.synthesize'),'NOT_INVOKED'),
            'review_requirement':getattr(graph,'review_requirement','SKIP'),
            'review_result':'UNAVAILABLE' if getattr(graph,'review_unavailable',False) else state['critic'].decision.value if 'critic' in state else 'ERROR' if graph.roles.get('critic',0) else 'NOT_INVOKED',
            'completion_repair_attempted':graph.completion_repair_attempted},
        'release':graph.release_record.model_dump(mode='json') if graph.release_record else None,
        'failures':[e.model_dump(mode='json') for e in graph.agent_trace if e.error_type],
        'provider_schema_errors':[f for f in getattr(graph.provider,'failures',()) if f.get('schema_errors')]}
