# backend/analysis/weather_fit.py
"""Weather Fit scorer for CropAdvisor (fusion module #4).

Scores each crop by how well the location's seasonal climate (from Open-Meteo,
via analysis.weather_client) matches the crop's climatic envelope, derived from
Crop_recommendation.csv. Gaussian z-distance over temperature/humidity,
max-normalized to 1.0 like the other modules. Only the 22 soil-model crops have
envelopes; the rest are omitted so fusion degrades them per-crop. Returns {} (the
whole module skipped) when coordinates can't be resolved or the weather call
fails — a recommendation is never blocked.
"""
import math
from pathlib import Path

import pandas as pd

from config import DATA_RAW
from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST
from analysis.geo import get_centroid
from analysis.weather_client import seasonal_climate

# rainfall is intentionally excluded: the Crop_recommendation.csv rainfall column
# is not real annual mm and is incomparable to live precipitation (it collapsed the
# weather signal in live testing). temperature + humidity are directly comparable.
_DIMS = ("temperature", "humidity")
_STD_FLOOR = 1e-6
_CSV_CANDIDATES = [DATA_RAW / "Crop_recommendation.csv",
                   Path(r"E:\DataSETAgri\Crop_recommendation.csv")]
_ENVELOPES = None


def _csv_path() -> Path:
    for p in _CSV_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(f"Crop_recommendation.csv not found in {_CSV_CANDIDATES}")


def crop_envelopes() -> dict:
    """Per-crop {dim: (mean, std)} for the soil-model crops (those with a
    non-None suitability label in the catalog). Cached."""
    global _ENVELOPES
    if _ENVELOPES is not None:
        return _ENVELOPES
    df = pd.read_csv(_csv_path())
    missing = [d for d in _DIMS if d not in df.columns]
    if missing:
        raise ValueError(f"Crop_recommendation.csv missing columns: {missing}")
    df["_label"] = df["label"].astype(str).str.strip().str.lower()
    env = {}
    for crop, meta in CANONICAL_CROPS.items():
        label = meta["suitability"]
        if label is None:
            continue
        sub = df[df["_label"] == label.lower()]
        if sub.empty:
            continue
        env[crop] = {d: (float(sub[d].mean()),
                         max(float(sub[d].std(ddof=0)), _STD_FLOOR)) for d in _DIMS}
    _ENVELOPES = env
    return env


def _fit(score: float) -> str:
    """good/fair/poor band for the max-normalized score (relative to the query set)."""
    return "good" if score >= 2 / 3 else "fair" if score >= 1 / 3 else "poor"


def weather_fit_scores(state, district, season, crops=None) -> dict:
    crops = list(crops) if crops else WHITELIST
    coords = get_centroid(state, district)
    if not coords:
        return {}
    try:
        climate = seasonal_climate(coords[0], coords[1], season)
    except Exception:
        return {}  # never block a recommendation on weather

    dims = [d for d in _DIMS if d in climate]
    if not dims:
        return {}
    env = crop_envelopes()
    raw = {}  # crop -> (similarity, climate-detail)
    for c in crops:
        e = env.get(c)
        if not e:
            continue
        zs = [(climate[d] - e[d][0]) / e[d][1] for d in dims]
        sim = math.exp(-0.5 * sum(z * z for z in zs) / len(zs))
        raw[c] = (sim, {d: round(climate[d], 1) for d in dims})
    if not raw:
        return {}

    top = max(s for s, _ in raw.values()) or 1.0
    return {c: {"score": round(s / top, 3), "fit": _fit(s / top), "climate": detail}
            for c, (s, detail) in raw.items()}
