# FPO Collective-Selling Decision Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stateless engine + API + dashboard that tells an FPO manager whether pooling members' harvest and trucking it together earns more than each farmer selling alone, and by how much (`extra_income`), using only real `mandi_prices` + distances + an editable truck cost.

**Architecture:** A pure engine (`analysis/fpo_bulk.py`) reuses `price_source.get_market_prices(rate_per_km=0)` to pull each market's modal price + distance, then applies its own truck-amortization math. A thin FastAPI adapter (`api/fpo.py`) validates input and serializes the engine's result. A React page (`pages/FpoBulkDashboard.jsx`) under the "Where & when to sell" workspace tab collects farmer rows + transport config and renders the plan.

**Tech Stack:** Python 3.10 / FastAPI / Pydantic v2 / pytest (`-p no:asyncio`) / PostgreSQL 16 (Docker); React 19 + Vite + Tailwind + axios.

**Spec:** `docs/superpowers/specs/2026-06-03-fpo-bulk-selling-design.md`

**Conventions (in force for every task):**
- Tests run from `backend/`: `venv\Scripts\python.exe -m pytest -p no:asyncio ...`
- Targeted `git add <paths>` only — never `-A`/`.`/`-u`. Never stage the large CSVs or `data/agri.db`.
- Commit trailer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Docker Postgres must be up for API tests (engine tests monkeypatch the DB away).
- Branch: `feat/fpo-bulk-selling` (already created; the spec is committed there).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/analysis/fpo_bulk.py` (create) | Pure engine: `TransportConfig`, geometry helpers, individual baseline, aggregated truck plan, `plan_bulk_sale` orchestrator. No HTTP, no React, no DB writes. |
| `backend/tests/test_fpo_bulk.py` (create) | Exhaustive engine unit tests; monkeypatches `analysis.fpo_bulk.get_market_prices`. |
| `backend/api/fpo.py` (create) | `POST /api/fpo/bulk-plan`: Pydantic validation + serialization only. |
| `backend/tests/test_fpo_api.py` (create) | API tests via FastAPI `TestClient`. |
| `backend/main.py` (modify) | Register the `fpo` router. |
| `frontend/src/api/client.js` (modify) | Add `fpoBulkPlan(body)`. |
| `frontend/src/pages/FpoBulkDashboard.jsx` (create) | Farmer table + transport config + results panel. |
| `frontend/src/workspace/Workspace.jsx` (modify) | Add the dashboard as a tool under the "sell" intent. |

---

## Task 1: Engine scaffold — `TransportConfig` + geometry helpers

**Files:**
- Create: `backend/analysis/fpo_bulk.py`
- Test: `backend/tests/test_fpo_bulk.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fpo_bulk.py
import math
import pytest
from analysis.fpo_bulk import TransportConfig, _centroid, _max_pairwise_km


def test_transport_config_defaults():
    cfg = TransportConfig()
    assert cfg.truck_capacity_q == 100.0
    assert cfg.fixed_hire_per_truck == 2000.0
    assert cfg.per_km_per_truck == 30.0
    assert cfg.per_q_local_rate == 2.0


def test_centroid_is_mean_of_points():
    farmers = [{"lat": 10.0, "lon": 20.0}, {"lat": 12.0, "lon": 24.0}]
    lat, lon = _centroid(farmers)
    assert lat == 11.0
    assert lon == 22.0


def test_max_pairwise_km_zero_for_identical_points():
    farmers = [{"lat": 10.0, "lon": 20.0}, {"lat": 10.0, "lon": 20.0}]
    assert _max_pairwise_km(farmers) == 0.0


def test_max_pairwise_km_positive_for_spread():
    # Punjab-ish to Tamil-Nadu-ish: should be well over 1000 km
    farmers = [{"lat": 31.0, "lon": 75.0}, {"lat": 11.0, "lon": 78.0}]
    assert _max_pairwise_km(farmers) > 1000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.fpo_bulk'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/analysis/fpo_bulk.py
"""FPO collective-selling engine: does pooling + trucking a group's harvest
beat each farmer selling alone? Pure arithmetic on real mandi_prices +
distances + an editable truck cost (fixed hire + per-km). No invented
premium. Stateless — no DB writes, no HTTP, no React."""
from dataclasses import dataclass
from math import ceil
from analysis.geo import haversine
from analysis.price_source import get_market_prices

