"""Load district-level crop production history into Postgres.

Source: "Crop Production data.csv" (State_Name, District_Name, Crop_Year, Season,
Crop, Area, Production) — real India data, 1997-2015, ~246K rows. Powers the
Regional Fit module: "which crops have a track record in this district/season".

Each row is tagged with `canonical_crop` (from analysis.crop_catalog) when its
production name maps to a whitelist crop, so Regional Fit can query by canonical
name; rows outside the whitelist keep canonical_crop = NULL.

Cleaning notes (from the Phase 0 alignment spike):
  - text columns have trailing whitespace ("Kharif     ") -> stripped
  - State_Name mixes cases ("ANDAMAN AND NICOBAR" vs "Andhra Pradesh") -> title-cased
  - ~3.7K rows have null Production -> dropped (can't contribute to history)

Run from backend/ as a module:
    venv\\Scripts\\python.exe -m data.load_crop_history
    venv\\Scripts\\python.exe -m data.load_crop_history "E:\\DataSETAgri\\Crop Production data.csv"
"""
import sys

import pandas as pd
from sqlalchemy import text

from database import get_engine
from analysis.crop_catalog import CANONICAL_CROPS

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_PATH = r"E:\DataSETAgri\Crop Production data.csv"

COLMAP = {
    "State_Name": "state", "District_Name": "district", "Crop_Year": "crop_year",
    "Season": "season", "Crop": "crop", "Area": "area", "Production": "production",
}

# production alias (exact, stripped) -> canonical whitelist crop
ALIAS_TO_CANONICAL = {
    alias: canon
    for canon, m in CANONICAL_CROPS.items()
    for alias in m["production"]
}

COLUMNS = ["state", "district", "crop_year", "season", "crop",
           "canonical_crop", "area", "production", "crop_yield"]


def clean_history(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLMAP)
    for c in ["state", "district", "season", "crop"]:
        df[c] = df[c].astype(str).str.strip()
    # normalize state/district case so they align with the rest of the app
    df["state"] = df["state"].str.title()
    df["district"] = df["district"].str.title()

    df["crop_year"] = pd.to_numeric(df["crop_year"], errors="coerce").astype("Int64")
    df["area"] = pd.to_numeric(df["area"], errors="coerce")
    df["production"] = pd.to_numeric(df["production"], errors="coerce")

    # need production and a positive area to be useful for history/yield
    df = df.dropna(subset=["production", "area", "crop_year"])
    df = df[df["area"] > 0]

    df["canonical_crop"] = df["crop"].map(ALIAS_TO_CANONICAL)
    df["crop_yield"] = (df["production"] / df["area"]).round(4)

    df["canonical_crop"] = df["canonical_crop"].astype(object).where(
        df["canonical_crop"].notna(), None
    )
    return df[COLUMNS]


def create_table() -> None:
    with get_engine().begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS district_crop_history"))
        conn.execute(text("""
            CREATE TABLE district_crop_history (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                state TEXT, district TEXT,
                crop_year INTEGER, season TEXT,
                crop TEXT, canonical_crop TEXT,
                area REAL, production REAL, crop_yield REAL
            )
        """))


def insert(df: pd.DataFrame) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        df.to_sql("district_crop_history", conn, if_exists="append",
                  index=False, chunksize=10000)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_dch_canonical ON district_crop_history(canonical_crop)"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_dch_lower_state_district "
            "ON district_crop_history (LOWER(state), LOWER(district))"))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    print(f"Reading {path} ...", flush=True)
    raw = pd.read_csv(path)
    print(f"Raw rows: {len(raw):,}", flush=True)
    clean = clean_history(raw)
    mapped = clean["canonical_crop"].notna().sum()
    print(f"Clean rows: {len(clean):,}  ({mapped:,} mapped to a whitelist crop)", flush=True)
    create_table()
    insert(clean)
    print("=== DONE === district_crop_history populated.", flush=True)
