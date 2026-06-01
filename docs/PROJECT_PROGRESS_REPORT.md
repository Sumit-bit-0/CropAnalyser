# Agri Market Access Analyser — Full Progress Report

**Prepared:** 2026-06-01
**Project root:** `E:\agri-market-analyser`
**Owner:** Sumit (BTech CSE 2026) — built to strengthen **Product Manager** and **Data Analyst** CVs, agriculture / social-impact domain.
**Current branch:** `master` (working tree dirty — see §9).

> This report covers everything built on the project to date: the original 5-page dashboard, the 4-feature MVP upgrade, LSTM forecasting at scale, performance hardening, the SQLite→PostgreSQL migration, and the CropAdvisor multi-source recommender. Newest work is summarized first; the full chronology follows.

---

## 1. What the product is

An **India farm-to-retail price-gap dashboard and farmer decision tool**. It analyses ~28 million mandi/Agmarknet price records to show where farmers lose value between farm gate and market, forecasts prices, and recommends which crops to grow. Two audiences: a **data-analytics story** (dashboards, LSTM forecasting, fusion modelling) and a **product story** (farmer-first features, charter/WBS/risk register, policy brief).

### Pages (10 routes)
| Route | Page | Purpose |
|---|---|---|
| `/` | Home | Mobile-first summary cards |
| `/map` | State Map | Leaflet choropleth of price markup by state |
| `/analyser` | Crop Analyser | Per-crop markup analysis |
| `/trends` | Price Trend | Historical price charts |
| `/revenue` | Revenue Loss | Estimated farmer revenue loss |
| `/forecast` | LSTM Forecast | 6-month price forecasts (trained states only) |
| `/recommend` | Soil Match | Soil/climate → crop (7-input MLP, "Simple") |
| `/profit` | Profit Planner | Profit/break-even calculator + price volatility |
| `/mandi` | Mandi Compare | GPS → nearest markets ranked by net price |
| `/advisor` | **Crop Advisor** | **Multi-source fused crop recommendation** ⭐ |

---

## 2. Technology stack (complete)

### Backend
| Concern | Tool |
|---|---|
| Language | Python 3.10.11 |
| Web framework | FastAPI (thin `api/` routers → `analysis/` logic) |
| Server | uvicorn |
| Validation | Pydantic |
| **Database** | **PostgreSQL 16** (Docker) — migrated from SQLite 2026-05-31 |
| DB driver / engine | psycopg 3.3.4 + SQLAlchemy 2.0.50 (core + `text()`) |
| Config | python-dotenv (`.env` → `DATABASE_URL`, API base URLs) |
| ML — recommender | PyTorch MLP (7-input soil/climate classifier) |
| ML — forecasting | PyTorch LSTM (1,985 per-series price models) |
| Scaler persistence | joblib |
| Tests | pytest (`pytest tests -p no:asyncio`) — **97 passing** |

### Frontend
| Concern | Tool |
|---|---|
| Framework | React 19 |
| Build / dev | Vite (`:5173`, proxies `/api` → `:8000`) |
| Styling | Tailwind CSS v3 |
| Charts | Recharts |
| Maps | Leaflet |
| Routing | react-router-dom |
| HTTP | axios |
| Geolocation | Browser Geolocation API |

### Infrastructure & hardware
| Concern | Detail |
|---|---|
| DB container | Docker Compose — Postgres 16, named volume `agri_pgdata`, healthcheck |
| Bulk load | PostgreSQL `COPY` (28M+ rows) |
| GPU | NVIDIA **RTX 3060 Laptop (6 GB)**, CUDA — torch 2.11.0+cu128 |
| Dev machine | ASUS TUF A15 FA506QM · Ryzen 9 5900HX · 16 GB · 2× NVMe |
| Planned deploy | Render (backend + managed Postgres) + Vercel (frontend) |

> **Standing rule:** all model training must run on the RTX 3060 (CUDA), never CPU. Honored throughout.

---

## 3. Data assets

