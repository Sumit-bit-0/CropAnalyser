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


from data.yield_dataset import fit_vocabs, encode, fit_target_scalers, scale_targets


def test_fit_and_encode_roundtrip():
    df = pd.concat([
        _frame("rice", 600, [2.0] * 600),
        _frame("wheat", 600, [3.0] * 600),
    ], ignore_index=True)
    df.loc[df.index[:300], "district"] = "Patna"
    vocabs = fit_vocabs(df)
    assert vocabs["canonical_crop"]["rice"] >= 1
    codes = encode(df, vocabs)
    assert codes["canonical_crop"].min() >= 1
    assert codes["district"].max() <= len(vocabs["district"])


def test_unknown_category_maps_to_zero():
    df = _frame("rice", 600, [2.0] * 600)
    vocabs = fit_vocabs(df)
    unk = pd.DataFrame({"state": ["Bihar"], "district": ["NoSuchDist"],
                        "season": ["Kharif"], "canonical_crop": ["rice"],
                        "crop_year": [2010], "crop_yield": [2.0]})
    codes = encode(unk, vocabs)
    assert int(codes["district"].iloc[0]) == 0  # unknown -> 0


def test_target_scaling_is_per_crop_and_invertible():
    df = pd.concat([_frame("rice", 600, list(np.linspace(1, 3, 600))),
                    _frame("sugarcane", 600, list(np.linspace(40, 70, 600)))],
                   ignore_index=True)
    scalers = fit_target_scalers(df)
    z = scale_targets(df, scalers)
    assert abs(z.mean()) < 1e-6
    s = scalers["sugarcane"]
    approx = z[df["canonical_crop"] == "sugarcane"] * s["std"] + s["mean"]
    assert np.allclose(approx.values,
                       df.loc[df["canonical_crop"] == "sugarcane", "crop_yield"].values, atol=1e-6)


import torch
from models.yield_mlp import YieldMLP


def test_yield_mlp_forward_shape():
    vocab_sizes = {"state": 5, "district": 50, "season": 6, "canonical_crop": 20}
    model = YieldMLP(vocab_sizes)
    cats = {k: torch.randint(0, v + 1, (8,)) for k, v in vocab_sizes.items()}
    year = torch.randn(8, 1)
    out = model(cats, year)
    assert out.shape == (8,)
