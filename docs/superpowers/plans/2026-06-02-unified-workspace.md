# Unified Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat 10-page app with one chooser-driven workspace — 3 farmer-intent tabs with sub-tabs, a shared React-context location bar (pincode/GPS/dropdown → precise coords), and a global Simple/Smart switch — reusing the existing page bodies.

**Architecture:** Backend gains an offline-first pincode resolver (bundled `india_pincodes.csv` + postalpincode.in API fallback) and threads precise `lat/lon` into the weather term. Frontend gains a `WorkspaceContext` that holds location/season/crop/mode/soil; a `Workspace` shell renders intent tabs → sub-tabs → the active reused page, each refactored to read shared context.

**Tech Stack:** Python 3.10 / FastAPI / pytest (backend, stdlib `urllib` only — no new deps); React 19 + Vite + React Router + Tailwind (frontend, no new deps, no JS test runner).

**Conventions (project rules — apply to every task):**
- Run backend from `backend/`: `venv\Scripts\python.exe -m pytest -p no:asyncio <args>`.
- Docker Postgres must be up for DB-touching tests: `docker compose up -d`.
- Commit with **targeted `git add <paths>`** — never `git add -A`. Never commit the stray untracked `data/agri.db` or the 22 MB `all_india_pincode_directory_2025.csv`.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Frontend verification = `npm run build` clean (run from `frontend/`) + manual browser check; there is no JS test runner.

---

## Task 1: Pincode loader → canonical `india_pincodes.csv`

Aggregate the 165k-row India Post directory to one row per pincode (centroid of valid office coords).

**Files:**
- Create: `backend/data/load_pincodes.py`
- Test: `backend/tests/test_load_pincodes.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_load_pincodes.py
from data.load_pincodes import aggregate_pincodes


def test_aggregates_to_one_row_per_pincode_with_centroid():
    rows = [
        {"officename": "Begusarai H.O", "officetype": "HO", "pincode": "851101",
         "district": "BEGUSARAI", "statename": "BIHAR", "latitude": "25.40", "longitude": "86.10"},
        {"officename": "Begusarai Bazar B.O", "officetype": "BO", "pincode": "851101",
         "district": "BEGUSARAI", "statename": "BIHAR", "latitude": "25.44", "longitude": "86.16"},
        {"officename": "No Coords B.O", "officetype": "BO", "pincode": "851101",
         "district": "BEGUSARAI", "statename": "BIHAR", "latitude": "NA", "longitude": "NA"},
    ]
    out = aggregate_pincodes(rows)
    assert len(out) == 1
    rec = out[0]
    assert rec["pincode"] == "851101"
    assert rec["area"] == "Begusarai H.O"      # head office preferred
    assert rec["district"] == "Begusarai"      # title-cased
    assert rec["state"] == "Bihar"
    assert rec["lat"] == round((25.40 + 25.44) / 2, 5)   # NA office excluded
    assert rec["lon"] == round((86.10 + 86.16) / 2, 5)


def test_pincode_with_no_valid_coords_is_skipped():
    rows = [{"officename": "X B.O", "officetype": "BO", "pincode": "999999",
             "district": "Z", "statename": "Y", "latitude": "NA", "longitude": "NA"}]
    assert aggregate_pincodes(rows) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_load_pincodes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data.load_pincodes'`

- [ ] **Step 3: Write the implementation**

```python
# backend/data/load_pincodes.py
"""Aggregate the India Post directory into a per-pincode centroid file.

Source: all_india_pincode_directory_2025.csv (project root, 165,627 office rows;
columns circlename, regionname, divisionname, officename, pincode, officetype,
delivery, district, statename, latitude, longitude). Many office rows have
latitude/longitude == "NA". A pincode has several offices, so we average the
valid office coordinates into a single pincode centroid.

Output: data/raw/india_pincodes.csv (pincode, area, district, state, lat, lon) —
read offline by analysis/pincode.py, mirroring india_district_centroids.csv.

Run from backend/ as a module:
    venv\\Scripts\\python.exe -m data.load_pincodes
    venv\\Scripts\\python.exe -m data.load_pincodes "C:\\path\\to\\directory.csv"
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import config

FIELDNAMES = ["pincode", "area", "district", "state", "lat", "lon"]


def aggregate_pincodes(rows):
    """rows: iterable of dicts (India Post directory). Returns a list of dicts
    with FIELDNAMES, one per pincode, sorted by pincode. Pincodes with no usable
    coordinates are skipped (the resolver falls back to the district centroid)."""
    groups = defaultdict(list)
    for r in rows:
        pin = (r.get("pincode") or "").strip()
        if pin:
            groups[pin].append(r)

    out = []
    for pin, recs in groups.items():
        lats, lons = [], []
        for r in recs:
            la = (r.get("latitude") or "").strip()
            lo = (r.get("longitude") or "").strip()
            if la and lo and la.upper() != "NA" and lo.upper() != "NA":
                try:
                    lats.append(float(la))
                    lons.append(float(lo))
                except ValueError:
                    pass
        if not lats:
            continue
        head = next((r for r in recs
                     if (r.get("officetype") or "").strip().upper() == "HO"), recs[0])
        out.append({
            "pincode": pin,
            "area": (head.get("officename") or "").strip(),
            "district": (recs[0].get("district") or "").strip().title(),
            "state": (recs[0].get("statename") or "").strip().title(),
            "lat": round(sum(lats) / len(lats), 5),
            "lon": round(sum(lons) / len(lons), 5),
        })
    out.sort(key=lambda d: d["pincode"])
    return out


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else config.ROOT / "all_india_pincode_directory_2025.csv"
    with open(src, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
    agg = aggregate_pincodes(rows)
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    out_path = config.DATA_RAW / "india_pincodes.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(agg)
    print(f"wrote {len(agg)} pincodes -> {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_load_pincodes.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Generate the real canonical file**

Run: `venv\Scripts\python.exe -m data.load_pincodes`
Expected: `wrote 19561 pincodes -> ...\data\raw\india_pincodes.csv` (count ~19,561; small file <1 MB)

- [ ] **Step 6: Commit** (commit the loader, the test, and the generated data file — NOT the 22 MB source)

```bash
git add backend/data/load_pincodes.py backend/tests/test_load_pincodes.py data/raw/india_pincodes.csv
git commit -m "feat(geo): pincode directory loader + bundled india_pincodes.csv"
```

---

## Task 2: Offline pincode resolver (`analysis/pincode.py`)

**Files:**
- Create: `backend/analysis/pincode.py`
- Test: `backend/tests/test_pincode.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pincode.py
import pytest

import analysis.pincode as pc


