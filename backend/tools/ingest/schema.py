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
        "N" REAL, "P" REAL, "K" REAL, ph REAL,
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
