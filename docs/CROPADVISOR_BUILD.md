# CropAdvisor — Build Documentation

**Project:** Agri Market Access Analyser
**Feature:** CropAdvisor multi-source crop recommendation engine
**Location:** `E:\agri-market-analyser`
**Built:** 2026-05-31 (merged to `master` @ `2a463b6`)
**Status:** Core feature shipped & verified live in browser. UX polish + GPS locate built, tested, **currently uncommitted** on `master`.

---

## 1. What we built (one paragraph)

CropAdvisor recommends the best crops for a farmer's field by **fusing three independent signals** — what the region has historically grown well, how agronomically suitable the soil/climate is, and how profitable the crop is in the market — into a single ranked list with plain-language explanations. Along the way we **migrated the project's entire database from SQLite to PostgreSQL** (28+ million rows) to make the project production-credible and deployable, and added a **GPS "Use my location"** convenience feature.

---

## 2. Tech stack & tools

### Backend
| Concern | Tool / library |
|---|---|
| Web framework | **FastAPI** (thin routers in `api/` → logic in `analysis/`) |
| Server | **uvicorn** |
| Validation | **Pydantic** |
| Database | **PostgreSQL 16** (via Docker) |
| DB driver | **psycopg 3** (`psycopg[binary]==3.3.4`) |
| ORM/engine | **SQLAlchemy 2.0.50** (core engine + `text()`, not full ORM) |
| Config | **python-dotenv** (`.env` → `DATABASE_URL`) |
| ML | **PyTorch** MLP crop classifier (GPU-trained, RTX 3060) + 1,985 LSTM price models |
| Tests | **pytest** (`pytest tests -p no:asyncio`) |

### Frontend
| Concern | Tool / library |
|---|---|
| Framework | **React 19** |
| Build / dev server | **Vite** (`:5173`, proxies `/api` → `:8000`) |
| Styling | **Tailwind CSS** |
| Routing | **react-router-dom** |
| HTTP | **axios** |
| Geolocation | Browser **Geolocation API** + reverse-locate via haversine |

### Infrastructure
| Concern | Tool |
|---|---|
| Database container | **Docker Compose** (Postgres 16, named volume `agri_pgdata`, healthcheck) |
| Bulk migration | PostgreSQL **COPY** (28M rows) |

---

## 3. The database migration (SQLite → PostgreSQL)

**Why:** the project is for a portfolio/resume and is meant to go live. SQLite isn't credible for a "real" deployable data app; Postgres is. We also wanted real indexing performance on a 28M-row price table.

**Result:** ~55× speedup on the heavy endpoints, zero query call-site changes, 28.3M rows migrated row-for-row.

**How we did it without rewriting every query:**
- `database.py` was rewritten around a SQLAlchemy engine + psycopg3.
- A `_to_named()` shim rewrites SQLite-style `?` placeholders into named bind params (`:p0, :p1, …`) at runtime, so **none of the existing `query(sql, params)` call sites had to change**.
- Bulk data moved via Postgres `COPY` (`data/migrate_to_pg.py`), then summaries were rebuilt and row counts verified.
- Added **functional indexes** on `LOWER(state)/LOWER(commodity)` for case-insensitive lookups.

**Postgres-vs-SQLite gotchas we fixed:**
- `ROUND(double precision, n)` fails → must `CAST(... AS numeric)`.
- Text `ORDER BY` collation differs → we now sort in Python (`trends.py`, `mandi_compare.py`) for stable, collation-independent ordering.
- `sqlite_master` → use `to_regclass` / SQLAlchemy inspector (`table_exists()`).
- `AUTOINCREMENT` → `BIGINT GENERATED ALWAYS AS IDENTITY`.

**Files:** `docker-compose.yml`, `.env`/`.env.example`, `backend/config.py`, `backend/database.py`, `backend/data/migrate_to_pg.py`, `backend/data/load_mandi.py`, `backend/analysis/{summaries,trends,mandi_compare}.py`, `requirements.txt`, `CLAUDE.md`.

