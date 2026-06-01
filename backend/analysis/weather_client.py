"""Live seasonal climatology from the Open-Meteo Archive API (ERA5; free, no key).

Turns (lat, lon, season) into the location's typical {temperature, humidity,
rainfall} for that season, averaged over recent years. Pure stdlib (urllib/json)
so it adds no dependency. Raises WeatherUnavailable on any network/parse failure
so callers can skip the weather term cleanly — it never fabricates data.
"""
import json
import urllib.parse
import urllib.request
from datetime import date
from functools import lru_cache

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
YEARS_BACK = 5      # number of complete past years to average
TIMEOUT = 4         # seconds per HTTP attempt

# India agronomic season -> calendar months. Unknown/blank -> all 12.
_SEASONS = {
    "kharif": (6, 7, 8, 9, 10),
    "rabi": (11, 12, 1, 2, 3),
    "summer": (3, 4, 5, 6),
    "zaid": (3, 4, 5, 6),
    "winter": (12, 1, 2),
    "autumn": (9, 10, 11),
    "whole year": tuple(range(1, 13)),  # DB stores "Whole Year" (two words)
}


class WeatherUnavailable(Exception):
    """Raised when the archive can't be fetched or has no usable data."""


def season_months(season) -> tuple:
    """Calendar month numbers (1–12) for an India agronomic season name.

    Case-insensitive; strips whitespace. Unknown/blank/None -> all 12 months.
    """
    return _SEASONS.get((season or "").strip().lower(), tuple(range(1, 13)))


def _fetch_archive(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    """GET the Open-Meteo daily archive; raise WeatherUnavailable on any failure."""
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": start_date, "end_date": end_date,
        "daily": "temperature_2m_mean,relative_humidity_2m_mean,precipitation_sum",
        "timezone": "auto",
    })
    url = f"{ARCHIVE_URL}?{params}"
    last = None
    for _ in range(2):  # one retry
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # network, timeout, JSON, HTTP error
            last = e
    raise WeatherUnavailable(f"archive fetch failed: {last}")


def seasonal_climate(lat: float, lon: float, season) -> dict:
    """Location's typical season climate. Cached by ~0.1deg coords + season."""
    return _seasonal_cached(round(lat, 1), round(lon, 1), (season or "").strip().lower())


@lru_cache(maxsize=512)
def _seasonal_cached(lat: float, lon: float, season: str) -> dict:
    months = season_months(season)
    end_year = date.today().year - 1
    start_year = end_year - (YEARS_BACK - 1)
    data = _fetch_archive(lat, lon, f"{start_year}-01-01", f"{end_year}-12-31")
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    if not times:
        raise WeatherUnavailable("empty archive response")

    out: dict = {}
    # temperature & humidity: mean of daily means over the season's months
    for key, name in (("temperature_2m_mean", "temperature"),
                      ("relative_humidity_2m_mean", "humidity")):
        vals = daily.get(key)
        if vals:
            picked = [v for t, v in zip(times, vals)
                      if v is not None and int(t[5:7]) in months]
            if picked:
                out[name] = sum(picked) / len(picked)

    # rainfall: total per calendar year, averaged across years (annual mm)
    rain = daily.get("precipitation_sum")
    if rain:
        per_year: dict = {}
        for t, v in zip(times, rain):
            if v is not None:
                per_year[t[:4]] = per_year.get(t[:4], 0.0) + v
        if per_year:
            out["rainfall"] = sum(per_year.values()) / len(per_year)

    if not out:
        raise WeatherUnavailable("no usable climate variables")
    return out
