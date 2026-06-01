"""Build the yield-model training frame from district_crop_history.

Pure pandas/numpy (no torch): load mapped history, clip per-crop yield outliers
(unit/entry errors like maize=1494 vs median 1.8), drop crops with too little
history, encode categoricals to integer ids, and split temporally.
"""
import numpy as np
import pandas as pd

from database import query

CATEGORICALS = ["state", "district", "season", "canonical_crop"]
MIN_ROWS = 500     # per-crop row floor (drops coffee=6, apple=4, watermelon=85...)
MIN_YEARS = 5      # per-crop distinct-year floor
CUTOFF_YEAR = 2012  # train <= cutoff, holdout > cutoff


def load_history() -> pd.DataFrame:
    return query("""
        SELECT state, district, season, canonical_crop, crop_year, crop_yield
        FROM district_crop_history
        WHERE canonical_crop IS NOT NULL AND crop_yield > 0
              AND crop_year IS NOT NULL
    """)


def clip_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Winsorize crop_yield to the per-crop [1st, 99th] percentile."""
    df = df.copy()
    lo = df.groupby("canonical_crop")["crop_yield"].transform(lambda s: s.quantile(0.01))
    hi = df.groupby("canonical_crop")["crop_yield"].transform(lambda s: s.quantile(0.99))
    df["crop_yield"] = df["crop_yield"].clip(lower=lo, upper=hi)
    return df


def eligible_crops(df: pd.DataFrame) -> set:
    g = df.groupby("canonical_crop").agg(
        rows=("crop_yield", "size"), yrs=("crop_year", "nunique"))
    return set(g[(g["rows"] >= MIN_ROWS) & (g["yrs"] >= MIN_YEARS)].index)


def temporal_split(df: pd.DataFrame, cutoff_year: int = CUTOFF_YEAR):
    train = df[df["crop_year"] <= cutoff_year].copy()
    holdout = df[df["crop_year"] > cutoff_year].copy()
    return train, holdout


def build_frame() -> pd.DataFrame:
    """Full pipeline: load -> clip -> keep eligible crops."""
    df = load_history()
    df = clip_outliers(df)
    keep = eligible_crops(df)
    return df[df["canonical_crop"].isin(keep)].reset_index(drop=True)


def fit_vocabs(df: pd.DataFrame) -> dict:
    """Per-categorical {value: id}; ids start at 1, 0 reserved for unknown."""
    vocabs = {}
    for col in CATEGORICALS:
        uniques = sorted(df[col].astype(str).unique())
        vocabs[col] = {v: i + 1 for i, v in enumerate(uniques)}
    return vocabs


def encode(df: pd.DataFrame, vocabs: dict) -> pd.DataFrame:
    """Map categoricals to int ids (unknown -> 0). Returns a new frame of codes."""
    out = pd.DataFrame(index=df.index)
    for col in CATEGORICALS:
        out[col] = df[col].astype(str).map(vocabs[col]).fillna(0).astype("int64")
    return out


def fit_target_scalers(df: pd.DataFrame) -> dict:
    """Per-crop {mean, std} of crop_yield for standardization."""
    scalers = {}
    for crop, sub in df.groupby("canonical_crop"):
        mean = float(sub["crop_yield"].mean())
        std = float(sub["crop_yield"].std(ddof=0)) or 1.0
        scalers[crop] = {"mean": mean, "std": std}
    return scalers


def scale_targets(df: pd.DataFrame, scalers: dict) -> pd.Series:
    means = df["canonical_crop"].map(lambda c: scalers[c]["mean"])
    stds = df["canonical_crop"].map(lambda c: scalers[c]["std"])
    return (df["crop_yield"] - means) / stds
