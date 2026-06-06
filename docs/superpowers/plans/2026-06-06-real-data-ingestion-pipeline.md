# Real-Data Ingestion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase 1 seed CSVs with real, Postgres-backed data via one extensible `tools/ingest/` adapter framework, and refactor `soil_nutrients.py` / `demand_gate.py` to read the DB.

**Architecture:** A `SourceAdapter` ABC (`fetch → normalize → validate → load`) with one adapter per data source, a shared validators module, a schema module (`CREATE TABLE IF NOT EXISTS`), a registry, and a `run.py` CLI that orchestrates and records provenance. Hybrid acquisition: `api` adapters hit data.gov.in (keyed), `manual` adapters read curated CSVs from a gitignored `_staging/` dir. Three Postgres tables (`processing_units`, `soil_nutrients`, `facility_crop_map`) plus `data_provenance`. Loaders refactored to query the DB while preserving their exact return contracts.

**Tech Stack:** Python 3.10, SQLAlchemy (via existing `database.py`), pandas, pytest, FastAPI (unchanged), PostgreSQL 16. Tests run from `backend/` with `venv/Scripts/python.exe -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-06-real-data-ingestion-pipeline-design.md`

---

## Conventions for every task

- **Working dir:** all commands run from `E:\agri-market-analyser\backend`.
- **Python:** use the venv interpreter — `venv/Scripts/python.exe` (PowerShell) — for pytest and scripts.
- **DB access:** import from `database` (`query`, `get_engine`, `table_exists`). `query()` uses `?` placeholders.
- **Commit trailer:** every commit ends with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- **Targeted `git add` only** — never `git add -A`. Never commit `venv/`, `agri.db`, `.env`, `*.log`, screenshots, or anything under `tools/ingest/_staging/`.
- **DB-backed tests** create their own tables and clean up; they must pass on Postgres (the configured `DATABASE_URL`) and not depend on row order.

---

## File Structure

**Create:**
- `backend/tools/ingest/__init__.py` — package marker.
- `backend/tools/ingest/schema.py` — `ensure_tables()`: `CREATE TABLE IF NOT EXISTS` for all four tables.
- `backend/tools/ingest/base.py` — `SourceAdapter` ABC + a `delete_by_source_then_insert` load helper.
- `backend/tools/ingest/validators.py` — shared row validation (state norm, India bbox, crop→WHITELIST, dedupe, required cols).
- `backend/tools/ingest/registry.py` — `ADAPTERS` dict + `get_adapter()` / `all_adapters()`.
- `backend/tools/ingest/run.py` — CLI orchestrator + provenance writer.
- `backend/tools/ingest/adapters/__init__.py`
- `backend/tools/ingest/adapters/facility_crop_seed.py`
- `backend/tools/ingest/adapters/isma_sugar.py`
- `backend/tools/ingest/adapters/shc_soil.py`
- `backend/tools/ingest/adapters/datagov_mills.py`
- `backend/tools/ingest/adapters/mofpi_units.py`
- `backend/tools/ingest/adapters/state_signature.py`
- `backend/tools/ingest/_staging/.gitkeep` — keep the dir; ignore its contents.
- `data/raw/facility_crop_map.csv` — committed taxonomy seed.
- `data/raw/state_signature_units.csv` — committed curated signature units (WHITELIST crops only).
- Tests under `backend/tests/`: `test_ingest_validators.py`, `test_ingest_schema.py`, `test_ingest_base.py`, `test_ingest_run.py`, `test_adapter_facility_crop_seed.py`, `test_adapter_isma_sugar.py`, `test_adapter_shc_soil.py`, `test_adapter_state_signature.py`, `test_soil_nutrients_db.py`, `test_demand_gate_db.py`.

**Modify:**
- `backend/analysis/soil_nutrients.py` — query `soil_nutrients` table instead of CSV.
- `backend/analysis/demand_gate.py` — query `processing_units` + `facility_crop_map` instead of CSV.
- `backend/tests/test_soil_nutrients.py` — re-point fixtures to DB (replaces CSV monkeypatch).
- `.gitignore` (repo root) — ignore `backend/tools/ingest/_staging/`.
- `.env.example` (if present) / spec note — document `DATA_GOV_API_KEY`.

---

## Task 0: Package skeleton, .gitignore, staging dir

**Files:**
- Create: `backend/tools/ingest/__init__.py`, `backend/tools/ingest/adapters/__init__.py`, `backend/tools/ingest/_staging/.gitkeep`
- Modify: `.gitignore` (repo root)

- [ ] **Step 1: Create the package files**

`backend/tools/ingest/__init__.py`:
```python
"""Real-data ingestion framework: fetch -> normalize -> validate -> load."""
```

`backend/tools/ingest/adapters/__init__.py`:
```python
"""Source adapters, one module per data source."""
```

`backend/tools/ingest/_staging/.gitkeep`:
```
# Manual downloads land here. Contents are gitignored; this file keeps the dir.
```

- [ ] **Step 2: Ignore staging contents**

Append to repo-root `.gitignore`:
```
# Real-data ingestion: manual downloads / large raw source files (never commit)
backend/tools/ingest/_staging/*
!backend/tools/ingest/_staging/.gitkeep
```

- [ ] **Step 3: Verify the package imports**

Run: `venv/Scripts/python.exe -c "import tools.ingest; import tools.ingest.adapters; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/tools/ingest/__init__.py backend/tools/ingest/adapters/__init__.py backend/tools/ingest/_staging/.gitkeep .gitignore
git commit -m "feat(ingest): package skeleton + gitignore staging dir"
```

---

## Task 1: Schema module

**Files:**
- Create: `backend/tools/ingest/schema.py`
- Test: `backend/tests/test_ingest_schema.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ingest_schema.py`:
```python
from database import get_engine, table_exists
from tools.ingest import schema


def test_ensure_tables_creates_all_four():
    schema.ensure_tables()
    for t in ("processing_units", "soil_nutrients",
              "facility_crop_map", "data_provenance"):
        assert table_exists(t)


def test_ensure_tables_is_idempotent():
    schema.ensure_tables()
    schema.ensure_tables()  # second call must not raise
    assert table_exists("processing_units")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_ingest_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.ingest.schema'`

- [ ] **Step 3: Write the implementation**

