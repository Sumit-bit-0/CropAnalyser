# Real-Data Ingestion Pipeline — Design

**Date:** 2026-06-06
**Status:** Approved (design); pending implementation plan
**Phase:** Phase 2 prerequisite — data layer for the food-processing recommender engine

---

## 1. Goal

Replace the Phase 1 seed CSVs (`data/raw/india_district_soil.csv`, `data/raw/processing_units.csv`) with real, Postgres-backed data via one extensible ingestion framework, so the recommender's processing-demand gate and soil signals reflect actual Indian facilities and soil. First pass covers the major agricultural states; remaining states arrive in later passes through the same framework.

This sub-project deliberately **precedes** the engine work (generalized gate, channel comparison). It de-risks everything downstream by establishing trustworthy, provenance-tracked data and the loader contracts the engine will read.

## 2. Background & motivation

Phase 1 shipped a single hardcoded gate (`sugar_mill → sugarcane`, distance-scaled) reading 6 seed sugar mills and 8 seed soil districts from CSV. The Phase 2 reframe identified a **soil-scale blocker**: fine-grained soil for all of India is not obtainable, so soil was downgraded to advisory-text and **processing-industry demand** became the engine's core differentiator (grow-for-industry vs grow-for-mandi).

That makes real, geolocated processing-facility data the highest-leverage asset, with real soil as a secondary advisory input. Both must move off seed CSVs into Postgres (matching the existing `district_crop_history` pattern) before the engine can generalize.

## 3. Scope

**In scope**
- One ingestion framework under `backend/tools/ingest/`.
- Three data domains, unified into Postgres tables: processing facilities (absorbing "industries"), soil nutrients, and the facility→crop taxonomy.
- Hybrid acquisition: API adapters where a real endpoint exists (data.gov.in), manual-curated-CSV adapters where it does not (ISMA, MoFPI, state-signature units).
- Refactor of `soil_nutrients.py` and `demand_gate.py` to read Postgres instead of CSV, preserving their existing return contracts.
- Coverage: **major agri-states first** (~8–10 top agricultural states), all facility types; remaining states deferred to a later pass.

**Out of scope (deferred)**
- The engine changes themselves (generalized multi-crop gate logic, channel comparison, FRP/MSP pricing) — separate later specs.
- Block-level soil granularity (district-level only for now).
- A separate `industries` table — folded into `processing_units`.
- Live scheduled refresh / cron — adapters are re-runnable on demand only.
- NDVI / remote sensing.

## 4. Decisions locked during brainstorming

| Decision | Choice |
|---|---|
| Datasets | All three (processing units, industries, soil) |
| "Industries" modeling | Folded into `processing_units` as additional source adapters, not a separate table |
| Acquisition | Hybrid — per-adapter `method` of `"api"` or `"manual"` |
| Storage | Postgres tables; loaders refactored to query the DB |
| Facility taxonomy | Core staples (sugar→sugarcane, rice mills→paddy, **flour mills→wheat**, oil mills→oilseeds, dal mills→pulses, cotton ginning→cotton) **plus** curated state-signature units (tea, coffee, coir/coconut, spices, etc.) for crops a state is specifically known for |
| Coverage bar | Major agri-states first, phased by geography |
| Architecture | Approach A — unified adapter framework with provenance |

## 5. Architecture

### 5.1 Package layout — `backend/tools/ingest/`

```
tools/ingest/
  __init__.py
  base.py          # SourceAdapter ABC
  schema.py        # CREATE TABLE IF NOT EXISTS for all target tables
  validators.py    # shared validation rules
  registry.py      # name -> adapter instance
  run.py           # CLI entrypoint: python -m tools.ingest.run <name|all>
  adapters/
    __init__.py
    isma_sugar.py
    shc_soil.py
    datagov_mills.py
    mofpi_units.py
    state_signature.py
    facility_crop_seed.py
  _staging/         # GITIGNORED — manual downloads / large raw files land here
```

