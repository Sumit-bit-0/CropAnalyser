# backend/analysis/demand_gate.py
"""Processing-demand gate: a crop that must be processed locally (e.g. sugarcane
-> sugar mill) only ranks high near a facility. Curated coords in
data/raw/processing_units.csv (facility_type, name, state, district, lat, lon).
Generic by facility type so Phase 2 industries plug straight in."""
import csv

from config import DATA_RAW
from analysis.geo import haversine

PROCESSING_CSV = DATA_RAW / "processing_units.csv"
GATED_CROPS = {"sugarcane": "sugar_mill"}  # crop -> required facility type
NEAR_KM, FAR_KM, FLOOR = 50.0, 150.0, 0.2
_UNITS = None  # cache: list of {facility_type, name, lat, lon}


def _load():
    global _UNITS
    if _UNITS is not None:
        return _UNITS
    out = []
    if PROCESSING_CSV.exists():
        with open(PROCESSING_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    out.append({"facility_type": r["facility_type"].strip(),
                                "name": r["name"].strip(),
                                "lat": float(r["lat"]), "lon": float(r["lon"])})
                except (KeyError, ValueError):
                    continue
    _UNITS = out
    return out


def nearest_facility(facility_type: str, lat: float, lon: float):
    """{name, km} of the closest facility of this type, or None."""
    best, best_d = None, float("inf")
    for u in _load():
        if u["facility_type"] != facility_type:
            continue
        d = haversine(lat, lon, u["lat"], u["lon"])
        if d < best_d:
            best_d, best = d, u
    if best is None:
        return None
    return {"name": best["name"], "km": round(best_d, 1)}


def proximity_factor(km) -> float:
    """1.0 within NEAR_KM, linear taper to FLOOR at FAR_KM, FLOOR beyond/unknown."""
    if km is None:
        return FLOOR
    if km <= NEAR_KM:
        return 1.0
    if km >= FAR_KM:
        return FLOOR
    frac = (km - NEAR_KM) / (FAR_KM - NEAR_KM)
    return round(1.0 - frac * (1.0 - FLOOR), 4)
