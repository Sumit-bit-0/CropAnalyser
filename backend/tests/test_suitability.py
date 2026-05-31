"""Tests for the agronomic Suitability scorer (reuses the trained crop model)."""
import pytest

from analysis.suitability import suitability_scores
from analysis.crop_catalog import WHITELIST

# textbook rice row from Crop_recommendation.csv
RICE_SAMPLE = {"N": 90, "P": 42, "K": 43, "temperature": 20.8,
               "humidity": 82.0, "ph": 6.5, "rainfall": 202.9}


def test_returns_whitelist_with_normalized_scores():
    s = suitability_scores(RICE_SAMPLE)
    assert set(s) == set(WHITELIST)
    for v in s.values():
        assert 0.0 <= v["score"] <= 1.0
        assert {"score", "prob_pct"} <= set(v)
    assert max(v["score"] for v in s.values()) == 1.0  # top candidate normalized


def test_rice_sample_ranks_rice_top():
    s = suitability_scores(RICE_SAMPLE)
    top_crop = max(s, key=lambda c: s[c]["score"])
    assert top_crop == "rice"
    assert s["rice"]["score"] == 1.0


def test_crops_subset_filter():
    s = suitability_scores(RICE_SAMPLE, crops=["rice", "maize"])
    assert set(s) == {"rice", "maize"}


def test_missing_feature_raises():
    with pytest.raises(ValueError):
        suitability_scores({"N": 1, "P": 2})  # missing the rest
