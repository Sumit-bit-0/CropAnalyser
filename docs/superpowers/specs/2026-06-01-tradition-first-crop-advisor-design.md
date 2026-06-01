# Tradition-First Crop Advisor — Design Spec

**Date:** 2026-06-01
**Project:** Agri Market Access Analyser (`E:\agri-market-analyser`)
**Status:** Design approved; spec under review.

---

## 1. Motivation

The current CropAdvisor ranks crops by a fusion of regional history, agronomic
suitability, and market profitability. Even after the 2026-06-01 accuracy fix
(36-crop vocabulary, regional-led Simple Mode, yield-weighted market), the
**advice still reads as profit/market-centric** and does not reflect how farmers
actually decide: by the **traditional, generational cropping pattern** of their
district and state.

The ranking itself is now acceptable (regional/tradition already leads Simple
Mode at 0.60). The gap is in **what the advice expresses**: it shows an abstract
0–1 "match" score and a market bar, but nothing about a crop's traditional
standing in the district, nothing about its expected yield, and it ignores the
1,985 LSTM price-forecast models we already trained.

**This task reframes each recommendation around tradition + our own model
predictions**, and de-emphasizes the profit/market framing.

## 2. Goals / Non-goals

**Goals**
- Center each recommendation on its **traditional standing** in the district
  ("grown 18 of 18 years on record").
- Show **our model's predicted yield** for that crop in that district, alongside
  the district's historical/traditional yield.
- Show a **price outlook** (representative price + trend ↗/→/↘) from our existing
  LSTM forecast models.
- Visually demote the market/profit bar (keep it, small).

**Non-goals (this task)**
- Re-architecting the fusion ranking (it's already tradition-led).
- Historical weather features in the yield model → **Phase 2** (NASA POWER).
- NDVI / remote sensing → Phase 3.
- Net-profit-per-hectare (cost data) → separate roadmap item.

## 3. Components

### A. Yield-prediction model (new, GPU-trained)

**Data:** `district_crop_history` (≈242K rows, 1997–2015, 33 states, ~600
districts, all crops; columns: state, district, crop_year, season, crop,
canonical_crop, area, production, crop_yield). Already loaded in Postgres.

**Target:** `crop_yield` (= production / area), in each crop's **native units**
(tonnes/ha for cereals & pulses, bales/ha for cotton & jute, nuts/ha for
coconut). Yield is **never compared across crops**; it is always displayed
per-crop with a unit label. v1 display focuses on field crops (cereals, pulses,
oilseeds, sugarcane, potato) where units are tonnes→quintals; fibre/plantation
crops show yield with a "(units vary)" caveat or omit the projection.

**Features (v1, no weather):**
- Categorical (embeddings): `state`, `district`, `season`, `canonical_crop`.
- Numeric: `crop_year` (centered/scaled) — lets the model learn the yield trend.

**Model:** a single multi-crop **PyTorch MLP with categorical embedding layers**
(one embedding table per categorical field) concatenated with the scaled year,
through 2–3 dense layers → scalar predicted yield. One model for all crops;
shared embeddings let sparse districts borrow strength from similar
districts/state. Trained on **CUDA (RTX 3060)** per the project GPU rule.
Standardize the target per-crop (z-score within `canonical_crop`) so the loss
isn't dominated by high-magnitude crops (sugarcane), and invert at inference.

**Data quality — required preprocessing (from the 2026-06-01 data audit):**
- **Per-crop outlier clipping (winsorization).** The raw yields contain
  unit/entry errors (e.g. maize yield max 1,494 vs median 1.8; sugarcane 88,000
  vs 53). Before scaling/training, clip `crop_yield` to the per-crop
  [1st, 99th] percentile. Without this, MSE and the per-crop scaler are wrecked
  by a few extreme rows. This is the single most important data fix.
- **Minimum-data threshold per crop.** Crops with too little history are
  excluded from the model (and from yield display): drop crops with
  `< ~500 rows` or `< ~5 years` — this removes coffee (6 rows), apple (4),
  watermelon (85), pomegranate (66), grapes (129) and similar. They almost never
  have local regional history anyway, so they're already floored in ranking.

**Training:**
- Loss: MSE on standardized yield (computed AFTER clipping). Adam, early stopping
  on val loss.
- Split: **temporal holdout** — train on `crop_year ≤ 2012` (≈156K rows),
  validate/test on `2013–2015` (≈18K rows; note 2015 is sparse — data effectively
  ends ~2014). More honest for a forecast than a random split. Keep a small random
  val slice of the train years for early stopping.
- Drop rows with non-positive area/production (loader already does).

**Evaluation:** report **MAE, RMSE, R²** overall and for the major field crops
(rice, wheat, maize, sugarcane, potato, mustard, the pulses). Compare against a
**baseline** = "predict the district×crop×season historical mean" — the model
must beat that baseline to justify itself. Metrics written to a small report.

**Artifacts:** model `.pt` + the embedding vocab maps + target scalers, saved to
`saved_models/` (gitignored), loaded by the inference module. Trainer is a
resumable script run as a module from `backend/`.

**Inference module** `analysis/yield_predict.py`:
```
predict_yield(state, district, season, crop, year) ->
    {"predicted_yield": float | None, "traditional_yield": float | None,
     "trend": "rising" | "flat" | "falling" | None, "unit": str,
     "level": "district" | "state" | "none"}
```
- District→state fallback when the district/combo is unseen.
- `traditional_yield` = district median historical yield (real data).
- `trend` = sign of (predicted − traditional) beyond a small deadband.
- **Sparse-crop guard:** for crops below the minimum-data threshold (coffee,
  apple, etc.), return `predicted_yield=None` / `level="none"` so the card shows
  "no reliable yield estimate" instead of a fabricated number.

### B. Price outlook (activate the LSTM models)

**Module** `analysis/price_outlook.py`:
```
price_outlook(state, crop) ->
    {"price": float, "trend": "rising"|"flat"|"falling", "horizon_months": int,
     "source": "forecast" | "historical"}
```
- Map `crop` → its primary market commodity via `CANONICAL_CROPS[crop]["market"]`.
- Try `models.predictor.predict(state, commodity)` (existing 6-month LSTM
  forecast). `price` = near-term forecast value; `trend` = sign of (forecast end
  − current) beyond a deadband; `source="forecast"`.
- **Fallback** when no trained model for that state×commodity: use the most
  recent historical modal price, `trend` from the last 2–3 years' slope,
  `source="historical"` (no over-claiming).
- Computed only for the **displayed top-k** crops (LSTM calls are expensive) —
  fusion calls this after ranking, not across all candidates.

### C. Fusion enrichment + frontend reframe

**`fusion.recommend()`** — after ranking, enrich each of the top-k recommendations
with backward-compatible fields (existing fields unchanged):
```
"traditional":  {"years_grown": int, "level": "district"|"state"|"none"}
"yield":        {predicted_yield, traditional_yield, trend, unit}   # from A
"price_outlook":{price, trend, source}                              # from B
```
`traditional` is derived from the regional module's existing output (years_grown,
level). Enrichment runs only for the returned top-k.

