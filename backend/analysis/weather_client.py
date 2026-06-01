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
    "whole year": tuple(range(1, 13)),
}


class WeatherUnavailable(Exception):
    """Raised when the archive can't be fetched or has no usable data."""


def season_months(season) -> tuple:
    return _SEASONS.get((season or "").strip().lower(), tuple(range(1, 13)))
