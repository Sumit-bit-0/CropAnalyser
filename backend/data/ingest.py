from data.loader import load_agmarknet
from data.cleaner import clean_agmarknet
from database import init_db, insert_prices

if __name__ == "__main__":
    print("Loading raw data...")
    raw = load_agmarknet()
    print(f"Loaded {len(raw)} rows")
    print("Cleaning...")
    clean = clean_agmarknet(raw)
    print(f"Clean rows: {len(clean)}")
    print("Writing to SQLite...")
    init_db()
    insert_prices(clean)
    print("Done.")
