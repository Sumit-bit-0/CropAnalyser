import api.mandi as m
from analysis.crop_catalog import CropIdentity


def test_commodities_returns_union_objects(monkeypatch):
    monkeypatch.setattr(m, "list_all_crops", lambda: [
        CropIdentity("maize", "maize", "Maize", "Maize", True, True),
        CropIdentity("bottlegourd", "Bottle Gourd", None, "Bottle Gourd", False, True),
    ])
    out = m.mandi_commodities()
    assert out[0]["display_name"] == "maize" and out[0]["has_mandi"] is True
    assert out[1]["has_mandi"] is False


def test_compare_delegates_to_price_source(monkeypatch):
    captured = {}
    def fake(crop, lat=None, lon=None, state=None, rate_per_km=0.0, top_k=10):
        captured.update(crop=crop, state=state, lat=lat)
        return {"source": "state_fallback", "markets": [], "state_avg": 1850.0}
    monkeypatch.setattr(m, "get_market_prices", fake)
    out = m.mandi_compare(commodity="Maize", lat=30.9, lon=75.8, state="Punjab",
                          rate_per_km=2.0, top=10)
    assert out["source"] == "state_fallback" and out["state_avg"] == 1850.0
    assert captured["crop"] == "Maize" and captured["state"] == "Punjab"