SPREAD_THRESHOLD_KM = 200.0


@dataclass
class TransportConfig:
    truck_capacity_q: float = 100.0       # quintals per truckload (~10 tonnes)
    fixed_hire_per_truck: float = 2000.0  # flat hire per truck (Rs)
    per_km_per_truck: float = 30.0        # Rs per km per truck
    per_q_local_rate: float = 2.0         # Rs per quintal per km (individual)


def _centroid(farmers):
    """Mean (lat, lon) of the farmer locations — proxy for the FPO hub."""
    n = len(farmers)
    return (sum(f["lat"] for f in farmers) / n,
            sum(f["lon"] for f in farmers) / n)


def _max_pairwise_km(farmers):
    """Largest great-circle distance between any two members."""
    d = 0.0
    for i in range(len(farmers)):
        for j in range(i + 1, len(farmers)):
            d = max(d, haversine(farmers[i]["lat"], farmers[i]["lon"],
                                 farmers[j]["lat"], farmers[j]["lon"]))
    return d
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/fpo_bulk.py backend/tests/test_fpo_bulk.py
git commit -m "feat: FPO engine scaffold — TransportConfig + geometry helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Individual baseline — best net per farmer at a per-quintal rate

**Files:**
- Modify: `backend/analysis/fpo_bulk.py`
- Test: `backend/tests/test_fpo_bulk.py`

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_fpo_bulk.py
from analysis.fpo_bulk import _individual_revenue


def test_individual_picks_best_net_at_per_q_rate():
    # rate=3 Rs/q/km. near: 1000-30=970; far: 1200-300=900 -> near wins.
    markets = [
        {"market": "Near", "district": "D1", "state": "S", "modal_price": 1000, "distance_km": 10},
        {"market": "Far", "district": "D2", "state": "S", "modal_price": 1200, "distance_km": 100},
    ]
    rev, chosen = _individual_revenue({"quantity_q": 50}, markets, per_q_local_rate=3.0)
    assert chosen["market"] == "Near"
    assert rev == 50 * (1000 - 10 * 3.0)   # 48500


def test_individual_skips_markets_without_distance():
    markets = [{"market": "NoLoc", "district": "D", "state": "S", "modal_price": 9999, "distance_km": None}]
    rev, chosen = _individual_revenue({"quantity_q": 10}, markets, per_q_local_rate=2.0)
    assert chosen is None
    assert rev == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py::test_individual_picks_best_net_at_per_q_rate -v`
Expected: FAIL — `ImportError: cannot import name '_individual_revenue'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to backend/analysis/fpo_bulk.py
def _individual_revenue(farmer, markets, per_q_local_rate):
    """Best net revenue for one farmer's lot, carried at a per-quintal local
    rate (no fixed cost). Returns (revenue, chosen_market_or_None)."""
    q = farmer["quantity_q"]
    best = None
    for m in markets:
        d = m["distance_km"]
        if d is None:
            continue
        net = q * (m["modal_price"] - d * per_q_local_rate)
        if best is None or net > best[0]:
            best = (net, m)
    if best is None:
        return 0.0, None
    return best[0], best[1]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/fpo_bulk.py backend/tests/test_fpo_bulk.py
git commit -m "feat: FPO individual baseline (best net at per-quintal rate)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Aggregated plan — truck-amortized best net for the pooled load

**Files:**
- Modify: `backend/analysis/fpo_bulk.py`
- Test: `backend/tests/test_fpo_bulk.py`

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_fpo_bulk.py
from analysis.fpo_bulk import _aggregated_plan


def test_aggregated_reaches_farther_premium_mandi():
    cfg = TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                          per_km_per_truck=30, per_q_local_rate=3.0)
    markets = [
        {"market": "Near", "district": "D1", "state": "S", "modal_price": 1000, "distance_km": 10},
        {"market": "Far", "district": "D2", "state": "S", "modal_price": 1200, "distance_km": 100},
    ]
    plan = _aggregated_plan(markets, total_q=100, cfg=cfg)
    # Far: 100*1200 - 1*(2000 + 100*30) = 120000 - 5000 = 115000
    assert plan["market"] == "Far"
    assert plan["trucks"] == 1
    assert plan["transport_cost"] == 5000.0
    assert plan["revenue"] == 115000.0


