"""New controlled release regressions; no held evaluations or paid provider calls."""
import pytest

from src.llm.fake_provider import DeterministicFakeProvider
from tests.test_step8_api import client, graph_factory


class ContradictoryProvider(DeterministicFakeProvider):
    def __init__(self, text, summary_only=False):
        super().__init__()
        self.text = text
        self.summary_only = summary_only

    def _draft(self, bundle, *, revision):
        draft = super()._draft(bundle, revision=revision)
        claims = draft.claims if self.summary_only else (
            draft.claims[0].model_copy(update={"text": self.text}), *draft.claims[1:],
        )
        return draft.model_copy(update={"claims": claims, "answer": self.text})


def test_omitting_structured_value_does_not_escape_prose_check():
    class MissingValueProvider(ContradictoryProvider):
        def _draft(self, bundle, *, revision):
            draft = super()._draft(bundle, revision=revision)
            return draft.model_copy(update={"claims": (draft.claims[0].model_copy(update={"value": None}),)})
    result = graph_factory(MissingValueProvider("Henkel sales were EUR 999 million.")).run("What were Henkel H1 2026 sales?", question_id="gate_a_missing_value")
    assert result.verification.verdict.value != "PASS" and not result.claims


def test_document_citation_does_not_authorize_unbound_financial_prose():
    class DocumentNumberProvider(DeterministicFakeProvider):
        def _draft(self, bundle, *, revision):
            draft = super()._draft(bundle, revision=revision)
            claims = tuple(claim.model_copy(update={"text": "Henkel sales were EUR 999 million."}) for claim in draft.claims)
            return draft.model_copy(update={"claims": claims, "answer": "Henkel sales were EUR 999 million."})
    result = graph_factory(DocumentNumberProvider()).run("How does Henkel define organic sales growth?", question_id="gate_a_doc_amount")
    assert result.verification.verdict.value != "PASS" and not result.claims


def test_matching_number_cannot_relabel_reported_currency_as_percent():
    class UnitRelabelProvider(DeterministicFakeProvider):
        def _draft(self, bundle, *, revision):
            draft = super()._draft(bundle, revision=revision)
            claim = draft.claims[0].model_copy(update={"unit": "percent", "text": "Sales were 10348 percent."})
            return draft.model_copy(update={"claims": (claim,), "answer": claim.text})
    result = graph_factory(UnitRelabelProvider()).run("What were Henkel H1 2026 sales?", question_id="gate_a_unit_relabel")
    assert result.verification.verdict.value != "PASS" and not result.claims


@pytest.mark.parametrize("text", ["Henkel H1 2026 sales were EUR 10,348 million.", "The reported value was 10348 EUR_million for Sales."])
def test_correct_prose_still_passes_and_release_is_bound(text):
    result = graph_factory(ContradictoryProvider(text)).run("What were Henkel H1 2026 sales?", question_id="gate_a_correct")
    assert result.verification.verdict.value == "PASS"
    assert result.answer == " ".join(claim.text for claim in result.claims)
    assert "10348 EUR_million" in result.answer


@pytest.mark.parametrize("text", [
    "Henkel H1 2026 sales were EUR 999 million.",
    "Henkel H1 2026 sales were EUR -10348 million.",
    "Henkel H1 2026 sales were USD 10348 million.",
    "Henkel H1 2026 sales were EUR 10,348 billion.",
    "Sales were 10348 EUR_million, with a further EUR 999 million.",
    "Sales were nine hundred ninety-nine million euros.",
    "Sales were EUR 999 million.",
    "Sales were EUR (10348) million.",
    "Sales were 1.0348e4 EUR_million.",
])
def test_contradictory_claim_prose_cannot_pass_or_be_released(text):
    provider = ContradictoryProvider(text)
    graph = graph_factory(provider)
    result = graph.run("What were Henkel H1 2026 sales?", question_id="gate_a_prose")
    assert result.verification.verdict.value != "PASS"
    assert result.status.value == "REFUSED"
    assert not result.claims
    assert text not in result.answer


def test_summary_only_contradiction_is_not_passed_or_released():
    text = "Henkel H1 2026 sales were EUR 999 million."
    with client(provider=ContradictoryProvider(text, summary_only=True)) as api:
        response = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"})
    body = response.json()
    assert response.status_code == 200
    assert body["verification"]["verdict"] != "PASS"
    assert "999" not in body["answer"]
    assert body["claims"][0]["value"] == "10348"


def test_rotation_does_not_reset_anonymous_client_quota():
    with client(rate_limit=1) as api:
        first = api.post("/api/v1/query", json={"question": "What was BMW revenue?", "session_id": "session_first"})
        header = api.post("/api/v1/query", headers={"X-Session-ID": "session_second", "X-Forwarded-For": "192.0.2.2"}, json={"question": "What was BMW revenue?"})
        body = api.post("/api/v1/query", json={"question": "What was BMW revenue?", "session_id": "session_third"})
    assert first.status_code == 200
    assert header.status_code == body.status_code == 429


def test_limiter_peer_isolation_expiry_and_address_privacy(monkeypatch):
    from src.api.rate_limit import SlidingWindowLimiter
    clock = [100.0]
    monkeypatch.setattr("src.api.rate_limit.time.monotonic", lambda: clock[0])
    limiter = SlidingWindowLimiter(1)
    assert limiter.allow("192.0.2.1")
    assert not limiter.allow("192.0.2.1")
    assert limiter.allow("192.0.2.2")
    assert all("192.0.2" not in key for key in limiter._events)
    clock[0] = 161.0
    assert limiter.allow("192.0.2.1")
    assert len(limiter._events) == 1


def test_limiter_parallel_requests_cannot_exceed_quota():
    from concurrent.futures import ThreadPoolExecutor
    from src.api.rate_limit import SlidingWindowLimiter
    limiter = SlidingWindowLimiter(3)
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(limiter.allow, ["same-peer"] * 30)) == 3


def test_public_demo_without_private_assets(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from src.api.app import create_app
    from src.api.settings import AppSettings
    settings = AppSettings(app_mode="demo", public_demo=True, checkpoint_uri=str(tmp_path / "checkpoint.sqlite"), session_db_path=str(tmp_path / "sessions.sqlite"))
    # Fail if private corpus or model cache is accessed by the demo workflow.
    from pathlib import Path
    original = Path.read_text
    def guarded_read(path, *args, **kwargs):
        assert "data/retrieval/local" not in str(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    with TestClient(create_app(settings=settings)) as api:
        metadata = api.get("/api/v1/metadata").json()
        numeric = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"}).json()
        documentary = api.post("/api/v1/query", json={"question": "How does Henkel define organic sales growth?"}).json()
        assert api.get("/ready").status_code == 200
    assert "public numerical-only" in metadata["retrieval_model"]
    assert numeric["status"] == "COMPLETED" and numeric["provider"] == "deterministic_fake"
    assert numeric["claims"][0]["value"] == "10348"
    assert documentary["status"] == "REFUSED" and not documentary["claims"]


def test_public_demo_cannot_silently_enable_in_production():
    from src.api.settings import AppSettings
    with pytest.raises(ValueError):
        AppSettings(public_demo=True)
