"""Ingest mandi-level prices from Agriculture_price_dataset.csv into SQLite.

Run from backend/ as a module:
    venv\\Scripts\\python.exe -m data.load_mandi "E:\\DataSETAgri\\Agriculture_price_dataset.csv"
"""
import sys
import pandas as pd
from sqlalchemy import text
from database import get_engine

COLMAP = {
    "STATE": "state", "District Name": "district", "Market Name": "market",
    "Commodity": "commodity", "Variety": "variety", "Grade": "grade",
    "Min_Price": "min_price", "Max_Price": "max_price", "Modal_Price": "modal_price",
    "Price Date": "price_date",
}


def clean_mandi(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLMAP)
    for c in ["state", "district", "market", "commodity", "variety", "grade"]:
        df[c] = df[c].astype(str).str.strip()
    for c in ["min_price", "max_price", "modal_price"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["price_date"] = pd.to_datetime(df["price_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["modal_price", "price_date"])
    df = df[df["modal_price"] > 0]
    return df[list(COLMAP.values())]


def create_table() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS mandi_prices"))
        conn.execute(text("""
            CREATE TABLE mandi_prices (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                state TEXT, district TEXT, market TEXT, commodity TEXT,
                variety TEXT, grade TEXT,
                min_price REAL, max_price REAL, modal_price REAL,
                price_date TEXT
            )
        """))


def insert(df: pd.DataFrame) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        df.to_sql("mandi_prices", conn, if_exists="append", index=False, chunksize=10000)
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mandi_commodity ON mandi_prices(commodity)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mandi_state_district ON mandi_prices(state, district)"))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else r"E:\DataSETAgri\Agriculture_price_dataset.csv"
    print(f"Reading {path} ...")
    raw = pd.read_csv(path)
    print(f"Raw rows: {len(raw):,}")
    clean = clean_mandi(raw)
    print(f"Clean rows: {len(clean):,}")
    create_table()
    insert(clean)
    print("Done. mandi_prices populated.")