---

## 4. CropAdvisor architecture (built tier by tier)

```
                ┌─────────────────────────────────────────────┐
  User input →  │  state, district, season, goal, [soil/climate] │
                └─────────────────────────────────────────────┘
                                   │
                          crop_catalog.py
                   (20-crop whitelist + synonym mapping)
                                   │
        ┌──────────────────┬───────────────────┬──────────────────┐
        ▼                  ▼                   ▼                  
  regional_fit.py    suitability.py    market_profitability.py
  (history)          (soil/climate ML)  (price × stability)
        │                  │                   │
        └──────────────────┴───────────────────┘
                           ▼
                       fusion.py
        weighted GEOMETRIC mean + goal multipliers
                           ▼
            ranked crops + why / cautions
                           ▼
        POST /api/recommend/smart  →  /advisor (React)
```

### Phase 0 — Crop-name alignment catalog (`analysis/crop_catalog.py`)
The three data sources speak **different crop vocabularies**. We built `CANONICAL_CROPS` (canonical name → {suitability label, production aliases[], market aliases[]}) and derived a **20-crop `WHITELIST`** = the intersection of all three vocabularies:

> apple, banana, blackgram, chickpea, coconut, coffee, cotton, grapes, jute, lentil, maize, mango, mothbeans, mungbean, orange, papaya, pigeonpeas, pomegranate, rice, watermelon

Excluded: `kidneybeans` (no market data), `muskmelon` (no production data).

### Data foundation — `district_crop_history` (`data/load_crop_history.py`)
Cleans `Crop Production data.csv` (strip whitespace, title-case state/district, drop null-production / zero-area rows), tags each row with its `canonical_crop`, computes `crop_yield`, and loads **242,361 rows**. *Data-quality find: coconut showed 0 rows due to trailing whitespace in the CSV `Crop` column — fixed with `.strip()`.*

### Scorer #1 — Regional Fit (`analysis/regional_fit.py`)
"Has this region grown this crop, consistently and at volume?"
`score = 0.5·consistency + 0.5·log-volume`, normalized so the region's top crop = 1.0. District → state fallback. Returns years grown, total production, avg yield.

### Scorer #2 — Suitability (`analysis/suitability.py`)
"Does the soil/climate suit this crop?" Reuses the PyTorch MLP via a new `predict_proba(features) → {label: prob}` added to `crop_recommender.py` (Simple Mode behaviour unchanged). Max-normalized. **Only active when the user supplies soil/climate (Smart Mode).**

### Scorer #3 — Market Profitability (`analysis/market_profitability.py`)
"Will it pay?" **v2: yield-weighted gross revenue per hectare** — `score = recent_price × typical_yield × (1 − volatility_cv)`, max-normalized, national default (optional per-state). `typical_yield` = national median of `district_crop_history.crop_yield`. Returns recent price, avg price, volatility CV, risk level, typical yield. (**v1** used absolute `recent_price·(1−CV)`, which buried cheap-but-high-yield staples — rice/maize ranked below low-yield pulses; see §12.) **Remaining limitation:** this is gross revenue, not net profit — ignores cost of cultivation. Next step is net-profit/ha, which needs a cost dataset (§12).

### Fusion (`analysis/fusion.py`) — and why we hardened it
`recommend(state, district, season, features, goal, crops, top_k, weights, method)`.

- **Default weights:** suitability 0.35, regional 0.30, market 0.35.
- **Goal multipliers** re-weight for `max_profit / low_risk / sustainable / water_efficient`.
- **Graceful degradation:** with no soil input, suitability drops out (Simple Mode).

**The hardening story:** the first version used an **additive** mean, which let an agronomically absurd crop (e.g. *coffee in Punjab*) top the ranking — a high score in one module masked a near-zero in another. We switched to a **weighted geometric mean** with a softening floor:

