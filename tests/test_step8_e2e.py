import pytest

from tests.test_step8_api import client


@pytest.mark.parametrize("question,expected", [
    ("What were Henkel H1 2026 sales?", {"status": "COMPLETED", "route": "ANALYTICS_ONLY", "analytics": True}),
    ("How does Henkel define organic sales growth?", {"status": "COMPLETED", "route": "KNOWLEDGE_ONLY", "retrieval": True}),
    ("Why did Henkel organic sales growth change in H1 2026?", {"status": "COMPLETED", "route": "HYBRID", "analytics": True, "retrieval": True}),
    ("What was BMW revenue in Q2 2026?", {"status": "REFUSED", "route": "UNSUPPORTED"}),
])
def test_frontend_facing_query_contract(question, expected):
    with client() as api:
        response = api.post("/api/v1/query", json={"question": question})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == expected["status"]
    assert payload["route"] == expected["route"]
    if "analytics" in expected:
        assert payload["execution"]["analytics_used"] is expected["analytics"]
    if "retrieval" in expected:
        assert payload["execution"]["retrieval_used"] is expected["retrieval"]
    assert isinstance(payload["claims"], list)
    assert isinstance(payload["citations"], list)
    assert isinstance(payload["limitations"], list)
