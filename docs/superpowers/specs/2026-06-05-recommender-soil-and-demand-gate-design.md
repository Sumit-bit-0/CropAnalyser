# Recommender Phase 1 — Location-Derived Soil + Processing-Demand Gate

- **Date:** 2026-06-05
- **Status:** Approved (design) — pending spec review → implementation plan
- **Scope:** Phase 1 of a two-phase effort. Phase 2 (full industry tracking +
  grow-for-industry vs grow-for-mandi profit comparison) is a **separate spec**
  and explicitly out of scope here.

## Problem

For Bihar (and structurally for every state) the CropAdvisor over-recommends
**sugarcane** almost regardless of inputs. Three causes stack:

1. **Soil/climate is never used unless typed in by hand.** The `/recommend/smart`
   endpoint only adds the suitability module when a `soil` block is posted
   (Smart Mode). In Simple Mode the weights are regional 0.50 / market 0.30 /
   weather 0.20 — no agronomic term at all. There is **no pincode→soil lookup**.
2. **Regional history dominates and the bundled production data ends ~2015.** The
   10-year recency window (`RECENT_YEARS=10`, → 2006–2015) still sees sugarcane
   as "proven" because the post-2015 mill closures are not in the data.
3. **Sugarcane is a processing crop.** It must be crushed within ~24–48h, so it
   is only viable **near a working sugar mill** — not shippable to a distant
   mandi. The model has no notion of processing demand. This is the deepest
   cause, and fixing it is also the seed of the Phase 2 feature.

## Goals

- Recommendations consider **soil + climate derived automatically from the
  farmer's location** (pincode or GPS), for **all states**, with no manual entry.
- A crop that requires local processing (Phase 1: **sugarcane**) ranks high
  **only when a processing facility is nearby**, and decays with distance.
- Stale regional history alone can no longer crown a crop.
- The farmer can **optionally** supply their own soil-test numbers to override.
- Mechanisms are built generically so Phase 2 industries reuse them.

## Non-goals (Phase 1)

- No industries dataset beyond a curated **sugar-mill** list.
- No profit comparison (grow-for-industry vs grow-for-mandi) — that is Phase 2.
- No demand-gating of crops other than sugarcane (mechanism is generic; the
  gated-crop set stays {sugarcane} for now).
- No retraining of the suitability or yield models.

## Architecture

Five changes, four backend + one frontend.

### 1. `soil_profile` service — `backend/analysis/soil_profile.py` (new)

Builds the full 7-feature vector the suitability model expects
(`N, P, K, temperature, humidity, ph, rainfall`) from a location alone.

```
soil_profile(state, district, *, coords=None, season=None) -> dict
  returns {
    "features": {N, P, K, temperature, humidity, ph, rainfall},
    "soil_source": "district" | "state" | "national",
    "climate_source": "weather_api" | "none",
  }
```

- **N, P, K, pH** ← district soil-nutrient dataset (see Data Sources). Resolve the
  district key from `state`+`district` (the same names `resolve_pincode` returns).
  Fallback chain: **district → state-average → national-average**; record which
  tier was used in `soil_source` so the UI can be honest about precision.
- **temperature, humidity, rainfall** ← reuse the climate the existing
  `analysis/weather_fit` path already pulls by `coords` (climate normals for the
  season). If coords/API unavailable, fall back to the district/state climate
  baked into the soil table; set `climate_source` accordingly.
- District nutrient lookups are cached in a module dict (same pattern as
  `pincode._load_pincodes`).

### 2. Processing-demand gate — `backend/analysis/demand_gate.py` (new)

```
GATED_CROPS = {"sugarcane": "sugar_mill"}        # crop -> facility type
proximity_factor(km: float|None) -> float        # 1.0 ≤50, taper 50–150, ~0.2 floor >150, None→0.2
nearest_facility(facility_type, lat, lon) -> {name, km} | None
```

- Curated facility table `data/raw/processing_units.csv`
  (`facility_type, name, state, district, lat, lon`); Phase 1 rows = operational
  **sugar mills** in the major states. Distance via `analysis.geo.haversine`.
- The gate is applied **after fusion scoring**: for a gated crop, multiply the
  final score by `proximity_factor(nearest_facility_km)`. When the factor is low,
  add a caution: *"No sugar mill within {km} km — hard to sell a processing crop."*
- Requires coords; if the request has none, the gate is a no-op (never blocks).

### 3. Fusion changes — `backend/analysis/fusion.py`

- `recommend()` accepts the (now usually present) auto-derived `features` and a
  `coords` tuple (already does). When `features` is present the suitability
  module runs and `DEFAULT_WEIGHTS` (soil 0.30 / regional 0.25 / market 0.30 /
  weather 0.15) apply — regional drops from 0.50→0.25.
- Apply the **demand gate** to each scored crop before ranking (step 2 above),
  and surface the caution through the existing `cautions` list.
- **Recency decay** in `regional_fit`: weight recent years more than 2006-era
  ones within the window (e.g. linear ramp across the `RECENT_YEARS` span) so the
  newer pattern wins even inside the bundled data. Keep `RECENT_YEARS=10`.

