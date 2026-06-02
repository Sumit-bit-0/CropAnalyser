# Analyzer Crop-Vocabulary Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every analyzer follow one crop vocabulary driven by the selected/recommended crop, expanding Mandi to ~27 commodities (merge agmarknet) and falling back to state-level prices (with an honest badge) when no market data exists.

**Architecture:** Merge a second mandi source into `mandi_prices`; add a crop-identity resolver in `crop_catalog.py` (normalization-based matching against live commodity lists) as the single source of truth; add a `price_source.py` module owning the `mandi → state_fallback → none` chain; route `/mandi/*` through them; widen the frontend's shared crop picker to the full union and auto-load tools on crop change.

**Tech Stack:** Python 3.10 / FastAPI / pytest / PostgreSQL 16 (Docker) backend; React 19 + Vite + Tailwind frontend.

**Conventions for every task:**
- Run backend from `backend/`. Tests: `venv\Scripts\python.exe -m pytest -p no:asyncio <path>`. Docker Postgres must be up (`docker compose up -d`).
- Every commit message ends with the trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Stage only the exact paths listed (targeted `git add <paths>`; never `git add -A`/`.`/`-u`). Never commit the large source CSVs (`Agriculture_price_dataset.csv`, `agmarknet_india_historical_prices_2024_2025.csv`).

---

### Task 1: Merge agmarknet into the mandi loader

**Files:**
- Modify: `backend/data/load_mandi.py`
- Test: `backend/tests/test_load_mandi.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_load_mandi.py`:

```python
import pandas as pd
from data.load_mandi import clean_mandi, AGMARKNET_COLMAP, merge_dedupe


def test_agmarknet_schema_normalizes_to_mandi_columns():
    raw = pd.DataFrame([{
        "Sl no.": 1, "District Name": "Auraiya", "Market Name": "Achalda",
        "Commodity": "Wheat", "Variety": "Dara", "Grade": "FAQ",
        "Min Price (Rs./Quintal)": 2350, "Max Price (Rs./Quintal)": 2550,
        "Modal Price (Rs./Quintal)": 2450, "Price Date": "05 Apr 2025",
        "State": "Uttar Pradesh",
    }])
    out = clean_mandi(raw, AGMARKNET_COLMAP)
    assert list(out.columns) == ["state", "district", "market", "commodity",
                                 "variety", "grade", "min_price", "max_price",
                                 "modal_price", "price_date"]
    row = out.iloc[0]
    assert row["state"] == "Uttar Pradesh" and row["commodity"] == "Wheat"
    assert row["market"] == "Achalda" and row["modal_price"] == 2450
    assert row["price_date"] == "2025-04-05"


def test_merge_dedupe_keeps_latest_price_date():
    cols = ["state", "district", "market", "commodity", "variety", "grade",
            "min_price", "max_price", "modal_price", "price_date"]
    older = pd.DataFrame([["Punjab", "Ludhiana", "Khanna", "Wheat", "Dara", "FAQ",
                           2000, 2100, 2050, "2025-01-01"]], columns=cols)
    newer = pd.DataFrame([["Punjab", "Ludhiana", "Khanna", "Wheat", "Dara", "FAQ",
                           2200, 2300, 2250, "2025-06-01"]], columns=cols)
    out = merge_dedupe([older, newer])
    assert len(out) == 1
    assert out.iloc[0]["modal_price"] == 2250  # latest kept
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_load_mandi.py -v`
Expected: FAIL — `ImportError: cannot import name 'AGMARKNET_COLMAP'` / `merge_dedupe`.

- [ ] **Step 3: Implement in `backend/data/load_mandi.py`**

Change `clean_mandi` to accept a colmap, add `AGMARKNET_COLMAP`, add `merge_dedupe`, and rewrite `__main__` to load + merge both sources. Replace the existing `clean_mandi` and `__main__` block:

