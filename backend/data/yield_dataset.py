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
