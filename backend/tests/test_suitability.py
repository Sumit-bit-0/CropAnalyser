"""Tests for the agronomic Suitability scorer (reuses the trained crop model)."""
import pytest

from analysis.suitability import suitability_scores
from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST

# textbook rice row from Crop_recommendation.csv
RICE_SAMPLE = {"N": 90, "P": 42, "K": 43, "temperature": 20.8,
               "humidity": 82.0, "ph": 6.5, "rainfall": 202.9}


def test_returns_only_soil_model_crops_normalized():
    s = suitability_scores(RICE_SAMPLE)
    # only crops with a soil-model label are scored; staples are omitted, not 0
    scorable = {c for c in WHITELIST if CANONICAL_CROPS[c]["suitability"] is not None}
    assert set(s) == scorable
    assert "wheat" not in s and "sugarcane" not in s
    for v in s.values():
        assert 0.0 <= v["score"] <= 1.0
        assert {"score", "prob_pct"} <= set(v)
    assert max(v["score"] for v in s.values()) == 1.0  # top candidate normalized


def test_rice_sample_ranks_rice_top():
    s = suitability_scores(RICE_SAMPLE)
    top_crop = max(s, key=lambda c: s[c]["score"])
    assert top_crop == "rice"
    assert s["rice"]["score"] == 1.0


def test_crops_subset_filter_drops_unscorable():
    # wheat has no soil label, so it is silently dropped from the subset
    s = suitability_scores(RICE_SAMPLE, crops=["rice", "maize", "wheat"])
    assert set(s) == {"rice", "maize"}


def test_missing_feature_raises():
    with pytest.raises(ValueError):
        suitability_scores({"N": 1, "P": 2})  # missing the rest
