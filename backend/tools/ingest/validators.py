"""Shared row-level validation for ingestion adapters.

All adapters normalize their source into a DataFrame, then call the matching
validate_* function here. Validators drop (never raise on) bad rows, normalize
state names, dedupe, and reject crops outside the canonical WHITELIST so the
downstream engine only ever sees crops it can reason about.
"""
import pandas as pd

from analysis.geo import normalize_state
from analysis.crop_catalog import WHITELIST

LAT_MIN, LAT_MAX = 6.0, 37.5
LON_MIN, LON_MAX = 68.0, 97.5

_WHITELIST = set(WHITELIST)


def in_india_bbox(lat, lon) -> bool:
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def _coerce_float(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def validate_facilities(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a processing_units-shaped frame."""
    required = {"facility_type", "name", "state", "district", "lat", "lon",
                "crop", "source", "source_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"facilities frame missing columns: {sorted(missing)}")
    df = df.copy()
    df = _coerce_float(df, ["lat", "lon"])
    df = df.dropna(subset=["lat", "lon"])
    df = df[df.apply(lambda r: in_india_bbox(r["lat"], r["lon"]), axis=1)]
    df["state"] = df["state"].map(normalize_state)
    df["crop"] = df["crop"].str.strip().str.lower()
    df = df[df["crop"].isin(_WHITELIST)]
    df = df.drop_duplicates(subset=["source", "source_id"])
    df = df.drop_duplicates(subset=["name", "lat", "lon"])
    return df.reset_index(drop=True)


def validate_soil(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a soil_nutrients-shaped frame."""
    required = {"state", "district", "N", "P", "K", "ph", "source"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"soil frame missing columns: {sorted(missing)}")
    df = df.copy()
    df = _coerce_float(df, ["N", "P", "K", "ph"])
    df = df.dropna(subset=["N", "P", "K"], how="all")
    df["state"] = df["state"].map(normalize_state)
    return df.reset_index(drop=True)


def validate_crop_map(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a facility_crop_map-shaped frame (crop -> facility_type)."""
    required = {"crop", "facility_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"crop_map frame missing columns: {sorted(missing)}")
    df = df.copy()
    df["crop"] = df["crop"].str.strip().str.lower()
    df["facility_type"] = df["facility_type"].str.strip()
    df = df[df["crop"].isin(_WHITELIST)]
    df = df.drop_duplicates(subset=["crop"])
    return df.reset_index(drop=True)