### 5.2 `SourceAdapter` contract (`base.py`)

```python
class SourceAdapter(ABC):
    source_name: str          # e.g. "isma_sugar"
    target_table: str         # e.g. "processing_units"
    method: str               # "api" | "manual"
    source_ref: str           # API resource id / URL, or staging filename

    @abstractmethod
    def fetch(self) -> object: ...
        # api: HTTP GET (uses DATA_GOV_API_KEY); manual: read _staging/<file>

    @abstractmethod
    def normalize(self, raw) -> pd.DataFrame: ...
        # map source columns to the target table's schema

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> pd.DataFrame: ...
        # apply shared validators; drop/flag bad rows; return clean df

    @abstractmethod
    def load(self, df: pd.DataFrame) -> int: ...
        # idempotent upsert into target_table; return rows loaded
```

### 5.3 Orchestration (`run.py`)

`python -m tools.ingest.run <adapter_name>` or `python -m tools.ingest.run all`:
1. Ensure schema (call `schema.ensure_tables()`).
2. For each selected adapter: `fetch → normalize → validate → load`.
3. Write one `data_provenance` row per adapter run (source, table, method, source_ref, rows_loaded, loaded_at).
4. Print a summary table.

Adapters must be **idempotent**: a second run loads zero net new rows (upsert / delete-by-source-then-insert), so the pipeline is safe to re-run against dev or prod.

## 6. Postgres tables (`schema.py`)

All created with `CREATE TABLE IF NOT EXISTS`, mirroring `database.init_db()`.

### `processing_units`
```sql
CREATE TABLE IF NOT EXISTS processing_units (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    facility_type TEXT NOT NULL,
    name      TEXT NOT NULL,
    state     TEXT NOT NULL,
    district  TEXT,
    lat       REAL NOT NULL,
    lon       REAL NOT NULL,
    crop      TEXT NOT NULL,        -- canonical WHITELIST crop consumed
    source    TEXT NOT NULL,        -- adapter source_name
    source_id TEXT,                 -- stable id from source if available
    loaded_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pu_state ON processing_units(state);
CREATE INDEX IF NOT EXISTS idx_pu_type  ON processing_units(facility_type);
```

### `soil_nutrients`
```sql
CREATE TABLE IF NOT EXISTS soil_nutrients (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state     TEXT NOT NULL,
    district  TEXT,
    N         REAL, P REAL, K REAL, ph REAL,
    source    TEXT NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_soil_state ON soil_nutrients(state);
```

### `facility_crop_map`
```sql
CREATE TABLE IF NOT EXISTS facility_crop_map (
    facility_type TEXT PRIMARY KEY,
    crop          TEXT NOT NULL     -- canonical WHITELIST crop
);
```
Seeded from a small **committed** CSV (`data/raw/facility_crop_map.csv`) via the `facility_crop_seed` adapter. Replaces the hardcoded `GATED_CROPS` dict in `demand_gate.py`.

### `data_provenance`
```sql
CREATE TABLE IF NOT EXISTS data_provenance (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name  TEXT NOT NULL,
    target_table TEXT NOT NULL,
    method       TEXT NOT NULL,
    source_ref   TEXT,
    rows_loaded  INTEGER NOT NULL,
    loaded_at    TIMESTAMP NOT NULL DEFAULT now()
);
```

## 7. Initial adapters

| Adapter | Target table | Method | Notes |
|---|---|---|---|
| `facility_crop_seed` | `facility_crop_map` | manual | committed taxonomy CSV; load first (others depend on the crop mapping) |
| `isma_sugar` | `processing_units` | manual | ISMA mill list → curated `_staging/` CSV; `sugar_mill`→`sugarcane` |
| `shc_soil` | `soil_nutrients` | api | data.gov.in Soil Health Card nutrient resource (keyed) |
| `datagov_mills` | `processing_units` | api | rice / flour / oil / dal mill & cold-storage registries where a data.gov.in resource exists |
| `mofpi_units` | `processing_units` | manual | MoFPI mega food parks / registered units → curated `_staging/` CSV |
| `state_signature` | `processing_units` | manual | curated per-state signature units (tea, coffee, coir/coconut, spices) for the ~8–10 target states |

