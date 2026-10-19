"""Scripted fixtures are not model reasoning or evidence of agentic value."""
from decimal import Decimal

from src.llm.fake_provider import DeterministicFakeProvider
from src.orchestration.models import ProviderResult, SynthesisDraft, TokenUsage

from .models import (AnalyticsAction, AnalyticsInvestigationRequest,
    AnalyticsFollowUpDecision, EvidenceSearchRequest, EvidenceSearchStrategy,
    EvidenceFollowUpDecision, EvidenceCoverageAssessment, CriticFeedback, CriticDecision)
from .post_synthesis import CompactSynthesis, ContextStatement, ActionableCritic


class SpikeFixtureProvider(DeterministicFakeProvider):
    def __init__(self, fixtures=None, **kwargs):
        super().__init__(**kwargs)
        self.fixtures = fixtures or {}
        self.calls = []

    def generate_structured(self, *, role, prompt, payload, output_model, prompt_version, revision=False):
        from .source_ownership import SourceSynthesis
        if issubclass(output_model, SourceSynthesis):
            configured=self.fixtures.get(role)
            if isinstance(configured,dict) and ('numeric_fact_ids' in configured or configured.get('direct_answer',{} ) is not None and configured.get('direct_answer',{}).get('kind')=='source'):
                self.calls.append(role)
                return ProviderResult(value=output_model.model_validate_json(__import__('json').dumps(configured)),
                    usage=TokenUsage(input_tokens=100,output_tokens=25,estimated_cost_usd=Decimal('0')),
                    provider_name=self.name,provider_model=self.model,prompt_version=prompt_version)
            # Legacy fixtures remain useful for adversarial tests; this adapter
            # is fake-only and is never used by a live provider.
            old = self.generate_structured(role=role,prompt=prompt,payload=payload,
                output_model=CompactSynthesis,prompt_version=prompt_version,revision=revision)
            value = CompactSynthesis.model_validate_json(old.value.model_dump_json()) if hasattr(old.value,'model_dump_json') else CompactSynthesis.model_validate(old.value)
            def selection(c):
                if c is None:return None
                if c.kind.value == 'quote':
                    docs={d['id']:d for d in payload['documents']}
                    if any(e not in docs or c.text not in docs[e]['text'] for e in c.evidence_ids):
                        raise ValueError('Invalid legacy fixture quote')
                    return {'kind':'source','text':None,'evidence_ids':c.evidence_ids}
                return {'kind':c.kind.value,'text':c.text,'evidence_ids':c.evidence_ids}
            result={'direct_answer':selection(value.direct_answer),
                'context':[selection(c) for c in value.context]}
            if 'numeric_fact_ids' in output_model.model_fields:result['numeric_fact_ids']=payload['numeric_fact_ids']
            return old.model_copy(update={'value':output_model.model_validate_json(__import__('json').dumps(result))})
        self.calls.append(role)
        if output_model is CompactSynthesis:
            configured=self.fixtures.get(role)
            if configured is None:
                docs=payload['documents']
                required=payload.get('answer_requirements',{}).get('documentary_required',False)
                if required and docs and 'Governed definition and reporting context.' not in docs[0]['text']:
                    text=docs[0]['text']
                    # Deterministic fake output only; not model-value evidence.
                    if text.startswith('Synthetic development') and '. ' in text:
                        text=text.split('. ',1)[1]
                    configured=CompactSynthesis(direct_answer=ContextStatement(kind='quote',text=text,evidence_ids=(docs[0]['id'],)),context=())
                context=() if payload['numeric_claims'] and not self.fixtures.get('critic') else tuple(ContextStatement(
                    kind='limitation' if x['source_id'].startswith('synthetic_') else 'quote',
                    text='The selected synthetic development source does not establish the official metric definition.'
                    if x['source_id'].startswith('synthetic_') else x['text'], evidence_ids=(x['id'],)) for x in docs[:1])
                configured=configured or CompactSynthesis(context=context)
            if self.fault_by_question_id:
                configured={'context':[], 'numeric_override':'forbidden'}
            return ProviderResult(value=configured,usage=TokenUsage(input_tokens=100,output_tokens=25,
                estimated_cost_usd=Decimal('0')),provider_name=self.name,provider_model=self.model,prompt_version=prompt_version)
        if output_model is ActionableCritic:
            configured=self.fixtures.get(role)
            if isinstance(configured,list):
                configured=configured[min(self.calls.count(role)-1,len(configured)-1)]
            configured=configured if configured is not None else ActionableCritic(
                decision='approve',issues=(),claim_ids=(),evidence_sufficient=True,corrections=())
            return ProviderResult(value=configured,usage=TokenUsage(input_tokens=100,output_tokens=25,
                estimated_cost_usd=Decimal('0')),provider_name=self.name,provider_model=self.model,prompt_version=prompt_version)
        if output_model is SynthesisDraft:
            return super().generate_structured(role=role, prompt=prompt, payload=payload,
                output_model=output_model, prompt_version=prompt_version, revision=revision)
        configured = self.fixtures.get(role)
        if isinstance(configured, list):
            configured = configured[min(self.calls.count(role)-1, len(configured)-1)]
        defaults = {
            AnalyticsInvestigationRequest: lambda: AnalyticsInvestigationRequest(action=AnalyticsAction.TASK),
            AnalyticsFollowUpDecision: lambda: AnalyticsFollowUpDecision(action=AnalyticsAction.STOP),
            EvidenceSearchRequest: lambda: EvidenceSearchRequest(strategy=EvidenceSearchStrategy.HYBRID),
            EvidenceFollowUpDecision: lambda: EvidenceFollowUpDecision(coverage=EvidenceCoverageAssessment(
                sufficient=bool(payload["results"]), selected_evidence_ids=tuple(x.evidence_unit_id for x in payload["results"])), follow_up=None),
            CriticFeedback: lambda: CriticFeedback(decision=CriticDecision.APPROVE, issues=(), claim_ids=(),
                evidence_sufficient=payload["evidence_bundle"].retrieval is None or bool(payload["evidence_bundle"].selected_evidence_ids)),
        }
        base = next((model for model in defaults if issubclass(output_model, model)), output_model)
        value = configured if configured is not None else defaults[base]()
        return ProviderResult(value=value, usage=TokenUsage(input_tokens=100, output_tokens=25,
            estimated_cost_usd=Decimal("0")), provider_name=self.name, provider_model=self.model,
            prompt_version=prompt_version)
