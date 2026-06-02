import pandas as pd
import analysis.price_source as ps
from analysis.crop_catalog import CropIdentity


def _ident(mandi, prices):
    return CropIdentity("x", "X", mandi, prices,
                        has_mandi=mandi is not None, has_forecast=prices is not None)


def test_returns_mandi_when_market_rows_exist(monkeypatch):
    monkeypatch.setattr(ps, "resolve_crop", lambda c: _ident("Maize", "Maize"))
    monkeypatch.setattr(ps, "compare_markets",
                        lambda *a, **k: [{"market": "Khanna", "net_price": 2100}])
    out = ps.get_market_prices("maize", lat=30.9, lon=75.8, state="Punjab")
    assert out["source"] == "mandi" and out["markets"][0]["market"] == "Khanna"


def test_falls_back_to_state_average(monkeypatch):
    monkeypatch.setattr(ps, "resolve_crop", lambda c: _ident(None, "Bottle Gourd"))
    monkeypatch.setattr(ps, "_state_avg", lambda prices_name, state: 1850.0)
    out = ps.get_market_prices("bottle gourd", state="Maharashtra")
    assert out["source"] == "state_fallback" and out["state_avg"] == 1850.0
    assert out["markets"] == []


def test_returns_none_when_no_data(monkeypatch):
    monkeypatch.setattr(ps, "resolve_crop", lambda c: _ident(None, None))
    out = ps.get_market_prices("dragonfruit", state="Punjab")
    assert out["source"] == "none"


def test_state_avg_matches_via_normalization(monkeypatch):
    # context state "Orissa" must match prices' "Odisha"
    def fake_query(sql, params=None):
        if "DISTINCT state" in sql:
            return pd.DataFrame({"state": ["Odisha", "Punjab"]})
        return pd.DataFrame({"modal_price": [1000.0, 1200.0], "year": [2025, 2025], "month": [4, 5]})
    monkeypatch.setattr(ps, "query", fake_query)
    assert ps._state_avg("Rice", "Orissa") == 1100.0
