"""Ingest mandi-level prices into PostgreSQL, merging two sources: the current
Agriculture_price_dataset.csv and the agmarknet historical-prices CSV. Together
they cover ~27 commodities (the current source's Onion/Potato/Rice/Tomato plus
agmarknet's Maize/pulses/oilseeds/vegetables, deduped on the Wheat overlap).

Run from backend/ as a module:
    venv\\Scripts\\python.exe -m data.load_mandi [current_csv [agmarknet_csv]]
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
