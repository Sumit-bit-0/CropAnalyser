"""Tests for the Market Profitability scorer (reads the prices table)."""
from analysis.market_profitability import market_profitability_scores
from analysis.crop_catalog import WHITELIST


def test_returns_whitelist_normalized():
    s = market_profitability_scores()
    assert set(s) == set(WHITELIST)
    for v in s.values():
        assert 0.0 <= v["score"] <= 1.0
        assert {"score", "recent_price", "avg_price", "volatility_cv", "risk_level"} <= set(v)
    assert max(v["score"] for v in s.values()) == 1.0


def test_common_crops_have_price_and_risk():
    s = market_profitability_scores()
    assert s["rice"]["recent_price"] and s["rice"]["recent_price"] > 0
    assert s["rice"]["risk_level"] in {"low", "medium", "high"}


def test_crops_subset_filter():
    s = market_profitability_scores(crops=["rice", "maize", "cotton"])
    assert set(s) == {"rice", "maize", "cotton"}
    assert max(v["score"] for v in s.values()) == 1.0


def test_state_filter_runs():
    s = market_profitability_scores(state="Punjab", crops=["rice", "maize"])
    assert set(s) == {"rice", "maize"}
    for v in s.values():
        assert 0.0 <= v["score"] <= 1.0
