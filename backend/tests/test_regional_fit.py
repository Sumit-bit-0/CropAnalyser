"""Tests for the Regional Fit scorer (uses the loaded district_crop_history)."""
import pytest

from analysis.regional_fit import regional_fit_scores
from analysis.crop_catalog import WHITELIST
from database import table_exists

pytestmark = pytest.mark.skipif(
    not table_exists("district_crop_history"),
    reason="district_crop_history not loaded",
)


def test_returns_all_requested_crops_in_range():
    scores = regional_fit_scores("Punjab", "Ludhiana")
    assert set(scores) == set(WHITELIST)
    for c, v in scores.items():
        assert 0.0 <= v["score"] <= 1.0
        assert {"score", "level", "years_grown", "total_production", "avg_yield"} <= set(v)


def test_ludhiana_rice_is_top_and_normalized():
    scores = regional_fit_scores("Punjab", "Ludhiana")
    # rice dominates Ludhiana's history -> should be the normalized top (1.0)
    assert scores["rice"]["score"] == 1.0
    assert scores["rice"]["level"] == "district"
    assert scores["rice"]["years_grown"] > 0
    # the region's max is normalized to 1.0
    assert max(v["score"] for v in scores.values()) == 1.0


def test_absent_crop_scores_zero():
    scores = regional_fit_scores("Punjab", "Ludhiana")
    # coconut has no history in Ludhiana
    assert scores["coconut"]["score"] == 0.0
    assert scores["coconut"]["level"] == "none"


def test_state_fallback_when_district_unknown():
    scores = regional_fit_scores("Kerala", "ZzzNoSuchDistrict")
    # should fall back to Kerala state-level history
    levels = {v["level"] for v in scores.values() if v["score"] > 0}
    assert levels == {"state"}
    assert any(v["score"] > 0 for v in scores.values())


def test_crops_subset_filter():
    scores = regional_fit_scores("Punjab", "Ludhiana", crops=["rice", "maize"])
    assert set(scores) == {"rice", "maize"}
