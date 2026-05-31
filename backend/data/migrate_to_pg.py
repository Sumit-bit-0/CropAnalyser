"""One-shot migration of the legacy SQLite DB into PostgreSQL.

Streams `prices` (~27.6M rows) and `mandi_prices` (~737K) out of agri.db and
bulk-loads them into Postgres via COPY (the fast path), creates indexes, rebuilds
the summary tables, and verifies row counts match. The SQLite file is only read,
never modified — it stays as a fallback.

Run from backend/ as a module:
    venv\\Scripts\\python.exe -m data.migrate_to_pg
"""
import sqlite3
import sys
import time

import psycopg

from config import DB_PATH, DATABASE_URL
from analysis.summaries import build_summaries

# Devanagari commodity names exist; keep console output safe on Windows.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# psycopg wants a plain libpq URL, not the SQLAlchemy "+psycopg" dialect form.
PG_DSN = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
CHUNK = 200_000

PRICES_DDL = """
    CREATE TABLE prices (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        state TEXT NOT NULL, commodity TEXT NOT NULL,
        year INTEGER NOT NULL, month INTEGER NOT NULL,
        farm_gate_price REAL NOT NULL, modal_price REAL NOT NULL
    )
"""
MANDI_DDL = """
    CREATE TABLE mandi_prices (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        state TEXT, district TEXT, market TEXT, commodity TEXT,
        variety TEXT, grade TEXT,
        min_price REAL, max_price REAL, modal_price REAL, price_date TEXT
    )
"""

# table -> (data columns to copy, create DDL, post-load index statements)
TABLES = {
    "prices": (
        ["state", "commodity", "year", "month", "farm_gate_price", "modal_price"],
        PRICES_DDL,
        ["CREATE INDEX idx_state_commodity ON prices(state, commodity)",
         # Functional index for the LOWER(state)=LOWER(?) AND LOWER(commodity)=LOWER(?)
         # filters in trends/profit — a plain index can't serve those.
         "CREATE INDEX idx_prices_lower_state_commodity ON prices (LOWER(state), LOWER(commodity))"],
    ),
    "mandi_prices": (
        ["state", "district", "market", "commodity", "variety", "grade",
         "min_price", "max_price", "modal_price", "price_date"],
        MANDI_DDL,
        ["CREATE INDEX idx_mandi_commodity ON mandi_prices(commodity)",
         "CREATE INDEX idx_mandi_state_district ON mandi_prices(state, district)",
         # Functional index for mandi_compare's LOWER(commodity)=LOWER(?) filter.
         "CREATE INDEX idx_mandi_lower_commodity ON mandi_prices (LOWER(commodity))"],
    ),
}


def copy_table(sconn, pconn, table, cols, ddl, indexes):
    collist = ", ".join(cols)
    total = sconn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"\n=== {table}: {total:,} rows ===", flush=True)

    pconn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    pconn.execute(ddl)
    pconn.commit()

    done, t0 = 0, time.time()
    src = sconn.execute(f"SELECT {collist} FROM {table}")
    with pconn.cursor() as cur:
        with cur.copy(f"COPY {table} ({collist}) FROM STDIN") as cp:
            while True:
                rows = src.fetchmany(CHUNK)
                if not rows:
                    break
                for row in rows:
                    cp.write_row(row)
                done += len(rows)
                pct = done * 100 // total if total else 100
                print(f"  {done:,}/{total:,} ({pct}%) {time.time() - t0:.0f}s", flush=True)
    pconn.commit()

    for stmt in indexes:
        print(f"  index: {stmt.split('ON')[0].strip()}", flush=True)
        pconn.execute(stmt)
    pconn.commit()

    pg_count = pconn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  loaded {pg_count:,} (sqlite had {total:,}) "
          f"-> {'OK' if pg_count == total else 'MISMATCH!'}", flush=True)
    return total, pg_count


def main():
    print(f"SQLite source : {DB_PATH}")
    print(f"Postgres dest : {PG_DSN.rsplit('@', 1)[-1]}")  # hide creds in log
    sconn = sqlite3.connect(str(DB_PATH))
    pconn = psycopg.connect(PG_DSN)
    try:
        results = {}
        for table, (cols, ddl, idx) in TABLES.items():
            results[table] = copy_table(sconn, pconn, table, cols, ddl, idx)
    finally:
        pconn.close()
        sconn.close()

    print("\n=== rebuilding summary tables ===", flush=True)
    t0 = time.time()
    counts = build_summaries()
    print(f"  summaries rebuilt in {time.time() - t0:.0f}s: {counts}", flush=True)

    ok = all(s == p for s, p in results.values())
    print(f"\n=== DONE === row counts {'all match' if ok else 'MISMATCH — review above'}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