```
score = exp( Σ wᵢ · ln(floor + (1−floor)·scoreᵢ) )      floor = 0.05
```

A geometric mean collapses toward zero if **any** module scores low, so a crop must be decent on *all* axes to rank — coffee in Punjab can no longer win. (Additive remains available behind `method=` for comparison/testing.) Output per crop: `score`, `breakdown{}`, `why[]`, `cautions[]`, plus `modules_used`, `weights_used`, `goal`, `method`.

---

## 5. API

**`POST /api/recommend/smart`** (`api/recommend.py`)
`SmartRecommendInput`: `state` (required), optional `district`, `season`, `goal`, `top_k`, `soil` (CropInput). Returns the fused ranked recommendations.

**`GET /api/geo/locate?lat=&lon=`** (`api/geo.py` — uncommitted)
Reverse-geocodes coordinates → nearest state centroid, refined to nearest district from a bundled `india_district_centroids.csv` via haversine. Backs the "Use my location" button.

The original Simple Mode endpoint `POST /api/recommend/crop` is untouched.

---

## 6. Frontend (`frontend/src/pages/CropAdvisor.jsx` → `/advisor`)

- State dropdown (from `/api/trends/filters`), District / Season / Goal selectors.
- **Soil toggle** that flips Simple ↔ Smart Mode (reveals 7 soil/climate number inputs: N, P, K, temp, humidity, pH, rainfall).
- **📍 Use my location** button → browser geolocation → `/api/geo/locate` → auto-fills state + district.
- Results: rank badges, "Best pick" ribbon on #1, color-coded module bars (Soil/Climate = emerald, Regional = sky, Market = amber), ✓ why / ⚠ cautions lines, a Simple/Smart mode pill showing the fusion method + weights, and a dashed empty-state hint.
- Wired in `client.js` (`recommendSmart`, `locateByGps`), `App.jsx` route `/advisor`, and `NavBar.jsx` ("Crop Advisor" → `/advisor`, "Soil Match" → `/recommend`).

---

## 7. Testing

All work was test-backed; the suite stands at **93+ tests green** (run with `pytest tests -p no:asyncio`).

New/updated test files:
`test_crop_catalog.py`, `test_crop_history.py`, `test_regional_fit.py`, `test_suitability.py`, `test_market_profitability.py`, `test_fusion.py`, `test_recommend_smart.py`, `test_geo.py`, `test_summaries.py` (ROUND-cast fix).

**Notable test fixes:**
- `test_additive_method_still_available_and_differs` was using a 2-crop subset where suitability re-normalizes — fixed by testing across the full whitelist (coffee only tops under additive across the full candidate set).
- The `::` Postgres cast collides with SQLAlchemy `:bind` syntax — smoke test rewritten to use `CAST(? AS INTEGER)` (real codebase has no `::`).

---

## 8. Git history (this feature)

```
3b6de22  Add CropAdvisor planning docs (vision + data/backend note)
2a463b6  Merge: PostgreSQL migration + CropAdvisor recommendation engine
385a084  Add CropAdvisor Smart Mode frontend page
465b7e5  Add POST /api/recommend/smart fusion endpoint
208f6fb  Harden fusion ranking with weighted geometric mean
8fd8d67  Add fusion layer (CropAdvisor recommendation engine, additive v1)
f3e5982  Add Market Profitability scorer (CropAdvisor fusion input #2)
ba95e0a  Add agronomic Suitability scorer (CropAdvisor fusion input #3)
7789c66  Add Regional Fit scorer (CropAdvisor fusion input #1)
e770cd4  Add district_crop_history loader (Regional Fit data foundation)
1dc0507  Add CropAdvisor Phase 0 crop-name alignment catalog
2449adf  Migrate database from SQLite to PostgreSQL via Docker
```

---

## 9. Uncommitted work (resume here)

