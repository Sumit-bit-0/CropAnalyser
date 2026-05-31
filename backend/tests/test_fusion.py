"""Tests for the CropAdvisor fusion layer."""
import pytest

from analysis.fusion import recommend, DEFAULT_WEIGHTS
from database import table_exists

RICE_SOIL = {"N": 90, "P": 42, "K": 43, "temperature": 26,
             "humidity": 80, "ph": 6.5, "rainfall": 180}


def test_smart_mode_uses_all_three_modules():
    out = recommend("Punjab", "Ludhiana", features=RICE_SOIL, top_k=3)
    assert out["modules_used"] == ["market", "regional", "suitability"]
    assert abs(sum(out["weights_used"].values()) - 1.0) < 1e-6
    recs = out["recommendations"]
    assert len(recs) == 3
    # sorted by score desc, scores in range, breakdown matches modules
    scores = [r["score"] for r in recs]
    assert scores == sorted(scores, reverse=True)
    for r in recs:
        assert 0.0 <= r["score"] <= 1.0
        assert set(r["breakdown"]) == set(out["modules_used"])
        assert "why" in r and "cautions" in r


def test_simple_mode_drops_suitability_and_renormalizes():
    out = recommend("Punjab", "Ludhiana", top_k=3)  # no soil features
    assert out["modules_used"] == ["market", "regional"]
    assert "suitability" not in out["weights_used"]
    assert abs(sum(out["weights_used"].values()) - 1.0) < 1e-6


def test_goal_max_profit_shifts_weight_to_market():
    base = recommend("Punjab", "Ludhiana", features=RICE_SOIL)["weights_used"]
    profit = recommend("Punjab", "Ludhiana", features=RICE_SOIL, goal="max_profit")["weights_used"]
    assert profit["market"] > base["market"]


def test_top_k_and_crops_filter():
    out = recommend("Punjab", "Ludhiana", features=RICE_SOIL, crops=["rice", "maize", "cotton"], top_k=2)
    assert len(out["recommendations"]) == 2
    crops_seen = {r["crop"] for r in out["recommendations"]}
    assert crops_seen <= {"rice", "maize", "cotton"}


def test_explanations_present_for_strong_crop():
    # rice in Ludhiana should surface a regional "proven" why-line
    out = recommend("Punjab", "Ludhiana", features=RICE_SOIL, crops=["rice"], top_k=1)
    rec = out["recommendations"][0]
    assert rec["crop"] == "rice"
    assert any("proven" in w for w in rec["why"])
