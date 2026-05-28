import pandas as pd
from pathlib import Path
from config import DATA_RAW


def load_agmarknet() -> pd.DataFrame:
    path = DATA_RAW / "agmarknet.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    return df


def load_agmarknet_dir(source_dir: str | Path) -> pd.DataFrame:
    source_dir = Path(source_dir)
    frames = []
    for csv_file in sorted(source_dir.glob("*.csv")):
        df = pd.read_csv(csv_file, encoding="utf-8-sig", low_memory=False)
        df.columns = df.columns.str.strip()
        frames.append(df)
        print(f"  Loaded {csv_file.name}: {len(df):,} rows")
    return pd.concat(frames, ignore_index=True)
