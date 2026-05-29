# Agri Analyser MVP Upgrade — Design (4 features)

**Date:** 2026-05-29
**Project:** Agri Market Access Analyser (`E:\agri-market-analyser`)
**Source idea:** `idea.md` — MVP-6 set. **Building 4 this round; 2 deferred.**

## Scope decisions (from user)
| idea.md MVP-6 | This round? | Note |
|---|---|---|
| A. Crop Recommendation Engine | ✅ build | PyTorch MLP on GPU |
| B. Profit Planner | ✅ build | calculator + volatility risk |
| C. Mandi Comparison | ✅ build | **GPS → nearest markets**, district-centroid geolocation |
| D. Smart Forecast + confidence | ⏸ **deferred** | LSTM not trained yet; do with a future training run |
| E. Market Alerts | ⏸ **deferred** | needs user/auth system first |
| F. Farmer-friendly mobile UI | ✅ build | responsive + mobile-first Home + hamburger nav |

## Data strategy (per dataset)
- `Crop_recommendation.csv` (0.1 MB) → snapshot to `backend/data/raw/`; train-only.
- **`Agriculture_price_dataset.csv` (52 MB)** → ingest to new SQLite table **`mandi_prices`** (state, district, market, commodity, variety, grade, min/max/modal price, price_date). Powers Mandi Comparison.
- **India district centroids** → bundle `backend/data/raw/india_district_centroids.csv` (`state, district, lat, lon`). Sourced from a public dataset during implementation; **fallback = hardcoded 36 state/UT centroids** if a district file can't be obtained offline. Geocodes each market via its district.
- Profit Planner current price + volatility → existing `prices` table (unchanged).

---

## Feature 1 — Crop Recommendation Engine
PyTorch MLP (7 soil/climate features → 22 crops), trained on GPU, artifacts in `saved_models/`.
`POST /api/recommend/crop` → top-3 crops + confidence %. React page: form → confidence-bar cards.
*(Full task detail unchanged from the original 2-feature plan.)*

## Feature 2 — Profit Planner
Pure calculator: `profit`, `break_even_price`, `target_sale_price`, `recommendation`. `risk_level` from
price volatility (CV of `prices.modal_price`). `POST /api/profit/plan` + `GET /api/profit/price-reference`.
React page: dropdowns + cost inputs → green/red profit card + risk badge.
*(Full task detail unchanged from the original 2-feature plan.)*

---

## Feature 3 — Mandi Comparison (GPS-based)

### Data ingestion — `backend/data/load_mandi.py` (CLI, like `ingest.py`)
- Read `E:\DataSETAgri\Agriculture_price_dataset.csv` (cols `STATE, District Name, Market Name, Commodity, Variety, Grade, Min_Price, Max_Price, Modal_Price, Price Date`).
- Clean: strip/normalize state+district+market+commodity; parse `Price Date` (`M/D/YYYY`); coerce prices to numeric; drop rows with null/zero modal price; keep most recent **per (market, commodity)** for the "current price" view (also keep history for later).
- Create table `mandi_prices(id, state, district, market, commodity, variety, grade, min_price, max_price, modal_price, price_date)` + index on `(commodity)` and `(state, district)`.

### Geolocation — `backend/analysis/geo.py`
- Load `india_district_centroids.csv` into a `{(state, district): (lat, lon)}` map (lowercased keys). Fallback to state centroid if district missing; `None` if neither.
- `haversine(lat1, lon1, lat2, lon2) -> km`.

### Comparison logic — `backend/analysis/mandi_compare.py`
- `compare_markets(commodity, lat, lon, rate_per_km=0.0, top_k=10) -> list[dict]`:
  - Query latest `modal_price` per market for the commodity from `mandi_prices`.
  - Attach (lat, lon) via geo map; compute `distance_km` (round 1 dp); skip markets with no location.
  - `transport_per_q = round(distance_km * rate_per_km, 2)` (₹/quintal; rate is ₹ per km per quintal, default 0 → pure price compare).
  - `net_price = round(modal_price - transport_per_q, 2)`.
  - Sort by **distance ascending** (nearest first); return top_k with `{market, district, state, modal_price, distance_km, transport_per_q, net_price, variety}`.
  - Also flag `is_best_net` on the row with the max `net_price` among returned.

