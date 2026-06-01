# Weather Fit Module (CropAdvisor Phase 2) — Design

**Date:** 2026-06-01
**Status:** Approved (design); ready for implementation plan
**Project:** Agri Market Access Analyser (`E:\agri-market-analyser`)

## Goal

Add a **live weather term** to the CropAdvisor fusion ranking: a new "Weather Fit"
scorer that fetches a location's seasonal climate from Open-Meteo and scores each
candidate crop by how well that climate matches the crop's known climatic envelope.
It runs in **both Simple and Smart Mode** (it is location-derived and needs no soil
entry), giving Simple Mode its first agronomic signal.

This is the Phase 2 promised after the tradition-first advisor merge. NDVI remains
Phase 3. A separate, larger "unify all analysers into one chooser-driven window"
idea was explicitly deferred to its own future brainstorm (logged in the backlog).

## Why

CropAdvisor v1 defaulted weather and only used soil/climate through the manually
typed 7-input suitability model (Smart Mode). Crop choice is fundamentally seasonal
and climate-driven, yet Simple Mode had no climate awareness at all. A live,
location-true seasonal-climate term makes recommendations respond to *where and
when* the farmer actually is, without asking them to type anything.

## Architecture

One new fusion module plus a thin weather client, wired into `fusion.recommend()`
as a 4th scorer using the **same per-crop graceful-degradation** the suitability
term already uses.

```
recommend(state, district, season, …)
        ├─ regional_fit_scores      (existing)
        ├─ market_profitability     (existing)
        ├─ suitability_scores       (existing, Smart Mode only)
        └─ weather_fit_scores  ◀── NEW (both modes)
                │ get_centroid(state, district) → (lat, lon)        [analysis/geo.py, existing]
                │ seasonal_climate(lat, lon, season) → {temp, humidity, annual_rain}  [Open-Meteo archive]
                │ crop_envelopes() → per-crop mean/std from Crop_recommendation.csv
                └ Gaussian z-distance → 0–1, max-normalized
```

### Component 1 — `backend/analysis/weather_client.py`

`seasonal_climate(lat, lon, season) -> {"temp": float, "humidity": float, "annual_rain": float}`

- **Season → months mapping** (India agronomic seasons):
  - `Kharif` → Jun–Oct (6–10)
  - `Rabi` → Nov–Mar (11,12,1,2,3)
  - `Summer` / `Zaid` → Mar–Jun (3–6)
  - `Winter` → Dec–Feb (12,1,2)
  - `Autumn` → Sep–Nov (9–11)
  - `Whole Year` / `Any` / `None` → all 12 months
- Calls Open-Meteo **Archive API** (ERA5; free, no API key):
  `https://archive-api.open-meteo.com/v1/archive` with `daily=temperature_2m_mean,relative_humidity_2m_mean,precipitation_sum`
  over the **last ~5 complete years**.
