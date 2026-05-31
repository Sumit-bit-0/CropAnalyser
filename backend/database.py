"""Database access layer.

Backed by SQLAlchemy so the same code runs on PostgreSQL (prod/dev via Docker)
or SQLite (legacy fallback), selected by the DATABASE_URL in config. Call sites
keep using SQLite-style `?` placeholders; `query()` rewrites them to named bind
params transparently, so no callers needed to change during the PG migration.
"""
from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from config import DATABASE_URL, init_dirs


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    init_dirs()
    # pool_pre_ping avoids stale-connection errors after the DB container restarts.
    return create_engine(DATABASE_URL, pool_pre_ping=True, future=True)


def get_connection():
    """A SQLAlchemy Connection. Prefer get_engine() / query() in new code."""
    return get_engine().connect()


def table_exists(name: str) -> bool:
    return inspect(get_engine()).has_table(name)


def _to_named(sql: str, params: tuple) -> tuple[str, dict]:
    """Rewrite positional `?` placeholders into :p0, :p1, ... bind params."""
    parts = sql.split("?")
    if len(parts) - 1 != len(params):
        raise ValueError(
            f"Placeholder count ({len(parts) - 1}) != params ({len(params)})"
        )
    rebuilt = parts[0]
    binds: dict = {}
    for i, tail in enumerate(parts[1:]):
        binds[f"p{i}"] = params[i]
        rebuilt += f":p{i}{tail}"
    return rebuilt, binds


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with get_engine().connect() as conn:
        if params:
            named_sql, binds = _to_named(sql, params)
            return pd.read_sql_query(text(named_sql), conn, params=binds)
        return pd.read_sql_query(text(sql), conn)


def init_db() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prices (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                state TEXT NOT NULL,
                commodity TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                farm_gate_price REAL NOT NULL,
                modal_price REAL NOT NULL
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_state_commodity ON prices(state, commodity)"
        ))


def insert_prices(df: pd.DataFrame) -> None:
    with get_engine().begin() as conn:
        df.to_sql("prices", conn, if_exists="append", index=False, chunksize=10000)
