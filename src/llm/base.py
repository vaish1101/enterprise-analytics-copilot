"""Provider-neutral structured generation contract."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from src.orchestration.models import ProviderResult


T = TypeVar("T", bound=BaseModel)


class ProviderError(RuntimeError): pass
class ProviderRetryableError(ProviderError): pass
class ProviderMalformedOutputError(ProviderRetryableError): pass
class ProviderRefusalError(ProviderError): pass
class ProviderConfigurationError(ProviderError): pass


class StructuredLLMProvider(Protocol):
    name: str
    model: str

    def generate_structured(
        self, *, role: str, prompt: str, payload: dict[str, Any], output_model: type[T],
        prompt_version: str, revision: bool = False,
    ) -> ProviderResult: ...