@pytest.fixture(autouse=True)
def _fixture_pincodes(monkeypatch):
    """Inject a tiny offline table so tests never read the bundled CSV."""
    monkeypatch.setattr(pc, "_PINCODES", {
        "851101": {"pincode": "851101", "area": "Begusarai H.O",
                   "district": "Begusarai", "state": "Bihar", "lat": 25.42, "lon": 86.13},
        "141001": {"pincode": "141001", "area": "Ludhiana H.O",
                   "district": "Ludhiana", "state": "Punjab", "lat": 30.91, "lon": 75.85},
    })


def test_resolve_offline_hit():
    r = pc.resolve_pincode("851101")
    assert r["state"] == "Bihar" and r["district"] == "Begusarai"
    assert r["lat"] == 25.42 and r["source"] == "offline"


def test_resolve_rejects_bad_pin():
    assert pc.resolve_pincode("12") is None
    assert pc.resolve_pincode("abcdef") is None
    assert pc.resolve_pincode("") is None


def test_nearest_pincode_picks_closest():
    r = pc.nearest_pincode(30.90, 75.86)   # near Ludhiana
    assert r["pincode"] == "141001"
    assert r["distance_km"] < 5 and r["source"] == "offline"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_pincode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.pincode'`

- [ ] **Step 3: Write the implementation**

```python
# backend/analysis/pincode.py
"""Resolve an Indian pincode to a precise location, offline-first.

Tier 1 (offline): bundled data/raw/india_pincodes.csv (pincode -> area, district,
state, lat, lon). Forward lookup by pincode; reverse lookup (GPS) by nearest
pincode centroid. Tier 2 (Task 3): a free API fallback for pincodes absent from
the offline set. Mirrors the CSV-cache pattern in analysis/geo.py.
"""
import csv

from analysis.geo import haversine
from config import DATA_RAW

PINCODE_CSV = DATA_RAW / "india_pincodes.csv"

_PINCODES = None  # module cache: {pincode: {pincode, area, district, state, lat, lon}}


def _load_pincodes() -> dict:
    global _PINCODES
    if _PINCODES is not None:
        return _PINCODES
    out = {}
    if PINCODE_CSV.exists():
        with open(PINCODE_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    out[r["pincode"].strip()] = {
                        "pincode": r["pincode"].strip(),
                        "area": r["area"].strip(),
                        "district": r["district"].strip(),
                        "state": r["state"].strip(),
                        "lat": float(r["lat"]),
                        "lon": float(r["lon"]),
                    }
                except (KeyError, ValueError):
                    continue
    _PINCODES = out
    return out


def resolve_pincode(pin: str):
    """6-digit pincode -> {pincode, area, district, state, lat, lon, source} or None."""
    pin = (pin or "").strip()
    if len(pin) != 6 or not pin.isdigit():
        return None
    hit = _load_pincodes().get(pin)
    if hit:
        return {**hit, "source": "offline"}
    return None  # API fallback added in Task 3


def nearest_pincode(lat: float, lon: float):
    """Reverse GPS -> nearest pincode centroid, or None if the table is empty."""
    best, best_d = None, float("inf")
    for rec in _load_pincodes().values():
        d = haversine(lat, lon, rec["lat"], rec["lon"])
        if d < best_d:
            best_d, best = d, rec
    if best is None:
        return None
    return {**best, "distance_km": round(best_d, 1), "source": "offline"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_pincode.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/pincode.py backend/tests/test_pincode.py
git commit -m "feat(geo): offline pincode resolver + nearest-pincode reverse lookup"
```

---

## Task 3: API fallback for missing pincodes

When a pincode is absent offline, query postalpincode.in (no key, stdlib `urllib`); approximate coords from the district centroid since the API returns none.

**Files:**
- Modify: `backend/analysis/pincode.py`
- Test: `backend/tests/test_pincode.py` (add)

- [ ] **Step 1: Write the failing test** (append to `tests/test_pincode.py`)

```python
def test_resolve_api_fallback(monkeypatch):
    import io, json

    sample = json.dumps([{
        "Status": "Success",
        "PostOffice": [{"Name": "Sample SO", "District": "Patna", "State": "Bihar"}],
    }]).encode()

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return sample

    monkeypatch.setattr(pc.urllib.request, "urlopen", lambda *a, **k: _Resp())
    monkeypatch.setattr(pc, "get_centroid", lambda s, d: (25.61, 85.14))

    r = pc.resolve_pincode("800001")   # not in the fixture offline table
    assert r["source"] == "api"
    assert r["state"] == "Bihar" and r["district"] == "Patna"
    assert r["lat"] == 25.61 and r["lon"] == 85.14


def test_resolve_api_failure_returns_none(monkeypatch):
    def _boom(*a, **k):
        raise OSError("network down")
    monkeypatch.setattr(pc.urllib.request, "urlopen", _boom)
    assert pc.resolve_pincode("800001") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_pincode.py -v`
Expected: FAIL — `AttributeError: module 'analysis.pincode' has no attribute 'urllib'` (and api branch missing)

- [ ] **Step 3: Update the implementation**

Add imports at the top of `analysis/pincode.py` (below the existing `import csv`):

```python
import json
import urllib.request

from analysis.geo import get_centroid, haversine
```

(Replace the existing `from analysis.geo import haversine` line with the combined import above.)

Add the constants below `PINCODE_CSV`:

```python
API_URL = "https://api.postalpincode.in/pincode/"
API_TIMEOUT = 4
```

Replace the `return None  # API fallback added in Task 3` line in `resolve_pincode` with:

```python
    return _resolve_via_api(pin)
```

Add the new function (below `resolve_pincode`):

```python
def _resolve_via_api(pin: str):
    """Tier 2: postalpincode.in lookup. Returns names; coords approximated from the
    district centroid (the API has none). Any failure -> None (never blocks)."""
    try:
        with urllib.request.urlopen(API_URL + pin, timeout=API_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    rec = data[0] if isinstance(data, list) and data else {}
    offices = rec.get("PostOffice") or []
    if rec.get("Status") != "Success" or not offices:
        return None
    po = offices[0]
    state = (po.get("State") or "").strip()
    district = (po.get("District") or "").strip()
    coords = get_centroid(state, district)
    return {
        "pincode": pin,
        "area": (po.get("Name") or "").strip(),
        "district": district,
        "state": state,
        "lat": coords[0] if coords else None,
        "lon": coords[1] if coords else None,
        "source": "api",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_pincode.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/pincode.py backend/tests/test_pincode.py
git commit -m "feat(geo): postalpincode.in API fallback for unknown pincodes"
```

---

## Task 4: Pincode + upgraded reverse-locate API routes

**Files:**
- Modify: `backend/api/geo.py`
- Test: `backend/tests/test_pincode.py` (add)

- [ ] **Step 1: Write the failing test** (append to `tests/test_pincode.py`)

