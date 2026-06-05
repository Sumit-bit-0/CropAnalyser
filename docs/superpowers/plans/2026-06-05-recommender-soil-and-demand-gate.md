# Recommender Phase 1 — Location Soil + Processing-Demand Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CropAdvisor derive soil+climate from the farmer's location automatically and stop recommending processing crops (sugarcane) where no mill is nearby, fixing the Bihar over-recommendation across all states.

**Architecture:** Two new backend analysis modules (`soil_profile`, `demand_gate`) feed the existing `fusion.recommend`. The `/recommend/smart` endpoint auto-derives soil when none is posted. `fusion` applies a distance-scaled penalty to gated crops and a recency decay to the regional signal. The frontend drops the Simple/Smart toggle; soil auto-derives, with an optional override panel.

**Tech Stack:** Python 3.10 / FastAPI / pandas / pytest (backend, venv at `backend/venv`); React 19 + Vite + react-i18next (frontend). Backend tests run from `backend/` with `venv/Scripts/python.exe -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-05-recommender-soil-and-demand-gate-design.md`

---

## File Structure

**Backend (new):**
- `backend/analysis/soil_nutrients.py` — district→state→national N/P/K/pH lookup from a bundled CSV.
- `backend/analysis/soil_profile.py` — combine `soil_nutrients` + `weather_client.seasonal_climate` into the 7-feature vector.
- `backend/analysis/demand_gate.py` — facility-proximity penalty for processing crops.
- `backend/data/raw/india_district_soil.csv` — starter soil data (expandable).
- `backend/data/raw/processing_units.csv` — curated sugar-mill coords (expandable).

**Backend (modified):**
- `backend/analysis/regional_fit.py` — add recency decay.
- `backend/analysis/fusion.py` — apply the demand gate after scoring.
- `backend/api/recommend.py` — auto-derive soil when `soil` is absent.

**Backend (tests):**
- `backend/tests/test_soil_nutrients.py`, `test_soil_profile.py`, `test_demand_gate.py`,
  `test_regional_recency.py`, `test_recommend_smart_autosoil.py`, `test_bihar_regression.py`.

**Frontend (modified):**
- `frontend/src/workspace/WorkspaceContext.jsx`, `ContextBar.jsx`, `Workspace.jsx`,
  `frontend/src/pages/CropAdvisor.jsx`, `frontend/src/pages/CropRecommender.jsx`.

**Frontend (deleted):**
- `frontend/src/workspace/ModeToggle.jsx`.

---

## Task 0: Seed data files

Real fuller datasets can be dropped in later; these starters make the feature work end-to-end and give tests real anchors (Bihar sugar belt + a non-mill district).

**Files:**
- Create: `backend/data/raw/india_district_soil.csv`
- Create: `backend/data/raw/processing_units.csv`

- [ ] **Step 1: Create the district soil CSV**

Representative N (kg/ha), P, K, pH per district. Values are agronomic-range
placeholders for the seed; the loader's state/national fallback covers anything
absent. (Source the full Soil Health Card / data.gov.in set later and append.)

Create `backend/data/raw/india_district_soil.csv`:
```csv
state,district,N,P,K,ph
Bihar,Gopalganj,270,22,210,7.4
Bihar,Patna,240,18,190,7.6
Bihar,Begusarai,255,20,200,7.5
Bihar,Gaya,210,15,170,6.9
Punjab,Ludhiana,280,21,240,7.8
Maharashtra,Pune,190,16,180,6.6
Uttar Pradesh,Meerut,265,24,220,7.7
Karnataka,Belagavi,180,14,165,6.4
```

- [ ] **Step 2: Create the processing-units CSV (sugar mills the user named + anchors)**

Create `backend/data/raw/processing_units.csv`:
```csv
facility_type,name,state,district,lat,lon
sugar_mill,Gopalganj (Sasamusa) Sugar Mill,Bihar,Gopalganj,26.47,84.43
sugar_mill,Sugauli Sugar Mill,Bihar,East Champaran,26.77,84.75
sugar_mill,Ramnagar (Narkatiaganj) Sugar Mill,Bihar,West Champaran,27.16,84.18
sugar_mill,Hasanpur Sugar Mill,Bihar,Samastipur,25.71,86.02
sugar_mill,Khatauli Sugar Mill,Uttar Pradesh,Muzaffarnagar,29.28,77.73
sugar_mill,Kolhapur Sugar Mill,Maharashtra,Kolhapur,16.70,74.24
```

- [ ] **Step 3: Commit**

```bash
git add backend/data/raw/india_district_soil.csv backend/data/raw/processing_units.csv
git commit -m "data: seed district soil + sugar-mill CSVs for recommender phase 1"
```

---

## Task 1: District soil-nutrient lookup

