# Real-data ingestion

Loads real processing-facility, soil, and facility-crop-taxonomy data into
Postgres, replacing the old seed CSVs. One adapter per source, all sharing a
`fetch → normalize → validate → load` contract; loads are idempotent
(re-running an adapter replaces only that source's rows).

## Run
    cd backend
    venv/Scripts/python.exe -m tools.ingest.run all          # every adapter
    venv/Scripts/python.exe -m tools.ingest.run isma_sugar   # one adapter

Adapters with a missing input (no staging file / no API key) fail loudly with a
remediation message but do not halt an `all` run.

## Adapters
| name | table | method | input |
|---|---|---|---|
| facility_crop_seed | facility_crop_map | manual | `data/raw/facility_crop_map.csv` (committed) |
| state_signature | processing_units | manual | `data/raw/state_signature_units.csv` (committed) |
| isma_sugar | processing_units | manual | `_staging/isma_sugar.csv` |
| mofpi_units | processing_units | manual | `_staging/mofpi_units.csv` |
| shc_soil | soil_nutrients | api | data.gov.in (`DATA_GOV_API_KEY`, `SHC_RESOURCE_ID`) |
| datagov_mills | processing_units | api | data.gov.in (`DATA_GOV_API_KEY`, `MILLS_RESOURCE_ID`, `MILLS_FACILITY_TYPE`, `MILLS_CROP`) |

## .env keys
    DATA_GOV_API_KEY=...
    SHC_RESOURCE_ID=...
    MILLS_RESOURCE_ID=...
    MILLS_FACILITY_TYPE=rice_mill
    MILLS_CROP=rice

## Notes
- Manual adapters read curated CSVs from `_staging/` (gitignored — never
  committed). Only the small curated lookups in `data/raw/` are committed.
- `tea` is not in the crop catalog WHITELIST, so tea processing units are
  deferred until `tea` is added to `analysis/crop_catalog.py`.
- The demand gate (`analysis/demand_gate.py`) gates a crop only when its
  `facility_type` has at least one facility loaded — a taxonomy entry with no
  facilities yet is a data gap, not a "no demand" signal, so the crop is not
  penalised until its mills are ingested.
- `N`/`P`/`K` are quoted uppercase columns in Postgres; SQL touching
  `soil_nutrients` must quote them (`SELECT "N","P","K" ...`).
- Provenance for every load is recorded in the `data_provenance` table.
