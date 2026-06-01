# Weather Fit Module (CropAdvisor Phase 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live "Weather Fit" scorer to the CropAdvisor fusion ranking that fetches a location's seasonal climate from Open-Meteo and scores each crop against its climatic envelope, running in both Simple and Smart Mode.

**Architecture:** A network client (`weather_client.py`, stdlib `urllib`, cached) fetches seasonal climatology from the Open-Meteo Archive API; a scorer (`weather_fit.py`) compares that against per-crop climate envelopes built from `Crop_recommendation.csv` via a Gaussian z-distance, max-normalized like the other modules; `fusion.py` blends it as a 4th module with the existing per-crop graceful-degradation. Frontend adds one module bar.

**Tech Stack:** Python · stdlib `urllib`/`json`/`functools` · pandas · FastAPI · React 19 + Vite + Tailwind · pytest. Spec: `docs/superpowers/specs/2026-06-01-weather-fit-module-design.md`.

---

## Conventions (read once)

- **Run everything from `backend/`** with the venv Python: `venv\Scripts\python.exe`.
- **Run pytest with** `-p no:asyncio`. Postgres must be up: `docker compose up -d` from project root.
- **No new dependency** — weather uses stdlib `urllib.request`.
- **Catalog:** `from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST`. `CANONICAL_CROPS[c]["suitability"]` is the soil-model label (lowercase) or `None`.
- **Coords:** `from analysis.geo import get_centroid` → `get_centroid(state, district)` returns `(lat, lon)` (district centroid, else state centroid) or `None`.
- **Reference CSV:** `Crop_recommendation.csv`, columns `N,P,K,temperature,humidity,ph,rainfall,label`. Lives at `E:\DataSETAgri\Crop_recommendation.csv` (no `data/raw` copy); resolver tries `config.DATA_RAW` first.
- **Commits use TARGETED paths only** (never `git add -A`) — the tree may carry unrelated work.

## File Structure

**Create:**
- `backend/analysis/weather_client.py` — Open-Meteo archive fetch + season→months + seasonal-climatology aggregation. One responsibility: turn `(lat, lon, season)` into `{temperature, humidity, rainfall}`. No knowledge of crops.
- `backend/analysis/weather_fit.py` — crop climate envelopes + the fusion-shaped `weather_fit_scores(...)`. Depends on `weather_client`, `geo`, `crop_catalog`.
- `backend/tests/test_weather_client.py`, `backend/tests/test_weather_fit.py`.

**Modify:**
- `backend/analysis/fusion.py` — add the weather module + weights + why/cautions.
- `backend/tests/conftest.py` — autouse fixture defaulting the weather module off (network-free tests).
- `backend/tests/test_fusion.py` — add one weather-integration test (existing tests unchanged).
- `frontend/src/pages/CropAdvisor.jsx` — one entry in the `MODULES` array.
- `docs/CROPADVISOR_BUILD.md`, memory files — after build.

---

## Task 1: Season → months mapping (pure)

**Files:**
- Create: `backend/analysis/weather_client.py`
- Test: `backend/tests/test_weather_client.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_weather_client.py
from analysis.weather_client import season_months


def test_kharif_months():
    assert season_months("Kharif") == (6, 7, 8, 9, 10)


def test_rabi_months_wrap_year():
    assert season_months("Rabi") == (11, 12, 1, 2, 3)


def test_any_and_blank_default_to_all_twelve():
    assert season_months("Any") == tuple(range(1, 13))
    assert season_months("") == tuple(range(1, 13))
    assert season_months(None) == tuple(range(1, 13))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_weather_client.py -p no:asyncio -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.weather_client'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/analysis/weather_client.py
"""Live seasonal climatology from the Open-Meteo Archive API (ERA5; free, no key).

Turns (lat, lon, season) into the location's typical {temperature, humidity,
rainfall} for that season, averaged over recent years. Pure stdlib (urllib/json)
so it adds no dependency. Raises WeatherUnavailable on any network/parse failure
so callers can skip the weather term cleanly — it never fabricates data.
"""
import json
import urllib.parse
import urllib.request
from datetime import date
from functools import lru_cache

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
YEARS_BACK = 5      # number of complete past years to average
TIMEOUT = 4         # seconds per HTTP attempt

# India agronomic season -> calendar months. Unknown/blank -> all 12.
_SEASONS = {
    "kharif": (6, 7, 8, 9, 10),
    "rabi": (11, 12, 1, 2, 3),
    "summer": (3, 4, 5, 6),
    "zaid": (3, 4, 5, 6),
    "winter": (12, 1, 2),
    "autumn": (9, 10, 11),
    "whole year": tuple(range(1, 13)),
}


class WeatherUnavailable(Exception):
    """Raised when the archive can't be fetched or has no usable data."""


def season_months(season) -> tuple:
    return _SEASONS.get((season or "").strip().lower(), tuple(range(1, 13)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_weather_client.py -p no:asyncio -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/weather_client.py backend/tests/test_weather_client.py
git commit -m "feat(weather): season->months mapping for the climate client"
```

