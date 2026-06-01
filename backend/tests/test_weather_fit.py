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