API adapters read `DATA_GOV_API_KEY` from `.env` (never committed). If the key or a resource is unavailable, the adapter fails loudly with a clear message rather than silently loading nothing.

**Target states (first pass, ~8–10):** Uttar Pradesh, Punjab, Maharashtra, Madhya Pradesh, Karnataka, Gujarat, West Bengal, Bihar, Andhra Pradesh, Tamil Nadu. (Adjustable during planning.)

## 8. Loader refactor

### `analysis/soil_nutrients.py`
- Replace CSV read (`SOIL_CSV`, `_ROWS` cache) with `query("SELECT ... FROM soil_nutrients WHERE ...")`.
- **Preserve** the district→state→national fallback chain and the exact return dict (`{N, P, K, ph, soil_source}`); return `None` when the table is empty/absent (`table_exists` guard).
- Tests updated to seed a temp table / monkeypatch `query` instead of writing a CSV.

### `analysis/demand_gate.py`
- Replace `PROCESSING_CSV` / `_UNITS` cache with a DB query for nearest facility of a given `facility_type`.
- Build `GATED_CROPS` from the `facility_crop_map` table (cached) instead of the hardcoded dict.
- `nearest_facility`, `proximity_factor`, haversine, and the `NEAR_KM/FAR_KM/FLOOR` constants stay unchanged.

## 9. Shared validation (`validators.py`)

- Required columns present for the target table; otherwise raise.
- Drop rows missing `lat`/`lon` (facilities) or all of `N`/`P`/`K` (soil).
- Normalize `state` via `analysis.geo.normalize_state`.
- Dedupe on `(source, source_id)` when `source_id` present, else `(name, lat, lon)`.
- Reject rows whose `lat`/`lon` fall outside the India bounding box (~6–37°N, 68–98°E).
- Map `crop` to a canonical `WHITELIST` crop; unknown crops are flagged (logged) and **not** loaded.
- Loads are idempotent (delete-by-source-then-insert, or upsert), so re-running an adapter does not duplicate rows.

## 10. Testing (TDD)

- **Per adapter:** feed a small raw fixture → assert `normalize()` output shape/values; assert `validate()` drops the bad rows (missing coords, out-of-bbox, unknown crop, unknown state).
- **Framework:** registry resolves names; `run` writes a `data_provenance` row; **idempotency** — running an adapter twice yields no duplicate rows.
- **Loader refactor:** `soil_nutrients` / `demand_gate` query a seeded test table and return the same contract as before.
- **Regression:** the existing `test_bihar_regression.py` cases must still pass with the DB-backed gate (Gaya far-from-mill ≠ sugarcane first; Gopalganj can surface sugarcane).
- Full backend suite stays green.

## 11. Deploy & standing-rule safety

- Large raw downloads live in gitignored `backend/tools/ingest/_staging/` — never committed.
- Only small curated lookups are committed: `data/raw/facility_crop_map.csv` and the `state_signature` seed CSV.
- `DATA_GOV_API_KEY` lives in `.env` (already gitignored).
- Postgres is the runtime source of truth; deployment = run `python -m tools.ingest.run all` against the prod DB.
- Targeted `git add` only; never `-A`. Never commit venv / agri.db / logs / screenshots / staging data.

## 12. Open items / follow-ups

- Block-level soil granularity (later soil pass).
- Remaining (non-major) states — second geographic pass through the same adapters.
- FRP/MSP pricing module + generalized gate + channel comparison — the engine specs that consume this data.
- Bhasini API key (translations) — unrelated external dependency, still pending.
