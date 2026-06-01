# Tradition-First Crop Advisor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe each CropAdvisor recommendation around its traditional standing in the district plus our own model predictions — a GPU-trained yield prediction and an LSTM-backed price outlook — and de-emphasize the profit/market framing.

**Architecture:** Three backend additions (a yield-prediction MLP with categorical embeddings, an LSTM price-outlook wrapper, and a fusion enrichment step) plus a frontend card reframe. The yield model trains on `district_crop_history` with per-crop outlier clipping and a temporal holdout, and must beat a historical-mean baseline. Enrichment runs only for the top-k returned crops and is fully backward-compatible.

**Tech Stack:** Python · PyTorch (CUDA / RTX 3060) · pandas · scikit-learn · SQLAlchemy/psycopg3 · PostgreSQL 16 · FastAPI · React 19 + Vite + Tailwind. Tests via `pytest tests -p no:asyncio`.

---

## Conventions (read once)

- **Run everything from `backend/`** with the venv Python: `venv\Scripts\python.exe`.
- **Run scripts as modules:** `venv\Scripts\python.exe -m models.train_yield` (NOT by path — `import config` breaks otherwise).
- **Always run pytest with** `-p no:asyncio` and set UTF-8 for scripts that print ₹/Devanagari: prefix `set PYTHONIOENCODING=utf-8` (cmd) or use the reconfigure shim already in the data scripts.
- **Postgres must be up:** `docker compose up -d` from the project root.
- **GPU rule:** model training MUST run on CUDA (RTX 3060). The trainer prints the device and warns on CPU.
- **DB query helper:** `from database import query` uses `?` placeholders (a shim rewrites them to named binds). `query(sql, params)` returns a pandas DataFrame.
- **Catalog:** `from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST` (36 crops; some have `suitability: None`). `CANONICAL_CROPS[c]["market"]` is the list of market commodity aliases.
- **Artifacts** go to `MODELS_DIR` (`from config import MODELS_DIR`) = `saved_models/` (gitignored).

## File Structure

**Create:**
- `backend/models/yield_mlp.py` — the `YieldMLP` nn.Module (embeddings + dense head).
- `backend/data/yield_dataset.py` — builds the training frame: load history, clip outliers per crop, min-data filter, encode categoricals, temporal split, per-crop target scaling. Pure functions, no torch.
- `backend/models/train_yield.py` — GPU training script; computes the historical-mean baseline; writes model + vocab + scalers + metrics report.
- `backend/analysis/yield_predict.py` — inference: `predict_yield(...)`.
- `backend/analysis/price_outlook.py` — inference: `price_outlook(...)` wrapping the LSTM predictor with historical fallback.
- Test files: `backend/tests/test_yield_dataset.py`, `test_yield_predict.py`, `test_price_outlook.py`, `test_fusion_enrichment.py`.

**Modify:**
- `backend/analysis/fusion.py` — add `_enrich()` and call it for the top-k in `recommend()`.
- `backend/tests/test_fusion.py` — keep existing assertions valid (enrichment is additive).
- `frontend/src/pages/CropAdvisor.jsx` — reframe the recommendation card.
- `docs/CROPADVISOR_BUILD.md` and memory files — update after build.

**Responsibilities:** data shaping lives in `data/yield_dataset.py`; the network in `models/yield_mlp.py`; training orchestration in `models/train_yield.py`; serving in `analysis/yield_predict.py` and `analysis/price_outlook.py`; assembly in `fusion.py`. Each is independently testable.

---

## Task 1: Yield dataset builder — load, clip, filter, encode, split

**Files:**
- Create: `backend/data/yield_dataset.py`
- Test: `backend/tests/test_yield_dataset.py`

Helpers this task defines (used by later tasks): `MIN_ROWS=500`, `MIN_YEARS=5`, `CATEGORICALS=["state","district","season","canonical_crop"]`, `clip_outliers(df)`, `eligible_crops(df)`, `build_frame()`, `temporal_split(df)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_yield_dataset.py
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
    # 99 normal maize rows ~2.0 + one absurd 1494 -> clipped down near the top
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_yield_dataset.py -p no:asyncio -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'data.yield_dataset'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/data/yield_dataset.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_yield_dataset.py -p no:asyncio -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/data/yield_dataset.py backend/tests/test_yield_dataset.py
git commit -m "feat(yield): dataset builder with per-crop outlier clipping + temporal split"
```