| Dataset | Where it lives | Size |
|---|---|---|
| Agmarknet prices | `prices` table (Postgres) | **~27.6 M rows** |
| Mandi prices (GPS) | `mandi_prices` table | **737 K rows** (5 commodities) |
| District crop history | `district_crop_history` table | **242 K rows** |
| Precomputed summaries | `summary_state_markup` (34), `summary_crop_markup` (4,566), `summary_revenue_loss` (34) | tiny |
| Soil/climate training | `Crop_recommendation.csv` (real, 7 features) | small |
| District centroids | `india_district_centroids.csv` (416 districts / 35 states) | small |
| Source datasets | `E:\DataSETAgri\` | ~2 GB |

---

## 4. Build timeline (chronological)

### 2026-05-25 — Planning
Full spec + plan written (5-page dashboard). Stack chosen: FastAPI + PyTorch + SQLite / React + Leaflet + Recharts + Tailwind. Two CV angles defined.

### 2026-05-27 — Full build (Tasks 1–14)
Entire base project built via subagent-driven development with spec/quality review after each task — **21 commits, 29/29 tests**. Phases: scaffold → data schema/loader/cleaner/SQLite → markup/revenue/trends analysis → PriceLSTM + trainer + predictor → FastAPI (lifespan) + 5 endpoints (TDD) → React dashboard (5 pages). Notable decisions: `contextlib.closing()` for connections, joblib scaler, CORS from env, GeoJSON from `geohacker/india`, Tailwind v3 pinned.

### 2026-05-28 — LSTM prep + laptop service
Thermal investigation (peak 83.9 °C → laptop sent for service). Confirmed training env ready (2 GB SQLite DB, empty `saved_models`, torch was CPU-only at this point).

### 2026-05-29 — Moved to E: + MVP upgrade scoped & built
- **Project relocated** `C:\…\Projects\` → `E:\agri-market-analyser\` (robocopy, 379 files / 2.05 GB). Old copy deleted.
- venv recreated with **CUDA torch** (cu128, RTX 3060 verified). 29/29 tests green on E:.
- **Built 4 MVP features** (branch `feature/mvp-upgrade`, 5 commits, TDD throughout, **52/52 tests**):
  1. **Crop Recommender** — PyTorch MLP, GPU-trained, **98.6 % val acc**, `POST /api/recommend/crop`, `/recommend` page.
  2. **Profit Planner** — break-even/target calculator + price volatility/risk from `prices`, `/profit` page.
  3. **Mandi Comparison (GPS)** — ingested `mandi_prices` (737 K rows), haversine + district centroids, net-price-after-transport ranking, `/mandi` page.
  4. **Farmer-friendly mobile UI** — responsive hamburger nav, mobile-first Home, StateMap → `/map`.

### 2026-05-30 — A heavy day: merge, LSTM at scale, perf hardening
- **Merged MVP upgrade → master** (`946cfd7`, fast-forward).
- **Laptop performance optimization** (machine back from service): startup trim, browser HW-accel pinned, service recommendations, GPU memory clarified (RTX 3060 = full 6 GB; CUDA Sysmem Fallback for >6 GB models).
- **LSTM forecasting scaled to 15 major states** → **1,985 `.pt` models** (66–170 per state), all GPU-trained, resumable trainer `train_major.py`. 143 benign failures (raw rows ≥23 but <23 monthly points). *Gotcha: exit-code 127 is spurious — check log for `=== DONE ===`; Windows console needs UTF-8 reconfigure for Devanagari commodity names.*
- **Forecast page filtered** to only trained state×crop combos (no dead options) — committed `310f924`.
- **Live browser smoke test** of all 9 pages — green, 0 console errors.
- **Critical perf fix:** `states/markup`, `revenue-loss`, `crops/{crop}/markup` each did a full `GROUP BY` over 27.6 M rows (~70 s/request). Introduced **precomputed summary tables** → **~70 s → ~6 ms** (~10,000×). Extended same pattern to `trends/filters` (12 s → 7 ms) and `forecast/available` (2.5 s → 162 ms). Committed `782b910`.

### 2026-05-31 — PostgreSQL migration + CropAdvisor
The two biggest pieces — see §5 and §6.

### 2026-05-31 (late) — CropAdvisor UX polish + GPS locate
Built and tested, **left uncommitted** at the user's instruction — see §9.

---

## 5. PostgreSQL migration (the infrastructure milestone)

**Why:** portfolio/resume credibility + a real deployable path (Render-managed Postgres). SQLite isn't convincing for a "real" data product, and a 28 M-row table wants real indexing.

**Result:** ~55× speedup on heavy paths, **28.3 M rows migrated row-for-row**, **zero query call-site changes**.

**How:**
- New `docker-compose.yml` (Postgres 16, volume, healthcheck) + `.env`/`.env.example` with `DATABASE_URL`.
- `database.py` rewritten on SQLAlchemy + psycopg3, driven by `DATABASE_URL`.
- A **`?` → named-bind shim** (`_to_named`) rewrites SQLite placeholders to `:p0, :p1…` at runtime — so existing `query()` calls were untouched.
- `data/migrate_to_pg.py` `COPY`-migrated `prices` (27.58 M) + `mandi_prices` (737 K), rebuilt summaries, verified counts.
- **Functional indexes** on `LOWER(state)/LOWER(commodity)` — a filtered trend query went 2.4 s → 44 ms.
- Legacy `agri.db` retained as a fallback.

**Postgres-vs-SQLite fixes:** `ROUND(double precision)` needs `CAST(… AS numeric)`; text `ORDER BY` collation differs → sort in Python; `sqlite_master` → inspector / `to_regclass`; `AUTOINCREMENT` → `GENERATED ALWAYS AS IDENTITY`.

---

## 6. CropAdvisor — multi-source recommender (the feature milestone)

Recommends crops by **fusing three independent signals** into one explained ranking. Merged to `master` @ `2a463b6`, **93 tests**, verified live in browser.

```
 inputs: state, district, season, goal, [soil/climate]
        │
   crop_catalog.py  →  20-crop whitelist (synonym-mapped)
        │
   ┌────┴───────────────┬──────────────────────┐
 regional_fit       suitability         market_profitability
 (history:          (PyTorch MLP        (recent_price ×
 consistency +       softmax,            (1 − volatility))
 log-volume)         Smart Mode only)
   └────┬───────────────┴──────────────────────┘
        ▼
     fusion.py  — weighted GEOMETRIC mean + goal nudges
        ▼
  ranked crops + why / cautions  →  POST /api/recommend/smart  →  /advisor