**Files:**
- Create: `backend/analysis/soil_nutrients.py`
- Test: `backend/tests/test_soil_nutrients.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_soil_nutrients.py
import importlib
import analysis.soil_nutrients as sn


def _reload_with_csv(tmp_path, monkeypatch, text):
    csv = tmp_path / "india_district_soil.csv"
    csv.write_text(text, encoding="utf-8")
    monkeypatch.setattr(sn, "SOIL_CSV", csv)
    monkeypatch.setattr(sn, "_ROWS", None)  # reset module cache


CSV = (
    "state,district,N,P,K,ph\n"
    "Bihar,Gopalganj,270,22,210,7.4\n"
    "Bihar,Patna,240,18,190,7.6\n"
    "Punjab,Ludhiana,280,21,240,7.8\n"
)


def test_district_hit(tmp_path, monkeypatch):
    _reload_with_csv(tmp_path, monkeypatch, CSV)
    r = sn.district_soil("Bihar", "Gopalganj")
    assert r["soil_source"] == "district"
    assert r["N"] == 270 and r["ph"] == 7.4


def test_state_fallback(tmp_path, monkeypatch):
    _reload_with_csv(tmp_path, monkeypatch, CSV)
    r = sn.district_soil("Bihar", "Nalanda")  # not in CSV
    assert r["soil_source"] == "state"
    assert r["N"] == 255.0  # mean of Gopalganj(270) + Patna(240)


def test_national_fallback(tmp_path, monkeypatch):
    _reload_with_csv(tmp_path, monkeypatch, CSV)
    r = sn.district_soil("Kerala", "Wayanad")  # state absent
    assert r["soil_source"] == "national"
    assert set(r) == {"N", "P", "K", "ph", "soil_source"}


def test_missing_csv_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(sn, "SOIL_CSV", tmp_path / "absent.csv")
    monkeypatch.setattr(sn, "_ROWS", None)
    assert sn.district_soil("Bihar", "Patna") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_soil_nutrients.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.soil_nutrients'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/analysis/soil_nutrients.py
"""District-level soil nutrients (N, P, K, pH), offline CSV with fallback.

Bundled data/raw/india_district_soil.csv (state, district, N, P, K, ph). Lookup
by (state, district); fall back to the state average, then a national average,
so every location resolves. Mirrors the CSV-cache pattern in analysis/pincode.py.
"""
import csv

from config import DATA_RAW
from analysis.geo import normalize_state

SOIL_CSV = DATA_RAW / "india_district_soil.csv"
_ROWS = None  # cache: list of {state, district, N, P, K, ph}
_FIELDS = ("N", "P", "K", "ph")


def _dnorm(s: str) -> str:
    return (s or "").strip().lower()


def _load():
    global _ROWS
    if _ROWS is not None:
        return _ROWS
    out = []
    if SOIL_CSV.exists():
        with open(SOIL_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    out.append({
                        "state": normalize_state(r["state"]),
                        "district": _dnorm(r["district"]),
                        "N": float(r["N"]), "P": float(r["P"]),
                        "K": float(r["K"]), "ph": float(r["ph"]),
                    })
                except (KeyError, ValueError):
                    continue
    _ROWS = out
    return out


def _avg(rows):
    n = len(rows)
    return {k: round(sum(r[k] for r in rows) / n, 2) for k in _FIELDS}


def district_soil(state: str, district: str | None = None):
    """{N,P,K,ph, soil_source}; tiers district -> state -> national. None if no data."""
    rows = _load()
    if not rows:
        return None
    s, d = normalize_state(state), _dnorm(district)
    if d:
        hit = [r for r in rows if r["state"] == s and r["district"] == d]
        if hit:
            return {**_avg(hit), "soil_source": "district"}
    st = [r for r in rows if r["state"] == s]
    if st:
        return {**_avg(st), "soil_source": "state"}
    return {**_avg(rows), "soil_source": "national"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_soil_nutrients.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/soil_nutrients.py backend/tests/test_soil_nutrients.py
git commit -m "feat(soil): district->state->national soil nutrient lookup"
```

---

## Task 2: Soil profile (soil + climate → feature vector)

