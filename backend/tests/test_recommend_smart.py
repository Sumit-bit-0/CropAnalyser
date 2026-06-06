"""API tests for the CropAdvisor fusion endpoint POST /api/recommend/smart."""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SOIL = {"N": 90, "P": 42, "K": 43, "temperature": 26,
        "humidity": 80, "ph": 6.5, "rainfall": 180}


def test_smart_mode_with_soil():
    r = client.post("/api/recommend/smart", json={
        "state": "Punjab", "district": "Ludhiana", "goal": "max_profit",
        "top_k": 3, "soil": SOIL,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["modules_used"] == ["market", "regional", "suitability"]
    assert body["method"] == "geometric"
    assert len(body["recommendations"]) == 3
    rec = body["recommendations"][0]
    assert {"crop", "score", "breakdown", "why", "cautions"} <= set(rec)
    # hardening holds through the API: coffee not the top pick in Punjab
    assert rec["crop"] != "coffee"


def test_soil_auto_derived_without_explicit_block(seeded):
    # No `soil` block posted: the API auto-derives soil from the district table,
    # so suitability is included (Ludhiana has seed soil data). There is no
    # longer a "simple mode" default — soil is always derived when data exists.
    # `seeded` fixture (conftest.py) ensures Punjab/Ludhiana row is in the DB.
    r = client.post("/api/recommend/smart", json={
        "state": "Punjab", "district": "Ludhiana", "top_k": 3,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["modules_used"] == ["market", "regional", "suitability"]
    assert body["soil_source"] == "district"
    assert len(body["recommendations"]) == 3


def test_validation_requires_state():
    r = client.post("/api/recommend/smart", json={"district": "Ludhiana"})
    assert r.status_code == 422