```python
import api.geo as geo_api
from fastapi import HTTPException


def test_route_pincode_found(monkeypatch):
    monkeypatch.setattr(geo_api, "resolve_pincode",
                        lambda pin: {"pincode": pin, "state": "Bihar", "district": "Begusarai",
                                     "area": "Begusarai H.O", "lat": 25.42, "lon": 86.13, "source": "offline"})
    out = geo_api.geo_pincode("851101")
    assert out["state"] == "Bihar" and out["lat"] == 25.42


def test_route_pincode_not_found(monkeypatch):
    monkeypatch.setattr(geo_api, "resolve_pincode", lambda pin: None)
    with pytest.raises(HTTPException) as exc:
        geo_api.geo_pincode("000000")
    assert exc.value.status_code == 404


def test_route_locate_prefers_pincode(monkeypatch):
    monkeypatch.setattr(geo_api, "nearest_pincode",
                        lambda lat, lon: {"pincode": "141001", "state": "Punjab",
                                          "district": "Ludhiana", "area": "Ludhiana H.O",
                                          "lat": 30.91, "lon": 75.85, "distance_km": 2.1, "source": "offline"})
    out = geo_api.geo_locate(30.90, 75.86)
    assert out["pincode"] == "141001" and out["area"] == "Ludhiana H.O"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_pincode.py -v`
Expected: FAIL — `AttributeError: module 'api.geo' has no attribute 'geo_pincode'`

- [ ] **Step 3: Rewrite `backend/api/geo.py`**

```python
from fastapi import APIRouter, Query, HTTPException
from analysis.geo import locate
from analysis.pincode import resolve_pincode, nearest_pincode

router = APIRouter()


@router.get("/geo/locate")
def geo_locate(lat: float = Query(...), lon: float = Query(...)):
    """Reverse-locate GPS coords. Prefers the nearest pincode (precise area +
    coords) when the pincode table is bundled; otherwise falls back to the
    district-centroid locate()."""
    near = nearest_pincode(lat, lon)
    if near:
        return near
    return locate(lat, lon)


@router.get("/geo/pincode/{pin}")
def geo_pincode(pin: str):
    """Forward-resolve a 6-digit pincode to {area, district, state, lat, lon}."""
    rec = resolve_pincode(pin)
    if not rec:
        raise HTTPException(status_code=404, detail="Pincode not found")
    return rec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_pincode.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/api/geo.py backend/tests/test_pincode.py
git commit -m "feat(api): GET /geo/pincode/{pin} + pincode-level /geo/locate"
```

---

## Task 5: Thread precise `lat/lon` through the recommender

So a pincode's precise point sharpens the Phase 2 weather term instead of the district centroid.

**Files:**
- Modify: `backend/analysis/weather_fit.py:69` (signature)
- Modify: `backend/analysis/fusion.py:121` and `:135`
- Modify: `backend/api/recommend.py`
- Test: `backend/tests/test_fusion.py` (add)

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_fusion.py`)

```python
def test_recommend_passes_coords_to_weather(monkeypatch):
    """When coords are supplied, fusion forwards them to the weather scorer
    instead of relying on the district centroid."""
    import analysis.fusion as fusion
    captured = {}

    def _spy(state, district, season, crops=None, coords=None):
        captured["coords"] = coords
        return {}

    monkeypatch.setattr(fusion, "weather_fit_scores", _spy)
    fusion.recommend(state="Bihar", district="Begusarai", season="Kharif",
                     coords=(25.42, 86.13), top_k=3)
    assert captured["coords"] == (25.42, 86.13)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_fusion.py::test_recommend_passes_coords_to_weather -v`
Expected: FAIL — `TypeError: recommend() got an unexpected keyword argument 'coords'`

- [ ] **Step 3: Update `weather_fit.py`** — change the signature at line 69 and the coords resolution:

Replace:
```python
def weather_fit_scores(state, district, season, crops=None) -> dict:
    crops = list(crops) if crops else WHITELIST
    coords = get_centroid(state, district)
    if not coords:
        return {}
```
with:
```python
def weather_fit_scores(state, district, season, crops=None, coords=None) -> dict:
    crops = list(crops) if crops else WHITELIST
    if coords is None:
        coords = get_centroid(state, district)
    if not coords:
        return {}
```

- [ ] **Step 4: Update `fusion.py`** — add the `coords` param (line 121-124) and forward it (line 135).

Replace the `def recommend(...)` signature:
```python
def recommend(state: str, district: str | None = None, season: str | None = None,
              features: dict | None = None, goal: str | None = None,
              crops=None, top_k: int = 3, weights: dict | None = None,
              method: str = "geometric") -> dict:
```
with:
```python
def recommend(state: str, district: str | None = None, season: str | None = None,
              features: dict | None = None, goal: str | None = None,
              crops=None, top_k: int = 3, weights: dict | None = None,
              method: str = "geometric", coords: tuple | None = None) -> dict:
```
Replace:
```python
    wf = weather_fit_scores(state, district, season, crops)
```
with:
```python
    wf = weather_fit_scores(state, district, season, crops, coords=coords)
```

- [ ] **Step 5: Update `api/recommend.py`** — add `lat`/`lon` to the request and pass coords.

In `SmartRecommendInput`, add below `soil`:
```python
    lat: Optional[float] = None
    lon: Optional[float] = None
