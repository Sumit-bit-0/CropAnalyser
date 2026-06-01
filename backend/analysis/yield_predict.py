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

# crops whose crop_yield is in tonnes/ha -> display as quintals/ha (x10).
# others have inconsistent units; shown as "units/ha".
_Q_HA = {"rice", "wheat", "maize", "bajra", "jowar", "ragi", "barley", "mustard",
         "groundnut", "soyabean", "sunflower", "sesamum", "chickpea", "lentil",
         "pigeonpeas", "mungbean", "blackgram", "mothbeans"}
UNIT_LABEL = {c: "q/ha" for c in _Q_HA}
DEADBAND = 0.03  # +/-3% around traditional yield counts as "flat"


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