The UX polish + GPS locate feature is built and tested but **not yet committed** (deliberately deferred). Dirty tree on `master`:

```
 M backend/analysis/geo.py        # added locate(lat, lon)
 M backend/main.py                # include geo.router
 M backend/tests/test_geo.py      # locate() + endpoint tests
 M frontend/src/api/client.js     # locateByGps()
 M frontend/src/pages/CropAdvisor.jsx   # polished UI + 📍 button
?? backend/api/geo.py             # GET /geo/locate
```

**Before committing:** verify the 📍 "Use my location" button end-to-end in a live browser (not yet click-tested — Playwright had disconnected last round). Branch decision pending (`feat/advisor-ux` was the leaning option vs. straight-to-master).

---

## 10. Roadmap (next)

1. **Net profit per hectare** (the market-score endgame) — see §12.
2. **Phase 2** — live **Open-Meteo** weather term in the suitability/fusion path.
3. **Phase 3** — **NDVI** (satellite vegetation index) signal.
4. **Deploy live** — GitHub → Render (backend + Postgres) + Vercel (frontend).

---

## 11. Accuracy iteration (2026-06-01) — fixing the Begusarai mismatch

A test on **Bihar / Begusarai** returned pulses on top and never showed wheat/sugarcane/maize, disagreeing with common knowledge. Root-cause investigation (with the live DB) found three stacked causes and we fixed two:

**Cause A — candidate vocabulary too small.** The whitelist was 20 crops gated by the soil model's 22-crop Kaggle dataset, which has **no wheat, sugarcane, potato, mustard** — Begusarai's actual top crops. **Fix:** expanded the catalog to **36 crops**, adding 16 major Indian field crops (wheat, sugarcane, potato, mustard, onion, soyabean, groundnut, bajra, jowar, ragi, barley, sunflower, sesamum, turmeric, garlic, tapioca). These carry `suitability: None` — they're scored on regional + market only. The suitability scorer now **omits** crops with no soil label (rather than scoring them 0), and `fusion._fuse` renormalizes weights **per crop** over the modules that actually cover it, so a missing agronomic term degrades gracefully instead of penalizing. The history table was re-tagged (`load_crop_history`) — 174K rows now mapped.

**Cause C — Simple Mode let market dominate.** With suitability dropped (no soil), renormalizing default weights gave **market 54%**. **Fix:** `SIMPLE_MODE_WEIGHTS = {regional: 0.60, market: 0.40}` — proven local history leads when there's no soil input.

**Cause B — market used absolute ₹/quintal** (partially fixed → see §12). Switched to **yield-weighted gross revenue/ha** (`price × typical_yield`), which lifts high-yield staples. Begusarai Simple-Mode top now reads **sugarcane, banana, potato, rice, wheat, jute, onion, turmeric, maize** — and absurd crops (coffee/apple/grapes) fall to the bottom (no local history → geometric-floored).

Diagnostic CLI added: `python -m tools.advisor_explain "<State>" "<District>"` dumps each scorer's contribution for any district.

---

## 12. The market-score endgame — net profit per hectare

Where the market score is heading, and why it's not done:

| Version | Formula | Status |
|---|---|---|
| v1 | `recent_price × (1−CV)` | absolute price — favoured expensive crops (the bug) |
| **v2 (current)** | `recent_price × typical_yield × (1−CV)` | **gross revenue/ha** — staples restored |
| v3 (planned) | `(recent_price × yield − cost_per_ha) × (1−CV)` | **net profit/ha** — the real target |

