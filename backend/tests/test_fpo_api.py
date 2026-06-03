from fastapi.testclient import TestClient
import analysis.fpo_bulk as fpo
from main import app

client = TestClient(app)


def _stub_markets(monkeypatch, markets, source="mandi", crop="wheat"):
    def stub(crop_arg, lat=None, lon=None, state=None, rate_per_km=0.0, top_k=10):
        return {"source": source, "markets": markets, "crop": crop}
    monkeypatch.setattr(fpo, "get_market_prices", stub)


def test_bulk_plan_returns_expected_keys(monkeypatch):
    markets = [
        {"market": "Near", "district": "D1", "state": "S", "modal_price": 1000, "distance_km": 10},
        {"market": "Far", "district": "D2", "state": "S", "modal_price": 1200, "distance_km": 100},
    ]
    _stub_markets(monkeypatch, markets)
    body = {
        "crop": "wheat",
        "farmers": [
            {"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50},
            {"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50},
        ],
        "transport": {"truck_capacity_q": 100, "fixed_hire_per_truck": 2000,
                      "per_km_per_truck": 30, "per_q_local_rate": 3.0},
    }
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 200
    data = r.json()
    for key in ("baseline", "aggregated_rev", "extra_income", "price_basis", "chosen_mandi"):
        assert key in data
    assert data["extra_income"] == 18000.0


def test_missing_coords_is_422():
    body = {"crop": "wheat", "farmers": [{"state": "S", "quantity_q": 50}]}
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 422


def test_non_positive_quantity_is_422():
    body = {"crop": "wheat", "farmers": [{"lat": 30.0, "lon": 75.0, "quantity_q": 0}]}
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 422


def test_empty_farmer_list_is_422():
    body = {"crop": "wheat", "farmers": []}
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 422


def test_state_fallback_crop_returns_200_with_flag(monkeypatch):
    _stub_markets(monkeypatch, markets=[], source="state_fallback", crop="bajra")
    body = {"crop": "bajra", "farmers": [{"lat": 30.0, "lon": 75.0, "state": "Punjab", "quantity_q": 50}]}
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 200
    assert r.json()["price_basis"] == "state_fallback"