```python
COLMAP = {
    "STATE": "state", "District Name": "district", "Market Name": "market",
    "Commodity": "commodity", "Variety": "variety", "Grade": "grade",
    "Min_Price": "min_price", "Max_Price": "max_price", "Modal_Price": "modal_price",
    "Price Date": "price_date",
}

AGMARKNET_COLMAP = {
    "State": "state", "District Name": "district", "Market Name": "market",
    "Commodity": "commodity", "Variety": "variety", "Grade": "grade",
    "Min Price (Rs./Quintal)": "min_price", "Max Price (Rs./Quintal)": "max_price",
    "Modal Price (Rs./Quintal)": "modal_price", "Price Date": "price_date",
}

OUT_COLS = ["state", "district", "market", "commodity", "variety", "grade",
            "min_price", "max_price", "modal_price", "price_date"]


def clean_mandi(df: pd.DataFrame, colmap: dict = COLMAP) -> pd.DataFrame:
    df = df.rename(columns=colmap)
    for c in ["state", "district", "market", "commodity", "variety", "grade"]:
        df[c] = df[c].astype(str).str.strip()
    for c in ["min_price", "max_price", "modal_price"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["price_date"] = pd.to_datetime(df["price_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["modal_price", "price_date"])
    df = df[df["modal_price"] > 0]
    return df[OUT_COLS]


def merge_dedupe(frames: list[pd.DataFrame]) -> pd.DataFrame:
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("price_date").drop_duplicates(
        subset=["state", "district", "market", "commodity", "variety"], keep="last"
    )
    return combined.reset_index(drop=True)
```

Replace the `if __name__ == "__main__":` block:

```python
DEFAULT_CURRENT = r"E:\DataSETAgri\Agriculture_price_dataset.csv"
DEFAULT_AGMARKNET = (r"E:\DataSETAgri\agmarknet-india-commodity-prices-2024-2025"
                     r"\agmarknet_india_historical_prices_2024_2025.csv")

if __name__ == "__main__":
    current_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CURRENT
    agmarknet_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_AGMARKNET
    frames = []
    print(f"Reading current source {current_path} ...")
    frames.append(clean_mandi(pd.read_csv(current_path), COLMAP))
    print(f"Reading agmarknet {agmarknet_path} ...")
    frames.append(clean_mandi(pd.read_csv(agmarknet_path), AGMARKNET_COLMAP))
    clean = merge_dedupe(frames)
    print(f"Merged clean rows: {len(clean):,} | commodities: {clean['commodity'].nunique()}")
    create_table()
    insert(clean)
    print("Done. mandi_prices populated.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_load_mandi.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Re-ingest and verify commodity count grew**

Run: `venv\Scripts\python.exe -m data.load_mandi`
Then: `venv\Scripts\python.exe -c "from database import query; d=query('SELECT DISTINCT commodity FROM mandi_prices'); print(len(d), sorted(d['commodity'].tolist()))"`
Expected: ~27 commodities, list includes `Maize`, `Onion`, `Potato`, `Tomato`, `Wheat`.

- [ ] **Step 6: Commit**

```bash
git add backend/data/load_mandi.py backend/tests/test_load_mandi.py
git commit -m "feat: merge agmarknet source into mandi_prices (5->~27 commodities)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: State-name normalization helper

**Files:**
- Modify: `backend/analysis/geo.py`
- Test: `backend/tests/test_normalize_state.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_normalize_state.py`:

```python
from analysis.geo import normalize_state


def test_spelling_and_alias_variants_collapse():
    assert normalize_state("Orissa") == normalize_state("Odisha")
    assert normalize_state("Tamilnadu") == normalize_state("Tamil Nadu")
    assert normalize_state("Chattisgarh") == normalize_state("Chhattisgarh")
    assert normalize_state("Gao") == normalize_state("Goa")
    assert normalize_state("Nct Of Delhi") == normalize_state("Delhi")
    assert normalize_state("Uttrakhand") == normalize_state("Uttarakhand")
    assert normalize_state("Jammu & Kashmir") == normalize_state("Jammu and Kashmir")


def test_plain_state_normalizes_stably():
    assert normalize_state("Punjab") == normalize_state(" punjab ")
    assert normalize_state("Maharashtra") != normalize_state("Punjab")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_normalize_state.py -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_state'`.