**Why v3 needs work:** it requires a per-crop **cost-of-cultivation** dataset (seed, fertiliser, labour, irrigation, ₹/ha) — sourceable from **CACP** (Commission for Agricultural Costs & Prices) or the Directorate of Economics & Statistics, which publish A2+FL / C2 cost estimates per crop per state. Plan: ingest a `crop_costs` table (crop × state × year × cost_per_ha), join it in the market scorer, and switch the formula to net profit. **Open data caveats:** cost data is coarser (state-level, lagging) than price data, and `crop_yield` units in our history are inconsistent across crops (tonnes vs cotton/jute bales vs coconut nuts) — v2 leans on the regional gate to suppress the unit-distorted crops; v3 should normalise units per crop when the cost data is wired in.

---

## 13. Tradition-first advisor + our own prediction models (2026-06-01)

A reframe driven by user feedback: the advisor was *too* centred on profit/market cap and ignored that crop choice is, for most farmers, a generations-deep regional tradition. So each recommendation card now leads with **how traditional the crop is in that district** and **our own model's predictions**, with the module bars demoted to secondary detail.

### Asset #1 — GPU-trained yield model (`models/yield_mlp.py`, `models/train_yield.py`, `data/yield_dataset.py`)

A multi-crop yield regressor: categorical **embeddings** for state / district / season / canonical_crop + a scaled `crop_year` → predicted yield. Trained on `district_crop_history` on the **RTX 3060 (CUDA)** per the project GPU rule.

Data hygiene that makes it honest:
- **Per-crop outlier winsorization** to the [1st, 99th] percentile — fixes unit/entry errors (e.g. a maize row at 1494 vs a median of ~1.8) that would otherwise wreck scaling.
- **Sparse-crop guard** (`MIN_ROWS=500`, `MIN_YEARS=5`) drops thin crops (coffee, apple…) → those return `predicted_yield=None` instead of a fabricated number.
- **Per-crop target z-scaling** so high-magnitude crops (sugarcane) don't dominate the MSE.
- **Temporal holdout** (train ≤2012, test 2013–2015) + a **historical-mean baseline gate**: the model is only saved if it beats the baseline MAE; otherwise inference cleanly falls back to the historical mean.

**Result (`saved_models/yield_metrics.json`):** model MAE **29.25** vs baseline **36.47**, **R² 0.755**, **28 crops**, 17,666 holdout rows, `beats_baseline: true`.

Inference (`analysis/yield_predict.py`): `predict_yield(state, district, season, crop, year=2016)` → `{predicted_yield, traditional_yield, trend, unit, level}`, with district→state fallback. Tonnes/ha field crops are shown in **q/ha** (×10); other crops keep `units/ha` because their source units are inconsistent.

### Asset #2 — Price outlook (`analysis/price_outlook.py`)

`price_outlook(state, crop)` wraps the existing **LSTM price models** (`models/predictor.py`) for the crop's primary market commodity, returning a near-term price + trend with `source="forecast"`. When no model covers that state × commodity it falls back to the recent historical modal-price slope (`source="historical"`), so the UI never over-claims a forecast.

### Wiring — fusion enrichment (`analysis/fusion.py`)

`_enrich()` attaches `traditional{years_grown, level}`, `yield{…}`, and `price_outlook{…}` to each top-k recommendation. **Additive and backward-compatible** — existing `crop/score/breakdown/why/cautions` fields are untouched; enrichment runs only for the returned crops, not the whole whitelist.

### The card (`frontend/src/pages/CropAdvisor.jsx`)

Each card now leads with **"✓ Traditional here — grown N yrs on record"**, then **predicted yield** (with ↗/→/↘ trend arrow and the "was ~X" historical anchor), then a **price outlook** tagged `(forecast)` or `(recent)`. The regional/market/suitability bars are kept but muted (`opacity-70`) as supporting detail. Sparse crops show "No reliable yield estimate".

Verified live on Bihar/Begusarai: sugarcane / banana / potato / rice / wheat, all proven 10–18 yrs, each with a model yield + price outlook.

---

## 14. Phase 2 — live Weather Fit term (2026-06-01)

