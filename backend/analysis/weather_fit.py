# backend/analysis/weather_fit.py
"""Weather Fit scorer for CropAdvisor (fusion module #4).

Scores each crop by how well the location's seasonal climate (from Open-Meteo,
via analysis.weather_client) matches the crop's climatic envelope, derived from
Crop_recommendation.csv. Gaussian z-distance over temperature/humidity/rainfall,
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

_DIMS = ("temperature", "humidity", "rainfall")
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
    """Per-crop {dim: (mean, std)} for the 22 soil-model crops. Cached."""
    global _ENVELOPES
    if _ENVELOPES is not None:
        return _ENVELOPES
    df = pd.read_csv(_csv_path())
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
