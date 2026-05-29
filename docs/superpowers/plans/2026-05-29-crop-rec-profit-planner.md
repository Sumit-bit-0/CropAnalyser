# Crop Recommendation Engine + Profit Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two farmer-first decision tools — a GPU-trained Crop Recommendation Engine and a Profit Planner — to the Agri Market Access Analyser, full-stack.

**Architecture:** Follow the existing pattern: thin FastAPI routers (`api/`) → logic modules (`analysis/`, `models/`) → `database.py`. Crop recommender = PyTorch MLP trained on GPU from a CSV snapshot, artifacts in `saved_models/`, loaded for inference. Profit Planner = pure deterministic calculator + a volatility lookup against the existing `prices` table. Frontend = two new React pages wired into the router/NavBar.

**Tech Stack:** FastAPI, PyTorch (CUDA, RTX 3060), scikit-learn (StandardScaler/LabelEncoder), pandas, SQLite, React 19 + Vite + Tailwind + axios.

**Working dir for all commands:** `E:\agri-market-analyser\backend` (backend) or `E:\agri-market-analyser\frontend` (frontend). Python = `venv\Scripts\python.exe`.

**Commit note:** Commit steps are included per TDD convention. The repo has no remote (local-only). Confirm commit cadence with the user at execution start.

---

## File Structure

**Create:**
- `backend/data/raw/crop_recommendation.csv` — snapshot of training data
- `backend/models/crop_recommender.py` — `CropMLP` nn.Module
- `backend/models/train_crop_recommender.py` — GPU training script → artifacts
- `backend/analysis/crop_recommender.py` — inference (`recommend_crops`)
- `backend/analysis/profit_planner.py` — `plan_profit`, `get_price_reference`
- `backend/api/recommend.py` — `POST /api/recommend/crop`
- `backend/api/profit.py` — `POST /api/profit/plan`, `GET /api/profit/price-reference`
- `backend/tests/test_crop_recommender.py`
- `backend/tests/test_profit_planner.py`
- `frontend/src/pages/CropRecommender.jsx`
- `frontend/src/pages/ProfitPlanner.jsx`

**Modify:**
- `backend/main.py` — add `"POST"` to CORS, register 2 routers
- `backend/tests/test_api.py` — add endpoint tests
- `frontend/src/api/client.js` — add 3 API functions
- `frontend/src/components/NavBar.jsx` — 2 nav links
- `frontend/src/App.jsx` — 2 routes

**Artifacts produced (not committed — in `saved_models/`, gitignored):**
- `crop_recommender.pt`, `crop_recommender_scaler.joblib`, `crop_recommender_labels.json`

---

## Task 1: Project setup — data snapshot + CORS

**Files:**
- Create: `backend/data/raw/crop_recommendation.csv`
- Modify: `backend/main.py:14-19`

- [ ] **Step 1: Copy the dataset snapshot**

Run (PowerShell):
```powershell
Copy-Item "E:\DataSETAgri\Crop_recommendation.csv" "E:\agri-market-analyser\backend\data\raw\crop_recommendation.csv"
```

- [ ] **Step 2: Verify header + row count**

Run: `venv\Scripts\python.exe -c "import pandas as pd; d=pd.read_csv('data/raw/crop_recommendation.csv'); print(list(d.columns)); print(len(d), d['label'].nunique())"`
Expected: `['N','P','K','temperature','humidity','ph','rainfall','label']` and a row count (~2200) with ~22 unique labels.

- [ ] **Step 3: Add POST to CORS in `main.py`**

Change `allow_methods=["GET"]` to:
```python
    allow_methods=["GET", "POST"],
```

- [ ] **Step 4: Verify existing tests still pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_api.py -q`
Expected: all pass (no regressions).

- [ ] **Step 5: Commit**

```bash
git add backend/data/raw/crop_recommendation.csv backend/main.py
git commit -m "chore: add crop-rec dataset snapshot + enable POST CORS"
```

---

## Task 2: CropMLP model class

**Files:**
- Create: `backend/models/crop_recommender.py`
- Test: `backend/tests/test_crop_recommender.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_crop_recommender.py
import torch
from models.crop_recommender import CropMLP

def test_cropmlp_output_shape():
    model = CropMLP(in_features=7, n_classes=22)
    x = torch.randn(5, 7)
    out = model(x)
    assert out.shape == (5, 22)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_crop_recommender.py::test_cropmlp_output_shape -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.crop_recommender'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/models/crop_recommender.py
