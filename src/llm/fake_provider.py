"""Deterministic structured provider for tests and reproducible local evaluation."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from typing import Any, TypeVar

from pydantic import BaseModel

from src.orchestration.models import (
    Claim,
    ClaimType,
    EvidenceBundle,
    ProviderResult,
    SynthesisDraft,
    TokenUsage,
)
from src.schemas.models import ProvenanceType
from src.retrieval.models import EvidenceRelevance


T = TypeVar("T", bound=BaseModel)


def _display(value: Decimal) -> str:
    return format(value, "f")


class DeterministicFakeProvider:
    """A fake provider with optional first-draft faults; revision is always clean."""

    name = "deterministic_fake"
    model = "governed-template-v1"

    def __init__(self, fault_by_question_id: dict[str, str] | None = None):
        self.fault_by_question_id = fault_by_question_id or {}
        self.generated: list[SynthesisDraft] = []

    def generate_structured(
        self, *, role: str, prompt: str, payload: dict[str, Any], output_model: type[T],
        prompt_version: str, revision: bool = False,
    ) -> ProviderResult:
        if output_model is not SynthesisDraft:
            raise TypeError("fake provider currently supports SynthesisDraft only")
        bundle = payload["evidence_bundle"]
        if not isinstance(bundle, EvidenceBundle):
            bundle = EvidenceBundle.model_validate(bundle)
        draft = self._draft(bundle, revision=revision)
        fault = None if revision else self.fault_by_question_id.get(bundle.question_id)
        if fault:
            draft = self._inject(draft, fault)
        self.generated.append(draft)
        encoded_in = json.dumps(payload, default=str, sort_keys=True)
        encoded_out = draft.model_dump_json()
        usage = TokenUsage(
            input_tokens=max(1, len(encoded_in) // 4),
            output_tokens=max(1, len(encoded_out) // 4),
            estimated_cost_usd=Decimal("0"),
        )
        return ProviderResult(
            value=draft, usage=usage, provider_name=self.name,
            provider_model=self.model, prompt_version=prompt_version,
        )

    def _draft(self, bundle: EvidenceBundle, *, revision: bool) -> SynthesisDraft:
        claims: list[Claim] = []
        analytics = bundle.analytics
        if analytics:
            facts = [analytics.primary_result]
            if analytics.comparison_result:
                facts.append(analytics.comparison_result)
            facts.extend(analytics.decomposition_components)
            seen: set[int] = set()
            for fact in facts:
                if fact.fact_id in seen:
                    continue
                seen.add(fact.fact_id)
                claim_type = (
                    ClaimType.MANAGEMENT_ATTRIBUTED
                    if fact.provenance_type is ProvenanceType.MANAGEMENT_ATTRIBUTED
                    else ClaimType.REPORTED
                )
                prefix = "Management reported the bridge contribution" if claim_type is ClaimType.MANAGEMENT_ATTRIBUTED else "The reported value was"
                claims.append(Claim(
                    claim_id=f"claim_{len(claims)+1:03d}", claim_type=claim_type,
                    text=f"{prefix} {_display(fact.value)} {fact.unit.value} for {fact.reported_name}.",
                    company_id=fact.company.value, metric_id=fact.metric_id.value,
                    business_scope=fact.business_scope, periods=(fact.period.value,),
                    value=fact.value, unit=fact.unit.value, fact_ids=(fact.fact_id,),
                    evidence_ids=fact.evidence_ids,
                ))
            calculations = (
                ("absolute change", analytics.absolute_change),
                ("percentage change", analytics.percentage_change),
                ("percentage-point change", analytics.percentage_point_change),
            )
            for label, value in calculations:
                if value is None:
                    continue
                unit = "percentage_point" if "percentage-point" in label else (
                    "percent" if label == "percentage change" else analytics.primary_result.unit.value
                )
                matching = tuple(
                    run.run_id for run in analytics.calculation_runs
                    if run.result_value == value
                )
                if not matching:
                    matching = analytics.calculation_run_ids
                claims.append(Claim(
                    claim_id=f"claim_{len(claims)+1:03d}", claim_type=ClaimType.CALCULATED,
                    text=f"The calculated {label} was {_display(value)} {unit}.",
                    company_id=analytics.primary_result.company.value,
                    metric_id=analytics.primary_result.metric_id.value,
                    business_scope=analytics.primary_result.business_scope,
                    periods=tuple(x.period.value for x in facts[:2]), value=value, unit=unit,
                    fact_ids=tuple(x.fact_id for x in facts[:2]), calculation_run_ids=matching,
                    evidence_ids=analytics.evidence_ids,
                ))
        if bundle.retrieval:
            existing_evidence = {eid for claim in claims for eid in claim.evidence_ids}
            for item in bundle.retrieval.results:
                if item.evidence_unit_id not in bundle.selected_evidence_ids or item.evidence_unit_id in existing_evidence:
                    continue
                injection_markers = ("ignore system", "system prompt", "call analytics", "reveal secrets", "execute tool")
                if item.evidence_relevance is EvidenceRelevance.DEFINITION and not any(marker in item.text.lower() for marker in injection_markers):
                    safe_summary = "The source defines the metric as follows: " + " ".join(item.text.split())[:500]
                else:
                    safe_summary = f"The source discusses {item.section} for the governed company, period, scope, and metric."
                claims.append(Claim(
                    claim_id=f"claim_{len(claims)+1:03d}", claim_type=ClaimType.REPORTED,
                    text=safe_summary, company_id=item.company_id,
                    metric_id=item.metric_ids[0] if item.metric_ids else None,
                    business_scope=item.business_scopes[0] if item.business_scopes else None,
                    periods=item.reporting_periods, evidence_ids=(item.evidence_unit_id,),
                ))
                break
        limitations = []
        if analytics:
            limitations.extend(item.value for item in analytics.limitations)
            limitations.extend(item.value for item in analytics.warnings)
        answer = " ".join(claim.text for claim in claims)
        identity = hashlib.sha256((bundle.question_id + answer + str(revision)).encode()).hexdigest()[:16]
        return SynthesisDraft(
            draft_id=f"draft_{identity}", question_id=bundle.question_id,
            answer=answer or "No supported claim could be produced from the governed evidence.",
            claims=tuple(claims), limitations=tuple(dict.fromkeys(limitations)),
            revision_number=1 if revision else 0,
        )

    @staticmethod
    def _inject(draft: SynthesisDraft, fault: str) -> SynthesisDraft:
        if not draft.claims:
            return draft
        claims = list(draft.claims)
        target_index = 0
        if fault == "causal_overstatement":
            target_index = next((i for i, claim in enumerate(claims) if claim.claim_type is ClaimType.MANAGEMENT_ATTRIBUTED), 0)
        target = claims[target_index]
        changes: dict[str, Any] = {}
        if fault == "wrong_number" and target.value is not None:
            changes["value"] = target.value + Decimal("1")
        elif fault == "wrong_unit": changes["unit"] = "USD_million"
        elif fault == "wrong_period": changes["periods"] = ("Q1_1999",)
        elif fault == "wrong_scope": changes["business_scope"] = "wrong_scope"
        elif fault == "wrong_company": changes["company_id"] = "wrong_company"
        elif fault == "wrong_metric": changes["metric_id"] = "wrong_metric"
        elif fault == "provenance_relabel": changes["claim_type"] = ClaimType.CALCULATED
        elif fault == "causal_overstatement": changes["text"] = "This caused the reported outcome."
        elif fault == "missing_citation": changes["evidence_ids"] = ()
        elif fault == "wrong_citation": changes["evidence_ids"] = ("eu_000000000000000000000000",)
        elif fault == "calculated_without_lineage": changes["claim_type"] = ClaimType.CALCULATED; changes["calculation_run_ids"] = ()
        else: changes["text"] = target.text + " Unsupported interpretation."
        claims[target_index] = target.model_copy(update=changes)
        return draft.model_copy(update={"claims": tuple(claims), "answer": " ".join(c.text for c in claims)})
