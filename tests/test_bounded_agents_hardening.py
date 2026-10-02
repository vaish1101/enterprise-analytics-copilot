"""Mocked SDK tests: hard request constraints without credentials or paid calls."""
from decimal import Decimal
from types import SimpleNamespace
import time

import pytest

from src.bounded_agents.models import AgentBudgetState, AnalyticsInvestigationRequest
from src.bounded_agents.planner import BoundedIntentPlanner
from src.bounded_agents.provider import BudgetedOpenAIProvider, SpendLedger, ProviderBudgetExceeded
from src.planning.planner import QuestionPlanner


class SDKStub:
    def __init__(self, counted=20, fail=False, output=10):
        self.counted = counted; self.fail = fail; self.output = output
        self.options = []; self.requests = []; self.count_requests = []
        self.responses = SimpleNamespace(input_tokens=SimpleNamespace(count=self.count), parse=self.parse)

    def with_options(self, **kwargs):
        self.options.append(kwargs); return self

    def count(self, **kwargs):
        self.count_requests.append(kwargs)
        return SimpleNamespace(input_tokens=self.counted)

    def parse(self, **kwargs):
        self.requests.append(kwargs)
        if self.fail: raise TimeoutError("unknown upstream outcome")
        return SimpleNamespace(status="completed", output_parsed=AnalyticsInvestigationRequest(action="task"),
            usage=SimpleNamespace(input_tokens=self.counted, output_tokens=self.output))


def provider(stub, limits=None, ledger=None):
    return BudgetedOpenAIProvider(model="explicit-test-model", input_rate=1,
        output_rate=2, ledger=ledger or SpendLedger(1), limits=limits, client=stub)


def call(p):
    return p.generate_structured(role="analytics.choose", prompt="typed decision",
        payload={"approved_actions":["task"]}, output_model=AnalyticsInvestigationRequest,
        prompt_version="test")


@pytest.mark.parametrize("phrase,direction", [("What helped", "LARGEST_POSITIVE"),
    ("What hurt", "LARGEST_NEGATIVE"), ("What had the biggest impact on", "ABSOLUTE_MAGNITUDE")])
def test_v2_routes_intents_without_changing_v1(phrase, direction):
    question = phrase + " Mercedes-Benz Cars adjusted EBIT in Q2 2026?"
    v1 = QuestionPlanner().plan(question); v2 = BoundedIntentPlanner().plan(question)
    assert v1.operation.value == "LOOKUP" and not v1.requires_decomposition
    assert v2.operation.value == "RANK_CONTRIBUTIONS"
    assert v2.ranking_direction.value == direction
    assert v2.primary_target == v1.primary_target and v2.raw_question == question


def test_provider_sends_hard_caps_timeout_and_no_retries():
    stub = SDKStub(); p = provider(stub, AgentBudgetState(max_output_tokens_per_call=64))
    result = call(p)
    assert stub.requests[0]["max_output_tokens"] == 64
    assert stub.requests[0]["store"] is False and stub.requests[0]["truncation"] == "disabled"
    assert stub.count_requests[0]["input"] == stub.requests[0]["input"]
    assert all(x["max_retries"] == 0 and 0 < x["timeout"] <= 30 for x in stub.options)
    assert result.usage.estimated_cost_usd == Decimal(".00004")
    assert p.committed_tokens == 30


def test_total_token_cap_reduces_output_allowance():
    stub = SDKStub(); p = provider(stub, AgentBudgetState(max_tokens=35, max_output_tokens_per_call=64))
    call(p)
    assert stub.requests[0]["max_output_tokens"] == 15
    with pytest.raises(ProviderBudgetExceeded): call(p)
    assert len(stub.requests) == 1


def test_input_limit_prevents_generation():
    stub = SDKStub(counted=100); p = provider(stub, AgentBudgetState(max_input_tokens_per_call=50))
    with pytest.raises(ProviderBudgetExceeded): call(p)
    assert not stub.requests


def test_spending_reservation_prevents_generation():
    stub = SDKStub(); p = provider(stub, ledger=SpendLedger(".000001"))
    with pytest.raises(ProviderBudgetExceeded): call(p)
    assert not stub.requests


def test_unknown_timeout_retains_full_reservation():
    stub = SDKStub(fail=True); ledger = SpendLedger(1)
    p = provider(stub, AgentBudgetState(max_output_tokens_per_call=64), ledger)
    with pytest.raises(TimeoutError): call(p)
    assert p.committed_tokens == 84
    assert ledger.committed_usd == Decimal(".000148")
    assert p.records[0]["status"] == "unknown"


def test_call_cap_counts_failed_attempts():
    p = provider(SDKStub(fail=True), AgentBudgetState(max_total_calls=1))
    with pytest.raises(TimeoutError): call(p)
    with pytest.raises(ProviderBudgetExceeded): call(p)
    assert p.calls == 1


def test_deadline_prevents_any_request():
    stub = SDKStub(); p = provider(stub); p.deadline = time.monotonic() - 1
    with pytest.raises(ProviderBudgetExceeded): call(p)
    assert not stub.count_requests and not stub.requests


def test_usage_over_cap_is_rejected():
    p = provider(SDKStub(output=100), AgentBudgetState(max_output_tokens_per_call=64))
    with pytest.raises(ProviderBudgetExceeded): call(p)


def test_missing_verified_pricing_cannot_run():
    with pytest.raises(Exception):
        BudgetedOpenAIProvider(model="test", input_rate=0, output_rate=1,
            ledger=SpendLedger(1), client=SDKStub())
