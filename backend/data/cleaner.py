import pandas as pd


def clean_agmarknet(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(subset=["State", "Commodity", "Arrival_Date"])
    df["farm_gate_price"] = pd.to_numeric(df["Min_Price"], errors="coerce").astype(float)
    df["modal_price"] = pd.to_numeric(df["Modal_Price"], errors="coerce").astype(float)
    df = df.dropna(subset=["farm_gate_price", "modal_price"])
    df = df[df["farm_gate_price"] > 0]
    df["date"] = pd.to_datetime(df["Arrival_Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["state"] = df["State"].str.strip().str.title()
    df["commodity"] = df["Commodity"].str.strip().str.title()
    return df[["state", "commodity", "year", "month", "farm_gate_price", "modal_price"]]
