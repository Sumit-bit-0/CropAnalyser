# backend/analysis/soil_nutrients.py
"""District-level soil nutrients (N, P, K, pH), offline CSV with fallback.

Bundled data/raw/india_district_soil.csv (state, district, N, P, K, ph). Lookup
by (state, district); fall back to the state average, then a national average,
so every location resolves. Mirrors the CSV-cache pattern in analysis/pincode.py.
"""
import csv

from config import DATA_RAW
from analysis.geo import normalize_state

SOIL_CSV = DATA_RAW / "india_district_soil.csv"
_ROWS = None  # cache: list of {state, district, N, P, K, ph}
_FIELDS = ("N", "P", "K", "ph")


def _dnorm(s: str) -> str:
    return (s or "").strip().lower()


def _load():
    global _ROWS
    if _ROWS is not None:
        return _ROWS
    out = []
    if SOIL_CSV.exists():
        with open(SOIL_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    out.append({
                        "state": normalize_state(r["state"]),
                        "district": _dnorm(r["district"]),
                        "N": float(r["N"]), "P": float(r["P"]),
                        "K": float(r["K"]), "ph": float(r["ph"]),
                    })
                except (KeyError, ValueError):
                    continue
    _ROWS = out
    return out


def _avg(rows):
    n = len(rows)
    return {k: round(sum(r[k] for r in rows) / n, 2) for k in _FIELDS}


def district_soil(state: str, district: str | None = None):
    """{N,P,K,ph, soil_source}; tiers district -> state -> national. None if no data."""
    rows = _load()
    if not rows:
        return None
    s, d = normalize_state(state), _dnorm(district)
    if d:
        hit = [r for r in rows if r["state"] == s and r["district"] == d]
        if hit:
            return {**_avg(hit), "soil_source": "district"}
    st = [r for r in rows if r["state"] == s]
    if st:
        return {**_avg(st), "soil_source": "state"}
    return {**_avg(rows), "soil_source": "national"}
