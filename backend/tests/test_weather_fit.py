# backend/tests/test_weather_fit.py
import pytest
from analysis.weather_fit import crop_envelopes, _csv_path


def _csv_exists():
    try:
        _csv_path()
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _csv_exists(), reason="Crop_recommendation.csv not found")
def test_envelopes_cover_soil_crops_with_sane_values():
    env = crop_envelopes()
    assert "rice" in env and "maize" in env
    # rice is warm + very wet in the Kaggle set
    rice_temp_mean, rice_temp_std = env["rice"]["temperature"]
    assert 18 <= rice_temp_mean <= 30
    assert rice_temp_std > 0
    rice_rain_mean, _ = env["rice"]["rainfall"]
    assert rice_rain_mean > 150  # rice rainfall ~200mm in this dataset
    # expansion crops (no soil label) get no envelope
    assert "wheat" not in env and "sugarcane" not in env


# ---------- weather_fit_scores tests ----------
import analysis.weather_fit as wf


@pytest.mark.skipif(not _csv_exists(), reason="Crop_recommendation.csv not found")
def test_scores_high_near_envelope_low_far(monkeypatch):
    env = wf.crop_envelopes()
    rice = {d: env["rice"][d][0] for d in ("temperature", "humidity", "rainfall")}
    monkeypatch.setattr(wf, "get_centroid", lambda s, d: (25.7, 85.3))
    # location climate == rice's envelope center -> rice should score the max (1.0)
    monkeypatch.setattr(wf, "seasonal_climate", lambda lat, lon, season: rice)
    out = wf.weather_fit_scores("Bihar", "Begusarai", "Kharif", crops=["rice", "apple"])
    assert out["rice"]["score"] == pytest.approx(1.0)
    assert out["rice"]["fit"] == "good"
    assert out["rice"]["score"] >= out["apple"]["score"]


def test_no_coords_returns_empty(monkeypatch):
    monkeypatch.setattr(wf, "get_centroid", lambda s, d: None)
    assert wf.weather_fit_scores("Nowhere", "Nowhere", "Kharif") == {}


def test_weather_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(wf, "get_centroid", lambda s, d: (25.7, 85.3))
    def boom(*a, **k):
        from analysis.weather_client import WeatherUnavailable
        raise WeatherUnavailable("down")
    monkeypatch.setattr(wf, "seasonal_climate", boom)
    assert wf.weather_fit_scores("Bihar", "Begusarai", "Kharif") == {}


def test_expansion_crop_omitted(monkeypatch):
    monkeypatch.setattr(wf, "get_centroid", lambda s, d: (25.7, 85.3))
    monkeypatch.setattr(wf, "seasonal_climate",
                        lambda lat, lon, season: {"temperature": 25, "humidity": 70, "rainfall": 150})
    out = wf.weather_fit_scores("Bihar", "Begusarai", "Kharif", crops=["rice", "wheat"])
    assert "wheat" not in out  # no envelope -> omitted
    assert "rice" in out
