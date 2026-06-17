# Grow-for-Industry vs Mandi Channel Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-channel net-price comparison (sell-to-processor at MSP/FRP+premium vs sell-at-mandi at modal−transport) and feed its profitability back into the crop recommender as a bounded boost.

**Architecture:** A small curated MSP/FRP reference table feeds `price_reference.py`. `channel_compare.py` composes that with the existing `demand_gate.nearest_facility` and `mandi_compare.compare_markets` to net both channels apples-to-apples and pick a winner. A new `/compare/channels` router exposes it; `fusion.py` calls it to nudge gated crops up when their processor channel out-pays the mandi. A two-column card surfaces it in the workspace.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy/psycopg + Postgres 16, pandas, pytest; React + Vite frontend.

**Spec:** `docs/superpowers/specs/2026-06-17-grow-for-industry-channel-engine-design.md`

---

## Conventions (read before starting)

- **Test runner:** `backend/venv/Scripts/python.exe -m pytest tests/<file> -p no:cacheprovider -q` (run from `backend/`). Do **not** run the whole `tests/` tree unless Docker/Postgres is up — some modules connect at import.
- **DB-free tests:** the new pure/composition logic must not hit Postgres. Tests monkeypatch the composed functions (`assured_price`, `nearest_facility`, `compare_markets`, `predict_yield`) directly — mirror `tests/test_mandi_compare.py` which tests the pure ranker without a DB.
- **Targeted commits only:** `git add <exact paths>` — never `git add -A`. Commit trailer:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Master pushes are fine; the user pushes manually.
- **Committed data:** small curated CSVs under `data/raw/` ARE committed.
- Branch: create `feat/channel-engine` off master before Task 1.

---

## File Structure

| File | Responsibility |
|---|---|
| `data/raw/msp_frp.csv` (new) | Curated `crop,year,msp_per_quintal,basis,premium_pct` reference. |
| `backend/analysis/price_reference.py` (new) | Load table; `assured_price(crop, year)` applies premium. |
| `backend/analysis/channel_compare.py` (new) | `compare_channels(...)` — the engine. |
| `backend/api/compare.py` (new) | `GET /compare/channels` router. |
| `backend/main.py` (modify) | Register the new router. |
| `backend/analysis/fusion.py` (modify) | Bounded processor-wins boost in the gate block. |
| `backend/tests/test_price_reference.py` (new) | price_reference tests. |
| `backend/tests/test_channel_compare.py` (new) | channel_compare tests. |
| `backend/tests/test_api_compare.py` (new) | API tests. |
| `backend/tests/test_fusion_boost.py` (new) | boost + Phase-1 regression. |
| `frontend/src/api/client.js` (modify) | `compareChannels()` call. |
| `frontend/src/workspace/ChannelCompareCard.jsx` (new) | Two-column comparison card. |

---

## Task 1: MSP/FRP reference data + `price_reference.py`

**Files:**
- Create: `data/raw/msp_frp.csv`
- Create: `backend/analysis/price_reference.py`
- Test: `backend/tests/test_price_reference.py`

- [ ] **Step 1: Create the curated CSV**

Create `data/raw/msp_frp.csv`. Columns: `crop,year,msp_per_quintal,basis,premium_pct`. `premium_pct` is blank for the default (5%) and only filled to override. Values below are 2024-25 CACP MSP (₹/quintal) and sugarcane FRP — verify against the latest CACP table at plan-execution time and correct any that have moved; the schema is what matters.

```csv
crop,year,msp_per_quintal,basis,premium_pct
wheat,2024,2425,MSP,
rice,2024,2300,MSP,
mustard,2024,5650,MSP,
groundnut,2024,6783,MSP,
soyabean,2024,4892,MSP,
sunflower,2024,7280,MSP,
pigeonpeas,2024,7550,MSP,
gram,2024,5440,MSP,
lentil,2024,6700,MSP,
cotton,2024,7121,MSP,
sugarcane,2024,340,FRP,
maize,2024,2225,MSP,
barley,2024,1850,MSP,
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_price_reference.py`:

