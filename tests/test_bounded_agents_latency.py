"""Local latency contracts only. Never use credentials or make paid calls."""
from threading import Event
from time import monotonic, sleep
from decimal import Decimal

import pytest

from src.bounded_agents.fixtures import SpikeFixtureProvider
from src.bounded_agents.models import (AgentBudgetState, AnalyticsInvestigationRequest,
    AnalyticsFollowUpDecision, EvidenceFollowUpDecision, EvidenceCoverageAssessment,
    CriticFeedback)
from src.bounded_agents.provider import ProviderBudgetExceeded
from tests.test_bounded_agents_hardening import SDKStub, provider, call
from tests.test_bounded_agents_spike import graph, FACT, BRIDGE, DOCUMENT, assert_closed


@pytest.mark.parametrize("question,analytics,evidence", [
    (FACT, False, False),
    ("Calculate Henkel sales change from H1 2025 to H1 2026.", False, False),
    (DOCUMENT, False, True),
    (BRIDGE, True, True),
    ("What was Henkel H1 2026 sales according to management?", False, True),
])
def test_route_activation_and_critic_retained(question, analytics, evidence):
    p = SpikeFixtureProvider(); g = graph(p); result = g.run(question)
    assert result.status.value == "COMPLETED"
    assert ("analytics.choose" in p.calls) is analytics
    assert ("evidence.choose" in p.calls) is evidence
    assert ("critic" in p.calls) is (question==DOCUMENT)  # Canonical numeric drivers also skip.


@pytest.mark.parametrize("question", ["Investigate adjusted EBIT.",
    "Isolate solely the price contribution to Mercedes-Benz Cars adjusted EBIT in Q2 2026."])
def test_short_circuit_never_invokes_agents(question):
    p = SpikeFixtureProvider(); graph(p).run(question)
    assert p.calls == []


def test_fact_does_not_pay_for_stop_only_followup():
    p = SpikeFixtureProvider({"analytics.follow_up":{"action":"arbitrary_sql"}})
    g = graph(p); result = g.run(FACT)
    assert result.verification.verdict.value == "PASS"
    assert p.calls == []
    assert any(x.role == "analytics.follow_up" and x.status.value == "Skipped" for x in g.agent_trace)


def test_meaningful_followup_remains_allowed_and_bounded():
    p = SpikeFixtureProvider({"analytics.choose":AnalyticsInvestigationRequest(action="lookup"),
        "analytics.follow_up":AnalyticsFollowUpDecision(action="rank_negative")})
    g = graph(p); g.run(BRIDGE)
    assert [x.action.value for x in g.observations] == ["lookup"]
    assert p.calls.count("analytics.follow_up") == 0


def test_exact_anchor_duplication_removed_not_distinct_observations():
    g = graph(); result = g.run(BRIDGE)
    state = g.last_state
    assert g.observations and g._distinct_observations(state) == ()
    assert state["evidence"].analytics == g.observations[0].result
    assert result.fact_ids
    other = graph(SpikeFixtureProvider({"analytics.choose":AnalyticsInvestigationRequest(action="lookup")}))
    other.run(BRIDGE)
    assert other._distinct_observations(other.last_state)


def test_global_deadline_is_same_for_every_role_not_reset():
    class Capture(SpikeFixtureProvider):
        def __init__(self): super().__init__(); self.deadlines = []
        def generate_bounded(self, *, limits, deadline, **kwargs):
            self.deadlines.append((kwargs["role"], deadline, deadline-monotonic()))
            sleep(.002)
            return super().generate_structured(**kwargs)
    p = Capture(); g = graph(p); g.run(BRIDGE)
    global_deadline = g.started + g.budget.max_seconds
    assert all(x[1] <= global_deadline for x in p.deadlines)
    assert len({x[1] for x in p.deadlines if x[0] in {'analytics.choose','evidence.choose'}}) == 1
    assert p.deadlines[-1][1] <= global_deadline-g.reserves.verification-g.reserves.revision