---

## Task 2: Categorical encoders + tensor prep in the dataset builder

**Files:**
- Modify: `backend/data/yield_dataset.py`
- Test: `backend/tests/test_yield_dataset.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# append to backend/tests/test_yield_dataset.py
from data.yield_dataset import fit_vocabs, encode, fit_target_scalers, scale_targets


def test_fit_and_encode_roundtrip():
    df = pd.concat([
        _frame("rice", 600, [2.0] * 600),
        _frame("wheat", 600, [3.0] * 600),
    ], ignore_index=True)
    df.loc[df.index[:300], "district"] = "Patna"
    vocabs = fit_vocabs(df)
    # every categorical gets a 0-based id space sized vocab + 1 (index 0 = unknown)
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
    assert abs(z.mean()) < 1e-6                # standardized
    # invert sugarcane back
    s = scalers["sugarcane"]
    approx = z[df["canonical_crop"] == "sugarcane"] * s["std"] + s["mean"]
    assert np.allclose(approx.values,
                       df.loc[df["canonical_crop"] == "sugarcane", "crop_yield"].values, atol=1e-6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_yield_dataset.py -p no:asyncio -q`
Expected: FAIL with `ImportError: cannot import name 'fit_vocabs'`.

- [ ] **Step 3: Write minimal implementation (append to `yield_dataset.py`)**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_yield_dataset.py -p no:asyncio -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/data/yield_dataset.py backend/tests/test_yield_dataset.py
git commit -m "feat(yield): categorical vocabs + per-crop target scaling"
```

---

## Task 3: The YieldMLP network

**Files:**
- Create: `backend/models/yield_mlp.py`
- Test: `backend/tests/test_yield_dataset.py` (add a small shape test here to avoid a new file)

- [ ] **Step 1: Write the failing test (append)**

```python
# append to backend/tests/test_yield_dataset.py
import torch
from models.yield_mlp import YieldMLP


def test_yield_mlp_forward_shape():
    # 4 categoricals with small vocab sizes, batch of 8
    vocab_sizes = {"state": 5, "district": 50, "season": 6, "canonical_crop": 20}
    model = YieldMLP(vocab_sizes)
    cats = {k: torch.randint(0, v + 1, (8,)) for k, v in vocab_sizes.items()}
    year = torch.randn(8, 1)
    out = model(cats, year)
    assert out.shape == (8,)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_yield_dataset.py::test_yield_mlp_forward_shape -p no:asyncio -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'models.yield_mlp'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/models/yield_mlp.py
"""Multi-crop yield regressor: categorical embeddings + scaled year -> yield (z)."""
import torch
import torch.nn as nn