```
In `recommend_smart`, replace the body with:
```python
    features = body.soil.model_dump() if body.soil else None
    coords = (body.lat, body.lon) if body.lat is not None and body.lon is not None else None
    try:
        return fusion_recommend(
            state=body.state, district=body.district, season=body.season,
            features=features, goal=body.goal, top_k=body.top_k, coords=coords,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
```

- [ ] **Step 6: Run the new test + the full suite**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio -q`
Expected: PASS — previous 124 + new tests (Task 1-5) all green; no regressions.

- [ ] **Step 7: Commit**

```bash
git add backend/analysis/weather_fit.py backend/analysis/fusion.py backend/api/recommend.py backend/tests/test_fusion.py
git commit -m "feat(advisor): use precise lat/lon for weather when provided"
```

---

## Task 6: Frontend API client — `resolvePincode`

**Files:**
- Modify: `frontend/src/api/client.js`

- [ ] **Step 1: Add the client function** (append after the `locateByGps` line)

```javascript
export const resolvePincode   = (pin) => api.get(`/geo/pincode/${pin}`).then(r => r.data)
```

- [ ] **Step 2: Verify build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.js
git commit -m "feat(client): resolvePincode API call"
```

---

## Task 7: WorkspaceContext + provider

**Files:**
- Create: `frontend/src/workspace/WorkspaceContext.jsx`

- [ ] **Step 1: Create the context**

```jsx
import { createContext, useContext, useState } from 'react'

const WorkspaceContext = createContext(null)

const DEFAULT = {
  state: 'Punjab', district: 'Ludhiana', area: '', pincode: '',
  lat: null, lon: null, season: 'Any', crop: '', mode: 'simple', soil: null,
}

export function WorkspaceProvider({ children }) {
  const [ctx, setCtx] = useState(DEFAULT)
  const value = {
    ...ctx,
    setLocation: (partial) => setCtx((c) => ({ ...c, ...partial })),
    setSeason: (season) => setCtx((c) => ({ ...c, season })),
    setCrop: (crop) => setCtx((c) => ({ ...c, crop })),
    // leaving Smart clears soil so the Advisor reverts to Simple cleanly
    setMode: (mode) => setCtx((c) => ({ ...c, mode, soil: mode === 'simple' ? null : c.soil })),
    setSoil: (soil) => setCtx((c) => ({ ...c, soil })),
  }
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const v = useContext(WorkspaceContext)
  if (!v) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return v
}
```

- [ ] **Step 2: Verify build** — `npm run build` (Expected: succeeds; unused for now is fine.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/workspace/WorkspaceContext.jsx
git commit -m "feat(workspace): shared WorkspaceContext (location/season/crop/mode/soil)"
```

---

## Task 8: ModeToggle + SoilPanel

**Files:**
- Create: `frontend/src/workspace/ModeToggle.jsx`
- Create: `frontend/src/workspace/SoilPanel.jsx`

- [ ] **Step 1: Create `ModeToggle.jsx`**

```jsx
import { useWorkspace } from './WorkspaceContext'

export default function ModeToggle() {
  const { mode, setMode } = useWorkspace()
  const smart = mode === 'smart'
  return (
    <label className="flex items-center gap-2 text-sm select-none">
      <span className={smart ? 'opacity-70' : 'font-semibold'}>Simple</span>
      <button type="button" role="switch" aria-checked={smart} aria-label="Toggle Smart mode"
        onClick={() => setMode(smart ? 'simple' : 'smart')}
        className={`relative w-10 h-5 rounded-full transition ${smart ? 'bg-green-300' : 'bg-green-900'}`}>
        <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all ${smart ? 'left-5' : 'left-0.5'}`} />
      </button>
      <span className={smart ? 'font-semibold' : 'opacity-70'}>Smart</span>
    </label>
  )
}
```

- [ ] **Step 2: Create `SoilPanel.jsx`** (the 7 soil fields, lifted out of CropAdvisor)

```jsx
import { useWorkspace } from './WorkspaceContext'

const SOIL_FIELDS = [
  ['N', 'Nitrogen (N)', 90], ['P', 'Phosphorus (P)', 42], ['K', 'Potassium (K)', 43],
  ['temperature', 'Temp (°C)', 26], ['humidity', 'Humidity (%)', 80],
  ['ph', 'Soil pH', 6.5], ['rainfall', 'Rainfall (mm)', 180],
]

const DEFAULT_SOIL = Object.fromEntries(SOIL_FIELDS.map(([k, , v]) => [k, v]))

export default function SoilPanel() {
  const { soil, setSoil } = useWorkspace()
  const s = soil || DEFAULT_SOIL
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
      {SOIL_FIELDS.map(([k, label]) => (
        <label key={k} className="text-sm text-gray-700">{label}
          <input type="number" step="any" value={s[k]}
            onChange={(e) => setSoil({ ...s, [k]: Number(e.target.value) })}
            className="mt-1 w-full border rounded px-2 py-2" />
        </label>
      ))}
    </div>
  )
}

export { DEFAULT_SOIL }
```

- [ ] **Step 3: Verify build** — `npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/workspace/ModeToggle.jsx frontend/src/workspace/SoilPanel.jsx
git commit -m "feat(workspace): global Simple/Smart toggle + shared soil panel"
```

---

## Task 9: LocationPicker

Pincode / GPS / manual-dropdown entry, all writing the resolved location into context.

**Files:**
- Create: `frontend/src/workspace/LocationPicker.jsx`

- [ ] **Step 1: Create `LocationPicker.jsx`**

```jsx
import { useState } from 'react'
import { useWorkspace } from './WorkspaceContext'
import { resolvePincode, locateByGps } from '../api/client'

export default function LocationPicker({ states }) {
  const { state, district, area, pincode, setLocation } = useWorkspace()
  const [tab, setTab] = useState('pincode')   // 'pincode' | 'manual'
  const [pin, setPin] = useState(pincode || '')
  const [status, setStatus] = useState(null)  // {ok} | {err}
  const [busy, setBusy] = useState(false)

  const applyResolved = (r, fallbackCoords) => {
    setLocation({
      state: r.state, district: r.district, area: r.area || '',
      pincode: r.pincode || '',
      lat: r.lat ?? fallbackCoords?.lat ?? null,
      lon: r.lon ?? fallbackCoords?.lon ?? null,
    })
    setStatus({ ok: `${r.area || r.district || ''}, ${r.state}` })
  }

  const lookupPin = async () => {
    if (!/^\d{6}$/.test(pin)) { setStatus({ err: 'Enter a 6-digit pincode' }); return }
    setBusy(true); setStatus(null)
    try { applyResolved(await resolvePincode(pin)) }
    catch { setStatus({ err: "Couldn't find that PIN — pick your district" }) }
    finally { setBusy(false) }
  }

  const useGps = () => {
    if (!navigator.geolocation) { setStatus({ err: 'Geolocation not supported' }); return }
    setBusy(true); setStatus(null)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const fallback = { lat: pos.coords.latitude, lon: pos.coords.longitude }
        try {
          const r = await locateByGps(fallback.lat, fallback.lon)
          setPin(r.pincode || '')
          applyResolved(r, fallback)
        } catch { setStatus({ err: 'Could not resolve your location' }) }
        finally { setBusy(false) }
      },
      () => { setStatus({ err: 'Location permission denied' }); setBusy(false) },
      { timeout: 8000 },
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex gap-1 text-xs">
          {['pincode', 'manual'].map((t) => (
            <button key={t} type="button" onClick={() => setTab(t)}
              className={`px-2 py-1 rounded ${tab === t ? 'bg-green-700 text-white' : 'bg-gray-100 text-gray-600'}`}>
              {t === 'pincode' ? 'Pincode' : 'State / District'}
            </button>
          ))}
        </div>

        {tab === 'pincode' ? (
          <>
            <label className="text-sm text-gray-700">Pincode
              <input value={pin} inputMode="numeric" maxLength={6} placeholder="e.g. 851101"
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                className="mt-1 block w-32 border rounded px-2 py-2" />
            </label>
            <button type="button" onClick={lookupPin} disabled={busy}
              className="bg-green-700 text-white rounded px-3 py-2 text-sm disabled:opacity-50">
              {busy ? '…' : 'Find'}
            </button>
          </>
        ) : (
          <>
            <label className="text-sm text-gray-700">State
              <select value={state} onChange={(e) => setLocation({ state: e.target.value })}
                className="mt-1 block border rounded px-2 py-2">
                {states.length === 0 && <option>{state}</option>}
                {states.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label className="text-sm text-gray-700">District
              <input value={district} placeholder="e.g. Ludhiana"
                onChange={(e) => setLocation({ district: e.target.value })}
                className="mt-1 block border rounded px-2 py-2" />
            </label>
          </>
        )}

        <button type="button" onClick={useGps} disabled={busy}
          className="text-sm text-green-700 hover:text-green-900 disabled:opacity-50 pb-2">
          📍 Use my location
        </button>
      </div>

      <p className="text-xs">
        {status?.err && <span className="text-amber-600">{status.err}</span>}
        {status?.ok && <span className="text-gray-500">📍 {status.ok}</span>}
        {!status && (area || district) &&
          <span className="text-gray-500">📍 {area || district}, {state}
            {pincode ? ` · ${pincode}` : ''}</span>}
      </p>
    </div>
  )
}
```

- [ ] **Step 2: Verify build** — `npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/workspace/LocationPicker.jsx
git commit -m "feat(workspace): LocationPicker (pincode / GPS / dropdown -> context)"
```

---

## Task 10: ContextBar

**Files:**
- Create: `frontend/src/workspace/ContextBar.jsx`

- [ ] **Step 1: Create `ContextBar.jsx`**

```jsx
import { useState } from 'react'
import { useWorkspace } from './WorkspaceContext'
import LocationPicker from './LocationPicker'
import SoilPanel from './SoilPanel'