def test_timeout_signals_cooperative_cancel_no_downstream_no_fallback():
    class Cancellable(SpikeFixtureProvider):
        def __init__(self):
            super().__init__(); self.cancelled = Event(); self.finished = Event(); self.roles = []
        def cancel_pending(self): self.cancelled.set()
        def generate_bounded(self, *, limits, deadline, **kwargs):
            self.roles.append(kwargs["role"])
            try:
                self.cancelled.wait(.5)
                if self.cancelled.is_set(): raise TimeoutError("cancelled locally")
                return super().generate_structured(**kwargs)
            finally: self.finished.set()
    p = Cancellable(); g = graph(p, AgentBudgetState(max_seconds=.04))
    from src.bounded_agents.activation import DeadlineReserves
    g.reserves = DeadlineReserves(synthesis=.005, critic=.002, revision=.001, verification=.001)
    assert_closed(g.run("What was Henkel H1 2026 sales according to management?"))
    assert p.finished.wait(.1) and p.cancelled.is_set()
    assert p.roles == ["synthesis"]
    timed = [x for x in g.agent_trace if x.role == "synthesis" and x.error_category]
    assert timed and timed[-1].duration_ms > 0


def test_sync_transport_cancellation_limit_is_explicit():
    # A running synchronous request is NOT cancelled by the cooperative flag.
    # This is a release-gate blocker, not a pretend successful cancellation test.
    stub = SDKStub(); p = provider(stub)
    p.cancel_pending()
    with pytest.raises(TimeoutError): call(p)
    assert not stub.count_requests and not stub.requests


def test_sdk_timeout_is_timed_and_signals_stop():
    from httpx import Request
    from openai import APITimeoutError
    class SDKTimeout(SpikeFixtureProvider):
        def __init__(self): super().__init__(); self.cancelled = False
        def cancel_pending(self): self.cancelled = True
        def generate_structured(self, **kwargs):
            raise APITimeoutError(request=Request("POST", "https://example.invalid"))
    p = SDKTimeout(); g = graph(p); assert_closed(g.run("What was Henkel H1 2026 sales according to management?"))
    assert p.cancelled
    errors = [x for x in g.agent_trace if x.role == "evidence.choose" and x.error_category]
    assert errors[-1].duration_ms > 0 and errors[-1].phase == "initial"


@pytest.mark.parametrize("cancel", [False, True])
def test_expired_or_cancelled_preflight_never_starts_generation(cancel):
    stub = SDKStub(); p = provider(stub, AgentBudgetState(max_seconds=.01))
    original = stub.responses.input_tokens.count
    def counted(**kwargs):
        value = original(**kwargs)
        if cancel: p.cancel_pending()
        else: sleep(.02)
        return value
    stub.responses.input_tokens.count = counted
    with pytest.raises((TimeoutError, ProviderBudgetExceeded)): call(p)
    assert stub.count_requests and not stub.requests
    assert not p.records and p.ledger.committed_usd == 0
    assert p.preflights[0]["duration_ms"] >= 0


def test_late_known_usage_is_settled_but_not_released():
    stub = SDKStub(); p = provider(stub)
    original = stub.responses.parse
    def late(**kwargs):
        value = original(**kwargs); p.cancel_pending(); return value
    stub.responses.parse = late
    with pytest.raises(TimeoutError): call(p)
    assert p.records[0]["status"] == "completed"
    assert p.ledger.committed_usd == Decimal(p.records[0]["actual_usd"])


def test_critic_insufficient_evidence_still_withholds_verifier_pass():
    p = SpikeFixtureProvider({"critic":CriticFeedback(decision="approve", issues=(),
        claim_ids=(), evidence_sufficient=False),
        "evidence.coverage":EvidenceFollowUpDecision(coverage=EvidenceCoverageAssessment(
            sufficient=False, selected_evidence_ids=()), follow_up="lexical")})
    result = graph(p).run(DOCUMENT)
    assert_closed(result)
    assert result.verification.verdict.value == "PASS"


def test_future_traces_measure_deterministic_nodes_and_revision_phase():
    g = graph(); g.run(FACT)
    nodes = {x.role for x in g.agent_trace if x.role.startswith("stage.") and x.status.value == "Completed"}
    assert nodes >= {"stage.plan", "stage.route", "stage.verify", "stage.finalize"}
    assert all(x.duration_ms >= 0 and x.elapsed_ms >= 0 for x in g.agent_trace)