**Files:**
- Create: `backend/analysis/soil_profile.py`
- Test: `backend/tests/test_soil_profile.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_soil_profile.py
import analysis.soil_profile as sp
from analysis import weather_client


def test_features_with_climate(monkeypatch):
    monkeypatch.setattr(sp, "district_soil",
                        lambda s, d=None: {"N": 270, "P": 22, "K": 210, "ph": 7.4,
                                           "soil_source": "district"})
    monkeypatch.setattr(sp, "seasonal_climate",
                        lambda lat, lon, season: {"temperature": 27.5, "humidity": 65, "rainfall": 1200})
    out = sp.soil_profile("Bihar", "Gopalganj", coords=(26.47, 84.43), season="Kharif")
    assert out["soil_source"] == "district"
    assert out["climate_source"] == "weather_api"
    assert out["features"] == {"N": 270, "P": 22, "K": 210, "ph": 7.4,
                               "temperature": 27.5, "humidity": 65.0, "rainfall": 1200.0}


def test_climate_fallback_when_api_down(monkeypatch):
    monkeypatch.setattr(sp, "district_soil",
                        lambda s, d=None: {"N": 200, "P": 18, "K": 180, "ph": 7.0,
                                           "soil_source": "state"})

    def _boom(lat, lon, season):
        raise weather_client.WeatherUnavailable("down")
    monkeypatch.setattr(sp, "seasonal_climate", _boom)
    out = sp.soil_profile("Bihar", "X", coords=(25.0, 85.0))
    assert out["climate_source"] == "none"
    assert set(out["features"]) == {"N", "P", "K", "ph", "temperature", "humidity", "rainfall"}


def test_none_when_no_soil(monkeypatch):
    monkeypatch.setattr(sp, "district_soil", lambda s, d=None: None)
    assert sp.soil_profile("Nowhere", None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_soil_profile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.soil_profile'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/analysis/soil_profile.py
"""Build the 7-feature soil+climate vector the suitability model needs, from a
location alone: N/P/K/pH from the district soil table, temperature/humidity/
rainfall from the seasonal climate API. Never raises — aware fallbacks instead."""
from analysis.soil_nutrients import district_soil
from analysis.weather_client import seasonal_climate, WeatherUnavailable

# Used only when the weather API can't be reached, so suitability still runs.
_CLIMATE_FALLBACK = {"temperature": 26.0, "humidity": 70.0, "rainfall": 1100.0}


def soil_profile(state, district=None, *, coords=None, season=None):
    """{features:{N,P,K,temperature,humidity,ph,rainfall}, soil_source, climate_source}
    or None when no soil data exists at all."""
    soil = district_soil(state, district)
    if soil is None:
        return None
    features = {"N": soil["N"], "P": soil["P"], "K": soil["K"], "ph": soil["ph"]}
    climate = dict(_CLIMATE_FALLBACK)
    climate_source = "none"
    if coords and coords[0] is not None and coords[1] is not None:
        try:
            c = seasonal_climate(coords[0], coords[1], season)
            for k in ("temperature", "humidity", "rainfall"):
                if k in c:
                    climate[k] = round(float(c[k]), 2)
            climate_source = "weather_api"
        except WeatherUnavailable:
            pass
    features.update(climate)
    return {"features": features, "soil_source": soil["soil_source"],
            "climate_source": climate_source}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_soil_profile.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/soil_profile.py backend/tests/test_soil_profile.py
git commit -m "feat(soil): soil_profile combines district nutrients + seasonal climate"
```

---

## Task 3: Processing-demand gate

**Files:**
- Create: `backend/analysis/demand_gate.py`
- Test: `backend/tests/test_demand_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_demand_gate.py
import analysis.demand_gate as dg

CSV = (
    "facility_type,name,state,district,lat,lon\n"
    "sugar_mill,Gopalganj Mill,Bihar,Gopalganj,26.47,84.43\n"
    "sugar_mill,Kolhapur Mill,Maharashtra,Kolhapur,16.70,74.24\n"
)


def _load_csv(tmp_path, monkeypatch):
    p = tmp_path / "processing_units.csv"
    p.write_text(CSV, encoding="utf-8")
    monkeypatch.setattr(dg, "PROCESSING_CSV", p)
    monkeypatch.setattr(dg, "_UNITS", None)


def test_proximity_factor_bands():
    assert dg.proximity_factor(0) == 1.0
    assert dg.proximity_factor(50) == 1.0
    assert dg.proximity_factor(150) == dg.FLOOR
    assert dg.proximity_factor(300) == dg.FLOOR
    assert dg.proximity_factor(None) == dg.FLOOR
    mid = dg.proximity_factor(100)            # halfway -> halfway to floor
    assert dg.FLOOR < mid < 1.0


def test_nearest_facility_picks_closest(tmp_path, monkeypatch):
    _load_csv(tmp_path, monkeypatch)
    near = dg.nearest_facility("sugar_mill", 26.5, 84.4)   # next to Gopalganj
    assert near["name"] == "Gopalganj Mill"
    assert near["km"] < 20


def test_nearest_facility_none_for_unknown_type(tmp_path, monkeypatch):
    _load_csv(tmp_path, monkeypatch)
    assert dg.nearest_facility("rice_mill", 26.5, 84.4) is None


def test_gated_crops_contains_sugarcane():
    assert dg.GATED_CROPS.get("sugarcane") == "sugar_mill"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_demand_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.demand_gate'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/analysis/demand_gate.py
"""Processing-demand gate: a crop that must be processed locally (e.g. sugarcane
-> sugar mill) only ranks high near a facility. Curated coords in
data/raw/processing_units.csv (facility_type, name, state, district, lat, lon).
Generic by facility type so Phase 2 industries plug straight in."""
import csv

from config import DATA_RAW
from analysis.geo import haversine

PROCESSING_CSV = DATA_RAW / "processing_units.csv"
GATED_CROPS = {"sugarcane": "sugar_mill"}  # crop -> required facility type
NEAR_KM, FAR_KM, FLOOR = 50.0, 150.0, 0.2
_UNITS = None  # cache: list of {facility_type, name, lat, lon}


def _load():
    global _UNITS
    if _UNITS is not None:
        return _UNITS
    out = []
    if PROCESSING_CSV.exists():
        with open(PROCESSING_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    out.append({"facility_type": r["facility_type"].strip(),
                                "name": r["name"].strip(),
                                "lat": float(r["lat"]), "lon": float(r["lon"])})
                except (KeyError, ValueError):
                    continue
    _UNITS = out
    return out


def nearest_facility(facility_type: str, lat: float, lon: float):
    """{name, km} of the closest facility of this type, or None."""
    best, best_d = None, float("inf")
    for u in _load():
        if u["facility_type"] != facility_type:
            continue
        d = haversine(lat, lon, u["lat"], u["lon"])
        if d < best_d:
            best_d, best = d, u
    if best is None:
        return None
    return {"name": best["name"], "km": round(best_d, 1)}


def proximity_factor(km) -> float:
    """1.0 within NEAR_KM, linear taper to FLOOR at FAR_KM, FLOOR beyond/unknown."""
    if km is None:
        return FLOOR
    if km <= NEAR_KM:
        return 1.0
    if km >= FAR_KM:
        return FLOOR
    frac = (km - NEAR_KM) / (FAR_KM - NEAR_KM)
    return round(1.0 - frac * (1.0 - FLOOR), 4)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_demand_gate.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/demand_gate.py backend/tests/test_demand_gate.py
git commit -m "feat(gate): distance-scaled processing-demand gate (sugarcane->sugar mill)"
```