- [ ] **Step 3: Implement in `backend/analysis/geo.py`**

Add after the `in_india` function (added in the earlier pincode fix):

```python
import re

# Map spelling/alias variants to one canonical token. Keys are normalized
# (lowercased, non-alphanumerics stripped); values are the canonical token.
_STATE_ALIASES = {
    "orissa": "odisha",
    "chattisgarh": "chhattisgarh",
    "gao": "goa",
    "nctofdelhi": "delhi",
    "uttrakhand": "uttarakhand",
    "jammukashmir": "jammuandkashmir",
    "pondicherry": "puducherry",
}


def normalize_state(name: str) -> str:
    """Collapse a state's spelling/alias variants to one canonical token, so the
    state-level price fallback can join mandi_prices and prices reliably."""
    n = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return _STATE_ALIASES.get(n, n)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_normalize_state.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/geo.py backend/tests/test_normalize_state.py
git commit -m "feat: add normalize_state for cross-table state matching

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Crop-identity resolver in the catalog

**Files:**
- Modify: `backend/analysis/crop_catalog.py`
- Test: `backend/tests/test_crop_identity.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_crop_identity.py`:

```python
import pytest
import analysis.crop_catalog as cc


@pytest.fixture(autouse=True)
def _fake_commodities(monkeypatch):
    # normalized -> actual, injected so tests never hit the DB
    monkeypatch.setattr(cc, "_MANDI_MAP", {
        "maize": "Maize", "onion": "Onion",
        "arharturredgramwhole": "Arhar (Tur/Red Gram)(Whole)",
    })
    monkeypatch.setattr(cc, "_PRICES_MAP", {
        "maize": "Maize", "onion": "Onion", "arhar": "Arhar",
        "bottlegourd": "Bottle Gourd",   # prices-only, no mandi
    })


def test_resolve_canonical_with_both_vocabularies():
    ident = cc.resolve_crop("maize")
    assert ident.canonical == "maize"
    assert ident.mandi_name == "Maize" and ident.prices_name == "Maize"
    assert ident.has_mandi and ident.has_forecast


def test_resolve_canonical_with_alias_mismatch():
    # pigeonpeas: mandi uses the verbose Arhar string, prices uses "Arhar"
    ident = cc.resolve_crop("pigeonpeas")
    assert ident.mandi_name == "Arhar (Tur/Red Gram)(Whole)"
    assert ident.prices_name == "Arhar"
    assert ident.has_mandi


def test_resolve_prices_only_commodity():
    ident = cc.resolve_crop("Bottle Gourd")
    assert ident.prices_name == "Bottle Gourd"
    assert ident.mandi_name is None and ident.has_mandi is False
    assert ident.has_forecast is True


def test_resolve_unknown_returns_self_identity():
    ident = cc.resolve_crop("Dragonfruit")
    assert ident.mandi_name is None and ident.prices_name is None
    assert ident.has_mandi is False and ident.has_forecast is False


def test_list_all_crops_unions_and_dedupes():
    crops = cc.list_all_crops()
    names = [c.display_name for c in crops]
    assert "Bottle Gourd" in names            # prices-only included
    assert any(c.has_mandi for c in crops)     # mandi crops flagged
    assert len(names) == len(set(names))       # deduped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_crop_identity.py -v`
Expected: FAIL — `AttributeError: module 'analysis.crop_catalog' has no attribute 'resolve_crop'`.

- [ ] **Step 3: Implement in `backend/analysis/crop_catalog.py`**

Add at the top (after the module docstring, before `CANONICAL_CROPS`):

