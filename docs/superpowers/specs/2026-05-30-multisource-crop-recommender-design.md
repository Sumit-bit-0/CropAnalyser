# Multi-Source Crop Recommender — Design Spec

**Date:** 2026-05-30
**Status:** SCOPED — not yet built. Deferred to a dedicated build+train session (user choice).
**Supersedes (eventually):** the current 7-input soil/climate `crop_recommender` (N, P, K, temperature, humidity, pH, rainfall).

## Goal

Recommend the best crop(s) for a farmer's *specific field* by fusing five signals instead of manual soil chemistry alone:

1. **Remote sensing** — NDVI / soil moisture (vegetation & moisture from satellite)
2. **Crop history** — what has grown well in this district historically
3. **Weather** — temperature, rainfall, humidity, sunlight
4. **Irrigation** — irrigation type/availability
5. **Market data** — profitability (price × expected yield − cost)

Move from "what suits this soil" → "what is agronomically suitable, regionally proven, AND profitable for *this* location."

## Data reality (audited 2026-05-30, `E:\DataSETAgri`)

| Signal | Source we have | Notes / gap |
|--------|----------------|-------------|
| Remote sensing (NDVI), irrigation, weather, soil moisture | `Smart_Farming_Crop_Yield_2024.csv` — cols: `NDVI_index`, `irrigation_type`, `soil_moisture_%`, `soil_pH`, `temperature_C`, `rainfall_mm`, `humidity_%`, `sunlight_hours`, `crop_type`, `yield_kg_per_hectare`, lat/lon, dates, `crop_disease_status` | **Synthetic/global** (regions: "North India", "South USA"), ~83 KB, NDVI is **simulated** not real satellite. Good for a v1 prototype model only. |
| Crop history | `Crop Production data.csv` (State/District/Crop_Year/Season/Crop/Area/Production), `Crops_data.csv` (district × year × per-crop area/production/yield) | Real India, large. No NDVI/weather. |
| Market | `prices` + `mandi_prices` tables (already loaded, 737k rows) | Real. 5 mandi commodities; `prices` broader. |
| Weather (live) | open-meteo API (free, GPS-keyed) | The local `open-meteo-*.csv` are **Berlin** samples — useless as-is. |
| Real remote sensing (live) | NONE locally | Needs Google Earth Engine / Sentinel Hub integration (auth, keys) — heavy. |

**Core constraint:** these datasets share **no common key**. There is no single joined table with all five signals for one place+time. So a single end-to-end fused model has **no integrated training data**. The architecture must work around this.

## Recommended architecture — modular decision fusion

Rather than one (untrainable) fused model, combine independent, individually-testable scorers — fits the existing `analysis/` module pattern:

1. **Agronomic suitability scorer** (ML, GPU) — trained on `Smart_Farming_Crop_Yield_2024.csv`.
   Inputs: NDVI, soil_moisture, soil_pH, temperature, rainfall, humidity, sunlight, irrigation_type.
   Output: predicted yield per crop (regression) → rank, OR crop-suitability classification.
   *This is where remote sensing + irrigation + weather enter.* (v1 = synthetic-data prototype.)
2. **Historical regional fit** (lookup/stat, no model) — from `Crop Production data.csv`: for the farmer's district, which crops have strong historical area/yield → a data-driven prior.
3. **Market profitability** (reuse) — from `prices`/`mandi_prices` + existing `profit_planner`: latest price × expected yield − costs → expected revenue per crop.
4. **Fusion layer** — weighted combination of (suitability × historical fit × profitability) → ranked recommendations **with explanation** ("strong NDVI + grows well in your district + high current mandi price").

### Inference-time inputs
- **GPS** (already have browser geolocation + `geo.py` district centroids) → district → historical fit + weather lookup.
- **NDVI / remote sensing:** v1 = user-entered or dataset default; v3 = live satellite by GPS+date.
- **Weather:** v1 = manual/default; v2 = open-meteo API by GPS.
- **Irrigation:** user selects type.

## Phasing

- **Phase 1 (v1 — data on hand):** suitability model on Smart_Farming + historical-fit lookup + market re-ranking + fusion + explanation. NDVI/weather entered manually or defaulted. New `/recommend` mode or a new page; keep old 7-input model available.
- **Phase 2 (live weather):** open-meteo API integration (free, easy) — auto-fill weather from GPS.
- **Phase 3 (real remote sensing):** Google Earth Engine / Sentinel Hub NDVI by GPS+date — heaviest; needs auth/keys/quota review.

## Open questions (resolve at build time)

1. Real India remote-sensing source & licensing (GEE auth, quotas, offline vs live).
2. Suitability model: predict **yield (regression)** or **suitability class (classification)**? Regression lets us feed yield into profitability — leaning regression.
3. Fusion weights — fixed heuristic v1, learnable later?
4. **Crop-name alignment** across datasets: Smart_Farming `crop_type` vs market commodities vs Crop Production crops have different vocabularies/coverage. Need a canonical crop mapping/whitelist (intersection only for v1).
5. Keep vs replace the existing 7-input model (recommend: keep as "Simple mode", add this as "Smart mode").

## Constraints
- **GPU rule:** the suitability model training MUST use the NVIDIA RTX 3060 (CUDA), never CPU.
- Follow existing layering: thin router (`api/`) → `analysis/` module → `database.py`; Pydantic models; tests per module (TDD).

## Next step
A dedicated session: re-confirm open questions 1–5, then `superpowers:writing-plans` → phased implementation (Phase 1 first), with GPU training for the suitability model.