**Frontend `/advisor` card** (`CropAdvisor.jsx`) reframed, leading with tradition:
```
┌─────────────────────────────────────────────┐
│ ① Rice          ✓ Traditional here (18 yrs)  │
│   Our predicted yield: ~38 q/ha  ↗ (was ~36) │
│   Price outlook: ₹2,200/q  ↗ rising          │
│   ▂ Regional ███  Market ▂  (small bars)     │
│   ✓ proven locally   ⚠ high price volatility │
└─────────────────────────────────────────────┘
```
- Tradition badge + years prominent.
- Predicted yield (vs traditional) with trend arrow.
- Price outlook with trend arrow + a subtle "forecast/historical" marker.
- Module bars shrunk and de-emphasized (kept for transparency).
- `source="historical"` price shows no over-confident arrow styling.

## 4. Testing

- **Yield model:** unit tests for the data pipeline (feature encoding, temporal
  split, per-crop target scaling, district→state fallback); a training smoke
  test on a tiny subset; an evaluation test asserting the model **beats the
  historical-mean baseline** on the holdout (guards against a useless model).
- **Price outlook:** forecast path (mock/real predict) and the historical
  fallback path; commodity-alias mapping; trend deadband.
- **Fusion enrichment:** top-k carries the new fields; fields are absent/safe
  when modules can't run; existing fusion tests still pass.
- **Frontend:** card renders tradition/yield/price; graceful when fields missing.
- Full suite stays green (currently 100) with `pytest tests -p no:asyncio`.

## 4a. Dataset sufficiency (2026-06-01 audit)

Verified against the live DB; full output via `python -m tools.data_audit`.
- **Enough data:** 174K mapped rows; the ~24 advised field crops have 3K–15K rows
  each over 300–620 districts and 18–19 years. 156K train / 18K holdout.
- **Outliers** (maize 1,494 vs 1.8 median; sugarcane 88,000 vs 53) → per-crop
  winsorization (§3A).
- **Sparse crops** (coffee 6, apple 4, watermelon 85, pomegranate 66, grapes 129)
  → excluded via the min-data threshold + sparse-crop guard (§3A).
- **Sparse combos** (~3,300 single-year district×crop×season) → handled by the
  embedding design; confidence exposed via fallback `level`.
- Data effectively ends ~2014 (2015 = 521 rows) → "estimate from history" framing.

## 5. Build order

1. Yield model: data pipeline (**clip outliers + min-data filter**) + temporal
   split + baseline → MLP trainer (GPU) → evaluation report (must beat baseline).
2. `analysis/yield_predict.py` inference + tests.
3. `analysis/price_outlook.py` (wrap LSTM predictor + fallback) + tests.
4. `fusion.recommend()` enrichment (backward-compatible) + tests.
5. Frontend card reframe + manual browser check.
6. Update docs (`CROPADVISOR_BUILD.md`) + memory.

## 6. Known limitations / risks

- **Yield units vary by crop** — display per-crop with labels; focus projections
  on field crops; flag fibre/plantation crops. (Same root issue noted for the
  market scorer.)
- **Data ends 2015** — "predicted next season" is relative to the last data year;
  present honestly (it's a yield *estimate from historical patterns*, not a
  live-season forecast). Phase 2 weather features will improve currency.
- **A model that can't beat the historical mean** — the baseline test gates this;
  if it can't beat the mean we ship the historical mean as `predicted_yield` and
  defer the model, rather than show a worse number.
- **LSTM coverage is 15 states** — many state×crop combos fall back to historical
  price outlook; that's expected and labeled via `source`.

## 7. Phase 2 (not now)

Add historical district weather (rainfall, temperature) as yield-model features
via **NASA POWER** keyed off `india_district_centroids.csv` (lat/lon), cached to
a `district_weather` table. Retrain the yield model with weather features and
compare metrics against the v1 model.
