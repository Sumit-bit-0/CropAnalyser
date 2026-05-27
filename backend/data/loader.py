import pandas as pd
from config import DATA_RAW

def load_agmarknet() -> pd.DataFrame:
    path = DATA_RAW / "agmarknet.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    return df