`backend/tools/ingest/schema.py`:
```python
"""DDL for the ingestion target tables. Mirrors database.init_db() style:
CREATE TABLE IF NOT EXISTS, run idempotently."""
from sqlalchemy import text

from database import get_engine

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS processing_units (
        id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        facility_type TEXT NOT NULL,
        name      TEXT NOT NULL,
        state     TEXT NOT NULL,
        district  TEXT,
        lat       REAL NOT NULL,
        lon       REAL NOT NULL,
        crop      TEXT NOT NULL,
        source    TEXT NOT NULL,
        source_id TEXT,
        loaded_at TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pu_state ON processing_units(state)",
    "CREATE INDEX IF NOT EXISTS idx_pu_type  ON processing_units(facility_type)",
    """
    CREATE TABLE IF NOT EXISTS soil_nutrients (
        id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        state     TEXT NOT NULL,
        district  TEXT,
        N REAL, P REAL, K REAL, ph REAL,
        source    TEXT NOT NULL,
        loaded_at TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_soil_state ON soil_nutrients(state)",
    """
    CREATE TABLE IF NOT EXISTS facility_crop_map (
        crop          TEXT PRIMARY KEY,
        facility_type TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_provenance (
        id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        source_name  TEXT NOT NULL,
        target_table TEXT NOT NULL,
        method       TEXT NOT NULL,
        source_ref   TEXT,
        rows_loaded  INTEGER NOT NULL,
        loaded_at    TIMESTAMP NOT NULL DEFAULT now()
    )
    """,
]


def ensure_tables() -> None:
    with get_engine().begin() as conn:
        for stmt in _DDL:
            conn.execute(text(stmt))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_ingest_schema.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/schema.py backend/tests/test_ingest_schema.py
git commit -m "feat(ingest): schema.ensure_tables for the four target tables"
```

---

## Task 2: Shared validators

**Files:**
- Create: `backend/tools/ingest/validators.py`
- Test: `backend/tests/test_ingest_validators.py`

India bbox: lat 6.0–37.5, lon 68.0–97.5.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ingest_validators.py`:
```python
import pandas as pd
from tools.ingest import validators as v


def test_in_india_bbox():
    assert v.in_india_bbox(26.47, 84.43) is True   # Gopalganj, Bihar
    assert v.in_india_bbox(0.0, 0.0) is False
    assert v.in_india_bbox(51.5, -0.1) is False     # London


def test_validate_facilities_drops_bad_rows():
    df = pd.DataFrame([
        {"facility_type": "sugar_mill", "name": "A", "state": "Bihar",
         "district": "Gopalganj", "lat": 26.47, "lon": 84.43,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "1"},
        # missing lat -> dropped
        {"facility_type": "sugar_mill", "name": "B", "state": "Bihar",
         "district": "Patna", "lat": None, "lon": 85.1,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "2"},
        # out of bbox -> dropped
        {"facility_type": "sugar_mill", "name": "C", "state": "Bihar",
         "district": "X", "lat": 0.0, "lon": 0.0,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "3"},
        # crop not in WHITELIST -> dropped
        {"facility_type": "tea_factory", "name": "D", "state": "Assam",
         "district": "Jorhat", "lat": 26.75, "lon": 94.2,
         "crop": "tea", "source": "x", "source_id": "4"},
    ])
    out = v.validate_facilities(df)
    assert list(out["name"]) == ["A"]
    assert out.iloc[0]["state"] == "Bihar"  # normalized


def test_validate_facilities_dedupes():
    df = pd.DataFrame([
        {"facility_type": "sugar_mill", "name": "A", "state": "Bihar",
         "district": "Gopalganj", "lat": 26.47, "lon": 84.43,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "1"},
        {"facility_type": "sugar_mill", "name": "A-dup", "state": "Bihar",
         "district": "Gopalganj", "lat": 26.47, "lon": 84.43,
         "crop": "sugarcane", "source": "isma_sugar", "source_id": "1"},
    ])
    out = v.validate_facilities(df)
    assert len(out) == 1


def test_validate_soil_drops_all_npk_missing():
    df = pd.DataFrame([
        {"state": "Bihar", "district": "Gopalganj", "N": 270, "P": 22,
         "K": 210, "ph": 7.4, "source": "shc_soil"},
        {"state": "Bihar", "district": "Empty", "N": None, "P": None,
         "K": None, "ph": None, "source": "shc_soil"},
    ])
    out = v.validate_soil(df)
    assert list(out["district"]) == ["Gopalganj"]