const SEASONS = ['Any', 'Kharif', 'Rabi', 'Summer', 'Winter', 'Autumn', 'Whole Year']

export default function ContextBar({ states }) {
  const { season, setSeason, mode } = useWorkspace()
  const [showSoil, setShowSoil] = useState(false)
  return (
    <div className="bg-white border-b px-4 md:px-6 py-3">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <LocationPicker states={states} />
        <label className="text-sm text-gray-700">Season
          <select value={season} onChange={(e) => setSeason(e.target.value)}
            className="mt-1 block border rounded px-2 py-2">
            {SEASONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        {mode === 'smart' && (
          <button type="button" onClick={() => setShowSoil((v) => !v)}
            className="text-sm text-green-700 hover:text-green-900 pb-2">
            {showSoil ? '▾' : '▸'} Soil details
          </button>
        )}
      </div>
      {mode === 'smart' && showSoil && <SoilPanel />}
    </div>
  )
}
```

- [ ] **Step 2: Verify build** — `npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/workspace/ContextBar.jsx
git commit -m "feat(workspace): ContextBar (location + season + smart soil)"
```

---

## Task 11: Workspace shell + routing (mount, pages unchanged yet)

Mount the shell at `/`; old routes render the workspace pre-selected. Pages still carry their own forms until Tasks 12-14 — build stays green; the only visible quirk mid-refactor is a tool showing its own location inputs below the context bar.

**Files:**
- Create: `frontend/src/workspace/Workspace.jsx`
- Modify: `frontend/src/App.jsx`
- Delete: `frontend/src/components/NavBar.jsx`, `frontend/src/pages/Home.jsx`

- [ ] **Step 1: Create `Workspace.jsx`**

```jsx
import { useEffect, useState } from 'react'
import { getTrendFilters } from '../api/client'
import { useWorkspace } from './WorkspaceContext'
import ContextBar from './ContextBar'
import ModeToggle from './ModeToggle'
import CropAdvisor from '../pages/CropAdvisor'
import CropRecommender from '../pages/CropRecommender'
import MandiCompare from '../pages/MandiCompare'
import ProfitPlanner from '../pages/ProfitPlanner'
import StateMap from '../pages/StateMap'
import CropAnalyser from '../pages/CropAnalyser'
import RevenueLoss from '../pages/RevenueLoss'
import PriceTrend from '../pages/PriceTrend'
import Forecast from '../pages/Forecast'

const INTENTS = [
  { id: 'grow', label: '🌱 What to grow', tools: [
    { id: 'advisor', label: 'Crop Advisor', C: CropAdvisor },
    { id: 'soil', label: 'Soil Match', C: CropRecommender },
  ] },
  { id: 'sell', label: '💰 Where & when to sell', tools: [
    { id: 'mandi', label: 'Mandi Compare', C: MandiCompare },
    { id: 'profit', label: 'Profit Planner', C: ProfitPlanner },
  ] },
  { id: 'explore', label: '📊 Explore', tools: [
    { id: 'map', label: 'State Map', C: StateMap },
    { id: 'crops', label: 'Crop Analyser', C: CropAnalyser },
    { id: 'revenue', label: 'Revenue Loss', C: RevenueLoss },
    { id: 'trends', label: 'Price Trend', C: PriceTrend },
    { id: 'forecast', label: 'Forecast', C: Forecast },
  ] },
]

export default function Workspace({ initialIntent = 'grow', initialTool = null }) {
  const [states, setStates] = useState([])
  const [intentId, setIntentId] = useState(initialIntent)
  const intent = INTENTS.find((i) => i.id === intentId) || INTENTS[0]
  const [toolId, setToolId] = useState(initialTool || intent.tools[0].id)

  useEffect(() => { getTrendFilters().then((d) => setStates(d.states)).catch(() => {}) }, [])

  const pickIntent = (id) => {
    setIntentId(id)
    setToolId(INTENTS.find((i) => i.id === id).tools[0].id)
  }
  const tool = intent.tools.find((t) => t.id === toolId) || intent.tools[0]
  const Tool = tool.C

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-green-800 text-white px-4 md:px-6 py-3 flex items-center justify-between">
        <span className="font-bold text-green-200">🌾 Agri Market Analyser</span>
        <ModeToggle />
      </header>

      <ContextBar states={states} />

      <nav className="flex gap-2 px-4 md:px-6 pt-3 flex-wrap">
        {INTENTS.map((i) => (
          <button key={i.id} onClick={() => pickIntent(i.id)}
            className={`px-3 py-2 rounded-t-lg text-sm font-medium ${i.id === intentId ? 'bg-white border border-b-0 text-green-800' : 'bg-green-50 text-green-700 hover:bg-green-100'}`}>
            {i.label}
          </button>
        ))}
      </nav>
      <div className="flex gap-3 px-4 md:px-6 border-b text-sm">
        {intent.tools.map((t) => (
          <button key={t.id} onClick={() => setToolId(t.id)}
            className={`py-2 ${t.id === toolId ? 'text-green-800 font-semibold border-b-2 border-green-700' : 'text-gray-500 hover:text-green-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <main className="p-6 flex-1"><Tool /></main>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite `App.jsx`**

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { WorkspaceProvider } from './workspace/WorkspaceContext'
import Workspace from './workspace/Workspace'

// Old routes deep-link into the workspace with the right intent + sub-tab.
const DEEP_LINKS = {
  '/advisor': ['grow', 'advisor'], '/recommend': ['grow', 'soil'],
  '/mandi': ['sell', 'mandi'], '/profit': ['sell', 'profit'],
  '/map': ['explore', 'map'], '/crops': ['explore', 'crops'],
  '/revenue': ['explore', 'revenue'], '/trends': ['explore', 'trends'],
  '/forecast': ['explore', 'forecast'],
}

export default function App() {
  return (
    <BrowserRouter>
      <WorkspaceProvider>
        <Routes>
          <Route path="/" element={<Workspace />} />
          {Object.entries(DEEP_LINKS).map(([path, [i, t]]) => (
            <Route key={path} path={path} element={<Workspace initialIntent={i} initialTool={t} />} />
          ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </WorkspaceProvider>
    </BrowserRouter>
  )
}
```

- [ ] **Step 3: Delete the obsolete files**

```bash
git rm frontend/src/components/NavBar.jsx frontend/src/pages/Home.jsx
```

- [ ] **Step 4: Verify build** — `npm run build` (Expected: succeeds. No remaining imports of NavBar/Home — App.jsx was the only importer.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/workspace/Workspace.jsx frontend/src/App.jsx
git commit -m "feat(workspace): mount intent-tab shell at / with deep-link routes"
```

---

## Task 12: Refactor Crop Advisor to consume context

Remove its own location form, GPS, season, and soil toggle; read them from context. Keep only the Goal selector, the submit button, and results. (This is the largest page change.)

**Files:**
- Modify: `frontend/src/pages/CropAdvisor.jsx`

- [ ] **Step 1: Replace `frontend/src/pages/CropAdvisor.jsx` entirely**

```jsx
import { useState } from 'react'
import { recommendSmart } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'

const GOALS = [
  ['', 'Balanced'], ['max_profit', 'Max Profit'], ['low_risk', 'Low Risk'],
  ['sustainable', 'Sustainable'], ['water_efficient', 'Water Efficient'],
]
const MODULES = [
  ['suitability', 'Soil/Climate', 'bg-emerald-500'],
  ['regional', 'Regional', 'bg-sky-500'],
  ['market', 'Market', 'bg-amber-500'],
  ['weather', 'Weather', 'bg-cyan-500'],
]
const RANK_BADGE = ['bg-green-600', 'bg-green-500', 'bg-green-400', 'bg-gray-400', 'bg-gray-400']
const TREND = { rising: '↗', flat: '→', falling: '↘' }
const trendColor = (t) => (t === 'rising' ? 'text-green-600' : t === 'falling' ? 'text-red-500' : 'text-gray-400')

export default function CropAdvisor() {
  const { state, district, season, lat, lon, mode, soil } = useWorkspace()
  const [goal, setGoal] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null); setLoading(true)
    try {
      const body = { state, top_k: 5 }
      if (district?.trim()) body.district = district.trim()
      if (season && season !== 'Any') body.season = season
      if (goal) body.goal = goal
      if (lat != null && lon != null) { body.lat = lat; body.lon = lon }
      if (mode === 'smart' && soil) body.soil = soil
      setResult(await recommendSmart(body))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed'); setResult(null)
    } finally { setLoading(false) }
  }

  const isSmart = result?.modules_used?.includes('suitability')

  return (
    <div className="max-w-3xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">🌱 Crop Advisor</h1>
      <p className="text-gray-600 mb-4">
        Best crops for your field — regional history, market prices, and live seasonal
        weather. Switch to Smart mode and add soil details for a sharper agronomic match.
      </p>
      {error && <ErrorBanner message={error} />}

      <form onSubmit={submit} className="bg-white border rounded-lg p-4 mb-6 flex flex-wrap items-end gap-3 shadow-sm">
        <label className="text-sm text-gray-700">Goal
          <select value={goal} onChange={(e) => setGoal(e.target.value)}
            className="mt-1 block w-44 border rounded px-2 py-2">
            {GOALS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <button disabled={loading}
          className="bg-green-700 text-white rounded px-5 py-3 font-medium hover:bg-green-800 disabled:opacity-60">
          {loading ? 'Analyzing…' : 'Recommend crops'}
        </button>
        {mode !== 'smart' && (
          <span className="text-xs text-gray-400">Simple Mode · turn on Smart for soil suitability</span>
        )}
      </form>

      {!result && !loading && (
        <div className="text-center text-gray-400 border border-dashed rounded-lg py-10">
          Set your location above, then hit <span className="font-medium text-gray-500">Recommend crops</span>.
        </div>
      )}

      {result && (
        <div>
          <p className="text-xs text-gray-500 mb-3">
            <span className={`inline-block px-2 py-0.5 rounded-full mr-2 ${isSmart ? 'bg-emerald-100 text-emerald-700' : 'bg-sky-100 text-sky-700'}`}>
              {isSmart ? 'Smart Mode' : 'Simple Mode'}
            </span>
            {result.method} fusion ·{' '}
            {Object.entries(result.weights_used).map(([m, w]) =>
              `${MODULES.find((x) => x[0] === m)?.[1] || m} ${Math.round(w * 100)}%`).join(' · ')}
          </p>
          <div className="space-y-3">
            {result.recommendations.map((r, i) => (
              <div key={r.crop}
                className={`p-4 rounded-lg border shadow-sm ${i === 0 ? 'border-green-500 bg-green-50' : 'border-gray-200 bg-white'}`}>
                <div className="flex items-center gap-3 mb-3">
                  <span className={`flex items-center justify-center w-7 h-7 rounded-full text-white text-sm font-bold ${RANK_BADGE[i] || 'bg-gray-400'}`}>
                    {i + 1}
                  </span>
                  <span className="font-bold capitalize text-green-800 text-lg">{r.crop}</span>
                  {i === 0 && <span className="text-xs bg-green-600 text-white px-2 py-0.5 rounded-full">Best pick</span>}
                  <span className="ml-auto text-xs text-gray-400">match {r.score}</span>
                </div>
                {r.traditional?.years_grown > 0 && (
                  <p className="text-sm text-green-800 font-medium mb-1">
                    ✓ Traditional here — grown {r.traditional.years_grown} yr
                    {r.traditional.years_grown > 1 ? 's' : ''} on record
                    {r.traditional.level === 'state' && ' (state-wide)'}
                  </p>
                )}
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-700 mb-2">
                  {r.yield?.predicted_yield != null ? (
                    <span>
                      Predicted yield: <b>~{r.yield.predicted_yield} {r.yield.unit}</b>{' '}
                      <span className={trendColor(r.yield.trend)}>{TREND[r.yield.trend]}</span>
                      {r.yield.traditional_yield != null &&
                        <span className="text-gray-400"> (was ~{r.yield.traditional_yield})</span>}
                    </span>
                  ) : (
                    <span className="text-gray-400">No reliable yield estimate</span>
                  )}
                  {r.price_outlook?.price != null && (
                    <span>
                      Price outlook: <b>₹{r.price_outlook.price}/q</b>{' '}
                      <span className={trendColor(r.price_outlook.trend)}>{TREND[r.price_outlook.trend]}</span>
                      <span className="text-gray-400 text-xs">
                        {' '}{r.price_outlook.source === 'forecast' ? '(forecast)' : '(recent)'}
                      </span>
                    </span>
                  )}
                </div>
                <div className="space-y-1 mb-3 opacity-70">
                  {MODULES.filter(([m]) => m in r.breakdown).map(([m, label, color]) => (
                    <div key={m} className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="w-24 shrink-0">{label}</span>
                      <div className="flex-1 h-2.5 bg-gray-200 rounded-full overflow-hidden">
                        <div className={`h-2.5 rounded-full ${color}`}
                          style={{ width: `${Math.round(r.breakdown[m] * 100)}%` }} />
                      </div>
                      <span className="w-8 text-right tabular-nums">{Math.round(r.breakdown[m] * 100)}</span>
                    </div>
                  ))}
                </div>
                {r.why.map((w) => <p key={w} className="text-sm text-green-700">✓ {w}</p>)}
                {r.cautions.map((c) => <p key={c} className="text-sm text-amber-600">⚠ {c}</p>)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build** — `npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CropAdvisor.jsx
git commit -m "refactor(advisor): read location/season/mode/soil from workspace context"
```

---

## Task 13: Refactor Soil Match (CropRecommender) to consume context soil

Soil Match becomes "predict crop from the shared soil inputs". It reads `soil` from context (filled via the Smart-mode SoilPanel) instead of its own form.

**Files:**
- Modify: `frontend/src/pages/CropRecommender.jsx`

- [ ] **Step 1: Replace `frontend/src/pages/CropRecommender.jsx` entirely**

```jsx
import { useState } from 'react'
import { recommendCrop } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import { DEFAULT_SOIL } from '../workspace/SoilPanel'
import ErrorBanner from '../components/ErrorBanner'

export default function CropRecommender() {
  const { mode, soil, setMode } = useWorkspace()
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      setResult(await recommendCrop(soil || DEFAULT_SOIL))
    } catch (err) {
      setError(err.response?.data?.detail || 'Recommendation failed'); setResult(null)
    }
  }

  return (
    <div className="max-w-3xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">Soil Match</h1>
      <p className="text-gray-600 mb-4">
        Pure soil/climate model: enter your soil values in the <b>Soil details</b> panel
        (Smart mode) above, then match the best crops.
      </p>
      {error && <ErrorBanner message={error} />}

      {mode !== 'smart' ? (
        <div className="border border-dashed rounded-lg p-6 text-center text-gray-500">
          Turn on <b>Smart</b> mode (top-right) to enter soil details, then come back here.
          <div className="mt-3">
            <button onClick={() => setMode('smart')}
              className="bg-green-700 text-white rounded px-4 py-2 text-sm">Switch to Smart</button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="mb-6">
          <button className="bg-green-700 text-white rounded px-5 py-3 font-medium hover:bg-green-800">
            Match crops {soil ? '' : '(using defaults — fill Soil details for accuracy)'}
          </button>
        </form>
      )}

      {result && (
        <div>
          <p className="text-lg mb-3">Best pick for your soil:{' '}
            <span className="font-bold text-green-700 capitalize">{result.top.crop}</span>{' '}
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

- [ ] **Step 2: Verify build** — `npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CropRecommender.jsx
git commit -m "refactor(soil-match): drive from shared soil context"
```

---

## Task 14: Refactor location/crop-consuming tools

Five small edits so Profit/Mandi/Price-Trend/Forecast react to the shared location, and the three trends-vocabulary tools (Profit, Price Trend, Crop Analyser) keep a shared `crop` for continuity. Each is its own commit-able change; do them in order.

**Files:** `frontend/src/pages/ProfitPlanner.jsx`, `MandiCompare.jsx`, `PriceTrend.jsx`, `Forecast.jsx`, `CropAnalyser.jsx`

- [ ] **Step 1 — ProfitPlanner: read state + crop from context**

In `ProfitPlanner.jsx`, replace the imports and the local `state`/`commodity` state with context reads.

Replace:
```jsx
import { useState, useEffect } from 'react'
import { planProfit, getPriceReference, getTrendFilters } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
```
with:
```jsx
import { useState, useEffect } from 'react'
import { planProfit, getPriceReference, getTrendFilters } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'
```
Replace:
```jsx
  const [filters, setFilters] = useState({ states: [], commodities: [] })
  const [state, setState] = useState('')
  const [commodity, setCommodity] = useState('')
```
with:
```jsx
  const { state, crop, setCrop } = useWorkspace()
  const [filters, setFilters] = useState({ states: [], commodities: [] })
  const commodity = crop
  const setCommodity = setCrop
```
Then delete the **State** `<label>…</label>` block (the one with `value={state} onChange={(e) => setState(e.target.value)}`) from the JSX, since state now comes from the context bar. Leave the Commodity select (now bound to `crop`/`setCrop`) and everything else unchanged.

Run: `npm run build` → succeeds.
```bash
git add frontend/src/pages/ProfitPlanner.jsx
git commit -m "refactor(profit): use shared state + crop from context"
```

- [ ] **Step 2 — MandiCompare: use precise context coords + shared crop default**

In `MandiCompare.jsx`:

Replace:
```jsx
import { useState, useEffect } from 'react'
import { getMandiCommodities, compareMandis } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'

export default function MandiCompare() {
  const [commodities, setCommodities] = useState([])
  const [commodity, setCommodity] = useState('')
  const [coords, setCoords] = useState(null)
  const [rate, setRate] = useState(2)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)
  const [locMsg, setLocMsg] = useState('')

  useEffect(() => { getMandiCommodities().then(setCommodities).catch(() => {}) }, [])

  const useLocation = () => {
    if (!navigator.geolocation) { setLocMsg('Geolocation not supported on this device.'); return }
    setLocMsg('Getting your location…')
    navigator.geolocation.getCurrentPosition(
      (pos) => { setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }); setLocMsg('') },
      () => setLocMsg('Location permission denied — showing markets by price instead.'),
    )
  }

```
with:
```jsx
import { useState, useEffect } from 'react'
import { getMandiCommodities, compareMandis } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'

export default function MandiCompare() {
  const { lat, lon, area, district } = useWorkspace()
  const coords = lat != null && lon != null ? { lat, lon } : null
  const [commodities, setCommodities] = useState([])
  const [commodity, setCommodity] = useState('')
  const [rate, setRate] = useState(2)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => { getMandiCommodities().then(setCommodities).catch(() => {}) }, [])

```
Then in the JSX, **delete** the `📍 Use my location` button (`<button type="button" onClick={useLocation} …>`) and replace the location-status paragraph:
```jsx
      {(locMsg || coords) && (
        <p className="text-xs text-gray-500 mb-3">
          {coords ? `Using your location (${coords.lat.toFixed(3)}, ${coords.lon.toFixed(3)}). Markets ranked by distance.` : locMsg}
        </p>
      )}
```
with:
```jsx
      {coords ? (
        <p className="text-xs text-gray-500 mb-3">
          Using {area || district || 'your location'} ({coords.lat.toFixed(3)}, {coords.lon.toFixed(3)}). Markets ranked by distance.
        </p>
      ) : (
        <p className="text-xs text-gray-500 mb-3">Set a pincode or use GPS above to rank markets by distance.</p>
      )}
```

Run: `npm run build` → succeeds.
```bash
git add frontend/src/pages/MandiCompare.jsx
git commit -m "refactor(mandi): rank from shared precise coords (pincode/GPS)"
```

- [ ] **Step 3 — PriceTrend: read state + crop from context**

In `PriceTrend.jsx`:

Replace:
```jsx
import { getTrendFilters, getPriceTrend } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function PriceTrend() {
  const [filters, setFilters]     = useState({ states: [], commodities: [] })
  const [state, setState]         = useState('')
  const [commodity, setCommodity] = useState('')
  const [data, setData]           = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setFilters(f)
        if (f.states.length)      setState(f.states[0])
        if (f.commodities.length) setCommodity(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])
```
with:
```jsx
import { getTrendFilters, getPriceTrend } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function PriceTrend() {
  const { state, crop, setCrop } = useWorkspace()
  const [filters, setFilters]     = useState({ states: [], commodities: [] })
  const commodity = crop
  const setCommodity = setCrop
  const [data, setData]           = useState([])
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setFilters(f)
        if (!crop && f.commodities.length) setCrop(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])
```
Then **delete** the State `<select>` block (`value={state} onChange={e => setState(e.target.value)}`) from the JSX — state now comes from the context bar. Keep the commodity select.

Run: `npm run build` → succeeds.
```bash
git add frontend/src/pages/PriceTrend.jsx
git commit -m "refactor(trend): shared state + crop from context"
```

- [ ] **Step 4 — Forecast: seed state from context (models are constrained)**

Forecast only lists states/crops with trained models, so it keeps its own selectors but seeds from context when possible.

In `Forecast.jsx`, add the import and consume context for the initial state:

Replace:
```jsx
import { getForecastAvailable, getPriceTrend, getForecast } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function Forecast() {
```
with:
```jsx
import { getForecastAvailable, getPriceTrend, getForecast } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function Forecast() {
  const { state: ctxState } = useWorkspace()
```
Replace the availability effect's state-selection lines:
```jsx
        const s0 = map['Punjab'] ? 'Punjab' : states[0] || ''
```
with (prefer the context state when it has trained models):
```jsx
        const s0 = map[ctxState] ? ctxState : map['Punjab'] ? 'Punjab' : states[0] || ''
```

Run: `npm run build` → succeeds.
```bash
git add frontend/src/pages/Forecast.jsx
git commit -m "refactor(forecast): seed state from context when a model exists"
```

- [ ] **Step 5 — CropAnalyser: share the selected crop**

In `CropAnalyser.jsx`:

Replace:
```jsx
import { getCropMarkup, getTrendFilters } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function CropAnalyser() {
  const [crops, setCrops]       = useState([])
  const [selected, setSelected] = useState('')
  const [data, setData]         = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setCrops(f.commodities)
        if (f.commodities.length) setSelected(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    setError(null)
    getCropMarkup(selected)
      .then(d => setData([...d].sort((a, b) => b.avg_markup_pct - a.avg_markup_pct)))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selected])
```
with:
```jsx
import { getCropMarkup, getTrendFilters } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function CropAnalyser() {
  const { crop, setCrop } = useWorkspace()
  const selected = crop
  const setSelected = setCrop
  const [crops, setCrops]       = useState([])
  const [data, setData]         = useState([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  useEffect(() => {
    getTrendFilters()
      .then(f => {
        setCrops(f.commodities)
        if (!crop && f.commodities.length) setCrop(f.commodities[0])
      })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    setError(null)
    getCropMarkup(selected)
      .then(d => setData([...d].sort((a, b) => b.avg_markup_pct - a.avg_markup_pct)))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selected])
```

Run: `npm run build` → succeeds.
```bash
git add frontend/src/pages/CropAnalyser.jsx
git commit -m "refactor(crop-analyser): share selected crop via context"
```

---

## Task 15: Full verification & manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Backend suite** — `docker compose up -d` then from `backend/`:

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio -q`
Expected: all green (124 prior + the pincode/coords additions).

- [ ] **Step 2: Frontend build** — from `frontend/`:

Run: `npm run build`
Expected: succeeds, no warnings about missing imports (NavBar/Home gone).

- [ ] **Step 3: Manual browser smoke** (dev servers up: backend `uvicorn`, frontend `npm run dev`)

Verify:
- Context bar: enter pincode `851101` → resolves "Begusarai, Bihar" with ✓; GPS button resolves to a nearby area.
- Switch intent tabs (Grow / Sell / Explore) and sub-tabs → location/season persist across all of them.
- Crop Advisor (Simple) → recommends; flip global **Smart**, the **Soil details** panel appears in the context bar; fill it → Advisor card shows "Smart Mode" and the Soil/Climate bar.
- Mandi Compare picks up the pincode coordinates (status line shows the area + coords).
- Old URL `/profit` opens the workspace on the Sell → Profit Planner sub-tab.

- [ ] **Step 4: Confirm clean tree** (no stray data committed)

Run: `git status`
Expected: working tree clean except the known untracked `data/agri.db` and the 22 MB `all_india_pincode_directory_2025.csv` (both intentionally uncommitted).

---

## Notes for the implementer

- **Crop vocabulary is intentionally split.** `context.crop` carries a *trends-commodities* value, shared cleanly across Profit / Price Trend / Crop Analyser (all use `getTrendFilters().commodities`). Mandi (its own commodity set) and Forecast (trained-model subset) keep their own selectors and only *seed* from context — never assume `context.crop` exists in their lists. Crop Advisor does not read or write `context.crop` (it outputs recommendations, not a single crop).
- **StateMap and RevenueLoss are national/global** — they take no location input and need no refactor; they simply render inside the shell.
- **Mid-refactor redundancy is expected and harmless:** after Task 11 but before Tasks 12-14, a tool may show its own old location inputs beneath the context bar. Build stays green throughout; each task removes one tool's duplication.
- **Simple/Smart scope (deliberate deviation from the spec's illustrative table):** the switch meaningfully drives only the Soil-details panel + Crop Advisor (soil suitability) + Soil Match. Profit Planner and Forecast treat it as a **no-op** — Profit already exposes all its inputs (nothing to hide), and the Forecast horizon is fixed at 6 months by the trained LSTM (can't be adjusted without retraining). This honors the spec's own rule that Smart "only reveals extra controls on tools that have them"; the Profit/Forecast rows in the spec table were illustrative, not required. Revisit if those tools later grow genuine advanced inputs.
- **Routing:** old paths render the workspace **pre-selected** on the right intent/sub-tab (deep-link) rather than issuing an HTTP redirect — same UX, no URL bounce, bookmarks still land correctly.
