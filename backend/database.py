import contextlib
import sqlite3
import pandas as pd
from config import DB_PATH, init_dirs


def get_connection() -> sqlite3.Connection:
    init_dirs()
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with contextlib.closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                commodity TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                farm_gate_price REAL NOT NULL,
                modal_price REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_state_commodity ON prices(state, commodity)")
        conn.commit()


def insert_prices(df: pd.DataFrame) -> None:
    with contextlib.closing(get_connection()) as conn:
        df.to_sql("prices", conn, if_exists="append", index=False)
        conn.commit()


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with contextlib.closing(get_connection()) as conn:
        return pd.read_sql_query(sql, conn, params=params)