```python
import re
from dataclasses import dataclass


@dataclass
class CropIdentity:
    canonical: str
    display_name: str
    mandi_name: str | None
    prices_name: str | None
    has_mandi: bool
    has_forecast: bool
```

Add at the bottom of the file (after `WHITELIST`, before `validate`):

```python
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# normalized alias -> canonical crop key, built once from the catalog
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _c, _m in CANONICAL_CROPS.items():
    for _a in [_c] + _m["production"] + _m["market"]:
        _ALIAS_TO_CANONICAL[_norm(_a)] = _c

# normalized commodity -> actual DB string; lazily loaded, monkeypatched in tests
_MANDI_MAP: dict[str, str] | None = None
_PRICES_MAP: dict[str, str] | None = None


def _commodity_maps():
    global _MANDI_MAP, _PRICES_MAP
    if _MANDI_MAP is None or _PRICES_MAP is None:
        from database import query
        _MANDI_MAP = {_norm(x): x for x in query("SELECT DISTINCT commodity FROM mandi_prices")["commodity"]}
        _PRICES_MAP = {_norm(x): x for x in query("SELECT DISTINCT commodity FROM prices")["commodity"]}
    return _MANDI_MAP, _PRICES_MAP


def resolve_crop(name: str) -> CropIdentity:
    """Resolve any crop name (canonical, alias, or raw commodity) to its name in
    each tool vocabulary plus availability flags. has_forecast mirrors prices
    presence (forecasts are built on the prices series)."""
    mandi_map, prices_map = _commodity_maps()
    n = _norm(name)
    canonical = _ALIAS_TO_CANONICAL.get(n, (name or "").lower())
    if canonical in CANONICAL_CROPS:
        m = CANONICAL_CROPS[canonical]
        aliases = [canonical] + m["production"] + m["market"]
        display = canonical
    else:
        aliases = [name]
        display = name
    mandi_name = next((mandi_map[_norm(a)] for a in aliases if _norm(a) in mandi_map), None)
    prices_name = next((prices_map[_norm(a)] for a in aliases if _norm(a) in prices_map), None)
    return CropIdentity(canonical=canonical, display_name=display,
                        mandi_name=mandi_name, prices_name=prices_name,
                        has_mandi=mandi_name is not None,
                        has_forecast=prices_name is not None)


def list_all_crops() -> list[CropIdentity]:
    """Deduped union of every crop in the prices and mandi tables, each resolved
    to its identity + availability flags. Powers the shared crop picker."""
    mandi_map, prices_map = _commodity_maps()
    seen: dict[str, CropIdentity] = {}
    for actual in list(prices_map.values()) + list(mandi_map.values()):
        ident = resolve_crop(actual)
        if ident.canonical not in seen:
            seen[ident.canonical] = ident
    return sorted(seen.values(), key=lambda i: i.display_name.lower())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_crop_identity.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/crop_catalog.py backend/tests/test_crop_identity.py
git commit -m "feat: crop-identity resolver (single source of truth)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Price-source fallback module

**Files:**
- Create: `backend/analysis/price_source.py`
- Test: `backend/tests/test_price_source.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_price_source.py`:

```python
import pandas as pd
import analysis.price_source as ps
from analysis.crop_catalog import CropIdentity


def _ident(mandi, prices):
    return CropIdentity("x", "X", mandi, prices,
                        has_mandi=mandi is not None, has_forecast=prices is not None)


def test_returns_mandi_when_market_rows_exist(monkeypatch):
    monkeypatch.setattr(ps, "resolve_crop", lambda c: _ident("Maize", "Maize"))
    monkeypatch.setattr(ps, "compare_markets",
                        lambda *a, **k: [{"market": "Khanna", "net_price": 2100}])
    out = ps.get_market_prices("maize", lat=30.9, lon=75.8, state="Punjab")
    assert out["source"] == "mandi" and out["markets"][0]["market"] == "Khanna"