import torch.nn as nn


class CropMLP(nn.Module):
    def __init__(self, in_features: int, n_classes: int, hidden=(64, 32)):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden[0]), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden[0], hidden[1]), nn.ReLU(),
            nn.Linear(hidden[1], n_classes),
        )

    def forward(self, x):
        return self.net(x)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_crop_recommender.py::test_cropmlp_output_shape -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/models/crop_recommender.py backend/tests/test_crop_recommender.py
git commit -m "feat: add CropMLP classifier model"
```

---

## Task 3: GPU training script

**Files:**
- Create: `backend/models/train_crop_recommender.py`

- [ ] **Step 1: Write the training script**

```python
# backend/models/train_crop_recommender.py
import json
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from config import DATA_RAW, MODELS_DIR, init_dirs
from models.crop_recommender import CropMLP

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def main():
    init_dirs()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        print("WARNING: CUDA not available — training on CPU (violates project GPU rule).")
    print(f"Training crop recommender on device: {device}")

    df = pd.read_csv(DATA_RAW / "crop_recommendation.csv")
    labels = sorted(df["label"].unique().tolist())
    label_to_idx = {c: i for i, c in enumerate(labels)}

    X = df[FEATURES].values.astype(np.float32)
    y = df["label"].map(label_to_idx).values.astype(np.int64)

    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X).astype(np.float32)

    Xtr, Xva, ytr, yva = train_test_split(Xs, y, test_size=0.2, stratify=y, random_state=42)
    Xtr_t = torch.tensor(Xtr, device=device); ytr_t = torch.tensor(ytr, device=device)
    Xva_t = torch.tensor(Xva, device=device); yva_t = torch.tensor(yva, device=device)

    model = CropMLP(in_features=len(FEATURES), n_classes=len(labels)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(200):
        model.train(); opt.zero_grad()
        loss = loss_fn(model(Xtr_t), ytr_t)
        loss.backward(); opt.step()
        if (epoch + 1) % 50 == 0:
            model.eval()
            with torch.no_grad():
                acc = (model(Xva_t).argmax(1) == yva_t).float().mean().item()
            print(f"epoch {epoch+1}: loss={loss.item():.4f} val_acc={acc:.4f}")

    model.eval()
    with torch.no_grad():
        val_acc = (model(Xva_t).argmax(1) == yva_t).float().mean().item()
    print(f"FINAL val_acc={val_acc:.4f}")

    torch.save(
        {"state_dict": model.cpu().state_dict(),
         "in_features": len(FEATURES), "n_classes": len(labels)},
        MODELS_DIR / "crop_recommender.pt",
    )
    joblib.dump(scaler, MODELS_DIR / "crop_recommender_scaler.joblib")
    (MODELS_DIR / "crop_recommender_labels.json").write_text(json.dumps(labels))
    print(f"Saved artifacts to {MODELS_DIR}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the training script**

Run: `venv\Scripts\python.exe models\train_crop_recommender.py`
Expected: prints `device: cuda`, epoch logs, `FINAL val_acc=` ≥ 0.90 (clean dataset), and "Saved artifacts".

- [ ] **Step 3: Verify artifacts exist**

Run: `venv\Scripts\python.exe -c "from config import MODELS_DIR; import os; print([f for f in os.listdir(MODELS_DIR) if 'crop_recommender' in f])"`
Expected: `['crop_recommender.pt', 'crop_recommender_labels.json', 'crop_recommender_scaler.joblib']`.

- [ ] **Step 4: Commit**

```bash
git add backend/models/train_crop_recommender.py
git commit -m "feat: GPU training script for crop recommender"
```

---

## Task 4: Crop recommender inference

**Files:**
- Create: `backend/analysis/crop_recommender.py`
- Test: `backend/tests/test_crop_recommender.py` (append)

- [ ] **Step 1: Write the failing tests (append to test file)**

```python
import pytest
from analysis import crop_recommender as cr

SAMPLE = {"N": 90, "P": 42, "K": 43, "temperature": 20.8,
          "humidity": 82.0, "ph": 6.5, "rainfall": 202.9}

def test_recommend_crops_structure():
    out = cr.recommend_crops(SAMPLE, top_k=3)
    assert len(out) == 3
    assert {"crop", "confidence_pct"} <= set(out[0].keys())
    assert out[0]["confidence_pct"] >= out[1]["confidence_pct"]  # sorted desc
    assert sum(r["confidence_pct"] for r in out) <= 100.5

def test_recommend_missing_model_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(cr, "_CACHE", None, raising=False)
    monkeypatch.setattr(cr, "MODELS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        cr.recommend_crops(SAMPLE)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_crop_recommender.py -k recommend -v`
Expected: FAIL — `ModuleNotFoundError` / attribute missing.

- [ ] **Step 3: Write the implementation**

```python
# backend/analysis/crop_recommender.py
import json
import joblib
import numpy as np
import torch
from config import MODELS_DIR
from models.crop_recommender import CropMLP

FEATURES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]
_CACHE = None


def _load():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    model_path = MODELS_DIR / "crop_recommender.pt"
    scaler_path = MODELS_DIR / "crop_recommender_scaler.joblib"
    labels_path = MODELS_DIR / "crop_recommender_labels.json"
    if not (model_path.exists() and scaler_path.exists() and labels_path.exists()):
        raise FileNotFoundError(
            "Crop recommendation model not trained yet. Run models/train_crop_recommender.py"
        )
    ckpt = torch.load(str(model_path), map_location="cpu")
    model = CropMLP(in_features=ckpt["in_features"], n_classes=ckpt["n_classes"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    scaler = joblib.load(scaler_path)
    labels = json.loads(labels_path.read_text())
    _CACHE = (model, scaler, labels)
    return _CACHE


def recommend_crops(features: dict, top_k: int = 3) -> list[dict]:
    missing = [f for f in FEATURES if f not in features]
    if missing:
        raise ValueError(f"Missing features: {missing}")
    model, scaler, labels = _load()
    x = np.array([[float(features[f]) for f in FEATURES]], dtype=np.float32)
    xs = scaler.transform(x).astype(np.float32)
    with torch.no_grad():
        probs = torch.softmax(model(torch.tensor(xs)), dim=1).numpy()[0]
    idx = probs.argsort()[::-1][:top_k]
    return [{"crop": labels[i], "confidence_pct": round(float(probs[i] * 100), 1)} for i in idx]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_crop_recommender.py -v`
Expected: all PASS (requires Task 3 artifacts present).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/crop_recommender.py backend/tests/test_crop_recommender.py
git commit -m "feat: crop recommendation inference"
```

---

## Task 5: Crop recommendation API

**Files:**
- Create: `backend/api/recommend.py`
- Modify: `backend/main.py` (import + register router)
- Test: `backend/tests/test_api.py` (append)

- [ ] **Step 1: Write the failing test (append to test_api.py)**

```python
def test_recommend_crop():
    body = {"N": 90, "P": 42, "K": 43, "temperature": 20.8,
            "humidity": 82.0, "ph": 6.5, "rainfall": 202.9}
    r = client.post("/api/recommend/crop", json=body)
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        data = r.json()
        assert "recommendations" in data and "top" in data
        assert "crop" in data["top"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_api.py::test_recommend_crop -v`
Expected: FAIL — 404 (route not found).

- [ ] **Step 3: Write the router**

```python
# backend/api/recommend.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from analysis.crop_recommender import recommend_crops

router = APIRouter()


class CropInput(BaseModel):
    N: float = Field(ge=0)
    P: float = Field(ge=0)
    K: float = Field(ge=0)
    temperature: float
    humidity: float = Field(ge=0, le=100)
    ph: float = Field(ge=0, le=14)
    rainfall: float = Field(ge=0)


@router.post("/recommend/crop")
def recommend(body: CropInput):
    try:
        recs = recommend_crops(body.model_dump(), top_k=3)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"top": recs[0], "recommendations": recs, "model_trained": True}
```

- [ ] **Step 4: Register router in `main.py`**

Add to the import line: `from api import states, crops, trends, revenue, forecast, recommend, profit`
Add after the forecast router line:
```python
app.include_router(recommend.router, prefix="/api")
```
(Note: `profit` import is used in Task 8 — adding it now is fine only AFTER Task 8 creates the file. To avoid an import error, add `recommend` here and add `profit` in Task 8. So for THIS task, import only `recommend`.)

For this task, set the import to:
```python
from api import states, crops, trends, revenue, forecast, recommend
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_api.py::test_recommend_crop -v`
Expected: PASS (200, since model trained in Task 3).

- [ ] **Step 6: Commit**

```bash
git add backend/api/recommend.py backend/main.py backend/tests/test_api.py
git commit -m "feat: POST /api/recommend/crop endpoint"
```

---

## Task 6: Profit Planner calculation

**Files:**
- Create: `backend/analysis/profit_planner.py`
- Test: `backend/tests/test_profit_planner.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_profit_planner.py
from analysis.profit_planner import plan_profit

BASE = dict(area_acres=2.0, yield_q_per_acre=20.0, input_cost=10000.0,
            labour_cost=5000.0, transport_cost=3000.0, market_price=1500.0)

def test_profit_positive():
    r = plan_profit(**BASE)
    # total_yield = 40 q; revenue = 60000; cost = 18000; profit = 42000
    assert r["total_yield_q"] == 40.0
    assert r["total_revenue"] == 60000.0
    assert r["total_cost"] == 18000.0
    assert r["profit"] == 42000.0

def test_break_even_and_target():
    r = plan_profit(**BASE, desired_margin_pct=20)
    assert r["break_even_price"] == 450.0          # 18000 / 40
    assert r["target_sale_price"] == 540.0          # 450 * 1.2

def test_recommendation_sell_now():
    r = plan_profit(**BASE)                          # market 1500 >> target
    assert r["recommendation"].startswith("Sell")

def test_loss_when_price_below_break_even():
    r = plan_profit(**{**BASE, "market_price": 300.0})  # < break-even 450
    assert r["profit"] < 0
    assert "loss" in r["recommendation"].lower()

def test_zero_yield_guarded():
    r = plan_profit(**{**BASE, "yield_q_per_acre": 0.0})
    assert r["break_even_price"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_profit_planner.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# backend/analysis/profit_planner.py
from database import query


def plan_profit(area_acres, yield_q_per_acre, input_cost, labour_cost,
                transport_cost, market_price, desired_margin_pct=20.0):
    total_yield_q = area_acres * yield_q_per_acre
    total_cost = input_cost + labour_cost + transport_cost
    total_revenue = total_yield_q * market_price
    profit = total_revenue - total_cost

    if total_yield_q > 0:
        break_even_price = round(total_cost / total_yield_q, 2)
        target_sale_price = round(break_even_price * (1 + desired_margin_pct / 100), 2)
    else:
        break_even_price = None
        target_sale_price = None

    margin_pct = round((profit / total_revenue * 100), 1) if total_revenue > 0 else None

    if break_even_price is None:
        rec = "Enter a yield greater than zero to plan profit."
    elif market_price < break_even_price:
        rec = f"Loss risk — current price ₹{market_price}/q is below your break-even ₹{break_even_price}/q. Reconsider this crop or cut costs."
    elif target_sale_price is not None and market_price >= target_sale_price:
        rec = f"Sell now — current price ₹{market_price}/q already beats your target ₹{target_sale_price}/q."
    else:
        rec = f"Wait or negotiate — you cover costs, but aim for ₹{target_sale_price}/q to hit your {desired_margin_pct:.0f}% margin."

    return {
        "total_yield_q": round(total_yield_q, 2),
        "total_cost": round(total_cost, 2),
        "total_revenue": round(total_revenue, 2),
        "profit": round(profit, 2),
        "profit_margin_pct": margin_pct,
        "break_even_price": break_even_price,
        "target_sale_price": target_sale_price,
        "recommendation": rec,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_profit_planner.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/profit_planner.py backend/tests/test_profit_planner.py
git commit -m "feat: profit planner calculation"
```

---

## Task 7: Price reference (volatility / risk) from prices table

**Files:**
- Modify: `backend/analysis/profit_planner.py` (add function)
- Test: `backend/tests/test_profit_planner.py` (append)

- [ ] **Step 1: Write the failing test**

```python
from analysis.profit_planner import get_price_reference

def test_price_reference_keys():
    r = get_price_reference("Maharashtra", "Onion")
    assert {"latest_price", "avg_price", "volatility_cv", "risk_level"} <= set(r.keys())
    assert r["risk_level"] in ("low", "medium", "high", "unknown")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_profit_planner.py::test_price_reference_keys -v`
Expected: FAIL — `ImportError: cannot import name 'get_price_reference'`.

- [ ] **Step 3: Add the function to `profit_planner.py`**

```python
def get_price_reference(state: str, commodity: str) -> dict:
    df = query(
        """
        SELECT modal_price, year, month FROM prices
        WHERE LOWER(state) = LOWER(?) AND LOWER(commodity) = LOWER(?)
        ORDER BY year, month
        """,
        (state, commodity),
    )
    if df.empty:
        return {"latest_price": None, "avg_price": None,
                "volatility_cv": None, "risk_level": "unknown"}
    mean = float(df["modal_price"].mean())
    std = float(df["modal_price"].std(ddof=0))
    cv = (std / mean) if mean else 0.0
    if cv < 0.15:
        risk = "low"
    elif cv <= 0.30:
        risk = "medium"
    else:
        risk = "high"
    return {
        "latest_price": round(float(df["modal_price"].iloc[-1]), 2),
        "avg_price": round(mean, 2),
        "volatility_cv": round(cv, 3),
        "risk_level": risk,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_profit_planner.py::test_price_reference_keys -v`
Expected: PASS (risk_level may be any valid value depending on data).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/profit_planner.py backend/tests/test_profit_planner.py
git commit -m "feat: price reference + volatility risk level"
```

---

## Task 8: Profit Planner API

**Files:**
- Create: `backend/api/profit.py`
- Modify: `backend/main.py` (import + register)
- Test: `backend/tests/test_api.py` (append)

- [ ] **Step 1: Write the failing tests (append)**

```python
def test_profit_plan():
    body = {"area_acres": 2, "yield_q_per_acre": 20, "input_cost": 10000,
            "labour_cost": 5000, "transport_cost": 3000, "market_price": 1500}
    r = client.post("/api/profit/plan", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["profit"] == 42000.0
    assert "recommendation" in data

def test_price_reference_endpoint():
    r = client.get("/api/profit/price-reference", params={"state": "Maharashtra", "commodity": "Onion"})
    assert r.status_code == 200
    assert "risk_level" in r.json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_api.py -k "profit or price_reference" -v`
Expected: FAIL — 404.

- [ ] **Step 3: Write the router**

```python
# backend/api/profit.py
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from analysis.profit_planner import plan_profit, get_price_reference

router = APIRouter()


class ProfitInput(BaseModel):
    area_acres: float = Field(gt=0)
    yield_q_per_acre: float = Field(ge=0)
    input_cost: float = Field(ge=0)
    labour_cost: float = Field(ge=0)
    transport_cost: float = Field(ge=0)
    market_price: float = Field(ge=0)
    desired_margin_pct: float = Field(default=20.0, ge=0)


@router.post("/profit/plan")
def profit_plan(body: ProfitInput):
    return plan_profit(**body.model_dump())


@router.get("/profit/price-reference")
def price_reference(state: str = Query(...), commodity: str = Query(...)):
    return get_price_reference(state, commodity)
```

- [ ] **Step 4: Register router in `main.py`**

Update import to: `from api import states, crops, trends, revenue, forecast, recommend, profit`
Add after the recommend router line:
```python
app.include_router(profit.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_api.py -k "profit or price_reference" -v`
Expected: PASS.

- [ ] **Step 6: Run the FULL backend suite (no regressions)**

Run: `venv\Scripts\python.exe -m pytest tests/ -q`
Expected: all pass (29 original + new tests).

- [ ] **Step 7: Commit**

```bash
git add backend/api/profit.py backend/main.py backend/tests/test_api.py
git commit -m "feat: profit planner API endpoints"
```

---

## Task 9: Frontend API client methods

**Files:**
- Modify: `frontend/src/api/client.js`

- [ ] **Step 1: Add the three functions (append before EOF)**

```javascript
export const recommendCrop    = (body) => api.post('/recommend/crop', body).then(r => r.data)
export const planProfit       = (body) => api.post('/profit/plan', body).then(r => r.data)
export const getPriceReference = (state, commodity) =>
  api.get('/profit/price-reference', { params: { state, commodity } }).then(r => r.data)
```

- [ ] **Step 2: Verify it compiles**

Run (in `frontend/`): `npm run build`
Expected: build succeeds (exit 0).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "feat: frontend API client for recommend + profit"
```

---

## Task 10: Crop Recommender page

**Files:**
- Create: `frontend/src/pages/CropRecommender.jsx`

- [ ] **Step 1: Write the page**

```jsx
import { useState } from 'react'
import { recommendCrop } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'

const FIELDS = [
  ['N', 'Nitrogen (N)', 90], ['P', 'Phosphorus (P)', 42], ['K', 'Potassium (K)', 43],
  ['temperature', 'Temperature (°C)', 21], ['humidity', 'Humidity (%)', 82],
  ['ph', 'Soil pH', 6.5], ['rainfall', 'Rainfall (mm)', 203],
]

export default function CropRecommender() {
  const [form, setForm] = useState(Object.fromEntries(FIELDS.map(([k, , v]) => [k, v])))
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, Number(v)]))
      setResult(await recommendCrop(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed')
      setResult(null)
    }
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-green-800 mb-1">Crop Recommendation</h1>
      <p className="text-gray-600 mb-4">Enter your soil and climate values to find the best crops to grow.</p>
      {error && <ErrorBanner message={error} />}
      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {FIELDS.map(([k, label]) => (
          <label key={k} className="text-sm text-gray-700">
            {label}
            <input type="number" step="any" value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              className="mt-1 w-full border rounded px-2 py-1" />
          </label>
        ))}
        <button className="col-span-2 md:col-span-4 bg-green-700 text-white rounded py-2 font-medium hover:bg-green-800">
          Recommend crops
        </button>
      </form>
      {result && (
        <div>
          <p className="text-lg mb-3">Best pick for your soil:{' '}
            <span className="font-bold text-green-700">{result.top.crop}</span>{' '}
            ({result.top.confidence_pct}% match)</p>
          <div className="space-y-2">
            {result.recommendations.map((r, i) => (
              <div key={r.crop} className={`p-3 rounded border ${i === 0 ? 'border-green-500 bg-green-50' : 'border-gray-200'}`}>
                <div className="flex justify-between text-sm font-medium">
                  <span className="capitalize">{r.crop}</span><span>{r.confidence_pct}%</span>
                </div>
                <div className="h-2 bg-gray-200 rounded mt-1">
                  <div className="h-2 bg-green-600 rounded" style={{ width: `${r.confidence_pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run (in `frontend/`): `npm run build`
Expected: succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CropRecommender.jsx
git commit -m "feat: Crop Recommender page"
```

---

## Task 11: Profit Planner page

**Files:**
- Create: `frontend/src/pages/ProfitPlanner.jsx`

- [ ] **Step 1: Write the page**

```jsx
import { useState, useEffect } from 'react'
import { planProfit, getPriceReference, getTrendFilters } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'

const RISK_COLOR = { low: 'bg-green-100 text-green-800', medium: 'bg-yellow-100 text-yellow-800',
                     high: 'bg-red-100 text-red-800', unknown: 'bg-gray-100 text-gray-600' }
const NUM = ['area_acres', 'yield_q_per_acre', 'input_cost', 'labour_cost', 'transport_cost', 'market_price']
const LABELS = { area_acres: 'Area (acres)', yield_q_per_acre: 'Yield (quintal/acre)',
  input_cost: 'Input cost (₹)', labour_cost: 'Labour cost (₹)', transport_cost: 'Transport cost (₹)',
  market_price: 'Market price (₹/quintal)' }

export default function ProfitPlanner() {
  const [filters, setFilters] = useState({ states: [], commodities: [] })
  const [state, setState] = useState('')
  const [commodity, setCommodity] = useState('')
  const [ref, setRef] = useState(null)
  const [form, setForm] = useState({ area_acres: 2, yield_q_per_acre: 20, input_cost: 10000,
    labour_cost: 5000, transport_cost: 3000, market_price: 1500 })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { getTrendFilters().then(setFilters).catch(() => {}) }, [])

  const loadPrice = async () => {
    if (!state || !commodity) return
    const r = await getPriceReference(state, commodity)
    setRef(r)
    if (r.latest_price) setForm((f) => ({ ...f, market_price: r.latest_price }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const body = Object.fromEntries(NUM.map((k) => [k, Number(form[k])]))
      setResult(await planProfit(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Calculation failed'); setResult(null)
    }
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-green-800 mb-1">Profit Planner</h1>
      <p className="text-gray-600 mb-4">Estimate profit, break-even price, and selling risk for your crop.</p>
      {error && <ErrorBanner message={error} />}

      <div className="flex flex-wrap gap-2 items-end mb-4">
        <label className="text-sm">State
          <select className="mt-1 block border rounded px-2 py-1" value={state} onChange={(e) => setState(e.target.value)}>
            <option value="">—</option>{filters.states.map((s) => <option key={s}>{s}</option>)}
          </select></label>
        <label className="text-sm">Commodity
          <select className="mt-1 block border rounded px-2 py-1" value={commodity} onChange={(e) => setCommodity(e.target.value)}>
            <option value="">—</option>{filters.commodities.map((c) => <option key={c}>{c}</option>)}
          </select></label>
        <button type="button" onClick={loadPrice} className="bg-green-700 text-white rounded px-3 py-1 text-sm">Use market price</button>
        {ref && (
          <span className={`text-xs px-2 py-1 rounded ${RISK_COLOR[ref.risk_level]}`}>
            Price risk: {ref.risk_level}{ref.latest_price ? ` (latest ₹${ref.latest_price}/q)` : ''}
          </span>
        )}
      </div>

      <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {NUM.map((k) => (
          <label key={k} className="text-sm text-gray-700">{LABELS[k]}
            <input type="number" step="any" value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              className="mt-1 w-full border rounded px-2 py-1" /></label>
        ))}
        <button className="col-span-2 md:col-span-3 bg-green-700 text-white rounded py-2 font-medium hover:bg-green-800">Calculate</button>
      </form>

      {result && (
        <div className="border rounded p-4 space-y-2">
          <p className={`text-2xl font-bold ${result.profit >= 0 ? 'text-green-700' : 'text-red-600'}`}>
            {result.profit >= 0 ? 'Profit' : 'Loss'}: ₹{Math.abs(result.profit).toLocaleString('en-IN')}
          </p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <span>Revenue: ₹{result.total_revenue.toLocaleString('en-IN')}</span>
            <span>Total cost: ₹{result.total_cost.toLocaleString('en-IN')}</span>
            <span>Break-even price: {result.break_even_price ? `₹${result.break_even_price}/q` : '—'}</span>
            <span>Target sale price: {result.target_sale_price ? `₹${result.target_sale_price}/q` : '—'}</span>
          </div>
          <p className="text-gray-800 bg-gray-50 rounded p-2">{result.recommendation}</p>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run (in `frontend/`): `npm run build`
Expected: succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProfitPlanner.jsx
git commit -m "feat: Profit Planner page"
```

---

## Task 12: Wire routes + nav

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/NavBar.jsx`

- [ ] **Step 1: Add imports + routes in `App.jsx`**

Add imports:
```jsx
import CropRecommender from './pages/CropRecommender'
import ProfitPlanner from './pages/ProfitPlanner'
```
Add routes inside `<Routes>`:
```jsx
          <Route path="/recommend" element={<CropRecommender />} />
          <Route path="/profit"    element={<ProfitPlanner />} />
```

- [ ] **Step 2: Add nav links in `NavBar.jsx`**

Add to the `links` array:
```jsx
  { to: '/recommend', label: 'Crop Advisor' },
  { to: '/profit', label: 'Profit Planner' },
```

- [ ] **Step 3: Verify build**

Run (in `frontend/`): `npm run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/components/NavBar.jsx
git commit -m "feat: wire crop advisor + profit planner into nav/routes"
```

---

## Task 13: End-to-end verification

- [ ] **Step 1: Full backend test suite**

Run (in `backend/`): `venv\Scripts\python.exe -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 2: Frontend build**

Run (in `frontend/`): `npm run build`
Expected: exit 0.

- [ ] **Step 3: Manual smoke (optional but recommended)**

Start backend `venv\Scripts\python.exe -m uvicorn main:app --reload` and frontend `npm run dev`; open the two new nav pages, submit each form, confirm a recommendation and a profit result render.

- [ ] **Step 4: Final commit (if any uncommitted changes)**

```bash
git add -A
git commit -m "chore: crop recommender + profit planner complete"
```

---

## Self-Review Notes
- **Spec coverage:** Crop rec model/train/inference/API → Tasks 2–5; Profit calc/price-ref/API → Tasks 6–8; CORS POST → Task 1; frontend pages + wiring → Tasks 9–12; TDD tests throughout; DoD verification → Task 13. ✅
- **Type consistency:** `recommend_crops` returns `[{crop, confidence_pct}]` (Task 4) consumed identically by API (Task 5) and page (Task 10). `plan_profit` keys (Task 6) match API (Task 8) and page (Task 11). `get_price_reference` keys (Task 7) match endpoint + page. `_CACHE`/`MODELS_DIR` monkeypatch target matches module globals. ✅
- **No placeholders:** every code step is complete. ✅