- **temp / humidity**: mean of daily means restricted to the season's months.
- **annual_rain**: total `precipitation_sum` per calendar year, averaged across the
  years (annual total — to match the CSV's annual rainfall semantics; see Honesty note).
- **Caching:** `functools.lru_cache` keyed on `(round(lat,1), round(lon,1), season)`
  (coords rounded to ~0.1° ≈ 11 km, plenty for district-level climatology and good
  cache reuse). HTTP via stdlib `urllib.request` — **no new dependency**.
- **Timeout** ~4s, single retry. On any HTTP / JSON / empty-data failure → **raise**
  (caller decides to skip). Never returns partial/fabricated data.

### Component 2 — `backend/analysis/weather_fit.py`

`weather_fit_scores(state, district, season, crops=None) -> {crop: {...}}`

- `crop_envelopes()` (module-level cache): reads `Crop_recommendation.csv`, groups by
  `label`, computes per-crop `{temp:(mean,std), humidity:(mean,std), rain:(mean,std)}`
  for the **22 suitability crops** mapped through `CANONICAL_CROPS[c]["suitability"]`.
  `std` floored to a small epsilon to avoid divide-by-zero.
- Resolve coords with `analysis.geo.get_centroid(state, district)`. If `None` →
  return `{}` (module skipped).
- Fetch `seasonal_climate(...)`. On exception → return `{}` (graceful skip; log once).
- For each candidate crop **that has an envelope**:
  - `z_dim = (loc_value − mean) / std` for temp, humidity, annual_rain
  - `raw = exp(-0.5 * mean(z_dim²))`  → smooth 0–1 similarity
- **Max-normalize** so the best-fitting candidate = 1.0 (consistent with
  `regional_fit` / `suitability`).
- Return `{crop: {"score": 0–1, "fit": "good|fair|poor", "detail": {temp,humidity,rain z's or deltas}}}`.
- Crops with **no envelope** (the 14 expansion crops, `suitability: None`) are
  **omitted** → fusion degrades them to regional+market(+suitability) per-crop.

### Component 3 — `backend/analysis/fusion.py` integration

- Add `"weather": weather_fit_scores(state, district, season, crops)` to `modules`
  (attempt in **both** modes). If it returns `{}` the module is effectively absent
  and the existing weight renormalization handles it.
- **Weights** (sum to 1.0):
  - `DEFAULT_WEIGHTS` (Smart): `{"suitability": 0.30, "regional": 0.25, "market": 0.30, "weather": 0.15}`
  - `SIMPLE_MODE_WEIGHTS`: `{"regional": 0.50, "market": 0.30, "weather": 0.20}`
- Per-crop weight renormalization (already in `recommend()`) covers crops missing
  the weather term, and a wholly-unavailable weather module (API down / no coords).
- `_why` / `_cautions` clauses: weather score ≥ ~0.6 → "climate well-suited this
  season"; ≤ ~0.3 → "seasonal climate is marginal for this crop".

### Component 4 — Frontend `frontend/src/pages/CropAdvisor.jsx`

- Add `['weather', 'Weather', 'bg-cyan-500']` to the `MODULES` array (emerald=
  suitability, sky=regional, amber=market are taken; cyan is distinct) — the bar
  renders automatically from `r.breakdown.weather`. The `why`/`cautions` lines
  already render from the API. No structural card change.

## Data flow

1. Request → `recommend()` runs regional, market, (suitability if soil), and weather.
2. Weather: `state/district/season` → `get_centroid` → `(lat,lon)` → Open-Meteo
   seasonal climatology → per-crop Gaussian match → max-normalized scores.
3. Fusion blends per-crop with mode weights; top-k enriched (tradition/yield/price)
   as today.

## Honesty / correctness notes

- `Crop_recommendation.csv` `rainfall` reads as an **annual total (mm)**, so the
  location's rainfall feature is computed as an **annual** total; temperature and
  humidity use **season-month averages**. This keeps each dimension comparable
  rather than mixing seasonal vs annual.
- The weather term and the suitability term overlap in crop coverage (both the 22
  CSV crops) but use different inputs: suitability = full 7-input MLP on
  **user-typed** climate+soil; weather = **live, location-true** climate only. In
  Smart Mode both run; the geometric-mean fusion tolerates the mild correlation, and
  weather adds the location-truth the typed values may lack.
- Open-Meteo archive lags ~5 days; multi-year season averaging makes that irrelevant.

## Edge cases

| Situation | Behavior |
|---|---|
| Season = "Any"/None | Annual climatology (all 12 months) |
| `get_centroid` returns None | Weather module skipped (`{}`) |
| Open-Meteo timeout / error / empty | Weather module skipped, logged once; advisor still returns |
| Crop has no climate envelope (14 expansion crops) | Omitted from weather scores → per-crop degrade |
| Whole weather module unavailable | Weights renormalize over remaining modules |

## Testing

- **`weather_client`**: monkeypatched HTTP — season→months mapping; correct
  averaging of mocked daily data; failure/empty raises.
- **`crop_envelopes`**: built from CSV, 22 crops present, sane mean ranges
  (e.g. rice temp ~20–27°C, high rainfall).
- **`weather_fit`**: with mocked `seasonal_climate` — a crop near its envelope center
  scores high, far away scores low; no-envelope crops omitted; coords-None → `{}`;
  client exception → `{}`.
- **`fusion`**: weather integrated additively; weights renormalize; per-crop
  degradation for None-suitability crops; **existing 113 tests stay green**.

## Out of scope (deferred)

- NDVI / satellite vegetation index (Phase 3).
- Near-term operational forecast advisories.
- Unifying all analyser pages into one chooser-driven window (separate future
  brainstorm — logged in ideas backlog).
- B-v3 net-profit-per-hectare market score (needs CACP cost-of-cultivation data).

## Dependencies & config

- No new Python dependency (stdlib `urllib`).
- Possible `config.py` additions: `OPEN_METEO_ARCHIVE_URL`, `WEATHER_YEARS_BACK=5`,
  `WEATHER_TIMEOUT=4`. Confirm `Crop_recommendation.csv` path during planning
  (`config.DATA_RAW / "Crop_recommendation.csv"`, with `E:\DataSETAgri` fallback as
  used by `crop_catalog.validate()`).