```

**Phase 0 — crop alignment** (`analysis/crop_catalog.py`): the three sources use different crop names, so we derived a **20-crop whitelist** = suitability labels ∩ production crops ∩ market commodities (dropped `kidneybeans` = no market, `muskmelon` = no production) with a synonym map (e.g. pigeonpeas → "Arhar (Tur/Red Gram)").

**Data foundation** (`data/load_crop_history.py`): cleaned `Crop Production data.csv` → `district_crop_history` (242 K rows), canonical-crop tagged, yield computed. *Found & fixed a trailing-whitespace data bug that hid all coconut rows.*

**Three scorers** (each `(inputs) → {crop: score 0-1 + stats}`):
- `regional_fit.py` — `0.5·consistency + 0.5·log-volume`, district→state fallback.
- `suitability.py` — reuses the GPU-trained 7-input MLP via new `predict_proba()`, max-normalized (Smart Mode only).
- `market_profitability.py` — `recent_price·(1−CV)`, national default.

**Fusion** (`fusion.py`): weighted **geometric mean** with a softening floor (0.05) and goal multipliers. We started additive, but additive let an absurd crop (**coffee in Punjab**) top the list on market strength alone. The geometric mean collapses toward zero if *any* module scores low, so a crop must be decent on **all** axes — fixing the bug. Graceful degradation: no soil input → suitability drops out (Simple Mode). Emits `why[]` / `cautions[]`.

**API + UI:** `POST /api/recommend/smart` (with `soil` → Smart, without → Simple) + the `/advisor` React page (the old soil-only page was relabeled "Soil Match").

**Known v1 limitations / next refinements:** market score uses absolute ₹ (favours high-price crops — needs per-crop cost/yield); weather is defaulted (Phase 2 = live Open-Meteo); NDVI deferred (Phase 3); the synthetic Smart_Farming dataset was **deliberately rejected as dishonest** — suitability stays on the real `Crop_recommendation.csv`.

---

## 7. Machine learning summary

| Model | Type | Training | Result |
|---|---|---|---|
| Crop recommender | PyTorch MLP, 7 soil/climate inputs | GPU (RTX 3060) | 98.6 % val acc; powers Soil Match + Suitability scorer |
| Price forecaster | PyTorch LSTM, per series (hidden 64, 2 layers, seq 12 → 6) | GPU, 400 epochs, early-stop, resumable | **1,985 models**, 15 major states fully covered |

---

## 8. Testing & verification posture

- **97 backend tests** pass (`pytest tests -p no:asyncio`). Grew 29 → 52 → 93 → 97 across milestones, green at each.
- TDD used for new features and the perf/migration work.
- Multiple **live Chromium smoke tests** (Playwright): all 9–10 pages render with 0 console errors; GPS path verified by overriding geolocation; Forecast error path confirmed friendly.
- Test gotchas captured: run with `-p no:asyncio` (a conftest interaction crashes bare `pytest`); pipe pytest to a log, not `tail` (exit code); don't run the full suite concurrently with browser tests (DB contention).

---

## 9. Current state & open items

**Working tree is intentionally dirty on `master`** — the CropAdvisor UX polish + GPS "Use my location" feature is built and tested but not committed (user: *"log everything, we'll work later"*):

```
 M backend/analysis/geo.py        # locate(lat, lon) — nearest state→district
 M backend/main.py                # include geo.router
 M backend/tests/test_geo.py      # +4 locate/endpoint tests
 M frontend/src/api/client.js     # locateByGps()
 M frontend/src/pages/CropAdvisor.jsx   # polished UI + 📍 button
