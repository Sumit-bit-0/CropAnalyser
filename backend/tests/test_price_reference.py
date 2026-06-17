import pytest
from analysis.price_reference import assured_price, PREMIUM_PCT_DEFAULT


def test_known_crop_applies_default_premium():
    out = assured_price("wheat", year=2024)
    assert out["available"] is True
    assert out["basis"] == "MSP"
    assert out["premium_pct"] == PREMIUM_PCT_DEFAULT
    assert out["processor_price"] == pytest.approx(out["msp"] * (1 + PREMIUM_PCT_DEFAULT / 100))


def test_unknown_crop_is_unavailable():
    out = assured_price("dragonfruit")
    assert out["available"] is False
    assert out["processor_price"] is None


def test_sugarcane_uses_frp_basis():
    assert assured_price("sugarcane", year=2024)["basis"] == "FRP"


def test_year_none_picks_latest_on_record(monkeypatch):
    import analysis.price_reference as pr
    monkeypatch.setattr(pr, "_TABLE", None)  # force reload
    monkeypatch.setattr(pr, "_rows", lambda: [
        {"crop": "wheat", "year": 2023, "msp_per_quintal": 2275, "basis": "MSP", "premium_pct": ""},
        {"crop": "wheat", "year": 2024, "msp_per_quintal": 2425, "basis": "MSP", "premium_pct": ""},
    ])
    assert assured_price("wheat")["msp"] == 2425


def test_per_crop_premium_override(monkeypatch):
    import analysis.price_reference as pr
    monkeypatch.setattr(pr, "_TABLE", None)
    monkeypatch.setattr(pr, "_rows", lambda: [
        {"crop": "wheat", "year": 2024, "msp_per_quintal": 2000, "basis": "MSP", "premium_pct": "10"},
    ])
    out = assured_price("wheat")
    assert out["premium_pct"] == 10.0
    assert out["processor_price"] == pytest.approx(2200.0)