```python
import pytest
from analysis.price_reference import assured_price, PREMIUM_PCT_DEFAULT


def test_known_crop_applies_default_premium():
    out = assured_price("wheat", year=2024)
    assert out["available"] is True
    assert out["basis"] == "MSP"
    assert out["premium_pct"] == PREMIUM_PCT_DEFAULT
    assert out["processor_price"] == pytest.approx(out["msp"] * (1 + PREMIUM_PCT_DEFAULT / 100))


def test_unknown_crop_is_unavailable():
    out = assured_price("dragonfruit")
    assert out["available"] is False
    assert out["processor_price"] is None


def test_sugarcane_uses_frp_basis():
    assert assured_price("sugarcane", year=2024)["basis"] == "FRP"


def test_year_none_picks_latest_on_record(monkeypatch):
    import analysis.price_reference as pr
    monkeypatch.setattr(pr, "_TABLE", None)  # force reload
    monkeypatch.setattr(pr, "_rows", lambda: [
        {"crop": "wheat", "year": 2023, "msp_per_quintal": 2275, "basis": "MSP", "premium_pct": ""},
        {"crop": "wheat", "year": 2024, "msp_per_quintal": 2425, "basis": "MSP", "premium_pct": ""},
    ])
    assert assured_price("wheat")["msp"] == 2425


def test_per_crop_premium_override(monkeypatch):
    import analysis.price_reference as pr
    monkeypatch.setattr(pr, "_TABLE", None)
    monkeypatch.setattr(pr, "_rows", lambda: [
        {"crop": "wheat", "year": 2024, "msp_per_quintal": 2000, "basis": "MSP", "premium_pct": "10"},
    ])
    out = assured_price("wheat")
    assert out["premium_pct"] == 10.0
    assert out["processor_price"] == pytest.approx(2200.0)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_price_reference.py -p no:cacheprovider -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.price_reference'`.

- [ ] **Step 4: Implement `price_reference.py`**

Create `backend/analysis/price_reference.py`:

```python
"""MSP/FRP assured-price reference for the processor selling channel.

Loads the curated data/raw/msp_frp.csv once. assured_price() returns the
processor price = MSP/FRP * (1 + premium). The premium is a documented estimate
(processors often pay a little above the floor); it is labeled estimated in the
UI and overridable per-crop via the optional premium_pct column.
"""
import csv
from config import DATA_RAW

PREMIUM_PCT_DEFAULT = 5.0
_CSV = DATA_RAW / "msp_frp.csv"
_TABLE = None  # {crop: [row, ...]} built lazily; tests reset to None to reload


def _rows():
    """All CSV rows as dicts. Split out so tests can monkeypatch the source."""
    with _CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _load():
    global _TABLE
    if _TABLE is None:
        table = {}
        for r in _rows():
            table.setdefault(r["crop"].strip().lower(), []).append(r)
        _TABLE = table
    return _TABLE


def assured_price(crop, year=None):
    rows = _load().get((crop or "").strip().lower())
    if not rows:
        return {"available": False, "msp": None, "basis": None,
                "premium_pct": PREMIUM_PCT_DEFAULT, "processor_price": None}
    candidates = [r for r in rows if year is None or int(r["year"]) <= year]
    if not candidates:
        candidates = rows
    row = max(candidates, key=lambda r: int(r["year"]))
    msp = float(row["msp_per_quintal"])
    raw_prem = (row.get("premium_pct") or "").strip()
    premium = float(raw_prem) if raw_prem else PREMIUM_PCT_DEFAULT
    return {
        "available": True,
        "msp": msp,
        "basis": row["basis"].strip(),
        "premium_pct": premium,
        "processor_price": round(msp * (1 + premium / 100), 2),
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_price_reference.py -p no:cacheprovider -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add data/raw/msp_frp.csv backend/analysis/price_reference.py backend/tests/test_price_reference.py
git commit -m "feat: MSP/FRP assured-price reference for processor channel"
```

---

## Task 2: `channel_compare.py` — core comparison (no totals)

**Files:**
- Create: `backend/analysis/channel_compare.py`
- Test: `backend/tests/test_channel_compare.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_channel_compare.py`:

