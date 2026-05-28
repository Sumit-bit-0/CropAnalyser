import sys
from data.loader import load_agmarknet, load_agmarknet_dir
from data.cleaner import clean_agmarknet
from database import init_db, insert_prices

if __name__ == "__main__":
    source_dir = sys.argv[1] if len(sys.argv) > 1 else None

    print("Loading raw data...")
    if source_dir:
        raw = load_agmarknet_dir(source_dir)
    else:
        raw = load_agmarknet()
    print(f"Total loaded: {len(raw):,} rows")

    print("Cleaning...")
    clean = clean_agmarknet(raw)
    print(f"Clean rows: {len(clean):,}")

    print("Writing to SQLite...")
    init_db()
    insert_prices(clean)
    print("Done.")
