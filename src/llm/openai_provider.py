"""Optional OpenAI Structured Outputs provider. It is never required by tests."""

from __future__ import annotations

from decimal import Decimal
import json
import os
from typing import Any, TypeVar

from openai import APIConnectionError, APITimeoutError, BadRequestError, OpenAI, RateLimitError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.orchestration.models import Claim, ClaimType, ProviderResult, SynthesisDraft, TokenUsage
from .base import (
    ProviderConfigurationError, ProviderMalformedOutputError,
    ProviderRefusalError, ProviderRetryableError,
)


T = TypeVar("T", bound=BaseModel)


class _OpenAIClaim(BaseModel):
    """Structured-Outputs wire shape; Decimal's JSON-schema regex is unsupported."""

    model_config = ConfigDict(extra="forbid")
    claim_id: str = Field(pattern=r"^claim_[0-9]{3}$")
    claim_type: ClaimType
    text: str
    company_id: str | None
    metric_id: str | None
    business_scope: str | None
    periods: list[str]
    value: str | None
    unit: str | None
    fact_ids: list[int]
    calculation_run_ids: list[str]
    evidence_ids: list[str]


class _OpenAISynthesisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_id: str
    question_id: str
    answer: str
    claims: list[_OpenAIClaim]
    limitations: list[str]
    revision_number: int = Field(ge=0, le=1)


def _to_governed_draft(parsed: _OpenAISynthesisDraft) -> SynthesisDraft:
    """Keep only claims that satisfy the governed internal contract.

    The provider wire shape intentionally represents Decimal values as strings,
    and Structured Outputs cannot express all conditional lineage invariants.
    A malformed claim must not invalidate otherwise usable claims or leave its
    prose behind in the released answer.
    """
    valid_claims: list[Claim] = []
    removed = 0
    for item in parsed.claims:
        try:
            valid_claims.append(Claim.model_validate(item.model_dump(), strict=False))
        except ValidationError:
            removed += 1
    if not valid_claims:
        raise ProviderMalformedOutputError("provider returned no governed-valid claims")
    limitations = list(parsed.limitations)
    answer = parsed.answer
    if removed:
        limitations.append(f"{removed} malformed provider claim(s) were removed before verification.")
        answer = " ".join(claim.text for claim in valid_claims)
    return SynthesisDraft(
        draft_id=parsed.draft_id,
        question_id=parsed.question_id,
        answer=answer,
        claims=tuple(valid_claims),
        limitations=tuple(limitations),
        revision_number=parsed.revision_number,
    )


class OpenAIStructuredProvider:
    name = "openai"

    def __init__(self, *, model: str | None = None, timeout_seconds: float | None = None,
                 max_retries: int = 0, input_cost_per_million: Decimal | None = None,
                 output_cost_per_million: Decimal | None = None):
        if not os.getenv("OPENAI_API_KEY"):
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured")
        self.model = model or os.getenv("LLM_MODEL", "gpt-6-astra")
        self.timeout_seconds = timeout_seconds or float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        self.max_retries = max_retries
        self.input_cost_per_million = input_cost_per_million or Decimal(os.getenv("LLM_INPUT_COST_PER_MILLION", "0"))
        self.output_cost_per_million = output_cost_per_million or Decimal(os.getenv("LLM_OUTPUT_COST_PER_MILLION", "0"))
        self.client = OpenAI(max_retries=max_retries, timeout=self.timeout_seconds)

    def generate_structured(
        self, *, role: str, prompt: str, payload: dict[str, Any], output_model: type[T],
        prompt_version: str, revision: bool = False,
    ) -> ProviderResult:
        wire_model: type[BaseModel] = _OpenAISynthesisDraft if output_model is SynthesisDraft else output_model
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(payload, default=str, sort_keys=True)},
                ],
                text_format=wire_model,
            )
        except (APITimeoutError, RateLimitError, APIConnectionError) as error:
            raise ProviderRetryableError(type(error).__name__) from error
        except ValidationError as error:
            raise ProviderMalformedOutputError("structured output failed schema validation") from error
        except BadRequestError as error:
            raise ProviderConfigurationError("provider rejected the structured request") from error
        if response.output_parsed is None:
            refusal = any(getattr(item, "type", None) == "refusal" for item in getattr(response, "output", ()))
            if refusal:
                raise ProviderRefusalError("provider safety refusal")
            raise ProviderMalformedOutputError("provider returned empty or malformed structured output")
        usage = response.usage
        input_tokens = int(usage.input_tokens if usage else 0)
        output_tokens = int(usage.output_tokens if usage else 0)
        cost = (
            Decimal(input_tokens) * self.input_cost_per_million
            + Decimal(output_tokens) * self.output_cost_per_million
        ) / Decimal("1000000")
        parsed = response.output_parsed
        if output_model is SynthesisDraft:
            parsed = _to_governed_draft(parsed)
        return ProviderResult(
            value=parsed,
            usage=TokenUsage(
                input_tokens=input_tokens, output_tokens=output_tokens,
                estimated_cost_usd=cost,
            ),
            provider_name=self.name, provider_model=self.model, prompt_version=prompt_version,
        )
