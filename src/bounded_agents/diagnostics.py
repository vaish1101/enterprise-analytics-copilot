"""Sanitized operational failure categories; never exception text/input/prompts."""
import json
from pydantic import ValidationError
from openai import APITimeoutError, BadRequestError
from src.llm.base import ProviderMalformedOutputError
from src.orchestration.tools import ToolAuthorizationError
from .models import AgentFailureCategory, FailureKind


def failure_category(error, *, stage=None):
    from .source_ownership import SynthesisContractError
    if isinstance(error, SynthesisContractError):
        return AgentFailureCategory.SCHEMA_FAILURE
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
    if stage == 'revise':
        return AgentFailureCategory.PATCH_EXECUTION_ERROR
    if stage is not None:
        return AgentFailureCategory.LOCAL_RUNTIME_ERROR
    return AgentFailureCategory.PROVIDER_FAILURE


def failure_kind(role, category):
    if category is AgentFailureCategory.TIMEOUT:
        return FailureKind.PROVIDER_TIMEOUT if role in {'analytics.choose','evidence.choose','synthesis','critic'} else FailureKind.LOCAL_RUNTIME_ERROR
    if category in {AgentFailureCategory.POLICY_REJECTION, AgentFailureCategory.BUDGET_EXCEEDED}:
        return FailureKind.POLICY_WITHHOLDING
    if category is AgentFailureCategory.PATCH_EXECUTION_ERROR or role in {'revise','stage.revise'}:
        return FailureKind.PATCH_EXECUTION_ERROR
    return {'analytics.choose':FailureKind.MODEL_DECISION_ERROR,
        'evidence.choose':FailureKind.RETRIEVAL_DECISION_ERROR,
        'evidence':FailureKind.RETRIEVAL_DECISION_ERROR,
        'synthesis':FailureKind.SYNTHESIS_ERROR,
        'synthesize':FailureKind.SYNTHESIS_ERROR,
        'critic':FailureKind.CRITIC_ERROR,
        'verifier':FailureKind.VERIFIER_REJECTION}.get(role,FailureKind.LOCAL_RUNTIME_ERROR)
