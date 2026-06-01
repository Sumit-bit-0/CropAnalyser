import pytest
from analysis.price_outlook import price_outlook
from database import table_exists

pytestmark = pytest.mark.skipif(not table_exists("prices"), reason="prices not loaded")


def test_returns_price_and_source():
    r = price_outlook("Punjab", "wheat")
    assert r["source"] in {"forecast", "historical", "none"}
    if r["source"] != "none":
        assert r["price"] is not None and r["price"] > 0
        assert r["trend"] in {"rising", "flat", "falling"}


def test_falls_back_to_historical_when_no_model(monkeypatch):
    # force the forecast path to raise -> exercise historical fallback
    import analysis.price_outlook as po
    monkeypatch.setattr(po, "_forecast", lambda s, c: (_ for _ in ()).throw(FileNotFoundError()))
    r = price_outlook("Punjab", "wheat")
    assert r["source"] in {"historical", "none"}