---

## Task 2: Fetch + aggregate seasonal climatology

**Files:**
- Modify: `backend/analysis/weather_client.py`
- Test: `backend/tests/test_weather_client.py`

`seasonal_climate(lat, lon, season)` → `{"temperature": float, "humidity": float, "rainfall": float}` (rainfall = annual total mm, averaged across years; temperature/humidity = mean over the season's months). A dimension is omitted if the archive lacks it. Cached by rounded coords + season.

- [ ] **Step 1: Write the failing test (append)**

```python
# append to backend/tests/test_weather_client.py
import pytest
import analysis.weather_client as wc


# Two calendar years of canned daily data: Jan all warm, Jun-Oct (kharif) hot,
# precip 1mm/day -> ~365mm/year.
def _fake_daily():
    times, temp, hum, rain = [], [], [], []
    for year in (2023, 2024):
        for month in range(1, 13):
            for day in (1, 15):
                times.append(f"{year}-{month:02d}-{day:02d}")
                temp.append(30.0 if month in (6, 7, 8, 9, 10) else 18.0)
                hum.append(80.0 if month in (6, 7, 8, 9, 10) else 40.0)
                rain.append(2.0)  # mm per sampled day
    return {"daily": {"time": times, "temperature_2m_mean": temp,
                      "relative_humidity_2m_mean": hum, "precipitation_sum": rain}}


def test_seasonal_climate_aggregates_season_months(monkeypatch):
    wc._seasonal_cached.cache_clear()
    monkeypatch.setattr(wc, "_fetch_archive", lambda *a, **k: _fake_daily())
    out = wc.seasonal_climate(25.7, 85.3, "Kharif")
    assert out["temperature"] == pytest.approx(30.0)      # only kharif months
    assert out["humidity"] == pytest.approx(80.0)
    # rainfall is ANNUAL: 24 sampled days/year * 2mm = 48, averaged over 2 yrs = 48
    assert out["rainfall"] == pytest.approx(48.0)


def test_seasonal_climate_raises_on_empty(monkeypatch):
    wc._seasonal_cached.cache_clear()
    monkeypatch.setattr(wc, "_fetch_archive", lambda *a, **k: {"daily": {"time": []}})
    with pytest.raises(wc.WeatherUnavailable):
        wc.seasonal_climate(25.7, 85.3, "Rabi")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_weather_client.py -p no:asyncio -q`
Expected: FAIL with `AttributeError: module 'analysis.weather_client' has no attribute '_fetch_archive'` (or `seasonal_climate`).

- [ ] **Step 3: Write minimal implementation (append to `weather_client.py`)**

```python
def _fetch_archive(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    """GET the Open-Meteo daily archive; raise WeatherUnavailable on any failure."""
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": start_date, "end_date": end_date,
        "daily": "temperature_2m_mean,relative_humidity_2m_mean,precipitation_sum",
        "timezone": "auto",
    })
    url = f"{ARCHIVE_URL}?{params}"
    last = None
    for _ in range(2):  # one retry
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # network, timeout, JSON, HTTP error
            last = e
    raise WeatherUnavailable(f"archive fetch failed: {last}")


def seasonal_climate(lat: float, lon: float, season) -> dict:
    """Location's typical season climate. Cached by ~0.1deg coords + season."""
    return _seasonal_cached(round(lat, 1), round(lon, 1), (season or "").strip().lower())


@lru_cache(maxsize=512)
def _seasonal_cached(lat: float, lon: float, season: str) -> dict:
    months = season_months(season)
    end_year = date.today().year - 1
    start_year = end_year - (YEARS_BACK - 1)
    data = _fetch_archive(lat, lon, f"{start_year}-01-01", f"{end_year}-12-31")
    daily = data.get("daily") or {}
    times = daily.get("time") or []
    if not times:
        raise WeatherUnavailable("empty archive response")

    out: dict = {}
    # temperature & humidity: mean of daily means over the season's months
    for key, name in (("temperature_2m_mean", "temperature"),
                      ("relative_humidity_2m_mean", "humidity")):
        vals = daily.get(key)
        if vals:
            picked = [v for t, v in zip(times, vals)
                      if v is not None and int(t[5:7]) in months]
            if picked:
                out[name] = sum(picked) / len(picked)

    # rainfall: total per calendar year, averaged across years (annual mm)
    rain = daily.get("precipitation_sum")
    if rain:
        per_year: dict = {}
        for t, v in zip(times, rain):
            if v is not None:
                per_year[t[:4]] = per_year.get(t[:4], 0.0) + v
        if per_year:
            out["rainfall"] = sum(per_year.values()) / len(per_year)

    if not out:
        raise WeatherUnavailable("no usable climate variables")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_weather_client.py -p no:asyncio -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/weather_client.py backend/tests/test_weather_client.py
git commit -m "feat(weather): seasonal climatology fetch + aggregation (Open-Meteo archive)"
```

---

## Task 3: Per-crop climate envelopes from the CSV

**Files:**
- Create: `backend/analysis/weather_fit.py`
- Test: `backend/tests/test_weather_fit.py`

`crop_envelopes()` → `{canonical_crop: {"temperature": (mean,std), "humidity": (mean,std), "rainfall": (mean,std)}}` for the 22 crops that have a soil-model label; cached at module scope.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_weather_fit.py
import pytest
from analysis.weather_fit import crop_envelopes, _csv_path


def _csv_exists():
    try:
        _csv_path()
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _csv_exists(), reason="Crop_recommendation.csv not found")
def test_envelopes_cover_soil_crops_with_sane_values():
    env = crop_envelopes()
    assert "rice" in env and "maize" in env
    # rice is warm + very wet in the Kaggle set
    rice_temp_mean, rice_temp_std = env["rice"]["temperature"]
    assert 18 <= rice_temp_mean <= 30
    assert rice_temp_std > 0
    rice_rain_mean, _ = env["rice"]["rainfall"]
    assert rice_rain_mean > 150  # rice rainfall ~200mm in this dataset
    # expansion crops (no soil label) get no envelope
    assert "wheat" not in env and "sugarcane" not in env
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_weather_fit.py -p no:asyncio -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.weather_fit'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/analysis/weather_fit.py
"""Weather Fit scorer for CropAdvisor (fusion module #4).

Scores each crop by how well the location's seasonal climate (from Open-Meteo,
via analysis.weather_client) matches the crop's climatic envelope, derived from
Crop_recommendation.csv. Gaussian z-distance over temperature/humidity/rainfall,
max-normalized to 1.0 like the other modules. Only the 22 soil-model crops have
envelopes; the rest are omitted so fusion degrades them per-crop. Returns {} (the
whole module skipped) when coordinates can't be resolved or the weather call
fails — a recommendation is never blocked.
"""
import math
from pathlib import Path