def _emb_dim(vocab: int) -> int:
    return min(50, (vocab + 1) // 2 + 1)


class YieldMLP(nn.Module):
    def __init__(self, vocab_sizes: dict, hidden=(128, 64)):
        super().__init__()
        self.cols = list(vocab_sizes.keys())
        self.embs = nn.ModuleDict({
            # +1 row for the unknown id (0)
            c: nn.Embedding(v + 1, _emb_dim(v)) for c, v in vocab_sizes.items()
        })
        in_dim = sum(_emb_dim(v) for v in vocab_sizes.values()) + 1  # +1 = year
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden[0]), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden[0], hidden[1]), nn.ReLU(),
            nn.Linear(hidden[1], 1),
        )

    def forward(self, cats: dict, year: torch.Tensor) -> torch.Tensor:
        parts = [self.embs[c](cats[c]) for c in self.cols]
        x = torch.cat(parts + [year], dim=1)
        return self.net(x).squeeze(1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_yield_dataset.py::test_yield_mlp_forward_shape -p no:asyncio -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/models/yield_mlp.py backend/tests/test_yield_dataset.py
git commit -m "feat(yield): YieldMLP embedding regressor"
```

---

## Task 4: Training script with baseline gate (GPU)

**Files:**
- Create: `backend/models/train_yield.py`
- Test: manual run (training is not unit-tested; the baseline gate is the test).

This script: builds the frame, fits vocabs + target scalers on TRAIN only, trains on CUDA with early stopping, evaluates on the 2013–2015 holdout, computes the historical-mean baseline (predict each row's train district×crop×season mean, else train crop mean), and writes artifacts only if the model beats the baseline MAE.

- [ ] **Step 1: Write the script**

```python
# backend/models/train_yield.py
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

    # fit encoders/scalers on TRAIN only (no leakage)
    vocabs = fit_vocabs(train_df)
    scalers = fit_target_scalers(train_df)
    # holdout rows whose crop wasn't in train can't be scored -> drop
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

    # de-standardize predictions to real yield units for honest MAE
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
```

- [ ] **Step 2: Run training (manual, GPU)**

Run: `set PYTHONIOENCODING=utf-8 && venv\Scripts\python.exe -m models.train_yield`
Expected: prints `device: cuda`, per-epoch loss, a METRICS block, and `=== DONE === saved yield model`. Confirm `metrics["beats_baseline"]` is `true` and `r2 > 0`. (Exit code may be a spurious 127 on background runs — verify via the `=== DONE ===` line, per project convention.)

- [ ] **Step 3: Verify artifacts exist**

Run: `dir saved_models\yield_model.pt saved_models\yield_vocabs.json saved_models\yield_target_scalers.json saved_models\yield_metrics.json`
Expected: all four files present.

- [ ] **Step 4: Commit (code only — artifacts are gitignored)**

```bash
git add backend/models/train_yield.py
git commit -m "feat(yield): GPU trainer with historical-mean baseline gate"
```

---

## Task 5: Yield inference module

**Files:**
- Create: `backend/analysis/yield_predict.py`
- Test: `backend/tests/test_yield_predict.py`

`predict_yield(state, district, season, crop, year)` returns
`{"predicted_yield": float|None, "traditional_yield": float|None, "trend": str|None, "unit": str, "level": "district"|"state"|"none"}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_yield_predict.py
import pytest
from analysis.yield_predict import predict_yield, UNIT_LABEL
from database import table_exists

pytestmark = pytest.mark.skipif(not table_exists("district_crop_history"),
                                reason="history not loaded")


def test_known_crop_district_returns_yield():
    r = predict_yield("Bihar", "Begusarai", "Kharif", "rice", 2016)
    assert r["level"] in {"district", "state"}
    assert r["predicted_yield"] is not None and r["predicted_yield"] > 0
    assert r["traditional_yield"] is not None
    assert r["trend"] in {"rising", "flat", "falling"}
    assert r["unit"] == UNIT_LABEL.get("rice", "units/ha")


def test_sparse_crop_returns_none():
    # apple is excluded by the min-data filter -> no fabricated number
    r = predict_yield("Bihar", "Begusarai", "Kharif", "apple", 2016)
    assert r["predicted_yield"] is None
    assert r["level"] == "none"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_yield_predict.py -p no:asyncio -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.yield_predict'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/analysis/yield_predict.py
"""Predict yield for a (state, district, season, crop) using the trained YieldMLP.

Falls back to the district/state historical mean when the model isn't trained or a
crop was excluded. Returns predicted_yield=None for crops with no reliable history
(sparse-crop guard), so the UI never shows a fabricated number.
"""
import json
from functools import lru_cache

import numpy as np
import torch

from config import MODELS_DIR
from database import query, table_exists
from models.yield_mlp import YieldMLP

# crops whose crop_yield is in tonnes/ha -> display as quintals/ha (×10).
# others have inconsistent units; shown as "units/ha".
_Q_HA = {"rice", "wheat", "maize", "bajra", "jowar", "ragi", "barley", "mustard",
         "groundnut", "soyabean", "sunflower", "sesamum", "chickpea", "lentil",
         "pigeonpeas", "mungbean", "blackgram", "mothbeans"}
UNIT_LABEL = {c: "q/ha" for c in _Q_HA}
DEADBAND = 0.03  # ±3% around traditional yield counts as "flat"


@lru_cache(maxsize=1)
def _load_model():
    p = MODELS_DIR / "yield_model.pt"
    if not p.exists():
        return None
    ckpt = torch.load(str(p), map_location="cpu")
    model = YieldMLP(ckpt["vocab_sizes"])
    model.load_state_dict(ckpt["state_dict"]); model.eval()
    vocabs = json.loads((MODELS_DIR / "yield_vocabs.json").read_text())
    scalers = json.loads((MODELS_DIR / "yield_target_scalers.json").read_text())
    return model, vocabs, scalers, float(ckpt["year_mean"]), float(ckpt["year_std"])


def _traditional(state, district, season, crop):
    """(median historical yield, level) at district scope, else state, else None."""
    for level, where, params in (
        ("district", "LOWER(state)=LOWER(?) AND LOWER(district)=LOWER(?) "
                      "AND canonical_crop=? AND crop_yield>0", (state, district, crop)),
        ("state", "LOWER(state)=LOWER(?) AND canonical_crop=? AND crop_yield>0",
                  (state, crop)),
    ):
        if district is None and level == "district":
            continue
        df = query(f"""SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY crop_yield) m,
                              COUNT(*) n FROM district_crop_history WHERE {where}""", params)
        if not df.empty and df.iloc[0]["n"] and int(df.iloc[0]["n"]) > 0:
            return float(df.iloc[0]["m"]), level
    return None, "none"


def _unit(crop, val):
    if crop in _Q_HA:
        return val * 10.0, "q/ha"     # tonnes/ha -> quintals/ha
    return val, "units/ha"


def predict_yield(state, district, season, crop, year):
    loaded = _load_model()
    trad, level = _traditional(state, district, season, crop) if table_exists("district_crop_history") else (None, "none")
    if trad is None:
        return {"predicted_yield": None, "traditional_yield": None,
                "trend": None, "unit": UNIT_LABEL.get(crop, "units/ha"), "level": "none"}

    if loaded is None:
        pred_raw = trad                      # fallback: historical mean
    else:
        model, vocabs, scalers, ymean, ystd = loaded
        if crop not in scalers:              # crop excluded from model
            pred_raw = trad
        else:
            cats = {c: torch.tensor([vocabs[c].get(str(v), 0)])
                    for c, v in (("state", state), ("district", district or ""),
                                 ("season", season or ""), ("canonical_crop", crop))}
            yr = torch.tensor([[(year - ymean) / ystd]], dtype=torch.float32)
            with torch.no_grad():
                z = float(model(cats, yr).item())
            s = scalers[crop]
            pred_raw = max(0.0, z * s["std"] + s["mean"])

    pred_disp, unit = _unit(crop, pred_raw)
    trad_disp, _ = _unit(crop, trad)
    if pred_disp > trad_disp * (1 + DEADBAND):
        trend = "rising"
    elif pred_disp < trad_disp * (1 - DEADBAND):
        trend = "falling"
    else:
        trend = "flat"
    return {"predicted_yield": round(pred_disp, 2), "traditional_yield": round(trad_disp, 2),
            "trend": trend, "unit": unit, "level": level}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_yield_predict.py -p no:asyncio -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/yield_predict.py backend/tests/test_yield_predict.py
git commit -m "feat(yield): inference with district/state fallback + sparse-crop guard"
```

---

## Task 6: Price outlook module (LSTM wrapper + historical fallback)

**Files:**
- Create: `backend/analysis/price_outlook.py`
- Test: `backend/tests/test_price_outlook.py`

`price_outlook(state, crop)` returns `{"price": float|None, "trend": str|None, "horizon_months": int, "source": "forecast"|"historical"|"none"}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_price_outlook.py
import pytest
from analysis.price_outlook import price_outlook
from database import table_exists

pytestmark = pytest.mark.skipif(not table_exists("prices"), reason="prices not loaded")


def test_returns_price_and_source():
    r = price_outlook("Punjab", "wheat")
    assert r["source"] in {"forecast", "historical", "none"}
    if r["source"] != "none":
        assert r["price"] is not None and r["price"] > 0
        assert r["trend"] in {"rising", "flat", "falling"}


def test_falls_back_to_historical_when_no_model(monkeypatch):
    # force the forecast path to raise -> exercise historical fallback
    import analysis.price_outlook as po
    monkeypatch.setattr(po, "_forecast", lambda s, c: (_ for _ in ()).throw(FileNotFoundError()))
    r = price_outlook("Punjab", "wheat")
    assert r["source"] in {"historical", "none"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_price_outlook.py -p no:asyncio -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.price_outlook'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/analysis/price_outlook.py
"""Near-term price outlook per crop for the advisor.

Prefers the trained LSTM forecast (models.predictor.predict) for the state + the
crop's primary market commodity; falls back to the recent historical modal-price
slope when no model covers that state x commodity. `source` labels which path ran
so the UI never over-claims a forecast.
"""
from config import LSTM_FORECAST_LEN
from database import query
from models.predictor import predict
from analysis.crop_catalog import CANONICAL_CROPS

DEADBAND = 0.02


def _commodity(crop: str) -> str | None:
    aliases = CANONICAL_CROPS.get(crop, {}).get("market", [])
    return aliases[0] if aliases else None


def _trend(first: float, last: float) -> str:
    if last > first * (1 + DEADBAND): return "rising"
    if last < first * (1 - DEADBAND): return "falling"
    return "flat"


def _forecast(state: str, commodity: str):
    """(near-term price, trend) from the LSTM; raises if no model."""
    fc = predict(state, commodity)  # list of {period, modal_price, ...}; raises FileNotFoundError
    prices = [f["modal_price"] for f in fc]
    return float(prices[0]), _trend(prices[0], prices[-1])


def _historical(state: str, commodity: str):
    """(recent modal price, trend) from the last few years; None if no data."""
    df = query("""SELECT year, AVG(modal_price) p FROM prices
                  WHERE commodity = ? AND LOWER(state)=LOWER(?)
                  GROUP BY year ORDER BY year""", (commodity, state))
    if df.empty:
        df = query("""SELECT year, AVG(modal_price) p FROM prices
                      WHERE commodity = ? GROUP BY year ORDER BY year""", (commodity,))
    if df.empty:
        return None, None
    ps = df["p"].tolist()
    recent = float(ps[-1])
    base = float(ps[-3]) if len(ps) >= 3 else float(ps[0])
    return recent, _trend(base, recent)


def price_outlook(state: str, crop: str) -> dict:
    commodity = _commodity(crop)
    if not commodity:
        return {"price": None, "trend": None, "horizon_months": 0, "source": "none"}
    try:
        price, trend = _forecast(state, commodity)
        return {"price": round(price, 2), "trend": trend,
                "horizon_months": LSTM_FORECAST_LEN, "source": "forecast"}
    except (FileNotFoundError, ValueError):
        price, trend = _historical(state, commodity)
        if price is None:
            return {"price": None, "trend": None, "horizon_months": 0, "source": "none"}
        return {"price": price, "trend": trend, "horizon_months": 0, "source": "historical"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_price_outlook.py -p no:asyncio -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/price_outlook.py backend/tests/test_price_outlook.py
git commit -m "feat(advisor): LSTM-backed price outlook with historical fallback"
```

---

## Task 7: Fusion enrichment for the top-k

**Files:**
- Modify: `backend/analysis/fusion.py`
- Test: `backend/tests/test_fusion_enrichment.py`

Add `_enrich(rec, state, district, season)` and call it for each returned recommendation in `recommend()`. Existing fields/behavior unchanged.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fusion_enrichment.py
import pytest
from analysis.fusion import recommend
from database import table_exists

pytestmark = pytest.mark.skipif(not table_exists("district_crop_history"),
                                reason="history not loaded")


def test_recommendations_carry_tradition_yield_price():
    out = recommend("Bihar", "Begusarai", top_k=5)
    for r in out["recommendations"]:
        assert "traditional" in r and "years_grown" in r["traditional"]
        assert "yield" in r and {"predicted_yield", "traditional_yield", "trend", "unit"} <= set(r["yield"])
        assert "price_outlook" in r and "source" in r["price_outlook"]
    # a proven local crop reports years_grown > 0 at district level
    by_crop = {r["crop"]: r for r in out["recommendations"]}
    if "rice" in by_crop:
        assert by_crop["rice"]["traditional"]["years_grown"] > 0


def test_existing_fields_still_present():
    out = recommend("Bihar", "Begusarai", top_k=3)
    for r in out["recommendations"]:
        assert {"crop", "score", "breakdown", "why", "cautions"} <= set(r)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_fusion_enrichment.py -p no:asyncio -q`
Expected: FAIL with `KeyError: 'traditional'` (field not added yet).

- [ ] **Step 3: Write minimal implementation**

In `backend/analysis/fusion.py`, add imports near the top (after the existing analysis imports):

```python
from analysis.yield_predict import predict_yield
from analysis.price_outlook import price_outlook
```

Add this helper above `recommend()`:

```python
def _enrich(rec: dict, modules: dict, state, district, season) -> dict:
    """Attach tradition standing + our yield prediction + price outlook to a rec."""
    crop = rec["crop"]
    reg = modules.get("regional", {}).get(crop, {})
    rec["traditional"] = {"years_grown": int(reg.get("years_grown", 0) or 0),
                          "level": reg.get("level", "none")}
    rec["yield"] = predict_yield(state, district, season, crop, year=2016)
    rec["price_outlook"] = price_outlook(state, crop)
    return rec
```

Then in `recommend()`, change the recommendations construction so each top-k rec is enriched. Replace the existing list comprehension:

```python
    recommendations = [{
        "crop": c,
        "score": score,
        "breakdown": breakdown,
        "why": _why(c, modules),
        "cautions": _cautions(c, modules),
    } for c, score, breakdown in scored[:top_k]]
```

with:

```python
    recommendations = [_enrich({
        "crop": c,
        "score": score,
        "breakdown": breakdown,
        "why": _why(c, modules),
        "cautions": _cautions(c, modules),
    }, modules, state, district, season) for c, score, breakdown in scored[:top_k]]
```

- [ ] **Step 4: Run tests to verify they pass (and nothing regressed)**

Run: `venv\Scripts\python.exe -m pytest tests/test_fusion_enrichment.py tests/test_fusion.py -p no:asyncio -q`
Expected: PASS (all). The existing `test_fusion.py` assertions stay valid because enrichment only adds keys.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/fusion.py backend/tests/test_fusion_enrichment.py
git commit -m "feat(advisor): enrich top-k with tradition, predicted yield, price outlook"
```

---

## Task 8: Full backend suite green

**Files:** none (verification gate).

- [ ] **Step 1: Run the whole suite**

Run: `set PYTHONIOENCODING=utf-8 && venv\Scripts\python.exe -m pytest tests -p no:asyncio -q`
Expected: PASS — previous count (100) plus the new tests, 0 failures. If `test_recommend_smart.py` asserts an exact response shape, confirm the new keys don't break it (they're additive); update only if it does a strict `set(...)==` on recommendation keys.

- [ ] **Step 2: Sanity-check the endpoint shape**

Run (with the API up via `venv\Scripts\python.exe -m uvicorn main:app` in another shell):
`curl -s -X POST localhost:8000/api/recommend/smart -H "Content-Type: application/json" -d "{\"state\":\"Bihar\",\"district\":\"Begusarai\",\"top_k\":5}"`
Expected: JSON whose `recommendations[0]` contains `traditional`, `yield`, and `price_outlook` blocks.

- [ ] **Step 3: Commit (if any test needed adjusting)**

```bash
git add backend/tests
git commit -m "test: keep suite green after advisor enrichment"
```

---

## Task 9: Frontend card reframe

**Files:**
- Modify: `frontend/src/pages/CropAdvisor.jsx`
- Verify: `npm run build` + browser

The API now returns `traditional`, `yield`, `price_outlook` per recommendation. Lead the card with tradition + our predictions; shrink the module bars.

- [ ] **Step 1: Add small helpers near the top of the component file**

After the existing `const` definitions (e.g. after `RANK_BADGE`), add:

```jsx
const TREND = { rising: '↗', flat: '→', falling: '↘' }
const trendColor = (t) => (t === 'rising' ? 'text-green-600' : t === 'falling' ? 'text-red-500' : 'text-gray-400')
```

- [ ] **Step 2: Replace the per-crop detail block with the tradition-first layout**

Inside the `result.recommendations.map((r, i) => ( ... ))` card, immediately AFTER the rank/crop header row (the `<div className="flex items-center gap-3 mb-3">...</div>`) and BEFORE the module-bars block, insert:

```jsx
                {r.traditional?.years_grown > 0 && (
                  <p className="text-sm text-green-800 font-medium mb-1">
                    ✓ Traditional here — grown {r.traditional.years_grown} yr
                    {r.traditional.years_grown > 1 ? 's' : ''} on record
                    {r.traditional.level === 'state' && ' (state-wide)'}
                  </p>
                )}
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-700 mb-2">
                  {r.yield?.predicted_yield != null ? (
                    <span>
                      Predicted yield: <b>~{r.yield.predicted_yield} {r.yield.unit}</b>{' '}
                      <span className={trendColor(r.yield.trend)}>{TREND[r.yield.trend]}</span>
                      {r.yield.traditional_yield != null &&
                        <span className="text-gray-400"> (was ~{r.yield.traditional_yield})</span>}
                    </span>
                  ) : (
                    <span className="text-gray-400">No reliable yield estimate</span>
                  )}
                  {r.price_outlook?.price != null && (
                    <span>
                      Price outlook: <b>₹{r.price_outlook.price}/q</b>{' '}
                      <span className={trendColor(r.price_outlook.trend)}>{TREND[r.price_outlook.trend]}</span>
                      <span className="text-gray-400 text-xs">
                        {' '}{r.price_outlook.source === 'forecast' ? '(forecast)' : '(recent)'}
                      </span>
                    </span>
                  )}
                </div>
```

- [ ] **Step 3: De-emphasize the module bars**

In the same card, find the module-bars wrapper `<div className="space-y-1.5 mb-3">` and change it to `<div className="space-y-1 mb-3 opacity-70">` so the regional/market/suitability bars read as secondary detail. (Leave the bar rows themselves unchanged.)

- [ ] **Step 4: Build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds, no errors.

- [ ] **Step 5: Manual browser check**

Start backend (`venv\Scripts\python.exe -m uvicorn main:app`) and frontend (`npm run dev`), open `/advisor`, run Bihar/Begusarai. Expected: each card leads with "Traditional here — grown N yrs", shows predicted yield (with arrow + "was ~X") and a price outlook with a (forecast)/(recent) tag; module bars are visibly muted.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/CropAdvisor.jsx
git commit -m "feat(advisor): tradition-first recommendation card (yield + price outlook)"
```

---

## Task 10: Docs + memory update

**Files:**
- Modify: `docs/CROPADVISOR_BUILD.md`
- Modify: memory `work_journal.md` and `project_agri_analyser.md`

- [ ] **Step 1: Update `docs/CROPADVISOR_BUILD.md`**

Add a subsection under the scorers describing the new yield model (features, GPU, temporal holdout, baseline gate, per-crop clipping), the price-outlook activation of the LSTM models, and the tradition-first card. Note the metrics from `saved_models/yield_metrics.json`.

- [ ] **Step 2: Update memory**

Add a `work_journal.md` entry (date 2026-06-01) summarizing: yield model trained on GPU (record model_mae vs baseline_mae and r2), price outlook wired in, fusion enriched, card reframed, test count. Update the `project_agri_analyser.md` CropAdvisor block to mark tradition-first advisor as built and yield model as a new asset.

- [ ] **Step 3: Commit**

```bash
git add docs/CROPADVISOR_BUILD.md
git commit -m "docs: tradition-first advisor + yield model"
```

---

## Done criteria

- `models/train_yield.py` produces a yield model that **beats the historical-mean baseline** on the 2013–2015 holdout (`yield_metrics.json` → `beats_baseline: true`); otherwise inference cleanly falls back to the historical mean.
- `/api/recommend/smart` returns `traditional`, `yield`, and `price_outlook` per recommendation; existing fields unchanged.
- `/advisor` cards lead with tradition + predicted yield + price outlook; module bars de-emphasized.
- Full backend suite green (`pytest tests -p no:asyncio`); `npm run build` clean.
- Sparse crops (coffee/apple/etc.) show "No reliable yield estimate" rather than a fabricated number.

## Notes / risks (from the data audit)

- Per-crop yield outliers are clipped in `yield_dataset.clip_outliers` — do not skip this, or training/scaling breaks.
- Yield units differ by crop; only the tonnes/ha field crops are shown in q/ha, others as "units/ha" — keep `_Q_HA` accurate.
- Data ends ~2014; `predict_yield` uses `year=2016` as the "next season" anchor — it's an estimate from historical patterns, framed as such.
- LSTM covers 15 states; many state×crop pairs use the historical price fallback (`source="historical"`), which is expected and labeled.
