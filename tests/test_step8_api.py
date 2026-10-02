from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.service import GraphService
from src.api.sessions import SessionStore
from src.api.settings import AppSettings
from src.llm.fake_provider import DeterministicFakeProvider
from src.orchestration.graph import EnterpriseAnalyticsGraph
from src.persistence.checkpoint_store import CheckpointStore
from src.retrieval.models import EvidenceUnit
from src.retrieval.retrieve import GovernedRetriever


ROOT = Path(__file__).resolve().parents[1]


def graph_factory(provider=None):
    units = [
        EvidenceUnit.model_validate_json(line)
        for line in (ROOT / "data/retrieval/local/evidence_units.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    return EnterpriseAnalyticsGraph(
        ROOT,
        provider=provider or DeterministicFakeProvider(),
        retriever=GovernedRetriever(units, root=ROOT),
        retrieval_method="dense",
        checkpoint_store=CheckpointStore(mode="memory"),
    )


def client(*, provider=None, rate_limit=50, max_question_length=1000, app_mode="test"):
    settings = AppSettings(
        app_mode=app_mode, rate_limit_per_minute=rate_limit,
        max_question_length=max_question_length, request_timeout_seconds=30,
        checkpoint_backend="memory", checkpoint_uri="", session_db_path="",
    )
    service = GraphService(
        settings,
        graph_factory=lambda: graph_factory(provider),
        session_store=SessionStore(None),
    )
    return TestClient(create_app(settings=settings, graph_service=service))


def test_health_readiness_and_metadata_are_safe():
    with client() as api:
        health = api.get("/health")
        ready = api.get("/ready")
        metadata = api.get("/api/v1/metadata")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert ready.status_code == 200
    assert all(item["ready"] for item in ready.json()["checks"])
    assert metadata.json()["retrieval_method"] == "metadata-first dense semantic retrieval"
    assert metadata.json()["retrieval_version"] == "governed-semantic-dense-1.0.0"
    serialized = metadata.text.lower()
    assert "api_key" not in serialized and "raw_sources" not in serialized


def test_demo_mode_hides_diagnostics_and_private_paths():
    with client(app_mode="demo") as api:
        metrics = api.get("/api/v1/metrics")
        docs = api.get("/docs")
        raw = api.get("/data/raw_sources/report.pdf")
        health = api.get("/health")
    assert metrics.status_code == 404
    assert docs.status_code == 404
    assert raw.status_code == 404
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    assert health.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("question,route,status", [
    ("What were Henkel H1 2026 sales?", "ANALYTICS_ONLY", "COMPLETED"),
    ("How does Henkel define organic sales growth?", "KNOWLEDGE_ONLY", "COMPLETED"),
    ("Why did Henkel organic sales growth change in H1 2026?", "HYBRID", "COMPLETED"),
    ("What contributed to Henkel organic growth in H1 2026?", "DECOMPOSITION_EXPLANATION", "COMPLETED"),
    ("What was revenue in Q2 2026?", "NEEDS_CLARIFICATION", "NEEDS_CLARIFICATION"),
    ("What was BMW revenue in Q2 2026?", "UNSUPPORTED", "REFUSED"),
])
def test_governed_routes(question, route, status):
    with client() as api:
        response = api.post("/api/v1/query", json={"question": question})
    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == route
    assert payload["status"] == status
    assert payload["request_id"].startswith("request_")
    assert payload["session_id"].startswith("session_")
    assert isinstance(payload["execution"]["stages"], list)
    assert "chain-of-thought" not in response.text.lower()


def test_session_contains_only_safe_structured_history():
    with client() as api:
        result = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"}).json()
        history = api.get(f"/api/v1/sessions/{result['session_id']}")
    assert history.status_code == 200
    payload = history.json()
    assert payload["interaction_count"] == 1
    assert set(payload["interactions"][0]) == {"created_at", "request_id", "question", "resolved_question", "status", "route", "answer"}
    assert "evidence_units" not in history.text and "OPENAI_API_KEY" not in history.text


def test_session_questions_use_independent_graph_checkpoints():
    with client() as api:
        first = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"}).json()
        second = api.post("/api/v1/query", json={
            "question": "How does Henkel define organic sales growth?",
            "session_id": first["session_id"],
        }).json()
        history = api.get(f"/api/v1/sessions/{first['session_id']}").json()
    assert first["route"] == "ANALYTICS_ONLY"
    assert second["route"] == "KNOWLEDGE_ONLY"
    assert history["interaction_count"] == 2


def test_malformed_and_oversized_requests_fail_safely():
    with client(max_question_length=40) as api:
        malformed = api.post("/api/v1/query", json={"question": "x", "unexpected": True})
        oversized = api.post("/api/v1/query", json={"question": "a reasonable question " * 5})
    assert malformed.status_code == 422
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "QUESTION_TOO_LONG"


def test_rate_limit_is_bounded():
    with client(rate_limit=1) as api:
        first = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"})
        second = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMITED"


def test_provider_failure_releases_no_unverified_claims_or_secret():
    class BrokenProvider(DeterministicFakeProvider):
        def generate_structured(self, **kwargs):
            raise RuntimeError("provider exploded with credential material that must never leak")

    with client(provider=BrokenProvider()) as api:
        response = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "REFUSED"
    assert payload["claims"] == []
    assert "secret" not in response.text.lower()


def test_evidence_conflict_fails_closed():
    class PersistentWrongNumber(DeterministicFakeProvider):
        def generate_structured(self, **kwargs):
            generated = super().generate_structured(**kwargs)
            broken = self._inject(generated.value, "wrong_number")
            return generated.model_copy(update={"value": broken})

    with client(provider=PersistentWrongNumber()) as api:
        response = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "REFUSED"
    assert payload["claims"] == []
    assert payload["verification"]["verdict"] != "PASS"


def test_metrics_expose_aggregate_operational_data_only():
    with client() as api:
        api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"})
        metrics = api.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["requests"] == 1
    assert "question" not in metrics.text.lower()
    assert "answer" not in metrics.text.lower()
