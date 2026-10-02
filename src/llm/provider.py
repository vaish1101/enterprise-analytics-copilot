"""Environment-selected provider construction without secret persistence."""

from __future__ import annotations

import os

from .base import ProviderConfigurationError, StructuredLLMProvider
from .fake_provider import DeterministicFakeProvider
from .openai_provider import OpenAIStructuredProvider


def provider_from_environment(*, allow_fake: bool = False) -> StructuredLLMProvider:
    name = os.getenv("LLM_PROVIDER", "").strip().lower()
    if name == "openai":
        return OpenAIStructuredProvider(
            model=os.getenv("LLM_MODEL") or None,
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
            max_retries=0,
        )
    if name == "fake" and allow_fake:
        return DeterministicFakeProvider()
    if not name:
        raise ProviderConfigurationError("LLM_PROVIDER is not configured")
    raise ProviderConfigurationError(f"unsupported LLM_PROVIDER: {name}")
