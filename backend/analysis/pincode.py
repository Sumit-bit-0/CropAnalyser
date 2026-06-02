"""Resolve an Indian pincode to a precise location, offline-first.

Tier 1 (offline): bundled data/raw/india_pincodes.csv (pincode -> area, district,
state, lat, lon). Forward lookup by pincode; reverse lookup (GPS) by nearest
pincode centroid. Tier 2 (Task 3): a free API fallback for pincodes absent from
the offline set. Mirrors the CSV-cache pattern in analysis/geo.py.
"""
import csv

import json
import urllib.request

from analysis.geo import get_centroid, haversine
from config import DATA_RAW

PINCODE_CSV = DATA_RAW / "india_pincodes.csv"
API_URL = "https://api.postalpincode.in/pincode/"
API_TIMEOUT = 4

_PINCODES = None  # module cache: {pincode: {pincode, area, district, state, lat, lon}}


def _load_pincodes() -> dict:
    global _PINCODES
    if _PINCODES is not None:
        return _PINCODES
    out = {}
    if PINCODE_CSV.exists():
        with open(PINCODE_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    out[r["pincode"].strip()] = {
                        "pincode": r["pincode"].strip(),
                        "area": r["area"].strip(),
                        "district": r["district"].strip(),
                        "state": r["state"].strip(),
                        "lat": float(r["lat"]),
                        "lon": float(r["lon"]),
                    }
                except (KeyError, ValueError):
                    continue
    _PINCODES = out
    return out


def resolve_pincode(pin: str):
    """6-digit pincode -> {pincode, area, district, state, lat, lon, source} or None."""
    pin = (pin or "").strip()
    if len(pin) != 6 or not pin.isdigit():
        return None
    hit = _load_pincodes().get(pin)
    if hit:
        return {**hit, "source": "offline"}
    return _resolve_via_api(pin)


def _resolve_via_api(pin: str):
    """Tier 2: postalpincode.in lookup. Returns names; coords approximated from the
    district centroid (the API has none). Any failure -> None (never blocks)."""
    try:
        with urllib.request.urlopen(API_URL + pin, timeout=API_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    rec = data[0] if isinstance(data, list) and data else {}
    offices = rec.get("PostOffice") or []
    if rec.get("Status") != "Success" or not offices:
        return None
    po = offices[0]
    state = (po.get("State") or "").strip()
    district = (po.get("District") or "").strip()
    coords = get_centroid(state, district)
    return {
        "pincode": pin,
        "area": (po.get("Name") or "").strip(),
        "district": district,
        "state": state,
        "lat": coords[0] if coords else None,
        "lon": coords[1] if coords else None,
        "source": "api",
    }


def nearest_pincode(lat: float, lon: float):
    """Reverse GPS -> nearest pincode centroid, or None if the table is empty."""
    best, best_d = None, float("inf")
    for rec in _load_pincodes().values():
        d = haversine(lat, lon, rec["lat"], rec["lon"])
        if d < best_d:
            best_d, best = d, rec
    if best is None:
        return None
    return {**best, "distance_km": round(best_d, 1), "source": "offline"}
