"""Geolocation helpers for Mandi Comparison.

Market coordinates are resolved at district granularity if a district-centroid
CSV is bundled at ``data/raw/india_district_centroids.csv`` (columns:
``state, district, lat, lon``). Otherwise we fall back to approximate
state/UT centroids so the feature still works offline (coarser ranking).
"""
import csv
from math import radians, sin, cos, asin, sqrt
from config import DATA_RAW

# Approximate geographic centroids of Indian states/UTs (lat, lon).
STATE_CENTROIDS = {
    "andhra pradesh": (15.91, 79.74), "arunachal pradesh": (28.22, 94.73),
    "assam": (26.20, 92.94), "bihar": (25.70, 85.30), "chhattisgarh": (21.28, 81.87),
    "goa": (15.36, 74.06), "gujarat": (22.31, 72.14), "haryana": (29.06, 76.09),
    "himachal pradesh": (31.96, 77.19), "jharkhand": (23.61, 85.28),
    "karnataka": (15.32, 75.71), "kerala": (10.51, 76.27), "madhya pradesh": (23.47, 77.95),
    "maharashtra": (19.66, 75.30), "manipur": (24.66, 93.91), "meghalaya": (25.47, 91.37),
    "mizoram": (23.16, 92.94), "nagaland": (26.16, 94.56), "odisha": (20.95, 85.10),
    "punjab": (31.15, 75.34), "rajasthan": (27.02, 74.22), "sikkim": (27.53, 88.51),
    "tamil nadu": (11.13, 78.66), "telangana": (17.86, 79.36), "tripura": (23.75, 91.72),
    "uttar pradesh": (26.85, 80.91), "uttarakhand": (30.07, 79.11), "west bengal": (22.99, 87.86),
    "nct of delhi": (28.65, 77.19), "delhi": (28.65, 77.19),
    "jammu and kashmir": (33.78, 76.58), "ladakh": (34.21, 77.61),
    "puducherry": (11.94, 79.81), "pondicherry": (11.94, 79.81),
    "chandigarh": (30.73, 76.78), "andaman and nicobar islands": (11.74, 92.66),
    "dadra and nagar haveli": (20.18, 73.02), "daman and diu": (20.40, 72.83),
    "lakshadweep": (10.57, 72.64),
}

_DISTRICT_CENTROIDS = None


def _load_district_centroids() -> dict:
    global _DISTRICT_CENTROIDS
    if _DISTRICT_CENTROIDS is not None:
        return _DISTRICT_CENTROIDS
    path = DATA_RAW / "india_district_centroids.csv"
    out = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    key = (row["state"].strip().lower(), row["district"].strip().lower())
                    out[key] = (float(row["lat"]), float(row["lon"]))
                except (KeyError, ValueError):
                    continue
    _DISTRICT_CENTROIDS = out
    return out


def get_centroid(state: str, district: str):
    """Return (lat, lon) for a market's district, falling back to state, else None."""
    districts = _load_district_centroids()
    s = (state or "").strip().lower()
    d = (district or "").strip().lower()
    if (s, d) in districts:
        return districts[(s, d)]
    return STATE_CENTROIDS.get(s)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))
