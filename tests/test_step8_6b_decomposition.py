from tests.test_step8_api import client


QUESTION = "What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?"


def test_mercedes_cars_decomposition_api_contract_and_serialization():
    with client(rate_limit=20) as api:
        response = api.post("/api/v1/query", json={"question": QUESTION})

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "DECOMPOSITION_EXPLANATION"
    assert payload["status"] == "COMPLETED"
    assert payload["verification"]["verdict"] == "PASS"
    assert payload["execution"]["analytics_used"] is True
    assert payload["execution"]["retrieval_used"] is True
    values_by_fact = {
        fact_id: claim["value"]
        for claim in payload["claims"]
        for fact_id in claim["fact_ids"]
    }
    assert values_by_fact[110] == "909"
    assert values_by_fact[141] == "-602"
    combined = next(claim for claim in payload["claims"] if 141 in claim["fact_ids"])
    assert "Volume / structure / net pricing" in combined["text"]
    assert "price alone" not in response.text.lower()
    assert payload["refusal_reason"] is None


def test_mercedes_vans_followup_keeps_company_metric_and_period():
    with client(rate_limit=20) as api:
        cars = api.post("/api/v1/query", json={"question": QUESTION}).json()
        vans_response = api.post(
            "/api/v1/query",
            json={"question": "What about Vans?", "session_id": cars["session_id"]},
        )
        history = api.get(f"/api/v1/sessions/{cars['session_id']}").json()

    assert vans_response.status_code == 200
    vans = vans_response.json()
    assert vans["route"] == "DECOMPOSITION_EXPLANATION"
    assert vans["status"] == "COMPLETED"
    assert vans["verification"]["verdict"] == "PASS"
    assert vans["clarification_question"] is None
    assert all(claim["company_id"] == "mercedes_benz_group" for claim in vans["claims"])
    assert any(claim["business_scope"] == "mercedes_vans" for claim in vans["claims"])
    assert all("Q2_2026" in claim["periods"] for claim in vans["claims"] if claim["periods"])
    assert any(claim["metric_id"] == "mercedes_adjusted_ebit" for claim in vans["claims"])
    assert history["interaction_count"] == 2
    assert "Mercedes-Benz Vans" in history["interactions"][1]["resolved_question"]
