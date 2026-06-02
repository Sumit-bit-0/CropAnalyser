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

def test_forecast_available():
    r = client.get("/api/forecast/available")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict) and body
    assert "Punjab" in body and "Wheat" in body["Punjab"]
    # every advertised combo must actually forecast (no dead options)
    state = "Punjab"
    commodity = body[state][0]
    assert client.get(f"/api/forecast?state={state}&commodity={commodity}").status_code == 200


def test_recommend_crop():
    body = {"N": 90, "P": 42, "K": 43, "temperature": 20.8,
            "humidity": 82.0, "ph": 6.5, "rainfall": 202.9}
    r = client.post("/api/recommend/crop", json=body)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "recommendations" in data and "top" in data
        assert "crop" in data["top"]


def test_profit_plan():
    body = {"area_acres": 2, "yield_q_per_acre": 20, "input_cost": 10000,
            "labour_cost": 5000, "transport_cost": 3000, "market_price": 1500}
    r = client.post("/api/profit/plan", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["profit"] == 42000.0
    assert "recommendation" in data


def test_price_reference_endpoint():
    r = client.get("/api/profit/price-reference",
                   params={"state": "Maharashtra", "commodity": "Onion"})
    assert r.status_code == 200
    assert "risk_level" in r.json()


def test_mandi_commodities():
    r = client.get("/api/mandi/commodities")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_mandi_compare():
    r = client.get("/api/mandi/compare",
                   params={"commodity": "Wheat", "lat": 19.07, "lon": 72.88, "top": 5})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "source" in data and "markets" in data
    if data["markets"]:
        assert {"market", "modal_price", "net_price"} <= set(data["markets"][0].keys())
