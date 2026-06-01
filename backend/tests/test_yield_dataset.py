import numpy as np
import pandas as pd
import pytest
from data.yield_dataset import clip_outliers, eligible_crops, temporal_split, MIN_ROWS


def _frame(crop, n, yields, years=None):
    years = years or [2000 + (i % 16) for i in range(n)]
    return pd.DataFrame({
        "state": ["Bihar"] * n, "district": ["Begusarai"] * n,
        "season": ["Kharif"] * n, "canonical_crop": [crop] * n,
        "crop_year": years[:n], "crop_yield": yields,
    })


def test_clip_outliers_caps_per_crop_99th_pct():
    ys = [2.0] * 99 + [1494.0]
    out = clip_outliers(_frame("maize", 100, ys))
    assert out["crop_yield"].max() < 100        # the 1494 outlier is clipped
    assert out["crop_yield"].min() >= 0


def test_eligible_crops_drops_sparse_crops():
    big = _frame("rice", MIN_ROWS + 10, [2.0] * (MIN_ROWS + 10))
    tiny = _frame("apple", 4, [1.0, 1.1, 0.9, 1.0], years=[2001, 2002, 2003, 2004])
    df = pd.concat([big, tiny], ignore_index=True)
    keep = eligible_crops(df)
    assert "rice" in keep and "apple" not in keep


def test_temporal_split_by_year():
    df = _frame("rice", 20, [2.0] * 20, years=list(range(1997, 2017)))
    train, holdout = temporal_split(df, cutoff_year=2012)
    assert train["crop_year"].max() <= 2012
    assert holdout["crop_year"].min() >= 2013