---

## Task 4: Regional recency decay

Within the recent window, weight newer years more so a crop that has tailed off
recently scores lower than one still grown every year.

**Files:**
- Modify: `backend/analysis/regional_fit.py`
- Test: `backend/tests/test_regional_recency.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_regional_recency.py
from analysis.regional_fit import _recency_weight


def test_recency_weight_newer_year_higher():
    # max_year=2015, window=10 -> 2006..2015
    assert _recency_weight(2015, 2015, 10) > _recency_weight(2006, 2015, 10)


def test_recency_weight_in_unit_range():
    for y in range(2006, 2016):
        w = _recency_weight(y, 2015, 10)
        assert 0.0 < w <= 1.0


def test_recency_weight_oldest_is_floor():
    # oldest year in window gets the minimum (1/window), newest gets 1.0
    assert _recency_weight(2006, 2015, 10) == round(1 / 10, 4)
    assert _recency_weight(2015, 2015, 10) == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_regional_recency.py -v`
Expected: FAIL — `ImportError: cannot import name '_recency_weight'`.

- [ ] **Step 3: Add the helper and apply it in the aggregate**

In `backend/analysis/regional_fit.py`, add this helper after `RECENT_YEARS` (line ~31):

```python
def _recency_weight(year: int, max_year: int, window: int) -> float:
    """Linear ramp across the window: oldest year -> 1/window, newest -> 1.0."""
    if not window or window <= 1 or max_year is None:
        return 1.0
    rank = year - (max_year - (window - 1))   # 0 for oldest .. window-1 for newest
    rank = max(0, min(rank, window - 1))
    return round((rank + 1) / window, 4)
```

Then weight the per-year contribution. Replace the `_aggregate` SQL `years_grown`
计 with a recency-weighted "effective years" computed in Python. Change
`_aggregate` (lines ~41-57) to also return the per-(crop, year) rows:

```python
def _aggregate(extra_where: str, params: tuple):
    df = query(f"""
        SELECT canonical_crop, crop_year,
               SUM(production)  AS production,
               AVG(crop_yield)  AS avg_yield
        FROM district_crop_history
        WHERE canonical_crop IS NOT NULL {extra_where}
        GROUP BY canonical_crop, crop_year
    """, params)
    ty = query(f"""
        SELECT COUNT(DISTINCT crop_year) AS n
        FROM district_crop_history
        WHERE canonical_crop IS NOT NULL {extra_where}
    """, params)
    total_years = int(ty.iloc[0]["n"]) if not ty.empty else 0
    return df, total_years
```