def test_falls_back_to_state_average(monkeypatch):
    monkeypatch.setattr(ps, "resolve_crop", lambda c: _ident(None, "Bottle Gourd"))
    monkeypatch.setattr(ps, "_state_avg", lambda prices_name, state: 1850.0)
    out = ps.get_market_prices("bottle gourd", state="Maharashtra")
    assert out["source"] == "state_fallback" and out["state_avg"] == 1850.0
    assert out["markets"] == []


def test_returns_none_when_no_data(monkeypatch):
    monkeypatch.setattr(ps, "resolve_crop", lambda c: _ident(None, None))
    out = ps.get_market_prices("dragonfruit", state="Punjab")
    assert out["source"] == "none"


def test_state_avg_matches_via_normalization(monkeypatch):
    # context state "Orissa" must match prices' "Odisha"
    def fake_query(sql, params=None):
        if "DISTINCT state" in sql:
            return pd.DataFrame({"state": ["Odisha", "Punjab"]})
        return pd.DataFrame({"modal_price": [1000.0, 1200.0], "year": [2025, 2025], "month": [4, 5]})
    monkeypatch.setattr(ps, "query", fake_query)
    assert ps._state_avg("Rice", "Orissa") == 1100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_price_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.price_source'`.

- [ ] **Step 3: Implement `backend/analysis/price_source.py`**

```python
"""Resolve market prices for a crop with a graceful fallback chain:
real mandi markets -> state-level average from the prices table -> none.
The one place the fallback lives; api/mandi.py routes through it."""
from analysis.crop_catalog import resolve_crop
from analysis.mandi_compare import compare_markets
from analysis.geo import normalize_state
from database import query


def _state_avg(prices_name: str, state: str):
    """Average modal price for (state, commodity) at the latest available year,
    or None. Joins on a normalized state name so spelling variants match."""
    target = normalize_state(state)
    states = query("SELECT DISTINCT state FROM prices")
    state_map = {normalize_state(s): s for s in states["state"].tolist()}
    actual = state_map.get(target)
    if not actual:
        return None
    df = query(
        """SELECT modal_price, year, month FROM prices
           WHERE LOWER(commodity) = LOWER(?) AND state = ?
           ORDER BY year DESC, month DESC""",
        (prices_name, actual),
    )
    if df.empty:
        return None
    latest_year = df.iloc[0]["year"]
    recent = df[df["year"] == latest_year]
    return round(float(recent["modal_price"].mean()), 2)


def get_market_prices(crop: str, lat=None, lon=None, state=None,
                      rate_per_km: float = 0.0, top_k: int = 10) -> dict:
    ident = resolve_crop(crop)
    if ident.mandi_name:
        markets = compare_markets(ident.mandi_name, lat=lat, lon=lon,
                                  rate_per_km=rate_per_km, top_k=top_k)
        if markets:
            return {"source": "mandi", "markets": markets, "crop": ident.display_name}
    if ident.prices_name and state:
        avg = _state_avg(ident.prices_name, state)
        if avg is not None:
            return {"source": "state_fallback", "markets": [], "state_avg": avg,
                    "state": state, "crop": ident.display_name}
    return {"source": "none", "markets": [], "crop": ident.display_name}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_price_source.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/price_source.py backend/tests/test_price_source.py
git commit -m "feat: price_source fallback chain (mandi -> state avg -> none)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Wire the mandi API through the new layers

**Files:**
- Modify: `backend/api/mandi.py`
- Test: `backend/tests/test_api_mandi.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_api_mandi.py`:

```python
import api.mandi as m
from analysis.crop_catalog import CropIdentity


def test_commodities_returns_union_objects(monkeypatch):
    monkeypatch.setattr(m, "list_all_crops", lambda: [
        CropIdentity("maize", "maize", "Maize", "Maize", True, True),
        CropIdentity("bottlegourd", "Bottle Gourd", None, "Bottle Gourd", False, True),
    ])
    out = m.mandi_commodities()
    assert out[0]["display_name"] == "maize" and out[0]["has_mandi"] is True
    assert out[1]["has_mandi"] is False


