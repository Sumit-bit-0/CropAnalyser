# backend/analysis/soil_profile.py
"""Build the 7-feature soil+climate vector the suitability model needs, from a
location alone: N/P/K/pH from the district soil table, temperature/humidity/
rainfall from the seasonal climate API. Never raises — aware fallbacks instead."""
from analysis.soil_nutrients import district_soil
from analysis.weather_client import seasonal_climate, WeatherUnavailable

# Used only when the weather API can't be reached, so suitability still runs.
_CLIMATE_FALLBACK = {"temperature": 26.0, "humidity": 70.0, "rainfall": 1100.0}


def soil_profile(state, district=None, *, coords=None, season=None):
    """{features:{N,P,K,temperature,humidity,ph,rainfall}, soil_source, climate_source}
    or None when no soil data exists at all."""
    soil = district_soil(state, district)
    if soil is None:
        return None
    features = {"N": soil["N"], "P": soil["P"], "K": soil["K"], "ph": soil["ph"]}
    climate = dict(_CLIMATE_FALLBACK)
    climate_source = "none"
    if coords and coords[0] is not None and coords[1] is not None:
        try:
            c = seasonal_climate(coords[0], coords[1], season)
            for k in ("temperature", "humidity", "rainfall"):
                if k in c:
                    climate[k] = round(float(c[k]), 2)
            climate_source = "weather_api"
        except WeatherUnavailable:
            pass
    features.update(climate)
    return {"features": features, "soil_source": soil["soil_source"],
            "climate_source": climate_source}