A 4th fusion module that makes recommendations respond to the location's actual climate, with **no extra input from the farmer** (it's location-derived, so it runs in **both Simple and Smart Mode** — Simple Mode's first agronomic signal). Spec: `docs/superpowers/specs/2026-06-01-weather-fit-module-design.md`; plan: `docs/superpowers/plans/2026-06-01-weather-fit-module.md`.

### How it works
- **`analysis/weather_client.py`** — `seasonal_climate(lat, lon, season)` pulls the location's typical climate from the **Open-Meteo Archive API** (ERA5; free, no key; stdlib `urllib`, **zero new dependencies**). Season → calendar months (Kharif Jun–Oct, Rabi Nov–Mar, etc.); temperature & humidity are averaged over the season's months across the last ~5 years. `@lru_cache` keyed on ~0.1° coords + season; ~4s timeout, one retry; raises `WeatherUnavailable` on any failure so the caller can skip cleanly.
- **`analysis/weather_fit.py`** — `weather_fit_scores(state, district, season, crops)`. Resolves coords via the existing `geo.get_centroid` (district centroid → state fallback). Builds per-crop **climate envelopes** (mean/std) from `Crop_recommendation.csv` for the 22 soil-model crops. Score = Gaussian `exp(-½·mean(z²))` over the climate dims, **max-normalized** to 1.0 like the other modules. Returns `{}` (whole module skipped) when coords can't resolve or the API is down — a recommendation is never blocked. The 14 expansion crops (wheat/sugarcane/…) have no envelope and are omitted → fusion degrades them per-crop.
- **`analysis/fusion.py`** — weather blended at **0.15** (Smart: suitability .30/regional .25/market .30/weather .15) and **0.20** (Simple: regional .50/market .30/weather .20). Added only when it actually ran (`if wf:`); per-crop weight renormalization handles crops without a weather term. New why-line "climate well-suited for this season" / caution "seasonal climate is marginal for this crop".
- **Card:** a cyan **Weather** bar (`frontend/src/pages/CropAdvisor.jsx`), rendered automatically from `breakdown.weather`.

### ⚠️ Key correction (found in live verification)
The scorer uses **temperature + humidity ONLY**. The first cut included rainfall, but `Crop_recommendation.csv`'s `rainfall` column (~85–240) is **not** real annual mm — Open-Meteo returns ~1250 mm for Bihar. That ~20σ mismatch made `exp(-½·z²)` underflow to ~0 for every crop, collapsing the signal to a near-binary 0/1 and inverting the ranking (it pushed soil-model crops *below* the expansion crops that have no weather term). Temperature and humidity are genuinely comparable between the CSV and live data, so rainfall was dropped. `seasonal_climate` still returns a real annual `rainfall` value, but the scorer ignores it.

### Verified live (Bihar/Begusarai, Kharif)
`modules_used = [market, regional, weather]`; banana scores weather **1.00** (29°C/78% ≈ banana's 27°C/80%), with a real gradient down through mungbean 0.32 / pigeonpeas 0.22 / maize 0.07 / rice 0.05. Top picks are legitimate Bihar-Kharif crops (pigeonpeas, mungbean, ragi, jute, maize, rice), regional history leading with weather as a sensible secondary nudge. 124 backend tests green; `npm run build` clean.

### Test design note
`tests/conftest.py` has an **autouse fixture** defaulting the weather module OFF, so the suite never hits the network and stays deterministic; the one weather-integration test in `test_fusion.py` overrides it with a stub. `weather_client`/`weather_fit` unit tests monkeypatch `_fetch_archive`/`seasonal_climate`/`get_centroid` directly.

---

## How to run (dev)

```powershell
# 1. Database
docker compose up -d                      # Postgres 16 on :5432

# 2. Backend  (from backend/, venv active)
uvicorn main:app --reload                 # :8000

# 3. Frontend (from frontend/)
npm run dev                               # :5173  (proxies /api → :8000)

# Tests
pytest tests -p no:asyncio                # from backend/
```