def test_compare_delegates_to_price_source(monkeypatch):
    captured = {}
    def fake(crop, lat=None, lon=None, state=None, rate_per_km=0.0, top_k=10):
        captured.update(crop=crop, state=state, lat=lat)
        return {"source": "state_fallback", "markets": [], "state_avg": 1850.0}
    monkeypatch.setattr(m, "get_market_prices", fake)
    out = m.mandi_compare(commodity="Maize", lat=30.9, lon=75.8, state="Punjab",
                          rate_per_km=2.0, top=10)
    assert out["source"] == "state_fallback" and out["state_avg"] == 1850.0
    assert captured["crop"] == "Maize" and captured["state"] == "Punjab"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_api_mandi.py -v`
Expected: FAIL — `AttributeError: module 'api.mandi' has no attribute 'list_all_crops'`.

- [ ] **Step 3: Rewrite `backend/api/mandi.py`**

```python
from dataclasses import asdict
from fastapi import APIRouter, Query
from analysis.crop_catalog import list_all_crops
from analysis.price_source import get_market_prices

router = APIRouter()


@router.get("/mandi/commodities")
def mandi_commodities():
    """Full crop union with per-tool availability flags (powers the picker)."""
    return [asdict(c) for c in list_all_crops()]


@router.get("/mandi/compare")
def mandi_compare(
    commodity: str = Query(...),
    lat: float | None = Query(None),
    lon: float | None = Query(None),
    state: str | None = Query(None),
    rate_per_km: float = Query(0.0, ge=0),
    top: int = Query(10, ge=1, le=50),
):
    return get_market_prices(commodity, lat=lat, lon=lon, state=state,
                             rate_per_km=rate_per_km, top_k=top)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio tests/test_api_mandi.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full backend suite (no regressions)**

Run: `venv\Scripts\python.exe -m pytest -p no:asyncio -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/api/mandi.py backend/tests/test_api_mandi.py
git commit -m "feat: route /mandi through union list + price_source fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Shared crop picker in the context bar

**Files:**
- Create: `frontend/src/workspace/CropPicker.jsx`
- Modify: `frontend/src/workspace/ContextBar.jsx`

> No JS test runner — verify with `npm run build` and the browser smoke in Task 9.

- [ ] **Step 1: Create `frontend/src/workspace/CropPicker.jsx`**

A searchable (datalist-backed) input bound to the shared `context.crop`. Loads the union once. An "est." hint marks crops without live mandi data.

```jsx
import { useEffect, useState } from 'react'
import { getMandiCommodities } from '../api/client'
import { useWorkspace } from './WorkspaceContext'

export default function CropPicker() {
  const { crop, setCrop } = useWorkspace()
  const [crops, setCrops] = useState([])
  const [text, setText] = useState(crop || '')

  useEffect(() => { getMandiCommodities().then(setCrops).catch(() => {}) }, [])
  useEffect(() => { setText(crop || '') }, [crop])

  const commit = (value) => {
    setText(value)
    const match = crops.find((c) => c.display_name.toLowerCase() === value.toLowerCase())
    setCrop(match ? match.display_name : value)
  }

  return (
    <label className="text-sm text-gray-700">Crop
      <input list="crop-options" value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        placeholder="e.g. Maize"
        className="mt-1 block w-44 border rounded px-2 py-2" />
      <datalist id="crop-options">
        {crops.map((c) => (
          <option key={c.display_name} value={c.display_name}>
            {c.has_mandi ? '' : 'est.'}
          </option>
        ))}
      </datalist>
    </label>
  )
}
```

- [ ] **Step 2: Add the picker to `frontend/src/workspace/ContextBar.jsx`**

Import it and place it next to Season. Add the import near the top:

```jsx
import CropPicker from './CropPicker'
```

Insert `<CropPicker />` immediately before the `Season` label inside the flex row:

```jsx
        <LocationPicker states={states} />
        <CropPicker />
        <label className="text-sm text-gray-700">Season