```python
import analysis.channel_compare as cc


def _patch(monkeypatch, *, gated, facility, assured, mandi_rows):
    monkeypatch.setattr(cc, "gated_crops", lambda: gated)
    monkeypatch.setattr(cc, "nearest_facility", lambda ft, lat, lon: facility)
    monkeypatch.setattr(cc, "assured_price", lambda crop, year=None: assured)
    monkeypatch.setattr(cc, "compare_markets",
                        lambda crop, lat, lon, rate_per_km, top_k: mandi_rows)


def test_processor_wins_when_near_and_assured_beats_mandi(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility={"name": "X Flour Mill", "km": 22.0},
           assured={"available": True, "msp": 2425, "basis": "MSP",
                    "premium_pct": 5, "processor_price": 2546.25},
           mandi_rows=[{"is_best_net": True, "net_price": 2270.0, "market": "Patna",
                        "distance_km": 60.0, "modal_price": 2300, "transport_per_q": 30.0}])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    assert out["processor"]["available"] is True
    assert out["mandi"]["available"] is True
    assert out["winner"] == "processor"
    assert out["margin_per_q"] > 0
    # net = 2546.25 - 22*0.5 = 2535.25
    assert out["processor"]["net_price"] == 2535.25


def test_mandi_wins_when_facility_far(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility={"name": "Far Mill", "km": 200.0},
           assured={"available": True, "msp": 2425, "basis": "MSP",
                    "premium_pct": 5, "processor_price": 2546.25},
           mandi_rows=[{"is_best_net": True, "net_price": 2500.0, "market": "Patna",
                        "distance_km": 10.0, "modal_price": 2510, "transport_per_q": 5.0}])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    # processor net = 2546.25 - 200*0.5 = 2446.25 < 2500
    assert out["winner"] == "mandi"


def test_processor_unavailable_when_no_facility(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility=None,
           assured={"available": True, "msp": 2425, "basis": "MSP",
                    "premium_pct": 5, "processor_price": 2546.25},
           mandi_rows=[{"is_best_net": True, "net_price": 2270.0, "market": "Patna",
                        "distance_km": 60.0, "modal_price": 2300, "transport_per_q": 30.0}])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    assert out["processor"]["available"] is False
    assert out["winner"] == "mandi"
    assert out["margin_per_q"] is None


def test_processor_unavailable_when_no_msp(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility={"name": "X", "km": 10.0},
           assured={"available": False, "msp": None, "basis": None,
                    "premium_pct": 5, "processor_price": None},
           mandi_rows=[{"is_best_net": True, "net_price": 2270.0, "market": "Patna",
                        "distance_km": 60.0, "modal_price": 2300, "transport_per_q": 30.0}])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    assert out["processor"]["available"] is False
    assert out["winner"] == "mandi"


def test_both_unavailable_gives_null_winner(monkeypatch):
    _patch(monkeypatch,
           gated={},  # crop not gated -> no facility type
           facility=None,
           assured={"available": False, "msp": None, "basis": None,
                    "premium_pct": 5, "processor_price": None},
           mandi_rows=[])
    out = cc.compare_channels("wheat", 25.6, 85.1)
    assert out["winner"] is None
    assert "cannot" in out["explanation"].lower() or "no" in out["explanation"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_channel_compare.py -p no:cacheprovider -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.channel_compare'`.

- [ ] **Step 3: Implement `channel_compare.py`**

Create `backend/analysis/channel_compare.py`:

```python
"""Grow-for-industry vs grow-for-mandi channel comparison.

Composes price_reference (assured processor price) + demand_gate.nearest_facility
(distance to a processor) + mandi_compare.compare_markets (best mandi net) and
nets both channels the same way (price - transport) so they compare apples to
apples. An unavailable channel is marked unavailable, never read as 0.
"""
from analysis.price_reference import assured_price
from analysis.demand_gate import gated_crops, nearest_facility
from analysis.mandi_compare import compare_markets

# Estimated transport cost, rupees per quintal per km (truck ~100 q at ~Rs.50/km).
# Documented estimate, overridable by the caller. Must be non-zero so distance
# actually affects the net comparison (compare_markets defaults it to 0.0).
DEFAULT_RATE_PER_KM = 0.5


def _processor_channel(crop, lat, lon, year, rate_per_km):
    ftype = gated_crops().get(crop)
    if ftype is None:
        return {"available": False, "reason": "crop has no processing channel"}
    fac = nearest_facility(ftype, lat, lon)
    if fac is None:
        return {"available": False, "reason": f"no {ftype} on record nearby"}
    price = assured_price(crop, year=year)
    if not price["available"]:
        return {"available": False, "reason": "no MSP/FRP on record"}
    transport = round(fac["km"] * rate_per_km, 2)
    net = round(price["processor_price"] - transport, 2)
    return {
        "available": True, "facility": fac["name"], "distance_km": fac["km"],
        "assured_price": price["msp"], "premium_pct": price["premium_pct"],
        "processor_price": price["processor_price"], "basis": price["basis"],
        "transport_per_q": transport, "net_price": net,
    }


def _mandi_channel(crop, lat, lon, rate_per_km):
    rows = compare_markets(crop, lat, lon, rate_per_km=rate_per_km, top_k=10)
    best = next((r for r in rows if r.get("is_best_net")), None)
    if best is None:
        return {"available": False, "reason": "no mandi price"}
    return {
        "available": True, "market": best["market"], "distance_km": best["distance_km"],
        "modal_price": best["modal_price"], "transport_per_q": best["transport_per_q"],
        "net_price": best["net_price"],
    }


def _explain(crop, proc, mandi, winner):
    if winner == "processor":
        return (f"Processor pays Rs.{proc['processor_price']:.0f}/q "
                f"({proc['basis']} + est. {proc['premium_pct']:.0f}% premium); after "
                f"{proc['distance_km']} km transport nets Rs.{proc['net_price']:.0f}/q "
                f"vs the best mandi's Rs.{mandi['net_price']:.0f}/q.")
    if winner == "mandi":
        m = (f"Best mandi ({mandi['market']}) nets Rs.{mandi['net_price']:.0f}/q")
        if proc.get("available"):
            return m + f" vs the processor's Rs.{proc['net_price']:.0f}/q."
        return m + f"; processor channel unavailable ({proc.get('reason')})."
    return "No comparison possible: neither a processor nor a mandi price is available."


def compare_channels(crop, lat, lon, *, area_ha=None, state=None, district=None,
                     season=None, year=None, rate_per_km=DEFAULT_RATE_PER_KM):
    proc = _processor_channel(crop, lat, lon, year, rate_per_km)
    mandi = _mandi_channel(crop, lat, lon, rate_per_km)

    if proc.get("available") and mandi.get("available"):
        winner = "processor" if proc["net_price"] >= mandi["net_price"] else "mandi"
        margin = round(proc["net_price"] - mandi["net_price"], 2)
    elif proc.get("available"):
        winner, margin = "processor", None
    elif mandi.get("available"):
        winner, margin = "mandi", None
    else:
        winner, margin = None, None

    return {
        "crop": crop, "processor": proc, "mandi": mandi,
        "winner": winner, "margin_per_q": margin, "total_advantage": None,
        "explanation": _explain(crop, proc, mandi, winner),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_channel_compare.py -p no:cacheprovider -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/channel_compare.py backend/tests/test_channel_compare.py
git commit -m "feat: channel_compare core (processor vs mandi net comparison)"
```

---

## Task 3: `channel_compare` — optional total-₹ advantage

**Files:**
- Modify: `backend/analysis/channel_compare.py`
- Test: `backend/tests/test_channel_compare.py`

- [ ] **Step 1: Write the failing test (append to the test file)**

```python
def _patch_yield(monkeypatch, predicted):
    monkeypatch.setattr(cc, "predict_yield",
                        lambda state, district, season, crop, year:
                        {"predicted_yield": predicted, "unit": "q/ha"})


def test_total_advantage_present_when_yield_and_area_resolve(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility={"name": "X", "km": 22.0},
           assured={"available": True, "msp": 2425, "basis": "MSP",
                    "premium_pct": 5, "processor_price": 2546.25},
           mandi_rows=[{"is_best_net": True, "net_price": 2270.0, "market": "Patna",
                        "distance_km": 60.0, "modal_price": 2300, "transport_per_q": 30.0}])
    _patch_yield(monkeypatch, 35)
    out = cc.compare_channels("wheat", 25.6, 85.1, area_ha=2.0,
                              state="Bihar", district="Patna", season="rabi", year=2024)
    ta = out["total_advantage"]
    assert ta["estimate"] is True
    assert ta["yield_q_per_ha"] == 35
    assert ta["value"] == round(out["margin_per_q"] * 35 * 2.0, 2)


def test_total_advantage_omitted_when_yield_none(monkeypatch):
    _patch(monkeypatch,
           gated={"wheat": "flour_mill"},
           facility={"name": "X", "km": 22.0},
           assured={"available": True, "msp": 2425, "basis": "MSP",
                    "premium_pct": 5, "processor_price": 2546.25},
           mandi_rows=[{"is_best_net": True, "net_price": 2270.0, "market": "Patna",
                        "distance_km": 60.0, "modal_price": 2300, "transport_per_q": 30.0}])
    _patch_yield(monkeypatch, None)
    out = cc.compare_channels("wheat", 25.6, 85.1, area_ha=2.0,
                              state="Bihar", district="Patna", season="rabi", year=2024)
    assert out["total_advantage"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_channel_compare.py -p no:cacheprovider -q`