def test_aggregated_truck_count_scales_with_quantity():
    cfg = TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                          per_km_per_truck=30)
    markets = [{"market": "M", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 50}]
    plan = _aggregated_plan(markets, total_q=250, cfg=cfg)  # ceil(250/100)=3
    assert plan["trucks"] == 3
    assert plan["transport_cost"] == 3 * (2000 + 50 * 30)   # 10500


def test_aggregated_returns_none_when_no_located_market():
    cfg = TransportConfig()
    markets = [{"market": "X", "district": "D", "state": "S", "modal_price": 1000, "distance_km": None}]
    assert _aggregated_plan(markets, total_q=100, cfg=cfg) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py::test_aggregated_reaches_farther_premium_mandi -v`
Expected: FAIL — `ImportError: cannot import name '_aggregated_plan'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to backend/analysis/fpo_bulk.py
def _aggregated_plan(markets, total_q, cfg):
    """Best net revenue for the pooled load, trucked (fixed hire + per-km).
    Returns a plan dict, or None if no market has a usable distance."""
    trucks = ceil(total_q / cfg.truck_capacity_q)
    best = None
    for m in markets:
        d = m["distance_km"]
        if d is None:
            continue
        cost = trucks * (cfg.fixed_hire_per_truck + d * cfg.per_km_per_truck)
        net = total_q * m["modal_price"] - cost
        if best is None or net > best[0]:
            best = (net, m, cost)
    if best is None:
        return None
    net, m, cost = best
    return {
        "revenue": round(net, 2),
        "market": m["market"], "district": m["district"], "state": m["state"],
        "modal_price": m["modal_price"], "distance_km": m["distance_km"],
        "trucks": trucks, "transport_cost": round(cost, 2),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/fpo_bulk.py backend/tests/test_fpo_bulk.py
git commit -m "feat: FPO aggregated truck-amortized plan

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `plan_bulk_sale` orchestrator — extra_income, caching, spread, honest loss

**Files:**
- Modify: `backend/analysis/fpo_bulk.py`
- Test: `backend/tests/test_fpo_bulk.py`

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_fpo_bulk.py
import analysis.fpo_bulk as fpo


def _patch_markets(monkeypatch, markets, source="mandi", crop="testcrop"):
    """Replace get_market_prices with a stub that ignores coords and records
    the top_k it was called with. Returns a calls list (one entry per call)."""
    calls = []

    def stub(crop_arg, lat=None, lon=None, state=None, rate_per_km=0.0, top_k=10):
        calls.append({"lat": lat, "lon": lon, "top_k": top_k})
        return {"source": source, "markets": markets, "crop": crop}

    monkeypatch.setattr(fpo, "get_market_prices", stub)
    return calls


def test_extra_income_is_exact_arithmetic_core_win(monkeypatch):
    markets = [
        {"market": "Near", "district": "D1", "state": "S", "modal_price": 1000, "distance_km": 10},
        {"market": "Far", "district": "D2", "state": "S", "modal_price": 1200, "distance_km": 100},
    ]
    _patch_markets(monkeypatch, markets)
    cfg = fpo.TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                              per_km_per_truck=30, per_q_local_rate=3.0)
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50},
               {"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50}]
    res = fpo.plan_bulk_sale("testcrop", farmers, cfg)
    # individuals pick Near: 50*(1000-30)=48500 each -> baseline 97000
    # aggregated picks Far: 115000 -> extra 18000
    assert res["price_basis"] == "mandi"
    assert res["baseline"] == 97000.0
    assert res["aggregated_rev"] == 115000.0
    assert res["extra_income"] == 18000.0
    assert res["chosen_mandi"]["market"] == "Far"
    assert all(f["best_market"] == "Near" for f in res["per_farmer"])


def test_honest_loss_when_pooling_does_not_help(monkeypatch):
    # only a near market; small quantities -> truck fixed cost dominates
    markets = [{"market": "Near", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    _patch_markets(monkeypatch, markets)
    cfg = fpo.TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                              per_km_per_truck=30, per_q_local_rate=3.0)
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 5},
               {"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 5}]
    res = fpo.plan_bulk_sale("testcrop", farmers, cfg)
    # baseline 2*5*970=9700 ; aggregated 10*1000-2300=7700 ; extra -2000
    assert res["extra_income"] == -2000.0
    assert "locally" in res["message"].lower()


def test_single_farmer_pooling_has_no_benefit(monkeypatch):
    markets = [{"market": "Near", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    _patch_markets(monkeypatch, markets)
    cfg = fpo.TransportConfig(truck_capacity_q=100, fixed_hire_per_truck=2000,
                              per_km_per_truck=30, per_q_local_rate=3.0)
    res = fpo.plan_bulk_sale("testcrop", [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50}], cfg)
    assert res["extra_income"] < 0


def test_spread_warning_triggers_beyond_threshold(monkeypatch):
    markets = [{"market": "Near", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    _patch_markets(monkeypatch, markets)
    farmers = [{"lat": 31.0, "lon": 75.0, "state": "Punjab", "quantity_q": 50},
               {"lat": 11.0, "lon": 78.0, "state": "Tamil Nadu", "quantity_q": 50}]
    res = fpo.plan_bulk_sale("testcrop", farmers)
    assert res["spread_warning"] is not None


def test_market_lookup_is_cached_per_rounded_coord(monkeypatch):
    markets = [{"market": "Near", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    calls = _patch_markets(monkeypatch, markets)
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 10} for _ in range(5)]
    fpo.plan_bulk_sale("testcrop", farmers)
    # 5 identical coords + their identical centroid share one cache key -> 1 call
    assert len(calls) == 1


def test_engine_requests_full_market_list_not_nearest_few(monkeypatch):
    markets = [{"market": "M", "district": "D", "state": "S", "modal_price": 1000, "distance_km": 10}]
    calls = _patch_markets(monkeypatch, markets)
    fpo.plan_bulk_sale("testcrop", [{"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 10}])
    # high top_k so a farther premium mandi is never truncated away
    assert all(c["top_k"] >= 100 for c in calls)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py::test_extra_income_is_exact_arithmetic_core_win -v`
Expected: FAIL — `AttributeError: module 'analysis.fpo_bulk' has no attribute 'plan_bulk_sale'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to backend/analysis/fpo_bulk.py
def _make_market_fetcher(crop):
    """Cache candidate markets per rounded (lat, lon) within one request so a
    village of farmers triggers one DB lookup, not one per farmer. top_k is
    large so a farther, higher-priced mandi is never truncated away (see spec)."""
    cache = {}

    def fetch(lat, lon, state):
        key = (round(lat, 2), round(lon, 2))
        if key not in cache:
            cache[key] = get_market_prices(crop, lat=lat, lon=lon, state=state,
                                           rate_per_km=0, top_k=200)
        return cache[key]

    return fetch


def plan_bulk_sale(crop, farmers, cfg=None):
    """Compare pooled+trucked selling against each farmer selling alone.

    farmers: list of {lat, lon, state, quantity_q}.
    Returns a plan dict with baseline, aggregated_rev, extra_income (all None
    when distance optimization isn't possible), chosen_mandi, per_farmer,
    price_basis, spread_warning, and a human-readable message."""
    cfg = cfg or TransportConfig()
    fetch = _make_market_fetcher(crop)

    origin_lat, origin_lon = _centroid(farmers)
    state = next((f.get("state") for f in farmers if f.get("state")), None)
    origin = fetch(origin_lat, origin_lon, state)
    basis = origin["source"]
    crop_name = origin["crop"]
    total_q = sum(f["quantity_q"] for f in farmers)

    if basis != "mandi":
        msg = ("Only a state-level average is available for this crop — "
               "distance-based pooling can't be computed."
               if basis == "state_fallback"
               else "No market or state price data for this crop.")
        return {
            "crop": crop_name, "price_basis": basis, "total_q": round(total_q, 2),
            "baseline": None, "aggregated_rev": None, "extra_income": None,
            "chosen_mandi": None, "per_farmer": [], "spread_warning": None,
            "message": msg,
        }

    baseline = 0.0
    per_farmer = []
    for f in farmers:
        markets = fetch(f["lat"], f["lon"], f.get("state"))["markets"]
        rev, m = _individual_revenue(f, markets, cfg.per_q_local_rate)
        baseline += rev
        per_farmer.append({
            "lat": f["lat"], "lon": f["lon"], "quantity_q": f["quantity_q"],
            "best_market": m["market"] if m else None, "revenue": round(rev, 2),
        })

    agg = _aggregated_plan(origin["markets"], total_q, cfg)
    aggregated_rev = agg["revenue"] if agg else None
    extra = round(aggregated_rev - baseline, 2) if agg else None

    spread = _max_pairwise_km(farmers)
    spread_warning = (
        f"Members span ~{round(spread)} km — likely too far to pool into one "
        "truck; treat this plan as optimistic."
        if spread > SPREAD_THRESHOLD_KM else None
    )

    if extra is None:
        msg = "No located market found for this crop."
    elif extra <= 0:
        msg = "Pooling doesn't beat selling locally here — members should sell individually."
    else:
        msg = f"Pooling to {agg['market']} earns the group Rs {extra} more than selling alone."

    return {
        "crop": crop_name, "price_basis": basis, "total_q": round(total_q, 2),
        "baseline": round(baseline, 2), "aggregated_rev": aggregated_rev,
        "extra_income": extra, "chosen_mandi": agg, "per_farmer": per_farmer,
        "spread_warning": spread_warning, "message": msg,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py -v`
Expected: PASS (15 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/fpo_bulk.py backend/tests/test_fpo_bulk.py
git commit -m "feat: FPO plan_bulk_sale orchestrator (extra_income, caching, spread guard)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: State-fallback & no-price handling

**Files:**
- Test: `backend/tests/test_fpo_bulk.py` (logic already implemented in Task 4; this task locks it with tests)

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_fpo_bulk.py
def test_state_fallback_crop_skips_optimization(monkeypatch):
    _patch_markets(monkeypatch, markets=[], source="state_fallback", crop="bajra")
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "Punjab", "quantity_q": 50}]
    res = fpo.plan_bulk_sale("bajra", farmers)
    assert res["price_basis"] == "state_fallback"
    assert res["extra_income"] is None
    assert res["aggregated_rev"] is None
    assert res["chosen_mandi"] is None
    assert "state-level" in res["message"].lower()


def test_no_price_data_returns_clean_message(monkeypatch):
    _patch_markets(monkeypatch, markets=[], source="none", crop="unobtanium")
    farmers = [{"lat": 30.0, "lon": 75.0, "state": "Punjab", "quantity_q": 50}]
    res = fpo.plan_bulk_sale("unobtanium", farmers)
    assert res["price_basis"] == "none"
    assert res["extra_income"] is None
    assert "no market" in res["message"].lower()
```

- [ ] **Step 2: Run test to verify it fails OR passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py -k "fallback or no_price" -v`
Expected: These should PASS immediately (the branch was implemented in Task 4). If either fails, fix `plan_bulk_sale`'s non-`mandi` branch until both pass. This task exists to guarantee the honest-degradation behavior is covered.

- [ ] **Step 3: (only if a test failed) adjust the fallback branch**

No new code expected. If `test_no_price_data_returns_clean_message` fails on the message assertion, confirm the `else` message contains "No market".

- [ ] **Step 4: Run the full engine suite**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_bulk.py -v`
Expected: PASS (17 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_fpo_bulk.py
git commit -m "test: FPO honest degradation (state-fallback & no-price crops)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: API endpoint — `POST /api/fpo/bulk-plan`

**Files:**
- Create: `backend/api/fpo.py`
- Modify: `backend/main.py:5` (import) and `backend/main.py:29` (register router)
- Test: `backend/tests/test_fpo_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fpo_api.py
from fastapi.testclient import TestClient
import analysis.fpo_bulk as fpo
from main import app

client = TestClient(app)


def _stub_markets(monkeypatch, markets, source="mandi", crop="wheat"):
    def stub(crop_arg, lat=None, lon=None, state=None, rate_per_km=0.0, top_k=10):
        return {"source": source, "markets": markets, "crop": crop}
    monkeypatch.setattr(fpo, "get_market_prices", stub)


def test_bulk_plan_returns_expected_keys(monkeypatch):
    markets = [
        {"market": "Near", "district": "D1", "state": "S", "modal_price": 1000, "distance_km": 10},
        {"market": "Far", "district": "D2", "state": "S", "modal_price": 1200, "distance_km": 100},
    ]
    _stub_markets(monkeypatch, markets)
    body = {
        "crop": "wheat",
        "farmers": [
            {"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50},
            {"lat": 30.0, "lon": 75.0, "state": "S", "quantity_q": 50},
        ],
        "transport": {"truck_capacity_q": 100, "fixed_hire_per_truck": 2000,
                      "per_km_per_truck": 30, "per_q_local_rate": 3.0},
    }
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 200
    data = r.json()
    for key in ("baseline", "aggregated_rev", "extra_income", "price_basis", "chosen_mandi"):
        assert key in data
    assert data["extra_income"] == 18000.0


def test_missing_coords_is_422():
    body = {"crop": "wheat", "farmers": [{"state": "S", "quantity_q": 50}]}
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 422


def test_non_positive_quantity_is_422():
    body = {"crop": "wheat", "farmers": [{"lat": 30.0, "lon": 75.0, "quantity_q": 0}]}
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 422


def test_empty_farmer_list_is_422():
    body = {"crop": "wheat", "farmers": []}
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 422


def test_state_fallback_crop_returns_200_with_flag(monkeypatch):
    _stub_markets(monkeypatch, markets=[], source="state_fallback", crop="bajra")
    body = {"crop": "bajra", "farmers": [{"lat": 30.0, "lon": 75.0, "state": "Punjab", "quantity_q": 50}]}
    r = client.post("/api/fpo/bulk-plan", json=body)
    assert r.status_code == 200
    assert r.json()["price_basis"] == "state_fallback"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_api.py -v`
Expected: FAIL — 404 on the POST (route not registered) / collection error.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/api/fpo.py
from fastapi import APIRouter
from pydantic import BaseModel, Field
from analysis.fpo_bulk import plan_bulk_sale, TransportConfig

router = APIRouter()


class Farmer(BaseModel):
    lat: float
    lon: float
    state: str | None = None
    quantity_q: float = Field(gt=0)


class TransportIn(BaseModel):
    truck_capacity_q: float = Field(100.0, gt=0)
    fixed_hire_per_truck: float = Field(2000.0, ge=0)
    per_km_per_truck: float = Field(30.0, ge=0)
    per_q_local_rate: float = Field(2.0, ge=0)


class BulkPlanRequest(BaseModel):
    crop: str
    farmers: list[Farmer] = Field(min_length=1)
    transport: TransportIn = TransportIn()


@router.post("/fpo/bulk-plan")
def fpo_bulk_plan(req: BulkPlanRequest):
    cfg = TransportConfig(**req.transport.model_dump())
    farmers = [f.model_dump() for f in req.farmers]
    return plan_bulk_sale(req.crop, farmers, cfg)
```

Then register the router in `backend/main.py`:

```python
# line 5: add `fpo` to the existing import
from api import states, crops, trends, revenue, forecast, recommend, profit, mandi, geo, fpo
```

```python
# after line 29 (app.include_router(geo.router, prefix="/api")) add:
app.include_router(fpo.router, prefix="/api")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fpo_api.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/api/fpo.py backend/main.py backend/tests/test_fpo_api.py
git commit -m "feat: POST /api/fpo/bulk-plan endpoint + validation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Frontend — `FpoBulkDashboard` under the "sell" tab

**Files:**
- Modify: `frontend/src/api/client.js` (add `fpoBulkPlan`)
- Create: `frontend/src/pages/FpoBulkDashboard.jsx`
- Modify: `frontend/src/workspace/Workspace.jsx` (import + add tool to `sell` intent)

Note: the repo has no JS test harness; this task is verified live against the dev server.

- [ ] **Step 1: Add the API client function**

In `frontend/src/api/client.js`, after the `compareMandis` line, add:

```javascript
export const fpoBulkPlan       = (body) => api.post('/fpo/bulk-plan', body).then(r => r.data)
```

- [ ] **Step 2: Create the dashboard page**

```jsx
// frontend/src/pages/FpoBulkDashboard.jsx
import { useState } from 'react'
import { fpoBulkPlan } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'

const DEFAULT_TRANSPORT = {
  truck_capacity_q: 100, fixed_hire_per_truck: 2000,
  per_km_per_truck: 30, per_q_local_rate: 2,
}

export default function FpoBulkDashboard() {
  const { crop, state, lat, lon } = useWorkspace()
  const firstRow = {
    lat: lat ?? '', lon: lon ?? '', state: state || '', quantity_q: '',
  }
  const [rows, setRows] = useState([firstRow])
  const [transport, setTransport] = useState(DEFAULT_TRANSPORT)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const setRow = (i, key, val) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [key]: val } : r)))
  const addRow = () => setRows((rs) => [...rs, { lat: '', lon: '', state: state || '', quantity_q: '' }])
  const removeRow = (i) => setRows((rs) => rs.filter((_, j) => j !== i))
  const setT = (key, val) => setTransport((t) => ({ ...t, [key]: val }))

  const submit = async () => {
    setError(null)
    try {
      const farmers = rows.map((r) => ({
        lat: Number(r.lat), lon: Number(r.lon),
        state: r.state || null, quantity_q: Number(r.quantity_q),
      }))
      const body = {
        crop,
        farmers,
        transport: Object.fromEntries(
          Object.entries(transport).map(([k, v]) => [k, Number(v)])),
      }
      setResult(await fpoBulkPlan(body))
    } catch (err) {
      setError(err.response?.data?.detail
        ? 'Check farmer rows: each needs coordinates and a positive quantity.'
        : 'Plan failed.')
      setResult(null)
    }
  }

  return (
    <div className="max-w-4xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">FPO Bulk Selling</h1>
      <p className="text-gray-600 mb-4">
        Pool members' harvest and see if trucking it together beats selling alone.
      </p>
      {error && <ErrorBanner message={error} />}
      {!crop && <p className="text-gray-500 mb-3">Pick a crop above first.</p>}

      <table className="min-w-full text-sm border mb-3">
        <thead className="bg-green-50 text-left">
          <tr>
            <th className="px-2 py-2">Lat</th><th className="px-2 py-2">Lon</th>
            <th className="px-2 py-2">State</th><th className="px-2 py-2">Quantity (q)</th>
            <th className="px-2 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t">
              <td className="px-2 py-1"><input className="w-24 border rounded px-1 py-1" value={r.lat} onChange={(e) => setRow(i, 'lat', e.target.value)} /></td>
              <td className="px-2 py-1"><input className="w-24 border rounded px-1 py-1" value={r.lon} onChange={(e) => setRow(i, 'lon', e.target.value)} /></td>
              <td className="px-2 py-1"><input className="w-28 border rounded px-1 py-1" value={r.state} onChange={(e) => setRow(i, 'state', e.target.value)} /></td>
              <td className="px-2 py-1"><input className="w-24 border rounded px-1 py-1" value={r.quantity_q} onChange={(e) => setRow(i, 'quantity_q', e.target.value)} /></td>
              <td className="px-2 py-1">{rows.length > 1 && <button onClick={() => removeRow(i)} className="text-red-600">✕</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={addRow} className="text-green-700 text-sm mb-4">+ Add farmer</button>

      <div className="flex gap-3 flex-wrap mb-4 text-sm">
        {Object.keys(DEFAULT_TRANSPORT).map((k) => (
          <label key={k} className="capitalize">{k.replace(/_/g, ' ')}
            <input type="number" step="any" value={transport[k]} onChange={(e) => setT(k, e.target.value)}
              className="mt-1 block w-32 border rounded px-2 py-1" />
          </label>
        ))}
      </div>

      <button onClick={submit} disabled={!crop}
        className="bg-green-700 text-white px-4 py-2 rounded disabled:opacity-50">
        Compute plan
      </button>

      {result && (
        <div className="mt-5">
          {result.price_basis !== 'mandi' ? (
            <div className="border border-amber-300 bg-amber-50 rounded-lg p-4">
              <p>{result.message}</p>
            </div>
          ) : (
            <div className="border rounded-lg p-4">
              {result.spread_warning && (
                <p className="text-amber-700 text-sm mb-2">⚠ {result.spread_warning}</p>
              )}
              <p className="text-lg mb-1">{result.message}</p>
              <ul className="text-sm text-gray-700 space-y-1 mt-2">
                <li>Selling individually: <b>₹{result.baseline}</b></li>
                <li>Pooled &amp; trucked{result.chosen_mandi ? ` to ${result.chosen_mandi.market}` : ''}: <b>₹{result.aggregated_rev}</b>
                  {result.chosen_mandi ? ` (${result.chosen_mandi.trucks} truck(s), ₹${result.chosen_mandi.transport_cost} transport)` : ''}</li>
                <li className={result.extra_income > 0 ? 'text-green-700 font-semibold' : 'text-gray-600'}>
                  Extra income from pooling: ₹{result.extra_income}</li>
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire it into the workspace**

In `frontend/src/workspace/Workspace.jsx`, add the import after line 9 (`import ProfitPlanner ...`):

```jsx
import FpoBulkDashboard from '../pages/FpoBulkDashboard'
```

Then add the tool to the `sell` intent's `tools` array (currently lines 21-24), after Profit Planner:

```jsx
  { id: 'sell', label: '💰 Where & when to sell', tools: [
    { id: 'mandi', label: 'Mandi Compare', C: MandiCompare },
    { id: 'profit', label: 'Profit Planner', C: ProfitPlanner },
    { id: 'fpo', label: 'FPO Bulk Selling', C: FpoBulkDashboard },
  ] },
```

- [ ] **Step 4: Verify live**

Start the dev servers (backend `venv\Scripts\python.exe -m uvicorn main:app --reload` from `backend/`; frontend `npm run dev` from `frontend/`). In the browser:
1. Pick a mandi crop (e.g. wheat), set a pincode/GPS so coords populate.
2. Go to **💰 Where & when to sell → FPO Bulk Selling**. First row pre-fills coords.
3. Add a 2nd farmer with different coords + quantities; click **Compute plan** → individual vs pooled + extra income render.
4. Pick a non-mandi crop → the amber state-level banner shows (no fabricated number).

Expected: all four behave as described; no console errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.js frontend/src/pages/FpoBulkDashboard.jsx frontend/src/workspace/Workspace.jsx
git commit -m "feat: FPO Bulk Selling dashboard under the sell tab

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Full-suite regression + branch wrap

**Files:** none (verification + finish)

- [ ] **Step 1: Run the entire backend suite**

Run (from `backend/`): `venv\Scripts\python.exe -m pytest -p no:asyncio`
Expected: all prior tests (156) + the new FPO tests pass; no regressions.

- [ ] **Step 2: Finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to review, squash-merge `feat/fpo-bulk-selling` into `master`, and clean up — mirroring how the crop-vocab branch (PR #1) was finished. Do not push unless the user authorizes it at that point.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- §1 benefit math (`extra_income = aggregated_rev − Σ individual_rev`, per-q individual rate, truck-amortized aggregate) → Tasks 2, 3, 4.
- §2 architecture (engine / API / UI split; `rate_per_km=0` reuse) → Tasks 1–7.
- §3 algorithm (centroid origin, ceil trucks, high `top_k`) → Tasks 1, 3, 4.
- §4 edge cases: extra≤0 → Task 4; state_fallback → Tasks 4/5; source none → Tasks 4/5; single farmer → Task 4; spread soft-warning → Task 4; missing coords/qty 422 → Task 6; caching → Task 4. All covered.
- §5 testing: engine tests 1–10 → Tasks 1–5; API tests 11–13 → Task 6; frontend live verify → Task 7. All covered.

**Placeholder scan:** none — every code step shows complete code.

**Type consistency:** `plan_bulk_sale(crop, farmers, cfg)`, `_individual_revenue(farmer, markets, per_q_local_rate)`, `_aggregated_plan(markets, total_q, cfg)`, `_make_market_fetcher(crop)→fetch(lat,lon,state)`, `TransportConfig(truck_capacity_q, fixed_hire_per_truck, per_km_per_truck, per_q_local_rate)` — names and signatures match across tasks and tests. Result keys (`baseline`, `aggregated_rev`, `extra_income`, `price_basis`, `chosen_mandi`, `per_farmer`, `spread_warning`, `message`, `total_q`, `crop`) are consistent between engine, API tests, and the frontend.
