"""Tests for the CropAdvisor fusion layer."""
import pytest

from analysis.fusion import recommend, DEFAULT_WEIGHTS
from analysis.crop_catalog import WHITELIST
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
        # breakdown is per-crop: always has regional+market, suitability only
        # for crops the soil model knows; never more than the modules that ran
        assert {"regional", "market"} <= set(r["breakdown"]) <= set(out["modules_used"])
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


def test_geometric_ranking_demotes_agronomically_absurd_crop():
    """The hardening regression: across the full whitelist, coffee (high market,
    ~0 suitability+regional in Punjab) must NOT top the list under geometric
    fusion, even chasing profit; a real Punjab crop (rice) should rank above it."""
    out = recommend("Punjab", "Ludhiana", features=RICE_SOIL,
                    goal="max_profit", top_k=len(WHITELIST))
    assert out["method"] == "geometric"
    ranking = [r["crop"] for r in out["recommendations"]]
    top3 = ranking[:3]
    assert "coffee" not in top3
    assert ranking.index("rice") < ranking.index("coffee")


def test_additive_method_reproduces_the_flaw():
    """Under the old additive rule, a crop with a lone strong market score floats
    to the very top despite NO local track record (regional fit = 0) — exactly the
    flaw geometric fusion fixes by demoting it."""
    add = recommend("Punjab", "Ludhiana", features=RICE_SOIL,
                    goal="max_profit", top_k=len(WHITELIST), method="additive")
    assert add["method"] == "additive"
    top = add["recommendations"][0]
    # the additive winner is surfaced by market alone — unproven in Punjab
    assert top["breakdown"]["regional"] == 0.0
    # geometric fusion does NOT crown a crop with zero regional history
    geo = recommend("Punjab", "Ludhiana", features=RICE_SOIL,
                    goal="max_profit", top_k=len(WHITELIST))
    assert geo["recommendations"][0]["crop"] != top["crop"]
    assert geo["recommendations"][0]["breakdown"]["regional"] > 0.0


def test_weather_module_integrates_and_degrades_per_crop(monkeypatch):
    import analysis.fusion as fz
    stub = {"rice": {"score": 0.9, "fit": "good", "climate": {}},
            "maize": {"score": 0.5, "fit": "fair", "climate": {}}}
    monkeypatch.setattr(fz, "weather_fit_scores", lambda *a, **k: stub)
    out = fz.recommend("Punjab", "Ludhiana", crops=["rice", "maize", "wheat"], top_k=3)
    assert "weather" in out["modules_used"]
    assert abs(sum(out["weights_used"].values()) - 1.0) < 1e-6
    crops = {r["crop"] for r in out["recommendations"]}
    assert "wheat" in crops  # no weather score -> still recommended (per-crop degrade)
    for r in out["recommendations"]:
        if r["crop"] in stub:
            assert "weather" in r["breakdown"]
