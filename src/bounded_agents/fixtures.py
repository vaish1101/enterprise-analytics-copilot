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
        self.calls.append(role)
        if output_model is CompactSynthesis:
            configured=self.fixtures.get(role)
            if configured is None:
                docs=payload['documents']
                context=() if payload['numeric_claims'] and not self.fixtures.get('critic') else tuple(ContextStatement(
                    kind='limitation' if x['source_id'].startswith('synthetic_') else 'quote',
                    text='The selected synthetic development source does not establish the official metric definition.'
                    if x['source_id'].startswith('synthetic_') else x['text'], evidence_ids=(x['id'],)) for x in docs[:1])
                configured=CompactSynthesis(context=context)
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