?? backend/api/geo.py             # GET /api/geo/locate
```
Plus two new untracked docs in `docs/` (`CROPADVISOR_BUILD.md`, this report).

**Verified:** `npm run build` ✓ (691 modules); 97 tests ✓.
**Not yet verified:** the 📍 button end-to-end in a live browser (Playwright had disconnected). Do this before committing.
**Branch decision pending:** likely `feat/advisor-ux` rather than straight to `master`.

**No git remote is configured** — nothing has been pushed anywhere yet.

---

## 10. Roadmap

| Priority | Item |
|---|---|
| Now | Browser-verify GPS button → commit UX/GPS work (branch decision) |
| Phase 2 | Live **Open-Meteo** weather term in suitability/fusion |
| Next | Refine **market score** with per-crop cost & yield (fix expensive-crop bias) |
| Phase 3 | **NDVI** satellite signal |
| Deploy | GitHub remote → **Render** (backend + Postgres) + **Vercel** (frontend) |
| PM track | Charter, WBS, risk register, Trello board, policy brief → PDF |
| Data | Optional ingest of larger mandi dataset for more than 5 commodities |

---

## 11. How to run (dev)

```powershell
docker compose up -d                  # Postgres 16 on :5432
# backend (from backend\, venv active)
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
# frontend (from frontend\)
npm run dev                           # :5173 (proxies /api → :8000)
# tests (from backend\)
venv\Scripts\python.exe -m pytest tests -p no:asyncio -q
```

**Key commands seen along the way:**
```powershell
docker compose up -d
venv\Scripts\python.exe -m data.migrate_to_pg
venv\Scripts\python.exe -m data.load_crop_history
venv\Scripts\python.exe -m models.train_major        # resumable LSTM sweep
git merge --no-ff feat/postgres-migration            # -> master 2a463b6
```
