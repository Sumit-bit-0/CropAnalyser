# Crop Recommendation Engine + Profit Planner — Design

**Date:** 2026-05-29
**Project:** Agri Market Access Analyser (`E:\agri-market-analyser`)
**Source idea:** `idea.md` features **A. Crop Recommendation Engine** and **B. Profit Planner**

## Goal
Turn two of the idea.md "decision tools" into working full-stack features that fit the
existing architecture (thin FastAPI routers → `analysis/` modules → `database.py`; React +
Vite + Tailwind frontend). Both are **action-oriented and farmer-friendly**: a form in,
a plain-language decision out, color-coded green / yellow / red.

## Data strategy (decided per dataset)
- **`E:\DataSETAgri\Crop_recommendation.csv`** (≈2,200 rows; cols `N,P,K,temperature,humidity,ph,rainfall,label`, 22 crop classes) → copy a **snapshot** into `backend/data/raw/crop_recommendation.csv` (repo-reproducible, 0.1 MB). Used **only for training**; never read at request time.
- **Profit Planner "current price" + volatility** → read from the **existing `prices` table** (`state, commodity, year, month, farm_gate_price, modal_price`). No new ingestion this round.
- The large mandi CSVs (52 MB / 59 MB) stay **out of scope** — they belong to the deferred Mandi Comparison feature.

---

## Feature 1 — Crop Recommendation Engine

### Model (PyTorch MLP on GPU — honors the GPU rule)
- **`models/crop_recommender.py`** — `CropMLP(nn.Module)`: input 7 → Linear(64) → ReLU → Dropout(0.2) → Linear(32) → ReLU → Linear(n_classes). Small + fast.
- **`models/train_crop_recommender.py`** — CLI script:
  - Load snapshot CSV; `X` = 7 numeric features, `y` = label.
  - `StandardScaler` fit on X (saved). `LabelEncoder` / sorted class list (saved).
  - Stratified train/val split (80/20). `device = cuda if available else cpu` — **print device, warn loudly if CPU** (per GPU rule).
  - CrossEntropyLoss + Adam, ~200 epochs, full-batch (tiny data). Print val accuracy.
  - Save artifacts to `saved_models/`: `crop_recommender.pt` (state_dict + `{in_features, hidden, n_classes}` meta), `crop_recommender_scaler.joblib`, `crop_recommender_labels.json`.

### Inference — `analysis/crop_recommender.py`
- Lazy-load + cache artifacts (module-level singleton).
- `recommend_crops(features: dict, top_k=3) -> list[dict]`: validate 7 fields present & numeric → scale → forward → softmax → top-k → `[{"crop": str, "confidence_pct": float}]` (rounded 1 dp).
- Raise `FileNotFoundError` (→ 503 at API) if artifacts missing.

### API — `api/recommend.py`
- `POST /api/recommend/crop` with Pydantic body `CropInput{N,P,K: float; temperature,humidity,ph,rainfall: float}` (range-validated, e.g. ph 0–14, humidity 0–100).
- Response: `{"top": {...}, "recommendations": [top-3], "model_trained": true}`.
- If model not trained → **503** `{"detail": "Crop recommendation model not trained yet. Run models/train_crop_recommender.py"}` (mirrors forecast's graceful "no model" handling).

### Frontend — `pages/CropRecommender.jsx`
- Form: 7 number inputs with plain labels + units (e.g. "Soil Nitrogen (N)", "Rainfall (mm)"), sensible defaults/placeholders.
- On submit → `recommendCrop(body)`. Render top-3 as cards with a **confidence bar**; #1 highlighted green. Headline in plain language: *"Best pick for your soil: **Maize** (92% match)."*
- Handle 503 with a friendly "model not trained yet" banner (reuse `ErrorBanner`).

---

## Feature 2 — Profit Planner

### Calculation — `analysis/profit_planner.py` (pure, deterministic)
Units (farmer-friendly, India): **area in acres**, **yield in quintal/acre**, **price in ₹/quintal**, costs as **total ₹**.

`plan_profit(...)` inputs: `area_acres, yield_q_per_acre, input_cost, labour_cost, transport_cost, market_price, desired_margin_pct=20`.
- `total_yield_q = area_acres * yield_q_per_acre`
- `total_cost = input_cost + labour_cost + transport_cost`
- `total_revenue = total_yield_q * market_price`
- `profit = total_revenue - total_cost`
- `break_even_price = total_cost / total_yield_q` (guard divide-by-zero → 0/None)
- `target_sale_price = break_even_price * (1 + desired_margin_pct/100)`
- Returns the above + `profit_margin_pct`, a `risk_level`, a plain-language `summary`, and a `recommendation` ("sell now" if market_price ≥ target; "wait / negotiate" if break_even ≤ market_price < target; "loss risk — reconsider" if market_price < break_even).

`get_price_reference(state, commodity)` (from `prices` table):
- `latest_price` (most recent modal_price), `avg_price`, **volatility CV** = `std/mean` of modal_price.
- `risk_level`: CV < 0.15 → **low** (green), 0.15–0.30 → **medium** (yellow), > 0.30 → **high** (red). If no rows → `risk_level="unknown"`, prices `None`.

### API — `api/profit.py`
- `POST /api/profit/plan` (Pydantic body, all positive-number validated) → result dict above.
- `GET /api/profit/price-reference?state=&commodity=` → `{latest_price, avg_price, volatility_cv, risk_level}` (prefills the form's market price + shows risk).

### Frontend — `pages/ProfitPlanner.jsx`
- State + commodity dropdowns sourced from existing `GET /api/trends/filters`.
- "Use market price" button → calls `getPriceReference` to prefill `market_price` and show a risk badge.
- Inputs: area, yield, input/labour/transport cost, (optional) margin %.
- Result card: **profit** (green if +, red if −), break-even ₹/q, target sale ₹/q, **risk badge** (green/yellow/red), and the recommendation sentence.

---

## Cross-cutting change
- **CORS:** `main.py` currently sets `allow_methods=["GET"]`. Add `"POST"` (and keep `"GET"`).
- Register both new routers in `main.py` under `/api`.

## Testing (TDD — never break the 29 existing tests)
- **`tests/test_profit_planner.py`** — pure-math unit tests with explicit `market_price` (no DB): profit sign, break-even, target price, each `risk_level` threshold, divide-by-zero guard, recommendation branches.
- **`tests/test_crop_recommender.py`** — train a tiny model into a temp `saved_models` (or fixture) and assert `recommend_crops` returns `top_k` dicts summing≈100%; assert `FileNotFoundError` path.
- **`tests/test_api.py` additions** — `POST /api/recommend/crop` (200 structure when model present / 503 when absent), `POST /api/profit/plan` (200 structure), `GET /api/profit/price-reference` (200, keys present).

## Out of scope (idea.md roadmap, not this round)
Mandi Comparison, Smart-Forecast-confidence upgrade, Market Alerts, Chatbot, What-If Simulator,
standalone Risk Score page, i18n, Mobile-first mode, PDF export.

## Definition of done
- `train_crop_recommender.py` runs on GPU, prints val accuracy, writes 3 artifacts.
- All new + existing backend tests pass (`pytest tests/ -q`).
- `npm run build` passes; both new pages reachable from the NavBar and functional against the running backend.