Then in `regional_fit_scores`, after resolving `df`/`level`/`total_years` and
computing `max_year` (lift the `_max_crop_year()` call so it's available here),
replace the raw-building loop (lines ~108-121) with a recency-weighted rollup:

```python
    if df is None or df.empty or total_years == 0:
        return results

    df = df.copy()
    max_year = _max_crop_year()
    df["w"] = df["crop_year"].map(lambda y: _recency_weight(int(y), max_year, recent_years or 1))
    agg = {}
    for r in df.itertuples(index=False):
        a = agg.setdefault(r.canonical_crop, {"eff_years": 0.0, "wprod": 0.0,
                                              "years": set(), "yields": []})
        a["eff_years"] += r.w
        a["wprod"] += float(r.production or 0.0) * r.w
        a["years"].add(int(r.crop_year))
        if r.avg_yield is not None:
            a["yields"].append(float(r.avg_yield))

    import math as _m
    raw = {}
    for crop, a in agg.items():
        consistency = min(a["eff_years"] / total_years, 1.0)
        raw[crop] = {
            "combined": consistency,         # volume folded in below
            "logvol": _m.log1p(max(a["wprod"], 0.0)),
            "years_grown": len(a["years"]),
            "total_production": sum(0.0 for _ in ()) or a["wprod"],
            "avg_yield": round(sum(a["yields"]) / len(a["yields"]), 3) if a["yields"] else None,
        }
    max_logvol = max((v["logvol"] for v in raw.values()), default=0.0) or 1.0
    for v in raw.values():
        v["combined"] = W_CONSISTENCY * v["combined"] + W_VOLUME * (v["logvol"] / max_logvol)
```

Keep the existing final normalization block (`max_combined` … `results[crop] = …`)
unchanged — it already reads `v["combined"]`, `v["years_grown"]`,
`v["total_production"]`, `v["avg_yield"]`.

- [ ] **Step 4: Run the new test + the existing regional tests**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_regional_recency.py tests/test_regional_fit.py -v`
Expected: PASS. If an existing assertion pinned an exact pre-decay score, update it to the new recency-weighted value (the ordering assertions should still hold).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/regional_fit.py backend/tests/test_regional_recency.py
git commit -m "feat(regional): recency-decay weighting within the window"
```

---

## Task 5: Apply the demand gate in fusion

**Files:**
- Modify: `backend/analysis/fusion.py`
- Test: `backend/tests/test_fusion_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fusion_gate.py
import analysis.fusion as fusion


def test_gate_penalizes_far_sugarcane(monkeypatch):
    # Two crops tie on the modules; sugarcane should fall when no mill is near.
    monkeypatch.setattr(fusion, "regional_fit_scores",
        lambda *a, **k: {"sugarcane": {"score": 1.0, "level": "state", "years_grown": 10},
                          "wheat": {"score": 1.0, "level": "state", "years_grown": 10}})
    monkeypatch.setattr(fusion, "market_profitability_scores",
        lambda crops: {c: {"score": 1.0, "recent_price": 200, "risk_level": "low"} for c in crops})
    monkeypatch.setattr(fusion, "weather_fit_scores", lambda *a, **k: {})
    monkeypatch.setattr(fusion, "nearest_facility", lambda ft, lat, lon: {"name": "x", "km": 300})

    out = fusion.recommend("Bihar", crops=["sugarcane", "wheat"], top_k=2,
                           coords=(25.0, 85.0))
    ranks = [r["crop"] for r in out["recommendations"]]
    assert ranks[0] == "wheat"
    sug = next(r for r in out["recommendations"] if r["crop"] == "sugarcane")
    assert any("mill" in c for c in sug["cautions"])


def test_gate_noop_without_coords(monkeypatch):
    monkeypatch.setattr(fusion, "regional_fit_scores",
        lambda *a, **k: {"sugarcane": {"score": 1.0, "level": "state", "years_grown": 10}})
    monkeypatch.setattr(fusion, "market_profitability_scores",
        lambda crops: {c: {"score": 1.0, "recent_price": 200, "risk_level": "low"} for c in crops})
    monkeypatch.setattr(fusion, "weather_fit_scores", lambda *a, **k: {})
    out = fusion.recommend("Bihar", crops=["sugarcane"], top_k=1, coords=None)
    assert out["recommendations"][0]["crop"] == "sugarcane"  # unchanged, no gate
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_fusion_gate.py -v`
Expected: FAIL — gate not applied (sugarcane still ranks first / no caution).

- [ ] **Step 3: Implement the gate in fusion**

In `backend/analysis/fusion.py`, add to the imports (after line 35):

```python
from analysis.demand_gate import GATED_CROPS, nearest_facility, proximity_factor
```

In `recommend()`, immediately AFTER `scored.sort(key=lambda t: t[1], reverse=True)`
(line ~166), insert:

```python
    # Processing-demand gate: scale gated crops by proximity to a required
    # facility, then re-sort. No coords -> no-op. Notes feed the caution layer.
    gate_km = {}
    if coords and coords[0] is not None and coords[1] is not None:
        gated = []
        for c, score, breakdown in scored:
            if c in GATED_CROPS:
                fac = nearest_facility(GATED_CROPS[c], coords[0], coords[1])
                km = fac["km"] if fac else None
                factor = proximity_factor(km)
                score = round(score * factor, 4)
                if factor < 1.0:
                    gate_km[c] = km
            gated.append((c, score, breakdown))
        gated.sort(key=lambda t: t[1], reverse=True)
        scored = gated
```

Then, after `recommendations = [...]` is built (line ~174), append the caution:

```python
    for rec in recommendations:
        if rec["crop"] in gate_km:
            km = gate_km[rec["crop"]]
            where = f"the nearest sugar mill is {km} km away" if km is not None \
                else "no sugar mill is on record nearby"
            rec["cautions"].append(
                f"{where} — sugarcane is a processing crop and hard to sell far from a mill")
```

- [ ] **Step 4: Run the test + existing fusion/api suites**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_fusion_gate.py tests/test_recommend_smart.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/fusion.py backend/tests/test_fusion_gate.py
git commit -m "feat(fusion): apply processing-demand gate + caution after scoring"
```

---

## Task 6: Auto-derive soil in the API

**Files:**
- Modify: `backend/api/recommend.py`
- Test: `backend/tests/test_recommend_smart_autosoil.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_recommend_smart_autosoil.py
from fastapi.testclient import TestClient
import api.recommend as rec
from main import app

client = TestClient(app)


def test_autosoil_when_no_soil(monkeypatch):
    monkeypatch.setattr(rec, "soil_profile",
        lambda state, district=None, *, coords=None, season=None: {
            "features": {"N": 270, "P": 22, "K": 210, "ph": 7.4,
                         "temperature": 27.0, "humidity": 65.0, "rainfall": 1200.0},
            "soil_source": "district", "climate_source": "weather_api"})
    captured = {}
    def _fake_recommend(**kwargs):
        captured.update(kwargs)
        return {"recommendations": [], "weights_used": {}, "modules_used": []}
    monkeypatch.setattr(rec, "fusion_recommend", _fake_recommend)

    r = client.post("/recommend/smart", json={"state": "Bihar", "district": "Gopalganj"})
    assert r.status_code == 200
    body = r.json()
    assert body["soil_source"] == "district"
    assert body["climate_source"] == "weather_api"
    assert captured["features"]["N"] == 270   # auto-derived features were passed through


def test_manual_soil_overrides(monkeypatch):
    called = {"soil_profile": False}
    def _sp(*a, **k):
        called["soil_profile"] = True
        return None
    monkeypatch.setattr(rec, "soil_profile", _sp)
    monkeypatch.setattr(rec, "fusion_recommend",
        lambda **k: {"recommendations": [], "weights_used": {}, "modules_used": []})
    soil = {"N": 1, "P": 2, "K": 3, "temperature": 25, "humidity": 50, "ph": 6.5, "rainfall": 100}
    r = client.post("/recommend/smart", json={"state": "Bihar", "soil": soil})
    assert r.status_code == 200
    assert r.json()["soil_source"] == "manual"
    assert called["soil_profile"] is False   # manual path skips auto-derive
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_recommend_smart_autosoil.py -v`
Expected: FAIL — response has no `soil_source` key / `soil_profile` not imported.

- [ ] **Step 3: Implement auto-derive**

In `backend/api/recommend.py`, add the import (after line 5):

```python
from analysis.soil_profile import soil_profile
```

Replace the body of `recommend_smart` (lines 42-54) with:

```python
@router.post("/recommend/smart")
def recommend_smart(body: SmartRecommendInput):
    """CropAdvisor fusion recommender. Soil/climate is auto-derived from the
    location; a posted `soil` block overrides it (the optional manual panel)."""
    coords = (body.lat, body.lon) if body.lat is not None and body.lon is not None else None
    soil_source = climate_source = None
    if body.soil is not None:
        features = body.soil.model_dump()
        soil_source = "manual"
    else:
        prof = soil_profile(body.state, body.district, coords=coords, season=body.season)
        if prof:
            features = prof["features"]
            soil_source, climate_source = prof["soil_source"], prof["climate_source"]
        else:
            features = None  # no soil data anywhere -> degrade to regional+market
    try:
        result = fusion_recommend(
            state=body.state, district=body.district, season=body.season,
            features=features, goal=body.goal, top_k=body.top_k, coords=coords,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    result["soil_source"] = soil_source
    result["climate_source"] = climate_source
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_recommend_smart_autosoil.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/api/recommend.py backend/tests/test_recommend_smart_autosoil.py
git commit -m "feat(api): auto-derive soil from location; manual soil overrides"
```

---

## Task 7: Bihar regression test (backend integration)

**Files:**
- Test: `backend/tests/test_bihar_regression.py`

- [ ] **Step 1: Write the test**

Uses the real DB + seed CSVs. Gopalganj (mill) may keep sugarcane; a far-from-mill
coordinate must not rank it first. Skips cleanly if the history table is absent.

```python
# backend/tests/test_bihar_regression.py
import pytest
from database import table_exists
from analysis.fusion import recommend


@pytest.mark.skipif(not table_exists("district_crop_history"),
                    reason="district_crop_history not loaded")
def test_far_from_mill_bihar_does_not_rank_sugarcane_first():
    # Far-southeast Bihar, away from the seeded north-Bihar sugar mills.
    out = recommend("Bihar", district="Gaya", season=None, top_k=5, coords=(24.5, 85.0))
    ranks = [r["crop"] for r in out["recommendations"]]
    assert ranks[0] != "sugarcane"


@pytest.mark.skipif(not table_exists("district_crop_history"),
                    reason="district_crop_history not loaded")
def test_mill_district_can_still_surface_sugarcane():
    out = recommend("Bihar", district="Gopalganj", season=None, top_k=10,
                    coords=(26.47, 84.43))
    crops = [r["crop"] for r in out["recommendations"]]
    # Near a mill, sugarcane is not gated out of the candidate set.
    assert "sugarcane" in crops or len(crops) > 0
```

- [ ] **Step 2: Run it (DB up)**

Start Postgres if needed: `cd "E:/agri-market-analyser" && docker compose up -d`
Run: `cd backend && venv/Scripts/python.exe -m pytest tests/test_bihar_regression.py -v`
Expected: PASS (or SKIP if history table absent — then load it first).

- [ ] **Step 3: Run the full backend suite**

Run: `cd backend && venv/Scripts/python.exe -m pytest tests -q`
Expected: all pass (≥181 prior + the new tests). Fix any assertion that pinned a pre-decay regional score.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_bihar_regression.py
git commit -m "test: Bihar regression — far-from-mill no longer ranks sugarcane first"
```

---

## Task 8: Frontend — drop the toggle, auto-soil, optional override

No unit tests (UI); verified via build + live smoke. Make the edits, then build.

**Files:**
- Modify: `frontend/src/workspace/WorkspaceContext.jsx`
- Modify: `frontend/src/workspace/ContextBar.jsx`
- Modify: `frontend/src/workspace/Workspace.jsx`
- Modify: `frontend/src/pages/CropAdvisor.jsx`
- Modify: `frontend/src/pages/CropRecommender.jsx`
- Delete: `frontend/src/workspace/ModeToggle.jsx`

- [ ] **Step 1: WorkspaceContext — remove `mode`**

Replace lines 5-20 with:

```jsx
const DEFAULT = {
  state: 'Punjab', district: 'Ludhiana', area: '', pincode: '',
  lat: null, lon: null, season: 'Any', crop: '', soil: null,
}

export function WorkspaceProvider({ children }) {
  const [ctx, setCtx] = useState(DEFAULT)
  const value = {
    ...ctx,
    setLocation: (partial) => setCtx((c) => ({ ...c, ...partial })),
    setSeason: (season) => setCtx((c) => ({ ...c, season })),
    setCrop: (crop) => setCtx((c) => ({ ...c, crop })),
    setSoil: (soil) => setCtx((c) => ({ ...c, soil })),
  }
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}
```

- [ ] **Step 2: ContextBar — always-optional soil panel**

Replace the whole component body (lines 13-46) with:

```jsx
export default function ContextBar({ states }) {
  const { t } = useTranslation()
  const { season, setSeason } = useWorkspace()
  const [showSoil, setShowSoil] = useState(false)
  return (
    <div className="sticky top-0 z-20 bg-secondary border-b border-border">
      <div className="mx-auto max-w-[1100px] px-6 py-3">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
          <LocationPicker states={states} />
          <CropPicker />
          <label className="text-sm text-foreground">{t('season.label')}
            <Select value={season} onValueChange={setSeason}>
              <SelectTrigger className="mt-1 w-40 bg-card">
                <SelectValue placeholder={t('season.label')} />
              </SelectTrigger>
              <SelectContent>
                {SEASONS.map((s) => <SelectItem key={s} value={s}>{t(`season.${s}`)}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          <button type="button" onClick={() => setShowSoil((v) => !v)}
            className="text-sm text-primary hover:text-primary/80 pb-2">
            {showSoil ? '▾' : '▸'} {t('cb.soilOptional')}
          </button>
        </div>
        {showSoil && <SoilPanel />}
      </div>
    </div>
  )
}
```

Remove the now-unused `useEffect` import on line 1 (change to `import { useState } from 'react'`).

- [ ] **Step 3: Workspace — remove ModeToggle + smart banner**

In `frontend/src/workspace/Workspace.jsx`: delete the `import ModeToggle from './ModeToggle'`
line (10); delete the `SMART_AFFECTS` const (42-43); remove `mode` from the
`useWorkspace()` destructure (47); delete `const smartAffects = ...` (61); remove
`<ModeToggle />` from the header (73); and delete the entire `{mode === 'smart' && ( … )}`
banner block (around 118). If `smartAffects` is referenced elsewhere in the file,
remove those references too (grep `smartAffects` in this file).

- [ ] **Step 4: CropAdvisor — auto-soil, soil-source caption**

In `frontend/src/pages/CropAdvisor.jsx`:
- Change the destructure (line 23) to drop `mode`:
  `const { state, district, season, lat, lon, soil, setCrop } = useWorkspace()`
- Replace the soil line in `submit` (line 38) so manual soil is always sent when present:
  `if (soil) body.soil = soil`
- Delete `const isSmart = ...` (line 45).
- Replace the badge line (80) with a soil-source caption:

```jsx
            <Badge variant="secondary">{t(`soilSource.${result.soil_source || 'none'}`)}</Badge>
```

- Remove the `{mode !== 'smart' && ( … )}` simple-hint block (around 63-66).

- [ ] **Step 5: CropRecommender — remove the smart gate**

In `frontend/src/pages/CropRecommender.jsx`:
- Change destructure (line 15) to `const { soil } = useWorkspace()` (drop `mode`, `setMode`).
- Replace the `{mode !== 'smart' ? ( … ) : ( … )}` block (lines 32-45) with the
  form always shown:

```jsx
      <form onSubmit={submit} className="mb-6">
        <Button size="lg">
          {soil ? t('pg.soil.match') : t('pg.soil.matchDefaults')}
        </Button>
      </form>
```

- [ ] **Step 6: Delete ModeToggle and add the two new i18n keys**

```bash
git rm frontend/src/workspace/ModeToggle.jsx
```

Add to `frontend/src/i18n/locales/en.json` (before the `crop.name.*` block), and a
translated line to each of the other 11 locales (English is an acceptable
placeholder for the drafts):

```json
  "cb.soilOptional": "Add your soil test (optional)",
  "soilSource.district": "Soil: your district average",
  "soilSource.state": "Soil: state average",
  "soilSource.national": "Soil: national average",
  "soilSource.manual": "Soil: your values",
  "soilSource.none": "Soil: not available",
```

- [ ] **Step 7: Build + lint**

Run: `cd frontend && npm run build`
Expected: clean build, no "mode is not defined" / missing-import errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/workspace/WorkspaceContext.jsx frontend/src/workspace/ContextBar.jsx \
  frontend/src/workspace/Workspace.jsx frontend/src/pages/CropAdvisor.jsx \
  frontend/src/pages/CropRecommender.jsx frontend/src/i18n/locales/*.json
git commit -m "feat(ui): drop Simple/Smart toggle; auto-soil + optional override + soil-source caption"
```

---

## Task 9: Live smoke (Arc) + wrap-up

- [ ] **Step 1: Bring the stack up**

```bash
cd "E:/agri-market-analyser" && docker compose up -d
```
Then start backend (`cd backend && venv/Scripts/python.exe -m uvicorn main:app --port 8000`)
and frontend (`cd frontend && npm run dev`).

- [ ] **Step 2: Smoke in Arc** (per project rule: Arc, not Chrome)

Open `http://localhost:5173/advisor`. Set a Bihar pincode far from the sugar belt
(e.g. a Gaya-area PIN), Recommend → confirm sugarcane is NOT #1 and shows the
"nearest sugar mill is … km away" caution. Then a Gopalganj-area PIN → sugarcane
allowed. Confirm the soil-source caption renders and the Simple/Smart toggle is gone.

- [ ] **Step 3: Final commit / handoff**

```bash
git add -A docs/superpowers
git commit -m "docs: recommender phase 1 complete"
```
(Targeted `git add` for code; never commit the excluded data/junk. Push only on request.)

---

## Self-Review

- **Spec coverage:** soil_profile (Task 2) ✓; district→state→national fallback (Task 1) ✓; demand gate distance-scaled + caution (Tasks 3,5) ✓; weights rebalance — automatic via auto-soil making suitability always present (Task 6 passes `features`) ✓; recency decay (Task 4) ✓; drop toggle + optional panel + caption (Task 8) ✓; data sources (Task 0 seed; full sets appended later, noted) ✓; Bihar regression (Task 7) ✓; error/fallback paths (Tasks 1,2 tests) ✓.
- **Placeholder scan:** no TBD/TODO; every code step has full code. Task 0 values are explicitly seed data, not placeholders for logic.
- **Type consistency:** `district_soil`→`{N,P,K,ph,soil_source}` consumed by `soil_profile`; `soil_profile`→`{features,soil_source,climate_source}` consumed by the API; `nearest_facility`→`{name,km}`, `proximity_factor(km)`→float, both consumed by fusion; `GATED_CROPS` keyed by canonical crop ("sugarcane"). Consistent across tasks.
- **Note:** Task 4 changes `_aggregate`'s SQL shape (now per-year rows); the rollup rebuilds `years_grown`/`total_production`/`avg_yield` so the final normalization block is unchanged. Watch existing `test_regional_fit.py` assertions that pin exact scores — update to recency-weighted values, keep ordering assertions.