### API — `backend/api/mandi.py`
- `GET /api/mandi/commodities` → distinct commodities in `mandi_prices` (for the dropdown).
- `GET /api/mandi/compare?commodity=&lat=&lon=&rate_per_km=&top=` → list above. If `lat/lon` omitted → return markets sorted by price (no distance). 422 on bad params via FastAPI.

### Frontend — `frontend/src/pages/MandiCompare.jsx`
- "📍 Use my location" button → `navigator.geolocation.getCurrentPosition` → lat/lon (graceful message if denied).
- Commodity dropdown (`/api/mandi/commodities`); optional ₹/km rate input.
- Results table: market (district, state), modal price, distance, transport/q, **net price** — best net row highlighted green. Plain-language headline: *"Best net price near you: **Lasalgaon** — ₹1,180/q after ~12 km transport."*

---

## Feature 4 — Farmer-friendly mobile UI

### Responsive nav — `frontend/src/components/NavBar.jsx`
- On `< md`: collapse links into a hamburger toggle (useState open/close); full row on desktop. Larger tap targets.

### Mobile-first Home — `frontend/src/pages/Home.jsx` (new `/` route)
- Quick **summary cards** linking to each tool (Crop Advisor, Profit Planner, Mandi Compare, State Map, etc.), big icons/buttons, short text. The current StateMap moves to `/map`.
- Tailwind responsive grid (1 col on mobile, multi-col desktop).

### Routing changes — `frontend/src/App.jsx`
- `/` → `Home`; `/map` → `StateMap`; existing tool routes unchanged; add `/mandi`.
- NavBar links updated to include Home, Map, Crop Advisor, Profit Planner, Mandi, plus existing Trend/Revenue/Forecast.

### Responsiveness pass
- Ensure each page container uses fluid widths (`max-w-*` + `w-full`), forms stack on mobile (`grid-cols-2 md:grid-cols-4`), tables scroll horizontally (`overflow-x-auto`).

---

## Cross-cutting
- **CORS:** add `"POST"` to `main.py` `allow_methods`.
- Register routers: `recommend`, `profit`, `mandi`.

## Testing (TDD — never break the 29 existing tests)
- Crop rec + Profit planner tests (as before).
- **Mandi:** `test_geo.py` (haversine known distance, centroid lookup), `test_mandi_compare.py` (sort order, net price math, no-location skip, best-net flag — using a small seeded `mandi_prices` fixture), `test_api.py` (`/api/mandi/commodities`, `/api/mandi/compare`).
- Frontend: `npm run build` green after each page.

## Phasing (build order; commit per phase)
1. **Phase 1 — Decision tools backend:** Crop Rec (model/train/inference/API) + Profit Planner (calc/price-ref/API). CORS.
2. **Phase 2 — Decision tools frontend:** client methods + CropRecommender + ProfitPlanner pages + wiring.
3. **Phase 3 — Mandi Comparison:** ingest `mandi_prices` + district centroids + geo + compare + API + page.
4. **Phase 4 — Mobile UI:** responsive NavBar + Home summary + routing + responsiveness pass.

## Deferred to roadmap
Smart Forecast confidence (after LSTM training), Market Alerts (after auth), Chatbot, What-If, standalone Risk Score, i18n, PDF export, opportunity map, cooperative mode.

## Definition of done
All backend tests pass; `npm run build` green; all four features reachable from the (responsive) NavBar and functional against the running backend; Mandi Comparison returns ranked nearest markets from a real GPS coordinate.
