import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_states_markup():
    r = client.get("/api/states/markup")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        assert "state" in data[0]
        assert "avg_markup_pct" in data[0]

def test_crops_markup():
    r = client.get("/api/crops/Tomato/markup")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_trends_filters():
    r = client.get("/api/trends/filters")
    assert r.status_code == 200
    body = r.json()
    assert "states" in body
    assert "commodities" in body

def test_revenue_loss():
    r = client.get("/api/revenue-loss")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_forecast_no_model_returns_404():
    # Pondicherry/Wheat is a real state+commodity but has no trained model
    # (skipped during training due to insufficient records).
    r = client.get("/api/forecast?state=Pondicherry&commodity=Wheat")
    assert r.status_code == 404
