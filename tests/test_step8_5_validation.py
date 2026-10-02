from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.service import GraphService
from src.api.sessions import SessionStore
from src.api.settings import AppSettings
from tests.test_step8_api import client, graph_factory


def test_rate_limit_survives_body_session_rotation_and_common_headers_present():
    with client(rate_limit=1) as api:
        first = api.post("/api/v1/query", json={
            "question": "What were Henkel H1 2026 sales?", "session_id": "session_AAAAA",
        })
        second = api.post("/api/v1/query", json={
            "question": "What were Henkel H1 2026 sales?", "session_id": "session_BBBBB",
        })
        limited = api.post("/api/v1/query", json={
            "question": "What were Henkel H1 2026 sales?", "session_id": "session_AAAAA",
        })
    assert (first.status_code, second.status_code, limited.status_code) == (200, 429, 429)
    assert limited.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in limited.headers["content-security-policy"]


def test_safe_followup_scope_resolution_and_cross_company_reset():
    with client(rate_limit=20) as api:
        first = api.post("/api/v1/query", json={
            "question": "What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
        }).json()
        sid = first["session_id"]
        vans = api.post("/api/v1/query", json={"question": "What about Vans?", "session_id": sid}).json()
        financial = api.post("/api/v1/query", json={"question": "And Financial Services?", "session_id": sid}).json()
        henkel = api.post("/api/v1/query", json={"question": "Now switch to Henkel.", "session_id": sid}).json()
        history = api.get(f"/api/v1/sessions/{sid}").json()["interactions"]
    assert first["route"] == vans["route"] == financial["route"] == "DECOMPOSITION_EXPLANATION"
    assert any(claim["business_scope"] == "mercedes_vans" for claim in vans["claims"])
    assert any(claim["business_scope"] == "mercedes_financial_services" for claim in financial["claims"])
    assert henkel["status"] == "NEEDS_CLARIFICATION"
    assert "Mercedes-Benz Vans" in history[1]["resolved_question"]
    assert "Financial Services" in history[2]["resolved_question"]
    assert history[3]["resolved_question"] == "Now switch to Henkel."


def test_cross_session_isolation_and_unique_request_ids():
    with client(rate_limit=20) as api:
        mercedes = api.post("/api/v1/query", json={
            "question": "What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
        }).json()
        henkel = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"}).json()
        ambiguous = api.post("/api/v1/query", json={
            "question": "What about Vans?", "session_id": henkel["session_id"],
        }).json()
    assert mercedes["session_id"] != henkel["session_id"]
    assert mercedes["request_id"] != henkel["request_id"]
    assert ambiguous["status"] == "NEEDS_CLARIFICATION"
    assert all(claim.get("company_id") != "mercedes_benz_group" for claim in ambiguous["claims"])


def test_concurrent_requests_are_isolated_by_serialized_graph_access():
    api = client(rate_limit=20)
    questions = [
        "What were Henkel H1 2026 sales?",
        "How does Henkel define organic sales growth?",
        "What was Mercedes-Benz Group revenue in H1 2026?",
        "Why did Henkel organic sales growth change in H1 2026?",
    ]
    with api:
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda q: api.post("/api/v1/query", json={"question": q}), questions))
    payloads = [response.json() for response in responses]
    assert all(response.status_code == 200 for response in responses)
    assert len({payload["request_id"] for payload in payloads}) == 4
    assert [payload["route"] for payload in payloads] == [
        "ANALYTICS_ONLY", "KNOWLEDGE_ONLY", "ANALYTICS_ONLY", "HYBRID",
    ]
    assert all(
        citation["company_id"] == "henkel"
        for payload in (payloads[1], payloads[3]) for citation in payload["citations"]
    )


def test_sqlite_session_history_survives_store_restart(tmp_path: Path):
    database = tmp_path / "sessions.sqlite"
    first = SessionStore(str(database))
    first.append("session_persist", {"question": "safe question", "status": "COMPLETED"})
    first.close()
    second = SessionStore(str(database))
    records = second.get("session_persist")
    second.close()
    assert len(records) == 1
    assert records[0]["question"] == "safe question"
    serialized = database.read_bytes()
    assert b"OPENAI_API_KEY" not in serialized and b"system prompt" not in serialized


def test_bogus_postgres_is_not_ready_but_health_stays_healthy():
    settings = AppSettings(
        app_mode="development", checkpoint_backend="postgres",
        checkpoint_uri="postgresql://invalid:invalid@127.0.0.1:1/missing",
        session_db_path="", request_timeout_seconds=5,
    )
    service = GraphService(settings, graph_factory=graph_factory, session_store=SessionStore(None))
    with TestClient(create_app(settings=settings, graph_service=service)) as api:
        health = api.get("/health")
        ready = api.get("/ready")
    checkpoint = next(item for item in ready.json()["checks"] if item["name"] == "checkpoint")
    assert health.status_code == 200
    assert ready.status_code == 503
    assert checkpoint == {"name": "checkpoint", "ready": False, "detail": "postgres unavailable"}
    assert "invalid:invalid" not in ready.text


def test_demo_cors_errors_and_private_paths_are_safe():
    with client(app_mode="demo", rate_limit=10) as api:
        preflight = api.options("/api/v1/query", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST",
        })
        invalid = api.post("/api/v1/query", content="{broken", headers={"Content-Type": "application/json"})
        paths = [api.get(path) for path in (
            "/data/retrieval/local/evidence_units.jsonl", "/.env", "/config/metric_catalog.csv",
            "/../data/raw_sources/report.pdf", "/api/v1/metrics", "/docs",
        )]
    assert preflight.status_code == 400
    assert invalid.status_code == 422
    assert all(response.status_code == 404 for response in paths)
    combined = " ".join(response.text for response in [invalid, *paths])
    assert "/Users/" not in combined and "postgresql://" not in combined and "OPENAI_API_KEY" not in combined


def test_unhandled_runtime_error_is_sanitized():
    settings = AppSettings(app_mode="test", checkpoint_backend="memory", checkpoint_uri="", session_db_path="")
    service = GraphService(settings, graph_factory=graph_factory, session_store=SessionStore(None))

    async def broken_query(*args, **kwargs):
        raise RuntimeError("private-path-/Users/example secret detail")

    service.query = broken_query  # type: ignore[method-assign]
    with TestClient(create_app(settings=settings, graph_service=service), raise_server_exceptions=False) as api:
        response = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-path" not in response.text and "/Users/" not in response.text


def test_session_delete_is_idempotent_and_removes_history():
    with client(rate_limit=10) as api:
        result = api.post("/api/v1/query", json={"question": "What were Henkel H1 2026 sales?"}).json()
        first = api.delete(f"/api/v1/sessions/{result['session_id']}")
        second = api.delete(f"/api/v1/sessions/{result['session_id']}")
        missing = api.get(f"/api/v1/sessions/{result['session_id']}")
    assert first.status_code == second.status_code == 204
    assert missing.status_code == 404