### 4. API changes — `backend/api/recommend.py`

- `/recommend/smart`: when `body.soil` is **absent**, auto-derive features via
  `soil_profile(state, district, coords=...)` and pass them to `fusion_recommend`
  along with the chosen-tier metadata. When `body.soil` is **present**, it
  overrides (the optional side panel).
- The response gains `soil_source` / `climate_source` so the UI can caption it,
  plus the per-crop demand caution (already inside `cautions`).
- `pincode` may be passed and resolved server-side via `analysis.pincode`, or the
  frontend keeps resolving and sends `state/district/lat/lon` (current behavior);
  either is acceptable — pick the smaller diff at plan time.

### 5. Frontend changes — `frontend/src/workspace/*`, `pages/CropAdvisor.jsx`

- **Remove the Simple/Smart toggle**: delete `ModeToggle`, the `mode` state in
  `WorkspaceContext`, the smart-mode banner/animation, and the `SMART_AFFECTS`
  logic. Recommendations always send location; soil is auto-derived server-side.
- **Optional soil panel**: repurpose `SoilPanel` into a collapsed-by-default side
  panel — *"Have a soil test? Add your own values (optional)."* When filled, its
  values are posted as `soil` and override the auto-derived profile.
- **Soil-source caption** on results, e.g. *"Soil: Gopalganj district average."*
  driven by `soil_source` (`district`/`state`/`national`).
- Retire the now-unused i18n keys (`mode.*`, `badge.smartMode`, `badge.simpleMode`,
  `ws.smart.*`); leaving them is harmless but cleaning is preferred.

## Data sources to acquire

1. **District soil nutrients (N, P, K, pH).** Soil Health Card portal
   (soilhealth.gov.in) / data.gov.in district nutrient datasets. Cleaned to one
   row per (state, district) with the four values; gaps handled by the
   state→national fallback. Researched-and-verified, same as the crop-name work.
2. **Sugar-mill locations.** ISMA directory / data.gov.in operational-sugar-mills
   list → `processing_units.csv`. Curated; only needs the major sugar states for
   Phase 1.

Both are uncommitted data dependencies; if a clean district soil set is only
partially available, the **state-average fallback keeps every location working**.

## Data flow (a recommendation)

```
pincode/GPS ─ resolve_pincode/nearest_pincode ─▶ state, district, lat, lon
                                                   │
            soil_profile(state,district,coords) ◀──┤
              ├─ district soil table → N,P,K,pH (+ fallback tier)
              └─ weather API (coords) → temp,humidity,rainfall
                                                   │
   features ─▶ fusion.recommend(features, coords)  │
              ├─ suitability + regional(+decay) + market + weather
              ├─ weighted geometric mean  → score
              └─ demand_gate: score *= proximity_factor(nearest sugar mill)
                                                   ▼
                       ranked recs + cautions + soil_source/climate_source
```

## Error handling / fallbacks

- District soil missing → state avg → national avg (`soil_source` reflects it).
- Weather API down / no coords → climate baseline from the soil table
  (`climate_source="none"`); suitability still runs.
- No coords at all → demand gate is a no-op; recommendation still returns.
- Manual `soil` override always wins when present.
- Any dataset file missing → 503 with a clear message (existing pattern), never a
  silent wrong answer.

## Testing

- `soil_profile`: returns 7 features for a known district; fallback tiers fire
  correctly (district present, district-missing→state, state-missing→national);
  manual override path.
- `demand_gate`: `proximity_factor` boundary values (0/50/150/∞/None);
  `nearest_facility` picks the closest mill; sugarcane near a mill keeps its
  score, far from one is penalized + carries the caution.
- `fusion`: with auto soil present, weights = DEFAULT_WEIGHTS; regional recency
  decay reduces an old-but-not-recent crop's regional score; **Bihar regression
  test** — a non-mill Bihar district no longer ranks sugarcane #1, a mill-district
  (e.g. Gopalganj) still can.
- API: `/recommend/smart` with no `soil` auto-derives and returns `soil_source`;
  with `soil` it overrides.
- Keep the existing suite green (181 tests).

## Rollout

1. Source + commit the two datasets (soil nutrients, sugar mills).
2. `soil_profile` + tests.
3. `demand_gate` + tests.
4. Fusion wiring (auto soil, gate, recency decay) + API change + tests.
5. Frontend: drop toggle, optional soil panel, soil-source caption.
6. Live smoke (Arc) on Bihar non-mill vs mill district.

## Risks / open questions

- **Soil dataset coverage/quality** is the main risk; mitigated by the
  state/national fallback (degrades precision, never blocks).
- **Mill-list freshness** — a curated list can go stale; acceptable for Phase 1
  and far better than history-only. Phase 2 formalizes the industries dataset.
- Climate "normals vs live" — for a recommendation, seasonal normals are more
  appropriate than today's weather; confirm `weather_fit` exposes normals (else
  derive a seasonal average).
- Removing `mode` touches `WorkspaceContext` consumers across pages; the plan
  must sweep all references, not just the advisor.
```
