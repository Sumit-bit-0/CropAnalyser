# backend/tests/test_soil_profile.py
import analysis.soil_profile as sp
from analysis import weather_client


def test_features_with_climate(monkeypatch):
    monkeypatch.setattr(sp, "district_soil",
                        lambda s, d=None: {"N": 270, "P": 22, "K": 210, "ph": 7.4,
                                           "soil_source": "district"})
    monkeypatch.setattr(sp, "seasonal_climate",
                        lambda lat, lon, season: {"temperature": 27.5, "humidity": 65, "rainfall": 1200})
    out = sp.soil_profile("Bihar", "Gopalganj", coords=(26.47, 84.43), season="Kharif")
    assert out["soil_source"] == "district"
    assert out["climate_source"] == "weather_api"
    assert out["features"] == {"N": 270, "P": 22, "K": 210, "ph": 7.4,
                               "temperature": 27.5, "humidity": 65.0, "rainfall": 1200.0}


def test_climate_fallback_when_api_down(monkeypatch):
    monkeypatch.setattr(sp, "district_soil",
                        lambda s, d=None: {"N": 200, "P": 18, "K": 180, "ph": 7.0,
                                           "soil_source": "state"})

    def _boom(lat, lon, season):
        raise weather_client.WeatherUnavailable("down")
    monkeypatch.setattr(sp, "seasonal_climate", _boom)
    out = sp.soil_profile("Bihar", "X", coords=(25.0, 85.0))
    assert out["climate_source"] == "none"
    assert set(out["features"]) == {"N", "P", "K", "ph", "temperature", "humidity", "rainfall"}


def test_none_when_no_soil(monkeypatch):
    monkeypatch.setattr(sp, "district_soil", lambda s, d=None: None)
    assert sp.soil_profile("Nowhere", None) is None
