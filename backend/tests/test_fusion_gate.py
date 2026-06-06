# backend/tests/test_fusion_gate.py
import analysis.fusion as fusion


def test_gate_penalizes_far_sugarcane(monkeypatch):
    # Two crops tie on the modules; sugarcane should fall when no mill is near.
    monkeypatch.setattr(fusion, "regional_fit_scores",
        lambda *a, **k: {"sugarcane": {"score": 1.0, "level": "state", "years_grown": 10},
                          "wheat": {"score": 1.0, "level": "state", "years_grown": 10}})
    monkeypatch.setattr(fusion, "market_profitability_scores",
        lambda crops: {c: {"score": 1.0, "recent_price": 200, "risk_level": "low"} for c in crops})
    monkeypatch.setattr(fusion, "weather_fit_scores", lambda *a, **k: {})
    # Gate only sugarcane (not wheat) so the penalty is asymmetric.
    monkeypatch.setattr(fusion, "gated_crops", lambda: {"sugarcane": "sugar_mill"})
    monkeypatch.setattr(fusion, "nearest_facility", lambda ft, lat, lon: {"name": "x", "km": 300})

    out = fusion.recommend("Bihar", crops=["sugarcane", "wheat"], top_k=2,
                           coords=(25.0, 85.0))
    ranks = [r["crop"] for r in out["recommendations"]]
    assert ranks[0] == "wheat"
    sug = next(r for r in out["recommendations"] if r["crop"] == "sugarcane")
    assert any("mill" in c for c in sug["cautions"])


def test_gate_noop_without_coords(monkeypatch):
    monkeypatch.setattr(fusion, "regional_fit_scores",
        lambda *a, **k: {"sugarcane": {"score": 1.0, "level": "state", "years_grown": 10}})
    monkeypatch.setattr(fusion, "market_profitability_scores",
        lambda crops: {c: {"score": 1.0, "recent_price": 200, "risk_level": "low"} for c in crops})
    monkeypatch.setattr(fusion, "weather_fit_scores", lambda *a, **k: {})
    out = fusion.recommend("Bihar", crops=["sugarcane"], top_k=1, coords=None)
    assert out["recommendations"][0]["crop"] == "sugarcane"  # unchanged, no gate