Expected: FAIL — `AttributeError: module 'analysis.channel_compare' has no attribute 'predict_yield'` (and total_advantage stays None).

- [ ] **Step 3: Implement the total**

In `backend/analysis/channel_compare.py`, add the import near the top:

```python
from analysis.yield_predict import predict_yield
```

Then in `compare_channels`, replace the `return { ... "total_advantage": None, ... }` block with a computed total before the return:

```python
    total = None
    if (margin is not None and area_ha and state and season is not None):
        y = predict_yield(state, district, season, crop, year or 2024)
        yq = y.get("predicted_yield")
        if yq:
            total = {"area_ha": area_ha, "yield_q_per_ha": yq,
                     "value": round(margin * yq * area_ha, 2), "estimate": True}

    return {
        "crop": crop, "processor": proc, "mandi": mandi,
        "winner": winner, "margin_per_q": margin, "total_advantage": total,
        "explanation": _explain(crop, proc, mandi, winner),
    }
```

(Delete the old `return` that set `total_advantage` to `None`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_channel_compare.py -p no:cacheprovider -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/channel_compare.py backend/tests/test_channel_compare.py
git commit -m "feat: optional total-rupee advantage via yield model"
```

---

## Task 4: `/compare/channels` API router

**Files:**
- Create: `backend/api/compare.py`
- Modify: `backend/main.py` (router registration, ~lines 21-28)
- Test: `backend/tests/test_api_compare.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_api_compare.py`:

```python
from fastapi.testclient import TestClient
import api.compare as compare_api
from main import app

client = TestClient(app)


def test_missing_coords_returns_400():
    r = client.get("/api/compare/channels", params={"crop": "wheat"})
    assert r.status_code == 400


def test_happy_path_returns_payload(monkeypatch):
    monkeypatch.setattr(compare_api, "compare_channels",
                        lambda *a, **k: {"crop": "wheat", "winner": "processor",
                                         "margin_per_q": 265.0, "processor": {"available": True},
                                         "mandi": {"available": True}, "total_advantage": None,
                                         "explanation": "ok"})
    r = client.get("/api/compare/channels",
                   params={"crop": "wheat", "lat": 25.6, "lon": 85.1, "area": 2.0})
    assert r.status_code == 200
    assert r.json()["winner"] == "processor"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_api_compare.py -p no:cacheprovider -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.compare'`.
(Note: `TestClient`/`app` import touches the DB layer; if it errors on a missing Postgres, start Docker `docker compose up -d` first — this is the one task that needs the app to import.)

- [ ] **Step 3: Implement the router**

Create `backend/api/compare.py`:

```python
from fastapi import APIRouter, Query, HTTPException
from analysis.channel_compare import compare_channels

router = APIRouter()


@router.get("/compare/channels")
def compare_channels_endpoint(
    crop: str = Query(...),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    area: float | None = Query(None),
    state: str | None = Query(None),
    district: str | None = Query(None),
    season: str | None = Query(None),
    year: int | None = Query(None),
):
    if lat is None or lon is None:
        raise HTTPException(status_code=400,
                            detail="lat and lon are required for a channel comparison")
    return compare_channels(crop, lat, lon, area_ha=area, state=state,
                            district=district, season=season, year=year)
```

- [ ] **Step 4: Register the router in `backend/main.py`**

Add the import alongside the other `from api import ...` lines, and after the existing `app.include_router(mandi.router, prefix="/api")` (line ~28) add:

```python
app.include_router(compare.router, prefix="/api")
```

Make sure `compare` is in the `from api import (...)` import block at the top.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_api_compare.py -p no:cacheprovider -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/api/compare.py backend/main.py backend/tests/test_api_compare.py
git commit -m "feat: /compare/channels API endpoint"
```

---

## Task 5: Recommender boost in `fusion.py`

**Files:**
- Modify: `backend/analysis/fusion.py` (gate block, lines ~169-201)
- Test: `backend/tests/test_fusion_boost.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_fusion_boost.py`:

```python
import analysis.fusion as fusion
from analysis.fusion import apply_processor_boost, BOOST_CAP


def test_boost_lifts_score_when_processor_wins(monkeypatch):
    monkeypatch.setattr(fusion, "compare_channels", lambda crop, lat, lon: {
        "winner": "processor", "margin_per_q": 300.0,
        "mandi": {"available": True, "net_price": 2270.0},
        "processor": {"available": True, "facility": "X Mill", "distance_km": 20.0},
    })
    new_score, note = apply_processor_boost("wheat", 0.50, 25.6, 85.1)
    assert new_score > 0.50
    assert new_score <= 0.50 * (1 + BOOST_CAP) + 1e-9
    assert "grow-for-industry" in note


def test_no_boost_when_mandi_wins(monkeypatch):
    monkeypatch.setattr(fusion, "compare_channels", lambda crop, lat, lon: {
        "winner": "mandi", "margin_per_q": -100.0,
        "mandi": {"available": True, "net_price": 2400.0},
        "processor": {"available": True, "net_price": 2300.0},
    })
    new_score, note = apply_processor_boost("wheat", 0.50, 25.6, 85.1)
    assert new_score == 0.50
    assert note is None


def test_boost_is_capped(monkeypatch):
    monkeypatch.setattr(fusion, "compare_channels", lambda crop, lat, lon: {
        "winner": "processor", "margin_per_q": 99999.0,
        "mandi": {"available": True, "net_price": 100.0},
        "processor": {"available": True, "facility": "X", "distance_km": 5.0},
    })
    new_score, _ = apply_processor_boost("wheat", 0.50, 25.6, 85.1)
    assert new_score == round(0.50 * (1 + BOOST_CAP), 4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_fusion_boost.py -p no:cacheprovider -q`
Expected: FAIL — `ImportError: cannot import name 'apply_processor_boost'`.

- [ ] **Step 3: Implement the boost helper**

In `backend/analysis/fusion.py`, add the import near the other analysis imports (line ~36):

```python
from analysis.channel_compare import compare_channels
```

Add the constant near the top (by `SOFT_FLOOR`/weights, ~line 49):

```python
BOOST_CAP = 0.15  # max +15% ranking uplift when a processor channel out-pays the mandi
```

Add the helper (place it above `recommend()`):

```python
def apply_processor_boost(crop, score, lat, lon):
    """Return (boosted_score, positive_note|None). Bounded uplift when the crop's
    processor channel out-pays the mandi; otherwise unchanged. Pure given
    compare_channels (which is monkeypatched in tests)."""
    cmp = compare_channels(crop, lat, lon)
    if cmp.get("winner") != "processor" or not cmp.get("margin_per_q"):
        return score, None
    mandi = cmp["mandi"]
    ref = mandi["net_price"] if mandi.get("available") and mandi["net_price"] else cmp["margin_per_q"]
    norm = min(1.0, max(0.0, cmp["margin_per_q"] / ref)) if ref else 1.0
    boosted = round(score * (1 + BOOST_CAP * norm), 4)
    proc = cmp["processor"]
    note = (f"a {proc['facility']} is {proc['distance_km']} km away and pays "
            f"~Rs.{cmp['margin_per_q']:.0f}/q more than the mandi — "
            f"strong grow-for-industry option")
    return boosted, note
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_fusion_boost.py -p no:cacheprovider -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire the helper into the gate block**

In `recommend()`, inside the `if coords and coords[0] is not None ...` gate loop (lines ~174-185), after the proximity-factor down-weight and before `gated.append(...)`, add the uplift for gated crops and collect notes. Insert a `boost_notes = {}` dict just before the `for c, score, breakdown in scored:` loop, and inside the loop, after the existing `score = round(score * factor, 4)` line, add:

```python
                if factor >= 1.0:  # facility is near; reward only when it out-pays mandi
                    score, note = apply_processor_boost(c, score, coords[0], coords[1])
                    if note:
                        boost_notes[c] = note
```

Then after the recommendations are built (after the `for rec in recommendations:` caution loop, ~line 201), add:

```python
    for rec in recommendations:
        if rec["crop"] in boost_notes:
            rec.setdefault("highlights", []).append(boost_notes[rec["crop"]])
```

- [ ] **Step 6: Run the full gate/fusion tests to verify no regression**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_fusion_boost.py tests/test_fusion_gate.py tests/test_demand_gate.py -p no:cacheprovider -q`
Expected: PASS (Phase-1 gate behavior unchanged; boost tests green). If `test_fusion_gate.py` touches the DB, start Docker first.

- [ ] **Step 7: Commit**

```bash
git add backend/analysis/fusion.py backend/tests/test_fusion_boost.py
git commit -m "feat: bounded recommender boost when processor channel out-pays mandi"
```

---

## Task 6: Frontend comparison card

**Files:**
- Modify: `frontend/src/api/client.js`
- Create: `frontend/src/workspace/ChannelCompareCard.jsx`
- Modify: the workspace results view that renders per-crop detail (locate with the grep in Step 1)

> No JS unit-test harness exists in this project; verification is a live Arc smoke (per the browser-testing rule). Keep the component presentational and driven entirely by the API payload.

- [ ] **Step 1: Locate the workspace mount point**

Run: `cd frontend && grep -rn "client" src/workspace src/pages/CropAdvisor.jsx | head` and open the file that renders a selected recommendation's detail. The card mounts there, receiving the selected `{crop, lat, lon, state, district, season}`.

- [ ] **Step 2: Add the API call**

In `frontend/src/api/client.js`, after the `api` instance is created, add:

```javascript
export const compareChannels = (params) =>
  api.get('/compare/channels', { params }).then((r) => r.data)
```

- [ ] **Step 3: Build the card**

Create `frontend/src/workspace/ChannelCompareCard.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { compareChannels } from '../api/client'

const fmt = (n) => (n == null ? '—' : `₹${Math.round(n).toLocaleString('en-IN')}`)

function Channel({ title, data, win }) {
  if (!data?.available) {
    return (
      <div className="cc-col cc-unavailable">
        <h4>{title}</h4>
        <p className="cc-reason">{data?.reason || 'unavailable'}</p>
      </div>
    )
  }
  return (
    <div className={`cc-col${win ? ' cc-win' : ''}`}>
      <h4>{title}{win ? ' ✓' : ''}</h4>
      <div className="cc-line">Price {fmt(data.processor_price ?? data.modal_price)}</div>
      <div className="cc-line">− transport {fmt(data.transport_per_q)}</div>
      <div className="cc-net">Net {fmt(data.net_price)}/q</div>
      {data.premium_pct != null && (
        <div className="cc-note">incl. est. {data.premium_pct}% premium</div>
      )}
    </div>
  )
}

export default function ChannelCompareCard({ crop, lat, lon, state, district, season, area }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!crop || lat == null || lon == null) return
    setData(null); setErr(null)
    compareChannels({ crop, lat, lon, state, district, season, area })
      .then(setData)
      .catch(() => setErr('Comparison unavailable'))
  }, [crop, lat, lon, state, district, season, area])

  if (err) return <div className="cc-card">{err}</div>
  if (!data) return <div className="cc-card">Comparing channels…</div>

  return (
    <div className="cc-card">
      <p className="cc-explain">{data.explanation}</p>
      <div className="cc-cols">
        <Channel title="Sell to processor" data={data.processor} win={data.winner === 'processor'} />
        <Channel title="Sell at mandi" data={data.mandi} win={data.winner === 'mandi'} />
      </div>
      {data.total_advantage && (
        <p className="cc-total">
          Est. advantage on {data.total_advantage.area_ha} ha: {fmt(data.total_advantage.value)}
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Mount the card**

Import and render `<ChannelCompareCard {...selectedCropContext} />` in the results-detail file found in Step 1, passing the selected crop + resolved location. Match the surrounding Warm-Editorial classnames; the `cc-*` classes can map to existing token utilities or a small scoped block — do not introduce a new design system.

- [ ] **Step 5: Live Arc smoke**

Run the frontend (`cd frontend && npm run dev`) with Docker + backend up. In **Arc**, open the workspace, pick a crop in a mill-district location (expect processor wins, premium labeled) and a no-facility location (expect mandi wins / processor greyed with reason). Confirm no ₹0 fabrication.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.js frontend/src/workspace/ChannelCompareCard.jsx <mount-file>
git commit -m "feat: channel comparison card in workspace"
```

---

## Final verification

- [ ] With Docker up, run the backend suite: `cd backend && venv/Scripts/python.exe -m pytest tests/ -p no:cacheprovider -q` — expect all green (existing + new).
- [ ] Merge `feat/channel-engine` → master (fast-forward / no-ff per preference).
- [ ] Hand off to user for the deferred deploy (Vercel + Render + Neon).

---

## Deferred (not in this plan)

- FPO collective as a third channel (Approach B).
- Deploy: frontend → Vercel, FastAPI → Render, Postgres → Neon with data migrated up.