import pandas as pd

from config import DATA_RAW
from analysis.crop_catalog import CANONICAL_CROPS, WHITELIST
from analysis.geo import get_centroid
from analysis.weather_client import seasonal_climate

_DIMS = ("temperature", "humidity", "rainfall")
_STD_FLOOR = 1e-6
_CSV_CANDIDATES = [DATA_RAW / "Crop_recommendation.csv",
                   Path(r"E:\DataSETAgri\Crop_recommendation.csv")]
_ENVELOPES = None


def _csv_path() -> Path:
    for p in _CSV_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(f"Crop_recommendation.csv not found in {_CSV_CANDIDATES}")


def crop_envelopes() -> dict:
    """Per-crop {dim: (mean, std)} for the 22 soil-model crops. Cached."""
    global _ENVELOPES
    if _ENVELOPES is not None:
        return _ENVELOPES
    df = pd.read_csv(_csv_path())
    df["_label"] = df["label"].astype(str).str.strip().str.lower()
    env = {}
    for crop, meta in CANONICAL_CROPS.items():
        label = meta["suitability"]
        if label is None:
            continue
        sub = df[df["_label"] == label.lower()]
        if sub.empty:
            continue
        env[crop] = {d: (float(sub[d].mean()),
                         max(float(sub[d].std(ddof=0)), _STD_FLOOR)) for d in _DIMS}
    _ENVELOPES = env
    return env
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_weather_fit.py -p no:asyncio -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/weather_fit.py backend/tests/test_weather_fit.py
git commit -m "feat(weather): per-crop climate envelopes from Crop_recommendation.csv"
```

---

## Task 4: `weather_fit_scores()` — Gaussian match + skip logic

**Files:**
- Modify: `backend/analysis/weather_fit.py`
- Test: `backend/tests/test_weather_fit.py`

`weather_fit_scores(state, district, season, crops=None)` → `{crop: {"score": 0-1, "fit": "good|fair|poor", "climate": {dim: value}}}` for crops with envelopes; `{}` if no coords or the weather call fails.

- [ ] **Step 1: Write the failing test (append)**

```python
# append to backend/tests/test_weather_fit.py
import analysis.weather_fit as wf