```

- [ ] **Step 3: Verify build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds, no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/workspace/CropPicker.jsx frontend/src/workspace/ContextBar.jsx
git commit -m "feat: shared crop picker (full union) in the context bar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Mandi tool reads shared crop, auto-loads, shows fallback badge

**Files:**
- Modify: `frontend/src/pages/MandiCompare.jsx`

- [ ] **Step 1: Rewrite `frontend/src/pages/MandiCompare.jsx`**

Drop the local commodity `<select>` (the picker is now shared); read `crop` from context; auto-load on `[crop, coords, rate]`; render the `{source, markets, state_avg}` shape with a fallback badge.

```jsx
import { useState, useEffect } from 'react'
import { compareMandis } from '../api/client'
import { useWorkspace } from '../workspace/WorkspaceContext'
import ErrorBanner from '../components/ErrorBanner'

export default function MandiCompare() {
  const { crop, state, lat, lon, area, district } = useWorkspace()
  const coords = lat != null && lon != null ? { lat, lon } : null
  const [rate, setRate] = useState(2)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!crop) { setResult(null); return }
    const params = { commodity: crop, top: 10 }
    if (state) params.state = state
    if (coords) { params.lat = coords.lat; params.lon = coords.lon; params.rate_per_km = Number(rate) }
    let live = true
    compareMandis(params)
      .then((r) => { if (live) { setResult(r); setError(null) } })
      .catch((err) => { if (live) { setError(err.response?.data?.detail || 'Comparison failed'); setResult(null) } })
    return () => { live = false }
  }, [crop, state, lat, lon, rate])

  const markets = result?.markets || []
  const best = markets.find((r) => r.is_best_net)

  return (
    <div className="max-w-4xl w-full">
      <h1 className="text-2xl font-bold text-green-800 mb-1">Mandi Comparison</h1>
      <p className="text-gray-600 mb-4">Nearest markets for your crop, with net price after transport.</p>
      {error && <ErrorBanner message={error} />}

      {!crop && <p className="text-gray-500">Pick a crop above to see market prices.</p>}

      {crop && (
        <label className="text-sm inline-block mb-4">Transport ₹/km/quintal
          <input type="number" step="any" value={rate} onChange={(e) => setRate(e.target.value)}
            className="mt-1 block w-28 border rounded px-2 py-2" />
        </label>
      )}

      {result?.source === 'state_fallback' && (
        <div className="border border-amber-300 bg-amber-50 rounded-lg p-4 mb-3">
          <p className="text-lg">State-level estimate for <b className="capitalize">{result.crop}</b> in {result.state}:{' '}
            <span className="font-bold text-green-700">₹{result.state_avg}/q</span></p>
          <p className="text-xs text-amber-700 mt-1">No live mandi data for this crop in your area — showing the state average instead.</p>
        </div>
      )}

      {result?.source === 'none' && (
        <p className="text-gray-500">No market or state price data for <b className="capitalize">{crop}</b>.</p>
      )}

      {result?.source === 'mandi' && (
        <>
          {coords ? (
            <p className="text-xs text-gray-500 mb-3">Using {area || district || 'your location'} ({coords.lat.toFixed(3)}, {coords.lon.toFixed(3)}). Markets ranked by distance.</p>
          ) : (
            <p className="text-xs text-gray-500 mb-3">Set a pincode or use GPS above to rank markets by distance.</p>
          )}
          {best && (
            <p className="text-lg mb-3">Best net price near you:{' '}
              <span className="font-bold text-green-700">{best.market}</span>{' '}
              — ₹{best.net_price}/q{best.distance_km != null ? ` after ~${best.distance_km} km` : ''}.</p>
          )}
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm border">
              <thead className="bg-green-50 text-left">
                <tr>
                  <th className="px-3 py-2">Market</th><th className="px-3 py-2">District</th>
                  <th className="px-3 py-2">Modal ₹/q</th><th className="px-3 py-2">Distance</th>
                  <th className="px-3 py-2">Transport ₹/q</th><th className="px-3 py-2">Net ₹/q</th>
                </tr>
              </thead>
              <tbody>
                {markets.map((r, i) => (
                  <tr key={i} className={r.is_best_net ? 'bg-green-100 font-medium' : 'border-t'}>
                    <td className="px-3 py-2">{r.market}</td>
                    <td className="px-3 py-2">{r.district}, {r.state}</td>
                    <td className="px-3 py-2">₹{r.modal_price}</td>
                    <td className="px-3 py-2">{r.distance_km != null ? `${r.distance_km} km` : '—'}</td>
                    <td className="px-3 py-2">₹{r.transport_per_q}</td>
                    <td className="px-3 py-2">₹{r.net_price}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/MandiCompare.jsx
git commit -m "feat: mandi tool follows shared crop, auto-loads, shows fallback badge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Advisor recommendation sets the shared crop

**Files:**
- Modify: `frontend/src/pages/CropAdvisor.jsx`

- [ ] **Step 1: Add `setCrop` to the context destructure**

In `frontend/src/pages/CropAdvisor.jsx`, change line 21:

```jsx
  const { state, district, season, lat, lon, mode, soil, setCrop } = useWorkspace()
```

- [ ] **Step 2: Add a "See market & prices" action to each recommendation card**

Inside the recommendation card, right after the closing of the rank/name header row (after the line with `match {r.score}` span's closing `</div>` near line 97), insert a button that sets the shared crop:

```jsx
                <button type="button" onClick={() => setCrop(r.crop)}
                  className="text-xs text-green-700 hover:text-green-900 underline mb-2">
                  See market &amp; prices for {r.crop} →
                </button>
```

- [ ] **Step 3: Verify build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/CropAdvisor.jsx
git commit -m "feat: advisor recommendation sets shared crop for other tools

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: End-to-end smoke verification

**Files:** none (manual verification)

- [ ] **Step 1: Start backend + frontend**

Backend (from `backend/`, Docker Postgres up): `venv\Scripts\python.exe -m uvicorn main:app --reload`
Frontend (from `frontend/`): `npm run dev`

- [ ] **Step 2: Verify crop sync + real mandi data**

In the browser: set location (pincode/GPS), pick **Maize** in the context-bar crop picker, open the Sell → Mandi tool.
Expected: ranked markets table appears (Maize now has data via agmarknet).

- [ ] **Step 3: Verify state-level fallback badge**

Pick a vegetable with no mandi coverage in your state (e.g. **Bottle Gourd**).
Expected: amber "State-level estimate" badge with a single ₹/q figure, no markets table.

- [ ] **Step 4: Verify advisor → picker flow**

Open Grow → Crop Advisor, run a recommendation, click "See market & prices for <crop> →".
Expected: shared crop updates; switching to the Mandi tool shows that crop's data automatically (no extra submit).

- [ ] **Step 5: Final full backend suite**

Run (from `backend/`): `venv\Scripts\python.exe -m pytest -p no:asyncio -q`
Expected: all pass.

---

## Notes for the implementer

- `resolve_crop`/`list_all_crops` cache the distinct commodity lists at module level (`_MANDI_MAP`, `_PRICES_MAP`); tests monkeypatch these to avoid the DB. In a long-running server the cache is populated once at first call — fine, since re-ingest happens offline.
- The picker value passed to `/mandi/compare` is the crop's `display_name` (canonical token for known crops, e.g. `maize`; raw commodity for the rest). `resolve_crop` accepts any alias, so the backend maps it to the right `mandi_name`/`prices_name`.
- Profit/Trends/Forecast already read `context.crop`; they are intentionally left on their existing data paths in this plan (Mandi-only fallback per the spec's Out of Scope).
