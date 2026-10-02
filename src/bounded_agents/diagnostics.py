"""Sanitized operational failure categories; never exception text/input/prompts."""
import json
from pydantic import ValidationError
from openai import APITimeoutError, BadRequestError
from src.llm.base import ProviderMalformedOutputError
from src.orchestration.tools import ToolAuthorizationError
from .models import AgentFailureCategory


def failure_category(error):
    if isinstance(error, (TimeoutError, APITimeoutError)):
        return AgentFailureCategory.TIMEOUT
    if isinstance(error, ValidationError):
        if any(item["type"] == "json_invalid" for item in error.errors(include_input=False, include_context=False, include_url=False)):
            return AgentFailureCategory.MALFORMED_OUTPUT
        return AgentFailureCategory.SCHEMA_FAILURE
    if isinstance(error, BadRequestError) and getattr(error, "code", None) == "invalid_json_schema":
        return AgentFailureCategory.SCHEMA_FAILURE
    if isinstance(error, (ProviderMalformedOutputError, json.JSONDecodeError)):
        return AgentFailureCategory.MALFORMED_OUTPUT
    if isinstance(error, ToolAuthorizationError):
        return AgentFailureCategory.POLICY_REJECTION
    if type(error).__name__ in {"BudgetExceeded", "ProviderBudgetExceeded"}:
        return AgentFailureCategory.BUDGET_EXCEEDED
    return AgentFailureCategory.PROVIDER_FAILURE