@pytest.mark.skipif(not _csv_exists(), reason="Crop_recommendation.csv not found")
def test_scores_high_near_envelope_low_far(monkeypatch):
    env = wf.crop_envelopes()
    rice = {d: env["rice"][d][0] for d in ("temperature", "humidity", "rainfall")}
    monkeypatch.setattr(wf, "get_centroid", lambda s, d: (25.7, 85.3))
    # location climate == rice's envelope center -> rice should score the max (1.0)
    monkeypatch.setattr(wf, "seasonal_climate", lambda lat, lon, season: rice)
    out = wf.weather_fit_scores("Bihar", "Begusarai", "Kharif", crops=["rice", "apple"])
    assert out["rice"]["score"] == pytest.approx(1.0)
    assert out["rice"]["fit"] == "good"
    assert out["rice"]["score"] >= out["apple"]["score"]


def test_no_coords_returns_empty(monkeypatch):
    monkeypatch.setattr(wf, "get_centroid", lambda s, d: None)
    assert wf.weather_fit_scores("Nowhere", "Nowhere", "Kharif") == {}


def test_weather_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(wf, "get_centroid", lambda s, d: (25.7, 85.3))
    def boom(*a, **k):
        from analysis.weather_client import WeatherUnavailable
        raise WeatherUnavailable("down")
    monkeypatch.setattr(wf, "seasonal_climate", boom)
    assert wf.weather_fit_scores("Bihar", "Begusarai", "Kharif") == {}


def test_expansion_crop_omitted(monkeypatch):
    monkeypatch.setattr(wf, "get_centroid", lambda s, d: (25.7, 85.3))
    monkeypatch.setattr(wf, "seasonal_climate",
                        lambda lat, lon, season: {"temperature": 25, "humidity": 70, "rainfall": 150})
    out = wf.weather_fit_scores("Bihar", "Begusarai", "Kharif", crops=["rice", "wheat"])
    assert "wheat" not in out  # no envelope -> omitted
    assert "rice" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_weather_fit.py -p no:asyncio -q`
Expected: FAIL with `AttributeError: ... has no attribute 'weather_fit_scores'`.

- [ ] **Step 3: Write minimal implementation (append to `weather_fit.py`)**

```python
def _fit(score: float) -> str:
    return "good" if score >= 0.66 else "fair" if score >= 0.33 else "poor"


