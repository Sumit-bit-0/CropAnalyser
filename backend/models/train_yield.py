"""Train the multi-crop yield regressor on CUDA (RTX 3060). Run from backend/:
    venv\\Scripts\\python.exe -m models.train_yield
Writes saved_models/yield_model.pt, yield_vocabs.json, yield_target_scalers.json,
and yield_metrics.json. Skips saving the model if it can't beat the baseline.
"""
import json
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from config import MODELS_DIR, init_dirs
from data.yield_dataset import (build_frame, fit_vocabs, encode, fit_target_scalers,
                                scale_targets, temporal_split, CATEGORICALS, CUTOFF_YEAR)
from models.yield_mlp import YieldMLP

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

YEAR_MEAN, YEAR_STD = 2006.0, 6.0  # fixed scaling for crop_year (data spans 1997-2015)


def _to_tensors(codes, year_scaled, device):
    cats = {c: torch.tensor(codes[c].values, device=device) for c in CATEGORICALS}
    year = torch.tensor(year_scaled, dtype=torch.float32, device=device).unsqueeze(1)
    return cats, year


def _baseline_mae(train: pd.DataFrame, test: pd.DataFrame) -> float:
    key = ["state", "district", "season", "canonical_crop"]
    combo = train.groupby(key)["crop_yield"].mean()
    crop = train.groupby("canonical_crop")["crop_yield"].mean()
    def pred(row):
        k = (row["state"], row["district"], row["season"], row["canonical_crop"])
        if k in combo.index: return combo.loc[k]
        return crop.get(row["canonical_crop"], train["crop_yield"].mean())
    preds = test.apply(pred, axis=1).values
    return float(np.mean(np.abs(preds - test["crop_yield"].values)))


def main():
    init_dirs()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        print("WARNING: CUDA not available — training on CPU (violates project GPU rule).")
    print(f"Training yield model on device: {device}", flush=True)

    df = build_frame()
    print(f"Frame: {len(df):,} rows, {df['canonical_crop'].nunique()} crops", flush=True)
    train_df, holdout_df = temporal_split(df, CUTOFF_YEAR)
    print(f"train<= {CUTOFF_YEAR}: {len(train_df):,}  holdout: {len(holdout_df):,}", flush=True)

    vocabs = fit_vocabs(train_df)
    scalers = fit_target_scalers(train_df)
    holdout_df = holdout_df[holdout_df["canonical_crop"].isin(scalers)].copy()

    def prep(frame):
        codes = encode(frame, vocabs)
        yr = ((frame["crop_year"].values - YEAR_MEAN) / YEAR_STD).astype(np.float32)
        z = scale_targets(frame, scalers).values.astype(np.float32)
        return codes, yr, z

    tr_codes, tr_yr, tr_z = prep(train_df)
    ho_codes, ho_yr, ho_z = prep(holdout_df)

    vocab_sizes = {c: len(vocabs[c]) for c in CATEGORICALS}
    model = YieldMLP(vocab_sizes).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=0.005)
    loss_fn = nn.MSELoss()

    tr_cats, tr_year = _to_tensors(tr_codes, tr_yr, device)
    tr_y = torch.tensor(tr_z, device=device)
    ho_cats, ho_year = _to_tensors(ho_codes, ho_yr, device)
    ho_y = torch.tensor(ho_z, device=device)

    best, best_state, patience = float("inf"), None, 0
    for epoch in range(300):
        model.train(); opt.zero_grad()
        loss = loss_fn(model(tr_cats, tr_year), tr_y)
        loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            vloss = loss_fn(model(ho_cats, ho_year), ho_y).item()
        if vloss < best - 1e-4:
            best, best_state, patience = vloss, {k: v.cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            patience += 1
        if (epoch + 1) % 25 == 0:
            print(f"epoch {epoch+1}: train={loss.item():.4f} holdout_z_mse={vloss:.4f}", flush=True)
        if patience >= 30:
            print(f"early stop @ {epoch+1}", flush=True); break

    model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        pred_z = model(ho_cats, ho_year).cpu().numpy()
    means = holdout_df["canonical_crop"].map(lambda c: scalers[c]["mean"]).values
    stds = holdout_df["canonical_crop"].map(lambda c: scalers[c]["std"]).values
    pred_y = pred_z * stds + means
    true_y = holdout_df["crop_yield"].values
    model_mae = float(np.mean(np.abs(pred_y - true_y)))
    ss_res = float(np.sum((true_y - pred_y) ** 2))
    ss_tot = float(np.sum((true_y - true_y.mean()) ** 2)) or 1.0
    r2 = 1 - ss_res / ss_tot
    base_mae = _baseline_mae(train_df, holdout_df)

    metrics = {"model_mae": round(model_mae, 4), "baseline_mae": round(base_mae, 4),
               "r2": round(r2, 4), "beats_baseline": bool(model_mae < base_mae),
               "holdout_rows": int(len(holdout_df)), "crops": sorted(scalers.keys())}
    print("METRICS:", json.dumps(metrics, indent=2), flush=True)

    if not metrics["beats_baseline"]:
        print("=== DONE === model did NOT beat baseline; NOT saving model. "
              "Inference will fall back to historical mean.", flush=True)
        (MODELS_DIR / "yield_metrics.json").write_text(json.dumps(metrics, indent=2))
        return

    torch.save({"state_dict": model.cpu().state_dict(), "vocab_sizes": vocab_sizes,
                "year_mean": YEAR_MEAN, "year_std": YEAR_STD},
               MODELS_DIR / "yield_model.pt")
    (MODELS_DIR / "yield_vocabs.json").write_text(json.dumps(vocabs))
    (MODELS_DIR / "yield_target_scalers.json").write_text(json.dumps(scalers))
    (MODELS_DIR / "yield_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"=== DONE === saved yield model to {MODELS_DIR}", flush=True)


if __name__ == "__main__":
    main()