def test_validate_crop_map_rejects_non_whitelist():
    df = pd.DataFrame([
        {"crop": "sugarcane", "facility_type": "sugar_mill"},
        {"crop": "tea", "facility_type": "tea_factory"},  # not in WHITELIST
    ])
    out = v.validate_crop_map(df)
    assert list(out["crop"]) == ["sugarcane"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_ingest_validators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.ingest.validators'`

- [ ] **Step 3: Write the implementation**

`backend/tools/ingest/validators.py`:
```python
"""Shared row-level validation for ingestion adapters.

All adapters normalize their source into a DataFrame, then call the matching
validate_* function here. Validators drop (never raise on) bad rows, normalize
state names, dedupe, and reject crops outside the canonical WHITELIST so the
downstream engine only ever sees crops it can reason about.
"""
import pandas as pd

from analysis.geo import normalize_state
from analysis.crop_catalog import WHITELIST

LAT_MIN, LAT_MAX = 6.0, 37.5
LON_MIN, LON_MAX = 68.0, 97.5

_WHITELIST = set(WHITELIST)


def in_india_bbox(lat, lon) -> bool:
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def _coerce_float(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def validate_facilities(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a processing_units-shaped frame."""
    required = {"facility_type", "name", "state", "district", "lat", "lon",
                "crop", "source", "source_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"facilities frame missing columns: {sorted(missing)}")
    df = df.copy()
    df = _coerce_float(df, ["lat", "lon"])
    df = df.dropna(subset=["lat", "lon"])
    df = df[df.apply(lambda r: in_india_bbox(r["lat"], r["lon"]), axis=1)]
    df["state"] = df["state"].map(normalize_state)
    df["crop"] = df["crop"].str.strip().str.lower()
    df = df[df["crop"].isin(_WHITELIST)]
    df = df.drop_duplicates(subset=["source", "source_id"])
    df = df.drop_duplicates(subset=["name", "lat", "lon"])
    return df.reset_index(drop=True)


def validate_soil(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a soil_nutrients-shaped frame."""
    required = {"state", "district", "N", "P", "K", "ph", "source"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"soil frame missing columns: {sorted(missing)}")
    df = df.copy()
    df = _coerce_float(df, ["N", "P", "K", "ph"])
    df = df.dropna(subset=["N", "P", "K"], how="all")
    df["state"] = df["state"].map(normalize_state)
    return df.reset_index(drop=True)


def validate_crop_map(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a facility_crop_map-shaped frame (crop -> facility_type)."""
    required = {"crop", "facility_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"crop_map frame missing columns: {sorted(missing)}")
    df = df.copy()
    df["crop"] = df["crop"].str.strip().str.lower()
    df["facility_type"] = df["facility_type"].str.strip()
    df = df[df["crop"].isin(_WHITELIST)]
    df = df.drop_duplicates(subset=["crop"])
    return df.reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_ingest_validators.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/validators.py backend/tests/test_ingest_validators.py
git commit -m "feat(ingest): shared validators (bbox, state norm, dedupe, WHITELIST gate)"
```

---

## Task 3: SourceAdapter base + idempotent load helper

**Files:**
- Create: `backend/tools/ingest/base.py`
- Test: `backend/tests/test_ingest_base.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ingest_base.py`:
```python
import pandas as pd
from sqlalchemy import text

from database import get_engine, query
from tools.ingest import schema, base


class _FakeAdapter(base.SourceAdapter):
    source_name = "fake"
    target_table = "processing_units"
    method = "manual"
    source_ref = "fake.csv"

    def __init__(self, rows):
        self._rows = rows

    def fetch(self):
        return self._rows

    def normalize(self, raw):
        return pd.DataFrame(raw)

    def validate(self, df):
        return df

    def load(self, df):
        return self.delete_by_source_then_insert(df)


def _row(name, source_id):
    return {"facility_type": "sugar_mill", "name": name, "state": "Bihar",
            "district": "Gopalganj", "lat": 26.47, "lon": 84.43,
            "crop": "sugarcane", "source": "fake", "source_id": source_id}


def test_load_then_reload_is_idempotent():
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='fake'"))

    a = _FakeAdapter([_row("M1", "1"), _row("M2", "2")])
    n1 = a.load(a.validate(a.normalize(a.fetch())))
    assert n1 == 2

    a2 = _FakeAdapter([_row("M1", "1"), _row("M2", "2")])
    a2.load(a2.validate(a2.normalize(a2.fetch())))

    cnt = query("SELECT COUNT(*) AS n FROM processing_units WHERE source=?",
                ("fake",)).iloc[0]["n"]
    assert int(cnt) == 2  # not 4 — old rows for this source were replaced

    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='fake'"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_ingest_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.ingest.base'`

- [ ] **Step 3: Write the implementation**

`backend/tools/ingest/base.py`:
```python
"""SourceAdapter contract + a delete-by-source-then-insert load helper that
makes every adapter idempotent (re-running replaces that source's rows)."""
from abc import ABC, abstractmethod

import pandas as pd
from sqlalchemy import text

from database import get_engine

# Columns persisted per target table (drops any extra helper columns).
_TABLE_COLS = {
    "processing_units": ["facility_type", "name", "state", "district",
                         "lat", "lon", "crop", "source", "source_id"],
    "soil_nutrients": ["state", "district", "N", "P", "K", "ph", "source"],
    "facility_crop_map": ["crop", "facility_type"],
}


class SourceAdapter(ABC):
    source_name: str
    target_table: str
    method: str          # "api" | "manual"
    source_ref: str

    @abstractmethod
    def fetch(self): ...

    @abstractmethod
    def normalize(self, raw) -> pd.DataFrame: ...

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> pd.DataFrame: ...

    @abstractmethod
    def load(self, df: pd.DataFrame) -> int: ...

    def delete_by_source_then_insert(self, df: pd.DataFrame) -> int:
        """Replace this source's existing rows with df. Idempotent."""
        cols = _TABLE_COLS[self.target_table]
        df = df[cols].copy()
        with get_engine().begin() as conn:
            if "source" in cols:
                conn.execute(
                    text(f"DELETE FROM {self.target_table} WHERE source=:s"),
                    {"s": self.source_name},
                )
                df.to_sql(self.target_table, conn, if_exists="append",
                          index=False)
            else:
                # facility_crop_map has no source column: full replace.
                conn.execute(text(f"DELETE FROM {self.target_table}"))
                df.to_sql(self.target_table, conn, if_exists="append",
                          index=False)
        return len(df)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_ingest_base.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/base.py backend/tests/test_ingest_base.py
git commit -m "feat(ingest): SourceAdapter ABC + idempotent load helper"
```

---

## Task 4: facility_crop_seed adapter + committed taxonomy CSV

**Files:**
- Create: `data/raw/facility_crop_map.csv`, `backend/tools/ingest/adapters/facility_crop_seed.py`
- Test: `backend/tests/test_adapter_facility_crop_seed.py`

- [ ] **Step 1: Create the committed taxonomy CSV**

`data/raw/facility_crop_map.csv` (crop → facility_type; WHITELIST crops only; tea omitted):
```csv
crop,facility_type
sugarcane,sugar_mill
rice,rice_mill
wheat,flour_mill
mustard,oil_mill
groundnut,oil_mill
soyabean,oil_mill
sunflower,oil_mill
sesamum,oil_mill
pigeonpeas,dal_mill
chickpea,dal_mill
lentil,dal_mill
blackgram,dal_mill
mungbean,dal_mill
mothbeans,dal_mill
cotton,cotton_ginning
coffee,coffee_curing
coconut,coir_mill
turmeric,spice_processing
jute,jute_mill
grapes,winery
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_adapter_facility_crop_seed.py`:
```python
from database import get_engine, query
from sqlalchemy import text
from tools.ingest import schema
from tools.ingest.adapters.facility_crop_seed import FacilityCropSeed


def test_seed_loads_taxonomy():
    schema.ensure_tables()
    a = FacilityCropSeed()
    df = a.validate(a.normalize(a.fetch()))
    # tea must not be present (not in WHITELIST)
    assert "tea" not in set(df["crop"])
    # oilseeds share oil_mill
    oil = df[df["facility_type"] == "oil_mill"]["crop"].tolist()
    assert {"mustard", "groundnut", "soyabean"} <= set(oil)
    n = a.load(df)
    assert n == len(df)
    row = query("SELECT facility_type FROM facility_crop_map WHERE crop=?",
                ("sugarcane",))
    assert row.iloc[0]["facility_type"] == "sugar_mill"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_adapter_facility_crop_seed.py -v`
Expected: FAIL — `ModuleNotFoundError` on `facility_crop_seed`

- [ ] **Step 4: Write the implementation**

`backend/tools/ingest/adapters/facility_crop_seed.py`:
```python
"""Loads the committed facility_crop_map taxonomy (crop -> facility_type).
This is the canonical mapping the demand gate reads; tea is intentionally
absent until 'tea' enters the crop catalog WHITELIST."""
import pandas as pd

from config import DATA_RAW
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_crop_map

CSV = DATA_RAW / "facility_crop_map.csv"


class FacilityCropSeed(SourceAdapter):
    source_name = "facility_crop_seed"
    target_table = "facility_crop_map"
    method = "manual"
    source_ref = "data/raw/facility_crop_map.csv"

    def fetch(self):
        return CSV

    def normalize(self, raw) -> pd.DataFrame:
        return pd.read_csv(raw)

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_crop_map(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_adapter_facility_crop_seed.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add data/raw/facility_crop_map.csv backend/tools/ingest/adapters/facility_crop_seed.py backend/tests/test_adapter_facility_crop_seed.py
git commit -m "feat(ingest): facility_crop_seed adapter + committed taxonomy CSV"
```

---

## Task 5: isma_sugar adapter (manual CSV)

**Files:**
- Create: `backend/tools/ingest/adapters/isma_sugar.py`
- Test: `backend/tests/test_adapter_isma_sugar.py`

This adapter reads a curated staging CSV (a developer drops the ISMA-derived list at `tools/ingest/_staging/isma_sugar.csv`). The test writes a tiny staging file via a monkeypatched path so it never depends on the real download.

Staging CSV columns: `name,state,district,lat,lon` (crop/facility_type are constants the adapter adds).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_adapter_isma_sugar.py`:
```python
import pandas as pd
import tools.ingest.adapters.isma_sugar as mod
from tools.ingest.adapters.isma_sugar import IsmaSugar


def test_isma_normalizes_and_validates(tmp_path, monkeypatch):
    csv = tmp_path / "isma_sugar.csv"
    csv.write_text(
        "name,state,district,lat,lon\n"
        "Gopalganj Sugar Mill,Bihar,Gopalganj,26.47,84.43\n"
        "Bad Mill,Bihar,Nowhere,0.0,0.0\n",          # out of bbox -> dropped
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STAGING_CSV", csv)
    a = IsmaSugar()
    df = a.validate(a.normalize(a.fetch()))
    assert list(df["name"]) == ["Gopalganj Sugar Mill"]
    assert df.iloc[0]["facility_type"] == "sugar_mill"
    assert df.iloc[0]["crop"] == "sugarcane"
    assert df.iloc[0]["source"] == "isma_sugar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_adapter_isma_sugar.py -v`
Expected: FAIL — `ModuleNotFoundError` on `isma_sugar`

- [ ] **Step 3: Write the implementation**

`backend/tools/ingest/adapters/isma_sugar.py`:
```python
"""Sugar mills from a curated ISMA-derived staging CSV
(tools/ingest/_staging/isma_sugar.csv with columns name,state,district,lat,lon).
facility_type/crop are constants. Manual method: download is done by hand,
this adapter only normalizes + loads."""
import pandas as pd

from config import ROOT
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

STAGING_CSV = ROOT / "backend" / "tools" / "ingest" / "_staging" / "isma_sugar.csv"


class IsmaSugar(SourceAdapter):
    source_name = "isma_sugar"
    target_table = "processing_units"
    method = "manual"
    source_ref = "tools/ingest/_staging/isma_sugar.csv (ISMA mill list)"

    def fetch(self):
        if not STAGING_CSV.exists():
            raise FileNotFoundError(
                f"Staging file missing: {STAGING_CSV}. Download the ISMA mill "
                f"list, save as name,state,district,lat,lon, then re-run."
            )
        return STAGING_CSV

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.read_csv(raw)
        df["facility_type"] = "sugar_mill"
        df["crop"] = "sugarcane"
        df["source"] = self.source_name
        df["source_id"] = df["name"].astype(str).str.strip()
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_adapter_isma_sugar.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/adapters/isma_sugar.py backend/tests/test_adapter_isma_sugar.py
git commit -m "feat(ingest): isma_sugar adapter (manual staging CSV)"
```

---

## Task 6: state_signature adapter + committed seed CSV

**Files:**
- Create: `data/raw/state_signature_units.csv`, `backend/tools/ingest/adapters/state_signature.py`
- Test: `backend/tests/test_adapter_state_signature.py`

Curated signature units for the first-pass states. WHITELIST crops only (no tea). Small enough to commit. Columns match `processing_units`: `facility_type,name,state,district,lat,lon,crop`.

- [ ] **Step 1: Create the committed seed CSV**

`data/raw/state_signature_units.csv` (representative known units; coordinates approximate centroids):
```csv
facility_type,name,state,district,lat,lon,crop
coffee_curing,Chikmagalur Coffee Curing Works,Karnataka,Chikkamagaluru,13.32,75.77,coffee
coffee_curing,Coorg Coffee Curing,Karnataka,Kodagu,12.42,75.74,coffee
coffee_curing,Wayanad Coffee Curing,Kerala,Wayanad,11.69,76.13,coffee
coir_mill,Alappuzha Coir Unit,Kerala,Alappuzha,9.49,76.34,coconut
coir_mill,Kozhikode Coir Unit,Kerala,Kozhikode,11.25,75.78,coconut
spice_processing,Kochi Spice Processing,Kerala,Ernakulam,9.98,76.28,turmeric
jute_mill,Hooghly Jute Mill,West Bengal,Hooghly,22.90,88.39,jute
jute_mill,Howrah Jute Mill,West Bengal,Howrah,22.59,88.31,jute
winery,Nashik Winery Cluster,Maharashtra,Nashik,19.99,73.79,grapes
oil_mill,Rajkot Groundnut Oil Mill,Gujarat,Rajkot,22.30,70.80,groundnut
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_adapter_state_signature.py`:
```python
from tools.ingest import schema
from tools.ingest.adapters.state_signature import StateSignature


def test_state_signature_loads_whitelist_crops_only():
    schema.ensure_tables()
    a = StateSignature()
    df = a.validate(a.normalize(a.fetch()))
    assert "tea" not in set(df["crop"])         # tea excluded
    assert "coffee" in set(df["crop"])
    assert df["source"].eq("state_signature").all()
    # every row carries a facility_type and valid coords
    assert df["facility_type"].notna().all()
    n = a.load(df)
    assert n == len(df) and n > 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_adapter_state_signature.py -v`
Expected: FAIL — `ModuleNotFoundError` on `state_signature`

- [ ] **Step 4: Write the implementation**

`backend/tools/ingest/adapters/state_signature.py`:
```python
"""Curated state-signature processing units (coffee curing, coir, spice, jute,
winery, regional oil mills) for the first-pass states. Committed CSV, WHITELIST
crops only — tea units are deferred until 'tea' enters the crop catalog."""
import pandas as pd

from config import DATA_RAW
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

CSV = DATA_RAW / "state_signature_units.csv"


class StateSignature(SourceAdapter):
    source_name = "state_signature"
    target_table = "processing_units"
    method = "manual"
    source_ref = "data/raw/state_signature_units.csv"

    def fetch(self):
        return CSV

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.read_csv(raw)
        df["source"] = self.source_name
        df["source_id"] = df["name"].astype(str).str.strip()
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_adapter_state_signature.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add data/raw/state_signature_units.csv backend/tools/ingest/adapters/state_signature.py backend/tests/test_adapter_state_signature.py
git commit -m "feat(ingest): state_signature adapter + committed seed CSV"
```

---

## Task 7: shc_soil adapter (API, data.gov.in)

**Files:**
- Create: `backend/tools/ingest/adapters/shc_soil.py`
- Test: `backend/tests/test_adapter_shc_soil.py`

The API call (`requests.get`) is isolated in `fetch()`; the test monkeypatches `fetch` so it never hits the network. The data.gov.in Soil Health Card resource returns JSON records with district-level macro-nutrient figures; `normalize()` maps them to the soil schema. Reads `DATA_GOV_API_KEY` from env.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_adapter_shc_soil.py`:
```python
from tools.ingest import schema
from tools.ingest.adapters.shc_soil import ShcSoil


SAMPLE_RECORDS = [
    {"state": "Bihar", "district": "Gopalganj",
     "nitrogen": "270", "phosphorous": "22", "potassium": "210", "ph": "7.4"},
    {"state": "Bihar", "district": "Patna",
     "nitrogen": "", "phosphorous": "", "potassium": "", "ph": ""},  # dropped
]


def test_shc_normalizes_records(monkeypatch):
    schema.ensure_tables()
    a = ShcSoil()
    monkeypatch.setattr(a, "fetch", lambda: SAMPLE_RECORDS)
    df = a.validate(a.normalize(a.fetch()))
    assert list(df["district"]) == ["Gopalganj"]
    assert df.iloc[0]["N"] == 270.0
    assert df.iloc[0]["state"] == "Bihar"
    assert df.iloc[0]["source"] == "shc_soil"
    n = a.load(df)
    assert n == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_adapter_shc_soil.py -v`
Expected: FAIL — `ModuleNotFoundError` on `shc_soil`

- [ ] **Step 3: Write the implementation**

`backend/tools/ingest/adapters/shc_soil.py`:
```python
"""Soil Health Card district macro-nutrients from data.gov.in (keyed API).
fetch() is the only network call; normalize() maps SHC field names to the
soil_nutrients schema. Set DATA_GOV_API_KEY and SHC_RESOURCE_ID in .env."""
import os

import pandas as pd
import requests

from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_soil

BASE = "https://api.data.gov.in/resource"
TIMEOUT = 30

# data.gov.in field -> our column
_FIELD_MAP = {
    "nitrogen": "N", "phosphorous": "P", "potassium": "K", "ph": "ph",
}


class ShcSoil(SourceAdapter):
    source_name = "shc_soil"
    target_table = "soil_nutrients"
    method = "api"
    source_ref = "data.gov.in Soil Health Card resource"

    def fetch(self):
        key = os.getenv("DATA_GOV_API_KEY")
        resource = os.getenv("SHC_RESOURCE_ID")
        if not key or not resource:
            raise RuntimeError(
                "DATA_GOV_API_KEY and SHC_RESOURCE_ID must be set in .env "
                "to fetch Soil Health Card data."
            )
        resp = requests.get(
            f"{BASE}/{resource}",
            params={"api-key": key, "format": "json", "limit": 10000},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("records", [])

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.DataFrame(raw)
        df = df.rename(columns=_FIELD_MAP)
        for col in ("state", "district", "N", "P", "K", "ph"):
            if col not in df.columns:
                df[col] = None
        df["source"] = self.source_name
        return df[["state", "district", "N", "P", "K", "ph", "source"]]

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_soil(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_adapter_shc_soil.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/adapters/shc_soil.py backend/tests/test_adapter_shc_soil.py
git commit -m "feat(ingest): shc_soil adapter (data.gov.in keyed API, network isolated)"
```

---

## Task 8: datagov_mills + mofpi_units adapters (stubs wired to the framework)

**Files:**
- Create: `backend/tools/ingest/adapters/datagov_mills.py`, `backend/tools/ingest/adapters/mofpi_units.py`

These two follow the same shape as `shc_soil` (API) and `isma_sugar`/`state_signature` (manual). They are wired into the framework now so the registry and CLI are complete; their real source mappings are filled as the resource ids / staging files become available. No new test file — they are covered structurally by the registry test (Task 9) and reuse the validated `validate_facilities` path. Keep them minimal (YAGNI): a working `fetch/normalize/validate/load` against the documented input shape.

- [ ] **Step 1: Write `datagov_mills.py`**

`backend/tools/ingest/adapters/datagov_mills.py`:
```python
"""Rice / flour / oil / dal mills and cold storage from data.gov.in registries.
Each registry resource maps to a facility_type via FACILITY_FOR_RESOURCE.
fetch() is the only network call. Set DATA_GOV_API_KEY and MILLS_RESOURCE_ID
(+ MILLS_FACILITY_TYPE, MILLS_CROP) in .env for the resource being loaded."""
import os

import pandas as pd
import requests

from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

BASE = "https://api.data.gov.in/resource"
TIMEOUT = 30


class DatagovMills(SourceAdapter):
    source_name = "datagov_mills"
    target_table = "processing_units"
    method = "api"
    source_ref = "data.gov.in mill/cold-storage registry"

    def fetch(self):
        key = os.getenv("DATA_GOV_API_KEY")
        resource = os.getenv("MILLS_RESOURCE_ID")
        if not key or not resource:
            raise RuntimeError(
                "DATA_GOV_API_KEY and MILLS_RESOURCE_ID must be set in .env."
            )
        resp = requests.get(
            f"{BASE}/{resource}",
            params={"api-key": key, "format": "json", "limit": 10000},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("records", [])

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.DataFrame(raw)
        df["facility_type"] = os.getenv("MILLS_FACILITY_TYPE", "rice_mill")
        df["crop"] = os.getenv("MILLS_CROP", "rice")
        df["source"] = self.source_name
        if "source_id" not in df.columns:
            df["source_id"] = df.get("name", pd.Series(dtype=str)).astype(str)
        for col in ("name", "state", "district", "lat", "lon"):
            if col not in df.columns:
                df[col] = None
        return df[["facility_type", "name", "state", "district",
                   "lat", "lon", "crop", "source", "source_id"]]

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
```

- [ ] **Step 2: Write `mofpi_units.py`**

`backend/tools/ingest/adapters/mofpi_units.py`:
```python
"""MoFPI food parks / registered food-processing units from a curated staging
CSV (columns facility_type,name,state,district,lat,lon,crop). Manual method."""
import pandas as pd

from config import ROOT
from tools.ingest.base import SourceAdapter
from tools.ingest.validators import validate_facilities

STAGING_CSV = ROOT / "backend" / "tools" / "ingest" / "_staging" / "mofpi_units.csv"


class MofpiUnits(SourceAdapter):
    source_name = "mofpi_units"
    target_table = "processing_units"
    method = "manual"
    source_ref = "tools/ingest/_staging/mofpi_units.csv (MoFPI registry)"

    def fetch(self):
        if not STAGING_CSV.exists():
            raise FileNotFoundError(
                f"Staging file missing: {STAGING_CSV}. Save MoFPI units as "
                f"facility_type,name,state,district,lat,lon,crop and re-run."
            )
        return STAGING_CSV

    def normalize(self, raw) -> pd.DataFrame:
        df = pd.read_csv(raw)
        df["source"] = self.source_name
        df["source_id"] = df["name"].astype(str).str.strip()
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_facilities(df)

    def load(self, df: pd.DataFrame) -> int:
        return self.delete_by_source_then_insert(df)
```

- [ ] **Step 3: Verify both import**

Run: `venv/Scripts/python.exe -c "from tools.ingest.adapters.datagov_mills import DatagovMills; from tools.ingest.adapters.mofpi_units import MofpiUnits; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/tools/ingest/adapters/datagov_mills.py backend/tools/ingest/adapters/mofpi_units.py
git commit -m "feat(ingest): datagov_mills + mofpi_units adapters"
```

---

## Task 9: Registry + run.py CLI with provenance

**Files:**
- Create: `backend/tools/ingest/registry.py`, `backend/tools/ingest/run.py`
- Test: `backend/tests/test_ingest_run.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_ingest_run.py`:
```python
from database import get_engine, query
from sqlalchemy import text
from tools.ingest import schema, registry, run


def test_registry_lists_all_adapters():
    names = set(registry.ADAPTERS)
    assert {"facility_crop_seed", "isma_sugar", "shc_soil",
            "datagov_mills", "mofpi_units", "state_signature"} <= names


def test_run_adapter_writes_provenance():
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM data_provenance WHERE source_name='facility_crop_seed'"))
    # facility_crop_seed has no network/staging dependency
    rows = run.run_adapter("facility_crop_seed")
    assert rows > 0
    prov = query(
        "SELECT rows_loaded, target_table, method FROM data_provenance "
        "WHERE source_name=? ORDER BY id DESC", ("facility_crop_seed",))
    assert int(prov.iloc[0]["rows_loaded"]) == rows
    assert prov.iloc[0]["target_table"] == "facility_crop_map"
    assert prov.iloc[0]["method"] == "manual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_ingest_run.py -v`
Expected: FAIL — `ModuleNotFoundError` on `tools.ingest.registry`

- [ ] **Step 3: Write the registry**

`backend/tools/ingest/registry.py`:
```python
"""Maps adapter names to instances. Add new adapters here."""
from tools.ingest.adapters.facility_crop_seed import FacilityCropSeed
from tools.ingest.adapters.isma_sugar import IsmaSugar
from tools.ingest.adapters.shc_soil import ShcSoil
from tools.ingest.adapters.datagov_mills import DatagovMills
from tools.ingest.adapters.mofpi_units import MofpiUnits
from tools.ingest.adapters.state_signature import StateSignature

ADAPTERS = {
    "facility_crop_seed": FacilityCropSeed,
    "isma_sugar": IsmaSugar,
    "shc_soil": ShcSoil,
    "datagov_mills": DatagovMills,
    "mofpi_units": MofpiUnits,
    "state_signature": StateSignature,
}


def get_adapter(name: str):
    if name not in ADAPTERS:
        raise KeyError(f"Unknown adapter '{name}'. Known: {sorted(ADAPTERS)}")
    return ADAPTERS[name]()


def all_adapters():
    return [cls() for cls in ADAPTERS.values()]
```

- [ ] **Step 4: Write run.py**

`backend/tools/ingest/run.py`:
```python
"""CLI orchestrator: fetch -> normalize -> validate -> load, then record
provenance. Usage:
    python -m tools.ingest.run <adapter_name>
    python -m tools.ingest.run all
"""
import sys

from sqlalchemy import text

from database import get_engine
from tools.ingest import schema, registry


def _record_provenance(adapter, rows: int) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("""INSERT INTO data_provenance
                    (source_name, target_table, method, source_ref, rows_loaded)
                    VALUES (:s, :t, :m, :r, :n)"""),
            {"s": adapter.source_name, "t": adapter.target_table,
             "m": adapter.method, "r": adapter.source_ref, "n": rows},
        )


def run_adapter(name: str) -> int:
    schema.ensure_tables()
    adapter = registry.get_adapter(name)
    df = adapter.validate(adapter.normalize(adapter.fetch()))
    rows = adapter.load(df)
    _record_provenance(adapter, rows)
    return rows


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m tools.ingest.run <adapter_name|all>")
        return 2
    target = argv[0]
    names = list(registry.ADAPTERS) if target == "all" else [target]
    for name in names:
        try:
            n = run_adapter(name)
            print(f"[ok]   {name}: {n} rows -> "
                  f"{registry.get_adapter(name).target_table}")
        except Exception as e:  # adapters fail loudly, one bad source doesn't halt 'all'
            print(f"[fail] {name}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_ingest_run.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/tools/ingest/registry.py backend/tools/ingest/run.py backend/tests/test_ingest_run.py
git commit -m "feat(ingest): registry + run.py CLI with provenance"
```

---

## Task 10: Refactor soil_nutrients.py to query the DB

**Files:**
- Modify: `backend/analysis/soil_nutrients.py` (full rewrite of the loader, same public API)
- Create: `backend/tests/test_soil_nutrients_db.py`
- Modify: `backend/tests/test_soil_nutrients.py` (re-point to DB)

`district_soil(state, district=None)` must keep returning `{N,P,K,ph,soil_source}` with `soil_source` in `{"district","state","national"}`, or `None` when there is no data.

- [ ] **Step 1: Write the new DB-backed test**

`backend/tests/test_soil_nutrients_db.py`:
```python
import pytest
from sqlalchemy import text

from database import get_engine, table_exists
from tools.ingest import schema
import analysis.soil_nutrients as sn

ROWS = [
    ("Bihar", "Gopalganj", 270, 22, 210, 7.4),
    ("Bihar", "Patna", 240, 18, 190, 7.6),
    ("Punjab", "Ludhiana", 280, 21, 240, 7.8),
]


@pytest.fixture
def seeded():
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM soil_nutrients WHERE source='test'"))
        for s, d, n, p, k, ph in ROWS:
            c.execute(text("""INSERT INTO soil_nutrients
                (state, district, N, P, K, ph, source)
                VALUES (:s,:d,:n,:p,:k,:ph,'test')"""),
                {"s": s, "d": d, "n": n, "p": p, "k": k, "ph": ph})
    yield
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM soil_nutrients WHERE source='test'"))


def test_district_hit(seeded):
    r = sn.district_soil("Bihar", "Gopalganj")
    assert r["soil_source"] == "district"
    assert r["N"] == 270 and r["ph"] == 7.4


def test_state_fallback(seeded):
    r = sn.district_soil("Bihar", "Nalanda")  # district absent
    assert r["soil_source"] == "state"
    assert r["N"] == 255.0  # mean of 270 + 240


def test_national_fallback(seeded):
    r = sn.district_soil("Kerala", "Wayanad")  # state absent
    assert r["soil_source"] == "national"
    assert set(r) == {"N", "P", "K", "ph", "soil_source"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_soil_nutrients_db.py -v`
Expected: FAIL — current `district_soil` reads CSV, so with no CSV it returns `None` and assertions fail (or `soil_source` mismatch).

- [ ] **Step 3: Rewrite soil_nutrients.py**

`backend/analysis/soil_nutrients.py` (full file):
```python
# backend/analysis/soil_nutrients.py
"""District-level soil nutrients (N, P, K, pH) from the Postgres soil_nutrients
table (loaded by tools/ingest). Lookup by (state, district); fall back to the
state average, then a national average, so every location resolves. Returns
None when the table is empty/absent."""
from database import query, table_exists
from analysis.geo import normalize_state

_FIELDS = ("N", "P", "K", "ph")


def _dnorm(s: str) -> str:
    return (s or "").strip().lower()


def _avg(df) -> dict:
    return {k: round(float(df[k].dropna().mean()), 2) for k in _FIELDS}


def district_soil(state: str, district: str | None = None):
    """{N,P,K,ph, soil_source}; tiers district -> state -> national. None if no data."""
    if not table_exists("soil_nutrients"):
        return None
    s = normalize_state(state)
    if district:
        hit = query(
            "SELECT N, P, K, ph FROM soil_nutrients "
            "WHERE LOWER(state)=LOWER(?) AND LOWER(district)=LOWER(?)",
            (s, district),
        )
        if not hit.empty:
            return {**_avg(hit), "soil_source": "district"}
    st = query("SELECT N, P, K, ph FROM soil_nutrients "
               "WHERE LOWER(state)=LOWER(?)", (s,))
    if not st.empty:
        return {**_avg(st), "soil_source": "state"}
    nat = query("SELECT N, P, K, ph FROM soil_nutrients")
    if nat.empty:
        return None
    return {**_avg(nat), "soil_source": "national"}
```

- [ ] **Step 4: Replace the old CSV-based test file**

Overwrite `backend/tests/test_soil_nutrients.py` to delegate to the DB suite (the CSV monkeypatch path no longer exists):
```python
# Soil nutrient lookups are DB-backed now; see test_soil_nutrients_db.py.
# This module is kept as a thin re-export so old references still collect.
from tests.test_soil_nutrients_db import (  # noqa: F401
    test_district_hit, test_state_fallback, test_national_fallback,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_soil_nutrients_db.py tests/test_soil_nutrients.py -v`
Expected: PASS (district, state, national — collected via both files)

- [ ] **Step 6: Commit**

```bash
git add backend/analysis/soil_nutrients.py backend/tests/test_soil_nutrients_db.py backend/tests/test_soil_nutrients.py
git commit -m "refactor(soil): district_soil reads Postgres soil_nutrients (same contract)"
```

---

## Task 11: Refactor demand_gate.py to query the DB

**Files:**
- Modify: `backend/analysis/demand_gate.py`
- Create: `backend/tests/test_demand_gate_db.py`

Keep `nearest_facility`, `proximity_factor`, `NEAR_KM/FAR_KM/FLOOR` behavior identical. `GATED_CROPS` becomes a function reading `facility_crop_map`. `nearest_facility` reads `processing_units`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_demand_gate_db.py`:
```python
import pytest
from sqlalchemy import text

from database import get_engine
from tools.ingest import schema
import analysis.demand_gate as dg


@pytest.fixture
def seeded():
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='test'"))
        c.execute(text("DELETE FROM facility_crop_map"))
        c.execute(text("INSERT INTO facility_crop_map (crop, facility_type) "
                       "VALUES ('sugarcane','sugar_mill')"))
        c.execute(text("""INSERT INTO processing_units
            (facility_type,name,state,district,lat,lon,crop,source,source_id)
            VALUES ('sugar_mill','Gopalganj Mill','Bihar','Gopalganj',
                    26.47,84.43,'sugarcane','test','1')"""))
    yield
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM processing_units WHERE source='test'"))


def test_gated_crops_from_db(seeded):
    assert dg.gated_crops().get("sugarcane") == "sugar_mill"


def test_nearest_facility_from_db(seeded):
    # near Gopalganj
    near = dg.nearest_facility("sugar_mill", 26.47, 84.43)
    assert near["name"] == "Gopalganj Mill"
    assert near["km"] < 5.0


def test_proximity_factor_unchanged():
    assert dg.proximity_factor(10) == 1.0
    assert dg.proximity_factor(None) == dg.FLOOR
    assert dg.proximity_factor(200) == dg.FLOOR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_demand_gate_db.py -v`
Expected: FAIL — `dg.gated_crops` does not exist; `nearest_facility` reads CSV not DB.

- [ ] **Step 3: Rewrite demand_gate.py**

`backend/analysis/demand_gate.py` (full file):
```python
# backend/analysis/demand_gate.py
"""Processing-demand gate: a crop that must be processed locally (e.g. sugarcane
-> sugar mill) only ranks high near a facility. Facilities live in the Postgres
processing_units table; the crop -> facility_type mapping in facility_crop_map.
Both are loaded by tools/ingest. Generic by facility type."""
from functools import lru_cache

from database import query, table_exists
from analysis.geo import haversine

NEAR_KM, FAR_KM, FLOOR = 50.0, 150.0, 0.2


@lru_cache(maxsize=1)
def gated_crops() -> dict:
    """crop -> required facility_type, from facility_crop_map. {} if absent."""
    if not table_exists("facility_crop_map"):
        return {}
    df = query("SELECT crop, facility_type FROM facility_crop_map")
    return dict(zip(df["crop"], df["facility_type"]))


def nearest_facility(facility_type: str, lat: float, lon: float):
    """{name, km} of the closest facility of this type, or None."""
    if not table_exists("processing_units"):
        return None
    df = query("SELECT name, lat, lon FROM processing_units "
               "WHERE facility_type=?", (facility_type,))
    best, best_d = None, float("inf")
    for r in df.itertuples(index=False):
        d = haversine(lat, lon, float(r.lat), float(r.lon))
        if d < best_d:
            best_d, best = d, r
    if best is None:
        return None
    return {"name": best.name, "km": round(best_d, 1)}


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

Run: `venv/Scripts/python.exe -m pytest tests/test_demand_gate_db.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Update fusion.py's import of GATED_CROPS**

`fusion.py` imports `GATED_CROPS` (a dict) from `demand_gate`. It is now a function `gated_crops()`. Find the usage:

Run: `venv/Scripts/python.exe -m pytest tests/ -k fusion -v` first to see current state, then update `backend/analysis/fusion.py`:
- Change the import `from analysis.demand_gate import GATED_CROPS, nearest_facility, proximity_factor` to `from analysis.demand_gate import gated_crops, nearest_facility, proximity_factor`.
- At the point GATED_CROPS was iterated, call `gated = gated_crops()` once near the top of the scoring function and use `gated` where `GATED_CROPS` was referenced (e.g. `for crop, ftype in gated.items():` or `gated.get(crop)`).

(Read `backend/analysis/fusion.py` to apply the exact substitution — the variable was introduced in Phase 1 Task 5.)

- [ ] **Step 6: Run the fusion + Bihar regression tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_recommend_smart.py tests/test_bihar_regression.py -v`
Expected: PASS — the Bihar regression must still hold (Gaya far-from-mill ≠ sugarcane first; Gopalganj can surface sugarcane), now DB-backed. If `test_bihar_regression.py` was skipif-gated on `district_crop_history`, it also needs `processing_units` + `facility_crop_map` seeded; ensure the test seeds them or runs `run.run_adapter` for the seed adapters in a fixture.

- [ ] **Step 7: Commit**

```bash
git add backend/analysis/demand_gate.py backend/analysis/fusion.py backend/tests/test_demand_gate_db.py
git commit -m "refactor(gate): demand_gate reads processing_units + facility_crop_map from DB"
```

---

## Task 12: Retire seed CSVs + document the pipeline

**Files:**
- Delete: `data/raw/india_district_soil.csv`, `data/raw/processing_units.csv` (superseded by DB + ingest)
- Modify: `.env.example` (or create a short `backend/tools/ingest/README.md`)

- [ ] **Step 1: Confirm nothing still reads the old CSVs**

Run: `venv/Scripts/python.exe -m pytest tests/ -q` and grep:
Run: `grep -rn "india_district_soil\|processing_units.csv\|SOIL_CSV\|PROCESSING_CSV" backend/ --include=*.py`
Expected: no remaining references in `analysis/` or `tests/` (only this plan / docs may mention them).

- [ ] **Step 2: Remove the superseded seed CSVs**

```bash
git rm data/raw/india_district_soil.csv data/raw/processing_units.csv
```

- [ ] **Step 3: Document the pipeline**

Create `backend/tools/ingest/README.md`:
```markdown
# Real-data ingestion

Loads real processing-facility, soil, and facility-crop-taxonomy data into
Postgres, replacing the old seed CSVs.

## Run
    cd backend
    venv/Scripts/python.exe -m tools.ingest.run all      # every adapter
    venv/Scripts/python.exe -m tools.ingest.run isma_sugar

## Adapters
| name | table | method | input |
|---|---|---|---|
| facility_crop_seed | facility_crop_map | manual | data/raw/facility_crop_map.csv (committed) |
| state_signature | processing_units | manual | data/raw/state_signature_units.csv (committed) |
| isma_sugar | processing_units | manual | _staging/isma_sugar.csv |
| mofpi_units | processing_units | manual | _staging/mofpi_units.csv |
| shc_soil | soil_nutrients | api | data.gov.in (DATA_GOV_API_KEY, SHC_RESOURCE_ID) |
| datagov_mills | processing_units | api | data.gov.in (DATA_GOV_API_KEY, MILLS_RESOURCE_ID, MILLS_FACILITY_TYPE, MILLS_CROP) |

## .env keys
    DATA_GOV_API_KEY=...
    SHC_RESOURCE_ID=...
    MILLS_RESOURCE_ID=...
    MILLS_FACILITY_TYPE=rice_mill
    MILLS_CROP=rice

Manual adapters read curated CSVs from `_staging/` (gitignored). `tea` is not
yet in the crop catalog WHITELIST, so tea units are deferred.
```

- [ ] **Step 4: Run the full suite**

Run: `venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all green (no CSV-dependent failures).

- [ ] **Step 5: Commit**

```bash
git add backend/tools/ingest/README.md
git commit -m "chore(ingest): retire seed CSVs, document the pipeline"
```

---

## Task 13: Load real first-pass data + verify end-to-end

This is a data task, not code. It populates the DB from the committed seeds and any staging files the developer has prepared, then verifies the recommender uses real data.

- [ ] **Step 1: Seed the always-available sources**

Run:
```
cd backend
venv/Scripts/python.exe -m tools.ingest.run facility_crop_seed
venv/Scripts/python.exe -m tools.ingest.run state_signature
```
Expected: `[ok] facility_crop_seed: N rows` and `[ok] state_signature: M rows`.

- [ ] **Step 2: Load manual + API sources where inputs exist**

For each source whose staging CSV / API key is ready, run `python -m tools.ingest.run <name>`. Adapters with missing inputs fail loudly — that's expected; load them later. Re-running is idempotent.

- [ ] **Step 3: Verify provenance + counts**

Run: `venv/Scripts/python.exe -c "from database import query; print(query('SELECT source_name, target_table, rows_loaded, loaded_at FROM data_provenance ORDER BY id DESC LIMIT 10'))"`
Expected: one row per successful adapter run.

- [ ] **Step 4: Verify the gate uses real data end-to-end**

Run: `venv/Scripts/python.exe -c "from analysis.demand_gate import gated_crops, nearest_facility; print(gated_crops()); print(nearest_facility('sugar_mill', 24.5, 85.0))"`
Expected: `gated_crops()` includes `sugarcane -> sugar_mill` and the oilseed/dal/etc. mappings; `nearest_facility` returns a real mill + km (or None if no sugar mills loaded yet).

- [ ] **Step 5: Final full suite + summary (no commit — data lives in the DB)**

Run: `venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all green. Report final counts per table and per source. (DB contents are not committed; only code + committed seed CSVs are in git.)

---

## Self-Review (completed by plan author)

**Spec coverage:** §2 framework → Tasks 1–3,9; §3 scope (3 datasets, hybrid, Postgres, major-states) → Tasks 4–8,13; §4 decisions (industries folded, crop-keyed map, tea deferred) → Tasks 4,6 + validators Task 2; §5 layout → Tasks 0–9; §6 tables → Task 1; §7 adapters → Tasks 4–8; §8 loader refactor → Tasks 10–11; §9 validation → Task 2; §10 testing → every task + Task 11 regression; §11 deploy safety (gitignore staging, committed small seeds, .env key) → Tasks 0,4,6,7,12. All covered.

**Placeholder scan:** No TBDs. Task 8 adapters and Task 11 Step 5 reference reading `fusion.py` to apply an exact substitution — the only "read existing file" step, justified because the GATED_CROPS usage was introduced in Phase 1 and must be matched precisely rather than guessed.

**Type consistency:** `facility_crop_map` keyed by `crop` everywhere (schema, validator, seed CSV, demand_gate). `gated_crops()` (function) replaces `GATED_CROPS` (dict) consistently in Tasks 11 + fusion update. `validate_facilities/validate_soil/validate_crop_map` names match between Task 2 and all adapters. `delete_by_source_then_insert` consistent between Task 3 and adapters. `processing_units` columns identical across schema, base `_TABLE_COLS`, validators, and adapters.