def weather_fit_scores(state, district, season, crops=None) -> dict:
    crops = list(crops) if crops else WHITELIST
    coords = get_centroid(state, district)
    if not coords:
        return {}
    try:
        climate = seasonal_climate(coords[0], coords[1], season)
    except Exception:
        return {}  # never block a recommendation on weather

    env = crop_envelopes()
    raw = {}  # crop -> (similarity, climate-detail)
    for c in crops:
        e = env.get(c)
        if not e:
            continue
        dims = [d for d in _DIMS if d in climate]
        if not dims:
            continue
        zs = [(climate[d] - e[d][0]) / e[d][1] for d in dims]
        sim = math.exp(-0.5 * sum(z * z for z in zs) / len(zs))
        raw[c] = (sim, {d: round(climate[d], 1) for d in dims})
    if not raw:
        return {}

    top = max(s for s, _ in raw.values()) or 1.0
    return {c: {"score": round(s / top, 3), "fit": _fit(s / top), "climate": detail}
            for c, (s, detail) in raw.items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest tests/test_weather_fit.py -p no:asyncio -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/weather_fit.py backend/tests/test_weather_fit.py
git commit -m "feat(weather): weather_fit_scores Gaussian envelope match + graceful skip"
```

---

## Task 5: Fusion integration + network-free tests

**Files:**
- Modify: `backend/analysis/fusion.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_fusion.py`

- [ ] **Step 1: Add the autouse fixture so tests never hit the network**

Append to `backend/tests/conftest.py`:

```python
import pytest


@pytest.fixture(autouse=True)
def _disable_live_weather(monkeypatch):
    """Tests must not hit the Open-Meteo network. Default the weather module OFF;
    tests that exercise weather override this with their own monkeypatch."""
    monkeypatch.setattr("analysis.fusion.weather_fit_scores",
                        lambda *a, **k: {}, raising=False)
```

- [ ] **Step 2: Write the failing integration test (append to `test_fusion.py`)**

```python
# append to backend/tests/test_fusion.py
def test_weather_module_integrates_and_degrades_per_crop(monkeypatch):
    import analysis.fusion as fz
    stub = {"rice": {"score": 0.9, "fit": "good", "climate": {}},
            "maize": {"score": 0.5, "fit": "fair", "climate": {}}}
    monkeypatch.setattr(fz, "weather_fit_scores", lambda *a, **k: stub)
    out = fz.recommend("Punjab", "Ludhiana", crops=["rice", "maize", "wheat"], top_k=3)
    assert "weather" in out["modules_used"]
    assert abs(sum(out["weights_used"].values()) - 1.0) < 1e-6
    crops = {r["crop"] for r in out["recommendations"]}
    assert "wheat" in crops  # no weather score -> still recommended (per-crop degrade)
    for r in out["recommendations"]:
        if r["crop"] in stub:
            assert "weather" in r["breakdown"]
```

- [ ] **Step 3: Run the new test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest tests/test_fusion.py::test_weather_module_integrates_and_degrades_per_crop -p no:asyncio -q`
Expected: FAIL — `"weather" not in out["modules_used"]` (KeyError/assert), since fusion doesn't call weather yet.

- [ ] **Step 4: Implement fusion integration**

In `backend/analysis/fusion.py`:

(a) Add the import after the existing analysis imports (near `from analysis.price_outlook import price_outlook`):

```python
from analysis.weather_fit import weather_fit_scores
```

(b) Replace the weights constants:

```python
DEFAULT_WEIGHTS = {"suitability": 0.35, "regional": 0.30, "market": 0.35}
```
with
```python
DEFAULT_WEIGHTS = {"suitability": 0.30, "regional": 0.25, "market": 0.30, "weather": 0.15}
```

and
```python
SIMPLE_MODE_WEIGHTS = {"regional": 0.60, "market": 0.40}
```
with
```python
SIMPLE_MODE_WEIGHTS = {"regional": 0.50, "market": 0.30, "weather": 0.20}
```

(c) In `recommend()`, right after the `if features:` block that adds suitability (before the "2. base weights" comment), add the weather module:

```python
    wf = weather_fit_scores(state, district, season, crops)
    if wf:  # only include when it actually ran (coords ok + API up)
        modules["weather"] = wf
```

(d) In `_why()`, before `return why`, add:

```python
    if "weather" in modules and crop in modules["weather"]:
        if modules["weather"][crop]["score"] >= 0.6:
            why.append("climate well-suited for this season")
```

(e) In `_cautions()`, before `return cautions`, add:

```python
    if ("weather" in modules and crop in modules["weather"]
            and modules["weather"][crop]["score"] <= 0.3):
        cautions.append("seasonal climate is marginal for this crop")
```

- [ ] **Step 5: Run the integration test + the full fusion/enrichment/api suites**

Run: `venv\Scripts\python.exe -m pytest tests/test_fusion.py tests/test_fusion_enrichment.py tests/test_recommend_smart.py -p no:asyncio -q`
Expected: PASS (all). The autouse fixture keeps the pre-existing tests' `modules_used`/`weights_used` exactly as before (weather defaults to `{}`); only the new test enables weather.

- [ ] **Step 6: Commit**

```bash
git add backend/analysis/fusion.py backend/tests/conftest.py backend/tests/test_fusion.py
git commit -m "feat(advisor): blend Weather Fit into fusion (both modes) with graceful degradation"
```

---

## Task 6: Frontend module bar

**Files:**
- Modify: `frontend/src/pages/CropAdvisor.jsx`

The card renders a bar for every module present in `r.breakdown`, so adding one `MODULES` entry is all that's needed.

- [ ] **Step 1: Add the weather entry**

In `frontend/src/pages/CropAdvisor.jsx`, change:

```jsx
const MODULES = [
  ['suitability', 'Soil/Climate', 'bg-emerald-500'],
  ['regional', 'Regional', 'bg-sky-500'],
  ['market', 'Market', 'bg-amber-500'],
]
```
to:
```jsx
const MODULES = [
  ['suitability', 'Soil/Climate', 'bg-emerald-500'],
  ['regional', 'Regional', 'bg-sky-500'],
  ['market', 'Market', 'bg-amber-500'],
  ['weather', 'Weather', 'bg-cyan-500'],
]
```

- [ ] **Step 2: Build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds, no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CropAdvisor.jsx
git commit -m "feat(advisor): show Weather module bar on recommendation cards"
```

---

## Task 7: Full suite gate + live verification

**Files:** none (verification gate).

- [ ] **Step 1: Run the whole backend suite**

Run: `venv\Scripts\python.exe -m pytest tests -p no:asyncio -q`
Expected: PASS — previous 113 + new weather tests (≈ +11), 0 failures. (Ensure Docker Postgres is up first.)

- [ ] **Step 2: Live endpoint check (real Open-Meteo)**

Start the API (`venv\Scripts\python.exe -m uvicorn main:app --port 8000`), then:
`curl -s -X POST localhost:8000/api/recommend/smart -H "Content-Type: application/json" -d "{\"state\":\"Bihar\",\"district\":\"Begusarai\",\"season\":\"Kharif\",\"top_k\":5}"`
Expected: `modules_used` includes `"weather"`; soil-model crops (rice/maize) carry a `breakdown.weather` value; expansion crops (sugarcane/wheat) do not (per-crop degrade). If the network is down, `weather` is simply absent — that is acceptable behavior, but for verification confirm it appears when online.

- [ ] **Step 3: Browser check (optional but recommended)**

Start frontend (`npm run dev`), open `/advisor`, run Bihar/Begusarai (Kharif). Expected: a cyan **Weather** bar on the soil-model crops; muted alongside the other module bars; a "climate well-suited for this season" why-line where the score is high.

- [ ] **Step 4: Commit (only if a test needed adjusting)**

```bash
git add backend/tests
git commit -m "test: keep suite green after Weather Fit integration"
```

---

## Task 8: Docs + memory

**Files:**
- Modify: `docs/CROPADVISOR_BUILD.md`
- Modify: memory `work_journal.md`, `project_agri_analyser.md`

- [ ] **Step 1: Update `docs/CROPADVISOR_BUILD.md`**

Add a section "14. Phase 2 — live Weather Fit term" describing: Open-Meteo archive seasonal climatology (season→months, last 5 yrs, annual rainfall vs season temp/humidity), per-crop Gaussian envelope from `Crop_recommendation.csv`, both-mode weights (Smart suitability/regional/market/weather = .30/.25/.30/.15; Simple regional/market/weather = .50/.30/.20), graceful skip on no-coords/API-down, and the cyan card bar.

- [ ] **Step 2: Update memory**

`work_journal.md`: new dated entry — Weather Fit built (client + scorer + fusion + card), test count, any gotchas. `project_agri_analyser.md`: mark Phase 2 weather as BUILT; note `weather_client.py`/`weather_fit.py` as new assets; NDVI remains Phase 3. Update `MEMORY.md` index line.

- [ ] **Step 3: Commit**

```bash
git add docs/CROPADVISOR_BUILD.md
git commit -m "docs: Phase 2 Weather Fit term"
```

Then run `superpowers:finishing-a-development-branch` to merge.

---

## Done criteria

- `weather_fit_scores` returns max-normalized 0–1 scores for the 22 soil-model crops and `{}` when coords can't resolve or Open-Meteo is unavailable; expansion crops are omitted (never fabricated).
- `/api/recommend/smart` includes a `weather` module (and per-crop `breakdown.weather`) in both Simple and Smart Mode when online; degrades cleanly when offline.
- Full backend suite green; `npm run build` clean; existing fusion/api tests unchanged (network-free via the autouse fixture).
- `/advisor` cards show a cyan Weather bar for soil-model crops.

## Notes / risks

- **No network in tests:** the autouse `_disable_live_weather` fixture is essential — without it, fusion/api tests would hit Open-Meteo (slow, flaky) and `modules_used` assertions would break. Weather-specific tests mock `_fetch_archive`/`seasonal_climate`/`get_centroid` directly.
- **Humidity variable:** if the archive ever rejects `relative_humidity_2m_mean`, `seasonal_climate` simply omits humidity and scoring proceeds on temperature+rainfall (the dims-present intersection handles it) — no crash.
- **Rainfall units:** CSV rainfall is annual mm; the client computes annual precipitation to match. Do not switch it to a seasonal sum or every crop's score will skew.
- **Cache:** `_seasonal_cached` is process-wide; if a long-running server should refresh climatology, restart it (acceptable — climatology barely moves).
